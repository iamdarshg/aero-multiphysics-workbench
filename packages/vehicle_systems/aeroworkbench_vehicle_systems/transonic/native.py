"""Governed native compressible-CFD seam: capability-gated and fail-closed."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .contracts import ResultEnvelope, ShockFeature, Validity, native_envelope
from .errors import TransonicCapabilityUnavailable, TransonicContractError, TransonicValidityError
from .policy import THERMAL_COUPLING_MIN_MACH, promotion_for
from .regime import assert_not_hypersonic

__all__ = [
    "COMPRESSIBLE_EXECUTABLES",
    "CompressibleCapability",
    "NativeCompressibleBackend",
    "NativeCompressibleReceipt",
    "NativeCompressibleRequest",
    "NativeCompressibleSolution",
    "native_compressible_capability",
    "prepare_compressible_case",
    "probe_any_compressible_capability",
    "probe_compressible_capability",
    "require_native_compressible",
    "solve_native_compressible",
]

COMPRESSIBLE_EXECUTABLES: tuple[str, ...] = ("rhoCentralFoam", "simpleFoam", "SU2_CFD", "su2_cfd")
NATIVE_MODEL = "vehicle-systems.transonic.native-rans"


@dataclass(frozen=True, slots=True)
class CompressibleCapability:
    """Observed availability of a native compressible-CFD executable."""

    backend: str
    available: bool
    executable: str | None
    version: str | None
    detail: str

    def canonical(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "executable": self.executable,
            "version": self.version,
            "detail": self.detail,
        }


def probe_compressible_capability(executable: str = "rhoCentralFoam") -> CompressibleCapability:
    """Probe for a native compressible-CFD executable without running it."""

    resolved = shutil.which(executable)
    if resolved is None:
        return CompressibleCapability(
            executable, False, None, None, f"{executable} is not installed; native CFD fails closed"
        )
    return CompressibleCapability(
        executable, True, resolved, None, f"{executable} present at {resolved}"
    )


def probe_any_compressible_capability() -> CompressibleCapability:
    """Probe known OpenFOAM/SU2 executables and return the first present."""

    for executable in COMPRESSIBLE_EXECUTABLES:
        capability = probe_compressible_capability(executable)
        if capability.available:
            return capability
    return probe_compressible_capability(COMPRESSIBLE_EXECUTABLES[0])


def native_compressible_capability(executable: str = "rhoCentralFoam") -> CompressibleCapability:
    """Alias for :func:`probe_compressible_capability` used by promotion seams."""

    return probe_compressible_capability(executable)


def require_native_compressible(executable: str = "rhoCentralFoam") -> CompressibleCapability:
    """Return the capability or fail closed with a typed error."""

    capability = probe_compressible_capability(executable)
    if not capability.available:
        raise TransonicCapabilityUnavailable(
            f"NATIVE_COMPRESSIBLE_UNAVAILABLE:{executable}:{capability.detail}"
        )
    return capability


@dataclass(frozen=True, slots=True)
class NativeCompressibleRequest:
    """A native compressible-CFD request with its mesh/model contract."""

    case_id: str
    mach: float
    geometry_digest: str
    shock_sensitive: bool
    mesh_shock_refined: bool
    turbulence_model: str | None
    thermal_coupling: bool

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.geometry_digest.strip():
            raise TransonicContractError("NATIVE_REQUEST_NEEDS_CASE_AND_GEOMETRY")
        assert_not_hypersonic(self.mach)
        if not isfinite(self.mach) or self.mach < 0.0:
            raise TransonicContractError(f"INVALID_MACH:{self.mach!r}")
        if self.turbulence_model is not None and not self.turbulence_model.strip():
            raise TransonicContractError("NATIVE_TURBULENCE_MODEL_BLANK")

    def canonical(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "mach": self.mach,
            "geometryDigest": self.geometry_digest,
            "shockSensitive": self.shock_sensitive,
            "meshShockRefined": self.mesh_shock_refined,
            "turbulenceModel": self.turbulence_model,
            "thermalCoupling": self.thermal_coupling,
        }


@dataclass(frozen=True, slots=True)
class NativeCompressibleSolution:
    """Outputs a real compressible-CFD backend returns for one request."""

    lift_coefficient: float
    cd_wave: float
    shock_detail: str
    artifacts: tuple[str, ...]
    validity_checks: tuple[tuple[str, bool], ...] = ()
    shock_feature: ShockFeature | None = None

    def __post_init__(self) -> None:
        if not self.shock_detail.strip():
            raise TransonicContractError("NATIVE_SOLUTION_DETAIL_REQUIRED")
        for label, item in (("LIFT", self.lift_coefficient), ("WAVE_DRAG", self.cd_wave)):
            if not isfinite(item):
                raise TransonicContractError(f"NATIVE_SOLUTION_{label}_NOT_FINITE")
        for name, _ in self.validity_checks:
            if not name.strip():
                raise TransonicContractError("NATIVE_VALIDITY_CHECK_NAME_REQUIRED")


@runtime_checkable
class NativeCompressibleBackend(Protocol):
    """A real OpenFOAM/SU2 execution backend (request -> parsed solution)."""

    solver_name: str
    solver_version: str

    def solve(self, request: NativeCompressibleRequest) -> NativeCompressibleSolution: ...


def prepare_compressible_case(
    request: NativeCompressibleRequest, directory: Path
) -> Path:
    """Write the canonical case manifest a native backend consumes."""

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{request.case_id}.compressible-case.json"
    target.write_text(
        json.dumps(request.canonical(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return target


@dataclass(frozen=True, slots=True)
class NativeCompressibleReceipt:
    """A governed native result with mandatory solver identity and envelope."""

    case_id: str
    lift_coefficient: float
    cd_wave: float
    solver_name: str
    solver_version: str
    run_id: str
    validity: Validity
    envelope: ResultEnvelope
    artifacts: tuple[str, ...] = ()
    shock_feature: ShockFeature | None = None

    def canonical(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "liftCoefficient": self.lift_coefficient,
            "cdWave": self.cd_wave,
            "shockFeature": None if self.shock_feature is None else self.shock_feature.canonical(),
            "solver": {
                "name": self.solver_name,
                "version": self.solver_version,
                "runId": self.run_id,
            },
            "validity": self.validity.canonical(),
            "artifacts": list(self.artifacts),
            "envelope": self.envelope.as_dict(),
        }

    @property
    def input_hash(self) -> str:
        return self.envelope.inputs_hash


def solve_native_compressible(
    request: NativeCompressibleRequest,
    *,
    backend: NativeCompressibleBackend | None,
    run_id: str,
) -> NativeCompressibleReceipt:
    """Run the governed native path, or fail closed with no fabricated values."""

    if backend is None:
        raise TransonicCapabilityUnavailable("NATIVE_COMPRESSIBLE_UNAVAILABLE:no backend is wired")
    if not run_id.strip():
        raise TransonicContractError("NATIVE_COMPRESSIBLE_RUN_ID_REQUIRED")
    if not backend.solver_name.strip() or not backend.solver_version.strip():
        raise TransonicContractError("NATIVE_COMPRESSIBLE_SOLVER_IDENTITY_REQUIRED")
    promotion = promotion_for(request.mach, request.shock_sensitive)
    if promotion.needs_native:
        if not request.mesh_shock_refined:
            raise TransonicValidityError("NATIVE_NEEDS_SHOCK_AWARE_MESH:see ADV-PHYS 14 seam")
        if request.turbulence_model is None:
            raise TransonicValidityError("NATIVE_NEEDS_TURBULENCE_MODEL:see ADV-PHYS 12 registry")
    if request.mach >= THERMAL_COUPLING_MIN_MACH and not request.thermal_coupling:
        raise TransonicValidityError("NATIVE_NEEDS_THERMAL_COUPLING:mach>=3")
    solution = backend.solve(request)
    checks = solution.validity_checks or (("native_solution_returned", True),)
    failed = [name for name, ok in checks if not ok]
    validity = Validity(
        not failed,
        dict(checks),
        solution.shock_detail if not failed else f"native checks failed:{','.join(failed)}",
    )
    envelope = native_envelope(
        model=NATIVE_MODEL,
        inputs=dict(request.canonical()) | {"runId": run_id},
        validity=validity,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
        assumptions=("native compressible RANS owns its discretization",),
    )
    return NativeCompressibleReceipt(
        request.case_id,
        solution.lift_coefficient,
        solution.cd_wave,
        backend.solver_name,
        backend.solver_version,
        run_id,
        validity,
        envelope,
        solution.artifacts,
        solution.shock_feature,
    )
