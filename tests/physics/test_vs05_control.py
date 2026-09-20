"""VS 05: aircraft control allocation, controller synthesis, handling qualities.

Tiny deterministic fixtures: a fixed-wing layout with redundant pitch
effectors, a flying-wing elevon pair, and a quad multirotor run through the
same allocator. Redundant actuators share moments subject to bounds,
saturation and rate limits make demands infeasible instead of silently
clipping, failures reconfigure explicitly with provenance, bounded synthesis
produces real PID/actuator contracts, handling constraints participate in
campaign feasibility, and native requests fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe.trim import (
    DerivativeBundle,
    FlightMode,
    LateralDirectionalDerivatives,
    LongitudinalDerivatives,
)
from aeroworkbench_system_dynamics import ActuatorSpec, PIDController
from aeroworkbench_vehicle_systems.control import (
    ALLOCATION_METHODS,
    AllocationError,
    AllocationRequest,
    AxisLoop,
    AxisPlant,
    CapabilityUnavailable,
    ClosedLoopSpec,
    ControlContractError,
    ControlEffector,
    EffectorFault,
    FaultKind,
    GainBounds,
    HandlingMetric,
    HandlingQualityConstraint,
    HandlingQualityError,
    SynthesisError,
    SynthesisTarget,
    TrimEffectivenessMap,
    actuators_for_effectors,
    allocate,
    build_effectiveness,
    closed_loop_campaign_evaluator,
    closed_loop_study_constraints,
    compare_flight_test,
    effectiveness_from_trim,
    evaluate_closed_loop,
    evaluate_handling_qualities,
    handling_evaluator,
    handling_study_constraint,
    mode_metrics,
    native_closed_loop_status,
    require_native_closed_loop,
    solve_native_closed_loop,
    synthesize_axis_pid,
    synthesize_schedule,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "vehicle_systems" / "control"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _effectors(payload: dict[str, Any]) -> tuple[ControlEffector, ...]:
    effectors: list[ControlEffector] = []
    for item in payload["effectors"]:
        gains = item["gains"]
        effectors.append(
            ControlEffector(
                name=str(item["name"]),
                gains=(float(gains["roll"]), float(gains["pitch"]), float(gains["yaw"])),
                lower_limit=float(item["lowerLimit"]),
                upper_limit=float(item["upperLimit"]),
                max_rate=float(item["maxRate"]),
                time_constant_s=float(item["timeConstantS"]),
                priority=int(item["priority"]),
            )
        )
    return tuple(effectors)


def _request(
    payload: dict[str, Any],
    *,
    method: str = "pseudo-inverse",
    faults: tuple[EffectorFault, ...] = (),
    dt_s: float | None = None,
    desired: tuple[float, float, float] | None = None,
) -> AllocationRequest:
    want = payload["desired"]
    return AllocationRequest(
        desired=(
            (float(want["roll"]), float(want["pitch"]), float(want["yaw"]))
            if desired is None
            else desired
        ),
        current=tuple(
            (name, float(value)) for name, value in sorted(payload["current"].items())
        ),
        dt_s=float(payload["dtS"]) if dt_s is None else dt_s,
        method=method,
        faults=faults,
    )


def _modes() -> tuple[tuple[FlightMode, ...], tuple[FlightMode, ...]]:
    longitudinal = (
        FlightMode("short-period", 0.9, 0.65, -4.9, -4.9, 5.66, True),
        FlightMode("phugoid", 0.05, 0.1, -0.03, -0.03, 0.31, True),
    )
    lateral = (
        FlightMode("dutch-roll", 0.5, 0.4, -1.26, -1.26, 2.88, True),
        FlightMode("roll", 0.0, 1.0, -3.0, -3.0, 0.0, True),
    )
    return longitudinal, lateral


def _pitch_plant() -> AxisPlant:
    return AxisPlant(
        axis="pitch",
        inertia=2000.0,
        effectiveness=800.0,
        damping=500.0,
        stiffness=100.0,
        max_deflection=0.35,
        required_moment=200.0,
    )


def _pitch_bounds() -> GainBounds:
    return GainBounds(kp=(0.0, 1000.0), ki=(0.0, 5000.0), kd=(0.0, 200.0))


def _pitch_target() -> SynthesisTarget:
    return SynthesisTarget(bandwidth_hz=1.0, damping_ratio=0.7)


def _pitch_target_damped() -> SynthesisTarget:
    return SynthesisTarget(bandwidth_hz=1.0, damping_ratio=1.2)


def test_fixture_files_load_and_are_deterministic() -> None:
    for name in ("fixed_wing.json", "flying_wing.json", "multirotor.json"):
        payload = _load(name)
        effectors = _effectors(payload)
        matrix = build_effectiveness(effectors)
        first = allocate(matrix, effectors, _request(payload)).digest
        second = allocate(matrix, effectors, _request(payload)).digest
        assert first == second
        assert len(first) == 64


def test_redundant_pitch_effectors_share_moment() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    result = allocate(build_effectiveness(effectors), effectors, _request(payload))
    assert result.feasible
    assert result.residual_norm == pytest.approx(0.0, abs=1e-6)
    assert result.position("elevator") != pytest.approx(0.0)
    assert result.position("stabilator") != pytest.approx(0.0)
    assert not result.reconfigured
    assert result.method == "pseudo-inverse"


def test_daisy_chain_defers_to_low_priority_effector() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    result = allocate(
        build_effectiveness(effectors),
        effectors,
        _request(payload, method="daisy-chain", desired=(20.0, -50.0, 10.0)),
    )
    assert result.feasible
    assert result.position("stabilator") == pytest.approx(0.0, abs=1e-9)
    assert result.residual_norm == pytest.approx(0.0, abs=1e-6)


def test_multirotor_allocates_differential_thrust() -> None:
    payload = _load("multirotor.json")
    effectors = _effectors(payload)
    result = allocate(build_effectiveness(effectors), effectors, _request(payload))
    assert result.feasible
    assert result.residual_norm == pytest.approx(0.0, abs=1e-6)


def test_saturation_makes_trimmed_maneuver_infeasible() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    result = allocate(
        build_effectiveness(effectors),
        effectors,
        _request(payload, desired=(0.0, -100000.0, 0.0)),
    )
    assert not result.feasible
    assert "CONTROL_AUTHORITY_INSUFFICIENT" in result.reasons
    assert not result.meta.validity.passed


def test_rate_limit_makes_maneuver_infeasible() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    result = allocate(
        build_effectiveness(effectors), effectors, _request(payload, dt_s=1e-4)
    )
    assert not result.feasible
    assert result.rate_limited or any("RATE_LIMIT" in reason for reason in result.reasons)


def test_failed_motor_reallocation_is_explicit_and_provenance_backed() -> None:
    payload = _load("multirotor.json")
    effectors = _effectors(payload)
    matrix = build_effectiveness(effectors)
    faults = (EffectorFault("m1", FaultKind.FAILED),)
    result = allocate(
        matrix, effectors, _request(payload, faults=faults, desired=(0.3, 0.0, 0.0))
    )
    assert result.feasible
    assert result.reconfigured
    assert result.failed == ("m1",)
    assert result.residual_norm == pytest.approx(0.0, abs=1e-6)
    assert "RECONFIGURED_AROUND:m1" in result.reasons
    meta = result.meta.as_dict()
    assert meta["provenance"]["inputsHash"] == meta["inputHash"]
    assert allocate(matrix, effectors, _request(payload, faults=faults,
                                                desired=(0.3, 0.0, 0.0))).digest == result.digest


def test_stuck_surface_reallocation_meets_demand() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    faults = (EffectorFault("elevator", FaultKind.STUCK, stuck_at=0.1),)
    result = allocate(build_effectiveness(effectors), effectors,
                      _request(payload, faults=faults))
    assert result.feasible
    assert result.reconfigured
    assert result.position("elevator") == pytest.approx(0.1)
    assert result.residual_norm == pytest.approx(0.0, abs=1e-6)


def test_unknown_fault_fails_closed() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    with pytest.raises(ControlContractError):
        allocate(
            build_effectiveness(effectors),
            effectors,
            AllocationRequest(
                desired=(0.0, 0.0, 0.0),
                current=tuple((e.name, 0.0) for e in effectors),
                dt_s=0.5,
                faults=(EffectorFault("ghost", FaultKind.FAILED),),
            ),
        )


def test_trim_derivative_seam_builds_effectiveness() -> None:
    bundle = DerivativeBundle(
        longitudinal=LongitudinalDerivatives(cm_de=-1.2, cl_alpha=4.5, cm_alpha=-0.8),
        lateral_directional=LateralDirectionalDerivatives(
            cl_da=0.4, cn_dr=-0.15, cn_beta=0.1, cl_beta=-0.08, cl_p=-0.4, cn_r=-0.2
        ),
    )
    matrix = effectiveness_from_trim(
        bundle,
        (
            TrimEffectivenessMap("elevator", "pitch", "cm_de", 800.0),
            TrimEffectivenessMap("aileron", "roll", "cl_da", 1500.0),
            TrimEffectivenessMap("rudder", "yaw", "cn_dr", 1500.0),
        ),
    )
    assert matrix.column("elevator") == pytest.approx((0.0, -960.0, 0.0))
    assert matrix.column("aileron") == pytest.approx((600.0, 0.0, 0.0))
    with pytest.raises(ControlContractError):
        effectiveness_from_trim(
            DerivativeBundle(
                longitudinal=LongitudinalDerivatives(),
                lateral_directional=LateralDirectionalDerivatives(),
            ),
            (TrimEffectivenessMap("elevator", "pitch", "cm_de", 800.0),),
        )


def test_synthesis_is_bounded_and_materializes_pid() -> None:
    designed = synthesize_axis_pid(_pitch_plant(), _pitch_target(), _pitch_bounds())
    assert designed.within_bounds
    assert designed.authority_sufficient
    assert all(pole.real < 0.0 for pole in designed.closed_loop_poles)
    assert _pitch_bounds().contains(
        designed.gains.kp, designed.gains.ki, designed.gains.kd
    )
    pid = designed.gains.to_pid("pitch-loop", setpoint=0.0)
    assert isinstance(pid, PIDController)
    assert pid.kp == pytest.approx(designed.gains.kp)
    assert designed.meta.validity.passed
    with pytest.raises(SynthesisError):
        synthesize_axis_pid(
            _pitch_plant(), _pitch_target(), GainBounds((0.0, 10.0), (0.0, 10.0), (0.0, 10.0))
        )
    starved = AxisPlant(
        axis="pitch", inertia=2000.0, effectiveness=800.0,
        damping=500.0, max_deflection=0.35, required_moment=500.0,
    )
    with pytest.raises(SynthesisError):
        synthesize_axis_pid(starved, _pitch_target(), _pitch_bounds())


def test_synthesis_schedule_interpolates_deterministically() -> None:
    light = AxisPlant(axis="roll", inertia=800.0, effectiveness=600.0,
                      damping=200.0, max_deflection=0.4, required_moment=100.0)
    heavy = AxisPlant(axis="roll", inertia=1200.0, effectiveness=600.0,
                      damping=200.0, max_deflection=0.4, required_moment=100.0)
    bounds = GainBounds(kp=(0.0, 5000.0), ki=(0.0, 20000.0), kd=(0.0, 2000.0))
    target = SynthesisTarget(bandwidth_hz=1.5, damping_ratio=0.7)
    schedule = synthesize_schedule(
        "dynamic_pressure", ((20.0, light, target), (60.0, heavy, target)), bounds
    )
    assert schedule.axis == "roll"
    assert schedule.evaluate(0.0).kp == pytest.approx(schedule.evaluate(20.0).kp)
    assert schedule.evaluate(999.0).kp == pytest.approx(schedule.evaluate(60.0).kp)
    mid = schedule.evaluate(40.0)
    assert mid.kp == pytest.approx(
        (schedule.evaluate(20.0).kp + schedule.evaluate(60.0).kp) / 2.0
    )
    assert schedule.evaluate(40.0).kp == pytest.approx(mid.kp)


def test_allocation_respects_actuator_contract() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    specs = actuators_for_effectors(effectors)
    assert isinstance(specs[0], ActuatorSpec)
    by_id = {spec.actuator_id: spec for spec in specs}
    assert by_id["elevator"].upper_limit == pytest.approx(0.35)
    clamped = by_id["elevator"].step(10.0, position=0.0, dt_s=0.01)
    assert clamped.command_clamped
    assert clamped.provenance.inputs_hash
    result = allocate(build_effectiveness(effectors), effectors, _request(payload))
    response = by_id["elevator"].step(
        result.position("elevator"), position=0.0, dt_s=float(payload["dtS"])
    )
    assert not response.command_clamped
    assert response.position == pytest.approx(result.position("elevator"), abs=1e-3)


def test_handling_constraints_from_modes_and_cap() -> None:
    longitudinal, lateral = _modes()
    metrics = mode_metrics(longitudinal, lateral, load_per_alpha_g=8.0)
    assert metrics["cap"] == pytest.approx(4.0, rel=0.05)
    assert metrics["roll_time_constant_s"] == pytest.approx(1.0 / 3.0)
    constraints = (
        HandlingQualityConstraint("sp-damping", HandlingMetric.SHORT_PERIOD_DAMPING,
                                  "lower", 0.3, "MIL-STD-1797A-screening"),
        HandlingQualityConstraint("cap-upper", HandlingMetric.CAP,
                                  "upper", 10.0, "MIL-STD-1797A-screening"),
        HandlingQualityConstraint("roll-tau", HandlingMetric.ROLL_TIME_CONSTANT_S,
                                  "upper", 1.0, "MIL-STD-1797A-screening"),
    )
    report = evaluate_handling_qualities(metrics, constraints)
    assert report.feasible
    assert report.check("sp-damping").margin > 0.0
    strict = constraints + (
        HandlingQualityConstraint("dr-damping", HandlingMetric.DUTCH_ROLL_DAMPING,
                                  "lower", 0.9, "MIL-STD-1797A-screening"),
    )
    assert not evaluate_handling_qualities(metrics, strict).feasible
    study_constraint = handling_study_constraint(constraints[0])
    assert (study_constraint.name, study_constraint.bound) == ("sp-damping", "lower")


def test_closed_loop_step_settles_and_meets_handling() -> None:
    designed = synthesize_axis_pid(_pitch_plant(), _pitch_target_damped(), _pitch_bounds())
    specs = {spec.actuator_id: spec for spec in actuators_for_effectors((
        ControlEffector("pitch-surface", (0.0, -800.0, 0.0), -0.35, 0.35, 1.5, 0.05),
    ))}
    loop = AxisLoop(
        plant=_pitch_plant(), gains=designed.gains, actuator=specs["pitch-surface"],
        step_command_rad=0.05, output_min=-0.35, output_max=0.35,
    )
    spec = ClosedLoopSpec(
        loops=(loop,),
        handling=(
            HandlingQualityConstraint("sp-damping", HandlingMetric.SHORT_PERIOD_DAMPING,
                                      "lower", 0.3, "MIL-STD-1797A-screening"),
            HandlingQualityConstraint("overshoot", HandlingMetric.OVERSHOOT,
                                      "upper", 0.3, "analytical-screening"),
            HandlingQualityConstraint("settling", HandlingMetric.SETTLING_TIME_S,
                                      "upper", 6.0, "analytical-screening"),
        ),
        mode_metrics=(("short_period_damping", 0.65),),
    )
    report = evaluate_closed_loop(spec)
    assert report.feasible
    assert report.steps[0].settled
    assert report.metric("overshoot") <= 0.3
    assert evaluate_closed_loop(spec).digest == report.digest
    evaluator = closed_loop_campaign_evaluator(spec)
    outputs, flags = evaluator({"step": 0.05}, "nominal")
    assert flags.converged and flags.validity_ok
    assert outputs["feasible"] == pytest.approx(1.0)


def test_closed_loop_campaign_constraints_participate_in_feasibility() -> None:
    longitudinal, lateral = _modes()
    metrics = mode_metrics(longitudinal, lateral, load_per_alpha_g=8.0)
    constraints = (
        HandlingQualityConstraint("sp-damping", HandlingMetric.SHORT_PERIOD_DAMPING,
                                  "lower", 0.3, "MIL-STD-1797A-screening"),
        HandlingQualityConstraint("roll-tau", HandlingMetric.ROLL_TIME_CONSTANT_S,
                                  "upper", 1.0, "MIL-STD-1797A-screening"),
    )
    study_constraints = closed_loop_study_constraints(constraints)
    assert len(study_constraints) == 2
    outputs, flags = handling_evaluator(metrics, constraints)
    assert flags.validity_ok
    for constraint in study_constraints:
        value = outputs[constraint.name]
        if constraint.bound == "lower":
            assert value >= constraint.limit
        else:
            assert value <= constraint.limit


def test_infeasible_allocation_poisons_closed_loop() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    bad = allocate(
        build_effectiveness(effectors), effectors,
        _request(payload, desired=(0.0, -100000.0, 0.0)),
    )
    assert not bad.feasible
    designed = synthesize_axis_pid(_pitch_plant(), _pitch_target_damped(), _pitch_bounds())
    specs = {spec.actuator_id: spec for spec in actuators_for_effectors((
        ControlEffector("pitch-surface", (0.0, -800.0, 0.0), -0.35, 0.35, 1.5, 0.05),
    ))}
    spec = ClosedLoopSpec(
        loops=(AxisLoop(plant=_pitch_plant(), gains=designed.gains,
                        actuator=specs["pitch-surface"], step_command_rad=0.05,
                        output_min=-0.35, output_max=0.35),),
        handling=(
            HandlingQualityConstraint("overshoot", HandlingMetric.OVERSHOOT,
                                      "upper", 0.3, "analytical-screening"),
        ),
        allocation=bad,
    )
    report = evaluate_closed_loop(spec)
    assert not report.feasible
    assert "ALLOCATION_INFEASIBLE" in report.reasons


def test_flight_test_comparison_seam() -> None:
    predicted = {"short_period_damping": 0.65, "overshoot": 0.05}
    measured = {"short_period_damping": 0.62, "overshoot": 0.06}
    tolerances = {"short_period_damping": 0.1, "overshoot": 0.05}
    comparison = compare_flight_test(predicted, measured, tolerances)
    assert comparison.passed
    failed = compare_flight_test(predicted, measured, {"overshoot": 1e-6})
    assert not failed.passed
    assert failed.reasons == ("FLIGHT_TEST_MISMATCH:overshoot",)
    with pytest.raises(HandlingQualityError):
        compare_flight_test(predicted, {}, tolerances)


def test_native_capability_fails_closed() -> None:
    state = native_closed_loop_status("closed-loop-native")
    assert not state.available
    with pytest.raises(CapabilityUnavailable):
        require_native_closed_loop("closed-loop-native")
    designed = synthesize_axis_pid(_pitch_plant(), _pitch_target(), _pitch_bounds())
    specs = {spec.actuator_id: spec for spec in actuators_for_effectors((
        ControlEffector("pitch-surface", (0.0, -800.0, 0.0), -0.35, 0.35, 1.5, 0.05),
    ))}
    spec = ClosedLoopSpec(
        loops=(AxisLoop(plant=_pitch_plant(), gains=designed.gains,
                        actuator=specs["pitch-surface"], step_command_rad=0.05),),
        handling=(
            HandlingQualityConstraint("overshoot", HandlingMetric.OVERSHOOT,
                                      "upper", 0.3, "analytical-screening"),
        ),
    )
    with pytest.raises(CapabilityUnavailable):
        solve_native_closed_loop(spec, {"pitch": 0.05}, backend=None, run_id="run-1")


def test_result_contract_and_hashability() -> None:
    payload = _load("fixed_wing.json")
    effectors = _effectors(payload)
    result = allocate(build_effectiveness(effectors), effectors, _request(payload))
    meta = result.meta.as_dict()
    assert meta["source"] == "analytical"
    assert meta["fidelity"] == "analytical"
    assert meta["units"]["moment"] == "N.m"
    assert meta["units"]["angle"] == "rad"
    assert meta["validity"]["passed"]
    assert set(meta["validity"]["checks"]) == {
        "authority-sufficient", "within-position-limits", "no-escalation",
    }
    assert len(meta["inputHash"]) == 64
    assert meta["software"] == {
        "name": "aeroworkbench-vehicle-systems-control", "version": "1.0.0",
    }
    assert meta["provenance"]["inputsHash"] == meta["inputHash"]
    assert hash(result) == hash(
        allocate(build_effectiveness(effectors), effectors, _request(payload))
    )
    assert hash(_request(payload)) == hash(_request(payload))


def test_invalid_contracts_fail_closed() -> None:
    with pytest.raises(ControlContractError):
        ControlEffector("bad", (0.0, 0.0, 0.0), 0.5, -0.5, 1.0)
    with pytest.raises(ControlContractError):
        AllocationRequest(desired=(0.0, 0.0, 0.0), current=(), dt_s=0.5, method="warp")
    with pytest.raises(ControlContractError):
        build_effectiveness(())
    with pytest.raises(ControlContractError):
        allocate(
            build_effectiveness((ControlEffector("e", (0.0, 1.0, 0.0), -1.0, 1.0, 1.0),)),
            (ControlEffector("other", (0.0, 1.0, 0.0), -1.0, 1.0, 1.0),),
            AllocationRequest(desired=(0.0, 0.0, 0.0), current=(("other", 0.0),), dt_s=0.5),
        )
    solo = allocate(
        build_effectiveness((ControlEffector("e", (0.0, 1.0, 0.0), -1.0, 1.0, 1.0),)),
        (ControlEffector("e", (0.0, 1.0, 0.0), -1.0, 1.0, 1.0),),
        AllocationRequest(desired=(0.0, 0.0, 0.0), current=(("e", 0.0),), dt_s=0.5),
    )
    with pytest.raises(AllocationError):
        solo.position("ghost")
    with pytest.raises(ControlContractError):
        HandlingQualityConstraint("bad", HandlingMetric.CAP, "sideways", 1.0, "std")
    with pytest.raises(HandlingQualityError):
        evaluate_handling_qualities(
            {"cap": 1.0},
            (HandlingQualityConstraint("m", HandlingMetric.OVERSHOOT, "upper", 1.0, "std"),),
        )
    assert set(ALLOCATION_METHODS) == {"pseudo-inverse", "daisy-chain"}
