"""Gmsh command planning with explicit capability and quality gates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from aeroworkbench_geometry import GeometryModel, shape_hash


@dataclass(frozen=True, slots=True)
class MeshPlan:
    geometry_hash: str
    dimension: int
    element_size_mm: float
    minimum_quality: float
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MeshReceipt:
    state: str
    geometry_hash: str
    mesh_hash: str | None
    element_count: int
    minimum_quality: float | None
    detail: str


def plan_gmsh_mesh(
    geometry: GeometryModel,
    *,
    case_directory: str,
    element_size_mm: float = 2.0,
    dimension: int = 3,
    gmsh_executable: str = "gmsh",
) -> MeshPlan:
    """Plan a native Gmsh invocation without spawning or shell interpolation."""

    if not case_directory or "/" in case_directory or "\\" in case_directory:
        raise ValueError("INVALID_CASE_DIRECTORY")
    if element_size_mm <= 0 or dimension not in (2, 3):
        raise ValueError("INVALID_MESH_SETTINGS")
    geometry_digest = shape_hash(geometry)
    command = (gmsh_executable, "-3" if dimension == 3 else "-2", "-format", "msh4", case_directory)
    return MeshPlan(geometry_digest, dimension, element_size_mm, 0.2, command)


def unavailable_receipt(plan: MeshPlan, detail: str = "gmsh is not installed") -> MeshReceipt:
    """Return an honest capability receipt; never substitute a fake mesh."""

    return MeshReceipt("unavailable", plan.geometry_hash, None, 0, None, detail)


def receipt_from_native_mesh(
    plan: MeshPlan, *, mesh_path: Path, element_count: int, minimum_quality: float
) -> MeshReceipt:
    """Create a receipt only after a native mesh artifact exists and passes quality."""

    if element_count <= 0 or not 0 <= minimum_quality <= 1:
        raise ValueError("INVALID_MESH_QUALITY")
    if minimum_quality < plan.minimum_quality:
        return MeshReceipt(
            "failed",
            plan.geometry_hash,
            None,
            element_count,
            minimum_quality,
            "MESH_QUALITY_BELOW_THRESHOLD",
        )
    payload = json.dumps(
        {
            "geometryHash": plan.geometry_hash,
            "elementCount": element_count,
            "minimumQuality": minimum_quality,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    artifact_hash = hashlib.sha256(mesh_path.read_bytes() + payload).hexdigest()
    return MeshReceipt(
        "completed",
        plan.geometry_hash,
        artifact_hash,
        element_count,
        minimum_quality,
        "native mesh accepted",
    )
