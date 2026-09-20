"""AIRFRAME 08: analytical rotorcraft synthesis and operating-point contracts."""

from __future__ import annotations

import pytest
from aeroworkbench_airframe.synthesis import (
    RotorcraftCapabilityUnavailable,
    evaluate_rotorcraft_envelope,
    generate_fixed_wing_seeds,
    probe_rotorcraft_foundation,
    synthesize_rotorcraft_seam,
)
from aeroworkbench_airframe.synthesis.requirements import compile_requirements_payload


def _compiled():
    return compile_requirements_payload(
        {
            "requirements": [
                {"id": "payload", "kind": "mission", "metric": "payload_mass", "operator": "at_least", "value": 100.0, "unit": "kg"},
                {"id": "stall", "kind": "performance", "metric": "stall_speed", "operator": "at_most", "value": 28.0, "unit": "m/s"},
                {"id": "cruise", "kind": "performance", "metric": "cruise_speed", "operator": "at_least", "value": 45.0, "unit": "m/s"},
            ]
        }
    )


def test_airframe08_hover_and_forward_flight_are_distinct_analytical_points() -> None:
    assert probe_rotorcraft_foundation().available
    seam = synthesize_rotorcraft_seam(_compiled())
    assert seam.available and len(seam.seeds) == 1
    envelope = evaluate_rotorcraft_envelope(seam.seeds[0])
    assert envelope.valid
    assert envelope.hover.forward_speed_m_s == pytest.approx(0.0)
    assert envelope.hover.advance_ratio == pytest.approx(0.0)
    assert envelope.forward_flight.forward_speed_m_s > 0.0
    assert envelope.forward_flight.advance_ratio > 0.0
    assert envelope.forward_flight.required_power_w > envelope.hover.required_power_w
    assert envelope.provenance.source.value == "analytical"


def test_airframe08_native_rotor_request_fails_closed_without_receipt() -> None:
    seed = synthesize_rotorcraft_seam(_compiled()).seeds[0]
    with pytest.raises(RotorcraftCapabilityUnavailable, match="NATIVE_ROTOR_RECEIPT_REQUIRED"):
        evaluate_rotorcraft_envelope(seed, fidelity="native")


def test_airframe08_fixed_wing_seed_is_not_accepted_as_rotorcraft() -> None:
    fixed = generate_fixed_wing_seeds(_compiled(), seed_count=1)[0]
    with pytest.raises(ValueError, match="ROTORCRAFT_SEED_REQUIRED"):
        evaluate_rotorcraft_envelope(fixed)
