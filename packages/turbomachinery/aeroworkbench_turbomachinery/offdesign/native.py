"""Native off-design capability gating; missing capability fails closed."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..fidelity.native import (
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
)
from .errors import OffdesignCapabilityUnavailable
from .operating_point import OperatingPoint
from .results import OffdesignFidelity

NATIVE_OFFDESIGN_CAPABILITY = "turbomachinery-offdesign-native"


def native_offdesign_status(
    gate: NativeCapabilityGate | None = None,
) -> CapabilityStatus:
    if gate is None:
        return CapabilityStatus(
            NATIVE_OFFDESIGN_CAPABILITY,
            NativeCapabilityState.UNAVAILABLE,
            None,
            "no capability probe supplied",
        )
    return gate.status(NATIVE_OFFDESIGN_CAPABILITY)


@dataclass(frozen=True, slots=True)
class NativeOffdesignRequest:
    points: tuple[OperatingPoint, ...]
    fidelity: OffdesignFidelity = OffdesignFidelity.NATIVE_OFFDESIGN
    receipt: NativeReceipt | None = None

    def canonical(self) -> dict[str, object]:
        return {
            "points": [point.canonical() for point in self.points],
            "fidelity": self.fidelity.value,
            "receipt": self.receipt.canonical() if self.receipt is not None else None,
        }


def request_native_offdesign(
    request: NativeOffdesignRequest,
    gate: NativeCapabilityGate | None = None,
    parameters: Mapping[str, float] | None = None,
) -> None:
    del parameters
    status = native_offdesign_status(gate)
    if not status.available:
        raise OffdesignCapabilityUnavailable(
            f"CAPABILITY_UNAVAILABLE:{NATIVE_OFFDESIGN_CAPABILITY}:{status.detail}"
        )
    if request.receipt is None or (
        gate is not None and not gate.receipt_valid(request.receipt)
    ):
        raise OffdesignCapabilityUnavailable(
            f"NATIVE_RECEIPT_REQUIRED:{NATIVE_OFFDESIGN_CAPABILITY}"
        )
    raise OffdesignCapabilityUnavailable(
        f"NATIVE_EXECUTION_NOT_IMPLEMENTED:{NATIVE_OFFDESIGN_CAPABILITY}"
    )


__all__ = [
    "NATIVE_OFFDESIGN_CAPABILITY",
    "NativeOffdesignRequest",
    "native_offdesign_status",
    "request_native_offdesign",
]
