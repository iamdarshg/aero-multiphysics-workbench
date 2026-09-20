"""Typed performance participants: the aero/propulsion consumption seam.

A participant answers two instantaneous questions at one operating point: what
aerodynamic drag/lift acts on the vehicle, and what fuel/electrical energy the
propulsion system spends to produce a demanded thrust. The analytical fixed-wing
and rotorcraft participants are closed-form and deterministic; the map
participant consumes validated #68 performance maps and fails closed (rejects)
or escalates when a query would silently extrapolate. Every returned point
carries its source/fidelity/validity/escalation state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import isfinite, pi, sqrt
from typing import Any, Protocol

from aeroworkbench_fluid_properties import ISA, AtmosphereState, FluidError, StandardAtmosphere
from aeroworkbench_rom import (
    ExtrapolationError,
    ExtrapolationPolicy,
    MapConsumption,
    PerformanceMap,
    RomError,
    ValidationError,
    consume_map,
)

from .contracts import MissionFidelity
from .errors import MissionContractError, MissionValidationError, PerformanceRejected
from .segments import SegmentKind

__all__ = [
    "GRAVITY_M_S2",
    "AeroPoint",
    "AnalyticalFixedWingParticipant",
    "AnalyticalRotorcraftParticipant",
    "OperatingPoint",
    "PerformanceMapParticipant",
    "PerformanceParticipant",
    "PropulsionPoint",
]

GRAVITY_M_S2 = 9.80665


@dataclass(frozen=True, slots=True)
class OperatingPoint:
    """The instantaneous physical point at which performance is evaluated."""

    altitude_m: float
    speed_m_s: float
    mass_kg: float
    climb_rate_m_s: float
    throttle: float
    power_fraction: float
    configuration: int
    segment_kind: SegmentKind
    phase: str

    def canonical(self) -> dict[str, Any]:
        return {
            "altitudeM": self.altitude_m,
            "speedMS": self.speed_m_s,
            "massKg": self.mass_kg,
            "climbRateMS": self.climb_rate_m_s,
            "throttle": self.throttle,
            "powerFraction": self.power_fraction,
            "configuration": self.configuration,
            "segmentKind": self.segment_kind.value,
            "phase": self.phase,
        }


@dataclass(frozen=True, slots=True)
class AeroPoint:
    """Instantaneous aerodynamic result at one operating point."""

    drag_n: float
    lift_n: float
    density_kg_m3: float
    mach: float
    fidelity: MissionFidelity
    inside_validity: bool
    requires_escalation: bool
    uncertainty: float
    detail: str = ""

    def canonical(self) -> dict[str, Any]:
        return {
            "dragN": self.drag_n,
            "liftN": self.lift_n,
            "densityKgM3": self.density_kg_m3,
            "mach": self.mach,
            "fidelity": self.fidelity.value,
            "insideValidity": self.inside_validity,
            "requiresEscalation": self.requires_escalation,
            "uncertainty": self.uncertainty,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PropulsionPoint:
    """Instantaneous propulsion result for a demanded thrust."""

    thrust_n: float
    fuel_flow_kg_s: float
    electrical_power_w: float
    propulsive_power_w: float
    thermal_load_w: float
    available_thrust_n: float
    fidelity: MissionFidelity
    inside_validity: bool
    requires_escalation: bool
    uncertainty: float
    detail: str = ""

    def energy_flow_w(self, fuel_lhv_j_kg: float) -> float:
        return self.fuel_flow_kg_s * fuel_lhv_j_kg + self.electrical_power_w

    def canonical(self) -> dict[str, Any]:
        return {
            "thrustN": self.thrust_n,
            "fuelFlowKgS": self.fuel_flow_kg_s,
            "electricalPowerW": self.electrical_power_w,
            "propulsivePowerW": self.propulsive_power_w,
            "thermalLoadW": self.thermal_load_w,
            "availableThrustN": self.available_thrust_n,
            "fidelity": self.fidelity.value,
            "insideValidity": self.inside_validity,
            "requiresEscalation": self.requires_escalation,
            "uncertainty": self.uncertainty,
            "detail": self.detail,
        }


class PerformanceParticipant(Protocol):
    """The seam shared by analytical, map, and native performance providers."""

    participant_id: str

    def drag(self, point: OperatingPoint) -> AeroPoint: ...

    def propulsion(self, point: OperatingPoint, thrust_n: float) -> PropulsionPoint: ...


def _atmosphere(atmosphere: StandardAtmosphere, altitude_m: float) -> AtmosphereState:
    try:
        return atmosphere.evaluate(altitude_m=altitude_m)
    except FluidError as exc:
        raise MissionValidationError(f"ATMOSPHERE_OUT_OF_VALIDITY:{altitude_m}:{exc}") from exc


@dataclass(frozen=True, slots=True)
class AnalyticalFixedWingParticipant:
    """Closed-form parabolic-polar drag plus a turbofan or electric propulsion."""

    participant_id: str = "fixed-wing-analytical"
    cd0: float = 0.02
    oswald_e: float = 0.8
    aspect_ratio: float = 8.0
    reference_area_m2: float = 16.0
    max_thrust_n: float = 20000.0
    tsfc_kg_n_s: float = 1.5e-5
    fuel_lhv_j_kg: float = 0.0
    power_model: str = "turbofan"
    propeller_efficiency: float = 0.8
    thermal_load_fraction: float = 0.02
    atmosphere: StandardAtmosphere = field(default_factory=lambda: ISA)

    def __post_init__(self) -> None:
        if self.power_model not in {"turbofan", "electric"}:
            raise MissionContractError(f"UNKNOWN_POWER_MODEL:{self.power_model}")
        for label, value in (
            ("cd0", self.cd0),
            ("oswald_e", self.oswald_e),
            ("aspect_ratio", self.aspect_ratio),
            ("reference_area_m2", self.reference_area_m2),
            ("max_thrust_n", self.max_thrust_n),
        ):
            if not isfinite(value) or value <= 0.0:
                raise MissionContractError(f"FIXED_WING_PARAM_INVALID:{label}")
        if self.power_model == "electric" and not 0.0 < self.propeller_efficiency <= 1.0:
            raise MissionContractError("FIXED_WING_EFFICIENCY_OUT_OF_RANGE")

    def drag(self, point: OperatingPoint) -> AeroPoint:
        state = _atmosphere(self.atmosphere, point.altitude_m)
        density = state.density_kg_m3
        speed = point.speed_m_s
        dynamic = 0.5 * density * speed * speed
        weight = point.mass_kg * GRAVITY_M_S2
        lift_coefficient = weight / (dynamic * self.reference_area_m2) if dynamic > 0.0 else 0.0
        induced = lift_coefficient * lift_coefficient / (pi * self.aspect_ratio * self.oswald_e)
        drag = dynamic * self.reference_area_m2 * (self.cd0 + induced)
        return AeroPoint(
            drag_n=drag,
            lift_n=weight,
            density_kg_m3=density,
            mach=speed / state.speed_of_sound_m_s,
            fidelity=MissionFidelity.ANALYTICAL,
            inside_validity=True,
            requires_escalation=False,
            uncertainty=0.0,
            detail="parabolic polar",
        )

    def propulsion(self, point: OperatingPoint, thrust_n: float) -> PropulsionPoint:
        maximum = self.max_thrust_n * point.throttle
        thrust = min(max(thrust_n, 0.0), maximum)
        propulsive = thrust * point.speed_m_s
        if self.power_model == "electric":
            fuel_flow = 0.0
            electrical = propulsive / self.propeller_efficiency if propulsive > 0.0 else 0.0
        else:
            fuel_flow = self.tsfc_kg_n_s * thrust
            electrical = 0.0
        thermal = self.thermal_load_fraction * (fuel_flow * self.fuel_lhv_j_kg + electrical)
        return PropulsionPoint(
            thrust_n=thrust,
            fuel_flow_kg_s=fuel_flow,
            electrical_power_w=electrical,
            propulsive_power_w=propulsive,
            thermal_load_w=thermal,
            available_thrust_n=maximum,
            fidelity=MissionFidelity.ANALYTICAL,
            inside_validity=True,
            requires_escalation=False,
            uncertainty=0.0,
            detail=(
                "turbofan TSFC"
                if self.power_model == "turbofan"
                else "electric shaft efficiency"
            ),
        )


@dataclass(frozen=True, slots=True)
class AnalyticalRotorcraftParticipant:
    """Momentum-theory induced power plus profile and parasite power."""

    participant_id: str = "rotorcraft-analytical"
    disk_area_m2: float = 80.0
    figure_of_merit: float = 0.75
    profile_power_w: float = 50000.0
    parasite_flat_plate_m2: float = 2.0
    max_shaft_power_w: float = 2.0e6
    max_horizontal_thrust_n: float = 20000.0
    power_model: str = "turbofan"
    tsfc_kg_w_s: float = 8.0e-8
    fuel_lhv_j_kg: float = 0.0
    propeller_efficiency: float = 0.85
    thermal_load_fraction: float = 0.02
    atmosphere: StandardAtmosphere = field(default_factory=lambda: ISA)

    def __post_init__(self) -> None:
        if self.power_model not in {"turbofan", "electric"}:
            raise MissionContractError(f"UNKNOWN_POWER_MODEL:{self.power_model}")
        for label, value in (
            ("disk_area_m2", self.disk_area_m2),
            ("figure_of_merit", self.figure_of_merit),
            ("max_shaft_power_w", self.max_shaft_power_w),
        ):
            if not isfinite(value) or value <= 0.0:
                raise MissionContractError(f"ROTORCRAFT_PARAM_INVALID:{label}")

    def drag(self, point: OperatingPoint) -> AeroPoint:
        state = _atmosphere(self.atmosphere, point.altitude_m)
        density = state.density_kg_m3
        speed = point.speed_m_s
        drag = 0.5 * density * self.parasite_flat_plate_m2 * speed * speed
        return AeroPoint(
            drag_n=drag,
            lift_n=point.mass_kg * GRAVITY_M_S2,
            density_kg_m3=density,
            mach=speed / state.speed_of_sound_m_s,
            fidelity=MissionFidelity.ANALYTICAL,
            inside_validity=True,
            requires_escalation=False,
            uncertainty=0.0,
            detail="parasite flat plate",
        )

    def propulsion(self, point: OperatingPoint, thrust_n: float) -> PropulsionPoint:
        state = _atmosphere(self.atmosphere, point.altitude_m)
        density = state.density_kg_m3
        weight = point.mass_kg * GRAVITY_M_S2
        induced = (weight**1.5) / (sqrt(2.0 * density * self.disk_area_m2) * self.figure_of_merit)
        parasite = 0.5 * density * self.parasite_flat_plate_m2 * point.speed_m_s**3
        power = min(induced + self.profile_power_w + parasite, self.max_shaft_power_w)
        thrust = min(max(thrust_n, 0.0), self.max_horizontal_thrust_n)
        if self.power_model == "electric":
            fuel_flow = 0.0
            electrical = power / self.propeller_efficiency
        else:
            fuel_flow = self.tsfc_kg_w_s * power
            electrical = 0.0
        thermal = self.thermal_load_fraction * (fuel_flow * self.fuel_lhv_j_kg + electrical)
        return PropulsionPoint(
            thrust_n=thrust,
            fuel_flow_kg_s=fuel_flow,
            electrical_power_w=electrical,
            propulsive_power_w=power,
            thermal_load_w=thermal,
            available_thrust_n=self.max_horizontal_thrust_n,
            fidelity=MissionFidelity.ANALYTICAL,
            inside_validity=True,
            requires_escalation=False,
            uncertainty=0.0,
            detail="momentum theory induced + profile + parasite",
        )


@dataclass(frozen=True, slots=True)
class PerformanceMapParticipant:
    """Consumes validated #68 maps; rejects or escalates outside validity.

    A missing map for a requested capability fails closed. When the map would
    need to extrapolate and the policy is not ``REJECT`` the returned point
    carries ``requires_escalation`` plus the map's uncertainty; the mission
    evaluator then refuses to treat the result as trustworthy.
    """

    participant_id: str
    aero_inputs: Callable[[OperatingPoint], Mapping[str, float]]
    propulsion_inputs: Callable[[OperatingPoint, float], Mapping[str, float]]
    drag_map: PerformanceMap | None = None
    propulsion_map: PerformanceMap | None = None
    drag_output: str = "drag_n"
    lift_output: str | None = None
    fuel_flow_output: str = "fuel_flow_kg_s"
    electrical_power_output: str = "electrical_power_w"
    propulsive_power_output: str = "propulsive_power_w"
    available_thrust_output: str = "available_thrust_n"
    thermal_load_output: str | None = None
    policy: ExtrapolationPolicy = ExtrapolationPolicy.REJECT
    tolerances: tuple[tuple[str, float], ...] = ()

    def _consume(
        self, performance_map: PerformanceMap, point: Mapping[str, float]
    ) -> MapConsumption:
        try:
            return consume_map(
                performance_map,
                dict(point),
                tolerances=dict(self.tolerances),
                policy=self.policy,
            )
        except (ExtrapolationError, ValidationError) as exc:
            raise PerformanceRejected(
                f"PERFORMANCE_MAP_REJECTED:{self.participant_id}:{performance_map.map_id}:{exc}"
            ) from exc
        except RomError as exc:
            raise PerformanceRejected(
                f"PERFORMANCE_MAP_CONTRACT:{self.participant_id}:{exc}"
            ) from exc

    def drag(self, point: OperatingPoint) -> AeroPoint:
        if self.drag_map is None:
            raise PerformanceRejected(f"NO_AERO_MAP:{self.participant_id}")
        consumption = self._consume(self.drag_map, self.aero_inputs(point))
        outputs = consumption.outputs
        if self.drag_output not in outputs:
            raise PerformanceRejected(
                f"MAP_MISSING_OUTPUT:{self.drag_map.map_id}:{self.drag_output}"
            )
        lift = (
            outputs[self.lift_output]
            if self.lift_output is not None
            else point.mass_kg * GRAVITY_M_S2
        )
        return AeroPoint(
            drag_n=outputs[self.drag_output],
            lift_n=lift,
            density_kg_m3=0.0,
            mach=0.0,
            fidelity=MissionFidelity.REDUCED_MAP,
            inside_validity=consumption.inside_validity,
            requires_escalation=consumption.requires_escalation,
            uncertainty=max(consumption.uncertainty.values(), default=0.0),
            detail=";".join(consumption.reasons),
        )

    def propulsion(self, point: OperatingPoint, thrust_n: float) -> PropulsionPoint:
        if self.propulsion_map is None:
            raise PerformanceRejected(f"NO_PROPULSION_MAP:{self.participant_id}")
        propulsion_map = self.propulsion_map
        consumption = self._consume(propulsion_map, self.propulsion_inputs(point, thrust_n))
        outputs = consumption.outputs

        def value(name: str | None, default: float) -> float:
            if name is None:
                return default
            if name not in outputs:
                raise PerformanceRejected(f"MAP_MISSING_OUTPUT:{propulsion_map.map_id}:{name}")
            return outputs[name]

        return PropulsionPoint(
            thrust_n=thrust_n,
            fuel_flow_kg_s=value(self.fuel_flow_output, 0.0),
            electrical_power_w=value(self.electrical_power_output, 0.0),
            propulsive_power_w=value(self.propulsive_power_output, 0.0),
            thermal_load_w=value(self.thermal_load_output, 0.0),
            available_thrust_n=value(self.available_thrust_output, thrust_n),
            fidelity=MissionFidelity.REDUCED_MAP,
            inside_validity=consumption.inside_validity,
            requires_escalation=consumption.requires_escalation,
            uncertainty=max(consumption.uncertainty.values(), default=0.0),
            detail=";".join(consumption.reasons),
        )
