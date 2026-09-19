"""Measured mesh-quality receipt with provenance.

A :class:`MeshQualityReceipt` records cell counts by region, skewness,
non-orthogonality, aspect ratio, SICN, achieved y+/first-layer and layer
coverage, gap cells, interface quality, adaptation lineage, and estimated
memory/runtime. When the mesh was measured by a native mesher, the metrics are
copied verbatim from that measurement. When only a plan exists, metrics stay
``None`` and the receipt is explicitly ``measured=False`` rather than inventing
numbers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aeroworkbench_mesh import MeshQuality

from .boundary_layer import BoundaryLayerPlan
from .contracts import ResultEnvelope, Validity

__all__ = [
    "InterfaceQuality",
    "MeshQualityReceipt",
    "RegionCellCount",
    "build_quality_receipt",
]


@dataclass(frozen=True, slots=True)
class RegionCellCount:
    """Cell count attributed to one semantic region."""

    region: str
    cell_count: int

    def __post_init__(self) -> None:
        if not self.region.strip():
            raise ValueError("REGION_CELL_COUNT_NAME_REQUIRED")
        if self.cell_count < 0:
            raise ValueError(f"REGION_CELL_COUNT_NEGATIVE:{self.region}")


@dataclass(frozen=True, slots=True)
class InterfaceQuality:
    """Quality of one declared interface group."""

    name: str
    kind: str
    surface_count: int
    conformal_achieved: bool

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("INTERFACE_QUALITY_NAME_REQUIRED")
        if self.surface_count < 0:
            raise ValueError(f"INTERFACE_QUALITY_NEGATIVE:{self.name}")


@dataclass(frozen=True, slots=True)
class MeshQualityReceipt:
    """Auditable quality record for a planned or measured mesh."""

    measured: bool
    region_cell_counts: tuple[RegionCellCount, ...]
    total_cells: int
    node_count: int
    skewness_max: float | None
    non_orthogonality_deg_max: float | None
    non_orthogonality_note: str
    aspect_ratio_max: float | None
    min_sicn: float | None
    inverted_count: int
    y_plus_target: float | None
    achieved_first_layer_mm: float | None
    achieved_y_plus: float | None
    layer_count: int
    layer_coverage: float
    gap_cells: tuple[tuple[str, int], ...]
    interfaces: tuple[InterfaceQuality, ...]
    adaptation_lineage: tuple[int, ...]
    estimated_memory_mb: float | None
    estimated_runtime_s: float | None
    validity: Validity
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, object]:
        return {
            "measured": self.measured,
            "regionCellCounts": [
                {"region": item.region, "cellCount": item.cell_count}
                for item in self.region_cell_counts
            ],
            "totalCells": self.total_cells,
            "nodeCount": self.node_count,
            "skewnessMax": self.skewness_max,
            "nonOrthogonalityDegMax": self.non_orthogonality_deg_max,
            "nonOrthogonalityNote": self.non_orthogonality_note,
            "aspectRatioMax": self.aspect_ratio_max,
            "minSicn": self.min_sicn,
            "invertedCount": self.inverted_count,
            "yPlusTarget": self.y_plus_target,
            "achievedFirstLayerMm": self.achieved_first_layer_mm,
            "achievedYPlus": self.achieved_y_plus,
            "layerCount": self.layer_count,
            "layerCoverage": self.layer_coverage,
            "gapCells": {region: count for region, count in self.gap_cells},
            "interfaces": [
                {
                    "name": item.name,
                    "kind": item.kind,
                    "surfaceCount": item.surface_count,
                    "conformalAchieved": item.conformal_achieved,
                }
                for item in self.interfaces
            ],
            "adaptationLineage": list(self.adaptation_lineage),
            "estimatedMemoryMb": self.estimated_memory_mb,
            "estimatedRuntimeS": self.estimated_runtime_s,
            "validity": self.validity.canonical(),
        }


def build_quality_receipt(
    *,
    region_cell_counts: Sequence[RegionCellCount],
    envelope: ResultEnvelope,
    gap_cells: Sequence[tuple[str, int]] = (),
    interfaces: Sequence[InterfaceQuality] = (),
    adaptation_lineage: Sequence[int] = (),
    boundary_layer: BoundaryLayerPlan | None = None,
    target_y_plus: float | None = None,
    estimated_memory_mb: float | None = None,
    estimated_runtime_s: float | None = None,
    measured: MeshQuality | None = None,
    minimum_sicn: float | None = None,
) -> MeshQualityReceipt:
    """Build a quality receipt from a measurement, or an unmeasured plan."""

    checks: dict[str, bool] = {"metrics_measured": measured is not None}
    if measured is not None:
        total_cells = measured.element_count
        node_count = measured.node_count
        skewness_max = None
        non_orthogonality = measured.non_orthogonality_deg
        non_orthogonality_note = measured.non_orthogonality_note
        aspect_ratio = measured.aspect_ratio_max
        min_sicn = measured.min_sicn
        inverted = measured.inverted_count
        checks["no_inverted_elements"] = inverted == 0
        if minimum_sicn is not None:
            checks["sicn_floor"] = min_sicn is not None and min_sicn >= minimum_sicn
    else:
        total_cells = sum(item.cell_count for item in region_cell_counts)
        node_count = 0
        skewness_max = None
        non_orthogonality = None
        non_orthogonality_note = "unmeasured plan; use native mesher/checkMesh"
        aspect_ratio = None
        min_sicn = None
        inverted = 0

    achieved_first = boundary_layer.achieved_first_layer_mm if boundary_layer else None
    achieved_y_plus = boundary_layer.achieved_y_plus if boundary_layer else None
    layer_count = boundary_layer.achieved_layer_count if boundary_layer else 0
    layer_coverage = boundary_layer.coverage_fraction if boundary_layer else 0.0
    if target_y_plus is not None and boundary_layer is not None:
        checks["y_plus_within_tolerance"] = bool(boundary_layer.meets_y_plus_target)

    detail = (
        "native measurement"
        if measured is not None
        else "planned resolution; metrics unmeasured until a native mesh exists"
    )
    validity = Validity(passed=all(checks.values()), checks=checks, detail=detail)
    return MeshQualityReceipt(
        measured=measured is not None,
        region_cell_counts=tuple(region_cell_counts),
        total_cells=total_cells,
        node_count=node_count,
        skewness_max=skewness_max,
        non_orthogonality_deg_max=non_orthogonality,
        non_orthogonality_note=non_orthogonality_note,
        aspect_ratio_max=aspect_ratio,
        min_sicn=min_sicn,
        inverted_count=inverted,
        y_plus_target=target_y_plus,
        achieved_first_layer_mm=achieved_first,
        achieved_y_plus=achieved_y_plus,
        layer_count=layer_count,
        layer_coverage=layer_coverage,
        gap_cells=tuple(gap_cells),
        interfaces=tuple(interfaces),
        adaptation_lineage=tuple(adaptation_lineage),
        estimated_memory_mb=estimated_memory_mb,
        estimated_runtime_s=estimated_runtime_s,
        validity=validity,
        envelope=envelope,
    )
