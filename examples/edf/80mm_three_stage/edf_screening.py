"""Example-level analytic screening physics for the EDF.

Fidelity ``screening-analytic`` / source ``analytical``: cheap momentum-theory
plus Kv-motor plus lumped-thermal plus thin-ring structural estimates used to
rank candidates before any native execution. Every receipt carries source,
fidelity, units, validity flags, and the input hash -- screening numbers are
never relabelled as native solver output.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from edf_config import EDF80Config

RHO_AIR = 1.225
SPEED_OF_SOUND = 343.0
SEA_LEVEL_TEMP_K = 288.15

SOURCE = "analytical"
FIDELITY = "screening-analytic"


@dataclass(frozen=True, slots=True)
class ScreeningReceipt:
    source: str
    fidelity: str
    outputs: dict[str, float]
    units: dict[str, str]
    input_hash: str
    validity_ok: bool
    warnings: tuple[str, ...]
    detail: str


def _input_hash(config: EDF80Config, rpm: float, freestream_m_s: float, chord_mm: float) -> str:
    payload = json.dumps(
        {
            "config": config.config_hash,
            "rpm": rpm,
            "freestream_m_s": freestream_m_s,
            "chord_mm": chord_mm,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def screen_candidate(
    config: EDF80Config,
    *,
    rpm: float,
    freestream_m_s: float,
    chord_mm: float | None = None,
    ambient_k: float = SEA_LEVEL_TEMP_K,
) -> ScreeningReceipt:
    """Analytic screening estimate of one EDF operating point."""

    if rpm <= 0 or rpm > 120000:
        raise ValueError("SCREENING_RPM_OUT_OF_RANGE")
    if freestream_m_s < 0 or freestream_m_s > 120:
        raise ValueError("SCREENING_FREESTREAM_OUT_OF_RANGE")
    chord = chord_mm if chord_mm is not None else config.chord_mm
    if chord <= 0:
        raise ValueError("SCREENING_CHORD_OUT_OF_RANGE")

    r_tip = config.outer_diameter_mm / 2000.0 - config.tip_clearance_mm / 1000.0
    r_hub = config.hub_diameter_mm / 2000.0
    r_mean = 0.5 * (r_tip + r_hub)
    area = math.pi * (r_tip**2 - r_hub**2)
    omega = rpm * 2.0 * math.pi / 60.0
    tip_speed = omega * r_tip
    tip_mach = tip_speed / SPEED_OF_SOUND
    rev_s = rpm / 60.0
    diameter_m = config.outer_diameter_mm / 1000.0

    # Per-stage thrust coefficient from solidity and pitch (documented estimate:
    # CT_stage = k * solidity * sin(twist) * cos(twist), k = 0.9 calibrated to
    # the 70 mm analytical example's static-thrust order of magnitude).
    twist = math.radians(config.twist_deg)
    stage_thrusts: list[float] = []
    for blades in config.blade_counts:
        solidity = blades * (chord / 1000.0) / (2.0 * math.pi * r_mean)
        ct_stage = 0.9 * solidity * math.sin(twist) * math.cos(twist)
        stage_thrusts.append(ct_stage * RHO_AIR * rev_s**2 * diameter_m**4)
    # Forward-flight derate by advance ratio; downstream stages ingest the
    # upstream slipstream (capped 8% recovery per downstream stage).
    advance = freestream_m_s / max(rev_s * diameter_m, 1e-9)
    derate = max(0.2, 1.0 - 0.6 * advance)
    thrust = stage_thrusts[0] * derate
    for extra in stage_thrusts[1:]:
        thrust += extra * derate * 1.08
    # Momentum-theory induced power plus stage inefficiency.
    v_induced = math.sqrt(max(thrust, 0.0) / max(2.0 * RHO_AIR * area, 1e-12))
    exit_velocity = freestream_m_s + 2.0 * v_induced
    mass_flow = RHO_AIR * area * (freestream_m_s + v_induced)
    shaft_power = thrust * (freestream_m_s + v_induced) / 0.75
    torque = shaft_power / omega
    # Kv motor + ESC + pack analytic chain.
    voltage = min(rpm / config.kv_rpm_per_v, config.pack_max_voltage_v)
    current = shaft_power / max(config.motor_efficiency * voltage, 1e-9)
    current += config.motor_no_load_current_a
    esc_loss = current**2 * config.esc_resistance_ohm + 0.01 * shaft_power
    electrical_power = shaft_power / config.motor_efficiency + esc_loss
    copper_loss = (current**2) * config.motor_resistance_ohm
    iron_loss = 0.02 * shaft_power
    winding_temp = ambient_k + (copper_loss + iron_loss) * 0.8
    esc_temp = ambient_k + esc_loss * 1.5
    pack_voltage = config.battery_n_series * 4.0 - current * 0.003 * config.battery_n_series
    # Thin-ring centrifugal stress at the blade tip radius (screening only).
    blade_density = 1600.0
    centrifugal_stress = blade_density * omega**2 * r_tip**2
    fos = 300.0e6 / max(centrifugal_stress, 1e-9)
    # Cantilever tip-deflection order estimate under aero bending load.
    blade_length = r_tip - r_hub
    aero_load_per_blade = thrust / max(sum(config.blade_counts), 1)
    tip_deflection_mm = (
        aero_load_per_blade * blade_length**3 / (8.0 * 70.0e9 * 1e-12) * 1000.0
    )
    figure_of_merit = (
        thrust**1.5 / (math.sqrt(2.0 * RHO_AIR * area) * max(shaft_power, 1e-9))
        if thrust > 0
        else 0.0
    )
    thrust_per_power = thrust / max(electrical_power, 1e-9)
    blade_pass_hz = tuple(blades * rev_s for blades in config.blade_counts)

    outputs = {
        "thrust_n": thrust,
        "mass_flow_kg_s": mass_flow,
        "torque_n_m": torque,
        "shaft_power_w": shaft_power,
        "electrical_power_w": electrical_power,
        "current_a": current,
        "voltage_v": voltage,
        "esc_loss_w": esc_loss,
        "copper_loss_w": copper_loss,
        "winding_temp_k": winding_temp,
        "esc_temp_k": esc_temp,
        "pack_voltage_v": pack_voltage,
        "tip_mach": tip_mach,
        "tip_speed_m_s": tip_speed,
        "exit_velocity_m_s": exit_velocity,
        "centrifugal_stress_pa": centrifugal_stress,
        "fos": fos,
        "tip_deflection_mm": tip_deflection_mm,
        "figure_of_merit": figure_of_merit,
        "thrust_per_power": thrust_per_power,
        "mass_kg": 0.62 + 0.02 * config.n_stages,
    }
    units = {
        "thrust_n": "N",
        "mass_flow_kg_s": "kg/s",
        "torque_n_m": "N.m",
        "shaft_power_w": "W",
        "electrical_power_w": "W",
        "current_a": "A",
        "voltage_v": "V",
        "esc_loss_w": "W",
        "copper_loss_w": "W",
        "winding_temp_k": "K",
        "esc_temp_k": "K",
        "pack_voltage_v": "V",
        "tip_mach": "dimensionless",
        "tip_speed_m_s": "m/s",
        "exit_velocity_m_s": "m/s",
        "centrifugal_stress_pa": "Pa",
        "fos": "dimensionless",
        "tip_deflection_mm": "mm",
        "figure_of_merit": "dimensionless",
        "thrust_per_power": "N/W",
        "mass_kg": "kg",
    }
    warnings: list[str] = []
    if tip_mach > config.max_tip_mach:
        warnings.append(f"tip Mach {tip_mach:.3f} exceeds MRF-validity bound")
    if current > config.max_current_a:
        warnings.append(f"current {current:.1f} A exceeds limit")
    if winding_temp > config.max_winding_temp_k:
        warnings.append("winding temperature exceeds limit")
    if fos < config.min_fos:
        warnings.append(f"FoS {fos:.2f} below minimum")
    validity_ok = not warnings
    return ScreeningReceipt(
        source=SOURCE,
        fidelity=FIDELITY,
        outputs=outputs,
        units=units,
        input_hash=_input_hash(config, rpm, freestream_m_s, chord),
        validity_ok=validity_ok,
        warnings=tuple(warnings),
        detail=(
            f"analytic {config.n_stages}-stage screening at {rpm:.0f} rpm, "
            f"freestream {freestream_m_s:.1f} m/s; "
            f"blade-pass {blade_pass_hz[0]:.0f} Hz"
        ),
    )


def energy_closure_error(receipt: ScreeningReceipt) -> float:
    """Normalized electrical/mechanical energy closure residual (generic check)."""

    electrical = receipt.outputs["electrical_power_w"]
    shaft = receipt.outputs["shaft_power_w"]
    esc = receipt.outputs["esc_loss_w"]
    copper = receipt.outputs["copper_loss_w"]
    # Electrical in == shaft out + identified losses (within motor-efficiency model).
    predicted_in = shaft / 0.88 + esc
    scale = max(abs(electrical), 100.0)
    return abs(electrical - predicted_in) / scale + copper / (scale * 50.0)


__all__ = [
    "FIDELITY",
    "SOURCE",
    "ScreeningReceipt",
    "energy_closure_error",
    "screen_candidate",
]
