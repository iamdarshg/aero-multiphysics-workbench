"""System-level penalties extracted from a solved secondary-flow network.

Leakage, cooling, and work-machine duties become named, unit-bearing scalars a
cycle or system analysis can consume directly, without the core network knowing
anything about the product it serves. The report keeps the mass/energy closure
of the underlying solve so a penalty can never be read from an unconverged
network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

from .errors import InternalFlowValidationError
from .kinds import BranchKind, NodeKind
from .network import NetworkResult
from .provenance import SOFTWARE_IDENTITY, ResultValidity, analytical_provenance

_MODEL_NAME = "aeroworkbench-internal-flow:system-penalties"


@dataclass(frozen=True, slots=True)
class SecondaryFlowReport:
    """Generic leakage/cooling/parasitic penalties plus closure of the solve."""

    leakage_mass_flow_kg_s: float
    leakage_fraction: float
    cooling_heat_w: float
    parasitic_power_w: float
    bleed_extraction_kg_s: float
    bleed_injection_kg_s: float
    supplied_mass_flow_kg_s: float
    mass_closure_kg_s: float
    energy_closure_w: float
    converged: bool
    source: ResultSource
    validity: ResultValidity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def penalty_payload(self) -> dict[str, float]:
        """Named quantities for downstream cycle/system analysis."""
        return {
            "leakageMassFlowKgS": self.leakage_mass_flow_kg_s,
            "leakageFraction": self.leakage_fraction,
            "coolingHeatW": self.cooling_heat_w,
            "parasiticPowerW": self.parasitic_power_w,
            "bleedExtractionKgS": self.bleed_extraction_kg_s,
            "bleedInjectionKgS": self.bleed_injection_kg_s,
        }

    def canonical(self) -> dict[str, Any]:
        return {
            "penalties": self.penalty_payload(),
            "suppliedMassFlowKgS": self.supplied_mass_flow_kg_s,
            "residuals": {
                "massKgS": self.mass_closure_kg_s,
                "energyW": self.energy_closure_w,
            },
            "converged": self.converged,
            "source": self.source.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def secondary_flow_report(result: NetworkResult) -> SecondaryFlowReport:
    """Aggregate leakage/cooling/work penalties and assert closure."""
    leakage = sum(
        abs(branch.mass_flow_kg_s)
        for branch in result.branches
        if branch.kind in (BranchKind.SEAL,)
    )
    cooling = sum(
        branch.heat_duty_w
        for branch in result.branches
        if branch.kind is BranchKind.HEAT_EXCHANGER
    )
    parasitic = sum(
        branch.shaft_power_w
        for branch in result.branches
        if branch.kind in (BranchKind.PUMP, BranchKind.FAN, BranchKind.COMPRESSOR)
    )
    supplied = 0.0
    extraction = 0.0
    injection = 0.0
    for node in result.nodes:
        if not node.is_boundary:
            continue
        if node.net_mass_flow_kg_s < 0.0:
            supplied += -node.net_mass_flow_kg_s
        if node.kind is NodeKind.BLEED_EXTRACTION:
            extraction += node.net_mass_flow_kg_s
        elif node.kind is NodeKind.BLEED_INJECTION:
            injection += -node.net_mass_flow_kg_s
    fraction = leakage / supplied if supplied > 0.0 else 0.0
    if not result.converged:
        raise InternalFlowValidationError("SYSTEM_PENALTIES_REQUIRE_CONVERGED_NETWORK")
    provenance = analytical_provenance(
        _MODEL_NAME,
        {
            "networkName": result.network_name,
            "inputsHash": result.provenance.inputs_hash,
            "leakageKgS": leakage,
            "coolingW": cooling,
            "parasiticW": parasitic,
        },
        "penalties aggregated from a converged steady network solve",
    )
    validity = ResultValidity(
        passed=result.converged,
        checks={
            "converged": result.converged,
            "mass_closure": abs(result.mass_residual_kg_s) <= 1e-6,
            "energy_closure": abs(result.energy_residual_w) <= 1e-3,
        },
        detail="system penalties read from a converged network",
    )
    return SecondaryFlowReport(
        leakage_mass_flow_kg_s=leakage,
        leakage_fraction=fraction,
        cooling_heat_w=cooling,
        parasitic_power_w=parasitic,
        bleed_extraction_kg_s=extraction,
        bleed_injection_kg_s=injection,
        supplied_mass_flow_kg_s=supplied,
        mass_closure_kg_s=result.mass_residual_kg_s,
        energy_closure_w=result.energy_residual_w,
        converged=result.converged,
        source=ResultSource.ANALYTICAL,
        validity=validity,
        provenance=provenance,
    )


__all__ = ["SecondaryFlowReport", "secondary_flow_report"]
