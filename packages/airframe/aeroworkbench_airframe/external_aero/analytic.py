"""Analytical/screening external-aerodynamics level.

Two closed-form screening models share the typed result contract:

* :func:`drag_buildup` accumulates a parasite-drag coefficient from declared
  component wetted areas, form and interference factors and a flat-plate skin
  friction coefficient evaluated at the reference Reynolds number;
* :func:`evaluate_analytic` applies finite-wing lifting-line screening to the
  section model seam: 3-D lift-curve slope, zero-lift angle, induced drag with
  a declared Oswald-efficiency correlation, and the section zero-lift pitching
  moment.

Nothing here is a solver; every quantity is a declared screening correlation
with its assumptions recorded in provenance and its limits on the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log10, pi

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .case import ExternalAeroCase
from .contracts import (
    ANALYTICAL_VALIDITY_LIMITS,
    D_CD_D_ALPHA,
    D_CL_D_ALPHA,
    D_CM_D_ALPHA,
    AeroCoefficients,
    AeroDerivatives,
    AeroReference,
    ExternalAeroFidelity,
    ExternalAeroResult,
    evaluate_aero_validity,
)
from .errors import ExternalAeroValidationError

ANALYTIC_MODEL = "airframe.external_aero.lifting-line-screening"
_OSWALD_SOURCE = "Raymer straight-wing Oswald-efficiency correlation"
_FLAT_PLATE_SOURCE = "Prandtl-Schlichting turbulent flat-plate skin friction"


@dataclass(frozen=True, slots=True)
class DragComponent:
    """One parasite-drag build-up component (all areas in square metres)."""

    name: str
    wetted_area_m2: float
    form_factor: float
    interference_factor: float = 1.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ExternalAeroValidationError("DRAG_COMPONENT_NAME_REQUIRED")
        for label, value in (
            ("WETTED_AREA", self.wetted_area_m2),
            ("FORM_FACTOR", self.form_factor),
            ("INTERFERENCE_FACTOR", self.interference_factor),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ExternalAeroValidationError(f"DRAG_COMPONENT_{label}_INVALID")

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "wettedAreaM2": self.wetted_area_m2,
            "formFactor": self.form_factor,
            "interferenceFactor": self.interference_factor,
        }


def flat_plate_friction_coefficient(reynolds_number: float) -> float:
    """Prandtl-Schlichting turbulent flat-plate skin-friction coefficient."""

    if not isfinite(reynolds_number) or reynolds_number <= 1.0:
        raise ExternalAeroValidationError("FRICTION_REYNOLDS_INVALID")
    return float(0.455 / log10(reynolds_number) ** 2.58)


def compressibility_friction_factor(mach_number: float) -> float:
    """Raymer turbulent flat-plate compressibility correction factor."""

    if not isfinite(mach_number) or mach_number < 0.0:
        raise ExternalAeroValidationError("FRICTION_MACH_INVALID")
    return float((1.0 + 0.144 * mach_number * mach_number) ** -0.65)


def drag_buildup(
    reference: AeroReference,
    components: tuple[DragComponent, ...],
    *,
    miscellaneous_drag: float = 0.0,
) -> float:
    """Parasite drag coefficient from declared component build-up factors."""

    friction = flat_plate_friction_coefficient(reference.reynolds_number)
    friction *= compressibility_friction_factor(reference.mach_number)
    total = 0.0
    for component in components:
        total += (
            friction
            * component.form_factor
            * component.interference_factor
            * component.wetted_area_m2
            / reference.area_m2
        )
    if not isfinite(miscellaneous_drag) or miscellaneous_drag < 0.0:
        raise ExternalAeroValidationError("MISCELLANEOUS_DRAG_INVALID")
    return total + miscellaneous_drag


def oswald_efficiency(aspect_ratio: float) -> float:
    """Declared straight-wing Oswald-efficiency correlation, bounded to [0.5, 1]."""

    if not isfinite(aspect_ratio) or aspect_ratio <= 0.0:
        raise ExternalAeroValidationError("OSWALD_ASPECT_RATIO_INVALID")
    if aspect_ratio <= 1.0:
        return 0.7
    efficiency = 1.78 * (1.0 - 0.045 * aspect_ratio**0.68) - 0.64
    return float(min(max(efficiency, 0.5), 1.0))


def finite_wing_lift_curve_slope(
    section_slope_per_rad: float, aspect_ratio: float, efficiency: float
) -> float:
    """Finite-wing lifting-line lift-curve slope in per-radian units."""

    if not isfinite(section_slope_per_rad) or section_slope_per_rad <= 0.0:
        raise ExternalAeroValidationError("SECTION_SLOPE_INVALID")
    return section_slope_per_rad / (
        1.0 + section_slope_per_rad / (pi * aspect_ratio * efficiency)
    )


def evaluate_analytic(
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    drag_components: tuple[DragComponent, ...] = (),
    miscellaneous_drag: float = 0.0,
) -> ExternalAeroResult:
    """Analytical lifting-line screening result for the case."""

    geometry = case.geometry_reference()
    aspect_ratio = geometry.span_m**2 / geometry.area_m2
    section = case.section_model(case.surfaces[0].surface_id)
    efficiency = oswald_efficiency(aspect_ratio)
    slope = finite_wing_lift_curve_slope(section.lift_curve_slope_per_rad, aspect_ratio, efficiency)
    alpha0 = section.zero_lift_angle_deg
    lift = slope * (reference.alpha_deg - alpha0) * pi / 180.0
    parasite = drag_buildup(
        reference, drag_components, miscellaneous_drag=miscellaneous_drag
    )
    if case.bodies:
        parasite += 0.0025 * case.body_volume_m3 / max(reference.area_m2, 1e-9)
    induced = lift * lift / (pi * aspect_ratio * efficiency)
    drag = parasite + induced
    pitching = section.quarter_chord_moment_coefficient()
    slope_per_deg = slope * pi / 180.0
    derivatives = AeroDerivatives(
        values=(
            (D_CL_D_ALPHA, slope_per_deg),
            (D_CD_D_ALPHA, 2.0 * lift * slope_per_deg / (pi * aspect_ratio * efficiency)),
            (D_CM_D_ALPHA, 0.0),
        ),
        method="lifting-line-screening",
        step_deg=0.5,
    )
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=ANALYTIC_MODEL,
        model_version="1.0.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={
            "case": case.digest,
            "reference": reference.canonical(),
            "dragComponents": [component.canonical() for component in drag_components],
            "miscellaneousDrag": miscellaneous_drag,
        },
        assumptions=(
            "finite-wing lifting-line screening; attached subsonic flow",
            f"Oswald efficiency: {_OSWALD_SOURCE}",
            f"skin friction: {_FLAT_PLATE_SOURCE}",
            "moment reference assumed at the aerodynamic center",
        ),
    )
    return ExternalAeroResult(
        result_id=f"{case.case_id}-analytic",
        fidelity=ExternalAeroFidelity.ANALYTICAL,
        source=ResultSource.ANALYTICAL,
        reference=reference,
        coefficients=AeroCoefficients(
            lift=lift, drag=drag, side=0.0, roll=0.0, pitch=pitching, yaw=0.0
        ),
        derivatives=derivatives,
        validity=evaluate_aero_validity(reference, ANALYTICAL_VALIDITY_LIMITS),
        provenance=provenance,
    )


__all__ = [
    "ANALYTIC_MODEL",
    "DragComponent",
    "compressibility_friction_factor",
    "drag_buildup",
    "evaluate_analytic",
    "finite_wing_lift_curve_slope",
    "flat_plate_friction_coefficient",
    "oswald_efficiency",
]
