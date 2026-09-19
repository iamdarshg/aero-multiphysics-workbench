"""Bounded, deterministic sampling for uncertain inputs.

Sampling is a pure function of the plan (method, count, seed) and the declared
variables: the same request reproduces the same samples, and the samples are
content-addressed. The unit hypercube is drawn first; a Gaussian copula turns
it into correlated standard normals; each marginal inverse CDF then yields the
physical value. Model-form discrepancy is sampled on a separate derived stream
so it can never be conflated with physical (aleatory) scatter.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import sqrt
from typing import Any

from aeroworkbench_optimization.design_space import content_digest

from .contracts import CorrelationSpec, ModelFormUncertainty, UncertaintySpec
from .distributions import normal_cdf, normal_inv_cdf
from .errors import SamplingError

__all__ = [
    "DEFAULT_MAX_SAMPLES",
    "SamplingMethod",
    "SamplingPlan",
    "UncertainSamples",
    "cholesky",
    "correlation_matrix",
    "sample_model_form",
    "sample_uncertainty",
    "unit_hypercube",
]

DEFAULT_MAX_SAMPLES = 100_000


class SamplingMethod(StrEnum):
    """Supported deterministic sampling plans."""

    MONTE_CARLO = "monte-carlo"
    LATIN_HYPERCUBE = "latin-hypercube"


@dataclass(frozen=True, slots=True)
class SamplingPlan:
    """A bounded, reproducible sampling plan."""

    plan_id: str
    method: SamplingMethod = SamplingMethod.LATIN_HYPERCUBE
    count: int = 64
    seed: int = 0
    max_count: int = DEFAULT_MAX_SAMPLES

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise SamplingError("SAMPLING_PLAN_NEEDS_ID")
        if self.count <= 0:
            raise SamplingError("SAMPLING_COUNT_MUST_BE_POSITIVE")
        if self.max_count <= 0:
            raise SamplingError("SAMPLING_MAX_COUNT_MUST_BE_POSITIVE")
        if self.count > self.max_count:
            raise SamplingError(
                f"SAMPLING_COUNT_EXCEEDS_BOUND:{self.count}>{self.max_count}"
            )
        if not isinstance(self.seed, int):
            raise SamplingError("SAMPLING_SEED_MUST_BE_INTEGER")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id,
            "method": self.method.value,
            "count": self.count,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class UncertainSamples:
    """A reproducible sample set over declared input variables."""

    spec_id: str
    plan_id: str
    method: SamplingMethod
    seed: int
    names: tuple[str, ...]
    units: tuple[str, ...]
    uncertainty_classes: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        dimension = len(self.names)
        if dimension == 0:
            raise SamplingError("SAMPLES_NEED_VARIABLES")
        if len(self.units) != dimension or len(self.uncertainty_classes) != dimension:
            raise SamplingError("SAMPLE_METADATA_LENGTH_MISMATCH")
        for row in self.rows:
            if len(row) != dimension:
                raise SamplingError("SAMPLE_ROW_LENGTH_MISMATCH")

    @property
    def count(self) -> int:
        return len(self.rows)

    def as_points(self) -> tuple[dict[str, float], ...]:
        return tuple(
            dict(zip(self.names, row, strict=True)) for row in self.rows
        )

    def column(self, name: str) -> tuple[float, ...]:
        try:
            position = self.names.index(name)
        except ValueError as exc:
            raise SamplingError(f"UNKNOWN_SAMPLE_VARIABLE:{name}") from exc
        return tuple(row[position] for row in self.rows)

    def digest(self) -> str:
        return content_digest(
            {
                "specId": self.spec_id,
                "planId": self.plan_id,
                "method": self.method.value,
                "seed": self.seed,
                "names": list(self.names),
                "rows": [list(row) for row in self.rows],
            }
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "specId": self.spec_id,
            "planId": self.plan_id,
            "method": self.method.value,
            "seed": self.seed,
            "names": list(self.names),
            "units": list(self.units),
            "uncertaintyClasses": list(self.uncertainty_classes),
            "count": self.count,
            "digest": self.digest(),
        }


def unit_hypercube(plan: SamplingPlan, dimension: int) -> tuple[tuple[float, ...], ...]:
    """Deterministic unit-hypercube draws for ``dimension`` inputs."""
    if dimension <= 0:
        raise SamplingError("SAMPLING_DIMENSION_MUST_BE_POSITIVE")
    rng = random.Random(plan.seed)
    if plan.method is SamplingMethod.MONTE_CARLO:
        return tuple(
            tuple(rng.random() for _ in range(dimension)) for _ in range(plan.count)
        )
    if plan.method is SamplingMethod.LATIN_HYPERCUBE:
        columns: list[list[float]] = []
        for _ in range(dimension):
            strata = [(index + rng.random()) / plan.count for index in range(plan.count)]
            for position in range(plan.count - 1, 0, -1):
                swap = rng.randrange(position + 1)
                strata[position], strata[swap] = strata[swap], strata[position]
            columns.append(strata)
        return tuple(
            tuple(columns[axis][sample] for axis in range(dimension))
            for sample in range(plan.count)
        )
    raise SamplingError(f"UNKNOWN_SAMPLING_METHOD:{plan.method.value}")


def correlation_matrix(
    names: Sequence[str], correlations: Sequence[CorrelationSpec]
) -> tuple[tuple[float, ...], ...]:
    """Symmetric correlation matrix; identity when no correlations are declared."""
    position = {name: index for index, name in enumerate(names)}
    size = len(names)
    matrix = [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]
    for correlation in correlations:
        try:
            left = position[correlation.name_a]
            right = position[correlation.name_b]
        except KeyError as exc:
            raise SamplingError(f"CORRELATION_UNKNOWN_VARIABLE:{exc.args[0]}") from exc
        matrix[left][right] = correlation.coefficient
        matrix[right][left] = correlation.coefficient
    return tuple(tuple(row) for row in matrix)


def cholesky(matrix: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    """Lower-triangular Cholesky factor; fail closed when not positive-definite."""
    size = len(matrix)
    if size == 0:
        raise SamplingError("CHOLESKY_NEEDS_NONEMPTY_MATRIX")
    if any(len(row) != size for row in matrix):
        raise SamplingError("CHOLESKY_MATRIX_NOT_SQUARE")
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            total = matrix[row][column]
            for inner in range(column):
                total -= lower[row][inner] * lower[column][inner]
            if row == column:
                if total <= 0.0:
                    raise SamplingError("CORRELATION_MATRIX_NOT_POSITIVE_DEFINITE")
                lower[row][column] = sqrt(total)
            else:
                denominator = lower[column][column]
                if denominator == 0.0:
                    raise SamplingError("CORRELATION_MATRIX_NOT_POSITIVE_DEFINITE")
                lower[row][column] = total / denominator
    return tuple(tuple(row) for row in lower)


def _correlated_normals(
    units: tuple[tuple[float, ...], ...],
    factor: tuple[tuple[float, ...], ...],
) -> tuple[tuple[float, ...], ...]:
    transformed: list[tuple[float, ...]] = []
    for row in units:
        normals = [normal_inv_cdf(min(max(value, 1e-12), 1.0 - 1e-12)) for value in row]
        correlated: list[float] = []
        for index, factor_row in enumerate(factor):
            correlated.append(
                sum(factor_row[inner] * normals[inner] for inner in range(index + 1))
            )
        transformed.append(tuple(correlated))
    return tuple(transformed)


def sample_uncertainty(spec: UncertaintySpec, plan: SamplingPlan) -> UncertainSamples:
    """Sample every declared uncertain input reproducibly under ``plan``."""
    names = spec.names
    units = tuple(variable.unit for variable in spec.variables)
    classes = tuple(variable.uncertainty_class.value for variable in spec.variables)
    matrix = correlation_matrix(names, spec.correlations)
    units_draws = unit_hypercube(plan, len(names))
    factor = cholesky(matrix)
    normals = _correlated_normals(units_draws, factor)
    index = spec.index()
    rows: list[tuple[float, ...]] = []
    for normal_row in normals:
        values = tuple(
            index[name].distribution.ppf(min(max(normal_cdf(value), 0.0), 1.0))
            for name, value in zip(names, normal_row, strict=True)
        )
        rows.append(values)
    return UncertainSamples(
        spec_id=spec.spec_id,
        plan_id=plan.plan_id,
        method=plan.method,
        seed=plan.seed,
        names=names,
        units=units,
        uncertainty_classes=classes,
        rows=tuple(rows),
    )


def _model_form_seed(plan: SamplingPlan, fidelity: str) -> int:
    digest = hashlib.sha256(fidelity.encode("utf-8")).digest()
    offset = int.from_bytes(digest[:4], "big")
    return plan.seed + offset


def sample_model_form(
    spec: UncertaintySpec,
    plan: SamplingPlan,
    fidelity: str,
) -> tuple[float, ...] | None:
    """Sample the declared model-form discrepancy for one fidelity.

    Returns ``None`` when no model-form uncertainty is declared for the
    fidelity. The derived seed is a pure function of the plan seed and the
    fidelity name, so the stream is reproducible but distinct from the physical
    input stream.
    """
    uncertainty: ModelFormUncertainty | None = spec.model_form_for(fidelity)
    if uncertainty is None:
        return None
    derived = SamplingPlan(
        plan_id=f"{plan.plan_id}:modelform:{fidelity}",
        method=plan.method,
        count=plan.count,
        seed=_model_form_seed(plan, fidelity),
        max_count=plan.max_count,
    )
    draws = unit_hypercube(derived, 1)
    return tuple(
        uncertainty.distribution.ppf(row[0]) for row in draws
    )
