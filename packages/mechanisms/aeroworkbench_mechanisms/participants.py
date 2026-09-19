"""Participant declarations for the generic mechanical-interface components.

Each component declares typed output ports and their downstream closure
(structural, rotordynamic, thermal, fluid network, fatigue/life). This is the
seam by which component results couple into other analyses without encoding
any product-specific assumption. Native requirements are declared explicitly
and reported as capability-gated states that fail closed when absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .validity import CapabilityUnavailable, MechanismError

_PORT_TARGETS = frozenset({"structural", "rotordynamic", "thermal", "fluid", "fatigue"})


@dataclass(frozen=True, slots=True)
class PortSpec:
    """One typed scalar output port of a component participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MechanismError("participant.port.name is required")
        if not self.unit.strip():
            raise MechanismError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise MechanismError(f"participant.port.target unknown:{self.target}")

    def canonical_payload(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class ComponentParticipant:
    """One declared generic mechanical-interface participant."""

    participant_id: str
    component_kind: str
    physics_domain: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[PortSpec, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise MechanismError("participant.participant_id is required")
        if not self.outputs:
            raise MechanismError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.outputs if port.target == target)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "participant_id": self.participant_id,
            "component_kind": self.component_kind,
            "physics_domain": self.physics_domain,
            "fidelity_levels": list(self.fidelity_levels),
            "outputs": [port.canonical_payload() for port in self.outputs],
            "native_requirement": self.native_requirement,
        }


_STRUCTURAL = (
    PortSpec("stiffness_n_m", "N/m", "structural"),
    PortSpec("damping_n_s_m", "N*s/m", "structural"),
)

MECHANISM_PARTICIPANTS: tuple[ComponentParticipant, ...] = (
    ComponentParticipant(
        participant_id="mechanical-support",
        component_kind="support",
        physics_domain="structures",
        fidelity_levels=("analytical",),
        outputs=(
            *_STRUCTURAL,
            PortSpec("thermal_growth_m", "m", "thermal"),
        ),
    ),
    ComponentParticipant(
        participant_id="mechanical-joint",
        component_kind="joint",
        physics_domain="structures",
        fidelity_levels=("analytical",),
        outputs=(
            *_STRUCTURAL,
            PortSpec("heat_generation_w", "W", "thermal"),
            PortSpec("interface_load_n", "N", "fatigue"),
        ),
    ),
    ComponentParticipant(
        participant_id="rolling-bearing",
        component_kind="bearing",
        physics_domain="rotordynamics",
        fidelity_levels=("catalog",),
        outputs=(
            PortSpec("radial_stiffness_n_m", "N/m", "rotordynamic"),
            PortSpec("damping_n_s_m", "N*s/m", "rotordynamic"),
            PortSpec("heat_generation_w", "W", "thermal"),
            PortSpec("life_hours", "s", "fatigue"),
        ),
        native_requirement="ehl-bearing-stiffness",
    ),
    ComponentParticipant(
        participant_id="journal-bearing",
        component_kind="bearing",
        physics_domain="rotordynamics",
        fidelity_levels=("analytical",),
        outputs=(
            PortSpec("radial_stiffness_n_m", "N/m", "rotordynamic"),
            PortSpec("heat_generation_w", "W", "thermal"),
            PortSpec("min_film_thickness_m", "m", "fatigue"),
        ),
        native_requirement="ehl-bearing-stiffness",
    ),
    ComponentParticipant(
        participant_id="mechanical-seal",
        component_kind="seal",
        physics_domain="fluid-structure",
        fidelity_levels=("analytical",),
        outputs=(
            PortSpec("leakage_mass_flow_kg_s", "kg/s", "fluid"),
            PortSpec("heat_generation_w", "W", "thermal"),
        ),
    ),
    ComponentParticipant(
        participant_id="gear-mesh",
        component_kind="gear",
        physics_domain="powertrain",
        fidelity_levels=("analytical",),
        outputs=(
            PortSpec("mesh_stiffness_n_m", "N/m", "structural"),
            PortSpec("tangential_load_n", "N", "fatigue"),
            PortSpec("power_loss_w", "W", "thermal"),
        ),
        native_requirement="gear-contact-fea",
    ),
    ComponentParticipant(
        participant_id="tribology-contact",
        component_kind="contact",
        physics_domain="tribology",
        fidelity_levels=("analytical", "native"),
        outputs=(
            PortSpec("friction_power_w", "W", "thermal"),
            PortSpec("wear_depth_rate_m_s", "m/s", "fatigue"),
        ),
        native_requirement="contact-fea",
    ),
)


def mechanism_participants() -> tuple[ComponentParticipant, ...]:
    """Return the declared generic mechanical-interface participants."""

    return MECHANISM_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in MECHANISM_PARTICIPANTS)


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Capability-gated availability of a declared native requirement."""

    requirement: str
    state: str
    detail: str


def native_capability(requirement: str, *, present: bool = False) -> CapabilityState:
    """Report a native requirement; absent capability is explicitly blocked."""

    if not requirement.strip():
        raise MechanismError("capability.requirement is required")
    if present:
        return CapabilityState(requirement, "engine-present-not-wired", "engine present")
    return CapabilityState(
        requirement,
        "unavailable",
        f"{requirement} is not available; the native level fails closed",
    )


def require_native(requirement: str, *, present: bool = False) -> None:
    """Fail closed unless a wired native capability is declared present."""

    raise CapabilityUnavailable(native_capability(requirement, present=present).detail)


__all__ = [
    "MECHANISM_PARTICIPANTS",
    "CapabilityState",
    "ComponentParticipant",
    "PortSpec",
    "mechanism_participants",
    "native_capability",
    "participant_ids",
    "require_native",
]
