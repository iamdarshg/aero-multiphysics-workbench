"""Calorically-perfect ideal-gas relations for the generic gas-path solver.

The gas model is deliberately generic: a constant specific heat, ratio of
specific heats, and (optionally) an explicit gas constant. No application name
or vehicle concept appears here. Combustion changes the selected gas properties
in the design; the solver itself stays a single-fluid calorically-perfect model
and records that assumption in its provenance.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CycleModelError


@dataclass(frozen=True, slots=True)
class GasProperties:
    """Constant ``cp``/``gamma`` ideal gas with an optional explicit gas constant."""

    cp_j_kg_k: float
    gamma: float
    identity: str = "ideal-gas"
    gas_constant_j_kg_k: float | None = None

    def __post_init__(self) -> None:
        if not self.identity.strip():
            raise CycleModelError("GAS_IDENTITY_REQUIRED")
        if not self.cp_j_kg_k > 0:
            raise CycleModelError("GAS_CP_MUST_BE_POSITIVE")
        if not self.gamma > 1:
            raise CycleModelError("GAS_GAMMA_MUST_EXCEED_ONE")
        if self.gas_constant_j_kg_k is not None and self.gas_constant_j_kg_k <= 0:
            raise CycleModelError("GAS_CONSTANT_MUST_BE_POSITIVE")

    @property
    def r_j_kg_k(self) -> float:
        if self.gas_constant_j_kg_k is not None:
            return self.gas_constant_j_kg_k
        return self.cp_j_kg_k * (self.gamma - 1.0) / self.gamma

    @property
    def exponent(self) -> float:
        """Isentropic exponent ``(gamma - 1) / gamma``."""

        return (self.gamma - 1.0) / self.gamma

    @property
    def critical_pressure_ratio(self) -> float:
        """Choking total-to-static pressure ratio of a converging nozzle."""

        return float(((self.gamma + 1.0) / 2.0) ** (self.gamma / (self.gamma - 1.0)))

    def canonical(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "cpJkgK": self.cp_j_kg_k,
            "gamma": self.gamma,
            "gasConstantJkgK": self.r_j_kg_k,
        }


AIR = GasProperties(cp_j_kg_k=1005.0, gamma=1.4, identity="dry-air")
COMBUSTION_GAS = GasProperties(cp_j_kg_k=1150.0, gamma=1.33, identity="combustion-gas")


def isentropic_temperature_ratio(gas: GasProperties, pressure_ratio: float) -> float:
    """Total-to-total isentropic temperature ratio for a pressure ratio."""

    if pressure_ratio <= 0:
        raise CycleModelError(f"PRESSURE_RATIO_MUST_BE_POSITIVE:{pressure_ratio}")
    return float(pressure_ratio**gas.exponent)


def isentropic_pressure_ratio(gas: GasProperties, temperature_ratio: float) -> float:
    """Total-to-total isentropic pressure ratio for a temperature ratio."""

    if temperature_ratio <= 0:
        raise CycleModelError(f"TEMPERATURE_RATIO_MUST_BE_POSITIVE:{temperature_ratio}")
    return float(temperature_ratio ** (1.0 / gas.exponent))


def compressor_exit_temperature(
    gas: GasProperties,
    *,
    inlet_total_temperature_k: float,
    pressure_ratio: float,
    isentropic_efficiency: float,
) -> float:
    """Compressor exit total temperature from pressure ratio and efficiency."""

    if not 0 < isentropic_efficiency <= 1:
        raise CycleModelError(f"COMPRESSOR_EFFICIENCY_OUT_OF_RANGE:{isentropic_efficiency}")
    if pressure_ratio < 1:
        raise CycleModelError(f"COMPRESSOR_PRESSURE_RATIO_BELOW_ONE:{pressure_ratio}")
    ideal = isentropic_temperature_ratio(gas, pressure_ratio)
    return inlet_total_temperature_k * (1.0 + (ideal - 1.0) / isentropic_efficiency)


def turbine_exit_temperature(
    gas: GasProperties,
    *,
    inlet_total_temperature_k: float,
    expansion_ratio: float,
    isentropic_efficiency: float,
) -> float:
    """Turbine exit total temperature from expansion ratio and efficiency."""

    if not 0 < isentropic_efficiency <= 1:
        raise CycleModelError(f"TURBINE_EFFICIENCY_OUT_OF_RANGE:{isentropic_efficiency}")
    if expansion_ratio < 1:
        raise CycleModelError(f"TURBINE_EXPANSION_RATIO_BELOW_ONE:{expansion_ratio}")
    ideal_ratio = float(expansion_ratio ** (-gas.exponent))
    return inlet_total_temperature_k * (1.0 - isentropic_efficiency * (1.0 - ideal_ratio))


def static_temperature_from_total(
    gas: GasProperties, *, total_temperature_k: float, mach: float
) -> float:
    return total_temperature_k / (1.0 + 0.5 * (gas.gamma - 1.0) * mach * mach)


def static_pressure_from_total(
    gas: GasProperties, *, total_pressure_pa: float, mach: float
) -> float:
    return float(
        total_pressure_pa
        * (1.0 + 0.5 * (gas.gamma - 1.0) * mach * mach)
        ** (-gas.gamma / (gas.gamma - 1.0))
    )


def velocity_from_temperature_drop(
    gas: GasProperties, *, total_temperature_k: float, static_temperature_k: float
) -> float:
    drop = total_temperature_k - static_temperature_k
    return float((2.0 * gas.cp_j_kg_k * max(drop, 0.0)) ** 0.5)


def total_temperature_from_static(
    gas: GasProperties, *, static_temperature_k: float, velocity_m_s: float
) -> float:
    return static_temperature_k + velocity_m_s * velocity_m_s / (2.0 * gas.cp_j_kg_k)


def ideal_gas_density(*, pressure_pa: float, temperature_k: float, r_j_kg_k: float) -> float:
    if temperature_k <= 0 or r_j_kg_k <= 0:
        raise CycleModelError("DENSITY_NEEDS_POSITIVE_TEMPERATURE_AND_GAS_CONSTANT")
    return pressure_pa / (r_j_kg_k * temperature_k)


__all__ = [
    "AIR",
    "COMBUSTION_GAS",
    "GasProperties",
    "compressor_exit_temperature",
    "ideal_gas_density",
    "isentropic_pressure_ratio",
    "isentropic_temperature_ratio",
    "static_pressure_from_total",
    "static_temperature_from_total",
    "total_temperature_from_static",
    "turbine_exit_temperature",
    "velocity_from_temperature_drop",
]
