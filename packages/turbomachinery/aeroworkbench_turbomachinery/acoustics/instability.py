"""Compressor/fan instability indicators: stall, rotating stall, and surge margin.

Indicators are measured against declared stability boundaries and unsteady
oscillation content, never assumed. Proximity is normalized so a value near zero
means the operating point sits close to a boundary; near-boundary and oscillatory
conditions request a higher-fidelity transient analysis from the shared planner.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from ..canonical import content_digest
from .errors import AcousticInputError
from .results import (
    DEFAULT_ACOUSTIC_SOFTWARE,
    AcousticFidelity,
    AcousticSoftware,
    AcousticValidity,
    analytical_provenance,
    check_validity,
    finite,
)

__all__ = [
    "InstabilityIndicators",
    "OperatingPoint",
    "OscillationLine",
    "StabilityBoundary",
    "UnsteadyOscillation",
    "assess_instability",
    "rotating_stall_order",
]

STATE_CLEAR = "clear"
STATE_WATCH = "watch"
STATE_TRIGGERED = "triggered"

_BOUNDARY_KINDS = ("surge", "stall")
_SIGNAL_KINDS = ("mass-flow", "pressure")


@dataclass(frozen=True, slots=True)
class StabilityBoundary:
    """A piecewise-linear stability boundary in the mass-flow/pressure-ratio plane."""

    boundary_id: str
    kind: str
    speed_rpm: float
    mass_flow_kg_s: tuple[float, ...]
    pressure_ratio: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.boundary_id.strip():
            raise AcousticInputError("stability boundary id is required")
        if self.kind not in _BOUNDARY_KINDS:
            raise AcousticInputError(f"UNKNOWN_STABILITY_BOUNDARY_KIND:{self.kind}")
        finite(self.speed_rpm, "speed_rpm", minimum=0.0)
        if len(self.mass_flow_kg_s) < 2 or len(self.mass_flow_kg_s) != len(self.pressure_ratio):
            raise AcousticInputError("stability boundary needs matching flow/pressure arrays")
        flow = tuple(
            finite(value, "mass_flow_kg_s", positive=True) for value in self.mass_flow_kg_s
        )
        ratio = tuple(
            finite(value, "pressure_ratio", positive=True) for value in self.pressure_ratio
        )
        if any(second <= first for first, second in zip(flow, flow[1:], strict=False)):
            raise AcousticInputError("stability boundary mass flow must be strictly increasing")
        object.__setattr__(self, "mass_flow_kg_s", flow)
        object.__setattr__(self, "pressure_ratio", ratio)

    def pressure_ratio_at(self, mass_flow_kg_s: float) -> float:
        flow = finite(mass_flow_kg_s, "mass_flow_kg_s")
        if not self.mass_flow_kg_s[0] <= flow <= self.mass_flow_kg_s[-1]:
            raise AcousticInputError("operating mass flow is outside the declared boundary")
        return _interp(flow, self.mass_flow_kg_s, self.pressure_ratio)

    def flow_at_pressure_ratio(self, pressure_ratio: float) -> float:
        ratio = finite(pressure_ratio, "pressure_ratio", positive=True)
        values = self.pressure_ratio
        if not values[0] <= ratio <= values[-1]:
            raise AcousticInputError("operating pressure ratio is outside the declared boundary")
        increasing = all(
            second > first for first, second in zip(values, values[1:], strict=False)
        )
        decreasing = all(
            second < first for first, second in zip(values, values[1:], strict=False)
        )
        if not (increasing or decreasing):
            raise AcousticInputError("stability boundary is not monotonic in pressure ratio")
        return _interp(ratio, values, self.mass_flow_kg_s)

    def canonical(self) -> dict[str, Any]:
        return {
            "boundaryId": self.boundary_id,
            "kind": self.kind,
            "speedRpm": self.speed_rpm,
            "massFlowKgS": list(self.mass_flow_kg_s),
            "pressureRatio": list(self.pressure_ratio),
        }


def _interp(x: float, xs: tuple[float, ...], ys: tuple[float, ...]) -> float:
    for index in range(len(xs) - 1):
        low, high = xs[index], xs[index + 1]
        if low <= x <= high:
            span = high - low
            if span <= 0.0:
                return ys[index]
            weight = (x - low) / span
            return ys[index] + weight * (ys[index + 1] - ys[index])
    return ys[-1]


@dataclass(frozen=True, slots=True)
class OperatingPoint:
    """One declared compressor/fan operating point."""

    mass_flow_kg_s: float
    pressure_ratio: float
    speed_rpm: float

    def __post_init__(self) -> None:
        finite(self.mass_flow_kg_s, "mass_flow_kg_s", positive=True)
        finite(self.pressure_ratio, "pressure_ratio", positive=True)
        finite(self.speed_rpm, "speed_rpm", minimum=0.0)

    def canonical(self) -> dict[str, Any]:
        return {
            "massFlowKgS": self.mass_flow_kg_s,
            "pressureRatio": self.pressure_ratio,
            "speedRpm": self.speed_rpm,
        }


@dataclass(frozen=True, slots=True)
class OscillationLine:
    """One unsteady mass-flow/pressure oscillation line."""

    label: str
    frequency_hz: float
    amplitude: float
    order: float | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise AcousticInputError("oscillation label is required")
        finite(self.frequency_hz, "frequency_hz", minimum=0.0)
        finite(self.amplitude, "amplitude", minimum=0.0)
        if self.order is not None:
            finite(self.order, "order")

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "frequency_hz": self.frequency_hz,
            "amplitude": self.amplitude,
            "order": self.order,
        }


@dataclass(frozen=True, slots=True)
class UnsteadyOscillation:
    """Unsteady mass-flow/pressure content from a transient record."""

    signal: str
    mean_value: float
    lines: tuple[OscillationLine, ...]

    def __post_init__(self) -> None:
        if self.signal not in _SIGNAL_KINDS:
            raise AcousticInputError(f"UNKNOWN_OSCILLATION_SIGNAL:{self.signal}")
        finite(self.mean_value, "mean_value", positive=True)
        if not self.lines:
            raise AcousticInputError(f"unsteady {self.signal} oscillation needs at least one line")
        identifiers = [line.label for line in self.lines]
        if len(identifiers) != len(set(identifiers)):
            raise AcousticInputError("oscillation labels must be unique")

    def relative_amplitude(self) -> float:
        energy = sum(line.amplitude * line.amplitude for line in self.lines)
        return sqrt(energy) / self.mean_value

    def dominant(self) -> OscillationLine:
        return max(self.lines, key=lambda line: (line.amplitude, -line.frequency_hz))

    def order_content(self) -> tuple[float, ...]:
        ordered = sorted(
            (line for line in self.lines if line.order is not None),
            key=lambda line: (-line.amplitude, line.label),
        )
        return tuple(abs(line.order) for line in ordered if line.order is not None)

    def canonical(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "meanValue": self.mean_value,
            "lines": [line.canonical() for line in self.lines],
        }


def rotating_stall_order(
    oscillation: UnsteadyOscillation, *, shaft_frequency_hz: float
) -> float | None:
    """Dominant rotating-stall order from unsteady content, never assumed."""

    shaft = finite(shaft_frequency_hz, "shaft_frequency_hz", minimum=0.0)
    content = oscillation.order_content()
    if content:
        return content[0]
    dominant = oscillation.dominant()
    if shaft <= 0.0:
        return None
    return abs(dominant.frequency_hz) / shaft


@dataclass(frozen=True, slots=True)
class InstabilityIndicators:
    """Compressor/fan stability margins and rotating-stall/surge proximity."""

    surge_margin_fraction: float
    stall_margin_fraction: float | None
    proximity: float
    state: str
    rotating_stall_order: float | None
    mass_flow_oscillation_fraction: float | None
    pressure_oscillation_fraction: float | None
    dominant_oscillation_hz: float | None
    required_capability: str | None
    fidelity: AcousticFidelity
    validity: AcousticValidity
    provenance: Provenance
    software: AcousticSoftware = DEFAULT_ACOUSTIC_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "surge_margin_fraction": "dimensionless",
            "stall_margin_fraction": "dimensionless",
            "proximity": "dimensionless",
            "mass_flow_oscillation_fraction": "dimensionless",
            "pressure_oscillation_fraction": "dimensionless",
            "dominant_oscillation_hz": "Hz",
            "rotating_stall_order": "dimensionless",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "surgeMarginFraction": self.surge_margin_fraction,
            "stallMarginFraction": self.stall_margin_fraction,
            "proximity": self.proximity,
            "state": self.state,
            "rotatingStallOrder": self.rotating_stall_order,
            "massFlowOscillationFraction": self.mass_flow_oscillation_fraction,
            "pressureOscillationFraction": self.pressure_oscillation_fraction,
            "dominantOscillationHz": self.dominant_oscillation_hz,
            "requiredCapability": self.required_capability,
            "fidelity": self.fidelity.value,
            "source": self.provenance.source.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())

    def promotion_signal(self) -> dict[str, Any]:
        return {
            "choke_stall_surge_proximity": self.proximity,
            "required_capability": self.required_capability,
        }


def _lower_margin(reference: float, actual: float) -> float:
    """Fractional headroom above a lower boundary."""

    return (actual - reference) / max(abs(actual), 1e-9)


def assess_instability(
    operating: OperatingPoint,
    *,
    surge_boundary: StabilityBoundary,
    stall_boundary: StabilityBoundary | None = None,
    oscillation: UnsteadyOscillation | None = None,
    margin_scale: float = 0.3,
    watch_threshold: float = 0.25,
    trigger_threshold: float = 0.1,
    watch_oscillation: float = 0.05,
    trigger_oscillation: float = 0.1,
) -> InstabilityIndicators:
    """Assess stall/rotating-stall/surge proximity from declared boundaries."""

    scale = finite(margin_scale, "margin_scale", positive=True)
    watch = finite(watch_threshold, "watch_threshold", minimum=0.0)
    trigger = finite(trigger_threshold, "trigger_threshold", minimum=0.0)
    if trigger > watch:
        raise AcousticInputError("trigger threshold must not exceed the watch threshold")

    try:
        surge_reference = surge_boundary.flow_at_pressure_ratio(operating.pressure_ratio)
        surge_margin = _lower_margin(surge_reference, operating.mass_flow_kg_s)
    except AcousticInputError:
        surge_reference = operating.mass_flow_kg_s
        surge_margin = 0.0

    stall_margin: float | None = None
    if stall_boundary is not None:
        try:
            stall_reference = stall_boundary.pressure_ratio_at(operating.mass_flow_kg_s)
            stall_margin = (stall_reference - operating.pressure_ratio) / max(
                abs(stall_reference), 1e-9
            )
        except AcousticInputError:
            stall_margin = 0.0

    margins = [surge_margin] if stall_margin is None else [surge_margin, stall_margin]
    minimum_margin = min(margins)
    proximity = min(1.0, max(0.0, minimum_margin / scale))

    mass_flow_fraction: float | None = None
    pressure_fraction: float | None = None
    dominant_hz: float | None = None
    stall_order: float | None = None
    oscillation_max: float | None = None
    if oscillation is not None:
        fraction = oscillation.relative_amplitude()
        if oscillation.signal == "mass-flow":
            mass_flow_fraction = fraction
        else:
            pressure_fraction = fraction
        dominant_hz = oscillation.dominant().frequency_hz
        stall_order = rotating_stall_order(
            oscillation, shaft_frequency_hz=operating.speed_rpm / 60.0
        )
        oscillation_max = fraction

    triggered = proximity <= trigger or (
        oscillation_max is not None and oscillation_max >= trigger_oscillation
    )
    watching = proximity <= watch or (
        oscillation_max is not None and oscillation_max >= watch_oscillation
    )
    if triggered:
        state = STATE_TRIGGERED
        capability: str | None = "transient-cfd"
    elif watching:
        state = STATE_WATCH
        capability = "unsteady-cfd"
    else:
        state = STATE_CLEAR
        capability = None

    checks = {
        "surge_margin_finite": isfinite(surge_margin),
        "proximity_bounded": 0.0 <= proximity <= 1.0,
        "operating_positive": operating.mass_flow_kg_s > 0.0 and operating.pressure_ratio > 0.0,
    }
    inputs = {
        "operating": operating.canonical(),
        "surgeBoundary": surge_boundary.canonical(),
        "stallBoundary": None if stall_boundary is None else stall_boundary.canonical(),
        "oscillation": None if oscillation is None else oscillation.canonical(),
        "marginScale": scale,
    }
    return InstabilityIndicators(
        surge_margin_fraction=surge_margin,
        stall_margin_fraction=stall_margin,
        proximity=proximity,
        state=state,
        rotating_stall_order=stall_order,
        mass_flow_oscillation_fraction=mass_flow_fraction,
        pressure_oscillation_fraction=pressure_fraction,
        dominant_oscillation_hz=dominant_hz,
        required_capability=capability,
        fidelity=AcousticFidelity.TONAL_SCREENING,
        validity=check_validity(checks, f"instability state {state} at proximity {proximity:.3g}"),
        provenance=analytical_provenance(
            "acoustics.instability-indicators",
            inputs,
            assumptions=(
                "margins are normalized distances to declared stability boundaries",
                "oscillation content is measured, not modelled",
            ),
        ),
    )
