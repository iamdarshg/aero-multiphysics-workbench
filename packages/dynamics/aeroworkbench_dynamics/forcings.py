"""Participant-declared forcing spectra and generic resonance assessment.

Nothing in this module invents a frequency. Every forcing line is declared by a
participant with a source id, a frequency in Hz and/or a rotational order, an
optional amplitude, an explicit speed dependence, and optional harmonic-family
metadata. Assessment compares declared lines against computed mode frequencies
and reports separation margins plus the higher-fidelity capability that a
resonance trigger should request from the generic fidelity planner.

No blade-pass, stator-pass, or other domain frequency is generated here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

SPEED_DEPENDENCE = ("fixed", "constant", "synchronous", "order")
STATE_CLEAR = "clear"
STATE_WATCH = "watch"
STATE_TRIGGERED = "triggered"


class ForcingSpecError(ValueError):
    """Raised when a declared forcing spectrum is not well formed."""


def _finite(
    value: Any, name: str, *, minimum: float | None = None, positive: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForcingSpecError(f"{name} must be a number")
    result = float(value)
    if not isfinite(result):
        raise ForcingSpecError(f"{name} must be finite")
    if positive and result <= 0:
        raise ForcingSpecError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise ForcingSpecError(f"{name} must be >= {minimum}")
    return result


@dataclass(frozen=True, slots=True)
class ForcingLine:
    """One participant-declared forcing line."""

    source: str
    label: str = "forcing"
    frequency_hz: float | None = None
    amplitude: float | None = None
    order: float | None = None
    speed_dependence: str = "fixed"
    harmonic_family: str | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ForcingSpecError("forcing source is required")
        if not self.label.strip():
            raise ForcingSpecError("forcing label is required")
        if self.speed_dependence not in SPEED_DEPENDENCE:
            raise ForcingSpecError(
                f"speed_dependence must be one of {sorted(SPEED_DEPENDENCE)}"
            )
        if self.frequency_hz is None and self.order is None:
            raise ForcingSpecError("forcing line needs a frequency_hz or an order")
        if self.frequency_hz is not None:
            _finite(self.frequency_hz, "frequency_hz", minimum=0.0)
        if self.amplitude is not None:
            _finite(self.amplitude, "amplitude", minimum=0.0)
        if self.order is not None:
            _finite(self.order, "order", minimum=0.0)
        if self.harmonic_family is not None and not self.harmonic_family.strip():
            raise ForcingSpecError("harmonic_family must be non-empty when given")

    def frequency_at(self, speed_rpm: float) -> float:
        """Resolve this line's frequency at a shaft speed without inventing data."""

        if self.speed_dependence == "synchronous":
            speed = _finite(speed_rpm, "speed_rpm", minimum=0.0)
            return speed / 60.0
        if self.order is not None and (
            self.frequency_hz is None or self.speed_dependence == "order"
        ):
            speed = _finite(speed_rpm, "speed_rpm", minimum=0.0)
            return self.order * speed / 60.0
        if self.frequency_hz is not None:
            return self.frequency_hz
        assert self.order is not None  # guarded by __post_init__
        speed = _finite(speed_rpm, "speed_rpm", minimum=0.0)
        return self.order * speed / 60.0

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "label": self.label,
            "frequency_hz": self.frequency_hz,
            "amplitude": self.amplitude,
            "order": self.order,
            "speed_dependence": self.speed_dependence,
            "harmonic_family": self.harmonic_family,
        }


def _line_from_mapping(entry: Mapping[str, Any], source: str, label: str) -> ForcingLine:
    return ForcingLine(
        source=str(entry.get("source", entry.get("source_id", source))),
        label=str(entry.get("label", label)),
        frequency_hz=(
            None if entry.get("frequency_hz") is None else entry.get("frequency_hz")
        ),
        amplitude=entry.get("amplitude"),
        order=entry.get("order"),
        speed_dependence=str(entry.get("speed_dependence", "fixed")),
        harmonic_family=entry.get("harmonic_family"),
    )


