"""Canonical property identifiers, units, and the fidelity ladder.

Units are the canonical SI labels used for every stored value. The labels reuse
the same convention as the materials package (a value is stored as an SI float
plus its canonical unit string) instead of introducing a second conversion
system.
"""

from __future__ import annotations

from enum import StrEnum


class PropertyId(StrEnum):
    """Thermophysical and transport properties the platform can expose."""

    DENSITY = "density"
    CP = "cp"
    CV = "cv"
    GAMMA = "gamma"
    SPECIFIC_GAS_CONSTANT = "specific_gas_constant"
    MOLAR_MASS = "molar_mass"
    ENTHALPY = "enthalpy"
    ENTROPY = "entropy"
    INTERNAL_ENERGY = "internal_energy"
    SPEED_OF_SOUND = "speed_of_sound"
    VISCOSITY = "viscosity"
    THERMAL_CONDUCTIVITY = "thermal_conductivity"
    PRANDTL = "prandtl"
    COMPRESSIBILITY_FACTOR = "compressibility_factor"


PROPERTY_UNITS: dict[PropertyId, str] = {
    PropertyId.DENSITY: "kg/m^3",
    PropertyId.CP: "J/(kg K)",
    PropertyId.CV: "J/(kg K)",
    PropertyId.GAMMA: "1",
    PropertyId.SPECIFIC_GAS_CONSTANT: "J/(kg K)",
    PropertyId.MOLAR_MASS: "kg/mol",
    PropertyId.ENTHALPY: "J/kg",
    PropertyId.ENTROPY: "J/(kg K)",
    PropertyId.INTERNAL_ENERGY: "J/kg",
    PropertyId.SPEED_OF_SOUND: "m/s",
    PropertyId.VISCOSITY: "Pa s",
    PropertyId.THERMAL_CONDUCTIVITY: "W/(m K)",
    PropertyId.PRANDTL: "1",
    PropertyId.COMPRESSIBILITY_FACTOR: "1",
}


class PropertyFidelity(StrEnum):
    """How a property was obtained, from cheapest to most faithful."""

    CONSTANT_IDEAL_GAS = "constant_ideal_gas"
    TEMPERATURE_DEPENDENT_IDEAL_MIXTURE = "temperature_dependent_ideal_mixture"
    FROZEN_COMBUSTION_GAS = "frozen_combustion_gas"
    EQUILIBRIUM_COMBUSTION_GAS = "equilibrium_combustion_gas"
    REAL_GAS = "real_gas"


IDEAL_GAS_FIDELITIES: frozenset[PropertyFidelity] = frozenset(
    {
        PropertyFidelity.CONSTANT_IDEAL_GAS,
        PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE,
        PropertyFidelity.FROZEN_COMBUSTION_GAS,
    }
)


def unit_for(prop: PropertyId) -> str:
    """Return the canonical SI unit for a property id."""
    return PROPERTY_UNITS[prop]
