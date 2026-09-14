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
from .parameters import ParameterDef, ParameterSet, parameter_digest
from .parametric import (
    BuiltModel,
    ComponentTopology,
    Frame,
    KernelIdentity,
    ParametricModel,
    built_model_digest,
    export_artifacts,
    probe_kernel,
    require_kernel,
)

__all__ = [
    "GeometryModel",
    "Surface",
    "make_edf_geometry",
    "shape_hash",
    "ParameterDef",
    "ParameterSet",
    "parameter_digest",
    "ParametricModel",
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
    "build_duct_system",
    "fluid_zone_names",
    "rotating_zone_names",
    "solid_names",
    "stationary_zone_names",
]
