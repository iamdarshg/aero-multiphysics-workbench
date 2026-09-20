"""Stall warning, margin, deep-stall and tail-blanketing assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import ResultSource

from .contracts import HighLiftFidelity, ResultMeta, result_meta
from .errors import HighLiftError, finite
from .wing import FiniteWingResult

MODEL_MARGIN = "vehicle-systems.highlift.stall-margin"
MODEL_DEEPSTALL = "vehicle-systems.highlift.deep-stall"

WARNING_LEVELS: tuple[str, ...] = ("none", "advisory", "caution", "warning", "stall")


def warning_level(alpha_margin_deg: float) -> str:
    finite(alpha_margin_deg, "alpha_margin_deg")
    if alpha_margin_deg < 0.0:
        return "stall"
    if alpha_margin_deg < 1.5:
        return "warning"
    if alpha_margin_deg < 3.0:
        return "caution"
    if alpha_margin_deg < 5.0:
        return "advisory"
    return "none"


@dataclass(frozen=True, slots=True)
class StallMargin:
    alpha_deg: float
    alpha_stall_deg: float
    alpha_margin_deg: float
    cl: float
    cl_max: float
    cl_margin: float
    level: str
    stick_shaker: bool
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "alphaDeg": self.alpha_deg,
            "alphaStallDeg": self.alpha_stall_deg,
            "alphaMarginDeg": self.alpha_margin_deg,
            "CL": self.cl,
            "clMax": self.cl_max,
            "clMargin": self.cl_margin,
            "level": self.level,
            "stickShaker": self.stick_shaker,
            "meta": self.meta.canonical(),
        }


def evaluate_stall_margin(wing: FiniteWingResult) -> StallMargin:
    alpha_margin = wing.alpha_stall_wing_deg - wing.alpha_deg
    cl_margin = wing.cl_max_wing - wing.lift
    level = warning_level(alpha_margin)
    meta = result_meta(
        model=MODEL_MARGIN,
        inputs={"wing": wing.canonical()},
        valid=level in ("none", "advisory"),
        fidelity=HighLiftFidelity.FINITE_WING_NONLINEAR,
        checks={
            "positive_alpha_margin": alpha_margin > 0.0,
            "positive_cl_margin": cl_margin > 0.0,
            "no_warning": level in ("none", "advisory"),
        },
        detail=f"stall margin {alpha_margin:.3g} deg is {level}",
        assumptions=("Warning bands at 5/3/1.5/0 deg alpha margin.",),
        source=ResultSource.ANALYTICAL,
    )
    return StallMargin(
        alpha_deg=wing.alpha_deg,
        alpha_stall_deg=wing.alpha_stall_wing_deg,
        alpha_margin_deg=alpha_margin,
        cl=wing.lift,
        cl_max=wing.cl_max_wing,
        cl_margin=cl_margin,
        level=level,
        stick_shaker=level in ("warning", "stall"),
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class DeepStallAssessment:
    assessed: bool
    alpha_deg: float
    deep_stall_alpha_deg: float | None
    tail_declared: bool
    blanketing_risk: str
    detail: str
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "assessed": self.assessed,
            "alphaDeg": self.alpha_deg,
            "deepStallAlphaDeg": self.deep_stall_alpha_deg,
            "tailDeclared": self.tail_declared,
            "blanketingRisk": self.blanketing_risk,
            "detail": self.detail,
            "meta": self.meta.canonical(),
        }


def assess_deep_stall(
    wing: FiniteWingResult,
    *,
    deep_stall_alpha_deg: float | None,
    tail_declared: bool,
    tail_arm_m: float | None = None,
) -> DeepStallAssessment:
    if deep_stall_alpha_deg is not None:
        finite(deep_stall_alpha_deg, "deep_stall_alpha_deg")
    if tail_arm_m is not None:
        finite(tail_arm_m, "tail_arm_m", positive=True)
    if deep_stall_alpha_deg is None or not tail_declared:
        detail = "deep-stall not assessed: tail geometry not declared"
        meta = result_meta(
            model=MODEL_DEEPSTALL,
            inputs={
                "wing": wing.canonical(),
                "tailDeclared": tail_declared,
            },
            valid=False,
            fidelity=HighLiftFidelity.FINITE_WING_NONLINEAR,
            checks={"assessed": False},
            detail=detail,
            assumptions=("No blanketing claim without declared tail geometry.",),
            source=ResultSource.ANALYTICAL,
        )
        return DeepStallAssessment(
            assessed=False,
            alpha_deg=wing.alpha_deg,
            deep_stall_alpha_deg=deep_stall_alpha_deg,
            tail_declared=tail_declared,
            blanketing_risk="unknown",
            detail=detail,
            meta=meta,
        )
    if wing.alpha_deg >= deep_stall_alpha_deg:
        risk = "high"
        detail = f"alpha {wing.alpha_deg} deg at/above deep-stall {deep_stall_alpha_deg} deg"
    elif wing.alpha_deg >= deep_stall_alpha_deg - 3.0:
        risk = "elevated"
        detail = f"alpha {wing.alpha_deg} deg within 3 deg of deep-stall"
    else:
        risk = "low"
        detail = f"alpha {wing.alpha_deg} deg clear of deep-stall {deep_stall_alpha_deg} deg"
    if tail_arm_m is None:
        raise HighLiftError("tail_arm_m required when tail is declared")
    meta = result_meta(
        model=MODEL_DEEPSTALL,
        inputs={
            "wing": wing.canonical(),
            "deepStallAlphaDeg": deep_stall_alpha_deg,
            "tailDeclared": tail_declared,
            "tailArmM": tail_arm_m,
        },
        valid=risk == "low",
        fidelity=HighLiftFidelity.FINITE_WING_NONLINEAR,
        checks={"deep_stall_clear": risk == "low", "assessed": True},
        detail=detail,
        assumptions=("Deep-stall band is a declared threshold, not a resolved wake.",),
        source=ResultSource.ANALYTICAL,
    )
    return DeepStallAssessment(
        assessed=True,
        alpha_deg=wing.alpha_deg,
        deep_stall_alpha_deg=deep_stall_alpha_deg,
        tail_declared=True,
        blanketing_risk=risk,
        detail=detail,
        meta=meta,
    )


__all__ = [
    "MODEL_DEEPSTALL",
    "MODEL_MARGIN",
    "WARNING_LEVELS",
    "DeepStallAssessment",
    "StallMargin",
    "assess_deep_stall",
    "evaluate_stall_margin",
    "warning_level",
]
