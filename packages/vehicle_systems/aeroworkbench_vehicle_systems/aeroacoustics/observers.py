"""Generic acoustic observer contract: position, weighting, bandwidth, environment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, log10, sqrt
from typing import Any

from .errors import ContractError, ValidityError

__all__ = [
    "EnvironmentSpec",
    "FlightState",
    "ObserverSpec",
    "Weighting",
    "a_weighting_db",
    "absorption_loss_db",
    "apply_weighting",
    "c_weighting_db",
    "closing_speed_m_s",
    "distance_m",
    "doppler_factor",
    "spherical_transmission_loss_db",
]

Vector3 = tuple[float, float, float]


class Weighting(StrEnum):
    """Frequency weighting applied to an observer level, with its standard."""

    NONE = "none"
    A = "a"
    C = "c"


WEIGHTING_STANDARDS: dict[str, str] = {
    Weighting.NONE.value: "unweighted (linear)",
    Weighting.A.value: "IEC 61672-1:2013 A-weighting filter shape",
    Weighting.C.value: "IEC 61672-1:2013 C-weighting filter shape",
}


def _vector(value: Any, name: str) -> Vector3:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ContractError(f"{name} must be a 3-element vector")
    items = tuple(value)
    if len(items) != 3:
        raise ContractError(f"{name} must be a 3-element vector")
    result: list[float] = []
    for index, item in enumerate(items):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ContractError(f"{name}[{index}] must be a number")
        number = float(item)
        if not isfinite(number):
            raise ContractError(f"{name}[{index}] must be finite")
        result.append(number)
    return (result[0], result[1], result[2])


def _finite(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a number")
    number = float(value)
    if not isfinite(number):
        raise ContractError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ContractError(f"{name} must be positive")
    return number


@dataclass(frozen=True, slots=True)
class ObserverSpec:
    """One ground/community observer: identity plus a fixed position."""

    observer_id: str
    position_m: Vector3
    description: str = ""

    def __post_init__(self) -> None:
        if not self.observer_id.strip():
            raise ContractError("observer_id is required")
        object.__setattr__(self, "position_m", _vector(self.position_m, "position_m"))

    def canonical(self) -> dict[str, Any]:
        return {
            "observerId": self.observer_id,
            "positionM": list(self.position_m),
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentSpec:
    """Propagation environment: sound speed, density, and declared absorption."""

    speed_of_sound_m_s: float = 340.0
    density_kg_m3: float = 1.225
    absorption_db_per_m: float = 0.0
    reference_distance_m: float = 1.0

    def __post_init__(self) -> None:
        _finite(self.speed_of_sound_m_s, "speed_of_sound_m_s", positive=True)
        _finite(self.density_kg_m3, "density_kg_m3", positive=True)
        absorption = _finite(self.absorption_db_per_m, "absorption_db_per_m")
        if absorption < 0.0:
            raise ContractError("absorption_db_per_m must be >= 0")
        _finite(self.reference_distance_m, "reference_distance_m", positive=True)

    def canonical(self) -> dict[str, Any]:
        return {
            "speedOfSoundMS": self.speed_of_sound_m_s,
            "densityKgM3": self.density_kg_m3,
            "absorptionDbPerM": self.absorption_db_per_m,
            "referenceDistanceM": self.reference_distance_m,
        }


@dataclass(frozen=True, slots=True)
class FlightState:
    """Vehicle motion at one instant: source position/velocity plus time."""

    source_position_m: Vector3
    source_velocity_m_s: Vector3 = (0.0, 0.0, 0.0)
    time_s: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_position_m", _vector(self.source_position_m, "source_position_m")
        )
        object.__setattr__(
            self, "source_velocity_m_s", _vector(self.source_velocity_m_s, "source_velocity_m_s")
        )
        _finite(self.time_s, "time_s")

    def canonical(self) -> dict[str, Any]:
        return {
            "sourcePositionM": list(self.source_position_m),
            "sourceVelocityMS": list(self.source_velocity_m_s),
            "timeS": self.time_s,
        }


def distance_m(observer: ObserverSpec, source_position_m: Vector3) -> float:
    """Euclidean source-observer distance; coincident points fail closed."""

    source = _vector(source_position_m, "source_position_m")
    squared = sum(
        (observed - emitted) ** 2
        for observed, emitted in zip(observer.position_m, source, strict=True)
    )
    result = sqrt(squared)
    if result <= 0.0:
        raise ValidityError("SOURCE_OBSERVER_COINCIDENT: observer distance must be positive")
    return result


def closing_speed_m_s(flight: FlightState, observer: ObserverSpec) -> float:
    """Radial closing speed of the source toward the observer (m/s)."""

    relative = tuple(
        observed - emitted
        for observed, emitted in zip(
            observer.position_m, flight.source_position_m, strict=True
        )
    )
    slant = sqrt(sum(component**2 for component in relative))
    if slant <= 0.0:
        raise ValidityError("SOURCE_OBSERVER_COINCIDENT: observer distance must be positive")
    return sum(
        velocity * component / slant
        for velocity, component in zip(flight.source_velocity_m_s, relative, strict=True)
    )


def doppler_factor(flight: FlightState, observer: ObserverSpec, env: EnvironmentSpec) -> float:
    """Convective Doppler factor for a moving source; supersonic approach fails."""

    closing = closing_speed_m_s(flight, observer)
    sound = env.speed_of_sound_m_s
    if closing >= sound:
        raise ValidityError("SUPERSONIC_APPROACH: linear Doppler model is out of validity")
    return sound / (sound - closing)


def spherical_transmission_loss_db(distance: float, reference_distance_m: float) -> float:
    """Spherical-spreading loss of a source level relative to a reference distance."""

    value = _finite(distance, "distance_m", positive=True)
    reference = _finite(reference_distance_m, "reference_distance_m", positive=True)
    return 20.0 * log10(value / reference)


def absorption_loss_db(distance: float, env: EnvironmentSpec) -> float:
    """Declared atmospheric-absorption loss; zero unless a coefficient is declared."""

    value = _finite(distance, "distance_m", positive=True)
    return env.absorption_db_per_m * value


def _a_curve(frequency_hz: float) -> float:
    squared = frequency_hz * frequency_hz
    numerator = (12194.0**2) * squared * squared
    denominator = (
        (squared + 20.6**2)
        * sqrt((squared + 107.7**2) * (squared + 737.9**2))
        * (squared + 12194.0**2)
    )
    return numerator / denominator


def a_weighting_db(frequency_hz: float) -> float:
    """A-weighting correction in dB for a tonal/band frequency."""

    frequency = _finite(frequency_hz, "frequency_hz", positive=True)
    return 20.0 * log10(_a_curve(frequency) / _a_curve(1000.0))


def c_weighting_db(frequency_hz: float) -> float:
    """C-weighting correction in dB for a tonal/band frequency."""

    frequency = _finite(frequency_hz, "frequency_hz", positive=True)
    squared = frequency * frequency
    numerator = (12194.0**2) * squared
    denominator = (squared + 20.6**2) * (squared + 12194.0**2)
    reference = (12194.0**2) * 1.0e6 / ((1.0e6 + 20.6**2) * (1.0e6 + 12194.0**2))
    return 20.0 * log10((numerator / denominator) / reference)


def apply_weighting(level_db: float, frequency_hz: float, weighting: Weighting) -> float:
    """Apply a declared weighting to one level; the standard travels with it."""

    level = _finite(level_db, "level_db")
    if weighting is Weighting.NONE:
        return level
    if weighting is Weighting.A:
        return level + a_weighting_db(frequency_hz)
    if weighting is Weighting.C:
        return level + c_weighting_db(frequency_hz)
    raise ContractError(f"UNKNOWN_WEIGHTING:{weighting}")
