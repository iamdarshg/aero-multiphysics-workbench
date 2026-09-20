"""Bounded time-domain takeoff, landing, and rejected-takeoff dynamics.

Distances emerge from thrust, drag, lift, mass, rolling resistance, and braking
acting on a point-mass runway model; no takeoff/landing distance heuristic is
stored. A declared drag polar and thrust lapse define the aerodynamics, and the
surface friction comes from the runway contract. Integration is deterministic
fixed-step (Heun/RK2) with zero-order-held inputs and a recorded receipt.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import asin, cos, pi, sin
from typing import Any

from aeroworkbench_fluid_properties import ISA
from aeroworkbench_system_dynamics import (
    IntegrationMethod,
    IntegratorReceipt,
    TimeSeries,
    advance,
)

from .contracts import LandingGearFidelity, ResultMeta, result_meta
from .errors import LimitExceeded, finite
from .friction import RunwaySpec
from .geometry import LandingGearAssembly

_GRAVITY = 9.80665
_MAX_CLIMB_ANGLE = 0.5


def isa_density_kg_m3(altitude_m: float) -> float:
    """Density from the platform ISA model at a declared altitude."""

    altitude = finite(altitude_m, "altitude_m", minimum=0.0)
    return ISA.evaluate(altitude_m=altitude).density_kg_m3


@dataclass(frozen=True, slots=True)
class DragPolar:
    """A quadratic drag polar with a linear lift curve."""

    reference_area_m2: float
    cl0: float
    cl_alpha_per_rad: float
    cd0: float
    aspect_ratio: float
    oswald_efficiency: float = 0.8

    def __post_init__(self) -> None:
        finite(self.reference_area_m2, "polar.reference_area_m2", positive=True)
        finite(self.cl0, "polar.cl0")
        finite(self.cl_alpha_per_rad, "polar.cl_alpha_per_rad", positive=True)
        finite(self.cd0, "polar.cd0", minimum=0.0)
        finite(self.aspect_ratio, "polar.aspect_ratio", positive=True)
        finite(self.oswald_efficiency, "polar.oswald_efficiency", positive=True)

    def lift_coefficient(self, alpha_rad: float) -> float:
        return self.cl0 + self.cl_alpha_per_rad * finite(alpha_rad, "alpha_rad")

    def drag_coefficient(self, lift_coefficient: float) -> float:
        cl = finite(lift_coefficient, "lift_coefficient")
        return self.cd0 + cl * cl / (pi * self.aspect_ratio * self.oswald_efficiency)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "referenceAreaM2": self.reference_area_m2,
            "cl0": self.cl0,
            "clAlphaPerRad": self.cl_alpha_per_rad,
            "cd0": self.cd0,
            "aspectRatio": self.aspect_ratio,
            "oswaldEfficiency": self.oswald_efficiency,
        }


@dataclass(frozen=True, slots=True)
class ThrustModel:
    """Thrust that lapses linearly with speed and scales with throttle."""

    static_thrust_n: float
    lapse_per_m_s: float = 0.0

    def __post_init__(self) -> None:
        finite(self.static_thrust_n, "thrust.static_thrust_n", positive=True)
        finite(self.lapse_per_m_s, "thrust.lapse_per_m_s", minimum=0.0)

    def thrust_n(self, speed_m_s: float, throttle: float = 1.0) -> float:
        speed = finite(speed_m_s, "speed_m_s", minimum=0.0)
        setting = finite(throttle, "throttle", minimum=0.0, maximum=1.0)
        return max(0.0, self.static_thrust_n * (1.0 - self.lapse_per_m_s * speed)) * setting

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "staticThrustN": self.static_thrust_n,
            "lapsePerMS": self.lapse_per_m_s,
        }


@dataclass(frozen=True, slots=True)
class GroundVehicleModel:
    """Declared point-mass aircraft parameters for ground/transition dynamics."""

    vehicle_id: str
    mass_kg: float
    polar: DragPolar
    thrust: ThrustModel
    cl_ground: float
    cl_max: float
    rotation_alpha_rad: float
    rotation_speed_m_s: float
    screen_height_m: float
    density_kg_m3: float
    gravity_m_s2: float = _GRAVITY

    def __post_init__(self) -> None:
        if not self.vehicle_id.strip():
            raise LimitExceeded("vehicle.vehicle_id is required")
        finite(self.mass_kg, "vehicle.mass_kg", positive=True)
        finite(self.cl_ground, "vehicle.cl_ground")
        finite(self.cl_max, "vehicle.cl_max", positive=True)
        if self.cl_max < self.cl_ground:
            raise LimitExceeded("vehicle.cl_max must be >= cl_ground")
        finite(self.rotation_alpha_rad, "vehicle.rotation_alpha_rad")
        finite(self.rotation_speed_m_s, "vehicle.rotation_speed_m_s", positive=True)
        finite(self.screen_height_m, "vehicle.screen_height_m", positive=True)
        finite(self.density_kg_m3, "vehicle.density_kg_m3", positive=True)
        finite(self.gravity_m_s2, "vehicle.gravity_m_s2", positive=True)

    @property
    def weight_n(self) -> float:
        return self.mass_kg * self.gravity_m_s2

    def lift_n(self, speed_m_s: float, lift_coefficient: float) -> float:
        speed = max(finite(speed_m_s, "speed_m_s"), 0.0)
        return (
            0.5
            * self.density_kg_m3
            * speed
            * speed
            * self.polar.reference_area_m2
            * lift_coefficient
        )

    def drag_n(self, speed_m_s: float, lift_coefficient: float) -> float:
        speed = max(finite(speed_m_s, "speed_m_s"), 0.0)
        cd = self.polar.drag_coefficient(lift_coefficient)
        return 0.5 * self.density_kg_m3 * speed * speed * self.polar.reference_area_m2 * cd

    def liftoff_lift_coefficient(self) -> float:
        return min(self.cl_max, self.polar.lift_coefficient(self.rotation_alpha_rad))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "vehicleId": self.vehicle_id,
            "massKg": self.mass_kg,
            "polar": self.polar.canonical_payload(),
            "thrust": self.thrust.canonical_payload(),
            "clGround": self.cl_ground,
            "clMax": self.cl_max,
            "rotationAlphaRad": self.rotation_alpha_rad,
            "rotationSpeedMS": self.rotation_speed_m_s,
            "screenHeightM": self.screen_height_m,
            "densityKgM3": self.density_kg_m3,
            "gravityMS2": self.gravity_m_s2,
        }


def _series(name: str, unit: str, times: list[float], values: list[float]) -> TimeSeries:
    return TimeSeries(name=name, unit=unit, times_s=tuple(times), values=tuple(values))


def _braking_capacity_n(assembly: LandingGearAssembly | None) -> float | None:
    if assembly is None:
        return None
    total = 0.0
    for leg in assembly.legs:
        if leg.brake is not None and leg.wheel is not None:
            total += leg.brake.max_braking_force_n(leg.wheel.radius.value_si)
    return total if total > 0.0 else None


@dataclass(frozen=True, slots=True)
class TakeoffResult:
    """Takeoff ground roll plus climb to screen height."""

    scenario_id: str
    ground_roll_distance_m: float
    air_distance_m: float
    takeoff_distance_m: float
    liftoff_speed_m_s: float
    rotation_speed_m_s: float
    total_time_s: float
    distance_series: TimeSeries
    speed_series: TimeSeries
    height_series: TimeSeries
    receipt: IntegratorReceipt
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {"distance": "m", "speed": "m/s", "time": "s"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "groundRollDistanceM": self.ground_roll_distance_m,
            "airDistanceM": self.air_distance_m,
            "takeoffDistanceM": self.takeoff_distance_m,
            "liftoffSpeedMS": self.liftoff_speed_m_s,
            "rotationSpeedMS": self.rotation_speed_m_s,
            "totalTimeS": self.total_time_s,
            "meta": self.meta.canonical(),
        }


def simulate_takeoff(
    model: GroundVehicleModel,
    *,
    runway: RunwaySpec,
    scenario_id: str = "takeoff",
    throttle: float = 1.0,
    step_size_s: float = 0.01,
    max_time_s: float = 180.0,
) -> TakeoffResult:
    """Integrate a takeoff; distance emerges from the instantaneous force balance."""

    step = finite(step_size_s, "step_size_s", positive=True)
    horizon = finite(max_time_s, "max_time_s", positive=True)
    setting = finite(throttle, "throttle", minimum=0.0, maximum=1.0)
    lift_cl = model.liftoff_lift_coefficient()
    mass = model.mass_kg
    weight = model.weight_n
    slope = runway.slope_rad
    mu_roll = runway.rolling_resistance_coefficient
    phase = {"rotated": False, "airborne": False}

    def derivative(
        time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> Mapping[str, float]:
        del time_s, inputs
        speed = max(state["speed"], 0.0)
        cl = lift_cl if phase["rotated"] else model.cl_ground
        lift = model.lift_n(speed, cl)
        drag = model.drag_n(speed, cl)
        thrust = model.thrust.thrust_n(speed, setting)
        if not phase["airborne"]:
            normal = max(weight - lift, 0.0)
            acceleration = (thrust - drag - mu_roll * normal - weight * sin(slope)) / mass
            return {"speed": acceleration, "distance": speed, "height": 0.0}
        excess = max(-0.5, min((thrust - drag) / weight, _MAX_CLIMB_ANGLE))
        gamma = asin(excess)
        acceleration = (thrust - drag - weight * sin(gamma)) / mass
        return {
            "speed": acceleration,
            "distance": speed * cos(gamma),
            "height": speed * sin(gamma),
        }

    state: dict[str, float] = {"speed": 0.0, "distance": 0.0, "height": 0.0}
    times: list[float] = [0.0]
    speeds: list[float] = [0.0]
    distances: list[float] = [0.0]
    heights: list[float] = [0.0]
    time = 0.0
    steps = 0
    ground_roll = 0.0
    liftoff_speed = 0.0
    max_steps = int(horizon / step) + 1
    while steps < max_steps:
        speed = max(state["speed"], 0.0)
        if not phase["rotated"] and speed >= model.rotation_speed_m_s:
            phase["rotated"] = True
        if not phase["airborne"] and phase["rotated"]:
            cl = lift_cl
            if model.lift_n(speed, cl) >= weight:
                phase["airborne"] = True
                ground_roll = state["distance"]
                liftoff_speed = speed
        if phase["airborne"] and state["height"] >= model.screen_height_m:
            break
        state = dict(advance(derivative, IntegrationMethod.HEUN, time, state, step, {}))
        state["speed"] = max(state["speed"], 0.0)
        state["height"] = max(state["height"], 0.0)
        time += step
        steps += 1
        times.append(time)
        speeds.append(state["speed"])
        distances.append(state["distance"])
        heights.append(state["height"])
    if not phase["airborne"]:
        raise LimitExceeded("TAKEOFF_DID_NOT_LIFT_OFF_WITHIN_HORIZON")

    takeoff_distance = state["distance"]
    receipt = IntegratorReceipt(
        method=IntegrationMethod.HEUN.value,
        step_size_s=step,
        steps=steps,
        duration_s=time,
        recorded_points=len(times),
    )
    meta = result_meta(
        model="vehicle-systems.landing-gear.takeoff-dynamics",
        inputs={
            "vehicle": model.canonical_payload(),
            "runway": runway.canonical_payload(),
            "throttle": setting,
            "stepSizeS": step,
        },
        valid=takeoff_distance > ground_roll,
        checks={
            "lifted_off": liftoff_speed > 0.0,
            "positive_air_distance": takeoff_distance > ground_roll,
        },
        detail="bounded ground roll + climb to screen height",
        fidelity=LandingGearFidelity.GROUND_TRANSIENT,
        assumptions=(
            "point-mass longitudinal model; no wind or lateral dynamics",
            "thrust, drag, lift, rolling resistance act on the instantaneous state",
        ),
    )
    return TakeoffResult(
        scenario_id=scenario_id,
        ground_roll_distance_m=ground_roll,
        air_distance_m=takeoff_distance - ground_roll,
        takeoff_distance_m=takeoff_distance,
        liftoff_speed_m_s=liftoff_speed,
        rotation_speed_m_s=model.rotation_speed_m_s,
        total_time_s=time,
        distance_series=_series("distance", "m", times, distances),
        speed_series=_series("speed", "m/s", times, speeds),
        height_series=_series("height", "m", times, heights),
        receipt=receipt,
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class LandingResult:
    """Approach/ flare air distance plus the braked ground rollout."""

    scenario_id: str
    approach_speed_m_s: float
    touchdown_speed_m_s: float
    touchdown_sink_rate_m_s: float
    air_distance_m: float
    rollout_distance_m: float
    landing_distance_m: float
    stopping_time_s: float
    distance_series: TimeSeries
    speed_series: TimeSeries
    receipt: IntegratorReceipt
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {"distance": "m", "speed": "m/s", "time": "s"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "approachSpeedMS": self.approach_speed_m_s,
            "touchdownSpeedMS": self.touchdown_speed_m_s,
            "touchdownSinkRateMS": self.touchdown_sink_rate_m_s,
            "airDistanceM": self.air_distance_m,
            "rolloutDistanceM": self.rollout_distance_m,
            "landingDistanceM": self.landing_distance_m,
            "stoppingTimeS": self.stopping_time_s,
            "meta": self.meta.canonical(),
        }


def simulate_landing(
    model: GroundVehicleModel,
    *,
    runway: RunwaySpec,
    scenario_id: str = "landing",
    approach_speed_m_s: float,
    touchdown_sink_rate_m_s: float = 1.0,
    glide_slope_deg: float = 3.0,
    throttle: float = 0.0,
    assembly: LandingGearAssembly | None = None,
    step_size_s: float = 0.01,
    max_time_s: float = 180.0,
) -> LandingResult:
    """Land from screen height and brake to a stop; distance depends on friction."""

    approach = finite(approach_speed_m_s, "approach_speed_m_s", positive=True)
    sink_rate = finite(touchdown_sink_rate_m_s, "touchdown_sink_rate_m_s", positive=True)
    slope_deg = finite(glide_slope_deg, "glide_slope_deg", minimum=0.1, maximum=45.0)
    step = finite(step_size_s, "step_size_s", positive=True)
    horizon = finite(max_time_s, "max_time_s", positive=True)
    setting = finite(throttle, "throttle", minimum=0.0, maximum=1.0)
    slope_rad = slope_deg * pi / 180.0
    if abs(approach * sin(slope_rad)) < 1e-9:
        raise LimitExceeded("LANDING_GLIDE_SLOPE_TOO_SHALLOW")
    air_distance = model.screen_height_m * cos(slope_rad) / sin(slope_rad)

    mass = model.mass_kg
    weight = model.weight_n
    mu_brake = runway.braking_friction_coefficient
    capacity = _braking_capacity_n(assembly)
    cl_roll = model.cl_ground

    def derivative(
        time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> Mapping[str, float]:
        del time_s, inputs
        speed = max(state["speed"], 0.0)
        lift = model.lift_n(speed, cl_roll)
        drag = model.drag_n(speed, cl_roll)
        thrust = model.thrust.thrust_n(speed, setting)
        normal = max(weight - lift, 0.0)
        braking = mu_brake * normal if speed > 1e-6 else 0.0
        if capacity is not None:
            braking = min(braking, capacity)
        acceleration = (thrust - drag - braking) / mass
        return {"speed": acceleration, "distance": speed}

    state: dict[str, float] = {"speed": approach, "distance": 0.0}
    times: list[float] = [0.0]
    speeds: list[float] = [approach]
    distances: list[float] = [0.0]
    time = 0.0
    steps = 0
    max_steps = int(horizon / step) + 1
    while state["speed"] > 0.0 and steps < max_steps:
        state = dict(advance(derivative, IntegrationMethod.HEUN, time, state, step, {}))
        state["speed"] = max(state["speed"], 0.0)
        time += step
        steps += 1
        times.append(time)
        speeds.append(state["speed"])
        distances.append(state["distance"])
    if state["speed"] > 0.0:
        raise LimitExceeded("LANDING_DID_NOT_STOP_WITHIN_HORIZON")

    rollout = state["distance"]
    receipt = IntegratorReceipt(
        method=IntegrationMethod.HEUN.value,
        step_size_s=step,
        steps=steps,
        duration_s=time,
        recorded_points=len(times),
    )
    meta = result_meta(
        model="vehicle-systems.landing-gear.landing-dynamics",
        inputs={
            "vehicle": model.canonical_payload(),
            "runway": runway.canonical_payload(),
            "approachSpeedMS": approach,
            "touchdownSinkRateMS": sink_rate,
            "glideSlopeDeg": slope_deg,
            "throttle": setting,
            "brakingCapacityN": capacity,
            "stepSizeS": step,
        },
        valid=rollout > 0.0,
        checks={"stopped_within_horizon": state["speed"] <= 0.0, "rollout_positive": rollout > 0.0},
        detail="screen-height air distance + braked ground rollout",
        fidelity=LandingGearFidelity.GROUND_TRANSIENT,
        assumptions=(
            "constant glide slope from screen height; no flare arc",
            "braking friction from the declared surface, optionally torque-capped",
        ),
    )
    return LandingResult(
        scenario_id=scenario_id,
        approach_speed_m_s=approach,
        touchdown_speed_m_s=approach,
        touchdown_sink_rate_m_s=sink_rate,
        air_distance_m=air_distance,
        rollout_distance_m=rollout,
        landing_distance_m=air_distance + rollout,
        stopping_time_s=time,
        distance_series=_series("distance", "m", times, distances),
        speed_series=_series("speed", "m/s", times, speeds),
        receipt=receipt,
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class RejectedTakeoffResult:
    """Acceleration to a decision speed then a full-stop braking rollout."""

    scenario_id: str
    decision_speed_m_s: float
    acceleration_distance_m: float
    stopping_distance_m: float
    rejected_distance_m: float
    stopping_time_s: float
    distance_series: TimeSeries
    speed_series: TimeSeries
    receipt: IntegratorReceipt
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {"distance": "m", "speed": "m/s", "time": "s"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "decisionSpeedMS": self.decision_speed_m_s,
            "accelerationDistanceM": self.acceleration_distance_m,
            "stoppingDistanceM": self.stopping_distance_m,
            "rejectedDistanceM": self.rejected_distance_m,
            "stoppingTimeS": self.stopping_time_s,
            "meta": self.meta.canonical(),
        }


def simulate_rejected_takeoff(
    model: GroundVehicleModel,
    *,
    runway: RunwaySpec,
    scenario_id: str = "rejected-takeoff",
    decision_speed_m_s: float,
    throttle: float = 1.0,
    assembly: LandingGearAssembly | None = None,
    step_size_s: float = 0.01,
    max_time_s: float = 180.0,
) -> RejectedTakeoffResult:
    """Accelerate to a decision speed, cut thrust, and brake to a full stop."""

    decision = finite(decision_speed_m_s, "decision_speed_m_s", positive=True)
    step = finite(step_size_s, "step_size_s", positive=True)
    horizon = finite(max_time_s, "max_time_s", positive=True)
    setting = finite(throttle, "throttle", minimum=0.0, maximum=1.0)
    mass = model.mass_kg
    weight = model.weight_n
    mu_roll = runway.rolling_resistance_coefficient
    mu_brake = runway.braking_friction_coefficient
    capacity = _braking_capacity_n(assembly)
    slope = runway.slope_rad
    cl_roll = model.cl_ground

    def accel_derivative(
        time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> Mapping[str, float]:
        del time_s, inputs
        speed = max(state["speed"], 0.0)
        lift = model.lift_n(speed, cl_roll)
        drag = model.drag_n(speed, cl_roll)
        thrust = model.thrust.thrust_n(speed, setting)
        normal = max(weight - lift, 0.0)
        acceleration = (thrust - drag - mu_roll * normal - weight * sin(slope)) / mass
        return {"speed": acceleration, "distance": speed}

    def stop_derivative(
        time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> Mapping[str, float]:
        del time_s, inputs
        speed = max(state["speed"], 0.0)
        lift = model.lift_n(speed, cl_roll)
        drag = model.drag_n(speed, cl_roll)
        thrust = model.thrust.thrust_n(speed, 0.0)
        normal = max(weight - lift, 0.0)
        braking = mu_brake * normal if speed > 1e-6 else 0.0
        if capacity is not None:
            braking = min(braking, capacity)
        acceleration = (thrust - drag - braking) / mass
        return {"speed": acceleration, "distance": speed}

    times: list[float] = [0.0]
    speeds: list[float] = [0.0]
    distances: list[float] = [0.0]
    state: dict[str, float] = {"speed": 0.0, "distance": 0.0}
    time = 0.0
    steps = 0
    max_steps = int(horizon / step) + 1
    while state["speed"] < decision and steps < max_steps:
        state = dict(advance(accel_derivative, IntegrationMethod.HEUN, time, state, step, {}))
        state["speed"] = max(state["speed"], 0.0)
        time += step
        steps += 1
        times.append(time)
        speeds.append(state["speed"])
        distances.append(state["distance"])
    if state["speed"] < decision:
        raise LimitExceeded("REJECTED_TAKEOFF_DID_NOT_REACH_DECISION_SPEED")
    acceleration_distance = state["distance"]

    while state["speed"] > 0.0 and steps < max_steps:
        state = dict(advance(stop_derivative, IntegrationMethod.HEUN, time, state, step, {}))
        state["speed"] = max(state["speed"], 0.0)
        time += step
        steps += 1
        times.append(time)
        speeds.append(state["speed"])
        distances.append(state["distance"])
    if state["speed"] > 0.0:
        raise LimitExceeded("REJECTED_TAKEOFF_DID_NOT_STOP_WITHIN_HORIZON")
    stopping_distance = state["distance"] - acceleration_distance

    receipt = IntegratorReceipt(
        method=IntegrationMethod.HEUN.value,
        step_size_s=step,
        steps=steps,
        duration_s=time,
        recorded_points=len(times),
    )
    meta = result_meta(
        model="vehicle-systems.landing-gear.rejected-takeoff",
        inputs={
            "vehicle": model.canonical_payload(),
            "runway": runway.canonical_payload(),
            "decisionSpeedMS": decision,
            "throttle": setting,
            "brakingCapacityN": capacity,
            "stepSizeS": step,
        },
        valid=state["speed"] <= 0.0,
        checks={"stopped_within_horizon": state["speed"] <= 0.0},
        detail="accelerate to decision speed then full-stop braking",
        fidelity=LandingGearFidelity.GROUND_TRANSIENT,
        assumptions=("rejected-takeoff stop uses the declared surface braking friction",),
    )
    return RejectedTakeoffResult(
        scenario_id=scenario_id,
        decision_speed_m_s=decision,
        acceleration_distance_m=acceleration_distance,
        stopping_distance_m=stopping_distance,
        rejected_distance_m=state["distance"],
        stopping_time_s=time,
        distance_series=_series("distance", "m", times, distances),
        speed_series=_series("speed", "m/s", times, speeds),
        receipt=receipt,
        meta=meta,
    )
