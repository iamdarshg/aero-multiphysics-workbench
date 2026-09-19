"""Capability-gated real-gas backend seam.

Real-gas properties are only produced by an external native backend. When no
backend is installed, every request fails closed with
:class:`FluidCapabilityUnavailableError`; no screening substitute is ever
relabelled as real gas. A backend may also expose derivatives, in which case the
Jacobian seam is available for the same state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aeroworkbench_core.types import Provenance

from .canonical import content_digest
from .capabilities import PropertyBackend, require_backend
from .errors import FluidCapabilityUnavailableError, FluidValidationError
from .fluid import WorkingFluid
from .ideal_gas import PRESSURE_VALIDITY
from .property_ids import PROPERTY_UNITS, PropertyFidelity, PropertyId
from .results import (
    DEFAULT_SOFTWARE,
    PropertyResult,
    SoftwareIdentity,
    native_provenance,
)
from .validity import ValidityRange

_MODEL_NAME = "aeroworkbench-fluid-properties:real-gas"

DEFAULT_REAL_GAS_PROPERTIES: tuple[PropertyId, ...] = (
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

DERIVATIVE_INPUTS: tuple[str, ...] = ("temperature", "pressure")


@runtime_checkable
class RealGasBackend(Protocol):
    """The minimal contract a native real-gas backend must satisfy."""

    @property
    def backend_id(self) -> str: ...

    @property
    def software_version(self) -> str: ...

    def properties(
        self, fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
    ) -> Mapping[PropertyId, float]: ...

    def temperature_validity(self, fluid: WorkingFluid) -> ValidityRange: ...

    def jacobian(
        self,
        fluid: WorkingFluid,
        *,
        temperature_k: float,
        pressure_pa: float,
        properties: tuple[PropertyId, ...],
        with_respect_to: tuple[str, ...],
    ) -> Mapping[tuple[PropertyId, str], float]: ...


class _CoolPropBackend:
    """Adapter over CoolProp's high-accuracy Helmholtz (HEOS) backend."""

    _FLUIDS: dict[str, str] = {
        "air": "Air",
        "co2": "CO2",
        "n2": "Nitrogen",
        "o2": "Oxygen",
        "ar": "Argon",
        "h2o": "Water",
        "co": "CarbonMonoxide",
        "h2": "Hydrogen",
        "ch4": "Methane",
    }

    _PROPERTY_KEYS: dict[PropertyId, str] = {
        PropertyId.DENSITY: "D",
        PropertyId.CP: "C",
        PropertyId.CV: "O",
        PropertyId.ENTHALPY: "H",
        PropertyId.ENTROPY: "S",
        PropertyId.INTERNAL_ENERGY: "U",
        PropertyId.SPEED_OF_SOUND: "A",
        PropertyId.VISCOSITY: "V",
        PropertyId.THERMAL_CONDUCTIVITY: "L",
        PropertyId.PRANDTL: "PRANDTL",
        PropertyId.COMPRESSIBILITY_FACTOR: "Z",
        PropertyId.MOLAR_MASS: "M",
    }

    def __init__(self, version: str) -> None:
        self._version = version

    @property
    def backend_id(self) -> str:
        return "coolprop"

    @property
    def software_version(self) -> str:
        return self._version

    def _fluid_name(self, fluid: WorkingFluid) -> str:
        species = [name for name, _ in fluid.composition.species]
        if len(species) == 1:
            name = self._FLUIDS.get(species[0])
            if name is not None:
                return name
        raise FluidCapabilityUnavailableError(
            f"COOLPROP_FLUID_UNSUPPORTED:{fluid.identity}"
        )

    def temperature_validity(self, fluid: WorkingFluid) -> ValidityRange:
        return fluid.temperature_range()

    def properties(
        self, fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
    ) -> Mapping[PropertyId, float]:
        from CoolProp.CoolProp import PropsSI

        name = self._fluid_name(fluid)
        values: dict[PropertyId, float] = {}
        for prop, key in self._PROPERTY_KEYS.items():
            values[prop] = float(PropsSI(key, "T", temperature_k, "P", pressure_pa, name))
        cp = values[PropertyId.CP]
        cv = values[PropertyId.CV]
        if cv <= 0.0:
            raise FluidValidationError("REAL_GAS_NONPOSITIVE_CV")
        values[PropertyId.GAMMA] = cp / cv
        molar_mass = values[PropertyId.MOLAR_MASS]
        if molar_mass <= 0.0:
            raise FluidValidationError("REAL_GAS_INVALID_MOLAR_MASS")
        values[PropertyId.SPECIFIC_GAS_CONSTANT] = 8.31446261815324 / molar_mass
        return values

    def jacobian(
        self,
        fluid: WorkingFluid,
        *,
        temperature_k: float,
        pressure_pa: float,
        properties: tuple[PropertyId, ...],
        with_respect_to: tuple[str, ...],
    ) -> Mapping[tuple[PropertyId, str], float]:
        raise FluidCapabilityUnavailableError("COOLPROP_JACOBIAN_UNAVAILABLE")


def _resolve_backend(backend: RealGasBackend | None) -> RealGasBackend:
    if backend is not None:
        return backend
    capability = require_backend(PropertyBackend.COOLPROP)
    assert capability.version is not None
    return _CoolPropBackend(capability.version)


