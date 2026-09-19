"""Mass-property closure report with provenance.

The closure report never raises for an infeasible design: it records every
closure check and every CG/static-margin finding so a campaign can classify the
result as infeasible. Structural/physical inconsistencies still fail closed in
:func:`aggregate.aggregate_mass_properties`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..canonical import content_digest
from ..state import InertiaTensor, MassProperties
from ..units import Quantity, Vec3
from .aggregate import (
    MassClosureCheck,
    compute_mass_properties,
    mass_closure_checks,
)
from .constraints import (
    CenterOfGravityRange,
    CogConstraintFinding,
    StaticMarginConstraint,
    evaluate_cog_constraints,
)
from .contracts import MassBreakdown, MassResultMeta, result_meta

MODEL = "airframe-mass-closure"

_ASSUMPTIONS = (
    "Closure compares the aggregate against the component sum and inertia rank.",
    "CG ranges are reported as findings; an infeasible layout is never hidden.",
    "No mass value is invented to make a closure check pass.",
)

_DEFAULT_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class MassClosureReport:
    mass_properties: MassProperties
    checks: tuple[MassClosureCheck, ...]
    cg_findings: tuple[CogConstraintFinding, ...]
    meta: MassResultMeta

    @property
    def total_mass(self) -> Quantity:
        return self.mass_properties.mass

    @property
    def cg(self) -> Vec3:
        return self.mass_properties.cg

    @property
    def inertia(self) -> InertiaTensor:
        return self.mass_properties.inertia

    @property
    def closure_passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def feasible(self) -> bool:
        return self.closure_passed and all(finding.passed for finding in self.cg_findings)

    @property
    def reasons(self) -> tuple[str, ...]:
        closure = tuple(check.detail for check in self.checks if not check.passed)
        cg = tuple(finding.detail for finding in self.cg_findings if not finding.passed)
        return closure + cg

    def as_dict(self) -> dict[str, Any]:
        return {
            "massProperties": self.mass_properties.canonical(),
            "checks": [check.as_dict() for check in self.checks],
            "cgFindings": [finding.as_dict() for finding in self.cg_findings],
            "meta": self.meta.as_dict(),
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.as_dict())


def close_mass_breakdown(
    breakdown: MassBreakdown,
    *,
    cg_ranges: tuple[CenterOfGravityRange, ...] = (),
    static_margins: tuple[StaticMarginConstraint, ...] = (),
    tolerance: float = _DEFAULT_TOLERANCE,
) -> MassClosureReport:
    """Aggregate a breakdown and report closure, CG ranges, and static margins."""
    mass_properties = compute_mass_properties(breakdown)
    checks = mass_closure_checks(breakdown, mass_properties, tolerance=tolerance)
    cog_report = evaluate_cog_constraints(
        mass_properties, ranges=cg_ranges, static_margins=static_margins
    )
    failed = tuple(check.detail for check in checks if not check.passed) + cog_report.reasons
    inputs = {
        "breakdown": breakdown.canonical(),
        "cgRanges": [constraint.as_dict() for constraint in cg_ranges],
        "staticMargins": [constraint.as_dict() for constraint in static_margins],
    }
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=not failed,
        notes=failed,
        assumptions=_ASSUMPTIONS,
    )
    return MassClosureReport(
        mass_properties=mass_properties,
        checks=checks,
        cg_findings=cog_report.findings,
        meta=meta,
    )
