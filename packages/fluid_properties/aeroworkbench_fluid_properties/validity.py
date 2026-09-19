"""Declared validity ranges with fail-closed evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .errors import FluidValidationError, FluidValidityError


@dataclass(frozen=True, slots=True)
class ValidityRange:
    """A closed interval over which a model may be evaluated.

    Any query outside ``[minimum, maximum]`` raises :class:`FluidValidityError`
    instead of silently extrapolating.
    """

    quantity: str
    unit: str
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not self.quantity.strip():
            raise FluidValidationError("VALIDITY_QUANTITY_REQUIRED")
        if not self.unit.strip():
            raise FluidValidationError("VALIDITY_UNIT_REQUIRED")
        if not (isfinite(self.minimum) and isfinite(self.maximum)):
            raise FluidValidationError("NONFINITE_VALIDITY_BOUND")
        if self.minimum > self.maximum:
            raise FluidValidationError("VALIDITY_BOUNDS_INVERTED")

    def contains(self, value: float) -> bool:
        return isfinite(value) and self.minimum <= value <= self.maximum

    def require(self, value: float, *, label: str | None = None) -> float:
        """Return ``value`` or fail closed with a typed message."""
        name = label or self.quantity
        if not isfinite(value):
            raise FluidValidityError(f"NONFINITE_{name.upper()}")
        if not self.minimum <= value <= self.maximum:
            raise FluidValidityError(
                f"{name.upper()}_OUT_OF_VALIDITY_RANGE:"
                f"{value}:{self.minimum}:{self.maximum}:{self.unit}"
            )
        return value

    def intersection(self, other: ValidityRange) -> ValidityRange:
        """Intersect two ranges over the same quantity; fail if disjoint."""
        if self.quantity != other.quantity or self.unit != other.unit:
            raise FluidValidationError("VALIDITY_QUANTITY_MISMATCH")
        minimum = max(self.minimum, other.minimum)
        maximum = min(self.maximum, other.maximum)
        if minimum > maximum:
            raise FluidValidationError("VALIDITY_RANGES_DISJOINT")
        return ValidityRange(self.quantity, self.unit, minimum, maximum)

    def canonical(self) -> dict[str, object]:
        return {
            "quantity": self.quantity,
            "unit": self.unit,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }
