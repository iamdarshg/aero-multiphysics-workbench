"""Thermodynamic stations carrying unit-bearing total/static state.

Every state field is optional and only present when the selected architecture
needs it. Working-fluid identity, composition, swirl, and annulus geometry
references travel with the station so downstream analysis has both the state and
the geometry/material context.
"""

from __future__ import annotations

from dataclasses import dataclass

from .units import Quantity, require_dimension


@dataclass(frozen=True, slots=True)
class WorkingFluid:
    """Working-fluid identity plus optional species mass fractions."""

    identity: str
    composition: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise ValueError("FLUID_IDENTITY_REQUIRED")
        species = [name for name, _ in self.composition]
        if len(species) != len(set(species)):
            raise ValueError("DUPLICATE_SPECIES")
        for name, fraction in self.composition:
            if not name.strip():
                raise ValueError("SPECIES_NAME_REQUIRED")
            if fraction != fraction or fraction < 0 or fraction > 1:
                raise ValueError(f"INVALID_MASS_FRACTION:{name}")
        if self.composition:
            total = sum(fraction for _, fraction in self.composition)
            if abs(total - 1.0) > 1e-6:
                raise ValueError("MASS_FRACTIONS_MUST_SUM_TO_ONE")

    def canonical(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "composition": {name: fraction for name, fraction in sorted(self.composition)},
        }


@dataclass(frozen=True, slots=True)
class AnnulusGeometryRef:
    """Annulus area/radius plus a stable reference into a geometry definition."""

    area: Quantity | None = None
    radius: Quantity | None = None
    hub_radius: Quantity | None = None
    tip_radius: Quantity | None = None
    geometry_ref: str | None = None

    def __post_init__(self) -> None:
        for label, quantity in (("area", self.area), ("radius", self.radius)):
            if quantity is not None:
                require_dimension(quantity, "area" if label == "area" else "length", label)
        for label, quantity in (
            ("hubRadius", self.hub_radius),
            ("tipRadius", self.tip_radius),
        ):
            if quantity is not None:
                require_dimension(quantity, "length", label)
        if (
            self.hub_radius is not None
            and self.tip_radius is not None
            and self.hub_radius.value_si >= self.tip_radius.value_si
        ):
            raise ValueError("HUB_RADIUS_MUST_BE_SMALLER_THAN_TIP_RADIUS")

    def canonical(self) -> dict[str, object]:
        return {
            "area": None if self.area is None else self.area.canonical(),
            "radius": None if self.radius is None else self.radius.canonical(),
            "hubRadius": None if self.hub_radius is None else self.hub_radius.canonical(),
            "tipRadius": None if self.tip_radius is None else self.tip_radius.canonical(),
            "geometryRef": self.geometry_ref,
        }


@dataclass(frozen=True, slots=True)
class StationState:
    """Unit-bearing total/static thermodynamic state at one station."""

    mass_flow: Quantity | None = None
    total_pressure: Quantity | None = None
    static_pressure: Quantity | None = None
    total_temperature: Quantity | None = None
    static_temperature: Quantity | None = None
    density: Quantity | None = None
    velocity: Quantity | None = None
    mach: Quantity | None = None
    tangential_velocity: Quantity | None = None
    swirl_angle: Quantity | None = None
    fluid: WorkingFluid | None = None
    annulus: AnnulusGeometryRef | None = None

    def __post_init__(self) -> None:
        expected = (
            ("massFlow", self.mass_flow, "mass_flow"),
            ("totalPressure", self.total_pressure, "pressure"),
            ("staticPressure", self.static_pressure, "pressure"),
            ("totalTemperature", self.total_temperature, "temperature"),
            ("staticTemperature", self.static_temperature, "temperature"),
            ("density", self.density, "density"),
            ("velocity", self.velocity, "velocity"),
            ("mach", self.mach, "dimensionless"),
            ("tangentialVelocity", self.tangential_velocity, "velocity"),
            ("swirlAngle", self.swirl_angle, "angle"),
        )
        for label, quantity, dimension in expected:
            if quantity is not None:
                require_dimension(quantity, dimension, label)

    def canonical(self) -> dict[str, object]:
        def q(quantity: Quantity | None) -> dict[str, object] | None:
            return None if quantity is None else quantity.canonical()

        return {
            "massFlow": q(self.mass_flow),
            "totalPressure": q(self.total_pressure),
            "staticPressure": q(self.static_pressure),
            "totalTemperature": q(self.total_temperature),
            "staticTemperature": q(self.static_temperature),
            "density": q(self.density),
            "velocity": q(self.velocity),
            "mach": q(self.mach),
            "tangentialVelocity": q(self.tangential_velocity),
            "swirlAngle": q(self.swirl_angle),
            "fluid": None if self.fluid is None else self.fluid.canonical(),
            "annulus": None if self.annulus is None else self.annulus.canonical(),
        }


@dataclass(frozen=True, slots=True)
class Station:
    """One named station with its thermodynamic state."""

    station_id: str
    state: StationState
    name: str | None = None

    def __post_init__(self) -> None:
        if not self.station_id.strip():
            raise ValueError("STATION_ID_REQUIRED")

    def canonical(self) -> dict[str, object]:
        return {"id": self.station_id, "name": self.name, "state": self.state.canonical()}
