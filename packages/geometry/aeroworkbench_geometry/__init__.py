"""Deterministic geometry contracts for the engineering workbench."""

from .builder import execute, live_shapes
from .canonical import GeometryModel, Surface, make_edf_geometry, shape_hash
from .duct_system import (
    build_duct_system,
    fluid_zone_names,
    rotating_zone_names,
    solid_names,
    stationary_zone_names,
)
from .parameters import (
    ParameterDef,
    ParameterSet,
    parameter_digest,
    resolved_parameter_digest,
)
from .parametric import (
    BuiltModel,
    ComponentTopology,
    Frame,
    KernelIdentity,
    ParameterRef,
    ParametricModel,
    built_model_digest,
    export_artifacts,
    geometry_definition_digest,
    param,
    probe_kernel,
    require_kernel,
)
from .regeneration import (
    ArtifactReference,
    GeometryReceipt,
    GeometryRegenerationRequest,
    GeometryRegenerator,
    SemanticBinding,
    geometry_receipt_digest,
    regenerate,
)

__all__ = [
    "GeometryModel",
    "Surface",
    "make_edf_geometry",
    "shape_hash",
    "ParameterDef",
    "ParameterSet",
    "parameter_digest",
    "resolved_parameter_digest",
    "ParametricModel",
    "ParameterRef",
    "param",
    "geometry_definition_digest",
    "BuiltModel",
    "ComponentTopology",
    "Frame",
    "KernelIdentity",
    "probe_kernel",
    "require_kernel",
    "built_model_digest",
    "export_artifacts",
    "execute",
    "live_shapes",
    "ArtifactReference",
    "GeometryReceipt",
    "GeometryRegenerationRequest",
    "GeometryRegenerator",
    "SemanticBinding",
    "geometry_receipt_digest",
    "regenerate",
    "build_duct_system",
    "fluid_zone_names",
    "rotating_zone_names",
    "solid_names",
    "stationary_zone_names",
]
