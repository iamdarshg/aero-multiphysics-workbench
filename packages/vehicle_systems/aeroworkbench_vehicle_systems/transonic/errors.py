"""Fail-closed error taxonomy for transonic/supersonic external-aero design."""

from __future__ import annotations

__all__ = [
    "TransonicCapabilityUnavailable",
    "TransonicContractError",
    "TransonicError",
    "TransonicOutOfScope",
    "TransonicValidityError",
]


class TransonicError(ValueError):
    """Base class for transonic/supersonic screening failures."""


class TransonicContractError(TransonicError):
    """A transonic input, station set, or case contract is malformed."""


class TransonicValidityError(TransonicError):
    """A query lies outside a declared compressibility/validity range."""


class TransonicOutOfScope(TransonicError):
    """Hypersonic/high-enthalpy flow is explicitly out of scope."""


class TransonicCapabilityUnavailable(TransonicError, RuntimeError):
    """A requested native compressible-CFD capability is not wired."""
