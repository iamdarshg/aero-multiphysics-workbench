"""Participant declarations for generic propulsor components.

Each participant declares typed output ports and their downstream closure
(aerodynamics, structural, rotordynamic, thermal, propulsion, controls) so a
single/open/ducted propulsor shares the same coupling vocabulary. Native
requirements are declared explicitly and are capability-gated: they fail closed
when the engine is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .validity import AeroFidelity, PropulsorError

_PORT_TARGETS = frozenset(
    {"aerodynamics", "structural", "rotordynamic", "thermal", "propulsion", "controls"}
)


@dataclass(frozen=True, slots=True)
class PortSpec:
    """One typed scalar output port of a propulsor participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise PropulsorError("participant.port.name is required")
        if not self.unit.strip():
            raise PropulsorError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise PropulsorError(f"participant.port.target unknown:{self.target}")

    def canonical_payload(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class ComponentParticipant:
    """One declared generic propulsor participant."""

    participant_id: str
    component_kind: str
    physics_domain: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[PortSpec, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise PropulsorError("participant.participant_id is required")
        if not self.outputs:
            raise PropulsorError(f"participant {self.participant_id} has no outputs")

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


_AERO_OUTPUTS = (
    PortSpec("thrust_n", "N", "aerodynamics"),
    PortSpec("tip_mach", "dimensionless", "aerodynamics"),
)

PROPULSOR_PARTICIPANTS: tuple[ComponentParticipant, ...] = (
    ComponentParticipant(
        participant_id="propulsor-rotor",
        component_kind="rotor",
        physics_domain="aerodynamics",
        fidelity_levels=("actuator_disk", "blade_element_momentum"),
        outputs=(
            *_AERO_OUTPUTS,
            PortSpec("torque_n_m", "N*m", "rotordynamic"),
            PortSpec("power_w", "W", "propulsion"),
            PortSpec("induced_velocity_m_s", "m/s", "aerodynamics"),
        ),
        native_requirement="lifting-line-free-wake",
    ),
    ComponentParticipant(
        participant_id="propulsor-blade-row",
        component_kind="blade-row",
        physics_domain="geometry",
        fidelity_levels=("structured-surface", "brep"),
        outputs=(
            PortSpec("blade_count", "dimensionless", "controls"),
            PortSpec("diameter_m", "m", "controls"),
            PortSpec("axial_spacing_m", "m", "controls"),
        ),
        native_requirement="cad-kernel",
    ),
    ComponentParticipant(
        participant_id="propulsor-installation",
        component_kind="installation",
        physics_domain="installation",
        fidelity_levels=("analytical",),
        outputs=(
            PortSpec("normal_force_n", "N", "structural"),
            PortSpec("pitching_moment_n_m", "N*m", "structural"),
            PortSpec("slipstream_velocity_m_s", "m/s", "aerodynamics"),
        ),
    ),
    ComponentParticipant(
        participant_id="propulsor-control",
        component_kind="control",
        physics_domain="controls",
        fidelity_levels=("analytical",),
        outputs=(
            PortSpec("collective_pitch_deg", "deg", "controls"),
            PortSpec("blade_passing_frequency_hz", "s", "rotordynamic"),
        ),
    ),
)


def propulsor_participants() -> tuple[ComponentParticipant, ...]:
    """Return the declared generic propulsor participants."""

    return PROPULSOR_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in PROPULSOR_PARTICIPANTS)


def native_requirements() -> tuple[str, ...]:
    return tuple(
        participant.native_requirement
        for participant in PROPULSOR_PARTICIPANTS
        if participant.native_requirement is not None
    )


def declared_levels() -> tuple[AeroFidelity, ...]:
    return (AeroFidelity.ACTUATOR_DISK, AeroFidelity.BLADE_ELEMENT_MOMENTUM)


__all__ = [
    "PROPULSOR_PARTICIPANTS",
    "ComponentParticipant",
    "PortSpec",
    "declared_levels",
    "native_requirements",
    "participant_ids",
    "propulsor_participants",
]
