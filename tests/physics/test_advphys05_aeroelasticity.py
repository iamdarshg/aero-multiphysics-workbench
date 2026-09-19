"""ADV-PHYS 05: generic aeroelasticity, flutter, forced response, gust and loads.

These tests drive the generic aeroelastic layer from typed, deterministic
fixtures. They cover linear/modal coupling, the flutter/stability fidelity
ladder, forced response (rotating-order and pressure-spectrum), mistuning and
cyclic assembly, atmospheric gust/dynamic loads, and the contact/rub escalation
seam. Every result must be unit-bearing, hashable, and carry source/fidelity/
software-identity/provenance; native FEA/CFD/FSI seams must fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_aeroelasticity import (
    AEROELASTIC_PARTICIPANTS,
    SI_UNITS,
    AeroelasticCapabilityUnavailable,
    AeroelasticError,
    AeroelasticFidelity,
    AtmosphericGust,
    CyclicStructureSpec,
    GustKind,
    HarmonicForce,
    ModalBasis,
    PressureField,
    PressureSample,
    RubContactSpec,
    StructuralMode,
    TypicalSection,
    UnitError,
    actuator_force,
    aerodynamic_damping_estimate,
    analyze_cyclic_structure,
    assess_flutter_escalation,
    assess_modal_resonance,
    build_stability_curve,
    dryden_psd_m2_s,
    evaluate_contact_event,
    evaluate_continuous_gust,
    evaluate_discrete_gust,
    evaluate_harmonic_response,
    evaluate_stability,
    finite,
    localization_factor,
    map_pressure_to_modes,
    match_excitation_to_modes,
    participant_ids,
    participant_native_states,
    pressure_spectrum_forces,
    require_unit,
    rotating_order_force,
    sector_to_full_mapping,
    solve_native_contact,
    solve_pk_flutter,
    solve_transient_fsi,
)
from aeroworkbench_core.resonance import Excitation
from aeroworkbench_core.types import FidelityLevel, ResultSource
from aeroworkbench_dynamics import ForcingLine

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "aeroelasticity"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _basis() -> ModalBasis:
    payload = _fixture("modal_coupling.json")
    modes = tuple(
        StructuralMode(
            mode_id=mode["mode_id"],
            frequency_hz=mode["frequency_hz"],
            damping_ratio=mode["damping_ratio"],
            generalized_mass_kg=mode["generalized_mass_kg"],
            shape=tuple(tuple(entry) for entry in mode["shape"]),
        )
        for mode in payload["modes"]
    )
    return ModalBasis("modal-coupling-basis", modes)


def _field() -> PressureField:
    payload = _fixture("modal_coupling.json")
    samples = tuple(
        PressureSample(
            node_id=sample["node_id"],
            location_m=tuple(sample["location_m"]),
            pressure_pa=sample["pressure_pa"],
            area_m2=sample["area_m2"],
            normal=tuple(sample["normal"]),
        )
        for sample in payload["samples"]
    )
    return PressureField(payload["interface_id"], samples)


def _section() -> tuple[TypicalSection, dict[str, Any]]:
    payload = _fixture("typical_section.json")
    section = TypicalSection(
        section_id=payload["section_id"],
        semi_chord_m=payload["semi_chord_m"],
        elastic_axis_fraction=payload["elastic_axis_fraction"],
        mass_matrix=tuple(tuple(row) for row in payload["mass_matrix"]),
        stiffness_matrix=tuple(tuple(row) for row in payload["stiffness_matrix"]),
        damping_matrix=tuple(tuple(row) for row in payload["damping_matrix"]),
        lift_curve_slope_per_rad=payload["lift_curve_slope_per_rad"],
        density_kg_m3=payload["density_kg_m3"],
    )
    return section, payload


# -- A. units, validation, provenance ----------------------------------------


def test_advphys05_units_are_known_si_labels() -> None:
    for label in ("N", "N/m", "Pa", "Hz", "m/s", "dimensionless", "1/s"):
        assert label in SI_UNITS
        assert require_unit(label) == label


def test_advphys05_unknown_unit_fails_closed() -> None:
    with pytest.raises(UnitError):
        require_unit("furlong")


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "5"])
def test_advphys05_finite_rejects_non_numbers(bad: object) -> None:
    with pytest.raises(AeroelasticError):
        finite(bad, "value")


def test_advphys05_finite_rejects_out_of_range() -> None:
    with pytest.raises(AeroelasticError):
        finite(-1.0, "value", positive=True)


def test_advphys05_provenance_hash_is_deterministic() -> None:
    first = map_pressure_to_modes(_field(), _basis())
    second = map_pressure_to_modes(_field(), _basis())
    assert first.provenance.inputs_hash == second.provenance.inputs_hash
    assert len(first.provenance.inputs_hash) == 64
    assert first.provenance.source is ResultSource.ANALYTICAL
    assert first.software.canonical()["name"] == "aeroworkbench-aeroelasticity"


def test_advphys05_result_units_are_all_si() -> None:
    for result in (
        map_pressure_to_modes(_field(), _basis()),
        build_stability_curve(_section()[0].to_system(), speeds_m_s=(1.0, 20.0)),
        evaluate_harmonic_response(_basis(), (HarmonicForce("bend-1", 10.0, 100.0),)),
    ):
        for unit in result.units().values():
            assert require_unit(unit) == unit


def test_advphys05_fidelity_ladder_maps_to_core_levels() -> None:
    assert AeroelasticFidelity.SCREENING.core_level() is FidelityLevel.ANALYTICAL
    assert AeroelasticFidelity.REDUCED.core_level() is FidelityLevel.MRF
    assert AeroelasticFidelity.HARMONIC.core_level() is FidelityLevel.HARMONIC_RESPONSE
    assert AeroelasticFidelity.TRANSIENT_FSI.core_level() is FidelityLevel.TRANSIENT


# -- B. linear/modal coupling -------------------------------------------------


def test_advphys05_pressure_projection_generalized_forces() -> None:
    result = map_pressure_to_modes(_field(), _basis())
    forces = {force.mode_id: force for force in result.generalized_forces}
    assert forces["bend-1"].force_n == pytest.approx(3.0)
    assert forces["bend-2"].force_n == pytest.approx(-1.0)
    assert forces["bend-1"].participation == pytest.approx(0.75)
    assert forces["bend-2"].participation == pytest.approx(0.25)
    assert result.total_force_n == pytest.approx(3.0)
    assert result.resultant_n == pytest.approx((0.0, 3.0, 0.0))
    assert result.dominant_mode_id == "bend-1"
    assert result.fidelity is AeroelasticFidelity.REDUCED


def test_advphys05_projection_rejects_sample_mismatch() -> None:
    basis = ModalBasis(
        "short",
        (StructuralMode("m", 5.0, 0.01, 1.0, ((0.0, 1.0, 0.0),)),),
    )
    with pytest.raises(AeroelasticError):
        map_pressure_to_modes(_field(), basis)


def test_advphys05_order_matching_triggers_and_clears() -> None:
    basis = _basis()
    near = match_excitation_to_modes(
        basis,
        force_lines=(ForcingLine(source="r", order=1.0, speed_dependence="order"),),
        speed_rpm=600.0,
    )
    assert near.state == "triggered"
    assert near.minima_hz == pytest.approx(0.0)
    far = match_excitation_to_modes(
        basis,
        force_lines=(ForcingLine(source="r", order=5.0, speed_dependence="order"),),
        speed_rpm=600.0,
    )
    assert far.state == "clear"


def test_advphys05_modal_resonance_escalates() -> None:
    report = assess_modal_resonance(
        _basis(),
        excitations=(Excitation(name="rotor-order", frequency_hz=10.0),),
        current_fidelity=AeroelasticFidelity.SCREENING,
    )
    assert report.escalation_required is True
    assert report.required_fidelity is FidelityLevel.HARMONIC_RESPONSE


# -- C. flutter / stability ---------------------------------------------------


def test_advphys05_stability_is_stable_then_unstable() -> None:
    system = _section()[0].to_system()
    low = evaluate_stability(system, speed_m_s=1.0)
    high = evaluate_stability(system, speed_m_s=60.0)
    assert low.stable is True
    assert high.flutter is True
    assert high.max_growth_rate_1_s > 0.0


def test_advphys05_critical_speed_interpolated() -> None:
    section, payload = _section()
    curve = build_stability_curve(
        system=section.to_system(), speeds_m_s=tuple(payload["speeds_m_s"])
    )
    boundary = curve.boundary
    assert boundary.critical_speed_m_s is not None
    assert 35.0 < boundary.critical_speed_m_s < 42.0
    assert boundary.critical_frequency_hz is not None
    assert 8.0 < boundary.critical_frequency_hz < 12.0
    assert boundary.method == "quasi-steady-damping-crossing"


def test_advphys05_stable_curve_has_no_critical_speed() -> None:
    system = _section()[0].to_system()
    curve = build_stability_curve(system=system, speeds_m_s=(1.0, 11.0, 21.0))
    assert curve.boundary.critical_speed_m_s is None
    assert curve.unstable is False


def test_advphys05_escalation_ladder_states() -> None:
    system = _section()[0].to_system()
    triggered = build_stability_curve(system=system, speeds_m_s=(1.0, 61.0))
    decision = assess_flutter_escalation(triggered)
    assert decision.state == "triggered"
    assert decision.required_fidelity is AeroelasticFidelity.TRANSIENT_FSI
    assert decision.required_capability == "precice-fsi"

    near = build_stability_curve(system=system, speeds_m_s=(31.0, 36.0))
    watch = assess_flutter_escalation(near, policy=None)
    assert watch.state == "clear"

    from aeroworkbench_aeroelasticity import FlutterEscalationPolicy

    watched = assess_flutter_escalation(
        near, policy=FlutterEscalationPolicy(warning_damping_margin=0.2)
    )
    assert watched.state == "watch"
    assert watched.required_capability == "pk-flutter"


def test_advphys05_aerodynamic_damping_scales_with_speed() -> None:
    system = _section()[0].to_system()
    slow = aerodynamic_damping_estimate(system, speed_m_s=10.0)
    fast = aerodynamic_damping_estimate(system, speed_m_s=20.0)
    assert fast.per_dof_damping_n_s_m[0] == pytest.approx(2.0 * slow.per_dof_damping_n_s_m[0])
    assert abs(fast.per_dof_damping_n_s_m[1]) > abs(slow.per_dof_damping_n_s_m[1])


def test_advphys05_native_flutter_seams_fail_closed() -> None:
    system = _section()[0].to_system()
    with pytest.raises(AeroelasticCapabilityUnavailable):
        solve_pk_flutter(system, speeds_m_s=(1.0,))
    with pytest.raises(AeroelasticCapabilityUnavailable):
        solve_transient_fsi(system, speed_m_s=1.0)


# -- D. forced response -------------------------------------------------------


def test_advphys05_resonance_amplification_matches_damping() -> None:
    basis = _basis()
    force = HarmonicForce("bend-1", 10.0, 100.0)
    result = evaluate_harmonic_response(basis, (force,))
    response = result.responses[0]
    assert response.amplification == pytest.approx(1.0 / (2.0 * 0.02))
    assert response.excitation_frequency_hz == pytest.approx(10.0)
    assert result.peak_mode_id == "bend-1"


def test_advphys05_rotating_order_frequency_uses_shared_forcing() -> None:
    line = ForcingLine(source="rotor", order=3.0, amplitude=50.0, speed_dependence="order")
    force = rotating_order_force(line, mode_id="bend-1", speed_rpm=3000.0)
    assert force.frequency_hz == pytest.approx(3.0 * 3000.0 / 60.0)
    assert force.generalized_force_n == pytest.approx(50.0)
    assert force.order == pytest.approx(3.0)


def test_advphys05_pressure_spectrum_and_actuator_forces() -> None:
    spectrum = pressure_spectrum_forces(
        mode_id="bend-1",
        mode_shape_norm=1.0,
        area_m2=0.01,
        lines=((5.0, 200.0), (10.0, 100.0)),
    )
    assert len(spectrum) == 2
    assert spectrum[0].generalized_force_n == pytest.approx(2.0)
    actuator = actuator_force(mode_id="bend-1", frequency_hz=7.0, generalized_force_n=3.0)
    assert actuator.source == "actuator"
    assert actuator.generalized_force_n == pytest.approx(3.0)


def test_advphys05_forced_response_rejects_unknown_mode() -> None:
    with pytest.raises(AeroelasticError):
        evaluate_harmonic_response(_basis(), (HarmonicForce("missing", 10.0, 1.0),))


# -- E. mistuning / cyclic ----------------------------------------------------


def test_advphys05_mistuning_localizes_modes() -> None:
    tuned = analyze_cyclic_structure(
        CyclicStructureSpec("tuned", 6, 1.0, 1.0e6, 1.0e5)
    )
    payload = _fixture("cyclic_rotor.json")
    mistuned = analyze_cyclic_structure(
        CyclicStructureSpec(
            payload["structure_id"],
            payload["sector_count"],
            payload["sector_mass_kg"],
            payload["sector_stiffness_n_m"],
            payload["inter_sector_coupling_n_m"],
            tuple(payload["mistuning"]),
        )
    )
    assert mistuned.mistuned is True
    assert tuned.mistuned is False
    assert mistuned.max_localization_factor > tuned.max_localization_factor
    assert all(freq > 0.0 for freq in mistuned.frequencies_hz())
    assert mistuned.frequency_split_hz > 0.0


def test_advphys05_localization_factor_extended_vs_localized() -> None:
    extended = (0.5, 0.5, 0.5, 0.5)
    localized = (1.0, 0.0, 0.0, 0.0)
    assert localization_factor(extended) == pytest.approx(0.25)
    assert localization_factor(localized) == pytest.approx(1.0)


def test_advphys05_sector_to_full_mapping() -> None:
    mapping = sector_to_full_mapping(sector_count=3, dof_per_sector=2)
    assert mapping == ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1))


def test_advphys05_mistuning_length_mismatch_fails_closed() -> None:
    with pytest.raises(AeroelasticError):
        CyclicStructureSpec("bad", 4, 1.0, 1.0e6, 1.0e5, (0.1, 0.2))


# -- F. gust / dynamic loads --------------------------------------------------


def test_advphys05_discrete_gust_load_matches_quasi_steady() -> None:
    payload = _fixture("gust.json")
    gust = AtmosphericGust(
        payload["discrete"]["gust_id"],
        GustKind(payload["discrete"]["kind"]),
        payload["discrete"]["design_gust_velocity_m_s"],
        gradient_distance_m=payload["discrete"]["gradient_distance_m"],
    )
    result = evaluate_discrete_gust(
        gust,
        airspeed_m_s=payload["airspeed_m_s"],
        density_kg_m3=payload["density_kg_m3"],
        wing_area_m2=payload["wing_area_m2"],
        lift_curve_slope_per_rad=payload["lift_curve_slope_per_rad"],
        mass_kg=payload["mass_kg"],
    )
    q_dyn = 0.5 * payload["density_kg_m3"] * payload["airspeed_m_s"] ** 2
    expected = (
        q_dyn
        * payload["wing_area_m2"]
        * payload["lift_curve_slope_per_rad"]
        * (payload["discrete"]["design_gust_velocity_m_s"] / payload["airspeed_m_s"])
    )
    assert result.load_increment_n == pytest.approx(expected)
    assert result.load_factor_increment == pytest.approx(expected / (payload["mass_kg"] * 9.80665))
    assert result.fidelity is AeroelasticFidelity.SCREENING


def test_advphys05_continuous_gust_and_dryden_psd() -> None:
    payload = _fixture("gust.json")
    continuous = payload["continuous"]
    gust = AtmosphericGust(
        continuous["gust_id"],
        GustKind(continuous["kind"]),
        continuous["design_gust_velocity_m_s"],
        scale_length_m=continuous["scale_length_m"],
        turbulence_sigma_m_s=continuous["turbulence_sigma_m_s"],
    )
    result = evaluate_continuous_gust(
        gust,
        airspeed_m_s=payload["airspeed_m_s"],
        density_kg_m3=payload["density_kg_m3"],
        wing_area_m2=payload["wing_area_m2"],
        lift_curve_slope_per_rad=payload["lift_curve_slope_per_rad"],
        mass_kg=payload["mass_kg"],
    )
    assert result.load_increment_n > 0.0
    low = dryden_psd_m2_s(
        kind=GustKind.CONTINUOUS_DRYDEN,
        airspeed_m_s=200.0,
        sigma_m_s=3.0,
        scale_length_m=500.0,
        frequency_hz=0.1,
    )
    high = dryden_psd_m2_s(
        kind=GustKind.CONTINUOUS_DRYDEN,
        airspeed_m_s=200.0,
        sigma_m_s=3.0,
        scale_length_m=500.0,
        frequency_hz=5.0,
    )
    assert low > high > 0.0


def test_advphys05_discrete_gust_rejects_continuous_kind() -> None:
    continuous = AtmosphericGust(
        "c", GustKind.CONTINUOUS_DRYDEN, 5.0, scale_length_m=500.0
    )
    with pytest.raises(AeroelasticError):
        evaluate_discrete_gust(
            continuous,
            airspeed_m_s=100.0,
            density_kg_m3=1.225,
            wing_area_m2=30.0,
            lift_curve_slope_per_rad=6.283185307179586,
            mass_kg=5000.0,
        )


def test_advphys05_gust_payload_is_structural_ready() -> None:
    payload = _fixture("gust.json")
    gust = AtmosphericGust(
        payload["discrete"]["gust_id"],
        GustKind(payload["discrete"]["kind"]),
        payload["discrete"]["design_gust_velocity_m_s"],
        gradient_distance_m=payload["discrete"]["gradient_distance_m"],
    )
    result = evaluate_discrete_gust(
        gust,
        airspeed_m_s=payload["airspeed_m_s"],
        density_kg_m3=payload["density_kg_m3"],
        wing_area_m2=payload["wing_area_m2"],
        lift_curve_slope_per_rad=payload["lift_curve_slope_per_rad"],
        mass_kg=payload["mass_kg"],
    )
    assert set(result.dynamic_load_payload()) == {
        "load_increment_n",
        "load_factor_increment",
        "peak_gust_velocity_m_s",
    }


# -- G. contact / rub ---------------------------------------------------------


def test_advphys05_open_clearance_has_no_contact() -> None:
    result = evaluate_contact_event(RubContactSpec("open", 1.0e-4, 5.0e-5, 1.0e7))
    assert result.closed is False
    assert result.contact_force_n == pytest.approx(0.0)
    assert result.escalation_required is False


def test_advphys05_closed_contact_friction_and_heat() -> None:
    spec = RubContactSpec(
        "rub",
        clearance_m=1.0e-4,
        relative_displacement_m=3.0e-4,
        contact_stiffness_n_m=1.0e7,
        friction_coefficient=0.3,
        sliding_speed_m_s=5.0,
        allowable_contact_force_n=1000.0,
    )
    result = evaluate_contact_event(spec)
    assert result.closed is True
    assert result.penetration_m == pytest.approx(2.0e-4)
    assert result.contact_force_n == pytest.approx(2000.0)
    assert result.friction_force_n == pytest.approx(600.0)
    assert result.rub_heat_generation_w == pytest.approx(3000.0)
    assert result.escalation_required is True
    assert result.required_capability == "contact-fea"


def test_advphys05_native_contact_fails_closed() -> None:
    with pytest.raises(AeroelasticCapabilityUnavailable):
        solve_native_contact(RubContactSpec("rub", 1.0e-4, 3.0e-4, 1.0e7))


# -- H. participants / capabilities ------------------------------------------


def test_advphys05_participants_cover_all_capabilities() -> None:
    ids = participant_ids()
    for expected in (
        "modal-coupling",
        "flutter-stability",
        "forced-response",
        "mistuning-cyclic",
        "gust-load",
        "contact-rub",
    ):
        assert expected in ids
    assert len(AEROELASTIC_PARTICIPANTS) == len(ids)


def test_advphys05_participant_ports_route_to_targets() -> None:
    flutter = next(
        participant
        for participant in AEROELASTIC_PARTICIPANTS
        if participant.participant_id == "flutter-stability"
    )
    targets = {port.target for port in flutter.outputs}
    assert targets == {"stability"}
    assert "critical_speed_m_s" in flutter.port_names()


def test_advphys05_native_capabilities_are_gated() -> None:
    states = participant_native_states()
    assert states
    assert all(state["state"] == "unavailable" for state in states)
    with pytest.raises(AeroelasticCapabilityUnavailable):
        solve_native_contact(RubContactSpec("rub", 1.0e-4, 3.0e-4, 1.0e7))
