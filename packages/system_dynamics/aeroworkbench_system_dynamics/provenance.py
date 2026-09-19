"""Provenance construction for transient system-dynamics results.

Every engineering output records source, model identity/version, fidelity,
input hash, and assumptions through the shared core provenance contract. A
native transient coordinator result requires explicit solver identity and a run
identifier, so a native result can never be silently relabelled analytical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-system-dynamics"
SOFTWARE_VERSION = "1.0.0"


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a closed-form analytical integration/model output."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=tuple(assumptions),
    )


def reduced_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a reduced/surrogate transient model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.SURROGATE,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=tuple(assumptions),
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
    """Provenance for a native transient coordinator; identity is mandatory."""

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


__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "analytical_provenance",
    "native_provenance",
    "reduced_provenance",
]
