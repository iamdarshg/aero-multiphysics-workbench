"""Analytical two-way rotor/installed-airframe coupling for AIRFRAME Lane C."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt

from aeroworkbench_core.composition import (
    ComposedPort,
    check_compatible,
    fluid_port,
    mechanical_port,
)
from aeroworkbench_core.types import Provenance
from aeroworkbench_propulsors.provenance import analytical_provenance

from .rotorcraft import (
    RotorcraftControls,
    RotorcraftFlightCondition,
    RotorcraftResult,
    RotorcraftRotor,
    RotorWakeField,
    evaluate_rotorcraft,
    rotor_wake_field,
)

_Vector3 = tuple[float, float, float]


class RotorAirframeNativeUnavailable(RuntimeError):
    """Native/free-wake installed coupling is unavailable without a receipt."""


def _vector(value: Iterable[float], name: str) -> _Vector3:
    result = tuple(float(item) for item in value)
    if len(result) != 3 or any(not isfinite(item) for item in result):
        raise ValueError(f"{name}_INVALID")
    first, second, third = result
    return (first, second, third)


@dataclass(frozen=True, slots=True)
class RotorAirframeSurface:
    """A low-order installed wing, body, or tail interaction surface."""

    surface_id: str
    frame: str
    points_m: tuple[_Vector3, ...]
    areas_m2: tuple[float, ...]
    normal: _Vector3 = (0.0, 0.0, 1.0)
    angle_of_attack_rad: float = 0.08
    lift_slope_per_rad: float = 4.5
    drag_coefficient: float = 0.03
    rotor_feedback_factor: float = 0.05

    def __post_init__(self) -> None:
        if not self.surface_id.strip() or not self.frame.strip():
            raise ValueError("ROTOR_AIRFRAME_SURFACE_ID_REQUIRED")
        if len(self.points_m) != len(self.areas_m2) or len(self.points_m) < 2:
            raise ValueError("ROTOR_AIRFRAME_SURFACE_NODES_INVALID")
        points = tuple(
            _vector(point, "ROTOR_AIRFRAME_SURFACE_POINT") for point in self.points_m
        )
        if any(not isfinite(area) or area <= 0.0 for area in self.areas_m2):
            raise ValueError("ROTOR_AIRFRAME_SURFACE_AREAS_INVALID")
        normal = _vector(self.normal, "ROTOR_AIRFRAME_SURFACE_NORMAL")
        magnitude = sqrt(sum(value * value for value in normal))
        if magnitude <= 1e-12:
            raise ValueError("ROTOR_AIRFRAME_SURFACE_NORMAL_INVALID")
        object.__setattr__(self, "points_m", points)
        object.__setattr__(
            self, "areas_m2", tuple(float(area) for area in self.areas_m2)
        )
        object.__setattr__(self, "normal", tuple(value / magnitude for value in normal))


@dataclass(frozen=True, slots=True)
class RotorSurfaceLoad:
    surface_id: str
    local_velocity_m_s: _Vector3
    force_n: _Vector3
    moment_n_m: _Vector3
    wake_fraction: float


@dataclass(frozen=True, slots=True)
class VehicleTrimEffects:
    force_n: _Vector3
    hub_moment_n_m: _Vector3
    thrust_line_moment_n_m: _Vector3
    total_moment_n_m: _Vector3


@dataclass(frozen=True, slots=True)
class RotorAirframeCouplingResult:
    rotor_result: RotorcraftResult
    wake_field: RotorWakeField
    surface_loads: tuple[RotorSurfaceLoad, ...]
    vehicle_trim: VehicleTrimEffects
    airframe_feedback_m_s: float
    iterations: int
    residual_trace: tuple[float, ...]
    converged: bool
    flow_port: ComposedPort
    load_port: ComposedPort
    provenance: Provenance


def _cross(a: _Vector3, b: _Vector3) -> _Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def couple_rotor_airframe(
    rotor: RotorcraftRotor,
    condition: RotorcraftFlightCondition,
    surfaces: tuple[RotorAirframeSurface, ...],
    controls: RotorcraftControls | None = None,
    *,
    thrust_line_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
    max_iterations: int = 20,
    tolerance: float = 1e-4,
    relaxation: float = 0.6,
    fidelity: str = "analytical",
) -> RotorAirframeCouplingResult:
    """Solve rotor local flow <-> installed surface loads to a fixed point."""
    if fidelity == "native":
        raise RotorAirframeNativeUnavailable("NATIVE_FREE_WAKE_RECEIPT_REQUIRED")
    if fidelity != "analytical":
        raise ValueError("ROTOR_AIRFRAME_FIDELITY_UNSUPPORTED")
    if max_iterations <= 0 or tolerance <= 0.0 or not 0.0 < relaxation <= 1.0:
        raise ValueError("ROTOR_AIRFRAME_COUPLING_SETTINGS_INVALID")
    thrust_line = _vector(thrust_line_m, "THRUST_LINE")
    # These are generic contracts, not a new airframe-specific coupling schema.
    flow_port = fluid_port("rotor-wake", "velocity", "m/s", "out", "body")
    airframe_flow_port = fluid_port("airframe-flow", "velocity", "m/s", "in", "body")
    load_port = mechanical_port("rotor-load", "force", "N", "out", "body")
    vehicle_load_port = mechanical_port("vehicle-load", "force", "N", "in", "body")
    check_compatible(flow_port, airframe_flow_port)
    check_compatible(load_port, vehicle_load_port)

    points = tuple(point for surface in surfaces for point in surface.points_m)
    feedback = 0.0
    trace: list[float] = []
    rotor_result = evaluate_rotorcraft(rotor, condition, controls)
    wake = rotor_wake_field(rotor, rotor_result, condition, points)
    loads: tuple[RotorSurfaceLoad, ...] = ()
    for _iteration in range(1, max_iterations + 1):
        effective = RotorcraftFlightCondition(
            velocity_m_s=(
                condition.velocity_m_s[0],
                condition.velocity_m_s[1],
                condition.velocity_m_s[2] + feedback,
            ),
            density_kg_m3=condition.density_kg_m3,
            speed_of_sound_m_s=condition.speed_of_sound_m_s,
        )
        rotor_result = evaluate_rotorcraft(rotor, effective, controls)
        wake = rotor_wake_field(rotor, rotor_result, effective, points)
        loads_list: list[RotorSurfaceLoad] = []
        offset = 0
        next_feedback = 0.0
        for surface in surfaces:
            local = wake.local_velocities_m_s[offset : offset + len(surface.points_m)]
            induced = wake.induced_flow_m_s[offset : offset + len(surface.points_m)]
            offset += len(surface.points_m)
            mean_velocity: _Vector3 = (
                sum(point[0] for point in local) / len(local),
                sum(point[1] for point in local) / len(local),
                sum(point[2] for point in local) / len(local),
            )
            mean_induced = sum(-point[2] for point in induced) / len(induced)
            speed = max(sqrt(sum(value * value for value in mean_velocity)), 1e-6)
            area = sum(surface.areas_m2)
            dynamic = 0.5 * effective.density_kg_m3 * speed * speed
            lift = (
                dynamic
                * area
                * surface.lift_slope_per_rad
                * surface.angle_of_attack_rad
            )
            drag = dynamic * area * surface.drag_coefficient
            force: _Vector3 = (
                lift * surface.normal[0] - drag,
                lift * surface.normal[1],
                lift * surface.normal[2],
            )
            reference = surface.points_m[0]
            moment = _cross(reference, force)
            loads_list.append(
                RotorSurfaceLoad(
                    surface.surface_id,
                    mean_velocity,
                    force,
                    moment,
                    min(
                        1.0, mean_induced / max(rotor_result.induced_velocity_m_s, 1e-9)
                    ),
                )
            )
            next_feedback += surface.rotor_feedback_factor * mean_induced
        loads = tuple(loads_list)
        residual = abs(next_feedback - feedback)
        trace.append(residual)
        feedback += relaxation * (next_feedback - feedback)
        if residual <= tolerance:
            break

    airframe_force: _Vector3 = (
        sum(load.force_n[0] for load in loads),
        sum(load.force_n[1] for load in loads),
        sum(load.force_n[2] for load in loads),
    )
    vehicle_force: _Vector3 = (
        rotor_result.loads.hub_force_n[0] + airframe_force[0],
        rotor_result.loads.hub_force_n[1] + airframe_force[1],
        rotor_result.loads.hub_force_n[2] + airframe_force[2],
    )
    thrust_line_moment = _cross(thrust_line, rotor_result.loads.hub_force_n)
    surface_moment: _Vector3 = (
        sum(load.moment_n_m[0] for load in loads),
        sum(load.moment_n_m[1] for load in loads),
        sum(load.moment_n_m[2] for load in loads),
    )
    total_moment: _Vector3 = (
        rotor_result.loads.hub_moment_n_m[0]
        + thrust_line_moment[0]
        + surface_moment[0],
        rotor_result.loads.hub_moment_n_m[1]
        + thrust_line_moment[1]
        + surface_moment[1],
        rotor_result.loads.hub_moment_n_m[2]
        + thrust_line_moment[2]
        + surface_moment[2],
    )
    trim = VehicleTrimEffects(
        vehicle_force,
        rotor_result.loads.hub_moment_n_m,
        thrust_line_moment,
        total_moment,
    )
    provenance = analytical_provenance(
        "airframe.rotorcraft.rotor-airframe-coupling",
        {
            "rotor": rotor.spec.rotor_id,
            "surfaces": [surface.surface_id for surface in surfaces],
            "iterations": len(trace),
        },
        assumptions=(
            "Analytical BEM rotor and low-order installed surface interaction.",
            "Native free-wake is capability-gated.",
        ),
    )
    return RotorAirframeCouplingResult(
        rotor_result,
        wake,
        loads,
        trim,
        feedback,
        len(trace),
        tuple(trace),
        bool(trace and trace[-1] <= tolerance),
        flow_port,
        load_port,
        provenance,
    )


__all__ = [
    "RotorAirframeCouplingResult",
    "RotorAirframeNativeUnavailable",
    "RotorAirframeSurface",
    "RotorSurfaceLoad",
    "VehicleTrimEffects",
    "couple_rotor_airframe",
]
