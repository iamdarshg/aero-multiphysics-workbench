"""Shared result envelope pieces for the acoustics layer.

Every acoustic result carries a source, a fidelity level, units, a validity
verdict, an input hash, a software identity, and provenance. Values are never
invented: analytical screening and post-processing are labelled analytical or
reduced, and native propagation requires explicit solver identity and a trusted
run receipt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .errors import AcousticInputError, AcousticValidityError

SOFTWARE_IDENTITY = "aeroworkbench-turbomachinery-acoustics"
SOFTWARE_VERSION = "1.0.0"

REFERENCE_PRESSURE_PA = 20.0e-6


class AcousticFidelity(StrEnum):
    """The aeroacoustic fidelity ladder, cheapest first."""

    TONAL_SCREENING = "tonal-screening"
    THERMOACOUSTIC_SCREENING = "thermoacoustic-screening"
    SURFACE_SPECTRA = "surface-pressure-spectra"
    FW_H_PROPAGATION = "fw-h-propagation"
    OBSERVER_SPL = "observer-spl-tonal"
    TRANSIENT_REACTING = "transient-reacting"

    def core_level(self) -> FidelityLevel:
        return _CORE_LEVELS[self]

    def rank(self) -> int:
        return _FIDELITY_RANK[self]

    def requires_native(self) -> bool:
        return self in (AcousticFidelity.SURFACE_SPECTRA,
                        AcousticFidelity.FW_H_PROPAGATION,
                        AcousticFidelity.OBSERVER_SPL,
                        AcousticFidelity.TRANSIENT_REACTING)


_CORE_LEVELS: dict[AcousticFidelity, FidelityLevel] = {
    AcousticFidelity.TONAL_SCREENING: FidelityLevel.ANALYTICAL,
    AcousticFidelity.THERMOACOUSTIC_SCREENING: FidelityLevel.MRF,
    AcousticFidelity.SURFACE_SPECTRA: FidelityLevel.MRF,
    AcousticFidelity.FW_H_PROPAGATION: FidelityLevel.TRANSIENT,
    AcousticFidelity.OBSERVER_SPL: FidelityLevel.TRANSIENT,
    AcousticFidelity.TRANSIENT_REACTING: FidelityLevel.TRANSIENT,
}

_FIDELITY_RANK: dict[AcousticFidelity, int] = {
    AcousticFidelity.TONAL_SCREENING: 0,
    AcousticFidelity.THERMOACOUSTIC_SCREENING: 1,
    AcousticFidelity.SURFACE_SPECTRA: 2,
    AcousticFidelity.FW_H_PROPAGATION: 3,
    AcousticFidelity.OBSERVER_SPL: 4,
    AcousticFidelity.TRANSIENT_REACTING: 5,
}


@dataclass(frozen=True, slots=True)
class AcousticSoftware:
    """The software identity that produced an acoustic result."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_ACOUSTIC_SOFTWARE = AcousticSoftware()


@dataclass(frozen=True, slots=True)
class AcousticValidity:
    """Per-check validity verdict carried on every acoustic result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "detail": self.detail,
        }


def finite(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float:
    """Validate a finite real number, failing closed with a typed error."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AcousticInputError(f"{name} must be a number")
    result = float(value)
    if not isfinite(result):
        raise AcousticInputError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise AcousticInputError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise AcousticInputError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise AcousticInputError(f"{name} must be <= {maximum}")
    return result


def finite_series(value: Any, name: str) -> tuple[float, ...]:
    """Validate a non-empty sequence of finite reals."""

    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise AcousticInputError(f"{name} must be a non-empty sequence")
    return tuple(finite(item, f"{name}[{index}]") for index, item in enumerate(value))


def spectrum_lines(value: Any, name: str) -> tuple[tuple[float, float], ...]:
    """Validate, sort, and de-duplicate ``(frequency_hz, amplitude)`` lines."""

    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise AcousticInputError(f"{name} must be a sequence")
    lines: list[tuple[float, float]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise AcousticInputError(f"{name}[{index}] must be a (frequency, amplitude) pair")
        frequency = finite(entry[0], f"{name}[{index}].frequency_hz", minimum=0.0)
        amplitude = finite(entry[1], f"{name}[{index}].amplitude")
        lines.append((frequency, amplitude))
    return tuple(sorted(lines))


def check_validity(checks: Mapping[str, bool], detail: str) -> AcousticValidity:
    """Collapse a named check map into a fail-closed validity verdict."""

    report = {str(name): bool(flag) for name, flag in checks.items()}
    return AcousticValidity(passed=all(report.values()), checks=report, detail=detail)


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
    fidelity: FidelityLevel = FidelityLevel.ANALYTICAL,
) -> Provenance:
    """Provenance for a closed-form/reduced aeroacoustic screening model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity,
        assumptions=tuple(assumptions),
    )


def native_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    solver_name: str,
    solver_version: str,
    run_id: str,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a native result; solver identity and run id are mandatory."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.TRANSIENT,
        assumptions=tuple(assumptions),
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
    )


def spl_db(pressure_pa: float, *, reference_pressure_pa: float = REFERENCE_PRESSURE_PA) -> float:
    """Sound pressure level of a pressure amplitude against a reference."""

    pressure = finite(pressure_pa, "pressure_pa", minimum=0.0)
    reference = finite(reference_pressure_pa, "reference_pressure_pa", positive=True)
    from math import log10

    if pressure <= 0.0:
        return 0.0
    return 20.0 * log10(pressure / reference)


def energy_sum_db(levels_db: Sequence[float]) -> float:
    """Incoherent (energy) sum of decibel levels."""

    from math import log10

    total = 0.0
    for level in levels_db:
        value = finite(level, "level_db")
        total += 10.0 ** (value / 10.0)
    return 10.0 * log10(total) if total > 0.0 else 0.0


__all__ = [
    "DEFAULT_ACOUSTIC_SOFTWARE",
    "REFERENCE_PRESSURE_PA",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "AcousticFidelity",
    "AcousticSoftware",
    "AcousticValidity",
    "AcousticValidityError",
    "AcousticInputError",
    "analytical_provenance",
    "check_validity",
    "energy_sum_db",
    "finite",
    "finite_series",
    "native_provenance",
    "spl_db",
    "spectrum_lines",
]
