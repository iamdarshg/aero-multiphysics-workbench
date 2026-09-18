"""GEN 04: candidate evaluation, selection, diversity, and multi-fidelity promotion.

A tiny deterministic evaluator stands in for the participant graph: it returns
measured outputs and physics flags per (candidate, fidelity), so no solver runs
and every assertion is a pure campaign-contract check.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from aeroworkbench_optimization import (
    CampaignBudget,
    CampaignRecord,
    CampaignSpec,
    CampaignState,
    Candidate,
    CandidateProvenance,
    EvaluationRecord,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    InMemoryResultStore,
    PhysicsFlags,
    StudyConstraint,
    StudyObjective,
    run_campaign,
)
from aeroworkbench_optimization.campaign import (
    pareto_front,
    rank_weighted,
    select_diverse,
    select_feasible,
    top_k,
)

CAMPAIGN_SPACE = r"""
{
  "id": "gen04-campaign",
  "variables": [
    { "id": "x", "kind": "integer",
      "bindings": [{ "target": "parameter", "path": "p.x" }], "baseValue": 1,
      "domain": { "kind": "integer", "lower": 0, "upper": 2, "step": 1 } },
    { "id": "y", "kind": "discrete",
      "bindings": [{ "target": "parameter", "path": "p.y" }], "baseValue": 1.0,
      "domain": { "kind": "discrete", "values": [1.0, 2.0] } },
    { "id": "mat", "kind": "categorical",
      "bindings": [{ "target": "material", "path": "m.mat" }], "baseValue": "a",
      "domain": { "kind": "categorical", "values": ["a", "b"] } },
    { "id": "c", "kind": "continuous",
      "bindings": [{ "target": "parameter", "path": "p.c" }], "baseValue": 0.5,
      "domain": { "kind": "continuous", "lower": 0.0, "upper": 1.0 } }
  ],
  "branches": [],
  "constraints": []
}
"""

OBJECTIVES = (StudyObjective("thrust", "maximize"), StudyObjective("mass", "minimize"))
LADDER = (
    FidelityImplementation("analytical", 0, 1.0),
    FidelityImplementation("native", 1, 4.0),
)


def campaign_space() -> dict:
    return json.loads(CAMPAIGN_SPACE)


def spec(**overrides: object) -> CampaignSpec:
    base: dict = {
        "campaign_id": "gen04",
        "base_revision": "rev-base",
        "space": campaign_space(),
        "generation": GenerationRequest("factorial", levels=2, budget=100),
        "objectives": OBJECTIVES,
        "fidelity_ladder": LADDER,
        "promote_fraction": 1.0,
        "min_promote": 1,
    }
    base.update(overrides)
    return CampaignSpec(**base)  # type: ignore[arg-type]


def make_evaluator(
    calls: list[str],
    *,
    analytical_thrust: Callable[[float, float], float] = lambda x, c: x + c,
    native_thrust: Callable[[float, float], float] = lambda x, c: 2.0 - x - c,
    disagreement: float = 0.5,
) -> Callable[[Candidate, str], EvaluationResult]:
    def evaluator(candidate: Candidate, fidelity: str) -> EvaluationResult:
        calls.append(fidelity)
        values = {
            item.variable_id: item.value
            for item in candidate.assignment
            if item.point_id is None
        }
        x = float(values["x"])
        c = float(values["c"])
        y = float(values["y"])
        mat = values["mat"]
        thrust = native_thrust(x, c) if fidelity == "native" else analytical_thrust(x, c)
        outputs = {"thrust": thrust, "mass": y, "stress": x}
        flags = PhysicsFlags(
            converged=mat != "b", closure_passed=True, validity_ok=True
        )
        signals = {"disagreement": disagreement if fidelity == "analytical" else 0.0}
        return EvaluationResult(
            outputs=outputs,
            flags=flags,
            fidelity=fidelity,
            cost=4.0 if fidelity == "native" else 1.0,
            signals=signals,
        )

    return evaluator


def _synthetic_candidate(name: str, normalized: dict[str, float]) -> Candidate:
    return Candidate(
        candidate_hash=name,
        parent_hash=None,
        space_id="synthetic",
        index=0,
        strategy="random",
        seed=0,
        preflight_state="valid",
        preflight_reasons=(),
        active_variables=tuple(normalized),
        assignment=(),
        mutations=(),
        normalized=tuple(sorted(normalized.items())),
        state={},
        flat=None,
        provenance=CandidateProvenance("synthetic", None, "random", 0, 0, None, "cfg"),
    )


def _synthetic_eval(name: str, thrust: float, state: str = "valid") -> EvaluationRecord:
    return EvaluationRecord(
        candidate_hash=name,
        fidelity="analytical",
        state=state,
        reasons=() if state == "valid" else ("solver did not converge",),
        outputs=(("thrust", thrust), ("mass", 1.0)),
        cost=0.0,
        source="test",
        geometry_hash=None,
        signal_digest="",
        detail="",
    )


def test_gen04_campaign_end_to_end_excludes_invalid_and_reranks_at_higher_fidelity() -> None:
    calls: list[str] = []
    record = run_campaign(spec(), make_evaluator(calls), evaluator_identity="eval-v1")
    assert record.state is CampaignState.COMPLETED
    assert record.metrics["generated"] == 24
    assert record.metrics["invalid"] == 12
    assert record.metrics["high_fidelity_evaluations"] == 12
    assert record.metrics["evaluations"] == 24 + 12
    assert record.best is not None
    best = record.candidates[record.best]
    assert best.fidelity == "native"
    assert best.outputs["thrust"] == pytest.approx(2.0)
    assert best.status in {"feasible", "retained"}
    assert record.pareto
    for promotion in record.promotions:
        entry = record.candidates[promotion.candidate_hash]
        assert entry.status != "invalid"
        if promotion.advanced:
            assert entry.fidelity == "native"
    invalid_hashes = {
        candidate_hash
        for candidate_hash, entry in record.candidates.items()
        if entry.status == "invalid"
    }
    assert invalid_hashes
    assert invalid_hashes.isdisjoint(set(record.pareto))
    assert record.best not in invalid_hashes


def test_gen04_promotion_uses_measured_signals() -> None:
    calls: list[str] = []
    record = run_campaign(spec(), make_evaluator(calls), evaluator_identity="eval-v1")
    advanced = [promotion for promotion in record.promotions if promotion.advanced]
    assert advanced
    assert all(promotion.from_fidelity == "analytical" for promotion in advanced)
    assert all(promotion.to_fidelity == "native" for promotion in advanced)
    assert any(
        "disagreement" in reason for promotion in advanced for reason in promotion.reasons
    )
    assert all(promotion.signal_digest for promotion in advanced)


def test_gen04_invalid_samples_never_rank_or_promote() -> None:
    valid = _synthetic_candidate("aaa", {"x": 0.0})
    invalid = _synthetic_candidate("bbb", {"x": 1.0})
    records = [
        (valid, _synthetic_eval("aaa", 1.0)),
        (invalid, _synthetic_eval("bbb", 0.0, "invalid")),
    ]
    ranked = rank_weighted(records, OBJECTIVES)
    assert [candidate.candidate_hash for candidate, _ in ranked] == ["aaa"]
    front = pareto_front(records, OBJECTIVES)
    assert [candidate.candidate_hash for candidate, _ in front] == ["aaa"]
    feasible = select_feasible(records, ())
    assert [candidate.candidate_hash for candidate, _ in feasible] == ["aaa"]


def test_gen04_pareto_and_top_k_are_deterministic() -> None:
    left = _synthetic_eval("aaa", 1.0)
    right = _synthetic_eval("bbb", 1.0)
    records = [
        (_synthetic_candidate("aaa", {"x": 0.0}), left),
        (_synthetic_candidate("bbb", {"x": 1.0}), right),
    ]
    first = rank_weighted(records, OBJECTIVES)
    second = rank_weighted(records, OBJECTIVES)
    assert [item[0].candidate_hash for item in first] == [item[0].candidate_hash for item in second]
    # Equal scores break deterministically by candidate hash.
    assert [item[0].candidate_hash for item in first] == ["aaa", "bbb"]
    front = pareto_front(records, OBJECTIVES)
    # Identical objective vectors: neither dominates, so both stay on the front.
    assert [item[0].candidate_hash for item in front] == ["aaa", "bbb"]
    assert [item[0].candidate_hash for item in top_k(first, 1)] == ["aaa"]


def test_gen04_diversity_prevents_near_duplicates() -> None:
    best = _synthetic_candidate("best", {"x": 0.0})
    near = _synthetic_candidate("near", {"x": 0.001})
    distinct = _synthetic_candidate("distinct", {"x": 1.0})
    ranked = [
        (best, _synthetic_eval("best", 3.0)),
        (near, _synthetic_eval("near", 2.9)),
        (distinct, _synthetic_eval("distinct", 1.0)),
    ]
    chosen = select_diverse(ranked, 2)
    hashes = {candidate.candidate_hash for candidate, _ in chosen}
    assert hashes == {"best", "distinct"}


def test_gen04_resume_reuses_completed_candidate_results() -> None:
    store = InMemoryResultStore()
    first_calls: list[str] = []
    run_campaign(
        spec(), make_evaluator(first_calls), store=store, evaluator_identity="eval-v1"
    )
    assert first_calls
    assert store.keys()
    second_calls: list[str] = []
    record = run_campaign(
        spec(), make_evaluator(second_calls), store=store, evaluator_identity="eval-v1"
    )
    assert second_calls == []
    assert record.metrics["evaluations"] == 0
    assert record.metrics["cache_hits"] == 24 + 12
    assert record.best is not None


def test_gen04_budget_stops_cleanly() -> None:
    calls: list[str] = []
    record = run_campaign(
        spec(budget=CampaignBudget(max_evaluations=3)),
        make_evaluator(calls),
        evaluator_identity="eval-v1",
    )
    assert record.state is CampaignState.COMPLETED
    assert record.stop_reason == "max-evaluations"
    assert record.metrics["evaluations"] == 3
    assert len(record.evaluations) == 3


def test_gen04_target_feasibility_stops_campaign() -> None:
    calls: list[str] = []
    constrained = spec(
        constraints=(StudyConstraint("stress", "upper", 1.0),),
        budget=CampaignBudget(target_feasibility=0.6),
    )
    record = run_campaign(constrained, make_evaluator(calls), evaluator_identity="eval-v1")
    assert record.stop_reason == "target-feasibility"
    assert record.metrics["high_fidelity_evaluations"] == 0


def test_gen04_no_improvement_rounds_stop_campaign() -> None:
    calls: list[str] = []
    flat = make_evaluator(
        calls, analytical_thrust=lambda x, c: x, native_thrust=lambda x, c: x
    )
    record = run_campaign(
        spec(budget=CampaignBudget(no_improvement_rounds=1)),
        flat,
        evaluator_identity="eval-v1",
    )
    assert record.stop_reason == "no-improvement"
    assert record.metrics["high_fidelity_evaluations"] > 0


def test_gen04_cancellation_preserves_evidence() -> None:
    calls: list[str] = []

    def cancel_check() -> bool:
        return len(calls) >= 5

    record = run_campaign(
        spec(),
        make_evaluator(calls),
        evaluator_identity="eval-v1",
        cancel_check=cancel_check,
    )
    assert record.state is CampaignState.CANCELLED
    assert record.stop_reason == "cancelled"
    assert record.evaluations
    assert record.candidates
    assert record.metrics["evaluations"] >= 5


def test_gen04_state_machine_history_is_ordered() -> None:
    calls: list[str] = []
    record = run_campaign(spec(), make_evaluator(calls), evaluator_identity="eval-v1")
    history = list(record.state_history)
    assert history[0] is CampaignState.CREATED
    assert history.index(CampaignState.GENERATING) < history.index(CampaignState.EVALUATING)
    assert history.index(CampaignState.EVALUATING) < history.index(CampaignState.SELECTING)
    assert history.index(CampaignState.SELECTING) < history.index(CampaignState.PROMOTING)
    assert history[-1] is CampaignState.COMPLETED


def test_gen04_custom_selector_seam_is_honored() -> None:
    calls: list[str] = []
    seen: dict[str, int] = {}

    def selector(evaluated: object, objectives: object) -> tuple:
        seen["count"] = len(evaluated)  # type: ignore[arg-type]
        return tuple(reversed(evaluated))  # type: ignore[arg-type]

    record = run_campaign(
        spec(selector=selector), make_evaluator(calls), evaluator_identity="eval-v1"
    )
    assert seen["count"] == 12
    assert record.state is CampaignState.COMPLETED


def test_gen04_record_round_trips_through_json() -> None:
    calls: list[str] = []
    record = run_campaign(spec(), make_evaluator(calls), evaluator_identity="eval-v1")
    payload = json.loads(json.dumps(record.as_dict()))
    rebuilt = CampaignRecord.from_dict(payload)
    assert rebuilt.as_dict() == record.as_dict()
