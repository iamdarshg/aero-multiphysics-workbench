"""Shared result contract: fidelity ladder, validity verdict, provenance.

Every turbulence result carries an explicit staged fidelity, a per-check
validity verdict, the software identity that produced it, and provenance with a
canonical input hash. The provenance reuses
:class:`aeroworkbench_core.types.Provenance`; the software identity reuses the
fluid-properties envelope so the whole platform cites software the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

SOFTWARE_NAME = "aeroworkbench-turbulence"
SOFTWARE_VERSION = "1.0.0"
SOFTWARE_IDENTITY = SoftwareIdentity(name=SOFTWARE_NAME, version=SOFTWARE_VERSION)


class TurbulenceFidelity(StrEnum):
    """Staged fidelity ladder for turbulence and transition modelling.

    ``LAMINAR`` resolves no turbulence. ``RANS`` is a fully turbulent steady
    closure. ``TRANSITION_RANS`` adds a transition-sensitive closure.
    ``HYBRID_RANS_LES`` blends modelled and resolved turbulence. ``LES`` and
    ``DNS`` resolve turbulence and require a native engine. A screening
    correlation is never presented as native.
    """

    LAMINAR = "laminar"
    RANS = "rans"
    TRANSITION_RANS = "transition_rans"
    HYBRID_RANS_LES = "hybrid_rans_les"
    LES = "les"
    DNS = "dns"

    def core_level(self) -> FidelityLevel:
        if self in (TurbulenceFidelity.HYBRID_RANS_LES, TurbulenceFidelity.LES):
            return FidelityLevel.TRANSIENT
        if self is TurbulenceFidelity.DNS:
            return FidelityLevel.TRANSIENT
        return FidelityLevel.ANALYTICAL


@dataclass(frozen=True, slots=True)
class Validity:
    """Per-check validity verdict carried on every result."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", dict(self.checks))

    def canonical(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "detail": self.detail}


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


__all__ = [
    "SOFTWARE_IDENTITY",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "TurbulenceFidelity",
    "Validity",
    "analytical_provenance",
    "native_provenance",
]
