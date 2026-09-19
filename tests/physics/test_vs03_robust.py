"""VS 03: uncertainty propagation, reliability constraints, robust optimization.

All fixtures are tiny and deterministic: distributions, sampling plans, and
hand-computable statistics. No solver runs; the campaign integration uses a
closed-form nominal evaluator so every assertion is a pure contract check.
"""

from __future__ import annotations

import json
from math import exp, sqrt
from pathlib import Path

import pytest
from aeroworkbench_optimization import (
    CampaignState,
    Candidate,
    CandidateProvenance,
    EvaluationRecord,
    FidelityImplementation,
    GenerationRequest,
    run_campaign,
)
from aeroworkbench_vehicle_systems.robust import (
    SOFTWARE_NAME,
    CorrelationSpec,
    Distribution,
    DistributionKind,
    LimitDirection,
    ModelFormUncertainty,
    PropagationError,
    ReliabilityConstraint,
    ReliabilityError,
    ReliabilityMethod,
    RobustEvaluationSpec,
    RobustObjective,
    RobustObjectiveKind,
    RobustSelector,
    SamplingError,
    SamplingMethod,
    SamplingPlan,
    UncertaintyClass,
    UncertaintySource,
    UncertaintySpec,
    UncertainVariable,
    VariableProvenance,
    build_campaign_spec,
    calibration_model_form,
    calibration_variable,
    estimate_reliability,
    evaluate_robust_objective,
    first_order_reliability,
    material_scatter_variable,
    normal_cdf,
    normal_inv_cdf,
    propagate,
    robust_evaluator,
    robust_objective_values,
    sample_responses,
    sample_uncertainty,
    tolerance_variable,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "vehicle_systems"
    / "robust"
    / "uncertainty_spec.json"
)


def _provenance(
    source: UncertaintySource = UncertaintySource.MANUFACTURING_TOLERANCE,
    reference: str = "fixture-ref",
) -> VariableProvenance:
    return VariableProvenance(source, reference)


def _normal(
    name: str,
    mean: float,
    std: float,
    *,
    unit: str = "m",
    uncertainty_class: UncertaintyClass = UncertaintyClass.ALEATORY,
    source: UncertaintySource = UncertaintySource.MANUFACTURING_TOLERANCE,
) -> UncertainVariable:
    return UncertainVariable(
        name=name,
        unit=unit,
        distribution=Distribution(DistributionKind.NORMAL, (mean, std)),
        provenance=_provenance(source),
        uncertainty_class=uncertainty_class,
    )


def _spec(
    variables: tuple[UncertainVariable, ...],
    correlations: tuple[CorrelationSpec, ...] = (),
    model_form: tuple[ModelFormUncertainty, ...] = (),
) -> UncertaintySpec:
    return UncertaintySpec("vs03", variables, correlations, model_form)


def _candidate(name: str) -> Candidate:
    return Candidate(
        candidate_hash=name,
        parent_hash=None,
        space_id="synthetic",
        index=0,
        strategy="random",
        seed=0,
        preflight_state="valid",
        preflight_reasons=(),
        active_variables=(),
        assignment=(),
        mutations=(),
        normalized=(),
        state={},
        flat=None,
        provenance=CandidateProvenance("synthetic", None, "random", 0, 0, None, "cfg"),
    )


def _record(
    name: str,
    fidelity: str,
    outputs: dict[str, float],
    state: str = "valid",
) -> EvaluationRecord:
    return EvaluationRecord(
        candidate_hash=name,
        fidelity=fidelity,
        state=state,
        reasons=() if state == "valid" else ("invalid",),
        outputs=tuple(sorted(outputs.items())),
        cost=0.0,
        source="test",
        geometry_hash=None,
        signal_digest="",
        detail="",
    )


