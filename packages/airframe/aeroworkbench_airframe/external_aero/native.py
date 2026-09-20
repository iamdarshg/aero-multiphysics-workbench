"""Governed OpenVSP/VSPAERO native path: capability-gated and fail-closed.

VSPAERO is an optional native capability. This module never manufactures a
native result: it probes for the executable, assembles the canonical case, and
runs a real backend only when one is wired. If the executable is absent, or the
executable is present but no execution backend is wired, the request fails
closed with :class:`ExternalAeroCapabilityUnavailableError`; an analytical or
vortex-lattice result is never relabelled native.

A native result must carry full solver identity, the produced artifacts and a
validity verdict, and its provenance uses the core native-solver contract.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .case import ExternalAeroCase
from .contracts import (
    VSPAERO_VALIDITY_LIMITS,
    AeroCoefficients,
    AeroDerivatives,
    AeroReference,
    AeroValidity,
    ExternalAeroFidelity,
    ExternalAeroResult,
    SpanLoad,
)
from .errors import ExternalAeroCapabilityUnavailableError, ExternalAeroValidationError

VSPAERO_MODEL = "airframe.external_aero.vspaero"
VSPAERO_EXECUTABLES: tuple[str, ...] = ("vspaero", "vspaero.exe", "openvsp", "vsp")


@dataclass(frozen=True, slots=True)
class VspaeroCapability:
    """Observed availability of the native VSPAERO executable (never optimistic)."""

    backend: str
    available: bool
    executable: str | None
    version: str | None
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "available": self.available,
            "executable": self.executable,
            "version": self.version,
            "detail": self.detail,
        }


def probe_vspaero_capability(executable: str = "vspaero") -> VspaeroCapability:
    """Probe for a native VSPAERO executable without running it."""

    resolved = shutil.which(executable)
    if resolved is None:
        return VspaeroCapability(
            backend=executable,
            available=False,
            executable=None,
            version=None,
            detail=f"{executable} is not installed; native VSPAERO fails closed",
        )
    return VspaeroCapability(
        backend=executable,
        available=True,
        executable=resolved,
        version=None,
        detail=f"{executable} present at {resolved}",
    )


def probe_any_vspaero_capability() -> VspaeroCapability:
    """Probe the known VSPAERO/OpenVSP executables and return the first present."""

    for executable in VSPAERO_EXECUTABLES:
        capability = probe_vspaero_capability(executable)
        if capability.available:
            return capability
    return probe_vspaero_capability(VSPAERO_EXECUTABLES[0])


def require_vspaero_capability(executable: str = "vspaero") -> VspaeroCapability:
    """Return the capability or fail closed with a typed error."""

    capability = probe_vspaero_capability(executable)
    if not capability.available:
        raise ExternalAeroCapabilityUnavailableError(
            f"NATIVE_VSPAERO_UNAVAILABLE:{executable}:{capability.detail}"
        )
    return capability


@dataclass(frozen=True, slots=True)
class VspaeroSolution:
    """Outputs a real VSPAERO backend returns for one prepared case."""

    coefficients: AeroCoefficients
    artifacts: tuple[str, ...]
    detail: str
    derivatives: AeroDerivatives | None = None
    distributed_loads: tuple[SpanLoad, ...] = ()
    validity_checks: tuple[tuple[str, bool], ...] = ()

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ExternalAeroValidationError("VSPAERO_SOLUTION_DETAIL_REQUIRED")
        for name, _ in self.validity_checks:
            if not name.strip():
                raise ExternalAeroValidationError("VSPAERO_VALIDITY_CHECK_NAME_REQUIRED")


@runtime_checkable
class VspaeroBackend(Protocol):
    """A real VSPAERO execution backend (case deck -> parsed coefficients)."""

    solver_name: str
    solver_version: str

    def solve(self, case: ExternalAeroCase, reference: AeroReference) -> VspaeroSolution: ...


def prepare_vspaero_case(
    case: ExternalAeroCase, reference: AeroReference, directory: Path
) -> Path:
    """Write the canonical case manifest a VSPAERO backend consumes.

    This is platform case *preparation* only: it records the geometry,
    reference and discretization deterministically. It is not a solver run and
    claims no coefficients.
    """

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{case.case_id}.vspaero-case.json"
    payload: dict[str, object] = {
        "caseId": case.case_id,
        "caseDigest": case.digest,
        "symmetry": case.symmetry,
        "reference": reference.canonical(),
        "surfaces": [surface.canonical_payload() for surface in case.surfaces],
        "controls": [control.canonical_payload() for control in case.controls],
    }
    target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return target


def _native_validity(solution: VspaeroSolution) -> AeroValidity:
    checks = solution.validity_checks or (("native_solution_returned", True),)
    failed = [name for name, ok in checks if not ok]
    return AeroValidity(
        passed=not failed,
        checks=checks,
        detail=solution.detail,
        limits=VSPAERO_VALIDITY_LIMITS,
    )


def solve_vspaero(
    case: ExternalAeroCase,
    reference: AeroReference,
    *,
    backend: VspaeroBackend | None = None,
    run_id: str | None = None,
    executable: str = "vspaero",
) -> ExternalAeroResult:
    """Run the governed native path, or fail closed with no fabricated values."""

    if backend is None:
        capability = probe_any_vspaero_capability()
        if capability.available:
            raise ExternalAeroCapabilityUnavailableError(
                "NATIVE_VSPAERO_EXECUTION_BACKEND_NOT_WIRED:"
                f"{capability.executable}:no parser backend is wired"
            )
        capability = probe_vspaero_capability(executable)
        raise ExternalAeroCapabilityUnavailableError(
            f"NATIVE_VSPAERO_UNAVAILABLE:{executable}:{capability.detail}"
        )
    if run_id is None or not run_id.strip():
        raise ExternalAeroValidationError("NATIVE_VSPAERO_RUN_ID_REQUIRED")
    if not backend.solver_name.strip() or not backend.solver_version.strip():
        raise ExternalAeroValidationError("NATIVE_VSPAERO_SOLVER_IDENTITY_REQUIRED")

    solution = backend.solve(case, reference)
    for label, value in (
        ("CL", solution.coefficients.lift),
        ("CD", solution.coefficients.drag),
        ("CY", solution.coefficients.side),
        ("Cl", solution.coefficients.roll),
        ("Cm", solution.coefficients.pitch),
        ("Cn", solution.coefficients.yaw),
    ):
        if not isfinite(value):
            raise ExternalAeroValidationError(f"NATIVE_VSPAERO_COEFFICIENT_NOT_FINITE:{label}")

    provenance = Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=VSPAERO_MODEL,
        model_version="1.0.0",
        fidelity=FidelityLevel.TRANSIENT,
        inputs={
            "case": case.digest,
            "reference": reference.canonical(),
            "runId": run_id,
        },
        assumptions=(
            "native OpenVSP/VSPAERO lifting-surface solve",
            "validity and artifacts as reported by the native run",
        ),
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
    )
    return ExternalAeroResult(
        result_id=f"{case.case_id}-vspaero",
        fidelity=ExternalAeroFidelity.VSPAERO,
        source=ResultSource.NATIVE_SOLVER,
        reference=reference,
        coefficients=solution.coefficients,
        derivatives=solution.derivatives,
        distributed_loads=solution.distributed_loads,
        validity=_native_validity(solution),
        artifacts=solution.artifacts,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
        provenance=provenance,
    )


def vspaero_case_manifest(case: ExternalAeroCase, reference: AeroReference) -> dict[str, Any]:
    """Canonical case manifest as a plain mapping (same content as the file)."""

    return {
        "caseId": case.case_id,
        "caseDigest": case.digest,
        "symmetry": case.symmetry,
        "reference": reference.canonical(),
        "surfaces": [surface.canonical_payload() for surface in case.surfaces],
        "controls": [control.canonical_payload() for control in case.controls],
    }


__all__ = [
    "VSPAERO_EXECUTABLES",
    "VSPAERO_MODEL",
    "VspaeroBackend",
    "VspaeroCapability",
    "VspaeroSolution",
    "prepare_vspaero_case",
    "probe_any_vspaero_capability",
    "probe_vspaero_capability",
    "require_vspaero_capability",
    "solve_vspaero",
    "vspaero_case_manifest",
]
