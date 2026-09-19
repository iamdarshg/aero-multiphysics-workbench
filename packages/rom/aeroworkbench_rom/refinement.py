"""Active refinement: spend high-fidelity samples where the map is weak.

New samples are requested where interpolation uncertainty is high, where a
constraint boundary is near, where two models disagree, or where the query
would otherwise extrapolate. Candidate points come from the declared sampling
plan; refinement is bounded by the plan budget and the per-round budget, and
never fabricates a request when no criterion fires.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_optimization.drivers import StudyConstraint

from .errors import MapContractError
from .map import MapSample, PerformanceMap, build_map, point_key
from .models import SurrogateModel
from .sampling import SamplingPlan

__all__ = [
    "RefinementCriteria",
    "RefinementPlan",
    "RefinementPoint",
    "RefinementResult",
    "propose_refinement",
    "refine",
]


@dataclass(frozen=True, slots=True)
class RefinementCriteria:
    """Thresholds that decide whether a candidate sample is worth requesting."""

    uncertainty_threshold: float = 0.0
    boundary_margin: float = 0.0
    disagreement_threshold: float | None = None
    include_extrapolation_candidates: bool = True

    def __post_init__(self) -> None:
        if not isfinite(self.uncertainty_threshold) or self.uncertainty_threshold < 0.0:
            raise MapContractError("INVALID_UNCERTAINTY_THRESHOLD")
        if not isfinite(self.boundary_margin) or self.boundary_margin < 0.0:
            raise MapContractError("INVALID_BOUNDARY_MARGIN")
        if self.disagreement_threshold is not None and (
            not isfinite(self.disagreement_threshold) or self.disagreement_threshold < 0.0
        ):
            raise MapContractError("INVALID_DISAGREEMENT_THRESHOLD")


@dataclass(frozen=True, slots=True)
class RefinementPoint:
    """One requested refinement point with the criteria that fired."""

    point: Mapping[str, float]
    uncertainty: float
    boundary_margin: float
    disagreement: float
    extrapolates: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "point", {str(k): float(v) for k, v in self.point.items()})

    def as_dict(self) -> dict[str, Any]:
        return {
            "point": dict(sorted(self.point.items())),
            "uncertainty": self.uncertainty,
            "boundaryMargin": self.boundary_margin,
            "disagreement": self.disagreement,
            "extrapolates": self.extrapolates,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class RefinementPlan:
    """A bounded set of requested high-fidelity samples for one round."""

    round_index: int
    points: tuple[RefinementPoint, ...]
    considered: int
    budget: int
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "round": self.round_index,
            "considered": self.considered,
            "budget": self.budget,
            "digest": self.digest,
            "points": [point.as_dict() for point in self.points],
        }


@dataclass(frozen=True, slots=True)
class RefinementResult:
    """The outcome of a bounded refinement loop."""

    rounds: int
    added_samples: tuple[MapSample, ...]
    performance_map: PerformanceMap
    plans: tuple[RefinementPlan, ...]
    stop_reason: str


def _boundary_margin(
    outputs: Mapping[str, float], constraints: Sequence[StudyConstraint]
) -> float:
    if not constraints:
        return 1.0
    margins: list[float] = []
    for constraint in constraints:
        value = outputs.get(constraint.name)
        if value is None:
            margins.append(0.0)
            continue
        scale = max(abs(constraint.limit), 1e-9)
        if constraint.bound == "upper":
            margins.append((constraint.limit - value) / scale)
        elif constraint.bound == "lower":
            margins.append((value - constraint.limit) / scale)
        else:
            margins.append(1.0 - abs(value - constraint.limit) / scale)
    return min(max(margin, -1.0) for margin in margins)


def _disagreement(
    primary_model: SurrogateModel,
    other: SurrogateModel | None,
    point: Mapping[str, float],
) -> float:
    if other is None:
        return 0.0
    primary = primary_model.predict(dict(point))
    reference = other.predict(dict(point))
    names = set(primary.outputs) & set(reference.outputs)
    if not names:
        return 0.0
    return max(abs(primary.outputs[name] - reference.outputs[name]) for name in names)


def propose_refinement(
    performance_map: PerformanceMap,
    plan: SamplingPlan,
    criteria: RefinementCriteria,
    *,
    round_index: int = 1,
    constraints: Sequence[StudyConstraint] = (),
    disagreement_model: SurrogateModel | None = None,
    budget: int = 8,
) -> RefinementPlan:
    """Select bounded refinement points from the sampling plan."""

    if budget <= 0:
        raise MapContractError("REFINEMENT_BUDGET_MUST_BE_POSITIVE")
    existing = [sample.inputs for sample in performance_map.samples]
    candidates = plan.adaptive_points(
        exclude=existing, round_index=round_index, count=max(budget, plan.count)
    )
    selected: list[RefinementPoint] = []
    for point in candidates:
        inside = performance_map.contains(point)
        prediction = performance_map.model.predict(dict(point))
        uncertainty = max(prediction.uncertainty.values(), default=0.0)
        margin = _boundary_margin(prediction.outputs, constraints)
        disagreement = _disagreement(performance_map.model, disagreement_model, point)
        reasons: list[str] = []
        if not inside and criteria.include_extrapolation_candidates:
            reasons.append("extrapolation")
        if uncertainty >= criteria.uncertainty_threshold and criteria.uncertainty_threshold > 0.0:
            reasons.append("high-uncertainty")
        if criteria.boundary_margin > 0.0 and margin < criteria.boundary_margin:
            reasons.append("near-constraint-boundary")
        if (
            criteria.disagreement_threshold is not None
            and disagreement >= criteria.disagreement_threshold
        ):
            reasons.append("model-disagreement")
        if not reasons:
            continue
        selected.append(
            RefinementPoint(
                point=point,
                uncertainty=uncertainty,
                boundary_margin=margin,
                disagreement=disagreement,
                extrapolates=not inside,
                reasons=tuple(reasons),
            )
        )
    selected.sort(key=lambda item: (-item.uncertainty, point_key(item.point)))
    bounded = tuple(selected[:budget])
    digest = content_digest([item.as_dict() for item in bounded])
    return RefinementPlan(
        round_index=round_index,
        points=bounded,
        considered=len(candidates),
        budget=budget,
        digest=digest,
    )


def refine(
    performance_map: PerformanceMap,
    plan: SamplingPlan,
    criteria: RefinementCriteria,
    evaluate: Callable[[Mapping[str, float]], MapSample],
    *,
    model_factory: Callable[[], SurrogateModel],
    rounds: int = 1,
    budget: int = 8,
    constraints: Sequence[StudyConstraint] = (),
    disagreement_model: SurrogateModel | None = None,
    validation_tolerances: Mapping[str, float] | None = None,
    validation_folds: int = 3,
) -> RefinementResult:
    """Run a bounded refinement loop, rebuilding and revalidating the map."""

    if rounds < 1:
        raise MapContractError("REFINEMENT_ROUNDS_MUST_BE_POSITIVE")
    current = performance_map
    added: list[MapSample] = []
    plans: list[RefinementPlan] = []
    stop_reason = "budget"
    completed = 0
    for round_index in range(1, rounds + 1):
        round_plan = propose_refinement(
            current,
            plan,
            criteria,
            round_index=round_index,
            constraints=constraints,
            disagreement_model=disagreement_model,
            budget=budget,
        )
        plans.append(round_plan)
        if not round_plan.points:
            stop_reason = "converged"
            break
        new_samples = tuple(evaluate(dict(item.point)) for item in round_plan.points)
        added.extend(new_samples)
        samples = (*current.samples, *new_samples)
        model = model_factory()
        current = build_map(
            map_id=current.map_id,
            variables=current.variables,
            outputs=current.outputs,
            samples=samples,
            model=model,
            revision=current.revision + 1,
            extrapolation=current.extrapolation,
            parent_revision=current.revision,
            provenance=current.provenance,
        )
        completed = round_index
        if validation_tolerances is not None:
            from .validation import CrossValidationReport, cross_validate

            report: CrossValidationReport = cross_validate(
                model_factory, samples, folds=validation_folds
            )
            current = PerformanceMap(
                map_id=current.map_id,
                revision=current.revision,
                variables=current.variables,
                outputs=current.outputs,
                model=current.model,
                samples=current.samples,
                extrapolation=current.extrapolation,
                validation=report,
                parent_revision=current.parent_revision,
                software=current.software,
                provenance=current.provenance,
            )
    return RefinementResult(
        rounds=completed,
        added_samples=tuple(added),
        performance_map=current,
        plans=tuple(plans),
        stop_reason=stop_reason,
    )
