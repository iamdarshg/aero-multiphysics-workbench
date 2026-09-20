"""Typed mission, vehicle, segment, constraint, and reserve definitions.

A mission is a canonical, ordered graph of typed segments. Each segment declares
its mode (bounded duration, bounded distance, or a target end state), its
controls (speed, altitude, climb rate, throttle, power fraction, configuration),
and its own altitude/speed/climb/thermal/duration constraints. Reserves are
declared independently and are enforced at mission end, never inferred from a
nominal range. Everything is frozen and hashable so two identical definitions
are bit-identical.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest

from .contracts import MissionFidelity
from .errors import MissionContractError

__all__ = [
    "CLOSURE_DIMENSIONS",
    "ClosureTolerances",
    "ControlName",
    "MissionSpec",
    "ReserveKind",
    "ReserveSpec",
    "SegmentConstraints",
    "SegmentKind",
    "SegmentMode",
    "SegmentSpec",
    "VehicleSpec",
]


class SegmentKind(StrEnum):
    """The canonical mission segment families plus a user-defined escape hatch."""

    TAXI = "taxi"
    TAKEOFF = "takeoff"
    CLIMB = "climb"
    ACCELERATION = "acceleration"
    CRUISE = "cruise"
    LOITER = "loiter"
    DASH = "dash"
    DESCENT = "descent"
    APPROACH = "approach"
    LANDING = "landing"
    RESERVE = "reserve"
    CUSTOM = "custom"


class SegmentMode(StrEnum):
    """How a segment terminates; every mode is bounded."""

    DURATION = "duration"
    DISTANCE = "distance"
    TARGET_STATE = "target-state"


class ControlName(StrEnum):
    """The segment control channels a trajectory optimizer may vary."""

    SPEED = "speed"
    ALTITUDE = "altitude"
    CLIMB_RATE = "climb-rate"
    THROTTLE = "throttle"
    POWER = "power"
    RPM = "rpm"
    PROPULSOR_PITCH = "propulsor-pitch"
    ROTOR_PITCH = "rotor-pitch"
    CONFIGURATION = "configuration"


class ReserveKind(StrEnum):
    """The reserve families enforced at mission end."""

    FUEL = "fuel"
    ENERGY = "energy"
    TIME = "time"


@dataclass(frozen=True, slots=True)
class ReserveSpec:
    """A reserve requirement enforced explicitly at mission end."""

    kind: ReserveKind
    amount: float
    label: str = "reserve"

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise MissionContractError("RESERVE_LABEL_REQUIRED")
        if not isfinite(self.amount) or self.amount < 0.0:
            raise MissionContractError(f"RESERVE_AMOUNT_INVALID:{self.label}")

    def unit(self) -> str:
        return {ReserveKind.FUEL: "kg", ReserveKind.ENERGY: "J", ReserveKind.TIME: "s"}[self.kind]

    def canonical(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "amount": self.amount,
            "label": self.label,
            "unit": self.unit(),
        }


@dataclass(frozen=True, slots=True)
class SegmentConstraints:
    """Per-segment altitude/speed/climb/thermal/duration envelope."""

    max_altitude_m: float | None = None
    min_speed_m_s: float | None = None
    max_speed_m_s: float | None = None
    max_climb_rate_m_s: float | None = None
    max_thermal_k: float | None = None
    max_duration_s: float | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("max_altitude_m", self.max_altitude_m),
            ("min_speed_m_s", self.min_speed_m_s),
            ("max_speed_m_s", self.max_speed_m_s),
            ("max_climb_rate_m_s", self.max_climb_rate_m_s),
            ("max_thermal_k", self.max_thermal_k),
            ("max_duration_s", self.max_duration_s),
        ):
            if value is not None and (not isfinite(value) or value < 0.0):
                raise MissionContractError(f"SEGMENT_CONSTRAINT_INVALID:{label}")
        if (
            self.min_speed_m_s is not None
            and self.max_speed_m_s is not None
            and self.min_speed_m_s > self.max_speed_m_s
        ):
            raise MissionContractError("SEGMENT_SPEED_BAND_INVERTED")

    def canonical(self) -> dict[str, Any]:
        return {
            "maxAltitudeM": self.max_altitude_m,
            "minSpeedMS": self.min_speed_m_s,
            "maxSpeedMS": self.max_speed_m_s,
            "maxClimbRateMS": self.max_climb_rate_m_s,
            "maxThermalK": self.max_thermal_k,
            "maxDurationS": self.max_duration_s,
        }


@dataclass(frozen=True, slots=True)
class SegmentSpec:
    """One typed, bounded mission segment with typed controls."""

    segment_id: str
    kind: SegmentKind
    mode: SegmentMode
    speed_m_s: float
    altitude_m: float
    climb_rate_m_s: float = 0.0
    throttle: float = 1.0
    power_fraction: float = 1.0
    configuration: int = 0
    duration_s: float | None = None
    distance_m: float | None = None
    target_altitude_m: float | None = None
    target_speed_m_s: float | None = None
    constraints: SegmentConstraints = field(default_factory=SegmentConstraints)
    jettison_kg: float = 0.0
    reserve: ReserveSpec | None = None
    label: str = ""
    rpm: float | None = None
    propulsor_pitch_deg: float | None = None
    rotor_pitch_deg: float | None = None

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise MissionContractError("SEGMENT_ID_REQUIRED")
        for name, value in (
            ("speed_m_s", self.speed_m_s),
            ("altitude_m", self.altitude_m),
            ("climb_rate_m_s", self.climb_rate_m_s),
        ):
            if not isfinite(value) or value < 0.0:
                raise MissionContractError(f"SEGMENT_CONTROL_INVALID:{self.segment_id}:{name}")
        for name, value in (("throttle", self.throttle), ("power_fraction", self.power_fraction)):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise MissionContractError(f"SEGMENT_CONTROL_RANGE:{self.segment_id}:{name}")
        if self.rpm is not None and (not isfinite(self.rpm) or self.rpm <= 0.0):
            raise MissionContractError(f"SEGMENT_CONTROL_RANGE:{self.segment_id}:rpm")
        for name, control_value in (
            ("propulsor_pitch_deg", self.propulsor_pitch_deg),
            ("rotor_pitch_deg", self.rotor_pitch_deg),
        ):
            if control_value is not None and not isfinite(control_value):
                raise MissionContractError(f"SEGMENT_CONTROL_INVALID:{self.segment_id}:{name}")
        if self.configuration < 0:
            raise MissionContractError(f"SEGMENT_CONFIGURATION_INVALID:{self.segment_id}")
        if not isfinite(self.jettison_kg) or self.jettison_kg < 0.0:
            raise MissionContractError(f"SEGMENT_JETTISON_INVALID:{self.segment_id}")
        if self.mode is SegmentMode.DURATION and self.duration_s is None:
            raise MissionContractError(f"SEGMENT_DURATION_REQUIRED:{self.segment_id}")
        if self.mode is SegmentMode.DISTANCE and self.distance_m is None:
            raise MissionContractError(f"SEGMENT_DISTANCE_REQUIRED:{self.segment_id}")
        if self.mode is SegmentMode.TARGET_STATE and (
            self.target_altitude_m is None and self.target_speed_m_s is None
        ):
            raise MissionContractError(f"SEGMENT_TARGET_REQUIRED:{self.segment_id}")
        for term_label, term_value in (
            ("duration_s", self.duration_s),
            ("distance_m", self.distance_m),
            ("target_altitude_m", self.target_altitude_m),
            ("target_speed_m_s", self.target_speed_m_s),
        ):
            if term_value is not None and (not isfinite(term_value) or term_value < 0.0):
                raise MissionContractError(
                    f"SEGMENT_TERMINATION_INVALID:{self.segment_id}:{term_label}"
                )

    @property
    def is_reserve(self) -> bool:
        return self.kind is SegmentKind.RESERVE

    def control(self, name: ControlName) -> float:
        if name is ControlName.SPEED:
            return self.speed_m_s
        if name is ControlName.ALTITUDE:
            return self.altitude_m
        if name is ControlName.CLIMB_RATE:
            return self.climb_rate_m_s
        if name is ControlName.THROTTLE:
            return self.throttle
        if name is ControlName.POWER:
            return self.power_fraction
        if name is ControlName.RPM:
            if self.rpm is None:
                raise MissionContractError(f"SEGMENT_CONTROL_UNSET:{self.segment_id}:rpm")
            return self.rpm
        if name is ControlName.PROPULSOR_PITCH:
            if self.propulsor_pitch_deg is None:
                raise MissionContractError(
                    f"SEGMENT_CONTROL_UNSET:{self.segment_id}:propulsor-pitch"
                )
            return self.propulsor_pitch_deg
        if name is ControlName.ROTOR_PITCH:
            if self.rotor_pitch_deg is None:
                raise MissionContractError(f"SEGMENT_CONTROL_UNSET:{self.segment_id}:rotor-pitch")
            return self.rotor_pitch_deg
        return float(self.configuration)

    def with_control(self, name: ControlName, value: float) -> SegmentSpec:
        if name is ControlName.SPEED:
            return replace(self, speed_m_s=value)
        if name is ControlName.ALTITUDE:
            return replace(self, altitude_m=value)
        if name is ControlName.CLIMB_RATE:
            return replace(self, climb_rate_m_s=value)
        if name is ControlName.THROTTLE:
            return replace(self, throttle=value)
        if name is ControlName.POWER:
            return replace(self, power_fraction=value)
        if name is ControlName.RPM:
            return replace(self, rpm=value)
        if name is ControlName.PROPULSOR_PITCH:
            return replace(self, propulsor_pitch_deg=value)
        if name is ControlName.ROTOR_PITCH:
            return replace(self, rotor_pitch_deg=value)
        return replace(self, configuration=int(round(value)))

    def canonical(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "segmentId": self.segment_id,
            "kind": self.kind.value,
            "mode": self.mode.value,
            "speedMS": self.speed_m_s,
            "altitudeM": self.altitude_m,
            "climbRateMS": self.climb_rate_m_s,
            "throttle": self.throttle,
            "powerFraction": self.power_fraction,
            "configuration": self.configuration,
            "durationS": self.duration_s,
            "distanceM": self.distance_m,
            "targetAltitudeM": self.target_altitude_m,
            "targetSpeedMS": self.target_speed_m_s,
            "constraints": self.constraints.canonical(),
            "jettisonKg": self.jettison_kg,
            "label": self.label,
        }
        if self.rpm is not None:
            payload["rpm"] = self.rpm
        if self.propulsor_pitch_deg is not None:
            payload["propulsorPitchDeg"] = self.propulsor_pitch_deg
        if self.rotor_pitch_deg is not None:
            payload["rotorPitchDeg"] = self.rotor_pitch_deg
        if self.reserve is not None:
            payload["reserve"] = self.reserve.canonical()
        return payload


@dataclass(frozen=True, slots=True)
class VehicleSpec:
    """Deterministic vehicle mass/energy/thermal/envelope definition."""

    vehicle_id: str
    empty_mass_kg: float
    initial_fuel_kg: float
    fuel_lhv_j_kg: float
    battery_capacity_j: float = 0.0
    initial_state_of_charge: float = 1.0
    thermal_heat_capacity_j_k: float = 0.0
    thermal_resistance_k_w: float = 0.0
    initial_thermal_k: float = 288.15
    reference_area_m2: float = 1.0
    envelope: SegmentConstraints = field(default_factory=SegmentConstraints)
    step_size_s: float = 1.0
    max_steps: int = 100000
    ground_speed_m_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.vehicle_id.strip():
            raise MissionContractError("VEHICLE_ID_REQUIRED")
        for name, value in (
            ("empty_mass_kg", self.empty_mass_kg),
            ("initial_fuel_kg", self.initial_fuel_kg),
            ("fuel_lhv_j_kg", self.fuel_lhv_j_kg),
            ("battery_capacity_j", self.battery_capacity_j),
        ):
            minimum = 0.0
            if not isfinite(value) or value < minimum:
                raise MissionContractError(f"VEHICLE_PARAM_INVALID:{name}")
        if self.empty_mass_kg <= 0.0:
            raise MissionContractError("VEHICLE_EMPTY_MASS_MUST_BE_POSITIVE")
        if not 0.0 <= self.initial_state_of_charge <= 1.0:
            raise MissionContractError("VEHICLE_SOC_OUT_OF_RANGE")
        if self.thermal_heat_capacity_j_k < 0.0 or self.thermal_resistance_k_w < 0.0:
            raise MissionContractError("VEHICLE_THERMAL_INVALID")
        if not isfinite(self.initial_thermal_k) or self.initial_thermal_k <= 0.0:
            raise MissionContractError("VEHICLE_INITIAL_THERMAL_INVALID")
        if self.reference_area_m2 <= 0.0:
            raise MissionContractError("VEHICLE_REFERENCE_AREA_MUST_BE_POSITIVE")
        if not isfinite(self.step_size_s) or self.step_size_s <= 0.0:
            raise MissionContractError("VEHICLE_STEP_SIZE_INVALID")
        if self.max_steps <= 0:
            raise MissionContractError("VEHICLE_MAX_STEPS_INVALID")
        if not isfinite(self.ground_speed_m_s) or self.ground_speed_m_s < 0.0:
            raise MissionContractError("VEHICLE_GROUND_SPEED_INVALID")

    @property
    def initial_mass_kg(self) -> float:
        return self.empty_mass_kg + self.initial_fuel_kg

    def canonical(self) -> dict[str, Any]:
        return {
            "vehicleId": self.vehicle_id,
            "emptyMassKg": self.empty_mass_kg,
            "initialFuelKg": self.initial_fuel_kg,
            "fuelLhvJKg": self.fuel_lhv_j_kg,
            "batteryCapacityJ": self.battery_capacity_j,
            "initialStateOfCharge": self.initial_state_of_charge,
            "thermalHeatCapacityJK": self.thermal_heat_capacity_j_k,
            "thermalResistanceKW": self.thermal_resistance_k_w,
            "initialThermalK": self.initial_thermal_k,
            "referenceAreaM2": self.reference_area_m2,
            "envelope": self.envelope.canonical(),
            "stepSizeS": self.step_size_s,
            "maxSteps": self.max_steps,
            "groundSpeedMS": self.ground_speed_m_s,
        }


CLOSURE_DIMENSIONS: tuple[str, ...] = ("mass", "fuel", "energy", "distance", "continuity")


@dataclass(frozen=True, slots=True)
class ClosureTolerances:
    """Relative/absolute tolerances for mission closure residuals."""

    mass_rel: float = 1e-6
    fuel_rel: float = 1e-6
    energy_rel: float = 1e-6
    distance_rel: float = 1e-6
    continuity_abs: float = 1e-6

    def __post_init__(self) -> None:
        for label, value in (
            ("mass_rel", self.mass_rel),
            ("fuel_rel", self.fuel_rel),
            ("energy_rel", self.energy_rel),
            ("distance_rel", self.distance_rel),
            ("continuity_abs", self.continuity_abs),
        ):
            if not isfinite(value) or value < 0.0:
                raise MissionContractError(f"CLOSURE_TOLERANCE_INVALID:{label}")

    def canonical(self) -> dict[str, float]:
        return {
            "massRel": self.mass_rel,
            "fuelRel": self.fuel_rel,
            "energyRel": self.energy_rel,
            "distanceRel": self.distance_rel,
            "continuityAbs": self.continuity_abs,
        }


@dataclass(frozen=True, slots=True)
class MissionSpec:
    """A canonical, ordered, deterministic mission definition."""

    mission_id: str
    vehicle: VehicleSpec
    segments: tuple[SegmentSpec, ...]
    reserves: tuple[ReserveSpec, ...] = ()
    closure: ClosureTolerances = field(default_factory=ClosureTolerances)
    expected_fidelity: MissionFidelity = MissionFidelity.ANALYTICAL
    label: str = ""

    def __post_init__(self) -> None:
        if not self.mission_id.strip():
            raise MissionContractError("MISSION_ID_REQUIRED")
        if not self.segments:
            raise MissionContractError("MISSION_NEEDS_SEGMENTS")
        identifiers = [segment.segment_id for segment in self.segments]
        if len(identifiers) != len(set(identifiers)):
            raise MissionContractError("MISSION_DUPLICATE_SEGMENT_ID")
        reserve_segments = [segment for segment in self.segments if segment.is_reserve]
        if len(reserve_segments) > 1:
            raise MissionContractError("MISSION_AT_MOST_ONE_RESERVE_SEGMENT")

    def segment(self, segment_id: str) -> SegmentSpec:
        for candidate in self.segments:
            if candidate.segment_id == segment_id:
                return candidate
        raise MissionContractError(f"UNKNOWN_SEGMENT:{segment_id}")

    def reserve(self, kind: ReserveKind) -> ReserveSpec | None:
        for candidate in self.reserves:
            if candidate.kind is kind:
                return candidate
        return None

    def with_segments(self, segments: Iterable[SegmentSpec]) -> MissionSpec:
        return replace(self, segments=tuple(segments))

    def canonical(self) -> dict[str, Any]:
        return {
            "missionId": self.mission_id,
            "label": self.label,
            "vehicle": self.vehicle.canonical(),
            "segments": [segment.canonical() for segment in self.segments],
            "reserves": [reserve.canonical() for reserve in self.reserves],
            "closure": self.closure.canonical(),
            "expectedFidelity": self.expected_fidelity.value,
        }

    def digest(self) -> str:
        return content_digest(self.canonical())
