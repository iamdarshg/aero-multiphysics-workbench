"""Reusable component contracts for the generic gas-path/cycle graph.

Every component is the same shape: unit-bearing inlet station states in,
unit-bearing outlet station states out, plus shaft work, fuel flow, thrust, and
explicit warnings. The solver walks the graph in topological order and never
hard-codes a named architecture; a compressor, a splitter, or a recuperator is
just a node kind with a declared parameter set.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..stations import StationState, WorkingFluid
from ..units import Quantity
from .contracts import CycleModelError, OutOfEnvelopePolicy
from .gas import (
    GasProperties,
    compressor_exit_temperature,
    ideal_gas_density,
    turbine_exit_temperature,
    velocity_from_temperature_drop,
)
from .maps import OperatingMap

SOURCE_KINDS: tuple[str, ...] = ("ambient",)
PASSIVE_KINDS: tuple[str, ...] = (
    "inlet",
    "intake",
    "duct",
    "plenum",
    "stator_row",
    "diffuser",
    "turning_only",
)
WORK_ADDING_KINDS: tuple[str, ...] = (
    "compressor_stage",
    "fan_stage",
    "work_adding",
)
WORK_EXTRACTING_KINDS: tuple[str, ...] = (
    "turbine_stage",
    "expander_stage",
    "work_extracting",
)
HEAT_ADDITION_KINDS: tuple[str, ...] = ("combustor", "heat_addition")
HEAT_EXCHANGER_KINDS: tuple[str, ...] = (
    "heat_exchanger",
    "recuperator",
    "intercooler",
)
SPLIT_KINDS: tuple[str, ...] = (
    "splitter",
    "bypass_split",
    "core_split",
    "bleed_extract",
)
MIX_KINDS: tuple[str, ...] = (
    "mixer",
    "bypass_merge",
    "core_merge",
    "cooling_inject",
)
NOZZLE_KINDS: tuple[str, ...] = ("nozzle",)
EXHAUST_KINDS: tuple[str, ...] = ("exhaust",)

COMPONENT_KINDS: tuple[str, ...] = (
    *SOURCE_KINDS,
    *PASSIVE_KINDS,
    *WORK_ADDING_KINDS,
    *WORK_EXTRACTING_KINDS,
    *HEAT_ADDITION_KINDS,
    *HEAT_EXCHANGER_KINDS,
    *SPLIT_KINDS,
    *MIX_KINDS,
    *NOZZLE_KINDS,
    *EXHAUST_KINDS,
)


@dataclass(frozen=True, slots=True)
class ComponentParameters:
    """Union of optional parameters; a component only reads what it needs."""

    pressure_recovery: float | None = None
    pressure_ratio: float | None = None
    expansion_ratio: float | None = None
    isentropic_efficiency: float | None = None
    pressure_loss_fraction: float | None = None
    heat_addition_w: float | None = None
    exit_total_temperature_k: float | None = None
    fuel_lower_heating_value_j_kg: float | None = None
    combustion_efficiency: float | None = None
    effectiveness: float | None = None
    sink_temperature_k: float | None = None
    bleed_fraction: float | None = None
    split_fractions: tuple[float, ...] = ()
    mixer_pressure_loss_fraction: float | None = None
    nozzle_exit_area_m2: float | None = None
    ambient_pressure_pa: float | None = None
    corrected_speed: float | None = None
    corrected_flow: float | None = None
    component_map: OperatingMap | None = None
    machine_efficiency: float | None = None
    electric_power_w: float | None = None
    reference_pressure_pa: float = 101325.0
    reference_temperature_k: float = 288.15

    def canonical(self) -> dict[str, object]:
        return {
            "pressureRecovery": self.pressure_recovery,
            "pressureRatio": self.pressure_ratio,
            "expansionRatio": self.expansion_ratio,
            "isentropicEfficiency": self.isentropic_efficiency,
            "pressureLossFraction": self.pressure_loss_fraction,
            "heatAdditionW": self.heat_addition_w,
            "exitTotalTemperatureK": self.exit_total_temperature_k,
            "fuelLowerHeatingValueJkg": self.fuel_lower_heating_value_j_kg,
            "combustionEfficiency": self.combustion_efficiency,
            "effectiveness": self.effectiveness,
            "sinkTemperatureK": self.sink_temperature_k,
            "bleedFraction": self.bleed_fraction,
            "splitFractions": list(self.split_fractions),
            "mixerPressureLossFraction": self.mixer_pressure_loss_fraction,
            "nozzleExitAreaM2": self.nozzle_exit_area_m2,
            "ambientPressurePa": self.ambient_pressure_pa,
            "correctedSpeed": self.corrected_speed,
            "correctedFlow": self.corrected_flow,
            "machineEfficiency": self.machine_efficiency,
            "electricPowerW": self.electric_power_w,
            "referencePressurePa": self.reference_pressure_pa,
            "referenceTemperatureK": self.reference_temperature_k,
            "mapRevision": None
            if self.component_map is None
            else self.component_map.provenance.revision,
        }


@dataclass(frozen=True, slots=True)
class ComponentEvaluation:
    """One component's evaluated outlets and side quantities."""

    node_id: str
    kind: str
    outputs: tuple[tuple[str, StationState], ...]
    shaft_power_w: float = 0.0
    shaft_id: str | None = None
    fuel_flow_kg_s: float = 0.0
    thrust_n: float = 0.0
    choked: bool | None = None
    warnings: tuple[str, ...] = ()
    detail: str = ""
    used_map: bool = False

    def output_state(self, key: str) -> StationState:
        for candidate, state in self.outputs:
            if candidate == key:
                return state
        raise CycleModelError(f"COMPONENT_OUTPUT_MISSING:{self.node_id}:{key}")


