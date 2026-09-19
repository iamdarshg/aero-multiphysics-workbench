"""Unit-safe physical quantities for the generic environmental contracts.

The vocabulary spans the dimensions an exposure/degradation state needs
(concentrations, areal mass, areal mass rate, dose, length, time, temperature,
velocity, energy, pressure, ...). Every value normalizes to SI and a quantity
can never change dimension silently. Unknown units fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

from .errors import UnitError, finite

# unit label -> (dimension, scale to SI, offset to SI): si = value * scale + offset
_UNITS: dict[str, tuple[str, float, float]] = {
    "dimensionless": ("dimensionless", 1.0, 0.0),
    "m": ("length", 1.0, 0.0),
    "cm": ("length", 1e-2, 0.0),
    "mm": ("length", 1e-3, 0.0),
    "um": ("length", 1e-6, 0.0),
    "in": ("length", 0.0254, 0.0),
    "ft": ("length", 0.3048, 0.0),
    "m2": ("area", 1.0, 0.0),
    "cm2": ("area", 1e-4, 0.0),
    "mm2": ("area", 1e-6, 0.0),
    "m3": ("volume", 1.0, 0.0),
    "cm3": ("volume", 1e-6, 0.0),
    "l": ("volume", 1e-3, 0.0),
    "kg": ("mass", 1.0, 0.0),
    "g": ("mass", 1e-3, 0.0),
    "mg": ("mass", 1e-6, 0.0),
    "s": ("time", 1.0, 0.0),
    "min": ("time", 60.0, 0.0),
    "h": ("time", 3600.0, 0.0),
    "m/s": ("velocity", 1.0, 0.0),
    "mm/s": ("velocity", 1e-3, 0.0),
    "km/h": ("velocity", 1000.0 / 3600.0, 0.0),
    "kt": ("velocity", 1852.0 / 3600.0, 0.0),
    "ft/s": ("velocity", 0.3048, 0.0),
    "m/s2": ("acceleration", 1.0, 0.0),
    "g0": ("acceleration", 9.80665, 0.0),
    "K": ("temperature", 1.0, 0.0),
    "degC": ("temperature", 1.0, 273.15),
    "kg/m3": ("density", 1.0, 0.0),
    "g/m3": ("density", 1e-3, 0.0),
    "mg/m3": ("density", 1e-6, 0.0),
    "g/cm3": ("density", 1e3, 0.0),
    "kg/m2": ("mass_per_area", 1.0, 0.0),
    "g/m2": ("mass_per_area", 1e-3, 0.0),
    "kg/(m2*s)": ("mass_per_area_time", 1.0, 0.0),
    "g/(m2*h)": ("mass_per_area_time", 1e-3 / 3600.0, 0.0),
    "Pa": ("pressure", 1.0, 0.0),
    "kPa": ("pressure", 1e3, 0.0),
    "MPa": ("pressure", 1e6, 0.0),
    "N": ("force", 1.0, 0.0),
    "kN": ("force", 1e3, 0.0),
    "J": ("energy", 1.0, 0.0),
    "kJ": ("energy", 1e3, 0.0),
    "kg*m/s": ("momentum", 1.0, 0.0),
    "N*s": ("momentum", 1.0, 0.0),
    "W": ("power", 1.0, 0.0),
    "kW": ("power", 1e3, 0.0),
    "Hz": ("frequency", 1.0, 0.0),
    "kg/s": ("mass_flow", 1.0, 0.0),
}

_SI_UNITS: dict[str, str] = {
    "dimensionless": "dimensionless",
    "length": "m",
    "area": "m2",
    "volume": "m3",
    "mass": "kg",
    "time": "s",
    "velocity": "m/s",
    "acceleration": "m/s2",
    "temperature": "K",
    "density": "kg/m3",
    "mass_per_area": "kg/m2",
    "mass_per_area_time": "kg/(m2*s)",
    "pressure": "Pa",
    "force": "N",
    "energy": "J",
    "momentum": "kg*m/s",
    "power": "W",    "frequency": "Hz",
    "mass_flow": "kg/s",
}

SI_UNITS = frozenset(_UNITS)


def require_unit(unit: str) -> str:
    """Return a known unit label, failing closed otherwise."""

    if unit not in _UNITS:
        raise UnitError(f"UNKNOWN_UNIT:{unit}")
    return unit


def dimension_of(unit: str) -> str:
    try:
        return _UNITS[unit][0]
    except KeyError:
        raise UnitError(f"UNKNOWN_UNIT:{unit}") from None


def si_unit_for_dimension(dimension: str) -> str:
    try:
        return _SI_UNITS[dimension]
    except KeyError:
        raise UnitError(f"UNKNOWN_DIMENSION:{dimension}") from None


def to_si(value: float, unit: str) -> float:
    if unit not in _UNITS:
        raise UnitError(f"UNKNOWN_UNIT:{unit}")
    number = finite(value, "quantity")
    _, scale, offset = _UNITS[unit]
    return number * scale + offset


def from_si(value_si: float, unit: str) -> float:
    if unit not in _UNITS:
        raise UnitError(f"UNKNOWN_UNIT:{unit}")
    number = finite(value_si, "quantity")
    _, scale, offset = _UNITS[unit]
    return (number - offset) / scale


@dataclass(frozen=True, slots=True)
class Quantity:
    """A finite scalar carrying its unit; canonicalized to SI on serialization."""

    value: float
    unit: str

    def __post_init__(self) -> None:
        if self.unit not in _UNITS:
            raise UnitError(f"UNKNOWN_UNIT:{self.unit}")
        finite(self.value, "quantity")

    @property
    def dimension(self) -> str:
        return dimension_of(self.unit)

    @property
    def value_si(self) -> float:
        return to_si(self.value, self.unit)

    def to_unit(self, unit: str) -> Quantity:
        if dimension_of(unit) != self.dimension:
            raise UnitError(f"QUANTITY_DIMENSION_MISMATCH:{unit}:{self.dimension}")
        return Quantity(value=from_si(self.value_si, unit), unit=unit)

    def canonical(self) -> dict[str, object]:
        return {"valueSI": round(self.value_si, 15), "dimension": self.dimension}


def require_dimension(quantity: Quantity, dimension: str, label: str) -> None:
    """Fail closed when a quantity does not carry the expected dimension."""

    if quantity.dimension != dimension:
        raise UnitError(
            f"QUANTITY_DIMENSION_MISMATCH:{label}:{quantity.dimension}:{dimension}"
        )


DEGREES = pi / 180.0

__all__ = [
    "DEGREES",
    "SI_UNITS",
    "Quantity",
    "dimension_of",
    "from_si",
    "require_dimension",
    "require_unit",
    "si_unit_for_dimension",
    "to_si",
]
