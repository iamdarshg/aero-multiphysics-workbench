"""Generic unit dimensions, compatibility checks, and conversions.

The scalar coordinator and field coupler enforce units at the adapter level:
OpenMDAO itself sees plain floats while this module remains the authoritative
unit gate. Dimensions are generic physical dimensions; no application
(e.g. motor/EDF/battery) concepts appear here.
"""

from __future__ import annotations

# unit label -> (dimension key, scale to SI, offset to SI: si = value * scale + offset)
_UNIT_TABLE: dict[str, tuple[str, float, float]] = {
    "dimensionless": ("dimensionless", 1.0, 0.0),
    "m": ("length", 1.0, 0.0),
    "mm": ("length", 1e-3, 0.0),
    "s": ("time", 1.0, 0.0),
    "m/s": ("velocity", 1.0, 0.0),
    "Hz": ("frequency", 1.0, 0.0),
    "rpm": ("frequency", 1.0 / 60.0, 0.0),
    "Pa": ("pressure", 1.0, 0.0),
    "N/m2": ("traction", 1.0, 0.0),
    "N": ("force", 1.0, 0.0),
    "N/m": ("stiffness", 1.0, 0.0),
    "N.m": ("torque", 1.0, 0.0),
    "Pa.s": ("viscosity", 1.0, 0.0),
    "K": ("temperature", 1.0, 0.0),
    "degC": ("temperature", 1.0, 273.15),
    "W": ("power", 1.0, 0.0),
    "W/m2": ("thermal_flux", 1.0, 0.0),
    "W/m.K": ("conductivity", 1.0, 0.0),
    "V": ("voltage", 1.0, 0.0),
    "A": ("current", 1.0, 0.0),
    "A/m2": ("electrical_flux", 1.0, 0.0),
    "A.h": ("charge", 3600.0, 0.0),
    "kg/m3": ("density", 1.0, 0.0),
    "kg/s": ("mass_flux", 1.0, 0.0),
    "m3/s": ("volume_flux", 1.0, 0.0),
}


def dimension_of(unit: str) -> str:
    """Return the physical dimension key for a unit label."""
    try:
        return _UNIT_TABLE[unit][0]
    except KeyError:
        raise ValueError(f"UNKNOWN_UNIT:{unit}") from None


def units_compatible(first: str, second: str) -> bool:
    """Two units are compatible when they share a physical dimension."""
    return dimension_of(first) == dimension_of(second)


def convert_value(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a finite value between two compatible units."""
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("NONFINITE_VALUE_FOR_CONVERSION")
    dimension, from_scale, from_offset = _UNIT_TABLE.get(from_unit, ("", 0.0, 0.0))
    if not dimension:
        raise ValueError(f"UNKNOWN_UNIT:{from_unit}")
    to_dimension, to_scale, to_offset = _UNIT_TABLE.get(to_unit, ("", 0.0, 0.0))
    if not to_dimension:
        raise ValueError(f"UNKNOWN_UNIT:{to_unit}")
    if dimension != to_dimension:
        raise ValueError(f"UNIT_MISMATCH:{from_unit}:{to_unit}")
    si_value = value * from_scale + from_offset
    return (si_value - to_offset) / to_scale
