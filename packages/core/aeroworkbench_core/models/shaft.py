from __future__ import annotations

import math

from pydantic import Field

from aeroworkbench_core.types import Provenance

from .common import AnalyticalModel, analytical_provenance


class ShaftInput(AnalyticalModel):
    length_m: float = Field(gt=0)
    diameter_m: float = Field(gt=0)
    elastic_modulus_pa: float = Field(gt=0)
    density_kg_m3: float = Field(gt=0)
    speed_rpm: float = Field(ge=0)


class ShaftResult(AnalyticalModel):
    first_bending_frequency_hz: float
    rotational_frequency_hz: float
    separation_margin_fraction: float
    provenance: Provenance


def evaluate_shaft(inputs: ShaftInput) -> ShaftResult:
    area = math.pi * inputs.diameter_m**2 / 4
    inertia = math.pi * inputs.diameter_m**4 / 64
    bending = (
        math.pi
        / 2
        * math.sqrt(
            inputs.elastic_modulus_pa * inertia / (inputs.density_kg_m3 * area * inputs.length_m**4)
        )
    )
    rotational = inputs.speed_rpm / 60
    return ShaftResult(
        first_bending_frequency_hz=bending,
        rotational_frequency_hz=rotational,
        separation_margin_fraction=abs(bending - rotational) / bending,
        provenance=analytical_provenance(
            "simply-supported-euler-bernoulli-shaft",
            inputs.model_dump(),
            "uniform solid shaft",
            "bearing and gyroscopic effects omitted",
        ),
    )
