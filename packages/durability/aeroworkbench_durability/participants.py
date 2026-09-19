"""Participant declarations and capability-gated native durability seams.

Each durability participant declares typed output ports and their downstream
closure (structural, thermal, fatigue, life). Native structural/FEA
requirements are declared explicitly and reported as capability-gated states
that fail closed when absent; a requested native analysis is never replaced by
a screening model and relabelled complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .validity import CapabilityUnavailable, DurabilityError

_PORT_TARGETS = frozenset(
    {"structural", "thermal", "fatigue", "life", "fracture", "rotordynamic"}
)


@dataclass(frozen=True, slots=True)
class DurabilityPort:
    """One typed scalar output port of a durability participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DurabilityError("participant.port.name is required")
        if not self.unit.strip():
            raise DurabilityError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise DurabilityError(f"participant.port.target unknown:{self.target}")

    def canonical_payload(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class DurabilityParticipant:
    """One declared generic durability participant."""

    participant_id: str
    component_kind: str
    physics_domain: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[DurabilityPort, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise DurabilityError("participant.participant_id is required")
        if not self.outputs:
            raise DurabilityError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[DurabilityPort, ...]:
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


DURABILITY_PARTICIPANTS: tuple[DurabilityParticipant, ...] = (
    DurabilityParticipant(
        participant_id="high-cycle-fatigue",
        component_kind="fatigue",
        physics_domain="durability",
        fidelity_levels=("analytical", "catalog"),
        outputs=(
            DurabilityPort("damage", "1", "life"),
            DurabilityPort("life_cycles", "cycle", "life"),
        ),
        native_requirement="fatigue-fea",
    ),
    DurabilityParticipant(
        participant_id="low-cycle-fatigue",
        component_kind="fatigue",
        physics_domain="durability",
        fidelity_levels=("analytical",),
        outputs=(
            DurabilityPort("damage", "1", "life"),
            DurabilityPort("reversals_to_failure", "reversal", "life"),
        ),
        native_requirement="fatigue-fea",
    ),
    DurabilityParticipant(
        participant_id="creep-rupture",
        component_kind="creep",
        physics_domain="durability",
        fidelity_levels=("analytical", "catalog"),
        outputs=(
            DurabilityPort("rupture_fraction", "1", "life"),
            DurabilityPort("allowable_stress_pa", "Pa", "structural"),
        ),
        native_requirement="creep-fea",
    ),
    DurabilityParticipant(
        participant_id="crack-growth",
        component_kind="fracture",
        physics_domain="durability",
        fidelity_levels=("analytical",),
        outputs=(
            DurabilityPort("stress_intensity_pa_m05", "Pa*m^0.5", "fracture"),
            DurabilityPort("cycles_to_critical", "cycle", "life"),
        ),
        native_requirement="crack-growth-fea",
    ),
    DurabilityParticipant(
        participant_id="thermo-mechanical-fatigue",
        component_kind="fatigue",
        physics_domain="durability",
        fidelity_levels=("analytical",),
        outputs=(
            DurabilityPort("damage", "1", "life"),
            DurabilityPort("temperature_k", "K", "thermal"),
        ),
        native_requirement="thermo-mechanical-fea",
    ),
    DurabilityParticipant(
        participant_id="life-limited-part",
        component_kind="life-limited-part",
        physics_domain="durability",
        fidelity_levels=("analytical",),
        outputs=(
            DurabilityPort("utilization", "1", "life"),
            DurabilityPort("inspection_interval_cycles", "cycle", "life"),
        ),
    ),
    DurabilityParticipant(
        participant_id="composite-fatigue",
        component_kind="composite",
        physics_domain="durability",
        fidelity_levels=("analytical",),
        outputs=(DurabilityPort("damage", "1", "life"),),
        native_requirement="composite-damage-fea",
    ),
)


def durability_participants() -> tuple[DurabilityParticipant, ...]:
    """Return the declared generic durability participants."""

    return DURABILITY_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in DURABILITY_PARTICIPANTS)


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Capability-gated availability of a declared native requirement."""

    requirement: str
    state: str
    detail: str


def native_capability(requirement: str, *, present: bool = False) -> CapabilityState:
    """Report a native durability requirement; absent capability is blocked."""

    if not requirement.strip():
        raise DurabilityError("capability.requirement is required")
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


def solve_native_durability(
    analysis: str, *, solver_name: str | None = None, present: bool = False
) -> None:
    """Native durability execution seam; fails closed when the engine is absent."""

    if not analysis.strip():
        raise DurabilityError("native durability analysis name is required")
    detail = native_capability(analysis, present=present).detail
    if present and solver_name:
        detail = f"{analysis} native engine '{solver_name}' is not wired for execution"
    raise CapabilityUnavailable(detail)


__all__ = [
    "DURABILITY_PARTICIPANTS",
    "CapabilityState",
    "DurabilityParticipant",
    "DurabilityPort",
    "durability_participants",
    "native_capability",
    "participant_ids",
    "require_native",
    "solve_native_durability",
]
