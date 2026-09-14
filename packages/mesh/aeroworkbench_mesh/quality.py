"""Measured mesh quality from the live Gmsh model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MeshQuality:
    """Quality measures where the backend provides them.

    ``non_orthogonality_deg`` is not a Gmsh-native quantity; it is recorded
    as ``None`` with the reason so downstream OpenFOAM ``checkMesh`` remains
    the authority instead of an invented number.
    """

    element_count: int
    node_count: int
    min_size_mm: float | None
    max_size_mm: float | None
    min_sicn: float | None
    min_scaled_jacobian: float | None
    inverted_count: int
    aspect_ratio_max: float | None
    boundary_layer_applied: bool
    boundary_layer_detail: str
    non_orthogonality_deg: float | None = None
    non_orthogonality_note: str = "not provided by Gmsh; use checkMesh downstream"

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "elementCount": self.element_count,
            "nodeCount": self.node_count,
            "minSizeMm": self.min_size_mm,
            "maxSizeMm": self.max_size_mm,
            "minSicn": self.min_sicn,
            "minScaledJacobian": self.min_scaled_jacobian,
            "invertedCount": self.inverted_count,
            "aspectRatioMax": self.aspect_ratio_max,
            "boundaryLayerApplied": self.boundary_layer_applied,
            "boundaryLayerDetail": self.boundary_layer_detail,
            "nonOrthogonalityDeg": self.non_orthogonality_deg,
            "nonOrthogonalityNote": self.non_orthogonality_note,
        }


def _qualities(gmsh: Any, element_tags: list[int], measure: str) -> list[float]:
    if not element_tags:
        return []
    try:
        qualities = gmsh.model.mesh.getElementQualities(element_tags, measure)
    except Exception:
        return []
    return [float(value) for value in qualities]


def compute_quality(gmsh: Any, *, boundary_layer: tuple[bool, str]) -> MeshQuality:
    """Measure quality of the current mesh in the live Gmsh model."""

    volumes = gmsh.model.getEntities(3)
    dimension = 3 if volumes else 2
    _entity_types, element_tags_nested, node_tags_per_element = (
        gmsh.model.mesh.getElements(dimension, -1)
    )
    element_tags = [int(tag) for tags in element_tags_nested for tag in tags]
    element_count = sum(len(tags) for tags in node_tags_per_element)
    node_tags, _, _ = gmsh.model.mesh.getNodes(-1, -1, True, False)
    sicn = _qualities(gmsh, element_tags, "minSICN")
    jacobian = _qualities(gmsh, element_tags, "minSJ")
    min_edge = _qualities(gmsh, element_tags, "minEdge")
    max_edge = _qualities(gmsh, element_tags, "maxEdge")
    aspect = _qualities(gmsh, element_tags, "aspectRatio")
    inverted = sum(1 for value in sicn if value < 0)
    return MeshQuality(
        element_count=element_count,
        node_count=len(node_tags),
        min_size_mm=min(min_edge) if min_edge else None,
        max_size_mm=max(max_edge) if max_edge else None,
        min_sicn=min(sicn) if sicn else None,
        min_scaled_jacobian=min(jacobian) if jacobian else None,
        inverted_count=inverted,
        aspect_ratio_max=max(aspect) if aspect else None,
        boundary_layer_applied=boundary_layer[0],
        boundary_layer_detail=boundary_layer[1],
    )
