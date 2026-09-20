"""Native aeroacoustic capability probes, capability-gated and fail closed.

Higher-fidelity acoustics is optional. Transient surface-pressure extraction,
FW-H (or equivalent) propagation, observer SPL synthesis, and unsteady reacting
analysis are only trusted when the backing capability is present and the caller
supplies a trusted native receipt. A missing capability resolves to
``unavailable`` and every request that needs it fails closed; a screening result
is never relabelled as native.
"""

from __future__ import annotations

from enum import StrEnum
from importlib import metadata
from shutil import which
from typing import NoReturn

from ..fidelity.native import (
    CapabilityProbe,
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
)
from .errors import AcousticCapabilityUnavailable

__all__ = [
    "ACOUSTIC_CAPABILITY_GATE",
    "NativeAcousticRequirement",
    "acoustic_capability_gate",
    "native_acoustic_capability",
    "require_native_acoustic",
    "trusted_acoustic_receipt",
]


class NativeAcousticRequirement(StrEnum):
    """Declared optional native aeroacoustic capabilities."""

    TRANSIENT_CFD_SPECTRA = "transient-cfd-spectra"
    FW_H_PROPAGATION = "fw-h-propagation"
    OBSERVER_SPL = "observer-spl"
    REACTING_UNSTEADY_CFD = "reacting-unsteady-cfd"


_DISTRIBUTIONS: dict[NativeAcousticRequirement, tuple[str, ...]] = {
    NativeAcousticRequirement.TRANSIENT_CFD_SPECTRA: ("pyprecice", "precice"),
    NativeAcousticRequirement.FW_H_PROPAGATION: ("pyacoustics", "acoustics", "libAcoustics"),
    NativeAcousticRequirement.OBSERVER_SPL: (),
    NativeAcousticRequirement.REACTING_UNSTEADY_CFD: ("pyprecice", "precice"),
}

_EXECUTABLES: dict[NativeAcousticRequirement, tuple[str, ...]] = {
    NativeAcousticRequirement.FW_H_PROPAGATION: ("acoustics",),
    NativeAcousticRequirement.TRANSIENT_CFD_SPECTRA: (),
    NativeAcousticRequirement.OBSERVER_SPL: (),
    NativeAcousticRequirement.REACTING_UNSTEADY_CFD: (),
}


def _probe_distribution(distribution: str) -> CapabilityStatus | None:
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None
    except Exception:  # noqa: BLE001 - metadata failures must never crash a probe
        return None
    return CapabilityStatus(
        distribution,
        NativeCapabilityState.READY,
        version,
        f"{distribution} {version} installed",
    )


def native_acoustic_capability(
    requirement: NativeAcousticRequirement,
    *,
    probe: CapabilityProbe | None = None,
) -> CapabilityStatus:
    """Probe one native aeroacoustic requirement without importing the engine."""

    if probe is not None:
        return probe(requirement.value)
    for distribution in _DISTRIBUTIONS[requirement]:
        status = _probe_distribution(distribution)
        if status is not None:
            return CapabilityStatus(
                requirement.value,
                NativeCapabilityState.READY,
                status.version,
                status.detail,
            )
    for executable in _EXECUTABLES[requirement]:
        resolved = which(executable)
        if resolved is not None:
            return CapabilityStatus(
                requirement.value,
                NativeCapabilityState.READY,
                None,
                f"{executable} present at {resolved}; engine-present-not-wired",
            )
    return CapabilityStatus(
        requirement.value,
        NativeCapabilityState.UNAVAILABLE,
        None,
        f"{requirement.value} is not wired; the native level fails closed",
    )


def acoustic_capability_gate() -> NativeCapabilityGate:
    """Build the capability gate for the declared native aeroacoustic options."""

    return NativeCapabilityGate(
        {item.value: native_acoustic_capability(item) for item in NativeAcousticRequirement}
    )


ACOUSTIC_CAPABILITY_GATE = acoustic_capability_gate()


def trusted_acoustic_receipt(receipt: NativeReceipt | None) -> NativeReceipt:
    """Fail closed unless a complete, trusted native receipt is supplied."""

    if receipt is None:
        raise AcousticCapabilityUnavailable(
            "native-receipt", "a trusted native receipt is required for a native result"
        )
    if not receipt.valid:
        raise AcousticCapabilityUnavailable(
            receipt.capability, "native receipt is untrusted or incomplete"
        )
    return receipt


def require_native_acoustic(requirement: NativeAcousticRequirement) -> NoReturn:
    """Fail closed: this repository has no wired native aeroacoustic engine."""

    status = native_acoustic_capability(requirement)
    raise AcousticCapabilityUnavailable(requirement.value, status.detail)
