"""preCICE configuration and restart lifecycle contracts."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from xml.etree import ElementTree

from .units import units_compatible


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


# -- generic field-coupling contract -----------------------------------------
#
# The M3 contract above describes a fixed two-participant pressure/displacement
# configuration. The GEN 11 contract is manifest-driven: participants declare
# typed field ports, ``DomainInterface`` declarations bind two participants and
# the fields exchanged across them, and the catalog below supplies the native
# data type plus the default mapping kernel for the well-known interface
# quantities. Unknown quantities are allowed as long as they declare a type,
# so future fields never require application logic in this core.


class CouplingFailureCode(StrEnum):
    """Closed set of explicit field-coupling failure reasons."""

    PRECICE_UNAVAILABLE = "PRECICE_UNAVAILABLE"
    PARTICIPANT_UNAVAILABLE = "PARTICIPANT_UNAVAILABLE"
    INTERFACE_MISMATCH = "INTERFACE_MISMATCH"
    FIELD_UNIT_MISMATCH = "FIELD_UNIT_MISMATCH"
    MAPPING_FAILURE = "MAPPING_FAILURE"
    COUPLING_NONCONVERGENCE = "COUPLING_NONCONVERGENCE"
    CHECKPOINT_ROLLBACK_FAILURE = "CHECKPOINT_ROLLBACK_FAILURE"


class CouplingError(RuntimeError):
    """A field-coupling failure with a stable, explicit reason code."""

    def __init__(self, code: CouplingFailureCode, detail: str) -> None:
        if not detail.strip():
            raise ValueError("COUPLING_ERROR_DETAIL_REQUIRED")
        super().__init__(f"{code.value}:{detail}")
        self.code = code
        self.detail = detail


# quantity label -> (native data type, default mapping kernel)
FIELD_CATALOG: dict[str, tuple[str, str]] = {
    "pressure": ("scalar", "conservative"),
    "traction": ("vector", "conservative"),
    "displacement": ("vector", "consistent"),
    "temperature": ("scalar", "consistent"),
    "heat-flux": ("scalar", "conservative"),
}


@dataclass(frozen=True, slots=True)
class ParticipantView:
    """Field-port view of one participant manifest for coupling validation."""

    name: str
    physics_domain: str = "generic"
    field_inputs: tuple[tuple[str, str], ...] = ()
    field_outputs: tuple[tuple[str, str], ...] = ()


def participant_view(manifest: object) -> ParticipantView:
    """Adapt a ``ParticipantManifest`` into a lightweight coupling view."""

    field_inputs = tuple(
        (port.name, port.unit) for port in getattr(manifest, "field_inputs", ())
    )
    field_outputs = tuple(
        (port.name, port.unit) for port in getattr(manifest, "field_outputs", ())
    )
    return ParticipantView(
        name=str(getattr(manifest, "participant_id", "")),
        physics_domain=str(getattr(manifest, "physics_domain", "generic")),
        field_inputs=field_inputs,
        field_outputs=field_outputs,
    )


@dataclass(frozen=True, slots=True)
class CouplingField:
    """One declared scalar/vector exchange across a ``DomainInterface``."""

    name: str
    write: str
    read: str
    unit: str
    quantity: str = ""
    mapping: str = ""


@dataclass(frozen=True, slots=True)
class DomainInterface:
    """Declared field-coupling interface between two named participants."""

    name: str
    zone_a: str
    zone_b: str
    participant_a: str
    participant_b: str
    kind: str = "precice_interface"
    conformal: bool = False
    fields: tuple[CouplingField, ...] = ()


@dataclass(frozen=True, slots=True)
class CouplingContract:
    """Manifest-backed preCICE contract plus its rendered native config."""

    participants: tuple[str, ...]
    interfaces: tuple[DomainInterface, ...]
    fields: tuple[CouplingField, ...]
    mapping: str
    coupling_dt: float
    max_iterations: int
    tolerance: float
    acceleration: str
    config: PreciceConfig


def _resolve_quantity(field: CouplingField) -> tuple[CouplingField, str, str]:
    entry = FIELD_CATALOG.get(field.name.lower())
    quantity = field.quantity or (entry[0] if entry else "")
    mapping = field.mapping or (entry[1] if entry else "conservative")
    if quantity not in {"scalar", "vector"} or not mapping:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH,
            f"UNKNOWN_FIELD:{field.name}: declare quantity/mapping for new fields",
        )
    if mapping not in {"conservative", "consistent"}:
        raise CouplingError(
            CouplingFailureCode.MAPPING_FAILURE, f"mapping not supported:{mapping}"
        )
    return (
        CouplingField(field.name, field.write, field.read, field.unit, quantity, mapping),
        quantity,
        mapping,
    )


def _check_unit(label: str, declared: str, port_unit: str) -> None:
    try:
        compatible = units_compatible(declared, port_unit)
    except ValueError:
        # An interface unit outside the shared table is carried verbatim.
        return
    if not compatible:
        raise CouplingError(
            CouplingFailureCode.FIELD_UNIT_MISMATCH,
            f"{label}: declared {declared} incompatible with manifest port {port_unit}",
        )


def _validate_manifest_units(
    field: CouplingField, manifests: Mapping[str, ParticipantView]
) -> None:
    writer = manifests.get(field.write)
    if writer is not None:
        for name, unit in writer.field_outputs:
            if name == field.name:
                _check_unit(f"{field.write}.{field.name}", field.unit, unit)
    reader = manifests.get(field.read)
    if reader is not None:
        for name, unit in reader.field_inputs:
            if name == field.name:
                _check_unit(f"{field.read}.{field.name}", field.unit, unit)


def build_coupling_contract(
    *,
    participants: Sequence[str],
    interfaces: Sequence[DomainInterface],
    manifests: Mapping[str, ParticipantView] | None = None,
    mapping: str = "conservative",
    coupling_dt: float = 1e-3,
    max_iterations: int = 50,
    tolerance: float = 1e-6,
    acceleration: str = "IQN-ILS",
) -> CouplingContract:
    """Build and validate a manifest-driven native preCICE contract."""

    names = tuple(participants)
    if len(names) < 2 or any(not name.strip() for name in names):
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH, "at least two participants required"
        )
    if len(set(names)) != len(names):
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH, "duplicate participant"
        )
    declared = set(names)
    for interface in interfaces:
        if (
            interface.participant_a not in declared
            or interface.participant_b not in declared
            or interface.participant_a == interface.participant_b
            or interface.zone_a == interface.zone_b
        ):
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH,
                f"interface {interface.name} endpoint not declared",
            )
    if not interfaces:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH, "no interfaces declared"
        )
    if mapping not in {"conservative", "consistent"}:
        raise CouplingError(
            CouplingFailureCode.MAPPING_FAILURE, f"mapping not supported:{mapping}"
        )
    if coupling_dt <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise CouplingError(
            CouplingFailureCode.INTERFACE_MISMATCH, "invalid coupling settings"
        )
    resolved_manifests = dict(manifests or {})
    all_fields: list[CouplingField] = []
    resolved_interfaces: list[DomainInterface] = []
    for interface in interfaces:
        if not interface.fields:
            raise CouplingError(
                CouplingFailureCode.INTERFACE_MISMATCH,
                f"interface {interface.name} declares no fields",
            )
        resolved_fields: list[CouplingField] = []
        for field in interface.fields:
            endpoints = {field.write, field.read}
            if endpoints != {interface.participant_a, interface.participant_b}:
                raise CouplingError(
                    CouplingFailureCode.INTERFACE_MISMATCH,
                    f"field {field.name} direction does not match {interface.name}",
                )
            field, _, _ = _resolve_quantity(field)
            _validate_manifest_units(field, resolved_manifests)
            resolved_fields.append(field)
            all_fields.append(field)
        resolved_interfaces.append(
            DomainInterface(
                interface.name,
                interface.zone_a,
                interface.zone_b,
                interface.participant_a,
                interface.participant_b,
                interface.kind,
                interface.conformal,
                tuple(resolved_fields),
            )
        )
    config = _render_contract_config(
        names,
        tuple(resolved_interfaces),
        tuple(all_fields),
        mapping=mapping,
        coupling_dt=coupling_dt,
        max_iterations=max_iterations,
        tolerance=tolerance,
        acceleration=acceleration,
    )
    return CouplingContract(
        names,
        tuple(resolved_interfaces),
        tuple(all_fields),
        mapping,
        coupling_dt,
        max_iterations,
        tolerance,
        acceleration,
        config,
    )


def _render_contract_config(
    participants: tuple[str, ...],
    interfaces: tuple[DomainInterface, ...],
    fields: tuple[CouplingField, ...],
    *,
    mapping: str,
    coupling_dt: float,
    max_iterations: int,
    tolerance: float,
    acceleration: str,
) -> PreciceConfig:
    root = ElementTree.Element("precice-configuration")
    participant_node = ElementTree.SubElement(root, "participants")
    meshes_node = ElementTree.SubElement(root, "meshes")
    data_node = ElementTree.SubElement(root, "data")
    seen_data: set[str] = set()
    for field in fields:
        if field.name in seen_data:
            continue
        seen_data.add(field.name)
        quantity = field.quantity or FIELD_CATALOG.get(field.name.lower(), ("scalar", ""))[0]
        ElementTree.SubElement(data_node, "data-field", {"name": field.name, "type": quantity})
    mesh_names: dict[str, str] = {}
    for interface in interfaces:
        for participant, zone in (
            (interface.participant_a, interface.zone_a),
            (interface.participant_b, interface.zone_b),
        ):
            mesh_name = f"{interface.name}:{zone}"
            mesh_names[f"{interface.name}:{participant}"] = mesh_name
            ElementTree.SubElement(
                meshes_node, "mesh", {"name": mesh_name, "dimensions": "3"}
            )
    for participant in participants:
        node = ElementTree.SubElement(participant_node, "participant", {"name": participant})
        for interface in interfaces:
            mesh_name = mesh_names[f"{interface.name}:{participant}"]
            ElementTree.SubElement(
                node, "use-mesh", {"name": mesh_name, "provide": "yes"}
            )
        for field in fields:
            interface_name = _interface_of(interfaces, field)
            field_mesh = mesh_names[f"{interface_name}:{participant}"]
            if field.write == participant:
                ElementTree.SubElement(
                    node, "write-data", {"name": field.name, "mesh": field_mesh}
                )
            if field.read == participant:
                ElementTree.SubElement(
                    node, "read-data", {"name": field.name, "mesh": field_mesh}
                )
    scheme = ElementTree.SubElement(root, "coupling-scheme", {"type": "implicit"})
    ElementTree.SubElement(scheme, "time-window-size", {"value": repr(coupling_dt)})
    ElementTree.SubElement(scheme, "max-iterations", {"value": str(max_iterations)})
    ElementTree.SubElement(
        scheme, "relative-convergence-measure", {"limit": repr(tolerance)}
    )
    for field in fields:
        interface_name = _interface_of(interfaces, field)
        from_mesh = mesh_names[f"{interface_name}:{field.write}"]
        to_mesh = mesh_names[f"{interface_name}:{field.read}"]
        ElementTree.SubElement(
            scheme,
            "exchange",
            {
                "data": field.name,
                "mesh": from_mesh,
                "from": field.write,
                "to": field.read,
            },
        )
        ElementTree.SubElement(
            scheme,
            "mapping",
            {
                "direction": "write",
                "type": field.mapping or mapping,
                "data": field.name,
                "from": from_mesh,
                "to": to_mesh,
            },
        )
    ElementTree.SubElement(scheme, "quasi-newton", {"type": acceleration})
    xml = ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)
    digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()
    return PreciceConfig(xml, digest, participants, mapping, coupling_dt, max_iterations)


def _interface_of(
    interfaces: tuple[DomainInterface, ...], field: CouplingField
) -> str:
    for interface in interfaces:
        if field in interface.fields:
            return interface.name
    raise CouplingError(
        CouplingFailureCode.INTERFACE_MISMATCH, f"field not bound to an interface:{field.name}"
    )
