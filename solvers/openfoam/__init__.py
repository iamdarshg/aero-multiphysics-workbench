"""OpenFOAM case preparation, mesh ingestion, and result validation boundary."""

from .adapter import OpenFoamCapability, OpenFoamCase, inspect_openfoam, prepare_case
from .case import (
    AmiPair,
    GovernedMesh,
    RotatingZone,
    parse_case_result,
    prepare_case_files,
    select_application,
    validate_case_result,
)
from .mesh_ingest import (
    MeshInterface,
    MeshPatch,
    MeshZone,
    ingest_governed_mesh,
    mapping_payload_hash,
)

__all__ = [
    "AmiPair",
    "GovernedMesh",
    "MeshInterface",
    "MeshPatch",
    "MeshZone",
    "OpenFoamCase",
    "OpenFoamCapability",
    "RotatingZone",
    "ingest_governed_mesh",
    "inspect_openfoam",
    "mapping_payload_hash",
    "parse_case_result",
    "prepare_case",
    "prepare_case_files",
    "select_application",
    "validate_case_result",
]