def _q(value: float, unit: str) -> Quantity:
    return Quantity(value=value, unit=unit)


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


def _fluid(gas: GasProperties) -> WorkingFluid:
    return WorkingFluid(identity=gas.identity)


def _flow_state(
    gas: GasProperties,
    *,
    mass_flow_kg_s: float,
    total_pressure_pa: float,
    total_temperature_k: float,
    static_pressure_pa: float | None = None,
    static_temperature_k: float | None = None,
    velocity_m_s: float | None = None,
    mach: float | None = None,
    area_m2: float | None = None,
) -> StationState:
    from ..stations import AnnulusGeometryRef

    return StationState(
        mass_flow=_q(mass_flow_kg_s, "kg/s"),
        total_pressure=_q(total_pressure_pa, "Pa"),
        total_temperature=_q(total_temperature_k, "K"),
        static_pressure=None if static_pressure_pa is None else _q(static_pressure_pa, "Pa"),
        static_temperature=None
        if static_temperature_k is None
        else _q(static_temperature_k, "K"),
        velocity=None if velocity_m_s is None else _q(velocity_m_s, "m/s"),
        mach=None if mach is None else _q(mach, "dimensionless"),
        density=None
        if static_pressure_pa is None or static_temperature_k is None
        else _q(
            ideal_gas_density(
                pressure_pa=static_pressure_pa,
                temperature_k=static_temperature_k,
                r_j_kg_k=gas.r_j_kg_k,
            ),
            "kg/m3",
        ),
        fluid=_fluid(gas),
        annulus=None if area_m2 is None else AnnulusGeometryRef(area=_q(area_m2, "m2")),
    )


def _require_recovery(parameters: ComponentParameters, node_id: str) -> float:
    recovery = parameters.pressure_recovery
    if recovery is None:
        return 1.0
    if not 0 < recovery <= 1:
        raise CycleModelError(f"PRESSURE_RECOVERY_OUT_OF_RANGE:{node_id}:{recovery}")
    return recovery


