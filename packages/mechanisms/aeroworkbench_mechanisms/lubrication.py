"""Lubricant identity, viscosity-temperature behavior, and supply contract.

Lubricant flow is represented from typed physical data: identity, two
reference kinematic viscosities that fix the ASTM D341 double-log viscosity
curve, density, heat capacity, thermal conductivity, and pressure-viscosity
coefficient. Supply temperature, pressure, and flow are carried explicitly so
heat rejection can enter a thermal/energy closure. Detailed elastohydrodynamic
film prediction remains a separate fidelity with its own participant seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .validity import MechanismError, Validity, finite

_CST_PER_M2_S = 1.0e6
_REFERENCE_TEMPERATURE_40C_K = 313.15
_REFERENCE_TEMPERATURE_100C_K = 373.15
_ENVELOPE_K = (253.15, 453.15)


@dataclass(frozen=True, slots=True)
class LubricantSpec:
    """A lubricant defined by its identity and standardized reference data."""

    name: str
    kinematic_viscosity_40c_m2_s: float
    kinematic_viscosity_100c_m2_s: float
    density_kg_m3: float
    specific_heat_j_kg_k: float
    thermal_conductivity_w_m_k: float
    pressure_viscosity_coefficient_inv_pa: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MechanismError("lubricant.name is required")
        v40 = finite(
            self.kinematic_viscosity_40c_m2_s,
            "lubricant.kinematic_viscosity_40c_m2_s",
            positive=True,
        )
        v100 = finite(
            self.kinematic_viscosity_100c_m2_s,
            "lubricant.kinematic_viscosity_100c_m2_s",
            positive=True,
        )
        if v100 >= v40:
            raise MechanismError("lubricant viscosity must fall with temperature")
        finite(self.density_kg_m3, "lubricant.density_kg_m3", positive=True)
        finite(self.specific_heat_j_kg_k, "lubricant.specific_heat_j_kg_k", positive=True)
        finite(
            self.thermal_conductivity_w_m_k,
            "lubricant.thermal_conductivity_w_m_k",
            positive=True,
        )
        finite(
            self.pressure_viscosity_coefficient_inv_pa,
            "lubricant.pressure_viscosity_coefficient_inv_pa",
            positive=True,
        )

    @property
    def viscosity_ratio_40_100(self) -> float:
        return self.kinematic_viscosity_40c_m2_s / self.kinematic_viscosity_100c_m2_s

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kinematic_viscosity_40c_m2_s": self.kinematic_viscosity_40c_m2_s,
            "kinematic_viscosity_100c_m2_s": self.kinematic_viscosity_100c_m2_s,
            "density_kg_m3": self.density_kg_m3,
            "specific_heat_j_kg_k": self.specific_heat_j_kg_k,
            "thermal_conductivity_w_m_k": self.thermal_conductivity_w_m_k,
            "pressure_viscosity_coefficient_inv_pa": (
                self.pressure_viscosity_coefficient_inv_pa
            ),
        }


def _d341_constants(spec: LubricantSpec) -> tuple[float, float]:
    """Solve the ASTM D341 double-log relation from two reference points."""

    z40 = spec.kinematic_viscosity_40c_m2_s * _CST_PER_M2_S + 0.7
    z100 = spec.kinematic_viscosity_100c_m2_s * _CST_PER_M2_S + 0.7
    slope = (log10(log10(z40)) - log10(log10(z100))) / (
        log10(_REFERENCE_TEMPERATURE_100C_K) - log10(_REFERENCE_TEMPERATURE_40C_K)
    )
    intercept = log10(log10(z40)) + slope * log10(_REFERENCE_TEMPERATURE_40C_K)
    return intercept, slope


def kinematic_viscosity_at(spec: LubricantSpec, temperature_k: float) -> float:
    """ASTM D341 kinematic viscosity in m^2/s at an absolute temperature."""

    temperature = finite(temperature_k, "temperature_k", positive=True)
    intercept, slope = _d341_constants(spec)
    double_log = intercept - slope * log10(temperature)
    z = float(10.0 ** (10.0**double_log))
    return max(z - 0.7, 1.0e-9) / _CST_PER_M2_S


def dynamic_viscosity_at(spec: LubricantSpec, temperature_k: float) -> float:
    """Dynamic (absolute) viscosity in Pa*s at an absolute temperature."""

    return kinematic_viscosity_at(spec, temperature_k) * spec.density_kg_m3


@dataclass(frozen=True, slots=True)
class LubricationState:
    """Evaluated lubricant state at one operating temperature."""

    lubricant: LubricantSpec
    temperature_k: float
    kinematic_viscosity_m2_s: float
    dynamic_viscosity_pa_s: float
    density_kg_m3: float
    pressure_viscosity_coefficient_inv_pa: float
    validity: Validity
    provenance: Provenance

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "lubricant": self.lubricant.name,
            "temperature_k": self.temperature_k,
            "kinematic_viscosity_m2_s": self.kinematic_viscosity_m2_s,
            "dynamic_viscosity_pa_s": self.dynamic_viscosity_pa_s,
            "density_kg_m3": self.density_kg_m3,
        }

    def units(self) -> dict[str, str]:
        return {
            "temperature_k": "K",
            "kinematic_viscosity_m2_s": "m2/s",
            "dynamic_viscosity_pa_s": "Pa*s",
            "density_kg_m3": "kg/m3",
            "pressure_viscosity_coefficient_inv_pa": "1/Pa",
        }


def evaluate_lubrication(spec: LubricantSpec, temperature_k: float) -> LubricationState:
    """Evaluate viscosity at a temperature and report envelope validity."""

    temperature = finite(temperature_k, "temperature_k", positive=True)
    kinematic = kinematic_viscosity_at(spec, temperature)
    dynamic = kinematic * spec.density_kg_m3
    checks = {
        "temperature_in_envelope": _ENVELOPE_K[0] <= temperature <= _ENVELOPE_K[1],
        "kinematic_viscosity_positive": kinematic > 0.0,
        "dynamic_viscosity_positive": dynamic > 0.0,
    }
    provenance = analytical_provenance(
        "mechanisms.lubrication.astm-d341",
        {"lubricant": spec.canonical_payload(), "temperature_k": temperature},
        assumptions=("viscosity-temperature curve from two ASTM D341 reference points",),
    )
    return LubricationState(
        lubricant=spec,
        temperature_k=temperature,
        kinematic_viscosity_m2_s=kinematic,
        dynamic_viscosity_pa_s=dynamic,
        density_kg_m3=spec.density_kg_m3,
        pressure_viscosity_coefficient_inv_pa=spec.pressure_viscosity_coefficient_inv_pa,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"ASTM D341 curve for {spec.name}",
        ),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class LubricantSupply:
    """Supply-side lubricant state feeding a thermal/energy closure."""

    temperature_k: float
    pressure_pa: float
    flow_rate_m3_s: float

    def __post_init__(self) -> None:
        finite(self.temperature_k, "supply.temperature_k", positive=True)
        finite(self.pressure_pa, "supply.pressure_pa", positive=True)
        finite(self.flow_rate_m3_s, "supply.flow_rate_m3_s", positive=True)

    def mass_flow_kg_s(self, spec: LubricantSpec) -> float:
        return self.flow_rate_m3_s * spec.density_kg_m3

    def heat_rejection_w(self, spec: LubricantSpec, outlet_temperature_k: float) -> float:
        """Heat carried away by the lubricant for a given outlet temperature."""

        outlet = finite(outlet_temperature_k, "outlet_temperature_k", positive=True)
        if outlet < self.temperature_k:
            raise MechanismError("outlet temperature below supply temperature")
        return (
            self.mass_flow_kg_s(spec)
            * spec.specific_heat_j_kg_k
            * (outlet - self.temperature_k)
        )

    def temperature_rise_k(self, spec: LubricantSpec, heat_w: float) -> float:
        """Temperature rise that removes a heat load through the flow."""

        load = finite(heat_w, "heat_w", minimum=0.0)
        capacity = self.mass_flow_kg_s(spec) * spec.specific_heat_j_kg_k
        return load / capacity

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "temperature_k": self.temperature_k,
            "pressure_pa": self.pressure_pa,
            "flow_rate_m3_s": self.flow_rate_m3_s,
        }


LUBRICANTS: dict[str, LubricantSpec] = {
    "iso-vg32": LubricantSpec(
        name="iso-vg32",
        kinematic_viscosity_40c_m2_s=32.0e-6,
        kinematic_viscosity_100c_m2_s=5.4e-6,
        density_kg_m3=875.0,
        specific_heat_j_kg_k=1900.0,
        thermal_conductivity_w_m_k=0.14,
        pressure_viscosity_coefficient_inv_pa=2.0e-8,
    ),
    "iso-vg46": LubricantSpec(
        name="iso-vg46",
        kinematic_viscosity_40c_m2_s=46.0e-6,
        kinematic_viscosity_100c_m2_s=6.8e-6,
        density_kg_m3=872.0,
        specific_heat_j_kg_k=1900.0,
        thermal_conductivity_w_m_k=0.14,
        pressure_viscosity_coefficient_inv_pa=2.0e-8,
    ),
}


def get_lubricant(name: str) -> LubricantSpec:
    """Return a registry lubricant, failing closed on an unknown name."""

    try:
        return LUBRICANTS[name.lower()]
    except KeyError:
        raise MechanismError(f"lubricant.unknown:{name}") from None


__all__ = [
    "LUBRICANTS",
    "LubricantSpec",
    "LubricantSupply",
    "LubricationState",
    "dynamic_viscosity_at",
    "evaluate_lubrication",
    "get_lubricant",
    "kinematic_viscosity_at",
]
