"""Native Code_Aster mapping seam for generated structure, capability-gated.

A sized generated structure is mapped to an explicit Code_Aster group/element
model (beams, shells, per-group thickness or section references) — never as a
single lumped element. Actually executing the native structural engine is
capability-gated: when no wired native solver is present the seam fails closed,
returning an ``unavailable`` state and raising
:class:`StructuresCapabilityUnavailable` from execution rather than substituting
a screening model and relabelling it native.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance

from .checks import BEAM_KINDS
from .contracts import analytical_envelope, content_digest
from .errors import StructuralContractError, StructuresCapabilityUnavailable
from .members import StructuralMember
from .sizing import SizedMember, SizedStructure

__all__ = [
    "CodeAsterGroup",
    "CodeAsterStructureMapping",
    "NativeStructureCapability",
    "NativeStructureReceipt",
    "NativeStructureRequest",
    "map_structure_to_code_aster",
    "native_structure_capability",
    "require_native_structure",
    "solve_native_structure",
]

_BEAM_ELEMENT = "POU_D_T"
_SHELL_ELEMENT = "DKT"


@dataclass(frozen=True, slots=True)
class CodeAsterGroup:
    """One native mesh group with its element type, members, and section data."""

    name: str
    element_type: str
    member_ids: tuple[str, ...]
    thickness_m: float | None
    section_shape: str | None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.element_type.strip():
            raise StructuralContractError("CODE_ASTER_GROUP_NEEDS_NAME_AND_ELEMENT")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "elementType": self.element_type,
            "memberIds": list(self.member_ids),
            "thicknessM": self.thickness_m,
            "sectionShape": self.section_shape,
        }


@dataclass(frozen=True, slots=True)
class CodeAsterStructureMapping:
    """A generated structure mapped to a declared Code_Aster model."""

    solver: str
    analysis: str
    element_model: str
    groups: tuple[CodeAsterGroup, ...]
    inputs_hash: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not self.solver.strip() or not self.analysis.strip():
            raise StructuralContractError("CODE_ASTER_MAPPING_NEEDS_SOLVER_AND_ANALYSIS")
        if not self.groups:
            raise StructuralContractError("CODE_ASTER_MAPPING_REQUIRES_GROUPS")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "solver": self.solver,
            "analysis": self.analysis,
            "elementModel": self.element_model,
            "groups": [group.as_dict() for group in self.groups],
            "inputsHash": self.inputs_hash,
        }

    def as_dict(self) -> dict[str, Any]:
        return self.canonical_payload()

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class NativeStructureCapability:
    """The observed availability of one native structural requirement."""

    requirement: str
    state: str
    detail: str

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "state": self.state,
            "available": self.available,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class NativeStructureRequest:
    """A capability-gated native structural analysis request."""

    requirement: str
    solver_name: str
    analysis: str
    mapping: CodeAsterStructureMapping
    inputs_hash: str

    def __post_init__(self) -> None:
        if not self.requirement.strip() or not self.solver_name.strip():
            raise StructuralContractError("NATIVE_REQUEST_NEEDS_REQUIREMENT_AND_SOLVER")
        if not self.analysis.strip():
            raise StructuralContractError("NATIVE_REQUEST_NEEDS_ANALYSIS")

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "solverName": self.solver_name,
            "analysis": self.analysis,
            "mapping": self.mapping.as_dict(),
            "inputsHash": self.inputs_hash,
        }


@dataclass(frozen=True, slots=True)
class NativeStructureReceipt:
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


def _element_for(member: StructuralMember) -> str:
    return _BEAM_ELEMENT if member.kind in BEAM_KINDS else _SHELL_ELEMENT


def map_structure_to_code_aster(
    sized: SizedStructure,
    *,
    solver: str = "code_aster",
    analysis: str = "static",
) -> CodeAsterStructureMapping:
    """Map a sized structure to explicit Code_Aster groups without execution."""

    grouped: dict[tuple[str, str], list[SizedMember]] = {}
    for candidate in sized.members:
        member = candidate.member
        key = (_element_for(member), member.material.identity)
        grouped.setdefault(key, []).append(candidate)
    groups: list[CodeAsterGroup] = []
    for index, (key, candidates) in enumerate(sorted(grouped.items())):
        element_type, material_identity = key
        members = tuple(
            candidate.member.member_id
            for candidate in sorted(candidates, key=lambda item: item.member.member_id)
        )
        thickness = (
            None
            if element_type == _BEAM_ELEMENT
            else max(candidate.member.section.thickness_m for candidate in candidates)
        )
        section_shape = (
            candidates[0].member.section.shape.value
            if element_type == _BEAM_ELEMENT
            else None
        )
        groups.append(
            CodeAsterGroup(
                name=f"{element_type}_{index + 1}",
                element_type=element_type,
                member_ids=members,
                thickness_m=thickness,
                section_shape=section_shape,
            )
        )
    payload = {
        "architectureId": sized.architecture_id,
        "solver": solver,
        "analysis": analysis,
        "groups": [group.as_dict() for group in groups],
    }
    inputs_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    envelope = analytical_envelope(
        model="code-aster-structure-mapping",
        inputs=payload,
        validity=sized.validity,
        assumptions=(
            "explicit beam/shell groups mapped from sized members",
            "no native execution was performed by this mapping",
        ),
    )
    return CodeAsterStructureMapping(
        solver=solver,
        analysis=analysis,
        element_model=f"{_BEAM_ELEMENT}+{_SHELL_ELEMENT}",
        groups=tuple(groups),
        inputs_hash=inputs_hash,
        provenance=envelope.provenance,
    )


def native_structure_capability(
    requirement: str, *, present: bool = False
) -> NativeStructureCapability:
    """Report a native structural requirement; absent is blocked, never faked."""

    if not requirement.strip():
        raise StructuralContractError("NATIVE_CAPABILITY_REQUIREMENT_REQUIRED")
    if present:
        return NativeStructureCapability(
            requirement, "engine-present-not-wired", "engine present but not wired"
        )
    return NativeStructureCapability(
        requirement,
        "unavailable",
        f"{requirement} is not wired; the native structural level fails closed",
    )


def require_native_structure(requirement: str) -> None:
    """Fail closed unless a wired native structural capability is declared present."""

    detail = native_structure_capability(requirement).detail
    raise StructuresCapabilityUnavailable(detail)


def solve_native_structure(
    request: NativeStructureRequest, *, present: bool = False
) -> NativeStructureReceipt:
    """Native structural execution seam; fails closed when absent or unwired."""

    detail = native_structure_capability(request.requirement, present=present).detail
    raise StructuresCapabilityUnavailable(
        f"{request.analysis} native engine '{request.solver_name}' is not wired: {detail}"
    )
