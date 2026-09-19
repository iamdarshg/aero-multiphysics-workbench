"""Manufacturing constraints for composite layups, enforced before analysis.

Declarative process limits (ply thickness, allowed orientations, minimum ply
count, symmetry/balance, drape/curvature, ply-drop taper) are screened against a
laminate. A hard violation is reported by code and, through
:func:`require_manufacturable`, rejected before any expensive CLT/failure or
native analysis runs. The same limits are emitted as TURBO 05 manufacturing
envelopes so the shared :class:`ManufacturabilityGate` can enforce them in the
platform staging order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_manufacturing import (
    ConstraintClass,
    EnvelopeReport,
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
from aeroworkbench_materials import LaminateRevision

from .clt import is_balanced, is_symmetric
from .provenance import analytical_provenance
from .validity import DataUnavailable, ManufacturingViolation, finite

__all__ = [
    "ManufacturingFinding",
    "ManufacturingReport",
    "PlyProcessLimits",
    "evaluate_manufacturability",
    "laminate_measurements",
    "manufacturing_envelope",
    "manufacturing_limits",
    "require_manufacturable",
    "screen_with_turbo05",
]


@dataclass(frozen=True, slots=True)
class PlyProcessLimits:
    """Declarative process limits for one composite manufacturing route."""

    process: str
    revision: str
    source: str
    min_ply_thickness_m: float
    max_ply_thickness_m: float
    allowed_orientations_deg: tuple[float, ...]
    orientation_tolerance_deg: float = 1e-6
    min_ply_count: int = 1
    require_symmetric: bool = False
    require_balanced: bool = False
    min_radius_m: float | None = None
    max_ply_drop_ratio: float | None = None
    max_drape_angle_deg: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.process.strip() or not self.source.strip() or not self.revision.strip():
            raise DataUnavailable("PROCESS_LIMITS_IDENTITY_AND_SOURCE_REQUIRED")
        finite(self.min_ply_thickness_m, "min_ply_thickness_m", positive=True)
        finite(self.max_ply_thickness_m, "max_ply_thickness_m", positive=True)
        if self.max_ply_thickness_m < self.min_ply_thickness_m:
            raise DataUnavailable("PROCESS_PLY_THICKNESS_RANGE_INVALID")
        if not self.allowed_orientations_deg:
            raise DataUnavailable("PROCESS_REQUIRES_ALLOWED_ORIENTATIONS")
        for angle in self.allowed_orientations_deg:
            finite(angle, "allowed_orientation_deg")
        if self.min_ply_count < 1:
            raise DataUnavailable("PROCESS_MIN_PLY_COUNT_INVALID")
        for name in ("min_radius_m", "max_ply_drop_ratio", "max_drape_angle_deg"):
            value = getattr(self, name)
            if value is not None:
                finite(value, name, positive=True)

    @property
    def identity(self) -> str:
        return f"{self.process}@{self.revision}"

    def allows_orientation(self, angle_deg: float) -> bool:
        target = angle_deg % 180.0
        return any(
            abs(target - (allowed % 180.0)) <= self.orientation_tolerance_deg
            for allowed in self.allowed_orientations_deg
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "process": self.process,
            "revision": self.revision,
            "source": self.source,
            "minPlyThicknessM": self.min_ply_thickness_m,
            "maxPlyThicknessM": self.max_ply_thickness_m,
            "allowedOrientationsDeg": list(self.allowed_orientations_deg),
            "minPlyCount": self.min_ply_count,
            "requireSymmetric": self.require_symmetric,
            "requireBalanced": self.require_balanced,
            "minRadiusM": self.min_radius_m,
            "maxPlyDropRatio": self.max_ply_drop_ratio,
            "maxDrapeAngleDeg": self.max_drape_angle_deg,
        }


@dataclass(frozen=True, slots=True)
class ManufacturingFinding:
    """One typed manufacturing-constraint finding."""

    code: str
    detail: str
    ply_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "plyIndex": self.ply_index}


@dataclass(frozen=True, slots=True)
class ManufacturingReport:
    """Manufacturability screen result for one laminate."""

    passed: bool
    findings: tuple[ManufacturingFinding, ...]
    checks: dict[str, bool]
    provenance: Provenance

    @property
    def violations(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [finding.as_dict() for finding in self.findings],
            "checks": dict(self.checks),
            "violations": list(self.violations),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def _adjacent_drop_ratio(thicknesses: tuple[float, ...]) -> float:
    worst = 0.0
    for first, second in zip(thicknesses, thicknesses[1:], strict=False):
        smaller = min(first, second)
        worst = max(worst, abs(first - second) / smaller)
    return worst


def evaluate_manufacturability(
    laminate: LaminateRevision,
    limits: PlyProcessLimits,
    *,
    region_radius_m: float | None = None,
    drape_angle_deg: float | None = None,
) -> ManufacturingReport:
    """Screen a laminate against declarative process limits, cheapest first."""

    findings: list[ManufacturingFinding] = []
    thicknesses = tuple(ply.thickness_m for ply in laminate.plies)
    checks: dict[str, bool] = {}

    thickness_ok = True
    for index, thickness in enumerate(thicknesses):
        if thickness < limits.min_ply_thickness_m - 1e-12:
            thickness_ok = False
            findings.append(
                ManufacturingFinding(
                    "PLY_THICKNESS_BELOW_MINIMUM",
                    f"ply {index} thickness {thickness:.6g} m < "
                    f"{limits.min_ply_thickness_m:.6g} m",
                    index,
                )
            )
        elif thickness > limits.max_ply_thickness_m + 1e-12:
            thickness_ok = False
            findings.append(
                ManufacturingFinding(
                    "PLY_THICKNESS_ABOVE_MAXIMUM",
                    f"ply {index} thickness {thickness:.6g} m > "
                    f"{limits.max_ply_thickness_m:.6g} m",
                    index,
                )
            )
    checks["ply_thickness_within_process_limits"] = thickness_ok

    orientation_ok = True
    for index, ply in enumerate(laminate.plies):
        if not limits.allows_orientation(ply.angle_deg):
            orientation_ok = False
            findings.append(
                ManufacturingFinding(
                    "ORIENTATION_NOT_ALLOWED",
                    f"ply {index} orientation {ply.angle_deg:.6g} deg is not in the "
                    f"allowed set",
                    index,
                )
            )
    checks["orientations_allowed"] = orientation_ok

    count_ok = len(laminate.plies) >= limits.min_ply_count
    if not count_ok:
        findings.append(
            ManufacturingFinding(
                "PLY_COUNT_BELOW_MINIMUM",
                f"{len(laminate.plies)} plies < required {limits.min_ply_count}",
            )
        )
    checks["ply_count_meets_minimum"] = count_ok

    symmetric = is_symmetric(laminate)
    symmetric_ok = symmetric or not limits.require_symmetric
    if limits.require_symmetric and not symmetric:
        findings.append(
            ManufacturingFinding(
                "LAYUP_NOT_SYMMETRIC", "process requires a symmetric stacking sequence"
            )
        )
    checks["symmetry_requirement_met"] = symmetric_ok

    balanced = is_balanced(laminate)
    balanced_ok = balanced or not limits.require_balanced
    if limits.require_balanced and not balanced:
        findings.append(
            ManufacturingFinding(
                "LAYUP_NOT_BALANCED", "process requires a balanced stacking sequence"
            )
        )
    checks["balance_requirement_met"] = balanced_ok

    radius_ok = True
    if limits.min_radius_m is not None:
        if region_radius_m is None:
            radius_ok = False
            findings.append(
                ManufacturingFinding(
                    "REGION_RADIUS_UNAVAILABLE",
                    "process declares a minimum radius but no region curvature was supplied",
                )
            )
        elif region_radius_m < limits.min_radius_m:
            radius_ok = False
            findings.append(
                ManufacturingFinding(
                    "REGION_RADIUS_BELOW_MINIMUM",
                    f"curvature radius {region_radius_m:.6g} m < required "
                    f"{limits.min_radius_m:.6g} m",
                )
            )
    checks["drapability_radius_met"] = radius_ok

    drape_ok = True
    if limits.max_drape_angle_deg is not None:
        if drape_angle_deg is None:
            drape_ok = False
            findings.append(
                ManufacturingFinding(
                    "DRAPE_ANGLE_UNAVAILABLE",
                    "process declares a maximum drape angle but none was supplied",
                )
            )
        elif abs(drape_angle_deg) > limits.max_drape_angle_deg:
            drape_ok = False
            findings.append(
                ManufacturingFinding(
                    "DRAPE_ANGLE_EXCEEDED",
                    f"drape angle {drape_angle_deg:.6g} deg > "
                    f"{limits.max_drape_angle_deg:.6g} deg",
                )
            )
    checks["drape_angle_within_limit"] = drape_ok

    drop_ratio = _adjacent_drop_ratio(thicknesses)
    if limits.max_ply_drop_ratio is None:
        drop_ok = True
    else:
        drop_ok = drop_ratio <= limits.max_ply_drop_ratio + 1e-12
        if not drop_ok:
            findings.append(
                ManufacturingFinding(
                    "PLY_DROP_RATIO_EXCEEDED",
                    f"adjacent ply drop ratio {drop_ratio:.6g} > allowed "
                    f"{limits.max_ply_drop_ratio:.6g}",
                )
            )
    checks["ply_drop_ratio_within_limit"] = drop_ok

    provenance = analytical_provenance(
        "composite-manufacturability-screen",
        {
            "laminate": laminate.identity,
            "process": limits.identity,
            "plyThicknessesM": list(thicknesses),
            "anglesDeg": [ply.angle_deg for ply in laminate.plies],
            "regionRadiusM": region_radius_m,
            "drapeAngleDeg": drape_angle_deg,
            "plyDropRatio": drop_ratio,
        },
        assumptions=(
            "declarative process-limit screening; no native solver was executed",
            "hard findings reject the layup before expensive analysis",
        ),
    )
    return ManufacturingReport(
        passed=not findings,
        findings=tuple(findings),
        checks=checks,
        provenance=provenance,
    )


def require_manufacturable(
    laminate: LaminateRevision,
    limits: PlyProcessLimits,
    *,
    region_radius_m: float | None = None,
    drape_angle_deg: float | None = None,
) -> ManufacturingReport:
    """Fail closed with provenance if any hard manufacturing limit is violated."""

    report = evaluate_manufacturability(
        laminate,
        limits,
        region_radius_m=region_radius_m,
        drape_angle_deg=drape_angle_deg,
    )
    if not report.passed:
        raise ManufacturingViolation(
            f"MANUFACTURING_CONSTRAINTS_VIOLATED:{laminate.identity}:"
            + ",".join(report.violations),
            violations=report.violations,
            provenance=report.provenance,
        )
    return report


def _provenance(limits: PlyProcessLimits) -> LimitProvenance:
    return LimitProvenance(
        source_kind=LimitSourceKind.MANUFACTURING_METHOD,
        reference=limits.process,
        revision=limits.revision,
        software="aeroworkbench-composites",
    )


def manufacturing_limits(limits: PlyProcessLimits) -> tuple[ScalarLimit, ...]:
    """Express process limits as TURBO 05 scalar limits in evaluation order."""

    provenance = _provenance(limits)
    built: list[ScalarLimit] = [
        ScalarLimit(
            id="composite-ply-count-min",
            value_name="ply_count",
            relation=LimitRelation.GREATER_OR_EQUAL,
            limit=float(limits.min_ply_count),
            unit="1",
            stage=EvaluationStage.PRE_CAD_ALGEBRAIC,
            constraint_class=ConstraintClass.HARD,
            provenance=provenance,
            detail="minimum number of plies",
        ),
        ScalarLimit(
            id="composite-min-ply-thickness",
            value_name="minimum_ply_thickness",
            relation=LimitRelation.GREATER_OR_EQUAL,
            limit=limits.min_ply_thickness_m,
            unit="m",
            stage=EvaluationStage.POST_CAD_GEOMETRY,
            constraint_class=ConstraintClass.HARD,
            provenance=provenance,
            detail="minimum cured ply thickness",
        ),
        ScalarLimit(
            id="composite-max-ply-thickness",
            value_name="maximum_ply_thickness",
            relation=LimitRelation.LESS_OR_EQUAL,
            limit=limits.max_ply_thickness_m,
            unit="m",
            stage=EvaluationStage.POST_CAD_GEOMETRY,
            constraint_class=ConstraintClass.HARD,
            provenance=provenance,
            detail="maximum cured ply thickness",
        ),
    ]
    if limits.min_radius_m is not None:
        built.append(
            ScalarLimit(
                id="composite-min-radius",
                value_name="region_curvature_radius",
                relation=LimitRelation.GREATER_OR_EQUAL,
                limit=limits.min_radius_m,
                unit="m",
                stage=EvaluationStage.POST_CAD_GEOMETRY,
                constraint_class=ConstraintClass.HARD,
                provenance=provenance,
                detail="minimum drape/curvature radius",
            )
        )
    if limits.max_ply_drop_ratio is not None:
        built.append(
            ScalarLimit(
                id="composite-max-ply-drop-ratio",
                value_name="ply_drop_ratio",
                relation=LimitRelation.LESS_OR_EQUAL,
                limit=limits.max_ply_drop_ratio,
                unit="1",
                stage=EvaluationStage.PRE_SOLVER_PHYSICS,
                constraint_class=ConstraintClass.HARD,
                provenance=provenance,
                detail="maximum adjacent ply drop/taper ratio",
            )
        )
    return tuple(built)


def manufacturing_envelope(
    limits: PlyProcessLimits, *, envelope_id: str = "composite-layup"
) -> ManufacturingProcessEnvelope:
    """Build the TURBO 05 process envelope for a composite layup route."""

    return ManufacturingProcessEnvelope(
        id=envelope_id,
        process=limits.process,
        revision=1,
        limits=manufacturing_limits(limits),
        capability={
            "allowedOrientationsDeg": list(limits.allowed_orientations_deg),
            "requireSymmetric": limits.require_symmetric,
            "requireBalanced": limits.require_balanced,
        },
        provenance=_provenance(limits),
    )


def laminate_measurements(
    laminate: LaminateRevision, *, region_radius_m: float | None = None
) -> tuple[Measurement, ...]:
    """Observed laminate metrics for the TURBO 05 gate."""

    thicknesses = tuple(ply.thickness_m for ply in laminate.plies)
    drop_ratio = _adjacent_drop_ratio(thicknesses)
    measurements = [
        Measurement(name="ply_count", value=float(len(laminate.plies)), unit="1"),
        Measurement(
            name="minimum_ply_thickness", value=min(thicknesses), unit="m"
        ),
        Measurement(
            name="maximum_ply_thickness", value=max(thicknesses), unit="m"
        ),
        Measurement(name="ply_drop_ratio", value=drop_ratio, unit="1"),
    ]
    if region_radius_m is not None:
        measurements.append(
            Measurement(
                name="region_curvature_radius", value=region_radius_m, unit="m"
            )
        )
    return tuple(measurements)


def screen_with_turbo05(
    limits: PlyProcessLimits,
    laminate: LaminateRevision,
    *,
    region_radius_m: float | None = None,
) -> EnvelopeReport:
    """Evaluate the process envelope through the shared TURBO 05 gate."""

    envelope = manufacturing_envelope(limits)
    gate = ManufacturabilityGate(EnvelopeSet(manufacturing=(envelope,)))
    return gate.evaluate(
        {"entries": []},
        measurements=laminate_measurements(laminate, region_radius_m=region_radius_m),
    )
