"""Structural stiffness, mass, and deflected-shape seam for closing the loop.

The sized structure is folded into equivalent beam stiffnesses (bending ``EI``
and torsion ``GJ``), an equivalent areal mass, a first cantilever bending
frequency, and a tip deflection. The :meth:`StiffnessSeam.to_aeroelastic_inputs`
mapping emits exactly the keys the composites workstream publishes, so a
generated structure can drive an aeroelastic loop without a translation layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .checks import effective_second_moment_m4
from .contracts import content_digest
from .errors import StructuralContractError
from .members import StructuralMember

__all__ = [
    "StiffnessSeam",
    "build_stiffness_seam",
    "cantilever_bending_frequency_hz",
]

_FIRST_MODE_FACTOR = 1.875104068711961


def cantilever_bending_frequency_hz(
    bending_stiffness_n_m2: float, mass_per_length_kg_m: float, length_m: float
) -> float:
    """First cantilever bending frequency from equivalent ``EI`` and mass/length."""

    if bending_stiffness_n_m2 <= 0.0 or mass_per_length_kg_m <= 0.0 or length_m <= 0.0:
        raise StructuralContractError("FREQUENCY_INPUTS_MUST_BE_POSITIVE")
    return (
        _FIRST_MODE_FACTOR**2
        / (2.0 * math.pi)
        * math.sqrt(bending_stiffness_n_m2 / (mass_per_length_kg_m * length_m**4))
    )


@dataclass(frozen=True, slots=True)
class StiffnessSeam:
    """Equivalent beam stiffness and inertia of a sized structure."""

    architecture_id: str
    component_id: str
    frame: str
    span_m: float
    bending_stiffness_n_m2: float
    torsional_stiffness_n_m2: float
    total_mass_kg: float
    areal_mass_kg_m2: float
    first_bending_frequency_hz: float
    tip_deflection_m: float

    def to_aeroelastic_inputs(self) -> dict[str, float]:
        return {
            "frequency_hz": self.first_bending_frequency_hz,
            "areal_mass_kg_m2": self.areal_mass_kg_m2,
            "bending_stiffness_d11_n_m": self.bending_stiffness_n_m2 / max(self.span_m, 1.0e-9),
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "architectureId": self.architecture_id,
            "componentId": self.component_id,
            "frame": self.frame,
            "spanM": self.span_m,
            "bendingStiffnessNm2": self.bending_stiffness_n_m2,
            "torsionalStiffnessNm2": self.torsional_stiffness_n_m2,
            "totalMassKg": self.total_mass_kg,
            "arealMassKgM2": self.areal_mass_kg_m2,
            "firstBendingFrequencyHz": self.first_bending_frequency_hz,
            "tipDeflectionM": self.tip_deflection_m,
        }

    def as_dict(self) -> dict[str, Any]:
        return self.canonical_payload()

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def build_stiffness_seam(
    members: tuple[StructuralMember, ...],
    *,
    architecture_id: str,
    component_id: str,
    frame: str,
    span_m: float,
    reference_area_m2: float,
    root_bending_n_m: float,
) -> StiffnessSeam:
    """Fold sized members into equivalent beam stiffnesses and inertia."""

    if span_m <= 0.0 or reference_area_m2 <= 0.0:
        raise StructuralContractError("STIFFNESS_REFERENCE_MUST_BE_POSITIVE")
    bending = 0.0
    torsion = 0.0
    total_mass = 0.0
    for member in members:
        properties = member.section.properties()
        bending += member.material.youngs_modulus_pa() * effective_second_moment_m4(member)
        torsion += member.material.shear_modulus_pa() * properties.torsion_constant_m4
        total_mass += member.mass_kg()
    if bending <= 0.0:
        raise StructuralContractError("STRUCTURE_HAS_NO_BENDING_STIFFNESS")
    mass_per_length = total_mass / span_m
    frequency = cantilever_bending_frequency_hz(bending, mass_per_length, span_m)
    tip_deflection = root_bending_n_m * span_m**2 / (2.0 * bending)
    return StiffnessSeam(
        architecture_id=architecture_id,
        component_id=component_id,
        frame=frame,
        span_m=span_m,
        bending_stiffness_n_m2=bending,
        torsional_stiffness_n_m2=torsion,
        total_mass_kg=total_mass,
        areal_mass_kg_m2=total_mass / reference_area_m2,
        first_bending_frequency_hz=frequency,
        tip_deflection_m=tip_deflection,
    )
