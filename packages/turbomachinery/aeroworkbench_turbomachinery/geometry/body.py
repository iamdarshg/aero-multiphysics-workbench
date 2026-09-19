"""Deterministic structured-surface geometry bodies.

The canonical representation is a set of *surface patches* (structured point
grids) carrying engineering semantic roles. It owns no CAD kernel and needs
none: coordinates, patch connectivity, manifold incidence, and content hashes
are computed directly, so a change in chord, stagger, twist, clearance, count,
or profile family alters the real topology and hash rather than a label.

Native BREP solids are produced separately by :mod:`cad` through the shared
CadQuery operation contracts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal

Point = tuple[float, float, float]
Domain = Literal["solid", "fluid"]

_PRECISION = 9
_EDGE_PRECISION = 6

OPEN_PATCH_KINDS: frozenset[str] = frozenset(
    {
        "inlet",
        "outlet",
        "periodic",
        "interface",
        "sliding_interface",
        "bleed",
        "cooling",
        "mixing_plane",
        "symmetry",
    }
)


def _quantize(value: float) -> float:
    number = round(float(value), _PRECISION)
    if number == 0:
        return 0.0
    return number


def _key(point: Point) -> Point:
    return (
        round(float(point[0]), _EDGE_PRECISION),
        round(float(point[1]), _EDGE_PRECISION),
        round(float(point[2]), _EDGE_PRECISION),
    )


def _validate_point(point: Point, label: str) -> None:
    if len(point) != 3:
        raise ValueError(f"{label}_NEEDS_THREE_COORDINATES")
    if not all(isfinite(float(coordinate)) for coordinate in point):
        raise ValueError(f"{label}_NOT_FINITE")


@dataclass(frozen=True, slots=True)
class SurfacePatch:
    """One structured surface patch belonging to a semantic engineering role.

    ``points`` is a row-major ``nu`` by ``nv`` grid. ``closed_u``/``closed_v``
    make the grid wrap in that direction (a full annulus or a closed outline).
    ``kind`` is the boundary character (wall, inlet, outlet, periodic,
    interface, ...) used by the robustness and meshing layers.
    """

    patch_id: str
    role: str
    kind: str
    nu: int
    nv: int
    points: tuple[Point, ...]
    closed_u: bool = False
    closed_v: bool = False

    def __post_init__(self) -> None:
        if not self.patch_id.strip():
            raise ValueError("PATCH_ID_REQUIRED")
        if not self.role.strip():
            raise ValueError("PATCH_ROLE_REQUIRED")
        if self.nu < 1 or self.nv < 1:
            raise ValueError(f"PATCH_GRID_DIMENSIONS_REQUIRED:{self.patch_id}")
        if len(self.points) != self.nu * self.nv:
            raise ValueError(f"PATCH_POINT_COUNT_MISMATCH:{self.patch_id}")
        for point in self.points:
            _validate_point(point, f"PATCH_POINT:{self.patch_id}")
        if self.closed_u and self.nu < 3:
            raise ValueError(f"CLOSED_U_NEEDS_THREE_COLUMNS:{self.patch_id}")
        if self.closed_v and self.nv < 3:
            raise ValueError(f"CLOSED_V_NEEDS_THREE_ROWS:{self.patch_id}")

    def point(self, i: int, j: int) -> Point:
        return self.points[j * self.nu + i]

    def faces(self) -> list[list[Point]]:
        """Quadrilateral/triangle faces of the structured patch.

        Interior grid edges therefore appear twice (shared by two faces) and
        boundary edges once, which is what manifold incidence must measure.
        """

        nu, nv = self.nu, self.nv
        if nu == 1 or nv == 1:
            count = max(nu, nv)
            points = [self.point(i, 0) if nv == 1 else self.point(0, i) for i in range(count)]
            return [
                [points[0], points[index], points[index + 1]]
                for index in range(1, count - 1)
            ]
        faces: list[list[Point]] = []
        u_count = nu if self.closed_u else nu - 1
        v_count = nv if self.closed_v else nv - 1
        for j in range(v_count):
            j_next = (j + 1) % nv
            for i in range(u_count):
                i_next = (i + 1) % nu
                faces.append(
                    [
                        self.point(i, j),
                        self.point(i_next, j),
                        self.point(i_next, j_next),
                        self.point(i, j_next),
                    ]
                )
        return faces

    def edges(self) -> list[tuple[Point, Point]]:
        result: list[tuple[Point, Point]] = []
        for face in self.faces():
            closed = [*face, face[0]]
            for start, end in zip(closed, closed[1:], strict=False):
                result.append((start, end))
        return result

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "patchId": self.patch_id,
            "role": self.role,
            "kind": self.kind,
            "nu": self.nu,
            "nv": self.nv,
            "closedU": self.closed_u,
            "closedV": self.closed_v,
            "points": [
                [_quantize(coordinate) for coordinate in point] for point in self.points
            ],
        }

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        zs = [point[2] for point in self.points]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


@dataclass(frozen=True, slots=True)
class GeometryBody:
    """A named set of semantic surface patches (solid or fluid domain)."""

    body_id: str
    domain: Domain
    patches: tuple[SurfacePatch, ...]

    def __post_init__(self) -> None:
        if not self.body_id.strip():
            raise ValueError("BODY_ID_REQUIRED")
        if self.domain not in ("solid", "fluid"):
            raise ValueError(f"UNKNOWN_BODY_DOMAIN:{self.domain}")
        if not self.patches:
            raise ValueError(f"BODY_NEEDS_PATCHES:{self.body_id}")
        identifiers = [patch.patch_id for patch in self.patches]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"DUPLICATE_PATCH_ID:{self.body_id}")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "bodyId": self.body_id,
            "domain": self.domain,
            "patches": [
                patch.canonical_payload()
                for patch in sorted(self.patches, key=lambda item: item.patch_id)
            ],
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        boxes = [patch.bounds() for patch in self.patches]
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
            max(box[4] for box in boxes),
            max(box[5] for box in boxes),
        )

    def edge_incidence(self) -> dict[tuple[Point, Point], int]:
        incidence: dict[tuple[Point, Point], int] = {}
        for patch in self.patches:
            for start, end in patch.edges():
                a, b = _key(start), _key(end)
                if a == b:
                    continue
                edge = (a, b) if a <= b else (b, a)
                incidence[edge] = incidence.get(edge, 0) + 1
        return incidence

    def unpaired_edges(self) -> tuple[tuple[Point, Point], ...]:
        return tuple(
            sorted(edge for edge, count in self.edge_incidence().items() if count == 1)
        )

    def nonmanifold_edges(self) -> tuple[tuple[Point, Point], ...]:
        return tuple(
            sorted(edge for edge, count in self.edge_incidence().items() if count > 2)
        )

    def is_manifold(self) -> bool:
        return not self.nonmanifold_edges()

    def is_closed(self) -> bool:
        return not self.unpaired_edges() and self.is_manifold()

    def roles(self) -> tuple[str, ...]:
        return tuple(sorted({patch.role for patch in self.patches}))

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({patch.kind for patch in self.patches}))

    def topology_signature(self) -> tuple[tuple[str, str, str, int, int, bool, bool], ...]:
        return tuple(
            (
                patch.patch_id,
                patch.role,
                patch.kind,
                patch.nu,
                patch.nv,
                patch.closed_u,
                patch.closed_v,
            )
            for patch in sorted(self.patches, key=lambda item: item.patch_id)
        )


def body_digest(body: GeometryBody) -> str:
    return body.digest()
