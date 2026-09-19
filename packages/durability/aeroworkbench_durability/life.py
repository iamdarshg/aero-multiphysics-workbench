"""Life-limited-part bookkeeping, inspection intervals, and strength margins.

A declared life requirement cannot be satisfied by static strength alone: an
assessment needs a provenance-backed cyclic damage rate, otherwise it returns
``DATA_UNAVAILABLE``. From a damage rate the module derives allowable life,
inspection intervals, remaining life, and required safety factors, and provides
ultimate/overspeed margin contracts for highly loaded and rotating parts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .validity import DataUnavailable, DurabilityError, Validity, finite

__all__ = [
    "LifeAssessment",
    "LifeLedger",
    "LifeLedgerEntry",
    "LifeRequirement",
    "MarginResult",
    "assess_life_requirement",
    "evaluate_margin",
    "inspection_interval_cycles",
    "overspeed_burst_margin",
    "ultimate_load_margin",
]


def inspection_interval_cycles(
    damage_per_cycle: float, *, detectable_damage: float = 0.1
) -> float:
    """Cycles between inspections that keep damage below a detectable level."""

    damage = finite(damage_per_cycle, "damage_per_cycle", positive=True)
    threshold = finite(detectable_damage, "detectable_damage", positive=True)
    if threshold > 1.0:
        raise DurabilityError("detectable_damage must not exceed 1.0")
    return threshold / damage


@dataclass(frozen=True, slots=True)
class LifeRequirement:
    """A declared required life for a life-limited part."""

    part_id: str
    required_cycles: float | None = None
    required_hours: float | None = None
    safety_factor: float = 1.0
    allowable_damage: float = 1.0

    def __post_init__(self) -> None:
        if not self.part_id.strip():
            raise DurabilityError("life requirement part_id is required")
        if self.required_cycles is None and self.required_hours is None:
            raise DurabilityError("life requirement needs required_cycles and/or required_hours")
        if self.required_cycles is not None:
            finite(self.required_cycles, "required_cycles", positive=True)
        if self.required_hours is not None:
            finite(self.required_hours, "required_hours", positive=True)
        finite(self.safety_factor, "safety_factor", positive=True)
        allowable = finite(self.allowable_damage, "allowable_damage", positive=True)
        if allowable > 1.0:
            raise DurabilityError("allowable_damage must not exceed 1.0")


@dataclass(frozen=True, slots=True)
class LifeAssessment:
    """Provenance-backed life-requirement assessment."""

    part_id: str
    damage_per_cycle: float
    allowable_cycles: float
    consumed_cycles: float
    remaining_cycles: float
    utilization: float
    inspection_interval_cycles: float
    required_cycles: float | None
    required_hours: float | None
    allowable_hours: float | None
    validity: Validity
    provenance: Provenance

    @property
    def passed(self) -> bool:
        return self.validity.passed

    def units(self) -> dict[str, str]:
        return {
            "damage_per_cycle": "1/cycle",
            "allowable_cycles": "cycle",
            "consumed_cycles": "cycle",
            "inspection_interval_cycles": "cycle",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "partId": self.part_id,
            "damagePerCycle": self.damage_per_cycle,
            "allowableCycles": self.allowable_cycles,
            "consumedCycles": self.consumed_cycles,
            "remainingCycles": self.remaining_cycles,
            "utilization": self.utilization,
            "inspectionIntervalCycles": self.inspection_interval_cycles,
            "requiredCycles": self.required_cycles,
            "requiredHours": self.required_hours,
            "allowableHours": self.allowable_hours,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def assess_life_requirement(
    requirement: LifeRequirement,
    *,
    damage_per_cycle: float | None,
    consumed_cycles: float = 0.0,
    cycles_per_hour: float | None = None,
    detectable_damage: float = 0.1,
) -> LifeAssessment:
    """Assess a life requirement from a cyclic damage rate.

    ``damage_per_cycle=None`` means only static strength was supplied, which
    cannot demonstrate a cyclic life requirement; the call fails closed.
    """

    if damage_per_cycle is None:
        raise DataUnavailable(
            "static strength alone cannot satisfy a declared life requirement; "
            "provenance-backed cyclic durability evidence is required"
        )
    damage = finite(damage_per_cycle, "damage_per_cycle", positive=True)
    consumed = finite(consumed_cycles, "consumed_cycles")
    if consumed < 0.0:
        raise DurabilityError("consumed_cycles must be non-negative")
    allowable = requirement.allowable_damage / (damage * requirement.safety_factor)
    remaining = allowable - consumed
    utilization = consumed / allowable
    interval = inspection_interval_cycles(damage, detectable_damage=detectable_damage)

    allowable_hours: float | None = None
    checks: dict[str, bool] = {}
    if requirement.required_cycles is not None:
        checks["required_cycles_within_allowable"] = (
            requirement.required_cycles <= allowable
        )
    if requirement.required_hours is not None:
        if cycles_per_hour is None:
            raise DataUnavailable("required_hours needs cycles_per_hour to convert life")
        rate = finite(cycles_per_hour, "cycles_per_hour", positive=True)
        allowable_hours = allowable / rate
        checks["required_hours_within_allowable"] = requirement.required_hours <= allowable_hours
    passed = bool(checks) and all(checks.values())
    provenance = analytical_provenance(
        "life-requirement-assessment",
        {
            "partId": requirement.part_id,
            "damagePerCycle": damage,
            "consumedCycles": consumed,
            "safetyFactor": requirement.safety_factor,
            "allowableDamage": requirement.allowable_damage,
            "requiredCycles": requirement.required_cycles,
            "requiredHours": requirement.required_hours,
        },
        assumptions=(
            "linear damage accrual at a constant damage-per-cycle rate",
            "life requirement is met only when required life is within the factored allowable",
        ),
    )
    return LifeAssessment(
        part_id=requirement.part_id,
        damage_per_cycle=damage,
        allowable_cycles=allowable,
        consumed_cycles=consumed,
        remaining_cycles=remaining,
        utilization=utilization,
        inspection_interval_cycles=interval,
        required_cycles=requirement.required_cycles,
        required_hours=requirement.required_hours,
        allowable_hours=allowable_hours,
        validity=Validity(passed=passed, checks=checks, detail=f"life:{requirement.part_id}"),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class MarginResult:
    """A strength or load margin with an explicit reserve factor."""

    name: str
    allowable_pa: float
    applied_pa: float
    safety_factor: float
    reserve_factor: float
    provenance: Provenance

    @property
    def passed(self) -> bool:
        return self.reserve_factor >= 1.0

    def units(self) -> dict[str, str]:
        return {
            "allowable_pa": "Pa",
            "applied_pa": "Pa",
            "reserve_factor": "1",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "allowablePa": self.allowable_pa,
            "appliedPa": self.applied_pa,
            "safetyFactor": self.safety_factor,
            "reserveFactor": self.reserve_factor,
            "passed": self.passed,
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def evaluate_margin(
    name: str,
    allowable_pa: float,
    applied_pa: float,
    *,
    safety_factor: float = 1.0,
) -> MarginResult:
    """Reserve factor ``allowable / (applied * safety_factor)``."""

    if not name.strip():
        raise DurabilityError("margin name is required")
    allowable = finite(allowable_pa, "allowable_pa", positive=True)
    applied = finite(applied_pa, "applied_pa", positive=True)
    factor = finite(safety_factor, "safety_factor", positive=True)
    reserve = allowable / (applied * factor)
    provenance = analytical_provenance(
        "strength-margin",
        {
            "name": name,
            "allowablePa": allowable,
            "appliedPa": applied,
            "safetyFactor": factor,
        },
        assumptions=("reserve factor is a single scalar margin on the declared stress",),
    )
    return MarginResult(
        name=name,
        allowable_pa=allowable,
        applied_pa=applied,
        safety_factor=factor,
        reserve_factor=reserve,
        provenance=provenance,
    )


def overspeed_burst_margin(
    allowable_pa: float,
    operating_stress_pa: float,
    *,
    overspeed_factor: float,
    safety_factor: float = 1.0,
) -> MarginResult:
    """Burst margin for a rotating part at an overspeed condition."""

    overspeed = finite(overspeed_factor, "overspeed_factor", positive=True)
    if overspeed < 1.0:
        raise DurabilityError("overspeed_factor must be at least 1.0")
    applied = finite(operating_stress_pa, "operating_stress_pa", positive=True) * overspeed
    return evaluate_margin(
        "overspeed-burst", allowable_pa, applied, safety_factor=safety_factor
    )


def ultimate_load_margin(
    allowable_pa: float,
    limit_stress_pa: float,
    *,
    ultimate_factor: float = 1.5,
    safety_factor: float = 1.0,
) -> MarginResult:
    """Ultimate-load margin on a limit stress."""

    load_factor = finite(ultimate_factor, "ultimate_factor", positive=True)
    if load_factor < 1.0:
        raise DurabilityError("ultimate_factor must be at least 1.0")
    applied = finite(limit_stress_pa, "limit_stress_pa", positive=True) * load_factor
    return evaluate_margin(
        "ultimate-load", allowable_pa, applied, safety_factor=safety_factor
    )


@dataclass(frozen=True, slots=True)
class LifeLedgerEntry:
    """One part's consumed and allowable life for ledger bookkeeping."""

    part_id: str
    consumed_cycles: float
    consumed_hours: float
    allowable_cycles: float
    allowable_hours: float | None

    @property
    def utilization(self) -> float:
        return self.consumed_cycles / self.allowable_cycles

    @property
    def exhausted(self) -> bool:
        return self.consumed_cycles >= self.allowable_cycles

    def canonical(self) -> dict[str, Any]:
        return {
            "consumedCycles": self.consumed_cycles,
            "consumedHours": self.consumed_hours,
            "allowableCycles": self.allowable_cycles,
            "allowableHours": self.allowable_hours,
        }


