"""Physics-derived architecture features used to select applicable fidelity rungs.

Features are derived from the canonical gas-path graph (node kinds, row
frames/roles, shaft kinds, coupling kinds), never from a product or machine
name. Downstream ladder applicability, dependency graph selection, and
promotion policy all use the same feature document.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..architecture import RotatingGasArchitecture, architecture_from_payload
from ..canonical import content_digest

__all__ = ["ArchitectureFeatures", "architecture_features"]

_HEAT_NODE_KINDS = frozenset(
    {"combustor", "heat_addition", "heat_exchanger", "recuperator", "intercooler"}
)
_COMBUSTION_NODE_KINDS = frozenset({"combustor", "heat_addition"})
_SPLITTER_NODE_KINDS = frozenset(
    {"bypass_split", "core_split", "splitter", "bypass_merge", "core_merge", "mixer"}
)


@dataclass(frozen=True, slots=True)
class ArchitectureFeatures:
    """Deterministic, hashable physics descriptor for one architecture."""

    has_flow: bool
    has_rotating_rows: bool
    is_work_adding: bool
    is_work_extracting: bool
    is_electrically_driven: bool
    has_generator: bool
    has_mechanical_load: bool
    is_free_power: bool
    has_heat_addition: bool
    has_combustion: bool
    has_splitting: bool
    acoustics_requested: bool = False

    def canonical(self) -> dict[str, Any]:
        return {
            "hasFlow": self.has_flow,
            "hasRotatingRows": self.has_rotating_rows,
            "isWorkAdding": self.is_work_adding,
            "isWorkExtracting": self.is_work_extracting,
            "isElectricallyDriven": self.is_electrically_driven,
            "hasGenerator": self.has_generator,
            "hasMechanicalLoad": self.has_mechanical_load,
            "isFreePower": self.is_free_power,
            "hasHeatAddition": self.has_heat_addition,
            "hasCombustion": self.has_combustion,
            "hasSplitting": self.has_splitting,
            "acousticsRequested": self.acoustics_requested,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def _architecture(value: RotatingGasArchitecture | Mapping[str, Any]) -> RotatingGasArchitecture:
    if isinstance(value, RotatingGasArchitecture):
        return value
    return architecture_from_payload(value)


def architecture_features(
    value: RotatingGasArchitecture | Mapping[str, Any],
    *,
    acoustics_requested: bool = False,
) -> ArchitectureFeatures:
    """Derive features from the graph; the same architecture always maps to one."""
    architecture = _architecture(value)
    node_kinds = {node.kind for node in architecture.nodes}
    coupling_kinds = {
        coupling.kind for shaft in architecture.shafts for coupling in shaft.couplings
    }
    return ArchitectureFeatures(
        has_flow=any(node.is_flow for node in architecture.nodes),
        has_rotating_rows=any(row.frame == "rotating" for row in architecture.rows),
        is_work_adding=any(row.role == "work_adding" for row in architecture.rows),
        is_work_extracting=any(row.role == "work_extracting" for row in architecture.rows),
        is_electrically_driven=(
            "electric_motor" in coupling_kinds or "motor_coupling" in node_kinds
        ),
        has_generator=(
            "electric_generator" in coupling_kinds or "generator_coupling" in node_kinds
        ),
        has_mechanical_load=(
            "mechanical_load" in coupling_kinds or "mechanical_load" in node_kinds
        ),
        is_free_power=any(shaft.kind == "free_power" for shaft in architecture.shafts),
        has_heat_addition=bool(node_kinds & _HEAT_NODE_KINDS),
        has_combustion=bool(node_kinds & _COMBUSTION_NODE_KINDS),
        has_splitting=bool(node_kinds & _SPLITTER_NODE_KINDS),
        acoustics_requested=acoustics_requested,
    )
