"""Fidelity, extrapolation policy, and validity contracts for electrical models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FidelityLevel(StrEnum):
    """The explicit generic fidelity ladder for electrical participants."""

    ANALYTICAL = "analytical"
    REDUCED = "reduced"
    NATIVE = "native"


class OutOfEnvelopePolicy(StrEnum):
    """How a map-backed (reduced) level treats an out-of-envelope request."""

    FAIL = "fail"
    CLAMP = "clamp"


@dataclass(frozen=True, slots=True)
class Validity:
    """Participant validity outcome carried on every fidelity level."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))


__all__ = ["FidelityLevel", "OutOfEnvelopePolicy", "Validity"]
