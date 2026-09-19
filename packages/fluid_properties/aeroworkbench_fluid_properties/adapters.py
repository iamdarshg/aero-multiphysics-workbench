"""Common adapters so external solvers consume one fluid definition.

Each adapter projects the same canonical :class:`WorkingFluid` into the shape a
downstream tool expects, reusing the shared constants instead of redefining
them. Adapters are analytical-only: a fluid whose default fidelity needs a native
backend fails closed here rather than emitting a screening approximation.
"""

from __future__ import annotations

from .errors import FluidCapabilityUnavailableError
from .fluid import WorkingFluid
from .ideal_gas import IdealGasEvaluation, IdealGasModel
from .property_ids import IDEAL_GAS_FIDELITIES, PropertyId


def _ideal_evaluation(
    fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
) -> IdealGasEvaluation:
    if fluid.default_fidelity not in IDEAL_GAS_FIDELITIES:
        raise FluidCapabilityUnavailableError(
            f"ADAPTER_REQUIRES_IDEAL_GAS:{fluid.identity}:{fluid.default_fidelity.value}"
        )
    return IdealGasModel(fluid).evaluate(
        temperature_k=temperature_k, pressure_pa=pressure_pa
    )


def _envelope(fluid: WorkingFluid, evaluation: IdealGasEvaluation) -> dict[str, object]:
    provenance = evaluation.get(PropertyId.CP).provenance
    return {
        "fluid": fluid.identity,
        "fluidDigest": fluid.digest(),
        "fidelity": evaluation.fidelity.value,
        "source": provenance.source.value,
        "inputsHash": provenance.inputs_hash,
    }


def export_cantera_fluid(fluid: WorkingFluid) -> dict[str, object]:
    """Composition-only export for Cantera mechanism consumers."""
    payload: dict[str, object] = {
        "fluid": fluid.identity,
        "fluidDigest": fluid.digest(),
        "kind": fluid.kind.value,
        "moleFractions": {
            name: fraction for name, fraction in fluid.composition.mole_fractions()
        },
        "species": [name for name, _ in fluid.composition.mole_fractions()],
        "source": fluid.source,
    }
    return payload


def export_openfoam_fluid(
    fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
) -> dict[str, object]:
    """Thermophysical constants for an OpenFOAM ``thermophysicalProperties``."""
    evaluation = _ideal_evaluation(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    if not evaluation.has(PropertyId.VISCOSITY):
        raise FluidCapabilityUnavailableError(
            f"OPENFOAM_EXPORT_REQUIRES_TRANSPORT:{fluid.identity}"
        )
    payload = _envelope(fluid, evaluation)
    payload.update(
        {
            "molWeight": fluid.molar_mass_kg_per_mol * 1000.0,
            "rho": evaluation.value(PropertyId.DENSITY),
            "Cp": evaluation.value(PropertyId.CP),
            "Cv": evaluation.value(PropertyId.CV),
            "gamma": evaluation.value(PropertyId.GAMMA),
            "mu": evaluation.value(PropertyId.VISCOSITY),
            "Pr": evaluation.value(PropertyId.PRANDTL),
            "temperatureK": temperature_k,
            "pressurePa": pressure_pa,
        }
    )
    return payload


def export_pycycle_fluid(
    fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
) -> dict[str, object]:
    """Gas-path constants for a pyCycle-style element."""
    evaluation = _ideal_evaluation(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    payload = _envelope(fluid, evaluation)
    payload.update(
        {
            "gamma": evaluation.value(PropertyId.GAMMA),
            "R": evaluation.value(PropertyId.SPECIFIC_GAS_CONSTANT),
            "Cp": evaluation.value(PropertyId.CP),
            "Cv": evaluation.value(PropertyId.CV),
            "molarMass": fluid.molar_mass_kg_per_mol,
            "temperatureK": temperature_k,
            "pressurePa": pressure_pa,
        }
    )
    return payload


def export_reduced_fluid(
    fluid: WorkingFluid,
    *,
    reference_temperature_k: float = 288.15,
    reference_pressure_pa: float = 101325.0,
) -> dict[str, object]:
    """Reduced (constant) gas model for screening models and simple networks."""
    evaluation = _ideal_evaluation(
        fluid, temperature_k=reference_temperature_k, pressure_pa=reference_pressure_pa
    )
    payload = _envelope(fluid, evaluation)
    payload.update(
        {
            "gamma": evaluation.value(PropertyId.GAMMA),
            "R": evaluation.value(PropertyId.SPECIFIC_GAS_CONSTANT),
            "Cp": evaluation.value(PropertyId.CP),
            "Cv": evaluation.value(PropertyId.CV),
            "referenceTemperatureK": reference_temperature_k,
            "referencePressurePa": reference_pressure_pa,
        }
    )
    return payload
