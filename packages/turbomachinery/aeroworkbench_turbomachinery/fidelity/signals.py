"""Measured promotion signals and their mapping onto the shared fidelity planner.

Signals are measured, never assumed: objective rank/Pareto position, constraint
margin, correlation validity, model disagreement, mesh/timestep dependence,
convergence difficulty, choke/stall/surge proximity, tip-Mach/loading
proximity, thermal/stress margin, resonance proximity, and the cost budget.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from aeroworkbench_optimization import FidelitySignals

from ..canonical import content_digest

__all__ = ["PromotionSignals"]

_NUMERIC_FIELDS = (
    "objective_rank",
    "pareto_position",
    "constraint_margin",
    "correlation_validity",
    "model_disagreement",
    "mesh_dependence",
    "timestep_dependence",
    "convergence_difficulty",
    "choke_stall_surge_proximity",
    "tip_mach_loading_proximity",
    "thermal_stress_margin",
    "resonance_proximity",
    "cost_budget",
    "maturity",
    "sensitivity",
)


@dataclass(frozen=True, slots=True)
class PromotionSignals:
    """All measured escalation cues for one candidate at one rung."""

    objective_rank: float = 0.0
    pareto_position: float = 0.0
    constraint_margin: float = 1.0
    correlation_validity: float = 1.0
    model_disagreement: float = 0.0
    mesh_dependence: float = 0.0
    timestep_dependence: float = 0.0
    convergence_difficulty: float = 0.0
    choke_stall_surge_proximity: float = 1.0
    tip_mach_loading_proximity: float = 1.0
    thermal_stress_margin: float = 1.0
    resonance_proximity: float = 1.0
    cost_budget: float = 0.0
    maturity: float = 0.5
    sensitivity: float = 0.0
    required_capability: str | None = None
    validity_ok: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in _NUMERIC_FIELDS:
            value = float(getattr(self, name))
            if not isfinite(value):
                raise ValueError(f"NONFINITE_PROMOTION_SIGNAL:{name}")
        if self.cost_budget < 0:
            raise ValueError("PROMOTION_COST_BUDGET_NEGATIVE")
        if self.required_capability is not None and not self.required_capability.strip():
            raise ValueError("PROMOTION_REQUIRED_CAPABILITY_EMPTY")

    def to_fidelity_signals(self, current: str, question: str) -> FidelitySignals:
        """Adapt to the shared planner's signal contract without losing evidence."""
        return FidelitySignals(
            question=question,
            maturity=self.maturity,
            constraint_margin=self.constraint_margin,
            disagreement=self.model_disagreement,
            sensitivity=self.sensitivity,
            convergence_difficulty=self.convergence_difficulty,
            mesh_dependence=self.mesh_dependence,
            timestep_dependence=self.timestep_dependence,
            resonance_proximity=self.resonance_proximity,
            validity_ok=dict(self.validity_ok),
            cost_budget=self.cost_budget,
            required_capability=self.required_capability,
        )

    def extra_escalation_reasons(self) -> tuple[str, ...]:
        """Escalation cues the generic planner does not model directly."""
        reasons: list[str] = []
        if self.choke_stall_surge_proximity < 0.1:
            reasons.append(
                f"choke/stall/surge proximity {self.choke_stall_surge_proximity:.3g}"
            )
        if self.tip_mach_loading_proximity < 0.1:
            reasons.append(
                f"tip-Mach/loading proximity {self.tip_mach_loading_proximity:.3g}"
            )
        if self.thermal_stress_margin < 0.1:
            reasons.append(f"thermal/stress margin {self.thermal_stress_margin:.3g}")
        if self.correlation_validity < 0.9:
            reasons.append(f"correlation validity {self.correlation_validity:.3g}")
        return tuple(reasons)

    def canonical(self) -> dict[str, Any]:
        return {
            **{name: float(getattr(self, name)) for name in _NUMERIC_FIELDS},
            "requiredCapability": self.required_capability,
            "validityOk": {str(key): bool(value) for key, value in self.validity_ok.items()},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())
