"""Unit-bearing station quantities for the rotating gas-path contract.

The vocabulary is deliberately generic (pressure, temperature, mass flow, ...)
and shares definitions with the TypeScript mirror in
``packages/schema/src/rotating_gas.ts``. Canonical serialization normalizes every
value to SI so a hash is unit-invariant across the two languages.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

from .canonical import canonical_number

# unit label -> (dimension, scale to SI, offset to SI): si = value * scale + offset
_UNIT_TABLE: dict[str, tuple[str, float, float]] = {
    "dimensionless": ("dimensionless", 1.0, 0.0),
    "kg/s": ("mass_flow", 1.0, 0.0),
    "kg/h": ("mass_flow", 1.0 / 3600.0, 0.0),
    "Pa": ("pressure", 1.0, 0.0),
    "kPa": ("pressure", 1e3, 0.0),
    "MPa": ("pressure", 1e6, 0.0),
    "bar": ("pressure", 1e5, 0.0),
    "K": ("temperature", 1.0, 0.0),
    "degC": ("temperature", 1.0, 273.15),
    "kg/m3": ("density", 1.0, 0.0),
    "m/s": ("velocity", 1.0, 0.0),
    "m": ("length", 1.0, 0.0),
    "mm": ("length", 1e-3, 0.0),
    "m2": ("area", 1.0, 0.0),
    "cm2": ("area", 1e-4, 0.0),
    "W": ("power", 1.0, 0.0),
    "kW": ("power", 1e3, 0.0),
    "MW": ("power", 1e6, 0.0),
    "N.m": ("torque", 1.0, 0.0),
    "rpm": ("rotational_speed", 1.0 / 60.0, 0.0),
    "rev/s": ("rotational_speed", 1.0, 0.0),
    "rad/s": ("rotational_speed", 1.0 / (2.0 * pi), 0.0),
    "deg": ("angle", pi / 180.0, 0.0),
    "rad": ("angle", 1.0, 0.0),
    "s": ("time", 1.0, 0.0),
}


def dimension_of(unit: str) -> str:
    """Return the physical dimension of a unit label, failing closed if unknown."""
    try:
        return _UNIT_TABLE[unit][0]
    except KeyError:
        raise ValueError(f"UNKNOWN_UNIT:{unit}") from None


# dimension -> canonical SI unit label (all have scale 1 and offset 0)
_SI_UNIT_LABELS: dict[str, str] = {
    "dimensionless": "dimensionless",
    "mass_flow": "kg/s",
    "pressure": "Pa",
    "temperature": "K",
    "density": "kg/m3",
    "velocity": "m/s",
    "length": "m",
    "area": "m2",
    "power": "W",
    "torque": "N.m",
    "rotational_speed": "rev/s",
    "angle": "rad",
    "time": "s",
}


def si_unit_for_dimension(dimension: str) -> str:
    """Return the canonical SI unit label for a physical dimension."""
    try:
        return _SI_UNIT_LABELS[dimension]
    except KeyError:
        raise ValueError(f"UNKNOWN_DIMENSION:{dimension}") from None



def to_si(value: float, unit: str) -> float:
    """Normalize a finite value to SI, rejecting unknown units."""
    if unit not in _UNIT_TABLE:
        raise ValueError(f"UNKNOWN_UNIT:{unit}")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("NONFINITE_QUANTITY_VALUE")
    _, scale, offset = _UNIT_TABLE[unit]
    return value * scale + offset


@dataclass(frozen=True, slots=True)
class Quantity:
    """A finite scalar carrying its unit; canonicalized to SI on serialization."""

    value: float
    unit: str

    def __post_init__(self) -> None:
        if self.unit not in _UNIT_TABLE:
            raise ValueError(f"UNKNOWN_UNIT:{self.unit}")
        if self.value != self.value or self.value in (float("inf"), float("-inf")):
            raise ValueError("NONFINITE_QUANTITY_VALUE")

    @property
    def dimension(self) -> str:
        return dimension_of(self.unit)

    @property
    def value_si(self) -> float:
        return to_si(self.value, self.unit)

    def canonical(self) -> dict[str, object]:
        return {"valueSI": canonical_number(self.value_si), "dimension": self.dimension}


def require_dimension(quantity: Quantity, dimension: str, label: str) -> None:
    """Fail closed when a quantity does not carry the expected physical dimension."""
    if quantity.dimension != dimension:
        raise ValueError(f"QUANTITY_DIMENSION_MISMATCH:{label}:{quantity.dimension}:{dimension}")
