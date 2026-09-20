"""Result envelopes: every result carries source/fidelity/units/validity/hash."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest
from .errors import OffdesignInputError
from .matching import PointMatch
from .operating_point import OperatingPoint

SOFTWARE_IDENTITY = "aeroworkbench-turbomachinery-offdesign"
SOFTWARE_VERSION = "1.0.0"


class OffdesignFidelity(StrEnum):
    ANALYTICAL_SCREENING = "analytical-screening"
    MAP_PRELIMINARY = "map-preliminary"
    ENVELOPE_SCREENING = "envelope-screening"
    NATIVE_OFFDESIGN = "native-offdesign"

    def core_level(self) -> FidelityLevel:
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class OffdesignSoftware:
    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_OFFDESIGN_SOFTWARE = OffdesignSoftware()


@dataclass(frozen=True, slots=True)
class OffdesignValidity:
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


def offdesign_provenance(
    source: ResultSource,
    fidelity: OffdesignFidelity,
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


@dataclass(frozen=True, slots=True)
class OffdesignPointResult:
    point_id: str
    thrust_n: float
    shaft_power_w: float
    max_residual: float
    surge_margin: float
    source: str
    fidelity: str
    units: tuple[tuple[str, str], ...]
    validity: OffdesignValidity
    input_hash: str
    software: OffdesignSoftware
    provenance: Provenance
    controls: tuple[tuple[str, float], ...]
    warnings: tuple[str, ...]

    def canonical(self) -> dict[str, object]:
        return {
            "pointId": self.point_id,
            "thrustN": self.thrust_n,
            "shaftPowerW": self.shaft_power_w,
            "maxResidual": self.max_residual,
            "surgeMargin": self.surge_margin,
            "source": self.source,
            "fidelity": self.fidelity,
            "units": [[name, unit] for name, unit in self.units],
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "software": self.software.canonical(),
            "provenance": self.provenance.model_dump(mode="json"),
            "controls": [[name, value] for name, value in self.controls],
            "warnings": list(self.warnings),
        }

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical())


_POINT_UNITS: tuple[tuple[str, str], ...] = (
    ("thrustN", "N"),
    ("shaftPowerW", "W"),
    ("maxResidual", "dimensionless"),
    ("surgeMargin", "dimensionless"),
)


def point_result(
    point: OperatingPoint,
    match: PointMatch,
    *,
    controls: Mapping[str, float] | None = None,
    fidelity: OffdesignFidelity = OffdesignFidelity.MAP_PRELIMINARY,
) -> OffdesignPointResult:
    if match.point_id != point.point_id:
        raise OffdesignInputError("POINT_RESULT_ID_MISMATCH")
    applied = tuple(
        sorted((controls or {}).items(), key=lambda item: item[0])
    )
    checks = {name: passed for name, passed in match.checks}
    validity = OffdesignValidity(
        passed=match.hard_passed,
        checks=checks,
        detail=f"max residual {match.max_residual:.3g}; surge margin {match.surge_margin:.3g}",
    )
    inputs: dict[str, Any] = {
        "point": point.canonical(),
        "match": match.canonical(),
        "controls": [[name, value] for name, value in applied],
        "fidelity": fidelity.value,
    }
    provenance = offdesign_provenance(
        ResultSource.ANALYTICAL,
        fidelity,
        inputs,
        (
            "calorically-perfect gas; station total states only",
            "preliminary-design or declared-map component performance",
            "not a native solver result",
        ),
    )
    return OffdesignPointResult(
        point_id=point.point_id,
        thrust_n=match.thrust_n,
        shaft_power_w=match.shaft_power_w,
        max_residual=match.max_residual,
        surge_margin=match.surge_margin,
        source=ResultSource.ANALYTICAL.value,
        fidelity=fidelity.value,
        units=_POINT_UNITS,
        validity=validity,
        input_hash=provenance.inputs_hash,
        software=DEFAULT_OFFDESIGN_SOFTWARE,
        provenance=provenance,
        controls=applied,
        warnings=match.warnings,
    )


@dataclass(frozen=True, slots=True)
class MultiPointResult:
    outcomes: tuple[dict[str, object], ...]
    point_hashes: tuple[tuple[str, str], ...]
    source: str
    fidelity: str
    units: tuple[tuple[str, str], ...]
    validity: OffdesignValidity
    input_hash: str
    software: OffdesignSoftware
    provenance: Provenance

    def canonical(self) -> dict[str, object]:
        return {
            "outcomes": list(self.outcomes),
            "pointHashes": [[name, value] for name, value in self.point_hashes],
            "source": self.source,
            "fidelity": self.fidelity,
            "units": [[name, unit] for name, unit in self.units],
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "software": self.software.canonical(),
            "provenance": self.provenance.model_dump(mode="json"),
        }

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class EnvelopeCell:
    coordinates: tuple[tuple[str, float], ...]
    status: str
    point_hash: str

    def canonical(self) -> dict[str, object]:
        return {
            "coordinates": [[name, value] for name, value in self.coordinates],
            "status": self.status,
            "pointHash": self.point_hash,
        }


@dataclass(frozen=True, slots=True)
class OperatingEnvelope:
    cells: tuple[EnvelopeCell, ...]
    refined_cells: tuple[EnvelopeCell, ...]
    source: str
    fidelity: str
    units: tuple[tuple[str, str], ...]
    validity: OffdesignValidity
    input_hash: str
    software: OffdesignSoftware
    provenance: Provenance

    def canonical(self) -> dict[str, object]:
        return {
            "cells": [cell.canonical() for cell in self.cells],
            "refinedCells": [cell.canonical() for cell in self.refined_cells],
            "source": self.source,
            "fidelity": self.fidelity,
            "units": [[name, unit] for name, unit in self.units],
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "software": self.software.canonical(),
            "provenance": self.provenance.model_dump(mode="json"),
        }

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical())

    def status_counts(self) -> dict[str, int]:
        counts = {"viable": 0, "constrained": 0, "failed": 0}
        for cell in (*self.cells, *self.refined_cells):
            if cell.status in counts:
                counts[cell.status] += 1
        return counts


__all__ = [
    "DEFAULT_OFFDESIGN_SOFTWARE",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "EnvelopeCell",
    "MultiPointResult",
    "OffdesignFidelity",
    "OffdesignPointResult",
    "OffdesignSoftware",
    "OffdesignValidity",
    "OperatingEnvelope",
    "offdesign_provenance",
    "point_result",
]
