"""Erosion / material-loss assessment.

Erosion is represented as an explicit material-loss depth and areal mass
impacted derived from a declared sand/dust or rain exposure. The result is a
screening envelope with full provenance; it is not a validated erosion model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance

from .contracts import (
    DEFAULT_SOFTWARE,
    EnvironmentalFidelity,
    SoftwareIdentity,
    Validity,
)
from .degradation import (
    DEFAULT_ENVELOPE_MODEL,
    EnvelopeModel,
    evaluate_degradation,
)
from .errors import EnvironmentalError, ValidityError
from .exposure import EnvironmentState, ExposureKind, ExposureSpec
from .units import Quantity

_ERODING_KINDS = (ExposureKind.SAND_DUST, ExposureKind.RAIN_INGESTION)


@dataclass(frozen=True, slots=True)
class ErosionAssessment:
    """Material loss for one sand/dust or rain exposure."""

    exposure_kind: ExposureKind
    material_loss_depth: Quantity
    areal_mass_impacted: Quantity
    erosion_rate: Quantity
    fidelity: EnvironmentalFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "material_loss_depth": self.material_loss_depth.unit,
            "areal_mass_impacted": self.areal_mass_impacted.unit,
            "erosion_rate": self.erosion_rate.unit,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "exposureKind": self.exposure_kind.value,
            "fidelity": self.fidelity.value,
            "materialLossDepth": self.material_loss_depth.canonical(),
            "arealMassImpacted": self.areal_mass_impacted.canonical(),
            "erosionRate": self.erosion_rate.canonical(),
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
        }


def evaluate_erosion(
    exposure: ExposureSpec,
    *,
    model: EnvelopeModel = DEFAULT_ENVELOPE_MODEL,
) -> ErosionAssessment:
    """Assess a sand/dust or rain exposure as an explicit erosion envelope."""

    if exposure.kind not in _ERODING_KINDS:
        raise EnvironmentalError(f"erosion.unsupportedExposure:{exposure.kind.value}")
    environment = EnvironmentState(
        environment_id="erosion-assessment",
        revision=0,
        atmosphere_model="declared-reference",
        exposures=(exposure,),
    )
    state = evaluate_degradation(environment, model=model)
    deltas = {modifier.quantity_name: modifier.delta for modifier in state.modifiers}
    loss = deltas.get("material_loss_depth")
    if loss is None:
        raise ValidityError("erosion.envelopeMissingModifier")
    if exposure.kind is ExposureKind.SAND_DUST:
        concentration = exposure.si("particle_concentration")
    else:
        concentration = exposure.si("water_content")
    dose = concentration * exposure.si("impact_speed") * exposure.si("duration")
    duration = exposure.si("duration")
    return ErosionAssessment(
        exposure_kind=exposure.kind,
        material_loss_depth=loss,
        areal_mass_impacted=Quantity(dose, "kg/m2"),
        erosion_rate=Quantity(loss.value_si / duration, "m/s"),
        fidelity=EnvironmentalFidelity.ENVELOPE,
        validity=Validity(
            passed=True,
            checks={"loss_nonnegative": loss.value_si >= 0.0},
            detail=f"erosion screening envelope {model.model_id}@{model.revision}",
        ),
        provenance=state.provenance,
    )


__all__ = [
    "ErosionAssessment",
    "evaluate_erosion",
]