def _split_fractions(
    parameters: ComponentParameters, node_id: str, outlet_count: int
) -> tuple[float, ...]:
    fractions = parameters.split_fractions
    if not fractions and parameters.bleed_fraction is not None and outlet_count == 2:
        bleed = parameters.bleed_fraction
        fractions = (1.0 - bleed, bleed)
    if not fractions and outlet_count == 1:
        fractions = (1.0,)
    if len(fractions) != outlet_count:
        raise CycleModelError(
            f"SPLIT_FRACTIONS_MUST_MATCH_OUTLETS:{node_id}:"
            f"{len(fractions)}!={outlet_count}"
        )
    for fraction in fractions:
        if not 0 <= fraction <= 1:
            raise CycleModelError(f"SPLIT_FRACTION_OUT_OF_RANGE:{node_id}:{fraction}")
    if abs(sum(fractions) - 1.0) > 1e-6:
        raise CycleModelError(f"SPLIT_FRACTIONS_MUST_SUM_TO_ONE:{node_id}")
    return fractions


def evaluate_component(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet_states: tuple[StationState, ...],
    outlet_keys: tuple[str, ...],
    shaft_id: str | None = None,
) -> ComponentEvaluation:
    """Evaluate one component against its inlet station states."""

    if kind not in COMPONENT_KINDS:
        raise CycleModelError(f"UNKNOWN_COMPONENT_KIND:{node_id}:{kind}")
    if not inlet_states and kind not in SOURCE_KINDS:
        raise CycleModelError(f"COMPONENT_REQUIRES_INLET:{node_id}")
    if kind in SOURCE_KINDS:
        raise CycleModelError(f"SOURCE_NODE_IS_A_BOUNDARY_NOT_A_COMPONENT:{node_id}")
    if not outlet_keys:
        if kind in EXHAUST_KINDS:
            return ComponentEvaluation(
                node_id=node_id, kind=kind, outputs=(), detail="terminal exhaust"
            )
        raise CycleModelError(f"COMPONENT_REQUIRES_OUTLET:{node_id}")

    if kind in PASSIVE_KINDS or kind in EXHAUST_KINDS:
        return _passive(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlet=inlet_states[0],
            outlet_key=outlet_keys[0],
        )
    if kind in WORK_ADDING_KINDS:
        return _work_adding(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlet=inlet_states[0],
            outlet_key=outlet_keys[0],
            shaft_id=shaft_id,
        )
    if kind in WORK_EXTRACTING_KINDS:
        return _work_extracting(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlet=inlet_states[0],
            outlet_key=outlet_keys[0],
            shaft_id=shaft_id,
        )
    if kind in HEAT_ADDITION_KINDS:
        return _heat_addition(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlet=inlet_states[0],
            outlet_key=outlet_keys[0],
        )
    if kind in HEAT_EXCHANGER_KINDS:
        return _heat_exchanger(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlet=inlet_states[0],
            outlet_key=outlet_keys[0],
        )
    if kind in SPLIT_KINDS:
        return _split(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlet=inlet_states[0],
            outlet_keys=outlet_keys,
        )
    if kind in MIX_KINDS:
        return _mix(
            node_id=node_id,
            kind=kind,
            parameters=parameters,
            gas=gas,
            inlets=inlet_states,
            outlet_key=outlet_keys[0],
        )
    return _nozzle(
        node_id=node_id,
        kind=kind,
        parameters=parameters,
        gas=gas,
        inlet=inlet_states[0],
        outlet_key=outlet_keys[0],
    )


def _passive(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_key: str,
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    loss = parameters.pressure_loss_fraction or 0.0
    if not 0 <= loss < 1:
        raise CycleModelError(f"PRESSURE_LOSS_OUT_OF_RANGE:{node_id}:{loss}")
    recovery = _require_recovery(parameters, node_id)
    out = _flow_state(
        gas,
        mass_flow_kg_s=mdot,
        total_pressure_pa=pt * recovery * (1.0 - loss),
        total_temperature_k=tt,
    )
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=((outlet_key, out),),
        detail="passive total-pressure element",
    )


