"""Observer propagation: analytical Doppler/spreading plus the native FW-H seam.

The analytical path shifts declared source lines by the convective Doppler
factor and applies spherical spreading plus a declared absorption; source
fidelity and propagation fidelity are reported separately on every result.
Transient surface/volume records are ingested through the shared TURBO 09
spectral piece, never re-implemented. Native FW-H propagation lives in
:mod:`aeroworkbench_vehicle_systems.aeroacoustics.native` and fails closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_turbomachinery.acoustics import (  # type: ignore[import-not-found, unused-ignore]
    SurfacePressureSpectrum,
    energy_sum_db,
    spl_db,
    surface_pressure_spectrum_from_record,
)

from .contracts import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    NoiseFidelity,
    NoiseValidity,
    analytical_provenance,
)
from .errors import ContractError
from .observers import (
    EnvironmentSpec,
    FlightState,
    ObserverSpec,
    absorption_loss_db,
    distance_m,
    doppler_factor,
    spherical_transmission_loss_db,
)
from .sources import (
    AirframeScreening,
    BroadbandScreening,
    InteractionScreening,
    RotorScreening,
)

__all__ = [
    "ObserverNoiseLine",
    "ObserverNoiseResult",
    "PropagatableLine",
    "ingest_surface_record",
    "lines_from_airframe",
    "lines_from_broadband",
    "lines_from_interaction",
    "lines_from_rotor",
    "propagate_spectrum_to_observer",
    "propagate_to_observer",
]


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a number")
    number = float(value)
    if not isfinite(number):
        raise ContractError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class PropagatableLine:
    """One typed source line ready for observer propagation."""

    label: str
    frequency_hz: float
    source_level_db: float
    contributor: str

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.contributor.strip():
            raise ContractError("propagatable line needs a label and a contributor")

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "frequencyHz": self.frequency_hz,
            "sourceLevelDb": self.source_level_db,
            "contributor": self.contributor,
        }


def lines_from_rotor(screening: RotorScreening) -> tuple[PropagatableLine, ...]:
    """Typed seam: rotor tonal screening into propagatable observer lines."""

    return tuple(
        PropagatableLine(
            label=line.order_id,
            frequency_hz=line.frequency_hz,
            source_level_db=line.level_db,
            contributor=f"rotor-tonal:{screening.rotor_id}",
        )
        for line in screening.lines
    )


def lines_from_broadband(screening: BroadbandScreening) -> tuple[PropagatableLine, ...]:
    """Typed seam: declared broadband screening into propagatable lines."""

    return tuple(
        PropagatableLine(
            label=f"broadband:{screening.contributor}:{index}",
            frequency_hz=line.frequency_hz,
            source_level_db=line.level_db,
            contributor=f"broadband:{screening.contributor}",
        )
        for index, line in enumerate(screening.lines)
    )


def lines_from_airframe(screening: AirframeScreening) -> tuple[PropagatableLine, ...]:
    """Typed seam: airframe contributor level into one propagatable line."""

    return (
        PropagatableLine(
            label=f"airframe:{screening.contributor.value}",
            frequency_hz=screening.frequency_hz,
            source_level_db=screening.scaled_level_db,
            contributor=f"airframe:{screening.contributor.value}",
        ),
    )


def lines_from_interaction(screening: InteractionScreening) -> tuple[PropagatableLine, ...]:
    """Typed seam: interaction tones into propagatable lines."""

    return tuple(
        PropagatableLine(
            label=f"interaction:{screening.rotor_id}:{index}",
            frequency_hz=line.frequency_hz,
            source_level_db=line.level_db,
            contributor=f"interaction:{screening.rotor_id}",
        )
        for index, line in enumerate(screening.lines)
    )


@dataclass(frozen=True, slots=True)
class ObserverNoiseLine:
    """One propagated observer line with source and observed frequency."""

    label: str
    contributor: str
    source_frequency_hz: float
    observed_frequency_hz: float
    source_level_db: float
    observer_level_db: float

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "contributor": self.contributor,
            "sourceFrequencyHz": self.source_frequency_hz,
            "observedFrequencyHz": self.observed_frequency_hz,
            "sourceLevelDb": self.source_level_db,
            "observerLevelDb": self.observer_level_db,
        }


@dataclass(frozen=True, slots=True)
class ObserverNoiseResult:
    """Observer noise with source and propagation fidelities reported separately."""

    observer_id: str
    lines: tuple[ObserverNoiseLine, ...]
    overall_level_db: float
    distance_m: float
    doppler_factor: float
    transmission_loss_db: float
    absorption_loss_db: float
    source_fidelity: NoiseFidelity
    propagation_fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "level_db": "dB", "distance_m": "m",
                "loss_db": "dB", "doppler": "dimensionless"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "observerId": self.observer_id,
            "lines": [line.canonical() for line in self.lines],
            "overallLevelDb": self.overall_level_db,
            "distanceM": self.distance_m,
            "dopplerFactor": self.doppler_factor,
            "transmissionLossDb": self.transmission_loss_db,
            "absorptionLossDb": self.absorption_loss_db,
            "sourceFidelity": self.source_fidelity.value,
            "propagationFidelity": self.propagation_fidelity.value,
            "source": self.source,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def propagate_to_observer(
    lines: Sequence[PropagatableLine],
    observer: ObserverSpec,
    environment: EnvironmentSpec,
    flight: FlightState,
    *,
    source_fidelity: NoiseFidelity,
) -> ObserverNoiseResult:
    """Propagate declared source lines to one observer with motion handling."""

    if not lines:
        raise ContractError("NO_SOURCE_LINES: at least one declared source line is required")
    slant = distance_m(observer, flight.source_position_m)
    doppler = doppler_factor(flight, observer, environment)
    spreading = spherical_transmission_loss_db(slant, environment.reference_distance_m)
    absorption = absorption_loss_db(slant, environment)
    resolved: list[ObserverNoiseLine] = []
    for line in lines:
        frequency = _finite(line.frequency_hz, f"line[{line.label}].frequency_hz")
        level = _finite(line.source_level_db, f"line[{line.label}].source_level_db")
        if frequency <= 0.0:
            raise ContractError(f"line[{line.label}] frequency must be positive")
        resolved.append(
            ObserverNoiseLine(
                label=line.label,
                contributor=line.contributor,
                source_frequency_hz=frequency,
                observed_frequency_hz=frequency * doppler,
                source_level_db=level,
                observer_level_db=level - spreading - absorption,
            )
        )
    ordered = tuple(sorted(resolved, key=lambda entry: (-entry.observer_level_db, entry.label)))
    checks = {
        "distance_positive": slant > 0.0,
        "doppler_finite": isfinite(doppler) and doppler > 0.0,
        "observed_frequencies_positive": all(
            entry.observed_frequency_hz > 0.0 for entry in ordered
        ),
    }
    inputs = {
        "lines": [line.canonical() for line in lines],
        "observer": observer.canonical(),
        "environment": environment.canonical(),
        "flight": flight.canonical(),
        "sourceFidelity": source_fidelity.value,
        "distanceM": slant,
        "dopplerFactor": doppler,
        "transmissionLossDb": spreading,
        "absorptionLossDb": absorption,
    }
    return ObserverNoiseResult(
        observer_id=observer.observer_id,
        lines=ordered,
        overall_level_db=float(energy_sum_db([entry.observer_level_db for entry in ordered])),
        distance_m=slant,
        doppler_factor=doppler,
        transmission_loss_db=spreading,
        absorption_loss_db=absorption,
        source_fidelity=source_fidelity,
        propagation_fidelity=NoiseFidelity.OBSERVER_ANALYTICAL,
        validity=NoiseValidity(
            all(checks.values()), checks,
            f"propagated {len(ordered)} lines to {observer.observer_id}",
        ),
        provenance=analytical_provenance(
            "aeroacoustics.observer-propagation",
            inputs,
            assumptions=(
                "spherical spreading plus declared absorption only",
                "Doppler shifts frequency; amplitude directivity is not modelled",
            ),
        ),
    )


def ingest_surface_record(
    record_pa: Sequence[float],
    sample_rate_hz: float,
    *,
    interface_id: str,
    window: str = "hann",
) -> SurfacePressureSpectrum:
    """Ingest a transient surface-pressure record via the shared spectral piece.

    Higher-fidelity propagation needs real transient data; without it callers
    must use the analytical screening path instead of inventing spectra.
    """

    if not interface_id.strip():
        raise ContractError("interface_id is required")
    try:
        return surface_pressure_spectrum_from_record(
            record_pa, sample_rate_hz, interface_id=interface_id, window=window
        )
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(f"transient record rejected: {exc}") from exc


def propagate_spectrum_to_observer(
    spectrum: SurfacePressureSpectrum,
    observer: ObserverSpec,
    environment: EnvironmentSpec,
    flight: FlightState,
    *,
    reference_pressure_pa: float | None = None,
) -> ObserverNoiseResult:
    """Propagate an ingested transient spectrum to one observer analytically."""

    lines: list[PropagatableLine] = []
    for index, (frequency, pressure) in enumerate(spectrum.lines):
        if frequency <= 0.0 or pressure <= 0.0:
            continue
        if reference_pressure_pa is None:
            level = float(spl_db(pressure))
        else:
            reference = _finite(reference_pressure_pa, "reference_pressure_pa")
            if reference <= 0.0:
                raise ContractError("reference_pressure_pa must be positive")
            level = float(spl_db(pressure, reference_pressure_pa=reference))
        lines.append(
            PropagatableLine(
                label=f"spectrum:{spectrum.interface_id}:{index}",
                frequency_hz=frequency,
                source_level_db=level,
                contributor=f"surface-spectrum:{spectrum.interface_id}",
            )
        )
    if not lines:
        raise ContractError("NO_SPECTRAL_CONTENT: ingested spectrum carries no energy")
    return propagate_to_observer(
        lines,
        observer,
        environment,
        flight,
        source_fidelity=NoiseFidelity.BROADBAND_SCREENING,
    )


def observer_inputs_hash(inputs: Mapping[str, Any]) -> str:
    """Deterministic input hash for an observer-side payload."""

    return content_digest(dict(inputs))
