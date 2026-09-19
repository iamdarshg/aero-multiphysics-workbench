"""Soft manufacturability ranking that can never rescue a hard failure.

Soft metrics are normalized proxies (0 = easiest). They only rank candidates
already accepted by the hard-limit gate; a rejected candidate has no score and
is excluded from ranking.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Protocol, runtime_checkable

__all__ = [
    "DEFAULT_SOFT_WEIGHTS",
    "SOFT_METRIC_NAMES",
    "Scorable",
    "manufacturability_score",
    "rank_by_manufacturability",
]

#: Generic soft manufacturability proxies; no application-specific logic.
SOFT_METRIC_NAMES: tuple[str, ...] = (
    "machining_time",
    "support_volume",
    "tool_changes",
    "tolerance_difficulty",
    "part_count",
    "balance_difficulty",
    "cost",
)

DEFAULT_SOFT_WEIGHTS: dict[str, float] = {
    "machining_time": 0.20,
    "support_volume": 0.15,
    "tool_changes": 0.10,
    "tolerance_difficulty": 0.15,
    "part_count": 0.10,
    "balance_difficulty": 0.10,
    "cost": 0.20,
}


def manufacturability_score(
    metrics: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
) -> float:
    """Weighted mean of provided 0..1 metrics (lower is better).

    Weights are renormalized over the metrics actually provided, so a caller
    does not have to supply all proxies. An empty metric set scores 0.0.
    """

    active_weights = dict(weights) if weights is not None else dict(DEFAULT_SOFT_WEIGHTS)
    total_weight = 0.0
    total = 0.0
    for name, value in metrics.items():
        if not isfinite(value) or value < 0:
            raise ValueError(f"INVALID_SOFT_METRIC:{name}")
        weight = active_weights.get(name, 0.0)
        if weight <= 0:
            continue
        total += weight * float(value)
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return total / total_weight


@runtime_checkable
class Scorable(Protocol):
    """The minimal report contract needed for soft ranking."""

    @property
    def admissible(self) -> bool: ...

    @property
    def score(self) -> float | None: ...


def rank_by_manufacturability(reports: Sequence[Scorable]) -> tuple[Scorable, ...]:
    """Sort admissible reports by ascending soft score; rejected never rank.

    Rejected reports are dropped, so a favourable soft metric cannot outweigh a
    hard buildability or safety violation.
    """

    admissible = [
        report for report in reports if report.admissible and report.score is not None
    ]

    def _score(report: Scorable) -> float:
        return report.score if report.score is not None else 0.0

    return tuple(sorted(admissible, key=lambda report: (_score(report), id(report))))
