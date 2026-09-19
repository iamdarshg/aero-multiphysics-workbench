"""INFRA-FIX 03/04 integration: one executor contract, local and remote.

Deterministic, $0: the remote transport is the in-memory fake. This proves the
scheduler routes both backends through the same envelope/provenance contract
while the real GCP backend fails closed without provisioning.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from participants import lifecycle as lifecycle_mod
from participants import manifest as manifest_mod
from participants.errors import NativeErrorCode, ParticipantError
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

PARTICIPANT = "infra-integration-tiny"
_IMAGE = "sha256:" + "d" * 64
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
        detail="tiny integration participant",
    )


def _register() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    manifest = ParticipantManifest(
        participant_id=PARTICIPANT,
        physics_domain="test",
        manifest_version=manifest_mod.MANIFEST_VERSION,
        description="Tiny governed participant for executor integration tests.",
        inputs=(PortSpec("seed", "scalar", "int", "dimensionless", "in"),),
        outputs=(PortSpec("value", "scalar", "float", "dimensionless", "out"),),
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        coupling_direction="none",
        convergence_measures=("residual",),
        fidelity_levels=("tiny",),
        executable=ExecutableCapability("infra-integration", ("infra-integration",), "in-process"),
        prepare_ref=f"{__name__}:_prepare",
        execute_ref=f"{__name__}:_execute",
        parser_ref=f"{__name__}:_parse",
        validity_ref=f"{__name__}:_validate",
        artifacts=("result.json",),
        checkpoint=True,
        checkpoint_policy=CheckpointMode.PERIODIC,
        benchmark_ref="infra-fix-integration",
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
                "infra-integration",
                "infra-integration",
                "ready",
                "test-1",
                "tiny integration participant",
            )
        return original(participant_id)

    lifecycle_mod.probe_participant = _probe
    _REGISTERED = True


@pytest.fixture(autouse=True)
def _registered() -> None:
    _register()


def _policy(enabled: bool = True) -> RemoteComputePolicy:
    return RemoteComputePolicy(
        enabled=enabled,
        limits=RemoteLimits(
            max_job_cost_usd=0.15,
            max_session_cost_usd=0.49,
            allowed_image_digests=(_IMAGE,),
        ),
    )


def test_fake_executor_implements_the_full_transport_contract(tmp_path: Path) -> None:
    executor = FakeRemoteExecutor(
        script=FakeRemoteScript(
            states=("running", "completed"),
            stdout=b"stdout\n",
            stderr=b"stderr\n",
            artifacts={"result.json": b'{"value": 5.0}'},
        )
    )
    plan = ExecutionPlan(
        job_id="j1",
        participant_id=PARTICIPANT,
        solver_id="infra-integration",
        solver_version="test-1",
        execution_mode="remote",
        case_id="case-j1",
        input_hash="0" * 64,
        case_dir=str(tmp_path),
        artifacts=("result.json",),
    )
    ref = executor.submit(plan)
    assert executor.poll(ref) == "running"
    assert executor.poll(ref) == "completed"
    assert executor.fetch_stdout(ref) == b"stdout\n"
    assert executor.fetch_stderr(ref) == b"stderr\n"
    assert set(executor.fetch_artifacts(ref)) == {"result.json"}
    receipt = executor.terminal_receipt(ref)
    assert receipt.state == "completed"
    assert receipt.execution_mode == "remote"
    assert receipt.input_hash == plan.input_hash
    assert receipt.artifacts[0].name == "result.json"
    assert receipt.stdout_sha256 == hashlib.sha256(b"stdout\n").hexdigest()


def test_local_and_remote_envelopes_obey_the_same_contract(tmp_path: Path) -> None:
    local = NativeJobManager(tmp_path / "local")
    remote = NativeJobManager(
        tmp_path / "remote",
        execution_backend="remote",
        remote_policy=_policy(),
        remote_executor=FakeRemoteExecutor(
            script=FakeRemoteScript(
                states=("running", "completed"),
                artifacts={"result.json": b'{"value": 4.0}'},
            )
        ),
    )
    try:
        local_id = local.submit(PARTICIPANT, {"seed": 3}, deferred=True)
        remote_id = remote.submit(PARTICIPANT, {"seed": 3}, deferred=True)
        assert local.run(local_id) == JobState.COMPLETED.value
        assert remote.run(remote_id) == JobState.COMPLETED.value

        local_envelope = local.envelope(local_id)
        remote_envelope = remote.envelope(remote_id)
        assert set(local_envelope) == set(remote_envelope)
        assert local_envelope["source"] == remote_envelope["source"] == "native_solver"
        assert local_envelope["solver_identity"] == remote_envelope["solver_identity"]
        assert local_envelope["validity"] == remote_envelope["validity"]
        assert local_envelope["units"] == remote_envelope["units"]
        assert remote.status(remote_id)["executor"] == "remote"
        assert local.status(local_id)["executor"] == "local"
    finally:
        local.close()
        remote.close()


def test_gcp_executor_never_silently_falls_back_to_local(tmp_path: Path) -> None:
    disabled = GCPBatchExecutor(RemoteComputePolicy.disabled())
    plan = ExecutionPlan(
        job_id="j2",
        participant_id=PARTICIPANT,
        solver_id="infra-integration",
        solver_version="test-1",
        execution_mode="remote",
        case_id="case-j2",
        input_hash="0" * 64,
        case_dir=str(tmp_path),
        image_digest=_IMAGE,
        region="us-central1",
    )
    with pytest.raises(ParticipantError) as excinfo:
        disabled.run(plan)
    assert excinfo.value.code == NativeErrorCode.CAPABILITY_UNAVAILABLE

    enabled_no_transport = GCPBatchExecutor(
        _policy(), project="demo", region="us-central1", image_digest=_IMAGE
    )
    with pytest.raises(ParticipantError) as gcp_exc:
        enabled_no_transport.run(plan)
    assert gcp_exc.value.code == NativeErrorCode.CAPABILITY_UNAVAILABLE


def test_unpriced_or_disallowed_placement_is_rejected() -> None:
    policy = _policy()
    with pytest.raises(ParticipantError):
        policy.assert_within_limits(
            RemoteResourceRequest(
                vcpu=1.0, memory_mib=1024.0, wall_time_s=60.0, machine_type="mystery-vm"
            )
        )
    with pytest.raises(ParticipantError):
        policy.assert_placement_allowed(region="mars-central1", project="demo")
