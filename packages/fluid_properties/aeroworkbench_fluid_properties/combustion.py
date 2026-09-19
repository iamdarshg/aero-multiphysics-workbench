"""Capability-gated equilibrium-combustion backend seam.

Equilibrium combustion products are a native capability. This module defines the
typed interface the governed native participant implements, probes whether an
equilibrium library is installed at all, and evaluates only through an injected
native backend. When no backend is supplied (or nothing is installed) the
request fails closed. A frozen (fixed-composition) combustion product mixture is
handled by the ideal-mixture path instead and is labelled
``frozen_combustion_gas`` so the two fidelities can never be confused.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from .canonical import content_digest
from .capabilities import BackendCapability, PropertyBackend, probe_backend
from .errors import FluidCapabilityUnavailableError, FluidValidationError
from .fluid import WorkingFluid
from .ideal_gas import PRESSURE_VALIDITY
from .property_ids import PROPERTY_UNITS, PropertyFidelity, PropertyId
from .results import PropertyResult, native_provenance
from .validity import ValidityRange

_MODEL_NAME = "aeroworkbench-fluid-properties:equilibrium-combustion"

EQUILIBRIUM_PROPERTIES: tuple[PropertyId, ...] = (
    PropertyId.DENSITY,
    PropertyId.CP,
    PropertyId.CV,
    PropertyId.GAMMA,
    PropertyId.SPECIFIC_GAS_CONSTANT,
    PropertyId.MOLAR_MASS,
    PropertyId.ENTHALPY,
    PropertyId.ENTROPY,
    PropertyId.INTERNAL_ENERGY,
    PropertyId.SPEED_OF_SOUND,
    PropertyId.VISCOSITY,
    PropertyId.THERMAL_CONDUCTIVITY,
    PropertyId.PRANDTL,
    PropertyId.COMPRESSIBILITY_FACTOR,
)


@runtime_checkable
class EquilibriumBackend(Protocol):
    """The contract a native equilibrium-combustion backend must satisfy."""

    @property
    def backend_id(self) -> str: ...

    @property
    def software_version(self) -> str: ...

    def temperature_validity(self, fluid: WorkingFluid) -> ValidityRange: ...

    def properties(
        self, fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
    ) -> Mapping[PropertyId, float]: ...

    def mechanism(self) -> str | None: ...


def require_equilibrium_capability() -> BackendCapability:
    """Probe for an installed equilibrium library; fail closed if absent."""
    capability = probe_backend(PropertyBackend.CANTERA)
    if not capability.available:
        raise FluidCapabilityUnavailableError(
            f"EQUILIBRIUM_BACKEND_UNAVAILABLE:{capability.detail}"
        )
    return capability


def evaluate_equilibrium(
    fluid: WorkingFluid,
    *,
    backend: EquilibriumBackend | None = None,
    temperature_k: float,
    pressure_pa: float,
    properties: tuple[PropertyId, ...] = EQUILIBRIUM_PROPERTIES,
    run_id: str | None = None,
) -> tuple[PropertyResult, ...]:
    """Evaluate equilibrium products through a native backend; never fabricate."""
    if backend is None:
        capability = probe_backend(PropertyBackend.CANTERA)
        raise FluidCapabilityUnavailableError(
            "EQUILIBRIUM_BACKEND_NOT_SUPPLIED:"
            f"{capability.state}:{capability.detail}"
        )
    validity = backend.temperature_validity(fluid)
    validity.require(temperature_k, label="temperature")
    PRESSURE_VALIDITY.require(pressure_pa, label="pressure")
    payload: dict[str, object] = {
        "fluid": fluid.digest(),
        "fidelity": PropertyFidelity.EQUILIBRIUM_COMBUSTION_GAS.value,
        "temperatureK": temperature_k,
        "pressurePa": pressure_pa,
        "properties": [prop.value for prop in properties],
        "backend": backend.backend_id,
    }
    effective_run_id = run_id or f"equil-{content_digest(payload)[:16]}"
    provenance = native_provenance(
        model=_MODEL_NAME,
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=effective_run_id,
        inputs=payload,
        assumptions=("native equilibrium-combustion backend execution",),
    )
    raw = backend.properties(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    results: list[PropertyResult] = []
    for prop in properties:
        if prop not in raw:
            raise FluidCapabilityUnavailableError(
                f"EQUILIBRIUM_PROPERTY_UNAVAILABLE:{prop.value}:{backend.backend_id}"
            )
        value = float(raw[prop])
        if not math.isfinite(value):
            raise FluidValidationError(f"NONFINITE_EQUILIBRIUM_PROPERTY:{prop.value}")
        results.append(
            PropertyResult(
                property=prop,
                value_si=value,
                unit=PROPERTY_UNITS[prop],
                fidelity=PropertyFidelity.EQUILIBRIUM_COMBUSTION_GAS,
                validity=validity,
                provenance=provenance,
            )
        )
    return tuple(results)
