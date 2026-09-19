"""Native CFD escalation seam: capability-gated and fail-closed.

The reduced-order network engine is analytical. When a case leaves correlation
validity, or a caller explicitly requests native fidelity, the request must go
to a wired native CFD engine. No such engine is wired in this repository, so an
absent backend raises :class:`InternalFlowCapabilityUnavailableError`; a caller
may inject a backend object (for a real engine or for a governed test double)
and receive a result with full native provenance. A screening correlation is
never relabelled as native.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_fluid_properties import SoftwareIdentity

from .errors import (
    InternalFlowCapabilityUnavailableError,
    InternalFlowValidationError,
)
from .network import FluidNetwork, NetworkResult
from .provenance import (
    SOFTWARE_IDENTITY,
    ResultValidity,
    native_provenance,
)

_MODEL_NAME = "aeroworkbench-internal-flow:native-cfd"
_KNOWN_EXECUTABLES = ("foamRun", "simpleFoam", "su2_CFD", "cfx5solve", "fluent")


@dataclass(frozen=True, slots=True)
class CfdCapability:
    """Observed availability of a native CFD executable (never optimistic)."""

    backend: str
    available: bool
    executable: str | None
    version: str | None
    detail: str

    def canonical(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "executable": self.executable,
            "version": self.version,
            "detail": self.detail,
        }


def probe_cfd_capability(executable: str = "foamRun") -> CfdCapability:
    """Probe for a native CFD executable without importing or running it."""
    resolved = shutil.which(executable)
    if resolved is None:
        return CfdCapability(
            backend=executable,
            available=False,
            executable=None,
            version=None,
            detail=f"{executable} is not installed; native CFD fidelity fails closed",
        )
    return CfdCapability(
        backend=executable,
        available=True,
        executable=resolved,
        version=None,
        detail=f"{executable} present at {resolved}",
    )


def probe_any_cfd_capability() -> CfdCapability:
    """Probe the known native CFD executables and return the first available."""
    for executable in _KNOWN_EXECUTABLES:
        capability = probe_cfd_capability(executable)
        if capability.available:
            return capability
    return probe_cfd_capability(_KNOWN_EXECUTABLES[0])


def require_cfd_capability(executable: str = "foamRun") -> CfdCapability:
    """Return the capability or fail closed with a typed error."""
    capability = probe_cfd_capability(executable)
    if not capability.available:
        raise InternalFlowCapabilityUnavailableError(
            f"NATIVE_CFD_UNAVAILABLE:{executable}:{capability.detail}"
        )
    return capability


@dataclass(frozen=True, slots=True)
class NativeCfdRequest:
    """Everything a native CFD engine needs to reproduce the network case."""

    network_name: str
    fidelity: str
    reason: str
    boundary_nodes: tuple[tuple[str, str, float, float], ...]
    branches: tuple[tuple[str, str, str], ...]
    payload: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        return {
            "networkName": self.network_name,
            "fidelity": self.fidelity,
            "reason": self.reason,
            "boundaryNodes": [list(item) for item in self.boundary_nodes],
            "branches": [list(item) for item in self.branches],
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class NativeCfdSolution:
    """Node and branch fields returned by a native CFD backend."""

    node_pressures_pa: dict[str, float]
    node_temperatures_k: dict[str, float]
    branch_mass_flows_kg_s: dict[str, float]
    detail: str = ""


@runtime_checkable
class NativeCfdBackend(Protocol):
    """The injectable native CFD backend contract."""

    backend_id: str
    software_version: str

    def solve(self, request: NativeCfdRequest) -> NativeCfdSolution: ...


@dataclass(frozen=True, slots=True)
class NativeCfdResult:
    """Native CFD outcome with full solver identity and provenance."""

    request: NativeCfdRequest
    solution: NativeCfdSolution
    solver_name: str
    solver_version: str
    run_id: str
    source: ResultSource
    validity: ResultValidity
    provenance: Provenance
    software: SoftwareIdentity = SOFTWARE_IDENTITY

    def canonical(self) -> dict[str, Any]:
        return {
            "request": self.request.canonical(),
            "nodePressuresPa": dict(sorted(self.solution.node_pressures_pa.items())),
            "nodeTemperaturesK": dict(sorted(self.solution.node_temperatures_k.items())),
            "branchMassFlowsKgS": dict(sorted(self.solution.branch_mass_flows_kg_s.items())),
            "detail": self.solution.detail,
            "source": self.source.value,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "solver": {
                "name": self.solver_name,
                "version": self.solver_version,
                "runId": self.run_id,
            },
            "software": self.software.canonical(),
        }


def build_native_request(
    network: FluidNetwork, *, fidelity: str = "native", reason: str
) -> NativeCfdRequest:
    boundary_nodes: list[tuple[str, str, float, float]] = []
    for node in network.nodes:
        if not node.is_boundary:
            continue
        pressure = node.pressure_pa
        temperature = node.temperature_k
        if pressure is None or temperature is None:
            raise InternalFlowValidationError(f"BOUNDARY_NODE_REQUIRES_P_T:{node.node_id}")
        boundary_nodes.append((node.node_id, node.kind.value, pressure, temperature))
    branches = tuple(
        (branch.branch_id, branch.from_node, branch.to_node) for branch in network.branches
    )
    return NativeCfdRequest(
        network_name=network.name,
        fidelity=fidelity,
        reason=reason,
        boundary_nodes=tuple(boundary_nodes),
        branches=branches,
        payload=network.network_payload(),
    )


def escalation_reasons(result: NetworkResult) -> tuple[str, ...]:
    """Why a solved network may need a native CFD escalation."""
    reasons: list[str] = []
    if not result.converged:
        reasons.append("NON_CONVERGED_REDUCED_ORDER_SOLVE")
    if result.fidelity == "reduced":
        reasons.append("REDUCED_ORDER_ROTATING_CAVITY_MODEL")
    return tuple(reasons)


def evaluate_native_cfd(
    network: FluidNetwork,
    *,
    backend: NativeCfdBackend | None = None,
    run_id: str | None = None,
    reason: str = "outside reduced-order correlation validity",
    fidelity: str = "native",
) -> NativeCfdResult:
    """Run the native CFD seam, or fail closed when no backend is wired."""
    if backend is None:
        capability = probe_any_cfd_capability()
        raise InternalFlowCapabilityUnavailableError(
            f"NATIVE_CFD_BACKEND_REQUIRED:{capability.detail}"
        )
    if run_id is None or not run_id.strip():
        raise InternalFlowValidationError("NATIVE_CFD_RUN_ID_REQUIRED")
    request = build_native_request(network, fidelity=fidelity, reason=reason)
    solution = backend.solve(request)
    missing_nodes = [
        node_id
        for node_id, _, _, _ in request.boundary_nodes
        if node_id not in solution.node_pressures_pa
    ]
    if missing_nodes:
        raise InternalFlowValidationError(
            f"NATIVE_CFD_SOLUTION_INCOMPLETE:{','.join(missing_nodes)}"
        )
    provenance = native_provenance(
        model=_MODEL_NAME,
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=run_id,
        inputs={"request": request.canonical()},
        assumptions=("native CFD engine solved the escalated network case",),
    )
    validity = ResultValidity(
        passed=True,
        checks={"solution_complete": True, "native_identity": True},
        detail=solution.detail or "native CFD solution accepted",
    )
    return NativeCfdResult(
        request=request,
        solution=solution,
        solver_name=backend.backend_id,
        solver_version=backend.software_version,
        run_id=run_id,
        source=ResultSource.NATIVE_SOLVER,
        validity=validity,
        provenance=provenance,
    )


def solve_native_or_fail(
    network: FluidNetwork,
    *,
    backend: NativeCfdBackend | None = None,
    run_id: str | None = None,
    reason: str = "native fidelity requested",
) -> NativeCfdResult:
    """Explicit fail-closed entry point used by a ``fidelity='native'`` request."""
    return evaluate_native_cfd(
        network, backend=backend, run_id=run_id, reason=reason, fidelity="native"
    )


__all__ = [
    "CfdCapability",
    "NativeCfdBackend",
    "NativeCfdRequest",
    "NativeCfdResult",
    "NativeCfdSolution",
    "build_native_request",
    "escalation_reasons",
    "evaluate_native_cfd",
    "probe_any_cfd_capability",
    "probe_cfd_capability",
    "require_cfd_capability",
    "solve_native_or_fail",
]
