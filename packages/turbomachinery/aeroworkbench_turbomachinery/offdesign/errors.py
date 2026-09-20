"""Typed, fail-closed errors for the multi-point off-design layer."""

from __future__ import annotations


class OffdesignError(ValueError):
    """An off-design contract violation."""

    code = "OFFDESIGN_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class OffdesignInputError(OffdesignError):
    """A malformed or non-physical operating point, schedule, or envelope input."""

    code = "OFFDESIGN_INPUT_INVALID"


class OffdesignCapabilityUnavailable(RuntimeError):
    """A requested native off-design capability is not available."""

    code = "CAPABILITY_UNAVAILABLE"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


__all__ = [
    "OffdesignCapabilityUnavailable",
    "OffdesignError",
    "OffdesignInputError",
]
