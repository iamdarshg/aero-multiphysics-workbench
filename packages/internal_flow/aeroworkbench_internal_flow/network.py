"""Generic steady internal-flow network: contract, solver, and conservation receipts.

A :class:`FluidNetwork` is a typed graph of nodes (plena, junctions, rotating
cavities, and fixed-pressure sources/sinks/bleed ports) and branches (ducts,
orifices, valves, seals, heat exchangers, and work machines). The solver couples
mass, momentum/pressure loss, and enthalpy/energy conservation with a damped
Newton iteration whose Jacobian is evaluated by central differences, so a
quadratic ``dp ~ m|m|`` branch with zero flow does not produce a singular step.

Every solved result carries source, fidelity, units, validity, input hash,
software identity, and provenance; non-convergence is reported honestly rather
than hidden, and a requested native fidelity fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import (
    PropertyId,
    SoftwareIdentity,
    WorkingFluid,
    evaluate_ideal_gas,
    fluid_digest,
)

from .correlations import CorrelationRef, windage_moment_coefficient, windage_power_w
from .errors import (
    InternalFlowCapabilityUnavailableError,
    InternalFlowValidationError,
)
from .kinds import BOUNDARY_NODE_KINDS, INTERNAL_NODE_KINDS, BranchKind, NodeKind
from .losses import (
    ExplicitResistance,
    LossModel,
    evaluate_loss_model,
    loss_model_payload,
    mean_density,
)
from .provenance import (
    SOFTWARE_IDENTITY,
    ResultValidity,
    analytical_provenance,
)
from .states import BranchState, HydraulicResistance, ModelReference

_MODEL_NAME = "aeroworkbench-internal-flow:network"
_MOMENTUM_WEIGHT = 1.0 / 1.0e4
_MASS_WEIGHT = 1.0 / 1.0e-3
_ENERGY_WEIGHT = 1.0 / 1.0e3
_SUPPORTED_FIDELITIES = frozenset({"analytical", "reduced"})


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """A typed control volume or fixed boundary of the network."""

    node_id: str
    kind: NodeKind
    fluid: WorkingFluid
    pressure_pa: float | None = None
    temperature_k: float | None = None
    heat_load_w: float = 0.0
    rotation_speed_rpm: float = 0.0
    cavity_radius_m: float | None = None
    windage_sides: int = 2

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise InternalFlowValidationError("NODE_ID_REQUIRED")
        if not isfinite(self.heat_load_w):
            raise InternalFlowValidationError(f"NODE_HEAT_LOAD_NONFINITE:{self.node_id}")
        if self.kind in BOUNDARY_NODE_KINDS:
            if self.pressure_pa is None or self.temperature_k is None:
                raise InternalFlowValidationError(f"BOUNDARY_NODE_REQUIRES_P_T:{self.node_id}")
            if not isfinite(self.pressure_pa) or self.pressure_pa <= 0.0:
                raise InternalFlowValidationError(f"BOUNDARY_PRESSURE_INVALID:{self.node_id}")
            if not isfinite(self.temperature_k) or self.temperature_k <= 0.0:
                raise InternalFlowValidationError(f"BOUNDARY_TEMPERATURE_INVALID:{self.node_id}")
        elif self.kind in INTERNAL_NODE_KINDS:
            if self.pressure_pa is not None or self.temperature_k is not None:
                raise InternalFlowValidationError(f"INTERNAL_NODE_MUST_NOT_FIX_P_T:{self.node_id}")
        else:
            raise InternalFlowValidationError(f"UNKNOWN_NODE_KIND:{self.kind}")
        if self.kind is NodeKind.CAVITY:
            if self.rotation_speed_rpm <= 0.0 or self.cavity_radius_m is None:
                raise InternalFlowValidationError(
                    f"CAVITY_REQUIRES_ROTATION_AND_RADIUS:{self.node_id}"
                )
            if not isfinite(self.cavity_radius_m) or self.cavity_radius_m <= 0.0:
                raise InternalFlowValidationError(f"CAVITY_RADIUS_INVALID:{self.node_id}")
            if self.windage_sides < 1:
                raise InternalFlowValidationError(f"CAVITY_WINDAGE_SIDES_INVALID:{self.node_id}")
        elif self.rotation_speed_rpm != 0.0:
            raise InternalFlowValidationError(f"ROTATION_ONLY_VALID_ON_CAVITY:{self.node_id}")

    @property
    def is_boundary(self) -> bool:
        return self.kind in BOUNDARY_NODE_KINDS

    def canonical(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "kind": self.kind.value,
            "fluid": self.fluid.identity,
            "fluidDigest": fluid_digest(self.fluid),
            "pressurePa": self.pressure_pa,
            "temperatureK": self.temperature_k,
            "heatLoadW": self.heat_load_w,
            "rotationSpeedRpm": self.rotation_speed_rpm,
            "cavityRadiusM": self.cavity_radius_m,
            "windageSides": self.windage_sides,
        }


@dataclass(frozen=True, slots=True)
class BranchSpec:
    """A typed loss/work element connecting two nodes."""

    branch_id: str
    kind: BranchKind
    from_node: str
    to_node: str
    loss_model: LossModel = field(
        default_factory=lambda: ExplicitResistance(0.0, 0.0, source="ideal-frictionless-branch")
    )
    pressure_rise_pa: float = 0.0
    heat_duty_w: float = 0.0
    shaft_power_w: float = 0.0
    shaft_efficiency: float = 1.0
    correlation_refs: tuple[CorrelationRef, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if not self.branch_id.strip():
            raise InternalFlowValidationError("BRANCH_ID_REQUIRED")
        if not self.from_node.strip() or not self.to_node.strip():
            raise InternalFlowValidationError(f"BRANCH_NODES_REQUIRED:{self.branch_id}")
        if self.from_node == self.to_node:
            raise InternalFlowValidationError(f"BRANCH_SELF_LOOP:{self.branch_id}")
        for label, value in (
            ("pressure_rise", self.pressure_rise_pa),
            ("heat_duty", self.heat_duty_w),
            ("shaft_power", self.shaft_power_w),
        ):
            if not isfinite(value):
                raise InternalFlowValidationError(
                    f"BRANCH_{label.upper()}_NONFINITE:{self.branch_id}"
                )
        if self.pressure_rise_pa < 0.0:
            raise InternalFlowValidationError(f"BRANCH_PRESSURE_RISE_NEGATIVE:{self.branch_id}")
        if self.shaft_power_w < 0.0:
            raise InternalFlowValidationError(f"BRANCH_SHAFT_POWER_NEGATIVE:{self.branch_id}")
        if not 0.0 < self.shaft_efficiency <= 1.0:
            raise InternalFlowValidationError(f"BRANCH_SHAFT_EFFICIENCY_INVALID:{self.branch_id}")

    @property
    def fluid_work_w(self) -> float:
        return self.shaft_power_w * self.shaft_efficiency

    def canonical(self) -> dict[str, Any]:
        return {
            "branchId": self.branch_id,
            "kind": self.kind.value,
            "fromNode": self.from_node,
            "toNode": self.to_node,
            "lossModel": loss_model_payload(self.loss_model),
            "pressureRisePa": self.pressure_rise_pa,
            "heatDutyW": self.heat_duty_w,
            "shaftPowerW": self.shaft_power_w,
            "shaftEfficiency": self.shaft_efficiency,
            "correlations": [ref.canonical() for ref in self.correlation_refs],
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class NodeResult:
    """Solved state of one node with its units and residuals."""

    node_id: str
    kind: NodeKind
    is_boundary: bool
    pressure_pa: float
    temperature_k: float
    density_kg_m3: float
    viscosity_pa_s: float | None
    cp_j_kg_k: float
    enthalpy_j_kg: float
    heat_load_w: float
    windage_heat_w: float
    net_mass_flow_kg_s: float

    def canonical(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "kind": self.kind.value,
            "isBoundary": self.is_boundary,
            "pressurePa": self.pressure_pa,
            "temperatureK": self.temperature_k,
            "densityKgM3": self.density_kg_m3,
            "viscosityPaS": self.viscosity_pa_s,
            "cpJkgK": self.cp_j_kg_k,
            "enthalpyJkg": self.enthalpy_j_kg,
            "heatLoadW": self.heat_load_w,
            "windageHeatW": self.windage_heat_w,
            "netMassFlowKgS": self.net_mass_flow_kg_s,
            "units": {"pressure": "Pa", "temperature": "K", "massFlow": "kg/s"},
        }


@dataclass(frozen=True, slots=True)
class BranchResult:
    """Solved flow, loss, and energy transport of one branch."""

    branch_id: str
    kind: BranchKind
    from_node: str
    to_node: str
    mass_flow_kg_s: float
    volumetric_flow_m3_s: float
    pressure_drop_pa: float
    pressure_rise_pa: float
    heat_duty_w: float
    shaft_power_w: float
    fluid_work_w: float
    enthalpy_rise_j_kg: float
    reynolds_number: float | None
    friction_factor: float | None
    resistance: HydraulicResistance
    correlation_refs: tuple[ModelReference, ...]
    notes: tuple[str, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "branchId": self.branch_id,
            "kind": self.kind.value,
            "fromNode": self.from_node,
            "toNode": self.to_node,
            "massFlowKgS": self.mass_flow_kg_s,
            "volumetricFlowM3S": self.volumetric_flow_m3_s,
            "pressureDropPa": self.pressure_drop_pa,
            "pressureRisePa": self.pressure_rise_pa,
            "heatDutyW": self.heat_duty_w,
            "shaftPowerW": self.shaft_power_w,
            "fluidWorkW": self.fluid_work_w,
            "enthalpyRiseJkg": self.enthalpy_rise_j_kg,
            "reynoldsNumber": self.reynolds_number,
            "frictionFactor": self.friction_factor,
            "resistance": self.resistance.canonical(),
            "correlations": [ref.canonical() for ref in self.correlation_refs],
            "notes": list(self.notes),
            "units": {"massFlow": "kg/s", "pressure": "Pa", "heat": "W"},
        }


@dataclass(frozen=True, slots=True)
class NetworkResult:
    """Complete solved network with explicit conservation and provenance."""

    network_name: str
    nodes: tuple[NodeResult, ...]
    branches: tuple[BranchResult, ...]
    mass_residual_kg_s: float
    momentum_residual_pa: float
    energy_residual_w: float
    converged: bool
    iterations: int
    fidelity: str
    source: ResultSource
    validity: ResultValidity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def node(self, node_id: str) -> NodeResult:
        for item in self.nodes:
            if item.node_id == node_id:
                return item
        raise InternalFlowValidationError(f"UNKNOWN_RESULT_NODE:{node_id}")

    def branch(self, branch_id: str) -> BranchResult:
        for item in self.branches:
            if item.branch_id == branch_id:
                return item
        raise InternalFlowValidationError(f"UNKNOWN_RESULT_BRANCH:{branch_id}")

    def canonical(self) -> dict[str, Any]:
        return {
            "networkName": self.network_name,
            "nodes": [item.canonical() for item in self.nodes],
            "branches": [item.canonical() for item in self.branches],
            "residuals": {
                "massKgS": self.mass_residual_kg_s,
                "momentumPa": self.momentum_residual_pa,
                "energyW": self.energy_residual_w,
            },
            "converged": self.converged,
            "iterations": self.iterations,
            "fidelity": self.fidelity,
            "source": self.source.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
            "provenance": {
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "solverName": self.provenance.solver_name,
                "solverVersion": self.provenance.solver_version,
                "runId": self.provenance.run_id,
                "assumptions": list(self.provenance.assumptions),
            },
        }


def _evaluate_state(fluid: WorkingFluid, pressure_pa: float, temperature_k: float) -> BranchState:
    evaluation = evaluate_ideal_gas(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    viscosity = (
        evaluation.value(PropertyId.VISCOSITY)
        if evaluation.has(PropertyId.VISCOSITY)
        else None
    )
    return BranchState(
        pressure_pa=pressure_pa,
        temperature_k=temperature_k,
        density_kg_m3=evaluation.value(PropertyId.DENSITY),
        viscosity_pa_s=viscosity,
        cp_j_kg_k=evaluation.value(PropertyId.CP),
        enthalpy_j_kg=evaluation.value(PropertyId.ENTHALPY),
    )


def _cavity_windage(node: NodeSpec, state: BranchState) -> tuple[float, tuple[CorrelationRef, ...]]:
    if node.kind is not NodeKind.CAVITY or node.rotation_speed_rpm <= 0.0:
        return 0.0, ()
    radius = node.cavity_radius_m
    if radius is None:
        raise InternalFlowValidationError(f"CAVITY_RADIUS_REQUIRED:{node.node_id}")
    if state.viscosity_pa_s is None:
        raise InternalFlowCapabilityUnavailableError(
            f"MISSING_TRANSPORT_FOR_WINDAGE:{node.node_id}"
        )
    angular_velocity = 2.0 * pi * node.rotation_speed_rpm / 60.0
    rotational_reynolds = (
        state.density_kg_m3 * angular_velocity * radius * radius / state.viscosity_pa_s
    )
    if rotational_reynolds <= 0.0:
        return 0.0, ()
    coefficient, reference = windage_moment_coefficient(rotational_reynolds)
    power = windage_power_w(
        density_kg_m3=state.density_kg_m3,
        angular_velocity_rad_s=angular_velocity,
        radius_m=radius,
        moment_coefficient=coefficient,
        sides=node.windage_sides,
    )
    return power, (reference,)


def _solve_linear(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = len(rhs)
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-300:
            raise InternalFlowValidationError("NETWORK_JACOBIAN_SINGULAR")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column] / augmented[column][column]
            for index in range(column, size + 1):
                augmented[row][index] -= factor * augmented[column][index]
    return [augmented[index][size] / augmented[index][index] for index in range(size)]


def _invert_flow_law(
    drive_pa: float, resistance: HydraulicResistance, density_kg_m3: float
) -> float:
    """Exact inverse of ``dp = R_lin Q + R_quad Q|Q|`` for an initial flow guess."""
    linear = resistance.linear_pa_s_m3
    quadratic = resistance.quadratic_pa_s2_m6
    if drive_pa == 0.0:
        return 0.0
    magnitude = abs(drive_pa)
    if quadratic == 0.0:
        if linear == 0.0:
            return 0.0
        volumetric = magnitude / linear
    else:
        volumetric = (-linear + sqrt(linear * linear + 4.0 * quadratic * magnitude)) / (
            2.0 * quadratic
        )
    return (1.0 if drive_pa > 0.0 else -1.0) * volumetric * density_kg_m3


def _invert_enthalpy(fluid: WorkingFluid, target_j_kg: float) -> float:
    """Invert the ideal-gas enthalpy for temperature by deterministic bisection."""
    temperature_range = fluid.temperature_range()
    if fluid.transport is not None:
        temperature_range = temperature_range.intersection(fluid.transport.validity)
    low = temperature_range.minimum
    high = temperature_range.maximum
    for _ in range(80):
        middle = 0.5 * (low + high)
        enthalpy = evaluate_ideal_gas(
            fluid, temperature_k=middle, pressure_pa=101325.0
        ).value(PropertyId.ENTHALPY)
        if enthalpy < target_j_kg:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


class FluidNetwork:
    """A typed, mutable builder that solves to an immutable :class:`NetworkResult`."""

    def __init__(self, *, name: str = "internal-flow-network") -> None:
        if not name.strip():
            raise InternalFlowValidationError("NETWORK_NAME_REQUIRED")
        self.name = name
        self._nodes: dict[str, NodeSpec] = {}
        self._branches: dict[str, BranchSpec] = {}

    def add_node(self, spec: NodeSpec) -> FluidNetwork:
        if spec.node_id in self._nodes:
            raise InternalFlowValidationError(f"DUPLICATE_NODE:{spec.node_id}")
        self._nodes[spec.node_id] = spec
        return self

    def add_branch(self, spec: BranchSpec) -> FluidNetwork:
        if spec.branch_id in self._branches:
            raise InternalFlowValidationError(f"DUPLICATE_BRANCH:{spec.branch_id}")
        self._branches[spec.branch_id] = spec
        return self

    @property
    def nodes(self) -> tuple[NodeSpec, ...]:
        return tuple(self._nodes.values())

    @property
    def branches(self) -> tuple[BranchSpec, ...]:
        return tuple(self._branches.values())

    def network_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nodes": [self._nodes[key].canonical() for key in sorted(self._nodes)],
            "branches": [self._branches[key].canonical() for key in sorted(self._branches)],
        }

    def _validate_topology(self) -> None:
        if not self._nodes:
            raise InternalFlowValidationError("NETWORK_EMPTY")
        if not any(node.is_boundary for node in self._nodes.values()):
            raise InternalFlowValidationError("NETWORK_REQUIRES_BOUNDARY")
        for branch in self._branches.values():
            for endpoint in (branch.from_node, branch.to_node):
                if endpoint not in self._nodes:
                    raise InternalFlowValidationError(
                        f"BRANCH_ENDPOINT_UNKNOWN:{branch.branch_id}:{endpoint}"
                    )
        for node in self._nodes.values():
            if node.is_boundary:
                continue
            connected = any(
                node.node_id in (branch.from_node, branch.to_node)
                for branch in self._branches.values()
            )
            if not connected:
                raise InternalFlowValidationError(f"INTERNAL_NODE_DISCONNECTED:{node.node_id}")

    def _components(
        self,
        internal_nodes: list[str],
        branches: list[BranchSpec],
        pressures: dict[str, float],
        temperatures: dict[str, float],
        flows: dict[str, float],
    ) -> tuple[list[float], list[float], list[float]]:
        states = {
            node_id: _evaluate_state(node.fluid, pressures[node_id], temperatures[node_id])
            for node_id, node in self._nodes.items()
        }
        momentum: list[float] = []
        for branch in branches:
            mass_flow = flows[branch.branch_id]
            from_state = states[branch.from_node]
            to_state = states[branch.to_node]
            density = mean_density(from_state, to_state)
            volumetric = mass_flow / density
            resistance, _ = evaluate_loss_model(
                branch.loss_model,
                mass_flow_kg_s=mass_flow,
                from_state=from_state,
                to_state=to_state,
                enforce_validity=False,
            )
            loss = resistance.pressure_drop_pa(volumetric)
            momentum.append(
                (pressures[branch.from_node] - pressures[branch.to_node])
                + branch.pressure_rise_pa
                - loss
            )
        mass: list[float] = []
        energy: list[float] = []
        for node_id in internal_nodes:
            net = 0.0
            for branch in branches:
                if branch.to_node == node_id:
                    net += flows[branch.branch_id]
                elif branch.from_node == node_id:
                    net -= flows[branch.branch_id]
            mass.append(net)
            inflow = 0.0
            outflow = 0.0
            for branch in branches:
                if branch.to_node == node_id:
                    mass_into = flows[branch.branch_id]
                    other = branch.from_node
                elif branch.from_node == node_id:
                    mass_into = -flows[branch.branch_id]
                    other = branch.to_node
                else:
                    continue
                branch_energy = branch.heat_duty_w + branch.fluid_work_w
                if mass_into >= 0.0:
                    inflow += mass_into * states[other].enthalpy_j_kg + branch_energy
                else:
                    outflow += -mass_into
            windage, _ = _cavity_windage(self._nodes[node_id], states[node_id])
            energy.append(
                inflow
                + self._nodes[node_id].heat_load_w
                + windage
                - outflow * states[node_id].enthalpy_j_kg
            )
        return momentum, mass, energy

    def solve(
        self,
        *,
        fidelity: str = "analytical",
        tolerance: float = 1e-6,
        max_iterations: int = 200,
    ) -> NetworkResult:
        if fidelity not in _SUPPORTED_FIDELITIES:
            raise InternalFlowCapabilityUnavailableError(
                f"NETWORK_FIDELITY_REQUIRES_NATIVE_CFD:{fidelity}"
            )
        if tolerance <= 0.0 or max_iterations <= 0:
            raise InternalFlowValidationError("INVALID_SOLVER_SETTINGS")
        self._validate_topology()
        internal_nodes = sorted(
            node.node_id for node in self._nodes.values() if not node.is_boundary
        )
        branches = list(self._branches.values())
        boundary = {node.node_id: node for node in self._nodes.values() if node.is_boundary}
        mean_pressure = sum(
            node.pressure_pa for node in boundary.values() if node.pressure_pa is not None
        ) / len(boundary)
        mean_temperature = sum(
            node.temperature_k for node in boundary.values() if node.temperature_k is not None
        ) / len(boundary)
        pressures = {node_id: mean_pressure for node_id in self._nodes}
        temperatures = {node_id: mean_temperature for node_id in self._nodes}
        for node_id, node in boundary.items():
            pressure = node.pressure_pa
            temperature = node.temperature_k
            if pressure is None or temperature is None:
                raise InternalFlowValidationError(f"BOUNDARY_NODE_REQUIRES_P_T:{node_id}")
            pressures[node_id] = pressure
            temperatures[node_id] = temperature
        flows = self._initial_flows(branches, pressures, temperatures)
        iterations = 0
        converged = False
        for iteration in range(1, max_iterations + 1):
            iterations = iteration
            flows, states = self._solve_pressures(
                internal_nodes, branches, pressures, temperatures, flows
            )
            for node_id in internal_nodes:
                self._update_temperature(node_id, branches, states, flows, temperatures)
            momentum, mass, energy = self._components(
                internal_nodes, branches, pressures, temperatures, flows
            )
            max_momentum = max((abs(value) for value in momentum), default=0.0)
            max_mass = max((abs(value) for value in mass), default=0.0)
            max_energy = max((abs(value) for value in energy), default=0.0)
            normalized = max(
                max_mass * _MASS_WEIGHT,
                max_momentum * _MOMENTUM_WEIGHT,
                max_energy * _ENERGY_WEIGHT,
            )
            if normalized <= tolerance:
                converged = True
                break
        momentum, mass, energy = self._components(
            internal_nodes, branches, pressures, temperatures, flows
        )
        max_momentum = max((abs(value) for value in momentum), default=0.0)
        max_mass = max((abs(value) for value in mass), default=0.0)
        max_energy = max((abs(value) for value in energy), default=0.0)
        validity = ResultValidity(
            passed=converged,
            checks={
                "converged": converged,
                "mass_closure": max_mass <= max(tolerance * 1e3, 1e-9),
                "energy_closure": max_energy <= max(tolerance * 1e3, 1e-6),
            },
            detail=(
                "steady mass/momentum/energy closure satisfied"
                if converged
                else f"steady solve did not converge in {iterations} iterations"
            ),
        )
        return self._build_result(
            branches, pressures, temperatures, flows, converged, iterations,
            max_mass, max_momentum, max_energy, fidelity, validity,
        )

    def _solve_pressures(
        self,
        internal_nodes: list[str],
        branches: list[BranchSpec],
        pressures: dict[str, float],
        temperatures: dict[str, float],
        reference_flows: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, BranchState]]:
        """Solve node pressures so branch flows satisfy mass conservation."""
        index = {node_id: position for position, node_id in enumerate(internal_nodes)}
        flows = dict(reference_flows)
        states = {
            node_id: _evaluate_state(node.fluid, pressures[node_id], temperatures[node_id])
            for node_id, node in self._nodes.items()
        }
        for _ in range(80):
            states = {
                node_id: _evaluate_state(node.fluid, pressures[node_id], temperatures[node_id])
                for node_id, node in self._nodes.items()
            }
            flow: dict[str, float] = {}
            slope: dict[str, float] = {}
            for branch in branches:
                from_state = states[branch.from_node]
                to_state = states[branch.to_node]
                density = mean_density(from_state, to_state)
                resistance, _ = evaluate_loss_model(
                    branch.loss_model,
                    mass_flow_kg_s=flows[branch.branch_id],
                    from_state=from_state,
                    to_state=to_state,
                    enforce_validity=False,
                )
                drive = (
                    pressures[branch.from_node]
                    - pressures[branch.to_node]
                    + branch.pressure_rise_pa
                )
                value = _invert_flow_law(drive, resistance, density)
                flow[branch.branch_id] = value
                volumetric = abs(value) / density if density > 0.0 else 0.0
                denominator = resistance.linear_pa_s_m3 + (
                    2.0
                    * resistance.quadratic_pa_s2_m6
                    * max(volumetric, 1.0e-3)
                )
                slope[branch.branch_id] = density / denominator if denominator > 0.0 else 0.0
            residual = [0.0] * len(internal_nodes)
            matrix = [[0.0] * len(internal_nodes) for _ in internal_nodes]
            for branch in branches:
                value = flow[branch.branch_id]
                derivative = slope[branch.branch_id]
                upstream = branch.from_node
                downstream = branch.to_node
                if downstream in index:
                    residual[index[downstream]] += value
                if upstream in index:
                    residual[index[upstream]] -= value
                if upstream in index and downstream in index:
                    first = index[upstream]
                    second = index[downstream]
                    matrix[first][first] -= derivative
                    matrix[first][second] += derivative
                    matrix[second][second] -= derivative
                    matrix[second][first] += derivative
                elif upstream in index:
                    matrix[index[upstream]][index[upstream]] -= derivative
                elif downstream in index:
                    matrix[index[downstream]][index[downstream]] -= derivative
            if max((abs(value) for value in residual), default=0.0) <= 1.0e-9:
                flows = flow
                break
            for position in range(len(internal_nodes)):
                matrix[position][position] += 1.0e-12
            try:
                correction = _solve_linear(matrix, [-value for value in residual])
            except InternalFlowValidationError:
                flows = flow
                break
            for position, node_id in enumerate(internal_nodes):
                pressures[node_id] = max(pressures[node_id] + correction[position], 1.0)
            flows = flow
        states = {
            node_id: _evaluate_state(node.fluid, pressures[node_id], temperatures[node_id])
            for node_id, node in self._nodes.items()
        }
        for branch in branches:
            from_state = states[branch.from_node]
            to_state = states[branch.to_node]
            density = mean_density(from_state, to_state)
            resistance, _ = evaluate_loss_model(
                branch.loss_model,
                mass_flow_kg_s=flows[branch.branch_id],
                from_state=from_state,
                to_state=to_state,
                enforce_validity=False,
            )
            drive = (
                pressures[branch.from_node]
                - pressures[branch.to_node]
                + branch.pressure_rise_pa
            )
            flows[branch.branch_id] = _invert_flow_law(drive, resistance, density)
        return flows, states

    def _update_temperature(
        self,
        node_id: str,
        branches: list[BranchSpec],
        states: dict[str, BranchState],
        flows: dict[str, float],
        temperatures: dict[str, float],
    ) -> None:
        inflow_enthalpy = 0.0
        outflow_mass = 0.0
        for branch in branches:
            mass_flow = flows[branch.branch_id]
            if branch.to_node == node_id:
                mass_into = mass_flow
                other = branch.from_node
            elif branch.from_node == node_id:
                mass_into = -mass_flow
                other = branch.to_node
            else:
                continue
            branch_energy = branch.heat_duty_w + branch.fluid_work_w
            if mass_into >= 0.0:
                inflow_enthalpy += mass_into * states[other].enthalpy_j_kg + branch_energy
            else:
                outflow_mass += -mass_into
        if outflow_mass <= 1.0e-12:
            return
        windage, _ = _cavity_windage(self._nodes[node_id], states[node_id])
        target = (
            inflow_enthalpy + self._nodes[node_id].heat_load_w + windage
        ) / outflow_mass
        fluid = self._nodes[node_id].fluid
        temperature_range = fluid.temperature_range()
        if fluid.transport is not None:
            temperature_range = temperature_range.intersection(fluid.transport.validity)
        updated = _invert_enthalpy(fluid, target)
        updated = min(max(updated, temperature_range.minimum), temperature_range.maximum)
        temperatures[node_id] = 0.5 * temperatures[node_id] + 0.5 * updated

    def _initial_flows(
        self,
        branches: list[BranchSpec],
        pressures: dict[str, float],
        temperatures: dict[str, float],
    ) -> dict[str, float]:
        guess = 1.0e-3
        flows: dict[str, float] = {}
        for branch in branches:
            from_node = self._nodes[branch.from_node]
            to_node = self._nodes[branch.to_node]
            from_state = _evaluate_state(
                from_node.fluid, pressures[branch.from_node], temperatures[branch.from_node]
            )
            to_state = _evaluate_state(
                to_node.fluid, pressures[branch.to_node], temperatures[branch.to_node]
            )
            density = mean_density(from_state, to_state)
            resistance, _ = evaluate_loss_model(
                branch.loss_model,
                mass_flow_kg_s=guess,
                from_state=from_state,
                to_state=to_state,
                enforce_validity=False,
            )
            drive = (
                pressures[branch.from_node]
                - pressures[branch.to_node]
                + branch.pressure_rise_pa
            )
            flows[branch.branch_id] = _invert_flow_law(drive, resistance, density)
        return flows

    def _build_result(
        self,
        branches: list[BranchSpec],
        pressures: dict[str, float],
        temperatures: dict[str, float],
        flows: dict[str, float],
        converged: bool,
        iterations: int,
        mass_residual: float,
        momentum_residual: float,
        energy_residual: float,
        fidelity: str,
        validity: ResultValidity,
    ) -> NetworkResult:
        states = {
            node_id: _evaluate_state(node.fluid, pressures[node_id], temperatures[node_id])
            for node_id, node in self._nodes.items()
        }
        branch_results: list[BranchResult] = []
        for branch in branches:
            mass_flow = flows[branch.branch_id]
            from_state = states[branch.from_node]
            to_state = states[branch.to_node]
            density = mean_density(from_state, to_state)
            resistance, evaluation = evaluate_loss_model(
                branch.loss_model,
                mass_flow_kg_s=mass_flow,
                from_state=from_state,
                to_state=to_state,
            )
            branch_energy = branch.heat_duty_w + branch.fluid_work_w
            enthalpy_rise = branch_energy / mass_flow if abs(mass_flow) > 1e-12 else 0.0
            branch_results.append(
                BranchResult(
                    branch_id=branch.branch_id,
                    kind=branch.kind,
                    from_node=branch.from_node,
                    to_node=branch.to_node,
                    mass_flow_kg_s=mass_flow,
                    volumetric_flow_m3_s=mass_flow / density,
                    pressure_drop_pa=pressures[branch.from_node] - pressures[branch.to_node],
                    pressure_rise_pa=branch.pressure_rise_pa,
                    heat_duty_w=branch.heat_duty_w,
                    shaft_power_w=branch.shaft_power_w,
                    fluid_work_w=branch.fluid_work_w,
                    enthalpy_rise_j_kg=enthalpy_rise,
                    reynolds_number=evaluation.reynolds_number,
                    friction_factor=evaluation.friction_factor,
                    resistance=resistance,
                    correlation_refs=tuple(branch.correlation_refs) + evaluation.correlation_refs,
                    notes=evaluation.notes,
                )
            )
        node_results: list[NodeResult] = []
        for node_id in sorted(self._nodes):
            node = self._nodes[node_id]
            windage, _ = _cavity_windage(node, states[node_id])
            net = 0.0
            for branch in branches:
                if branch.to_node == node_id:
                    net += flows[branch.branch_id]
                elif branch.from_node == node_id:
                    net -= flows[branch.branch_id]
            node_results.append(
                NodeResult(
                    node_id=node_id,
                    kind=node.kind,
                    is_boundary=node.is_boundary,
                    pressure_pa=states[node_id].pressure_pa,
                    temperature_k=states[node_id].temperature_k,
                    density_kg_m3=states[node_id].density_kg_m3,
                    viscosity_pa_s=states[node_id].viscosity_pa_s,
                    cp_j_kg_k=states[node_id].cp_j_kg_k,
                    enthalpy_j_kg=states[node_id].enthalpy_j_kg,
                    heat_load_w=node.heat_load_w,
                    windage_heat_w=windage,
                    net_mass_flow_kg_s=net,
                )
            )
        assumptions = (
            "steady, single-phase, one-dimensional branch network",
            "pressure loss from versioned correlations with declared validity",
            "rotating cavities evaluated at reduced fidelity with CFD escalation hooks",
        )
        provenance = analytical_provenance(
            _MODEL_NAME, {"network": self.network_payload()}, *assumptions
        )
        return NetworkResult(
            network_name=self.name,
            nodes=tuple(node_results),
            branches=tuple(branch_results),
            mass_residual_kg_s=mass_residual,
            momentum_residual_pa=momentum_residual,
            energy_residual_w=energy_residual,
            converged=converged,
            iterations=iterations,
            fidelity=fidelity,
            source=ResultSource.ANALYTICAL,
            validity=validity,
            provenance=provenance,
        )


__all__ = [
    "BranchResult",
    "BranchSpec",
    "FluidNetwork",
    "NetworkResult",
    "NodeResult",
    "NodeSpec",
]
