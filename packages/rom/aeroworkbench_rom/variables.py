"""Declared independent and output variables for a performance map.

Variables are typed physical contracts: a name, a unit, a numeric kind, and
finite declared bounds. They are the single source of truth for sampling plans,
map validity domains, and interpolation dimensionality; no product-specific
assumption is encoded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .errors import MapContractError

__all__ = ["IndependentVariable", "OutputVariable", "VariableKind"]


class VariableKind(StrEnum):
    """Numeric kinds a map can interpolate over."""

    CONTINUOUS = "continuous"
    INTEGER = "integer"
    DISCRETE = "discrete"


@dataclass(frozen=True, slots=True)
class IndependentVariable:
    """One declared independent variable with unit and bounds."""

    name: str
    unit: str
    kind: VariableKind
    lower: float
    upper: float
    values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MapContractError("VARIABLE_NAME_REQUIRED")
        if not self.unit.strip():
            raise MapContractError(f"VARIABLE_UNIT_REQUIRED:{self.name}")
        for label, value in (("lower", self.lower), ("upper", self.upper)):
            if not isfinite(value):
                raise MapContractError(f"NONFINITE_VARIABLE_BOUND:{self.name}:{label}")
        if self.kind is VariableKind.DISCRETE:
            if not self.values:
                raise MapContractError(f"DISCRETE_VARIABLE_NEEDS_VALUES:{self.name}")
            if len(set(self.values)) != len(self.values):
                raise MapContractError(f"DISCRETE_VARIABLE_DUPLICATE_VALUES:{self.name}")
            for value in self.values:
                if not isfinite(value):
                    raise MapContractError(f"NONFINITE_DISCRETE_VALUE:{self.name}")
            return
        if self.lower >= self.upper:
            raise MapContractError(f"INVALID_VARIABLE_BOUNDS:{self.name}")
        if self.kind is VariableKind.INTEGER and (
            not self.lower.is_integer() or not self.upper.is_integer()
        ):
            raise MapContractError(f"INTEGER_VARIABLE_NEEDS_INTEGER_BOUNDS:{self.name}")

    def contains(self, value: float) -> bool:
        if self.kind is VariableKind.DISCRETE:
            return value in self.values
        return self.lower <= value <= self.upper


@dataclass(frozen=True, slots=True)
class OutputVariable:
    """One declared map output with a unit."""

    name: str
    unit: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MapContractError("OUTPUT_NAME_REQUIRED")
        if not self.unit.strip():
            raise MapContractError(f"OUTPUT_UNIT_REQUIRED:{self.name}")
