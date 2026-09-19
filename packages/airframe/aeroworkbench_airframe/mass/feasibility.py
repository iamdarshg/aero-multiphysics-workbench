"""Combined mass feasibility verdict for campaign consumption.

Closure failures are classified ``preflight-invalid`` because the aggregate
itself is inconsistent; packaging or CG/static-margin violations are classified
``infeasible``. Either way the verdict is explicit and never silently repaired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .closure import MassClosureReport, close_mass_breakdown
from .constraints import CenterOfGravityRange, StaticMarginConstraint
from .contracts import MassBreakdown, MassResultMeta, result_meta
from .packaging import PackagingLayout, PackagingReport, evaluate_packaging

MODEL = "airframe-mass-feasibility"

FEASIBLE = "feasible"
INFEASIBLE = "infeasible"
PREFLIGHT_INVALID = "preflight-invalid"

_ASSUMPTIONS = (
    "Closure inconsistency is preflight-invalid; packaging/CG violations are infeasible.",
    "The verdict never repairs a violation or invents a passing mass.",
)


@dataclass(frozen=True, slots=True)
class MassFeasibilityReport:
    status: str
    closure: MassClosureReport
    packaging: PackagingReport | None
    meta: MassResultMeta

    @property
    def feasible(self) -> bool:
        return self.status == FEASIBLE

    @property
    def reasons(self) -> tuple[str, ...]:
        reasons = list(self.closure.reasons)
        if self.packaging is not None:
            reasons.extend(self.packaging.reasons)
        return tuple(reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "closure": self.closure.as_dict(),
            "packaging": None if self.packaging is None else self.packaging.as_dict(),
            "reasons": list(self.reasons),
            "meta": self.meta.as_dict(),
        }


def evaluate_mass_feasibility(
    breakdown: MassBreakdown,
    *,
    cg_ranges: tuple[CenterOfGravityRange, ...] = (),
    static_margins: tuple[StaticMarginConstraint, ...] = (),
    layout: PackagingLayout | None = None,
    tolerance: float = 1e-9,
) -> MassFeasibilityReport:
    """Classify a mass breakdown as feasible, infeasible, or preflight-invalid."""
    closure = close_mass_breakdown(
        breakdown,
        cg_ranges=cg_ranges,
        static_margins=static_margins,
        tolerance=tolerance,
    )
    packaging = None if layout is None else evaluate_packaging(layout)
    if not closure.closure_passed:
        status = PREFLIGHT_INVALID
    elif not closure.feasible or (packaging is not None and not packaging.feasible):
        status = INFEASIBLE
    else:
        status = FEASIBLE
    reasons: list[str] = list(closure.reasons)
    if packaging is not None:
        reasons.extend(packaging.reasons)
    inputs = {
        "breakdown": breakdown.canonical(),
        "cgRanges": [constraint.as_dict() for constraint in cg_ranges],
        "staticMargins": [constraint.as_dict() for constraint in static_margins],
        "packaging": None if layout is None else layout.canonical(),
    }
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=status == FEASIBLE,
        notes=tuple(reasons),
        assumptions=_ASSUMPTIONS,
    )
    return MassFeasibilityReport(
        status=status, closure=closure, packaging=packaging, meta=meta
    )
