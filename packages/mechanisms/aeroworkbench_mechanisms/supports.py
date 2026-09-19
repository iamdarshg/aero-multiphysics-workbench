"""Generic fixed/elastic supports with 6-DOF stiffness, damping, and growth.

Supports are the mechanical grounding of any assembly: fixed restraints,
elastic (spring-damper) supports, and bushings. They expose translational and
rotational stiffness/damping for structural and rotordynamic models, plus
thermal growth and misalignment reaction loads so interface loads can enter a
life assessment. Application-specific naming is deliberately absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .validity import MechanismError, Validity, finite, finite_vector


class SupportKind(StrEnum):
    """The generic support taxonomy."""

    FIXED = "fixed"
    ELASTIC = "elastic"
    BUSHING = "bushing"


@dataclass(frozen=True, slots=True)
class SixDofProperties:
    """Translational and rotational stiffness/damping for a support or joint."""

    translation_stiffness_n_m: tuple[float, ...] = (0.0, 0.0, 0.0)
    translation_damping_n_s_m: tuple[float, ...] = (0.0, 0.0, 0.0)
    rotation_stiffness_n_m_rad: tuple[float, ...] = (0.0, 0.0, 0.0)
    rotation_damping_n_m_s_rad: tuple[float, ...] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        for label, vector in (
            ("translation_stiffness_n_m", self.translation_stiffness_n_m),
            ("translation_damping_n_s_m", self.translation_damping_n_s_m),
            ("rotation_stiffness_n_m_rad", self.rotation_stiffness_n_m_rad),
            ("rotation_damping_n_m_s_rad", self.rotation_damping_n_m_s_rad),
        ):
            finite_vector(vector, label, minimum=0.0)
        if any(value < 0.0 for value in self.translation_stiffness_n_m):
            raise MechanismError("translation stiffness must be non-negative")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "translation_stiffness_n_m": list(self.translation_stiffness_n_m),
            "translation_damping_n_s_m": list(self.translation_damping_n_s_m),
            "rotation_stiffness_n_m_rad": list(self.rotation_stiffness_n_m_rad),
            "rotation_damping_n_m_s_rad": list(self.rotation_damping_n_m_s_rad),
        }

    @property
    def is_rigid(self) -> bool:
        return all(value == 0.0 for value in self.translation_stiffness_n_m)


@dataclass(frozen=True, slots=True)
class SupportSpec:
    """One typed support declaration."""

    support_id: str
    kind: SupportKind
    properties: SixDofProperties
    length_m: float
    thermal_expansion_per_k: float
    reference_temperature_k: float = 293.15
    allowable_reaction_n: float | None = None

    def __post_init__(self) -> None:
        if not self.support_id.strip():
            raise MechanismError("support.support_id is required")
        finite(self.length_m, "support.length_m", minimum=0.0)
        finite(self.thermal_expansion_per_k, "support.thermal_expansion_per_k", minimum=0.0)
        finite(
            self.reference_temperature_k,
            "support.reference_temperature_k",
            positive=True,
        )
        if self.kind is not SupportKind.FIXED and self.properties.is_rigid:
            raise MechanismError("elastic/bushing support requires non-zero stiffness")
        if self.allowable_reaction_n is not None:
            finite(self.allowable_reaction_n, "support.allowable_reaction_n", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "support_id": self.support_id,
            "kind": self.kind.value,
            "properties": self.properties.canonical_payload(),
            "length_m": self.length_m,
            "thermal_expansion_per_k": self.thermal_expansion_per_k,
            "reference_temperature_k": self.reference_temperature_k,
            "allowable_reaction_n": self.allowable_reaction_n,
        }


@dataclass(frozen=True, slots=True)
class SupportResult:
    """Evaluated support state with reaction, growth, and provenance."""

    support_id: str
    kind: str
    grounded: bool
    stiffness_n_m: tuple[float, ...]
    damping_n_s_m: tuple[float, ...]
    rotation_stiffness_n_m_rad: tuple[float, ...]
    rotation_damping_n_m_s_rad: tuple[float, ...]
    thermal_growth_m: float
    misalignment_m: float
    reaction_force_n: float
    utilization: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "stiffness_n_m": "N/m",
            "damping_n_s_m": "N*s/m",
            "rotation_stiffness_n_m_rad": "N*m/rad",
            "rotation_damping_n_m_s_rad": "N*m*s/rad",
            "thermal_growth_m": "m",
            "misalignment_m": "m",
            "reaction_force_n": "N",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "support_id": self.support_id,
            "kind": self.kind,
            "grounded": self.grounded,
            "reaction_force_n": self.reaction_force_n,
            "thermal_growth_m": self.thermal_growth_m,
        }


def evaluate_support(
    spec: SupportSpec,
    *,
    temperature_k: float,
    misalignment_m: float = 0.0,
    offset_load_n: float = 0.0,
) -> SupportResult:
    """Evaluate a support reaction, growth, and limit utilization."""

    temperature = finite(temperature_k, "temperature_k", positive=True)
    misalignment = finite(misalignment_m, "misalignment_m", minimum=0.0)
    offset = finite(offset_load_n, "offset_load_n", minimum=0.0)
    thermal_growth = (
        spec.thermal_expansion_per_k * spec.length_m * (temperature - spec.reference_temperature_k)
    )
    grounded = spec.kind is SupportKind.FIXED
    stiffness = spec.properties.translation_stiffness_n_m
    effective = stiffness[1] if stiffness[1] > 0.0 else stiffness[0]
    reaction = offset + effective * misalignment
    utilization = (
        reaction / spec.allowable_reaction_n if spec.allowable_reaction_n else 0.0
    )
    checks = {
        "temperature_above_zero": temperature > 0.0,
        "reaction_finite": reaction >= 0.0,
        "within_allowable_reaction": utilization <= 1.0,
        "stiffness_declared": grounded or not spec.properties.is_rigid,
    }
    provenance = analytical_provenance(
        "mechanisms.supports.elastic-support",
        {
            "support": spec.canonical_payload(),
            "temperature_k": temperature,
            "misalignment_m": misalignment,
            "offset_load_n": offset,
        },
    )
    return SupportResult(
        support_id=spec.support_id,
        kind=spec.kind.value,
        grounded=grounded,
        stiffness_n_m=tuple(stiffness),
        damping_n_s_m=tuple(spec.properties.translation_damping_n_s_m),
        rotation_stiffness_n_m_rad=tuple(spec.properties.rotation_stiffness_n_m_rad),
        rotation_damping_n_m_s_rad=tuple(spec.properties.rotation_damping_n_m_s_rad),
        thermal_growth_m=thermal_growth,
        misalignment_m=misalignment,
        reaction_force_n=reaction,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="linear elastic support reaction under declared misalignment",
        ),
        provenance=provenance,
    )


__all__ = [
    "SixDofProperties",
    "SupportKind",
    "SupportResult",
    "SupportSpec",
    "evaluate_support",
]
