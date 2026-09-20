"""Fail-closed error taxonomy for generative airframe structure and sizing.

Every failure mode is explicit: an invalid member/section/architecture contract,
a layout that cannot be generated from the declared outer geometry, a malformed
load-case source seam, a bounded sizing pass that cannot meet a strength,
buckling, or deflection constraint, and a native structural capability that is
not wired (which fails closed rather than being replaced by a screening model).
"""

from __future__ import annotations

__all__ = [
    "LoadCaseError",
    "SizingError",
    "StructuralConstraintError",
    "StructuralContractError",
    "StructuralLayoutError",
    "StructuresCapabilityUnavailable",
    "StructuresError",
]


class StructuresError(ValueError):
    """Base class for generative airframe structural design failures."""


class StructuralContractError(StructuresError):
    """A structural member, section, material, or result contract is invalid."""


class StructuralLayoutError(StructuralContractError):
    """A structural layout cannot be generated from the supplied outer geometry."""


class LoadCaseError(StructuresError):
    """A structural load case or one of its typed source seams is invalid."""


class SizingError(StructuresError):
    """Automatic sizing failed to find a feasible bounded design."""


class StructuralConstraintError(SizingError):
    """Strength, buckling, or deflection constraints reject a candidate design."""

    def __init__(self, detail: str, *, violations: tuple[str, ...]) -> None:
        self.violations = tuple(violations)
        super().__init__(detail)


class StructuresCapabilityUnavailable(StructuresError):
    """A requested native structural capability is not wired; fail closed."""
