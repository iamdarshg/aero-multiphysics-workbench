"""Participant declarations and native capability gating.

Each generic environmental participant declares typed output ports and their
downstream closure (geometry, structural, performance, thermal, life). Native
requirements (icing CFD, impact structural FEA, corrosion life model, particle
erosion CFD) are declared explicitly and reported as capability-gated states
that fail closed when absent. No product-specific assumption is encoded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import CapabilityUnavailable, EnvironmentalError

_PORT_TARGETS = frozenset({"geometry", "structural", "performance", "thermal", "life"})


@dataclass(frozen=True, slots=True)
class PortSpec:
    """One typed scalar output port of an environmental participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise EnvironmentalError("participant.port.name is required")
        if not self.unit.strip():
            raise EnvironmentalError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise EnvironmentalError(f"participant.port.target unknown:{self.target}")

    def canonical_payload(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class EnvironmentalParticipant:
    """One declared generic environmental participant."""

    participant_id: str
    component_kind: str
    physics_domain: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[PortSpec, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise EnvironmentalError("participant.participantId is required")
        if not self.outputs:
            raise EnvironmentalError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.outputs if port.target == target)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "participantId": self.participant_id,
            "componentKind": self.component_kind,
            "physicsDomain": self.physics_domain,
            "fidelityLevels": list(self.fidelity_levels),
            "outputs": [port.canonical_payload() for port in self.outputs],
            "nativeRequirement": self.native_requirement,
        }


ENVIRONMENTAL_PARTICIPANTS: tuple[EnvironmentalParticipant, ...] = (
    EnvironmentalParticipant(
        participant_id="ice-accretion",
        component_kind="icing",
        physics_domain="fluid-thermal",
        fidelity_levels=("envelope", "geometry", "native"),
        outputs=(
            PortSpec("ice_thickness_m", "m", "geometry"),
            PortSpec("leading_edge_roughness_m", "m", "performance"),
            PortSpec("accreted_areal_mass_kg_m2", "kg/m2", "structural"),
        ),
        native_requirement="ice-accretion-cfd",
    ),
    EnvironmentalParticipant(
        participant_id="surface-contamination",
        component_kind="contamination",
        physics_domain="surface",
        fidelity_levels=("envelope",),
        outputs=(
            PortSpec("deposit_thickness_m", "m", "geometry"),
            PortSpec("blocked_area_fraction", "dimensionless", "performance"),
        ),
    ),
    EnvironmentalParticipant(
        participant_id="surface-erosion",
        component_kind="erosion",
        physics_domain="surface",
        fidelity_levels=("envelope", "native"),
        outputs=(
            PortSpec("material_loss_depth_m", "m", "geometry"),
            PortSpec("erosion_rate_m_s", "m/s", "life"),
        ),
        native_requirement="particle-erosion-cfd",
    ),
    EnvironmentalParticipant(
        participant_id="foreign-object-impact",
        component_kind="fod",
        physics_domain="structures",
        fidelity_levels=("envelope", "native"),
        outputs=(
            PortSpec("kinetic_energy_j", "J", "structural"),
            PortSpec("footprint_area_m2", "m2", "structural"),
        ),
        native_requirement="impact-structural-fea",
    ),
    EnvironmentalParticipant(
        participant_id="corrosive-exposure",
        component_kind="corrosion",
        physics_domain="materials",
        fidelity_levels=("envelope", "native"),
        outputs=(
            PortSpec("strength_fraction_reduction", "dimensionless", "structural"),
            PortSpec("material_loss_depth_m", "m", "life"),
        ),
        native_requirement="corrosion-life-model",
    ),
)


def environmental_participants() -> tuple[EnvironmentalParticipant, ...]:
    """Return the declared generic environmental participants."""

    return ENVIRONMENTAL_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in ENVIRONMENTAL_PARTICIPANTS)


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Capability-gated availability of a declared native requirement."""

    requirement: str
    state: str
    detail: str

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def canonical(self) -> dict[str, str]:
        return {"requirement": self.requirement, "state": self.state, "detail": self.detail}


def native_environmental_capability(
    requirement: str, *, present: bool = False
) -> CapabilityState:
    """Report a native requirement; absent capability is explicitly blocked."""

    if not requirement.strip():
        raise EnvironmentalError("capability.requirement is required")
    if present:
        return CapabilityState(requirement, "ready", f"{requirement} engine wired")
    return CapabilityState(
        requirement,
        "unavailable",
        f"{requirement} is not available; the native level fails closed",
    )


def require_native_environmental(requirement: str, *, present: bool = False) -> CapabilityState:
    """Fail closed unless a wired native capability is declared present."""

    capability = native_environmental_capability(requirement, present=present)
    if not capability.available:
        raise CapabilityUnavailable(capability.detail)
    return capability


__all__ = [
    "ENVIRONMENTAL_PARTICIPANTS",
    "CapabilityState",
    "EnvironmentalParticipant",
    "PortSpec",
    "environmental_participants",
    "native_environmental_capability",
    "participant_ids",
    "require_native_environmental",
]
