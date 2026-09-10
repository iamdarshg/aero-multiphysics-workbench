"""preCICE configuration and restart lifecycle contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True, slots=True)
class InterfaceField:
    name: str
    quantity: str
    write: str
    read: str


@dataclass(frozen=True, slots=True)
class PreciceConfig:
    xml: str
    digest_sha256: str
    participant_names: tuple[str, ...]
    mapping: str
    coupling_dt: float
    max_iterations: int


@dataclass(frozen=True, slots=True)
class MappingReceipt:
    state: str
    mapping: str
    relative_conservation_error: float
    tolerance: float
    detail: str


@dataclass(frozen=True, slots=True)
class RestartEvent:
    sequence: int
    kind: str
    checkpoint: str
    reason: str


class CouplingSession:
    """Small state machine for checkpoint, rollback, and accepted steps."""

    def __init__(self) -> None:
        self._events: list[RestartEvent] = []
        self._step = 0

    def checkpoint(self, checkpoint: str) -> RestartEvent:
        if not checkpoint:
            raise ValueError("CHECKPOINT_REQUIRED")
        event = RestartEvent(len(self._events) + 1, "checkpoint", checkpoint, "accepted state")
        self._events.append(event)
        return event

    def rollback(self, checkpoint: str, reason: str) -> RestartEvent:
        if not checkpoint or not reason:
            raise ValueError("ROLLBACK_FIELDS_REQUIRED")
        event = RestartEvent(len(self._events) + 1, "rollback", checkpoint, reason)
        self._events.append(event)
        return event

    def accept_step(self) -> int:
        self._step += 1
        return self._step

    def events(self) -> tuple[RestartEvent, ...]:
        return tuple(self._events)


def build_precice_config(
    *,
    participants: tuple[str, ...] = ("fluid", "structure"),
    fields: tuple[InterfaceField, ...] = (
        InterfaceField("Pressure", "scalar", "fluid", "structure"),
        InterfaceField("Displacement", "vector", "structure", "fluid"),
        InterfaceField("Temperature", "scalar", "fluid", "structure"),
        InterfaceField("Heat-Flux", "scalar", "structure", "fluid"),
    ),
    mapping: str = "conservative",
    coupling_dt: float = 1e-3,
    max_iterations: int = 50,
    tolerance: float = 1e-6,
) -> PreciceConfig:
    """Build a stable implicit quasi-Newton configuration."""

    if len(participants) < 2 or any(not participant for participant in participants):
        raise ValueError("PARTICIPANTS_REQUIRED")
    if len(set(participants)) != len(participants):
        raise ValueError("DUPLICATE_PARTICIPANT")
    if mapping not in {"conservative", "consistent"}:
        raise ValueError("MAPPING_NOT_SUPPORTED")
    if coupling_dt <= 0 or max_iterations <= 0 or tolerance <= 0 or not fields:
        raise ValueError("INVALID_COUPLING_SETTINGS")
    if any(field.write not in participants or field.read not in participants for field in fields):
        raise ValueError("FIELD_PARTICIPANT_NOT_DECLARED")
    root = ElementTree.Element("precice-configuration", {"coupling-scheme": "implicit"})
    participant_node = ElementTree.SubElement(root, "participants")
    for participant in participants:
        ElementTree.SubElement(participant_node, "participant", {"name": participant})
    meshes = ElementTree.SubElement(root, "meshes")
    ElementTree.SubElement(meshes, "mesh", {"name": "fluid-interface", "dimensions": "3"})
    data = ElementTree.SubElement(root, "data")
    for field in fields:
        ElementTree.SubElement(data, "data-field", {"name": field.name, "type": field.quantity})
    scheme = ElementTree.SubElement(root, "coupling-scheme", {"type": "implicit"})
    ElementTree.SubElement(scheme, "time-window-size", {"value": str(coupling_dt)})
    ElementTree.SubElement(scheme, "max-iterations", {"value": str(max_iterations)})
    ElementTree.SubElement(scheme, "relative-convergence-measure", {"limit": str(tolerance)})
    ElementTree.SubElement(scheme, "quasi-newton", {"mapping": mapping, "type": "IQN-ILS"})
    xml = ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)
    digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()
    return PreciceConfig(xml, digest, participants, mapping, coupling_dt, max_iterations)


def verify_mapping(
    *, mapping: str, relative_conservation_error: float, tolerance: float = 1e-6
) -> MappingReceipt:
    if (
        mapping not in {"conservative", "consistent"}
        or relative_conservation_error < 0
        or tolerance <= 0
    ):
        raise ValueError("INVALID_MAPPING_RECEIPT")
    accepted = relative_conservation_error <= tolerance
    return MappingReceipt(
        "completed" if accepted else "failed",
        mapping,
        relative_conservation_error,
        tolerance,
        "conservation within tolerance"
        if accepted
        else "interface conservation exceeded tolerance",
    )
