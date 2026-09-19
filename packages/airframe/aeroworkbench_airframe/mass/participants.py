"""Typed structural-participant seam for post-sizing mass-distribution updates.

A structural (or propulsion/battery) participant returns explicit
:class:`MassUpdate` records after sizing. Updates are applied to a
:class:`MassBreakdown` by id; an update for an unknown item must carry a full
replacement, so no property is silently defaulted. The seam is a protocol and a
plain function, not an import of any structural package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..state import InertiaTensor
from ..units import Quantity, Vec3, require_dimension
from .contracts import (
    InstallationTransform,
    MassBreakdown,
    MassCategory,
    MassItem,
    MassItemSource,
    MassResultMeta,
    result_meta,
)
from .errors import MassParticipantError

MODEL = "airframe-mass-participants"

_ASSUMPTIONS = (
    "Participants return explicit updates; no mass default is injected.",
    "An update for a new item must state category, CG, inertia, and installation.",
    "Updates are applied in declared order and remain deterministic.",
)


@dataclass(frozen=True, slots=True)
class MassUpdate:
    """One participant's post-sizing restatement of a component's mass properties."""

    item_id: str
    mass: Quantity
    reason: str
    cg: Vec3 | None = None
    inertia: InertiaTensor | None = None
    installation: InstallationTransform | None = None
    category: MassCategory | None = None
    source: MassItemSource | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("MASS_UPDATE_ITEM_ID_REQUIRED")
        if not self.reason.strip():
            raise ValueError("MASS_UPDATE_REASON_REQUIRED")
        require_dimension(self.mass, "mass", f"massUpdate.{self.item_id}.mass")
        if self.mass.value_si <= 0:
            raise ValueError(f"NONPOSITIVE_MASS_UPDATE:{self.item_id}")
        if self.cg is not None:
            require_dimension(self.cg, "length", f"massUpdate.{self.item_id}.cg")
        if (
            self.inertia is not None
            and self.installation is not None
            and self.inertia.frame != self.installation.from_frame
        ):
            raise ValueError(f"MASS_UPDATE_INERTIA_FRAME_MISMATCH:{self.item_id}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "itemId": self.item_id,
            "mass": self.mass.canonical(),
            "reason": self.reason,
            "cg": None if self.cg is None else self.cg.canonical(),
            "inertia": None if self.inertia is None else self.inertia.canonical(),
            "installation": None if self.installation is None else self.installation.as_dict(),
            "category": None if self.category is None else self.category.value,
            "source": None if self.source is None else self.source.as_dict(),
        }


@runtime_checkable
class MassParticipant(Protocol):
    """A typed producer of mass updates after its own sizing pass."""

    @property
    def participant_id(self) -> str: ...

    def mass_updates(self, context: Mapping[str, Any]) -> tuple[MassUpdate, ...]: ...


@dataclass(frozen=True, slots=True)
class MassDistributionUpdate:
    """The resulting breakdown plus the ids that were updated and added."""

    breakdown: MassBreakdown
    updated_item_ids: tuple[str, ...]
    added_item_ids: tuple[str, ...]
    meta: MassResultMeta

    def as_dict(self) -> dict[str, Any]:
        return {
            "breakdown": self.breakdown.canonical(),
            "updatedItemIds": list(self.updated_item_ids),
            "addedItemIds": list(self.added_item_ids),
            "meta": self.meta.as_dict(),
        }


def _apply_one(breakdown: MassBreakdown, update: MassUpdate) -> MassItem:
    try:
        existing = breakdown.item(update.item_id)
    except KeyError:
        existing = None
    if existing is None:
        if (
            update.category is None
            or update.cg is None
            or update.inertia is None
            or update.installation is None
            or update.source is None
        ):
            raise MassParticipantError(f"NEW_MASS_ITEM_REQUIRES_FULL_PROPERTIES:{update.item_id}")
        return MassItem(
            item_id=update.item_id,
            category=update.category,
            mass=update.mass,
            cg=update.cg,
            inertia=update.inertia,
            installation=update.installation,
            source=update.source,
        )
    return MassItem(
        item_id=existing.item_id,
        category=existing.category if update.category is None else update.category,
        mass=update.mass,
        cg=existing.cg if update.cg is None else update.cg,
        inertia=existing.inertia if update.inertia is None else update.inertia,
        installation=existing.installation if update.installation is None else update.installation,
        source=existing.source if update.source is None else update.source,
    )


def apply_mass_updates(
    breakdown: MassBreakdown,
    updates: tuple[MassUpdate, ...],
) -> MassDistributionUpdate:
    """Apply updates deterministically; fail closed on duplicate or partial data."""
    identifiers = [update.item_id for update in updates]
    if len(identifiers) != len(set(identifiers)):
        raise MassParticipantError("DUPLICATE_MASS_UPDATE")
    updated_ids: list[str] = []
    added_ids: list[str] = []
    result = breakdown
    known = {item.item_id for item in breakdown.items}
    for update in updates:
        if update.item_id in known:
            updated_ids.append(update.item_id)
        else:
            added_ids.append(update.item_id)
            known.add(update.item_id)
        result = result.with_item(_apply_one(result, update))
    meta = result_meta(
        model=MODEL,
        inputs={
            "breakdown": breakdown.canonical(),
            "updates": [update.as_dict() for update in updates],
        },
        valid=True,
        notes=("updates applied",),
        assumptions=_ASSUMPTIONS,
    )
    return MassDistributionUpdate(
        breakdown=result,
        updated_item_ids=tuple(updated_ids),
        added_item_ids=tuple(added_ids),
        meta=meta,
    )


def apply_participants(
    breakdown: MassBreakdown,
    participants: tuple[MassParticipant, ...],
    context: Mapping[str, Any],
) -> MassDistributionUpdate:
    """Collect updates from every participant in declared order and apply them."""
    ordered = tuple(sorted(participants, key=lambda participant: participant.participant_id))
    collected: list[MassUpdate] = []
    for participant in ordered:
        if not participant.participant_id.strip():
            raise MassParticipantError("MASS_PARTICIPANT_ID_REQUIRED")
        collected.extend(participant.mass_updates(context))
    return apply_mass_updates(breakdown, tuple(collected))
