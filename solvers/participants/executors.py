"""Provider-neutral governed executor contract.

One logical lifecycle (PREPARE -> VALIDATE -> ADMIT -> EXECUTE -> MONITOR ->
PARSE -> VALIDATE RESULT -> HASH -> PUBLISH -> PROVENANCE) serves every
participant; only the transport/executor differs. ``LocalExecutor`` runs the
existing governed subprocess path, ``FakeRemoteExecutor`` is a deterministic
in-memory transport for tests, and ``GCPBatchExecutor`` is the fail-closed real
backend skeleton that never falls back silently.

Participant code never sees cloud details: an :class:`ExecutionPlan` carries
only provider-neutral identity, resource, and artifact declarations.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Protocol, runtime_checkable

from participants.checkpoints import CheckpointReceipt
from participants.errors import NativeErrorCode, ParticipantError
from participants.remote_policy import RemoteComputePolicy, RemoteResourceRequest

__all__ = [
    "ArtifactDigest",
    "ExecutionPlan",
    "ExecutionReceipt",
    "FakeRemoteExecutor",
    "FakeRemoteScript",
    "GCPBatchExecutor",
    "JobExecutor",
    "LocalExecutor",
    "RemoteExecutor",
    "verify_remote_evidence",
]

_HEX = "0123456789abcdef"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_hex64(value: str | None) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in _HEX for c in value)


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """A declared output file and the hash the worker attests to."""

    name: str
    sha256: str
    bytes: int

    def __post_init__(self) -> None:
        if not self.name.strip() or "/" in self.name or "\\" in self.name:
            raise ValueError(f"INVALID_ARTIFACT_NAME:{self.name}")
        if not _is_hex64(self.sha256):
            raise ValueError(f"INVALID_ARTIFACT_HASH:{self.name}")
        if self.bytes < 0:
            raise ValueError(f"INVALID_ARTIFACT_SIZE:{self.name}")


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Provider-neutral description of one attempt for any executor."""

    job_id: str
    participant_id: str
    solver_id: str
    solver_version: str
    execution_mode: str
    case_id: str
    input_hash: str
    case_dir: str
    command: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    resource: RemoteResourceRequest | None = None
    image_digest: str | None = None
    region: str | None = None
    project: str | None = None
    checkpoint_id: str | None = None
    resume_of: str | None = None
    attempt: int = 1
    inputs: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    """Terminal outcome of one execution attempt on any transport."""

    state: str  # "completed" | "failed" | "cancelled" | "preempted"
    execution_mode: str  # "subprocess" | "in-process" | "remote"
    exit_code: int | None = None
    reason: str | None = None
    detail: str = ""
    peak_rss_mib: float | None = None
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    artifacts: tuple[ArtifactDigest, ...] = ()
    started_at: float = 0.0
    finished_at: float = 0.0
    input_hash: str | None = None
    solver_identity: str | None = None
    solver_version: str | None = None
    image_digest: str | None = None
    machine_type: str | None = None
    region: str | None = None
    project: str | None = None
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float | None = None
    preempted: bool = False
    interruption_reason: str | None = None
    checkpoint: CheckpointReceipt | None = None
    evidence_verified: bool = False

    def __post_init__(self) -> None:
        if self.state not in {"completed", "failed", "cancelled", "preempted"}:
            raise ValueError(f"INVALID_EXECUTION_STATE:{self.state}")
        if self.execution_mode not in {"subprocess", "in-process", "remote"}:
            raise ValueError(f"INVALID_EXECUTION_MODE:{self.execution_mode}")

    @property
    def runtime_s(self) -> float:
        if self.finished_at <= 0 or self.started_at <= 0:
            return 0.0
        return max(0.0, self.finished_at - self.started_at)


@runtime_checkable
class JobExecutor(Protocol):
    """The single transport contract behind the scheduler."""

    name: str

    def submit(self, plan: ExecutionPlan) -> str: ...

    def poll(self, ref: str) -> str: ...

    def cancel(self, ref: str) -> None: ...

    def fetch_stdout(self, ref: str) -> bytes: ...

    def fetch_stderr(self, ref: str) -> bytes: ...

    def fetch_artifacts(self, ref: str) -> Mapping[str, bytes]: ...

    def terminal_receipt(self, ref: str) -> ExecutionReceipt: ...

    def run(
        self, plan: ExecutionPlan, cancel: Event | None = None
    ) -> ExecutionReceipt: ...


