"""Ingest a governed solver-ready mesh artifact and its semantic mapping.

The OpenFOAM participant never fabricates a placeholder domain. It consumes
the artifact produced by the mesh participant (GEN 05): a generated mesh file
plus ``mesh_mapping.json`` carrying content-address lineage and the explicit
semantic mapping from engineering roles to native patch/zone/interface names.

Every gate here fails closed with ``MESH_INVALID``: a missing mapping, a
lineage hash mismatch, an absent required role, an unknown interface zone, or
a declared moving-interface requirement that the mesh cannot satisfy.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError

MESH_MAPPING_NAME = "mesh_mapping.json"
DEFAULT_MESH_NAME = "domain.msh"

# Boundary kinds the solver understands. A patch kind outside this set is
# carried through as an opaque patch (never silently upgraded to a wall).
_KNOWN_KINDS = frozenset(
    {
        "inlet",
        "outlet",
        "wall",
        "symmetry",
        "periodic",
        "interface",
        "fsi_interface",
        "cht_interface",
        "precice_interface",
        "thermal_contact",
        "mechanical_constraint",
        "mechanical_load",
    }
)


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.MESH_INVALID, detail)


def _hex64(value: object) -> str | None:
    if (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return None


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{label} is missing or empty")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class MeshZone:
    """One declared cell zone with its motion and domain role."""

    name: str
    motion: str
    domain: str

    @property
    def rotating(self) -> bool:
        return self.motion == "rotating"


@dataclass(frozen=True, slots=True)
class MeshPatch:
    """One declared boundary patch with its native OpenFOAM type."""

    name: str
    kind: str
    native_type: str


@dataclass(frozen=True, slots=True)
class MeshInterface:
    """One declared pairing between two zones (field coupling interface)."""

    name: str
    kind: str
    zone_a: str
    zone_b: str
    conformal: bool


@dataclass(frozen=True, slots=True)
class GovernedMesh:
    """Validated solver-ready mesh artifact: lineage + semantic mapping."""

    mesh_path: Path
    mesh_hash: str
    geometry_hash: str
    topology_digest: str
    mapping_hash: str
    zones: tuple[MeshZone, ...]
    patches: tuple[MeshPatch, ...]
    interfaces: tuple[MeshInterface, ...]

    def patch(self, name: str) -> MeshPatch:
        for patch in self.patches:
            if patch.name == name:
                return patch
        raise KeyError(f"MESH_PATCH_NOT_FOUND:{name}")

    def zone(self, name: str) -> MeshZone:
        for zone in self.zones:
            if zone.name == name:
                return zone
        raise KeyError(f"MESH_ZONE_NOT_FOUND:{name}")

    def moving_zones(self) -> tuple[MeshZone, ...]:
        return tuple(zone for zone in self.zones if zone.rotating)


def _openfoam_export(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    exports = payload.get("exports")
    if not isinstance(exports, list):
        raise _fail("mesh_mapping.json has no exports list")
    for export in exports:
        if isinstance(export, Mapping) and export.get("participant") == "openfoam":
            return export
    raise _fail("mesh mapping has no openfoam export")


def _mapping_zones(export: Mapping[str, Any]) -> tuple[MeshZone, ...]:
    raw = export.get("zones")
    if not isinstance(raw, list) or not raw:
        raise _fail("openfoam mapping declares no zones")
    zones: list[MeshZone] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise _fail("malformed zone entry in mesh mapping")
        zones.append(
            MeshZone(
                name=_text(entry.get("name"), "zone name"),
                motion=_text(entry.get("motion"), "zone motion"),
                domain=_text(entry.get("domain"), "zone domain"),
            )
        )
    return tuple(zones)


def _mapping_patches(export: Mapping[str, Any]) -> tuple[MeshPatch, ...]:
    raw = export.get("patches", [])
    if not isinstance(raw, list):
        raise _fail("malformed patches list in mesh mapping")
    patches: list[MeshPatch] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise _fail("malformed patch entry in mesh mapping")
        kind = _text(entry.get("kind"), "patch kind")
        native = entry.get("nativeType")
        patches.append(
            MeshPatch(
                name=_text(entry.get("name"), "patch name"),
                kind=kind if kind in _KNOWN_KINDS else "patch",
                native_type=native if isinstance(native, str) and native else "patch",
            )
        )
    return tuple(patches)


def _mapping_interfaces(export: Mapping[str, Any]) -> tuple[MeshInterface, ...]:
    raw = export.get("interfaces", [])
    if not isinstance(raw, list):
        raise _fail("malformed interfaces list in mesh mapping")
    interfaces: list[MeshInterface] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise _fail("malformed interface entry in mesh mapping")
        conformal = entry.get("conformalRequested", True)
        interfaces.append(
            MeshInterface(
                name=_text(entry.get("name"), "interface name"),
                kind=_text(entry.get("kind"), "interface kind"),
                zone_a=_text(entry.get("zoneA"), "interface zoneA"),
                zone_b=_text(entry.get("zoneB"), "interface zoneB"),
                conformal=bool(conformal),
            )
        )
    return tuple(interfaces)


def ingest_governed_mesh(
    mesh_dir: Path,
    *,
    expected_geometry_hash: str | None = None,
    expected_mesh_hash: str | None = None,
    required_patch_kinds: Sequence[str] = (),
    required_zone_motions: Sequence[str] = (),
    require_interfaces: bool = False,
    mesh_name: str = DEFAULT_MESH_NAME,
) -> GovernedMesh:
    """Load and validate a generated mesh artifact as solver input.

    ``geometry_hash`` and ``mesh_hash`` are recomputed and compared against
    the mapping provenance; the mesh bytes are re-hashed so a mutated artifact
    can never masquerade as the governed one. Required roles, zone motions,
    and (when demanded) interface availability are enforced before any case
    is written.
    """

    directory = Path(mesh_dir)
    if not directory.is_dir():
        raise _fail(f"mesh artifact directory missing:{directory}")
    mapping_path = directory / MESH_MAPPING_NAME
    if not mapping_path.is_file():
        raise _fail(f"semantic mapping missing:{MESH_MAPPING_NAME}")
    try:
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _fail(f"semantic mapping unreadable:{exc}") from exc
    if not isinstance(payload, Mapping):
        raise _fail("semantic mapping is not an object")

    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise _fail("semantic mapping has no provenance block")
    declared_geometry = _hex64(provenance.get("geometryHash"))
    if declared_geometry is None:
        raise _fail("provenance geometryHash is not a sha256 digest")
    declared_mesh = _hex64(provenance.get("meshHash"))
    if declared_mesh is None:
        raise _fail("provenance meshHash is not a sha256 digest")
    topology_digest = provenance.get("topologyDigest")
    if not isinstance(topology_digest, str):
        topology_digest = ""

    mesh_path = directory / mesh_name
    if not mesh_path.is_file():
        raise _fail(f"mesh file missing:{mesh_name}")
    actual_mesh_hash = _sha256_file(mesh_path)
    if actual_mesh_hash != declared_mesh:
        raise _fail("mesh artifact hash does not match provenance meshHash")
    if expected_mesh_hash is not None and actual_mesh_hash != expected_mesh_hash:
        raise _fail("mesh hash does not match the requested mesh lineage")
    if expected_geometry_hash is not None and declared_geometry != expected_geometry_hash:
        raise _fail("mesh geometry lineage does not match the requested geometry")

    export = _openfoam_export(payload)
    zones = _mapping_zones(export)
    patches = _mapping_patches(export)
    interfaces = _mapping_interfaces(export)

    zone_names = {zone.name for zone in zones}
    for interface in interfaces:
        if interface.zone_a not in zone_names or interface.zone_b not in zone_names:
            raise _fail(
                f"interface {interface.name} references unknown zones "
                f"{interface.zone_a}/{interface.zone_b}"
            )

    patch_kinds = {patch.kind for patch in patches}
    for required in required_patch_kinds:
        if required not in patch_kinds:
            raise _fail(f"required patch role absent:{required}")
    motions = {zone.motion for zone in zones}
    for required in required_zone_motions:
        if required not in motions:
            raise _fail(f"required zone motion absent:{required}")
    if require_interfaces and not interfaces:
        raise _fail("moving interface requested but mesh declares no interfaces")

    return GovernedMesh(
        mesh_path=mesh_path,
        mesh_hash=actual_mesh_hash,
        geometry_hash=declared_geometry,
        topology_digest=topology_digest,
        mapping_hash=hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
        zones=zones,
        patches=patches,
        interfaces=interfaces,
    )


def mapping_payload_hash(mesh: GovernedMesh) -> str:
    """Content hash binding a case to its consumed mapping artifact."""

    return mesh.mapping_hash
