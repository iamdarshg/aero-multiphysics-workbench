"""Compile a TURBO 01 architecture plus a design into a solvable cycle model.

The compiler is the only place that understands the canonical architecture; the
components and the solver only see a directed, topologically-ordered graph of
generic nodes. Any architecture family -- driven fan, single/multi-spool gas
turbine, bypass/core split, free turbine, recuperated cycle, generator/load --
compiles through the same code path with no special-case solver logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from ..architecture import RotatingGasArchitecture, architecture_hash
from ..canonical import content_digest
from ..components import GasPathEdge
from ..rows import BladeRow
from ..shafts import Shaft, ShaftCoupling
from ..stations import Station
from .components import (
    NOZZLE_KINDS,
    WORK_ADDING_KINDS,
    WORK_EXTRACTING_KINDS,
    ComponentParameters,
)
from .contracts import CycleModelError
from .gas import AIR, GasProperties
from .maps import OperatingMap

_EDGE_SANITIZE = re.compile(r"[^0-9A-Za-z_]")


def edge_key(edge: GasPathEdge) -> str:
    raw = f"{edge.from_node}||{edge.kind}||{edge.to_node}||{edge.station or 'none'}"
    return _EDGE_SANITIZE.sub("_", raw)


@dataclass(frozen=True, slots=True)
class CycleDesign:
    """The user-declared design point: gas, boundary, and component parameters."""

    architecture: RotatingGasArchitecture
    component_parameters: tuple[tuple[str, ComponentParameters], ...] = ()
    gas: GasProperties = AIR
    ambient_total_pressure_pa: float = 101325.0
    ambient_total_temperature_k: float = 288.15
    mass_flow_kg_s: float = 1.0

    def __post_init__(self) -> None:
        if not self.mass_flow_kg_s > 0:
            raise CycleModelError("DESIGN_MASS_FLOW_MUST_BE_POSITIVE")
        if not self.ambient_total_pressure_pa > 0:
            raise CycleModelError("DESIGN_AMBIENT_PRESSURE_MUST_BE_POSITIVE")
        if not self.ambient_total_temperature_k > 0:
            raise CycleModelError("DESIGN_AMBIENT_TEMPERATURE_MUST_BE_POSITIVE")
        seen: set[str] = set()
        for node_id, _ in self.component_parameters:
            if not node_id.strip():
                raise CycleModelError("COMPONENT_PARAMETER_NODE_ID_REQUIRED")
            if node_id in seen:
                raise CycleModelError(f"DUPLICATE_COMPONENT_PARAMETERS:{node_id}")
            seen.add(node_id)

    def parameters_for(self, node_id: str) -> ComponentParameters:
        for candidate, parameters in self.component_parameters:
            if candidate == node_id:
                return parameters
        return ComponentParameters()

    def with_parameters(
        self, component_parameters: tuple[tuple[str, ComponentParameters], ...]
    ) -> CycleDesign:
        return replace(self, component_parameters=component_parameters)

    def canonical(self) -> dict[str, object]:
        return {
            "architectureHash": architecture_hash(self.architecture),
            "gas": self.gas.canonical(),
            "ambientTotalPressurePa": self.ambient_total_pressure_pa,
            "ambientTotalTemperatureK": self.ambient_total_temperature_k,
            "massFlowKgS": self.mass_flow_kg_s,
            "componentParameters": [
                [node_id, parameters.canonical()]
                for node_id, parameters in sorted(self.component_parameters)
            ],
        }


@dataclass(frozen=True, slots=True)
class CycleNodeSpec:
    """One compiled component node with resolved ports, spool, and parameters."""

    node_id: str
    kind: str
    shaft_id: str | None
    inlet_keys: tuple[str, ...]
    outlet_keys: tuple[str, ...]
    parameters: ComponentParameters
    declared_ratio: float | None = None

    @property
    def is_source(self) -> bool:
        return not self.inlet_keys

    @property
    def is_work_adding(self) -> bool:
        return self.kind in WORK_ADDING_KINDS

    @property
    def is_work_extracting(self) -> bool:
        return self.kind in WORK_EXTRACTING_KINDS

    def canonical(self) -> dict[str, object]:
        return {
            "nodeId": self.node_id,
            "kind": self.kind,
            "shaftId": self.shaft_id,
            "inletKeys": list(self.inlet_keys),
            "outletKeys": list(self.outlet_keys),
            "parameters": self.parameters.canonical(),
            "declaredRatio": self.declared_ratio,
        }


@dataclass(frozen=True, slots=True)
class CycleShaftSpec:
    """One spool with its member nodes, speed, loss, and couplings."""

    shaft_id: str
    kind: str
    speed_rpm: float | None
    mechanical_loss_fraction: float
    member_nodes: tuple[str, ...]
    work_adding_nodes: tuple[str, ...]
    work_extracting_nodes: tuple[str, ...]
    couplings: tuple[ShaftCoupling, ...]

    def canonical(self) -> dict[str, object]:
        return {
            "shaftId": self.shaft_id,
            "kind": self.kind,
            "speedRpm": self.speed_rpm,
            "mechanicalLossFraction": self.mechanical_loss_fraction,
            "memberNodes": list(self.member_nodes),
            "workAddingNodes": list(self.work_adding_nodes),
            "workExtractingNodes": list(self.work_extracting_nodes),
            "couplings": [
                coupling.canonical()
                for coupling in sorted(self.couplings, key=lambda item: item.coupling_id)
            ],
        }


@dataclass(frozen=True, slots=True)
class CycleModel:
    """A compiled, topologically-ordered, deterministically-hashed cycle model."""

    architecture: RotatingGasArchitecture
    design: CycleDesign
    nodes: tuple[CycleNodeSpec, ...]
    order: tuple[str, ...]
    shafts: tuple[CycleShaftSpec, ...]
    source_node_ids: tuple[str, ...]
    digest: str

    def node(self, node_id: str) -> CycleNodeSpec:
        for candidate in self.nodes:
            if candidate.node_id == node_id:
                return candidate
        raise CycleModelError(f"UNKNOWN_CYCLE_NODE:{node_id}")

    def shaft(self, shaft_id: str) -> CycleShaftSpec:
        for candidate in self.shafts:
            if candidate.shaft_id == shaft_id:
                return candidate
        raise CycleModelError(f"UNKNOWN_CYCLE_SHAFT:{shaft_id}")

    def canonical(self) -> dict[str, object]:
        return {
            "architectureHash": architecture_hash(self.architecture),
            "design": self.design.canonical(),
            "order": list(self.order),
            "sourceNodeIds": list(self.source_node_ids),
            "nodes": [node.canonical() for node in sorted(self.nodes, key=lambda n: n.node_id)],
            "shafts": [
                shaft.canonical() for shaft in sorted(self.shafts, key=lambda s: s.shaft_id)
            ],
            "maps": [component_map.canonical() for component_map in map_coefficients(self)],
        }


def _resolve_kind(kind: str, rows: tuple[BladeRow, ...]) -> str:
    if kind != "rotor_row":
        return kind
    roles = {row.role for row in rows}
    if "work_adding" in roles and "work_extracting" in roles:
        raise CycleModelError("ROTOR_ROW_MIXES_WORK_DIRECTIONS")
    if "work_adding" in roles:
        return "compressor_stage"
    if "work_extracting" in roles:
        return "turbine_stage"
    return "stator_row"


def _shaft_for_node(node_id: str, rows: tuple[BladeRow, ...]) -> str | None:
    shafts = {row.shaft for row in rows if row.shaft is not None}
    if len(shafts) > 1:
        raise CycleModelError(f"NODE_BOUND_TO_MULTIPLE_SHAFTS:{node_id}")
    return next(iter(shafts), None)


def _declared_ratio(
    architecture: RotatingGasArchitecture,
    inlet_keys: tuple[str, ...],
    outlet_keys: tuple[str, ...],
    *,
    extracting: bool,
) -> float | None:
    station_by_id = {station.station_id: station for station in architecture.stations}
    edge_by_key = {edge_key(edge): edge for edge in architecture.edges}

    def pressure(key: str) -> float | None:
        edge = edge_by_key.get(key)
        if edge is None or edge.station is None:
            return None
        station: Station | None = station_by_id.get(edge.station)
        if station is None or station.state.total_pressure is None:
            return None
        return station.state.total_pressure.value_si

    if not inlet_keys or not outlet_keys:
        return None
    inlet = pressure(inlet_keys[0])
    outlet = pressure(outlet_keys[0])
    if inlet is None or outlet is None or inlet <= 0 or outlet <= 0:
        return None
    ratio = inlet / outlet if extracting else outlet / inlet
    return ratio if ratio > 0 else None


def _topological_order(
    flow_nodes: tuple[str, ...], edges: tuple[GasPathEdge, ...]
) -> tuple[str, ...]:
    flow = set(flow_nodes)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in flow_nodes}
    indegree: dict[str, int] = dict.fromkeys(flow_nodes, 0)
    for edge in edges:
        if edge.from_node in flow and edge.to_node in flow:
            adjacency[edge.from_node].append(edge.to_node)
            indegree[edge.to_node] += 1
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for downstream in sorted(adjacency[node_id]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                ready.append(downstream)
                ready.sort()
    if len(order) != len(flow_nodes):
        raise CycleModelError("CYCLE_FLOW_GRAPH_IS_NOT_ACYCLIC")
    return tuple(order)


def _speed_rpm(shaft: Shaft) -> float | None:
    if shaft.speed is None or shaft.speed.kind != "speed":
        return None
    return shaft.speed.value.value_si * 60.0


def compile_cycle_model(design: CycleDesign) -> CycleModel:
    """Compile an architecture plus design into a solvable :class:`CycleModel`."""

    architecture = design.architecture
    rows_by_node: dict[str, list[BladeRow]] = {}
    for row in architecture.rows:
        rows_by_node.setdefault(row.node, []).append(row)

    flow_nodes = tuple(node.node_id for node in architecture.nodes if node.is_flow)
    if not flow_nodes:
        raise CycleModelError("ARCHITECTURE_HAS_NO_FLOW_NODES")

    edges_by_node_in: dict[str, list[GasPathEdge]] = {node_id: [] for node_id in flow_nodes}
    edges_by_node_out: dict[str, list[GasPathEdge]] = {node_id: [] for node_id in flow_nodes}
    seen_keys: set[str] = set()
    for edge in architecture.edges:
        key = edge_key(edge)
        if key in seen_keys:
            raise CycleModelError(f"EDGE_KEY_COLLISION:{key}")
        seen_keys.add(key)
        if edge.from_node in edges_by_node_out:
            edges_by_node_out[edge.from_node].append(edge)
        if edge.to_node in edges_by_node_in:
            edges_by_node_in[edge.to_node].append(edge)

    specs: list[CycleNodeSpec] = []
    for node in architecture.nodes:
        if not node.is_flow:
            continue
        rows = tuple(rows_by_node.get(node.node_id, ()))
        effective_kind = _resolve_kind(node.kind, rows)
        shaft_id = _shaft_for_node(node.node_id, rows)
        inlet_keys = tuple(
            sorted(edge_key(edge) for edge in edges_by_node_in[node.node_id])
        )
        outlet_keys = tuple(
            sorted(edge_key(edge) for edge in edges_by_node_out[node.node_id])
        )
        parameters = design.parameters_for(node.node_id)
        if effective_kind in NOZZLE_KINDS and parameters.ambient_pressure_pa is None:
            parameters = replace(
                parameters, ambient_pressure_pa=design.ambient_total_pressure_pa
            )
        declared = _declared_ratio(
            architecture,
            inlet_keys,
            outlet_keys,
            extracting=effective_kind in WORK_EXTRACTING_KINDS,
        )
        specs.append(
            CycleNodeSpec(
                node_id=node.node_id,
                kind=effective_kind,
                shaft_id=shaft_id,
                inlet_keys=inlet_keys,
                outlet_keys=outlet_keys,
                parameters=parameters,
                declared_ratio=declared,
            )
        )

    spec_by_id = {spec.node_id: spec for spec in specs}
    order = _topological_order(flow_nodes, architecture.edges)
    source_node_ids = tuple(
        sorted(node_id for node_id in flow_nodes if not spec_by_id[node_id].inlet_keys)
    )
    if not source_node_ids:
        raise CycleModelError("CYCLE_GRAPH_HAS_NO_SOURCE_NODE")

    shafts: list[CycleShaftSpec] = []
    for shaft in architecture.shafts:
        adding: list[str] = []
        extracting: list[str] = []
        members: list[str] = []
        for row in architecture.rows:
            if row.shaft != shaft.shaft_id:
                continue
            spec = spec_by_id.get(row.node)
            if spec is None:
                continue
            if spec.node_id not in members:
                members.append(spec.node_id)
            if spec.is_work_adding and spec.node_id not in adding:
                adding.append(spec.node_id)
            if spec.is_work_extracting and spec.node_id not in extracting:
                extracting.append(spec.node_id)
        shafts.append(
            CycleShaftSpec(
                shaft_id=shaft.shaft_id,
                kind=shaft.kind,
                speed_rpm=_speed_rpm(shaft),
                mechanical_loss_fraction=shaft.mechanical_loss_fraction,
                member_nodes=tuple(sorted(members)),
                work_adding_nodes=tuple(sorted(adding)),
                work_extracting_nodes=tuple(sorted(extracting)),
                couplings=shaft.couplings,
            )
        )

    model = CycleModel(
        architecture=architecture,
        design=design,
        nodes=tuple(sorted(specs, key=lambda spec: spec.node_id)),
        order=order,
        shafts=tuple(sorted(shafts, key=lambda shaft: shaft.shaft_id)),
        source_node_ids=source_node_ids,
        digest="",
    )
    digest = content_digest(model.canonical())
    return replace(model, digest=digest)


def map_coefficients(model: CycleModel) -> tuple[OperatingMap, ...]:
    """Every distinct map declared anywhere in the model, in deterministic order."""

    maps: list[OperatingMap] = []
    for node in model.nodes:
        component_map = node.parameters.component_map
        if component_map is not None and component_map not in maps:
            maps.append(component_map)
    return tuple(maps)


__all__ = [
    "CycleDesign",
    "CycleModel",
    "CycleNodeSpec",
    "CycleShaftSpec",
    "compile_cycle_model",
    "edge_key",
    "map_coefficients",
]