# The provider-neutral remote contract: an executor is any implementation of
# the transport protocol above. Participant code depends on neither name.
RemoteExecutor = JobExecutor


def verify_remote_evidence(
    receipt: ExecutionReceipt, plan: ExecutionPlan, policy: RemoteComputePolicy
) -> None:
    """Control-plane verification of a remote worker's evidence bundle.

    Fails closed on any identity/hash/placement mismatch, before any result can
    reach the envelope/provenance publication path.
    """

    policy.require_enabled()
    if receipt.state != "completed":
        return
    if receipt.execution_mode != "remote":
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, "remote receipt is not marked remote"
        )
    if receipt.input_hash != plan.input_hash:
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, "remote evidence input hash mismatch"
        )
    if receipt.solver_identity != plan.solver_id:
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID,
            f"remote evidence solver identity mismatch:{receipt.solver_identity}",
        )
    if receipt.exit_code != 0:
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, f"remote exit code:{receipt.exit_code}"
        )
    if plan.image_digest is not None:
        policy.assert_image_allowed(plan.image_digest)
        if receipt.image_digest != plan.image_digest:
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, "remote image digest mismatch"
            )
    policy.assert_placement_allowed(region=receipt.region, project=receipt.project)
    declared = {artifact.name for artifact in receipt.artifacts}
    missing = [name for name in plan.artifacts if name not in declared]
    if missing:
        raise ParticipantError(
            NativeErrorCode.RESULT_INVALID, f"remote evidence missing artifacts:{','.join(missing)}"
        )


class LocalExecutor:
    """Existing governed local path expressed through the executor contract."""

    name = "local"

    def __init__(
        self,
        *,
        job_root: Path,
        rss_limit_mib: float,
        timeout_s: float,
        extra_env: Callable[[str], Mapping[str, str] | None] | None = None,
        runner: Callable[..., object] | None = None,
    ) -> None:
        self._job_root = job_root
        self._rss_limit_mib = rss_limit_mib
        self._timeout_s = timeout_s
        self._extra_env = extra_env
        self._runner = runner

    def _run_governed(
        self, plan: ExecutionPlan, cancel: Event | None
    ) -> object:
        if self._runner is None:
            from participants.runner import run_governed

            runner: Callable[..., object] = run_governed
        else:
            runner = self._runner
        extra_env = self._extra_env(plan.solver_id) if self._extra_env else None
        return runner(
            plan.command,
            case_dir=Path(plan.case_dir),
            job_root=self._job_root,
            rss_limit_mib=self._rss_limit_mib,
            timeout_s=self._timeout_s,
            cancel=cancel,
            extra_env=extra_env,
        )

    def run(
        self, plan: ExecutionPlan, cancel: Event | None = None
    ) -> ExecutionReceipt:
        if plan.execution_mode == "in-process":
            raise ParticipantError(
                NativeErrorCode.PROCESS_START_FAILED,
                "local in-process execution is handled by the lifecycle",
            )
        try:
            receipt = self._run_governed(plan, cancel)
        except ParticipantError as exc:
            return ExecutionReceipt(
                state="failed",
                execution_mode="subprocess",
                reason=exc.code.value,
                detail=exc.detail,
                input_hash=plan.input_hash,
                solver_identity=plan.solver_id,
            )
        exit_code = getattr(receipt, "exit_code", 0)
        peak = getattr(receipt, "peak_rss_mib", 0.0)
        return ExecutionReceipt(
            state="completed",
            execution_mode="subprocess",
            exit_code=int(exit_code or 0),
            peak_rss_mib=float(peak or 0.0),
            stdout_sha256=str(getattr(receipt, "stdout_sha256", "")),
            stderr_sha256=str(getattr(receipt, "stderr_sha256", "")),
            started_at=float(getattr(receipt, "started_at", 0.0)),
            finished_at=float(getattr(receipt, "finished_at", 0.0)),
            input_hash=plan.input_hash,
            solver_identity=plan.solver_id,
        )

    def _ref(self, plan: ExecutionPlan) -> str:
        return f"local-{plan.job_id}"

    def submit(self, plan: ExecutionPlan) -> str:
        return self._ref(plan)

    def poll(self, ref: str) -> str:
        return "completed"

    def cancel(self, ref: str) -> None:
        return None

    def fetch_stdout(self, ref: str) -> bytes:
        path = self._job_root / ref.removeprefix("local-") / "stdout.log"
        return path.read_bytes() if path.is_file() else b""

    def fetch_stderr(self, ref: str) -> bytes:
        path = self._job_root / ref.removeprefix("local-") / "stderr.log"
        return path.read_bytes() if path.is_file() else b""

    def fetch_artifacts(self, ref: str) -> Mapping[str, bytes]:
        return {}

    def terminal_receipt(self, ref: str) -> ExecutionReceipt:
        return ExecutionReceipt(state="completed", execution_mode="subprocess")


