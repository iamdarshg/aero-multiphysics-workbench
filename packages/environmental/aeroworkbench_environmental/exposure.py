"""Generic environment/exposure state.

An exposure is a declared event with typed physical drivers, not a hidden
coefficient. The same contract represents icing/supercooled droplets, rain/water
ingestion, sand/dust, salt/corrosive environment, particulate contamination,
thermal cycling, and foreign-object impact without encoding any product-specific
assumption. Units are validated per driver; an unknown, missing, or wrong-
dimension driver fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import EnvironmentalError
from .units import Quantity, require_dimension

#: Reserved if a raw angle is ever needed for an exposure driver.
ANGLE_DIMENSION = "dimensionless"


class ExposureKind(StrEnum):
    ICING = "icing"
    RAIN_INGESTION = "rain_ingestion"
    SAND_DUST = "sand_dust"
    SALT_CORROSIVE = "salt_corrosive"
    PARTICULATE_FOULING = "particulate_fouling"
    THERMAL_CYCLING = "thermal_cycling"
    FOREIGN_OBJECT_IMPACT = "foreign_object_impact"


#: Required driver name -> expected physical dimension for each exposure kind.
EXPOSURE_DRIVERS: dict[ExposureKind, tuple[tuple[str, str], ...]] = {
    ExposureKind.ICING: (
        ("ambient_temperature", "temperature"),
        ("droplet_diameter", "length"),
        ("duration", "time"),
        ("impact_speed", "velocity"),
        ("water_content", "density"),
    ),
    ExposureKind.RAIN_INGESTION: (
        ("duration", "time"),
        ("impact_speed", "velocity"),
        ("water_content", "density"),
    ),
    ExposureKind.SAND_DUST: (
        ("duration", "time"),
        ("impact_speed", "velocity"),
        ("particle_concentration", "density"),
        ("particle_diameter", "length"),
    ),
    ExposureKind.SALT_CORROSIVE: (
        ("duration", "time"),
        ("relative_humidity", "dimensionless"),
        ("salt_concentration", "density"),
    ),
    ExposureKind.PARTICULATE_FOULING: (
        ("deposit_rate", "mass_per_area_time"),
        ("duration", "time"),
    ),
    ExposureKind.THERMAL_CYCLING: (
        ("cycles", "dimensionless"),
        ("temperature_swing", "temperature"),
    ),
    ExposureKind.FOREIGN_OBJECT_IMPACT: (
        ("impact_speed", "velocity"),
        ("impactor_diameter", "length"),
        ("impactor_mass", "mass"),
    ),
}


@dataclass(frozen=True, slots=True)
class ExposureSpec:
    """One declared exposure event with typed physical drivers."""

    kind: ExposureKind
    drivers: tuple[tuple[str, Quantity], ...]

    def __post_init__(self) -> None:
        required = dict(EXPOSURE_DRIVERS[self.kind])
        provided = dict(self.drivers)
        if len(provided) != len(self.drivers):
            raise EnvironmentalError(f"exposure.duplicateDriver:{self.kind.value}")
        missing = sorted(set(required) - set(provided))
        if missing:
            raise EnvironmentalError(
                f"exposure.missingDriver:{self.kind.value}:{','.join(missing)}"
            )
        unknown = sorted(set(provided) - set(required))
        if unknown:
            raise EnvironmentalError(
                f"exposure.unknownDriver:{self.kind.value}:{','.join(unknown)}"
            )
        for name in sorted(required):
            require_dimension(provided[name], required[name], f"exposure.{name}")
        for name in ("duration",):
            if name in provided and provided[name].value_si <= 0.0:
                raise EnvironmentalError(f"exposure.nonPositive:{name}")
        for name, quantity in provided.items():
            if name == "ambient_temperature":
                continue
            if quantity.value_si < 0.0:
                raise EnvironmentalError(f"exposure.negative:{name}")
        object.__setattr__(self, "drivers", tuple(sorted(self.drivers)))

    def has(self, name: str) -> bool:
        return name in dict(self.drivers)

    def driver(self, name: str) -> Quantity:
        try:
            return dict(self.drivers)[name]
        except KeyError:
            raise EnvironmentalError(f"exposure.driverNotDeclared:{name}") from None

    def si(self, name: str) -> float:
        return self.driver(name).value_si

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "drivers": {name: quantity.canonical() for name, quantity in self.drivers},
        }


@dataclass(frozen=True, slots=True)
class EnvironmentState:
    """Revisioned environment setting plus its declared exposures.

    ``atmosphere_model`` is a declared reference identifier only; this contract
    never evaluates an atmosphere model (see ``aeroworkbench_fluid_properties``).
    """

    environment_id: str
    revision: int
    atmosphere_model: str
    exposures: tuple[ExposureSpec, ...] = ()
    ambient_temperature: Quantity | None = None

    def __post_init__(self) -> None:
        if not self.environment_id.strip():
            raise EnvironmentalError("environment.environmentId is required")
        if self.revision < 0:
            raise EnvironmentalError("environment.revision must be >= 0")
        if not self.atmosphere_model.strip():
            raise EnvironmentalError("environment.atmosphereModel is required")
        if self.ambient_temperature is not None:
            require_dimension(self.ambient_temperature, "temperature", "ambientTemperature")
        kinds = [exposure.kind for exposure in self.exposures]
        if len(kinds) != len(set(kinds)):
            raise EnvironmentalError("environment.duplicateExposureKind")
        object.__setattr__(
            self, "exposures", tuple(sorted(self.exposures, key=lambda item: item.kind.value))
        )

    def exposure(self, kind: ExposureKind) -> ExposureSpec | None:
        for exposure in self.exposures:
            if exposure.kind is kind:
                return exposure
        return None

    def with_exposure(self, exposure: ExposureSpec, *, revision: int) -> EnvironmentState:
        remaining = tuple(item for item in self.exposures if item.kind is not exposure.kind)
        return EnvironmentState(
            environment_id=self.environment_id,
            revision=revision,
            atmosphere_model=self.atmosphere_model,
            exposures=(*remaining, exposure),
            ambient_temperature=self.ambient_temperature,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "environmentId": self.environment_id,
            "revision": self.revision,
            "atmosphereModel": self.atmosphere_model,
            "ambientTemperature": (
                None if self.ambient_temperature is None else self.ambient_temperature.canonical()
            ),
            "exposures": [exposure.canonical_payload() for exposure in self.exposures],
        }


__all__ = [
    "ANGLE_DIMENSION",
    "EXPOSURE_DRIVERS",
    "EnvironmentState",
    "ExposureKind",
    "ExposureSpec",
]
