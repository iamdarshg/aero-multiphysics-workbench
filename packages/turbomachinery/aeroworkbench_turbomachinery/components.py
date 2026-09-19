"""Typed gas-path graph nodes and edges for rotating machinery.

The graph is generic: nothing is mandatory except the nodes and edges an
architecture actually declares. Flow nodes form the aerodynamic gas path;
mechanical and electrical nodes attach shafts, loads, motors, and generators.
"""

from __future__ import annotations

from dataclasses import dataclass

FLOW_NODE_KINDS: tuple[str, ...] = (
    "ambient",
    "inlet",
    "intake",
    "duct",
    "plenum",
    "mixer",
    "splitter",
    "rotor_row",
    "stator_row",
    "diffuser",
    "compressor_stage",
    "fan_stage",
    "turbine_stage",
    "expander_stage",
    "combustor",
    "heat_addition",
    "heat_exchanger",
    "recuperator",
    "intercooler",
    "nozzle",
    "exhaust",
    "bleed_extract",
    "cooling_inject",
    "bypass_split",
    "core_split",
    "bypass_merge",
    "core_merge",
)

MECHANICAL_NODE_KINDS: tuple[str, ...] = (
    "shaft_spool",
    "mechanical_load",
)

ELECTRICAL_NODE_KINDS: tuple[str, ...] = (
    "motor_coupling",
    "generator_coupling",
)

NODE_KINDS: tuple[str, ...] = (
    *FLOW_NODE_KINDS,
    *MECHANICAL_NODE_KINDS,
    *ELECTRICAL_NODE_KINDS,
)

FLOW_EDGE_KINDS: tuple[str, ...] = ("flow", "bleed", "cooling", "bypass", "core")

COUPLING_EDGE_KINDS: tuple[str, ...] = ("mechanical", "electrical")

EDGE_KINDS: tuple[str, ...] = (*FLOW_EDGE_KINDS, *COUPLING_EDGE_KINDS)


@dataclass(frozen=True, slots=True)
class GasPathNode:
    """One typed node in the gas-path graph."""

    node_id: str
    kind: str
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("NODE_ID_REQUIRED")
        if self.kind not in NODE_KINDS:
            raise ValueError(f"UNKNOWN_NODE_KIND:{self.kind}")

    @property
    def is_flow(self) -> bool:
        return self.kind in FLOW_NODE_KINDS

    def canonical(self) -> dict[str, object]:
        return {"id": self.node_id, "kind": self.kind, "label": self.label}


@dataclass(frozen=True, slots=True)
class GasPathEdge:
    """One directed typed edge between two graph nodes."""

    from_node: str
    to_node: str
    kind: str
    station: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EDGE_KINDS:
            raise ValueError(f"UNKNOWN_EDGE_KIND:{self.kind}")
        if not self.from_node.strip() or not self.to_node.strip():
            raise ValueError("EDGE_ENDPOINT_REQUIRED")
        if self.from_node == self.to_node:
            raise ValueError(f"SELF_EDGE:{self.from_node}")

    def canonical(self) -> dict[str, object]:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "kind": self.kind,
            "station": self.station,
        }
