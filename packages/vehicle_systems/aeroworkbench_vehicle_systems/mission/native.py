"""Native mission capability gating.

A native mission coordinator is an optional capability. Until a real backend is
wired every native request fails closed with :class:`CapabilityUnavailable`; a
reduced-map or analytical evaluation is never silently substituted for a
requested native run. When a backend is present its solver identity is recorded
in the result provenance.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import MissionFidelity, MissionMeta, native_provenance, result_meta
from .errors import CapabilityUnavailable
from .segments import MissionSpec

__all__ = [
    "CapabilityState",
    "NativeMissionBackend",
    "NativeMissionOutcome",
    "native_mission_status",
    "require_native_mission",
    "solve_native_mission",
]


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Whether a declared native mission capability is present, and why."""

    requirement: str
    state: str
    available: bool
    detail: str = ""


def native_mission_status(requirement: str, *, present: bool = False) -> CapabilityState:
    """Report native mission availability without pretending."""

    if not requirement.strip():
        raise CapabilityUnavailable("NATIVE_MISSION_REQUIREMENT_REQUIRED")
    if present:
        return CapabilityState(requirement, "available", True, "native mission backend is wired")
    return CapabilityState(requirement, "unavailable", False, "no native mission backend is wired")


def require_native_mission(requirement: str, *, present: bool = False) -> CapabilityState:
    """Fail closed unless a native mission backend is actually wired."""

    state = native_mission_status(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(f"NATIVE_MISSION_UNAVAILABLE:{requirement}")
    return state


class NativeMissionBackend(Protocol):
    """A real external mission coordinator returning mission-level metrics."""

    solver_name: str
    solver_version: str

    def simulate(
        self,
        spec: MissionSpec,
        controls: Mapping[str, float],
        *,
        run_id: str,
    ) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class NativeMissionOutcome:
    """A native mission result with mandatory solver identity and provenance."""

    mission_id: str
    metrics: Mapping[str, float]
    meta: MissionMeta

    @property
    def source(self) -> str:
        return self.meta.source.value

    def canonical(self) -> dict[str, Any]:
        return {"missionId": self.mission_id, "metrics": dict(sorted(self.metrics.items())),
                "meta": self.meta.as_dict()}


def solve_native_mission(
    spec: MissionSpec,
    controls: Mapping[str, float],
    *,
    backend: NativeMissionBackend | None,
    run_id: str,
) -> NativeMissionOutcome:
    """Run a native mission coordinator, or fail closed with no backend."""

    if backend is None:
        raise CapabilityUnavailable("NATIVE_MISSION_UNAVAILABLE:native-mission")
    if not run_id.strip():
        raise CapabilityUnavailable("NATIVE_MISSION_NEEDS_RUN_ID")
    produced = backend.simulate(spec, controls, run_id=run_id)
    metrics = {str(key): float(value) for key, value in produced.items()}
    provenance = native_provenance(
        "mission-native",
        {"mission": spec.digest(), "controls": dict(sorted(controls.items()))},
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        run_id=run_id,
        assumptions=("native coordinator owns its internal discretization",),
    )
    meta = result_meta(
        model="mission-native",
        inputs={"mission": spec.digest(), "runId": run_id},
        valid=True,
        fidelity=MissionFidelity.NATIVE,
        provenance=provenance,
    )
    return NativeMissionOutcome(mission_id=spec.mission_id, metrics=metrics, meta=meta)
