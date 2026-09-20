"""Typed handling-quality constraints over damping, frequency, CAP, and roll.

A :class:`HandlingQualityConstraint` names one handling metric, a bound, a
limit, and the declared standard or source behind the limit (for example a
named military standard or an analytical screening assumption). Metrics are
computed from AIRFRAME 05 dynamic-stability modes and from the closed-loop
step response; :func:`evaluate_handling_qualities` checks every constraint
and :func:`handling_study_constraint` exposes each one as an optimization
campaign constraint so handling qualities participate in campaign feasibility.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_airframe.trim.dynamics import FlightMode
from aeroworkbench_optimization.drivers import StudyConstraint
from aeroworkbench_optimization.quality import PhysicsFlags

from .contracts import ControlMeta, result_meta
from .errors import ControlContractError, HandlingQualityError

__all__ = [
    "HandlingMetric",
    "HandlingQualityCheck",
    "HandlingQualityConstraint",
    "HandlingQualityReport",
    "control_anticipation_parameter",
    "evaluate_handling_qualities",
    "handling_campaign_outputs",
    "handling_evaluator",
    "handling_study_constraint",
    "mode_metrics",
    "roll_time_constant",
]


class HandlingMetric(StrEnum):
    """Handling-quality metrics this package can evaluate."""

    SHORT_PERIOD_DAMPING = "short_period_damping"
    SHORT_PERIOD_FREQUENCY_HZ = "short_period_frequency_hz"
    PHUGOID_DAMPING = "phugoid_damping"
    DUTCH_ROLL_DAMPING = "dutch_roll_damping"
    DUTCH_ROLL_FREQUENCY_HZ = "dutch_roll_frequency_hz"
    CAP = "cap"
    ROLL_TIME_CONSTANT_S = "roll_time_constant_s"
    OVERSHOOT = "overshoot"
    SETTLING_TIME_S = "settling_time_s"
    BANDWIDTH_HZ = "bandwidth_hz"


_METRIC_UNITS = {
    HandlingMetric.SHORT_PERIOD_DAMPING: "1",
    HandlingMetric.SHORT_PERIOD_FREQUENCY_HZ: "Hz",
    HandlingMetric.PHUGOID_DAMPING: "1",
    HandlingMetric.DUTCH_ROLL_DAMPING: "1",
    HandlingMetric.DUTCH_ROLL_FREQUENCY_HZ: "Hz",
    HandlingMetric.CAP: "1/s2",
    HandlingMetric.ROLL_TIME_CONSTANT_S: "s",
    HandlingMetric.OVERSHOOT: "1",
    HandlingMetric.SETTLING_TIME_S: "s",
    HandlingMetric.BANDWIDTH_HZ: "Hz",
}


@dataclass(frozen=True, slots=True)
class HandlingQualityConstraint:
    """One typed handling-quality requirement with its declared standard."""

    name: str
    metric: HandlingMetric
    bound: str
    limit: float
    standard: str
    unit: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ControlContractError("HANDLING_CONSTRAINT_NAME_REQUIRED")
        if self.bound not in {"lower", "upper"}:
            raise ControlContractError(f"UNKNOWN_HANDLING_BOUND:{self.name}")
        if not self.standard.strip():
            raise ControlContractError(f"HANDLING_STANDARD_REQUIRED:{self.name}")
        value = self.limit
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ControlContractError(f"NONFINITE_VALUE:handling.{self.name}")
        if float(value) != float(value) or float(value) in (float("inf"), float("-inf")):
            raise ControlContractError(f"NONFINITE_VALUE:handling.{self.name}")
        expected = _METRIC_UNITS[self.metric]
        if self.unit and self.unit != expected:
            raise ControlContractError(f"HANDLING_UNIT_MISMATCH:{self.name}")
        object.__setattr__(self, "unit", self.unit or expected)

    def satisfied_by(self, value: float) -> bool:
        if self.bound == "lower":
            return value >= self.limit
        return value <= self.limit

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metric": self.metric.value,
            "bound": self.bound,
            "limit": self.limit,
            "standard": self.standard,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class HandlingQualityCheck:
    """One evaluated constraint: metric value, verdict, and margin."""

    name: str
    metric: str
    value: float
    limit: float
    bound: str
    passed: bool
    margin: float
    standard: str

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metric": self.metric,
            "value": self.value,
            "limit": self.limit,
            "bound": self.bound,
            "passed": self.passed,
            "margin": self.margin,
            "standard": self.standard,
        }


@dataclass(frozen=True, slots=True)
class HandlingQualityReport:
    """Handling-quality verdict with per-constraint checks and provenance."""

    checks: tuple[HandlingQualityCheck, ...]
    feasible: bool
    meta: ControlMeta

    def check(self, name: str) -> HandlingQualityCheck:
        for item in self.checks:
            if item.name == name:
                return item
        raise HandlingQualityError(f"UNKNOWN_HANDLING_CHECK:{name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "checks": [item.canonical() for item in self.checks],
            "feasible": self.feasible,
            "meta": self.meta.as_dict(),
        }


def _mode_by_kind(modes: tuple[FlightMode, ...], kind: str) -> FlightMode:
    matches = [mode for mode in modes if mode.kind == kind]
    if not matches:
        raise HandlingQualityError(f"HANDLING_MODE_UNAVAILABLE:{kind}")
    matches.sort(key=lambda mode: (mode.damping_ratio, mode.frequency_hz))
    return matches[0]


def control_anticipation_parameter(
    short_period_freq_rad_s: float, load_per_alpha_g: float
) -> float:
    """Control anticipation parameter: omega_sp^2 divided by load per alpha."""
    if not short_period_freq_rad_s > 0.0:
        raise HandlingQualityError("CAP_NEEDS_POSITIVE_FREQUENCY")
    if not load_per_alpha_g > 0.0:
        raise HandlingQualityError("CAP_NEEDS_POSITIVE_LOAD_PER_ALPHA")
    return (short_period_freq_rad_s * short_period_freq_rad_s) / load_per_alpha_g


def roll_time_constant(roll_mode: FlightMode) -> float:
    """Roll-mode time constant from the aperiodic root, failing closed."""
    if roll_mode.kind != "roll":
        raise HandlingQualityError("ROLL_METRIC_NEEDS_ROLL_MODE")
    if roll_mode.real >= 0.0:
        raise HandlingQualityError("DIVERGENT_ROLL_MODE")
    return -1.0 / roll_mode.real


def mode_metrics(
    longitudinal: tuple[FlightMode, ...],
    lateral: tuple[FlightMode, ...],
    *,
    load_per_alpha_g: float | None = None,
) -> dict[str, float]:
    """Extract handling metrics from classified dynamic-stability modes."""
    short_period = _mode_by_kind(longitudinal, "short-period")
    phugoid = _mode_by_kind(longitudinal, "phugoid")
    dutch_roll = _mode_by_kind(lateral, "dutch-roll")
    roll = _mode_by_kind(lateral, "roll")
    metrics: dict[str, float] = {
        HandlingMetric.SHORT_PERIOD_DAMPING.value: short_period.damping_ratio,
        HandlingMetric.SHORT_PERIOD_FREQUENCY_HZ.value: short_period.frequency_hz,
        HandlingMetric.PHUGOID_DAMPING.value: phugoid.damping_ratio,
        HandlingMetric.DUTCH_ROLL_DAMPING.value: dutch_roll.damping_ratio,
        HandlingMetric.DUTCH_ROLL_FREQUENCY_HZ.value: dutch_roll.frequency_hz,
        HandlingMetric.ROLL_TIME_CONSTANT_S.value: roll_time_constant(roll),
    }
    if load_per_alpha_g is not None:
        import math

        metrics[HandlingMetric.CAP.value] = control_anticipation_parameter(
            2.0 * math.pi * short_period.frequency_hz, load_per_alpha_g
        )
    return metrics


def evaluate_handling_qualities(
    metrics: Mapping[str, float],
    constraints: tuple[HandlingQualityConstraint, ...],
) -> HandlingQualityReport:
    """Check every handling constraint against computed metrics, fail closed."""
    if not constraints:
        raise ControlContractError("HANDLING_NEEDS_CONSTRAINTS")
    names = [constraint.name for constraint in constraints]
    if len(set(names)) != len(names):
        raise ControlContractError("DUPLICATE_HANDLING_CONSTRAINT")
    checks: list[HandlingQualityCheck] = []
    for constraint in constraints:
        if constraint.metric.value not in metrics:
            raise HandlingQualityError(
                f"HANDLING_METRIC_UNAVAILABLE:{constraint.metric.value}"
            )
        value = float(metrics[constraint.metric.value])
        if value != value or value in (float("inf"), float("-inf")):
            raise HandlingQualityError(f"NONFINITE_HANDLING_METRIC:{constraint.metric.value}")
        passed = constraint.satisfied_by(value)
        if constraint.bound == "lower":
            margin = value - constraint.limit
        else:
            margin = constraint.limit - value
        checks.append(
            HandlingQualityCheck(
                name=constraint.name,
                metric=constraint.metric.value,
                value=value,
                limit=constraint.limit,
                bound=constraint.bound,
                passed=passed,
                margin=margin,
                standard=constraint.standard,
            )
        )
    feasible = all(check.passed for check in checks)
    inputs: dict[str, Any] = {
        "metrics": dict(sorted((key, float(value)) for key, value in metrics.items())),
        "constraints": [constraint.canonical() for constraint in constraints],
    }
    standards = sorted({constraint.standard for constraint in constraints})
    meta = result_meta(
        model="vehicle-handling-qualities",
        inputs=inputs,
        valid=feasible,
        checks=tuple((check.name, check.passed) for check in checks),
        detail="handling qualities feasible" if feasible else "handling constraint violated",
        assumptions=tuple(
            ["metrics computed from linearized modes and closed-loop step response"]
            + [f"limit source: {standard}" for standard in standards]
        ),
    )
    return HandlingQualityReport(checks=tuple(checks), feasible=feasible, meta=meta)


def handling_study_constraint(constraint: HandlingQualityConstraint) -> StudyConstraint:
    """Expose one handling constraint as an optimization campaign constraint."""
    return StudyConstraint(
        constraint.name, constraint.bound, constraint.limit, constraint.unit
    )


def handling_campaign_outputs(report: HandlingQualityReport) -> dict[str, float]:
    """Campaign outputs keyed by constraint name for feasibility ranking."""
    return {check.name: check.value for check in report.checks}


def handling_evaluator(
    metrics: Mapping[str, float],
    constraints: tuple[HandlingQualityConstraint, ...],
) -> tuple[dict[str, float], PhysicsFlags]:
    """Evaluate handling qualities as a campaign evaluator output."""
    report = evaluate_handling_qualities(metrics, constraints)
    outputs = handling_campaign_outputs(report)
    flags = PhysicsFlags(
        converged=True,
        closure_passed=report.feasible,
        validity_ok=report.feasible,
    )
    return outputs, flags
