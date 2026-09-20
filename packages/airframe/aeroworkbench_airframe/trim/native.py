"""Capability-gated native/nonlinear trim verification seam (governed JSBSim).

Screening trim is an analytical equilibrium solution. Nonlinear 6-DoF
verification of a trim point is a different fidelity and is capability-gated:
this module probes for a wired JSBSim distribution using package metadata only
and fails closed when it is absent. A screening trim is never relabelled as
native verification, and missing aerodynamic data is never replaced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata
from typing import NoReturn

from .contract import TrimFidelity
from .errors import NativeTrimCapabilityError


class NativeTrimRequirement(StrEnum):
    """Declared native trim-verification capabilities."""

    JSBSIM_6DOF = "jsbsim-6dof"


_DISTRIBUTIONS: dict[NativeTrimRequirement, tuple[str, ...]] = {
    NativeTrimRequirement.JSBSIM_6DOF: ("jsbsim",),
}


@dataclass(frozen=True, slots=True)
class NativeTrimCapability:
    requirement: NativeTrimRequirement
    state: str
    distribution: str | None
    version: str | None
    detail: str

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def as_dict(self) -> dict[str, object]:
        return {
            "requirement": self.requirement.value,
            "state": self.state,
            "distribution": self.distribution,
            "version": self.version,
            "detail": self.detail,
        }


def _probe(distribution: str) -> tuple[str, str | None, str]:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ("unavailable", None, f"{distribution} is not installed")
    except Exception as exc:  # noqa: BLE001 - metadata failures must never crash a probe
        return ("unavailable", None, f"{distribution} metadata unreadable:{exc}")
    return ("engine-present-not-wired", version, f"{distribution} {version} installed")


def native_trim_capability(
    requirement: NativeTrimRequirement = NativeTrimRequirement.JSBSIM_6DOF,
) -> NativeTrimCapability:
    """Probe a native trim-verification requirement without importing the engine."""

    for distribution in _DISTRIBUTIONS[requirement]:
        state, version, detail = _probe(distribution)
        if state != "unavailable":
            return NativeTrimCapability(requirement, state, distribution, version, detail)
    return NativeTrimCapability(
        requirement,
        "unavailable",
        None,
        None,
        f"{requirement.value} is not wired; native nonlinear verification fails closed",
    )


def verification_fidelity(
    requirement: NativeTrimRequirement = NativeTrimRequirement.JSBSIM_6DOF,
) -> TrimFidelity:
    capability = native_trim_capability(requirement)
    return TrimFidelity.NATIVE_NONLINEAR if capability.available else TrimFidelity.SCREENING


def require_native_trim(
    requirement: NativeTrimRequirement = NativeTrimRequirement.JSBSIM_6DOF,
) -> NoReturn:
    """Fail closed: no native nonlinear trim verifier is wired in this build."""

    capability = native_trim_capability(requirement)
    raise NativeTrimCapabilityError(
        f"{requirement.value} unavailable: {capability.detail}"
    )


def verify_trim_nonlinear(
    *,
    requirement: NativeTrimRequirement = NativeTrimRequirement.JSBSIM_6DOF,
) -> NoReturn:
    """Request nonlinear 6-DoF verification of a screening trim point."""

    require_native_trim(requirement)


__all__ = [
    "NativeTrimCapability",
    "NativeTrimRequirement",
    "native_trim_capability",
    "require_native_trim",
    "verification_fidelity",
    "verify_trim_nonlinear",
]
