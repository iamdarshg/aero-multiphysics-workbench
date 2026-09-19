"""ADV-PHYS 07: generic internal-flow networks, leakage, cooling, and coupling.

These tests drive the product-neutral network engine from typed, deterministic
fixtures: plena, ducts, orifices, valves, seals, heat exchangers, work machines,
and rotating cavities. Mass/momentum/energy closure is explicit; every
correlation is versioned and validity-bounded; temperature-dependent properties
come from ADV-PHYS 01; heat exchangers couple to structures through the existing
thermal interface; and a requested native CFD capability fails closed when no
engine is wired. Nothing is fabricated and no screening result is relabelled
native.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aeroworkbench_internal_flow as iflow
import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_fluid_properties import (
    PropertyId,
    dry_air_fluid,
    evaluate_ideal_gas,
    pure_species_fluid,
)
from aeroworkbench_internal_flow import (
    BranchKind,
    BranchSpec,
    BranchState,
    DeclaredCoefficient,
    DuctLoss,
    ExplicitResistance,
    FluidNetwork,
    InternalFlowCapabilityUnavailableError,
    InternalFlowValidationError,
    InternalFlowValidityError,
    NodeKind,
    NodeSpec,
    OrificeLoss,
    SealLoss,
    ValveLoss,
)
from aeroworkbench_thermal import ThermalNetwork

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "internal_flow"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _fluid(name: str) -> Any:
    if name == "dry_air":
        return dry_air_fluid()
    if name == "o2":
        return pure_species_fluid("o2")
    raise AssertionError(f"unknown fixture fluid: {name}")


def _coefficient(payload: dict[str, Any]) -> DeclaredCoefficient:
    return DeclaredCoefficient(
        name=payload["name"],
        value=float(payload["value"]),
        unit=payload["unit"],
        source=payload["source"],
    )


def _loss(payload: dict[str, Any]) -> Any:
    kind = payload["type"]
    if kind == "duct":
        return DuctLoss(
            length_m=payload["lengthM"],
            diameter_m=payload["diameterM"],
            roughness_m=payload["roughnessM"],
            source=payload["source"],
        )
    if kind == "valve":
        return ValveLoss(
            area_m2=payload["areaM2"],
            loss_coefficient=_coefficient(payload["lossCoefficient"]),
            source=payload["source"],
        )
    if kind == "orifice":
        return OrificeLoss(
            area_m2=payload["areaM2"],
            discharge_coefficient=_coefficient(payload["dischargeCoefficient"]),
            source=payload["source"],
        )
    if kind == "seal":
        return SealLoss(
            diameter_m=payload["diameterM"],
            clearance_m=payload["clearanceM"],
            length_m=payload["lengthM"],
            source=payload["source"],
        )
    if kind == "explicit":
        return ExplicitResistance(
            payload["linearPaSM3"], payload["quadraticPaS2M6"], source=payload["source"]
        )
    raise AssertionError(f"unknown fixture loss: {kind}")


def _build(payload: dict[str, Any]) -> FluidNetwork:
    network = FluidNetwork(name=payload["name"])
    for node in payload["nodes"]:
        network.add_node(
            NodeSpec(
                node_id=node["id"],
                kind=NodeKind(node["kind"]),
                fluid=_fluid(node["fluid"]),
                pressure_pa=node.get("pressurePa"),
                temperature_k=node.get("temperatureK"),
                heat_load_w=node.get("heatLoadW", 0.0),
                rotation_speed_rpm=node.get("rotationSpeedRpm", 0.0),
                cavity_radius_m=node.get("cavityRadiusM"),
                windage_sides=node.get("windageSides", 2),
            )
        )
    for branch in payload["branches"]:
        network.add_branch(
            BranchSpec(
                branch_id=branch["id"],
                kind=BranchKind(branch["kind"]),
                from_node=branch["from"],
                to_node=branch["to"],
                loss_model=_loss(branch["loss"]),
                pressure_rise_pa=branch.get("pressureRisePa", 0.0),
                heat_duty_w=branch.get("heatDutyW", 0.0),
                shaft_power_w=branch.get("shaftPowerW", 0.0),
                shaft_efficiency=branch.get("shaftEfficiency", 1.0),
            )
        )
    return network


def _state(fluid: Any, pressure_pa: float, temperature_k: float) -> BranchState:
    evaluation = evaluate_ideal_gas(fluid, temperature_k=temperature_k, pressure_pa=pressure_pa)
    return BranchState(
        pressure_pa=pressure_pa,
        temperature_k=temperature_k,
        density_kg_m3=evaluation.value(PropertyId.DENSITY),
        viscosity_pa_s=evaluation.value(PropertyId.VISCOSITY),
        cp_j_kg_k=evaluation.value(PropertyId.CP),
        enthalpy_j_kg=evaluation.value(PropertyId.ENTHALPY),
    )


def _series_network() -> FluidNetwork:
    fluid = dry_air_fluid()
    network = FluidNetwork(name="series")
    network.add_node(
        NodeSpec("S", NodeKind.SOURCE, fluid, pressure_pa=110000.0, temperature_k=300.0)
    )
    network.add_node(NodeSpec("K", NodeKind.SINK, fluid, pressure_pa=100000.0, temperature_k=300.0))
    network.add_node(NodeSpec("P", NodeKind.PLENUM, fluid))
    network.add_branch(
        BranchSpec(
            "b1",
            BranchKind.ORIFICE,
            "S",
            "P",
            loss_model=OrificeLoss(
                area_m2=1e-4,
                discharge_coefficient=DeclaredCoefficient("cd", 0.8, "1", "ISO 5167"),
                source="metering plate",
            ),
        )
    )
    network.add_branch(
        BranchSpec(
            "b2",
            BranchKind.VALVE,
            "P",
            "K",
            loss_model=ValveLoss(
                area_m2=1e-3,
                loss_coefficient=DeclaredCoefficient("k", 2.0, "1", "vendor data"),
                source="control valve",
            ),
        )
    )
    return network


# -- A. network contract and conservation ------------------------------------


def test_advphys07_series_network_conserves_mass_momentum_energy() -> None:
    result = _series_network().solve()
    assert result.converged
    assert result.mass_residual_kg_s == pytest.approx(0.0, abs=1e-8)
    assert result.momentum_residual_pa == pytest.approx(0.0, abs=1e-2)
    assert result.energy_residual_w == pytest.approx(0.0, abs=1e-2)
    plenum = result.node("P")
    assert plenum.net_mass_flow_kg_s == pytest.approx(0.0, abs=1e-8)
    assert result.branch("b1").mass_flow_kg_s == pytest.approx(
        result.branch("b2").mass_flow_kg_s, rel=1e-9
    )
    assert plenum.temperature_k == pytest.approx(300.0, abs=1e-3)


def test_advphys07_contract_covers_every_declared_kind() -> None:
    node_kinds = {kind.value for kind in NodeKind}
    branch_kinds = {kind.value for kind in BranchKind}
    assert {"plenum", "junction", "cavity", "source", "sink"} <= node_kinds
    assert {"bleed_extraction", "bleed_injection"} <= node_kinds
    assert {
        "duct",
        "pipe",
        "orifice",
        "valve",
        "seal",
        "heat_exchanger",
        "pump",
        "fan",
        "compressor",
    } <= branch_kinds
    for kind in BranchKind:
        BranchSpec(
            f"branch-{kind.value}",
            kind,
            "a",
            "b",
            loss_model=ExplicitResistance(1.0, 1.0, source="declared"),
        )


def test_advphys07_topology_violations_fail_closed() -> None:
    fluid = dry_air_fluid()
    with pytest.raises(InternalFlowValidationError):
        NodeSpec("S", NodeKind.SOURCE, fluid)
    with pytest.raises(InternalFlowValidationError):
        NodeSpec("P", NodeKind.PLENUM, fluid, pressure_pa=1e5, temperature_k=300.0)
    with pytest.raises(InternalFlowValidationError):
        BranchSpec("b", BranchKind.DUCT, "P", "P")
    network = FluidNetwork(name="bad")
    network.add_node(NodeSpec("S", NodeKind.SOURCE, fluid, pressure_pa=1e5, temperature_k=300.0))
    network.add_branch(BranchSpec("b", BranchKind.DUCT, "S", "missing"))
    with pytest.raises(InternalFlowValidationError):
        network.solve()
    empty = FluidNetwork(name="empty")
    with pytest.raises(InternalFlowValidationError):
        empty.solve()


def test_advphys07_unknown_fidelity_fails_closed() -> None:
    with pytest.raises(InternalFlowCapabilityUnavailableError):
        _series_network().solve(fidelity="native")


def test_advphys07_result_carries_full_contract() -> None:
    result = _series_network().solve()
    assert result.source is ResultSource.ANALYTICAL
    assert result.fidelity == "analytical"
    assert len(result.provenance.inputs_hash) == 64
    assert result.software.name == iflow.SOFTWARE_NAME
    assert result.validity.passed
    canonical = result.canonical()
    assert canonical["source"] == "analytical"
    assert canonical["inputsHash"] == result.provenance.inputs_hash
    branch = result.branch("b1").canonical()
    assert branch["units"]["massFlow"] == "kg/s"
    assert branch["units"]["pressure"] == "Pa"
    assert canonical["software"] == {
        "name": iflow.SOFTWARE_NAME,
        "version": iflow.SOFTWARE_VERSION,
    }


# -- B. correlations ---------------------------------------------------------


def test_advphys07_churchill_friction_limits_and_monotonicity() -> None:
    laminar = iflow.churchill_friction_factor(1000.0, 0.0)
    assert laminar == pytest.approx(64.0 / 1000.0, rel=1e-3)
    smooth = iflow.churchill_friction_factor(1e5, 0.0)
    assert smooth == pytest.approx(0.0185, abs=0.003)
    values = [iflow.churchill_friction_factor(re, 0.0) for re in (1e4, 1e5, 1e6)]
    assert all(later < earlier for earlier, later in zip(values, values[1:], strict=False))
    assert iflow.CHURCHILL_FRICTION.source
    assert iflow.CHURCHILL_FRICTION.version


def test_advphys07_friction_correlations_fail_closed_out_of_range() -> None:
    with pytest.raises(InternalFlowValidityError):
        iflow.laminar_friction_factor(5000.0)
    with pytest.raises(InternalFlowValidityError):
        iflow.haaland_friction_factor(1000.0, 0.0)
    with pytest.raises(InternalFlowValidityError):
        iflow.churchill_friction_factor(1e12, 0.0)


def test_advphys07_orifice_round_trip_and_validity() -> None:
    mass_flow = iflow.orifice_mass_flow(
        pressure_drop_pa=5000.0, density_kg_m3=1.2, area_m2=1e-4, discharge_coefficient=0.62
    )
    recovered = iflow.orifice_pressure_drop(
        mass_flow_kg_s=mass_flow, density_kg_m3=1.2, area_m2=1e-4, discharge_coefficient=0.62
    )
    assert recovered == pytest.approx(5000.0, rel=1e-12)
    iflow.require_orifice_validity(5000.0, 100000.0)
    with pytest.raises(InternalFlowValidityError):
        iflow.require_orifice_validity(50000.0, 100000.0)


def test_advphys07_annular_seal_leakage_is_linear_and_bounded() -> None:
    resistance = iflow.annular_seal_linear_resistance(
        diameter_m=0.1, clearance_m=1e-4, length_m=0.1, viscosity_pa_s=1.8e-5
    )
    low = iflow.annular_seal_mass_flow(
        diameter_m=0.1,
        clearance_m=1e-4,
        length_m=0.1,
        viscosity_pa_s=1.8e-5,
        density_kg_m3=1.2,
        pressure_drop_pa=10000.0,
    )
    high = iflow.annular_seal_mass_flow(
        diameter_m=0.1,
        clearance_m=1e-4,
        length_m=0.1,
        viscosity_pa_s=1.8e-5,
        density_kg_m3=1.2,
        pressure_drop_pa=20000.0,
    )
    assert high == pytest.approx(2.0 * low, rel=1e-12)
    assert resistance > 0.0
    iflow.require_annular_seal_validity(
        reynolds_number=100.0, clearance_ratio=1e-3, length_ratio=1.0
    )
    with pytest.raises(InternalFlowValidityError):
        iflow.require_annular_seal_validity(
            reynolds_number=5000.0, clearance_ratio=1e-3, length_ratio=1.0
        )


def test_advphys07_dittus_boelter_heat_transfer() -> None:
    nusselt = iflow.dittus_boelter_nusselt(
        reynolds_number=50000.0, prandtl_number=0.72, length_diameter_ratio=50.0, heating=True
    )
    assert nusselt > 0.0
    coefficient = iflow.duct_convection_coefficient(
        reynolds_number=50000.0,
        prandtl_number=0.72,
        length_diameter_ratio=50.0,
        conductivity_w_m_k=0.026,
        diameter_m=0.05,
        heating=True,
    )
    assert coefficient > 0.0
    with pytest.raises(InternalFlowValidityError):
        iflow.dittus_boelter_nusselt(
            reynolds_number=100.0, prandtl_number=0.72, length_diameter_ratio=50.0, heating=True
        )


def test_advphys07_no_anonymous_constants_are_accepted() -> None:
    with pytest.raises(InternalFlowValidationError):
        DeclaredCoefficient("cd", 0.62, "1", "")
    with pytest.raises(InternalFlowValidationError):
        iflow.CorrelationRef("id", "1.0", "")
    with pytest.raises(InternalFlowValidationError):
        ExplicitResistance(1.0, 1.0, source="")


def test_advphys07_effectiveness_ntu_and_duty() -> None:
    low = iflow.counterflow_effectiveness(1.0, 0.5)
    high = iflow.counterflow_effectiveness(5.0, 0.5)
    assert 0.0 < low < high < 1.0
    duty, effectiveness, reference = iflow.heat_exchanger_duty_to_wall(
        ua_w_k=200.0,
        hot_capacity_rate_w_k=100.0,
        cold_capacity_rate_w_k=200.0,
        hot_inlet_k=400.0,
        cold_inlet_k=300.0,
    )
    assert duty > 0.0
    assert 0.0 < effectiveness < 1.0
    assert reference.correlation_id == "counterflow-effectiveness-ntu"


# -- C. fluid-property integration -------------------------------------------


def test_advphys07_temperature_dependent_properties_change_loss() -> None:
    fluid = dry_air_fluid()
    duct = DuctLoss(length_m=1.0, diameter_m=0.05, roughness_m=4.5e-5, source="pipe")
    cold = iflow.evaluate_loss_model(
        duct,
        mass_flow_kg_s=0.2,
        from_state=_state(fluid, 200000.0, 300.0),
        to_state=_state(fluid, 150000.0, 300.0),
    )[0]
    hot = iflow.evaluate_loss_model(
        duct,
        mass_flow_kg_s=0.2,
        from_state=_state(fluid, 200000.0, 600.0),
        to_state=_state(fluid, 150000.0, 600.0),
    )[0]
    assert cold.quadratic_pa_s2_m6 > 0.0
    assert hot.quadratic_pa_s2_m6 > 0.0
    assert cold.quadratic_pa_s2_m6 != hot.quadratic_pa_s2_m6


def test_advphys07_missing_transport_fails_closed() -> None:
    fluid = pure_species_fluid("co2")
    network = FluidNetwork(name="no-transport")
    network.add_node(
        NodeSpec("S", NodeKind.SOURCE, fluid, pressure_pa=110000.0, temperature_k=300.0)
    )
    network.add_node(NodeSpec("K", NodeKind.SINK, fluid, pressure_pa=100000.0, temperature_k=300.0))
    network.add_node(NodeSpec("P", NodeKind.PLENUM, fluid))
    duct = DuctLoss(length_m=1.0, diameter_m=0.05, roughness_m=1e-6, source="pipe")
    network.add_branch(BranchSpec("d1", BranchKind.DUCT, "S", "P", loss_model=duct))
    network.add_branch(BranchSpec("d2", BranchKind.DUCT, "P", "K", loss_model=duct))
    with pytest.raises(InternalFlowCapabilityUnavailableError):
        network.solve()


def test_advphys07_out_of_validity_orifice_fails_closed() -> None:
    fluid = dry_air_fluid()
    network = FluidNetwork(name="choked")
    network.add_node(
        NodeSpec("S", NodeKind.SOURCE, fluid, pressure_pa=300000.0, temperature_k=300.0)
    )
    network.add_node(NodeSpec("K", NodeKind.SINK, fluid, pressure_pa=100000.0, temperature_k=300.0))
    network.add_branch(
        BranchSpec(
            "o",
            BranchKind.ORIFICE,
            "S",
            "K",
            loss_model=OrificeLoss(
                area_m2=1e-4,
                discharge_coefficient=DeclaredCoefficient("cd", 0.62, "1", "ISO 5167"),
                source="plate",
            ),
        )
    )
    with pytest.raises(InternalFlowValidityError):
        network.solve()


# -- D. thermal coupling to structures ---------------------------------------


def test_advphys07_heat_exchanger_couples_to_structure() -> None:
    result = _build(_fixture("turbine_cooling.json")).solve()
    assert result.converged
    thermal = ThermalNetwork(ambient_c=25.0)
    thermal.connect("solid", "ambient", 0.5)
    links = iflow.structure_links_from_result(result, {"hx": "solid"})
    assert len(links) == 1
    coupling = iflow.apply_structure_heat_loads(thermal_network=thermal, links=links)
    wall = dict(coupling.wall_temperatures_c)["solid"]
    assert wall > 25.0
    assert coupling.thermal.converged
    assert coupling.source is ResultSource.ANALYTICAL
    assert len(coupling.provenance.inputs_hash) == 64
    with pytest.raises(InternalFlowValidationError):
        iflow.StructureThermalLink("hx", "solid", -1.0, "bad")


def test_advphys07_structure_coupling_requires_links() -> None:
    thermal = ThermalNetwork(ambient_c=25.0)
    with pytest.raises(InternalFlowValidationError):
        iflow.apply_structure_heat_loads(thermal_network=thermal, links=())


# -- E. rotating/cavity seam -------------------------------------------------


def test_advphys07_windage_moment_correlation_bounds() -> None:
    laminar, laminar_ref = iflow.windage_moment_coefficient(1e5)
    turbulent, turbulent_ref = iflow.windage_moment_coefficient(1e6)
    assert laminar > turbulent > 0.0
    assert laminar_ref.correlation_id == "daily-nece-windage-moment-laminar"
    assert turbulent_ref.correlation_id == "daily-nece-windage-moment-turbulent"
    with pytest.raises(InternalFlowValidityError):
        iflow.windage_moment_coefficient(0.5)


def test_advphys07_cavity_adds_windage_heat() -> None:
    result = _build(_fixture("turbine_cooling.json")).solve()
    cavity = result.node("C")
    plenum = result.node("P")
    assert cavity.windage_heat_w > 0.0
    assert cavity.temperature_k > plenum.temperature_k


def test_advphys07_reduced_fidelity_escalation_hook() -> None:
    network = _build(_fixture("turbine_cooling.json"))
    result = network.solve(fidelity="reduced")
    assert result.converged
    assert "REDUCED_ORDER_ROTATING_CAVITY_MODEL" in iflow.escalation_reasons(result)
    with pytest.raises(InternalFlowCapabilityUnavailableError):
        network.solve(fidelity="native")


# -- F. system integration ---------------------------------------------------


def test_advphys07_secondary_flow_penalties() -> None:
    result = _build(_fixture("turbine_cooling.json")).solve()
    report = iflow.secondary_flow_report(result)
    assert report.leakage_mass_flow_kg_s > 0.0
    assert report.cooling_heat_w == pytest.approx(5000.0)
    assert report.bleed_extraction_kg_s > 0.0
    assert 0.0 < report.leakage_fraction < 1.0
    payload = report.penalty_payload()
    assert set(payload) == {
        "leakageMassFlowKgS",
        "leakageFraction",
        "coolingHeatW",
        "parasiticPowerW",
        "bleedExtractionKgS",
        "bleedInjectionKgS",
    }
    assert report.source is ResultSource.ANALYTICAL
    assert len(report.provenance.inputs_hash) == 64


# -- G. composition ----------------------------------------------------------


def test_advphys07_composition_mixing_closes() -> None:
    air = dry_air_fluid()
    oxygen = pure_species_fluid("o2")
    network = FluidNetwork(name="mixing")
    network.add_node(
        NodeSpec("S1", NodeKind.SOURCE, air, pressure_pa=200000.0, temperature_k=300.0)
    )
    network.add_node(
        NodeSpec("S2", NodeKind.SOURCE, oxygen, pressure_pa=200000.0, temperature_k=300.0)
    )
    network.add_node(NodeSpec("P", NodeKind.PLENUM, air))
    network.add_node(NodeSpec("K", NodeKind.SINK, air, pressure_pa=100000.0, temperature_k=300.0))
    def resistance() -> ExplicitResistance:
        return ExplicitResistance(1000.0, 0.0, source="declared")

    network.add_branch(BranchSpec("a", BranchKind.DUCT, "S1", "P", loss_model=resistance()))
    network.add_branch(BranchSpec("b", BranchKind.DUCT, "S2", "P", loss_model=resistance()))
    network.add_branch(BranchSpec("c", BranchKind.DUCT, "P", "K", loss_model=resistance()))
    result = network.solve()
    assert result.converged
    composition = {item.node_id: item for item in iflow.solve_composition(network, result)}
    air_o2 = dict(air.composition.mass_fractions())["o2"]
    mixed_o2 = dict(composition["P"].mass_fractions)["o2"]
    assert air_o2 < mixed_o2 < 1.0
    assert composition["P"].closure_residual == pytest.approx(0.0, abs=1e-9)


# -- H. native CFD seam ------------------------------------------------------


class _FakeCfdBackend:
    backend_id = "fake-cfd"
    software_version = "9.9.9"

    def solve(self, request: iflow.NativeCfdRequest) -> iflow.NativeCfdSolution:
        return iflow.NativeCfdSolution(
            node_pressures_pa={item[0]: item[2] for item in request.boundary_nodes},
            node_temperatures_k={item[0]: item[3] for item in request.boundary_nodes},
            branch_mass_flows_kg_s={item[0]: 0.1 for item in request.branches},
            detail="fake native solve",
        )


def test_advphys07_cfd_capability_probe_reports_state() -> None:
    capability = iflow.probe_cfd_capability("foamRun")
    assert isinstance(capability.available, bool)
    assert capability.canonical()["backend"] == "foamRun"


def test_advphys07_native_cfd_fails_closed_without_backend() -> None:
    network = _series_network()
    with pytest.raises(InternalFlowCapabilityUnavailableError):
        iflow.solve_native_or_fail(network, run_id="run-1")


def test_advphys07_native_cfd_backend_seam_is_native() -> None:
    network = _series_network()
    result = iflow.evaluate_native_cfd(network, backend=_FakeCfdBackend(), run_id="cfd-run-1")
    assert result.source is ResultSource.NATIVE_SOLVER
    assert result.solver_name == "fake-cfd"
    assert result.solver_version == "9.9.9"
    assert result.provenance.run_id == "cfd-run-1"
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    assert len(result.provenance.inputs_hash) == 64
    assert result.canonical()["source"] == "native_solver"


def test_advphys07_native_cfd_requires_run_id() -> None:
    with pytest.raises(InternalFlowValidationError):
        iflow.evaluate_native_cfd(_series_network(), backend=_FakeCfdBackend(), run_id=None)


# -- I. portability fixtures -------------------------------------------------


def test_advphys07_fixture_turbine_cooling() -> None:
    payload = _fixture("turbine_cooling.json")
    result = _build(payload).solve()
    assert result.converged is payload["expect"]["converged"]
    report = iflow.secondary_flow_report(result)
    assert report.cooling_heat_w == pytest.approx(payload["expect"]["coolingHeatW"])
    assert report.leakage_mass_flow_kg_s >= payload["expect"]["minLeakageKgS"]
    assert report.bleed_extraction_kg_s >= payload["expect"]["minBleedKgS"]
    assert result.node("C").temperature_k > result.node("P").temperature_k


def test_advphys07_fixture_electronics_cooling() -> None:
    payload = _fixture("electronics_cooling.json")
    result = _build(payload).solve()
    assert result.converged is payload["expect"]["converged"]
    report = iflow.secondary_flow_report(result)
    assert report.cooling_heat_w == pytest.approx(payload["expect"]["coolingHeatW"])
    assert report.parasitic_power_w == pytest.approx(payload["expect"]["parasiticPowerW"])
    pump = result.branch("pump")
    assert pump.fluid_work_w > 0.0
    assert pump.enthalpy_rise_j_kg > 0.0
