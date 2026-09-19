"""PERF 02: resource-aware concurrent scheduling over the governed lifecycle.

All fixtures here are tiny/bounded: the synthetic participant is in-process and
sleeps for milliseconds, so these tests prove *scheduler* behavior (overlap,
memory reservation, exclusivity, fairness, cancellation, recovery, batched
submission) without running any real CFD/FEA workload. No provenance,
validation, or fail-closed gate is weakened.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from participants.lifecycle import (
    JobProfile,
    JobRequest,
    JobState,
    NativeJobManager,
    ResourceScheduler,
    SolverResourcePolicy,
)
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

TERMINAL = {JobState.COMPLETED.value, JobState.FAILED.value, JobState.CANCELLED.value}

_REGISTERED = False
_EXEC_LOCK = threading.Lock()
_EXEC_ACTIVE = 0
_EXEC_MAX = 0
_EXEC_ORDER: list[str] = []


def _reset_counters() -> None:
    global _EXEC_ACTIVE, _EXEC_MAX
    with _EXEC_LOCK:
        _EXEC_ACTIVE = 0
        _EXEC_MAX = 0
        _EXEC_ORDER.clear()


# -- synthetic in-process participant (orchestration only) -------------------


def _prepare(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    case_dir.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(
        {key: inputs[key] for key in sorted(inputs)}, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    (case_dir / "case.json").write_text(canonical, encoding="utf-8")
    return PrepareReceipt(
        participant_id="perf02-tiny",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail="perf02 synthetic participant",
    )


def _execute(inputs: dict[str, object], case_dir: Path) -> None:
    global _EXEC_ACTIVE, _EXEC_MAX
    sleep_s = float(inputs.get("sleep_s", 0.0))
    with _EXEC_LOCK:
        _EXEC_ACTIVE += 1
        _EXEC_MAX = max(_EXEC_MAX, _EXEC_ACTIVE)
        _EXEC_ORDER.append(str(inputs.get("seed")))
    try:
        if sleep_s > 0:
            time.sleep(sleep_s)
        (case_dir / "result.json").write_text(
            json.dumps({"value": 1.0}), encoding="utf-8"
        )
    finally:
        with _EXEC_LOCK:
            _EXEC_ACTIVE -= 1


def _parse(case_dir: Path) -> ParseReceipt:
    data = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    return ParseReceipt(
        participant_id="perf02-tiny",
        parser="test_perf02_scheduling:_parse",
        scalars={"value": float(data["value"])},
        units={"value": "dimensionless"},
    )


def _validate(scalars: dict[str, float], inputs: dict[str, object]) -> ValidityReport:
    _ = (scalars, inputs)
    return ValidityReport(
        participant_id="perf02-tiny", passed=True, checks={"finite": True}, detail="ok"
    )


def _ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    from participants import lifecycle as lifecycle_mod
    from participants import manifest as manifest_mod
    from participants.manifest import ExecutableCapability, ParticipantManifest, PortSpec
    from participants.receipts import CapabilityProbe

    manifest = ParticipantManifest(
        participant_id="perf02-tiny",
        physics_domain="performance",
        manifest_version=manifest_mod.MANIFEST_VERSION,
        description="PERF 02 test participant: scheduler behavior only.",
        inputs=(
            PortSpec("seed", "scalar", "int", "dimensionless", "in"),
            PortSpec("sleep_s", "scalar", "float", "s", "in"),
        ),
        outputs=(PortSpec("value", "scalar", "float", "dimensionless", "out"),),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        coupling_direction="none",
        convergence_measures=("residual",),
        fidelity_levels=("perf",),
        executable=ExecutableCapability("test-perf", ("test-perf",), "in-process"),
        prepare_ref="test_perf02_scheduling:_prepare",
        execute_ref="test_perf02_scheduling:_execute",
        parser_ref="test_perf02_scheduling:_parse",
        validity_ref="test_perf02_scheduling:_validate",
        artifacts=("result.json",),
        checkpoint=False,
        benchmark_ref="perf-02",
    )
    manifest_mod._REGISTRY["perf02-tiny"] = manifest
    lifecycle_mod._ALLOWED_MODULES = frozenset(
        set(lifecycle_mod._ALLOWED_MODULES) | {"test_perf02_scheduling"}
    )
    original_probe = lifecycle_mod.probe_participant

    def _probe(participant_id: str) -> CapabilityProbe:
        if participant_id == "perf02-tiny":
            return CapabilityProbe(
                participant_id, "test-perf", "test-perf", "ready", "test", "perf02 synthetic"
            )
        return original_probe(participant_id)

    lifecycle_mod.probe_participant = _probe
    _REGISTERED = True


def _profile(job_id: str, *, memory: float = 64.0, **kwargs: Any) -> JobProfile:
    base: dict[str, Any] = {
        "job_id": job_id,
        "participant_id": "perf02-tiny",
        "solver_id": "test-perf",
        "execution_mode": "in-process",
        "memory_mib": memory,
    }
    base.update(kwargs)
    return JobProfile(**base)


def _manager(tmp_path: Path, **kwargs: Any) -> NativeJobManager:
    _ensure_registered()
    policy = SolverResourcePolicy(max_concurrency=4, memory_mib=64.0)
    kwargs.setdefault("max_active_jobs", 4)
    return NativeJobManager(
        tmp_path / "jobs",
        solver_policies={"test-perf": policy},
        **kwargs,
    )


def _wait_terminal(manager: NativeJobManager, job_id: str, timeout_s: float = 30.0) -> str:
    deadline = time.monotonic() + timeout_s
    state = manager.status(job_id)["state"]
    while state not in TERMINAL:
        assert time.monotonic() < deadline, f"job stuck in {state}"
        time.sleep(0.01)
        state = manager.status(job_id)["state"]
    return state


# -- A/B. concurrency + conservative defaults --------------------------------


def test_independent_inprocess_jobs_overlap(tmp_path: Path) -> None:
    _reset_counters()
    manager = _manager(tmp_path)
    try:
        job_ids = manager.submit_batch(
            [JobRequest("perf02-tiny", {"seed": index, "sleep_s": 0.3}) for index in range(4)]
        )
        assert len(job_ids) == 4
        for job_id in job_ids:
            assert _wait_terminal(manager, job_id) == JobState.COMPLETED.value
        metrics = manager.scheduler_metrics()
        assert _EXEC_MAX >= 2, "independent in-process jobs did not overlap"
        assert int(metrics["peak_active_jobs"]) >= 2
        assert float(metrics["peak_reservation_mib"]) <= 896.0
    finally:
        manager.close()


def test_concurrent_overhead_is_materially_lower_than_serialized(
    tmp_path: Path, capsys: Any
) -> None:
    _reset_counters()
    batch = [
        JobRequest("perf02-tiny", {"seed": index, "sleep_s": 0.3}) for index in range(4)
    ]

    serial_manager = _manager(tmp_path / "serial", max_active_jobs=1)
    try:
        start = time.perf_counter()
        serial_ids = serial_manager.submit_batch(batch)
        for job_id in serial_ids:
            assert _wait_terminal(serial_manager, job_id) == JobState.COMPLETED.value
        serial_ms = (time.perf_counter() - start) * 1000.0
    finally:
        serial_manager.close()

    _reset_counters()
    concurrent_manager = _manager(tmp_path / "concurrent", max_active_jobs=4)
    try:
        start = time.perf_counter()
        parallel_ids = concurrent_manager.submit_batch(batch)
        for job_id in parallel_ids:
            assert _wait_terminal(concurrent_manager, job_id) == JobState.COMPLETED.value
        concurrent_ms = (time.perf_counter() - start) * 1000.0
        metrics = concurrent_manager.scheduler_metrics()
    finally:
        concurrent_manager.close()

    with capsys.disabled():
        print(
            f"\n[perf02] 4x300ms: serialized={serial_ms:.1f} ms, "
            f"concurrent={concurrent_ms:.1f} ms, "
            f"peak_active={metrics['peak_active_jobs']}"
        )
    assert metrics["peak_active_jobs"] >= 2
    assert concurrent_ms < serial_ms * 0.75


def test_scheduler_memory_reservation_prevents_unsafe_overlap() -> None:
    scheduler = ResourceScheduler(aggregate_memory_mib=896.0, max_active_jobs=4)
    first = _profile("mem-a", memory=600.0)
    second = _profile("mem-b", memory=600.0)
    assert scheduler.acquire(first) is True
    admitted = Event()

    def worker() -> None:
        if scheduler.acquire(second):
            admitted.set()
        scheduler.release(second.job_id)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert not admitted.wait(0.25), "600+600 MiB must not both be admitted"
    finally:
        scheduler.release(first.job_id)
    assert admitted.wait(2.0), "second job never admitted after memory freed"
    thread.join(2.0)
    assert float(scheduler.metrics()["peak_reservation_mib"]) <= 896.0


def test_exclusive_job_serializes_against_normal_jobs() -> None:
    scheduler = ResourceScheduler(aggregate_memory_mib=896.0, max_active_jobs=4)
    exclusive = _profile("exclusive", memory=64.0, exclusive=True)
    normal = _profile("normal", memory=64.0)
    assert scheduler.acquire(exclusive) is True
    admitted = Event()

    def worker() -> None:
        if scheduler.acquire(normal):
            admitted.set()
        scheduler.release(normal.job_id)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert not admitted.wait(0.25), "a normal job ran while an exclusive job was active"
    finally:
        scheduler.release(exclusive.job_id)
    assert admitted.wait(2.0)
    thread.join(2.0)


def test_per_solver_concurrency_cap_is_honored() -> None:
    scheduler = ResourceScheduler(aggregate_memory_mib=896.0, max_active_jobs=4)
    first = _profile("cap-a", memory=64.0, max_concurrency=1)
    second = _profile("cap-b", memory=64.0, max_concurrency=1)
    assert scheduler.acquire(first) is True
    admitted = Event()

    def worker() -> None:
        if scheduler.acquire(second):
            admitted.set()
        scheduler.release(second.job_id)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert not admitted.wait(0.25)
    finally:
        scheduler.release(first.job_id)
    assert admitted.wait(2.0)
    thread.join(2.0)


# -- C. deterministic bounded fairness ---------------------------------------


def test_promoted_job_is_not_starved_by_a_cheap_stream() -> None:
    scheduler = ResourceScheduler(
        aggregate_memory_mib=128.0, max_active_jobs=1, aging_after_skips=1
    )
    blocker = _profile("blocker", memory=128.0)
    assert scheduler.acquire(blocker) is True
    high = _profile("high", memory=128.0, priority=5)
    cheap_one = _profile("cheap-1", memory=128.0)
    cheap_two = _profile("cheap-2", memory=128.0)

    order: list[str] = []
    events = {name: Event() for name in ("high", "cheap-1", "cheap-2")}

    def worker(profile: JobProfile) -> None:
        if scheduler.acquire(profile):
            order.append(profile.job_id)
            events[profile.job_id].set()

    threads = [
        threading.Thread(target=worker, args=(profile,))
        for profile in (high, cheap_one, cheap_two)
    ]
    for thread in threads:
        thread.start()
    time.sleep(0.05)
    scheduler.release(blocker.job_id)
    try:
        assert events["high"].wait(2.0), "promoted job was not admitted first"
        assert not events["cheap-1"].is_set() and not events["cheap-2"].is_set()
        scheduler.release("high")
        assert events["cheap-1"].wait(2.0)
        scheduler.release("cheap-1")
        assert events["cheap-2"].wait(2.0)
    finally:
        scheduler.release("cheap-2")
        scheduler.release("high")
        scheduler.release("cheap-1")
    for thread in threads:
        thread.join(2.0)
    assert order == ["high", "cheap-1", "cheap-2"]


# -- cancellation priority ---------------------------------------------------


def test_queued_waiter_is_cancelled_promptly() -> None:
    scheduler = ResourceScheduler(aggregate_memory_mib=64.0, max_active_jobs=1)
    holder = _profile("holder", memory=64.0)
    assert scheduler.acquire(holder) is True
    target = _profile("target", memory=64.0)
    cancel = Event()
    result: dict[str, bool] = {}

    def worker() -> None:
        result["admitted"] = scheduler.acquire(target, cancel)

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(0.1)
    cancel.set()
    thread.join(2.0)
    assert result.get("admitted") is False
    scheduler.release(holder.job_id)


def test_scheduler_metrics_are_recorded() -> None:
    scheduler = ResourceScheduler(aggregate_memory_mib=896.0, max_active_jobs=4)
    profile = _profile("metrics", memory=64.0)
    assert scheduler.acquire(profile) is True
    time.sleep(0.05)
    scheduler.release(profile.job_id)
    metrics = scheduler.metrics()
    assert metrics["admitted_total"] == 1
    assert metrics["peak_active_jobs"] == 1
    assert metrics["queue_delay_samples"] == 1
    assert metrics["queue_delay_max_ms"] >= 0.0
    assert metrics["busy_ms"] > 0.0
    assert 0.0 <= float(metrics["utilization"]) <= 1.0
    assert metrics["active_reservation_mib"] == 0.0


# -- D. recovery / no duplicate execution ------------------------------------


def test_run_never_executes_a_terminal_job_twice(tmp_path: Path) -> None:
    _reset_counters()
    manager = _manager(tmp_path)
    try:
        job_id = manager.submit("perf02-tiny", {"seed": 1, "sleep_s": 0.05}, deferred=True)
        manager._ledger.update(
            job_id, state=JobState.COMPLETED.value, updated_at=datetime.now(UTC).isoformat()
        )
        assert manager.run(job_id) == JobState.COMPLETED.value
        assert _EXEC_ORDER == [], "a terminal job was executed again"
    finally:
        manager.close()


def test_concurrent_run_calls_execute_a_queued_job_once(tmp_path: Path) -> None:
    _reset_counters()
    manager = _manager(tmp_path)
    try:
        job_id = manager.submit("perf02-tiny", {"seed": 7, "sleep_s": 0.2}, deferred=True)
        results: list[str] = []
        threads = [
            threading.Thread(target=lambda: results.append(manager.run(job_id)))
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30.0)
        assert _wait_terminal(manager, job_id) == JobState.COMPLETED.value
        assert _EXEC_ORDER.count("7") == 1
    finally:
        manager.close()


def test_restart_keeps_terminal_terminal_and_queued_resumable(tmp_path: Path) -> None:
    _ensure_registered()
    root = tmp_path / "jobs"
    policy = SolverResourcePolicy(max_concurrency=4, memory_mib=64.0)
    manager = NativeJobManager(root, solver_policies={"test-perf": policy})
    try:
        completed = manager.submit("perf02-tiny", {"seed": 2, "sleep_s": 0.0}, deferred=True)
        assert manager.run(completed) == JobState.COMPLETED.value
        queued = manager.submit("perf02-tiny", {"seed": 3, "sleep_s": 0.0}, deferred=True)
    finally:
        manager.close()

    revived = NativeJobManager(root, solver_policies={"test-perf": policy})
    try:
        assert revived.status(completed)["state"] == JobState.COMPLETED.value
        assert revived.status(queued)["state"] == JobState.QUEUED.value
        assert revived.run(queued) == JobState.COMPLETED.value
    finally:
        revived.close()


# -- E. batch submission + completion consumption ----------------------------


def test_batch_submission_and_completion_cursor(tmp_path: Path) -> None:
    _reset_counters()
    manager = _manager(tmp_path)
    try:
        job_ids = manager.submit_batch(
            [JobRequest("perf02-tiny", {"seed": index, "sleep_s": 0.05}) for index in range(3)]
        )
        for job_id in job_ids:
            assert _wait_terminal(manager, job_id) == JobState.COMPLETED.value
        completions = manager.completions_since(0)
        assert {item["job_id"] for item in completions} == set(job_ids)
        assert all(item["state"] == JobState.COMPLETED.value for item in completions)
        cursor = max(int(item["sequence"]) for item in completions)
        assert manager.completions_since(cursor) == ()
    finally:
        manager.close()


def test_invalid_batch_is_cancelled_before_the_error_propagates(tmp_path: Path) -> None:
    _ensure_registered()
    manager = _manager(tmp_path)
    try:
        with pytest.raises(ValueError, match="INVALID_JOB_INPUTS"):
            manager.submit_batch(
                [
                    JobRequest("perf02-tiny", {"seed": 1}),
                    JobRequest("perf02-tiny", {"seed": 2}, fidelity="not-a-level"),
                ]
            )
        assert manager._scheduler.metrics()["admitted_total"] == 0
    finally:
        manager.close()
