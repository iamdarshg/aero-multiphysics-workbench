"""Species/composition transport closure for a solved fluid network.

Composition is a passive scalar once the mass flows are known: every internal
node is the mass-flow-weighted mixture of the streams entering it. This module
solves that linear transport by a deterministic fixed-point sweep and reports a
per-node closure residual, so species conservation is explicit alongside mass,
momentum, and energy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

from .errors import InternalFlowValidationError
from .network import BranchSpec, FluidNetwork, NetworkResult
from .provenance import SOFTWARE_IDENTITY, analytical_provenance

_MODEL_NAME = "aeroworkbench-internal-flow:composition"
_TOLERANCE = 1.0e-12


@dataclass(frozen=True, slots=True)
class NodeComposition:
    """Mixed mass fractions at one node with the closure residual."""

    node_id: str
    mass_fractions: tuple[tuple[str, float], ...]
    closure_residual: float
    source: ResultSource
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "massFractions": {name: value for name, value in self.mass_fractions},
            "closureResidual": self.closure_residual,
            "source": self.source.value,
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def _fractions(network: FluidNetwork, node_id: str) -> dict[str, float]:
    node = next(item for item in network.nodes if item.node_id == node_id)
    return dict(node.fluid.composition.mass_fractions())


def solve_composition(
    network: FluidNetwork, result: NetworkResult
) -> tuple[NodeComposition, ...]:
    """Return per-node mixed composition and an explicit closure residual."""
    if not result.converged:
        raise InternalFlowValidationError("COMPOSITION_REQUIRES_CONVERGED_FLOW")
    branch_flow = {branch.branch_id: branch.mass_flow_kg_s for branch in result.branches}
    specs = {branch.branch_id: branch for branch in network.branches}
    internal = [node.node_id for node in network.nodes if not node.is_boundary]
    species = sorted({name for node in network.nodes for name, _ in node.fluid.composition.species})
    mixture: dict[str, dict[str, float]] = {
        node_id: _fractions(network, node_id) for node_id in internal
    }
    for _ in range(200):
        change = 0.0
        for node_id in internal:
            inflow: dict[str, float] = {name: 0.0 for name in species}
            total = 0.0
            for branch in specs.values():
                flow = branch_flow[branch.branch_id]
                if branch.to_node == node_id:
                    upstream = branch.from_node
                elif branch.from_node == node_id:
                    flow = -flow
                    upstream = branch.to_node
                else:
                    continue
                if flow <= 0.0:
                    continue
                upstream_fractions = mixture.get(upstream, _fractions(network, upstream))
                for name in species:
                    inflow[name] += flow * upstream_fractions.get(name, 0.0)
                total += flow
            if total <= 0.0:
                continue
            updated = {name: inflow[name] / total for name in species}
            change = max(
                change,
                max(abs(updated[name] - mixture[node_id].get(name, 0.0)) for name in species),
            )
            mixture[node_id] = updated
        if change <= _TOLERANCE:
            break
    results: list[NodeComposition] = []
    for node_id in sorted({node.node_id for node in network.nodes}):
        fractions = mixture.get(node_id, _fractions(network, node_id))
        residual = _closure_residual(node_id, specs, branch_flow, mixture, fractions, species)
        provenance = analytical_provenance(
            _MODEL_NAME,
            {
                "network": network.name,
                "node": node_id,
                "massFractions": {name: fractions.get(name, 0.0) for name in species},
            },
            "passive-scalar mass-weighted mixing at steady state",
        )
        results.append(
            NodeComposition(
                node_id=node_id,
                mass_fractions=tuple((name, fractions.get(name, 0.0)) for name in species),
                closure_residual=residual,
                source=ResultSource.ANALYTICAL,
                provenance=provenance,
            )
        )
    return tuple(results)


def _closure_residual(
    node_id: str,
    specs: dict[str, BranchSpec],
    branch_flow: dict[str, float],
    mixture: dict[str, dict[str, float]],
    fractions: dict[str, float],
    species: list[str],
) -> float:
    if node_id not in mixture:
        return 0.0
    balance = {name: 0.0 for name in species}
    for spec in specs.values():
        flow = branch_flow[spec.branch_id]
        if spec.to_node == node_id:
            upstream = spec.from_node
        elif spec.from_node == node_id:
            flow = -flow
            upstream = spec.to_node
        else:
            continue
        if flow == 0.0:
            continue
        upstream_fractions = mixture.get(upstream, fractions)
        for name in species:
            balance[name] += flow * (
                upstream_fractions.get(name, 0.0) - fractions.get(name, 0.0)
            )
    return max((abs(value) for value in balance.values()), default=0.0)


__all__ = ["NodeComposition", "solve_composition"]
