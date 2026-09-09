from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResultSource(StrEnum):
    ANALYTICAL = "analytical"
    BENCHMARK = "benchmark"
    NATIVE_SOLVER = "native_solver"
    SURROGATE = "surrogate"


class FidelityLevel(StrEnum):
    ANALYTICAL = "analytical"
    MRF = "mrf"
    HARMONIC_RESPONSE = "harmonic_response"
    TRANSIENT = "transient"


_UNITS: dict[str, tuple[str, float]] = {
    "m": ("length", 1.0),
    "mm": ("length", 1e-3),
    "in": ("length", 0.0254),
    "W": ("power", 1.0),
    "kW": ("power", 1e3),
    "N": ("force", 1.0),
    "V": ("voltage", 1.0),
    "A": ("current", 1.0),
    "K": ("temperature", 1.0),
}


class Quantity(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: float = Field(allow_inf_nan=False)
    unit: str

    @model_validator(mode="after")
    def validate_unit(self) -> Quantity:
        if self.unit not in _UNITS:
            raise ValueError(f"Unsupported unit: {self.unit}")
        return self

    @property
    def dimension(self) -> str:
        return _UNITS[self.unit][0]

    @property
    def si_value(self) -> float:
        return self.value * _UNITS[self.unit][1]

    def to(self, unit: str) -> Quantity:
        if unit not in _UNITS:
            raise ValueError(f"Unsupported unit: {unit}")
        target_dimension, target_scale = _UNITS[unit]
        if target_dimension != self.dimension:
            raise ValueError(f"Cannot convert {self.dimension} to {target_dimension}")
        return Quantity(value=self.si_value / target_scale, unit=unit)


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: ResultSource
    model: str
    model_version: str = "1.0"
    fidelity: FidelityLevel = FidelityLevel.ANALYTICAL
    inputs_hash: str = Field(default="", pattern=r"^$|^[0-9a-f]{64}$")
    assumptions: tuple[str, ...] = ()
    solver_name: str | None = None
    solver_version: str | None = None
    run_id: str | None = None

    @model_validator(mode="after")
    def require_native_identity(self) -> Provenance:
        if self.source is ResultSource.NATIVE_SOLVER and not all(
            (self.solver_name, self.solver_version, self.run_id)
        ):
            raise ValueError(
                "Native solver provenance requires solver_name, solver_version, and run_id"
            )
        return self

    @classmethod
    def from_inputs(cls, *, inputs: dict[str, Any], **kwargs: Any) -> Provenance:
        payload = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(inputs_hash=hashlib.sha256(payload.encode()).hexdigest(), **kwargs)
