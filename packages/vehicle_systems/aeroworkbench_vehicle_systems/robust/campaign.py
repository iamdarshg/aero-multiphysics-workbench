"""Campaign adapter: robust objectives and reliability through existing seams.

This module does not add a second optimization engine. It wraps a deterministic
nominal evaluator into the campaign's :class:`Evaluator` seam so each candidate
is evaluated by bounded uncertainty propagation, and it supplies a
:class:`RobustSelector` through the campaign's :class:`Selector` seam. Robust
objectives become ordinary :class:`StudyObjective` values and reliability
requirements become ordinary :class:`StudyConstraint` values, so weighted and
Pareto selection keep their exact core semantics.

Model-form uncertainty stays visible: a reliability claim is only admissible at
a *trusted* fidelity, and a cheap surrogate's discrepancy is carried as a
worst-case margin penalty rather than being converted into physical scatter.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from aeroworkbench_core.types import ResultSource
from aeroworkbench_optimization import (
    CampaignBudget,
    CampaignSpec,
    Candidate,
    EvaluationRecord,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    PhysicsFlags,
    QualityPolicy,
    StudyConstraint,
    StudyObjective,
)
from aeroworkbench_optimization.campaign import pareto_front, rank_weighted

from .contracts import ModelFormUncertainty, UncertaintyClass, UncertaintySpec
from .errors import PropagationError, RobustOptimizationError
from .objectives import RobustObjective, robust_objective_values
from .propagation import sample_responses
from .reliability import (
    LimitDirection,
    ReliabilityConstraint,
    ReliabilityEstimate,
    estimate_reliability,
)
from .sampling import SamplingPlan

__all__ = [
    "NominalEvaluator",
    "RobustEvaluationSpec",
    "RobustEvaluator",
    "RobustSelector",
    "build_campaign_spec",
    "robust_evaluator",
    "robust_study_constraints",
    "robust_study_objectives",
]

NominalEvaluator = Callable[[Mapping[str, float], str], Mapping[str, float]]
FlagsFor = Callable[[str], PhysicsFlags]


@dataclass(frozen=True, slots=True)
class RobustEvaluationSpec:
    """Everything needed to evaluate one candidate robustly at a fidelity."""

    spec: UncertaintySpec
    plan: SamplingPlan
    objectives: tuple[RobustObjective, ...]
    reliability: tuple[ReliabilityConstraint, ...] = ()
    classes: tuple[UncertaintyClass, ...] = (UncertaintyClass.ALEATORY,)
    source: ResultSource = ResultSource.SURROGATE
    fidelity_trust: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objectives:
            raise RobustOptimizationError("ROBUST_EVALUATION_NEEDS_OBJECTIVES")
        names = [objective.name for objective in self.objectives]
        names.extend(constraint.name for constraint in self.reliability)
        if len(names) != len(set(names)):
            raise RobustOptimizationError("ROBUST_EVALUATION_DUPLICATE_OUTPUT_NAME")
        if not self.classes:
            raise RobustOptimizationError("ROBUST_EVALUATION_NEEDS_CLASSES")

    @property
    def response_names(self) -> tuple[str, ...]:
        names: list[str] = [objective.response for objective in self.objectives]
        names.extend(constraint.response for constraint in self.reliability)
        return tuple(dict.fromkeys(names))

    def is_trusted(self, fidelity: str) -> bool:
        override = self.fidelity_trust.get(fidelity)
        if override is not None:
            return override
        return self.spec.fidelity_is_trusted(fidelity)

    def model_form_for(self, fidelity: str, response: str) -> ModelFormUncertainty | None:
        for uncertainty in self.spec.model_form:
            if uncertainty.fidelity == fidelity and uncertainty.response == response:
                return uncertainty
        return None


class RobustEvaluator:
    """Evaluator-seam adapter that propagates uncertainty per candidate."""

    def __init__(
        self,
        evaluation: RobustEvaluationSpec,
        nominal: NominalEvaluator,
        *,
        flags_for: FlagsFor | None = None,
    ) -> None:
        self.evaluation = evaluation
        self.nominal = nominal
        self.flags_for = flags_for

    def __call__(self, candidate: Candidate, fidelity: str) -> EvaluationResult:
        base_point = self._base_point(candidate)
        evaluation = self.evaluation

        def evaluate(point: Mapping[str, float]) -> Mapping[str, float]:
            merged = dict(base_point)
            merged.update(point)
            return self.nominal(merged, fidelity)

        try:
            samples = sample_responses(
                evaluation.spec,
                evaluation.plan,
                evaluate,
                evaluation.response_names,
                classes=evaluation.classes,
            )
        except PropagationError as exc:
            return EvaluationResult(
                outputs={},
                flags=PhysicsFlags(converged=False, closure_passed=False, validity_ok=False),
                fidelity=fidelity,
                source=evaluation.source.value,
                detail=f"ROBUST_PROPAGATION_FAILED:{exc}",
            )
        responses = {name: samples.response(name) for name in evaluation.response_names}
        outputs = robust_objective_values(evaluation.objectives, responses)
        trusted = evaluation.is_trusted(fidelity)
        estimates = self._reliability_estimates(responses, fidelity, trusted)
        for estimate in estimates:
            outputs[estimate.name] = estimate.probability_of_failure
        flags = (
            self.flags_for(fidelity)
            if self.flags_for is not None
            else PhysicsFlags(converged=True, closure_passed=True, validity_ok=True)
        )
        return EvaluationResult(
            outputs=outputs,
            flags=flags,
            fidelity=fidelity,
            source=evaluation.source.value,
            cost=float(samples.count),
            signals=self._signals(responses, fidelity, trusted),
            detail=(
                f"robust {samples.count} samples; trusted={trusted}; "
                f"reliability={len(estimates)}"
            ),
        )

    @staticmethod
    def _base_point(candidate: Candidate) -> dict[str, float]:
        values: dict[str, float] = {}
        for item in candidate.assignment:
            if item.point_id is not None:
                continue
            if isinstance(item.value, bool) or not isinstance(item.value, (int, float)):
                continue
            values[str(item.variable_id)] = float(item.value)
        return values

    def _reliability_estimates(
        self,
        responses: Mapping[str, Sequence[float]],
        fidelity: str,
        trusted: bool,
    ) -> tuple[ReliabilityEstimate, ...]:
        evaluation = self.evaluation
        estimates: list[ReliabilityEstimate] = []
        for constraint in evaluation.reliability:
            values = responses[constraint.response]
            applied = constraint
            model_form = evaluation.model_form_for(fidelity, constraint.response)
            if model_form is not None and not trusted:
                penalty = _worst_case_penalty(model_form, constraint.direction)
                applied = replace(constraint, margin_penalty=constraint.margin_penalty + penalty)
            estimates.append(
                estimate_reliability(
                    applied,
                    values,
                    trusted=trusted,
                    basis="aleatory" if trusted else "model-form-bound",
                )
            )
        return tuple(estimates)

    def _signals(
        self,
        responses: Mapping[str, Sequence[float]],
        fidelity: str,
        trusted: bool,
    ) -> Mapping[str, float]:
        evaluation = self.evaluation
        signals: dict[str, float] = {
            "uncertainty_samples": float(evaluation.plan.count),
            "reliability_trusted": 1.0 if trusted else 0.0,
        }
        relative = 0.0
        for objective in evaluation.objectives:
            model_form = evaluation.model_form_for(fidelity, objective.response)
            if model_form is None:
                continue
            moments = model_form.distribution
            values = responses[objective.response]
            mean = sum(values) / len(values)
            scale = max(abs(mean), 1e-9)
            relative = max(relative, moments.std() / scale)
            signals["model_form_mean"] = moments.mean()
            signals["model_form_std"] = moments.std()
        if evaluation.reliability:
            signals["disagreement"] = relative if relative > 0.0 else 1.0 if not trusted else 0.0
            if not trusted:
                signals["constraint_margin"] = 0.0
        elif relative > 0.0:
            signals["disagreement"] = relative
        return signals


def _worst_case_penalty(
    uncertainty: ModelFormUncertainty, direction: LimitDirection
) -> float:
    distribution = uncertainty.distribution
    if direction is LimitDirection.UPPER:
        return max(0.0, distribution.ppf(0.999))
    return max(0.0, -distribution.ppf(0.001))


class RobustSelector:
    """Selector-seam policy: reliability-admissible candidates rank first."""

    def __init__(self, evaluation: RobustEvaluationSpec, *, selection: str = "weighted") -> None:
        if selection not in {"weighted", "pareto"}:
            raise RobustOptimizationError(f"UNKNOWN_ROBUST_SELECTION:{selection}")
        self.evaluation = evaluation
        self.selection = selection

    def __call__(
        self,
        evaluated: Sequence[tuple[Candidate, EvaluationRecord]],
        objectives: Sequence[StudyObjective],
    ) -> Sequence[tuple[Candidate, EvaluationRecord]]:
        valid = [record for record in evaluated if record[1].state == "valid"]
        if not valid:
            return ()
        if self.selection == "pareto":
            return pareto_front(tuple(valid), objectives)
        admissible: list[tuple[Candidate, EvaluationRecord]] = []
        deferred: list[tuple[Candidate, EvaluationRecord]] = []
        for record in valid:
            (admissible if self._reliability_admissible(record[1]) else deferred).append(record)
        ranked: list[tuple[Candidate, EvaluationRecord]] = []
        if admissible:
            ranked.extend(rank_weighted(tuple(admissible), objectives))
        if deferred:
            ranked.extend(rank_weighted(tuple(deferred), objectives))
        return tuple(ranked)

    def _reliability_admissible(self, record: EvaluationRecord) -> bool:
        evaluation = self.evaluation
        if not evaluation.reliability:
            return True
        if not evaluation.is_trusted(record.fidelity):
            return False
        outputs = record.output_dict
        for constraint in evaluation.reliability:
            value = outputs.get(constraint.name)
            if value is None or value > constraint.target_probability_of_failure:
                return False
        return True


def robust_evaluator(
    evaluation: RobustEvaluationSpec,
    nominal: NominalEvaluator,
    *,
    flags_for: FlagsFor | None = None,
) -> RobustEvaluator:
    return RobustEvaluator(evaluation, nominal, flags_for=flags_for)


def robust_study_objectives(
    evaluation: RobustEvaluationSpec,
) -> tuple[StudyObjective, ...]:
    return tuple(objective.as_study_objective() for objective in evaluation.objectives)


def robust_study_constraints(
    evaluation: RobustEvaluationSpec,
) -> tuple[StudyConstraint, ...]:
    return tuple(
        StudyConstraint(
            name=constraint.name,
            bound="upper",
            limit=constraint.target_probability_of_failure,
            unit="probability",
        )
        for constraint in evaluation.reliability
    )


def build_campaign_spec(
    evaluation: RobustEvaluationSpec,
    *,
    campaign_id: str,
    base_revision: str,
    space: Mapping[str, Any],
    generation: GenerationRequest,
    fidelity_ladder: tuple[FidelityImplementation, ...],
    budget: CampaignBudget | None = None,
    quality: QualityPolicy | None = None,
    promote_fraction: float = 0.5,
    min_promote: int = 1,
    diversity: bool = True,
    selection: str = "weighted",
    maturity: float = 0.5,
) -> CampaignSpec:
    """Assemble a campaign spec whose selector applies robust reliability gating."""

    return CampaignSpec(
        campaign_id=campaign_id,
        base_revision=base_revision,
        space=space,
        generation=generation,
        objectives=robust_study_objectives(evaluation),
        constraints=robust_study_constraints(evaluation),
        fidelity_ladder=fidelity_ladder,
        budget=budget if budget is not None else CampaignBudget(),
        quality=quality if quality is not None else QualityPolicy(),
        promote_fraction=promote_fraction,
        min_promote=min_promote,
        diversity=diversity,
        selection=selection,
        maturity=maturity,
        selector=RobustSelector(evaluation, selection=selection),
    )
