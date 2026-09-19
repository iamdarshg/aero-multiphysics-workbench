"""Native capability gating and trusted native receipts.

A native rung may only be promoted when the capability that backs it is
probed ready, and a native result may only be trusted when it carries a
complete, trusted receipt (solver name, version, run id, inputs hash). Any
missing probe resolves to ``unavailable`` so callers fail closed rather than
substituting an analytical answer for a native one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..canonical import content_digest

__all__ = [
    "CapabilityProbe",
    "CapabilityStatus",
    "NativeCapabilityGate",
    "NativeCapabilityState",
    "NativeReceipt",
]


class NativeCapabilityState(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class CapabilityStatus:
    capability: str
    state: NativeCapabilityState
    version: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise ValueError("CAPABILITY_ID_REQUIRED")

    @property
    def available(self) -> bool:
        return self.state is NativeCapabilityState.READY

    def canonical(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "state": self.state.value,
            "version": self.version,
            "detail": self.detail,
        }


CapabilityProbe = Callable[[str], CapabilityStatus]


@dataclass(frozen=True, slots=True)
class NativeReceipt:
    """Trusted observation that a native solver actually produced a result."""

    capability: str
    solver_name: str
    solver_version: str
    run_id: str
    inputs_hash: str
    trusted: bool = True

    def __post_init__(self) -> None:
        for label, value in (
            ("capability", self.capability),
            ("solver_name", self.solver_name),
            ("solver_version", self.solver_version),
            ("run_id", self.run_id),
            ("inputs_hash", self.inputs_hash),
        ):
            if not value.strip():
                raise ValueError(f"NATIVE_RECEIPT_{label.upper()}_REQUIRED")

    @property
    def valid(self) -> bool:
        return bool(self.trusted and self.inputs_hash.strip())

    def canonical(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "solverName": self.solver_name,
            "solverVersion": self.solver_version,
            "runId": self.run_id,
            "inputsHash": self.inputs_hash,
            "trusted": self.trusted,
        }


@dataclass(frozen=True, slots=True)
class NativeCapabilityGate:
    """Resolves capability availability; unknown capabilities are unavailable."""

    statuses: Mapping[str, CapabilityStatus] = field(default_factory=dict)

    def status(self, capability: str) -> CapabilityStatus:
        found = self.statuses.get(capability)
        if found is not None:
            return found
        return CapabilityStatus(
            capability,
            NativeCapabilityState.UNAVAILABLE,
            None,
            "no capability probe registered",
        )

    def permits(self, capability: str) -> bool:
        return self.status(capability).available

    def permits_all(self, capabilities: Sequence[str]) -> bool:
        return bool(capabilities) and all(self.permits(item) for item in capabilities)

    def receipt_valid(self, receipt: NativeReceipt) -> bool:
        return self.permits(receipt.capability) and receipt.valid

    def canonical(self) -> dict[str, Any]:
        return {
            "statuses": [
                self.statuses[key].canonical() for key in sorted(self.statuses)
            ]
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def capability_status(
    capability: str,
    *,
    probe: CapabilityProbe | None = None,
) -> CapabilityStatus:
    """Fail closed: a missing probe is ``unavailable``, never ready."""
    if probe is None:
        return CapabilityStatus(
            capability,
            NativeCapabilityState.UNAVAILABLE,
            None,
            "no capability probe supplied",
        )
    return probe(capability)
