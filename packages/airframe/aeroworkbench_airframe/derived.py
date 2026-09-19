"""Derived flight quantities that always carry provenance.

These are analytical definitions only (no solver execution). Every returned
quantity records its inputs hash and the analytical model identity so downstream
results can distinguish a definition from a measured or fabricated result.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .units import Quantity, require_dimension

_MODEL = "airframe-flight-quantities"
_MODEL_VERSION = "1.0"
_ASSUMPTIONS = (
    "Analytical definition only; no solver execution.",
    "Atmosphere and gravity are declared reference values, not evaluated here.",
)


@dataclass(frozen=True, slots=True)
class DerivedQuantity:
    """A computed quantity with the provenance of its analytical definition."""

    name: str
    quantity: Quantity
    provenance: Provenance


def _provenance(inputs: dict[str, float]) -> Provenance:
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=_MODEL,
        model_version=_MODEL_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=inputs,
        assumptions=_ASSUMPTIONS,
    )


def mach_number(true_airspeed: Quantity, speed_of_sound: Quantity) -> DerivedQuantity:
    require_dimension(true_airspeed, "velocity", "trueAirspeed")
    require_dimension(speed_of_sound, "velocity", "speedOfSound")
    if speed_of_sound.value_si <= 0:
        raise ValueError("NONPOSITIVE_SPEED_OF_SOUND")
    value = true_airspeed.value_si / speed_of_sound.value_si
    return DerivedQuantity(
        name="mach",
        quantity=Quantity(value=value, unit="dimensionless"),
        provenance=_provenance(
            {"trueAirspeed": true_airspeed.value_si, "speedOfSound": speed_of_sound.value_si}
        ),
    )


def dynamic_pressure(density: Quantity, true_airspeed: Quantity) -> DerivedQuantity:
    require_dimension(density, "density", "density")
    require_dimension(true_airspeed, "velocity", "trueAirspeed")
    value = 0.5 * density.value_si * true_airspeed.value_si * true_airspeed.value_si
    return DerivedQuantity(
        name="dynamicPressure",
        quantity=Quantity(value=value, unit="Pa"),
        provenance=_provenance(
            {"density": density.value_si, "trueAirspeed": true_airspeed.value_si}
        ),
    )


def equivalent_airspeed(
    true_airspeed: Quantity, density: Quantity, sea_level_density: Quantity
) -> DerivedQuantity:
    require_dimension(true_airspeed, "velocity", "trueAirspeed")
    require_dimension(density, "density", "density")
    require_dimension(sea_level_density, "density", "seaLevelDensity")
    if density.value_si < 0 or sea_level_density.value_si <= 0:
        raise ValueError("INVALID_DENSITY_FOR_EQUIVALENT_AIRSPEED")
    value = true_airspeed.value_si * sqrt(density.value_si / sea_level_density.value_si)
    return DerivedQuantity(
        name="equivalentAirspeed",
        quantity=Quantity(value=value, unit="m/s"),
        provenance=_provenance(
            {
                "trueAirspeed": true_airspeed.value_si,
                "density": density.value_si,
                "seaLevelDensity": sea_level_density.value_si,
            }
        ),
    )


def weight_force(mass: Quantity, gravity: Quantity) -> DerivedQuantity:
    require_dimension(mass, "mass", "mass")
    require_dimension(gravity, "acceleration", "gravity")
    return DerivedQuantity(
        name="weight",
        quantity=Quantity(value=mass.value_si * gravity.value_si, unit="N"),
        provenance=_provenance({"mass": mass.value_si, "gravity": gravity.value_si}),
    )
