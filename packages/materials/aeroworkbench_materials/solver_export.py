"""Solver-facing material export.

Exports are explicit about symmetry: orthotropic data is never collapsed to a
single modulus, and laminate export always carries the ply stack. Consumers
that cannot represent anisotropy receive a failure, not a silent substitution.
"""

from __future__ import annotations

from typing import Any

from .assignments import MaterialAssignmentSet
from .database import MaterialDatabase
from .laminate import LaminateRevision, effective_orthotropic
from .revision import MaterialRevision


def _eval(props: dict[str, Any], name: str, **kwargs: Any) -> float | None:
    prop = props.get(name)
    if prop is None:
        return None
    return float(prop.evaluate(**kwargs))


def export_mechanical(material: MaterialRevision, **kwargs: Any) -> dict[str, Any]:
    """Export mechanical/thermal/electrical scalars for solver input decks."""

    props = material.properties
    record: dict[str, Any] = {
        "identity": material.identity,
        "symmetry": material.symmetry,
        "density_kg_m3": _eval(props, "density", **kwargs),
        "youngs_modulus_pa": _eval(props, "youngs_modulus", **kwargs),
        "poisson_ratio": _eval(props, "poisson_ratio", **kwargs),
        "shear_modulus_pa": _eval(props, "shear_modulus", **kwargs),
        "yield_strength_pa": _eval(props, "yield_strength", **kwargs),
        "ultimate_strength_pa": _eval(props, "ultimate_strength", **kwargs),
        "conductivity_w_m_k": _eval(props, "conductivity", **kwargs),
        "heat_capacity_j_kg_k": _eval(props, "heat_capacity", **kwargs),
        "thermal_expansion_1_k": _eval(props, "thermal_expansion", **kwargs),
        "emissivity": _eval(props, "emissivity", **kwargs),
        "resistivity_ohm_m": _eval(props, "resistivity", **kwargs),
        "permeability_relative": _eval(props, "permeability", **kwargs),
    }
    if material.symmetry in ("orthotropic", "transversely_isotropic"):
        for key in ("youngs_modulus_transverse", "youngs_modulus_2"):
            if key in props:
                record["transverse_modulus_pa"] = _eval(props, key, **kwargs)
                break
    return record


def export_laminate(
    laminate: LaminateRevision, database: MaterialDatabase
) -> dict[str, Any]:
    """Export a laminate as an explicit ply stack plus derived membrane data."""

    _ = database  # ply materials travel by digest; registry lookup is caller's job
    homogenized = effective_orthotropic(laminate)
    return {
        "identity": laminate.identity,
        "totalThicknessM": laminate.total_thickness_m,
        "plies": [
            {
                "materialIdentity": ply.material.identity,
                "angleDeg": ply.angle_deg,
                "thicknessM": ply.thickness_m,
                "mechanical": export_mechanical(ply.material),
            }
            for ply in laminate.plies
        ],
        "homogenizedMembrane": export_mechanical(homogenized),
        "symmetry": "orthotropic-homogenized-membrane-only",
        "warning": "homogenized values are membrane-only; bending requires A/B/D",
    }


def export_assignment_set(
    assignment_set: MaterialAssignmentSet,
    database: MaterialDatabase,
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    """Export every assigned region's solver material record."""

    exported: dict[str, dict[str, Any]] = {}
    for assignment in assignment_set.assignments:
        material_id = assignment.material_identity.split("@")[0]
        exported[assignment.region_key] = export_mechanical(
            database.get_material(material_id), **kwargs
        )
    return exported


def require_isotropic_capable(
    material: MaterialRevision, solver_name: str
) -> MaterialRevision:
    """Fail closed when an isotropic-only solver meets anisotropic material."""

    if material.symmetry != "isotropic":
        raise TypeError(
            f"SOLVER_REQUIRES_ISOTROPIC:{solver_name}:{material.identity}:"
            "homogenize explicitly instead of substituting silently"
        )
    return material
