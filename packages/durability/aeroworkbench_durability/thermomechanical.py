"""Thermo-mechanical fatigue from coupled thermal/structural histories.

A coupled thermal result supplies the node-temperature range; structural stress
cycles are paired with the temperature at which they act, and an isothermal S-N
curve valid at that temperature is required. When no curve covers a cycle
temperature the seam fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass

from aeroworkbench_thermal import ThermalResult

from .curves import SNCurve
from .fatigue import (
    DamageContribution,
    DamageResult,
    MeanStressCorrection,
    equivalent_amplitude,
)
from .provenance import MINER_LIMITATIONS, analytical_provenance
from .validity import CapabilityUnavailable, DataUnavailable, Validity, finite

__all__ = [
    "ThermalMechanicalCycle",
    "evaluate_tmf",
    "temperature_range_from_thermal",
]

_KELVIN_OFFSET = 273.15


def temperature_range_from_thermal(result: ThermalResult) -> tuple[float, float]:
    """Convert a coupled thermal result to a node-temperature range in kelvin."""

    if not result.temperatures_c:
        raise DataUnavailable("THERMAL_RESULT_HAS_NO_NODE_TEMPERATURES")
    values = [value + _KELVIN_OFFSET for _, value in result.temperatures_c]
    return (min(values), max(values))


@dataclass(frozen=True, slots=True)
class ThermalMechanicalCycle:
    """One cyclic stress excursion acting at a temperature."""

    stress_amplitude_pa: float
    stress_mean_pa: float
    temperature_k: float
    count: float

    def __post_init__(self) -> None:
        if finite(self.stress_amplitude_pa, "stress_amplitude_pa") < 0.0:
            raise DataUnavailable("stress_amplitude_pa must be non-negative")
        finite(self.stress_mean_pa, "stress_mean_pa")
        finite(self.temperature_k, "temperature_k", positive=True)
        if finite(self.count, "count", positive=True) <= 0.0:
            raise DataUnavailable("cycle count must be positive")


def _select_curve(
    curves: tuple[SNCurve, ...], temperature_k: float
) -> SNCurve:
    for curve in curves:
        if curve.temperature_min_k <= temperature_k <= curve.temperature_max_k:
            return curve
    raise CapabilityUnavailable(
        f"no isothermal S-N curve is valid at {temperature_k} K; "
        "a thermo-mechanical curve or interpolated allowables are required"
    )


def evaluate_tmf(
    cycles: tuple[ThermalMechanicalCycle, ...],
    curves: tuple[SNCurve, ...],
    *,
    correction: MeanStressCorrection = MeanStressCorrection.NONE,
    ultimate_pa: float | None = None,
    yield_pa: float | None = None,
    safety_factor: float = 1.0,
) -> DamageResult:
    """Accumulate fatigue damage across a thermo-mechanical load block."""

    if not cycles:
        raise DataUnavailable("NO_THERMO_MECHANICAL_CYCLES")
    if not curves:
        raise CapabilityUnavailable("no S-N curves supplied for thermo-mechanical fatigue")
    factor = finite(safety_factor, "safety_factor", positive=True)
    contributions: list[DamageContribution] = []
    total = 0.0
    for cycle in cycles:
        curve = _select_curve(curves, cycle.temperature_k)
        amplitude = equivalent_amplitude(
            cycle.stress_amplitude_pa,
            cycle.stress_mean_pa,
            correction,
            ultimate_pa=ultimate_pa,
            yield_pa=yield_pa,
            fatigue_strength_coefficient_pa=curve.fatigue_strength_coefficient_pa,
        )
        life = curve.life_cycles(amplitude, temperature_k=cycle.temperature_k)
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
        "thermo-mechanical-fatigue",
        {
            "temperatureK": [cycle.temperature_k for cycle in cycles],
            "correction": correction.value,
            "safetyFactor": factor,
            "cycles": [
                [
                    cycle.stress_amplitude_pa,
                    cycle.stress_mean_pa,
                    cycle.temperature_k,
                    cycle.count,
                ]
                for cycle in cycles
            ],
        },
        assumptions=(
            "temperature-dependent isothermal S-N curves selected per cycle",
            "phase/oxidation interaction and creep contribution are not modelled here",
            *MINER_LIMITATIONS,
        ),
    )
    passed = total <= 1.0
    return DamageResult(
        method="thermo-mechanical-fatigue",
        contributions=tuple(contributions),
        damage=total,
        safety_factor=factor,
        validity=Validity(
            passed=passed,
            checks={"damage_within_allowable": passed},
            detail="tmf:block",
        ),
        provenance=provenance,
    )
