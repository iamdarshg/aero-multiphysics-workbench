"""Standard-atmosphere and environment participant.

The ISA model is built from sea-level constants and lapse rates only: layer base
temperatures and pressures are derived with the barometric formula, so there is
no hidden tabulated data. Thermosphere/high-altitude validity is declared and a
query outside it fails closed. Density and speed of sound are evaluated through
the same working-fluid definition used by the rest of the platform, so a gas
path and the atmosphere cannot disagree about air.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from aeroworkbench_core.types import Provenance

from .errors import FluidValidationError
from .fluid import FluidKind, WorkingFluid
from .humidity import humid_air_composition
from .ideal_gas import IdealGasModel
from .property_ids import PropertyFidelity, PropertyId
from .results import DEFAULT_SOFTWARE, SoftwareIdentity, analytical_provenance
from .validity import ValidityRange

GRAVITY_M_S2 = 9.80665
SEA_LEVEL_TEMPERATURE_K = 288.15
SEA_LEVEL_PRESSURE_PA = 101325.0
ISA_TOP_ALTITUDE_M = 84852.0
_MODEL_NAME = "aeroworkbench-fluid-properties:standard-atmosphere"

_ISA_LAPSE: tuple[tuple[float, float], ...] = (
    (0.0, -0.0065),
    (11000.0, 0.0),
    (20000.0, 0.001),
    (32000.0, 0.0028),
    (47000.0, 0.0),
    (51000.0, -0.0028),
    (71000.0, -0.002),
)


@dataclass(frozen=True, slots=True)
class AtmosphereLayer:
    """One ISA layer with a base state and lapse rate; isothermal when rate is 0."""

    base_altitude_m: float
    base_temperature_k: float
    base_pressure_pa: float
    lapse_rate_k_per_m: float

    def canonical(self) -> dict[str, object]:
        return {
            "baseAltitudeM": self.base_altitude_m,
            "baseTemperatureK": self.base_temperature_k,
            "basePressurePa": self.base_pressure_pa,
            "lapseRateKPerM": self.lapse_rate_k_per_m,
        }


@dataclass(frozen=True, slots=True)
class WindState:
    """A horizontal wind vector expressed as speed and heading."""

    speed_m_s: float = 0.0
    heading_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.speed_m_s < 0.0:
            raise FluidValidationError("NEGATIVE_WIND_SPEED")
        if not 0.0 <= self.heading_deg < 360.0:
            raise FluidValidationError("WIND_HEADING_OUT_OF_RANGE")

    def canonical(self) -> dict[str, object]:
        return {"speedMS": self.speed_m_s, "headingDeg": self.heading_deg}


@dataclass(frozen=True, slots=True)
class AtmosphereState:
    """An evaluated environment state at one altitude."""

    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float
    temperature_offset_k: float
    relative_humidity: float
    wind: WindState
    fluid_identity: str
    validity: ValidityRange
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    def canonical(self) -> dict[str, object]:
        return {
            "altitudeM": self.altitude_m,
            "temperatureK": self.temperature_k,
            "pressurePa": self.pressure_pa,
            "densityKgM3": self.density_kg_m3,
            "speedOfSoundMS": self.speed_of_sound_m_s,
            "temperatureOffsetK": self.temperature_offset_k,
            "relativeHumidity": self.relative_humidity,
            "wind": self.wind.canonical(),
            "fluid": self.fluid_identity,
            "validity": self.validity.canonical(),
            "source": self.provenance.source.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _advance(
    temperature_k: float,
    pressure_pa: float,
    lapse_rate_k_per_m: float,
    thickness_m: float,
    gas_constant: float,
) -> tuple[float, float]:
    top_temperature = temperature_k + lapse_rate_k_per_m * thickness_m
    if lapse_rate_k_per_m == 0.0:
        top_pressure = pressure_pa * exp(
            -GRAVITY_M_S2 * thickness_m / (gas_constant * temperature_k)
        )
    else:
        exponent = -GRAVITY_M_S2 / (lapse_rate_k_per_m * gas_constant)
        top_pressure = pressure_pa * (top_temperature / temperature_k) ** exponent
    return top_temperature, top_pressure


def build_isa_layers(fluid: WorkingFluid) -> tuple[AtmosphereLayer, ...]:
    """Derive ISA layer base states from sea-level constants and lapse rates."""
    gas_constant = fluid.specific_gas_constant_j_kg_k
    temperature = SEA_LEVEL_TEMPERATURE_K
    pressure = SEA_LEVEL_PRESSURE_PA
    layers: list[AtmosphereLayer] = []
    for index, (base_altitude, lapse_rate) in enumerate(_ISA_LAPSE):
        layers.append(AtmosphereLayer(base_altitude, temperature, pressure, lapse_rate))
        top_altitude = (
            _ISA_LAPSE[index + 1][0] if index + 1 < len(_ISA_LAPSE) else ISA_TOP_ALTITUDE_M
        )
        temperature, pressure = _advance(
            temperature, pressure, lapse_rate, top_altitude - base_altitude, gas_constant
        )
    return tuple(layers)


@dataclass(frozen=True, slots=True)
class StandardAtmosphere:
    """A layered standard atmosphere bound to a working-fluid definition."""

    model_id: str
    revision: str
    layers: tuple[AtmosphereLayer, ...]
    validity: ValidityRange
    source: str
    fluid: WorkingFluid

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.revision.strip():
            raise FluidValidationError("ATMOSPHERE_IDENTITY_REQUIRED")
        if not self.layers:
            raise FluidValidationError("ATMOSPHERE_REQUIRES_LAYERS")
        if self.validity.quantity != "altitude" or self.validity.unit != "m":
            raise FluidValidationError("ATMOSPHERE_VALIDITY_MUST_BE_ALTITUDE")

    def temperature_pressure(self, altitude_m: float) -> tuple[float, float]:
        """ISA temperature and pressure; fails closed outside the validity range."""
        self.validity.require(altitude_m, label="altitude")
        layer = self.layers[0]
        for candidate in self.layers:
            if candidate.base_altitude_m <= altitude_m:
                layer = candidate
            else:
                break
        thickness = altitude_m - layer.base_altitude_m
        temperature = layer.base_temperature_k + layer.lapse_rate_k_per_m * thickness
        if layer.lapse_rate_k_per_m == 0.0:
            pressure = layer.base_pressure_pa * exp(
                -GRAVITY_M_S2
                * thickness
                / (self.fluid.specific_gas_constant_j_kg_k * layer.base_temperature_k)
            )
        else:
            exponent = -GRAVITY_M_S2 / (
                layer.lapse_rate_k_per_m * self.fluid.specific_gas_constant_j_kg_k
            )
            pressure = layer.base_pressure_pa * (temperature / layer.base_temperature_k) ** exponent
        return temperature, pressure

    def evaluate(
        self,
        *,
        altitude_m: float,
        temperature_offset_k: float = 0.0,
        relative_humidity: float = 0.0,
        wind: WindState | None = None,
    ) -> AtmosphereState:
        isa_temperature, pressure = self.temperature_pressure(altitude_m)
        temperature = isa_temperature + temperature_offset_k
        if temperature <= 0.0:
            raise FluidValidationError("NONPOSITIVE_ATMOSPHERE_TEMPERATURE")
        fluid = self.fluid
        if relative_humidity > 0.0:
            composition = humid_air_composition(
                self.fluid.composition,
                temperature_k=temperature,
                pressure_pa=pressure,
                relative_humidity=relative_humidity,
            )
            fluid = WorkingFluid(
                fluid_id=f"{self.fluid.fluid_id}-humid",
                revision=self.fluid.revision,
                kind=FluidKind.HUMID_AIR,
                composition=composition,
                default_fidelity=PropertyFidelity.CONSTANT_IDEAL_GAS,
                transport=self.fluid.transport,
                source=self.fluid.source,
            )
        evaluation = IdealGasModel(fluid).evaluate(
            temperature_k=temperature, pressure_pa=pressure
        )
        provenance = analytical_provenance(
            _MODEL_NAME,
            {
                "atmosphere": f"{self.model_id}@{self.revision}",
                "altitudeM": altitude_m,
                "temperatureOffsetK": temperature_offset_k,
                "relativeHumidity": relative_humidity,
            },
            "ISA layered barometric model",
        )
        return AtmosphereState(
            altitude_m=altitude_m,
            temperature_k=temperature,
            pressure_pa=pressure,
            density_kg_m3=evaluation.value(PropertyId.DENSITY),
            speed_of_sound_m_s=evaluation.value(PropertyId.SPEED_OF_SOUND),
            temperature_offset_k=temperature_offset_k,
            relative_humidity=relative_humidity,
            wind=wind or WindState(),
            fluid_identity=fluid.identity,
            validity=self.validity,
            provenance=provenance,
        )

    def participant_manifest(self) -> dict[str, object]:
        """A participant-style declaration of this environment model."""
        return {
            "participantId": "environment-standard-atmosphere",
            "modelId": self.model_id,
            "revision": self.revision,
            "validity": self.validity.canonical(),
            "fluid": self.fluid.identity,
            "fluidDigest": self.fluid.digest(),
            "source": self.source,
            "layers": [layer.canonical() for layer in self.layers],
        }


def standard_atmosphere(
    fluid: WorkingFluid,
    *,
    model_id: str = "ISA",
    revision: str = "1",
    source: str = "ICAO/ISO 2533 International Standard Atmosphere",
) -> StandardAtmosphere:
    """Build an ISA model whose layers are derived from the bound fluid's gas constant."""
    return StandardAtmosphere(
        model_id=model_id,
        revision=revision,
        layers=build_isa_layers(fluid),
        validity=ValidityRange("altitude", "m", 0.0, ISA_TOP_ALTITUDE_M),
        source=source,
        fluid=fluid,
    )
