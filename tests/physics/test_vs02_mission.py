"""VS 02: mission simulation and trajectory optimization with reserves.

Tiny deterministic fixtures: a fixed-wing mission and a rotorcraft mission run
through the same engine. Propagation conserves mass/fuel/energy, reserves are
enforced at mission end, the bounded optimizer trades declared controls without
touching hard constraints, out-of-map operation fails closed, and native
requests fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_vehicle_systems.mission import (
    AnalyticalFixedWingParticipant,
    AnalyticalRotorcraftParticipant,
    CapabilityUnavailable,
    ClosureError,
    ClosureTolerances,
    ControlName,
    ControlVariable,
    MissionBalance,
    MissionContractError,
    MissionOptimizationError,
    MissionSet,
    MissionSpec,
    OperatingPoint,
    PerformanceMapParticipant,
    PerformanceRejected,
    PropagationPolicy,
    ReserveError,
    ReserveKind,
    ReserveSpec,
    SegmentConstraints,
    SegmentKind,
    SegmentMode,
    SegmentSpec,
    TrajectoryOptimization,
    VehicleSpec,
    apply_controls,
    evaluate_closure,
    evaluate_mission_set,
    evaluate_reserves,
    mission_campaign_objectives,
    mission_evaluator,
    native_mission_status,
    objective_value,
    optimize_trajectory,
    require_native_mission,
    run_mission,
    solve_native_mission,
    trajectory_study,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "vehicle_systems" / "mission"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _vehicle(payload: dict[str, Any]) -> VehicleSpec:
    envelope = payload.get("envelope", {})
    return VehicleSpec(
        vehicle_id=str(payload["vehicleId"]),
        empty_mass_kg=float(payload["emptyMassKg"]),
        initial_fuel_kg=float(payload["initialFuelKg"]),
        fuel_lhv_j_kg=float(payload["fuelLhvJKg"]),
        battery_capacity_j=float(payload.get("batteryCapacityJ", 0.0)),
        initial_state_of_charge=float(payload.get("initialStateOfCharge", 1.0)),
        reference_area_m2=float(payload.get("referenceAreaM2", 1.0)),
        envelope=SegmentConstraints(
            max_altitude_m=envelope.get("maxAltitudeM"),
            min_speed_m_s=envelope.get("minSpeedMS"),
            max_speed_m_s=envelope.get("maxSpeedMS"),
            max_climb_rate_m_s=envelope.get("maxClimbRateMS"),
            max_thermal_k=envelope.get("maxThermalK"),
        ),
        step_size_s=float(payload.get("stepSizeS", 10.0)),
        max_steps=int(payload.get("maxSteps", 20000)),
        ground_speed_m_s=float(payload.get("groundSpeedMS", 0.0)),
    )


def _segment(payload: dict[str, Any]) -> SegmentSpec:
    reserve_payload = payload.get("reserve")
    reserve = (
        ReserveSpec(
            kind=ReserveKind(str(reserve_payload["kind"])),
            amount=float(reserve_payload["amount"]),
            label=str(reserve_payload.get("label", "reserve")),
        )
        if isinstance(reserve_payload, dict)
        else None
    )
    return SegmentSpec(
        segment_id=str(payload["segmentId"]),
        kind=SegmentKind(str(payload["kind"])),
        mode=SegmentMode(str(payload["mode"])),
        speed_m_s=float(payload["speedMS"]),
        altitude_m=float(payload["altitudeM"]),
        climb_rate_m_s=float(payload.get("climbRateMS", 0.0)),
        throttle=float(payload.get("throttle", 1.0)),
        duration_s=payload.get("durationS"),
        distance_m=payload.get("distanceM"),
        target_altitude_m=payload.get("targetAltitudeM"),
        target_speed_m_s=payload.get("targetSpeedMS"),
        reserve=reserve,
    )


def _mission(payload: dict[str, Any]) -> MissionSpec:
    return MissionSpec(
        mission_id=str(payload["missionId"]),
        vehicle=_vehicle(payload["vehicle"]),
        segments=tuple(_segment(item) for item in payload["segments"]),
        reserves=tuple(
            ReserveSpec(
                kind=ReserveKind(str(item["kind"])),
                amount=float(item["amount"]),
                label=str(item.get("label", "reserve")),
            )
            for item in payload.get("reserves", [])
        ),
        label=str(payload.get("label", "")),
    )


def _fixed_wing(payload: dict[str, Any]) -> AnalyticalFixedWingParticipant:
    participant = payload["participant"]
    return AnalyticalFixedWingParticipant(
        cd0=float(participant["cd0"]),
        oswald_e=float(participant["oswaldE"]),
        aspect_ratio=float(participant["aspectRatio"]),
        reference_area_m2=float(participant["referenceAreaM2"]),
        max_thrust_n=float(participant["maxThrustN"]),
        tsfc_kg_n_s=float(participant["tsfcKgNS"]),
        fuel_lhv_j_kg=float(payload["vehicle"]["fuelLhvJKg"]),
        power_model=str(participant["powerModel"]),
    )


def _rotorcraft(payload: dict[str, Any]) -> AnalyticalRotorcraftParticipant:
    participant = payload["participant"]
    return AnalyticalRotorcraftParticipant(
        disk_area_m2=float(participant["diskAreaM2"]),
        figure_of_merit=float(participant["figureOfMerit"]),
        profile_power_w=float(participant["profilePowerW"]),
        parasite_flat_plate_m2=float(participant["parasiteFlatPlateM2"]),
        max_shaft_power_w=float(participant["maxShaftPowerW"]),
        max_horizontal_thrust_n=float(participant["maxHorizontalThrustN"]),
        tsfc_kg_w_s=float(participant["tsfcKgWS"]),
        fuel_lhv_j_kg=float(payload["vehicle"]["fuelLhvJKg"]),
        power_model=str(participant["powerModel"]),
    )


def test_fixture_files_load_and_are_stable() -> None:
    for name in ("fixed_wing_mission.json", "rotorcraft_mission.json"):
        first = _mission(_load(name))
        second = _mission(_load(name))
        assert first.digest() == second.digest()
        assert len(first.segments) >= 4


def test_full_mission_closes_mass_fuel_energy() -> None:
    payload = _load("fixed_wing_mission.json")
    result = run_mission(_mission(payload), _fixed_wing(payload))
    assert result.closure_passed
    assert result.reserves_passed
    assert result.valid
    assert {item.dimension for item in result.closure_report.residuals} == {
        "mass",
        "fuel",
        "energy",
        "distance",
        "continuity",
    }
    assert result.fuel_burned_kg > 0.0
    assert result.energy_consumed_j > 0.0
    assert result.final_specific_energy_j_kg > 0.0
    kinds = [segment.kind for segment in result.trace.segments]
    for expected in (
        SegmentKind.TAKEOFF,
        SegmentKind.CLIMB,
        SegmentKind.CRUISE,
        SegmentKind.DESCENT,
        SegmentKind.LANDING,
    ):
        assert expected in kinds


def test_taxi_and_loiter_segments_propagate() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    taxi = SegmentSpec(
        segment_id="taxi",
        kind=SegmentKind.TAXI,
        mode=SegmentMode.DURATION,
        speed_m_s=30.0,
        altitude_m=0.0,
        duration_s=30.0,
    )
    loiter = SegmentSpec(
        segment_id="loiter",
        kind=SegmentKind.LOITER,
        mode=SegmentMode.DURATION,
        speed_m_s=80.0,
        altitude_m=1000.0,
        duration_s=60.0,
    )
    segments = (taxi,) + spec.segments + (loiter,)
    extended = MissionSpec(
        mission_id="vs02-taxi-loiter",
        vehicle=spec.vehicle,
        segments=segments,
        reserves=spec.reserves,
    )
    result = run_mission(extended, _fixed_wing(payload))
    assert result.closure_passed
    assert result.valid


def test_reserve_enforced_at_end_not_inferred() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    participant = _fixed_wing(payload)
    verdict = evaluate_reserves(
        spec,
        run_mission(spec, participant).trace.final,
        reserve_duration_s=0.0,
    )
    assert verdict.passed
    starved = MissionSpec(
        mission_id="vs02-starved",
        vehicle=spec.vehicle,
        segments=spec.segments,
        reserves=(ReserveSpec(kind=ReserveKind.FUEL, amount=1.0e9, label="impossible"),),
    )
    failed = evaluate_reserves(
        starved,
        run_mission(starved, participant).trace.final,
        reserve_duration_s=0.0,
    )
    assert not failed.passed
    with pytest.raises(ReserveError):
        evaluate_reserves(
            starved,
            run_mission(starved, participant).trace.final,
            reserve_duration_s=0.0,
            raise_on_failure=True,
        )
    with pytest.raises(ReserveError):
        run_mission(starved, participant, raise_on_failure=True)


def test_time_reserve_needs_flown_reserve_segment() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    reserve_leg = SegmentSpec(
        segment_id="hold",
        kind=SegmentKind.RESERVE,
        mode=SegmentMode.DURATION,
        speed_m_s=80.0,
        altitude_m=1000.0,
        duration_s=60.0,
    )
    with_hold = MissionSpec(
        mission_id="vs02-with-hold",
        vehicle=spec.vehicle,
        segments=spec.segments + (reserve_leg,),
        reserves=(ReserveSpec(kind=ReserveKind.TIME, amount=60.0, label="hold-time"),),
    )
    result = run_mission(with_hold, _fixed_wing(payload))
    assert result.reserve_verdict.passed
    assert result.trace.reserve_duration_s >= 60.0
    short = MissionSpec(
        mission_id="vs02-short-hold",
        vehicle=spec.vehicle,
        segments=spec.segments,
        reserves=(ReserveSpec(kind=ReserveKind.TIME, amount=60.0, label="hold-time"),),
    )
    assert not run_mission(short, _fixed_wing(payload)).reserve_verdict.passed


def test_optimizer_trades_controls_without_touching_hard_constraints() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    participant = _fixed_wing(payload)
    optimization = TrajectoryOptimization(
        objective="fuel",
        variables=(
            ControlVariable("cruise", ControlName.SPEED, 80.0, 120.0, 100.0),
            ControlVariable("climb", ControlName.CLIMB_RATE, 5.0, 15.0, 10.0),
        ),
        max_iterations=10,
        step_fraction=0.5,
        tolerance=2.0,
    )
    outcome = optimize_trajectory(spec, participant, optimization)
    assert outcome.converged
    assert outcome.feasible
    assert outcome.best_value <= outcome.baseline_value
    assert outcome.result.trace.final.mass_kg > 0.0
    for before, after in zip(spec.segments, outcome.result.trace.segments, strict=True):
        assert before.segment_id == after.segment_id
        assert before.kind is after.kind
    assert outcome.result.trace.segments[0].start.mass_kg == spec.vehicle.initial_mass_kg
    vehicle_before = spec.vehicle.canonical()
    vehicle_after = outcome.result.trace.initial.mass_kg
    assert vehicle_after == vehicle_before["emptyMassKg"] + vehicle_before["initialFuelKg"]
    assert objective_value(outcome.result, "fuel") == outcome.result.fuel_burned_kg
    with pytest.raises(MissionOptimizationError):
        objective_value(outcome.result, "nonsense")


def test_apply_controls_rejects_unknown_segment() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    variables = (ControlVariable("ghost", ControlName.SPEED, 1.0, 2.0, 1.5),)
    with pytest.raises(MissionOptimizationError):
        apply_controls(spec, variables, {"ghost:speed": 1.5})


def test_out_of_map_operation_rejects() -> None:
    point = OperatingPoint(
        altitude_m=1000.0,
        speed_m_s=80.0,
        mass_kg=1100.0,
        climb_rate_m_s=0.0,
        throttle=1.0,
        power_fraction=1.0,
        configuration=0,
        segment_kind=SegmentKind.CRUISE,
        phase="distance",
    )
    participant = PerformanceMapParticipant(
        participant_id="empty-map",
        aero_inputs=lambda _point: {},
        propulsion_inputs=lambda _point, _thrust: {},
    )
    with pytest.raises(PerformanceRejected):
        participant.drag(point)
    with pytest.raises(PerformanceRejected):
        participant.propulsion(point, 1000.0)


def test_same_engine_accepts_rotorcraft() -> None:
    payload = _load("rotorcraft_mission.json")
    result = run_mission(_mission(payload), _rotorcraft(payload), policy=PropagationPolicy())
    assert result.closure_passed
    assert result.reserves_passed
    assert result.valid
    assert result.energy_consumed_j > 0.0


def test_energy_state_closure() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    result = run_mission(spec, _fixed_wing(payload))
    vehicle = spec.vehicle
    initial_energy = result.trace.initial.stored_energy_j(vehicle)
    final_energy = result.trace.final.stored_energy_j(vehicle)
    assert initial_energy - final_energy == pytest.approx(result.energy_consumed_j)
    assert result.final_energy_j == pytest.approx(final_energy)
    report = result.closure_report
    assert abs(report.residual_for("energy").residual) <= report.residual_for("energy").tolerance


def test_closure_failure_is_visible_not_silent() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    result = run_mission(spec, _fixed_wing(payload))
    tampered = MissionBalance(
        initial_mass_kg=result.trace.initial.mass_kg,
        final_mass_kg=result.trace.final.mass_kg,
        fuel_burned_kg=result.trace.fuel_burned_kg + 50.0,
        jettisoned_kg=result.trace.jettisoned_kg,
        initial_fuel_kg=result.trace.initial.fuel_kg,
        final_fuel_kg=result.trace.final.fuel_kg,
        initial_energy_j=result.trace.initial.stored_energy_j(spec.vehicle),
        final_energy_j=result.trace.final.stored_energy_j(spec.vehicle),
        stored_energy_consumed_j=result.trace.final.stored_energy_consumed_j,
        mission_distance_m=result.trace.final.distance_m,
        segment_distance_sum_m=result.trace.segment_distance_sum_m,
        max_boundary_discontinuity=result.trace.max_boundary_discontinuity,
    )
    report = evaluate_closure(spec, tampered)
    assert not report.passed
    assert not report.residual_for("mass").passed
    with pytest.raises(ClosureError):
        report.residual_for("nonexistent")


def test_mission_set_and_campaign_seam() -> None:
    fixed_payload = _load("fixed_wing_mission.json")
    rotor_payload = _load("rotorcraft_mission.json")
    fixed_spec = _mission(fixed_payload)
    rotor_spec = _mission(rotor_payload)
    mission_set = MissionSet(
        set_id="vs02-set",
        missions=(fixed_spec, rotor_spec),
        weights=(0.6, 0.4),
    )
    outcome = evaluate_mission_set(
        mission_set,
        {
            fixed_spec.mission_id: _fixed_wing(fixed_payload),
            rotor_spec.mission_id: _rotorcraft(rotor_payload),
        },
    )
    assert outcome.valid
    assert outcome.aggregate["fuel_burned_kg"] > 0.0
    assert "energy_consumed_j" in outcome.aggregate
    evaluator = mission_evaluator(
        fixed_spec,
        _fixed_wing(fixed_payload),
        {"cruise_speed": ("cruise", ControlName.SPEED)},
    )
    outputs, flags = evaluator({"cruise_speed": 100.0}, "nominal")
    assert outputs["fuel_burned_kg"] > 0.0
    assert flags.converged
    assert mission_campaign_objectives()


def test_invalid_contracts_fail_closed() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    with pytest.raises(MissionContractError):
        MissionSpec(
            mission_id="vs02-duplicate",
            vehicle=spec.vehicle,
            segments=(spec.segments[0], spec.segments[0]),
        )
    with pytest.raises(MissionContractError):
        SegmentSpec(
            segment_id="bad",
            kind=SegmentKind.CRUISE,
            mode=SegmentMode.DURATION,
            speed_m_s=100.0,
            altitude_m=1000.0,
        )
    with pytest.raises(MissionOptimizationError):
        ControlVariable("cruise", ControlName.SPEED, 120.0, 80.0, 100.0)
    with pytest.raises(MissionOptimizationError):
        TrajectoryOptimization(objective="fuel", variables=())
    with pytest.raises(MissionOptimizationError):
        TrajectoryOptimization(
            objective="fuel",
            variables=(ControlVariable("cruise", ControlName.SPEED, 80.0, 120.0, 100.0),),
            driver="warp",
        )
    assert trajectory_study(
        TrajectoryOptimization(
            objective="fuel",
            variables=(ControlVariable("cruise", ControlName.SPEED, 80.0, 120.0, 100.0),),
        )
    )


def test_native_capability_fails_closed() -> None:
    state = native_mission_status("mission-native")
    assert not state.available
    with pytest.raises(CapabilityUnavailable):
        require_native_mission("mission-native")
    payload = _load("fixed_wing_mission.json")
    with pytest.raises(CapabilityUnavailable):
        solve_native_mission(_mission(payload), {}, backend=None, run_id="run-1")


def test_result_contract_and_determinism() -> None:
    payload = _load("fixed_wing_mission.json")
    spec = _mission(payload)
    participant = _fixed_wing(payload)
    first = run_mission(spec, participant)
    second = run_mission(spec, participant)
    assert first.digest() == second.digest()
    meta = first.meta.as_dict()
    assert meta["source"] == "analytical"
    assert meta["fidelity"] == "analytical"
    assert meta["units"]["mass"] == "kg"
    assert meta["units"]["energy"] == "J"
    assert meta["validity"]["passed"]
    assert set(meta["validity"]["checks"]) == {
        "closure",
        "reserves",
        "constraints",
        "no-escalation",
        "fidelity-nominal",
    }
    assert len(meta["inputHash"]) == 64
    assert meta["software"]["name"] == "aeroworkbench-vehicle-systems-mission"
    assert meta["provenance"]["inputsHash"] == meta["inputHash"]
    assert first.canonical()["objectives"]["fuel_burned_kg"] == pytest.approx(
        second.fuel_burned_kg
    )


def test_closure_tolerances_contract() -> None:
    tolerances = ClosureTolerances()
    assert tolerances.canonical()["massRel"] == tolerances.mass_rel
    with pytest.raises(MissionContractError):
        ClosureTolerances(mass_rel=-1.0)
