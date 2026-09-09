from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CouplingPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    strength: float = Field(ge=0, le=1)
    interface_tolerance: float = Field(gt=0)
    max_coupling_iterations: int = Field(gt=0)
    field_exchange_frequency: int = Field(gt=0)
    geometry_feedback_interval: int = Field(gt=0)
    dynamic_solver_enabled: bool
    expert_overrides: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_strength(
        cls, strength: float, expert_overrides: dict[str, Any] | None = None
    ) -> CouplingPolicy:
        overrides = expert_overrides or {}
        allowed = {
            "interface_tolerance",
            "max_coupling_iterations",
            "field_exchange_frequency",
            "geometry_feedback_interval",
            "dynamic_solver_enabled",
        }
        unknown = set(overrides) - allowed
        if unknown:
            raise ValueError(f"Unknown expert override: {min(unknown)}")
        values: dict[str, Any] = {
            "interface_tolerance": 10 ** (-3 - 3 * strength),
            "max_coupling_iterations": round(10 + 90 * strength),
            "field_exchange_frequency": round(1 + 9 * strength),
            "geometry_feedback_interval": max(1, round(10 - 9 * strength)),
            "dynamic_solver_enabled": strength >= 0.75,
        }
        values.update(overrides)
        return cls(strength=strength, expert_overrides=dict(overrides), **values)