def _work_adding(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_key: str,
    shaft_id: str | None,
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    warnings: list[str] = []
    used_map = False
    if parameters.component_map is not None:
        if parameters.corrected_speed is None or parameters.corrected_flow is None:
            raise CycleModelError(f"MAP_COMPONENT_NEEDS_SPEED_AND_FLOW:{node_id}")
        evaluation = parameters.component_map.evaluate(
            parameters.corrected_speed,
            parameters.corrected_flow,
            OutOfEnvelopePolicy.FAIL,
        )
        pressure_ratio = evaluation.pressure_ratio
        efficiency = evaluation.efficiency
        warnings.extend(evaluation.warnings)
        used_map = True
    else:
        if parameters.pressure_ratio is None or parameters.isentropic_efficiency is None:
            raise CycleModelError(f"COMPRESSOR_REQUIRES_MAP_OR_PRELIMINARY_DESIGN:{node_id}")
        pressure_ratio = parameters.pressure_ratio
        efficiency = parameters.isentropic_efficiency
    exit_tt = compressor_exit_temperature(
        gas,
        inlet_total_temperature_k=tt,
        pressure_ratio=pressure_ratio,
        isentropic_efficiency=efficiency,
    )
    exit_pt = pt * pressure_ratio
    power = mdot * gas.cp_j_kg_k * (exit_tt - tt)
    out = _flow_state(
        gas,
        mass_flow_kg_s=mdot,
        total_pressure_pa=exit_pt,
        total_temperature_k=exit_tt,
    )
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=((outlet_key, out),),
        shaft_power_w=-power,
        shaft_id=shaft_id,
        warnings=tuple(warnings),
        detail=(
            f"map pressure ratio {pressure_ratio:.5g}"
            if used_map
            else f"preliminary-design pressure ratio {pressure_ratio:.5g}"
        ),
        used_map=used_map,
    )


def _work_extracting(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_key: str,
    shaft_id: str | None,
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    warnings: list[str] = []
    used_map = False
    if parameters.component_map is not None:
        if parameters.corrected_speed is None or parameters.corrected_flow is None:
            raise CycleModelError(f"MAP_COMPONENT_NEEDS_SPEED_AND_FLOW:{node_id}")
        evaluation = parameters.component_map.evaluate(
            parameters.corrected_speed,
            parameters.corrected_flow,
            OutOfEnvelopePolicy.FAIL,
        )
        expansion_ratio = evaluation.pressure_ratio
        efficiency = evaluation.efficiency
        warnings.extend(evaluation.warnings)
        used_map = True
    else:
        if parameters.expansion_ratio is None or parameters.isentropic_efficiency is None:
            raise CycleModelError(
                f"TURBINE_REQUIRES_MAP_OR_PRELIMINARY_DESIGN:{node_id}"
            )
        expansion_ratio = parameters.expansion_ratio
        efficiency = parameters.isentropic_efficiency
    exit_tt = turbine_exit_temperature(
        gas,
        inlet_total_temperature_k=tt,
        expansion_ratio=expansion_ratio,
        isentropic_efficiency=efficiency,
    )
    exit_pt = pt / expansion_ratio
    power = mdot * gas.cp_j_kg_k * (tt - exit_tt)
    out = _flow_state(
        gas,
        mass_flow_kg_s=mdot,
        total_pressure_pa=exit_pt,
        total_temperature_k=exit_tt,
    )
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=((outlet_key, out),),
        shaft_power_w=power,
        shaft_id=shaft_id,
        warnings=tuple(warnings),
        detail=(
            f"map expansion ratio {expansion_ratio:.5g}"
            if used_map
            else f"preliminary-design expansion ratio {expansion_ratio:.5g}"
        ),
        used_map=used_map,
    )


