"""Low-cost generic propulsor aerodynamics: actuator disk and BEMT.

A blade-element/momentum screening solver integrates spanwise sections with
swirl, Prandtl tip/root loss corrections, advance ratio, thrust/torque/power
coefficients, propulsive efficiency, and tip-Mach checks, for both static and
forward-flight operation. Coaxial/contra-rotating pairs are evaluated with an
explicit upstream/downstream induced-flow coupling; the rear rotor is never
evaluated independently of the front rotor's wake. No duct or stator is
required, and native fidelity levels fail closed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan2, cos, exp, isfinite, pi, sin, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .geometry import PropellerGeometry
from .provenance import analytical_provenance
from .validity import (
    AeroFidelity,
    CapabilityUnavailable,
    PropulsorError,
    Validity,
    finite,
    integer,
    nonempty,
)

_DIRECTION_SIGN: dict[str, float] = {"clockwise": 1.0, "counterclockwise": -1.0}

MAX_TIP_MACH = 0.9


@dataclass(frozen=True, slots=True)
class BladeStation:
    """One blade-element station: radius, chord, twist and 2-D coefficients."""

    radius_m: float
    chord_m: float
    twist_deg: float
    lift_slope_per_rad: float = 2.0 * pi
    zero_lift_angle_deg: float = 0.0
    drag_coefficient: float = 0.012
    max_lift_coefficient: float = 1.1

    def __post_init__(self) -> None:
        finite(self.radius_m, "station.radius_m", positive=True)
        finite(self.chord_m, "station.chord_m", positive=True)
        finite(self.twist_deg, "station.twist_deg")
        finite(self.lift_slope_per_rad, "station.lift_slope_per_rad", positive=True)
        finite(self.zero_lift_angle_deg, "station.zero_lift_angle_deg")
        finite(self.drag_coefficient, "station.drag_coefficient", minimum=0.0)
        finite(self.max_lift_coefficient, "station.max_lift_coefficient", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "radiusM": self.radius_m,
            "chordM": self.chord_m,
            "twistDeg": self.twist_deg,
            "liftSlopePerRad": self.lift_slope_per_rad,
            "zeroLiftAngleDeg": self.zero_lift_angle_deg,
            "dragCoefficient": self.drag_coefficient,
            "maxLiftCoefficient": self.max_lift_coefficient,
        }


@dataclass(frozen=True, slots=True)
class RotorSpec:
    """A generic single-rotor aerodynamic definition."""

    rotor_id: str
    blade_count: int
    tip_radius_m: float
    hub_radius_m: float
    rpm: float
    direction: str
    shaft_id: str
    stations: tuple[BladeStation, ...]
    collective_pitch_deg: float = 0.0
    stall_angle_deg: float = 14.0

    def __post_init__(self) -> None:
        nonempty(self.rotor_id, "rotor.rotor_id")
        integer(self.blade_count, "rotor.blade_count", minimum=1, maximum=64)
        finite(self.tip_radius_m, "rotor.tip_radius_m", positive=True)
        finite(self.hub_radius_m, "rotor.hub_radius_m", positive=True)
        if self.hub_radius_m >= self.tip_radius_m:
            raise PropulsorError("rotor.hub_radius_m must be below tip")
        finite(self.rpm, "rotor.rpm", minimum=0.0)
        if self.direction not in _DIRECTION_SIGN:
            raise PropulsorError(f"rotor.direction unknown:{self.direction}")
        nonempty(self.shaft_id, "rotor.shaft_id")
        if len(self.stations) < 1:
            raise PropulsorError("rotor needs at least one station")
        finite(self.collective_pitch_deg, "rotor.collective_pitch_deg")
        finite(self.stall_angle_deg, "rotor.stall_angle_deg", positive=True)

    @property
    def diameter_m(self) -> float:
        return 2.0 * self.tip_radius_m

    @property
    def disk_area_m2(self) -> float:
        return pi * self.tip_radius_m * self.tip_radius_m

    @property
    def revolutions_per_second(self) -> float:
        return self.rpm / 60.0

    @property
    def direction_sign(self) -> float:
        return _DIRECTION_SIGN[self.direction]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "bladeCount": self.blade_count,
            "tipRadiusM": self.tip_radius_m,
            "hubRadiusM": self.hub_radius_m,
            "rpm": self.rpm,
            "direction": self.direction,
            "shaftId": self.shaft_id,
            "collectivePitchDeg": self.collective_pitch_deg,
            "stallAngleDeg": self.stall_angle_deg,
            "stations": [station.canonical_payload() for station in self.stations],
        }


@dataclass(frozen=True, slots=True)
class Inflow:
    """Freestream/installation inflow at the propulsor disk."""

    axial_velocity_m_s: float = 0.0
    density_kg_m3: float = 1.225
    speed_of_sound_m_s: float = 340.29
    swirl_velocity_m_s: float = 0.0
    yaw_deg: float = 0.0

    def __post_init__(self) -> None:
        finite(self.axial_velocity_m_s, "inflow.axial_velocity_m_s")
        finite(self.density_kg_m3, "inflow.density_kg_m3", positive=True)
        finite(self.speed_of_sound_m_s, "inflow.speed_of_sound_m_s", positive=True)
        finite(self.swirl_velocity_m_s, "inflow.swirl_velocity_m_s")
        finite(self.yaw_deg, "inflow.yaw_deg")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "axialVelocityMS": self.axial_velocity_m_s,
            "densityKgM3": self.density_kg_m3,
            "speedOfSoundMS": self.speed_of_sound_m_s,
            "swirlVelocityMS": self.swirl_velocity_m_s,
            "yawDeg": self.yaw_deg,
        }


@dataclass(frozen=True, slots=True)
class StationLoad:
    """Integrated blade-element state at one blade station."""

    radius_m: float
    axial_induction: float
    swirl_induction: float
    inflow_angle_deg: float
    angle_of_attack_deg: float
    lift_coefficient: float
    drag_coefficient: float
    tip_loss_factor: float
    thrust_n: float
    torque_n_m: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "radiusM": self.radius_m,
            "axialInduction": self.axial_induction,
            "swirlInduction": self.swirl_induction,
            "inflowAngleDeg": self.inflow_angle_deg,
            "angleOfAttackDeg": self.angle_of_attack_deg,
            "liftCoefficient": self.lift_coefficient,
            "dragCoefficient": self.drag_coefficient,
            "tipLossFactor": self.tip_loss_factor,
            "thrustN": self.thrust_n,
            "torqueNM": self.torque_n_m,
        }


@dataclass(frozen=True, slots=True)
class RotorAeroResult:
    """Integrated screening result for one rotor."""

    rotor_id: str
    fidelity: str
    thrust_n: float
    torque_n_m: float
    power_w: float
    advance_ratio: float
    thrust_coefficient: float
    torque_coefficient: float
    power_coefficient: float
    propulsive_efficiency: float
    induced_velocity_m_s: float
    tip_mach: float
    disk_area_m2: float
    axial_velocity_m_s: float
    station_loads: tuple[StationLoad, ...]
    coupling: str | None
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "thrust_n": "N",
            "torque_n_m": "N*m",
            "power_w": "W",
            "advance_ratio": "dimensionless",
            "thrust_coefficient": "dimensionless",
            "torque_coefficient": "dimensionless",
            "power_coefficient": "dimensionless",
            "propulsive_efficiency": "dimensionless",
            "induced_velocity_m_s": "m/s",
            "tip_mach": "dimensionless",
            "disk_area_m2": "m2",
        }

    @property
    def within_envelope(self) -> bool:
        return self.validity.passed

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "fidelity": self.fidelity,
            "thrustN": self.thrust_n,
            "torqueNM": self.torque_n_m,
            "powerW": self.power_w,
            "advanceRatio": self.advance_ratio,
            "thrustCoefficient": self.thrust_coefficient,
            "powerCoefficient": self.power_coefficient,
            "propulsiveEfficiency": self.propulsive_efficiency,
            "inducedVelocityMS": self.induced_velocity_m_s,
            "tipMach": self.tip_mach,
            "diskAreaM2": self.disk_area_m2,
        }


@dataclass(frozen=True, slots=True)
class ActuatorDiskResult:
    """Ideal actuator-disk momentum result for a declared disk loading."""

    disk_area_m2: float
    thrust_n: float
    axial_velocity_m_s: float
    induced_velocity_m_s: float
    ideal_power_w: float
    propulsive_efficiency: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "disk_area_m2": "m2",
            "thrust_n": "N",
            "axial_velocity_m_s": "m/s",
            "induced_velocity_m_s": "m/s",
            "ideal_power_w": "W",
            "propulsive_efficiency": "dimensionless",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "diskAreaM2": self.disk_area_m2,
            "thrustN": self.thrust_n,
            "inducedVelocityMS": self.induced_velocity_m_s,
            "idealPowerW": self.ideal_power_w,
            "propulsiveEfficiency": self.propulsive_efficiency,
        }


@dataclass(frozen=True, slots=True)
class CoaxialCoupling:
    """Explicit induced-flow coupling between two in-line rotors."""

    front_rotor_id: str
    rear_rotor_id: str
    axial_spacing_m: float
    downstream_axial_factor: float
    swirl_fraction: float
    front_induced_velocity_m_s: float
    rear_axial_inflow_m_s: float
    rear_swirl_inflow_m_s: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "frontRotorId": self.front_rotor_id,
            "rearRotorId": self.rear_rotor_id,
            "axialSpacingM": self.axial_spacing_m,
            "downstreamAxialFactor": self.downstream_axial_factor,
            "swirlFraction": self.swirl_fraction,
            "frontInducedVelocityMS": self.front_induced_velocity_m_s,
            "rearAxialInflowMS": self.rear_axial_inflow_m_s,
            "rearSwirlInflowMS": self.rear_swirl_inflow_m_s,
            "coupled": True,
        }


@dataclass(frozen=True, slots=True)
class CoaxialResult:
    """Coupled result for a coaxial/contra-rotating pair."""

    coupling: CoaxialCoupling
    front: RotorAeroResult
    rear: RotorAeroResult
    total_thrust_n: float
    total_torque_n_m: float
    total_power_w: float
    propulsive_efficiency: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "total_thrust_n": "N",
            "total_torque_n_m": "N*m",
            "total_power_w": "W",
            "propulsive_efficiency": "dimensionless",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "coupling": self.coupling.canonical_payload(),
            "front": self.front.canonical_payload(),
            "rear": self.rear.canonical_payload(),
            "totalThrustN": self.total_thrust_n,
            "totalTorqueNM": self.total_torque_n_m,
            "totalPowerW": self.total_power_w,
            "propulsiveEfficiency": self.propulsive_efficiency,
        }


def rotor_spec_from_geometry(
    geometry: PropellerGeometry,
    *,
    rpm: float,
    direction: str,
    shaft_id: str,
    collective_pitch_deg: float = 0.0,
    drag_coefficient: float = 0.012,
    max_lift_coefficient: float = 1.1,
) -> RotorSpec:
    """Build a screening rotor from real geometry distributions."""

    span = geometry.tip_radius_m - geometry.hub_radius_m
    stations = tuple(
        BladeStation(
            radius_m=geometry.hub_radius_m + section.radius_fraction * span,
            chord_m=section.chord_m,
            twist_deg=section.twist_deg,
            drag_coefficient=drag_coefficient,
            max_lift_coefficient=max_lift_coefficient,
        )
        for section in geometry.sections
        if geometry.hub_radius_m + section.radius_fraction * span > 0.0
    )
    return RotorSpec(
        rotor_id=geometry.rotor_id,
        blade_count=geometry.blade_count,
        tip_radius_m=geometry.tip_radius_m,
        hub_radius_m=geometry.hub_radius_m,
        rpm=rpm,
        direction=direction,
        shaft_id=shaft_id,
        stations=stations,
        collective_pitch_deg=collective_pitch_deg,
    )


def _interp_section(stations: tuple[BladeStation, ...], radius: float) -> BladeStation:
    ordered = sorted(stations, key=lambda station: station.radius_m)
    if radius <= ordered[0].radius_m:
        return ordered[0]
    if radius >= ordered[-1].radius_m:
        return ordered[-1]
    for lower, upper in zip(ordered, ordered[1:], strict=False):
        if lower.radius_m <= radius <= upper.radius_m:
            span = upper.radius_m - lower.radius_m
            fraction = (radius - lower.radius_m) / span if span > 0.0 else 0.0
            return BladeStation(
                radius_m=radius,
                chord_m=lower.chord_m + fraction * (upper.chord_m - lower.chord_m),
                twist_deg=lower.twist_deg + fraction * (upper.twist_deg - lower.twist_deg),
                lift_slope_per_rad=lower.lift_slope_per_rad
                + fraction * (upper.lift_slope_per_rad - lower.lift_slope_per_rad),
                zero_lift_angle_deg=lower.zero_lift_angle_deg
                + fraction * (upper.zero_lift_angle_deg - lower.zero_lift_angle_deg),
                drag_coefficient=lower.drag_coefficient
                + fraction * (upper.drag_coefficient - lower.drag_coefficient),
                max_lift_coefficient=lower.max_lift_coefficient
                + fraction * (upper.max_lift_coefficient - lower.max_lift_coefficient),
            )
    return ordered[-1]


def _annuli(
    rotor: RotorSpec,
) -> tuple[tuple[float, float, BladeStation], ...]:
    boundaries = sorted(
        {rotor.hub_radius_m, rotor.tip_radius_m, *(station.radius_m for station in rotor.stations)}
    )
    annuli: list[tuple[float, float, BladeStation]] = []
    for lower, upper in zip(boundaries, boundaries[1:], strict=False):
        if upper <= lower:
            continue
        midpoint = 0.5 * (lower + upper)
        annuli.append((midpoint, upper - lower, _interp_section(rotor.stations, midpoint)))
    return tuple(annuli)



def _prandtl_loss(
    blade_count: int,
    radius: float,
    tip_radius: float,
    hub_radius: float,
    sin_phi: float,
) -> float:
    if sin_phi <= 1e-9:
        return 1.0
    f_tip = (blade_count / 2.0) * (tip_radius - radius) / (radius * sin_phi)
    f_root = (blade_count / 2.0) * (radius - hub_radius) / (hub_radius * sin_phi)
    f_tip = max(f_tip, 0.0)
    f_root = max(f_root, 0.0)
    tip = (2.0 / pi) * acos(min(1.0, exp(-f_tip)))
    root = (2.0 / pi) * acos(min(1.0, exp(-f_root)))
    return max(tip * root, 1e-3)


def evaluate_actuator_disk(
    disk_area_m2: float,
    thrust_n: float,
    inflow: Inflow,
    *,
    rotor_id: str = "actuator-disk",
) -> ActuatorDiskResult:
    """Ideal actuator-disk momentum: induced velocity and ideal power."""

    finite(disk_area_m2, "actuator_disk.disk_area_m2", positive=True)
    finite(thrust_n, "actuator_disk.thrust_n", minimum=0.0)
    velocity = inflow.axial_velocity_m_s
    loading = thrust_n / (2.0 * inflow.density_kg_m3 * disk_area_m2)
    induced = -velocity / 2.0 + sqrt((velocity / 2.0) ** 2 + loading)
    ideal_power = thrust_n * (velocity + induced)
    efficiency = (thrust_n * velocity / ideal_power) if ideal_power > 0.0 else 0.0
    checks = {
        "thrust_nonnegative": thrust_n >= 0.0,
        "induced_velocity_nonnegative": induced >= 0.0,
        "ideal_power_positive": ideal_power >= 0.0,
    }
    provenance = analytical_provenance(
        "propulsors.aero.actuator-disk",
        {
            "rotorId": rotor_id,
            "diskAreaM2": disk_area_m2,
            "thrustN": thrust_n,
            "inflow": inflow.canonical_payload(),
        },
        assumptions=("Ideal uniform actuator disk; no swirl or profile loss.",),
    )
    return ActuatorDiskResult(
        disk_area_m2=disk_area_m2,
        thrust_n=thrust_n,
        axial_velocity_m_s=velocity,
        induced_velocity_m_s=induced,
        ideal_power_w=ideal_power,
        propulsive_efficiency=efficiency,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="ideal actuator-disk momentum theory",
        ),
        provenance=provenance,
    )


def evaluate_rotor(
    rotor: RotorSpec,
    inflow: Inflow,
    *,
    fidelity: AeroFidelity = AeroFidelity.BLADE_ELEMENT_MOMENTUM,
    tip_loss_correction: bool = True,
    max_iterations: int = 80,
    tolerance: float = 1e-9,
    relaxation: float = 0.35,
    coupling: str | None = None,
) -> RotorAeroResult:
    """Blade-element/momentum screening for a single rotor (static or forward)."""

    if fidelity.is_native:
        raise CapabilityUnavailable(
            f"{fidelity.value} is a native seam; use promote_to_native with a wired backend"
        )
    if fidelity is not AeroFidelity.BLADE_ELEMENT_MOMENTUM:
        raise PropulsorError(
            f"evaluate_rotor implements blade-element momentum, not {fidelity.value}"
        )
    integer(max_iterations, "max_iterations", minimum=1, maximum=10000)
    finite(tolerance, "tolerance", positive=True)
    finite(relaxation, "relaxation", positive=True, maximum=1.0)

    omega_abs = 2.0 * pi * rotor.revolutions_per_second
    omega_signed = rotor.direction_sign * omega_abs
    velocity = inflow.axial_velocity_m_s
    density = inflow.density_kg_m3
    annuli = _annuli(rotor)

    if omega_abs <= 0.0:
        provenance = _rotor_provenance(rotor, inflow, fidelity, tip_loss_correction)
        return RotorAeroResult(
            rotor_id=rotor.rotor_id,
            fidelity=fidelity.value,
            thrust_n=0.0,
            torque_n_m=0.0,
            power_w=0.0,
            advance_ratio=0.0,
            thrust_coefficient=0.0,
            torque_coefficient=0.0,
            power_coefficient=0.0,
            propulsive_efficiency=0.0,
            induced_velocity_m_s=0.0,
            tip_mach=0.0,
            disk_area_m2=rotor.disk_area_m2,
            axial_velocity_m_s=velocity,
            station_loads=(),
            coupling=coupling,
            validity=Validity(passed=True, checks={"non_rotating": True}, detail="rpm=0"),
            provenance=provenance,
        )

    station_loads: list[StationLoad] = []
    total_thrust = 0.0
    total_torque = 0.0
    induction_sum = 0.0
    weight_sum = 0.0
    max_alpha = 0.0
    stalled = False

    for radius, width, section in annuli:
        chord = section.chord_m
        theta = section.twist_deg + rotor.collective_pitch_deg
        vi = 0.0
        aprime = 0.0
        tip_loss = 1.0
        phi = 0.0
        alpha = 0.0
        cl = 0.0
        cd = section.drag_coefficient
        for _iteration in range(max_iterations):
            axial = velocity + vi
            tangential = omega_signed * radius * (1.0 - aprime) + inflow.swirl_velocity_m_s
            w2 = axial * axial + tangential * tangential
            phi = atan2(axial, tangential) if tangential != 0.0 else pi / 2.0
            alpha_rad = theta * pi / 180.0 - phi
            alpha = alpha_rad * 180.0 / pi
            raw_cl = section.lift_slope_per_rad * (
                alpha_rad - section.zero_lift_angle_deg * pi / 180.0
            )
            cl = max(
                -section.max_lift_coefficient,
                min(section.max_lift_coefficient, raw_cl),
            )
            cd = section.drag_coefficient
            sin_phi = sin(phi)
            tip_loss = (
                _prandtl_loss(
                    rotor.blade_count, radius, rotor.tip_radius_m, rotor.hub_radius_m, abs(sin_phi)
                )
                if tip_loss_correction
                else 1.0
            )
            cos_phi = cos(phi)
            common = 0.5 * density * w2 * rotor.blade_count * chord
            thrust_per_span = common * (cl * cos_phi - cd * sin_phi)
            torque_per_span = common * (cl * sin_phi + cd * cos_phi) * radius
            discriminant = velocity * velocity + thrust_per_span / (
                pi * radius * density * tip_loss
            )
            vi_target = max(0.0, 0.5 * (-velocity + sqrt(max(discriminant, 0.0))))
            torque_denominator = (
                4.0 * pi * radius**3 * density * (velocity + vi) * omega_signed * tip_loss
            )
            aprime_target = (
                torque_per_span / torque_denominator
                if abs(torque_denominator) > 1e-12
                else 0.0
            )
            aprime_target = max(-1.0, min(1.0, aprime_target))
            next_vi = relaxation * vi_target + (1.0 - relaxation) * vi
            next_aprime = relaxation * aprime_target + (1.0 - relaxation) * aprime
            converged = abs(next_vi - vi) <= tolerance * (1.0 + abs(vi)) and abs(
                next_aprime - aprime
            ) <= tolerance * (1.0 + abs(aprime))
            vi = next_vi
            aprime = next_aprime
            if converged:
                break
        axial = velocity + vi
        tangential = omega_signed * radius * (1.0 - aprime) + inflow.swirl_velocity_m_s
        w2 = axial * axial + tangential * tangential
        phi = atan2(axial, tangential) if tangential != 0.0 else pi / 2.0
        alpha = theta * pi / 180.0 - phi
        cos_phi = cos(phi)
        sin_phi = sin(phi)
        common = 0.5 * density * w2 * rotor.blade_count * chord
        thrust_per_span = common * (cl * cos_phi - cd * sin_phi)
        torque_per_span = common * (cl * sin_phi + cd * cos_phi) * radius
        total_thrust += thrust_per_span * width
        total_torque += torque_per_span * width
        induction_sum += vi * width
        weight_sum += width
        max_alpha = max(max_alpha, abs(alpha * 180.0 / pi))
        if abs(cl) >= section.max_lift_coefficient - 1e-9:
            stalled = True
        station_loads.append(
            StationLoad(
                radius_m=radius,
                axial_induction=vi / velocity if velocity > 0.0 else 0.0,
                swirl_induction=aprime,
                inflow_angle_deg=phi * 180.0 / pi,
                angle_of_attack_deg=alpha * 180.0 / pi,
                lift_coefficient=cl,
                drag_coefficient=cd,
                tip_loss_factor=tip_loss,
                thrust_n=thrust_per_span * width,
                torque_n_m=torque_per_span * width,
            )
        )

    power = omega_signed * total_torque
    n = rotor.revolutions_per_second
    diameter = rotor.diameter_m
    advance_ratio = velocity / (n * diameter) if n > 0.0 and diameter > 0.0 else 0.0
    thrust_coefficient = (
        total_thrust / (density * n * n * diameter**4)
        if n > 0.0 and diameter > 0.0
        else 0.0
    )
    torque_coefficient = (
        abs(total_torque) / (density * n * n * diameter**5)
        if n > 0.0 and diameter > 0.0
        else 0.0
    )
    power_coefficient = (
        abs(power) / (density * n**3 * diameter**5) if n > 0.0 and diameter > 0.0 else 0.0
    )
    efficiency = total_thrust * velocity / power if power > 1e-12 else 0.0
    induced_velocity = induction_sum / weight_sum if weight_sum > 0.0 else 0.0
    tip_mach = omega_abs * rotor.tip_radius_m / inflow.speed_of_sound_m_s
    checks = {
        "sections_within_stall": not stalled and max_alpha <= rotor.stall_angle_deg + 1e-9,
        "tip_mach_below_limit": tip_mach <= MAX_TIP_MACH,
        "induced_velocity_nonnegative": induced_velocity >= 0.0,
        "finite_outputs": all(
            isfinite(value)
            for value in (total_thrust, total_torque, power, efficiency, induced_velocity)
        ),
    }
    validity = Validity(
        passed=all(checks.values()),
        checks=checks,
        detail=(
            "blade-element momentum with Prandtl tip/root loss"
            if tip_loss_correction
            else "blade-element momentum without tip correction"
        ),
    )
    return RotorAeroResult(
        rotor_id=rotor.rotor_id,
        fidelity=fidelity.value,
        thrust_n=total_thrust,
        torque_n_m=total_torque,
        power_w=power,
        advance_ratio=advance_ratio,
        thrust_coefficient=thrust_coefficient,
        torque_coefficient=torque_coefficient,
        power_coefficient=power_coefficient,
        propulsive_efficiency=efficiency,
        induced_velocity_m_s=induced_velocity,
        tip_mach=tip_mach,
        disk_area_m2=rotor.disk_area_m2,
        axial_velocity_m_s=velocity,
        station_loads=tuple(station_loads),
        coupling=coupling,
        validity=validity,
        provenance=_rotor_provenance(rotor, inflow, fidelity, tip_loss_correction),
    )


def _rotor_provenance(
    rotor: RotorSpec,
    inflow: Inflow,
    fidelity: AeroFidelity,
    tip_loss_correction: bool,
) -> Provenance:
    return analytical_provenance(
        "propulsors.aero.blade-element-momentum",
        {
            "rotor": rotor.canonical_payload(),
            "inflow": inflow.canonical_payload(),
            "fidelity": fidelity.value,
            "tipLossCorrection": tip_loss_correction,
        },
        assumptions=(
            "Steady axisymmetric BEMT; 2-D section lift slope; Prandtl tip/root loss;"
            " profile drag coefficient constant.",
        ),
    )


def _swirl_at_reference(result: RotorAeroResult, rotor: RotorSpec) -> float:
    if not result.station_loads:
        return 0.0
    omega_signed = rotor.direction_sign * 2.0 * pi * rotor.revolutions_per_second
    reference = rotor.hub_radius_m + 0.75 * (rotor.tip_radius_m - rotor.hub_radius_m)
    nearest = min(result.station_loads, key=lambda load: abs(load.radius_m - reference))
    return nearest.swirl_induction * omega_signed * nearest.radius_m


def coaxial_coupling(
    front: RotorSpec,
    rear: RotorSpec,
    front_result: RotorAeroResult,
    *,
    axial_spacing_m: float,
    inflow: Inflow,
) -> CoaxialCoupling:
    """Compute the explicit front-to-rear induced-flow coupling."""

    finite(axial_spacing_m, "coaxial.axial_spacing_m", positive=True)
    if front.direction == rear.direction:
        raise PropulsorError("coaxial pair must rotate in opposite directions")
    radius = front.tip_radius_m
    decay = exp(-axial_spacing_m / (0.5 * radius))
    downstream_factor = 1.0 + (1.0 - decay)
    swirl_fraction = decay
    front_swirl_fixed = _swirl_at_reference(front_result, front)
    rear_axial = inflow.axial_velocity_m_s + downstream_factor * front_result.induced_velocity_m_s
    rear_swirl = swirl_fraction * front_swirl_fixed
    return CoaxialCoupling(
        front_rotor_id=front.rotor_id,
        rear_rotor_id=rear.rotor_id,
        axial_spacing_m=axial_spacing_m,
        downstream_axial_factor=downstream_factor,
        swirl_fraction=swirl_fraction,
        front_induced_velocity_m_s=front_result.induced_velocity_m_s,
        rear_axial_inflow_m_s=rear_axial,
        rear_swirl_inflow_m_s=rear_swirl,
    )


def evaluate_coaxial_pair(
    front: RotorSpec,
    rear: RotorSpec,
    *,
    axial_spacing_m: float,
    inflow: Inflow,
    tip_loss_correction: bool = True,
    max_iterations: int = 80,
    tolerance: float = 1e-9,
    relaxation: float = 0.35,
) -> CoaxialResult:
    """Evaluate a coaxial/contra-rotating pair with coupled induced flow."""

    if front.direction == rear.direction:
        raise PropulsorError("coaxial pair must rotate in opposite directions")
    front_result = evaluate_rotor(
        front,
        inflow,
        tip_loss_correction=tip_loss_correction,
        max_iterations=max_iterations,
        tolerance=tolerance,
        relaxation=relaxation,
        coupling="coaxial-front",
    )
    coupling = coaxial_coupling(
        front, rear, front_result, axial_spacing_m=axial_spacing_m, inflow=inflow
    )
    rear_inflow = Inflow(
        axial_velocity_m_s=coupling.rear_axial_inflow_m_s,
        density_kg_m3=inflow.density_kg_m3,
        speed_of_sound_m_s=inflow.speed_of_sound_m_s,
        swirl_velocity_m_s=coupling.rear_swirl_inflow_m_s,
        yaw_deg=inflow.yaw_deg,
    )
    rear_result = evaluate_rotor(
        rear,
        rear_inflow,
        tip_loss_correction=tip_loss_correction,
        max_iterations=max_iterations,
        tolerance=tolerance,
        relaxation=relaxation,
        coupling="coaxial-rear",
    )
    total_thrust = front_result.thrust_n + rear_result.thrust_n
    total_torque = front_result.torque_n_m + rear_result.torque_n_m
    total_power = front_result.power_w + rear_result.power_w
    velocity = inflow.axial_velocity_m_s
    efficiency = total_thrust * velocity / total_power if total_power > 1e-12 else 0.0
    checks = {
        "front_within_envelope": front_result.validity.passed,
        "rear_within_envelope": rear_result.validity.passed,
        "opposite_directions": front.direction != rear.direction,
        "coupled_induced_flow": coupling.downstream_axial_factor >= 1.0,
    }
    provenance = analytical_provenance(
        "propulsors.aero.coaxial-coupled",
        {
            "coupling": coupling.canonical_payload(),
            "front": front.canonical_payload(),
            "rear": rear.canonical_payload(),
            "inflow": inflow.canonical_payload(),
        },
        assumptions=(
            "Rear rotor inflow includes front-rotor axial induction and partially"
            " recovered swirl; rotors are never evaluated independently.",
        ),
    )
    return CoaxialResult(
        coupling=coupling,
        front=front_result,
        rear=rear_result,
        total_thrust_n=total_thrust,
        total_torque_n_m=total_torque,
        total_power_w=total_power,
        propulsive_efficiency=efficiency,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="coupled coaxial BEMT",
        ),
        provenance=provenance,
    )


__all__ = [
    "MAX_TIP_MACH",
    "ActuatorDiskResult",
    "BladeStation",
    "CoaxialCoupling",
    "CoaxialResult",
    "Inflow",
    "RotorAeroResult",
    "RotorSpec",
    "StationLoad",
    "coaxial_coupling",
    "evaluate_actuator_disk",
    "evaluate_coaxial_pair",
    "evaluate_rotor",
    "rotor_spec_from_geometry",
]
