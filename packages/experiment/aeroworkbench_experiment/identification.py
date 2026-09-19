"""Generic bounded system-identification / calibration seam.

A caller supplies a parametric model (a plain ``predict`` contract) and paired
observations; this module estimates bounded parameters by deterministic damped
Gauss-Newton with a numerical Jacobian, reports per-parameter uncertainty from
the residual covariance, and keeps the calibration and validation splits
distinct. It never hides a poor validation fit: a report is only "passed" when
the held-out RMSE meets the caller's tolerance.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any, Protocol

from aeroworkbench_core.types import Provenance
from aeroworkbench_optimization.design_space import content_digest

from .contracts import DEFAULT_SOFTWARE, SoftwareIdentity, Validity
from .errors import IdentificationError, finite
from .provenance import calibrated_provenance
from .units import require_unit

__all__ = [
    "CalibrationSplit",
    "IdentificationReport",
    "Observation",
    "ParameterBound",
    "ParameterEstimate",
    "ParametricModel",
    "estimate_parameters",
    "identify",
    "split_calibration_validation",
]


class ParametricModel(Protocol):
    """A model whose output depends on inputs and a bounded parameter vector."""

    def predict(self, inputs: Mapping[str, float], parameters: Sequence[float]) -> float: ...


@dataclass(frozen=True, slots=True)
class ParameterBound:
    """A bounded parameter to identify, with its unit and optional seed."""

    name: str
    unit: str
    lower: float
    upper: float
    initial: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise IdentificationError("PARAMETER_NAME_REQUIRED")
        require_unit(self.unit)
        finite(self.lower, f"parameter lower bound {self.name}")
        finite(self.upper, f"parameter upper bound {self.name}")
        if self.lower >= self.upper:
            raise IdentificationError(f"PARAMETER_BOUNDS_INVALID:{self.name}")
        if self.initial is not None:
            finite(self.initial, f"parameter initial {self.name}")
            if self.initial < self.lower or self.initial > self.upper:
                raise IdentificationError(f"PARAMETER_INITIAL_OUT_OF_BOUNDS:{self.name}")


@dataclass(frozen=True, slots=True)
class Observation:
    """A measured input/output pair with an optional uncertainty weight."""

    inputs: Mapping[str, float]
    measured: float
    uncertainty: float = 1.0

    def __post_init__(self) -> None:
        if not self.inputs:
            raise IdentificationError("OBSERVATION_INPUTS_REQUIRED")
        for name, value in self.inputs.items():
            if not isfinite(float(value)):
                raise IdentificationError(f"OBSERVATION_INPUT_NONFINITE:{name}")
        finite(self.measured, "observation measured")
        finite(self.uncertainty, "observation uncertainty", positive=True)


@dataclass(frozen=True, slots=True)
class CalibrationSplit:
    """A distinct calibration set and held-out validation set."""

    calibration: tuple[Observation, ...]
    validation: tuple[Observation, ...]

    def canonical(self) -> dict[str, int]:
        return {"calibration": len(self.calibration), "validation": len(self.validation)}


def split_calibration_validation(
    observations: Sequence[Observation],
    *,
    calibration_fraction: float = 2.0 / 3.0,
    seed: int = 0,
) -> CalibrationSplit:
    """Deterministically partition observations into calibration and validation."""

    if len(observations) < 2:
        raise IdentificationError("IDENTIFICATION_NEEDS_AT_LEAST_TWO_OBSERVATIONS")
    finite(calibration_fraction, "calibration fraction", minimum=0.0, maximum=1.0)
    identifiers = list(range(len(observations)))
    random.Random(seed).shuffle(identifiers)
    calibration_count = int(round(len(observations) * calibration_fraction))
    calibration_count = max(1, min(len(observations) - 1, calibration_count))
    calibration_ids = set(identifiers[:calibration_count])
    calibration = tuple(
        observation
        for index, observation in enumerate(observations)
        if index in calibration_ids
    )
    validation = tuple(
        observation
        for index, observation in enumerate(observations)
        if index not in calibration_ids
    )
    return CalibrationSplit(calibration=calibration, validation=validation)


@dataclass(frozen=True, slots=True)
class ParameterEstimate:
    """One identified parameter with uncertainty and its enforced bounds."""

    name: str
    unit: str
    value: float
    uncertainty: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        finite(self.value, f"parameter value {self.name}")
        finite(self.uncertainty, f"parameter uncertainty {self.name}", minimum=0.0)

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "value": self.value,
            "uncertainty": self.uncertainty,
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass(frozen=True, slots=True)
class _Fit:
    parameters: tuple[float, ...]
    iterations: int
    converged: bool
    jacobian: tuple[tuple[float, ...], ...]
    residuals: tuple[float, ...]


def _initial(bounds: Sequence[ParameterBound]) -> list[float]:
    return [
        bound.initial if bound.initial is not None else 0.5 * (bound.lower + bound.upper)
        for bound in bounds
    ]


def _clip(values: Sequence[float], bounds: Sequence[ParameterBound]) -> list[float]:
    return [
        min(max(value, bound.lower), bound.upper)
        for value, bound in zip(values, bounds, strict=True)
    ]


def _residuals(
    model: ParametricModel, observations: Sequence[Observation], parameters: Sequence[float]
) -> list[float]:
    return [
        (model.predict(observation.inputs, parameters) - observation.measured)
        / observation.uncertainty
        for observation in observations
    ]


def _with_value(
    parameters: Sequence[float], index: int, value: float
) -> list[float]:
    return [*parameters[:index], value, *parameters[index + 1 :]]


def _jacobian(
    model: ParametricModel,
    observations: Sequence[Observation],
    parameters: Sequence[float],
    bounds: Sequence[ParameterBound],
) -> list[list[float]]:
    rows: list[list[float]] = []
    for observation in observations:
        row: list[float] = []
        for index, value in enumerate(parameters):
            bound = bounds[index]
            step = 1e-6 * max(1.0, abs(value))
            forward = min(value + step, bound.upper)
            backward = max(value - step, bound.lower)
            span = forward - backward
            if span <= 0:
                row.append(0.0)
                continue
            plus = (
                model.predict(observation.inputs, _with_value(parameters, index, forward))
                - observation.measured
            ) / observation.uncertainty
            minus = (
                model.predict(observation.inputs, _with_value(parameters, index, backward))
                - observation.measured
            ) / observation.uncertainty
            row.append((plus - minus) / span)
        rows.append(row)
    return rows


def _normal(jacobian: Sequence[Sequence[float]]) -> list[list[float]]:
    size = len(jacobian[0])
    matrix = [[0.0] * size for _ in range(size)]
    for row in jacobian:
        for i in range(size):
            for j in range(size):
                matrix[i][j] += row[i] * row[j]
    return matrix


def _solve(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float]:
    size = len(matrix)
    augmented = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise IdentificationError("IDENTIFICATION_SINGULAR_NORMAL_EQUATIONS")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for cell in range(column, size + 1):
            augmented[column][cell] /= pivot_value
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            for cell in range(column, size + 1):
                augmented[row][cell] -= factor * augmented[column][cell]
    return [augmented[row][size] for row in range(size)]


def _invert(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    size = len(matrix)
    identity = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
    augmented = [list(matrix[i]) + identity[i] for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise IdentificationError("IDENTIFICATION_SINGULAR_COVARIANCE")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for cell in range(2 * size):
            augmented[column][cell] /= pivot_value
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            for cell in range(2 * size):
                augmented[row][cell] -= factor * augmented[column][cell]
    return [row[size:] for row in augmented]


def _fit(
    model: ParametricModel,
    observations: Sequence[Observation],
    bounds: Sequence[ParameterBound],
    *,
    max_iterations: int,
    tolerance: float,
) -> _Fit:
    parameters = _initial(bounds)
    residuals = _residuals(model, observations, parameters)
    converged = False
    iterations = 0
    jacobian: list[list[float]] = []
    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        jacobian = _jacobian(model, observations, parameters, bounds)
        normal = _normal(jacobian)
        size = len(parameters)
        for index in range(size):
            normal[index][index] += 1e-10
        gradient = [
            -sum(jacobian[row][index] * residuals[row] for row in range(len(residuals)))
            for index in range(size)
        ]
        step = _solve(normal, gradient)
        candidate = _clip(
            [parameters[index] + step[index] for index in range(size)], bounds
        )
        candidate_residuals = _residuals(model, observations, candidate)
        if sum(value * value for value in candidate_residuals) > sum(
            value * value for value in residuals
        ):
            step = [0.5 * value for value in step]
            candidate = _clip([parameters[index] + step[index] for index in range(size)], bounds)
            candidate_residuals = _residuals(model, observations, candidate)
        parameters = candidate
        residuals = candidate_residuals
        if sqrt(sum(value * value for value in step)) < tolerance:
            converged = True
            break
    jacobian = _jacobian(model, observations, parameters, bounds)
    return _Fit(
        parameters=tuple(parameters),
        iterations=iterations,
        converged=converged,
        jacobian=tuple(tuple(row) for row in jacobian),
        residuals=tuple(residuals),
    )


def _estimates_from_fit(
    fit: _Fit, observations: Sequence[Observation], bounds: Sequence[ParameterBound]
) -> tuple[ParameterEstimate, ...]:
    degrees = len(observations) - len(bounds)
    if degrees <= 0:
        raise IdentificationError("IDENTIFICATION_NEEDS_MORE_OBSERVATIONS_THAN_PARAMETERS")
    sse = sum(value * value for value in fit.residuals)
    variance = sse / degrees
    normal = _normal(fit.jacobian)
    for index in range(len(bounds)):
        normal[index][index] += 1e-12
    covariance = _invert(normal)
    estimates: list[ParameterEstimate] = []
    for index, bound in enumerate(bounds):
        parameter_uncertainty = sqrt(max(variance * covariance[index][index], 0.0))
        estimates.append(
            ParameterEstimate(
                name=bound.name,
                unit=bound.unit,
                value=fit.parameters[index],
                uncertainty=parameter_uncertainty,
                lower=bound.lower,
                upper=bound.upper,
            )
        )
    return tuple(estimates)


def estimate_parameters(
    model: ParametricModel,
    observations: Sequence[Observation],
    *,
    bounds: Sequence[ParameterBound],
    max_iterations: int = 100,
    tolerance: float = 1e-10,
) -> tuple[ParameterEstimate, ...]:
    """Estimate bounded parameters and their covariance-based uncertainty."""

    if not bounds:
        raise IdentificationError("IDENTIFICATION_BOUNDS_REQUIRED")
    if len(observations) <= len(bounds):
        raise IdentificationError(
            "IDENTIFICATION_NEEDS_MORE_OBSERVATIONS_THAN_PARAMETERS"
        )
    fit = _fit(
        model, observations, bounds, max_iterations=max_iterations, tolerance=tolerance
    )
    return _estimates_from_fit(fit, observations, bounds)


def _rmse(
    model: ParametricModel, observations: Sequence[Observation], parameters: Sequence[float]
) -> float:
    if not observations:
        raise IdentificationError("IDENTIFICATION_SPLIT_IS_EMPTY")
    total = 0.0
    for observation in observations:
        difference = model.predict(observation.inputs, parameters) - observation.measured
        total += difference * difference
    return sqrt(total / len(observations))


@dataclass(frozen=True, slots=True)
class IdentificationReport:
    """A bounded identification with distinct calibration and validation errors."""

    calibration_count: int
    validation_count: int
    parameters: tuple[ParameterEstimate, ...]
    calibration_rmse: float
    validation_rmse: float
    iterations: int
    converged: bool
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    def parameter(self, name: str) -> ParameterEstimate:
        for estimate in self.parameters:
            if estimate.name == name:
                return estimate
        raise IdentificationError(f"IDENTIFICATION_UNKNOWN_PARAMETER:{name}")

    def passed(self, *, max_validation_rmse: float) -> bool:
        finite(max_validation_rmse, "max validation rmse", minimum=0.0)
        return self.converged and self.validation_rmse <= max_validation_rmse

    def canonical(self) -> dict[str, Any]:
        return {
            "calibrationCount": self.calibration_count,
            "validationCount": self.validation_count,
            "parameters": [estimate.canonical() for estimate in self.parameters],
            "calibrationRmse": self.calibration_rmse,
            "validationRmse": self.validation_rmse,
            "iterations": self.iterations,
            "converged": self.converged,
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def identify(
    model: ParametricModel,
    observations: Sequence[Observation],
    *,
    bounds: Sequence[ParameterBound],
    calibration_fraction: float = 2.0 / 3.0,
    seed: int = 0,
    max_iterations: int = 100,
    tolerance: float = 1e-10,
    max_validation_rmse: float | None = None,
) -> IdentificationReport:
    """Split observations, identify on calibration, and score held-out validation."""

    split = split_calibration_validation(
        observations, calibration_fraction=calibration_fraction, seed=seed
    )
    fit = _fit(
        model, split.calibration, bounds, max_iterations=max_iterations, tolerance=tolerance
    )
    estimates = _estimates_from_fit(fit, split.calibration, bounds)
    values = [estimate.value for estimate in estimates]
    calibration_rmse = _rmse(model, split.calibration, values)
    validation_rmse = _rmse(model, split.validation, values)
    payload = {
        "observations": [
            {"inputs": dict(sorted(observation.inputs.items())), "measured": observation.measured}
            for observation in observations
        ],
        "bounds": [bound.name for bound in bounds],
        "seed": seed,
        "calibrationFraction": calibration_fraction,
    }
    checks: dict[str, bool] = {
        "identification-converged": fit.converged,
        "distinct-splits": True,
    }
    if max_validation_rmse is not None:
        finite(max_validation_rmse, "max validation rmse", minimum=0.0)
        checks["validation-rmse"] = validation_rmse <= max_validation_rmse
    passed = all(checks.values())
    validity = Validity(
        passed=passed,
        checks=checks,
        detail="" if passed else "identification or held-out validation gate failed",
    )
    return IdentificationReport(
        calibration_count=len(split.calibration),
        validation_count=len(split.validation),
        parameters=estimates,
        calibration_rmse=calibration_rmse,
        validation_rmse=validation_rmse,
        iterations=fit.iterations,
        converged=fit.converged,
        validity=validity,
        inputs_hash=content_digest(payload),
        software=DEFAULT_SOFTWARE,
        provenance=calibrated_provenance(
            "bounded-parameter-identification",
            payload,
            assumptions=(
                "model parameters fitted to the calibration split only",
                "validation split held out and scored separately",
            ),
        ),
    )
