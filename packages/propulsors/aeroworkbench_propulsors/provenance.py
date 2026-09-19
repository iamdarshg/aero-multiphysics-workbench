"""Provenance construction for generic propulsor results.

Every engineering output records source, model identity/version, fidelity, an
input hash, and assumptions through the shared core provenance contract. A
native result requires explicit solver identity and a run identifier, so a
native result can never be silently relabelled analytical; a screening result
never claims native fidelity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-propulsors"
SOFTWARE_VERSION = "1.0.0"


def _assumptions(assumptions: Sequence[str]) -> tuple[str, ...]:
    return tuple(assumptions)


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a closed-form propulsor screening model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=_assumptions(assumptions),
    )


def reduced_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a reduced/surrogate propulsor model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.SURROGATE,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=_assumptions(assumptions),
    )


def native_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    solver_name: str,
    solver_version: str,
    run_id: str,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a native engine result; identity is mandatory."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        assumptions=_assumptions(assumptions),
    )


__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "analytical_provenance",
    "native_provenance",
    "reduced_provenance",
]
