"""Fail-closed manufacturability and operating-limit screening gate.

The gate evaluates declarative envelopes against a flattened design state and a
set of measurements from later stages (CAD geometry, physics screening, native
solver receipts). A hard limit that cannot be evaluated fails closed: the
candidate is rejected with a typed reason instead of being silently accepted.
Soft metrics may rank admissible candidates and never rescue a hard failure.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

from .envelopes import (
    STAGE_ORDER,
    ConstraintClass,
    EnvelopeError,
    EnvelopeSet,
    EvaluationStage,
    LimitRelation,
    ScalarLimit,
)
from .predicates import evaluate_predicate, flatten_index
from .scoring import manufacturability_score
from .units import to_si

__all__ = [
    "ConstraintViolation",
    "EnvelopeReport",
    "Measurement",
    "MeasurementError",
    "ManufacturabilityGate",
    "evaluate_envelopes",
]


class MeasurementError(EnvelopeError):
    """Raised when a measurement set is malformed (e.g. duplicate names)."""


@dataclass(frozen=True, slots=True)
class Measurement:
    """A value observed at a later stage, with its own provenance."""

    name: str
    value: float
    unit: str = "1"
    source: str = "analytical"
    fidelity: str = "analytical"
    software: str | None = None
    software_version: str | None = None
    run_id: str | None = None
    inputs_hash: str = ""
    validity: str = "valid"
    trusted: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MeasurementError("MEASUREMENT_NAME_REQUIRED")
        if not isfinite(self.value):
            raise MeasurementError(f"NONFINITE_MEASUREMENT:{self.name}")

    @property
    def value_si(self) -> float:
        return to_si(self.value, self.unit)

    @property
    def is_native_receipt(self) -> bool:
        return (
            self.source == ResultSource.NATIVE_SOLVER.value
            and self.trusted
            and bool(self.software)
            and bool(self.software_version)
            and bool(self.run_id)
            and bool(self.inputs_hash)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "valueSI": self.value_si,
            "unit": self.unit,
            "source": self.source,
            "fidelity": self.fidelity,
            "software": self.software,
            "softwareVersion": self.software_version,
            "runId": self.run_id,
            "inputsHash": self.inputs_hash,
            "validity": self.validity,
            "trusted": self.trusted,
        }


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    """A typed, machine-readable record of one rejected or unmet limit."""

    constraint_id: str
    value_name: str
    relation: str
    stage: str
    constraint_class: str
    measured_value_si: float | None
    limit_si: float
    unit: str
    declared_limit: float
    envelope_id: str
    envelope_kind: str
    envelope_revision: int
    envelope_hash: str
    source: Mapping[str, Any]
    recommended_variables: tuple[str, ...]
    measured_available: bool
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "constraintId": self.constraint_id,
            "valueName": self.value_name,
            "relation": self.relation,
            "stage": self.stage,
            "constraintClass": self.constraint_class,
            "measuredValueSI": self.measured_value_si,
            "limitSI": self.limit_si,
            "unit": self.unit,
            "declaredLimit": self.declared_limit,
            "envelopeId": self.envelope_id,
            "envelopeKind": self.envelope_kind,
            "envelopeRevision": self.envelope_revision,
            "envelopeHash": self.envelope_hash,
            "source": dict(self.source),
            "recommendedVariables": list(self.recommended_variables),
            "measuredAvailable": self.measured_available,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class EnvelopeReport:
    """The screening outcome for one candidate."""

    status: str  # "accepted" | "rejected"
    hard_violations: tuple[ConstraintViolation, ...]
    soft_violations: tuple[ConstraintViolation, ...]
    unresolved: tuple[ConstraintViolation, ...]
    active_limit_ids: tuple[str, ...]
    cleared_stages: tuple[str, ...]
    stage_reached: str
    score: float | None
    soft_metrics: Mapping[str, float]
    provenance: Mapping[str, Any]

    @property
    def admissible(self) -> bool:
        return self.status == "accepted"

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(
            f"{violation.constraint_id}:{violation.reason}"
            for violation in (*self.hard_violations, *self.unresolved)
        )

    def permits(self, stage: EvaluationStage | str) -> bool:
        """True only when no hard failure was recorded at or before ``stage``.

        A cheap hard rejection therefore blocks all later, more expensive work.
        """

        target = stage.value if isinstance(stage, EvaluationStage) else str(stage)
        order = [item.value for item in STAGE_ORDER]
        if target not in order:
            raise EnvelopeError(f"UNKNOWN_EVALUATION_STAGE:{target}")
        blocking = set(order[: order.index(target) + 1])
        return not any(
            violation.stage in blocking
            for violation in (*self.hard_violations, *self.unresolved)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "admissible": self.admissible,
            "hardViolations": [item.as_dict() for item in self.hard_violations],
            "softViolations": [item.as_dict() for item in self.soft_violations],
            "unresolved": [item.as_dict() for item in self.unresolved],
            "activeLimitIds": list(self.active_limit_ids),
            "clearedStages": list(self.cleared_stages),
            "stageReached": self.stage_reached,
            "score": self.score,
            "softMetrics": dict(self.soft_metrics),
            "provenance": dict(self.provenance),
        }


def _measurement_index(
    measurements: Iterable[Measurement] | Mapping[str, Measurement] | None,
) -> dict[str, Measurement]:
    index: dict[str, Measurement] = {}
    if measurements is None:
        return index
    items = measurements.values() if isinstance(measurements, Mapping) else measurements
    for measurement in items:
        if measurement.name in index:
            raise MeasurementError(f"DUPLICATE_MEASUREMENT:{measurement.name}")
        index[measurement.name] = measurement
    return index


def _owner_active(
    applies_when: Mapping[str, Any] | None,
    index: Mapping[str, Mapping[str, Any]],
) -> bool:
    if applies_when is None:
        return True
    return evaluate_predicate(applies_when, index)


def _limit_active(
    limit: ScalarLimit,
    index: Mapping[str, Mapping[str, Any]],
) -> bool:
    if limit.applies_when is None:
        return True
    return evaluate_predicate(limit.applies_when, index)


def _compare(relation: LimitRelation, measured_si: float, limit_si: float) -> bool:
    """True when the relation is satisfied."""

    if relation is LimitRelation.LESS_OR_EQUAL:
        return measured_si <= limit_si
    if relation is LimitRelation.GREATER_OR_EQUAL:
        return measured_si >= limit_si
    return abs(measured_si - limit_si) <= 1e-9 * max(abs(limit_si), 1.0)


def _design_value_si(
    name: str, index: Mapping[str, Mapping[str, Any]]
) -> tuple[float | None, str]:
    entry = index.get(name)
    if entry is None:
        return None, "unavailable"
    value = entry.get("valueSI")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), "design-state"
    return None, "unavailable"


@dataclass(frozen=True, slots=True)
class _BoundLimit:
    envelope_id: str
    envelope_kind: str
    envelope_revision: int
    envelope_hash: str
    applies_when: Mapping[str, Any] | None
    limit: ScalarLimit


def _bound_limits(envelopes: EnvelopeSet) -> tuple[_BoundLimit, ...]:
    bound: list[_BoundLimit] = []
    for process_envelope in envelopes.manufacturing:
        for limit in process_envelope.limits:
            bound.append(
                _BoundLimit(
                    envelope_id=process_envelope.id,
                    envelope_kind="manufacturing",
                    envelope_revision=process_envelope.revision,
                    envelope_hash=process_envelope.content_hash,
                    applies_when=process_envelope.applies_when,
                    limit=limit,
                )
            )
    for hardware_envelope in envelopes.hardware:
        for limit in hardware_envelope.limits:
            bound.append(
                _BoundLimit(
                    envelope_id=hardware_envelope.id,
                    envelope_kind="hardware",
                    envelope_revision=hardware_envelope.revision,
                    envelope_hash=hardware_envelope.content_hash,
                    applies_when=hardware_envelope.applies_when,
                    limit=limit,
                )
            )
    return tuple(
        sorted(
            bound,
            key=lambda item: (
                item.envelope_kind,
                item.envelope_id,
                item.limit.stage.value,
                item.limit.id,
            ),
        )
    )


class ManufacturabilityGate:
    """Screen candidates against process and hardware limit envelopes."""

    def __init__(
        self,
        envelopes: EnvelopeSet,
        *,
        soft_weights: Mapping[str, float] | None = None,
    ) -> None:
        self.envelopes = envelopes
        self.soft_weights = soft_weights
        self._bound = _bound_limits(envelopes)
        self.envelope_set_hash = envelopes.content_hash

    def evaluate(
        self,
        flat: Mapping[str, Any],
        *,
        measurements: Iterable[Measurement] | Mapping[str, Measurement] | None = None,
        soft_metrics: Mapping[str, float] | None = None,
    ) -> EnvelopeReport:
        index = flatten_index(flat)
        measured = _measurement_index(measurements)
        hard: list[ConstraintViolation] = []
        soft: list[ConstraintViolation] = []
        unresolved: list[ConstraintViolation] = []
        active_ids: list[str] = []
        stage_hard_issue: dict[EvaluationStage, bool] = {
            stage: False for stage in STAGE_ORDER
        }
        stage_had_limit: dict[EvaluationStage, bool] = {
            stage: False for stage in STAGE_ORDER
        }
        for bound_limit in self._bound:
            limit = bound_limit.limit
            owner_active = _owner_active(bound_limit.applies_when, index)
            if not owner_active:
                continue
            if not _limit_active(limit, index):
                continue
            active_ids.append(limit.id)
            stage_had_limit[limit.stage] = True
            measured_si, value_source = self._resolve_value(
                limit, measured, index
            )
            if measured_si is None:
                if limit.constraint_class is ConstraintClass.HARD:
                    reason = (
                        "MEASUREMENT_UNAVAILABLE"
                        if value_source == "unavailable"
                        else value_source
                    )
                    violation = self._violation(
                        bound_limit, limit, None, value_source, reason
                    )
                    hard.append(violation)
                    unresolved.append(violation)
                    stage_hard_issue[limit.stage] = True
                continue
            satisfied = _compare(limit.relation, measured_si, limit.limit_si)
            if satisfied:
                continue
            violation = self._violation(
                bound_limit, limit, measured_si, value_source, "LIMIT_EXCEEDED"
            )
            if limit.constraint_class is ConstraintClass.HARD:
                hard.append(violation)
                stage_hard_issue[limit.stage] = True
            else:
                soft.append(violation)
        metrics = self._soft_metrics(soft_metrics)
        cleared = self._cleared_stages(stage_had_limit, stage_hard_issue)
        accepted = not hard
        score = (
            manufacturability_score(metrics, self.soft_weights)
            if accepted and metrics
            else None
        )
        return EnvelopeReport(
            status="accepted" if accepted else "rejected",
            hard_violations=tuple(hard),
            soft_violations=tuple(soft),
            unresolved=tuple(unresolved),
            active_limit_ids=tuple(active_ids),
            cleared_stages=cleared,
            stage_reached=cleared[-1] if cleared else "none",
            score=score,
            soft_metrics=metrics,
            provenance=self._provenance(active_ids, flat, measurements, score),
        )

    def evaluate_state(
        self,
        space: Mapping[str, Any],
        state: Mapping[str, Any],
        *,
        measurements: Iterable[Measurement] | Mapping[str, Measurement] | None = None,
        soft_metrics: Mapping[str, float] | None = None,
    ) -> EnvelopeReport:
        from aeroworkbench_optimization.design_space import flatten_design_state

        flat = flatten_design_state(space, state)
        return self.evaluate(flat, measurements=measurements, soft_metrics=soft_metrics)

    def _resolve_value(
        self,
        limit: ScalarLimit,
        measured: Mapping[str, Measurement],
        index: Mapping[str, Mapping[str, Any]],
    ) -> tuple[float | None, str]:
        if limit.stage is EvaluationStage.NATIVE_SOLVER_VALIDATED:
            receipt = measured.get(limit.value_name)
            if receipt is None:
                return None, "native-receipt-missing"
            if not receipt.is_native_receipt or receipt.validity != "valid":
                return None, "native-receipt-untrusted"
            return receipt.value_si, "native_solver"
        if limit.stage is EvaluationStage.POST_CAD_GEOMETRY:
            observation = measured.get(limit.value_name)
            if observation is None:
                return None, "geometry-not-built"
            return observation.value_si, f"measurement:{observation.source}"
        measurement = measured.get(limit.value_name)
        if measurement is not None:
            return measurement.value_si, f"measurement:{measurement.source}"
        return _design_value_si(limit.value_name, index)

    def _violation(
        self,
        bound_limit: _BoundLimit,
        limit: ScalarLimit,
        measured_si: float | None,
        value_source: str,
        reason: str,
    ) -> ConstraintViolation:
        return ConstraintViolation(
            constraint_id=limit.id,
            value_name=limit.value_name,
            relation=limit.relation.value,
            stage=limit.stage.value,
            constraint_class=limit.constraint_class.value,
            measured_value_si=measured_si,
            limit_si=limit.limit_si,
            unit=limit.unit,
            declared_limit=limit.limit,
            envelope_id=bound_limit.envelope_id,
            envelope_kind=bound_limit.envelope_kind,
            envelope_revision=bound_limit.envelope_revision,
            envelope_hash=bound_limit.envelope_hash,
            source=limit.provenance.as_dict(),
            recommended_variables=limit.recommended_variables,
            measured_available=measured_si is not None,
            reason=reason,
            detail=limit.detail,
        )

    def _cleared_stages(
        self,
        stage_had_limit: Mapping[EvaluationStage, bool],
        stage_hard_issue: Mapping[EvaluationStage, bool],
    ) -> tuple[str, ...]:
        cleared: list[str] = []
        for stage in STAGE_ORDER:
            if stage_hard_issue[stage]:
                break
            if stage_had_limit[stage]:
                cleared.append(stage.value)
        return tuple(cleared)

    def _soft_metrics(
        self, soft_metrics: Mapping[str, float] | None
    ) -> dict[str, float]:
        if not soft_metrics:
            return {}
        metrics: dict[str, float] = {}
        for name, value in soft_metrics.items():
            if not isfinite(value) or value < 0:
                raise EnvelopeError(f"INVALID_SOFT_METRIC:{name}")
            metrics[str(name)] = float(value)
        return metrics

    def _provenance(
        self,
        active_ids: list[str],
        flat: Mapping[str, Any],
        measurements: Iterable[Measurement] | Mapping[str, Measurement] | None,
        score: float | None,
    ) -> dict[str, Any]:
        measurement_source = [
            item.as_dict()
            for item in _measurement_index(measurements).values()
        ]
        provenance = Provenance.from_inputs(
            source=ResultSource.ANALYTICAL,
            model="turbo05-manufacturability-gate",
            model_version="1.0",
            fidelity=FidelityLevel.ANALYTICAL,
            inputs={
                "envelopeSetHash": self.envelope_set_hash,
                "designStateHash": content_digest(flat),
                "activeLimits": active_ids,
                "measurements": measurement_source,
                "score": score,
            },
            assumptions=(
                "declarative limit screening only; no native solver was executed",
                "native-solver-validated limits require a trusted native receipt "
                "and fail closed otherwise",
                "soft metrics never override a hard violation",
            ),
        )
        return dict(provenance.model_dump(mode="json"))


def evaluate_envelopes(
    envelopes: EnvelopeSet,
    flat: Mapping[str, Any],
    *,
    measurements: Iterable[Measurement] | Mapping[str, Measurement] | None = None,
    soft_metrics: Mapping[str, float] | None = None,
    soft_weights: Mapping[str, float] | None = None,
) -> EnvelopeReport:
    """Convenience wrapper constructing a gate and evaluating one candidate."""

    return ManufacturabilityGate(envelopes, soft_weights=soft_weights).evaluate(
        flat, measurements=measurements, soft_metrics=soft_metrics
    )
