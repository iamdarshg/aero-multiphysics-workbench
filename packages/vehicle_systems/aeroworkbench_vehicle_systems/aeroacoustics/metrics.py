"""Aggregate observer metrics: OASPL, SEL, and simplified EPNL with raw spectra."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite, log10
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_turbomachinery.acoustics import (  # type: ignore[import-not-found, unused-ignore]
    energy_sum_db,
)

from .contracts import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    NoiseFidelity,
    NoiseValidity,
    analytical_provenance,
)
from .errors import ContractError
from .observers import WEIGHTING_STANDARDS, Weighting, apply_weighting
from .propagation import ObserverNoiseResult

__all__ = [
    "EPNL_MODEL",
    "NoiseMetrics",
    "assess_observer_noise",
    "effective_perceived_noise_level_db",
    "overall_level_db",
    "sound_exposure_level_db",
]

EPNL_MODEL = "simplified-EPNL on an ICAO Annex 16 basis; not a certification finding"


def _finite(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a number")
    number = float(value)
    if not isfinite(number):
        raise ContractError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise ContractError(f"{name} must be positive")
    return number


def overall_level_db(levels_db: Sequence[float]) -> float:
    """Incoherent energy sum of decibel levels (shared acoustic piece)."""

    if not levels_db:
        raise ContractError("NO_LEVELS: at least one level is required")
    return float(energy_sum_db([_finite(level, "level_db") for level in levels_db]))


def sound_exposure_level_db(overall_db: float, duration_s: float) -> float:
    """Sound exposure level: overall level normalized to a 1 s reference."""

    level = _finite(overall_db, "overall_db")
    duration = _finite(duration_s, "duration_s", positive=True)
    return level + 10.0 * log10(duration)


def effective_perceived_noise_level_db(
    max_tone_corrected_db: float, duration_s: float, *, tone_correction_db: float = 0.0
) -> float:
    """Simplified EPNL from a declared tone-corrected maximum plus duration."""

    maximum = _finite(max_tone_corrected_db, "max_tone_corrected_db")
    duration = _finite(duration_s, "duration_s", positive=True)
    correction = _finite(tone_correction_db, "tone_correction_db")
    if correction < 0.0:
        raise ContractError("tone_correction_db must be >= 0")
    return maximum + correction + 10.0 * log10(duration / 10.0)


@dataclass(frozen=True, slots=True)
class NoiseMetrics:
    """Aggregate observer metrics with standards cited and raw spectra preserved."""

    observer_id: str
    oaspl_db: float
    weighting: Weighting
    weighted_level_db: float
    duration_s: float
    sel_db: float
    epnl_db: float
    tone_correction_db: float
    standards: tuple[str, ...]
    spectrum: tuple[tuple[float, float], ...]
    fidelity: NoiseFidelity
    validity: NoiseValidity
    provenance: Any
    software: str = SOFTWARE_NAME
    software_version: str = SOFTWARE_VERSION

    def units(self) -> dict[str, str]:
        return {"frequency_hz": "Hz", "level_db": "dB", "duration_s": "s"}

    @property
    def source(self) -> str:
        return str(self.provenance.source.value)

    @property
    def input_hash(self) -> str:
        return str(self.provenance.inputs_hash)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "observerId": self.observer_id,
            "oasplDb": self.oaspl_db,
            "weighting": self.weighting.value,
            "weightedLevelDb": self.weighted_level_db,
            "durationS": self.duration_s,
            "selDb": self.sel_db,
            "epnlDb": self.epnl_db,
            "toneCorrectionDb": self.tone_correction_db,
            "standards": list(self.standards),
            "spectrum": [[frequency, level] for frequency, level in self.spectrum],
            "source": self.source,
            "fidelity": self.fidelity.value,
            "inputsHash": self.input_hash,
            "software": {"name": self.software, "version": self.software_version},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def assess_observer_noise(
    result: ObserverNoiseResult,
    *,
    weighting: Weighting = Weighting.A,
    duration_s: float = 10.0,
    tone_correction_db: float = 0.0,
) -> NoiseMetrics:
    """Aggregate one observer result into OASPL/SEL/EPNL with explicit standards."""

    if not result.lines:
        raise ContractError("NO_OBSERVER_LINES: the observer result carries no lines")
    duration = _finite(duration_s, "duration_s", positive=True)
    correction = _finite(tone_correction_db, "tone_correction_db")
    if correction < 0.0:
        raise ContractError("tone_correction_db must be >= 0")
    weighted = tuple(
        apply_weighting(line.observer_level_db, line.observed_frequency_hz, weighting)
        for line in result.lines
    )
    weighted_level = overall_level_db(weighted)
    spectrum = tuple(
        (line.observed_frequency_hz, line.observer_level_db) for line in result.lines
    )
    maximum = max(weighted)
    standards = (WEIGHTING_STANDARDS[weighting.value], EPNL_MODEL)
    checks = {
        "observer_valid": result.validity.passed,
        "duration_positive": duration > 0.0,
        "spectrum_preserved": len(spectrum) == len(result.lines),
    }
    inputs = {
        "observer": result.canonical_payload(),
        "weighting": weighting.value,
        "durationS": duration,
        "toneCorrectionDb": correction,
    }
    return NoiseMetrics(
        observer_id=result.observer_id,
        oaspl_db=result.overall_level_db,
        weighting=weighting,
        weighted_level_db=weighted_level,
        duration_s=duration,
        sel_db=sound_exposure_level_db(result.overall_level_db, duration),
        epnl_db=effective_perceived_noise_level_db(maximum, duration,
                                                   tone_correction_db=correction),
        tone_correction_db=correction,
        standards=standards,
        spectrum=spectrum,
        fidelity=NoiseFidelity.OBSERVER_ANALYTICAL,
        validity=NoiseValidity(
            all(checks.values()), checks, f"aggregated {len(spectrum)} observer lines"
        ),
        provenance=analytical_provenance(
            "aeroacoustics.observer-metrics",
            inputs,
            assumptions=(
                "weighting filter shape follows the cited standard",
                "EPNL is a simplified duration correction, not certification",
                "raw observer spectrum is preserved alongside aggregates",
            ),
        ),
    )
