"""Native closed-loop capability gating.

A native closed-loop coordinator (AIRFRAME flight dynamics or a JSBSim seam)
is an optional capability. Until a real backend is wired every native request
fails closed; a screening closed-loop evaluation is never silently
substituted for a requested native run.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .closedloop import ClosedLoopSpec
from .contracts import ControlFidelity, ControlMeta, native_provenance, result_meta
from .errors import CapabilityUnavailable

__all__ = [
    "CapabilityState",
    "NativeClosedLoopBackend",
    "NativeClosedLoopOutcome",
    "native_closed_loop_status",
    "require_native_closed_loop",
    "solve_native_closed_loop",
]


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Whether a declared native closed-loop capability is present, and why."""

    requirement: str
    state: str
    available: bool
    detail: str = ""


def native_closed_loop_status(requirement: str, *, present: bool = False) -> CapabilityState:
    """Report native closed-loop availability without pretending."""
    if not requirement.strip():
        raise CapabilityUnavailable("NATIVE_CLOSED_LOOP_REQUIREMENT_REQUIRED")
    if present:
        return CapabilityState(
            requirement, "available", True, "native closed-loop backend is wired"
        )
    return CapabilityState(
        requirement, "unavailable", False, "no native closed-loop backend is wired"
    )


def require_native_closed_loop(requirement: str, *, present: bool = False) -> CapabilityState:
    """Fail closed unless a native closed-loop backend is actually wired."""
    state = native_closed_loop_status(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(f"NATIVE_CLOSED_LOOP_UNAVAILABLE:{requirement}")
    return state


class NativeClosedLoopBackend(Protocol):
    """A real external closed-loop coordinator returning loop-level metrics."""

    solver_name: str
    solver_version: str

    def simulate(
        self,
        spec: ClosedLoopSpec,
        commands: Mapping[str, float],
        *,
        run_id: str,
    ) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class NativeClosedLoopOutcome:
    """A native closed-loop result with mandatory solver identity and provenance."""

    loop_id: str
    metrics: Mapping[str, float]
    meta: ControlMeta

    def canonical(self) -> dict[str, Any]:
        return {
            "loopId": self.loop_id,
            "metrics": dict(sorted(self.metrics.items())),
            "meta": self.meta.as_dict(),
        }


def solve_native_closed_loop(
    spec: ClosedLoopSpec,
    commands: Mapping[str, float],
    *,
    backend: NativeClosedLoopBackend | None,
    run_id: str,
) -> NativeClosedLoopOutcome:
    """Run a native closed-loop coordinator, or fail closed with no backend."""
    if backend is None:
        raise CapabilityUnavailable("NATIVE_CLOSED_LOOP_UNAVAILABLE:native-closed-loop")
    if not run_id.strip():
        raise CapabilityUnavailable("NATIVE_CLOSED_LOOP_NEEDS_RUN_ID")
    produced = backend.simulate(spec, commands, run_id=run_id)
    metrics = {str(key): float(value) for key, value in produced.items()}
    provenance = native_provenance(
        "closed-loop-native",
        {"spec": spec.canonical(), "commands": dict(sorted(commands.items()))},
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
        assumptions=("native coordinator owns its internal discretization",),
    )
    meta = result_meta(
        model="closed-loop-native",
        inputs={"spec": spec.canonical(), "runId": run_id},
        valid=True,
        fidelity=ControlFidelity.NATIVE,
        provenance=provenance,
    )
    loop_id = "-".join(sorted(loop.plant.axis for loop in spec.loops))
    return NativeClosedLoopOutcome(loop_id=loop_id, metrics=metrics, meta=meta)
