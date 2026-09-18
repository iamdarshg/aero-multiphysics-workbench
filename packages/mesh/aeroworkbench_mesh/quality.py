"""Measured mesh quality from the live Gmsh model.

Every number here is measured from the mesh Gmsh actually produced. Metrics the
backend cannot supply are recorded as ``None`` with a reason instead of being
invented; downstream ``checkMesh`` remains the authority for those.
"""

from __future__ import annotations

from contextlib import suppress
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
    element_counts_by_type: tuple[tuple[str, int], ...] = ()
    percentile_sicn: tuple[tuple[str, float], ...] = ()
    orphan_surface_count: int = 0
    unclassified_volume_count: int = 0

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
            "elementCountsByType": dict(self.element_counts_by_type),
            "percentileSicn": dict(self.percentile_sicn),
            "orphanSurfaceCount": self.orphan_surface_count,
            "unclassifiedVolumeCount": self.unclassified_volume_count,
        }


def _qualities(gmsh: Any, element_tags: list[int], measure: str) -> list[float]:
    if not element_tags:
        return []
    try:
        qualities = gmsh.model.mesh.getElementQualities(element_tags, measure)
    except Exception:
        return []
    return [float(value) for value in qualities]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _element_counts_by_type(
    gmsh: Any, element_types: list[int], element_tags: list[list[int]]
) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    for element_type, tags in zip(element_types, element_tags, strict=False):
        name = f"type-{element_type}"
        with suppress(Exception):
            name = str(gmsh.model.mesh.getElementProperties(int(element_type))[0])
        counts.append((name, len(tags)))
    return sorted(counts)


def compute_quality(
    gmsh: Any,
    *,
    boundary_layer: tuple[bool, str],
    classified_surfaces: set[int] | None = None,
    classified_volumes: set[int] | None = None,
) -> MeshQuality:
    """Measure quality of the current mesh in the live Gmsh model."""

    volumes = gmsh.model.getEntities(3)
    dimension = 3 if volumes else 2
    element_types, element_tags_nested, node_tags_per_element = (
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
    percentiles: list[tuple[str, float]] = []
    for label, fraction in (("p01", 0.01), ("p05", 0.05), ("p50", 0.50)):
        value = _percentile(sicn, fraction)
        if value is not None:
            percentiles.append((label, value))
    orphan_surfaces = 0
    if classified_surfaces is not None:
        all_surfaces = {int(tag) for _, tag in gmsh.model.getEntities(2)}
        orphan_surfaces = len(all_surfaces - classified_surfaces)
    unclassified_volumes = 0
    if classified_volumes is not None:
        all_volumes = {int(tag) for _, tag in gmsh.model.getEntities(3)}
        unclassified_volumes = len(all_volumes - classified_volumes)
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
        element_counts_by_type=tuple(
            _element_counts_by_type(gmsh, element_types, element_tags_nested)
        ),
        percentile_sicn=tuple(percentiles),
        orphan_surface_count=orphan_surfaces,
        unclassified_volume_count=unclassified_volumes,
    )


def evaluate_quality_gate(
    quality: MeshQuality, minimum_sicn: float
) -> tuple[bool, str]:
    """Pure acceptance gate: no inverted elements and a measured SICN floor.

    A missing SICN is *not* a pass: when the backend cannot measure quality the
    gate fails closed instead of assuming the mesh is acceptable.
    """

    if quality.inverted_count:
        return False, f"MESH_INVERTED_ELEMENTS:{quality.inverted_count}"
    if quality.min_sicn is None:
        return False, "MESH_QUALITY_UNMEASURED"
    if quality.min_sicn < minimum_sicn:
        return False, f"MESH_QUALITY_BELOW_THRESHOLD:{quality.min_sicn:.6f}<{minimum_sicn}"
    return True, (
        f"min SICN {quality.min_sicn:.6f} >= {minimum_sicn}"
        f"; {quality.element_count} elements, 0 inverted"
    )
