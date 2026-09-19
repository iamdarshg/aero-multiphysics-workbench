"""Icing seam with a staged fidelity contract.

Three stages are represented explicitly and can never be confused:

1. ``ENVELOPE`` -- a simple accretion/roughness envelope from the declared
   exposure (screening only).
2. ``GEOMETRY`` -- an explicit geometry-change revision derived from the
   envelope, which invalidates downstream geometry/mesh/analysis results.
3. ``NATIVE`` -- an adapter to a real icing CFD/tool, capability-gated and
   fail-closed when the engine is absent.

An empirical envelope is never presented as high-fidelity ice accretion.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from aeroworkbench_core.types import Provenance

from .contracts import (
    DEFAULT_SOFTWARE,
    EnvironmentalFidelity,
    SoftwareIdentity,
    Validity,
)
from .degradation import (
    DEFAULT_ENVELOPE_MODEL,
    EnvelopeModel,
    evaluate_degradation,
)
from .errors import CapabilityUnavailable, EnvironmentalError, ValidityError
from .exposure import EnvironmentState, ExposureKind, ExposureSpec
from .provenance import analytical_provenance, native_provenance
from .units import Quantity

_REQUIREMENT = "ice-accretion-cfd"


def _require_hex(value: str, label: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise EnvironmentalError(f"{label} must be a 64-char lowercase hex hash")
    return value


@dataclass(frozen=True, slots=True)
class IceAccretionRequest:
    """An icing request bound to a declared exposure and base geometry."""

    request_id: str
    exposure: ExposureSpec
    geometry_hash: str

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise EnvironmentalError("icing.requestId is required")
        if self.exposure.kind is not ExposureKind.ICING:
            raise EnvironmentalError("icing.exposure must be an icing exposure")
        _require_hex(self.geometry_hash, "icing.geometryHash")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "exposure": self.exposure.canonical_payload(),
            "geometryHash": self.geometry_hash,
        }


@dataclass(frozen=True, slots=True)
class IceAccretionResult:
    """Accreted ice state with the fidelity of the producing model."""

    request_id: str
    fidelity: EnvironmentalFidelity
    accreted_areal_mass: Quantity
    ice_thickness: Quantity
    roughness_increment: Quantity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE
    warnings: tuple[str, ...] = ()

    def units(self) -> dict[str, str]:
        return {
            "accreted_areal_mass": self.accreted_areal_mass.unit,
            "ice_thickness": self.ice_thickness.unit,
            "roughness_increment": self.roughness_increment.unit,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "fidelity": self.fidelity.value,
            "accretedArealMass": self.accreted_areal_mass.canonical(),
            "iceThickness": self.ice_thickness.canonical(),
            "roughnessIncrement": self.roughness_increment.canonical(),
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": self.software.canonical(),
            "warnings": list(self.warnings),
        }


def evaluate_ice_accretion_envelope(
    request: IceAccretionRequest,
    *,
    model: EnvelopeModel = DEFAULT_ENVELOPE_MODEL,
) -> IceAccretionResult:
    """Stage 1: simple accretion/roughness envelope (screening only)."""

    environment = EnvironmentState(
        environment_id=request.request_id,
        revision=0,
        atmosphere_model="declared-reference",
        exposures=(request.exposure,),
    )
    state = evaluate_degradation(environment, model=model)
    deltas = {modifier.quantity_name: modifier.delta for modifier in state.modifiers}
    areal = deltas.get("ice_areal_mass")
    thickness = deltas.get("leading_edge_roughness_increment")
    roughness = deltas.get("surface_roughness_increment")
    if areal is None or thickness is None or roughness is None:
        raise ValidityError("icing.envelopeMissingModifier")
    provenance = analytical_provenance(
        f"environmental.icing.envelope.{model.model_id}@{model.revision}",
        {"request": request.canonical_payload(), "model": model.canonical_payload()},
        assumptions=(
            "screening accretion envelope; not validated ice-accretion physics",
            "use the geometry-change stage or a native icing solver for design",
        ),
    )
    return IceAccretionResult(
        request_id=request.request_id,
        fidelity=EnvironmentalFidelity.ENVELOPE,
        accreted_areal_mass=areal,
        ice_thickness=thickness,
        roughness_increment=roughness,
        validity=Validity(
            passed=True,
            checks={"envelope_modifiers_present": True},
            detail=f"icing screening envelope {model.model_id}@{model.revision}",
        ),
        provenance=provenance,
        warnings=(
            "EMPIRICAL ENVELOPE: not high-fidelity ice accretion; do not use for certification",
        ),
    )


@dataclass(frozen=True, slots=True)
class GeometryChange:
    """A new geometry revision produced by a degradation/icing model."""

    geometry_hash: str
    previous_hash: str
    revision: int
    changed_sections: tuple[str, ...]
    changes: tuple[tuple[str, Quantity], ...]
    fidelity: EnvironmentalFidelity
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "geometryHash": self.geometry_hash,
            "previousHash": self.previous_hash,
            "revision": self.revision,
            "changedSections": list(self.changed_sections),
            "changes": {name: quantity.canonical() for name, quantity in self.changes},
            "fidelity": self.fidelity.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _revise_hash(previous: str, digest: str, label: str) -> str:
    return hashlib.sha256(f"{label}:{previous}:{digest}".encode()).hexdigest()


def ice_geometry_change(
    result: IceAccretionResult,
    *,
    previous_hash: str,
    revision: int,
) -> GeometryChange:
    """Stage 2: explicit geometry change from an envelope ice state."""

    if result.fidelity is EnvironmentalFidelity.NATIVE:
        raise EnvironmentalError("icing.nativeResultAlreadyHasGeometry")
    _require_hex(previous_hash, "icing.previousHash")
    provenance = analytical_provenance(
        "environmental.icing.geometry-change",
        {"result": result.canonical_payload(), "previousHash": previous_hash},
        assumptions=("geometry revision derived from the screening envelope",),
    )
    return GeometryChange(
        geometry_hash=_revise_hash(previous_hash, str(provenance.inputs_hash), "ice"),
        previous_hash=previous_hash,
        revision=revision,
        changed_sections=("geometry",),
        changes=(
            ("leading_edge_roughness_increment", result.roughness_increment),
            ("ice_thickness", result.ice_thickness),
        ),
        fidelity=EnvironmentalFidelity.GEOMETRY,
        validity=Validity(
            passed=True,
            checks={"revision_advanced": revision > 0},
            detail="geometry-change model",
        ),
        provenance=provenance,
    )


class NativeIcingBackend(Protocol):
    """Adapter interface for a real icing CFD/tool."""

    solver_name: str
    solver_version: str

    def accrete(
        self, request: IceAccretionRequest, model: EnvelopeModel
    ) -> Mapping[str, float]:  # pragma: no cover - structural protocol
        ...


@dataclass(frozen=True, slots=True)
class IcingCapability:
    """Capability-gated availability of a native icing engine."""

    requirement: str
    state: str
    detail: str

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def canonical(self) -> dict[str, str]:
        return {"requirement": self.requirement, "state": self.state, "detail": self.detail}


def native_icing_capability(*, present: bool = False) -> IcingCapability:
    """Report native icing availability; absent is explicitly blocked."""

    if present:
        return IcingCapability(_REQUIREMENT, "ready", "native icing engine wired")
    return IcingCapability(
        _REQUIREMENT,
        "unavailable",
        f"{_REQUIREMENT} is not available; the native stage fails closed",
    )


def solve_native_icing(
    request: IceAccretionRequest,
    *,
    backend: NativeIcingBackend | None = None,
    run_id: str | None = None,
    model: EnvelopeModel = DEFAULT_ENVELOPE_MODEL,
) -> IceAccretionResult:
    """Stage 3: native adapter, capability-gated and fail-closed.

    Without a wired backend this raises :class:`CapabilityUnavailable`; it never
    substitutes the envelope and relabels it native.
    """

    if backend is None:
        raise CapabilityUnavailable(native_icing_capability().detail)
    scalars = backend.accrete(request, model)
    try:
        areal = float(scalars["accreted_areal_mass_kg_m2"])
        thickness = float(scalars["ice_thickness_m"])
        roughness = float(scalars["roughness_increment_m"])
    except KeyError as exc:
        raise CapabilityUnavailable(
            f"native icing backend missing scalar:{exc.args[0]}"
        ) from None
    for name, value in (("areal", areal), ("thickness", thickness), ("roughness", roughness)):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValidityError(f"ice.nativeNonFinite:{name}")
    provenance = native_provenance(
        "environmental.icing.native",
        {"request": request.canonical_payload()},
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id or f"icing-{request.request_id}",
        assumptions=("native icing engine result",),
    )
    return IceAccretionResult(
        request_id=request.request_id,
        fidelity=EnvironmentalFidelity.NATIVE,
        accreted_areal_mass=Quantity(areal, "kg/m2"),
        ice_thickness=Quantity(thickness, "m"),
        roughness_increment=Quantity(roughness, "m"),
        validity=Validity(passed=True, checks={"native_scalars_present": True}, detail="native"),
        provenance=provenance,
    )


__all__ = [
    "GeometryChange",
    "IceAccretionRequest",
    "IceAccretionResult",
    "IcingCapability",
    "NativeIcingBackend",
    "evaluate_ice_accretion_envelope",
    "ice_geometry_change",
    "native_icing_capability",
    "solve_native_icing",
]
