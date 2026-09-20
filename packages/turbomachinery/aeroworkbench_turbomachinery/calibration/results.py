"""Shared result envelope: source/fidelity/units/validity/hash/provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-turbomachinery-calibration"
SOFTWARE_VERSION = "1.0.0"


class CalibrationFidelity(StrEnum):
    ANALYTICAL_SCREENING = "analytical-screening"
    CALIBRATED_SCREENING = "calibrated-screening"
    MAP_PRELIMINARY = "map-preliminary"
    NATIVE_CALIBRATION = "native-calibration"

    def core_level(self) -> FidelityLevel:
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class CalibrationSoftware:
    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_CALIBRATION_SOFTWARE = CalibrationSoftware()


@dataclass(frozen=True, slots=True)
class CalibrationValidity:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": {key: self.checks[key] for key in sorted(self.checks)},
            "detail": self.detail,
        }


def calibration_provenance(
    source: ResultSource,
    fidelity: CalibrationFidelity,
    inputs: dict[str, Any],
    assumptions: tuple[str, ...],
) -> Provenance:
    return Provenance.from_inputs(
        source=source,
        model=SOFTWARE_IDENTITY,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity.core_level(),
        inputs=inputs,
        assumptions=assumptions,
    )


def screening_label(*, calibrated: bool) -> str:
    return (
        CalibrationFidelity.CALIBRATED_SCREENING.value
        if calibrated
        else CalibrationFidelity.ANALYTICAL_SCREENING.value
    )
