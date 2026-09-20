"""Fail-closed error taxonomy for mission simulation and trajectory optimization.

Every failure mode is explicit: a structurally invalid mission contract, a
segment that exceeds its bounded transient, a failed reserve requirement, a
failed mass/fuel/energy closure, an inadmissible trajectory-optimization
request, a performance map query that would silently extrapolate, or a native
mission capability that is not actually wired.
"""

from __future__ import annotations

__all__ = [
    "CapabilityUnavailable",
    "ClosureError",
    "MissionContractError",
    "MissionError",
    "MissionOptimizationError",
    "MissionValidationError",
    "PerformanceRejected",
    "ReserveError",
]


class MissionError(ValueError):
    """Base class for mission-simulation contract and physics failures."""


class MissionContractError(MissionError):
    """A mission, segment, vehicle, reserve, or state contract is invalid."""


class MissionValidationError(MissionError):
    """A bounded propagation or envelope check failed closed."""


class ReserveError(MissionError):
    """A fuel/energy/time reserve requirement was not met at mission end."""


class ClosureError(MissionError):
    """A mass, fuel, energy, distance, or segment-continuity balance failed."""


class PerformanceRejected(MissionError):
    """A performance participant rejected a point or would silently extrapolate."""


class MissionOptimizationError(MissionError):
    """A trajectory-optimization request is inadmissible or yielded no feasible plan."""


class CapabilityUnavailable(MissionError):
    """A requested native mission capability is not wired; fail closed."""
