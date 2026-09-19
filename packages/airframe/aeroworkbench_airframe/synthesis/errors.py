"""Typed failures for the requirements compiler and initial vehicle synthesis.

Every failure is explicit and fail-closed: a requirement that cannot be parsed,
a requirement set that is internally contradictory, or a synthesis chain that
leaves a declared analytical validity envelope never degrades into a fabricated
result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequirementConflict:
    """A pair of requirements whose simultaneous satisfaction is impossible."""

    metric: str
    dimension: str
    lower_si: float | None
    upper_si: float | None
    requirement_ids: tuple[str, ...]
    reason: str

    def canonical(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "dimension": self.dimension,
            "lowerSI": self.lower_si,
            "upperSI": self.upper_si,
            "requirementIds": list(self.requirement_ids),
            "reason": self.reason,
        }


class RequirementError(ValueError):
    """Base class for requirements-compiler failures."""


class RequirementCompileError(RequirementError):
    """Raised when a single requirement is structurally invalid."""


class RequirementConflictError(RequirementError):
    """Raised when a requirement set cannot be satisfied simultaneously."""

    def __init__(self, conflicts: tuple[RequirementConflict, ...]) -> None:
        self.conflicts = conflicts
        details = "; ".join(
            f"{conflict.metric}:{conflict.reason}:" + ",".join(conflict.requirement_ids)
            for conflict in conflicts
        )
        super().__init__(f"REQUIREMENT_CONFLICT:{details}")


class SynthesisError(ValueError):
    """Base class for initial-synthesis failures."""


class SynthesisInfeasibleError(SynthesisError):
    """Raised when requirements cannot be met within declared method validity."""
