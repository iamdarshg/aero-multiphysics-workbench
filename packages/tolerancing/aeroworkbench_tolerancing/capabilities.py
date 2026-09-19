"""Capability gates for native tolerance/assembly evaluation.

Native interference checking and native metrology are optional capabilities.
When one is not wired the request fails closed with
:class:`CapabilityUnavailable`; a screening tolerance model is never substituted
for the requested native capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .contracts import ResultEnvelope, SoftwareIdentity
from .errors import CapabilityUnavailable

__all__ = [
    "CapabilityState",
    "NativeInspectionBackend",
    "NativeInterferenceResult",
    "native_interference_capability",
    "native_interference_check",
    "require_native_interference",
]


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Whether a declared native capability is present, and why."""

    requirement: str
    state: str
    available: bool
    detail: str = ""


def _state(requirement: str, *, present: bool, kind: str) -> CapabilityState:
    if not requirement.strip():
        raise CapabilityUnavailable("CAPABILITY_REQUIREMENT_REQUIRED")
    if present:
        return CapabilityState(requirement, "available", True, f"{kind} backend is wired")
    return CapabilityState(requirement, "unavailable", False, f"no {kind} backend is wired")


def native_interference_capability(
    requirement: str = "native-interference-check", *, present: bool = False
) -> CapabilityState:
    """Report native interference-check availability without pretending."""

    return _state(requirement, present=present, kind="native")


def require_native_interference(
    requirement: str = "native-interference-check", *, present: bool = False
) -> CapabilityState:
    """Fail closed unless a native interference backend is actually wired."""

    state = native_interference_capability(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(f"NATIVE_CAPABILITY_UNAVAILABLE:{requirement}")
    return state


class NativeInspectionBackend(Protocol):
    """A real external engine that reports native overlap/metrology values."""

    solver_name: str
    solver_version: str

    def interference(
        self, request: Mapping[str, Any], *, run_id: str
    ) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class NativeInterferenceResult:
    """Native interference overlaps for a set of part pairs."""

    request_id: str
    solver_name: str
    solver_version: str
    run_id: str
    overlaps: tuple[tuple[str, str, float], ...]
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "solverName": self.solver_name,
            "solverVersion": self.solver_version,
            "runId": self.run_id,
            "overlaps": [
                {"pair": [left, right], "overlapM3": value}
                for left, right, value in self.overlaps
            ],
            "envelope": self.envelope.as_dict(),
        }


def native_interference_check(
    request: Mapping[str, Any],
    *,
    backend: NativeInspectionBackend | None,
    run_id: str,
    request_id: str,
) -> NativeInterferenceResult:
    """Run a native interference check, or fail closed with no backend."""

    if backend is None:
        raise CapabilityUnavailable("NATIVE_CAPABILITY_UNAVAILABLE:native-interference-check")
    if not run_id.strip():
        raise CapabilityUnavailable("NATIVE_INTERFERENCE_NEEDS_RUN_ID")
    if not request_id.strip():
        raise CapabilityUnavailable("NATIVE_INTERFERENCE_NEEDS_REQUEST_ID")
    produced = dict(backend.interference(dict(request), run_id=run_id))
    overlaps: list[tuple[str, str, float]] = []
    for key, value in sorted(produced.items()):
        if "|" not in key:
            raise CapabilityUnavailable(f"NATIVE_INTERFERENCE_BAD_PAIR:{key}")
        left, right = key.split("|", 1)
        overlaps.append((left, right, float(value)))
    provenance = Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model="advphys10-native-interference",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={"request": dict(request), "requestId": request_id},
        assumptions=(
            "native interference overlap reported by the wired backend",
            "core fidelity enum has no generic native level; source is native_solver",
        ),
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
    )
    envelope = ResultEnvelope(
        source=provenance.source.value,
        fidelity="native",
        unit="m3",
        validity="valid",
        inputs_hash=provenance.inputs_hash,
        software=SoftwareIdentity(),
        provenance=provenance,
        assumptions=tuple(provenance.assumptions),
    )
    return NativeInterferenceResult(
        request_id=request_id,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
        overlaps=tuple(overlaps),
        envelope=envelope,
    )
