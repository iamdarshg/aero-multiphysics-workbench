"""Typed failure modes for the external-aerodynamics fidelity ladder.

Malformed cases, references, polars, or coefficient envelopes raise
:class:`ExternalAeroValidationError`. A query outside a declared
regime/validity range raises :class:`ExternalAeroValidityError`. A requested
native capability (VSPAERO/OpenVSP) that is not present fails closed with
:class:`ExternalAeroCapabilityUnavailableError`; an analytical or VLM result is
never relabelled native.
"""

from __future__ import annotations


class ExternalAeroError(Exception):
    """Base class for every external-aerodynamics failure."""


class ExternalAeroValidationError(ExternalAeroError, ValueError):
    """A case, reference, polar, or coefficient definition is malformed."""


class ExternalAeroValidityError(ExternalAeroError, ValueError):
    """A query lies outside a declared validity/regime range."""


class ExternalAeroCapabilityUnavailableError(ExternalAeroError, RuntimeError):
    """A requested native capability is absent; the request fails closed."""


__all__ = [
    "ExternalAeroCapabilityUnavailableError",
    "ExternalAeroError",
    "ExternalAeroValidationError",
    "ExternalAeroValidityError",
]
