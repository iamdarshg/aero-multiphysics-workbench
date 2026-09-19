"""Typed failures for the AIRFRAME 03 mass-properties subpackage."""

from __future__ import annotations


class MassError(ValueError):
    """Base class for mass-property contract violations."""


class MassClosureError(MassError):
    """Raised when aggregate closure (mass sum / inertia) fails closed."""


class PackagingError(MassError):
    """Raised when a packaging layout document is structurally invalid."""


class MassParticipantError(MassError):
    """Raised when a structural mass update cannot be applied safely."""


__all__ = [
    "MassClosureError",
    "MassError",
    "MassParticipantError",
    "PackagingError",
]
