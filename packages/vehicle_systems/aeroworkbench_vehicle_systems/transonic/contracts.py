"""Shared result envelope for transonic/supersonic external-aero design."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.result_contract import TASK1_ANALYTICAL_RESULT_CONTRACT
from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "TRANSONIC_SCHEMA_VERSION",
    "TRANSONIC_UNITS",
    "FlowRegime",
    "ResultEnvelope",
    "SoftwareIdentity",
    "TransonicFidelity",
    "Validity",
    "analytical_envelope",
    "content_digest",
    "native_envelope",
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