def _resolve_run_id(payload: dict[str, object], run_id: str | None) -> str:
    if run_id is not None:
        if not run_id.strip():
            raise FluidValidationError("RUN_ID_REQUIRED")
        return run_id
    return f"realgas-{content_digest(payload)[:16]}"


def evaluate_real_gas(
    fluid: WorkingFluid,
    *,
    backend: RealGasBackend | None = None,
    temperature_k: float,
    pressure_pa: float,
    properties: tuple[PropertyId, ...] = DEFAULT_REAL_GAS_PROPERTIES,
    run_id: str | None = None,
) -> tuple[PropertyResult, ...]:
    """Evaluate real-gas properties; fails closed when no backend is available."""
    resolved = _resolve_backend(backend)
    validity = resolved.temperature_validity(fluid)
    validity.require(temperature_k, label="temperature")
    PRESSURE_VALIDITY.require(pressure_pa, label="pressure")

    payload: dict[str, object] = {
        "fluid": fluid.digest(),
        "fidelity": PropertyFidelity.REAL_GAS.value,
        "temperatureK": temperature_k,
        "pressurePa": pressure_pa,
        "properties": [prop.value for prop in properties],
    }
    provenance = native_provenance(
        model=_MODEL_NAME,
        solver_name=resolved.backend_id,
        solver_version=resolved.software_version,
        run_id=_resolve_run_id(payload, run_id),
        inputs=payload,
        assumptions=("native real-gas backend execution",),
    )
    raw = resolved.properties(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    results: list[PropertyResult] = []
    for prop in properties:
        if prop not in raw:
            raise FluidCapabilityUnavailableError(
                f"REAL_GAS_PROPERTY_UNAVAILABLE:{prop.value}:{resolved.backend_id}"
            )
        value = float(raw[prop])
        if not math.isfinite(value):
            raise FluidValidationError(f"NONFINITE_REAL_GAS_PROPERTY:{prop.value}")
        results.append(
            PropertyResult(
                property=prop,
                value_si=value,
                unit=PROPERTY_UNITS[prop],
                fidelity=PropertyFidelity.REAL_GAS,
                validity=validity,
                provenance=provenance,
            )
        )
    return tuple(results)


@dataclass(frozen=True, slots=True)
class JacobianResult:
    """A capability-gated derivative/Jacobian result for a real-gas state."""

    fluid_identity: str
    temperature_k: float
    pressure_pa: float
    entries: tuple[tuple[PropertyId, str, float], ...]
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def value(self, prop: PropertyId, with_respect_to: str) -> float:
        for entry_prop, entry_wrt, value in self.entries:
            if entry_prop is prop and entry_wrt == with_respect_to:
                return value
        raise FluidCapabilityUnavailableError(
            f"JACOBIAN_ENTRY_UNAVAILABLE:{prop.value}:{with_respect_to}"
        )

    def canonical(self) -> dict[str, object]:
        return {
            "fluid": self.fluid_identity,
            "temperatureK": self.temperature_k,
            "pressurePa": self.pressure_pa,
            "entries": [
                {"property": prop.value, "withRespectTo": wrt, "value": value}
                for prop, wrt, value in self.entries
            ],
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def evaluate_real_gas_jacobian(
    fluid: WorkingFluid,
    *,
    backend: RealGasBackend | None = None,
    temperature_k: float,
    pressure_pa: float,
    properties: tuple[PropertyId, ...] = (PropertyId.ENTHALPY, PropertyId.DENSITY),
    with_respect_to: tuple[str, ...] = DERIVATIVE_INPUTS,
    run_id: str | None = None,
) -> JacobianResult:
    """Return a derivative/Jacobian result or fail closed if unsupported."""
    resolved = _resolve_backend(backend)
    if not hasattr(resolved, "jacobian"):
        raise FluidCapabilityUnavailableError(
            f"BACKEND_HAS_NO_JACOBIAN:{resolved.backend_id}"
        )
    validity = resolved.temperature_validity(fluid)
    validity.require(temperature_k, label="temperature")
    PRESSURE_VALIDITY.require(pressure_pa, label="pressure")
    payload: dict[str, object] = {
        "fluid": fluid.digest(),
        "temperatureK": temperature_k,
        "pressurePa": pressure_pa,
        "properties": [prop.value for prop in properties],
        "withRespectTo": list(with_respect_to),
    }
    provenance = native_provenance(
        model=f"{_MODEL_NAME}:jacobian",
        solver_name=resolved.backend_id,
        solver_version=resolved.software_version,
        run_id=_resolve_run_id(payload, run_id),
        inputs=payload,
        assumptions=("native real-gas backend derivative",),
    )
    raw = resolved.jacobian(
        fluid,
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        properties=properties,
        with_respect_to=with_respect_to,
    )
    entries = tuple(
        (prop, wrt, float(raw[(prop, wrt)]))
        for prop in properties
        for wrt in with_respect_to
        if (prop, wrt) in raw
    )
    if not entries:
        raise FluidCapabilityUnavailableError("JACOBIAN_EMPTY_RESULT")
    return JacobianResult(
        fluid_identity=fluid.identity,
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        entries=entries,
        provenance=provenance,
    )