def _heat_addition(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_key: str,
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    loss = parameters.pressure_loss_fraction or 0.0
    if not 0 <= loss < 1:
        raise CycleModelError(f"PRESSURE_LOSS_OUT_OF_RANGE:{node_id}:{loss}")
    if parameters.exit_total_temperature_k is not None:
        exit_tt = parameters.exit_total_temperature_k
        if exit_tt <= tt:
            raise CycleModelError(
                f"HEAT_ADDITION_EXIT_NOT_HOTTER_THAN_INLET:{node_id}:{exit_tt}<={tt}"
            )
        heat = mdot * gas.cp_j_kg_k * (exit_tt - tt)
    elif parameters.heat_addition_w is not None:
        heat = parameters.heat_addition_w
        if heat <= 0:
            raise CycleModelError(f"HEAT_ADDITION_MUST_BE_POSITIVE:{node_id}")
        exit_tt = tt + heat / (mdot * gas.cp_j_kg_k)
    else:
        raise CycleModelError(f"COMBUSTOR_REQUIRES_HEAT_INPUT:{node_id}")
    fuel_flow = 0.0
    if (
        parameters.fuel_lower_heating_value_j_kg is not None
        and parameters.combustion_efficiency is not None
    ):
        denominator = (
            parameters.combustion_efficiency * parameters.fuel_lower_heating_value_j_kg
        )
        if denominator <= 0:
            raise CycleModelError(f"COMBUSTOR_NEEDS_POSITIVE_HEAT_OF_REACTION:{node_id}")
        fuel_flow = heat / denominator
    out = _flow_state(
        gas,
        mass_flow_kg_s=mdot,
        total_pressure_pa=pt * (1.0 - loss),
        total_temperature_k=exit_tt,
    )
    warnings: tuple[str, ...] = ()
    if fuel_flow == 0.0:
        warnings = ("no fuel lower heating value declared; fuel flow not resolved",)
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=((outlet_key, out),),
        fuel_flow_kg_s=fuel_flow,
        warnings=warnings,
        detail=f"heat addition {heat:.6g} W",
    )


def _heat_exchanger(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_key: str,
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    effectiveness = parameters.effectiveness
    sink = parameters.sink_temperature_k
    if effectiveness is None or sink is None:
        raise CycleModelError(f"HEAT_EXCHANGER_NEEDS_EFFECTIVENESS_AND_SINK:{node_id}")
    if not 0 <= effectiveness <= 1:
        raise CycleModelError(f"HEAT_EXCHANGER_EFFECTIVENESS_OUT_OF_RANGE:{node_id}")
    exit_tt = tt + effectiveness * (sink - tt)
    loss = parameters.pressure_loss_fraction or 0.0
    if not 0 <= loss < 1:
        raise CycleModelError(f"PRESSURE_LOSS_OUT_OF_RANGE:{node_id}:{loss}")
    out = _flow_state(
        gas,
        mass_flow_kg_s=mdot,
        total_pressure_pa=pt * (1.0 - loss),
        total_temperature_k=exit_tt,
    )
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=((outlet_key, out),),
        detail=(
            "single-stream effectiveness heat exchanger against a declared sink; "
            "no two-stream recuperator network"
        ),
    )


def _split(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_keys: tuple[str, ...],
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    fractions = _split_fractions(parameters, node_id, len(outlet_keys))
    outputs = tuple(
        (
            key,
            _flow_state(
                gas,
                mass_flow_kg_s=mdot * fraction,
                total_pressure_pa=pt,
                total_temperature_k=tt,
            ),
        )
        for key, fraction in zip(outlet_keys, fractions, strict=True)
    )
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=outputs,
        detail=f"split fractions {fractions}",
    )


