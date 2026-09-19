"""INFRA-FIX 03: governed remote execution through the scheduler/envelope path.

Every test here is deterministic and spends $0: the remote transport is the
in-memory ``FakeRemoteExecutor``. The real GCP backend is exercised only for
its fail-closed gates.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from participants import lifecycle as lifecycle_mod
from participants import manifest as manifest_mod
from participants.errors import GovernanceErrorCode, NativeErrorCode, ParticipantError
from participants.executors import (
    ExecutionPlan,
    FakeRemoteExecutor,
    FakeRemoteScript,
    GCPBatchExecutor,
)
from participants.lifecycle import JobState, NativeJobManager
from participants.manifest import (
    CheckpointMode,
    ExecutableCapability,
    ParticipantManifest,
    PortSpec,
)
from participants.receipts import CapabilityProbe, ParseReceipt, PrepareReceipt, ValidityReport
from participants.remote_policy import (
    RemoteComputePolicy,
    RemoteLimits,
    RemoteResourceRequest,
)

PARTICIPANT = "infra-remote-tiny"
_IMAGE = "sha256:" + "a" * 64
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
        detail="tiny remote participant",
    )


def _register() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    manifest = ParticipantManifest(
        participant_id=PARTICIPANT,
        physics_domain="test",
        manifest_version=manifest_mod.MANIFEST_VERSION,
        description="Tiny governed participant for remote-executor tests.",
        inputs=(PortSpec("seed", "scalar", "int", "dimensionless", "in"),),
        outputs=(PortSpec("value", "scalar", "float", "dimensionless", "out"),),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        coupling_direction="none",
        convergence_measures=("residual",),
        fidelity_levels=("tiny",),
        executable=ExecutableCapability("infra-test", ("infra-test",), "in-process"),
        prepare_ref=f"{__name__}:_prepare",
        execute_ref=f"{__name__}:_execute",
        parser_ref=f"{__name__}:_parse",
        validity_ref=f"{__name__}:_validate",
        artifacts=("result.json",),
        checkpoint=True,
        checkpoint_policy=CheckpointMode.PERIODIC,
        benchmark_ref="infra-fix-03",
    )
    manifest_mod._REGISTRY[PARTICIPANT] = manifest
    lifecycle_mod._ALLOWED_MODULES = frozenset(
        set(lifecycle_mod._ALLOWED_MODULES) | {__name__}
    )
    original = lifecycle_mod.probe_participant

    def _probe(participant_id: str) -> CapabilityProbe:
        if participant_id == PARTICIPANT:
            return CapabilityProbe(
                participant_id, "infra-test", "infra-test", "ready", "test-1", "tiny participant"
            )
        return original(participant_id)

    lifecycle_mod.probe_participant = _probe
    _REGISTERED = True


@pytest.fixture(autouse=True)
def _registered() -> None:
    _register()


def _enabled_policy(**limit_overrides: Any) -> RemoteComputePolicy:
    limits = RemoteLimits(
        max_job_cost_usd=0.15,
        max_session_cost_usd=0.49,
        allowed_image_digests=(_IMAGE,),
        **limit_overrides,
    )
    return RemoteComputePolicy(enabled=True, limits=limits)


def _completed_executor(payload: bytes = b'{"value": 7.0}') -> FakeRemoteExecutor:
    return FakeRemoteExecutor(
        script=FakeRemoteScript(
            states=("running", "completed"),
            artifacts={"result.json": payload},
        )
    )


def _remote_manager(
    root: Path, executor: FakeRemoteExecutor, policy: RemoteComputePolicy | None = None
) -> NativeJobManager:
    return NativeJobManager(
        root,
        execution_backend="remote",
        remote_policy=policy or _enabled_policy(),
        remote_executor=executor,
    )


def _local_manager(root: Path) -> NativeJobManager:
    return NativeJobManager(root)


# -- A. one execution contract ------------------------------------------------


def test_remote_run_uses_the_same_lifecycle_and_envelope(tmp_path: Path) -> None:
    manager = _remote_manager(tmp_path / "jobs", _completed_executor())
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
        assert manager.run(job_id) == JobState.COMPLETED.value
        states = [event["state"] for event in manager.events(job_id)]
        assert states == [
            JobState.QUEUED.value,
            JobState.PREPARING.value,
            JobState.RUNNING.value,
            JobState.PARSING.value,
            JobState.VALIDATING.value,
            JobState.COMPLETED.value,
        ]
        envelope = manager.envelope(job_id)
        assert envelope["source"] == "native_solver"
        assert envelope["solver_identity"] == "infra-test"
        assert envelope["validity"]["passed"] is True
        assert envelope["scalars"]["value"] == 7.0
        artifact_names = {artifact["name"] for artifact in envelope["artifacts"]}
        assert "result.json" in artifact_names
        assert {"stdout.log", "stderr.log"} <= artifact_names
        status = manager.status(job_id)
        assert status["executor"] == "remote"
        assert status["run_id"] == envelope["run_id"]
    finally:
        manager.close()


def test_remote_worker_evidence_is_verified_before_publication(tmp_path: Path) -> None:
    executor = FakeRemoteExecutor(
        script=FakeRemoteScript(
            states=("running", "completed"),
            artifacts={"result.json": b'{"value": 1.0}'},
            solver_identity_override="impostor-solver",
        )
    )
    manager = _remote_manager(tmp_path / "jobs", executor)
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
        assert manager.run(job_id) == JobState.FAILED.value
        assert manager.status(job_id)["error_code"] == NativeErrorCode.RESULT_INVALID.value
        with pytest.raises(ParticipantError):
            manager.envelope(job_id)
    finally:
        manager.close()


# -- B. user-owned authorization ---------------------------------------------


def test_remote_is_impossible_unless_user_policy_enables_it(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as excinfo:
        NativeJobManager(
            tmp_path / "jobs",
            execution_backend="remote",
            remote_executor=_completed_executor(),
        )
    assert excinfo.value.code == NativeErrorCode.CAPABILITY_UNAVAILABLE

    executor = GCPBatchExecutor(RemoteComputePolicy.disabled(), project="p", region="us-central1")
    plan = ExecutionPlan(
        job_id="j1",
        participant_id=PARTICIPANT,
        solver_id="infra-test",
        solver_version="test-1",
        execution_mode="remote",
        case_id="case-j1",
        input_hash="0" * 64,
        case_dir=str(tmp_path),
    )
    with pytest.raises(ParticipantError) as gcp_exc:
        executor.run(plan)
    assert gcp_exc.value.code == NativeErrorCode.CAPABILITY_UNAVAILABLE


def test_gcp_backend_fails_closed_without_transport(tmp_path: Path) -> None:
    policy = _enabled_policy()
    executor = GCPBatchExecutor(
        policy, project="demo-project", region="us-central1", image_digest=_IMAGE
    )
    plan = ExecutionPlan(
        job_id="j2",
        participant_id=PARTICIPANT,
        solver_id="infra-test",
        solver_version="test-1",
        execution_mode="remote",
        case_id="case-j2",
        input_hash="0" * 64,
        case_dir=str(tmp_path),
        image_digest=_IMAGE,
        region="us-central1",
    )
    with pytest.raises(ParticipantError) as excinfo:
        executor.run(plan)
    assert excinfo.value.code == NativeErrorCode.CAPABILITY_UNAVAILABLE


def test_ai_tool_cannot_escalate_remote_or_cost_limits(tmp_path: Path) -> None:
    manager = _local_manager(tmp_path / "jobs")
    try:
        with pytest.raises(ParticipantError) as remote_exc:
            manager.submit(PARTICIPANT, {"seed": 1, "remote": True}, deferred=True)
        assert remote_exc.value.code == GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED
        with pytest.raises(ParticipantError) as cost_exc:
            manager.submit(PARTICIPANT, {"seed": 1, "costCeilingUsd": 5.0}, deferred=True)
        assert cost_exc.value.code == GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED
    finally:
        manager.close()


def test_resource_and_cost_escalation_rejected_before_launch(tmp_path: Path) -> None:
    policy = _enabled_policy()
    with pytest.raises(ParticipantError) as resource_exc:
        policy.assert_within_limits(
            RemoteResourceRequest(
                vcpu=64.0, memory_mib=4.0, wall_time_s=60.0, machine_type="e2-standard-2"
            )
        )
    assert resource_exc.value.code == GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED

    tight = RemoteComputePolicy(
        enabled=True,
        limits=RemoteLimits(
            max_job_cost_usd=0.000001,
            max_session_cost_usd=0.49,
            allowed_image_digests=(_IMAGE,),
        ),
    )
    manager = _remote_manager(tmp_path / "jobs", _completed_executor(), tight)
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
        assert manager.run(job_id) == JobState.FAILED.value
        assert manager.status(job_id)["error_code"] == GovernanceErrorCode.COST_LIMIT_EXCEEDED.value
    finally:
        manager.close()


# -- C. artifacts, cancellation, retry ---------------------------------------


def test_artifact_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    executor = FakeRemoteExecutor(
        script=FakeRemoteScript(
            states=("running", "completed"),
            artifacts={"result.json": b'{"value": 1.0}'},
            tamper_artifact="result.json",
        )
    )
    manager = _remote_manager(tmp_path / "jobs", executor)
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
        assert manager.run(job_id) == JobState.FAILED.value
        assert manager.status(job_id)["error_code"] == NativeErrorCode.RESULT_INVALID.value
        with pytest.raises(ParticipantError):
            manager.envelope(job_id)
    finally:
        manager.close()


def test_cancel_race_cannot_publish_success(tmp_path: Path) -> None:
    executor = FakeRemoteExecutor(
        script=FakeRemoteScript(
            states=("running", "running", "completed"),
            artifacts={"result.json": b'{"value": 1.0}'},
            late_success_after_cancel=True,
        )
    )
    manager = NativeJobManager(
        tmp_path / "jobs",
        execution_backend="remote",
        remote_policy=_enabled_policy(),
        remote_executor=executor,
        remote_poll_s=0.02,
    )
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)

        def _cancel_when_running() -> None:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if manager.status(job_id)["state"] == JobState.RUNNING.value:
                    manager.cancel(job_id)
                    return
                time.sleep(0.01)

        canceller = threading.Thread(target=_cancel_when_running, daemon=True)
        canceller.start()
        assert manager.run(job_id) == JobState.CANCELLED.value
        canceller.join(timeout=5.0)
        assert manager.status(job_id)["state"] == JobState.CANCELLED.value
        with pytest.raises(ParticipantError):
            manager.envelope(job_id)
    finally:
        manager.close()


def test_paid_job_never_retries_automatically(tmp_path: Path) -> None:
    executor = FakeRemoteExecutor(
        script=FakeRemoteScript(
            states=("running", "failed"),
            artifacts={"result.json": b'{"value": 1.0}'},
            actual_cost_usd=0.01,
        )
    )
    manager = _remote_manager(tmp_path / "jobs", executor)
    try:
        job_id = manager.submit(PARTICIPANT, {"seed": 1}, deferred=True)
        assert manager.run(job_id) == JobState.FAILED.value
        # One submission only: the default retry policy never resumes.
        assert len(executor._submitted) == 1
        assert manager.status(job_id)["resume_of"] is None
        # The paid attempt was accounted, never silently discarded or retried.
        assert manager._cost_ledger.spend(job_id) is not None
    finally:
        manager.close()
