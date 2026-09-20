"""Design-space invalidation seam for mass-property changes.

Mass lives in the AIRFRAME 01 ``parameters`` design section, so a changed mass
distribution maps onto the existing coupling-DAG invalidation vocabulary rather
than a parallel mechanism. Unknown sections still fail closed there.
"""

from __future__ import annotations

from ..architecture import MASS_SECTION
from ..state import MassProperties
from .aggregate import mass_properties_digest
from .contracts import MassBreakdown


def mass_properties_changed(before: MassProperties, after: MassProperties) -> bool:
    return mass_properties_digest(before) != mass_properties_digest(after)


def mass_change_sections(before: MassProperties, after: MassProperties) -> tuple[str, ...]:
    """Changed design sections for an aggregate mass-property delta."""
    return (MASS_SECTION,) if mass_properties_changed(before, after) else ()


def mass_breakdown_change_sections(
    before: MassBreakdown, after: MassBreakdown
) -> tuple[str, ...]:
    """Changed design sections for a component-breakdown delta."""
    return (MASS_SECTION,) if before.content_hash != after.content_hash else ()


def mass_invalidated_families(before: MassProperties, after: MassProperties) -> tuple[str, ...]:
    """Invalidated node families for an aggregate mass-property delta."""
    from aeroworkbench_coupling.dag import invalidated_families

    families = invalidated_families(mass_change_sections(before, after))
    return tuple(str(family) for family in families)
