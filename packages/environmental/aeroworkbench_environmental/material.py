"""Property degradation of an existing material revision.

A :class:`~aeroworkbench_materials.revision.MaterialRevision` is degraded by
scaling its constant stiffness/strength/thermal properties with the explicit
fractional modifiers from a :class:`DegradationState`. The result is a *new*
content-addressed material revision; downstream analyses keyed on the previous
material digest are invalidated. Temperature- or frequency-dependent properties
cannot be scaled without native data, so they are skipped and the result is
marked not-passed (fail closed) rather than silently approximated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_materials.properties import MaterialValue, constant
from aeroworkbench_materials.revision import MaterialRevision, material_digest

from .contracts import (
    DEFAULT_SOFTWARE,
    EnvironmentalFidelity,
    SoftwareIdentity,
    Validity,
)
from .degradation import DegradationState
from .errors import EnvironmentalError
from .provenance import analytical_provenance

_STIFFNESS_PROPERTIES = (
    "youngs_modulus",
    "youngs_modulus_2",
    "youngs_modulus_transverse",
    "shear_modulus",
)
_STRENGTH_PROPERTIES = ("yield_strength", "ultimate_strength", "fatigue")
_EMISSIVITY_PROPERTIES = ("emissivity",)
_HEAT_TRANSFER_PROPERTIES = ("conductivity",)


@dataclass(frozen=True, slots=True)
class DegradedMaterial:
    """A new material revision produced by explicit environmental degradation."""

    material: MaterialRevision
    previous_digest: str
    digest: str
    changed_properties: tuple[str, ...]
    fidelity: EnvironmentalFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "material": self.material.canonical_payload(),
            "previousDigest": self.previous_digest,
            "digest": self.digest,
            "changedProperties": list(self.changed_properties),
            "fidelity": self.fidelity.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
        }


def _fraction(modifiers: dict[str, float], name: str) -> float | None:
    return modifiers.get(name)


def _scale(
    value: MaterialValue, factor: float, property_name: str, checks: dict[str, bool]
) -> MaterialValue | None:
    if value.kind != "constant" or value.constant is None:
        checks[f"scalable:{property_name}"] = False
        return None
    if factor < 0.0:
        raise EnvironmentalError(f"material.degradationFactorNegative:{property_name}")
    return constant(value.constant * factor, value.unit, value.source)


def degrade_material_revision(
    material: MaterialRevision,
    degradation: DegradationState,
    *,
    revision: str,
) -> DegradedMaterial:
    """Apply a degradation state to a material and return a new revision."""

    if not revision.strip():
        raise EnvironmentalError("material.revision is required")
    modifiers: dict[str, float] = {
        modifier.quantity_name: modifier.delta.value_si
        for modifier in degradation.modifiers
    }
    stiffness = _fraction(modifiers, "stiffness_fraction_reduction")
    strength = _fraction(modifiers, "strength_fraction_reduction")
    emissivity = _fraction(modifiers, "emissivity_change")
    heat_transfer = _fraction(modifiers, "heat_transfer_fraction_change")

    properties = dict(material.properties)
    changed: list[str] = []
    checks: dict[str, bool] = {"degradation_nonempty": bool(modifiers)}

    def apply_group(names: tuple[str, ...], factor: float, label: str) -> None:
        for name in names:
            if name not in properties:
                continue
            scaled = _scale(properties[name], factor, name, checks)
            checks[f"{label}:{name}"] = scaled is not None
            if scaled is not None:
                properties[name] = scaled
                changed.append(name)

    if stiffness is not None:
        apply_group(_STIFFNESS_PROPERTIES, 1.0 - stiffness, "stiffness")
    if strength is not None:
        apply_group(_STRENGTH_PROPERTIES, 1.0 - strength, "strength")
    if emissivity is not None:
        apply_group(_EMISSIVITY_PROPERTIES, 1.0 + emissivity, "emissivity")
    if heat_transfer is not None:
        apply_group(_HEAT_TRANSFER_PROPERTIES, 1.0 + heat_transfer, "heat_transfer")

    if not changed:
        raise EnvironmentalError("material.noDegradableProperty")

    degraded = MaterialRevision(
        material_id=material.material_id,
        revision=revision,
        symmetry=material.symmetry,
        properties=properties,
        provenance=f"degraded:{degradation.digest}",
    )
    provenance = analytical_provenance(
        "environmental.material.degradation",
        {
            "material": material.canonical_payload(),
            "degradation": degradation.canonical_payload(),
            "revision": revision,
        },
        assumptions=("constant properties scaled by explicit degradation fractions",),
    )
    passed = all(checks.values())
    return DegradedMaterial(
        material=degraded,
        previous_digest=material_digest(material),
        digest=material_digest(degraded),
        changed_properties=tuple(sorted(changed)),
        fidelity=EnvironmentalFidelity.EMPIRICAL,
        validity=Validity(
            passed=passed,
            checks=checks,
            detail="property degradation applied",
        ),
        provenance=provenance,
    )


__all__ = [
    "DegradedMaterial",
    "degrade_material_revision",
]