def normalize_forcing_lines(raw: Any) -> tuple[ForcingLine, ...]:
    """Normalize declared forcing spectra from a participant into typed lines."""

    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ForcingSpecError("forcings must be a sequence")
    lines: list[ForcingLine] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ForcingSpecError("each forcing entry must be a mapping")
        source = str(entry.get("source", entry.get("source_id", "")))
        label = str(entry.get("label", "forcing"))
        nested = entry.get("lines")
        if nested is not None:
            if not isinstance(nested, Sequence) or isinstance(nested, (str, bytes)):
                raise ForcingSpecError("forcing lines must be a sequence")
            for line_entry in nested:
                if not isinstance(line_entry, Mapping):
                    raise ForcingSpecError("each forcing line must be a mapping")
                lines.append(_line_from_mapping(line_entry, source, label))
        else:
            lines.append(_line_from_mapping(entry, source, label))
    return tuple(lines)


@dataclass(frozen=True, slots=True)
class ForcingMargin:
    """One resolved line and its nearest computed mode."""

    source: str
    label: str
    frequency_hz: float
    nearest_mode_hz: float
    margin_hz: float
    amplitude: float | None = None
    order: float | None = None
    speed_dependence: str = "fixed"
    harmonic_family: str | None = None
    at_speed_rpm: float = 0.0

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "label": self.label,
            "frequency_hz": self.frequency_hz,
            "amplitude": self.amplitude,
            "order": self.order,
            "speed_dependence": self.speed_dependence,
            "harmonic_family": self.harmonic_family,
            "nearest_mode_hz": self.nearest_mode_hz,
            "margin_hz": self.margin_hz,
            "at_speed_rpm": self.at_speed_rpm,
        }


@dataclass(frozen=True, slots=True)
class ForcingAssessment:
    """Separation of declared forcing lines from computed modes."""

    minima_hz: float
    state: str
    required_capability: str | None
    lines: tuple[ForcingMargin, ...]
    detail: str

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "min_separation_hz": self.minima_hz,
            "state": self.state,
            "required_capability": self.required_capability,
            "lines": [line.canonical_payload() for line in self.lines],
            "detail": self.detail,
        }

    def fidelity_signal(self, *, reference_hz: float) -> dict[str, Any]:
        """Map the assessment to generic fidelity-planner signal fields."""

        reference = _finite(reference_hz, "reference_hz", positive=True)
        proximity = min(self.minima_hz / reference, 1.0)
        return {
            "resonance_proximity": proximity,
            "required_capability": self.required_capability,
        }


def _nearest(mode_frequencies_hz: Sequence[float], frequency: float) -> float:
    usable = [value for value in mode_frequencies_hz if isfinite(value) and value > 0.0]
    if not usable:
        raise ForcingSpecError("mode frequencies must contain a positive value")
    return min(usable, key=lambda mode: abs(mode - frequency))


def assess_forcing_separation(
    lines: Sequence[ForcingLine],
    mode_frequencies_hz: Sequence[float],
    *,
    speed_rpm: float,
    warning_margin_hz: float = 5.0,
    critical_margin_hz: float = 2.0,
    watch_capability: str = "harmonic",
    critical_capability: str = "transient",
) -> ForcingAssessment:
    """Compare declared forcing lines with computed modes at one speed."""

    warning = _finite(warning_margin_hz, "warning_margin_hz", positive=True)
    critical = _finite(critical_margin_hz, "critical_margin_hz", positive=True)
    if critical > warning:
        raise ForcingSpecError("critical margin must not exceed the warning margin")
    if not lines:
        raise ForcingSpecError("at least one forcing line is required")
    resolved: list[ForcingMargin] = []
    for line in lines:
        frequency = line.frequency_at(speed_rpm)
        nearest = _nearest(mode_frequencies_hz, frequency)
        resolved.append(
            ForcingMargin(
                source=line.source,
                label=line.label,
                frequency_hz=frequency,
                nearest_mode_hz=nearest,
                margin_hz=abs(nearest - frequency),
                amplitude=line.amplitude,
                order=line.order,
                speed_dependence=line.speed_dependence,
                harmonic_family=line.harmonic_family,
                at_speed_rpm=speed_rpm,
            )
        )
    ordered = tuple(sorted(resolved, key=lambda item: item.margin_hz))
    minima = ordered[0].margin_hz
    if minima <= critical:
        state = STATE_TRIGGERED
        capability: str | None = critical_capability
    elif minima <= warning:
        state = STATE_WATCH
        capability = watch_capability
    else:
        state = STATE_CLEAR
        capability = None
    return ForcingAssessment(
        minima_hz=minima,
        state=state,
        required_capability=capability,
        lines=ordered,
        detail=(
            f"closest declared forcing line margin {minima:.4g} Hz at {speed_rpm:.1f} rpm; "
            f"state={state}"
        ),
    )
