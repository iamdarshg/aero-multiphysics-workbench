"""Capability probes for optional native property backends.

Probes use package metadata only and never import the heavy module, matching the
platform's native-solver capability policy. A missing backend is ``unavailable``
and any request that needs it fails closed; a screening model is never
substituted and relabelled as native.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata

from .errors import FluidCapabilityUnavailableError


class PropertyBackend(StrEnum):
    """External libraries that can supply native property data."""

    CANTERA = "cantera"
    COOLPROP = "coolprop"
    REFPROP = "refprop"


_BACKEND_DISTRIBUTIONS: dict[PropertyBackend, tuple[str, ...]] = {
    PropertyBackend.CANTERA: ("cantera",),
    PropertyBackend.COOLPROP: ("CoolProp",),
    PropertyBackend.REFPROP: ("ctREFPROP", "refprop"),
}


@dataclass(frozen=True, slots=True)
class BackendCapability:
    """The observed availability of one external property backend."""

    backend: PropertyBackend
    distribution: str | None
    state: str
    version: str | None
    detail: str

    @property
    def available(self) -> bool:
        return self.state == "ready"

    def canonical(self) -> dict[str, object]:
        return {
            "backend": self.backend.value,
            "distribution": self.distribution,
            "state": self.state,
            "version": self.version,
            "detail": self.detail,
        }


def _probe_distribution(distribution: str) -> tuple[str, str | None, str]:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ("unavailable", None, f"{distribution} is not installed")
    except Exception as exc:  # noqa: BLE001 - metadata failures must never crash a probe
        return ("unavailable", None, f"{distribution} metadata unreadable:{exc}")
    return ("ready", version, f"{distribution} {version} installed")


def probe_backend(backend: PropertyBackend) -> BackendCapability:
    """Probe one backend without importing it."""
    for distribution in _BACKEND_DISTRIBUTIONS[backend]:
        state, version, detail = _probe_distribution(distribution)
        if state == "ready":
            return BackendCapability(backend, distribution, state, version, detail)
    first = _BACKEND_DISTRIBUTIONS[backend][0]
    return BackendCapability(
        backend,
        None,
        "unavailable",
        None,
        f"no distribution for {backend.value} is installed (tried {first})",
    )


def require_backend(backend: PropertyBackend) -> BackendCapability:
    """Return the capability or fail closed with a typed error."""
    capability = probe_backend(backend)
    if not capability.available:
        raise FluidCapabilityUnavailableError(
            f"PROPERTY_BACKEND_UNAVAILABLE:{backend.value}:{capability.detail}"
        )
    return capability
