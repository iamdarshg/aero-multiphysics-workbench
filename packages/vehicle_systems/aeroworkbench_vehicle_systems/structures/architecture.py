"""Generative structural architecture from semantic outer geometry.

The generator turns a generic :class:`LiftingSurface`, :class:`LoftedBody`, or
:class:`ControlSurface` into a typed internal structure of spars, caps, webs,
ribs, frames/bulkheads, stringers, and skin/panel members. Every choice is a
declared parameter (spar count, rib count, stringer count, margins, architecture
branch); no product- or platform-specific constant is embedded. The generated
layout is deterministic and hashable, and each member is bound back to the outer
geometry region it follows through a :class:`GeometryBinding`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from math import cos, isfinite, pi, sin
from typing import Any

from aeroworkbench_airframe import Vec3
from aeroworkbench_airframe.aero_geometry import (
    ControlSurface,
    LiftingSurface,
    LoftedBody,
    SpanwiseStation,
)

from .contracts import content_digest
from .errors import StructuralLayoutError
from .materials import MemberMaterial
from .members import (
    GeometryBinding,
    MemberKind,
    MemberOrientation,
    MemberSection,
    SectionShape,
    StructuralMember,
)

__all__ = [
    "ArchitectureKind",
    "StructuralArchitecture",
    "generate_body_architecture",
    "generate_control_surface_architecture",
    "generate_wing_architecture",
]

_LOAD_WEIGHTS: dict[MemberKind, float] = {
    MemberKind.SPAR_CAP: 1.0,
    MemberKind.SPAR_WEB: 0.1,
    MemberKind.STRINGER: 0.05,
    MemberKind.SKIN: 0.1,
    MemberKind.PANEL: 0.1,
    MemberKind.CONTROL_SURFACE: 1.0,
    MemberKind.RIB: 0.0,
    MemberKind.FRAME: 0.0,
    MemberKind.BULKHEAD: 0.0,
    MemberKind.REINFORCEMENT: 0.0,
}


class ArchitectureKind(StrEnum):
    """Structural architecture branches for a lifting surface."""

    MONOCOQUE = "monocoque"
    SEMI_MONOCOQUE = "semi_monocoque"
    MULTI_SPAR = "multi_spar"
    WINGBOX = "wingbox"
    SHELL = "shell"
    GENERAL = "general"


@dataclass(frozen=True, slots=True)
class StructuralArchitecture:
    """A deterministic, hashable set of typed structural members."""

    architecture_id: str
    kind: ArchitectureKind
    frame: str
    component_id: str
    members: tuple[StructuralMember, ...]
    reference_span_m: float
    reference_chord_m: float
    reference_area_m2: float

    def __post_init__(self) -> None:
        if not self.architecture_id.strip() or not self.frame.strip():
            raise StructuralLayoutError("ARCHITECTURE_ID_AND_FRAME_REQUIRED")
        if not self.members:
            raise StructuralLayoutError("ARCHITECTURE_REQUIRES_MEMBERS")
        identifiers = [member.member_id for member in self.members]
        if len(identifiers) != len(set(identifiers)):
            raise StructuralLayoutError("ARCHITECTURE_DUPLICATE_MEMBER_ID")
        for label, value in (
            ("SPAN", self.reference_span_m),
            ("CHORD", self.reference_chord_m),
            ("AREA", self.reference_area_m2),
        ):
            if not isfinite(value) or value <= 0.0:
                raise StructuralLayoutError(f"ARCHITECTURE_REFERENCE_{label}_INVALID")

    def member(self, member_id: str) -> StructuralMember:
        for candidate in self.members:
            if candidate.member_id == member_id:
                return candidate
        raise StructuralLayoutError(f"UNKNOWN_MEMBER:{member_id}")

    def sorted_members(self) -> tuple[StructuralMember, ...]:
        return tuple(sorted(self.members, key=lambda member: member.member_id))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "architectureId": self.architecture_id,
            "kind": self.kind.value,
            "frame": self.frame,
            "componentId": self.component_id,
            "referenceSpanM": self.reference_span_m,
            "referenceChordM": self.reference_chord_m,
            "referenceAreaM2": self.reference_area_m2,
            "members": [member.canonical_payload() for member in self.sorted_members()],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def _linspace(start: float, stop: float, count: int) -> tuple[float, ...]:
    if count <= 0:
        raise StructuralLayoutError("LAYOUT_COUNT_MUST_BE_POSITIVE")
    if count == 1:
        return (0.5 * (start + stop),)
    step = (stop - start) / (count - 1)
    return tuple(start + step * index for index in range(count))


def _wing_planform(surface: LiftingSurface) -> tuple[float, float, float]:
    span_mm = surface.span_mm
    if surface.planform is not None:
        return span_mm, surface.planform.root_chord_mm, surface.planform.tip_chord_mm
    return span_mm, surface.stations[0].chord_mm, surface.stations[-1].chord_mm


def _chord_at(root_chord_mm: float, tip_chord_mm: float, fraction: float) -> float:
    return root_chord_mm + (tip_chord_mm - root_chord_mm) * fraction


def _station_for(surface: LiftingSurface, fraction: float) -> SpanwiseStation:
    return min(surface.stations, key=lambda station: abs(station.span_fraction - fraction))


def _airfoil_thickness_m(
    surface: LiftingSurface, chord_fraction: float, span_fraction: float
) -> float:
    root_mm, tip_mm = _wing_planform(surface)[1:]
    chord_mm = _chord_at(root_mm, tip_mm, span_fraction)
    profile = _station_for(surface, span_fraction).profile
    thickness = profile.upper(chord_fraction) - profile.lower(chord_fraction)
    return max(thickness, 1.0e-4) * chord_mm * 1.0e-3


def _normalize_shares(members: list[StructuralMember]) -> tuple[StructuralMember, ...]:
    weights = [_LOAD_WEIGHTS[member.kind] for member in members]
    total = sum(weights)
    if total <= 0.0:
        return tuple(members)
    return tuple(
        replace(member, load_share=weight / total)
        for member, weight in zip(members, weights, strict=True)
    )


def _cap_section(thickness: float, airfoil_thickness_m: float) -> MemberSection:
    height = max(airfoil_thickness_m, 1.0e-3)
    width = max(0.3 * height, 3.0e-4)
    limit = 0.45 * min(height, width)
    return MemberSection(
        shape=SectionShape.I_BEAM,
        height_m=height,
        width_m=width,
        thickness_m=min(thickness, 0.9 * limit),
    )


def _plate_section(thickness: float, width_m: float) -> MemberSection:
    width = max(width_m, 1.0e-3)
    return MemberSection(
        shape=SectionShape.PLATE,
        height_m=width,
        width_m=width,
        thickness_m=min(thickness, 0.5 * width) * 0.999,
    )


def _tube_section(thickness: float, diameter_m: float) -> MemberSection:
    diameter = max(diameter_m, 1.0e-3)
    return MemberSection(
        shape=SectionShape.TUBE,
        height_m=diameter,
        width_m=diameter,
        thickness_m=min(thickness, 0.45 * diameter) * 0.999,
    )


def generate_wing_architecture(
    surface: LiftingSurface,
    *,
    material: MemberMaterial,
    architecture_id: str | None = None,
    kind: ArchitectureKind = ArchitectureKind.WINGBOX,
    spar_count: int = 2,
    rib_count: int = 5,
    stringer_count: int = 4,
    spar_root_fraction: float = 0.20,
    spar_tip_fraction: float = 0.70,
    initial_thickness_m: float = 1.0e-3,
) -> StructuralArchitecture:
    """Generate a generic wing internal structure from a lifting surface.

    Spar chord fractions default to the structural box (20%-70% chord) where
    airfoil depth supports preliminary sizing.
    """

    if len(surface.stations) < 2:
        raise StructuralLayoutError("WING_LAYOUT_NEEDS_TWO_STATIONS")
    if not 0.0 <= spar_root_fraction < spar_tip_fraction <= 1.0:
        raise StructuralLayoutError("WING_SPAR_MARGINS_INVALID")
    if kind not in set(ArchitectureKind):
        raise StructuralLayoutError(f"UNKNOWN_ARCHITECTURE_KIND:{kind}")
    identifier = architecture_id or f"{surface.surface_id}-structure"
    span_mm, root_chord_mm, tip_chord_mm = _wing_planform(surface)
    span_m = span_mm * 1.0e-3
    mean_chord_m = 0.5 * (root_chord_mm + tip_chord_mm) * 1.0e-3
    frame = surface.frame
    members: list[StructuralMember] = []

    def spanwise(
        member_id: str,
        member_kind: MemberKind,
        chord_fraction: float,
        section: MemberSection,
        span_fraction: float,
    ) -> StructuralMember:
        chord_mid_m = _chord_at(root_chord_mm, tip_chord_mm, span_fraction) * 1.0e-3
        return StructuralMember(
            member_id=member_id,
            kind=member_kind,
            orientation=MemberOrientation.SPANWISE,
            geometry=GeometryBinding(
                component_id=surface.surface_id,
                component_kind="lifting_surface",
                station_fraction=(0.0, 1.0),
                chord_fraction=chord_fraction,
                semantic_key=f"{surface.surface_id}.{member_id}",
            ),
            length_m=span_m,
            section=section,
            material=material,
            load_share=1.0,
            centroid=Vec3(
                x=chord_fraction * chord_mid_m,
                y=0.0,
                z=span_fraction * span_m,
                unit="m",
                frame=frame,
            ),
        )

    spar_fractions: tuple[float, ...] = ()
    if kind in (ArchitectureKind.WINGBOX, ArchitectureKind.MULTI_SPAR):
        spar_fractions = _linspace(spar_root_fraction, spar_tip_fraction, spar_count)
    for index, chord_fraction in enumerate(spar_fractions):
        thickness = _airfoil_thickness_m(surface, chord_fraction, 0.5)
        members.append(
            spanwise(
                f"spar-{index + 1}-cap",
                MemberKind.SPAR_CAP,
                chord_fraction,
                _cap_section(initial_thickness_m, thickness),
                0.5,
            )
        )
        members.append(
            spanwise(
                f"spar-{index + 1}-web",
                MemberKind.SPAR_WEB,
                chord_fraction,
                _plate_section(initial_thickness_m, thickness),
                0.5,
            )
        )

    for index, span_fraction in enumerate(_linspace(0.0, 1.0, rib_count)):
        chord_m = _chord_at(root_chord_mm, tip_chord_mm, span_fraction) * 1.0e-3
        thickness = _airfoil_thickness_m(surface, 0.3, span_fraction)
        half = 0.5 / max(rib_count, 1)
        members.append(
            StructuralMember(
                member_id=f"rib-{index + 1}",
                kind=MemberKind.RIB,
                orientation=MemberOrientation.CHORDWISE,
                geometry=GeometryBinding(
                    component_id=surface.surface_id,
                    component_kind="lifting_surface",
                    station_fraction=(
                        max(span_fraction - half, 0.0),
                        min(span_fraction + half, 1.0),
                    ),
                    chord_fraction=None,
                    semantic_key=f"{surface.surface_id}.rib-{index + 1}",
                ),
                length_m=chord_m,
                section=_plate_section(initial_thickness_m, thickness),
                material=material,
                load_share=0.0,
                centroid=Vec3(
                    x=0.5 * chord_m,
                    y=0.0,
                    z=span_fraction * span_m,
                    unit="m",
                    frame=frame,
                ),
            )
        )

    if (
        kind
        in (
            ArchitectureKind.SEMI_MONOCOQUE,
            ArchitectureKind.MULTI_SPAR,
            ArchitectureKind.WINGBOX,
        )
        and stringer_count > 0
    ):
        grid = _linspace(spar_root_fraction, spar_tip_fraction, stringer_count + 2)
        for index, chord_fraction in enumerate(grid[1:-1]):
            thickness = _airfoil_thickness_m(surface, chord_fraction, 0.5)
            members.append(
                spanwise(
                    f"stringer-{index + 1}",
                    MemberKind.STRINGER,
                    chord_fraction,
                    _tube_section(initial_thickness_m, 0.3 * thickness),
                    0.5,
                )
            )

    if kind is not ArchitectureKind.SHELL:
        skin_offset = _airfoil_thickness_m(surface, 0.3, 0.5) * 0.5
        panel_width_m = (
            mean_chord_m / (stringer_count + 1)
            if stringer_count > 0
            else 0.5 * mean_chord_m
        )
        for name, sign in (("upper", 1.0), ("lower", -1.0)):
            members.append(
                StructuralMember(
                    member_id=f"skin-{name}",
                    kind=MemberKind.SKIN,
                    orientation=MemberOrientation.SURFACE,
                    geometry=GeometryBinding(
                        component_id=surface.surface_id,
                        component_kind="lifting_surface",
                        station_fraction=(0.0, 1.0),
                        chord_fraction=None,
                        semantic_key=f"{surface.surface_id}.{name}",
                    ),
                    length_m=span_m,
                    section=_plate_section(initial_thickness_m, mean_chord_m),
                    material=material,
                    load_share=0.0,
                    centroid=Vec3(
                        x=0.5 * mean_chord_m,
                        y=sign * skin_offset,
                        z=0.5 * span_m,
                        unit="m",
                        frame=frame,
                    ),
                    buckling_width_m=panel_width_m,
                )
            )

    return StructuralArchitecture(
        architecture_id=identifier,
        kind=kind,
        frame=frame,
        component_id=surface.surface_id,
        members=_normalize_shares(members),
        reference_span_m=span_m,
        reference_chord_m=mean_chord_m,
        reference_area_m2=span_m * mean_chord_m,
    )


def generate_body_architecture(
    body: LoftedBody,
    *,
    material: MemberMaterial,
    architecture_id: str | None = None,
    kind: ArchitectureKind = ArchitectureKind.SEMI_MONOCOQUE,
    frame_count: int = 4,
    stringer_count: int = 6,
    initial_thickness_m: float = 1.0e-3,
) -> StructuralArchitecture:
    """Generate a generic fuselage/body structure (frames, stringers, shell)."""

    if len(body.sections) < 2:
        raise StructuralLayoutError("BODY_LAYOUT_NEEDS_TWO_SECTIONS")
    identifier = architecture_id or f"{body.body_id}-structure"
    frame = body.frame
    length_m = body.length_mm * 1.0e-3
    max_height_m = max(section.height_mm for section in body.sections) * 1.0e-3
    max_width_m = max(section.width_mm for section in body.sections) * 1.0e-3
    mean_diameter_m = 0.5 * (max_width_m + max_height_m)
    mean_circumference_m = pi * mean_diameter_m
    members: list[StructuralMember] = []

    for index, station_fraction in enumerate(_linspace(0.0, 1.0, frame_count)):
        section = min(
            body.sections, key=lambda item: abs(item.station_fraction - station_fraction)
        )
        diameter_m = 0.5 * (section.width_mm + section.height_mm) * 1.0e-3
        half = 0.5 / max(frame_count, 1)
        members.append(
            StructuralMember(
                member_id=f"frame-{index + 1}",
                kind=MemberKind.FRAME,
                orientation=MemberOrientation.TRANSVERSE,
                geometry=GeometryBinding(
                    component_id=body.body_id,
                    component_kind="lofted_body",
                    station_fraction=(
                        max(station_fraction - half, 0.0),
                        min(station_fraction + half, 1.0),
                    ),
                    chord_fraction=None,
                    semantic_key=f"{body.body_id}.frame-{index + 1}",
                ),
                length_m=pi * diameter_m,
                section=_tube_section(initial_thickness_m, 0.05 * diameter_m),
                material=material,
                load_share=0.0,
                centroid=Vec3(
                    x=section.spine_mm[0] * 1.0e-3,
                    y=section.spine_mm[1] * 1.0e-3,
                    z=section.spine_mm[2] * 1.0e-3,
                    unit="m",
                    frame=frame,
                ),
            )
        )

    radius = 0.5 * max_height_m
    for index in range(stringer_count):
        angle = 2.0 * pi * index / max(stringer_count, 1)
        members.append(
            StructuralMember(
                member_id=f"stringer-{index + 1}",
                kind=MemberKind.STRINGER,
                orientation=MemberOrientation.SPANWISE,
                geometry=GeometryBinding(
                    component_id=body.body_id,
                    component_kind="lofted_body",
                    station_fraction=(0.0, 1.0),
                    chord_fraction=None,
                    semantic_key=f"{body.body_id}.stringer-{index + 1}",
                ),
                length_m=length_m,
                section=_tube_section(initial_thickness_m, 0.05 * max_height_m),
                material=material,
                load_share=0.5,
                centroid=Vec3(
                    x=radius * cos(angle),
                    y=radius * sin(angle),
                    z=0.5 * length_m,
                    unit="m",
                    frame=frame,
                ),
            )
        )

    members.append(
        StructuralMember(
            member_id="shell",
            kind=MemberKind.SKIN,
            orientation=MemberOrientation.SURFACE,
            geometry=GeometryBinding(
                component_id=body.body_id,
                component_kind="lofted_body",
                station_fraction=(0.0, 1.0),
                chord_fraction=None,
                semantic_key=f"{body.body_id}.shell",
            ),
            length_m=length_m,
            section=_plate_section(initial_thickness_m, mean_circumference_m),
            material=material,
            load_share=0.5,
            centroid=Vec3(
                x=0.0, y=0.5 * mean_diameter_m, z=0.5 * length_m, unit="m", frame=frame
            ),
            buckling_width_m=length_m / max(frame_count, 1),
        )
    )

    return StructuralArchitecture(
        architecture_id=identifier,
        kind=kind,
        frame=frame,
        component_id=body.body_id,
        members=_normalize_shares(members),
        reference_span_m=length_m,
        reference_chord_m=mean_circumference_m,
        reference_area_m2=length_m * mean_circumference_m,
    )


def generate_control_surface_architecture(
    control: ControlSurface,
    parent: LiftingSurface,
    *,
    material: MemberMaterial,
    architecture_id: str | None = None,
    rib_count: int = 2,
    initial_thickness_m: float = 1.0e-3,
) -> StructuralArchitecture:
    """Generate a generic control-surface structure bound to its parent surface."""

    if control.parent_id != parent.surface_id:
        raise StructuralLayoutError(
            f"CONTROL_SURFACE_PARENT_MISMATCH:{control.parent_id}:{parent.surface_id}"
        )
    identifier = architecture_id or f"{control.control_id}-structure"
    frame = parent.frame
    span_mm, root_chord_mm, tip_chord_mm = _wing_planform(parent)
    start, end = control.span_fraction
    span_m = span_mm * 1.0e-3
    control_span_m = (end - start) * span_m
    mid_fraction = 0.5 * (start + end)
    outboard_chord_m = _chord_at(root_chord_mm, tip_chord_mm, mid_fraction) * 1.0e-3
    control_chord_m = (1.0 - control.hinge_fraction) * outboard_chord_m
    spar_fraction = 0.5 * (control.hinge_fraction + 1.0)
    thickness = max(0.12 * control_chord_m, 1.0e-3)
    members: list[StructuralMember] = []

    def spanwise(
        member_id: str, member_kind: MemberKind, section: MemberSection
    ) -> StructuralMember:
        return StructuralMember(
            member_id=member_id,
            kind=member_kind,
            orientation=MemberOrientation.SPANWISE,
            geometry=GeometryBinding(
                component_id=control.control_id,
                component_kind="control_surface",
                station_fraction=(start, end),
                chord_fraction=spar_fraction,
                semantic_key=f"{control.control_id}.{member_id}",
            ),
            length_m=control_span_m,
            section=section,
            material=material,
            load_share=1.0,
            centroid=Vec3(
                x=spar_fraction * outboard_chord_m,
                y=0.0,
                z=0.5 * (start + end) * span_m,
                unit="m",
                frame=frame,
            ),
        )

    members.append(
        spanwise("spar-cap", MemberKind.SPAR_CAP, _cap_section(initial_thickness_m, thickness))
    )
    members.append(
        spanwise("spar-web", MemberKind.SPAR_WEB, _plate_section(initial_thickness_m, thickness))
    )

    for index, fraction in enumerate(_linspace(start, end, rib_count)):
        members.append(
            StructuralMember(
                member_id=f"rib-{index + 1}",
                kind=MemberKind.RIB,
                orientation=MemberOrientation.CHORDWISE,
                geometry=GeometryBinding(
                    component_id=control.control_id,
                    component_kind="control_surface",
                    station_fraction=(start, end),
                    chord_fraction=None,
                    semantic_key=f"{control.control_id}.rib-{index + 1}",
                ),
                length_m=control_chord_m,
                section=_plate_section(initial_thickness_m, thickness),
                material=material,
                load_share=0.0,
                centroid=Vec3(
                    x=0.5 * (control.hinge_fraction + 1.0) * outboard_chord_m,
                    y=0.0,
                    z=fraction * span_m,
                    unit="m",
                    frame=frame,
                ),
            )
        )

    for name, sign in (("upper", 1.0), ("lower", -1.0)):
        members.append(
            StructuralMember(
                member_id=f"skin-{name}",
                kind=MemberKind.CONTROL_SURFACE,
                orientation=MemberOrientation.SURFACE,
                geometry=GeometryBinding(
                    component_id=control.control_id,
                    component_kind="control_surface",
                    station_fraction=(start, end),
                    chord_fraction=None,
                    semantic_key=f"{control.control_id}.{name}",
                ),
                length_m=control_span_m,
                section=_plate_section(initial_thickness_m, max(control_chord_m, 1.0e-3)),
                material=material,
                load_share=1.0,
                centroid=Vec3(
                    x=0.5 * (control.hinge_fraction + 1.0) * outboard_chord_m,
                    y=sign * 0.5 * thickness,
                    z=0.5 * (start + end) * span_m,
                    unit="m",
                    frame=frame,
                ),
                buckling_width_m=max(control_chord_m, 1.0e-3) / (rib_count + 1),
            )
        )

    return StructuralArchitecture(
        architecture_id=identifier,
        kind=ArchitectureKind.GENERAL,
        frame=frame,
        component_id=control.control_id,
        members=_normalize_shares(members),
        reference_span_m=control_span_m,
        reference_chord_m=control_chord_m,
        reference_area_m2=control_span_m * control_chord_m,
    )
