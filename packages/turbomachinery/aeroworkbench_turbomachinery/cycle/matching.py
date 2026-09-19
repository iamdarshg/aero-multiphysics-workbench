"""Coupled matching residuals for the generic gas-path/cycle solver.

Residuals are explicit and separately reported: shaft power/torque balance,
mass continuity, pressure/temperature continuity, spool-speed coupling, mixer
compatibility, nozzle flow/choking, bleed/cooling balance, and electric
mechanical/electrical balance. None of them is hidden inside the march.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from ..stations import StationState
from .components import MIX_KINDS, NOZZLE_KINDS, SPLIT_KINDS
from .contracts import CycleModelError
from .model import CycleModel, CycleShaftSpec

ELECTRIC_MOTOR = "electric_motor"
ELECTRIC_GENERATOR = "electric_generator"
MECHANICAL_LOAD = "mechanical_load"
MACHINE_COUPLING_KINDS: tuple[str, ...] = (
    ELECTRIC_MOTOR,
    ELECTRIC_GENERATOR,
    MECHANICAL_LOAD,
)


def requires_zero_balance(model: CycleModel, shaft: CycleShaftSpec) -> bool:
    """Whether a spool's net power is constrained to zero and must be matched.

    A spool with no machine couplings must balance its own work. A machine with
    a declared electrical/load power is a fixed external, so the spool must
    still balance. A purely adaptive motor/generator/load absorbs the deficit or
    surplus, so the spool's net power is an output, not a constraint.
    """

    machines = [c for c in shaft.couplings if c.kind in MACHINE_COUPLING_KINDS]
    if not machines:
        return True
    return any(
        coupling.target_node is not None
        and model.design.parameters_for(coupling.target_node).electric_power_w
        is not None
        for coupling in machines
    )


@dataclass(frozen=True, slots=True)
class ShaftPower:
    """One spool's power bookkeeping and residual."""

    shaft_id: str
    speed_rpm: float | None
    produced_w: float
    required_w: float
    mechanical_loss_w: float
    mechanical_load_w: float
    motor_input_w: float
    generator_load_w: float
    electrical_input_w: float
    electrical_output_w: float
    residual_w: float

    @property
    def signed_residual_fraction(self) -> float:
        scale = max(abs(self.produced_w), abs(self.required_w), 1.0)
        return self.residual_w / scale

    @property
    def residual_fraction(self) -> float:
        return abs(self.signed_residual_fraction)

    def canonical(self) -> dict[str, object]:
        return {
            "shaftId": self.shaft_id,
            "speedRpm": self.speed_rpm,
            "producedW": self.produced_w,
            "requiredW": self.required_w,
            "mechanicalLossW": self.mechanical_loss_w,
            "mechanicalLoadW": self.mechanical_load_w,
            "motorInputW": self.motor_input_w,
            "generatorLoadW": self.generator_load_w,
            "electricalInputW": self.electrical_input_w,
            "electricalOutputW": self.electrical_output_w,
            "residualW": self.residual_w,
            "residualFraction": self.residual_fraction,
        }


@dataclass(frozen=True, slots=True)
class MatchingResiduals:
    """Every coupled residual of one solved cycle, as relative measures."""

    shaft_power_fraction: tuple[tuple[str, float], ...]
    mass_continuity: float
    pressure_continuity: float
    temperature_continuity: float
    spool_speed: tuple[tuple[str, float], ...]
    mixer_compatibility: float
    nozzle_flow: float
    bleed_cooling: float
    electric_balance: tuple[tuple[str, float], ...]

    @property
    def matched_max(self) -> float:
        """The residuals the matching iteration drives to zero."""

        values = [value for _, value in self.shaft_power_fraction]
        values.extend(value for _, value in self.spool_speed)
        values.extend(value for _, value in self.electric_balance)
        return max(values, default=0.0)

    @property
    def max_residual(self) -> float:
        values = [self.matched_max]
        values.extend(
            [
                self.mass_continuity,
                self.pressure_continuity,
                self.temperature_continuity,
                self.mixer_compatibility,
                self.nozzle_flow,
                self.bleed_cooling,
            ]
        )
        return max(values, default=0.0)

    def converged(self, tolerance: float) -> bool:
        """Convergence of the matched residuals (not the physical diagnostics)."""

        return self.matched_max <= tolerance

    def canonical(self) -> dict[str, object]:
        return {
            "shaftPowerFraction": [[key, value] for key, value in self.shaft_power_fraction],
            "massContinuity": self.mass_continuity,
            "pressureContinuity": self.pressure_continuity,
            "temperatureContinuity": self.temperature_continuity,
            "spoolSpeed": [[key, value] for key, value in self.spool_speed],
            "mixerCompatibility": self.mixer_compatibility,
            "nozzleFlow": self.nozzle_flow,
            "bleedCooling": self.bleed_cooling,
            "electricBalance": [[key, value] for key, value in self.electric_balance],
            "maxResidual": self.max_residual,
        }


def _relative(numerator: float, scale: float) -> float:
    return abs(numerator) / max(abs(scale), 1e-9)


