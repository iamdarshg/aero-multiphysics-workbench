from __future__ import annotations

from pydantic import BaseModel, Field

from .models.common import analytical_provenance
from .types import Provenance


class ConvergenceCriteria(BaseModel):
    numerical_residual: float = 1e-5
    closure_fraction: float = 2e-3
    geometry_change_m: float = 1e-6
    thermal_change_k: float = 0.05
    electrical_change_fraction: float = 2e-3
    dynamic_frequency_change_fraction: float = 2e-3


class ConvergenceSnapshot(BaseModel):
    numerical_residuals: dict[str, float] = Field(default_factory=dict)
    mass_in_kg_s: float | None = None
    mass_out_kg_s: float | None = None
    energy_in_w: float | None = None
    energy_out_w: float | None = None
    force_applied_n: float | None = None
    force_reaction_n: float | None = None
    geometry_change_m: float | None = None
    thermal_change_k: float | None = None
    electrical_change_fraction: float | None = None
    dynamic_frequency_change_fraction: float | None = None


class CategoryResult(BaseModel):
    passed: bool
    value: float
    limit: float
    message: str


class ConvergenceReport(BaseModel):
    converged: bool
    categories: dict[str, CategoryResult]
    provenance: Provenance


class GlobalConvergenceManager:
    def __init__(self, criteria: ConvergenceCriteria) -> None:
        self.criteria = criteria

    @staticmethod
    def _closure(in_value: float | None, out_value: float | None) -> float:
        if in_value is None or out_value is None:
            return float("inf")
        return abs(in_value - out_value) / max(abs(in_value), abs(out_value), 1e-30)

    def evaluate(self, snapshot: ConvergenceSnapshot) -> ConvergenceReport:
        residual = max(snapshot.numerical_residuals.values(), default=float("inf"))
        values = {
            "numerical": (residual, self.criteria.numerical_residual, "numerical residual"),
            "mass": (
                self._closure(snapshot.mass_in_kg_s, snapshot.mass_out_kg_s),
                self.criteria.closure_fraction,
                "mass closure",
            ),
            "energy": (
                self._closure(snapshot.energy_in_w, snapshot.energy_out_w),
                self.criteria.closure_fraction,
                "energy closure",
            ),
            "force": (
                self._closure(snapshot.force_applied_n, snapshot.force_reaction_n),
                self.criteria.closure_fraction,
                "force closure",
            ),
            "geometry": (
                snapshot.geometry_change_m or 0.0,
                self.criteria.geometry_change_m,
                "geometry change",
            ),
            "thermal": (
                snapshot.thermal_change_k or 0.0,
                self.criteria.thermal_change_k,
                "thermal change",
            ),
            "electrical": (
                snapshot.electrical_change_fraction or 0.0,
                self.criteria.electrical_change_fraction,
                "electrical change",
            ),
            "dynamic": (
                snapshot.dynamic_frequency_change_fraction or 0.0,
                self.criteria.dynamic_frequency_change_fraction,
                "dynamic frequency change",
            ),
        }
        categories = {
            name: CategoryResult(
                passed=value <= limit,
                value=value,
                limit=limit,
                message=f"{label} {'within' if value <= limit else 'exceeds'} limit",
            )
            for name, (value, limit, label) in values.items()
        }
        return ConvergenceReport(
            converged=all(result.passed for result in categories.values()),
            categories=categories,
            provenance=analytical_provenance(
                "global-convergence-manager",
                {"criteria": self.criteria.model_dump(), "snapshot": snapshot.model_dump()},
                "missing required convergence measurements fail closed",
            ),
        )
