"""Runway surface, friction, rolling resistance, steering, and braking seams.

The surface is a declared property set: a peak braking friction coefficient and
a rolling-resistance coefficient. Every force is a closed-form function of the
instantaneous normal load and the declared coefficient; no distance heuristic is
stored. Unknown surfaces fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import atan, atan2, sin, tan
from typing import Any

from .contracts import LG_UNITS, LandingGearFidelity, result_meta
from .errors import LandingGearError, finite


class RunwaySurface(StrEnum):
    """Declared runway/ground surface taxonomy."""

    DRY_CONCRETE = "dry-concrete"
    DRY_ASPHALT = "dry-asphalt"
    WET_CONCRETE = "wet-concrete"
    WET_ASPHALT = "wet-asphalt"
    SNOW = "snow"
    ICE = "ice"
    GRASS = "grass"
    SOFT_FIELD = "soft-field"


_SURFACE_TABLE: dict[RunwaySurface, tuple[float, float]] = {
    RunwaySurface.DRY_CONCRETE: (0.80, 0.015),
    RunwaySurface.DRY_ASPHALT: (0.75, 0.020),
    RunwaySurface.WET_CONCRETE: (0.55, 0.020),
    RunwaySurface.WET_ASPHALT: (0.50, 0.025),
    RunwaySurface.SNOW: (0.30, 0.040),
    RunwaySurface.ICE: (0.10, 0.010),
    RunwaySurface.GRASS: (0.35, 0.060),
    RunwaySurface.SOFT_FIELD: (0.25, 0.100),
}


@dataclass(frozen=True, slots=True)
class RunwaySpec:
    """A declared runway: surface, available length, and slope."""

    runway_id: str
    surface: RunwaySurface
    length_m: float
    slope_deg: float = 0.0

    def __post_init__(self) -> None:
        if not self.runway_id.strip():
            raise LandingGearError("runway.runway_id is required")
        finite(self.length_m, "runway.length_m", positive=True)
        finite(self.slope_deg, "runway.slope_deg")

    @property
    def braking_friction_coefficient(self) -> float:
        return _SURFACE_TABLE[self.surface][0]

    @property
    def rolling_resistance_coefficient(self) -> float:
        return _SURFACE_TABLE[self.surface][1]

    @property
    def slope_rad(self) -> float:
        return self.slope_deg * 0.017453292519943295

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "runwayId": self.runway_id,
            "surface": self.surface.value,
            "lengthM": self.length_m,
            "slopeDeg": self.slope_deg,
            "brakingFrictionCoefficient": self.braking_friction_coefficient,
            "rollingResistanceCoefficient": self.rolling_resistance_coefficient,
        }


@dataclass(frozen=True, slots=True)
class FrictionResult:
    """A closed-form friction force with the load and coefficient it used."""

    kind: str
    normal_force_n: float
    friction_coefficient: float
    force_n: float
    available_force_n: float
    saturated: bool
    unit: str = "N"

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "normalForceN": self.normal_force_n,
            "frictionCoefficient": self.friction_coefficient,
            "forceN": self.force_n,
            "availableForceN": self.available_force_n,
            "saturated": self.saturated,
        }


def _friction(
    kind: str, normal_force_n: float, coefficient: float, *, available_n: float
) -> FrictionResult:
    normal = finite(normal_force_n, "normal_force_n", minimum=0.0)
    mu = finite(coefficient, "coefficient", minimum=0.0)
    available = finite(available_n, "available_n", minimum=0.0)
    requested = mu * normal
    force = min(requested, available)
    return FrictionResult(
        kind=kind,
        normal_force_n=normal,
        friction_coefficient=mu,
        force_n=force,
        available_force_n=available,
        saturated=requested > available,
    )


def rolling_resistance_force(normal_force_n: float, coefficient: float) -> FrictionResult:
    """Rolling resistance opposes motion; bounded by the normal force."""

    return _friction(
        "rolling-resistance", normal_force_n, coefficient, available_n=float("inf")
    )


def braking_force(
    normal_force_n: float, coefficient: float, *, available_force_n: float = float("inf")
) -> FrictionResult:
    """Braking friction, optionally capped by an anti-skid/torque limit."""

    return _friction("braking", normal_force_n, coefficient, available_n=available_force_n)


def side_friction_force(
    normal_force_n: float, sideslip_rad: float, cornering_stiffness_n_per_rad: float
) -> FrictionResult:
    """Linear cornering (side) force saturated by the friction circle."""

    normal = finite(normal_force_n, "normal_force_n", minimum=0.0)
    sideslip = finite(sideslip_rad, "sideslip_rad")
    stiffness = finite(cornering_stiffness_n_per_rad, "cornering_stiffness_n_per_rad", minimum=0.0)
    requested = stiffness * sin(sideslip)
    available = 0.8 * normal
    force = max(-available, min(requested, available))
    return FrictionResult(
        kind="side",
        normal_force_n=normal,
        friction_coefficient=stiffness,
        force_n=force,
        available_force_n=available,
        saturated=abs(requested) >= available,
    )


def steering_turn_rate_rad_s(speed_m_s: float, wheelbase_m: float, steer_angle_rad: float) -> float:
    """Low-speed bicycle-model yaw rate."""

    speed = finite(speed_m_s, "speed_m_s", minimum=0.0)
    wheelbase = finite(wheelbase_m, "wheelbase_m", positive=True)
    angle = finite(steer_angle_rad, "steer_angle_rad")
    if abs(angle) > 1.55:
        raise LandingGearError("STEER_ANGLE_OUT_OF_RANGE")
    return speed * tan(angle) / wheelbase


def steer_angle_for_radius_rad(radius_m: float, wheelbase_m: float) -> float:
    """Steer angle that produces a turn of the given radius."""

    radius = finite(radius_m, "radius_m", positive=True)
    wheelbase = finite(wheelbase_m, "wheelbase_m", positive=True)
    return atan(wheelbase / radius)


def crosswind_sideslip_rad(speed_m_s: float, crosswind_speed_m_s: float) -> float:
    """Ground sideslip angle induced by a crosswind component."""

    speed = finite(speed_m_s, "speed_m_s", positive=True)
    crosswind = finite(crosswind_speed_m_s, "crosswind_speed_m_s")
    return atan2(crosswind, speed)


def crosswind_side_force(
    normal_force_n: float,
    speed_m_s: float,
    crosswind_speed_m_s: float,
    cornering_stiffness_n_per_rad: float,
) -> FrictionResult:
    """Ground side force from a crosswind through the cornering model."""

    sideslip = crosswind_sideslip_rad(speed_m_s, crosswind_speed_m_s)
    return side_friction_force(normal_force_n, sideslip, cornering_stiffness_n_per_rad)


def friction_result_meta(runway: RunwaySpec) -> dict[str, Any]:
    return result_meta(
        model="vehicle-systems.landing-gear.runway-friction",
        inputs=runway.canonical_payload(),
        valid=True,
        fidelity=LandingGearFidelity.ANALYTICAL,
        detail="declared surface friction and rolling resistance",
        units=LG_UNITS,
    ).canonical()


__all__ = [
    "FrictionResult",
    "RunwaySpec",
    "RunwaySurface",
    "braking_force",
    "friction_result_meta",
    "rolling_resistance_force",
    "side_friction_force",
    "steer_angle_for_radius_rad",
    "steering_turn_rate_rad_s",
]
