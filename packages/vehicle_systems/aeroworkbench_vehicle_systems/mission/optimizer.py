"""Bounded trajectory optimization over segment controls (energy-state aware).

The optimizer trades only declared, bounded segment controls (speed, altitude,
climb rate, throttle, power fraction, configuration). Hard vehicle constraints
and reserve requirements are enforced inside every mission evaluation, so the
optimizer can never relax them: an infeasible candidate is penalized, not
accepted. The default driver is a deterministic bounded coordinate/pattern
search; ``openmdao`` delegates to the shared OpenMDAO driver seam through
``aeroworkbench_optimization``. Energy-state closure is checked for every
candidate, so a plan is only promoted when the mission closes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization import (
    DesignVariable,
    OperatingPointEval,
    PhysicsFlags,
    StudyObjective,
    run_optimize,
)
from aeroworkbench_optimization.design_space import content_digest

from .errors import MissionOptimizationError
from .evaluation import MissionResult, run_mission
from .performance import PerformanceParticipant
from .propagator import PropagationPolicy
from .segments import ControlName, MissionSpec

__all__ = [
    "ControlVariable",
    "TrajectoryOptimization",
    "TrajectoryOptimizationResult",
    "apply_controls",
    "objective_value",
    "optimize_trajectory",
    "trajectory_study",
]

_PENALTY = 1.0e12
_MINIMIZE = {"energy", "fuel", "time", "operating-cost"}


def objective_value(result: MissionResult, objective: str) -> float:
    """Map a mission result onto a scalar objective (maximize is negated)."""

    if objective == "energy":
        return result.energy_consumed_j
    if objective == "fuel":
        return result.fuel_burned_kg
    if objective == "time":
        return result.time_s
    if objective == "operating-cost":
        return result.operating_cost
    if objective == "range":
        return -result.distance_m
    if objective == "endurance":
        return -result.endurance_s
    raise MissionOptimizationError(f"UNKNOWN_TRAJECTORY_OBJECTIVE:{objective}")


@dataclass(frozen=True, slots=True)
class ControlVariable:
    """One bounded segment control the optimizer may vary."""

    segment_id: str
    control: ControlName
    lower: float
    upper: float
    initial: float

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise MissionOptimizationError("CONTROL_VARIABLE_SEGMENT_REQUIRED")
        if not (isfinite(self.lower) and isfinite(self.upper) and isfinite(self.initial)):
            raise MissionOptimizationError(f"CONTROL_VARIABLE_NONFINITE:{self.key}")
        if self.lower > self.upper:
            raise MissionOptimizationError(f"CONTROL_VARIABLE_BOUNDS_INVERTED:{self.key}")

    @property
    def key(self) -> str:
        return f"{self.segment_id}:{self.control.value}"

    def clamp(self, value: float) -> float:
        return min(max(value, self.lower), self.upper)

    def canonical(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "segmentId": self.segment_id,
            "control": self.control.value,
            "lower": self.lower,
            "upper": self.upper,
            "initial": self.initial,
        }


@dataclass(frozen=True, slots=True)
class TrajectoryOptimization:
    """A bounded trajectory-optimization request."""

    objective: str
    variables: tuple[ControlVariable, ...]
    driver: str = "coordinate"
    max_iterations: int = 40
    step_fraction: float = 0.25
    tolerance: float = 1e-6

    def __post_init__(self) -> None:
        if self.objective not in _MINIMIZE | {"range", "endurance"}:
            raise MissionOptimizationError(f"UNKNOWN_TRAJECTORY_OBJECTIVE:{self.objective}")
        if not self.variables:
            raise MissionOptimizationError("TRAJECTORY_OPTIMIZATION_NEEDS_VARIABLES")
        keys = [variable.key for variable in self.variables]
        if len(keys) != len(set(keys)):
            raise MissionOptimizationError("TRAJECTORY_OPTIMIZATION_DUPLICATE_CONTROL")
        if self.driver not in {"coordinate", "openmdao"}:
            raise MissionOptimizationError(f"UNKNOWN_TRAJECTORY_DRIVER:{self.driver}")
        if self.max_iterations <= 0:
            raise MissionOptimizationError("TRAJECTORY_OPTIMIZATION_NEEDS_ITERATIONS")
        if not 0.0 < self.step_fraction <= 1.0:
            raise MissionOptimizationError("TRAJECTORY_STEP_FRACTION_OUT_OF_RANGE")

    def canonical(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "driver": self.driver,
            "maxIterations": self.max_iterations,
            "stepFraction": self.step_fraction,
            "tolerance": self.tolerance,
            "variables": [variable.canonical() for variable in self.variables],
        }


@dataclass(frozen=True, slots=True)
class TrajectoryOptimizationResult:
    """The promoted trajectory together with its baseline and evaluation count."""

    mission_id: str
    driver: str
    objective: str
    baseline_value: float
    best_value: float
    best_controls: Mapping[str, float]
    evaluations: int
    converged: bool
    result: MissionResult
    detail: str = ""

    @property
    def feasible(self) -> bool:
        return self.result.valid

    def improvement(self) -> float:
        return self.baseline_value - self.best_value

    def canonical(self) -> dict[str, Any]:
        return {
            "missionId": self.mission_id,
            "driver": self.driver,
            "objective": self.objective,
            "baselineValue": self.baseline_value,
            "bestValue": self.best_value,
            "bestControls": dict(sorted(self.best_controls.items())),
            "evaluations": self.evaluations,
            "converged": self.converged,
            "feasible": self.feasible,
            "detail": self.detail,
            "result": self.result.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def apply_controls(
    spec: MissionSpec,
    variables: tuple[ControlVariable, ...],
    values: Mapping[str, float],
) -> MissionSpec:
    """Return a new mission with the declared controls set to bounded values."""

    segments = list(spec.segments)
    positions = {segment.segment_id: index for index, segment in enumerate(segments)}
    for variable in variables:
        value = variable.clamp(float(values.get(variable.key, variable.initial)))
        position = positions.get(variable.segment_id)
        if position is None:
            raise MissionOptimizationError(f"UNKNOWN_CONTROL_SEGMENT:{variable.segment_id}")
        segments[position] = segments[position].with_control(variable.control, value)
    return spec.with_segments(segments)


def _baseline_values(optimization: TrajectoryOptimization) -> dict[str, float]:
    return {variable.key: variable.clamp(variable.initial) for variable in optimization.variables}


def _evaluate(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    optimization: TrajectoryOptimization,
    values: Mapping[str, float],
    policy: PropagationPolicy | None,
) -> tuple[float, MissionResult]:
    candidate = apply_controls(spec, optimization.variables, values)
    result = run_mission(candidate, participant, policy=policy)
    if not result.valid:
        return _PENALTY, result
    return objective_value(result, optimization.objective), result


def _optimize_coordinate(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    optimization: TrajectoryOptimization,
    policy: PropagationPolicy | None,
) -> TrajectoryOptimizationResult:
    current = _baseline_values(optimization)
    baseline_value, baseline_result = _evaluate(spec, participant, optimization, current, policy)
    best_value = baseline_value
    best_values = dict(current)
    best_result = baseline_result
    evaluations = 1
    span = max(
        variable.upper - variable.lower for variable in optimization.variables
    )
    step = span * optimization.step_fraction
    if step <= optimization.tolerance:
        step = optimization.tolerance
    while step > optimization.tolerance:
        improved = False
        for item in optimization.variables:
            for direction in (1.0, -1.0):
                proposal = dict(current)
                proposal[item.key] = item.clamp(current[item.key] + direction * step)
                if proposal[item.key] == current[item.key]:
                    continue
                evaluations += 1
                value, result = _evaluate(spec, participant, optimization, proposal, policy)
                if value < best_value - optimization.tolerance:
                    best_value = value
                    best_values = dict(proposal)
                    best_result = result
                    current = proposal
                    improved = True
        if not improved:
            step *= 0.5
    return TrajectoryOptimizationResult(
        mission_id=spec.mission_id,
        driver="coordinate",
        objective=optimization.objective,
        baseline_value=baseline_value,
        best_value=best_value,
        best_controls=best_values,
        evaluations=evaluations,
        converged=best_result.valid,
        result=best_result,
        detail=f"bounded coordinate search; {evaluations} evaluations",
    )


def trajectory_study(optimization: TrajectoryOptimization) -> Mapping[str, object]:
    """The OpenMDAO-compatible study document for a trajectory optimization."""

    return {
        "variables": tuple(
            DesignVariable(
                name=variable.key,
                unit="dimensionless",
                kind="continuous",
                lower=variable.lower,
                upper=variable.upper,
            )
            for variable in optimization.variables
        ),
        "objectives": (StudyObjective("objective", "minimize"),),
        "constraints": (),
        "operating_points": (OperatingPointEval("nominal", 1.0),),
    }


def _optimize_openmdao(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    optimization: TrajectoryOptimization,
    policy: PropagationPolicy | None,
) -> TrajectoryOptimizationResult:
    baseline_values = _baseline_values(optimization)
    baseline_value, baseline_result = _evaluate(
        spec, participant, optimization, baseline_values, policy
    )
    evaluations = 1

    def evaluate(
        point: Mapping[str, float], operating_point: str
    ) -> tuple[Mapping[str, float], PhysicsFlags]:
        nonlocal evaluations
        del operating_point
        values = {variable.key: float(point.get(variable.key, baseline_values[variable.key]))
                  for variable in optimization.variables}
        value, result = _evaluate(spec, participant, optimization, values, policy)
        evaluations += 1
        flags = PhysicsFlags(
            converged=True,
            closure_passed=result.closure_passed,
            validity_ok=result.valid,
        )
        return {"objective": value, "valid": 1.0 if result.valid else 0.0}, flags

    study = trajectory_study(optimization)
    try:
        outcome = run_optimize(
            study,
            evaluate,
            driver="slsqp",
            max_iter=optimization.max_iterations,
        )
    except Exception as exc:  # noqa: BLE001 - optional OpenMDAO runtime; fail closed
        raise MissionOptimizationError(f"OPENMDAO_TRAJECTORY_FAILED:{exc}") from exc
    if outcome.best is None:
        raise MissionOptimizationError("TRAJECTORY_OPTIMIZATION_NO_FEASIBLE_PLAN")
    best_values = {name: float(value) for name, value in outcome.best.point}
    best_value, best_result = _evaluate(spec, participant, optimization, best_values, policy)
    return TrajectoryOptimizationResult(
        mission_id=spec.mission_id,
        driver="openmdao",
        objective=optimization.objective,
        baseline_value=baseline_value,
        best_value=min(best_value, baseline_value),
        best_controls=best_values,
        evaluations=evaluations,
        converged=best_result.valid,
        result=best_result,
        detail=f"{outcome.engine}; {evaluations} evaluations",
    )


def optimize_trajectory(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    optimization: TrajectoryOptimization,
    *,
    policy: PropagationPolicy | None = None,
) -> TrajectoryOptimizationResult:
    """Optimize the declared segment controls under fixed hard constraints."""

    if optimization.driver == "openmdao":
        return _optimize_openmdao(spec, participant, optimization, policy)
    return _optimize_coordinate(spec, participant, optimization, policy)
