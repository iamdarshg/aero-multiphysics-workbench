"""Generic lifting-surface primitives: planform, spanwise stations, surface body.

A :class:`LiftingSurface` is a spanwise stack of :class:`SpanwiseStation` records.
Each station carries its leading-edge position, chord, twist, dihedral/local
frame and profile; the same contract covers wings, tails, fins, rotor blades,
flying wings and lifting bodies. Geometry is deterministic and unit-bearing in
millimetres, and the profile geometry reuses the shared spanwise-section
primitives.

The structured seam (:meth:`LiftingSurface.seam`) exposes the upper/lower/
leading-edge/trailing-edge/root/tip control grids that a future FFD deformation
or mesh generator consumes, and the semantic assignments name those regions
without application-specific vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, isfinite, pi, sin, tan
from typing import Any

from aeroworkbench_geometry import ParameterDef, SemanticBinding
from aeroworkbench_semantics import SemanticAssignment

from ..canonical import content_digest
from .profile import DEFAULT_EDGE_POINTS, DEFAULT_PROFILE_POINTS, AirfoilProfile
from .seam import Point, SurfaceGrid, SurfaceSeam

LIFTING_SURFACE_ROLES: tuple[str, ...] = (
    "wing",
    "tail",
    "fin",
    "rotor_blade",
    "flying_wing",
    "lifting_body",
    "general",
)

SURFACE_BOUNDARY_ROLES: tuple[tuple[str, str, str], ...] = (
    ("upper", "surface_upper", "wall"),
    ("lower", "surface_lower", "wall"),
    ("leading_edge", "leading_edge", "wall"),
    ("trailing_edge", "trailing_edge", "wall"),
    ("root", "root", "interface"),
    ("tip", "tip", "wall"),
)


def _finite(label: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{label}_NOT_FINITE")


@dataclass(frozen=True, slots=True)
class Planform:
    """Trapezoidal planform control of a lifting surface (all lengths in mm)."""

    span_mm: float
    root_chord_mm: float
    tip_chord_mm: float
    sweep_deg: float = 0.0
    dihedral_deg: float = 0.0
    twist_root_deg: float = 0.0
    twist_tip_deg: float = 0.0

    def __post_init__(self) -> None:
        for label, value in (
            ("SPAN", self.span_mm),
            ("ROOT_CHORD", self.root_chord_mm),
            ("TIP_CHORD", self.tip_chord_mm),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"PLANFORM_{label}_MUST_BE_POSITIVE")
        for label, value in (
            ("SWEEP", self.sweep_deg),
            ("DIHEDRAL", self.dihedral_deg),
            ("TWIST_ROOT", self.twist_root_deg),
            ("TWIST_TIP", self.twist_tip_deg),
        ):
            _finite(f"PLANFORM_{label}", value)

    @property
    def taper_ratio(self) -> float:
        return self.tip_chord_mm / self.root_chord_mm

    def chord_at(self, span_fraction: float) -> float:
        return self.root_chord_mm + (self.tip_chord_mm - self.root_chord_mm) * span_fraction

    def twist_at(self, span_fraction: float) -> float:
        return self.twist_root_deg + (self.twist_tip_deg - self.twist_root_deg) * span_fraction

    def leading_edge_offset_mm(self, span_fraction: float) -> tuple[float, float]:
        reach = self.span_mm * span_fraction
        return (
            reach * tan(self.sweep_deg * pi / 180.0),
            reach * tan(self.dihedral_deg * pi / 180.0),
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "spanMm": self.span_mm,
            "rootChordMm": self.root_chord_mm,
            "tipChordMm": self.tip_chord_mm,
            "sweepDeg": self.sweep_deg,
            "dihedralDeg": self.dihedral_deg,
            "twistRootDeg": self.twist_root_deg,
            "twistTipDeg": self.twist_tip_deg,
        }


@dataclass(frozen=True, slots=True)
class SpanwiseStation:
    """One spanwise section: leading-edge position, chord, twist, dihedral, profile."""

    span_fraction: float
    leading_edge_mm: tuple[float, float, float]
    chord_mm: float
    twist_deg: float
    dihedral_deg: float
    profile: AirfoilProfile
    local_frame: str | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.span_fraction) or not 0.0 <= self.span_fraction <= 1.0:
            raise ValueError("STATION_SPAN_FRACTION_OUT_OF_RANGE")
        for label, value in (
            ("LEADING_EDGE_X", self.leading_edge_mm[0]),
            ("LEADING_EDGE_Y", self.leading_edge_mm[1]),
            ("LEADING_EDGE_Z", self.leading_edge_mm[2]),
        ):
            _finite(f"STATION_{label}", value)
        if not isfinite(self.chord_mm) or self.chord_mm <= 0.0:
            raise ValueError("STATION_CHORD_MUST_BE_POSITIVE")
        _finite("STATION_TWIST", self.twist_deg)
        _finite("STATION_DIHEDRAL", self.dihedral_deg)

    def place_profile(self, u: float, v: float) -> tuple[float, float, float]:
        """Place normalized profile point ``(u, v)`` in the station local frame."""
        angle = self.twist_deg * pi / 180.0
        x0 = u * self.chord_mm
        y0 = v * self.chord_mm
        x = x0 * cos(angle) - y0 * sin(angle) + self.leading_edge_mm[0]
        y = x0 * sin(angle) + y0 * cos(angle) + self.leading_edge_mm[1]
        return (x, y, self.leading_edge_mm[2])

    def section_loop(self, n_surface: int, n_edge: int) -> tuple[tuple[float, float], ...]:
        return tuple(
            (point[0], point[1]) for point in self.placed_outline(n_surface, n_edge)
        )

    def placed_outline(
        self, n_surface: int, n_edge: int
    ) -> tuple[tuple[float, float, float], ...]:
        return tuple(
            self.place_profile(u, v)
            for u, v in self.profile.outline(n_surface=n_surface, n_edge=n_edge)
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "spanFraction": self.span_fraction,
            "leadingEdgeMm": list(self.leading_edge_mm),
            "chordMm": self.chord_mm,
            "twistDeg": self.twist_deg,
            "dihedralDeg": self.dihedral_deg,
            "localFrame": self.local_frame,
            "profile": self.profile.canonical_payload(),
        }


@dataclass(frozen=True, slots=True)
class LiftingSurface:
    """Deterministic, hashable lifting surface built from spanwise stations."""

    surface_id: str
    role: str
    stations: tuple[SpanwiseStation, ...]
    frame: str
    n_surface: int = DEFAULT_PROFILE_POINTS
    n_edge: int = DEFAULT_EDGE_POINTS
    planform: Planform | None = None

    def __post_init__(self) -> None:
        if not self.surface_id.strip():
            raise ValueError("SURFACE_ID_REQUIRED")
        if not self.frame.strip():
            raise ValueError("SURFACE_FRAME_REQUIRED")
        if self.role not in LIFTING_SURFACE_ROLES:
            raise ValueError(f"UNKNOWN_LIFTING_SURFACE_ROLE:{self.role}")
        if len(self.stations) < 2:
            raise ValueError("SURFACE_REQUIRES_TWO_STATIONS")
        if self.n_surface < 3 or self.n_edge < 2:
            raise ValueError("SURFACE_PROFILE_RESOLUTION_TOO_LOW")
        fractions = [station.span_fraction for station in self.stations]
        if any(later <= earlier for earlier, later in zip(fractions, fractions[1:], strict=False)):
            raise ValueError("SURFACE_STATIONS_MUST_BE_SPAN_ORDERED")
        counts = {
            station.profile.point_count(self.n_surface, self.n_edge)
            for station in self.stations
        }
        if len(counts) != 1:
            raise ValueError("SURFACE_PROFILE_POINT_COUNT_MISMATCH")

    @classmethod
    def from_planform(
        cls,
        surface_id: str,
        role: str,
        planform: Planform,
        profile: AirfoilProfile,
        *,
        frame: str = "surface-local",
        n_stations: int = 5,
        profile_distribution: tuple[AirfoilProfile, ...] | None = None,
        local_frames: tuple[str | None, ...] | None = None,
        n_surface: int = DEFAULT_PROFILE_POINTS,
        n_edge: int = DEFAULT_EDGE_POINTS,
    ) -> LiftingSurface:
        if n_stations < 2:
            raise ValueError("SURFACE_REQUIRES_TWO_STATIONS")
        profiles = profile_distribution or (profile,) * n_stations
        if len(profiles) != n_stations:
            raise ValueError("SURFACE_PROFILE_DISTRIBUTION_LENGTH_MISMATCH")
        frames = local_frames or (None,) * n_stations
        if len(frames) != n_stations:
            raise ValueError("SURFACE_LOCAL_FRAME_LENGTH_MISMATCH")
        stations: list[SpanwiseStation] = []
        for index in range(n_stations):
            fraction = index / (n_stations - 1)
            offset = planform.leading_edge_offset_mm(fraction)
            reach = planform.span_mm * fraction
            stations.append(
                SpanwiseStation(
                    span_fraction=fraction,
                    leading_edge_mm=(offset[0], offset[1], reach),
                    chord_mm=planform.chord_at(fraction),
                    twist_deg=planform.twist_at(fraction),
                    dihedral_deg=planform.dihedral_deg,
                    profile=profiles[index],
                    local_frame=frames[index],
                )
            )
        return cls(
            surface_id=surface_id,
            role=role,
            stations=tuple(stations),
            frame=frame,
            n_surface=n_surface,
            n_edge=n_edge,
            planform=planform,
        )

    @property
    def span_mm(self) -> float:
        reach = [station.leading_edge_mm[2] for station in self.stations]
        return max(reach) - min(reach)

    @property
    def area_mm2(self) -> float:
        ordered = sorted(self.stations, key=lambda station: station.leading_edge_mm[2])
        area = 0.0
        for left, right in zip(ordered, ordered[1:], strict=False):
            dz = abs(right.leading_edge_mm[2] - left.leading_edge_mm[2])
            area += 0.5 * (left.chord_mm + right.chord_mm) * dz
        return area

    @property
    def aspect_ratio(self) -> float:
        area = self.area_mm2
        return 0.0 if area <= 0.0 else self.span_mm**2 / area

    def section_loops(self) -> tuple[tuple[tuple[float, float], ...], ...]:
        return tuple(
            station.section_loop(self.n_surface, self.n_edge) for station in self.stations
        )

    def offsets_mm(self) -> tuple[float, ...]:
        return tuple(station.leading_edge_mm[2] for station in self.stations)

    def _planform(self) -> Planform:
        if self.planform is not None:
            return self.planform
        first, last = self.stations[0], self.stations[-1]
        span = self.span_mm
        return Planform(
            span_mm=span if span > 0.0 else 1.0,
            root_chord_mm=first.chord_mm,
            tip_chord_mm=last.chord_mm,
            sweep_deg=0.0,
            dihedral_deg=last.dihedral_deg,
            twist_root_deg=first.twist_deg,
            twist_tip_deg=last.twist_deg,
        )

    def cad_parameter_defs(self, prefix: str | None = None) -> tuple[ParameterDef, ...]:
        planform = self._planform()
        name = prefix or self.surface_id
        return (
            ParameterDef(f"{name}.span", planform.span_mm, unit="mm"),
            ParameterDef(f"{name}.rootChord", planform.root_chord_mm, unit="mm"),
            ParameterDef(f"{name}.tipChord", planform.tip_chord_mm, unit="mm"),
            ParameterDef(f"{name}.sweep", planform.sweep_deg, unit="deg"),
            ParameterDef(f"{name}.dihedral", planform.dihedral_deg, unit="deg"),
            ParameterDef(f"{name}.twistRoot", planform.twist_root_deg, unit="deg"),
            ParameterDef(f"{name}.twistTip", planform.twist_tip_deg, unit="deg"),
        )

    def parameter_values(self) -> dict[str, float]:
        return {
            definition.name: float(definition.value or 0.0)
            for definition in self.cad_parameter_defs()
        }

    def with_parameters(self, values: dict[str, float]) -> LiftingSurface:
        prefix = self.surface_id
        if not any(name.startswith(f"{prefix}.") for name in values):
            return self
        planform = self._planform()
        updated = replace(
            planform,
            span_mm=values.get(f"{prefix}.span", planform.span_mm),
            root_chord_mm=values.get(f"{prefix}.rootChord", planform.root_chord_mm),
            tip_chord_mm=values.get(f"{prefix}.tipChord", planform.tip_chord_mm),
            sweep_deg=values.get(f"{prefix}.sweep", planform.sweep_deg),
            dihedral_deg=values.get(f"{prefix}.dihedral", planform.dihedral_deg),
            twist_root_deg=values.get(f"{prefix}.twistRoot", planform.twist_root_deg),
            twist_tip_deg=values.get(f"{prefix}.twistTip", planform.twist_tip_deg),
        )
        stations = tuple(
            replace(
                station,
                leading_edge_mm=(
                    *updated.leading_edge_offset_mm(station.span_fraction),
                    updated.span_mm * station.span_fraction,
                ),
                chord_mm=updated.chord_at(station.span_fraction),
                twist_deg=updated.twist_at(station.span_fraction),
                dihedral_deg=updated.dihedral_deg,
            )
            for station in self.stations
        )
        return replace(self, stations=stations, planform=updated)

    def semantic_assignments(self) -> tuple[SemanticAssignment, ...]:
        return tuple(
            SemanticAssignment(
                surface_id=f"{self.surface_id}.{region}",
                semantic_key=f"{self.surface_id}.{region}",
                role=role,
                boundary=boundary,
            )
            for region, role, boundary in SURFACE_BOUNDARY_ROLES
        )

    def semantic_binding(self, component: str) -> SemanticBinding:
        return SemanticBinding(
            semantic_key=f"{self.surface_id}.solid",
            kind="solid_region",
            region=self.surface_id,
            component=component,
        )

    def _grid(self, region: str, points: tuple[Point, ...], nu: int) -> SurfaceGrid:
        return SurfaceGrid(
            grid_id=f"{self.surface_id}.{region}",
            role=region,
            kind="wall",
            nu=nu,
            nv=len(self.stations),
            points=points,
        )

    def seam(self) -> SurfaceSeam:
        """Structured control-grid seam for FFD deformation and meshing."""
        loops = tuple(
            station.placed_outline(self.n_surface, self.n_edge) for station in self.stations
        )
        grids: list[SurfaceGrid] = []
        bspline = self.stations[0].profile.family == "bspline"
        if bspline:
            count = len(loops[0])
            points = tuple(point for loop in loops for point in loop)
            grids.append(
                SurfaceGrid(
                    grid_id=f"{self.surface_id}.shell",
                    role="surface",
                    kind="wall",
                    nu=count,
                    nv=len(self.stations),
                    points=points,
                    closed_u=True,
                )
            )
        else:
            segments = {
                "upper": (0, self.n_surface),
                "trailing_edge": (self.n_surface, self.n_surface + self.n_edge),
                "lower": (
                    self.n_surface + self.n_edge,
                    2 * self.n_surface + self.n_edge,
                ),
                "leading_edge": (
                    2 * self.n_surface + self.n_edge,
                    2 * self.n_surface + 2 * self.n_edge,
                ),
            }
            for region, (start, stop) in segments.items():
                nu = stop - start
                points = tuple(point for loop in loops for point in loop[start:stop])
                grids.append(self._grid(region, points, nu))
        for region, index in (("root", 0), ("tip", -1)):
            grids.append(
                SurfaceGrid(
                    grid_id=f"{self.surface_id}.{region}",
                    role=region,
                    kind="interface" if region == "root" else "wall",
                    nu=len(loops[index]),
                    nv=1,
                    points=loops[index],
                    closed_u=True,
                )
            )
        return SurfaceSeam(seam_id=self.surface_id, domain="solid", grids=tuple(grids))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "surfaceId": self.surface_id,
            "role": self.role,
            "frame": self.frame,
            "nSurface": self.n_surface,
            "nEdge": self.n_edge,
            "planform": None if self.planform is None else self.planform.canonical_payload(),
            "stations": [station.canonical_payload() for station in self.stations],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def lifting_surface_digest(surface: LiftingSurface) -> str:
    """Deterministic SHA-256 identity of a lifting surface."""

    return surface.digest


__all__ = [
    "LIFTING_SURFACE_ROLES",
    "SURFACE_BOUNDARY_ROLES",
    "LiftingSurface",
    "Planform",
    "SpanwiseStation",
    "lifting_surface_digest",
]
