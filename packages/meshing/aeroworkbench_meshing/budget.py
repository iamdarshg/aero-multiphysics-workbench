"""Mesh-budget control with an explicit insufficient-resolution state.

A :class:`MeshBudget` bounds total cells, memory, wall time, per-region cells,
and adaptation passes. :func:`assess_budget` estimates cells, memory, and runtime
from declared region volumes and the *requested* local sizes. When the requested
physics needs a resolution finer than the budget can afford, the assessment
returns ``insufficient_resolution`` instead of silently coarsening the request.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, floor, isfinite
from typing import Literal

from .errors import InsufficientResolutionError, MeshBudgetError, MeshContractError

__all__ = [
    "BudgetAssessment",
    "BudgetState",
    "MeshBudget",
    "RegionResolution",
    "assess_budget",
    "estimate_cells",
    "require_feasible",
]

BudgetState = Literal["within_budget", "insufficient_resolution", "budget_exceeded"]


@dataclass(frozen=True, slots=True)
class MeshBudget:
    """Declared limits for a meshing or adaptation campaign."""

    max_cells: int
    max_memory_mb: float
    max_wall_time_s: float
    max_adaptation_passes: int
    per_region_max_cells: tuple[tuple[str, int], ...] = ()
    bytes_per_cell: int = 512
    cells_per_second: float = 50000.0

    def __post_init__(self) -> None:
        if self.max_cells < 1:
            raise MeshContractError("BUDGET_MAX_CELLS_INVALID")
        if not isfinite(self.max_memory_mb) or self.max_memory_mb <= 0.0:
            raise MeshContractError("BUDGET_MAX_MEMORY_INVALID")
        if not isfinite(self.max_wall_time_s) or self.max_wall_time_s <= 0.0:
            raise MeshContractError("BUDGET_MAX_WALL_TIME_INVALID")
        if self.max_adaptation_passes < 0:
            raise MeshContractError("BUDGET_MAX_ADAPTATION_PASSES_INVALID")
        if self.bytes_per_cell < 1:
            raise MeshContractError("BUDGET_BYTES_PER_CELL_INVALID")
        if not isfinite(self.cells_per_second) or self.cells_per_second <= 0.0:
            raise MeshContractError("BUDGET_CELLS_PER_SECOND_INVALID")
        seen: set[str] = set()
        for region, cap in self.per_region_max_cells:
            if not region.strip():
                raise MeshContractError("BUDGET_REGION_NAME_REQUIRED")
            if cap < 1:
                raise MeshContractError(f"BUDGET_REGION_CAP_INVALID:{region}")
            if region in seen:
                raise MeshContractError(f"BUDGET_DUPLICATE_REGION:{region}")
            seen.add(region)

    def region_cap(self, region: str) -> int | None:
        for name, cap in self.per_region_max_cells:
            if name == region:
                return cap
        return None


@dataclass(frozen=True, slots=True)
class RegionResolution:
    """One region's requested local size and its domain volume."""

    region: str
    size_mm: float
    volume_mm3: float

    def __post_init__(self) -> None:
        if not self.region.strip():
            raise MeshContractError("REGION_RESOLUTION_NAME_REQUIRED")
        if not isfinite(self.size_mm) or self.size_mm <= 0.0:
            raise MeshContractError(f"REGION_RESOLUTION_SIZE_INVALID:{self.region}")
        if not isfinite(self.volume_mm3) or self.volume_mm3 <= 0.0:
            raise MeshContractError(f"REGION_RESOLUTION_VOLUME_INVALID:{self.region}")


def estimate_cells(volume_mm3: float, size_mm: float, *, dimension: int = 3) -> int:
    """Analytical cell-count estimate: volume divided by the cell size power."""

    if not isfinite(volume_mm3) or volume_mm3 <= 0.0:
        raise MeshContractError("ESTIMATE_VOLUME_MUST_BE_FINITE_POSITIVE")
    if not isfinite(size_mm) or size_mm <= 0.0:
        raise MeshContractError("ESTIMATE_SIZE_MUST_BE_FINITE_POSITIVE")
    if dimension not in (2, 3):
        raise MeshContractError("ESTIMATE_DIMENSION_INVALID")
    return max(1, int(ceil(volume_mm3 / size_mm**dimension)))


@dataclass(frozen=True, slots=True)
class BudgetAssessment:
    """Feasibility verdict for a requested set of local sizes."""

    state: BudgetState
    feasible: bool
    required_min_size_mm: float
    allowed_min_size_mm: float
    estimated_cells: int
    estimated_memory_mb: float
    estimated_wall_time_s: float
    max_cells_effective: int
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "feasible": self.feasible,
            "requiredMinSizeMm": self.required_min_size_mm,
            "allowedMinSizeMm": self.allowed_min_size_mm,
            "estimatedCells": self.estimated_cells,
            "estimatedMemoryMb": self.estimated_memory_mb,
            "estimatedWallTimeS": self.estimated_wall_time_s,
            "maxCellsEffective": self.max_cells_effective,
            "reasons": list(self.reasons),
        }


