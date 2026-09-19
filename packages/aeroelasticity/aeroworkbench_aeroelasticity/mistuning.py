"""Mistuning and cyclic structures.

A generic cyclic structure is a ring of identical sectors coupled to their
neighbours, with an optional per-sector mistuning distribution. The same seam
serves a blade/disk, a repeated airframe panel family, or any rotationally
periodic assembly. Analysis assembles the full annulus, extracts its natural
frequencies and mode shapes, and reports mode localization; a sector-to-full
mapping exposes how sector degrees of freedom embed in the full model.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .errors import AeroelasticError
from .linalg import FloatMatrix, symmetric_eigenpairs
from .provenance import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import AeroelasticFidelity, Validity, finite

MAX_SECTORS = 64


@dataclass(frozen=True, slots=True)
class CyclicStructureSpec:
    """A rotationally periodic structure with optional per-sector mistuning."""

    structure_id: str
    sector_count: int
    sector_mass_kg: float
    sector_stiffness_n_m: float
    inter_sector_coupling_n_m: float
    mistuning: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.structure_id.strip():
            raise AeroelasticError("structure_id is required")
        if isinstance(self.sector_count, bool) or not isinstance(self.sector_count, int):
            raise AeroelasticError("sector_count must be an integer")
        if not 2 <= self.sector_count <= MAX_SECTORS:
            raise AeroelasticError(f"sector_count must be within 2..{MAX_SECTORS}")
        finite(self.sector_mass_kg, "sector_mass_kg", positive=True)
        finite(self.sector_stiffness_n_m, "sector_stiffness_n_m", positive=True)
        finite(self.inter_sector_coupling_n_m, "inter_sector_coupling_n_m", minimum=0.0)
        if self.mistuning:
            if len(self.mistuning) != self.sector_count:
                raise AeroelasticError("mistuning length must equal sector_count")
            if any(value != value for value in self.mistuning):
                raise AeroelasticError("mistuning entries must not be NaN")
            for index, value in enumerate(self.mistuning):
                finite(value, f"mistuning[{index}]", minimum=-0.99)

    @property
    def mistuned(self) -> bool:
        return any(abs(value) > 1e-12 for value in self.mistuning) if self.mistuning else False

    def sector_stiffnesses_n_m(self) -> tuple[float, ...]:
        detuning = self.mistuning or (0.0,) * self.sector_count
        return tuple(
            self.sector_stiffness_n_m * (1.0 + value) for value in detuning
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "structure_id": self.structure_id,
            "sector_count": self.sector_count,
            "sector_mass_kg": self.sector_mass_kg,
            "sector_stiffness_n_m": self.sector_stiffness_n_m,
            "inter_sector_coupling_n_m": self.inter_sector_coupling_n_m,
            "mistuning": list(self.mistuning),
        }


def assemble_full_annulus(
    spec: CyclicStructureSpec,
) -> tuple[FloatMatrix, FloatMatrix]:
    """Return the full-annulus ``(mass, stiffness)`` matrices for the ring."""

    count = spec.sector_count
    stiffnesses = spec.sector_stiffnesses_n_m()
    coupling = spec.inter_sector_coupling_n_m
    stiffness = tuple(
        tuple(
            stiffnesses[i] + 2.0 * coupling
            if i == j
            else (-coupling if (j - i) % count in (1, count - 1) else 0.0)
            for j in range(count)
        )
        for i in range(count)
    )
    mass = tuple(
        tuple(spec.sector_mass_kg if i == j else 0.0 for j in range(count))
        for i in range(count)
    )
    return mass, stiffness


def sector_to_full_mapping(
    *, sector_count: int, dof_per_sector: int
) -> tuple[tuple[int, int], ...]:
    """Map each full-annulus degree of freedom to ``(sector, local_dof)``."""

    if isinstance(sector_count, bool) or not isinstance(sector_count, int):
        raise AeroelasticError("sector_count must be an integer")
    if isinstance(dof_per_sector, bool) or not isinstance(dof_per_sector, int):
        raise AeroelasticError("dof_per_sector must be an integer")
    if sector_count < 1 or not 1 <= dof_per_sector <= 32:
        raise AeroelasticError("invalid sector mapping request")
    return tuple(
        (index // dof_per_sector, index % dof_per_sector)
        for index in range(sector_count * dof_per_sector)
    )


def localization_factor(shape: tuple[float, ...]) -> float:
    """Peak modal participation: ``max_i phi_i^2`` for a unit-norm shape."""

    if not shape:
        raise AeroelasticError("mode shape must be non-empty")
    norm_squared = sum(value * value for value in shape)
    if norm_squared <= 0.0:
        raise AeroelasticError("mode shape must be non-zero")
    return max(value * value for value in shape) / norm_squared


def inverse_participation_ratio(shape: tuple[float, ...]) -> float:
    """IPR ``(sum phi^2)^2 / sum phi^4``; equals N for a fully extended mode."""

    if not shape:
        raise AeroelasticError("mode shape must be non-empty")
    norm_squared = sum(value * value for value in shape)
    quartic = sum(value**4 for value in shape)
    if quartic <= 0.0:
        raise AeroelasticError("mode shape must be non-zero")
    return norm_squared * norm_squared / quartic


@dataclass(frozen=True, slots=True)
class CyclicMode:
    """One natural mode of the full annulus."""

    index: int
    frequency_hz: float
    shape: tuple[float, ...]
    localization_factor: float
    inverse_participation_ratio: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "frequency_hz": self.frequency_hz,
            "shape": list(self.shape),
            "localization_factor": self.localization_factor,
            "inverse_participation_ratio": self.inverse_participation_ratio,
        }


@dataclass(frozen=True, slots=True)
class MistuningResult:
    """Natural frequencies and mode localization of a cyclic structure."""

    structure_id: str
    modes: tuple[CyclicMode, ...]
    mistuned: bool
    max_localization_factor: float
    frequency_split_hz: float
    fidelity: AeroelasticFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "frequency_hz": "Hz",
            "localization_factor": "dimensionless",
            "inverse_participation_ratio": "dimensionless",
        }

    def frequencies_hz(self) -> tuple[float, ...]:
        return tuple(mode.frequency_hz for mode in self.modes)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "structure_id": self.structure_id,
            "mistuned": self.mistuned,
            "max_localization_factor": self.max_localization_factor,
            "frequency_split_hz": self.frequency_split_hz,
            "modes": [mode.canonical_payload() for mode in self.modes],
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputs_hash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def analyze_cyclic_structure(spec: CyclicStructureSpec) -> MistuningResult:
    """Assemble the full annulus, solve its eigenproblem, and quantify localization."""

    mass, stiffness = assemble_full_annulus(spec)
    count = spec.sector_count
    inverse_root_mass = 1.0 / sqrt(spec.sector_mass_kg)
    scaled = tuple(
        tuple(
            stiffness[i][j] * inverse_root_mass * inverse_root_mass
            for j in range(count)
        )
        for i in range(count)
    )
    eigenvalues, vectors = symmetric_eigenpairs(scaled)
    modes: list[CyclicMode] = []
    for index, (eigenvalue, vector) in enumerate(zip(eigenvalues, vectors, strict=True)):
        omega = sqrt(max(eigenvalue, 0.0))
        modes.append(
            CyclicMode(
                index=index,
                frequency_hz=omega / (2.0 * pi),
                shape=vector,
                localization_factor=localization_factor(vector),
                inverse_participation_ratio=inverse_participation_ratio(vector),
            )
        )
    frequencies = [mode.frequency_hz for mode in modes]
    split = max(frequencies) - min(frequencies) if frequencies else 0.0
    checks = {
        "eigenvalues_nonnegative": all(value >= -1e-9 for value in eigenvalues),
        "mass_positive": spec.sector_mass_kg > 0.0,
        "sector_count_consistent": count == spec.sector_count,
    }
    return MistuningResult(
        structure_id=spec.structure_id,
        modes=tuple(modes),
        mistuned=spec.mistuned,
        max_localization_factor=max(
            (mode.localization_factor for mode in modes), default=0.0
        ),
        frequency_split_hz=split,
        fidelity=AeroelasticFidelity.REDUCED,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"{count}-sector annulus; mistuned={spec.mistuned}",
        ),
        provenance=analytical_provenance(
            "aeroelasticity.mistuning.cyclic-annulus-eigenproblem",
            {"structure": spec.canonical_payload()},
            assumptions=(
                "nearest-neighbour cyclic coupling; uniform sector mass",
                "linear eigenvalue problem; no aerodynamic coupling",
            ),
        ),
    )


__all__ = [
    "CyclicMode",
    "CyclicStructureSpec",
    "MistuningResult",
    "analyze_cyclic_structure",
    "assemble_full_annulus",
    "inverse_participation_ratio",
    "localization_factor",
    "sector_to_full_mapping",
]
