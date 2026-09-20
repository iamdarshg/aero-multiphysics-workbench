"""Fit reduced/meanline/cycle parameters to trusted data (issue TURBO 11, part B).

Fitting delegates to the generic bounded system-identification seam in
``aeroworkbench_experiment``; this module only adapts turbomachinery data and
labels the outcome. Raw measurements are never overwritten.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import ResultSource
from aeroworkbench_experiment.identification import (
    Observation,
    ParameterBound,
    estimate_parameters,
    identify,
)

from ..canonical import content_digest
from .data import CalibrationDataset, CalibrationDatum
from .errors import CalibrationInputError
from .results import (
    CalibrationFidelity,
    CalibrationSoftware,
    CalibrationValidity,
    calibration_provenance,
)

MAX_CALIBRATION_POINTS = 4096


class BiasModel:
    """One-parameter bias correction: ``predict = base + offset``."""

    def __init__(self, base: float, channel: str = "base") -> None:
        if base != base or base in (float("inf"), float("-inf")):
            raise CalibrationInputError("BIAS_BASE_NONFINITE")
        self._base = base
        self._channel = channel

    def predict(
        self, inputs: Mapping[str, float], parameters: Sequence[float]
    ) -> float:
        _ = inputs
        return self._base + float(parameters[0])


class AffineResponseModel:
    """Two-parameter gain/offset correction on one named input channel."""

    def __init__(self, channel: str) -> None:
        if not channel.strip():
            raise CalibrationInputError("AFFINE_CHANNEL_REQUIRED")
        self._channel = channel

    @property
    def channel(self) -> str:
        return self._channel

    def predict(
        self, inputs: Mapping[str, float], parameters: Sequence[float]
    ) -> float:
        try:
            value = float(inputs[self._channel])
        except KeyError as exc:
            raise CalibrationInputError(
                f"AFFINE_CHANNEL_MISSING:{self._channel}"
            ) from exc
        return float(parameters[0]) * value + float(parameters[1])


def _observations(dataset: CalibrationDataset) -> tuple[Observation, ...]:
    if len(dataset.data) > MAX_CALIBRATION_POINTS:
        raise CalibrationInputError("CALIBRATION_DATASET_TOO_LARGE")
    return tuple(
        Observation(
            inputs=datum.input_map(),
            measured=datum.measured,
            uncertainty=datum.uncertainty,
        )
        for datum in dataset.data
    )


def _parameter_bounds(
    names: Sequence[str], bounds: Mapping[str, tuple[float, float]], unit: str
) -> tuple[ParameterBound, ...]:
    resolved: list[ParameterBound] = []
    for name in names:
        if name not in bounds:
            raise CalibrationInputError(f"PARAMETER_BOUND_MISSING:{name}")
        lower, upper = bounds[name]
        resolved.append(
            ParameterBound(name=name, unit=unit, lower=float(lower), upper=float(upper))
        )
    return tuple(resolved)


@dataclass(frozen=True, slots=True)
class TurboCalibrationReceipt:
    dataset_id: str
    dataset_hash: str
    parameters: tuple[tuple[str, float, float, str], ...]
    calibration_rmse: float
    validation_rmse: float
    iterations: int
    converged: bool
    fidelity: str
    source: str
    units: tuple[tuple[str, str], ...]
    validity: CalibrationValidity
    input_hash: str
    software: CalibrationSoftware
    residuals: tuple[tuple[str, float], ...]
    provenance: Any

    def canonical(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "datasetHash": self.dataset_hash,
            "parameters": [
                {"name": n, "value": v, "uncertainty": u, "unit": un}
                for n, v, u, un in self.parameters
            ],
            "calibrationRmse": self.calibration_rmse,
            "validationRmse": self.validation_rmse,
            "iterations": self.iterations,
            "converged": self.converged,
            "fidelity": self.fidelity,
            "source": self.source,
            "units": [[n, u] for n, u in self.units],
            "validity": self.validity.canonical(),
            "inputHash": self.input_hash,
            "software": self.software.canonical(),
            "residuals": [[i, r] for i, r in self.residuals],
            "provenance": self.provenance.model_dump(mode="json"),
        }

    @property
    def result_hash(self) -> str:
        return content_digest(self.canonical())


def calibrate_model(
    model: BiasModel | AffineResponseModel,
    dataset: CalibrationDataset,
    parameter_names: Sequence[str],
    bounds: Mapping[str, tuple[float, float]],
    *,
    calibration_fraction: float = 2.0 / 3.0,
    max_validation_rmse: float | None = None,
    software: CalibrationSoftware | None = None,
) -> TurboCalibrationReceipt:
    observations = _observations(dataset)
    resolved_bounds = _parameter_bounds(parameter_names, bounds, dataset.unit)
    report = identify(
        model,
        observations,
        bounds=resolved_bounds,
        calibration_fraction=calibration_fraction,
        max_validation_rmse=max_validation_rmse,
    )
    resolved_software = software or CalibrationSoftware()
    payload = {
        "dataset": dataset.canonical(),
        "parameters": list(parameter_names),
        "bounds": {name: list(bounds[name]) for name in parameter_names},
        "calibrationFraction": calibration_fraction,
    }
    digest = content_digest(payload)
    checks = dict(report.validity.checks)
    passed = report.validity.passed
    validity = CalibrationValidity(passed=passed, checks=checks, detail=report.validity.detail)
    values = [report.parameter(name).value for name in parameter_names]
    residuals = tuple(
        (datum.datum_id, model.predict(datum.input_map(), values) - datum.measured)
        for datum in sorted(dataset.data, key=lambda d: d.datum_id)
    )
    return TurboCalibrationReceipt(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.dataset_hash,
        parameters=tuple(
            (e.name, e.value, e.uncertainty, e.unit) for e in report.parameters
        ),
        calibration_rmse=report.calibration_rmse,
        validation_rmse=report.validation_rmse,
        iterations=report.iterations,
        converged=report.converged,
        fidelity=CalibrationFidelity.CALIBRATED_SCREENING.value,
        source=ResultSource.SURROGATE.value,
        units=((dataset.unit, dataset.unit),),
        validity=validity,
        input_hash=digest,
        software=resolved_software,
        residuals=residuals,
        provenance=calibration_provenance(
            ResultSource.SURROGATE,
            CalibrationFidelity.CALIBRATED_SCREENING,
            payload,
            (
                "Parameters fitted on the calibration split only; validation split held out.",
                "Raw measurements preserved; receipt records residuals, not modified data.",
            ),
        ),
    )


def estimate_only(
    model: BiasModel | AffineResponseModel,
    data: Sequence[CalibrationDatum],
    parameter_names: Sequence[str],
    bounds: Mapping[str, tuple[float, float]],
    unit: str,
) -> tuple[tuple[str, float, float], ...]:
    if not data:
        raise CalibrationInputError("ESTIMATE_NEEDS_DATA")
    observations = tuple(
        Observation(
            inputs=datum.input_map(), measured=datum.measured, uncertainty=datum.uncertainty
        )
        for datum in data
    )
    estimates = estimate_parameters(
        model, observations, bounds=_parameter_bounds(parameter_names, bounds, unit)
    )
    return tuple((e.name, e.value, e.uncertainty) for e in estimates)


__all__ = [
    "MAX_CALIBRATION_POINTS",
    "AffineResponseModel",
    "BiasModel",
    "TurboCalibrationReceipt",
    "calibrate_model",
    "estimate_only",
]
