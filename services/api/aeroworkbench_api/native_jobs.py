"""Governed native scheduling routes: capabilities, submit, status, results."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from participants.capabilities import probe_all
from participants.errors import ParticipantError
from participants.executors import GCPBatchExecutor
from participants.lifecycle import NativeJobManager
from participants.manifest import PARTICIPANT_MANIFESTS
from participants.remote_policy import RemoteComputePolicy
from pydantic import BaseModel, ConfigDict, Field


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    design_id: str = Field(default="generic-design", min_length=1)
    deferred: bool = False
    owner_id: str | None = Field(default=None, min_length=1)
    revision_id: str | None = Field(default=None, min_length=1)
    analysis: str | None = Field(default=None, min_length=1)
    fidelity: str | None = Field(default=None, min_length=1)
    requested_memory_mib: float | None = None
    requested_threads: int | None = Field(default=None, ge=1)


def default_job_root() -> Path:
    """Stable on-disk home for the governed job lifecycle.

    Terminal job records must survive API restarts, so the default is a fixed
    directory (overridable with AEROWORKBENCH_JOB_ROOT), never a temp dir.
    """

    override = os.environ.get("AEROWORKBENCH_JOB_ROOT", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".aeroworkbench" / "native-jobs"


def _manager_for(root: Path) -> NativeJobManager:
    """Build the governed manager from user-owned environment switches only.

    There is deliberately no request/body path to remote compute: the backend is
    selected exclusively by operator environment. When remote is selected the
    user-owned policy must be enabled and a worker image digest pinned, or the
    manager fails closed instead of silently falling back to local execution.
    """

    policy = RemoteComputePolicy.from_environment()
    backend = os.environ.get("AEROWORKBENCH_EXECUTION_BACKEND", "local").strip().lower()
    if backend == "remote":
        executor = GCPBatchExecutor(
            policy,
            project=(os.environ.get("AEROWORKBENCH_GCP_PROJECT", "").strip() or None),
            region=(os.environ.get("AEROWORKBENCH_GCP_REGION", "").strip() or None),
            image_digest=(
                os.environ.get("AEROWORKBENCH_GCP_IMAGE_DIGEST", "").strip() or None
            ),
        )
        return NativeJobManager(
            root,
            execution_backend="remote",
            remote_policy=policy,
            remote_executor=executor,
        )
    return NativeJobManager(root, remote_policy=policy)


def _cancel_job(manager: NativeJobManager, job_id: str) -> dict[str, Any]:
    try:
        state = manager.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"}) from exc
    except ParticipantError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code.value, "message": exc.detail},
        ) from exc
    return {"job_id": job_id, "state": state}


def _parse_byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse one HTTP ``bytes=start-end`` range; ``None`` serves the whole file.

    Malformed or multi-range requests fall back to a full 200 response rather
    than guessing. A valid range yields ``(offset, length)`` for a 206.
    """

    if not header or size <= 0:
        return None
    value = header.strip().lower()
    if not value.startswith("bytes=") or "," in value:
        return None
    spec = value[len("bytes="):].strip()
    start_text, _, end_text = spec.partition("-")
    try:
        if start_text == "":
            suffix = int(end_text)
            if suffix <= 0:
                return None
            offset = max(0, size - suffix)
            return offset, size - offset
        offset = int(start_text)
        end = size - 1 if end_text == "" else int(end_text)
    except ValueError:
        return None
    if offset < 0 or offset >= size or end < offset:
        return None
    end = min(end, size - 1)
    return offset, end - offset + 1


def _sse_body(events: list[dict[str, Any]]) -> str:
    """Render persisted transitions as SSE; every event keeps its ledger identity."""

    chunks: list[str] = []
    for event in events:
        payload = {
            "sequence": event["sequence"],
            "state": event["state"],
            "at": event["at"],
            "detail": str(event.get("detail", ""))[:500],
        }
        chunks.append(f"event: progress\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n")
    return "".join(chunks)


