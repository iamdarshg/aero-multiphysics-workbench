"""Governed structural ingestion for the Code_Aster participant.

The participant consumes a *governed* structural request: a mesh mapping with
semantic volume/surface/node groups, named interfaces, material physical
groups and orientation frames, plus explicit material bindings, constraints,
and loads. Every reference is validated here against the declared mesh before
any native input is generated.

Validation fails closed:

- a constraint/load target that is not a declared group or interface,
- a volume with no material binding,
- an anisotropy model the native deck cannot represent (e.g. a raw laminate
  stack that must be homogenized first), and
- unknown contact/constraint/load modes.

Nothing is silently substituted. Loads refer to semantic regions/interfaces,
never to application names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError

ANALYSES: tuple[str, ...] = ("static", "modal", "harmonic", "transient")

# Only explicitly implemented native modes are accepted.
CONTACT_MODES: tuple[str, ...] = ("discrete",)
CONSTRAINT_MODES: tuple[str, ...] = ("fixed", "kinematic")
LOAD_KINDS: tuple[str, ...] = (
    "nodal_force",
    "distributed_force",
    "pressure",
    "traction",
    "centrifugal",
    "thermal",
    "harmonic_spectrum",
)
SUPPORTED_SYMMETRIES: tuple[str, ...] = (
    "isotropic",
    "orthotropic",
    "transversely_isotropic",
)
MESH_FORMATS: tuple[str, ...] = ("MED", "GMSH")
DOF_NAMES: tuple[str, ...] = ("DX", "DY", "DZ", "DRX", "DRY", "DRZ")
FORCE_COMPONENTS: tuple[str, ...] = ("FX", "FY", "FZ")

_ISOTROPIC_REQUIRED: tuple[str, ...] = (
    "youngs_modulus_pa",
    "poisson_ratio",
    "density_kg_m3",
)
_ORTHOTROPIC_REQUIRED: tuple[str, ...] = (
    "e_l_pa",
    "e_t_pa",
    "e_n_pa",
    "nu_lt",
    "nu_ln",
    "nu_tn",
    "g_lt_pa",
    "g_ln_pa",
    "g_tn_pa",
    "density_kg_m3",
)
_TRANSVERSE_REQUIRED: tuple[str, ...] = (
    "e_l_pa",
    "e_t_pa",
    "nu_lt",
    "nu_tn",
    "g_lt_pa",
    "g_tn_pa",
    "density_kg_m3",
)


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _text(data: Mapping[str, object], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{name} must be a non-empty string")
    return value.strip()


def _number(
    data: Mapping[str, object], name: str, *, positive: bool = False
) -> float:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise _fail(f"{name} must be finite")
    if positive and result <= 0:
        raise _fail(f"{name} must be positive")
    return result


def _mapping(data: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = data.get(name)
    if not isinstance(value, Mapping):
        raise _fail(f"{name} must be a mapping")
    return value


def _sequence(data: Mapping[str, object], name: str) -> Sequence[object]:
    value = data.get(name)
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _fail(f"{name} must be a list")
    return value


def _string_tuple(data: Mapping[str, object], name: str) -> tuple[str, ...]:
    value = data.get(name, ())
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _fail(f"{name} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise _fail(f"{name} entries must be non-empty strings")
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise _fail(f"{name} contains duplicate entries")
    return tuple(result)


def _vector3(data: Mapping[str, object], name: str) -> tuple[float, float, float]:
    value = data.get(name)
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 3:
        raise _fail(f"{name} must be a 3-vector")
    components = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise _fail(f"{name} must be numeric")
        components.append(float(item))
    return (components[0], components[1], components[2])


def _optional_text(data: Mapping[str, object], name: str) -> str | None:
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{name} must be a non-empty string when declared")
    return value.strip()


def _optional_hash(data: Mapping[str, object], name: str) -> str | None:
    value = _optional_text(data, name)
    if value is None:
        return None
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise _fail(f"{name} must be a 64-character lowercase hex digest")
    return value


@dataclass(frozen=True, slots=True)
class InterfaceIngestion:
    """One named coupling interface with an optional physical surface group."""

    name: str
    kind: str
    zone_a: str
    zone_b: str
    surface: str | None


@dataclass(frozen=True, slots=True)
class ContactIngestion:
    """An explicitly declared native contact zone."""

    mode: str
    slave: str
    master: str


@dataclass(frozen=True, slots=True)
class FrameIngestion:
    """A declared region-specific orientation/rotation frame."""

    name: str
    origin: tuple[float, float, float]
    axis: tuple[float, float, float]
    angles_deg: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class MeshIngestion:
    """Governed mesh mapping: semantic groups, material groups, frames."""

    file: str
    format: str
    volumes: tuple[str, ...]
    surfaces: tuple[str, ...]
    nodes: tuple[str, ...]
    material_groups: Mapping[str, str]
    interfaces: tuple[InterfaceIngestion, ...]
    frames: Mapping[str, FrameIngestion]
    geometry_hash: str | None = None
    mesh_hash: str | None = None

    def interface(self, name: str) -> InterfaceIngestion:
        for item in self.interfaces:
            if item.name == name:
                return item
        raise _fail(f"UNKNOWN_INTERFACE:{name}")

    def resolves_surface(self, target: str) -> str:
        if target in self.surfaces:
            return target
        for item in self.interfaces:
            if item.name == target:
                if item.surface is None:
                    raise _fail(f"INTERFACE_HAS_NO_SURFACE:{target}")
                return item.surface
        raise _fail(f"UNKNOWN_SURFACE_OR_INTERFACE:{target}")

    def resolves_node(self, target: str) -> str:
        if target in self.nodes:
            return target
        raise _fail(f"UNKNOWN_NODE_GROUP:{target}")


@dataclass(frozen=True, slots=True)
class MaterialIngestion:
    """One region's material binding with evaluated native constants."""

    region: str
    identity: str
    symmetry: str
    properties: Mapping[str, float]
    frame: str | None


