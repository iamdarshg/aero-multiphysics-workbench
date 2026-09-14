"""Resonance inside the physics loop, generalized to arbitrary participants.

Forcing spectra are accepted from arbitrary participants (any unsteady
source labels them; nothing hard-codes a particular machine's forcing).
Modal and rotordynamic spectra are accepted from arbitrary structural or
dynamic participants. When proximity crosses policy thresholds, the trigger
names the higher-fidelity implementations to activate (harmonic response,
transient structural/CFD, AMI, FSI, detailed EM, or any participant-declared
names) filtered by what is actually available, and exposes the required
capability for the fidelity planner.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ForcingSpectrum:
    """One forcing spectrum contributed by an arbitrary participant."""

    source: str
    label: str
    frequencies_hz: tuple[float, ...]
    amplitudes: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.label.strip():
            raise ValueError("FORCING_SPECTRUM_NEEDS_SOURCE_AND_LABEL")
        if not self.frequencies_hz or len(self.frequencies_hz) != len(self.amplitudes):
            raise ValueError("FORCING_SPECTRUM_NEEDS_MATCHED_LINES")
        for value in (*self.frequencies_hz, *self.amplitudes):
            if not isfinite(value) or value < 0:
                raise ValueError("FORCING_SPECTRUM_MUST_BE_FINITE_NONNEGATIVE")


@dataclass(frozen=True, slots=True)
class ModalSpectrum:
    """One modal/rotordynamic spectrum from an arbitrary dynamic participant."""

    source: str
    kind: str
    natural_frequencies_hz: tuple[float, ...]
    damping_ratios: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.kind.strip():
            raise ValueError("MODAL_SPECTRUM_NEEDS_SOURCE_AND_KIND")
        if not self.natural_frequencies_hz or len(self.natural_frequencies_hz) != len(
            self.damping_ratios
        ):
            raise ValueError("MODAL_SPECTRUM_NEEDS_MATCHED_MODES")
        for value in self.natural_frequencies_hz:
            if not isfinite(value) or value <= 0:
                raise ValueError("MODAL_FREQUENCIES_MUST_BE_POSITIVE")
        for value in self.damping_ratios:
            if not isfinite(value) or value < 0:
                raise ValueError("DAMPING_RATIOS_MUST_BE_NONNEGATIVE")


@dataclass(frozen=True, slots=True)
class ProximityReport:
    min_separation_hz: float
    worst_forcing: tuple[str, float]
    worst_mode: tuple[str, float]
    pairs: tuple[tuple[str, float, str, float, float], ...]


def separation(
    forcing: tuple[ForcingSpectrum, ...], modal: tuple[ModalSpectrum, ...]
) -> ProximityReport:
    """Minimum absolute separation between any forcing line and any mode."""
    if not forcing or not modal:
        raise ValueError("PROXIMITY_NEEDS_FORCING_AND_MODAL_SPECTRA")
    pairs: list[tuple[str, float, str, float, float]] = []
    for force in forcing:
        for frequency, _ in zip(force.frequencies_hz, force.amplitudes, strict=True):
            for spectrum in modal:
                for mode in spectrum.natural_frequencies_hz:
                    pairs.append(
                        (force.source, frequency, spectrum.source, mode, abs(mode - frequency))
                    )
    worst = min(pairs, key=lambda item: item[4])
    ordered = tuple(sorted(pairs, key=lambda item: item[4]))
    return ProximityReport(
        worst[4], (worst[0], worst[1]), (worst[2], worst[3]), ordered
    )


@dataclass(frozen=True, slots=True)
class ResonancePolicy:
    warning_margin_hz: float
    critical_margin_hz: float
    watch_activate: tuple[str, ...]
    critical_activate: tuple[str, ...]
    available: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isfinite(self.warning_margin_hz)
            or not isfinite(self.critical_margin_hz)
            or self.warning_margin_hz <= 0
            or self.critical_margin_hz <= 0
            or self.critical_margin_hz > self.warning_margin_hz
        ):
            raise ValueError("INVALID_RESONANCE_MARGINS")


@dataclass(frozen=True, slots=True)
class ResonanceTrigger:
    state: str  # "clear" | "watch" | "triggered"
    min_separation_hz: float
    activate: tuple[str, ...]
    required_capability: str | None
    detail: str


_CAPABILITY_BY_IMPLEMENTATION = (
    ("fsi", "field-coupled"),
    ("ami", "transient"),
    ("transient", "transient"),
    ("harmonic", "harmonic"),
    ("detailed", "transient"),
    ("coupled", "field-coupled"),
)


def _capability_for(name: str) -> str:
    lowered = name.lower()
    for marker, capability in _CAPABILITY_BY_IMPLEMENTATION:
        if marker in lowered:
            return capability
    return "transient"


def check_resonance(
    forcing: tuple[ForcingSpectrum, ...],
    modal: tuple[ModalSpectrum, ...],
    policy: ResonancePolicy,
) -> ResonanceTrigger:
    """Assess proximity and name the higher-fidelity implementations to run."""
    report = separation(forcing, modal)
    margin = report.min_separation_hz
    if margin <= policy.critical_margin_hz:
        wanted = policy.critical_activate
        state = "triggered"
    elif margin <= policy.warning_margin_hz:
        wanted = policy.watch_activate
        state = "watch" if wanted else "clear"
        if not wanted:
            return ResonanceTrigger(
                "clear", margin, (), None,
                f"separation {margin:.3g} Hz inside watch band but nothing to activate",
            )
    else:
        return ResonanceTrigger(
            "clear", margin, (), None,
            f"forcing lines separated from modes by {margin:.3g} Hz",
        )
    activate = tuple(name for name in wanted if name in policy.available)
    capability = _capability_for(activate[0]) if activate else None
    return ResonanceTrigger(
        state if activate else "watch", margin, activate, capability,
        f"separation {margin:.3g} Hz crosses the {state} margin; "
        f"activating {', '.join(activate) if activate else 'nothing available'}",
    )
