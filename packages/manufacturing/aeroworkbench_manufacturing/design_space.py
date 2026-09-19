"""Bind envelopes into the canonical design-space constraint system.

Unconditional algebraic limits compile to the existing ``relation`` constraint
kind; conditional limits compile to the existing ``requires`` constraint kind
with a numeric comparison predicate. Both are enforced by the existing
``preflight_design_state`` during candidate generation, so an unbuildable
candidate is flagged before any CAD or solver work. Limits that need measured
geometry/physics stay in the gate and are evaluated at their declared stage.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from aeroworkbench_optimization.design_space import validate_design_space
from aeroworkbench_optimization.generation import Candidate

from .envelopes import (
    ConstraintClass,
    EnvelopeError,
    EnvelopeSet,
    EvaluationStage,
    HardwareLimitEnvelope,
    LimitRelation,
    ManufacturingProcessEnvelope,
    ScalarLimit,
)
from .gate import EnvelopeReport, ManufacturabilityGate, Measurement

__all__ = [
    "envelope_design_constraints",
    "envelope_summary",
    "evaluate_candidate",
    "merge_envelope_constraints",
    "select_admissible",
]

_NUMERIC_KINDS = frozenset({"continuous", "integer", "discrete"})

_PREDICATE_OP = {
    LimitRelation.LESS_OR_EQUAL: "lessOrEqual",
    LimitRelation.GREATER_OR_EQUAL: "greaterOrEqual",
}


def _variable_index(space: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(variable["id"]): dict(variable) for variable in space.get("variables", ())}


def _combine_when(
    owner_when: Mapping[str, Any] | None, limit_when: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    if owner_when is None:
        return None if limit_when is None else dict(limit_when)
    if limit_when is None:
        return dict(owner_when)
    return {"op": "all", "clauses": [dict(owner_when), dict(limit_when)]}


def _unconditional_constraint(limit: ScalarLimit) -> dict[str, Any]:
    return {
        "id": limit.id,
        "kind": "relation",
        "expression": {"op": "variable", "variable": limit.value_name},
        "relation": limit.relation.value,
        "limit": limit.limit_si,
    }


def _conditional_constraint(
    limit: ScalarLimit, applies_when: dict[str, Any]
) -> dict[str, Any] | None:
    op = _PREDICATE_OP.get(limit.relation)
    if op is None:
        return None
    return {
        "id": limit.id,
        "kind": "requires",
        "when": applies_when,
        "require": {
            "op": op,
            "variable": limit.value_name,
            "valueSI": limit.limit_si,
        },
    }


def envelope_design_constraints(
    space: dict[str, Any], envelopes: EnvelopeSet
) -> tuple[dict[str, Any], ...]:
    """Compile the ``pre-cad-algebraic`` hard limits into design-space constraints."""

    index = _variable_index(space)
    compiled: list[dict[str, Any]] = []
    seen: set[str] = set()
    all_envelopes: tuple[
        ManufacturingProcessEnvelope | HardwareLimitEnvelope, ...
    ] = (*envelopes.manufacturing, *envelopes.hardware)
    for envelope in all_envelopes:
        owner_when = envelope.applies_when
        for limit in envelope.limits:
            if limit.constraint_class is not ConstraintClass.HARD:
                continue
            if limit.stage is not EvaluationStage.PRE_CAD_ALGEBRAIC:
                continue
            variable = index.get(limit.value_name)
            if variable is None:
                continue
            if limit.id in seen:
                raise EnvelopeError(f"DUPLICATE_COMPILED_CONSTRAINT:{limit.id}")
            effective_when = _combine_when(owner_when, limit.applies_when)
            if effective_when is None:
                compiled.append(_unconditional_constraint(limit))
            else:
                if variable["kind"] not in _NUMERIC_KINDS:
                    continue
                conditional = _conditional_constraint(limit, effective_when)
                if conditional is None:
                    continue
                compiled.append(conditional)
            seen.add(limit.id)
    return tuple(compiled)


def merge_envelope_constraints(
    space: dict[str, Any], envelopes: EnvelopeSet
) -> dict[str, Any]:
    """Return a copy of ``space`` with compiled envelope constraints appended."""

    merged: dict[str, Any] = copy.deepcopy(space)
    existing = {str(constraint["id"]) for constraint in merged.get("constraints", ())}
    compiled = envelope_design_constraints(space, envelopes)
    for constraint in compiled:
        if str(constraint["id"]) in existing:
            raise EnvelopeError(f"CONSTRAINT_ID_COLLISION:{constraint['id']}")
    merged.setdefault("constraints", [])
    merged["constraints"].extend(compiled)
    merged["manufacturingEnvelopes"] = {
        "schemaVersion": envelopes.schema_version,
        "envelopeSetHash": envelopes.content_hash,
        "compiledConstraintIds": [str(constraint["id"]) for constraint in compiled],
    }
    validate_design_space(merged)
    return merged


def evaluate_candidate(
    gate: ManufacturabilityGate,
    candidate: Candidate,
    *,
    measurements: Iterable[Measurement] | dict[str, Measurement] | None = None,
    soft_metrics: dict[str, float] | None = None,
) -> EnvelopeReport:
    """Screen one candidate's active design view; preflight-invalid fails closed."""

    if candidate.flat is None:
        flat: dict[str, Any] = {
            "spaceId": candidate.space_id,
            "order": [],
            "entries": [],
            "inactive": [],
        }
        report = gate.evaluate(flat, soft_metrics=soft_metrics)
        return report
    return gate.evaluate(candidate.flat, measurements=measurements, soft_metrics=soft_metrics)


def select_admissible(
    gate: ManufacturabilityGate,
    candidates: Iterable[Candidate],
    *,
    measurements_for: Callable[[Candidate], Iterable[Measurement] | None] | None = None,
) -> tuple[Candidate, ...]:
    """Yield only candidates whose envelope report is admissible."""

    admissible: list[Candidate] = []
    for candidate in candidates:
        if not candidate.valid:
            continue
        measurements = None if measurements_for is None else measurements_for(candidate)
        report = evaluate_candidate(gate, candidate, measurements=measurements)
        if report.admissible:
            admissible.append(candidate)
    return tuple(admissible)


def envelope_summary(envelopes: EnvelopeSet) -> str:
    """Deterministic JSON summary used in provenance/diagnostics."""

    return json.dumps(envelopes.as_dict(), sort_keys=True, separators=(",", ":"))
