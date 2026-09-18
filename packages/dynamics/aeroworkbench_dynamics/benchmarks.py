"""Canonical rotating-assembly benchmarks for generic rotordynamics.

Each benchmark is a raw participant input mapping that normalizes into a
canonical :class:`~aeroworkbench_dynamics.rotor_model.RotorModel`. They cover a
Jeffcott-style rotor, a flexible shaft on soft bearings, the short stiff shaft
that previously tripped a brittle beam-consistency gate, and a rotor with a
declared unbalance for forced response.
"""

from __future__ import annotations

from typing import Any

from .rotor_model import RotorModel, normalize_rotor_model

# Geometry/material/support definitions only; analysis and speed are added by
# benchmark_inputs so the same assembly can drive modal, Campbell, or forced runs.
_ASSEMBLIES: dict[str, dict[str, Any]] = {
    "jeffcott": {
        "shaft_length_m": 1.0,
        "shaft_diameter_m": 0.02,
        "n_elements": 8,
        "bearing_stiffness_n_m": 1.0e7,
        "bearing_damping_n_s_m": 50.0,
        "disk": {"position": 4.0, "outer_diameter_m": 0.12, "width_m": 0.03},
        "gyroscopic": True,
    },
    "flexible-shaft-bearings": {
        "shaft_length_m": 1.5,
        "shaft_diameter_m": 0.05,
        "n_elements": 6,
        "bearing_stiffness_n_m": 1.0e8,
        "bearing_damping_n_s_m": 1000.0,
        "gyroscopic": True,
    },
    "short-stiff-shaft": {
        "shaft_length_m": 0.15,
        "shaft_diameter_m": 0.008,
        "n_elements": 6,
        "bearing_stiffness_n_m": 5.0e6,
        "bearing_damping_n_s_m": 2000.0,
        "disk": {"position": 3.0, "outer_diameter_m": 0.05, "width_m": 0.02},
        "gyroscopic": True,
    },
    "unbalance-reference": {
        "shaft_length_m": 0.5,
        "shaft_diameter_m": 0.02,
        "n_elements": 6,
        "bearing_stiffness_n_m": 2.0e7,
        "bearing_damping_n_s_m": 200.0,
        "disk": {"position": 3.0, "outer_diameter_m": 0.08, "width_m": 0.02},
        "unbalance": {"node": 3, "magnitude_kg_m": 1.0e-4, "phase_deg": 0.0},
    },
}

_DEFAULT_SPEED_RPM = {
    "jeffcott": 6000.0,
    "flexible-shaft-bearings": 3000.0,
    "short-stiff-shaft": 42000.0,
    "unbalance-reference": 8000.0,
}

BENCHMARK_NAMES = tuple(_ASSEMBLIES)


def benchmark_inputs(
    name: str,
    *,
    analysis: str = "modal",
    speed_rpm: float | None = None,
    max_speed_rpm: float | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Return raw participant inputs for one canonical benchmark assembly."""

    try:
        inputs = dict(_ASSEMBLIES[name])
    except KeyError as exc:
        raise KeyError(f"UNKNOWN_ROTOR_BENCHMARK:{name}") from exc
    inputs.update(overrides)
    inputs["analysis"] = analysis
    default_speed = _DEFAULT_SPEED_RPM[name]
    if analysis == "campbell":
        inputs["max_speed_rpm"] = default_speed if max_speed_rpm is None else max_speed_rpm
    else:
        inputs["speed_rpm"] = default_speed if speed_rpm is None else speed_rpm
    return inputs


def benchmark_model(name: str, *, analysis: str = "modal") -> RotorModel:
    """Normalize one benchmark assembly into a canonical model."""

    return normalize_rotor_model(benchmark_inputs(name, analysis=analysis))
