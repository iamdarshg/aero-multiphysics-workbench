"""Fail-closed error taxonomy for generic tolerancing analysis.

Every failure mode is explicit: a malformed tolerance contract, a stack-up that
cannot be assembled from typed quantities, an unusable balance contract, an
assembly rule that cannot be evaluated, or a native capability that is not
wired. No path ever fabricates a numerical result.
"""

from __future__ import annotations

__all__ = [
    "AssemblyError",
    "BalanceError",
    "CapabilityUnavailable",
    "StackupError",
    "ToleranceContractError",
    "TolerancingError",
    "YieldError",
]


class TolerancingError(ValueError):
    """Base class for generic tolerancing failures."""


class ToleranceContractError(TolerancingError):
    """A tolerance callout or contract is structurally invalid."""


class StackupError(TolerancingError):
    """A tolerance stack-up is malformed or cannot be evaluated."""


class BalanceError(TolerancingError):
    """A balance or mass-property contract is malformed."""


class AssemblyError(TolerancingError):
    """An assembly constraint is malformed or cannot be evaluated."""


class YieldError(TolerancingError):
    """A yield/robustness estimate could not be produced."""


class CapabilityUnavailable(TolerancingError):
    """A requested native capability is not wired; fail closed."""
