"""Native meshing admission and quality contracts."""

from .gmsh_adapter import MeshPlan, MeshReceipt, plan_gmsh_mesh

__all__ = ["MeshPlan", "MeshReceipt", "plan_gmsh_mesh"]
