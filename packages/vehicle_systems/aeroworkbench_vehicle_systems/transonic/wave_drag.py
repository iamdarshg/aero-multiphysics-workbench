"""Wave-drag screening: Sears-Haack body minimum and Whitcomb area-rule check."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi, sqrt
from typing import Any

from .contracts import ResultEnvelope, Validity, analytical_envelope, content_digest
from .errors import TransonicContractError, TransonicValidityError
from .regime import assert_not_hypersonic

__all__ = [
    "AREA_PENALTY_FACTOR",
    "AREA_SMOOTHNESS_LIMIT",
    "AreaRuleResult",
    "SearsHaackResult",
    "area_rule_assessment",
    "assess_area_rule",
    "require_supersonic_band",
    "sears_haack_wave_drag",
]

AREA_SMOOTHNESS_LIMIT = 10.0
AREA_PENALTY_FACTOR = 0.002
SEARS_HAACK_MODEL = "vehicle-systems.transonic.sears-haack-minimum"
AREA_RULE_MODEL = "vehicle-systems.transonic.area-rule-screening"
SUPERSONIC_MIN_MACH = 1.05
SUPERSONIC_MAX_MACH = 3.0
MIN_FINENESS_RATIO = 5.0


def require_supersonic_band(mach: float, detail: str) -> float:
    """Require Mach inside the declared supersonic screening band."""

    return _require_supersonic_band(mach, detail)


def _require_supersonic_band(mach: float, detail: str) -> float:
    value = assert_not_hypersonic(mach)
    if not isfinite(value) or value < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    if not SUPERSONIC_MIN_MACH <= value <= SUPERSONIC_MAX_MACH:
        raise TransonicValidityError(f"{detail}:mach={value}:band=[1.05,3.0]")
    return value


@dataclass(frozen=True, slots=True)
class SearsHaackResult:
    """Sears-Haack minimum wave drag for a slender body with its envelope."""

    mach: float
    drag_over_q_m2: float
    cd_wave: float
    fineness_ratio: float
    validity: Validity
    envelope: ResultEnvelope

    def canonical(self) -> dict[str, Any]:
        return {
            "mach": self.mach,
            "dragOverQm2": self.drag_over_q_m2,
            "cdWave": self.cd_wave,
            "finenessRatio": self.fineness_ratio,
            "validity": self.validity.canonical(),
            "envelope": self.envelope.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())

    @property
    def input_hash(self) -> str:
        return self.envelope.inputs_hash


def sears_haack_wave_drag(
    volume_m3: float,
    length_m: float,
    max_cross_section_m2: float,
    reference_area_m2: float,
    mach: float,
) -> SearsHaackResult:
    """Minimum supersonic wave drag of the equal-volume Sears-Haack body."""

    value = _require_supersonic_band(mach, "SEARS_HAACK_OUT_OF_RANGE")
    for label, item in (
        ("VOLUME", volume_m3),
        ("LENGTH", length_m),
        ("MAX_CROSS_SECTION", max_cross_section_m2),
        ("REFERENCE_AREA", reference_area_m2),
    ):
        if not isfinite(item) or item <= 0.0:
            raise TransonicContractError(f"SEARS_HAACK_{label}_NOT_POSITIVE")
    diameter = 2.0 * sqrt(max_cross_section_m2 / pi)
    fineness = length_m / diameter
    if fineness < MIN_FINENESS_RATIO:
        raise TransonicValidityError(f"SEARS_HAACK_NOT_SLENDER:fineness={fineness}")
    drag_over_q = 128.0 * volume_m3 * volume_m3 / (pi * length_m**4)
    cd_wave = drag_over_q / reference_area_m2
    validity = Validity(
        True,
        {"supersonic_in_range": True, "slender": True},
        "Sears-Haack minimum; real bodies meet or exceed this value",
    )
    envelope = analytical_envelope(
        model=SEARS_HAACK_MODEL,
        inputs={
            "volumeM3": volume_m3,
            "lengthM": length_m,
            "maxCrossSectionM2": max_cross_section_m2,
            "referenceAreaM2": reference_area_m2,
            "mach": value,
        },
        validity=validity,
        assumptions=("slender-body theory optimum; lower bound, not a prediction",),
    )
    return SearsHaackResult(value, drag_over_q, cd_wave, fineness, validity, envelope)


def _require_stations(stations: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    if len(stations) < 5:
        raise TransonicContractError(f"AREA_RULE_NEEDS_STATIONS:got={len(stations)}")
    for x, area in stations:
        if not isfinite(x) or not isfinite(area) or area < 0.0:
            raise TransonicContractError(f"AREA_RULE_STATION_INVALID:{(x, area)!r}")
    for (x0, _), (x1, _) in zip(stations, stations[1:], strict=False):
        if x1 <= x0:
            raise TransonicContractError("AREA_RULE_STATIONS_MUST_ADVANCE")
    return stations


@dataclass(frozen=True, slots=True)
class AreaRuleResult:
    """Whitcomb area-rule smoothness screening with its envelope."""

    n_stations: int
    length_m: float
    max_area_m2: float
    max_curvature: float
    passes: bool
    delta_cd_penalty: float
    validity: Validity
    envelope: ResultEnvelope

    def canonical(self) -> dict[str, Any]:
        return {
            "nStations": self.n_stations,
            "lengthM": self.length_m,
            "maxAreaM2": self.max_area_m2,
            "maxCurvature": self.max_curvature,
            "passes": self.passes,
            "deltaCdPenalty": self.delta_cd_penalty,
            "validity": self.validity.canonical(),
            "envelope": self.envelope.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())

    @property
    def input_hash(self) -> str:
        return self.envelope.inputs_hash


def area_rule_assessment(stations: tuple[tuple[float, float], ...]) -> AreaRuleResult:
    """Screen an area distribution for area-rule smoothness violations."""

    points = _require_stations(stations)
    length = points[-1][0] - points[0][0]
    peak = max(area for _, area in points)
    if length <= 0.0 or peak <= 0.0:
        raise TransonicContractError("AREA_RULE_DEGENERATE_GEOMETRY")
    curvatures: list[float] = []
    for (x0, a0), (x1, a1), (x2, a2) in zip(points, points[1:], points[2:], strict=False):
        h0 = x1 - x0
        h1 = x2 - x1
        second = 2.0 * (h0 * a2 - (h0 + h1) * a1 + h1 * a0) / (h0 * h1 * (h0 + h1))
        curvatures.append(abs(second) * length * length / peak)
    worst = max(curvatures)
    passes = bool(worst <= AREA_SMOOTHNESS_LIMIT)
    penalty = float(AREA_PENALTY_FACTOR * sum(c * c for c in curvatures) / len(curvatures))
    validity = Validity(
        passes,
        {"area_rule_smooth": passes},
        "Whitcomb area-rule screening; a failure requires re-lofting",
    )
    envelope = analytical_envelope(
        model=AREA_RULE_MODEL,
        inputs={"stations": [[x, a] for x, a in points]},
        validity=validity,
        assumptions=(
            "far-field curvature screening; penalty is a declared screening constant",
            "transonic configurations only; supersonic bodies use Sears-Haack",
        ),
    )
    return AreaRuleResult(len(points), length, peak, worst, passes, penalty, validity, envelope)


def assess_area_rule(stations: tuple[tuple[float, float], ...]) -> AreaRuleResult:
    """Alias for :func:`area_rule_assessment` used by design seams."""

    return area_rule_assessment(stations)
