"""Revisioned working-fluid definitions with provenance.

A :class:`WorkingFluid` binds an identity and revision to a composition, the
default fidelity to use, and an optional transport model. Its identity digest is
stable, so a downstream result can cite exactly which fluid definition produced
it. All species and transport constants come from the shared registries rather
than being redefined per component.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .canonical import content_digest
from .composition import Composition
from .errors import FluidValidationError
from .property_ids import PropertyFidelity
from .species import get_species
from .transport import SutherlandTransport
from .validity import ValidityRange


class FluidKind(StrEnum):
    """The declared nature of a working fluid."""

    PURE_SPECIES = "pure_species"
    MIXTURE = "mixture"
    HUMID_AIR = "humid_air"
    COMBUSTION_PRODUCTS = "combustion_products"
    USER_MIXTURE = "user_mixture"


@dataclass(frozen=True, slots=True)
class WorkingFluid:
    """An immutable, revisioned working-fluid definition."""

    fluid_id: str
    revision: str
    kind: FluidKind
    composition: Composition
    default_fidelity: PropertyFidelity = PropertyFidelity.CONSTANT_IDEAL_GAS
    transport: SutherlandTransport | None = None
    source: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.fluid_id.strip() or not self.revision.strip():
            raise FluidValidationError("FLUID_IDENTITY_AND_REVISION_REQUIRED")
        if self.kind is FluidKind.PURE_SPECIES and len(self.composition.species) != 1:
            raise FluidValidationError("PURE_SPECIES_REQUIRES_SINGLE_SPECIES")
        for name, _ in self.composition.species:
            get_species(name)

    @property
    def identity(self) -> str:
        return f"{self.fluid_id}@{self.revision}"

    @property
    def molar_mass_kg_per_mol(self) -> float:
        return self.composition.molar_mass_kg_per_mol

    @property
    def specific_gas_constant_j_kg_k(self) -> float:
        return self.composition.specific_gas_constant_j_kg_k

    def temperature_range(self) -> ValidityRange:
        """Intersection of the validity ranges of every constituent species."""
        ranges = [
            get_species(name).temperature_range() for name, _ in self.composition.species
        ]
        result = ranges[0]
        for other in ranges[1:]:
            result = result.intersection(other)
        return result

    def supports_fidelity(self, fidelity: PropertyFidelity) -> bool:
        if fidelity is PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE:
            return all(
                get_species(name).supports_fidelity(temperature_dependent=True)
                for name, _ in self.composition.species
            )
        if fidelity is PropertyFidelity.CONSTANT_IDEAL_GAS:
            return all(
                get_species(name).constant_cp_j_kg_k is not None
                for name, _ in self.composition.species
            )
        return False

    def canonical_payload(self) -> dict[str, object]:
        return {
            "fluidId": self.fluid_id,
            "revision": self.revision,
            "kind": self.kind.value,
            "defaultFidelity": self.default_fidelity.value,
            "composition": self.composition.canonical(),
            "transport": None if self.transport is None else self.transport.canonical(),
            "source": self.source,
            "note": self.note,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def fluid_digest(fluid: WorkingFluid) -> str:
    """Content identity of a working-fluid definition."""
    return content_digest(fluid.canonical_payload())
