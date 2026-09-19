"""Deterministic worst-case, statistical, and Monte-Carlo tolerance stack-up.

Every method declares its assumptions and produces a hashable result that
carries source/fidelity/units/validity/input-hash/software-identity/provenance.
Monte-Carlo runs are bounded and deterministically seeded; no method silently
extrapolates beyond the declared tolerance intervals.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from aeroworkbench_manufacturing.units import from_si, to_si, unit_dimension

from .contracts import (
    ResultEnvelope,
    ToleranceCallout,
    build_envelope,
    deviation_scale,
)
from .errors import StackupError

__all__ = [
    "MAX_MONTE_CARLO_SAMPLES",
    "StackupModel",
    "StackupResult",
    "StackupTerm",
    "normal_cdf",
    "stackup_monte_carlo",
    "stackup_statistical",
    "stackup_worst_case",
]

MAX_MONTE_CARLO_SAMPLES = 200_000
DEFAULT_MONTE_CARLO_SAMPLES = 10_000


def normal_cdf(value: float, mean: float = 0.0, sigma: float = 1.0) -> float:
    """Standard normal CDF via ``erf``; ``sigma <= 0`` is a deterministic step."""

    if sigma <= 0.0:
        return 1.0 if value >= mean else 0.0
    return 0.5 * (1.0 + math.erf((value - mean) / (sigma * math.sqrt(2.0))))


@dataclass(frozen=True, slots=True)
class StackupTerm:
    """One signed contribution of a callout to a stack-up characteristic."""

    id: str
    callout: ToleranceCallout
    sensitivity: float = 1.0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise StackupError("STACKUP_TERM_ID_REQUIRED")
        if not math.isfinite(self.sensitivity):
            raise StackupError(f"NONFINITE_SENSITIVITY:{self.id}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calloutId": self.callout.id,
            "sensitivity": self.sensitivity,
        }


@dataclass(frozen=True, slots=True)
class StackupModel:
    """A linear stack-up of callouts with optional hard spec limits."""

    stackup_id: str
    characteristic: str
    unit: str
    terms: tuple[StackupTerm, ...]
    lower_spec: float | None = None
    upper_spec: float | None = None

    def __post_init__(self) -> None:
        if not self.stackup_id.strip() or not self.characteristic.strip():
            raise StackupError("STACKUP_ID_AND_CHARACTERISTIC_REQUIRED")
        unit_dimension(self.unit)
        if not self.terms:
            raise StackupError(f"STACKUP_NEEDS_TERMS:{self.stackup_id}")
        seen: set[str] = set()
        for term in self.terms:
            if term.id in seen:
                raise StackupError(f"DUPLICATE_STACKUP_TERM:{self.stackup_id}:{term.id}")
            seen.add(term.id)
            if unit_dimension(term.callout.unit) != unit_dimension(self.unit):
                raise StackupError(f"UNIT_DIMENSION_MISMATCH:{self.stackup_id}:{term.id}")
        if self.lower_spec is not None and not math.isfinite(self.lower_spec):
            raise StackupError(f"NONFINITE_LOWER_SPEC:{self.stackup_id}")
        if self.upper_spec is not None and not math.isfinite(self.upper_spec):
            raise StackupError(f"NONFINITE_UPPER_SPEC:{self.stackup_id}")
        if (
            self.lower_spec is not None
            and self.upper_spec is not None
            and self.lower_spec > self.upper_spec
        ):
            raise StackupError(f"SPEC_INTERVAL_INVERTED:{self.stackup_id}")

    @property
    def nominal_si(self) -> float:
        return sum(term.sensitivity * term.callout.nominal_si for term in self.terms)

    @property
    def spec_lower_si(self) -> float | None:
        return None if self.lower_spec is None else to_si(self.lower_spec, self.unit)

    @property
    def spec_upper_si(self) -> float | None:
        return None if self.upper_spec is None else to_si(self.upper_spec, self.unit)

    def worst_case_bounds_si(self) -> tuple[float, float]:
        lower = 0.0
        upper = 0.0
        for term in self.terms:
            callout = term.callout
            if term.sensitivity >= 0:
                lower += term.sensitivity * callout.lower_si
                upper += term.sensitivity * callout.upper_si
            else:
                lower += term.sensitivity * callout.upper_si
                upper += term.sensitivity * callout.lower_si
        return lower, upper

    def rss_sigma_si(self) -> float:
        variance = 0.0
        for term in self.terms:
            sigma = term.callout.to_distribution_sigma_si()
            variance += (term.sensitivity * sigma) ** 2
        return math.sqrt(variance)

    def inputs_payload(self) -> dict[str, Any]:
        return {
            "stackupId": self.stackup_id,
            "characteristic": self.characteristic,
            "unit": self.unit,
            "terms": [term.as_dict() for term in self.terms],
            "lowerSpec": self.lower_spec,
            "upperSpec": self.upper_spec,
        }

    def as_dict(self) -> dict[str, Any]:
        return self.inputs_payload()


@dataclass(frozen=True, slots=True)
class StackupResult:
    """One stack-up evaluation with its result envelope."""

    stackup_id: str
    characteristic: str
    method: str
    unit: str
    nominal: float
    lower: float
    upper: float
    tolerance: float
    mean: float
    std: float
    samples: int
    seed: int | None
    within_spec: bool | None
    yield_fraction: float | None
    ppm: float | None
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "stackupId": self.stackup_id,
            "characteristic": self.characteristic,
            "method": self.method,
            "unit": self.unit,
            "nominal": self.nominal,
            "lower": self.lower,
            "upper": self.upper,
            "tolerance": self.tolerance,
            "mean": self.mean,
            "std": self.std,
            "samples": self.samples,
            "seed": self.seed,
            "withinSpec": self.within_spec,
            "yieldFraction": self.yield_fraction,
            "ppm": self.ppm,
            "envelope": self.envelope.as_dict(),
        }


def _within_spec(
    lower_si: float, upper_si: float, model: StackupModel
) -> bool | None:
    spec_lower = model.spec_lower_si
    spec_upper = model.spec_upper_si
    if spec_lower is None or spec_upper is None:
        return None
    return lower_si >= spec_lower and upper_si <= spec_upper


def stackup_worst_case(model: StackupModel) -> StackupResult:
    """Conservative envelope: every callout simultaneously at its limit."""

    lower_si, upper_si = model.worst_case_bounds_si()
    nominal_si = model.nominal_si
    envelope = build_envelope(
        model="advphys10-tolerance-stackup-worst-case",
        inputs=model.inputs_payload(),
        unit=model.unit,
        assumptions=(
            "all callouts simultaneously at their drawing limits",
            "linear (first-order) sensitivity propagation",
            "no statistical cancellation is credited",
        ),
    )
    return StackupResult(
        stackup_id=model.stackup_id,
        characteristic=model.characteristic,
        method="worst_case",
        unit=model.unit,
        nominal=from_si(nominal_si, model.unit),
        lower=from_si(lower_si, model.unit),
        upper=from_si(upper_si, model.unit),
        tolerance=from_si(0.5 * (upper_si - lower_si), model.unit),
        mean=from_si(nominal_si, model.unit),
        std=0.0,
        samples=0,
        seed=None,
        within_spec=_within_spec(lower_si, upper_si, model),
        yield_fraction=None,
        ppm=None,
        envelope=envelope,
    )


def stackup_statistical(model: StackupModel, *, sigma_multiplier: float = 3.0) -> StackupResult:
    """RSS propagation assuming independent, declared per-callout distributions."""

    if sigma_multiplier <= 0:
        raise StackupError("SIGMA_MULTIPLIER_MUST_BE_POSITIVE")
    nominal_si = model.nominal_si
    sigma_si = model.rss_sigma_si()
    half = sigma_multiplier * sigma_si
    lower_si = nominal_si - half
    upper_si = nominal_si + half
    yield_fraction, ppm = _normal_yield(nominal_si, sigma_si, model)
    envelope = build_envelope(
        model="advphys10-tolerance-stackup-rss",
        inputs={
            **model.inputs_payload(),
            "sigmaMultiplier": sigma_multiplier,
        },
        unit=model.unit,
        assumptions=(
            "callout contributions are independent",
            "declared per-callout distributions with the given sigma multiplier",
            "linear (first-order) sensitivity propagation",
        ),
    )
    return StackupResult(
        stackup_id=model.stackup_id,
        characteristic=model.characteristic,
        method="rss",
        unit=model.unit,
        nominal=from_si(nominal_si, model.unit),
        lower=from_si(lower_si, model.unit),
        upper=from_si(upper_si, model.unit),
        tolerance=from_si(half, model.unit),
        mean=from_si(nominal_si, model.unit),
        std=from_si(sigma_si, model.unit),
        samples=0,
        seed=None,
        within_spec=_within_spec(lower_si, upper_si, model),
        yield_fraction=yield_fraction,
        ppm=ppm,
        envelope=envelope,
    )


def _normal_yield(
    nominal_si: float, sigma_si: float, model: StackupModel
) -> tuple[float | None, float | None]:
    spec_lower = model.spec_lower_si
    spec_upper = model.spec_upper_si
    if spec_lower is None or spec_upper is None:
        return None, None
    fraction = normal_cdf(spec_upper, nominal_si, sigma_si) - normal_cdf(
        spec_lower, nominal_si, sigma_si
    )
    fraction = min(max(fraction, 0.0), 1.0)
    return fraction, (1.0 - fraction) * 1.0e6


def stackup_monte_carlo(
    model: StackupModel,
    *,
    samples: int = DEFAULT_MONTE_CARLO_SAMPLES,
    seed: int = 0,
) -> StackupResult:
    """Bounded, deterministically seeded sampling of the declared distributions."""

    if samples < 1:
        raise StackupError("MONTE_CARLO_SAMPLES_MUST_BE_POSITIVE")
    if samples > MAX_MONTE_CARLO_SAMPLES:
        raise StackupError(f"MONTE_CARLO_SAMPLES_EXCEED_BOUND:{MAX_MONTE_CARLO_SAMPLES}")
    rng = random.Random(seed)
    nominal_si = model.nominal_si
    spec_lower = model.spec_lower_si
    spec_upper = model.spec_upper_si
    count = 0
    mean = 0.0
    m2 = 0.0
    minimum = math.inf
    maximum = -math.inf
    passed = 0
    for _ in range(samples):
        value = nominal_si
        for term in model.terms:
            deviation = term.callout.sample_deviation(rng)
            value += term.sensitivity * deviation * deviation_scale(term.callout.unit)
        count += 1
        delta = value - mean
        mean += delta / count
        m2 += delta * (value - mean)
        minimum = min(minimum, value)
        maximum = max(maximum, value)
        if (
            spec_lower is not None
            and spec_upper is not None
            and spec_lower <= value <= spec_upper
        ):
            passed += 1
    std_si = math.sqrt(m2 / count) if count > 1 else 0.0
    within_spec: bool | None
    yield_fraction: float | None
    ppm: float | None
    if spec_lower is not None and spec_upper is not None:
        fraction = passed / count
        within_spec = fraction == 1.0
        yield_fraction = fraction
        ppm = (1.0 - fraction) * 1.0e6
    else:
        within_spec = None
        yield_fraction = None
        ppm = None
    envelope = build_envelope(
        model="advphys10-tolerance-stackup-monte-carlo",
        inputs={
            **model.inputs_payload(),
            "samples": samples,
            "seed": seed,
        },
        unit=model.unit,
        assumptions=(
            "callouts sampled independently from their declared distributions",
            "normal callouts truncated to the declared drawing limits",
            "linear (first-order) sensitivity propagation",
            "fixed seed for reproducibility",
        ),
    )
    return StackupResult(
        stackup_id=model.stackup_id,
        characteristic=model.characteristic,
        method="monte_carlo",
        unit=model.unit,
        nominal=from_si(nominal_si, model.unit),
        lower=from_si(minimum, model.unit),
        upper=from_si(maximum, model.unit),
        tolerance=from_si(0.5 * (maximum - minimum), model.unit),
        mean=from_si(mean, model.unit),
        std=from_si(std_si, model.unit),
        samples=samples,
        seed=seed,
        within_spec=within_spec,
        yield_fraction=yield_fraction,
        ppm=ppm,
        envelope=envelope,
    )
