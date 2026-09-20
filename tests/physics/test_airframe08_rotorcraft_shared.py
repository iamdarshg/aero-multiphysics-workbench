"""AIRFRAME 08 reopened: shared-rotor analytical rotorcraft physics."""

from __future__ import annotations

import pytest
from aeroworkbench_airframe.synthesis.rotorcraft import (
    RotorcraftControls,
    RotorcraftFlightCondition,
    RotorcraftLimits,
    RotorcraftRotor,
    RotorcraftNativeUnavailable,
    evaluate_rotorcraft,
    evaluate_rotorcraft_assembly,
    trim_rotorcraft,
)
from aeroworkbench_propulsors import BladeStation, RotorSpec


def _rotor(rotor_id: str = "main", z: float = 0.0) -> RotorcraftRotor:
    spec = RotorSpec(
        rotor_id=rotor_id,
        blade_count=2,
        tip_radius_m=2.0,
        hub_radius_m=0.25,
        rpm=420.0,
        direction="clockwise",
        shaft_id=rotor_id,
        stations=(
            BladeStation(0.45, 0.18, 8.0),
            BladeStation(1.2, 0.16, 4.0),
            BladeStation(1.9, 0.11, 1.0),
        ),
    )
    return RotorcraftRotor(spec=spec, position_m=(0.0, 0.0, z))


def _hover() -> RotorcraftFlightCondition:
    return RotorcraftFlightCondition(velocity_m_s=(0.0, 0.0, 0.0), density_kg_m3=1.225)


def test_hover_trim_closes_thrust_and_records_analytical_provenance() -> None:
    result = trim_rotorcraft(_rotor(), _hover(), target_thrust_n=900.0)
    assert result.converged
    assert result.controls.collective_rad > 0.0
    assert result.result.loads.thrust_n == pytest.approx(900.0, rel=0.03)
    assert result.provenance.source.value == "analytical"


def test_forward_flight_cyclic_changes_azimuthal_loading_and_hub_moment() -> None:
    condition = RotorcraftFlightCondition(velocity_m_s=(35.0, 0.0, 0.0), density_kg_m3=1.225)
    no_cyclic = evaluate_rotorcraft(_rotor(), condition, RotorcraftControls(collective_rad=0.12))
    cyclic = evaluate_rotorcraft(
        _rotor(), condition, RotorcraftControls(collective_rad=0.12, lateral_cyclic_rad=0.06)
    )
    assert max(cyclic.azimuthal_loads) - min(cyclic.azimuthal_loads) > 0.0
    assert cyclic.loads.hub_moment_n_m != pytest.approx(no_cyclic.loads.hub_moment_n_m)


def test_coaxial_rotors_exchange_wake_and_are_not_independent() -> None:
    condition = _hover()
    pair = evaluate_rotorcraft_assembly((_rotor("front"), _rotor("rear", z=-0.35)), condition)
    independent = evaluate_rotorcraft(_rotor("rear"), condition, RotorcraftControls(collective_rad=0.12))
    assert pair.wake_exchange[0].incoming_axial_velocity_m_s > 0.0
    assert pair.rotors[1].loads.thrust_n < independent.loads.thrust_n


def test_retreated_stall_and_advancing_tip_mach_fail_closed() -> None:
    condition = RotorcraftFlightCondition(velocity_m_s=(120.0, 0.0, 0.0), density_kg_m3=1.225)
    limits = RotorcraftLimits(max_tip_mach=0.65, max_retreating_angle_deg=12.0)
    result = evaluate_rotorcraft(
        _rotor(), condition, RotorcraftControls(collective_rad=0.2), limits=limits
    )
    assert not result.valid
    assert "ADVANCING_TIP_MACH" in result.violations or "RETREATING_BLADE_STALL" in result.violations


def test_native_rotorcraft_request_fails_closed() -> None:
    with pytest.raises(RotorcraftNativeUnavailable):
        evaluate_rotorcraft(_rotor(), _hover(), RotorcraftControls(), fidelity="native")
