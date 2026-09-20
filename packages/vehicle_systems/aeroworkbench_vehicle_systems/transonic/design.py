"""Transonic/supersonic design guidance and optimization constraints."""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, degrees, isfinite, radians
from typing import Any

from aeroworkbench_optimization.drivers import StudyConstraint

from .corrections import compressible_derivative
from .drag_rise import MAX_SWEEP_DEG, drag_divergence_mach
from .errors import TransonicContractError, TransonicValidityError
from .regime import assert_not_hypersonic

__all__ = [
    "ConstraintEvaluation",
    "TipGuidance",
    "buffet_boundary_cl",
    "compatible_derivative",
    "evaluate_transonic_constraints",
    "max_thickness_ratio",
    "required_sweep_deg",
    "tip_section_guidance",
    "transonic_design_constraints",
]

DESIGN_MODEL = "vehicle-systems.transonic.design-guidance"


def required_sweep_deg(
    target_divergence_mach: float,
    thickness_ratio: float,
    lift_coefficient: float,
    kappa: float = 0.87,
) -> float:
    """Sweep needed so Korn divergence reaches the target; 0 when already met."""

    for label, item in (
        ("TARGET", target_divergence_mach),
        ("THICKNESS", thickness_ratio),
        ("LIFT", lift_coefficient),
    ):
        if not isfinite(item):
            raise TransonicContractError(f"DESIGN_{label}_NOT_FINITE")
    normal = drag_divergence_mach(thickness_ratio, lift_coefficient, 0.0, kappa)
    if target_divergence_mach <= normal:
        return 0.0
    cosine = normal / target_divergence_mach
    if cosine < cos(radians(MAX_SWEEP_DEG)):
        raise TransonicValidityError(
            f"SWEEP_BEYOND_DECLARED_BAND:target={target_divergence_mach}:escalate"
        )
    return float(degrees(acos(max(min(cosine, 1.0), -1.0))))


def max_thickness_ratio(
    target_divergence_mach: float,
    lift_coefficient: float,
    sweep_deg: float,
    kappa: float = 0.87,
) -> float:
    """Thickest section Korn divergence still reaches the target with."""

    if not isfinite(target_divergence_mach) or target_divergence_mach <= 0.0:
        raise TransonicContractError(f"DESIGN_TARGET_NOT_POSITIVE:{target_divergence_mach!r}")
    if not isfinite(sweep_deg) or not 0.0 <= sweep_deg <= MAX_SWEEP_DEG:
        raise TransonicContractError(f"SWEEP_OUT_OF_RANGE:{sweep_deg!r}")
    thick = kappa - 0.1 * lift_coefficient - target_divergence_mach * cos(radians(sweep_deg))
    if not isfinite(thick):
        raise TransonicContractError("DESIGN_THICKNESS_NOT_FINITE")
    if thick < 0.03:
        raise TransonicValidityError(f"THICKNESS_BELOW_DECLARED_BAND:t/c={thick}:escalate")
    return float(thick)


def buffet_boundary_cl(
    mach: float, thickness_ratio: float, sweep_deg: float, kappa: float = 0.87
) -> float:
    """Korn-derived buffet-boundary lift coefficient at one Mach and sweep."""

    value = assert_not_hypersonic(mach)
    if not isfinite(value) or not 0.3 <= value < 1.2:
        raise TransonicValidityError(f"BUFFET_BOUNDARY_MACH_OUT_OF_RANGE:mach={value}")
    if not isfinite(thickness_ratio) or not 0.03 <= thickness_ratio <= 0.20:
        raise TransonicContractError(f"THICKNESS_RATIO_OUT_OF_RANGE:{thickness_ratio!r}")
    if not isfinite(sweep_deg) or not 0.0 <= sweep_deg <= MAX_SWEEP_DEG:
        raise TransonicContractError(f"SWEEP_OUT_OF_RANGE:{sweep_deg!r}")
    cosine = cos(radians(sweep_deg))
    margin = kappa - value * cosine - thickness_ratio / cosine
    if margin <= 0.0:
        raise TransonicValidityError(f"ALREADY_DIVERGED:mach={value}:margin={margin}")
    return float(10.0 * cosine * cosine * margin)


