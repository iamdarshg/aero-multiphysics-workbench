"""Deterministic candidate generation over the canonical design space.

GEN 03. This module turns a ``DesignRevision.designSpace`` document (the same
canonical JSON mirrored by :mod:`aeroworkbench_optimization.design_space`) into a
bounded, lazy stream of immutable, content-addressed :class:`Candidate`
revisions plus generation provenance.

Design goals:

- **Mixed and conditional by construction.** Continuous, integer, discrete,
  categorical, boolean, and vector-profile variables are sampled natively; a
  categorical is never coerced to a number. Activation rules (``activeWhen``)
  and branch membership are evaluated during traversal, so an inactive branch
  is never enumerated and impossible assignments are never produced. Linked and
  derived variables are resolved from the design-space contract, never sampled.
- **Bounded before expensive work.** Exact cardinality is exposed when it is
  finite and cheap; otherwise an upper-bound estimate is. Enumerative
  strategies require an explicit hard budget and stop with a recorded reason
  instead of materializing a combinatorial explosion.
- **Deterministic and auditable.** A fixed seed reproduces the same candidate
  sequence. Every candidate records its parent hash, normalized assignment,
  mutation record, content hash, strategy/seed/index, and preflight state so a
  consumer can reconstruct why candidate *N* exists.

No solver is executed here; generation is pure combination plus the existing
design-space contract.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from .design_space import (
    DesignSpaceError,
    active_variable_ids,
    candidate_hash,
    canonical_json,
    content_digest,
    effective_profile_length,
    flatten_design_state,
    preflight_design_state,
    validate_design_space,
    variable_is_active,
)

__all__ = [
    "Assignment",
    "Candidate",
    "CandidateGenerator",
    "CandidateProvenance",
    "CardinalityEstimate",
    "GenerationBudgetError",
    "GenerationError",
    "GenerationPlan",
    "GenerationRequest",
    "GenerationStats",
    "Mutation",
    "STRATEGIES",
]

GENERATOR_VERSION = "gen03-v1"

#: Strategies accepted by :class:`GenerationRequest`.
STRATEGIES = ("grid", "factorial", "permutation", "random", "lhs", "halton", "sobol")

_ENUMERATIVE = frozenset({"grid", "factorial", "permutation"})
_STOCHASTIC = frozenset({"random", "lhs", "halton", "sobol"})

_MAX_CARDINALITY = 10**18
_FREE_KINDS = frozenset(
    {"continuous", "integer", "discrete", "categorical", "boolean", "vector-profile"}
)
_FIXED_KINDS = frozenset({"linked", "derived"})


class GenerationError(ValueError):
    """Raised when a generation request is structurally invalid."""


class GenerationBudgetError(GenerationError):
    """Raised when a request would exceed its hard candidate budget."""


# ---------------------------------------------------------------------------
# small deterministic helpers (stdlib only)
# ---------------------------------------------------------------------------


def _fixed_value(leaf: _Leaf) -> Any:
    if leaf.base is not None:
        return leaf.base
    if leaf.kind in {"categorical", "boolean", "discrete"}:
        return leaf.values[0]
    if leaf.lower is not None and leaf.upper is not None:
        return (leaf.lower + leaf.upper) / 2.0
    return 0.0


def _axis_values(leaf: _Leaf, strategy: str, levels: int) -> list[Any]:
    if strategy == "permutation" and leaf.kind in {"continuous", "integer"}:
        return [_fixed_value(leaf)]
    if leaf.kind in {"categorical", "boolean", "discrete"}:
        return list(leaf.values)
    if leaf.kind == "integer":
        lower = int(leaf.lower)  # type: ignore[arg-type]
        upper = int(leaf.upper)  # type: ignore[arg-type]
        step = max(1, int(leaf.step or 1))
        return [float(value) for value in range(lower, upper + 1, step)]
    if leaf.kind == "continuous":
        assert leaf.lower is not None and leaf.upper is not None
        if levels <= 1:
            return [(leaf.lower + leaf.upper) / 2.0]
        return [
            leaf.lower + index * (leaf.upper - leaf.lower) / (levels - 1)
            for index in range(levels)
        ]
    raise GenerationError(f"UNKNOWN_LEAF_KIND:{leaf.kind}")


def _domain_size(leaf: _Leaf, strategy: str, levels: int) -> int:
    if strategy == "permutation" and leaf.kind in {"continuous", "integer"}:
        return 1
    if leaf.kind in {"categorical", "boolean", "discrete"}:
        return len(leaf.values)
    if leaf.kind == "integer":
        lower = int(leaf.lower)  # type: ignore[arg-type]
        upper = int(leaf.upper)  # type: ignore[arg-type]
        step = max(1, int(leaf.step or 1))
        return (upper - lower) // step + 1
    if leaf.kind == "continuous":
        return max(1, levels)
    raise GenerationError(f"UNKNOWN_LEAF_KIND:{leaf.kind}")


def _predicate_variables(predicate: Mapping[str, Any]) -> list[str]:
    op = predicate.get("op")
    if op in {"equals", "in"}:
        return [str(predicate["variable"])]
    if op == "not":
        return _predicate_variables(predicate["clause"])
    if op in {"all", "any"}:
        found: list[str] = []
        for clause in predicate["clauses"]:
            found.extend(_predicate_variables(clause))
        return found
    return [str(predicate["variable"])]


def _expression_variables(expression: Mapping[str, Any]) -> list[str]:
    op = expression.get("op")
    if op == "variable":
        return [str(expression["variable"])]
    if op == "constant":
        return []
    return [
        *_expression_variables(expression["left"]),
        *_expression_variables(expression["right"]),
    ]


def _halton(index: int, base: int) -> float:
    """Deterministic radical-inverse low-discrepancy coordinate."""
    result = 0.0
    factor = 1.0 / base
    position = index + 1
    while position > 0:
        result += factor * (position % base)
        position //= base
        factor /= base
    return result


def _first_primes(count: int) -> list[int]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        if all(candidate % prime for prime in primes):
            primes.append(candidate)
        candidate += 1
    return primes


# ---------------------------------------------------------------------------
# decision model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Leaf:
    """One samplable scalar axis; vector-profile control points become leaves."""

    variable_id: str
    point_id: str | None
    kind: str
    unit: str | None
    lower: float | None
    upper: float | None
    step: float | None
    values: tuple[Any, ...]
    base: Any

    @property
    def key(self) -> str:
        return self.variable_id if self.point_id is None else f"{self.variable_id}::{self.point_id}"


def _variable_leaves(variable: Mapping[str, Any]) -> list[_Leaf]:
    variable_id = str(variable["id"])
    kind = variable["kind"]
    unit = variable.get("unit")
    if kind == "vector-profile":
        return [
            _Leaf(
                variable_id, str(point["id"]), "continuous", unit,
                float(point["lower"]), float(point["upper"]), None, (),
                float(point["baseValue"]),
            )
            for point in variable["domain"]["controlPoints"]
        ]
    domain = variable["domain"]
    if kind == "continuous":
        return [
            _Leaf(
                variable_id, None, kind, unit,
                float(domain["lower"]), float(domain["upper"]), None, (),
                variable.get("baseValue"),
            )
        ]
    if kind == "integer":
        return [
            _Leaf(
                variable_id, None, kind, unit,
                float(domain["lower"]), float(domain["upper"]), float(domain["step"]),
                (), variable.get("baseValue"),
            )
        ]
    if kind == "discrete":
        return [
            _Leaf(
                variable_id, None, kind, unit, None, None, None,
                tuple(float(value) for value in domain["values"]), variable.get("baseValue"),
            )
        ]
    if kind == "categorical":
        return [
            _Leaf(
                variable_id, None, kind, None, None, None, None,
                tuple(str(value) for value in domain["values"]), variable.get("baseValue"),
            )
        ]
    if kind == "boolean":
        return [
            _Leaf(
                variable_id, None, kind, None, None, None, None,
                (False, True), variable.get("baseValue"),
            )
        ]
    raise GenerationError(f"UNKNOWN_VARIABLE_KIND:{variable_id}")


def _dependency_order(space: Mapping[str, Any]) -> list[str]:
    """Variable order where selectors/lengths/targets precede their dependents."""
    variables = [str(variable["id"]) for variable in space["variables"]]
    edges: dict[str, set[str]] = {variable_id: set() for variable_id in variables}

    def add(variable_id: str, dependency: str) -> None:
        if dependency in edges:
            edges[variable_id].add(dependency)

    for variable in space["variables"]:
        variable_id = str(variable["id"])
        domain = variable["domain"]
        if domain["kind"] == "linked":
            add(variable_id, str(domain["targetVariable"]))
        elif domain["kind"] == "derived":
            for name in _expression_variables(domain["expression"]):
                add(variable_id, name)
        elif domain["kind"] == "vector-profile" and domain.get("lengthVariable") is not None:
            add(variable_id, str(domain["lengthVariable"]))
        if variable.get("activeWhen") is not None:
            for name in _predicate_variables(variable["activeWhen"]):
                add(variable_id, name)
    for branch in space.get("branches", ()):
        selector = str(branch["selector"])
        for members in branch.get("options", {}).values():
            for member in members:
                add(str(member), selector)

    ordered: list[str] = []
    state: dict[str, str] = {}

    def visit(variable_id: str) -> None:
        current = state.get(variable_id)
        if current == "done":
            return
        if current == "visiting":
            raise GenerationError(f"DESIGN_SPACE_ACTIVATION_CYCLE:{variable_id}")
        state[variable_id] = "visiting"
        for dependency in sorted(edges[variable_id]):
            visit(dependency)
        state[variable_id] = "done"
        ordered.append(variable_id)

    for variable_id in variables:
        visit(variable_id)
    return ordered


# ---------------------------------------------------------------------------
# request / plan / stats
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CardinalityEstimate:
    exact: bool
    count: int | None
    estimate: int
    reason: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    strategy: str
    count: int | None = None
    seed: int = 0
    levels: int = 3
    budget: int | None = None
    parent_hash: str | None = None
    parent_state: Mapping[str, Any] | None = None
    on_budget: str = "truncate"

    def __post_init__(self) -> None:
        if self.strategy not in STRATEGIES:
            raise GenerationError(f"UNKNOWN_GENERATION_STRATEGY:{self.strategy}")
        if self.count is not None and self.count <= 0:
            raise GenerationError("GENERATION_COUNT_MUST_BE_POSITIVE")
        if self.levels <= 0:
            raise GenerationError("GENERATION_LEVELS_MUST_BE_POSITIVE")
        if self.budget is not None and self.budget <= 0:
            raise GenerationError("GENERATION_BUDGET_MUST_BE_POSITIVE")
        if self.on_budget not in {"truncate", "raise"}:
            raise GenerationError(f"UNKNOWN_ON_BUDGET:{self.on_budget}")
        if not isinstance(self.seed, int):
            raise GenerationError("GENERATION_SEED_MUST_BE_INTEGER")

    def config(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "count": self.count,
            "seed": self.seed,
            "levels": self.levels,
            "budget": self.budget,
        }


@dataclass(frozen=True, slots=True)
class GenerationPlan:
    strategy: str
    cardinality: CardinalityEstimate
    requested: int | None
    budget: int | None
    exceeds_budget: bool
    stop_reason: str | None
    config_digest: str


@dataclass(slots=True)
class GenerationStats:
    generated: int = 0
    emitted: int = 0
    duplicates: int = 0
    preflight_invalid: int = 0
    stop_reason: str | None = None


# ---------------------------------------------------------------------------
# candidate records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Assignment:
    variable_id: str
    point_id: str | None
    kind: str
    value: Any
    unit: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "variableId": self.variable_id,
            "kind": self.kind,
            "value": self.value,
        }
        if self.point_id is not None:
            payload["pointId"] = self.point_id
        if self.unit is not None:
            payload["unit"] = self.unit
        return payload


@dataclass(frozen=True, slots=True)
class Mutation:
    variable_id: str
    point_id: str | None
    before: Any
    after: Any
    source: str  # "parent" | "base"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "variableId": self.variable_id,
            "before": self.before,
            "after": self.after,
            "source": self.source,
        }
        if self.point_id is not None:
            payload["pointId"] = self.point_id
        return payload


@dataclass(frozen=True, slots=True)
class CandidateProvenance:
    space_id: str
    parent_hash: str | None
    strategy: str
    seed: int
    index: int
    requested: int | None
    config_digest: str
    generator_version: str = GENERATOR_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "spaceId": self.space_id,
            "parentHash": self.parent_hash,
            "strategy": self.strategy,
            "seed": self.seed,
            "index": self.index,
            "requested": self.requested,
            "configDigest": self.config_digest,
            "generatorVersion": self.generator_version,
        }


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_hash: str
    parent_hash: str | None
    space_id: str
    index: int
    strategy: str
    seed: int
    preflight_state: str  # "valid" | "preflight-invalid"
    preflight_reasons: tuple[str, ...]
    active_variables: tuple[str, ...]
    assignment: tuple[Assignment, ...]
    mutations: tuple[Mutation, ...]
    normalized: tuple[tuple[str, float], ...]
    state: Mapping[str, Any]
    flat: Mapping[str, Any] | None
    provenance: CandidateProvenance

    @property
    def valid(self) -> bool:
        return self.preflight_state == "valid"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "parentHash": self.parent_hash,
            "spaceId": self.space_id,
            "index": self.index,
            "strategy": self.strategy,
            "seed": self.seed,
            "preflightState": self.preflight_state,
            "preflightReasons": list(self.preflight_reasons),
            "activeVariables": list(self.active_variables),
            "assignment": [item.as_dict() for item in self.assignment],
            "mutations": [item.as_dict() for item in self.mutations],
            "normalized": [list(item) for item in self.normalized],
            "state": _canonical(self.state),
            "provenance": self.provenance.as_dict(),
        }

    def content_digest(self) -> str:
        return content_digest(self.as_dict())


def _canonical(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return 0 if value == 0 else value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# generator
# ---------------------------------------------------------------------------


class CandidateGenerator:
    """Lazy, bounded, deterministic candidate stream for one request."""

    def __init__(self, space: Mapping[str, Any], request: GenerationRequest) -> None:
        validate_design_space(space)
        self.space = space
        self.request = request
        self.index = {str(variable["id"]): variable for variable in space["variables"]}
        self.order = _dependency_order(space)
        self.leaves_by_variable = {
            variable_id: _variable_leaves(self.index[variable_id])
            for variable_id in self.order
            if self.index[variable_id]["kind"] in _FREE_KINDS
        }
        self.leaves = [
            leaf for variable_id in self.order for leaf in self.leaves_by_variable[variable_id]
        ]
        if not self.leaves:
            raise GenerationError("DESIGN_SPACE_HAS_NO_FREE_VARIABLES")
        self.membership = self._branch_membership()
        self.stats = GenerationStats()
        self.plan = self._plan()
        if request.strategy in _ENUMERATIVE and request.budget is None:
            raise GenerationBudgetError("EXPLICIT_BUDGET_REQUIRED_FOR_ENUMERATION")
        if request.strategy in _STOCHASTIC and request.count is None:
            raise GenerationError("STOCHASTIC_STRATEGY_REQUIRES_COUNT")
        if self.plan.exceeds_budget and request.on_budget == "raise":
            raise GenerationBudgetError(
                f"REQUEST_EXCEEDS_BUDGET:{self.plan.cardinality.estimate}>{self.plan.budget}"
            )
        self._limit = self._effective_limit()

    # -- planning --------------------------------------------------------

    def _branch_membership(self) -> dict[str, list[str]]:
        membership: dict[str, list[str]] = {}
        for branch in self.space.get("branches", ()):
            selector = str(branch["selector"])
            for members in branch.get("options", {}).values():
                for member in members:
                    membership.setdefault(str(member), []).append(selector)
        return membership

    def _plan(self) -> GenerationPlan:
        estimate = 1
        saturate = False
        for leaf in self.leaves:
            size = _domain_size(leaf, self.request.strategy, self.request.levels)
            estimate *= size
            if estimate > _MAX_CARDINALITY:
                estimate = _MAX_CARDINALITY
                saturate = True
                break
        conditional = bool(self.space.get("branches")) or any(
            variable.get("activeWhen") is not None for variable in self.space["variables"]
        )
        aliased_profile = any(
            variable["kind"] == "vector-profile"
            and variable["domain"].get("lengthVariable") is not None
            for variable in self.space["variables"]
        )
        exact = (
            self.request.strategy in _ENUMERATIVE
            and not conditional
            and not aliased_profile
            and not saturate
        )
        if exact:
            reason = "finite product of declared domains"
        elif conditional:
            reason = "conditional activation: upper-bound estimate"
        elif aliased_profile:
            reason = "profile length aliases: upper-bound estimate"
        elif saturate:
            reason = "cardinality saturates estimate cap"
        else:
            reason = "strategy samples a finite count"
        cardinality = CardinalityEstimate(exact, estimate if exact else None, estimate, reason)
        requested = self.request.count
        if self.request.strategy in _ENUMERATIVE:
            planned = estimate if requested is None else min(estimate, requested)
        else:
            planned = requested or 0
        budget = self.request.budget
        exceeds = budget is not None and planned > budget
        config_digest = content_digest(
            {"space": self.space["id"], "version": GENERATOR_VERSION, **self.request.config()}
        )
        stop_reason: str | None = None
        if exceeds:
            stop_reason = "budget"
        elif requested is not None and planned > requested:
            stop_reason = "count"
        return GenerationPlan(
            self.request.strategy, cardinality, requested, budget, exceeds, stop_reason,
            config_digest,
        )

    def _effective_limit(self) -> int | None:
        limits: list[int] = []
        if self.request.budget is not None:
            limits.append(self.request.budget)
        if self.request.count is not None:
            limits.append(self.request.count)
        return min(limits) if limits else None

    # -- public API ------------------------------------------------------

    def __iter__(self) -> Iterator[Candidate]:
        self.stats = GenerationStats()
        if self.request.strategy in _ENUMERATIVE:
            raw = self._iter_enumerative()
        else:
            raw = self._iter_stochastic()
        seen: set[str] = set()
        limit = self._limit
        for state, index in raw:
            self.stats.generated += 1
            candidate = self._build_candidate(state, index)
            if candidate.candidate_hash in seen:
                self.stats.duplicates += 1
                continue
            seen.add(candidate.candidate_hash)
            self.stats.emitted += 1
            if not candidate.valid:
                self.stats.preflight_invalid += 1
            yield candidate
            if limit is not None and self.stats.emitted >= limit:
                budget_hit = (
                    self.request.budget is not None
                    and self.stats.emitted >= self.request.budget
                )
                self.stats.stop_reason = "budget" if budget_hit else "count"
                return
        self.stats.stop_reason = "exhausted"

    def take(self, count: int) -> tuple[Candidate, ...]:
        if count <= 0:
            raise GenerationError("TAKE_COUNT_MUST_BE_POSITIVE")
        return tuple(itertools.islice(iter(self), count))

    def plan_cardinality(self) -> CardinalityEstimate:
        return self.plan.cardinality

    # -- enumerative traversal (conditional-aware, lazy) -----------------

    def _context_state(self, rows: Mapping[str, Any]) -> dict[str, Any]:
        """Partial state used only for activation; base values fill the gaps."""
        state: dict[str, Any] = {}
        for variable_id, leaves in self.leaves_by_variable.items():
            if all(leaf.key in rows for leaf in leaves):
                variable = self.index[variable_id]
                if variable["kind"] == "vector-profile":
                    state[variable_id] = {
                        "kind": "vector-profile",
                        "points": [
                            _point_entry(leaf, rows[leaf.key]) for leaf in leaves
                        ],
                    }
                else:
                    state[variable_id] = _leaf_entry(leaves[0], rows[leaves[0].key])
        for variable_id, variable in self.index.items():
            if variable_id in state or variable["kind"] in _FIXED_KINDS:
                continue
            if variable["kind"] not in _FREE_KINDS:
                continue
            base = variable.get("baseValue")
            if base is not None:
                state[variable_id] = _base_entry(variable)
        return state

    def _iter_enumerative(self) -> Iterator[tuple[dict[str, Any], int]]:
        rows: dict[str, Any] = {}
        counter = itertools.count()

        def walk(position: int) -> Iterator[tuple[dict[str, Any], int]]:
            if position == len(self.order):
                yield self._materialize(rows), next(counter)
                return
            variable_id = self.order[position]
            variable = self.index[variable_id]
            if variable["kind"] in _FIXED_KINDS:
                yield from walk(position + 1)
                return
            context = self._context_state(rows)
            try:
                active = variable_is_active(self.space, context, variable_id)
            except DesignSpaceError:
                active = True
            if not active:
                yield from walk(position + 1)
                return
            leaves = self.leaves_by_variable[variable_id]
            axes = [
                _axis_values(leaf, self.request.strategy, self.request.levels)
                for leaf in leaves
            ]
            if variable["kind"] == "vector-profile":
                length = _resolved_length(self.space, self.index, variable, context)
                axes = axes[:length]
                leaves = leaves[:length]
            for combination in itertools.product(*axes):
                for leaf, value in zip(leaves, combination, strict=True):
                    rows[leaf.key] = value
                yield from walk(position + 1)
                for leaf in leaves:
                    rows.pop(leaf.key, None)

        yield from walk(0)

    # -- stochastic sampling --------------------------------------------

    def _unit_rows(self, count: int) -> list[list[float]]:
        dimension = len(self.leaves)
        strategy = self.request.strategy
        if strategy == "random":
            rng = random.Random(self.request.seed)
            return [[rng.random() for _ in range(dimension)] for _ in range(count)]
        if strategy == "lhs":
            import numpy as np
            from scipy.stats import qmc

            sampler = qmc.LatinHypercube(d=dimension, seed=self.request.seed)
            return [
                [float(value) for value in row]
                for row in np.asarray(sampler.random(n=count))
            ]
        if strategy == "sobol":
            import numpy as np
            from scipy.stats import qmc

            sampler = qmc.Sobol(d=dimension, scramble=True, seed=self.request.seed)
            return [
                [float(value) for value in row]
                for row in np.asarray(sampler.random(n=count))
            ]
        if strategy == "halton":
            primes = _first_primes(dimension)
            return [
                [_halton(sample, primes[axis]) for axis in range(dimension)]
                for sample in range(count)
            ]
        raise GenerationError(f"UNKNOWN_GENERATION_STRATEGY:{strategy}")

    def _iter_stochastic(self) -> Iterator[tuple[dict[str, Any], int]]:
        count = self.request.count or 0
        for sample_index, row in enumerate(self._unit_rows(count)):
            rows: dict[str, Any] = {}
            for leaf, unit in zip(self.leaves, row, strict=True):
                rows[leaf.key] = _unit_to_value(leaf, unit)
            yield self._materialize(rows), sample_index

    # -- materialization / identity -------------------------------------

    def _materialize(self, rows: Mapping[str, Any]) -> dict[str, Any]:
        """Active-only state; inactive branches are omitted, not generated."""
        active_rows: dict[str, Any] = {}
        for variable_id, leaves in self.leaves_by_variable.items():
            if any(leaf.key not in rows for leaf in leaves):
                continue
            active_rows[variable_id] = [rows[leaf.key] for leaf in leaves]
        context = self._context_state(rows)
        try:
            active = set(active_variable_ids(self.space, context))
        except DesignSpaceError:
            active = {variable_id for variable_id in self.leaves_by_variable}
        state: dict[str, Any] = {}
        for variable_id in self.order:
            if variable_id not in active_rows or variable_id not in active:
                continue
            variable = self.index[variable_id]
            leaves = self.leaves_by_variable[variable_id]
            values = active_rows[variable_id]
            if variable["kind"] == "vector-profile":
                length = _resolved_length(self.space, self.index, variable, context)
                points = [
                    _point_entry(leaf, value)
                    for leaf, value in list(zip(leaves, values, strict=True))[:length]
                ]
                if not points:
                    continue
                state[variable_id] = {"kind": "vector-profile", "points": points}
            else:
                state[variable_id] = _leaf_entry(leaves[0], values[0])
        return state

    def _build_candidate(self, state: Mapping[str, Any], index: int) -> Candidate:
        try:
            reasons = preflight_design_state(self.space, state)
        except DesignSpaceError as exc:
            reasons = (f"PREFLIGHT_ERROR:{exc}",)
        flat: Mapping[str, Any] | None = None
        if reasons:
            candidate_id = _tolerant_identity(self.space, state)
            preflight_state = "preflight-invalid"
            active: tuple[str, ...] = ()
        else:
            flat = flatten_design_state(self.space, state)
            candidate_id = candidate_hash(flat)
            preflight_state = "valid"
            active = tuple(str(name) for name in flat["order"])
        assignment = tuple(
            Assignment(
                leaf.variable_id, leaf.point_id, leaf.kind, value,
                leaf.unit,
            )
            for leaf in self.leaves
            if (value := _row_value(self, state, leaf)) is not None
        )
        mutations = self._mutations(assignment)
        normalized = self._normalize(assignment)
        provenance = CandidateProvenance(
            str(self.space["id"]), self.request.parent_hash, self.request.strategy,
            self.request.seed, index, self.request.count, self.plan.config_digest,
        )
        return Candidate(
            candidate_id, self.request.parent_hash, str(self.space["id"]), index,
            self.request.strategy, self.request.seed, preflight_state, tuple(reasons),
            active, assignment, mutations, normalized, dict(state), flat, provenance,
        )

    def _mutations(self, assignment: tuple[Assignment, ...]) -> tuple[Mutation, ...]:
        parent = self.request.parent_state
        mutations: list[Mutation] = []
        for item in assignment:
            if parent is not None:
                before = _read_parent(parent, item)
                if before is None or canonical_json(_canonical(before)) != canonical_json(
                    _canonical(item.value)
                ):
                    mutations.append(
                        Mutation(item.variable_id, item.point_id, before, item.value, "parent")
                    )
            else:
                mutations.append(
                    Mutation(item.variable_id, item.point_id, None, item.value, "base")
                )
        return tuple(mutations)

    def _normalize(self, assignment: tuple[Assignment, ...]) -> tuple[tuple[str, float], ...]:
        normalized: list[tuple[str, float]] = []
        for leaf in self.leaves:
            item = next(
                (
                    entry
                    for entry in assignment
                    if entry.variable_id == leaf.variable_id and entry.point_id == leaf.point_id
                ),
                None,
            )
            if item is None:
                continue
            normalized.append((leaf.key, _normalize_value(leaf, item.value)))
        return tuple(normalized)


def _leaf_entry(leaf: _Leaf, value: Any) -> dict[str, Any]:
    if leaf.kind == "categorical":
        return {"kind": "categorical", "value": str(value)}
    if leaf.kind == "boolean":
        return {"kind": "boolean", "value": bool(value)}
    if leaf.unit is not None:
        return {"kind": "number", "value": float(value), "unit": leaf.unit}
    return {"kind": "dimensionless", "value": float(value)}


def _base_entry(variable: Mapping[str, Any]) -> dict[str, Any]:
    base = variable["baseValue"]
    if variable["kind"] == "categorical":
        return {"kind": "categorical", "value": str(base)}
    if variable["kind"] == "boolean":
        return {"kind": "boolean", "value": bool(base)}
    if variable["kind"] == "vector-profile":
        return {
            "kind": "vector-profile",
            "points": [
                {
                    "id": str(point["id"]),
                    "value": float(point["baseValue"]),
                    **({"unit": variable["unit"]} if variable.get("unit") else {}),
                }
                for point in variable["domain"]["controlPoints"]
            ],
        }
    if variable.get("unit") is not None:
        return {"kind": "number", "value": float(base), "unit": variable["unit"]}
    return {"kind": "dimensionless", "value": float(base)}


def _point_entry(leaf: _Leaf, value: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": leaf.point_id, "value": float(value)}
    if leaf.unit is not None:
        entry["unit"] = leaf.unit
    return entry


def _unit_to_value(leaf: _Leaf, unit: float) -> Any:
    unit = min(max(unit, 0.0), 1.0)
    if leaf.kind in {"categorical", "boolean", "discrete"}:
        position = min(len(leaf.values) - 1, int(unit * len(leaf.values)))
        return leaf.values[position]
    assert leaf.lower is not None and leaf.upper is not None
    if leaf.kind == "integer":
        raw = leaf.lower + unit * (leaf.upper - leaf.lower)
        return float(round(raw))
    return leaf.lower + unit * (leaf.upper - leaf.lower)


def _normalize_value(leaf: _Leaf, value: Any) -> float:
    if leaf.kind in {"categorical", "boolean", "discrete"}:
        try:
            position = leaf.values.index(value)
        except ValueError:
            return 0.0
        if len(leaf.values) <= 1:
            return 0.0
        return position / (len(leaf.values) - 1)
    assert leaf.lower is not None and leaf.upper is not None
    if leaf.upper == leaf.lower:
        return 0.0
    return min(max((float(value) - leaf.lower) / (leaf.upper - leaf.lower), 0.0), 1.0)


def _resolved_length(
    space: Mapping[str, Any],
    index: Mapping[str, Mapping[str, Any]],
    variable: Mapping[str, Any],
    state: Mapping[str, Any],
) -> int:
    try:
        return effective_profile_length(variable, index, state)
    except (DesignSpaceError, KeyError):
        return len(variable["domain"]["controlPoints"])


def _row_value(
    generator: CandidateGenerator, state: Mapping[str, Any], leaf: _Leaf
) -> Any | None:
    variable = generator.index.get(leaf.variable_id)
    if variable is None:
        return None
    entry = state.get(leaf.variable_id)
    if entry is None:
        return None
    if leaf.point_id is not None:
        for point in entry.get("points", ()):
            if str(point["id"]) == leaf.point_id:
                return point.get("value")
        return None
    return entry.get("value")


def _read_parent(parent: Mapping[str, Any], item: Assignment) -> Any:
    entry = parent.get(item.variable_id)
    if not isinstance(entry, Mapping):
        return None
    if item.point_id is not None:
        for point in entry.get("points", ()):
            if str(point["id"]) == item.point_id:
                return point.get("value")
        return None
    return entry.get("value")


def _tolerant_identity(space: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    restricted = dict(state)
    try:
        active = set(active_variable_ids(space, state))
        restricted = {key: value for key, value in state.items() if key in active}
    except DesignSpaceError:
        pass
    return content_digest({"space": space["id"], "variables": _canonical(restricted)})
