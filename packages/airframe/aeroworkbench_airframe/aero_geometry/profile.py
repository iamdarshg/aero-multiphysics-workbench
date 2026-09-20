"""Generic two-dimensional aerodynamic profile contract.

A profile is a deterministic, unit-bearing, hashable closed curve expressed in
normalized chord fractions ``(u, v)``: ``u`` runs from the leading edge (0) to
the trailing edge (1), ``v`` is the normal/surface offset as a fraction of
chord. Five representation families are supported so imported data, a NACA
seam, CST coefficients, a spline/B-spline fit, and a closed-form camber/thickness
family all share one contract:

- ``parametric`` : camber line + thickness distribution;
- ``naca4``      : NACA four-digit thickness seam over a cambered mean line;
- ``cst``        : class-shape-transformation Bernstein coefficients;
- ``imported``   : explicit upper/lower coordinate polylines (linear);
- ``bspline``    : closed uniform cubic B-spline through control points.

Only closed-form math and explicit data are used; no CAD kernel is needed to
sample a profile. :meth:`AirfoilProfile.to_blade_section` exposes the same
profile through the shared turbomachinery spanwise-section primitive at
runtime. Native solids are produced by the shared parametric CAD layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb, cos, isfinite, pi, sin, sqrt
from typing import Any

from ..canonical import content_digest

PROFILE_FAMILIES: tuple[str, ...] = ("parametric", "naca4", "cst", "imported", "bspline")
CAMBER_FAMILIES: tuple[str, ...] = ("straight", "parabolic", "sine", "circular_arc")
THICKNESS_FAMILIES: tuple[str, ...] = ("uniform", "elliptic", "sine", "naca4")

DEFAULT_PROFILE_POINTS = 17
DEFAULT_EDGE_POINTS = 4
_MIN_EDGE_HALF = 1e-4


def linspace(start: float, stop: float, count: int) -> tuple[float, ...]:
    if count < 2:
        raise ValueError("LINSPACE_NEEDS_AT_LEAST_TWO_POINTS")
    step = (stop - start) / (count - 1)
    return tuple(start + step * index for index in range(count))


def _positive(label: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise ValueError(f"PROFILE_{label}_MUST_BE_POSITIVE")


def _non_negative(label: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise ValueError(f"PROFILE_{label}_MUST_NOT_BE_NEGATIVE")


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


def _bernstein(index: int, degree: int, u: float) -> float:
    return float(comb(degree, index)) * u**index * (1.0 - u) ** (degree - index)


def _cst_surface(coefficients: tuple[float, ...], u: float) -> float:
    degree = len(coefficients) - 1
    shape = sum(
        coefficient * _bernstein(index, degree, u)
        for index, coefficient in enumerate(coefficients)
    )
    return sqrt(u) * (1.0 - u) * shape


def _linear_interp(points: tuple[tuple[float, float], ...], u: float) -> float:
    clamped = min(max(u, points[0][0]), points[-1][0])
    for (u0, v0), (u1, v1) in zip(points, points[1:], strict=False):
        if u0 <= clamped <= u1:
            if u1 - u0 <= 1e-12:
                return 0.5 * (v0 + v1)
            weight = (clamped - u0) / (u1 - u0)
            return v0 + weight * (v1 - v0)
    return points[-1][1]


def _closed_bspline(
    controls: tuple[tuple[float, float], ...], samples: int
) -> tuple[tuple[float, float], ...]:
    count = len(controls)
    result: list[tuple[float, float]] = []
    for step in range(samples):
        location = (step / samples) * count
        segment = int(location) % count
        local = location - int(location)
        p0 = controls[(segment - 1) % count]
        p1 = controls[segment]
        p2 = controls[(segment + 1) % count]
        p3 = controls[(segment + 2) % count]
        b0 = (-local**3 + 3.0 * local**2 - 3.0 * local + 1.0) / 6.0
        b1 = (3.0 * local**3 - 6.0 * local**2 + 4.0) / 6.0
        b2 = (-3.0 * local**3 + 3.0 * local**2 + 3.0 * local + 1.0) / 6.0
        b3 = local**3 / 6.0
        result.append(
            (
                b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0],
                b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1],
            )
        )
    return tuple(result)


def _assemble_loop(
    upper: tuple[tuple[float, float], ...],
    lower: tuple[tuple[float, float], ...],
    *,
    n_edge: int,
    leading_edge_radius: float,
    trailing_edge_radius: float,
    leading_half: float,
    trailing_half: float,
) -> tuple[tuple[float, float], ...]:
    leading_camber = 0.5 * (upper[0][1] + lower[0][1])
    trailing_camber = 0.5 * (upper[-1][1] + lower[-1][1])
    trailing_cap = tuple(
        (
            1.0 + trailing_edge_radius * cos(angle),
            trailing_camber + trailing_half * sin(angle),
        )
        for angle in (
            pi / 2.0 - pi * index / (n_edge + 1) for index in range(1, n_edge + 1)
        )
    )
    leading_cap = tuple(
        (
            leading_edge_radius * cos(angle),
            leading_camber + leading_half * sin(angle),
        )
        for angle in (
            3.0 * pi / 2.0 - pi * index / (n_edge + 1) for index in range(1, n_edge + 1)
        )
    )
    points = (*upper, *trailing_cap, *reversed(lower), *leading_cap)
    for previous, current in zip(points, points[1:], strict=False):
        if abs(current[0] - previous[0]) <= 1e-12 and abs(current[1] - previous[1]) <= 1e-12:
            raise ValueError("PROFILE_OUTLINE_DEGENERATE")
    return tuple(points)


@dataclass(frozen=True, slots=True)
class AirfoilProfile:
    """Unit-safe, hashable two-dimensional profile in chord fractions."""

    family: str = "parametric"
    thickness_ratio: float = 0.12
    camber_ratio: float = 0.0
    camber_position: float = 0.4
    thickness_family: str = "naca4"
    camber_family: str = "circular_arc"
    max_thickness_location: float = 0.3
    leading_edge_thickness_ratio: float = 0.006
    trailing_edge_thickness_ratio: float = 0.004
    leading_edge_radius_ratio: float = 0.02
    trailing_edge_radius_ratio: float = 0.01
    upper_coordinates: tuple[tuple[float, float], ...] = ()
    lower_coordinates: tuple[tuple[float, float], ...] = ()
    cst_upper: tuple[float, ...] = ()
    cst_lower: tuple[float, ...] = ()
    spline_controls: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        if self.family not in PROFILE_FAMILIES:
            raise ValueError(f"UNKNOWN_PROFILE_FAMILY:{self.family}")
        _positive("THICKNESS_RATIO", self.thickness_ratio)
        if not isfinite(self.camber_ratio) or not 0.0 <= self.camber_ratio <= 0.5:
            raise ValueError("PROFILE_CAMBER_RATIO_OUT_OF_RANGE")
        if not isfinite(self.camber_position) or not 0.0 < self.camber_position < 1.0:
            raise ValueError("PROFILE_CAMBER_POSITION_OUT_OF_RANGE")
        if not isfinite(self.max_thickness_location) or not 0.0 < self.max_thickness_location < 1.0:
            raise ValueError("PROFILE_MAX_THICKNESS_LOCATION_OUT_OF_RANGE")
        _non_negative("LEADING_EDGE_THICKNESS_RATIO", self.leading_edge_thickness_ratio)
        _non_negative("TRAILING_EDGE_THICKNESS_RATIO", self.trailing_edge_thickness_ratio)
        _non_negative("LEADING_EDGE_RADIUS_RATIO", self.leading_edge_radius_ratio)
        _non_negative("TRAILING_EDGE_RADIUS_RATIO", self.trailing_edge_radius_ratio)
        if self.family in ("parametric", "naca4"):
            if self.thickness_family not in THICKNESS_FAMILIES:
                raise ValueError(f"UNKNOWN_THICKNESS_FAMILY:{self.thickness_family}")
            if self.camber_family not in CAMBER_FAMILIES:
                raise ValueError(f"UNKNOWN_CAMBER_FAMILY:{self.camber_family}")
        if self.family == "imported":
            for label, coordinates in (
                ("UPPER", self.upper_coordinates),
                ("LOWER", self.lower_coordinates),
            ):
                if len(coordinates) < 2:
                    raise ValueError(f"PROFILE_{label}_COORDINATES_REQUIRE_TWO_POINTS")
                for (u0, _), (u1, _) in zip(coordinates, coordinates[1:], strict=False):
                    if u1 <= u0:
                        raise ValueError(f"PROFILE_{label}_COORDINATES_NOT_MONOTONE")
        if self.family == "cst":
            if len(self.cst_upper) < 2:
                raise ValueError("PROFILE_CST_UPPER_REQUIRES_TWO_COEFFICIENTS")
            if len(self.cst_lower) < 2:
                raise ValueError("PROFILE_CST_LOWER_REQUIRES_TWO_COEFFICIENTS")
        if self.family == "bspline" and len(self.spline_controls) < 4:
            raise ValueError("PROFILE_BSPLINE_REQUIRES_FOUR_CONTROL_POINTS")
        if (
            self.family in ("cst", "imported")
            and self.leading_edge_thickness_ratio <= 0.0
            and self.trailing_edge_thickness_ratio <= 0.0
        ):
            raise ValueError("PROFILE_GENERATED_FAMILY_NEEDS_EDGE_THICKNESS")

    def _camber_offset(self, u: float) -> float:
        if self.camber_ratio == 0.0:
            return 0.0
        peak = _camber_shape("parabolic", 0.5)
        return self.camber_ratio * _camber_shape(self.camber_family, u) / peak

    def _half_thickness(self, u: float) -> float:
        peak = _thickness_shape(self.thickness_family, self.max_thickness_location)
        if peak <= 1e-9:
            raise ValueError(f"THICKNESS_FAMILY_DEGENERATE:{self.thickness_family}")
        shape = _thickness_shape(self.thickness_family, u) / peak
        low = self.leading_edge_thickness_ratio / 2.0
        high = self.trailing_edge_thickness_ratio / 2.0
        linear = low + (high - low) * u
        amplitude = self.thickness_ratio / 2.0 - (low + (high - low) * self.max_thickness_location)
        return linear + amplitude * shape

    def _edge_thickness(self, u: float) -> float:
        leading = self.leading_edge_thickness_ratio / 2.0
        trailing = self.trailing_edge_thickness_ratio / 2.0
        return leading + (trailing - leading) * u

    def _raw_surfaces(self, u: float) -> tuple[float, float]:
        if self.family == "cst":
            return (_cst_surface(self.cst_upper, u), _cst_surface(self.cst_lower, u))
        if self.family == "imported":
            return (
                _linear_interp(self.upper_coordinates, u),
                _linear_interp(self.lower_coordinates, u),
            )
        raise ValueError("PROFILE_BSPLINE_HAS_NO_SEPARATE_SURFACES")

    def _blended(self, u: float) -> tuple[float, float]:
        raw_upper, raw_lower = self._raw_surfaces(u)
        camber = 0.5 * (raw_upper + raw_lower)
        half = max(0.5 * (raw_upper - raw_lower), self._edge_thickness(u), _MIN_EDGE_HALF)
        return (camber + half, camber - half)

    def upper(self, u: float) -> float:
        """Normalized upper-surface offset at chord fraction ``u``."""
        if self.family in ("parametric", "naca4"):
            return self._camber_offset(u) + self._half_thickness(u)
        return self._blended(u)[0]

    def lower(self, u: float) -> float:
        """Normalized lower-surface offset at chord fraction ``u``."""
        if self.family in ("parametric", "naca4"):
            return self._camber_offset(u) - self._half_thickness(u)
        return self._blended(u)[1]

    def to_blade_section(self, chord_mm: float = 1.0) -> Any:
        """Expose this profile through the shared spanwise-section primitive."""
        if self.family not in ("parametric", "naca4"):
            raise ValueError("PROFILE_TO_BLADE_SECTION_NEEDS_CAMBER_THICKNESS_FAMILY")
        from aeroworkbench_turbomachinery.geometry.sections import (  # type: ignore[import-not-found, unused-ignore]  # noqa: E501
            BladeSection,
            CamberLine,
            ThicknessDistribution,
        )

        if self.family == "naca4":
            thickness_family = "naca4"
            camber_family = "parabolic"
        else:
            thickness_family = self.thickness_family
            camber_family = self.camber_family
        return BladeSection(
            span=0.0,
            radius_mm=1.0,
            chord_mm=chord_mm,
            stagger_deg=0.0,
            camber=CamberLine(family=camber_family, camber_ratio=self.camber_ratio),
            thickness=ThicknessDistribution(
                family=thickness_family,
                thickness_ratio=self.thickness_ratio,
                max_thickness_location=self.max_thickness_location,
                leading_edge_thickness_ratio=self.leading_edge_thickness_ratio,
                trailing_edge_thickness_ratio=self.trailing_edge_thickness_ratio,
            ),
            leading_edge_radius_mm=self.leading_edge_radius_ratio,
            trailing_edge_radius_mm=self.trailing_edge_radius_ratio,
        )

    def point_count(
        self,
        n_surface: int = DEFAULT_PROFILE_POINTS,
        n_edge: int = DEFAULT_EDGE_POINTS,
    ) -> int:
        return 2 * n_surface + 2 * n_edge

    def outline(
        self,
        n_surface: int = DEFAULT_PROFILE_POINTS,
        n_edge: int = DEFAULT_EDGE_POINTS,
    ) -> tuple[tuple[float, float], ...]:
        """Closed normalized loop: upper, trailing cap, lower, leading cap."""
        if n_surface < 3 or n_edge < 2:
            raise ValueError("PROFILE_OUTLINE_RESOLUTION_TOO_LOW")
        if self.family == "bspline":
            return _closed_bspline(
                self.spline_controls, self.point_count(n_surface, n_edge)
            )
        samples = linspace(0.0, 1.0, n_surface)
        upper = tuple((u, self.upper(u)) for u in samples)
        lower = tuple((u, self.lower(u)) for u in samples)
        return _assemble_loop(
            upper,
            lower,
            n_edge=n_edge,
            leading_edge_radius=self.leading_edge_radius_ratio,
            trailing_edge_radius=self.trailing_edge_radius_ratio,
            leading_half=self.leading_edge_thickness_ratio / 2.0,
            trailing_half=self.trailing_edge_thickness_ratio / 2.0,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "thicknessRatio": self.thickness_ratio,
            "camberRatio": self.camber_ratio,
            "camberPosition": self.camber_position,
            "thicknessFamily": self.thickness_family,
            "camberFamily": self.camber_family,
            "maxThicknessLocation": self.max_thickness_location,
            "leadingEdgeThicknessRatio": self.leading_edge_thickness_ratio,
            "trailingEdgeThicknessRatio": self.trailing_edge_thickness_ratio,
            "leadingEdgeRadiusRatio": self.leading_edge_radius_ratio,
            "trailingEdgeRadiusRatio": self.trailing_edge_radius_ratio,
            "upperCoordinates": [[u, v] for u, v in self.upper_coordinates],
            "lowerCoordinates": [[u, v] for u, v in self.lower_coordinates],
            "cstUpper": list(self.cst_upper),
            "cstLower": list(self.cst_lower),
            "splineControls": [[u, v] for u, v in self.spline_controls],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def profile_digest(profile: AirfoilProfile) -> str:
    """Deterministic SHA-256 identity of a profile contract."""

    return profile.digest


__all__ = [
    "CAMBER_FAMILIES",
    "DEFAULT_EDGE_POINTS",
    "DEFAULT_PROFILE_POINTS",
    "PROFILE_FAMILIES",
    "THICKNESS_FAMILIES",
    "AirfoilProfile",
    "linspace",
    "profile_digest",
]
