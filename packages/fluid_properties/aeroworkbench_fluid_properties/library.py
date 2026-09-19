"""Canonical working-fluid library.

These are the shared fluid definitions the rest of the platform should consume
instead of re-declaring gas constants. Everything here is built from the species
and transport registries, so changing a species propagates to every fluid,
adapter, and atmosphere that references it.
"""

from __future__ import annotations

from .atmosphere import StandardAtmosphere, standard_atmosphere
from .composition import Composition
from .errors import FluidValidationError
from .fluid import FluidKind, WorkingFluid
from .property_ids import PropertyFidelity
from .species import get_species
from .transport import SutherlandTransport
from .validity import ValidityRange

DRY_AIR_COMPOSITION = Composition.from_mole_fractions(
    (("n2", 0.78084), ("o2", 0.209476), ("ar", 0.00934), ("co2", 0.000412)),
    source="ISO 2533 dry air",
)

AIR_TRANSPORT = SutherlandTransport(
    reference_viscosity_pa_s=1.716e-5,
    reference_temperature_k=273.15,
    sutherland_constant_k=110.4,
    prandtl=0.72,
    validity=ValidityRange("temperature", "K", 180.0, 1600.0),
)


def dry_air_fluid() -> WorkingFluid:
    """The canonical dry-air working fluid (mixture + Sutherland transport)."""
    return WorkingFluid(
        fluid_id="dry-air",
        revision="1",
        kind=FluidKind.MIXTURE,
        composition=DRY_AIR_COMPOSITION,
        default_fidelity=PropertyFidelity.CONSTANT_IDEAL_GAS,
        transport=AIR_TRANSPORT,
        source="ISO 2533 dry air",
    )


def pure_species_fluid(
    species_id: str, *, revision: str = "1", source: str = ""
) -> WorkingFluid:
    """A single-species working fluid from the species registry."""
    get_species(species_id)
    return WorkingFluid(
        fluid_id=species_id,
        revision=revision,
        kind=FluidKind.PURE_SPECIES,
        composition=Composition.from_mole_fractions(((species_id, 1.0),), source=source),
        default_fidelity=PropertyFidelity.CONSTANT_IDEAL_GAS,
        source=source,
    )


def humid_air_fluid(
    *,
    temperature_k: float,
    pressure_pa: float,
    relative_humidity: float,
    revision: str = "1",
) -> WorkingFluid:
    """A humid-air working fluid at a declared state."""
    from .humidity import humid_air_composition

    composition = humid_air_composition(
        DRY_AIR_COMPOSITION,
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        relative_humidity=relative_humidity,
    )
    return WorkingFluid(
        fluid_id="humid-air",
        revision=revision,
        kind=FluidKind.HUMID_AIR,
        composition=composition,
        default_fidelity=PropertyFidelity.CONSTANT_IDEAL_GAS,
        transport=AIR_TRANSPORT,
        source=f"humid air derived from ISO 2533 at rh={relative_humidity}",
    )


def combustion_products_fluid(
    products: tuple[tuple[str, float], ...],
    *,
    fluid_id: str = "combustion-products",
    revision: str = "1",
    source: str = "user-declared frozen combustion products",
) -> WorkingFluid:
    """A frozen (fixed-composition) combustion-product mixture."""
    composition = Composition.from_mole_fractions(products, source=source)
    fidelity = PropertyFidelity.FROZEN_COMBUSTION_GAS
    if all(
        get_species(name).supports_fidelity(temperature_dependent=True)
        for name, _ in composition.species
    ):
        fidelity = PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE
    return WorkingFluid(
        fluid_id=fluid_id,
        revision=revision,
        kind=FluidKind.COMBUSTION_PRODUCTS,
        composition=composition,
        default_fidelity=fidelity,
        source=source,
    )


def fluid_from_payload(payload: dict[str, object]) -> WorkingFluid:
    """Rebuild a working fluid from its canonical payload (lossless round-trip)."""
    composition_payload = payload.get("composition")
    if not isinstance(composition_payload, dict):
        raise FluidValidationError("FLUID_PAYLOAD_REQUIRES_COMPOSITION")
    raw_species = composition_payload.get("species")
    if not isinstance(raw_species, list):
        raise FluidValidationError("FLUID_PAYLOAD_REQUIRES_SPECIES")
    fractions: list[tuple[str, float]] = []
    for entry in raw_species:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise FluidValidationError("FLUID_PAYLOAD_BAD_SPECIES_ENTRY")
        name, fraction = entry
        fractions.append((str(name), float(fraction)))
    composition = Composition.from_mole_fractions(
        tuple(fractions), source=str(composition_payload.get("source", ""))
    )
    transport: SutherlandTransport | None = None
    transport_payload = payload.get("transport")
    if isinstance(transport_payload, dict):
        validity_payload = transport_payload.get("validity")
        if not isinstance(validity_payload, dict):
            raise FluidValidationError("FLUID_PAYLOAD_REQUIRES_TRANSPORT_VALIDITY")
        transport = SutherlandTransport(
            reference_viscosity_pa_s=float(transport_payload["referenceViscosityPaS"]),
            reference_temperature_k=float(transport_payload["referenceTemperatureK"]),
            sutherland_constant_k=float(transport_payload["sutherlandConstantK"]),
            prandtl=float(transport_payload["prandtl"]),
            validity=ValidityRange(
                str(validity_payload["quantity"]),
                str(validity_payload["unit"]),
                float(validity_payload["minimum"]),
                float(validity_payload["maximum"]),
            ),
        )
    return WorkingFluid(
        fluid_id=str(payload["fluidId"]),
        revision=str(payload["revision"]),
        kind=FluidKind(str(payload["kind"])),
        composition=composition,
        default_fidelity=PropertyFidelity(str(payload["defaultFidelity"])),
        transport=transport,
        source=str(payload.get("source", "")),
        note=str(payload.get("note", "")),
    )


ISA: StandardAtmosphere = standard_atmosphere(dry_air_fluid())
