"""Declared structural participants and their typed output ports.

Each generative-structure capability declares typed output ports and their
downstream closure so a layout, a sizing pass, a margin table, and a
capability-gated native FEA result couple into mass, aeroelastic, and structural
loops without product-specific assumptions. Native requirements are declared
explicitly and reported as capability-gated states.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import StructuralContractError
from .native import native_structure_capability

__all__ = [
    "STRUCTURAL_PARTICIPANTS",
    "StructuralParticipant",
    "StructuralPort",
    "participant_ids",
    "participant_native_states",
    "structural_participants",
]

_PORT_TARGETS = frozenset(
    {"mass", "structural", "aeroelastic", "thermal", "optimization"}
)


@dataclass(frozen=True, slots=True)
class StructuralPort:
    """One typed scalar output port of a structural participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise StructuralContractError("participant.port.name is required")
        if not self.unit.strip():
            raise StructuralContractError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise StructuralContractError(f"participant.port.target unknown:{self.target}")

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class StructuralParticipant:
    """One declared generic generative-structure participant."""

    participant_id: str
    component_kind: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[StructuralPort, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise StructuralContractError("participant.participant_id is required")
        if not self.outputs:
            raise StructuralContractError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[StructuralPort, ...]:
        return tuple(port for port in self.outputs if port.target == target)

    def as_dict(self) -> dict[str, Any]:
        return {
            "participantId": self.participant_id,
            "componentKind": self.component_kind,
            "fidelityLevels": list(self.fidelity_levels),
            "outputs": [port.as_dict() for port in self.outputs],
            "nativeRequirement": self.native_requirement,
        }


STRUCTURAL_PARTICIPANTS: tuple[StructuralParticipant, ...] = (
    StructuralParticipant(
        participant_id="generative-layout",
        component_kind="airframe-structure",
        fidelity_levels=("analytical",),
        outputs=(
            StructuralPort("member_count", "1", "structural"),
            StructuralPort("architecture_digest", "1", "optimization"),
        ),
    ),
    StructuralParticipant(
        participant_id="preliminary-sizing",
        component_kind="airframe-structure",
        fidelity_levels=("analytical",),
        outputs=(
            StructuralPort("structural_mass_kg", "kg", "mass"),
            StructuralPort("bending_stiffness_n_m2", "N.m2", "aeroelastic"),
            StructuralPort("torsional_stiffness_n_m2", "N.m2", "aeroelastic"),
            StructuralPort("first_bending_frequency_hz", "Hz", "aeroelastic"),
            StructuralPort("tip_deflection_m", "m", "structural"),
        ),
    ),
    StructuralParticipant(
        participant_id="structural-margins",
        component_kind="airframe-structure",
        fidelity_levels=("analytical",),
        outputs=(
            StructuralPort("minimum_margin", "1", "structural"),
            StructuralPort("strength_margin", "1", "structural"),
            StructuralPort("buckling_margin", "1", "structural"),
        ),
    ),
    StructuralParticipant(
        participant_id="native-structure-fea",
        component_kind="airframe-structure",
        fidelity_levels=("native",),
        outputs=(
            StructuralPort("displacement_m", "m", "structural"),
            StructuralPort("element_stress_pa", "Pa", "structural"),
        ),
        native_requirement="code-aster-shell-beam",
    ),
)


def structural_participants() -> tuple[StructuralParticipant, ...]:
    """Return the declared generic structural participants."""

    return STRUCTURAL_PARTICIPANTS


def participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in STRUCTURAL_PARTICIPANTS)


def participant_native_states() -> tuple[dict[str, Any], ...]:
    """Report the capability-gated state of every declared native requirement."""

    seen: set[str] = set()
    states: list[dict[str, Any]] = []
    for participant in STRUCTURAL_PARTICIPANTS:
        requirement = participant.native_requirement
        if requirement is None or requirement in seen:
            continue
        seen.add(requirement)
        states.append(native_structure_capability(requirement).as_dict())
    return tuple(states)
