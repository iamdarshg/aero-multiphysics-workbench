"""Typed structural members, cross-sections, and outer-geometry bindings.

A :class:`StructuralMember` is a typed structural element (spar cap, spar web,
rib, frame, bulkhead, stringer, skin/panel, control-surface structure, local
reinforcement) bound to the semantic outer geometry it follows. Its
:class:`MemberSection` is a hollow or plate cross-section whose properties are
purely deterministic closed-form formulas, so a thickness change re-sizes the
member identically on every run and the member mass follows from the material
density and the section area.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from aeroworkbench_airframe import Vec3

from .contracts import content_digest
from .errors import StructuralContractError
from .materials import MemberMaterial

__all__ = [
    "GeometryBinding",
    "MemberKind",
    "MemberOrientation",
    "MemberSection",
    "SectionProperties",
    "SectionShape",
    "StructuralMember",
]


class MemberKind(StrEnum):
    """Generic structural element kinds; no platform-specific assumption."""

    SPAR_CAP = "spar_cap"
    SPAR_WEB = "spar_web"
    RIB = "rib"
    FRAME = "frame"
    BULKHEAD = "bulkhead"
    STRINGER = "stringer"
    SKIN = "skin"
    PANEL = "panel"
    CONTROL_SURFACE = "control_surface"
    REINFORCEMENT = "reinforcement"


class MemberOrientation(StrEnum):
    """How a member follows the outer geometry."""

    SPANWISE = "spanwise"
    CHORDWISE = "chordwise"
    TRANSVERSE = "transverse"
    SURFACE = "surface"


class SectionShape(StrEnum):
    """Closed-form structural cross-sections used by preliminary sizing."""

    BOX = "box"
    TUBE = "tube"
    I_BEAM = "i_beam"
    PLATE = "plate"


@dataclass(frozen=True, slots=True)
class SectionProperties:
    """Deterministic section properties of a member cross-section."""

    area_m2: float
    i_strong_m4: float
    i_weak_m4: float
    torsion_constant_m4: float

    def as_dict(self) -> dict[str, float]:
        return {
            "areaM2": self.area_m2,
            "iStrongM4": self.i_strong_m4,
            "iWeakM4": self.i_weak_m4,
            "torsionConstantM4": self.torsion_constant_m4,
        }


@dataclass(frozen=True, slots=True)
class MemberSection:
    """A cross-section defined by shape, envelope dimensions, and wall thickness."""

    shape: SectionShape
    height_m: float
    width_m: float
    thickness_m: float

    def __post_init__(self) -> None:
        if self.shape not in set(SectionShape):
            raise StructuralContractError(f"UNKNOWN_SECTION_SHAPE:{self.shape}")
        for label, value in (
            ("HEIGHT", self.height_m),
            ("WIDTH", self.width_m),
            ("THICKNESS", self.thickness_m),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise StructuralContractError(f"SECTION_{label}_MUST_BE_POSITIVE")
        limit = self.max_thickness_m()
        if self.thickness_m >= limit:
            raise StructuralContractError(
                f"SECTION_THICKNESS_ABOVE_LIMIT:{self.thickness_m}:{limit}"
            )

    def max_thickness_m(self) -> float:
        """Largest wall thickness that keeps the closed-section geometry valid."""

        if self.shape is SectionShape.PLATE:
            return 0.5 * self.width_m
        if self.shape is SectionShape.TUBE:
            return 0.45 * self.height_m
        if self.shape is SectionShape.BOX:
            return 0.45 * min(self.height_m, self.width_m)
        return 0.45 * min(self.height_m, self.width_m)

    @property
    def extreme_fibre_m(self) -> float:
        if self.shape is SectionShape.PLATE:
            return 0.5 * self.thickness_m
        return 0.5 * self.height_m

    def properties(self) -> SectionProperties:
        return section_properties(self)

    def with_thickness(self, thickness_m: float) -> MemberSection:
        return replace(self, thickness_m=thickness_m)

    def as_dict(self) -> dict[str, Any]:
        return {
            "shape": self.shape.value,
            "heightM": self.height_m,
            "widthM": self.width_m,
            "thicknessM": self.thickness_m,
        }


def section_properties(section: MemberSection) -> SectionProperties:
    """Closed-form area, second moments, and torsion constant of a section."""

    h = section.height_m
    b = section.width_m
    t = section.thickness_m
    shape = section.shape
    if shape is SectionShape.PLATE:
        area = b * t
        i_strong = b * t**3 / 12.0
        i_weak = t * b**3 / 12.0
        torsion = b * t**3 / 3.0
    elif shape is SectionShape.TUBE:
        inner = h - 2.0 * t
        area = math.pi / 4.0 * (h * h - inner * inner)
        i_strong = math.pi / 64.0 * (h**4 - inner**4)
        i_weak = i_strong
        torsion = 2.0 * i_strong
    elif shape is SectionShape.BOX:
        inner_h = h - 2.0 * t
        inner_b = b - 2.0 * t
        if inner_h <= 0.0 or inner_b <= 0.0:
            raise StructuralContractError("BOX_SECTION_WALL_TOO_THICK")
        area = b * h - inner_b * inner_h
        i_strong = (b * h**3 - inner_b * inner_h**3) / 12.0
        i_weak = (h * b**3 - inner_h * inner_b**3) / 12.0
        torsion = (
            2.0 * t * (b - t) ** 2 * (h - t) ** 2 / (b + h - 2.0 * t)
        )
    else:
        web_h = h - 2.0 * t
        if web_h <= 0.0:
            raise StructuralContractError("I_BEAM_SECTION_WALL_TOO_THICK")
        flange_b = b
        area = 2.0 * flange_b * t + web_h * t
        i_strong = (flange_b * h**3 - (flange_b - t) * web_h**3) / 12.0
        i_weak = (2.0 * t * flange_b**3 + web_h * t**3) / 12.0
        torsion = (2.0 * flange_b * t**3 + web_h * t**3) / 3.0
    return SectionProperties(
        area_m2=area,
        i_strong_m4=max(i_strong, 0.0),
        i_weak_m4=max(i_weak, 0.0),
        torsion_constant_m4=max(torsion, 0.0),
    )


@dataclass(frozen=True, slots=True)
class GeometryBinding:
    """Binding of a structural member to the semantic outer geometry it follows."""

    component_id: str
    component_kind: str
    station_fraction: tuple[float, float]
    chord_fraction: float | None = None
    semantic_key: str | None = None

    def __post_init__(self) -> None:
        if not self.component_id.strip():
            raise StructuralContractError("GEOMETRY_BINDING_COMPONENT_ID_REQUIRED")
        if self.component_kind not in (
            "lifting_surface",
            "lofted_body",
            "control_surface",
        ):
            raise StructuralContractError(
                f"UNKNOWN_GEOMETRY_COMPONENT_KIND:{self.component_kind}"
            )
        start, end = self.station_fraction
        if not (0.0 <= start < end <= 1.0):
            raise StructuralContractError("GEOMETRY_BINDING_STATION_RANGE_INVALID")
        if self.chord_fraction is not None and not 0.0 <= self.chord_fraction <= 1.0:
            raise StructuralContractError("GEOMETRY_BINDING_CHORD_FRACTION_INVALID")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "componentId": self.component_id,
            "componentKind": self.component_kind,
            "stationFraction": list(self.station_fraction),
            "chordFraction": self.chord_fraction,
            "semanticKey": self.semantic_key,
        }


@dataclass(frozen=True, slots=True)
class StructuralMember:
    """One typed structural member bound to the outer geometry and a material."""

    member_id: str
    kind: MemberKind
    orientation: MemberOrientation
    geometry: GeometryBinding
    length_m: float
    section: MemberSection
    material: MemberMaterial
    load_share: float
    centroid: Vec3
    buckling_width_m: float | None = None

    def __post_init__(self) -> None:
        if not self.member_id.strip():
            raise StructuralContractError("MEMBER_ID_REQUIRED")
        if not math.isfinite(self.length_m) or self.length_m <= 0.0:
            raise StructuralContractError(f"MEMBER_LENGTH_MUST_BE_POSITIVE:{self.member_id}")
        if not math.isfinite(self.load_share) or not 0.0 <= self.load_share <= 1.0:
            raise StructuralContractError(f"MEMBER_LOAD_SHARE_INVALID:{self.member_id}")
        if self.centroid.dimension != "length":
            raise StructuralContractError(f"MEMBER_CENTROID_NOT_LENGTH:{self.member_id}")
        if self.buckling_width_m is not None and (
            not math.isfinite(self.buckling_width_m) or self.buckling_width_m <= 0.0
        ):
            raise StructuralContractError(f"MEMBER_BUCKLING_WIDTH_INVALID:{self.member_id}")

    @property
    def effective_buckling_width_m(self) -> float:
        return self.buckling_width_m if self.buckling_width_m is not None else self.section.width_m

    def section_properties(self) -> SectionProperties:
        return self.section.properties()

    def mass_kg(self) -> float:
        properties = self.section.properties()
        return self.material.density_kg_m3() * properties.area_m2 * self.length_m

    def with_design(
        self,
        section: MemberSection,
        material: MemberMaterial | None = None,
    ) -> StructuralMember:
        return replace(
            self,
            section=section,
            material=self.material if material is None else material,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "memberId": self.member_id,
            "kind": self.kind.value,
            "orientation": self.orientation.value,
            "geometry": self.geometry.canonical_payload(),
            "lengthM": self.length_m,
            "section": self.section.as_dict(),
            "material": self.material.as_dict(),
            "loadShare": self.load_share,
            "centroid": self.centroid.canonical(),
            "bucklingWidthM": self.buckling_width_m,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())
