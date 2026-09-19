"""Shared result contract: fidelity, validity, software identity.

Every environmental result carries an explicit staged fidelity, a per-check
validity verdict, and the software identity that produced it. The provenance
(input hash, source, model identity/version) reuses the core contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel

SOFTWARE_IDENTITY = "aeroworkbench-environmental"
SOFTWARE_VERSION = "1.0.0"


class EnvironmentalFidelity(StrEnum):
    """Staged fidelity ladder for environmental degradation models.

    ``ENVELOPE`` is a declared screening envelope (roughness/accretion limits),
    ``GEOMETRY`` is an explicit geometry-change model, ``EMPIRICAL`` is a
    calibrated empirical correlation, and ``NATIVE`` is a real external engine.
    An envelope is never presented as native physics.
    """

    ENVELOPE = "envelope"
    EMPIRICAL = "empirical"
    GEOMETRY = "geometry"
    NATIVE = "native"

    def core_level(self) -> FidelityLevel:
        if self is EnvironmentalFidelity.NATIVE:
            return FidelityLevel.TRANSIENT
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a result."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity()


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity outcome carried on every result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}


__all__ = [
    "DEFAULT_SOFTWARE",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "EnvironmentalFidelity",
    "SoftwareIdentity",
    "Validity",
]
