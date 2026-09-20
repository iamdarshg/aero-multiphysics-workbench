"""Feed detected acoustic forcing spectra into the structural-resonance policy.

Resolved rotating-order/acoustic lines are converted into the shared
rotor-dynamics forcing contract, matched against computed modal frequencies with
the generic separation detector, and optionally evaluated through the shared
aeroelastic harmonic-response path. Nothing here invents a mode frequency or an
excitation line.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_aeroelasticity import (
    ForcedResponseResult,
    ModalBasis,
    evaluate_harmonic_response,
    rotating_order_force,
)
from aeroworkbench_dynamics import (
    ForcingAssessment,
    ForcingLine,
    assess_forcing_separation,
)

from .errors import AcousticInputError
from .orders import OrderSpectrum
from .results import finite

__all__ = [
    "StructuralHandoff",
    "couple_forcing_to_structure",
    "evaluate_structural_response",
    "spectrum_to_forcing_lines",
]

STATE_CLEAR = "clear"
STATE_WATCH = "watch"
STATE_TRIGGERED = "triggered"


@dataclass(frozen=True, slots=True)
class StructuralHandoff:
    """Acoustic forcing spectra handed to the structural-resonance policy."""

    spectrum_digest: str
    forcing_lines: tuple[ForcingLine, ...]
    assessment: ForcingAssessment
    required_capability: str | None
    state: str

    def units(self) -> dict[str, str]:
        return {
            "frequency_hz": "Hz",
            "amplitude": "Pa",
            "order": "dimensionless",
            "min_separation_hz": "Hz",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "spectrumDigest": self.spectrum_digest,
            "forcingLines": [line.canonical_payload() for line in self.forcing_lines],
            "assessment": self.assessment.canonical_payload(),
            "requiredCapability": self.required_capability,
            "state": self.state,
        }

    def fidelity_signal(self, *, reference_hz: float) -> dict[str, Any]:
        return self.assessment.fidelity_signal(reference_hz=reference_hz)


def spectrum_to_forcing_lines(
    spectrum: OrderSpectrum,
    *,
    speeds_rpm: Mapping[str, float] | None = None,
    amplitude_by_order: Mapping[str, float] | None = None,
) -> tuple[ForcingLine, ...]:
    """Resolve an order spectrum into shared forcing lines at declared speeds."""

    speeds = dict(spectrum.speed_map()) if speeds_rpm is None else dict(speeds_rpm)
    amplitudes = {} if amplitude_by_order is None else amplitude_by_order
    lines: list[ForcingLine] = []
    for order in spectrum.orders:
        frequency = order.frequency_hz(speeds)
        if frequency <= 0.0:
            continue
        amplitude = amplitudes.get(order.order_id)
        lines.append(
            ForcingLine(
                source="rotating-order-spectrum",
                label=order.order_id,
                frequency_hz=frequency,
                amplitude=amplitude,
                order=order.order,
                speed_dependence="fixed",
                harmonic_family=order.family.value,
            )
        )
    if not lines:
        raise AcousticInputError("order spectrum produced no usable forcing lines")
    return tuple(lines)


def couple_forcing_to_structure(
    spectrum: OrderSpectrum,
    *,
    mode_frequencies_hz: Sequence[float],
    amplitude_by_order: Mapping[str, float] | None = None,
    speeds_rpm: Mapping[str, float] | None = None,
    warning_margin_hz: float = 5.0,
    critical_margin_hz: float = 2.0,
    watch_capability: str = "harmonic-response",
    critical_capability: str = "transient-forced-response",
) -> StructuralHandoff:
    """Match acoustic order lines against modal frequencies and escalate."""

    speeds = dict(spectrum.speed_map()) if speeds_rpm is None else dict(speeds_rpm)
    lines = spectrum_to_forcing_lines(
        spectrum, speeds_rpm=speeds, amplitude_by_order=amplitude_by_order
    )
    reference_speed = max((finite(speed, "speed_rpm") for speed in speeds.values()), default=0.0)
    assessment = assess_forcing_separation(
        lines,
        tuple(mode_frequencies_hz),
        speed_rpm=reference_speed,
        warning_margin_hz=warning_margin_hz,
        critical_margin_hz=critical_margin_hz,
        watch_capability=watch_capability,
        critical_capability=critical_capability,
    )
    return StructuralHandoff(
        spectrum_digest=spectrum.digest,
        forcing_lines=lines,
        assessment=assessment,
        required_capability=assessment.required_capability,
        state=assessment.state,
    )


def evaluate_structural_response(
    basis: ModalBasis,
    lines: Sequence[ForcingLine],
    *,
    speed_rpm: float,
    force_per_amplitude_n: float = 1.0,
) -> ForcedResponseResult:
    """Evaluate the shared aeroelastic harmonic response for resolved forcing lines."""

    if not lines:
        raise AcousticInputError("forced response requires at least one forcing line")
    reference = finite(speed_rpm, "speed_rpm", minimum=0.0)
    forces = []
    for line in lines:
        frequency = line.frequency_at(reference)
        nearest = min(
            basis.modes,
            key=lambda mode: abs(mode.frequency_hz - frequency),
        )
        forces.append(
            rotating_order_force(
                line,
                mode_id=nearest.mode_id,
                speed_rpm=reference,
                force_per_amplitude_n=force_per_amplitude_n,
            )
        )
    return evaluate_harmonic_response(basis, tuple(forces))
