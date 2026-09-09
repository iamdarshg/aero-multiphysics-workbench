from __future__ import annotations

import math

from pydantic import Field

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class ThermalInput(AnalyticalModel):
    initial_temperature_k: float = Field(gt=0)
    ambient_temperature_k: float = Field(gt=0)
    heat_generation_w: float = Field(ge=0)
    thermal_resistance_k_per_w: float = Field(gt=0)
    thermal_capacitance_j_per_k: float = Field(gt=0)
    duration_s: float = Field(ge=0)


class ThermalResult(AnalyticalModel):
    final_temperature_k: float
    steady_state_temperature_k: float
    time_constant_s: float
    provenance: Provenance


def evaluate_thermal(inputs: ThermalInput) -> ThermalResult:
    steady = (
        inputs.ambient_temperature_k + inputs.heat_generation_w * inputs.thermal_resistance_k_per_w
    )
    tau = inputs.thermal_resistance_k_per_w * inputs.thermal_capacitance_j_per_k
    final = steady + (inputs.initial_temperature_k - steady) * math.exp(-inputs.duration_s / tau)
    return ThermalResult(
        final_temperature_k=final,
        steady_state_temperature_k=steady,
        time_constant_s=tau,
        provenance=analytical_provenance(
            "lumped-thermal-rc",
            inputs.model_dump(),
            "constant heat generation and ambient temperature",
        ),
    )
