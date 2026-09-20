"""Control schedules as bounded, co-optimizable design variables."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from ..canonical import content_digest
from .errors import OffdesignInputError

SCHEDULE_VARIABLES: tuple[str, ...] = (
    "speed",
    "variable_guide_vane",
    "bleed",
    "nozzle",
    "fuel_heat_input",
    "motor_command",
)


@dataclass(frozen=True, slots=True)
class ControlChannel:
    """One scheduled control variable keyed by operating-point id."""

    channel_id: str
    variable: str
    values: tuple[tuple[str, float], ...]
    lower: float
    upper: float
    max_slew: float | None = None
    monotonic: str = "none"

    def __post_init__(self) -> None:
        if not self.channel_id.strip():
            raise OffdesignInputError("SCHEDULE_CHANNEL_ID_REQUIRED")
        if self.variable not in SCHEDULE_VARIABLES:
            raise OffdesignInputError(f"SCHEDULE_UNKNOWN_VARIABLE:{self.variable}")
        if self.monotonic not in {"none", "increasing", "decreasing"}:
            raise OffdesignInputError(f"SCHEDULE_UNKNOWN_MONOTONICITY:{self.monotonic}")
        if not isfinite(self.lower) or not isfinite(self.upper) or not self.lower <= self.upper:
            raise OffdesignInputError(f"SCHEDULE_BOUNDS_INVALID:{self.channel_id}")
        if self.max_slew is not None and (
            not isfinite(self.max_slew) or self.max_slew < 0.0
        ):
            raise OffdesignInputError(f"SCHEDULE_SLEW_INVALID:{self.channel_id}")
        if not self.values:
            raise OffdesignInputError(f"SCHEDULE_NEEDS_VALUES:{self.channel_id}")
        seen: set[str] = set()
        for point_id, value in self.values:
            if not point_id.strip() or point_id in seen:
                raise OffdesignInputError(
                    f"SCHEDULE_POINT_ID_INVALID:{self.channel_id}:{point_id}"
                )
            seen.add(point_id)
            if not isfinite(value):
                raise OffdesignInputError(
                    f"SCHEDULE_VALUE_NONFINITE:{self.channel_id}:{point_id}"
                )

    def evaluate(self, point_id: str) -> float:
        for candidate, value in self.values:
            if candidate == point_id:
                return value
        raise OffdesignInputError(f"SCHEDULE_NO_VALUE:{self.channel_id}:{point_id}")

    def check(self, ordered_point_ids: tuple[str, ...]) -> tuple[str, ...]:
        violations: list[str] = []
        ordered = [self.evaluate(point_id) for point_id in ordered_point_ids]
        for point_id, value in zip(ordered_point_ids, ordered, strict=True):
            if not self.lower <= value <= self.upper:
                violations.append(f"{self.channel_id}:{point_id}:range")
        if self.max_slew is not None:
            for first, second in zip(ordered, ordered[1:], strict=False):
                if abs(second - first) > self.max_slew:
                    violations.append(f"{self.channel_id}:slew")
                    break
        if self.monotonic == "increasing" and any(
            second < first for first, second in zip(ordered, ordered[1:], strict=False)
        ):
            violations.append(f"{self.channel_id}:monotonicity")
        if self.monotonic == "decreasing" and any(
            second > first for first, second in zip(ordered, ordered[1:], strict=False)
        ):
            violations.append(f"{self.channel_id}:monotonicity")
        return tuple(violations)

    def canonical(self) -> dict[str, object]:
        return {
            "channelId": self.channel_id,
            "variable": self.variable,
            "values": [[point_id, value] for point_id, value in self.values],
            "lower": self.lower,
            "upper": self.upper,
            "maxSlew": self.max_slew,
            "monotonic": self.monotonic,
        }


@dataclass(frozen=True, slots=True)
class ControlSchedule:
    """The set of scheduled controls applied across the operating envelope."""

    channels: tuple[ControlChannel, ...] = ()

    def __post_init__(self) -> None:
        ids = [channel.channel_id for channel in self.channels]
        if len(set(ids)) != len(ids):
            raise OffdesignInputError("SCHEDULE_DUPLICATE_CHANNEL_ID")

    def values_for(self, point_id: str) -> dict[str, float]:
        applied: dict[str, float] = {}
        for channel in self.channels:
            applied[channel.channel_id] = channel.evaluate(point_id)
        return applied

    def validate(self, ordered_point_ids: tuple[str, ...]) -> tuple[str, ...]:
        violations: list[str] = []
        for channel in self.channels:
            try:
                violations.extend(channel.check(ordered_point_ids))
            except OffdesignInputError as exc:
                violations.append(f"{channel.channel_id}:missing:{exc.detail}")
        return tuple(violations)

    def as_design_variables(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "name": channel.channel_id,
                "unit": "dimensionless",
                "kind": "continuous",
                "lower": channel.lower,
                "upper": channel.upper,
                "values": [value for _, value in channel.values],
            }
            for channel in self.channels
        )

    def apply_to_mapping(self, point_id: str) -> Mapping[str, float]:
        return dict(self.values_for(point_id))

    def canonical(self) -> dict[str, object]:
        return {
            "channels": [
                channel.canonical()
                for channel in sorted(self.channels, key=lambda item: item.channel_id)
            ]
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


__all__ = [
    "SCHEDULE_VARIABLES",
    "ControlChannel",
    "ControlSchedule",
]
