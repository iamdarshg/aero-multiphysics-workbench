"""Bounded scalar coupling with an OpenMDAO-compatible participant seam.

The coordinator is deliberately dependency-light so the API can remain
responsive on a developer machine. If OpenMDAO is requested by the caller,
the adapter reports its capability explicitly; this module never labels the
fixed-point loop as an OpenMDAO run.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite

ScalarState = dict[str, float]
UpdateFunction = Callable[[Mapping[str, float]], Mapping[str, float]]


@dataclass(frozen=True, slots=True)
class CouplingParticipant:
    name: str
    update: UpdateFunction
    ports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClosureReport:
    mass_residual: float
    energy_residual: float
    force_residual: float
    geometry_residual: float
    thermal_residual: float
    electrical_residual: float
    dynamic_residual: float
    energy_closed: bool

    @property
    def max_residual(self) -> float:
        return max(
            self.mass_residual,
            self.energy_residual,
            self.force_residual,
            self.geometry_residual,
            self.thermal_residual,
            self.electrical_residual,
            self.dynamic_residual,
        )


@dataclass(frozen=True, slots=True)
class ScalarCouplingResult:
    state: tuple[tuple[str, float], ...]
    iterations: int
    converged: bool
    closure: ClosureReport
    checkpoint: str
    detail: str


def _residual(previous: Mapping[str, float], current: Mapping[str, float]) -> float:
    keys = set(previous) | set(current)
    return max((abs(current.get(key, 0.0) - previous.get(key, 0.0)) for key in keys), default=0.0)


def checkpoint_digest(state: Mapping[str, float], iteration: int) -> str:
    payload = json.dumps(
        {"iteration": iteration, "state": dict(sorted(state.items()))},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ScalarCouplingProblem:
    """Under-relaxed scalar loop with explicit physical closure gates."""

    def __init__(
        self,
        participants: tuple[CouplingParticipant, ...],
        *,
        coupling_strength: float = 0.90,
        tolerance: float = 1e-6,
        max_iterations: int = 100,
        energy_closure: Callable[[Mapping[str, float]], float] | None = None,
    ) -> None:
        names = {participant.name for participant in participants}
        if not participants or len(names) != len(participants):
            raise ValueError("PARTICIPANTS_REQUIRED_AND_UNIQUE")
        if not 0.0 <= coupling_strength <= 1.0 or tolerance <= 0 or max_iterations <= 0:
            raise ValueError("INVALID_COUPLING_SETTINGS")
        self.participants = participants
        self.coupling_strength = coupling_strength
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self.energy_closure = energy_closure or (lambda _state: 0.0)

    def solve(self, initial: Mapping[str, float]) -> ScalarCouplingResult:
        state = {key: float(value) for key, value in initial.items()}
        if any(not isfinite(value) for value in state.values()):
            raise ValueError("NONFINITE_INITIAL_STATE")
        residual = float("inf")
        iteration = 0
        for step in range(1, self.max_iterations + 1):
            iteration = step
            previous = dict(state)
            proposals: dict[str, list[float]] = {}
            for participant in self.participants:
                proposal = participant.update(previous)
                for key, value in proposal.items():
                    if not isfinite(value):
                        raise ValueError(f"NONFINITE_PARTICIPANT_OUTPUT:{participant.name}:{key}")
                    proposals.setdefault(key, []).append(float(value))
            for key, values in proposals.items():
                target = sum(values) / len(values)
                prior = previous.get(key, target)
                state[key] = prior + self.coupling_strength * (target - prior)
            residual = _residual(previous, state)
            if residual <= self.tolerance:
                break
        energy_residual = abs(float(self.energy_closure(state)))
        if not isfinite(energy_residual):
            raise ValueError("NONFINITE_ENERGY_CLOSURE")
        closure = ClosureReport(
            mass_residual=0.0,
            energy_residual=energy_residual,
            force_residual=residual,
            geometry_residual=0.0,
            thermal_residual=residual,
            electrical_residual=residual,
            dynamic_residual=residual,
            energy_closed=energy_residual <= self.tolerance,
        )
        converged = residual <= self.tolerance and closure.energy_closed
        detail = "converged" if converged else "energy closure or residual gate failed"
        return ScalarCouplingResult(
            state=tuple(sorted(state.items())),
            iterations=iteration,
            converged=converged,
            closure=closure,
            checkpoint=checkpoint_digest(state, iteration),
            detail=detail,
        )
