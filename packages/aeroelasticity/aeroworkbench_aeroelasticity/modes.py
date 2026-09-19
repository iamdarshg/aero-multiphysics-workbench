"""Linear/modal coupling: aerodynamic traction to structural modes.

Aerodynamic pressure/traction samples are projected onto a structural modal
basis to produce generalized forces and modal participation. The same contract
serves a turbomachinery row, a propeller/open rotor, a wing, a tail, or a
control surface: nothing here encodes a product-specific geometry. Frequency
and rotating-order matching reuse the shared rotor-dynamics forcing contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

from aeroworkbench_core.resonance import (
    Excitation,
    ResonanceDetector,
    ResonanceReport,
)
from aeroworkbench_core.resonance import (
    Mode as CoreMode,
)
from aeroworkbench_core.types import Provenance
from aeroworkbench_dynamics import (
    ForcingAssessment,
    ForcingLine,
    assess_forcing_separation,
)

from .errors import AeroelasticError
from .provenance import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import AeroelasticFidelity, Validity, finite

Vector3 = tuple[float, float, float]


def _vector3(value: Any, name: str) -> Vector3:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise AeroelasticError(f"{name} must be a 3-vector")
    return (
        finite(value[0], f"{name}[0]"),
        finite(value[1], f"{name}[1]"),
        finite(value[2], f"{name}[2]"),
    )


@dataclass(frozen=True, slots=True)
class PressureSample:
    """One surface sample carrying a traction along a unit normal."""

    node_id: str
    location_m: Vector3
    pressure_pa: float
    area_m2: float
    normal: Vector3

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise AeroelasticError("pressure sample node_id is required")
        object.__setattr__(self, "location_m", _vector3(self.location_m, "location_m"))
        object.__setattr__(self, "normal", _vector3(self.normal, "normal"))
        finite(self.pressure_pa, "pressure_pa")
        finite(self.area_m2, "area_m2", positive=True)
        length = sqrt(sum(component * component for component in self.normal))
        if length <= 0.0:
            raise AeroelasticError("normal must be non-zero")
        object.__setattr__(
            self, "normal", tuple(component / length for component in self.normal)
        )

    def traction_force(self) -> Vector3:
        scale = self.pressure_pa * self.area_m2
        return tuple(scale * component for component in self.normal)  # type: ignore[return-value]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "location_m": list(self.location_m),
            "pressure_pa": self.pressure_pa,
            "area_m2": self.area_m2,
            "normal": list(self.normal),
        }


@dataclass(frozen=True, slots=True)
class PressureField:
    """An ordered set of pressure/traction samples on a structural interface."""

    interface_id: str
    samples: tuple[PressureSample, ...]

    def __post_init__(self) -> None:
        if not self.interface_id.strip():
            raise AeroelasticError("field interface_id is required")
        if not self.samples:
            raise AeroelasticError("field requires at least one sample")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "samples": [sample.canonical_payload() for sample in self.samples],
        }


@dataclass(frozen=True, slots=True)
class StructuralMode:
    """One structural mode, sampled at the field's node ordering."""

    mode_id: str
    frequency_hz: float
    damping_ratio: float
    generalized_mass_kg: float
    shape: tuple[Vector3, ...]

    def __post_init__(self) -> None:
        if not self.mode_id.strip():
            raise AeroelasticError("mode_id is required")
        finite(self.frequency_hz, "frequency_hz", positive=True)
        finite(self.damping_ratio, "damping_ratio", minimum=0.0)
        finite(self.generalized_mass_kg, "generalized_mass_kg", positive=True)
        if not self.shape:
            raise AeroelasticError("mode shape requires at least one sample")
        object.__setattr__(
            self,
            "shape",
            tuple(
                _vector3(entry, f"shape[{index}]") for index, entry in enumerate(self.shape)
            ),
        )

    def to_core_mode(self) -> CoreMode:
        return CoreMode(
            name=self.mode_id,
            frequency_hz=self.frequency_hz,
            damping_ratio=self.damping_ratio,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "generalized_mass_kg": self.generalized_mass_kg,
            "shape": [list(entry) for entry in self.shape],
        }


@dataclass(frozen=True, slots=True)
class ModalBasis:
    """An ordered structural modal basis with its retained frequency band."""

    basis_id: str
    modes: tuple[StructuralMode, ...]

    def __post_init__(self) -> None:
        if not self.basis_id.strip():
            raise AeroelasticError("basis_id is required")
        if not self.modes:
            raise AeroelasticError("modal basis requires at least one mode")
        identifiers = [mode.mode_id for mode in self.modes]
        if len(set(identifiers)) != len(identifiers):
            raise AeroelasticError("mode_id values must be unique")

    def frequencies_hz(self) -> tuple[float, ...]:
        return tuple(mode.frequency_hz for mode in self.modes)

    def damping_ratios(self) -> tuple[float, ...]:
        return tuple(mode.damping_ratio for mode in self.modes)

    def generalized_masses_kg(self) -> tuple[float, ...]:
        return tuple(mode.generalized_mass_kg for mode in self.modes)

    def core_modes(self) -> tuple[CoreMode, ...]:
        return tuple(mode.to_core_mode() for mode in self.modes)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "basis_id": self.basis_id,
            "modes": [mode.canonical_payload() for mode in self.modes],
        }


