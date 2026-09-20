"""Bounded analytical lateral/yaw ground dynamics.

This is a declared tire-and-runway screening model, not a native multibody solve.
It reports violated constraints instead of hiding an infeasible ground scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, tan
from typing import Any

from .contracts import LandingGearFidelity, ResultMeta, result_meta
from .errors import LandingGearError, finite


@dataclass(frozen=True, slots=True)
class GroundLateralScenario:
    scenario_id: str
    mass_kg: float
    speed_m_s: float
    wheelbase_m: float
    track_m: float
    crosswind_speed_m_s: float
    steer_angle_rad: float
    normal_force_n: float
    cornering_stiffness_n_per_rad: float
    maximum_yaw_rate_rad_s: float
    maximum_lateral_acceleration_m_s2: float

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise LandingGearError("ground.scenario_id is required")
        finite(self.mass_kg, "ground.mass_kg", positive=True)
        finite(self.speed_m_s, "ground.speed_m_s", positive=True)
        finite(self.wheelbase_m, "ground.wheelbase_m", positive=True)
        finite(self.track_m, "ground.track_m", positive=True)
        finite(self.crosswind_speed_m_s, "ground.crosswind_speed_m_s")
        finite(self.steer_angle_rad, "ground.steer_angle_rad")
        finite(self.normal_force_n, "ground.normal_force_n", positive=True)
        finite(
            self.cornering_stiffness_n_per_rad,
            "ground.cornering_stiffness_n_per_rad",
            positive=True,
        )
        finite(
            self.maximum_yaw_rate_rad_s, "ground.maximum_yaw_rate_rad_s", positive=True
        )
        finite(
            self.maximum_lateral_acceleration_m_s2,
            "ground.maximum_lateral_acceleration_m_s2",
            positive=True,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class GroundLateralResult:
    scenario_id: str
    crosswind_sideslip_rad: float
    combined_tire_slip_rad: float
    lateral_force_n: float
    lateral_acceleration_m_s2: float
    yaw_rate_rad_s: float
    friction_capacity_n: float
    infeasibility_constraints: tuple[str, ...]
    feasible: bool
    meta: ResultMeta

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "crosswindSideslipRad": self.crosswind_sideslip_rad,
            "combinedTireSlipRad": self.combined_tire_slip_rad,
            "lateralForceN": self.lateral_force_n,
            "lateralAccelerationMS2": self.lateral_acceleration_m_s2,
            "yawRateRadS": self.yaw_rate_rad_s,
            "frictionCapacityN": self.friction_capacity_n,
            "infeasibilityConstraints": list(self.infeasibility_constraints),
            "feasible": self.feasible,
            "meta": self.meta.canonical(),
        }


def simulate_ground_lateral(scenario: GroundLateralScenario) -> GroundLateralResult:
    """Evaluate crosswind/steering demand against declared tire limits."""

    wind_slip = atan2(scenario.crosswind_speed_m_s, scenario.speed_m_s)
    combined_slip = wind_slip - scenario.steer_angle_rad
    tire_force = scenario.cornering_stiffness_n_per_rad * abs(combined_slip)
    yaw_rate = scenario.speed_m_s * tan(scenario.steer_angle_rad) / scenario.wheelbase_m
    steering_force = scenario.mass_kg * scenario.speed_m_s * abs(yaw_rate)
    lateral_force = tire_force + steering_force
    friction_capacity = 0.8 * scenario.normal_force_n
    lateral_acceleration = lateral_force / scenario.mass_kg
    constraints: list[str] = []
    if lateral_force > friction_capacity:
        constraints.append("LATERAL_FORCE_CAPACITY")
    if abs(yaw_rate) > scenario.maximum_yaw_rate_rad_s:
        constraints.append("YAW_RATE_LIMIT")
    if lateral_acceleration > scenario.maximum_lateral_acceleration_m_s2:
        constraints.append("LATERAL_ACCELERATION_LIMIT")
    checks = {
        "lateral_force_capacity": "LATERAL_FORCE_CAPACITY" not in constraints,
        "yaw_rate_limit": "YAW_RATE_LIMIT" not in constraints,
        "lateral_acceleration_limit": "LATERAL_ACCELERATION_LIMIT" not in constraints,
    }
    meta = result_meta(
        model="vehicle-systems.landing-gear.ground-lateral-dynamics",
        inputs=scenario.canonical_payload(),
        valid=not constraints,
        checks=checks,
        detail="bounded crosswind and steering tire/cornering screening",
        fidelity=LandingGearFidelity.GROUND_TRANSIENT,
        assumptions=(
            "steady-speed bicycle yaw relation",
            "linear tire cornering with declared friction-circle capacity",
            "no native multibody or transient tire relaxation is claimed",
        ),
    )
    return GroundLateralResult(
        scenario_id=scenario.scenario_id,
        crosswind_sideslip_rad=wind_slip,
        combined_tire_slip_rad=combined_slip,
        lateral_force_n=lateral_force,
        lateral_acceleration_m_s2=lateral_acceleration,
        yaw_rate_rad_s=yaw_rate,
        friction_capacity_n=friction_capacity,
        infeasibility_constraints=tuple(constraints),
        feasible=not constraints,
        meta=meta,
    )


__all__ = ["GroundLateralResult", "GroundLateralScenario", "simulate_ground_lateral"]
