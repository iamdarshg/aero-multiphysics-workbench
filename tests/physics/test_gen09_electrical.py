"""GEN 09: generic electrical-machine and power-electronics participants.

Generic rotating-electrical infrastructure only: typed ports, a real fidelity
ladder (analytical/reduced/native), material-database-backed properties, an
inverter loss model that closes energy, and an OpenMDAO composition. No
application/vehicle model appears here. Native EM is capability-gated and fails
closed; analytical/map results are never relabelled native.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "packages" / "electrical"))

from aeroworkbench_electrical import (  # noqa: E402
    ElectricalCapabilityUnavailable,
    ElectricalModelError,
    FidelityLevel,
    OutOfEnvelopePolicy,
    build_analytical_map,
    get_machine_parameters,
    magnet_remanence,
    native_em_status,
    screening_drive_revision,
    screening_machine_revision,
    solve_electrical_thermal,
    solve_inverter,
    solve_machine,
)
from electrical.machine import (  # noqa: E402
    execute_machine_case,
    parse_machine_result,
    prepare_machine_case,
    validate_machine_result,
)
from electrical.power_electronics import (  # noqa: E402
    execute_inverter_case,
    parse_inverter_result,
    prepare_inverter_case,
    validate_inverter_result,
)
from participants.manifest import get_participant  # noqa: E402

_MACHINE_ID = "rotating-electrical-machine"
_DRIVE_ID = "power-electronics-drive"


def _analytical(**overrides: float):
    arguments = {
        "bus_voltage_v": 22.0,
        "speed_rpm": 20000.0,
        "winding_temp_k": 293.15,
        "magnet_temp_k": 293.15,
    }
    arguments.update(overrides)
    return solve_machine(screening_machine_revision(), **arguments)


# -- manifests / typed ports -------------------------------------------------


def test_manifests_expose_typed_ports_and_fidelity_ladder() -> None:
    machine = get_participant(_MACHINE_ID)
    assert machine.fidelity_levels == ("analytical", "reduced", "native")
    assert machine.coupling_direction == "two-way"
    assert ("machine_parameter_revision", "string") in {
        (port.name, port.data_type) for port in machine.inputs
    }
    output_names = {port.name for port in machine.outputs}
    assert {
        "speed_rpm",
        "torque_n_m",
        "current_a",
        "electrical_power_w",
        "mechanical_power_w",
        "copper_loss_w",
        "core_loss_w",
        "efficiency",
        "heat_load_winding_w",
        "heat_load_core_w",
        "heat_load_magnet_w",
    } <= output_names
    for port in machine.outputs:
        assert port.unit.strip()

    drive = get_participant(_DRIVE_ID)
    drive_outputs = {port.name for port in drive.outputs}
    assert {"dc_current_a", "conduction_loss_w", "switching_loss_w", "heat_load_w"} <= drive_outputs


# -- analytical level --------------------------------------------------------


def test_analytical_level_power_and_torque_consistency() -> None:
    parameters = screening_machine_revision()
    result = _analytical()
    omega = 20000.0 * math.pi / 30.0
    assert result.fidelity == FidelityLevel.ANALYTICAL.value
    assert result.source == "analytical-lumped"
    assert result.mechanical_power_w == pytest.approx(result.torque_n_m * omega)
    assert result.electrical_power_w == pytest.approx(
        result.mechanical_power_w + result.total_loss_w
    )
    assert 0.0 < result.efficiency < 1.0
    assert result.current_a > 0.0
    resistance = parameters.winding_resistance_at(293.15)
    assert result.copper_loss_w == pytest.approx(result.current_a**2 * resistance)
    assert result.validity.passed is True


def test_reduced_map_level_executes_with_reduced_source() -> None:
    parameters = screening_machine_revision()
    machine_map = build_analytical_map(
        parameters,
        speeds_rpm=(5000.0, 10000.0, 20000.0, 30000.0),
        torques_n_m=(0.0, 0.25, 0.5, 0.75, 1.0),
    )
    result = solve_machine(
        parameters,
        bus_voltage_v=22.0,
        speed_rpm=20000.0,
        winding_temp_k=293.15,
        magnet_temp_k=293.15,
        load_torque_n_m=0.5,
        fidelity="reduced",
        machine_map=machine_map,
    )
    assert result.fidelity == FidelityLevel.REDUCED.value
    assert result.source.startswith("parameter-map:")
    assert result.mechanical_power_w == pytest.approx(
        result.electrical_power_w - result.total_loss_w
    )
    assert result.validity.passed is True


def test_temperature_feedback_changes_electrical_behavior() -> None:
    cold = _analytical(winding_temp_k=293.15, magnet_temp_k=293.15)
    hot = _analytical(winding_temp_k=393.15, magnet_temp_k=393.15)
    assert hot.copper_loss_w > cold.copper_loss_w
    assert hot.torque_n_m != pytest.approx(cold.torque_n_m)
    assert hot.current_a != pytest.approx(cold.current_a)
    # Resistance rise is material-database backed, not a hard-coded factor.
    parameters = screening_machine_revision()
    assert parameters.winding_resistance_at(393.15) > parameters.winding_resistance_at(293.15)


# -- reduced map validity envelope ------------------------------------------


def test_map_interpolation_respects_validity_bounds() -> None:
    parameters = screening_machine_revision()
    machine_map = build_analytical_map(
        parameters,
        speeds_rpm=(5000.0, 10000.0, 20000.0, 30000.0),
        torques_n_m=(0.0, 0.25, 0.5, 0.75),
    )
    assert machine_map.speed_envelope_rpm == (5000.0, 30000.0)
    midpoint = machine_map.evaluate(15000.0, 0.375)
    low = machine_map.current_a[0][0]
    high = machine_map.current_a[-1][-1]
    assert low <= midpoint.current_a <= high
    assert midpoint.warnings == ()


def test_map_extrapolation_fails_or_clamps_per_policy() -> None:
    parameters = screening_machine_revision()
    machine_map = build_analytical_map(
        parameters,
        speeds_rpm=(5000.0, 10000.0, 20000.0),
        torques_n_m=(0.0, 0.25, 0.5),
    )
    with pytest.raises(ElectricalModelError) as failed:
        machine_map.evaluate(50000.0, 0.25)
    assert "OUT_OF_ENVELOPE" in str(failed.value)
    clamped = machine_map.evaluate(
        50000.0, 1.0, OutOfEnvelopePolicy.CLAMP
    )
    assert clamped.speed_rpm == pytest.approx(20000.0)
    assert clamped.torque_n_m == pytest.approx(0.5)
    assert len(clamped.warnings) == 2


def test_unknown_revision_fails_closed() -> None:
    with pytest.raises(ValueError):
        get_machine_parameters("does-not-exist")


# -- power electronics -------------------------------------------------------


def test_power_electronics_loss_included_in_energy_closure() -> None:
    result = solve_inverter(
        screening_drive_revision(),
        dc_bus_voltage_v=22.0,
        output_power_w=1500.0,
        switching_frequency_hz=24000.0,
        modulation_index=0.92,
        case_temp_k=320.0,
    )
    assert result.conduction_loss_w > 0.0
    assert result.switching_loss_w > 0.0
    assert result.total_loss_w == pytest.approx(
        result.conduction_loss_w + result.switching_loss_w
    )
    assert result.dc_power_w == pytest.approx(result.output_power_w + result.total_loss_w)
    assert result.dc_current_a == pytest.approx(result.dc_power_w / 22.0)
    assert 0.0 < result.efficiency < 1.0
    assert result.heat_load_w == pytest.approx(result.total_loss_w)
    assert result.validity.passed is True


# -- OpenMDAO composition ----------------------------------------------------


def test_openmdao_closes_machine_drive_battery_thermal_loop() -> None:
    result = solve_electrical_thermal(speed_rpm=20000.0)
    values = dict(result.values)
    assert result.engine == "openmdao"
    assert result.converged is True, result.detail
    delivered = values["battery-scalar-pack.pack_voltage_v"] * values[
        "power-electronics-drive.dc_current_a"
    ]
    consumed = (
        values["rotating-electrical-machine.mechanical_power_w"]
        + values["rotating-electrical-machine.total_loss_w"]
        + values["power-electronics-drive.total_loss_w"]
    )
    assert delivered == pytest.approx(consumed, rel=1e-5, abs=1e-3)
    assert values["power-electronics-drive.total_loss_w"] > 0.0
    assert values["rotating-electrical-machine.current_a"] > 0.0
    assert values["thermal-scalar-lumped.winding_temp_k"] > 293.15


# -- governed participant path ----------------------------------------------


def test_participant_executes_analytical_machine_and_validates(tmp_path: Path) -> None:
    inputs: dict[str, object] = {
        "machine_parameter_revision": "screening-r1",
        "fidelity": "analytical",
        "bus_voltage_v": 22.0,
        "commanded_speed_rpm": 20000.0,
        "winding_temp_k": 293.15,
        "magnet_temp_k": 293.15,
    }
    case_dir = tmp_path / "machine"
    receipt = prepare_machine_case(dict(inputs), case_dir)
    assert receipt.participant_id == _MACHINE_ID
    execute_machine_case(dict(inputs), case_dir)
    parsed = parse_machine_result(case_dir)
    assert parsed.scalars["torque_n_m"] > 0.0
    report = validate_machine_result(parsed.scalars, inputs)
    assert report.passed is True


def test_participant_executes_inverter_and_validates(tmp_path: Path) -> None:
    inputs: dict[str, object] = {
        "device_parameter_revision": "screening-r1",
        "fidelity": "analytical",
        "dc_bus_voltage_v": 22.0,
        "output_power_w": 1500.0,
        "switching_frequency_hz": 24000.0,
        "modulation_index": 0.92,
        "case_temp_k": 320.0,
    }
    case_dir = tmp_path / "drive"
    receipt = prepare_inverter_case(dict(inputs), case_dir)
    assert receipt.participant_id == _DRIVE_ID
    execute_inverter_case(dict(inputs), case_dir)
    parsed = parse_inverter_result(case_dir)
    assert parsed.scalars["total_loss_w"] > 0.0
    report = validate_inverter_result(parsed.scalars, inputs)
    assert report.passed is True


def test_detailed_unavailable_engine_fails_closed(tmp_path: Path) -> None:
    status = native_em_status()
    assert status.state in {"unavailable", "engine-present-not-wired"}
    with pytest.raises(ElectricalCapabilityUnavailable) as failed:
        solve_machine(
            screening_machine_revision(),
            bus_voltage_v=22.0,
            speed_rpm=20000.0,
            winding_temp_k=293.15,
            magnet_temp_k=293.15,
            fidelity="native",
        )
    assert failed.value.code == "CAPABILITY_UNAVAILABLE"

    from participants.errors import NativeErrorCode, ParticipantError

    inputs: dict[str, object] = {
        "fidelity": "native",
        "bus_voltage_v": 22.0,
        "commanded_speed_rpm": 20000.0,
        "winding_temp_k": 293.15,
        "magnet_temp_k": 293.15,
    }
    case_dir = tmp_path / "native"
    prepare_machine_case(dict(inputs), case_dir)
    with pytest.raises(ParticipantError) as adapter_failed:
        execute_machine_case(dict(inputs), case_dir)
    assert adapter_failed.value.code is NativeErrorCode.CAPABILITY_UNAVAILABLE


def test_material_database_properties_are_real() -> None:
    assert magnet_remanence("ndfeb-n42") > 1.0
    assert get_machine_parameters("screening-r1").core_loss_w_at(20000.0) > 0.0
