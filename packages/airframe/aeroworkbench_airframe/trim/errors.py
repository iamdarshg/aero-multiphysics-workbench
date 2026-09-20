"""Typed failures for the AIRFRAME 05 trim/stability/control subpackage."""

from __future__ import annotations


class TrimError(ValueError):
    """Base class for trim, stability, and control-authority contract violations."""


class AeroCoefficientError(TrimError):
    """Raised when a required coefficient or derivative is unavailable."""


class TrimSolverError(TrimError):
    """Raised when the trim residual system is structurally unsolvable."""


class ControlAuthorityError(TrimError):
    """Raised when a control-authority request is structurally invalid."""


class NativeTrimCapabilityError(TrimError):
    """Raised when a native/nonlinear trim verification capability is requested."""


__all__ = [
    "AeroCoefficientError",
    "ControlAuthorityError",
    "NativeTrimCapabilityError",
    "TrimError",
    "TrimSolverError",
]
