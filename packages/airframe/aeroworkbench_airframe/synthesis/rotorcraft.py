"""Analytical shared-rotor physics for the AIRFRAME rotorcraft seam.

This module is a screening model, not a native/free-wake solver.  It reuses the
generic propulsor ``RotorSpec`` and station contracts, but adds the rotorcraft
controls and azimuthal terms that a propeller-only BEM model intentionally does
not own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import atan2, cos, degrees, exp, isfinite, pi, sin, sqrt

from aeroworkbench_core.types import Provenance
from aeroworkbench_propulsors import RotorSpec
from aeroworkbench_propulsors.provenance import analytical_provenance


class RotorcraftNativeUnavailable(RuntimeError):
    """Native/free-wake rotorcraft capability is not available at this seam."""


def _finite(value: float, name: str, *, minimum: float | None = None) -> float:
    value = float(value)
    if not isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"INVALID_ROTORCRAFT_VALUE:{name}")
    return value


@dataclass(frozen=True, slots=True)
class RotorcraftControls:
    collective_rad: float = 0.0
    longitudinal_cyclic_rad: float = 0.0
    lateral_cyclic_rad: float = 0.0


@dataclass(frozen=True, slots=True)
class RotorcraftFlightCondition:
    velocity_m_s: tuple[float, float, float] = (0.0, 0.0, 0.0)
    density_kg_m3: float = 1.225
    speed_of_sound_m_s: float = 340.29

    def __post_init__(self) -> None:
        if len(self.velocity_m_s) != 3:
            raise ValueError("ROTORCRAFT_VELOCITY_REQUIRED")
        for value in self.velocity_m_s:
            _finite(value, "velocity_m_s")
        _finite(self.density_kg_m3, "density_kg_m3", minimum=1e-9)
        _finite(self.speed_of_sound_m_s, "speed_of_sound_m_s", minimum=1e-9)


@dataclass(frozen=True, slots=True)
class RotorcraftLimits:
    max_tip_mach: float = 0.9
    max_retreating_angle_deg: float = 14.0


@dataclass(frozen=True, slots=True)
class RotorcraftRotor:
    spec: RotorSpec
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    flapping_stiffness: float = 1.0
    lead_lag_hook: Callable[[float, float], float] | None = None
    torsion_hook: Callable[[float, float], float] | None = None


@dataclass(frozen=True, slots=True)
class FlappingState:
    longitudinal_rad: float
    lateral_rad: float
    lead_lag_rad: float
    torsion_rad: float


@dataclass(frozen=True, slots=True)
class RotorcraftLoads:
    thrust_n: float
    torque_n_m: float
    hub_force_n: tuple[float, float, float]
    hub_moment_n_m: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class WakeExchange:
    source_rotor_id: str
    target_rotor_id: str
    incoming_axial_velocity_m_s: float
    incoming_swirl_velocity_m_s: float
    overlap_fraction: float
    model: str = "analytical-actuator-disk-wake"


@dataclass(frozen=True, slots=True)
class RotorcraftResult:
    rotor_id: str
    controls: RotorcraftControls
    loads: RotorcraftLoads
    induced_velocity_m_s: float
    azimuthal_loads: tuple[float, ...]
    flapping: FlappingState
    valid: bool
    violations: tuple[str, ...]
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class RotorcraftAssemblyResult:
    rotors: tuple[RotorcraftResult, ...]
    wake_exchange: tuple[WakeExchange, ...]
    valid: bool
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class RotorcraftTrimResult:
    result: RotorcraftResult
    controls: RotorcraftControls
    converged: bool
    provenance: Provenance


def _provenance(rotor_ids: Iterable[str], condition: RotorcraftFlightCondition) -> Provenance:
    return analytical_provenance(
        "airframe.rotorcraft.shared-rotor-bemt",
        {"rotors": list(rotor_ids), "condition": condition.velocity_m_s},
        assumptions=(
            "Analytical azimuthal blade-element loading with momentum induced inflow.",
            "Free-wake/native solver is not used; loads are screening evidence.",
        ),
    )


def _evaluate(
    rotor: RotorcraftRotor,
    condition: RotorcraftFlightCondition,
    controls: RotorcraftControls,
    limits: RotorcraftLimits,
    *,
    axial_wake_m_s: float = 0.0,
    azimuth_count: int = 36,
) -> RotorcraftResult:
    spec = rotor.spec
    rho = condition.density_kg_m3
    vx, vy, vz = condition.velocity_m_s
    omega = 2.0 * pi * spec.revolutions_per_second
    if omega <= 0.0:
        raise ValueError("ROTORCRAFT_RPM_REQUIRED")
    annuli = sorted(spec.stations, key=lambda station: station.radius_m)
    dr = (spec.tip_radius_m - spec.hub_radius_m) / max(len(annuli), 1)
    induced = max(0.0, sqrt(max(0.0, abs(vz + axial_wake_m_s) ** 2 / 4.0)))
    azimuthal: list[float] = []
    samples: list[tuple[float, float, float, float, float]] = []
    for _ in range(18):
        thrust_sum = 0.0
        torque_sum = 0.0
        azimuthal.clear()
        samples.clear()
        for index in range(azimuth_count):
            psi = 2.0 * pi * index / azimuth_count
            local_thrust = 0.0
            local_torque = 0.0
            for station in annuli:
                tangential = omega * station.radius_m + vx * sin(psi) - vy * cos(psi)
                axial = vz + axial_wake_m_s + induced
                speed = max(sqrt(tangential * tangential + axial * axial), 1e-6)
                inflow_angle = atan2(axial, abs(tangential))
                pitch = (
                    controls.collective_rad
                    + controls.longitudinal_cyclic_rad * cos(psi)
                    + controls.lateral_cyclic_rad * sin(psi)
                    + station.twist_deg * pi / 180.0
                )
                alpha = pitch - inflow_angle
                cl = max(
                    -station.max_lift_coefficient,
                    min(station.max_lift_coefficient, station.lift_slope_per_rad * alpha),
                )
                cd = station.drag_coefficient + 0.01 * cl * cl
                dynamic = 0.5 * rho * speed * speed * station.chord_m * dr
                normal = dynamic * (cl * cos(inflow_angle) - cd * sin(inflow_angle))
                tangential_force = dynamic * (cl * sin(inflow_angle) + cd * cos(inflow_angle))
                local_thrust += spec.blade_count * normal
                local_torque += spec.blade_count * tangential_force * station.radius_m
                samples.append((psi, tangential, degrees(alpha), speed, cl))
            thrust_sum += local_thrust
            torque_sum += local_torque
            azimuthal.append(local_thrust)
        thrust = max(thrust_sum / azimuth_count, 0.0)
        torque = max(torque_sum / azimuth_count, 0.0)
        target = max(
            0.0,
            sqrt(thrust / (2.0 * rho * spec.disk_area_m2)) - (vz + axial_wake_m_s) / 2.0,
        )
        induced = 0.55 * induced + 0.45 * target

    azimuths = (2.0 * pi * i / azimuth_count for i in range(azimuth_count))
    mean_flap_x = sum(load * cos(psi) for load, psi in zip(azimuthal, azimuths, strict=False))
    azimuths = (2.0 * pi * i / azimuth_count for i in range(azimuth_count))
    mean_flap_y = sum(load * sin(psi) for load, psi in zip(azimuthal, azimuths, strict=False))
    flap_scale = rotor.flapping_stiffness * max(thrust, 1.0) * spec.tip_radius_m
    flap = FlappingState(
        mean_flap_x / flap_scale,
        mean_flap_y / flap_scale,
        rotor.lead_lag_hook(induced, thrust) if rotor.lead_lag_hook else 0.0,
        rotor.torsion_hook(thrust, controls.collective_rad) if rotor.torsion_hook else 0.0,
    )
    hub_x = (
        sum(load * sin(2.0 * pi * i / azimuth_count) for i, load in enumerate(azimuthal))
        / azimuth_count
    )
    hub_y = (
        sum(load * cos(2.0 * pi * i / azimuth_count) for i, load in enumerate(azimuthal))
        / azimuth_count
    )
    tip_speed = sqrt((omega * spec.tip_radius_m) ** 2 + max(abs(vx), abs(vy)) ** 2)
    violations: list[str] = []
    if tip_speed / condition.speed_of_sound_m_s > limits.max_tip_mach:
        violations.append("ADVANCING_TIP_MACH")
    for _psi, tangential, alpha_deg, _speed, _ in samples:
        if tangential < 0.0 and abs(alpha_deg) > limits.max_retreating_angle_deg:
            violations.append("RETREATING_BLADE_STALL")
            break
    provenance = _provenance((spec.rotor_id,), condition)
    return RotorcraftResult(
        spec.rotor_id,
        controls,
        RotorcraftLoads(
            thrust,
            torque,
            (hub_x, hub_y, thrust),
            (
                hub_y * spec.tip_radius_m,
                -hub_x * spec.tip_radius_m,
                spec.direction_sign * torque,
            ),
        ),
        induced,
        tuple(azimuthal),
        flap,
        not violations,
        tuple(violations),
        provenance,
    )


def evaluate_rotorcraft(
    rotor: RotorcraftRotor,
    condition: RotorcraftFlightCondition,
    controls: RotorcraftControls | None = None,
    *,
    limits: RotorcraftLimits | None = None,
    fidelity: str = "analytical",
) -> RotorcraftResult:
    """Evaluate one rotor with collective, cyclic, inflow coupling, and limits."""
    if fidelity == "native":
        raise RotorcraftNativeUnavailable("NATIVE_ROTORCRAFT_RECEIPT_REQUIRED")
    if fidelity != "analytical":
        raise ValueError("ROTORCRAFT_FIDELITY_UNSUPPORTED")
    return _evaluate(
        rotor,
        condition,
        controls or RotorcraftControls(),
        limits or RotorcraftLimits(),
    )


def _wake(
    source: RotorcraftRotor,
    target: RotorcraftRotor,
    result: RotorcraftResult,
) -> WakeExchange:
    dx = target.position_m[0] - source.position_m[0]
    dy = target.position_m[1] - source.position_m[1]
    distance = sqrt(dx * dx + dy * dy)
    overlap = max(0.0, 1.0 - distance / source.spec.tip_radius_m)
    downstream = target.position_m[2] < source.position_m[2]
    overlap = overlap if downstream else 0.0
    factor = overlap * exp(
        -abs(target.position_m[2] - source.position_m[2]) / max(source.spec.tip_radius_m, 1e-9)
    )
    return WakeExchange(
        source.spec.rotor_id,
        target.spec.rotor_id,
        result.induced_velocity_m_s * factor,
        result.induced_velocity_m_s * 0.1 * source.spec.direction_sign * factor,
        factor,
    )


def evaluate_rotorcraft_assembly(
    rotors: tuple[RotorcraftRotor, ...],
    condition: RotorcraftFlightCondition,
    controls: RotorcraftControls | None = None,
    *,
    limits: RotorcraftLimits | None = None,
) -> RotorcraftAssemblyResult:
    """Evaluate multiple rotors in one shared wake field, including coaxial rows."""
    if not rotors:
        raise ValueError("ROTORCRAFT_ROTORS_REQUIRED")
    controls = controls or RotorcraftControls()
    limits = limits or RotorcraftLimits()
    results: list[RotorcraftResult] = []
    exchanges: list[WakeExchange] = []
    for rotor in rotors:
        incoming = 0.0
        for source, source_result in zip(rotors, results, strict=False):
            exchange = _wake(source, rotor, source_result)
            exchanges.append(exchange)
            incoming += exchange.incoming_axial_velocity_m_s
        results.append(_evaluate(rotor, condition, controls, limits, axial_wake_m_s=incoming))
    return RotorcraftAssemblyResult(
        tuple(results),
        tuple(exchanges),
        all(result.valid for result in results),
        _provenance((rotor.spec.rotor_id for rotor in rotors), condition),
    )


def trim_rotorcraft(
    rotor: RotorcraftRotor,
    condition: RotorcraftFlightCondition,
    *,
    target_thrust_n: float,
    target_hub_moment_n_m: tuple[float, float] = (0.0, 0.0),
    limits: RotorcraftLimits | None = None,
) -> RotorcraftTrimResult:
    """Close a small analytical collective/cyclic trim loop."""
    _finite(target_thrust_n, "target_thrust_n", minimum=0.0)
    controls = RotorcraftControls()
    result = evaluate_rotorcraft(rotor, condition, controls, limits=limits)
    for _ in range(24):
        thrust_error = target_thrust_n - result.loads.thrust_n
        if abs(thrust_error) <= max(1.0, 0.02 * target_thrust_n):
            return RotorcraftTrimResult(result, controls, True, result.provenance)
        controls = RotorcraftControls(
            collective_rad=max(
                -0.2,
                min(
                    0.7,
                    controls.collective_rad + thrust_error / max(target_thrust_n, 1.0) * 0.08,
                ),
            ),
            longitudinal_cyclic_rad=controls.longitudinal_cyclic_rad
            + (target_hub_moment_n_m[0] - result.loads.hub_moment_n_m[0])
            / max(target_thrust_n * rotor.spec.tip_radius_m, 1.0)
            * 0.03,
            lateral_cyclic_rad=controls.lateral_cyclic_rad
            + (target_hub_moment_n_m[1] - result.loads.hub_moment_n_m[1])
            / max(target_thrust_n * rotor.spec.tip_radius_m, 1.0)
            * 0.03,
        )
        result = evaluate_rotorcraft(rotor, condition, controls, limits=limits)
    return RotorcraftTrimResult(result, controls, False, result.provenance)


__all__ = [
    "FlappingState",
    "RotorcraftAssemblyResult",
    "RotorcraftControls",
    "RotorcraftFlightCondition",
    "RotorcraftLimits",
    "RotorcraftLoads",
    "RotorcraftNativeUnavailable",
    "RotorcraftResult",
    "RotorcraftRotor",
    "RotorcraftTrimResult",
    "WakeExchange",
    "evaluate_rotorcraft",
    "evaluate_rotorcraft_assembly",
    "trim_rotorcraft",
]
