"""Region assignments bind semantic regions to material revisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RegionAssignment:
    """One semantic region's material binding."""

    region_key: str
    material_identity: str
    material_digest: str
    orientation_frame: str | None = None

    def __post_init__(self) -> None:
        if not self.region_key.strip():
            raise ValueError("REGION_KEY_REQUIRED")
        if "@" not in self.material_identity:
            raise ValueError("MATERIAL_IDENTITY_MUST_BE_ID_AT_REVISION")


@dataclass(frozen=True, slots=True)
class MaterialAssignmentSet:
    """Immutable region->material bindings with a content digest."""

    assignments: tuple[RegionAssignment, ...]

    def __post_init__(self) -> None:
        keys = [item.region_key for item in self.assignments]
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_REGION_ASSIGNMENT")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "assignments": [
                {
                    "regionKey": item.region_key,
                    "materialIdentity": item.material_identity,
                    "materialDigest": item.material_digest,
                    "orientationFrame": item.orientation_frame,
                }
                for item in sorted(self.assignments, key=lambda a: a.region_key)
            ]
        }

    def material_for(self, region_key: str) -> RegionAssignment:
        for item in self.assignments:
            if item.region_key == region_key:
                return item
        raise KeyError(f"REGION_NOT_ASSIGNED:{region_key}")


def assignment_digest(assignment_set: MaterialAssignmentSet) -> str:
    encoded = json.dumps(
        assignment_set.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
