"""SI unit labels for composite structural results.

Every scalar leaving this package is an SI quantity, and every result exposes a
``units()`` mapping from scalar name to SI unit label so membrane/bending
resultants, ply stresses, and failure indices are never compared as bare
numbers. The label set extends the shared durability SI labels with the plate
resultant and areal-density units laminate analysis needs; an unknown label
fails closed.
"""

from __future__ import annotations

from aeroworkbench_durability.units import SI_UNITS as _CORE_SI_UNITS
from aeroworkbench_durability.units import UnitError as UnitError

__all__ = ["SI_UNITS", "UnitError", "require_unit"]

SI_UNITS: frozenset[str] = frozenset(
    set(_CORE_SI_UNITS)
    | {
        "N/m",
        "N*m",
        "N*m^2",
        "kg/m^2",
        "kg/m",
        "m^2",
        "m^3",
        "rad",
        "1/Pa",
    }
)


def require_unit(unit: str) -> str:
    """Return ``unit`` when it is a known composite SI label, else fail closed."""

    if unit not in SI_UNITS:
        raise UnitError(f"UNKNOWN_UNIT:{unit}")
    return unit
