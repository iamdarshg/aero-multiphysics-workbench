"""Reusable real 3-D turbomachinery geometry primitives.

The generic layer owns primitives only; product/domain examples supply
parameters and compose these contracts. Import the public names directly::

    from aeroworkbench_turbomachinery.geometry import BladeSection, ...
"""

from .blade_rows import (
    BladeRowGeometry,
    blade_row_parameter_defs,
    build_axial_blade_row,
    scaled_sections,
)
from .body import GeometryBody, SurfacePatch, body_digest
from .cad import (
    CadSolidReceipt,
    annular_revolve,
    blade_shape,
    export_shapes,
    fluid_sector_shape,
    probe_cad,
    radial_blade_shape,
    radial_fluid_sector_shape,
    row_shapes,
    solid_receipt,
)
from .fluid import (
    FluidDomain,
    build_annular_passage,
    build_row_fluid_domain,
    build_stage_fluid_domain,
    port_patch,
    sliding_interface,
)
from .radial import (
    MeridionalContour,
    RadialBladeRow,
    VoluteInterface,
    build_radial_blade_row,
    build_return_channel,
    build_vaneless_diffuser,
    scaled_radial_sections,
)
from .robustness import (
    GeometryDiagnostic,
    TopologyChange,
    TopologyChangeReceipt,
    blocking,
    check_clearance,
    check_manifold,
    check_required_roles,
    check_row_overlap,
    check_section,
    check_stack,
    topology_change_receipt,
)
from .sections import (
    CAMBER_FAMILIES,
    STACKING_AXES,
    THICKNESS_FAMILIES,
    BladeSection,
    CamberLine,
    ThicknessDistribution,
    place_section,
    section_digest,
    section_outline,
    section_parameters,
)

__all__ = [
    "CAMBER_FAMILIES",
    "STACKING_AXES",
    "THICKNESS_FAMILIES",
    "BladeSection",
    "CamberLine",
    "ThicknessDistribution",
    "place_section",
    "section_digest",
    "section_outline",
    "section_parameters",
    "GeometryBody",
    "SurfacePatch",
    "body_digest",
    "BladeRowGeometry",
    "build_axial_blade_row",
    "blade_row_parameter_defs",
    "scaled_sections",
    "MeridionalContour",
    "RadialBladeRow",
    "VoluteInterface",
    "build_radial_blade_row",
    "build_vaneless_diffuser",
    "build_return_channel",
    "scaled_radial_sections",
    "FluidDomain",
    "build_annular_passage",
    "build_row_fluid_domain",
    "build_stage_fluid_domain",
    "port_patch",
    "sliding_interface",
    "GeometryDiagnostic",
    "TopologyChange",
    "TopologyChangeReceipt",
    "blocking",
    "check_clearance",
    "check_manifold",
    "check_required_roles",
    "check_row_overlap",
    "check_section",
    "check_stack",
    "topology_change_receipt",
    "CadSolidReceipt",
    "annular_revolve",
    "blade_shape",
    "export_shapes",
    "fluid_sector_shape",
    "probe_cad",
    "radial_blade_shape",
    "radial_fluid_sector_shape",
    "row_shapes",
    "solid_receipt",
]
