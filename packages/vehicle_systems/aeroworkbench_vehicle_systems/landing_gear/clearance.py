"""Tail-strike, prop/rotor, and wingtip clearance through actual gear geometry.

Clearance points are rotated about the pivot gear contact by a declared pitch
angle and their height above the ground plane is compared with a required
clearance. This uses the real contact geometry (no stored strike-angle
heuristic): a low or overhung point fails its own check and the overall verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin
from typing import Any

from aeroworkbench_airframe import Vec3

from .contracts import LandingGearFidelity, ResultMeta, result_meta
from .errors import LandingGearError, finite
from .geometry import LandingGearAssembly


@dataclass(frozen=True, slots=True)
class ClearancePoint:
    """A physical point (tail/prop/rotor/wingtip) with a required clearance."""

    point_id: str
    location: Vec3
    required_clearance_m: float
    kind: str = "generic"

    def __post_init__(self) -> None:
        if not self.point_id.strip():
            raise LandingGearError("clearance.point_id is required")
        if self.location.dimension != "length":
            raise LandingGearError("clearance.location must be a length")
        finite(self.required_clearance_m, "clearance.required_clearance_m", minimum=0.0)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "pointId": self.point_id,
            "kind": self.kind,
            "location": self.location.canonical(),
            "requiredClearanceM": self.required_clearance_m,
        }


@dataclass(frozen=True, slots=True)
class PointClearance:
    """The rotated clearance of one point and its pass/fail verdict."""

    point_id: str
    kind: str
    clearance_m: float
    required_clearance_m: float
    passed: bool

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "pointId": self.point_id,
            "kind": self.kind,
            "clearanceM": self.clearance_m,
            "requiredClearanceM": self.required_clearance_m,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class ClearanceResult:
    """Pitch-angle clearance verdict for a set of physical points."""

    scenario_id: str
    rotation_angle_rad: float
    pivot_leg_id: str
    min_clearance_m: float
    points: tuple[PointClearance, ...]
    passed: bool
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {"length": "m", "angle": "rad"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "rotationAngleRad": self.rotation_angle_rad,
            "pivotLegId": self.pivot_leg_id,
            "minClearanceM": self.min_clearance_m,
            "points": [point.canonical_payload() for point in self.points],
            "passed": self.passed,
            "meta": self.meta.canonical(),
        }


def _pivot(
    assembly: LandingGearAssembly, pivot_leg_id: str | None
) -> tuple[str, Vec3]:
    if pivot_leg_id is not None:
        leg = assembly.leg(pivot_leg_id)
        return leg.leg_id, leg.contact_point()
    mains = assembly.main_legs
    if not mains:
        raise LandingGearError("CLEARANCE_REQUIRES_A_MAIN_GEAR_PIVOT")
    leg = min(mains, key=lambda candidate: candidate.contact_point().x)
    return leg.leg_id, leg.contact_point()


def check_clearance(
    assembly: LandingGearAssembly,
    points: tuple[ClearancePoint, ...],
    *,
    rotation_angle_rad: float,
    pivot_leg_id: str | None = None,
    scenario_id: str = "clearance",
    model: str = "clearance.pitch-rotation",
) -> ClearanceResult:
    """Rotate points about the gear pivot and verify required clearances."""

    angle = finite(rotation_angle_rad, "rotation_angle_rad")
    if not points:
        raise LandingGearError("CLEARANCE_POINTS_REQUIRED")
    identifiers = [point.point_id for point in points]
    if len(identifiers) != len(set(identifiers)):
        raise LandingGearError("DUPLICATE_CLEARANCE_POINT")
    pivot_id, pivot = _pivot(assembly, pivot_leg_id)
    cos_a, sin_a = cos(angle), sin(angle)

    evaluated: list[PointClearance] = []
    for point in points:
        dx = point.location.x - pivot.x
        dz = point.location.z - pivot.z
        rotated_z = -dx * sin_a + dz * cos_a
        clearance = -rotated_z
        evaluated.append(
            PointClearance(
                point_id=point.point_id,
                kind=point.kind,
                clearance_m=clearance,
                required_clearance_m=point.required_clearance_m,
                passed=clearance >= point.required_clearance_m,
            )
        )
    passed = all(point.passed for point in evaluated)
    min_clearance = min(point.clearance_m for point in evaluated)
    meta = result_meta(
        model=f"vehicle-systems.landing-gear.{model}",
        inputs={
            "assembly": assembly.canonical_payload(),
            "points": [point.canonical_payload() for point in points],
            "rotationAngleRad": angle,
            "pivotLegId": pivot_id,
        },
        valid=passed,
        checks={point.point_id: point.passed for point in evaluated},
        detail="pitch-rotation clearance about the gear contact pivot",
        fidelity=LandingGearFidelity.ANALYTICAL,
        assumptions=("rigid-body pitch rotation; no suspension compression",),
    )
    return ClearanceResult(
        scenario_id=scenario_id,
        rotation_angle_rad=angle,
        pivot_leg_id=pivot_id,
        min_clearance_m=min_clearance,
        points=tuple(evaluated),
        passed=passed,
        meta=meta,
    )


def rotation_clearance_points(
    *, tail: ClearancePoint | None = None, propeller: ClearancePoint | None = None
) -> tuple[ClearancePoint, ...]:
    """Convenience collector for the common tail-strike and prop-strike points."""

    points = [point for point in (tail, propeller) if point is not None]
    if not points:
        raise LandingGearError("NO_CLEARANCE_POINTS_DECLARED")
    return tuple(points)


def require_clearance(assembly: LandingGearAssembly, result: ClearanceResult) -> None:
    """Fail closed when any declared clearance point violates its requirement."""

    if not result.passed:
        failed = [point.point_id for point in result.points if not point.passed]
        raise LandingGearError(f"CLEARANCE_VIOLATION:{assembly.assembly_id}:{','.join(failed)}")


__all__ = [
    "ClearancePoint",
    "ClearanceResult",
    "PointClearance",
    "check_clearance",
    "require_clearance",
    "rotation_clearance_points",
]
