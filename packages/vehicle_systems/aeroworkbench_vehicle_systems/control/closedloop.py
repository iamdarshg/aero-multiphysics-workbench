"""Closed-loop verification: allocation, synthesized control, and handling.

:func:`evaluate_closed_loop` runs a deterministic per-axis step simulation
through the real generic controller and actuator contracts (a synthesized PID
driving an :class:`ActuatorSpec` lag/rate-limit stage into the screening
plant), measures overshoot/settling/bandwidth from the simulated response,
merges mode-derived metrics, and checks the handling-quality constraints. An
infeasible allocation, an unsettled loop, or a violated handling constraint
makes the report infeasible; the flight-test seam compares predicted metrics
against measured data without inventing agreement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_optimization.drivers import StudyConstraint
from aeroworkbench_optimization.quality import PhysicsFlags
from aeroworkbench_system_dynamics.actuators import ActuatorSpec

from .allocation import AllocationResult
from .contracts import ControlMeta, result_meta
from .errors import ControlContractError, HandlingQualityError
from .handling import (
    HandlingMetric,
    HandlingQualityConstraint,
    HandlingQualityReport,
    evaluate_handling_qualities,
    handling_study_constraint,
)
from .synthesis import AxisGains, AxisPlant

__all__ = [
    "AxisLoop",
    "ClosedLoopReport",
    "ClosedLoopSpec",
    "FlightTestComparison",
    "StepMetrics",
    "closed_loop_campaign_evaluator",
    "closed_loop_study_constraints",
    "compare_flight_test",
    "evaluate_closed_loop",
    "simulate_step",
]


@dataclass(frozen=True, slots=True)
class AxisLoop:
    """One closed axis: screening plant, synthesized gains, actuator, step."""

    plant: AxisPlant
    gains: AxisGains
    actuator: ActuatorSpec
    step_command_rad: float
    output_min: float | None = None
    output_max: float | None = None

    def __post_init__(self) -> None:
        if self.plant.axis != self.gains.axis:
            raise ControlContractError("LOOP_PLANT_GAINS_AXIS_MISMATCH")
        value = self.step_command_rad
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ControlContractError("NONFINITE_VALUE:loop.stepCommand")
        if not isfinite(float(value)):
            raise ControlContractError("NONFINITE_VALUE:loop.stepCommand")

    def canonical(self) -> dict[str, Any]:
        return {
            "plant": self.plant.canonical(),
            "gains": self.gains.canonical(),
            "actuator": self.actuator.actuator_id,
            "stepCommandRad": float(self.step_command_rad),
            "outputMin": self.output_min,
            "outputMax": self.output_max,
        }


@dataclass(frozen=True, slots=True)
class ClosedLoopSpec:
    """Closed-loop verification problem: loops, constraints, and horizons."""

    loops: tuple[AxisLoop, ...]
    handling: tuple[HandlingQualityConstraint, ...]
    mode_metrics: tuple[tuple[str, float], ...] = ()
    dt_s: float = 0.005
    steps: int = 2000
    allocation: AllocationResult | None = None

    def __post_init__(self) -> None:
        if not self.loops:
            raise ControlContractError("CLOSED_LOOP_NEEDS_LOOPS")
        if not self.handling:
            raise ControlContractError("CLOSED_LOOP_NEEDS_HANDLING")
        axes = [loop.plant.axis for loop in self.loops]
        if len(set(axes)) != len(axes):
            raise ControlContractError("DUPLICATE_CLOSED_LOOP_AXIS")
        if isinstance(self.dt_s, bool) or not isinstance(self.dt_s, (int, float)):
            raise ControlContractError("NONFINITE_VALUE:closedLoop.dt_s")
        if not isfinite(float(self.dt_s)) or float(self.dt_s) <= 0.0:
            raise ControlContractError("CLOSED_LOOP_DT_MUST_BE_POSITIVE")
        if not isinstance(self.steps, int) or isinstance(self.steps, bool) or self.steps < 100:
            raise ControlContractError("CLOSED_LOOP_STEPS_TOO_FEW")

    def canonical(self) -> dict[str, Any]:
        return {
            "loops": [
                loop.canonical() for loop in sorted(self.loops, key=lambda item: item.plant.axis)
            ],
            "handling": [constraint.canonical() for constraint in self.handling],
            "modeMetrics": {key: value for key, value in sorted(self.mode_metrics)},
            "dtS": float(self.dt_s),
            "steps": self.steps,
            "allocationFeasible": None if self.allocation is None else self.allocation.feasible,
        }


@dataclass(frozen=True, slots=True)
class StepMetrics:
    """Measured step-response metrics for one axis."""

    axis: str
    overshoot: float
    settling_time_s: float | None
    rise_time_s: float | None
    bandwidth_hz: float | None
    steady_error: float
    settled: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "overshoot": self.overshoot,
            "settlingTimeS": self.settling_time_s,
            "riseTimeS": self.rise_time_s,
            "bandwidthHz": self.bandwidth_hz,
            "steadyError": self.steady_error,
            "settled": self.settled,
        }


@dataclass(frozen=True, slots=True)
class ClosedLoopReport:
    """Closed-loop verdict with step metrics, handling checks, and provenance."""

    feasible: bool
    steps: tuple[StepMetrics, ...]
    handling: HandlingQualityReport
    metrics: tuple[tuple[str, float], ...]
    reasons: tuple[str, ...]
    meta: ControlMeta

    def metric(self, name: str) -> float:
        for key, value in self.metrics:
            if key == name:
                return value
        raise HandlingQualityError(f"UNKNOWN_CLOSED_LOOP_METRIC:{name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "steps": [item.canonical() for item in self.steps],
            "handling": self.handling.as_dict(),
            "metrics": {key: value for key, value in self.metrics},
            "reasons": list(self.reasons),
            "meta": self.meta.as_dict(),
        }

    def canonical(self) -> dict[str, Any]:
        payload = self.as_dict()
        payload["metrics"] = {key: value for key, value in sorted(self.metrics)}
        return payload

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def simulate_step(loop: AxisLoop, *, dt_s: float, steps: int) -> StepMetrics:
    """Simulate one axis step through the PID and actuator contracts."""
    plant = loop.plant
    pid = loop.gains.to_pid(
        f"closed-loop-{plant.axis}",
        setpoint=float(loop.step_command_rad),
        output_min=loop.output_min,
        output_max=loop.output_max,
    )
    pid.reset()
    position = loop.actuator.initial_position
    theta = 0.0
    omega = 0.0
    responses: list[float] = []
    command = float(loop.step_command_rad)
    peak = 0.0
    for _ in range(steps):
        measured = {
            f"{plant.axis}_angle": theta,
            f"{plant.axis}_rate": omega,
        }
        deflection_demand = float(pid.update(0.0, measured, dt_s)[f"{plant.axis}_deflection"])
        result = loop.actuator.step(deflection_demand, position=position, dt_s=dt_s)
        position = result.position
        applied = plant.effectiveness * position
        alpha = (applied - plant.damping * omega - plant.stiffness * theta) / plant.inertia
        omega += alpha * dt_s
        theta += omega * dt_s
        responses.append(theta)
        if abs(theta) > abs(peak):
            peak = theta
    steady = responses[-1]
    if command == 0.0:
        overshoot = 0.0 if peak == 0.0 else float("inf")
    else:
        overshoot = max(0.0, (abs(peak) - abs(command)) / abs(command))
    if overshoot == float("inf"):
        raise HandlingQualityError(f"DIVERGENT_STEP_RESPONSE:{plant.axis}")
    band = 0.02 * abs(command)
    settled_index: int | None = None
    for index in range(len(responses) - 1, -1, -1):
        if abs(responses[index] - command) > band:
            settled_index = index + 1
            break
    settled = settled_index is not None and settled_index < len(responses)
    settling_time = None if settled_index is None else settled_index * dt_s
    rise_time: float | None = None
    if command != 0.0:
        low_mark = 0.1 * command
        high_mark = 0.9 * command
        low_at: int | None = None
        high_at: int | None = None
        for index, value in enumerate(responses):
            if low_at is None and (
                (command > 0.0 and value >= low_mark) or (command < 0.0 and value <= low_mark)
            ):
                low_at = index
            if low_at is not None and (
                (command > 0.0 and value >= high_mark) or (command < 0.0 and value <= high_mark)
            ):
                high_at = index
                break
        if low_at is not None and high_at is not None and high_at > low_at:
            rise_time = (high_at - low_at) * dt_s
    bandwidth = 0.35 / rise_time if rise_time is not None and rise_time > 0.0 else None
    return StepMetrics(
        axis=plant.axis,
        overshoot=overshoot,
        settling_time_s=settling_time,
        rise_time_s=rise_time,
        bandwidth_hz=bandwidth,
        steady_error=abs(steady - command),
        settled=settled and (settling_time is not None),
    )


def evaluate_closed_loop(spec: ClosedLoopSpec) -> ClosedLoopReport:
    """Run every axis step, merge metrics, and check handling constraints."""
    steps = tuple(
        simulate_step(loop, dt_s=float(spec.dt_s), steps=spec.steps) for loop in spec.loops
    )
    reasons: list[str] = []
    if spec.allocation is not None and not spec.allocation.feasible:
        reasons.append("ALLOCATION_INFEASIBLE")
        reasons.extend(f"ALLOC:{reason}" for reason in spec.allocation.reasons)
    for item in steps:
        if not item.settled:
            reasons.append(f"LOOP_NOT_SETTLED:{item.axis}")
    metrics: dict[str, float] = dict(spec.mode_metrics)
    overshoots = [item.overshoot for item in steps]
    settling = [item.settling_time_s for item in steps if item.settling_time_s is not None]
    bandwidths = [item.bandwidth_hz for item in steps if item.bandwidth_hz is not None]
    metrics[HandlingMetric.OVERSHOOT.value] = max(overshoots) if overshoots else 0.0
    if settling:
        metrics[HandlingMetric.SETTLING_TIME_S.value] = max(settling)
    if bandwidths:
        metrics[HandlingMetric.BANDWIDTH_HZ.value] = min(bandwidths)
    handling = evaluate_handling_qualities(metrics, spec.handling)
    if not handling.feasible:
        reasons.append("HANDLING_CONSTRAINT_VIOLATED")
    feasible = handling.feasible and not reasons
    ordered = tuple(sorted(metrics.items()))
    inputs: dict[str, Any] = {
        "spec": spec.canonical(),
        "steps": [item.canonical() for item in steps],
        "metrics": dict(ordered),
    }
    meta = result_meta(
        model="vehicle-closed-loop",
        inputs=inputs,
        valid=feasible,
        checks=tuple(
            [(check.name, check.passed) for check in handling.checks]
            + [("loops-settled", all(item.settled for item in steps))]
            + [
                (
                    "allocation-feasible",
                    True if spec.allocation is None else spec.allocation.feasible,
                )
            ]
        ),
        detail="closed loop feasible" if feasible else ";".join(reasons),
        assumptions=(
            "per-axis screening plant with PID moment actuation",
            "actuator lag and rate limits applied through the generic actuator contract",
            "bandwidth estimated as 0.35 over 10-90% rise time",
        ),
    )
    return ClosedLoopReport(
        feasible=feasible,
        steps=steps,
        handling=handling,
        metrics=ordered,
        reasons=tuple(reasons),
        meta=meta,
    )


def closed_loop_study_constraints(
    constraints: tuple[HandlingQualityConstraint, ...],
) -> tuple[StudyConstraint, ...]:
    """Expose handling constraints as campaign constraints."""
    return tuple(handling_study_constraint(constraint) for constraint in constraints)


def closed_loop_campaign_evaluator(
    spec: ClosedLoopSpec,
) -> Any:
    """Build a campaign evaluator closure over a closed-loop verification."""

    def evaluate(
        point: Mapping[str, float], operating_point: str
    ) -> tuple[Mapping[str, float], PhysicsFlags]:
        del point, operating_point
        report = evaluate_closed_loop(spec)
        outputs = {key: float(value) for key, value in report.metrics}
        outputs["feasible"] = 1.0 if report.feasible else 0.0
        flags = PhysicsFlags(
            converged=all(item.settled for item in report.steps),
            closure_passed=report.feasible,
            validity_ok=report.feasible,
        )
        return outputs, flags

    return evaluate


@dataclass(frozen=True, slots=True)
class FlightTestComparison:
    """Predicted-versus-measured metric comparison with an explicit verdict."""

    residuals: tuple[tuple[str, float], ...]
    passed: bool
    reasons: tuple[str, ...]
    meta: ControlMeta

    def as_dict(self) -> dict[str, Any]:
        return {
            "residuals": {key: value for key, value in self.residuals},
            "passed": self.passed,
            "reasons": list(self.reasons),
            "meta": self.meta.as_dict(),
        }


def compare_flight_test(
    predicted: Mapping[str, float],
    measured: Mapping[str, float],
    tolerances: Mapping[str, float],
) -> FlightTestComparison:
    """Compare predicted handling metrics against flight-test data, fail closed."""
    if not tolerances:
        raise ControlContractError("FLIGHT_TEST_NEEDS_TOLERANCES")
    residuals: list[tuple[str, float]] = []
    reasons: list[str] = []
    for name in sorted(tolerances):
        tolerance = float(tolerances[name])
        if tolerance < 0.0:
            raise ControlContractError(f"FLIGHT_TEST_TOLERANCE_NEGATIVE:{name}")
        if name not in predicted:
            raise HandlingQualityError(f"FLIGHT_TEST_PREDICTION_MISSING:{name}")
        if name not in measured:
            raise HandlingQualityError(f"FLIGHT_TEST_MEASUREMENT_MISSING:{name}")
        residual = abs(float(predicted[name]) - float(measured[name]))
        residuals.append((name, residual))
        if residual > tolerance:
            reasons.append(f"FLIGHT_TEST_MISMATCH:{name}")
    passed = not reasons
    inputs: dict[str, Any] = {
        "predicted": {key: float(predicted[key]) for key in sorted(tolerances)},
        "measured": {key: float(measured[key]) for key in sorted(tolerances)},
        "tolerances": {key: float(tolerances[key]) for key in sorted(tolerances)},
    }
    residual_map = dict(residuals)
    meta = result_meta(
        model="vehicle-flight-test-comparison",
        inputs=inputs,
        valid=passed,
        checks=tuple(
            (name, residual_map[name] <= float(tolerances[name])) for name in sorted(tolerances)
        ),
        detail="flight-test comparison passed" if passed else ";".join(reasons),
        assumptions=("predicted and measured metrics share definitions and units",),
    )
    return FlightTestComparison(
        residuals=tuple(residuals),
        passed=passed,
        reasons=tuple(reasons),
        meta=meta,
    )
