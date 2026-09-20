"""Capability-gated native high-lift seam: RANS/unsteady promotion, fail-closed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

from .contracts import (
    DEFAULT_SOFTWARE,
    HL_UNITS,
    HighLiftFidelity,
    ResultMeta,
    SoftwareIdentity,
    Validity,
    result_meta,
)
from .errors import CapabilityUnavailable, HighLiftError
from .wing import FiniteWingResult

NATIVE_HIGHLIFT_RANS_REQUIREMENT = "native-rans-highlift"
MESH_PROMOTION_REQUIREMENT = "meshing-rans-promotion"

MODEL_PROMOTION = "vehicle-systems.highlift.rans-promotion"


@dataclass(frozen=True, slots=True)
class NativeHighLiftStatus:
    available: bool
    backend: str | None
    requirement: str
    meta: ResultMeta


def native_highlift_status(
    *, present: bool = False, backend: str | None = None
) -> NativeHighLiftStatus:
    meta = result_meta(
        model="vehicle-systems.highlift.native-status",
        inputs={"present": present, "backend": backend},
        valid=present,
        checks={"native_backend_available": present},
        detail="native high-lift capability probe",
        fidelity=HighLiftFidelity.NATIVE if present else HighLiftFidelity.ATTACHED_LINEAR,
        units=HL_UNITS,
    )
    return NativeHighLiftStatus(
        available=present,
        backend=backend,
        requirement=NATIVE_HIGHLIFT_RANS_REQUIREMENT,
        meta=meta,
    )


def require_native_highlift(*, present: bool = False) -> None:
    if not present:
        raise CapabilityUnavailable(
            f"{NATIVE_HIGHLIFT_RANS_REQUIREMENT} is not available; "
            "a native high-lift result cannot be claimed"
        )


@dataclass(frozen=True, slots=True)
class RansPromotionTicket:
    ticket_id: str
    wing_state: dict[str, Any]
    mesh_requirement: str
    backend: str
    run_id: str
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "ticketId": self.ticket_id,
            "wingState": dict(self.wing_state),
            "meshRequirement": self.mesh_requirement,
            "backend": self.backend,
            "runId": self.run_id,
            "meta": self.meta.canonical(),
        }


def promote_to_rans(
    wing: FiniteWingResult,
    config_digest: str,
    *,
    backend: str | None = None,
    run_id: str | None = None,
) -> RansPromotionTicket:
    if backend is None or not backend.strip():
        raise CapabilityUnavailable(
            f"{NATIVE_HIGHLIFT_RANS_REQUIREMENT} is not available; "
            "near-stall promotion requested but no RANS backend is wired"
        )
    if run_id is None or not run_id.strip():
        raise HighLiftError("RANS promotion requires a run id")
    if not config_digest.strip():
        raise HighLiftError("RANS promotion requires a configuration digest")
    meta = result_meta(
        model=MODEL_PROMOTION,
        inputs={
            "wing": wing.canonical(),
            "configDigest": config_digest,
            "backend": backend,
            "runId": run_id,
        },
        valid=True,
        fidelity=HighLiftFidelity.NATIVE,
        checks={"promotion_issued": True},
        detail=f"near-stall state promoted to {backend} via {MESH_PROMOTION_REQUIREMENT}",
        assumptions=("Promotion is a ticket, not a result; coefficients await the native run.",),
        source=ResultSource.ANALYTICAL,
    )
    return RansPromotionTicket(
        ticket_id=f"rans-{config_digest[:12]}-{run_id}",
        wing_state=wing.canonical(),
        mesh_requirement=MESH_PROMOTION_REQUIREMENT,
        backend=backend,
        run_id=run_id,
        meta=meta,
    )


def native_highlift_provenance(
    *,
    inputs: dict[str, Any],
    solver_name: str,
    solver_version: str,
    run_id: str,
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
) -> Provenance:
    if not solver_name.strip() or not solver_version.strip() or not run_id.strip():
        raise HighLiftError("native provenance requires solver identity and a run id")
    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.NATIVE_SOLVER,
        model="vehicle-systems.highlift.native-rans",
        model_version=software.version,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        assumptions=("Real RANS/unsteady run; validity as reported by the native run.",),
    )


def native_validity() -> Validity:
    return Validity(
        passed=True,
        checks={"native_solution_returned": True},
        detail="validity as reported by the native run",
    )


__all__ = [
    "MESH_PROMOTION_REQUIREMENT",
    "MODEL_PROMOTION",
    "NATIVE_HIGHLIFT_RANS_REQUIREMENT",
    "NativeHighLiftStatus",
    "RansPromotionTicket",
    "native_highlift_provenance",
    "native_highlift_status",
    "native_validity",
    "promote_to_rans",
    "require_native_highlift",
]
