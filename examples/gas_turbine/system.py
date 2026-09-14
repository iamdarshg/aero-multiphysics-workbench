"""Run the bounded analytical gas-turbine workflow."""

from __future__ import annotations

from dataclasses import dataclass

from aeroworkbench_core.models.gas_turbine import (
    GasTurbineInput,
    GasTurbineResult,
    evaluate_gas_turbine,
)
from aeroworkbench_geometry import shape_hash

from .geometry import make_gas_turbine_geometry


@dataclass(frozen=True, slots=True)
class GasTurbineDemo:
    result: GasTurbineResult
    geometry_hash: str


def _demo_inputs(
    *,
    turbine_inlet_temperature_k: float = 1200.0,
) -> GasTurbineInput:
    return GasTurbineInput(
        mass_flow_kg_s=1.0,
        ambient_temperature_k=288.15,
        ambient_pressure_pa=101_325.0,
        compressor_pressure_ratio=4.0,
        compressor_efficiency=0.82,
        turbine_inlet_temperature_k=turbine_inlet_temperature_k,
        turbine_efficiency=0.86,
        combustor_efficiency=0.98,
        combustor_pressure_loss_fraction=0.04,
        cp_j_kg_k=1005.0,
        gamma=1.4,
        fuel_lower_heating_value_j_kg=43e6,
    )


def run_gas_turbine_demo_with(
    *,
    turbine_inlet_temperature_k: float = 1200.0,
) -> GasTurbineDemo:
    geometry = make_gas_turbine_geometry()
    result = evaluate_gas_turbine(
        _demo_inputs(turbine_inlet_temperature_k=turbine_inlet_temperature_k)
    )
    return GasTurbineDemo(result=result, geometry_hash=shape_hash(geometry))


def run_gas_turbine_demo() -> GasTurbineDemo:
    return run_gas_turbine_demo_with()
