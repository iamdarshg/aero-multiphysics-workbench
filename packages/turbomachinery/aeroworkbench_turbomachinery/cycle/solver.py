"""Generic gas-path/cycle march and multi-spool matching.

The solver walks the compiled graph in topological order, evaluates each
component, and then closes the coupled residuals (shaft power, spool speed,
mixer, nozzle, mass/energy) with a bounded, deterministic Newton iteration on
the balancing elements. It never special-cases a named architecture: the same
march solves a driven fan, a single/multi-spool gas turbine, a bypass/core
split, a free turbine, a recuperated cycle, or a generator/load arrangement.

This module is the cheap, explicitly-labelled analytical screening fidelity. The
native/OpenMDAO path lives in :mod:`.adapter` and labels itself separately.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from ..stations import StationState, WorkingFluid
from ..units import Quantity
from .components import ComponentEvaluation, ComponentParameters, evaluate_component
from .contracts import (
    CycleFidelity,
    CycleModelError,
    CycleValidity,
)
from .gas import GasProperties
from .matching import (
    MatchingResiduals,
    ShaftPower,
    compute_residuals,
    requires_zero_balance,
    shaft_power,
)
from .model import CycleModel, CycleNodeSpec, edge_key

_RATIO_MIN = 1.0001
_RATIO_MAX = 200.0


@dataclass(frozen=True, slots=True)
class CycleOperatingPoint:
    """Boundary conditions for one solve; defaults copied from the design."""

    ambient_total_pressure_pa: float | None = None
    ambient_total_temperature_k: float | None = None
    mass_flow_kg_s: float | None = None

    def resolve(self, model: CycleModel) -> tuple[float, float, float]:
        pressure = self.ambient_total_pressure_pa or model.design.ambient_total_pressure_pa
        temperature = (
            self.ambient_total_temperature_k
            or model.design.ambient_total_temperature_k
        )
        mass_flow = self.mass_flow_kg_s or model.design.mass_flow_kg_s
        for label, value in (
            ("ambient_total_pressure_pa", pressure),
            ("ambient_total_temperature_k", temperature),
            ("mass_flow_kg_s", mass_flow),
        ):
            if not math.isfinite(value) or value <= 0:
                raise CycleModelError(f"OPERATING_POINT_INVALID:{label}:{value}")
        return pressure, temperature, mass_flow


@dataclass(frozen=True, slots=True)
class CycleStationResult:
    """One station state in a solved cycle, keyed by its graph edge."""

    station_id: str
    node_id: str
    edge_key: str
    state: StationState

    def canonical(self) -> dict[str, object]:
        return {
            "stationId": self.station_id,
            "nodeId": self.node_id,
            "edgeKey": self.edge_key,
            "state": self.state.canonical(),
        }


@dataclass(frozen=True, slots=True)
class CycleResult:
    """A solved cycle: unit-bearing stations, residuals, validity, provenance."""

    architecture_id: str
    model_digest: str
    fidelity: str
    source: str
    engine: str
    stations: tuple[CycleStationResult, ...]
    shafts: tuple[ShaftPower, ...]
    residuals: MatchingResiduals
    validity: CycleValidity
    provenance: Provenance
    iterations: int
    converged: bool
    fuel_flow_kg_s: float
    thrust_n: float
    warnings: tuple[str, ...]
    detail: str

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "architectureId": self.architecture_id,
            "modelDigest": self.model_digest,
            "fidelity": self.fidelity,
            "source": self.source,
            "engine": self.engine,
            "converged": self.converged,
            "iterations": self.iterations,
            "fuelFlowKgS": self.fuel_flow_kg_s,
            "thrustN": self.thrust_n,
            "stations": [
                station.canonical()
                for station in sorted(self.stations, key=lambda item: item.edge_key)
            ],
            "shafts": [
                power.canonical() for power in sorted(self.shafts, key=lambda s: s.shaft_id)
            ],
            "residuals": self.residuals.canonical(),
        }
        return payload

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical_payload())

    def station(self, station_id: str) -> StationState:
        for candidate in self.stations:
            if candidate.station_id == station_id:
                return candidate.state
        raise CycleModelError(f"RESULT_STATION_MISSING:{station_id}")

    def shaft(self, shaft_id: str) -> ShaftPower:
        for candidate in self.shafts:
            if candidate.shaft_id == shaft_id:
                return candidate
        raise CycleModelError(f"RESULT_SHAFT_MISSING:{shaft_id}")

    def as_scalars(self) -> dict[str, float]:
        scalars: dict[str, float] = {}
        for station in self.stations:
            state = station.state
            prefix = f"s{station.station_id}"
            if state.mass_flow is not None:
                scalars[f"{prefix}.massFlow"] = state.mass_flow.value_si
            if state.total_pressure is not None:
                scalars[f"{prefix}.totalPressure"] = state.total_pressure.value_si
            if state.total_temperature is not None:
                scalars[f"{prefix}.totalTemperature"] = state.total_temperature.value_si
            if state.velocity is not None:
                scalars[f"{prefix}.velocity"] = state.velocity.value_si
            if state.mach is not None:
                scalars[f"{prefix}.mach"] = state.mach.value_si
        scalars["fuelFlowKgS"] = self.fuel_flow_kg_s
        scalars["thrustN"] = self.thrust_n
        scalars["maxResidual"] = self.residuals.max_residual
        return scalars

    def units(self) -> dict[str, str]:
        units: dict[str, str] = {}
        for station in self.stations:
            prefix = f"s{station.station_id}"
            state = station.state
            if state.mass_flow is not None:
                units[f"{prefix}.massFlow"] = "kg/s"
            if state.total_pressure is not None:
                units[f"{prefix}.totalPressure"] = "Pa"
            if state.total_temperature is not None:
                units[f"{prefix}.totalTemperature"] = "K"
            if state.velocity is not None:
                units[f"{prefix}.velocity"] = "m/s"
            if state.mach is not None:
                units[f"{prefix}.mach"] = "dimensionless"
        units["fuelFlowKgS"] = "kg/s"
        units["thrustN"] = "N"
        units["maxResidual"] = "dimensionless"
        return units


@dataclass(slots=True)
class _March:
    edge_states: dict[str, StationState]
    edge_meta: dict[str, tuple[str, str]]
    evaluations: dict[str, ComponentEvaluation]
    produced: dict[str, float]
    required: dict[str, float]


def _boundary_state(
    gas: GasProperties,
    *,
    mass_flow_kg_s: float,
    total_pressure_pa: float,
    total_temperature_k: float,
) -> StationState:
    return StationState(
        mass_flow=Quantity(value=mass_flow_kg_s, unit="kg/s"),
        total_pressure=Quantity(value=total_pressure_pa, unit="Pa"),
        total_temperature=Quantity(value=total_temperature_k, unit="K"),
        fluid=WorkingFluid(identity=gas.identity),
    )


def resolve_spool_speeds(model: CycleModel) -> dict[str, float | None]:
    """Propagate declared speeds through common-shaft and geared couplings."""

    speeds: dict[str, float | None] = {
        shaft.shaft_id: shaft.speed_rpm for shaft in model.shafts
    }
    changed = True
    while changed:
        changed = False
        for shaft in model.shafts:
            for coupling in shaft.couplings:
                if coupling.target_shaft is None or coupling.target_shaft not in speeds:
                    continue
                source = speeds[shaft.shaft_id]
                target = speeds[coupling.target_shaft]
                if source is None and target is None:
                    continue
                if coupling.kind == "common_shaft":
                    if source is None:
                        speeds[shaft.shaft_id] = target
                        changed = True
                    elif target is None:
                        speeds[coupling.target_shaft] = source
                        changed = True
                elif coupling.kind == "geared":
                    ratio = coupling.ratio or 1.0
                    if source is not None and target is None:
                        speeds[coupling.target_shaft] = source / ratio
                        changed = True
                    elif target is not None and source is None:
                        speeds[shaft.shaft_id] = target * ratio
                        changed = True
    return speeds


def _node_parameters(
    node: CycleNodeSpec, overrides: Mapping[str, float]
) -> ComponentParameters:
    if node.node_id not in overrides:
        return node.parameters
    value = overrides[node.node_id]
    if node.parameters.component_map is not None:
        return replace(node.parameters, corrected_flow=value)
    if node.is_work_extracting:
        return replace(node.parameters, expansion_ratio=value)
    return replace(node.parameters, pressure_ratio=value)


def march(
    model: CycleModel,
    *,
    ambient_total_pressure_pa: float,
    ambient_total_temperature_k: float,
    mass_flow_kg_s: float,
    overrides: Mapping[str, float],
) -> _March:
    """Walk the compiled graph once and evaluate every component."""

    gas = model.design.gas
    edge_states: dict[str, StationState] = {}
    edge_meta: dict[str, tuple[str, str]] = {}
    evaluations: dict[str, ComponentEvaluation] = {}
    produced: dict[str, float] = {shaft.shaft_id: 0.0 for shaft in model.shafts}
    required: dict[str, float] = {shaft.shaft_id: 0.0 for shaft in model.shafts}
    edge_lookup = {edge_key(edge): edge for edge in model.architecture.edges}
    boundary = _boundary_state(
        gas,
        mass_flow_kg_s=mass_flow_kg_s,
        total_pressure_pa=ambient_total_pressure_pa,
        total_temperature_k=ambient_total_temperature_k,
    )
    for node_id in model.order:
        node = model.node(node_id)
        outgoing_edges = [edge_lookup[key] for key in node.outlet_keys]
        if node.is_source:
            for key, edge in zip(node.outlet_keys, outgoing_edges, strict=True):
                edge_states[key] = boundary
                edge_meta[key] = (node.node_id, edge.station or key)
            continue
        inlet_states = tuple(edge_states[key] for key in node.inlet_keys)
        evaluation = evaluate_component(
            node_id=node.node_id,
            kind=node.kind,
            parameters=_node_parameters(node, overrides),
            gas=gas,
            inlet_states=inlet_states,
            outlet_keys=node.outlet_keys,
            shaft_id=node.shaft_id,
        )
        evaluations[node.node_id] = evaluation
        for key, edge in zip(node.outlet_keys, outgoing_edges, strict=True):
            edge_states[key] = evaluation.output_state(key)
            edge_meta[key] = (node.node_id, edge.station or key)
        if node.shaft_id is not None:
            if evaluation.shaft_power_w >= 0:
                produced[node.shaft_id] += evaluation.shaft_power_w
            else:
                required[node.shaft_id] += -evaluation.shaft_power_w
    return _March(edge_states, edge_meta, evaluations, produced, required)


@dataclass(frozen=True, slots=True)
class _BalanceVariable:
    shaft_id: str
    node_id: str
    field: str
    initial: float


def _balance_variables(
    model: CycleModel, speeds: Mapping[str, float | None]
) -> tuple[_BalanceVariable, ...]:
    variables: list[_BalanceVariable] = []
    for shaft in model.shafts:
        has_adding = bool(shaft.work_adding_nodes)
        has_extracting = bool(shaft.work_extracting_nodes)
        if not (has_adding or has_extracting):
            continue
        if not requires_zero_balance(model, shaft):
            continue
        if has_extracting:
            node = model.node(shaft.work_extracting_nodes[0])
            field = (
                "corrected_flow" if node.parameters.component_map is not None else "expansion_ratio"
            )
        else:
            node = model.node(shaft.work_adding_nodes[0])
            field = (
                "corrected_flow" if node.parameters.component_map is not None else "pressure_ratio"
            )
        initial = _initial_ratio(node, field)
        variables.append(_BalanceVariable(shaft.shaft_id, node.node_id, field, initial))
    return tuple(variables)


def _initial_ratio(node: CycleNodeSpec, field: str) -> float:
    if field == "corrected_flow":
        return node.parameters.corrected_flow or 1.0
    if node.declared_ratio is not None:
        return node.declared_ratio
    if field == "expansion_ratio":
        return node.parameters.expansion_ratio or 1.5
    return node.parameters.pressure_ratio or 1.5


def _clamp_ratio(value: float) -> float:
    return min(max(value, _RATIO_MIN), _RATIO_MAX)


def _solve_linear(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    size = len(rhs)
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column] / pivot_value
            for item in range(column, size + 1):
                augmented[row][item] -= factor * augmented[column][item]
    return [augmented[index][size] / augmented[index][index] for index in range(size)]


def _build_shaft_powers(
    model: CycleModel,
    march_result: _March,
    speeds: Mapping[str, float | None],
) -> tuple[ShaftPower, ...]:
    powers: list[ShaftPower] = []
    for shaft in model.shafts:
        powers.append(
            shaft_power(
                model,
                shaft,
                produced_w=march_result.produced[shaft.shaft_id],
                required_w=march_result.required[shaft.shaft_id],
                speed_rpm=speeds.get(shaft.shaft_id),
            )
        )
    return tuple(powers)


def _match(
    model: CycleModel,
    *,
    pressure: float,
    temperature: float,
    mass_flow: float,
    speeds: Mapping[str, float | None],
    tolerance: float,
    max_iterations: int,
) -> tuple[_March, tuple[ShaftPower, ...], MatchingResiduals, int, bool]:
    variables = _balance_variables(model, speeds)

    def evaluate(values: list[float]) -> tuple[_March, tuple[ShaftPower, ...], list[float]]:
        overrides = {
            variable.node_id: value
            for variable, value in zip(variables, values, strict=True)
        }
        march_result = march(
            model,
            ambient_total_pressure_pa=pressure,
            ambient_total_temperature_k=temperature,
            mass_flow_kg_s=mass_flow,
            overrides=overrides,
        )
        powers = _build_shaft_powers(model, march_result, speeds)
        by_id = {power.shaft_id: power for power in powers}
        residual = [
            by_id[variable.shaft_id].signed_residual_fraction for variable in variables
        ]
        return march_result, powers, residual

    if not variables:
        march_result = march(
            model,
            ambient_total_pressure_pa=pressure,
            ambient_total_temperature_k=temperature,
            mass_flow_kg_s=mass_flow,
            overrides={},
        )
        powers = _build_shaft_powers(model, march_result, speeds)
        residuals = compute_residuals(
            model,
            edge_states=march_result.edge_states,
            shaft_powers=powers,
            speeds_rpm=speeds,
        )
        return march_result, powers, residuals, 1, residuals.converged(tolerance)

    values = [_clamp_ratio(variable.initial) for variable in variables]
    march_result, powers, residual = evaluate(values)
    iteration = 0
    converged = max((abs(item) for item in residual), default=0.0) <= tolerance
    while not converged and iteration < max_iterations:
        iteration += 1
        jacobian: list[list[float]] = [[0.0] * len(values) for _ in values]
        for column, value in enumerate(values):
            step = max(1e-5, abs(value) * 1e-4)
            perturbed = list(values)
            perturbed[column] = _clamp_ratio(value + step)
            _, _, perturbed_residual = evaluate(perturbed)
            actual_step = perturbed[column] - value
            if actual_step == 0:
                continue
            for row in range(len(values)):
                jacobian[row][column] = (
                    perturbed_residual[row] - residual[row]
                ) / actual_step
        direction = _solve_linear(jacobian, [-item for item in residual])
        if direction is None:
            direction = [-item for item in residual]
        best: tuple[float, _March, tuple[ShaftPower, ...], list[float], list[float]] | None = None
        inherited = max((abs(item) for item in residual), default=0.0)
        for alpha in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
            candidate = [
                _clamp_ratio(value + alpha * delta)
                for value, delta in zip(values, direction, strict=True)
            ]
            candidate_march, candidate_powers, candidate_residual = evaluate(candidate)
            candidate_max = max((abs(item) for item in candidate_residual), default=0.0)
            if candidate_max < inherited:
                best = (
                    candidate_max,
                    candidate_march,
                    candidate_powers,
                    candidate_residual,
                    candidate,
                )
                break
        if best is None:
            break
        candidate_max, march_result, powers, residual, values = best
        converged = candidate_max <= tolerance
        del candidate_max
    residuals = compute_residuals(
        model,
        edge_states=march_result.edge_states,
        shaft_powers=powers,
        speeds_rpm=speeds,
    )
    return march_result, powers, residuals, iteration, residuals.converged(tolerance)


def build_result(
    model: CycleModel,
    *,
    edge_states: Mapping[str, StationState],
    edge_meta: Mapping[str, tuple[str, str]],
    powers: tuple[ShaftPower, ...],
    residuals: MatchingResiduals,
    fidelity: str,
    source: str,
    engine: str,
    provenance: Provenance,
    iterations: int,
    converged: bool,
    tolerance: float,
    fuel_flow_kg_s: float,
    thrust_n: float,
    warnings: tuple[str, ...] = (),
    detail: str = "",
) -> CycleResult:
    """Assemble a :class:`CycleResult` from a marched cycle."""

    stations = tuple(
        CycleStationResult(
            station_id=station_id,
            node_id=node_id,
            edge_key=key,
            state=edge_states[key],
        )
        for key, (node_id, station_id) in sorted(edge_meta.items())
    )
    fuel_flow = fuel_flow_kg_s
    thrust = thrust_n
    checks: dict[str, bool] = {
        "shaft_power_closure": all(
            power.residual_fraction <= tolerance for power in powers
        ),
        "mass_continuity": residuals.mass_continuity <= tolerance,
        "pressure_continuity": residuals.pressure_continuity <= tolerance,
        "temperature_continuity": residuals.temperature_continuity <= tolerance,
        "mixer_compatibility": residuals.mixer_compatibility <= tolerance,
        "nozzle_flow": residuals.nozzle_flow <= tolerance,
        "bleed_cooling": residuals.bleed_cooling <= tolerance,
        "spool_speed": all(value <= tolerance for _, value in residuals.spool_speed),
        "electric_balance": all(
            value <= tolerance for _, value in residuals.electric_balance
        ),
    }
    warnings_out = list(warnings)
    return CycleResult(
        architecture_id=model.architecture.architecture_id,
        model_digest=model.digest,
        fidelity=fidelity,
        source=source,
        engine=engine,
        stations=stations,
        shafts=powers,
        residuals=residuals,
        validity=CycleValidity(
            passed=all(checks.values()),
            checks=checks,
            detail=detail or f"max residual {residuals.max_residual:.3g}",
        ),
        provenance=provenance,
        iterations=iterations,
        converged=converged,
        fuel_flow_kg_s=fuel_flow,
        thrust_n=thrust,
        warnings=tuple(dict.fromkeys(warnings_out)),
        detail=detail,
    )


def solve_cycle(
    model: CycleModel,
    operating_point: CycleOperatingPoint | None = None,
    *,
    tolerance: float = 1e-6,
    max_iterations: int = 60,
) -> CycleResult:
    """Solve and match a cycle at the declared analytical screening fidelity."""

    if not math.isfinite(tolerance) or tolerance <= 0:
        raise CycleModelError("SOLVER_TOLERANCE_MUST_BE_POSITIVE")
    if max_iterations <= 0:
        raise CycleModelError("SOLVER_MAX_ITERATIONS_MUST_BE_POSITIVE")
    pressure, temperature, mass_flow = (operating_point or CycleOperatingPoint()).resolve(
        model
    )
    speeds = resolve_spool_speeds(model)
    march_result, powers, residuals, iterations, converged = _match(
        model,
        pressure=pressure,
        temperature=temperature,
        mass_flow=mass_flow,
        speeds=speeds,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="generic-cycle-analytical-screening",
        model_version="1",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={
            "model": model.canonical(),
            "operatingPoint": {
                "ambientTotalPressurePa": pressure,
                "ambientTotalTemperatureK": temperature,
                "massFlowKgS": mass_flow,
            },
        },
        assumptions=(
            "calorically-perfect gas; station total states only",
            "preliminary-design or declared-map component performance",
            "not pyCycle and not a native solver result",
        ),
    )
    fuel_flow = sum(
        evaluation.fuel_flow_kg_s for evaluation in march_result.evaluations.values()
    )
    thrust = sum(evaluation.thrust_n for evaluation in march_result.evaluations.values())
    warnings = tuple(
        warning
        for evaluation in march_result.evaluations.values()
        for warning in evaluation.warnings
    )
    return build_result(
        model,
        edge_states=march_result.edge_states,
        edge_meta=march_result.edge_meta,
        powers=powers,
        residuals=residuals,
        fidelity=CycleFidelity.ANALYTICAL_SCREENING.value,
        source=ResultSource.ANALYTICAL.value,
        engine="analytical-screening",
        provenance=provenance,
        iterations=iterations,
        converged=converged,
        tolerance=tolerance,
        fuel_flow_kg_s=fuel_flow,
        thrust_n=thrust,
        warnings=warnings,
        detail=f"bounded Newton matching, {iterations} iterations",
    )


__all__ = [
    "CycleOperatingPoint",
    "CycleResult",
    "CycleStationResult",
    "build_result",
    "march",
    "resolve_spool_speeds",
    "solve_cycle",
]
