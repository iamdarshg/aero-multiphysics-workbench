"""Fail-closed error taxonomy for uncertainty, reliability, and robust design.

Every failure mode is explicit: a malformed uncertain-variable contract, a
non-positive-definite correlation matrix, a sampling request beyond its hard
bound, a propagation that produced a non-finite or missing response, or a
requested trusted-fidelity capability that is unavailable. No path fabricates a
statistic or silently degrades a reliability claim.
"""

from __future__ import annotations

__all__ = [
    "CapabilityUnavailable",
    "PropagationError",
    "ReliabilityError",
    "RobustOptimizationError",
    "SamplingError",
    "UncertaintyError",
]


class UncertaintyError(ValueError):
    """Base class for uncertainty-contract failures."""


class SamplingError(UncertaintyError):
    """A sampling plan is malformed or exceeds its hard bound."""


class PropagationError(UncertaintyError):
    """Uncertainty propagation could not produce a valid response."""


class ReliabilityError(UncertaintyError):
    """A reliability estimate could not be produced honestly."""


class RobustOptimizationError(UncertaintyError):
    """A robust optimization request is malformed."""


class CapabilityUnavailable(UncertaintyError):
    """A required trusted-fidelity capability is not wired; fail closed."""
