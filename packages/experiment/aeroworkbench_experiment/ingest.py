"""Data ingestion through a generic adapter seam.

A raw record is preserved verbatim (its bytes are never overwritten), hashed,
and optionally stored in the shared content-addressed artifact cache. A
:class:`TabularIngestion` adapter parses one common tabular/time-series shape;
additional formats plug in by implementing :class:`IngestionAdapter`. Parsed
values are normalized to SI units and the plan timebase, and every resulting
channel records its origin, fidelity, validity, input hash, software identity,
and provenance.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from aeroworkbench_core.types import Provenance
from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_rom.cache import ArtifactRef, MapArtifactCache

from .contracts import (
    DEFAULT_SOFTWARE,
    EvidenceFidelity,
    EvidenceKind,
    SoftwareIdentity,
    Validity,
)
from .errors import IngestionError
from .plan import ExperimentPlan
from .provenance import measurement_provenance
from .units import dimension_of, si_unit_for_dimension, to_si

__all__ = [
    "IngestionAdapter",
    "MeasurementChannel",
    "MeasurementDataset",
    "ParsedTable",
    "RawArtifact",
    "TabularAdapter",
    "ingest_tabular",
]


@dataclass(frozen=True, slots=True)
class ParsedTable:
    """A parsed header plus rows of raw string cells."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise IngestionError("PARSED_TABLE_NEEDS_COLUMNS")
        if len(set(self.columns)) != len(self.columns):
            raise IngestionError("PARSED_TABLE_DUPLICATE_COLUMN")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise IngestionError("PARSED_TABLE_ROW_WIDTH_MISMATCH")


class IngestionAdapter(Protocol):
    """A pluggable parser for one raw tabular/time-series format."""

    @property
    def name(self) -> str: ...

    def parse(self, raw_text: str) -> ParsedTable: ...


@dataclass(frozen=True, slots=True)
class TabularAdapter:
    """A deterministic delimiter-separated parser (CSV/TSV-like)."""

    name: str = "tabular"
    delimiter: str = ","
    comment: str = "#"
    header: bool = True

    def parse(self, raw_text: str) -> ParsedTable:
        if not self.delimiter:
            raise IngestionError("TABULAR_DELIMITER_REQUIRED")
        lines = [
            line.strip()
            for line in raw_text.splitlines()
            if line.strip() and not line.strip().startswith(self.comment)
        ]
        if not lines:
            raise IngestionError("TABULAR_RAW_IS_EMPTY")
        split = [tuple(cell.strip() for cell in line.split(self.delimiter)) for line in lines]
        if self.header:
            columns = split[0]
            rows = tuple(split[1:])
        else:
            columns = tuple(f"c{index}" for index in range(len(split[0])))
            rows = tuple(split)
        return ParsedTable(columns=columns, rows=rows)


@dataclass(frozen=True, slots=True)
class RawArtifact:
    """The verbatim raw record, preserved and content-addressed."""

    artifact_id: str
    media_type: str
    digest: str
    content: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifactId": self.artifact_id,
            "mediaType": self.media_type,
            "digest": self.digest,
            "size": len(self.content.encode("utf-8")),
        }


