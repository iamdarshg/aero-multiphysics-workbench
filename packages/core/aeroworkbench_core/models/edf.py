from __future__ import annotations

import math

from pydantic import Field, model_validator

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class EDFInput(AnalyticalModel):
    fan_diameter_m: float = Field(gt=0)
    hub_diameter_m: float = Field(ge=0)
    shaft_power_w: float = Field(gt=0)
    fan_efficiency: float = Field(gt=0, le=1)
    air_density_kg_m3: float = Field(gt=0)
    freestream_velocity_m_s: float = Field(ge=0)
    speed_rpm: float = Field(gt=0)
    blade_count: int = Field(gt=0)
    stator_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_annulus(self) -> EDFInput:
        if self.hub_diameter_m >= self.fan_diameter_m:
            raise ValueError("hub diameter must be smaller than fan diameter")
        return self


class EDFResult(AnalyticalModel):
    thrust_n: float
    fluid_power_w: float
    induced_velocity_m_s: float
    mass_flow_kg_s: float
    blade_passing_frequency_hz: float
    provenance: Provenance


def evaluate_edf(inputs: EDFInput) -> EDFResult:
    area = math.pi * (inputs.fan_diameter_m**2 - inputs.hub_diameter_m**2) / 4
    fluid_power = inputs.shaft_power_w * inputs.fan_efficiency
    if inputs.freestream_velocity_m_s == 0:
        induced_velocity = (fluid_power / (2 * inputs.air_density_kg_m3 * area)) ** (1 / 3)
        mass_flow = inputs.air_density_kg_m3 * area * induced_velocity
        thrust = 2 * mass_flow * induced_velocity
    else:
        # Solve P = 2 rho A vi (V + vi)^2 by monotonic bisection.
        lo, hi = 0.0, max(1.0, (fluid_power / (2 * inputs.air_density_kg_m3 * area)) ** (1 / 3))
        while (
            2 * inputs.air_density_kg_m3 * area * hi * (inputs.freestream_velocity_m_s + hi) ** 2
            < fluid_power
        ):
            hi *= 2
        for _ in range(80):
            mid = (lo + hi) / 2
            power = (
                2
                * inputs.air_density_kg_m3
                * area
                * mid
                * (inputs.freestream_velocity_m_s + mid) ** 2
            )
            lo, hi = (mid, hi) if power < fluid_power else (lo, mid)
        induced_velocity = (lo + hi) / 2
        mass_flow = (
            inputs.air_density_kg_m3 * area * (inputs.freestream_velocity_m_s + induced_velocity)
        )
        thrust = 2 * mass_flow * induced_velocity
    return EDFResult(
        thrust_n=thrust,
        fluid_power_w=fluid_power,
        induced_velocity_m_s=induced_velocity,
        mass_flow_kg_s=mass_flow,
        blade_passing_frequency_hz=inputs.speed_rpm / 60 * inputs.blade_count,
        provenance=analytical_provenance(
            "ideal-actuator-disk",
            inputs.model_dump(),
            "uniform incompressible annular disk loading",
            "no duct, tip-loss, swirl, or compressibility correction",
        ),
    )
