"""Composite fatigue seam that never applies isotropic life formulas to a laminate.

Isotropic S-N curves are not valid for laminates. Composite fatigue therefore
requires laminate-specific allowables bound to the exact laminate digest; when
those allowables are absent the seam fails closed instead of substituting an
isotropic model.
"""

from __future__ import annotations

from dataclasses import dataclass

from aeroworkbench_materials import LaminateRevision, laminate_digest

from .fatigue import DamageContribution, DamageResult, StressCycle
from .provenance import MINER_LIMITATIONS, analytical_provenance
from .validity import CapabilityUnavailable, DataUnavailable, Validity, finite

__all__ = [
    "CompositeFatigueAllowables",
    "evaluate_composite_fatigue",
]


@dataclass(frozen=True, slots=True)
class CompositeFatigueAllowables:
    """Laminate-specific fatigue allowables bound to one laminate digest."""

    laminate_digest: str
    revision: str
    source: str
    stress_amplitude_allowable_pa: float
    reference_life_cycles: float
    fatigue_strength_exponent: float
    temperature_min_k: float
    temperature_max_k: float
    note: str = ""

    def __post_init__(self) -> None:
        if len(self.laminate_digest) != 64:
            raise DataUnavailable("COMPOSITE_ALLOWABLES_REQUIRE_LAMINATE_DIGEST")
        if not self.revision.strip() or not self.source.strip():
            raise DataUnavailable("COMPOSITE_ALLOWABLES_SOURCE_AND_REVISION_REQUIRED")
        finite(self.stress_amplitude_allowable_pa, "stress_amplitude_allowable_pa", positive=True)
        finite(self.reference_life_cycles, "reference_life_cycles", positive=True)
        if finite(self.fatigue_strength_exponent, "fatigue_strength_exponent") >= 0.0:
            raise DataUnavailable("COMPOSITE_EXPONENT_MUST_BE_NEGATIVE")
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("COMPOSITE_TEMPERATURE_RANGE_INVALID")

    @property
    def identity(self) -> str:
        return f"laminate-fatigue@{self.revision}"

    def life_cycles(self, stress_amplitude_pa: float, *, temperature_k: float) -> float:
        amplitude = finite(stress_amplitude_pa, "stress_amplitude_pa", positive=True)
        temperature = finite(temperature_k, "temperature_k", positive=True)
        if temperature < self.temperature_min_k or temperature > self.temperature_max_k:
            raise DataUnavailable(f"{self.identity}_TEMPERATURE_OUT_OF_VALIDITY")
        return float(
            self.reference_life_cycles
            * (amplitude / self.stress_amplitude_allowable_pa)
            ** (1.0 / self.fatigue_strength_exponent)
        )


def evaluate_composite_fatigue(
    laminate: LaminateRevision,
    cycles: tuple[StressCycle, ...],
    *,
    allowables: CompositeFatigueAllowables | None = None,
    temperature_k: float,
    safety_factor: float = 1.0,
) -> DamageResult:
    """Accumulate laminate fatigue damage from laminate-specific allowables only.

    Without laminate-specific allowables this raises :class:`CapabilityUnavailable`;
    isotropic S-N formulas are never applied to a laminate.
    """

    if allowables is None:
        raise CapabilityUnavailable(
            "laminate fatigue allowables unavailable for "
            f"{laminate.identity}; isotropic fatigue formulas are not valid for laminates"
        )
    digest = laminate_digest(laminate)
    if allowables.laminate_digest != digest:
        raise DataUnavailable(
            "COMPOSITE_ALLOWABLES_DIGEST_MISMATCH: allowables do not belong to this laminate"
        )
    if not cycles:
        raise DataUnavailable("NO_LOAD_CYCLES_FOR_COMPOSITE_FATIGUE")
    factor = finite(safety_factor, "safety_factor", positive=True)
    contributions: list[DamageContribution] = []
    total = 0.0
    for cycle in cycles:
        life = allowables.life_cycles(
            cycle.stress_amplitude_pa, temperature_k=temperature_k
        )
        damage = cycle.count * factor / life
        total += damage
        contributions.append(
            DamageContribution(
                quantity="stress_amplitude_pa",
                amplitude=cycle.stress_amplitude_pa,
                mean=cycle.stress_mean_pa,
                equivalent_amplitude=cycle.stress_amplitude_pa,
                cycles=cycle.count,
                life_cycles=life,
                damage=damage,
                below_endurance=False,
            )
        )
    provenance = analytical_provenance(
        "laminate-fatigue-damage",
        {
            "laminate": laminate.identity,
            "laminateDigest": digest,
            "allowables": allowables.identity,
            "allowablesSource": allowables.source,
            "temperatureK": temperature_k,
            "safetyFactor": factor,
            "cycles": [
                [cycle.stress_amplitude_pa, cycle.stress_mean_pa, cycle.count]
                for cycle in cycles
            ],
        },
        assumptions=(
            "laminate-specific allowables; no isotropic-equivalence substitution",
            *MINER_LIMITATIONS,
        ),
    )
    passed = total <= 1.0
    return DamageResult(
        method="laminate-fatigue-damage",
        contributions=tuple(contributions),
        damage=total,
        safety_factor=factor,
        validity=Validity(
            passed=passed,
            checks={"damage_within_allowable": passed},
            detail=f"laminate-fatigue:{laminate.identity}",
        ),
        provenance=provenance,
    )
