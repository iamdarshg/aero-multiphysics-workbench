"""Geometry/property degradation produced by declared exposure.

Exposure is turned into explicit, revisioned modifiers: leading-edge and surface
roughness, erosion/material loss, deposits/fouling, clearance change, blocked
area, mass imbalance, stiffness/strength reduction, and heat-transfer/emissivity
change. The default model is a declared screening envelope, never a claim of
high-fidelity icing, erosion, or corrosion physics. Every result carries an
explicit fidelity, validity, SI units, input hash, software identity, and
provenance, and each modifier names the design sections it changes so the
existing invalidation contract can be reused.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .contracts import (
    DEFAULT_SOFTWARE,
    EnvironmentalFidelity,
    SoftwareIdentity,
    Validity,
)
from .errors import EnvironmentalError, ValidityError, finite
from .exposure import EnvironmentState, ExposureKind, ExposureSpec
from .provenance import analytical_provenance
from .units import Quantity

DESIGN_SECTIONS = frozenset({"parameters", "geometry", "materials", "operatingPoints"})


class DegradationKind(StrEnum):
    LEADING_EDGE_ROUGHNESS = "leading_edge_roughness"
    SURFACE_ROUGHNESS = "surface_roughness"
    EROSION_MATERIAL_LOSS = "erosion_material_loss"
    DEPOSIT_FOULING = "deposit_fouling"
    CLEARANCE_CHANGE = "clearance_change"
    BLOCKED_AREA = "blocked_area"
    MASS_IMBALANCE = "mass_imbalance"
    STIFFNESS_REDUCTION = "stiffness_reduction"
    STRENGTH_REDUCTION = "strength_reduction"
    HEAT_TRANSFER_CHANGE = "heat_transfer_change"
    EMISSIVITY_CHANGE = "emissivity_change"


#: degenerate quantity name -> expected physical dimension
DEGRADATION_QUANTITIES: dict[str, str] = {
    "leading_edge_roughness_increment": "length",
    "surface_roughness_increment": "length",
    "ice_areal_mass": "mass_per_area",
    "material_loss_depth": "length",
    "deposit_areal_mass": "mass_per_area",
    "blocked_area_fraction": "dimensionless",
    "clearance_change": "length",
    "mass_imbalance": "mass",
    "stiffness_fraction_reduction": "dimensionless",
    "strength_fraction_reduction": "dimensionless",
    "heat_transfer_fraction_change": "dimensionless",
    "emissivity_change": "dimensionless",
}


@dataclass(frozen=True, slots=True)
class EnvelopeModel:
    """Declared screening-envelope coefficients (all explicitly named).

    These are envelope parameters, not validated physics constants. ``source``
    records where the declared envelope comes from; the result provenance
    repeats it so an envelope is never mistaken for native data.
    """

    model_id: str
    revision: str
    ice_density_kg_m3: float
    collection_efficiency: float
    erosion_coefficient_m3_per_kg: float
    corrosion_coefficient_m3_per_kg: float
    deposit_density_kg_m3: float
    fouling_reference_areal_mass_kg_m2: float
    thermal_cycle_clearance_m_per_k: float
    strength_loss_per_cycle: float
    reference_material_thickness_m: float
    source: str

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.revision.strip():
            raise EnvironmentalError("envelope.model identity is required")
        if not self.source.strip():
            raise EnvironmentalError("envelope.source is required")
        for name in (
            "ice_density_kg_m3",
            "erosion_coefficient_m3_per_kg",
            "corrosion_coefficient_m3_per_kg",
            "deposit_density_kg_m3",
            "fouling_reference_areal_mass_kg_m2",
            "thermal_cycle_clearance_m_per_k",
            "strength_loss_per_cycle",
            "reference_material_thickness_m",
        ):
            finite(getattr(self, name), f"envelope.{name}", positive=True)
        finite(self.collection_efficiency, "envelope.collection_efficiency", minimum=0.0)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "modelId": self.model_id,
            "revision": self.revision,
            "iceDensityKgM3": self.ice_density_kg_m3,
            "collectionEfficiency": self.collection_efficiency,
            "erosionCoefficientM3PerKg": self.erosion_coefficient_m3_per_kg,
            "corrosionCoefficientM3PerKg": self.corrosion_coefficient_m3_per_kg,
            "depositDensityKgM3": self.deposit_density_kg_m3,
            "foulingReferenceArealMassKgM2": self.fouling_reference_areal_mass_kg_m2,
            "thermalCycleClearanceMPerK": self.thermal_cycle_clearance_m_per_k,
            "strengthLossPerCycle": self.strength_loss_per_cycle,
            "referenceMaterialThicknessM": self.reference_material_thickness_m,
            "source": self.source,
        }


DEFAULT_ENVELOPE_MODEL = EnvelopeModel(
    model_id="environmental-screening-envelope",
    revision="1",
    ice_density_kg_m3=900.0,
    collection_efficiency=1.0,
    erosion_coefficient_m3_per_kg=1.0e-10,
    corrosion_coefficient_m3_per_kg=1.0e-9,
    deposit_density_kg_m3=1500.0,
    fouling_reference_areal_mass_kg_m2=1.0,
    thermal_cycle_clearance_m_per_k=1.0e-9,
    strength_loss_per_cycle=1.0e-6,
    reference_material_thickness_m=5.0e-3,
    source="declared-screening-envelope-v1",
)

ENVELOPE_MODELS: dict[str, EnvelopeModel] = {
    DEFAULT_ENVELOPE_MODEL.model_id: DEFAULT_ENVELOPE_MODEL,
}


@dataclass(frozen=True, slots=True)
class DegradationModifier:
    """One explicit additive change to a named, dimensioned quantity."""

    kind: DegradationKind
    quantity_name: str
    delta: Quantity
    sections: tuple[str, ...]
    detail: str = ""

    def __post_init__(self) -> None:
        expected = DEGRADATION_QUANTITIES.get(self.quantity_name)
        if expected is None:
            raise EnvironmentalError(f"degradation.unknownQuantity:{self.quantity_name}")
        if self.delta.dimension != expected:
            raise EnvironmentalError(
                f"degradation.dimensionMismatch:{self.quantity_name}:"
                f"{self.delta.dimension}:{expected}"
            )
        if not self.sections:
            raise EnvironmentalError(f"degradation.sectionsRequired:{self.quantity_name}")
        unknown = sorted(set(self.sections) - DESIGN_SECTIONS)
        if unknown:
            raise EnvironmentalError(
                f"degradation.unknownSection:{','.join(unknown)}"
            )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "quantity": self.quantity_name,
            "deltaSI": self.delta.value_si,
            "dimension": self.delta.dimension,
            "sections": list(self.sections),
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class DegradationState:
    """The revisioned degradation produced from one environment state."""

    environment_id: str
    revision: int
    model_id: str
    modifiers: tuple[DegradationModifier, ...]
    changed_sections: tuple[str, ...]
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE
    fidelity: EnvironmentalFidelity = EnvironmentalFidelity.ENVELOPE

    @property
    def geometry_changed(self) -> bool:
        return "geometry" in self.changed_sections

    @property
    def material_changed(self) -> bool:
        return "materials" in self.changed_sections

    @property
    def digest(self) -> str:
        return self.provenance.inputs_hash

    def units(self) -> dict[str, str]:
        return {
            modifier.quantity_name: modifier.delta.unit
            for modifier in self.modifiers
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "environmentId": self.environment_id,
            "revision": self.revision,
            "modelId": self.model_id,
            "fidelity": self.fidelity.value,
            "changedSections": list(self.changed_sections),
            "modifiers": [modifier.canonical_payload() for modifier in self.modifiers],
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
        }


def _modifiers_for(
    exposure: ExposureSpec, model: EnvelopeModel
) -> list[DegradationModifier]:
    kind = exposure.kind
    if kind is ExposureKind.ICING:
        water = exposure.si("water_content")
        speed = exposure.si("impact_speed")
        duration = exposure.si("duration")
        areal = model.collection_efficiency * water * speed * duration
        thickness = areal / model.ice_density_kg_m3
        return [
            DegradationModifier(
                DegradationKind.LEADING_EDGE_ROUGHNESS,
                "leading_edge_roughness_increment",
                Quantity(thickness, "m"),
                ("geometry",),
                "ice-thickness roughness envelope",
            ),
            DegradationModifier(
                DegradationKind.SURFACE_ROUGHNESS,
                "surface_roughness_increment",
                Quantity(thickness, "m"),
                ("geometry",),
                "ice-thickness roughness envelope",
            ),
            DegradationModifier(
                DegradationKind.DEPOSIT_FOULING,
                "ice_areal_mass",
                Quantity(areal, "kg/m2"),
                ("geometry", "materials"),
                "accreted ice areal mass envelope",
            ),
        ]
    if kind in (ExposureKind.RAIN_INGESTION, ExposureKind.SAND_DUST):
        if kind is ExposureKind.RAIN_INGESTION:
            concentration = exposure.si("water_content")
        else:
            concentration = exposure.si("particle_concentration")
        speed = exposure.si("impact_speed")
        duration = exposure.si("duration")
        dose = concentration * speed * duration
        loss = model.erosion_coefficient_m3_per_kg * dose
        return [
            DegradationModifier(
                DegradationKind.EROSION_MATERIAL_LOSS,
                "material_loss_depth",
                Quantity(loss, "m"),
                ("geometry", "materials"),
                "erosion dose envelope",
            ),
            DegradationModifier(
                DegradationKind.SURFACE_ROUGHNESS,
                "surface_roughness_increment",
                Quantity(loss, "m"),
                ("geometry",),
                "erosion roughness envelope",
            ),
        ]
    if kind is ExposureKind.SALT_CORROSIVE:
        concentration = exposure.si("salt_concentration")
        duration = exposure.si("duration")
        depth = model.corrosion_coefficient_m3_per_kg * concentration * duration
        strength_loss = min(depth / model.reference_material_thickness_m, 1.0)
        return [
            DegradationModifier(
                DegradationKind.EROSION_MATERIAL_LOSS,
                "material_loss_depth",
                Quantity(depth, "m"),
                ("geometry", "materials"),
                "corrosion depth envelope",
            ),
            DegradationModifier(
                DegradationKind.STRENGTH_REDUCTION,
                "strength_fraction_reduction",
                Quantity(strength_loss, "dimensionless"),
                ("materials",),
                "corrosion strength-loss envelope",
            ),
            DegradationModifier(
                DegradationKind.STIFFNESS_REDUCTION,
                "stiffness_fraction_reduction",
                Quantity(0.5 * strength_loss, "dimensionless"),
                ("materials",),
                "corrosion stiffness-loss envelope",
            ),
            DegradationModifier(
                DegradationKind.HEAT_TRANSFER_CHANGE,
                "heat_transfer_fraction_change",
                Quantity(strength_loss, "dimensionless"),
                ("materials", "operatingPoints"),
                "corroded-surface heat-transfer change envelope",
            ),
            DegradationModifier(
                DegradationKind.EMISSIVITY_CHANGE,
                "emissivity_change",
                Quantity(strength_loss, "dimensionless"),
                ("materials",),
                "corroded-surface emissivity change envelope",
            ),
        ]
    if kind is ExposureKind.PARTICULATE_FOULING:
        deposit_rate = exposure.si("deposit_rate")
        duration = exposure.si("duration")
        areal = deposit_rate * duration
        thickness = areal / model.deposit_density_kg_m3
        blocked = min(areal / model.fouling_reference_areal_mass_kg_m2, 1.0)
        return [
            DegradationModifier(
                DegradationKind.DEPOSIT_FOULING,
                "deposit_areal_mass",
                Quantity(areal, "kg/m2"),
                ("geometry", "materials"),
                "fouling deposit envelope",
            ),
            DegradationModifier(
                DegradationKind.SURFACE_ROUGHNESS,
                "surface_roughness_increment",
                Quantity(thickness, "m"),
                ("geometry",),
                "deposit-thickness roughness envelope",
            ),
            DegradationModifier(
                DegradationKind.BLOCKED_AREA,
                "blocked_area_fraction",
                Quantity(blocked, "dimensionless"),
                ("geometry", "operatingPoints"),
                "fouling blockage envelope",
            ),
            DegradationModifier(
                DegradationKind.HEAT_TRANSFER_CHANGE,
                "heat_transfer_fraction_change",
                Quantity(blocked, "dimensionless"),
                ("materials", "operatingPoints"),
                "fouled-surface heat-transfer change envelope",
            ),
            DegradationModifier(
                DegradationKind.EMISSIVITY_CHANGE,
                "emissivity_change",
                Quantity(blocked, "dimensionless"),
                ("materials",),
                "fouled-surface emissivity change envelope",
            ),
        ]
    if kind is ExposureKind.THERMAL_CYCLING:
        swing = exposure.si("temperature_swing")
        cycles = exposure.si("cycles")
        clearance = model.thermal_cycle_clearance_m_per_k * swing * cycles
        strength_loss = min(model.strength_loss_per_cycle * cycles, 1.0)
        return [
            DegradationModifier(
                DegradationKind.CLEARANCE_CHANGE,
                "clearance_change",
                Quantity(clearance, "m"),
                ("geometry",),
                "thermal-cycling clearance envelope",
            ),
            DegradationModifier(
                DegradationKind.STRENGTH_REDUCTION,
                "strength_fraction_reduction",
                Quantity(strength_loss, "dimensionless"),
                ("materials",),
                "thermal-fatigue strength-loss envelope",
            ),
            DegradationModifier(
                DegradationKind.STIFFNESS_REDUCTION,
                "stiffness_fraction_reduction",
                Quantity(0.5 * strength_loss, "dimensionless"),
                ("materials",),
                "thermal-fatigue stiffness-loss envelope",
            ),
        ]
    if kind is ExposureKind.FOREIGN_OBJECT_IMPACT:
        mass = exposure.si("impactor_mass")
        return [
            DegradationModifier(
                DegradationKind.MASS_IMBALANCE,
                "mass_imbalance",
                Quantity(mass, "kg"),
                ("parameters",),
                "worst-case embedded foreign-object mass envelope",
            )
        ]
    raise EnvironmentalError(f"degradation.unsupportedExposure:{kind.value}")


def evaluate_degradation(
    environment: EnvironmentState,
    *,
    model: EnvelopeModel = DEFAULT_ENVELOPE_MODEL,
) -> DegradationState:
    """Turn a declared environment state into explicit degradation modifiers.

    The result is a screening envelope (``EnvironmentalFidelity.ENVELOPE``). It
    is deterministic, unit-bearing, and fully provenance-tracked; it never
    claims high-fidelity icing/erosion/corrosion physics.
    """

    modifiers: list[DegradationModifier] = []
    for exposure in environment.exposures:
        modifiers.extend(_modifiers_for(exposure, model))
    sections = tuple(sorted({section for item in modifiers for section in item.sections}))
    checks: dict[str, bool] = {}
    for modifier in modifiers:
        value = modifier.delta.value_si
        checks[f"finite:{modifier.quantity_name}"] = value == value and value not in (
            float("inf"),
            float("-inf"),
        )
        if modifier.delta.dimension == "dimensionless" and "fraction" in modifier.quantity_name:
            checks[f"bounded:{modifier.quantity_name}"] = 0.0 <= value <= 1.0
    if not all(checks.values()):
        raise ValidityError("degradation.producedOutOfDomainModifier")
    provenance = analytical_provenance(
        f"environmental.degradation.{model.model_id}@{model.revision}",
        {
            "environment": environment.canonical_payload(),
            "model": model.canonical_payload(),
        },
        assumptions=(
            "declared screening envelope; not validated ice/accretion/erosion physics",
            f"envelope source: {model.source}",
        ),
    )
    return DegradationState(
        environment_id=environment.environment_id,
        revision=environment.revision,
        model_id=model.model_id,
        modifiers=tuple(modifiers),
        changed_sections=sections,
        validity=Validity(
            passed=True,
            checks={**checks, "modifiers_produced": len(modifiers) > 0},
            detail=f"screening envelope {model.model_id}@{model.revision}",
        ),
        provenance=provenance,
    )


__all__ = [
    "DEFAULT_ENVELOPE_MODEL",
    "DEGRADATION_QUANTITIES",
    "DESIGN_SECTIONS",
    "ENVELOPE_MODELS",
    "DegradationKind",
    "DegradationModifier",
    "DegradationState",
    "EnvelopeModel",
    "evaluate_degradation",
]
