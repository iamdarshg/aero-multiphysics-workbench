"""Result contracts for mission simulation: source, fidelity, units, validity.

Every mission, segment, and trajectory result carries an explicit source, a
fidelity label, unit declarations, a validity verdict, an input hash, a
software identity, and provenance. A reduced-map prediction is never labelled
native and a native mission requires explicit solver identity plus a run id.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

__all__ = [
    "MISSION_UNITS",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "MissionFidelity",
    "MissionMeta",
    "MissionValidity",
    "analytical_provenance",
    "native_provenance",
    "reduced_provenance",
    "result_meta",
]

SOFTWARE_NAME = "aeroworkbench-vehicle-systems-mission"
SOFTWARE_VERSION = "1.0.0"

MISSION_UNITS: tuple[tuple[str, str], ...] = (
    ("time", "s"),
    ("distance", "m"),
    ("altitude", "m"),
    ("speed", "m/s"),
    ("mass", "kg"),
    ("energy", "J"),
    ("power", "W"),
    ("force", "N"),
    ("temperature", "K"),
    ("state_of_charge", "1"),
)


class MissionFidelity(StrEnum):
    """Fidelity label carried by a mission result or a performance participant."""

    ANALYTICAL = "analytical"
    REDUCED_MAP = "reduced-map"
    NATIVE = "native"

    def core_source(self) -> ResultSource:
        if self is MissionFidelity.NATIVE:
            return ResultSource.NATIVE_SOLVER
        if self is MissionFidelity.REDUCED_MAP:
            return ResultSource.SURROGATE
        return ResultSource.ANALYTICAL

    def core_level(self) -> FidelityLevel:
        if self is MissionFidelity.NATIVE:
            return FidelityLevel.TRANSIENT
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class MissionValidity:
    """Per-check validity verdict carried on every mission result."""

    passed: bool
    checks: Mapping[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "checks",
            {str(key): bool(value) for key, value in self.checks.items()},
        )

    def as_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}


@dataclass(frozen=True, slots=True)
class MissionMeta:
    """Uniform result metadata: source/fidelity/units/validity/hash/provenance."""

    source: ResultSource
    fidelity: FidelityLevel
    software: str
    software_version: str
    units: tuple[tuple[str, str], ...]
    validity: MissionValidity
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
    """Provenance for a closed-form/analytical mission model output."""

    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        inputs=dict(inputs),
        assumptions=assumptions,
    )


def reduced_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: tuple[str, ...] = (),
) -> Provenance:
    """Provenance for a reduced-map/surrogate mission output."""

    return Provenance.from_inputs(
        source=ResultSource.SURROGATE,
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
    """Provenance for a native mission coordinator; identity is mandatory."""

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
    checks: Mapping[str, bool] | None = None,
    detail: str = "",
    assumptions: tuple[str, ...] = (),
    fidelity: MissionFidelity = MissionFidelity.ANALYTICAL,
    provenance: Provenance | None = None,
) -> MissionMeta:
    """Build deterministic mission result metadata with an inputs hash."""

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
    return MissionMeta(
        source=source,
        fidelity=fidelity.core_level(),
        software=SOFTWARE_NAME,
        software_version=SOFTWARE_VERSION,
        units=MISSION_UNITS,
        validity=MissionValidity(valid, {} if checks is None else checks, detail),
        input_hash=content_digest(dict(inputs)),
        provenance=provenance,
    )
