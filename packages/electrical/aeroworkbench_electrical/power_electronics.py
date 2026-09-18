"""Generic inverter/ESC participant: conduction, switching loss, and heat.

Losses come from declared device parameters (conduction resistance and per-amp
switching energy) at the converged junction temperature. The DC power balance
``dc_power = output_power + total_loss`` holds by construction, so the drive's
loss always participates in global energy closure. Arbitrary switching
waveforms are deliberately out of scope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .parameters import UNITS, DriveParameters
from .validity import FidelityLevel, Validity


class InverterModelError(ValueError):
    """A typed, fail-closed inverter-model contract violation."""

    code = "PREPARATION_FAILED"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class InverterResult:
    """Typed inverter/ESC operating point with included loss terms."""

    fidelity: str
    source: str
    motor_voltage_v: float
    output_power_w: float
    output_current_a: float
    dc_current_a: float
    dc_power_w: float
    conduction_loss_w: float
    switching_loss_w: float
    total_loss_w: float
    efficiency: float
    case_temp_k: float
    junction_temp_k: float
    heat_load_w: float
    validity: Validity
    iterations: int = 1
    detail: str = ""
    warnings: tuple[str, ...] = field(default=())

    def as_scalars(self) -> dict[str, float]:
        return {
            "motor_voltage_v": float(self.motor_voltage_v),
            "output_current_a": float(self.output_current_a),
            "dc_current_a": float(self.dc_current_a),
            "dc_power_w": float(self.dc_power_w),
            "conduction_loss_w": float(self.conduction_loss_w),
            "switching_loss_w": float(self.switching_loss_w),
            "total_loss_w": float(self.total_loss_w),
            "efficiency": float(self.efficiency),
            "junction_temp_k": float(self.junction_temp_k),
            "heat_load_w": float(self.heat_load_w),
        }

    def units(self) -> dict[str, str]:
        return {name: UNITS[name] for name in self.as_scalars()}


def _require_finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise InverterModelError(f"INVERTER_NONFINITE_INPUT:{label}")
    return value


def solve_inverter(
    parameters: DriveParameters,
    *,
    dc_bus_voltage_v: float,
    output_power_w: float,
    switching_frequency_hz: float,
    modulation_index: float,
    case_temp_k: float,
    fidelity: str = FidelityLevel.ANALYTICAL,
    tolerance: float = 1e-6,
    max_iterations: int = 50,
) -> InverterResult:
    """Solve the generic inverter loss/thermal balance at one operating point."""

    level = FidelityLevel(fidelity)
    if level is FidelityLevel.NATIVE:
        raise InverterModelError("INVERTER_NATIVE_LEVEL_NOT_IMPLEMENTED")
    for label, value in (
        ("dc_bus_voltage_v", dc_bus_voltage_v),
        ("output_power_w", output_power_w),
        ("switching_frequency_hz", switching_frequency_hz),
        ("modulation_index", modulation_index),
        ("case_temp_k", case_temp_k),
    ):
        _require_finite(value, label)
    if dc_bus_voltage_v <= 0:
        raise InverterModelError("INVERTER_DC_BUS_MUST_BE_POSITIVE")
    if output_power_w < 0:
        raise InverterModelError("INVERTER_OUTPUT_POWER_MUST_BE_NONNEGATIVE")
    if switching_frequency_hz <= 0:
        raise InverterModelError("INVERTER_SWITCHING_FREQUENCY_MUST_BE_POSITIVE")
    if modulation_index <= 0:
        raise InverterModelError("INVERTER_MODULATION_MUST_BE_POSITIVE")

    motor_voltage = modulation_index * dc_bus_voltage_v
    output_current = output_power_w / motor_voltage

    junction_temp = case_temp_k
    converged = False
    iteration = 0
    for step in range(1, max_iterations + 1):
        iteration = step
        resistance = parameters.conduction_resistance_at(junction_temp)
        conduction = output_current * output_current * resistance
        switching = (
            parameters.switching_energy_j_per_a * switching_frequency_hz * output_current
        )
        junction_next = case_temp_k + (conduction + switching) * (
            parameters.thermal_resistance_k_per_w
        )
        if abs(junction_next - junction_temp) <= tolerance:
            junction_temp = junction_next
            converged = True
            break
        junction_temp = junction_next

    resistance = parameters.conduction_resistance_at(junction_temp)
    conduction_loss = output_current * output_current * resistance
    switching_loss = (
        parameters.switching_energy_j_per_a * switching_frequency_hz * output_current
    )
    total_loss = conduction_loss + switching_loss
    dc_power = output_power_w + total_loss
    dc_current = dc_power / dc_bus_voltage_v
    efficiency = output_power_w / dc_power if dc_power > 0 else 0.0
    balance_error = abs(dc_power - output_power_w - total_loss)

    checks = {
        "dc_bus_in_envelope": parameters.min_dc_bus_v
        <= dc_bus_voltage_v
        <= parameters.max_dc_bus_v,
        "power_in_envelope": output_power_w <= parameters.max_output_power_w,
        "modulation_in_envelope": 0.0 < modulation_index <= parameters.max_modulation_index,
        "case_temp_in_envelope": parameters.min_case_temp_k
        <= case_temp_k
        <= parameters.max_case_temp_k,
        "junction_temp_in_envelope": junction_temp <= parameters.max_junction_temp_k,
        "thermal_fixed_point_converged": converged,
        "power_balance": balance_error <= 1e-9 * max(1.0, dc_power),
        "efficiency_bounded": 0.0 <= efficiency <= 1.0,
    }
    return InverterResult(
        fidelity=FidelityLevel.ANALYTICAL.value,
        source="device-parameter-loss-model",
        motor_voltage_v=motor_voltage,
        output_power_w=output_power_w,
        output_current_a=output_current,
        dc_current_a=dc_current,
        dc_power_w=dc_power,
        conduction_loss_w=conduction_loss,
        switching_loss_w=switching_loss,
        total_loss_w=total_loss,
        efficiency=efficiency,
        case_temp_k=case_temp_k,
        junction_temp_k=junction_temp,
        heat_load_w=total_loss,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"junction fixed point in {iteration} iterations; losses included in dc balance",
        ),
        iterations=iteration,
        detail=(
            f"r_conduction={resistance:.6g} ohm, "
            f"e_sw={parameters.switching_energy_j_per_a:.6g} J/A"
        ),
    )


__all__ = ["InverterModelError", "InverterResult", "solve_inverter"]
