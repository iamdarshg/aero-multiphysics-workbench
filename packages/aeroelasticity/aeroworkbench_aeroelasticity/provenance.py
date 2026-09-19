"""Provenance construction for aeroelastic results.

Every engineering output records source, model identity/version, fidelity, input
hash, assumptions, and the software identity of this package. Analytical
screening, reduced/surrogate maps, benchmark data, and native engine results are
distinguished; native provenance requires explicit solver identity and a run
identifier, so a native result can never be silently relabelled analytical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

SOFTWARE_IDENTITY = "aeroworkbench-aeroelasticity"
SOFTWARE_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class SoftwareIdentity:
    """The software that produced a result."""

    name: str = SOFTWARE_IDENTITY
    version: str = SOFTWARE_VERSION

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_SOFTWARE = SoftwareIdentity()


def _assumptions(assumptions: Sequence[str]) -> tuple[str, ...]:
    return tuple(assumptions)


def analytical_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
    fidelity: FidelityLevel = FidelityLevel.ANALYTICAL,
) -> Provenance:
    """Provenance for a closed-form/reduced screening aeroelastic model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=fidelity,
        assumptions=_assumptions(assumptions),
    )


def reduced_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for a reduced-order/surrogate aeroelastic model."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.SURROGATE,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.MRF,
        assumptions=_assumptions(assumptions),
    )


def benchmark_provenance(
    model: str,
    inputs: Mapping[str, Any],
    *,
    assumptions: Sequence[str] = (),
) -> Provenance:
    """Provenance for empirical/benchmark aeroelastic data."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.BENCHMARK,
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
    """Provenance for a native coupled-field result; identity is mandatory."""

    return Provenance.from_inputs(
        inputs=dict(inputs),
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.TRANSIENT,
        assumptions=_assumptions(assumptions),
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
    )


__all__ = [
    "DEFAULT_SOFTWARE",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "SoftwareIdentity",
    "analytical_provenance",
    "benchmark_provenance",
    "native_provenance",
    "reduced_provenance",
]
