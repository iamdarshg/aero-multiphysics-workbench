"""AIRFRAME 09 Lane C: installed rotor/airframe two-way coupling."""

from __future__ import annotations

import pytest

from aeroworkbench_airframe.synthesis.rotor_airframe import (
    RotorAirframeNativeUnavailable,
    RotorAirframeSurface,
    couple_rotor_airframe,
)
from aeroworkbench_airframe.synthesis.rotorcraft import (
    RotorcraftFlightCondition,
    RotorcraftRotor,
)
from aeroworkbench_propulsors import BladeStation, RotorSpec


def _rotor() -> RotorcraftRotor:
    return RotorcraftRotor(
        RotorSpec(
            rotor_id="main",
            blade_count=2,
            tip_radius_m=2.0,
            hub_radius_m=0.25,
            rpm=420.0,
            direction="clockwise",
            shaft_id="main",
            stations=(
                BladeStation(0.45, 0.18, 8.0),
                BladeStation(1.2, 0.16, 4.0),
                BladeStation(1.9, 0.11, 1.0),
            ),
        ),
        position_m=(0.0, 0.0, 0.0),
    )


def _wing() -> RotorAirframeSurface:
    return RotorAirframeSurface(
        "wing",
        "wing-frame",
        ((0.0, 0.0, -0.8), (0.8, 0.0, -0.8), (1.6, 0.0, -0.8)),
        (2.0, 2.0, 2.0),
        normal=(0.0, 0.0, 1.0),
        rotor_feedback_factor=0.15,
    )


def test_wing_rotor_exchange_is_two_way_and_uses_typed_wake_field() -> None:
    condition = RotorcraftFlightCondition(velocity_m_s=(25.0, 0.0, 0.0))
    independent = couple_rotor_airframe(_rotor(), condition, ())
    coupled = couple_rotor_airframe(_rotor(), condition, (_wing(),), max_iterations=20)

    assert coupled.converged
    assert coupled.wake_field.source_frame == "rotor:main"
    assert coupled.wake_field.induced_flow_m_s[0][2] < 0.0
    assert coupled.surface_loads[0].surface_id == "wing"
    assert coupled.airframe_feedback_m_s != pytest.approx(0.0)
    assert coupled.rotor_result.loads.thrust_n != pytest.approx(
        independent.rotor_result.loads.thrust_n
    )
    assert coupled.provenance.source.value == "analytical"


def test_body_and_tail_receive_installed_wake_and_contribute_vehicle_moment() -> None:
    surfaces = (
        RotorAirframeSurface("body", "body-frame", ((0.0, 0.0, -0.5), (0.5, 0.0, -0.5)), (3.0, 3.0)),
        RotorAirframeSurface("tail", "tail-frame", ((0.0, 0.0, -3.0), (1.0, 0.0, -3.0)), (1.0, 1.0)),
    )
    result = couple_rotor_airframe(
        _rotor(),
        RotorcraftFlightCondition(),
        surfaces,
        thrust_line_m=(0.5, 0.0, 1.0),
    )

    assert [load.surface_id for load in result.surface_loads] == ["body", "tail"]
    assert all(load.local_velocity_m_s[2] < 0.0 for load in result.surface_loads)
    assert result.vehicle_trim.thrust_line_moment_n_m[1] != pytest.approx(0.0)
    assert result.vehicle_trim.total_moment_n_m != pytest.approx((0.0, 0.0, 0.0))


def test_native_free_wake_is_capability_gated() -> None:
    with pytest.raises(RotorAirframeNativeUnavailable):
        couple_rotor_airframe(_rotor(), RotorcraftFlightCondition(), (_wing(),), fidelity="native")
