"""Rainflow-compatible cycle counting from transient load histories.

A transient load channel is reduced to turning points and then to full and half
cycles with an explicit range, mean, and count using the standard three-point
rainflow (ASTM E1049) contract. The counting result is provenance-backed and
carries its method identity; it makes no claim about material behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .units import require_unit
from .validity import DurabilityError, Validity, finite

__all__ = [
    "CountingResult",
    "Cycle",
    "LoadHistory",
    "rainflow_count",
    "turning_points",
]


@dataclass(frozen=True, slots=True)
class Cycle:
    """One counted load cycle with a range, mean, and occurrence count."""

    range_value: float
    mean_value: float
    count: float
    unit: str

    def __post_init__(self) -> None:
        require_unit(self.unit)
        if finite(self.range_value, "cycle.range_value") < 0.0:
            raise DurabilityError("cycle.range_value must be non-negative")
        finite(self.mean_value, "cycle.mean_value")
        if finite(self.count, "cycle.count", positive=True) <= 0.0:
            raise DurabilityError("cycle.count must be positive")

    @property
    def amplitude(self) -> float:
        return 0.5 * self.range_value

    def as_dict(self) -> dict[str, Any]:
        return {
            "range": self.range_value,
            "mean": self.mean_value,
            "count": self.count,
            "unit": self.unit,
        }


def turning_points(values: tuple[float, ...]) -> tuple[float, ...]:
    """Extract the alternating peaks and valleys of a sampled channel."""

    if len(values) < 2:
        raise DurabilityError("load history needs at least two samples")
    for index, value in enumerate(values):
        finite(value, f"values[{index}]")
    points: list[float] = [values[0]]
    for previous, current, following in zip(values, values[1:], values[2:], strict=False):
        rising = current > previous and current >= following
        falling = current < previous and current <= following
        if (rising or falling) and points[-1] != current:
            points.append(current)
    if values[-1] != points[-1]:
        points.append(values[-1])
    return tuple(points)


@dataclass(frozen=True, slots=True)
class LoadHistory:
    """A uniform transient load channel with an SI unit and time base."""

    channel: str
    unit: str
    time_s: tuple[float, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.channel.strip():
            raise DurabilityError("load history channel is required")
        require_unit(self.unit)
        if len(self.time_s) != len(self.values):
            raise DurabilityError("load history time and value lengths must match")
        if len(self.values) < 2:
            raise DurabilityError("load history needs at least two samples")
        previous = None
        for index, time in enumerate(self.time_s):
            value = finite(time, f"time_s[{index}]")
            if previous is not None and value <= previous:
                raise DurabilityError("load history times must be strictly increasing")
            previous = value
        for index, sample in enumerate(self.values):
            finite(sample, f"values[{index}]")

    @property
    def duration_s(self) -> float:
        return self.time_s[-1] - self.time_s[0]

    def peak(self) -> float:
        return max(self.values)

    def valley(self) -> float:
        return min(self.values)

    def turning_points(self) -> tuple[float, ...]:
        return turning_points(self.values)


@dataclass(frozen=True, slots=True)
class CountingResult:
    """Provenance-backed rainflow cycle-counting outcome."""

    cycles: tuple[Cycle, ...]
    residual: tuple[Cycle, ...]
    unit: str
    method: str
    provenance: Provenance
    validity: Validity

    def all_cycles(self) -> tuple[Cycle, ...]:
        return self.cycles + self.residual

    def total_count(self) -> float:
        return float(sum(cycle.count for cycle in self.all_cycles()))

    def maximum_range(self) -> float:
        cycles = self.all_cycles()
        if not cycles:
            raise DurabilityError("no cycles were counted")
        return max(cycle.range_value for cycle in cycles)

    def units(self) -> dict[str, str]:
        return {name: self.unit for name in ("range_value", "mean_value")}

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit": self.unit,
            "method": self.method,
            "cycles": [cycle.as_dict() for cycle in self.cycles],
            "residual": [cycle.as_dict() for cycle in self.residual],
            "totalCount": self.total_count(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def rainflow_count(history: LoadHistory) -> CountingResult:
    """Count full and half cycles from a load history using three-point rainflow."""

    points = history.turning_points()
    stack: list[float] = []
    cycles: list[Cycle] = []
    for point in points:
        stack.append(point)
        while len(stack) >= 3:
            last, previous, before = stack[-1], stack[-2], stack[-3]
            if abs(last - previous) >= abs(previous - before):
                cycles.append(
                    Cycle(
                        range_value=abs(previous - before),
                        mean_value=0.5 * (previous + before),
                        count=1.0,
                        unit=history.unit,
                    )
                )
                del stack[-3:-1]
            else:
                break
    residual = tuple(
        Cycle(
            range_value=abs(second - first),
            mean_value=0.5 * (first + second),
            count=0.5,
            unit=history.unit,
        )
        for first, second in zip(stack, stack[1:], strict=False)
    )
    provenance = analytical_provenance(
        "rainflow-counting",
        {
            "channel": history.channel,
            "unit": history.unit,
            "values": list(history.values),
            "method": "three-point-rainflow",
        },
        assumptions=(
            "turning points extracted from a uniformly sampled channel",
            "half cycles below the largest range are retained with count 0.5",
        ),
    )
    return CountingResult(
        cycles=tuple(cycles),
        residual=residual,
        unit=history.unit,
        method="three-point-rainflow",
        provenance=provenance,
        validity=Validity(
            passed=bool(cycles) or bool(residual),
            checks={"cycles_found": bool(cycles) or bool(residual)},
            detail=f"rainflow:{history.channel}",
        ),
    )
