"""High-lift fidelity ladder, escalation policy, and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import ResultSource
from aeroworkbench_optimization import (
    FidelityImplementation,
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)

from .contracts import HighLiftFidelity, ResultMeta, result_meta
from .devices import HighLiftConfiguration
from .errors import CapabilityUnavailable, HighLiftError, finite
from .section import SectionStallParameters
from .stall import StallMargin
from .unsteady import DynamicStallBackend, DynamicStallRequest, solve_dynamic_stall
from .wing import FiniteWingResult, WingPlanform, evaluate_finite_wing

HIGHLIFT_LADDER: tuple[FidelityImplementation, ...] = (
    FidelityImplementation(
        name="attached_linear",
        rank=0,
        cost=0.0,
        capabilities=("screening", "validity_limits"),
        description="linear attached screening with declared stall caps",
    ),
    FidelityImplementation(
        name="section_nonlinear",
        rank=1,
        cost=0.1,
        capabilities=("screening", "nonlinear_section", "stall_onset"),
        description="nonlinear section lift with stall onset and post-stall branch",
    ),
    FidelityImplementation(
        name="finite_wing_nonlinear",
        rank=2,
        cost=1.0,
        capabilities=("nonlinear_section", "finite_wing", "stall_margin", "control_authority"),
        description="finite-wing nonlinear aggregation with stall margin and authority",
    ),
    FidelityImplementation(
        name="unsteady",
        rank=3,
        cost=10.0,
        capabilities=("native", "dynamic_stall", "hysteresis"),
        description="governed unsteady/dynamic-stall solve (capability-gated)",
    ),
    FidelityImplementation(
        name="native_rans",
        rank=4,
        cost=100.0,
        capabilities=("native", "rans", "separation", "meshing_promotion"),
        description="governed RANS/unsteady CFD promotion (capability-gated)",
    ),
)

_FIDELITY_BY_NAME: dict[str, HighLiftFidelity] = {
    "attached_linear": HighLiftFidelity.ATTACHED_LINEAR,
    "section_nonlinear": HighLiftFidelity.SECTION_NONLINEAR,
    "finite_wing_nonlinear": HighLiftFidelity.FINITE_WING_NONLINEAR,
    "unsteady": HighLiftFidelity.UNSTEADY,
    "native_rans": HighLiftFidelity.NATIVE,
}

STALL_ESCALATION_MARGIN_DEG = 2.0


def plan_highlift_fidelity(current: str, signals: FidelitySignals) -> FidelityPlan:
    return plan_fidelity(current, HIGHLIFT_LADDER, signals)


def escalation_for_margin(margin: StallMargin) -> tuple[bool, str]:
    if margin.level in ("warning", "stall"):
        return True, f"stall margin {margin.alpha_margin_deg:.3g} deg demands higher fidelity"
    if margin.level == "caution":
        return True, f"near-stall margin {margin.alpha_margin_deg:.3g} deg escalates one rank"
    return False, f"margin {margin.alpha_margin_deg:.3g} deg holds current fidelity"


def validity_signals_for_ladder(wing: FiniteWingResult) -> dict[str, bool]:
    attached = wing.regime in ("attached", "prestall")
    return {
        "attached_linear": attached and wing.alpha_deg < wing.alpha_stall_wing_deg - 2.0,
        "section_nonlinear": wing.regime != "deepstall",
        "finite_wing_nonlinear": wing.regime != "deepstall",
        "unsteady": False,
        "native_rans": False,
    }


@dataclass(frozen=True, slots=True)
class HighLiftAeroResult:
    result_id: str
    config_id: str
    alpha_deg: float
    lift: float
    drag: float
    moment: float
    regime: str
    fidelity: HighLiftFidelity
    cl_max_wing: float
    alpha_stall_wing_deg: float
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "resultId": self.result_id,
            "configId": self.config_id,
            "alphaDeg": self.alpha_deg,
            "CL": self.lift,
            "CD": self.drag,
            "Cm": self.moment,
            "regime": self.regime,
            "fidelity": self.fidelity.value,
            "clMaxWing": self.cl_max_wing,
            "alphaStallWingDeg": self.alpha_stall_wing_deg,
            "meta": self.meta.canonical(),
        }


def solve_highlift_aero(
    config: HighLiftConfiguration,
    params: SectionStallParameters,
    planform: WingPlanform,
    alpha_deg: float,
    *,
    fidelity: str = "finite_wing_nonlinear",
    unsteady_request: DynamicStallRequest | None = None,
    unsteady_backend: DynamicStallBackend | None = None,
    run_id: str | None = None,
) -> HighLiftAeroResult:
    finite(alpha_deg, "alpha_deg")
    if fidelity not in _FIDELITY_BY_NAME:
        raise HighLiftError(f"UNKNOWN_HIGHLIFT_FIDELITY:{fidelity}")
    if fidelity in ("unsteady", "native_rans"):
        if unsteady_backend is None:
            raise CapabilityUnavailable(
                f"HIGHLIFT_{fidelity.upper()}_UNAVAILABLE:no backend wired"
            )
        if unsteady_request is None:
            raise HighLiftError(f"HIGHLIFT_{fidelity.upper()}_REQUIRES_UNSTEADY_REQUEST")
        if run_id is None or not run_id.strip():
            raise HighLiftError(f"HIGHLIFT_{fidelity.upper()}_REQUIRES_RUN_ID")
        solved = solve_dynamic_stall(
            unsteady_request, backend=unsteady_backend, run_id=run_id
        )
        wing = evaluate_finite_wing(alpha_deg, params, planform, config.delta())
        return _wrap(
            config,
            wing,
            _FIDELITY_BY_NAME[fidelity],
            extra_inputs={"unsteadySolution": solved.solution.canonical()},
        )
    wing = evaluate_finite_wing(alpha_deg, params, planform, config.delta())
    return _wrap(config, wing, _FIDELITY_BY_NAME[fidelity])


def _wrap(
    config: HighLiftConfiguration,
    wing: FiniteWingResult,
    fidelity: HighLiftFidelity,
    extra_inputs: dict[str, Any] | None = None,
) -> HighLiftAeroResult:
    inputs: dict[str, Any] = {
        "config": config.canonical(),
        "wing": wing.canonical(),
        "fidelity": fidelity.value,
    }
    if extra_inputs:
        inputs.update(extra_inputs)
    meta = result_meta(
        model="vehicle-systems.highlift.solve",
        inputs=inputs,
        valid=wing.meta.validity.passed,
        fidelity=fidelity,
        checks=dict(wing.meta.validity.checks),
        detail=f"{config.config_id} at {wing.alpha_deg} deg via {fidelity.value}",
        assumptions=("Configuration increments applied to the nonlinear wing state.",),
        source=ResultSource.ANALYTICAL,
    )
    return HighLiftAeroResult(
        result_id=f"{config.config_id}-a{wing.alpha_deg:g}-{fidelity.value}",
        config_id=config.config_id,
        alpha_deg=wing.alpha_deg,
        lift=wing.lift,
        drag=wing.drag,
        moment=wing.moment,
        regime=wing.regime,
        fidelity=fidelity,
        cl_max_wing=wing.cl_max_wing,
        alpha_stall_wing_deg=wing.alpha_stall_wing_deg,
        meta=meta,
    )


__all__ = [
    "HIGHLIFT_LADDER",
    "STALL_ESCALATION_MARGIN_DEG",
    "HighLiftAeroResult",
    "escalation_for_margin",
    "plan_highlift_fidelity",
    "solve_highlift_aero",
    "validity_signals_for_ladder",
]
