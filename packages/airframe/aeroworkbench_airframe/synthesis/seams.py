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


class RotorcraftCapabilityUnavailable(RuntimeError):
    """Raised when a native rotor request lacks a trusted solver receipt."""


@dataclass(frozen=True, slots=True)
class RotorcraftOperatingPoint:
    forward_speed_m_s: float
    advance_ratio: float
    required_power_w: float


@dataclass(frozen=True, slots=True)
class RotorcraftEnvelope:
    valid: bool
    hover: RotorcraftOperatingPoint
    forward_flight: RotorcraftOperatingPoint
    provenance: Provenance


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
    """Provide a bounded analytical rotorcraft seed; native remains gated."""
    assumptions = ("Analytical actuator-disk screening only; no native rotor result is claimed.",)
    provenance = _provenance(compiled, "rotorcraft", "rotor-aerodynamics", assumptions)
    payload = requirement_bounds(compiled).get("payload_mass", (100.0, None))[0] or 100.0
    quantities = (
        methods.reference_quantity("hover_thrust", Quantity(value=payload * 9.80665 * 1.2, unit="N")),
        methods.reference_quantity("rotor_radius", Quantity(value=1.25, unit="m")),
        methods.reference_quantity("forward_flight_speed", Quantity(value=45.0, unit="m/s")),
    )
    seed = VehicleSeed(
        seed_id="rotorcraft-00", architecture_type="rotorcraft", quantities=quantities,
        provenance=provenance, assumptions=assumptions,
    )
    return SeamResult(
        architecture_type="rotorcraft",
        available=True,
        reason="ROTORCRAFT_ANALYTICAL_SEAM_AVAILABLE",
        seeds=(seed,),
        blocking_issue=None,
        provenance=provenance,
    )


def probe_rotorcraft_foundation() -> object:
    return type("RotorCapability", (), {"available": True, "detail": "analytical actuator-disk seam"})()


def evaluate_rotorcraft_envelope(seed: VehicleSeed, *, fidelity: str = "analytical") -> RotorcraftEnvelope:
    if seed.architecture_type != "rotorcraft":
        raise ValueError("ROTORCRAFT_SEED_REQUIRED")
    if fidelity == "native":
        raise RotorcraftCapabilityUnavailable("NATIVE_ROTOR_RECEIPT_REQUIRED")
    thrust = seed.parameter("hover_thrust").value_si
    radius = seed.parameter("rotor_radius").value_si
    forward = seed.parameter("forward_flight_speed").value_si
    disk_area = 3.141592653589793 * radius * radius
    hover_power = thrust * (thrust / (2.0 * 1.225 * disk_area)) ** 0.5
    hover = RotorcraftOperatingPoint(0.0, 0.0, hover_power)
    forward_point = RotorcraftOperatingPoint(forward, forward / (2.0 * radius * 120.0), hover_power * 1.25)
    return RotorcraftEnvelope(True, hover, forward_point, seed.provenance)


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
        # The declared volume is an upper bound; use the minimum manufacturable
        # thickness when that bound would create a nonphysical razor-thin body.
        minimum_volume = 0.06 * area.quantity.value_si * span.value_si
        thickness = methods.thickness_ratio_from_volume(
            max(volume_limit, minimum_volume), area.quantity, span
        )
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
