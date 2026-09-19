"""Governed native job lifecycle: prepare, schedule, execute, parse, publish.

One public path serves every participant: PREPARE -> VALIDATE INPUTS ->
SCHEDULE -> EXECUTE -> MONITOR -> PARSE -> VALIDATE RESULT -> HASH ARTIFACTS
-> ResultEnvelope -> STORE PROVENANCE. Job states persist in the ledger;
results publish only through the evidence-gated envelope path.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib
import json
import os
import sys
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Any, cast

from aeroworkbench_api.repositories.sqlite import ArtifactReference, SQLiteRepository
from participants.capabilities import probe_participant
from participants.checkpoints import (
    CheckpointArtifact,
    CheckpointReceipt,
    RetryPolicy,
    classify_failure,
    verify_resume_compatibility,
)
from participants.commands import build_command, require_opaque_case_id
from participants.envelope import (
    ArtifactFile,
    EvidenceBundle,
    ResultEnvelope,
    publish_result,
)
from participants.errors import GovernanceErrorCode, NativeErrorCode, ParticipantError
from participants.executors import (
    ExecutionPlan,
    ExecutionReceipt,
    JobExecutor,
    LocalExecutor,
    verify_remote_evidence,
)
from participants.manifest import get_participant
from participants.receipts import ParseReceipt
from participants.remote_policy import (
    CostLedger,
    RemoteComputePolicy,
    RemoteResourceRequest,
    reject_remote_escalation,
)
from participants.runner import SUPERVISOR_RSS_LIMIT_MIB
from participants.store import JobLedger

_ALLOWED_MODULES = frozenset(
    {
        "openfoam.case",
        "code_aster.comm",
        "ross.rotor",
        "pybamm.cell",
        "elmer.sif",
        "precice.validate",
        "participants.mesh_case",
        "participants.cad_case",
        "electrical.machine",
        "electrical.power_electronics",
    }
)

_PYTHON_MODULE_ENVS: dict[str, dict[str, str]] = {
    "ross": {"NUMBA_DISABLE_JIT": "1"},
    "pybamm": {},
}


class JobState(StrEnum):
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PARSING = "PARSING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED})

# The product job lifecycle is exactly this chain plus terminal failure/cancel
# from any non-terminal state. Anything else is rejected, never persisted.
_LEGAL_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.PREPARING, JobState.FAILED, JobState.CANCELLED}),
    JobState.PREPARING: frozenset({JobState.RUNNING, JobState.FAILED, JobState.CANCELLED}),
    JobState.RUNNING: frozenset({JobState.PARSING, JobState.FAILED, JobState.CANCELLED}),
    JobState.PARSING: frozenset({JobState.VALIDATING, JobState.FAILED, JobState.CANCELLED}),
    JobState.VALIDATING: frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
}

_RSS_CEILING_MIB = 896.0

_ARTIFACT_MIME: dict[str, str] = {
    "json": "application/json",
    "xml": "application/xml",
    "log": "text/plain",
    "txt": "text/plain",
    "dat": "text/plain",
    "sif": "text/plain",
    "comm": "text/plain",
    "py": "text/plain",
    "export": "text/plain",
    "step": "application/step",
    "stp": "application/step",
}

_ARTIFACT_CATEGORY: dict[str, str] = {
    "result.json": "report",
    "case.json": "case",
    "solver.log": "log",
    "stdout.log": "log",
    "stderr.log": "log",
}

_FAILURE_CODE_FROM_REASON: dict[str, NativeErrorCode | GovernanceErrorCode] = {
    "PROCESS_TIMEOUT": NativeErrorCode.PROCESS_TIMEOUT,
    "PROCESS_RSS_LIMIT_EXCEEDED": NativeErrorCode.PROCESS_RSS_LIMIT_EXCEEDED,
    "PROCESS_START_FAILED": NativeErrorCode.PROCESS_START_FAILED,
    "PROCESS_EXIT_NONZERO": NativeErrorCode.PROCESS_EXIT_NONZERO,
    "CANCELLED": NativeErrorCode.CANCELLED,
    "PREEMPTED": GovernanceErrorCode.PREEMPTED,
    "INTERRUPTED": NativeErrorCode.INTERRUPTED,
}

_EXECUTION_BACKENDS = frozenset({"local", "remote"})


def artifact_mime_for(name: str) -> str:
    """Bounded content type for a registered artifact name."""

    suffix = Path(name).suffix.lower().lstrip(".")
    return _ARTIFACT_MIME.get(suffix, "application/octet-stream")


def artifact_category_for(name: str) -> str:
    """Lightweight type category for a registered artifact name."""

    if name in _ARTIFACT_CATEGORY:
        return _ARTIFACT_CATEGORY[name]
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix in {"msh", "msh2"}:
        return "mesh"
    if suffix in {"step", "stp", "brep"}:
        return "geometry"
    if suffix in {"vtu", "h5", "hdf5", "zarr"}:
        return "field"
    if suffix in {"sif", "comm", "xml", "py"}:
        return "case"
    if suffix in {"log"}:
        return "log"
    if suffix in {"json", "txt", "dat", "export"}:
        return "report"
    return "other"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _resolve(ref: str) -> Callable[..., Any]:
    module_name, _, function_name = ref.partition(":")
    if module_name not in _ALLOWED_MODULES or not function_name:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"function ref not allowlisted:{ref}"
        )
    try:
        module = importlib.import_module(module_name)
        function = getattr(module, function_name)
    except (ImportError, AttributeError) as exc:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"function ref unresolvable:{ref}"
        ) from exc
    if not callable(function):
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"function ref not callable:{ref}"
        )
    return cast("Callable[..., Any]", function)


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _inputs_hash(inputs: Mapping[str, object]) -> str:
    try:
        payload = json.dumps(dict(inputs), sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_JOB_INPUTS:{exc}") from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _DigestCache:
    """Bounded LRU cache of verified file digests keyed by (path, size, mtime).

    PERF 06 digest reuse: within one publication path the same artifact can be
    hashed more than once (registration, listing, manifest). The cache avoids
    rereading unchanged bytes while a stat change (size or mtime) always forces
    a fresh streaming hash. Retrieval verification deliberately bypasses this
    cache so tampered bytes can never be served.
    """

    def __init__(self, limit: int = 512) -> None:
        self._entries: OrderedDict[tuple[str, int, int], str] = OrderedDict()
        self._lock = threading.Lock()
        self._limit = max(1, int(limit))
        self.hits = 0
        self.misses = 0

    def get(self, key: tuple[str, int, int]) -> str | None:
        with self._lock:
            value = self._entries.get(key)
            if value is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: tuple[str, int, int], digest: str) -> None:
        with self._lock:
            self._entries[key] = digest
            self._entries.move_to_end(key)
            while len(self._entries) > self._limit:
                self._entries.popitem(last=False)

    def metrics(self) -> dict[str, int]:
        with self._lock:
            return {"hits": self.hits, "misses": self.misses, "entries": len(self._entries)}


_DIGEST_CACHE = _DigestCache()


def _sha256_file_cached(path: Path) -> tuple[str, int]:
    """Streaming SHA-256 with bounded reuse for an unchanged file."""

    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    cached = _DIGEST_CACHE.get(key)
    if cached is not None:
        return cached, stat.st_size
    digest, size = _sha256_file(path)
    _DIGEST_CACHE.put(key, digest)
    return digest, size


class _InfeasibleProfile(ValueError):
    """The declared reservation cannot be hosted under the aggregate ceiling."""


@dataclasses.dataclass(frozen=True, slots=True)
class SolverResourcePolicy:
    """Per-solver-family concurrency, memory, thread, and priority policy."""

    max_concurrency: int = 1
    memory_mib: float = 256.0
    exclusive: bool = False
    priority: int = 0
    threads: int = 1

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise ValueError("INVALID_CONCURRENCY_POLICY")
        if not 0 < self.memory_mib <= _RSS_CEILING_MIB:
            raise ValueError("INVALID_MEMORY_POLICY")
        if self.threads < 1:
            raise ValueError("INVALID_THREAD_HINT")


# Conservative defaults: heavyweight native executables stay at concurrency 1
# (each reserves a large slice of the 896 MiB aggregate budget), governed
# Python solvers may overlap two-up, and cheap in-process analytical
# participants may run four-up. Nothing here raises the hard memory ceiling.
_DEFAULT_SOLVER_POLICIES: dict[str, SolverResourcePolicy] = {
    "openfoam": SolverResourcePolicy(max_concurrency=1, memory_mib=512.0),
    "code-aster": SolverResourcePolicy(max_concurrency=1, memory_mib=512.0),
    "elmer": SolverResourcePolicy(max_concurrency=1, memory_mib=384.0),
    "precice": SolverResourcePolicy(max_concurrency=1, memory_mib=128.0),
    "gmsh": SolverResourcePolicy(max_concurrency=1, memory_mib=256.0),
    "freecad": SolverResourcePolicy(max_concurrency=1, memory_mib=256.0),
    "ross": SolverResourcePolicy(max_concurrency=2, memory_mib=256.0),
    "pybamm": SolverResourcePolicy(max_concurrency=2, memory_mib=256.0),
    "aeroworkbench-electrical": SolverResourcePolicy(
        max_concurrency=4, memory_mib=64.0
    ),
}

DEFAULT_SOLVER_POLICY = SolverResourcePolicy(max_concurrency=2, memory_mib=128.0)


@dataclasses.dataclass(slots=True)
class JobProfile:
    """One queued job's declared resource envelope."""

    job_id: str
    participant_id: str
    solver_id: str
    execution_mode: str
    memory_mib: float
    threads: int = 1
    max_concurrency: int = 1
    exclusive: bool = False
    priority: int = 0
    sequence: int = 0
    effective_tier: int = 0
    skips: int = 0
    enqueued_at: float = 0.0
    admitted_at: float | None = None
    finished_at: float | None = None


