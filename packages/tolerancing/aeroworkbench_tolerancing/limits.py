"""Bridge from tolerancing results to declarative manufacturing/hardware limits.

Tolerance stack-ups produce scalar characteristics; the manufacturing package
already owns the declarative limit envelopes. This module indexes those
envelopes by characteristic and evaluates a value against every applicable
limit, so a tolerance-infeasible design is rejected against the same canonical
limits used elsewhere in the platform.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_manufacturing.envelopes import (
    ConstraintClass,
    EnvelopeSet,
    LimitRelation,
    ScalarLimit,
)

from .errors import TolerancingError

__all__ = [
    "LimitEvaluation",
    "LimitViolation",
    "evaluate_limits",
    "limits_for",
]


@dataclass(frozen=True, slots=True)
class LimitViolation:
    """One unresolved or exceeded declarative limit."""

    limit_id: str
    value_name: str
    relation: str
    constraint_class: str
    measured_value_si: float
    limit_si: float
    unit: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "limitId": self.limit_id,
            "valueName": self.value_name,
            "relation": self.relation,
            "constraintClass": self.constraint_class,
            "measuredValueSI": self.measured_value_si,
            "limitSI": self.limit_si,
            "unit": self.unit,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class LimitEvaluation:
    """Aggregate outcome of checking a value against declarative limits."""

    value_name: str
    measured_value_si: float
    satisfied: bool
    violations: tuple[LimitViolation, ...]
    active_limit_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valueName": self.value_name,
            "measuredValueSI": self.measured_value_si,
            "satisfied": self.satisfied,
            "violations": [item.as_dict() for item in self.violations],
            "activeLimitIds": list(self.active_limit_ids),
        }


def limits_for(envelopes: EnvelopeSet, value_name: str) -> tuple[ScalarLimit, ...]:
    """Every declared limit targeting ``value_name`` from process/hardware envelopes."""

    found: list[ScalarLimit] = []
    for process_envelope in envelopes.manufacturing:
        for limit in process_envelope.limits:
            if limit.value_name == value_name:
                found.append(limit)
    for hardware_envelope in envelopes.hardware:
        for limit in hardware_envelope.limits:
            if limit.value_name == value_name:
                found.append(limit)
    return tuple(
        sorted(found, key=lambda limit: (limit.stage.value, limit.id))
    )


def _compare(relation: LimitRelation, measured_si: float, limit_si: float) -> bool:
    if relation is LimitRelation.LESS_OR_EQUAL:
        return measured_si <= limit_si
    if relation is LimitRelation.GREATER_OR_EQUAL:
        return measured_si >= limit_si
    return abs(measured_si - limit_si) <= 1e-9 * max(abs(limit_si), 1.0)


def evaluate_limits(
    value_name: str,
    value_si: float,
    limits: Sequence[ScalarLimit],
) -> LimitEvaluation:
    """Evaluate one measured characteristic against a set of declarative limits."""

    if not math.isfinite(value_si):
        raise TolerancingError(f"NONFINITE_MEASURED_VALUE:{value_name}")
    violations: list[LimitViolation] = []
    active: list[str] = []
    for limit in limits:
        active.append(limit.id)
        if _compare(limit.relation, value_si, limit.limit_si):
            continue
        violations.append(
            LimitViolation(
                limit_id=limit.id,
                value_name=limit.value_name,
                relation=limit.relation.value,
                constraint_class=limit.constraint_class.value,
                measured_value_si=value_si,
                limit_si=limit.limit_si,
                unit=limit.unit,
                reason="LIMIT_EXCEEDED",
            )
        )
    hard = [
        item for item in violations if item.constraint_class == ConstraintClass.HARD.value
    ]
    return LimitEvaluation(
        value_name=value_name,
        measured_value_si=value_si,
        satisfied=not hard,
        violations=tuple(violations),
        active_limit_ids=tuple(active),
    )