@dataclass(frozen=True, slots=True)
class ConstraintIngestion:
    """One kinematic constraint with resolved group kind and DOF values."""

    name: str
    mode: str
    group: str
    group_kind: str  # "node" | "surface"
    dofs: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class LoadIngestion:
    """One load mapped onto a semantic region or interface."""

    name: str
    kind: str
    target: str
    group_kind: str  # "node" | "surface"
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StructuralRequest:
    """A validated governed structural request ready for native rendering."""

    analysis: str
    prestress: bool
    contact: ContactIngestion | None
    mesh: MeshIngestion
    materials: tuple[MaterialIngestion, ...]
    constraints: tuple[ConstraintIngestion, ...]
    loads: tuple[LoadIngestion, ...]
    n_modes: int
    time_end_s: float
    n_steps: int


def _ingest_mesh(data: Mapping[str, object]) -> MeshIngestion:
    mesh = _mapping(data, "mesh")
    file = _text(mesh, "file")
    fmt = _text(mesh, "format").upper()
    if fmt not in MESH_FORMATS:
        raise _fail(f"UNSUPPORTED_MESH_FORMAT:{fmt}")
    volumes = _string_tuple(mesh, "volumes")
    if not volumes:
        raise _fail("MESH_HAS_NO_VOLUME_GROUPS")
    surfaces = _string_tuple(mesh, "surfaces")
    nodes = _string_tuple(mesh, "nodes")

    raw_groups = _mapping(mesh, "material_groups")
    material_groups: dict[str, str] = {}
    for volume in volumes:
        group = raw_groups.get(volume)
        if not isinstance(group, str) or not group.strip():
            raise _fail(f"MISSING_MATERIAL_GROUP:{volume}")
        material_groups[volume] = group.strip()
    unknown_groups = sorted(set(raw_groups) - set(volumes))
    if unknown_groups:
        raise _fail(f"MATERIAL_GROUP_WITHOUT_VOLUME:{','.join(unknown_groups)}")

    interfaces: list[InterfaceIngestion] = []
    seen: set[str] = set()
    for raw in _sequence(mesh, "interfaces"):
        if not isinstance(raw, Mapping):
            raise _fail("interface entries must be mappings")
        name = _text(raw, "name")
        if name in seen:
            raise _fail(f"DUPLICATE_INTERFACE:{name}")
        seen.add(name)
        zone_a = _text(raw, "zone_a")
        zone_b = _text(raw, "zone_b")
        for zone in (zone_a, zone_b):
            if zone not in volumes:
                raise _fail(f"INTERFACE_ZONE_UNKNOWN:{name}:{zone}")
        interfaces.append(
            InterfaceIngestion(
                name=name,
                kind=_text(raw, "kind"),
                zone_a=zone_a,
                zone_b=zone_b,
                surface=_optional_text(raw, "surface"),
            )
        )

    frames: dict[str, FrameIngestion] = {}
    raw_frames = mesh.get("frames", {})
    if not isinstance(raw_frames, Mapping):
        raise _fail("frames must be a mapping")
    for name, raw in raw_frames.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(raw, Mapping):
            raise _fail("frame entries must be named mappings")
        frames[name.strip()] = FrameIngestion(
            name=name.strip(),
            origin=_vector3(raw, "origin"),
            axis=_vector3(raw, "axis"),
            angles_deg=_vector3(raw, "angles_deg"),
        )

    return MeshIngestion(
        file=file,
        format=fmt,
        volumes=volumes,
        surfaces=surfaces,
        nodes=nodes,
        material_groups=material_groups,
        interfaces=tuple(interfaces),
        frames=frames,
        geometry_hash=_optional_hash(mesh, "geometry_hash"),
        mesh_hash=_optional_hash(mesh, "mesh_hash"),
    )


