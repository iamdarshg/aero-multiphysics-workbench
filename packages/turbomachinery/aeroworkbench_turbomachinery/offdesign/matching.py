"""Per-point off-design matching: map validity, speed/flow balance, margins."""

from __future__ import annotations

from dataclasses import dataclass

from ..canonical import content_digest
from ..cycle.components import ComponentParameters
from ..cycle.contracts import CycleModelError, OutOfEnvelopePolicy
from ..cycle.maps import OperatingMap
from ..cycle.model import CycleDesign, CycleModel, compile_cycle_model
from ..cycle.solver import CycleOperatingPoint, CycleResult, solve_cycle
from .errors import OffdesignInputError
from .operating_point import OperatingPoint
from .schedules import ControlSchedule

REFERENCE_PRESSURE_PA = 101325.0
REFERENCE_TEMPERATURE_K = 288.15


@dataclass(frozen=True, slots=True)
class MapReference:
    """One component map applied at an operating point."""

    node_id: str
    component_map: OperatingMap
    design_corrected_flow: float

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise OffdesignInputError("MAP_REFERENCE_NODE_ID_REQUIRED")
        if not self.design_corrected_flow > 0.0:
            raise OffdesignInputError("MAP_REFERENCE_FLOW_MUST_BE_POSITIVE")

    def canonical(self) -> dict[str, object]:
        return {
            "nodeId": self.node_id,
            "map": self.component_map.canonical(),
            "designCorrectedFlow": self.design_corrected_flow,
        }


@dataclass(frozen=True, slots=True)
class OperabilityLimits:
    """Declared pointwise hard limits; violations fail the point, never averaged."""

    max_shaft_residual: float = 1e-3
    max_mass_residual: float = 1e-3
    min_surge_margin: float = 0.05
    max_corrected_speed: float | None = None
    max_exit_temperature_k: float | None = None
    max_pressure_pa: float | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("maxShaftResidual", self.max_shaft_residual),
            ("maxMassResidual", self.max_mass_residual),
            ("minSurgeMargin", self.min_surge_margin),
        ):
            if not value > 0.0:
                raise OffdesignInputError(f"OPERABILITY_LIMIT_NOT_POSITIVE:{label}")

    def canonical(self) -> dict[str, object]:
        return {
            "maxShaftResidual": self.max_shaft_residual,
            "maxMassResidual": self.max_mass_residual,
            "minSurgeMargin": self.min_surge_margin,
            "maxCorrectedSpeed": self.max_corrected_speed,
            "maxExitTemperatureK": self.max_exit_temperature_k,
            "maxPressurePa": self.max_pressure_pa,
        }


@dataclass(frozen=True, slots=True)
class PointMatch:
    """Raw per-point matching outcome before provenance wrapping."""

    point_id: str
    converged: bool
    thrust_n: float
    shaft_power_w: float
    max_residual: float
    surge_margin: float
    map_valid: bool
    checks: tuple[tuple[str, bool], ...]
    warnings: tuple[str, ...]

    @property
    def hard_passed(self) -> bool:
        return all(passed for _, passed in self.checks)

    def canonical(self) -> dict[str, object]:
        return {
            "pointId": self.point_id,
            "converged": self.converged,
            "thrustN": self.thrust_n,
            "shaftPowerW": self.shaft_power_w,
            "maxResidual": self.max_residual,
            "surgeMargin": self.surge_margin,
            "mapValid": self.map_valid,
            "checks": [[name, passed] for name, passed in self.checks],
            "warnings": list(self.warnings),
        }


def corrected_conditions(
    point: OperatingPoint, design: CycleDesign
) -> tuple[float, float, float, float]:
    pressure = point.ambient_pressure_pa or design.ambient_total_pressure_pa
    temperature = point.ambient_temperature_k or design.ambient_total_temperature_k
    mass_flow = point.mass_flow_kg_s or design.mass_flow_kg_s
    theta = temperature / REFERENCE_TEMPERATURE_K
    delta = pressure / REFERENCE_PRESSURE_PA
    corrected_flow = mass_flow * (theta**0.5) / delta
    return pressure, temperature, mass_flow, corrected_flow


def corrected_speed(shaft_rpm: float | None, temperature_k: float) -> float | None:
    if shaft_rpm is None:
        return None
    theta: float = temperature_k / REFERENCE_TEMPERATURE_K
    result: float = shaft_rpm / (theta**0.5)
    return result


def surge_margin_for(
    component_map: OperatingMap, speed_value: float, corrected_flow: float
) -> float:
    nearest = min(
        component_map.lines, key=lambda line: abs(line.corrected_speed - speed_value)
    )
    surge = nearest.surge_corrected_flow
    if corrected_flow <= 0.0:
        raise OffdesignInputError("CORRECTED_FLOW_MUST_BE_POSITIVE")
    return (corrected_flow - surge) / corrected_flow


