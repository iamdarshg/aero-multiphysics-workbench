"""Ideal Brayton stays a cheap, explicitly-labelled screening fidelity.

The pre-existing ``aeroworkbench_core.models.gas_turbine`` ideal-Brayton
calculation is wrapped, never silently promoted: this module reports it at the
``ideal-brayton-screening`` fidelity with the analytical source, and records
that it is not a mapped component or a native/OpenMDAO cycle result.
"""

from __future__ import annotations

from dataclasses import dataclass

from aeroworkbench_core.models.gas_turbine import (
    GasTurbineInput,
    evaluate_gas_turbine,
)
from aeroworkbench_core.types import Provenance

BRAYTON_SCREENING_FIDELITY = "ideal-brayton-screening"


@dataclass(frozen=True, slots=True)
class BraytonScreening:
    """Labelled ideal-Brayton screening result."""

    fidelity: str
    source: str
    net_shaft_power_w: float
    compressor_power_w: float
    turbine_power_w: float
    thermal_efficiency: float
    fuel_flow_kg_s: float
    bookkeeping_residual_fraction: float
    provenance: Provenance
    limitations: tuple[str, ...]

    def canonical(self) -> dict[str, object]:
        return {
            "fidelity": self.fidelity,
            "source": self.source,
            "netShaftPowerW": self.net_shaft_power_w,
            "compressorPowerW": self.compressor_power_w,
            "turbinePowerW": self.turbine_power_w,
            "thermalEfficiency": self.thermal_efficiency,
            "fuelFlowKgS": self.fuel_flow_kg_s,
            "bookkeepingResidualFraction": self.bookkeeping_residual_fraction,
            "limitations": list(self.limitations),
        }


def ideal_brayton_screening(inputs: GasTurbineInput) -> BraytonScreening:
    """Evaluate the ideal Brayton cycle and label it as screening only."""

    result = evaluate_gas_turbine(inputs)
    heat_input = (
        result.fuel_flow_kg_s * inputs.fuel_lower_heating_value_j_kg
    )
    thermal_efficiency = (
        result.net_shaft_power_w / heat_input if heat_input > 0 else 0.0
    )
    return BraytonScreening(
        fidelity=BRAYTON_SCREENING_FIDELITY,
        source=result.provenance.source.value,
        net_shaft_power_w=result.net_shaft_power_w,
        compressor_power_w=result.compressor_power_w,
        turbine_power_w=result.turbine_power_w,
        thermal_efficiency=thermal_efficiency,
        fuel_flow_kg_s=result.fuel_flow_kg_s,
        bookkeeping_residual_fraction=result.bookkeeping_residual_fraction,
        provenance=result.provenance,
        limitations=result.limitations,
    )


__all__ = [
    "BRAYTON_SCREENING_FIDELITY",
    "BraytonScreening",
    "ideal_brayton_screening",
]
