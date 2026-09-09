from __future__ import annotations

import math

import pytest
from aeroworkbench_core.convergence import (
    ConvergenceCriteria,
    ConvergenceSnapshot,
    GlobalConvergenceManager,
)
from aeroworkbench_core.envelope import (
    AircraftDefinition,
    EnvelopeLimits,
    EnvelopePoint,
    evaluate_operating_envelope,
)
from aeroworkbench_core.models.edf import EDFInput
from aeroworkbench_core.models.gas_turbine import GasTurbineInput
from aeroworkbench_core.resonance import ResonanceDetector
from aeroworkbench_core.types import FidelityLevel, Quantity, ResultSource
from pydantic import ValidationError


def test_quantity_rejects_non_finite_values_before_hashing() -> None:
    with pytest.raises(ValidationError):
        Quantity(value=math.nan, unit="m")
    with pytest.raises(ValidationError):
        EDFInput(
            fan_diameter_m=math.inf,
            hub_diameter_m=0.025,
            shaft_power_w=1000.0,
            fan_efficiency=0.7,
            air_density_kg_m3=1.225,
            freestream_velocity_m_s=0.0,
            speed_rpm=45000.0,
            blade_count=12,
            stator_count=9,
        )


def test_envelope_result_carries_analytical_provenance_for_derived_thrust() -> None:
    result = evaluate_operating_envelope(
        AircraftDefinition(
            mass_kg=4.0,
            wing_area_m2=0.5,
            cd0=0.025,
            induced_drag_factor=0.055,
            available_thrust_n=45.0,
        ),
        EnvelopeLimits(max_current_a=80.0, max_temperature_k=360.0, max_load_factor=8.0),
        [
            EnvelopePoint(
                airspeed_m_s=35.0,
                density_kg_m3=1.225,
                load_factor=1.0,
                current_a=45.0,
                temperature_k=330.0,
            )
        ],
    )

    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.provenance.fidelity is FidelityLevel.ANALYTICAL
    assert len(result.provenance.inputs_hash) == 64


def test_convergence_fails_closed_when_required_measurements_are_missing() -> None:
    report = GlobalConvergenceManager(ConvergenceCriteria()).evaluate(ConvergenceSnapshot())

    assert report.converged is False
    assert report.categories["mass"].passed is False
    assert report.categories["numerical"].passed is False


def test_resonance_fails_closed_for_empty_excitation_or_mode_sets() -> None:
    with pytest.raises(ValueError, match="at least one excitation and mode"):
        ResonanceDetector().evaluate(
            excitations=[], modes=[], current_fidelity=FidelityLevel.ANALYTICAL
        )


def test_gas_turbine_rejects_infeasible_turbine_inlet_temperature() -> None:
    with pytest.raises(ValidationError, match="turbine inlet temperature"):
        GasTurbineInput(
            mass_flow_kg_s=1.0,
            ambient_temperature_k=288.15,
            ambient_pressure_pa=101325.0,
            compressor_pressure_ratio=4.0,
            compressor_efficiency=0.82,
            turbine_inlet_temperature_k=400.0,
            turbine_efficiency=0.86,
            combustor_efficiency=0.98,
            combustor_pressure_loss_fraction=0.04,
            cp_j_kg_k=1005.0,
            gamma=1.4,
            fuel_lower_heating_value_j_kg=43e6,
        )
