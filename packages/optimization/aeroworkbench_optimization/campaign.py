"""Autonomous, auditable multi-fidelity engineering campaign engine.

GEN 04. This layer turns the bounded candidate stream from
:mod:`aeroworkbench_optimization.generation` into a resumable campaign:
cheap candidates are evaluated, invalid/nonconverged candidates are rejected
with explicit reasons, a diverse feasible set is selected, and promising
candidates are promoted up a declared fidelity ladder using *measured*
signals (maturity, constraint margin, solver disagreement, sensitivity,
convergence difficulty, mesh/timestep dependence, resonance warnings, cost).

The engine reuses the existing quality gate (``assess_sample``), fidelity
planner (``plan_fidelity``), and objective/constraint contracts
(``StudyObjective``/``StudyConstraint``) rather than duplicating them. It never
invents a favorable score for an invalid sample, never silently raises a
remote/cost limit, and preserves all evidence when stopped or cancelled.

Selection is generic: feasible-first filtering, weighted scalar ranking,
Pareto fronts, deterministic top-K, and greedy max-min diversity in normalized
design-variable space. No application-specific ranking logic lives here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import ceil, isfinite, sqrt
from time import perf_counter
from typing import Any, Protocol, runtime_checkable

from .batch_eval import (
    BatchEvaluator,
    BatchRequest,
    BatchRow,
    plan_batch_size,
)
from .design_space import content_digest
from .drivers import StudyConstraint, StudyObjective
from .generation import Candidate, CandidateGenerator, GenerationRequest
from .planner import FidelityImplementation, FidelitySignals, plan_fidelity
from .quality import PhysicsFlags, QualityPolicy, assess_sample

__all__ = [
    "CANDIDATE_STATUSES",
    "CampaignBudget",
    "CampaignRecord",
    "CampaignSpec",
    "CampaignState",
    "CandidateRecord",
    "EvaluationRecord",
    "EvaluationResult",
    "Evaluator",
    "InMemoryResultStore",
    "PromotionDecision",
    "ResultStore",
    "Selector",
    "pareto_front",
    "rank_weighted",
    "result_key",
    "run_campaign",
    "scalarized",
    "select_diverse",
    "select_feasible",
    "top_k",
]

CANDIDATE_STATUSES = (
    "pending",
    "preflight-invalid",
    "invalid",
    "feasible",
    "infeasible",
    "promoted",
    "retained",
)


class CampaignState(StrEnum):
    """Campaign lifecycle; transitions are recorded for auditability."""

    CREATED = "CREATED"
    GENERATING = "GENERATING"
    EVALUATING = "EVALUATING"
    SELECTING = "SELECTING"
    PROMOTING = "PROMOTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_TERMINAL = {CampaignState.COMPLETED, CampaignState.FAILED, CampaignState.CANCELLED}

_LEGAL_TRANSITIONS: dict[CampaignState, frozenset[CampaignState]] = {
    CampaignState.CREATED: frozenset({CampaignState.GENERATING, CampaignState.COMPLETED,
                                      CampaignState.CANCELLED, CampaignState.FAILED}),
    CampaignState.GENERATING: frozenset({CampaignState.EVALUATING, CampaignState.COMPLETED,
                                         CampaignState.CANCELLED, CampaignState.FAILED}),
    CampaignState.EVALUATING: frozenset({CampaignState.SELECTING, CampaignState.COMPLETED,
                                         CampaignState.CANCELLED, CampaignState.FAILED}),
    CampaignState.SELECTING: frozenset({CampaignState.PROMOTING, CampaignState.COMPLETED,
                                        CampaignState.CANCELLED, CampaignState.FAILED}),
    CampaignState.PROMOTING: frozenset({CampaignState.EVALUATING, CampaignState.COMPLETED,
                                        CampaignState.CANCELLED, CampaignState.FAILED}),
    CampaignState.COMPLETED: frozenset(),
    CampaignState.FAILED: frozenset(),
    CampaignState.CANCELLED: frozenset(),
}


# ---------------------------------------------------------------------------
# budgets, spec, evaluation contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CampaignBudget:
    max_evaluations: int | None = None
    max_high_fidelity_evaluations: int | None = None
    max_cost: float | None = None
    max_seconds: float | None = None
    target_feasibility: float | None = None
    no_improvement_rounds: int | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("max_evaluations", self.max_evaluations),
            ("max_high_fidelity_evaluations", self.max_high_fidelity_evaluations),
            ("no_improvement_rounds", self.no_improvement_rounds),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"INVALID_CAMPAIGN_BUDGET:{label}")
        for label, value in (("max_cost", self.max_cost), ("max_seconds", self.max_seconds)):
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(f"INVALID_CAMPAIGN_BUDGET:{label}")
        if self.target_feasibility is not None and not 0.0 <= self.target_feasibility <= 1.0:
            raise ValueError("INVALID_CAMPAIGN_BUDGET:target_feasibility")


@dataclass(frozen=True, slots=True)
class CampaignSpec:
    campaign_id: str
    base_revision: str
    space: Mapping[str, Any]
    generation: GenerationRequest
    objectives: tuple[StudyObjective, ...]
    constraints: tuple[StudyConstraint, ...] = ()
    fidelity_ladder: tuple[FidelityImplementation, ...] = (
        FidelityImplementation("analytical", 0, 0.0),
    )
    budget: CampaignBudget = CampaignBudget()
    quality: QualityPolicy = QualityPolicy()
    promote_fraction: float = 0.5
    min_promote: int = 1
    diversity: bool = True
    selection: str = "weighted"
    maturity: float = 0.5
    selector: Selector | None = None

    def __post_init__(self) -> None:
        if not self.campaign_id.strip() or not self.base_revision.strip():
            raise ValueError("CAMPAIGN_NEEDS_ID_AND_BASE_REVISION")
        if not self.objectives:
            raise ValueError("CAMPAIGN_NEEDS_OBJECTIVES")
        if self.selection not in {"weighted", "pareto"}:
            raise ValueError(f"UNKNOWN_SELECTION:{self.selection}")
        ranks = [rung.rank for rung in self.fidelity_ladder]
        if not self.fidelity_ladder or sorted(
            ranks
        ) != list(range(len(self.fidelity_ladder))):
            raise ValueError("FIDELITY_LADDER_MUST_FORM_RANK_LADDER_FROM_ZERO")
        if not 0.0 < self.promote_fraction <= 1.0:
            raise ValueError("PROMOTE_FRACTION_MUST_BE_IN_RANGE")
        if self.min_promote < 1:
            raise ValueError("MIN_PROMOTE_MUST_BE_POSITIVE")

    def ladder(self) -> tuple[FidelityImplementation, ...]:
        return tuple(sorted(self.fidelity_ladder, key=lambda rung: rung.rank))


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """What an evaluator returns for one candidate at one fidelity."""

    outputs: Mapping[str, float]
    flags: PhysicsFlags
    fidelity: str
    source: str = "analytical"
    cost: float = 0.0
    geometry_hash: str | None = None
    signals: Mapping[str, float] | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.fidelity.strip():
            raise ValueError("EVALUATION_NEEDS_FIDELITY")
        if not isfinite(self.cost) or self.cost < 0:
            raise ValueError("EVALUATION_COST_MUST_BE_NONNEGATIVE")


Evaluator = Callable[[Candidate, str], EvaluationResult]

#: Optional selection policy seam; a later Bayesian/surrogate/active-learning
#: policy can implement this without changing the campaign engine.
Selector = Callable[
    [Sequence[tuple[Candidate, "EvaluationRecord"]], Sequence[StudyObjective]],
    Sequence[tuple[Candidate, "EvaluationRecord"]],
]


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    candidate_hash: str
    fidelity: str
    state: str  # "valid" | "invalid"
    reasons: tuple[str, ...]
    outputs: tuple[tuple[str, float], ...]
    cost: float
    source: str
    geometry_hash: str | None
    signal_digest: str
    detail: str
    signals: tuple[tuple[str, float], ...] = ()

    @property
    def output_dict(self) -> dict[str, float]:
        return dict(self.outputs)

    @property
    def signal_dict(self) -> dict[str, float]:
        return dict(self.signals)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "fidelity": self.fidelity,
            "state": self.state,
            "reasons": list(self.reasons),
            "outputs": [[name, value] for name, value in self.outputs],
            "cost": self.cost,
            "source": self.source,
            "geometryHash": self.geometry_hash,
            "signalDigest": self.signal_digest,
            "detail": self.detail,
            "signals": [[name, value] for name, value in self.signals],
        }


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    candidate_hash: str
    from_fidelity: str
    to_fidelity: str
    advanced: bool
    reasons: tuple[str, ...]
    signal_digest: str
    rank: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "fromFidelity": self.from_fidelity,
            "toFidelity": self.to_fidelity,
            "advanced": self.advanced,
            "reasons": list(self.reasons),
            "signalDigest": self.signal_digest,
            "rank": self.rank,
        }


@dataclass(slots=True)
class CandidateRecord:
    candidate_hash: str
    status: str = "pending"
    reasons: list[str] = field(default_factory=list)
    fidelity: str | None = None
    outputs: dict[str, float] = field(default_factory=dict)
    feasible: bool | None = None
    score: float | None = None
    cost: float = 0.0
    evaluations: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "status": self.status,
            "reasons": list(self.reasons),
            "fidelity": self.fidelity,
            "outputs": dict(sorted(self.outputs.items())),
            "feasible": self.feasible,
            "score": self.score,
            "cost": self.cost,
            "evaluations": self.evaluations,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CandidateRecord:
        return cls(
            candidate_hash=str(payload["candidateHash"]),
            status=str(payload["status"]),
            reasons=[str(item) for item in payload.get("reasons", ())],
            fidelity=payload.get("fidelity"),
            outputs={str(key): float(value) for key, value in payload.get("outputs", {}).items()},
            feasible=payload.get("feasible"),
            score=None if payload.get("score") is None else float(payload["score"]),
            cost=float(payload.get("cost", 0.0)),
            evaluations=int(payload.get("evaluations", 0)),
        )


@dataclass(slots=True)
class CampaignRecord:
    campaign_id: str
    base_revision: str
    generator_config: Mapping[str, Any]
    objective_names: tuple[str, ...]
    constraint_names: tuple[str, ...]
    fidelity_names: tuple[str, ...]
    budget: CampaignBudget
    design_space: Mapping[str, Any] = field(default_factory=dict)
    objectives: tuple[StudyObjective, ...] = ()
    constraints: tuple[StudyConstraint, ...] = ()
    fidelity_ladder: tuple[FidelityImplementation, ...] = ()
    state: CampaignState = CampaignState.CREATED
    state_history: list[CampaignState] = field(default_factory=list)
    stop_reason: str | None = None
    candidates: dict[str, CandidateRecord] = field(default_factory=dict)
    evaluations: list[EvaluationRecord] = field(default_factory=list)
    promotions: list[PromotionDecision] = field(default_factory=list)
    pareto: tuple[str, ...] = ()
    best: str | None = None
    metrics: dict[str, int | float] = field(default_factory=dict)

    def transition(self, new_state: CampaignState) -> None:
        if new_state in _TERMINAL and self.state in _TERMINAL:
            return
        allowed = _LEGAL_TRANSITIONS.get(self.state, frozenset())
        if new_state != self.state and new_state not in allowed:
            raise ValueError(f"ILLEGAL_CAMPAIGN_TRANSITION:{self.state.value}->{new_state.value}")
        if not self.state_history:
            self.state_history.append(self.state)
        if self.state_history[-1] != new_state:
            self.state_history.append(new_state)
        self.state = new_state

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaignId": self.campaign_id,
            "baseRevision": self.base_revision,
            "generatorConfig": dict(self.generator_config),
            "objectiveNames": list(self.objective_names),
            "constraintNames": list(self.constraint_names),
            "fidelityNames": list(self.fidelity_names),
            "designSpace": dict(self.design_space),
            "objectives": [
                {
                    "name": objective.name,
                    "target": objective.target,
                    "weight": objective.weight,
                    "unit": objective.unit,
                }
                for objective in self.objectives
            ],
            "constraints": [
                {
                    "name": constraint.name,
                    "bound": constraint.bound,
                    "limit": constraint.limit,
                    "unit": constraint.unit,
                }
                for constraint in self.constraints
            ],
            "fidelityLadder": [
                {
                    "name": rung.name,
                    "rank": rung.rank,
                    "cost": rung.cost,
                    "capabilities": list(rung.capabilities),
                    "description": rung.description,
                }
                for rung in self.fidelity_ladder
            ],
            "budget": {
                "maxEvaluations": self.budget.max_evaluations,
                "maxHighFidelityEvaluations": self.budget.max_high_fidelity_evaluations,
                "maxCost": self.budget.max_cost,
                "maxSeconds": self.budget.max_seconds,
                "targetFeasibility": self.budget.target_feasibility,
                "noImprovementRounds": self.budget.no_improvement_rounds,
            },
            "state": self.state.value,
            "stateHistory": [item.value for item in self.state_history],
            "stopReason": self.stop_reason,
            "candidates": {key: value.as_dict() for key, value in sorted(self.candidates.items())},
            "evaluations": [item.as_dict() for item in self.evaluations],
            "promotions": [item.as_dict() for item in self.promotions],
            "pareto": list(self.pareto),
            "best": self.best,
            "metrics": dict(sorted(self.metrics.items())),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CampaignRecord:
        budget = payload.get("budget", {})
        record = cls(
            campaign_id=str(payload["campaignId"]),
            base_revision=str(payload["baseRevision"]),
            generator_config=dict(payload.get("generatorConfig", {})),
            objective_names=tuple(str(item) for item in payload.get("objectiveNames", ())),
            constraint_names=tuple(str(item) for item in payload.get("constraintNames", ())),
            fidelity_names=tuple(str(item) for item in payload.get("fidelityNames", ())),
            design_space=dict(payload.get("designSpace", {})),
            objectives=tuple(
                StudyObjective(
                    str(item["name"]),
                    str(item["target"]),
                    float(item.get("weight", 1.0)),
                    str(item.get("unit", "dimensionless")),
                )
                for item in payload.get("objectives", ())
            ),
            constraints=tuple(
                StudyConstraint(
                    str(item["name"]),
                    str(item["bound"]),
                    float(item["limit"]),
                    str(item.get("unit", "dimensionless")),
                )
                for item in payload.get("constraints", ())
            ),
            fidelity_ladder=tuple(
                FidelityImplementation(
                    str(item["name"]),
                    int(item["rank"]),
                    float(item.get("cost", 0.0)),
                    tuple(str(capability) for capability in item.get("capabilities", ())),
                    str(item.get("description", "")),
                )
                for item in payload.get("fidelityLadder", ())
            ),
            budget=CampaignBudget(
                max_evaluations=budget.get("maxEvaluations"),
                max_high_fidelity_evaluations=budget.get("maxHighFidelityEvaluations"),
                max_cost=budget.get("maxCost"),
                max_seconds=budget.get("maxSeconds"),
                target_feasibility=budget.get("targetFeasibility"),
                no_improvement_rounds=budget.get("noImprovementRounds"),
            ),
            state=CampaignState(str(payload.get("state", CampaignState.CREATED.value))),
            state_history=[
                CampaignState(str(item)) for item in payload.get("stateHistory", ())
            ],
            stop_reason=payload.get("stopReason"),
            candidates={
                str(key): CandidateRecord.from_dict(value)
                for key, value in payload.get("candidates", {}).items()
            },
            pareto=tuple(str(item) for item in payload.get("pareto", ())),
            best=payload.get("best"),
            metrics=dict(payload.get("metrics", {})),
        )
        record.evaluations = [
            EvaluationRecord(
                candidate_hash=str(item["candidateHash"]),
                fidelity=str(item["fidelity"]),
                state=str(item["state"]),
                reasons=tuple(str(reason) for reason in item.get("reasons", ())),
                outputs=tuple(
                    (str(name), float(value)) for name, value in item.get("outputs", ())
                ),
                cost=float(item.get("cost", 0.0)),
                source=str(item.get("source", "analytical")),
                geometry_hash=item.get("geometryHash"),
                signal_digest=str(item.get("signalDigest", "")),
                detail=str(item.get("detail", "")),
                signals=tuple(
                    (str(name), float(value)) for name, value in item.get("signals", ())
                ),
            )
            for item in payload.get("evaluations", ())
        ]
        record.promotions = [
            PromotionDecision(
                candidate_hash=str(item["candidateHash"]),
                from_fidelity=str(item["fromFidelity"]),
                to_fidelity=str(item["toFidelity"]),
                advanced=bool(item["advanced"]),
                reasons=tuple(str(reason) for reason in item.get("reasons", ())),
                signal_digest=str(item.get("signalDigest", "")),
                rank=int(item.get("rank", 0)),
            )
            for item in payload.get("promotions", ())
        ]
        return record


# ---------------------------------------------------------------------------
# result store (resume without re-evaluating content-identical candidates)
# ---------------------------------------------------------------------------


@runtime_checkable
class ResultStore(Protocol):
    def get(self, key: str) -> EvaluationRecord | None: ...

    def put(self, key: str, record: EvaluationRecord) -> None: ...


class InMemoryResultStore:
    """Default immutable, content-addressed evaluation store."""

    def __init__(self) -> None:
        self._entries: dict[str, EvaluationRecord] = {}

    def get(self, key: str) -> EvaluationRecord | None:
        return self._entries.get(key)

    def put(self, key: str, record: EvaluationRecord) -> None:
        existing = self._entries.get(key)
        if existing is not None and existing != record:
            raise ValueError(f"content-addressed evaluation {key} is immutable")
        self._entries[key] = record

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))


def result_key(candidate_hash: str, fidelity: str, evaluator_identity: str = "") -> str:
    """Stable key over candidate content, fidelity, and evaluator identity."""
    if not candidate_hash.strip() or not fidelity.strip():
        raise ValueError("RESULT_KEY_NEEDS_CANDIDATE_AND_FIDELITY")
    return content_digest(
        {"candidate": candidate_hash, "fidelity": fidelity, "evaluator": evaluator_identity}
    )


# ---------------------------------------------------------------------------
# selection primitives (generic, deterministic)
# ---------------------------------------------------------------------------


def scalarized(objectives: Sequence[StudyObjective], outputs: Mapping[str, float]) -> float:
    """Lower-is-better weighted scalar objective."""
    total = 0.0
    for objective in objectives:
        value = outputs[objective.name]
        total += objective.weight * (value if objective.target == "minimize" else -value)
    return total


def _satisfies(outputs: Mapping[str, float], constraints: Sequence[StudyConstraint]) -> bool:
    for constraint in constraints:
        value = outputs[constraint.name]
        if constraint.bound == "upper" and value > constraint.limit:
            return False
        if constraint.bound == "lower" and value < constraint.limit:
            return False
        if constraint.bound == "equality" and value != constraint.limit:
            return False
    return True


def select_feasible(
    records: Sequence[tuple[Candidate, EvaluationRecord]],
    constraints: Sequence[StudyConstraint],
) -> tuple[tuple[Candidate, EvaluationRecord], ...]:
    """Valid and constraint-feasible candidates only."""
    return tuple(
        (candidate, record)
        for candidate, record in records
        if record.state == "valid" and _satisfies(record.output_dict, constraints)
    )


def rank_weighted(
    records: Sequence[tuple[Candidate, EvaluationRecord]],
    objectives: Sequence[StudyObjective],
) -> tuple[tuple[Candidate, EvaluationRecord], ...]:
    """Deterministic weighted ranking; invalid records are excluded."""
    valid = [item for item in records if item[1].state == "valid"]
    return tuple(
        sorted(
            valid,
            key=lambda item: (
                scalarized(objectives, item[1].output_dict),
                item[0].candidate_hash,
            ),
        )
    )


def pareto_front(
    records: Sequence[tuple[Candidate, EvaluationRecord]],
    objectives: Sequence[StudyObjective],
) -> tuple[tuple[Candidate, EvaluationRecord], ...]:
    """Nondominated valid candidates, ordered deterministically."""
    valid = [item for item in records if item[1].state == "valid"]
    front: list[tuple[Candidate, EvaluationRecord]] = []
    for candidate in valid:
        outputs = candidate[1].output_dict
        dominated = False
        for other in valid:
            if other[0].candidate_hash == candidate[0].candidate_hash:
                continue
            other_outputs = other[1].output_dict
            better_or_equal = True
            strictly_better = False
            for objective in objectives:
                mine = outputs[objective.name]
                theirs = other_outputs[objective.name]
                if objective.target == "minimize":
                    if theirs > mine:
                        better_or_equal = False
                    if theirs < mine:
                        strictly_better = True
                else:
                    if theirs < mine:
                        better_or_equal = False
                    if theirs > mine:
                        strictly_better = True
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return tuple(sorted(front, key=lambda item: item[0].candidate_hash))


def top_k(
    records: Sequence[tuple[Candidate, EvaluationRecord]], k: int
) -> tuple[tuple[Candidate, EvaluationRecord], ...]:
    if k < 0:
        raise ValueError("TOP_K_MUST_BE_NONNEGATIVE")
    return tuple(records[:k])


def _features(candidate: Candidate) -> dict[str, float]:
    return dict(candidate.normalized)


def select_diverse(
    ranked: Sequence[tuple[Candidate, EvaluationRecord]],
    k: int,
) -> tuple[tuple[Candidate, EvaluationRecord], ...]:
    """Greedy max-min diversity over normalized design-variable space.

    Ranking quality seeds the set; subsequent picks maximize the minimum
    normalized Euclidean distance to the already-selected candidates, with
    deterministic hash tie-breaking.
    """
    if k <= 0 or not ranked:
        return ()
    if len(ranked) <= k:
        return tuple(ranked)
    selected = [ranked[0]]
    remaining = list(ranked[1:])
    while len(selected) < k and remaining:
        best_index = 0
        best_key: tuple[float, str] | None = None
        for index, item in enumerate(remaining):
            features = _features(item[0])
            distance = min(
                _distance(features, _features(chosen[0])) for chosen in selected
            )
            key = (-distance, item[0].candidate_hash)
            if best_key is None or key < best_key:
                best_key = key
                best_index = index
        selected.append(remaining.pop(best_index))
    return tuple(selected)


def _distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left) | set(right)
    total = 0.0
    for key in keys:
        delta = left.get(key, 0.0) - right.get(key, 0.0)
        total += delta * delta
    return sqrt(total)


# ---------------------------------------------------------------------------
# campaign execution
# ---------------------------------------------------------------------------


def _constraint_margin(
    outputs: Mapping[str, float], constraints: Sequence[StudyConstraint]
) -> float:
    if not constraints:
        return 1.0
    margins: list[float] = []
    for constraint in constraints:
        value = outputs.get(constraint.name)
        if value is None:
            margins.append(0.0)
            continue
        limit = constraint.limit
        scale = max(abs(limit), 1e-9)
        if constraint.bound == "upper":
            margins.append((limit - value) / scale)
        elif constraint.bound == "lower":
            margins.append((value - limit) / scale)
        else:
            margins.append(1.0 - abs(value - limit) / scale)
    return min(max(margin, -1.0) for margin in margins)


def _build_signals(
    spec: CampaignSpec,
    record: EvaluationRecord,
    rung: FidelityImplementation,
) -> FidelitySignals:
    measured = record.signal_dict
    return FidelitySignals(
        question=f"campaign:{spec.campaign_id}:{rung.name}",
        maturity=float(measured.get("maturity", spec.maturity)),
        constraint_margin=float(
            measured.get(
                "constraint_margin",
                _constraint_margin(record.output_dict, spec.constraints),
            )
        ),
        disagreement=float(measured.get("disagreement", 0.0)),
        sensitivity=float(measured.get("sensitivity", 0.0)),
        convergence_difficulty=float(measured.get("convergence_difficulty", 0.0)),
        mesh_dependence=float(measured.get("mesh_dependence", 0.0)),
        timestep_dependence=float(measured.get("timestep_dependence", 0.0)),
        resonance_proximity=float(measured.get("resonance_proximity", 1.0)),
        validity_ok={rung.name: record.state == "valid"},
        cost_budget=float(
            measured.get("cost_budget")
            if measured.get("cost_budget") is not None
            else (
                spec.budget.max_cost
                if spec.budget.max_cost is not None
                else sum(item.cost for item in spec.ladder()) + 1.0
            )
        ),
        required_capability=measured.get("required_capability"),  # type: ignore[arg-type]
    )


def _candidate_batch_inputs(candidate: Candidate) -> dict[str, float]:
    """Scalar batch inputs for a candidate, keyed by variable id."""
    values: dict[str, float] = {}
    for item in candidate.assignment:
        if (
            item.point_id is None
            and isinstance(item.value, (int, float))
            and not isinstance(item.value, bool)
        ):
            values[str(item.variable_id)] = float(item.value)
    return values


def _record_from_evaluation(
    candidate: Candidate,
    result: EvaluationResult,
    rung: FidelityImplementation,
    spec: CampaignSpec,
    *,
    extra_reasons: Sequence[str] = (),
) -> EvaluationRecord:
    verdict = assess_sample(result.flags, spec.quality)
    reasons: list[str] = list(extra_reasons) + list(verdict.reasons)
    if result.detail:
        reasons.append(result.detail)
    state = "valid" if verdict.state == "valid" else "invalid"
    if state == "invalid" and not reasons:
        reasons.append("evaluation reported invalid")
    signals = dict(result.signals or {})
    return EvaluationRecord(
        candidate_hash=candidate.candidate_hash,
        fidelity=rung.name,
        state=state,
        reasons=tuple(reasons),
        outputs=tuple(sorted((name, float(value)) for name, value in result.outputs.items())),
        cost=result.cost,
        source=result.source,
        geometry_hash=result.geometry_hash,
        signal_digest=content_digest(signals),
        detail=result.detail,
        signals=tuple(sorted((name, float(value)) for name, value in signals.items())),
    )


def _record_from_batch_row(
    candidate: Candidate,
    rung: FidelityImplementation,
    row: BatchRow,
    spec: CampaignSpec,
) -> EvaluationRecord:
    flags = row.flags
    if row.state != "valid":
        flags = PhysicsFlags(converged=False, closure_passed=False, validity_ok=False)
    result = EvaluationResult(
        outputs=row.output_dict,
        flags=flags,
        fidelity=rung.name,
        source=row.source,
        cost=row.cost,
        detail=row.detail,
        signals=row.signal_dict,
    )
    extra = () if row.state == "valid" else (row.reasons or ("batch marked row invalid",))
    return _record_from_evaluation(candidate, result, rung, spec, extra_reasons=extra)


def _evaluate_one(
    candidate: Candidate,
    rung: FidelityImplementation,
    spec: CampaignSpec,
    evaluator: Evaluator,
    store: ResultStore,
    evaluator_identity: str,
    counters: dict[str, int | float],
) -> EvaluationRecord:
    key = result_key(candidate.candidate_hash, rung.name, evaluator_identity)
    cached = store.get(key)
    if cached is not None:
        counters["cache_hits"] = int(counters["cache_hits"]) + 1
        return cached
    try:
        result = evaluator(candidate, rung.name)
    except Exception as exc:  # noqa: BLE001 - evaluation failures fail closed
        result = EvaluationResult(
            outputs={},
            flags=PhysicsFlags(converged=False, closure_passed=False, validity_ok=False),
            fidelity=rung.name,
            detail=f"EVALUATION_ERROR:{type(exc).__name__}:{exc}",
        )
    record = _record_from_evaluation(candidate, result, rung, spec)
    store.put(key, record)
    counters["evaluations"] = int(counters["evaluations"]) + 1
    counters["cost"] = float(counters["cost"]) + result.cost
    return record


def _accept_evaluation(
    record: CampaignRecord,
    candidate: Candidate,
    evaluation: EvaluationRecord,
    spec: CampaignSpec,
    evaluated: list[tuple[Candidate, EvaluationRecord]],
    metrics_by_hash: dict[str, EvaluationRecord],
) -> None:
    record.evaluations.append(evaluation)
    metrics_by_hash[candidate.candidate_hash] = evaluation
    _update_candidate_record(record, candidate, evaluation, spec)
    if evaluation.state == "valid":
        evaluated.append((candidate, evaluation))
    else:
        record.metrics["invalid"] = int(record.metrics["invalid"]) + 1


def _evaluate_rung_batched(
    record: CampaignRecord,
    active: Sequence[Candidate],
    rung: FidelityImplementation,
    spec: CampaignSpec,
    evaluator: Evaluator,
    batch_evaluator: BatchEvaluator,
    store: ResultStore,
    evaluator_identity: str,
    counters: dict[str, int | float],
    metrics_by_hash: dict[str, EvaluationRecord],
    cancel_check: Callable[[], bool] | None,
    batch_size: int,
    memory_budget_bytes: int | None,
) -> tuple[list[tuple[Candidate, EvaluationRecord]], str | None, bool, dict[str, float | int]]:
    """Chunk-batched evaluation of the cheap rung; only rows for this rung.

    Promoted candidates still flow through the normal one-at-a-time path on
    higher (native) rungs. A batch that violates the contract or raises falls
    back to the scalar evaluator for the affected chunk.
    """
    operations: list[tuple[bool, Candidate, EvaluationRecord | None]] = []
    requests: list[BatchRequest] = []
    request_candidates: list[Candidate] = []
    stop_reason: str | None = None
    cancelled = False
    committed = int(counters["evaluations"])
    planned = 0
    for candidate in active:
        if cancel_check is not None and cancel_check():
            cancelled = True
            break
        if (
            spec.budget.max_evaluations is not None
            and committed + planned >= spec.budget.max_evaluations
        ):
            stop_reason = "max-evaluations"
            break
        if (
            rung.rank > 0
            and spec.budget.max_high_fidelity_evaluations is not None
            and int(counters["high_fidelity_evaluations"])
            >= spec.budget.max_high_fidelity_evaluations
        ):
            stop_reason = "max-high-fidelity-evaluations"
            break
        if (
            spec.budget.max_cost is not None
            and float(counters["cost"]) >= spec.budget.max_cost
        ):
            stop_reason = "max-cost"
            break
        candidate_record = record.candidates[candidate.candidate_hash]
        if candidate_record.status == "preflight-invalid":
            continue
        key = result_key(candidate.candidate_hash, rung.name, evaluator_identity)
        cached = store.get(key)
        if cached is not None:
            counters["cache_hits"] = int(counters["cache_hits"]) + 1
            operations.append((True, candidate, cached))
            continue
        requests.append(
            BatchRequest(
                candidate_hash=candidate.candidate_hash,
                operating_point="nominal",
                inputs=tuple(sorted(_candidate_batch_inputs(candidate).items())),
                index=candidate.index,
            )
        )
        request_candidates.append(candidate)
        operations.append((False, candidate, None))
        planned += 1
    effective = plan_batch_size(batch_size, memory_budget_bytes=memory_budget_bytes)
    rows_by_key: dict[tuple[str, str], BatchRow] = {}
    stats: dict[str, float | int] = {
        "effective_batch_size": effective,
        "batches": 0,
        "fallback_batches": 0,
        "peak_batch_rows": 0,
        "setup_seconds": 0.0,
        "evaluate_seconds": 0.0,
    }
    started = perf_counter()
    for start in range(0, len(requests), effective):
        chunk = requests[start : start + effective]
        chunk_candidates = request_candidates[start : start + effective]
        stats["batches"] = int(stats["batches"]) + 1
        stats["peak_batch_rows"] = max(int(stats["peak_batch_rows"]), len(chunk))
        expected = {request.key for request in chunk}
        try:
            produced = tuple(batch_evaluator.evaluate_batch(chunk))
        except Exception:  # noqa: BLE001 - unusable batch falls back, fail-safe
            produced = ()
        if len(produced) != len(chunk) or {row.key for row in produced} != expected:
            stats["fallback_batches"] = int(stats["fallback_batches"]) + 1
            for candidate in chunk_candidates:
                rows_by_key.pop((candidate.candidate_hash, "nominal"), None)
            continue
        for row in produced:
            rows_by_key[row.key] = row
    stats["evaluate_seconds"] = perf_counter() - started
    evaluated: list[tuple[Candidate, EvaluationRecord]] = []
    for cached_flag, candidate, cached in operations:
        if cached_flag:
            evaluation = cached
        else:
            row = rows_by_key.get((candidate.candidate_hash, "nominal"))
            if row is None:
                evaluation = _evaluate_one(
                    candidate, rung, spec, evaluator, store, evaluator_identity, counters
                )
            else:
                evaluation = _record_from_batch_row(candidate, rung, row, spec)
                store.put(
                    result_key(candidate.candidate_hash, rung.name, evaluator_identity),
                    evaluation,
                )
                counters["evaluations"] = int(counters["evaluations"]) + 1
                counters["cost"] = float(counters["cost"]) + row.cost
        assert evaluation is not None
        if rung.rank > 0:
            counters["high_fidelity_evaluations"] = (
                int(counters["high_fidelity_evaluations"]) + 1
            )
        _accept_evaluation(record, candidate, evaluation, spec, evaluated, metrics_by_hash)
    return evaluated, stop_reason, cancelled, stats


def run_campaign(
    spec: CampaignSpec,
    evaluator: Evaluator,
    *,
    store: ResultStore | None = None,
    evaluator_identity: str = "",
    cancel_check: Callable[[], bool] | None = None,
    batch_evaluator: BatchEvaluator | None = None,
    batch_size: int = 64,
    memory_budget_bytes: int | None = None,
) -> CampaignRecord:
    """Run a bounded, resumable campaign and return its evidence record.

    When ``batch_evaluator`` is declared, the *cheap* rung is evaluated in
    memory-bounded chunks through it; promoted candidates then stream through
    the ordinary one-at-a-time path on the higher (native) rungs. Batching is
    disabled for a rung when a cost budget is set because per-candidate cost is
    only known after evaluation.
    """
    if batch_size <= 0:
        raise ValueError("BATCH_SIZE_MUST_BE_POSITIVE")
    rungs = spec.ladder()
    active_store = store if store is not None else InMemoryResultStore()
    record = CampaignRecord(
        campaign_id=spec.campaign_id,
        base_revision=spec.base_revision,
        generator_config=dict(spec.generation.config()),
        objective_names=tuple(objective.name for objective in spec.objectives),
        constraint_names=tuple(constraint.name for constraint in spec.constraints),
        fidelity_names=tuple(rung.name for rung in rungs),
        budget=spec.budget,
        design_space=dict(spec.space),
        objectives=spec.objectives,
        constraints=spec.constraints,
        fidelity_ladder=rungs,
        metrics={
            "generated": 0, "duplicates": 0, "preflight_invalid": 0, "evaluations": 0,
            "cache_hits": 0, "high_fidelity_evaluations": 0, "cost": 0.0,
            "promoted": 0, "retained": 0, "invalid": 0,
        },
    )
    record.transition(CampaignState.GENERATING)
    try:
        generator = CandidateGenerator(spec.space, spec.generation)
        candidates = list(generator)
        record.metrics["generated"] = len(candidates)
        record.metrics["duplicates"] = generator.stats.duplicates
        for candidate in candidates:
            status = "pending" if candidate.valid else "preflight-invalid"
            if status == "preflight-invalid":
                record.metrics["preflight_invalid"] = (
                    int(record.metrics["preflight_invalid"]) + 1
                )
                record.metrics["invalid"] = int(record.metrics["invalid"]) + 1
            record.candidates[candidate.candidate_hash] = CandidateRecord(
                candidate_hash=candidate.candidate_hash,
                status=status,
                reasons=list(candidate.preflight_reasons),
            )
        record.transition(CampaignState.EVALUATING)
        counters = record.metrics
        # Preflight-invalid candidates stay in the record but are never evaluated.
        active = list(candidates)
        current_rank = 0
        metrics_by_hash: dict[str, EvaluationRecord] = {}
        best_score: float | None = None
        no_improve_rounds = 0
        while active and current_rank < len(rungs):
            rung = rungs[current_rank]
            evaluated: list[tuple[Candidate, EvaluationRecord]] = []
            stop_reason: str | None = None
            use_batch = (
                batch_evaluator is not None
                and rung.rank == 0
                and spec.budget.max_cost is None
            )
            if use_batch:
                assert batch_evaluator is not None
                evaluated, stop_reason, cancelled, batch_stats = _evaluate_rung_batched(
                    record,
                    active,
                    rung,
                    spec,
                    evaluator,
                    batch_evaluator,
                    active_store,
                    evaluator_identity,
                    counters,
                    metrics_by_hash,
                    cancel_check,
                    batch_size,
                    memory_budget_bytes,
                )
                for key, value in batch_stats.items():
                    record.metrics[key] = value
                if cancelled:
                    record.transition(CampaignState.CANCELLED)
                    record.stop_reason = "cancelled"
                    return _finalize(record, spec, metrics_by_hash)
            else:
                for candidate in active:
                    if cancel_check is not None and cancel_check():
                        record.transition(CampaignState.CANCELLED)
                        record.stop_reason = "cancelled"
                        return _finalize(record, spec, metrics_by_hash)
                    if (
                        spec.budget.max_evaluations is not None
                        and int(counters["evaluations"]) >= spec.budget.max_evaluations
                    ):
                        stop_reason = "max-evaluations"
                        break
                    if (
                        rung.rank > 0
                        and spec.budget.max_high_fidelity_evaluations is not None
                        and int(counters["high_fidelity_evaluations"])
                        >= spec.budget.max_high_fidelity_evaluations
                    ):
                        stop_reason = "max-high-fidelity-evaluations"
                        break
                    if (
                        spec.budget.max_cost is not None
                        and float(counters["cost"]) >= spec.budget.max_cost
                    ):
                        stop_reason = "max-cost"
                        break
                    candidate_record = record.candidates[candidate.candidate_hash]
                    if candidate_record.status == "preflight-invalid":
                        continue
                    evaluation = _evaluate_one(
                        candidate, rung, spec, evaluator, active_store, evaluator_identity,
                        counters,
                    )
                    if rung.rank > 0:
                        counters["high_fidelity_evaluations"] = (
                            int(counters["high_fidelity_evaluations"]) + 1
                        )
                    _accept_evaluation(
                        record, candidate, evaluation, spec, evaluated, metrics_by_hash
                    )
            if stop_reason is not None:
                record.stop_reason = stop_reason
                break
            record.transition(CampaignState.SELECTING)
            if not evaluated:
                record.stop_reason = "no-valid-candidates"
                break
            selected = _select(evaluated, spec)
            if spec.budget.target_feasibility is not None:
                feasible_here = select_feasible(evaluated, spec.constraints)
                ratio = len(feasible_here) / len(evaluated)
                if ratio >= spec.budget.target_feasibility:
                    record.stop_reason = "target-feasibility"
                    break
            if selected:
                score = scalarized(spec.objectives, selected[0][1].output_dict)
                if best_score is None or score < best_score - 1e-12:
                    best_score = score
                    no_improve_rounds = 0
                else:
                    no_improve_rounds += 1
            if (
                spec.budget.no_improvement_rounds is not None
                and no_improve_rounds >= spec.budget.no_improvement_rounds
            ):
                record.stop_reason = "no-improvement"
                break
            surviving = _survive_count(len(selected), spec)
            if surviving <= 0:
                break
            if spec.diversity:
                survivors = select_diverse(selected, surviving)
            else:
                survivors = top_k(selected, surviving)
            if current_rank == len(rungs) - 1:
                for candidate, _ in selected:
                    _mark_status(record, candidate.candidate_hash, "retained")
                break
            record.transition(CampaignState.PROMOTING)
            next_rung = rungs[current_rank + 1]
            advanced: list[Candidate] = []
            for candidate, evaluation in survivors:
                signals = _build_signals(spec, evaluation, rung)
                planned = plan_fidelity(rung.name, rungs, signals)
                advanced_flag = planned.escalate
                if advanced_flag:
                    target = next_rung.name
                    advanced.append(candidate)
                    counters["promoted"] = int(counters["promoted"]) + 1
                    _mark_status(record, candidate.candidate_hash, "promoted")
                else:
                    target = rung.name
                    counters["retained"] = int(counters["retained"]) + 1
                    _mark_status(record, candidate.candidate_hash, "retained")
                record.promotions.append(
                    PromotionDecision(
                        candidate_hash=candidate.candidate_hash,
                        from_fidelity=rung.name,
                        to_fidelity=target,
                        advanced=advanced_flag,
                        reasons=tuple(planned.reasons),
                        signal_digest=planned.input_hash,
                        rank=candidate.index,
                    )
                )
            if not advanced:
                record.stop_reason = "promotion-halted"
                break
            active = advanced
            current_rank += 1
            record.transition(CampaignState.EVALUATING)
        return _finalize(record, spec, metrics_by_hash)
    except Exception:
        record.transition(CampaignState.FAILED)
        record.stop_reason = "failed"
        raise


# ---------------------------------------------------------------------------
# campaign helpers
# ---------------------------------------------------------------------------


def _survive_count(available: int, spec: CampaignSpec) -> int:
    if available <= 0:
        return 0
    keep = max(spec.min_promote, ceil(available * spec.promote_fraction))
    return min(available, keep)


def _select(
    evaluated: Sequence[tuple[Candidate, EvaluationRecord]], spec: CampaignSpec
) -> tuple[tuple[Candidate, EvaluationRecord], ...]:
    if spec.selector is not None:
        return tuple(spec.selector(list(evaluated), spec.objectives))
    if spec.selection == "pareto":
        return pareto_front(evaluated, spec.objectives)
    feasible = select_feasible(evaluated, spec.constraints)
    basis = feasible if feasible else evaluated
    return rank_weighted(basis, spec.objectives)


def _mark_status(record: CampaignRecord, candidate_hash: str, status: str) -> None:
    entry = record.candidates.get(candidate_hash)
    if entry is not None:
        entry.status = status


def _update_candidate_record(
    record: CampaignRecord,
    candidate: Candidate,
    evaluation: EvaluationRecord,
    spec: CampaignSpec,
) -> None:
    entry = record.candidates[candidate.candidate_hash]
    entry.fidelity = evaluation.fidelity
    entry.outputs = evaluation.output_dict
    entry.cost = evaluation.cost
    entry.evaluations += 1
    entry.feasible = evaluation.state == "valid" and _satisfies(
        evaluation.output_dict, spec.constraints
    )
    if evaluation.state == "valid":
        entry.status = "feasible" if entry.feasible else "infeasible"
        entry.score = scalarized(spec.objectives, evaluation.output_dict)
        entry.reasons = list(evaluation.reasons)
    else:
        entry.status = "invalid"
        entry.reasons = list(evaluation.reasons)


def _finalize(
    record: CampaignRecord,
    spec: CampaignSpec,
    latest: Mapping[str, EvaluationRecord],
) -> CampaignRecord:
    pairs = [
        (candidate_hash, evaluation)
        for candidate_hash, evaluation in latest.items()
        if evaluation.state == "valid"
    ]
    if pairs:
        feasible = [
            (candidate_hash, evaluation)
            for candidate_hash, evaluation in pairs
            if _satisfies(evaluation.output_dict, spec.constraints)
        ]
        basis = feasible if feasible else pairs
        pareto = _pareto_hashes(basis, spec.objectives)
        record.pareto = tuple(sorted(pareto))
        ranked = sorted(
            basis,
            key=lambda item: (
                scalarized(spec.objectives, item[1].output_dict),
                item[0],
            ),
        )
        record.best = ranked[0][0]
    else:
        record.pareto = ()
        record.best = None
    if record.state not in _TERMINAL:
        record.transition(CampaignState.COMPLETED)
    if record.stop_reason is None:
        record.stop_reason = "completed"
    return record


def _pareto_hashes(
    pairs: Sequence[tuple[str, EvaluationRecord]],
    objectives: Sequence[StudyObjective],
) -> set[str]:
    front: set[str] = set()
    for candidate_hash, evaluation in pairs:
        outputs = evaluation.output_dict
        dominated = False
        for other_hash, other in pairs:
            if other_hash == candidate_hash:
                continue
            other_outputs = other.output_dict
            better_or_equal = True
            strictly_better = False
            for objective in objectives:
                mine = outputs[objective.name]
                theirs = other_outputs[objective.name]
                if objective.target == "minimize":
                    if theirs > mine:
                        better_or_equal = False
                    if theirs < mine:
                        strictly_better = True
                else:
                    if theirs < mine:
                        better_or_equal = False
                    if theirs > mine:
                        strictly_better = True
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.add(candidate_hash)
    return front
