"""Shared result contract for landing-gear / ground-dynamics results.

Every result carries source, fidelity, SI units, a per-check validity verdict, an
inputs hash, software identity, and provenance. The provenance reuses the core
contract, so a native result can never be silently relabelled analytical and the
inputs hash is a cross-module contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-vehicle-systems-landing-gear"
SOFTWARE_VERSION = "1.0.0"

LG_UNITS: tuple[tuple[str, str], ...] = (
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
    ("angle", "rad"),
    ("dimensionless", "1"),
)


class LandingGearFidelity(StrEnum):
    """The declared fidelity ladder for ground/transition dynamics.

    ``ANALYTICAL`` is a closed-form/definition result, ``GROUND_TRANSIENT`` is a
    bounded deterministic time-domain ground simulation, and ``NATIVE`` is a real
    external engine. A ground transient is never presented as native physics.
    """

    ANALYTICAL = "analytical"
    GROUND_TRANSIENT = "ground-transient"
    NATIVE = "native"

    def core_level(self) -> FidelityLevel:
        if self is LandingGearFidelity.ANALYTICAL:
            return FidelityLevel.ANALYTICAL
        return FidelityLevel.TRANSIENT


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a result."""

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
    """Per-check validity verdict carried on every result."""

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
    """Uniform result metadata: source/fidelity/units/validity/hash/provenance."""

    source: ResultSource
    fidelity: LandingGearFidelity
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
    fidelity: LandingGearFidelity = LandingGearFidelity.ANALYTICAL,
    checks: Mapping[str, bool] | None = None,
    detail: str = "",
    assumptions: Sequence[str] = (),
    source: ResultSource = ResultSource.ANALYTICAL,
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
    units: tuple[tuple[str, str], ...] = LG_UNITS,
) -> ResultMeta:
    """Build deterministic result metadata with an inputs hash and provenance."""

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
    "LG_UNITS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "LandingGearFidelity",
    "ResultMeta",
    "SoftwareIdentity",
    "Validity",
    "result_meta",
]
