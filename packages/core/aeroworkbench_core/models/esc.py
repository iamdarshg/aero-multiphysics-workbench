from __future__ import annotations

from pydantic import Field

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class ESCInput(AnalyticalModel):
    voltage_v: float = Field(gt=0)
    current_a: float = Field(ge=0)
    duty_cycle: float = Field(gt=0, le=1)
    rds_on_ohm: float = Field(ge=0)
    switching_frequency_hz: float = Field(ge=0)
    rise_time_s: float = Field(ge=0)
    fall_time_s: float = Field(ge=0)


class ESCResult(AnalyticalModel):
    conduction_loss_w: float
    switching_loss_w: float
    total_loss_w: float
    output_power_w: float
    input_power_w: float
    provenance: Provenance


def evaluate_esc(inputs: ESCInput) -> ESCResult:
    conduction = inputs.current_a**2 * inputs.rds_on_ohm * inputs.duty_cycle
    switching = (
        0.5
        * inputs.voltage_v
        * inputs.current_a
        * (inputs.rise_time_s + inputs.fall_time_s)
        * inputs.switching_frequency_hz
    )
    output = inputs.voltage_v * inputs.current_a * inputs.duty_cycle
    total = conduction + switching
    return ESCResult(
        conduction_loss_w=conduction,
        switching_loss_w=switching,
        total_loss_w=total,
        output_power_w=output,
        input_power_w=output + total,
        provenance=analytical_provenance(
            "esc-loss-balance", inputs.model_dump(), "single equivalent conducting path"
        ),
    )
