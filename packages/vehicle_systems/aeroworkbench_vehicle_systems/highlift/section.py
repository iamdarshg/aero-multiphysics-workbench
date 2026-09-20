"""Low-cost nonlinear section lift/stall model with explicit validity."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

from aeroworkbench_core.types import ResultSource

from .contracts import HighLiftFidelity, ResultMeta, result_meta
from .devices import ConfigurationDelta
from .errors import HighLiftError, ValidityError, finite

MODEL_SECTION = "vehicle-systems.highlift.section-nonlinear"

REGIMES: tuple[str, ...] = (
    "attached",
    "prestall",
    "stalled",
    "poststall",
    "deepstall",
)

_ASSUMPTIONS = (
    "Piecewise-linear section lift: linear slope to stall onset, linear decay post-stall.",
    "Quadratic-parabolic section drag with linear post-stall separation rise.",
    "Validity envelope declared on the stall parameters; out-of-envelope queries fail closed.",
)


@dataclass(frozen=True, slots=True)
class SectionStallParameters:
    section_id: str
    alpha_zero_lift_deg: float
    lift_slope_per_rad: float
    alpha_stall_deg: float
    cl_max: float
    cd0: float
    drag_k: float
    cm0: float
    post_stall_drop_per_deg: float
    post_stall_drag_rise_per_deg: float
    deep_stall_alpha_deg: float
    alpha_min_deg: float = -10.0
    alpha_max_deg: float = 30.0
    source: str = "declared"

    def __post_init__(self) -> None:
        if not self.section_id.strip() or not self.source.strip():
            raise HighLiftError("SECTION_IDENTITY_REQUIRED")
        finite(self.alpha_zero_lift_deg, "alpha_zero_lift_deg")
        finite(self.lift_slope_per_rad, "lift_slope_per_rad", positive=True)
        finite(self.alpha_stall_deg, "alpha_stall_deg")
        finite(self.cl_max, "cl_max", positive=True)
        finite(self.cd0, "cd0", minimum=0.0)
        finite(self.drag_k, "drag_k", minimum=0.0)
        finite(self.cm0, "cm0")
        finite(self.post_stall_drop_per_deg, "post_stall_drop_per_deg", minimum=0.0)
        finite(self.post_stall_drag_rise_per_deg, "post_stall_drag_rise_per_deg", minimum=0.0)
        finite(self.deep_stall_alpha_deg, "deep_stall_alpha_deg")
        if not self.deep_stall_alpha_deg > self.alpha_stall_deg:
            raise HighLiftError("deep_stall_alpha_deg must exceed alpha_stall_deg")
        finite(self.alpha_min_deg, "alpha_min_deg")
        finite(self.alpha_max_deg, "alpha_max_deg")
        if not self.alpha_min_deg < self.alpha_max_deg:
            raise HighLiftError("section alpha envelope invalid")
        if not self.alpha_min_deg <= self.alpha_stall_deg <= self.alpha_max_deg:
            raise HighLiftError("alpha_stall_deg outside section envelope")

    def canonical(self) -> dict[str, Any]:
        return {
            "sectionId": self.section_id,
            "alphaZeroLiftDeg": self.alpha_zero_lift_deg,
            "liftSlopePerRad": self.lift_slope_per_rad,
            "alphaStallDeg": self.alpha_stall_deg,
            "clMax": self.cl_max,
            "cd0": self.cd0,
            "dragK": self.drag_k,
            "cm0": self.cm0,
            "postStallDropPerDeg": self.post_stall_drop_per_deg,
            "postStallDragRisePerDeg": self.post_stall_drag_rise_per_deg,
            "deepStallAlphaDeg": self.deep_stall_alpha_deg,
            "alphaMinDeg": self.alpha_min_deg,
            "alphaMaxDeg": self.alpha_max_deg,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class SectionNonlinearResult:
    alpha_deg: float
    lift: float
    drag: float
    moment: float
    regime: str
    separated: bool
    cl_max_effective: float
    alpha_stall_effective_deg: float
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "alphaDeg": self.alpha_deg,
            "cl": self.lift,
            "cd": self.drag,
            "cm": self.moment,
            "regime": self.regime,
            "separated": self.separated,
            "clMaxEffective": self.cl_max_effective,
            "alphaStallEffectiveDeg": self.alpha_stall_effective_deg,
            "meta": self.meta.canonical(),
        }


def classify_regime(alpha_deg: float, alpha_stall_deg: float, deep_alpha_deg: float) -> str:
    if alpha_deg >= deep_alpha_deg:
        return "deepstall"
    if alpha_deg >= alpha_stall_deg + 5.0:
        return "poststall"
    if alpha_deg >= alpha_stall_deg:
        return "stalled"
    if alpha_deg >= alpha_stall_deg - 2.0:
        return "prestall"
    return "attached"


def evaluate_section(
    alpha_deg: float,
    params: SectionStallParameters,
    delta: ConfigurationDelta | None = None,
) -> SectionNonlinearResult:
    finite(alpha_deg, "alpha_deg")
    if not params.alpha_min_deg <= alpha_deg <= params.alpha_max_deg:
        raise ValidityError(
            f"SECTION_ALPHA_OUT_OF_ENVELOPE:{params.section_id}:{alpha_deg}"
        )
    applied = delta or ConfigurationDelta(
        dcl0=0.0, dclmax=0.0, dcd=0.0, dcm=0.0, dstall_deg=0.0, area_gain=0.0
    )
    stall_eff = params.alpha_stall_deg + applied.dstall_deg
    clmax_eff = params.cl_max + applied.dclmax
    if clmax_eff <= 0.0:
        raise HighLiftError("effective cl_max must be positive")
    linear = (
        params.lift_slope_per_rad * (alpha_deg - params.alpha_zero_lift_deg) * pi / 180.0
        + applied.dcl0
    )
    if alpha_deg < stall_eff:
        lift = min(linear, clmax_eff)
    else:
        dropped = clmax_eff - params.post_stall_drop_per_deg * (alpha_deg - stall_eff)
        lift = max(dropped, 0.6)
    rise = (
        params.post_stall_drag_rise_per_deg * (alpha_deg - stall_eff)
        if alpha_deg > stall_eff
        else 0.0
    )
    drag = params.cd0 + applied.dcd + params.drag_k * lift * lift + rise
    moment = params.cm0 + applied.dcm - (
        0.004 * (alpha_deg - stall_eff) if alpha_deg > stall_eff else 0.0
    )
    regime = classify_regime(alpha_deg, stall_eff, params.deep_stall_alpha_deg)
    checks = {
        "alpha_in_envelope": True,
        "clmax_positive": clmax_eff > 0.0,
        "attached": regime == "attached",
        "below_stall": alpha_deg < stall_eff,
        "below_deep_stall": regime != "deepstall",
    }
    meta = result_meta(
        model=MODEL_SECTION,
        inputs={
            "section": params.canonical(),
            "alphaDeg": alpha_deg,
            "delta": applied.canonical(),
        },
        valid=regime in ("attached", "prestall"),
        fidelity=HighLiftFidelity.SECTION_NONLINEAR,
        checks=checks,
        detail=f"section {params.section_id} at {alpha_deg} deg is {regime}",
        assumptions=_ASSUMPTIONS,
        source=ResultSource.ANALYTICAL,
    )
    return SectionNonlinearResult(
        alpha_deg=alpha_deg,
        lift=lift,
        drag=drag,
        moment=moment,
        regime=regime,
        separated=regime not in ("attached",),
        cl_max_effective=clmax_eff,
        alpha_stall_effective_deg=stall_eff,
        meta=meta,
    )


def section_polar_table(
    params: SectionStallParameters,
    alphas_deg: tuple[float, ...],
    delta: ConfigurationDelta | None = None,
) -> tuple[SectionNonlinearResult, ...]:
    if not alphas_deg:
        raise HighLiftError("polar table requires alphas")
    return tuple(evaluate_section(alpha, params, delta) for alpha in alphas_deg)


__all__ = [
    "MODEL_SECTION",
    "REGIMES",
    "SectionNonlinearResult",
    "SectionStallParameters",
    "classify_regime",
    "evaluate_section",
    "section_polar_table",
]
