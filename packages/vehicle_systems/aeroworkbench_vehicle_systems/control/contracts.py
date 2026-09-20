"""Result contracts for vehicle-level control: source, fidelity, units, validity.

Every allocation, synthesis, handling-quality, and closed-loop result carries
an explicit source, a fidelity label, unit declarations, a validity verdict,
an input hash, a software identity, and provenance. A screening result is
never labelled native.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

__all__ = [
    "CONTROL_UNITS",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "ControlFidelity",
    "ControlMeta",
    "ControlValidity",
    "analytical_provenance",
    "native_provenance",
    "result_meta",
]

SOFTWARE_NAME = "aeroworkbench-vehicle-systems-control"
SOFTWARE_VERSION = "1.0.0"

CONTROL_UNITS: tuple[tuple[str, str], ...] = (
    ("moment", "N.m"),
    ("force", "N"),
    ("angle", "rad"),
    ("angular_rate", "rad/s"),
    ("time", "s"),
    ("frequency", "Hz"),
    ("dimensionless", "1"),
)


class ControlFidelity(StrEnum):
    """Fidelity label carried by a vehicle-control result."""

    ANALYTICAL = "analytical"
    NATIVE = "native"

    def core_source(self) -> ResultSource:
        if self is ControlFidelity.NATIVE:
            return ResultSource.NATIVE_SOLVER
        return ResultSource.ANALYTICAL

    def core_level(self) -> FidelityLevel:
        if self is ControlFidelity.NATIVE:
            return FidelityLevel.TRANSIENT
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class ControlValidity:
    """Per-check validity verdict carried on every control result."""

    passed: bool
    checks: tuple[tuple[str, bool], ...] = ()
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": {key: value for key, value in self.checks},
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ControlMeta:
    """Uniform result metadata: source/fidelity/units/validity/hash/provenance."""

    source: ResultSource
    fidelity: FidelityLevel
    software: str
    software_version: str
    units: tuple[tuple[str, str], ...]
    validity: ControlValidity
    input_hash: str
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "software": {"name": self.software, "version": self.software_version},
            "units": {dimension: unit for dimension, unit in self.units},
            "validity": self.validity.as_dict(),
            "inputHash": self.input_hash,
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "fidelity": self.provenance.fidelity.value,
                "inputsHash": self.provenance.inputs_hash,
                "assumptions": list(self.provenance.assumptions),
            },
        }


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: tuple[str, ...] = (),
) -> Provenance:
    """Provenance for a closed-form/analytical control model output."""
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        inputs=dict(inputs),
        assumptions=assumptions,
    )


def native_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    solver_name: str,
    solver_version: str,
    run_id: str,
    assumptions: tuple[str, ...] = (),
) -> Provenance:
    """Provenance for a native closed-loop coordinator; identity is mandatory."""
    return Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        inputs=dict(inputs),
        assumptions=assumptions,
    )


def result_meta(
    *,
    model: str,
    inputs: Mapping[str, Any],
    valid: bool,
    checks: tuple[tuple[str, bool], ...] = (),
    detail: str = "",
    assumptions: tuple[str, ...] = (),
    fidelity: ControlFidelity = ControlFidelity.ANALYTICAL,
    provenance: Provenance | None = None,
) -> ControlMeta:
    """Build deterministic control result metadata with an inputs hash."""
    source = fidelity.core_source()
    if provenance is None:
        provenance = Provenance.from_inputs(
            source=source,
            model=model,
            model_version=SOFTWARE_VERSION,
            fidelity=fidelity.core_level(),
            inputs=dict(inputs),
            assumptions=assumptions,
        )
    return ControlMeta(
        source=source,
        fidelity=fidelity.core_level(),
        software=SOFTWARE_NAME,
        software_version=SOFTWARE_VERSION,
        units=CONTROL_UNITS,
        validity=ControlValidity(valid, tuple(checks), detail),
        input_hash=provenance.inputs_hash,
        provenance=provenance,
    )
