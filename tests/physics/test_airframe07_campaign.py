"""AIRFRAME 07: campaign evaluation, mutation policy, replay, and resume."""

from __future__ import annotations

import json

import pytest
from aeroworkbench_airframe.campaign import (
    AirframeCampaignReceipt,
    AirframeCampaignSession,
    AirframeMutationPolicy,
    MutationStage,
    build_airframe_campaign_spec,
)
from aeroworkbench_airframe.synthesis import compile_requirements_payload, generate_fixed_wing_seeds
from aeroworkbench_optimization import (
    CampaignBudget,
    Candidate,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    PhysicsFlags,
    StudyObjective,
)


def _seed():
    compiled = compile_requirements_payload(
        {
            "requirements": [
                {"id": "payload", "kind": "mission", "metric": "payload_mass", "operator": "at_least", "value": 120.0, "unit": "kg"},  # noqa: E501
                {"id": "stall", "kind": "performance", "metric": "stall_speed", "operator": "at_most", "value": 30.0, "unit": "m/s"},  # noqa: E501
                {"id": "cruise", "kind": "performance", "metric": "cruise_speed", "operator": "at_least", "value": 65.0, "unit": "m/s"},  # noqa: E501
                {"id": "range", "kind": "mission", "metric": "range", "operator": "at_least", "value": 300.0, "unit": "km"},  # noqa: E501
            ]
        }
    )
    return generate_fixed_wing_seeds(compiled, seed_count=1)[0]


def _evaluator(candidate, fidelity: str) -> EvaluationResult:
    values = {
        item.variable_id: float(item.value)
        for item in candidate.assignment
        if item.point_id is None and isinstance(item.value, (int, float))
    }
    span = values["wing_span"]
    area = values["wing_area"]
    mass = values["max_takeoff_mass"]
    return EvaluationResult(
        outputs={"score": mass / area, "span": span},
        flags=PhysicsFlags(converged=True, closure_passed=True, validity_ok=True),
        fidelity=fidelity,
        source="analytical",
        cost=0.0,
        signals={"constraint_margin": 0.5},
    )


def test_airframe07_mutation_policy_invalidates_downstream_stages() -> None:
    policy = AirframeMutationPolicy.default()
    decision = policy.evaluate({"wing_span": (10.0, 10.5)})
    assert decision.accepted
    assert decision.earliest_stage is MutationStage.GEOMETRY
    assert decision.invalidated_stages == (
        MutationStage.GEOMETRY,
        MutationStage.MASS,
        MutationStage.AERO,
        MutationStage.TRIM,
        MutationStage.VERIFICATION,
    )
    unknown = policy.evaluate({"magic_knob": (0.0, 1.0)})
    assert not unknown.accepted
    assert unknown.reason == "UNKNOWN_AIRFRAME_MUTATION:magic_knob"


def test_airframe07_campaign_replays_and_resume_reuses_exact_results() -> None:
    spec = build_airframe_campaign_spec(
        "airframe07",
        _seed(),
        generation=GenerationRequest("lhs", budget=4, seed=19),
        objectives=(StudyObjective("score", "minimize"),),
        fidelity_ladder=(FidelityImplementation("analytical", 0, 0.0),),
        budget=CampaignBudget(max_evaluations=4),
    )
    session = AirframeCampaignSession(
        spec,
        _evaluator,
        evaluator_identity="airframe07-analytical-v1",
        mutation_policy=AirframeMutationPolicy.default(),
    )
    first = session.run()
    assert first.record.best is not None
    assert first.record.metrics["evaluations"] == 4
    assert first.mutation_decisions
    resumed = session.resume(first)
    assert resumed.record.metrics["evaluations"] == 0
    assert resumed.record.metrics["cache_hits"] == 4
    rebuilt = AirframeCampaignReceipt.from_dict(
        json.loads(json.dumps(first.as_dict()))
    )
    assert rebuilt.as_dict() == first.as_dict()
    assert rebuilt.digest == first.digest


def test_airframe07_resume_rejects_policy_or_evaluator_drift() -> None:
    spec = build_airframe_campaign_spec(
        "airframe07-drift",
        _seed(),
        generation=GenerationRequest("lhs", budget=1, seed=7),
        objectives=(StudyObjective("score", "minimize"),),
        fidelity_ladder=(FidelityImplementation("analytical", 0, 0.0),),
    )
    session = AirframeCampaignSession(
        spec,
        _evaluator,
        evaluator_identity="stable-evaluator",
        mutation_policy=AirframeMutationPolicy.default(),
    )
    receipt = session.run()
    incompatible = AirframeCampaignSession(
        spec,
        _evaluator,
        evaluator_identity="changed-evaluator",
        mutation_policy=AirframeMutationPolicy.default(),
    )
    with pytest.raises(ValueError, match="EVALUATOR_IDENTITY_MISMATCH"):
        incompatible.resume(receipt)


