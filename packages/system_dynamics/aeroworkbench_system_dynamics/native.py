"""Capability-gated native transient coordinator seam, failing closed.

A native implicit/DAE transient coordinator (for example an OpenMDAO-declared
transient driver, SUNDIALS/IDA, or an external co-simulation bus) is a declared
capability. When it is absent the native path raises ``CapabilityUnavailable``
instead of substituting a screening fixed-step model. When a backend is
supplied it must itself carry native solver identity, so a native result can
never be silently relabelled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aeroworkbench_core.types import ResultSource

from .errors import CapabilityUnavailable, TransientValidationError
from .results import TransientResult
from .transient import TransientScenario

DEFAULT_NATIVE_REQUIREMENT = "implicit-dae-transient-coordinator"


@dataclass(frozen=True, slots=True)
class NativeTransientStatus:
    """Capability-gated availability of a declared native coordinator."""

    requirement: str
    state: str
    detail: str

    def canonical(self) -> dict[str, str]:
        return {
            "requirement": self.requirement,
            "state": self.state,
            "detail": self.detail,
        }


class NativeTransientBackend(Protocol):
    """A native transient coordinator with mandatory solver identity."""

    backend_id: str
    software_version: str

    def integrate(self, scenario: TransientScenario) -> TransientResult: ...


def native_transient_status(
    requirement: str = DEFAULT_NATIVE_REQUIREMENT, *, present: bool = False
) -> NativeTransientStatus:
    """Report a native requirement; absent capability is explicitly blocked."""

    if not requirement.strip():
        raise TransientValidationError("capability.requirement is required")
    if present:
        return NativeTransientStatus(
            requirement, "engine-present-not-wired", "engine present"
        )
    return NativeTransientStatus(
        requirement,
        "unavailable",
        f"{requirement} is not available; the native level fails closed",
    )


def require_native_transient(
    requirement: str = DEFAULT_NATIVE_REQUIREMENT, *, present: bool = False
) -> None:
    """Fail closed unless a wired native capability is declared present."""

    if not present:
        raise CapabilityUnavailable(native_transient_status(requirement).detail)


def solve_native_transient(
    scenario: TransientScenario,
    *,
    backend: NativeTransientBackend | None = None,
    requirement: str = DEFAULT_NATIVE_REQUIREMENT,
) -> TransientResult:
    """Run a native transient when present; otherwise fail closed."""

    if backend is None:
        require_native_transient(requirement)
    assert backend is not None
    result = backend.integrate(scenario)
    if result.provenance.source is not ResultSource.NATIVE_SOLVER:
        raise TransientValidationError(
            "native transient backend returned non-native provenance"
        )
    if not (result.provenance.solver_name and result.provenance.solver_version):
        raise TransientValidationError(
            "native transient backend missing solver identity"
        )
    return result


__all__ = [
    "DEFAULT_NATIVE_REQUIREMENT",
    "NativeTransientBackend",
    "NativeTransientStatus",
    "native_transient_status",
    "require_native_transient",
    "solve_native_transient",
]
