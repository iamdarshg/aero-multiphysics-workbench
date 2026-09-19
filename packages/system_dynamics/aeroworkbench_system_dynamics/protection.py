"""Typed protection logic: limits, trips, interlocks, and hysteresis.

Protection limits are first-class constraints. Overspeed, overtemperature,
overcurrent, surge/stall margin, vibration/resonance, undervoltage, and
actuator/limit-failure guards are represented uniformly. A limit trips when its
condition holds; hysteresis governs reset; latching limits stay tripped. A
missing protected signal fails closed rather than silently passing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .errors import TransientValidationError
from .provenance import analytical_provenance
from .units import require_unit
from .validity import Validity, finite


class ProtectionKind(StrEnum):
    """The generic protection functions a transient system may declare."""

    OVERSPEED = "overspeed"
    OVERTEMPERATURE = "overtemperature"
    OVERCURRENT = "overcurrent"
    SURGE_STALL_MARGIN = "surge-stall-margin"
    VIBRATION_RESONANCE = "vibration-resonance"
    UNDERVOLTAGE = "undervoltage"
    ACTUATOR_LIMIT = "actuator-limit-failure"


@dataclass(frozen=True, slots=True)
class ProtectionLimit:
    """A typed protection threshold with hysteresis and latch behaviour."""

    name: str
    kind: ProtectionKind
    variable: str
    unit: str
    threshold: float
    direction: str
    hysteresis: float = 0.0
    latching: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.variable.strip():
            raise TransientValidationError("protection name and variable are required")
        if self.direction not in {"high", "low"}:
            raise TransientValidationError(f"UNKNOWN_PROTECTION_DIRECTION:{self.direction}")
        require_unit(self.unit)
        finite(self.threshold, "protection.threshold")
        finite(self.hysteresis, "protection.hysteresis", minimum=0.0)

    def tripped(self, value: float, *, currently_active: bool) -> bool:
        """Return the next active state, applying hysteresis and latching."""

        finite(value, f"protection.{self.name}.value")
        if self.direction == "high":
            if currently_active:
                return self.latching or value > self.threshold - self.hysteresis
            return value >= self.threshold
        if currently_active:
            return self.latching or value < self.threshold + self.hysteresis
        return value <= self.threshold

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "variable": self.variable,
            "unit": self.unit,
            "threshold": self.threshold,
            "direction": self.direction,
            "hysteresis": self.hysteresis,
            "latching": self.latching,
        }


@dataclass(frozen=True, slots=True)
class ProtectionResult:
    """The evaluated protection state with the newly tripped limits."""

    active: tuple[str, ...]
    trips: tuple[str, ...]
    checks: dict[str, bool]
    validity: Validity
    provenance: Provenance

    def canonical(self) -> dict[str, Any]:
        return {
            "active": list(self.active),
            "trips": list(self.trips),
            "checks": dict(self.checks),
            "validity": self.validity.as_dict(),
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "inputsHash": self.provenance.inputs_hash,
            },
        }


def evaluate_protection(
    limits: tuple[ProtectionLimit, ...],
    values: Mapping[str, float],
    *,
    active: frozenset[str] = frozenset(),
    provenance: Provenance | None = None,
) -> ProtectionResult:
    """Evaluate every declared limit; missing signals fail closed."""

    active_names: list[str] = []
    trips: list[str] = []
    checks: dict[str, bool] = {}
    for limit in limits:
        if limit.variable not in values:
            raise TransientValidationError(
                f"PROTECTION_SIGNAL_MISSING:{limit.name}:{limit.variable}"
            )
        was_active = limit.name in active
        now_active = limit.tripped(float(values[limit.variable]), currently_active=was_active)
        checks[limit.name] = not now_active
        if now_active and not was_active:
            trips.append(limit.name)
        if now_active:
            active_names.append(limit.name)
    evaluated = provenance or analytical_provenance(
        "protection-evaluation",
        {"limits": [limit.canonical() for limit in limits], "values": dict(values)},
    )
    passed = all(checks.values())
    validity = Validity(
        passed=passed,
        checks=checks,
        detail="all protection limits clear" if passed else "protection limit active",
    )
    return ProtectionResult(
        active=tuple(active_names),
        trips=tuple(trips),
        checks=checks,
        validity=validity,
        provenance=evaluated,
    )


@dataclass(frozen=True, slots=True)
class InterlockSpec:
    """A protection interlock that forces declared safe inputs when triggered."""

    interlock_id: str
    trigger: tuple[str, ...]
    overrides: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if not self.interlock_id.strip():
            raise TransientValidationError("interlock_id is required")
        if not self.trigger:
            raise TransientValidationError("interlock needs at least one trigger")
        if not self.overrides:
            raise TransientValidationError("interlock needs overrides")
        for name, value in self.overrides:
            if not name.strip():
                raise TransientValidationError("interlock override target is required")
            finite(value, f"interlock.{name}")

    def applies(self, active: tuple[str, ...]) -> bool:
        return any(name in active for name in self.trigger)


def apply_interlocks(
    interlocks: tuple[InterlockSpec, ...], active: tuple[str, ...]
) -> tuple[dict[str, float], tuple[str, ...]]:
    """Return forced input overrides and the fired interlock identifiers."""

    overrides: dict[str, float] = {}
    fired: list[str] = []
    for interlock in interlocks:
        if interlock.applies(active):
            fired.append(interlock.interlock_id)
            for name, value in interlock.overrides:
                overrides[name] = value
    return overrides, tuple(fired)


__all__ = [
    "InterlockSpec",
    "ProtectionKind",
    "ProtectionLimit",
    "ProtectionResult",
    "apply_interlocks",
    "evaluate_protection",
]
