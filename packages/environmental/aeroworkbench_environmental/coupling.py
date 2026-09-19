"""Couple environmental degradation into design state and invalidation.

Applying a :class:`DegradationState` to an existing
:class:`~aeroworkbench_core.design.PhysicalDesignState` produces a new design
variant with explicit, revisioned parameters. Any modifier that changes geometry
or material produces a new geometry/material revision hash, clears cached scalar
results, and maps the changed sections onto the existing coupling-DAG
invalidation contract so downstream cache/solver results are invalidated.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from aeroworkbench_core.design import ChangeRecord, FieldChange, PhysicalDesignState
from aeroworkbench_core.types import Provenance
from aeroworkbench_core.types import Quantity as DesignQuantity
from aeroworkbench_coupling.dag import invalidated_families

from .contracts import DEFAULT_SOFTWARE, SoftwareIdentity, Validity
from .degradation import DegradationState
from .errors import EnvironmentalError
from .provenance import analytical_provenance


def degradation_change_sections(degradation: DegradationState) -> tuple[str, ...]:
    """Design sections changed by a degradation state (sorted, existing vocabulary)."""

    return degradation.changed_sections


def degraded_invalidated_families(degradation: DegradationState) -> tuple[str, ...]:
    """Map the degradation sections onto invalidated coupling-DAG node families."""

    return cast(
        tuple[str, ...], invalidated_families(degradation_change_sections(degradation))
    )


def _revise(previous: str, digest: str, label: str) -> str:
    return hashlib.sha256(f"{label}:{previous}:{digest}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class DegradedDesign:
    """A new design variant plus the invalidation it forces."""

    design: PhysicalDesignState
    degradation_digest: str
    changed_sections: tuple[str, ...]
    invalidated_families: tuple[str, ...]
    previous_geometry_hash: str
    previous_material_hash: str
    geometry_revision_changed: bool
    material_revision_changed: bool
    parameter_changes: tuple[str, ...]
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "variantId": self.design.variant_id,
            "parentVariantId": self.design.parent_variant_id,
            "degradationDigest": self.degradation_digest,
            "changedSections": list(self.changed_sections),
            "invalidatedFamilies": list(self.invalidated_families),
            "geometryRevisionChanged": self.geometry_revision_changed,
            "materialRevisionChanged": self.material_revision_changed,
            "parameterChanges": list(self.parameter_changes),
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _degrade_parameters(
    design: PhysicalDesignState, degradation: DegradationState
) -> tuple[dict[str, DesignQuantity], dict[str, FieldChange]]:
    updated = dict(design.parameters)
    field_changes: dict[str, FieldChange] = {}
    for modifier in degradation.modifiers:
        current = updated.get(modifier.quantity_name)
        if current is None or current.dimension != modifier.delta.dimension:
            continue
        scale = DesignQuantity(value=1.0, unit=current.unit).si_value
        after = DesignQuantity(
            value=current.value + modifier.delta.value_si / scale,
            unit=current.unit,
        )
        updated[modifier.quantity_name] = after
        field_changes[modifier.quantity_name] = FieldChange(before=current, after=after)
    return updated, field_changes


def apply_degradation(
    design: PhysicalDesignState,
    degradation: DegradationState,
    *,
    variant_id: str,
    author: str,
    reason: str,
    created_at: datetime,
) -> DegradedDesign:
    """Apply degradation to a design; geometry/material change forces new revisions."""

    if not variant_id.strip():
        raise EnvironmentalError("degradation.variantId is required")
    if not author.strip() or not reason.strip():
        raise EnvironmentalError("degradation.author and reason are required")

    parameters, field_changes = _degrade_parameters(design, degradation)
    digest = degradation.digest
    geometry_hash = design.geometry_hash
    material_hash = design.material_hash
    geometry_changed = degradation.geometry_changed
    material_changed = degradation.material_changed
    if geometry_changed:
        geometry_hash = _revise(design.geometry_hash, digest, "geometry")
    if material_changed:
        material_hash = _revise(design.material_hash, digest, "material")

    new_design = PhysicalDesignState(
        design_id=design.design_id,
        variant_id=variant_id,
        parent_variant_id=design.variant_id,
        parameters=parameters,
        geometry_hash=geometry_hash,
        material_hash=material_hash,
        scalar_results={},
        change_record=ChangeRecord(
            author=author,
            reason=reason,
            created_at=created_at,
            changed_fields=field_changes,
        ),
    )
    sections = degradation_change_sections(degradation)
    families = invalidated_families(sections)
    provenance = analytical_provenance(
        "environmental.coupling.apply-degradation",
        {
            "design": design.content_hash,
            "degradation": degradation.canonical_payload(),
            "variantId": variant_id,
        },
        assumptions=("geometry/material change produces new revisions and clears caches",),
    )
    return DegradedDesign(
        design=new_design,
        degradation_digest=digest,
        changed_sections=sections,
        invalidated_families=families,
        previous_geometry_hash=design.geometry_hash,
        previous_material_hash=design.material_hash,
        geometry_revision_changed=geometry_changed,
        material_revision_changed=material_changed,
        parameter_changes=tuple(sorted(field_changes)),
        validity=Validity(
            passed=True,
            checks={
                "geometry_revision_advanced": (not geometry_changed)
                or geometry_hash != design.geometry_hash,
                "material_revision_advanced": (not material_changed)
                or material_hash != design.material_hash,
                "scalar_results_invalidated": new_design.scalar_results == {},
            },
            detail="degradation coupled into design state",
        ),
        provenance=provenance,
    )


__all__ = [
    "DegradedDesign",
    "apply_degradation",
    "degradation_change_sections",
    "degraded_invalidated_families",
]
