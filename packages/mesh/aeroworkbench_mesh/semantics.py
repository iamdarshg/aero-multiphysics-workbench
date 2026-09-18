"""Canonical, semantics-driven mesh request for arbitrary regenerated CAD.

A :class:`SemanticMeshRequest` is driven by:

- a geometry artifact/hash (content address of the CAD the mesh must match),
- a semantic topology receipt (engineering roles, not transient kernel faces),
- declared volume/surface roles, materials, interfaces, and export needs.

Declarations reference *semantic keys*, never application region names. The
resolver maps keys to built components and concrete Gmsh physical groups, and
fails closed when a required role, zone, interface, or CAD artifact is missing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aeroworkbench_semantics import TopologyModel

from .domains import (
    BoundaryLayerIntent,
    BoxSelector,
    DomainKind,
    InterfaceKind,
    InterfaceSpec,
    MaterialRegionSpec,
    MeshSpec,
    PatchKind,
    PatchSpec,
    RefinementSpec,
    ZoneMotion,
    ZoneSpec,
)

_REGION_ZONE_KINDS: dict[str, tuple[DomainKind, ZoneMotion]] = {
    "fluid_region": ("fluid", "stationary"),
    "solid_region": ("solid", "stationary"),
    "rotating_region": ("fluid", "rotating"),
    "stationary_region": ("fluid", "stationary"),
}
_BOUNDARY_KINDS: frozenset[str] = frozenset(
    {"inlet", "outlet", "wall", "symmetry", "periodic"}
)
_MATERIAL_KINDS: frozenset[str] = frozenset({"material_assignment"})

_EXPORT_PARTICIPANTS: frozenset[str] = frozenset(
    {"openfoam", "code_aster", "elmer", "precice"}
)


def _require_text(label: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{label}_REQUIRED")


@dataclass(frozen=True, slots=True)
class SemanticEntity:
    """One engineering entity with its resolved CAD component identity."""

    semantic_key: str
    kind: str
    region: str
    component: str
    frame: str | None = None
    material: str | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SemanticTopologyReceipt:
    """Immutable semantic topology view consumed by the mesh request."""

    digest: str
    entities: tuple[SemanticEntity, ...]

    def __post_init__(self) -> None:
        keys = [entity.semantic_key for entity in self.entities]
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_SEMANTIC_KEY")

    def by_key(self, semantic_key: str) -> SemanticEntity:
        for entity in self.entities:
            if entity.semantic_key == semantic_key:
                return entity
        raise KeyError(f"SEMANTIC_KEY_NOT_FOUND:{semantic_key}")

    def has_kind(self, kind: str) -> bool:
        return any(entity.kind == kind for entity in self.entities)

    def of_kind(self, kind: str) -> tuple[SemanticEntity, ...]:
        return tuple(entity for entity in self.entities if entity.kind == kind)

    def components_for_keys(self, semantic_keys: tuple[str, ...]) -> tuple[str, ...]:
        components: list[str] = []
        for key in semantic_keys:
            component = self.by_key(key).component
            if component not in components:
                components.append(component)
        return tuple(components)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "entities": [
                {
                    "key": entity.semantic_key,
                    "kind": entity.kind,
                    "region": entity.region,
                    "component": entity.component,
                    "frame": entity.frame,
                    "material": entity.material,
                }
                for entity in sorted(self.entities, key=lambda item: item.semantic_key)
            ]
        }


def _component_of(
    semantic_key: str, fingerprint: str, overrides: Mapping[str, str]
) -> str:
    override = overrides.get(semantic_key)
    if override is not None and override.strip():
        return override
    # ``topology_from_components`` prefixes the fingerprint with the component
    # name; this is the canonical linkage and avoids re-deriving identity.
    if "::" in fingerprint:
        prefix = fingerprint.split("::", 1)[0].strip()
        if prefix:
            return prefix
    raise ValueError(f"SEMANTIC_COMPONENT_UNRESOLVED:{semantic_key}")


def semantic_topology_from_model(
    model: TopologyModel, *, component_overrides: Mapping[str, str] | None = None
) -> SemanticTopologyReceipt:
    """Adapt the shared :class:`TopologyModel` into a mesh-facing receipt."""

    overrides = component_overrides or {}
    entities = tuple(
        SemanticEntity(
            semantic_key=entity.semantic_key,
            kind=str(entity.kind),
            region=entity.region,
            component=_component_of(entity.semantic_key, entity.fingerprint, overrides),
            frame=entity.frame,
            material=entity.material_identity,
            detail=entity.detail,
        )
        for entity in model.entities
    )
    receipt = SemanticTopologyReceipt(digest="", entities=entities)
    encoded = json.dumps(
        receipt.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return SemanticTopologyReceipt(
        digest=hashlib.sha256(encoded).hexdigest(), entities=entities
    )


@dataclass(frozen=True, slots=True)
class ZoneDeclaration:
    """Declare one cell zone from a set of semantic keys."""

    name: str
    motion: ZoneMotion
    domain: DomainKind
    semantic_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("ZONE_DECLARATION_NAME", self.name)
        if not self.semantic_keys:
            raise ValueError("ZONE_DECLARATION_NEEDS_KEYS")


@dataclass(frozen=True, slots=True)
class PatchDeclaration:
    """Declare one boundary patch selected from semantic keys and a box."""

    name: str
    kind: PatchKind
    domain: DomainKind
    semantic_keys: tuple[str, ...]
    selector: BoxSelector
    periodic_partner: str | None = None
    periodic_translation_mm: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        _require_text("PATCH_DECLARATION_NAME", self.name)
        if not self.semantic_keys:
            raise ValueError("PATCH_DECLARATION_NEEDS_KEYS")


@dataclass(frozen=True, slots=True)
class InterfaceDeclaration:
    """Declare one field-coupling interface between two named zones."""

    name: str
    kind: InterfaceKind
    zone_a: str
    zone_b: str
    conformal: bool = True
    semantic_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("INTERFACE_DECLARATION_NAME", self.name)
        _require_text("INTERFACE_DECLARATION_ZONE", self.zone_a)
        _require_text("INTERFACE_DECLARATION_ZONE", self.zone_b)


@dataclass(frozen=True, slots=True)
class MaterialDeclaration:
    """Declare one material volume region from semantic keys."""

    name: str
    material: str
    domain: DomainKind
    semantic_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("MATERIAL_DECLARATION_NAME", self.name)
        _require_text("MATERIAL_DECLARATION_MATERIAL", self.material)
        if not self.semantic_keys:
            raise ValueError("MATERIAL_DECLARATION_NEEDS_KEYS")


@dataclass(frozen=True, slots=True)
class ExportNeed:
    """Participant-specific export requirement (mapping names only)."""

    participant: str
    zones: tuple[str, ...] = ()
    patches: tuple[str, ...] = ()
    interfaces: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.participant not in _EXPORT_PARTICIPANTS:
            raise ValueError(f"UNKNOWN_EXPORT_PARTICIPANT:{self.participant}")


@dataclass(frozen=True, slots=True)
class SemanticMeshRequest:
    """The canonical mesh request: semantics + artifact hash + intent."""

    name: str
    geometry_hash: str
    topology_digest: str
    dimension: int
    base_size_mm: float
    min_size_mm: float
    max_size_mm: float
    zones: tuple[ZoneDeclaration, ...]
    patches: tuple[PatchDeclaration, ...] = ()
    interfaces: tuple[InterfaceDeclaration, ...] = ()
    materials: tuple[MaterialDeclaration, ...] = ()
    refinements: tuple[RefinementSpec, ...] = ()
    boundary_layer: BoundaryLayerIntent | None = None
    second_order: bool = False
    exports: tuple[ExportNeed, ...] = ()
    required_kinds: tuple[str, ...] = ()
    required_zones: tuple[str, ...] = ()
    required_patches: tuple[str, ...] = ()
    required_interfaces: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("MESH_REQUEST_NAME", self.name)
        if len(self.geometry_hash) != 64:
            raise ValueError("MESH_REQUEST_NEEDS_GEOMETRY_HASH")
        if self.dimension not in (2, 3):
            raise ValueError("INVALID_MESH_DIMENSION")
        if not 0 < self.min_size_mm <= self.base_size_mm <= self.max_size_mm:
            raise ValueError("INVALID_MESH_SIZES")
        if not self.zones:
            raise ValueError("MESH_REQUEST_REQUIRES_ZONES")
        names = [zone.name for zone in self.zones]
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ZONE_NAME")

    @property
    def zone_names(self) -> tuple[str, ...]:
        return tuple(zone.name for zone in self.zones)


@dataclass(frozen=True, slots=True)
class MeshRequestMapping:
    """Machine-readable semantic identity of every produced physical group."""

    zones: tuple[tuple[str, str, str, tuple[str, ...]], ...]
    patches: tuple[tuple[str, str, tuple[str, ...]], ...]
    interfaces: tuple[tuple[str, str, str, str, bool, tuple[str, ...]], ...]
    materials: tuple[tuple[str, str, tuple[str, ...]], ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "zones": [
                {
                    "name": name,
                    "motion": motion,
                    "domain": domain,
                    "semanticKeys": list(keys),
                }
                for name, motion, domain, keys in self.zones
            ],
            "patches": [
                {"name": name, "kind": kind, "semanticKeys": list(keys)}
                for name, kind, keys in self.patches
            ],
            "interfaces": [
                {
                    "name": name,
                    "kind": kind,
                    "zoneA": zone_a,
                    "zoneB": zone_b,
                    "conformalRequested": conformal,
                    "semanticKeys": list(keys),
                }
                for name, kind, zone_a, zone_b, conformal, keys in self.interfaces
            ],
            "materials": [
                {"name": name, "material": material, "semanticKeys": list(keys)}
                for name, material, keys in self.materials
            ],
        }


@dataclass(frozen=True, slots=True)
class ResolvedMeshRequest:
    """A canonical request resolved against a concrete CAD artifact set."""

    request: SemanticMeshRequest
    spec: MeshSpec
    mapping: MeshRequestMapping
    warnings: tuple[str, ...] = ()

    @property
    def missing_kinds(self) -> tuple[str, ...]:
        return self.warnings


def _components_for(
    topology: SemanticTopologyReceipt,
    semantic_keys: tuple[str, ...],
    component_files: Mapping[str, Path],
) -> tuple[str, ...]:
    try:
        components = topology.components_for_keys(semantic_keys)
    except KeyError as exc:
        raise ValueError(f"SEMANTIC_KEY_NOT_FOUND:{exc.args[0]}") from exc
    missing = [component for component in components if component not in component_files]
    if missing:
        raise ValueError(f"MESH_ARTIFACT_MISSING:{','.join(missing)}")
    return components


def semantic_request_from_topology(
    model: TopologyModel,
    *,
    name: str,
    geometry_hash: str,
    dimension: int,
    base_size_mm: float,
    min_size_mm: float,
    max_size_mm: float,
    selectors: Mapping[str, BoxSelector] | None = None,
    zone_domains: Mapping[str, DomainKind] | None = None,
    zone_motions: Mapping[str, ZoneMotion] | None = None,
    interfaces: tuple[InterfaceDeclaration, ...] = (),
    materials: tuple[MaterialDeclaration, ...] = (),
    refinements: tuple[RefinementSpec, ...] = (),
    boundary_layer: BoundaryLayerIntent | None = None,
    second_order: bool = False,
    exports: tuple[ExportNeed, ...] = (),
    required_kinds: tuple[str, ...] = (),
    required_zones: tuple[str, ...] = (),
    required_patches: tuple[str, ...] = (),
    required_interfaces: tuple[str, ...] = (),
    component_overrides: Mapping[str, str] | None = None,
) -> SemanticMeshRequest:
    """Derive a canonical request from semantic topology, without app names.

    Region-kind entities become zones, boundary-kind entities become patches
    (their box selectors come from the geometry artifact and are keyed by
    semantic key or region), and material assignments become material regions.
    Anything that cannot be classified is reported as a warning.
    """

    topology = semantic_topology_from_model(model, component_overrides=component_overrides)
    domain_overrides = zone_domains or {}
    motion_overrides = zone_motions or {}
    selector_map = selectors or {}

    zone_keys: dict[str, list[str]] = {}
    zone_traits: dict[str, tuple[DomainKind, ZoneMotion]] = {}
    for kind, (default_domain, default_motion) in _REGION_ZONE_KINDS.items():
        for entity in topology.of_kind(kind):
            domain = domain_overrides.get(entity.region, default_domain)
            motion = motion_overrides.get(entity.region, default_motion)
            existing = zone_traits.get(entity.region)
            if existing is not None and existing != (domain, motion):
                raise ValueError(f"ZONE_TRAIT_CONFLICT:{entity.region}")
            zone_traits[entity.region] = (domain, motion)
            zone_keys.setdefault(entity.region, []).append(entity.semantic_key)

    zones = tuple(
        ZoneDeclaration(
            name=region,
            motion=zone_traits[region][1],
            domain=zone_traits[region][0],
            semantic_keys=tuple(keys),
        )
        for region, keys in sorted(zone_keys.items())
    )

    patch_keys: dict[str, list[str]] = {}
    patch_kinds: dict[str, str] = {}
    warnings: list[str] = []
    for kind in sorted(_BOUNDARY_KINDS):
        for entity in topology.of_kind(kind):
            selector = selector_map.get(entity.semantic_key) or selector_map.get(entity.region)
            if selector is None:
                warnings.append(f"BOUNDARY_SELECTOR_MISSING:{entity.semantic_key}")
                continue
            patch_kinds[entity.region] = kind
            patch_keys.setdefault(entity.region, []).append(entity.semantic_key)

    patches = tuple(
        PatchDeclaration(
            name=region,
            kind=_as_patch_kind(patch_kinds[region]),
            domain=_patch_domain(patch_keys[region], zones),
            semantic_keys=tuple(patch_keys[region]),
            selector=_patch_selector(region, patch_keys[region], selector_map),
        )
        for region in sorted(patch_kinds)
    )

    material_decls: list[MaterialDeclaration] = list(materials)
    seen_material_names = {declaration.name for declaration in material_decls}
    for entity in topology.of_kind("material_assignment"):
        if entity.region in seen_material_names:
            continue
        seen_material_names.add(entity.region)
        material_decls.append(
            MaterialDeclaration(
                name=entity.region,
                material=entity.material or entity.region,
                domain="solid",
                semantic_keys=(entity.semantic_key,),
            )
        )

    return SemanticMeshRequest(
        name=name,
        geometry_hash=geometry_hash,
        topology_digest=topology.digest,
        dimension=dimension,
        base_size_mm=base_size_mm,
        min_size_mm=min_size_mm,
        max_size_mm=max_size_mm,
        zones=zones,
        patches=patches,
        interfaces=interfaces,
        materials=tuple(material_decls),
        refinements=refinements,
        boundary_layer=boundary_layer,
        second_order=second_order,
        exports=exports,
        required_kinds=required_kinds,
        required_zones=required_zones,
        required_patches=required_patches,
        required_interfaces=required_interfaces,
        warnings=tuple(warnings),
    )


def _as_patch_kind(kind: str) -> PatchKind:
    if kind == "periodic":
        return "periodic"
    return kind  # type: ignore[return-value]


def _patch_domain(keys: list[str], zones: tuple[ZoneDeclaration, ...]) -> DomainKind:
    key_set = set(keys)
    for zone in zones:
        if key_set & set(zone.semantic_keys):
            return zone.domain
    return "fluid"


def _patch_selector(
    region: str, keys: list[str], selector_map: Mapping[str, BoxSelector]
) -> BoxSelector:
    for key in keys:
        selector = selector_map.get(key)
        if selector is not None:
            return selector
    return selector_map[region]


def resolve_semantic_mesh_request(
    request: SemanticMeshRequest,
    topology: SemanticTopologyReceipt,
    component_files: Mapping[str, Path],
) -> ResolvedMeshRequest:
    """Map semantic declarations onto concrete zones/patches and Gmsh groups.

    Fails closed on a missing required kind, zone, patch, interface, or CAD
    artifact. Unclassified entities are reported as warnings, never silently
    dropped into a fabricated group.
    """

    for kind in request.required_kinds:
        if not topology.has_kind(kind):
            raise ValueError(f"SEMANTIC_REQUIRED_KIND_MISSING:{kind}")

    zone_specs: list[ZoneSpec] = []
    zone_keys: dict[str, tuple[str, ...]] = {}
    for zone_declaration in request.zones:
        components = _components_for(
            topology, zone_declaration.semantic_keys, component_files
        )
        zone_specs.append(
            ZoneSpec(
                name=zone_declaration.name,
                motion=zone_declaration.motion,
                domain=zone_declaration.domain,
                components=components,
            )
        )
        zone_keys[zone_declaration.name] = zone_declaration.semantic_keys

    patch_specs: list[PatchSpec] = []
    patch_keys: dict[str, tuple[str, ...]] = {}
    for patch_declaration in request.patches:
        components = _components_for(
            topology, patch_declaration.semantic_keys, component_files
        )
        patch_specs.append(
            PatchSpec(
                name=patch_declaration.name,
                kind=patch_declaration.kind,
                domain=patch_declaration.domain,
                region_components=components,
                selector=patch_declaration.selector,
                periodic_partner=patch_declaration.periodic_partner,
                periodic_translation_mm=patch_declaration.periodic_translation_mm,
            )
        )
        patch_keys[patch_declaration.name] = patch_declaration.semantic_keys

    material_specs: list[MaterialRegionSpec] = []
    material_keys: dict[str, tuple[str, ...]] = {}
    for material_declaration in request.materials:
        components = _components_for(
            topology, material_declaration.semantic_keys, component_files
        )
        material_specs.append(
            MaterialRegionSpec(
                name=material_declaration.name,
                material=material_declaration.material,
                components=components,
                domain=material_declaration.domain,
            )
        )
        material_keys[material_declaration.name] = material_declaration.semantic_keys

    zone_name_set = set(zone_keys)
    interface_specs: list[InterfaceSpec] = []
    for interface_declaration in request.interfaces:
        if (
            interface_declaration.zone_a not in zone_name_set
            or interface_declaration.zone_b not in zone_name_set
        ):
            raise ValueError(f"INTERFACE_ZONE_UNKNOWN:{interface_declaration.name}")
        interface_specs.append(
            InterfaceSpec(
                name=interface_declaration.name,
                kind=interface_declaration.kind,
                zone_a=interface_declaration.zone_a,
                zone_b=interface_declaration.zone_b,
                conformal=interface_declaration.conformal,
                semantic_keys=interface_declaration.semantic_keys,
            )
        )

    for required in request.required_zones:
        if required not in zone_name_set:
            raise ValueError(f"SEMANTIC_REQUIRED_ZONE_MISSING:{required}")
    patch_name_set = set(patch_keys)
    for required in request.required_patches:
        if required not in patch_name_set:
            raise ValueError(f"SEMANTIC_REQUIRED_PATCH_MISSING:{required}")
    interface_name_set = {item.name for item in interface_specs}
    for required in request.required_interfaces:
        if required not in interface_name_set:
            raise ValueError(f"SEMANTIC_REQUIRED_INTERFACE_MISSING:{required}")

    mapping = MeshRequestMapping(
        zones=tuple(
            (
                zone.name,
                zone.motion,
                zone.domain,
                zone_keys[zone.name],
            )
            for zone in zone_specs
        ),
        patches=tuple(
            (patch.name, patch.kind, patch_keys[patch.name]) for patch in patch_specs
        ),
        interfaces=tuple(
            (
                item.name,
                item.kind,
                item.zone_a,
                item.zone_b,
                item.conformal,
                item.semantic_keys,
            )
            for item in interface_specs
        ),
        materials=tuple(
            (item.name, item.material, material_keys[item.name])
            for item in material_specs
        ),
    )

    classified_keys = {
        key for keys in (*zone_keys.values(), *patch_keys.values(), *material_keys.values())
        for key in keys
    }
    warnings = tuple(
        sorted(
            f"UNCLASSIFIED_SEMANTIC_ENTITY:{entity.semantic_key}:{entity.kind}"
            for entity in topology.entities
            if entity.semantic_key not in classified_keys
        )
    )

    spec = MeshSpec(
        name=request.name,
        dimension=request.dimension,
        base_size_mm=request.base_size_mm,
        min_size_mm=request.min_size_mm,
        max_size_mm=request.max_size_mm,
        zones=tuple(zone_specs),
        patches=tuple(patch_specs),
        refinements=request.refinements,
        boundary_layer=request.boundary_layer,
        second_order=request.second_order,
        materials=tuple(material_specs),
        interfaces=tuple(interface_specs),
    )
    return ResolvedMeshRequest(
        request=request, spec=spec, mapping=mapping, warnings=warnings
    )
