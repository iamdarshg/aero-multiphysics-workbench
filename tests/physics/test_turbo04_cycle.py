"""TURBO 04: generic thermodynamic cycle and multi-spool matching.

The analytical screening solver is cheap and explicitly labelled. Map validity
and shaft/energy closure are explicit residuals. Electric and combustion-driven
rotary systems share the same station/spool contracts. The generic OpenMDAO
component network executes for real and labels itself separately; pyCycle is
capability-gated and fails closed when absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_turbomachinery import architecture_from_payload
from aeroworkbench_turbomachinery.cycle import (
    AIR,
    COMBUSTION_GAS,
    CycleCapabilityUnavailable,
    CycleDesign,
    CycleModelError,
    CycleParserError,
    OutOfEnvelopePolicy,
    build_screening_map,
    compile_cycle_model,
    edge_key,
    evaluate_component,
    ideal_brayton_screening,
    parse_pycycle_result,
    prepare_pycycle_case,
    probe_cycle_engine,
    probe_cycle_engines,
    pycycle_supported_topology,
    solve_cycle,
    solve_with_openmdao,
    solve_with_pycycle,
)
from aeroworkbench_turbomachinery.cycle.components import ComponentParameters
from aeroworkbench_turbomachinery.cycle.maps import MapLine, MapProvenance, OperatingMap

_ARCH_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "fixtures"
_CYCLE_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "cycle"


def _load_arch(directory: Path, name: str) -> Any:
    return architecture_from_payload(json.loads((directory / name).read_text(encoding="utf-8")))


def _arch(name: str) -> Any:
    return _load_arch(_ARCH_FIXTURES, name)


def _params(**overrides: object) -> ComponentParameters:
    return ComponentParameters(**overrides)  # type: ignore[arg-type]


def _single_fan_design() -> CycleDesign:
    arch = _arch("single_ducted_fan.json")
    return CycleDesign(
        architecture=arch,
        component_parameters=(
            ("inlet", _params(pressure_recovery=0.94)),
            ("fan", _params(pressure_ratio=1.158, isentropic_efficiency=0.90)),
            ("nozzle", _params(ambient_pressure_pa=101325.0)),
            ("motor", _params(machine_efficiency=0.95)),
        ),
        gas=AIR,
        ambient_total_pressure_pa=101325.0,
        ambient_total_temperature_k=288.15,
        mass_flow_kg_s=4.5,
    )


def _core_design() -> CycleDesign:
    arch = _arch("core_compressor_combustor_turbine.json")
    return CycleDesign(
        architecture=arch,
        component_parameters=(
            ("inlet", _params(pressure_recovery=0.977)),
            ("compressor", _params(pressure_ratio=8.0, isentropic_efficiency=0.86)),
            (
                "combustor",
                _params(
                    exit_total_temperature_k=1450.0,
                    pressure_loss_fraction=0.04,
                    fuel_lower_heating_value_j_kg=43.0e6,
                    combustion_efficiency=0.99,
                ),
            ),
            ("turbine", _params(expansion_ratio=2.714, isentropic_efficiency=0.90)),
            ("nozzle", _params(ambient_pressure_pa=101325.0)),
            ("load", _params(electric_power_w=0.0)),
        ),
        gas=COMBUSTION_GAS,
        ambient_total_pressure_pa=101325.0,
        ambient_total_temperature_k=288.15,
        mass_flow_kg_s=12.0,
    )


def _free_turbine_design() -> CycleDesign:
    arch = _arch("free_power_turbine.json")
    return CycleDesign(
        architecture=arch,
        component_parameters=(
            ("inlet", _params(pressure_recovery=0.977)),
            ("compressor", _params(pressure_ratio=5.25, isentropic_efficiency=0.85)),
            (
                "combustor",
                _params(
                    exit_total_temperature_k=1300.0,
                    pressure_loss_fraction=0.038,
                    fuel_lower_heating_value_j_kg=43.0e6,
                    combustion_efficiency=0.99,
                ),
            ),
            (
                "gas-gen-turbine",
                _params(expansion_ratio=2.381, isentropic_efficiency=0.90),
            ),
            ("free-turbine", _params(expansion_ratio=1.909, isentropic_efficiency=0.90)),
            ("nozzle", _params(ambient_pressure_pa=101325.0)),
            ("generator", _params(machine_efficiency=0.97)),
        ),
        gas=COMBUSTION_GAS,
        ambient_total_pressure_pa=101325.0,
        ambient_total_temperature_k=288.15,
        mass_flow_kg_s=2.4,
    )


def _multi_spool_design(name: str) -> CycleDesign:
    arch = _load_arch(_CYCLE_FIXTURES, name)
    return CycleDesign(
        architecture=arch,
        component_parameters=(
            ("inlet", _params(pressure_recovery=0.977)),
            ("fan", _params(pressure_ratio=1.162, isentropic_efficiency=0.89)),
            ("bypass-split", _params(split_fractions=(0.75, 0.25))),
            ("bypass-duct", _params(pressure_loss_fraction=0.018)),
            ("core-split", _params(split_fractions=(1.0,))),
            ("lpc", _params(pressure_ratio=1.5, isentropic_efficiency=0.88)),
            ("hpc", _params(pressure_ratio=2.1, isentropic_efficiency=0.86)),
            (
                "combustor",
                _params(
                    exit_total_temperature_k=1200.0,
                    pressure_loss_fraction=0.05,
                    fuel_lower_heating_value_j_kg=43.0e6,
                    combustion_efficiency=0.99,
                ),
            ),
            ("hpt", _params(expansion_ratio=2.0, isentropic_efficiency=0.90)),
            ("lpt", _params(expansion_ratio=1.64, isentropic_efficiency=0.90)),
            ("nozzle", _params(ambient_pressure_pa=101325.0)),
        ),
        gas=AIR,
        ambient_total_pressure_pa=101325.0,
        ambient_total_temperature_k=288.15,
        mass_flow_kg_s=120.0,
    )


def _recuperated_design() -> CycleDesign:
    arch = _load_arch(_CYCLE_FIXTURES, "recuperated_core.json")
    return CycleDesign(
        architecture=arch,
        component_parameters=(
            ("inlet", _params(pressure_recovery=0.977)),
            ("compressor", _params(pressure_ratio=4.0, isentropic_efficiency=0.85)),
            (
                "recuperator",
                _params(
                    effectiveness=0.7,
                    sink_temperature_k=900.0,
                    pressure_loss_fraction=0.01,
                ),
            ),
            (
                "combustor",
                _params(
                    exit_total_temperature_k=1250.0,
                    pressure_loss_fraction=0.05,
                    fuel_lower_heating_value_j_kg=43.0e6,
                    combustion_efficiency=0.99,
                ),
            ),
            ("turbine", _params(expansion_ratio=2.66, isentropic_efficiency=0.90)),
            ("nozzle", _params(ambient_pressure_pa=101325.0)),
            ("load", _params()),
        ),
        gas=COMBUSTION_GAS,
        ambient_total_pressure_pa=101325.0,
        ambient_total_temperature_k=288.15,
        mass_flow_kg_s=3.0,
    )


# -- A. generic component graph ----------------------------------------------


def test_turbo04_compile_is_topological_and_deterministic() -> None:
    design = _single_fan_design()
    model = compile_cycle_model(design)
    assert model.source_node_ids == ("ambient",)
    assert model.order[0] == "ambient"
    assert model.digest == compile_cycle_model(design).digest
    kinds = {node.kind for node in model.nodes}
    assert {"inlet", "fan_stage", "nozzle", "exhaust"} <= kinds
    fan = model.node("fan")
    assert fan.shaft_id == "fan-spool"
    assert fan.is_work_adding
    assert len(fan.outlet_keys) == 1


def test_turbo04_edge_keys_are_unique_and_sanitized() -> None:
    arch = _arch("multi_spool_bypass.json")
    keys = [edge_key(edge) for edge in arch.edges]
    assert len(keys) == len(set(keys))
    assert all(key.replace("_", "").isalnum() for key in keys)


def test_turbo04_splitter_and_mixer_preserve_mass_and_enthalpy() -> None:
    from aeroworkbench_turbomachinery import StationState
    from aeroworkbench_turbomachinery.units import Quantity

    def state(mass: float, tt: float) -> StationState:
        return StationState(
            mass_flow=Quantity(value=mass, unit="kg/s"),
            total_pressure=Quantity(value=200000.0, unit="Pa"),
            total_temperature=Quantity(value=tt, unit="K"),
        )

    split = evaluate_component(
        node_id="s",
        kind="splitter",
        parameters=_params(split_fractions=(0.6, 0.4)),
        gas=AIR,
        inlet_states=(state(10.0, 800.0),),
        outlet_keys=("a", "b"),
    )
    assert split.output_state("a").mass_flow is not None
    assert split.output_state("a").mass_flow.value_si == pytest.approx(6.0)
    assert split.output_state("b").mass_flow.value_si == pytest.approx(4.0)

    mixed = evaluate_component(
        node_id="m",
        kind="mixer",
        parameters=_params(),
        gas=AIR,
        inlet_states=(state(6.0, 900.0), state(4.0, 500.0)),
        outlet_keys=("out",),
    )
    exit_state = mixed.output_state("out")
    assert exit_state.mass_flow.value_si == pytest.approx(10.0)
    assert exit_state.total_temperature.value_si == pytest.approx(740.0)


def test_turbo04_compressor_turbine_and_combustor_contracts() -> None:
    from aeroworkbench_turbomachinery import StationState
    from aeroworkbench_turbomachinery.units import Quantity

    inlet = StationState(
        mass_flow=Quantity(value=10.0, unit="kg/s"),
        total_pressure=Quantity(value=100000.0, unit="Pa"),
        total_temperature=Quantity(value=288.15, unit="K"),
    )
    compressor = evaluate_component(
        node_id="c",
        kind="compressor_stage",
        parameters=_params(pressure_ratio=4.0, isentropic_efficiency=0.85),
        gas=AIR,
        inlet_states=(inlet,),
        outlet_keys=("out",),
        shaft_id="spool",
    )
    assert compressor.output_state("out").total_pressure.value_si == pytest.approx(400000.0)
    assert compressor.shaft_power_w < 0.0
    assert compressor.shaft_id == "spool"

    combustor = evaluate_component(
        node_id="b",
        kind="combustor",
        parameters=_params(
            exit_total_temperature_k=1450.0,
            pressure_loss_fraction=0.05,
            fuel_lower_heating_value_j_kg=43.0e6,
            combustion_efficiency=0.99,
        ),
        gas=COMBUSTION_GAS,
        inlet_states=(compressor.output_state("out"),),
        outlet_keys=("out",),
    )
    assert combustor.fuel_flow_kg_s > 0.0
    assert combustor.output_state("out").total_temperature.value_si == pytest.approx(1450.0)

    turbine = evaluate_component(
        node_id="t",
        kind="turbine_stage",
        parameters=_params(expansion_ratio=2.0, isentropic_efficiency=0.9),
        gas=COMBUSTION_GAS,
        inlet_states=(combustor.output_state("out"),),
        outlet_keys=("out",),
        shaft_id="spool",
    )
    assert turbine.shaft_power_w > 0.0
    assert turbine.output_state("out").total_pressure.value_si == pytest.approx(
        400000.0 * 0.95 / 2.0
    )


def test_turbo04_nozzle_chokes_above_critical_ratio() -> None:
    from aeroworkbench_turbomachinery import StationState
    from aeroworkbench_turbomachinery.units import Quantity

    inlet = StationState(
        mass_flow=Quantity(value=1.0, unit="kg/s"),
        total_pressure=Quantity(value=500000.0, unit="Pa"),
        total_temperature=Quantity(value=900.0, unit="K"),
    )
    nozzle = evaluate_component(
        node_id="n",
        kind="nozzle",
        parameters=_params(ambient_pressure_pa=101325.0, nozzle_exit_area_m2=0.01),
        gas=COMBUSTION_GAS,
        inlet_states=(inlet,),
        outlet_keys=("out",),
    )
    assert nozzle.choked is True
    exit_state = nozzle.output_state("out")
    assert exit_state.mach.value_si == pytest.approx(1.0)
    assert nozzle.thrust_n > 0.0


def test_turbo04_bleed_and_cooling_contracts() -> None:
    from aeroworkbench_turbomachinery import StationState
    from aeroworkbench_turbomachinery.units import Quantity

    def state(mass: float, tt: float) -> StationState:
        return StationState(
            mass_flow=Quantity(value=mass, unit="kg/s"),
            total_pressure=Quantity(value=500000.0, unit="Pa"),
            total_temperature=Quantity(value=tt, unit="K"),
        )

    bleed = evaluate_component(
        node_id="bleed",
        kind="bleed_extract",
        parameters=_params(bleed_fraction=0.1),
        gas=AIR,
        inlet_states=(state(10.0, 700.0),),
        outlet_keys=("core", "coolant"),
    )
    assert bleed.output_state("core").mass_flow.value_si == pytest.approx(9.0)
    assert bleed.output_state("coolant").mass_flow.value_si == pytest.approx(1.0)

    cooling = evaluate_component(
        node_id="cooling",
        kind="cooling_inject",
        parameters=_params(),
        gas=AIR,
        inlet_states=(bleed.output_state("core"), bleed.output_state("coolant")),
        outlet_keys=("out",),
    )
    exit_state = cooling.output_state("out")
    assert exit_state.mass_flow.value_si == pytest.approx(10.0)
    assert exit_state.total_temperature.value_si == pytest.approx(700.0)


def test_turbo04_recuperator_uses_effectiveness_and_sink() -> None:
    from aeroworkbench_turbomachinery import StationState
    from aeroworkbench_turbomachinery.units import Quantity

    inlet = StationState(
        mass_flow=Quantity(value=3.0, unit="kg/s"),
        total_pressure=Quantity(value=400000.0, unit="Pa"),
        total_temperature=Quantity(value=500.0, unit="K"),
    )
    recuperator = evaluate_component(
        node_id="r",
        kind="recuperator",
        parameters=_params(
            effectiveness=0.5, sink_temperature_k=900.0, pressure_loss_fraction=0.02
        ),
        gas=AIR,
        inlet_states=(inlet,),
        outlet_keys=("out",),
    )
    exit_state = recuperator.output_state("out")
    assert exit_state.total_temperature.value_si == pytest.approx(700.0)
    assert exit_state.total_pressure.value_si == pytest.approx(392000.0)


# -- D. generic map contract --------------------------------------------------


def test_turbo04_map_evaluates_design_point_and_boundaries() -> None:
    component_map = build_screening_map(
        machine="compressor",
        design_corrected_speed=1.0,
        design_corrected_flow=1.0,
        design_pressure_ratio=2.0,
        design_efficiency=0.88,
    )
    evaluation = component_map.evaluate(1.0, 1.0)
    assert evaluation.pressure_ratio == pytest.approx(2.0)
    assert evaluation.efficiency == pytest.approx(0.88)
    assert evaluation.extrapolated is False

    near_surge = component_map.evaluate(1.0, 0.75)
    assert near_surge.near_surge is True
    near_choke = component_map.evaluate(1.0, 1.2)
    assert near_choke.near_choke is True


def test_turbo04_map_never_silently_extrapolates() -> None:
    component_map = build_screening_map(
        machine="compressor",
        design_corrected_speed=1.0,
        design_corrected_flow=1.0,
        design_pressure_ratio=2.0,
        design_efficiency=0.88,
    )
    with pytest.raises(CycleModelError, match="MAP_OUT_OF_ENVELOPE"):
        component_map.evaluate(5.0, 1.0)
    with pytest.raises(CycleModelError, match="MAP_OUT_OF_ENVELOPE"):
        component_map.evaluate(1.0, 50.0)

    clamped = component_map.evaluate(5.0, 50.0, OutOfEnvelopePolicy.CLAMP)
    assert clamped.clamped
    assert clamped.extrapolated is False
    assert clamped.corrected_speed == pytest.approx(1.15)


def test_turbo04_map_pressure_ratio_inversion_round_trips() -> None:
    component_map = build_screening_map(
        machine="turbine",
        design_corrected_speed=1.0,
        design_corrected_flow=1.0,
        design_pressure_ratio=2.5,
        design_efficiency=0.9,
    )
    flow = component_map.flow_for_pressure_ratio(1.0, 2.5)
    evaluation = component_map.evaluate(1.0, flow)
    assert evaluation.pressure_ratio == pytest.approx(2.5, rel=1e-6)


def test_turbo04_map_contract_rejects_bad_lines() -> None:
    with pytest.raises(CycleModelError):
        MapLine(
            corrected_speed=1.0,
            corrected_flows=(1.0, 2.0),
            pressure_ratios=(2.0,),
            efficiencies=(0.9, 0.9),
            surge_corrected_flow=1.0,
            choke_corrected_flow=2.0,
        )
    with pytest.raises(CycleModelError):
        MapLine(
            corrected_speed=1.0,
            corrected_flows=(2.0, 1.0),
            pressure_ratios=(2.0, 2.0),
            efficiencies=(0.9, 0.9),
            surge_corrected_flow=1.0,
            choke_corrected_flow=2.0,
        )
    with pytest.raises(CycleModelError):
        OperatingMap(
            machine="compressor",
            lines=(
                MapLine(1.0, (1.0,), (2.0,), (0.9,), 1.0, 1.0),
                MapLine(1.0, (1.0,), (2.0,), (0.9,), 1.0, 1.0),
            ),
            provenance=MapProvenance(source="s", revision="r"),
        )


# -- E. architecture families share the same contracts ------------------------


def test_turbo04_every_architecture_family_compiles() -> None:
    for design in (
        _single_fan_design(),
        _core_design(),
        _free_turbine_design(),
        _multi_spool_design("two_spool_bypass_consistent.json"),
        _recuperated_design(),
    ):
        model = compile_cycle_model(design)
        assert model.order
        assert model.shafts


# -- B/C. analytical march and matching ---------------------------------------


def test_turbo04_driven_fan_solves_with_adaptive_motor() -> None:
    result = solve_cycle(compile_cycle_model(_single_fan_design()))
    assert result.fidelity == "analytical-screening"
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.provenance.solver_name is None
    fan_shaft = result.shaft("fan-spool")
    assert fan_shaft.required_w > 0.0
    assert fan_shaft.residual_fraction == pytest.approx(0.0, abs=1e-9)
    assert fan_shaft.electrical_input_w > fan_shaft.required_w
    assert result.residuals.mass_continuity == pytest.approx(0.0, abs=1e-9)
    assert result.units()["s1.totalPressure"] == "Pa"


def test_turbo04_single_spool_core_matches_shaft_power() -> None:
    result = solve_cycle(compile_cycle_model(_core_design()))
    assert result.converged
    shaft = result.shaft("core-spool")
    assert shaft.residual_fraction <= 1e-6
    assert shaft.produced_w > shaft.required_w
    assert shaft.produced_w - shaft.required_w == pytest.approx(
        shaft.mechanical_loss_w, rel=1e-4, abs=1.0
    )
    assert result.fuel_flow_kg_s > 0.0
    assert result.residuals.max_residual <= 1e-6
    assert result.validity.passed


def test_turbo04_free_power_turbine_generates_electricity() -> None:
    result = solve_cycle(compile_cycle_model(_free_turbine_design()))
    assert result.converged
    gas_gen = result.shaft("gas-gen-spool")
    assert gas_gen.residual_fraction <= 1e-6
    power_spool = result.shaft("power-spool")
    assert power_spool.generator_load_w > 0.0
    assert power_spool.electrical_output_w > 0.0
    assert power_spool.electrical_output_w < power_spool.produced_w


def test_turbo04_two_spool_bypass_matches_both_spools() -> None:
    design = _multi_spool_design("two_spool_bypass_consistent.json")
    result = solve_cycle(compile_cycle_model(design))
    assert result.converged
    assert result.residuals.spool_speed[0][1] == pytest.approx(0.0, abs=1e-9)
    assert result.shaft("lp-spool").residual_fraction <= 1e-6
    assert result.shaft("hp-spool").residual_fraction <= 1e-6
    assert result.residuals.mass_continuity <= 1e-9
    assert result.residuals.pressure_continuity <= 1e-9
    assert result.residuals.bleed_cooling <= 1e-9
    assert result.residuals.mixer_compatibility >= 0.0
    assert "mixer_compatibility" in result.validity.checks


def test_turbo04_declared_speed_inconsistency_is_an_explicit_residual() -> None:
    design = _multi_spool_design_from_turbo01()
    result = solve_cycle(compile_cycle_model(design))
    spool_speed = dict(result.residuals.spool_speed)
    assert spool_speed["hp-spool->lp-spool"] > 0.2
    assert result.residuals.max_residual >= 0.2


def _multi_spool_design_from_turbo01() -> CycleDesign:
    arch = _arch("multi_spool_bypass.json")
    base = _multi_spool_design("two_spool_bypass_consistent.json")
    return CycleDesign(
        architecture=arch,
        component_parameters=base.component_parameters,
        gas=base.gas,
        ambient_total_pressure_pa=base.ambient_total_pressure_pa,
        ambient_total_temperature_k=base.ambient_total_temperature_k,
        mass_flow_kg_s=base.mass_flow_kg_s,
    )


def test_turbo04_recuperated_cycle_raises_combustor_inlet_temperature() -> None:
    result = solve_cycle(compile_cycle_model(_recuperated_design()))
    compressor_exit = result.station("2")
    recuperator_exit = result.station("3")
    assert recuperator_exit.total_temperature.value_si > compressor_exit.total_temperature.value_si


def test_turbo04_electric_balance_residual_is_explicit() -> None:
    design = _core_design()
    parameters = [
        (node_id, parameters)
        for node_id, parameters in design.component_parameters
        if node_id != "load"
    ]
    parameters.append(("load", _params(electric_power_w=5.0e6)))
    mismatched = CycleDesign(
        architecture=design.architecture,
        component_parameters=tuple(parameters),
        gas=design.gas,
        ambient_total_pressure_pa=design.ambient_total_pressure_pa,
        ambient_total_temperature_k=design.ambient_total_temperature_k,
        mass_flow_kg_s=design.mass_flow_kg_s,
    )
    result = solve_cycle(compile_cycle_model(mismatched))
    electric = dict(result.residuals.electric_balance)
    assert "core-spool" in electric
    shaft = result.shaft("core-spool")
    assert shaft.mechanical_load_w == pytest.approx(5.0e6)
    assert "electric_balance" in result.validity.checks


def test_turbo04_result_is_deterministic_and_unit_bearing() -> None:
    model = compile_cycle_model(_core_design())
    first = solve_cycle(model)
    second = solve_cycle(model)
    assert first.result_hash == second.result_hash
    assert first.canonical_payload() == second.canonical_payload()
    for station in first.stations:
        if station.state.total_pressure is not None:
            assert station.state.total_pressure.unit == "Pa"
        if station.state.total_temperature is not None:
            assert station.state.total_temperature.unit == "K"


# -- B. optional pyCycle/OpenMDAO native path ---------------------------------


def test_turbo04_engine_probe_reports_both_engines() -> None:
    statuses = {status.engine: status for status in probe_cycle_engines()}
    assert set(statuses) == {"pycycle", "openmdao"}
    assert "available" in statuses["pycycle"].canonical()
    assert statuses["openmdao"].available == probe_cycle_engine("openmdao").available


def test_turbo04_pycycle_supported_topology_gate() -> None:
    supported, reason = pycycle_supported_topology(compile_cycle_model(_core_design()))
    assert supported is True
    assert "expressible" in reason

    recuperated, reason = pycycle_supported_topology(
        compile_cycle_model(_recuperated_design())
    )
    assert recuperated is False
    assert "recuperator" in reason


@pytest.mark.skipif(
    probe_cycle_engine("pycycle").available, reason="pyCycle is installed"
)
def test_turbo04_pycycle_fails_closed_when_absent() -> None:
    model = compile_cycle_model(_core_design())
    with pytest.raises(CycleCapabilityUnavailable) as prepare_failure:
        prepare_pycycle_case(model)
    assert prepare_failure.value.code == "CAPABILITY_UNAVAILABLE"
    with pytest.raises(CycleCapabilityUnavailable) as solve_failure:
        solve_with_pycycle(model)
    assert solve_failure.value.code == "CAPABILITY_UNAVAILABLE"


def test_turbo04_pycycle_parser_rejects_foreign_and_missing_results(
    tmp_path: Path,
) -> None:
    case = tmp_path / "case"
    case.mkdir()
    (case / "result.json").write_text(
        json.dumps({"library": "openfoam", "solverVersion": "x", "runId": "y"}),
        encoding="utf-8",
    )
    with pytest.raises(CycleParserError):
        parse_pycycle_result(case)
    with pytest.raises(CycleParserError):
        parse_pycycle_result(tmp_path / "missing")

    (case / "result.json").write_text(
        json.dumps({"library": "pycycle"}), encoding="utf-8"
    )
    with pytest.raises(CycleParserError, match="SOLVER_VERSION"):
        parse_pycycle_result(case)


@pytest.mark.skipif(
    not probe_cycle_engine("openmdao").available, reason="OpenMDAO is not installed"
)
def test_turbo04_openmdao_network_executes_and_labels_engine() -> None:
    model = compile_cycle_model(_single_fan_design())
    result = solve_with_openmdao(model)
    assert result.engine == "openmdao-generic-network"
    assert result.fidelity == "openmdao-generic-network"
    assert result.source == ResultSource.NATIVE_SOLVER.value
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    assert result.provenance.solver_name == "openmdao"
    assert result.provenance.solver_version
    assert result.provenance.run_id
    assert result.shaft("fan-spool").required_w > 0.0
    assert result.units()["s1.totalPressure"] == "Pa"


@pytest.mark.skipif(
    not probe_cycle_engine("openmdao").available, reason="OpenMDAO is not installed"
)
def test_turbo04_openmdao_matches_two_spools() -> None:
    model = compile_cycle_model(_multi_spool_design("two_spool_bypass_consistent.json"))
    result = solve_with_openmdao(model)
    assert result.converged
    assert result.shaft("lp-spool").residual_fraction <= 1e-5
    assert result.shaft("hp-spool").residual_fraction <= 1e-5
    assert result.residuals.mass_continuity <= 1e-9


@pytest.mark.skipif(
    not probe_cycle_engine("openmdao").available, reason="OpenMDAO is not installed"
)
def test_turbo04_openmdao_matches_analytical_stations() -> None:
    model = compile_cycle_model(_core_design())
    analytical = solve_cycle(model)
    native = solve_with_openmdao(model)
    for station_id in ("1", "4", "5"):
        assert native.station(station_id).total_pressure.value_si == pytest.approx(
            analytical.station(station_id).total_pressure.value_si, rel=1e-6
        )


# -- ideal Brayton stays labelled screening -----------------------------------


def test_turbo04_ideal_brayton_is_only_labelled_screening() -> None:
    from aeroworkbench_core.models.gas_turbine import GasTurbineInput

    screening = ideal_brayton_screening(
        GasTurbineInput(
            mass_flow_kg_s=12.0,
            ambient_temperature_k=288.15,
            ambient_pressure_pa=101325.0,
            compressor_pressure_ratio=8.0,
            compressor_efficiency=0.86,
            turbine_inlet_temperature_k=1450.0,
            turbine_efficiency=0.90,
            combustor_efficiency=0.99,
            combustor_pressure_loss_fraction=0.04,
            cp_j_kg_k=1150.0,
            gamma=1.33,
            fuel_lower_heating_value_j_kg=43.0e6,
        )
    )
    assert screening.fidelity == "ideal-brayton-screening"
    assert screening.source == "analytical"
    assert screening.provenance.solver_name is None
    assert any("pyCycle" in note for note in screening.limitations)
