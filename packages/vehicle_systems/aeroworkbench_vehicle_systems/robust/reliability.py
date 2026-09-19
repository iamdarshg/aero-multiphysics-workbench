"""Reliability constraints: probability-of-failure and reliability index.

Two honest estimators are provided. Bounded Monte Carlo counts exceedances and
reports a Wilson score interval; first-order reliability (FORM) uses the mean
and covariance of a linear limit state to produce an exact reliability index
for hand-computable cases. A reliability claim is only *admissible* when the
governing fidelity is trusted: a cheap surrogate's model-form error can tighten
the margin (a worst-case penalty) but can never by itself turn a surrogate into
a reliability PASS.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_rom.contracts import SoftwareIdentity, Validity

from .contracts import SOFTWARE_NAME, SOFTWARE_VERSION
from .distributions import normal_cdf, normal_inv_cdf
from .errors import ReliabilityError

__all__ = [
    "LimitDirection",
    "ReliabilityConstraint",
    "ReliabilityEstimate",
    "ReliabilityMethod",
    "estimate_reliability",
    "first_order_reliability",
    "monte_carlo_reliability",
    "reliability_index_from_failure_probability",
]


class LimitDirection(StrEnum):
    """Which side of the limit constitutes failure."""

    UPPER = "upper"
    LOWER = "lower"


class ReliabilityMethod(StrEnum):
    """Supported reliability estimators."""

    MONTE_CARLO = "monte-carlo"
    FIRST_ORDER = "first-order"


@dataclass(frozen=True, slots=True)
class ReliabilityConstraint:
    """A chance/reliability requirement on a named response."""

    name: str
    response: str
    direction: LimitDirection
    limit: float
    target_probability_of_failure: float = 1e-3
    method: ReliabilityMethod = ReliabilityMethod.MONTE_CARLO
    confidence: float = 0.95
    margin_penalty: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.response.strip():
            raise ReliabilityError("RELIABILITY_CONSTRAINT_NEEDS_NAME_AND_RESPONSE")
        if not isfinite(self.limit):
            raise ReliabilityError(f"NONFINITE_RELIABILITY_LIMIT:{self.name}")
        if not 0.0 <= self.target_probability_of_failure < 1.0:
            raise ReliabilityError(f"INVALID_TARGET_FAILURE_PROBABILITY:{self.name}")
        if not 0.0 < self.confidence < 1.0:
            raise ReliabilityError(f"INVALID_RELIABILITY_CONFIDENCE:{self.name}")
        if not isfinite(self.margin_penalty) or self.margin_penalty < 0.0:
            raise ReliabilityError(f"INVALID_RELIABILITY_MARGIN_PENALTY:{self.name}")

    def is_failure(self, value: float) -> bool:
        adjusted = value + self.margin_penalty if self.direction is LimitDirection.UPPER else (
            value - self.margin_penalty
        )
        return adjusted > self.limit if self.direction is LimitDirection.UPPER else (
            adjusted < self.limit
        )

    def margin(self, value: float) -> float:
        adjusted = value + self.margin_penalty if self.direction is LimitDirection.UPPER else (
            value - self.margin_penalty
        )
        return self.limit - adjusted if self.direction is LimitDirection.UPPER else (
            adjusted - self.limit
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "response": self.response,
            "direction": self.direction.value,
            "limit": self.limit,
            "targetProbabilityOfFailure": self.target_probability_of_failure,
            "method": self.method.value,
            "confidence": self.confidence,
            "marginPenalty": self.margin_penalty,
        }


@dataclass(frozen=True, slots=True)
class ReliabilityEstimate:
    """The evidence behind a reliability verdict."""

    name: str
    response: str
    method: str
    direction: str
    limit: float
    samples: int
    failures: int
    probability_of_failure: float
    probability_lower: float
    probability_upper: float
    reliability_index: float | None
    mean_response: float
    margin: float
    trusted: bool
    admissible: bool
    passed: bool
    basis: str
    reasons: tuple[str, ...]
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = field(
        default_factory=lambda: SoftwareIdentity(name=SOFTWARE_NAME, version=SOFTWARE_VERSION)
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "response": self.response,
            "method": self.method,
            "direction": self.direction,
            "limit": self.limit,
            "samples": self.samples,
            "failures": self.failures,
            "probabilityOfFailure": self.probability_of_failure,
            "probabilityLower": self.probability_lower,
            "probabilityUpper": self.probability_upper,
            "reliabilityIndex": self.reliability_index,
            "meanResponse": self.mean_response,
            "margin": self.margin,
            "trusted": self.trusted,
            "admissible": self.admissible,
            "passed": self.passed,
            "basis": self.basis,
            "reasons": list(self.reasons),
            "validity": self.validity.canonical(),
            "sourceKind": self.provenance.source.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def reliability_index_from_failure_probability(
    probability_of_failure: float,
) -> float | None:
    """Reliability index ``beta = -Phi^-1(pf)``; ``None`` at the boundaries."""
    if not 0.0 <= probability_of_failure <= 1.0:
        raise ReliabilityError("FAILURE_PROBABILITY_OUT_OF_RANGE")
    if probability_of_failure <= 0.0 or probability_of_failure >= 1.0:
        return None
    return -normal_inv_cdf(probability_of_failure)


def _wilson_interval(
    failures: int, samples: int, confidence: float
) -> tuple[float, float]:
    if samples <= 0:
        raise ReliabilityError("WILSON_INTERVAL_NEEDS_SAMPLES")
    z = normal_inv_cdf(0.5 + 0.5 * confidence)
    proportion = failures / samples
    denominator = 1.0 + z * z / samples
    center = (proportion + z * z / (2.0 * samples)) / denominator
    half = (
        z
        * sqrt(proportion * (1.0 - proportion) / samples + z * z / (4.0 * samples * samples))
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def _finite_values(values: Sequence[float]) -> tuple[float, ...]:
    if not values:
        raise ReliabilityError("RELIABILITY_NEEDS_VALUES")
    for value in values:
        if not isfinite(value):
            raise ReliabilityError("RELIABILITY_NEEDS_FINITE_VALUES")
    return tuple(float(value) for value in values)


def _provenance(
    constraint: ReliabilityConstraint, inputs: Mapping[str, Any], assumptions: Sequence[str]
) -> Provenance:
    return Provenance.from_inputs(
        inputs={"constraint": constraint.canonical_payload(), **inputs},
        source=ResultSource.SURROGATE,
        model=SOFTWARE_NAME,
        model_version=SOFTWARE_VERSION,
        assumptions=tuple(assumptions),
    )


def monte_carlo_reliability(
    constraint: ReliabilityConstraint,
    values: Sequence[float],
    *,
    trusted: bool,
    basis: str = "aleatory",
) -> ReliabilityEstimate:
    """Bounded Monte Carlo reliability with a conservative Wilson bound."""
    finite = _finite_values(values)
    samples = len(finite)
    failures = sum(1 for value in finite if constraint.is_failure(value))
    probability = failures / samples
    lower, upper = _wilson_interval(failures, samples, constraint.confidence)
    reasons: list[str] = []
    if not trusted:
        reasons.append(f"fidelity is not trusted for reliability ({basis})")
        admissible = False
        passed = False
    else:
        admissible = True
        passed = upper <= constraint.target_probability_of_failure
        if not passed:
            reasons.append(
                f"failure probability upper bound {upper:.3g} exceeds target "
                f"{constraint.target_probability_of_failure:.3g}"
            )
    mean_response = sum(finite) / samples
    margin = constraint.margin(mean_response)
    provenance = _provenance(
        constraint,
        {"samples": samples, "failures": failures, "basis": basis, "trusted": trusted},
        ("bounded Monte Carlo exceedance count", "Wilson score interval"),
    )
    return ReliabilityEstimate(
        name=constraint.name,
        response=constraint.response,
        method=ReliabilityMethod.MONTE_CARLO.value,
        direction=constraint.direction.value,
        limit=constraint.limit,
        samples=samples,
        failures=failures,
        probability_of_failure=probability,
        probability_lower=lower,
        probability_upper=upper,
        reliability_index=reliability_index_from_failure_probability(probability),
        mean_response=mean_response,
        margin=margin,
        trusted=trusted,
        admissible=admissible,
        passed=passed,
        basis=basis,
        reasons=tuple(reasons),
        validity=Validity(
            passed=trusted,
            checks={"trusted_fidelity": trusted, "finite_responses": True},
            detail=basis,
        ),
        provenance=provenance,
    )


def first_order_reliability(
    constraint: ReliabilityConstraint,
    mean_vector: Mapping[str, float],
    gradient: Mapping[str, float],
    covariance: Mapping[str, Mapping[str, float]],
    *,
    trusted: bool,
    basis: str = "aleatory",
) -> ReliabilityEstimate:
    """Exact FORM reliability index for a linear limit state.

    ``response = sum(gradient[i] * X[i])``; failure is ``response > limit``
    (upper) or ``response < limit`` (lower). ``covariance`` is keyed by the
    same variable names; any variable with no gradient term contributes zero.
    """
    names = tuple(gradient)
    if not names:
        raise ReliabilityError("FORM_NEEDS_GRADIENT")
    mean_response = 0.0
    for name in names:
        if name not in mean_vector:
            raise ReliabilityError(f"FORM_MISSING_MEAN:{name}")
        mean_response += gradient[name] * mean_vector[name]
    variance = 0.0
    for left in names:
        for right in names:
            variance += (
                gradient[left]
                * gradient[right]
                * covariance.get(left, {}).get(right, 0.0)
            )
    if variance < -1e-12:
        raise ReliabilityError("FORM_NEGATIVE_LIMIT_STATE_VARIANCE")
    sigma = sqrt(max(variance, 0.0))
    adjusted_mean = (
        mean_response + constraint.margin_penalty
        if constraint.direction is LimitDirection.UPPER
        else mean_response - constraint.margin_penalty
    )
    mean_margin = (
        constraint.limit - adjusted_mean
        if constraint.direction is LimitDirection.UPPER
        else adjusted_mean - constraint.limit
    )
    if sigma == 0.0:
        probability = 1.0 if mean_margin < 0.0 else 0.0
        beta_value: float | None = None
    else:
        beta = mean_margin / sigma
        probability = normal_cdf(-beta)
        beta_value = beta
    reasons: list[str] = []
    if not trusted:
        reasons.append(f"fidelity is not trusted for reliability ({basis})")
        admissible = False
        passed = False
    else:
        admissible = True
        passed = probability <= constraint.target_probability_of_failure
        if not passed:
            reasons.append(
                f"first-order failure probability {probability:.3g} exceeds target "
                f"{constraint.target_probability_of_failure:.3g}"
            )
    provenance = _provenance(
        constraint,
        {
            "meanResponse": mean_response,
            "limitStateStd": sigma,
            "basis": basis,
            "trusted": trusted,
        },
        ("first-order reliability method over a linear limit state",),
    )
    return ReliabilityEstimate(
        name=constraint.name,
        response=constraint.response,
        method=ReliabilityMethod.FIRST_ORDER.value,
        direction=constraint.direction.value,
        limit=constraint.limit,
        samples=0,
        failures=-1,
        probability_of_failure=probability,
        probability_lower=probability,
        probability_upper=probability,
        reliability_index=beta_value,
        mean_response=mean_response,
        margin=constraint.margin(mean_response),
        trusted=trusted,
        admissible=admissible,
        passed=passed,
        basis=basis,
        reasons=tuple(reasons),
        validity=Validity(
            passed=trusted,
            checks={"trusted_fidelity": trusted, "linear_limit_state": True},
            detail=basis,
        ),
        provenance=provenance,
    )


def estimate_reliability(
    constraint: ReliabilityConstraint,
    values: Sequence[float],
    *,
    trusted: bool,
    basis: str = "aleatory",
) -> ReliabilityEstimate:
    """Monte-Carlo reliability estimate for a sampled response.

    FORM has no gradient here, so the ``first-order`` method fails closed: use
    :func:`first_order_reliability` directly when a linear limit state is
    declared.
    """
    if constraint.method is ReliabilityMethod.FIRST_ORDER:
        raise ReliabilityError(
            "FIRST_ORDER_NEEDS_LINEAR_LIMIT_STATE:call first_order_reliability"
        )
    return monte_carlo_reliability(constraint, values, trusted=trusted, basis=basis)
