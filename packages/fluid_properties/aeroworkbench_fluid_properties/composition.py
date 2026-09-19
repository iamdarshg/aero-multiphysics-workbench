"""Immutable mixture compositions over the species registry.

Compositions are stored canonically as mole fractions sorted by species id so
that identical mixtures are equal and hash identically regardless of input
order. Mass-fraction inputs are converted through the registered molar masses.
"""

from __future__ import annotations

from dataclasses import dataclass

from .canonical import content_digest
from .errors import FluidValidationError
from .species import R_UNIVERSAL_J_PER_MOL_K, get_species

_FRACTION_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class Composition:
    """A mixture expressed as canonical mole fractions."""

    species: tuple[tuple[str, float], ...]
    source: str = ""

    def __post_init__(self) -> None:
        if not self.species:
            raise FluidValidationError("COMPOSITION_REQUIRES_SPECIES")
        ordered = tuple(sorted(self.species))
        names = [name for name, _ in ordered]
        if len(names) != len(set(names)):
            raise FluidValidationError("DUPLICATE_SPECIES")
        total = 0.0
        for name, fraction in ordered:
            get_species(name)
            if not 0.0 <= fraction <= 1.0:
                raise FluidValidationError(f"INVALID_MOLE_FRACTION:{name}")
            total += fraction
        if abs(total - 1.0) > _FRACTION_TOLERANCE:
            raise FluidValidationError("MOLE_FRACTIONS_MUST_SUM_TO_ONE")
        if ordered != self.species:
            object.__setattr__(self, "species", ordered)

    @classmethod
    def from_mole_fractions(
        cls, fractions: tuple[tuple[str, float], ...], *, source: str = ""
    ) -> Composition:
        if not fractions:
            raise FluidValidationError("COMPOSITION_REQUIRES_SPECIES")
        total = sum(fraction for _, fraction in fractions)
        if abs(total - 1.0) > 1e-2:
            raise FluidValidationError("MOLE_FRACTIONS_MUST_SUM_TO_ONE")
        if total <= 0.0:
            raise FluidValidationError("COMPOSITION_MOLE_FRACTIONS_MUST_BE_POSITIVE")
        normalized = tuple((name, fraction / total) for name, fraction in fractions)
        return cls(species=normalized, source=source)

    @classmethod
    def from_mass_fractions(
        cls, fractions: tuple[tuple[str, float], ...], *, source: str = ""
    ) -> Composition:
        """Convert mass fractions to mole fractions using registered molar masses."""
        if not fractions:
            raise FluidValidationError("COMPOSITION_REQUIRES_SPECIES")
        moles: list[tuple[str, float]] = []
        for name, mass_fraction in fractions:
            species = get_species(name)
            if mass_fraction < 0.0:
                raise FluidValidationError(f"INVALID_MASS_FRACTION:{name}")
            moles.append((name, mass_fraction / species.molar_mass_kg_per_mol))
        total_moles = sum(value for _, value in moles)
        if total_moles <= 0.0:
            raise FluidValidationError("COMPOSITION_MASS_FRACTIONS_MUST_SUM_TO_ONE")
        mole_fractions = tuple(
            (name, value / total_moles) for name, value in moles
        )
        return cls(species=mole_fractions, source=source)

    def mole_fraction(self, species_id: str) -> float:
        for name, fraction in self.species:
            if name == species_id:
                return fraction
        return 0.0

    def mole_fractions(self) -> tuple[tuple[str, float], ...]:
        return self.species

    def mass_fractions(self) -> tuple[tuple[str, float], ...]:
        molar_mass = self.molar_mass_kg_per_mol
        return tuple(
            (name, fraction * get_species(name).molar_mass_kg_per_mol / molar_mass)
            for name, fraction in self.species
        )

    @property
    def molar_mass_kg_per_mol(self) -> float:
        return sum(
            fraction * get_species(name).molar_mass_kg_per_mol
            for name, fraction in self.species
        )

    @property
    def specific_gas_constant_j_kg_k(self) -> float:
        return R_UNIVERSAL_J_PER_MOL_K / self.molar_mass_kg_per_mol

    def canonical(self) -> dict[str, object]:
        return {
            "species": [[name, fraction] for name, fraction in self.species],
            "molarMassKgPerMol": self.molar_mass_kg_per_mol,
            "source": self.source,
        }

    def digest(self) -> str:
        return content_digest(self.canonical())
