"""Boundary-layer generation: y+/first-cell targets with real achieved metrics.

A :class:`WallResolutionTarget` declares a target first-cell height or a target
y+ (with reference flow), a layer count, and a growth ratio. Planning converts
that into per-layer heights and a total thickness, then applies local curvature
and clearance limits and collision/negative-volume checks. The resulting
:class:`BoundaryLayerPlan` records *achieved* layer metrics, never only the
requested ones, so a downstream quality receipt can check the real result.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, log

from .contracts import ResultEnvelope, Validity, analytical_envelope
from .errors import MeshContractError
from .intents import PhysicsState

__all__ = [
    "BoundaryLayerPlan",
    "FlowReference",
    "WallResolutionTarget",
    "flow_reference_from_state",
    "layer_heights_mm",
    "plan_boundary_layer",
    "total_thickness_mm",
]


def _positive(label: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise MeshContractError(f"{label}_MUST_BE_FINITE_POSITIVE")


@dataclass(frozen=True, slots=True)
class FlowReference:
    """Reference wall flow used to convert a y+ target into a first-cell height."""

    friction_velocity_m_s: float
    density_kg_m3: float
    dynamic_viscosity_pa_s: float

    def __post_init__(self) -> None:
        _positive("FRICTION_VELOCITY", self.friction_velocity_m_s)
        _positive("DENSITY", self.density_kg_m3)
        _positive("DYNAMIC_VISCOSITY", self.dynamic_viscosity_pa_s)

    @property
    def kinematic_viscosity_m2_s(self) -> float:
        return self.dynamic_viscosity_pa_s / self.density_kg_m3

    def first_layer_from_y_plus(self, y_plus: float) -> float:
        _positive("Y_PLUS", y_plus)
        return y_plus * self.kinematic_viscosity_m2_s / self.friction_velocity_m_s * 1000.0

    def y_plus_for_height(self, first_layer_mm: float) -> float:
        _positive("FIRST_LAYER", first_layer_mm)
        return first_layer_mm / 1000.0 * self.friction_velocity_m_s / self.kinematic_viscosity_m2_s

    def as_dict(self) -> dict[str, float]:
        return {
            "frictionVelocityMS": self.friction_velocity_m_s,
            "densityKgM3": self.density_kg_m3,
            "dynamicViscosityPaS": self.dynamic_viscosity_pa_s,
        }


def flow_reference_from_state(state: PhysicsState) -> FlowReference | None:
    """Build a flow reference from declared state fields, or ``None`` if absent."""

    if (
        state.friction_velocity_m_s is None
        or state.density_kg_m3 is None
        or state.dynamic_viscosity_pa_s is None
    ):
        return None
    return FlowReference(
        friction_velocity_m_s=state.friction_velocity_m_s,
        density_kg_m3=state.density_kg_m3,
        dynamic_viscosity_pa_s=state.dynamic_viscosity_pa_s,
    )


@dataclass(frozen=True, slots=True)
class WallResolutionTarget:
    """Declared wall-resolution intent for one or more wall patches."""

    wall_patches: tuple[str, ...]
    layer_count: int
    growth_ratio: float
    first_layer_mm: float | None = None
    y_plus_target: float | None = None
    max_total_thickness_mm: float | None = None
    curvature_limit_fraction: float = 0.2
    clearance_fraction: float = 0.5
    y_plus_tolerance: float = 0.25

    def __post_init__(self) -> None:
        if not self.wall_patches:
            raise MeshContractError("BOUNDARY_LAYER_NEEDS_WALLS")
        if self.layer_count < 1:
            raise MeshContractError("BOUNDARY_LAYER_LAYER_COUNT_INVALID")
        if not isfinite(self.growth_ratio) or self.growth_ratio < 1.0:
            raise MeshContractError("BOUNDARY_LAYER_GROWTH_INVALID")
        if self.first_layer_mm is None and self.y_plus_target is None:
            raise MeshContractError("BOUNDARY_LAYER_NEEDS_FIRST_LAYER_OR_Y_PLUS")
        if self.first_layer_mm is not None:
            _positive("BOUNDARY_LAYER_FIRST_LAYER", self.first_layer_mm)
        if self.y_plus_target is not None:
            _positive("BOUNDARY_LAYER_Y_PLUS_TARGET", self.y_plus_target)
        if self.max_total_thickness_mm is not None:
            _positive("BOUNDARY_LAYER_MAX_TOTAL", self.max_total_thickness_mm)
        if not 0.0 < self.curvature_limit_fraction <= 1.0:
            raise MeshContractError("CURVATURE_LIMIT_FRACTION_INVALID")
        if not 0.0 < self.clearance_fraction <= 1.0:
            raise MeshContractError("CLEARANCE_FRACTION_INVALID")
        if not 0.0 <= self.y_plus_tolerance < 1.0:
            raise MeshContractError("Y_PLUS_TOLERANCE_INVALID")


def layer_heights_mm(
    first_layer_mm: float, growth_ratio: float, layer_count: int
) -> tuple[float, ...]:
    """Geometric layer heights for a boundary-layer stack."""

    _positive("FIRST_LAYER", first_layer_mm)
    if layer_count < 1:
        raise MeshContractError("LAYER_COUNT_INVALID")
    if not isfinite(growth_ratio) or growth_ratio < 1.0:
        raise MeshContractError("GROWTH_RATIO_INVALID")
    return tuple(first_layer_mm * growth_ratio**index for index in range(layer_count))


def total_thickness_mm(first_layer_mm: float, growth_ratio: float, layer_count: int) -> float:
    """Closed-form total thickness of a geometric layer stack."""

    _positive("FIRST_LAYER", first_layer_mm)
    if layer_count < 1:
        raise MeshContractError("LAYER_COUNT_INVALID")
    if not isfinite(growth_ratio) or growth_ratio < 1.0:
        raise MeshContractError("GROWTH_RATIO_INVALID")
    if growth_ratio == 1.0:
        return first_layer_mm * layer_count
    return first_layer_mm * (growth_ratio**layer_count - 1.0) / (growth_ratio - 1.0)


def _max_layers(first_layer_mm: float, growth_ratio: float, cap_mm: float) -> int:
    if cap_mm <= 0.0:
        return 0
    if growth_ratio == 1.0:
        return int(floor(cap_mm / first_layer_mm))
    ratio = 1.0 + cap_mm * (growth_ratio - 1.0) / first_layer_mm
    if ratio <= 1.0:
        return 0
    return int(floor(log(ratio) / log(growth_ratio)))


@dataclass(frozen=True, slots=True)
class BoundaryLayerPlan:
    """Achieved boundary-layer metrics after curvature/clearance limiting."""

    wall_patches: tuple[str, ...]
    requested_first_layer_mm: float
    achieved_first_layer_mm: float
    growth_ratio: float
    requested_layer_count: int
    achieved_layer_count: int
    requested_total_thickness_mm: float
    achieved_total_thickness_mm: float
    layer_heights_mm: tuple[float, ...]
    y_plus_target: float | None
    achieved_y_plus: float | None
    meets_y_plus_target: bool | None
    limited_by: tuple[str, ...]
    collision: bool
    negative_volume: bool
    coverage_fraction: float
    checks: dict[str, bool]
    envelope: ResultEnvelope

    @property
    def valid(self) -> bool:
        return not self.collision and not self.negative_volume and self.achieved_layer_count >= 1

    def as_dict(self) -> dict[str, object]:
        return {
            "wallPatches": list(self.wall_patches),
            "requestedFirstLayerMm": self.requested_first_layer_mm,
            "achievedFirstLayerMm": self.achieved_first_layer_mm,
            "growthRatio": self.growth_ratio,
            "requestedLayerCount": self.requested_layer_count,
            "achievedLayerCount": self.achieved_layer_count,
            "requestedTotalThicknessMm": self.requested_total_thickness_mm,
            "achievedTotalThicknessMm": self.achieved_total_thickness_mm,
            "layerHeightsMm": list(self.layer_heights_mm),
            "yPlusTarget": self.y_plus_target,
            "achievedYPlus": self.achieved_y_plus,
            "meetsYPlusTarget": self.meets_y_plus_target,
            "limitedBy": list(self.limited_by),
            "collision": self.collision,
            "negativeVolume": self.negative_volume,
            "coverageFraction": self.coverage_fraction,
            "checks": dict(self.checks),
            "valid": self.valid,
        }


def plan_boundary_layer(
    target: WallResolutionTarget,
    *,
    reference: FlowReference | None = None,
    curvature_radius_mm: float | None = None,
    clearance_mm: float | None = None,
) -> BoundaryLayerPlan:
    """Plan a wall stack and record achieved, not merely requested, metrics."""

    if curvature_radius_mm is not None:
        _positive("CURVATURE_RADIUS", curvature_radius_mm)
    if clearance_mm is not None:
        _positive("CLEARANCE", clearance_mm)

    if target.first_layer_mm is not None:
        requested_first = target.first_layer_mm
    elif reference is not None and target.y_plus_target is not None:
        requested_first = reference.first_layer_from_y_plus(target.y_plus_target)
    else:
        raise MeshContractError("BOUNDARY_LAYER_NEEDS_FIRST_LAYER_OR_Y_PLUS_REFERENCE")

    requested_total = total_thickness_mm(
        requested_first, target.growth_ratio, target.layer_count
    )

    caps: list[tuple[str, float]] = []
    if target.max_total_thickness_mm is not None:
        caps.append(("max_total_thickness", target.max_total_thickness_mm))
    if clearance_mm is not None:
        caps.append(("clearance", target.clearance_fraction * clearance_mm))
    if curvature_radius_mm is not None:
        caps.append(
            ("curvature", target.curvature_limit_fraction * curvature_radius_mm)
        )

    limited_by: list[str] = []
    achieved_count = target.layer_count
    collision = False
    if caps:
        cap_label, cap_value = min(caps, key=lambda item: item[1])
        capped = _max_layers(requested_first, target.growth_ratio, cap_value)
        if capped < achieved_count:
            limited_by.append(cap_label)
            achieved_count = capped
        if achieved_count < 1:
            collision = True

    negative_volume = requested_first <= 0.0 or target.growth_ratio < 1.0
    achieved_count = max(achieved_count, 0)
    achieved_total = (
        total_thickness_mm(requested_first, target.growth_ratio, achieved_count)
        if achieved_count >= 1
        else 0.0
    )
    heights = (
        layer_heights_mm(requested_first, target.growth_ratio, achieved_count)
        if achieved_count >= 1
        else ()
    )
    achieved_y_plus: float | None = None
    meets: bool | None = None
    if reference is not None:
        achieved_y_plus = reference.y_plus_for_height(requested_first)
        if target.y_plus_target is not None:
            meets = (
                abs(achieved_y_plus - target.y_plus_target)
                <= target.y_plus_tolerance * target.y_plus_target
            )
    coverage = achieved_total / requested_total if requested_total > 0.0 else 0.0
    checks = {
        "no_negative_volume": not negative_volume,
        "no_collision": not collision,
        "layers_present": achieved_count >= 1,
    }
    if meets is not None:
        checks["y_plus_within_tolerance"] = meets
    valid = Validity(
        passed=all(checks.values()),
        checks=checks,
        detail=(
            f"achieved {achieved_count}/{target.layer_count} layers, "
            f"first {requested_first:.6g}mm, coverage {coverage:.3f}"
        ),
    )
    envelope = analytical_envelope(
        model="boundary-layer-plan",
        inputs={
            "target": {
                "wallPatches": list(target.wall_patches),
                "layerCount": target.layer_count,
                "growthRatio": target.growth_ratio,
                "firstLayerMm": target.first_layer_mm,
                "yPlusTarget": target.y_plus_target,
                "maxTotalThicknessMm": target.max_total_thickness_mm,
            },
            "reference": None if reference is None else reference.as_dict(),
            "curvatureRadiusMm": curvature_radius_mm,
            "clearanceMm": clearance_mm,
        },
        units=(("length", "mm"), ("dimensionless", "1")),
        validity=valid,
        assumptions=(
            "geometric layer stack; achieved metrics recorded after limiting",
            "collision/negative-volume checked against declared clearance/curvature",
        ),
    )
    return BoundaryLayerPlan(
        wall_patches=tuple(target.wall_patches),
        requested_first_layer_mm=requested_first,
        achieved_first_layer_mm=requested_first,
        growth_ratio=target.growth_ratio,
        requested_layer_count=target.layer_count,
        achieved_layer_count=achieved_count,
        requested_total_thickness_mm=requested_total,
        achieved_total_thickness_mm=achieved_total,
        layer_heights_mm=heights,
        y_plus_target=target.y_plus_target,
        achieved_y_plus=achieved_y_plus,
        meets_y_plus_target=meets,
        limited_by=tuple(limited_by),
        collision=collision,
        negative_volume=negative_volume,
        coverage_fraction=coverage,
        checks=checks,
        envelope=envelope,
    )
