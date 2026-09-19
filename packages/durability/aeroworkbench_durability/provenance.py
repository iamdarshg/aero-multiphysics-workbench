"""Provenance construction for durability results.

Every engineering output records source, model identity/version, fidelity,
input hash, and assumptions through the shared core provenance contract.
Catalog life curves are empirical benchmark data; reduced maps are surrogates;
native results require explicit solver identity and a run identifier, so a
native result can never be silently relabelled analytical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-durability"
SOFTWARE_VERSION = "1.0.0"

MINER_LIMITATIONS: tuple[str, ...] = (
    "Miner linear cumulative damage: no load-sequence interaction or retardation",
    "damage fractions are summed without interaction unless an interaction model is declared",
    "life is only as trustworthy as the sourced, validity-bounded material curves used",
)


def _assumptions(assumptions: Sequence[str]) -> tuple[str, ...]:
    return tuple(assumptions)


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a closed-form durability model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=_assumptions(assumptions),
    )


def catalog_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a sourced empirical life curve (benchmark data)."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.BENCHMARK,
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
    """Provenance for a reduced/surrogate durability model."""

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
    "MINER_LIMITATIONS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "analytical_provenance",
    "catalog_provenance",
    "native_provenance",
    "reduced_provenance",
]
