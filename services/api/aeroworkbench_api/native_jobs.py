"""Governed native scheduling routes: capabilities, submit, status, results."""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from participants.capabilities import probe_all
from participants.errors import ParticipantError
from participants.lifecycle import NativeJobManager
from participants.manifest import PARTICIPANT_MANIFESTS
from pydantic import BaseModel, ConfigDict, Field


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    design_id: str = Field(default="generic-design", min_length=1)
    deferred: bool = False


def _manager_for(root: Path) -> NativeJobManager:
    return NativeJobManager(root)


def build_native_router(job_root: Path | None = None) -> tuple[APIRouter, NativeJobManager]:
    root = job_root or Path(tempfile.mkdtemp(prefix="native-jobs-"))
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

    @router.get("/v1/native/analyses/{job_id}/events")
    def job_events(job_id: str) -> dict[str, Any]:
        try:
            return {"job_id": job_id, "events": manager.events(job_id)}
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc

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
        thread = threading.Thread(
            target=manager.run, args=(job_id,), name=f"native-{job_id[:8]}", daemon=True
        )
        thread.start()
        return {"job_id": job_id, "state": "QUEUED"}

    @router.post("/v1/native/analyses/{job_id}/cancel")
    def job_cancel(job_id: str) -> dict[str, Any]:
        try:
            state = manager.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
            ) from exc
        except ParticipantError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code.value, "message": exc.detail},
            ) from exc
        return {"job_id": job_id, "state": state}

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
            return {"job_id": job_id, "artifacts": manager.artifacts(job_id)}
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "JOB_NOT_FOUND"}
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
