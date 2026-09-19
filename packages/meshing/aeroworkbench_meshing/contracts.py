"""Shared result envelope for physics-driven meshing.

Every meshing result carries source, fidelity, units, a validity verdict, an
input hash, the software identity that produced it, and a provenance record.
Native results additionally carry mandatory solver identity and a run id. A
planned (analytical) resolution is always labelled ``ANALYTICAL`` and is never
presented as a measured native mesh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.result_contract import TASK1_ANALYTICAL_RESULT_CONTRACT
from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

__all__ = [
    "MESH_SCHEMA_VERSION",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "MeshFidelity",
    "ResultEnvelope",
    "SoftwareIdentity",
    "Validity",
    "analytical_envelope",
    "content_digest",
    "native_envelope",
]

MESH_SCHEMA_VERSION = "advphys14-v1"
SOFTWARE_IDENTITY = "aeroworkbench-meshing"
SOFTWARE_VERSION = "1.0.0"


class MeshFidelity(StrEnum):
    """Fidelity label carried by a mesh plan, receipt, or native result."""

    ANALYTICAL = "analytical"
    SURROGATE = "surrogate"
    BENCHMARK = "benchmark"
    NATIVE = "native"

    def core_source(self) -> ResultSource:
        if self is MeshFidelity.NATIVE:
            return ResultSource.NATIVE_SOLVER
        if self is MeshFidelity.BENCHMARK:
            return ResultSource.BENCHMARK
        if self is MeshFidelity.SURROGATE:
            return ResultSource.SURROGATE
        return ResultSource.ANALYTICAL


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a meshing result."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity outcome carried on every meshing result."""

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
    fidelity: MeshFidelity
    units: tuple[tuple[str, str], ...]
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance
    assumptions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": MESH_SCHEMA_VERSION,
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
    units: tuple[tuple[str, str], ...],
    validity: Validity,
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
        fidelity=MeshFidelity.ANALYTICAL,
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
    units: tuple[tuple[str, str], ...],
    validity: Validity,
    solver_name: str,
    solver_version: str,
    run_id: str,
    assumptions: tuple[str, ...] = (),
) -> ResultEnvelope:
    """Build a native envelope carrying mandatory solver identity and run id."""

    provenance = Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=solver_version,
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=dict(inputs),
        assumptions=tuple(assumptions),
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
    )
    return ResultEnvelope(
        source=ResultSource.NATIVE_SOLVER,
        fidelity=MeshFidelity.NATIVE,
        units=tuple(units),
        validity=validity,
        inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(),
        provenance=provenance,
        assumptions=tuple(assumptions),
    )