@dataclass(slots=True)
class FakeRemoteScript:
    """Deterministic script for :class:`FakeRemoteExecutor` (tests, $0)."""

    states: tuple[str, ...] = ("running", "completed")
    stdout: bytes = b"fake-remote-stdout\n"
    stderr: bytes = b""
    artifacts: Mapping[str, bytes] = field(default_factory=dict)
    declared_artifacts: Mapping[str, tuple[str, int]] | None = None
    tamper_artifact: str | None = None
    input_hash_override: str | None = None
    image_digest_override: str | None = None
    solver_identity_override: str | None = None
    preempted: bool = False
    interruption_reason: str | None = None
    checkpoint: CheckpointReceipt | None = None
    actual_cost_usd: float | None = None
    estimated_cost_usd: float = 0.0
    machine_type: str = "e2-standard-2"
    runtime_s: float = 60.0
    late_success_after_cancel: bool = False
    image_digest: str = "sha256:" + "c" * 64


class FakeRemoteExecutor:
    """In-memory remote transport with deterministic, provider-neutral behavior."""

    name = "fake-remote"

    def __init__(
        self,
        *,
        script: FakeRemoteScript | None = None,
        script_factory: Callable[[ExecutionPlan], FakeRemoteScript] | None = None,
        artifacts_factory: Callable[[ExecutionPlan], Mapping[str, bytes]] | None = None,
        checkpoint_factory: Callable[[ExecutionPlan], CheckpointReceipt] | None = None,
    ) -> None:
        self._script = script or FakeRemoteScript()
        self._script_factory = script_factory
        self._artifacts_factory = artifacts_factory
        self._checkpoint_factory = checkpoint_factory
        self._plans: dict[str, ExecutionPlan] = {}
        self._scripts: dict[str, FakeRemoteScript] = {}
        self._states: dict[str, list[str]] = {}
        self._cancelled: set[str] = set()
        self._submitted: list[str] = []

    def _script_for(self, ref: str) -> FakeRemoteScript:
        return self._scripts.get(ref, self._script)

    def submit(self, plan: ExecutionPlan) -> str:
        ref = f"remote-{plan.job_id}"
        self._plans[ref] = plan
        script = self._script_factory(plan) if self._script_factory else self._script
        self._scripts[ref] = script
        self._states[ref] = list(script.states)
        self._submitted.append(ref)
        return ref

    def _advance(self, ref: str) -> str:
        states = self._states.get(ref, [])
        if len(states) > 1:
            return states.pop(0)
        return states[0] if states else "failed"

    def poll(self, ref: str) -> str:
        script = self._script_for(ref)
        if ref in self._cancelled and not script.late_success_after_cancel:
            return "cancelled"
        return self._advance(ref)

    def cancel(self, ref: str) -> None:
        self._cancelled.add(ref)

    def was_cancelled(self, ref: str) -> bool:
        return ref in self._cancelled

    def fetch_stdout(self, ref: str) -> bytes:
        return self._script_for(ref).stdout

    def fetch_stderr(self, ref: str) -> bytes:
        return self._script_for(ref).stderr

    def _artifacts(self, ref: str) -> Mapping[str, bytes]:
        if self._artifacts_factory is not None:
            return self._artifacts_factory(self._plans[ref])
        declared = self._script_for(ref).declared_artifacts
        if declared is not None:
            return {
                name: self._script_for(ref).artifacts.get(name, b"")
                for name in declared
            }
        return self._script_for(ref).artifacts

    def fetch_artifacts(self, ref: str) -> Mapping[str, bytes]:
        return dict(self._artifacts(ref))

    def terminal_receipt(self, ref: str) -> ExecutionReceipt:
        script = self._script_for(ref)
        plan = self._plans[ref]
        state = self._final_state(ref)
        artifacts: list[ArtifactDigest] = []
        for name, payload in self._artifacts(ref).items():
            digest = _sha256(payload)
            size = len(payload)
            if script.tamper_artifact == name:
                digest = _sha256(b"tampered-declared-bytes")
            artifacts.append(ArtifactDigest(name=name, sha256=digest, bytes=size))
        checkpoint = script.checkpoint
        if checkpoint is None and self._checkpoint_factory is not None:
            checkpoint = self._checkpoint_factory(plan)
        started = 1000.0
        return ExecutionReceipt(
            state=state,
            execution_mode="remote",
            exit_code=0 if state == "completed" else None,
            reason=None if state == "completed" else (
                "PREEMPTED" if state == "preempted" else state.upper()
            ),
            detail=script.interruption_reason or "",
            peak_rss_mib=0.0,
            stdout_sha256=_sha256(script.stdout),
            stderr_sha256=_sha256(script.stderr),
            artifacts=tuple(artifacts),
            started_at=started,
            finished_at=started + max(0.0, script.runtime_s),
            input_hash=script.input_hash_override or plan.input_hash,
            solver_identity=script.solver_identity_override or plan.solver_id,
            solver_version=plan.solver_version,
            image_digest=script.image_digest_override or plan.image_digest,
            machine_type=script.machine_type,
            region=plan.region,
            project=plan.project,
            estimated_cost_usd=script.estimated_cost_usd,
            actual_cost_usd=script.actual_cost_usd,
            preempted=script.preempted or state == "preempted",
            interruption_reason=script.interruption_reason,
            checkpoint=checkpoint,
        )

    def _final_state(self, ref: str) -> str:
        script = self._script_for(ref)
        if ref in self._cancelled and not script.late_success_after_cancel:
            return "cancelled"
        states = self._states.get(ref, [])
        if states:
            return states[-1]
        return "failed"

    def run(
        self, plan: ExecutionPlan, cancel: Event | None = None
    ) -> ExecutionReceipt:
        ref = self.submit(plan)
        while True:
            if cancel is not None and cancel.is_set():
                self.cancel(ref)
            state = self.poll(ref)
            if state in {"completed", "failed", "cancelled", "preempted"}:
                break
            time.sleep(0.0)
        return self.terminal_receipt(ref)


