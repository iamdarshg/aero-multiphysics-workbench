"""Bounded surrogate and reduced-order model families.

The platform does not mandate one machine-learning method. This module offers
generic, deterministic, bounded options behind one small interface:

- unstructured interpolation (inverse-distance nearest neighbours),
- structured tensor-grid multilinear interpolation,
- polynomial response surfaces,
- radial-basis-function surrogates (Gaussian or multiquadric),
- a POD/reduced-order field-model seam,
- an optional neural surrogate that fails closed when no backend is wired.

Every model reports a per-output uncertainty estimate and a canonical config so
a map can hash it. Nothing here executes a solver or fabricates data.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from .capabilities import require_neural
from .errors import CapabilityUnavailable, MapContractError

__all__ = [
    "ModelPrediction",
    "NearestInterpolator",
    "NeuralBackend",
    "NeuralSurrogate",
    "PodRom",
    "PolynomialResponseSurface",
    "RBFSurrogate",
    "StructuredInterpolator",
    "SurrogateModel",
    "build_model",
]

_EPS = 1e-12


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    """Predicted outputs and a per-output uncertainty estimate."""

    outputs: dict[str, float]
    uncertainty: dict[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", {str(k): float(v) for k, v in self.outputs.items()})
        object.__setattr__(
            self, "uncertainty", {str(k): float(v) for k, v in self.uncertainty.items()}
        )


class SurrogateModel(Protocol):
    """Minimal fitted-model interface used by performance maps."""

    family: str
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None: ...

    def predict(self, point: Mapping[str, float]) -> ModelPrediction: ...

    def config(self) -> dict[str, Any]: ...


def _sample_names(samples: Sequence[Mapping[str, float]], label: str) -> tuple[str, ...]:
    if not samples:
        raise MapContractError(f"{label}_SAMPLES_REQUIRED")
    names = tuple(sorted(samples[0].keys()))
    if not names:
        raise MapContractError(f"{label}_SAMPLES_HAVE_NO_FIELDS")
    for sample in samples:
        if tuple(sorted(sample.keys())) != names:
            raise MapContractError(f"{label}_SAMPLE_FIELDS_MISMATCH")
    return names


def _matrix(
    samples: Sequence[Mapping[str, float]], names: tuple[str, ...], label: str
) -> NDArray[np.float64]:
    rows: list[list[float]] = []
    for sample in samples:
        row: list[float] = []
        for name in names:
            value = sample[name]
            if not np.isfinite(value):
                raise MapContractError(f"NONFINITE_{label}_VALUE:{name}")
            row.append(float(value))
        rows.append(row)
    return np.asarray(rows, dtype=np.float64)


def _as_point(point: Mapping[str, float], names: tuple[str, ...]) -> NDArray[np.float64]:
    if tuple(sorted(point.keys())) != names:
        raise MapContractError("PREDICT_POINT_FIELDS_MISMATCH")
    values = np.asarray([float(point[name]) for name in names], dtype=np.float64)
    if not bool(np.all(np.isfinite(values))):
        raise MapContractError("NONFINITE_PREDICT_POINT")
    return values


def _ranges(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    span = matrix.max(axis=0) - matrix.min(axis=0)
    return np.where(span < _EPS, 1.0, span)


class NearestInterpolator:
    """Unstructured inverse-distance-weighted interpolation over k neighbours."""

    family = "nearest"

    def __init__(self, *, neighbors: int = 3, power: float = 2.0) -> None:
        if neighbors < 1:
            raise MapContractError("NEAREST_NEIGHBORS_MUST_BE_POSITIVE")
        if power <= 0.0:
            raise MapContractError("NEAREST_POWER_MUST_BE_POSITIVE")
        self.neighbors = neighbors
        self.power = power
        self.input_names: tuple[str, ...] = ()
        self.output_names: tuple[str, ...] = ()
        self._inputs: NDArray[np.float64] | None = None
        self._outputs: NDArray[np.float64] | None = None
        self._scale: NDArray[np.float64] | None = None

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None:
        if len(inputs) != len(outputs):
            raise MapContractError("INPUT_OUTPUT_COUNT_MISMATCH")
        self.input_names = _sample_names(inputs, "INPUT")
        self.output_names = _sample_names(outputs, "OUTPUT")
        self._inputs = _matrix(inputs, self.input_names, "INPUT")
        self._outputs = _matrix(outputs, self.output_names, "OUTPUT")
        self._scale = _ranges(self._inputs)

    def predict(self, point: Mapping[str, float]) -> ModelPrediction:
        if self._inputs is None or self._outputs is None or self._scale is None:
            raise MapContractError("MODEL_NOT_FITTED")
        x = _as_point(point, self.input_names)
        distance = np.linalg.norm((self._inputs - x) / self._scale, axis=1)
        order = np.argsort(distance, kind="stable")[: self.neighbors]
        if float(distance[order[0]]) < _EPS:
            values = self._outputs[order[0]]
            uncertainty = float(distance[order[0]])
        else:
            weights = 1.0 / np.power(distance[order], self.power)
            values = (weights @ self._outputs[order]) / float(weights.sum())
            uncertainty = float(distance[order[0]])
        outputs = {
            name: float(values[index]) for index, name in enumerate(self.output_names)
        }
        return ModelPrediction(
            outputs=outputs, uncertainty={name: uncertainty for name in self.output_names}
        )

    def config(self) -> dict[str, Any]:
        return {"family": self.family, "neighbors": self.neighbors, "power": self.power}


class StructuredInterpolator:
    """Multilinear interpolation on a full tensor grid of declared axes."""

    family = "structured"

    def __init__(self) -> None:
        self.input_names: tuple[str, ...] = ()
        self.output_names: tuple[str, ...] = ()
        self._axes: list[NDArray[np.float64]] = []
        self._values: NDArray[np.float64] | None = None

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None:
        if len(inputs) != len(outputs):
            raise MapContractError("INPUT_OUTPUT_COUNT_MISMATCH")
        self.input_names = _sample_names(inputs, "INPUT")
        self.output_names = _sample_names(outputs, "OUTPUT")
        matrix = _matrix(inputs, self.input_names, "INPUT")
        out = _matrix(outputs, self.output_names, "OUTPUT")
        axes = [np.unique(matrix[:, index]) for index in range(matrix.shape[1])]
        shape = tuple(len(axis) for axis in axes)
        expected = 1
        for length in shape:
            expected *= length
        if expected != matrix.shape[0]:
            raise MapContractError("STRUCTURED_INTERPOLATION_NEEDS_FULL_GRID")
        values = np.empty((*shape, len(self.output_names)), dtype=np.float64)
        seen: set[tuple[int, ...]] = set()
        for row in range(matrix.shape[0]):
            index = tuple(
                int(np.searchsorted(axis, matrix[row, axis_index]))
                for axis_index, axis in enumerate(axes)
            )
            if index in seen:
                raise MapContractError("STRUCTURED_INTERPOLATION_DUPLICATE_NODE")
            seen.add(index)
            values[index] = out[row]
        self._axes = axes
        self._values = values

    def predict(self, point: Mapping[str, float]) -> ModelPrediction:
        if self._values is None:
            raise MapContractError("MODEL_NOT_FITTED")
        x = _as_point(point, self.input_names)
        dimension = len(self.input_names)
        indices: list[int] = []
        fractions: list[float] = []
        for axis_index, axis in enumerate(self._axes):
            if len(axis) == 1:
                indices.append(0)
                fractions.append(0.0)
                continue
            position = int(np.searchsorted(axis, x[axis_index], side="right") - 1)
            position = min(max(position, 0), len(axis) - 2)
            span = axis[position + 1] - axis[position]
            fraction = float((x[axis_index] - axis[position]) / span)
            indices.append(position)
            fractions.append(min(max(fraction, 0.0), 1.0))
        values = np.zeros(len(self.output_names), dtype=np.float64)
        for bits in range(1 << dimension):
            weight = 1.0
            corner = []
            for axis_index in range(dimension):
                upper = bool((bits >> axis_index) & 1)
                weight *= fractions[axis_index] if upper else 1.0 - fractions[axis_index]
                corner.append(indices[axis_index] + (1 if upper else 0))
            if weight != 0.0:
                values += weight * self._values[tuple(corner)]
        uncertainty = float(np.sqrt(sum(frac * (1.0 - frac) for frac in fractions)))
        outputs = {name: float(values[i]) for i, name in enumerate(self.output_names)}
        return ModelPrediction(
            outputs=outputs, uncertainty={name: uncertainty for name in self.output_names}
        )

    def config(self) -> dict[str, Any]:
        return {"family": self.family}


def _monomials(dimension: int, degree: int) -> list[tuple[int, ...]]:
    exponents: list[tuple[int, ...]] = []
    for total in range(degree + 1):
        for combo in itertools.combinations_with_replacement(range(dimension), total):
            powers = [0] * dimension
            for index in combo:
                powers[index] += 1
            exponents.append(tuple(powers))
    return exponents


class PolynomialResponseSurface:
    """Least-squares polynomial response surface of declared total degree."""

    family = "polynomial"

    def __init__(self, *, degree: int = 2, ridge: float = 0.0) -> None:
        if degree < 0:
            raise MapContractError("POLYNOMIAL_DEGREE_MUST_BE_NONNEGATIVE")
        if ridge < 0.0:
            raise MapContractError("POLYNOMIAL_RIDGE_MUST_BE_NONNEGATIVE")
        self.degree = degree
        self.ridge = ridge
        self.input_names: tuple[str, ...] = ()
        self.output_names: tuple[str, ...] = ()
        self._exponents: list[tuple[int, ...]] = []
        self._coefficients: NDArray[np.float64] | None = None
        self._residual: dict[str, float] = {}

    def _design(self, matrix: NDArray[np.float64]) -> NDArray[np.float64]:
        columns = [
            np.prod(np.power(matrix, np.asarray(exponent, dtype=np.float64)), axis=1)
            for exponent in self._exponents
        ]
        return np.stack(columns, axis=1)

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None:
        if len(inputs) != len(outputs):
            raise MapContractError("INPUT_OUTPUT_COUNT_MISMATCH")
        self.input_names = _sample_names(inputs, "INPUT")
        self.output_names = _sample_names(outputs, "OUTPUT")
        matrix = _matrix(inputs, self.input_names, "INPUT")
        target = _matrix(outputs, self.output_names, "OUTPUT")
        self._exponents = _monomials(matrix.shape[1], self.degree)
        design = self._design(matrix)
        if self.ridge > 0.0:
            penalty = self.ridge * np.eye(design.shape[1], dtype=np.float64)
            coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
        else:
            coefficients = np.linalg.lstsq(design, target, rcond=None)[0]
        self._coefficients = coefficients
        residual = target - design @ coefficients
        for index, name in enumerate(self.output_names):
            self._residual[name] = float(np.sqrt(np.mean(residual[:, index] ** 2)))
        for name in self.output_names:
            self._residual[name] = max(self._residual[name], 0.0)

    def predict(self, point: Mapping[str, float]) -> ModelPrediction:
        if self._coefficients is None:
            raise MapContractError("MODEL_NOT_FITTED")
        x = _as_point(point, self.input_names)
        design = self._design(x.reshape(1, -1))
        values = design @ self._coefficients
        outputs = {
            name: float(values[0, index]) for index, name in enumerate(self.output_names)
        }
        return ModelPrediction(
            outputs=outputs,
            uncertainty={name: self._residual.get(name, 0.0) for name in self.output_names},
        )

    def config(self) -> dict[str, Any]:
        return {"family": self.family, "degree": self.degree, "ridge": self.ridge}


class RBFSurrogate:
    """Radial-basis-function surrogate with Gaussian or multiquadric kernel."""

    family = "rbf"

    def __init__(
        self, *, kernel: str = "gaussian", length_scale: float = 1.0, regularization: float = 1e-8
    ) -> None:
        if kernel not in {"gaussian", "multiquadric"}:
            raise MapContractError(f"UNKNOWN_RBF_KERNEL:{kernel}")
        if length_scale <= 0.0:
            raise MapContractError("RBF_LENGTH_SCALE_MUST_BE_POSITIVE")
        if regularization < 0.0:
            raise MapContractError("RBF_REGULARIZATION_MUST_BE_NONNEGATIVE")
        self.kernel = kernel
        self.length_scale = length_scale
        self.regularization = regularization
        self.input_names: tuple[str, ...] = ()
        self.output_names: tuple[str, ...] = ()
        self._centers: NDArray[np.float64] | None = None
        self._weights: NDArray[np.float64] | None = None
        self._scale: NDArray[np.float64] | None = None
        self._origin: NDArray[np.float64] | None = None

    def _kernel_matrix(
        self, left: NDArray[np.float64], right: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        delta = left[:, None, :] - right[None, :, :]
        distance = np.sqrt(np.sum(delta * delta, axis=2))
        if self.kernel == "gaussian":
            return np.exp(-(distance * distance) / (2.0 * self.length_scale**2))
        return np.sqrt(1.0 + (distance / self.length_scale) ** 2)

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None:
        if len(inputs) != len(outputs):
            raise MapContractError("INPUT_OUTPUT_COUNT_MISMATCH")
        self.input_names = _sample_names(inputs, "INPUT")
        self.output_names = _sample_names(outputs, "OUTPUT")
        matrix = _matrix(inputs, self.input_names, "INPUT")
        target = _matrix(outputs, self.output_names, "OUTPUT")
        self._scale = _ranges(matrix)
        self._origin = matrix.min(axis=0)
        self._centers = (matrix - self._origin) / self._scale
        kernel = self._kernel_matrix(self._centers, self._centers)
        system = kernel + self.regularization * np.eye(kernel.shape[0], dtype=np.float64)
        self._weights = np.linalg.solve(system, target)

    def predict(self, point: Mapping[str, float]) -> ModelPrediction:
        if (
            self._centers is None
            or self._weights is None
            or self._scale is None
            or self._origin is None
        ):
            raise MapContractError("MODEL_NOT_FITTED")
        x = _as_point(point, self.input_names)
        normalized = (x - self._origin) / self._scale
        kernel = self._kernel_matrix(normalized.reshape(1, -1), self._centers)
        values = kernel @ self._weights
        distance = np.linalg.norm(self._centers - normalized, axis=1)
        uncertainty = float(np.min(distance))
        outputs = {
            name: float(values[0, index]) for index, name in enumerate(self.output_names)
        }
        return ModelPrediction(
            outputs=outputs, uncertainty={name: uncertainty for name in self.output_names}
        )

    def config(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "kernel": self.kernel,
            "lengthScale": self.length_scale,
            "regularization": self.regularization,
        }


class PodRom:
    """Proper-orthogonal-decomposition seam for reduced-order field models.

    Snapshot vectors are compressed onto an energy-truncated POD basis, and the
    modal coefficients are interpolated with an inner RBF surrogate. This is the
    seam a higher-fidelity field solver can feed without the map layer encoding
    any field-specific assumption.
    """

    family = "pod"

    def __init__(self, *, energy: float = 0.999, max_modes: int | None = None) -> None:
        if not 0.0 < energy <= 1.0:
            raise MapContractError("POD_ENERGY_MUST_BE_IN_UNIT_INTERVAL")
        if max_modes is not None and max_modes < 1:
            raise MapContractError("POD_MAX_MODES_MUST_BE_POSITIVE")
        self.energy = energy
        self.max_modes = max_modes
        self.input_names: tuple[str, ...] = ()
        self._mean: NDArray[np.float64] | None = None
        self._basis: NDArray[np.float64] | None = None
        self._coefficient_model: RBFSurrogate | None = None
        self._energy_ratio: tuple[float, ...] = ()
        self._reconstruction_error = 0.0

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        fields: Sequence[Sequence[float]],
    ) -> None:
        if len(inputs) != len(fields):
            raise MapContractError("INPUT_FIELD_COUNT_MISMATCH")
        if not fields:
            raise MapContractError("POD_NEEDS_SNAPSHOTS")
        width = len(fields[0])
        if width == 0 or any(len(field) != width for field in fields):
            raise MapContractError("POD_SNAPSHOTS_MUST_BE_RECTANGULAR")
        self.input_names = _sample_names(inputs, "INPUT")
        snapshots = np.asarray(fields, dtype=np.float64)
        if not bool(np.all(np.isfinite(snapshots))):
            raise MapContractError("NONFINITE_POD_SNAPSHOT")
        self._mean = snapshots.mean(axis=0)
        centered = snapshots - self._mean
        left, singular, right = np.linalg.svd(centered, full_matrices=False)
        total = float(np.sum(singular * singular))
        ratio: tuple[float, ...]
        if total < _EPS:
            modes = 1
            ratio = (1.0,)
        else:
            cumulative = np.cumsum(singular * singular) / total
            modes = int(np.searchsorted(cumulative, self.energy) + 1)
            ratio = tuple(float(value) for value in cumulative)
        if self.max_modes is not None:
            modes = min(modes, self.max_modes)
        modes = max(1, min(modes, len(singular)))
        self._basis = right[:modes, :]
        coefficients = left[:, :modes] * singular[:modes]
        self._energy_ratio = ratio[:modes]
        inner = RBFSurrogate()
        inner.fit(
            inputs,
            [
                {f"c{index}": float(coefficients[row, index]) for index in range(modes)}
                for row in range(coefficients.shape[0])
            ],
        )
        self._coefficient_model = inner
        reconstruction = self._mean + coefficients @ self._basis
        denominator = float(np.linalg.norm(centered)) or 1.0
        self._reconstruction_error = float(np.linalg.norm(reconstruction - snapshots) / denominator)

    @property
    def mode_count(self) -> int:
        return 0 if self._basis is None else int(self._basis.shape[0])

    @property
    def energy_ratio(self) -> tuple[float, ...]:
        return self._energy_ratio

    @property
    def reconstruction_error(self) -> float:
        return self._reconstruction_error

    def predict_field(self, point: Mapping[str, float]) -> tuple[float, ...]:
        if self._basis is None or self._mean is None or self._coefficient_model is None:
            raise MapContractError("MODEL_NOT_FITTED")
        prediction = self._coefficient_model.predict(point)
        coefficients = np.asarray(
            [prediction.outputs[f"c{index}"] for index in range(self.mode_count)],
            dtype=np.float64,
        )
        field = self._mean + coefficients @ self._basis
        return tuple(float(value) for value in field)

    def config(self) -> dict[str, Any]:
        return {"family": self.family, "energy": self.energy, "maxModes": self.max_modes}


class NeuralBackend(Protocol):
    """A wired neural-network implementation; never assumed to exist."""

    input_names: tuple[str, ...]
    output_names: tuple[str, ...]

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None: ...

    def predict(self, point: Mapping[str, float]) -> ModelPrediction: ...

    def config(self) -> dict[str, Any]: ...


class NeuralSurrogate:
    """Capability-gated neural surrogate; fails closed without a backend."""

    family = "neural"

    def __init__(self, *, backend: NeuralBackend | None = None) -> None:
        if backend is None:
            raise CapabilityUnavailable("NEURAL_CAPABILITY_UNAVAILABLE:neural-surrogate")
        self._backend = backend
        self.input_names = backend.input_names
        self.output_names = backend.output_names

    def fit(
        self,
        inputs: Sequence[Mapping[str, float]],
        outputs: Sequence[Mapping[str, float]],
    ) -> None:
        self._backend.fit(inputs, outputs)
        self.input_names = self._backend.input_names
        self.output_names = self._backend.output_names

    def predict(self, point: Mapping[str, float]) -> ModelPrediction:
        return self._backend.predict(point)

    def config(self) -> dict[str, Any]:
        return {"family": self.family, **self._backend.config()}


def build_model(family: str, **options: Any) -> SurrogateModel:
    """Construct a model family by name; unknown families fail closed."""

    normalized = family.strip().lower()
    if normalized in {"nearest", "idw"}:
        return NearestInterpolator(**options)
    if normalized in {"structured", "grid", "tensor"}:
        return StructuredInterpolator(**options)
    if normalized in {"polynomial", "response-surface", "rsm"}:
        return PolynomialResponseSurface(**options)
    if normalized in {"rbf", "kriging", "gaussian-process"}:
        return RBFSurrogate(**options)
    if normalized == "neural":
        require_neural(present=options.get("backend") is not None)
        return NeuralSurrogate(**options)
    raise MapContractError(f"UNKNOWN_MODEL_FAMILY:{family}")
