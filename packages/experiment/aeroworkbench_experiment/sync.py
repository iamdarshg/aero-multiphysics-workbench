"""Reproducible synchronization and derived-signal processing.

Every operation (resampling, trigger alignment, filtering, spectral/order
analysis, cycle/event segmentation) is deterministic, records its parameters,
and returns a new derived channel whose lineage points at the immutable raw
channel. Raw measurements are never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, floor, pi, sin, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_optimization.design_space import content_digest

from .contracts import EvidenceFidelity, EvidenceKind, SoftwareIdentity, Validity
from .errors import SynchronizationError, finite
from .ingest import MeasurementChannel
from .provenance import derived_measurement_provenance

__all__ = [
    "CycleSegment",
    "EventSegment",
    "FilterSpec",
    "OrderSpectrum",
    "Spectrum",
    "TriggerAlignment",
    "align_to_trigger",
    "apply_filter",
    "order_spectrum",
    "resample",
    "segment_cycles",
    "segment_events",
    "spectrum",
    "trigger_time",
]


@dataclass(frozen=True, slots=True)
class FilterSpec:
    """A recorded, reproducible filter request."""

    kind: str
    window: int = 1
    cutoff_hz: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"moving_average", "lowpass"}:
            raise SynchronizationError(f"UNKNOWN_FILTER_KIND:{self.kind}")
        if self.kind == "moving_average" and self.window < 1:
            raise SynchronizationError("MOVING_AVERAGE_WINDOW_MUST_BE_POSITIVE")
        if self.kind == "lowpass" and self.cutoff_hz is None:
            raise SynchronizationError("LOWPASS_CUTOFF_REQUIRED")
        if self.kind == "lowpass" and self.cutoff_hz is not None:
            finite(self.cutoff_hz, "cutoff frequency", positive=True)

    def canonical(self) -> dict[str, Any]:
        return {"kind": self.kind, "window": self.window, "cutoffHz": self.cutoff_hz}


def _derive(
    source: MeasurementChannel,
    *,
    name: str,
    values: tuple[float, ...],
    time_s: tuple[float, ...],
    transform: dict[str, Any],
    filtering: tuple[str, ...] | None = None,
) -> MeasurementChannel:
    payload = {
        "sourceDigest": source.digest(),
        "name": name,
        "transform": transform,
        "timeS": list(time_s),
        "values": list(values),
    }
    return MeasurementChannel(
        name=name,
        unit=source.unit,
        source_unit=source.unit,
        sensor_id=source.sensor_id,
        time_s=time_s,
        values=values,
        origin=EvidenceKind.MEASUREMENT,
        fidelity=EvidenceFidelity.DERIVED,
        validity=Validity(
            passed=True,
            checks={"derived": True},
            detail="reproducible transform of immutable measured data",
        ),
        inputs_hash=content_digest(payload),
        software=source.software,
        provenance=derived_measurement_provenance(
            "derived-signal", payload, assumptions=("raw measurement channel is immutable",)
        ),
        derived_from=(source.digest(),),
        transform=transform,
        filtering=source.filtering if filtering is None else filtering,
    )


def _rate(time_s: tuple[float, ...]) -> float:
    if len(time_s) < 2:
        raise SynchronizationError("SERIES_NEEDS_AT_LEAST_TWO_SAMPLES")
    dt = time_s[1] - time_s[0]
    if dt <= 0:
        raise SynchronizationError("SERIES_TIME_NOT_INCREASING")
    return 1.0 / dt


def _interpolate(time_s: tuple[float, ...], values: tuple[float, ...], query: float) -> float:
    if query < time_s[0] or query > time_s[-1]:
        raise SynchronizationError("RESAMPLE_QUERY_OUTSIDE_SERIES")
    low = 0
    high = len(time_s) - 1
    while high - low > 1:
        mid = (low + high) // 2
        if time_s[mid] <= query:
            low = mid
        else:
            high = mid
    span = time_s[high] - time_s[low]
    if span == 0:
        return values[low]
    fraction = (query - time_s[low]) / span
    return values[low] + fraction * (values[high] - values[low])


def resample(
    channel: MeasurementChannel,
    *,
    rate_hz: float,
    start_s: float | None = None,
    end_s: float | None = None,
) -> MeasurementChannel:
    """Linearly resample onto a uniform grid; refuses to extrapolate."""

    finite(rate_hz, "resample rate", positive=True)
    start = channel.time_s[0] if start_s is None else start_s
    end = channel.time_s[-1] if end_s is None else end_s
    if start < channel.time_s[0] or end > channel.time_s[-1] or start >= end:
        raise SynchronizationError("RESAMPLE_WINDOW_OUTSIDE_SERIES")
    count = int(floor((end - start) * rate_hz)) + 1
    if count < 2:
        raise SynchronizationError("RESAMPLE_WINDOW_TOO_SHORT")
    step = 1.0 / rate_hz
    time_s = tuple(start + index * step for index in range(count))
    values = tuple(_interpolate(channel.time_s, channel.values, query) for query in time_s)
    return _derive(
        channel,
        name=f"{channel.name}:resampled",
        values=values,
        time_s=time_s,
        transform={"kind": "resample", "rateHz": rate_hz, "startS": start, "endS": end},
    )


@dataclass(frozen=True, slots=True)
class TriggerAlignment:
    """A trigger crossing location and the aligned channel."""

    trigger_time_s: float
    level: float
    direction: str
    channel: MeasurementChannel

    def canonical(self) -> dict[str, Any]:
        return {
            "triggerTimeS": self.trigger_time_s,
            "level": self.level,
            "direction": self.direction,
            "channel": self.channel.digest(),
        }


def trigger_time(channel: MeasurementChannel, *, level: float, direction: str = "rising") -> float:
    """Interpolate the first level crossing, failing closed if none exists."""

    if direction not in {"rising", "falling"}:
        raise SynchronizationError(f"UNKNOWN_TRIGGER_DIRECTION:{direction}")
    finite(level, "trigger level")
    for index in range(1, len(channel.values)):
        previous = channel.values[index - 1] - level
        current = channel.values[index] - level
        crossed = previous < 0 <= current if direction == "rising" else previous > 0 >= current
        if not crossed:
            continue
        span = channel.values[index] - channel.values[index - 1]
        if span == 0:
            return channel.time_s[index]
        fraction = (level - channel.values[index - 1]) / span
        lower_time = channel.time_s[index - 1]
        return lower_time + fraction * (channel.time_s[index] - lower_time)
    raise SynchronizationError("TRIGGER_LEVEL_NEVER_CROSSED")


def align_to_trigger(
    channel: MeasurementChannel, *, level: float, direction: str = "rising"
) -> TriggerAlignment:
    """Shift time so the trigger crossing sits at zero; raw data is unchanged."""

    crossing = trigger_time(channel, level=level, direction=direction)
    time_s = tuple(value - crossing for value in channel.time_s)
    aligned = _derive(
        channel,
        name=f"{channel.name}:aligned",
        values=channel.values,
        time_s=time_s,
        transform={
            "kind": "trigger-alignment",
            "level": level,
            "direction": direction,
            "triggerTimeS": crossing,
        },
    )
    return TriggerAlignment(
        trigger_time_s=crossing, level=level, direction=direction, channel=aligned
    )


def apply_filter(channel: MeasurementChannel, spec: FilterSpec) -> MeasurementChannel:
    """Apply a recorded filter; the filter parameters are part of the lineage."""

    if spec.kind == "moving_average":
        window = spec.window
        values: list[float] = []
        for index in range(len(channel.values)):
            start = max(0, index - window + 1)
            window_values = channel.values[start : index + 1]
            values.append(sum(window_values) / len(window_values))
    else:
        assert spec.cutoff_hz is not None
        dt = 1.0 / _rate(channel.time_s)
        tau = 1.0 / (2.0 * pi * spec.cutoff_hz)
        alpha = dt / (tau + dt)
        values = []
        previous = channel.values[0]
        for value in channel.values:
            previous = previous + alpha * (value - previous)
            values.append(previous)
    return _derive(
        channel,
        name=f"{channel.name}:filtered",
        values=tuple(values),
        time_s=channel.time_s,
        transform={"kind": "filter", "spec": spec.canonical()},
        filtering=(*channel.filtering, spec.kind),
    )


@dataclass(frozen=True, slots=True)
class Spectrum:
    """A single-sided amplitude spectrum of a measured channel."""

    source_name: str
    unit: str
    sample_rate_hz: float
    frequencies_hz: tuple[float, ...]
    amplitudes: tuple[float, ...]
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    def peak(self) -> tuple[float, float]:
        index = max(range(len(self.amplitudes)), key=self.amplitudes.__getitem__)
        return self.frequencies_hz[index], self.amplitudes[index]

    def canonical(self) -> dict[str, Any]:
        return {
            "sourceName": self.source_name,
            "unit": self.unit,
            "sampleRateHz": self.sample_rate_hz,
            "frequenciesHz": list(self.frequencies_hz),
            "amplitudes": list(self.amplitudes),
            "inputsHash": self.inputs_hash,
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def spectrum(channel: MeasurementChannel) -> Spectrum:
    """Naive single-sided DFT magnitude spectrum (deterministic, tiny-series safe)."""

    count = len(channel.values)
    rate = _rate(channel.time_s)
    mean = sum(channel.values) / count
    centered = tuple(value - mean for value in channel.values)
    half = count // 2
    frequencies: list[float] = []
    amplitudes: list[float] = []
    for index in range(half + 1):
        real = sum(centered[n] * cos(2 * pi * index * n / count) for n in range(count))
        imag = sum(centered[n] * sin(2 * pi * index * n / count) for n in range(count))
        magnitude = sqrt(real * real + imag * imag) / count
        scale = 1.0 if index in {0, half} else 2.0
        frequencies.append(index * rate / count)
        amplitudes.append(scale * magnitude)
    payload = {"sourceDigest": channel.digest(), "frequenciesHz": frequencies}
    return Spectrum(
        source_name=channel.name,
        unit=channel.unit,
        sample_rate_hz=rate,
        frequencies_hz=tuple(frequencies),
        amplitudes=tuple(amplitudes),
        inputs_hash=content_digest(payload),
        software=channel.software,
        provenance=derived_measurement_provenance(
            "spectrum",
            payload,
            assumptions=("single-sided DFT magnitude with mean removed",),
        ),
    )


@dataclass(frozen=True, slots=True)
class OrderSpectrum:
    """A spectrum expressed in orders of a reference shaft/rotation frequency."""

    reference_hz: float
    orders: tuple[float, ...]
    amplitudes: tuple[float, ...]
    source_digest: str
    inputs_hash: str
    software: SoftwareIdentity
    provenance: Provenance

    def canonical(self) -> dict[str, Any]:
        return {
            "referenceHz": self.reference_hz,
            "orders": list(self.orders),
            "amplitudes": list(self.amplitudes),
            "sourceDigest": self.source_digest,
            "inputsHash": self.inputs_hash,
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def order_spectrum(source: Spectrum, *, reference_hz: float) -> OrderSpectrum:
    """Convert a frequency spectrum into orders of a reference frequency."""

    finite(reference_hz, "reference frequency", positive=True)
    orders = tuple(frequency / reference_hz for frequency in source.frequencies_hz)
    payload = {"source": source.digest(), "referenceHz": reference_hz}
    return OrderSpectrum(
        reference_hz=reference_hz,
        orders=orders,
        amplitudes=source.amplitudes,
        source_digest=source.digest(),
        inputs_hash=content_digest(payload),
        software=source.software,
        provenance=derived_measurement_provenance(
            "order-spectrum", payload, assumptions=("order = frequency / reference frequency",)
        ),
    )


@dataclass(frozen=True, slots=True)
class CycleSegment:
    """One segmented cycle window of a measured channel."""

    index: int
    start_s: float
    end_s: float
    time_s: tuple[float, ...]
    values: tuple[float, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "startS": self.start_s,
            "endS": self.end_s,
            "timeS": list(self.time_s),
            "values": list(self.values),
        }


def segment_cycles(
    channel: MeasurementChannel, *, reference_hz: float, cycles_per_segment: int = 1
) -> tuple[CycleSegment, ...]:
    """Split a channel into reference-clock cycles, dropping the partial tail."""

    finite(reference_hz, "reference frequency", positive=True)
    if cycles_per_segment < 1:
        raise SynchronizationError("CYCLES_PER_SEGMENT_MUST_BE_POSITIVE")
    period = cycles_per_segment / reference_hz
    start = channel.time_s[0]
    segments: list[CycleSegment] = []
    index = 0
    while start + period <= channel.time_s[-1]:
        end = start + period
        window_time = tuple(value for value in channel.time_s if start <= value < end)
        if len(window_time) < 2:
            start = end
            continue
        window_values = tuple(
            _interpolate(channel.time_s, channel.values, value) for value in window_time
        )
        segments.append(
            CycleSegment(
                index=index,
                start_s=start,
                end_s=end,
                time_s=window_time,
                values=window_values,
            )
        )
        start = end
        index += 1
    if not segments:
        raise SynchronizationError("CYCLE_SEGMENTATION_PRODUCED_NO_SEGMENTS")
    return tuple(segments)


@dataclass(frozen=True, slots=True)
class EventSegment:
    """One event window above/below a threshold."""

    index: int
    start_s: float
    end_s: float
    peak: float

    def canonical(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "startS": self.start_s,
            "endS": self.end_s,
            "peak": self.peak,
        }


def segment_events(
    channel: MeasurementChannel,
    *,
    level: float,
    direction: str = "above",
    min_duration_s: float = 0.0,
) -> tuple[EventSegment, ...]:
    """Segment threshold-crossing events, failing closed if none are found."""

    if direction not in {"above", "below"}:
        raise SynchronizationError(f"UNKNOWN_EVENT_DIRECTION:{direction}")
    finite(level, "event level")
    finite(min_duration_s, "minimum event duration", minimum=0.0)
    segments: list[EventSegment] = []
    active = False
    start = 0.0
    peak = 0.0
    index = 0
    for time, value in zip(channel.time_s, channel.values, strict=True):
        inside = value >= level if direction == "above" else value <= level
        if inside and not active:
            active = True
            start = time
            peak = value
        elif inside:
            peak = max(peak, value) if direction == "above" else min(peak, value)
        elif active:
            active = False
            if time - start >= min_duration_s:
                segments.append(EventSegment(index=index, start_s=start, end_s=time, peak=peak))
                index += 1
    if active and channel.time_s[-1] - start >= min_duration_s:
        segments.append(
            EventSegment(index=index, start_s=start, end_s=channel.time_s[-1], peak=peak)
        )
    if not segments:
        raise SynchronizationError("EVENT_SEGMENTATION_PRODUCED_NO_SEGMENTS")
    return tuple(segments)
