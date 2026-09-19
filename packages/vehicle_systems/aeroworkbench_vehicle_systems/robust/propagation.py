"""Uncertainty propagation over an evaluator seam.

Propagation draws bounded, seeded samples, evaluates a caller-supplied
deterministic function at each sample, and reports honest moment estimates.
Nothing is invented: a non-finite or missing response fails closed. Physical
(aleatory) scatter stays separate from model-form discrepancy, which is
reported in its own block with its trust flag and provenance so it can never be
mistaken for physical randomness.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import floor, isfinite, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_rom.contracts import SoftwareIdentity, Validity

from .contracts import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    UncertaintyClass,
    UncertaintySpec,
)
from .errors import PropagationError
from .sampling import SamplingPlan, UncertainSamples, sample_model_form, sample_uncertainty

__all__ = [
    "DEFAULT_PROBABILITIES",
    "MomentEstimates",
    "ModelFormReport",
    "PropagationResult",
    "PropagationSamples",
    "moment_estimates",
    "propagate",
    "quantile",
    "result_digest",
    "sample_responses",
]

DEFAULT_PROBABILITIES = (0.05, 0.5, 0.95)

EvaluateResponses = Callable[[Mapping[str, float]], Mapping[str, float]]


def quantile(values: Sequence[float], probability: float) -> float:
    """Deterministic linear-interpolated quantile (NumPy-compatible default)."""
    if not values:
        raise PropagationError("QUANTILE_NEEDS_VALUES")
    if not isfinite(probability) or probability < 0.0 or probability > 1.0:
        raise PropagationError("QUANTILE_PROBABILITY_DOMAIN")
    ordered = sorted(values)
    size = len(ordered)
    if size == 1:
        return ordered[0]
    position = (size - 1) * probability
    lower = int(floor(position))
    upper = min(lower + 1, size - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


@dataclass(frozen=True, slots=True)
class MomentEstimates:
    """Honest statistics of a finite response sample."""

    count: int
    mean: float
    variance: float
    std: float
    minimum: float
    maximum: float
    standard_error: float
    coefficient_of_variation: float | None
    quantiles: tuple[tuple[float, float], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean": self.mean,
            "variance": self.variance,
            "std": self.std,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "standardError": self.standard_error,
            "coefficientOfVariation": self.coefficient_of_variation,
            "quantiles": [[level, value] for level, value in self.quantiles],
        }


def moment_estimates(
    values: Sequence[float], probabilities: Sequence[float] = DEFAULT_PROBABILITIES
) -> MomentEstimates:
    """Sample mean, unbiased variance, spread, and quantiles."""
    if not values:
        raise PropagationError("MOMENTS_NEED_VALUES")
    for value in values:
        if not isfinite(value):
            raise PropagationError("MOMENTS_NEED_FINITE_VALUES")
    count = len(values)
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1) if count > 1 else 0.0
    std = sqrt(variance)
    standard_error = std / sqrt(count) if count > 0 else 0.0
    coefficient = None if mean == 0.0 else std / abs(mean)
    return MomentEstimates(
        count=count,
        mean=mean,
        variance=variance,
        std=std,
        minimum=min(values),
        maximum=max(values),
        standard_error=standard_error,
        coefficient_of_variation=coefficient,
        quantiles=tuple((level, quantile(values, level)) for level in probabilities),
    )


@dataclass(frozen=True, slots=True)
class ModelFormReport:
    """Model-form discrepancy for one fidelity, kept apart from physical scatter."""

    fidelity: str
    response: str
    trusted: bool
    uncertainty_class: str
    provenance: dict[str, Any]
    moments: MomentEstimates

    def as_dict(self) -> dict[str, Any]:
        return {
            "fidelity": self.fidelity,
            "response": self.response,
            "trusted": self.trusted,
            "uncertaintyClass": self.uncertainty_class,
            "provenance": dict(self.provenance),
            "moments": self.moments.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class PropagationResult:
    """Evidence from one uncertainty-propagation run."""

    spec_id: str
    spec_digest: str
    plan_id: str
    method: str
    seed: int
    count: int
    fidelity: str
    source: str
    included_classes: tuple[str, ...]
    output_names: tuple[str, ...]
    moments: tuple[tuple[str, MomentEstimates], ...]
    model_form: tuple[ModelFormReport, ...]
    samples_digest: str
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity
    detail: str = ""

    def moment_for(self, name: str) -> MomentEstimates:
        for candidate, estimate in self.moments:
            if candidate == name:
                return estimate
        raise PropagationError(f"UNKNOWN_PROPAGATION_OUTPUT:{name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "specDigest": self.spec_digest,
            "planId": self.plan_id,
            "method": self.method,
            "seed": self.seed,
            "count": self.count,
            "fidelity": self.fidelity,
            "source": self.source,
            "includedClasses": list(self.included_classes),
            "outputNames": list(self.output_names),
            "moments": {name: estimate.as_dict() for name, estimate in self.moments},
            "modelForm": [report.as_dict() for report in self.model_form],
            "samplesDigest": self.samples_digest,
            "validity": self.validity.canonical(),
            "sourceKind": self.provenance.source.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
            "detail": self.detail,
        }


def _reduced_spec(
    spec: UncertaintySpec, classes: tuple[UncertaintyClass, ...] | None
) -> UncertaintySpec:
    if classes is None:
        return spec
    selected = tuple(
        variable
        for variable in spec.variables
        if variable.uncertainty_class in classes
    )
    if not selected:
        raise PropagationError("NO_VARIABLES_FOR_REQUESTED_CLASSES")
    names = {variable.name for variable in selected}
    correlations = tuple(
        correlation
        for correlation in spec.correlations
        if correlation.name_a in names and correlation.name_b in names
    )
    return UncertaintySpec(
        spec_id=f"{spec.spec_id}:{'|'.join(cls.value for cls in classes)}",
        variables=selected,
        correlations=correlations,
        software=spec.software,
    )


def _model_form_reports(
    spec: UncertaintySpec,
    plan: SamplingPlan,
    fidelity: str,
) -> tuple[ModelFormReport, ...]:
    reports: list[ModelFormReport] = []
    for uncertainty in spec.model_form:
        if uncertainty.fidelity != fidelity:
            continue
        discrepancy = sample_model_form(spec, plan, fidelity)
        if discrepancy is None:  # pragma: no cover - defensive
            continue
        reports.append(
            ModelFormReport(
                fidelity=uncertainty.fidelity,
                response=uncertainty.response,
                trusted=uncertainty.trusted,
                uncertainty_class=uncertainty.uncertainty_class.value,
                provenance=uncertainty.provenance.canonical_payload(),
                moments=moment_estimates(discrepancy),
            )
        )
    return tuple(reports)


@dataclass(frozen=True, slots=True)
class PropagationSamples:
    """Raw per-sample responses, kept bounded and content-addressed."""

    spec_id: str
    plan_id: str
    method: str
    seed: int
    count: int
    included_classes: tuple[str, ...]
    output_names: tuple[str, ...]
    responses: tuple[tuple[str, tuple[float, ...]], ...]
    samples_digest: str

    def response(self, name: str) -> tuple[float, ...]:
        for candidate, values in self.responses:
            if candidate == name:
                return values
        raise PropagationError(f"UNKNOWN_PROPAGATION_OUTPUT:{name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "planId": self.plan_id,
            "method": self.method,
            "seed": self.seed,
            "count": self.count,
            "includedClasses": list(self.included_classes),
            "outputNames": list(self.output_names),
            "samplesDigest": self.samples_digest,
        }


def sample_responses(
    spec: UncertaintySpec,
    plan: SamplingPlan,
    evaluate: EvaluateResponses,
    output_names: Sequence[str],
    *,
    classes: tuple[UncertaintyClass, ...] | None = None,
) -> PropagationSamples:
    """Evaluate ``evaluate`` once per bounded sample and return raw responses.

    The evaluator receives a complete point mapping built from the sampled
    values (unselected variables stay at their distribution mean). Every
    requested output must be present and finite for every sample; otherwise the
    run fails closed with an explicit reason.
    """
    if not output_names:
        raise PropagationError("PROPAGATION_NEEDS_OUTPUT_NAMES")
    reduced = _reduced_spec(spec, classes)
    samples: UncertainSamples = sample_uncertainty(reduced, plan)
    included = (
        tuple(variable.uncertainty_class.value for variable in reduced.variables)
        if classes is None
        else tuple(cls.value for cls in classes)
    )
    means = {variable.name: variable.distribution.mean() for variable in spec.variables}
    rows: dict[str, list[float]] = {name: [] for name in output_names}
    for index, row in enumerate(samples.rows):
        point = dict(means)
        point.update(dict(zip(samples.names, row, strict=True)))
        try:
            response = evaluate(point)
        except Exception as exc:  # noqa: BLE001 - evaluator failure fails closed
            raise PropagationError(
                f"PROPAGATION_EVALUATION_ERROR:{index}:{type(exc).__name__}:{exc}"
            ) from exc
        for name in output_names:
            value = response.get(name)
            if value is None:
                raise PropagationError(f"PROPAGATION_MISSING_OUTPUT:{index}:{name}")
            if not isfinite(value):
                raise PropagationError(f"PROPAGATION_NONFINITE_OUTPUT:{index}:{name}")
            rows[name].append(float(value))
    return PropagationSamples(
        spec_id=spec.spec_id,
        plan_id=plan.plan_id,
        method=plan.method.value,
        seed=plan.seed,
        count=plan.count,
        included_classes=included,
        output_names=tuple(output_names),
        responses=tuple((name, tuple(rows[name])) for name in output_names),
        samples_digest=samples.digest(),
    )


def propagate(
    spec: UncertaintySpec,
    plan: SamplingPlan,
    evaluate: EvaluateResponses,
    output_names: Sequence[str],
    *,
    fidelity: str = "analytical",
    source: ResultSource = ResultSource.SURROGATE,
    classes: tuple[UncertaintyClass, ...] | None = None,
) -> PropagationResult:
    """Propagate declared uncertainty through ``evaluate`` with bounded sampling.

    Physical response moments are computed from the sampled responses; model
    form discrepancy is reported separately. Every requested output must be
    present and finite for every sample, otherwise the run fails closed.
    """
    raw = sample_responses(spec, plan, evaluate, output_names, classes=classes)
    reduced = _reduced_spec(spec, classes)
    included = raw.included_classes
    moments = tuple(
        (name, moment_estimates(raw.response(name))) for name in raw.output_names
    )
    model_form = _model_form_reports(spec, plan, fidelity)
    samples_digest = raw.samples_digest
    inputs = {
        "spec": spec.digest(),
        "plan": plan.canonical_payload(),
        "samples": samples_digest,
        "classes": list(included),
    }
    provenance = Provenance.from_inputs(
        inputs=inputs,
        source=source,
        model=SOFTWARE_NAME,
        model_version=SOFTWARE_VERSION,
    )
    validity = Validity(
        passed=True,
        checks={
            "samples_within_bound": plan.count <= plan.max_count,
            "responses_finite": True,
            "model_form_separate": all(
                report.uncertainty_class == UncertaintyClass.MODEL_FORM.value
                for report in model_form
            ),
        },
        detail=f"{plan.count} samples over {len(reduced.variables)} uncertain inputs",
    )
    return PropagationResult(
        spec_id=spec.spec_id,
        spec_digest=spec.digest(),
        plan_id=plan.plan_id,
        method=plan.method.value,
        seed=plan.seed,
        count=plan.count,
        fidelity=fidelity,
        source=provenance.source.value,
        included_classes=included,
        output_names=tuple(output_names),
        moments=moments,
        model_form=model_form,
        samples_digest=samples_digest,
        validity=validity,
        provenance=provenance,
        software=spec.software,
        detail=(
            f"propagated {plan.count} {plan.method.value} samples; "
            f"model-form blocks={len(model_form)}"
        ),
    )


def result_digest(result: PropagationResult) -> str:
    """Stable digest over a propagation result's evidence."""

    return content_digest(result.as_dict())
