"""Typed failure modes for the generic internal-flow network system.

Malformed network definitions raise :class:`InternalFlowValidationError`. A
query outside a declared correlation validity range raises
:class:`InternalFlowValidityError`, which is also the escalation signal for a
native CFD solve. A requested native capability that is not wired raises
:class:`InternalFlowCapabilityUnavailableError` and fails closed; no screening
correlation is ever relabelled as native.
"""

from __future__ import annotations


class InternalFlowError(Exception):
    """Base class for every internal-flow failure."""


class InternalFlowValidationError(InternalFlowError, ValueError):
    """A node, branch, coefficient, or correlation definition is malformed."""


class InternalFlowValidityError(InternalFlowError, ValueError):
    """A query lies outside a declared validity range; no silent extrapolation."""


class InternalFlowCapabilityUnavailableError(InternalFlowError, RuntimeError):
    """A requested native capability is absent; the request fails closed."""
