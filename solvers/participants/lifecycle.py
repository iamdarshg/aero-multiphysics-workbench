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
from participants.runner import run_governed
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
    READY = "READY"
    RUNNING = "RUNNING"
    PARSING = "PARSING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset({JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED})


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
        timeout_s: float = 900.0,
    ) -> None:
        if not 0 < rss_limit_mib <= 896.0:
            raise ValueError("INVALID_RSS_LIMIT")
        if timeout_s <= 0:
            raise ValueError("INVALID_TIMEOUT")
        self._job_root = job_root
        self._job_root.mkdir(parents=True, exist_ok=True)
        self._repository = repository or SQLiteRepository(":memory:")
        self._ledger = ledger or JobLedger(job_root / "native_jobs.sqlite3")
        self._rss_limit_mib = rss_limit_mib
        self._timeout_s = timeout_s
        self._worker_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cancel_flags: dict[str, Event] = {}
        self._supervisor_cancels: dict[str, Event] = {}

    # -- submission ------------------------------------------------------

    def submit(
        self,
        participant_id: str,
        inputs: dict[str, object],
        *,
        design_id: str = "generic-design",
        deferred: bool = False,
    ) -> str:
        manifest = get_participant(participant_id)  # raises ValueError if unknown
        _ = manifest
        if not isinstance(inputs, dict):
            raise ValueError("INVALID_JOB_INPUTS:inputs must be a mapping")
        if not design_id.strip():
            raise ValueError("INVALID_JOB_INPUTS:design id required")
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
            inputs={"inputs": inputs, "case_id": case_id},
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
            self._transition(job_id, JobState.READY, f"files={len(receipt.files)}")
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
            self._ledger.update(
                job_id,
                state=JobState.COMPLETED.value,
                updated_at=_now(),
                envelope_json=envelope.model_dump_json(),
            )
            return self._transition(job_id, JobState.COMPLETED, f"run_id={run_id}")
        except ParticipantError as exc:
            self._transition(job_id, JobState.FAILED, f"{exc.code.value}:{exc.detail}")
            self._ledger.update(
                job_id,
                state=JobState.FAILED.value,
                updated_at=_now(),
                error_code=exc.code.value,
                error_detail=exc.detail,
            )
            return JobState.FAILED.value
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}:{exc}"
            self._transition(job_id, JobState.FAILED, detail)
            self._ledger.update(
                job_id,
                state=JobState.FAILED.value,
                updated_at=_now(),
                error_code=NativeErrorCode.RESULT_INVALID.value,
                error_detail=detail,
            )
            return JobState.FAILED.value

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
                rss_limit_mib=self._rss_limit_mib,
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
        envelope = publish_result(
            evidence,
            parse=parsed,
            validity=validity,
            fidelity=manifest.fidelity_levels[0],
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
                "fidelity": manifest.fidelity_levels[0],
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
        return {
            "job_id": row.job_id,
            "participant_id": row.participant_id,
            "design_id": row.design_id,
            "state": row.state,
            "error_code": row.error_code,
            "error_detail": row.error_detail,
            "run_id": row.run_id,
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
                merged[event.event_id] = event.model_dump(mode="json")
        return [merged[key] for key in sorted(merged, key=lambda key: merged[key]["sequence"])]

    # -- internals -------------------------------------------------------

    def _stored_inputs(self, job_id: str) -> dict[str, object]:
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
        inputs = data.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ParticipantError(
                NativeErrorCode.PREPARATION_FAILED, "stored inputs are not a mapping"
            )
        return dict(inputs)

    def _transition(self, job_id: str, state: JobState, detail: str) -> str:
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
