"""Analytical whole-aircraft envelope and installed-propulsion contracts."""

from .engine import (
    AircraftEnvelope,
    BoundaryRefinement,
    EnvelopeConstraints,
    FlightCondition,
    Region,
    evaluate_aircraft_envelope,
    refine_boundary,
    sweep_conditions,
)

__all__ = [
    "AircraftEnvelope",
    "BoundaryRefinement",
    "EnvelopeConstraints",
    "FlightCondition",
    "Region",
    "evaluate_aircraft_envelope",
    "refine_boundary",
    "sweep_conditions",
]
