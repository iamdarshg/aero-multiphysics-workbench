"""Typed, fail-closed error and numeric-guard contract for landing gear.

A requested native capability that is absent raises :class:`CapabilityUnavailable`
and never falls back to a relabelled analytical result. A declared limit
(stroke, load, angle) that is exceeded raises :class:`LimitExceeded`; an unstable
gear/CG placement raises :class:`GroundStabilityError`. Nothing is fabricated.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class LandingGearError(ValueError):
    """A typed, fail-closed landing-gear / ground-dynamics contract violation."""

    code = "LANDING_GEAR_ERROR"


class UnitError(LandingGearError):
    """An unknown or dimensionally inconsistent unit."""

    code = "UNIT_ERROR"


class CapabilityUnavailable(RuntimeError):
    """A requested native capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"


class LimitExceeded(LandingGearError):
    """A declared physical limit was exceeded."""

    code = "LIMIT_EXCEEDED"


class GroundStabilityError(LandingGearError):
    """The gear placement / CG combination is not ground-stable."""

    code = "GROUND_STABILITY_ERROR"


def finite(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float:
    """Validate a finite number, failing closed with a typed error."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LandingGearError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise LandingGearError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise LandingGearError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise LandingGearError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise LandingGearError(f"{name} must be <= {maximum}")
    return result


def finite_vector(
    vector: Sequence[float], name: str, *, minimum: float | None = None
) -> tuple[float, ...]:
    """Validate a finite vector element-wise, failing closed."""

    return tuple(
        finite(component, f"{name}[{index}]", minimum=minimum)
        for index, component in enumerate(vector)
    )


__all__ = [
    "CapabilityUnavailable",
    "GroundStabilityError",
    "LimitExceeded",
    "LandingGearError",
    "UnitError",
    "finite",
    "finite_vector",
]
