"""Structural mass feedback into the AIRFRAME mass/CG/inertia breakdown.

A sized structure is converted into explicit per-member mass updates and applied
to an existing :class:`MassBreakdown` through the AIRFRAME mass participant seam,
so structural mass, centre of gravity, and inertia close the vehicle mass loop
without a parallel mass model. Every update carries its own source record; no
mass is fabricated, and a missing property fails closed in the mass package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aeroworkbench_airframe import IDENTITY, InertiaTensor, Quantity, Vec3
from aeroworkbench_airframe.mass import (
    InstallationTransform,
    MassBreakdown,
    MassCategory,
    MassDistributionUpdate,
    MassItemSource,
    MassUpdate,
    SoftwareIdentity,
    apply_mass_updates,
)
from aeroworkbench_core.types import FidelityLevel, ResultSource

from .members import StructuralMember
from .sizing import SizedStructure
from .stiffness import StiffnessSeam

__all__ = [
    "StructuralMassParticipant",
    "apply_structure_mass",
    "member_inertia",
    "structure_mass_updates",
]

_PARTICIPANT_ID = "generative-airframe-structure"
_SOFTWARE = SoftwareIdentity("aeroworkbench-vehicle-systems-structures", "1.0.0")


def member_inertia(member: StructuralMember, mass_kg: float, frame: str) -> InertiaTensor:
    """Box inertia of a member about its own local CG (all principal moments > 0)."""

    length = member.length_m
    width = member.section.width_m
    height = member.section.height_m
    ixx = mass_kg * (width**2 + height**2) / 12.0
    iyy = mass_kg * (length**2 + height**2) / 12.0
    izz = mass_kg * (length**2 + width**2) / 12.0
    return InertiaTensor(
        ixx=Quantity(value=ixx, unit="kg.m2"),
        iyy=Quantity(value=iyy, unit="kg.m2"),
        izz=Quantity(value=izz, unit="kg.m2"),
        ixy=Quantity(value=0.0, unit="kg.m2"),
        ixz=Quantity(value=0.0, unit="kg.m2"),
        iyz=Quantity(value=0.0, unit="kg.m2"),
        frame=frame,
    )


def structure_mass_updates(
    sized: SizedStructure,
    *,
    frame: str | None = None,
    category: MassCategory = MassCategory.STRUCTURE,
) -> tuple[MassUpdate, ...]:
    """One mass update per sized structural member, with local inertia and CG."""

    target_frame = frame or sized.frame
    updates: list[MassUpdate] = []
    for candidate in sized.members:
        member = candidate.member
        local_frame = f"{member.member_id}-cg"
        translation = Vec3(
            x=member.centroid.value_si[0],
            y=member.centroid.value_si[1],
            z=member.centroid.value_si[2],
            unit="m",
            frame=target_frame,
        )
        updates.append(
            MassUpdate(
                item_id=f"structure.{member.member_id}",
                mass=Quantity(value=candidate.mass_kg, unit="kg"),
                reason=f"generative sizing of {member.kind.value}",
                cg=Vec3(x=0.0, y=0.0, z=0.0, unit="m", frame=local_frame),
                inertia=member_inertia(member, candidate.mass_kg, local_frame),
                installation=InstallationTransform(
                    from_frame=local_frame,
                    to_frame=target_frame,
                    translation=translation,
                    rotation=IDENTITY,
                ),
                category=category,
                source=MassItemSource(
                    source=ResultSource.ANALYTICAL,
                    fidelity=FidelityLevel.ANALYTICAL,
                    method="preliminary-beam-sizing",
                    reference=f"vs01:{sized.architecture_id}",
                    digest=sized.digest,
                    software=_SOFTWARE,
                ),
            )
        )
    return tuple(updates)


def apply_structure_mass(
    sized: SizedStructure,
    breakdown: MassBreakdown,
    *,
    frame: str | None = None,
    category: MassCategory = MassCategory.STRUCTURE,
) -> MassDistributionUpdate:
    """Apply the sized structure's mass updates to an existing breakdown."""

    return apply_mass_updates(
        breakdown,
        structure_mass_updates(sized, frame=frame, category=category),
    )


@dataclass(frozen=True, slots=True)
class StructuralMassParticipant:
    """A typed AIRFRAME mass participant exposing the sized structure's mass."""

    sized: SizedStructure
    frame: str | None = None
    category: MassCategory = MassCategory.STRUCTURE

    @property
    def participant_id(self) -> str:
        return _PARTICIPANT_ID

    def mass_updates(self, context: Mapping[str, Any]) -> tuple[MassUpdate, ...]:
        frame = self.frame
        if frame is None:
            override = context.get("frame")
            frame = override if isinstance(override, str) and override.strip() else None
        return structure_mass_updates(self.sized, frame=frame, category=self.category)

    def stiffness(self) -> StiffnessSeam:
        return self.sized.stiffness
