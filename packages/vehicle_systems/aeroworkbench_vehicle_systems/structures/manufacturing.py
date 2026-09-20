"""Structural design hand-off to the shared manufacturability gate.

The structural solver may find a strength-feasible thickness that cannot be made.
This adapter keeps process limits in the shared TURBO 05 contract and exposes the
structural observations as measurements, so missing observations fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_manufacturing import (
    ConstraintClass,
    EnvelopeSet,
    EvaluationStage,
    LimitProvenance,
    LimitRelation,
    LimitSourceKind,
    ManufacturabilityGate,
    ManufacturingProcessEnvelope,
    Measurement,
    ScalarLimit,
)

from .errors import StructuralConstraintError
from .sizing import SizedStructure

__all__ = [
    "StructuralManufacturingLimits",
    "screen_structure_manufacturability",
    "structural_measurements",
]


@dataclass(frozen=True, slots=True)
class StructuralManufacturingLimits:
    """Hard limits for one structural manufacturing route.

    ``dimensional_tolerance_m`` is the tolerance declared by the design. It is
    intentionally an input to the gate rather than an inferred solver value.
    """

    process: str
    revision: str
    minimum_dimension_m: float | None = None
    maximum_dimension_m: float | None = None
    minimum_gauge_m: float | None = None
    maximum_gauge_m: float | None = None
    dimensional_tolerance_m: float | None = None
    maximum_dimensional_tolerance_m: float | None = None
    minimum_yield_strength_pa: float | None = None
    minimum_laminate_ply_count: int | None = None
    minimum_laminate_ply_thickness_m: float | None = None
    maximum_laminate_ply_thickness_m: float | None = None

    def __post_init__(self) -> None:
        if not self.process.strip() or not self.revision.strip():
            raise ValueError("STRUCTURAL_PROCESS_IDENTITY_REQUIRED")
        for name in (
            "minimum_dimension_m",
            "maximum_dimension_m",
            "minimum_gauge_m",
            "maximum_gauge_m",
            "dimensional_tolerance_m",
            "maximum_dimensional_tolerance_m",
            "minimum_yield_strength_pa",
            "minimum_laminate_ply_thickness_m",
            "maximum_laminate_ply_thickness_m",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0.0:
                raise ValueError(f"STRUCTURAL_LIMIT_{name.upper()}_INVALID")
        if (
            self.minimum_laminate_ply_count is not None
            and self.minimum_laminate_ply_count < 1
        ):
            raise ValueError("STRUCTURAL_MINIMUM_PLY_COUNT_INVALID")

    def as_dict(self) -> dict[str, Any]:
        return {
            name: getattr(self, name)
            for name in (
                "process",
                "revision",
                "minimum_dimension_m",
                "maximum_dimension_m",
                "minimum_gauge_m",
                "maximum_gauge_m",
                "dimensional_tolerance_m",
                "maximum_dimensional_tolerance_m",
                "minimum_yield_strength_pa",
                "minimum_laminate_ply_count",
                "minimum_laminate_ply_thickness_m",
                "maximum_laminate_ply_thickness_m",
            )
        }


def _provenance(limits: StructuralManufacturingLimits) -> LimitProvenance:
    return LimitProvenance(
        source_kind=LimitSourceKind.MANUFACTURING_METHOD,
        reference=limits.process,
        revision=limits.revision,
        software="aeroworkbench-vehicle-systems-structures",
    )


def structural_measurements(structure: SizedStructure) -> tuple[Measurement, ...]:
    """Return deterministic per-member observations consumed by TURBO 05."""

    measurements: list[Measurement] = []
    for sized in structure.members:
        member = sized.member
        prefix = f"member.{member.member_id}"
        measurements.extend(
            (
                Measurement(
                    f"{prefix}.minimum_dimension",
                    min(member.section.height_m, member.section.width_m),
                    "m",
                ),
                Measurement(
                    f"{prefix}.maximum_dimension",
                    max(member.section.height_m, member.section.width_m),
                    "m",
                ),
                Measurement(f"{prefix}.gauge", member.section.thickness_m, "m"),
            )
        )
        if "yield_strength" in member.material.material.properties:
            measurements.append(
                Measurement(
                    f"{prefix}.yield_strength",
                    member.material.material.evaluate("yield_strength"),
                    "Pa",
                )
            )
        if member.material.laminate is not None:
            plies = member.material.laminate.plies
            measurements.extend(
                (
                    Measurement(f"{prefix}.ply_count", float(len(plies)), "1"),
                    Measurement(
                        f"{prefix}.minimum_ply_thickness",
                        min(ply.thickness_m for ply in plies),
                        "m",
                    ),
                    Measurement(
                        f"{prefix}.maximum_ply_thickness",
                        max(ply.thickness_m for ply in plies),
                        "m",
                    ),
                )
            )
    return tuple(measurements)


def _limits_for_member(
    member_id: str, limits: StructuralManufacturingLimits, *, laminate: bool
) -> tuple[ScalarLimit, ...]:
    provenance = _provenance(limits)
    built: list[ScalarLimit] = []

    def add(
        suffix: str, name: str, relation: LimitRelation, value: float, unit: str
    ) -> None:
        built.append(
            ScalarLimit(
                id=f"structural-{member_id}-{suffix}",
                value_name=f"member.{member_id}.{name}",
                relation=relation,
                limit=value,
                unit=unit,
                stage=EvaluationStage.PRE_SOLVER_PHYSICS,
                constraint_class=ConstraintClass.HARD,
                provenance=provenance,
            )
        )

    if limits.minimum_dimension_m is not None:
        add(
            "min-dimension",
            "minimum_dimension",
            LimitRelation.GREATER_OR_EQUAL,
            limits.minimum_dimension_m,
            "m",
        )
    if limits.maximum_dimension_m is not None:
        add(
            "max-dimension",
            "maximum_dimension",
            LimitRelation.LESS_OR_EQUAL,
            limits.maximum_dimension_m,
            "m",
        )
    if limits.minimum_gauge_m is not None:
        add(
            "min-gauge",
            "gauge",
            LimitRelation.GREATER_OR_EQUAL,
            limits.minimum_gauge_m,
            "m",
        )
    if limits.maximum_gauge_m is not None:
        add(
            "max-gauge",
            "gauge",
            LimitRelation.LESS_OR_EQUAL,
            limits.maximum_gauge_m,
            "m",
        )
    if limits.minimum_yield_strength_pa is not None:
        add(
            "min-yield",
            "yield_strength",
            LimitRelation.GREATER_OR_EQUAL,
            limits.minimum_yield_strength_pa,
            "Pa",
        )
    if laminate:
        if limits.minimum_laminate_ply_count is not None:
            add(
                "min-ply-count",
                "ply_count",
                LimitRelation.GREATER_OR_EQUAL,
                limits.minimum_laminate_ply_count,
                "1",
            )
        if limits.minimum_laminate_ply_thickness_m is not None:
            add(
                "min-ply-thickness",
                "minimum_ply_thickness",
                LimitRelation.GREATER_OR_EQUAL,
                limits.minimum_laminate_ply_thickness_m,
                "m",
            )
        if limits.maximum_laminate_ply_thickness_m is not None:
            add(
                "max-ply-thickness",
                "maximum_ply_thickness",
                LimitRelation.LESS_OR_EQUAL,
                limits.maximum_laminate_ply_thickness_m,
                "m",
            )
    return tuple(built)


def screen_structure_manufacturability(
    structure: SizedStructure, limits: StructuralManufacturingLimits
) -> None:
    """Reject a structurally feasible but unmanufacturable sized structure."""

    if (
        limits.maximum_dimensional_tolerance_m is not None
        and limits.dimensional_tolerance_m is None
    ):
        raise StructuralConstraintError(
            "STRUCTURAL_MANUFACTURING_TOLERANCE_UNDECLARED",
            violations=("tolerance:measurement-unavailable",),
        )
    envelope_limits: list[ScalarLimit] = []
    for sized in structure.members:
        envelope_limits.extend(
            _limits_for_member(
                sized.member.member_id,
                limits,
                laminate=sized.member.material.laminate is not None,
            )
        )
    if limits.maximum_dimensional_tolerance_m is not None:
        provenance = _provenance(limits)
        envelope_limits.append(
            ScalarLimit(
                id="structural-dimensional-tolerance",
                value_name="structural.dimensional_tolerance",
                relation=LimitRelation.LESS_OR_EQUAL,
                limit=limits.maximum_dimensional_tolerance_m,
                unit="m",
                stage=EvaluationStage.PRE_SOLVER_PHYSICS,
                constraint_class=ConstraintClass.HARD,
                provenance=provenance,
            )
        )
    envelope = ManufacturingProcessEnvelope(
        id=f"structural-{limits.process}",
        process=limits.process,
        revision=1,
        limits=tuple(envelope_limits),
        capability={"revision": limits.revision},
        provenance=_provenance(limits),
    )
    measurements = list(structural_measurements(structure))
    if limits.dimensional_tolerance_m is not None:
        measurements.append(
            Measurement(
                "structural.dimensional_tolerance", limits.dimensional_tolerance_m, "m"
            )
        )
    report = ManufacturabilityGate(EnvelopeSet(manufacturing=(envelope,))).evaluate(
        {"entries": []}, measurements=measurements
    )
    if report.status != "accepted":
        raise StructuralConstraintError(
            "STRUCTURAL_MANUFACTURING_GATE_REJECTED",
            violations=tuple(
                f"{item.constraint_id}:{item.reason}" for item in report.hard_violations
            ),
        )
