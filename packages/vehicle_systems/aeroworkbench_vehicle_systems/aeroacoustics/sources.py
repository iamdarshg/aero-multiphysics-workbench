"""Vehicle noise source seams: rotor/propulsor tones, broadband, airframe, interaction.

Frequencies and orders are derived from declared rotor geometry and operating
state; amplitudes are always declared/measured inputs, never modelled here. A
screening result preserves its declared source spectrum and reports an
analytical source fidelity. Level helpers reuse the shared TURBO 09 acoustic
pieces instead of duplicating them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, log10
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_turbomachinery.acoustics import (  # type: ignore[import-not-found, unused-ignore]
    REFERENCE_PRESSURE_PA,
    energy_sum_db,
    spl_db,
)

from .contracts import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    NoiseFidelity,
    NoiseValidity,
    analytical_provenance,
)
from .errors import ContractError

__all__ = [
    "AirframeContributor",
    "AirframeReference",
    "AirframeScreening",
    "BroadbandLine",
    "BroadbandScreening",
    "InteractionLine",
    "InteractionScreening",
    "RotorScreening",
    "RotorSpec",
    "RotorTone",
    "RotorToneLine",
    "blade_passing_frequency_hz",
    "rotor_tonal_orders",
    "screen_airframe_source",
    "screen_broadband",
    "screen_rotor_airframe_interaction",
    "screen_rotor_tones",
    "shaft_frequency_hz",
]


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
class RotorSpec:
    """Typed rotor/propulsor load-data seam: geometry plus operating state."""

    rotor_id: str
    blade_count: int
    rpm: float
    radius_m: float | None = None
    thrust_n: float | None = None

    def __post_init__(self) -> None:
        if not self.rotor_id.strip():
            raise ContractError("rotor_id is required")
        if (
            isinstance(self.blade_count, bool)
            or not isinstance(self.blade_count, int)
            or self.blade_count < 1
        ):
            raise ContractError("blade_count must be a positive integer")
        _finite(self.rpm, "rpm", positive=True)
        if self.radius_m is not None:
            _finite(self.radius_m, "radius_m", positive=True)
        if self.thrust_n is not None:
            _finite(self.thrust_n, "thrust_n")

    def canonical(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "bladeCount": self.blade_count,
            "rpm": self.rpm,
            "radiusM": self.radius_m,
            "thrustN": self.thrust_n,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def shaft_frequency_hz(spec: RotorSpec) -> float:
    """Shaft rotational frequency derived from the declared rpm."""

    return spec.rpm / 60.0


def blade_passing_frequency_hz(spec: RotorSpec) -> float:
    """Blade-passing frequency derived from declared blade count and rpm."""

    return spec.blade_count * spec.rpm / 60.0


@dataclass(frozen=True, slots=True)
class RotorTone:
    """One derived rotor tonal order: harmonic, frequency, and order."""

    harmonic: int
    frequency_hz: float
    order: float

    def canonical(self) -> dict[str, Any]:
        return {
            "harmonic": self.harmonic,
            "frequencyHz": self.frequency_hz,
            "order": self.order,
        }


def rotor_tonal_orders(spec: RotorSpec, *, harmonics: int = 3) -> tuple[RotorTone, ...]:
    """Derive blade-passing tonal orders from the declared rotor, nothing else."""

    if isinstance(harmonics, bool) or not isinstance(harmonics, int) or harmonics < 1:
        raise ContractError("harmonics must be a positive integer")
    base = blade_passing_frequency_hz(spec)
    return tuple(
        RotorTone(
            harmonic=index,
            frequency_hz=index * base,
            order=float(index * spec.blade_count),
        )
        for index in range(1, harmonics + 1)
    )


@dataclass(frozen=True, slots=True)
class RotorToneLine:
    """One resolved rotor tonal line with its declared amplitude."""

    order_id: str
    harmonic: int
    order: float
    frequency_hz: float
    pressure_pa: float
    level_db: float

    def canonical(self) -> dict[str, Any]:
        return {
            "orderId": self.order_id,
            "harmonic": self.harmonic,
            "order": self.order,
            "frequencyHz": self.frequency_hz,
            "pressurePa": self.pressure_pa,
            "levelDb": self.level_db,
        }


@dataclass(frozen=True, slots=True)
class RotorScreening:
    """Rotor tonal screening from declared per-harmonic amplitudes."""

    rotor_id: str
    rotor_hash: str
    shaft_hz: float
    blade_passing_hz: float
    lines: tuple[RotorToneLine, ...]
    dominant_frequency_hz: float
    dominant_level_db: float
    overall_level_db: float
    fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "order": "dimensionless", "pressure_pa": "Pa",
                "level_db": "dB"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "rotorHash": self.rotor_hash,
            "shaftHz": self.shaft_hz,
            "bladePassingHz": self.blade_passing_hz,
            "lines": [line.canonical() for line in self.lines],
            "dominantFrequencyHz": self.dominant_frequency_hz,
            "dominantLevelDb": self.dominant_level_db,
            "overallLevelDb": self.overall_level_db,
            "source": self.source,
            "fidelity": self.fidelity.value,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def screen_rotor_tones(
    spec: RotorSpec,
    amplitudes_pa_by_harmonic: Mapping[int, float],
    *,
    harmonics: int = 3,
    reference_pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> RotorScreening:
    """Screen declared per-harmonic pressures into tonal levels.

    Harmonics without a declared amplitude are skipped, never fabricated. At
    least one declared amplitude inside the harmonic range is required.
    """

    tones = rotor_tonal_orders(spec, harmonics=harmonics)
    reference = _finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    lines: list[RotorToneLine] = []
    for tone in tones:
        raw = amplitudes_pa_by_harmonic.get(tone.harmonic)
        if raw is None:
            continue
        pressure = _finite(raw, f"amplitude_h{tone.harmonic}", positive=False)
        if pressure < 0.0:
            raise ContractError(f"amplitude_h{tone.harmonic} must be >= 0")
        lines.append(
            RotorToneLine(
                order_id=f"bpf:{spec.rotor_id}:h{tone.harmonic}",
                harmonic=tone.harmonic,
                order=tone.order,
                frequency_hz=tone.frequency_hz,
                pressure_pa=pressure,
                level_db=float(spl_db(pressure, reference_pressure_pa=reference)),
            )
        )
    if not lines:
        raise ContractError("NO_TONAL_AMPLITUDES: at least one declared amplitude is required")
    ordered = tuple(sorted(lines, key=lambda line: (-line.level_db, line.order_id)))
    dominant = ordered[0]
    checks = {
        "frequencies_positive": all(line.frequency_hz > 0.0 for line in ordered),
        "amplitudes_nonnegative": all(line.pressure_pa >= 0.0 for line in ordered),
        "orders_positive": all(line.order > 0.0 for line in ordered),
    }
    inputs = {
        "rotor": spec.canonical(),
        "harmonics": harmonics,
        "amplitudesPaByHarmonic": {
            str(key): amplitudes_pa_by_harmonic[key]
            for key in sorted(amplitudes_pa_by_harmonic)
        },
        "referencePressurePa": reference,
    }
    validity = NoiseValidity(
        all(checks.values()), checks, f"screened {len(ordered)} declared rotor tonal lines"
    )
    return RotorScreening(
        rotor_id=spec.rotor_id,
        rotor_hash=spec.digest,
        shaft_hz=shaft_frequency_hz(spec),
        blade_passing_hz=blade_passing_frequency_hz(spec),
        lines=ordered,
        dominant_frequency_hz=dominant.frequency_hz,
        dominant_level_db=dominant.level_db,
        overall_level_db=float(energy_sum_db([line.level_db for line in ordered])),
        fidelity=NoiseFidelity.TONAL_SCREENING,
        validity=validity,
        provenance=analytical_provenance(
            "aeroacoustics.rotor-tonal-screening",
            inputs,
            assumptions=(
                "tonal amplitudes are declared/measured, not modelled",
                "levels are amplitudes relative to the reference pressure",
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class BroadbandLine:
    """One declared broadband spectral line."""

    frequency_hz: float
    pressure_pa: float
    level_db: float

    def canonical(self) -> dict[str, Any]:
        return {
            "frequencyHz": self.frequency_hz,
            "pressurePa": self.pressure_pa,
            "levelDb": self.level_db,
        }


@dataclass(frozen=True, slots=True)
class BroadbandScreening:
    """Broadband screening from a declared source spectrum, preserved verbatim."""

    contributor: str
    lines: tuple[BroadbandLine, ...]
    overall_level_db: float
    fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "pressure_pa": "Pa", "level_db": "dB"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "contributor": self.contributor,
            "lines": [line.canonical() for line in self.lines],
            "overallLevelDb": self.overall_level_db,
            "source": self.source,
            "fidelity": self.fidelity.value,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def screen_broadband(
    contributor: str,
    declared: Sequence[tuple[float, float]],
    *,
    reference_pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> BroadbandScreening:
    """Screen a declared (frequency_hz, pressure_pa) spectrum into levels."""

    if not contributor.strip():
        raise ContractError("broadband contributor is required")
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Sequence):
        raise ContractError("declared spectrum must be a sequence")
    if not declared:
        raise ContractError("NO_BROADBAND_SPECTRUM: a declared spectrum is required")
    reference = _finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    lines: list[BroadbandLine] = []
    for index, entry in enumerate(declared):
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise ContractError(f"declared[{index}] must be a (frequency, pressure) pair")
        frequency = _finite(entry[0], f"declared[{index}].frequency_hz")
        pressure = _finite(entry[1], f"declared[{index}].pressure_pa")
        if frequency <= 0.0 or pressure < 0.0:
            raise ContractError(f"declared[{index}] must have positive frequency")
        lines.append(
            BroadbandLine(
                frequency_hz=frequency,
                pressure_pa=pressure,
                level_db=float(spl_db(pressure, reference_pressure_pa=reference)),
            )
        )
    ordered = tuple(sorted(lines, key=lambda line: (line.frequency_hz, -line.level_db)))
    checks = {"lines_resolved": len(ordered) == len(declared)}
    inputs = {
        "contributor": contributor,
        "declared": [[float(entry[0]), float(entry[1])] for entry in declared],
        "referencePressurePa": reference,
    }
    return BroadbandScreening(
        contributor=contributor,
        lines=ordered,
        overall_level_db=float(energy_sum_db([line.level_db for line in ordered])),
        fidelity=NoiseFidelity.BROADBAND_SCREENING,
        validity=NoiseValidity(True, checks, f"screened {len(ordered)} declared broadband lines"),
        provenance=analytical_provenance(
            "aeroacoustics.broadband-screening",
            inputs,
            assumptions=("broadband spectrum is declared/measured, not modelled",),
        ),
    )


class AirframeContributor(StrEnum):
    """Airframe noise contributors with a declared scaling seam."""

    TRAILING_EDGE = "trailing-edge"
    HIGH_LIFT = "high-lift"
    LANDING_GEAR = "landing-gear"


@dataclass(frozen=True, slots=True)
class AirframeReference:
    """Declared airframe-noise reference: level at a reference condition."""

    contributor: AirframeContributor
    velocity_m_s: float
    reference_velocity_m_s: float
    reference_level_db: float
    exponent: float
    frequency_hz: float
    mach_number: float | None = None

    def __post_init__(self) -> None:
        _finite(self.velocity_m_s, "velocity_m_s", positive=True)
        _finite(self.reference_velocity_m_s, "reference_velocity_m_s", positive=True)
        _finite(self.reference_level_db, "reference_level_db")
        exponent = _finite(self.exponent, "exponent")
        if exponent < 0.0 or exponent > 8.0:
            raise ContractError("exponent must lie in [0, 8]")
        _finite(self.frequency_hz, "frequency_hz", positive=True)
        if self.mach_number is not None:
            mach = _finite(self.mach_number, "mach_number")
            if mach < 0.0:
                raise ContractError("mach_number must be >= 0")

    def canonical(self) -> dict[str, Any]:
        return {
            "contributor": self.contributor.value,
            "velocityMS": self.velocity_m_s,
            "referenceVelocityMS": self.reference_velocity_m_s,
            "referenceLevelDb": self.reference_level_db,
            "exponent": self.exponent,
            "frequencyHz": self.frequency_hz,
            "machNumber": self.mach_number,
        }


@dataclass(frozen=True, slots=True)
class AirframeScreening:
    """Airframe contributor level scaled from a declared reference condition."""

    contributor: AirframeContributor
    frequency_hz: float
    scaled_level_db: float
    fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "level_db": "dB", "velocity_m_s": "m/s"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "contributor": self.contributor.value,
            "frequencyHz": self.frequency_hz,
            "scaledLevelDb": self.scaled_level_db,
            "source": self.source,
            "fidelity": self.fidelity.value,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def screen_airframe_source(reference: AirframeReference) -> AirframeScreening:
    """Scale a declared airframe reference level by a declared velocity power law.

    Subsonic attached flow only: a declared Mach number above 0.6 fails closed.
    """

    if reference.mach_number is not None and reference.mach_number > 0.6:
        raise ContractError("AIRFRAME_OUT_OF_VALIDITY: scaling needs subsonic attached flow")
    scaled = reference.reference_level_db + 10.0 * reference.exponent * log10(
        reference.velocity_m_s / reference.reference_velocity_m_s
    )
    checks = {
        "velocities_positive": reference.velocity_m_s > 0.0
        and reference.reference_velocity_m_s > 0.0,
        "subsonic_attached": reference.mach_number is None or reference.mach_number <= 0.6,
    }
    inputs = {"reference": reference.canonical(), "scaledLevelDb": scaled}
    return AirframeScreening(
        contributor=reference.contributor,
        frequency_hz=reference.frequency_hz,
        scaled_level_db=scaled,
        fidelity=NoiseFidelity.AIRFRAME_SCREENING,
        validity=NoiseValidity(
            all(checks.values()), checks, f"scaled {reference.contributor.value} level"
        ),
        provenance=analytical_provenance(
            "aeroacoustics.airframe-scaling",
            inputs,
            assumptions=(
                "velocity power-law scaling of a declared reference level",
                "not a prediction from first principles",
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class InteractionLine:
    """One declared rotor-airframe interaction tone with its rotor-harmonic gap."""

    frequency_hz: float
    pressure_pa: float
    level_db: float
    nearest_rotor_gap_hz: float

    def canonical(self) -> dict[str, Any]:
        return {
            "frequencyHz": self.frequency_hz,
            "pressurePa": self.pressure_pa,
            "levelDb": self.level_db,
            "nearestRotorGapHz": self.nearest_rotor_gap_hz,
        }


@dataclass(frozen=True, slots=True)
class InteractionScreening:
    """Rotor-airframe interaction screening from declared interaction tones."""

    rotor_id: str
    rotor_hash: str
    lines: tuple[InteractionLine, ...]
    overall_level_db: float
    fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "pressure_pa": "Pa", "level_db": "dB"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "rotorHash": self.rotor_hash,
            "lines": [line.canonical() for line in self.lines],
            "overallLevelDb": self.overall_level_db,
            "source": self.source,
            "fidelity": self.fidelity.value,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def screen_rotor_airframe_interaction(
    spec: RotorSpec,
    declared_hz_to_pa: Mapping[float, float],
    *,
    harmonics: int = 3,
    reference_pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> InteractionScreening:
    """Screen declared interaction tones against the derived rotor harmonics."""

    if not declared_hz_to_pa:
        raise ContractError("NO_INTERACTION_TONES: declared interaction tones are required")
    reference = _finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    rotor_frequencies = [
        tone.frequency_hz for tone in rotor_tonal_orders(spec, harmonics=harmonics)
    ]
    lines: list[InteractionLine] = []
    for raw_frequency, raw_pressure in declared_hz_to_pa.items():
        frequency = _finite(raw_frequency, "interaction frequency_hz", positive=True)
        pressure = _finite(raw_pressure, "interaction pressure_pa")
        if pressure < 0.0:
            raise ContractError("interaction pressure_pa must be >= 0")
        gap = min(abs(frequency - rotor) for rotor in rotor_frequencies)
        lines.append(
            InteractionLine(
                frequency_hz=frequency,
                pressure_pa=pressure,
                level_db=float(spl_db(pressure, reference_pressure_pa=reference)),
                nearest_rotor_gap_hz=gap,
            )
        )
    ordered = tuple(sorted(lines, key=lambda line: (-line.level_db, line.frequency_hz)))
    checks = {
        "frequencies_positive": all(line.frequency_hz > 0.0 for line in ordered),
        "rotor_harmonics_derived": len(rotor_frequencies) == harmonics,
    }
    inputs = {
        "rotor": spec.canonical(),
        "harmonics": harmonics,
        "declaredHzToPa": {str(key): declared_hz_to_pa[key] for key in sorted(declared_hz_to_pa)},
        "referencePressurePa": reference,
    }
    return InteractionScreening(
        rotor_id=spec.rotor_id,
        rotor_hash=spec.digest,
        lines=ordered,
        overall_level_db=float(energy_sum_db([line.level_db for line in ordered])),
        fidelity=NoiseFidelity.INTERACTION_SCREENING,
        validity=NoiseValidity(
            all(checks.values()), checks, f"screened {len(ordered)} declared interaction tones"
        ),
        provenance=analytical_provenance(
            "aeroacoustics.rotor-airframe-interaction",
            inputs,
            assumptions=("interaction tones are declared/measured, not modelled",),
        ),
    )
