"""Typed, fail-closed errors for high-lift / stall aerodynamics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class HighLiftError(ValueError):
    code = "HIGHLIFT_ERROR"


class CapabilityUnavailable(RuntimeError):
    code = "CAPABILITY_UNAVAILABLE"


class ValidityError(HighLiftError):
    code = "VALIDITY_ERROR"


class LimitExceeded(HighLiftError):
    code = "LIMIT_EXCEEDED"


def finite(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HighLiftError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise HighLiftError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise HighLiftError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise HighLiftError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise HighLiftError(f"{name} must be <= {maximum}")
    return result


def finite_vector(
    vector: Sequence[float], name: str, *, minimum: float | None = None
) -> tuple[float, ...]:
    return tuple(
        finite(component, f"{name}[{index}]", minimum=minimum)
        for index, component in enumerate(vector)
    )


__all__ = [
    "CapabilityUnavailable",
    "HighLiftError",
    "LimitExceeded",
    "ValidityError",
    "finite",
    "finite_vector",
]