def _mass_flow(state: StationState, node_id: str) -> float:
    if state.mass_flow is None:
        raise CycleModelError(f"STATION_MASS_FLOW_REQUIRED:{node_id}")
    return state.mass_flow.value_si


def _total_pressure(state: StationState, node_id: str) -> float:
    if state.total_pressure is None:
        raise CycleModelError(f"STATION_TOTAL_PRESSURE_REQUIRED:{node_id}")
    return state.total_pressure.value_si


def _total_temperature(state: StationState, node_id: str) -> float:
    if state.total_temperature is None:
        raise CycleModelError(f"STATION_TOTAL_TEMPERATURE_REQUIRED:{node_id}")
    return state.total_temperature.value_si


def shaft_power(
    model: CycleModel,
    shaft: CycleShaftSpec,
    *,
    produced_w: float,
    required_w: float,
    speed_rpm: float | None,
) -> ShaftPower:
    """Assemble one spool's power balance from its components and couplings.

    A machine with a declared electrical power is a fixed load/source; without
    one it is sized to the shaft (it supplies or absorbs exactly the deficit or
    surplus). Mechanical loss is a declared fraction of the larger work term.
    """

    mechanical_loss = shaft.mechanical_loss_fraction * max(
        abs(produced_w), abs(required_w)
    )
    mechanical_load = 0.0
    fixed_motor_input = 0.0
    generator_load = 0.0
    electrical_input = 0.0
    electrical_output = 0.0
    has_motor = False
    has_generator = False
    has_mechanical_load = False
    motor_fixed = False
    generator_fixed = False
    load_fixed = False
    efficiency = 1.0
    for coupling in shaft.couplings:
        if coupling.kind not in MACHINE_COUPLING_KINDS:
            continue
        if coupling.target_node is None:
            continue
        parameters = model.design.parameters_for(coupling.target_node)
        efficiency = parameters.machine_efficiency or 1.0
        if not 0 < efficiency <= 1:
            raise CycleModelError(
                f"MACHINE_EFFICIENCY_OUT_OF_RANGE:{coupling.target_node}:{efficiency}"
            )
        electric = parameters.electric_power_w
        if coupling.kind == ELECTRIC_MOTOR:
            has_motor = True
            if electric is not None:
                motor_fixed = True
                fixed_motor_input += electric * efficiency
                electrical_input += electric
        elif coupling.kind == ELECTRIC_GENERATOR:
            has_generator = True
            if electric is not None:
                generator_fixed = True
                generator_load += electric / efficiency
                electrical_output += electric
        elif coupling.kind == MECHANICAL_LOAD:
            has_mechanical_load = True
            if electric is not None:
                load_fixed = True
                mechanical_load += electric

    motor_input = fixed_motor_input
    residual = (
        produced_w - required_w - mechanical_loss - mechanical_load - generator_load
        + motor_input
    )
    if has_motor and not motor_fixed:
        deficit = max(
            required_w + mechanical_loss + mechanical_load + generator_load - produced_w,
            0.0,
        )
        motor_input += deficit
        electrical_input += deficit / max(efficiency, 1e-9)
        residual += deficit
    if has_generator and not generator_fixed:
        surplus = max(residual, 0.0)
        generator_load += surplus
        electrical_output += surplus * max(efficiency, 1e-9)
        residual -= surplus
    if has_mechanical_load and not load_fixed:
        surplus = max(residual, 0.0)
        mechanical_load += surplus
        residual -= surplus
    return ShaftPower(
        shaft_id=shaft.shaft_id,
        speed_rpm=speed_rpm,
        produced_w=produced_w,
        required_w=required_w,
        mechanical_loss_w=mechanical_loss,
        mechanical_load_w=mechanical_load,
        motor_input_w=motor_input,
        generator_load_w=generator_load,
        electrical_input_w=electrical_input,
        electrical_output_w=electrical_output,
        residual_w=residual,
    )


def _split_continuity(
    model: CycleModel, edge_states: Mapping[str, StationState]
) -> tuple[float, float]:
    pressure_error = 0.0
    temperature_error = 0.0
    for node in model.nodes:
        if node.kind not in SPLIT_KINDS or not node.inlet_keys or not node.outlet_keys:
            continue
        inlet = edge_states.get(node.inlet_keys[0])
        if inlet is None:
            continue
        inlet_pressure = _total_pressure(inlet, node.node_id)
        inlet_temperature = _total_temperature(inlet, node.node_id)
        for key in node.outlet_keys:
            state = edge_states.get(key)
            if state is None:
                continue
            pressure_error = max(
                pressure_error,
                _relative(
                    _total_pressure(state, node.node_id) - inlet_pressure, inlet_pressure
                ),
            )
            temperature_error = max(
                temperature_error,
                _relative(
                    _total_temperature(state, node.node_id) - inlet_temperature,
                    inlet_temperature,
                ),
            )
    return pressure_error, temperature_error


