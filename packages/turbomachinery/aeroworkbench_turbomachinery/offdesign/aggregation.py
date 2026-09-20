"""Multi-point objective aggregation: weighted, worst-case, minimax, robust, Pareto."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from ..canonical import content_digest
from .errors import OffdesignInputError
from .matching import PointMatch

AGGREGATION_MODES: tuple[str, ...] = (
    "weighted",
    "worst_case",
    "minimax",
    "percentile",
    "pareto",
)


class AggregationMode(StrEnum):
    WEIGHTED = "weighted"
    WORST_CASE = "worst_case"
    MINIMAX = "minimax"
    PERCENTILE = "percentile"
    PARETO = "pareto"


@dataclass(frozen=True, slots=True)
class PointObjective:
    """Scalar objective values extracted from one matched point."""

    point_id: str
    values: tuple[tuple[str, float], ...]
    hard_passed: bool

    def value(self, name: str) -> float:
        for key, item in self.values:
            if key == name:
                return item
        raise OffdesignInputError(f"OBJECTIVE_UNKNOWN:{name}:{self.point_id}")

    def canonical(self) -> dict[str, object]:
        return {
            "pointId": self.point_id,
            "values": [[name, value] for name, value in self.values],
            "hardPassed": self.hard_passed,
        }


@dataclass(frozen=True, slots=True)
class AggregateOutcome:
    """One aggregated objective; score is None when a hard violation propagates."""

    objective: str
    mode: str
    score: float | None
    passed: bool
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "objective": self.objective,
            "mode": self.mode,
            "score": self.score,
            "passed": self.passed,
            "detail": self.detail,
        }


def objectives_from_matches(
    matches: tuple[PointMatch, ...],
    objectives: tuple[str, ...] = ("thrust_n", "shaft_power_w"),
) -> tuple[PointObjective, ...]:
    extracted: list[PointObjective] = []
    for match in matches:
        metrics = {
            "thrust_n": match.thrust_n,
            "shaft_power_w": match.shaft_power_w,
            "max_residual": match.max_residual,
            "surge_margin": match.surge_margin,
        }
        values: list[tuple[str, float]] = []
        for name in objectives:
            if name not in metrics:
                raise OffdesignInputError(f"OBJECTIVE_UNKNOWN:{name}")
            value = metrics[name]
            if not isfinite(value):
                raise OffdesignInputError(f"OBJECTIVE_NONFINITE:{name}:{match.point_id}")
            values.append((name, value))
        extracted.append(
            PointObjective(
                point_id=match.point_id,
                values=tuple(values),
                hard_passed=match.hard_passed,
            )
        )
    return tuple(extracted)


def _weights(
    entries: tuple[PointObjective, ...], weights: dict[str, float] | None
) -> list[float]:
    if weights is None:
        return [1.0 for _ in entries]
    result: list[float] = []
    for entry in entries:
        weight = weights.get(entry.point_id, 1.0)
        if not isfinite(weight) or weight < 0.0:
            raise OffdesignInputError(f"AGGREGATION_WEIGHT_INVALID:{entry.point_id}")
        result.append(weight)
    return result


def aggregate_objective(
    entries: tuple[PointObjective, ...],
    objective: str,
    mode: AggregationMode = AggregationMode.WEIGHTED,
    *,
    weights: dict[str, float] | None = None,
    percentile: float = 50.0,
    maximize: bool = True,
) -> AggregateOutcome:
    if not entries:
        raise OffdesignInputError("AGGREGATION_NEEDS_ENTRIES")
    if mode.value not in AGGREGATION_MODES:
        raise OffdesignInputError(f"AGGREGATION_UNKNOWN_MODE:{mode}")
    if not all(entry.hard_passed for entry in entries):
        failed = sorted(
            entry.point_id for entry in entries if not entry.hard_passed
        )
        return AggregateOutcome(
            objective=objective,
            mode=mode.value,
            score=None,
            passed=False,
            detail=f"hard violation at {','.join(failed)}; not averaged away",
        )
    values = [entry.value(objective) for entry in entries]
    if mode is AggregationMode.WEIGHTED:
        applied = _weights(entries, weights)
        total = sum(applied)
        if total <= 0.0:
            raise OffdesignInputError("AGGREGATION_WEIGHTS_SUM_TO_ZERO")
        score = sum(value * weight for value, weight in zip(values, applied, strict=True)) / total
        detail = f"weighted mean over {len(values)} points"
    elif mode is AggregationMode.WORST_CASE:
        score = min(values) if maximize else max(values)
        detail = f"worst case over {len(values)} points"
    elif mode is AggregationMode.MINIMAX:
        score = max(values) if maximize else min(values)
        detail = "minimax regret proxy: best single-point value"
    elif mode is AggregationMode.PERCENTILE:
        if not 0.0 <= percentile <= 100.0:
            raise OffdesignInputError(f"AGGREGATION_PERCENTILE_INVALID:{percentile}")
        ordered = sorted(values)
        rank = (percentile / 100.0) * (len(ordered) - 1)
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        score = ordered[low] + (rank - low) * (ordered[high] - ordered[low])
        detail = f"percentile {percentile} over {len(values)} points"
    else:
        score = sum(values) / len(values)
        detail = f"pareto mode reports mean; front computed by pareto_front ({len(values)} points)"
    return AggregateOutcome(
        objective=objective, mode=mode.value, score=score, passed=True, detail=detail
    )


def aggregate_multipoint(
    entries: tuple[PointObjective, ...],
    objectives: tuple[str, ...],
    mode: AggregationMode = AggregationMode.WEIGHTED,
    *,
    weights: dict[str, float] | None = None,
    maximize: tuple[bool, ...] | None = None,
) -> tuple[AggregateOutcome, ...]:
    directions = maximize if maximize is not None else tuple(True for _ in objectives)
    if len(directions) != len(objectives):
        raise OffdesignInputError("AGGREGATION_DIRECTION_COUNT_MISMATCH")
    return tuple(
        aggregate_objective(
            entries, name, mode, weights=weights, maximize=direction
        )
        for name, direction in zip(objectives, directions, strict=True)
    )


def pareto_front(
    entries: tuple[PointObjective, ...],
    objectives: tuple[str, ...],
    maximize: tuple[bool, ...],
) -> tuple[str, ...]:
    if len(objectives) != len(maximize):
        raise OffdesignInputError("PARETO_DIRECTION_COUNT_MISMATCH")
    feasible = [entry for entry in entries if entry.hard_passed]
    front: list[str] = []
    for candidate in feasible:
        dominated = False
        for other in feasible:
            if other.point_id == candidate.point_id:
                continue
            better_or_equal = True
            strictly_better = False
            for name, up in zip(objectives, maximize, strict=True):
                mine, theirs = candidate.value(name), other.value(name)
                if up:
                    if theirs < mine:
                        better_or_equal = False
                        break
                    if theirs > mine:
                        strictly_better = True
                elif theirs > mine:
                    better_or_equal = False
                    break
                elif theirs < mine:
                    strictly_better = True
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(candidate.point_id)
    return tuple(sorted(front))


def aggregation_digest(outcomes: tuple[AggregateOutcome, ...]) -> str:
    return content_digest([outcome.canonical() for outcome in outcomes])


__all__ = [
    "AGGREGATION_MODES",
    "AggregateOutcome",
    "AggregationMode",
    "PointObjective",
    "aggregate_multipoint",
    "aggregate_objective",
    "aggregation_digest",
    "objectives_from_matches",
    "pareto_front",
]
