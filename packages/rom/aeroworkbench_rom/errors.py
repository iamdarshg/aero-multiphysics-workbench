"""Fail-closed error taxonomy for reduced-order models and performance maps.

Every failure mode is explicit: an invalid contract, a query outside a declared
validity domain, a forbidden silent extrapolation, a missing native/neural
capability, or a surrogate that cannot be trusted because it was never
validated. No error path ever fabricates a value.
"""

from __future__ import annotations

__all__ = [
    "CacheImmutabilityError",
    "CacheIntegrityError",
    "CapabilityUnavailable",
    "ExtrapolationError",
    "MapContractError",
    "RomError",
    "ValidationError",
    "ValidityError",
]


class RomError(ValueError):
    """Base class for reduced-order-model and performance-map failures."""


class MapContractError(RomError):
    """A map, sample, variable, or model contract is structurally invalid."""


class ValidityError(RomError):
    """A query left the declared validity domain or failed a validity check."""


class ExtrapolationError(ValidityError):
    """Extrapolation was requested while the policy forbids silent extrapolation."""


class CapabilityUnavailable(RomError):
    """A requested native or neural capability is not wired; fail closed."""


class ValidationError(RomError):
    """Cross-validation or trust promotion could not be satisfied."""


class CacheIntegrityError(RomError):
    """A content-addressed artifact is missing or failed digest verification."""


class CacheImmutabilityError(RomError):
    """A content-addressed artifact key would be overwritten with different bytes."""