def test_vs03_distribution_moments_and_inverse_cdf() -> None:
    normal = Distribution(DistributionKind.NORMAL, (10.0, 2.0))
    assert normal.mean() == pytest.approx(10.0)
    assert normal.std() == pytest.approx(2.0)
    uniform = Distribution(DistributionKind.UNIFORM, (0.0, 1.0))
    assert uniform.mean() == pytest.approx(0.5)
    assert uniform.variance() == pytest.approx(1.0 / 12.0)
    triangular = Distribution(DistributionKind.TRIANGULAR, (0.0, 1.0, 3.0))
    assert triangular.mean() == pytest.approx(4.0 / 3.0)
    lognormal = Distribution(DistributionKind.LOGNORMAL, (0.0, 1.0))
    assert lognormal.mean() == pytest.approx(exp(0.5))
    assert normal_cdf(0.0) == pytest.approx(0.5)
    assert normal_inv_cdf(0.5) == pytest.approx(0.0, abs=1e-9)
    assert normal_inv_cdf(normal_cdf(1.0)) == pytest.approx(1.0, abs=1e-6)


def test_vs03_sampling_reproducible_and_seed_sensitive() -> None:
    spec = _spec((_normal("x", 0.0, 0.1),))
    plan = SamplingPlan("p", SamplingMethod.MONTE_CARLO, 128, seed=3)
    first = sample_uncertainty(spec, plan)
    second = sample_uncertainty(spec, plan)
    assert first.rows == second.rows
    assert first.digest() == second.digest()
    assert first.uncertainty_classes == ("aleatory",)
    other = sample_uncertainty(spec, SamplingPlan("p", SamplingMethod.MONTE_CARLO, 128, seed=4))
    assert other.digest() != first.digest()


def test_vs03_propagation_reproducible_and_provenance_complete() -> None:
    spec = _spec((_normal("x", 0.0, 0.1),))
    plan = SamplingPlan("p", SamplingMethod.LATIN_HYPERCUBE, 512, seed=11)
    evaluate = lambda point: {"y": point["x"] + 2.0}  # noqa: E731
    first = propagate(spec, plan, evaluate, ["y"])
    second = propagate(spec, plan, evaluate, ["y"])
    assert first.moment_for("y").mean == pytest.approx(2.0, abs=0.02)
    assert first.moment_for("y").std == pytest.approx(0.1, abs=0.02)
    assert first.as_dict()["moments"] == second.as_dict()["moments"]
    assert first.provenance.inputs_hash == second.provenance.inputs_hash
    assert len(first.provenance.inputs_hash) == 64
    assert first.source == "surrogate"
    assert first.validity.passed
    assert first.software.name == SOFTWARE_NAME
    assert first.count == 512


def test_vs03_correlated_inputs_propagate_hand_computable() -> None:
    spec = _spec(
        (_normal("x", 0.0, 1.0), _normal("y", 0.0, 1.0)),
        (CorrelationSpec("x", "y", 0.5),),
    )
    plan = SamplingPlan("corr", SamplingMethod.LATIN_HYPERCUBE, 40000, seed=5)
    samples = sample_uncertainty(spec, plan)
    xs = samples.column("x")
    ys = samples.column("y")
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys, strict=True)) / count
    std_x = sqrt(sum((a - mean_x) ** 2 for a in xs) / count)
    std_y = sqrt(sum((b - mean_y) ** 2 for b in ys) / count)
    assert covariance / (std_x * std_y) == pytest.approx(0.5, abs=0.03)
    result = propagate(spec, plan, lambda point: {"s": point["x"] + point["y"]}, ["s"])
    assert result.moment_for("s").std == pytest.approx(sqrt(3.0), abs=0.03)


def test_vs03_first_order_reliability_hand_computable() -> None:
    covariance = {"x": {"x": 1.0, "y": 0.5}, "y": {"x": 0.5, "y": 1.0}}
    gradient = {"x": 1.0, "y": 1.0}
    mean = {"x": 0.0, "y": 0.0}
    passing = ReliabilityConstraint("pf", "s", LimitDirection.UPPER, 3.0, 0.05)
    estimate = first_order_reliability(
        passing, mean, gradient, covariance, trusted=True
    )
    beta = 3.0 / sqrt(3.0)
    assert estimate.reliability_index == pytest.approx(beta, rel=1e-9)
    assert estimate.probability_of_failure == pytest.approx(normal_cdf(-beta), rel=1e-9)
    assert estimate.passed is True
    strict = ReliabilityConstraint("pf", "s", LimitDirection.UPPER, 3.0, 0.01)
    assert first_order_reliability(strict, mean, gradient, covariance, trusted=True).passed is False


