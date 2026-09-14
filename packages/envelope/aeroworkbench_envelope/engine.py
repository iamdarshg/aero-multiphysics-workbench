"""Deterministic, explicitly analytical installed-EDF envelope workflow.

This module is a useful whole-aircraft contract and screening model. It does not
claim to replace a high-fidelity external-flow or aeroelastic solver: every
result carries analytical provenance and the workflow refuses unbounded sweeps.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from itertools import product
from math import isfinite, radians, sin

from aeroworkbench_core.envelope import AircraftDefinition
from aeroworkbench_core.models.common import analytical_provenance
from aeroworkbench_core.models.edf import EDFInput, evaluate_edf
from aeroworkbench_geometry import GeometryModel, shape_hash


class Region(StrEnum):
    VIABLE = "viable"
    CONSTRAINED = "constrained"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FlightCondition:
    """One point in the operating-envelope parameter space."""

    airspeed_m_s: float
    mach: float
    altitude_m: float
    density_kg_m3: float
    temperature_k: float
    angle_of_attack_deg: float = 0.0
    sideslip_deg: float = 0.0
    body_rate_dps: float = 0.0
    load_factor: float = 1.0
    control_authority: float = 1.0
    thrust_command_n: float = 0.0
    rpm: float = 45_000.0
    current_a: float = 35.0
    soc: float = 0.8

    def __post_init__(self) -> None:
        nonnegative = {
            "mach": self.mach,
            "altitude_m": self.altitude_m,
            "body_rate_dps": self.body_rate_dps,
            "thrust_command_n": self.thrust_command_n,
            "current_a": self.current_a,
        }
        positive = {
            "airspeed_m_s": self.airspeed_m_s,
            "density_kg_m3": self.density_kg_m3,
            "temperature_k": self.temperature_k,
            "load_factor": self.load_factor,
            "rpm": self.rpm,
        }
        entries = (
            *nonnegative.items(),
            *positive.items(),
            ("soc", self.soc),
            ("control_authority", self.control_authority),
        )
        for name, value in entries:
            if not isfinite(value):
                raise ValueError(f"NONFINITE_FLIGHT_CONDITION:{name}")
        if any(value < 0 for value in nonnegative.values()):
            raise ValueError("NEGATIVE_FLIGHT_CONDITION")
        if any(value <= 0 for value in positive.values()):
            raise ValueError("NONPOSITIVE_FLIGHT_CONDITION")
        if not 0 <= self.control_authority <= 1:
            raise ValueError("CONTROL_AUTHORITY_OUT_OF_RANGE")
        if not 0 <= self.soc <= 1:
            raise ValueError("SOC_OUT_OF_RANGE")


@dataclass(frozen=True, slots=True)
class EnvelopeConstraints:
    max_mach: float = 0.85
    max_current_a: float = 80.0
    max_temperature_k: float = 360.0
    max_load_factor: float = 8.0
    min_soc: float = 0.15
    min_control_authority: float = 0.55

    def __post_init__(self) -> None:
        limits = (
            self.max_mach,
            self.max_current_a,
            self.max_temperature_k,
            self.max_load_factor,
        )
        for value in limits:
            if not isfinite(value) or value <= 0:
                raise ValueError("INVALID_ENVELOPE_CONSTRAINT")
        if not 0 <= self.min_soc <= 1 or not 0 <= self.min_control_authority <= 1:
            raise ValueError("ENVELOPE_CONSTRAINT_OUT_OF_RANGE")


@dataclass(frozen=True, slots=True)
class EvaluatedCondition:
    condition: FlightCondition
    required_thrust_n: float
    available_thrust_n: float
    margins: tuple[tuple[str, float], ...]
    region: Region
    violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoundaryRefinement:
    source_points: int
    inserted_points: int
    max_depth: int
    converged: bool


@dataclass(frozen=True, slots=True)
class AircraftEnvelope:
    points: tuple[EvaluatedCondition, ...]
    refinement: BoundaryRefinement
    geometry_hash: str | None
    provenance: object


def _midpoint(left: FlightCondition, right: FlightCondition) -> FlightCondition:
    values = {
        field: (getattr(left, field) + getattr(right, field)) / 2
        for field in FlightCondition.__dataclass_fields__
    }
    return FlightCondition(**values)


def _evaluate_condition(
    aircraft: AircraftDefinition,
    constraints: EnvelopeConstraints,
    condition: FlightCondition,
    *,
    edf_diameter_m: float,
    edf_hub_diameter_m: float,
) -> EvaluatedCondition:
    dynamic_pressure = 0.5 * condition.density_kg_m3 * condition.airspeed_m_s**2
    load_lift = aircraft.mass_kg * 9.81 * condition.load_factor
    lift_coefficient = load_lift / (dynamic_pressure * aircraft.wing_area_m2)
    incidence_factor = 1 + 0.35 * abs(sin(radians(condition.angle_of_attack_deg)))
    sideslip_factor = 1 + 0.20 * abs(sin(radians(condition.sideslip_deg)))
    rate_factor = 1 + 0.01 * condition.body_rate_dps
    required_thrust = dynamic_pressure * aircraft.wing_area_m2 * (
        aircraft.cd0 + aircraft.induced_drag_factor * lift_coefficient**2
    ) * incidence_factor * sideslip_factor * rate_factor
    edf = evaluate_edf(
        EDFInput(
            fan_diameter_m=edf_diameter_m,
            hub_diameter_m=edf_hub_diameter_m,
            shaft_power_w=max(1.0, 0.018 * condition.rpm * condition.current_a),
            fan_efficiency=0.70,
            air_density_kg_m3=condition.density_kg_m3,
            freestream_velocity_m_s=condition.airspeed_m_s,
            speed_rpm=condition.rpm,
            blade_count=12,
            stator_count=9,
        )
    )
    if condition.thrust_command_n > 0:
        available_thrust = min(edf.thrust_n, condition.thrust_command_n)
    else:
        available_thrust = edf.thrust_n
    temperature_estimate = (
        condition.temperature_k + 0.16 * condition.current_a + 0.8 * condition.body_rate_dps
    )
    margins = (
        ("thrust", (available_thrust - required_thrust) / max(required_thrust, 1e-9)),
        ("mach", (constraints.max_mach - condition.mach) / constraints.max_mach),
        ("current", (constraints.max_current_a - condition.current_a) / constraints.max_current_a),
        (
            "temperature",
            (constraints.max_temperature_k - temperature_estimate)
            / constraints.max_temperature_k,
        ),
        (
            "load_factor",
            (constraints.max_load_factor - condition.load_factor)
            / constraints.max_load_factor,
        ),
        ("soc", (condition.soc - constraints.min_soc) / max(1 - constraints.min_soc, 1e-9)),
        (
            "control_authority",
            (condition.control_authority - constraints.min_control_authority)
            / max(1 - constraints.min_control_authority, 1e-9),
        ),
    )
    violations = [name for name, margin in margins if margin < 0]
    near_limit = any(margin < 0.10 for _, margin in margins)
    if violations:
        region = Region.FAILED
    elif near_limit:
        region = Region.CONSTRAINED
    else:
        region = Region.VIABLE
    return EvaluatedCondition(
        condition, required_thrust, available_thrust, margins, region, tuple(violations)
    )


def refine_boundary(
    points: Iterable[FlightCondition],
    evaluator: Callable[[FlightCondition], EvaluatedCondition],
    *,
    max_depth: int = 2,
) -> tuple[tuple[EvaluatedCondition, ...], BoundaryRefinement]:
    """Insert deterministic midpoints where adjacent regions disagree."""

    if max_depth < 0:
        raise ValueError("INVALID_REFINEMENT_DEPTH")
    ordered = sorted(points, key=lambda point: (point.airspeed_m_s, point.mach, point.altitude_m))
    source_count = len(ordered)
    if not ordered:
        return (), BoundaryRefinement(0, 0, max_depth, True)
    evaluated = {point: evaluator(point) for point in ordered}
    inserted = 0
    for _depth in range(max_depth):
        additions: list[FlightCondition] = []
        for left, right in zip(ordered, ordered[1:], strict=False):
            if evaluated[left].region == evaluated[right].region:
                continue
            midpoint = _midpoint(left, right)
            if midpoint not in evaluated:
                additions.append(midpoint)
        if not additions:
            by_airspeed = sorted(evaluated, key=lambda item: item.airspeed_m_s)
            finished = BoundaryRefinement(source_count, inserted, _depth, True)
            return tuple(evaluated[point] for point in by_airspeed), finished
        for point in additions:
            evaluated[point] = evaluator(point)
        inserted += len(additions)
        ordered = sorted(
            evaluated, key=lambda point: (point.airspeed_m_s, point.mach, point.altitude_m)
        )
    pairs = zip(ordered, ordered[1:], strict=False)
    converged = not any(
        evaluated[left].region != evaluated[right].region for left, right in pairs
    )
    return tuple(evaluated[point] for point in ordered), BoundaryRefinement(
        source_count, inserted, max_depth, converged
    )


def evaluate_aircraft_envelope(
    aircraft: AircraftDefinition,
    constraints: EnvelopeConstraints,
    conditions: Iterable[FlightCondition],
    *,
    geometry: GeometryModel | None = None,
    edf_diameter_m: float = 0.070,
    edf_hub_diameter_m: float = 0.025,
    refinement_depth: int = 2,
) -> AircraftEnvelope:
    """Evaluate installed EDF screening points and adaptively refine boundaries."""

    original = tuple(conditions)
    if len(original) > 512:
        raise ValueError("SWEEP_EXCEEDS_POINT_LIMIT")
    if not original:
        raise ValueError("EMPTY_ENVELOPE_SWEEP")

    def evaluator(condition: FlightCondition) -> EvaluatedCondition:
        return _evaluate_condition(
            aircraft,
            constraints,
            condition,
            edf_diameter_m=edf_diameter_m,
            edf_hub_diameter_m=edf_hub_diameter_m,
        )

    points, refinement = refine_boundary(original, evaluator, max_depth=refinement_depth)
    return AircraftEnvelope(
        points=points,
        refinement=refinement,
        geometry_hash=shape_hash(geometry) if geometry is not None else None,
        provenance=analytical_provenance(
            "installed-edf-aircraft-envelope",
            {
                "aircraft": aircraft.model_dump(),
                "constraints": asdict(constraints),
                "conditions": [asdict(condition) for condition in original],
                "geometry_hash": shape_hash(geometry) if geometry is not None else None,
            },
            "parabolic wing polar with analytical installed annular-actuator-disk thrust",
            "AoA, sideslip, body-rate, authority, SOC, thermal terms are screening penalties",
            "native external CFD, aeroelastic loads, and control-law validation are not performed",
        ),
    )


def sweep_conditions(
    *,
    airspeeds_m_s: Iterable[float],
    mach_numbers: Iterable[float],
    altitudes_m: Iterable[float],
    density_kg_m3: Iterable[float],
    temperature_k: Iterable[float],
    **overrides: float,
) -> tuple[FlightCondition, ...]:
    """Build a bounded Cartesian sweep with explicit atmospheric axes."""

    axes = (
        tuple(airspeeds_m_s),
        tuple(mach_numbers),
        tuple(altitudes_m),
        tuple(density_kg_m3),
        tuple(temperature_k),
    )
    count = 1
    for axis in axes:
        count *= len(axis)
    if count == 0:
        raise ValueError("EMPTY_SWEEP_AXIS")
    if count > 512:
        raise ValueError("SWEEP_EXCEEDS_POINT_LIMIT")
    return tuple(
        FlightCondition(
            airspeed_m_s=values[0],
            mach=values[1],
            altitude_m=values[2],
            density_kg_m3=values[3],
            temperature_k=values[4],
            **overrides,
        )
        for values in product(*axes)
    )
