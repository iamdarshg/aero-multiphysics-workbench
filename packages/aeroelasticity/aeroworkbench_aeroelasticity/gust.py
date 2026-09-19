"""Atmospheric gust and dynamic-load response for lifting structures.

Discrete (tuned 1-cos) and continuous (Dryden/von Karman) atmospheric gusts are
converted to incremental lift and load factor through a declared wing reference
area and lift-curve slope. The frequency-domain form exposes the gust velocity
PSD so a vehicle or flexible-structure participant can drive a time- or
frequency-domain response without this core encoding a specific airframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import pi
from typing import Any

from aeroworkbench_core.types import Provenance

from .errors import AeroelasticError
from .provenance import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import AeroelasticFidelity, Validity, finite

GRAVITY_M_S2 = 9.80665


class GustKind(StrEnum):
    """Declared atmospheric gust models."""

    DISCRETE_1COS = "discrete-1cos"
    CONTINUOUS_DRYDEN = "continuous-dryden"
    CONTINUOUS_VON_KARMAN = "continuous-von-karman"


@dataclass(frozen=True, slots=True)
class AtmosphericGust:
    """A generic atmospheric gust definition."""

    gust_id: str
    kind: GustKind
    design_gust_velocity_m_s: float
    gradient_distance_m: float | None = None
    scale_length_m: float | None = None
    turbulence_sigma_m_s: float | None = None

    def __post_init__(self) -> None:
        if not self.gust_id.strip():
            raise AeroelasticError("gust_id is required")
        finite(self.design_gust_velocity_m_s, "design_gust_velocity_m_s", positive=True)
        if self.kind is GustKind.DISCRETE_1COS:
            if self.gradient_distance_m is None:
                raise AeroelasticError("discrete gust requires gradient_distance_m")
            finite(self.gradient_distance_m, "gradient_distance_m", positive=True)
        else:
            if self.scale_length_m is None:
                raise AeroelasticError("continuous gust requires scale_length_m")
            finite(self.scale_length_m, "scale_length_m", positive=True)
        if self.turbulence_sigma_m_s is not None:
            finite(self.turbulence_sigma_m_s, "turbulence_sigma_m_s", positive=True)

    @property
    def sigma_m_s(self) -> float:
        if self.turbulence_sigma_m_s is not None:
            return self.turbulence_sigma_m_s
        return self.design_gust_velocity_m_s

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gust_id": self.gust_id,
            "kind": self.kind.value,
            "design_gust_velocity_m_s": self.design_gust_velocity_m_s,
            "gradient_distance_m": self.gradient_distance_m,
            "scale_length_m": self.scale_length_m,
            "turbulence_sigma_m_s": self.turbulence_sigma_m_s,
        }


@dataclass(frozen=True, slots=True)
class GustLoadResult:
    """Incremental gust load and load factor for a lifting structure."""

    gust_id: str
    kind: str
    peak_gust_velocity_m_s: float
    dynamic_pressure_pa: float
    load_increment_n: float
    load_factor_increment: float
    reference_area_m2: float
    fidelity: AeroelasticFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "peak_gust_velocity_m_s": "m/s",
            "dynamic_pressure_pa": "Pa",
            "load_increment_n": "N",
            "load_factor_increment": "dimensionless",
            "reference_area_m2": "m2",
        }

    def dynamic_load_payload(self) -> dict[str, float]:
        """Typed payload for a downstream structural/dynamic participant."""

        return {
            "load_increment_n": self.load_increment_n,
            "load_factor_increment": self.load_factor_increment,
            "peak_gust_velocity_m_s": self.peak_gust_velocity_m_s,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gust_id": self.gust_id,
            "kind": self.kind,
            "peak_gust_velocity_m_s": self.peak_gust_velocity_m_s,
            "dynamic_pressure_pa": self.dynamic_pressure_pa,
            "load_increment_n": self.load_increment_n,
            "load_factor_increment": self.load_factor_increment,
            "reference_area_m2": self.reference_area_m2,
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputs_hash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def dryden_psd_m2_s(
    *,
    kind: GustKind,
    airspeed_m_s: float,
    sigma_m_s: float,
    scale_length_m: float,
    frequency_hz: float,
) -> float:
    """Return the Dryden or von Karman vertical-gust velocity PSD in m^2/s."""

    if kind is GustKind.DISCRETE_1COS:
        raise AeroelasticError("discrete 1-cos gust has no continuous PSD")
    speed = finite(airspeed_m_s, "airspeed_m_s", positive=True)
    sigma = finite(sigma_m_s, "sigma_m_s", positive=True)
    scale = finite(scale_length_m, "scale_length_m", positive=True)
    frequency = finite(frequency_hz, "frequency_hz", minimum=0.0)
    omega = 2.0 * pi * frequency
    ratio = scale * omega / speed
    if kind is GustKind.CONTINUOUS_DRYDEN:
        return float(
            (2.0 * sigma * sigma * scale / (pi * speed))
            * ((1.0 + 3.0 * ratio * ratio) / (1.0 + ratio * ratio) ** 2)
        )
    return float(
        (2.0 * sigma * sigma * scale / (pi * speed))
        * ((1.0 + 8.0 / 3.0 * ratio * ratio) / (1.0 + ratio * ratio) ** (11.0 / 6.0))
    )


def _lift_increment(
    *,
    dynamic_pressure_pa: float,
    wing_area_m2: float,
    lift_curve_slope_per_rad: float,
    mass_kg: float,
    gust_velocity_m_s: float,
    airspeed_m_s: float,
    gravity_m_s2: float,
) -> tuple[float, float]:
    gravity = finite(gravity_m_s2, "gravity_m_s2", positive=True)
    angle = gust_velocity_m_s / airspeed_m_s
    lift = dynamic_pressure_pa * wing_area_m2 * lift_curve_slope_per_rad * angle
    factor = lift / (mass_kg * gravity) if mass_kg > 0.0 else 0.0
    return lift, factor


def _common(
    *,
    airspeed_m_s: float,
    density_kg_m3: float,
    wing_area_m2: float,
    lift_curve_slope_per_rad: float,
    mass_kg: float,
) -> tuple[float, float, float, float, float]:
    speed = finite(airspeed_m_s, "airspeed_m_s", positive=True)
    density = finite(density_kg_m3, "density_kg_m3", positive=True)
    area = finite(wing_area_m2, "wing_area_m2", positive=True)
    slope = finite(lift_curve_slope_per_rad, "lift_curve_slope_per_rad", positive=True)
    mass = finite(mass_kg, "mass_kg", positive=True)
    return speed, density, area, slope, mass


def evaluate_discrete_gust(
    gust: AtmosphericGust,
    *,
    airspeed_m_s: float,
    density_kg_m3: float,
    wing_area_m2: float,
    lift_curve_slope_per_rad: float,
    mass_kg: float,
    gravity_m_s2: float = GRAVITY_M_S2,
) -> GustLoadResult:
    """Quasi-steady tuned 1-cos discrete gust load (no alleviation factor)."""

    if gust.kind is not GustKind.DISCRETE_1COS:
        raise AeroelasticError("evaluate_discrete_gust requires a discrete 1-cos gust")
    speed, density, area, slope, mass = _common(
        airspeed_m_s=airspeed_m_s,
        density_kg_m3=density_kg_m3,
        wing_area_m2=wing_area_m2,
        lift_curve_slope_per_rad=lift_curve_slope_per_rad,
        mass_kg=mass_kg,
    )
    q_dyn = 0.5 * density * speed * speed
    lift, factor = _lift_increment(
        dynamic_pressure_pa=q_dyn,
        wing_area_m2=area,
        lift_curve_slope_per_rad=slope,
        mass_kg=mass,
        gust_velocity_m_s=gust.design_gust_velocity_m_s,
        airspeed_m_s=speed,
        gravity_m_s2=gravity_m_s2,
    )
    checks = {
        "gust_velocity_positive": gust.design_gust_velocity_m_s > 0.0,
        "load_nonnegative": lift >= 0.0,
        "angle_small": (gust.design_gust_velocity_m_s / speed) <= 0.5,
    }
    return GustLoadResult(
        gust_id=gust.gust_id,
        kind=gust.kind.value,
        peak_gust_velocity_m_s=gust.design_gust_velocity_m_s,
        dynamic_pressure_pa=q_dyn,
        load_increment_n=lift,
        load_factor_increment=factor,
        reference_area_m2=area,
        fidelity=AeroelasticFidelity.SCREENING,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="quasi-steady discrete gust load; no alleviation factor applied",
        ),
        provenance=analytical_provenance(
            "aeroelasticity.gust.discrete-1cos",
            {"gust": gust.canonical_payload(), "airspeed_m_s": speed, "density_kg_m3": density},
            assumptions=(
                "quasi-steady lift; unitary gust alleviation factor; small gust angle",
            ),
        ),
    )


def evaluate_continuous_gust(
    gust: AtmosphericGust,
    *,
    airspeed_m_s: float,
    density_kg_m3: float,
    wing_area_m2: float,
    lift_curve_slope_per_rad: float,
    mass_kg: float,
    gravity_m_s2: float = GRAVITY_M_S2,
) -> GustLoadResult:
    """RMS continuous-gust load from the Dryden/von Karman velocity RMS."""

    if gust.kind is GustKind.DISCRETE_1COS:
        raise AeroelasticError("evaluate_continuous_gust requires a continuous gust")
    speed, density, area, slope, mass = _common(
        airspeed_m_s=airspeed_m_s,
        density_kg_m3=density_kg_m3,
        wing_area_m2=wing_area_m2,
        lift_curve_slope_per_rad=lift_curve_slope_per_rad,
        mass_kg=mass_kg,
    )
    q_dyn = 0.5 * density * speed * speed
    sigma = gust.sigma_m_s
    lift, factor = _lift_increment(
        dynamic_pressure_pa=q_dyn,
        wing_area_m2=area,
        lift_curve_slope_per_rad=slope,
        mass_kg=mass,
        gust_velocity_m_s=sigma,
        airspeed_m_s=speed,
        gravity_m_s2=gravity_m_s2,
    )
    checks = {
        "sigma_positive": sigma > 0.0,
        "scale_length_positive": (gust.scale_length_m or 0.0) > 0.0,
        "load_nonnegative": lift >= 0.0,
    }
    return GustLoadResult(
        gust_id=gust.gust_id,
        kind=gust.kind.value,
        peak_gust_velocity_m_s=sigma,
        dynamic_pressure_pa=q_dyn,
        load_increment_n=lift,
        load_factor_increment=factor,
        reference_area_m2=area,
        fidelity=AeroelasticFidelity.REDUCED,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="continuous gust RMS load; no frequency-dependent transfer applied",
        ),
        provenance=analytical_provenance(
            "aeroelasticity.gust.continuous-spectrum",
            {
                "gust": gust.canonical_payload(),
                "airspeed_m_s": speed,
                "density_kg_m3": density,
            },
            assumptions=(
                "Dryden/von Karman velocity RMS; rigid-body quasi-steady transfer",
            ),
        ),
    )


__all__ = [
    "GRAVITY_M_S2",
    "AtmosphericGust",
    "GustKind",
    "GustLoadResult",
    "dryden_psd_m2_s",
    "evaluate_continuous_gust",
    "evaluate_discrete_gust",
]
