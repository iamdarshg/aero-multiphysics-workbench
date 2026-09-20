"""External-aerodynamics case: lifting surfaces, controls, and section seams.

An :class:`ExternalAeroCase` binds the AIRFRAME 02 geometry primitives to the
2-D section seam. The aerodynamic frame used by the solver is explicit:
``x`` is streamwise (chordwise), ``y`` is spanwise, ``z`` is up. The AIRFRAME
generic station stores ``leading_edge_mm = (chordwise, vertical, spanwise)``, so
the mapping is ``x = le[0]``, ``y = le[2]``, ``z = le[1]`` with millimetres
converted to metres.

A geometry-derived :class:`GeometryReference` (area, span, mean chord, moment
reference) is computed from the declared stations; an explicit override may be
supplied when a project convention differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, isfinite, pi, sin

from ..aero_geometry import ControlSurface, LiftingSurface, SpanwiseStation
from ..canonical import content_digest
from .errors import ExternalAeroValidationError
from .polar import (
    ProfilePolar,
    SectionModel,
    TabulatedPolarSection,
    ThinAirfoilSection,
)

MM_TO_M = 1e-3
SYMMETRY_MODES: tuple[str, ...] = ("mirror", "none")


@dataclass(frozen=True, slots=True)
class GeometryReference:
    """Geometry-only reference quantities (no atmosphere)."""

    area_m2: float
    span_m: float
    mean_chord_m: float
    moment_reference_m: tuple[float, float, float]

    def __post_init__(self) -> None:
        for label, value in (
            ("AREA", self.area_m2),
            ("SPAN", self.span_m),
            ("MEAN_CHORD", self.mean_chord_m),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ExternalAeroValidationError(f"GEOMETRY_REFERENCE_{label}_NOT_POSITIVE")
        if not all(isfinite(value) for value in self.moment_reference_m):
            raise ExternalAeroValidationError("GEOMETRY_REFERENCE_MOMENT_POINT_NOT_FINITE")

    def canonical(self) -> dict[str, object]:
        return {
            "areaM2": self.area_m2,
            "spanM": self.span_m,
            "meanChordM": self.mean_chord_m,
            "momentReferenceM": list(self.moment_reference_m),
        }


def station_aero(station: SpanwiseStation) -> tuple[float, float, float]:
    """Return ``(x_streamwise_m, y_span_m, z_up_m)`` for a leading-edge station."""

    return (
        station.leading_edge_mm[0] * MM_TO_M,
        station.leading_edge_mm[2] * MM_TO_M,
        station.leading_edge_mm[1] * MM_TO_M,
    )


def control_effectiveness(hinge_fraction: float) -> float:
    """Thin-airfoil trailing-edge-flap effectiveness ``dalpha_eff/ddelta``."""

    if not isfinite(hinge_fraction) or not 0.0 < hinge_fraction < 1.0:
        raise ExternalAeroValidationError("CONTROL_HINGE_FRACTION_INVALID")
    theta = acos(1.0 - 2.0 * hinge_fraction)
    return (pi - theta + sin(theta)) / pi


@dataclass(frozen=True, slots=True)
class ExternalAeroCase:
    """A deterministic, hashable external-aerodynamics case definition."""

    case_id: str
    surfaces: tuple[LiftingSurface, ...]
    controls: tuple[ControlSurface, ...] = ()
    symmetry: str = "mirror"
    section_polars: tuple[tuple[str, ProfilePolar], ...] = ()
    section_profile_drag: tuple[tuple[str, float], ...] = ()
    reference: GeometryReference | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ExternalAeroValidationError("CASE_ID_REQUIRED")
        if not self.surfaces:
            raise ExternalAeroValidationError("CASE_REQUIRES_AT_LEAST_ONE_SURFACE")
        if self.symmetry not in SYMMETRY_MODES:
            raise ExternalAeroValidationError(f"UNKNOWN_SYMMETRY_MODE:{self.symmetry}")
        ids = [surface.surface_id for surface in self.surfaces]
        if len(set(ids)) != len(ids):
            raise ExternalAeroValidationError("CASE_SURFACE_IDS_NOT_UNIQUE")
        known = set(ids)
        for control in self.controls:
            if control.parent_id not in known:
                raise ExternalAeroValidationError(
                    f"CASE_CONTROL_PARENT_UNKNOWN:{control.control_id}:{control.parent_id}"
                )
        for surface_id, _ in self.section_polars:
            if surface_id not in known:
                raise ExternalAeroValidationError(f"CASE_POLAR_SURFACE_UNKNOWN:{surface_id}")
        for surface_id, drag in self.section_profile_drag:
            if surface_id not in known:
                raise ExternalAeroValidationError(f"CASE_DRAG_SURFACE_UNKNOWN:{surface_id}")
            if not isfinite(drag) or drag < 0.0:
                raise ExternalAeroValidationError(f"CASE_SECTION_DRAG_INVALID:{surface_id}")

    def surface(self, surface_id: str) -> LiftingSurface:
        for surface in self.surfaces:
            if surface.surface_id == surface_id:
                return surface
        raise ExternalAeroValidationError(f"UNKNOWN_SURFACE:{surface_id}")

    def _polar(self, surface_id: str) -> ProfilePolar | None:
        for name, polar in self.section_polars:
            if name == surface_id:
                return polar
        return None

    def _profile_drag(self, surface_id: str) -> float:
        for name, drag in self.section_profile_drag:
            if name == surface_id:
                return drag
        return 0.0

    def section_model(self, surface_id: str) -> SectionModel:
        polar = self._polar(surface_id)
        if polar is not None:
            return TabulatedPolarSection(polar=polar)
        profile = self.surface(surface_id).stations[0].profile
        return ThinAirfoilSection(profile=profile, profile_drag=self._profile_drag(surface_id))

    def controls_for(self, surface_id: str) -> tuple[ControlSurface, ...]:
        return tuple(control for control in self.controls if control.parent_id == surface_id)

    def geometry_reference(self) -> GeometryReference:
        if self.reference is not None:
            return self.reference
        return derive_geometry_reference(self)

    def canonical(self) -> dict[str, object]:
        return {
            "caseId": self.case_id,
            "symmetry": self.symmetry,
            "reference": self.geometry_reference().canonical(),
            "surfaces": [surface.canonical_payload() for surface in self.surfaces],
            "controls": [control.canonical_payload() for control in self.controls],
            "sectionPolars": [
                {"surfaceId": name, "polar": polar.canonical()}
                for name, polar in self.section_polars
            ],
            "sectionProfileDrag": [
                {"surfaceId": name, "drag": value}
                for name, value in self.section_profile_drag
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def _strip_metrics(surface: LiftingSurface) -> list[tuple[float, float, float]]:
    """Per-strip ``(width_m, chord_mid_m, quarter_chord_x_m)`` in aerodynamic axes."""

    strips: list[tuple[float, float, float]] = []
    for left, right in zip(surface.stations, surface.stations[1:], strict=False):
        y_left = station_aero(left)[1]
        y_right = station_aero(right)[1]
        width = abs(y_right - y_left)
        chord_mid = 0.5 * (left.chord_mm + right.chord_mm) * MM_TO_M
        qc_x = 0.5 * (
            station_aero(left)[0] + 0.25 * left.chord_mm * MM_TO_M
            + station_aero(right)[0] + 0.25 * right.chord_mm * MM_TO_M
        )
        strips.append((width, chord_mid, qc_x))
    return strips


def derive_geometry_reference(case: ExternalAeroCase) -> GeometryReference:
    """Derive area/span/mean-chord/moment point from the declared stations."""

    mirror = 2.0 if case.symmetry == "mirror" else 1.0
    area = 0.0
    weighted_qc = 0.0
    weighted_width = 0.0
    y_values: list[float] = []
    for surface in case.surfaces:
        for station in surface.stations:
            y_values.append(station_aero(station)[1])
        for width, chord_mid, qc_x in _strip_metrics(surface):
            area += width * chord_mid
            weighted_qc += width * qc_x
            weighted_width += width
    area *= mirror
    if area <= 0.0 or weighted_width <= 0.0:
        raise ExternalAeroValidationError("CASE_GEOMETRY_HAS_NO_AREA")
    span = (max(y_values) - min(y_values)) * mirror
    if span <= 0.0:
        raise ExternalAeroValidationError("CASE_GEOMETRY_HAS_NO_SPAN")
    mean_chord = area / span
    moment_x = weighted_qc / weighted_width
    return GeometryReference(
        area_m2=area,
        span_m=span,
        mean_chord_m=mean_chord,
        moment_reference_m=(moment_x, 0.0, 0.0),
    )


def control_alpha_increment_deg(
    case: ExternalAeroCase,
    surface_id: str,
    span_fraction: float,
    deflections: tuple[tuple[str, float], ...] | None = None,
) -> float:
    """Effective angle increment at one span fraction from all deployed controls."""

    increments: dict[str, float] = dict(deflections) if deflections else {}
    total = 0.0
    for control in case.controls_for(surface_id):
        start, end = control.span_fraction
        if not start <= span_fraction <= end:
            continue
        deflection = increments.get(control.control_id, control.deflection_deg)
        total += control_effectiveness(control.hinge_fraction) * deflection
    return total


def interpolate_stations(
    surface: LiftingSurface, fraction: float
) -> tuple[tuple[float, float, float], float, float, float, SpanwiseStation]:
    """Linearly interpolate ``(le_aero, chord_m, twist_deg, dihedral_deg, station)``."""

    if not isfinite(fraction) or not 0.0 <= fraction <= 1.0:
        raise ExternalAeroValidationError("SPAN_FRACTION_OUT_OF_RANGE")
    stations = surface.stations
    for lower, upper in zip(stations, stations[1:], strict=False):
        if lower.span_fraction <= fraction <= upper.span_fraction:
            span = upper.span_fraction - lower.span_fraction
            weight = 0.0 if span <= 0.0 else (fraction - lower.span_fraction) / span
            le: tuple[float, float, float] = (
                lower.leading_edge_mm[0]
                + weight * (upper.leading_edge_mm[0] - lower.leading_edge_mm[0]),
                lower.leading_edge_mm[1]
                + weight * (upper.leading_edge_mm[1] - lower.leading_edge_mm[1]),
                lower.leading_edge_mm[2]
                + weight * (upper.leading_edge_mm[2] - lower.leading_edge_mm[2]),
            )
            chord = lower.chord_mm + weight * (upper.chord_mm - lower.chord_mm)
            twist = lower.twist_deg + weight * (upper.twist_deg - lower.twist_deg)
            dihedral = lower.dihedral_deg + weight * (upper.dihedral_deg - lower.dihedral_deg)
            return (le, chord, twist, dihedral, lower)
    last = stations[-1]
    return (
        last.leading_edge_mm,
        last.chord_mm,
        last.twist_deg,
        last.dihedral_deg,
        last,
    )


def cosine_fractions(panels: int) -> tuple[float, ...]:
    """Cosine-clustered span fractions in ``[0, 1]`` (deterministic)."""

    if panels < 1:
        raise ExternalAeroValidationError("PANEL_COUNT_MUST_BE_POSITIVE")
    return tuple(0.5 * (1.0 - cos(pi * index / panels)) for index in range(panels + 1))


__all__ = [
    "MM_TO_M",
    "SYMMETRY_MODES",
    "ExternalAeroCase",
    "GeometryReference",
    "control_alpha_increment_deg",
    "control_effectiveness",
    "cosine_fractions",
    "derive_geometry_reference",
    "interpolate_stations",
    "station_aero",
]
