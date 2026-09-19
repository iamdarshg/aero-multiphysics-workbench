"""Generic spanwise blade-section representation.

A section is camber line + thickness distribution + leading/trailing-edge caps,
placed on a spanwise stack by radius/span, chord, stagger, sweep and lean. All
families are deterministic closed-form shapes; no product or application name
appears here. The same section contract serves axial, radial and mixed-flow
machinery.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import cos, isfinite, pi, sin, sqrt
from typing import Any

from aeroworkbench_geometry import ParameterDef

from .body import Point, _quantize

CAMBER_FAMILIES: tuple[str, ...] = ("straight", "parabolic", "sine", "circular_arc")
THICKNESS_FAMILIES: tuple[str, ...] = ("uniform", "elliptic", "sine", "naca4")
STACKING_AXES: tuple[str, ...] = ("radial", "tangential", "axial")

DEFAULT_SURFACE_POINTS = 9
DEFAULT_EDGE_POINTS = 4


def linspace(start: float, stop: float, count: int) -> tuple[float, ...]:
    if count < 2:
        raise ValueError("LINSPACE_NEEDS_AT_LEAST_TWO_POINTS")
    step = (stop - start) / (count - 1)
    return tuple(start + step * index for index in range(count))


def _camber_shape(family: str, u: float) -> float:
    if family == "straight":
        return 0.0
    if family == "parabolic":
        return 4.0 * u * (1.0 - u)
    if family == "sine":
        return sin(pi * u)
    if family == "circular_arc":
        reference = 0.1
        radius = (0.25 + reference * reference) / (2.0 * reference)
        return sqrt(max(radius * radius - (u - 0.5) ** 2, 0.0)) - (radius - reference)
    raise ValueError(f"UNKNOWN_CAMBER_FAMILY:{family}")


@dataclass(frozen=True, slots=True)
class CamberLine:
    """Mean-line camber family with a maximum-camber-to-chord ratio."""

    family: str = "circular_arc"
    camber_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.family not in CAMBER_FAMILIES:
            raise ValueError(f"UNKNOWN_CAMBER_FAMILY:{self.family}")
        if not isfinite(self.camber_ratio) or not 0.0 <= self.camber_ratio <= 0.5:
            raise ValueError("CAMBER_RATIO_OUT_OF_RANGE")

    def offset(self, u: float) -> float:
        peak = _camber_shape("parabolic", 0.5)
        return self.camber_ratio * _camber_shape(self.family, u) / peak


def _thickness_shape(family: str, u: float) -> float:
    if family == "uniform":
        return 1.0
    if family == "elliptic":
        return sqrt(max(1.0 - (2.0 * u - 1.0) ** 2, 0.0))
    if family == "sine":
        return sin(pi * u)
    if family == "naca4":
        return 5.0 * (
            0.2969 * sqrt(u)
            - 0.1260 * u
            - 0.3516 * u * u
            + 0.2843 * u**3
            - 0.1015 * u**4
        )
    raise ValueError(f"UNKNOWN_THICKNESS_FAMILY:{family}")


@dataclass(frozen=True, slots=True)
class ThicknessDistribution:
    """Thickness family with scaling, location and edge thickness controls."""

    family: str = "elliptic"
    thickness_ratio: float = 0.08
    max_thickness_location: float = 0.3
    leading_edge_thickness_ratio: float = 0.006
    trailing_edge_thickness_ratio: float = 0.004

    def __post_init__(self) -> None:
        if self.family not in THICKNESS_FAMILIES:
            raise ValueError(f"UNKNOWN_THICKNESS_FAMILY:{self.family}")
        if not isfinite(self.thickness_ratio) or self.thickness_ratio <= 0.0:
            raise ValueError("THICKNESS_RATIO_MUST_BE_POSITIVE")
        if not 0.0 < self.max_thickness_location < 1.0:
            raise ValueError("MAX_THICKNESS_LOCATION_OUT_OF_RANGE")
        for label, ratio in (
            ("leading", self.leading_edge_thickness_ratio),
            ("trailing", self.trailing_edge_thickness_ratio),
        ):
            if not isfinite(ratio) or ratio < 0.0:
                raise ValueError(f"{label.upper()}_EDGE_THICKNESS_INVALID")

    def half_thickness(self, u: float) -> float:
        peak = _thickness_shape(self.family, self.max_thickness_location)
        if peak <= 1e-9:
            raise ValueError(f"THICKNESS_FAMILY_DEGENERATE:{self.family}")
        shape = _thickness_shape(self.family, u) / peak
        low = self.leading_edge_thickness_ratio / 2.0
        high = self.trailing_edge_thickness_ratio / 2.0
        linear = low + (high - low) * u
        amplitude = self.thickness_ratio / 2.0 - (low + (high - low) * self.max_thickness_location)
        return linear + amplitude * shape


@dataclass(frozen=True, slots=True)
class BladeSection:
    """One spanwise section: profile, chord, stagger and stack offsets."""

    span: float
    radius_mm: float
    chord_mm: float
    stagger_deg: float
    camber: CamberLine = CamberLine()
    thickness: ThicknessDistribution = ThicknessDistribution()
    leading_edge_radius_mm: float = 0.6
    trailing_edge_radius_mm: float = 0.3
    sweep_mm: float = 0.0
    lean_mm: float = 0.0
    stack_offset_mm: float = 0.0
    stacking_axis: str = "radial"

    def __post_init__(self) -> None:
        if not isfinite(self.span) or not 0.0 <= self.span <= 1.0:
            raise ValueError("SECTION_SPAN_OUT_OF_RANGE")
        for label, value in (
            ("radius", self.radius_mm),
            ("chord", self.chord_mm),
            ("leadingEdgeRadius", self.leading_edge_radius_mm),
            ("trailingEdgeRadius", self.trailing_edge_radius_mm),
        ):
            if not isfinite(value):
                raise ValueError(f"SECTION_{label.upper()}_NOT_FINITE")
        if self.radius_mm <= 0.0:
            raise ValueError("SECTION_RADIUS_MUST_BE_POSITIVE")
        if self.chord_mm <= 0.0:
            raise ValueError("SECTION_CHORD_MUST_BE_POSITIVE")
        if self.leading_edge_radius_mm < 0.0 or self.trailing_edge_radius_mm < 0.0:
            raise ValueError("SECTION_EDGE_RADIUS_MUST_NOT_BE_NEGATIVE")
        if not isfinite(self.stagger_deg) or not isfinite(self.sweep_mm) or not isfinite(
            self.lean_mm
        ):
            raise ValueError("SECTION_OFFSET_NOT_FINITE")
        if not isfinite(self.stack_offset_mm):
            raise ValueError("SECTION_STACK_OFFSET_NOT_FINITE")
        if self.stacking_axis not in STACKING_AXES:
            raise ValueError(f"UNKNOWN_STACKING_AXIS:{self.stacking_axis}")

    def canonical(self) -> dict[str, Any]:
        return {
            "span": _quantize(self.span),
            "radiusMm": _quantize(self.radius_mm),
            "chordMm": _quantize(self.chord_mm),
            "staggerDeg": _quantize(self.stagger_deg),
            "camber": {"family": self.camber.family, "ratio": _quantize(self.camber.camber_ratio)},
            "thickness": {
                "family": self.thickness.family,
                "ratio": _quantize(self.thickness.thickness_ratio),
                "maxLocation": _quantize(self.thickness.max_thickness_location),
                "leadingEdgeThickness": _quantize(
                    self.thickness.leading_edge_thickness_ratio
                ),
                "trailingEdgeThickness": _quantize(
                    self.thickness.trailing_edge_thickness_ratio
                ),
            },
            "leadingEdgeRadiusMm": _quantize(self.leading_edge_radius_mm),
            "trailingEdgeRadiusMm": _quantize(self.trailing_edge_radius_mm),
            "sweepMm": _quantize(self.sweep_mm),
            "leanMm": _quantize(self.lean_mm),
            "stackOffsetMm": _quantize(self.stack_offset_mm),
            "stackingAxis": self.stacking_axis,
        }


def section_digest(section: BladeSection) -> str:
    encoded = json.dumps(
        section.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def section_parameters(section: BladeSection, prefix: str) -> tuple[ParameterDef, ...]:
    """Bind a section to named CAD parameters (unit-bearing literal values)."""

    if not prefix.strip():
        raise ValueError("SECTION_PARAMETER_PREFIX_REQUIRED")
    return (
        ParameterDef(f"{prefix}.radius", section.radius_mm, unit="mm"),
        ParameterDef(f"{prefix}.chord", section.chord_mm, unit="mm"),
        ParameterDef(f"{prefix}.stagger", section.stagger_deg, unit="deg"),
        ParameterDef(
            f"{prefix}.thicknessRatio", section.thickness.thickness_ratio,
            unit="dimensionless",
        ),
        ParameterDef(f"{prefix}.camberRatio", section.camber.camber_ratio, unit="dimensionless"),
        ParameterDef(
            f"{prefix}.leadingEdgeRadius", section.leading_edge_radius_mm, unit="mm"
        ),
        ParameterDef(
            f"{prefix}.trailingEdgeRadius", section.trailing_edge_radius_mm, unit="mm"
        ),
        ParameterDef(f"{prefix}.sweep", section.sweep_mm, unit="mm"),
        ParameterDef(f"{prefix}.lean", section.lean_mm, unit="mm"),
        ParameterDef(f"{prefix}.stackOffset", section.stack_offset_mm, unit="mm"),
    )


def section_outline(
    section: BladeSection,
    *,
    n_surface: int = DEFAULT_SURFACE_POINTS,
    n_edge: int = DEFAULT_EDGE_POINTS,
) -> tuple[tuple[float, float], ...]:
    """Return the closed normalized outline ``(u, v)`` in chord fractions.

    Order: upper surface (leading to trailing edge), trailing-edge cap interior,
    lower surface (trailing to leading edge), leading-edge cap interior.
    """

    if n_surface < 3 or n_edge < 2:
        raise ValueError("SECTION_OUTLINE_RESOLUTION_TOO_LOW")
    chord = section.chord_mm
    le_radius = section.leading_edge_radius_mm / chord
    te_radius = section.trailing_edge_radius_mm / chord
    le_half = section.thickness.leading_edge_thickness_ratio / 2.0
    te_half = section.thickness.trailing_edge_thickness_ratio / 2.0
    camber_le = section.camber.offset(0.0)
    camber_te = section.camber.offset(1.0)

    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for u in linspace(0.0, 1.0, n_surface):
        half = section.thickness.half_thickness(u)
        base = section.camber.offset(u)
        upper.append((u, base + half))
        lower.append((u, base - half))

    te_interior: list[tuple[float, float]] = []
    for index in range(1, n_edge + 1):
        angle = pi / 2.0 - pi * index / (n_edge + 1)
        te_interior.append(
            (1.0 + te_radius * cos(angle), camber_te + te_half * sin(angle))
        )

    le_interior: list[tuple[float, float]] = []
    for index in range(1, n_edge + 1):
        angle = 3.0 * pi / 2.0 - pi * index / (n_edge + 1)
        le_interior.append(
            (le_radius * cos(angle), camber_le + le_half * sin(angle))
        )

    points = [*upper, *te_interior, *reversed(lower), *le_interior]
    for previous, current in zip(points, points[1:], strict=False):
        if abs(current[0] - previous[0]) <= 1e-12 and abs(current[1] - previous[1]) <= 1e-12:
            raise ValueError("SECTION_OUTLINE_DEGENERATE")
    if abs(points[0][0] - points[-1][0]) <= 1e-12 and abs(
        points[0][1] - points[-1][1]
    ) <= 1e-12:
        raise ValueError("SECTION_OUTLINE_DEGENERATE")
    return tuple(points)


def section_loop_indices(
    *,
    n_surface: int = DEFAULT_SURFACE_POINTS,
    n_edge: int = DEFAULT_EDGE_POINTS,
) -> dict[str, tuple[int, ...]]:
    """Index ranges of the four outline segments within a section loop.

    Order matches :func:`section_outline`: upper surface, trailing-edge cap,
    lower surface, leading-edge cap.
    """

    if n_surface < 3 or n_edge < 2:
        raise ValueError("SECTION_OUTLINE_RESOLUTION_TOO_LOW")
    lower_start = n_surface + n_edge
    pressure = tuple(range(0, n_surface))
    trailing_edge = tuple([n_surface - 1, *range(n_surface, lower_start), lower_start])
    suction = tuple(range(lower_start, lower_start + n_surface))
    le_start = lower_start + n_surface
    leading_edge = tuple([le_start - 1, *range(le_start, le_start + n_edge), 0])
    return {
        "pressure": pressure,
        "trailing_edge": trailing_edge,
        "suction": suction,
        "leading_edge": leading_edge,
    }


def place_section(
    section: BladeSection,
    *,
    center: Point,
    theta_rad: float,
    meridional_angle_rad: float,
    n_surface: int = DEFAULT_SURFACE_POINTS,
    n_edge: int = DEFAULT_EDGE_POINTS,
    scale: float = 1.0,
) -> tuple[Point, ...]:
    """Place a section loop in world coordinates.

    ``meridional_angle_rad`` is 0 for a purely axial section plane and pi/2 for
    a purely radial one; ``center`` is the section origin on the gas path.
    """

    if not isfinite(theta_rad) or not isfinite(meridional_angle_rad):
        raise ValueError("SECTION_PLACEMENT_ANGLE_NOT_FINITE")
    if scale <= 0.0 or not isfinite(scale):
        raise ValueError("SECTION_SCALE_MUST_BE_POSITIVE")
    er = (cos(theta_rad), sin(theta_rad), 0.0)
    et = (-sin(theta_rad), cos(theta_rad), 0.0)
    ez = (0.0, 0.0, 1.0)
    meridian = tuple(
        cos(meridional_angle_rad) * ez[k] + sin(meridional_angle_rad) * er[k]
        for k in range(3)
    )
    cos_stagger = cos(section.stagger_deg * pi / 180.0)
    sin_stagger = sin(section.stagger_deg * pi / 180.0)
    if section.stacking_axis == "radial":
        stack_vector = er
    elif section.stacking_axis == "tangential":
        stack_vector = et
    else:
        stack_vector = ez
    offset = section.stack_offset_mm
    origin = (
        center[0] + stack_vector[0] * offset,
        center[1] + stack_vector[1] * offset,
        center[2] + stack_vector[2] * offset,
    )
    chord = section.chord_mm * scale
    placed: list[Point] = []
    for u, v in section_outline(section, n_surface=n_surface, n_edge=n_edge):
        chordwise = (u - 0.5) * chord
        normal = v * chord
        along = chordwise * cos_stagger - normal * sin_stagger + section.lean_mm
        across = chordwise * sin_stagger + normal * cos_stagger + section.sweep_mm
        placed.append(
            (
                origin[0] + meridian[0] * along + et[0] * across,
                origin[1] + meridian[1] * along + et[1] * across,
                origin[2] + meridian[2] * along + et[2] * across,
            )
        )
    return tuple(placed)