@dataclass(frozen=True, slots=True)
class TipGuidance:
    """Tip-section shock guidance: allowed tip CL and washout recommendation."""

    allowed_tip_cl: float
    tip_cl_estimate: float
    washout_recommended: bool
    margin: float

    def canonical(self) -> dict[str, Any]:
        return {
            "allowedTipCl": self.allowed_tip_cl,
            "tipClEstimate": self.tip_cl_estimate,
            "washoutRecommended": self.washout_recommended,
            "margin": self.margin,
        }


def tip_section_guidance(
    tip_cl_estimate: float,
    mach: float,
    tip_thickness_ratio: float,
    sweep_deg: float,
    kappa: float = 0.87,
) -> TipGuidance:
    """Bound tip loading against the buffet boundary; recommend washout when exceeded."""

    if not isfinite(tip_cl_estimate):
        raise TransonicContractError(f"DESIGN_TIP_CL_NOT_FINITE:{tip_cl_estimate!r}")
    allowed = buffet_boundary_cl(mach, tip_thickness_ratio, sweep_deg, kappa)
    margin = allowed - tip_cl_estimate
    return TipGuidance(allowed, float(tip_cl_estimate), bool(margin < 0.0), float(margin))


def compatible_derivative(
    cl_alpha_incomp_per_rad: float, mach: float, divergence_mach: float
) -> float:
    """Compressibility-scaled stability derivative; fails closed when shock-sensitive."""

    value = assert_not_hypersonic(mach)
    if value > divergence_mach - 0.02:
        raise TransonicValidityError(
            f"DERIVATIVE_SHOCK_SENSITIVE:mach={value}:mdd={divergence_mach}:use native"
        )
    return compressible_derivative(cl_alpha_incomp_per_rad, value)


def transonic_design_constraints(
    divergence_margin_min: float = 0.02, cd_wave_allowance: float = 0.002
) -> tuple[StudyConstraint, ...]:
    """Optimization constraints so compressibility participates in design studies."""

    if not isfinite(divergence_margin_min) or divergence_margin_min < 0.0:
        raise TransonicContractError(f"INVALID_MARGIN:{divergence_margin_min!r}")
    if not isfinite(cd_wave_allowance) or cd_wave_allowance < 0.0:
        raise TransonicContractError(f"INVALID_CD_ALLOWANCE:{cd_wave_allowance!r}")
    return (
        StudyConstraint(name="divergence-margin", bound="lower", limit=divergence_margin_min),
        StudyConstraint(name="wave-drag-rise", bound="upper", limit=cd_wave_allowance),
    )


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation:
    """One evaluated design constraint with its satisfaction verdict."""

    constraint: StudyConstraint
    value: float
    satisfied: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.constraint.name,
            "bound": self.constraint.bound,
            "limit": self.constraint.limit,
            "value": self.value,
            "satisfied": self.satisfied,
        }


def evaluate_transonic_constraints(
    mach: float,
    divergence_mach: float,
    delta_cd_wave: float,
    constraints: tuple[StudyConstraint, ...] | None = None,
) -> tuple[ConstraintEvaluation, ...]:
    """Evaluate divergence-margin and wave-drag constraints at one point."""

    active = constraints if constraints is not None else transonic_design_constraints()
    values = {"divergence-margin": divergence_mach - mach, "wave-drag-rise": delta_cd_wave}
    evaluations: list[ConstraintEvaluation] = []
    for constraint in active:
        if constraint.name not in values:
            raise TransonicContractError(f"UNKNOWN_TRANSONIC_CONSTRAINT:{constraint.name}")
        point = values[constraint.name]
        if not isfinite(point):
            raise TransonicContractError(f"CONSTRAINT_VALUE_NOT_FINITE:{constraint.name}")
        if constraint.bound == "lower":
            satisfied = point >= constraint.limit
        else:
            satisfied = point <= constraint.limit
        evaluations.append(ConstraintEvaluation(constraint, float(point), bool(satisfied)))
    return tuple(evaluations)
