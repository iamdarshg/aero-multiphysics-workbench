"""Reference EDF propulsion state for the drone workflow."""

from dataclasses import dataclass

from aeroworkbench_dynamics import assess_resonance, build_campbell
from pybamm.adapter import PackState, six_cell_series_state


@dataclass(frozen=True, slots=True)
class MotorState:
    voltage_v: float
    current_a: float
    rpm: float
    torque_nm: float
    heat_w: float
    fidelity: str


def motor_state(*, voltage_v: float, current_a: float, kv_rpm_per_v: float = 2100.0) -> MotorState:
    if voltage_v <= 0 or current_a < 0 or kv_rpm_per_v <= 0:
        raise ValueError("INVALID_MOTOR_STATE")
    rpm = voltage_v * kv_rpm_per_v
    torque = current_a / (kv_rpm_per_v * 2.0 * 3.141592653589793 / 60.0)
    return MotorState(voltage_v, current_a, rpm, torque, voltage_v * current_a * 0.08, "level-1")


def reference_edf_system() -> tuple[MotorState, PackState]:
    motor = motor_state(voltage_v=22.2, current_a=35.0)
    pack = six_cell_series_state(voltage_per_cell_v=3.7, current_a=35.0, soc=0.8)
    points = build_campbell(
        rpm_values=(motor.rpm,), blade_count=12, stator_count=11, modal_frequency_hz=450.0
    )
    assess_resonance(points)
    return motor, pack
