from __future__ import annotations

import math

import pytest
from aeroworkbench_core.models.battery import SixSBatteryInput, evaluate_six_s_battery
from aeroworkbench_core.models.edf import EDFInput, evaluate_edf
from aeroworkbench_core.models.esc import ESCInput, evaluate_esc
from aeroworkbench_core.models.gas_turbine import GasTurbineInput, evaluate_gas_turbine
from aeroworkbench_core.models.motor import MotorInput, evaluate_motor
from aeroworkbench_core.models.shaft import ShaftInput, evaluate_shaft
from aeroworkbench_core.models.thermal import ThermalInput, evaluate_thermal
from aeroworkbench_core.types import FidelityLevel, ResultSource
from pydantic import ValidationError


def test_motor_benchmark_closes_power_and_respects_kv_kt_identity() -> None:
    result = evaluate_motor(
        MotorInput(
            kv_rpm_per_v=1000.0,
            resistance_ohm=0.030,
            no_load_current_a=1.2,
            speed_rpm=18_000.0,
            torque_nm=0.30,
        )
    )

    expected_kt = 60.0 / (2.0 * math.pi * 1000.0)
    assert result.kt_nm_per_a == pytest.approx(expected_kt)
    assert result.current_a == pytest.approx(0.30 / expected_kt + 1.2)
    assert result.input_power_w == pytest.approx(
        result.shaft_power_w + result.copper_loss_w + result.iron_loss_w,
        rel=1e-12,
    )
    assert result.energy_closure_fraction < 1e-12
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.provenance.fidelity is FidelityLevel.ANALYTICAL


def test_motor_rejects_inconsistent_explicit_kt() -> None:
    with pytest.raises(ValidationError, match="Kv/Kt inconsistency"):
        MotorInput(
            kv_rpm_per_v=1000.0,
            kt_nm_per_a=0.02,
            resistance_ohm=0.03,
            no_load_current_a=1.0,
            speed_rpm=10_000,
            torque_nm=0.1,
        )


def test_esc_model_separates_conduction_and_switching_loss_with_power_closure() -> None:
    result = evaluate_esc(
        ESCInput(
            voltage_v=22.2,
            current_a=50.0,
            duty_cycle=0.8,
            rds_on_ohm=0.0015,
            switching_frequency_hz=24_000,
            rise_time_s=40e-9,
            fall_time_s=40e-9,
        )
    )

    assert result.conduction_loss_w == pytest.approx(3.0)
    assert result.switching_loss_w == pytest.approx(1.0656)
    assert result.input_power_w == pytest.approx(result.output_power_w + result.total_loss_w)
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_six_s_pack_voltage_and_heat_are_dimensionally_consistent() -> None:
    result = evaluate_six_s_battery(
        SixSBatteryInput(
            cell_ocv_v=3.70,
            cell_resistance_ohm=0.004,
            current_a=50.0,
            contact_and_wiring_resistance_ohm=0.003,
            soc=0.5,
            temperature_k=298.15,
        )
    )

    assert result.open_circuit_voltage_v == pytest.approx(22.2)
    assert result.loaded_voltage_v == pytest.approx(20.85)
    assert result.heat_generation_w == pytest.approx(67.5)
    assert result.chemical_power_w == pytest.approx(
        result.output_power_w + result.heat_generation_w
    )
    assert result.cell_count == 6


def test_lumped_thermal_model_matches_first_order_rc_solution() -> None:
    result = evaluate_thermal(
        ThermalInput(
            initial_temperature_k=300.0,
            ambient_temperature_k=295.0,
            heat_generation_w=100.0,
            thermal_resistance_k_per_w=0.2,
            thermal_capacitance_j_per_k=500.0,
            duration_s=100.0,
        )
    )

    expected = 315.0 + (300.0 - 315.0) * math.exp(-1.0)
    assert result.final_temperature_k == pytest.approx(expected)
    assert result.steady_state_temperature_k == pytest.approx(315.0)
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_static_edf_actuator_disk_benchmark_closes_momentum_and_energy() -> None:
    result = evaluate_edf(
        EDFInput(
            fan_diameter_m=0.070,
            hub_diameter_m=0.025,
            shaft_power_w=1000.0,
            fan_efficiency=0.70,
            air_density_kg_m3=1.225,
            freestream_velocity_m_s=0.0,
            speed_rpm=45_000.0,
            blade_count=12,
            stator_count=9,
        )
    )

    # T = (2 rho A P_fluid^2)^(1/3), with A equal to the open fan annulus.
    assert result.thrust_n == pytest.approx(15.914612, rel=1e-6)
    assert result.fluid_power_w == pytest.approx(700.0)
    assert result.thrust_n == pytest.approx(
        result.mass_flow_kg_s * 2.0 * result.induced_velocity_m_s,
        rel=1e-12,
    )
    assert result.fluid_power_w == pytest.approx(
        result.thrust_n * result.induced_velocity_m_s,
        rel=1e-12,
    )
    assert result.blade_passing_frequency_hz == pytest.approx(9000.0)
    assert result.provenance.model == "ideal-actuator-disk"


def test_shaft_bending_frequency_matches_simply_supported_beam_benchmark() -> None:
    result = evaluate_shaft(
        ShaftInput(
            length_m=0.20,
            diameter_m=0.008,
            elastic_modulus_pa=200e9,
            density_kg_m3=7800.0,
            speed_rpm=30_000,
        )
    )

    area = math.pi * 0.008**2 / 4
    inertia = math.pi * 0.008**4 / 64
    expected_hz = math.pi / 2 * math.sqrt(200e9 * inertia / (7800 * area * 0.20**4))
    assert result.first_bending_frequency_hz == pytest.approx(expected_hz)
    assert result.separation_margin_fraction == pytest.approx(
        abs(expected_hz - 500.0) / expected_hz
    )


def test_brayton_cycle_benchmark_closes_first_law_and_matches_specific_work() -> None:
    result = evaluate_gas_turbine(
        GasTurbineInput(
            mass_flow_kg_s=1.0,
            ambient_temperature_k=288.15,
            ambient_pressure_pa=101_325.0,
            compressor_pressure_ratio=4.0,
            compressor_efficiency=0.82,
            turbine_inlet_temperature_k=1200.0,
            turbine_efficiency=0.86,
            combustor_efficiency=0.98,
            combustor_pressure_loss_fraction=0.04,
            cp_j_kg_k=1005.0,
            gamma=1.4,
            fuel_lower_heating_value_j_kg=43e6,
        )
    )

    # Wc = m cp T1 [(PR^((gamma-1)/gamma) - 1) / eta_c].
    assert result.compressor_power_w == pytest.approx(171_633.476, rel=1e-6)
    assert result.turbine_power_w > result.compressor_power_w
    assert result.net_shaft_power_w == pytest.approx(
        result.turbine_power_w - result.compressor_power_w
    )
    assert result.energy_closure_fraction < 1e-12
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert "not pyCycle" in result.limitations[0]
