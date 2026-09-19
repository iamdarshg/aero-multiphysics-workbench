"""Ideal-gas properties and unit-bearing meanline thermodynamic state.

The state is deliberately plain: total/static temperature and pressure plus the
local velocity, Mach number, and mass flow. Specific heat is constant within a
row so that the Euler work and the total-enthalpy bookkeeping stay exact under
the model's stated assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from .errors import MeanlineInputError


def _finite(value: float, label: str) -> float:
    if not isfinite(value):
        raise MeanlineInputError(f"NONFINITE_INPUT:{label}")
    return value


def _positive(value: float, label: str) -> float:
    _finite(value, label)
    if value <= 0.0:
        raise MeanlineInputError(f"NONPOSITIVE_INPUT:{label}")
    return value


@dataclass(frozen=True, slots=True)
class IdealGas:
    """Constant-property ideal gas used by the reduced-order meanline model."""

    cp_j_kg_k: float
    gamma: float
    gas_constant_j_kg_k: float

    def __post_init__(self) -> None:
        _positive(self.cp_j_kg_k, "cp_j_kg_k")
        _positive(self.gas_constant_j_kg_k, "gas_constant_j_kg_k")
        _finite(self.gamma, "gamma")
        if self.gamma <= 1.0:
            raise MeanlineInputError(f"GAMMA_MUST_EXCEED_ONE:{self.gamma}")

    def sound_speed_m_s(self, temperature_k: float) -> float:
        _positive(temperature_k, "temperature_k")
        return sqrt(self.gamma * self.gas_constant_j_kg_k * temperature_k)

    def total_enthalpy_j_kg(self, total_temperature_k: float) -> float:
        _positive(total_temperature_k, "total_temperature_k")
        return self.cp_j_kg_k * total_temperature_k

    def static_enthalpy_j_kg(self, static_temperature_k: float) -> float:
        _positive(static_temperature_k, "static_temperature_k")
        return self.cp_j_kg_k * static_temperature_k

    def static_temperature_k(self, total_temperature_k: float, velocity_m_s: float) -> float:
        _positive(total_temperature_k, "total_temperature_k")
        _finite(velocity_m_s, "velocity_m_s")
        return total_temperature_k - velocity_m_s * velocity_m_s / (2.0 * self.cp_j_kg_k)

    def static_pressure_pa(
        self,
        total_pressure_pa: float,
        total_temperature_k: float,
        static_temperature_k: float,
    ) -> float:
        _positive(total_pressure_pa, "total_pressure_pa")
        _positive(total_temperature_k, "total_temperature_k")
        _positive(static_temperature_k, "static_temperature_k")
        exponent = self.gamma / (self.gamma - 1.0)
        return float(total_pressure_pa * (static_temperature_k / total_temperature_k) ** exponent)

    def density_kg_m3(self, pressure_pa: float, temperature_k: float) -> float:
        _positive(pressure_pa, "pressure_pa")
        _positive(temperature_k, "temperature_k")
        return pressure_pa / (self.gas_constant_j_kg_k * temperature_k)

    def canonical(self) -> dict[str, object]:
        return {
            "cpJkgK": self.cp_j_kg_k,
            "gamma": self.gamma,
            "gasConstantJkgK": self.gas_constant_j_kg_k,
        }


@dataclass(frozen=True, slots=True)
class MeanlineState:
    """Total/static thermodynamic state at one meanline station."""

    total_temperature_k: float
    total_pressure_pa: float
    static_temperature_k: float
    static_pressure_pa: float
    density_kg_m3: float
    velocity_m_s: float
    mach: float
    mass_flow_kg_s: float

    def canonical(self) -> dict[str, object]:
        return {
            "totalTemperatureK": self.total_temperature_k,
            "totalPressurePa": self.total_pressure_pa,
            "staticTemperatureK": self.static_temperature_k,
            "staticPressurePa": self.static_pressure_pa,
            "densityKgM3": self.density_kg_m3,
            "velocityMs": self.velocity_m_s,
            "mach": self.mach,
            "massFlowKgS": self.mass_flow_kg_s,
        }


def state_from_total(
    *,
    gas: IdealGas,
    total_temperature_k: float,
    total_pressure_pa: float,
    mass_flow_kg_s: float,
    velocity_m_s: float,
) -> MeanlineState:
    """Build a static state from total conditions and a representative velocity."""

    _positive(mass_flow_kg_s, "mass_flow_kg_s")
    static_temperature = gas.static_temperature_k(total_temperature_k, velocity_m_s)
    if static_temperature <= 0.0:
        raise MeanlineInputError(f"STATIC_TEMPERATURE_NONPOSITIVE:{static_temperature}")
    static_pressure = gas.static_pressure_pa(
        total_pressure_pa, total_temperature_k, static_temperature
    )
    density = gas.density_kg_m3(static_pressure, static_temperature)
    mach = mach_number(
        gas=gas, velocity_m_s=velocity_m_s, static_temperature_k=static_temperature
    )
    return MeanlineState(
        total_temperature_k=total_temperature_k,
        total_pressure_pa=total_pressure_pa,
        static_temperature_k=static_temperature,
        static_pressure_pa=static_pressure,
        density_kg_m3=density,
        velocity_m_s=velocity_m_s,
        mach=mach,
        mass_flow_kg_s=mass_flow_kg_s,
    )


def mach_number(*, gas: IdealGas, velocity_m_s: float, static_temperature_k: float) -> float:
    """Local Mach number based on the static temperature and gas properties."""

    return velocity_m_s / gas.sound_speed_m_s(static_temperature_k)


def reynolds_number(
    *,
    gas: IdealGas,
    static_pressure_pa: float,
    static_temperature_k: float,
    velocity_m_s: float,
    chord_m: float,
    dynamic_viscosity_pa_s: float,
) -> float:
    """Blade-chord Reynolds number from the local static state."""

    _positive(chord_m, "chord_m")
    _positive(dynamic_viscosity_pa_s, "dynamic_viscosity_pa_s")
    density = gas.density_kg_m3(static_pressure_pa, static_temperature_k)
    return density * velocity_m_s * chord_m / dynamic_viscosity_pa_s


__all__ = [
    "IdealGas",
    "MeanlineState",
    "state_from_total",
    "mach_number",
    "reynolds_number",
]
