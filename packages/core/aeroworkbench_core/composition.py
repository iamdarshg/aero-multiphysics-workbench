"""Recursive physical-system composition contracts.

Builds on :mod:`aeroworkbench_core.physical` without altering it. A
:class:`SystemRecord` is the rich recursive node: identity, type, install
transform, typed ports, children, links, bindings, mass, design variables,
requirements, operating state, solver capabilities, fidelity and digests.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import field
from math import isfinite
from typing import Any, Literal

from .physical import RigidTransform, Vector3, contract_digest
from .types import FidelityLevel, Provenance, ResultSource

PortDomain = Literal["mechanical", "fluid", "thermal", "electrical", "control"]
PortDirection = Literal["in", "out"]
AssemblyFidelity = Literal["analytical", "surrogate", "benchmark", "native"]
SubassemblyMode = Literal["frozen", "parametric", "rom", "live"]
BindingKind = Literal["geometry", "semantic", "mass", "interface"]

SOFTWARE_IDENTITY = "aeroworkbench-core-composition"
SOFTWARE_VERSION = "1.0.0"

DOMAIN_UNITS: dict[str, tuple[str, ...]] = {
    "mechanical": ("N", "N.m", "Pa", "m", "mm", "m/s", "rad/s", "N/m", "W"),
    "fluid": ("Pa", "K", "degC", "m/s", "kg/s", "N"),
    "thermal": ("W", "K", "degC"),
    "electrical": ("V", "A", "W"),
    "control": ("1", "rad", "m", "m/s", "N", "W"),
}

_FIDELITY_VALUES = ("analytical", "surrogate", "benchmark", "native")
_MODE_VALUES = ("frozen", "parametric", "rom", "live")
_HEX = frozenset("0123456789abcdef")


def _require_identity(*values: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError("COMPOSITION_IDENTITY_REQUIRED")


def _require_digest(name: str, value: str) -> None:
    if value and (len(value) != 64 or any(c not in _HEX for c in value)):
        raise ValueError(f"COMPOSITION_DIGEST_INVALID:{name}")


def _vec3(value: Any) -> Vector3:
    items = tuple(value) if isinstance(value, (list, tuple)) else ()
    if len(items) != 3:
        raise ValueError("VECTOR3_INVALID")
    return (float(items[0]), float(items[1]), float(items[2]))


def units_compatible(source: str, target: str) -> bool:
    if source == target:
        return True
    linear = {"m": 1.0, "mm": 0.001}
    if source in linear and target in linear:
        return True
    return {source, target} == {"K", "degC"}


def convert_unit(value: float, source_unit: str, target_unit: str) -> float:
    if not isfinite(value):
        raise ValueError("UNIT_VALUE_NONFINITE")
    if source_unit == target_unit:
        return float(value)
    linear = {"m": 1.0, "mm": 0.001}
    if source_unit in linear and target_unit in linear:
        return float(value) * linear[source_unit] / linear[target_unit]
    if source_unit == "degC" and target_unit == "K":
        return float(value) + 273.15
    if source_unit == "K" and target_unit == "degC":
        return float(value) - 273.15
    raise ValueError(f"UNIT_CONVERSION_UNSUPPORTED:{source_unit}->{target_unit}")


@_dataclass(frozen=True, slots=True)
class ComposedPort:
    port_id: str
    domain: PortDomain
    signal: str
    unit: str
    direction: PortDirection
    frame: str
    reference_m: Vector3 = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        _require_identity(self.port_id, self.domain, self.signal, self.unit, self.frame)
        if self.domain not in DOMAIN_UNITS:
            raise ValueError(f"PORT_DOMAIN_UNKNOWN:{self.domain}")
        if self.unit not in DOMAIN_UNITS[self.domain]:
            raise ValueError("PORT_UNIT_DOMAIN_MISMATCH")
        if self.direction not in ("in", "out"):
            raise ValueError("PORT_DIRECTION_INVALID")
        if len(self.reference_m) != 3 or any(not isfinite(v) for v in self.reference_m):
            raise ValueError("PORT_REFERENCE_INVALID")
        object.__setattr__(self, "reference_m", _vec3(self.reference_m))

    def to_dict(self) -> dict[str, Any]:
        return {
            "portId": self.port_id, "domain": self.domain, "signal": self.signal,
            "unit": self.unit, "direction": self.direction, "frame": self.frame,
            "referenceM": list(self.reference_m),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComposedPort:
        return cls(
            port_id=data["portId"], domain=data["domain"], signal=data["signal"],
            unit=data["unit"], direction=data["direction"], frame=data["frame"],
            reference_m=_vec3(data.get("referenceM", (0.0, 0.0, 0.0))),
        )


def _check_common(
    source: ComposedPort, target: ComposedPort, *, transform: RigidTransform | None,
) -> None:
    if source.domain != target.domain:
        raise ValueError("PORT_DOMAIN_MISMATCH")
    if source.signal != target.signal:
        raise ValueError("PORT_SIGNAL_MISMATCH")
    if not units_compatible(source.unit, target.unit):
        raise ValueError(f"PORT_UNIT_MISMATCH:{source.unit}->{target.unit}")
    if source.frame == target.frame:
        if transform is not None and (
            transform.source_frame != source.frame or transform.target_frame != target.frame
        ):
            raise ValueError("PORT_TRANSFORM_FRAME_MISMATCH")
        return
    if transform is None:
        raise ValueError("PORT_TRANSFORM_REQUIRED")
    if transform.source_frame != source.frame or transform.target_frame != target.frame:
        raise ValueError("PORT_FRAME_MISMATCH")


def check_compatible(
    source: ComposedPort, target: ComposedPort, *, transform: RigidTransform | None = None,
) -> None:
    if source.direction != "out" or target.direction != "in":
        raise ValueError("PORT_DIRECTION_MISMATCH")
    _check_common(source, target, transform=transform)


def check_feed_compatible(
    source: ComposedPort, target: ComposedPort, *, transform: RigidTransform | None = None,
) -> None:
    if source.direction != target.direction:
        raise ValueError("PORT_DIRECTION_MISMATCH")
    _check_common(source, target, transform=transform)


def mechanical_port(
    port_id: str, signal: str, unit: str, direction: PortDirection, frame: str,
    reference_m: Vector3 = (0.0, 0.0, 0.0),
) -> ComposedPort:
    return ComposedPort(port_id, "mechanical", signal, unit, direction, frame, reference_m)


def fluid_port(
    port_id: str, signal: str, unit: str, direction: PortDirection, frame: str,
    reference_m: Vector3 = (0.0, 0.0, 0.0),
) -> ComposedPort:
    return ComposedPort(port_id, "fluid", signal, unit, direction, frame, reference_m)


def thermal_port(
    port_id: str, signal: str, unit: str, direction: PortDirection, frame: str,
    reference_m: Vector3 = (0.0, 0.0, 0.0),
) -> ComposedPort:
    return ComposedPort(port_id, "thermal", signal, unit, direction, frame, reference_m)


def electrical_port(
    port_id: str, signal: str, unit: str, direction: PortDirection, frame: str,
    reference_m: Vector3 = (0.0, 0.0, 0.0),
) -> ComposedPort:
    return ComposedPort(port_id, "electrical", signal, unit, direction, frame, reference_m)


def control_port(
    port_id: str, signal: str, unit: str, direction: PortDirection, frame: str,
    reference_m: Vector3 = (0.0, 0.0, 0.0),
) -> ComposedPort:
    return ComposedPort(port_id, "control", signal, unit, direction, frame, reference_m)


@_dataclass(frozen=True, slots=True)
class MassProperties:
    mass_kg: float
    cg_m: Vector3 = (0.0, 0.0, 0.0)
    inertia_kgm2: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if not isfinite(self.mass_kg) or self.mass_kg < 0:
            raise ValueError("MASS_INVALID")
        if len(self.cg_m) != 3 or any(not isfinite(v) for v in self.cg_m):
            raise ValueError("MASS_CG_INVALID")
        if len(self.inertia_kgm2) != 3 or any(not isfinite(v) or v < 0 for v in self.inertia_kgm2):
            raise ValueError("MASS_INERTIA_INVALID")
        object.__setattr__(self, "cg_m", _vec3(self.cg_m))
        raw_inertia = tuple(float(v) for v in self.inertia_kgm2)
        object.__setattr__(self, "inertia_kgm2", (raw_inertia[0], raw_inertia[1], raw_inertia[2]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "massKg": self.mass_kg, "cgM": list(self.cg_m),
            "inertiaKgm2": list(self.inertia_kgm2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MassProperties:
        raw = tuple(float(v) for v in data.get("inertiaKgm2", (0, 0, 0)))
        return cls(data["massKg"], _vec3(data.get("cgM", (0, 0, 0))),
                   (raw[0], raw[1], raw[2]))


def _rotate(matrix: tuple[Vector3, Vector3, Vector3], vector: Vector3) -> Vector3:
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1] + matrix[0][2] * vector[2],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1] + matrix[1][2] * vector[2],
        matrix[2][0] * vector[0] + matrix[2][1] * vector[1] + matrix[2][2] * vector[2],
    )


def aggregate_mass(
    entries: tuple[tuple[MassProperties, RigidTransform | None], ...],
) -> MassProperties:
    if not entries:
        raise ValueError("MASS_AGGREGATION_EMPTY")
    total = sum(entry[0].mass_kg for entry in entries)
    if not isfinite(total) or total <= 0:
        raise ValueError("MASS_AGGREGATION_INVALID")
    worlds: list[tuple[RigidTransform | None, MassProperties, Vector3]] = []
    for mass, transform in entries:
        cg = mass.cg_m if transform is None else _rotate(transform.rotation, mass.cg_m)
        if transform is not None:
            cg = (cg[0] + transform.translation_m[0], cg[1] + transform.translation_m[1],
                  cg[2] + transform.translation_m[2])
        worlds.append((transform, mass, cg))
    combined = (
        sum(m.mass_kg * c[0] for _, m, c in worlds) / total,
        sum(m.mass_kg * c[1] for _, m, c in worlds) / total,
        sum(m.mass_kg * c[2] for _, m, c in worlds) / total,
    )
    tensor = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for transform, mass, cg in worlds:
        rotation = transform.rotation if transform is not None else (
            (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        diag = mass.inertia_kgm2
        rotated = [[rotation[i][0] * rotation[j][0] * diag[0]
                    + rotation[i][1] * rotation[j][1] * diag[1]
                    + rotation[i][2] * rotation[j][2] * diag[2] for j in range(3)]
                   for i in range(3)]
        offset = (cg[0] - combined[0], cg[1] - combined[1], cg[2] - combined[2])
        shift = sum(v * v for v in offset)
        for i in range(3):
            for j in range(3):
                parallel = mass.mass_kg * ((shift if i == j else 0.0) - offset[i] * offset[j])
                tensor[i][j] += rotated[i][j] + parallel
    return MassProperties(total, combined, (tensor[0][0], tensor[1][1], tensor[2][2]))


@_dataclass(frozen=True, slots=True)
class DesignVariable:
    name: str
    value: float
    unit: str
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        _require_identity(self.name, self.unit)
        for candidate in (self.value, self.minimum, self.maximum):
            if not isfinite(candidate):
                raise ValueError("DESIGN_VARIABLE_NONFINITE")
        if self.minimum > self.value or self.value > self.maximum:
            raise ValueError("DESIGN_VARIABLE_OUT_OF_BOUNDS")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "unit": self.unit,
                "minimum": self.minimum, "maximum": self.maximum}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DesignVariable:
        return cls(data["name"], data["value"], data["unit"], data["minimum"], data["maximum"])


@_dataclass(frozen=True, slots=True)
class Requirement:
    req_id: str
    description: str
    quantity: str
    unit: str
    threshold: float
    direction: Literal[">=", "<=", "=="]
    margin: float = 0.0

    def __post_init__(self) -> None:
        _require_identity(self.req_id, self.quantity, self.unit)
        if self.direction not in (">=", "<=", "=="):
            raise ValueError("REQUIREMENT_DIRECTION_INVALID")
        if not isfinite(self.threshold) or not isfinite(self.margin):
            raise ValueError("REQUIREMENT_NONFINITE")

    def evaluate(self, value: float) -> tuple[bool, float]:
        if not isfinite(value):
            raise ValueError("REQUIREMENT_VALUE_NONFINITE")
        scale = max(1.0, abs(self.threshold))
        if self.direction == ">=":
            return value >= self.threshold, (value - self.threshold) / scale
        if self.direction == "<=":
            return value <= self.threshold, (self.threshold - value) / scale
        tolerance = 1e-9 * scale
        return abs(value - self.threshold) <= tolerance, -abs(value - self.threshold) / scale

    def to_dict(self) -> dict[str, Any]:
        return {"reqId": self.req_id, "description": self.description, "quantity": self.quantity,
                "unit": self.unit, "threshold": self.threshold, "direction": self.direction,
                "margin": self.margin}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Requirement:
        return cls(data["reqId"], data.get("description", ""), data["quantity"], data["unit"],
                   data["threshold"], data["direction"], data.get("margin", 0.0))


@_dataclass(frozen=True, slots=True)
class OperatingState:
    name: str
    parameters: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identity(self.name)
        for key, value in self.parameters.items():
            if not key.strip() or not isfinite(value):
                raise ValueError("OPERATING_STATE_INVALID")
        object.__setattr__(self, "parameters", dict(self.parameters))

    @property
    def digest(self) -> str:
        return contract_digest({"name": self.name, "parameters": self.parameters})

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "parameters": dict(self.parameters)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperatingState:
        return cls(data["name"], dict(data.get("parameters", {})))


@_dataclass(frozen=True, slots=True)
class SolverCapability:
    participant: str
    physics: tuple[str, ...] = ()
    fidelity: AssemblyFidelity = "analytical"
    native: bool = False

    def __post_init__(self) -> None:
        _require_identity(self.participant)
        if self.fidelity not in _FIDELITY_VALUES:
            raise ValueError("SOLVER_FIDELITY_INVALID")
        object.__setattr__(self, "physics", tuple(self.physics))

    def to_dict(self) -> dict[str, Any]:
        return {"participant": self.participant, "physics": list(self.physics),
                "fidelity": self.fidelity, "native": self.native}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SolverCapability:
        return cls(data["participant"], tuple(data.get("physics", ())),
                   data.get("fidelity", "analytical"), data.get("native", False))


@_dataclass(frozen=True, slots=True)
class AssemblyLink:
    source_system: str
    source_port: str
    target_system: str
    target_port: str
    transform: RigidTransform | None = None
    mapping: str = "identity"
    version: str = "1"

    def __post_init__(self) -> None:
        _require_identity(self.source_system, self.source_port, self.target_system,
                          self.target_port, self.mapping, self.version)
        if self.source_system == self.target_system and self.source_port == self.target_port:
            raise ValueError("LINK_SELF_CONNECTION")

    @property
    def digest(self) -> str:
        return contract_digest({
            "sourceSystem": self.source_system, "sourcePort": self.source_port,
            "targetSystem": self.target_system, "targetPort": self.target_port,
            "transform": self.transform.digest if self.transform else None,
            "mapping": self.mapping, "version": self.version,
        })

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict as _asdict

        return {
            "sourceSystem": self.source_system, "sourcePort": self.source_port,
            "targetSystem": self.target_system, "targetPort": self.target_port,
            "transform": _asdict(self.transform) if self.transform else None,
            "mapping": self.mapping, "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssemblyLink:
        raw = data.get("transform")
        transform = RigidTransform(**raw) if raw else None
        return cls(data["sourceSystem"], data["sourcePort"], data["targetSystem"],
                   data["targetPort"], transform, data.get("mapping", "identity"),
                   data.get("version", "1"))


@_dataclass(frozen=True, slots=True)
class Binding:
    child_system: str
    child_port: str
    parent_port: str
    kind: BindingKind = "interface"

    def __post_init__(self) -> None:
        _require_identity(self.child_system, self.child_port, self.parent_port)
        if self.kind not in ("geometry", "semantic", "mass", "interface"):
            raise ValueError("BINDING_KIND_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return {"childSystem": self.child_system, "childPort": self.child_port,
                "parentPort": self.parent_port, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Binding:
        return cls(data["childSystem"], data["childPort"], data["parentPort"],
                   data.get("kind", "interface"))


@_dataclass(frozen=True, slots=True)
class SystemRecord:
    system_id: str
    revision: str
    system_type: str
    capabilities: tuple[str, ...] = ()
    transform: RigidTransform | None = None
    ports: tuple[ComposedPort, ...] = ()
    children: tuple[SystemRecord, ...] = ()
    links: tuple[AssemblyLink, ...] = ()
    bindings: tuple[Binding, ...] = ()
    mass: MassProperties | None = None
    design_vars: tuple[DesignVariable, ...] = ()
    requirements: tuple[Requirement, ...] = ()
    operating: OperatingState | None = None
    solvers: tuple[SolverCapability, ...] = ()
    fidelity: AssemblyFidelity = "analytical"
    geometry_digest: str = ""
    semantic_digest: str = ""
    model_digest: str = ""
    mode: SubassemblyMode = "live"
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identity(self.system_id, self.revision, self.system_type)
        if self.fidelity not in _FIDELITY_VALUES:
            raise ValueError("SYSTEM_FIDELITY_INVALID")
        if self.mode not in _MODE_VALUES:
            raise ValueError("SYSTEM_MODE_INVALID")
        for name in ("geometry", "semantic", "model"):
            _require_digest(name, getattr(self, f"{name}_digest"))
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "lineage", tuple(self.lineage))
        object.__setattr__(self, "ports", tuple(sorted(self.ports, key=lambda p: p.port_id)))
        object.__setattr__(self, "children",
                           tuple(sorted(self.children, key=lambda c: c.system_id)))
        object.__setattr__(self, "links", tuple(sorted(self.links, key=lambda c: c.digest)))
        object.__setattr__(self, "bindings", tuple(sorted(
            self.bindings, key=lambda b: (b.child_system, b.child_port, b.parent_port))))
        object.__setattr__(self, "design_vars",
                           tuple(sorted(self.design_vars, key=lambda v: v.name)))
        object.__setattr__(self, "requirements",
                           tuple(sorted(self.requirements, key=lambda r: r.req_id)))
        object.__setattr__(self, "solvers",
                           tuple(sorted(self.solvers, key=lambda s: s.participant)))
        if len({port.port_id for port in self.ports}) != len(self.ports):
            raise ValueError("DUPLICATE_PORT")
        if len({var.name for var in self.design_vars}) != len(self.design_vars):
            raise ValueError("DUPLICATE_DESIGN_VARIABLE")
        if len({req.req_id for req in self.requirements}) != len(self.requirements):
            raise ValueError("DUPLICATE_REQUIREMENT")
        seen: dict[str, SystemRecord] = {self.system_id: self}

        def collect(node: SystemRecord) -> None:
            for child in node.children:
                if child.system_id in seen:
                    raise ValueError(f"DUPLICATE_SYSTEM_ID:{child.system_id}")
                seen[child.system_id] = child
                collect(child)

        collect(self)
        members: dict[str, SystemRecord] = {self.system_id: self}
        for child in self.children:
            members[child.system_id] = child
        port_of = {port.port_id: port for port in self.ports}
        child_ports = {cid: {p.port_id: p for p in child.ports} for cid, child in members.items()}
        for link in self.links:
            if link.source_system not in members or link.target_system not in members:
                raise ValueError("LINK_ENDPOINT_UNKNOWN")
            if link.source_system == self.system_id and link.target_system == self.system_id:
                raise ValueError("LINK_SELF_SYSTEM")
            if link.target_system == self.system_id:
                raise ValueError("LINK_TO_PARENT_USE_BINDING")
            source = child_ports[link.source_system].get(link.source_port)
            target = child_ports[link.target_system].get(link.target_port)
            if source is None or target is None:
                raise ValueError("LINK_PORT_NOT_DECLARED")
            if link.source_system == self.system_id:
                check_feed_compatible(source, target, transform=link.transform)
            else:
                check_compatible(source, target, transform=link.transform)
        for binding in self.bindings:
            if binding.child_system not in members or binding.child_system == self.system_id:
                raise ValueError("BINDING_CHILD_UNKNOWN")
            if binding.child_port not in child_ports[binding.child_system]:
                raise ValueError("BINDING_CHILD_PORT_NOT_DECLARED")
            if binding.parent_port not in port_of:
                raise ValueError("BINDING_PARENT_PORT_NOT_DECLARED")
            if binding.kind == "interface":
                check_feed_compatible(
                    child_ports[binding.child_system][binding.child_port],
                    port_of[binding.parent_port])

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(child.depth for child in self.children)

    def find(self, system_id: str) -> SystemRecord | None:
        if self.system_id == system_id:
            return self
        for child in self.children:
            located = child.find(system_id)
            if located is not None:
                return located
        return None

    def leaves(self) -> tuple[SystemRecord, ...]:
        if not self.children:
            return (self,)
        ordered: list[SystemRecord] = []
        for child in self.children:
            ordered.extend(child.leaves())
        return tuple(ordered)

    @property
    def subtree_digest(self) -> str:
        return contract_digest({
            "systemId": self.system_id, "revision": self.revision,
            "systemType": self.system_type, "capabilities": list(self.capabilities),
            "transform": self.transform.digest if self.transform else None,
            "ports": [p.to_dict() for p in self.ports],
            "children": [{"id": c.system_id, "digest": c.subtree_digest} for c in self.children],
            "links": [link.digest for link in self.links],
            "bindings": [b.to_dict() for b in self.bindings],
            "mass": self.mass.to_dict() if self.mass else None,
            "designVars": [v.to_dict() for v in self.design_vars],
            "requirements": [r.to_dict() for r in self.requirements],
            "operating": self.operating.digest if self.operating else None,
            "solvers": [s.to_dict() for s in self.solvers],
            "fidelity": self.fidelity, "geometry": self.geometry_digest,
            "semantic": self.semantic_digest, "model": self.model_digest,
            "mode": self.mode, "lineage": list(self.lineage),
        })

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict as _asdict

        return {
            "systemId": self.system_id, "revision": self.revision,
            "systemType": self.system_type, "capabilities": list(self.capabilities),
            "transform": _asdict(self.transform) if self.transform else None,
            "ports": [p.to_dict() for p in self.ports],
            "children": [c.to_dict() for c in self.children],
            "links": [link.to_dict() for link in self.links],
            "bindings": [b.to_dict() for b in self.bindings],
            "mass": self.mass.to_dict() if self.mass else None,
            "designVars": [v.to_dict() for v in self.design_vars],
            "requirements": [r.to_dict() for r in self.requirements],
            "operating": self.operating.to_dict() if self.operating else None,
            "solvers": [s.to_dict() for s in self.solvers],
            "fidelity": self.fidelity, "geometryDigest": self.geometry_digest,
            "semanticDigest": self.semantic_digest, "modelDigest": self.model_digest,
            "mode": self.mode, "lineage": list(self.lineage),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemRecord:
        raw_transform = data.get("transform")
        operating = data.get("operating")
        mass = data.get("mass")
        return cls(
            system_id=data["systemId"], revision=data["revision"],
            system_type=data["systemType"], capabilities=tuple(data.get("capabilities", ())),
            transform=RigidTransform(**raw_transform) if raw_transform else None,
            ports=tuple(ComposedPort.from_dict(p) for p in data.get("ports", ())),
            children=tuple(cls.from_dict(c) for c in data.get("children", ())),
            links=tuple(AssemblyLink.from_dict(link) for link in data.get("links", ())),
            bindings=tuple(Binding.from_dict(b) for b in data.get("bindings", ())),
            mass=MassProperties.from_dict(mass) if mass else None,
            design_vars=tuple(DesignVariable.from_dict(v) for v in data.get("designVars", ())),
            requirements=tuple(Requirement.from_dict(r) for r in data.get("requirements", ())),
            operating=OperatingState.from_dict(operating) if operating else None,
            solvers=tuple(SolverCapability.from_dict(s) for s in data.get("solvers", ())),
            fidelity=data.get("fidelity", "analytical"),
            geometry_digest=data.get("geometryDigest", ""),
            semantic_digest=data.get("semanticDigest", ""),
            model_digest=data.get("modelDigest", ""),
            mode=data.get("mode", "live"), lineage=tuple(data.get("lineage", ())),
        )


@_dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


@_dataclass(frozen=True, slots=True)
class Validity:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}


_SOURCE_FOR: dict[str, ResultSource] = {
    "analytical": ResultSource.ANALYTICAL,
    "surrogate": ResultSource.SURROGATE,
    "benchmark": ResultSource.BENCHMARK,
    "native": ResultSource.NATIVE_SOLVER,
}

_FIDELITY_LEVEL_FOR: dict[str, FidelityLevel] = {
    "analytical": FidelityLevel.ANALYTICAL,
    "surrogate": FidelityLevel.ANALYTICAL,
    "benchmark": FidelityLevel.ANALYTICAL,
    "native": FidelityLevel.ANALYTICAL,
}


@_dataclass(frozen=True, slots=True)
class AssemblyResult:
    source: ResultSource
    fidelity: AssemblyFidelity
    units: dict[str, str] = field(default_factory=dict)
    validity: Validity = field(default_factory=lambda: Validity(True))
    inputs_hash: str = ""
    software: SoftwareIdentity = field(default_factory=SoftwareIdentity)
    provenance: Provenance | None = None
    values: dict[str, float] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.fidelity not in _FIDELITY_VALUES:
            raise ValueError("RESULT_FIDELITY_INVALID")
        _require_digest("inputs", self.inputs_hash)
        object.__setattr__(self, "units", dict(self.units))
        object.__setattr__(self, "values", dict(self.values))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value, "fidelity": self.fidelity,
            "units": dict(self.units), "validity": self.validity.canonical(),
            "inputsHash": self.inputs_hash, "software": self.software.canonical(),
            "provenance": self.provenance.model_dump(mode="json") if self.provenance else None,
            "values": dict(self.values), "assumptions": list(self.assumptions),
        }


def analytical_envelope(
    *,
    model: str,
    inputs: dict[str, Any],
    validity: Validity,
    fidelity: AssemblyFidelity = "analytical",
    units: dict[str, str] | None = None,
    values: dict[str, float] | None = None,
    assumptions: tuple[str, ...] = (),
) -> AssemblyResult:
    _require_identity(model)
    provenance = Provenance.from_inputs(
        source=_SOURCE_FOR[fidelity], model=model, model_version=SOFTWARE_VERSION,
        fidelity=_FIDELITY_LEVEL_FOR[fidelity], inputs=dict(inputs),
        assumptions=tuple(assumptions),
    )
    return AssemblyResult(
        source=_SOURCE_FOR[fidelity], fidelity=fidelity, units=dict(units or {}),
        validity=validity, inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(), provenance=provenance,
        values=dict(values or {}), assumptions=tuple(assumptions),
    )


def native_envelope(
    *,
    model: str,
    inputs: dict[str, Any],
    validity: Validity,
    solver_name: str,
    solver_version: str,
    run_id: str,
    units: dict[str, str] | None = None,
    values: dict[str, float] | None = None,
    assumptions: tuple[str, ...] = (),
) -> AssemblyResult:
    _require_identity(model, solver_name, solver_version, run_id)
    provenance = Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER, model=model, model_version=solver_version,
        fidelity=FidelityLevel.ANALYTICAL, inputs=dict(inputs),
        assumptions=tuple(assumptions), solver_name=solver_name,
        solver_version=solver_version, run_id=run_id,
    )
    return AssemblyResult(
        source=ResultSource.NATIVE_SOLVER, fidelity="native", units=dict(units or {}),
        validity=validity, inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(), provenance=provenance,
        values=dict(values or {}), assumptions=tuple(assumptions),
    )
