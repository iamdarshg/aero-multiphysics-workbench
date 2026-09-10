"""Campbell diagram and resonance-escalation policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CampbellPoint:
    rpm: float
    shaft_frequency_hz: float
    blade_passing_hz: float
    stator_passing_hz: float
    modal_frequency_hz: float


@dataclass(frozen=True, slots=True)
class ResonanceDecision:
    state: str
    minimum_margin_hz: float
    source: str
    escalate_to: str | None
    detail: str


def build_campbell(
    *,
    rpm_values: tuple[float, ...],
    blade_count: int,
    stator_count: int,
    modal_frequency_hz: float,
) -> tuple[CampbellPoint, ...]:
    if not rpm_values or blade_count <= 0 or stator_count <= 0 or modal_frequency_hz <= 0:
        raise ValueError("INVALID_CAMPBELL_INPUT")
    if any(rpm < 0 for rpm in rpm_values):
        raise ValueError("INVALID_RPM")
    return tuple(
        CampbellPoint(
            rpm=rpm,
            shaft_frequency_hz=rpm / 60.0,
            blade_passing_hz=rpm * blade_count / 60.0,
            stator_passing_hz=rpm * stator_count / 60.0,
            modal_frequency_hz=modal_frequency_hz,
        )
        for rpm in rpm_values
    )


def assess_resonance(
    points: tuple[CampbellPoint, ...], *, warning_margin_hz: float = 5.0
) -> ResonanceDecision:
    if not points or warning_margin_hz <= 0:
        raise ValueError("INVALID_RESONANCE_INPUT")
    candidates = [
        (abs(point.modal_frequency_hz - point.shaft_frequency_hz), "shaft") for point in points
    ]
    candidates.extend(
        (abs(point.modal_frequency_hz - point.blade_passing_hz), "blade-passing")
        for point in points
    )
    candidates.extend(
        (abs(point.modal_frequency_hz - point.stator_passing_hz), "stator-passing")
        for point in points
    )
    margin, source = min(candidates, key=lambda item: item[0])
    near = margin <= warning_margin_hz
    return ResonanceDecision(
        "warning" if near else "clear",
        margin,
        source,
        "harmonic-transient" if near else None,
        "steady CFD is insufficient near a forcing line"
        if near
        else "forcing lines separated from mode",
    )
