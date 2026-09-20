"""Uniform result metadata for high-lift / stall aerodynamics (VS 04)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-vehicle-systems-highlift"
SOFTWARE_VERSION = "1.0.0"

HL_UNITS: tuple[tuple[str, str], ...] = (
    ("length", "m"),
    ("area", "m2"),
    ("mass", "kg"),
    ("time", "s"),
    ("velocity", "m/s"),
    ("acceleration", "m/s2"),
    ("force", "N"),
    ("moment", "N.m"),
    ("pressure", "Pa"),
    ("density", "kg/m3"),
    ("angle", "deg"),
    ("frequency", "Hz"),
    ("dimensionless", "1"),
)


class HighLiftFidelity(StrEnum):
    ATTACHED_LINEAR = "attached_linear"
    SECTION_NONLINEAR = "section_nonlinear"
    FINITE_WING_NONLINEAR = "finite_wing_nonlinear"
    UNSTEADY = "unsteady"
    NATIVE = "native"

    def core_level(self) -> FidelityLevel:
        if self is HighLiftFidelity.ATTACHED_LINEAR:
            return FidelityLevel.ANALYTICAL
        return FidelityLevel.TRANSIENT

    def result_source(self) -> ResultSource:
        if self is HighLiftFidelity.NATIVE:
            return ResultSource.NATIVE_SOLVER
        return ResultSource.ANALYTICAL


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("SOFTWARE_IDENTITY_REQUIRED")

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity()


@dataclass(frozen=True, slots=True)
class Validity:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ResultMeta:
    source: ResultSource
    fidelity: HighLiftFidelity
    software: SoftwareIdentity
    units: tuple[tuple[str, str], ...]
    validity: Validity
    input_hash: str
    provenance: Provenance

    def unit_map(self) -> dict[str, str]:
        return {dimension: unit for dimension, unit in self.units}

    def canonical(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "software": self.software.canonical(),
            "units": self.unit_map(),
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "fidelity": self.provenance.fidelity.value,
                "inputsHash": self.provenance.inputs_hash,
                "assumptions": list(self.provenance.assumptions),
                "solverName": self.provenance.solver_name,
                "solverVersion": self.provenance.solver_version,
                "runId": self.provenance.run_id,
            },
        }


def result_meta(
    *,
    model: str,
    inputs: Mapping[str, Any],
    valid: bool,
    fidelity: HighLiftFidelity = HighLiftFidelity.SECTION_NONLINEAR,
    checks: Mapping[str, bool] | None = None,
    detail: str = "",
    assumptions: Sequence[str] = (),
    source: ResultSource = ResultSource.ANALYTICAL,
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
    units: tuple[tuple[str, str], ...] = HL_UNITS,
) -> ResultMeta:
    provenance = Provenance.from_inputs(
        inputs=dict(inputs),
        source=source,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity.core_level(),
        assumptions=tuple(assumptions),
    )
    return ResultMeta(
        source=source,
        fidelity=fidelity,
        software=software,
        units=units,
        validity=Validity(passed=valid, checks=dict(checks or {}), detail=detail),
        input_hash=provenance.inputs_hash,
        provenance=provenance,
    )


__all__ = [
    "DEFAULT_SOFTWARE",
    "HL_UNITS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "HighLiftFidelity",
    "ResultMeta",
    "SoftwareIdentity",
    "Validity",
    "result_meta",
]
