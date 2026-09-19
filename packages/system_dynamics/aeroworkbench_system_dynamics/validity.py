"""Fidelity, validity, and finite-number contracts for transient dynamics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel as CoreFidelityLevel

from .errors import SystemDynamicsError


class Fidelity(StrEnum):
    """The generic fidelity ladder for system-dynamics participants.

    A steady operating point and a time-accurate transient are distinct
    fidelities, so a screening steady solve can never be relabelled transient.
    """

    STEADY_POINT = "steady-point"
    TRANSIENT = "transient"
    REDUCED = "reduced"
    NATIVE_TRANSIENT = "native-transient"

    def core_level(self) -> CoreFidelityLevel:
        if self in (Fidelity.TRANSIENT, Fidelity.NATIVE_TRANSIENT):
            return CoreFidelityLevel.TRANSIENT
        return CoreFidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity verdict carried on every transient result."""

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
    """Validate a finite number, failing closed with a typed error."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SystemDynamicsError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise SystemDynamicsError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise SystemDynamicsError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise SystemDynamicsError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise SystemDynamicsError(f"{name} must be <= {maximum}")
    return result


__all__ = ["Fidelity", "Validity", "finite"]
