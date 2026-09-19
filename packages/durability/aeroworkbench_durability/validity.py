"""Fidelity, validity, and fail-closed error contracts for durability analysis.

Every durability result reports an explicit fidelity level, a per-check
validity verdict, and an immutable provenance record. Requested native
structural/FEA capabilities fail closed when absent, declared life limits fail
closed with provenance, and missing material-life data yields an explicit
unavailable verdict rather than an invented life.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel as CoreFidelityLevel
from aeroworkbench_core.types import Provenance


class Fidelity(StrEnum):
    """The generic fidelity ladder for durability participants."""

    ANALYTICAL = "analytical"
    CATALOG = "catalog"
    REDUCED = "reduced"
    NATIVE = "native"

    def core_level(self) -> CoreFidelityLevel:
        if self is Fidelity.NATIVE:
            return CoreFidelityLevel.TRANSIENT
        return CoreFidelityLevel.ANALYTICAL


class DurabilityError(ValueError):
    """A typed, fail-closed durability contract violation."""

    code = "PREPARATION_FAILED"


class CapabilityUnavailable(RuntimeError):
    """A requested native capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"


class DataUnavailable(RuntimeError):
    """Material-life or allowable data is absent or outside its valid domain.

    This is the "unavailable/partial, never invented" outcome required by the
    durability data discipline. It never substitutes a screening model for a
    requested native analysis.
    """

    code = "DATA_UNAVAILABLE"


class LimitExceeded(DurabilityError):
    """A declared life/strength limit was violated; carries provenance."""

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
    """Durability validity outcome carried on every result."""

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
        raise DurabilityError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise DurabilityError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise DurabilityError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise DurabilityError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise DurabilityError(f"{name} must be <= {maximum}")
    return result


def finite_vector(
    value: Any, name: str, *, length: int = 3, minimum: float | None = None
) -> tuple[float, ...]:
    """Validate a fixed-length vector of finite numbers."""

    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise DurabilityError(f"{name} must be a sequence of {length} numbers")
    return tuple(
        finite(item, f"{name}[{index}]", minimum=minimum)
        for index, item in enumerate(value)
    )


def flag(value: Any, name: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise DurabilityError(f"{name} must be a boolean")
    return value


def integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DurabilityError(f"{name} must be an integer")
    if isinstance(value, float):
        if not value.is_integer():
            raise DurabilityError(f"{name} must be an integer")
        value = int(value)
    if value < minimum or value > maximum:
        raise DurabilityError(f"{name} must be within {minimum}..{maximum}")
    return int(value)


__all__ = [
    "CapabilityUnavailable",
    "DataUnavailable",
    "DurabilityError",
    "Fidelity",
    "LimitExceeded",
    "Validity",
    "finite",
    "finite_vector",
    "flag",
    "integer",
]