def _mixer_compatibility(
    model: CycleModel, edge_states: Mapping[str, StationState]
) -> float:
    error = 0.0
    for node in model.nodes:
        if node.kind not in MIX_KINDS or len(node.inlet_keys) < 2:
            continue
        pressures = [
            _total_pressure(edge_states[key], node.node_id)
            for key in node.inlet_keys
            if key in edge_states
        ]
        if len(pressures) < 2:
            continue
        reference = max(pressures)
        error = max(error, _relative(max(pressures) - min(pressures), reference))
    return error


def _nozzle_flow(
    model: CycleModel, edge_states: Mapping[str, StationState]
) -> float:
    error = 0.0
    for node in model.nodes:
        if node.kind not in NOZZLE_KINDS or not node.outlet_keys:
            continue
        area = node.parameters.nozzle_exit_area_m2
        if area is None:
            continue
        outlet = edge_states.get(node.outlet_keys[0])
        if outlet is None or outlet.total_pressure is None or outlet.total_temperature is None:
            continue
        gas = model.design.gas
        pt = outlet.total_pressure.value_si
        tt = outlet.total_temperature.value_si
        if pt / (node.parameters.ambient_pressure_pa or 101325.0) < gas.critical_pressure_ratio:
            continue
        choked_flow = (
            pt
            * area
            * math.sqrt(gas.gamma / (gas.r_j_kg_k * tt))
            * (2.0 / (gas.gamma + 1.0)) ** ((gas.gamma + 1.0) / (2.0 * (gas.gamma - 1.0)))
        )
        if choked_flow <= 0:
            continue
        actual = _mass_flow(outlet, node.node_id)
        error = max(error, _relative(actual - choked_flow, choked_flow))
    return error


def _mass_continuity(
    model: CycleModel, edge_states: Mapping[str, StationState]
) -> tuple[float, float]:
    mass_error = 0.0
    bleed_cooling = 0.0
    for node in model.nodes:
        if not node.inlet_keys or not node.outlet_keys:
            continue
        inlet_mass = sum(
            _mass_flow(edge_states[key], node.node_id)
            for key in node.inlet_keys
            if key in edge_states
        )
        outlet_mass = sum(
            _mass_flow(edge_states[key], node.node_id)
            for key in node.outlet_keys
            if key in edge_states
        )
        if inlet_mass <= 0:
            continue
        error = _relative(outlet_mass - inlet_mass, inlet_mass)
        mass_error = max(mass_error, error)
        if node.kind in SPLIT_KINDS or node.kind in MIX_KINDS:
            bleed_cooling = max(bleed_cooling, error)
    return mass_error, bleed_cooling


def spool_speed_residuals(
    model: CycleModel, speeds_rpm: Mapping[str, float | None]
) -> tuple[tuple[str, float], ...]:
    """Geared/common-shaft speed coupling residuals."""

    residuals: list[tuple[str, float]] = []
    for shaft in model.shafts:
        for coupling in shaft.couplings:
            if coupling.target_shaft is None:
                continue
            source = speeds_rpm.get(shaft.shaft_id)
            target = speeds_rpm.get(coupling.target_shaft)
            if source is None or target is None:
                continue
            if coupling.kind == "geared":
                expected = source / (coupling.ratio or 1.0)
                residual = _relative(target - expected, expected)
            elif coupling.kind == "common_shaft":
                residual = _relative(target - source, source)
            else:
                continue
            residuals.append((f"{shaft.shaft_id}->{coupling.target_shaft}", residual))
    return tuple(residuals)


def compute_residuals(
    model: CycleModel,
    *,
    edge_states: Mapping[str, StationState],
    shaft_powers: tuple[ShaftPower, ...],
    speeds_rpm: Mapping[str, float | None],
) -> MatchingResiduals:
    """Compute every coupled residual for one marched cycle."""

    mass_error, bleed_cooling = _mass_continuity(model, edge_states)
    pressure_error, temperature_error = _split_continuity(model, edge_states)
    mixer_error = _mixer_compatibility(model, edge_states)
    nozzle_error = _nozzle_flow(model, edge_states)
    electric: list[tuple[str, float]] = []
    for power in shaft_powers:
        shaft = model.shaft(power.shaft_id)
        has_electric_spec = any(
            coupling.target_node is not None
            and model.design.parameters_for(coupling.target_node).electric_power_w
            is not None
            for coupling in shaft.couplings
        )
        if power.electrical_input_w > 0 or power.electrical_output_w > 0 or has_electric_spec:
            electric.append((power.shaft_id, power.residual_fraction))
    return MatchingResiduals(
        shaft_power_fraction=tuple(
            (power.shaft_id, power.residual_fraction) for power in shaft_powers
        ),
        mass_continuity=mass_error,
        pressure_continuity=pressure_error,
        temperature_continuity=temperature_error,
        spool_speed=spool_speed_residuals(model, speeds_rpm),
        mixer_compatibility=mixer_error,
        nozzle_flow=nozzle_error,
        bleed_cooling=bleed_cooling,
        electric_balance=tuple(electric),
    )


__all__ = [
    "MatchingResiduals",
    "ShaftPower",
    "compute_residuals",
    "shaft_power",
    "spool_speed_residuals",
]
