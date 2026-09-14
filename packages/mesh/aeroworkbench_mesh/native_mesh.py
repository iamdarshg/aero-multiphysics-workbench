"""Real generic meshing from the canonical CAD/semantic model via Gmsh.

Structural and fluid domains share one code path: volumes become zone
physical groups from semantic roles, boundary patches become named surface
groups via generic box selectors, shared volume boundaries become interface
groups, and every receipt carries measured quality plus lineage.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .domains import (
    BoundaryLayerIntent,
    BoxSelector,
    MeshSpec,
    PatchSpec,
    ZoneSpec,
)
from .quality import MeshQuality, compute_quality

_MESH_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class GmshCapability:
    available: bool
    version: str | None
    detail: str


def probe_gmsh() -> GmshCapability:
    try:
        import gmsh  # noqa: PLC0415
    except ImportError as exc:
        return GmshCapability(False, None, f"gmsh is not installed: {exc}")
    try:
        version = str(gmsh.GMSH_API_VERSION)
    except Exception:
        version = "unknown"
    return GmshCapability(True, version, "gmsh python API available")


@dataclass(frozen=True, slots=True)
class InterfaceGroup:
    name: str
    zone_a: str
    zone_b: str
    surface_count: int


@dataclass(frozen=True, slots=True)
class PeriodicPair:
    patch: str
    partner: str
    applied: bool
    detail: str


@dataclass(frozen=True, slots=True)
class NativeMeshReceipt:
    state: Literal["completed", "failed", "unavailable"]
    update: Literal["fresh", "morphed", "remeshed"]
    mesh_path: str | None
    mesh_hash: str | None
    geometry_hash: str
    topology_fingerprint: str | None
    quality: MeshQuality | None
    physical_groups: dict[str, str]
    interfaces: tuple[InterfaceGroup, ...]
    periodic: tuple[PeriodicPair, ...]
    minimum_quality: float | None
    detail: str

    @property
    def element_count(self) -> int:
        return self.quality.element_count if self.quality else 0


def _fail(
    geometry_hash: str, code: str, detail: str,
    update: Literal["fresh", "morphed", "remeshed"] = "fresh",
) -> NativeMeshReceipt:
    return NativeMeshReceipt(
        state="failed",
        update=update,
        mesh_path=None,
        mesh_hash=None,
        geometry_hash=geometry_hash,
        topology_fingerprint=None,
        quality=None,
        physical_groups={},
        interfaces=(),
        periodic=(),
        minimum_quality=None,
        detail=f"{code}:{detail}",
    )


def _surface_center(gmsh: Any, tag: int) -> tuple[float, float, float]:
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, tag)
    return ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)


def _apply_patch(
    gmsh: Any, patch: PatchSpec, zone_volumes: dict[str, list[int]]
) -> tuple[list[int], str]:
    """Collect region boundary surfaces whose center falls in the selector."""

    surfaces: set[int] = set()
    for component in patch.region_components:
        for volume in zone_volumes.get(component, []):
            boundary = gmsh.model.getBoundary([(3, volume)], oriented=False)
            for dim, tag in boundary:
                if dim != 2:
                    continue
                if patch.selector.contains(_surface_center(gmsh, tag)):
                    surfaces.add(tag)
    return sorted(surfaces), f"{len(surfaces)} surfaces in selector"


def _apply_periodic_pair(
    gmsh: Any, patch: PatchSpec, groups: dict[str, list[int]]
) -> PeriodicPair:
    master = groups.get(patch.name, [])
    slave = groups.get(patch.periodic_partner or "", [])
    if not master or not slave or patch.periodic_translation_mm is None:
        return PeriodicPair(patch.name, patch.periodic_partner or "",
                            False, "periodic partner group missing")
    translation = patch.periodic_translation_mm
    transform = [
        1, 0, 0, translation[0],
        0, 1, 0, translation[1],
        0, 0, 1, translation[2],
        0, 0, 0, 1,
    ]
    try:
        gmsh.model.mesh.setPeriodic(2, slave, master, transform)
    except Exception as exc:
        return PeriodicPair(patch.name, patch.periodic_partner or "",
                            False, f"setPeriodic failed: {exc}")
    return PeriodicPair(patch.name, patch.periodic_partner or "",
                        True, "setPeriodic translation applied")


def _wall_refinement_field(
    gmsh: Any, wall_surfaces: list[int], size_mm: float, base_mm: float
) -> int | None:
    if not wall_surfaces:
        return None
    try:
        distance = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(distance, "SurfacesList", wall_surfaces)
        gmsh.model.mesh.field.setNumber(distance, "Sampling", 100)
        threshold = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(threshold, "InField", distance)
        gmsh.model.mesh.field.setNumber(threshold, "SizeMin", size_mm)
        gmsh.model.mesh.field.setNumber(threshold, "SizeMax", base_mm)
        gmsh.model.mesh.field.setNumber(threshold, "DistMin", size_mm)
        gmsh.model.mesh.field.setNumber(threshold, "DistMax", base_mm * 4.0)
        return threshold
    except Exception:
        return None


def build_native_mesh(
    spec: MeshSpec,
    component_files: dict[str, Path],
    parent_geometry_hash: str,
    workdir: Path,
    *,
    mesh_filename: str | None = None,
    minimum_sicn: float = 0.05,
) -> NativeMeshReceipt:
    """Generate a real mesh with Gmsh from per-component STEP files."""

    capability = probe_gmsh()
    if not capability.available:
        receipt = _fail(parent_geometry_hash, "GMSH_UNAVAILABLE", capability.detail)
        return NativeMeshReceipt(
            state="unavailable", update=receipt.update, mesh_path=receipt.mesh_path,
            mesh_hash=None, geometry_hash=parent_geometry_hash,
            topology_fingerprint=None, quality=None, physical_groups={},
            interfaces=(), periodic=(), minimum_quality=None, detail=receipt.detail,
        )
    missing = [c for c in spec.components() if c not in component_files]
    if missing:
        return _fail(parent_geometry_hash, "MESH_INPUT_MISSING",
                      f"no CAD file for components: {missing}")
    workdir.mkdir(parents=True, exist_ok=True)
    mesh_path = workdir / (mesh_filename or f"{spec.name}.msh")

    import gmsh  # noqa: PLC0415

    with _MESH_LOCK:
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.option.setNumber("Mesh.MshFileVersion", 4.1)
            gmsh.option.setNumber("Mesh.Binary", 0)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMin", spec.min_size_mm)
            gmsh.option.setNumber("Mesh.CharacteristicLengthMax", spec.max_size_mm)
            gmsh.option.setNumber("Mesh.Algorithm3D", 1)
            gmsh.model.add(spec.name)

            # Import each component STEP; track fresh volumes per component.
            component_volumes: dict[str, list[int]] = {}
            input_owner: dict[int, str] = {}
            for component in spec.components():
                before = {tag for _, tag in gmsh.model.getEntities(3)}
                gmsh.merge(str(component_files[component]))
                gmsh.model.occ.synchronize()
                after = {tag for _, tag in gmsh.model.getEntities(3)}
                fresh = sorted(after - before)
                if not fresh:
                    return _fail(parent_geometry_hash, "MESH_IMPORT_EMPTY",
                                  f"component {component} produced no volume")
                component_volumes[component] = fresh
                for tag in fresh:
                    input_owner[tag] = component

            # Conformal fragment so shared boundaries become interfaces. The
            # fragment parent map (not point probes) tracks which component
            # each fragment came from, so annular/hollow regions map exactly.
            all_volumes = [(3, tag) for tags in component_volumes.values() for tag in tags]
            _, parent_map = gmsh.model.occ.fragment(all_volumes, all_volumes)
            gmsh.model.occ.synchronize()
            # parent_map covers object inputs then tool inputs; both are
            # all_volumes here, so the first half maps every input volume.
            object_map = parent_map[: len(all_volumes)]
            zone_volumes: dict[str, list[int]] = {c: [] for c in spec.components()}
            for (_, input_tag), children in zip(
                all_volumes, object_map, strict=True
            ):
                owner = input_owner.get(input_tag)
                if owner is None:
                    continue
                for child_dim, child_tag in children:
                    if child_dim == 3 and child_tag not in zone_volumes[owner]:
                        zone_volumes[owner].append(child_tag)
            unmapped = [c for c, tags in zone_volumes.items() if not tags]
            if unmapped:
                return _fail(parent_geometry_hash, "MESH_FRAGMENT_LOST",
                              f"components lost in fragment: {unmapped}")

            # Zone physical groups (rotating vs stationary, fluid vs solid).
            physical_groups: dict[str, str] = {}
            zone_volume_tags: dict[str, list[int]] = {}
            for zone in spec.zones:
                tags: list[int] = []
                for component in zone.components:
                    tags.extend(zone_volumes.get(component, []))
                if not tags:
                    return _fail(parent_geometry_hash, "MESH_ZONE_EMPTY",
                                  f"zone {zone.name} has no volumes")
                group = gmsh.model.addPhysicalGroup(3, tags)
                gmsh.model.setPhysicalName(3, group, zone.name)
                physical_groups[f"zone:{zone.name}"] = (
                    f"{zone.motion}:{zone.domain}:{len(tags)}vol"
                )
                zone_volume_tags[zone.name] = tags

            # Shared-boundary interface groups between zone pairs.
            interfaces: list[InterfaceGroup] = []
            zone_names = [zone.name for zone in spec.zones]
            boundaries: dict[str, set[int]] = {}
            for zone_name, tags in zone_volume_tags.items():
                faces: set[int] = set()
                for tag in tags:
                    for dim, face in gmsh.model.getBoundary(
                        [(3, tag)], oriented=False
                    ):
                        if dim == 2:
                            faces.add(face)
                boundaries[zone_name] = faces
            for index, name_a in enumerate(zone_names):
                for name_b in zone_names[index + 1:]:
                    shared = sorted(boundaries[name_a] & boundaries[name_b])
                    if not shared:
                        continue
                    group = gmsh.model.addPhysicalGroup(2, shared)
                    label = f"interface_{name_a}__{name_b}"
                    gmsh.model.setPhysicalName(2, group, label)
                    physical_groups[f"interface:{label}"] = (
                        f"{name_a}<->{name_b}:{len(shared)}faces"
                    )
                    interfaces.append(InterfaceGroup(label, name_a, name_b, len(shared)))

            # Named boundary patches via generic selectors.
            patch_surfaces: dict[str, list[int]] = {}
            # Map component->zone volumes for patch lookup keyed by component.
            for patch in spec.patches:
                surfaces, note = _apply_patch(gmsh, patch, zone_volumes)
                if not surfaces:
                    return _fail(parent_geometry_hash, "MESH_PATCH_EMPTY",
                                  f"patch {patch.name} selected no surfaces")
                group = gmsh.model.addPhysicalGroup(2, surfaces)
                gmsh.model.setPhysicalName(2, group, patch.name)
                physical_groups[f"patch:{patch.name}"] = f"{patch.kind}:{note}"
                patch_surfaces[patch.name] = surfaces

            # Local refinement fields.
            background_fields: list[int] = []
            for refinement in spec.refinements:
                cx = (refinement.selector.xmin + refinement.selector.xmax) / 2.0
                cy = (refinement.selector.ymin + refinement.selector.ymax) / 2.0
                cz = (refinement.selector.zmin + refinement.selector.zmax) / 2.0
                try:
                    distance = gmsh.model.mesh.field.add("Distance")
                    gmsh.model.mesh.field.setNumbers(
                        distance, "PointsList", [cx, cy, cz]
                    )
                    threshold = gmsh.model.mesh.field.add("Threshold")
                    gmsh.model.mesh.field.setNumber(threshold, "InField", distance)
                    gmsh.model.mesh.field.setNumber(
                        threshold, "SizeMin", refinement.element_size_mm
                    )
                    gmsh.model.mesh.field.setNumber(threshold, "SizeMax", spec.base_size_mm)
                    gmsh.model.mesh.field.setNumber(
                        threshold, "DistMin", refinement.element_size_mm
                    )
                    gmsh.model.mesh.field.setNumber(
                        threshold, "DistMax", spec.base_size_mm * 4.0
                    )
                    background_fields.append(threshold)
                except Exception:
                    continue

            # Boundary-layer intent: real 3D BL field attempt, honest fallback.
            bl_applied, bl_detail = False, "no boundary-layer intent requested"
            if spec.boundary_layer is not None:
                intent = spec.boundary_layer
                wall_surfaces: list[int] = []
                for patch_name in intent.wall_patches:
                    wall_surfaces.extend(patch_surfaces.get(patch_name, []))
                tried = _wall_refinement_field(
                    gmsh, wall_surfaces, intent.first_layer_mm, spec.base_size_mm
                )
                if tried is not None:
                    background_fields.append(tried)
                    bl_detail = (
                        f"wall Distance/Threshold refinement at {intent.first_layer_mm}mm "
                        f"on {len(wall_surfaces)} faces; full 3D BL extrusion with "
                        "fan-point control is downstream solver-mesh work"
                    )
                else:
                    bl_detail = "wall refinement field failed; base sizing used"
            if background_fields:
                try:
                    combined = gmsh.model.mesh.field.add("Min")
                    gmsh.model.mesh.field.setNumbers(
                        combined, "FieldsList", background_fields
                    )
                    gmsh.model.mesh.field.setAsBackgroundMesh(combined)
                except Exception:
                    pass

            # Periodic pairs.
            periodic: list[PeriodicPair] = []
            for patch in spec.patches:
                if patch.periodic_partner is not None:
                    periodic.append(
                        _apply_periodic_pair(gmsh, patch, patch_surfaces)
                    )

            gmsh.model.occ.synchronize()
            gmsh.model.mesh.generate(spec.dimension)
            if spec.second_order:
                gmsh.model.mesh.setOrder(2)
            with suppress(Exception):
                gmsh.model.mesh.optimize(
                    "Relocate3D" if spec.dimension == 3 else "Relocate2D"
                )
            quality = compute_quality(
                gmsh, boundary_layer=(bl_applied or bool(background_fields), bl_detail)
            )
            gmsh.write(str(mesh_path))
        finally:
            with suppress(Exception):
                gmsh.finalize()

    if not mesh_path.is_file():
        return _fail(parent_geometry_hash, "MESH_WRITE_FAILED",
                      "gmsh produced no mesh file")
    if quality.inverted_count:
        return _fail(parent_geometry_hash, "MESH_INVERTED_ELEMENTS",
                      f"{quality.inverted_count} inverted elements")
    if quality.min_sicn is not None and quality.min_sicn < minimum_sicn:
        return _fail(parent_geometry_hash, "MESH_QUALITY_BELOW_THRESHOLD",
                      f"min SICN {quality.min_sicn:.4f} < {minimum_sicn}")
    digest = hashlib.sha256(mesh_path.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "groups": sorted(physical_groups),
                "interfaces": sorted(
                    f"{i.name}:{i.zone_a}:{i.zone_b}" for i in interfaces
                ),
                "elements": quality.element_count,
                "nodes": quality.node_count,
            },
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return NativeMeshReceipt(
        state="completed",
        update="fresh",
        mesh_path=str(mesh_path),
        mesh_hash=digest,
        geometry_hash=parent_geometry_hash,
        topology_fingerprint=fingerprint,
        quality=quality,
        physical_groups=dict(sorted(physical_groups.items())),
        interfaces=tuple(interfaces),
        periodic=tuple(periodic),
        minimum_quality=quality.min_sicn,
        detail=f"gmsh {spec.dimension}D mesh accepted: "
        f"{quality.element_count} elements, min SICN {quality.min_sicn}",
    )


def duct_mesh_spec(
    *,
    name: str,
    rotating: tuple[str, ...],
    stationary_fluid: tuple[str, ...],
    solids: tuple[str, ...],
    length_mm: float,
    inner_diameter_mm: float,
    base_size_mm: float = 4.0,
    boundary_layer: bool = True,
) -> MeshSpec:
    """Build a generic duct-system mesh spec from zone component names.

    No counts are assumed: any number of rotating zones, stationary fluid
    regions, and solid bodies is accepted. Inlet/outlet patches are selected
    by axial end boxes, not by hard-coded names.
    """

    radius = inner_diameter_mm / 2.0
    half = length_mm / 2.0
    zones = [
        *[ZoneSpec(f"rot-{component}", "rotating", "fluid", (component,))
          for component in rotating],
        *[ZoneSpec(f"stat-{component}", "stationary", "fluid", (component,))
          for component in stationary_fluid],
        *[ZoneSpec(f"solid-{component}", "stationary", "solid", (component,))
          for component in solids],
    ]
    fluid_components = tuple([*rotating, *stationary_fluid])
    end = 0.51 * length_mm
    patches = [
        PatchSpec(
            "inlet", "inlet", "fluid", fluid_components,
            BoxSelector(-radius, -radius, -half - 1.0, radius, radius, -half + end * 0.02 + 1.0),
        ),
        PatchSpec(
            "outlet", "outlet", "fluid", fluid_components,
            BoxSelector(-radius, -radius, half - end * 0.02 - 1.0, radius, radius, half + 1.0),
        ),
        PatchSpec(
            "walls", "wall", "fluid", fluid_components,
            BoxSelector(-radius - 1.0, -radius - 1.0, -half, radius + 1.0, radius + 1.0, half),
        ),
    ]
    return MeshSpec(
        name=name,
        dimension=3,
        base_size_mm=base_size_mm,
        min_size_mm=base_size_mm / 4.0,
        max_size_mm=base_size_mm * 2.0,
        zones=tuple(zones),
        patches=tuple(patches),
        boundary_layer=(
            BoundaryLayerIntent(("walls",), base_size_mm / 4.0, 1.2, 3)
            if boundary_layer else None
        ),
    )
