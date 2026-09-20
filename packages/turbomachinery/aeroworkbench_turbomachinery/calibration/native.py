"""Native calibration capability gating; missing capability fails closed."""

from __future__ import annotations

from dataclasses import dataclass

from ..fidelity.native import (
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
)
from .errors import CalibrationCapabilityUnavailable

NATIVE_CALIBRATION_CAPABILITY = "turbomachinery-calibration-native"


def native_calibration_status(
    gate: NativeCapabilityGate | None = None,
) -> CapabilityStatus:
    if gate is None:
        return CapabilityStatus(
            NATIVE_CALIBRATION_CAPABILITY,
            NativeCapabilityState.UNAVAILABLE,
            None,
            "no capability probe supplied",
        )
    return gate.status(NATIVE_CALIBRATION_CAPABILITY)


@dataclass(frozen=True, slots=True)
class NativeCalibrationRequest:
    dataset_id: str
    dataset_hash: str
    receipt: NativeReceipt | None = None

    def canonical(self) -> dict[str, object]:
        return {
            "datasetId": self.dataset_id,
            "datasetHash": self.dataset_hash,
            "receipt": self.receipt.canonical() if self.receipt is not None else None,
        }


def request_native_calibration(
    request: NativeCalibrationRequest,
    gate: NativeCapabilityGate | None = None,
) -> None:
    status = native_calibration_status(gate)
    if not status.available:
        raise CalibrationCapabilityUnavailable(
            f"CAPABILITY_UNAVAILABLE:{NATIVE_CALIBRATION_CAPABILITY}:{status.detail}"
        )
    if request.receipt is None or (
        gate is not None and not gate.receipt_valid(request.receipt)
    ):
        raise CalibrationCapabilityUnavailable(
            f"NATIVE_RECEIPT_REQUIRED:{NATIVE_CALIBRATION_CAPABILITY}"
        )
    raise CalibrationCapabilityUnavailable(
        f"NATIVE_EXECUTION_NOT_IMPLEMENTED:{NATIVE_CALIBRATION_CAPABILITY}"
    )


__all__ = [
    "NATIVE_CALIBRATION_CAPABILITY",
    "NativeCalibrationRequest",
    "native_calibration_status",
    "request_native_calibration",
]
