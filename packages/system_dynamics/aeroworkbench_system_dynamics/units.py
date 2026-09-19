"""SI unit labels accepted by the transient system-dynamics contracts."""

from __future__ import annotations

from .errors import SystemDynamicsError


class UnitError(SystemDynamicsError):
    """An unknown unit label was supplied; the call fails closed."""

    code = "UNKNOWN_UNIT"


SI_UNITS: frozenset[str] = frozenset(
    {
        "1",
        "s",
        "rad",
        "rad/s",
        "rad/s2",
        "Hz",
        "m",
        "m/s",
        "m/s2",
        "m2",
        "m3",
        "m3/s",
        "kg",
        "kg/s",
        "kg*m2",
        "N",
        "N*m",
        "N*m*s",
        "N*m*s/rad",
        "N*s/m",
        "Pa",
        "Pa/s",
        "K",
        "K/s",
        "J",
        "J/K",
        "J/(kg*K)",
        "W",
        "W/K",
        "A",
        "A*s",
        "A/s",
        "V",
        "Ohm",
        "C",
    }
)


def require_unit(label: str) -> str:
    """Return the label when known; otherwise fail closed."""

    if label not in SI_UNITS:
        raise UnitError(f"UNKNOWN_UNIT:{label}")
    return label


__all__ = ["SI_UNITS", "UnitError", "require_unit"]
