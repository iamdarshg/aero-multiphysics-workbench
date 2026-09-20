"""Generic aerodynamic geometry primitives for profiles, lifting surfaces,
lofted bodies and typed control surfaces.

Public API (later AIRFRAME/geometry issues import these exact paths)::

    from aeroworkbench_airframe.aero_geometry import (
        AirfoilProfile,
        ProfileFamily,
        LiftingSurface,
        Planform,
        SpanwiseStation,
        LoftedBody,
        BodySection,
        ControlSurface,
        AeroGeometryAssembly,
        AeroGeometryRegenerator,
        regenerate_assembly,
        probe_cad,
    )

All primitives are deterministic, unit-bearing and hashable. Native CAD solids
are produced only through the shared :class:`GeometryRegenerationRequest` path,
which fails closed when the kernel is unavailable.
"""

from .assembly import (
    AeroGeometryAssembly,
    AeroGeometryRegenerator,
    regenerate_assembly,
)
from .body import (
    BODY_BOUNDARY_ROLES,
    BODY_ROLES,
    DEFAULT_SECTION_POINTS,
    MAX_SUPERELLIPSE_EXPONENT,
    BodySection,
    LoftedBody,
    lofted_body_digest,
)
from .cad import KernelIdentity, probe_cad, require_cad, require_kernel
from .control import (
    CONTROL_SURFACE_KINDS,
    CONTROL_SURFACE_ROLES,
    ControlSurface,
    control_surface_digest,
)
from .profile import (
    DEFAULT_EDGE_POINTS,
    DEFAULT_PROFILE_POINTS,
    PROFILE_FAMILIES,
    AirfoilProfile,
    profile_digest,
)
from .refinement import (
    FfdControl,
    GeometryRefinementPlan,
    RefinementReceipt,
    estimate_body_volume_mm3,
    refine_assembly,
)
from .robustness import (
    GeometryDiagnostic,
    TopologyChangeReceipt,
    aero_geometry_diagnostics,
    blocking,
    check_body,
    check_control_surface,
    check_lifting_surface,
    topology_change_receipt,
)
from .seam import Point, SurfaceGrid, SurfaceSeam, seam_digest
from .surface import (
    LIFTING_SURFACE_ROLES,
    SURFACE_BOUNDARY_ROLES,
    LiftingSurface,
    Planform,
    SpanwiseStation,
    lifting_surface_digest,
)

ProfileFamily = str

__all__ = [
    "PROFILE_FAMILIES",
    "DEFAULT_PROFILE_POINTS",
    "DEFAULT_EDGE_POINTS",
    "AirfoilProfile",
    "ProfileFamily",
    "profile_digest",
    "LIFTING_SURFACE_ROLES",
    "SURFACE_BOUNDARY_ROLES",
    "Planform",
    "SpanwiseStation",
    "LiftingSurface",
    "lifting_surface_digest",
    "BODY_ROLES",
    "BODY_BOUNDARY_ROLES",
    "DEFAULT_SECTION_POINTS",
    "MAX_SUPERELLIPSE_EXPONENT",
    "BodySection",
    "LoftedBody",
    "lofted_body_digest",
    "CONTROL_SURFACE_KINDS",
    "CONTROL_SURFACE_ROLES",
    "ControlSurface",
    "control_surface_digest",
    "AeroGeometryAssembly",
    "AeroGeometryRegenerator",
    "regenerate_assembly",
    "KernelIdentity",
    "probe_cad",
    "require_cad",
    "require_kernel",
    "GeometryDiagnostic",
    "TopologyChangeReceipt",
    "aero_geometry_diagnostics",
    "blocking",
    "check_body",
    "check_control_surface",
    "check_lifting_surface",
    "topology_change_receipt",
    "Point",
    "SurfaceGrid",
    "SurfaceSeam",
    "seam_digest",
    "FfdControl",
    "GeometryRefinementPlan",
    "RefinementReceipt",
    "estimate_body_volume_mm3",
    "refine_assembly",
]
