"""Canonical recursive physical contracts; no solver or domain implementation.

Frames are right-handed, SI, and transformations are active: x_target=R*x_source+t.
System IDs are unique throughout an assembly, making interface endpoints unambiguous.
Native capabilities remain the responsibility of the existing participant lifecycle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, Literal

Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]
IDENTITY: Matrix3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def contract_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _identity(*values: str) -> None:
    if any(not value.strip() for value in values):
        raise ValueError("PHYSICAL_IDENTITY_REQUIRED")


@dataclass(frozen=True, slots=True)
class RigidTransform:
    source_frame: str
    target_frame: str
    rotation: Matrix3 = IDENTITY
    translation_m: Vector3 = (0, 0, 0)

    def __post_init__(self) -> None:
        _identity(self.source_frame, self.target_frame)
        if len(self.rotation) != 3 or any(len(row) != 3 for row in self.rotation):
            raise ValueError("FRAME_ROTATION_MUST_BE_3X3")
        if len(self.translation_m) != 3 or any(
            not isfinite(v) for row in (*self.rotation, self.translation_m) for v in row
        ):
            raise ValueError("FRAME_MUST_BE_FINITE")
        r = self.rotation
        if any(abs(sum(r[i][k]*r[j][k] for k in range(3)) - (i == j)) > 1e-10
               for i in range(3) for j in range(3)):
            raise ValueError("FRAME_ROTATION_MUST_BE_ORTHONORMAL")
        determinant = sum(r[0][i]*(r[1][(i+1)%3]*r[2][(i+2)%3]
                                  - r[1][(i+2)%3]*r[2][(i+1)%3]) for i in range(3))
        if abs(determinant - 1) > 1e-10:
            raise ValueError("FRAME_MUST_BE_RIGHT_HANDED")
        object.__setattr__(self, "rotation", tuple(tuple(float(v) for v in row) for row in r))
        object.__setattr__(self, "translation_m", tuple(float(v) for v in self.translation_m))

    def rotate(self, vector: Vector3) -> Vector3:
        if len(vector) != 3 or any(not isfinite(v) for v in vector):
            raise ValueError("VECTOR_MUST_BE_FINITE_3D")
        return (sum(a*b for a, b in zip(self.rotation[0], vector, strict=True)),
                sum(a*b for a, b in zip(self.rotation[1], vector, strict=True)),
                sum(a*b for a, b in zip(self.rotation[2], vector, strict=True)))

    @property
    def digest(self) -> str:
        return contract_digest(asdict(self))


_SEMANTIC_UNITS = {
    "wrench": ("N",), "traction": ("Pa",), "pressure": ("Pa",),
    "displacement": ("m", "mm"), "temperature": ("K", "degC"),
    "thermal": ("W",), "electrical": ("W",), "shaft": ("W",),
    "harmonic": ("N", "N.m", "Pa", "m", "W"),
}


@dataclass(frozen=True, slots=True)
class PhysicalPort:
    port_id: str
    semantic: str
    unit: str
    direction: Literal["in", "out"]
    frame: str
    reference_m: Vector3 = (0, 0, 0)

    def __post_init__(self) -> None:
        _identity(self.port_id, self.frame)
        if self.direction not in ("in", "out"):
            raise ValueError("PORT_DIRECTION_INVALID")
        if self.unit not in _SEMANTIC_UNITS.get(self.semantic, ()):
            raise ValueError("PORT_UNIT_SEMANTIC_MISMATCH")
        if len(self.reference_m) != 3 or any(not isfinite(v) for v in self.reference_m):
            raise ValueError("PORT_REFERENCE_INVALID")
        object.__setattr__(self, "reference_m", tuple(float(v) for v in self.reference_m))


@dataclass(frozen=True, slots=True)
class InterfaceContract:
    source_system: str
    source: PhysicalPort
    target_system: str
    target: PhysicalPort
    mapping: str = "identity"
    version: str = "1"

    def __post_init__(self) -> None:
        _identity(self.source_system, self.target_system, self.mapping, self.version)
        if self.source_system == self.target_system:
            raise ValueError("INTERFACE_SELF_CONNECTION")
        if self.source.direction != "out" or self.target.direction != "in":
            raise ValueError("INTERFACE_DIRECTION_MISMATCH")
        if self.source.semantic != self.target.semantic:
            raise ValueError("INTERFACE_SEMANTIC_MISMATCH")
        compatible = ({"m", "mm"}, {"K", "degC"})
        if self.source.unit != self.target.unit and not any(
            {self.source.unit, self.target.unit} <= group for group in compatible
        ):
            raise ValueError("INTERFACE_UNIT_MISMATCH")

    @property
    def digest(self) -> str:
        return contract_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class HarmonicBasis:
    shaft_id: str
    frame: str
    frequency_hz: float
    order: float
    convention: Literal["exp(+iwt)"] = "exp(+iwt)"

    def __post_init__(self) -> None:
        _identity(self.shaft_id, self.frame)
        if (not isfinite(self.frequency_hz) or self.frequency_hz < 0
                or not isfinite(self.order) or self.convention != "exp(+iwt)"):
            raise ValueError("HARMONIC_BASIS_INVALID")


@dataclass(frozen=True, slots=True)
class PhysicalSystem:
    system_id: str
    revision: str
    ports: tuple[PhysicalPort, ...] = ()
    transform: RigidTransform | None = None
    boundary_digest: str = ""
    model_digest: str = ""
    mode: Literal["analytical", "surrogate", "native"] = "analytical"

    def __post_init__(self) -> None:
        _identity(self.system_id, self.revision)
        if self.mode not in ("analytical", "surrogate", "native"):
            raise ValueError("SYSTEM_MODE_INVALID")
        for digest in (self.boundary_digest, self.model_digest):
            if digest and (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("SYSTEM_DIGEST_INVALID")
        if len({port.port_id for port in self.ports}) != len(self.ports):
            raise ValueError("DUPLICATE_PORT")
        object.__setattr__(self, "ports", tuple(sorted(self.ports, key=lambda p: p.port_id)))

    def to_dict(self) -> dict[str, Any]:
        return {"system_id": self.system_id, "revision": self.revision,
                "ports": [asdict(port) for port in self.ports],
                "transform": asdict(self.transform) if self.transform else None,
                "boundary_digest": self.boundary_digest, "model_digest": self.model_digest,
                "mode": self.mode}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalSystem:
        values = dict(data)
        values["ports"] = tuple(PhysicalPort(**p) for p in values.get("ports", ()))
        if values.get("transform"):
            values["transform"] = RigidTransform(**values["transform"])
        if "children" in values:
            values["children"] = tuple(cls.from_dict(c) for c in values["children"])
            values["interfaces"] = tuple(InterfaceContract(
                **{**c, "source": PhysicalPort(**c["source"]), "target": PhysicalPort(**c["target"])}  # noqa: E501
            ) for c in values.get("interfaces", ()))
            return PhysicalAssembly(**values)
        return PhysicalSystem(**values)

    @property
    def subtree_digest(self) -> str:
        data = self.to_dict()
        if isinstance(self, PhysicalAssembly):
            data["children"] = [{"id": c.system_id, "digest": c.subtree_digest}
                                for c in self.children]
        return contract_digest(data)


@dataclass(frozen=True, slots=True)
class PhysicalAssembly(PhysicalSystem):
    children: tuple[PhysicalSystem, ...] = ()
    interfaces: tuple[InterfaceContract, ...] = ()

    def __post_init__(self) -> None:
        PhysicalSystem.__post_init__(self)
        object.__setattr__(self, "children", tuple(sorted(self.children, key=lambda c: c.system_id)))  # noqa: E501
        object.__setattr__(self, "interfaces", tuple(sorted(self.interfaces, key=lambda c: c.digest)))  # noqa: E501
        systems = {self.system_id: self}

        def collect(system: PhysicalSystem) -> None:
            if system.system_id in systems:
                raise ValueError("DUPLICATE_SYSTEM_ID")
            systems[system.system_id] = system
            if isinstance(system, PhysicalAssembly):
                for child in system.children:
                    collect(child)

        for child in self.children:
            collect(child)
        for contract in self.interfaces:
            for identity, port in ((contract.source_system, contract.source),
                                   (contract.target_system, contract.target)):
                if identity not in systems or port not in systems[identity].ports:
                    raise ValueError("INTERFACE_ENDPOINT_NOT_DECLARED")

    def to_dict(self) -> dict[str, Any]:
        return {**PhysicalSystem.to_dict(self), "children": [c.to_dict() for c in self.children],
                "interfaces": [asdict(c) for c in self.interfaces]}
