"""Provenance construction for environmental-degradation results.

Envelope, empirical, and geometry-change results are analytical/surrogate in
nature; native results require explicit solver identity and a run identifier so
a native result can never be silently relabelled. Every input hash is computed
over the canonical inputs by the shared core contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

from .contracts import SOFTWARE_VERSION


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a closed-form / declared envelope model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=tuple(assumptions),
    )


def empirical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a calibrated empirical correlation (still not native)."""

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
    """Provenance for a native engine result; identity is mandatory."""

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
    "analytical_provenance",
    "empirical_provenance",
    "native_provenance",
]
