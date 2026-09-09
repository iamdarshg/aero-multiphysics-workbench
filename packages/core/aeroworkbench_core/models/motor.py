from __future__ import annotations

import math

from pydantic import Field, model_validator

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class MotorInput(AnalyticalModel):
    kv_rpm_per_v: float = Field(gt=0)
    kt_nm_per_a: float | None = Field(default=None, gt=0)
    resistance_ohm: float = Field(ge=0)
    no_load_current_a: float = Field(ge=0)
    speed_rpm: float = Field(ge=0)
    torque_nm: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_constants(self) -> MotorInput:
        expected = 60 / (2 * math.pi * self.kv_rpm_per_v)
        if self.kt_nm_per_a is not None and not math.isclose(
            self.kt_nm_per_a, expected, rel_tol=0.02
        ):
            raise ValueError("Kv/Kt inconsistency exceeds 2%")
        return self


class MotorResult(AnalyticalModel):
    kt_nm_per_a: float
    current_a: float
    shaft_power_w: float
    copper_loss_w: float
    iron_loss_w: float
    input_power_w: float
    energy_closure_fraction: float
    provenance: Provenance


def evaluate_motor(inputs: MotorInput) -> MotorResult:
    kt = inputs.kt_nm_per_a or 60 / (2 * math.pi * inputs.kv_rpm_per_v)
    current = inputs.torque_nm / kt + inputs.no_load_current_a
    omega = inputs.speed_rpm * 2 * math.pi / 60
    shaft = inputs.torque_nm * omega
    copper = current * current * inputs.resistance_ohm
    iron = inputs.no_load_current_a * omega * kt
    input_power = shaft + copper + iron
    return MotorResult(
        kt_nm_per_a=kt,
        current_a=current,
        shaft_power_w=shaft,
        copper_loss_w=copper,
        iron_loss_w=iron,
        input_power_w=input_power,
        energy_closure_fraction=abs(input_power - shaft - copper - iron) / max(input_power, 1e-30),
        provenance=analytical_provenance(
            "dc-motor-equivalent-circuit",
            inputs.model_dump(),
            "Kt is derived from ideal SI Kv/Kt identity",
        ),
    )
