"""SI unit labels for aeroelastic results.

Every scalar leaving this package is an SI quantity. Results expose a
``units()`` mapping from scalar name to its SI unit label so modal, stability,
forced-response, gust, and contact closures never compare bare numbers. An
unknown unit label fails closed.
"""

from __future__ import annotations

SI_UNITS: frozenset[str] = frozenset(
    {
        "dimensionless",
        "m",
        "m2",
        "m3",
        "kg",
        "kg/m",
        "kg*m",
        "kg*m2",
        "s",
        "K",
        "J",
        "W",
        "W/m2",
        "Pa",
        "Pa*s",
        "N",
        "N/m",
        "N/m2",
        "N*m",
        "N*m*s",
        "N*s/m",
        "N*s2/m",
        "m/s",
        "m/s2",
        "rad",
        "rad/s",
        "1/s",
        "Hz",
        "Hz2",
        "N/Hz",
        "m2/Hz",
        "m2/s",
        "kg/m3",
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
