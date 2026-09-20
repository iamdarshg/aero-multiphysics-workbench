"""Community-noise footprints and trajectory sampling for mission studies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest

from .contracts import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    NoiseFidelity,
    NoiseValidity,
    analytical_provenance,
)
from .errors import ContractError
from .observers import EnvironmentSpec, FlightState, ObserverSpec, Vector3, _vector
from .propagation import PropagatableLine, propagate_to_observer

__all__ = [
    "FootprintCell",
    "FootprintGrid",
    "FootprintResult",
    "TrajectoryFootprint",
    "TrajectorySample",
    "footprint_from_trajectory",
    "sample_footprint",
]


def _finite(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a number")
    number = float(value)
    if not isfinite(number):
        raise ContractError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ContractError(f"{name} must be positive")
    return number


@dataclass(frozen=True, slots=True)
class FootprintGrid:
    """Deterministic ground-observer grid for community-noise footprints."""

    grid_id: str
    origin_m: Vector3
    spacing_m: float
    count_x: int
    count_y: int
    observer_height_m: float = 1.2

    def __post_init__(self) -> None:
        if not self.grid_id.strip():
            raise ContractError("grid_id is required")
        object.__setattr__(self, "origin_m", _vector(self.origin_m, "origin_m"))
        _finite(self.spacing_m, "spacing_m", positive=True)
        for label, count in (("count_x", self.count_x), ("count_y", self.count_y)):
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise ContractError(f"{label} must be a positive integer")
        _finite(self.observer_height_m, "observer_height_m")

    def observers(self) -> tuple[ObserverSpec, ...]:
        """Deterministic row-major observer lattice for the grid."""

        cells: list[ObserverSpec] = []
        for index_y in range(self.count_y):
            for index_x in range(self.count_x):
                cells.append(
                    ObserverSpec(
                        observer_id=f"{self.grid_id}:x{index_x}:y{index_y}",
                        position_m=(
                            self.origin_m[0] + index_x * self.spacing_m,
                            self.origin_m[1] + index_y * self.spacing_m,
                            self.observer_height_m,
                        ),
                    )
                )
        return tuple(cells)

    def canonical(self) -> dict[str, Any]:
        return {
            "gridId": self.grid_id,
            "originM": list(self.origin_m),
            "spacingM": self.spacing_m,
            "countX": self.count_x,
            "countY": self.count_y,
            "observerHeightM": self.observer_height_m,
        }


@dataclass(frozen=True, slots=True)
class FootprintCell:
    """One footprint observer with its propagated overall level."""

    observer_id: str
    overall_level_db: float

    def canonical(self) -> dict[str, Any]:
        return {"observerId": self.observer_id, "overallLevelDb": self.overall_level_db}


@dataclass(frozen=True, slots=True)
class FootprintResult:
    """Community-noise footprint: per-observer levels plus the maximum."""

    grid_id: str
    cells: tuple[FootprintCell, ...]
    max_level_db: float
    max_observer_id: str
    source_fidelity: NoiseFidelity
    propagation_fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"level_db": "dB", "distance_m": "m"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def area_above_db(self, threshold_db: float, spacing_m: float) -> float:
        """Grid area at or above a threshold; each cell owns one grid square."""

        threshold = _finite(threshold_db, "threshold_db")
        spacing = _finite(spacing_m, "spacing_m", positive=True)
        count = sum(1 for cell in self.cells if cell.overall_level_db >= threshold)
        return count * spacing * spacing

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gridId": self.grid_id,
            "cells": [cell.canonical() for cell in self.cells],
            "maxLevelDb": self.max_level_db,
            "maxObserverId": self.max_observer_id,
            "sourceFidelity": self.source_fidelity.value,
            "propagationFidelity": self.propagation_fidelity.value,
            "source": self.source,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def sample_footprint(
    grid: FootprintGrid,
    lines: Sequence[PropagatableLine],
    environment: EnvironmentSpec,
    flight: FlightState,
    *,
    source_fidelity: NoiseFidelity,
) -> FootprintResult:
    """Sample one instantaneous source state over the whole observer grid."""

    if not lines:
        raise ContractError("NO_SOURCE_LINES: at least one declared source line is required")
    cells: list[FootprintCell] = []
    for observer in grid.observers():
        propagated = propagate_to_observer(
            lines, observer, environment, flight, source_fidelity=source_fidelity
        )
        cells.append(
            FootprintCell(
                observer_id=observer.observer_id,
                overall_level_db=propagated.overall_level_db,
            )
        )
    ordered = tuple(sorted(cells, key=lambda cell: (-cell.overall_level_db, cell.observer_id)))
    worst = ordered[0]
    checks = {"cells_resolved": len(ordered) == grid.count_x * grid.count_y}
    inputs = {
        "grid": grid.canonical(),
        "lines": [line.canonical() for line in lines],
        "environment": environment.canonical(),
        "flight": flight.canonical(),
        "sourceFidelity": source_fidelity.value,
    }
    return FootprintResult(
        grid_id=grid.grid_id,
        cells=ordered,
        max_level_db=worst.overall_level_db,
        max_observer_id=worst.observer_id,
        source_fidelity=source_fidelity,
        propagation_fidelity=NoiseFidelity.OBSERVER_ANALYTICAL,
        validity=NoiseValidity(
            all(checks.values()), checks, f"sampled {len(ordered)} footprint observers"
        ),
        provenance=analytical_provenance(
            "aeroacoustics.footprint-sampling",
            inputs,
            assumptions=("one instantaneous source state over a fixed observer grid",),
        ),
    )


@dataclass(frozen=True, slots=True)
class TrajectorySample:
    """One trajectory instant: vehicle state plus its declared source lines."""

    time_s: float
    position_m: Vector3
    velocity_m_s: Vector3
    lines: tuple[PropagatableLine, ...]

    def __post_init__(self) -> None:
        _finite(self.time_s, "time_s")
        object.__setattr__(self, "position_m", _vector(self.position_m, "position_m"))
        object.__setattr__(self, "velocity_m_s", _vector(self.velocity_m_s, "velocity_m_s"))
        if not self.lines:
            raise ContractError("trajectory sample needs at least one source line")

    def flight(self) -> FlightState:
        return FlightState(
            source_position_m=self.position_m,
            source_velocity_m_s=self.velocity_m_s,
            time_s=self.time_s,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "timeS": self.time_s,
            "positionM": list(self.position_m),
            "velocityMS": list(self.velocity_m_s),
            "lines": [line.canonical() for line in self.lines],
        }


@dataclass(frozen=True, slots=True)
class TrajectoryFootprint:
    """Worst-case community footprint across a sampled trajectory."""

    grid_id: str
    sample_count: int
    cells: tuple[FootprintCell, ...]
    max_level_db: float
    max_observer_id: str
    max_time_s: float
    source_fidelity: NoiseFidelity
    propagation_fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"level_db": "dB", "time_s": "s", "distance_m": "m"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gridId": self.grid_id,
            "sampleCount": self.sample_count,
            "cells": [cell.canonical() for cell in self.cells],
            "maxLevelDb": self.max_level_db,
            "maxObserverId": self.max_observer_id,
            "maxTimeS": self.max_time_s,
            "sourceFidelity": self.source_fidelity.value,
            "propagationFidelity": self.propagation_fidelity.value,
            "source": self.source,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def footprint_from_trajectory(
    grid: FootprintGrid,
    samples: Sequence[TrajectorySample],
    environment: EnvironmentSpec,
    *,
    source_fidelity: NoiseFidelity,
) -> TrajectoryFootprint:
    """Worst-case footprint across trajectory samples for mission studies."""

    if not samples:
        raise ContractError("NO_TRAJECTORY_SAMPLES: at least one sample is required")
    per_sample = tuple(
        sample_footprint(grid, sample.lines, environment, sample.flight(),
                         source_fidelity=source_fidelity)
        for sample in samples
    )
    worst_by_observer: dict[str, float] = {}
    worst_time: dict[str, float] = {}
    for sample, footprint in zip(samples, per_sample, strict=True):
        for cell in footprint.cells:
            if cell.overall_level_db > worst_by_observer.get(cell.observer_id, float("-inf")):
                worst_by_observer[cell.observer_id] = cell.overall_level_db
                worst_time[cell.observer_id] = sample.time_s
    cells = tuple(
        FootprintCell(observer_id=observer_id, overall_level_db=worst_by_observer[observer_id])
        for observer_id in sorted(worst_by_observer)
    )
    ordered = tuple(sorted(cells, key=lambda cell: (-cell.overall_level_db, cell.observer_id)))
    worst = ordered[0]
    checks = {
        "samples_covered": len(per_sample) == len(samples),
        "observers_covered": len(cells) == grid.count_x * grid.count_y,
    }
    inputs = {
        "grid": grid.canonical(),
        "samples": [sample.canonical() for sample in samples],
        "environment": environment.canonical(),
        "sourceFidelity": source_fidelity.value,
    }
    return TrajectoryFootprint(
        grid_id=grid.grid_id,
        sample_count=len(samples),
        cells=ordered,
        max_level_db=worst.overall_level_db,
        max_observer_id=worst.observer_id,
        max_time_s=worst_time[worst.observer_id],
        source_fidelity=source_fidelity,
        propagation_fidelity=NoiseFidelity.OBSERVER_ANALYTICAL,
        validity=NoiseValidity(
            all(checks.values()), checks,
            f"worst case over {len(samples)} trajectory samples",
        ),
        provenance=analytical_provenance(
            "aeroacoustics.trajectory-footprint",
            inputs,
            assumptions=("worst-case per-observer level across declared samples",),
        ),
    )
