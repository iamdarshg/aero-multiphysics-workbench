"""Structured aerodynamic surface/body seam for FFD deformation and meshing.

A :class:`SurfaceSeam` is a named set of :class:`SurfaceGrid` structured point
grids carrying engineering roles. Coordinates, grid connectivity and content
hashes are computed directly, so a change in chord, sweep, twist, deflection or
section shape alters the real control net and its hash rather than a label. The
same seam serves lifting surfaces, lofted bodies and control surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from ..canonical import content_digest

Point = tuple[float, float, float]

SEAM_DOMAINS: tuple[str, ...] = ("solid", "fluid")


def _finite_point(point: Point, label: str) -> None:
    if len(point) != 3:
        raise ValueError(f"{label}_NEEDS_THREE_COORDINATES")
    if not all(isfinite(float(coordinate)) for coordinate in point):
        raise ValueError(f"{label}_NOT_FINITE")


@dataclass(frozen=True, slots=True)
class SurfaceGrid:
    """One structured ``nu`` by ``nv`` control grid in a semantic role."""

    grid_id: str
    role: str
    kind: str
    nu: int
    nv: int
    points: tuple[Point, ...]
    closed_u: bool = False
    closed_v: bool = False

    def __post_init__(self) -> None:
        if not self.grid_id.strip():
            raise ValueError("SEAM_GRID_ID_REQUIRED")
        if not self.role.strip():
            raise ValueError("SEAM_GRID_ROLE_REQUIRED")
        if self.nu < 1 or self.nv < 1:
            raise ValueError(f"SEAM_GRID_DIMENSIONS_REQUIRED:{self.grid_id}")
        if len(self.points) != self.nu * self.nv:
            raise ValueError(f"SEAM_GRID_POINT_COUNT_MISMATCH:{self.grid_id}")
        for point in self.points:
            _finite_point(point, f"SEAM_GRID_POINT:{self.grid_id}")
        if self.closed_u and self.nu < 3:
            raise ValueError(f"SEAM_CLOSED_U_NEEDS_THREE_COLUMNS:{self.grid_id}")
        if self.closed_v and self.nv < 3:
            raise ValueError(f"SEAM_CLOSED_V_NEEDS_THREE_ROWS:{self.grid_id}")

    def point(self, i: int, j: int) -> Point:
        return self.points[j * self.nu + i]

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        zs = [point[2] for point in self.points]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def topology_signature(self) -> tuple[str, str, str, int, int, bool, bool]:
        return (
            self.grid_id,
            self.role,
            self.kind,
            self.nu,
            self.nv,
            self.closed_u,
            self.closed_v,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gridId": self.grid_id,
            "role": self.role,
            "kind": self.kind,
            "nu": self.nu,
            "nv": self.nv,
            "closedU": self.closed_u,
            "closedV": self.closed_v,
            "points": [list(point) for point in self.points],
        }


@dataclass(frozen=True, slots=True)
class SurfaceSeam:
    """A named set of structured control grids (solid or fluid domain)."""

    seam_id: str
    domain: str
    grids: tuple[SurfaceGrid, ...]

    def __post_init__(self) -> None:
        if not self.seam_id.strip():
            raise ValueError("SEAM_ID_REQUIRED")
        if self.domain not in SEAM_DOMAINS:
            raise ValueError(f"UNKNOWN_SEAM_DOMAIN:{self.domain}")
        if not self.grids:
            raise ValueError(f"SEAM_NEEDS_GRIDS:{self.seam_id}")
        identifiers = [grid.grid_id for grid in self.grids]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"SEAM_DUPLICATE_GRID_ID:{self.seam_id}")

    def roles(self) -> tuple[str, ...]:
        return tuple(sorted({grid.role for grid in self.grids}))

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({grid.kind for grid in self.grids}))

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        boxes = [grid.bounds() for grid in self.grids]
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
            max(box[4] for box in boxes),
            max(box[5] for box in boxes),
        )

    def topology_signature(self) -> tuple[tuple[str, str, str, int, int, bool, bool], ...]:
        return tuple(
            grid.topology_signature()
            for grid in sorted(self.grids, key=lambda item: item.grid_id)
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "seamId": self.seam_id,
            "domain": self.domain,
            "grids": [
                grid.canonical_payload()
                for grid in sorted(self.grids, key=lambda item: item.grid_id)
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def seam_digest(seam: SurfaceSeam) -> str:
    """Deterministic SHA-256 identity of a structured seam."""

    return seam.digest


__all__ = [
    "Point",
    "SEAM_DOMAINS",
    "SurfaceGrid",
    "SurfaceSeam",
    "seam_digest",
]
