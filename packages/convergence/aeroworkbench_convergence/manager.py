"""Named convergence gates shared by scalar and field workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConvergencePolicy:
    tolerance: float = 1e-6
    require_energy_closure: bool = True


class ConvergenceManager:
    def __init__(self, policy: ConvergencePolicy | None = None) -> None:
        policy = policy or ConvergencePolicy()
        if policy.tolerance <= 0:
            raise ValueError("INVALID_CONVERGENCE_TOLERANCE")
        self.policy = policy

    def accept(self, residuals: Mapping[str, float], *, energy_closed: bool) -> bool:
        if any(value < 0 or value != value for value in residuals.values()):
            return False
        if any(value > self.policy.tolerance for value in residuals.values()):
            return False
        return energy_closed or not self.policy.require_energy_closure