def test_vs03_nominally_feasible_low_yield_candidate_rejected() -> None:
    constraint = ReliabilityConstraint("pf", "r", LimitDirection.UPPER, 10.0, 0.05)
    plan = SamplingPlan("mc", SamplingMethod.MONTE_CARLO, 20000, seed=13)
    high_scatter = _spec((_normal("r", 9.5, 1.0),))
    raw = sample_responses(
        high_scatter, plan, lambda point: {"r": point["r"]}, ["r"]
    )
    values = raw.response("r")
    assert sum(values) / len(values) < 10.0
    rejected = estimate_reliability(constraint, values, trusted=True)
    assert rejected.passed is False
    assert rejected.probability_of_failure > 0.05
    low_scatter = _spec((_normal("r", 9.5, 0.05),))
    raw_low = sample_responses(low_scatter, plan, lambda point: {"r": point["r"]}, ["r"])
    accepted = estimate_reliability(constraint, raw_low.response("r"), trusted=True)
    assert accepted.passed is True


def test_vs03_robust_objectives_hand_computable() -> None:
    values = (1.0, 2.0, 3.0, 4.0, 5.0)
    mean = RobustObjective("m", "r", RobustObjectiveKind.EXPECTED_VALUE)
    variance = RobustObjective("v", "r", RobustObjectiveKind.VARIANCE)
    worst = RobustObjective("w", "r", RobustObjectiveKind.WORST_CASE, "minimize")
    best = RobustObjective("b", "r", RobustObjectiveKind.WORST_CASE, "maximize")
    cvar = RobustObjective("c", "r", RobustObjectiveKind.CVAR, "minimize", alpha=0.4)
    percentile = RobustObjective("p", "r", RobustObjectiveKind.PERCENTILE, "minimize", alpha=0.5)
    mean_risk = RobustObjective(
        "mr", "r", RobustObjectiveKind.MEAN_RISK, "minimize", risk_penalty=1.0
    )
    assert evaluate_robust_objective(mean, values) == pytest.approx(3.0)
    assert evaluate_robust_objective(variance, values) == pytest.approx(2.5)
    assert evaluate_robust_objective(worst, values) == pytest.approx(5.0)
    assert evaluate_robust_objective(best, values) == pytest.approx(1.0)
    assert evaluate_robust_objective(cvar, values) == pytest.approx(4.5)
    assert evaluate_robust_objective(percentile, values) == pytest.approx(3.0)
    assert evaluate_robust_objective(mean_risk, values) == pytest.approx(3.0 + sqrt(2.5))
    assert robust_objective_values((mean, variance), {"r": values}) == {
        "m": pytest.approx(3.0),
        "v": pytest.approx(2.5),
    }


def test_vs03_reliability_constraints_participate_in_selection() -> None:
    evaluation = RobustEvaluationSpec(
        spec=_spec((_normal("tolerance", 0.0, 0.05),)),
        plan=SamplingPlan("p", SamplingMethod.MONTE_CARLO, 64, seed=1),
        objectives=(
            RobustObjective("obj", "thrust", RobustObjectiveKind.EXPECTED_VALUE, "minimize"),
        ),
        reliability=(ReliabilityConstraint("pf", "thrust", LimitDirection.UPPER, 1.0, 0.5),),
        fidelity_trust={"analytical": False, "native": True},
    )
    selector = RobustSelector(evaluation, selection="weighted")
    records = [
        (_candidate("a"), _record("a", "native", {"obj": 1.0, "pf": 0.0})),
        (_candidate("b"), _record("b", "native", {"obj": 0.2, "pf": 0.9})),
        (_candidate("c"), _record("c", "analytical", {"obj": 0.5, "pf": 0.0})),
    ]
    from aeroworkbench_optimization import StudyObjective

    objectives = (StudyObjective("obj", "minimize"),)
    ranked = list(selector(records, objectives))
    assert [candidate.candidate_hash for candidate, _ in ranked] == ["a", "b", "c"]
    assert ranked[0][0].candidate_hash == "a"
    without_reliability = RobustEvaluationSpec(
        spec=evaluation.spec,
        plan=evaluation.plan,
        objectives=evaluation.objectives,
    )
    plain = list(RobustSelector(without_reliability)(records, objectives))
    assert plain[0][0].candidate_hash == "b"


