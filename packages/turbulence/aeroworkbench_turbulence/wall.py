"""Near-wall treatment as a first-class, mesh-checked requirement.

A :class:`WallTreatmentRequirement` declares the target y+ range, the
wall-resolved vs wall-function mode, the first-cell-height target, the
prism/inflation-layer count and growth ratio, the total boundary-layer thickness
intent, and the thermal-wall requirement when conjugate heat transfer is active.
:func:`evaluate_wall_treatment` compares a *measured* mesh resolution against the
requirement and fails closed when the measurement is missing or incompatible, so
a solver case can reject a mesh whose wall resolution does not match the
requested wall model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_fluid_properties import SoftwareIdentity
from aeroworkbench_mesh import BoundaryLayerIntent

from .contracts import SOFTWARE_IDENTITY, analytical_provenance
from .errors import TurbulenceValidationError
from .regimes import FlowRegime, FlowState, reynolds_number
from .roughness import RoughnessSpec


@dataclass(frozen=True, slots=True)
class CorrelationRef:
    """A named, versioned, sourced correlation."""

    correlation_id: str
    version: str
    source: str

    def __post_init__(self) -> None:
        if not self.correlation_id.strip() or not self.version.strip():
            raise TurbulenceValidationError("CORRELATION_IDENTITY_REQUIRED")
        if not self.source.strip():
            raise TurbulenceValidationError("CORRELATION_SOURCE_REQUIRED")

    def canonical(self) -> dict[str, Any]:
        return {
            "correlationId": self.correlation_id,
            "version": self.version,
            "source": self.source,
        }


BLASIUS_LAMINAR_SKIN_FRICTION = CorrelationRef(
    correlation_id="blasius-laminar-skin-friction",
    version="1",
    source="Blasius flat-plate solution, Cf = 0.664/sqrt(Re_x)",
)

SCHLICHTING_TURBULENT_SKIN_FRICTION = CorrelationRef(
    correlation_id="schlichting-turbulent-skin-friction",
    version="1",
    source="Schlichting turbulent flat plate, Cf = 0.0576/Re_x^0.2",
)


class WallTreatmentMode(StrEnum):
    """Wall-resolved vs wall-function vs adaptive near-wall treatment."""

    NONE = "none"
    WALL_FUNCTION = "wall_function"
    WALL_RESOLVED = "wall_resolved"
    LOW_REYNOLDS = "low_reynolds"
    ADAPTIVE = "adaptive"


#: mode -> (target y+ min, target y+ max, nominal target y+)
_WALL_MODE_TARGETS: dict[WallTreatmentMode, tuple[float, float, float]] = {
    WallTreatmentMode.WALL_FUNCTION: (30.0, 300.0, 50.0),
    WallTreatmentMode.WALL_RESOLVED: (0.1, 5.0, 1.0),
    WallTreatmentMode.LOW_REYNOLDS: (0.1, 1.0, 0.5),
    WallTreatmentMode.ADAPTIVE: (1.0, 300.0, 30.0),
}

WALL_TREATMENT_SOURCES: dict[WallTreatmentMode, str] = {
    WallTreatmentMode.WALL_FUNCTION: "wall-function y+ band 30..300 (declared)",
    WallTreatmentMode.WALL_RESOLVED: "wall-resolved sublayer y+ band 0.1..5 (declared)",
    WallTreatmentMode.LOW_REYNOLDS: "low-Reynolds damping y+ band 0.1..1 (declared)",
    WallTreatmentMode.ADAPTIVE: "adaptive near-wall band y+ 1..300 (declared)",
    WallTreatmentMode.NONE: "no near-wall treatment requested",
}


def _require_positive(label: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise TurbulenceValidationError(f"{label}_INVALID")


def laminar_skin_friction(reynolds_x: float) -> tuple[float, CorrelationRef]:
    """Blasius laminar flat-plate skin friction; validity-bounded."""
    if not isfinite(reynolds_x) or not 1.0e3 <= reynolds_x <= 1.0e6:
        raise TurbulenceValidationError("BLASIUS_VALIDITY_EXCEEDED")
    return 0.664 / sqrt(reynolds_x), BLASIUS_LAMINAR_SKIN_FRICTION


def turbulent_skin_friction(reynolds_x: float) -> tuple[float, CorrelationRef]:
    """Schlichting turbulent flat-plate skin friction; validity-bounded."""
    if not isfinite(reynolds_x) or not 5.0e4 <= reynolds_x <= 1.0e9:
        raise TurbulenceValidationError("SCHLICHTING_VALIDITY_EXCEEDED")
    return 0.0576 / reynolds_x**0.2, SCHLICHTING_TURBULENT_SKIN_FRICTION


def skin_friction_coefficient_flat_plate(
    reynolds_x: float, *, regime: FlowRegime | None = None
) -> tuple[float, CorrelationRef]:
    """Select the laminar or turbulent skin-friction correlation by regime.

    A transitional regime uses the turbulent correlation as a declared
    conservative estimate; the returned :class:`CorrelationRef` records which
    correlation was used.
    """
    resolved = regime
    if resolved is None:
        resolved = (
            FlowRegime.LAMINAR if reynolds_x <= 5.0e5 else FlowRegime.TURBULENT
        )
    if resolved is FlowRegime.LAMINAR:
        return laminar_skin_friction(reynolds_x)
    return turbulent_skin_friction(reynolds_x)


def inflation_total_thickness(
    *, first_cell_height_m: float, growth_ratio: float, layer_count: int
) -> float:
    """Total thickness of a geometric inflation stack."""
    _require_positive("FIRST_CELL_HEIGHT", first_cell_height_m)
    _require_positive("GROWTH_RATIO", growth_ratio)
    if growth_ratio < 1.0:
        raise TurbulenceValidationError("GROWTH_RATIO_BELOW_ONE")
    if layer_count < 1:
        raise TurbulenceValidationError("LAYER_COUNT_INVALID")
    if growth_ratio == 1.0:
        return first_cell_height_m * layer_count
    return first_cell_height_m * (growth_ratio**layer_count - 1.0) / (growth_ratio - 1.0)


def first_cell_height_for_y_plus(
    *,
    target_y_plus: float,
    density_kg_m3: float,
    velocity_m_s: float,
    length_m: float,
    viscosity_pa_s: float,
    regime: FlowRegime | None = None,
) -> tuple[float, CorrelationRef]:
    """First-cell height achieving a target y+ from a skin-friction estimate."""
    _require_positive("TARGET_Y_PLUS", target_y_plus)
    if not isfinite(velocity_m_s) or velocity_m_s <= 0.0:
        raise TurbulenceValidationError("WALL_REFERENCE_VELOCITY_INVALID")
    reynolds = reynolds_number(
        density_kg_m3=density_kg_m3,
        velocity_m_s=velocity_m_s,
        length_m=length_m,
        viscosity_pa_s=viscosity_pa_s,
    )
    friction, reference = skin_friction_coefficient_flat_plate(reynolds, regime=regime)
    u_tau = velocity_m_s * sqrt(0.5 * friction)
    nu = viscosity_pa_s / density_kg_m3
    return target_y_plus * nu / u_tau, reference


def first_cell_height_from_flow(
    flow: FlowState, *, target_y_plus: float, regime: FlowRegime | None = None
) -> tuple[float, CorrelationRef]:
    """First-cell height using only the flow contract (no separate properties)."""
    _require_positive("TARGET_Y_PLUS", target_y_plus)
    velocity = flow.reference.velocity_m_s
    length = flow.reference.length_m
    if velocity <= 0.0:
        raise TurbulenceValidationError("WALL_REFERENCE_VELOCITY_INVALID")
    friction, reference = skin_friction_coefficient_flat_plate(
        flow.reynolds_number, regime=regime
    )
    u_tau = velocity * sqrt(0.5 * friction)
    nu = velocity * length / flow.reynolds_number
    return target_y_plus * nu / u_tau, reference


@dataclass(frozen=True, slots=True)
class WallTreatmentRequirement:
    """The declared near-wall resolution and layer requirements."""

    surface: str
    mode: WallTreatmentMode
    target_y_plus_min: float
    target_y_plus_max: float
    target_y_plus: float
    first_cell_height_target_m: float
    layer_count: int
    growth_ratio: float
    total_thickness_intent_m: float
    thermal_wall_required: bool
    source: str
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def __post_init__(self) -> None:
        if not self.surface.strip() or not self.source.strip():
            raise TurbulenceValidationError("WALL_REQUIREMENT_IDENTITY_REQUIRED")
        if not 0.0 <= self.target_y_plus_min <= self.target_y_plus <= self.target_y_plus_max:
            raise TurbulenceValidationError("WALL_Y_PLUS_BAND_INVALID")
        if self.first_cell_height_target_m < 0.0 or not isfinite(
            self.first_cell_height_target_m
        ):
            raise TurbulenceValidationError("WALL_FIRST_CELL_HEIGHT_INVALID")
        if self.layer_count < 0 or self.growth_ratio < 1.0:
            raise TurbulenceValidationError("WALL_LAYER_REQUIREMENT_INVALID")
        if self.total_thickness_intent_m < 0.0 or not isfinite(
            self.total_thickness_intent_m
        ):
            raise TurbulenceValidationError("WALL_THICKNESS_INTENT_INVALID")

    def canonical(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "mode": self.mode.value,
            "targetYPlusMin": self.target_y_plus_min,
            "targetYPlusMax": self.target_y_plus_max,
            "targetYPlus": self.target_y_plus,
            "firstCellHeightTargetM": self.first_cell_height_target_m,
            "layerCount": self.layer_count,
            "growthRatio": self.growth_ratio,
            "totalThicknessIntentM": self.total_thickness_intent_m,
            "thermalWallRequired": self.thermal_wall_required,
            "source": self.source,
            "units": {
                "firstCellHeightTargetM": "m",
                "targetYPlus": "1",
                "totalThicknessIntentM": "m",
            },
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


@dataclass(frozen=True, slots=True)
class MeasuredWallResolution:
    """Measured wall resolution from an actual mesh (never assumed)."""

    surface: str
    first_cell_height_m: float | None
    y_plus: float | None
    layer_count: int | None
    growth_ratio: float | None
    total_thickness_m: float | None
    thermal_wall_temperature_k: float | None
    source: str

    def __post_init__(self) -> None:
        if not self.surface.strip() or not self.source.strip():
            raise TurbulenceValidationError("MEASURED_WALL_IDENTITY_REQUIRED")
        for label, value in (
            ("first_cell_height", self.first_cell_height_m),
            ("y_plus", self.y_plus),
            ("total_thickness", self.total_thickness_m),
            ("thermal_wall_temperature", self.thermal_wall_temperature_k),
        ):
            if value is not None and (not isfinite(value) or value < 0.0):
                raise TurbulenceValidationError(f"MEASURED_WALL_{label}_INVALID")
        if self.layer_count is not None and self.layer_count < 0:
            raise TurbulenceValidationError("MEASURED_WALL_LAYER_COUNT_INVALID")
        if self.growth_ratio is not None and self.growth_ratio < 1.0:
            raise TurbulenceValidationError("MEASURED_WALL_GROWTH_RATIO_INVALID")

    def canonical(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "firstCellHeightM": self.first_cell_height_m,
            "yPlus": self.y_plus,
            "layerCount": self.layer_count,
            "growthRatio": self.growth_ratio,
            "totalThicknessM": self.total_thickness_m,
            "thermalWallTemperatureK": self.thermal_wall_temperature_k,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class WallCompatibility:
    """The mesh-vs-requirement verdict, with every check recorded."""

    compatible: bool
    requirement: WallTreatmentRequirement
    measured: MeasuredWallResolution
    checks: dict[str, bool]
    detail: str
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "requirement": self.requirement.canonical(),
            "measured": self.measured.canonical(),
            "checks": dict(self.checks),
            "detail": self.detail,
            "units": {"firstCellHeightM": "m", "yPlus": "1", "totalThicknessM": "m"},
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def wall_requirement_for_mode(
    *,
    surface: str,
    mode: WallTreatmentMode,
    flow: FlowState,
    layer_count: int,
    growth_ratio: float,
    total_thickness_intent_m: float | None = None,
    thermal_wall_required: bool | None = None,
    source: str | None = None,
) -> WallTreatmentRequirement:
    """Declare a wall requirement for a mode and flow state.

    The target y+ band and first-cell height target come from the declared mode
    table; the total thickness intent defaults to the geometric inflation stack
    implied by the first-cell target, growth ratio, and layer count.
    """
    if mode is WallTreatmentMode.NONE:
        first_cell = 0.0
        band = (0.0, 0.0, 0.0)
        reference = BLASIUS_LAMINAR_SKIN_FRICTION
    else:
        band = _WALL_MODE_TARGETS[mode]
        first_cell, reference = first_cell_height_from_flow(
            flow, target_y_plus=band[2], regime=flow.regime
        )
    thickness = (
        total_thickness_intent_m
        if total_thickness_intent_m is not None
        else (
            0.0
            if mode is WallTreatmentMode.NONE
            else inflation_total_thickness(
                first_cell_height_m=first_cell,
                growth_ratio=growth_ratio,
                layer_count=layer_count,
            )
        )
    )
    thermal = (
        thermal_wall_required
        if thermal_wall_required is not None
        else flow.conjugate_heat_transfer
    )
    resolved_source = source or WALL_TREATMENT_SOURCES[mode]
    provenance = analytical_provenance(
        f"turbulence.wall.requirement.{mode.value}",
        {
            "surface": surface,
            "mode": mode.value,
            "flow": flow.canonical(),
            "targetYPlus": band[2],
            "firstCellHeightTargetM": first_cell,
            "layerCount": layer_count,
            "growthRatio": growth_ratio,
            "totalThicknessIntentM": thickness,
            "thermalWallRequired": thermal,
            "source": resolved_source,
        },
        f"skin-friction correlation: {reference.correlation_id}@{reference.version}",
        f"wall mode source: {resolved_source}",
    )
    return WallTreatmentRequirement(
        surface=surface,
        mode=mode,
        target_y_plus_min=band[0],
        target_y_plus_max=band[1],
        target_y_plus=band[2],
        first_cell_height_target_m=first_cell,
        layer_count=layer_count,
        growth_ratio=growth_ratio,
        total_thickness_intent_m=thickness,
        thermal_wall_required=thermal,
        source=resolved_source,
        provenance=provenance,
    )


def wall_requirement_from_boundary_layer(
    intent: BoundaryLayerIntent,
    *,
    surface: str,
    mode: WallTreatmentMode,
    flow: FlowState,
    thermal_wall_required: bool | None = None,
    source: str | None = None,
) -> WallTreatmentRequirement:
    """Bridge a mesh :class:`BoundaryLayerIntent` into a wall requirement."""
    first_cell_m = intent.first_layer_mm * 1.0e-3
    total = inflation_total_thickness(
        first_cell_height_m=first_cell_m,
        growth_ratio=intent.growth_ratio,
        layer_count=intent.layer_count,
    )
    band = _WALL_MODE_TARGETS.get(mode, (0.0, 0.0, 0.0))
    thermal = (
        thermal_wall_required
        if thermal_wall_required is not None
        else flow.conjugate_heat_transfer
    )
    resolved_source = source or (
        f"mesh boundary-layer intent: {WALL_TREATMENT_SOURCES.get(mode, mode.value)}"
    )
    provenance = analytical_provenance(
        f"turbulence.wall.requirement.from-mesh.{mode.value}",
        {
            "surface": surface,
            "mode": mode.value,
            "flow": flow.canonical(),
            "wallPatches": list(intent.wall_patches),
            "firstLayerMm": intent.first_layer_mm,
            "growthRatio": intent.growth_ratio,
            "layerCount": intent.layer_count,
            "source": resolved_source,
        },
        "wall requirement inherited from declared mesh boundary-layer intent",
        f"wall mode source: {resolved_source}",
    )
    return WallTreatmentRequirement(
        surface=surface,
        mode=mode,
        target_y_plus_min=band[0],
        target_y_plus_max=band[1],
        target_y_plus=band[2],
        first_cell_height_target_m=first_cell_m,
        layer_count=intent.layer_count,
        growth_ratio=intent.growth_ratio,
        total_thickness_intent_m=total,
        thermal_wall_required=thermal,
        source=resolved_source,
        provenance=provenance,
    )


def evaluate_wall_treatment(
    requirement: WallTreatmentRequirement, measured: MeasuredWallResolution
) -> WallCompatibility:
    """Check a measured mesh against the wall requirement; fail closed.

    A missing measurement is never a pass: when the mesh backend cannot report
    the wall resolution, compatibility is ``False`` with the reason recorded.
    """
    if requirement.mode is WallTreatmentMode.NONE:
        none_checks = {"no_treatment_requested": True}
        return WallCompatibility(
            compatible=True,
            requirement=requirement,
            measured=measured,
            checks=none_checks,
            detail="no near-wall treatment requested",
            provenance=_wall_provenance(requirement, measured, none_checks),
        )
    measured_available = (
        measured.y_plus is not None or measured.first_cell_height_m is not None
    )
    checks: dict[str, bool] = {"measured_available": measured_available}
    if measured.y_plus is not None:
        checks["y_plus_in_band"] = (
            requirement.target_y_plus_min
            <= measured.y_plus
            <= requirement.target_y_plus_max
        )
    else:
        checks["y_plus_in_band"] = False
    if measured.first_cell_height_m is not None and requirement.first_cell_height_target_m > 0:
        ratio = measured.first_cell_height_m / requirement.first_cell_height_target_m
        checks["first_cell_height_within_factor"] = 1.0 / 3.0 <= ratio <= 3.0
    else:
        checks["first_cell_height_within_factor"] = False
    if measured.layer_count is not None:
        checks["layer_count_sufficient"] = measured.layer_count >= requirement.layer_count
    else:
        checks["layer_count_sufficient"] = False
    if measured.growth_ratio is not None:
        checks["growth_ratio_compatible"] = (
            measured.growth_ratio <= requirement.growth_ratio * 1.05
        )
    else:
        checks["growth_ratio_compatible"] = False
    if measured.total_thickness_m is not None:
        checks["thickness_intent_met"] = (
            measured.total_thickness_m >= requirement.total_thickness_intent_m * 0.9
        )
    else:
        checks["thickness_intent_met"] = False
    if requirement.thermal_wall_required:
        checks["thermal_wall_present"] = measured.thermal_wall_temperature_k is not None
    compatible = all(checks.values())
    failing = sorted(name for name, value in checks.items() if not value)
    detail = (
        "wall resolution compatible"
        if compatible
        else "WALL_RESOLUTION_INCOMPATIBLE:" + ",".join(failing)
    )
    return WallCompatibility(
        compatible=compatible,
        requirement=requirement,
        measured=measured,
        checks=checks,
        detail=detail,
        provenance=_wall_provenance(requirement, measured, checks),
    )


def _wall_provenance(
    requirement: WallTreatmentRequirement,
    measured: MeasuredWallResolution,
    checks: dict[str, bool],
) -> Provenance:
    return analytical_provenance(
        "turbulence.wall.compatibility",
        {
            "requirement": requirement.canonical(),
            "measured": measured.canonical(),
            "checks": dict(sorted(checks.items())),
        },
        "measured mesh wall resolution compared against the declared requirement",
    )


def require_wall_treatment(
    requirement: WallTreatmentRequirement, measured: MeasuredWallResolution
) -> WallCompatibility:
    """Return the compatibility verdict or fail closed when incompatible."""
    compatibility = evaluate_wall_treatment(requirement, measured)
    if not compatibility.compatible:
        raise TurbulenceValidationError(compatibility.detail)
    return compatibility


def roughness_wall_effect(roughness: RoughnessSpec, *, length_m: float) -> float:
    """Return the declared sand-grain ratio ``ks/L`` for solver wall settings."""
    return roughness.sand_grain_ratio(length_m)


__all__ = [
    "BLASIUS_LAMINAR_SKIN_FRICTION",
    "SCHLICHTING_TURBULENT_SKIN_FRICTION",
    "WALL_TREATMENT_SOURCES",
    "CorrelationRef",
    "MeasuredWallResolution",
    "WallCompatibility",
    "WallTreatmentMode",
    "WallTreatmentRequirement",
    "evaluate_wall_treatment",
    "first_cell_height_for_y_plus",
    "first_cell_height_from_flow",
    "inflation_total_thickness",
    "laminar_skin_friction",
    "require_wall_treatment",
    "roughness_wall_effect",
    "skin_friction_coefficient_flat_plate",
    "turbulent_skin_friction",
    "wall_requirement_for_mode",
    "wall_requirement_from_boundary_layer",
]
