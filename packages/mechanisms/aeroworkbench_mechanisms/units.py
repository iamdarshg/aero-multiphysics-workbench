"""Unit labels for mechanical-interface results.

Every scalar leaving this package is an SI quantity. Results expose a
``units()`` mapping from scalar name to its SI unit label so structural,
rotordynamic, thermal, and fluid closures never compare bare numbers. An
unknown unit label fails closed.
"""

from __future__ import annotations

SI_UNITS: frozenset[str] = frozenset(
    {
        "dimensionless",
        "m",
        "m2",
        "m3",
        "mm",
        "kg",
        "kg/s",
        "kg/m3",
        "s",
        "K",
        "J",
        "W",
        "W/m2",
        "W/m2/K",
        "Pa",
        "Pa*s",
        "N",
        "N/m",
        "N/m2",
        "N/m3",
        "N*m",
        "N*m/rad",
        "N*m*s/rad",
        "N*m/s",
        "N*s/m",
        "N*s/m2",
        "m/s",
        "m/s2",
        "m2/s",
        "m3/s",
        "rad",
        "rad/s",
        "1/s",
        "1/m",
        "1/Pa",
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
