"""Typed failure modes for the fluid property system.

Malformed definitions raise :class:`FluidValidationError`. A request outside a
declared validity range raises :class:`FluidValidityError`; a request for a
capability that is not installed (an external real-gas / equilibrium library or
a transport model) raises :class:`FluidCapabilityUnavailableError`. The latter
two never fall back to a screening substitute.
"""

from __future__ import annotations


class FluidError(Exception):
    """Base class for every fluid property failure."""


class FluidValidationError(FluidError, ValueError):
    """A fluid, composition, species, or query definition is malformed."""


class FluidValidityError(FluidError, ValueError):
    """A query lies outside a declared validity range; no silent extrapolation."""


class FluidCapabilityUnavailableError(FluidError):
    """A requested native capability is not available; the request fails closed."""
