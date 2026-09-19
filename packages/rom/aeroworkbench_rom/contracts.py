"""Shared result contract for reduced-order maps.

Every sample and prediction carries an explicit source/fidelity label, a
validity verdict, the software identity that produced it, and (for native
samples) mandatory solver identity. A surrogate is always labelled
``SURROGATE`` and is never presented as native physics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-rom"
SOFTWARE_VERSION = "1.0.0"

__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "ExtrapolationPolicy",
    "MapFidelity",
    "SampleKind",
    "SoftwareIdentity",
    "Validity",
    "source_for_kind",
]


class MapFidelity(StrEnum):
    """Fidelity label carried by a map sample or a prediction."""

    ANALYTICAL = "analytical"
    SURROGATE = "surrogate"
    BENCHMARK = "benchmark"
    NATIVE = "native"

    def core_source(self) -> ResultSource:
        if self is MapFidelity.NATIVE:
            return ResultSource.NATIVE_SOLVER
        if self is MapFidelity.BENCHMARK:
            return ResultSource.BENCHMARK
        if self is MapFidelity.SURROGATE:
            return ResultSource.SURROGATE
        return ResultSource.ANALYTICAL


class ExtrapolationPolicy(StrEnum):
    """What happens when a query leaves the declared validity domain.

    There is deliberately no "silent" option: ``REJECT`` raises, ``CLAMP``
    flags the result as extrapolated, and ``ESCALATE`` requests a higher
    fidelity evaluation.
    """

    REJECT = "reject"
    CLAMP = "clamp"
    ESCALATE = "escalate"


class SampleKind(StrEnum):
    """Whether a training sample came from simulation or an experiment."""

    SIMULATION = "simulation"
    EXPERIMENT = "experiment"


def source_for_kind(kind: SampleKind) -> MapFidelity:
    """Measured samples are benchmark data; simulated samples are labelled later."""

    return MapFidelity.BENCHMARK if kind is SampleKind.EXPERIMENT else MapFidelity.ANALYTICAL


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a map or sample."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity outcome carried on every map prediction."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}
