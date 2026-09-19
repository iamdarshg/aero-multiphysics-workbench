"""Typed fail-closed failure modes for the generic aeroelastic layer.

Malformed definitions raise :class:`AeroelasticError`. A request outside a
declared validity envelope raises :class:`AeroelasticValidityError`; declared
limits raise :class:`AeroelasticLimitExceeded` carrying provenance; and a
request for a native capability that is not wired raises
:class:`AeroelasticCapabilityUnavailable`. No failure path silently substitutes
a screening model for requested native physics.
"""

from __future__ import annotations

from aeroworkbench_core.types import Provenance


class AeroelasticError(ValueError):
    """Base class for every aeroelastic contract violation."""

    code = "PREPARATION_FAILED"


class AeroelasticValidityError(AeroelasticError):
    """A query lies outside the model's declared validity envelope."""

    code = "OUT_OF_VALIDITY"


class AeroelasticLimitExceeded(AeroelasticError):
    """A declared aeroelastic limit was violated; carries provenance."""

    code = "LIMIT_EXCEEDED"

    def __init__(
        self,
        detail: str,
        *,
        violations: tuple[str, ...],
        provenance: Provenance,
    ) -> None:
        super().__init__(detail)
        self.violations = violations
        self.provenance = provenance


class AeroelasticCapabilityUnavailable(RuntimeError):
    """A requested native capability is absent; the call fails closed."""

    code = "CAPABILITY_UNAVAILABLE"

    def __init__(self, capability: str, detail: str) -> None:
        super().__init__(f"{capability}:{detail}")
        self.capability = capability
        self.detail = detail
