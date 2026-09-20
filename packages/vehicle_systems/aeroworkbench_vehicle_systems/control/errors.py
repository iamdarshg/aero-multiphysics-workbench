"""Fail-closed error taxonomy for vehicle-level control allocation and synthesis.

Every failure mode is explicit: an invalid effector/allocation contract, a
moment demand that cannot be met inside position and rate limits, a bounded
synthesis request that cannot meet its gain or authority bounds, a violated
handling-quality constraint, or a native closed-loop capability that is not
actually wired.
"""

from __future__ import annotations

__all__ = [
    "AllocationError",
    "AllocationInfeasible",
    "CapabilityUnavailable",
    "ControlContractError",
    "ControlError",
    "HandlingQualityError",
    "SynthesisError",
]


class ControlError(ValueError):
    """Base class for vehicle-control contract and physics failures."""


class ControlContractError(ControlError):
    """An effector, effectiveness, allocation, or synthesis contract is invalid."""


class AllocationError(ControlError):
    """Control allocation failed to run or failed closed on its inputs."""


class AllocationInfeasible(AllocationError):
    """A moment/force demand cannot be met inside declared limits."""

    def __init__(self, detail: str, *, reasons: tuple[str, ...]) -> None:
        self.reasons = tuple(reasons)
        super().__init__(detail)


class SynthesisError(ControlError):
    """Bounded controller synthesis cannot meet its gain/authority bounds."""


class HandlingQualityError(ControlError):
    """A handling-quality metric or constraint cannot be evaluated or is violated."""


class CapabilityUnavailable(ControlError):
    """A requested native closed-loop capability is not wired; fail closed."""
