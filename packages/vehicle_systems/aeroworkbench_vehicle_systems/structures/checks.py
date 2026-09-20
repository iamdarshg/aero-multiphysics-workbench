"""Strength, local-buckling, and deflection checks with reserve-factor margins.

Every check returns a deterministic :class:`MarginResult` whose margin is
``capacity / demand`` (a reserve factor), so a margin at or above one passes and
a margin below one rejects the candidate. Isotropic members use explicit material
allowables; laminated members route strength through the composites first-ply
failure contract, preserving ply/laminate semantics. Surface members (skins and
shells) contribute bending stiffness through a parallel-axis separation term, so
the equivalent box bending stiffness is physical. No check ever invents an
allowable: a member whose material lacks one fails closed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .errors import StructuralContractError
from .materials import MemberMaterial
from .members import MemberKind, MemberOrientation, StructuralMember

__all__ = [
    "BEAM_KINDS",
    "DEFAULT_DEFLECTION_LIMIT_FRACTION",
    "MemberDemand",
    "MarginResult",
    "axial_stress_pa",
    "bending_stress_pa",
    "cantilever_tip_deflection_m",
    "effective_extreme_fibre_m",
    "effective_second_moment_m4",
    "euler_buckling_stress_pa",
    "evaluate_member_margins",
    "margin_of_safety",
    "material_has_allowable",
    "member_is_feasible",
    "plate_buckling_stress_pa",
]

DEFAULT_DEFLECTION_LIMIT_FRACTION = 0.05
_MARGIN_CAP = 1.0e12

BEAM_KINDS: frozenset[MemberKind] = frozenset(
    {
        MemberKind.SPAR_CAP,
        MemberKind.STRINGER,
        MemberKind.FRAME,
        MemberKind.BULKHEAD,
    }
)


@dataclass(frozen=True, slots=True)
class MemberDemand:
    """The factored internal loads one member must carry."""

    bending_moment_n_m: float
    shear_n: float
    axial_n: float
    length_m: float

    def as_dict(self) -> dict[str, float]:
        return {
            "bendingMomentNm": self.bending_moment_n_m,
            "shearN": self.shear_n,
            "axialN": self.axial_n,
            "lengthM": self.length_m,
        }


@dataclass(frozen=True, slots=True)
class MarginResult:
    """One deterministic constraint check with a reserve-factor margin."""

    name: str
    demand: float
    capacity: float
    margin: float
    passed: bool
    unit: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "demand": self.demand,
            "capacity": self.capacity,
            "margin": self.margin,
            "passed": self.passed,
            "unit": self.unit,
            "detail": self.detail,
        }


def margin_of_safety(capacity: float, demand: float) -> float:
    """Reserve factor ``capacity / demand`` with a finite cap for zero demand."""

    if not math.isfinite(capacity) or not math.isfinite(demand):
        raise StructuralContractError("MARGIN_INPUTS_MUST_BE_FINITE")
    if demand <= 0.0:
        return _MARGIN_CAP
    return capacity / demand


def effective_second_moment_m4(member: StructuralMember) -> float:
    """Strong-axis second moment, adding a box separation term for skins/shells."""

    properties = member.section.properties()
    if member.orientation is MemberOrientation.SURFACE:
        offset = abs(member.centroid.value_si[1])
        return properties.i_strong_m4 + properties.area_m2 * offset * offset
    return properties.i_strong_m4


def effective_extreme_fibre_m(member: StructuralMember) -> float:
    """Distance from the neutral axis to the extreme fibre of the equivalent beam."""

    return max(member.section.extreme_fibre_m, abs(member.centroid.value_si[1]))


def bending_stress_pa(member: StructuralMember, demand: MemberDemand) -> float:
    inertia = effective_second_moment_m4(member)
    if inertia <= 0.0:
        raise StructuralContractError(f"MEMBER_HAS_NO_BENDING_STIFFNESS:{member.member_id}")
    return demand.bending_moment_n_m * effective_extreme_fibre_m(member) / inertia


def axial_stress_pa(member: StructuralMember, demand: MemberDemand) -> float:
    properties = member.section.properties()
    if properties.area_m2 <= 0.0:
        raise StructuralContractError(f"MEMBER_HAS_NO_AREA:{member.member_id}")
    return demand.axial_n / properties.area_m2


def euler_buckling_stress_pa(member: StructuralMember) -> float:
    """Global Euler column stress for the member's unbraced length."""

    properties = member.section.properties()
    if properties.area_m2 <= 0.0 or member.length_m <= 0.0:
        raise StructuralContractError(f"MEMBER_CANNOT_BUCKLE:{member.member_id}")
    critical_load = (
        math.pi**2
        * member.material.youngs_modulus_pa()
        * properties.i_weak_m4
        / member.length_m**2
    )
    return critical_load / properties.area_m2


