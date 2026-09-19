"""Humid-air composition from relative humidity.

Water saturation pressure uses the Magnus form recommended by Alduchov and
Eskridge (1996), valid from -40 to +50 degrees Celsius. Relative humidity is
converted to a vapour mole fraction at the local pressure; when the requested
humidity cannot exist at that pressure the request fails closed.
"""

from __future__ import annotations

from math import exp, isfinite

from .composition import Composition
from .errors import FluidValidationError, FluidValidityError
from .validity import ValidityRange

_MAGNUS_A_PA = 610.94
_MAGNUS_B = 17.625
_MAGNUS_C_K = 243.04

SATURATION_VALIDITY = ValidityRange("temperature", "K", 233.15, 323.15)


def saturation_pressure_water_pa(temperature_k: float) -> float:
    """Saturation pressure of water vapour in Pa (Alduchov-Eskridge Magnus fit)."""
    SATURATION_VALIDITY.require(temperature_k, label="temperature")
    temperature_c = temperature_k - 273.15
    return _MAGNUS_A_PA * exp(_MAGNUS_B * temperature_c / (temperature_c + _MAGNUS_C_K))


def humid_air_composition(
    dry_air: Composition,
    *,
    temperature_k: float,
    pressure_pa: float,
    relative_humidity: float,
) -> Composition:
    """Return the moist-air composition at a state; fails on impossible humidity."""
    if not (isfinite(relative_humidity) and 0.0 <= relative_humidity <= 1.0):
        raise FluidValidationError("RELATIVE_HUMIDITY_OUT_OF_RANGE")
    if not (isfinite(pressure_pa) and pressure_pa > 0):
        raise FluidValidationError("INVALID_PRESSURE")
    if relative_humidity == 0.0:
        return Composition.from_mole_fractions(dry_air.species, source=dry_air.source)
    vapour_pressure = relative_humidity * saturation_pressure_water_pa(temperature_k)
    vapour_fraction = vapour_pressure / pressure_pa
    if vapour_fraction >= 1.0:
        raise FluidValidityError("HUMIDITY_EXCEEDS_SATURATION_AT_PRESSURE")
    scale = 1.0 - vapour_fraction
    fractions = tuple(
        (name, fraction * scale)
        for name, fraction in dry_air.species
        if name != "h2o"
    ) + (("h2o", vapour_fraction),)
    return Composition.from_mole_fractions(
        fractions, source=f"humid-air:rh={relative_humidity}"
    )
