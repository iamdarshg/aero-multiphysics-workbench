"""Robust objectives: mean, variance, worst case, percentile, CVaR, risk.

Each objective is evaluated deterministically from a finite response sample.
Directions follow the campaign's convention (``minimize`` means lower is
better), so a robust objective converts directly into an existing
:class:`~aeroworkbench_optimization.drivers.StudyObjective` without changing
campaign semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import ceil, isfinite
from typing import Any

from aeroworkbench_optimization.drivers import StudyObjective

from .errors import RobustOptimizationError
from .propagation import moment_estimates, quantile

__all__ = [
    "RobustObjective",
    "RobustObjectiveKind",
    "evaluate_robust_objective",
    "robust_objective_values",
]


class RobustObjectiveKind(StrEnum):
    """The statistic a robust objective reports."""

    EXPECTED_VALUE = "expected-value"
    VARIANCE = "variance"
    STANDARD_DEVIATION = "standard-deviation"
    WORST_CASE = "worst-case"
    PERCENTILE = "percentile"
    CVAR = "cvar"
    MEAN_RISK = "mean-risk"


@dataclass(frozen=True, slots=True)
class RobustObjective:
    """A robust objective on a named response.

    ``direction`` uses the campaign vocabulary (``minimize``/``maximize``).
    ``alpha`` is the tail fraction for ``cvar`` and the confidence level for
    ``percentile``; ``risk_penalty`` weights the standard deviation for
    ``mean-risk``.
    """

    name: str
    response: str
    kind: RobustObjectiveKind
    direction: str = "minimize"
    alpha: float = 0.95
    risk_penalty: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.response.strip():
            raise RobustOptimizationError("ROBUST_OBJECTIVE_NEEDS_NAME_AND_RESPONSE")
        if self.direction not in {"minimize", "maximize"}:
            raise RobustOptimizationError(f"UNKNOWN_ROBUST_DIRECTION:{self.name}")
        if not isfinite(self.alpha) or not 0.0 < self.alpha <= 1.0:
            raise RobustOptimizationError(f"INVALID_ROBUST_ALPHA:{self.name}")
        if not isfinite(self.risk_penalty) or self.risk_penalty < 0.0:
            raise RobustOptimizationError(f"INVALID_ROBUST_RISK_PENALTY:{self.name}")
        if self.kind is RobustObjectiveKind.CVAR and self.alpha >= 1.0:
            raise RobustOptimizationError(f"CVAR_ALPHA_MUST_BE_LESS_THAN_ONE:{self.name}")

    def as_study_objective(self) -> StudyObjective:
        return StudyObjective(
            name=self.name,
            target=self.direction,
            unit="dimensionless",
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "response": self.response,
            "kind": self.kind.value,
            "direction": self.direction,
            "alpha": self.alpha,
            "riskPenalty": self.risk_penalty,
        }


def _tail_mean(values: Sequence[float], fraction: float, direction: str) -> float:
    ordered = sorted(values)
    count = max(1, min(len(ordered), ceil(fraction * len(ordered))))
    tail = ordered[-count:] if direction == "minimize" else ordered[:count]
    return sum(tail) / count


def evaluate_robust_objective(
    objective: RobustObjective, values: Sequence[float]
) -> float:
    """Evaluate one robust objective from a finite response sample."""
    if not values:
        raise RobustOptimizationError(f"ROBUST_OBJECTIVE_NEEDS_VALUES:{objective.name}")
    for value in values:
        if not isfinite(value):
            raise RobustOptimizationError(f"ROBUST_OBJECTIVE_NONFINITE:{objective.name}")
    sample = tuple(float(value) for value in values)
    kind = objective.kind
    if kind is RobustObjectiveKind.EXPECTED_VALUE:
        return sum(sample) / len(sample)
    if kind is RobustObjectiveKind.VARIANCE:
        return moment_estimates(sample).variance
    if kind is RobustObjectiveKind.STANDARD_DEVIATION:
        return moment_estimates(sample).std
    if kind is RobustObjectiveKind.WORST_CASE:
        return max(sample) if objective.direction == "minimize" else min(sample)
    if kind is RobustObjectiveKind.PERCENTILE:
        level = objective.alpha if objective.direction == "minimize" else 1.0 - objective.alpha
        return quantile(sample, level)
    if kind is RobustObjectiveKind.CVAR:
        return _tail_mean(sample, objective.alpha, objective.direction)
    if kind is RobustObjectiveKind.MEAN_RISK:
        statistics = moment_estimates(sample)
        sign = 1.0 if objective.direction == "minimize" else -1.0
        return statistics.mean + sign * objective.risk_penalty * statistics.std
    raise RobustOptimizationError(f"UNKNOWN_ROBUST_OBJECTIVE:{kind.value}")


def robust_objective_values(
    objectives: Sequence[RobustObjective],
    responses: Mapping[str, Sequence[float]],
) -> dict[str, float]:
    """Evaluate every objective; all referenced responses must be present."""
    values: dict[str, float] = {}
    for objective in objectives:
        sample = responses.get(objective.response)
        if sample is None:
            raise RobustOptimizationError(
                f"ROBUST_OBJECTIVE_UNKNOWN_RESPONSE:{objective.name}:{objective.response}"
            )
        values[objective.name] = evaluate_robust_objective(objective, sample)
    return values
