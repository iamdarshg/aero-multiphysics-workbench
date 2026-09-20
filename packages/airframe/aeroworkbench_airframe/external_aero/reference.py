"""Atmosphere-aware aerodynamic reference construction.

The reference reuses the shared fluid/atmosphere system so density, speed of
sound and viscosity cannot disagree with the rest of the platform. A reference
built from a standard atmosphere is labelled ``ISA@1``; an explicit-conditions
reference is labelled ``declared``. Reynolds and Mach are always evaluated from
the reference state, never supplied independently.
"""

from __future__ import annotations

from aeroworkbench_fluid_properties import (
    WorkingFluid,
    dry_air_fluid,
    standard_atmosphere,
)

from .case import GeometryReference
from .contracts import AeroReference
from .errors import ExternalAeroValidationError


def reference_from_conditions(
    geometry: GeometryReference,
    *,
    density_kg_m3: float,
    velocity_m_s: float,
    speed_of_sound_m_s: float,
    viscosity_pa_s: float,
    alpha_deg: float = 0.0,
    beta_deg: float = 0.0,
    angular_rates: tuple[float, float, float] = (0.0, 0.0, 0.0),
    altitude_m: float | None = None,
    atmosphere_model: str = "declared",
) -> AeroReference:
    """Build a reference from explicit atmospheric conditions."""

    return AeroReference(
        area_m2=geometry.area_m2,
        span_m=geometry.span_m,
        mean_chord_m=geometry.mean_chord_m,
        moment_reference_m=geometry.moment_reference_m,
        density_kg_m3=density_kg_m3,
        velocity_m_s=velocity_m_s,
        speed_of_sound_m_s=speed_of_sound_m_s,
        viscosity_pa_s=viscosity_pa_s,
        alpha_deg=alpha_deg,
        beta_deg=beta_deg,
        angular_rates=angular_rates,
        altitude_m=altitude_m,
        atmosphere_model=atmosphere_model,
        source=atmosphere_model,
    )


def reference_from_altitude(
    geometry: GeometryReference,
    *,
    altitude_m: float,
    velocity_m_s: float,
    alpha_deg: float = 0.0,
    beta_deg: float = 0.0,
    angular_rates: tuple[float, float, float] = (0.0, 0.0, 0.0),
    temperature_offset_k: float = 0.0,
    fluid: WorkingFluid | None = None,
) -> AeroReference:
    """Build a reference from a standard-atmosphere evaluation at one altitude."""

    working_fluid = fluid or dry_air_fluid()
    model = standard_atmosphere(working_fluid)
    state = model.evaluate(
        altitude_m=altitude_m, temperature_offset_k=temperature_offset_k
    )
    transport = working_fluid.transport
    if transport is None:
        raise ExternalAeroValidationError("REFERENCE_FLUID_HAS_NO_TRANSPORT_MODEL")
    viscosity = transport.viscosity_pa_s(state.temperature_k)
    return AeroReference(
        area_m2=geometry.area_m2,
        span_m=geometry.span_m,
        mean_chord_m=geometry.mean_chord_m,
        moment_reference_m=geometry.moment_reference_m,
        density_kg_m3=state.density_kg_m3,
        velocity_m_s=velocity_m_s,
        speed_of_sound_m_s=state.speed_of_sound_m_s,
        viscosity_pa_s=viscosity,
        alpha_deg=alpha_deg,
        beta_deg=beta_deg,
        angular_rates=angular_rates,
        altitude_m=altitude_m,
        atmosphere_model=f"{model.model_id}@{model.revision}",
        source=f"{model.source}; {state.fluid_identity}",
    )


__all__ = ["reference_from_altitude", "reference_from_conditions"]
