"""Unit-safe flight quantities for the canonical airframe state contract.

The vocabulary is shared byte-for-byte with ``packages/schema/src/vehicle_state.ts``
so a hash is unit-invariant across the two languages. Canonical serialization
normalizes every value to SI; a quantity can never change dimension silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

from .canonical import canonical_number

# unit label -> (dimension, scale to SI, offset to SI): si = value * scale + offset
_UNIT_TABLE: dict[str, tuple[str, float, float]] = {
    "dimensionless": ("dimensionless", 1.0, 0.0),
    "kg": ("mass", 1.0, 0.0),
    "g": ("mass", 1e-3, 0.0),
    "mg": ("mass", 1e-6, 0.0),
    "lbm": ("mass", 0.45359237, 0.0),
    "slug": ("mass", 14.59390294, 0.0),
    "m": ("length", 1.0, 0.0),
    "cm": ("length", 1e-2, 0.0),
    "mm": ("length", 1e-3, 0.0),
    "in": ("length", 0.0254, 0.0),
    "ft": ("length", 0.3048, 0.0),
    "km": ("length", 1e3, 0.0),
    "m2": ("area", 1.0, 0.0),
    "cm2": ("area", 1e-4, 0.0),
    "mm2": ("area", 1e-6, 0.0),
    "ft2": ("area", 0.09290304, 0.0),
    "s": ("time", 1.0, 0.0),
    "min": ("time", 60.0, 0.0),
    "h": ("time", 3600.0, 0.0),
    "m/s": ("velocity", 1.0, 0.0),
    "cm/s": ("velocity", 1e-2, 0.0),
    "km/h": ("velocity", 1000.0 / 3600.0, 0.0),
    "kt": ("velocity", 1852.0 / 3600.0, 0.0),
    "ft/s": ("velocity", 0.3048, 0.0),
    "mph": ("velocity", 0.44704, 0.0),
    "m/s2": ("acceleration", 1.0, 0.0),
    "g0": ("acceleration", 9.80665, 0.0),
    "ft/s2": ("acceleration", 0.3048, 0.0),
    "N": ("force", 1.0, 0.0),
    "kN": ("force", 1e3, 0.0),
    "lbf": ("force", 4.4482216152605, 0.0),
    "kgf": ("force", 9.80665, 0.0),
    "N.m": ("moment", 1.0, 0.0),
    "kN.m": ("moment", 1e3, 0.0),
    "lbf.ft": ("moment", 1.3558179483314004, 0.0),
    "kg.m2": ("moment_of_inertia", 1.0, 0.0),
    "g.m2": ("moment_of_inertia", 1e-3, 0.0),
    "Pa": ("pressure", 1.0, 0.0),
    "hPa": ("pressure", 100.0, 0.0),
    "kPa": ("pressure", 1e3, 0.0),
    "MPa": ("pressure", 1e6, 0.0),
    "bar": ("pressure", 1e5, 0.0),
    "atm": ("pressure", 101325.0, 0.0),
    "psi": ("pressure", 6894.757293168361, 0.0),
    "K": ("temperature", 1.0, 0.0),
    "degC": ("temperature", 1.0, 273.15),
    "kg/m3": ("density", 1.0, 0.0),
    "g/cm3": ("density", 1e3, 0.0),
    "rad": ("angle", 1.0, 0.0),
    "deg": ("angle", pi / 180.0, 0.0),
    "rad/s": ("angular_rate", 1.0, 0.0),
    "deg/s": ("angular_rate", pi / 180.0, 0.0),
    "rpm": ("rotational_speed", 1.0 / 60.0, 0.0),
    "rev/s": ("rotational_speed", 1.0, 0.0),
    "kg/s": ("mass_flow", 1.0, 0.0),
    "kg/h": ("mass_flow", 1.0 / 3600.0, 0.0),
    "lbm/s": ("mass_flow", 0.45359237, 0.0),
    "J/(kg.K)": ("specific_gas_constant", 1.0, 0.0),
    "kJ/(kg.K)": ("specific_gas_constant", 1e3, 0.0),
    "W": ("power", 1.0, 0.0),
    "kW": ("power", 1e3, 0.0),
    "hp": ("power", 745.6998715822702, 0.0),
}

_SI_UNIT_LABELS: dict[str, str] = {
    "dimensionless": "dimensionless",
    "mass": "kg",
    "length": "m",
    "area": "m2",
    "time": "s",
    "velocity": "m/s",
    "acceleration": "m/s2",
    "force": "N",
    "moment": "N.m",
    "moment_of_inertia": "kg.m2",
    "pressure": "Pa",
    "temperature": "K",
    "density": "kg/m3",
    "angle": "rad",
    "angular_rate": "rad/s",
    "rotational_speed": "rev/s",
    "mass_flow": "kg/s",
    "specific_gas_constant": "J/(kg.K)",
    "power": "W",
}


def dimension_of(unit: str) -> str:
    """Return the physical dimension of a unit label, failing closed if unknown."""
    try:
        return _UNIT_TABLE[unit][0]
    except KeyError:
        raise ValueError(f"UNKNOWN_UNIT:{unit}") from None


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


def from_si(value_si: float, unit: str) -> float:
    """Invert :func:`to_si`; the value must stay finite and the unit must be known."""
    if unit not in _UNIT_TABLE:
        raise ValueError(f"UNKNOWN_UNIT:{unit}")
    if value_si != value_si or value_si in (float("inf"), float("-inf")):
        raise ValueError("NONFINITE_QUANTITY_VALUE")
    _, scale, offset = _UNIT_TABLE[unit]
    return (value_si - offset) / scale


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

    def to_unit(self, unit: str) -> Quantity:
        """Re-express this quantity in another unit of the same dimension."""
        if dimension_of(unit) != self.dimension:
            raise ValueError(f"QUANTITY_DIMENSION_MISMATCH:{unit}:{self.dimension}")
        _, scale, offset = _UNIT_TABLE[unit]
        return Quantity(value=(self.value_si - offset) / scale, unit=unit)

    def canonical(self) -> dict[str, object]:
        return {"valueSI": canonical_number(self.value_si), "dimension": self.dimension}


@dataclass(frozen=True, slots=True)
class Vec3:
    """A three-component quantity expressed in a declared reference frame."""

    x: float
    y: float
    z: float
    unit: str
    frame: str

    def __post_init__(self) -> None:
        if self.unit not in _UNIT_TABLE:
            raise ValueError(f"UNKNOWN_UNIT:{self.unit}")
        for label, component in (("x", self.x), ("y", self.y), ("z", self.z)):
            if component != component or component in (float("inf"), float("-inf")):
                raise ValueError(f"NONFINITE_VECTOR_COMPONENT:{label}")
        if not self.frame.strip():
            raise ValueError("VECTOR_FRAME_REQUIRED")

    @property
    def dimension(self) -> str:
        return dimension_of(self.unit)

    @property
    def value_si(self) -> tuple[float, float, float]:
        return (to_si(self.x, self.unit), to_si(self.y, self.unit), to_si(self.z, self.unit))

    def canonical(self) -> dict[str, object]:
        x, y, z = self.value_si
        return {
            "x": canonical_number(x),
            "y": canonical_number(y),
            "z": canonical_number(z),
            "dimension": self.dimension,
            "frame": self.frame,
        }


def require_dimension(quantity: Quantity | Vec3, dimension: str, label: str) -> None:
    """Fail closed when a scalar or vector does not carry the expected dimension."""
    if quantity.dimension != dimension:
        raise ValueError(f"QUANTITY_DIMENSION_MISMATCH:{label}:{quantity.dimension}:{dimension}")
