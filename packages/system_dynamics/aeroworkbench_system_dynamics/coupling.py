"""Solver coupling: exchange transient states through the shared core contracts.

The transient coordinator exchanges typed state with other physics participants
through the existing core coupling contracts: ``CouplingPolicy`` declares the
interface tolerance, iteration budget, exchange frequency, and whether a
dynamic solver is enabled; ``ComputationNode`` yields the deterministic cache
key for an exchange. A dynamic exchange requested while the policy has the
dynamic solver disabled fails closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.coupling import CouplingPolicy
from aeroworkbench_core.dag import ComputationNode
from aeroworkbench_core.types import Provenance

from .errors import CapabilityUnavailable, TransientValidationError
from .provenance import SOFTWARE_VERSION, analytical_provenance
from .units import require_unit
from .validity import Validity, finite


@dataclass(frozen=True, slots=True)
class CouplingPort:
    """One typed scalar interface port exchanged with another physics domain."""

    name: str
    unit: str
    direction: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise TransientValidationError("coupling port name is required")
        if self.direction not in {"in", "out"}:
            raise TransientValidationError(f"UNKNOWN_COUPLING_DIRECTION:{self.direction}")
        require_unit(self.unit)

    def canonical(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "direction": self.direction}


@dataclass(frozen=True, slots=True)
class CouplingExchange:
    """One state exchange with another participant, deterministically keyed."""

    coupling_id: str
    iteration: int
    values: tuple[tuple[str, float], ...]
    cache_key: str
    converged: bool
    residual: float
    validity: Validity
    provenance: Provenance

    def value(self, name: str) -> float:
        for key, value in self.values:
            if key == name:
                return value
        raise TransientValidationError(f"UNKNOWN_EXCHANGE_VALUE:{name}")

    def canonical(self) -> dict[str, Any]:
        return {
            "couplingId": self.coupling_id,
            "iteration": self.iteration,
            "values": {key: value for key, value in self.values},
            "cacheKey": self.cache_key,
            "converged": self.converged,
            "residual": self.residual,
            "validity": self.validity.as_dict(),
            "provenance": {
                "source": self.provenance.source.value,
                "model": self.provenance.model,
                "inputsHash": self.provenance.inputs_hash,
            },
        }


@dataclass(frozen=True, slots=True)
class SolverCoupling:
    """A declared transient coupling to other physics via core contracts."""

    coupling_id: str
    policy: CouplingPolicy
    ports: tuple[CouplingPort, ...]
    exchange_stride: int = 1

    def __post_init__(self) -> None:
        if not self.coupling_id.strip():
            raise TransientValidationError("coupling_id is required")
        if not self.ports:
            raise TransientValidationError("coupling needs at least one port")
        if self.exchange_stride <= 0:
            raise TransientValidationError("coupling.exchange_stride must be positive")
        names = [port.name for port in self.ports]
        if len(set(names)) != len(names):
            raise TransientValidationError("coupling ports must be unique")

    def output_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.ports if port.direction == "out")

    def input_names(self) -> tuple[str, ...]:
        return tuple(port.name for port in self.ports if port.direction == "in")

    def exchange(
        self,
        state: Mapping[str, float],
        *,
        iteration: int = 0,
        external: Mapping[str, float] | None = None,
    ) -> CouplingExchange:
        """Publish declared output states through a deterministic keyed exchange."""

        if not self.policy.dynamic_solver_enabled:
            raise CapabilityUnavailable(
                f"dynamic coupling disabled by policy:{self.coupling_id}"
            )
        values: list[tuple[str, float]] = []
        for port in self.ports:
            if port.name not in state:
                raise TransientValidationError(f"COUPLING_STATE_MISSING:{port.name}")
            values.append((port.name, finite(state[port.name], f"coupling.{port.name}")))
        node = ComputationNode(
            node_type="transient-state-exchange",
            inputs={
                "state": dict(sorted((name, value) for name, value in values)),
                "iteration": iteration,
                "external": dict(sorted((external or {}).items())),
            },
            dependencies={
                port.name: port.direction for port in self.ports
            },
            implementation_version=SOFTWARE_VERSION,
        )
        residual = 0.0
        for name in self.input_names():
            if external is not None and name in external:
                residual = max(residual, abs(float(external[name]) - state.get(name, 0.0)))
        converged = residual <= self.policy.interface_tolerance
        provenance = analytical_provenance(
            "transient-solver-coupling",
            {
                "couplingId": self.coupling_id,
                "iteration": iteration,
                "policyStrength": self.policy.strength,
                "tolerance": self.policy.interface_tolerance,
            },
        )
        validity = Validity(
            passed=converged,
            checks={"interface_converged": converged},
            detail="interface within tolerance" if converged else "interface residual high",
        )
        return CouplingExchange(
            coupling_id=self.coupling_id,
            iteration=iteration,
            values=tuple(values),
            cache_key=node.cache_key,
            converged=converged,
            residual=residual,
            validity=validity,
            provenance=provenance,
        )


__all__ = ["CouplingExchange", "CouplingPort", "SolverCoupling"]
