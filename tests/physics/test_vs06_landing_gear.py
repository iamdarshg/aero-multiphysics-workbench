"""VS 06: landing gear, ground operations, and takeoff/landing dynamics.

All fixtures are tiny and deterministic: a tricycle gear, a skid gear, a runway,
and a point-mass ground model. Distances are integrated from thrust, drag, lift,
mass, rolling resistance, and braking; nothing is a stored heuristic and no
solver runs. Native ground-dynamics / structural requests fail closed.
"""

from __future__ import annotations

import json
from math import pi
from pathlib import Path

import pytest
from aeroworkbench_airframe import InertiaTensor, MassProperties, Quantity, Vec3
from aeroworkbench_durability import rainflow_count
from aeroworkbench_vehicle_systems.landing_gear import (
    BrakeSpec,
    CapabilityUnavailable,
    ClearancePoint,
    DragPolar,
    GearArchitecture,
    GearLegSpec,
    GearRole,
    GroundStabilityError,
    GroundVehicleModel,
    LandingGearError,
    LimitExceeded,
    LoadCaseKind,
    RunwaySpec,
    RunwaySurface,
    ShockAbsorberSpec,
    ThrustModel,
    WheelSpec,
    apply_ground_effect,
    check_clearance,
    check_ground_stability,
    evaluate_shock_stroke,
    export_load_cases,
    native_ground_dynamics_status,
    require_clearance,
    require_native_gear_structure,
    require_native_ground_dynamics,
    require_native_ground_effect,
    require_native_structural,
    require_stable_ground,
    simulate_landing,
    simulate_rejected_takeoff,
    simulate_takeoff,
    skid_gear,
    steer_angle_for_radius_rad,
    steering_turn_rate_rad_s,
    touchdown_load_case,
    tricycle_gear,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "vehicle_systems" / "landing_gear"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _wheel(wheel_id: str = "wheel") -> WheelSpec:
    spec = _load("gear_fixture.json")["wheel"]
    assert isinstance(spec, dict)
    return WheelSpec(
        wheel_id=wheel_id,
        radius=Quantity(spec["radius_m"], "m"),
        width=Quantity(spec["width_m"], "m"),
        mass=Quantity(spec["mass_kg"], "kg"),
        spin_inertia=Quantity(spec["spin_inertia_kg_m2"], "kg.m2"),
        rolling_resistance_coefficient=spec["rolling_resistance_coefficient"],
        max_brake_friction_coefficient=spec["max_brake_friction_coefficient"],
        cornering_stiffness_n_per_rad=spec["cornering_stiffness_n_per_rad"],
    )


def _brake() -> BrakeSpec:
    spec = _load("gear_fixture.json")["brake"]
    assert isinstance(spec, dict)
    return BrakeSpec(
        brake_id="brake",
        max_torque=Quantity(spec["max_torque_n_m"], "N.m"),
        friction_coefficient=spec["friction_coefficient"],
        anti_skid=spec["anti_skid"],
    )


def _shock(max_stroke_m: float = 0.35) -> ShockAbsorberSpec:
    spec = _load("gear_fixture.json")["shock"]
    assert isinstance(spec, dict)
    return ShockAbsorberSpec(
        absorber_id="main-shock",
        gas_charge_pressure=Quantity(spec["gas_charge_pressure_pa"], "Pa"),
        piston_area=Quantity(spec["piston_area_m2"], "m2"),
        initial_gas_length=Quantity(spec["initial_gas_length_m"], "m"),
        polytropic_index=spec["polytropic_index"],
        hydraulic_damping_coefficient=spec["hydraulic_damping_coefficient"],
        max_stroke=Quantity(max_stroke_m, "m"),
    )


def _leg(leg_id: str, role: GearRole, attachment: list[float], axle: list[float]) -> GearLegSpec:
    return GearLegSpec(
        leg_id=leg_id,
        role=role,
        attachment_point=Vec3(attachment[0], attachment[1], attachment[2], "m", "body"),
        axle_point=Vec3(axle[0], axle[1], axle[2], "m", "body"),
        wheel=_wheel(f"{leg_id}-wheel"),
        brake=_brake(),
        shock=_shock(),
    )


def _assembly():
    data = _load("gear_fixture.json")
    nose = _leg("nose", GearRole.NOSE, data["nose"]["attachment"], data["nose"]["axle"])
    mains = tuple(
        _leg(entry["leg_id"], GearRole.MAIN, entry["attachment"], entry["axle"])
        for entry in data["main"]
    )
    return tricycle_gear(assembly_id=data["assembly_id"], nose_leg=nose, main_legs=mains)


def _skid_assembly():
    left = GearLegSpec(
        leg_id="skid-left",
        role=GearRole.SKID,
        attachment_point=Vec3(0.0, -0.8, 0.4, "m", "body"),
        axle_point=Vec3(0.0, -0.8, 0.6, "m", "body"),
    )
    right = GearLegSpec(
        leg_id="skid-right",
        role=GearRole.SKID,
        attachment_point=Vec3(0.0, 0.8, 0.4, "m", "body"),
        axle_point=Vec3(0.0, 0.8, 0.6, "m", "body"),
    )
    forward = GearLegSpec(
        leg_id="skid-nose",
        role=GearRole.SKID,
        attachment_point=Vec3(1.4, 0.0, 0.4, "m", "body"),
        axle_point=Vec3(1.4, 0.0, 0.6, "m", "body"),
    )
    return skid_gear(assembly_id="fixture-skid", skid_legs=(forward, left, right))


def _runway(surface: str) -> RunwaySpec:
    data = _load("gear_fixture.json")["runway"]
    assert isinstance(data, dict)
    return RunwaySpec(
        runway_id=f"{surface}-runway",
        surface=RunwaySurface(surface),
        length_m=data["length_m"],
        slope_deg=data["slope_deg"],
    )


def _vehicle(**overrides: float) -> GroundVehicleModel:
    data = _load("scenario_fixture.json")["vehicle"]
    assert isinstance(data, dict)
    polar_data = data["polar"]
    assert isinstance(polar_data, dict)
    thrust_data = data["thrust"]
    assert isinstance(thrust_data, dict)
    return GroundVehicleModel(
        vehicle_id=data["vehicle_id"],
        mass_kg=overrides.get("mass_kg", data["mass_kg"]),
        polar=DragPolar(
            reference_area_m2=polar_data["reference_area_m2"],
            cl0=polar_data["cl0"],
            cl_alpha_per_rad=polar_data["cl_alpha_per_rad"],
            cd0=polar_data["cd0"],
            aspect_ratio=polar_data["aspect_ratio"],
            oswald_efficiency=polar_data["oswald_efficiency"],
        ),
        thrust=ThrustModel(
            static_thrust_n=overrides.get("static_thrust_n", thrust_data["static_thrust_n"]),
            lapse_per_m_s=overrides.get("lapse_per_m_s", thrust_data["lapse_per_m_s"]),
        ),
        cl_ground=data["cl_ground"],
        cl_max=data["cl_max"],
        rotation_alpha_rad=data["rotation_alpha_rad"],
        rotation_speed_m_s=data["rotation_speed_m_s"],
        screen_height_m=data["screen_height_m"],
        density_kg_m3=data["density_kg_m3"],
        gravity_m_s2=data["gravity_m_s2"],
    )


def _mass_props(mass_kg: float, cg_x: float) -> MassProperties:
    inertia = InertiaTensor(
        ixx=Quantity(1000.0, "kg.m2"),
        iyy=Quantity(5000.0, "kg.m2"),
        izz=Quantity(5000.0, "kg.m2"),
        ixy=Quantity(0.0, "kg.m2"),
        ixz=Quantity(0.0, "kg.m2"),
        iyz=Quantity(0.0, "kg.m2"),
        frame="body",
    )
    return MassProperties(
        mass=Quantity(mass_kg, "kg"),
        cg=Vec3(cg_x, 0.0, 0.25, "m", "body"),
        inertia=inertia,
    )


def test_fixture_files_load_and_are_stable() -> None:
    assert _load("gear_fixture.json") == _load("gear_fixture.json")
    assert _load("scenario_fixture.json")["vehicle"]["mass_kg"] == 1200.0


def test_tricycle_assembly_roles_and_hash() -> None:
    assembly = _assembly()
    assert assembly.architecture is GearArchitecture.TRICYCLE
    assert len(assembly.main_legs) == 2
    assert len(assembly.nose_legs) == 1
    assert len(assembly.content_hash) == 64
    assert assembly.content_hash == _assembly().content_hash
    contacts = assembly.contact_points()
    assert len(contacts) == 3
    assert all(contact.dimension == "length" for contact in contacts)


def test_skid_assembly_contract() -> None:
    assembly = _skid_assembly()
    assert assembly.architecture is GearArchitecture.SKID
    assert len(assembly.legs) == 3
    assert all(leg.role is GearRole.SKID for leg in assembly.legs)


def test_runway_surface_friction_ordering() -> None:
    dry = _runway("dry-concrete")
    ice = _runway("ice")
    assert dry.braking_friction_coefficient > ice.braking_friction_coefficient
    assert ice.rolling_resistance_coefficient < dry.rolling_resistance_coefficient


def test_takeoff_distance_emerges_from_force_balance() -> None:
    model = _vehicle()
    result = simulate_takeoff(model, runway=_runway("dry-concrete"))
    assert result.ground_roll_distance_m > 0.0
    assert result.air_distance_m > 0.0
    assert result.takeoff_distance_m == pytest.approx(
        result.ground_roll_distance_m + result.air_distance_m
    )
    lift = model.lift_n(result.liftoff_speed_m_s, model.liftoff_lift_coefficient())
    assert lift == pytest.approx(model.weight_n, rel=0.05)

    stronger = simulate_takeoff(_vehicle(static_thrust_n=12000.0), runway=_runway("dry-concrete"))
    heavier = simulate_takeoff(_vehicle(mass_kg=1600.0), runway=_runway("dry-concrete"))
    assert stronger.takeoff_distance_m < result.takeoff_distance_m
    assert heavier.takeoff_distance_m > result.takeoff_distance_m


def test_braking_and_runway_friction_alter_landing_distance() -> None:
    model = _vehicle()
    landing = _load("scenario_fixture.json")["landing"]
    assert isinstance(landing, dict)
    dry = simulate_landing(
        model,
        runway=_runway("dry-concrete"),
        approach_speed_m_s=landing["approach_speed_m_s"],
        touchdown_sink_rate_m_s=landing["sink_rate_m_s"],
        glide_slope_deg=landing["glide_slope_deg"],
    )
    ice = simulate_landing(
        model,
        runway=_runway("ice"),
        approach_speed_m_s=landing["approach_speed_m_s"],
        touchdown_sink_rate_m_s=landing["sink_rate_m_s"],
        glide_slope_deg=landing["glide_slope_deg"],
    )
    assert dry.air_distance_m == pytest.approx(ice.air_distance_m)
    assert dry.rollout_distance_m < ice.rollout_distance_m
    assert dry.landing_distance_m < ice.landing_distance_m


def test_rejected_takeoff_friction_alters_stop_distance() -> None:
    model = _vehicle()
    decision = _load("scenario_fixture.json")["takeoff"]["decision_speed_m_s"]
    dry = simulate_rejected_takeoff(
        model, runway=_runway("dry-concrete"), decision_speed_m_s=decision
    )
    ice = simulate_rejected_takeoff(model, runway=_runway("ice"), decision_speed_m_s=decision)
    assert dry.acceleration_distance_m == pytest.approx(
        ice.acceleration_distance_m, rel=0.05
    )
    assert dry.stopping_distance_m < ice.stopping_distance_m
    assert dry.rejected_distance_m < ice.rejected_distance_m


def test_shock_absorber_stroke_response_and_limit() -> None:
    spec = _shock()
    soft = evaluate_shock_stroke(spec, effective_mass_kg=800.0, sink_rate_m_s=2.0)
    hard = evaluate_shock_stroke(spec, effective_mass_kg=800.0, sink_rate_m_s=4.0)
    assert hard.peak_load_n > soft.peak_load_n
    assert hard.peak_stroke_m >= soft.peak_stroke_m
    assert soft.receipt.steps > 0
    assert soft.meta.fidelity.value == "ground-transient"
    with pytest.raises(LimitExceeded):
        evaluate_shock_stroke(_shock(max_stroke_m=0.02), effective_mass_kg=800.0, sink_rate_m_s=2.0)


def test_touchdown_loads_feed_structural_sizing_and_fail_closed() -> None:
    shock = evaluate_shock_stroke(_shock(), effective_mass_kg=800.0, sink_rate_m_s=2.0)
    case = touchdown_load_case(shock, gear_id="main-left")
    assert case.kind is LoadCaseKind.TOUCHDOWN
    assert case.vertical_force_n == pytest.approx(shock.peak_load_n)

    export = export_load_cases("fixture-aircraft", (case,))
    assert len(export.content_hash) == 64
    histories = export.durability_load_histories()
    assert histories[0].peak() == pytest.approx(case.resultant_force_n)
    assert rainflow_count(histories[0]).total_count() >= 1.0

    with pytest.raises(CapabilityUnavailable):
        require_native_structural()


def test_bad_gear_placement_or_cg_fails_stability() -> None:
    assembly = _assembly()
    good = check_ground_stability(assembly, _mass_props(1200.0, 0.0), cg_height_m=0.7)
    assert good.stable
    assert 0.05 <= good.nose_load_fraction <= 0.35
    require_stable_ground(assembly, good)

    aft = check_ground_stability(assembly, _mass_props(1200.0, -0.5), cg_height_m=0.7)
    assert not aft.stable
    with pytest.raises(GroundStabilityError):
        require_stable_ground(assembly, aft)

    forward = check_ground_stability(assembly, _mass_props(1200.0, 1.4), cg_height_m=0.7)
    assert not forward.stable


def test_clearance_tail_strike_and_prop_strike() -> None:
    assembly = _assembly()
    tail = ClearancePoint(
        point_id="tail", location=Vec3(-3.0, 0.0, 0.5, "m", "body"), required_clearance_m=0.1
    )
    prop = ClearancePoint(
        point_id="prop", location=Vec3(2.5, 0.0, 0.3, "m", "body"), required_clearance_m=0.1
    )
    low = check_clearance(assembly, (tail, prop), rotation_angle_rad=5.0 * pi / 180.0)
    assert low.passed
    high = check_clearance(assembly, (tail, prop), rotation_angle_rad=15.0 * pi / 180.0)
    assert not high.passed
    assert not {point.point_id: point for point in high.points}["tail"].passed
    with pytest.raises(LandingGearError):
        require_clearance(assembly, high)
    nose_down = check_clearance(assembly, (prop,), rotation_angle_rad=-15.0 * pi / 180.0)
    assert not nose_down.passed


def test_ground_effect_reduces_induced_drag_and_native_gate() -> None:
    near = apply_ground_effect(cd0=0.03, cl=1.0, aspect_ratio=8.0, height_m=1.0, span_m=16.0)
    far = apply_ground_effect(cd0=0.03, cl=1.0, aspect_ratio=8.0, height_m=100.0, span_m=16.0)
    assert 0.0 <= near.factor < far.factor <= 1.0
    assert near.cd_ground_effect <= near.cd_free_air
    assert near.cd_ground_effect < far.cd_ground_effect
    with pytest.raises(CapabilityUnavailable):
        require_native_ground_effect()


def test_steering_and_side_friction_seam() -> None:
    angle = steer_angle_for_radius_rad(30.0, 1.5)
    rate = steering_turn_rate_rad_s(10.0, 1.5, angle)
    assert rate > 0.0
    assert angle == pytest.approx(0.049958, rel=1e-3)


def test_native_ground_dynamics_fail_closed() -> None:
    status = native_ground_dynamics_status()
    assert not status.available
    with pytest.raises(CapabilityUnavailable):
        require_native_ground_dynamics()
    with pytest.raises(CapabilityUnavailable):
        require_native_gear_structure()


def test_result_contract_and_determinism() -> None:
    first = simulate_takeoff(_vehicle(), runway=_runway("dry-concrete"))
    second = simulate_takeoff(_vehicle(), runway=_runway("dry-concrete"))
    assert first.meta.input_hash == second.meta.input_hash
    assert len(first.meta.input_hash) == 64

    payload = first.meta.canonical()
    assert payload["source"] == "analytical"
    assert payload["fidelity"] == "ground-transient"
    assert payload["units"]["force"] == "N"
    assert payload["units"]["length"] == "m"
    assert payload["validity"]["passed"] is True
    assert payload["software"]["name"]
    assert payload["provenance"]["model"].startswith("vehicle-systems.landing-gear")
    assert len(payload["provenance"]["inputsHash"]) == 64

    changed = simulate_takeoff(_vehicle(static_thrust_n=7000.0), runway=_runway("dry-concrete"))
    assert changed.meta.input_hash != first.meta.input_hash
