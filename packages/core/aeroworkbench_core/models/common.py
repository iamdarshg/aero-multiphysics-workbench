from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource


class AnalyticalModel(BaseModel):
    """Base contract rejecting non-finite values at analytical boundaries."""

    model_config = ConfigDict(allow_inf_nan=False)


def analytical_provenance(model: str, inputs: dict[str, Any], *assumptions: str) -> Provenance:
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=model,
        model_version="1.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs=inputs,
        assumptions=assumptions,
    )
