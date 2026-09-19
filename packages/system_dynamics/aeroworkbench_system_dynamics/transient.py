"""Transient coordinator: events, controls, actuators, protection, coupling.

The coordinator advances a typed plant state with a declared deterministic
integrator while discrete events inject input overrides, controllers and
actuators shape commands under their limits, protection limits trip with
hysteresis and drive interlocks, and optional solver coupling exchanges state
through the core coupling contracts. Steady operating points are solved
separately and reported at a distinct fidelity.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import ceil

from .actuators import ActuatorSpec
from .controls import Controller
from .coupling import SolverCoupling
from .errors import TransientValidationError
from .events import EventSchedule
from .integrators import IntegrationMethod, IntegratorSpec, advance
from .models import PlantModel
from .protection import (
    InterlockSpec,
    ProtectionLimit,
    apply_interlocks,
    evaluate_protection,
)
from .provenance import analytical_provenance
from .results import (
    EventRecord,
    IntegratorReceipt,
    SteadyStateResult,
    TimeSeries,
    TransientResult,
)
from .state import DynamicStateSpec
from .validity import Fidelity, Validity, finite

_INTEGRATION_ASSUMPTIONS = (
    "zero-order hold on inputs across each macro step",
    "protection and controls evaluated once per macro step",
)


@dataclass(frozen=True, slots=True)
class TransientScenario:
    """A deterministic, fully declared transient simulation request."""

    scenario_id: str
    plant: PlantModel
    integrator: IntegratorSpec
    duration_s: float
    inputs: Mapping[str, float] = field(default_factory=dict)
    initial_state: Mapping[str, float] = field(default_factory=dict)
    events: EventSchedule | None = None
    controllers: tuple[Controller, ...] = ()
    actuators: tuple[ActuatorSpec, ...] = ()
    protection: tuple[ProtectionLimit, ...] = ()
    interlocks: tuple[InterlockSpec, ...] = ()
    coupling: SolverCoupling | None = None
    coupling_external: Mapping[str, float] = field(default_factory=dict)
    record_signals: tuple[tuple[str, str], ...] = ()
    trip_policy: str = "continue"

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise TransientValidationError("scenario_id is required")
        finite(self.duration_s, "scenario.duration_s", positive=True)
        if self.trip_policy not in {"continue", "stop"}:
            raise TransientValidationError(f"UNKNOWN_TRIP_POLICY:{self.trip_policy}")
        for value in self.inputs.values():
            finite(value, "scenario.input")
        for value in self.coupling_external.values():
            finite(value, "scenario.coupling_external")

    def canonical(self) -> dict[str, object]:
        return {
            "scenarioId": self.scenario_id,
            "state": self.plant.state_spec().canonical(),
            "integrator": self.integrator.canonical(),
            "durationS": self.duration_s,
            "inputs": {key: self.inputs[key] for key in sorted(self.inputs)},
            "initialState": {
                key: self.initial_state[key] for key in sorted(self.initial_state)
            },
            "events": self.events.canonical() if self.events is not None else [],
            "actuators": [actuator.actuator_id for actuator in self.actuators],
            "protection": [limit.canonical() for limit in self.protection],
            "interlocks": [interlock.interlock_id for interlock in self.interlocks],
            "couplingId": None if self.coupling is None else self.coupling.coupling_id,
            "tripPolicy": self.trip_policy,
        }


def _resolve_initial(spec: DynamicStateSpec, overrides: Mapping[str, float]) -> dict[str, float]:
    state = spec.initial()
    for name, value in overrides.items():
        if name not in state:
            raise TransientValidationError(f"UNKNOWN_INITIAL_STATE:{name}")
        state[name] = finite(value, f"initial.{name}")
    return state


def simulate_transient(scenario: TransientScenario) -> TransientResult:
    """Run one deterministic transient and return a provenance-bearing result."""

    spec = scenario.plant.state_spec()
    state = _resolve_initial(spec, scenario.initial_state)
    step = scenario.integrator.step_size_s
    duration = scenario.duration_s
    steps = max(1, int(ceil(duration / step)))

    for controller in scenario.controllers:
        controller.reset()
    positions = {actuator.actuator_id: actuator.initial_position for actuator in scenario.actuators}
    active: frozenset[str] = frozenset()
    trips: list[str] = []
    times: list[float] = [0.0]
    state_history: dict[str, list[float]] = {
        name: [state[name]] for name in spec.names()
    }
    signal_history: dict[str, list[float]] = {
        name: [] for name, _unit in scenario.record_signals
    }

    def effective_inputs(time_s: float) -> dict[str, float]:
        merged = dict(scenario.inputs)
        if scenario.events is not None:
            merged.update(scenario.events.inputs_at(time_s))
        measured = scenario.plant.outputs(time_s, state, merged)
        for controller in scenario.controllers:
            merged.update(controller.update(time_s, measured, step))
        for actuator in scenario.actuators:
            command = merged.get(actuator.command_name, positions[actuator.actuator_id])
            response = actuator.step(
                command, position=positions[actuator.actuator_id], dt_s=step
            )
            positions[actuator.actuator_id] = response.position
            merged[actuator.output_name] = response.position
        if scenario.coupling is not None:
            scenario.coupling.exchange(
                state, iteration=len(times), external=scenario.coupling_external
            )
            for name in scenario.coupling.input_names():
                merged[name] = float(
                    scenario.coupling_external.get(name, state.get(name, 0.0))
                )
        return merged

    time = 0.0
    stopped = False
    for _ in range(steps):
        dt = min(step, duration - time)
        inputs = effective_inputs(time)
        measured = scenario.plant.outputs(time, state, inputs)
        protection_values = dict(state)
        protection_values.update(measured)
        protection_values.update(inputs)
        if scenario.protection:
            result = evaluate_protection(
                scenario.protection, protection_values, active=active
            )
            active = frozenset(result.active)
            trips.extend(result.trips)
            overrides, _fired = apply_interlocks(scenario.interlocks, result.active)
            if overrides:
                inputs = {**inputs, **overrides}
        for name, _unit in scenario.record_signals:
            signal_history[name].append(float(inputs.get(name, 0.0)))
        if scenario.trip_policy == "stop" and trips:
            stopped = True
            break
        state = advance(
            scenario.plant.derivative,
            scenario.integrator.method,
            time,
            state,
            dt,
            inputs,
        )
        time += dt
        times.append(time)
        for name in spec.names():
            state_history[name].append(state[name])

    for name, _unit in scenario.record_signals:
        values = signal_history[name]
        while len(values) < len(times):
            values.append(values[-1] if values else 0.0)
        del values[len(times):]

    series = tuple(
        TimeSeries(
            name=variable.name,
            unit=variable.unit,
            times_s=tuple(times),
            values=tuple(state_history[variable.name]),
        )
        for variable in spec.variables
    )
    signals = tuple(
        TimeSeries(
            name=name,
            unit=unit,
            times_s=tuple(times),
            values=tuple(signal_history[name]),
        )
        for name, unit in scenario.record_signals
    )

    events_log: list[EventRecord] = []
    if scenario.events is not None:
        final_time = times[-1]
        for event in scenario.events.ordered():
            if event.time_s <= final_time:
                events_log.append(
                    EventRecord(
                        time_s=event.time_s,
                        kind=event.kind.value,
                        target=event.target,
                        value=event.value,
                    )
                )
    checks = {
        "integration_completed": True,
        "protection_clear": not trips,
    }
    validity = Validity(
        passed=not trips,
        checks=checks,
        detail=(
            "protection limit active" if trips else
            ("stopped on trip" if stopped else "integration completed")
        ),
    )
    provenance = analytical_provenance(
        "transient-system-dynamics",
        scenario.canonical(),
        assumptions=_INTEGRATION_ASSUMPTIONS,
    )
    return TransientResult(
        scenario_id=scenario.scenario_id,
        times_s=tuple(times),
        series=series,
        signals=signals,
        fidelity=Fidelity.TRANSIENT,
        validity=validity,
        provenance=provenance,
        integrator=IntegratorReceipt(
            method=scenario.integrator.method.value,
            step_size_s=scenario.integrator.step_size_s,
            steps=steps,
            duration_s=scenario.duration_s,
            recorded_points=len(times),
        ),
        events=tuple(events_log),
        trips=tuple(dict.fromkeys(trips)),
    )


def find_steady_state(
    plant: PlantModel,
    inputs: Mapping[str, float],
    *,
    scenario_id: str = "steady-state",
    initial_state: Mapping[str, float] | None = None,
    step_s: float = 1.0,
    relaxation: float = 1.0,
    tolerance: float = 1e-9,
    max_iterations: int = 10000,
) -> SteadyStateResult:
    """Solve a steady operating point and report it at a distinct fidelity."""

    finite(step_s, "steady.step_s", positive=True)
    finite(relaxation, "steady.relaxation", positive=True)
    finite(tolerance, "steady.tolerance", positive=True)
    spec = plant.state_spec()
    state = _resolve_initial(spec, initial_state or {})
    residual = float("inf")
    for _ in range(max_iterations):
        derivative = plant.derivative(0.0, state, inputs)
        residual = max(abs(float(derivative[name])) for name in state)
        if residual <= tolerance:
            break
        state = {
            name: state[name] + relaxation * step_s * float(derivative[name])
            for name in state
        }
    converged = residual <= tolerance
    provenance = analytical_provenance(
        "steady-operating-point",
        {
            "scenarioId": scenario_id,
            "state": spec.canonical(),
            "inputs": {key: inputs[key] for key in sorted(inputs)},
            "stepS": step_s,
            "relaxation": relaxation,
        },
        assumptions=("explicit relaxation to a zero-derivative equilibrium",),
    )
    validity = Validity(
        passed=converged,
        checks={"residual_within_tolerance": converged},
        detail="steady state converged" if converged else "steady state did not settle",
    )
    return SteadyStateResult(
        scenario_id=scenario_id,
        state=tuple(sorted(state.items())),
        residual=residual,
        converged=converged,
        fidelity=Fidelity.STEADY_POINT,
        validity=validity,
        provenance=provenance,
    )


__all__ = [
    "IntegrationMethod",
    "TransientScenario",
    "find_steady_state",
    "simulate_transient",
]
