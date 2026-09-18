"""Electrical propulsion and generic rotor-dynamics contracts.

The legacy Campbell/`assess_resonance` helpers are retained for compatibility.
New generic rotordynamics work uses the canonical rotating-assembly model,
participant-declared forcing spectra, and canonical benchmarks exported here.
"""

from .benchmarks import BENCHMARK_NAMES, benchmark_inputs, benchmark_model
from .forcings import (
    ForcingAssessment,
    ForcingLine,
    ForcingMargin,
    ForcingSpecError,
    assess_forcing_separation,
    normalize_forcing_lines,
)
from .resonance import (
    CampbellPoint,
    ResonanceDecision,
    assess_resonance,
    build_campbell,
)
from .rotor_model import (
    ALUMINIUM,
    ANALYSES,
    STEEL,
    BearingSpec,
    DiskSpec,
    MaterialSpec,
    RotorModel,
    RotorModelError,
    ShaftSegment,
    UnbalanceSpec,
    normalize_rotor_model,
)

__all__ = [
    "ALUMINIUM",
    "ANALYSES",
    "BENCHMARK_NAMES",
    "BearingSpec",
    "CampbellPoint",
    "DiskSpec",
    "ForcingAssessment",
    "ForcingLine",
    "ForcingMargin",
    "ForcingSpecError",
    "MaterialSpec",
    "ResonanceDecision",
    "RotorModel",
    "RotorModelError",
    "STEEL",
    "ShaftSegment",
    "UnbalanceSpec",
    "assess_forcing_separation",
    "assess_resonance",
    "benchmark_inputs",
    "benchmark_model",
    "build_campbell",
    "normalize_forcing_lines",
    "normalize_rotor_model",
]
