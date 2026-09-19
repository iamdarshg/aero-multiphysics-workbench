"""Immutable transient time-history results with full engineering provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance

from .errors import TransientValidationError
from .units import require_unit
from .validity import Fidelity, Validity, finite


@dataclass(frozen=True, slots=True)
class TimeSeries:
    """One deterministic time history of a scalar, unit-bearing signal."""

    name: str
    unit: str
    times_s: tuple[float, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise TransientValidationError("series.name is required")
        require_unit(self.unit)
        if not self.times_s:
            raise TransientValidationError(f"series.{self.name} has no samples")
        if len(self.times_s) != len(self.values):
            raise TransientValidationError(f"series.{self.name} length mismatch")
        for index, (time, value) in enumerate(zip(self.times_s, self.values, strict=True)):
            finite(time, f"series.{self.name}.time[{index}]")
            finite(value, f"series.{self.name}.value[{index}]")

    def final(self) -> float:
        return self.values[-1]

    def minimum(self) -> float:
        return min(self.values)

    def maximum(self) -> float:
        return max(self.values)

    def at(self, index: int) -> float:
        return self.values[index]

    def peak_to_peak(self) -> float:
        return self.maximum() - self.minimum()

    def mean(self) -> float:
        return sum(self.values) / len(self.values)

    def rms(self) -> float:
        total: float = 0.0
        for value in self.values:
            total += value * value
        return float((total / len(self.values)) ** 0.5)

    def reversals(self) -> int:
        """Count direction reversals, a deterministic fatigue-loading proxy."""

        reversals = 0
        previous_sign = 0
        for earlier, later in zip(self.values, self.values[1:], strict=False):
            delta = later - earlier
            sign = (delta > 0.0) - (delta < 0.0)
            if sign != 0 and previous_sign != 0 and sign != previous_sign:
                reversals += 1
            if sign != 0:
                previous_sign = sign
        return reversals

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "timesS": list(self.times_s),
            "values": list(self.values),
        }


@dataclass(frozen=True, slots=True)
class IntegratorReceipt:
    """Declared time-integration method and its deterministic step accounting."""

    method: str
    step_size_s: float
    steps: int
    duration_s: float
    recorded_points: int

    def canonical(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "stepSizeS": self.step_size_s,
            "steps": self.steps,
            "durationS": self.duration_s,
            "recordedPoints": self.recorded_points,
        }


@dataclass(frozen=True, slots=True)
class EventRecord:
    """One discrete event observed during a transient."""

    time_s: float
    kind: str
    target: str
    value: float

    def canonical(self) -> dict[str, Any]:
        return {
            "timeS": self.time_s,
            "kind": self.kind,
            "target": self.target,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class TransientResult:
    """The complete, provenance-bearing output of a transient simulation."""

    scenario_id: str
    times_s: tuple[float, ...]
    series: tuple[TimeSeries, ...]
    signals: tuple[TimeSeries, ...]
    fidelity: Fidelity
    validity: Validity
    provenance: Provenance
    integrator: IntegratorReceipt
    events: tuple[EventRecord, ...]
    trips: tuple[str, ...]

    def series_for(self, name: str) -> TimeSeries:
        for series in self.series:
            if series.name == name:
                return series
        raise TransientValidationError(f"UNKNOWN_SERIES:{name}")

    def signal(self, name: str) -> TimeSeries:
        for series in self.signals:
            if series.name == name:
                return series
        raise TransientValidationError(f"UNKNOWN_SIGNAL:{name}")

    def fatigue_evidence(self) -> dict[str, dict[str, float]]:
        """Peak-to-peak and reversal histories to feed fatigue participants."""

        return {
            series.name: {
                "peak_to_peak": series.peak_to_peak(),
                "reversals": float(series.reversals()),
            }
            for series in self.series
        }

    def canonical(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "fidelity": self.fidelity.value,
            "validity": self.validity.as_dict(),
            "integrator": self.integrator.canonical(),
            "events": [event.canonical() for event in self.events],
            "trips": list(self.trips),
            "series": [series.canonical() for series in self.series],
            "signals": [series.canonical() for series in self.signals],
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "modelVersion": self.provenance.model_version,
                "inputsHash": self.provenance.inputs_hash,
                "solverName": self.provenance.solver_name,
                "solverVersion": self.provenance.solver_version,
                "runId": self.provenance.run_id,
            },
        }


@dataclass(frozen=True, slots=True)
class SteadyStateResult:
    """A solved steady operating point, explicitly distinct from transient."""

    scenario_id: str
    state: tuple[tuple[str, float], ...]
    residual: float
    converged: bool
    fidelity: Fidelity
    validity: Validity
    provenance: Provenance

    def value(self, name: str) -> float:
        for key, value in self.state:
            if key == name:
                return value
        raise TransientValidationError(f"UNKNOWN_STEADY_STATE:{name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "state": {key: value for key, value in self.state},
            "residual": self.residual,
            "converged": self.converged,
            "fidelity": self.fidelity.value,
            "validity": self.validity.as_dict(),
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "inputsHash": self.provenance.inputs_hash,
            },
        }


__all__ = [
    "EventRecord",
    "IntegratorReceipt",
    "SteadyStateResult",
    "TimeSeries",
    "TransientResult",
]
