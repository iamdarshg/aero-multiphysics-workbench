"""Architecture seams adjacent to fixed-wing synthesis.

Rotorcraft sizing is capability-gated on AIRFRAME 08/#61 rotor aerodynamics and
therefore fails closed until that capability exists. The lifting-body seam is
analytic: it derives a bounded planform/thickness/sweep seed from declared
span/volume/Mach constraints and marks every relation validity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest, normalize_numbers
from ..units import Quantity
from . import methods
from .errors import SynthesisInfeasibleError
from .fixed_wing import requirement_bounds
from .methods import SynthesisQuantity
from .requirements import CompiledRequirements
from .seeds import VehicleSeed

_ANALYTICAL = ResultSource.ANALYTICAL
_FIDELITY = FidelityLevel.ANALYTICAL
_LIFTING_BODY_ASPECT_RATIO = 1.5


@dataclass(frozen=True, slots=True)
class SeamResult:
    """Availability and (when available) seeds for one architecture seam."""

    architecture_type: str
    available: bool
    reason: str
    seeds: tuple[VehicleSeed, ...]
    blocking_issue: str | None
    provenance: Provenance

    def canonical(self) -> dict[str, object]:
        return cast(
            dict[str, object],
            normalize_numbers(
                {
                    "architectureType": self.architecture_type,
                    "available": self.available,
                    "reason": self.reason,
                    "blockingIssue": self.blocking_issue,
                    "seeds": [seed.canonical_payload() for seed in self.seeds],
                    "provenance": self.provenance.model_dump(mode="json"),
                }
            ),
        )

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())


def _provenance(
    compiled: CompiledRequirements, architecture: str, capability: str, assumptions: tuple[str, ...]
) -> Provenance:
    return Provenance.from_inputs(
        source=_ANALYTICAL,
        model=f"{methods.SYNTHESIS_MODEL}:{architecture}-seam",
        model_version=methods.SYNTHESIS_MODEL_VERSION,
        fidelity=_FIDELITY,
        inputs={"requirementsHash": compiled.content_hash, "capability": capability},
        assumptions=assumptions,
    )


def synthesize_rotorcraft_seam(compiled: CompiledRequirements) -> SeamResult:
    """Capability-gated rotorcraft seam: unavailable until AIRFRAME 08/#61."""
    assumptions = (
        "Capability-gated seam; rotor aerodynamics (AIRFRAME 08/#61) is not integrated.",
        "No rotor seed is fabricated; callers must fail closed or wait for the capability.",
    )
    provenance = _provenance(compiled, "rotorcraft", "rotor-aerodynamics", assumptions)
    return SeamResult(
        architecture_type="rotorcraft",
        available=False,
        reason="ROTORCRAFT_SEAM_UNAVAILABLE: AIRFRAME 08/#61 rotor aerodynamics not integrated",
        seeds=(),
        blocking_issue="AIRFRAME-08/#61",
        provenance=provenance,
    )


def _rename(quantity: SynthesisQuantity, name: str) -> SynthesisQuantity:
    return replace(quantity, name=name)


def synthesize_lifting_body_seam(compiled: CompiledRequirements) -> SeamResult:
    """Analytic lifting-body seam from span/volume/Mach constraints."""
    assumptions = (
        "Lifting-body seam: blended planform with declared aspect ratio and volume closure.",
        "Screening geometry only; no aerodynamic coefficients are claimed.",
    )
    bounds = requirement_bounds(compiled)
    span_limit = bounds.get("span_limit", (None, None))[1]
    volume_limit = bounds.get("volume_limit", (None, None))[1]
    speed = None
    for metric in ("max_speed", "cruise_speed"):
        lower, upper = bounds.get(metric, (None, None))
        candidate = lower if lower is not None else upper
        if candidate is not None:
            speed = candidate
            break
    if span_limit is None or volume_limit is None or speed is None:
        provenance = _provenance(compiled, "lifting-body", "planform-volume-sweep", assumptions)
        return SeamResult(
            architecture_type="lifting_body",
            available=False,
            reason=(
                "LIFTING_BODY_REQUIREMENTS_INCOMPLETE: "
                "span_limit, volume_limit, and max_speed required"
            ),
            seeds=(),
            blocking_issue=None,
            provenance=provenance,
        )

    provenance = _provenance(compiled, "lifting-body", "planform-volume-sweep", assumptions)
    try:
        span = Quantity(value=span_limit, unit="m")
        area = methods.planform_area(span, _LIFTING_BODY_ASPECT_RATIO)
        thickness = methods.thickness_ratio_from_volume(volume_limit, area.quantity, span)
        altitude = bounds.get("cruise_altitude", (None, None))
        cruise_altitude = altitude[0] if altitude[0] is not None else (altitude[1] or 0.0)
        speed_of_sound = methods.isa_speed_of_sound(Quantity(value=cruise_altitude, unit="m"))
        sweep = methods.sweep_drag_divergence(
            Quantity(value=speed, unit="m/s"),
            speed_of_sound.quantity,
            0.78,
            1.3962634015954636,
        )
    except (ValueError, SynthesisInfeasibleError) as error:
        return SeamResult(
            architecture_type="lifting_body",
            available=False,
            reason=f"LIFTING_BODY_SEAM_FAILED:{error}",
            seeds=(),
            blocking_issue=None,
            provenance=provenance,
        )

    quantities: tuple[SynthesisQuantity, ...] = (
        _rename(area, "lifting_body_planform_area"),
        _rename(thickness, "lifting_body_thickness_ratio"),
        _rename(sweep, "lifting_body_sweep"),
        methods.reference_quantity("span_limit", span),
        methods.reference_quantity("lifting_body_speed", Quantity(value=speed, unit="m/s")),
    )
    for quantity in quantities:
        if not quantity.validity.valid:
            return SeamResult(
                architecture_type="lifting_body",
                available=False,
                reason=f"LIFTING_BODY_VALIDITY_VIOLATION:{quantity.name}",
                seeds=(),
                blocking_issue=None,
                provenance=provenance,
            )

    seed = VehicleSeed(
        seed_id="lifting-body-00",
        architecture_type="lifting_body",
        quantities=quantities,
        provenance=provenance,
        assumptions=assumptions,
    )
    return SeamResult(
        architecture_type="lifting_body",
        available=True,
        reason="LIFTING_BODY_SEAM_AVAILABLE",
        seeds=(seed,),
        blocking_issue=None,
        provenance=provenance,
    )
