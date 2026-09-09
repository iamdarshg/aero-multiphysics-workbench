from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from aeroworkbench_core.coupling import CouplingPolicy
from aeroworkbench_core.envelope import (
    AircraftDefinition,
    EnvelopeLimits,
    EnvelopePoint,
    evaluate_operating_envelope,
)
from aeroworkbench_core.models.common import analytical_provenance
from aeroworkbench_core.models.edf import EDFInput, evaluate_edf
from aeroworkbench_core.models.gas_turbine import GasTurbineInput, evaluate_gas_turbine
from aeroworkbench_core.resonance import Excitation, Mode, ResonanceDetector
from aeroworkbench_core.types import FidelityLevel, ResultSource
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

ANALYTICAL_MODELS = [
    "aircraft",
    "battery",
    "edf",
    "esc",
    "gas_turbine",
    "motor",
    "shaft",
    "thermal",
]


def _edf_demo() -> dict[str, Any]:
    inputs = EDFInput(
        fan_diameter_m=0.070,
        hub_diameter_m=0.025,
        shaft_power_w=1000,
        fan_efficiency=0.70,
        air_density_kg_m3=1.225,
        freestream_velocity_m_s=0,
        speed_rpm=45_000,
        blade_count=12,
        stator_count=9,
    )
    result = evaluate_edf(inputs)
    balance: dict[str, Any] = {
        "shaft_power_w": inputs.shaft_power_w,
        "fluid_power_w": result.fluid_power_w,
        "loss_power_w": inputs.shaft_power_w - result.fluid_power_w,
    }
    balance["closure_fraction"] = (
        abs(balance["shaft_power_w"] - balance["fluid_power_w"] - balance["loss_power_w"])
        / balance["shaft_power_w"]
    )
    balance["provenance"] = analytical_provenance(
        "edf-power-balance",
        {"edf_inputs": inputs.model_dump(), "edf_result": result.model_dump(mode="json")},
        "loss power is shaft power minus ideal actuator-disk fluid power",
    ).model_dump(mode="json")
    resonance = ResonanceDetector().evaluate(
        excitations=[
            Excitation(name="blade passing", frequency_hz=result.blade_passing_frequency_hz)
        ],
        modes=[Mode(name="blade bending 1", frequency_hz=9045, damping_ratio=0.012)],
        current_fidelity=FidelityLevel.MRF,
    )
    return {
        "result_type": ResultSource.ANALYTICAL,
        "edf": result.model_dump(mode="json"),
        "power_balance": balance,
        "resonance": resonance.model_dump(mode="json"),
        "native_solver_executed": False,
    }


def _aircraft_demo() -> dict[str, Any]:
    aircraft = AircraftDefinition(
        mass_kg=4, wing_area_m2=0.5, cd0=0.025, induced_drag_factor=0.055, available_thrust_n=45
    )
    limits = EnvelopeLimits(max_current_a=80, max_temperature_k=360, max_load_factor=8)
    points = [
        EnvelopePoint(
            airspeed_m_s=35, density_kg_m3=1.225, load_factor=1, current_a=45, temperature_k=330
        ),
        EnvelopePoint(
            airspeed_m_s=24, density_kg_m3=1.225, load_factor=5, current_a=75, temperature_k=355
        ),
        EnvelopePoint(
            airspeed_m_s=20, density_kg_m3=1.225, load_factor=9, current_a=90, temperature_k=370
        ),
    ]
    return {
        "result_type": ResultSource.ANALYTICAL,
        "envelope": evaluate_operating_envelope(aircraft, limits, points).model_dump(mode="json"),
        "native_solver_executed": False,
    }


def _gas_turbine_demo() -> dict[str, Any]:
    result = evaluate_gas_turbine(
        GasTurbineInput(
            mass_flow_kg_s=1,
            ambient_temperature_k=288.15,
            ambient_pressure_pa=101325,
            compressor_pressure_ratio=4,
            compressor_efficiency=0.82,
            turbine_inlet_temperature_k=1200,
            turbine_efficiency=0.86,
            combustor_efficiency=0.98,
            combustor_pressure_loss_fraction=0.04,
            cp_j_kg_k=1005,
            gamma=1.4,
            fuel_lower_heating_value_j_kg=43e6,
        )
    )
    return {
        "result_type": ResultSource.ANALYTICAL,
        "cycle": result.model_dump(mode="json"),
        "native_solver_executed": False,
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Aero Multiphysics Workbench API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    jobs: dict[str, list[dict[str, Any]]] = {}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ready", "analytical_models": ANALYTICAL_MODELS, "native_solvers": {}}

    @app.get("/api/v1/workbench/state")
    def workbench_state() -> dict[str, Any]:
        return {
            "default_coupling_strength": CouplingPolicy.from_strength(0.9).strength,
            "available_result_sources": [source.value for source in ResultSource],
        }

    @app.post("/v1/demos/edf")
    @app.post("/api/v1/demos/edf/run")
    def edf_demo() -> dict[str, Any]:
        return _edf_demo()

    @app.post("/v1/demos/aircraft")
    def aircraft_demo() -> dict[str, Any]:
        return _aircraft_demo()

    @app.post("/v1/demos/gas-turbine")
    def gas_turbine_demo() -> dict[str, Any]:
        return _gas_turbine_demo()

    @app.post("/v1/native/{solver}/execute")
    def execute_native(solver: str) -> None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "NATIVE_SOLVER_UNAVAILABLE",
                "solver": solver,
                "message": "No verified native solver capability is configured.",
            },
        )

    @app.post("/v1/jobs/edf", status_code=status.HTTP_202_ACCEPTED)
    def start_edf_job() -> dict[str, str]:
        job_id = str(uuid4())
        jobs[job_id] = [
            {"sequence": 0, "status": "queued", "progress": 0},
            {"sequence": 1, "status": "running", "progress": 50},
            {"sequence": 2, "status": "completed", "progress": 100, "result": _edf_demo()},
        ]
        return {"job_id": job_id, "status": "completed"}

    @app.get("/v1/jobs/{job_id}/events")
    def job_events(job_id: str) -> Response:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"})
        body = "".join(
            f"event: progress\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
            for event in jobs[job_id]
        )
        return Response(content=body, media_type="text/event-stream")

    return app


app = create_app()
