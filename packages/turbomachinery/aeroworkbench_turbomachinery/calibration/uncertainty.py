"""Propagate data and model uncertainty through reduced models (part C).

Uncertainty variables reuse ``aeroworkbench_vehicle_systems.robust`` sources
and sampling; propagation delegates to ``robust.propagate``. This module adds
the turbomachinery-facing helpers: declared tolerance/ambient/map inputs,
robust constraint margins, and uncertainty-driven fidelity escalation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_vehicle_systems.robust.contracts import (
    UncertaintySpec,
    UncertainVariable,
)
from aeroworkbench_vehicle_systems.robust.propagation import (
    PropagationResult,
    propagate,
)
from aeroworkbench_vehicle_systems.robust.sampling import SamplingMethod, SamplingPlan
from aeroworkbench_vehicle_systems.robust.sources import (
    calibration_variable,
    material_scatter_variable,
    tolerance_variable,
)

from ..canonical import content_digest
from .errors import CalibrationInputError

MAX_PROPAGATION_SAMPLES = 512


def geometry_tolerance_input(
    name: str, unit: str, nominal: float, half_width: float
) -> UncertainVariable:
    return tolerance_variable(
        name, unit, nominal, half_width, reference="turbo-geometry-tolerance", revision="1"
    )


def ambient_condition_input(
    name: str, unit: str, nominal: float, half_width: float
) -> UncertainVariable:
    return tolerance_variable(
        name,
        unit,
        nominal,
        half_width,
        distribution="normal",
        reference="turbo-ambient-conditions",
        revision="1",
    )


def map_correlation_input(
    name: str, unit: str, mean: float, std: float
) -> UncertainVariable:
    if not std > 0.0:
        raise CalibrationInputError(f"MAP_UNCERTAINTY_MUST_BE_POSITIVE:{name}")
    return calibration_variable(
        name, unit, mean, std, reference="turbo-map-correlation", revision="1"
    )


def material_scatter_input(
    name: str, unit: str, mean: float, coefficient_of_variation: float
) -> UncertainVariable:
    return material_scatter_variable(
        name, unit, mean, coefficient_of_variation, reference="turbo-material-batch"
    )


def build_spec(
    spec_id: str, variables: Sequence[UncertainVariable]
) -> UncertaintySpec:
    if not spec_id.strip():
        raise CalibrationInputError("SPEC_ID_REQUIRED")
    if not variables:
        raise CalibrationInputError("SPEC_NEEDS_VARIABLES")
    names = [v.name for v in variables]
    if len(names) != len(set(names)):
        raise CalibrationInputError("DUPLICATE_UNCERTAIN_VARIABLE")
    return UncertaintySpec(
        spec_id=spec_id,
        variables=tuple(variables),
        correlations=(),
        model_form=(),
    )


def build_plan(
    plan_id: str, count: int, *, seed: int = 0, max_count: int = MAX_PROPAGATION_SAMPLES
) -> SamplingPlan:
    if count <= 0:
        raise CalibrationInputError("PROPAGATION_COUNT_MUST_BE_POSITIVE")
    if count > max_count:
        raise CalibrationInputError(f"PROPAGATION_COUNT_EXCEEDS_BOUND:{count}>{max_count}")
    return SamplingPlan(
        plan_id=plan_id,
        method=SamplingMethod.LATIN_HYPERCUBE,
        count=count,
        seed=seed,
        max_count=max_count,
    )


def propagate_predictions(
    spec: UncertaintySpec,
    plan: SamplingPlan,
    evaluate: Any,
    output_names: Sequence[str],
) -> PropagationResult:
    if not output_names:
        raise CalibrationInputError("PROPAGATION_NEEDS_OUTPUTS")
    return propagate(spec, plan, evaluate, tuple(output_names))


@dataclass(frozen=True, slots=True)
class ConstraintMargin:
    quantity: str
    unit: str
    limit: float
    mean: float
    std: float
    margin: float
    margin_in_sigma: float
    robust_pass: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "unit": self.unit,
            "limit": self.limit,
            "mean": self.mean,
            "std": self.std,
            "margin": self.margin,
            "marginInSigma": self.margin_in_sigma,
            "robustPass": self.robust_pass,
        }


def robust_constraint_margin(
    quantity: str,
    unit: str,
    limit: float,
    result: PropagationResult,
    *,
    upper_bound: bool = True,
    sigma_multiple: float = 2.0,
) -> ConstraintMargin:
    if quantity not in result.output_names:
        raise CalibrationInputError(f"UNKNOWN_PROPAGATED_OUTPUT:{quantity}")
    if sigma_multiple <= 0.0:
        raise CalibrationInputError("SIGMA_MULTIPLE_MUST_BE_POSITIVE")
    moments = result.moment_for(quantity)
    mean = moments.mean
    std = moments.std
    edge = mean + sigma_multiple * std if upper_bound else mean - sigma_multiple * std
    margin = limit - edge if upper_bound else edge - limit
    if std > 0.0:
        margin_in_sigma = margin / std
    elif margin > 0:
        margin_in_sigma = float("inf")
    else:
        margin_in_sigma = float("-inf")
    return ConstraintMargin(
        quantity=quantity,
        unit=unit,
        limit=limit,
        mean=mean,
        std=std,
        margin=margin,
        margin_in_sigma=margin_in_sigma,
        robust_pass=margin >= 0.0,
    )


@dataclass(frozen=True, slots=True)
class FidelityEscalation:
    escalate: bool
    reason: str
    worst_relative_std: float

    def canonical(self) -> dict[str, Any]:
        return {
            "escalate": self.escalate,
            "reason": self.reason,
            "worstRelativeStd": self.worst_relative_std,
        }


def fidelity_escalation_decision(
    result: PropagationResult, *, relative_std_threshold: float = 0.05
) -> FidelityEscalation:
    if relative_std_threshold <= 0.0:
        raise CalibrationInputError("ESCALATION_THRESHOLD_MUST_BE_POSITIVE")
    worst = 0.0
    for name in result.output_names:
        moments = result.moment_for(name)
        mean = moments.mean
        std = moments.std
        rel = abs(std / mean) if mean != 0.0 else (float("inf") if std > 0.0 else 0.0)
        worst = max(worst, rel)
    escalate = worst > relative_std_threshold
    return FidelityEscalation(
        escalate=escalate,
        reason=(
            f"worst relative std {worst:.4f} exceeds {relative_std_threshold:.4f}"
            if escalate
            else f"worst relative std {worst:.4f} within {relative_std_threshold:.4f}"
        ),
        worst_relative_std=worst,
    )


def uncertainty_digest(
    spec: UncertaintySpec, plan: SamplingPlan, outputs: Sequence[str]
) -> str:
    return content_digest(
        {
            "spec": spec.spec_id,
            "variables": sorted(v.name for v in spec.variables),
            "plan": plan.canonical_payload(),
            "outputs": list(outputs),
        }
    )


__all__ = [
    "MAX_PROPAGATION_SAMPLES",
    "ConstraintMargin",
    "FidelityEscalation",
    "ambient_condition_input",
    "build_plan",
    "build_spec",
    "fidelity_escalation_decision",
    "geometry_tolerance_input",
    "map_correlation_input",
    "material_scatter_input",
    "propagate_predictions",
    "robust_constraint_margin",
    "uncertainty_digest",
]
