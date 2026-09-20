"""Finite-wing nonlinear aggregation: section polar to wing CL/CD/Cm."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

from aeroworkbench_core.types import ResultSource

from .contracts import HighLiftFidelity, ResultMeta, result_meta
from .devices import ConfigurationDelta
from .errors import HighLiftError, ValidityError, finite
from .section import SectionStallParameters, evaluate_section

MODEL_WING = "vehicle-systems.highlift.finite-wing-nonlinear"

_ASSUMPTIONS = (
    "Finite-wing lift from section lift scaled by the lifting-line slope correction.",
    "Wing drag is section profile drag plus the induced term CL^2/(pi ARe).",
    "One representative section stands for the wing; spanwise stall spread is not resolved.",
)


@dataclass(frozen=True, slots=True)
class WingPlanform:
    aspect_ratio: float
    oswald_efficiency: float
    area_m2: float = 1.0

    def __post_init__(self) -> None:
        finite(self.aspect_ratio, "aspect_ratio", positive=True)
        finite(self.oswald_efficiency, "oswald_efficiency", positive=True)
        if self.oswald_efficiency > 1.0:
            raise HighLiftError("oswald_efficiency must be <= 1")
        finite(self.area_m2, "area_m2", positive=True)

    def lift_correction(self, section_slope_per_rad: float) -> float:
        finite(section_slope_per_rad, "section_slope_per_rad", positive=True)
        return 1.0 / (
            1.0
            + section_slope_per_rad / (pi * self.aspect_ratio * self.oswald_efficiency)
        )

    def canonical(self) -> dict[str, float]:
        return {
            "aspectRatio": self.aspect_ratio,
            "oswaldEfficiency": self.oswald_efficiency,
            "areaM2": self.area_m2,
        }


@dataclass(frozen=True, slots=True)
class FiniteWingResult:
    alpha_deg: float
    lift: float
    drag: float
    moment: float
    regime: str
    separated: bool
    cl_max_wing: float
    alpha_stall_wing_deg: float
    lift_correction: float
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "alphaDeg": self.alpha_deg,
            "CL": self.lift,
            "CD": self.drag,
            "Cm": self.moment,
            "regime": self.regime,
            "separated": self.separated,
            "clMaxWing": self.cl_max_wing,
            "alphaStallWingDeg": self.alpha_stall_wing_deg,
            "liftCorrection": self.lift_correction,
            "meta": self.meta.canonical(),
        }


def evaluate_finite_wing(
    alpha_deg: float,
    params: SectionStallParameters,
    planform: WingPlanform,
    delta: ConfigurationDelta | None = None,
) -> FiniteWingResult:
    finite(alpha_deg, "alpha_deg")
    section = evaluate_section(alpha_deg, params, delta)
    correction = planform.lift_correction(params.lift_slope_per_rad)
    clmax_wing = section.cl_max_effective * correction
    lift = section.lift * correction
    stall_eff = section.alpha_stall_effective_deg
    separation_rise = (
        params.post_stall_drag_rise_per_deg * (alpha_deg - stall_eff)
        if alpha_deg > stall_eff
        else 0.0
    )
    drag = (
        params.cd0
        + (delta.dcd if delta is not None else 0.0)
        + separation_rise
        + lift * lift / (pi * planform.aspect_ratio * planform.oswald_efficiency)
    )
    moment = section.moment
    checks = {
        "alpha_in_envelope": True,
        "below_stall": section.alpha_deg < section.alpha_stall_effective_deg,
        "below_deep_stall": section.regime != "deepstall",
        "cl_below_clmax": lift <= clmax_wing + 1e-12,
    }
    meta = result_meta(
        model=MODEL_WING,
        inputs={
            "section": params.canonical(),
            "planform": planform.canonical(),
            "alphaDeg": alpha_deg,
            "delta": (delta or ConfigurationDelta(
                dcl0=0.0, dclmax=0.0, dcd=0.0,
                dcm=0.0, dstall_deg=0.0, area_gain=0.0,
            )).canonical(),
            "sectionResult": {
                "cl": section.lift,
                "cd": section.drag,
                "regime": section.regime,
            },
        },
        valid=section.regime in ("attached", "prestall"),
        fidelity=HighLiftFidelity.FINITE_WING_NONLINEAR,
        checks=checks,
        detail=f"finite wing at {alpha_deg} deg is {section.regime}",
        assumptions=_ASSUMPTIONS,
        source=ResultSource.ANALYTICAL,
    )
    return FiniteWingResult(
        alpha_deg=alpha_deg,
        lift=lift,
        drag=drag,
        moment=moment,
        regime=section.regime,
        separated=section.separated,
        cl_max_wing=clmax_wing,
        alpha_stall_wing_deg=section.alpha_stall_effective_deg,
        lift_correction=correction,
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class StallConstraintVerdict:
    passed: bool
    required_cl: float
    cl_max_wing: float
    margin: float
    reasons: tuple[str, ...]
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "requiredCL": self.required_cl,
            "clMaxWing": self.cl_max_wing,
            "margin": self.margin,
            "reasons": list(self.reasons),
            "meta": self.meta.canonical(),
        }


def check_stall_constraint(
    required_cl: float,
    wing: FiniteWingResult,
    *,
    margin_fraction: float = 0.1,
) -> StallConstraintVerdict:
    finite(required_cl, "required_cl")
    finite(margin_fraction, "margin_fraction", minimum=0.0, maximum=0.9)
    allowable = wing.cl_max_wing * (1.0 - margin_fraction)
    margin = wing.cl_max_wing - required_cl
    reasons: list[str] = []
    if required_cl > allowable:
        reasons.append(
            f"STALL_CONSTRAINT_VIOLATED:required {required_cl:.4g} "
            f"exceeds allowable {allowable:.4g} (CLmax {wing.cl_max_wing:.4g})"
        )
    if wing.regime in ("stalled", "poststall", "deepstall"):
        reasons.append(f"STALL_REGIME_EXCEEDED:{wing.regime}")
    if not wing.meta.validity.passed and wing.regime not in ("attached", "prestall"):
        reasons.append("WING_STATE_OUTSIDE_ATTACHED_VALIDITY")
    passed = not reasons
    meta = result_meta(
        model="vehicle-systems.highlift.stall-constraint",
        inputs={
            "requiredCL": required_cl,
            "wing": wing.canonical(),
            "marginFraction": margin_fraction,
        },
        valid=passed,
        fidelity=HighLiftFidelity.FINITE_WING_NONLINEAR,
        checks={"stall_constraint_passed": passed},
        detail="stall constraint passed" if passed else ";".join(reasons),
        assumptions=("Required CL must clear the nonlinear wing CLmax with margin.",),
        source=ResultSource.ANALYTICAL,
    )
    return StallConstraintVerdict(
        passed=passed,
        required_cl=required_cl,
        cl_max_wing=wing.cl_max_wing,
        margin=margin,
        reasons=tuple(reasons),
        meta=meta,
    )


def linear_vlm_lift(
    alpha_deg: float, params: SectionStallParameters, planform: WingPlanform
) -> float:
    finite(alpha_deg, "alpha_deg")
    slope = params.lift_slope_per_rad * planform.lift_correction(params.lift_slope_per_rad)
    return slope * (alpha_deg - params.alpha_zero_lift_deg) * pi / 180.0


def require_nonlinear_guard(
    alpha_deg: float,
    required_cl: float,
    params: SectionStallParameters,
    planform: WingPlanform,
    delta: ConfigurationDelta | None = None,
) -> FiniteWingResult:
    wing = evaluate_finite_wing(alpha_deg, params, planform, delta)
    verdict = check_stall_constraint(required_cl, wing)
    if not verdict.passed:
        raise ValidityError(";".join(verdict.reasons))
    return wing


__all__ = [
    "MODEL_WING",
    "FiniteWingResult",
    "StallConstraintVerdict",
    "WingPlanform",
    "check_stall_constraint",
    "evaluate_finite_wing",
    "linear_vlm_lift",
    "require_nonlinear_guard",
]
