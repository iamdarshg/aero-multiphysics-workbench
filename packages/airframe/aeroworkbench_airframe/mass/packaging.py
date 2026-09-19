"""Lightweight axis-aligned packaging envelopes, keep-outs, and intersection checks.

Packaging uses bounding boxes only, so impossible layouts are rejected before any
heavy CAD or meshing work. A layout that intersects a keep-out, overlaps another
component, or falls outside every declared bay yields explicit infeasible
findings rather than an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..units import Vec3, require_dimension
from .contracts import MassItemSource, MassResultMeta, result_meta

MODEL = "airframe-mass-packaging"

_ASSUMPTIONS = (
    "Axis-aligned bounding boxes only; no CAD kernel is evaluated here.",
    "Touching faces are not an intersection; positive overlap is required.",
    "Keep-out volumes must remain empty and placements must sit inside a bay.",
)

_CONTAINMENT_TOLERANCE = 1e-9


class PackageVolumeKind(StrEnum):
    BAY = "bay"
    KEEPOUT = "keepout"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned box in a declared frame; all components are lengths."""

    frame: str
    minimum: Vec3
    maximum: Vec3

    def __post_init__(self) -> None:
        if not self.frame.strip():
            raise ValueError("BOUNDING_BOX_FRAME_REQUIRED")
        require_dimension(self.minimum, "length", "boundingBox.minimum")
        require_dimension(self.maximum, "length", "boundingBox.maximum")
        if self.minimum.frame != self.frame or self.maximum.frame != self.frame:
            raise ValueError("BOUNDING_BOX_FRAME_MISMATCH")
        low = self.minimum.value_si
        high = self.maximum.value_si
        for axis in range(3):
            if low[axis] > high[axis]:
                raise ValueError(f"BOUNDING_BOX_MIN_EXCEEDS_MAX:{axis}")

    def overlaps(self, other: BoundingBox, *, tolerance: float = 0.0) -> bool:
        if self.frame != other.frame:
            raise ValueError("BOUNDING_BOX_FRAME_MISMATCH")
        low_a = self.minimum.value_si
        high_a = self.maximum.value_si
        low_b = other.minimum.value_si
        high_b = other.maximum.value_si
        for axis in range(3):
            if min(high_a[axis], high_b[axis]) - max(low_a[axis], low_b[axis]) <= tolerance:
                return False
        return True

    def contains(self, inner: BoundingBox, *, tolerance: float = _CONTAINMENT_TOLERANCE) -> bool:
        if self.frame != inner.frame:
            raise ValueError("BOUNDING_BOX_FRAME_MISMATCH")
        low = self.minimum.value_si
        high = self.maximum.value_si
        inner_low = inner.minimum.value_si
        inner_high = inner.maximum.value_si
        for axis in range(3):
            if inner_low[axis] < low[axis] - tolerance or inner_high[axis] > high[axis] + tolerance:
                return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "minimum": self.minimum.canonical(),
            "maximum": self.maximum.canonical(),
        }


@dataclass(frozen=True, slots=True)
class PackageVolume:
    """A declared bay or keep-out envelope with provenance."""

    volume_id: str
    kind: PackageVolumeKind
    box: BoundingBox
    source: MassItemSource

    def __post_init__(self) -> None:
        if not self.volume_id.strip():
            raise ValueError("PACKAGE_VOLUME_ID_REQUIRED")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.volume_id,
            "kind": self.kind.value,
            "box": self.box.as_dict(),
            "source": self.source.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class Placement:
    """A component's installed bounding box within the layout frame."""

    item_id: str
    box: BoundingBox

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("PLACEMENT_ITEM_ID_REQUIRED")

    def as_dict(self) -> dict[str, Any]:
        return {"itemId": self.item_id, "box": self.box.as_dict()}


