"""Environmental degradation hooks as sourced property modifiers.

Oxidation, erosion, corrosion, and thermal aging reduce a strength or life
allowable by a declared factor, each with its own source, revision, and
temperature validity. Modifiers are applied in declared order and the full
chain is retained in provenance; an out-of-validity modifier fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .validity import DataUnavailable, Validity, finite

__all__ = [
    "DegradationMechanism",
    "DegradationModifier",
    "ModifiedProperty",
    "apply_modifiers",
]


class DegradationMechanism(StrEnum):
    """Generic environmental degradation mechanism."""

    OXIDATION = "oxidation"
    EROSION = "erosion"
    CORROSION = "corrosion"
    THERMAL_AGING = "thermal_aging"


@dataclass(frozen=True, slots=True)
class DegradationModifier:
    """A dimensionless reduction factor with a temperature validity domain."""

    modifier_id: str
    mechanism: DegradationMechanism
    factor: float
    source: str
    revision: str
    temperature_min_k: float
    temperature_max_k: float
    note: str = ""

    def __post_init__(self) -> None:
        if not self.modifier_id.strip() or not self.source.strip() or not self.revision.strip():
            raise DataUnavailable("DEGRADATION_MODIFIER_IDENTITY_AND_SOURCE_REQUIRED")
        value = finite(self.factor, "factor", positive=True)
        if value > 1.0:
            raise DataUnavailable("DEGRADATION_FACTOR_MUST_NOT_EXCEED_ONE")
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("DEGRADATION_TEMPERATURE_RANGE_INVALID")

    @property
    def identity(self) -> str:
        return f"{self.modifier_id}@{self.revision}"

    def apply(self, value: float, *, temperature_k: float) -> float:
        base = finite(value, "value", positive=True)
        temperature = finite(temperature_k, "temperature_k", positive=True)
        if temperature < self.temperature_min_k or temperature > self.temperature_max_k:
            raise DataUnavailable(
                f"{self.identity}_TEMPERATURE_OUT_OF_VALIDITY:"
                f"{temperature}<>{self.temperature_min_k}..{self.temperature_max_k}"
            )
        return base * self.factor


@dataclass(frozen=True, slots=True)
class ModifiedProperty:
    """A property after applying an ordered degradation-modifier chain."""

    name: str
    original: float
    modified: float
    factors: tuple[tuple[str, DegradationMechanism, float], ...]
    provenance: Provenance
    validity: Validity

    @property
    def reduction(self) -> float:
        return self.original - self.modified

    def units(self) -> dict[str, str]:
        return {"original": "-", "modified": "-"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "original": self.original,
            "modified": self.modified,
            "factors": [
                {"id": identity, "mechanism": mechanism.value, "factor": factor}
                for identity, mechanism, factor in self.factors
            ],
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def apply_modifiers(
    name: str,
    value: float,
    modifiers: tuple[DegradationModifier, ...],
    *,
    temperature_k: float,
) -> ModifiedProperty:
    """Apply an ordered modifier chain and retain the full provenance."""

    if not name.strip():
        raise DataUnavailable("MODIFIED_PROPERTY_NAME_REQUIRED")
    original = finite(value, "value", positive=True)
    current = original
    factors: list[tuple[str, DegradationMechanism, float]] = []
    for modifier in modifiers:
        current = modifier.apply(current, temperature_k=temperature_k)
        factors.append((modifier.identity, modifier.mechanism, modifier.factor))
    provenance = analytical_provenance(
        "degradation-modifier-chain",
        {
            "name": name,
            "original": original,
            "temperatureK": temperature_k,
            "modifiers": [
                {
                    "id": identity,
                    "mechanism": mechanism.value,
                    "factor": factor,
                }
                for identity, mechanism, factor in factors
            ],
        },
        assumptions=(
            "degradation factors multiply the allowable in declared order",
            "each factor applies only within its declared temperature validity",
        ),
    )
    return ModifiedProperty(
        name=name,
        original=original,
        modified=current,
        factors=tuple(factors),
        provenance=provenance,
        validity=Validity(
            passed=True,
            checks={"all_modifiers_in_validity": True},
            detail=f"degradation:{name}",
        ),
    )