class ResourceScheduler:
    """Bounded, resource-aware admission that replaces the global worker lock.

    Admission accounts for: declared/requested memory, solver-family
    concurrency policy, CPU/thread hints, exclusive-resource flags, and the
    896 MiB project aggregate reservation. Independent safe jobs overlap; a
    solver that declares ``exclusive`` (or a cap) is honored; memory is never
    oversubscribed to chase throughput.

    Fairness is deterministic: waiters are ordered by effective priority tier
    then admission sequence. Each admission ages every remaining waiter one
    ``skip``; once a waiter crosses ``aging_after_skips`` its tier is boosted,
    so a stream of cheap jobs cannot starve a promoted high-fidelity job. A
    higher-tier waiter blocked on memory or an exclusive slot holds the line
    (head-of-line reservation) so later jobs cannot consume its capacity.
    """

    def __init__(
        self,
        *,
        aggregate_memory_mib: float = _RSS_CEILING_MIB,
        max_active_jobs: int = 4,
        max_threads: int | None = None,
        aging_after_skips: int = 4,
        poll_s: float = 0.05,
    ) -> None:
        if not 0 < aggregate_memory_mib <= _RSS_CEILING_MIB:
            raise ValueError("INVALID_AGGREGATE_MEMORY")
        if max_active_jobs < 1:
            raise ValueError("INVALID_MAX_ACTIVE_JOBS")
        if aging_after_skips < 1:
            raise ValueError("INVALID_AGING_POLICY")
        self._aggregate = float(aggregate_memory_mib)
        self._max_active = int(max_active_jobs)
        self._max_threads = int(max_threads) if max_threads is not None else max(
            os.cpu_count() or 1, 1
        )
        self._aging_after_skips = int(aging_after_skips)
        self._poll_s = float(poll_s)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._waiters: dict[str, JobProfile] = {}
        self._active: dict[str, JobProfile] = {}
        self._active_reserved = 0.0
        self._active_threads = 0
        self._active_by_solver: dict[str, int] = {}
        self._sequence = 0
        self._admitted_total = 0
        self._queue_delay_ms: list[float] = []
        self._peak_active = 0
        self._peak_reserved = 0.0
        self._busy_ms = 0.0
        self._busy_by_solver: dict[str, float] = {}
        self._started_at = time.perf_counter()

    # -- admission -------------------------------------------------------

    def acquire(self, profile: JobProfile, cancel: Event | None = None) -> bool:
        """Block until ``profile`` may run; ``False`` means it was cancelled."""

        profile.enqueued_at = time.perf_counter()
        with self._cond:
            profile.sequence = self._sequence
            self._sequence += 1
            profile.effective_tier = profile.priority
            self._waiters[profile.job_id] = profile
            try:
                while True:
                    if cancel is not None and cancel.is_set():
                        return False
                    if self._should_admit(profile):
                        self._waiters.pop(profile.job_id, None)
                        self._activate(profile)
                        return True
                    self._cond.wait(self._poll_s)
            finally:
                self._waiters.pop(profile.job_id, None)

    def release(self, job_id: str) -> None:
        with self._cond:
            profile = self._active.pop(job_id, None)
            if profile is not None:
                profile.finished_at = time.perf_counter()
                self._active_reserved = max(
                    0.0, self._active_reserved - profile.memory_mib
                )
                self._active_threads = max(0, self._active_threads - profile.threads)
                remaining = self._active_by_solver.get(profile.solver_id, 0) - 1
                if remaining > 0:
                    self._active_by_solver[profile.solver_id] = remaining
                else:
                    self._active_by_solver.pop(profile.solver_id, None)
                if profile.admitted_at is not None:
                    elapsed = (profile.finished_at - profile.admitted_at) * 1000.0
                    self._busy_ms += elapsed
                    self._busy_by_solver[profile.solver_id] = (
                        self._busy_by_solver.get(profile.solver_id, 0.0) + elapsed
                    )
            else:
                self._waiters.pop(job_id, None)
            self._cond.notify_all()

    def _activate(self, profile: JobProfile) -> None:
        profile.admitted_at = time.perf_counter()
        self._active[profile.job_id] = profile
        self._active_reserved += profile.memory_mib
        self._active_threads += profile.threads
        self._active_by_solver[profile.solver_id] = (
            self._active_by_solver.get(profile.solver_id, 0) + 1
        )
        self._admitted_total += 1
        self._queue_delay_ms.append((profile.admitted_at - profile.enqueued_at) * 1000.0)
        if len(self._queue_delay_ms) > 4096:
            self._queue_delay_ms = self._queue_delay_ms[-2048:]
        self._peak_active = max(self._peak_active, len(self._active))
        self._peak_reserved = max(self._peak_reserved, self._active_reserved)
        for waiter in self._waiters.values():
            waiter.skips += 1
            if waiter.skips >= self._aging_after_skips:
                waiter.effective_tier = max(waiter.effective_tier, waiter.priority + 1)
        self._cond.notify_all()

    def _fits(
        self,
        profile: JobProfile,
        active: Mapping[str, JobProfile],
        reserved: float,
        threads: int,
        by_solver: Mapping[str, int],
    ) -> bool:
        if not 0 < profile.memory_mib <= self._aggregate:
            return False
        if profile.exclusive:
            if active:
                return False
        elif any(item.exclusive for item in active.values()):
            return False
        if by_solver.get(profile.solver_id, 0) >= profile.max_concurrency:
            return False
        if len(active) >= self._max_active:
            return False
        if reserved + profile.memory_mib > self._aggregate + 1e-9:
            return False
        return threads + profile.threads <= self._max_threads

    def _blocked_on_reservation(self, profile: JobProfile, reserved: float) -> bool:
        if not 0 < profile.memory_mib <= self._aggregate:
            # An infeasible declaration can never be satisfied; it must not
            # block the queue (callers fail it closed through admission).
            return False
        if profile.exclusive:
            return True
        return reserved + profile.memory_mib > self._aggregate + 1e-9

    def _should_admit(self, profile: JobProfile) -> bool:
        order = sorted(
            self._waiters.values(),
            key=lambda item: (-item.effective_tier, item.sequence),
        )
        active: dict[str, JobProfile] = dict(self._active)
        reserved = self._active_reserved
        threads = self._active_threads
        by_solver = dict(self._active_by_solver)
        for waiter in order:
            if self._fits(waiter, active, reserved, threads, by_solver):
                if waiter.job_id == profile.job_id:
                    return True
                active[waiter.job_id] = waiter
                reserved += waiter.memory_mib
                threads += waiter.threads
                by_solver[waiter.solver_id] = by_solver.get(waiter.solver_id, 0) + 1
            elif self._blocked_on_reservation(waiter, reserved):
                break
        return False

    # -- observability ---------------------------------------------------

    def active_jobs(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._active))

    def waiting_jobs(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._waiters))

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            elapsed_ms = (time.perf_counter() - self._started_at) * 1000.0
            samples = sorted(self._queue_delay_ms)
            count = len(samples)
            median = samples[count // 2] if count else 0.0
            p95 = samples[min(count - 1, int(0.95 * (count - 1)))] if count else 0.0
            latest = samples[-1] if count else 0.0
            return {
                "aggregate_memory_mib": self._aggregate,
                "max_active_jobs": self._max_active,
                "max_threads": self._max_threads,
                "active_jobs": len(self._active),
                "waiting_jobs": len(self._waiters),
                "active_reservation_mib": round(self._active_reserved, 6),
                "peak_reservation_mib": round(self._peak_reserved, 6),
                "peak_active_jobs": self._peak_active,
                "admitted_total": self._admitted_total,
                "queue_delay_samples": count,
                "queue_delay_median_ms": round(median, 6),
                "queue_delay_p95_ms": round(p95, 6),
                "queue_delay_max_ms": round(latest, 6),
                "busy_ms": round(self._busy_ms, 6),
                "elapsed_ms": round(elapsed_ms, 6),
                "utilization": (
                    round(self._busy_ms / elapsed_ms, 6) if elapsed_ms > 0 else 0.0
                ),
                "active_by_solver": dict(sorted(self._active_by_solver.items())),
                "busy_by_solver_ms": {
                    key: round(value, 6)
                    for key, value in sorted(self._busy_by_solver.items())
                },
            }


@dataclasses.dataclass(frozen=True, slots=True)
class JobRequest:
    """One batch submission entry (campaign integration seam)."""

    participant_id: str
    inputs: Mapping[str, object]
    design_id: str = "generic-design"
    owner_id: str | None = None
    revision_id: str | None = None
    analysis: str | None = None
    fidelity: str | None = None
    requested_memory_mib: float | None = None
    requested_threads: int | None = None


class NativeJobManager:
    """Resource-aware, governed execution for every native participant."""

    def __init__(
        self,
        job_root: Path,
        *,
        repository: SQLiteRepository | None = None,
        ledger: JobLedger | None = None,
        rss_limit_mib: float = 352.0,
        supervisor_rss_limit_mib: float = SUPERVISOR_RSS_LIMIT_MIB,
        timeout_s: float = 900.0,
        solver_policies: Mapping[str, SolverResourcePolicy] | None = None,
        default_policy: SolverResourcePolicy | None = None,
        aggregate_memory_mib: float = _RSS_CEILING_MIB,
        max_active_jobs: int = 4,
        max_threads: int | None = None,
        aging_after_skips: int = 4,
        execution_backend: str = "local",
        remote_policy: RemoteComputePolicy | None = None,
        remote_executor: JobExecutor | None = None,
        retry_policy: RetryPolicy | None = None,
        remote_poll_s: float = 0.05,
        project_spent_usd: float = 0.0,
        daily_spent_usd: float = 0.0,
        session_spent_usd: float = 0.0,
    ) -> None:
        if not 0 < rss_limit_mib <= 896.0:
            raise ValueError("INVALID_RSS_LIMIT")
        if not 0 < supervisor_rss_limit_mib <= 896.0:
            raise ValueError("INVALID_SUPERVISOR_RSS_LIMIT")
        if timeout_s <= 0:
            raise ValueError("INVALID_TIMEOUT")
        if execution_backend not in _EXECUTION_BACKENDS:
            raise ValueError(f"INVALID_EXECUTION_BACKEND:{execution_backend}")
        if remote_poll_s <= 0:
            raise ValueError("INVALID_REMOTE_POLL")
        self._job_root = job_root
        self._job_root.mkdir(parents=True, exist_ok=True)
        self._repository = repository or SQLiteRepository(job_root / "provenance.sqlite3")
        self._ledger = ledger or JobLedger(job_root / "native_jobs.sqlite3")
        self._rss_limit_mib = rss_limit_mib
        self._supervisor_rss_limit_mib = supervisor_rss_limit_mib
        self._timeout_s = timeout_s
        self._solver_policies = dict(_DEFAULT_SOLVER_POLICIES)
        if solver_policies:
            self._solver_policies.update(solver_policies)
        self._default_policy = default_policy or DEFAULT_SOLVER_POLICY
        self._scheduler = ResourceScheduler(
            aggregate_memory_mib=aggregate_memory_mib,
            max_active_jobs=max_active_jobs,
            max_threads=max_threads,
            aging_after_skips=aging_after_skips,
        )
        self._state_lock = threading.Lock()
        self._claims_lock = threading.Lock()
        self._claimed: set[str] = set()
        self._cancel_flags: dict[str, Event] = {}
        self._supervisor_cancels: dict[str, Event] = {}
        self._hash_bytes = 0
        self._hash_ms = 0.0
        self._artifact_read_bytes = 0
        self._artifact_read_ms = 0.0
        # INFRA-FIX 03/04: transport selection is a user-owned construction
        # decision, never a per-request or AI-supplied field. A remote manager
        # cannot even be constructed unless the user policy authorizes it.
        self._execution_backend = execution_backend
        self._remote_policy = remote_policy or RemoteComputePolicy.disabled()
        self._remote_executor = remote_executor
        self._retry_policy = retry_policy or RetryPolicy()
        self._remote_poll_s = remote_poll_s
        self._local_executor = LocalExecutor(
            job_root=self._job_root,
            rss_limit_mib=self._supervisor_rss_limit_mib,
            timeout_s=self._timeout_s,
            extra_env=lambda solver_id: _PYTHON_MODULE_ENVS.get(solver_id),
        )
        self._cost_ledger = CostLedger(
            self._remote_policy.limits,
            project_spent_usd=project_spent_usd,
            daily_spent_usd=daily_spent_usd,
            session_spent_usd=session_spent_usd,
        )
        if execution_backend == "remote":
            self._remote_policy.require_enabled()
            if remote_executor is None:
                raise ParticipantError(
                    NativeErrorCode.CAPABILITY_UNAVAILABLE,
                    "remote execution backend has no executor configured",
                )
        self.recover()

    def close(self) -> None:
        """Release the ledger and provenance stores."""
        self._ledger.close()
        self._repository.close()

    def recover(self) -> int:
        """Interrupt jobs orphaned by a previous process lifetime.

        Terminal rows stay queryable untouched; QUEUED rows never started and
        remain startable. Every other row had a worker that will never report
        back, so it becomes FAILED with an INTERRUPTED code and an evidence
        event instead of a silent success.
        """

        terminal = {state.value for state in TERMINAL_STATES}
        interrupted = 0
        for row in self._ledger.all():
            if row.state == JobState.QUEUED.value or row.state in terminal:
                continue
            detail = f"worker did not survive restart; last state was {row.state}"
            self._transition(row.job_id, JobState.FAILED, detail)
            self._ledger.update(
                row.job_id,
                state=JobState.FAILED.value,
                updated_at=_now(),
                error_code=NativeErrorCode.INTERRUPTED.value,
                error_detail=detail,
            )
            interrupted += 1
        return interrupted

    # -- submission ------------------------------------------------------

    def submit(
        self,
        participant_id: str,
        inputs: dict[str, object],
        *,
        design_id: str = "generic-design",
        deferred: bool = False,
        owner_id: str | None = None,
        revision_id: str | None = None,
        analysis: str | None = None,
        fidelity: str | None = None,
        requested_memory_mib: float | None = None,
        requested_threads: int | None = None,
        resume_of: str | None = None,
        attempt: int = 1,
        checkpoint_id: str | None = None,
    ) -> str:
        manifest = get_participant(participant_id)  # raises ValueError if unknown
        if not isinstance(inputs, dict):
            raise ValueError("INVALID_JOB_INPUTS:inputs must be a mapping")
        # A tool/AI payload may never enable remote work or raise a limit.
        reject_remote_escalation(inputs)
        if not design_id.strip():
            raise ValueError("INVALID_JOB_INPUTS:design id required")
        if attempt < 1:
            raise ValueError("INVALID_JOB_INPUTS:attempt must be positive")
        if resume_of is not None and not resume_of.strip():
            raise ValueError("INVALID_JOB_INPUTS:resume lineage must be non-empty")
        if checkpoint_id is not None and (
            len(checkpoint_id) != 64
            or any(character not in "0123456789abcdef" for character in checkpoint_id)
        ):
            raise ValueError("INVALID_JOB_INPUTS:checkpoint id must be a sha256 hex id")
        for label, value in (
            ("owner id", owner_id),
            ("revision id", revision_id),
            ("analysis", analysis),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"INVALID_JOB_INPUTS:{label} must be non-empty")
        if fidelity is not None and fidelity not in manifest.fidelity_levels:
            raise ValueError(
                f"INVALID_JOB_INPUTS:unknown fidelity:{fidelity} "
                f"allowed={','.join(manifest.fidelity_levels)}"
            )
        if requested_memory_mib is not None and (
            isinstance(requested_memory_mib, bool)
            or not isinstance(requested_memory_mib, (int, float))
        ):
            raise ValueError("INVALID_JOB_INPUTS:requested memory must be a number")
        if requested_threads is not None and (
            isinstance(requested_threads, bool)
            or not isinstance(requested_threads, int)
            or requested_threads < 1
        ):
            raise ValueError("INVALID_JOB_INPUTS:requested threads must be a positive integer")
        digest = _inputs_hash(inputs)
        job_id = uuid.uuid4().hex
        case_id = f"case-{job_id[:12]}"
        created = _now()
        self._ledger.create_with_event(
            job_id=job_id,
            participant_id=participant_id,
            design_id=design_id,
            state=JobState.QUEUED.value,
            created_at=created,
            inputs={
                "inputs": inputs,
                "case_id": case_id,
                "analysis": analysis,
                "fidelity": fidelity,
                "requested_memory_mib": requested_memory_mib,
                "requested_threads": requested_threads,
            },
            detail=f"input_hash={digest}",
            owner_id=owner_id,
            revision_id=revision_id,
            resume_of=resume_of,
            attempt=attempt,
            checkpoint_id=checkpoint_id,
        )
        with self._state_lock:
            self._cancel_flags[job_id] = Event()
        self._repository.append_provenance(
            event_id=f"launch-{job_id}",
            event_type="native.launch-accepted",
            subject_hash=digest,
            actor="native-scheduler",
            occurred_at=created,
            details={
                "job_id": job_id,
                "participant_id": participant_id,
                "design_id": design_id,
                "resume_of": resume_of,
                "attempt": attempt,
                "checkpoint_id": checkpoint_id,
            },
            artifacts=[],
        )
        if not deferred:
            self._spawn(job_id)
        return job_id

    def submit_batch(self, requests: Iterable[JobRequest]) -> tuple[str, ...]:
        """Submit many candidates in one call and start them concurrently.

        Validation is fail-closed: if any request is invalid, every job already
        created by this call is cancelled before the error propagates, so a
        campaign never observes a partially-admitted batch.
        """

        items = list(requests)
        created: list[str] = []
        try:
            for item in items:
                created.append(
                    self.submit(
                        item.participant_id,
                        dict(item.inputs),
                        design_id=item.design_id,
                        deferred=True,
                        owner_id=item.owner_id,
                        revision_id=item.revision_id,
                        analysis=item.analysis,
                        fidelity=item.fidelity,
                        requested_memory_mib=item.requested_memory_mib,
                        requested_threads=item.requested_threads,
                    )
                )
        except Exception:
            for job_id in created:
                with contextlib.suppress(KeyError, ParticipantError):
                    self.cancel(job_id)
            raise
        for job_id in created:
            self._spawn(job_id)
        return tuple(created)

    def completions_since(
        self, cursor: int = 0, *, limit: int = 0
    ) -> tuple[dict[str, Any], ...]:
        """Terminal jobs strictly after a ledger cursor (campaign consumption).

        The cursor is the event sequence of the terminal transition, so a
        campaign can drain completions in batches instead of polling every job.
        Terminal rows stay terminal; this read never mutates state.
        """

        entries: list[dict[str, Any]] = []
        for event in self._ledger.terminal_events_since(cursor, limit=limit):
            row = self._ledger.get(event.job_id)
            if row is None:
                continue
            entries.append(
                {
                    "sequence": event.sequence,
                    "job_id": event.job_id,
                    "participant_id": row.participant_id,
                    "design_id": row.design_id,
                    "state": event.state,
                    "run_id": row.run_id,
                    "result_id": row.result_id,
                    "provenance_id": row.provenance_id,
                    "error_code": row.error_code,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
        return tuple(entries)

    def cancel(self, job_id: str) -> str:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        if row.state in {state.value for state in TERMINAL_STATES}:
            raise ParticipantError(NativeErrorCode.CANCELLED, f"job already terminal:{row.state}")
        with self._state_lock:
            flag = self._cancel_flags.get(job_id)
            if flag is not None:
                flag.set()
            supervisor_cancel = self._supervisor_cancels.get(job_id)
            if supervisor_cancel is not None:
                supervisor_cancel.set()
        if row.state == JobState.QUEUED.value:
            self._transition(job_id, JobState.CANCELLED, "cancelled while queued")
            return JobState.CANCELLED.value
        return row.state

    def _cancelled(self, job_id: str) -> bool:
        with self._state_lock:
            flag = self._cancel_flags.get(job_id)
            return flag is not None and flag.is_set()

    def _cancel_event(self, job_id: str) -> Event:
        with self._state_lock:
            flag = self._cancel_flags.get(job_id)
            if flag is None:
                flag = Event()
                self._cancel_flags[job_id] = flag
            return flag

    def _spawn(self, job_id: str) -> bool:
        """Start exactly one worker thread for a still-QUEUED job."""

        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        if row.state != JobState.QUEUED.value:
            return False
        thread = threading.Thread(
            target=self.run, args=(job_id,), name=f"native-{job_id[:8]}", daemon=True
        )
        thread.start()
        return True

    def start(self, job_id: str) -> bool:
        """Begin a queued job (idempotent; returns False if not QUEUED)."""

        return self._spawn(job_id)

    # -- execution -------------------------------------------------------

    def run(self, job_id: str) -> str:
        """Claim a QUEUED job, wait for a resource reservation, then execute.

        The claim set is the no-duplicate-execution guard: two concurrent
        ``run`` calls for the same admitted job proceed at most once. A job
        cancelled while queued never commits worker resources.
        """

        with self._claims_lock:
            row = self._ledger.get(job_id)
            if row is None:
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")
            if row.state != JobState.QUEUED.value or job_id in self._claimed:
                return row.state
            self._claimed.add(job_id)
        try:
            try:
                profile = self._profile_for(row)
            except _InfeasibleProfile:
                # Fail closed through the normal admission path so the job
                # records ADMISSION_REJECTED (never a silent success).
                return self._run_guarded(job_id)
            admitted = self._scheduler.acquire(profile, self._cancel_event(job_id))
            if not admitted:
                current = self._ledger.get(job_id)
                return current.state if current is not None else JobState.CANCELLED.value
            try:
                return self._run_guarded(job_id)
            finally:
                self._scheduler.release(job_id)
        finally:
            with self._claims_lock:
                self._claimed.discard(job_id)

    def _profile_for(self, row: Any) -> JobProfile:
        manifest = get_participant(row.participant_id)
        solver_id = manifest.executable.solver_id
        policy = self._solver_policies.get(solver_id, self._default_policy)
        meta = self._request_meta(row.job_id)
        requested = meta.get("requested_memory_mib")
        if requested is None:
            memory = policy.memory_mib
        else:
            try:
                memory = float(requested)
            except (TypeError, ValueError) as exc:
                raise _InfeasibleProfile(str(requested)) from exc
            if not 0 < memory <= _RSS_CEILING_MIB:
                raise _InfeasibleProfile(str(requested))
        threads = policy.threads
        requested_threads = meta.get("requested_threads")
        if (
            isinstance(requested_threads, int)
            and not isinstance(requested_threads, bool)
            and requested_threads >= 1
        ):
            threads = min(requested_threads, policy.max_concurrency * policy.threads)
        priority = policy.priority
        fidelity = meta.get("fidelity")
        if isinstance(fidelity, str) and fidelity in manifest.fidelity_levels:
            priority += manifest.fidelity_levels.index(fidelity)
        return JobProfile(
            job_id=row.job_id,
            participant_id=row.participant_id,
            solver_id=solver_id,
            execution_mode=manifest.executable.execution_mode,
            memory_mib=memory,
            threads=max(1, threads),
            max_concurrency=policy.max_concurrency,
            exclusive=policy.exclusive,
            priority=priority,
        )

    def _admit(self, job_id: str) -> None:
        """Scheduler admission before any worker resources are committed.

        A job that cannot be hosted (unwritable job root, infeasible memory
        reservation) is rejected here with ADMISSION_REJECTED instead of
        failing later as if a solver had run.
        """

        if not self._job_root.is_dir() or not os.access(self._job_root, os.W_OK):
            raise ParticipantError(
                NativeErrorCode.ADMISSION_REJECTED,
                f"job root is not writable:{self._job_root}",
            )
        requested = self._request_meta(job_id).get("requested_memory_mib")
        if requested is None:
            return
        if (
            isinstance(requested, bool)
            or not isinstance(requested, (int, float))
            or not (0 < float(requested) <= _RSS_CEILING_MIB)
        ):
            raise ParticipantError(
                NativeErrorCode.ADMISSION_REJECTED,
                f"memory reservation outside 0..{_RSS_CEILING_MIB:g} MiB:{requested!r}",
            )

    def _run_guarded(self, job_id: str) -> str:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        if row.state != JobState.QUEUED.value:
            return row.state
        manifest = get_participant(row.participant_id)
        case_id = f"case-{job_id[:12]}"
        case_dir = self._job_root / case_id
        run_id = uuid.uuid4().hex
        try:
            if self._cancelled(job_id):
                return self._transition(job_id, JobState.CANCELLED, "cancelled before prepare")
            self._transition(job_id, JobState.PREPARING, f"participant={manifest.participant_id}")
            self._admit(job_id)
            prepare = _resolve(manifest.prepare_ref)
            receipt = prepare(self._stored_inputs(job_id), case_dir)
            if receipt.input_hash is None:
                raise ParticipantError(
                    NativeErrorCode.PREPARATION_FAILED, "prepare lost input hash"
                )
            self._ledger.update(
                job_id,
                state=JobState.PREPARING.value,
                updated_at=_now(),
                input_hash=receipt.input_hash,
                geometry_hash=receipt.geometry_hash,
                mesh_hash=receipt.mesh_hash,
            )
            if self._cancelled(job_id):
                return self._transition(job_id, JobState.CANCELLED, "cancelled after prepare")
            probe = probe_participant(manifest.participant_id)
            if probe.state != "ready":
                raise ParticipantError(
                    NativeErrorCode.CAPABILITY_UNAVAILABLE, probe.detail
                )
            if self._cancelled(job_id):
                return self._transition(job_id, JobState.CANCELLED, "cancelled before run")
            self._transition(
                job_id, JobState.RUNNING, f"run_id={run_id}", {"run_id": run_id}
            )
            execution = self._execute(manifest, job_id, case_dir, probe)
            if self._cancelled(job_id) or execution.state == "cancelled":
                return self._transition(job_id, JobState.CANCELLED, "cancelled during run")
            if execution.state == "preempted":
                return self._handle_preemption(manifest, job_id, run_id, execution, case_dir)
            if execution.state != "completed":
                code = _FAILURE_CODE_FROM_REASON.get(
                    execution.reason or "", NativeErrorCode.PROCESS_EXIT_NONZERO
                )
                raise ParticipantError(
                    code, execution.detail or execution.reason or "execution failed"
                )
            self._transition(job_id, JobState.PARSING, "solver output ready")
            parse = _resolve(manifest.parser_ref)
            parsed = parse(case_dir)
            parsed = dataclasses.replace(parsed, participant_id=manifest.participant_id)
            self._transition(job_id, JobState.VALIDATING, f"parser={manifest.parser_ref}")
            validate = _resolve(manifest.validity_ref)
            validity = validate(dict(parsed.scalars), self._stored_inputs(job_id))
            validity = dataclasses.replace(validity, participant_id=manifest.participant_id)
            if not validity.passed:
                raise ParticipantError(
                    NativeErrorCode.QUALITY_GATE_FAILED,
                    validity.detail or "participant validity checks failed",
                )
            envelope = self._publish(
                manifest,
                job_id,
                run_id,
                receipt,
                execution,
                parsed,
                validity,
                case_dir,
                probe,
            )
            envelope_json = envelope.model_dump_json()
            result_id = hashlib.sha256(envelope_json.encode("utf-8")).hexdigest()
            return self._transition(
                job_id,
                JobState.COMPLETED,
                f"run_id={run_id}",
                {
                    "envelope_json": envelope_json,
                    "result_id": result_id,
                    "provenance_id": envelope.provenance_id,
                },
            )
        except ParticipantError as exc:
            print(
                f"[native] job {job_id} FAILED {exc.code.value}:{exc.detail}",
                file=sys.stderr,
            )
            return self._transition(
                job_id,
                JobState.FAILED,
                f"{exc.code.value}:{exc.detail}",
                {"error_code": exc.code.value, "error_detail": exc.detail},
            )
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}:{exc}"
            print(f"[native] job {job_id} FAILED {detail}", file=sys.stderr)
            return self._transition(
                job_id,
                JobState.FAILED,
                detail,
                {"error_code": NativeErrorCode.RESULT_INVALID.value, "error_detail": detail},
            )

    def _execute(
        self, manifest: Any, job_id: str, case_dir: Path, probe: Any
    ) -> ExecutionReceipt:
        require_opaque_case_id(case_dir.name)
        if self._execution_backend == "remote":
            plan = self._build_plan(manifest, job_id, case_dir, probe)
            return self._execute_remote(job_id, case_dir, plan)
        if manifest.executable.execution_mode == "in-process":
            if manifest.execute_ref is None:
                raise ParticipantError(
                    NativeErrorCode.PREPARATION_FAILED, "in-process participant needs execute_ref"
                )
            execute = _resolve(manifest.execute_ref)
            execute(self._stored_inputs(job_id), case_dir)
            return ExecutionReceipt(
                state="completed",
                execution_mode="in-process",
                exit_code=0,
                input_hash=self._row_input_hash(job_id),
                solver_identity=manifest.executable.solver_id,
                solver_version=probe.version or "unknown",
            )
        command = build_command(manifest.participant_id, case_dir.name)
        plan = self._build_plan(manifest, job_id, case_dir, probe, command=command)
        supervisor_cancel = Event()
        with self._state_lock:
            self._supervisor_cancels[job_id] = supervisor_cancel
        if self._cancelled(job_id):
            supervisor_cancel.set()
        try:
            execution = self._local_executor.run(plan, supervisor_cancel)
            self._mirror_solver_log(case_dir)
            return execution
        finally:
            with self._state_lock:
                self._supervisor_cancels.pop(job_id, None)

    def _row_input_hash(self, job_id: str) -> str:
        row = self._ledger.get(job_id)
        if row is None or not row.input_hash:
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED, "job has no recorded input hash"
            )
        return row.input_hash

    def _build_plan(
        self,
        manifest: Any,
        job_id: str,
        case_dir: Path,
        probe: Any,
        *,
        command: tuple[str, ...] = (),
    ) -> ExecutionPlan:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        resource: RemoteResourceRequest | None = None
        image: str | None = None
        region: str | None = None
        project: str | None = None
        if self._execution_backend == "remote":
            limits = self._remote_policy.limits
            resource = RemoteResourceRequest(
                vcpu=limits.max_vcpu,
                memory_mib=limits.max_memory_mib,
                wall_time_s=self._timeout_s,
                machine_type=limits.machine_type,
                gpu_type=limits.gpu_type if limits.max_gpu_count > 0 else None,
                gpu_count=limits.max_gpu_count,
            )
            image = limits.allowed_image_digests[0] if limits.allowed_image_digests else None
            region = limits.allowed_regions[0] if limits.allowed_regions else None
            project = limits.allowed_projects[0] if limits.allowed_projects else None
        return ExecutionPlan(
            job_id=job_id,
            participant_id=manifest.participant_id,
            solver_id=manifest.executable.solver_id,
            solver_version=probe.version or "unknown",
            execution_mode=manifest.executable.execution_mode,
            case_id=case_dir.name,
            input_hash=row.input_hash or "",
            case_dir=str(case_dir),
            command=command,
            artifacts=tuple(manifest.artifacts),
            resource=resource,
            image_digest=image,
            region=region,
            project=project,
            checkpoint_id=row.checkpoint_id,
            resume_of=row.resume_of,
            attempt=row.attempt,
            inputs=self._stored_inputs(job_id),
        )

    # -- remote execution (INFRA-FIX 03) --------------------------------

    def _execute_remote(
        self, job_id: str, case_dir: Path, plan: ExecutionPlan
    ) -> ExecutionReceipt:
        self._remote_policy.require_enabled()
        executor = self._remote_executor
        if executor is None:
            raise ParticipantError(
                NativeErrorCode.CAPABILITY_UNAVAILABLE, "no remote executor configured"
            )
        if plan.resource is None:
            raise ParticipantError(
                NativeErrorCode.CAPABILITY_UNAVAILABLE, "remote plan has no resource envelope"
            )
        self._remote_policy.assert_within_limits(plan.resource)
        if plan.image_digest is not None:
            self._remote_policy.assert_image_allowed(plan.image_digest)
        cost_plan = self._cost_ledger.plan(job_id, plan.resource)
        self._cost_ledger.reserve(cost_plan)  # cost-admitted before launch
        cancel = self._cancel_event(job_id)
        settled = False
        try:
            ref, receipt = self._run_remote_transport(executor, plan, cancel)
            if self._cancelled(job_id):
                cost = self._settle_remote_cost(job_id, receipt, plan, preempted=receipt.preempted)
                settled = True
                return dataclasses.replace(
                    receipt,
                    state="cancelled",
                    evidence_verified=False,
                    estimated_cost_usd=cost.estimated_cost_usd,
                    actual_cost_usd=cost.actual_cost_usd,
                )
            if receipt.state == "preempted" and receipt.checkpoint is not None:
                self._preserve_checkpoint(job_id, case_dir, receipt.checkpoint, executor, ref)
            if receipt.state == "completed":
                try:
                    self._verify_and_materialize_remote(executor, ref, plan, receipt, case_dir)
                except Exception:
                    self._settle_remote_cost(job_id, receipt, plan, preempted=False)
                    settled = True
                    raise
                cost = self._settle_remote_cost(job_id, receipt, plan, preempted=False)
                settled = True
                return dataclasses.replace(
                    receipt,
                    evidence_verified=True,
                    estimated_cost_usd=cost.estimated_cost_usd,
                    actual_cost_usd=cost.actual_cost_usd,
                )
            cost = self._settle_remote_cost(job_id, receipt, plan, preempted=receipt.preempted)
            settled = True
            return dataclasses.replace(
                receipt,
                estimated_cost_usd=cost.estimated_cost_usd,
                actual_cost_usd=cost.actual_cost_usd,
            )
        finally:
            if not settled and self._cost_ledger.spend(job_id) is None:
                # No attempt ever terminated: the reservation must not leak.
                self._cost_ledger.release(job_id)

    def _run_remote_transport(
        self, executor: JobExecutor, plan: ExecutionPlan, cancel: Event
    ) -> tuple[str, ExecutionReceipt]:
        ref = executor.submit(plan)
        budget = (plan.resource.wall_time_s if plan.resource else self._timeout_s) + 30.0
        deadline = time.monotonic() + budget
        while True:
            if cancel.is_set():
                executor.cancel(ref)
            state = executor.poll(ref)
            if state in {"completed", "failed", "cancelled", "preempted"}:
                return ref, executor.terminal_receipt(ref)
            if time.monotonic() > deadline:
                executor.cancel(ref)
                raise ParticipantError(
                    NativeErrorCode.PROCESS_TIMEOUT, "remote execution exceeded its wall time"
                )
            time.sleep(self._remote_poll_s)

    def _settle_remote_cost(
        self, job_id: str, receipt: ExecutionReceipt, plan: ExecutionPlan, *, preempted: bool
    ) -> Any:
        machine_type = plan.resource.machine_type if plan.resource else "unknown"
        cost = self._cost_ledger.settle(
            job_id,
            actual_cost_usd=receipt.actual_cost_usd,
            runtime_s=receipt.runtime_s,
            machine_type=machine_type,
            preempted=preempted,
        )
        self._record_cost(job_id, cost)
        return cost

    def _verify_and_materialize_remote(
        self,
        executor: JobExecutor,
        ref: str,
        plan: ExecutionPlan,
        receipt: ExecutionReceipt,
        case_dir: Path,
    ) -> None:
        verify_remote_evidence(receipt, plan, self._remote_policy)
        stdout = executor.fetch_stdout(ref)
        stderr = executor.fetch_stderr(ref)
        if hashlib.sha256(stdout).hexdigest() != (receipt.stdout_sha256 or ""):
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, "remote stdout hash mismatch"
            )
        if hashlib.sha256(stderr).hexdigest() != (receipt.stderr_sha256 or ""):
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, "remote stderr hash mismatch"
            )
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "stdout.log").write_bytes(stdout)
        (case_dir / "stderr.log").write_bytes(stderr)
        artifacts = dict(executor.fetch_artifacts(ref))
        declared = {artifact.name: artifact for artifact in receipt.artifacts}
        for name in plan.artifacts:
            if Path(name).name != name:
                raise ParticipantError(
                    NativeErrorCode.RESULT_INVALID, f"unsafe remote artifact name:{name}"
                )
            payload = artifacts.get(name)
            if payload is None:
                raise ParticipantError(
                    NativeErrorCode.RESULT_INVALID, f"remote artifact missing:{name}"
                )
            declared_digest = declared.get(name)
            if declared_digest is None or (
                hashlib.sha256(payload).hexdigest() != declared_digest.sha256
            ):
                raise ParticipantError(
                    NativeErrorCode.RESULT_INVALID, f"remote artifact hash mismatch:{name}"
                )
            (case_dir / name).write_bytes(payload)
        self._mirror_solver_log(case_dir)

    def _preserve_checkpoint(
        self,
        job_id: str,
        case_dir: Path,
        checkpoint: CheckpointReceipt,
        executor: JobExecutor,
        ref: str,
    ) -> None:
        """Materialize the latest accepted checkpoint before the attempt dies."""

        destination = case_dir / "checkpoints" / checkpoint.checkpoint_id
        destination.mkdir(parents=True, exist_ok=True)
        try:
            artifacts = dict(executor.fetch_artifacts(ref))
        except Exception:  # noqa: BLE001 - best-effort preservation, never masked
            artifacts = {}
        for artifact in checkpoint.artifacts:
            payload = artifacts.get(artifact.name)
            if payload is None or Path(artifact.name).name != artifact.name:
                continue
            if hashlib.sha256(payload).hexdigest() != artifact.sha256:
                # Corrupt bytes are never persisted as a trusted checkpoint.
                continue
            (destination / artifact.name).write_bytes(payload)
        (destination / "checkpoint.json").write_text(checkpoint.to_json(), encoding="utf-8")

    # -- checkpoint / preemption / resume (INFRA-FIX 04) ----------------

    def _handle_preemption(
        self,
        manifest: Any,
        job_id: str,
        run_id: str,
        execution: ExecutionReceipt,
        case_dir: Path,
    ) -> str:
        _ = case_dir
        detail = execution.interruption_reason or execution.detail or "remote preemption"
        fields: dict[str, Any] = {
            "error_code": GovernanceErrorCode.PREEMPTED.value,
            "error_detail": detail,
            "interruption_reason": detail,
        }
        checkpoint = execution.checkpoint
        if checkpoint is not None:
            fields["checkpoint_json"] = self._append_checkpoint_blob(job_id, checkpoint)
            fields["checkpoint_id"] = checkpoint.checkpoint_id
        state = self._transition(job_id, JobState.FAILED, f"PREEMPTED:{detail}", fields)
        if checkpoint is not None:
            self._record_checkpoint_provenance(manifest, job_id, run_id, checkpoint)
        self._maybe_auto_resume(manifest, job_id)
        return state

    def _append_checkpoint_blob(self, job_id: str, checkpoint: CheckpointReceipt) -> str:
        payload = self._load_checkpoint_payloads(job_id)
        if checkpoint.checkpoint_id not in {
            str(item.get("checkpoint_id")) for item in payload
        }:
            payload.append(checkpoint.to_payload())
        return json.dumps({"checkpoints": payload}, sort_keys=True, separators=(",", ":"))

    def _load_checkpoint_payloads(self, job_id: str) -> list[dict[str, Any]]:
        row = self._ledger.get(job_id)
        if row is None or not row.checkpoint_json:
            return []
        try:
            data = json.loads(row.checkpoint_json)
        except ValueError:
            return []
        if not isinstance(data, dict):
            return []
        entries = data.get("checkpoints")
        if not isinstance(entries, list):
            return []
        return [item for item in entries if isinstance(item, dict)]

    def _load_checkpoints(self, job_id: str) -> list[CheckpointReceipt]:
        receipts: list[CheckpointReceipt] = []
        for item in self._load_checkpoint_payloads(job_id):
            try:
                artifacts = tuple(
                    CheckpointArtifact(
                        name=str(raw["name"]),
                        sha256=str(raw["sha256"]),
                        bytes=int(raw["bytes"]),
                    )
                    for raw in item.get("artifacts", [])
                    if isinstance(raw, dict)
                )
                payload = dict(item)
                payload["artifacts"] = artifacts
                payload["upstream_hashes"] = tuple(
                    (str(pair[0]), str(pair[1]))
                    for pair in item.get("upstream_hashes", [])
                    if isinstance(pair, list) and len(pair) == 2
                )
                payload["compatibility"] = tuple(
                    (str(pair[0]), str(pair[1]))
                    for pair in item.get("compatibility", [])
                    if isinstance(pair, list) and len(pair) == 2
                )
                receipts.append(CheckpointReceipt(**payload))
            except (KeyError, TypeError, ValueError):
                continue
        return receipts

    def _record_checkpoint_provenance(
        self, manifest: Any, job_id: str, run_id: str, checkpoint: CheckpointReceipt
    ) -> None:
        self._repository.append_provenance(
            event_id=f"checkpoint-{job_id}-{checkpoint.checkpoint_id[:12]}",
            event_type="native.checkpoint-recorded",
            subject_hash=checkpoint.input_hash,
            actor="native-scheduler",
            occurred_at=_now(),
            details={
                "job_id": job_id,
                "run_id": run_id,
                "participant_id": manifest.participant_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "sequence": checkpoint.sequence,
            },
            artifacts=[],
        )

    def _record_cost(self, job_id: str, cost: Any) -> None:
        row = self._ledger.get(job_id)
        if row is None:
            return
        self._ledger.update(
            job_id,
            state=row.state,
            updated_at=_now(),
            cost_json=json.dumps(
                {
                    "planned_max_cost_usd": cost.planned_max_cost_usd,
                    "estimated_cost_usd": cost.estimated_cost_usd,
                    "actual_cost_usd": cost.actual_cost_usd,
                    "runtime_s": cost.runtime_s,
                    "machine_type": cost.machine_type,
                    "preempted": cost.preempted,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def _lineage_chain(self, job_id: str) -> list[str]:
        chain: list[str] = []
        current: str | None = job_id
        seen: set[str] = set()
        while current is not None and current not in seen:
            seen.add(current)
            chain.append(current)
            row = self._ledger.get(current)
            current = row.resume_of if row is not None else None
        return chain

    def _live_checkpoint_hashes(
        self, row: Any, checkpoint: CheckpointReceipt
    ) -> dict[str, str | None]:
        base = self._job_root / f"case-{row.job_id[:12]}" / "checkpoints" / checkpoint.checkpoint_id
        live: dict[str, str | None] = {}
        for artifact in checkpoint.artifacts:
            target = base / artifact.name
            if target.is_file():
                digest, _ = _sha256_file(target)
                live[artifact.name] = digest
            else:
                live[artifact.name] = None
        return live

    def _maybe_auto_resume(self, manifest: Any, job_id: str) -> str | None:
        row = self._ledger.get(job_id)
        if row is None:
            return None
        retry_class = classify_failure(row.error_code, reason=row.error_detail)
        if not self._retry_policy.may_retry(retry_class, row.attempt):
            return None
        if not self._load_checkpoints(job_id):
            return None
        try:
            return self.resume(job_id)
        except ParticipantError:
            return None

    def resume(self, job_id: str, *, checkpoint_id: str | None = None) -> str:
        """Create a trusted resume attempt linked to a failed checkpointed run."""

        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        manifest = get_participant(row.participant_id)
        if row.state == JobState.CANCELLED.value:
            raise ParticipantError(
                GovernanceErrorCode.RESUME_REJECTED,
                "a cancelled job cannot resume automatically",
            )
        if row.state != JobState.FAILED.value:
            raise ParticipantError(
                GovernanceErrorCode.RESUME_REJECTED,
                f"only failed attempts can resume:{row.state}",
            )
        receipts = self._load_checkpoints(job_id)
        if not receipts:
            raise ParticipantError(
                GovernanceErrorCode.CHECKPOINT_UNSUPPORTED,
                f"no trusted checkpoint for mode={manifest.checkpoint_policy}",
            )
        selected: CheckpointReceipt | None = None
        if checkpoint_id is not None:
            selected = next(
                (item for item in receipts if item.checkpoint_id == checkpoint_id), None
            )
            if selected is None:
                raise ParticipantError(
                    GovernanceErrorCode.CHECKPOINT_INCOMPATIBLE,
                    "requested checkpoint not found",
                )
        else:
            selected = receipts[-1]
        expected_input_hash = row.input_hash or _inputs_hash(self._stored_inputs(job_id))
        compatibility = verify_resume_compatibility(
            selected,
            expected_input_hash=expected_input_hash,
            expected_solver_id=manifest.executable.solver_id,
            expected_solver_version=None,
            expected_image_digest=(
                next(iter(self._remote_policy.limits.allowed_image_digests))
                if self._execution_backend == "remote"
                and self._remote_policy.limits.allowed_image_digests
                else None
            ),
            expected_geometry_hash=row.geometry_hash,
            expected_mesh_hash=row.mesh_hash,
            live_artifact_hashes=self._live_checkpoint_hashes(row, selected),
            lineage_ok=selected.job_id in self._lineage_chain(job_id),
        )
        compatibility.require_ok()
        if self._execution_backend == "remote" and self._remote_policy.enabled:
            limits = self._remote_policy.limits
            request = RemoteResourceRequest(
                vcpu=limits.max_vcpu,
                memory_mib=limits.max_memory_mib,
                wall_time_s=self._timeout_s,
                machine_type=limits.machine_type,
                gpu_type=limits.gpu_type if limits.max_gpu_count > 0 else None,
                gpu_count=limits.max_gpu_count,
            )
            plan = self._cost_ledger.plan(job_id, request)
            if self._cost_ledger.remaining_for(plan) < plan.planned_max_cost_usd:
                raise ParticipantError(
                    GovernanceErrorCode.COST_LIMIT_EXCEEDED, "no remaining budget to resume"
                )
        meta = self._request_meta(job_id)
        new_id = self.submit(
            row.participant_id,
            self._stored_inputs(job_id),
            design_id=row.design_id,
            owner_id=row.owner_id,
            revision_id=row.revision_id,
            analysis=meta.get("analysis"),
            fidelity=meta.get("fidelity"),
            requested_memory_mib=meta.get("requested_memory_mib"),
            requested_threads=meta.get("requested_threads"),
            resume_of=job_id,
            attempt=row.attempt + 1,
            checkpoint_id=selected.checkpoint_id,
            deferred=True,
        )
        self._spawn(new_id)
        return new_id

    @staticmethod
    def _mirror_solver_log(case_dir: Path) -> None:
        """Expose the captured stdout as solver.log for manifest parsers.

        The bytes are identical; parsers declare solver.log as their input.
        """

        stdout = case_dir / "stdout.log"
        mirror = case_dir / "solver.log"
        if stdout.is_file() and not mirror.exists():
            mirror.write_bytes(stdout.read_bytes())

    def _publish(
        self,
        manifest: Any,
        job_id: str,
        run_id: str,
        receipt: Any,
        execution: ExecutionReceipt,
        parsed: ParseReceipt,
        validity: Any,
        case_dir: Path,
        probe: Any,
    ) -> ResultEnvelope:
        row = self._ledger.get(job_id)
        input_hash = receipt.input_hash
        solver_version = probe.version or "unknown"
        result_meta = self._read_result_meta(case_dir)
        if isinstance(result_meta.get("solver_version"), str):
            solver_version = str(result_meta["solver_version"])
        geometry_hash = receipt.geometry_hash or self._meta_hash(result_meta, "geometry_hash")
        mesh_hash = receipt.mesh_hash or self._meta_hash(result_meta, "mesh_hash")
        execution_mode = execution.execution_mode
        if execution_mode == "in-process":
            stdout_hash = None
            stderr_hash = None
            peak_rss: float | None = None
            exit_code = 0
        else:
            stdout_hash = execution.stdout_sha256
            stderr_hash = execution.stderr_sha256
            peak_rss = execution.peak_rss_mib
            exit_code = execution.exit_code or 0
        hash_start = time.perf_counter()
        output_files = self._hash_artifacts(case_dir, manifest.artifacts)
        self._hash_ms += (time.perf_counter() - hash_start) * 1000.0
        self._hash_bytes += sum(artifact.bytes for artifact in output_files)
        warnings = self._warnings(manifest, probe)
        evidence = EvidenceBundle(
            capability_state="ready",
            capability_detail=probe.detail,
            solver_name=manifest.executable.solver_id,
            solver_version=solver_version,
            input_hash=input_hash,
            run_id=run_id,
            process_state="completed",
            exit_code=exit_code,
            peak_rss_mib=peak_rss,
            execution_mode=execution_mode,
            stdout_sha256=stdout_hash,
            stderr_sha256=stderr_hash,
            parser_name=manifest.parser_ref,
            parser_detail=parsed.detail,
            output_files=tuple(output_files),
            geometry_hash=geometry_hash,
            mesh_hash=mesh_hash,
            participant_id=manifest.participant_id,
            manifest_version=manifest.manifest_version,
            validity_passed=bool(validity.passed),
            validity_detail=validity.detail,
            executor=self._execution_backend,
            image_digest=execution.image_digest,
            region=execution.region,
            project=execution.project,
            estimated_cost_usd=execution.estimated_cost_usd or None,
            actual_cost_usd=execution.actual_cost_usd,
            checkpoint_id=row.checkpoint_id if row is not None else None,
            resume_of=row.resume_of if row is not None else None,
            attempt=row.attempt if row is not None else 1,
        )
        provenance_id = uuid.uuid4().hex
        fidelity = self._request_meta(job_id).get("fidelity") or manifest.fidelity_levels[0]
        envelope = publish_result(
            evidence,
            parse=parsed,
            validity=validity,
            fidelity=str(fidelity),
            provenance_id=provenance_id,
            warnings=tuple(warnings),
            expected_artifacts=tuple(manifest.artifacts),
        )
        references = [
            ArtifactReference(
                format=self._artifact_format(name),
                uri=f"jobs/{job_id}/{name}",
                sha256=artifact.sha256,
                bytes=artifact.bytes,
            )
            for name, artifact in zip(
                [name for name in manifest.artifacts if name in {a.name for a in output_files}],
                [a for a in output_files if a.name in manifest.artifacts],
                strict=True,
            )
        ]
        self._repository.append_provenance(
            event_id=f"result-{job_id}",
            event_type="native.result-recorded",
            subject_hash=input_hash,
            actor="native-scheduler",
            occurred_at=_now(),
            details={
                "job_id": job_id,
                "participant_id": manifest.participant_id,
                "run_id": run_id,
                "solver_version": solver_version,
                "fidelity": str(fidelity),
            },
            artifacts=references,
        )
        _ = row
        return envelope

    # -- accessors -------------------------------------------------------

    def status(self, job_id: str) -> dict[str, Any]:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        meta = self._request_meta(job_id)
        manifest = get_participant(row.participant_id)
        return {
            "job_id": row.job_id,
            "participant_id": row.participant_id,
            "design_id": row.design_id,
            "owner_id": row.owner_id,
            "revision_id": row.revision_id,
            "analysis": meta.get("analysis"),
            "fidelity": meta.get("fidelity") or manifest.fidelity_levels[0],
            "state": row.state,
            "error_code": row.error_code,
            "error_detail": row.error_detail,
            "run_id": row.run_id,
            "result_id": row.result_id,
            "provenance_id": row.provenance_id,
            "input_hash": row.input_hash,
            "executor": self._execution_backend,
            "resume_of": row.resume_of,
            "attempt": row.attempt,
            "checkpoint_id": row.checkpoint_id,
            "interruption_reason": row.interruption_reason,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def events(self, job_id: str) -> list[dict[str, Any]]:
        if self._ledger.get(job_id) is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        return [
            {
                "sequence": event.sequence,
                "state": event.state,
                "at": event.at,
                "detail": event.detail,
            }
            for event in self._ledger.events(job_id)
        ]

    def envelope(self, job_id: str) -> dict[str, Any]:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        if row.state != JobState.COMPLETED.value or not row.envelope_json:
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, f"no published envelope:{row.state}"
            )
        return cast("dict[str, Any]", json.loads(row.envelope_json))

    def artifacts(self, job_id: str) -> list[dict[str, Any]]:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        case_dir = self._job_root / f"case-{job_id[:12]}"
        manifest = get_participant(row.participant_id)
        manifest_names = list(manifest.artifacts)
        extra = ["stdout.log", "stderr.log"] if (case_dir / "stdout.log").exists() else []
        entries: list[dict[str, Any]] = []
        start = time.perf_counter()
        total_bytes = 0
        for name in manifest_names + extra:
            target = case_dir / name
            if target.is_file():
                digest, size = _sha256_file_cached(target)
                total_bytes += size
                entries.append(
                    {"name": name, "sha256": digest, "bytes": size, "uri": f"jobs/{job_id}/{name}"}
                )
        self._artifact_read_ms += (time.perf_counter() - start) * 1000.0
        self._artifact_read_bytes += total_bytes
        return entries

    def artifact_metadata(self, job_id: str) -> list[dict[str, Any]]:
        """Bounded read-only metadata for artifacts registered to a result.

        Only files already registered to the job (manifest outputs plus
        captured solver logs actually present on disk) are exposed. No
        directory listing or arbitrary paths leave this method.
        """

        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        manifest = get_participant(row.participant_id)
        enriched: list[dict[str, Any]] = []
        for entry in self.artifacts(job_id):
            name = str(entry["name"])
            enriched.append(
                {
                    "id": name,
                    "name": name,
                    "display_name": name,
                    "mime": artifact_mime_for(name),
                    "category": artifact_category_for(name),
                    "bytes": entry["bytes"],
                    "sha256": entry["sha256"],
                    "solver_id": manifest.executable.solver_id,
                    "run_id": row.run_id,
                    "provenance_id": row.provenance_id,
                    "download_url": f"/v1/native/artifacts/{job_id}/{name}",
                    "uri": entry["uri"],
                }
            )
        return enriched

    def _artifact_target(self, job_id: str, artifact_name: str) -> tuple[Any, Path]:
        """Resolve one declared artifact without listing or arbitrary paths.

        The name must match a declared output exactly (rejecting every
        traversal spelling) and the resolved path must stay inside the job case
        directory. Raises the same KeyError codes the API maps to 404s.
        """

        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        manifest = get_participant(row.participant_id)
        case_dir = self._job_root / f"case-{job_id[:12]}"
        declared = list(manifest.artifacts)
        if (case_dir / "stdout.log").exists():
            declared += ["stdout.log", "stderr.log"]
        if not artifact_name or artifact_name != Path(artifact_name).name:
            raise KeyError(f"ARTIFACT_NOT_FOUND:{job_id}:{artifact_name}")
        if artifact_name not in declared:
            raise KeyError(f"ARTIFACT_NOT_FOUND:{job_id}:{artifact_name}")
        target = (case_dir / artifact_name).resolve()
        if target.parent != case_dir.resolve() or not target.is_file():
            raise KeyError(f"ARTIFACT_UNAVAILABLE:{job_id}:{artifact_name}")
        return row, target

    @staticmethod
    def _artifact_baseline(row: Any, artifact_name: str) -> str | None:
        """The envelope-recorded digest for a completed job, or None."""

        if row.state != JobState.COMPLETED.value or not row.envelope_json:
            return None
        baseline = {
            str(item.get("name")): str(item.get("sha256"))
            for item in cast("dict[str, Any]", json.loads(row.envelope_json)).get(
                "artifacts", []
            )
            if isinstance(item, dict)
        }
        expected = baseline.get(artifact_name)
        if expected is None:
            raise KeyError(f"ARTIFACT_NOT_FOUND:{row.job_id}:{artifact_name}")
        return expected

    def read_artifact(self, job_id: str, artifact_name: str) -> tuple[bytes, str, dict[str, Any]]:
        """Return the bytes of one registered artifact after containment+hash checks.

        Resolution goes only through repository metadata: the name must match
        a declared output exactly (which rejects every traversal spelling),
        the resolved path must stay inside the job case directory, and for a
        completed job the on-disk bytes must still match the digest recorded
        in the published envelope.
        """

        row, target = self._artifact_target(job_id, artifact_name)
        payload = target.read_bytes()
        expected = self._artifact_baseline(row, artifact_name)
        if expected is not None and hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"ARTIFACT_HASH_MISMATCH:{job_id}:{artifact_name}")
        metadata = next(
            item for item in self.artifact_metadata(job_id) if item["id"] == artifact_name
        )
        return payload, artifact_mime_for(artifact_name), metadata

    def verify_artifact(
        self, job_id: str, artifact_name: str
    ) -> tuple[Path, str, int, dict[str, Any]]:
        """Verify one artifact by streaming its bytes, then return its descriptor.

        Hash verification remains mandatory: for a completed job the file is
        streamed through SHA-256 in bounded chunks and compared to the
        published envelope digest. The artifact is never loaded whole into
        memory, and retrieval serves ids/ranges rather than blobs.
        """

        row, target = self._artifact_target(job_id, artifact_name)
        expected = self._artifact_baseline(row, artifact_name)
        start = time.perf_counter()
        if expected is not None:
            actual, size = _sha256_file(target)
            if actual != expected:
                raise ValueError(f"ARTIFACT_HASH_MISMATCH:{job_id}:{artifact_name}")
        else:
            size = target.stat().st_size
        self._artifact_read_ms += (time.perf_counter() - start) * 1000.0
        self._artifact_read_bytes += size
        metadata = next(
            item for item in self.artifact_metadata(job_id) if item["id"] == artifact_name
        )
        return target, artifact_mime_for(artifact_name), size, metadata

    @staticmethod
    def stream_file(
        target: Path,
        *,
        offset: int = 0,
        length: int | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        """Yield a verified file (or byte range) in bounded chunks."""

        size = target.stat().st_size
        if offset < 0 or offset > size:
            raise ValueError("ARTIFACT_RANGE_INVALID")
        if length is None:
            remaining = size - offset
        else:
            if length < 0:
                raise ValueError("ARTIFACT_RANGE_INVALID")
            remaining = min(length, size - offset)

        def _stream() -> Iterator[bytes]:
            nonlocal remaining
            with target.open("rb") as stream:
                stream.seek(offset)
                while remaining > 0:
                    chunk = stream.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return _stream()

    def iter_artifact(
        self,
        job_id: str,
        artifact_name: str,
        *,
        offset: int = 0,
        length: int | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> tuple[Iterator[bytes], str, int]:
        """Stream one verified artifact (optionally a byte range), bounded memory."""

        target, mime, size, _metadata = self.verify_artifact(job_id, artifact_name)
        return (
            self.stream_file(target, offset=offset, length=length, chunk_size=chunk_size),
            mime,
            size,
        )

    def result_manifest(self, job_id: str) -> dict[str, Any]:
        """Small machine-readable manifest: lineage and hashes, never blobs."""

        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        if row.state != JobState.COMPLETED.value or not row.envelope_json:
            raise ParticipantError(
                NativeErrorCode.RESULT_INVALID, f"no published envelope:{row.state}"
            )
        envelope = cast("dict[str, Any]", json.loads(row.envelope_json))
        raw_validity = envelope.get("validity")
        validity: dict[str, Any] = raw_validity if isinstance(raw_validity, dict) else {}
        return {
            "job_id": row.job_id,
            "design_id": row.design_id,
            "revision_id": row.revision_id,
            "result_id": row.result_id,
            "run_id": row.run_id,
            "provenance_id": row.provenance_id,
            "source": envelope.get("source"),
            "fidelity": envelope.get("fidelity"),
            "validity": {
                "passed": validity.get("passed") is True,
                "detail": str(validity.get("detail") or ""),
            },
            "solver_identity": envelope.get("solver_identity"),
            "solver_version": envelope.get("solver_version"),
            "input_hash": row.input_hash or envelope.get("input_hash"),
            "artifacts": [
                {"name": str(entry["name"]), "sha256": entry["sha256"], "bytes": entry["bytes"]}
                for entry in self.artifacts(job_id)
            ],
        }

    def provenance(self, job_id: str) -> list[dict[str, Any]]:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        # Launch acceptance is recorded under the submit-time inputs hash while
        # the result is recorded under the validated case hash; report both so
        # the lineage reads launch-accepted -> result-recorded.
        subjects: list[str] = []
        if row.inputs_json:
            try:
                stored = json.loads(row.inputs_json)
                subjects.append(_inputs_hash(dict(stored["inputs"])))
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
        if row.input_hash:
            subjects.append(row.input_hash)
        merged: dict[str, dict[str, Any]] = {}
        for subject in subjects:
            for event in self._repository.list_provenance(subject):
                # The provenance store is shared across jobs and restarts, and
                # identical inputs hash identically: keep only this job's lineage.
                details = event.details if isinstance(event.details, dict) else {}
                if details.get("job_id") != job_id:
                    continue
                merged[event.event_id] = event.model_dump(mode="json")
        return [merged[key] for key in sorted(merged, key=lambda key: merged[key]["sequence"])]

    # -- metrics (PERF 01 / PERF 02 / PERF 06 reporting) -----------------

    def scheduler_metrics(self) -> dict[str, Any]:
        """Queue delay, occupancy, active reservation, and utilization."""

        return self._scheduler.metrics()

    def persistence_metrics(self) -> dict[str, Any]:
        """DB commit time, bytes hashed, artifact read time, and digest reuse."""

        return {
            "ledger": self._ledger.metrics(),
            "repository": self._repository.metrics(),
            "hash_bytes": self._hash_bytes,
            "hash_ms": round(self._hash_ms, 6),
            "artifact_read_bytes": self._artifact_read_bytes,
            "artifact_read_ms": round(self._artifact_read_ms, 6),
            "digest_cache": _DIGEST_CACHE.metrics(),
        }

    # -- internals -------------------------------------------------------

    def _stored_inputs(self, job_id: str) -> dict[str, object]:
        inputs = self._request_blob(job_id).get("inputs", {})
        if not isinstance(inputs, dict):
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED, "stored inputs are not a mapping"
            )
        return dict(inputs)

    def _request_meta(self, job_id: str) -> dict[str, Any]:
        blob = self._request_blob(job_id)
        keys = ("analysis", "fidelity", "requested_memory_mib", "requested_threads")
        return {key: blob[key] for key in keys if key in blob}

    def _request_blob(self, job_id: str) -> dict[str, Any]:
        row = self._ledger.get(job_id)
        if row is None or not row.inputs_json:
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED, f"stored inputs missing:{job_id}"
            )
        try:
            data = json.loads(row.inputs_json)
        except ValueError as exc:
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED, f"stored inputs corrupt:{exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED, "stored request is not a mapping"
            )
        return dict(data)

    def _transition(
        self,
        job_id: str,
        state: JobState,
        detail: str,
        fields: Mapping[str, Any] | None = None,
    ) -> str:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        try:
            current = JobState(row.state)
        except ValueError as exc:
            raise ValueError(f"ILLEGAL_JOB_TRANSITION:unknown stored state:{row.state}") from exc
        if state not in _LEGAL_TRANSITIONS[current]:
            raise ValueError(f"ILLEGAL_JOB_TRANSITION:{current.value}->{state.value}")
        # Terminal metadata (result/error ids) and the event row commit in ONE
        # transaction, so a concurrent poller can never observe a terminal
        # state before its metadata (e.g. FAILED with a missing error_code) and
        # the persisted event stream can never drift from the job row.
        self._ledger.transition(
            job_id,
            state=state.value,
            updated_at=_now(),
            detail=detail,
            fields=dict(fields) if fields else None,
        )
        return state.value

    @staticmethod
    def _read_result_meta(case_dir: Path) -> dict[str, Any]:
        target = case_dir / "result.json"
        if not target.is_file():
            return {}
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _meta_hash(meta: Mapping[str, Any], key: str) -> str | None:
        value = meta.get(key)
        if (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        ):
            return value
        return None

    @staticmethod
    def _hash_artifacts(case_dir: Path, expected: tuple[str, ...]) -> list[ArtifactFile]:
        produced: list[ArtifactFile] = []
        for name in sorted(set(expected) | {"stdout.log", "stderr.log"}):
            target = case_dir / name
            if "/" in name or "\\" in name or not target.is_file():
                continue
            digest, size = _sha256_file_cached(target)
            produced.append(ArtifactFile(name=name, sha256=digest, bytes=size))
        return produced

    @staticmethod
    def _warnings(manifest: Any, probe: Any) -> list[str]:
        warnings: list[str] = []
        if manifest.executable.solver_id == "ross":
            warnings.append(
                "NUMBA_DISABLE_JIT=1 was set for ROSS compatibility; numerics unaffected"
            )
        detail = str(probe.detail)
        if "fallback" in detail.lower():
            warnings.append(detail)
        return warnings

    @staticmethod
    def _artifact_format(name: str) -> Any:
        suffix = Path(name).suffix.lower().lstrip(".")
        mapping = {
            "log": "log",
            "json": "json",
            "msh": "msh",
            "sif": "sif",
            "comm": "comm",
            "export": "txt",
            "xml": "xml",
            "py": "py",
            "txt": "txt",
            "dat": "dat",
            "step": "step",
            "brep": "brep",
            "vtu": "vtk",
            "msh2": "msh",
        }
        return mapping.get(suffix, "txt")