@dataclass(frozen=True, slots=True)
class GeneralizedForce:
    """One modal generalized force and its participation fraction."""

    mode_id: str
    frequency_hz: float
    damping_ratio: float
    generalized_mass_kg: float
    force_n: float
    participation: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "generalized_mass_kg": self.generalized_mass_kg,
            "force_n": self.force_n,
            "participation": self.participation,
        }


@dataclass(frozen=True, slots=True)
class ModalCouplingResult:
    """Projected generalized forces for an aerodynamic traction field."""

    interface_id: str
    basis_id: str
    generalized_forces: tuple[GeneralizedForce, ...]
    total_force_n: float
    resultant_n: Vector3
    fidelity: AeroelasticFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "force_n": "N",
            "participation": "dimensionless",
            "frequency_hz": "Hz",
            "generalized_mass_kg": "kg",
        }

    @property
    def dominant_mode_id(self) -> str:
        return max(self.generalized_forces, key=lambda item: abs(item.force_n)).mode_id

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "basis_id": self.basis_id,
            "total_force_n": self.total_force_n,
            "resultant_n": list(self.resultant_n),
            "dominant_mode_id": self.dominant_mode_id,
            "generalized_forces": [
                force.canonical_payload() for force in self.generalized_forces
            ],
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputs_hash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def map_pressure_to_modes(
    field: PressureField,
    basis: ModalBasis,
) -> ModalCouplingResult:
    """Project a pressure/traction field onto a modal basis.

    Generalized force ``Q_i = sum_s phi_i(s) . (p_s A_s n_s)`` so the same
    operation applies to a row, a rotor, or a lifting surface.
    """

    sample_count = len(field.samples)
    for mode in basis.modes:
        if len(mode.shape) != sample_count:
            raise AeroelasticError(
                f"mode {mode.mode_id} has {len(mode.shape)} samples, field has {sample_count}"
            )
    tractions = [sample.traction_force() for sample in field.samples]
    total_force_n = sum(
        sqrt(sum(component * component for component in traction))
        for traction in tractions
    )
    raw = tuple(
        sum(
            mode.shape[index][axis] * tractions[index][axis]
            for index in range(sample_count)
            for axis in range(3)
        )
        for mode in basis.modes
    )
    total = sum(abs(value) for value in raw)
    forces = tuple(
        GeneralizedForce(
            mode_id=mode.mode_id,
            frequency_hz=mode.frequency_hz,
            damping_ratio=mode.damping_ratio,
            generalized_mass_kg=mode.generalized_mass_kg,
            force_n=value,
            participation=(abs(value) / total if total > 0.0 else 0.0),
        )
        for mode, value in zip(basis.modes, raw, strict=True)
    )
    resultant: Vector3 = (
        sum(force[0] for force in tractions),
        sum(force[1] for force in tractions),
        sum(force[2] for force in tractions),
    )
    checks = {
        "samples_positive_area": all(sample.area_m2 > 0.0 for sample in field.samples),
        "participation_normalized": abs(sum(f.participation for f in forces) - 1.0) < 1e-9
        or total == 0.0,
        "frequencies_positive": all(mode.frequency_hz > 0.0 for mode in basis.modes),
    }
    inputs = {"field": field.canonical_payload(), "basis": basis.canonical_payload()}
    return ModalCouplingResult(
        interface_id=field.interface_id,
        basis_id=basis.basis_id,
        generalized_forces=forces,
        total_force_n=total_force_n,
        resultant_n=resultant,
        fidelity=AeroelasticFidelity.REDUCED,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"projected {len(field.samples)} samples onto {len(basis.modes)} modes",
        ),
        provenance=analytical_provenance(
            "aeroelasticity.modal.pressure-projection",
            inputs,
            assumptions=(
                "linear modal superposition; small displacement; sampled traction",
            ),
        ),
    )


def match_excitation_to_modes(
    basis: ModalBasis,
    *,
    force_lines: tuple[ForcingLine, ...],
    speed_rpm: float,
    warning_margin_hz: float = 5.0,
    critical_margin_hz: float = 2.0,
) -> ForcingAssessment:
    """Match declared frequency/order excitation lines against modal frequencies."""

    return assess_forcing_separation(
        force_lines,
        basis.frequencies_hz(),
        speed_rpm=speed_rpm,
        warning_margin_hz=warning_margin_hz,
        critical_margin_hz=critical_margin_hz,
    )


def assess_modal_resonance(
    basis: ModalBasis,
    *,
    excitations: tuple[Excitation, ...],
    current_fidelity: AeroelasticFidelity,
) -> ResonanceReport:
    """Reuse the shared frequency-separation detector for a modal basis."""

    report = ResonanceDetector().evaluate(
        excitations=list(excitations),
        modes=list(basis.core_modes()),
        current_fidelity=current_fidelity.core_level(),
    )
    return report


__all__ = [
    "GeneralizedForce",
    "ModalBasis",
    "ModalCouplingResult",
    "PressureField",
    "PressureSample",
    "StructuralMode",
    "map_pressure_to_modes",
    "match_excitation_to_modes",
    "assess_modal_resonance",
]
