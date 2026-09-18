"""Governed native job lifecycle: prepare, schedule, execute, parse, publish.

One public path serves every participant: PREPARE -> VALIDATE INPUTS ->
SCHEDULE -> EXECUTE -> MONITOR -> PARSE -> VALIDATE RESULT -> HASH ARTIFACTS
-> ResultEnvelope -> STORE PROVENANCE. Job states persist in the ledger;
results publish only through the evidence-gated envelope path.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import os
import threading
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Any, cast

from aeroworkbench_api.process_supervisor import ProcessReceipt
from aeroworkbench_api.repositories.sqlite import ArtifactReference, SQLiteRepository
from participants.capabilities import probe_participant
from participants.commands import build_command, require_opaque_case_id
from participants.envelope import (
    ArtifactFile,
    EvidenceBundle,
    ResultEnvelope,
    publish_result,
)
from participants.errors import NativeErrorCode, ParticipantError
from participants.manifest import get_participant
from participants.receipts import ParseReceipt
from participants.runner import SUPERVISOR_RSS_LIMIT_MIB, run_governed
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


class NativeJobManager:
    """Single-worker governed execution for every native participant."""

    def __init__(
        self,
        job_root: Path,
        *,
        repository: SQLiteRepository | None = None,
        ledger: JobLedger | None = None,
        rss_limit_mib: float = 352.0,
        supervisor_rss_limit_mib: float = SUPERVISOR_RSS_LIMIT_MIB,
        timeout_s: float = 900.0,
    ) -> None:
        if not 0 < rss_limit_mib <= 896.0:
            raise ValueError("INVALID_RSS_LIMIT")
        if not 0 < supervisor_rss_limit_mib <= 896.0:
            raise ValueError("INVALID_SUPERVISOR_RSS_LIMIT")
        if supervisor_rss_limit_mib < rss_limit_mib:
            raise ValueError("SUPERVISOR_RSS_LIMIT_BELOW_ADMISSION_BUDGET")
        if timeout_s <= 0:
            raise ValueError("INVALID_TIMEOUT")
        self._job_root = job_root
        self._job_root.mkdir(parents=True, exist_ok=True)
        self._repository = repository or SQLiteRepository(job_root / "provenance.sqlite3")
        self._ledger = ledger or JobLedger(job_root / "native_jobs.sqlite3")
        self._rss_limit_mib = rss_limit_mib
        self._supervisor_rss_limit_mib = supervisor_rss_limit_mib
        self._timeout_s = timeout_s
        self._worker_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cancel_flags: dict[str, Event] = {}
        self._supervisor_cancels: dict[str, Event] = {}
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
    ) -> str:
        manifest = get_participant(participant_id)  # raises ValueError if unknown
        if not isinstance(inputs, dict):
            raise ValueError("INVALID_JOB_INPUTS:inputs must be a mapping")
        if not design_id.strip():
            raise ValueError("INVALID_JOB_INPUTS:design id required")
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
        digest = _inputs_hash(inputs)
        job_id = uuid.uuid4().hex
        case_id = f"case-{job_id[:12]}"
        created = _now()
        self._ledger.create(
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
            },
            owner_id=owner_id,
            revision_id=revision_id,
        )
        self._ledger.append_event(
            job_id=job_id, state=JobState.QUEUED.value, at=created, detail=f"input_hash={digest}"
        )
        with self._state_lock:
            self._cancel_flags[job_id] = Event()
        self._repository.append_provenance(
            event_id=f"launch-{job_id}",
            event_type="native.launch-accepted",
            subject_hash=digest,
            actor="native-scheduler",
            occurred_at=created,
            details={"job_id": job_id, "participant_id": participant_id, "design_id": design_id},
            artifacts=[],
        )
        if not deferred:
            thread = threading.Thread(
                target=self.run, args=(job_id,), name=f"native-{job_id[:8]}", daemon=True
            )
            thread.start()
        return job_id

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

    # -- execution -------------------------------------------------------

    def run(self, job_id: str) -> str:
        with self._worker_lock:
            return self._run_guarded(job_id)

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
            self._transition(job_id, JobState.RUNNING, f"run_id={run_id}")
            self._ledger.update(
                job_id, state=JobState.RUNNING.value, updated_at=_now(), run_id=run_id
            )
            process_receipt = self._execute(manifest, job_id, case_dir)
            if self._cancelled(job_id):
                return self._transition(job_id, JobState.CANCELLED, "cancelled during run")
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
                process_receipt,
                parsed,
                validity,
                case_dir,
                probe,
            )
            envelope_json = envelope.model_dump_json()
            result_id = hashlib.sha256(envelope_json.encode("utf-8")).hexdigest()
            completed = self._transition(job_id, JobState.COMPLETED, f"run_id={run_id}")
            self._ledger.update(
                job_id,
                state=JobState.COMPLETED.value,
                updated_at=_now(),
                envelope_json=envelope_json,
                result_id=result_id,
                provenance_id=envelope.provenance_id,
            )
            return completed
        except ParticipantError as exc:
            failed = self._transition(job_id, JobState.FAILED, f"{exc.code.value}:{exc.detail}")
            self._ledger.update(
                job_id,
                state=JobState.FAILED.value,
                updated_at=_now(),
                error_code=exc.code.value,
                error_detail=exc.detail,
            )
            return failed
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}:{exc}"
            failed = self._transition(job_id, JobState.FAILED, detail)
            self._ledger.update(
                job_id,
                state=JobState.FAILED.value,
                updated_at=_now(),
                error_code=NativeErrorCode.RESULT_INVALID.value,
                error_detail=detail,
            )
            return failed

    def _execute(
        self, manifest: Any, job_id: str, case_dir: Path
    ) -> ProcessReceipt | None:
        require_opaque_case_id(case_dir.name)
        if manifest.executable.execution_mode == "in-process":
            if manifest.execute_ref is None:
                raise ParticipantError(
                    NativeErrorCode.PREPARATION_FAILED, "in-process participant needs execute_ref"
                )
            execute = _resolve(manifest.execute_ref)
            execute(self._stored_inputs(job_id), case_dir)
            return None
        command = build_command(manifest.participant_id, case_dir.name)
        supervisor_cancel = Event()
        with self._state_lock:
            self._supervisor_cancels[job_id] = supervisor_cancel
        if self._cancelled(job_id):
            supervisor_cancel.set()
        try:
            receipt = run_governed(
                command,
                case_dir=case_dir,
                job_root=self._job_root,
                rss_limit_mib=self._supervisor_rss_limit_mib,
                timeout_s=self._timeout_s,
                cancel=supervisor_cancel,
                extra_env=_PYTHON_MODULE_ENVS.get(manifest.executable.solver_id),
            )
            self._mirror_solver_log(case_dir)
            return receipt
        finally:
            with self._state_lock:
                self._supervisor_cancels.pop(job_id, None)

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
        process_receipt: ProcessReceipt | None,
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
        if process_receipt is None:
            execution_mode = "in-process"
            stdout_hash = None
            stderr_hash = None
            peak_rss: float | None = None
            exit_code = 0
        else:
            execution_mode = "subprocess"
            stdout_hash = process_receipt.stdout_sha256
            stderr_hash = process_receipt.stderr_sha256
            peak_rss = process_receipt.peak_rss_mib
            exit_code = process_receipt.exit_code or 0
        output_files = self._hash_artifacts(case_dir, manifest.artifacts)
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
        for name in manifest_names + extra:
            target = case_dir / name
            if target.is_file():
                digest, size = _sha256_file(target)
                entries.append(
                    {"name": name, "sha256": digest, "bytes": size, "uri": f"jobs/{job_id}/{name}"}
                )
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

    def read_artifact(self, job_id: str, artifact_name: str) -> tuple[bytes, str, dict[str, Any]]:
        """Return the bytes of one registered artifact after containment+hash checks.

        Resolution goes only through repository metadata: the name must match
        a declared output exactly (which rejects every traversal spelling),
        the resolved path must stay inside the job case directory, and for a
        completed job the on-disk bytes must still match the digest recorded
        in the published envelope.
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
        payload = target.read_bytes()
        if row.state == JobState.COMPLETED.value and row.envelope_json:
            baseline = {
                str(item.get("name")): str(item.get("sha256"))
                for item in cast("dict[str, Any]", json.loads(row.envelope_json)).get(
                    "artifacts", []
                )
                if isinstance(item, dict)
            }
            expected = baseline.get(artifact_name)
            if expected is None:
                raise KeyError(f"ARTIFACT_NOT_FOUND:{job_id}:{artifact_name}")
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError(f"ARTIFACT_HASH_MISMATCH:{job_id}:{artifact_name}")
        metadata = next(
            item for item in self.artifact_metadata(job_id) if item["id"] == artifact_name
        )
        return payload, artifact_mime_for(artifact_name), metadata

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
        keys = ("analysis", "fidelity", "requested_memory_mib")
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

    def _transition(self, job_id: str, state: JobState, detail: str) -> str:
        row = self._ledger.get(job_id)
        if row is None:
            raise KeyError(f"JOB_NOT_FOUND:{job_id}")
        try:
            current = JobState(row.state)
        except ValueError as exc:
            raise ValueError(f"ILLEGAL_JOB_TRANSITION:unknown stored state:{row.state}") from exc
        if state not in _LEGAL_TRANSITIONS[current]:
            raise ValueError(f"ILLEGAL_JOB_TRANSITION:{current.value}->{state.value}")
        self._ledger.update(job_id, state=state.value, updated_at=_now())
        self._ledger.append_event(job_id=job_id, state=state.value, at=_now(), detail=detail)
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
            digest, size = _sha256_file(target)
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
