"""High-cycle and low-cycle fatigue with mean-stress corrections.

S-N (Basquin) and strain-life (Coffin-Manson) damage accumulation use sourced,
validity-bounded material curves and explicit mean-stress corrections. Miner
linear damage is reported with its limitations recorded in provenance; missing
or out-of-validity curve data fails closed rather than inventing life.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .curves import SNCurve, StrainLifeCurve
from .provenance import MINER_LIMITATIONS, analytical_provenance
from .validity import DataUnavailable, DurabilityError, Validity, finite

__all__ = [
    "DamageContribution",
    "DamageResult",
    "MeanStressCorrection",
    "StressCycle",
    "StrainCycle",
    "equivalent_amplitude",
    "miner_damage",
    "strain_life_damage",
]


class MeanStressCorrection(StrEnum):
    """Mean-stress correction applied to an alternating stress amplitude."""

    NONE = "none"
    GOODMAN = "goodman"
    GERBER = "gerber"
    SODERBERG = "soderberg"
    MORROW = "morrow"


def equivalent_amplitude(
    stress_amplitude_pa: float,
    stress_mean_pa: float,
    correction: MeanStressCorrection,
    *,
    ultimate_pa: float | None = None,
    yield_pa: float | None = None,
    fatigue_strength_coefficient_pa: float | None = None,
) -> float:
    """Compute a fully-reversed equivalent amplitude for a mean stress state."""

    amplitude = finite(stress_amplitude_pa, "stress_amplitude_pa")
    mean = finite(stress_mean_pa, "stress_mean_pa")
    if amplitude < 0.0:
        raise DurabilityError("stress_amplitude_pa must be non-negative")
    if correction is MeanStressCorrection.NONE:
        return amplitude

    def denominator(reference_pa: float, exponent: int, label: str) -> float:
        finite(reference_pa, label, positive=True)
        ratio = mean / reference_pa
        value = 1.0 - ratio**exponent
        if value <= 0.0:
            raise DataUnavailable(f"{label}_MEAN_STRESS_EXCEEDS_REFERENCE")
        return value

    if correction is MeanStressCorrection.GOODMAN:
        if ultimate_pa is None:
            raise DataUnavailable("GOODMAN_REQUIRES_ULTIMATE_STRENGTH")
        return amplitude / denominator(ultimate_pa, 1, "ultimate_pa")
    if correction is MeanStressCorrection.GERBER:
        if ultimate_pa is None:
            raise DataUnavailable("GERBER_REQUIRES_ULTIMATE_STRENGTH")
        return amplitude / denominator(ultimate_pa, 2, "ultimate_pa")
    if correction is MeanStressCorrection.SODERBERG:
        if yield_pa is None:
            raise DataUnavailable("SODERBERG_REQUIRES_YIELD_STRENGTH")
        return amplitude / denominator(yield_pa, 1, "yield_pa")
    if fatigue_strength_coefficient_pa is None:
        raise DataUnavailable("MORROW_REQUIRES_FATIGUE_STRENGTH_COEFFICIENT")
    return amplitude / denominator(
        fatigue_strength_coefficient_pa, 1, "fatigue_strength_coefficient_pa"
    )


@dataclass(frozen=True, slots=True)
class StressCycle:
    """One constant-amplitude stress cycle in SI units."""

    stress_amplitude_pa: float
    stress_mean_pa: float
    count: float

    def __post_init__(self) -> None:
        amplitude = finite(self.stress_amplitude_pa, "stress_amplitude_pa")
        if amplitude < 0.0:
            raise DurabilityError("stress_amplitude_pa must be non-negative")
        finite(self.stress_mean_pa, "stress_mean_pa")
        if finite(self.count, "count", positive=True) <= 0.0:
            raise DurabilityError("cycle count must be positive")

    @property
    def stress_range_pa(self) -> float:
        return 2.0 * self.stress_amplitude_pa

    @property
    def stress_ratio(self) -> float:
        maximum = self.stress_mean_pa + self.stress_amplitude_pa
        minimum = self.stress_mean_pa - self.stress_amplitude_pa
        if maximum == 0.0:
            raise DurabilityError("stress ratio undefined for zero maximum stress")
        return minimum / maximum


@dataclass(frozen=True, slots=True)
class DamageContribution:
    """Per-cycle damage contribution retained for auditability."""

    quantity: str
    amplitude: float
    mean: float
    equivalent_amplitude: float
    cycles: float
    life_cycles: float
    damage: float
    below_endurance: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "amplitude": self.amplitude,
            "mean": self.mean,
            "equivalentAmplitude": self.equivalent_amplitude,
            "cycles": self.cycles,
            "lifeCycles": self.life_cycles,
            "damage": self.damage,
            "belowEndurance": self.below_endurance,
        }


@dataclass(frozen=True, slots=True)
class DamageResult:
    """Provenance-backed cumulative-fatigue-damage outcome."""

    method: str
    contributions: tuple[DamageContribution, ...]
    damage: float
    safety_factor: float
    validity: Validity
    provenance: Provenance

    @property
    def life_cycles(self) -> float:
        if self.damage <= 0.0:
            return float("inf")
        return 1.0 / self.damage

    def units(self) -> dict[str, str]:
        return {
            "damage": "1",
            "life_cycles": "cycle",
            "safety_factor": "1",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "damage": self.damage,
            "lifeCycles": self.life_cycles,
            "safetyFactor": self.safety_factor,
            "contributions": [item.as_dict() for item in self.contributions],
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def miner_damage(
    curve: SNCurve,
    cycles: tuple[StressCycle, ...],
    *,
    temperature_k: float,
    correction: MeanStressCorrection = MeanStressCorrection.NONE,
    ultimate_pa: float | None = None,
    yield_pa: float | None = None,
    safety_factor: float = 1.0,
) -> DamageResult:
    """Accumulate S-N damage over counted stress cycles (Miner linear rule)."""

    if not cycles:
        raise DataUnavailable("NO_LOAD_CYCLES_FOR_FATIGUE")
    factor = finite(safety_factor, "safety_factor", positive=True)
    contributions: list[DamageContribution] = []
    total = 0.0
    for cycle in cycles:
        amplitude = equivalent_amplitude(
            cycle.stress_amplitude_pa,
            cycle.stress_mean_pa,
            correction,
            ultimate_pa=ultimate_pa,
            yield_pa=yield_pa,
            fatigue_strength_coefficient_pa=curve.fatigue_strength_coefficient_pa,
        )
        life = curve.life_cycles(amplitude, temperature_k=temperature_k)
        below = life == float("inf")
        damage = 0.0 if below else cycle.count * factor / life
        total += damage
        contributions.append(
            DamageContribution(
                quantity="stress_amplitude_pa",
                amplitude=cycle.stress_amplitude_pa,
                mean=cycle.stress_mean_pa,
                equivalent_amplitude=amplitude,
                cycles=cycle.count,
                life_cycles=life,
                damage=damage,
                below_endurance=below,
            )
        )
    provenance = analytical_provenance(
        "miner-sn-damage",
        {
            "curve": curve.identity,
            "curveSource": curve.source,
            "temperatureK": temperature_k,
            "correction": correction.value,
            "safetyFactor": factor,
            "cycles": [
                [cycle.stress_amplitude_pa, cycle.stress_mean_pa, cycle.count]
                for cycle in cycles
            ],
        },
        assumptions=(*MINER_LIMITATIONS, f"mean-stress correction: {correction.value}"),
    )
    passed = total <= 1.0
    return DamageResult(
        method="miner-sn-damage",
        contributions=tuple(contributions),
        damage=total,
        safety_factor=factor,
        validity=Validity(
            passed=passed,
            checks={"damage_within_allowable": passed},
            detail=f"miner:{curve.identity}",
        ),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class StrainCycle:
    """One constant-amplitude strain cycle with a mean stress offset."""

    total_strain_amplitude: float
    stress_mean_pa: float
    count: float

    def __post_init__(self) -> None:
        if finite(self.total_strain_amplitude, "total_strain_amplitude", positive=True) <= 0.0:
            raise DurabilityError("total_strain_amplitude must be positive")
        finite(self.stress_mean_pa, "stress_mean_pa")
        if finite(self.count, "count", positive=True) <= 0.0:
            raise DurabilityError("cycle count must be positive")


def strain_life_damage(
    curve: StrainLifeCurve,
    cycles: tuple[StrainCycle, ...],
    *,
    temperature_k: float,
    safety_factor: float = 1.0,
) -> DamageResult:
    """Accumulate Coffin-Manson strain-life damage with Morrow mean stress."""

    if not cycles:
        raise DataUnavailable("NO_LOAD_CYCLES_FOR_STRAIN_LIFE")
    factor = finite(safety_factor, "safety_factor", positive=True)
    contributions: list[DamageContribution] = []
    total = 0.0
    for cycle in cycles:
        life = curve.cycles_to_failure(
            cycle.total_strain_amplitude,
            mean_stress_pa=cycle.stress_mean_pa,
            temperature_k=temperature_k,
        )
        damage = cycle.count * factor / life
        total += damage
        contributions.append(
            DamageContribution(
                quantity="total_strain_amplitude",
                amplitude=cycle.total_strain_amplitude,
                mean=cycle.stress_mean_pa,
                equivalent_amplitude=cycle.total_strain_amplitude,
                cycles=cycle.count,
                life_cycles=life,
                damage=damage,
                below_endurance=False,
            )
        )
    provenance = analytical_provenance(
        "coffin-manson-strain-life",
        {
            "curve": curve.identity,
            "curveSource": curve.source,
            "temperatureK": temperature_k,
            "safetyFactor": factor,
            "cycles": [
                [cycle.total_strain_amplitude, cycle.stress_mean_pa, cycle.count]
                for cycle in cycles
            ],
        },
        assumptions=(
            "Coffin-Manson strain-life with Morrow mean-stress offset",
            *MINER_LIMITATIONS,
        ),
    )
    passed = total <= 1.0
    return DamageResult(
        method="coffin-manson-strain-life",
        contributions=tuple(contributions),
        damage=total,
        safety_factor=factor,
        validity=Validity(
            passed=passed,
            checks={"damage_within_allowable": passed},
            detail=f"strain-life:{curve.identity}",
        ),
        provenance=provenance,
    )
