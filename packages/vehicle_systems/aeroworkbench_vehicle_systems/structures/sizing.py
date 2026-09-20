"""Bounded automatic sizing of generated structure against declared load cases.

Sizing is a deterministic bounded bisection: each member's wall thickness (or, for
a laminated member, its total laminate thickness with every ply scaled by a common
factor) is driven to the smallest value within declared bounds that satisfies the
strength, buckling, and deflection margins for its factored demand. A member that
cannot meet its constraints within bounds raises
:class:`StructuralConstraintError`, so an aerodynamically attractive but
structurally infeasible candidate is rejected rather than silently accepted. Mass
and equivalent stiffness are reported so the mass breakdown and the aeroelastic
loop can close.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .architecture import ArchitectureKind, StructuralArchitecture
from .checks import (
    DEFAULT_DEFLECTION_LIMIT_FRACTION,
    MarginResult,
    MemberDemand,
    evaluate_member_margins,
    member_is_feasible,
)
from .contracts import ResultEnvelope, Validity, analytical_envelope, content_digest
from .errors import SizingError, StructuralConstraintError, StructuresError
from .loads import LoadEnvelope, StructuralLoadSet
from .members import StructuralMember
from .stiffness import StiffnessSeam, build_stiffness_seam

if TYPE_CHECKING:
    from .manufacturing import StructuralManufacturingLimits

__all__ = [
    "SizedMember",
    "SizedStructure",
    "SizingOptions",
    "size_architecture",
]

_DEFAULT_MINIMUM_THICKNESS_M = 5.0e-4
_DEFAULT_MAXIMUM_THICKNESS_M = 0.1


@dataclass(frozen=True, slots=True)
class SizingOptions:
    """Bounded sizing controls; all values are declared, none are implicit.

    The default minimum gauge (0.5 mm) reflects metallic airframe minimum gauge;
    laminated members additionally respect their ply-stack minimum.
    """

    minimum_thickness_m: float = _DEFAULT_MINIMUM_THICKNESS_M
    maximum_thickness_m: float = _DEFAULT_MAXIMUM_THICKNESS_M
    deflection_limit_fraction: float = DEFAULT_DEFLECTION_LIMIT_FRACTION
    safety_factor: float = 1.5
    max_iterations: int = 60
    relative_tolerance: float = 1.0e-6
    manufacturing_limits: StructuralManufacturingLimits | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.minimum_thickness_m < self.maximum_thickness_m:
            raise SizingError("SIZING_THICKNESS_BOUNDS_INVALID")
        if (
            not math.isfinite(self.deflection_limit_fraction)
            or self.deflection_limit_fraction <= 0.0
        ):
            raise SizingError("SIZING_DEFLECTION_LIMIT_INVALID")
        if not math.isfinite(self.safety_factor) or self.safety_factor < 1.0:
            raise SizingError("SIZING_SAFETY_FACTOR_INVALID")
        if self.max_iterations <= 0:
            raise SizingError("SIZING_ITERATIONS_MUST_BE_POSITIVE")
        if not 0.0 < self.relative_tolerance < 1.0:
            raise SizingError("SIZING_TOLERANCE_INVALID")

    def as_dict(self) -> dict[str, Any]:
        return {
            "minimumThicknessM": self.minimum_thickness_m,
            "maximumThicknessM": self.maximum_thickness_m,
            "deflectionLimitFraction": self.deflection_limit_fraction,
            "safetyFactor": self.safety_factor,
            "maxIterations": float(self.max_iterations),
            "relativeTolerance": self.relative_tolerance,
            "manufacturingLimits": (
                None if self.manufacturing_limits is None else self.manufacturing_limits.as_dict()
            ),
        }


def _demand_for(
    member: StructuralMember, envelope: LoadEnvelope, safety_factor: float
) -> MemberDemand:
    share = member.load_share
    return MemberDemand(
        bending_moment_n_m=envelope.root_bending_n_m * share * safety_factor,
        shear_n=envelope.total_shear_n * share * safety_factor,
        axial_n=envelope.total_axial_n * share * safety_factor,
        length_m=member.length_m,
    )


def _thickness_bounds(
    member: StructuralMember, options: SizingOptions
) -> tuple[float, float]:
    lower = max(options.minimum_thickness_m, member.material.minimum_thickness_m)
    upper = min(
        options.maximum_thickness_m, member.section.max_thickness_m() * 0.999
    )
    return lower, upper


def _feasible(
    member: StructuralMember, demand: MemberDemand, thickness: float
) -> bool:
    candidate = member.with_design(
        member.section.with_thickness(thickness),
        member.material.with_thickness(thickness),
    )
    return member_is_feasible(candidate, demand)


def _violations(
    member: StructuralMember, demand: MemberDemand, thickness: float
) -> tuple[str, ...]:
    candidate = member.with_design(
        member.section.with_thickness(thickness),
        member.material.with_thickness(thickness),
    )
    return tuple(
        f"{member.member_id}:{result.name}"
        for result in evaluate_member_margins(candidate, demand)
        if not result.passed
    )


def _size_member(
    member: StructuralMember, demand: MemberDemand, options: SizingOptions
) -> StructuralMember:
    lower, upper = _thickness_bounds(member, options)
    if upper <= lower:
        raise StructuralConstraintError(
            f"MEMBER_THICKNESS_BOUNDS_EMPTY:{member.member_id}",
            violations=(f"{member.member_id}:bounds",),
        )
    if _feasible(member, demand, lower):
        chosen = lower
    elif not _feasible(member, demand, upper):
        violations = _violations(member, demand, upper)
        raise StructuralConstraintError(
            f"MEMBER_INFEASIBLE_WITHIN_BOUNDS:{member.member_id}",
            violations=violations,
        )
    else:
        low, high = lower, upper
        for _ in range(options.max_iterations):
            if high - low <= options.relative_tolerance * high:
                break
            middle = 0.5 * (low + high)
            if _feasible(member, demand, middle):
                high = middle
            else:
                low = middle
        chosen = high
    return member.with_design(
        member.section.with_thickness(chosen),
        member.material.with_thickness(chosen),
    )


@dataclass(frozen=True, slots=True)
class SizedMember:
    """One member after bounded sizing, with its demand and margins."""

    member: StructuralMember
    demand: MemberDemand
    margins: tuple[MarginResult, ...]
    mass_kg: float

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.margins)

    def as_dict(self) -> dict[str, Any]:
        return {
            "member": self.member.canonical_payload(),
            "demand": self.demand.as_dict(),
            "margins": [result.as_dict() for result in self.margins],
            "massKg": self.mass_kg,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class SizedStructure:
    """A fully sized structure with mass, stiffness, validity, and provenance."""

    architecture_id: str
    component_id: str
    kind: ArchitectureKind
    frame: str
    members: tuple[SizedMember, ...]
    load_case_ids: tuple[str, ...]
    total_mass_kg: float
    stiffness: StiffnessSeam
    validity: Validity
    meta: ResultEnvelope
    digest: str

    def member(self, member_id: str) -> SizedMember:
        for candidate in self.members:
            if candidate.member.member_id == member_id:
                return candidate
        raise StructuresError(f"UNKNOWN_SIZED_MEMBER:{member_id}")

    def structural_members(self) -> tuple[StructuralMember, ...]:
        return tuple(candidate.member for candidate in self.members)

    def as_dict(self) -> dict[str, Any]:
        return {
            "architectureId": self.architecture_id,
            "componentId": self.component_id,
            "kind": self.kind.value,
            "frame": self.frame,
            "loadCaseIds": list(self.load_case_ids),
            "totalMassKg": self.total_mass_kg,
            "stiffness": self.stiffness.as_dict(),
            "members": [candidate.as_dict() for candidate in self.members],
            "validity": self.validity.canonical(),
            "digest": self.digest,
            "meta": self.meta.as_dict(),
        }


def size_architecture(
    architecture: StructuralArchitecture,
    load_set: StructuralLoadSet,
    *,
    options: SizingOptions | None = None,
) -> SizedStructure:
    """Size every member in a generated architecture against a load set."""

    controls = options or SizingOptions()
    column = load_set.envelope(architecture.reference_span_m)
    sized: list[SizedMember] = []
    for member in architecture.sorted_members():
        demand = _demand_for(member, column, controls.safety_factor)
        built = _size_member(member, demand, controls)
        margins = evaluate_member_margins(built, demand)
        sized.append(
            SizedMember(
                member=built,
                demand=demand,
                margins=margins,
                mass_kg=built.mass_kg(),
            )
        )
    total_mass = sum(candidate.mass_kg for candidate in sized)
    if total_mass <= 0.0:
        raise SizingError("SIZED_STRUCTURE_HAS_NONPOSITIVE_MASS")
    stiffness = build_stiffness_seam(
        tuple(candidate.member for candidate in sized),
        architecture_id=architecture.architecture_id,
        component_id=architecture.component_id,
        frame=architecture.frame,
        span_m=architecture.reference_span_m,
        reference_area_m2=architecture.reference_area_m2,
        root_bending_n_m=column.root_bending_n_m,
    )
    deflection_limit_m = controls.deflection_limit_fraction * architecture.reference_span_m
    if stiffness.tip_deflection_m > deflection_limit_m:
        raise StructuralConstraintError(
            "GLOBAL_DEFLECTION_LIMIT_EXCEEDED",
            violations=(
                f"tip_deflection_m={stiffness.tip_deflection_m}",
                f"limit_m={deflection_limit_m}",
            ),
        )
    checks = {
        "all_members_sized": all(candidate.passed for candidate in sized),
        "mass_positive": total_mass > 0.0,
        "bending_stiffness_positive": stiffness.bending_stiffness_n_m2 > 0.0,
        "deflection_within_limit": stiffness.tip_deflection_m
        <= controls.deflection_limit_fraction * architecture.reference_span_m,
    }
    validity = Validity(passed=all(checks.values()), checks=checks, detail="bounded sizing")
    meta = analytical_envelope(
        model="generative-airframe-structural-sizing",
        inputs={
            "architecture": architecture.canonical_payload(),
            "loadSet": load_set.canonical_payload(),
            "options": controls.as_dict(),
        },
        validity=validity,
        assumptions=(
            "preliminary beam/shell sizing against a folded load envelope",
            "members sized independently by bounded bisection within declared bounds",
            "no native FEA was executed; native structure remains capability-gated",
        ),
    )
    digest = content_digest(
        {
            "architecture": architecture.digest,
            "loadSet": load_set.digest,
            "options": controls.as_dict(),
            "totalMassKg": total_mass,
            "members": [candidate.as_dict() for candidate in sized],
        }
    )
    result = SizedStructure(
        architecture_id=architecture.architecture_id,
        component_id=architecture.component_id,
        kind=architecture.kind,
        frame=architecture.frame,
        members=tuple(sized),
        load_case_ids=column.case_ids,
        total_mass_kg=total_mass,
        stiffness=stiffness,
        validity=validity,
        meta=meta,
        digest=digest,
    )
    if controls.manufacturing_limits is not None:
        from .manufacturing import screen_structure_manufacturability

        screen_structure_manufacturability(result, controls.manufacturing_limits)
    return result
