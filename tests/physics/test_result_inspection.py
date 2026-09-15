"""Issue #6: result/artifact inspection and export over registered metadata only.

Backend coverage for the genuine delta: enriched artifact metadata for a
completed result, safe artifact retrieval by registered id (root containment
+ hash checks, no listings or arbitrary paths), and a small machine-readable
result manifest with immutable hashes and lineage. No solver is executed here;
completion is fabricated on the same on-disk ledger the API serves.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from participants.lifecycle import NativeJobManager

from aeroworkbench_api.main import create_app

_JOB_ROOT_ENV = "AEROWORKBENCH_JOB_ROOT"


def _spm_inputs() -> dict[str, object]:
    return {
        "model": "spm",
        "parameter_set": "Chen2020",
        "discharge_current_a": 1.0,
        "duration_s": 60.0,
        "n_series": 1,
        "n_parallel": 1,
    }


def _hex_for(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _submit_deferred(client: TestClient) -> str:
    response = client.post(
        "/v1/native/analyses",
        json={
            "participant_id": "cell-spm-discharge",
            "inputs": _spm_inputs(),
            "design_id": "bench-pack",
            "deferred": True,
        },
    )
    assert response.status_code == 202
    return str(response.json()["job_id"])


def _seed_case_files(manager: NativeJobManager, job_id: str) -> dict[str, bytes]:
    """Write registered case files; only manifest names become retrievable."""
    from pathlib import Path

    case_dir = Path(str(manager._job_root)) / f"case-{job_id[:12]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "case.json": json.dumps({"model": "spm"}, sort_keys=True).encode(),
        "result.json": json.dumps({"voltage_end_v": 3.7}, sort_keys=True).encode(),
        "solver.log": b"solver finished ok\n",
    }
    for name, payload in payloads.items():
        (case_dir / name).write_bytes(payload)
    return payloads


def _complete_job(
    manager: NativeJobManager, job_id: str, payloads: dict[str, bytes] | None = None
) -> dict[str, Any]:
    """Fabricate a COMPLETED record on the shared ledger (test seam only)."""
    status = manager.status(job_id)
    run_id = "run-" + job_id[:12]
    provenance_id = "prov-" + job_id[:12]
    result_id = _hex_for(job_id.encode())
    envelope = {
        "source": "native_solver",
        "fidelity": status["fidelity"],
        "units": {"voltage_end_v": "V"},
        "validity": {
            "participant_id": "cell-spm-discharge",
            "passed": True,
            "checks": {},
            "detail": "",
        },
        "input_hash": status["input_hash"] or _hex_for(b"inputs"),
        "solver_identity": "pybamm",
        "solver_version": "test-0.0",
        "run_id": run_id,
        "provenance_id": provenance_id,
        "warnings": [],
        "scalars": {"voltage_end_v": 3.7},
        "artifacts": [
            {"name": name, "sha256": _hex_for(payload), "bytes": len(payload)}
            for name, payload in (payloads or {}).items()
        ],
    }
    manager._ledger.update(
        job_id,
        state="COMPLETED",
        updated_at=datetime.now(UTC).isoformat(),
        envelope_json=json.dumps(envelope, sort_keys=True),
        run_id=run_id,
        result_id=result_id,
        provenance_id=provenance_id,
    )
    return {"run_id": run_id, "provenance_id": provenance_id, "result_id": result_id}


def _client_with_root(tmp_path: Any, monkeypatch: Any) -> TestClient:  # noqa: ANN001
    root = tmp_path / "jobs"
    monkeypatch.setenv(_JOB_ROOT_ENV, str(root))
    return TestClient(create_app())


# -- A. artifact metadata --------------------------------------------------------


def test_artifact_metadata_exposes_registered_artifacts_only(
    tmp_path: Any, monkeypatch: Any  # noqa: ANN001
) -> None:
    client = _client_with_root(tmp_path, monkeypatch)
    with client:
        job_id = _submit_deferred(client)
        manager = NativeJobManager(tmp_path / "jobs")
        try:
            payloads = _seed_case_files(manager, job_id)
            # An unregistered file on disk must never leak through metadata.
            (manager._job_root / f"case-{job_id[:12]}" / "secret.txt").write_bytes(b"nope")
            body = client.get(f"/v1/native/artifacts/{job_id}").json()
            entries = {entry["id"]: entry for entry in body["artifacts"]}
            assert {"case.json", "result.json", "solver.log"} <= set(entries)
            assert "secret.txt" not in entries
            assert "run_ross.py" not in entries
            result = entries["result.json"]
            assert result["sha256"] == _hex_for(payloads["result.json"])
            assert result["bytes"] == len(payloads["result.json"])
            assert result["mime"]
            assert result["category"]
            assert result["solver_id"] == "pybamm"
            assert result["download_url"].endswith(f"/v1/native/artifacts/{job_id}/result.json")
            assert result["display_name"] == "result.json"
        finally:
            manager.close()


def test_artifact_metadata_unknown_job_is_not_found(tmp_path: Any, monkeypatch: Any) -> None:  # noqa: ANN001
    client = _client_with_root(tmp_path, monkeypatch)
    with client:
        response = client.get("/v1/native/artifacts/does-not-exist")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"


# -- B. safe retrieval -----------------------------------------------------------


def test_artifact_download_serves_registered_bytes_with_content_type(
    tmp_path: Any, monkeypatch: Any  # noqa: ANN001
) -> None:
    client = _client_with_root(tmp_path, monkeypatch)
    with client:
        job_id = _submit_deferred(client)
        manager = NativeJobManager(tmp_path / "jobs")
        try:
            payloads = _seed_case_files(manager, job_id)
            response = client.get(f"/v1/native/artifacts/{job_id}/result.json")
            assert response.status_code == 200
            assert response.content == payloads["result.json"]
            assert response.headers["content-type"].startswith("application/json")
            logged = client.get(f"/v1/native/artifacts/{job_id}/solver.log")
            assert logged.status_code == 200
            assert logged.content == payloads["solver.log"]
        finally:
            manager.close()


def test_artifact_download_rejects_unregistered_and_traversal_ids(
    tmp_path: Any, monkeypatch: Any  # noqa: ANN001
) -> None:
    client = _client_with_root(tmp_path, monkeypatch)
    with client:
        job_id = _submit_deferred(client)
        manager = NativeJobManager(tmp_path / "jobs")
        try:
            _seed_case_files(manager, job_id)
            for artifact_id in ("secret.txt", "run_ross.py"):
                response = client.get(f"/v1/native/artifacts/{job_id}/{artifact_id}")
                assert response.status_code == 404, artifact_id
                assert response.json()["detail"]["code"] == "ARTIFACT_NOT_FOUND"
            # A dot id normalizes onto the metadata listing: metadata, never bytes.
            dotted = client.get(f"/v1/native/artifacts/{job_id}/.")
            assert dotted.status_code == 200
            assert "artifacts" in dotted.json()
            # Separator spellings never resolve to a registered artifact: they
            # either miss the single-segment route or land on a neighboring
            # route. All must stay 404 with no bytes served.
            for escaped_id in ("../sibling", "..%2Fsibling", "sub/dir"):
                escaped = client.get(f"/v1/native/artifacts/{job_id}/{escaped_id}")
                assert escaped.status_code == 404, escaped_id
                body = escaped.json()
                detail = body.get("detail") if isinstance(body, dict) else None
                if isinstance(detail, dict):
                    assert detail.get("code") in ("ARTIFACT_NOT_FOUND", "JOB_NOT_FOUND")
            # An empty artifact id resolves to the metadata listing, never bytes.
            listed = client.get(f"/v1/native/artifacts/{job_id}/")
            assert listed.status_code == 200
            assert "artifacts" in listed.json()
            assert client.get(f"/v1/native/artifacts/{job_id}").status_code == 200
        finally:
            manager.close()


def test_artifact_download_rejects_missing_and_hash_invalid_files(
    tmp_path: Any, monkeypatch: Any  # noqa: ANN001
) -> None:
    client = _client_with_root(tmp_path, monkeypatch)
    with client:
        job_id = _submit_deferred(client)
        manager = NativeJobManager(tmp_path / "jobs")
        try:
            payloads = _seed_case_files(manager, job_id)
            case_dir = manager._job_root / f"case-{job_id[:12]}"
            (case_dir / "result.json").unlink()
            missing = client.get(f"/v1/native/artifacts/{job_id}/result.json")
            assert missing.status_code == 404
            assert missing.json()["detail"]["code"] == "ARTIFACT_UNAVAILABLE"
            # Restore, publish the envelope baseline, then tamper: the
            # on-disk bytes no longer match the published digest.
            (case_dir / "result.json").write_bytes(payloads["result.json"])
            _complete_job(manager, job_id, payloads)
            published = client.get(f"/v1/native/artifacts/{job_id}/result.json")
            assert published.status_code == 200
            (case_dir / "result.json").write_bytes(payloads["result.json"] + b"tampered")
            tampered = client.get(f"/v1/native/artifacts/{job_id}/result.json")
            assert tampered.status_code == 409
            assert tampered.json()["detail"]["code"] == "ARTIFACT_HASH_MISMATCH"
        finally:
            manager.close()


# -- E. manifest export ----------------------------------------------------------


def test_manifest_export_carries_hashes_and_lineage(
    tmp_path: Any, monkeypatch: Any  # noqa: ANN001
) -> None:
    client = _client_with_root(tmp_path, monkeypatch)
    with client:
        job_id = _submit_deferred(client)
        manager = NativeJobManager(tmp_path / "jobs")
        try:
            # No manifest before a published envelope.
            early = client.get(f"/v1/native/results/{job_id}/manifest")
            assert early.status_code == 404
            assert early.json()["detail"]["code"] == "RESULT_NOT_PUBLISHED"
            payloads = _seed_case_files(manager, job_id)
            sealed = _complete_job(manager, job_id)
            manifest = client.get(f"/v1/native/results/{job_id}/manifest").json()
            assert manifest["job_id"] == job_id
            assert manifest["design_id"] == "bench-pack"
            assert manifest["run_id"] == sealed["run_id"]
            assert manifest["result_id"] == sealed["result_id"]
            assert manifest["provenance_id"] == sealed["provenance_id"]
            assert manifest["source"] == "native_solver"
            assert manifest["fidelity"]
            assert manifest["solver_identity"] == "pybamm"
            assert manifest["validity"]["passed"] is True
            assert manifest["input_hash"]
            names = {entry["name"]: entry for entry in manifest["artifacts"]}
            assert names["result.json"]["sha256"] == _hex_for(payloads["result.json"])
            assert names["result.json"]["bytes"] == len(payloads["result.json"])
            # Manifest stays small: hashes and lineage only, no bundled outputs.
            assert "scalars" not in manifest
            assert "outputs" not in manifest
        finally:
            manager.close()
