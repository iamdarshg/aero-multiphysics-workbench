from __future__ import annotations

from pydantic import Field, model_validator

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class GasTurbineInput(AnalyticalModel):
    mass_flow_kg_s: float = Field(gt=0)
    ambient_temperature_k: float = Field(gt=0)
    ambient_pressure_pa: float = Field(gt=0)
    compressor_pressure_ratio: float = Field(gt=1)
    compressor_efficiency: float = Field(gt=0, le=1)
    turbine_inlet_temperature_k: float = Field(gt=0)
    turbine_efficiency: float = Field(gt=0, le=1)
    combustor_efficiency: float = Field(gt=0, le=1)
    combustor_pressure_loss_fraction: float = Field(ge=0, lt=1)
    cp_j_kg_k: float = Field(gt=0)
    gamma: float = Field(gt=1)
    fuel_lower_heating_value_j_kg: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_cycle_ordering(self) -> GasTurbineInput:
        exponent = (self.gamma - 1) / self.gamma
        compressor_exit = self.ambient_temperature_k * self.compressor_pressure_ratio**exponent
        if self.turbine_inlet_temperature_k <= compressor_exit:
            raise ValueError("turbine inlet temperature must exceed compressor exit temperature")
        if self.compressor_pressure_ratio * (1 - self.combustor_pressure_loss_fraction) <= 1:
            raise ValueError("combustor pressure loss leaves no turbine expansion ratio")
        return self


class GasTurbineResult(AnalyticalModel):
    compressor_exit_temperature_k: float
    turbine_exit_temperature_k: float
    compressor_power_w: float
    turbine_power_w: float
    net_shaft_power_w: float
    fuel_flow_kg_s: float
    energy_closure_fraction: float
    provenance: Provenance
    limitations: tuple[str, ...]


def evaluate_gas_turbine(inputs: GasTurbineInput) -> GasTurbineResult:
    exponent = (inputs.gamma - 1) / inputs.gamma
    t2s = inputs.ambient_temperature_k * inputs.compressor_pressure_ratio**exponent
    t2 = (
        inputs.ambient_temperature_k
        + (t2s - inputs.ambient_temperature_k) / inputs.compressor_efficiency
    )
    compressor = inputs.mass_flow_kg_s * inputs.cp_j_kg_k * (t2 - inputs.ambient_temperature_k)
    fuel = (
        inputs.mass_flow_kg_s
        * inputs.cp_j_kg_k
        * (inputs.turbine_inlet_temperature_k - t2)
        / (inputs.combustor_efficiency * inputs.fuel_lower_heating_value_j_kg)
    )
    expansion_ratio = inputs.compressor_pressure_ratio * (
        1 - inputs.combustor_pressure_loss_fraction
    )
    t4s = inputs.turbine_inlet_temperature_k / expansion_ratio**exponent
    t4 = inputs.turbine_inlet_temperature_k - inputs.turbine_efficiency * (
        inputs.turbine_inlet_temperature_k - t4s
    )
    turbine = inputs.mass_flow_kg_s * inputs.cp_j_kg_k * (inputs.turbine_inlet_temperature_k - t4)
    net = turbine - compressor
    closure = abs(net - turbine + compressor) / max(abs(turbine), 1e-30)
    return GasTurbineResult(
        compressor_exit_temperature_k=t2,
        turbine_exit_temperature_k=t4,
        compressor_power_w=compressor,
        turbine_power_w=turbine,
        net_shaft_power_w=net,
        fuel_flow_kg_s=fuel,
        energy_closure_fraction=closure,
        provenance=analytical_provenance(
            "ideal-brayton-cycle", inputs.model_dump(), "constant specific heat and gamma"
        ),
        limitations=(
            "Analytical ideal Brayton cycle; not pyCycle or native solver output.",
            "No component maps, cooling bleed, or mechanical losses.",
        ),
    )
