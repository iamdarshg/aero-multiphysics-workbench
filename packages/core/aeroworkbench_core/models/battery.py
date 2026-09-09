from __future__ import annotations

from pydantic import Field

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class SixSBatteryInput(AnalyticalModel):
    cell_ocv_v: float = Field(gt=0)
    cell_resistance_ohm: float = Field(ge=0)
    current_a: float = Field(ge=0)
    contact_and_wiring_resistance_ohm: float = Field(ge=0)
    soc: float = Field(ge=0, le=1)
    temperature_k: float = Field(gt=0)


class SixSBatteryResult(AnalyticalModel):
    cell_count: int = 6
    open_circuit_voltage_v: float
    loaded_voltage_v: float
    heat_generation_w: float
    output_power_w: float
    chemical_power_w: float
    provenance: Provenance


def evaluate_six_s_battery(inputs: SixSBatteryInput) -> SixSBatteryResult:
    resistance = 6 * inputs.cell_resistance_ohm + inputs.contact_and_wiring_resistance_ohm
    ocv = 6 * inputs.cell_ocv_v
    loaded = ocv - inputs.current_a * resistance
    heat = inputs.current_a**2 * resistance
    output = loaded * inputs.current_a
    return SixSBatteryResult(
        open_circuit_voltage_v=ocv,
        loaded_voltage_v=loaded,
        heat_generation_w=heat,
        output_power_w=output,
        chemical_power_w=output + heat,
        provenance=analytical_provenance(
            "six-s-thevenin-pack",
            inputs.model_dump(),
            "fixed six-series-cell topology",
            "SOC is recorded but does not alter open-circuit voltage or resistance",
            "temperature is recorded but does not alter battery parameters",
        ),
    )
