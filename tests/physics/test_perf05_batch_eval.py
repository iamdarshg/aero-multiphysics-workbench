"""PERF 05: batch/vectorized cheap-candidate evaluation before native promotion.

Bounded deterministic tests: no native solver runs, no cloud, no large sweeps.
They verify the batch contract (identity preserved, invalid-row isolation, scalar
fallback equivalence), NumPy vectorization restricted to analytical/reduced
models, memory-bounded chunking, OpenMDAO Problem setup reuse, and the campaign
engine streaming only promoted candidates to the native rung.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence

import numpy as np
import pytest
from aeroworkbench_coupling.manifest_coordinator import (
    BatchSolveResult,
    CouplingLink,
    ManifestCoordinator,
    ParticipantBatchRow,
    ProblemReusePolicy,
    ScalarParticipantSpec,
    VariableSpec,
    evaluate_participant_batch,
)
from aeroworkbench_optimization import (
    BatchEvaluator,
    BatchRequest,
    BatchRow,
    CampaignSpec,
    Candidate,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    OneAtATimeBatchEvaluator,
    PhysicsFlags,
    ScalarEvaluation,
    StudyObjective,
    VectorizedReducedModel,
    build_batch_requests,
    compare_batch_rows,
    iter_chunks,
    plan_batch_size,
    run_batch_requests,
    run_campaign,
)
from aeroworkbench_optimization.batch_eval import BatchMetrics

# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _valid_flags() -> PhysicsFlags:
    return PhysicsFlags(converged=True, closure_passed=True, validity_ok=True)


def _batch_lite_model() -> VectorizedReducedModel:
    def vector_function(
        arrays: Mapping[str, object], operating_points: tuple[str, ...]
    ) -> Mapping[str, object]:
        x = np.asarray(arrays["x"], dtype=float)
        y = np.asarray(arrays["y"], dtype=float)
        c = np.asarray(arrays["c"], dtype=float)
        scale = np.array([2.0 if op == "hot" else 1.0 for op in operating_points])
        return {"thrust": scale * (x + c), "mass": y, "stress": x}

    return VectorizedReducedModel(
        model_id="batch-lite",
        fidelity="analytical",
        input_names=("x", "y", "c"),
        output_names=("thrust", "mass", "stress"),
        vector_function=vector_function,
    )


def _scalar_lite(inputs: Mapping[str, float], operating_point: str) -> ScalarEvaluation:
    scale = 2.0 if operating_point == "hot" else 1.0
    return ScalarEvaluation(
        outputs={
            "thrust": scale * (inputs["x"] + inputs["c"]),
            "mass": inputs["y"],
            "stress": inputs["x"],
        },
        flags=_valid_flags(),
    )


def _entries(count: int) -> list[tuple[str, dict[str, float]]]:
    return [
        (
            f"cand-{index:04d}",
            {"x": float(index % 7), "y": float(index % 3), "c": index / max(count, 1)},
        )
        for index in range(count)
    ]


class _CountingBatchEvaluator:
    """Wraps a batch model and counts how many times the underlying math ran."""

    def __init__(self, inner: BatchEvaluator) -> None:
        self._inner = inner
        self.calls = 0
        self.rows = 0

    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> Sequence[BatchRow]:
        self.calls += 1
        self.rows += len(requests)
        return self._inner.evaluate_batch(requests)


class _ShuffledBatchEvaluator:
    """Correct rows returned out of order to prove identity-based matching."""

    def __init__(self, inner: BatchEvaluator) -> None:
        self._inner = inner

    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> Sequence[BatchRow]:
        return tuple(reversed(tuple(self._inner.evaluate_batch(requests))))


class _WrongCountEvaluator:
    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> Sequence[BatchRow]:
        return ()


class _ScalarCallable:
    """Adapters the campaign helper expects: Evaluator + BatchEvaluator."""

    def __init__(self) -> None:
        self.scalar_fidelities: list[str] = []
        self.batch_rows = 0

    def scalar(self, candidate: Candidate, fidelity: str) -> EvaluationResult:
        self.scalar_fidelities.append(fidelity)
        values = {
            item.variable_id: item.value
            for item in candidate.assignment
            if item.point_id is None
        }
        x = float(values["x"])
        c = float(values["c"])
        y = float(values["y"])
        thrust = 2.0 - x - c if fidelity == "native" else x + c
        return EvaluationResult(
            outputs={"thrust": thrust, "mass": y, "stress": x},
            flags=_valid_flags(),
            fidelity=fidelity,
            cost=4.0 if fidelity == "native" else 0.0,
            signals={"disagreement": 0.5} if fidelity == "analytical" else None,
        )

    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> Sequence[BatchRow]:
        self.batch_rows += len(requests)
        rows: list[BatchRow] = []
        for request in requests:
            inputs = request.input_dict()
            x = inputs["x"]
            c = inputs["c"]
            y = inputs["y"]
            rows.append(
                BatchRow(
                    candidate_hash=request.candidate_hash,
                    operating_point=request.operating_point,
                    index=request.index,
                    state="valid",
                    outputs=(("mass", y), ("stress", x), ("thrust", x + c)),
                    flags=_valid_flags(),
                    source="analytical",
                    signals=(("disagreement", 0.5),),
                )
            )
        return tuple(rows)


CAMPAIGN_SPACE = json.dumps(
    {
        "id": "perf05-campaign",
        "variables": [
            {
                "id": "x",
                "kind": "integer",
                "bindings": [{"target": "parameter", "path": "p.x"}],
                "baseValue": 1,
                "domain": {"kind": "integer", "lower": 0, "upper": 3, "step": 1},
            },
            {
                "id": "y",
                "kind": "discrete",
                "bindings": [{"target": "parameter", "path": "p.y"}],
                "baseValue": 1.0,
                "domain": {"kind": "discrete", "values": [1.0, 2.0]},
            },
            {
                "id": "c",
                "kind": "continuous",
                "bindings": [{"target": "parameter", "path": "p.c"}],
                "baseValue": 0.5,
                "domain": {"kind": "continuous", "lower": 0.0, "upper": 1.0},
            },
        ],
        "branches": [],
        "constraints": [],
    }
)

OBJECTIVES = (StudyObjective("thrust", "maximize"), StudyObjective("mass", "minimize"))
LADDER = (
    FidelityImplementation("analytical", 0, 0.0),
    FidelityImplementation("native", 1, 4.0),
)


def _campaign_spec(**overrides: object) -> CampaignSpec:
    base: dict = {
        "campaign_id": "perf05",
        "base_revision": "rev-base",
        "space": json.loads(CAMPAIGN_SPACE),
        "generation": GenerationRequest("factorial", levels=2, budget=100),
        "objectives": OBJECTIVES,
        "fidelity_ladder": LADDER,
        "promote_fraction": 1.0,
        "min_promote": 1,
    }
    base.update(overrides)
    return CampaignSpec(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. batch evaluator contract
# ---------------------------------------------------------------------------


def test_requests_preserve_candidate_hash_and_operating_point_identity() -> None:
    requests = build_batch_requests(
        _entries(3), operating_points=("cold", "hot"), start_index=0
    )
    assert len(requests) == 6
    shuffled = _ShuffledBatchEvaluator(_batch_lite_model())
    result = run_batch_requests(requests, fallback=_scalar_lite, evaluator=shuffled)
    assert [row.key for row in result.rows] == [request.key for request in requests]
    by_key = result.by_key()
    assert by_key[("cand-0001", "hot")].output_dict["thrust"] == pytest.approx(
        by_key[("cand-0001", "cold")].output_dict["thrust"] * 2.0
    )


def test_one_at_a_time_fallback_isolates_failing_rows() -> None:
    def fallback(inputs: Mapping[str, float], operating_point: str) -> ScalarEvaluation:
        if inputs["x"] == 2.0:
            raise RuntimeError("boom")
        if inputs["x"] == 3.0:
            return ScalarEvaluation(outputs={"thrust": math.nan}, flags=_valid_flags())
        return _scalar_lite(inputs, operating_point)

    requests = build_batch_requests(_entries(4), operating_points=("nominal",))
    rows = OneAtATimeBatchEvaluator(fallback).evaluate_batch(requests)
    assert [row.state for row in rows] == ["valid", "valid", "invalid", "invalid"]
    assert "EVALUATION_ERROR" in rows[2].reasons[0]
    assert "NONFINITE_OUTPUT" in rows[3].reasons[0]
    assert rows[0].output_dict["thrust"] == pytest.approx(rows[0].output_dict["stress"])


def test_malformed_batch_falls_back_and_stays_correct() -> None:
    requests = build_batch_requests(_entries(5), operating_points=("nominal",))
    result = run_batch_requests(
        requests, fallback=_scalar_lite, evaluator=_WrongCountEvaluator(), batch_size=2
    )
    assert all(row.state == "valid" for row in result.rows)
    assert result.metrics.fallback_batches >= 1
    # Fallback result must equal the scalar reference.
    reference = run_batch_requests(requests, fallback=_scalar_lite)
    assert compare_batch_rows(reference.rows, result.rows) == ()


def test_batch_and_scalar_results_are_equivalent_within_tolerance() -> None:
    requests = build_batch_requests(_entries(100), operating_points=("cold", "hot"))
    batch = run_batch_requests(requests, fallback=_scalar_lite, evaluator=_batch_lite_model())
    scalar = run_batch_requests(requests, fallback=_scalar_lite)
    assert compare_batch_rows(scalar.rows, batch.rows, rtol=1e-12, atol=1e-12) == ()


# ---------------------------------------------------------------------------
# B. vectorization restricted to pure analytical/reduced models
# ---------------------------------------------------------------------------


def test_vectorized_model_refuses_native_fidelity() -> None:
    with pytest.raises(ValueError, match="BATCH_VECTORIZATION_NATIVE_NOT_ALLOWED"):
        VectorizedReducedModel(
            model_id="native-thing",
            fidelity="native",
            input_names=("x",),
            output_names=("y",),
            vector_function=lambda arrays, ops: {"y": arrays["x"]},
        )


def test_vectorized_model_runs_once_per_chunk_not_once_per_candidate() -> None:
    counter = _CountingBatchEvaluator(_batch_lite_model())
    requests = build_batch_requests(_entries(100), operating_points=("nominal",))
    result = run_batch_requests(
        requests, fallback=_scalar_lite, evaluator=counter, batch_size=25
    )
    assert counter.calls == 4, "100 rows / 25 per chunk must be 4 vector calls"
    assert counter.rows == 100
    assert result.metrics.batches == 4
    assert result.metrics.effective_batch_size == 25


def test_vectorized_model_marks_only_bad_rows_invalid() -> None:
    def vector_function(
        arrays: Mapping[str, object], operating_points: tuple[str, ...]
    ) -> Mapping[str, object]:
        x = np.asarray(arrays["x"], dtype=float)
        thrust = x + np.asarray(arrays["c"], dtype=float)
        thrust = np.where(x == 0.0, np.nan, thrust)
        return {"thrust": thrust, "mass": np.asarray(arrays["y"], dtype=float)}

    model = VectorizedReducedModel(
        model_id="bad-row",
        fidelity="reduced",
        input_names=("x", "y", "c"),
        output_names=("thrust", "mass"),
        vector_function=vector_function,
    )
    requests = build_batch_requests(_entries(6), operating_points=("nominal",))
    rows = model.evaluate_batch(requests)
    invalid = [row for row in rows if row.state == "invalid"]
    assert len(invalid) == 1
    assert invalid[0].key == ("cand-0000", "nominal")
    assert "NONFINITE_BATCH_OUTPUT" in invalid[0].reasons[0]


def test_vectorized_model_marks_missing_input_invalid() -> None:
    requests = (
        BatchRequest("cand-a", "nominal", (("x", 1.0), ("y", 1.0), ("c", 0.5))),
        BatchRequest("cand-b", "nominal", (("x", 1.0), ("y", 1.0))),
    )
    rows = _batch_lite_model().evaluate_batch(requests)
    assert rows[0].state == "valid"
    assert rows[1].state == "invalid"
    assert "MISSING_BATCH_INPUT" in rows[1].reasons[0]


# ---------------------------------------------------------------------------
# C. operating-point batching
# ---------------------------------------------------------------------------


def test_operating_points_are_batched_but_keep_separate_records() -> None:
    requests = build_batch_requests(_entries(10), operating_points=("cold", "hot"))
    batch = run_batch_requests(requests, fallback=_scalar_lite, evaluator=_batch_lite_model())
    scalar = run_batch_requests(requests, fallback=_scalar_lite)
    assert len(batch.rows) == 20
    assert compare_batch_rows(scalar.rows, batch.rows) == ()
    hot = {row.key for row in batch.rows if row.operating_point == "hot"}
    cold = {row.key for row in batch.rows if row.operating_point == "cold"}
    assert hot.isdisjoint(cold)
    assert len(hot) == len(cold) == 10


# ---------------------------------------------------------------------------
# D. memory-bounded chunking
# ---------------------------------------------------------------------------


def test_plan_batch_size_respects_memory_budget() -> None:
    assert plan_batch_size(1000) == 1000
    assert plan_batch_size(1000, memory_budget_bytes=4096, bytes_per_row=1024) == 4
    assert plan_batch_size(2, memory_budget_bytes=1, bytes_per_row=1024) == 1
    with pytest.raises(ValueError):
        plan_batch_size(0)


def test_iter_chunks_never_exceeds_batch_size() -> None:
    requests = build_batch_requests(_entries(10), operating_points=("nominal",))
    chunks = list(iter_chunks(requests, 3))
    assert [len(chunk) for chunk in chunks] == [3, 3, 3, 1]


def test_chunked_run_bounds_peak_rows_for_1000_candidates() -> None:
    requests = build_batch_requests(_entries(1000), operating_points=("nominal",))
    result = run_batch_requests(
        requests,
        fallback=_scalar_lite,
        evaluator=_batch_lite_model(),
        batch_size=128,
        memory_budget_bytes=64 * 1024,
        bytes_per_row=1024,
    )
    assert result.metrics.peak_batch_rows <= result.metrics.effective_batch_size
    assert result.metrics.effective_batch_size == 64
    assert result.metrics.batches == math.ceil(1000 / 64)
    assert len(result.rows) == 1000


# ---------------------------------------------------------------------------
# E/F. deterministic 1/10/100/1000 benchmarks + metrics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 10, 100, 1000])
def test_batch_benchmark_sizes_match_scalar(count: int) -> None:
    requests = build_batch_requests(_entries(count), operating_points=("cold", "hot"))
    batch = run_batch_requests(
        requests, fallback=_scalar_lite, evaluator=_batch_lite_model(), batch_size=100
    )
    scalar = run_batch_requests(requests, fallback=_scalar_lite, batch_size=100)
    assert compare_batch_rows(scalar.rows, batch.rows) == ()
    assert batch.metrics.candidates == 2 * count
    assert batch.metrics.candidates_per_second > 0
    assert batch.metrics.per_candidate_overhead_ms >= 0
    assert batch.metrics.setup_seconds >= 0
    assert batch.metrics.effective_batch_size == 100
    # Batch reaches the vector model once per chunk; scalar path once per row.
    assert batch.metrics.batches <= scalar.metrics.batches
    print(
        f"[perf05] n={count} rows={batch.metrics.candidates} "
        f"batches={batch.metrics.batches} cand/s={batch.metrics.candidates_per_second:.0f} "
        f"overhead_ms={batch.metrics.per_candidate_overhead_ms:.4f}"
    )


def test_setup_time_is_measured_and_reported() -> None:
    state = {"built": 0}

    def setup() -> None:
        state["built"] += 1

    requests = build_batch_requests(_entries(50), operating_points=("nominal",))
    result = run_batch_requests(
        requests, fallback=_scalar_lite, evaluator=_batch_lite_model(), setup=setup
    )
    assert state["built"] == 1
    assert isinstance(result.metrics, BatchMetrics)
    assert result.metrics.setup_seconds >= 0.0
    payload = result.metrics.as_dict()
    for key in (
        "candidatesPerSecond",
        "perCandidateOverheadMs",
        "setupSeconds",
        "batchSize",
    ):
        assert key in payload


# ---------------------------------------------------------------------------
# F. OpenMDAO Problem setup reuse
# ---------------------------------------------------------------------------


def _shared_input_participants() -> tuple[ScalarParticipantSpec, ScalarParticipantSpec]:
    heater = ScalarParticipantSpec(
        participant_id="heater",
        physics_domain="thermal",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("power_w", "W", 100.0), VariableSpec("ambient_k", "K", 300.0)),
        outputs=(VariableSpec("temperature_k", "K", 300.0),),
        function=lambda state: {
            "temperature_k": state["ambient_k"] + 0.05 * state["power_w"]
        },
    )
    controller = ScalarParticipantSpec(
        participant_id="controller",
        physics_domain="control",
        fidelity="analytical",
        solver_identity="toy",
        solver_version="0.0.0",
        inputs=(VariableSpec("temperature_k", "K", 300.0), VariableSpec("ambient_k", "K", 300.0)),
        outputs=(VariableSpec("power_w", "W", 100.0),),
        function=lambda state: {
            "power_w": 200.0 - 0.5 * (state["temperature_k"] - state["ambient_k"])
        },
    )
    return heater, controller


def _cycle_links() -> tuple[CouplingLink, ...]:
    return (
        CouplingLink("heater", "temperature_k", "controller", "temperature_k"),
        CouplingLink("controller", "power_w", "heater", "power_w"),
    )


def test_solve_many_reuses_setup_and_matches_fresh_solves() -> None:
    heater, controller = _shared_input_participants()
    coordinator = ManifestCoordinator((heater, controller), _cycle_links(), shared=("ambient_k",))
    candidates = [{"ambient_k": 290.0 + index} for index in range(5)]
    batched = coordinator.solve_many(candidates, policy=ProblemReusePolicy(reuse_problem=True))
    assert isinstance(batched, BatchSolveResult)
    assert batched.metrics.problems_built == 1
    assert batched.metrics.reused_setups == 4
    assert batched.metrics.solves == 5
    assert batched.metrics.candidates_per_second > 0
    assert batched.metrics.setup_seconds >= 0
    assert batched.metrics.per_candidate_overhead_ms > 0
    for initial, result in zip(candidates, batched.results, strict=True):
        fresh = ManifestCoordinator(
            (heater, controller), _cycle_links(), shared=("ambient_k",)
        ).solve(initial)
        assert result.converged and fresh.converged
        left, right = dict(result.values), dict(fresh.values)
        assert left.keys() == right.keys()
        for key in left:
            assert left[key] == pytest.approx(right[key], rel=1e-9, abs=1e-9)
        assert result.iterations == fresh.iterations


def test_reuse_warm_start_stays_within_declared_tolerance() -> None:
    heater, controller = _shared_input_participants()
    coordinator = ManifestCoordinator((heater, controller), _cycle_links(), shared=("ambient_k",))
    candidates = [{"ambient_k": 300.0 + 2.0 * index} for index in range(4)]
    warm = coordinator.solve_many(
        candidates, policy=ProblemReusePolicy(reuse_problem=True, warm_start=True)
    )
    for initial, result in zip(candidates, warm.results, strict=True):
        fresh = ManifestCoordinator(
            (heater, controller), _cycle_links(), shared=("ambient_k",)
        ).solve(initial)
        for key, value in dict(fresh.values).items():
            assert dict(result.values)[key] == pytest.approx(value, rel=1e-6, abs=1e-6)


def test_reuse_policy_rebuilds_when_disabled() -> None:
    heater, controller = _shared_input_participants()
    coordinator = ManifestCoordinator((heater, controller), _cycle_links(), shared=("ambient_k",))
    candidates = [{"ambient_k": 295.0 + index} for index in range(3)]
    rebuilt = coordinator.solve_many(
        candidates, policy=ProblemReusePolicy(reuse_problem=False)
    )
    assert rebuilt.metrics.problems_built == 3
    assert rebuilt.metrics.reused_setups == 0


def test_coordinator_batch_participant_contract_isolates_invalid_rows() -> None:
    def batch_function(
        states: Sequence[Mapping[str, float]],
    ) -> Sequence[Mapping[str, float]]:
        return [
            {"temperature_k": state["ambient_k"] + 1.0}
            if state["ambient_k"] < 400.0
            else {"temperature_k": math.nan}
            for state in states
        ]

    spec, _ = _shared_input_participants()
    batched = ScalarParticipantSpec(
        participant_id=spec.participant_id,
        physics_domain=spec.physics_domain,
        fidelity=spec.fidelity,
        solver_identity=spec.solver_identity,
        solver_version=spec.solver_version,
        inputs=spec.inputs,
        outputs=spec.outputs,
        function=spec.function,
        batch_function=batch_function,
    )
    assert batched.supports_batch
    rows = evaluate_participant_batch(batched, ({"ambient_k": 300.0}, {"ambient_k": 500.0}))
    assert isinstance(rows[0], ParticipantBatchRow)
    assert rows[0].participant_id == "heater"
    assert rows[0].state == "valid"
    assert rows[1].state == "invalid"
    assert "NONFINITE_PARTICIPANT_OUTPUT" in rows[1].reasons[0]
    assert len(rows) == 2


def test_participant_batch_failure_falls_back_to_scalar() -> None:
    def bad_batch(states: Sequence[Mapping[str, float]]) -> Sequence[Mapping[str, float]]:
        raise RuntimeError("no batch for this participant")

    spec, _ = _shared_input_participants()
    declared = ScalarParticipantSpec(
        participant_id=spec.participant_id,
        physics_domain=spec.physics_domain,
        fidelity=spec.fidelity,
        solver_identity=spec.solver_identity,
        solver_version=spec.solver_version,
        inputs=spec.inputs,
        outputs=spec.outputs,
        function=lambda state: {"temperature_k": state["ambient_k"] + 5.0},
        batch_function=bad_batch,
    )
    rows = evaluate_participant_batch(declared, ({"ambient_k": 301.0}, {"ambient_k": 302.0}))
    assert all(row.state == "valid" for row in rows)
    assert rows[0].output_dict["temperature_k"] == pytest.approx(306.0)


# ---------------------------------------------------------------------------
# E. campaign engine: chunk cheap rung, stream only promoted to native
# ---------------------------------------------------------------------------


def test_campaign_batch_path_matches_scalar_campaign() -> None:
    adapter = _ScalarCallable()
    scalar_record = run_campaign(
        _campaign_spec(), adapter.scalar, evaluator_identity="perf05"
    )
    batch_adapter = _ScalarCallable()
    batch_record = run_campaign(
        _campaign_spec(),
        batch_adapter.scalar,
        evaluator_identity="perf05",
        batch_evaluator=batch_adapter,
        batch_size=8,
    )
    assert batch_record.state == scalar_record.state
    assert batch_record.best == scalar_record.best
    assert batch_record.pareto == scalar_record.pareto
    assert batch_record.metrics["evaluations"] == scalar_record.metrics["evaluations"]
    assert (
        batch_record.metrics["high_fidelity_evaluations"]
        == scalar_record.metrics["high_fidelity_evaluations"]
    )
    assert batch_record.metrics["promoted"] == scalar_record.metrics["promoted"]
    assert batch_record.metrics["invalid"] == scalar_record.metrics["invalid"]
    for hash_key, entry in scalar_record.candidates.items():
        assert batch_record.candidates[hash_key].status == entry.status
        assert batch_record.candidates[hash_key].outputs == entry.outputs
    # Batch metrics are recorded from measured values.
    assert batch_record.metrics["batches"] >= 1
    assert batch_record.metrics["effective_batch_size"] == 8
    assert batch_record.metrics["peak_batch_rows"] <= 8
    assert batch_record.metrics["setup_seconds"] >= 0


def test_campaign_only_promoted_candidates_reach_native_rung() -> None:
    adapter = _ScalarCallable()
    record = run_campaign(
        _campaign_spec(),
        adapter.scalar,
        evaluator_identity="perf05",
        batch_evaluator=adapter,
        batch_size=8,
    )
    native_calls = sum(1 for fidelity in adapter.scalar_fidelities if fidelity == "native")
    assert native_calls == record.metrics["high_fidelity_evaluations"]
    assert native_calls == record.metrics["promoted"]
    # Cheap analytical rung was fully served by the batch evaluator.
    assert adapter.scalar_fidelities.count("analytical") == 0
    assert adapter.batch_rows >= record.metrics["high_fidelity_evaluations"]


def test_campaign_batch_path_respects_evaluation_budget() -> None:
    from aeroworkbench_optimization import CampaignBudget

    adapter = _ScalarCallable()
    record = run_campaign(
        _campaign_spec(budget=CampaignBudget(max_evaluations=5)),
        adapter.scalar,
        evaluator_identity="perf05",
        batch_evaluator=adapter,
        batch_size=8,
    )
    assert record.stop_reason == "max-evaluations"
    assert record.metrics["evaluations"] == 5


def test_campaign_without_batch_evaluator_is_unchanged_and_correct() -> None:
    adapter = _ScalarCallable()
    record = run_campaign(_campaign_spec(), adapter.scalar, evaluator_identity="perf05")
    assert "batchSize" not in record.metrics
    assert record.metrics["generated"] == 16
    assert record.best is not None
