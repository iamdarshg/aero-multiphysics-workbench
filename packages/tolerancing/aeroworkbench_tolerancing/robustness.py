"""Yield and robustness: probability of satisfying hard toleranced limits.

Nominal feasibility is reported separately from tolerance feasibility and from
the estimated fraction satisfying the spec, so a design that is valid only at
its nominal point can never be presented as production-ready. All estimates are
deterministic, seeded, and bounded.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .contracts import ResultEnvelope, build_envelope
from .errors import YieldError
from .stackup import (
    DEFAULT_MONTE_CARLO_SAMPLES,
    StackupModel,
    StackupResult,
    stackup_monte_carlo,
    stackup_statistical,
    stackup_worst_case,
)

__all__ = [
    "RobustnessReport",
    "YieldEstimate",
    "assess_robustness",
    "estimate_yield",
    "require_robust",
    "wilson_interval",
]

_Z_95 = 1.959963984540054


@dataclass(frozen=True, slots=True)
class YieldEstimate:
    """Estimated fraction satisfying all hard constraints, plus PPM and interval."""

    samples: int
    passed: int
    fraction: float
    ppm: float
    method: str
    seed: int | None
    confidence_low: float
    confidence_high: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "passed": self.passed,
            "fraction": self.fraction,
            "ppm": self.ppm,
            "method": self.method,
            "seed": self.seed,
            "confidenceLow": self.confidence_low,
            "confidenceHigh": self.confidence_high,
        }


def wilson_interval(passed: int, total: int, *, z: float = _Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (stable near 0 and 1)."""

    if total <= 0:
        raise YieldError("YIELD_NEEDS_POSITIVE_SAMPLE_COUNT")
    if passed < 0 or passed > total:
        raise YieldError("YIELD_PASSED_OUT_OF_RANGE")
    p = passed / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    margin = (
        z
        * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
        / denom
    )
    return max(center - margin, 0.0), min(center + margin, 1.0)


def estimate_yield(
    passes: Sequence[bool],
    *,
    method: str = "monte-carlo",
    seed: int | None = None,
) -> YieldEstimate:
    """Fold a sequence of per-sample pass/fail outcomes into a yield estimate."""

    total = len(passes)
    if total == 0:
        raise YieldError("YIELD_NEEDS_POSITIVE_SAMPLE_COUNT")
    passed = sum(1 for item in passes if item)
    fraction = passed / total
    low, high = wilson_interval(passed, total)
    return YieldEstimate(
        samples=total,
        passed=passed,
        fraction=fraction,
        ppm=(1.0 - fraction) * 1.0e6,
        method=method,
        seed=seed,
        confidence_low=low,
        confidence_high=high,
    )


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    """Nominal vs tolerance feasibility and estimated production yield."""

    characteristic: str
    unit: str
    nominally_feasible: bool
    tolerance_feasible: bool
    required_yield: float
    estimated_yield: float
    meets_required_yield: bool
    robust: bool
    worst_case: StackupResult
    statistic: StackupResult
    samples: StackupResult
    estimate: YieldEstimate
    envelope: ResultEnvelope

    def as_dict(self) -> dict[str, Any]:
        return {
            "characteristic": self.characteristic,
            "unit": self.unit,
            "nominallyFeasible": self.nominally_feasible,
            "toleranceFeasible": self.tolerance_feasible,
            "requiredYield": self.required_yield,
            "estimatedYield": self.estimated_yield,
            "meetsRequiredYield": self.meets_required_yield,
            "robust": self.robust,
            "worstCase": self.worst_case.as_dict(),
            "statistic": self.statistic.as_dict(),
            "samples": self.samples.as_dict(),
            "estimate": self.estimate.as_dict(),
            "envelope": self.envelope.as_dict(),
        }


