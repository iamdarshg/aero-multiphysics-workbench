"""Native mesher access through Gmsh, capability-gated and fail-closed.

When Gmsh is unavailable the native path returns an explicit ``unavailable``
state and raises :class:`MesherCapabilityUnavailable` from
:func:`require_native_mesher`. It never substitutes a screening or analytical
mesh for a requested native mesh. When Gmsh is present, real meshes are
generated and their quality is measured, not fabricated.
"""

from __future__ import annotations

import hashlib
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from aeroworkbench_mesh import (
    MeshQuality,
    MeshSpec,
    NativeMeshReceipt,
    build_native_mesh,
    compute_quality,
    probe_gmsh,
)
from aeroworkbench_mesh.native_mesh import _MESH_LOCK

from .contracts import ResultEnvelope, Validity, native_envelope
from .errors import MesherCapabilityUnavailable

__all__ = [
    "MesherCapability",
    "NativeMeshResult",
    "build_native_mesh_physics",
    "mesh_box_native",
    "probe_mesher",
    "require_native_mesher",
]


@dataclass(frozen=True, slots=True)
class MesherCapability:
    """Whether a native mesher is present, and its identity."""

    available: bool
    version: str | None
    detail: str


def probe_mesher() -> MesherCapability:
    """Report native mesher availability without pretending."""

    capability = probe_gmsh()
    return MesherCapability(capability.available, capability.version, capability.detail)


def require_native_mesher() -> MesherCapability:
    """Fail closed unless a native mesher is actually wired."""

    capability = probe_mesher()
    if not capability.available:
        raise MesherCapabilityUnavailable(f"NATIVE_MESHER_UNAVAILABLE:{capability.detail}")
    return capability


@dataclass(frozen=True, slots=True)
class NativeMeshResult:
    """Result of a native meshing attempt with measured quality and provenance."""

    state: Literal["completed", "failed", "unavailable"]
    mesh_hash: str | None
    mesh_path: str | None
    quality: MeshQuality | None
    envelope: ResultEnvelope | None
    detail: str
    receipt: NativeMeshReceipt | None = None

    @property
    def measured(self) -> bool:
        return self.quality is not None

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "meshHash": self.mesh_hash,
            "meshPath": self.mesh_path,
            "detail": self.detail,
            "measured": self.measured,
            "quality": None if self.quality is None else self.quality.canonical_payload(),
            "envelope": None if self.envelope is None else self.envelope.as_dict(),
        }


def _native_units() -> tuple[tuple[str, str], ...]:
    return (("length", "mm"), ("dimensionless", "1"))


