"""Fail-closed error taxonomy for vehicle aeroacoustics and community noise."""

from __future__ import annotations

__all__ = [
    "AeroacousticError",
    "CapabilityUnavailable",
    "ContractError",
    "ValidityError",
]


class AeroacousticError(ValueError):
    """Base class for every vehicle-aeroacoustics failure."""


class ContractError(AeroacousticError):
    """A rotor/observer/environment/trajectory contract is structurally invalid."""


class ValidityError(AeroacousticError):
    """A physics-validity gate failed closed (no level is invented instead)."""


class CapabilityUnavailable(AeroacousticError):
    """A requested native CAA capability is not wired; fail closed."""

    def __init__(self, capability: str, detail: str) -> None:
        self.capability = capability
        self.detail = detail
        super().__init__(f"{capability}: {detail}")
