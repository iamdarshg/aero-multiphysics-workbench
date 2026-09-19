"""SI unit labels for durability results.

Every scalar leaving this package is an SI quantity. Results expose a
``units()`` mapping from scalar name to its SI unit label so life, damage,
crack-growth, and structural closures never compare bare numbers. An unknown
unit label fails closed.
"""

from __future__ import annotations

SI_UNITS: frozenset[str] = frozenset(
    {
        "dimensionless",
        "1",
        "1/m",
        "1/K",
        "1/cycle",
        "1/h",
        "m",
        "mm",
        "m/cycle",
        "m2",
        "m3",
        "kg",
        "kg/m3",
        "kg/s",
        "s",
        "h",
        "K",
        "J",
        "J/(kg K)",
        "W",
        "W/(m K)",
        "Pa",
        "Pa*m^0.5",
        "Pa*s",
        "N",
        "N*m",
        "cycle",
        "reversal",
        "block",
        "count",
    }
)


class UnitError(ValueError):
    """Raised for an unknown unit label."""


def require_unit(unit: str) -> str:
    """Return ``unit`` when it is a known SI label, else fail closed."""

    if unit not in SI_UNITS:
        raise UnitError(f"UNKNOWN_UNIT:{unit}")
    return unit


__all__ = ["SI_UNITS", "UnitError", "require_unit"]
