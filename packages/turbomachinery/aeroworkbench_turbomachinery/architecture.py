"""Canonical rotating-gas-machine architecture: gas path, stations, rows, shafts.

One immutable, hashable model connects the directed gas-path graph, unit-bearing
stations, blade rows, and the shaft/spool graph. It is deliberately
application-agnostic: no fan, compressor, turbine, or vehicle concept is
mandatory, and the same contract represents an electrically driven ducted fan,
a multi-row axial compressor, a radial compressor plus diffuser, a
compressor-combustor-turbine core, a multi-spool bypass path, and a free-power
turbine.

The canonical serialization and hash are mirrored byte-for-byte by
``packages/schema/src/rotating_gas.ts``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .canonical import content_digest, normalize_numbers
from .components import FLOW_EDGE_KINDS, GasPathEdge, GasPathNode
from .rows import BladeClearance, BladeRow
from .shafts import Shaft, ShaftCoupling, SpeedBound
from .stations import AnnulusGeometryRef, Station, StationState, WorkingFluid
from .units import Quantity, si_unit_for_dimension

SCHEMA_VERSION = 1

ROLE_ALLOWED_NODE_KINDS: dict[str, tuple[str, ...]] = {
    "work_adding": ("rotor_row", "compressor_stage", "fan_stage"),
    "work_extracting": ("rotor_row", "turbine_stage", "expander_stage"),
    "turning_only": ("stator_row",),
    "diffuser_guide": ("stator_row", "diffuser"),
}


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"EXPECTED_OBJECT:{label}")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"EXPECTED_ARRAY:{label}")
    return cast(Sequence[Any], value)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"EXPECTED_NONEMPTY_STRING:{label}")
    return value


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"EXPECTED_STRING:{label}")
    return value


def _optional_number(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"EXPECTED_NUMBER:{label}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"NONFINITE_NUMBER:{label}")
    return number


def _integer(value: Any, label: str, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"EXPECTED_INTEGER:{label}")
    return cast(int, value)


def _quantity(value: Any, label: str) -> Quantity | None:
    if value is None:
        return None
    item = _mapping(value, label)
    if "unit" in item:
        number = _optional_number(item.get("value"), label)
        assert number is not None
        return Quantity(value=number, unit=_string(item["unit"], f"{label}.unit"))
    if "valueSI" in item:
        number = _optional_number(item.get("valueSI"), label)
        assert number is not None
        dimension = _string(item.get("dimension"), f"{label}.dimension")
        return Quantity(value=number, unit=si_unit_for_dimension(dimension))
    raise ValueError(f"QUANTITY_NEEDS_VALUE_AND_UNIT:{label}")


def _fluid(value: Any, label: str) -> WorkingFluid | None:
    if value is None:
        return None
    item = _mapping(value, label)
    raw_composition = item.get("composition") or {}
    composition_map = _mapping(raw_composition, f"{label}.composition")
    composition = tuple(
        (str(name), float(fraction)) for name, fraction in composition_map.items()
    )
    return WorkingFluid(
        identity=_string(item.get("identity"), f"{label}.identity"),
        composition=composition,
    )


def _annulus(value: Any, label: str) -> AnnulusGeometryRef | None:
    if value is None:
        return None
    item = _mapping(value, label)
    return AnnulusGeometryRef(
        area=_quantity(item.get("area"), f"{label}.area"),
        radius=_quantity(item.get("radius"), f"{label}.radius"),
        hub_radius=_quantity(item.get("hubRadius"), f"{label}.hubRadius"),
        tip_radius=_quantity(item.get("tipRadius"), f"{label}.tipRadius"),
        geometry_ref=_optional_string(item.get("geometryRef"), f"{label}.geometryRef"),
    )


def _state(value: Any, label: str) -> StationState:
    item = _mapping(value, label)
    return StationState(
        mass_flow=_quantity(item.get("massFlow"), f"{label}.massFlow"),
        total_pressure=_quantity(item.get("totalPressure"), f"{label}.totalPressure"),
        static_pressure=_quantity(item.get("staticPressure"), f"{label}.staticPressure"),
        total_temperature=_quantity(item.get("totalTemperature"), f"{label}.totalTemperature"),
        static_temperature=_quantity(
            item.get("staticTemperature"), f"{label}.staticTemperature"
        ),
        density=_quantity(item.get("density"), f"{label}.density"),
        velocity=_quantity(item.get("velocity"), f"{label}.velocity"),
        mach=_quantity(item.get("mach"), f"{label}.mach"),
        tangential_velocity=_quantity(
            item.get("tangentialVelocity"), f"{label}.tangentialVelocity"
        ),
        swirl_angle=_quantity(item.get("swirlAngle"), f"{label}.swirlAngle"),
        fluid=_fluid(item.get("fluid"), f"{label}.fluid"),
        annulus=_annulus(item.get("annulus"), f"{label}.annulus"),
    )


def _station(value: Any, label: str) -> Station:
    item = _mapping(value, label)
    return Station(
        station_id=_string(item.get("id"), f"{label}.id"),
        name=_optional_string(item.get("name"), f"{label}.name"),
        state=_state(item.get("state") or {}, f"{label}.state"),
    )


def _node(value: Any, label: str) -> GasPathNode:
    item = _mapping(value, label)
    return GasPathNode(
        node_id=_string(item.get("id"), f"{label}.id"),
        kind=_string(item.get("kind"), f"{label}.kind"),
        label=_optional_string(item.get("label"), f"{label}.label"),
    )


def _edge(value: Any, label: str) -> GasPathEdge:
    item = _mapping(value, label)
    return GasPathEdge(
        from_node=_string(item.get("from"), f"{label}.from"),
        to_node=_string(item.get("to"), f"{label}.to"),
        kind=_string(item.get("kind"), f"{label}.kind"),
        station=_optional_string(item.get("station"), f"{label}.station"),
    )


def _clearance(value: Any, label: str) -> BladeClearance:
    if value is None:
        return BladeClearance()
    item = _mapping(value, label)
    return BladeClearance(
        tip_clearance=_quantity(item.get("tipClearance"), f"{label}.tipClearance"),
        endwall_state=_optional_string(item.get("endwallState"), f"{label}.endwallState"),
        shroud_state=_optional_string(item.get("shroudState"), f"{label}.shroudState"),
    )


def _row(value: Any, label: str) -> BladeRow:
    item = _mapping(value, label)
    return BladeRow(
        row_id=_string(item.get("id"), f"{label}.id"),
        node=_string(item.get("node"), f"{label}.node"),
        role=_string(item.get("role"), f"{label}.role"),
        frame=_string(item.get("frame"), f"{label}.frame"),
        shaft=_optional_string(item.get("shaft"), f"{label}.shaft"),
        station_in=_string(item.get("stationIn"), f"{label}.stationIn"),
        station_out=_string(item.get("stationOut"), f"{label}.stationOut"),
        row_count=_integer(item.get("rowCount"), f"{label}.rowCount", 1),
        periodicity=_integer(item.get("periodicity"), f"{label}.periodicity", 1),
        family=str(item.get("family", "axial")),
        geometry_ref=_optional_string(item.get("geometryRef"), f"{label}.geometryRef"),
        clearance=_clearance(item.get("clearance"), f"{label}.clearance"),
        material_ref=_optional_string(item.get("materialRef"), f"{label}.materialRef"),
        thermal_ref=_optional_string(item.get("thermalRef"), f"{label}.thermalRef"),
    )


def _speed(value: Any, label: str) -> SpeedBound | None:
    if value is None:
        return None
    item = _mapping(value, label)
    quantity = _quantity(item.get("value"), f"{label}.value")
    if quantity is None:
        raise ValueError(f"SPEED_BOUND_NEEDS_VALUE:{label}")
    return SpeedBound(kind=_string(item.get("kind"), f"{label}.kind"), value=quantity)


def _coupling(value: Any, label: str) -> ShaftCoupling:
    item = _mapping(value, label)
    return ShaftCoupling(
        coupling_id=_string(item.get("id"), f"{label}.id"),
        kind=_string(item.get("kind"), f"{label}.kind"),
        target_shaft=_optional_string(item.get("targetShaft"), f"{label}.targetShaft"),
        target_node=_optional_string(item.get("targetNode"), f"{label}.targetNode"),
        ratio=_optional_number(item.get("ratio"), f"{label}.ratio"),
        efficiency=_optional_number(item.get("efficiency"), f"{label}.efficiency"),
    )


def _shaft(value: Any, label: str) -> Shaft:
    item = _mapping(value, label)
    members = tuple(
        _string(member, f"{label}.members[]")
        for member in _sequence(item.get("members") or [], f"{label}.members")
    )
    couplings = tuple(
        _coupling(coupling, f"{label}.couplings[{index}]")
        for index, coupling in enumerate(
            _sequence(item.get("couplings") or [], f"{label}.couplings")
        )
    )
    return Shaft(
        shaft_id=_string(item.get("id"), f"{label}.id"),
        kind=_string(item.get("kind"), f"{label}.kind"),
        members=members,
        speed=_speed(item.get("speed"), f"{label}.speed"),
        mechanical_loss_fraction=_optional_number(
            item.get("mechanicalLossFraction"), f"{label}.mechanicalLossFraction"
        )
        or 0.0,
        couplings=couplings,
    )


@dataclass(frozen=True, slots=True)
class RotatingGasArchitecture:
    """Immutable canonical rotating gas-path architecture."""

    architecture_id: str
    nodes: tuple[GasPathNode, ...]
    edges: tuple[GasPathEdge, ...]
    stations: tuple[Station, ...]
    rows: tuple[BladeRow, ...]
    shafts: tuple[Shaft, ...]
    default_fluid: WorkingFluid | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"SCHEMA_VERSION_UNSUPPORTED:{self.schema_version}")
        if not self.architecture_id.strip():
            raise ValueError("ARCHITECTURE_ID_REQUIRED")
        if not self.nodes:
            raise ValueError("NODES_REQUIRED")
        self._validate_unique()
        self._validate_references()
        self._validate_flow_graph()

    def _validate_unique(self) -> None:
        for label, identifiers in (
            ("NODE", [node.node_id for node in self.nodes]),
            ("STATION", [station.station_id for station in self.stations]),
            ("ROW", [row.row_id for row in self.rows]),
            ("SHAFT", [shaft.shaft_id for shaft in self.shafts]),
        ):
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"DUPLICATE_{label}")
        edge_keys = [
            (edge.from_node, edge.to_node, edge.kind, edge.station) for edge in self.edges
        ]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("DUPLICATE_EDGE")

    def _validate_references(self) -> None:
        node_by_id = {node.node_id: node for node in self.nodes}
        station_ids = {station.station_id for station in self.stations}
        shaft_by_id = {shaft.shaft_id: shaft for shaft in self.shafts}
        for edge in self.edges:
            for endpoint in (edge.from_node, edge.to_node):
                if endpoint not in node_by_id:
                    raise ValueError(f"EDGE_ENDPOINT_UNKNOWN:{endpoint}")
            if edge.station is not None and edge.station not in station_ids:
                raise ValueError(f"EDGE_STATION_UNKNOWN:{edge.station}")
        row_shaft_binding: dict[str, str] = {}
        for row in self.rows:
            node = node_by_id.get(row.node)
            if node is None:
                raise ValueError(f"ROW_NODE_UNKNOWN:{row.row_id}")
            allowed = ROLE_ALLOWED_NODE_KINDS[row.role]
            if node.kind not in allowed:
                raise ValueError(f"ROW_ROLE_NODE_MISMATCH:{row.row_id}:{node.kind}")
            for station_id in (row.station_in, row.station_out):
                if station_id not in station_ids:
                    raise ValueError(f"ROW_STATION_UNKNOWN:{row.row_id}:{station_id}")
            if row.shaft is not None:
                if row.shaft not in shaft_by_id:
                    raise ValueError(f"ROW_SHAFT_UNKNOWN:{row.row_id}:{row.shaft}")
                if row.row_id in row_shaft_binding:
                    raise ValueError(f"ROW_BOUND_TO_MULTIPLE_SHAFTS:{row.row_id}")
                row_shaft_binding[row.row_id] = row.shaft
        for shaft in self.shafts:
            for member in shaft.members:
                if member not in row_shaft_binding:
                    raise ValueError(f"SHAFT_MEMBER_UNKNOWN:{shaft.shaft_id}:{member}")
                if row_shaft_binding[member] != shaft.shaft_id:
                    raise ValueError(f"SHAFT_MEMBER_BOUND_ELSEWHERE:{shaft.shaft_id}:{member}")
            for coupling in shaft.couplings:
                if coupling.target_shaft is not None:
                    if coupling.target_shaft not in shaft_by_id:
                        raise ValueError(
                            f"COUPLING_TARGET_SHAFT_UNKNOWN:{shaft.shaft_id}:{coupling.coupling_id}"
                        )
                    if coupling.target_shaft == shaft.shaft_id:
                        raise ValueError(
                            f"COUPLING_SELF_REFERENCE:{shaft.shaft_id}:{coupling.coupling_id}"
                        )
                if coupling.target_node is not None:
                    target = node_by_id.get(coupling.target_node)
                    if target is None:
                        raise ValueError(
                            f"COUPLING_TARGET_NODE_UNKNOWN:{shaft.shaft_id}:{coupling.coupling_id}"
                        )
                    expected = coupling.expected_target_node_kind
                    if expected is not None and target.kind != expected:
                        raise ValueError(
                            f"COUPLING_TARGET_NODE_KIND:{coupling.coupling_id}:{target.kind}"
                        )

    def _validate_flow_graph(self) -> None:
        flow_nodes = {node.node_id for node in self.nodes if node.is_flow}
        edges = [edge for edge in self.edges if edge.kind in FLOW_EDGE_KINDS]
        for edge in edges:
            if edge.from_node not in flow_nodes or edge.to_node not in flow_nodes:
                raise ValueError(f"FLOW_EDGE_NEEDS_FLOW_NODES:{edge.from_node}->{edge.to_node}")
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in flow_nodes}
        undirected: dict[str, set[str]] = {node_id: set() for node_id in flow_nodes}
        for edge in edges:
            adjacency[edge.from_node].append(edge.to_node)
            undirected[edge.from_node].add(edge.to_node)
            undirected[edge.to_node].add(edge.from_node)
        state: dict[str, str] = {}

        def visit(node_id: str) -> None:
            current = state.get(node_id)
            if current == "done":
                return
            if current == "visiting":
                raise ValueError(f"FLOW_CYCLE:{node_id}")
            state[node_id] = "visiting"
            for downstream in adjacency[node_id]:
                visit(downstream)
            state[node_id] = "done"

        for node_id in flow_nodes:
            visit(node_id)
        if flow_nodes:
            start = min(flow_nodes)
            seen = {start}
            frontier = [start]
            while frontier:
                current = frontier.pop()
                for neighbour in undirected[current]:
                    if neighbour not in seen:
                        seen.add(neighbour)
                        frontier.append(neighbour)
            if seen != flow_nodes:
                raise ValueError("FLOW_GRAPH_DISCONNECTED")

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": self.schema_version,
            "architectureId": self.architecture_id,
            "defaultFluid": None if self.default_fluid is None else self.default_fluid.canonical(),
            "nodes": [node.canonical() for node in sorted(self.nodes, key=lambda n: n.node_id)],
            "edges": [
                edge.canonical()
                for edge in sorted(
                    self.edges,
                    key=lambda e: (e.from_node, e.to_node, e.kind, e.station or ""),
                )
            ],
            "stations": [
                station.canonical() for station in sorted(self.stations, key=lambda s: s.station_id)
            ],
            "rows": [row.canonical() for row in sorted(self.rows, key=lambda r: r.row_id)],
            "shafts": [
                shaft.canonical()
                for shaft in sorted(self.shafts, key=lambda s: s.shaft_id)
            ],
        }
        return cast(dict[str, object], normalize_numbers(payload))

    def topology_payload(self) -> dict[str, object]:
        """Structural view of the architecture used for design-space invalidation."""
        payload: dict[str, object] = {
            "schemaVersion": self.schema_version,
            "nodes": [
                {"id": node.node_id, "kind": node.kind}
                for node in sorted(self.nodes, key=lambda n: n.node_id)
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "kind": edge.kind,
                    "station": edge.station,
                }
                for edge in sorted(
                    self.edges,
                    key=lambda e: (e.from_node, e.to_node, e.kind, e.station or ""),
                )
            ],
            "stations": [
                station.station_id
                for station in sorted(self.stations, key=lambda s: s.station_id)
            ],
            "rows": [
                {
                    "id": row.row_id,
                    "node": row.node,
                    "role": row.role,
                    "frame": row.frame,
                    "shaft": row.shaft,
                    "stationIn": row.station_in,
                    "stationOut": row.station_out,
                    "rowCount": row.row_count,
                    "periodicity": row.periodicity,
                    "family": row.family,
                    "geometryRef": row.geometry_ref,
                    "materialRef": row.material_ref,
                    "thermalRef": row.thermal_ref,
                }
                for row in sorted(self.rows, key=lambda r: r.row_id)
            ],
            "shafts": [
                {
                    "id": shaft.shaft_id,
                    "kind": shaft.kind,
                    "members": sorted(shaft.members),
                    "speedKind": None if shaft.speed is None else shaft.speed.kind,
                    "couplings": [
                        {
                            "id": coupling.coupling_id,
                            "kind": coupling.kind,
                            "targetShaft": coupling.target_shaft,
                            "targetNode": coupling.target_node,
                        }
                        for coupling in sorted(shaft.couplings, key=lambda c: c.coupling_id)
                    ],
                }
                for shaft in sorted(self.shafts, key=lambda s: s.shaft_id)
            ],
        }
        return cast(dict[str, object], normalize_numbers(payload))

    @property
    def topology_digest(self) -> str:
        return content_digest(self.topology_payload())

    @property
    def architecture_hash(self) -> str:
        return content_digest(self.canonical_payload())


def architecture_from_payload(payload: Mapping[str, Any]) -> RotatingGasArchitecture:
    """Build and validate an architecture from its canonical JSON document."""
    document = _mapping(payload, "architecture")
    version = document.get("schemaVersion")
    if version is not None and not isinstance(version, bool) and isinstance(version, int):
        schema_version = version
    else:
        schema_version = SCHEMA_VERSION
    nodes = tuple(
        _node(item, f"nodes[{index}]")
        for index, item in enumerate(_sequence(document.get("nodes") or [], "nodes"))
    )
    edges = tuple(
        _edge(item, f"edges[{index}]")
        for index, item in enumerate(_sequence(document.get("edges") or [], "edges"))
    )
    stations = tuple(
        _station(item, f"stations[{index}]")
        for index, item in enumerate(_sequence(document.get("stations") or [], "stations"))
    )
    rows = tuple(
        _row(item, f"rows[{index}]")
        for index, item in enumerate(_sequence(document.get("rows") or [], "rows"))
    )
    shafts = tuple(
        _shaft(item, f"shafts[{index}]")
        for index, item in enumerate(_sequence(document.get("shafts") or [], "shafts"))
    )
    return RotatingGasArchitecture(
        architecture_id=_string(document.get("architectureId"), "architectureId"),
        nodes=nodes,
        edges=edges,
        stations=stations,
        rows=rows,
        shafts=shafts,
        default_fluid=_fluid(document.get("defaultFluid"), "defaultFluid"),
        schema_version=schema_version,
    )


def _as_architecture(value: RotatingGasArchitecture | Mapping[str, Any]) -> RotatingGasArchitecture:
    if isinstance(value, RotatingGasArchitecture):
        return value
    return architecture_from_payload(value)


def canonical_architecture(
    value: RotatingGasArchitecture | Mapping[str, Any],
) -> dict[str, object]:
    """Canonical, deterministic payload for an architecture (or its raw JSON)."""
    return _as_architecture(value).canonical_payload()


def architecture_hash(value: RotatingGasArchitecture | Mapping[str, Any]) -> str:
    """Deterministic SHA-256 content hash of the full architecture."""
    return content_digest(canonical_architecture(value))


def topology_digest(value: RotatingGasArchitecture | Mapping[str, Any]) -> str:
    """Deterministic digest of the structural topology only."""
    return _as_architecture(value).topology_digest


def _graph_signature(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    nodes = tuple(sorted((node.node_id, node.kind) for node in architecture.nodes))
    edges = tuple(
        sorted(
            (edge.from_node, edge.to_node, edge.kind, edge.station or "")
            for edge in architecture.edges
        )
    )
    return (nodes, edges)


def _station_ids(architecture: RotatingGasArchitecture) -> tuple[str, ...]:
    return tuple(sorted(station.station_id for station in architecture.stations))


def _row_structure(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (
                row.row_id,
                row.node,
                row.role,
                row.frame,
                row.shaft or "",
                row.station_in,
                row.station_out,
                row.family,
            )
            for row in architecture.rows
        )
    )


def _station_values(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (station.station_id, _freeze(station.state.canonical()))
            for station in architecture.stations
        )
    )


def _geometry_signature(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    rows = tuple(
        sorted(
            (row.row_id, row.row_count, row.periodicity, row.geometry_ref or "")
            for row in architecture.rows
        )
    )
    annuli = tuple(
        sorted(
            (station.station_id, _freeze(station.state.annulus.canonical()))
            for station in architecture.stations
            if station.state.annulus is not None
        )
    )
    return (rows, annuli)


def _motion_signature(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    rows = tuple(sorted((row.row_id, row.frame, row.shaft or "") for row in architecture.rows))
    shafts = tuple(
        sorted(
            (shaft.shaft_id, shaft.kind, tuple(sorted(shaft.members)))
            for shaft in architecture.shafts
        )
    )
    return (rows, shafts)


def _material_signature(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (row.row_id, row.material_ref or "", row.thermal_ref or "")
            for row in architecture.rows
        )
    )


def _parametric_signature(architecture: RotatingGasArchitecture) -> tuple[Any, ...]:
    rows = tuple(
        sorted(
            (
                row.row_id,
                _freeze(row.clearance.canonical()),
            )
            for row in architecture.rows
        )
    )
    shafts = tuple(
        sorted(
            (
                shaft.shaft_id,
                shaft.mechanical_loss_fraction,
                _freeze(None if shaft.speed is None else shaft.speed.canonical()),
                tuple(
                    sorted(
                        (coupling.coupling_id, coupling.ratio, coupling.efficiency)
                        for coupling in shaft.couplings
                    )
                ),
            )
            for shaft in architecture.shafts
        )
    )
    return (rows, shafts)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def topology_change_sections(
    before: RotatingGasArchitecture | Mapping[str, Any],
    after: RotatingGasArchitecture | Mapping[str, Any],
) -> tuple[str, ...]:
    """Classify an architecture delta into existing design-section vocabulary.

    The returned section names are the keys consumed by the existing
    ``CHANGE_IMPACT`` invalidation tables (``packages/schema/src/design.ts`` and
    ``packages/coupling/aeroworkbench_coupling/dag.py``); callers pass them to
    ``invalidated_nodes`` / ``invalidated_families`` to invalidate geometry, mesh,
    analysis, interfaces, operating points, and optimization descendants.
    """
    previous = _as_architecture(before)
    current = _as_architecture(after)
    sections: set[str] = set()
    if _graph_signature(previous) != _graph_signature(current):
        sections.add("topologyDigest")
    if _station_ids(previous) != _station_ids(current):
        sections.add("topologyDigest")
    if _row_structure(previous) != _row_structure(current):
        sections.add("topologyDigest")
    if _geometry_signature(previous) != _geometry_signature(current):
        sections.add("geometry")
    if _motion_signature(previous) != _motion_signature(current):
        sections.add("motionFrames")
    if _material_signature(previous) != _material_signature(current):
        sections.add("materials")
    if _station_values(previous) != _station_values(current):
        sections.add("operatingPoints")
    if _parametric_signature(previous) != _parametric_signature(current):
        sections.add("parameters")
    return tuple(sorted(sections))


def architecture_provenance(
    value: RotatingGasArchitecture | Mapping[str, Any],
) -> Provenance:
    """Schema identity/provenance for any downstream result derived from the model.

    The architecture is a declaration, not a computed result; no solver output is
    fabricated. The returned provenance records the analytical/schema source, the
    model version, and the input hash so downstream results can cite it.
    """
    architecture = _as_architecture(value)
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="rotating-gas-architecture",
        model_version=str(architecture.schema_version),
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=architecture.canonical_payload(),
        assumptions=(
            "Canonical topology/station/row/shaft schema only; no solver execution.",
        ),
    )
