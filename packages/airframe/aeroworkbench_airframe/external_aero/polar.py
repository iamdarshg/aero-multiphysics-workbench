"""Two-dimensional profile-polar input seam and section lift/drag/moment models.

A :class:`ProfilePolar` is the explicit seam for externally supplied 2-D polar
data (experiment, a panel method, or a vendor deck). A
:class:`ThinAirfoilSection` is the closed-form section model derived from an
:class:`AirfoilProfile` with thin-airfoil theory: its zero-lift angle, lift-curve
slope and quarter-chord pitching moment come from the camber line by numerical
quadrature (deterministic, fixed sample count), never from a lookup of a
product-specific coefficient table.

Both satisfy the :class:`SectionModel` contract the vortex-lattice solver reads,
so switching from a closed-form section to measured polar data changes only the
seam, not the solver.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import cos, isfinite, pi
from typing import Protocol, runtime_checkable

from ..aero_geometry import AirfoilProfile
from .errors import ExternalAeroValidationError, ExternalAeroValidityError

_THIN_AIRFOIL_SAMPLES = 64
_DEFAULT_SLOPE_PER_RAD = 2.0 * pi


@dataclass(frozen=True, slots=True)
class SectionCoefficients:
    """A section lift/drag/moment triple at one angle of attack."""

    lift: float
    drag: float
    moment: float = 0.0

    def __post_init__(self) -> None:
        for label, value in (
            ("LIFT", self.lift),
            ("DRAG", self.drag),
            ("MOMENT", self.moment),
        ):
            if not isfinite(value):
                raise ExternalAeroValidationError(f"SECTION_COEFFICIENT_{label}_NOT_FINITE")

    def canonical(self) -> dict[str, float]:
        return {"cl": self.lift, "cd": self.drag, "cm": self.moment}


@dataclass(frozen=True, slots=True)
class PolarPoint:
    """One measured/computed point of a two-dimensional profile polar."""

    alpha_deg: float
    lift: float
    drag: float
    moment: float = 0.0

    def __post_init__(self) -> None:
        for label, value in (
            ("ALPHA", self.alpha_deg),
            ("LIFT", self.lift),
            ("DRAG", self.drag),
            ("MOMENT", self.moment),
        ):
            if not isfinite(value):
                raise ExternalAeroValidationError(f"POLAR_POINT_{label}_NOT_FINITE")


@dataclass(frozen=True, slots=True)
class ProfilePolar:
    """Declared 2-D profile polar with a Reynolds/Mach validity label."""

    polar_id: str
    points: tuple[PolarPoint, ...]
    reynolds_number: float | None = None
    mach_number: float | None = None
    source: str = "declared"

    def __post_init__(self) -> None:
        if not self.polar_id.strip() or not self.source.strip():
            raise ExternalAeroValidationError("POLAR_IDENTITY_REQUIRED")
        if len(self.points) < 2:
            raise ExternalAeroValidationError("POLAR_REQUIRES_TWO_POINTS")
        for earlier, later in zip(self.points, self.points[1:], strict=False):
            if later.alpha_deg <= earlier.alpha_deg:
                raise ExternalAeroValidationError("POLAR_ALPHA_NOT_STRICTLY_INCREASING")
        for label, value in (
            ("REYNOLDS", self.reynolds_number),
            ("MACH", self.mach_number),
        ):
            if value is not None and (not isfinite(value) or value < 0.0):
                raise ExternalAeroValidationError(f"POLAR_{label}_INVALID")

    def _bracket(self, alpha_deg: float) -> tuple[PolarPoint, PolarPoint]:
        if not self.points[0].alpha_deg <= alpha_deg <= self.points[-1].alpha_deg:
            raise ExternalAeroValidityError(
                f"POLAR_ALPHA_OUT_OF_RANGE:{self.polar_id}:{alpha_deg}"
            )
        for lower, upper in zip(self.points, self.points[1:], strict=False):
            if lower.alpha_deg <= alpha_deg <= upper.alpha_deg:
                return lower, upper
        raise ExternalAeroValidityError(f"POLAR_ALPHA_OUT_OF_RANGE:{self.polar_id}")

    def section(self, alpha_deg: float) -> SectionCoefficients:
        lower, upper = self._bracket(alpha_deg)
        span = upper.alpha_deg - lower.alpha_deg
        if span <= 0.0:
            return SectionCoefficients(lower.lift, lower.drag, lower.moment)
        weight = (alpha_deg - lower.alpha_deg) / span
        return SectionCoefficients(
            lift=lower.lift + weight * (upper.lift - lower.lift),
            drag=lower.drag + weight * (upper.drag - lower.drag),
            moment=lower.moment + weight * (upper.moment - lower.moment),
        )

    def zero_lift_angle_deg(self) -> float:
        for lower, upper in zip(self.points, self.points[1:], strict=False):
            if lower.lift == 0.0:
                return lower.alpha_deg
            if lower.lift * upper.lift < 0.0:
                weight = lower.lift / (lower.lift - upper.lift)
                return lower.alpha_deg + weight * (upper.alpha_deg - lower.alpha_deg)
        raise ExternalAeroValidationError(f"POLAR_HAS_NO_ZERO_LIFT_CROSSING:{self.polar_id}")

    def lift_curve_slope_per_rad(self) -> float:
        lower, upper = self._bracket(0.0)
        span_deg = upper.alpha_deg - lower.alpha_deg
        if span_deg <= 0.0:
            return _DEFAULT_SLOPE_PER_RAD
        return (upper.lift - lower.lift) / span_deg * 180.0 / pi

    def quarter_chord_moment_coefficient(self) -> float:
        return self.section(self.zero_lift_angle_deg()).moment

    def profile_drag_coefficient(self, lift: float) -> float:
        ordered = sorted(self.points, key=lambda point: point.lift)
        if lift <= ordered[0].lift:
            return ordered[0].drag
        if lift >= ordered[-1].lift:
            return ordered[-1].drag
        for lower, upper in zip(ordered, ordered[1:], strict=False):
            if lower.lift <= lift <= upper.lift:
                span = upper.lift - lower.lift
                if span <= 0.0:
                    return lower.drag
                weight = (lift - lower.lift) / span
                return lower.drag + weight * (upper.drag - lower.drag)
        return ordered[-1].drag

    def canonical(self) -> dict[str, object]:
        return {
            "polarId": self.polar_id,
            "reynoldsNumber": self.reynolds_number,
            "machNumber": self.mach_number,
            "source": self.source,
            "points": [
                {
                    "alphaDeg": point.alpha_deg,
                    "cl": point.lift,
                    "cd": point.drag,
                    "cm": point.moment,
                }
                for point in self.points
            ],
        }


@runtime_checkable
class SectionModel(Protocol):
    """The section contract the vortex-lattice solver reads."""

    @property
    def zero_lift_angle_deg(self) -> float: ...

    @property
    def lift_curve_slope_per_rad(self) -> float: ...

    def profile_drag_coefficient(self, lift: float) -> float: ...

    def quarter_chord_moment_coefficient(self) -> float: ...


def _camber_line(profile: AirfoilProfile, u: float) -> float:
    return 0.5 * (profile.upper(u) + profile.lower(u))


def _camber_slope(profile: AirfoilProfile, u: float) -> float:
    step = 1e-4
    lower = max(0.0, u - step)
    upper = min(1.0, u + step)
    span = upper - lower
    if span <= 0.0:
        return 0.0
    return (_camber_line(profile, upper) - _camber_line(profile, lower)) / span


def _thin_airfoil_fourier(profile: AirfoilProfile) -> tuple[float, float, float]:
    """Return ``(alpha_l0_rad, A1, A2)`` for the camber line (midpoint rule)."""

    samples = _THIN_AIRFOIL_SAMPLES
    constant = 0.0
    first = 0.0
    second = 0.0
    for index in range(samples):
        theta = pi * (index + 0.5) / samples
        u = 0.5 * (1.0 - cos(theta))
        slope = _camber_slope(profile, u)
        constant += slope * (cos(theta) - 1.0)
        first += slope * cos(theta)
        second += slope * cos(2.0 * theta)
    alpha_l0 = -(constant / samples)
    a1 = 2.0 * first / samples
    a2 = 2.0 * second / samples
    return alpha_l0, a1, a2


@dataclass(frozen=True, slots=True)
class ThinAirfoilSection:
    """Closed-form thin-airfoil section derived from an :class:`AirfoilProfile`."""

    profile: AirfoilProfile
    profile_drag: float = 0.0

    def __post_init__(self) -> None:
        if not isfinite(self.profile_drag) or self.profile_drag < 0.0:
            raise ExternalAeroValidationError("SECTION_PROFILE_DRAG_INVALID")

    @property
    def zero_lift_angle_deg(self) -> float:
        if self.profile.camber_ratio == 0.0:
            return 0.0
        alpha_l0, _, _ = _thin_airfoil_fourier(self.profile)
        return alpha_l0 * 180.0 / pi

    @property
    def lift_curve_slope_per_rad(self) -> float:
        return _DEFAULT_SLOPE_PER_RAD

    def quarter_chord_moment_coefficient(self) -> float:
        if self.profile.camber_ratio == 0.0:
            return 0.0
        _, a1, a2 = _thin_airfoil_fourier(self.profile)
        return (pi / 4.0) * (a2 - a1)

    def profile_drag_coefficient(self, lift: float) -> float:
        return self.profile_drag

    def canonical(self) -> dict[str, object]:
        return {
            "model": "thin-airfoil",
            "profile": self.profile.canonical_payload(),
            "profileDrag": self.profile_drag,
            "zeroLiftAngleDeg": self.zero_lift_angle_deg,
            "liftCurveSlopePerRad": self.lift_curve_slope_per_rad,
            "quarterChordMomentCoefficient": self.quarter_chord_moment_coefficient(),
        }


@dataclass(frozen=True, slots=True)
class TabulatedPolarSection:
    """Section model backed by a declared :class:`ProfilePolar` table."""

    polar: ProfilePolar

    @property
    def zero_lift_angle_deg(self) -> float:
        return self.polar.zero_lift_angle_deg()

    @property
    def lift_curve_slope_per_rad(self) -> float:
        return self.polar.lift_curve_slope_per_rad()

    def profile_drag_coefficient(self, lift: float) -> float:
        return self.polar.profile_drag_coefficient(lift)

    def quarter_chord_moment_coefficient(self) -> float:
        return self.polar.quarter_chord_moment_coefficient()

    def canonical(self) -> dict[str, object]:
        return {"model": "tabulated-polar", "polar": self.polar.canonical()}


def section_model_for_profile(
    profile: AirfoilProfile, *, profile_drag: float = 0.0
) -> ThinAirfoilSection:
    return ThinAirfoilSection(profile=profile, profile_drag=profile_drag)


def polar_from_points(
    polar_id: str,
    points: Sequence[tuple[float, float, float, float]],
    *,
    reynolds_number: float | None = None,
    mach_number: float | None = None,
    source: str = "declared",
) -> ProfilePolar:
    """Build a :class:`ProfilePolar` from ``(alpha_deg, cl, cd, cm)`` tuples."""

    return ProfilePolar(
        polar_id=polar_id,
        points=tuple(
            PolarPoint(alpha_deg, lift, drag, moment) for alpha_deg, lift, drag, moment in points
        ),
        reynolds_number=reynolds_number,
        mach_number=mach_number,
        source=source,
    )


__all__ = [
    "ProfilePolar",
    "PolarPoint",
    "SectionCoefficients",
    "SectionModel",
    "TabulatedPolarSection",
    "ThinAirfoilSection",
    "polar_from_points",
    "section_model_for_profile",
]
