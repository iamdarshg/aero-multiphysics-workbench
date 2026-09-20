"""Dynamic-stall / unsteady seam: capability-gated, fail-closed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import Provenance, ResultSource

from .contracts import (
    DEFAULT_SOFTWARE,
    HL_UNITS,
    HighLiftFidelity,
    ResultMeta,
    Validity,
)
from .errors import CapabilityUnavailable, HighLiftError, finite

MODEL_UNSTEADY = "vehicle-systems.highlift.dynamic-stall"

NATIVE_UNSTEADY_REQUIREMENT = "native-unsteady-dynamic-stall"

_ASSUMPTIONS = (
    "Quasi-steady screening only; hysteresis loops need a real unsteady backend.",
    "Reduced frequency above 0.05 invalidates the quasi-steady claim.",
)


@dataclass(frozen=True, slots=True)
class DynamicStallRequest:
    request_id: str
    mean_alpha_deg: float
    amplitude_deg: float
    reduced_frequency: float
    mach: float = 0.2
    reynolds: float = 3.0e6

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise HighLiftError("REQUEST_ID_REQUIRED")
        finite(self.mean_alpha_deg, "mean_alpha_deg")
        finite(self.amplitude_deg, "amplitude_deg", minimum=0.0)
        finite(self.reduced_frequency, "reduced_frequency", minimum=0.0)
        finite(self.mach, "mach", minimum=0.0)
        finite(self.reynolds, "reynolds", positive=True)

    def canonical(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "meanAlphaDeg": self.mean_alpha_deg,
            "amplitudeDeg": self.amplitude_deg,
            "reducedFrequency": self.reduced_frequency,
            "mach": self.mach,
            "reynolds": self.reynolds,
        }


@dataclass(frozen=True, slots=True)
class DynamicStallSolution:
    lift_mean: float
    lift_loop_width: float
    moment_undershoot: float
    detail: str

    def __post_init__(self) -> None:
        finite(self.lift_mean, "lift_mean")
        finite(self.lift_loop_width, "lift_loop_width", minimum=0.0)
        finite(self.moment_undershoot, "moment_undershoot")
        if not self.detail.strip():
            raise HighLiftError("SOLUTION_DETAIL_REQUIRED")

    def canonical(self) -> dict[str, Any]:
        return {
            "liftMean": self.lift_mean,
            "liftLoopWidth": self.lift_loop_width,
            "momentUndershoot": self.moment_undershoot,
            "detail": self.detail,
        }


@runtime_checkable
class DynamicStallBackend(Protocol):
    solver_name: str
    solver_version: str

    def solve(self, request: DynamicStallRequest) -> DynamicStallSolution: ...


@dataclass(frozen=True, slots=True)
class DynamicStallResult:
    request_id: str
    solution: DynamicStallSolution
    quasi_steady_valid: bool
    meta: ResultMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "solution": self.solution.canonical(),
            "quasiSteadyValid": self.quasi_steady_valid,
            "meta": self.meta.canonical(),
        }


def quasi_steady_valid(request: DynamicStallRequest) -> bool:
    return request.reduced_frequency <= 0.05 and request.amplitude_deg <= 2.0


def require_dynamic_stall_capability(backend: DynamicStallBackend | None) -> DynamicStallBackend:
    if backend is None:
        raise CapabilityUnavailable(
            f"{NATIVE_UNSTEADY_REQUIREMENT} is not available; "
            "dynamic-stall hysteresis cannot be claimed"
        )
    return backend


def solve_dynamic_stall(
    request: DynamicStallRequest,
    *,
    backend: DynamicStallBackend | None = None,
    run_id: str | None = None,
) -> DynamicStallResult:
    wired = require_dynamic_stall_capability(backend)
    if run_id is None or not run_id.strip():
        raise HighLiftError("dynamic-stall run requires solver identity and a run id")
    if not wired.solver_name.strip() or not wired.solver_version.strip():
        raise HighLiftError("dynamic-stall backend requires solver identity")
    solution = wired.solve(request)
    provenance = Provenance.from_inputs(
        inputs={"request": request.canonical(), "runId": run_id},
        source=ResultSource.NATIVE_SOLVER,
        model=MODEL_UNSTEADY,
        model_version="1.0.0",
        fidelity=HighLiftFidelity.UNSTEADY.core_level(),
        assumptions=_ASSUMPTIONS,
        solver_name=wired.solver_name,
        solver_version=wired.solver_version,
        run_id=run_id,
    )
    meta = ResultMeta(
        source=ResultSource.NATIVE_SOLVER,
        fidelity=HighLiftFidelity.UNSTEADY,
        software=DEFAULT_SOFTWARE,
        units=HL_UNITS,
        validity=Validity(
            passed=True,
            checks={"backend_solved": True},
            detail=solution.detail,
        ),
        input_hash=provenance.inputs_hash,
        provenance=provenance,
    )
    return DynamicStallResult(
        request_id=request.request_id,
        solution=solution,
        quasi_steady_valid=quasi_steady_valid(request),
        meta=meta,
    )


__all__ = [
    "MODEL_UNSTEADY",
    "NATIVE_UNSTEADY_REQUIREMENT",
    "DynamicStallBackend",
    "DynamicStallRequest",
    "DynamicStallResult",
    "DynamicStallSolution",
    "quasi_steady_valid",
    "require_dynamic_stall_capability",
    "solve_dynamic_stall",
]
