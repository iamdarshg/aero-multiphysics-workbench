"""Deterministic mission propagation with bounded, typed segments.

The propagator advances the shared mission state (distance, altitude, speed,
mass, fuel, battery state of charge, thermal state, consumed/propulsive energy)
through each segment with the deterministic integrator from
``aeroworkbench_system_dynamics``. Segment controls and performance consumption
come from a typed :class:`PerformanceParticipant`. Every segment is bounded:
duration, distance, or a target end state, plus a hard step cap. Fuel/battery
exhaustion, envelope breaches, and non-terminating segments fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import atan2, ceil, isinf, sin
from typing import Any

from aeroworkbench_fluid_properties import ISA, FluidError
from aeroworkbench_system_dynamics import DerivativeFn, IntegrationMethod, advance

from .contracts import MissionFidelity
from .errors import MissionContractError, MissionValidationError, PerformanceRejected
from .performance import (
    GRAVITY_M_S2,
    AeroPoint,
    OperatingPoint,
    PerformanceParticipant,
    PropulsionPoint,
)
from .segments import MissionSpec, SegmentKind, SegmentMode, SegmentSpec, VehicleSpec
from .state import MissionState

__all__ = [
    "MissionTrace",
    "PropagationPolicy",
    "SegmentTrace",
    "propagate_mission",
]

_ALTITUDE_TOLERANCE_M = 1.0
_SPEED_TOLERANCE_M_S = 0.1
_TARGET_STATE_MAX_S = 21600.0
_DEFAULT_SPEED_TIME_CONSTANT_S = 30.0


@dataclass(frozen=True, slots=True)
class PropagationPolicy:
    """Bounded propagation behaviour; escalation is rejected by default."""

    speed_time_constant_s: float = _DEFAULT_SPEED_TIME_CONSTANT_S
    altitude_tolerance_m: float = _ALTITUDE_TOLERANCE_M
    speed_tolerance_m_s: float = _SPEED_TOLERANCE_M_S
    default_climb_rate_m_s: float = 5.0
    on_escalation: str = "reject"

    def __post_init__(self) -> None:
        if self.on_escalation not in {"reject", "record"}:
            raise MissionContractError(f"UNKNOWN_ESCALATION_POLICY:{self.on_escalation}")
        if self.speed_time_constant_s <= 0.0:
            raise MissionContractError("SPEED_TIME_CONSTANT_MUST_BE_POSITIVE")
        if self.default_climb_rate_m_s <= 0.0:
            raise MissionContractError("DEFAULT_CLIMB_RATE_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class SegmentTrace:
    """One propagated segment with its balances and validity checks."""

    segment_id: str
    kind: SegmentKind
    start: MissionState
    end: MissionState
    steps: int
    terminated: bool
    fuel_burned_kg: float
    energy_consumed_j: float
    propulsive_energy_j: float
    aero_fidelity: MissionFidelity
    propulsion_fidelity: MissionFidelity
    requires_escalation: bool
    constraint_violations: tuple[str, ...]

    @property
    def duration_s(self) -> float:
        return self.end.time_s - self.start.time_s

    @property
    def distance_m(self) -> float:
        return self.end.distance_m - self.start.distance_m

    @property
    def passed(self) -> bool:
        return self.terminated and not self.constraint_violations and not self.requires_escalation

    def canonical(self) -> dict[str, Any]:
        return {
            "segmentId": self.segment_id,
            "kind": self.kind.value,
            "steps": self.steps,
            "terminated": self.terminated,
            "durationS": self.duration_s,
            "distanceM": self.distance_m,
            "fuelBurnedKg": self.fuel_burned_kg,
            "energyConsumedJ": self.energy_consumed_j,
            "propulsiveEnergyJ": self.propulsive_energy_j,
            "aeroFidelity": self.aero_fidelity.value,
            "propulsionFidelity": self.propulsion_fidelity.value,
            "requiresEscalation": self.requires_escalation,
            "constraintViolations": list(self.constraint_violations),
            "start": self.start.canonical(),
            "end": self.end.canonical(),
        }


@dataclass(frozen=True, slots=True)
class MissionTrace:
    """The complete propagation trace of a mission."""

    mission_id: str
    initial: MissionState
    final: MissionState
    segments: tuple[SegmentTrace, ...]
    fuel_burned_kg: float
    energy_consumed_j: float
    propulsive_energy_j: float
    jettisoned_kg: float
    reserve_duration_s: float
    max_boundary_discontinuity: float
    peak_altitude_m: float
    peak_speed_m_s: float
    max_mach: float
    peak_thermal_k: float
    escalations: tuple[str, ...]
    constraint_violations: tuple[str, ...]
    fidelity: MissionFidelity
    assumptions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def segment_distance_sum_m(self) -> float:
        return sum(segment.distance_m for segment in self.segments)

    def canonical(self) -> dict[str, Any]:
        return {
            "missionId": self.mission_id,
            "initial": self.initial.canonical(),
            "final": self.final.canonical(),
            "segments": [segment.canonical() for segment in self.segments],
            "fuelBurnedKg": self.fuel_burned_kg,
            "energyConsumedJ": self.energy_consumed_j,
            "propulsiveEnergyJ": self.propulsive_energy_j,
            "jettisonedKg": self.jettisoned_kg,
            "reserveDurationS": self.reserve_duration_s,
            "maxBoundaryDiscontinuity": self.max_boundary_discontinuity,
            "peakAltitudeM": self.peak_altitude_m,
            "peakSpeedMS": self.peak_speed_m_s,
            "maxMach": self.max_mach,
            "peakThermalK": self.peak_thermal_k,
            "escalations": list(self.escalations),
            "constraintViolations": list(self.constraint_violations),
            "fidelity": self.fidelity.value,
            "assumptions": list(self.assumptions),
        }


def _ambient_temperature_k(altitude_m: float) -> float:
    try:
        return ISA.evaluate(altitude_m=altitude_m).temperature_k
    except FluidError as exc:
        raise MissionValidationError(f"ATMOSPHERE_OUT_OF_VALIDITY:{altitude_m}:{exc}") from exc


def _commanded_climb(segment: SegmentSpec, state: MissionState, step_s: float) -> float:
    if segment.target_altitude_m is not None:
        delta = segment.target_altitude_m - state.altitude_m
        if abs(delta) <= _ALTITUDE_TOLERANCE_M:
            return 0.0
        magnitude = min(abs(delta) / step_s, segment.climb_rate_m_s)
        return magnitude if delta > 0.0 else -magnitude
    if segment.kind in (SegmentKind.DESCENT, SegmentKind.APPROACH, SegmentKind.LANDING):
        return -segment.climb_rate_m_s
    return segment.climb_rate_m_s


def _target_reached(segment: SegmentSpec, state: MissionState, policy: PropagationPolicy) -> bool:
    altitude_reached = segment.target_altitude_m is None or (
        abs(state.altitude_m - segment.target_altitude_m) <= policy.altitude_tolerance_m
    )
    speed_reached = segment.target_speed_m_s is None or (
        abs(state.speed_m_s - segment.target_speed_m_s) <= policy.speed_tolerance_m_s
    )
    return altitude_reached and speed_reached


def _check_envelope(
    segment: SegmentSpec, vehicle: VehicleSpec, state: MissionState, climb_rate_m_s: float
) -> tuple[str, ...]:
    violations: list[str] = []
    for label, constraint, value in (
        ("ALTITUDE", vehicle.envelope.max_altitude_m, state.altitude_m),
        ("SPEED_MAX", vehicle.envelope.max_speed_m_s, state.speed_m_s),
        ("SPEED_MIN", vehicle.envelope.min_speed_m_s, state.speed_m_s),
        ("CLIMB", vehicle.envelope.max_climb_rate_m_s, abs(climb_rate_m_s)),
        ("THERMAL", vehicle.envelope.max_thermal_k, state.thermal_k),
    ):
        if constraint is None:
            continue
        if label == "SPEED_MIN":
            if value < constraint - _SPEED_TOLERANCE_M_S:
                violations.append(f"ENVELOPE_{label}:{segment.segment_id}:{value}<{constraint}")
        elif value > constraint + _ALTITUDE_TOLERANCE_M:
            violations.append(f"ENVELOPE_{label}:{segment.segment_id}:{value}>{constraint}")
    for label, constraint, value in (
        ("ALTITUDE", segment.constraints.max_altitude_m, state.altitude_m),
        ("SPEED_MAX", segment.constraints.max_speed_m_s, state.speed_m_s),
        ("CLIMB", segment.constraints.max_climb_rate_m_s, abs(climb_rate_m_s)),
        ("THERMAL", segment.constraints.max_thermal_k, state.thermal_k),
    ):
        if constraint is None:
            continue
        if value > constraint + _ALTITUDE_TOLERANCE_M:
            violations.append(f"SEGMENT_{label}:{segment.segment_id}:{value}>{constraint}")
    if (
        segment.constraints.min_speed_m_s is not None
        and state.speed_m_s < segment.constraints.min_speed_m_s - _SPEED_TOLERANCE_M_S
    ):
        violations.append(f"SEGMENT_SPEED_MIN:{segment.segment_id}")
    return tuple(violations)


def _make_derivative(vehicle: VehicleSpec) -> DerivativeFn:
    def derivative(
        time_s: float, state: Mapping[str, float], inputs: Mapping[str, float]
    ) -> dict[str, float]:
        del time_s
        fuel_flow = inputs["fuel_flow_kg_s"]
        electrical = inputs["electrical_power_w"]
        capacity = vehicle.battery_capacity_j
        heat_capacity = vehicle.thermal_heat_capacity_j_k
        resistance = vehicle.thermal_resistance_k_w
        thermal_rate = 0.0
        if heat_capacity > 0.0 and resistance > 0.0:
            thermal_rate = (
                inputs["thermal_load_w"]
                - (state["thermal_k"] - inputs["ambient_temperature_k"]) / resistance
            ) / heat_capacity
        soc_rate = -electrical / capacity if capacity > 0.0 else 0.0
        return {
            "distance_m": state["speed_m_s"],
            "altitude_m": inputs["climb_rate_m_s"],
            "speed_m_s": inputs["speed_acceleration_m_s2"],
            "mass_kg": -fuel_flow,
            "fuel_kg": -fuel_flow,
            "battery_soc": soc_rate,
            "thermal_k": thermal_rate,
            "stored_energy_consumed_j": fuel_flow * vehicle.fuel_lhv_j_kg + electrical,
            "propulsive_energy_j": inputs["propulsive_power_w"],
        }

    return derivative


def _step(
    *,
    derivative: DerivativeFn,
    method: IntegrationMethod,
    time_s: float,
    state: MissionState,
    dt_s: float,
    inputs: dict[str, float],
) -> MissionState:
    advanced = advance(derivative, method, time_s, state.core(), dt_s, inputs)
    return MissionState.from_core(
        time_s=time_s + dt_s,
        core=dict(advanced),
        jettisoned_kg=state.jettisoned_kg,
    )


def _validate_state(segment: SegmentSpec, state: MissionState) -> None:
    if state.fuel_kg < -1e-9:
        raise MissionValidationError(f"FUEL_EXHAUSTED:{segment.segment_id}")
    if state.battery_soc < -1e-9:
        raise MissionValidationError(f"BATTERY_DEPLETED:{segment.segment_id}")
    if state.mass_kg <= 0.0:
        raise MissionValidationError(f"NONPOSITIVE_MASS:{segment.segment_id}")


def _propagate_segment(
    spec: MissionSpec,
    segment: SegmentSpec,
    state: MissionState,
    participant: PerformanceParticipant,
    policy: PropagationPolicy,
    *,
    derivative: DerivativeFn,
    method: IntegrationMethod,
) -> SegmentTrace:
    vehicle = spec.vehicle
    step = vehicle.step_size_s
    if segment.mode is SegmentMode.DURATION:
        duration = segment.duration_s
        assert duration is not None
        max_steps = int(ceil(duration / step)) + 1
    elif segment.mode is SegmentMode.DISTANCE:
        distance = segment.distance_m
        assert distance is not None
        horizon = distance / max(segment.speed_m_s, 1e-6) * 4.0 + step
        max_steps = min(vehicle.max_steps, int(ceil(horizon / step)) + 10)
    else:
        max_steps = min(vehicle.max_steps, int(ceil(_TARGET_STATE_MAX_S / step)) + 10)

    start = state
    fuel_before = state.fuel_kg
    energy_before = state.stored_energy_consumed_j
    propulsive_before = state.propulsive_energy_j
    steps = 0
    terminated = False
    requires_escalation = False
    aero_fidelity = MissionFidelity.ANALYTICAL
    propulsion_fidelity = MissionFidelity.ANALYTICAL
    violations: list[str] = []

    while steps < max_steps:
        point = OperatingPoint(
            altitude_m=state.altitude_m,
            speed_m_s=state.speed_m_s,
            mass_kg=state.mass_kg,
            climb_rate_m_s=segment.climb_rate_m_s,
            throttle=segment.throttle,
            power_fraction=segment.power_fraction,
            configuration=segment.configuration,
            segment_kind=segment.kind,
            phase=segment.mode.value,
        )
        aero: AeroPoint = participant.drag(point)
        climb = _commanded_climb(segment, state, step)
        gamma = atan2(climb, max(state.speed_m_s, 1e-6))
        required_thrust = aero.drag_n + state.mass_kg * GRAVITY_M_S2 * sin(gamma)
        ungoverned = segment.kind is SegmentKind.ACCELERATION
        if ungoverned:
            propulsion: PropulsionPoint = participant.propulsion(point, float("inf"))
        else:
            commanded = (
                segment.target_speed_m_s
                if segment.mode is SegmentMode.TARGET_STATE and segment.target_speed_m_s is not None
                else segment.speed_m_s
            )
            desired_acceleration = 0.0
            if commanded > 0.0:
                desired_acceleration = (
                    commanded - state.speed_m_s
                ) / policy.speed_time_constant_s
            command = required_thrust + state.mass_kg * desired_acceleration
            propulsion = participant.propulsion(point, max(command, 0.0))
        acceleration = (propulsion.thrust_n - required_thrust) / state.mass_kg
        aero_fidelity = aero.fidelity
        propulsion_fidelity = propulsion.fidelity
        if aero.requires_escalation or propulsion.requires_escalation:
            requires_escalation = True
            if policy.on_escalation == "reject":
                raise PerformanceRejected(
                    f"PERFORMANCE_ESCALATION_REQUIRED:{segment.segment_id}:"
                    f"{aero.detail}|{propulsion.detail}"
                )
        inputs = {
            "fuel_flow_kg_s": propulsion.fuel_flow_kg_s,
            "electrical_power_w": propulsion.electrical_power_w,
            "thermal_load_w": propulsion.thermal_load_w,
            "propulsive_power_w": propulsion.propulsive_power_w,
            "climb_rate_m_s": climb,
            "speed_acceleration_m_s2": acceleration,
            "ambient_temperature_k": _ambient_temperature_k(state.altitude_m),
        }
        state = _step(
            derivative=derivative,
            method=method,
            time_s=state.time_s,
            state=state,
            dt_s=step,
            inputs=inputs,
        )
        steps += 1
        _validate_state(segment, state)
        violations.extend(_check_envelope(segment, vehicle, state, climb))
        if violations:
            break
        if segment.constraints.max_duration_s is not None and (
            state.time_s - start.time_s >= segment.constraints.max_duration_s - 1e-9
        ):
            break
        if segment.mode is SegmentMode.DURATION:
            duration = segment.duration_s
            assert duration is not None
            terminated = state.time_s - start.time_s >= duration - 1e-9
        elif segment.mode is SegmentMode.DISTANCE:
            distance = segment.distance_m
            assert distance is not None
            terminated = state.distance_m - start.distance_m >= distance - 1e-9
        else:
            terminated = _target_reached(segment, state, policy)
        if terminated:
            break

    if not terminated and not violations:
        raise MissionValidationError(f"SEGMENT_DID_NOT_TERMINATE:{segment.segment_id}")

    if segment.jettison_kg > 0.0:
        state = state.jettison(segment.jettison_kg)

    return SegmentTrace(
        segment_id=segment.segment_id,
        kind=segment.kind,
        start=start,
        end=state,
        steps=steps,
        terminated=terminated,
        fuel_burned_kg=fuel_before - state.fuel_kg,
        energy_consumed_j=state.stored_energy_consumed_j - energy_before,
        propulsive_energy_j=state.propulsive_energy_j - propulsive_before,
        aero_fidelity=aero_fidelity,
        propulsion_fidelity=propulsion_fidelity,
        requires_escalation=requires_escalation,
        constraint_violations=tuple(violations),
    )


def _max_fidelity(a: MissionFidelity, b: MissionFidelity) -> MissionFidelity:
    order = {
        MissionFidelity.ANALYTICAL: 0,
        MissionFidelity.REDUCED_MAP: 1,
        MissionFidelity.NATIVE: 2,
    }
    return a if order[a] >= order[b] else b


def propagate_mission(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    *,
    policy: PropagationPolicy | None = None,
) -> MissionTrace:
    """Propagate a whole mission segment by segment, accumulating balances."""

    active = policy if policy is not None else PropagationPolicy()
    derivative = _make_derivative(spec.vehicle)
    method = IntegrationMethod.EXPLICIT_EULER
    state = MissionState.initial(spec.vehicle)
    initial = state
    segments: list[SegmentTrace] = []
    escalations: list[str] = []
    violations: list[str] = []
    peak_altitude = state.altitude_m
    peak_speed = state.speed_m_s
    max_mach = 0.0
    peak_thermal = state.thermal_k

    for segment in spec.segments:
        trace = _propagate_segment(
            spec,
            segment,
            state,
            participant,
            active,
            derivative=derivative,
            method=method,
        )
        segments.append(trace)
        if trace.requires_escalation:
            escalations.append(f"{segment.segment_id}:{trace.aero_fidelity.value}")
        if trace.constraint_violations:
            violations.extend(trace.constraint_violations)
        state = trace.end
        peak_altitude = max(peak_altitude, trace.end.altitude_m)
        peak_speed = max(peak_speed, trace.end.speed_m_s)
        peak_thermal = max(peak_thermal, trace.end.thermal_k)
        try:
            state_air = ISA.evaluate(altitude_m=trace.end.altitude_m)
            mach = trace.end.speed_m_s / state_air.speed_of_sound_m_s
        except FluidError:
            mach = 0.0
        if not isinf(mach):
            max_mach = max(max_mach, mach)

    max_discontinuity = 0.0
    for earlier, later in zip(segments, segments[1:], strict=False):
        max_discontinuity = max(
            max_discontinuity,
            abs(earlier.end.speed_m_s - later.start.speed_m_s),
            abs(earlier.end.altitude_m - later.start.altitude_m),
            abs(earlier.end.time_s - later.start.time_s),
        )

    fidelity = MissionFidelity.ANALYTICAL
    for trace in segments:
        fidelity = _max_fidelity(fidelity, trace.aero_fidelity)
        fidelity = _max_fidelity(fidelity, trace.propulsion_fidelity)

    reserve_duration = sum(
        trace.duration_s for trace in segments if trace.kind is SegmentKind.RESERVE
    )
    fuel_burned = sum(trace.fuel_burned_kg for trace in segments)
    energy_consumed = sum(trace.energy_consumed_j for trace in segments)
    propulsive = sum(trace.propulsive_energy_j for trace in segments)
    return MissionTrace(
        mission_id=spec.mission_id,
        initial=initial,
        final=state,
        segments=tuple(segments),
        fuel_burned_kg=fuel_burned,
        energy_consumed_j=energy_consumed,
        propulsive_energy_j=propulsive,
        jettisoned_kg=state.jettisoned_kg,
        reserve_duration_s=reserve_duration,
        max_boundary_discontinuity=max_discontinuity,
        peak_altitude_m=peak_altitude,
        peak_speed_m_s=peak_speed,
        max_mach=max_mach,
        peak_thermal_k=peak_thermal,
        escalations=tuple(escalations),
        constraint_violations=tuple(violations),
        fidelity=fidelity,
        assumptions=(
            "quasi-steady point-mass aero with zero-order-hold inputs per step",
            f"explicit-euler integration step {spec.vehicle.step_size_s} s",
            "commanded-speed first-order tracking",
        ),
    )
