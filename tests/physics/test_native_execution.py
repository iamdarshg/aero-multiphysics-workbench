"""Milestone 2: real bounded native benchmarks through the public scheduling path.

ROSS, PyBaMM, and Gmsh execute locally with small cases. Heavy binaries that
are genuinely absent fail closed with explicit codes. The acceptance test
submits fluid + structural + lightweight participants through the SAME public
API path without touching adapter internals.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from participants.capabilities import probe_participant
from participants.errors import NativeErrorCode
from participants.lifecycle import JobState, NativeJobManager
from participants.manifest import get_participant
from ross.rotor import beam_first_critical_rpm

from aeroworkbench_api.main import create_app

TERMINAL = {
    JobState.COMPLETED.value,
    JobState.FAILED.value,
    JobState.CANCELLED.value,
}

MESH_DIMS = {
    "length_mm": 48.0,
    "inner_diameter_mm": 54.0,
    "outer_diameter_mm": 60.0,
    "zone_length_mm": 10.0,
    "zone_gap_mm": 6.0,
}


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
        "n_series": 2,
        "n_parallel": 3,
    }


def _wait(manager: NativeJobManager, job_id: str, timeout_s: float = 600.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    current = manager.status(job_id)
    while current["state"] not in TERMINAL:
        assert time.monotonic() < deadline, f"job stuck in {current['state']}"
        time.sleep(0.5)
        current = manager.status(job_id)
    return current


def _wait_api(client: TestClient, job_id: str, timeout_s: float = 600.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    current = client.get(f"/v1/native/analyses/{job_id}").json()
    while current["state"] not in TERMINAL:
        assert time.monotonic() < deadline, f"job stuck in {current['state']}"
        time.sleep(0.5)
        current = client.get(f"/v1/native/analyses/{job_id}").json()
    return current


# -- F. canonical physics benchmarks (actually executed) -----------------------


def test_ross_campbell_benchmark_runs_natively(tmp_path) -> None:  # noqa: ANN001
    if probe_participant("rotor-campbell").state != "ready":
        pytest.skip("ROSS is not installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("rotor-campbell", _rotor_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["fidelity"] == "beam-campbell"
    assert envelope["solver_identity"] == "ross"
    assert "rotordynamics" in envelope["solver_version"] or envelope["solver_version"]
    first = envelope["scalars"]["first_critical_rpm"]
    estimate = beam_first_critical_rpm(shaft_length_m=1.5, shaft_diameter_m=0.05)
    assert first == pytest.approx(estimate, rel=0.10)
    assert envelope["validity"]["passed"] is True
    assert any("NUMBA_DISABLE_JIT" in warning for warning in envelope["warnings"])
    artifacts = {entry["name"]: entry for entry in manager.artifacts(job_id)}
    assert set(("case.json", "run_ross.py", "result.json", "solver.log")) <= set(artifacts)
    assert len(artifacts["result.json"]["sha256"]) == 64


def test_pybamm_spm_benchmark_runs_natively(tmp_path) -> None:  # noqa: ANN001
    if probe_participant("cell-spm-discharge").state != "ready":
        pytest.skip("PyBaMM is not installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("cell-spm-discharge", _spm_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["solver_identity"] == "pybamm"
    assert envelope["units"]["delivered_ah"] == "A.h"
    assert envelope["scalars"]["voltage_end_v"] < envelope["scalars"]["voltage_start_v"]
    assert envelope["scalars"]["delivered_ah"] == pytest.approx(0.05, rel=0.05)
    assert envelope["validity"]["passed"] is True
    assert len(manager.provenance(job_id)) == 2  # launch-accepted + result-recorded


def test_gmsh_mesh_benchmark_runs_natively(tmp_path) -> None:  # noqa: ANN001
    if probe_participant("domain-mesh").state != "ready":
        pytest.skip("gmsh is not installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "domain-mesh", {"base_size_mm": 10.0, "n_rotating": 1, **MESH_DIMS}, deferred=True
    )
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["scalars"]["element_count"] > 0
    assert envelope["validity"]["passed"] is True


def test_cad_interchange_benchmark_runs_natively(tmp_path) -> None:  # noqa: ANN001
    if probe_participant("cad-interchange").state != "ready":
        pytest.skip("no CAD converter is installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "cad-interchange",
        {"n_rotating": 1, "source_format": "step", **MESH_DIMS},
        deferred=True,
    )
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["scalars"]["faces_before"] == envelope["scalars"]["faces_after"]


# -- E. API integration ----------------------------------------------------------


def test_api_capability_report_and_participant_catalog() -> None:
    with TestClient(create_app()) as client:
        capabilities = client.get("/v1/native/capabilities")
        catalog = client.get("/v1/native/participants")
    assert capabilities.status_code == 200
    ready = {entry["participant_id"] for entry in capabilities.json()["ready"]}
    assert "rotor-campbell" in ready
    assert "cell-spm-discharge" in ready
    assert "domain-mesh" in ready
    assert catalog.status_code == 200
    assert catalog.json()["manifest_version"] == "2"
    assert len(catalog.json()["participants"]) == len(
        {entry["participant_id"] for entry in catalog.json()["participants"]}
    )


def test_api_rejects_unknown_participant_without_running_anything() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/native/analyses", json={"participant_id": "rm -rf", "inputs": {}}
        )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "UNKNOWN_PARTICIPANT"


def test_api_deferred_submit_cancel_result_provenance_cycle() -> None:
    with TestClient(create_app()) as client:
        submitted = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "cell-spm-discharge",
                "inputs": _spm_inputs(),
                "deferred": True,
            },
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]
        assert submitted.json()["state"] == "QUEUED"

        events = client.get(f"/v1/native/analyses/{job_id}/events").json()["events"]
        assert [event["state"] for event in events] == ["QUEUED"]

        cancelled = client.post(f"/v1/native/analyses/{job_id}/cancel")
        assert cancelled.json()["state"] == "CANCELLED"

        restarted = client.post(f"/v1/native/analyses/{job_id}/start")
        assert restarted.status_code == 409
        assert restarted.json()["detail"]["code"] == "JOB_ALREADY_STARTED"

        result = client.get(f"/v1/native/results/{job_id}")
        assert result.status_code == 404
        assert result.json()["detail"]["code"] == "RESULT_NOT_PUBLISHED"

        gated = client.post(
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
                "deferred": True,
            },
        ).json()
        assert client.post(f"/v1/native/analyses/{gated['job_id']}/start").status_code == 202
        final = _wait_api(client, gated["job_id"], timeout_s=120.0)
        if probe_participant("incompressible-steady-flow").state != "ready":
            assert final["error_code"] == "CAPABILITY_UNAVAILABLE"
        else:
            assert final["state"] == "COMPLETED"

        missing = client.get("/v1/native/analyses/" + "0" * 32)
        assert missing.status_code == 404


# -- H. acceptance: one path for fluid, structural, lightweight ------------------


def test_acceptance_fluid_structural_lightweight_share_one_public_path() -> None:
    fluid_probe = probe_participant("incompressible-steady-flow")
    structural_probe = probe_participant("structural-modal")
    with TestClient(create_app()) as client:
        fluid = client.post(
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
        ).json()
        structural = client.post(
            "/v1/native/analyses",
            json={
                "participant_id": "structural-modal",
                "inputs": {
                    "analysis": "modal",
                    "prestress": False,
                    "thermal_load": False,
                    "contact": False,
                    "youngs_modulus_pa": 2.1e11,
                    "poisson_ratio": 0.3,
                    "density_kg_m3": 7800.0,
                    "n_modes": 4,
                    "mesh_file": "mesh.med",
                },
            },
        ).json()
        lightweight = client.post(
            "/v1/native/analyses",
            json={"participant_id": "cell-spm-discharge", "inputs": _spm_inputs()},
        ).json()

        fluid_final = _wait_api(client, fluid["job_id"])
        structural_final = _wait_api(client, structural["job_id"])
        light_final = _wait_api(client, lightweight["job_id"])

        if fluid_probe.state != "ready":
            assert fluid_final["state"] == "FAILED"
            assert fluid_final["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
        else:
            assert fluid_final["state"] == "COMPLETED"
        if structural_probe.state != "ready":
            assert structural_final["state"] == "FAILED"
            assert structural_final["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
        else:
            assert structural_final["state"] == "COMPLETED"

        assert light_final["state"] == "COMPLETED"
        envelope = client.get(f"/v1/native/results/{lightweight['job_id']}").json()
        assert envelope["source"] == "native_solver"
        assert envelope["run_id"] == light_final["run_id"]
        artifacts = client.get(f"/v1/native/artifacts/{lightweight['job_id']}").json()
        assert {entry["name"] for entry in artifacts["artifacts"]} >= {"result.json", "solver.log"}
        provenance = client.get(f"/v1/native/provenance/{lightweight['job_id']}").json()
        assert [event["event_type"] for event in provenance["events"]] == [
            "native.launch-accepted",
            "native.result-recorded",
        ]
        # Failure paths never masquerade as analytical results.
        for final in (fluid_final, structural_final):
            if final["state"] == "FAILED":
                assert final["error_code"] != "analytical"
    assert get_participant("incompressible-steady-flow").executable.solver_id == "openfoam"
    assert get_participant("structural-modal").executable.solver_id == "code-aster"
