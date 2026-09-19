"""Scalar participant and OpenMDAO adapter for the meanline design layer.

The scalar function wraps one consistent design point through the analytical
throughflow solver and returns the quantities an optimizer couples to the cycle,
geometry, and constraint workstreams. Finite-difference derivatives are provided
explicitly so the generic optimizer can use the component even without analytic
partials; the OpenMDAO component is built lazily so importing this module never
pulls the OpenMDAO stack.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any

from .design import MeanlineRow, StageDesign
from .properties import IdealGas
from .throughflow import ThroughflowResult, solve_throughflow

_AIR = IdealGas(cp_j_kg_k=1005.0, gamma=1.4, gas_constant_j_kg_k=287.05)
_INLET_TOTAL_TEMPERATURE_K = 288.15
_INLET_TOTAL_PRESSURE_PA = 101325.0
_MASS_FLOW_KG_S = 1.0
_DYNAMIC_VISCOSITY_PA_S = 1.8e-5

DEFAULT_MEANLINE_INPUTS: dict[str, float] = {
    "mean_radius_m": 0.25,
    "rotational_speed_rpm": 8000.0,
    "meridional_velocity_m_s": 160.0,
    "inlet_swirl_angle_deg": 0.0,
    "exit_metal_angle_deg": -45.0,
    "stagger_deg": 30.0,
    "camber_deg": 30.0,
    "solidity": 1.2,
    "chord_m": 0.05,
    "span_m": 0.08,
    "blade_count": 40.0,
    "tip_clearance_m": 0.0005,
    "incidence_deg": 0.0,
}

_OUTPUT_DEFAULTS: dict[str, float] = {
    "euler_work_j_kg": 0.0,
    "total_pressure_loss_pa": 0.0,
    "total_pressure_ratio": 1.0,
    "reaction": 0.5,
    "diffusion_factor": 0.3,
    "relative_mach_out": 0.5,
    "loss_coefficient": 0.0,
}


def _design_stage(state: Mapping[str, float]) -> tuple[StageDesign, MeanlineRow]:
    from math import atan2, degrees, radians, tan

    radius = float(state["mean_radius_m"])
    rpm = float(state["rotational_speed_rpm"])
    meridional = float(state["meridional_velocity_m_s"])
    swirl = float(state["inlet_swirl_angle_deg"])
    omega = rpm * 2.0 * 3.141592653589793 / 60.0
    blade_speed = omega * radius
    relative_tangential = meridional * tan(radians(swirl)) - blade_speed
    design_relative_angle = degrees(atan2(relative_tangential, meridional))
    incidence = float(state.get("incidence_deg", 0.0))
    row = MeanlineRow(
        row_family="axial_compressor_rotor",
        mean_radius_in_m=radius,
        mean_radius_out_m=radius,
        meridional_velocity_in_m_s=meridional,
        inlet_metal_angle_deg=design_relative_angle + incidence,
        exit_metal_angle_deg=float(state["exit_metal_angle_deg"]),
        stagger_deg=float(state["stagger_deg"]),
        camber_deg=float(state["camber_deg"]),
        solidity=float(state["solidity"]),
        chord_m=float(state["chord_m"]),
        span_m=float(state["span_m"]),
        blade_count=int(state["blade_count"]),
        tip_clearance_m=float(state["tip_clearance_m"]),
    )
    stage = StageDesign(
        gas=_AIR,
        inlet_total_temperature_k=_INLET_TOTAL_TEMPERATURE_K,
        inlet_total_pressure_pa=_INLET_TOTAL_PRESSURE_PA,
        mass_flow_kg_s=_MASS_FLOW_KG_S,
        rotational_speed_rpm=rpm,
        rows=(row,),
        name="meanline-scalar-point",
        inlet_swirl_angle_deg=swirl,
        dynamic_viscosity_pa_s=_DYNAMIC_VISCOSITY_PA_S,
    )
    return stage, row


def meanline_scalars(inputs: Mapping[str, float]) -> dict[str, float]:
    """Evaluate one meanline design point into flat scalar outputs."""

    stage, _ = _design_stage(inputs)
    result: ThroughflowResult = solve_throughflow(stage)
    row_result = result.rows[0]
    return {
        "euler_work_j_kg": row_result.euler_work_j_kg,
        "total_pressure_loss_pa": row_result.total_pressure_loss_pa,
        "total_pressure_ratio": result.pressure_ratio,
        "reaction": row_result.reaction,
        "diffusion_factor": row_result.diffusion_factor,
        "relative_mach_out": row_result.outlet_triangle.relative_velocity_m_s
        / _AIR.sound_speed_m_s(row_result.outlet_state.static_temperature_k),
        "incidence_deg": row_result.incidence_deg,
        "loss_coefficient": row_result.loss_breakdown.total,
    }


def finite_difference_jacobian(
    function: Callable[[Mapping[str, float]], Mapping[str, float]],
    inputs: Mapping[str, float],
    *,
    relative_step: float = 1e-6,
) -> dict[str, dict[str, float]]:
    """Bounded forward-difference Jacobian of a scalar participant."""

    if relative_step <= 0.0:
        raise ValueError(f"RELATIVE_STEP_MUST_BE_POSITIVE:{relative_step}")
    base = dict(inputs)
    baseline = dict(function(base))
    jacobian: dict[str, dict[str, float]] = {
        output: {} for output in baseline
    }
    for name, value in base.items():
        step = relative_step * max(abs(value), 1e-3)
        perturbed = dict(base)
        perturbed[name] = value + step
        outputs = function(perturbed)
        for output, output_value in baseline.items():
            jacobian[output][name] = (outputs[output] - output_value) / step
    return jacobian


def build_openmdao_component() -> Any:
    """Build an OpenMDAO ExplicitComponent wrapping :func:`meanline_scalars`.

    Imports OpenMDAO lazily so the meanline package can be imported and tested
    without the OpenMDAO stack installed.
    """

    om = importlib.import_module("openmdao.api")

    class MeanlineArrayComponent(om.ExplicitComponent):  # type: ignore[misc, name-defined]
        def setup(self) -> None:
            for name, value in DEFAULT_MEANLINE_INPUTS.items():
                self.add_input(name, val=value)
            for name, value in _OUTPUT_DEFAULTS.items():
                self.add_output(name, val=value)

        def setup_partials(self) -> None:
            self.declare_partials("*", "*", method="fd")

        def compute(self, inputs: Any, outputs: Any) -> None:
            state = {name: float(inputs[name][0]) for name in DEFAULT_MEANLINE_INPUTS}
            for name, value in meanline_scalars(state).items():
                if name in _OUTPUT_DEFAULTS:
                    outputs[name] = value

    return MeanlineArrayComponent


__all__ = [
    "DEFAULT_MEANLINE_INPUTS",
    "meanline_scalars",
    "finite_difference_jacobian",
    "build_openmdao_component",
]
