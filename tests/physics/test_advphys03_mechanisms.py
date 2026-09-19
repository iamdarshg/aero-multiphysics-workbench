"""ADV-PHYS 03: generic joints, supports, bearings, seals, gears, tribology.

These tests drive the generic mechanical-interface participants from typed,
deterministic fixtures. Every result must be unit-bearing, hashable, and carry
source/fidelity/provenance; declared limits must fail closed with provenance;
and the native tribology/FEA seam must fail closed when the engine is absent.
No result is ever relabelled analytical when native physics was requested.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_mechanisms import (
    LUBRICANTS,
    MECHANISM_PARTICIPANTS,
    SI_UNITS,
    BearingCatalog,
    BearingGeometry,
    BoltedJointSpec,
    CapabilityUnavailable,
    ContactInterface,
    GearKind,
    GearPairSpec,
    JointKind,
    JointSpec,
    JournalBearingGeometry,
    LimitExceeded,
    LubricantSpec,
    LubricantSupply,
    MechanismError,
    PinJointSpec,
    SealKind,
    SealSpec,
    SixDofProperties,
    SupportKind,
    SupportSpec,
    UnitError,
    dynamic_viscosity_at,
    evaluate_bolted_joint,
    evaluate_contact_friction,
    evaluate_gear_pair,
    evaluate_joint,
    evaluate_journal_bearing,
    evaluate_lubrication,
    evaluate_pin_hinge,
    evaluate_rolling_bearing,
    evaluate_seal,
    evaluate_support,
    finite,
    kinematic_viscosity_at,
    mechanism_participants,
    native_capability,
    participant_ids,
    require_native,
    require_unit,
    solve_native_tribology,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "mechanisms"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _lubricant() -> LubricantSpec:
    return LubricantSpec(**_fixture("lubricant_iso_vg46.json"))


def _catalog(**overrides: object) -> BearingCatalog:
    payload = _fixture("bearing_catalog.json")
    payload.update(overrides)
    return BearingCatalog(**payload)


def _bearing_geometry() -> BearingGeometry:
    return BearingGeometry(
        bore_diameter_m=0.03,
        outer_diameter_m=0.062,
        width_m=0.016,
        pitch_diameter_m=0.046,
        rolling_element_count=9,
        rolling_element_diameter_m=0.0095,
        contact_angle_deg=0.0,
    )


# -- A. unit and validation contracts ----------------------------------------


def test_advphys03_units_are_known_si_labels() -> None:
    assert {"N", "N/m", "N*s/m", "N*m", "Pa", "W", "m3/s", "kg/s", "K"} <= SI_UNITS
    for label in ("N", "N/m", "N*s/m", "N*m", "Pa", "W", "m3/s", "kg/s", "K"):
        assert require_unit(label) == label


def test_advphys03_unknown_unit_fails_closed() -> None:
    with pytest.raises(UnitError):
        require_unit("furlong")


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "5"])
def test_advphys03_finite_rejects_non_numbers(bad: object) -> None:
    with pytest.raises(MechanismError):
        finite(bad, "value")


def test_advphys03_finite_rejects_out_of_range() -> None:
    with pytest.raises(MechanismError):
        finite(-1.0, "value", positive=True)


# -- B. provenance and determinism -------------------------------------------


def test_advphys03_provenance_hash_is_deterministic() -> None:
    first = evaluate_support(
        SupportSpec(
            support_id="s1",
            kind=SupportKind.ELASTIC,
            properties=SixDofProperties(translation_stiffness_n_m=(1e7, 2e7, 1e7)),
            length_m=0.2,
            thermal_expansion_per_k=1.2e-5,
        ),
        temperature_k=333.15,
    )
    second = evaluate_support(
        SupportSpec(
            support_id="s1",
            kind=SupportKind.ELASTIC,
            properties=SixDofProperties(translation_stiffness_n_m=(1e7, 2e7, 1e7)),
            length_m=0.2,
            thermal_expansion_per_k=1.2e-5,
        ),
        temperature_k=333.15,
    )
    assert first.provenance.inputs_hash == second.provenance.inputs_hash
    assert len(first.provenance.inputs_hash) == 64


def test_advphys03_result_units_are_all_si() -> None:
    result = evaluate_lubrication(_lubricant(), 333.15)
    for unit in result.units().values():
        require_unit(unit)


# -- C. lubrication -----------------------------------------------------------


def test_advphys03_astm_d341_reproduces_reference_points() -> None:
    lubricant = _lubricant()
    assert kinematic_viscosity_at(lubricant, 313.15) == pytest.approx(46.0e-6, rel=1e-6)
    assert kinematic_viscosity_at(lubricant, 373.15) == pytest.approx(6.8e-6, rel=1e-6)


def test_advphys03_viscosity_is_monotonic_and_dynamic_scales_with_density() -> None:
    lubricant = _lubricant()
    cold = kinematic_viscosity_at(lubricant, 313.15)
    hot = kinematic_viscosity_at(lubricant, 373.15)
    assert cold > hot
    assert dynamic_viscosity_at(lubricant, 313.15) == pytest.approx(cold * 872.0)


def test_advphys03_lubrication_envelope_is_reported() -> None:
    inside = evaluate_lubrication(_lubricant(), 333.15)
    outside = evaluate_lubrication(_lubricant(), 200.0)
    assert inside.validity.passed is True
    assert outside.validity.passed is False
    assert outside.provenance.source is ResultSource.ANALYTICAL


def test_advphys03_supply_heat_rejection_and_rise() -> None:
    lubricant = _lubricant()
    supply = LubricantSupply(temperature_k=313.15, pressure_pa=3.0e5, flow_rate_m3_s=1.0e-4)
    heat = supply.heat_rejection_w(lubricant, 323.15)
    assert heat == pytest.approx(1.0e-4 * 872.0 * 1900.0 * 10.0)
    assert supply.temperature_rise_k(lubricant, heat) == pytest.approx(10.0)
    assert supply.mass_flow_kg_s(lubricant) == pytest.approx(0.0872)


def test_advphys03_lubricant_registry_is_addressable() -> None:
    assert LUBRICANTS["iso-vg46"].viscosity_ratio_40_100 > 1.0
    with pytest.raises(MechanismError):
        LubricantSpec(
            name="bad",
            kinematic_viscosity_40c_m2_s=5.0e-6,
            kinematic_viscosity_100c_m2_s=8.0e-6,
            density_kg_m3=800.0,
            specific_heat_j_kg_k=1900.0,
            thermal_conductivity_w_m_k=0.14,
            pressure_viscosity_coefficient_inv_pa=2.0e-8,
        )


# -- D. supports --------------------------------------------------------------


def test_advphys03_elastic_support_reaction_and_growth() -> None:
    spec = SupportSpec(
        support_id="elastic-1",
        kind=SupportKind.ELASTIC,
        properties=SixDofProperties(
            translation_stiffness_n_m=(1e7, 2e7, 1e7),
            translation_damping_n_s_m=(1e3, 2e3, 1e3),
        ),
        length_m=0.2,
        thermal_expansion_per_k=1.2e-5,
        allowable_reaction_n=1.0e4,
    )
    result = evaluate_support(spec, temperature_k=333.15, misalignment_m=1.0e-4)
    assert result.grounded is False
    assert result.reaction_force_n == pytest.approx(2000.0)
    assert result.thermal_growth_m == pytest.approx(1.2e-5 * 0.2 * 40.0)
    assert result.validity.passed is True


def test_advphys03_fixed_support_is_grounded() -> None:
    spec = SupportSpec(
        support_id="fixed-1",
        kind=SupportKind.FIXED,
        properties=SixDofProperties(),
        length_m=0.0,
        thermal_expansion_per_k=0.0,
    )
    result = evaluate_support(spec, temperature_k=293.15)
    assert result.grounded is True


def test_advphys03_elastic_support_requires_stiffness() -> None:
    with pytest.raises(MechanismError):
        SupportSpec(
            support_id="bad",
            kind=SupportKind.ELASTIC,
            properties=SixDofProperties(),
            length_m=0.1,
            thermal_expansion_per_k=0.0,
        )


# -- E. joints ----------------------------------------------------------------


def test_advphys03_bolted_joint_load_sharing() -> None:
    spec = BoltedJointSpec(
        joint_id="bolt-1",
        bolt_count=4,
        bolt_stiffness_n_m=2.0e8,
        member_stiffness_n_m=8.0e8,
        proof_load_n=50000.0,
        preload_fraction=0.75,
        external_load_n=60000.0,
        friction_coefficient=0.2,
    )
    result = evaluate_bolted_joint(spec)
    assert result.preload_n == pytest.approx(150000.0)
    assert result.bolt_load_n == pytest.approx(162000.0)
    assert result.clamp_load_n == pytest.approx(102000.0)
    assert result.slip_capacity_n == pytest.approx(20400.0)
    assert result.utilization == pytest.approx(0.81)


def test_advphys03_bolted_joint_separation_fails_closed() -> None:
    spec = BoltedJointSpec(
        joint_id="bolt-2",
        bolt_count=4,
        bolt_stiffness_n_m=2.0e8,
        member_stiffness_n_m=8.0e8,
        proof_load_n=50000.0,
        preload_fraction=0.75,
        external_load_n=300000.0,
        friction_coefficient=0.2,
    )
    with pytest.raises(LimitExceeded) as failed:
        evaluate_bolted_joint(spec)
    assert "separation" in failed.value.violations
    assert len(failed.value.provenance.inputs_hash) == 64


def test_advphys03_pin_joint_pressure_and_friction() -> None:
    spec = PinJointSpec(
        joint_id="pin-1",
        pin_diameter_m=0.02,
        length_m=0.03,
        load_n=5000.0,
        friction_coefficient=0.15,
        angular_velocity_rad_s=10.0,
        allowable_pressure_pa=20.0e6,
    )
    result = evaluate_pin_hinge(spec)
    assert result.contact_pressure_pa == pytest.approx(5000.0 / 0.0006)
    assert result.friction_torque_n_m == pytest.approx(7.5)
    assert result.heat_generation_w == pytest.approx(75.0)
    assert result.validity.passed is True


def test_advphys03_pin_joint_pressure_limit_fails_closed() -> None:
    spec = PinJointSpec(
        joint_id="pin-2",
        pin_diameter_m=0.02,
        length_m=0.03,
        load_n=5000.0,
        friction_coefficient=0.1,
        allowable_pressure_pa=5.0e6,
    )
    with pytest.raises(LimitExceeded) as failed:
        evaluate_pin_hinge(spec)
    assert failed.value.violations == ("contact_pressure",)


def test_advphys03_generic_contact_joint_reports_loss_and_backlash() -> None:
    spec = JointSpec(
        joint_id="coupling-1",
        kind=JointKind.CONTACT,
        properties=SixDofProperties(translation_stiffness_n_m=(1e6, 1e6, 1e6)),
        friction_coefficient=0.3,
        backlash_m=1.0e-4,
        clearance_m=2.0e-4,
    )
    result = evaluate_joint(
        spec,
        applied_load_n=(100.0, 0.0, 0.0),
        sliding_velocity_m_s=2.0,
        contact_area_m2=1.0e-4,
    )
    assert result.friction_force_n == pytest.approx(30.0)
    assert result.heat_generation_w == pytest.approx(60.0)
    assert result.contact_pressure_pa == pytest.approx(1.0e6)
    assert result.validity.passed is True


def test_advphys03_generic_joint_load_limit_fails_closed() -> None:
    spec = JointSpec(
        joint_id="coupling-2",
        kind=JointKind.SPLINE,
        properties=SixDofProperties(translation_stiffness_n_m=(1e6, 1e6, 1e6)),
        allowable_load_n=1000.0,
    )
    with pytest.raises(LimitExceeded) as failed:
        evaluate_joint(spec, applied_load_n=(2000.0, 0.0, 0.0))
    assert failed.value.violations == ("load",)


# -- F. bearings --------------------------------------------------------------


def test_advphys03_rolling_bearing_l10_life() -> None:
    result = evaluate_rolling_bearing(
        _catalog(),
        _bearing_geometry(),
        speed_rpm=3000.0,
        radial_load_n=5000.0,
    )
    assert result.equivalent_load_n == pytest.approx(5000.0)
    assert result.life_revolutions == pytest.approx(216.0e6)
    assert result.life_hours == pytest.approx(1200.0)
    assert result.dn_value_mm_rpm == pytest.approx(30.0 * 3000.0)
    assert result.friction_torque_n_m == pytest.approx(0.5 * 0.0015 * 5000.0 * 0.046)
    assert result.heat_generation_w == pytest.approx(
        result.friction_torque_n_m * 3000.0 * 3.141592653589793 / 30.0
    )


def test_advphys03_rolling_bearing_speed_limit_fails_closed() -> None:
    with pytest.raises(LimitExceeded) as failed:
        evaluate_rolling_bearing(
            _catalog(),
            _bearing_geometry(),
            speed_rpm=12000.0,
            radial_load_n=5000.0,
        )
    assert "limiting_speed" in failed.value.violations
    assert len(failed.value.provenance.inputs_hash) == 64


def test_advphys03_rolling_bearing_feeds_rotordynamics() -> None:
    result = evaluate_rolling_bearing(
        _catalog(),
        _bearing_geometry(),
        speed_rpm=3000.0,
        radial_load_n=5000.0,
    )
    rotor_bearing = result.to_rotor_bearing(node=0)
    assert rotor_bearing.kxx == pytest.approx(1.0e8)
    assert rotor_bearing.cxx == pytest.approx(1.0e4)


def test_advphys03_bearing_without_stiffness_fails_closed_for_rotordynamics() -> None:
    catalog = _catalog(radial_stiffness_n_m=None, damping_n_s_m=None)
    result = evaluate_rolling_bearing(
        catalog,
        _bearing_geometry(),
        speed_rpm=3000.0,
        radial_load_n=5000.0,
    )
    with pytest.raises(CapabilityUnavailable):
        result.to_rotor_bearing(node=1)


def test_advphys03_journal_bearing_sommerfeld_and_film() -> None:
    geometry = JournalBearingGeometry(
        journal_diameter_m=0.05,
        length_m=0.025,
        radial_clearance_m=25.0e-6,
        eccentricity_ratio=0.5,
    )
    state = evaluate_lubrication(_lubricant(), 313.15)
    result = evaluate_journal_bearing(
        geometry,
        state,
        speed_rpm=3000.0,
        load_n=1000.0,
        radial_stiffness_n_m=5.0e7,
        damping_n_s_m=5.0e3,
    )
    assert result.min_film_thickness_m == pytest.approx(12.5e-6)
    assert result.sommerfeld_number > 0.0
    assert result.friction_torque_n_m > 0.0
    assert result.heat_generation_w > 0.0
    assert result.to_rotor_bearing(node=2).kyy == pytest.approx(5.0e7)


# -- G. gears -----------------------------------------------------------------


def test_advphys03_gear_pair_fixture_loads_and_loss() -> None:
    payload = _fixture("gear_pair_helical.json")
    payload["kind"] = GearKind(payload["kind"])
    spec = GearPairSpec(**payload)  # type: ignore[arg-type]
    result = evaluate_gear_pair(spec, input_torque_n_m=50.0, input_speed_rpm=1500.0)
    assert result.gear_ratio == pytest.approx(2.0)
    assert result.pitch_diameter_driving_m == pytest.approx(0.04)
    assert result.tangential_load_n == pytest.approx(2500.0)
    assert result.radial_load_n == pytest.approx(2500.0 * 0.36397023426620234)
    assert result.power_in_w == pytest.approx(50.0 * 1500.0 * 3.141592653589793 / 30.0)
    assert result.power_loss_w == pytest.approx(result.power_in_w * 0.02)
    assert result.heat_generation_w == pytest.approx(result.power_loss_w)
    assert result.validity.passed is True


def test_advphys03_gear_contact_stress_limit_fails_closed() -> None:
    spec = GearPairSpec(
        gear_id="gear-limit",
        kind=GearKind.SPUR,
        teeth_driving=18,
        teeth_driven=36,
        normal_module_m=0.003,
        face_width_m=0.015,
        mesh_efficiency=0.98,
        youngs_modulus_pa=206.0e9,
        poisson_ratio=0.3,
        allowable_contact_stress_pa=1.0e8,
    )
    with pytest.raises(LimitExceeded) as failed:
        evaluate_gear_pair(spec, input_torque_n_m=200.0, input_speed_rpm=3000.0)
    assert failed.value.violations == ("contact_stress",)


# -- H. seals -----------------------------------------------------------------


def test_advphys03_clearance_seal_hagen_poiseuille_leakage() -> None:
    spec = SealSpec(
        seal_id="seal-1",
        kind=SealKind.CLEARANCE,
        diameter_m=0.05,
        clearance_m=50.0e-6,
        length_m=0.02,
        allowable_leakage_m3_s=1.0e-6,
    )
    result = evaluate_seal(
        spec,
        pressure_drop_pa=2.0e5,
        density_kg_m3=872.0,
        dynamic_viscosity_pa_s=0.04,
    )
    expected = 3.141592653589793 * 0.05 * (50.0e-6) ** 3 * 2.0e5 / (12.0 * 0.04 * 0.02)
    assert result.leakage_volume_flow_m3_s == pytest.approx(expected)
    assert result.leakage_mass_flow_kg_s == pytest.approx(expected * 872.0)
    assert result.leakage_to_fluid_network()["leakage_mass_flow_kg_s"] == pytest.approx(
        expected * 872.0
    )
    assert result.validity.passed is True


def test_advphys03_seal_leakage_limit_fails_closed() -> None:
    spec = SealSpec(
        seal_id="seal-2",
        kind=SealKind.CLEARANCE,
        diameter_m=0.05,
        clearance_m=50.0e-6,
        length_m=0.02,
        allowable_leakage_m3_s=1.0e-7,
    )
    with pytest.raises(LimitExceeded) as failed:
        evaluate_seal(
            spec,
            pressure_drop_pa=2.0e5,
            density_kg_m3=872.0,
            dynamic_viscosity_pa_s=0.04,
        )
    assert failed.value.violations == ("leakage",)


def test_advphys03_lip_seal_friction_heats() -> None:
    spec = SealSpec(
        seal_id="seal-lip",
        kind=SealKind.LIP,
        diameter_m=0.04,
        clearance_m=0.0,
        length_m=0.004,
        friction_coefficient=0.2,
        radial_preload_n=100.0,
    )
    result = evaluate_seal(
        spec,
        pressure_drop_pa=1.0e5,
        density_kg_m3=872.0,
        dynamic_viscosity_pa_s=0.04,
        speed_rpm=3000.0,
    )
    assert result.leakage_volume_flow_m3_s == pytest.approx(0.0)
    assert result.friction_torque_n_m == pytest.approx(0.2 * 100.0 * 0.04 / 2.0)
    assert result.heat_generation_w > 0.0


# -- I. tribology -------------------------------------------------------------


def _contact(rq: float) -> ContactInterface:
    return ContactInterface(
        interface_id="contact-1",
        normal_load_n=1000.0,
        sliding_velocity_m_s=1.0,
        friction_coefficient=0.05,
        hardness_pa=5.0e9,
        wear_coefficient=1.0e-5,
        contact_area_m2=1.0e-4,
        effective_radius_m=0.01,
        contact_length_m=0.01,
        roughness_rq1_m=rq,
        roughness_rq2_m=rq,
        effective_modulus_pa=1.0e11,
    )


def test_advphys03_dry_contact_friction_and_archard_wear() -> None:
    result = evaluate_contact_friction(_contact(0.2e-6))
    assert result.friction_force_n == pytest.approx(50.0)
    assert result.friction_power_w == pytest.approx(50.0)
    assert result.heat_generation_w == pytest.approx(50.0)
    assert result.wear_volume_rate_m3_s == pytest.approx(2.0e-12)
    assert result.wear_depth_rate_m_s == pytest.approx(2.0e-8)
    assert result.regime == "dry"
    assert result.provenance.source is ResultSource.ANALYTICAL


@pytest.mark.parametrize(
    ("roughness", "regime"),
    [
        (0.05e-6, "elastohydrodynamic"),
        (0.1e-6, "mixed"),
        (1.0e-6, "boundary"),
    ],
)
def test_advphys03_ehl_regime_from_lambda(roughness: float, regime: str) -> None:
    state = evaluate_lubrication(_lubricant(), 313.15)
    result = evaluate_contact_friction(_contact(roughness), state)
    assert result.film_thickness_m > 0.0
    assert result.regime == regime
    assert result.lambda_ratio > 0.0


def test_advphys03_native_tribology_fails_closed() -> None:
    with pytest.raises(CapabilityUnavailable):
        solve_native_tribology(_contact(0.2e-6), solver_name="definitely-absent-tribo-xyz")


# -- J. participants ----------------------------------------------------------


def test_advphys03_participant_registry_covers_all_components() -> None:
    ids = participant_ids()
    assert "rolling-bearing" in ids
    assert "mechanical-seal" in ids
    assert "gear-mesh" in ids
    assert "tribology-contact" in ids
    assert len(mechanism_participants()) == len(MECHANISM_PARTICIPANTS)


def test_advphys03_participant_ports_route_to_closures() -> None:
    bearing = next(p for p in MECHANISM_PARTICIPANTS if p.participant_id == "rolling-bearing")
    targets = {port.target for port in bearing.outputs}
    assert {"rotordynamic", "thermal", "fatigue"} <= targets
    assert "radial_stiffness_n_m" in bearing.port_names()


def test_advphys03_native_capability_is_capability_gated() -> None:
    state = native_capability("contact-fea")
    assert state.state == "unavailable"
    with pytest.raises(CapabilityUnavailable):
        require_native("contact-fea")
