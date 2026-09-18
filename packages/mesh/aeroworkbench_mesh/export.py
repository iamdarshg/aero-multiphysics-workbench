"""Solver-oriented mesh mappings for OpenFOAM, Code_Aster/Elmer, and preCICE.

Solvers receive an explicit, provenance-backed mapping from physical groups to
their native patch/zone/interface names instead of rediscovering semantic
groups by hand. Only names and identities are exported here; no solver physics
is synthesized.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .semantics import MeshRequestMapping, ResolvedMeshRequest

_DEFAULT_PARTICIPANTS: tuple[str, ...] = (
    "openfoam",
    "code_aster",
    "elmer",
    "precice",
)

# Boundary kind -> OpenFOAM patch type. Unknown kinds stay explicit as
# ``patch`` so they are never silently treated as walls.
_OPENFOAM_PATCH_TYPES: dict[str, str] = {
    "inlet": "patch",
    "outlet": "patch",
    "wall": "wall",
    "symmetry": "symmetryPlane",
    "periodic": "cyclic",
    "interface": "interface",
    "fsi_interface": "interface",
    "cht_interface": "interface",
    "precice_interface": "interface",
    "thermal_contact": "interface",
    "mechanical_constraint": "wall",
    "mechanical_load": "patch",
    "electrical_conductor": "patch",
    "magnetic_region": "patch",
}


@dataclass(frozen=True, slots=True)
class SolverMeshExport:
    """One participant's explicit mapping onto the generated mesh groups."""

    participant: str
    format: str
    zones: tuple[tuple[str, str, str], ...]
    patches: tuple[tuple[str, str, str], ...]
    interfaces: tuple[tuple[str, str, str, str, bool], ...]
    materials: tuple[tuple[str, str], ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "participant": self.participant,
            "format": self.format,
            "zones": [
                {"name": name, "motion": motion, "domain": domain}
                for name, motion, domain in self.zones
            ],
            "patches": [
                {"name": name, "kind": kind, "nativeType": native}
                for name, kind, native in self.patches
            ],
            "interfaces": [
                {
                    "name": name,
                    "kind": kind,
                    "zoneA": zone_a,
                    "zoneB": zone_b,
                    "conformalRequested": conformal,
                }
                for name, kind, zone_a, zone_b, conformal in self.interfaces
            ],
            "materials": [
                {"name": name, "material": material}
                for name, material in self.materials
            ],
        }


def _select_participants(resolved: ResolvedMeshRequest) -> tuple[str, ...]:
    needs = resolved.request.exports
    if not needs:
        return _DEFAULT_PARTICIPANTS
    return tuple(dict.fromkeys(need.participant for need in needs))


def _openfoam_patch_type(kind: str) -> str:
    return _OPENFOAM_PATCH_TYPES.get(kind, "patch")


def build_solver_exports(
    resolved: ResolvedMeshRequest,
    mapping: MeshRequestMapping,
    *,
    participants: Sequence[str] | None = None,
) -> tuple[SolverMeshExport, ...]:
    """Build explicit per-participant mappings from a resolved request."""

    selected = tuple(participants) if participants is not None else _select_participants(
        resolved
    )
    zones = tuple((name, motion, domain) for name, motion, domain, _ in mapping.zones)
    interfaces = tuple(
        (name, kind, zone_a, zone_b, conformal)
        for name, kind, zone_a, zone_b, conformal, _ in mapping.interfaces
    )
    materials = tuple((name, material) for name, material, _ in mapping.materials)
    exports: list[SolverMeshExport] = []
    for participant in selected:
        if participant == "openfoam":
            patches = tuple(
                (name, kind, _openfoam_patch_type(kind))
                for name, kind, _ in mapping.patches
            )
            exports.append(
                SolverMeshExport(
                    participant, "openfoam", zones, patches, interfaces, materials
                )
            )
        elif participant in {"code_aster", "elmer"}:
            patches = tuple((name, kind, kind) for name, kind, _ in mapping.patches)
            exports.append(
                SolverMeshExport(
                    participant, participant, zones, patches, interfaces, materials
                )
            )
        elif participant == "precice":
            exports.append(
                SolverMeshExport(participant, "precice", zones, (), interfaces, ())
            )
        else:  # pragma: no cover - ExportNeed validates the participant
            raise ValueError(f"UNKNOWN_EXPORT_PARTICIPANT:{participant}")
    return tuple(exports)


def solver_mapping_digest(
    exports: tuple[SolverMeshExport, ...],
    *,
    geometry_hash: str,
    mesh_hash: str | None,
) -> str:
    payload = {
        "geometryHash": geometry_hash,
        "meshHash": mesh_hash,
        "exports": [export.canonical_payload() for export in exports],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_solver_mapping(
    path: Path,
    exports: tuple[SolverMeshExport, ...],
    *,
    provenance: Mapping[str, Any],
) -> str:
    """Write solver mappings to JSON and return the artifact hash."""

    payload = {
        "provenance": dict(provenance),
        "exports": [export.canonical_payload() for export in exports],
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()
