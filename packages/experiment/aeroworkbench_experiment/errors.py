"""Typed, fail-closed error taxonomy for the experimental evidence layer.

Every failure mode is explicit: a malformed contract, an unknown unit, a raw
record that cannot be parsed, an out-of-domain comparison, a failed
identification, or a requested native/DAQ capability that is not wired. A
requested hardware path never falls back to a screening model; it fails closed
with :class:`CapabilityUnavailable`. Nothing is fabricated.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CapabilityUnavailable",
    "ComparisonError",
    "EvidenceError",
    "ExperimentError",
    "IdentificationError",
    "IngestionError",
    "SynchronizationError",
    "UnitError",
    "ValidityError",
    "finite",
]


class ExperimentError(ValueError):
    """Base class for experimental-evidence contract violations."""

    code = "EXPERIMENT_ERROR"


class UnitError(ExperimentError):
    """An unknown or dimensionally inconsistent unit."""

    code = "UNIT_ERROR"


class ValidityError(ExperimentError):
    """A request left the declared validity domain of a contract."""

    code = "VALIDITY_ERROR"


class IngestionError(ExperimentError):
    """A raw measurement record could not be parsed or normalized."""

    code = "INGESTION_ERROR"


class SynchronizationError(ExperimentError):
    """A resample/alignment/filter/segmentation request was ill-posed."""

    code = "SYNCHRONIZATION_ERROR"


class ComparisonError(ExperimentError):
    """A measurement could not be matched to a simulation result envelope."""

    code = "COMPARISON_ERROR"


class IdentificationError(ExperimentError):
    """A bounded parameter identification could not be satisfied."""

    code = "IDENTIFICATION_ERROR"


class EvidenceError(ExperimentError):
    """An evidence record would conflate measurement and simulation, or relabel."""

    code = "EVIDENCE_ERROR"


class CapabilityUnavailable(RuntimeError):
    """A requested native solver or DAQ hardware capability is absent."""

    code = "CAPABILITY_UNAVAILABLE"


def finite(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    positive: bool = False,
) -> float:
    """Validate a finite number, failing closed with a typed error."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentError(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ExperimentError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise ExperimentError(f"{name} must be positive")
    if minimum is not None and result < minimum:
        raise ExperimentError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise ExperimentError(f"{name} must be <= {maximum}")
    return result
