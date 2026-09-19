"""Fidelity, validity, and fail-closed errors for generic propulsors.

A propulsor is any unshrouded or shrouded rotating machine that produces
thrust: a single propeller, a coaxial/contra-rotating pair, an open rotor or a
propfan. A duct or stationary stator is always optional. The fidelity ladder
spans a low-cost screening level (actuator disk / blade-element momentum) up to
native reduced-wake and moving-mesh CFD seams; requested native levels fail
closed when no backend is wired, and declared limits fail closed with
provenance rather than returning an out-of-limit result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel as CoreFidelityLevel
from aeroworkbench_core.types import Provenance


class AeroFidelity(StrEnum):
    """The generic propulsor aerodynamic fidelity ladder."""

    ACTUATOR_DISK = "actuator_disk"
    BLADE_ELEMENT_MOMENTUM = "blade_element_momentum"
    LIFTING_LINE = "lifting_line"
    ROTATING_FRAME_CFD = "rotating_frame_cfd"
    TRANSIENT_CFD = "transient_cfd"

    @property
    def is_native(self) -> bool:
        return self in (
            AeroFidelity.LIFTING_LINE,
            AeroFidelity.ROTATING_FRAME_CFD,
            AeroFidelity.TRANSIENT_CFD,
        )

    @property
    def is_screening(self) -> bool:
        return not self.is_native

    def core_level(self) -> CoreFidelityLevel:
        if self is AeroFidelity.ROTATING_FRAME_CFD:
            return CoreFidelityLevel.MRF
        if self is AeroFidelity.TRANSIENT_CFD:
            return CoreFidelityLevel.TRANSIENT
        return CoreFidelityLevel.ANALYTICAL


class PropulsorError(ValueError):
    """A typed, fail-closed propulsor contract violation."""

    code = "PREPARATION_FAILED"


class CapabilityUnavailable(RuntimeError):
    """A requested native propulsor capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"


class LimitExceeded(PropulsorError):
    """A declared propulsor design/operating limit was violated."""

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
    """Participant validity outcome carried on every propulsor result."""

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
        raise PropulsorError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise PropulsorError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise PropulsorError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise PropulsorError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise PropulsorError(f"{name} must be <= {maximum}")
    return result


def finite_vector(
    value: Any, name: str, *, length: int = 3, minimum: float | None = None
) -> tuple[float, ...]:
    """Validate a fixed-length vector of finite numbers."""

    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise PropulsorError(f"{name} must be a sequence of {length} numbers")
    return tuple(
        finite(item, f"{name}[{index}]", minimum=minimum)
        for index, item in enumerate(value)
    )


def flag(value: Any, name: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise PropulsorError(f"{name} must be a boolean")
    return value


def integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PropulsorError(f"{name} must be an integer")
    if isinstance(value, float):
        if not value.is_integer():
            raise PropulsorError(f"{name} must be an integer")
        value = int(value)
    if value < minimum or value > maximum:
        raise PropulsorError(f"{name} must be within {minimum}..{maximum}")
    return int(value)


def nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PropulsorError(f"{name} is required")
    return value


__all__ = [
    "AeroFidelity",
    "CapabilityUnavailable",
    "LimitExceeded",
    "PropulsorError",
    "Validity",
    "finite",
    "finite_vector",
    "flag",
    "integer",
    "nonempty",
]
