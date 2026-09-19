"""Provenance construction for experimental evidence.

Measurement data is ``benchmark`` in the shared core vocabulary, a digital
model result is ``analytical`` or ``surrogate``, and only an actually executed
external engine may carry ``native_solver`` (with mandatory solver identity and
run id). Every input hash is computed over the canonical inputs by the shared
core contract, so an analytical result can never be silently relabelled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .contracts import SOFTWARE_VERSION

__all__ = [
    "calibrated_provenance",
    "derived_measurement_provenance",
    "measurement_provenance",
    "native_solver_provenance",
    "simulation_provenance",
]


def measurement_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for physical (measured) test data; benchmark, never native."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.BENCHMARK,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        assumptions=tuple(assumptions),
    )


def derived_measurement_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a reproducible transform of measured data."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.BENCHMARK,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        assumptions=tuple(assumptions),
    )


def simulation_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    fidelity: FidelityLevel = FidelityLevel.ANALYTICAL,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a screening/analytical simulation result."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity,
        assumptions=tuple(assumptions),
    )


def calibrated_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a model calibrated against measured data (still surrogate)."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.SURROGATE,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=tuple(assumptions),
    )


def native_solver_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    solver_name: str,
    solver_version: str,
    run_id: str,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for an actually executed external engine; identity is mandatory."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        assumptions=tuple(assumptions),
    )
