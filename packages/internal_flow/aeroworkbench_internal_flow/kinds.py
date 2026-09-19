"""Typed node and branch kinds for generic internal-flow networks.

The vocabulary is deliberately product-neutral: a turbomachinery cooling
circuit, an aircraft bleed/anti-ice duct, an electronics cold plate loop, or a
bearing-oil gallery all map onto the same typed contracts.
"""

from __future__ import annotations

from enum import StrEnum


class NodeKind(StrEnum):
    """A control volume or boundary of the fluid network."""

    PLENUM = "plenum"
    JUNCTION = "junction"
    CAVITY = "cavity"
    SOURCE = "source"
    SINK = "sink"
    BLEED_EXTRACTION = "bleed_extraction"
    BLEED_INJECTION = "bleed_injection"
    AMBIENT = "ambient"


class BranchKind(StrEnum):
    """A loss or work element connecting two nodes."""

    DUCT = "duct"
    PIPE = "pipe"
    ORIFICE = "orifice"
    VALVE = "valve"
    SEAL = "seal"
    HEAT_EXCHANGER = "heat_exchanger"
    PUMP = "pump"
    FAN = "fan"
    COMPRESSOR = "compressor"


BOUNDARY_NODE_KINDS: frozenset[NodeKind] = frozenset(
    {
        NodeKind.SOURCE,
        NodeKind.SINK,
        NodeKind.BLEED_EXTRACTION,
        NodeKind.BLEED_INJECTION,
        NodeKind.AMBIENT,
    }
)

INTERNAL_NODE_KINDS: frozenset[NodeKind] = frozenset(
    {NodeKind.PLENUM, NodeKind.JUNCTION, NodeKind.CAVITY}
)

LEAKAGE_BRANCH_KINDS: frozenset[BranchKind] = frozenset({BranchKind.SEAL})
WORK_BRANCH_KINDS: frozenset[BranchKind] = frozenset(
    {BranchKind.PUMP, BranchKind.FAN, BranchKind.COMPRESSOR}
)
THERMAL_BRANCH_KINDS: frozenset[BranchKind] = frozenset({BranchKind.HEAT_EXCHANGER})
