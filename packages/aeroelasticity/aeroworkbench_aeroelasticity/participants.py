"""Participant declarations for the generic aeroelastic layer.

Each aeroelastic capability declares typed output ports and their downstream
closure so modal, stability, forced-response, mistuning, gust, and contact
results couple into other analyses without product-specific assumptions. Native
requirements are declared explicitly and reported as capability-gated states.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import NativeRequirement, native_capability
from .errors import AeroelasticError

_PORT_TARGETS = frozenset(
    {"modal", "structural", "thermal", "stability", "cyclic", "gust", "contact"}
)


@dataclass(frozen=True, slots=True)
class PortSpec:
    """One typed scalar output port of an aeroelastic participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise AeroelasticError("participant.port.name is required")
        if not self.unit.strip():
            raise AeroelasticError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise AeroelasticError(f"participant.port.target unknown:{self.target}")

    def canonical_payload(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class AeroelasticParticipant:
    """One declared generic aeroelastic participant."""

    participant_id: str
    physics_domain: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[PortSpec, ...]
    native_requirement: NativeRequirement | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise AeroelasticError("participant.participant_id is required")
        if not self.outputs:
            raise AeroelasticError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[PortSpec, ...]:
        return tuple(port for port in self.outputs if port.target == target)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "participant_id": self.participant_id,
            "physics_domain": self.physics_domain,
            "fidelity_levels": list(self.fidelity_levels),
            "outputs": [port.canonical_payload() for port in self.outputs],
            "native_requirement": (
                self.native_requirement.value if self.native_requirement else None
            ),
        }


AEROELASTIC_PARTICIPANTS: tuple[AeroelasticParticipant, ...] = (
    AeroelasticParticipant(
        participant_id="modal-coupling",
        physics_domain="aeroelasticity",
        fidelity_levels=("reduced",),
        outputs=(
            PortSpec("generalized_force_n", "N", "modal"),
            PortSpec("modal_participation", "dimensionless", "modal"),
        ),
    ),
    AeroelasticParticipant(
        participant_id="flutter-stability",
        physics_domain="aeroelasticity",
        fidelity_levels=("screening", "harmonic", "transient_fsi"),
        outputs=(
            PortSpec("critical_speed_m_s", "m/s", "stability"),
            PortSpec("damping_ratio", "dimensionless", "stability"),
            PortSpec("growth_rate_1_s", "1/s", "stability"),
        ),
        native_requirement=NativeRequirement.PK_FLUTTER,
    ),
    AeroelasticParticipant(
        participant_id="forced-response",
        physics_domain="aeroelasticity",
        fidelity_levels=("harmonic",),
        outputs=(
            PortSpec("response_amplitude_m", "m", "structural"),
            PortSpec("dynamic_load_n", "N", "structural"),
            PortSpec("amplification", "dimensionless", "structural"),
        ),
    ),
    AeroelasticParticipant(
        participant_id="mistuning-cyclic",
        physics_domain="aeroelasticity",
        fidelity_levels=("reduced",),
        outputs=(
            PortSpec("localized_mode_frequency_hz", "Hz", "cyclic"),
            PortSpec("localization_factor", "dimensionless", "cyclic"),
        ),
    ),
    AeroelasticParticipant(
        participant_id="gust-load",
        physics_domain="aeroelasticity",
        fidelity_levels=("screening", "reduced"),
        outputs=(
            PortSpec("gust_load_increment_n", "N", "gust"),
            PortSpec("load_factor_increment", "dimensionless", "gust"),
        ),
    ),
    AeroelasticParticipant(
        participant_id="contact-rub",
        physics_domain="aeroelasticity",
        fidelity_levels=("screening", "transient_fsi"),
        outputs=(
            PortSpec("contact_force_n", "N", "contact"),
            PortSpec("rub_heat_generation_w", "W", "thermal"),
        ),
        native_requirement=NativeRequirement.CONTACT_FEA,
    ),
)


def aeroelastic_participants() -> tuple[AeroelasticParticipant, ...]:
    """Return the declared generic aeroelastic participants."""

    return AEROELASTIC_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in AEROELASTIC_PARTICIPANTS)


def participant_native_states() -> tuple[dict[str, object], ...]:
    """Report the capability-gated state of every declared native requirement."""

    seen: set[NativeRequirement] = set()
    states: list[dict[str, object]] = []
    for participant in AEROELASTIC_PARTICIPANTS:
        requirement = participant.native_requirement
        if requirement is None or requirement in seen:
            continue
        seen.add(requirement)
        states.append(native_capability(requirement).canonical())
    return tuple(states)


__all__ = [
    "AEROELASTIC_PARTICIPANTS",
    "AeroelasticParticipant",
    "PortSpec",
    "aeroelastic_participants",
    "participant_ids",
    "participant_native_states",
]
