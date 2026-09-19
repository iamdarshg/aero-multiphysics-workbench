"""Capability gates for native sampling and neural surrogates.

Native physics and trained neural networks are optional capabilities. When one
is not wired the request fails closed with :class:`CapabilityUnavailable`; a
screening surrogate is never substituted for the requested native physics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .contracts import MapFidelity, SampleKind
from .errors import CapabilityUnavailable

if TYPE_CHECKING:
    from .map import MapSample

__all__ = [
    "CapabilityState",
    "NativeSamplingBackend",
    "native_sample",
    "native_sampling_capability",
    "neural_capability",
    "require_native_sampling",
    "require_neural",
]


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Whether a declared capability is present, and why."""

    requirement: str
    state: str
    available: bool
    detail: str = ""


def _state(requirement: str, *, present: bool, kind: str) -> CapabilityState:
    if not requirement.strip():
        raise ValueError("CAPABILITY_REQUIREMENT_REQUIRED")
    if present:
        return CapabilityState(requirement, "available", True, f"{kind} backend is wired")
    return CapabilityState(requirement, "unavailable", False, f"no {kind} backend is wired")


def native_sampling_capability(requirement: str, *, present: bool = False) -> CapabilityState:
    """Report native high-fidelity sampling availability without pretending."""

    return _state(requirement, present=present, kind="native")


def require_native_sampling(requirement: str, *, present: bool = False) -> CapabilityState:
    """Fail closed unless a native sampling backend is actually wired."""

    state = native_sampling_capability(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(f"NATIVE_CAPABILITY_UNAVAILABLE:{requirement}")
    return state


def neural_capability(
    requirement: str = "neural-surrogate", *, present: bool = False
) -> CapabilityState:
    """Report neural-surrogate availability without pretending."""

    return _state(requirement, present=present, kind="neural")


def require_neural(
    requirement: str = "neural-surrogate", *, present: bool = False
) -> CapabilityState:
    """Fail closed unless a neural backend is actually wired."""

    state = neural_capability(requirement, present=present)
    if not state.available:
        raise CapabilityUnavailable(f"NEURAL_CAPABILITY_UNAVAILABLE:{requirement}")
    return state


class NativeSamplingBackend(Protocol):
    """A real external engine that returns high-fidelity samples."""

    solver_name: str
    solver_version: str

    def sample(self, point: Mapping[str, float], *, run_id: str) -> Mapping[str, float]: ...


def native_sample(
    point: Mapping[str, float],
    outputs: tuple[str, ...],
    *,
    backend: NativeSamplingBackend | None,
    run_id: str,
    sample_id: str,
) -> MapSample:
    """Produce a native-labelled sample, or fail closed with no backend."""

    if backend is None:
        raise CapabilityUnavailable("NATIVE_CAPABILITY_UNAVAILABLE:native-sampling")
    if not run_id.strip():
        raise CapabilityUnavailable("NATIVE_SAMPLE_NEEDS_RUN_ID")
    produced = dict(backend.sample(dict(point), run_id=run_id))
    missing = [name for name in outputs if name not in produced]
    if missing:
        raise CapabilityUnavailable(f"NATIVE_SAMPLE_MISSING_OUTPUT:{missing[0]}")
    from .map import MapSample

    return MapSample(
        sample_id=sample_id,
        inputs=dict(point),
        outputs={name: float(produced[name]) for name in outputs},
        source=MapFidelity.NATIVE,
        kind=SampleKind.SIMULATION,
        solver=(backend.solver_name, backend.solver_version),
        run_id=run_id,
    )
