"""Typed, fail-closed errors for the generic meanline/throughflow layer."""

from __future__ import annotations


class MeanlineError(ValueError):
    """A meanline contract violation."""

    code = "MEANLINE_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class MeanlineInputError(MeanlineError):
    """A malformed or non-physical design input."""

    code = "MEANLINE_INPUT_INVALID"


class MeanlineCorrelationError(MeanlineError):
    """A correlation was evaluated outside its declared validity envelope."""

    code = "CORRELATION_OUT_OF_ENVELOPE"


class MeanlineCapabilityUnavailable(RuntimeError):
    """A requested non-analytical/native meanline capability is not available."""

    code = "CAPABILITY_UNAVAILABLE"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


__all__ = [
    "MeanlineError",
    "MeanlineInputError",
    "MeanlineCorrelationError",
    "MeanlineCapabilityUnavailable",
]
