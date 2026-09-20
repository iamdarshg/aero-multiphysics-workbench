"""Resonance inside the physics loop, generalized to arbitrary participants.

Forcing spectra are accepted from arbitrary participants (any unsteady
source labels them; nothing hard-codes a particular machine's forcing).
Modal and rotordynamic spectra are accepted from arbitrary structural or
dynamic participants. When proximity crosses policy thresholds, the trigger
names the higher-fidelity implementations to activate (harmonic response,
transient structural/CFD, AMI, FSI, detailed EM, or any participant-declared
names) filtered by what is actually available, and exposes the required
capability for the fidelity planner.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from json import dumps
from math import fmod, isfinite, pi
from typing import Literal


@dataclass(frozen=True, slots=True)
class HarmonicBasis:
    """Identity and normalization metadata for a complex harmonic line.

    ``base_orders`` and ``base_frequencies_hz`` describe a line as a signed
    integer/real combination of asynchronous bases.  The original
    ``base_id``/``order`` form remains valid for one-base callers.
    """

    shaft_id: str
    frame: str
    frequency_hz: float
    order: float
    convention: Literal["exp(+iwt)", "exp(-iwt)"] = "exp(+iwt)"
    amplitude_convention: Literal["peak", "rms", "peak-to-peak"] = "peak"
    phase_reference: Literal["cosine", "sine"] = "cosine"
    normalization: Literal["one-sided", "two-sided"] = "two-sided"
    spectral_kind: Literal["line", "PSD", "CSD"] = "line"
    base_id: str = ""
    base_orders: tuple[tuple[str, float], ...] | Mapping[str, float] = ()
    base_frequencies_hz: tuple[tuple[str, float], ...] | Mapping[str, float] = ()
    phase_references_rad: tuple[tuple[str, float], ...] | Mapping[str, float] = ()
    nodal_diameter: int | None = None

    def __post_init__(self) -> None:
        if not self.shaft_id.strip() or not self.frame.strip():
            raise ValueError("HARMONIC_BASIS_INVALID")
        supplied_orders = _canonical_pairs(self.base_orders, signed=True)
        if not supplied_orders:
            if not self.base_id.strip():
                raise ValueError("HARMONIC_BASIS_INVALID")
            if not isfinite(self.order):
                raise ValueError("HARMONIC_BASIS_INVALID")
            supplied_orders = ((self.base_id.strip(), float(self.order)),)
        frequencies = _canonical_pairs(self.base_frequencies_hz, signed=False)
        if frequencies and {name for name, _ in frequencies} != {
            name for name, _ in supplied_orders
        }:
            raise ValueError("HARMONIC_BASES_MISMATCH")
        phases = _canonical_phases(self.phase_references_rad, supplied_orders)
        if frequencies:
            calculated_frequency = sum(
                coefficient * dict(frequencies)[name]
                for name, coefficient in supplied_orders
            )
        else:
            calculated_frequency = self.frequency_hz
        if not isfinite(calculated_frequency) or calculated_frequency < 0:
            raise ValueError("HARMONIC_BASIS_INVALID")
        if self.nodal_diameter is not None and (
            not isinstance(self.nodal_diameter, int) or self.nodal_diameter < 0
        ):
            raise ValueError("HARMONIC_NODAL_DIAMETER_INVALID")
        object.__setattr__(self, "base_id", supplied_orders[0][0])
        object.__setattr__(self, "base_orders", supplied_orders)
        object.__setattr__(self, "base_frequencies_hz", frequencies)
        object.__setattr__(self, "phase_references_rad", phases)
        object.__setattr__(self, "frequency_hz", float(calculated_frequency))
        object.__setattr__(self, "order", float(sum(value for _, value in supplied_orders)))

    @property
    def order_identity(self) -> tuple[str, float] | tuple[tuple[str, float], ...]:
        """Canonical order identity, retaining the legacy one-base shape."""
        if len(self.base_orders) == 1 and not self.base_frequencies_hz:
            return self.base_orders[0]
        return self.base_orders

    @property
    def phase_identity(self) -> tuple[tuple[str, float], ...]:
        return self.phase_references_rad

    @property
    def base_ids(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.base_orders)

    @property
    def coefficients(self) -> tuple[float, ...]:
        return tuple(value for _, value in self.base_orders)

    @property
    def phase_references(self) -> tuple[tuple[str, float], ...]:
        return self.phase_references_rad

    @property
    def calculated_frequency_hz(self) -> float:
        return self.frequency_hz

    def transform_phase_identity(self, *, angle_rad: float = 0.0, delay_s: float = 0.0) -> float:
        """Return the deterministic phase applied by a frame/time transfer."""
        if not isfinite(angle_rad) or not isfinite(delay_s):
            raise ValueError("HARMONIC_TRANSFORM_PHASE_INVALID")
        return sum(phase for _, phase in self.phase_references_rad) + self.order * angle_rad - (
            2.0 * pi * self.frequency_hz * delay_s
        )

    transfer_phase_identity = transform_phase_identity

    @property
    def cache_digest(self) -> str:
        payload = {
            "shaft_id": self.shaft_id.strip(),
            "frame": self.frame.strip(),
            "frequency_hz": self.frequency_hz,
            "order_identity": self.base_orders,
            "base_frequencies_hz": self.base_frequencies_hz,
            "phase_identity": self.phase_references_rad,
            "nodal_diameter": self.nodal_diameter,
            "convention": self.convention,
            "amplitude_convention": self.amplitude_convention,
            "phase_reference": self.phase_reference,
            "normalization": self.normalization,
            "spectral_kind": self.spectral_kind,
        }
        return sha256(dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @property
    def digest(self) -> str:
        return self.cache_digest


def _canonical_pairs(
    values: tuple[tuple[str, float], ...] | Mapping[str, float], *, signed: bool
) -> tuple[tuple[str, float], ...]:
    items = values.items() if isinstance(values, Mapping) else values
    result: list[tuple[str, float]] = []
    for name, value in items:
        canonical_name = str(name).strip()
        if not canonical_name or not isfinite(value) or (not signed and value < 0):
            raise ValueError("HARMONIC_BASIS_INVALID")
        result.append((canonical_name, 0.0 if value == 0 else float(value)))
    if len({name for name, _ in result}) != len(result):
        raise ValueError("HARMONIC_BASES_NOT_UNIQUE")
    return tuple(sorted(result, key=lambda item: item[0]))


def _canonical_phases(
    values: tuple[tuple[str, float], ...] | Mapping[str, float],
    orders: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    supplied = _canonical_pairs(values, signed=True)
    expected = {name for name, _ in orders}
    if supplied and {name for name, _ in supplied} != expected:
        raise ValueError("HARMONIC_PHASE_BASES_MISMATCH")
    phase_by_name = dict(supplied)
    return tuple(
        (name, _canonical_angle(phase_by_name.get(name, 0.0)))
        for name, _ in orders
    )


def _canonical_angle(value: float) -> float:
    if not isfinite(value):
        raise ValueError("HARMONIC_PHASE_INVALID")
    normalized = fmod(value, 2.0 * pi)
    return 0.0 if abs(normalized) < 1e-15 else normalized % (2.0 * pi)


@dataclass(frozen=True, slots=True)
class ForcingSpectrum:
    """One forcing spectrum contributed by an arbitrary participant."""

    source: str
    label: str
    frequencies_hz: tuple[float, ...]
    amplitudes: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.label.strip():
            raise ValueError("FORCING_SPECTRUM_NEEDS_SOURCE_AND_LABEL")
        if not self.frequencies_hz or len(self.frequencies_hz) != len(self.amplitudes):
            raise ValueError("FORCING_SPECTRUM_NEEDS_MATCHED_LINES")
        for value in (*self.frequencies_hz, *self.amplitudes):
            if not isfinite(value) or value < 0:
                raise ValueError("FORCING_SPECTRUM_MUST_BE_FINITE_NONNEGATIVE")


@dataclass(frozen=True, slots=True)
class ModalSpectrum:
    """One modal/rotordynamic spectrum from an arbitrary dynamic participant."""

    source: str
    kind: str
    natural_frequencies_hz: tuple[float, ...]
    damping_ratios: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.kind.strip():
            raise ValueError("MODAL_SPECTRUM_NEEDS_SOURCE_AND_KIND")
        if not self.natural_frequencies_hz or len(self.natural_frequencies_hz) != len(
            self.damping_ratios
        ):
            raise ValueError("MODAL_SPECTRUM_NEEDS_MATCHED_MODES")
        for value in self.natural_frequencies_hz:
            if not isfinite(value) or value <= 0:
                raise ValueError("MODAL_FREQUENCIES_MUST_BE_POSITIVE")
        for value in self.damping_ratios:
            if not isfinite(value) or value < 0:
                raise ValueError("DAMPING_RATIOS_MUST_BE_NONNEGATIVE")


@dataclass(frozen=True, slots=True)
class ProximityReport:
    min_separation_hz: float
    worst_forcing: tuple[str, float]
    worst_mode: tuple[str, float]
    pairs: tuple[tuple[str, float, str, float, float], ...]


def separation(
    forcing: tuple[ForcingSpectrum, ...], modal: tuple[ModalSpectrum, ...]
) -> ProximityReport:
    """Minimum absolute separation between any forcing line and any mode."""
    if not forcing or not modal:
        raise ValueError("PROXIMITY_NEEDS_FORCING_AND_MODAL_SPECTRA")
    pairs: list[tuple[str, float, str, float, float]] = []
    for force in forcing:
        for frequency, _ in zip(force.frequencies_hz, force.amplitudes, strict=True):
            for spectrum in modal:
                for mode in spectrum.natural_frequencies_hz:
                    pairs.append(
                        (
                            force.source,
                            frequency,
                            spectrum.source,
                            mode,
                            abs(mode - frequency),
                        )
                    )
    worst = min(pairs, key=lambda item: item[4])
    ordered = tuple(sorted(pairs, key=lambda item: item[4]))
    return ProximityReport(
        worst[4], (worst[0], worst[1]), (worst[2], worst[3]), ordered
    )


@dataclass(frozen=True, slots=True)
class ResonancePolicy:
    warning_margin_hz: float
    critical_margin_hz: float
    watch_activate: tuple[str, ...]
    critical_activate: tuple[str, ...]
    available: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isfinite(self.warning_margin_hz)
            or not isfinite(self.critical_margin_hz)
            or self.warning_margin_hz <= 0
            or self.critical_margin_hz <= 0
            or self.critical_margin_hz > self.warning_margin_hz
        ):
            raise ValueError("INVALID_RESONANCE_MARGINS")


@dataclass(frozen=True, slots=True)
class ResonanceTrigger:
    state: str  # "clear" | "watch" | "triggered"
    min_separation_hz: float
    activate: tuple[str, ...]
    required_capability: str | None
    detail: str


_CAPABILITY_BY_IMPLEMENTATION = (
    ("fsi", "field-coupled"),
    ("ami", "transient"),
    ("transient", "transient"),
    ("harmonic", "harmonic"),
    ("detailed", "transient"),
    ("coupled", "field-coupled"),
)


def _capability_for(name: str) -> str:
    lowered = name.lower()
    for marker, capability in _CAPABILITY_BY_IMPLEMENTATION:
        if marker in lowered:
            return capability
    return "transient"


def check_resonance(
    forcing: tuple[ForcingSpectrum, ...],
    modal: tuple[ModalSpectrum, ...],
    policy: ResonancePolicy,
) -> ResonanceTrigger:
    """Assess proximity and name the higher-fidelity implementations to run."""
    report = separation(forcing, modal)
    margin = report.min_separation_hz
    if margin <= policy.critical_margin_hz:
        wanted = policy.critical_activate
        state = "triggered"
    elif margin <= policy.warning_margin_hz:
        wanted = policy.watch_activate
        state = "watch" if wanted else "clear"
        if not wanted:
            return ResonanceTrigger(
                "clear",
                margin,
                (),
                None,
                f"separation {margin:.3g} Hz inside watch band but nothing to activate",
            )
    else:
        return ResonanceTrigger(
            "clear",
            margin,
            (),
            None,
            f"forcing lines separated from modes by {margin:.3g} Hz",
        )
    activate = tuple(name for name in wanted if name in policy.available)
    capability = _capability_for(activate[0]) if activate else None
    return ResonanceTrigger(
        state if activate else "watch",
        margin,
        activate,
        capability,
        f"separation {margin:.3g} Hz crosses the {state} margin; "
        f"activating {', '.join(activate) if activate else 'nothing available'}",
    )