@dataclass(frozen=True, slots=True)
class LifeLedger:
    """Content-addressed bookkeeping of consumed life across parts."""

    entries: tuple[LifeLedgerEntry, ...] = ()

    def _by_id(self) -> dict[str, LifeLedgerEntry]:
        return {entry.part_id: entry for entry in self.entries}

    def record(
        self,
        part_id: str,
        *,
        consumed_cycles: float,
        consumed_hours: float,
        allowable_cycles: float,
        allowable_hours: float | None = None,
    ) -> LifeLedger:
        if not part_id.strip():
            raise DurabilityError("ledger part_id is required")
        entry = LifeLedgerEntry(
            part_id=part_id,
            consumed_cycles=finite(consumed_cycles, "consumed_cycles"),
            consumed_hours=finite(consumed_hours, "consumed_hours"),
            allowable_cycles=finite(allowable_cycles, "allowable_cycles", positive=True),
            allowable_hours=(
                finite(allowable_hours, "allowable_hours", positive=True)
                if allowable_hours is not None
                else None
            ),
        )
        updated = self._by_id()
        updated[part_id] = entry
        return LifeLedger(tuple(updated[key] for key in sorted(updated)))

    def utilization(self, part_id: str) -> float:
        return self._by_id()[part_id].utilization

    def exhausted(self) -> tuple[str, ...]:
        return tuple(
            sorted(entry.part_id for entry in self.entries if entry.exhausted)
        )

    def digest(self) -> str:
        payload = json.dumps(
            {entry.part_id: entry.canonical() for entry in self.entries},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "parts": {entry.part_id: entry.canonical() for entry in self.entries},
            "digest": self.digest(),
        }