def assess_robustness(
    model: StackupModel,
    *,
    required_yield: float = 0.9973,
    samples: int = DEFAULT_MONTE_CARLO_SAMPLES,
    seed: int = 0,
) -> RobustnessReport:
    """Assess a toleranced characteristic against hard spec limits.

    The report never treats nominal feasibility as sufficient: tolerance
    feasibility and estimated yield are computed and compared against the
    required yield independently.
    """

    if not math.isfinite(required_yield) or not 0.0 < required_yield <= 1.0:
        raise YieldError("REQUIRED_YIELD_MUST_BE_IN_(0,1]")
    spec_lower = model.spec_lower_si
    spec_upper = model.spec_upper_si
    if spec_lower is None or spec_upper is None:
        raise YieldError(f"ROBUSTNESS_NEEDS_SPEC_LIMITS:{model.stackup_id}")
    worst_case = stackup_worst_case(model)
    statistical = stackup_statistical(model)
    sampled = stackup_monte_carlo(model, samples=samples, seed=seed)
    nominal_si = model.nominal_si
    nominally_feasible = spec_lower <= nominal_si <= spec_upper
    lower_si, upper_si = model.worst_case_bounds_si()
    tolerance_feasible = lower_si >= spec_lower and upper_si <= spec_upper
    if sampled.yield_fraction is None:  # pragma: no cover - spec limits guaranteed
        raise YieldError(f"YIELD_UNAVAILABLE:{model.stackup_id}")
    passed = int(round(sampled.yield_fraction * sampled.samples))
    low, high = wilson_interval(passed, sampled.samples)
    estimate = YieldEstimate(
        samples=sampled.samples,
        passed=passed,
        fraction=sampled.yield_fraction,
        ppm=0.0 if sampled.ppm is None else sampled.ppm,
        method="monte-carlo",
        seed=seed,
        confidence_low=low,
        confidence_high=high,
    )
    meets_required = estimate.fraction >= required_yield
    robust = nominally_feasible and tolerance_feasible and meets_required
    envelope = build_envelope(
        model="advphys10-robustness",
        inputs={
            **model.inputs_payload(),
            "requiredYield": required_yield,
            "samples": samples,
            "seed": seed,
        },
        unit=model.unit,
        assumptions=(
            "yield is the sampled fraction satisfying both hard spec limits",
            "tolerance feasibility uses the worst-case drawing envelope",
            "nominal feasibility is never treated as sufficient",
            "fixed seed for reproducibility",
        ),
        validity="valid" if robust else "rejected",
    )
    return RobustnessReport(
        characteristic=model.characteristic,
        unit=model.unit,
        nominally_feasible=nominally_feasible,
        tolerance_feasible=tolerance_feasible,
        required_yield=required_yield,
        estimated_yield=estimate.fraction,
        meets_required_yield=meets_required,
        robust=robust,
        worst_case=worst_case,
        statistic=statistical,
        samples=sampled,
        estimate=estimate,
        envelope=envelope,
    )


def require_robust(
    model: StackupModel,
    *,
    required_yield: float = 0.9973,
    samples: int = DEFAULT_MONTE_CARLO_SAMPLES,
    seed: int = 0,
) -> RobustnessReport:
    """Fail closed unless the design is nominally and tolerance feasible."""

    report = assess_robustness(
        model, required_yield=required_yield, samples=samples, seed=seed
    )
    if not report.robust:
        reasons: list[str] = []
        if not report.nominally_feasible:
            reasons.append("NOMINALLY_INFEASIBLE")
        if not report.tolerance_feasible:
            reasons.append("TOLERANCE_INFEASIBLE")
        if not report.meets_required_yield:
            reasons.append("YIELD_BELOW_REQUIRED")
        raise YieldError(f"DESIGN_NOT_ROBUST:{model.stackup_id}:{','.join(reasons)}")
    return report


def robustness_from_mapping(
    model: StackupModel, payload: Mapping[str, Any]
) -> RobustnessReport:
    """Convenience wrapper accepting explicit option overrides."""

    return assess_robustness(
        model,
        required_yield=float(payload.get("requiredYield", 0.9973)),
        samples=int(payload.get("samples", DEFAULT_MONTE_CARLO_SAMPLES)),
        seed=int(payload.get("seed", 0)),
    )
