"""Result contracts for vehicle aeroacoustics: source, fidelity, units, validity.

Every screening, observer, metric, and footprint result carries an explicit
source, a fidelity label, unit declarations, a per-check validity verdict, an
input hash, the software identity, and provenance. An analytical screening is
never labelled native, and a native FW-H/CAA result requires explicit solver
identity plus a run id.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

__all__ = [
    "NOISE_UNITS",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "NoiseFidelity",
    "NoiseMeta",
    "NoiseValidity",
    "analytical_provenance",
    "native_provenance",
    "result_meta",
]

SOFTWARE_NAME = "aeroworkbench-vehicle-systems-aeroacoustics"
SOFTWARE_VERSION = "1.0.0"

NOISE_UNITS: tuple[tuple[str, str], ...] = (
    ("frequency", "Hz"),
    ("pressure", "Pa"),
    ("level", "dB"),
    ("distance", "m"),
    ("speed", "m/s"),
    ("time", "s"),
    ("thrust", "N"),
)


class NoiseFidelity(StrEnum):
    """Fidelity label carried by a vehicle-aeroacoustics result."""

    TONAL_SCREENING = "tonal-screening"
    BROADBAND_SCREENING = "broadband-screening"
    AIRFRAME_SCREENING = "airframe-screening"
    INTERACTION_SCREENING = "interaction-screening"
    OBSERVER_ANALYTICAL = "observer-analytical"
    FOOTPRINT = "footprint"
    FW_H_NATIVE = "fw-h-native"

    def core_source(self) -> ResultSource:
        if self is NoiseFidelity.FW_H_NATIVE:
            return ResultSource.NATIVE_SOLVER
        return ResultSource.ANALYTICAL

    def core_level(self) -> FidelityLevel:
        if self is NoiseFidelity.FW_H_NATIVE:
            return FidelityLevel.TRANSIENT
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class NoiseValidity:
    """Per-check validity verdict carried on every aeroacoustics result."""

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
class NoiseMeta:
    """Uniform result metadata: source/fidelity/units/validity/hash/provenance."""

    source: ResultSource
    fidelity: FidelityLevel
    software: str
    software_version: str
    units: tuple[tuple[str, str], ...]
    validity: NoiseValidity
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
    """Provenance for a closed-form/analytical aeroacoustics model output."""

    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
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
    """Provenance for a native CAA/FW-H result; solver identity is mandatory."""

    return Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.TRANSIENT,
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
    fidelity: NoiseFidelity = NoiseFidelity.TONAL_SCREENING,
    provenance: Provenance | None = None,
) -> NoiseMeta:
    """Build deterministic aeroacoustics result metadata with an inputs hash."""

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
    return NoiseMeta(
        source=source,
        fidelity=fidelity.core_level(),
        software=SOFTWARE_NAME,
        software_version=SOFTWARE_VERSION,
        units=NOISE_UNITS,
        validity=NoiseValidity(valid, {} if checks is None else checks, detail),
        input_hash=content_digest(dict(inputs)),
        provenance=provenance,
    )
