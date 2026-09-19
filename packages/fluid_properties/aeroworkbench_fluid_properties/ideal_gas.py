"""Ideal-gas and ideal-mixture property evaluation.

The model evaluates a :class:`WorkingFluid` at a thermodynamic state and returns
a :class:`PropertyResult` for every property it can define. It never extrapolates
outside the species validity ranges and never invents a transport or real-gas
value: unsupported properties fail closed. Enthalpy and entropy are referenced
to the species reference state so differences are physical and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from aeroworkbench_core.types import Provenance

from .errors import FluidCapabilityUnavailableError, FluidValidationError
from .fluid import WorkingFluid
from .property_ids import (
    IDEAL_GAS_FIDELITIES,
    PROPERTY_UNITS,
    PropertyFidelity,
    PropertyId,
)
from .results import PropertyResult, analytical_provenance
from .species import get_species
from .validity import ValidityRange

PRESSURE_VALIDITY = ValidityRange("pressure", "Pa", 1e-6, 1e10)
_MODEL_NAME = "aeroworkbench-fluid-properties:ideal-gas"


def _require_ideal_fidelity(fluid: WorkingFluid, fidelity: PropertyFidelity) -> bool:
    """Return whether the temperature-dependent polynomial model is required."""
    if fidelity not in IDEAL_GAS_FIDELITIES:
        raise FluidValidationError(f"FIDELITY_REQUIRES_NATIVE_BACKEND:{fidelity.value}")
    if fidelity is PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE:
        if not fluid.supports_fidelity(fidelity):
            raise FluidCapabilityUnavailableError(
                f"MISSING_TEMPERATURE_DEPENDENT_CP:{fluid.identity}"
            )
        return True
    if fidelity is PropertyFidelity.CONSTANT_IDEAL_GAS:
        if not fluid.supports_fidelity(PropertyFidelity.CONSTANT_IDEAL_GAS):
            raise FluidCapabilityUnavailableError(f"MISSING_CONSTANT_CP:{fluid.identity}")
        return False
    return fluid.supports_fidelity(PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE)


class IdealGasModel:
    """Evaluate ideal-gas and ideal-mixture thermophysical properties."""

    def __init__(
        self, fluid: WorkingFluid, *, fidelity: PropertyFidelity | None = None
    ) -> None:
        self.fluid = fluid
        self.fidelity = fidelity or fluid.default_fidelity
        _require_ideal_fidelity(fluid, self.fidelity)

    def evaluate(self, *, temperature_k: float, pressure_pa: float) -> IdealGasEvaluation:
        temperature_range = self.fluid.temperature_range()
        temperature_range.require(temperature_k, label="temperature")
        PRESSURE_VALIDITY.require(pressure_pa, label="pressure")

        composition = self.fluid.composition
        specific_gas_constant = composition.specific_gas_constant_j_kg_k
        mass_fractions = composition.mass_fractions()

        cp = sum(
            mass_fraction * get_species(name).cp_j_kg_k(temperature_k)
            for name, mass_fraction in mass_fractions
        )
        cv = cp - specific_gas_constant
        if cv <= 0.0:
            raise FluidValidationError("NONPOSITIVE_CV")
        gamma = cp / cv
        enthalpy = sum(
            mass_fraction * get_species(name).enthalpy_j_kg(temperature_k)
            for name, mass_fraction in mass_fractions
        )
        entropy = sum(
            mass_fraction
            * get_species(name).entropy_j_kg_k(
                temperature_k, composition.mole_fraction(name) * pressure_pa
            )
            for name, mass_fraction in mass_fractions
            if composition.mole_fraction(name) > 0.0
        )
        internal_energy = enthalpy - specific_gas_constant * temperature_k
        speed_of_sound = sqrt(gamma * specific_gas_constant * temperature_k)
        density = pressure_pa / (specific_gas_constant * temperature_k)

        inputs: dict[str, object] = {
            "fluid": self.fluid.digest(),
            "fidelity": self.fidelity.value,
            "temperatureK": temperature_k,
            "pressurePa": pressure_pa,
        }
        provenance = analytical_provenance(
            _MODEL_NAME,
            inputs,
            f"ideal-gas-mixture:{self.fidelity.value}",
        )

        values: dict[PropertyId, float] = {
            PropertyId.DENSITY: density,
            PropertyId.CP: cp,
            PropertyId.CV: cv,
            PropertyId.GAMMA: gamma,
            PropertyId.SPECIFIC_GAS_CONSTANT: specific_gas_constant,
            PropertyId.MOLAR_MASS: composition.molar_mass_kg_per_mol,
            PropertyId.ENTHALPY: enthalpy,
            PropertyId.ENTROPY: entropy,
            PropertyId.INTERNAL_ENERGY: internal_energy,
            PropertyId.SPEED_OF_SOUND: speed_of_sound,
            PropertyId.COMPRESSIBILITY_FACTOR: 1.0,
        }
        results = [
            self._result(prop, value, temperature_range, provenance)
            for prop, value in sorted(values.items(), key=lambda item: item[0].value)
        ]
        results.extend(
            self._transport_results(temperature_k, cp, temperature_range, provenance)
        )
        return IdealGasEvaluation(
            fluid=self.fluid,
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
            fidelity=self.fidelity,
            results=tuple(results),
        )

    def _result(
        self,
        prop: PropertyId,
        value: float,
        temperature_range: ValidityRange,
        provenance: Provenance,
    ) -> PropertyResult:
        return PropertyResult(
            property=prop,
            value_si=value,
            unit=PROPERTY_UNITS[prop],
            fidelity=self.fidelity,
            validity=temperature_range,
            provenance=provenance,
        )

    def _transport_results(
        self,
        temperature_k: float,
        cp_j_kg_k: float,
        temperature_range: ValidityRange,
        provenance: Provenance,
    ) -> list[PropertyResult]:
        transport = self.fluid.transport
        if transport is None or not transport.validity.contains(temperature_k):
            return []
        return [
            self._result(
                PropertyId.VISCOSITY,
                transport.viscosity_pa_s(temperature_k),
                temperature_range,
                provenance,
            ),
            self._result(
                PropertyId.THERMAL_CONDUCTIVITY,
                transport.conductivity_w_m_k(temperature_k, cp_j_kg_k),
                temperature_range,
                provenance,
            ),
            self._result(
                PropertyId.PRANDTL,
                transport.prandtl,
                temperature_range,
                provenance,
            ),
        ]


@dataclass(frozen=True, slots=True)
class IdealGasEvaluation:
    """The evaluated ideal-gas state with one result per available property."""

    fluid: WorkingFluid
    temperature_k: float
    pressure_pa: float
    fidelity: PropertyFidelity
    results: tuple[PropertyResult, ...]

    def get(self, prop: PropertyId) -> PropertyResult:
        for result in self.results:
            if result.property is prop:
                return result
        raise FluidCapabilityUnavailableError(
            f"PROPERTY_NOT_AVAILABLE:{prop.value}:{self.fidelity.value}"
        )

    def value(self, prop: PropertyId) -> float:
        return self.get(prop).value_si

    def has(self, prop: PropertyId) -> bool:
        return any(result.property is prop for result in self.results)

    def canonical(self) -> dict[str, object]:
        return {
            "fluid": self.fluid.identity,
            "fluidDigest": self.fluid.digest(),
            "fidelity": self.fidelity.value,
            "temperatureK": self.temperature_k,
            "pressurePa": self.pressure_pa,
            "properties": {
                result.property.value: result.canonical() for result in self.results
            },
        }


def evaluate_ideal_gas(
    fluid: WorkingFluid,
    *,
    temperature_k: float,
    pressure_pa: float,
    fidelity: PropertyFidelity | None = None,
) -> IdealGasEvaluation:
    """Convenience wrapper building a model and evaluating one state."""
    return IdealGasModel(fluid, fidelity=fidelity).evaluate(
        temperature_k=temperature_k, pressure_pa=pressure_pa
    )
