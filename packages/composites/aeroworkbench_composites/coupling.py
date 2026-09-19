"""Dynamic, thermal, and durability coupling for composite structures.

Composite membrane/bending stiffness, areal mass, thermal resultants, and
rotational prestress are exposed as operating-point values that feed the
ADV-PHYS 04/05 durability and aeroelastic participants. Laminate fatigue always
routes through the durability package's laminate-specific fatigue seam, so an
isotropic S-N model is never applied to a composite.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_durability.composites import (
    CompositeFatigueAllowables,
    evaluate_composite_fatigue,
)
from aeroworkbench_durability.fatigue import DamageResult, StressCycle
from aeroworkbench_materials import LaminateRevision

from .clt import LaminateAnalysis, LaminateLoad, analyze_laminate
from .provenance import analytical_provenance
from .validity import DataUnavailable, Validity, finite

__all__ = [
    "ModalEstimate",
    "analyze_and_estimate",
    "areal_mass_kg_m2",
    "cantilever_bending_frequency_hz",
    "centrifugal_membrane_load",
    "composite_fatigue_damage",
    "pressure_hoop_load",
    "to_aeroelastic_inputs",
]

_CANTILEVER_BETA1_L = 1.875104068711961


@dataclass(frozen=True, slots=True)
class ModalEstimate:
    """A reduced (analytical) first-mode estimate of a laminated beam/shell."""

    frequency_hz: float
    areal_mass_kg_m2: float
    bending_stiffness_d11_n_m: float
    length_m: float
    method: str
    provenance: Provenance
    validity: Validity

    def units(self) -> dict[str, str]:
        return {
            "frequency_hz": "1",
            "areal_mass_kg_m2": "kg/m^2",
            "bending_stiffness_d11_n_m": "N*m",
            "length_m": "m",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "frequencyHz": self.frequency_hz,
            "arealMassKgM2": self.areal_mass_kg_m2,
            "bendingStiffnessD11NM": self.bending_stiffness_d11_n_m,
            "lengthM": self.length_m,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def areal_mass_kg_m2(analysis: LaminateAnalysis) -> float:
    """Mass per unit area, failing closed when density data is absent."""

    density = analysis.membrane.density_kg_m3
    if density <= 0.0:
        raise DataUnavailable("AREAL_MASS_REQUIRES_PLY_DENSITY")
    return density * analysis.total_thickness_m


def cantilever_bending_frequency_hz(
    analysis: LaminateAnalysis, *, length_m: float
) -> ModalEstimate:
    """First bending mode of a cantilevered laminated beam/shell strip."""

    length = finite(length_m, "length_m", positive=True)
    areal = areal_mass_kg_m2(analysis)
    d11 = analysis.d[0][0]
    if d11 <= 0.0:
        raise DataUnavailable("BENDING_STIFFNESS_D11_NOT_POSITIVE")
    frequency = (
        (_CANTILEVER_BETA1_L**2 / (2.0 * pi)) * sqrt(d11 / areal) / (length * length)
    )
    provenance = analytical_provenance(
        "composite-cantilever-modal-estimate",
        {
            "laminate": analysis.laminate_identity,
            "laminateDigest": analysis.laminate_digest,
            "lengthM": length,
            "d11NM": d11,
            "arealMassKgM2": areal,
        },
        assumptions=(
            "Euler-Bernoulli cantilever first mode; unit-width strip",
            "reduced analytical estimate, not a native modal solve",
        ),
    )
    return ModalEstimate(
        frequency_hz=frequency,
        areal_mass_kg_m2=areal,
        bending_stiffness_d11_n_m=d11,
        length_m=length,
        method="cantilever-euler-bernoulli-first-mode",
        provenance=provenance,
        validity=Validity(
            passed=True,
            checks={"bending_stiffness_positive": True},
            detail=f"modal:{analysis.laminate_identity}",
        ),
    )


def centrifugal_membrane_load(
    analysis: LaminateAnalysis, *, tip_radius_m: float, omega_rad_s: float
) -> LaminateLoad:
    """Root membrane resultant of a uniform rotating strip (per unit width).

    For a uniform laminate of areal mass m radially spun at omega from r=0 to R,
    the root resultant is N = 0.5 * m * omega^2 * R^2.
    """

    radius = finite(tip_radius_m, "tip_radius_m", positive=True)
    omega = finite(omega_rad_s, "omega_rad_s")
    areal = areal_mass_kg_m2(analysis)
    root_resultant = 0.5 * areal * omega * omega * radius * radius
    return LaminateLoad(n_x_n_m=root_resultant)


def pressure_hoop_load(
    pressure_pa: float, *, radius_m: float, factor: float = 1.0
) -> LaminateLoad:
    """Pressure-driven membrane resultant N = factor * p * R (per unit width)."""

    pressure = finite(pressure_pa, "pressure_pa")
    radius = finite(radius_m, "radius_m", positive=True)
    scale = finite(factor, "factor")
    return LaminateLoad(n_y_n_m=scale * pressure * radius)


def composite_fatigue_damage(
    laminate: LaminateRevision,
    cycles: tuple[StressCycle, ...],
    *,
    allowables: CompositeFatigueAllowables | None,
    temperature_k: float,
    safety_factor: float = 1.0,
) -> DamageResult:
    """Delegate laminate fatigue to the durability package's laminate seam.

    ``allowables`` must be a durability :class:`CompositeFatigueAllowables` bound
    to this laminate's digest; absent/mismatched allowables fail closed inside
    the seam, so no isotropic S-N formula is ever substituted.
    """

    return evaluate_composite_fatigue(
        laminate,
        cycles,
        allowables=allowables,
        temperature_k=temperature_k,
        safety_factor=safety_factor,
    )


def to_aeroelastic_inputs(estimate: ModalEstimate) -> dict[str, float]:
    """Operating-point scalars published to the aeroelastic participant."""

    return {
        "frequency_hz": estimate.frequency_hz,
        "areal_mass_kg_m2": estimate.areal_mass_kg_m2,
        "bending_stiffness_d11_n_m": estimate.bending_stiffness_d11_n_m,
    }


def analyze_and_estimate(
    laminate: LaminateRevision, *, length_m: float
) -> ModalEstimate:
    """Convenience: CLT then first-mode estimate on the same laminate."""

    return cantilever_bending_frequency_hz(analyze_laminate(laminate), length_m=length_m)
