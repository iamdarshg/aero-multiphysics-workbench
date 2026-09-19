"""Shared experimental-evidence contract: kind, fidelity, validity, identity.

Every experimental artifact carries an explicit :class:`EvidenceKind` that
separates a measurement from a simulation, an :class:`EvidenceFidelity` label,
a per-check :class:`Validity` verdict, and the :class:`SoftwareIdentity` that
produced it. Measurement evidence is always ``benchmark`` in the shared core
:class:`~aeroworkbench_core.types.ResultSource` vocabulary and can never be
labelled native solver output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-experiment"
SOFTWARE_VERSION = "1.0.0"

__all__ = [
    "DEFAULT_SOFTWARE",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "EvidenceFidelity",
    "EvidenceKind",
    "SoftwareIdentity",
    "Validity",
    "core_level_for",
    "core_source_for",
]


class EvidenceKind(StrEnum):
    """Whether an artifact came from the real world or from a digital model.

    ``MEASUREMENT`` is physical test data, ``SIMULATION`` is a model result,
    ``REPLAY`` is a recorded stream replayed into a controller, and
    ``HARDWARE_IN_LOOP`` is a live hardware/controller stream. A measurement is
    never conflated with a simulation.
    """

    MEASUREMENT = "measurement"
    SIMULATION = "simulation"
    REPLAY = "replay"
    HARDWARE_IN_LOOP = "hardware_in_loop"


class EvidenceFidelity(StrEnum):
    """Fidelity label carried by experimental evidence.

    ``MEASURED`` is direct sensor data, ``DERIVED`` is a reproducible transform
    of measured data, ``CALIBRATED`` is a model fitted to measured data,
    ``REPLAY`` is recorded-stream evidence, and ``HARDWARE`` is live hardware
    evidence. A screening or calibrated model is never presented as measured.
    """

    MEASURED = "measured"
    DERIVED = "derived"
    CALIBRATED = "calibrated"
    REPLAY = "replay"
    HARDWARE = "hardware"


def core_source_for(kind: EvidenceKind) -> ResultSource:
    """Map an evidence kind onto the shared core ``ResultSource`` vocabulary."""

    if kind is EvidenceKind.MEASUREMENT:
        return ResultSource.BENCHMARK
    if kind is EvidenceKind.SIMULATION:
        return ResultSource.ANALYTICAL
    return ResultSource.BENCHMARK


def core_level_for(fidelity: EvidenceFidelity) -> FidelityLevel:
    """Map experimental fidelity onto the shared core fidelity ladder."""

    if fidelity is EvidenceFidelity.HARDWARE:
        return FidelityLevel.TRANSIENT
    return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced an experimental artifact."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity()


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity outcome carried on every experimental artifact."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}
