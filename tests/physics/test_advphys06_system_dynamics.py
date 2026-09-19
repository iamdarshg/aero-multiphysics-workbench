"""ADV-PHYS 06: generic transient system dynamics, controls, actuators, protection.

These tests drive the generic transient capability from typed, deterministic
fixtures: declared integrators, typed dynamic state, controllers, actuators,
protection limits/interlocks/hysteresis, discrete events, and solver coupling
through the shared core contracts. Every result must be unit-bearing,
hashable, and carry source/fidelity/validity/software identity/provenance;
declared limits fail closed; and native transient coordinators are
capability-gated and fail closed when absent. No result is fabricated.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import aeroworkbench_system_dynamics as sd
import pytest
from aeroworkbench_core.types import ResultSource

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "system_dynamics"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _spool() -> sd.SpoolModel:
    model = _fixture("spool_transient.json")["model"]
    assert isinstance(model, dict)
    return sd.SpoolModel(
        inertia_kg_m2=model["inertiaKgM2"],
        damping_n_m_s=model["dampingNmS"],
        initial_speed_rad_s=model["initialSpeedRadS"],
    )


def _spool_scenario(**overrides: object) -> sd.TransientScenario:
    fixture = _fixture("spool_transient.json")
    scenario = fixture["scenario"]
    assert isinstance(scenario, dict)
    payload: dict[str, object] = {
        "scenario_id": "spool-ramp",
        "plant": _spool(),
        "integrator": sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, scenario["stepS"]),
        "duration_s": scenario["durationS"],
        "inputs": {
            "shaft_torque_n_m": scenario["shaftTorqueNm"],
            "load_torque_n_m": scenario["loadTorqueNm"],
        },
    }
    payload.update(overrides)
    return sd.TransientScenario(**payload)  # type: ignore[arg-type]


# -- A. units, validity, and state contracts ---------------------------------


def test_advphys06_units_are_known_si_labels() -> None:
    for label in ("rad/s", "kg*m2", "Pa", "K", "A", "m/s", "N*m", "J/K"):
        assert sd.require_unit(label) == label
    assert "rad/s" in sd.SI_UNITS


def test_advphys06_unknown_unit_fails_closed() -> None:
    with pytest.raises(sd.UnitError):
        sd.require_unit("furlong")


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "5"])
def test_advphys06_finite_rejects_non_numbers(bad: object) -> None:
    with pytest.raises(sd.SystemDynamicsError):
        sd.finite(bad, "value")


def test_advphys06_dynamic_state_supports_every_category() -> None:
    cases = (
        ("shaft_speed_rad_s", "rad/s", sd.StateKind.SHAFT_SPEED),
        ("inertia_kg_m2", "kg*m2", sd.StateKind.ROTATIONAL_INERTIA),
        ("pressure_pa", "Pa", sd.StateKind.PRESSURE_STORAGE),
        ("temperature_storage_k", "K", sd.StateKind.TEMPERATURE_STORAGE),
        ("flow_kg_s", "kg/s", sd.StateKind.FLOW_STORAGE),
        ("state_of_charge", "1", sd.StateKind.ELECTRICAL),
        ("position_m", "m", sd.StateKind.ACTUATOR_POSITION),
        ("rate_m_s", "m/s", sd.StateKind.ACTUATOR_RATE),
        ("control_state", "1", sd.StateKind.CONTROL),
        ("temperature_k", "K", sd.StateKind.THERMAL_CAPACITANCE),
        ("speed_m_s", "m/s", sd.StateKind.VEHICLE),
        ("airflow_m_s", "m/s", sd.StateKind.AIRFLOW),
    )
    spec = sd.DynamicStateSpec(
        "all-kinds",
        tuple(sd.StateVariable(name, unit, kind, 0.0) for name, unit, kind in cases),
    )
    assert set(spec.names()) == {name for name, _unit, _kind in cases}
    assert spec.by_kind(sd.StateKind.SHAFT_SPEED)[0].unit == "rad/s"
    assert spec.initial()["shaft_speed_rad_s"] == 0.0
    assert len(spec.canonical()["variables"]) == len(cases)  # type: ignore[arg-type]


def test_advphys06_duplicate_state_names_fail_closed() -> None:
    variable = sd.StateVariable("x", "1", sd.StateKind.CONTROL, 0.0)
    with pytest.raises(sd.TransientValidationError):
        sd.DynamicStateSpec("dup", (variable, variable))


# -- B. deterministic integrators --------------------------------------------


def test_advphys06_rk4_matches_analytic_first_order_lag() -> None:
    def derivative(
        time_s: float, state: dict[str, float], inputs: dict[str, float]
    ) -> dict[str, float]:
        del time_s, inputs
        return {"x": 1.0 - state["x"]}

    history = sd.integrate_fixed_step(
        derivative,
        {"x": 0.0},
        spec=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, 0.01),
        duration_s=1.0,
    )
    assert history.states[-1]["x"] == pytest.approx(1.0 - math.exp(-1.0), rel=1e-6)
    assert history.receipt.method == "runge-kutta-4"
    assert history.receipt.steps == 100
    assert history.receipt.recorded_points == 101


def test_advphys06_integrators_are_deterministic() -> None:
    def derivative(
        time_s: float, state: dict[str, float], inputs: dict[str, float]
    ) -> dict[str, float]:
        return {"x": -0.5 * state["x"]}

    spec = sd.IntegratorSpec(sd.IntegrationMethod.HEUN, 0.01)
    first = sd.integrate_fixed_step(derivative, {"x": 2.0}, spec=spec, duration_s=1.0)
    second = sd.integrate_fixed_step(derivative, {"x": 2.0}, spec=spec, duration_s=1.0)
    assert first.states == second.states


def test_advphys06_missing_derivative_state_fails_closed() -> None:
    with pytest.raises(sd.TransientValidationError):
        sd.advance(
            lambda time_s, state, inputs: {},
            sd.IntegrationMethod.EXPLICIT_EULER,
            0.0,
            {"x": 1.0},
            0.1,
            {},
        )


# -- C. spool transient and distinct steady fidelity -------------------------


def test_advphys06_spool_transient_matches_analytic() -> None:
    fixture = _fixture("spool_transient.json")
    expect = fixture["expect"]
    assert isinstance(expect, dict)
    result = sd.simulate_transient(_spool_scenario())
    series = result.series_for("shaft_speed_rad_s")
    assert series.unit == "rad/s"
    assert series.final() == pytest.approx(
        expect["finalSpeedRadS"], abs=expect["finalSpeedToleranceRadS"]
    )
    assert result.fidelity is sd.Fidelity.TRANSIENT
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.provenance.model == expect["softwareModel"]
    assert result.provenance.model_version == sd.SOFTWARE_VERSION
    assert len(result.provenance.inputs_hash) == 64


def test_advphys06_spool_transient_is_reproducible() -> None:
    first = sd.simulate_transient(_spool_scenario())
    second = sd.simulate_transient(_spool_scenario())
    assert first.provenance.inputs_hash == second.provenance.inputs_hash
    assert first.series_for("shaft_speed_rad_s").values == second.series_for(
        "shaft_speed_rad_s"
    ).values


def test_advphys06_steady_point_is_a_distinct_fidelity() -> None:
    steady = sd.find_steady_state(
        _spool(),
        {"shaft_torque_n_m": 1.0, "load_torque_n_m": 0.0},
        step_s=1.0,
        tolerance=1e-9,
    )
    transient = sd.simulate_transient(_spool_scenario())
    assert steady.converged is True
    assert steady.fidelity is sd.Fidelity.STEADY_POINT
    assert transient.fidelity is sd.Fidelity.TRANSIENT
    assert steady.value("shaft_speed_rad_s") == pytest.approx(100.0, rel=1e-6)
    assert steady.provenance.model != transient.provenance.model


def test_advphys06_variable_inertia_is_an_integrated_state() -> None:
    model = sd.SpoolModel(
        inertia_kg_m2=0.05, damping_n_m_s=0.0, variable_inertia=True
    )
    scenario = sd.TransientScenario(
        scenario_id="variable-inertia",
        plant=model,
        integrator=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, 0.01),
        duration_s=1.0,
        inputs={"shaft_torque_n_m": 0.1, "inertia_rate_kg_m2_s": 0.01},
    )
    result = sd.simulate_transient(scenario)
    assert result.series_for("inertia_kg_m2").final() == pytest.approx(0.06, rel=1e-9)


# -- D. thermal and storage transients ---------------------------------------


def test_advphys06_thermal_capacitance_matches_analytic() -> None:
    fixture = _fixture("thermal_step.json")
    model = fixture["model"]
    scenario = fixture["scenario"]
    expect = fixture["expect"]
    assert isinstance(model, dict) and isinstance(scenario, dict) and isinstance(expect, dict)
    plant = sd.ThermalCapacitanceModel(
        heat_capacity_j_k=model["heatCapacityJK"],
        ambient_temperature_k=model["ambientTemperatureK"],
        resistance_k_w=model["resistanceKW"],
        initial_temperature_k=model["initialTemperatureK"],
    )
    result = sd.simulate_transient(
        sd.TransientScenario(
            scenario_id="thermal-step",
            plant=plant,
            integrator=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, scenario["stepS"]),
            duration_s=scenario["durationS"],
            inputs={"heat_in_w": scenario["heatInW"], "heat_out_w": scenario["heatOutW"]},
        )
    )
    assert result.series_for("temperature_k").final() == pytest.approx(
        expect["finalTemperatureK"], abs=expect["finalTemperatureToleranceK"]
    )
    steady = sd.find_steady_state(
        plant,
        {"heat_in_w": scenario["heatInW"], "heat_out_w": scenario["heatOutW"]},
        step_s=1.0,
    )
    assert steady.value("temperature_k") == pytest.approx(expect["steadyTemperatureK"], rel=1e-6)


def test_advphys06_storage_volume_pressure_rate() -> None:
    fixture = _fixture("storage_volume.json")
    model = fixture["model"]
    scenario = fixture["scenario"]
    expect = fixture["expect"]
    assert isinstance(model, dict) and isinstance(scenario, dict) and isinstance(expect, dict)
    plant = sd.StorageVolumeModel(
        volume_m3=model["volumeM3"],
        gas_constant_j_kg_k=model["gasConstantJKgK"],
        temperature_k=model["temperatureK"],
        specific_heat_ratio=model["specificHeatRatio"],
        initial_pressure_pa=model["initialPressurePa"],
    )
    result = sd.simulate_transient(
        sd.TransientScenario(
            scenario_id="storage",
            plant=plant,
            integrator=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, scenario["stepS"]),
            duration_s=scenario["durationS"],
            inputs={
                "mass_flow_in_kg_s": scenario["massFlowInKgS"],
                "mass_flow_out_kg_s": scenario["massFlowOutKgS"],
            },
        )
    )
    series = result.series_for("pressure_pa")
    rate = (series.at(1) - series.at(0)) / (result.times_s[1] - result.times_s[0])
    assert rate == pytest.approx(expect["pressureRatePaS"], rel=1e-6)
    assert series.final() == pytest.approx(
        expect["finalPressurePa"], abs=expect["finalPressureTolerancePa"]
    )


def test_advphys06_battery_state_of_charge_coulomb_counting() -> None:
    plant = sd.BatteryStateOfChargeModel(capacity_a_s=3600.0, initial_state_of_charge=1.0)
    result = sd.simulate_transient(
        sd.TransientScenario(
            scenario_id="battery",
            plant=plant,
            integrator=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, 0.01),
            duration_s=60.0,
            inputs={"current_a": 1.0},
        )
    )
    assert result.series_for("state_of_charge").final() == pytest.approx(
        1.0 - 60.0 / 3600.0, rel=1e-9
    )


# -- E. actuators -------------------------------------------------------------


def test_advphys06_actuator_rate_limit_fixture() -> None:
    fixture = _fixture("actuator_positioning.json")
    config = fixture["actuator"]
    scenario = fixture["scenario"]
    expect = fixture["expect"]
    assert isinstance(config, dict) and isinstance(scenario, dict) and isinstance(expect, dict)
    actuator = sd.ActuatorSpec(
        actuator_id=config["actuatorId"],
        command_name=config["commandName"],
        output_name=config["outputName"],
        unit=config["unit"],
        lower_limit=config["lowerLimit"],
        upper_limit=config["upperLimit"],
        max_rate=config["maxRate"],
        time_constant_s=config["timeConstantS"],
        initial_position=config["initialPosition"],
    )
    result = sd.simulate_transient(
        sd.TransientScenario(
            scenario_id="actuator",
            plant=sd.FirstOrderLagModel(
                variable_name="x", unit="1", kind=sd.StateKind.CONTROL,
                time_constant_s=1.0, initial_value=0.0, target_input="target",
            ),
            integrator=sd.IntegratorSpec(sd.IntegrationMethod.EXPLICIT_EULER, scenario["stepS"]),
            duration_s=scenario["durationS"],
            inputs={config["commandName"]: scenario["commandM"], "target": 0.0},
            actuators=(actuator,),
            record_signals=((config["outputName"], config["unit"]),),
        )
    )
    position = result.signal(config["outputName"])
    assert position.final() == pytest.approx(expect["finalPositionM"], rel=1e-9)
    assert position.maximum() == pytest.approx(expect["finalPositionM"], rel=1e-6)
    step = actuator.step(config["upperLimit"], position=0.0, dt_s=0.01)
    assert step.rate == pytest.approx(expect["rateLimitMS"], rel=1e-9)
    assert step.rate_limited is True


def test_advphys06_actuator_position_saturation_and_state_spec() -> None:
    actuator = sd.ActuatorSpec(
        actuator_id="valve",
        command_name="command",
        output_name="position",
        unit="rad",
        lower_limit=0.0,
        upper_limit=1.0,
        max_rate=100.0,
    )
    response = actuator.step(2.0, position=0.0, dt_s=0.1)
    assert response.command_clamped is True
    assert response.position == pytest.approx(1.0)
    spec = actuator.state_spec()
    assert set(spec.names()) == {"valve.position", "valve.rate"}
    assert response.provenance.source is ResultSource.ANALYTICAL
    assert len(response.provenance.inputs_hash) == 64


def test_advphys06_actuator_first_order_lag() -> None:
    actuator = sd.ActuatorSpec(
        actuator_id="lag",
        command_name="command",
        output_name="position",
        unit="rad",
        lower_limit=0.0,
        upper_limit=2.0,
        max_rate=1000.0,
        time_constant_s=1.0,
    )
    response = actuator.step(1.0, position=0.0, dt_s=1.0)
    assert response.position == pytest.approx(1.0 - math.exp(-1.0), rel=1e-9)


# -- F. controls --------------------------------------------------------------


def test_advphys06_pid_saturation_and_anti_windup_seam() -> None:
    controller = sd.PIDController(
        "pid-1", "command", measured_variable="x", setpoint=1.0,
        kp=2.0, ki=1.0, output_min=None, output_max=1.5,
    )
    controller.reset()
    output = controller.update(0.0, {"x": 0.0}, 1.0)
    assert output["command"] == pytest.approx(1.5)
    assert controller.saturated is True
    assert controller.anti_windup_active is True
    assert controller.integral == pytest.approx(-0.5)


def test_advphys06_pid_rate_limit() -> None:
    controller = sd.PIDController(
        "pid-2", "command", measured_variable="x", setpoint=1.0,
        kp=10.0, max_rate=1.0,
    )
    controller.reset()
    assert controller.update(0.0, {"x": 0.0}, 0.1)["command"] == pytest.approx(0.1)


def test_advphys06_schedule_controller_linear_and_step() -> None:
    linear = sd.ScheduleController(
        "sched", "command", unit="1", points=((0.0, 0.0), (2.0, 2.0))
    )
    assert linear.update(1.0, {}, 0.1)["command"] == pytest.approx(1.0)
    step = sd.ScheduleController(
        "sched-step", "command", unit="1", points=((0.0, 0.0), (2.0, 2.0)), mode="step"
    )
    assert step.update(1.0, {}, 0.1)["command"] == pytest.approx(0.0)


def test_advphys06_lookup_controller_interpolates_and_fails_closed() -> None:
    controller = sd.LookupController(
        "lookup", "command", input_variable="x", unit="1",
        table=((0.0, 0.0), (10.0, 100.0)),
    )
    assert controller.update(0.0, {"x": 5.0}, 0.1)["command"] == pytest.approx(50.0)
    strict = sd.LookupController(
        "lookup-strict", "command", input_variable="x", unit="1",
        table=((0.0, 0.0), (10.0, 100.0)), clamp=False,
    )
    with pytest.raises(sd.TransientValidationError):
        strict.update(0.0, {"x": 20.0}, 0.1)


def test_advphys06_state_machine_controller_transitions() -> None:
    controller = sd.StateMachineController(
        "sm", "command", unit="1", initial_state="idle",
        states=(
            sd.ControllerState(
                "idle", 0.0,
                (sd.StateTransition("speed", "gt", 10.0, "run"),),
            ),
            sd.ControllerState("run", 1.0),
        ),
    )
    controller.reset()
    assert controller.update(0.0, {"speed": 5.0}, 0.1)["command"] == pytest.approx(0.0)
    assert controller.update(1.0, {"speed": 11.0}, 0.1)["command"] == pytest.approx(1.0)
    assert controller.current_state == "run"


def test_advphys06_sensor_filter_first_order_lag() -> None:
    controller = sd.FirstOrderSensorFilter(
        "filter", "filtered", input_variable="raw", unit="1",
        time_constant_s=1.0, initial_value=0.0,
    )
    controller.reset()
    output = controller.update(0.0, {"raw": 1.0}, 1.0)
    assert output["filtered"] == pytest.approx(1.0 - math.exp(-1.0), rel=1e-9)


# -- G. protection ------------------------------------------------------------


def test_advphys06_protection_hysteresis_fixture() -> None:
    fixture = _fixture("protection_hysteresis.json")
    config = fixture["limit"]
    sequence = fixture["sequence"]
    assert isinstance(config, dict) and isinstance(sequence, list)
    limit = sd.ProtectionLimit(
        name=config["name"],
        kind=sd.ProtectionKind(config["kind"]),
        variable=config["variable"],
        unit=config["unit"],
        threshold=config["threshold"],
        direction=config["direction"],
        hysteresis=config["hysteresis"],
        latching=config["latching"],
    )
    active: frozenset[str] = frozenset()
    trips: list[str] = []
    for step in sequence:
        assert isinstance(step, dict)
        result = sd.evaluate_protection(
            (limit,), {config["variable"]: step["value"]}, active=active
        )
        active = frozenset(result.active)
        trips.extend(result.trips)
        assert (config["name"] in active) is step["expectActive"]
    assert trips == [config["name"]]


def test_advphys06_latching_protection_stays_tripped() -> None:
    limit = sd.ProtectionLimit(
        name="overtemp",
        kind=sd.ProtectionKind.OVERTEMPERATURE,
        variable="temperature_k",
        unit="K",
        threshold=400.0,
        direction="high",
        hysteresis=5.0,
        latching=True,
    )
    first = sd.evaluate_protection((limit,), {"temperature_k": 500.0})
    assert first.active == ("overtemp",)
    assert first.validity.passed is False
    second = sd.evaluate_protection(
        (limit,), {"temperature_k": 300.0}, active=frozenset(first.active)
    )
    assert "overtemp" in second.active
    assert second.trips == ()


def test_advphys06_protection_missing_signal_fails_closed() -> None:
    limit = sd.ProtectionLimit(
        name="overcurrent",
        kind=sd.ProtectionKind.OVERCURRENT,
        variable="current_a",
        unit="A",
        threshold=10.0,
        direction="high",
    )
    with pytest.raises(sd.TransientValidationError):
        sd.evaluate_protection((limit,), {"current_a_x": 1.0})


@pytest.mark.parametrize(
    "kind",
    [
        sd.ProtectionKind.OVERSPEED,
        sd.ProtectionKind.OVERTEMPERATURE,
        sd.ProtectionKind.OVERCURRENT,
        sd.ProtectionKind.SURGE_STALL_MARGIN,
        sd.ProtectionKind.VIBRATION_RESONANCE,
        sd.ProtectionKind.UNDERVOLTAGE,
        sd.ProtectionKind.ACTUATOR_LIMIT,
    ],
)
def test_advphys06_protection_limits_are_first_class(kind: sd.ProtectionKind) -> None:
    limit = sd.ProtectionLimit(
        name=f"limit-{kind.value}",
        kind=kind,
        variable="x",
        unit="1",
        threshold=1.0,
        direction="high",
    )
    result = sd.evaluate_protection((limit,), {"x": 2.0})
    assert limit.name in result.active
    assert result.checks[limit.name] is False


def test_advphys06_interlocks_force_safe_inputs() -> None:
    interlock = sd.InterlockSpec(
        "trip-interlock", ("overspeed",), (("shaft_torque_n_m", 0.0),)
    )
    overrides, fired = sd.apply_interlocks((interlock,), ("overspeed",))
    assert fired == ("trip-interlock",)
    assert overrides == {"shaft_torque_n_m": 0.0}
    assert sd.apply_interlocks((interlock,), ()) == ({}, ())


def test_advphys06_spool_overspeed_trip_stops_transient() -> None:
    limit = sd.ProtectionLimit(
        name="overspeed",
        kind=sd.ProtectionKind.OVERSPEED,
        variable="shaft_speed_rad_s",
        unit="rad/s",
        threshold=20.0,
        direction="high",
        hysteresis=1.0,
    )
    result = sd.simulate_transient(
        _spool_scenario(protection=(limit,), trip_policy="stop")
    )
    assert result.trips == ("overspeed",)
    assert result.validity.passed is False
    assert result.times_s[-1] < 2.0


# -- H. events ----------------------------------------------------------------


def test_advphys06_events_step_and_ramp_inputs() -> None:
    schedule = sd.EventSchedule(
        (
            sd.DiscreteEvent(0.0, sd.EventKind.STARTUP, "throttle", 0.5, "1"),
            sd.DiscreteEvent(
                1.0, sd.EventKind.COMMAND_RAMP, "throttle", 1.0, "1",
                ramp_duration_s=2.0, start_value=0.5,
            ),
            sd.DiscreteEvent(3.0, sd.EventKind.LOAD_REJECTION, "load", 0.0, "N*m"),
        )
    )
    assert schedule.inputs_at(0.5)["throttle"] == pytest.approx(0.5)
    assert schedule.inputs_at(2.0)["throttle"] == pytest.approx(0.75)
    assert schedule.inputs_at(4.0)["throttle"] == pytest.approx(1.0)
    assert schedule.fired(0.0, 1.0)[0].kind is sd.EventKind.COMMAND_RAMP
    shutdown = sd.DiscreteEvent(5.0, sd.EventKind.SHUTDOWN, "x", 0.0, "1")
    assert sd.EventKind.SHUTDOWN is shutdown.kind


def test_advphys06_transient_records_events() -> None:
    schedule = sd.EventSchedule(
        (
            sd.DiscreteEvent(0.0, sd.EventKind.STARTUP, "shaft_torque_n_m", 1.0, "N*m"),
            sd.DiscreteEvent(0.5, sd.EventKind.ACCELERATION, "shaft_torque_n_m", 2.0, "N*m"),
        )
    )
    result = sd.simulate_transient(
        _spool_scenario(events=schedule, inputs={"load_torque_n_m": 0.0})
    )
    kinds = [record.kind for record in result.events]
    assert kinds == ["startup", "acceleration"]


# -- I. solver coupling through core contracts --------------------------------


def _coupling_policy(enabled: bool) -> object:
    from aeroworkbench_core.coupling import CouplingPolicy

    return CouplingPolicy.from_strength(0.9 if enabled else 0.1)


def test_advphys06_coupling_exchange_is_deterministic_and_keyed() -> None:
    coupling = sd.SolverCoupling(
        coupling_id="shaft-exchange",
        policy=_coupling_policy(True),  # type: ignore[arg-type]
        ports=(
            sd.CouplingPort("shaft_speed_rad_s", "rad/s", "out"),
            sd.CouplingPort("load_torque_n_m", "N*m", "in"),
        ),
    )
    state = {"shaft_speed_rad_s": 12.0, "load_torque_n_m": 0.0}
    first = coupling.exchange(state, iteration=0, external={"load_torque_n_m": 0.0})
    second = coupling.exchange(state, iteration=0, external={"load_torque_n_m": 0.0})
    assert first.cache_key == second.cache_key
    assert len(first.cache_key) == 64
    assert first.converged is True
    other = coupling.exchange(
        {"shaft_speed_rad_s": 13.0, "load_torque_n_m": 0.0},
        iteration=0,
        external={"load_torque_n_m": 0.0},
    )
    assert other.cache_key != first.cache_key


def test_advphys06_coupling_disabled_fails_closed() -> None:
    coupling = sd.SolverCoupling(
        coupling_id="shaft-exchange",
        policy=_coupling_policy(False),  # type: ignore[arg-type]
        ports=(sd.CouplingPort("shaft_speed_rad_s", "rad/s", "out"),),
    )
    with pytest.raises(sd.CapabilityUnavailable):
        coupling.exchange({"shaft_speed_rad_s": 1.0})


def test_advphys06_coupling_missing_state_fails_closed() -> None:
    coupling = sd.SolverCoupling(
        coupling_id="shaft-exchange",
        policy=_coupling_policy(True),  # type: ignore[arg-type]
        ports=(sd.CouplingPort("shaft_speed_rad_s", "rad/s", "out"),),
    )
    with pytest.raises(sd.TransientValidationError):
        coupling.exchange({"not_a_state": 1.0})


# -- J. multi-domain portability ---------------------------------------------


def _multi_domain_plant() -> sd.CompositePlant:
    return sd.CompositePlant(
        "multi-domain-transient",
        (
            sd.SpoolModel(inertia_kg_m2=0.05, damping_n_m_s=0.01),
            sd.ThermalCapacitanceModel(
                heat_capacity_j_k=10.0,
                ambient_temperature_k=300.0,
                resistance_k_w=0.5,
                initial_temperature_k=300.0,
            ),
            sd.StorageVolumeModel(
                volume_m3=0.01,
                gas_constant_j_kg_k=287.0,
                temperature_k=300.0,
                specific_heat_ratio=1.4,
                initial_pressure_pa=100000.0,
            ),
            sd.BatteryStateOfChargeModel(capacity_a_s=3600.0, initial_state_of_charge=1.0),
            sd.VehicleSpeedModel(mass_kg=2.0),
        ),
    )


def test_advphys06_same_contracts_for_propulsion_and_airframe() -> None:
    fixture = _fixture("coupled_multi_domain.json")
    scenario = fixture["scenario"]
    expect = fixture["expect"]
    assert isinstance(scenario, dict) and isinstance(expect, dict)
    inputs = scenario["inputs"]
    assert isinstance(inputs, dict)
    result = sd.simulate_transient(
        sd.TransientScenario(
            scenario_id="multi-domain",
            plant=_multi_domain_plant(),
            integrator=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, scenario["stepS"]),
            duration_s=scenario["durationS"],
            inputs=inputs,
        )
    )
    for name, unit in (
        ("shaft_speed_rad_s", "rad/s"),
        ("temperature_k", "K"),
        ("pressure_pa", "Pa"),
        ("state_of_charge", "1"),
        ("speed_m_s", "m/s"),
    ):
        assert result.series_for(name).unit == unit
    assert result.series_for("shaft_speed_rad_s").final() == pytest.approx(
        expect["shaftSpeedRadS"], abs=expect["toleranceSpeedRadS"]
    )
    assert result.series_for("temperature_k").final() == pytest.approx(
        expect["temperatureK"], abs=expect["toleranceTemperatureK"]
    )
    assert result.series_for("pressure_pa").final() == pytest.approx(
        expect["pressurePa"], abs=expect["tolerancePressurePa"]
    )
    assert result.series_for("state_of_charge").final() == pytest.approx(
        expect["stateOfCharge"], abs=expect["toleranceStateOfCharge"]
    )
    assert result.series_for("speed_m_s").final() == pytest.approx(
        expect["speedMS"], abs=expect["toleranceSpeedMS"]
    )
    assert result.provenance.model == "transient-system-dynamics"


def test_advphys06_time_histories_feed_fatigue_evidence() -> None:
    result = sd.simulate_transient(_spool_scenario())
    evidence = result.fatigue_evidence()
    assert evidence["shaft_speed_rad_s"]["peak_to_peak"] > 0.0
    assert evidence["shaft_speed_rad_s"]["reversals"] == 0.0


def test_advphys06_canonical_result_is_serializable() -> None:
    canonical = sd.simulate_transient(_spool_scenario()).canonical()
    assert canonical["fidelity"] == "transient"
    assert canonical["integrator"]["method"] == "runge-kutta-4"  # type: ignore[index]
    assert canonical["provenance"]["inputsHash"]  # type: ignore[index]
    json.dumps(canonical)


# -- K. participants and capability gating ------------------------------------


def test_advphys06_participant_registry_covers_components() -> None:
    ids = sd.participant_ids()
    assert "transient-shaft-spool" in ids
    assert "transient-actuator" in ids
    assert "protection-supervisor" in ids
    assert len(sd.system_participants()) == len(sd.SYSTEM_DYNAMICS_PARTICIPANTS)


def test_advphys06_participant_ports_route_downstream() -> None:
    spool = next(
        participant
        for participant in sd.SYSTEM_DYNAMICS_PARTICIPANTS
        if participant.participant_id == "transient-shaft-spool"
    )
    targets = {port.target for port in spool.outputs}
    assert {"controls", "fatigue", "structural"} <= targets
    assert "shaft_speed_rad_s" in spool.port_names()


def test_advphys06_native_capability_is_gated_and_fails_closed() -> None:
    status = sd.native_transient_status("implicit-dae-transient-coordinator")
    assert status.state == "unavailable"
    with pytest.raises(sd.CapabilityUnavailable):
        sd.require_native_transient("implicit-dae-transient-coordinator")


def test_advphys06_native_solve_without_backend_fails_closed() -> None:
    with pytest.raises(sd.CapabilityUnavailable):
        sd.solve_native_transient(_spool_scenario())


class _FakeNativeBackend:
    backend_id = "fake-native-transient"
    software_version = "9.9.9"

    def integrate(self, scenario: sd.TransientScenario) -> sd.TransientResult:
        base = sd.simulate_transient(scenario)
        return replace(
            base,
            fidelity=sd.Fidelity.NATIVE_TRANSIENT,
            provenance=sd.native_provenance(
                "native-transient",
                scenario.canonical(),
                solver_name=self.backend_id,
                solver_version=self.software_version,
                run_id="native-run-1",
            ),
        )


class _MislabeledNativeBackend:
    backend_id = "mislabeled"
    software_version = "0.0.1"

    def integrate(self, scenario: sd.TransientScenario) -> sd.TransientResult:
        return sd.simulate_transient(scenario)


def test_advphys06_native_backend_carries_native_identity() -> None:
    result = sd.solve_native_transient(_spool_scenario(), backend=_FakeNativeBackend())
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    assert result.provenance.solver_name == "fake-native-transient"
    assert result.provenance.solver_version == "9.9.9"
    assert result.provenance.run_id == "native-run-1"
    assert result.fidelity is sd.Fidelity.NATIVE_TRANSIENT


def test_advphys06_mislabeled_native_backend_fails_closed() -> None:
    with pytest.raises(sd.TransientValidationError):
        sd.solve_native_transient(_spool_scenario(), backend=_MislabeledNativeBackend())


# -- L. record signals from controls -----------------------------------------


def test_advphys06_control_signal_is_recorded() -> None:
    controller = sd.ScheduleController(
        "sched", "target", unit="1", points=((0.0, 0.0), (1.0, 1.0))
    )
    plant = sd.FirstOrderLagModel(
        variable_name="x", unit="1", kind=sd.StateKind.CONTROL,
        time_constant_s=0.5, initial_value=0.0, target_input="target",
    )
    result = sd.simulate_transient(
        sd.TransientScenario(
            scenario_id="control-signal",
            plant=plant,
            integrator=sd.IntegratorSpec(sd.IntegrationMethod.RUNGE_KUTTA_4, 0.001),
            duration_s=1.0,
            controllers=(controller,),
            record_signals=(("target", "1"),),
        )
    )
    assert result.signal("target").final() == pytest.approx(1.0, abs=0.002)
    assert result.series_for("x").final() > 0.5
