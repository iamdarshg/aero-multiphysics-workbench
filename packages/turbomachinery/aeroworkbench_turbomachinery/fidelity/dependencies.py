"""Multi-physics dependency graph: which analyses are relevant and which gate which.

Promotion requests only the participants the physics needs. Each participant
declares the analyses it delivers, the participants that must be satisfied
before it runs (its gates), and the condition under which it is relevant. Gate
closure guarantees a requested participant always brings its prerequisites;
acoustics and field-coupled analysis stay out unless requested or triggered.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from ..canonical import content_digest
from .features import ArchitectureFeatures
from .ladder import AnalysisKind

__all__ = [
    "CONDITIONS",
    "MultiphysicsDependencyGraph",
    "MultiphysicsParticipant",
    "default_multiphysics_graph",
]

CONDITIONS: tuple[str, ...] = (
    "always",
    "flow",
    "rotating",
    "work-extracting",
    "electrical",
    "thermal",
    "heat-addition",
    "acoustics-requested",
    "coupled-requested",
    "battery-requested",
)


@dataclass(frozen=True, slots=True)
class MultiphysicsParticipant:
    participant_id: str
    analyses: tuple[AnalysisKind, ...]
    gates: tuple[str, ...]
    condition: str
    capabilities: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise ValueError("PARTICIPANT_ID_REQUIRED")
        if not self.analyses:
            raise ValueError(f"PARTICIPANT_NEEDS_ANALYSES:{self.participant_id}")
        if self.condition not in CONDITIONS:
            raise ValueError(f"UNKNOWN_PARTICIPANT_CONDITION:{self.condition}")

    def canonical(self) -> dict[str, Any]:
        return {
            "participantId": self.participant_id,
            "analyses": sorted(item.value for item in self.analyses),
            "gates": list(self.gates),
            "condition": self.condition,
            "capabilities": list(self.capabilities),
            "description": self.description,
        }


def _condition_met(
    condition: str, features: ArchitectureFeatures, requested: frozenset[str]
) -> bool:
    if condition == "always":
        return True
    if condition == "flow":
        return features.has_flow
    if condition == "rotating":
        return features.has_rotating_rows
    if condition == "work-extracting":
        return (
            features.is_work_extracting
            or features.is_free_power
            or features.has_mechanical_load
        )
    if condition == "electrical":
        return features.is_electrically_driven or features.has_generator
    if condition == "thermal":
        return (
            features.has_heat_addition
            or features.is_electrically_driven
            or AnalysisKind.THERMAL.value in requested
        )
    if condition == "heat-addition":
        return features.has_combustion
    if condition == "acoustics-requested":
        return features.acoustics_requested or AnalysisKind.ACOUSTICS.value in requested
    if condition == "coupled-requested":
        return bool(
            requested
            & {
                AnalysisKind.FIELD_COUPLING.value,
                AnalysisKind.THERMAL.value,
                AnalysisKind.STRUCTURAL.value,
                "cht",
                "fsi",
            }
        )
    if condition == "battery-requested":
        return AnalysisKind.BATTERY.value in requested
    raise ValueError(f"UNKNOWN_PARTICIPANT_CONDITION:{condition}")


@dataclass(frozen=True, slots=True)
class MultiphysicsDependencyGraph:
    participants: tuple[MultiphysicsParticipant, ...]
    graph_id: str = "rotating-gas-multiphysics-graph"

    def __post_init__(self) -> None:
        if not self.graph_id.strip():
            raise ValueError("MULTIPHYSICS_GRAPH_ID_REQUIRED")
        if not self.participants:
            raise ValueError("MULTIPHYSICS_GRAPH_NEEDS_PARTICIPANTS")
        identifiers = [item.participant_id for item in self.participants]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("MULTIPHYSICS_GRAPH_DUPLICATE_PARTICIPANT")
        known = set(identifiers)
        for item in self.participants:
            for gate in item.gates:
                if gate not in known:
                    raise ValueError(f"UNKNOWN_PARTICIPANT_GATE:{item.participant_id}:{gate}")
                if gate == item.participant_id:
                    raise ValueError(f"PARTICIPANT_SELF_GATE:{item.participant_id}")
        self.topological_order()

    def participant(self, participant_id: str) -> MultiphysicsParticipant:
        for item in self.participants:
            if item.participant_id == participant_id:
                return item
        raise ValueError(f"UNKNOWN_PARTICIPANT:{participant_id}")

    def topological_order(self) -> tuple[str, ...]:
        index = {item.participant_id: position for position, item in enumerate(self.participants)}
        state: dict[str, str] = {}
        order: list[str] = []

        def visit(participant_id: str) -> None:
            current = state.get(participant_id)
            if current == "done":
                return
            if current == "visiting":
                raise ValueError(f"MULTIPHYSICS_GRAPH_CYCLE:{participant_id}")
            state[participant_id] = "visiting"
            gates = sorted(
                self.participant(participant_id).gates, key=lambda gate: index[gate]
            )
            for gate in gates:
                visit(gate)
            state[participant_id] = "done"
            order.append(participant_id)

        for item in self.participants:
            visit(item.participant_id)
        return tuple(order)

    def required_ids(
        self,
        features: ArchitectureFeatures,
        requested: Collection[str] = (),
    ) -> tuple[str, ...]:
        requested_set = frozenset(requested)
        selected = {
            item.participant_id
            for item in self.participants
            if _condition_met(item.condition, features, requested_set)
        }
        frontier = list(selected)
        while frontier:
            participant_id = frontier.pop()
            for gate in self.participant(participant_id).gates:
                if gate not in selected:
                    selected.add(gate)
                    frontier.append(gate)
        return tuple(
            participant_id
            for participant_id in self.topological_order()
            if participant_id in selected
        )

    def participants_for(
        self,
        features: ArchitectureFeatures,
        requested: Collection[str] = (),
    ) -> tuple[MultiphysicsParticipant, ...]:
        return tuple(self.participant(item) for item in self.required_ids(features, requested))

    def canonical(self) -> dict[str, Any]:
        return {
            "graphId": self.graph_id,
            "participants": [item.canonical() for item in self.participants],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def default_multiphysics_graph() -> MultiphysicsDependencyGraph:
    """Canonical participant graph for generic rotating gas machinery."""
    return MultiphysicsDependencyGraph(
        participants=(
            MultiphysicsParticipant(
                "flow",
                (AnalysisKind.AERODYNAMIC_SCREENING, AnalysisKind.STEADY_RANS),
                (),
                "flow",
                ("screening",),
                "gas-path aerodynamic screening / steady flow",
            ),
            MultiphysicsParticipant(
                "throughflow",
                (AnalysisKind.THROUGHFLOW,),
                ("flow",),
                "flow",
                ("throughflow",),
                "reduced-order throughflow row matching",
            ),
            MultiphysicsParticipant(
                "shaft-load-balance",
                (AnalysisKind.SHAFT_LOAD_BALANCE,),
                ("flow",),
                "work-extracting",
                ("shaft-balance",),
                "shaft power/load balance",
            ),
            MultiphysicsParticipant(
                "electrical",
                (AnalysisKind.ELECTRICAL,),
                ("shaft-load-balance",),
                "electrical",
                ("electrical",),
                "motor/generator electrical drive",
            ),
            MultiphysicsParticipant(
                "battery",
                (AnalysisKind.BATTERY,),
                ("electrical",),
                "battery-requested",
                ("battery",),
                "battery/energy storage (requested)",
            ),
            MultiphysicsParticipant(
                "thermal",
                (AnalysisKind.THERMAL,),
                ("flow",),
                "thermal",
                ("thermal",),
                "thermal/conjugate heat transfer",
            ),
            MultiphysicsParticipant(
                "combustion",
                (AnalysisKind.COMBUSTION,),
                ("flow", "thermal"),
                "heat-addition",
                ("chemistry",),
                "combustion/chemistry for heat-addition architectures",
            ),
            MultiphysicsParticipant(
                "structure",
                (AnalysisKind.STRUCTURAL,),
                ("flow",),
                "rotating",
                ("structural",),
                "structural stress/durability",
            ),
            MultiphysicsParticipant(
                "rotordynamics",
                (AnalysisKind.ROTORDYNAMIC,),
                ("structure", "shaft-load-balance"),
                "rotating",
                ("rotordynamics", "resonance"),
                "rotordynamics/resonance",
            ),
            MultiphysicsParticipant(
                "acoustics",
                (AnalysisKind.ACOUSTICS,),
                ("flow",),
                "acoustics-requested",
                ("acoustics",),
                "acoustics/noise (only when requested or triggered)",
            ),
            MultiphysicsParticipant(
                "field-coupling",
                (AnalysisKind.FIELD_COUPLING,),
                ("thermal", "structure"),
                "coupled-requested",
                ("field-coupling",),
                "CHT/FSI field coupling (only when requested)",
            ),
        )
    )
