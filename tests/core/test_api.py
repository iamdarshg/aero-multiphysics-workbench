from __future__ import annotations

from fastapi.testclient import TestClient

from aeroworkbench_api.main import create_app


def test_health_exposes_analytical_capabilities_without_claiming_native_solvers() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["analytical_models"] == [
        "aircraft",
        "battery",
        "edf",
        "esc",
        "gas_turbine",
        "motor",
        "shaft",
        "thermal",
    ]
    assert body["native_solvers"] == {}


def test_edf_demonstrator_is_typed_conservation_checked_and_resonance_aware() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/demos/edf", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["result_type"] == "analytical"
    assert body["power_balance"]["closure_fraction"] < 1e-9
    assert body["edf"]["provenance"]["source"] == "analytical"
    assert body["resonance"]["escalation_required"] is True
    assert body["resonance"]["required_fidelity"] == "harmonic_response"


def test_aircraft_demonstrator_returns_operating_envelope_regions() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/demos/aircraft", json={})

    assert response.status_code == 200
    statuses = {point["status"] for point in response.json()["envelope"]["points"]}
    assert statuses == {"viable", "constrained", "failed"}
    assert response.json()["result_type"] == "analytical"


def test_gas_turbine_demonstrator_does_not_mislabel_cycle_as_pycycle() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/demos/gas-turbine", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["result_type"] == "analytical"
    assert body["cycle"]["provenance"]["model"] == "ideal-brayton-cycle"
    assert body["native_solver_executed"] is False
    assert "not pyCycle" in body["cycle"]["limitations"][0]


def test_native_solver_execution_fails_closed_when_capability_is_unavailable() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/native/openfoam/execute", json={})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "NATIVE_SOLVER_UNAVAILABLE"
    assert response.json()["detail"]["solver"] == "openfoam"


def test_job_progress_stream_emits_ordered_sse_events() -> None:
    with TestClient(create_app()) as client:
        started = client.post("/v1/jobs/edf", json={})
        assert started.status_code == 202
        job_id = started.json()["job_id"]

        response = client.get(f"/v1/jobs/{job_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress" in response.text
    assert '"status":"completed"' in response.text
    assert response.text.index('"status":"queued"') < response.text.index('"status":"completed"')


def test_frontend_contract_exposes_state_and_run_routes_with_local_cors() -> None:
    with TestClient(create_app()) as client:
        state = client.get("/api/v1/workbench/state")
        run = client.post("/api/v1/demos/edf/run", json={})
        preflight = client.options(
            "/api/v1/demos/edf/run",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert state.status_code == 200
    assert state.json()["default_coupling_strength"] == 0.9
    assert state.json()["available_result_sources"] == [
        "analytical",
        "benchmark",
        "native_solver",
        "surrogate",
    ]
    assert run.status_code == 200
    assert run.json()["edf"]["provenance"]["fidelity"] == "analytical"
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
