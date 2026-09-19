"""Analytical transport correlations with declared validity ranges.

Only models that are genuinely defined for a fluid are attached to it. When a
fluid has no transport model, transport queries fail closed rather than
returning a made-up value.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .errors import FluidValidationError
from .validity import ValidityRange


@dataclass(frozen=True, slots=True)
class SutherlandTransport:
    """Sutherland-law dynamic viscosity plus a constant Prandtl number.

    Thermal conductivity follows from ``k = mu * cp / Pr``. All values are SI.
    """

    reference_viscosity_pa_s: float
    reference_temperature_k: float
    sutherland_constant_k: float
    prandtl: float
    validity: ValidityRange

    def __post_init__(self) -> None:
        if not isfinite(self.reference_viscosity_pa_s) or self.reference_viscosity_pa_s <= 0:
            raise FluidValidationError("INVALID_SUTHERLAND_REFERENCE_VISCOSITY")
        if not isfinite(self.reference_temperature_k) or self.reference_temperature_k <= 0:
            raise FluidValidationError("INVALID_SUTHERLAND_REFERENCE_TEMPERATURE")
        if not isfinite(self.sutherland_constant_k) or self.sutherland_constant_k < 0:
            raise FluidValidationError("INVALID_SUTHERLAND_CONSTANT")
        if not isfinite(self.prandtl) or self.prandtl <= 0:
            raise FluidValidationError("INVALID_PRANDTL_NUMBER")
        if self.validity.quantity != "temperature" or self.validity.unit != "K":
            raise FluidValidationError("TRANSPORT_VALIDITY_MUST_BE_TEMPERATURE")

    def viscosity_pa_s(self, temperature_k: float) -> float:
        self.validity.require(temperature_k, label="temperature")
        reference = self.reference_temperature_k
        value = (
            self.reference_viscosity_pa_s
            * (temperature_k / reference) ** 1.5
            * (reference + self.sutherland_constant_k)
            / (temperature_k + self.sutherland_constant_k)
        )
        return float(value)

    def conductivity_w_m_k(self, temperature_k: float, cp_j_kg_k: float) -> float:
        return self.viscosity_pa_s(temperature_k) * cp_j_kg_k / self.prandtl

    def canonical(self) -> dict[str, object]:
        return {
            "model": "sutherland",
            "referenceViscosityPaS": self.reference_viscosity_pa_s,
            "referenceTemperatureK": self.reference_temperature_k,
            "sutherlandConstantK": self.sutherland_constant_k,
            "prandtl": self.prandtl,
            "validity": self.validity.canonical(),
        }
