"""Native meshing admission and quality contracts."""

from .domains import (
    BoundaryLayerIntent,
    BoxSelector,
    DomainKind,
    MeshSpec,
    PatchKind,
    PatchSpec,
    RefinementSpec,
    ZoneMotion,
    ZoneSpec,
)
from .gmsh_adapter import MeshPlan, MeshReceipt, plan_gmsh_mesh
from .morph import MorphReceipt, UpdatePolicy, decide_update_strategy, morph_affine
from .native_mesh import (
    GmshCapability,
    InterfaceGroup,
    NativeMeshReceipt,
    PeriodicPair,
    build_native_mesh,
    duct_mesh_spec,
    probe_gmsh,
)
from .quality import MeshQuality, compute_quality

__all__ = [
    "MeshPlan",
    "MeshReceipt",
    "plan_gmsh_mesh",
    "BoundaryLayerIntent",
    "BoxSelector",
    "DomainKind",
    "MeshSpec",
    "PatchKind",
    "PatchSpec",
    "RefinementSpec",
    "ZoneMotion",
    "ZoneSpec",
    "MorphReceipt",
    "UpdatePolicy",
    "decide_update_strategy",
    "morph_affine",
    "GmshCapability",
    "InterfaceGroup",
    "NativeMeshReceipt",
    "PeriodicPair",
    "build_native_mesh",
    "duct_mesh_spec",
    "probe_gmsh",
    "MeshQuality",
    "compute_quality",
]
