"""Generic unit normalization for manufacturing and hardware limits.

Limits and measurements may be declared in engineering units but are always
compared in SI. An unknown unit fails closed instead of being silently treated
as dimensionless; every declared unit is preserved for human-readable reports.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SUPPORTED_UNITS",
    "UnitConversionError",
    "UnitDefinition",
    "from_si",
    "to_si",
    "unit_dimension",
]


class UnitConversionError(ValueError):
    """Raised when a unit is unknown or a conversion is not defined."""


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    dimension: str
    scale: float
    offset: float = 0.0


def _unit(dimension: str, scale: float, offset: float = 0.0) -> UnitDefinition:
    return UnitDefinition(dimension, scale, offset)


#: Every unit this package can normalize. Offsets implement absolute scales
#: (only temperature uses a non-zero offset).
SUPPORTED_UNITS: dict[str, UnitDefinition] = {
    "1": _unit("dimensionless", 1.0),
    "": _unit("dimensionless", 1.0),
    "%": _unit("dimensionless", 0.01),
    "m": _unit("length", 1.0),
    "dm": _unit("length", 0.1),
    "cm": _unit("length", 0.01),
    "mm": _unit("length", 1e-3),
    "um": _unit("length", 1e-6),
    "in": _unit("length", 0.0254),
    "ft": _unit("length", 0.3048),
    "m2": _unit("area", 1.0),
    "cm2": _unit("area", 1e-4),
    "mm2": _unit("area", 1e-6),
    "m3": _unit("volume", 1.0),
    "cm3": _unit("volume", 1e-6),
    "mm3": _unit("volume", 1e-9),
    "L": _unit("volume", 1e-3),
    "kg": _unit("mass", 1.0),
    "g": _unit("mass", 1e-3),
    "mg": _unit("mass", 1e-6),
    "t": _unit("mass", 1e3),
    "lb": _unit("mass", 0.45359237),
    "s": _unit("time", 1.0),
    "ms": _unit("time", 1e-3),
    "min": _unit("time", 60.0),
    "h": _unit("time", 3600.0),
    "Hz": _unit("frequency", 1.0),
    "kHz": _unit("frequency", 1e3),
    "rpm": _unit("frequency", 1.0 / 60.0),
    "rad/s": _unit("angular_velocity", 1.0),
    "deg/s": _unit("angular_velocity", 0.017453292519943295),
    "rad/s2": _unit("angular_acceleration", 1.0),
    "rad": _unit("angle", 1.0),
    "deg": _unit("angle", 0.017453292519943295),
    "m/s": _unit("velocity", 1.0),
    "mm/s": _unit("velocity", 1e-3),
    "km/h": _unit("velocity", 1.0 / 3.6),
    "ft/s": _unit("velocity", 0.3048),
    "mph": _unit("velocity", 0.44704),
    "Mach": _unit("mach", 1.0),
    "N": _unit("force", 1.0),
    "kN": _unit("force", 1e3),
    "lbf": _unit("force", 4.4482216152605),
    "N*m": _unit("torque", 1.0),
    "N.m": _unit("torque", 1.0),
    "kN*m": _unit("torque", 1e3),
    "N*mm": _unit("torque", 1e-3),
    "Pa": _unit("pressure", 1.0),
    "kPa": _unit("pressure", 1e3),
    "MPa": _unit("pressure", 1e6),
    "GPa": _unit("pressure", 1e9),
    "bar": _unit("pressure", 1e5),
    "psi": _unit("pressure", 6894.757293168),
    "W": _unit("power", 1.0),
    "kW": _unit("power", 1e3),
    "hp": _unit("power", 745.6998715822702),
    "K": _unit("temperature", 1.0),
    "degC": _unit("temperature", 1.0, 273.15),
    "degF": _unit("temperature", 5.0 / 9.0, 255.3722222222222),
}


def unit_dimension(unit: str) -> str:
    """Return the physical dimension of ``unit`` or fail closed."""

    definition = SUPPORTED_UNITS.get(unit)
    if definition is None:
        raise UnitConversionError(f"UNKNOWN_UNIT:{unit}")
    return definition.dimension


def to_si(value: float, unit: str) -> float:
    """Convert ``value`` in ``unit`` to SI (absolute for temperature)."""

    definition = SUPPORTED_UNITS.get(unit)
    if definition is None:
        raise UnitConversionError(f"UNKNOWN_UNIT:{unit}")
    return value * definition.scale + definition.offset


def from_si(value_si: float, unit: str) -> float:
    """Convert an SI value back into ``unit`` (inverse of :func:`to_si`)."""

    definition = SUPPORTED_UNITS.get(unit)
    if definition is None:
        raise UnitConversionError(f"UNKNOWN_UNIT:{unit}")
    return (value_si - definition.offset) / definition.scale
