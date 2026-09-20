"""Shared result envelope for transonic/supersonic external-aero design."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.result_contract import TASK1_ANALYTICAL_RESULT_CONTRACT
from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

from .errors import TransonicContractError

__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "TRANSONIC_SCHEMA_VERSION",
    "TRANSONIC_UNITS",
    "FlowRegime",
    "ShockFeature",
    "ShockFeatureResult",
    "ResultEnvelope",
    "SoftwareIdentity",
    "TransonicFidelity",
    "Validity",
    "analytical_envelope",
    "content_digest",
    "native_envelope",
    "analytical_shock_feature",
]

TRANSONIC_SCHEMA_VERSION = "vs08-transonic-v1"
SOFTWARE_IDENTITY = "aeroworkbench-vehicle-systems-transonic"
SOFTWARE_VERSION = "1.0.0"

TRANSONIC_UNITS: tuple[tuple[str, str], ...] = (
    ("mach_number", "1"),
    ("pressure_coefficient", "1"),
    ("drag_coefficient", "1"),
    ("lift_coefficient", "1"),
    ("pressure_ratio", "1"),
    ("density_ratio", "1"),
    ("temperature_ratio", "1"),
    ("length", "m"),
    ("area", "m2"),
    ("volume", "m3"),
    ("angle", "deg"),
    ("dimensionless", "1"),
)


class TransonicFidelity(StrEnum):
    """Fidelity label carried by a transonic/supersonic screening or native result."""

    ANALYTICAL = "analytical"
    SURROGATE = "surrogate"
    BENCHMARK = "benchmark"
    NATIVE = "native"

    def core_source(self) -> ResultSource:
        if self is TransonicFidelity.NATIVE:
            return ResultSource.NATIVE_SOLVER
        if self is TransonicFidelity.BENCHMARK:
            return ResultSource.BENCHMARK
        if self is TransonicFidelity.SURROGATE:
            return ResultSource.SURROGATE
        return ResultSource.ANALYTICAL


class FlowRegime(StrEnum):
    """External-flow regime by freestream Mach number."""

    INCOMPRESSIBLE = "incompressible"
    SUBSONIC = "subsonic"
    TRANSONIC = "transonic"
    SUPERSONIC = "supersonic"
    HYPERSONIC = "hypersonic"


@dataclass(frozen=True, slots=True)
class ShockFeature:
    """A shock observation; location is absent unless a solver observed it."""

    location: float | None
    reference_surface: str | None
    local_mach: float | None
    pressure_ratio: float | None
    strength_indicator: float | None
    confidence: float
    fidelity: TransonicFidelity
    source: ResultSource
    provenance: Provenance

    def __post_init__(self) -> None:
        for name, value in (
            ("location", self.location),
            ("local_mach", self.local_mach),
            ("pressure_ratio", self.pressure_ratio),
            ("strength_indicator", self.strength_indicator),
            ("confidence", self.confidence),
        ):
            if value is not None and not isinstance(value, (int, float)):
                raise TransonicContractError(f"SHOCK_{name.upper()}_MUST_BE_NUMERIC")
            if value is not None and not isfinite(value):
                raise TransonicContractError(f"SHOCK_{name.upper()}_NOT_FINITE")
        if not 0.0 <= self.confidence <= 1.0:
            raise TransonicContractError("SHOCK_CONFIDENCE_OUT_OF_RANGE")
        if self.location is not None and not self.reference_surface:
            raise TransonicContractError("SHOCK_REFERENCE_SURFACE_REQUIRED_WITH_LOCATION")

    @property
    def location_status(self) -> str:
        return "observed" if self.location is not None else "unavailable"

    @classmethod
    def native(
        cls, *, location: float, reference_surface: str, local_mach: float,
        pressure_ratio: float, strength_indicator: float, confidence: float,
        inputs: dict[str, Any], solver_name: str, solver_version: str, run_id: str,
    ) -> ShockFeature:
        provenance = Provenance.from_inputs(
            source=ResultSource.NATIVE_SOLVER,
            model="vehicle-systems.transonic.shock-feature",
            model_version=solver_version,
            fidelity=FidelityLevel.TRANSIENT,
            inputs=dict(inputs),
            solver_name=solver_name,
            solver_version=solver_version,
            run_id=run_id,
        )
        return cls(location, reference_surface, local_mach, pressure_ratio,
                   strength_indicator, confidence, TransonicFidelity.NATIVE,
                   ResultSource.NATIVE_SOLVER, provenance)

    def canonical(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "locationStatus": self.location_status,
            "referenceSurface": self.reference_surface,
            "localMach": self.local_mach,
            "pressureRatio": self.pressure_ratio,
            "strengthIndicator": self.strength_indicator,
            "confidence": self.confidence,
            "fidelity": self.fidelity.value,
            "source": self.source.value,
            "provenance": dict(self.provenance.model_dump(mode="json")),
        }


@dataclass(frozen=True, slots=True)
class ShockFeatureResult:
    feature: ShockFeature
    validity: Validity

    def canonical(self) -> dict[str, Any]:
        return {"feature": self.feature.canonical(), "validity": self.validity.canonical()}


def analytical_shock_feature(mach: float) -> ShockFeatureResult:
    """Screen a normal shock analytically without inventing its surface location."""
    if not isfinite(mach) or mach <= 1.0:
        raise TransonicContractError("ANALYTICAL_SHOCK_REQUIRES_SUPERSONIC_MACH")
    gamma = 1.4
    pressure_ratio = 1.0 + 2.0 * gamma / (gamma + 1.0) * (mach * mach - 1.0)
    inputs = {"mach": float(mach), "gamma": gamma, "location": None}
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="vehicle-systems.transonic.normal-shock-screening",
        inputs=inputs,
        fidelity=FidelityLevel.ANALYTICAL,
        assumptions=("normal shock relations; shock surface location unavailable",),
    )
    feature = ShockFeature(
        None, None, float(mach), pressure_ratio, pressure_ratio - 1.0, 0.5,
        TransonicFidelity.ANALYTICAL, ResultSource.ANALYTICAL, provenance,
    )
    return ShockFeatureResult(feature, Validity(True, {"location_available": False},
                                                "analytical screening cannot locate shock"))


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a transonic result."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity outcome carried on every transonic result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}


@dataclass(frozen=True, slots=True)
class ResultEnvelope:
    """Source/fidelity/units/validity/hash/software/provenance envelope."""

    source: ResultSource
    fidelity: TransonicFidelity
    units: tuple[tuple[str, str], ...]
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance
    assumptions: tuple[str, ...] = ()
    schema_version: str = TRANSONIC_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "units": {dimension: unit for dimension, unit in self.units},
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
            "assumptions": list(self.assumptions),
            "provenance": dict(self.provenance.model_dump(mode="json")),
            "resultContract": TASK1_ANALYTICAL_RESULT_CONTRACT,
        }


def analytical_envelope(
    *,
    model: str,
    inputs: dict[str, Any],
    validity: Validity,
    units: tuple[tuple[str, str], ...] = TRANSONIC_UNITS,
    assumptions: tuple[str, ...] = (),
) -> ResultEnvelope:
    """Build an analytical envelope from declared inputs and assumptions."""

    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=dict(inputs),
        assumptions=tuple(assumptions),
    )
    return ResultEnvelope(
        source=ResultSource.ANALYTICAL,
        fidelity=TransonicFidelity.ANALYTICAL,
        units=tuple(units),
        validity=validity,
        inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(),
        provenance=provenance,
        assumptions=tuple(assumptions),
    )


def native_envelope(
    *,
    model: str,
    inputs: dict[str, Any],
    validity: Validity,
    solver_name: str,
    solver_version: str,
    run_id: str,
    units: tuple[tuple[str, str], ...] = TRANSONIC_UNITS,
    assumptions: tuple[str, ...] = (),
) -> ResultEnvelope:
    """Build a native envelope carrying mandatory solver identity and run id."""

    provenance = Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=solver_version,
        fidelity=FidelityLevel.TRANSIENT,
        inputs=dict(inputs),
        assumptions=tuple(assumptions),
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
    )
    return ResultEnvelope(
        source=ResultSource.NATIVE_SOLVER,
        fidelity=TransonicFidelity.NATIVE,
        units=tuple(units),
        validity=validity,
        inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(),
        provenance=provenance,
        assumptions=tuple(assumptions),
    )
