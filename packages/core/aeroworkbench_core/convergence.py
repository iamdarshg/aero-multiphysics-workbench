from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models.common import analytical_provenance
from .types import Provenance


class ConvergenceCriteria(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    numerical_residual: float = Field(default=1e-5, ge=0)
    closure_fraction: float = Field(default=2e-3, ge=0)
    geometry_change_m: float = Field(default=1e-6, ge=0)
    thermal_change_k: float = Field(default=0.05, ge=0)
    electrical_change_fraction: float = Field(default=2e-3, ge=0)
    dynamic_frequency_change_fraction: float = Field(default=2e-3, ge=0)


class ConvergenceSnapshot(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    numerical_residuals: dict[str, float] = Field(default_factory=dict)
    mass_in_kg_s: float | None = Field(default=None, ge=0)
    mass_out_kg_s: float | None = Field(default=None, ge=0)
    energy_in_w: float | None = Field(default=None, ge=0)
    energy_out_w: float | None = Field(default=None, ge=0)
    force_applied_n: float | None = Field(default=None)
    force_reaction_n: float | None = Field(default=None)
    geometry_change_m: float | None = Field(default=None, ge=0)
    thermal_change_k: float | None = Field(default=None, ge=0)
    electrical_change_fraction: float | None = Field(default=None, ge=0)
    dynamic_frequency_change_fraction: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_residuals(self) -> ConvergenceSnapshot:
        for name, value in self.numerical_residuals.items():
            if not name:
                raise ValueError("numerical residual names must not be empty")
            if not math.isfinite(value) or value < 0:
                raise ValueError("numerical residuals must be finite and nonnegative")
        return self


class CategoryResult(BaseModel):
    passed: bool
    available: bool
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
    def _closure(in_value: float | None, out_value: float | None) -> tuple[float, bool]:
        if in_value is None or out_value is None:
            return 0.0, False
        return abs(in_value - out_value) / max(abs(in_value), abs(out_value), 1e-30), True

    @staticmethod
    def _change(value: float | None) -> tuple[float, bool]:
        return (0.0, False) if value is None else (value, True)

    def evaluate(self, snapshot: ConvergenceSnapshot) -> ConvergenceReport:
        residual = (
            max(snapshot.numerical_residuals.values())
            if snapshot.numerical_residuals
            else 0.0
        )
        values = {
            "numerical": (
                residual,
                bool(snapshot.numerical_residuals),
                self.criteria.numerical_residual,
                "numerical residual",
            ),
            "mass": (
                *self._closure(snapshot.mass_in_kg_s, snapshot.mass_out_kg_s),
                self.criteria.closure_fraction,
                "mass closure",
            ),
            "energy": (
                *self._closure(snapshot.energy_in_w, snapshot.energy_out_w),
                self.criteria.closure_fraction,
                "energy closure",
            ),
            "force": (
                *self._closure(snapshot.force_applied_n, snapshot.force_reaction_n),
                self.criteria.closure_fraction,
                "force closure",
            ),
            "geometry": (
                *self._change(snapshot.geometry_change_m),
                self.criteria.geometry_change_m,
                "geometry change",
            ),
            "thermal": (
                *self._change(snapshot.thermal_change_k),
                self.criteria.thermal_change_k,
                "thermal change",
            ),
            "electrical": (
                *self._change(snapshot.electrical_change_fraction),
                self.criteria.electrical_change_fraction,
                "electrical change",
            ),
            "dynamic": (
                *self._change(snapshot.dynamic_frequency_change_fraction),
                self.criteria.dynamic_frequency_change_fraction,
                "dynamic frequency change",
            ),
        }
        categories = {
            name: CategoryResult(
                passed=available and value <= limit,
                available=available,
                value=value,
                limit=limit,
                message=(
                    f"{label} missing"
                    if not available
                    else f"{label} {'within' if value <= limit else 'exceeds'} limit"
                ),
            )
            for name, (value, available, limit, label) in values.items()
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
