"""Typed, fail-closed error contracts for transient system dynamics.

A requested native capability that is absent raises ``CapabilityUnavailable``;
an ill-posed transient scenario raises ``TransientValidationError``; and a
declared protection/actuator/control limit that is violated raises
``LimitExceeded`` or ``ProtectionTrip`` carrying the offending provenance.
"""

from __future__ import annotations

from aeroworkbench_core.types import Provenance


class SystemDynamicsError(ValueError):
    """A typed, fail-closed system-dynamics contract violation."""

    code = "PREPARATION_FAILED"


class TransientValidationError(SystemDynamicsError):
    """A transient scenario or contract is ill-posed and cannot be run."""

    code = "INVALID_TRANSIENT"


class LimitExceeded(SystemDynamicsError):
    """A declared control/actuator limit was violated; carries provenance."""

    code = "LIMIT_EXCEEDED"

    def __init__(
        self, detail: str, *, violations: tuple[str, ...], provenance: Provenance
    ) -> None:
        super().__init__(detail)
        self.violations = violations
        self.provenance = provenance


class ProtectionTrip(SystemDynamicsError):
    """A protection limit tripped and the caller requested a hard stop."""

    code = "PROTECTION_TRIP"

    def __init__(
        self, detail: str, *, trips: tuple[str, ...], provenance: Provenance
    ) -> None:
        super().__init__(detail)
        self.trips = trips
        self.provenance = provenance


class CapabilityUnavailable(RuntimeError):
    """A requested native capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"


__all__ = [
    "CapabilityUnavailable",
    "LimitExceeded",
    "ProtectionTrip",
    "SystemDynamicsError",
    "TransientValidationError",
]
