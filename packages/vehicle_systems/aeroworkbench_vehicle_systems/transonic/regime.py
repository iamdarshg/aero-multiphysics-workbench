"""Regime classification across incompressible to hypersonic external flow."""

from __future__ import annotations

from math import isfinite

from .contracts import FlowRegime
from .errors import TransonicContractError, TransonicOutOfScope

__all__ = [
    "HYPERSONIC_MIN_MACH",
    "INCOMPRESSIBLE_MAX_MACH",
    "SUBSONIC_MAX_MACH",
    "SUPERSONIC_MAX_MACH",
    "TRANSONIC_MAX_MACH",
    "assert_not_hypersonic",
    "classify_regime",
    "is_shock_regime",
    "regime_of",
]

INCOMPRESSIBLE_MAX_MACH = 0.3
SUBSONIC_MAX_MACH = 0.8
TRANSONIC_MAX_MACH = 1.2
SUPERSONIC_MAX_MACH = 5.0
HYPERSONIC_MIN_MACH = 5.0


def _require_mach(mach: float) -> float:
    if not isfinite(mach) or mach < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    return float(mach)


def classify_regime(mach: float) -> FlowRegime:
    """Classify freestream Mach into a declared external-flow regime."""

    value = _require_mach(mach)
    if value < INCOMPRESSIBLE_MAX_MACH:
        return FlowRegime.INCOMPRESSIBLE
    if value < SUBSONIC_MAX_MACH:
        return FlowRegime.SUBSONIC
    if value < TRANSONIC_MAX_MACH:
        return FlowRegime.TRANSONIC
    if value < HYPERSONIC_MIN_MACH:
        return FlowRegime.SUPERSONIC
    return FlowRegime.HYPERSONIC


def regime_of(mach: float) -> FlowRegime:
    """Alias for :func:`classify_regime` used by downstream seams."""

    return classify_regime(mach)


def assert_not_hypersonic(mach: float) -> float:
    """Fail closed on hypersonic/high-enthalpy flow, which is out of scope."""

    value = _require_mach(mach)
    if value >= HYPERSONIC_MIN_MACH:
        raise TransonicOutOfScope(
            f"HYPERSONIC_OUT_OF_SCOPE:mach={value}:high-enthalpy flow needs a separate issue"
        )
    return value


def is_shock_regime(mach: float) -> bool:
    """Whether embedded or bow shocks must be assumed at this Mach."""

    return classify_regime(mach) in (FlowRegime.TRANSONIC, FlowRegime.SUPERSONIC)
