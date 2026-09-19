"""Typed failure modes for generic transition/turbulence/wall/roughness management.

Malformed flow states, model declarations, wall-treatment requests, and
roughness specifications raise :class:`TurbulenceValidationError`. A query
outside a declared regime/model/correlation validity range raises
:class:`TurbulenceValidityError`, which is also the escalation signal for a
native solve. A requested native capability that is not wired raises
:class:`TurbulenceCapabilityUnavailableError` and fails closed; a screening
correlation is never relabelled native.
"""

from __future__ import annotations


class TurbulenceError(Exception):
    """Base class for every turbulence-management failure."""


class TurbulenceValidationError(TurbulenceError, ValueError):
    """A flow state, model, wall, or roughness definition is malformed."""


class TurbulenceValidityError(TurbulenceError, ValueError):
    """A query lies outside a declared regime/model/correlation validity range."""


class TurbulenceCapabilityUnavailableError(TurbulenceError, RuntimeError):
    """A requested native capability is absent; the request fails closed."""


__all__ = [
    "TurbulenceCapabilityUnavailableError",
    "TurbulenceError",
    "TurbulenceValidationError",
    "TurbulenceValidityError",
]
