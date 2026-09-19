"""Fidelity, validity, and fail-closed error contracts for mechanisms.

Generic mechanical-interface participants report an explicit fidelity level,
a per-check validity verdict, and an immutable provenance record. Requested
native capabilities (external tribology or structural FEA engines) fail closed
when absent, and declared component limits fail closed with provenance rather
than returning a usable-but-silent out-of-limit result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel as CoreFidelityLevel
from aeroworkbench_core.types import Provenance


class Fidelity(StrEnum):
    """The generic fidelity ladder for mechanical-interface participants."""

    ANALYTICAL = "analytical"
    CATALOG = "catalog"
    REDUCED = "reduced"
    NATIVE = "native"

    def core_level(self) -> CoreFidelityLevel:
        if self is Fidelity.NATIVE:
            return CoreFidelityLevel.TRANSIENT
        return CoreFidelityLevel.ANALYTICAL


class MechanismError(ValueError):
    """A typed, fail-closed mechanical-interface contract violation."""

    code = "PREPARATION_FAILED"


class CapabilityUnavailable(RuntimeError):
    """A requested native capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"


class LimitExceeded(MechanismError):
    """A declared component limit was violated; carries provenance."""

    code = "LIMIT_EXCEEDED"

    def __init__(
        self,
        detail: str,
        *,
        violations: tuple[str, ...],
        provenance: Provenance,
    ) -> None:
        super().__init__(detail)
        self.violations = violations
        self.provenance = provenance


@dataclass(frozen=True, slots=True)
class Validity:
    """Participant validity outcome carried on every result."""

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
        raise MechanismError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise MechanismError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise MechanismError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise MechanismError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise MechanismError(f"{name} must be <= {maximum}")
    return result


def finite_vector(
    value: Any, name: str, *, length: int = 3, minimum: float | None = None
) -> tuple[float, ...]:
    """Validate a fixed-length vector of finite numbers."""

    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise MechanismError(f"{name} must be a sequence of {length} numbers")
    return tuple(
        finite(item, f"{name}[{index}]", minimum=minimum)
        for index, item in enumerate(value)
    )


def flag(value: Any, name: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise MechanismError(f"{name} must be a boolean")
    return value


def integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MechanismError(f"{name} must be an integer")
    if isinstance(value, float):
        if not value.is_integer():
            raise MechanismError(f"{name} must be an integer")
        value = int(value)
    if value < minimum or value > maximum:
        raise MechanismError(f"{name} must be within {minimum}..{maximum}")
    return int(value)


__all__ = [
    "CapabilityUnavailable",
    "Fidelity",
    "LimitExceeded",
    "MechanismError",
    "Validity",
    "finite",
    "finite_vector",
    "flag",
    "integer",
]
