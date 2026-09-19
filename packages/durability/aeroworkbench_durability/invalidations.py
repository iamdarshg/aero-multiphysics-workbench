"""Design-space invalidation wiring for durability-sensitive inputs.

Changes to a durability input (material revision, load spectrum, operating
temperature, crack geometry factor) are classified onto the existing design
section vocabulary and mapped through the shared coupling-DAG invalidation
table, so durability work reruns only when its inputs actually change.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, cast

from .validity import DurabilityError, finite

__all__ = [
    "DurabilityInputs",
    "durability_change_sections",
    "durability_invalidated_families",
    "durability_invalidated_for",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class DurabilityInputs:
    """Content identity of the inputs that drive a durability analysis."""

    part_id: str
    material_digest: str
    load_spectrum_digest: str
    temperature_k: float
    geometry_factor: float = 1.0

    def __post_init__(self) -> None:
        if not self.part_id.strip():
            raise DurabilityError("durability input part_id is required")
        for name in ("material_digest", "load_spectrum_digest"):
            if not _SHA256.fullmatch(getattr(self, name)):
                raise DurabilityError(f"{name} must be a sha256 digest")
        finite(self.temperature_k, "temperature_k", positive=True)
        finite(self.geometry_factor, "geometry_factor", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "partId": self.part_id,
            "materialDigest": self.material_digest,
            "loadSpectrumDigest": self.load_spectrum_digest,
            "temperatureK": self.temperature_k,
            "geometryFactor": self.geometry_factor,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def durability_change_sections(
    before: DurabilityInputs, after: DurabilityInputs
) -> tuple[str, ...]:
    """Classify a durability-input delta onto the design-section vocabulary."""

    sections: set[str] = set()
    if before.material_digest != after.material_digest:
        sections.add("materials")
    if (
        before.load_spectrum_digest != after.load_spectrum_digest
        or before.temperature_k != after.temperature_k
    ):
        sections.add("operatingPoints")
    if before.geometry_factor != after.geometry_factor:
        sections.add("geometry")
    return tuple(sorted(sections))


def durability_invalidated_families(changed_sections: tuple[str, ...]) -> tuple[str, ...]:
    """Map changed design sections to invalidated node families via the DAG."""

    from aeroworkbench_coupling.dag import invalidated_families

    return cast(tuple[str, ...], invalidated_families(changed_sections))


def durability_invalidated_for(
    before: DurabilityInputs, after: DurabilityInputs
) -> tuple[str, ...]:
    """Full change-section to invalidated-family mapping for a durability delta."""

    return durability_invalidated_families(durability_change_sections(before, after))