def plate_buckling_stress_pa(member: StructuralMember) -> float:
    """Local plate buckling stress across the member's effective plate width."""

    width = member.effective_buckling_width_m
    if width <= 0.0:
        raise StructuralContractError(f"MEMBER_HAS_NO_PLATE_WIDTH:{member.member_id}")
    nu = member.material.poisson_ratio()
    factor = 4.0 * math.pi**2 * member.material.youngs_modulus_pa() / (12.0 * (1.0 - nu**2))
    return factor * (member.section.thickness_m / width) ** 2


def cantilever_tip_deflection_m(member: StructuralMember, demand: MemberDemand) -> float:
    stiffness = member.material.youngs_modulus_pa() * effective_second_moment_m4(member)
    if stiffness <= 0.0:
        raise StructuralContractError(f"MEMBER_HAS_NO_DEFLECTION_STIFFNESS:{member.member_id}")
    return abs(demand.bending_moment_n_m) * member.length_m**2 / (2.0 * stiffness)


def _isotropic_strength(member: StructuralMember, demand: MemberDemand) -> MarginResult:
    stress = abs(bending_stress_pa(member, demand) + axial_stress_pa(member, demand))
    allowable = member.material.allowable_pa()
    margin = margin_of_safety(allowable, stress)
    return MarginResult(
        name="strength",
        demand=stress,
        capacity=allowable,
        margin=margin,
        passed=margin >= 1.0,
        unit="Pa",
        detail=f"allowable={allowable}",
    )


def _laminate_strength(member: StructuralMember, demand: MemberDemand) -> MarginResult:
    stress = abs(bending_stress_pa(member, demand) + axial_stress_pa(member, demand))
    membrane_load = stress * member.section.thickness_m
    index = member.material.composite_failure_index(membrane_load_n_m=membrane_load)
    margin = margin_of_safety(1.0, index)
    return MarginResult(
        name="laminate-first-ply",
        demand=index,
        capacity=1.0,
        margin=margin,
        passed=index <= 1.0,
        unit="1",
        detail="first-ply failure index (composites #72)",
    )


def evaluate_member_margins(
    member: StructuralMember, demand: MemberDemand
) -> tuple[MarginResult, ...]:
    """Evaluate strength and local buckling for one member."""

    strength = (
        _laminate_strength(member, demand)
        if member.material.laminate is not None
        else _isotropic_strength(member, demand)
    )
    buckling_capacity = plate_buckling_stress_pa(member)
    compressive = max(
        axial_stress_pa(member, demand) + bending_stress_pa(member, demand), 0.0
    )
    buckling_margin = margin_of_safety(buckling_capacity, compressive)
    return (
        strength,
        MarginResult(
            name="local-buckling",
            demand=compressive,
            capacity=buckling_capacity,
            margin=buckling_margin,
            passed=buckling_margin >= 1.0,
            unit="Pa",
            detail=f"critical={buckling_capacity}",
        ),
    )


def member_is_feasible(member: StructuralMember, demand: MemberDemand) -> bool:
    """True when every margin for the member is at or above one."""

    return all(result.passed for result in evaluate_member_margins(member, demand))


def material_has_allowable(material: MemberMaterial) -> bool:
    """Whether the material exposes an explicit strength allowable."""

    if material.laminate is not None:
        return material.strengths is not None
    return any(
        key in material.material.properties
        for key in ("yield_strength", "ultimate_strength")
    )
