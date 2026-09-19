"""Typed, fail-closed error contract for environmental degradation.

A requested native capability that is absent raises :class:`CapabilityUnavailable`
and never falls back to a screening envelope relabelled as high fidelity. An
out-of-domain request raises :class:`ValidityError`; a malformed unit or a
non-finite value raises :class:`EnvironmentalError`. Nothing is fabricated.
"""

from __future__ import annotations

from typing import Any


class EnvironmentalError(ValueError):
    """A typed, fail-closed environmental-degradation contract violation."""

    code = "ENVIRONMENTAL_ERROR"


class UnitError(EnvironmentalError):
    """An unknown or dimensionally inconsistent unit."""

    code = "UNIT_ERROR"


class ValidityError(EnvironmentalError):
    """A request left the declared validity domain of the model."""

    code = "VALIDITY_ERROR"


class CapabilityUnavailable(RuntimeError):
    """A requested native capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"


class LimitViolation(EnvironmentalError):
    """A declared degradation limit was exceeded."""

    code = "LIMIT_VIOLATION"


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
        raise EnvironmentalError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise EnvironmentalError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise EnvironmentalError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise EnvironmentalError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise EnvironmentalError(f"{name} must be <= {maximum}")
    return result


__all__ = [
    "CapabilityUnavailable",
    "EnvironmentalError",
    "LimitViolation",
    "UnitError",
    "ValidityError",
    "finite",
]
