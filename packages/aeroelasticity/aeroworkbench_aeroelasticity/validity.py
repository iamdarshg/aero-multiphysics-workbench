"""Fidelity ladder, validity verdict, and numeric guards for aeroelastic results.

The generic aeroelastic layer serves turbomachinery blades, propellers/open
rotors, wings, tails, control surfaces, and flexible structures through one
contract. The fidelity ladder records which level actually produced a result so
a screening value is never relabelled as a transient/native coupled-field value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import FidelityLevel

from .errors import AeroelasticError


class AeroelasticFidelity(StrEnum):
    """The aeroelastic fidelity ladder, cheapest first."""

    SCREENING = "screening"
    REDUCED = "reduced"
    HARMONIC = "harmonic"
    TRANSIENT_FSI = "transient_fsi"

    def core_level(self) -> FidelityLevel:
        if self is AeroelasticFidelity.TRANSIENT_FSI:
            return FidelityLevel.TRANSIENT
        if self is AeroelasticFidelity.HARMONIC:
            return FidelityLevel.HARMONIC_RESPONSE
        if self is AeroelasticFidelity.REDUCED:
            return FidelityLevel.MRF
        return FidelityLevel.ANALYTICAL

    def rank(self) -> int:
        return {
            AeroelasticFidelity.SCREENING: 0,
            AeroelasticFidelity.REDUCED: 1,
            AeroelasticFidelity.HARMONIC: 2,
            AeroelasticFidelity.TRANSIENT_FSI: 3,
        }[self]


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity outcome carried on every aeroelastic result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "detail": self.detail,
        }


def finite(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float:
    """Validate a finite real number, failing closed with a typed error."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AeroelasticError(f"{name} must be a number")
    result = float(value)
    if not isfinite(result):
        raise AeroelasticError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise AeroelasticError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise AeroelasticError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise AeroelasticError(f"{name} must be <= {maximum}")
    return result


def finite_tuple(value: Any, name: str) -> tuple[float, ...]:
    """Validate a non-empty sequence of finite real numbers."""

    if not isinstance(value, (tuple, list)) or not value:
        raise AeroelasticError(f"{name} must be a non-empty sequence")
    return tuple(finite(item, f"{name}[{index}]") for index, item in enumerate(value))


def flag(value: Any, name: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise AeroelasticError(f"{name} must be a boolean")
    return value


__all__ = [
    "AeroelasticFidelity",
    "Validity",
    "finite",
    "finite_tuple",
    "flag",
]
