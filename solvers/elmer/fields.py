"""Canonical interface field artifacts for the Elmer thermal participant.

GEN 11 consumes exchange fields in a canonical, lineage-bearing container. This
module writes and reads that container for the two thermal quantities Elmer
owns: ``Temperature`` (K) and ``Heat-Flux`` (W/m^2). Every artifact carries the
mesh hash, geometry hash, mapping hash, interface identity/hash, analysis type,
units, and the native provenance that produced it. Values are never invented:
an artifact is only written from a parsed native result or an explicit caller
provided sample set, and it always records its ``source``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Canonical field identities shared with the coupling/preCICE layer. Kept as
# literals so importing this solver module never pulls the OpenMDAO stack.
FIELD_QUANTITIES: dict[str, tuple[str, str]] = {
    "Temperature": ("temperature", "K"),
    "Heat-Flux": ("heat-flux", "W/m^2"),
    "Interface-Heat-Flow": ("heat-flow", "W"),
}

_FORMAT = "aeroworkbench.interface-field.v1"


def _sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def interface_hash(name: str, kind: str, zone_a: str, zone_b: str, mesh_hash: str) -> str:
    """Content hash binding one interface to its mesh and zone pair."""

    return _sha256(
        {
            "name": name,
            "kind": kind,
            "zoneA": zone_a,
            "zoneB": zone_b,
            "meshHash": mesh_hash,
        }
    )


@dataclass(frozen=True, slots=True)
class FieldEntry:
    """One labelled value carried by an interface field artifact."""

    label: str
    value: float

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("FIELD_ENTRY_LABEL_REQUIRED")
        if self.value != self.value:
            raise ValueError("FIELD_ENTRY_NOT_FINITE")

    def canonical_payload(self, unit: str) -> dict[str, Any]:
        return {"label": self.label, "value": self.value, "unit": unit}


@dataclass(frozen=True, slots=True)
class FieldArtifact:
    """A canonical field artifact with full mesh/interface lineage."""

    field_name: str
    quantity: str
    unit: str
    source: str
    solver: str
    analysis: str
    mesh_hash: str
    geometry_hash: str | None
    mapping_hash: str | None
    interface_name: str
    interface_kind: str
    interface_hash: str
    zone_a: str
    zone_b: str
    entries: tuple[FieldEntry, ...] = ()
    statistics: dict[str, float] = field(default_factory=dict)
    time_s: float | None = None
    input_hash: str | None = None
    case_hash: str | None = None
    run_id: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.field_name not in FIELD_QUANTITIES:
            raise ValueError(f"UNKNOWN_FIELD:{self.field_name}")
        expected_quantity, expected_unit = FIELD_QUANTITIES[self.field_name]
        if self.quantity != expected_quantity or self.unit != expected_unit:
            raise ValueError(f"FIELD_QUANTITY_UNIT_MISMATCH:{self.field_name}")
        if len(self.mesh_hash) != 64:
            raise ValueError("FIELD_ARTIFACT_NEEDS_MESH_HASH")
        if len(self.interface_hash) != 64:
            raise ValueError("FIELD_ARTIFACT_NEEDS_INTERFACE_HASH")
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "statistics", dict(self.statistics))
        for value in self.statistics.values():
            if value != value:
                raise ValueError("FIELD_STATISTIC_NOT_FINITE")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "format": _FORMAT,
            "field": self.field_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "source": self.source,
            "solver": self.solver,
            "analysis": self.analysis,
            "time_s": self.time_s,
            "mesh": {
                "meshHash": self.mesh_hash,
                "geometryHash": self.geometry_hash,
                "mappingHash": self.mapping_hash,
            },
            "interface": {
                "name": self.interface_name,
                "kind": self.interface_kind,
                "zoneA": self.zone_a,
                "zoneB": self.zone_b,
                "interfaceHash": self.interface_hash,
            },
            "entries": [entry.canonical_payload(self.unit) for entry in self.entries],
            "statistics": self.statistics,
            "provenance": {
                "inputHash": self.input_hash,
                "caseHash": self.case_hash,
                "runId": self.run_id,
            },
            "detail": self.detail,
        }


def build_field_artifact(
    *,
    field_name: str,
    mesh_hash: str,
    interface_name: str,
    interface_kind: str,
    zone_a: str,
    zone_b: str,
    entries: tuple[FieldEntry, ...],
    analysis: str = "steady",
    geometry_hash: str | None = None,
    mapping_hash: str | None = None,
    statistics: dict[str, float] | None = None,
    time_s: float | None = None,
    input_hash: str | None = None,
    case_hash: str | None = None,
    run_id: str | None = None,
    source: str = "native_solver",
    detail: str = "",
) -> FieldArtifact:
    """Build one interface field artifact, deriving its interface hash."""

    try:
        quantity, unit = FIELD_QUANTITIES[field_name]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_FIELD:{field_name}") from exc
    return FieldArtifact(
        field_name=field_name,
        quantity=quantity,
        unit=unit,
        source=source,
        solver="elmer",
        analysis=analysis,
        mesh_hash=mesh_hash,
        geometry_hash=geometry_hash,
        mapping_hash=mapping_hash,
        interface_name=interface_name,
        interface_kind=interface_kind,
        interface_hash=interface_hash(interface_name, interface_kind, zone_a, zone_b, mesh_hash),
        zone_a=zone_a,
        zone_b=zone_b,
        entries=entries,
        statistics=statistics or {},
        time_s=time_s,
        input_hash=input_hash,
        case_hash=case_hash,
        run_id=run_id,
        detail=detail,
    )


def field_artifact_path(case_dir: Path, field_name: str) -> Path:
    safe = field_name.replace("/", "_")
    return case_dir / "fields" / f"{safe}.json"


def write_field_artifact(case_dir: Path, artifact: FieldArtifact) -> Path:
    """Write one artifact under ``case_dir/fields``; returns the file path."""

    target = field_artifact_path(case_dir, artifact.field_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact.canonical_payload(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return target


def read_field_artifact(path: Path) -> FieldArtifact:
    """Read one canonical field artifact back into a typed object."""

    if not path.is_file():
        raise FileNotFoundError(f"FIELD_ARTIFACT_MISSING:{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != _FORMAT:
        raise ValueError(f"FIELD_ARTIFACT_FORMAT:{payload.get('format')}")
    mesh = payload.get("mesh", {})
    interface = payload.get("interface", {})
    provenance = payload.get("provenance", {})
    entries = tuple(
        FieldEntry(str(item["label"]), float(item["value"]))
        for item in payload.get("entries", [])
    )
    artifact = FieldArtifact(
        field_name=str(payload["field"]),
        quantity=str(payload["quantity"]),
        unit=str(payload["unit"]),
        source=str(payload.get("source", "unknown")),
        solver=str(payload.get("solver", "elmer")),
        analysis=str(payload.get("analysis", "steady")),
        mesh_hash=str(mesh.get("meshHash", "")),
        geometry_hash=mesh.get("geometryHash"),
        mapping_hash=mesh.get("mappingHash"),
        interface_name=str(interface.get("name", "")),
        interface_kind=str(interface.get("kind", "")),
        interface_hash=str(interface.get("interfaceHash", "")),
        zone_a=str(interface.get("zoneA", "")),
        zone_b=str(interface.get("zoneB", "")),
        entries=entries,
        statistics={
            str(key): float(value) for key, value in payload.get("statistics", {}).items()
        },
        time_s=payload.get("time_s"),
        input_hash=provenance.get("inputHash"),
        case_hash=provenance.get("caseHash"),
        run_id=provenance.get("runId"),
        detail=str(payload.get("detail", "")),
    )
    # Re-derive the interface hash so a tampered artifact is rejected on read.
    expected = interface_hash(
        artifact.interface_name,
        artifact.interface_kind,
        artifact.zone_a,
        artifact.zone_b,
        artifact.mesh_hash,
    )
    if expected != artifact.interface_hash:
        raise ValueError("FIELD_ARTIFACT_INTERFACE_HASH_MISMATCH")
    return artifact
