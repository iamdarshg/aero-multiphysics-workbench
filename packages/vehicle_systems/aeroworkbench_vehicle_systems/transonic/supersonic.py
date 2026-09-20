"""Supersonic screening: linearized lifting surfaces and normal-shock strength."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, radians, sqrt
from typing import Any

from .contracts import ResultEnvelope, Validity, analytical_envelope, content_digest
from .errors import TransonicContractError, TransonicValidityError
from .regime import assert_not_hypersonic
from .wave_drag import require_supersonic_band

__all__ = [
    "MAX_ALPHA_DEG",
    "MAX_THICKNESS_RATIO",
    "SupersonicAssessment",
    "ackeret_lift",
    "assess_supersonic_section",
    "double_wedge_wave_drag",
    "normal_shock_ratios",
]

MAX_ALPHA_DEG = 8.0
MAX_THICKNESS_RATIO = 0.15
SUPERSONIC_MODEL = "vehicle-systems.transonic.ackeret-screening"
SHOCK_MODEL = "vehicle-systems.transonic.normal-shock"


def _require_section_inputs(alpha_deg: float, thickness_ratio: float) -> tuple[float, float]:
    if not isfinite(alpha_deg) or abs(alpha_deg) > MAX_ALPHA_DEG:
        raise TransonicContractError(f"ALPHA_OUT_OF_RANGE:{alpha_deg!r}")
    if not isfinite(thickness_ratio) or not 0.0 < thickness_ratio <= MAX_THICKNESS_RATIO:
        raise TransonicContractError(f"THICKNESS_RATIO_OUT_OF_RANGE:{thickness_ratio!r}")
    return float(alpha_deg), float(thickness_ratio)


def ackeret_lift(alpha_deg: float, mach: float) -> float:
    """Linearized supersonic section lift coefficient."""

    alpha, _ = _require_section_inputs(alpha_deg, 0.05)
    beta = _ackeret_beta(mach)
    return 4.0 * radians(alpha) / beta


def double_wedge_wave_drag(thickness_ratio: float, alpha_deg: float, mach: float) -> float:
    """Ackeret wave drag of a symmetric double-wedge section."""

    alpha, thick = _require_section_inputs(alpha_deg, thickness_ratio)
    beta = _ackeret_beta(mach)
    alpha_rad = radians(alpha)
    return float(4.0 * (alpha_rad * alpha_rad + thick * thick) / beta)


def _ackeret_beta(mach: float) -> float:
    value = require_supersonic_band(mach, "ACKERET_OUT_OF_RANGE")
    return sqrt(value * value - 1.0)


def normal_shock_ratios(mach: float, gamma: float = 1.4) -> dict[str, float]:
    """Exact normal-shock jump relations; shock strength only, never location."""

    value = assert_not_hypersonic(mach)
    if not isfinite(value) or value < 1.0:
        raise TransonicValidityError(f"NORMAL_SHOCK_NEEDS_SUPERSONIC:mach={value}")
    if not isfinite(gamma) or gamma <= 1.0:
        raise TransonicContractError(f"INVALID_GAMMA:{gamma!r}")
    m2 = value * value
    downstream = sqrt(((gamma - 1.0) * m2 + 2.0) / (2.0 * gamma * m2 - (gamma - 1.0)))
    pressure = 1.0 + 2.0 * gamma / (gamma + 1.0) * (m2 - 1.0)
    density = (gamma + 1.0) * m2 / (2.0 + (gamma - 1.0) * m2)
    total = (
        (((gamma + 1.0) * (gamma + 1.0) * m2) / (4.0 * gamma * m2 - 2.0 * (gamma - 1.0)))
        ** (gamma / (gamma - 1.0))
        * ((1.0 - gamma + 2.0 * gamma * m2) / (gamma + 1.0))
    ) / ((1.0 + (gamma - 1.0) / 2.0 * m2) ** (gamma / (gamma - 1.0)))
    return {
        "downstreamMach": float(downstream),
        "staticPressureRatio": float(pressure),
        "densityRatio": float(density),
        "temperatureRatio": float(pressure / density),
        "totalPressureRatio": float(total),
    }


@dataclass(frozen=True, slots=True)
class SupersonicAssessment:
    """Supersonic section screening with shock strength and its envelope."""

    mach: float
    alpha_deg: float
    thickness_ratio: float
    lift_coefficient: float
    cd_wave: float
    shock: dict[str, float]
    validity: Validity
    envelope: ResultEnvelope

    def canonical(self) -> dict[str, Any]:
        return {
            "mach": self.mach,
            "alphaDeg": self.alpha_deg,
            "thicknessRatio": self.thickness_ratio,
            "liftCoefficient": self.lift_coefficient,
            "cdWave": self.cd_wave,
            "shock": dict(self.shock),
            "validity": self.validity.canonical(),
            "envelope": self.envelope.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())

    @property
    def input_hash(self) -> str:
        return self.envelope.inputs_hash


def assess_supersonic_section(
    alpha_deg: float, thickness_ratio: float, mach: float
) -> SupersonicAssessment:
    """Assess one thin supersonic section; shock location requires native CFD."""

    value = require_supersonic_band(mach, "SUPERSONIC_SECTION_OUT_OF_RANGE")
    alpha, thick = _require_section_inputs(alpha_deg, thickness_ratio)
    lift = ackeret_lift(alpha, value)
    drag = double_wedge_wave_drag(thick, alpha, value)
    shock = normal_shock_ratios(value)
    validity = Validity(
        True,
        {"ackeret_in_range": True, "shock_strength_exact": True},
        "Ackeret screening; shock location is not predicted analytically",
    )
    envelope = analytical_envelope(
        model=SUPERSONIC_MODEL,
        inputs={"alphaDeg": alpha, "thicknessRatio": thick, "mach": value},
        validity=validity,
        assumptions=(
            "thin double-wedge Ackeret screening; small angles only",
            "normal-shock strength is exact for the declared gamma",
        ),
    )
    return SupersonicAssessment(value, alpha, thick, lift, drag, shock, validity, envelope)
