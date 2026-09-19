"""Capability probes for optional native aeroelastic backends.

Native coupled-field aeroelasticity (p-k flutter solvers, transient CFD/FSI via
preCICE, contact/rub FEA) is capability-gated. Probes use package metadata only
and never import the heavy engine. A missing backend is ``unavailable`` and any
request that needs it fails closed; a screening model is never substituted and
relabelled native.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata
from typing import NoReturn

from .errors import AeroelasticCapabilityUnavailable


class NativeRequirement(StrEnum):
    """Declared native aeroelastic capabilities."""

    PRECICE_FSI = "precice-fsi"
    TRANSIENT_CFD = "transient-cfd"
    PK_FLUTTER = "pk-flutter"
    CONTACT_FEA = "contact-fea"


_DISTRIBUTIONS: dict[NativeRequirement, tuple[str, ...]] = {
    NativeRequirement.PRECICE_FSI: ("pyprecice", "precice"),
    NativeRequirement.TRANSIENT_CFD: ("precice",),
    NativeRequirement.PK_FLUTTER: (),
    NativeRequirement.CONTACT_FEA: (),
}


@dataclass(frozen=True, slots=True)
class CapabilityState:
    """The observed availability of one native requirement."""

    requirement: NativeRequirement
    state: str
    distribution: str | None
    version: str | None
    detail: str

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def canonical(self) -> dict[str, object]:
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


def native_capability(requirement: NativeRequirement) -> CapabilityState:
    """Probe one native requirement without importing the engine."""

    for distribution in _DISTRIBUTIONS[requirement]:
        state, version, detail = _probe(distribution)
        if state != "unavailable":
            return CapabilityState(requirement, state, distribution, version, detail)
    return CapabilityState(
        requirement,
        "unavailable",
        None,
        None,
        f"{requirement.value} is not wired; the native level fails closed",
    )


def require_native(requirement: NativeRequirement) -> NoReturn:
    """Fail closed unless a wired native capability is declared present."""

    capability = native_capability(requirement)
    raise AeroelasticCapabilityUnavailable(requirement.value, capability.detail)


__all__ = [
    "CapabilityState",
    "NativeRequirement",
    "native_capability",
    "require_native",
]
