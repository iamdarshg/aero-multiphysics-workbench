from dataclasses import replace
from math import pi

import pytest

from aeroworkbench_core import physical
from aeroworkbench_coupling import field


def contract(semantic="wrench", unit="N", target_frame="vehicle"):
    source = physical.PhysicalPort("out", semantic, unit, "out", "motor")
    target = physical.PhysicalPort("in", semantic, unit, "in", target_frame)
    return physical.InterfaceContract("motor", source, "vehicle", target)


def test_wrench_rotation_reference_shift_and_virtual_work():
    transform = physical.RigidTransform("motor", "vehicle",
        ((0, -1, 0), (1, 0, 0), (0, 0, 1)), (1, 0, 0))
    receipt = field.transfer_wrench(contract(), (10, 0, 0), (0, 0, 2), transform)
    assert receipt.values == pytest.approx((0, 10, 0, 0, 0, 12))
    assert receipt.source_system == "motor"
    assert receipt.target_port == "in"
    assert receipt.accepted
    assert len(receipt.operator_digest) == 64
    with pytest.raises(ValueError, match="FRAME"):
        field.transfer_wrench(contract(), (10, 0, 0), (0, 0, 2),
                              replace(transform, source_frame="other"))
    good = field.virtual_work_receipt((2, 4), (3, 1), (10,), (1,))
    assert good.accepted  # 2*3 + 4*1 = 10*1
    assert not field.virtual_work_receipt((2, 4), (3, 1), (10,), (2,)).accepted


def test_thermal_electrical_and_shaft_power_close_or_reject():
    assert field.power_closure(contract("thermal", "W"), 100, 90, loss_w=10).accepted
    assert not field.power_closure(contract("thermal", "W"), 100, 90).accepted
    assert field.electrical_closure(contract("electrical", "W"),
                                    20, 5, 18, 5, loss_w=10).accepted
    assert field.shaft_closure(contract("shaft", "W"),
                               2, 50, 3, 30, loss_w=10).accepted
    with pytest.raises(ValueError):
        field.power_closure(contract("thermal", "W"), 100, 90, loss_w=-10)


def test_harmonics_keep_complex_phase_order_and_shaft_identity():
    basis = physical.HarmonicBasis("shaft-1", "motor", frequency_hz=2, order=3)
    result = field.transfer_harmonic(contract("harmonic", "N"),
        (1+0j,), basis, delay_s=0.125, angle_rad=pi/6)
    # exp(-i*2*pi*2*.125 + i*3*pi/6) = 1
    assert result.coefficients == pytest.approx((1+0j,))
    assert result.basis.shaft_id == "shaft-1"
    assert result.basis.order == 3
    assert result.basis.frame == "vehicle"
    assert result.receipt.accepted
    with pytest.raises(ValueError, match="FRAME"):
        field.transfer_harmonic(contract("harmonic", "N"), (1+0j,),
                                replace(basis, frame="wrong"))


def test_legacy_field_receipt_has_mesh_names_not_objects():
    source = field.register_mesh("a", (0, 1))
    target = field.register_mesh("b", (0, .5, 1))
    receipt = field.transfer_field(source, target, "traction", (2, 2))
    assert receipt.source_mesh == "a"
    assert receipt.target_mesh == "b"
