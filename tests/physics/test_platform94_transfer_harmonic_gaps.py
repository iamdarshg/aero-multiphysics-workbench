from __future__ import annotations

from math import pi

import pytest

from aeroworkbench_coupling import field
from aeroworkbench_coupling.resonance import HarmonicBasis


def test_3d_distributed_force_preserves_resultant_and_moment() -> None:
    source = field.register_mesh(
        "source",
        ((0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
        normals=((0.0, 0.0, 1.0),) * 2,
        areas=(1.0, 1.0),
    )
    target = field.register_mesh(
        "target",
        ((0.0, 1.0, 0.0), (0.5, 1.0, 0.0), (1.0, 1.0, 0.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
        areas=(0.5, 0.5, 1.0),
    )
    receipt = field.transfer_distributed_load(
        source, ((2.0, 0.0, 0.0), (2.0, 0.0, 0.0)), target, quantity="traction"
    )
    assert receipt.accepted
    assert receipt.resultant_force == pytest.approx((4.0, 0.0, 0.0))
    assert receipt.resultant_moment == pytest.approx((0.0, 0.0, -4.0))


def test_virtual_work_and_flux_closure_receipts() -> None:
    assert field.virtual_work_receipt(
        ((1.0, 0.0, 0.0),), ((2.0, 0.0, 0.0),), ((1.0, 0.0, 0.0),), ((2.0, 0.0, 0.0),)
    ).accepted
    assert field.thermal_flux_closure((2.0, 3.0), (1.0, 4.0)).accepted
    assert field.fluid_flux_closure((1.0, 2.0), (2.0, 1.0)).accepted


def test_temporal_resampling_declares_policy_and_closes_integral() -> None:
    receipt = field.resample_temporal(
        (0.0, 1.0, 2.0), (0.0, 2.0, 4.0), (0.0, 0.5, 1.0), interpolation="linear"
    )
    assert receipt.accepted
    assert receipt.values == pytest.approx((0.0, 1.0, 2.0))
    assert receipt.interpolation == "linear"
    assert receipt.extrapolation == "refuse"
    assert receipt.anti_alias == "none"


def test_harmonic_order_identity_phase_and_roundtrip() -> None:
    basis = HarmonicBasis(
        "shaft", "frame", 2.0, 3.0, amplitude_convention="peak",
        phase_reference="cosine", base_id="base-a", normalization="two-sided",
    )
    values = (2.0 + 0.0j,)
    shifted = field.transfer_harmonic_field(values, basis, angle_rad=pi / 6)
    assert shifted.coefficients[0] == pytest.approx(2j)
    assert shifted.basis.order_identity == ("base-a", 3.0)
    times = (0.0, 0.25, 0.5, 0.75)
    samples = field.harmonic_to_time(values, basis, times)
    roundtrip = field.time_to_harmonic(samples, times, basis)
    assert roundtrip.receipt.accepted
    assert roundtrip.coefficients[0] == pytest.approx(values[0], abs=1e-9)