def mesh_box_native(
    name: str,
    *,
    extent_mm: tuple[float, float, float] = (10.0, 10.0, 10.0),
    size_mm: float = 2.0,
    dimension: int = 3,
    workdir: Path | None = None,
) -> NativeMeshResult:
    """Generate a tiny real Gmsh box mesh and measure its quality.

    This is the bounded native smoke path: a single box, one characteristic
    size, measured element counts and SICN. If Gmsh is missing it fails closed
    with an ``unavailable`` state and no fabricated metrics.
    """

    if not name.strip():
        raise ValueError("NATIVE_MESH_NAME_REQUIRED")
    if dimension not in (2, 3):
        raise ValueError("NATIVE_MESH_DIMENSION_INVALID")
    capability = probe_mesher()
    if not capability.available:
        return NativeMeshResult(
            state="unavailable",
            mesh_hash=None,
            mesh_path=None,
            quality=None,
            envelope=None,
            detail=f"GMSH_UNAVAILABLE:{capability.detail}",
        )

    import gmsh  # noqa: PLC0415

    target_dir = workdir if workdir is not None else Path(tempfile.mkdtemp(prefix="mesh-box-"))
    target_dir.mkdir(parents=True, exist_ok=True)
    mesh_path = target_dir / f"{name}.msh"
    lx, ly, lz = extent_mm

    with _MESH_LOCK:
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMin", size_mm)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMax", size_mm)
            gmsh.model.add(name)
            if dimension == 3:
                gmsh.model.occ.addBox(0.0, 0.0, 0.0, lx, ly, lz)
            else:
                gmsh.model.occ.addRectangle(0.0, 0.0, 0.0, lx, ly)
            gmsh.model.occ.synchronize()
            gmsh.model.mesh.generate(dimension)
            quality = compute_quality(
                gmsh, boundary_layer=(False, "native-box:no boundary layer")
            )
            gmsh.write(str(mesh_path))
        finally:
            with suppress(Exception):
                gmsh.finalize()

    if not mesh_path.is_file():
        return NativeMeshResult(
            state="failed",
            mesh_hash=None,
            mesh_path=None,
            quality=None,
            envelope=None,
            detail="MESH_WRITE_FAILED:gmsh produced no mesh file",
        )
    digest = hashlib.sha256(mesh_path.read_bytes()).hexdigest()
    checks = {
        "elements_present": quality.element_count > 0,
        "no_inverted_elements": quality.inverted_count == 0,
        "sicn_measured": quality.min_sicn is not None,
    }
    validity = Validity(passed=all(checks.values()), checks=checks, detail="native box mesh")
    envelope = native_envelope(
        model="gmsh-box",
        inputs={
            "name": name,
            "extentMm": list(extent_mm),
            "sizeMm": size_mm,
            "dimension": dimension,
        },
        units=_native_units(),
        validity=validity,
        solver_name="gmsh",
        solver_version=capability.version or "unknown",
        run_id=f"gmsh-box-{digest[:16]}",
        assumptions=("single box; measured quality from the native mesher",),
    )
    return NativeMeshResult(
        state="completed",
        mesh_hash=digest,
        mesh_path=str(mesh_path),
        quality=quality,
        envelope=envelope,
        detail=(
            f"gmsh {dimension}D box mesh: {quality.element_count} elements, "
            f"min SICN {quality.min_sicn}"
        ),
    )


def build_native_mesh_physics(
    spec: MeshSpec,
    component_files: dict[str, Path],
    parent_geometry_hash: str,
    workdir: Path,
    *,
    minimum_sicn: float = 0.05,
    mesh_filename: str | None = None,
    mapping_payload: dict[str, Any] | None = None,
) -> NativeMeshResult:
    """Delegate to the existing native mesh builder and attach provenance."""

    capability = probe_mesher()
    if not capability.available:
        return NativeMeshResult(
            state="unavailable",
            mesh_hash=None,
            mesh_path=None,
            quality=None,
            envelope=None,
            detail=f"GMSH_UNAVAILABLE:{capability.detail}",
        )
    receipt = build_native_mesh(
        spec,
        component_files,
        parent_geometry_hash,
        workdir,
        mesh_filename=mesh_filename,
        minimum_sicn=minimum_sicn,
        mapping_payload=mapping_payload,
    )
    if receipt.state != "completed" or receipt.quality is None or receipt.mesh_hash is None:
        return NativeMeshResult(
            state="failed" if receipt.state == "failed" else "unavailable",
            mesh_hash=receipt.mesh_hash,
            mesh_path=receipt.mesh_path,
            quality=receipt.quality,
            envelope=None,
            detail=receipt.detail,
            receipt=receipt,
        )
    validity = Validity(
        passed=receipt.quality.inverted_count == 0,
        checks={
            "elements_present": receipt.quality.element_count > 0,
            "no_inverted_elements": receipt.quality.inverted_count == 0,
        },
        detail=receipt.detail,
    )
    envelope = native_envelope(
        model="gmsh-semantic-mesh",
        inputs=dict(receipt.input_hashes),
        units=_native_units(),
        validity=validity,
        solver_name="gmsh",
        solver_version=capability.version or "unknown",
        run_id=f"gmsh-{receipt.mesh_hash[:16]}",
        assumptions=("semantic zones/patches/interfaces from the shared mesh contract",),
    )
    return NativeMeshResult(
        state="completed",
        mesh_hash=receipt.mesh_hash,
        mesh_path=receipt.mesh_path,
        quality=receipt.quality,
        envelope=envelope,
        detail=receipt.detail,
        receipt=receipt,
    )
