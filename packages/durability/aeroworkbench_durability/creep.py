"""Creep, rupture, and creep-fatigue interaction for high-temperature parts.

Norton power-law creep gives a temperature-dependent secondary creep rate.
Larson-Miller rupture curves (with temperature/material validity enforced) give
time to rupture, from which a Robinson life-fraction is accumulated. Combined
creep-fatigue interaction is offered only through an explicitly declared model;
unknown interaction models fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any

from aeroworkbench_core.types import Provenance

from .curves import CreepRuptureCurve
from .fatigue import DamageResult
from .provenance import analytical_provenance
from .validity import (
    CapabilityUnavailable,
    DataUnavailable,
    DurabilityError,
    Validity,
    finite,
)

__all__ = [
    "CreepDamageResult",
    "CreepExposure",
    "InteractionResult",
    "NortonParameters",
    "creep_fatigue_interaction",
    "creep_strain_rate_per_s",
    "robinson_rupture_fraction",
]

_GAS_CONSTANT_J_MOL_K = 8.314462618


@dataclass(frozen=True, slots=True)
class NortonParameters:
    """Norton power-law creep parameters with a sourced temperature validity."""

    coefficient: float
    stress_exponent: float
    activation_energy_j_mol: float
    source: str
    revision: str
    temperature_min_k: float
    temperature_max_k: float
    gas_constant_j_mol_k: float = _GAS_CONSTANT_J_MOL_K

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.revision.strip():
            raise DataUnavailable("NORTON_SOURCE_AND_REVISION_REQUIRED")
        finite(self.coefficient, "coefficient", positive=True)
        finite(self.stress_exponent, "stress_exponent", positive=True)
        finite(self.activation_energy_j_mol, "activation_energy_j_mol", positive=True)
        finite(self.gas_constant_j_mol_k, "gas_constant_j_mol_k", positive=True)
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("NORTON_TEMPERATURE_RANGE_INVALID")

    @property
    def identity(self) -> str:
        return f"norton@{self.revision}"


def creep_strain_rate_per_s(
    parameters: NortonParameters, stress_pa: float, *, temperature_k: float
) -> float:
    """Secondary creep strain rate from the Norton-Arrhenius relation."""

    stress = finite(stress_pa, "stress_pa", positive=True)
    temperature = finite(temperature_k, "temperature_k", positive=True)
    if temperature < parameters.temperature_min_k or temperature > parameters.temperature_max_k:
        raise DataUnavailable(
            f"{parameters.identity}_TEMPERATURE_OUT_OF_VALIDITY:"
            f"{temperature}<>{parameters.temperature_min_k}..{parameters.temperature_max_k}"
        )
    rate = (
        parameters.coefficient
        * stress**parameters.stress_exponent
        * exp(-parameters.activation_energy_j_mol / (parameters.gas_constant_j_mol_k * temperature))
    )
    if rate <= 0.0 or rate != rate or rate == float("inf"):
        raise DataUnavailable(f"{parameters.identity}_STRAIN_RATE_NOT_RESOLVABLE")
    return float(rate)


@dataclass(frozen=True, slots=True)
class CreepExposure:
    """One isothermal, constant-stress creep dwell."""

    stress_pa: float
    temperature_k: float
    time_hours: float

    def __post_init__(self) -> None:
        finite(self.stress_pa, "stress_pa", positive=True)
        finite(self.temperature_k, "temperature_k", positive=True)
        finite(self.time_hours, "time_hours", positive=True)


@dataclass(frozen=True, slots=True)
class CreepDamageResult:
    """Provenance-backed Robinson rupture-fraction outcome."""

    method: str
    fraction: float
    contributions: tuple[tuple[float, float, float, float, float], ...]
    validity: Validity
    provenance: Provenance

    @property
    def damage(self) -> float:
        return self.fraction

    def units(self) -> dict[str, str]:
        return {"fraction": "1"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "fraction": self.fraction,
            "contributions": [list(item) for item in self.contributions],
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def robinson_rupture_fraction(
    curve: CreepRuptureCurve, exposures: tuple[CreepExposure, ...]
) -> CreepDamageResult:
    """Accumulate the Robinson life-fraction ``sum(t / t_rupture)``."""

    if not exposures:
        raise DataUnavailable("NO_CREEP_EXPOSURES")
    contributions: list[tuple[float, float, float, float, float]] = []
    total = 0.0
    for exposure in exposures:
        rupture_hours = curve.rupture_time_hours(
            exposure.stress_pa, temperature_k=exposure.temperature_k
        )
        fraction = exposure.time_hours / rupture_hours
        total += fraction
        contributions.append(
            (
                exposure.stress_pa,
                exposure.temperature_k,
                exposure.time_hours,
                rupture_hours,
                fraction,
            )
        )
    provenance = analytical_provenance(
        "robinson-rupture-fraction",
        {
            "curve": curve.identity,
            "curveSource": curve.source,
            "exposures": [
                [exposure.stress_pa, exposure.temperature_k, exposure.time_hours]
                for exposure in exposures
            ],
        },
        assumptions=(
            "Robinson linear life-fraction rule (time-fraction summation)",
            "isothermal constant-stress dwells; no load-history interaction",
        ),
    )
    passed = total <= 1.0
    return CreepDamageResult(
        method="robinson-rupture-fraction",
        fraction=total,
        contributions=tuple(contributions),
        validity=Validity(
            passed=passed,
            checks={"fraction_within_allowable": passed},
            detail=f"creep:{curve.identity}",
        ),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class InteractionResult:
    """Combined creep-fatigue damage with an explicit interaction model."""

    model: str
    fatigue_damage: float
    creep_damage: float
    combined_damage: float
    validity: Validity
    provenance: Provenance

    @property
    def passed(self) -> bool:
        return self.validity.passed

    def units(self) -> dict[str, str]:
        return {
            "fatigue_damage": "1",
            "creep_damage": "1",
            "combined_damage": "1",
        }


def creep_fatigue_interaction(
    fatigue: DamageResult,
    creep: CreepDamageResult,
    *,
    model: str = "linear",
    allowable_damage: float = 1.0,
) -> InteractionResult:
    """Combine fatigue and creep damage through a declared interaction model."""

    if model != "linear":
        raise CapabilityUnavailable(
            f"creep-fatigue interaction model '{model}' is not available; "
            "only the linear summation model is implemented"
        )
    allowable = finite(allowable_damage, "allowable_damage", positive=True)
    if not fatigue.provenance.inputs_hash or not creep.provenance.inputs_hash:
        raise DurabilityError("interaction requires provenance-backed fatigue and creep damage")
    combined = fatigue.damage + creep.fraction
    passed = combined <= allowable
    provenance = analytical_provenance(
        "linear-creep-fatigue-interaction",
        {
            "fatigueDamage": fatigue.damage,
            "creepDamage": creep.fraction,
            "allowableDamage": allowable,
            "model": model,
        },
        assumptions=(
            "linear creep-fatigue damage summation D_f + D_c <= allowable",
            "no creep-fatigue interaction diagram or hold-time effect is modelled",
        ),
    )
    return InteractionResult(
        model=model,
        fatigue_damage=fatigue.damage,
        creep_damage=creep.fraction,
        combined_damage=combined,
        validity=Validity(
            passed=passed,
            checks={"combined_damage_within_allowable": passed},
            detail=f"creep-fatigue:{model}",
        ),
        provenance=provenance,
    )
