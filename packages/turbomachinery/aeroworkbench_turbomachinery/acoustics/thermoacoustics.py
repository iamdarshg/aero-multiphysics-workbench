"""Thermoacoustics for heat-addition systems: heat-release/pressure coupling.

Thermoacoustics is an optional discipline: it activates only when the
architecture declares heat addition, and it consumes the reduced-order
heat-release output of the TURBO 08 combustion participant. Acoustic modes are
estimated from declared cavity length and sound speed, and a Rayleigh-type index
measures phase-aligned heat release as a growth indicator. Near-margin or
unstable conditions request a transient reacting analysis.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import cos
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance

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
    spectrum_lines,
)

__all__ = [
    "AcousticModeEstimate",
    "HeatReleaseSpectrum",
    "ThermoacousticInput",
    "ThermoacousticResult",
    "assess_thermoacoustics",
    "estimate_acoustic_modes",
    "rayleigh_index",
]

STATE_INACTIVE = "inactive"
STATE_STABLE = "stable"
STATE_NEAR_MARGIN = "near-margin"
STATE_UNSTABLE = "unstable"

_BOUNDARIES = ("quarter-wave", "half-wave")


@dataclass(frozen=True, slots=True)
class AcousticModeEstimate:
    """One estimated acoustic mode of a cavity."""

    mode_number: int
    frequency_hz: float
    kind: str = "longitudinal"

    def __post_init__(self) -> None:
        if self.mode_number < 1:
            raise AcousticInputError("acoustic mode number must be >= 1")
        finite(self.frequency_hz, "frequency_hz", positive=True)

    def canonical(self) -> dict[str, Any]:
        return {
            "modeNumber": self.mode_number,
            "frequencyHz": self.frequency_hz,
            "kind": self.kind,
        }


def estimate_acoustic_modes(
    *,
    cavity_length_m: float,
    speed_of_sound_m_s: float,
    mode_numbers: Sequence[int] = (1, 2, 3),
    boundary: str = "quarter-wave",
) -> tuple[AcousticModeEstimate, ...]:
    """Estimate longitudinal acoustic modes for a declared cavity and boundary."""

    length = finite(cavity_length_m, "cavity_length_m", positive=True)
    sound_speed = finite(speed_of_sound_m_s, "speed_of_sound_m_s", positive=True)
    if boundary not in _BOUNDARIES:
        raise AcousticInputError(f"UNKNOWN_ACOUSTIC_BOUNDARY:{boundary}")
    if not mode_numbers:
        raise AcousticInputError("at least one acoustic mode number is required")
    modes: list[AcousticModeEstimate] = []
    for number in mode_numbers:
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise AcousticInputError("acoustic mode numbers must be positive integers")
        if boundary == "quarter-wave":
            frequency = (2 * number - 1) * sound_speed / (4.0 * length)
        else:
            frequency = number * sound_speed / (2.0 * length)
        modes.append(AcousticModeEstimate(number, frequency))
    return tuple(modes)


def _nearest_line(
    lines: Sequence[tuple[float, float]], frequency: float, tolerance: float
) -> float | None:
    best: tuple[float, float] | None = None
    best_distance = float("inf")
    for line_frequency, amplitude in lines:
        distance = abs(line_frequency - frequency)
        if distance < best_distance:
            best_distance = distance
            best = (line_frequency, amplitude)
    if best is None:
        return None
    if frequency <= 0.0 or best_distance / frequency > tolerance:
        return None
    return best[1]


def rayleigh_index(
    pressure_lines: Sequence[tuple[float, float]],
    heat_release_lines: Sequence[tuple[float, float]],
    *,
    mode_frequencies_hz: Sequence[float],
    phases_rad: Mapping[float, float],
    tolerance: float = 0.05,
) -> float:
    """Normalized Rayleigh growth index in ``[-1, 1]`` from aligned mode content."""

    if not mode_frequencies_hz:
        raise AcousticInputError("thermoacoustics needs at least one acoustic mode")
    driving = 0.0
    capacity = 0.0
    aligned = 0
    for frequency in mode_frequencies_hz:
        mode_frequency = finite(frequency, "mode_frequency_hz", positive=True)
        pressure = _nearest_line(pressure_lines, mode_frequency, tolerance)
        heat = _nearest_line(heat_release_lines, mode_frequency, tolerance)
        if pressure is None or heat is None:
            continue
        phase = phases_rad.get(mode_frequency)
        if phase is None:
            continue
        angle = finite(phase, "phase_rad")
        driving += pressure * heat * cos(angle)
        capacity += pressure * heat
        aligned += 1
    if aligned == 0 or capacity <= 0.0:
        raise AcousticInputError("NO_MODE_ALIGNED_THERMOACOUSTIC_LINES")
    return max(-1.0, min(1.0, driving / capacity))


@dataclass(frozen=True, slots=True)
class HeatReleaseSpectrum:
    """A fluctuating heat-release spectrum, optionally sourced from TURBO 08."""

    lines: tuple[tuple[float, float], ...]
    mean_heat_release_w: float
    combustor_model: str = "reduced-combustor-network"
    combustor_inputs_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", spectrum_lines(self.lines, "lines"))
        finite(self.mean_heat_release_w, "mean_heat_release_w", positive=True)
        if not self.combustor_model.strip():
            raise AcousticInputError("combustor_model is required")
        if self.combustor_inputs_hash is not None and len(self.combustor_inputs_hash) != 64:
            raise AcousticInputError("combustor_inputs_hash must be a sha-256 hex digest")

    def canonical(self) -> dict[str, Any]:
        return {
            "lines": [[frequency, amplitude] for frequency, amplitude in self.lines],
            "meanHeatReleaseW": self.mean_heat_release_w,
            "combustorModel": self.combustor_model,
            "combustorInputsHash": self.combustor_inputs_hash,
        }


@dataclass(frozen=True, slots=True)
class ThermoacousticInput:
    """Declared optional thermoacoustic inputs for one architecture."""

    heat_addition: bool
    acoustic_modes: tuple[AcousticModeEstimate, ...] = ()
    pressure_spectrum: tuple[tuple[float, float], ...] = ()
    heat_release: HeatReleaseSpectrum | None = None
    phases_rad: tuple[tuple[float, float], ...] = ()

    def phase_map(self) -> dict[float, float]:
        return {float(key): float(value) for key, value in self.phases_rad}


@dataclass(frozen=True, slots=True)
class ThermoacousticResult:
    """Thermoacoustic screening outcome; inactive without heat addition."""

    active: bool
    state: str
    rayleigh_index: float | None
    mean_heat_release_w: float | None
    acoustic_modes: tuple[AcousticModeEstimate, ...]
    pressure_lines: tuple[tuple[float, float], ...]
    heat_release_lines: tuple[tuple[float, float], ...]
    required_capability: str | None
    fidelity: AcousticFidelity
    validity: AcousticValidity
    provenance: Provenance
    software: AcousticSoftware = DEFAULT_ACOUSTIC_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "frequency_hz": "Hz",
            "pressure_pa": "Pa",
            "heat_release_w": "W",
            "rayleigh_index": "dimensionless",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "state": self.state,
            "rayleighIndex": self.rayleigh_index,
            "meanHeatReleaseW": self.mean_heat_release_w,
            "acousticModes": [mode.canonical() for mode in self.acoustic_modes],
            "pressureLines": [
                [frequency, amplitude] for frequency, amplitude in self.pressure_lines
            ],
            "heatReleaseLines": [
                [frequency, amplitude] for frequency, amplitude in self.heat_release_lines
            ],
            "requiredCapability": self.required_capability,
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())

    def promotion_signal(self) -> dict[str, Any]:
        return {
            "model_disagreement": abs(self.rayleigh_index) if self.rayleigh_index else 0.0,
            "required_capability": self.required_capability,
        }


def assess_thermoacoustics(
    inputs: ThermoacousticInput,
    *,
    growth_threshold: float = 0.2,
) -> ThermoacousticResult:
    """Assess thermoacoustic stability; inert unless heat addition is declared."""

    threshold = finite(growth_threshold, "growth_threshold", minimum=0.0)
    pressure_lines = spectrum_lines(inputs.pressure_spectrum, "pressure_spectrum")
    modes = tuple(inputs.acoustic_modes)
    heat_lines = inputs.heat_release.lines if inputs.heat_release is not None else ()
    base_inputs: dict[str, Any] = {
        "heatAddition": inputs.heat_addition,
        "acousticModes": [mode.canonical() for mode in modes],
        "pressureSpectrum": [[f, a] for f, a in pressure_lines],
        "heatRelease": None if inputs.heat_release is None else inputs.heat_release.canonical(),
        "phasesRad": [[f, p] for f, p in inputs.phases_rad],
        "growthThreshold": threshold,
    }

    if not inputs.heat_addition:
        return ThermoacousticResult(
            active=False,
            state=STATE_INACTIVE,
            rayleigh_index=None,
            mean_heat_release_w=(
                None if inputs.heat_release is None else inputs.heat_release.mean_heat_release_w
            ),
            acoustic_modes=modes,
            pressure_lines=pressure_lines,
            heat_release_lines=heat_lines,
            required_capability=None,
            fidelity=AcousticFidelity.THERMOACOUSTIC_SCREENING,
            validity=check_validity(
                {"heat_addition_absent": True},
                "no heat-addition node; thermoacoustics is inactive",
            ),
            provenance=analytical_provenance(
                "acoustics.thermoacoustics.inactive",
                base_inputs,
                assumptions=("thermoacoustics activates only for heat-addition systems",),
                fidelity=FidelityLevel.MRF,
            ),
        )

    if inputs.heat_release is None:
        raise AcousticInputError("heat-addition thermoacoustics requires a heat-release spectrum")
    if not modes:
        raise AcousticInputError("heat-addition thermoacoustics requires acoustic modes")
    index = rayleigh_index(
        pressure_lines,
        heat_lines,
        mode_frequencies_hz=tuple(mode.frequency_hz for mode in modes),
        phases_rad=inputs.phase_map(),
    )
    if index >= threshold:
        state = STATE_UNSTABLE
        capability: str | None = "reacting-unsteady-cfd"
    elif index > 0.0:
        state = STATE_NEAR_MARGIN
        capability = "reacting-unsteady-cfd"
    else:
        state = STATE_STABLE
        capability = None

    checks = {
        "heat_addition_present": True,
        "rayleigh_bounded": -1.0 <= index <= 1.0,
        "heat_release_positive": inputs.heat_release.mean_heat_release_w > 0.0,
    }
    return ThermoacousticResult(
        active=True,
        state=state,
        rayleigh_index=index,
        mean_heat_release_w=inputs.heat_release.mean_heat_release_w,
        acoustic_modes=modes,
        pressure_lines=pressure_lines,
        heat_release_lines=heat_lines,
        required_capability=capability,
        fidelity=AcousticFidelity.THERMOACOUSTIC_SCREENING,
        validity=check_validity(
            checks, f"thermoacoustic state {state} at Rayleigh index {index:.4g}"
        ),
        provenance=analytical_provenance(
            "acoustics.thermoacoustics.rayleigh",
            base_inputs,
            assumptions=(
                "Rayleigh index uses phase-aligned mode content only",
                "mode frequencies are estimated from a declared cavity and sound speed",
            ),
            fidelity=FidelityLevel.MRF,
        ),
    )
