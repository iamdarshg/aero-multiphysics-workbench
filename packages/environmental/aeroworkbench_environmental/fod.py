"""Foreign-object / debris impact event and result contracts.

The contract records a declared impact event and its kinematics (kinetic
energy, momentum, projected footprint). It deliberately does **not** invent
residual strength, damage tolerance, or penetration: those require a native
structural FEA / damage engine and fail closed when it is absent. The report
exposes a typed ``structural_damage_feed`` that can be handed to a structural
damage/life analysis, plus a location descriptor for the impacted geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any

from aeroworkbench_core.types import Provenance

from .contracts import (
    DEFAULT_SOFTWARE,
    EnvironmentalFidelity,
    SoftwareIdentity,
    Validity,
)
from .errors import CapabilityUnavailable, EnvironmentalError, finite
from .exposure import ExposureKind, ExposureSpec
from .provenance import analytical_provenance
from .units import Quantity

_REQUIREMENT = "impact-structural-fea"


@dataclass(frozen=True, slots=True)
class ImpactEvent:
    """A declared impact event (generic debris / foreign object)."""

    event_id: str
    impactor_mass: Quantity
    impact_speed: Quantity
    impactor_diameter: Quantity
    location: str
    incidence_angle_deg: float = 0.0

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise EnvironmentalError("impact.eventId is required")
        if not self.location.strip():
            raise EnvironmentalError("impact.location is required")
        if self.impactor_mass.dimension != "mass":
            raise EnvironmentalError("impact.impactorMass must be a mass")
        if self.impact_speed.dimension != "velocity":
            raise EnvironmentalError("impact.impactorSpeed must be a velocity")
        if self.impactor_diameter.dimension != "length":
            raise EnvironmentalError("impact.impactorDiameter must be a length")
        if self.impactor_mass.value_si <= 0.0 or self.impactor_diameter.value_si <= 0.0:
            raise EnvironmentalError("impact mass and diameter must be positive")
        if self.impact_speed.value_si <= 0.0:
            raise EnvironmentalError("impact speed must be positive")
        finite(self.incidence_angle_deg, "impact.incidenceAngleDeg")

    @property
    def kinetic_energy_j(self) -> float:
        speed = self.impact_speed.value_si
        return 0.5 * self.impactor_mass.value_si * speed * speed

    @property
    def momentum_kg_m_s(self) -> float:
        return self.impactor_mass.value_si * self.impact_speed.value_si

    @property
    def footprint_area_m2(self) -> float:
        radius = 0.5 * self.impactor_diameter.value_si
        return pi * radius * radius

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "impactorMass": self.impactor_mass.canonical(),
            "impactSpeed": self.impact_speed.canonical(),
            "impactorDiameter": self.impactor_diameter.canonical(),
            "location": self.location,
            "incidenceAngleDeg": self.incidence_angle_deg,
        }

    @classmethod
    def from_exposure(
        cls, exposure: ExposureSpec, *, event_id: str, location: str
    ) -> ImpactEvent:
        if exposure.kind is not ExposureKind.FOREIGN_OBJECT_IMPACT:
            raise EnvironmentalError("impact.exposure must be a foreign-object impact")
        return cls(
            event_id=event_id,
            impactor_mass=exposure.driver("impactor_mass"),
            impact_speed=exposure.driver("impact_speed"),
            impactor_diameter=exposure.driver("impactor_diameter"),
            location=location,
        )


@dataclass(frozen=True, slots=True)
class StructuralDamageFeed:
    """Typed hand-off to a structural damage/life analysis (no strength claim)."""

    event_id: str
    location: str
    kinetic_energy: Quantity
    momentum: Quantity
    footprint_area: Quantity
    incidence_angle_deg: float
    residual_strength_provided: bool = False

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "location": self.location,
            "kineticEnergy": self.kinetic_energy.canonical(),
            "momentum": self.momentum.canonical(),
            "footprintArea": self.footprint_area.canonical(),
            "incidenceAngleDeg": self.incidence_angle_deg,
            "residualStrengthProvided": self.residual_strength_provided,
        }


@dataclass(frozen=True, slots=True)
class ImpactReport:
    """Kinematic impact report; residual strength is explicitly not claimed."""

    event_id: str
    location: str
    kinetic_energy: Quantity
    momentum: Quantity
    footprint_area: Quantity
    fidelity: EnvironmentalFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE
    residual_strength_provided: bool = False
    structural_analysis_required: bool = True

    def units(self) -> dict[str, str]:
        return {
            "kinetic_energy": self.kinetic_energy.unit,
            "momentum": self.momentum.unit,
            "footprint_area": self.footprint_area.unit,
        }

    def structural_damage_feed(self) -> StructuralDamageFeed:
        """A feed for structural damage/life analysis; never a residual strength."""

        return StructuralDamageFeed(
            event_id=self.event_id,
            location=self.location,
            kinetic_energy=self.kinetic_energy,
            momentum=self.momentum,
            footprint_area=self.footprint_area,
            incidence_angle_deg=0.0,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "location": self.location,
            "fidelity": self.fidelity.value,
            "kineticEnergy": self.kinetic_energy.canonical(),
            "momentum": self.momentum.canonical(),
            "footprintArea": self.footprint_area.canonical(),
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
            "residualStrengthProvided": self.residual_strength_provided,
            "structuralAnalysisRequired": self.structural_analysis_required,
        }


def evaluate_impact(event: ImpactEvent) -> ImpactReport:
    """Deterministic impact kinematics; never invents residual strength."""

    provenance = analytical_provenance(
        "environmental.fod.impact-kinematics",
        {"event": event.canonical_payload()},
        assumptions=(
            "kinematics only; residual strength/damage tolerance require native FEA",
        ),
    )
    return ImpactReport(
        event_id=event.event_id,
        location=event.location,
        kinetic_energy=Quantity(event.kinetic_energy_j, "J"),
        momentum=Quantity(event.momentum_kg_m_s, "kg*m/s"),
        footprint_area=Quantity(event.footprint_area_m2, "m2"),
        fidelity=EnvironmentalFidelity.ENVELOPE,
        validity=Validity(
            passed=True,
            checks={"energy_positive": event.kinetic_energy_j > 0.0},
            detail="impact kinematics",
        ),
        provenance=provenance,
    )


def native_impact_capability(*, present: bool = False) -> bool:
    """Whether a native impact/structural-damage engine is wired."""

    return present


def require_residual_strength(*, present: bool = False) -> None:
    """Residual strength requires a native structural engine; else fail closed."""

    if not native_impact_capability(present=present):
        raise CapabilityUnavailable(
            f"{_REQUIREMENT} is not available; residual strength cannot be claimed"
        )


__all__ = [
    "ImpactEvent",
    "ImpactReport",
    "StructuralDamageFeed",
    "evaluate_impact",
    "native_impact_capability",
    "require_residual_strength",
]