def assess_budget(
    resolutions: Sequence[RegionResolution],
    *,
    required_min_size_mm: float,
    budget: MeshBudget,
    base_size_mm: float,
    dimension: int = 3,
    floor_size_mm: float | None = None,
) -> BudgetAssessment:
    """Assess feasibility without ever coarsening the requested resolution."""

    if not resolutions:
        raise MeshContractError("BUDGET_NEEDS_REGION_RESOLUTIONS")
    if not isfinite(required_min_size_mm) or required_min_size_mm <= 0.0:
        raise MeshContractError("BUDGET_REQUIRED_MIN_SIZE_INVALID")
    total_volume = sum(item.volume_mm3 for item in resolutions)
    max_cells_memory = int(floor(budget.max_memory_mb * 1_000_000.0 / budget.bytes_per_cell))
    max_cells_time = int(floor(budget.max_wall_time_s * budget.cells_per_second))
    effective_max = min(budget.max_cells, max_cells_memory, max_cells_time)
    if effective_max < 1:
        raise MeshBudgetError("BUDGET_EFFECTIVE_CELL_LIMIT_BELOW_ONE")
    allowed = (total_volume / effective_max) ** (1.0 / dimension)
    if floor_size_mm is not None:
        allowed = max(allowed, floor_size_mm)

    estimated_cells = sum(
        estimate_cells(item.volume_mm3, item.size_mm, dimension=dimension)
        for item in resolutions
    )
    estimated_memory = estimated_cells * budget.bytes_per_cell / 1_000_000.0
    estimated_time = estimated_cells / budget.cells_per_second

    refinement_sizes = [item.size_mm for item in resolutions if item.size_mm < base_size_mm]
    refinement_min = min(refinement_sizes) if refinement_sizes else None
    reasons: list[str] = []
    tolerance = 1.0 + 1e-9

    if refinement_min is not None and refinement_min < allowed * tolerance:
        state: BudgetState = "insufficient_resolution"
        reasons.append(
            f"requested refinement {refinement_min:.6g}mm below affordable "
            f"{allowed:.6g}mm: coarsening refused"
        )
    elif required_min_size_mm < allowed * tolerance:
        state = "budget_exceeded"
        reasons.append(
            f"base resolution {required_min_size_mm:.6g}mm below affordable "
            f"{allowed:.6g}mm"
        )
    elif estimated_cells > budget.max_cells:
        state = "budget_exceeded"
        reasons.append(f"estimated {estimated_cells} cells exceeds {budget.max_cells}")
    elif estimated_memory > budget.max_memory_mb:
        state = "budget_exceeded"
        reasons.append(
            f"estimated {estimated_memory:.3f}MB exceeds {budget.max_memory_mb}MB"
        )
    elif estimated_time > budget.max_wall_time_s:
        state = "budget_exceeded"
        reasons.append(
            f"estimated {estimated_time:.3f}s exceeds {budget.max_wall_time_s}s"
        )
    else:
        state = "within_budget"
        reasons.append(
            f"estimated {estimated_cells} cells within {budget.max_cells} at "
            f"{required_min_size_mm:.6g}mm"
        )

    for item in resolutions:
        cap = budget.region_cap(item.region)
        if cap is None:
            continue
        region_cells = estimate_cells(item.volume_mm3, item.size_mm, dimension=dimension)
        if region_cells > cap:
            state = "budget_exceeded"
            reasons.append(f"region {item.region} estimate {region_cells} exceeds cap {cap}")

    return BudgetAssessment(
        state=state,
        feasible=state == "within_budget",
        required_min_size_mm=required_min_size_mm,
        allowed_min_size_mm=allowed,
        estimated_cells=estimated_cells,
        estimated_memory_mb=estimated_memory,
        estimated_wall_time_s=estimated_time,
        max_cells_effective=effective_max,
        reasons=tuple(reasons),
    )


def require_feasible(assessment: BudgetAssessment) -> None:
    """Fail closed unless the assessment is within budget."""

    if assessment.feasible:
        return
    detail = "; ".join(assessment.reasons) or assessment.state
    if assessment.state == "insufficient_resolution":
        raise InsufficientResolutionError(f"INSUFFICIENT_RESOLUTION:{detail}")
    raise MeshBudgetError(f"MESH_BUDGET_EXCEEDED:{detail}")
