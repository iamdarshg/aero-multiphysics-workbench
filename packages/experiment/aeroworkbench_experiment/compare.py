"""Match measurements to simulation result envelopes and report residuals.

A :class:`SimulationResultEnvelope` is the simulation-side result contract: it
carries its design revision, operating-condition key, per-channel data with
units, its source/fidelity, and provenance. Measurements are matched to
envelopes by design revision and condition key (never by guesswork), and
residuals are reported for scalar, time-domain, and frequency-domain data. A
comparison never relabels the simulation evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import isfinite, sqrt
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization.design_space import content_digest

from .contracts import DEFAULT_SOFTWARE, SoftwareIdentity, Validity
from .errors import ComparisonError
from .ingest import MeasurementChannel, MeasurementDataset
from .provenance import simulation_provenance
from .sync import Spectrum, spectrum

__all__ = [
    "ComparisonReport",
    "ScalarResidual",
    "SeriesResidual",
    "SimulationChannel",
    "SimulationResultEnvelope",
    "compare_dataset",
    "compare_spectra",
    "match_dataset",
    "require_match",
    "scalar_residual",
]


@dataclass(frozen=True, slots=True)
class SimulationChannel:
    """A simulation-side channel: scalar, time series, or frequency series."""

    name: str
    unit: str
    values: tuple[float, ...]
    time_s: tuple[float, ...] | None = None
    frequency_hz: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ComparisonError("SIMULATION_CHANNEL_NAME_REQUIRED")
        if not self.values:
            raise ComparisonError(f"SIMULATION_CHANNEL_EMPTY:{self.name}")
        if self.time_s is not None and len(self.time_s) != len(self.values):
            raise ComparisonError(f"SIMULATION_CHANNEL_TIME_MISMATCH:{self.name}")
        if self.frequency_hz is not None and len(self.frequency_hz) != len(self.values):
            raise ComparisonError(f"SIMULATION_CHANNEL_FREQUENCY_MISMATCH:{self.name}")
        for value in (*self.values, *(self.time_s or ()), *(self.frequency_hz or ())):
            if not isfinite(value):
                raise ComparisonError(f"SIMULATION_CHANNEL_NONFINITE:{self.name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "values": list(self.values),
            "timeS": None if self.time_s is None else list(self.time_s),
            "frequencyHz": None if self.frequency_hz is None else list(self.frequency_hz),
        }


@dataclass(frozen=True, slots=True)
class SimulationResultEnvelope:
    """A simulation result matched to a design revision and operating condition."""

    envelope_id: str
    design_revision: str
    condition_key: str
    channels: tuple[SimulationChannel, ...]
    source: ResultSource
    fidelity: FidelityLevel
    provenance: Provenance
    software: SoftwareIdentity = field(default_factory=lambda: DEFAULT_SOFTWARE)

    def __post_init__(self) -> None:
        if not self.envelope_id.strip():
            raise ComparisonError("ENVELOPE_ID_REQUIRED")
        if not self.design_revision.strip():
            raise ComparisonError("ENVELOPE_DESIGN_REVISION_REQUIRED")
        if not self.condition_key.strip():
            raise ComparisonError("ENVELOPE_CONDITION_KEY_REQUIRED")
        if not self.channels:
            raise ComparisonError("ENVELOPE_CHANNELS_REQUIRED")
        if self.source is not self.provenance.source:
            raise ComparisonError("ENVELOPE_SOURCE_PROVENANCE_MISMATCH")

    def channel(self, name: str) -> SimulationChannel:
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise ComparisonError(f"ENVELOPE_UNKNOWN_CHANNEL:{name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "envelopeId": self.envelope_id,
            "designRevision": self.design_revision,
            "conditionKey": self.condition_key,
            "channels": [channel.canonical() for channel in self.channels],
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "provenance": self.provenance.model_dump(mode="json"),
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class ScalarResidual:
    """Measured-minus-simulated residual for a scalar quantity."""

    channel: str
    measured: float
    simulated: float
    absolute: float
    relative: float | None

    def canonical(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "measured": self.measured,
            "simulated": self.simulated,
            "absolute": self.absolute,
            "relative": self.relative,
        }


@dataclass(frozen=True, slots=True)
class SeriesResidual:
    """Aggregate residual statistics over a time or frequency domain."""

    channel: str
    domain: str
    count: int
    rmse: float
    mae: float
    max_abs: float
    mean_signed: float
    tolerance: float
    passed: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "domain": self.domain,
            "count": self.count,
            "rmse": self.rmse,
            "mae": self.mae,
            "maxAbs": self.max_abs,
            "meanSigned": self.mean_signed,
            "tolerance": self.tolerance,
            "passed": self.passed,
        }


def _statistics(residuals: Sequence[float]) -> tuple[float, float, float, float]:
    count = len(residuals)
    if count == 0:
        raise ComparisonError("RESIDUAL_SERIES_IS_EMPTY")
    rmse = sqrt(sum(value * value for value in residuals) / count)
    mae = sum(abs(value) for value in residuals) / count
    max_abs = max(abs(value) for value in residuals)
    mean_signed = sum(residuals) / count
    return rmse, mae, max_abs, mean_signed


def scalar_residual(channel: str, measured: float, simulated: float) -> ScalarResidual:
    """Measured-minus-simulated residual with absolute and relative error."""

    if not isfinite(measured) or not isfinite(simulated):
        raise ComparisonError(f"SCALAR_RESIDUAL_NONFINITE:{channel}")
    absolute = measured - simulated
    relative = None if simulated == 0 else absolute / abs(simulated)
    return ScalarResidual(
        channel=channel,
        measured=measured,
        simulated=simulated,
        absolute=absolute,
        relative=relative,
    )


def _residual_report(
    channel: str, domain: str, residuals: Sequence[float], tolerance: float
) -> SeriesResidual:
    if not isfinite(tolerance) or tolerance < 0:
        raise ComparisonError(f"RESIDUAL_TOLERANCE_INVALID:{channel}")
    rmse, mae, max_abs, mean_signed = _statistics(residuals)
    return SeriesResidual(
        channel=channel,
        domain=domain,
        count=len(residuals),
        rmse=rmse,
        mae=mae,
        max_abs=max_abs,
        mean_signed=mean_signed,
        tolerance=tolerance,
        passed=rmse <= tolerance,
    )


def _interp(grid: Sequence[float], values: Sequence[float], query: float) -> float:
    if query < grid[0] or query > grid[-1]:
        raise ComparisonError("COMPARISON_QUERY_OUTSIDE_SIMULATION")
    low = 0
    high = len(grid) - 1
    while high - low > 1:
        mid = (low + high) // 2
        if grid[mid] <= query:
            low = mid
        else:
            high = mid
    span = grid[high] - grid[low]
    if span == 0:
        return values[low]
    fraction = (query - grid[low]) / span
    return values[low] + fraction * (values[high] - values[low])


def _time_residual(
    measured: MeasurementChannel, simulated: SimulationChannel, tolerance: float
) -> SeriesResidual:
    if simulated.time_s is None:
        raise ComparisonError(f"SIMULATION_CHANNEL_NEEDS_TIME:{simulated.name}")
    grid = simulated.time_s
    residuals = tuple(
        measured_value - _interp(grid, simulated.values, time)
        for time, measured_value in zip(measured.time_s, measured.values, strict=True)
    )
    return _residual_report(measured.name, "time", residuals, tolerance)


def compare_spectra(
    measured: Spectrum, simulated: Spectrum, *, tolerance: float
) -> SeriesResidual:
    """Frequency-domain residual (measured minus simulated amplitude)."""

    frequencies = measured.frequencies_hz
    residuals: list[float] = []
    for frequency, amplitude in zip(
        frequencies, measured.amplitudes, strict=True
    ):
        if frequency < simulated.frequencies_hz[0] or frequency > simulated.frequencies_hz[-1]:
            continue
        expected = _interp(simulated.frequencies_hz, simulated.amplitudes, frequency)
        residuals.append(amplitude - expected)
    if not residuals:
        raise ComparisonError("SPECTRAL_COMPARISON_HAS_NO_COMMON_BINS")
    return _residual_report(measured.source_name, "frequency", residuals, tolerance)


def _frequency_residual(
    measured: MeasurementChannel, simulated: SimulationChannel, tolerance: float
) -> SeriesResidual:
    if simulated.frequency_hz is None:
        raise ComparisonError(f"SIMULATION_CHANNEL_NEEDS_FREQUENCY:{simulated.name}")
    measured_spectrum = spectrum(measured)
    simulated_spectrum = Spectrum(
        source_name=simulated.name,
        unit=simulated.unit,
        sample_rate_hz=0.0,
        frequencies_hz=simulated.frequency_hz,
        amplitudes=simulated.values,
        inputs_hash=content_digest(simulated.canonical()),
        software=DEFAULT_SOFTWARE,
        provenance=simulation_provenance("simulated-spectrum", simulated.canonical()),
    )
    return compare_spectra(measured_spectrum, simulated_spectrum, tolerance=tolerance)


def match_dataset(
    dataset: MeasurementDataset, envelopes: Sequence[SimulationResultEnvelope]
) -> tuple[SimulationResultEnvelope, ...]:
    """All envelopes whose design revision and condition key match the dataset."""

    return tuple(
        envelope
        for envelope in envelopes
        if envelope.design_revision == dataset.design_revision
        and envelope.condition_key == dataset.condition_key
    )


def require_match(
    dataset: MeasurementDataset, envelopes: Sequence[SimulationResultEnvelope]
) -> SimulationResultEnvelope:
    """Exactly one matching envelope, or fail closed."""

    matches = match_dataset(dataset, envelopes)
    if not matches:
        raise ComparisonError(
            f"NO_SIMULATION_MATCH:{dataset.design_revision}:{dataset.condition_key}"
        )
    if len(matches) > 1:
        raise ComparisonError(
            f"AMBIGUOUS_SIMULATION_MATCH:{dataset.design_revision}:{dataset.condition_key}"
        )
    return matches[0]


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """A reproducible measurement-versus-simulation comparison report."""

    report_id: str
    dataset_id: str
    envelope_id: str
    design_revision: str
    condition_key: str
    scalars: tuple[ScalarResidual, ...]
    series: tuple[SeriesResidual, ...]
    validity: Validity
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    def passed(self) -> bool:
        return self.validity.passed and all(item.passed for item in self.series)

    def failing(self) -> tuple[str, ...]:
        reasons = [
            f"{item.channel}:rmse={item.rmse:.6g}>tol={item.tolerance:.6g}"
            for item in self.series
            if not item.passed
        ]
        if not self.validity.passed:
            reasons.append(f"validity:{self.validity.detail}")
        return tuple(reasons)

    def canonical(self) -> dict[str, Any]:
        return {
            "reportId": self.report_id,
            "datasetId": self.dataset_id,
            "envelopeId": self.envelope_id,
            "designRevision": self.design_revision,
            "conditionKey": self.condition_key,
            "scalars": [item.canonical() for item in self.scalars],
            "series": [item.canonical() for item in self.series],
            "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash,
            "software": self.software.canonical(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


_MODE_SCALAR = "scalar"
_MODE_TIME = "time"
_MODE_FREQUENCY = "frequency"


def compare_dataset(
    dataset: MeasurementDataset,
    envelope: SimulationResultEnvelope,
    *,
    modes: Mapping[str, str],
    tolerances: Mapping[str, float],
    report_id: str = "comparison",
) -> ComparisonReport:
    """Compare selected channels by explicit mode: scalar, time, or frequency."""

    if not modes:
        raise ComparisonError("COMPARISON_MODES_REQUIRED")
    if envelope.design_revision != dataset.design_revision:
        raise ComparisonError("COMPARISON_DESIGN_REVISION_MISMATCH")
    if envelope.condition_key != dataset.condition_key:
        raise ComparisonError("COMPARISON_CONDITION_MISMATCH")
    scalars: list[ScalarResidual] = []
    series: list[SeriesResidual] = []
    tolerance_default = float(tolerances.get("default", 0.0))
    for channel_name in sorted(modes):
        mode = modes[channel_name]
        measured = dataset.channel(channel_name)
        simulated = envelope.channel(channel_name)
        tolerance = float(tolerances.get(channel_name, tolerance_default))
        if mode == _MODE_SCALAR:
            if len(simulated.values) != 1:
                raise ComparisonError(f"SCALAR_COMPARISON_NEEDS_ONE_SIMULATED_VALUE:{channel_name}")
            scalars.append(
                scalar_residual(channel_name, measured.values[-1], simulated.values[0])
            )
        elif mode == _MODE_TIME:
            series.append(_time_residual(measured, simulated, tolerance))
        elif mode == _MODE_FREQUENCY:
            series.append(_frequency_residual(measured, simulated, tolerance))
        else:
            raise ComparisonError(f"UNKNOWN_COMPARISON_MODE:{channel_name}:{mode}")
    payload = {
        "datasetId": dataset.digest(),
        "envelopeId": envelope.digest(),
        "modes": dict(sorted(modes.items())),
        "tolerances": dict(sorted(tolerances.items())),
    }
    all_passed = all(item.passed for item in series)
    validity = Validity(
        passed=all_passed,
        checks={item.channel: item.passed for item in series},
        detail="" if all_passed else "one or more channels exceeded tolerance",
    )
    return ComparisonReport(
        report_id=report_id,
        dataset_id=dataset.dataset_id,
        envelope_id=envelope.envelope_id,
        design_revision=dataset.design_revision,
        condition_key=dataset.condition_key,
        scalars=tuple(scalars),
        series=tuple(series),
        validity=validity,
        inputs_hash=content_digest(payload),
        software=DEFAULT_SOFTWARE,
        provenance=simulation_provenance(
            "measurement-simulation-comparison",
            payload,
            assumptions=(
                "simulation evidence remains labelled as simulation",
                "residuals are measured minus simulated",
            ),
        ),
    )
