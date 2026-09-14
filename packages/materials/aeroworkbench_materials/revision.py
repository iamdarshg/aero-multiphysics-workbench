"""Immutable, content-addressed material revisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from .properties import MaterialValue

Symmetry = Literal["isotropic", "transversely_isotropic", "orthotropic", "laminate"]

MECHANICAL_PROPERTIES = (
    "density",
    "youngs_modulus",
    "youngs_modulus_2",
    "youngs_modulus_transverse",
    "poisson_ratio",
    "shear_modulus",
    "yield_strength",
    "ultimate_strength",
    "fatigue",
)

THERMAL_PROPERTIES = (
    "conductivity",
    "heat_capacity",
    "thermal_expansion",
    "emissivity",
)

ELECTRICAL_PROPERTIES = (
    "resistivity",
    "conductivity",
    "temperature_coefficient",
)

MAGNETIC_PROPERTIES = (
    "permeability",
    "remanence",
    "coercivity",
    "bh_curve",
    "core_loss",
)

KNOWN_PROPERTIES = frozenset(
    MECHANICAL_PROPERTIES + THERMAL_PROPERTIES + ELECTRICAL_PROPERTIES + MAGNETIC_PROPERTIES
)


@dataclass(frozen=True, slots=True)
class MaterialRevision:
    """One immutable revision of a material definition."""

    material_id: str
    revision: str
    symmetry: Symmetry
    properties: dict[str, MaterialValue]
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.material_id.strip() or not self.revision.strip():
            raise ValueError("MATERIAL_IDENTITY_REQUIRED")
        unknown = sorted(set(self.properties) - KNOWN_PROPERTIES)
        if unknown:
            raise ValueError(f"UNKNOWN_MATERIAL_PROPERTIES:{','.join(unknown)}")
        if self.symmetry == "isotropic" and not {"density"} <= set(self.properties):
            raise ValueError("ISOTROPIC_REQUIRES_DENSITY")

    @property
    def identity(self) -> str:
        return f"{self.material_id}@{self.revision}"

    def evaluate(
        self,
        name: str,
        *,
        temperature_k: float | None = None,
        frequency_hz: float | None = None,
        axis: float | None = None,
    ) -> float:
        """Evaluate a named property; unknown names and out-of-range use fail."""

        try:
            prop = self.properties[name]
        except KeyError as exc:
            raise KeyError(f"PROPERTY_NOT_DEFINED:{name}") from exc
        return prop.evaluate(
            temperature_k=temperature_k, frequency_hz=frequency_hz, axis=axis
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "materialId": self.material_id,
            "revision": self.revision,
            "symmetry": self.symmetry,
            "provenance": self.provenance,
            "properties": {
                name: self.properties[name].canonical_payload()
                for name in sorted(self.properties)
            },
        }


def material_digest(material: MaterialRevision) -> str:
    """Content identity of a material revision."""

    encoded = json.dumps(
        material.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