def test_vs03_model_form_uncertainty_visible_and_distinct() -> None:
    model_form = ModelFormUncertainty(
        "surrogate",
        "y",
        Distribution(DistributionKind.NORMAL, (0.0, 0.03)),
        _provenance(UncertaintySource.AERODYNAMIC_MODEL_DISCREPANCY, "rom-vs-native"),
        trusted=False,
    )
    spec = _spec((_normal("x", 0.0, 0.1),), model_form=(model_form,))
    plan = SamplingPlan("mf", SamplingMethod.MONTE_CARLO, 256, seed=2)
    result = propagate(
        spec, plan, lambda point: {"y": point["x"]}, ["y"], fidelity="surrogate"
    )
    assert result.included_classes == ("aleatory",)
    assert len(result.model_form) == 1
    report = result.model_form[0]
    assert report.uncertainty_class == UncertaintyClass.MODEL_FORM.value
    assert report.trusted is False
    assert report.provenance["source"] == UncertaintySource.AERODYNAMIC_MODEL_DISCREPANCY.value
    assert result.moment_for("y").std == pytest.approx(0.1, abs=0.02)
    assert spec.fidelity_is_trusted("surrogate") is False


def test_vs03_untrusted_reliability_is_inadmissible() -> None:
    constraint = ReliabilityConstraint("pf", "r", LimitDirection.UPPER, 10.0, 0.5)
    estimate = estimate_reliability(
        constraint, [1.0, 2.0, 3.0], trusted=False, basis="model-form-bound"
    )
    assert estimate.admissible is False
    assert estimate.passed is False
    assert estimate.trusted is False
    assert estimate.basis == "model-form-bound"
    with pytest.raises(ReliabilityError):
        estimate_reliability(
            ReliabilityConstraint(
                "pf", "r", LimitDirection.UPPER, 10.0, 0.5,
                method=ReliabilityMethod.FIRST_ORDER,
            ),
            [1.0, 2.0],
            trusted=True,
        )


def test_vs03_fail_closed_on_nonfinite_missing_and_bounds() -> None:
    spec = _spec((_normal("x", 0.0, 0.1),))
    plan = SamplingPlan("p", SamplingMethod.MONTE_CARLO, 16, seed=0)
    with pytest.raises(PropagationError):
        propagate(spec, plan, lambda point: {"y": float("nan")}, ["y"])
    with pytest.raises(PropagationError):
        propagate(spec, plan, lambda point: {"other": 1.0}, ["y"])
    with pytest.raises(SamplingError):
        SamplingPlan("p", SamplingMethod.MONTE_CARLO, 5, seed=0, max_count=4)
    bad = _spec(
        (_normal("x", 0.0, 1.0), _normal("y", 0.0, 1.0), _normal("z", 0.0, 1.0)),
        (
            CorrelationSpec("x", "y", 0.9),
            CorrelationSpec("x", "z", -0.9),
            CorrelationSpec("y", "z", 0.9),
        ),
    )
    with pytest.raises(SamplingError):
        sample_uncertainty(bad, SamplingPlan("p", SamplingMethod.MONTE_CARLO, 8, seed=0))