def evaluate_point(
    model: CycleModel,
    point: OperatingPoint,
    *,
    maps: tuple[MapReference, ...] = (),
    limits: OperabilityLimits | None = None,
    schedule: ControlSchedule | None = None,
    tolerance: float = 1e-6,
) -> tuple[PointMatch, CycleResult]:
    active = limits or OperabilityLimits()
    applied_controls = schedule.values_for(point.point_id) if schedule is not None else {}
    pressure, temperature, mass_flow, corrected_flow = corrected_conditions(
        point, model.design
    )
    cycle_point = CycleOperatingPoint(
        ambient_total_pressure_pa=pressure,
        ambient_total_temperature_k=temperature,
        mass_flow_kg_s=mass_flow,
    )
    try:
        result = solve_cycle(model, cycle_point, tolerance=tolerance)
    except CycleModelError as exc:
        raise OffdesignInputError(f"OFFDESIGN_POINT_FAILED:{point.point_id}") from exc
    shaft_power_w = sum(power.required_w for power in result.shafts)
    shaft_residual = max(
        (power.residual_fraction for power in result.shafts), default=0.0
    )
    checks: list[tuple[str, bool]] = [
        ("cycle_converged", result.converged),
        ("shaft_power_closure", shaft_residual <= active.max_shaft_residual),
        ("mass_continuity", result.residuals.mass_continuity <= active.max_mass_residual),
    ]
    warnings: list[str] = list(result.warnings)
    margins: list[float] = []
    map_valid = True
    for reference in maps:
        node = model.node(reference.node_id)
        requested = dict(point.spool_speeds_rpm)
        shaft_rpm = requested.get(node.shaft_id or "")
        if shaft_rpm is None:
            for shaft in model.shafts:
                if node.node_id in shaft.member_nodes:
                    shaft_rpm = shaft.speed_rpm
                    break
        speed_value = corrected_speed(shaft_rpm, temperature)
        if speed_value is None:
            map_valid = False
            checks.append((f"map_speed:{reference.node_id}", False))
            continue
        if (
            active.max_corrected_speed is not None
            and speed_value > active.max_corrected_speed
        ):
            checks.append((f"speed_limit:{reference.node_id}", False))
        try:
            evaluation = reference.component_map.evaluate(
                speed_value, corrected_flow, OutOfEnvelopePolicy.FAIL
            )
        except CycleModelError:
            map_valid = False
            checks.append((f"map_validity:{reference.node_id}", False))
            continue
        margin = surge_margin_for(reference.component_map, speed_value, corrected_flow)
        margins.append(margin)
        checks.append((f"map_validity:{reference.node_id}", True))
        checks.append(
            (f"surge_margin:{reference.node_id}", margin >= active.min_surge_margin)
        )
        if evaluation.near_surge or evaluation.near_choke:
            warnings.append(f"{reference.node_id}:near stability boundary")
    surge_margin = min(margins) if margins else -1.0
    checks.append(("map_valid", map_valid))
    if margins:
        checks.append(("surge_margin_ok", surge_margin >= active.min_surge_margin))
    else:
        checks.append(("surge_margin_ok", False))
    if active.max_exit_temperature_k is not None:
        hottest = max(
            (
                station.state.total_temperature.value_si
                for station in result.stations
                if station.state.total_temperature is not None
            ),
            default=0.0,
        )
        checks.append(("exit_temperature_limit", hottest <= active.max_exit_temperature_k))
    if active.max_pressure_pa is not None:
        peak = max(
            (
                station.state.total_pressure.value_si
                for station in result.stations
                if station.state.total_pressure is not None
            ),
            default=0.0,
        )
        checks.append(("pressure_limit", peak <= active.max_pressure_pa))
    if not applied_controls:
        warnings.append("no scheduled controls applied")
    match = PointMatch(
        point_id=point.point_id,
        converged=result.converged,
        thrust_n=result.thrust_n,
        shaft_power_w=shaft_power_w,
        max_residual=result.residuals.max_residual,
        surge_margin=surge_margin,
        map_valid=map_valid,
        checks=tuple(checks),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    return match, result


def evaluate_multipoint(
    design: CycleDesign,
    points: tuple[OperatingPoint, ...],
    *,
    maps: tuple[MapReference, ...] = (),
    limits: OperabilityLimits | None = None,
    schedule: ControlSchedule | None = None,
    parameters: tuple[tuple[str, ComponentParameters], ...] | None = None,
) -> tuple[tuple[PointMatch, ...], CycleModel]:
    if parameters is not None:
        design = design.with_parameters(parameters)
    model = compile_cycle_model(design)
    ordered = tuple(sorted(points, key=lambda item: item.point_id))
    if schedule is not None:
        violations = schedule.validate(tuple(point.point_id for point in ordered))
        if violations:
            raise OffdesignInputError(
                f"SCHEDULE_CONSTRAINT_VIOLATED:{';'.join(violations)}"
            )
    matches: list[PointMatch] = []
    for point in ordered:
        match, _ = evaluate_point(
            model, point, maps=maps, limits=limits, schedule=schedule
        )
        matches.append(match)
    return tuple(matches), model


def match_digest(matches: tuple[PointMatch, ...]) -> str:
    return content_digest([match.canonical() for match in matches])


__all__ = [
    "MapReference",
    "OperabilityLimits",
    "PointMatch",
    "corrected_conditions",
    "corrected_speed",
    "evaluate_multipoint",
    "evaluate_point",
    "match_digest",
    "surge_margin_for",
]
