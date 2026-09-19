"""Typed probability distributions with deterministic inverse-CDF sampling.

Distributions are *declared data*: a kind plus finite parameters, no hidden
state. Sampling is expressed as an inverse CDF (``ppf``) so a caller can drive
it from an independent unit-hypercube draw. That extra seam is what makes
common-random-number reproducibility and Gaussian-copula correlation possible
without re-parameterizing each distribution.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import erf, exp, isfinite, log, sqrt
from typing import Any

from .errors import UncertaintyError

__all__ = [
    "Distribution",
    "DistributionKind",
    "normal_cdf",
    "normal_inv_cdf",
]

_SQRT_TWO = sqrt(2.0)

# Acklam's rational approximation for the standard normal inverse CDF.
_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def normal_cdf(z: float) -> float:
    """Standard normal cumulative distribution function."""
    if not isfinite(z):
        raise UncertaintyError("NORMAL_CDF_NEEDS_FINITE_INPUT")
    return 0.5 * (1.0 + erf(z / _SQRT_TWO))


def normal_inv_cdf(p: float) -> float:
    """Standard normal inverse CDF (Acklam); exact to ~1e-9 over the tails."""
    if not isfinite(p) or p < 0.0 or p > 1.0:
        raise UncertaintyError("NORMAL_PPF_DOMAIN")
    if p == 0.0:
        return -math.inf
    if p == 1.0:
        return math.inf
    if p < _P_LOW:
        q = sqrt(-2.0 * log(p))
        return (
            ((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]
        ) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    if p > _P_HIGH:
        q = sqrt(-2.0 * log(1.0 - p))
        return -(
            ((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]
        ) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    q = p - 0.5
    r = q * q
    return (
        (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q
    ) / (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)


class DistributionKind(StrEnum):
    """Supported declared distribution families."""

    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    DETERMINISTIC = "deterministic"
    EMPIRICAL = "empirical"


@dataclass(frozen=True, slots=True)
class Distribution:
    """A declared distribution over a single scalar.

    ``normal``/``lognormal`` take ``(mean, std)`` and ``(mu, sigma)`` for the
    underlying normal; ``uniform`` takes ``(low, high)``; ``triangular`` takes
    ``(low, mode, high)``; ``deterministic`` takes ``(value,)``; ``empirical``
    takes an ordered sample ``(x1, x2, ...)`` treated as equally likely.
    """

    kind: DistributionKind
    params: tuple[float, ...]

    def __post_init__(self) -> None:
        params = self.params
        for index, value in enumerate(params):
            if not isfinite(value):
                raise UncertaintyError(f"NONFINITE_DISTRIBUTION_PARAM:{self.kind.value}:{index}")
        if self.kind is DistributionKind.EMPIRICAL:
            if not params:
                raise UncertaintyError("EMPIRICAL_DISTRIBUTION_NEEDS_SAMPLES")
        elif self.kind is DistributionKind.DETERMINISTIC:
            if len(params) != 1:
                raise UncertaintyError("DETERMINISTIC_DISTRIBUTION_NEEDS_ONE_VALUE")
        elif self.kind is DistributionKind.NORMAL or self.kind is DistributionKind.LOGNORMAL:
            if len(params) != 2 or params[1] <= 0.0:
                raise UncertaintyError(f"INVALID_{self.kind.value.upper()}_PARAMS")
        elif self.kind is DistributionKind.UNIFORM:
            if len(params) != 2 or not params[0] < params[1]:
                raise UncertaintyError("INVALID_UNIFORM_PARAMS")
        elif self.kind is DistributionKind.TRIANGULAR:
            if len(params) != 3 or not params[0] < params[2] or not (
                params[0] <= params[1] <= params[2]
            ):
                raise UncertaintyError("INVALID_TRIANGULAR_PARAMS")
        else:  # pragma: no cover - StrEnum exhaustiveness guard
            raise UncertaintyError(f"UNKNOWN_DISTRIBUTION:{self.kind.value}")

    def mean(self) -> float:
        """Analytic mean of the declared distribution."""
        params = self.params
        if self.kind is DistributionKind.NORMAL:
            return params[0]
        if self.kind is DistributionKind.LOGNORMAL:
            return exp(params[0] + 0.5 * params[1] * params[1])
        if self.kind is DistributionKind.UNIFORM:
            return 0.5 * (params[0] + params[1])
        if self.kind is DistributionKind.TRIANGULAR:
            return (params[0] + params[1] + params[2]) / 3.0
        if self.kind is DistributionKind.DETERMINISTIC:
            return params[0]
        return sum(params) / len(params)

    def variance(self) -> float:
        """Analytic variance of the declared distribution."""
        params = self.params
        if self.kind is DistributionKind.NORMAL:
            return params[1] * params[1]
        if self.kind is DistributionKind.LOGNORMAL:
            sigma_sq = params[1] * params[1]
            return (exp(sigma_sq) - 1.0) * exp(2.0 * params[0] + sigma_sq)
        if self.kind is DistributionKind.UNIFORM:
            span = params[1] - params[0]
            return span * span / 12.0
        if self.kind is DistributionKind.TRIANGULAR:
            low, mode, high = params
            return (
                low * low
                + mode * mode
                + high * high
                - low * mode
                - low * high
                - mode * high
            ) / 18.0
        if self.kind is DistributionKind.DETERMINISTIC:
            return 0.0
        mean = self.mean()
        return sum((value - mean) ** 2 for value in params) / len(params)

    def std(self) -> float:
        """Analytic standard deviation of the declared distribution."""
        return sqrt(self.variance())

    def ppf(self, p: float) -> float:
        """Inverse CDF; ``p`` must lie in the closed unit interval."""
        if not isfinite(p) or p < 0.0 or p > 1.0:
            raise UncertaintyError("DISTRIBUTION_PPF_DOMAIN")
        params = self.params
        if self.kind is DistributionKind.NORMAL:
            return params[0] + params[1] * normal_inv_cdf(p)
        if self.kind is DistributionKind.LOGNORMAL:
            return exp(params[0] + params[1] * normal_inv_cdf(p))
        if self.kind is DistributionKind.UNIFORM:
            return params[0] + p * (params[1] - params[0])
        if self.kind is DistributionKind.TRIANGULAR:
            low, mode, high = params
            split = (mode - low) / (high - low)
            if p <= split:
                return low + sqrt(p * (high - low) * (mode - low))
            return high - sqrt((1.0 - p) * (high - low) * (high - mode))
        if self.kind is DistributionKind.DETERMINISTIC:
            return params[0]
        ordered = sorted(params)
        index = min(len(ordered) - 1, int(p * len(ordered)))
        return ordered[index]

    def canonical_payload(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "params": list(self.params)}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Distribution:
        raw_params = payload.get("params", ())
        if not isinstance(raw_params, Sequence):
            raise UncertaintyError("DISTRIBUTION_PARAMS_MUST_BE_SEQUENCE")
        return cls(
            kind=DistributionKind(str(payload["kind"])),
            params=tuple(float(value) for value in raw_params),
        )
