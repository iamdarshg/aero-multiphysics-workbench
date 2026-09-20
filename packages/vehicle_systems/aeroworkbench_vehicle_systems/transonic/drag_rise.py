"""Transonic drag rise: Korn critical/divergence Mach and wave-drag increment."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians
from typing import Any

from .contracts import ResultEnvelope, Validity, analytical_envelope, content_digest
from .errors import TransonicContractError, TransonicValidityError
from .regime import assert_not_hypersonic

__all__ = [
    "CRITICAL_TO_DIVERGENCE_OFFSET",
    "DRAG_RISE_EXPONENT",
    "DRAG_RISE_FACTOR",
    "DragRiseResult",
    "assess_drag_rise",
    "critical_mach",
    "drag_divergence_mach",
    "korn_drag_divergence",
    "wave_drag_rise",
]

CRITICAL_TO_DIVERGENCE_OFFSET = 0.08
DRAG_RISE_FACTOR = 5.0
DRAG_RISE_EXPONENT = 2.0
DRAG_MODEL = "vehicle-systems.transonic.korn-drag-rise"
MAX_SWEEP_DEG = 60.0


def _require_section(thickness_ratio: float, lift_coefficient: float, sweep_deg: float) -> None:
    if not isfinite(thickness_ratio) or not 0.03 <= thickness_ratio <= 0.20:
        raise TransonicContractError(f"THICKNESS_RATIO_OUT_OF_RANGE:{thickness_ratio!r}")
    if not isfinite(lift_coefficient) or not -0.5 <= lift_coefficient <= 1.5:
        raise TransonicContractError(f"LIFT_COEFFICIENT_OUT_OF_RANGE:{lift_coefficient!r}")
    if not isfinite(sweep_deg) or not 0.0 <= sweep_deg <= MAX_SWEEP_DEG:
        raise TransonicContractError(f"SWEEP_OUT_OF_RANGE:{sweep_deg!r}")


def _require_kappa(kappa: float) -> float:
    if not isfinite(kappa) or not 0.80 <= kappa <= 1.00:
        raise TransonicContractError(f"KAPPA_OUT_OF_RANGE:{kappa!r}")
    return float(kappa)


def korn_drag_divergence(
    thickness_ratio: float,
    lift_coefficient: float,
    sweep_deg: float = 0.0,
    kappa: float = 0.87,
) -> float:
    """Korn drag-divergence Mach with normal-section sweep correction."""

    _require_section(thickness_ratio, lift_coefficient, sweep_deg)
    technology = _require_kappa(kappa)
    normal = technology - thickness_ratio - 0.1 * lift_coefficient
    diverged = normal / cos(radians(sweep_deg))
    if not isfinite(diverged):
        raise TransonicContractError("KORN_DIVERGENCE_NOT_FINITE")
    return float(diverged)


def drag_divergence_mach(
    thickness_ratio: float,
    lift_coefficient: float,
    sweep_deg: float = 0.0,
    kappa: float = 0.87,
) -> float:
    """Alias for :func:`korn_drag_divergence` used by design seams."""

    return korn_drag_divergence(thickness_ratio, lift_coefficient, sweep_deg, kappa)


def critical_mach(
    thickness_ratio: float,
    lift_coefficient: float,
    sweep_deg: float = 0.0,
    kappa: float = 0.87,
) -> float:
    """Critical Mach, declared one offset below drag divergence."""

    return korn_drag_divergence(thickness_ratio, lift_coefficient, sweep_deg, kappa) - (
        CRITICAL_TO_DIVERGENCE_OFFSET
    )


def wave_drag_rise(mach: float, divergence_mach: float, factor: float = DRAG_RISE_FACTOR) -> float:
    """Quadratic transonic wave-drag increment above drag divergence."""

    value = assert_not_hypersonic(mach)
    if not isfinite(value) or value < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    if not isfinite(divergence_mach) or divergence_mach <= 0.0:
        raise TransonicContractError(f"INVALID_DIVERGENCE_MACH:{divergence_mach!r}")
    if not isfinite(factor) or factor <= 0.0:
        raise TransonicContractError(f"INVALID_DRAG_RISE_FACTOR:{factor!r}")
    if value >= 1.0:
        raise TransonicValidityError(f"DRAG_RISE_NOT_VALID_AT_SONIC:mach={value}:escalate")
    if value <= divergence_mach:
        return 0.0
    return float(factor * (value - divergence_mach) ** DRAG_RISE_EXPONENT)


@dataclass(frozen=True, slots=True)
class DragRiseResult:
    """Critical/divergence Mach plus wave-drag increment with its envelope."""

    mach: float
    critical_mach: float
    divergence_mach: float
    delta_cd_wave: float
    shock_sensitive: bool
    requires_native: bool
    validity: Validity
    envelope: ResultEnvelope

    def canonical(self) -> dict[str, Any]:
        return {
            "mach": self.mach,
            "criticalMach": self.critical_mach,
            "divergenceMach": self.divergence_mach,
            "deltaCdWave": self.delta_cd_wave,
            "shockSensitive": self.shock_sensitive,
            "requiresNative": self.requires_native,
            "validity": self.validity.canonical(),
            "envelope": self.envelope.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())

    @property
    def input_hash(self) -> str:
        return self.envelope.inputs_hash


def assess_drag_rise(
    mach: float,
    thickness_ratio: float,
    lift_coefficient: float,
    sweep_deg: float = 0.0,
    kappa: float = 0.87,
) -> DragRiseResult:
    """Assess drag rise at one operating point; flags native promotion."""

    value = assert_not_hypersonic(mach)
    m_dd = korn_drag_divergence(thickness_ratio, lift_coefficient, sweep_deg, kappa)
    m_cr = m_dd - CRITICAL_TO_DIVERGENCE_OFFSET
    increment = wave_drag_rise(value, m_dd)
    sensitive = bool(value > m_dd - 0.02)
    validity = Validity(
        True,
        {"korn_in_range": True, "shock_sensitive": sensitive},
        "Korn screening; native RANS required when shock-sensitive",
    )
    envelope = analytical_envelope(
        model=DRAG_MODEL,
        inputs={
            "mach": value,
            "thicknessRatio": thickness_ratio,
            "liftCoefficient": lift_coefficient,
            "sweepDeg": sweep_deg,
            "kappa": kappa,
        },
        validity=validity,
        assumptions=(
            "Korn drag-divergence screening with sweep correction",
            "quadratic wave-drag rise above divergence; no shock location predicted",
        ),
    )
    return DragRiseResult(value, m_cr, m_dd, increment, sensitive, sensitive, validity, envelope)
