from __future__ import annotations

import time

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


def test_native_analysis_submit_fails_closed_without_capability() -> None:
    from participants.capabilities import probe_participant

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "incompressible-steady-flow",
                "inputs": {
                    "compressibility": "incompressible",
                    "steady": True,
                    "rotating_model": "none",
                    "thermal_model": "isothermal",
                    "turbulence": "kOmegaSST",
                    "inlet_velocity_m_s": 10.0,
                    "outlet_pressure_pa": 0.0,
                    "density_kg_m3": 1.225,
                    "viscosity_pa_s": 1.8e-5,
                },
            },
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        deadline = 60.0
        final = response.json()
        elapsed = 0.0
        while final["state"] not in {"COMPLETED", "FAILED", "CANCELLED"} and elapsed < deadline:
            time.sleep(0.2)
            elapsed += 0.2
            final = client.get(f"/v1/native/analyses/{job_id}").json()

    probe = probe_participant("incompressible-steady-flow")
    if probe.state != "ready":
        assert final["state"] == "FAILED"
        assert final["error_code"] == "CAPABILITY_UNAVAILABLE"
    else:
        assert final["state"] == "COMPLETED"


def test_job_progress_stream_comes_from_persisted_native_transitions() -> None:
    with TestClient(create_app()) as client:
        submitted = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "cell-spm-discharge",
                "inputs": {
                    "model": "spm",
                    "parameter_set": "Chen2020",
                    "discharge_current_a": 1.0,
                    "duration_s": 60.0,
                    "n_series": 1,
                    "n_parallel": 1,
                },
                "deferred": True,
            },
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]

        response = client.get(
            f"/v1/native/analyses/{job_id}/events", headers={"Accept": "text/event-stream"}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress" in response.text
    assert '"state":"QUEUED"' in response.text
    sequences = [
        int(line.split('"sequence":')[1].split(",")[0])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert sequences == sorted(sequences)


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