def build_native_router(job_root: Path | None = None) -> tuple[APIRouter, NativeJobManager]:
    root = job_root or default_job_root()
    manager = _manager_for(root)
    router = APIRouter()

    @router.get("/v1/native/capabilities")
    def capabilities() -> dict[str, Any]:
        probes = probe_all()
        return {
            "ready": [
                {
                    "participant_id": probe.participant_id,
                    "solver_id": probe.solver_id,
                    "executable": probe.executable,
                    "version": probe.version,
                    "detail": probe.detail,
                }
                for probe in probes
                if probe.state == "ready"
            ],
            "unavailable": [
                {
                    "participant_id": probe.participant_id,
                    "solver_id": probe.solver_id,
                    "executable": probe.executable,
                    "detail": probe.detail,
                }
                for probe in probes
                if probe.state != "ready"
            ],
        }

    @router.get("/v1/native/participants")
    def participants() -> dict[str, Any]:
        return {
            "manifest_version": "2",
            "participants": [
                {
                    "participant_id": manifest.participant_id,
                    "physics_domain": manifest.physics_domain,
                    "solver_id": manifest.executable.solver_id,
                    "execution_mode": manifest.executable.execution_mode,
                    "inputs": [
                        {"name": port.name, "kind": port.kind, "unit": port.unit}
                        for port in manifest.inputs
                    ],
                    "outputs": [
                        {"name": port.name, "kind": port.kind, "unit": port.unit}
                        for port in manifest.outputs
                    ],
                    "fidelity_levels": list(manifest.fidelity_levels),
                    "coupling_direction": manifest.coupling_direction,
                    "benchmark_ref": manifest.benchmark_ref,
                }
                for manifest in PARTICIPANT_MANIFESTS
            ],
        }

    @router.post("/v1/native/analyses", status_code=status.HTTP_202_ACCEPTED)
    def submit(request: SubmitRequest) -> dict[str, Any]:
        try:
            job_id = manager.submit(
                request.participant_id,
                dict(request.inputs),
                design_id=request.design_id,
                deferred=request.deferred,
                owner_id=request.owner_id,
                revision_id=request.revision_id,
                analysis=request.analysis,
                fidelity=request.fidelity,
                requested_memory_mib=request.requested_memory_mib,
                requested_threads=request.requested_threads,
            )
        except ValueError as exc:
            message = str(exc)
            if message.startswith("UNKNOWN_PARTICIPANT"):
                raise HTTPException(
                    status_code=404, detail={"code": "UNKNOWN_PARTICIPANT"}
                ) from exc
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_JOB_INPUTS", "message": message}
            ) from exc
        return {"job_id": job_id, **manager.status(job_id)}

    @router.get("/v1/native/analyses/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        try:
            return manager.status(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc

    @router.get("/v1/native/analyses/{job_id}/events", response_model=None)
    def job_events(job_id: str, request: Request) -> Response | dict[str, Any]:
        try:
            events = manager.events(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"}) from exc
        if "text/event-stream" in request.headers.get("accept", ""):
            return Response(content=_sse_body(events), media_type="text/event-stream")
        return {"job_id": job_id, "events": events}

    @router.post("/v1/native/analyses/{job_id}/start", status_code=status.HTTP_202_ACCEPTED)
    def job_start(job_id: str) -> dict[str, Any]:
        try:
            current = manager.status(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc
        if current["state"] != "QUEUED":
            raise HTTPException(
                status_code=409,
                detail={"code": "JOB_ALREADY_STARTED", "state": current["state"]},
            )
        manager.start(job_id)
        return {"job_id": job_id, "state": "QUEUED"}

    @router.post("/v1/native/analyses/{job_id}/cancel")
    def job_cancel(job_id: str) -> dict[str, Any]:
        return _cancel_job(manager, job_id)

    @router.delete("/v1/native/analyses/{job_id}/cancel")
    def job_cancel_delete(job_id: str) -> dict[str, Any]:
        return _cancel_job(manager, job_id)

    @router.get("/v1/native/results/{job_id}")
    def job_result(job_id: str) -> dict[str, Any]:
        try:
            return manager.envelope(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc
        except ParticipantError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "RESULT_NOT_PUBLISHED", "message": exc.detail},
            ) from exc

    @router.get("/v1/native/artifacts/{job_id}")
    def job_artifacts(job_id: str) -> dict[str, Any]:
        try:
            return {"job_id": job_id, "artifacts": manager.artifact_metadata(job_id)}
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc

    @router.get("/v1/native/artifacts/{job_id}/{artifact_name}")
    def job_artifact_download(
        job_id: str, artifact_name: str, request: Request
    ) -> Response:
        try:
            # verify_artifact streams the file through SHA-256 in bounded chunks
            # and rejects tampered bytes *before* any payload is served; the
            # response then streams ids/ranges instead of a giant JSON value.
            target, mime, size, _metadata = manager.verify_artifact(job_id, artifact_name)
        except KeyError as exc:
            # NOTE: str(KeyError) wraps the message in quotes; match on args.
            message = str(exc.args[0]) if exc.args else ""
            if message.startswith("JOB_NOT_FOUND"):
                raise HTTPException(
                    status_code=404, detail={"code": "JOB_NOT_FOUND"}
                ) from exc
            if message.startswith("ARTIFACT_UNAVAILABLE"):
                raise HTTPException(
                    status_code=404, detail={"code": "ARTIFACT_UNAVAILABLE"}
                ) from exc
            raise HTTPException(
                status_code=404, detail={"code": "ARTIFACT_NOT_FOUND"}
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=409, detail={"code": "ARTIFACT_HASH_MISMATCH"}
            ) from exc
        headers = {
            "Content-Disposition": f'attachment; filename="{artifact_name}"',
            "Accept-Ranges": "bytes",
        }
        byte_range = _parse_byte_range(request.headers.get("range"), size)
        if byte_range is not None:
            offset, length = byte_range
            headers["Content-Length"] = str(length)
            headers["Content-Range"] = f"bytes {offset}-{offset + length - 1}/{size}"
            return StreamingResponse(
                manager.stream_file(target, offset=offset, length=length),
                status_code=206,
                media_type=mime,
                headers=headers,
            )
        headers["Content-Length"] = str(size)
        return StreamingResponse(
            manager.stream_file(target), media_type=mime, headers=headers
        )

    @router.get("/v1/native/results/{job_id}/manifest")
    def job_result_manifest(job_id: str) -> dict[str, Any]:
        try:
            return manager.result_manifest(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc
        except ParticipantError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "RESULT_NOT_PUBLISHED", "message": exc.detail},
            ) from exc

    @router.get("/v1/native/provenance/{job_id}")
    def job_provenance(job_id: str) -> dict[str, Any]:
        try:
            return {"job_id": job_id, "events": manager.provenance(job_id)}
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc

    return router, manager


def wait_for_state(
    manager: NativeJobManager,
    job_id: str,
    states: set[str],
    *,
    timeout_s: float = 600.0,
    poll_s: float = 0.2,
) -> dict[str, Any]:
    """Poll a job until it reaches one of the given states (test helper)."""

    deadline = time.monotonic() + timeout_s
    current = manager.status(job_id)
    while current["state"] not in states:
        if time.monotonic() > deadline:
            raise TimeoutError(f"job {job_id} stuck in {current['state']}")
        time.sleep(poll_s)
        current = manager.status(job_id)
    return current


__all__ = ["SubmitRequest", "build_native_router", "wait_for_state"]
