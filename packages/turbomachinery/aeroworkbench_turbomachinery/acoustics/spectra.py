"""Aeroacoustic post-processing with an explicit, capability-gated fidelity ladder.

The cheap rung screens declared tonal/order content into observer levels; a
higher rung turns a transient surface-pressure record into a one-sided pressure
spectrum; the highest rungs are native FW-H (or equivalent) propagation and
observer SPL synthesis, which only run behind a ready capability and a trusted
native receipt. A screening result is never relabelled native.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import cos, isfinite, pi, sin, sqrt
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_optimization import FidelityImplementation

from ..canonical import content_digest
from ..fidelity.features import ArchitectureFeatures
from ..fidelity.native import NativeCapabilityGate, NativeReceipt
from .capabilities import (
    NativeAcousticRequirement,
    trusted_acoustic_receipt,
)
from .errors import AcousticCapabilityUnavailable, AcousticInputError
from .orders import OrderSpectrum
from .results import (
    DEFAULT_ACOUSTIC_SOFTWARE,
    REFERENCE_PRESSURE_PA,
    AcousticFidelity,
    AcousticSoftware,
    AcousticValidity,
    analytical_provenance,
    check_validity,
    energy_sum_db,
    finite,
    finite_series,
    native_provenance,
    spectrum_lines,
    spl_db,
)

__all__ = [
    "AcousticLevel",
    "AcousticRung",
    "AeroacousticLadder",
    "ObserverSplLine",
    "ObserverSplResult",
    "SurfacePressureSpectrum",
    "TonalLine",
    "TonalScreeningResult",
    "default_aeroacoustic_ladder",
    "observer_spl_from_spectrum",
    "propagate_fw_h",
    "screen_tonal_orders",
    "surface_pressure_spectrum_from_record",
]


class AcousticLevel(StrEnum):
    """Canonical aeroacoustic fidelity rungs, cheapest first."""

    TONAL_SCREENING = "tonal-order-screening"
    THERMOACOUSTIC_SCREENING = "thermoacoustic-screening"
    SURFACE_PRESSURE_SPECTRA = "surface-pressure-spectra"
    FW_H_PROPAGATION = "fw-h-propagation"
    OBSERVER_SPL = "observer-spl-tonal"


@dataclass(frozen=True, slots=True)
class AcousticRung:
    """One declared aeroacoustic rung with its source, validity, and native gate."""

    rung_id: str
    level: AcousticLevel
    rank: int
    cost: float
    source: ResultSource
    fidelity: FidelityLevel
    analyses: tuple[str, ...]
    validity_criteria: tuple[str, ...] = ()
    native_capabilities: tuple[str, ...] = ()
    requires_native: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not self.rung_id.strip():
            raise AcousticInputError("acoustic rung id is required")
        if self.rank < 0 or not isfinite(self.cost) or self.cost < 0.0:
            raise AcousticInputError(f"invalid acoustic rung spec:{self.rung_id}")
        if not self.analyses:
            raise AcousticInputError(f"acoustic rung needs analyses:{self.rung_id}")
        if self.requires_native and not self.native_capabilities:
            raise AcousticInputError(f"native acoustic rung needs a capability:{self.rung_id}")
        if not self.requires_native and self.native_capabilities:
            raise AcousticInputError(f"non-native acoustic rung has a capability:{self.rung_id}")
        if self.requires_native and self.source is not ResultSource.NATIVE_SOLVER:
            raise AcousticInputError(f"native acoustic rung source mismatch:{self.rung_id}")

    def implementation(self, rank: int | None = None) -> FidelityImplementation:
        return FidelityImplementation(
            self.rung_id,
            self.rank if rank is None else rank,
            self.cost,
            self.native_capabilities if self.requires_native else self.analyses,
            self.description,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "rungId": self.rung_id,
            "level": self.level.value,
            "rank": self.rank,
            "cost": self.cost,
            "source": self.source.value,
            "fidelity": self.fidelity.value,
            "analyses": list(self.analyses),
            "validityCriteria": list(self.validity_criteria),
            "nativeCapabilities": list(self.native_capabilities),
            "requiresNative": self.requires_native,
            "description": self.description,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class AeroacousticLadder:
    """Immutable ordered ladder whose ranks form a contiguous range from zero."""

    rungs: tuple[AcousticRung, ...]
    ladder_id: str = "rotating-gas-aeroacoustic-ladder"

    def __post_init__(self) -> None:
        if not self.ladder_id.strip():
            raise AcousticInputError("acoustic ladder id is required")
        if not self.rungs:
            raise AcousticInputError("acoustic ladder needs rungs")
        ordered = sorted(self.rungs, key=lambda rung: rung.rank)
        if [rung.rank for rung in ordered] != list(range(len(ordered))):
            raise AcousticInputError("acoustic ladder must form a rank ladder from zero")
        if len({rung.rung_id for rung in ordered}) != len(ordered):
            raise AcousticInputError("acoustic ladder has duplicate rungs")
        object.__setattr__(self, "rungs", tuple(ordered))

    def rung(self, rung_id: str) -> AcousticRung:
        for rung in self.rungs:
            if rung.rung_id == rung_id:
                return rung
        raise AcousticInputError(f"UNKNOWN_ACOUSTIC_RUNG:{rung_id}")

    def rung_ids(self) -> tuple[str, ...]:
        return tuple(rung.rung_id for rung in self.rungs)

    def cheapest(self) -> AcousticRung:
        return self.rungs[0]

    def next_rung(self, rung_id: str) -> AcousticRung | None:
        current = self.rung(rung_id)
        following = [rung for rung in self.rungs if rung.rank > current.rank]
        return following[0] if following else None

    def applicable(
        self,
        features: ArchitectureFeatures,
        requested: Sequence[str] = (),
    ) -> tuple[AcousticRung, ...]:
        requested_set = frozenset(requested)
        return tuple(
            rung for rung in self.rungs if _rung_applies(rung, features, requested_set)
        )

    def implementations(
        self, rungs: Sequence[AcousticRung] | None = None
    ) -> tuple[FidelityImplementation, ...]:
        selected = tuple(rungs) if rungs is not None else self.rungs
        ordered = sorted(selected, key=lambda rung: rung.rank)
        return tuple(rung.implementation(index) for index, rung in enumerate(ordered))

    def canonical(self) -> dict[str, Any]:
        return {"ladderId": self.ladder_id, "rungs": [rung.canonical() for rung in self.rungs]}

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def _rung_applies(
    rung: AcousticRung, features: ArchitectureFeatures, requested: frozenset[str]
) -> bool:
    if rung.level is AcousticLevel.TONAL_SCREENING:
        return features.has_rotating_rows or "acoustics" in requested
    if rung.level is AcousticLevel.THERMOACOUSTIC_SCREENING:
        return features.has_heat_addition
    if rung.level is AcousticLevel.SURFACE_PRESSURE_SPECTRA:
        return features.has_rotating_rows or "unsteady-cfd" in requested
    if rung.level is AcousticLevel.FW_H_PROPAGATION:
        return features.acoustics_requested or "fw-h" in requested or bool(
            requested & {"acoustics", "propagation"}
        )
    if rung.level is AcousticLevel.OBSERVER_SPL:
        return features.acoustics_requested or "observer-spl" in requested or bool(
            requested & {"acoustics", "propagation"}
        )
    return False


def default_aeroacoustic_ladder() -> AeroacousticLadder:
    """Canonical aeroacoustic ladder; applicability is applied per architecture."""

    return AeroacousticLadder(
        rungs=(
            AcousticRung(
                "tonal-order-screening",
                AcousticLevel.TONAL_SCREENING,
                0,
                0.01,
                ResultSource.ANALYTICAL,
                FidelityLevel.ANALYTICAL,
                ("tonal-order-screening",),
                ("buildable-orders", "declared-amplitudes"),
                description="tonal/order screening from actual row interaction",
            ),
            AcousticRung(
                "thermoacoustic-screening",
                AcousticLevel.THERMOACOUSTIC_SCREENING,
                1,
                0.05,
                ResultSource.ANALYTICAL,
                FidelityLevel.MRF,
                ("thermoacoustic-screening",),
                ("heat-addition", "mode-alignment"),
                description="Rayleigh-type heat-release/pressure growth screening",
            ),
            AcousticRung(
                "surface-pressure-spectra",
                AcousticLevel.SURFACE_PRESSURE_SPECTRA,
                2,
                1.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.MRF,
                ("surface-pressure-spectra",),
                ("timestep-independence", "nyquist"),
                native_capabilities=(NativeAcousticRequirement.TRANSIENT_CFD_SPECTRA.value,),
                requires_native=True,
                description="surface pressure spectra from transient CFD",
            ),
            AcousticRung(
                "fw-h-propagation",
                AcousticLevel.FW_H_PROPAGATION,
                3,
                8.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.TRANSIENT,
                ("acoustic-propagation",),
                ("solver-convergence", "receiver-convergence"),
                native_capabilities=(NativeAcousticRequirement.FW_H_PROPAGATION.value,),
                requires_native=True,
                description="FW-H or equivalent acoustic propagation seam",
            ),
            AcousticRung(
                "observer-spl-tonal",
                AcousticLevel.OBSERVER_SPL,
                4,
                12.0,
                ResultSource.NATIVE_SOLVER,
                FidelityLevel.TRANSIENT,
                ("observer-spl",),
                ("propagation-validity", "observer-sampling"),
                native_capabilities=(NativeAcousticRequirement.OBSERVER_SPL.value,),
                requires_native=True,
                description="observer SPL/tonal synthesis with provenance",
            ),
        )
    )


# -- tonal screening ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TonalLine:
    """One resolved tonal line with its pressure amplitude and level."""

    order_id: str
    family: str
    frequency_hz: float
    order: float
    pressure_pa: float
    level_db: float
    shaft: str

    def canonical(self) -> dict[str, Any]:
        return {
            "orderId": self.order_id,
            "family": self.family,
            "frequency_hz": self.frequency_hz,
            "order": self.order,
            "pressure_pa": self.pressure_pa,
            "level_db": self.level_db,
            "shaft": self.shaft,
        }


@dataclass(frozen=True, slots=True)
class TonalScreeningResult:
    """Observer tonal levels screened from declared order amplitudes."""

    architecture_hash: str
    lines: tuple[TonalLine, ...]
    dominant_frequency_hz: float
    dominant_level_db: float
    overall_level_db: float
    fidelity: AcousticFidelity
    validity: AcousticValidity
    provenance: Provenance
    software: AcousticSoftware = DEFAULT_ACOUSTIC_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "frequency_hz": "Hz",
            "order": "dimensionless",
            "pressure_pa": "Pa",
            "level_db": "dB",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "architectureHash": self.architecture_hash,
            "lines": [line.canonical() for line in self.lines],
            "dominantFrequencyHz": self.dominant_frequency_hz,
            "dominantLevelDb": self.dominant_level_db,
            "overallLevelDb": self.overall_level_db,
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def screen_tonal_orders(
    spectrum: OrderSpectrum,
    *,
    amplitude_by_order: Mapping[str, float],
    reference_pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> TonalScreeningResult:
    """Screen declared per-order pressure amplitudes into observer tonal levels.

    Orders without a declared amplitude are skipped, never fabricated. At least
    one declared amplitude is required.
    """

    speeds = spectrum.speed_map()
    reference = finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    lines: list[TonalLine] = []
    for order in spectrum.orders:
        raw = amplitude_by_order.get(order.order_id)
        if raw is None:
            continue
        pressure = finite(raw, f"amplitude_by_order[{order.order_id}]", minimum=0.0)
        frequency = order.frequency_hz(speeds)
        if frequency <= 0.0:
            continue
        lines.append(
            TonalLine(
                order_id=order.order_id,
                family=order.family.value,
                frequency_hz=frequency,
                order=order.order,
                pressure_pa=pressure,
                level_db=spl_db(pressure, reference_pressure_pa=reference),
                shaft=order.primary_shaft,
            )
        )
    if not lines:
        raise AcousticInputError("NO_TONAL_AMPLITUDES: at least one declared amplitude is required")
    dominant = max(lines, key=lambda line: line.level_db)
    ordered = tuple(sorted(lines, key=lambda line: (-line.level_db, line.order_id)))
    checks = {
        "frequencies_positive": all(line.frequency_hz > 0.0 for line in ordered),
        "amplitudes_nonnegative": all(line.pressure_pa >= 0.0 for line in ordered),
        "orders_positive": all(line.order > 0.0 for line in ordered),
    }
    inputs = {
        "architectureHash": spectrum.architecture_hash,
        "orders": [order.canonical() for order in spectrum.orders],
        "amplitudeByOrder": {key: amplitude_by_order[key] for key in sorted(amplitude_by_order)},
        "referencePressurePa": reference,
    }
    return TonalScreeningResult(
        architecture_hash=spectrum.architecture_hash,
        lines=ordered,
        dominant_frequency_hz=dominant.frequency_hz,
        dominant_level_db=dominant.level_db,
        overall_level_db=energy_sum_db([line.level_db for line in ordered]),
        fidelity=AcousticFidelity.TONAL_SCREENING,
        validity=check_validity(checks, f"screened {len(ordered)} declared tonal lines"),
        provenance=analytical_provenance(
            "acoustics.tonal-order-screening",
            inputs,
            assumptions=(
                "tonal amplitudes are declared/measured, not modelled",
                "levels are amplitudes relative to the reference pressure",
            ),
        ),
    )


# -- surface pressure spectra -------------------------------------------------


def _window_weights(window: str, count: int) -> tuple[tuple[float, ...], float]:
    if window == "rectangular":
        return tuple(1.0 for _ in range(count)), 1.0
    if window == "hann":
        weights = tuple(
            0.5 * (1.0 - cos(2.0 * pi * index / (count - 1))) for index in range(count)
        )
        return weights, 0.5
    raise AcousticInputError(f"UNKNOWN_WINDOW:{window}")


@dataclass(frozen=True, slots=True)
class SurfacePressureSpectrum:
    """A one-sided surface pressure amplitude spectrum with full provenance."""

    interface_id: str
    sample_rate_hz: float
    sample_count: int
    window: str
    lines: tuple[tuple[float, float], ...]
    fidelity: AcousticFidelity
    validity: AcousticValidity
    provenance: Provenance
    software: AcousticSoftware = DEFAULT_ACOUSTIC_SOFTWARE

    def __post_init__(self) -> None:
        if not self.interface_id.strip():
            raise AcousticInputError("surface pressure spectrum interface_id is required")
        object.__setattr__(self, "lines", spectrum_lines(self.lines, "lines"))

    @property
    def nyquist_hz(self) -> float:
        return self.sample_rate_hz / 2.0

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "pressure_pa": "Pa", "sample_rate_hz": "Hz"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interfaceId": self.interface_id,
            "sampleRateHz": self.sample_rate_hz,
            "sampleCount": self.sample_count,
            "window": self.window,
            "nyquistHz": self.nyquist_hz,
            "lines": [[frequency, amplitude] for frequency, amplitude in self.lines],
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def surface_pressure_spectrum_from_record(
    record_pa: Sequence[float],
    sample_rate_hz: float,
    *,
    interface_id: str,
    window: str = "hann",
    provenance: Provenance | None = None,
) -> SurfacePressureSpectrum:
    """One-sided amplitude spectrum of a transient surface-pressure record."""

    samples = finite_series(record_pa, "record_pa")
    count = len(samples)
    if count < 4:
        raise AcousticInputError("surface pressure record needs at least four samples")
    rate = finite(sample_rate_hz, "sample_rate_hz", positive=True)
    weights, coherent_gain = _window_weights(window, count)
    mean = sum(samples) / count
    centered = tuple(value - mean for value in samples)
    lines: list[tuple[float, float]] = []
    for bin_index in range(count // 2 + 1):
        real = 0.0
        imaginary = 0.0
        for index, value in enumerate(centered):
            angle = 2.0 * pi * bin_index * index / count
            real += value * weights[index] * cos(angle)
            imaginary -= value * weights[index] * sin(angle)
        magnitude = sqrt(real * real + imaginary * imaginary)
        scale = 2.0 if 0 < bin_index < count // 2 else 1.0
        amplitude = scale * magnitude / (count * coherent_gain)
        lines.append((bin_index * rate / count, amplitude))
    checks = {
        "sample_count_ok": count >= 4,
        "nyquist_positive": rate > 0.0,
        "amplitudes_finite": all(isfinite(amplitude) for _, amplitude in lines),
    }
    inputs = {
        "interfaceId": interface_id,
        "sampleRateHz": rate,
        "sampleCount": count,
        "window": window,
        "meanPa": mean,
    }
    return SurfacePressureSpectrum(
        interface_id=interface_id,
        sample_rate_hz=rate,
        sample_count=count,
        window=window,
        lines=tuple(lines),
        fidelity=AcousticFidelity.SURFACE_SPECTRA,
        validity=check_validity(checks, f"{count}-sample one-sided amplitude spectrum"),
        provenance=provenance
        if provenance is not None
        else analytical_provenance(
            "acoustics.surface-pressure-spectrum.dft",
            inputs,
            assumptions=(
                "one-sided amplitude spectrum of a supplied transient pressure record",
                "no propagation or directivity model is applied",
            ),
            fidelity=FidelityLevel.MRF,
        ),
    )


# -- observer SPL -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObserverSplLine:
    """One observer tonal level derived from a source pressure line."""

    label: str
    frequency_hz: float
    source_level_db: float
    observer_level_db: float
    order: float | None = None

    def canonical(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "frequency_hz": self.frequency_hz,
            "source_level_db": self.source_level_db,
            "observer_level_db": self.observer_level_db,
            "order": self.order,
        }


@dataclass(frozen=True, slots=True)
class ObserverSplResult:
    """Observer SPL/tonal output with source, fidelity, validity, and provenance."""

    observer_id: str
    lines: tuple[ObserverSplLine, ...]
    overall_level_db: float
    transmission_loss_db: float
    distance_m: float
    fidelity: AcousticFidelity
    validity: AcousticValidity
    provenance: Provenance
    software: AcousticSoftware = DEFAULT_ACOUSTIC_SOFTWARE

    def units(self) -> dict[str, str]:
        return {
            "frequency_hz": "Hz",
            "level_db": "dB",
            "transmission_loss_db": "dB",
            "distance_m": "m",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "observerId": self.observer_id,
            "lines": [line.canonical() for line in self.lines],
            "overallLevelDb": self.overall_level_db,
            "transmissionLossDb": self.transmission_loss_db,
            "distanceM": self.distance_m,
            "source": self.provenance.source.value,
            "fidelity": self.fidelity.value,
            "solverName": self.provenance.solver_name,
            "solverVersion": self.provenance.solver_version,
            "runId": self.provenance.run_id,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def _observer_levels(
    lines: Sequence[tuple[float, float]],
    *,
    transmission_loss_db: float,
    reference_pressure_pa: float,
) -> tuple[tuple[ObserverSplLine, ...], float]:
    resolved: list[ObserverSplLine] = []
    for index, (frequency, pressure) in enumerate(lines):
        source_level = spl_db(pressure, reference_pressure_pa=reference_pressure_pa)
        resolved.append(
            ObserverSplLine(
                label=f"line-{index}",
                frequency_hz=frequency,
                source_level_db=source_level,
                observer_level_db=source_level - transmission_loss_db,
            )
        )
    ordered = tuple(sorted(resolved, key=lambda line: (-line.observer_level_db, line.frequency_hz)))
    return ordered, energy_sum_db([line.observer_level_db for line in ordered])


def observer_spl_from_spectrum(
    spectrum: SurfacePressureSpectrum,
    *,
    observer_id: str = "observer",
    transmission_loss_db: float = 0.0,
    distance_m: float = 1.0,
    reference_pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> ObserverSplResult:
    """Observer SPL from a surface spectrum with a declared transmission loss."""

    if not observer_id.strip():
        raise AcousticInputError("observer_id is required")
    loss = finite(transmission_loss_db, "transmission_loss_db")
    distance = finite(distance_m, "distance_m", positive=True)
    reference = finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    lines, overall = _observer_levels(
        spectrum.lines, transmission_loss_db=loss, reference_pressure_pa=reference
    )
    inputs = {
        "spectrum": spectrum.canonical_payload(),
        "observerId": observer_id,
        "transmissionLossDb": loss,
        "distanceM": distance,
        "referencePressurePa": reference,
    }
    return ObserverSplResult(
        observer_id=observer_id,
        lines=lines,
        overall_level_db=overall,
        transmission_loss_db=loss,
        distance_m=distance,
        fidelity=AcousticFidelity.OBSERVER_SPL,
        validity=check_validity(
            {"spectrum_valid": spectrum.validity.passed, "loss_nonnegative": loss >= 0.0},
            f"observer levels for {len(lines)} spectral lines",
        ),
        provenance=analytical_provenance(
            "acoustics.observer-spl",
            inputs,
            assumptions=("declared transmission loss applied to source levels",),
        ),
    )


def propagate_fw_h(
    spectrum: SurfacePressureSpectrum,
    *,
    capability_gate: NativeCapabilityGate | None,
    receipt: NativeReceipt | None,
    observer_id: str = "observer",
    transmission_loss_db: float = 0.0,
    distance_m: float = 1.0,
    reference_pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> ObserverSplResult:
    """Native FW-H (or equivalent) propagation seam; fails closed when unavailable."""

    capability = NativeAcousticRequirement.FW_H_PROPAGATION.value
    gate = capability_gate if capability_gate is not None else NativeCapabilityGate()
    if not gate.permits(capability):
        raise AcousticCapabilityUnavailable(
            capability, "capability is not probed ready; native propagation fails closed"
        )
    trusted = trusted_acoustic_receipt(receipt)
    if trusted.capability not in (capability, NativeAcousticRequirement.OBSERVER_SPL.value):
        raise AcousticCapabilityUnavailable(
            trusted.capability, f"receipt does not cover {capability}"
        )
    if not gate.receipt_valid(trusted):
        raise AcousticCapabilityUnavailable(capability, "native receipt is not trusted")
    if not observer_id.strip():
        raise AcousticInputError("observer_id is required")
    loss = finite(transmission_loss_db, "transmission_loss_db")
    distance = finite(distance_m, "distance_m", positive=True)
    reference = finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    lines, overall = _observer_levels(
        spectrum.lines, transmission_loss_db=loss, reference_pressure_pa=reference
    )
    inputs = {
        "spectrum": spectrum.canonical_payload(),
        "observerId": observer_id,
        "transmissionLossDb": loss,
        "distanceM": distance,
        "referencePressurePa": reference,
    }
    return ObserverSplResult(
        observer_id=observer_id,
        lines=lines,
        overall_level_db=overall,
        transmission_loss_db=loss,
        distance_m=distance,
        fidelity=AcousticFidelity.FW_H_PROPAGATION,
        validity=check_validity(
            {
                "capability_ready": bool(gate.permits(capability)),
                "receipt_trusted": bool(trusted.valid),
                "spectrum_valid": spectrum.validity.passed,
            },
            f"native propagation for {len(lines)} lines",
        ),
        provenance=native_provenance(
            "acoustics.fw-h-propagation",
            inputs,
            solver_name=trusted.solver_name,
            solver_version=trusted.solver_version,
            run_id=trusted.run_id,
            assumptions=("native acoustic propagation result carried by a trusted receipt",),
        ),
    )
