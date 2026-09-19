"""Result envelopes carrying source, fidelity, units, validity, and provenance.

Each :class:`PropertyResult` reuses :class:`aeroworkbench_core.types.Provenance`
(which already carries the input hash for analytical results and the
solver/version/run identity required for native results) and adds the property
identity, canonical SI unit, fidelity label, validity range, and the software
identity of this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .errors import FluidValidationError
from .property_ids import PROPERTY_UNITS, PropertyFidelity, PropertyId
from .validity import ValidityRange

SOFTWARE_NAME = "aeroworkbench-fluid-properties"
SOFTWARE_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a result."""

    name: str = SOFTWARE_NAME
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, object]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity()


def analytical_provenance(
    model: str,
    inputs: dict[str, object],
    *assumptions: str,
) -> Provenance:
    """Build analytical provenance whose input hash is over the canonical inputs."""
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        assumptions=assumptions,
        inputs=inputs,
    )


def native_provenance(
    *,
    model: str,
    solver_name: str,
    solver_version: str,
    run_id: str,
    inputs: dict[str, object],
    assumptions: tuple[str, ...] = (),
) -> Provenance:
    """Build native provenance; the core contract requires full solver identity."""
    return Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        assumptions=assumptions,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        inputs=inputs,
    )


@dataclass(frozen=True, slots=True)
class PropertyResult:
    """One evaluated property with its full provenance and validity."""

    property: PropertyId
    value_si: float
    unit: str
    fidelity: PropertyFidelity
    validity: ValidityRange
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def __post_init__(self) -> None:
        if not isfinite(self.value_si):
            raise FluidValidationError(f"NONFINITE_PROPERTY_VALUE:{self.property}")
        expected = PROPERTY_UNITS[self.property]
        if self.unit != expected:
            raise FluidValidationError(
                f"PROPERTY_UNIT_MISMATCH:{self.property}:{self.unit}:{expected}"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "property": self.property.value,
            "valueSI": self.value_si,
            "unit": self.unit,
            "fidelity": self.fidelity.value,
            "validity": self.validity.canonical(),
            "source": self.provenance.source.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
            "provenance": {
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "solverName": self.provenance.solver_name,
                "solverVersion": self.provenance.solver_version,
                "runId": self.provenance.run_id,
                "assumptions": list(self.provenance.assumptions),
            },
        }
