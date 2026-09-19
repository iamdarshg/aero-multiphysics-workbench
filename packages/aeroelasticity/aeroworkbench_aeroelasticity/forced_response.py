"""Forced response: harmonic, rotating-order, actuator, and pressure-spectrum.

Generalized harmonic forces are applied to a modal basis through the standard
single-degree-of-freedom transfer function, so the same contract handles a
rotating-order excitation on a turbomachinery row or propeller, actuator/control
excitation on a control surface, and a pressure-spectrum forcing on a wing.
Rotating-order lines reuse the shared rotor-dynamics forcing contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_dynamics import ForcingLine

from .errors import AeroelasticError
from .modes import ModalBasis
from .provenance import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import AeroelasticFidelity, Validity, finite


@dataclass(frozen=True, slots=True)
class HarmonicForce:
    """One generalized harmonic force applied to a named mode."""

    mode_id: str
    frequency_hz: float
    generalized_force_n: float
    phase_deg: float = 0.0
    source: str = "participant"
    order: float | None = None

    def __post_init__(self) -> None:
        if not self.mode_id.strip() or not self.source.strip():
            raise AeroelasticError("harmonic force requires mode_id and source")
        finite(self.frequency_hz, "frequency_hz", minimum=0.0)
        finite(self.generalized_force_n, "generalized_force_n")
        finite(self.phase_deg, "phase_deg")
        if self.order is not None:
            finite(self.order, "order", minimum=0.0)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "frequency_hz": self.frequency_hz,
            "generalized_force_n": self.generalized_force_n,
            "phase_deg": self.phase_deg,
            "source": self.source,
            "order": self.order,
        }


def rotating_order_force(
    line: ForcingLine,
    *,
    mode_id: str,
    speed_rpm: float,
    force_per_amplitude_n: float = 1.0,
) -> HarmonicForce:
    """Resolve a declared rotating-order/excitation line into a modal force."""

    frequency = line.frequency_at(speed_rpm)
    scale = finite(force_per_amplitude_n, "force_per_amplitude_n", minimum=0.0)
    amplitude = (line.amplitude if line.amplitude is not None else 1.0) * scale
    return HarmonicForce(
        mode_id=mode_id,
        frequency_hz=frequency,
        generalized_force_n=amplitude,
        source=line.source,
        order=line.order,
    )


def actuator_force(
    *, mode_id: str, frequency_hz: float, generalized_force_n: float
) -> HarmonicForce:
    """Build a generic actuator/control-surface harmonic excitation."""

    return HarmonicForce(
        mode_id=mode_id,
        frequency_hz=frequency_hz,
        generalized_force_n=generalized_force_n,
        source="actuator",
    )


def pressure_spectrum_forces(
    *,
    mode_id: str,
    mode_shape_norm: float,
    area_m2: float,
    lines: tuple[tuple[float, float], ...],
    source: str = "pressure-spectrum",
) -> tuple[HarmonicForce, ...]:
    """Project pressure-spectrum lines ``(frequency_hz, amplitude_pa)`` onto a mode."""

    shape = finite(mode_shape_norm, "mode_shape_norm", minimum=0.0)
    area = finite(area_m2, "area_m2", positive=True)
    if not lines:
        raise AeroelasticError("pressure spectrum requires at least one line")
    forces = []
    for frequency, amplitude in lines:
        finite(frequency, "spectrum.frequency_hz", minimum=0.0)
        finite(amplitude, "spectrum.amplitude_pa", minimum=0.0)
        forces.append(
            HarmonicForce(
                mode_id=mode_id,
                frequency_hz=frequency,
                generalized_force_n=amplitude * area * shape,
                source=source,
            )
        )
    return tuple(forces)


@dataclass(frozen=True, slots=True)
class ModeResponse:
    """Steady harmonic response of one mode to one excitation line."""

    mode_id: str
    modal_frequency_hz: float
    excitation_frequency_hz: float
    amplitude_m: float
    phase_deg: float
    dynamic_load_n: float
    amplification: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "modal_frequency_hz": self.modal_frequency_hz,
            "excitation_frequency_hz": self.excitation_frequency_hz,
            "amplitude_m": self.amplitude_m,
            "phase_deg": self.phase_deg,
            "dynamic_load_n": self.dynamic_load_n,
            "amplification": self.amplification,
        }


@dataclass(frozen=True, slots=True)
class ForcedResponseResult:
    """Peak forced response across a modal basis and excitation set."""

    basis_id: str
    responses: tuple[ModeResponse, ...]
    peak_amplitude_m: float
    peak_frequency_hz: float
    peak_mode_id: str
    fidelity: AeroelasticFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "amplitude_m": "m",
            "frequency_hz": "Hz",
            "phase_deg": "dimensionless",
            "dynamic_load_n": "N",
            "amplification": "dimensionless",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "basis_id": self.basis_id,
            "peak_amplitude_m": self.peak_amplitude_m,
            "peak_frequency_hz": self.peak_frequency_hz,
            "peak_mode_id": self.peak_mode_id,
            "responses": [response.canonical_payload() for response in self.responses],
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputs_hash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _mode_response(
    *,
    mode_id: str,
    modal_frequency_hz: float,
    damping_ratio: float,
    generalized_mass_kg: float,
    force: HarmonicForce,
) -> ModeResponse:
    omega_n = 2.0 * pi * modal_frequency_hz
    omega = 2.0 * pi * force.frequency_hz
    stiffness = generalized_mass_kg * omega_n * omega_n
    damping = 2.0 * damping_ratio * generalized_mass_kg * omega_n
    real = stiffness - generalized_mass_kg * omega * omega
    imaginary = damping * omega
    magnitude = sqrt(real * real + imaginary * imaginary)
    amplitude = abs(force.generalized_force_n) / magnitude if magnitude > 0.0 else 0.0
    phase = degrees(atan2(imaginary, real))
    dynamic_load = stiffness * amplitude
    static = abs(force.generalized_force_n) / stiffness
    return ModeResponse(
        mode_id=mode_id,
        modal_frequency_hz=modal_frequency_hz,
        excitation_frequency_hz=force.frequency_hz,
        amplitude_m=amplitude,
        phase_deg=phase,
        dynamic_load_n=dynamic_load,
        amplification=(amplitude / static if static > 0.0 else 0.0),
    )


def evaluate_harmonic_response(
    basis: ModalBasis,
    forces: tuple[HarmonicForce, ...],
) -> ForcedResponseResult:
    """Evaluate the steady harmonic response of a modal basis to harmonic forces."""

    if not forces:
        raise AeroelasticError("forced response requires at least one force")
    lookup = {mode.mode_id: mode for mode in basis.modes}
    responses: list[ModeResponse] = []
    for force in forces:
        mode = lookup.get(force.mode_id)
        if mode is None:
            raise AeroelasticError(f"force targets unknown mode:{force.mode_id}")
        responses.append(
            _mode_response(
                mode_id=mode.mode_id,
                modal_frequency_hz=mode.frequency_hz,
                damping_ratio=mode.damping_ratio,
                generalized_mass_kg=mode.generalized_mass_kg,
                force=force,
            )
        )
    peak = max(responses, key=lambda response: response.amplitude_m)
    checks = {
        "all_amplitudes_finite": all(
            response.amplitude_m == response.amplitude_m for response in responses
        ),
        "damping_nonnegative": all(mode.damping_ratio >= 0.0 for mode in basis.modes),
        "frequencies_nonnegative": all(force.frequency_hz >= 0.0 for force in forces),
    }
    inputs = {
        "basis": basis.canonical_payload(),
        "forces": [force.canonical_payload() for force in forces],
    }
    return ForcedResponseResult(
        basis_id=basis.basis_id,
        responses=tuple(responses),
        peak_amplitude_m=peak.amplitude_m,
        peak_frequency_hz=peak.excitation_frequency_hz,
        peak_mode_id=peak.mode_id,
        fidelity=AeroelasticFidelity.HARMONIC,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"peak amplification {peak.amplification:.3g}x",
        ),
        provenance=analytical_provenance(
            "aeroelasticity.forced-response.modal-transfer",
            inputs,
            assumptions=(
                "linear modal single-degree-of-freedom transfer function",
                "steady harmonic response; no transient term",
            ),
        ),
    )


__all__ = [
    "ForcedResponseResult",
    "HarmonicForce",
    "ModeResponse",
    "actuator_force",
    "evaluate_harmonic_response",
    "pressure_spectrum_forces",
    "rotating_order_force",
]
