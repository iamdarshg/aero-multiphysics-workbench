"""Capability-gated native ground-dynamics / structural backend seam.

The analytical ground dynamics in this package never pretend to be a native
multibody or structural engine. A caller that needs a native ground-dynamics or
gear-structural solve goes through this seam; when the backend is absent the
request fails closed and no result is fabricated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

from .contracts import (
    DEFAULT_SOFTWARE,
    LG_UNITS,
    LandingGearFidelity,
    ResultMeta,
    SoftwareIdentity,
    result_meta,
)
from .errors import CapabilityUnavailable, LandingGearError

NATIVE_GROUND_DYNAMICS_REQUIREMENT = "native-ground-dynamics"
NATIVE_GEAR_STRUCTURE_REQUIREMENT = "gear-structural-fea"


@dataclass(frozen=True, slots=True)
class NativeGroundDynamicsStatus:
    """Whether a native ground-dynamics backend is wired."""

    available: bool
    backend: str | None
    requirement: str
    meta: ResultMeta


def native_ground_dynamics_status(
    *, present: bool = False, backend: str | None = None
) -> NativeGroundDynamicsStatus:
    """Probe the native ground-dynamics backend without running it."""

    meta = result_meta(
        model="vehicle-systems.landing-gear.native-status",
        inputs={"present": present, "backend": backend},
        valid=present,
        checks={"native_backend_available": present},
        detail="native ground-dynamics capability probe",
        fidelity=LandingGearFidelity.NATIVE if present else LandingGearFidelity.ANALYTICAL,
        units=LG_UNITS,
    )
    return NativeGroundDynamicsStatus(
        available=present,
        backend=backend,
        requirement=NATIVE_GROUND_DYNAMICS_REQUIREMENT,
        meta=meta,
    )


def require_native_ground_dynamics(*, present: bool = False) -> None:
    """Fail closed when a native ground-dynamics backend is requested but absent."""

    if not present:
        raise CapabilityUnavailable(
            f"{NATIVE_GROUND_DYNAMICS_REQUIREMENT} is not available; "
            "a native ground-dynamics result cannot be claimed"
        )


def require_native_gear_structure(*, present: bool = False) -> None:
    """Fail closed when a native gear structural engine is requested but absent."""

    if not present:
        raise CapabilityUnavailable(
            f"{NATIVE_GEAR_STRUCTURE_REQUIREMENT} is not available; "
            "gear structural margins cannot be claimed"
        )


def native_ground_dynamics_provenance(
    *,
    inputs: Mapping[str, Any],
    solver_name: str,
    solver_version: str,
    run_id: str,
    assumptions: Sequence[str] = (),
    software: SoftwareIdentity = DEFAULT_SOFTWARE,
) -> Provenance:
    """Native provenance for a real external run; identity is mandatory."""

    if not solver_name.strip() or not solver_version.strip() or not run_id.strip():
        raise LandingGearError("native provenance requires solver identity and a run id")
    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.NATIVE_SOLVER,
        model="vehicle-systems.landing-gear.native-ground-dynamics",
        model_version=software.version,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        assumptions=tuple(assumptions),
    )


__all__ = [
    "NATIVE_GEAR_STRUCTURE_REQUIREMENT",
    "NATIVE_GROUND_DYNAMICS_REQUIREMENT",
    "NativeGroundDynamicsStatus",
    "native_ground_dynamics_provenance",
    "native_ground_dynamics_status",
    "require_native_gear_structure",
    "require_native_ground_dynamics",
]
