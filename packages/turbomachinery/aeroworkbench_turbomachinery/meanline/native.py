"""Native meanline seam: capability-gated and fail-closed.

The reduced-order row-matching solver is analytical. There is no wired native
three-dimensional throughflow engine in this repository, so a native-fidelity
request is refused rather than answered with an analytical result relabelled as
native.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from .design import StageDesign
from .errors import MeanlineCapabilityUnavailable, MeanlineInputError
from .limits import ScreeningLimits
from .throughflow import ThroughflowResult, solve_throughflow

_NATIVE_MEANLINE_IMPLEMENTATION = "declared-native-throughflow-interface"


@dataclass(frozen=True, slots=True)
class NativeMeanlineStatus:
    """Actual status of the native throughflow seam (never optimistic)."""

    state: str
    executable: str | None
    implementation: str
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "state": self.state,
            "executable": self.executable,
            "implementation": self.implementation,
            "detail": self.detail,
        }


def native_meanline_status(executable: str = "meanline") -> NativeMeanlineStatus:
    """Report whether a real native throughflow engine is present and wired."""

    resolved = shutil.which(executable)
    if resolved is None:
        return NativeMeanlineStatus(
            "unavailable",
            None,
            _NATIVE_MEANLINE_IMPLEMENTATION,
            f"{executable} is not installed; native meanline fidelity fails closed",
        )
    return NativeMeanlineStatus(
        "engine-present-not-wired",
        resolved,
        _NATIVE_MEANLINE_IMPLEMENTATION,
        "engine present but only the interface is declared; no native throughflow case",
    )


def solve_meanline(
    stage: StageDesign,
    *,
    fidelity: str = "analytical",
    limits: ScreeningLimits | None = None,
) -> ThroughflowResult:
    """Dispatch a stage design through the fidelity ladder, failing closed native.

    Only the analytical and reduced-order (still analytical, honestly labelled)
    levels execute. Any other requested fidelity needs a native engine that is
    not wired and raises :class:`MeanlineCapabilityUnavailable`.
    """

    if fidelity == "analytical":
        return solve_throughflow(stage, fidelity="analytical", limits=limits)
    if fidelity == "reduced":
        return solve_throughflow(stage, fidelity="reduced", limits=limits)
    if fidelity == "native":
        raise MeanlineCapabilityUnavailable(native_meanline_status().detail)
    raise MeanlineInputError(f"UNSUPPORTED_MEANLINE_FIDELITY:{fidelity}")


__all__ = ["NativeMeanlineStatus", "native_meanline_status", "solve_meanline"]
