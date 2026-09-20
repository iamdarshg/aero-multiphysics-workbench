from __future__ import annotations

from math import pi

import pytest

from aeroworkbench_coupling.resonance import (
    HarmonicBasis,
    ForcingSpectrum,
    ModalSpectrum,
    ResonancePolicy,
    check_resonance,
)


def test_async_bases_have_canonical_signed_identity_and_frequency() -> None:
    basis = HarmonicBasis(
        "shaft", "rotor-frame", 0.0, 0.0,
        base_orders=((" rotor-b ", -0.5), ("rotor-a", 2)),
        base_frequencies_hz=(("rotor-b", 130.0), ("rotor-a", 50.0)),
        phase_references_rad=(("rotor-b", pi), ("rotor-a", 0.25)),
        nodal_diameter=3,
    )

    assert basis.base_orders == (("rotor-a", 2.0), ("rotor-b", -0.5))
    assert basis.frequency_hz == pytest.approx(35.0)
    assert basis.order == pytest.approx(1.5)
    assert basis.order_identity == basis.base_orders
    assert basis.phase_identity == (("rotor-a", 0.25), ("rotor-b", pi))


def test_transform_phase_identity_includes_all_bases_and_delay() -> None:
    basis = HarmonicBasis(
        "shaft", "frame", 0.0, 0.0,
        base_orders=(("a", 2), ("b", -1)),
        base_frequencies_hz=(("a", 10), ("b", 13)),
        phase_references_rad=(("a", 0.1), ("b", 0.2)),
    )

    assert basis.transform_phase_identity(angle_rad=0.5, delay_s=0.25) == pytest.approx(
        2.0 * 0.5 - 1.0 * 0.5 - 2.0 * pi * 7.0 * 0.25 + 0.3
    )


def test_async_frequency_crossing_is_detected_and_digest_is_sensitive() -> None:
    first = HarmonicBasis(
        "shaft", "frame", 0.0, 0.0,
        base_orders=(("a", 2), ("b", -1)),
        base_frequencies_hz=(("a", 80), ("b", 30)),
        phase_references_rad=(("a", 0.0), ("b", 0.0)),
    )
    changed = HarmonicBasis(
        "shaft", "frame", 0.0, 0.0,
        base_orders=(("a", 2), ("b", -1)),
        base_frequencies_hz=(("a", 81), ("b", 30)),
        phase_references_rad=(("a", 0.0), ("b", 0.0)),
    )
    phase_changed = HarmonicBasis(
        "shaft", "frame", 0.0, 0.0,
        base_orders=(("a", 2), ("b", -1)),
        base_frequencies_hz=(("a", 80), ("b", 30)),
        phase_references_rad=(("a", 0.1), ("b", 0.0)),
    )
    forcing = ForcingSpectrum("rotors", "async", (first.frequency_hz,), (1.0,))
    trigger = check_resonance(
        (forcing,),
        (ModalSpectrum("structure", "mode", (130.0,), (0.01,)),),
        ResonancePolicy(2.0, 0.5, (), ("harmonic-response",), ("harmonic-response",)),
    )

    assert trigger.state == "triggered"
    assert first.cache_digest != changed.cache_digest
    assert first.cache_digest != phase_changed.cache_digest
