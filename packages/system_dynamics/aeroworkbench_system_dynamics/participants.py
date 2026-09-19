"""Participant declarations for generic transient system-dynamics components.

Each component declares typed output ports and their downstream closure
(fatigue, thermal, controls, structures, electrical, fluid). This is the seam
by which transient time histories couple into other analyses without encoding
any product-specific assumption. Native requirements are declared explicitly
and reported as capability-gated states that fail closed when absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import TransientValidationError

_PORT_TARGETS = frozenset(
    {"fatigue", "thermal", "controls", "structural", "electrical", "fluid", "dynamics"}
)


@dataclass(frozen=True, slots=True)
class PortSpec:
    """One typed scalar output port of a transient component participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise TransientValidationError("participant.port.name is required")
        if not self.unit.strip():
            raise TransientValidationError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise TransientValidationError(f"participant.port.target unknown:{self.target}")

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class SystemParticipant:
    """One declared generic transient system-dynamics participant."""

    participant_id: str
    component_kind: str
    physics_domain: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[PortSpec, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise TransientValidationError("participant.participant_id is required")
        if not self.outputs:
            raise TransientValidationError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.outputs if port.target == target)

    def canonical(self) -> dict[str, Any]:
        return {
            "participantId": self.participant_id,
            "componentKind": self.component_kind,
            "physicsDomain": self.physics_domain,
            "fidelityLevels": list(self.fidelity_levels),
            "outputs": [port.canonical() for port in self.outputs],
            "nativeRequirement": self.native_requirement,
        }


SYSTEM_DYNAMICS_PARTICIPANTS: tuple[SystemParticipant, ...] = (
    SystemParticipant(
        participant_id="transient-shaft-spool",
        component_kind="rotational-inertia",
        physics_domain="dynamics",
        fidelity_levels=("transient",),
        outputs=(
            PortSpec("shaft_speed_rad_s", "rad/s", "controls"),
            PortSpec("shaft_acceleration_rad_s2", "rad/s2", "fatigue"),
            PortSpec("shaft_torque_n_m", "N*m", "structural"),
        ),
    ),
    SystemParticipant(
        participant_id="transient-storage-volume",
        component_kind="storage",
        physics_domain="fluid",
        fidelity_levels=("transient",),
        outputs=(
            PortSpec("pressure_pa", "Pa", "fluid"),
            PortSpec("net_mass_flow_kg_s", "kg/s", "fluid"),
        ),
    ),
    SystemParticipant(
        participant_id="transient-thermal-capacitance",
        component_kind="thermal-capacitance",
        physics_domain="thermal",
        fidelity_levels=("transient",),
        outputs=(
            PortSpec("temperature_k", "K", "thermal"),
            PortSpec("heat_rejection_w", "W", "thermal"),
        ),
    ),
    SystemParticipant(
        participant_id="transient-electrical-storage",
        component_kind="battery",
        physics_domain="electrical",
        fidelity_levels=("transient",),
        outputs=(
            PortSpec("state_of_charge", "1", "electrical"),
            PortSpec("pack_voltage_v", "V", "electrical"),
        ),
    ),
    SystemParticipant(
        participant_id="transient-actuator",
        component_kind="actuator",
        physics_domain="controls",
        fidelity_levels=("transient",),
        outputs=(
            PortSpec("position_m", "m", "controls"),
            PortSpec("rate_m_s", "m/s", "controls"),
            PortSpec("actuator_force_n", "N", "structural"),
        ),
    ),
    SystemParticipant(
        participant_id="protection-supervisor",
        component_kind="protection",
        physics_domain="controls",
        fidelity_levels=("transient",),
        outputs=(
            PortSpec("trip_flag", "1", "controls"),
            PortSpec("safe_command", "1", "controls"),
            PortSpec("limit_margin", "1", "controls"),
        ),
        native_requirement="implicit-dae-transient-coordinator",
    ),
)


def system_participants() -> tuple[SystemParticipant, ...]:
    """Return the declared generic transient system-dynamics participants."""

    return SYSTEM_DYNAMICS_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in SYSTEM_DYNAMICS_PARTICIPANTS)


__all__ = [
    "SYSTEM_DYNAMICS_PARTICIPANTS",
    "PortSpec",
    "SystemParticipant",
    "participant_ids",
    "system_participants",
]
