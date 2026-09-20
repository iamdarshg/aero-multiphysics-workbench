"""Provenance-backed calibration-data contract (issue TURBO 11, part A).

Every datum records its source, revision, units, conditions, and validity
range. Raw measurements are immutable; calibration never overwrites them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

from ..canonical import content_digest
from .errors import CalibrationInputError
from .results import (
    DEFAULT_CALIBRATION_SOFTWARE,
    CalibrationFidelity,
    CalibrationSoftware,
    CalibrationValidity,
    calibration_provenance,
)

DATUM_KINDS: tuple[str, ...] = (
    "component_map",
    "rig_measurement",
    "manufacturer_curve",
    "published_benchmark",
    "correlation_coefficient",
    "geometry_measurement",
)

DATUM_SOURCES: tuple[str, ...] = (
    "rig",
    "manufacturer",
    "benchmark",
    "correlation",
    "geometry",
)


class DatumKind(StrEnum):
    COMPONENT_MAP = "component_map"
    RIG_MEASUREMENT = "rig_measurement"
    MANUFACTURER_CURVE = "manufacturer_curve"
    PUBLISHED_BENCHMARK = "published_benchmark"
    CORRELATION_COEFFICIENT = "correlation_coefficient"
    GEOMETRY_MEASUREMENT = "geometry_measurement"


def _finite(value: float, label: str, *, positive: bool = False) -> float:
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise CalibrationInputError(f"NONFINITE:{label}")
    if positive and number <= 0.0:
        raise CalibrationInputError(f"NONPOSITIVE:{label}")
    return number


@dataclass(frozen=True, slots=True)
class CalibrationDatum:
    """One immutable calibration observation with full provenance."""

    datum_id: str
    kind: DatumKind
    quantity: str
    measured: float
    uncertainty: float
    unit: str
    source: str
    revision: str
    inputs: tuple[tuple[str, float], ...] = ()
    conditions: tuple[tuple[str, str], ...] = ()
    validity_range: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.datum_id.strip():
            raise CalibrationInputError("DATUM_ID_REQUIRED")
        if not self.quantity.strip():
            raise CalibrationInputError("DATUM_QUANTITY_REQUIRED")
        if not self.unit.strip():
            raise CalibrationInputError("DATUM_UNIT_REQUIRED")
        if not self.source.strip():
            raise CalibrationInputError("DATUM_SOURCE_REQUIRED")
        if not self.revision.strip():
            raise CalibrationInputError("DATUM_REVISION_REQUIRED")
        _finite(self.measured, f"measured:{self.datum_id}")
        _finite(self.uncertainty, f"uncertainty:{self.datum_id}", positive=True)
        for name, value in self.inputs:
            if not name.strip():
                raise CalibrationInputError(f"DATUM_INPUT_NAME_REQUIRED:{self.datum_id}")
            _finite(value, f"input:{self.datum_id}:{name}")
        names = [name for name, _ in self.inputs]
        if len(names) != len(set(names)):
            raise CalibrationInputError(f"DUPLICATE_INPUT:{self.datum_id}")

    def input_map(self) -> dict[str, float]:
        return dict(self.inputs)

    def canonical(self) -> dict[str, Any]:
        return {
            "datumId": self.datum_id,
            "kind": self.kind.value,
            "quantity": self.quantity,
            "measured": self.measured,
            "uncertainty": self.uncertainty,
            "unit": self.unit,
            "source": self.source,
            "revision": self.revision,
            "inputs": [[name, value] for name, value in self.inputs],
            "conditions": [[name, value] for name, value in self.conditions],
            "validityRange": [[name, value] for name, value in self.validity_range],
        }


def datum_from_mapping(payload: Mapping[str, Any]) -> CalibrationDatum:
    if not isinstance(payload, Mapping):
        raise CalibrationInputError("DATUM_PAYLOAD_MUST_BE_OBJECT")
    try:
        kind = DatumKind(str(payload["kind"]))
    except (KeyError, ValueError) as exc:
        raise CalibrationInputError(f"UNKNOWN_DATUM_KIND:{payload.get('kind')}") from exc
    raw_inputs = payload.get("inputs", [])
    raw_conditions = payload.get("conditions", [])
    raw_range = payload.get("validityRange", [])
    if not isinstance(raw_inputs, Sequence) or isinstance(raw_inputs, (str, bytes)):
        raise CalibrationInputError("DATUM_INPUTS_MUST_BE_ARRAY")
    return CalibrationDatum(
        datum_id=str(payload["datumId"]),
        kind=kind,
        quantity=str(payload["quantity"]),
        measured=float(payload["measured"]),
        uncertainty=float(payload["uncertainty"]),
        unit=str(payload["unit"]),
        source=str(payload["source"]),
        revision=str(payload["revision"]),
        inputs=tuple((str(n), float(v)) for n, v in raw_inputs),
        conditions=tuple((str(n), str(v)) for n, v in raw_conditions),
        validity_range=tuple((str(n), float(v)) for n, v in raw_range),
    )


@dataclass(frozen=True, slots=True)
class CalibrationDataset:
    """An immutable, hashable set of calibration data with a declared split."""

    dataset_id: str
    data: tuple[CalibrationDatum, ...]
    source: str = ResultSource.BENCHMARK.value
    software: CalibrationSoftware = field(default_factory=CalibrationSoftware)

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise CalibrationInputError("DATASET_ID_REQUIRED")
        if not self.data:
            raise CalibrationInputError("DATASET_EMPTY")
        identifiers = [datum.datum_id for datum in self.data]
        if len(identifiers) != len(set(identifiers)):
            raise CalibrationInputError("DUPLICATE_DATUM_ID")
        units = {datum.unit for datum in self.data}
        if len(units) != 1:
            raise CalibrationInputError("DATASET_MIXED_UNITS")

    @property
    def unit(self) -> str:
        return self.data[0].unit

    @property
    def dataset_hash(self) -> str:
        return content_digest(self.canonical())

    def canonical(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "source": self.source,
            "data": [datum.canonical() for datum in sorted(self.data, key=lambda d: d.datum_id)],
        }

    def split(self, *, calibration_fraction: float = 2.0 / 3.0) -> tuple[
        tuple[CalibrationDatum, ...],
        tuple[CalibrationDatum, ...],
    ]:
        _finite(calibration_fraction, "calibration_fraction")
        if not 0.0 < calibration_fraction < 1.0:
            raise CalibrationInputError("SPLIT_FRACTION_OUT_OF_RANGE")
        ordered = tuple(sorted(self.data, key=lambda d: d.datum_id))
        count = max(1, min(len(ordered) - 1, round(len(ordered) * calibration_fraction)))
        return ordered[:count], ordered[count:]

    def provenance(self) -> Provenance:
        return calibration_provenance(
            ResultSource.BENCHMARK,
            CalibrationFidelity.ANALYTICAL_SCREENING,
            self.canonical(),
            (
                "Calibration data ingested with source/revision/units/validity.",
                "Raw values immutable.",
            ),
        )

    def ingest_receipt(
        self, *, passed: bool = True, detail: str = ""
    ) -> IngestReceipt:
        payload = self.canonical()
        validity = CalibrationValidity(
            passed=passed,
            checks={"all-data-provenance-backed": True, "raw-immutable": True},
            detail=detail,
        )
        digest = content_digest(payload)
        return IngestReceipt(
            dataset_id=self.dataset_id,
            count=len(self.data),
            unit=self.unit,
            source=self.source,
            validity=validity,
            input_hash=digest,
            software=self.software,
            provenance=calibration_provenance(
                ResultSource.BENCHMARK,
                CalibrationFidelity.ANALYTICAL_SCREENING,
                payload,
                ("Ingest records provenance only; no fitting performed.",),
            ),
        )


@dataclass(frozen=True, slots=True)
class IngestReceipt:
    dataset_id: str
    count: int
    unit: str
    source: str
    validity: CalibrationValidity
    input_hash: str
    software: CalibrationSoftware
    provenance: Provenance

    def canonical(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "count": self.count,
            "unit": self.unit,
            "source": self.source,
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "software": self.software.canonical(),
            "provenance": self.provenance.model_dump(mode="json"),
        }

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical())


__all__ = [
    "DATUM_KINDS",
    "DATUM_SOURCES",
    "DEFAULT_CALIBRATION_SOFTWARE",
    "CalibrationDataset",
    "CalibrationDatum",
    "DatumKind",
    "IngestReceipt",
    "datum_from_mapping",
]