def test_airframe07_uses_generic_generation_and_declared_fidelity_ladder() -> None:
    calls: list[tuple[str, str]] = []

    def evaluator(candidate: Candidate, fidelity: str) -> EvaluationResult:
        calls.append((candidate.candidate_hash, fidelity))
        return EvaluationResult(
            outputs={"score": float(candidate.index)},
            flags=PhysicsFlags(converged=True, closure_passed=True, validity_ok=True),
            fidelity=fidelity,
            signals={"disagreement": 1.0} if fidelity == "analytical" else {},
        )

    spec = build_airframe_campaign_spec(
        "airframe07-generic",
        _seed(),
        generation=GenerationRequest("lhs", count=4, budget=4, seed=19),
        objectives=(StudyObjective("score", "minimize"),),
        fidelity_ladder=(
            FidelityImplementation("analytical", 0, 0.0),
            FidelityImplementation("native", 1, 1.0),
        ),
        budget=CampaignBudget(max_evaluations=8),
    )
    receipt = AirframeCampaignSession(
        spec,
        evaluator,
        evaluator_identity="generic-v1",
        mutation_policy=AirframeMutationPolicy.default(),
    ).run()

    assert len({candidate_hash for candidate_hash, _ in calls}) == 4
    assert {fidelity for _, fidelity in calls} == {"analytical", "native"}
    assert receipt.generic_record is not None
    assert receipt.generic_record.pareto


def test_airframe07_invalid_geometry_is_rejected_before_native_evaluation() -> None:
    calls: list[str] = []
    parents: list[object | None] = []

    class Receipt:
        def __init__(self, valid: bool) -> None:
            self.validity_state = "valid" if valid else "invalid"
            self.shape_hash = "shape" if valid else ""
            self.invalid_reasons = () if valid else ("SHAPE_INVALID",)

    def regenerate(candidate: Candidate, parent: object | None) -> object:
        parents.append(parent)
        return Receipt(candidate.index != 1)

    def evaluator(candidate: Candidate, fidelity: str) -> EvaluationResult:
        calls.append(fidelity)
        return EvaluationResult(
            outputs={"score": 1.0},
            flags=PhysicsFlags(converged=True, closure_passed=True, validity_ok=True),
            fidelity=fidelity,
        )

    spec = build_airframe_campaign_spec(
        "airframe07-geometry",
        _seed(),
        generation=GenerationRequest("lhs", count=3, budget=3, seed=3),
        objectives=(StudyObjective("score", "minimize"),),
        fidelity_ladder=(
            FidelityImplementation("analytical", 0, 0.0),
            FidelityImplementation("native", 1, 1.0),
        ),
        budget=CampaignBudget(max_evaluations=6),
    )
    receipt = AirframeCampaignSession(
        spec,
        evaluator,
        evaluator_identity="geometry-v1",
        mutation_policy=AirframeMutationPolicy.default(),
        geometry_regenerator=regenerate,
    ).run()

    assert calls.count("native") < 2
    assert len(parents) == 3
    assert parents[0] is None
    assert all(parent is not None for parent in parents[1:])
    assert any(
        "GEOMETRY_INVALID" in getattr(result, "detail", "")
        for result in receipt.record.results
    )


def test_airframe07_compiled_downstream_requirement_makes_violation_invalid() -> None:
    compiled = compile_requirements_payload(
        {
            "requirements": [
                {
                    "id": "payload",
                    "kind": "mission",
                    "metric": "payload_mass",
                    "operator": "at_least",
                    "value": 120.0,
                    "unit": "kg",
                },
                {
                    "id": "stall",
                    "kind": "performance",
                    "metric": "stall_speed",
                    "operator": "at_most",
                    "value": 30.0,
                    "unit": "m/s",
                },
                {
                    "id": "cruise",
                    "kind": "performance",
                    "metric": "cruise_speed",
                    "operator": "at_least",
                    "value": 65.0,
                    "unit": "m/s",
                },
                {
                    "id": "power",
                    "kind": "constraint",
                    "metric": "power_limit",
                    "operator": "at_most",
                    "value": 1.0,
                    "unit": "W",
                },
            ]
        }
    )
    seed = generate_fixed_wing_seeds(compiled, seed_count=1)[0]
    spec = build_airframe_campaign_spec(
        "airframe07-downstream",
        seed,
        generation=GenerationRequest("lhs", count=1, budget=1, seed=1),
        objectives=(StudyObjective("score", "minimize"),),
        fidelity_ladder=(FidelityImplementation("analytical", 0, 0.0),),
        budget=CampaignBudget(max_evaluations=1),
        requirements=compiled,
    )

    def evaluator(candidate: Candidate, fidelity: str) -> EvaluationResult:
        return EvaluationResult(
            outputs={"score": 1.0, "power_limit": 2.0},
            flags=PhysicsFlags(converged=True, closure_passed=True, validity_ok=True),
            fidelity=fidelity,
        )

    receipt = AirframeCampaignSession(
        spec,
        evaluator,
        evaluator_identity="downstream-v1",
        mutation_policy=AirframeMutationPolicy.default(),
    ).run()
    assert receipt.record.best is None
    assert receipt.record.results[0].detail.startswith("REQUIREMENT_CONSTRAINT_VIOLATED")
