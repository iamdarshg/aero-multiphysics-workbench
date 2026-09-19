"""Provenance construction for composite structural results.

Every engineering output records source, model identity/version, fidelity, input
hash, and assumptions through the shared core provenance contract. Composite
allowables sourced from a qualified program are benchmark data; a homogenized
surrogate is a surrogate; native structural results require explicit solver
identity and a run identifier, so a native result can never be silently
relabelled analytical and an analytical result can never masquerade as native.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource

__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "analytical_provenance",
    "benchmark_provenance",
    "native_provenance",
    "reduced_provenance",
]

SOFTWARE_IDENTITY = "aeroworkbench-composites"
SOFTWARE_VERSION = "1.0.0"


def _assumptions(assumptions: Sequence[str]) -> tuple[str, ...]:
    return tuple(assumptions)


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a closed-form composite model (CLT, failure criteria)."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        assumptions=_assumptions(assumptions),
    )


def benchmark_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for sourced experimental/allowable data."""

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
    """Provenance for a reduced-order/surrogate composite model."""

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
    """Provenance for a native structural result; identity is mandatory."""

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
