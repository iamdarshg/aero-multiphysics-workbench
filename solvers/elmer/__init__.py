"""Elmer capability boundary and native thermal participant entry points."""

from .adapter import ElmerCapability, inspect_elmer
from .case import (
    ThermalCase,
    build_thermal_case,
    load_elmer_mesh,
    prepare_native_thermal,
    render_thermal_sif,
)
from .fields import (
    FieldArtifact,
    FieldEntry,
    build_field_artifact,
    interface_hash,
    read_field_artifact,
    write_field_artifact,
)
from .materials import ElmerMaterial, map_material, map_materials
from .parser import (
    parse_elmer_output,
    publish_case_fields,
    validate_elmer_result,
)
from .sif import parse_sif_result, prepare_sif, validate_sif_result

__all__ = [
    "ElmerCapability",
    "ElmerMaterial",
    "FieldArtifact",
    "FieldEntry",
    "ThermalCase",
    "build_field_artifact",
    "build_thermal_case",
    "inspect_elmer",
    "interface_hash",
    "load_elmer_mesh",
    "map_material",
    "map_materials",
    "parse_elmer_output",
    "parse_sif_result",
    "prepare_native_thermal",
    "prepare_sif",
    "publish_case_fields",
    "read_field_artifact",
    "render_thermal_sif",
    "validate_elmer_result",
    "validate_sif_result",
    "write_field_artifact",
]
