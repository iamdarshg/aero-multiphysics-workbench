"""Typed errors for rotating-flow acoustics, instability, and thermoacoustics."""

from __future__ import annotations


class AcousticError(ValueError):
    """Base class for every acoustics-layer failure."""


class AcousticInputError(AcousticError):
    """Raised when a declared acoustic input is not well formed."""


class AcousticValidityError(AcousticError):
    """Raised when an acoustic result fails a physical-validity gate."""


class AcousticCapabilityUnavailable(AcousticError):
    """Raised when a requested native acoustic capability is not available."""

    def __init__(self, capability: str, detail: str) -> None:
        self.capability = capability
        self.detail = detail
        super().__init__(f"{capability}: {detail}")


__all__ = [
    "AcousticCapabilityUnavailable",
    "AcousticError",
    "AcousticInputError",
    "AcousticValidityError",
]
