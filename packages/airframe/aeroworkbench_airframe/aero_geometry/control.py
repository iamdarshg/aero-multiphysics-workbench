"""Typed, deflectable control surfaces as semantic children of lifting surfaces.

A :class:`ControlSurface` references a parent lifting surface by id and is
positioned by hinge/span/chord fractions. Its solid is a real lofted surface
derived from the parent station profiles and rotated about the hinge line by
the commanded deflection, so a deflection changes the child geometry without
mutating or hiding the parent semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, isfinite, pi, sin
from typing import Any

from aeroworkbench_geometry import ParameterDef, SemanticBinding
from aeroworkbench_semantics import SemanticAssignment

from ..canonical import content_digest
from .profile import DEFAULT_PROFILE_POINTS, linspace
from .seam import Point, SurfaceGrid, SurfaceSeam
from .surface import LiftingSurface, SpanwiseStation

CONTROL_SURFACE_KINDS: tuple[str, ...] = (
    "aileron",
    "flap",
    "elevator",
    "rudder",
    "spoiler",
    "elevon",
    "flaperon",
    "slat",
    "general",
)

CONTROL_SURFACE_ROLES: tuple[str, ...] = (
    "surface_upper",
    "surface_lower",
    "hinge",
    "trailing_edge",
    "root",
    "tip",
)


def _rotate_about(
    point: tuple[float, float], hinge: tuple[float, float], angle_deg: float
) -> tuple[float, float]:
    angle = angle_deg * pi / 180.0
    dx = point[0] - hinge[0]
    dy = point[1] - hinge[1]
    return (
        hinge[0] + dx * cos(angle) - dy * sin(angle),
        hinge[1] + dx * sin(angle) + dy * cos(angle),
    )


@dataclass(frozen=True, slots=True)
class ControlSurface:
    """A typed, deflectable trailing-edge control surface."""

    control_id: str
    parent_id: str
    kind: str
    hinge_fraction: float
    span_fraction: tuple[float, float]
    deflection_deg: float = 0.0
    deflection_limits_deg: tuple[float, float] = (-30.0, 30.0)
    n_surface: int = DEFAULT_PROFILE_POINTS

    def __post_init__(self) -> None:
        if not self.control_id.strip():
            raise ValueError("CONTROL_SURFACE_ID_REQUIRED")
        if not self.parent_id.strip():
            raise ValueError("CONTROL_SURFACE_PARENT_REQUIRED")
        if self.kind not in CONTROL_SURFACE_KINDS:
            raise ValueError(f"UNKNOWN_CONTROL_SURFACE_KIND:{self.kind}")
        if not isfinite(self.hinge_fraction) or not 0.0 < self.hinge_fraction < 1.0:
            raise ValueError("CONTROL_SURFACE_HINGE_FRACTION_OUT_OF_RANGE")
        start, end = self.span_fraction
        if not isfinite(start) or not isfinite(end) or not 0.0 <= start < end <= 1.0:
            raise ValueError("CONTROL_SURFACE_SPAN_FRACTION_OUT_OF_RANGE")
        low, high = self.deflection_limits_deg
        if not isfinite(low) or not isfinite(high) or low >= high:
            raise ValueError("CONTROL_SURFACE_DEFLECTION_LIMITS_INVALID")
        if not isfinite(self.deflection_deg):
            raise ValueError("CONTROL_SURFACE_DEFLECTION_NOT_FINITE")
        if not low <= self.deflection_deg <= high:
            raise ValueError("CONTROL_SURFACE_DEFLECTION_OUT_OF_LIMITS")
        if self.n_surface < 3:
            raise ValueError("CONTROL_SURFACE_PROFILE_RESOLUTION_TOO_LOW")

    def with_deflection(self, deflection_deg: float) -> ControlSurface:
        return replace(self, deflection_deg=deflection_deg)

    def _stations(self, parent: LiftingSurface) -> tuple[SpanwiseStation, ...]:
        if parent.surface_id != self.parent_id:
            raise ValueError(f"CONTROL_SURFACE_PARENT_MISMATCH:{self.parent_id}")
        start, end = self.span_fraction
        selected = tuple(
            station
            for station in parent.stations
            if start <= station.span_fraction <= end
        )
        if len(selected) < 2:
            raise ValueError("CONTROL_SURFACE_SPAN_NEEDS_TWO_PARENT_STATIONS")
        return selected

    def section_loops(
        self, parent: LiftingSurface
    ) -> tuple[tuple[tuple[float, float], ...], ...]:
        loops: list[tuple[tuple[float, float], ...]] = []
        for station in self._stations(parent):
            if station.profile.family == "bspline":
                raise ValueError("CONTROL_SURFACE_REQUIRES_SURFACE_PROFILE")
            hinge = station.place_profile(self.hinge_fraction, 0.0)
            samples = linspace(self.hinge_fraction, 1.0, self.n_surface)
            lower = tuple(
                station.place_profile(u, station.profile.lower(u)) for u in samples
            )
            upper = tuple(
                station.place_profile(u, station.profile.upper(u)) for u in samples
            )
            loop = (*lower, *reversed(upper))
            loops.append(
                tuple(
                    _rotate_about((point[0], point[1]), (hinge[0], hinge[1]), self.deflection_deg)
                    for point in loop
                )
            )
        return tuple(loops)

    def offsets_mm(self, parent: LiftingSurface) -> tuple[float, ...]:
        return tuple(station.leading_edge_mm[2] for station in self._stations(parent))

    def cad_parameter_defs(self) -> tuple[ParameterDef, ...]:
        return (
            ParameterDef(f"{self.control_id}.deflection", self.deflection_deg, unit="deg"),
            ParameterDef(f"{self.control_id}.hinge", self.hinge_fraction, unit="dimensionless"),
        )

    def parameter_values(self) -> dict[str, float]:
        return {
            definition.name: float(definition.value or 0.0)
            for definition in self.cad_parameter_defs()
        }

    def semantic_assignments(self) -> tuple[SemanticAssignment, ...]:
        assignments = []
        for region, role in (
            ("hinge", "hinge"),
            ("upper", "surface_upper"),
            ("lower", "surface_lower"),
            ("trailing_edge", "trailing_edge"),
            ("root", "root"),
            ("tip", "tip"),
        ):
            boundary = "interface" if region in ("hinge", "root") else "wall"
            assignments.append(
                SemanticAssignment(
                    surface_id=f"{self.control_id}.{region}",
                    semantic_key=f"{self.control_id}.{region}",
                    role=role,
                    boundary=boundary,
                )
            )
        return tuple(assignments)

    def semantic_binding(self, component: str) -> SemanticBinding:
        return SemanticBinding(
            semantic_key=f"{self.control_id}.solid",
            kind="solid_region",
            region=self.control_id,
            component=component,
        )

    def seam(self, parent: LiftingSurface) -> SurfaceSeam:
        """Structured control-surface control grid for FFD and meshing."""
        stations = self._stations(parent)
        loops = self.section_loops(parent)
        count = len(loops[0])
        shell_points: tuple[Point, ...] = tuple(
            (point[0], point[1], stations[index].leading_edge_mm[2])
            for index, loop in enumerate(loops)
            for point in loop
        )
        grids: list[SurfaceGrid] = [
            SurfaceGrid(
                grid_id=f"{self.control_id}.shell",
                role="surface",
                kind="wall",
                nu=count,
                nv=len(loops),
                points=shell_points,
                closed_u=True,
            )
        ]
        for region, index, kind in (("root", 0, "interface"), ("tip", -1, "wall")):
            spine_z = stations[index].leading_edge_mm[2]
            cap_points: tuple[Point, ...] = tuple(
                (point[0], point[1], spine_z) for point in loops[index]
            )
            grids.append(
                SurfaceGrid(
                    grid_id=f"{self.control_id}.{region}",
                    role=region,
                    kind=kind,
                    nu=len(cap_points),
                    nv=1,
                    points=cap_points,
                    closed_u=True,
                )
            )
        return SurfaceSeam(seam_id=self.control_id, domain="solid", grids=tuple(grids))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "controlId": self.control_id,
            "parentId": self.parent_id,
            "kind": self.kind,
            "hingeFraction": self.hinge_fraction,
            "spanFraction": list(self.span_fraction),
            "deflectionDeg": self.deflection_deg,
            "deflectionLimitsDeg": list(self.deflection_limits_deg),
            "nSurface": self.n_surface,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def control_surface_digest(control: ControlSurface) -> str:
    """Deterministic SHA-256 identity of a control surface."""

    return control.digest


__all__ = [
    "CONTROL_SURFACE_KINDS",
    "CONTROL_SURFACE_ROLES",
    "ControlSurface",
    "control_surface_digest",
]
