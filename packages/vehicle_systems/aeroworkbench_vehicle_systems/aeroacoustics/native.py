"""Native CAA/FW-H capability gating for vehicle aeroacoustics.

Higher-fidelity propagation is optional. A native FW-H (or equivalent) result
is only produced when the caller supplies a real backend plus a run id; every
other native request fails closed with :class:`CapabilityUnavailable`. An
analytical screening is never silently substituted for a requested native run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

from aeroworkbench_optimization.design_space import content_digest

from .contracts import NoiseFidelity, NoiseValidity, native_provenance
from .errors import CapabilityUnavailable, ContractError
from .observers import EnvironmentSpec, FlightState, ObserverSpec, distance_m, doppler_factor
from .propagation import ObserverNoiseLine, ObserverNoiseResult, PropagatableLine

__all__ = [
    "CapabilityState",
    "NativeCAABackend",
    "native_caa_status",
    "propagate_fw_h_native",
    "require_native_caa",
]

NATIVE_REQUIREMENT = "fw-h-propagation"


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Whether a declared native CAA capability is present, and why."""

    requirement: str
    state: str
    available: bool
    detail: str = ""


def native_caa_status(requirement: str, *, present: bool = False) -> CapabilityState:
    """Report native CAA availability without pretending."""

    if not requirement.strip():
        raise CapabilityUnavailable("NATIVE_CAA_REQUIREMENT_REQUIRED", "requirement is required")
    if present:
        return CapabilityState(requirement, "available", True, "native CAA backend is wired")
    return CapabilityState(
        requirement, "unavailable", False, "no native CAA backend is wired"
    )


def require_native_caa(requirement: str, *, present: bool = False) -> CapabilityState:
    """Fail closed unless a native CAA backend is actually wired."""

    state = native_caa_status(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(requirement, state.detail)
    return state


class NativeCAABackend(Protocol):
    """A real external FW-H (or equivalent) propagator returning observer levels."""

    solver_name: str
    solver_version: str

    def propagate(
        self, source_levels_db: Mapping[str, float], *, run_id: str
    ) -> Mapping[str, float]: ...


def propagate_fw_h_native(
    lines: Sequence[PropagatableLine],
    observer: ObserverSpec,
    environment: EnvironmentSpec,
    flight: FlightState,
    *,
    backend: NativeCAABackend | None,
    run_id: str,
    source_fidelity: NoiseFidelity,
) -> ObserverNoiseResult:
    """Native FW-H propagation seam; fails closed without a wired backend."""

    require_native_caa(NATIVE_REQUIREMENT, present=backend is not None)
    if backend is None:
        raise CapabilityUnavailable(NATIVE_REQUIREMENT, "no native CAA backend is wired")
    if not run_id.strip():
        raise CapabilityUnavailable(NATIVE_REQUIREMENT, "a native run id is required")
    if not lines:
        raise ContractError("NO_SOURCE_LINES: at least one declared source line is required")
    produced = backend.propagate(
        {line.label: line.source_level_db for line in lines}, run_id=run_id
    )
    resolved: list[ObserverNoiseLine] = []
    for line in lines:
        if line.label not in produced:
            raise CapabilityUnavailable(
                NATIVE_REQUIREMENT, f"native backend omitted line:{line.label}"
            )
        level = produced[line.label]
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            raise CapabilityUnavailable(NATIVE_REQUIREMENT, f"non-numeric level:{line.label}")
        if not isfinite(float(level)):
            raise CapabilityUnavailable(NATIVE_REQUIREMENT, f"nonfinite level:{line.label}")
        resolved.append(
            ObserverNoiseLine(
                label=line.label,
                contributor=line.contributor,
                source_frequency_hz=line.frequency_hz,
                observed_frequency_hz=line.frequency_hz,
                source_level_db=line.source_level_db,
                observer_level_db=float(level),
            )
        )
    ordered = tuple(sorted(resolved, key=lambda entry: (-entry.observer_level_db, entry.label)))
    total = sum(10.0 ** (entry.observer_level_db / 10.0) for entry in ordered)
    from math import log10

    overall = 10.0 * log10(total) if total > 0.0 else 0.0
    checks = {
        "backend_wired": True,
        "lines_complete": len(ordered) == len(lines),
        "levels_finite": all(isfinite(entry.observer_level_db) for entry in ordered),
    }
    inputs: dict[str, Any] = {
        "lines": [line.canonical() for line in lines],
        "observer": observer.canonical(),
        "environment": environment.canonical(),
        "flight": flight.canonical(),
        "sourceFidelity": source_fidelity.value,
        "runId": run_id,
    }
    slant = distance_m(observer, flight.source_position_m)
    motion = doppler_factor(flight, observer, environment)
    return ObserverNoiseResult(
        observer_id=observer.observer_id,
        lines=ordered,
        overall_level_db=overall,
        distance_m=slant,
        doppler_factor=motion,
        transmission_loss_db=0.0,
        absorption_loss_db=0.0,
        source_fidelity=source_fidelity,
        propagation_fidelity=NoiseFidelity.FW_H_NATIVE,
        validity=NoiseValidity(True, checks, f"native propagation for {len(ordered)} lines"),
        provenance=native_provenance(
            "aeroacoustics.fw-h-propagation",
            inputs,
            solver_name=backend.solver_name,
            solver_version=backend.solver_version,
            run_id=run_id,
            assumptions=(
                "observer levels are owned by the native backend",
                "distance/doppler report the geometric motion state only",
            ),
        ),
    )


def native_inputs_hash(inputs: Mapping[str, Any]) -> str:
    """Deterministic input hash for a native-side payload."""

    return content_digest(dict(inputs))