def test_vs03_evidence_sources_convert_with_documented_assumptions() -> None:
    tolerance = tolerance_variable("wall", "m", 0.01, 0.002, distribution="uniform")
    assert tolerance.distribution.mean() == pytest.approx(0.01)
    assert tolerance.distribution.variance() == pytest.approx((0.004**2) / 12.0)
    assert tolerance.uncertainty_class is UncertaintyClass.ALEATORY
    assert tolerance.provenance.source is UncertaintySource.MANUFACTURING_TOLERANCE
    material = material_scatter_variable("E", "Pa", 70e9, 0.05)
    assert material.distribution.mean() == pytest.approx(70e9, rel=1e-9)
    assert material.distribution.std() / 70e9 == pytest.approx(0.05, rel=1e-6)
    assert material.provenance.source is UncertaintySource.MATERIAL_SCATTER
    calibrated = calibration_variable("cd0", "dimensionless", 0.02, 0.001)
    assert calibrated.uncertainty_class is UncertaintyClass.EPISTEMIC
    model_form = calibration_model_form("surrogate", "drag", 0.0, 0.01)
    assert model_form.trusted is False
    assert model_form.provenance.source is UncertaintySource.EXPERIMENT_CALIBRATION


def test_vs03_fixture_spec_round_trips_and_stays_hashable() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spec = UncertaintySpec.from_payload(payload)
    rebuilt = UncertaintySpec.from_payload(spec.canonical_payload())
    assert spec.digest() == rebuilt.digest()
    assert len(spec.variables) == 2
    assert len(spec.correlations) == 1
    assert spec.fidelity_is_trusted("surrogate") is False
    model_form = spec.model_form_for("surrogate")
    assert model_form is not None
    assert model_form.response == "thrust"


def test_vs03_campaign_integration_multi_fidelity_and_trust() -> None:
    uncertainty = _spec((_normal("tolerance", 0.0, 0.05),))
    evaluation = RobustEvaluationSpec(
        spec=uncertainty,
        plan=SamplingPlan("camp", SamplingMethod.MONTE_CARLO, 400, seed=17),
        objectives=(
            RobustObjective(
                "thrust_mean", "thrust", RobustObjectiveKind.EXPECTED_VALUE, "maximize"
            ),
        ),
        reliability=(
            ReliabilityConstraint("thrust_pf", "thrust", LimitDirection.LOWER, 0.5, 0.02),
        ),
        fidelity_trust={"analytical": False, "native": True},
    )
    space = {
        "id": "vs03-space",
        "variables": [
            {
                "id": "design",
                "kind": "continuous",
                "domain": {"kind": "continuous", "lower": 0.0, "upper": 1.0},
                "baseValue": 0.5,
                "bindings": [{"target": "parameter", "path": "p.design"}],
            }
        ],
    }
    spec = build_campaign_spec(
        evaluation,
        campaign_id="vs03-campaign",
        base_revision="rev-base",
        space=space,
        generation=GenerationRequest("factorial", levels=5, budget=50),
        fidelity_ladder=(
            FidelityImplementation("analytical", 0, 1.0),
            FidelityImplementation("native", 1, 4.0),
        ),
        promote_fraction=1.0,
        min_promote=1,
    )
    evaluator = robust_evaluator(
        evaluation, lambda point, fidelity: {"thrust": point["design"] - point["tolerance"]}
    )
    record = run_campaign(spec, evaluator, evaluator_identity="vs03")
    assert record.state is CampaignState.COMPLETED
    analytical = [item for item in record.evaluations if item.fidelity == "analytical"]
    native = [item for item in record.evaluations if item.fidelity == "native"]
    assert analytical
    assert native
    assert all(item.signal_dict.get("reliability_trusted") == 0.0 for item in analytical)
    assert any(item.signal_dict.get("reliability_trusted") == 1.0 for item in native)
    assert all("thrust_pf" in item.output_dict for item in native)
    assert record.best is not None
    best = record.candidates[record.best]
    assert best.fidelity == "native"
    assert best.feasible is True
    assert best.outputs["thrust_pf"] <= 0.02
