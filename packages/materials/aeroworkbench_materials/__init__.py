"""Real material system: revisions, laminates, database, assignments, export."""

from .assignments import (
    MaterialAssignmentSet,
    RegionAssignment,
    assignment_digest,
)
from .database import MaterialDatabase
from .laminate import (
    LaminateRevision,
    Ply,
    PlyMaterialError,
    effective_orthotropic,
    laminate_digest,
)
from .properties import (
    MaterialValue,
    constant,
    frequency_table,
    temperature_table,
)
from .revision import (
    MaterialRevision,
    material_digest,
)
from .solver_export import (
    export_assignment_set,
    export_laminate,
    export_mechanical,
    require_isotropic_capable,
)

__all__ = [
    "MaterialAssignmentSet",
    "RegionAssignment",
    "assignment_digest",
    "MaterialDatabase",
    "LaminateRevision",
    "Ply",
    "PlyMaterialError",
    "effective_orthotropic",
    "laminate_digest",
    "MaterialValue",
    "constant",
    "frequency_table",
    "temperature_table",
    "MaterialRevision",
    "material_digest",
    "export_assignment_set",
    "export_laminate",
    "export_mechanical",
    "require_isotropic_capable",
]
