"""Particulate contamination / fouling assessment.

Contamination is represented as explicit deposit areal mass, deposit thickness
(roughness), and blocked-area fraction derived from a declared exposure. The
result is a screening envelope with full provenance; it is not a validated
fouling model.
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


@dataclass(frozen=True, slots=True)
class ContaminationAssessment:
    """Deposit/fouling state for one particulate-fouling exposure."""

    exposure_kind: ExposureKind
    deposit_areal_mass: Quantity
    deposit_thickness: Quantity
    blocked_area_fraction: Quantity
    fidelity: EnvironmentalFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "deposit_areal_mass": self.deposit_areal_mass.unit,
            "deposit_thickness": self.deposit_thickness.unit,
            "blocked_area_fraction": self.blocked_area_fraction.unit,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "exposureKind": self.exposure_kind.value,
            "fidelity": self.fidelity.value,
            "depositArealMass": self.deposit_areal_mass.canonical(),
            "depositThickness": self.deposit_thickness.canonical(),
            "blockedAreaFraction": self.blocked_area_fraction.canonical(),
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
        }


def evaluate_contamination(
    exposure: ExposureSpec,
    *,
    model: EnvelopeModel = DEFAULT_ENVELOPE_MODEL,
) -> ContaminationAssessment:
    """Assess a particulate-fouling exposure as an explicit deposit envelope."""

    if exposure.kind is not ExposureKind.PARTICULATE_FOULING:
        raise EnvironmentalError(
            f"contamination.unsupportedExposure:{exposure.kind.value}"
        )
    environment = EnvironmentState(
        environment_id="contamination-assessment",
        revision=0,
        atmosphere_model="declared-reference",
        exposures=(exposure,),
    )
    state = evaluate_degradation(environment, model=model)
    deltas = {modifier.quantity_name: modifier.delta for modifier in state.modifiers}
    areal = deltas.get("deposit_areal_mass")
    thickness = deltas.get("surface_roughness_increment")
    blocked = deltas.get("blocked_area_fraction")
    if areal is None or thickness is None or blocked is None:
        raise ValidityError("contamination.envelopeMissingModifier")
    return ContaminationAssessment(
        exposure_kind=exposure.kind,
        deposit_areal_mass=areal,
        deposit_thickness=thickness,
        blocked_area_fraction=blocked,
        fidelity=EnvironmentalFidelity.ENVELOPE,
        validity=Validity(
            passed=True,
            checks={"blockage_bounded": 0.0 <= blocked.value_si <= 1.0},
            detail=f"fouling screening envelope {model.model_id}@{model.revision}",
        ),
        provenance=state.provenance,
    )


__all__ = [
    "ContaminationAssessment",
    "evaluate_contamination",
]
