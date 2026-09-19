"""INFRA-FIX 04: checkpoint, preemption, retry, and trusted resume semantics.

All transports are deterministic and cost $0. The tests prove that resume is
fail-closed, bounded, and never bypasses budget/security/result-validation.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest
from participants import lifecycle as lifecycle_mod
from participants import manifest as manifest_mod
from participants.checkpoints import (
    CheckpointArtifact,
    CheckpointReceipt,
    RetryClass,
    RetryPolicy,
    classify_failure,
    make_checkpoint_receipt,
    verify_resume_compatibility,
)
from participants.errors import GovernanceErrorCode, NativeErrorCode, ParticipantError
from participants.executors import (
    ExecutionPlan,
    FakeRemoteExecutor,
    FakeRemoteScript,
)
from participants.lifecycle import JobState, NativeJobManager
from participants.manifest import (
    CheckpointMode,
    ExecutableCapability,
    ParticipantManifest,
    PortSpec,
)
from participants.receipts import CapabilityProbe, ParseReceipt, PrepareReceipt, ValidityReport
from participants.remote_policy import RemoteComputePolicy, RemoteLimits

PARTICIPANT = "infra-checkpoint-tiny"
_IMAGE = "sha256:" + "b" * 64
_CKPT_BYTES = b"ckpt-bytes-v1"
_RESULT_BYTES = b'{"value": 9.0}'
_REGISTERED = False


def _prepare(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    canonical = {"seed": int(inputs.get("seed", 1))}  # type: ignore[arg-type]
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(json.dumps(canonical), encoding="utf-8")
    return PrepareReceipt(
        participant_id=PARTICIPANT,
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        geometry_hash=hashlib.sha256(b"geom-a").hexdigest(),
        mesh_hash=hashlib.sha256(b"mesh-a").hexdigest(),
    )


def _execute(inputs: dict[str, object], case_dir: Path) -> None:
    value = float(inputs.get("seed", 1)) + 1.0  # type: ignore[arg-type]
    (case_dir / "result.json").write_text(json.dumps({"value": value}), encoding="utf-8")


def _parse(case_dir: Path) -> ParseReceipt:
    data = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    return ParseReceipt(
        participant_id=PARTICIPANT,
        parser=f"{__name__}:_parse",
        scalars={"value": float(data["value"])},
        units={"value": "dimensionless"},
    )


def _validate(scalars: dict[str, float], inputs: dict[str, object]) -> ValidityReport:
    _ = inputs
    value = float(scalars.get("value", float("nan")))
    finite = value == value and value not in (float("inf"), float("-inf"))
    return ValidityReport(
        participant_id=PARTICIPANT,
        passed=finite,
        checks={"finite": finite},
        detail="tiny checkpoint participant",
    )


def _register() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    manifest = ParticipantManifest(
        participant_id=PARTICIPANT,
        physics_domain="test",
        manifest_version=manifest_mod.MANIFEST_VERSION,
        description="Tiny governed participant for checkpoint/resume tests.",
        inputs=(PortSpec("seed", "scalar", "int", "dimensionless", "in"),),
        outputs=(PortSpec("value", "scalar", "float", "dimensionless", "out"),),
        geometry_roles=(("solid_region",)),
        mesh_roles=(("solid",)),
        semantic_requirements=(),
        coupling_direction="none",
        convergence_measures=("residual",),
        fidelity_levels=("tiny",),
        executable=ExecutableCapability("infra-checkpoint", ("infra-checkpoint",), "in-process"),
        prepare_ref=f"{__name__}:_prepare",
        execute_ref=f"{__name__}:_execute",
        parser_ref=f"{__name__}:_parse",
        validity_ref=f"{__name__}:_validate",
        artifacts=("result.json",),
        checkpoint=True,
        checkpoint_policy=CheckpointMode.PERIODIC,
        benchmark_ref="infra-fix-04",
    )
    manifest_mod._REGISTRY[PARTICIPANT] = manifest
    lifecycle_mod._ALLOWED_MODULES = frozenset(
        set(lifecycle_mod._ALLOWED_MODULES) | {__name__}
    )
    original = lifecycle_mod.probe_participant

    def _probe(participant_id: str) -> CapabilityProbe:
        if participant_id == PARTICIPANT:
            return CapabilityProbe(
                participant_id,
                "infra-checkpoint",
                "infra-checkpoint",
                "ready",
                "test-1",
                "tiny checkpoint participant",
            )
        return original(participant_id)

    lifecycle_mod.probe_participant = _probe
    _REGISTERED = True


@pytest.fixture(autouse=True)
def _registered() -> None:
    _register()


def _policy() -> RemoteComputePolicy:
    return RemoteComputePolicy(
        enabled=True,
        limits=RemoteLimits(
            max_job_cost_usd=0.15,
            max_session_cost_usd=0.49,
            allowed_image_digests=(_IMAGE,),
        ),
    )


def _checkpoint(plan: ExecutionPlan, *, input_hash: str | None = None) -> CheckpointReceipt:
    declared_hash = hashlib.sha256(_CKPT_BYTES).hexdigest()
    return make_checkpoint_receipt(
        job_id=plan.job_id,
        run_id=f"run-{plan.job_id}",
        participant_id=plan.participant_id,
        solver_id=plan.solver_id,
        solver_version=plan.solver_version,
        input_hash=input_hash or plan.input_hash,
        geometry_hash=hashlib.sha256(b"geom-a").hexdigest(),
        mesh_hash=hashlib.sha256(b"mesh-a").hexdigest(),
        image_digest=plan.image_digest,
        sequence=1,
        created_at="2026-01-01T00:00:00+00:00",
        artifacts=(CheckpointArtifact("state.bin", declared_hash, len(_CKPT_BYTES)),),
        detail="periodic checkpoint",
    )


def _script_factory(plan: ExecutionPlan) -> FakeRemoteScript:
    if plan.resume_of is None:
        return FakeRemoteScript(
            states=("running", "preempted"),
            artifacts={"state.bin": _CKPT_BYTES},
            preempted=True,
            interruption_reason="SPOT_PREEMPTED",
            actual_cost_usd=0.0,
        )
    return FakeRemoteScript(
        states=("running", "completed"),
        artifacts={"result.json": _RESULT_BYTES},
        actual_cost_usd=0.0,
    )


def _executor(
    *, checkpoint_factory: Any = None, script_factory: Any = None
) -> FakeRemoteExecutor:
    return FakeRemoteExecutor(
        script_factory=script_factory or _script_factory,
        checkpoint_factory=checkpoint_factory or _checkpoint,
    )


def _manager(
    root: Path,
    executor: FakeRemoteExecutor,
    *,
    retry_policy: RetryPolicy | None = None,
    session_spent_usd: float = 0.0,
) -> NativeJobManager:
    return NativeJobManager(
        root,
        execution_backend="remote",
        remote_policy=_policy(),
        remote_executor=executor,
        retry_policy=retry_policy,
        session_spent_usd=session_spent_usd,
    )


def _wait(manager: NativeJobManager, job_id: str, timeout_s: float = 15.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        status = manager.status(job_id)
        terminal = {
            JobState.COMPLETED.value,
            JobState.FAILED.value,
            JobState.CANCELLED.value,
        }
        if status["state"] in terminal:
            return status
        if time.monotonic() > deadline:
            raise TimeoutError(f"job {job_id} stuck in {status['state']}")
        time.sleep(0.02)


def _preempt(manager: NativeJobManager) -> str:
    job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
    assert manager.run(job_id) == JobState.FAILED.value
    status = manager.status(job_id)
    assert status["error_code"] == GovernanceErrorCode.PREEMPTED.value
    assert status["checkpoint_id"]
    assert status["interruption_reason"] == "SPOT_PREEMPTED"
    return job_id


# -- A. trusted resume --------------------------------------------------------


def test_valid_checkpoint_resumes_with_separate_provenance(tmp_path: Path) -> None:
    manager = _manager(tmp_path / "jobs", _executor())
    try:
        job_id = _preempt(manager)
        checkpoints = manager._load_checkpoints(job_id)
        assert len(checkpoints) == 1
        assert checkpoints[0].mesh_hash == hashlib.sha256(b"mesh-a").hexdigest()

        resumed_id = manager.resume(job_id)
        assert resumed_id != job_id
        resumed = _wait(manager, resumed_id)
        assert resumed["state"] == JobState.COMPLETED.value
        assert resumed["resume_of"] == job_id
        assert resumed["attempt"] == 2
        assert resumed["checkpoint_id"] == checkpoints[0].checkpoint_id
        envelope = manager.envelope(resumed_id)
        assert envelope["scalars"]["value"] == 9.0

        # The original attempt stays FAILED; history is never rewritten.
        assert manager.status(job_id)["state"] == JobState.FAILED.value
        original_events = [e["event_type"] for e in manager.provenance(job_id)]
        assert "native.checkpoint-recorded" in original_events
        resumed_events = [e["event_type"] for e in manager.provenance(resumed_id)]
        assert resumed_events == ["native.launch-accepted", "native.result-recorded"]
    finally:
        manager.close()


def test_changed_mesh_rejects_resume(tmp_path: Path) -> None:
    def _changed_mesh(plan: ExecutionPlan) -> CheckpointReceipt:
        return make_checkpoint_receipt(
            job_id=plan.job_id,
            run_id=f"run-{plan.job_id}",
            participant_id=plan.participant_id,
            solver_id=plan.solver_id,
            solver_version=plan.solver_version,
            input_hash=plan.input_hash,
            geometry_hash=hashlib.sha256(b"geom-a").hexdigest(),
            mesh_hash=hashlib.sha256(b"mesh-b").hexdigest(),
            image_digest=plan.image_digest,
            sequence=1,
            created_at="2026-01-01T00:00:00+00:00",
            artifacts=(
                CheckpointArtifact(
                    "state.bin", hashlib.sha256(_CKPT_BYTES).hexdigest(), len(_CKPT_BYTES)
                ),
            ),
        )

    manager = _manager(tmp_path / "jobs", _executor(checkpoint_factory=_changed_mesh))
    try:
        job_id = _preempt(manager)
        with pytest.raises(ParticipantError) as excinfo:
            manager.resume(job_id)
        assert excinfo.value.code == GovernanceErrorCode.CHECKPOINT_INCOMPATIBLE
    finally:
        manager.close()


def test_changed_input_rejects_resume(tmp_path: Path) -> None:
    def _bad_input(plan: ExecutionPlan) -> CheckpointReceipt:
        return _checkpoint(plan, input_hash="0" * 64)

    manager = _manager(
        tmp_path / "jobs", _executor(checkpoint_factory=_bad_input)
    )
    try:
        job_id = _preempt(manager)
        with pytest.raises(ParticipantError) as excinfo:
            manager.resume(job_id)
        assert excinfo.value.code == GovernanceErrorCode.CHECKPOINT_INCOMPATIBLE
    finally:
        manager.close()


def test_corrupted_checkpoint_hash_rejects_resume(tmp_path: Path) -> None:
    def _corrupt_checkpoint(plan: ExecutionPlan) -> CheckpointReceipt:
        return make_checkpoint_receipt(
            job_id=plan.job_id,
            run_id=f"run-{plan.job_id}",
            participant_id=plan.participant_id,
            solver_id=plan.solver_id,
            solver_version=plan.solver_version,
            input_hash=plan.input_hash,
            geometry_hash=hashlib.sha256(b"geom-a").hexdigest(),
            mesh_hash=hashlib.sha256(b"mesh-a").hexdigest(),
            image_digest=plan.image_digest,
            sequence=1,
            created_at="2026-01-01T00:00:00+00:00",
            artifacts=(
                CheckpointArtifact(
                    "state.bin", hashlib.sha256(b"not-the-bytes").hexdigest(), 13
                ),
            ),
        )

    manager = _manager(
        tmp_path / "jobs", _executor(checkpoint_factory=_corrupt_checkpoint)
    )
    try:
        job_id = _preempt(manager)
        with pytest.raises(ParticipantError) as excinfo:
            manager.resume(job_id)
        assert excinfo.value.code == GovernanceErrorCode.CHECKPOINT_CORRUPT
    finally:
        manager.close()


def test_compatibility_rules_reject_changed_mesh_version_and_lineage() -> None:
    receipt = make_checkpoint_receipt(
        job_id="job-1",
        run_id="run-1",
        participant_id=PARTICIPANT,
        solver_id="infra-checkpoint",
        solver_version="v1",
        input_hash=hashlib.sha256(b"input").hexdigest(),
        mesh_hash=hashlib.sha256(b"mesh-a").hexdigest(),
        sequence=1,
        created_at="2026-01-01T00:00:00+00:00",
        artifacts=(
            CheckpointArtifact("state.bin", hashlib.sha256(b"state").hexdigest(), 5),
        ),
    )
    live = {artifact.name: artifact.sha256 for artifact in receipt.artifacts}
    changed_mesh = verify_resume_compatibility(
        receipt,
        expected_input_hash=receipt.input_hash,
        expected_solver_id="infra-checkpoint",
        expected_mesh_hash=hashlib.sha256(b"mesh-b").hexdigest(),
        live_artifact_hashes=live,
    )
    assert not changed_mesh.ok and changed_mesh.reason == "CHANGED_MESH"
    bad_version = verify_resume_compatibility(
        receipt,
        expected_input_hash=receipt.input_hash,
        expected_solver_id="infra-checkpoint",
        expected_solver_version="v2",
        live_artifact_hashes=live,
    )
    assert not bad_version.ok and bad_version.reason == "INCOMPATIBLE_SOLVER_VERSION"
    invalid_lineage = verify_resume_compatibility(
        receipt,
        expected_input_hash=receipt.input_hash,
        expected_solver_id="infra-checkpoint",
        live_artifact_hashes=live,
        lineage_ok=False,
    )
    assert not invalid_lineage.ok and invalid_lineage.reason == "INVALID_LINEAGE"


# -- B/C/D. cancellation, budget, bounded retry -------------------------------


def test_cancelled_job_cannot_resume(tmp_path: Path) -> None:
    manager = NativeJobManager(tmp_path / "jobs")
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
        assert manager.cancel(job_id) == JobState.CANCELLED.value
        with pytest.raises(ParticipantError) as excinfo:
            manager.resume(job_id)
        assert excinfo.value.code == GovernanceErrorCode.RESUME_REJECTED
    finally:
        manager.close()


def test_budget_exhausted_resume_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    executor = _executor()
    manager = _manager(root, executor)
    job_id = _preempt(manager)
    manager.close()

    broke = _manager(root, executor, session_spent_usd=0.49)
    try:
        with pytest.raises(ParticipantError) as excinfo:
            broke.resume(job_id)
        assert excinfo.value.code in {
            GovernanceErrorCode.COST_LIMIT_EXCEEDED,
            GovernanceErrorCode.RESUME_REJECTED,
        }
    finally:
        broke.close()


def test_retry_policy_is_bounded_and_reason_aware() -> None:
    assert (
        classify_failure(GovernanceErrorCode.PREEMPTED) is RetryClass.INFRASTRUCTURE_TRANSIENT
    )
    assert classify_failure(NativeErrorCode.QUALITY_GATE_FAILED) is RetryClass.SOLVER_DIVERGENCE
    assert classify_failure(NativeErrorCode.CANCELLED) is RetryClass.USER_CANCELLATION
    assert (
        classify_failure(GovernanceErrorCode.COST_LIMIT_EXCEEDED)
        is RetryClass.BUDGET_EXHAUSTION
    )

    policy = RetryPolicy(
        max_attempts=2,
        auto_resume_classes=frozenset({RetryClass.INFRASTRUCTURE_TRANSIENT}),
    )
    assert policy.may_retry(RetryClass.INFRASTRUCTURE_TRANSIENT, 1)
    assert not policy.may_retry(RetryClass.INFRASTRUCTURE_TRANSIENT, 2)
    assert not policy.may_retry(RetryClass.SOLVER_DIVERGENCE, 1)


def test_bounded_auto_resume_after_transient_preemption(tmp_path: Path) -> None:
    policy = RetryPolicy(
        max_attempts=2,
        auto_resume_classes=frozenset({RetryClass.INFRASTRUCTURE_TRANSIENT}),
    )
    manager = _manager(tmp_path / "jobs", _executor(), retry_policy=policy)
    try:
        job_id = _preempt(manager)
        # Auto-resume creates exactly one linked attempt and then stops.
        deadline = time.monotonic() + 15.0
        rows = manager._ledger.all()
        while len(rows) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
            rows = manager._ledger.all()
        assert len(rows) == 2, "retry loop was not bounded to a single resume"
        resumed = next(row for row in rows if row.resume_of == job_id)
        assert resumed.attempt == 2
        assert _wait(manager, resumed.job_id)["state"] == JobState.COMPLETED.value
    finally:
        manager.close()