class GCPBatchExecutor:
    """Real GCP Batch backend skeleton; fails closed until user-authorized.

    No network call is made here. A real deployment injects a ``transport``
    callable; without one (the default, and the only state in this repository)
    the executor returns CAPABILITY_UNAVAILABLE rather than falling back to
    local execution.
    """

    name = "gcp-batch"

    def __init__(
        self,
        policy: RemoteComputePolicy,
        *,
        project: str | None = None,
        region: str | None = None,
        image_digest: str | None = None,
        transport: Callable[[ExecutionPlan], ExecutionReceipt] | None = None,
    ) -> None:
        self._policy = policy
        self._project = project
        self._region = region
        self._image_digest = image_digest
        self._transport = transport

    def _refuse(self, detail: str) -> ParticipantError:
        return ParticipantError(NativeErrorCode.CAPABILITY_UNAVAILABLE, detail)

    def submit(self, plan: ExecutionPlan) -> str:
        self._policy.require_enabled()
        self._policy.assert_placement_allowed(region=self._region, project=self._project)
        self._policy.assert_image_allowed(self._image_digest)
        if self._transport is None:
            raise self._refuse("GCP Batch transport is not provisioned")
        return f"gcp-{plan.job_id}"

    def poll(self, ref: str) -> str:
        self._policy.require_enabled()
        if self._transport is None:
            raise self._refuse("GCP Batch transport is not provisioned")
        return "completed"

    def cancel(self, ref: str) -> None:
        self._policy.require_enabled()
        if self._transport is None:
            raise self._refuse("GCP Batch transport is not provisioned")

    def fetch_stdout(self, ref: str) -> bytes:
        raise self._refuse("GCP Batch transport is not provisioned")

    def fetch_stderr(self, ref: str) -> bytes:
        raise self._refuse("GCP Batch transport is not provisioned")

    def fetch_artifacts(self, ref: str) -> Mapping[str, bytes]:
        raise self._refuse("GCP Batch transport is not provisioned")

    def terminal_receipt(self, ref: str) -> ExecutionReceipt:
        raise self._refuse("GCP Batch transport is not provisioned")

    def run(
        self, plan: ExecutionPlan, cancel: Event | None = None
    ) -> ExecutionReceipt:
        self.submit(plan)
        if self._transport is None:
            raise self._refuse("GCP Batch transport is not provisioned")
        return self._transport(plan)
