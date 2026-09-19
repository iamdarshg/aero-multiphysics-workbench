"""Higher-fidelity native propulsor seam: reduced wake and CFD.

Promotion beyond the screening solver to a lifting-line/free-wake method, a
steady rotating-frame (MRF) CFD, or a transient sliding/overset/moving-mesh CFD
for rotor-rotor and installed interaction is a capability-gated native seam.
It is available only through a wired backend that supplies real solver
identity; with no backend the seam fails closed and no screening result is ever
relabelled native.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import Provenance

from .aero import Inflow, RotorSpec
from .provenance import native_provenance
from .validity import (
    AeroFidelity,
    CapabilityUnavailable,
    PropulsorError,
    Validity,
    finite,
    nonempty,
)

NATIVE_LEVELS: tuple[AeroFidelity, ...] = (
    AeroFidelity.LIFTING_LINE,
    AeroFidelity.ROTATING_FRAME_CFD,
    AeroFidelity.TRANSIENT_CFD,
)


@dataclass(frozen=True, slots=True)
class NativeRequest:
    """A fully specified native propulsor promotion request."""

    rotor: RotorSpec
    inflow: Inflow
    level: AeroFidelity
    run_id: str
    rear_rotor: RotorSpec | None = None
    axial_spacing_m: float | None = None
    installation_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.level.is_native:
            raise PropulsorError(f"native request needs a native level, got {self.level.value}")
        nonempty(self.run_id, "native_request.run_id")
        if self.axial_spacing_m is not None:
            finite(self.axial_spacing_m, "native_request.axial_spacing_m", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "runId": self.run_id,
            "rotor": self.rotor.canonical_payload(),
            "inflow": self.inflow.canonical_payload(),
            "rearRotor": None if self.rear_rotor is None else self.rear_rotor.canonical_payload(),
            "axialSpacingM": self.axial_spacing_m,
            "installationRef": self.installation_ref,
        }


@runtime_checkable
class WakeBackend(Protocol):
    """A wired native reduced-wake or CFD backend."""

    backend_id: str
    software_version: str

    def solve(self, request: NativeRequest) -> Mapping[str, float]: ...


@dataclass(frozen=True, slots=True)
class NativeAeroResult:
    """Native solver result carrying mandatory solver identity and provenance."""

    rotor_id: str
    level: str
    thrust_n: float
    torque_n_m: float
    power_w: float
    induced_velocity_m_s: float
    solver_name: str
    solver_version: str
    run_id: str
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "thrust_n": "N",
            "torque_n_m": "N*m",
            "power_w": "W",
            "induced_velocity_m_s": "m/s",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "level": self.level,
            "thrustN": self.thrust_n,
            "torqueNM": self.torque_n_m,
            "powerW": self.power_w,
            "inducedVelocityMS": self.induced_velocity_m_s,
            "solverName": self.solver_name,
            "solverVersion": self.solver_version,
            "runId": self.run_id,
        }


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """Capability-gated availability of a native propulsor fidelity level."""

    level: str
    state: str
    detail: str


def native_capability(level: AeroFidelity, *, present: bool = False) -> CapabilityState:
    """Report a native level; an absent backend is explicitly blocked."""

    if not level.is_native:
        raise PropulsorError(f"not a native level:{level.value}")
    if present:
        return CapabilityState(level.value, "engine-present-not-wired", "backend present")
    return CapabilityState(
        level.value,
        "unavailable",
        f"{level.value} requires a wired native backend; the seam fails closed",
    )


def require_native(level: AeroFidelity, *, present: bool = False) -> None:
    """Fail closed unless a wired native backend is declared present."""

    raise CapabilityUnavailable(native_capability(level, present=present).detail)


def promote_to_native(
    rotor: RotorSpec,
    inflow: Inflow,
    *,
    level: AeroFidelity,
    run_id: str,
    backend: WakeBackend | None = None,
    rear_rotor: RotorSpec | None = None,
    axial_spacing_m: float | None = None,
    installation_ref: str | None = None,
) -> NativeAeroResult:
    """Promote to a native level through a wired backend; fail closed if absent."""

    if not level.is_native:
        raise PropulsorError(f"promote_to_native needs a native level, got {level.value}")
    if backend is None:
        raise CapabilityUnavailable(
            f"{level.value} has no wired backend; requested native physics fails closed"
        )
    request = NativeRequest(
        rotor=rotor,
        inflow=inflow,
        level=level,
        run_id=run_id,
        rear_rotor=rear_rotor,
        axial_spacing_m=axial_spacing_m,
        installation_ref=installation_ref,
    )
    outputs = backend.solve(request)
    thrust = finite(outputs.get("thrust_n"), "native.thrust_n")
    torque = finite(outputs.get("torque_n_m"), "native.torque_n_m")
    power = finite(outputs.get("power_w"), "native.power_w")
    induced = finite(outputs.get("induced_velocity_m_s", 0.0), "native.induced_velocity_m_s")
    checks = {
        "thrust_nonnegative": thrust >= 0.0,
        "power_nonnegative": power >= 0.0,
        "finite_outputs": True,
    }
    provenance = native_provenance(
        f"propulsors.native.{level.value}",
        request.canonical_payload(),
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=run_id,
        assumptions=("Native backend supplied measured solver output; not fabricated.",),
    )
    return NativeAeroResult(
        rotor_id=rotor.rotor_id,
        level=level.value,
        thrust_n=thrust,
        torque_n_m=torque,
        power_w=power,
        induced_velocity_m_s=induced,
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=run_id,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"native {level.value} result from {backend.backend_id}",
        ),
        provenance=provenance,
    )


__all__ = [
    "NATIVE_LEVELS",
    "CapabilityState",
    "NativeAeroResult",
    "NativeRequest",
    "WakeBackend",
    "native_capability",
    "promote_to_native",
    "require_native",
]
