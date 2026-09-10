from __future__ import annotations

import pytest
from aeroworkbench_dynamics import assess_resonance, build_campbell
from elmer.adapter import inspect_elmer
from pybamm.adapter import inspect_pybamm, six_cell_series_state
from ross.adapter import first_critical_speed, inspect_ross


def test_six_cell_pack_and_motor_screening_contract() -> None:
    pack = six_cell_series_state(voltage_per_cell_v=3.7, current_a=35, soc=0.8)
    assert pack.cells_in_series == 6
    assert pack.voltage_v == pytest.approx(22.2)
    assert pack.fidelity == "ecm"


def test_campbell_resonance_triggers_harmonic_transient_escalation() -> None:
    points = build_campbell(
        rpm_values=(2250.0,), blade_count=12, stator_count=11, modal_frequency_hz=450.0
    )
    decision = assess_resonance(points)
    assert decision.state == "warning"
    assert decision.escalate_to == "harmonic-transient"
    critical = first_critical_speed(stiffness_n_m=1000.0, modal_mass_kg=0.1)
    assert critical.rpm > 0


def test_native_capabilities_fail_closed_when_tools_are_missing() -> None:
    assert inspect_pybamm("missing-pybamm").state == "unavailable"
    assert inspect_ross("missing-ross").state == "unavailable"
    assert inspect_elmer("missing-elmer").state == "unavailable"