def _mix(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlets: tuple[StationState, ...],
    outlet_key: str,
) -> ComponentEvaluation:
    if not inlets:
        raise CycleModelError(f"MIXER_REQUIRES_INLET:{node_id}")
    mass_flows = [_mass_flow(state, node_id) for state in inlets]
    total = sum(mass_flows)
    if total <= 0:
        raise CycleModelError(f"MIXER_TOTAL_MASS_FLOW_MUST_BE_POSITIVE:{node_id}")
    enthalpy = sum(
        mdot * gas.cp_j_kg_k * _total_temperature(state, node_id)
        for mdot, state in zip(mass_flows, inlets, strict=True)
    )
    tt = enthalpy / (total * gas.cp_j_kg_k)
    pt = sum(
        mdot * _total_pressure(state, node_id)
        for mdot, state in zip(mass_flows, inlets, strict=True)
    ) / total
    loss = parameters.mixer_pressure_loss_fraction
    if loss is None:
        loss = parameters.pressure_loss_fraction or 0.0
    if not 0 <= loss < 1:
        raise CycleModelError(f"PRESSURE_LOSS_OUT_OF_RANGE:{node_id}:{loss}")
    pt *= 1.0 - loss
    if len(inlets) > 1:
        pressures = [_total_pressure(state, node_id) for state in inlets]
        spread = (max(pressures) - min(pressures)) / max(max(pressures), 1e-9)
        if spread > 0.05:
            return ComponentEvaluation(
                node_id=node_id,
                kind=kind,
                outputs=(
                    (
                        outlet_key,
                        _flow_state(
                            gas,
                            mass_flow_kg_s=total,
                            total_pressure_pa=pt,
                            total_temperature_k=tt,
                        ),
                    ),
                ),
                warnings=(
                    f"mixer inlet total pressures differ by {spread * 100:.2f}%",
                ),
                detail="mass/enthalpy mixing",
            )
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=(
            (
                outlet_key,
                _flow_state(
                    gas,
                    mass_flow_kg_s=total,
                    total_pressure_pa=pt,
                    total_temperature_k=tt,
                ),
            ),
        ),
        detail="mass/enthalpy mixing",
    )


def _nozzle(
    *,
    node_id: str,
    kind: str,
    parameters: ComponentParameters,
    gas: GasProperties,
    inlet: StationState,
    outlet_key: str,
) -> ComponentEvaluation:
    mdot = _mass_flow(inlet, node_id)
    pt = _total_pressure(inlet, node_id)
    tt = _total_temperature(inlet, node_id)
    loss = parameters.pressure_loss_fraction or 0.0
    if not 0 <= loss < 1:
        raise CycleModelError(f"PRESSURE_LOSS_OUT_OF_RANGE:{node_id}:{loss}")
    pt *= 1.0 - loss
    ambient = parameters.ambient_pressure_pa or 101325.0
    area = parameters.nozzle_exit_area_m2
    critical = gas.critical_pressure_ratio
    if pt / ambient >= critical:
        choked = True
        static_p = pt / critical
        static_t = tt * 2.0 / (gas.gamma + 1.0)
        mach = 1.0
    else:
        choked = False
        static_p = ambient
        static_t = tt * (ambient / pt) ** gas.exponent
        mach = math.sqrt(
            max(2.0 / (gas.gamma - 1.0) * ((pt / ambient) ** gas.exponent - 1.0), 0.0)
        )
    velocity = velocity_from_temperature_drop(
        gas, total_temperature_k=tt, static_temperature_k=static_t
    )
    if not math.isfinite(velocity):
        velocity = 0.0
    thrust = mdot * velocity + (static_p - ambient) * (area or 0.0)
    out = _flow_state(
        gas,
        mass_flow_kg_s=mdot,
        total_pressure_pa=pt,
        total_temperature_k=tt,
        static_pressure_pa=static_p,
        static_temperature_k=static_t,
        velocity_m_s=velocity,
        mach=mach,
        area_m2=area,
    )
    warnings: tuple[str, ...] = ()
    if choked:
        warnings = ("nozzle is choked; exit static state is sonic",)
    return ComponentEvaluation(
        node_id=node_id,
        kind=kind,
        outputs=((outlet_key, out),),
        thrust_n=thrust,
        choked=choked,
        warnings=warnings,
        detail=f"converging nozzle, exit Mach {mach:.4g}",
    )


__all__ = [
    "COMPONENT_KINDS",
    "ComponentEvaluation",
    "ComponentParameters",
    "EXHAUST_KINDS",
    "HEAT_ADDITION_KINDS",
    "HEAT_EXCHANGER_KINDS",
    "MIX_KINDS",
    "NOZZLE_KINDS",
    "PASSIVE_KINDS",
    "SOURCE_KINDS",
    "SPLIT_KINDS",
    "WORK_ADDING_KINDS",
    "WORK_EXTRACTING_KINDS",
    "evaluate_component",
]