@dataclass(frozen=True, slots=True)
class MeasurementChannel:
    """A normalized, provenance-backed measured channel (SI units)."""

    name: str
    unit: str
    source_unit: str
    sensor_id: str
    time_s: tuple[float, ...]
    values: tuple[float, ...]
    origin: EvidenceKind
    fidelity: EvidenceFidelity
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance
    derived_from: tuple[str, ...] = ()
    transform: Mapping[str, Any] = field(default_factory=dict)
    filtering: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise IngestionError("CHANNEL_NAME_REQUIRED")
        if len(self.time_s) != len(self.values):
            raise IngestionError(f"CHANNEL_SERIES_LENGTH_MISMATCH:{self.name}")
        if not self.values:
            raise IngestionError(f"CHANNEL_SERIES_EMPTY:{self.name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "sourceUnit": self.source_unit,
            "sensorId": self.sensor_id,
            "origin": self.origin.value,
            "fidelity": self.fidelity.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "derivedFrom": list(self.derived_from),
            "transform": dict(self.transform),
            "filtering": list(self.filtering),
            "timeS": list(self.time_s),
            "values": list(self.values),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class MeasurementDataset:
    """A normalized measurement dataset tied to its plan, condition, and raw record."""

    dataset_id: str
    plan_id: str
    plan_digest: str
    design_revision: str
    configuration: str
    condition_key: str
    raw: RawArtifact
    artifact: ArtifactRef | None
    channels: tuple[MeasurementChannel, ...]
    origin: EvidenceKind
    fidelity: EvidenceFidelity
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise IngestionError("DATASET_ID_REQUIRED")
        if not self.channels:
            raise IngestionError("DATASET_CHANNELS_REQUIRED")
        names = [channel.name for channel in self.channels]
        if len(set(names)) != len(names):
            raise IngestionError("DATASET_DUPLICATE_CHANNEL")

    def channel(self, name: str) -> MeasurementChannel:
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise IngestionError(f"DATASET_UNKNOWN_CHANNEL:{name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "planId": self.plan_id,
            "planDigest": self.plan_digest,
            "designRevision": self.design_revision,
            "configuration": self.configuration,
            "conditionKey": self.condition_key,
            "raw": self.raw.as_dict(),
            "artifact": None if self.artifact is None else self.artifact.as_dict(),
            "channels": [channel.canonical() for channel in self.channels],
            "origin": self.origin.value,
            "fidelity": self.fidelity.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def _parse_float(raw: str, label: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise IngestionError(f"INGESTION_NOT_A_NUMBER:{label}:{raw}") from exc


def ingest_tabular(
    plan: ExperimentPlan,
    raw_text: str,
    *,
    dataset_id: str,
    columns: Mapping[str, tuple[str, str]],
    time_column: str = "time_s",
    time_unit: str = "s",
    adapter: IngestionAdapter | None = None,
    artifact_cache: MapArtifactCache | None = None,
    media_type: str = "text/tabular",
) -> MeasurementDataset:
    """Ingest a raw tabular record into a normalized, provenance-backed dataset.

    ``columns`` maps a plan channel name to its ``(raw_column, source_unit)``.
    Values are converted to SI; the raw record is preserved byte-for-byte.
    """

    if not dataset_id.strip():
        raise IngestionError("DATASET_ID_REQUIRED")
    if not columns:
        raise IngestionError("INGESTION_COLUMNS_REQUIRED")
    active_adapter: IngestionAdapter = adapter or TabularAdapter()
    table = active_adapter.parse(raw_text)
    if time_column not in table.columns:
        raise IngestionError(f"INGESTION_MISSING_TIME_COLUMN:{time_column}")
    time_index = table.columns.index(time_column)

    time_s = tuple(
        to_si(_parse_float(row[time_index], time_column), time_unit) for row in table.rows
    )
    if len(time_s) < 2:
        raise IngestionError("INGESTION_NEEDS_AT_LEAST_TWO_SAMPLES")
    if any(time_s[index] < time_s[index - 1] for index in range(1, len(time_s))):
        raise IngestionError("INGESTION_TIME_NOT_MONOTONIC")

    channels: list[MeasurementChannel] = []
    for channel_name in sorted(columns):
        raw_name, source_unit = columns[channel_name]
        if raw_name not in table.columns:
            raise IngestionError(f"INGESTION_MISSING_COLUMN:{channel_name}:{raw_name}")
        index = table.columns.index(raw_name)
        spec = plan.channel(channel_name)
        values = tuple(to_si(_parse_float(row[index], raw_name), source_unit) for row in table.rows)
        normalized_unit = si_unit_for_dimension(dimension_of(spec.unit))
        range_passed = all(spec.contains(value) for value in values)
        validity = Validity(
            passed=range_passed,
            checks={"expected-range": range_passed, "monotonic-time": True},
            detail="" if range_passed else "one or more samples left the declared range",
        )
        payload = {
            "datasetId": dataset_id,
            "planDigest": plan.digest(),
            "channel": channel_name,
            "rawColumn": raw_name,
            "sourceUnit": source_unit,
            "timeS": list(time_s),
            "values": list(values),
        }
        channels.append(
            MeasurementChannel(
                name=channel_name,
                unit=normalized_unit,
                source_unit=source_unit,
                sensor_id=spec.sensor.sensor_id,
                time_s=time_s,
                values=values,
                origin=EvidenceKind.MEASUREMENT,
                fidelity=EvidenceFidelity.MEASURED,
                validity=validity,
                inputs_hash=content_digest(payload),
                software=DEFAULT_SOFTWARE,
                provenance=measurement_provenance(
                    "tabular-ingestion",
                    payload,
                    assumptions=("raw record preserved verbatim and never overwritten",),
                ),
            )
        )

    raw_digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    raw = RawArtifact(
        artifact_id=f"{dataset_id}:raw",
        media_type=media_type,
        digest=raw_digest,
        content=raw_text,
    )
    cache = artifact_cache if artifact_cache is not None else MapArtifactCache()
    artifact = cache.put({"mediaType": media_type, "digest": raw_digest, "content": raw_text})
    dataset_payload = {
        "datasetId": dataset_id,
        "planDigest": plan.digest(),
        "rawDigest": raw_digest,
        "channels": [channel.digest() for channel in channels],
    }
    validity = Validity(
        passed=all(channel.validity.passed for channel in channels),
        checks={
            f"{channel.name}:expected-range": channel.validity.passed for channel in channels
        },
        detail="",
    )
    return MeasurementDataset(
        dataset_id=dataset_id,
        plan_id=plan.plan_id,
        plan_digest=plan.digest(),
        design_revision=plan.design_revision,
        configuration=plan.configuration,
        condition_key=plan.condition_key,
        raw=raw,
        artifact=artifact,
        channels=tuple(channels),
        origin=EvidenceKind.MEASUREMENT,
        fidelity=EvidenceFidelity.MEASURED,
        validity=validity,
        inputs_hash=content_digest(dataset_payload),
        software=DEFAULT_SOFTWARE,
        provenance=measurement_provenance(
            "tabular-ingestion",
            dataset_payload,
            assumptions=("raw record preserved verbatim and never overwritten",),
        ),
    )