def _material_properties(
    raw: Mapping[str, object], symmetry: str
) -> dict[str, float]:
    if symmetry == "isotropic":
        required = _ISOTROPIC_REQUIRED
    elif symmetry == "orthotropic":
        required = _ORTHOTROPIC_REQUIRED
    else:
        required = _TRANSVERSE_REQUIRED
    properties: dict[str, float] = {}
    missing: list[str] = []
    for key in required:
        if key not in raw:
            missing.append(key)
            continue
        properties[key] = _number(
            raw,
            key,
            positive=(key != "poisson_ratio" and not key.startswith("nu_")),
        )
    if missing:
        raise _fail(f"INCOMPLETE_{symmetry.upper()}_CONSTANTS:{','.join(missing)}")
    for nu in ("nu_lt", "nu_ln", "nu_tn"):
        if nu in properties and not 0 <= properties[nu] < 0.5:
            raise _fail(f"POISSON_OUT_OF_RANGE:{nu}")
    return properties


def _ingest_materials(
    data: Mapping[str, object], mesh: MeshIngestion
) -> tuple[MaterialIngestion, ...]:
    raw_materials = _sequence(data, "materials")
    if not raw_materials:
        raise _fail("MATERIALS_REQUIRED")
    bindings: dict[str, MaterialIngestion] = {}
    for raw in raw_materials:
        if not isinstance(raw, Mapping):
            raise _fail("material entries must be mappings")
        region = _text(raw, "region")
        if region not in mesh.volumes:
            raise _fail(f"MATERIAL_REGION_NOT_IN_MESH:{region}")
        if region in bindings:
            raise _fail(f"DUPLICATE_MATERIAL_BINDING:{region}")
        symmetry = _text(raw, "symmetry")
        if symmetry not in SUPPORTED_SYMMETRIES:
            if symmetry == "laminate":
                raise _fail(
                    f"UNSUPPORTED_ANISOTROPY:{region}:laminate stack must be "
                    "homogenized (CLT) before a native deck"
                )
            raise _fail(f"UNSUPPORTED_MATERIAL_SYMMETRY:{region}:{symmetry}")
        frame = _optional_text(raw, "frame")
        if frame is not None and frame not in mesh.frames:
            raise _fail(f"UNDECLARED_ORIENTATION_FRAME:{region}:{frame}")
        bindings[region] = MaterialIngestion(
            region=region,
            identity=str(raw.get("identity", region)),
            symmetry=symmetry,
            properties=_material_properties(raw, symmetry),
            frame=frame,
        )
    missing = sorted(set(mesh.volumes) - set(bindings))
    if missing:
        raise _fail(f"MISSING_MATERIAL_BINDING:{','.join(missing)}")
    return tuple(bindings[volume] for volume in mesh.volumes)


