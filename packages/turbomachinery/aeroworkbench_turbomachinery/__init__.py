"""Canonical rotating-gas-machine architecture: gas path, stations, rows, shafts.

Public API (later issues import these exact paths):

    from aeroworkbench_turbomachinery import (
        RotatingGasArchitecture,
        architecture_from_payload,
        architecture_hash,
        architecture_provenance,
        canonical_architecture,
        topology_change_sections,
        topology_digest,
    )
"""

from .architecture import (
    ROLE_ALLOWED_NODE_KINDS,
    SCHEMA_VERSION,
    RotatingGasArchitecture,
    architecture_from_payload,
    architecture_hash,
    architecture_provenance,
    canonical_architecture,
    topology_change_sections,
    topology_digest,
)
from .canonical import canonical_json, content_digest, normalize_numbers
from .components import (
    COUPLING_EDGE_KINDS,
    EDGE_KINDS,
    ELECTRICAL_NODE_KINDS,
    FLOW_EDGE_KINDS,
    FLOW_NODE_KINDS,
    MECHANICAL_NODE_KINDS,
    NODE_KINDS,
    GasPathEdge,
    GasPathNode,
)
from .rows import FLOW_FAMILIES, ROW_FRAMES, ROW_ROLES, BladeClearance, BladeRow
from .shafts import (
    COUPLING_KINDS,
    SHAFT_KINDS,
    Shaft,
    ShaftCoupling,
    SpeedBound,
)
from .stations import AnnulusGeometryRef, Station, StationState, WorkingFluid
from .units import Quantity, dimension_of, require_dimension, to_si

__all__ = [
    "SCHEMA_VERSION",
    "ROLE_ALLOWED_NODE_KINDS",
    "RotatingGasArchitecture",
    "architecture_from_payload",
    "architecture_hash",
    "architecture_provenance",
    "canonical_architecture",
    "topology_change_sections",
    "topology_digest",
    "canonical_json",
    "content_digest",
    "normalize_numbers",
    "GasPathNode",
    "GasPathEdge",
    "NODE_KINDS",
    "FLOW_NODE_KINDS",
    "MECHANICAL_NODE_KINDS",
    "ELECTRICAL_NODE_KINDS",
    "FLOW_EDGE_KINDS",
    "COUPLING_EDGE_KINDS",
    "EDGE_KINDS",
    "BladeRow",
    "BladeClearance",
    "ROW_ROLES",
    "ROW_FRAMES",
    "FLOW_FAMILIES",
    "Shaft",
    "ShaftCoupling",
    "SpeedBound",
    "SHAFT_KINDS",
    "COUPLING_KINDS",
    "Station",
    "StationState",
    "WorkingFluid",
    "AnnulusGeometryRef",
    "Quantity",
    "dimension_of",
    "require_dimension",
    "to_si",
]
