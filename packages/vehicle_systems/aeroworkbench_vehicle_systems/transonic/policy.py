"""Compressible external-aero fidelity policy and native-promotion rules."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization import (
    FidelityImplementation,
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)

from .errors import TransonicContractError
from .regime import (
    INCOMPRESSIBLE_MAX_MACH,
    TRANSONIC_MAX_MACH,
    assert_not_hypersonic,
    classify_regime,
)

__all__ = [
    "COMPRESSIBLE_LADDER",
    "THERMAL_COUPLING_MIN_MACH",
    "Escalation",
    "PromotionRequirement",
    "escalation_for_mach",
    "heating_seam_required",
    "plan_compressible_fidelity",
    "promotion_for",
]

COMPRESSIBLE_LADDER: tuple[FidelityImplementation, ...] = (
    FidelityImplementation(
        name="incompressible",
        rank=0,
        cost=0.0,
        capabilities=("screening", "vlm-compatible"),
        description="incompressible VLM/analytic screening below M 0.3",
    ),
    FidelityImplementation(
        name="corrected",
        rank=1,
        cost=0.1,
        capabilities=("screening", "compressibility-correction"),
        description="Prandtl-Glauert/Karman-Tsien/Laitone corrected screening",
    ),
    FidelityImplementation(
        name="transonic_screening",
        rank=2,
        cost=1.0,
        capabilities=("screening", "drag-rise", "area-rule"),
        description="Korn drag-rise and area-rule screening without shock location",
    ),
    FidelityImplementation(
        name="supersonic_screening",
        rank=3,
        cost=1.0,
        capabilities=("screening", "ackeret", "sears-haack"),
        description="linearized supersonic and slender-body wave-drag screening",
    ),
    FidelityImplementation(
        name="rans_cfd",
        rank=4,
        cost=10.0,
        capabilities=("native", "shock-location", "wave-drag"),
        description="governed native compressible RANS CFD (capability-gated)",
    ),
)

THERMAL_COUPLING_MIN_MACH = 3.0


def plan_compressible_fidelity(current: str, signals: FidelitySignals) -> FidelityPlan:
    """Plan one compressible-aero fidelity step with explainable rules."""

    return plan_fidelity(current, COMPRESSIBLE_LADDER, signals)


@dataclass(frozen=True, slots=True)
class Escalation:
    """Deterministic fidelity escalation for one Mach and divergence state."""

    mach: float
    required_fidelity: str
    escalate: bool
    needs_native: bool
    reason: str

    def canonical(self) -> dict[str, Any]:
        return {
            "mach": self.mach,
            "requiredFidelity": self.required_fidelity,
            "escalate": self.escalate,
            "needsNative": self.needs_native,
            "reason": self.reason,
        }


def escalation_for_mach(
    mach: float, divergence_mach: float | None = None, shock_sensitive: bool = False
) -> Escalation:
    """Map Mach (and optional divergence state) to the minimum valid fidelity."""

    value = assert_not_hypersonic(mach)
    if not isfinite(value) or value < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    if divergence_mach is not None and (not isfinite(divergence_mach) or divergence_mach <= 0.0):
        raise TransonicContractError(f"INVALID_DIVERGENCE_MACH:{divergence_mach!r}")
    regime = classify_regime(value)
    near_divergence = divergence_mach is not None and value > divergence_mach - 0.02
    if shock_sensitive or near_divergence:
        return Escalation(
            value, "rans_cfd", True, True, "shock-sensitive:trust native RANS,not screening"
        )
    if value < INCOMPRESSIBLE_MAX_MACH:
        return Escalation(value, "incompressible", False, False, "M<0.3:no correction invoked")
    if value <= 0.85:
        return Escalation(value, "corrected", False, False, "declared correction band")
    if value < TRANSONIC_MAX_MACH or regime.name == "TRANSONIC":
        return Escalation(
            value, "transonic_screening", True, False, "drag-rise screening below sonic"
        )
    return Escalation(
        value, "supersonic_screening", True, False, "linearized supersonic screening"
    )


@dataclass(frozen=True, slots=True)
class PromotionRequirement:
    """Native-promotion verdict with required mesh/model/thermal settings."""

    needs_native: bool
    reason: str
    mesh_requirement: str
    turbulence_requirement: str
    thermal_coupling_required: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "needsNative": self.needs_native,
            "reason": self.reason,
            "meshRequirement": self.mesh_requirement,
            "turbulenceRequirement": self.turbulence_requirement,
            "thermalCouplingRequired": self.thermal_coupling_required,
        }


def promotion_for(
    mach: float, shock_sensitive: bool, divergence_mach: float | None = None
) -> PromotionRequirement:
    """Decide native RANS promotion and the mesh/model settings it requires."""

    escalation = escalation_for_mach(mach, divergence_mach, shock_sensitive)
    thermal = heating_seam_required(escalation.mach)
    if escalation.needs_native:
        return PromotionRequirement(
            True,
            escalation.reason,
            "shock-aware refinement via the ADV-PHYS 14 meshing adaptation seam",
            "declared RANS closure from the ADV-PHYS 12 turbulence registry",
            thermal,
        )
    return PromotionRequirement(
        False,
        escalation.reason,
        "no shock-aware refinement required at screening fidelity",
        "no RANS closure required at screening fidelity",
        thermal,
    )


def heating_seam_required(mach: float) -> bool:
    """Whether the heating/high-temperature coupling seam is required (M >= 3)."""

    value = assert_not_hypersonic(mach)
    if not isfinite(value) or value < 0.0:
        raise TransonicContractError(f"INVALID_MACH:{mach!r}")
    return bool(value >= THERMAL_COUPLING_MIN_MACH)