def _ingest_constraints(
    data: Mapping[str, object], mesh: MeshIngestion
) -> tuple[ConstraintIngestion, ...]:
    constraints: list[ConstraintIngestion] = []
    seen: set[str] = set()
    for raw in _sequence(data, "constraints"):
        if not isinstance(raw, Mapping):
            raise _fail("constraint entries must be mappings")
        name = _text(raw, "name")
        if name in seen:
            raise _fail(f"DUPLICATE_CONSTRAINT:{name}")
        seen.add(name)
        mode = _text(raw, "mode")
        if mode not in CONSTRAINT_MODES:
            raise _fail(f"UNSUPPORTED_CONSTRAINT_MODE:{name}:{mode}")
        group = _text(raw, "group")
        if group in mesh.nodes:
            group_kind = "node"
        elif group in mesh.surfaces:
            group_kind = "surface"
        else:
            raise _fail(f"UNKNOWN_CONSTRAINT_GROUP:{name}:{group}")
        if mode == "fixed":
            dofs = {"DX": 0.0, "DY": 0.0, "DZ": 0.0}
        else:
            raw_dofs = raw.get("dofs")
            if not isinstance(raw_dofs, Mapping) or not raw_dofs:
                raise _fail(f"KINEMATIC_CONSTRAINT_REQUIRES_DOFS:{name}")
            dofs = {}
            for dof, value in raw_dofs.items():
                if dof not in DOF_NAMES:
                    raise _fail(f"UNKNOWN_DOF:{name}:{dof}")
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise _fail(f"DOF_VALUE_MUST_BE_NUMBER:{name}:{dof}")
                dofs[str(dof)] = float(value)
        constraints.append(
            ConstraintIngestion(
                name=name, mode=mode, group=group, group_kind=group_kind, dofs=dofs
            )
        )
    return tuple(constraints)


def _force_components(raw: Mapping[str, object], name: str) -> dict[str, float]:
    components: dict[str, float] = {}
    for component in FORCE_COMPONENTS:
        if component in raw:
            components[component] = _number(raw, component)
    if not components:
        raise _fail(f"LOAD_REQUIRES_FORCE_COMPONENT:{name}")
    return components


def _ingest_loads(
    data: Mapping[str, object], mesh: MeshIngestion
) -> tuple[LoadIngestion, ...]:
    loads: list[LoadIngestion] = []
    seen: set[str] = set()
    for raw in _sequence(data, "loads"):
        if not isinstance(raw, Mapping):
            raise _fail("load entries must be mappings")
        name = _text(raw, "name")
        if name in seen:
            raise _fail(f"DUPLICATE_LOAD:{name}")
        seen.add(name)
        kind = _text(raw, "kind")
        if kind not in LOAD_KINDS:
            raise _fail(f"UNSUPPORTED_LOAD_KIND:{name}:{kind}")
        target = _text(raw, "target")
        parameters: dict[str, Any] = {}

        if kind == "nodal_force":
            group = mesh.resolves_node(target)
            parameters["group"] = group
            parameters["components"] = _force_components(raw, name)
            group_kind = "node"
        elif kind in {"distributed_force", "traction"}:
            parameters["group"] = mesh.resolves_surface(target)
            parameters["components"] = _force_components(raw, name)
            group_kind = "surface"
        elif kind == "pressure":
            parameters["group"] = mesh.resolves_surface(target)
            parameters["pressure_pa"] = _number(raw, "pressure_pa")
            group_kind = "surface"
        elif kind == "centrifugal":
            if target not in mesh.volumes:
                raise _fail(f"UNKNOWN_VOLUME_GROUP:{name}:{target}")
            frame = _text(raw, "frame")
            if frame not in mesh.frames:
                raise _fail(f"UNDECLARED_ROTATION_FRAME:{name}:{frame}")
            parameters["group"] = mesh.material_groups[target]
            parameters["frame"] = frame
            parameters["omega_rad_s"] = _number(raw, "omega_rad_s", positive=True)
            group_kind = "surface"
        elif kind == "thermal":
            if target in mesh.volumes:
                parameters["group"] = mesh.material_groups[target]
            elif target in mesh.surfaces:
                parameters["group"] = target
            else:
                raise _fail(f"UNKNOWN_THERMAL_TARGET:{name}:{target}")
            parameters["temperature_k"] = _number(raw, "temperature_k")
            group_kind = "surface"
        else:  # harmonic_spectrum
            parameters["group"] = mesh.resolves_surface(target)
            frequencies = _number_list(raw, "frequencies_hz")
            if not frequencies:
                raise _fail(f"HARMONIC_SPECTRUM_REQUIRES_FREQUENCIES:{name}")
            parameters["frequencies_hz"] = frequencies
            parameters["amplitude"] = _number(raw, "amplitude")
            group_kind = "surface"

        loads.append(
            LoadIngestion(
                name=name,
                kind=kind,
                target=target,
                group_kind=group_kind,
                parameters=parameters,
            )
        )
    return tuple(loads)


