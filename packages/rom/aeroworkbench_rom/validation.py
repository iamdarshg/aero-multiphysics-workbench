"""Cross-validation and validation-gated trust for performance maps.

A surrogate without held-out error statistics cannot be promoted as trusted.
This module holds out data with a deterministic fold split, refits a fresh model
per fold, and records actual per-output error statistics (RMSE, MAE, max
absolute error). Promotion is a separate, explicit decision.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Any

from .errors import ValidationError
from .map import MapSample, PerformanceMap
from .models import SurrogateModel

__all__ = [
    "CrossValidationReport",
    "OutputErrorStats",
    "TrustDecision",
    "assess_trust",
    "cross_validate",
    "map_trust",
]


@dataclass(frozen=True, slots=True)
class OutputErrorStats:
    """Held-out error statistics for one output."""

    name: str
    count: int
    rmse: float
    mae: float
    max_abs: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "rmse": self.rmse,
            "mae": self.mae,
            "maxAbs": self.max_abs,
        }


@dataclass(frozen=True, slots=True)
class CrossValidationReport:
    """Actual held-out error statistics for a map's model family."""

    folds: int
    sample_count: int
    seed: int
    per_output: tuple[OutputErrorStats, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "folds": self.folds,
            "sampleCount": self.sample_count,
            "seed": self.seed,
            "perOutput": [stats.as_dict() for stats in self.per_output],
        }

    def passed(self, tolerances: Mapping[str, float] | None = None) -> bool:
        limits = tolerances or {}
        return all(
            stats.rmse <= float(limits.get(stats.name, float("inf")))
            for stats in self.per_output
        )

    def failing(self, tolerances: Mapping[str, float] | None = None) -> tuple[str, ...]:
        limits = tolerances or {}
        return tuple(
            f"{stats.name}:rmse={stats.rmse:.6g}>tol={float(limits[stats.name]):.6g}"
            for stats in self.per_output
            if stats.rmse > float(limits.get(stats.name, float("inf")))
        )


@dataclass(frozen=True, slots=True)
class TrustDecision:
    """Whether a map may be consumed as trusted, with explicit reasons."""

    trusted: bool
    status: str
    reasons: tuple[str, ...]
    report: CrossValidationReport | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "trusted": self.trusted,
            "status": self.status,
            "reasons": list(self.reasons),
            "report": None if self.report is None else self.report.canonical(),
        }


def cross_validate(
    model_factory: Callable[[], SurrogateModel],
    samples: Sequence[MapSample],
    *,
    folds: int = 3,
    seed: int = 0,
) -> CrossValidationReport:
    """Deterministic k-fold cross-validation with actual error statistics."""

    if folds < 2:
        raise ValidationError("CROSS_VALIDATION_NEEDS_AT_LEAST_TWO_FOLDS")
    if len(samples) < folds:
        raise ValidationError("CROSS_VALIDATION_NEEDS_AT_LEAST_ONE_SAMPLE_PER_FOLD")
    output_names = tuple(sorted(samples[0].outputs.keys()))
    for sample in samples:
        if tuple(sorted(sample.outputs.keys())) != output_names:
            raise ValidationError("CROSS_VALIDATION_SAMPLE_OUTPUTS_MISMATCH")
    identifiers = sorted(sample.sample_id for sample in samples)
    rng = random.Random(seed)
    rng.shuffle(identifiers)
    assignment = {sample_id: index % folds for index, sample_id in enumerate(identifiers)}
    by_id = {sample.sample_id: sample for sample in samples}
    errors: dict[str, list[float]] = {name: [] for name in output_names}
    for fold in range(folds):
        train = [by_id[sid] for sid in identifiers if assignment[sid] != fold]
        test = [by_id[sid] for sid in identifiers if assignment[sid] == fold]
        if not train or not test:
            continue
        model = model_factory()
        model.fit(
            [dict(sample.inputs) for sample in train],
            [dict(sample.outputs) for sample in train],
        )
        for sample in test:
            prediction = model.predict(dict(sample.inputs))
            for name in output_names:
                errors[name].append(prediction.outputs[name] - sample.outputs[name])
    stats: list[OutputErrorStats] = []
    for name in output_names:
        values = errors[name]
        if not values:
            raise ValidationError(f"CROSS_VALIDATION_NO_HELD_OUT_ERRORS:{name}")
        count = len(values)
        rmse = sqrt(sum(value * value for value in values) / count)
        mae = sum(abs(value) for value in values) / count
        max_abs = max(abs(value) for value in values)
        stats.append(OutputErrorStats(name, count, rmse, mae, max_abs))
    return CrossValidationReport(
        folds=folds, sample_count=len(samples), seed=seed, per_output=tuple(stats)
    )


def assess_trust(
    report: CrossValidationReport | None,
    tolerances: Mapping[str, float] | None = None,
) -> TrustDecision:
    """Promote a surrogate only when a held-out report satisfies tolerances."""

    if report is None:
        return TrustDecision(False, "unvalidated", ("no cross-validation report",), None)
    if report.passed(tolerances):
        return TrustDecision(True, "validated", ("held-out error within tolerance",), report)
    failing = report.failing(tolerances)
    return TrustDecision(False, "failed", failing, report)


def map_trust(
    performance_map: PerformanceMap, tolerances: Mapping[str, float] | None = None
) -> TrustDecision:
    report = performance_map.validation
    if not isinstance(report, CrossValidationReport):
        return TrustDecision(False, "unvalidated", ("map carries no validation report",), None)
    return assess_trust(report, tolerances)
