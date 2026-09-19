"""Discrete transient events: startup/shutdown, ramps, load rejection, faults.

An ``EventSchedule`` maps absolute time onto a set of input overrides. Step
events apply instantly; ramp events interpolate from a declared start value.
Event kinds are semantic labels so startup, shutdown, acceleration,
deceleration, load rejection, command steps/ramps, and faults are all first
class and recorded in the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import TransientValidationError
from .units import require_unit
from .validity import finite


class EventKind(StrEnum):
    """The generic discrete-event categories a transient may carry."""

    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    ACCELERATION = "acceleration"
    DECELERATION = "deceleration"
    LOAD_REJECTION = "load-rejection"
    COMMAND_STEP = "command-step"
    COMMAND_RAMP = "command-ramp"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class DiscreteEvent:
    """One time-stamped input override applied during a transient."""

    time_s: float
    kind: EventKind
    target: str
    value: float
    unit: str
    ramp_duration_s: float = 0.0
    start_value: float = 0.0

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise TransientValidationError("event.target is required")
        finite(self.time_s, "event.time_s", minimum=0.0)
        finite(self.value, "event.value")
        finite(self.ramp_duration_s, "event.ramp_duration_s", minimum=0.0)
        finite(self.start_value, "event.start_value")
        require_unit(self.unit)

    def value_at(self, time_s: float) -> float:
        if time_s < self.time_s:
            return self.start_value
        if self.ramp_duration_s <= 0.0:
            return self.value
        fraction = min(1.0, (time_s - self.time_s) / self.ramp_duration_s)
        return self.start_value + (self.value - self.start_value) * fraction

    def canonical(self) -> dict[str, Any]:
        return {
            "timeS": self.time_s,
            "kind": self.kind.value,
            "target": self.target,
            "value": self.value,
            "unit": self.unit,
            "rampDurationS": self.ramp_duration_s,
            "startValue": self.start_value,
        }


@dataclass(frozen=True, slots=True)
class EventSchedule:
    """An ordered collection of discrete events over a transient window."""

    events: tuple[DiscreteEvent, ...]

    def __post_init__(self) -> None:
        for event in self.events:
            if not isinstance(event, DiscreteEvent):
                raise TransientValidationError("schedule entries must be DiscreteEvent")

    def ordered(self) -> tuple[DiscreteEvent, ...]:
        return tuple(sorted(self.events, key=lambda event: event.time_s))

    def inputs_at(self, time_s: float) -> dict[str, float]:
        """Resolve every active override at ``time_s`` (later events win)."""

        values: dict[str, float] = {}
        for event in self.ordered():
            if event.time_s <= time_s:
                values[event.target] = event.value_at(time_s)
        return values

    def fired(self, previous_time_s: float, time_s: float) -> tuple[DiscreteEvent, ...]:
        """Return events whose start lies in ``(previous_time_s, time_s]``."""

        return tuple(
            event
            for event in self.ordered()
            if previous_time_s < event.time_s <= time_s
        )

    def active_kinds(self, time_s: float) -> tuple[EventKind, ...]:
        return tuple(
            event.kind for event in self.ordered() if event.time_s <= time_s
        )

    def canonical(self) -> list[dict[str, Any]]:
        return [event.canonical() for event in self.ordered()]


__all__ = ["DiscreteEvent", "EventKind", "EventSchedule"]