def _number_list(data: Mapping[str, object], name: str) -> tuple[float, ...]:
    raw = data.get(name)
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise _fail(f"{name} must be a list of numbers")
    values: list[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise _fail(f"{name} entries must be numbers")
        value = float(item)
        if value != value or value <= 0:
            raise _fail(f"{name} entries must be positive and finite")
        values.append(value)
    if any(a >= b for a, b in zip(values, values[1:], strict=False)):
        raise _fail(f"{name} must be strictly increasing")
    return tuple(values)


def _ingest_contact(
    data: Mapping[str, object], mesh: MeshIngestion
) -> ContactIngestion | None:
    raw = data.get("contact")
    if raw is None or raw is False:
        return None
    if raw is True or isinstance(raw, str):
        mode = "discrete" if raw is True else raw
        raise _fail(f"CONTACT_REQUIRES_DECLARED_SURFACES:{mode}")
    if not isinstance(raw, Mapping):
        raise _fail("contact must be a boolean, mode string, or mapping")
    mode = _text(raw, "mode")
    if mode not in CONTACT_MODES:
        raise _fail(f"UNSUPPORTED_CONTACT_MODE:{mode}")
    slave = _text(raw, "slave")
    master = _text(raw, "master")
    for label, group in (("slave", slave), ("master", master)):
        if group not in mesh.surfaces:
            raise _fail(f"UNKNOWN_CONTACT_SURFACE:{label}:{group}")
    if slave == master:
        raise _fail("CONTACT_SURFACES_MUST_DIFFER")
    return ContactIngestion(mode=mode, slave=slave, master=master)


def ingest_structural_request(data: Mapping[str, object]) -> StructuralRequest:
    """Validate a governed structural request and resolve every reference."""

    analysis = _text(data, "analysis")
    if analysis not in ANALYSES:
        raise _fail(f"INVALID_STRUCTURAL_ANALYSIS:{analysis}")
    prestress_raw = data.get("prestress", False)
    if not isinstance(prestress_raw, bool):
        raise _fail("prestress must be a boolean")
    prestress = prestress_raw
    if prestress and analysis not in {"modal", "harmonic", "transient"}:
        raise _fail("PRESTRESS_REQUIRES_DYNAMIC_ANALYSIS")

    n_modes_raw = data.get("n_modes", 4)
    if isinstance(n_modes_raw, bool) or not isinstance(n_modes_raw, int) or n_modes_raw < 1:
        raise _fail("n_modes must be a positive integer")
    time_end = _number(data, "time_end_s") if "time_end_s" in data else 0.01
    n_steps_raw = data.get("n_steps", 100)
    if isinstance(n_steps_raw, bool) or not isinstance(n_steps_raw, int) or n_steps_raw < 2:
        raise _fail("n_steps must be an integer >= 2")

    mesh = _ingest_mesh(data)
    contact = _ingest_contact(data, mesh)
    materials = _ingest_materials(data, mesh)
    constraints = _ingest_constraints(data, mesh)
    loads = _ingest_loads(data, mesh)
    if not loads:
        raise _fail("LOADS_REQUIRED")
    if analysis in {"modal", "harmonic", "transient"} and not constraints:
        raise _fail("DYNAMIC_ANALYSIS_REQUIRES_CONSTRAINTS")
    if analysis == "harmonic" and not any(
        load.kind == "harmonic_spectrum" for load in loads
    ):
        raise _fail("HARMONIC_ANALYSIS_REQUIRES_SPECTRUM")
    return StructuralRequest(
        analysis=analysis,
        prestress=prestress,
        contact=contact,
        mesh=mesh,
        materials=materials,
        constraints=constraints,
        loads=loads,
        n_modes=int(n_modes_raw),
        time_end_s=time_end,
        n_steps=int(n_steps_raw),
    )


__all__ = [
    "ANALYSES",
    "CONTACT_MODES",
    "CONSTRAINT_MODES",
    "LOAD_KINDS",
    "SUPPORTED_SYMMETRIES",
    "ConstraintIngestion",
    "ContactIngestion",
    "FrameIngestion",
    "InterfaceIngestion",
    "LoadIngestion",
    "MaterialIngestion",
    "MeshIngestion",
    "StructuralRequest",
    "ingest_structural_request",
]
