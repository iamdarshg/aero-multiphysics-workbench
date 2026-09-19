"""Optional governed pyCycle/OpenMDAO execution path for the cycle solver.

pyCycle and OpenMDAO are optional native capabilities. This module probes them,
prepares a canonical case, sets up and executes a real OpenMDAO component
network at a separately labelled fidelity, and fails closed with
``CAPABILITY_UNAVAILABLE`` whenever a requested engine is absent. An analytical
result is never relabelled native, and a pyCycle result is never fabricated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from ..stations import StationState, WorkingFluid
from ..units import Quantity
from .components import (
    HEAT_EXCHANGER_KINDS,
    ComponentParameters,
    evaluate_component,
)
from .contracts import (
    CycleCapabilityUnavailable,
    CycleEngineStatus,
    CycleFidelity,
    CycleModelError,
    CycleParserError,
    probe_cycle_engine,
)
from .gas import GasProperties
from .matching import (
    ShaftPower,
    compute_residuals,
    requires_zero_balance,
    shaft_power,
)
from .model import CycleModel, CycleNodeSpec, edge_key
from .solver import (
    CycleOperatingPoint,
    CycleResult,
    _clamp_ratio,
    _solve_linear,
    build_result,
    resolve_spool_speeds,
)

_PYCYCLE_UNSUPPORTED_NODE_KINDS: frozenset[str] = frozenset(
    {*HEAT_EXCHANGER_KINDS, "cooling_inject"}
)


def _safe(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value)
    return cleaned.replace("__", "_")


def _as_float(value: object) -> float:
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return float(item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, (list, tuple)) and value:
        return _as_float(value[0])
    return float(value)  # type: ignore[arg-type]


def _station(
    gas: GasProperties,
    *,
    mass_flow_kg_s: float,
    total_pressure_pa: float,
    total_temperature_k: float,
    static_pressure_pa: float | None = None,
    static_temperature_k: float | None = None,
    velocity_m_s: float | None = None,
    mach: float | None = None,
) -> StationState:
    return StationState(
        mass_flow=Quantity(value=mass_flow_kg_s, unit="kg/s"),
        total_pressure=Quantity(value=total_pressure_pa, unit="Pa"),
        total_temperature=Quantity(value=total_temperature_k, unit="K"),
        static_pressure=None
        if static_pressure_pa is None
        else Quantity(value=static_pressure_pa, unit="Pa"),
        static_temperature=None
        if static_temperature_k is None
        else Quantity(value=static_temperature_k, unit="K"),
        velocity=None if velocity_m_s is None else Quantity(value=velocity_m_s, unit="m/s"),
        mach=None if mach is None else Quantity(value=mach, unit="dimensionless"),
        density=None
        if static_pressure_pa is None or static_temperature_k is None
        else Quantity(
            value=static_pressure_pa / (gas.r_j_kg_k * static_temperature_k),
            unit="kg/m3",
        ),
        fluid=WorkingFluid(identity=gas.identity),
    )


# ---------------------------------------------------------------------------
# pyCycle capability, preparation, topology gate, and parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PyCycleCase:
    """A prepared pyCycle case document plus its identity and provenance."""

    engine: str
    version: str
    topology_supported: bool
    input_hash: str
    canonical_case: dict[str, object]
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "version": self.version,
            "topologySupported": self.topology_supported,
            "inputHash": self.input_hash,
            "case": self.canonical_case,
            "detail": self.detail,
        }


def pycycle_supported_topology(model: CycleModel) -> tuple[bool, str]:
    """Whether the pyCycle element set can express this compiled topology.

    Recuperators/intercoolers and arbitrary cooling injection are not part of
    the pyCycle element set used here; they fail clearly instead of being
    silently dropped.
    """

    unsupported = sorted(
        {node.kind for node in model.nodes if node.kind in _PYCYCLE_UNSUPPORTED_NODE_KINDS}
    )
    if unsupported:
        return False, f"pycycle cannot express node kinds:{','.join(unsupported)}"
    return True, "topology is expressible with the pyCycle element set"


def _canonical_pycycle_case(
    model: CycleModel, operating_point: CycleOperatingPoint | None
) -> dict[str, object]:
    pressure, temperature, mass_flow = (operating_point or CycleOperatingPoint()).resolve(
        model
    )
    edge_lookup = {edge_key(edge): edge for edge in model.architecture.edges}
    return {
        "library": "pycycle",
        "architectureId": model.architecture.architecture_id,
        "modelDigest": model.digest,
        "boundary": {
            "ambientTotalPressurePa": pressure,
            "ambientTotalTemperatureK": temperature,
            "massFlowKgS": mass_flow,
        },
        "elements": [
            {
                "id": node.node_id,
                "kind": node.kind,
                "shaft": node.shaft_id,
                "inletKeys": list(node.inlet_keys),
                "outletKeys": list(node.outlet_keys),
                "parameters": node.parameters.canonical(),
            }
            for node in sorted(model.nodes, key=lambda item: item.node_id)
        ],
        "connections": [
            {
                "edge": key,
                "from": edge.from_node,
                "to": edge.to_node,
                "kind": edge.kind,
                "station": edge.station,
            }
            for key, edge in sorted(edge_lookup.items())
        ],
        "solvers": [
            {
                "shaftId": shaft.shaft_id,
                "kind": shaft.kind,
                "speedRpm": shaft.speed_rpm,
                "members": list(shaft.member_nodes),
            }
            for shaft in sorted(model.shafts, key=lambda item: item.shaft_id)
        ],
    }


def prepare_pycycle_case(
    model: CycleModel,
    operating_point: CycleOperatingPoint | None = None,
    case_dir: Path | None = None,
) -> PyCycleCase:
    """Probe pyCycle, gate the topology, and stage a canonical case document."""

    status = probe_cycle_engine("pycycle")
    if not status.available:
        raise CycleCapabilityUnavailable(
            f"pyCycle is not installed: {status.detail}; native cycle level fails closed"
        )
    supported, reason = pycycle_supported_topology(model)
    if not supported:
        raise CycleModelError(f"PYCYCLE_TOPOLOGY_UNSUPPORTED:{reason}")
    canonical_case = _canonical_pycycle_case(model, operating_point)
    input_hash = content_digest(canonical_case)
    if case_dir is not None:
        prepared = case_dir / "case.json"
        prepared.parent.mkdir(parents=True, exist_ok=True)
        prepared.write_text(
            json.dumps(canonical_case, indent=2, sort_keys=True), encoding="utf-8"
        )
    return PyCycleCase(
        engine="pycycle",
        version=status.version or "unknown",
        topology_supported=True,
        input_hash=input_hash,
        canonical_case=canonical_case,
        detail=reason,
    )


def solve_with_pycycle(
    model: CycleModel, operating_point: CycleOperatingPoint | None = None
) -> CycleResult:
    """Execute the native pyCycle level, failing closed when it is unavailable.

    A pyCycle result is published only from a trusted governed native run; such
    a receipt is not available here, so this fails closed rather than
    substituting an analytical answer under a native label.
    """

    status = probe_cycle_engine("pycycle")
    if not status.available:
        raise CycleCapabilityUnavailable(
            f"pyCycle is not installed: {status.detail}; native cycle level fails closed"
        )
    supported, reason = pycycle_supported_topology(model)
    if not supported:
        raise CycleModelError(f"PYCYCLE_TOPOLOGY_UNSUPPORTED:{reason}")
    del operating_point
    raise CycleCapabilityUnavailable(
        "pyCycle execution requires a governed native benchmark run; "
        "no trusted receipt is available and no analytical result is relabelled"
    )


def parse_pycycle_result(case_dir: Path) -> dict[str, object]:
    """Structurally validate a pyCycle result document; fail closed otherwise."""

    path = case_dir / "result.json"
    if not path.is_file():
        raise CycleParserError(f"PYCYCLE_RESULT_MISSING:{path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CycleParserError(f"PYCYCLE_RESULT_UNREADABLE:{exc}") from exc
    if not isinstance(document, dict):
        raise CycleParserError("PYCYCLE_RESULT_NOT_AN_OBJECT")
    if document.get("library") != "pycycle":
        raise CycleParserError(f"PYCYCLE_RESULT_LIBRARY_MISMATCH:{document.get('library')}")
    if not document.get("solverVersion"):
        raise CycleParserError("PYCYCLE_RESULT_WITHOUT_SOLVER_VERSION")
    if not document.get("runId"):
        raise CycleParserError("PYCYCLE_RESULT_WITHOUT_RUN_ID")
    return document


# ---------------------------------------------------------------------------
# Generic OpenMDAO component-network engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OpenMdaoPolicy:
    """Bounded matching policy for the generic OpenMDAO network."""

    tolerance: float = 1e-6
    max_iterations: int = 60


def _balance_targets(model: CycleModel) -> dict[str, str]:
    """Map each balancing node id to its override field, if it balances."""

    targets: dict[str, str] = {}
    for shaft in model.shafts:
        has_adding = bool(shaft.work_adding_nodes)
        has_extracting = bool(shaft.work_extracting_nodes)
        if not (has_adding or has_extracting):
            continue
        if not requires_zero_balance(model, shaft):
            continue
        node = model.node(
            shaft.work_extracting_nodes[0] if has_extracting else shaft.work_adding_nodes[0]
        )
        if node.parameters.component_map is not None:
            targets[node.node_id] = "corrected_flow"
        elif node.is_work_extracting:
            targets[node.node_id] = "expansion_ratio"
        else:
            targets[node.node_id] = "pressure_ratio"
    return targets


def _initial_value(node: CycleNodeSpec, field: str) -> float:
    if field == "corrected_flow":
        return node.parameters.corrected_flow or 1.0
    if node.declared_ratio is not None:
        return node.declared_ratio
    if field == "expansion_ratio":
        return node.parameters.expansion_ratio or 1.5
    return node.parameters.pressure_ratio or 1.5


def _parameters_with_override(
    node: CycleNodeSpec, field: str, value: float
) -> ComponentParameters:
    if field == "corrected_flow":
        return replace(node.parameters, corrected_flow=value)
    if field == "expansion_ratio":
        return replace(node.parameters, expansion_ratio=value)
    return replace(node.parameters, pressure_ratio=value)


def _write_state(outputs: Any, key: str, state: StationState) -> None:
    safe = _safe(key)
    outputs[f"mf__{safe}"] = state.mass_flow.value_si if state.mass_flow else 0.0
    outputs[f"pt__{safe}"] = state.total_pressure.value_si if state.total_pressure else 0.0
    outputs[f"tt__{safe}"] = (
        state.total_temperature.value_si if state.total_temperature else 0.0
    )
    outputs[f"ps__{safe}"] = state.static_pressure.value_si if state.static_pressure else 0.0
    outputs[f"ts__{safe}"] = (
        state.static_temperature.value_si if state.static_temperature else 0.0
    )
    outputs[f"vel__{safe}"] = state.velocity.value_si if state.velocity else 0.0
    outputs[f"mach__{safe}"] = state.mach.value_si if state.mach else 0.0


def _write_boundary(outputs: Any, key: str, mass: float, pressure: float, temp: float) -> None:
    safe = _safe(key)
    outputs[f"mf__{safe}"] = mass
    outputs[f"pt__{safe}"] = pressure
    outputs[f"tt__{safe}"] = temp
    outputs[f"ps__{safe}"] = 0.0
    outputs[f"ts__{safe}"] = 0.0
    outputs[f"vel__{safe}"] = 0.0
    outputs[f"mach__{safe}"] = 0.0


def _make_node_component(
    *,
    node: CycleNodeSpec,
    gas: GasProperties,
    boundary: tuple[float, float, float],
    field: str | None,
) -> object:
    import openmdao.api as om

    class _NodeComponent(om.ExplicitComponent):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self._node = node
            self._gas = gas
            self._boundary = boundary
            self._field = field

        def setup(self) -> None:
            for key in self._node.inlet_keys:
                self.add_input(f"mf__{_safe(key)}", val=0.0)
                self.add_input(f"pt__{_safe(key)}", val=0.0)
                self.add_input(f"tt__{_safe(key)}", val=0.0)
            for key in self._node.outlet_keys:
                for prefix in ("mf", "pt", "tt", "ps", "ts", "vel", "mach"):
                    self.add_output(f"{prefix}__{_safe(key)}", val=0.0)
            if self._field is not None:
                self.add_input("ratio__override", val=1.0)
            self.add_output("power__w", val=0.0)
            self.add_output("fuel__flow", val=0.0)
            self.add_output("thrust__n", val=0.0)
            if self._node.inlet_keys:
                self.declare_partials("*", "*", method="fd")

        def compute(self, inputs: Any, outputs: Any) -> None:
            mass_flow, pressure, temperature = self._boundary
            if self._node.is_source:
                for key in self._node.outlet_keys:
                    _write_boundary(outputs, key, mass_flow, pressure, temperature)
                return
            inlets = tuple(
                _station(
                    self._gas,
                    mass_flow_kg_s=_as_float(inputs[f"mf__{_safe(key)}"]),
                    total_pressure_pa=_as_float(inputs[f"pt__{_safe(key)}"]),
                    total_temperature_k=_as_float(inputs[f"tt__{_safe(key)}"]),
                )
                for key in self._node.inlet_keys
            )
            parameters = self._node.parameters
            if self._field is not None:
                parameters = _parameters_with_override(
                    self._node, self._field, _as_float(inputs["ratio__override"])
                )
            evaluation = evaluate_component(
                node_id=self._node.node_id,
                kind=self._node.kind,
                parameters=parameters,
                gas=self._gas,
                inlet_states=inlets,
                outlet_keys=self._node.outlet_keys,
                shaft_id=self._node.shaft_id,
            )
            outputs["power__w"] = evaluation.shaft_power_w
            outputs["fuel__flow"] = evaluation.fuel_flow_kg_s
            outputs["thrust__n"] = evaluation.thrust_n
            for key in self._node.outlet_keys:
                _write_state(outputs, key, evaluation.output_state(key))

    return _NodeComponent()


class OpenMdaoCycleEngine:
    """Prepare, set up, execute, and parse a real OpenMDAO cycle network."""

    def __init__(
        self,
        model: CycleModel,
        operating_point: CycleOperatingPoint | None = None,
        *,
        policy: OpenMdaoPolicy | None = None,
    ) -> None:
        self.model = model
        self.operating_point = operating_point or CycleOperatingPoint()
        self.policy = policy or OpenMdaoPolicy()
        if self.policy.tolerance <= 0 or self.policy.max_iterations <= 0:
            raise CycleModelError("OPENMDAO_POLICY_INVALID")
        self.speeds = resolve_spool_speeds(model)
        self.balance_targets = _balance_targets(model)
        self._balance_shafts: tuple[str, ...] = tuple(
            shaft.shaft_id
            for node_id in self.balance_targets
            for shaft in model.shafts
            if node_id in (*shaft.work_adding_nodes, *shaft.work_extracting_nodes)
        )
        self._problem: Any | None = None
        self._version: str | None = None
        self._result: CycleResult | None = None
        self._iterations = 0

    @staticmethod
    def status() -> CycleEngineStatus:
        return probe_cycle_engine("openmdao")

    def prepare(self) -> dict[str, object]:
        """Canonical description of the network the engine will execute."""

        pressure, temperature, mass_flow = self.operating_point.resolve(self.model)
        return {
            "library": "openmdao",
            "architectureId": self.model.architecture.architecture_id,
            "modelDigest": self.model.digest,
            "boundary": {
                "ambientTotalPressurePa": pressure,
                "ambientTotalTemperatureK": temperature,
                "massFlowKgS": mass_flow,
            },
            "nodes": [
                {
                    "id": node.node_id,
                    "kind": node.kind,
                    "shaft": node.shaft_id,
                    "inletKeys": list(node.inlet_keys),
                    "outletKeys": list(node.outlet_keys),
                }
                for node in sorted(self.model.nodes, key=lambda item: item.node_id)
            ],
            "balanceTargets": {
                key: value for key, value in sorted(self.balance_targets.items())
            },
        }

    def setup(self) -> OpenMdaoCycleEngine:
        status = probe_cycle_engine("openmdao")
        if not status.available:
            raise CycleCapabilityUnavailable(f"OpenMDAO is not installed: {status.detail}")
        import openmdao.api as om

        self._version = status.version or "unknown"
        pressure, temperature, mass_flow = self.operating_point.resolve(self.model)
        gas = self.model.design.gas
        problem = om.Problem(reports=False)
        model_group = problem.model
        paths: dict[str, str] = {}
        ordered_nodes = [self.model.node(node_id) for node_id in self.model.order]
        for node in ordered_nodes:
            path = f"c_{_safe(node.node_id)}"
            paths[node.node_id] = path
            model_group.add_subsystem(
                path,
                _make_node_component(
                    node=node,
                    gas=gas,
                    boundary=(mass_flow, pressure, temperature),
                    field=self.balance_targets.get(node.node_id),
                ),
            )
        if self.balance_targets:
            indep = om.IndepVarComp()
            for node_id in self.balance_targets:
                indep.add_output(f"b_{_safe(node_id)}", val=1.0)
            model_group.add_subsystem("balances", indep)
            for node_id in self.balance_targets:
                model_group.connect(
                    f"balances.b_{_safe(node_id)}",
                    f"{paths[node_id]}.ratio__override",
                )
        edge_lookup = {edge_key(edge): edge for edge in self.model.architecture.edges}
        for key, edge in edge_lookup.items():
            source = paths[edge.from_node]
            target = paths[edge.to_node]
            for prefix in ("mf", "pt", "tt"):
                model_group.connect(
                    f"{source}.{prefix}__{_safe(key)}",
                    f"{target}.{prefix}__{_safe(key)}",
                )
        problem.setup()
        self._problem = problem
        return self

    def _shaft_powers(self) -> tuple[ShaftPower, ...]:
        problem = self._require_problem()
        produced: dict[str, float] = {shaft.shaft_id: 0.0 for shaft in self.model.shafts}
        required: dict[str, float] = {shaft.shaft_id: 0.0 for shaft in self.model.shafts}
        for node in self.model.nodes:
            if node.shaft_id is None:
                continue
            power = _as_float(problem.get_val(f"c_{_safe(node.node_id)}.power__w"))
            if power >= 0:
                produced[node.shaft_id] += power
            else:
                required[node.shaft_id] += -power
        return tuple(
            shaft_power(
                self.model,
                shaft,
                produced_w=produced[shaft.shaft_id],
                required_w=required[shaft.shaft_id],
                speed_rpm=self.speeds.get(shaft.shaft_id),
            )
            for shaft in self.model.shafts
        )

    def _require_problem(self) -> Any:
        if self._problem is None:
            raise CycleModelError("OPENMDAO_PROBLEM_NOT_SET_UP")
        return self._problem

    def _residual_vector(self) -> list[float]:
        powers = {power.shaft_id: power for power in self._shaft_powers()}
        return [
            powers[shaft_id].signed_residual_fraction for shaft_id in self._balance_shafts
        ]

    def _evaluate(self, values: list[float]) -> list[float]:
        problem = self._require_problem()
        for node_id, value in zip(self.balance_targets, values, strict=True):
            problem.set_val(f"balances.b_{_safe(node_id)}", value)
        problem.run_model()
        return self._residual_vector()

    def solve(self) -> CycleResult:
        if self._problem is None:
            self.setup()
        variables = list(self.balance_targets)
        values = [
            _clamp_ratio(
                _initial_value(self.model.node(node_id), self.balance_targets[node_id])
            )
            for node_id in variables
        ]
        residual = self._evaluate(values)
        iteration = 0
        converged = max((abs(item) for item in residual), default=0.0) <= self.policy.tolerance
        while not converged and iteration < self.policy.max_iterations:
            iteration += 1
            jacobian: list[list[float]] = [[0.0] * len(values) for _ in values]
            for column, value in enumerate(values):
                step = max(1e-5, abs(value) * 1e-4)
                perturbed = list(values)
                perturbed[column] = _clamp_ratio(value + step)
                perturbed_residual = self._evaluate(perturbed)
                actual = perturbed[column] - value
                if actual == 0:
                    continue
                for row in range(len(values)):
                    jacobian[row][column] = (
                        perturbed_residual[row] - residual[row]
                    ) / actual
            direction = _solve_linear(jacobian, [-item for item in residual])
            if direction is None:
                direction = [-item for item in residual]
            accepted = False
            inherited = max((abs(item) for item in residual), default=0.0)
            for alpha in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
                candidate = [
                    _clamp_ratio(value + alpha * delta)
                    for value, delta in zip(values, direction, strict=True)
                ]
                candidate_residual = self._evaluate(candidate)
                if max((abs(item) for item in candidate_residual), default=0.0) < inherited:
                    values = candidate
                    residual = candidate_residual
                    accepted = True
                    break
            if not accepted:
                break
            converged = max((abs(item) for item in residual), default=0.0) <= self.policy.tolerance
        self._iterations = iteration
        self._result = self._build_result(converged)
        return self._result

    def _extract_edge_states(
        self,
    ) -> tuple[dict[str, StationState], dict[str, tuple[str, str]]]:
        problem = self._require_problem()
        gas = self.model.design.gas
        edge_states: dict[str, StationState] = {}
        edge_meta: dict[str, tuple[str, str]] = {}
        edge_lookup = {edge_key(edge): edge for edge in self.model.architecture.edges}
        for node in self.model.nodes:
            path = f"c_{_safe(node.node_id)}"
            for key in node.outlet_keys:
                safe = _safe(key)
                mf = _as_float(problem.get_val(f"{path}.mf__{safe}"))
                pt = _as_float(problem.get_val(f"{path}.pt__{safe}"))
                tt = _as_float(problem.get_val(f"{path}.tt__{safe}"))
                ps = _as_float(problem.get_val(f"{path}.ps__{safe}"))
                ts = _as_float(problem.get_val(f"{path}.ts__{safe}"))
                vel = _as_float(problem.get_val(f"{path}.vel__{safe}"))
                mach = _as_float(problem.get_val(f"{path}.mach__{safe}"))
                edge_states[key] = _station(
                    gas,
                    mass_flow_kg_s=mf,
                    total_pressure_pa=pt,
                    total_temperature_k=tt,
                    static_pressure_pa=ps if ps > 0 else None,
                    static_temperature_k=ts if ts > 0 else None,
                    velocity_m_s=vel if vel > 0 else None,
                    mach=mach if mach > 0 else None,
                )
                edge = edge_lookup[key]
                edge_meta[key] = (edge.from_node, edge.station or key)
        return edge_states, edge_meta

    def _build_result(self, converged: bool) -> CycleResult:
        problem = self._require_problem()
        edge_states, edge_meta = self._extract_edge_states()
        powers = self._shaft_powers()
        residuals = compute_residuals(
            self.model,
            edge_states=edge_states,
            shaft_powers=powers,
            speeds_rpm=self.speeds,
        )
        pressure, temperature, mass_flow = self.operating_point.resolve(self.model)
        version = self._version or "unknown"
        run_id = content_digest(
            {
                "modelDigest": self.model.digest,
                "engine": "openmdao",
                "version": version,
                "boundary": [pressure, temperature, mass_flow],
                "iterations": self._iterations,
            }
        )
        provenance = Provenance.from_inputs(
            source=ResultSource.NATIVE_SOLVER,
            model="openmdao-generic-cycle-network",
            model_version=version,
            fidelity=FidelityLevel.ANALYTICAL,
            inputs={
                "model": self.model.canonical(),
                "boundary": {
                    "ambientTotalPressurePa": pressure,
                    "ambientTotalTemperatureK": temperature,
                    "massFlowKgS": mass_flow,
                },
            },
            assumptions=(
                "0-D lumped cycle network executed by openmdao.Problem.run_model",
                "governing physics fidelity is the analytical cycle class; "
                "source records the executing engine",
                "not pyCycle",
            ),
            solver_name="openmdao",
            solver_version=version,
            run_id=run_id,
        )
        fuel_flow = sum(
            _as_float(problem.get_val(f"c_{_safe(node.node_id)}.fuel__flow"))
            for node in self.model.nodes
        )
        thrust = sum(
            _as_float(problem.get_val(f"c_{_safe(node.node_id)}.thrust__n"))
            for node in self.model.nodes
        )
        return build_result(
            self.model,
            edge_states=edge_states,
            edge_meta=edge_meta,
            powers=powers,
            residuals=residuals,
            fidelity=CycleFidelity.OPENMDAO_GENERIC.value,
            source=ResultSource.NATIVE_SOLVER.value,
            engine="openmdao-generic-network",
            provenance=provenance,
            iterations=self._iterations,
            converged=converged,
            tolerance=self.policy.tolerance,
            fuel_flow_kg_s=fuel_flow,
            thrust_n=thrust,
            detail=f"openmdao {version}, {self._iterations} matching iterations",
        )

    def result(self) -> CycleResult:
        if self._result is None:
            return self.solve()
        return self._result


def solve_with_openmdao(
    model: CycleModel,
    operating_point: CycleOperatingPoint | None = None,
    *,
    policy: OpenMdaoPolicy | None = None,
) -> CycleResult:
    """Execute the generic OpenMDAO component network at its labelled fidelity."""

    status = probe_cycle_engine("openmdao")
    if not status.available:
        raise CycleCapabilityUnavailable(f"OpenMDAO is not installed: {status.detail}")
    engine = OpenMdaoCycleEngine(model, operating_point, policy=policy)
    engine.setup()
    return engine.solve()


__all__ = [
    "OpenMdaoCycleEngine",
    "OpenMdaoPolicy",
    "PyCycleCase",
    "parse_pycycle_result",
    "prepare_pycycle_case",
    "pycycle_supported_topology",
    "solve_with_openmdao",
    "solve_with_pycycle",
]
