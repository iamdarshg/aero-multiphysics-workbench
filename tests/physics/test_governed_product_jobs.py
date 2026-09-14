"""Issue #2: product wrap over the real governed native-job lifecycle.

Backend-only coverage for the genuine delta: exact durable job states with
illegal-transition rejection, submission validation without demo shortcuts,
real persisted event streams, stable failure codes, restart behavior, and
completed payloads carrying result/provenance ids. Analytical demos stay
separate and explicitly labelled.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from participants.errors import NativeErrorCode, ParticipantError
from participants.lifecycle import JobState, NativeJobManager
from participants.receipts import ValidityReport

from aeroworkbench_api.main import create_app

TERMINAL = {JobState.COMPLETED.value, JobState.FAILED.value, JobState.CANCELLED.value}


def _rotor_inputs() -> dict[str, object]:
    return {
        "analysis": "campbell",
        "shaft_length_m": 1.5,
        "shaft_diameter_m": 0.05,
        "n_elements": 4,
        "bearing_stiffness_n_m": 1e8,
        "bearing_damping_n_s_m": 1000.0,
        "max_speed_rpm": 12000.0,
    }


def _spm_inputs() -> dict[str, object]:
    return {
        "model": "spm",
        "parameter_set": "Chen2020",
        "discharge_current_a": 1.0,
        "duration_s": 60.0,
        "n_series": 1,
        "n_parallel": 1,
    }


def _openfoam_inputs() -> dict[str, object]:
    return {
        "compressibility": "incompressible",
        "steady": True,
        "rotating_model": "none",
        "thermal_model": "isothermal",
        "turbulence": "kOmegaSST",
        "inlet_velocity_m_s": 10.0,
        "outlet_pressure_pa": 0.0,
        "density_kg_m3": 1.225,
        "viscosity_pa_s": 1.8e-5,
    }


def _states(manager: NativeJobManager, job_id: str) -> list[str]:
    return [event["state"] for event in manager.events(job_id)]


def _wait_api(client: TestClient, job_id: str, timeout_s: float = 600.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    current: dict[str, Any] = client.get(f"/v1/native/analyses/{job_id}").json()
    while current["state"] not in TERMINAL:
        assert time.monotonic() < deadline, f"job stuck in {current['state']}"
        time.sleep(0.5)
        current = client.get(f"/v1/native/analyses/{job_id}").json()
    return current


def _submit_deferred(
    client: TestClient, participant_id: str, inputs: dict[str, object]
) -> str:
    response = client.post(
        "/v1/native/analyses",
        json={"participant_id": participant_id, "inputs": inputs, "deferred": True},
    )
    assert response.status_code == 202
    return str(response.json()["job_id"])


def _needs_ready(participant_id: str) -> None:
    from participants.capabilities import probe_participant

    if probe_participant(participant_id).state != "ready":
        pytest.skip(f"{participant_id} capability is not ready")


def _needs_unavailable(participant_id: str) -> None:
    from participants.capabilities import probe_participant

    if probe_participant(participant_id).state == "ready":
        pytest.skip(f"{participant_id} capability is ready; failure path not exercised")


# -- A. exact durable states ----------------------------------------------------


def test_illegal_state_transitions_are_rejected(tmp_path: Any) -> None:  # noqa: ANN001
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("cell-spm-discharge", _spm_inputs(), deferred=True)
    with pytest.raises(ValueError, match="ILLEGAL_JOB_TRANSITION"):
        manager._transition(job_id, JobState.COMPLETED, "skip the pipeline")
    with pytest.raises(ValueError, match="ILLEGAL_JOB_TRANSITION"):
        manager._transition(job_id, JobState.RUNNING, "skip admission")
    assert manager.cancel(job_id) == JobState.CANCELLED.value
    with pytest.raises(ValueError, match="ILLEGAL_JOB_TRANSITION"):
        manager._transition(job_id, JobState.RUNNING, "resurrect terminal job")
    manager.close()


def test_bounded_native_run_follows_the_legal_state_sequence(tmp_path: Any) -> None:  # noqa: ANN001
    _needs_ready("rotor-campbell")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("rotor-campbell", _rotor_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value
    assert _states(manager, job_id) == [
        JobState.QUEUED.value,
        JobState.PREPARING.value,
        JobState.RUNNING.value,
        JobState.PARSING.value,
        JobState.VALIDATING.value,
        JobState.COMPLETED.value,
    ]
    manager.close()


def test_unavailable_capability_fails_without_inventing_states(tmp_path: Any) -> None:  # noqa: ANN001
    _needs_unavailable("incompressible-steady-flow")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("incompressible-steady-flow", _openfoam_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.FAILED.value
    assert _states(manager, job_id) == [
        JobState.QUEUED.value,
        JobState.PREPARING.value,
        JobState.FAILED.value,
    ]
    assert manager.status(job_id)["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
    manager.close()


def test_completed_status_carries_result_and_provenance_ids(tmp_path: Any) -> None:  # noqa: ANN001
    _needs_ready("rotor-campbell")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "rotor-campbell",
        _rotor_inputs(),
        design_id="bench-rotor",
        owner_id="tests",
        revision_id="rev-1",
        analysis="campbell",
        fidelity="beam-campbell",
        deferred=True,
    )
    assert manager.run(job_id) == JobState.COMPLETED.value
    status = manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert status["owner_id"] == "tests"
    assert status["design_id"] == "bench-rotor"
    assert status["revision_id"] == "rev-1"
    assert status["analysis"] == "campbell"
    assert status["fidelity"] == "beam-campbell"
    assert status["run_id"] == envelope["run_id"]
    assert status["provenance_id"] == envelope["provenance_id"]
    result_id = status["result_id"]
    assert isinstance(result_id, str) and len(result_id) == 64
    assert all(character in "0123456789abcdef" for character in result_id)
    manager.close()


# -- B. submission path ----------------------------------------------------------


def test_submit_validates_fidelity_against_the_manifest(tmp_path: Any) -> None:  # noqa: ANN001
    manager = NativeJobManager(tmp_path / "jobs")
    with pytest.raises(ValueError, match="INVALID_JOB_INPUTS"):
        manager.submit(
            "rotor-campbell", _rotor_inputs(), fidelity="bogus-level", deferred=True
        )
    job_id = manager.submit(
        "rotor-campbell", _rotor_inputs(), fidelity="beam-campbell", deferred=True
    )
    assert manager.status(job_id)["fidelity"] == "beam-campbell"
    manager.close()


def test_admission_rejects_infeasible_memory_reservation(tmp_path: Any) -> None:  # noqa: ANN001
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "rotor-campbell", _rotor_inputs(), requested_memory_mib=1_000_000.0, deferred=True
    )
    assert manager.run(job_id) == JobState.FAILED.value
    status = manager.status(job_id)
    assert status["error_code"] == NativeErrorCode.ADMISSION_REJECTED.value
    assert _states(manager, job_id) == [
        JobState.QUEUED.value,
        JobState.PREPARING.value,
        JobState.FAILED.value,
    ]
    manager.close()


# -- E. failure mapping ------------------------------------------------------------


def test_quality_gate_failure_maps_to_a_stable_code(  # noqa: D103
    tmp_path: Any,  # noqa: ANN001
    monkeypatch: Any,  # noqa: ANN001
) -> None:
    _needs_ready("rotor-campbell")

    def _always_fail(scalars: dict[str, float], inputs: dict[str, object]) -> ValidityReport:
        return ValidityReport(
            participant_id="rotor-campbell", passed=False, checks={}, detail="injected failure"
        )

    monkeypatch.setattr("ross.rotor.validate_rotor_result", _always_fail)
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("rotor-campbell", _rotor_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.FAILED.value
    status = manager.status(job_id)
    assert status["error_code"] == NativeErrorCode.QUALITY_GATE_FAILED.value
    assert _states(manager, job_id)[-1] == JobState.FAILED.value
    with pytest.raises(ParticipantError):
        manager.envelope(job_id)
    manager.close()


def test_parser_failure_maps_to_a_stable_code(  # noqa: D103
    tmp_path: Any,  # noqa: ANN001
    monkeypatch: Any,  # noqa: ANN001
) -> None:
    _needs_ready("rotor-campbell")

    def _boom(case_dir: Any) -> Any:  # noqa: ANN001, ANN202
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "injected parser failure")

    monkeypatch.setattr("ross.rotor.parse_rotor_result", _boom)
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("rotor-campbell", _rotor_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.FAILED.value
    assert manager.status(job_id)["error_code"] == NativeErrorCode.PARSER_FAILED.value
    manager.close()


# -- F. restart behavior --------------------------------------------------------------


def test_restart_preserves_terminal_jobs_and_interrupts_inflight(tmp_path: Any) -> None:  # noqa: ANN001
    root = tmp_path / "jobs"
    manager = NativeJobManager(root)
    settled = manager.submit("cell-spm-discharge", _spm_inputs(), deferred=True)
    assert manager.cancel(settled) == JobState.CANCELLED.value
    queued = manager.submit("cell-spm-discharge", _spm_inputs(), deferred=True)
    # Simulate a worker that died mid-run: the ledger says RUNNING but no
    # worker will ever report back.
    doomed = manager.submit("cell-spm-discharge", _spm_inputs(), deferred=True)
    manager._ledger.update(
        doomed, state=JobState.RUNNING.value, updated_at=datetime.now(UTC).isoformat()
    )
    manager.close()

    revived = NativeJobManager(root)
    try:
        assert revived.status(settled)["state"] == JobState.CANCELLED.value
        assert _states(revived, settled) == [
            JobState.QUEUED.value,
            JobState.CANCELLED.value,
        ]
        assert revived.status(queued)["state"] == JobState.QUEUED.value
        doomed_status = revived.status(doomed)
        assert doomed_status["state"] == JobState.FAILED.value
        assert doomed_status["error_code"] == NativeErrorCode.INTERRUPTED.value
        assert doomed_status["error_detail"]
        doomed_events = _states(revived, doomed)
        assert doomed_events[0] == JobState.QUEUED.value
        assert doomed_events[-1] == JobState.FAILED.value
        # A job that never started is still usable after restart.
        assert revived.cancel(queued) == JobState.CANCELLED.value
    finally:
        revived.close()


# -- C/D. API surface over the real lifecycle ----------------------------------------------


def test_product_submit_observe_retrieve_bounded_benchmark() -> None:
    _needs_ready("rotor-campbell")
    with TestClient(create_app()) as client:
        submitted = client.post(
            "/v1/native/analyses",
            json={"participant_id": "rotor-campbell", "inputs": _rotor_inputs()},
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]
        final = _wait_api(client, job_id)
        assert final["state"] == JobState.COMPLETED.value
        assert final["result_id"]
        assert final["provenance_id"]
        assert final["run_id"]

        envelope = client.get(f"/v1/native/results/{job_id}").json()
        assert envelope["source"] == "native_solver"
        assert envelope["run_id"] == final["run_id"]
        assert envelope["provenance_id"] == final["provenance_id"]

        provenance = client.get(f"/v1/native/provenance/{job_id}").json()
        assert [event["event_type"] for event in provenance["events"]] == [
            "native.launch-accepted",
            "native.result-recorded",
        ]


def test_capability_unavailable_fails_honestly_via_api() -> None:
    _needs_unavailable("incompressible-steady-flow")
    with TestClient(create_app()) as client:
        submitted = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "incompressible-steady-flow",
                "inputs": _openfoam_inputs(),
                "deferred": True,
            },
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]
        assert client.post(f"/v1/native/analyses/{job_id}/start").status_code == 202
        final = _wait_api(client, job_id, timeout_s=120.0)
        assert final["state"] == JobState.FAILED.value
        assert final["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
        result = client.get(f"/v1/native/results/{job_id}")
        assert result.status_code == 404
        assert result.json()["detail"]["code"] == "RESULT_NOT_PUBLISHED"


def test_event_stream_comes_from_persisted_transitions() -> None:
    with TestClient(create_app()) as client:
        job_id = _submit_deferred(client, "cell-spm-discharge", _spm_inputs())

        def _fetch() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            as_json = client.get(f"/v1/native/analyses/{job_id}/events").json()["events"]
            sse = client.get(
                f"/v1/native/analyses/{job_id}/events",
                headers={"Accept": "text/event-stream"},
            )
            assert sse.status_code == 200
            assert sse.headers["content-type"].startswith("text/event-stream")
            parsed = [
                json.loads(line[len("data: "):])
                for line in sse.text.splitlines()
                if line.startswith("data: ")
            ]
            return as_json, parsed

        before_json, before_sse = _fetch()
        assert [event["state"] for event in before_sse] == [
            event["state"] for event in before_json
        ]
        sequences = [event["sequence"] for event in before_sse]
        assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
        assert all({"sequence", "state", "at"} <= set(event) for event in before_sse)

        assert client.post(f"/v1/native/analyses/{job_id}/cancel").json()["state"] == (
            "CANCELLED"
        )
        after_json, after_sse = _fetch()
        assert len(after_sse) == len(after_json) == len(before_sse) + 1
        assert after_sse[-1]["state"] == "CANCELLED"
        sequences = [event["sequence"] for event in after_sse]
        assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)


def test_cancel_terminal_job_conflicts_and_delete_alias_works() -> None:
    with TestClient(create_app()) as client:
        first_id = _submit_deferred(client, "cell-spm-discharge", _spm_inputs())
        cancelled = client.post(f"/v1/native/analyses/{first_id}/cancel")
        assert cancelled.json()["state"] == "CANCELLED"
        repeated = client.post(f"/v1/native/analyses/{first_id}/cancel")
        assert repeated.status_code == 409
        assert repeated.json()["detail"]["code"] == "CANCELLED"
        via_delete = client.delete(f"/v1/native/analyses/{first_id}/cancel")
        assert via_delete.status_code == 409

        second_id = _submit_deferred(client, "cell-spm-discharge", _spm_inputs())
        deleted = client.delete(f"/v1/native/analyses/{second_id}/cancel")
        assert deleted.status_code == 200
        assert deleted.json()["state"] == "CANCELLED"


def test_submit_rejects_unlisted_fidelity_and_shell_shaped_fields() -> None:
    with TestClient(create_app()) as client:
        bad_fidelity = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "rotor-campbell",
                "inputs": _rotor_inputs(),
                "fidelity": "bogus-level",
                "deferred": True,
            },
        )
        assert bad_fidelity.status_code == 422
        assert bad_fidelity.json()["detail"]["code"] == "INVALID_JOB_INPUTS"

        shell_shaped = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "rotor-campbell",
                "inputs": _rotor_inputs(),
                "executable": "rm",
                "deferred": True,
            },
        )
        assert shell_shaped.status_code == 422


def test_fake_demo_job_routes_are_gone_and_analytical_demos_stay_labelled() -> None:
    with TestClient(create_app()) as client:
        assert client.post("/v1/jobs/edf", json={}).status_code == 404
        assert client.get("/v1/jobs/does-not-exist/events").status_code == 404
        for route in ("/v1/demos/edf", "/v1/demos/aircraft", "/v1/demos/gas-turbine"):
            response = client.post(route, json={})
            assert response.status_code == 200
            body = response.json()
            assert body["result_type"] == "analytical"
            assert body["native_solver_executed"] is False
