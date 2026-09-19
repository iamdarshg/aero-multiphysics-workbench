"""Provenance, software identity, and validity receipts for internal-flow results.

Reuses the shared :class:`aeroworkbench_core.types.Provenance` (which already
carries the canonical input hash and the full solver identity required for a
native result) and the :class:`aeroworkbench_fluid_properties.SoftwareIdentity`
envelope so every result cites exactly which software produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

SOFTWARE_NAME = "aeroworkbench-internal-flow"
SOFTWARE_VERSION = "1.0.0"
SOFTWARE_IDENTITY = SoftwareIdentity(name=SOFTWARE_NAME, version=SOFTWARE_VERSION)


def analytical_provenance(
    model: str, inputs: dict[str, Any], *assumptions: str
) -> Provenance:
    """Analytical provenance whose input hash is over the canonical inputs."""
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        assumptions=assumptions,
        inputs=inputs,
    )


def native_provenance(
    *,
    model: str,
    solver_name: str,
    solver_version: str,
    run_id: str,
    inputs: dict[str, Any],
    assumptions: tuple[str, ...] = (),
) -> Provenance:
    """Native provenance; the core contract requires full solver identity."""
    return Provenance.from_inputs(
        source=ResultSource.NATIVE_SOLVER,
        model=model,
        model_version=SOFTWARE_VERSION,
        fidelity=FidelityLevel.TRANSIENT,
        assumptions=assumptions,
        solver_name=solver_name,
        solver_version=solver_version,
        run_id=run_id,
        inputs=inputs,
    )


@dataclass(frozen=True, slots=True)
class ResultValidity:
    """Per-check validity verdict carried on every network result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}