@dataclass(frozen=True, slots=True)
class PackagingLayout:
    """Declared bays/keep-outs plus installed component bounding boxes."""

    frame: str
    volumes: tuple[PackageVolume, ...] = field(default_factory=tuple)
    placements: tuple[Placement, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.frame.strip():
            raise ValueError("PACKAGING_LAYOUT_FRAME_REQUIRED")
        volume_ids = [volume.volume_id for volume in self.volumes]
        if len(volume_ids) != len(set(volume_ids)):
            raise ValueError("DUPLICATE_PACKAGE_VOLUME_ID")
        placement_ids = [placement.item_id for placement in self.placements]
        if len(placement_ids) != len(set(placement_ids)):
            raise ValueError("DUPLICATE_PLACEMENT_ITEM_ID")
        for volume in self.volumes:
            if volume.box.frame != self.frame:
                raise ValueError(f"PACKAGE_VOLUME_FRAME_MISMATCH:{volume.volume_id}")
        for placement in self.placements:
            if placement.box.frame != self.frame:
                raise ValueError(f"PLACEMENT_FRAME_MISMATCH:{placement.item_id}")

    def bays(self) -> tuple[PackageVolume, ...]:
        return tuple(volume for volume in self.volumes if volume.kind is PackageVolumeKind.BAY)

    def keepouts(self) -> tuple[PackageVolume, ...]:
        return tuple(
            volume for volume in self.volumes if volume.kind is PackageVolumeKind.KEEPOUT
        )

    def sorted_volumes(self) -> tuple[PackageVolume, ...]:
        return tuple(sorted(self.volumes, key=lambda volume: volume.volume_id))

    def sorted_placements(self) -> tuple[Placement, ...]:
        return tuple(sorted(self.placements, key=lambda placement: placement.item_id))

    def canonical(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "volumes": [volume.as_dict() for volume in self.sorted_volumes()],
            "placements": [placement.as_dict() for placement in self.sorted_placements()],
        }

    def as_dict(self) -> dict[str, Any]:
        return self.canonical()


@dataclass(frozen=True, slots=True)
class PackagingFinding:
    code: str
    detail: str
    entities: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "entities": list(self.entities)}


@dataclass(frozen=True, slots=True)
class PackagingReport:
    findings: tuple[PackagingFinding, ...]
    meta: MassResultMeta

    @property
    def feasible(self) -> bool:
        return not self.findings

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(finding.detail for finding in self.findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [finding.as_dict() for finding in self.findings],
            "meta": self.meta.as_dict(),
        }


def evaluate_packaging(layout: PackagingLayout) -> PackagingReport:
    """Check keep-outs, component intersections, and bay containment."""
    findings: list[PackagingFinding] = []
    bays = layout.bays()
    keepouts = layout.keepouts()
    placements = layout.sorted_placements()

    for placement in placements:
        for keepout in sorted(keepouts, key=lambda volume: volume.volume_id):
            if placement.box.overlaps(keepout.box):
                findings.append(
                    PackagingFinding(
                        code="KEEPOUT_INTERSECTION",
                        detail=(
                            f"placement {placement.item_id} intersects keep-out "
                            f"{keepout.volume_id}"
                        ),
                        entities=(placement.item_id, keepout.volume_id),
                    )
                )

    for index, first in enumerate(placements):
        for second in placements[index + 1 :]:
            if first.box.overlaps(second.box):
                findings.append(
                    PackagingFinding(
                        code="COMPONENT_INTERSECTION",
                        detail=f"placements {first.item_id} and {second.item_id} intersect",
                        entities=(first.item_id, second.item_id),
                    )
                )

    if bays:
        for placement in placements:
            if not any(bay.box.contains(placement.box) for bay in bays):
                findings.append(
                    PackagingFinding(
                        code="OUTSIDE_PACKAGING_BAY",
                        detail=f"placement {placement.item_id} is outside every declared bay",
                        entities=(placement.item_id,),
                    )
                )

    ordered = tuple(
        sorted(findings, key=lambda finding: (finding.code, finding.entities))
    )
    failed = tuple(finding.detail for finding in ordered)
    meta = result_meta(
        model=MODEL,
        inputs=layout.canonical(),
        valid=not ordered,
        notes=failed,
        assumptions=_ASSUMPTIONS,
    )
    return PackagingReport(findings=ordered, meta=meta)
