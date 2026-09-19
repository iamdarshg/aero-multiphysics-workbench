"""ADV-PHYS 02: generic unshrouded/open/single/coaxial propulsor workflows.

These tests drive the generic propulsor participants from typed, deterministic
fixtures: architecture and placement, real propeller/open-rotor CAD, low-cost
actuator-disk and blade-element momentum screening, a capability-gated native
reduced-wake/CFD seam, airframe installation coupling, and controls/limits.
Every result carries source/fidelity/units/validity/input-hash/software-
identity/provenance; native capability and declared limits fail closed and no
solver output is fabricated.
"""

from __future__ import annotations

import json
from math import pi, sqrt
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_propulsors import (
    NATIVE_LEVELS,
    PROPULSOR_PARTICIPANTS,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    ActuatorDiskResult,
    AeroFidelity,
    BladeStation,
    CapabilityUnavailable,
    Installation,
    InstallationFrame,
    LimitExceeded,
    PropellerGeometry,
    PropulsorArchitecture,
    PropulsorConstraints,
    PropulsorError,
    RotorSpec,
    SpanSection,
    SpinnerGeometry,
    Validity,
    apply_collective_schedule,
    architecture_from_payload,
    architecture_hash,
    architecture_provenance,
    blade_passing_frequency_hz,
    check_constraints,
    coaxial_coupling,
    coaxial_spacing_ok,
    effective_inflow,
    evaluate_actuator_disk,
    evaluate_coaxial_pair,
    evaluate_rotor,
    installed_loads,
    native_capability,
    participant_ids,
    promote_to_native,
    propulsor_participants,
    require_native,
    resonance_margin,
    rotor_design_space,
    rotor_spec_from_geometry,
    slipstream_field,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "propulsors"

_KNOWN_UNITS = frozenset(
    {"N", "N*m", "W", "m/s", "m2", "m", "deg", "dimensionless", "rpm", "s", "kg/m3"}
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _architecture(document: dict[str, Any]) -> PropulsorArchitecture:
    return architecture_from_payload(document["architecture"])


def _spinner(payload: dict[str, Any] | None) -> SpinnerGeometry | None:
    if payload is None:
        return None
    return SpinnerGeometry(
        nose_radius_m=payload["noseRadiusM"],
        nose_length_m=payload["noseLengthM"],
        hub_radius_m=payload["hubRadiusM"],
        shaft_radius_m=payload["shaftRadiusM"],
    )


def _geometry(document: dict[str, Any], rotor_id: str) -> PropellerGeometry:
    architecture = _architecture(document)
    rotor = architecture.rotor(rotor_id)
    payload = document["geometry"][rotor_id]
    sections = tuple(
        SpanSection(
            radius_fraction=item["radiusFraction"],
            chord_m=item["chordM"],
            twist_deg=item["twistDeg"],
            sweep_m=item.get("sweepM", 0.0),
            rake_m=item.get("rakeM", 0.0),
            thickness_ratio=item.get("thicknessRatio", 0.08),
            camber_ratio=item.get("camberRatio", 0.0),
            camber_family=item.get("camberFamily", "circular_arc"),
            thickness_family=item.get("thicknessFamily", "naca4"),
        )
        for item in payload["sections"]
    )
    return PropellerGeometry(
        rotor_id=rotor_id,
        blade_count=rotor.blade_count,
        tip_radius_m=rotor.tip_radius_m,
        hub_radius_m=rotor.hub_radius_m,
        sections=sections,
        pitch_axis_fraction=payload.get("pitchAxisFraction", 0.25),
        spinner=_spinner(payload.get("spinner")) or architecture.spinner,
        coaxial=payload.get("coaxial", False),
        axial_spacing_m=payload.get("axialSpacingM"),
        axial_offset_m=payload.get("axialOffsetM", 0.0),
        shroud_state=payload.get("shroudState", "unshrouded"),
        root_fillet_m=payload.get("rootFilletM", 0.002),
        material_ref=rotor.material_ref,
        architecture_id=architecture.architecture_id,
    )


def _inflow(document: dict[str, Any]) -> Any:
    from aeroworkbench_propulsors import Inflow

    state = document["inflow"]
    return Inflow(
        axial_velocity_m_s=state["axialVelocityMS"],
        density_kg_m3=state["densityKgM3"],
        speed_of_sound_m_s=state["speedOfSoundMS"],
    )


def _rotor(document: dict[str, Any], rotor_id: str) -> RotorSpec:
    architecture = _architecture(document)
    declaration = architecture.rotor(rotor_id)
    return rotor_spec_from_geometry(
        _geometry(document, rotor_id),
        rpm=declaration.rpm,
        direction=declaration.direction,
        shaft_id=declaration.shaft_id,
        collective_pitch_deg=declaration.collective_pitch_deg,
    )


# -- A. propulsor architecture contract --------------------------------------


def test_advphys02_single_tractor_architecture_has_no_duct_or_stator() -> None:
    architecture = _architecture(_fixture("single_tractor.json"))
    assert architecture.placement == "tractor"
    assert architecture.ducted is False
    assert architecture.stator is False
    assert architecture.number_of_rotors == 1
    assert architecture.is_contra_rotating is False
    rotor = architecture.rotor("prop-front")
    assert rotor.blade_count == 4
    assert rotor.direction == "clockwise"
    assert architecture.shaft(rotor.shaft_id).kind == "independent"
    assert architecture.spinner is not None


def test_advphys02_architecture_round_trips_and_hash_is_deterministic() -> None:
    document = _fixture("single_tractor.json")
    first = _architecture(document)
    second = architecture_from_payload(first.canonical_payload())
    assert first.architecture_hash == second.architecture_hash
    assert len(first.architecture_hash) == 64
    assert architecture_hash(first) == first.architecture_hash


def test_advphys02_installation_frame_is_declared() -> None:
    architecture = _architecture(_fixture("single_tractor.json"))
    frame = architecture.installation_frame
    assert isinstance(frame, InstallationFrame)
    assert frame.body_ref == "vehicle-nose"
    assert frame.canonical_payload()["axis"] == [1.0, 0.0, 0.0]


def test_advphys02_coaxial_pair_requires_opposite_directions() -> None:
    document = _fixture("coaxial_contra_rotating.json")
    payload = document["architecture"]
    payload["rotors"][1]["direction"] = "clockwise"
    with pytest.raises(PropulsorError):
        architecture_from_payload(payload)


def test_advphys02_coaxial_pair_groups_are_explicit() -> None:
    architecture = _architecture(_fixture("coaxial_contra_rotating.json"))
    groups = architecture.coaxial_groups()
    assert set(groups) == {"coax-stack"}
    members = groups["coax-stack"]
    assert len(members) == 2
    assert {rotor.direction for rotor in members} == {"clockwise", "counterclockwise"}
    assert {rotor.shaft_id for rotor in members} == {"shaft-a", "shaft-b"}


def test_advphys02_shared_shaft_must_be_common() -> None:
    payload = _fixture("coaxial_contra_rotating.json")["architecture"]
    payload["rotors"][1]["shaftId"] = "shaft-a"
    with pytest.raises(PropulsorError):
        architecture_from_payload(payload)
    payload["shafts"][0]["kind"] = "common"
    payload["shafts"][0]["linkedShaftId"] = "shaft-b"
    payload["rotors"][1]["shaftId"] = "shaft-a"
    architecture = architecture_from_payload(payload)
    assert architecture.shaft("shaft-a").kind == "common"


def test_advphys02_geared_shaft_requires_ratio() -> None:
    from aeroworkbench_propulsors import ShaftDeclaration

    with pytest.raises(PropulsorError):
        ShaftDeclaration(shaft_id="g", kind="geared", linked_shaft_id="other", gear_ratio=None)
    shaft = ShaftDeclaration(shaft_id="g", kind="geared", linked_shaft_id="other", gear_ratio=2.0)
    assert shaft.gear_ratio == 2.0


def test_advphys02_cyclic_pitch_seam_is_optional() -> None:
    from aeroworkbench_propulsors import CyclicPitchSeam

    document = _fixture("single_tractor.json")
    payload = document["architecture"]
    payload["rotors"][0]["pitchControl"] = "cyclic"
    with pytest.raises(PropulsorError):
        architecture_from_payload(payload)
    payload["cyclic"] = {"amplitudeDeg": 4.0, "phaseDeg": 90.0}
    architecture = architecture_from_payload(payload)
    assert architecture.cyclic == CyclicPitchSeam(amplitude_deg=4.0, phase_deg=90.0)


def test_advphys02_architecture_provenance_is_analytical_and_hashed() -> None:
    provenance = architecture_provenance(_architecture(_fixture("single_tractor.json")))
    assert provenance.source is ResultSource.ANALYTICAL
    assert len(provenance.inputs_hash) == 64
    assert provenance.model_version == SOFTWARE_VERSION


# -- B. real propeller / open-rotor CAD --------------------------------------


def test_advphys02_geometry_produces_real_structured_bodies() -> None:
    geometry = _geometry(_fixture("single_tractor.json"), "prop-front")
    row = geometry.blade_row()
    assert row.blade_count == 4
    assert row.tip_radius_mm == pytest.approx(1000.0)
    assert len(geometry.sections) == 3
    bodies = geometry.bodies()
    assert len(bodies) >= row.blade_count
    roles = {role for body in bodies for role in body.roles()}
    assert "blade.pressure" in roles
    assert "blade.suction" in roles


def test_advphys02_geometry_digest_tracks_chord_change() -> None:
    architecture = _architecture(_fixture("single_tractor.json"))
    base = _geometry(_fixture("single_tractor.json"), "prop-front")
    changed = PropellerGeometry(
        rotor_id=base.rotor_id,
        blade_count=base.blade_count,
        tip_radius_m=base.tip_radius_m,
        hub_radius_m=base.hub_radius_m,
        sections=(
            SpanSection(radius_fraction=0.2, chord_m=0.20, twist_deg=28.0),
            *base.sections[1:],
        ),
    )
    assert base.geometry_digest() != changed.geometry_digest()
    assert architecture.architecture_id == "fixture-single-tractor"


def test_advphys02_spanwise_distributions_are_exposed() -> None:
    geometry = _geometry(_fixture("open_rotor_propfan.json"), "or-front")
    assert geometry.blade_count == 8
    assert any(section.sweep_m > 0.0 for section in geometry.sections)
    assert any(section.rake_m != 0.0 for section in geometry.sections)
    parameters = dict((name, value) for name, value, _unit in geometry.parameters())
    assert parameters[f"{geometry.rotor_id}.tipRadius"] == pytest.approx(1.2)


def test_advphys02_spinner_and_hub_surfaces_are_present() -> None:
    geometry = _geometry(_fixture("single_tractor.json"), "prop-front")
    roles = {role for body in geometry.bodies() for role in body.roles()}
    assert {"spinner", "hub"}.issubset(roles)


def test_advphys02_coaxial_spacing_clearance_check() -> None:
    document = _fixture("coaxial_contra_rotating.json")
    front = _geometry(document, "coax-front")
    rear = _geometry(document, "coax-rear")
    assert coaxial_spacing_ok(front, rear, minimum_spacing_m=0.1) is True
    assert coaxial_spacing_ok(front, rear, minimum_spacing_m=0.5) is False


def test_advphys02_native_brep_receipts_or_fail_closed() -> None:
    geometry = _geometry(_fixture("single_tractor.json"), "prop-front")
    try:
        receipts = geometry.brep_receipts()
    except CapabilityUnavailable:
        return
    assert receipts
    for receipt in receipts.values():
        assert "faceCount" in receipt
        assert receipt["volumeMm3"] >= 0.0


def test_advphys02_geometry_validates_without_blocking_diagnostics() -> None:
    from aeroworkbench_turbomachinery.geometry import blocking

    diagnostics = _geometry(_fixture("single_tractor.json"), "prop-front").validate()
    assert blocking(diagnostics) == ()


# -- C. low-cost aerodynamic fidelity ----------------------------------------


def test_advphys02_actuator_disk_ideal_induced_velocity() -> None:
    result = evaluate_actuator_disk(
        10.0,
        5000.0,
        _inflow(_fixture("single_tractor.json")),
        rotor_id="dummy",
    )
    assert isinstance(result, ActuatorDiskResult)
    expected_static = sqrt(5000.0 / (2.0 * 1.0 * 10.0))
    assert result.induced_velocity_m_s < expected_static
    assert result.validity.passed is True
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_advphys02_bemt_screening_has_positive_thrust_and_coefficients() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    result = evaluate_rotor(rotor, _inflow(document))
    assert result.thrust_n > 0.0
    assert result.power_w > 0.0
    assert result.fidelity == AeroFidelity.BLADE_ELEMENT_MOMENTUM.value
    assert result.power_coefficient == pytest.approx(2.0 * pi * result.torque_coefficient, rel=1e-9)
    assert result.propulsive_efficiency == pytest.approx(
        result.advance_ratio * result.thrust_coefficient / result.power_coefficient, rel=1e-9
    )
    assert result.propulsive_efficiency > 0.0
    assert result.tip_mach < 0.9
    assert result.validity.passed is True


def test_advphys02_station_loads_record_swirl_and_induction() -> None:
    document = _fixture("single_tractor.json")
    result = evaluate_rotor(_rotor(document, "prop-front"), _inflow(document))
    assert len(result.station_loads) == 3
    assert any(load.thrust_n > 0.0 for load in result.station_loads)
    assert sum(load.thrust_n for load in result.station_loads) == pytest.approx(result.thrust_n)
    assert all(load.tip_loss_factor <= 1.0 for load in result.station_loads)
    assert result.induced_velocity_m_s > 0.0


def test_advphys02_static_operation_produces_thrust_with_zero_efficiency() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    from aeroworkbench_propulsors import Inflow

    static = evaluate_rotor(rotor, Inflow(axial_velocity_m_s=0.0, density_kg_m3=1.0))
    assert static.thrust_n > 0.0
    assert static.advance_ratio == 0.0
    assert static.propulsive_efficiency == 0.0
    assert static.induced_velocity_m_s > 0.0


def test_advphys02_tip_correction_changes_the_solution() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    corrected = evaluate_rotor(rotor, _inflow(document), tip_loss_correction=True)
    uncorrected = evaluate_rotor(rotor, _inflow(document), tip_loss_correction=False)
    assert corrected.thrust_n != pytest.approx(uncorrected.thrust_n, rel=1e-9)
    assert all(load.tip_loss_factor <= 1.0 for load in corrected.station_loads)


def test_advphys02_high_rpm_fails_tip_mach_validity_check() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    from dataclasses import replace as _replace

    fast = _replace(rotor, rpm=8000.0)
    result = evaluate_rotor(fast, _inflow(document))
    assert result.tip_mach > 0.9
    assert result.validity.passed is False
    assert result.validity.checks["tip_mach_below_limit"] is False


def test_advphys02_coaxial_coupling_is_explicit_and_rear_is_not_independent() -> None:
    document = _fixture("coaxial_contra_rotating.json")
    front = _rotor(document, "coax-front")
    rear = _rotor(document, "coax-rear")
    inflow = _inflow(document)
    coupled = evaluate_coaxial_pair(front, rear, axial_spacing_m=0.25, inflow=inflow)
    assert coupled.coupling.downstream_axial_factor >= 1.0
    assert coupled.coupling.rear_axial_inflow_m_s > inflow.axial_velocity_m_s
    assert coupled.front.coupling == "coaxial-front"
    assert coupled.rear.coupling == "coaxial-rear"
    independent = evaluate_rotor(rear, inflow)
    assert coupled.rear.thrust_n != pytest.approx(independent.thrust_n, rel=1e-6)
    assert coupled.total_thrust_n == pytest.approx(coupled.front.thrust_n + coupled.rear.thrust_n)


def test_advphys02_coaxial_coupling_decays_with_spacing() -> None:
    document = _fixture("coaxial_contra_rotating.json")
    front = _rotor(document, "coax-front")
    rear = _rotor(document, "coax-rear")
    inflow = _inflow(document)
    front_result = evaluate_rotor(front, inflow)
    near = coaxial_coupling(front, rear, front_result, axial_spacing_m=0.05, inflow=inflow)
    far = coaxial_coupling(front, rear, front_result, axial_spacing_m=2.0, inflow=inflow)
    assert near.swirl_fraction > far.swirl_fraction
    assert far.downstream_axial_factor > near.downstream_axial_factor


def test_advphys02_coaxial_same_direction_fails_closed() -> None:
    document = _fixture("coaxial_contra_rotating.json")
    front = _rotor(document, "coax-front")
    rear = _rotor(document, "coax-rear")
    from dataclasses import replace as _replace

    with pytest.raises(PropulsorError):
        evaluate_coaxial_pair(
            front,
            _replace(rear, direction=front.direction),
            axial_spacing_m=0.25,
            inflow=_inflow(document),
        )


def test_advphys02_native_aero_fidelity_fails_closed_in_screening_solver() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    with pytest.raises(CapabilityUnavailable):
        evaluate_rotor(rotor, _inflow(document), fidelity=AeroFidelity.ROTATING_FRAME_CFD)


# -- D. higher-fidelity native seam ------------------------------------------


class _FakeWakeBackend:
    backend_id = "fake-free-wake"
    software_version = "2.1.0"

    def solve(self, request: Any) -> dict[str, float]:
        scale = 1.0 if request.level is AeroFidelity.LIFTING_LINE else 1.1
        return {
            "thrust_n": 1234.5 * scale,
            "torque_n_m": 321.0 * scale,
            "power_w": 40000.0 * scale,
            "induced_velocity_m_s": 8.0,
        }


def test_advphys02_native_seam_fails_closed_without_backend() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    inflow = _inflow(document)
    for level in NATIVE_LEVELS:
        with pytest.raises(CapabilityUnavailable):
            promote_to_native(rotor, inflow, level=level, run_id="r1")
    for level in NATIVE_LEVELS:
        with pytest.raises(CapabilityUnavailable):
            require_native(level)
        assert native_capability(level).state == "unavailable"


def test_advphys02_native_seam_uses_wired_backend_identity() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    result = promote_to_native(
        rotor,
        _inflow(document),
        level=AeroFidelity.LIFTING_LINE,
        run_id="wake-run-7",
        backend=_FakeWakeBackend(),
    )
    assert result.thrust_n == pytest.approx(1234.5)
    assert result.solver_name == "fake-free-wake"
    assert result.solver_version == "2.1.0"
    assert result.run_id == "wake-run-7"
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    assert result.provenance.inputs_hash != ""
    assert len(result.provenance.inputs_hash) == 64


def test_advphys02_native_promotion_rejects_screening_level() -> None:
    document = _fixture("single_tractor.json")
    with pytest.raises(PropulsorError):
        promote_to_native(
            _rotor(document, "prop-front"),
            _inflow(document),
            level=AeroFidelity.BLADE_ELEMENT_MOMENTUM,
            run_id="x",
        )


# -- E. installation coupling -------------------------------------------------


def test_advphys02_effective_inflow_applies_distortion_and_yaw() -> None:
    document = _fixture("single_tractor.json")
    free = _inflow(document)
    installation = Installation(
        installation_id="inst-1",
        yaw_deg=6.0,
        inflow_distortion_deg=4.0,
        interference_velocity_m_s=2.0,
    )
    installed = effective_inflow(installation, free)
    assert installed.total_inflow_angle_deg == pytest.approx(10.0)
    assert installed.axial_velocity_m_s < free.axial_velocity_m_s + 2.0
    assert installed.distortion_factor < 1.0


def test_advphys02_pusher_ingestion_adds_upstream_wake() -> None:
    document = _fixture("pusher_propeller.json")
    free = _inflow(document)
    pusher = Installation(
        installation_id="pusher",
        pusher_ingestion_factor=0.5,
        upstream_wake_velocity_m_s=10.0,
    )
    installed = effective_inflow(pusher, free)
    assert installed.ingested_wake_m_s == pytest.approx(5.0)
    assert installed.axial_velocity_m_s == pytest.approx(free.axial_velocity_m_s + 5.0)


def test_advphys02_slipstream_field_reports_jet_and_contraction() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    result = evaluate_rotor(rotor, _inflow(document))
    field = slipstream_field(
        result, Installation(installation_id="inst-2"), rotor=rotor, axial_stations_m=(0.1, 0.5)
    )
    assert field.jet_velocity_m_s == pytest.approx(
        result.axial_velocity_m_s + 2.0 * result.induced_velocity_m_s
    )
    assert 0.0 <= field.contraction_ratio <= 1.0
    assert field.swirl_velocity_m_s > 0.0
    for unit in field.units().values():
        assert unit in _KNOWN_UNITS


def test_advphys02_installed_loads_transfer_thrust_torque_and_moment() -> None:
    document = _fixture("single_tractor.json")
    result = evaluate_rotor(_rotor(document, "prop-front"), _inflow(document))
    loads = installed_loads(
        result, Installation(installation_id="inst-3", yaw_deg=8.0), thrust_arm_m=1.5
    )
    assert loads.thrust_n > 0.0
    assert loads.normal_force_n > 0.0
    assert loads.pitching_moment_n_m == pytest.approx(loads.normal_force_n * 1.5)
    assert loads.torque_n_m == pytest.approx(result.torque_n_m)
    assert loads.provenance.source is ResultSource.ANALYTICAL


# -- F. controls and constraints ---------------------------------------------


def test_advphys02_design_space_is_bounded_per_rotor() -> None:
    architecture = _architecture(_fixture("single_tractor.json"))
    space = rotor_design_space(architecture, "prop-front")
    assert "prop-front.bladeCount" in space.names()
    assert space.value("prop-front.collectivePitch") == pytest.approx(20.0)
    updated = space.with_value("prop-front.collectivePitch", 25.0)
    assert updated.value("prop-front.collectivePitch") == pytest.approx(25.0)
    with pytest.raises(PropulsorError):
        space.with_value("prop-front.collectivePitch", 999.0)


def test_advphys02_collective_schedule_interpolates() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    schedule = ((0.0, 24.0), (0.8, 18.0), (1.6, 12.0))
    assert apply_collective_schedule(rotor, schedule, 0.0).collective_pitch_deg == 24.0
    assert apply_collective_schedule(rotor, schedule, 0.4).collective_pitch_deg == pytest.approx(
        21.0
    )
    assert apply_collective_schedule(rotor, schedule, 5.0).collective_pitch_deg == 12.0


def test_advphys02_constraints_pass_within_limits() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    result = evaluate_rotor(rotor, _inflow(document))
    constraints = PropulsorConstraints(
        max_diameter_m=3.0,
        max_chord_m=0.25,
        max_rpm=2000.0,
        max_tip_mach=0.85,
        min_clearance_m=0.01,
    )
    report = check_constraints(rotor, result, constraints, clearance_m=0.05)
    assert report.passed is True
    assert report.violations == ()
    assert {"max_diameter", "max_rpm", "max_tip_mach"} <= set(report.checks)


def test_advphys02_constraints_fail_closed_on_diameter() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    result = evaluate_rotor(rotor, _inflow(document))
    constraints = PropulsorConstraints(max_diameter_m=1.0)
    with pytest.raises(LimitExceeded) as failed:
        check_constraints(rotor, result, constraints)
    assert "max_diameter" in failed.value.violations
    assert len(failed.value.provenance.inputs_hash) == 64


def test_advphys02_structural_resonance_margin_is_enforced() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    result = evaluate_rotor(rotor, _inflow(document))
    excitation = blade_passing_frequency_hz(rotor)
    assert excitation == pytest.approx(20.0 * 4.0)
    assert resonance_margin(excitation * 1.5, excitation) == pytest.approx(0.5)
    constraints = PropulsorConstraints(resonance_margin_fraction=0.15)
    with pytest.raises(LimitExceeded) as failed:
        check_constraints(
            rotor, result, constraints, blade_natural_frequency_hz=excitation * 1.01
        )
    assert "structural_resonance_margin" in failed.value.violations


def test_advphys02_participants_declare_shared_ports_and_native_requirements() -> None:
    ids = participant_ids()
    assert "propulsor-rotor" in ids
    assert "propulsor-blade-row" in ids
    assert "propulsor-installation" in ids
    assert len(propulsor_participants()) == len(PROPULSOR_PARTICIPANTS)
    rotor = next(p for p in PROPULSOR_PARTICIPANTS if p.participant_id == "propulsor-rotor")
    targets = {port.target for port in rotor.outputs}
    assert {"aerodynamics", "rotordynamic", "propulsion"} <= targets
    assert rotor.native_requirement == "lifting-line-free-wake"


# -- contract: provenance / fidelity / units / validity / determinism --------


def test_advphys02_result_carries_full_contract() -> None:
    document = _fixture("single_tractor.json")
    result = evaluate_rotor(_rotor(document, "prop-front"), _inflow(document))
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert len(result.provenance.inputs_hash) == 64
    assert result.provenance.model.startswith("propulsors.")
    assert result.provenance.model_version == SOFTWARE_VERSION
    assert SOFTWARE_IDENTITY == "aeroworkbench-propulsors"
    assert isinstance(result.validity, Validity)
    assert result.validity.detail
    for unit in result.units().values():
        assert unit in _KNOWN_UNITS


def test_advphys02_repeated_evaluation_is_deterministic() -> None:
    document = _fixture("single_tractor.json")
    rotor = _rotor(document, "prop-front")
    inflow = _inflow(document)
    first = evaluate_rotor(rotor, inflow)
    second = evaluate_rotor(rotor, inflow)
    assert first.provenance.inputs_hash == second.provenance.inputs_hash
    assert first.thrust_n == second.thrust_n
    assert first.torque_n_m == second.torque_n_m
    geometry = _geometry(document, "prop-front")
    assert geometry.geometry_digest() == _geometry(document, "prop-front").geometry_digest()


def test_advphys02_nonphysical_rotor_fails_closed() -> None:
    with pytest.raises(PropulsorError):
        RotorSpec(
            rotor_id="bad",
            blade_count=3,
            tip_radius_m=0.5,
            hub_radius_m=0.6,
            rpm=1000.0,
            direction="clockwise",
            shaft_id="s",
            stations=(BladeStation(radius_m=0.55, chord_m=0.1, twist_deg=10.0),),
        )


# -- G. verification fixtures -------------------------------------------------


def test_advphys02_fixture_single_tractor() -> None:
    document = _fixture("single_tractor.json")
    result = evaluate_rotor(_rotor(document, "prop-front"), _inflow(document))
    expect = document["expect"]
    assert (result.thrust_n > 0.0) is expect["thrustPositive"]
    assert (result.propulsive_efficiency > 0.0) is expect["efficiencyPositive"]
    assert (result.tip_mach < 0.9) is expect["tipMachBelowLimit"]


def test_advphys02_fixture_pusher_propeller() -> None:
    document = _fixture("pusher_propeller.json")
    architecture = _architecture(document)
    assert architecture.placement == "pusher"
    result = evaluate_rotor(_rotor(document, "prop-rear"), _inflow(document))
    assert (result.thrust_n > 0.0) is document["expect"]["thrustPositive"]


def test_advphys02_fixture_coaxial_contra_rotating() -> None:
    document = _fixture("coaxial_contra_rotating.json")
    front = _rotor(document, "coax-front")
    rear = _rotor(document, "coax-rear")
    coupled = evaluate_coaxial_pair(front, rear, axial_spacing_m=0.25, inflow=_inflow(document))
    expect = document["expect"]
    assert (front.direction != rear.direction) is expect["oppositeDirections"]
    assert (coupled.coupling.downstream_axial_factor >= 1.0) is expect["coupledInducedFlow"]
    assert (coupled.total_thrust_n > 0.0) is expect["totalThrustPositive"]


def test_advphys02_fixture_open_rotor_propfan_pair() -> None:
    document = _fixture("open_rotor_propfan.json")
    front_geometry = _geometry(document, "or-front")
    assert front_geometry.blade_count == 8
    coupling = evaluate_coaxial_pair(
        _rotor(document, "or-front"),
        _rotor(document, "or-rear"),
        axial_spacing_m=0.4,
        inflow=_inflow(document),
    )
    assert coupling.total_thrust_n > 0.0
    assert coupling.front.provenance.model_version == SOFTWARE_VERSION


def test_advphys02_fixture_ducted_rotor_shares_blade_contract() -> None:
    document = _fixture("ducted_rotor.json")
    architecture = _architecture(document)
    assert architecture.ducted is document["expect"]["ducted"]
    assert architecture.duct_geometry_ref == "duct-shared-geometry"
    geometry = _geometry(document, "ducted-rotor")
    assert geometry.shroud_state == "shrouded"
    row = geometry.blade_row()
    assert row.shroud_state == "shrouded"
    result = evaluate_rotor(_rotor(document, "ducted-rotor"), _inflow(document))
    assert (result.thrust_n > 0.0) is document["expect"]["thrustPositive"]
    assert result.provenance.source is ResultSource.ANALYTICAL
