"""Native structural mapping for anisotropic laminates and capability gating.

A laminate is mapped into a structural participant as an explicit, ordered ply
stack with a local material frame, element orientation, and per-ply
thickness/offset — never as a single isotropic modulus. Centrifugal/prestress
and pressure/aerodynamic surface loads are carried alongside. Actually running a
native structural engine is capability-gated: when no composite-capable solver
is wired the seam fails closed rather than substituting a screening model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_durability.participants import CapabilityState
from aeroworkbench_materials import LaminateRevision, material_digest

from .provenance import analytical_provenance
from .validity import CapabilityUnavailable, CompositesError, DataUnavailable, finite

__all__ = [
    "COMPOSITES_PARTICIPANTS",
    "CompositesParticipant",
    "CompositesPort",
    "LocalFrame",
    "NativeStructuralReceipt",
    "NativeStructuralRequest",
    "PlyMapping",
    "PrestressState",
    "StructuralMapping",
    "SurfaceLoad",
    "composites_participant_ids",
    "map_laminate_to_structural",
    "native_structural_capability",
    "reject_isotropic_reduction",
    "require_native_structural",
    "solve_native_structural",
]

_ELEMENT_KINDS = ("shell", "solid")
_PORT_TARGETS = frozenset(
    {"structural", "thermal", "durability", "aeroelastic", "mass"}
)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


@dataclass(frozen=True, slots=True)
class LocalFrame:
    """An orthonormal local material frame for a mapped region."""

    frame_id: str
    z_axis: tuple[float, float, float]
    x_axis: tuple[float, float, float]

    def __post_init__(self) -> None:
        if not self.frame_id.strip():
            raise CompositesError("LOCAL_FRAME_ID_REQUIRED")
        for axis in (self.x_axis, self.z_axis):
            for component in axis:
                finite(component, "axis_component")
        xn = _dot(self.x_axis, self.x_axis)
        zn = _dot(self.z_axis, self.z_axis)
        if xn <= 0.0 or zn <= 0.0:
            raise CompositesError("LOCAL_FRAME_AXIS_MUST_BE_NONZERO")
        if abs(xn - 1.0) > 1e-6 or abs(zn - 1.0) > 1e-6:
            raise CompositesError("LOCAL_FRAME_AXIS_MUST_BE_UNIT")
        if abs(_dot(self.x_axis, self.z_axis)) > 1e-6:
            raise CompositesError("LOCAL_FRAME_AXES_MUST_BE_ORTHOGONAL")

    @property
    def y_axis(self) -> tuple[float, float, float]:
        zx, zy, zz = self.z_axis
        xx, xy, xz = self.x_axis
        return (
            zy * xz - zz * xy,
            zz * xx - zx * xz,
            zx * xy - zy * xx,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "frameId": self.frame_id,
            "xAxis": list(self.x_axis),
            "yAxis": list(self.y_axis),
            "zAxis": list(self.z_axis),
        }


@dataclass(frozen=True, slots=True)
class PlyMapping:
    """One ply as the structural participant must represent it."""

    ply_index: int
    material_digest: str
    angle_deg: float
    thickness_m: float
    offset_m: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "plyIndex": self.ply_index,
            "materialDigest": self.material_digest,
            "angleDeg": self.angle_deg,
            "thicknessM": self.thickness_m,
            "offsetM": self.offset_m,
        }


@dataclass(frozen=True, slots=True)
class PrestressState:
    """Centrifugal/prestress condition carried into the structural mapping."""

    rotational_speed_rad_s: float
    reference_radius_m: float
    temperature_k: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        finite(self.rotational_speed_rad_s, "rotational_speed_rad_s")
        finite(self.reference_radius_m, "reference_radius_m", positive=True)
        if self.temperature_k is not None:
            finite(self.temperature_k, "temperature_k", positive=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rotationalSpeedRadS": self.rotational_speed_rad_s,
            "referenceRadiusM": self.reference_radius_m,
            "temperatureK": self.temperature_k,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class SurfaceLoad:
    """An aerodynamic/pressure surface load in a named frame."""

    name: str
    pressure_pa: float
    frame_id: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.frame_id.strip():
            raise CompositesError("SURFACE_LOAD_NAME_AND_FRAME_REQUIRED")
        finite(self.pressure_pa, "pressure_pa")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pressurePa": self.pressure_pa,
            "frameId": self.frame_id,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class StructuralMapping:
    """An anisotropic laminate mapped into a declared structural participant."""

    laminate_identity: str
    laminate_digest: str
    element_kind: str
    frame: LocalFrame
    plies: tuple[PlyMapping, ...]
    total_thickness_m: float
    prestress: PrestressState | None
    pressure_loads: tuple[SurfaceLoad, ...]
    reduction: str | None
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.element_kind not in _ELEMENT_KINDS:
            raise DataUnavailable(f"UNSUPPORTED_ELEMENT_KIND:{self.element_kind}")
        if self.reduction is not None:
            raise CompositesError(
                "ANISOTROPIC_LAMINATE_MUST_NOT_BE_REDUCED_TO_ISOTROPIC"
            )
        if not self.plies:
            raise DataUnavailable("STRUCTURAL_MAPPING_REQUIRES_PLIES")

    def as_dict(self) -> dict[str, Any]:
        return {
            "laminate": self.laminate_identity,
            "laminateDigest": self.laminate_digest,
            "elementKind": self.element_kind,
            "frame": self.frame.as_dict(),
            "plies": [ply.as_dict() for ply in self.plies],
            "totalThicknessM": self.total_thickness_m,
            "prestress": None if self.prestress is None else self.prestress.as_dict(),
            "pressureLoads": [load.as_dict() for load in self.pressure_loads],
            "reduction": self.reduction,
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def reject_isotropic_reduction(requested: str) -> None:
    """Fail closed when a caller asks to collapse anisotropy to isotropy."""

    raise CompositesError(
        f"ANISOTROPIC_LAMINATE_MUST_NOT_BE_REDUCED_TO_ISOTROPIC:{requested}"
    )


def map_laminate_to_structural(
    laminate: LaminateRevision,
    *,
    frame: LocalFrame,
    element_kind: str = "shell",
    prestress: PrestressState | None = None,
    pressure_loads: tuple[SurfaceLoad, ...] = (),
) -> StructuralMapping:
    """Map a laminate to a structural participant without losing anisotropy."""

    if element_kind not in _ELEMENT_KINDS:
        raise DataUnavailable(f"UNSUPPORTED_ELEMENT_KIND:{element_kind}")
    thickness = laminate.total_thickness_m
    half = thickness / 2.0
    offset = -half
    plies: list[PlyMapping] = []
    for index, ply in enumerate(laminate.plies):
        plies.append(
            PlyMapping(
                ply_index=index,
                material_digest=material_digest(ply.material),
                angle_deg=ply.angle_deg,
                thickness_m=ply.thickness_m,
                offset_m=offset,
            )
        )
        offset += ply.thickness_m
    provenance = analytical_provenance(
        "laminate-to-structural-map",
        {
            "laminate": laminate.identity,
            "laminateDigest": _laminate_digest(laminate),
            "elementKind": element_kind,
            "frame": frame.as_dict(),
            "prestress": None if prestress is None else prestress.as_dict(),
            "pressureLoads": [load.as_dict() for load in pressure_loads],
        },
        assumptions=(
            "anisotropic plies travel individually; no isotropic reduction is performed",
            "native execution is a separate capability-gated step",
        ),
    )
    return StructuralMapping(
        laminate_identity=laminate.identity,
        laminate_digest=_laminate_digest(laminate),
        element_kind=element_kind,
        frame=frame,
        plies=tuple(plies),
        total_thickness_m=thickness,
        prestress=prestress,
        pressure_loads=pressure_loads,
        reduction=None,
        provenance=provenance,
    )


def _laminate_digest(laminate: LaminateRevision) -> str:
    from aeroworkbench_materials import laminate_digest

    return laminate_digest(laminate)


@dataclass(frozen=True, slots=True)
class NativeStructuralRequest:
    """A capability-gated native structural analysis request."""

    requirement: str
    solver_name: str
    analysis: str
    mapping: StructuralMapping
    provenance: Provenance

    def __post_init__(self) -> None:
        if not self.requirement.strip() or not self.solver_name.strip():
            raise CompositesError("NATIVE_REQUEST_REQUIRES_REQUIREMENT_AND_SOLVER")
        if not self.analysis.strip():
            raise CompositesError("NATIVE_REQUEST_REQUIRES_ANALYSIS_NAME")

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "solverName": self.solver_name,
            "analysis": self.analysis,
            "mapping": self.mapping.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
        }


@dataclass(frozen=True, slots=True)
class NativeStructuralReceipt:
    """A trusted native execution receipt; never fabricated by this package."""

    solver_name: str
    solver_version: str
    run_id: str
    inputs_hash: str
    values: dict[str, float]
    units: dict[str, str]
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "solverName": self.solver_name,
            "solverVersion": self.solver_version,
            "runId": self.run_id,
            "inputsHash": self.inputs_hash,
            "values": dict(self.values),
            "units": dict(self.units),
            "source": self.provenance.source.value,
        }


@dataclass(frozen=True, slots=True)
class CompositesPort:
    """One typed scalar output port of a composite participant."""

    name: str
    unit: str
    target: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise CompositesError("participant.port.name is required")
        if not self.unit.strip():
            raise CompositesError(f"participant.port.unit required for {self.name}")
        if self.target not in _PORT_TARGETS:
            raise CompositesError(f"participant.port.target unknown:{self.target}")

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "target": self.target}


@dataclass(frozen=True, slots=True)
class CompositesParticipant:
    """One declared generic composite-structural participant."""

    participant_id: str
    component_kind: str
    fidelity_levels: tuple[str, ...]
    outputs: tuple[CompositesPort, ...]
    native_requirement: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise CompositesError("participant.participant_id is required")
        if not self.outputs:
            raise CompositesError(f"participant {self.participant_id} has no outputs")

    def port_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.outputs)

    def ports_for(self, target: str) -> tuple[CompositesPort, ...]:
        return tuple(port for port in self.outputs if port.target == target)

    def as_dict(self) -> dict[str, Any]:
        return {
            "participantId": self.participant_id,
            "componentKind": self.component_kind,
            "fidelityLevels": list(self.fidelity_levels),
            "outputs": [port.as_dict() for port in self.outputs],
            "nativeRequirement": self.native_requirement,
        }


COMPOSITES_PARTICIPANTS: tuple[CompositesParticipant, ...] = (
    CompositesParticipant(
        participant_id="laminate-clt",
        component_kind="laminate",
        fidelity_levels=("analytical",),
        outputs=(
            CompositesPort("a_matrix_n_m", "N/m", "structural"),
            CompositesPort("d_matrix_n_m", "N*m", "structural"),
            CompositesPort("membrane_ex_pa", "Pa", "structural"),
            CompositesPort("areal_mass_kg_m2", "kg/m^2", "mass"),
        ),
    ),
    CompositesParticipant(
        participant_id="ply-failure",
        component_kind="laminate",
        fidelity_levels=("analytical",),
        outputs=(
            CompositesPort("failure_index", "1", "structural"),
            CompositesPort("reserve_factor", "1", "structural"),
        ),
    ),
    CompositesParticipant(
        participant_id="layup-manufacturability",
        component_kind="laminate",
        fidelity_levels=("analytical",),
        outputs=(CompositesPort("manufacturing_pass", "1", "structural"),),
    ),
    CompositesParticipant(
        participant_id="composite-structural-fea",
        component_kind="laminate",
        fidelity_levels=("native",),
        outputs=(
            CompositesPort("displacement_m", "m", "structural"),
            CompositesPort("ply_stress_pa", "Pa", "structural"),
        ),
        native_requirement="code-aster-shell-composite",
    ),
    CompositesParticipant(
        participant_id="composite-modal",
        component_kind="laminate",
        fidelity_levels=("analytical", "native"),
        outputs=(
            CompositesPort("frequency_hz", "1", "aeroelastic"),
            CompositesPort("areal_mass_kg_m2", "kg/m^2", "mass"),
        ),
        native_requirement="code-aster-modal-composite",
    ),
)


def composites_participant_ids() -> tuple[str, ...]:
    return tuple(participant.participant_id for participant in COMPOSITES_PARTICIPANTS)


def native_structural_capability(
    requirement: str, *, present: bool = False
) -> CapabilityState:
    """Report a native composite-structural requirement; absent is blocked."""

    if not requirement.strip():
        raise CompositesError("capability.requirement is required")
    if present:
        return CapabilityState(
            requirement, "engine-present-not-wired", "engine present"
        )
    return CapabilityState(
        requirement,
        "unavailable",
        f"{requirement} is not available; the native level fails closed",
    )


def require_native_structural(requirement: str, *, present: bool = False) -> None:
    """Fail closed unless a wired native composite capability is declared present."""

    raise CapabilityUnavailable(
        native_structural_capability(requirement, present=present).detail
    )


def solve_native_structural(
    request: NativeStructuralRequest, *, present: bool = False
) -> NativeStructuralReceipt:
    """Native composite-structural execution seam; fails closed when absent."""

    detail = native_structural_capability(request.requirement, present=present).detail
    if present:
        detail = (
            f"{request.analysis} native engine '{request.solver_name}' "
            "is not wired for execution"
        )
    raise CapabilityUnavailable(detail)
