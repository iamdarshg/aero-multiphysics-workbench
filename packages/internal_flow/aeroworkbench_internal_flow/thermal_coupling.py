"""Thermal coupling of internal-flow heat exchangers to structures/solids.

Reuses the existing :class:`aeroworkbench_thermal.ThermalNetwork` interface
verbatim: an internal-flow heat-exchanger duty becomes a heat load on a solid
thermal node, and the solved wall temperatures come back as a first-class
result. A second helper evaluates an effectiveness-NTU duty against a wall
temperature so the fluid and structure sides can be reconciled.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity
from aeroworkbench_thermal import ThermalNetwork, ThermalResult

from .correlations import (
    COUNTERFLOW_HX,
    CorrelationRef,
    counterflow_effectiveness,
    heat_exchanger_duty,
)
from .errors import InternalFlowValidationError
from .kinds import BranchKind
from .network import NetworkResult
from .provenance import SOFTWARE_IDENTITY, ResultValidity, analytical_provenance

_MODEL_NAME = "aeroworkbench-internal-flow:structure-thermal-coupling"


@dataclass(frozen=True, slots=True)
class StructureThermalLink:
    """One heat-exchanger duty mapped onto a structural thermal node."""

    network_node_id: str
    thermal_node: str
    heat_duty_w: float
    source: str

    def __post_init__(self) -> None:
        if not self.network_node_id.strip() or not self.thermal_node.strip():
            raise InternalFlowValidationError("STRUCTURE_LINK_IDS_REQUIRED")
        if not isfinite(self.heat_duty_w) or self.heat_duty_w < 0.0:
            raise InternalFlowValidationError("STRUCTURE_LINK_HEAT_MUST_BE_NONNEGATIVE")
        if not self.source.strip():
            raise InternalFlowValidationError("STRUCTURE_LINK_SOURCE_REQUIRED")

    def canonical(self) -> dict[str, Any]:
        return {
            "networkNodeId": self.network_node_id,
            "thermalNode": self.thermal_node,
            "heatDutyW": self.heat_duty_w,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class StructureCouplingResult:
    """Solved wall temperatures and the heat loads that produced them."""

    thermal: ThermalResult
    links: tuple[StructureThermalLink, ...]
    wall_temperatures_c: tuple[tuple[str, float], ...]
    source: ResultSource
    validity: ResultValidity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "wallTemperaturesC": {name: value for name, value in self.wall_temperatures_c},
            "links": [link.canonical() for link in self.links],
            "thermalEnergyResidualW": self.thermal.energy_residual_w,
            "thermalConverged": self.thermal.converged,
            "source": self.source.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def structure_links_from_result(
    result: NetworkResult, mapping: dict[str, str]
) -> tuple[StructureThermalLink, ...]:
    """Map every heat-exchanger branch duty onto a structural thermal node."""
    links: list[StructureThermalLink] = []
    for branch in result.branches:
        if branch.kind is not BranchKind.HEAT_EXCHANGER:
            continue
        thermal_node = mapping.get(branch.branch_id)
        if thermal_node is None:
            continue
        links.append(
            StructureThermalLink(
                network_node_id=branch.branch_id,
                thermal_node=thermal_node,
                heat_duty_w=abs(branch.heat_duty_w),
                source=f"internal-flow-heat-exchanger:{branch.branch_id}",
            )
        )
    return tuple(links)


def apply_structure_heat_loads(
    *,
    thermal_network: ThermalNetwork,
    links: tuple[StructureThermalLink, ...],
    ambient_c: float = 25.0,
) -> StructureCouplingResult:
    """Inject heat-exchanger duties into the existing thermal network and solve."""
    if not links:
        raise InternalFlowValidationError("STRUCTURE_COUPLING_REQUIRES_LINKS")
    for link in links:
        thermal_network.add_load(link.thermal_node, link.heat_duty_w)
    thermal_result = thermal_network.solve()
    provenance = analytical_provenance(
        _MODEL_NAME,
        {
            "links": [link.canonical() for link in links],
            "ambientC": ambient_c,
        },
        "steady thermal network with fluid-side heat duties applied to solid nodes",
    )
    validity = ResultValidity(
        passed=thermal_result.converged,
        checks={
            "thermal_converged": thermal_result.converged,
            "energy_closure": isfinite(thermal_result.energy_residual_w),
        },
        detail="structure thermal network solved" if thermal_result.converged else "not converged",
    )
    return StructureCouplingResult(
        thermal=thermal_result,
        links=links,
        wall_temperatures_c=thermal_result.temperatures_c,
        source=ResultSource.ANALYTICAL,
        validity=validity,
        provenance=provenance,
    )


def heat_exchanger_duty_to_wall(
    *,
    ua_w_k: float,
    hot_capacity_rate_w_k: float,
    cold_capacity_rate_w_k: float,
    hot_inlet_k: float,
    cold_inlet_k: float,
) -> tuple[float, float, CorrelationRef]:
    """Effectiveness-NTU duty for a counter-flow exchanger against a wall stream."""
    if not isfinite(ua_w_k) or ua_w_k < 0.0:
        raise InternalFlowValidationError("UA_MUST_BE_NONNEGATIVE")
    capacity_min = min(hot_capacity_rate_w_k, cold_capacity_rate_w_k)
    if capacity_min <= 0.0:
        raise InternalFlowValidationError("CAPACITY_RATES_MUST_BE_POSITIVE")
    capacity_max = max(hot_capacity_rate_w_k, cold_capacity_rate_w_k)
    ntu = ua_w_k / capacity_min
    effectiveness = counterflow_effectiveness(ntu, capacity_min / capacity_max)
    duty = heat_exchanger_duty(
        effectiveness=effectiveness,
        hot_capacity_rate_w_k=capacity_min,
        hot_inlet_k=hot_inlet_k,
        cold_inlet_k=cold_inlet_k,
    )
    return duty, effectiveness, COUNTERFLOW_HX


__all__ = [
    "StructureCouplingResult",
    "StructureThermalLink",
    "apply_structure_heat_loads",
    "heat_exchanger_duty_to_wall",
    "structure_links_from_result",
]
