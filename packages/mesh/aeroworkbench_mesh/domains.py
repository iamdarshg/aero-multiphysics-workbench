"""Generic mesh specification: domains, zones, patches, refinement intent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DomainKind = Literal["fluid", "solid"]
ZoneMotion = Literal["rotating", "stationary"]
PatchKind = Literal[
    "inlet", "outlet", "wall", "symmetry", "periodic", "interface",
    "fsi_interface", "cht_interface", "precice_interface",
]


@dataclass(frozen=True, slots=True)
class BoxSelector:
    """Select mesh entities whose center lies inside an XYZ box (mm)."""

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    def contains(self, point: tuple[float, float, float]) -> bool:
        x, y, z = point
        return (
            self.xmin <= x <= self.xmax
            and self.ymin <= y <= self.ymax
            and self.zmin <= z <= self.zmax
        )


@dataclass(frozen=True, slots=True)
class ZoneSpec:
    """One cell zone: components sharing a motion/region role."""

    name: str
    motion: ZoneMotion
    domain: DomainKind
    components: tuple[str, ...]
    frame: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ZONE_NAME_REQUIRED")
        if not self.components:
            raise ValueError("ZONE_REQUIRES_COMPONENTS")


@dataclass(frozen=True, slots=True)
class PatchSpec:
    """One named boundary patch selected generically from region surfaces."""

    name: str
    kind: PatchKind
    domain: DomainKind
    region_components: tuple[str, ...]
    selector: BoxSelector
    periodic_partner: str | None = None
    periodic_translation_mm: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PATCH_NAME_REQUIRED")
        if not self.region_components:
            raise ValueError("PATCH_REQUIRES_REGION_COMPONENTS")
        if (self.periodic_partner is None) != (
            self.periodic_translation_mm is None
        ):
            raise ValueError("PERIODIC_NEEDS_PARTNER_AND_TRANSLATION")


@dataclass(frozen=True, slots=True)
class RefinementSpec:
    """Local refinement intent around a box-selected feature."""

    name: str
    selector: BoxSelector
    element_size_mm: float

    def __post_init__(self) -> None:
        if self.element_size_mm <= 0:
            raise ValueError("REFINEMENT_SIZE_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class BoundaryLayerIntent:
    """Boundary-layer meshing intent recorded on wall patches."""

    wall_patches: tuple[str, ...]
    first_layer_mm: float
    growth_ratio: float
    layer_count: int

    def __post_init__(self) -> None:
        if not self.wall_patches:
            raise ValueError("BOUNDARY_LAYER_NEEDS_WALLS")
        if self.first_layer_mm <= 0 or self.growth_ratio < 1.0 or self.layer_count < 1:
            raise ValueError("INVALID_BOUNDARY_LAYER_PARAMETERS")


@dataclass(frozen=True, slots=True)
class MeshSpec:
    """Complete generic mesh request for one domain assembly."""

    name: str
    dimension: int
    base_size_mm: float
    min_size_mm: float
    max_size_mm: float
    zones: tuple[ZoneSpec, ...]
    patches: tuple[PatchSpec, ...]
    refinements: tuple[RefinementSpec, ...] = ()
    boundary_layer: BoundaryLayerIntent | None = None
    second_order: bool = False

    def __post_init__(self) -> None:
        if self.dimension not in (2, 3):
            raise ValueError("INVALID_MESH_DIMENSION")
        if not 0 < self.min_size_mm <= self.base_size_mm <= self.max_size_mm:
            raise ValueError("INVALID_MESH_SIZES")
        if not self.zones:
            raise ValueError("MESH_REQUIRES_ZONES")
        names = [zone.name for zone in self.zones]
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ZONE_NAME")
        patch_names = [patch.name for patch in self.patches]
        if len(patch_names) != len(set(patch_names)):
            raise ValueError("DUPLICATE_PATCH_NAME")

    def components(self) -> tuple[str, ...]:
        seen: list[str] = []
        for zone in self.zones:
            for component in zone.components:
                if component not in seen:
                    seen.append(component)
        return tuple(seen)
