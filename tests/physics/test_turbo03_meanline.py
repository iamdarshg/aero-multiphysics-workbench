"""TURBO 03: generic meanline / throughflow preliminary design.

Covers the station/velocity-triangle solver, row families across axial/radial/
mixed flow, versioned loss/deviation/slip correlations with validity envelopes,
multi-row swirl/work matching, screening indicators, geometry-synthesis targets,
and the scalar/OpenMDAO participant. Every result keeps source and provenance and
native fidelity fails closed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_turbomachinery.meanline import (
    DEFAULT_MEANLINE_INPUTS,
    ROW_FAMILY_MODELS,
    IdealGas,
    MeanlineCapabilityUnavailable,
    MeanlineInputError,
    MeanlineRow,
    ScreeningLimits,
    StageDesign,
    carter_deviation_deg,
    degree_of_reaction,
    euler_work_j_kg,
    finite_difference_jacobian,
    lieblein_diffusion_factor,
    meanline_scalars,
    native_meanline_status,
    solve_meanline,
    solve_throughflow,
    solve_triangle,
    stage_from_payload,
    synthesize_geometry,
    triangle_from_angle,
)

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _TESTS_ROOT / "turbo" / "meanline"

_AIR = IdealGas(cp_j_kg_k=1005.0, gamma=1.4, gas_constant_j_kg_k=287.05)


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def stage(name: str) -> StageDesign:
    return stage_from_payload(load_fixture(name))


# -- A. station / velocity-triangle solver ------------------------------------


def test_turbo03_manufactured_triangle_matches_exact_components() -> None:
    payload = load_fixture("manufactured_triangle.json")
    expected = payload["expected"]
    triangle = triangle_from_angle(
        station_id=payload["station_id"],
        blade_speed_m_s=payload["blade_speed_m_s"],
        meridional_velocity_m_s=payload["meridional_velocity_m_s"],
        absolute_angle_deg=payload["absolute_angle_deg"],
    )
    assert triangle.tangential_velocity_m_s == pytest.approx(
        expected["tangential_velocity_m_s"]
    )
    assert triangle.relative_tangential_velocity_m_s == pytest.approx(
        expected["relative_tangential_velocity_m_s"]
    )
    assert triangle.absolute_velocity_m_s == pytest.approx(
        expected["absolute_velocity_m_s"]
    )
    assert triangle.relative_velocity_m_s == pytest.approx(expected["relative_velocity_m_s"])
    assert triangle.relative_angle_deg == pytest.approx(expected["relative_angle_deg"])
    assert triangle.flow_coefficient == pytest.approx(expected["flow_coefficient"])


def test_turbo03_euler_work_and_reaction_are_consistent() -> None:
    inlet = solve_triangle(
        station_id="1", blade_speed_m_s=250.0, axial_velocity_m_s=150.0,
        tangential_velocity_m_s=0.0,
    )
    outlet = solve_triangle(
        station_id="2", blade_speed_m_s=250.0, axial_velocity_m_s=150.0,
        tangential_velocity_m_s=100.0,
    )
    work = euler_work_j_kg(inlet=inlet, outlet=outlet)
    assert work == pytest.approx(250.0 * 100.0 - 250.0 * 0.0)
    reaction = degree_of_reaction(inlet=inlet, outlet=outlet)
    expected = 1.0 - (
        outlet.absolute_velocity_m_s**2 - inlet.absolute_velocity_m_s**2
    ) / (2.0 * work)
    assert reaction == pytest.approx(expected)
    assert 0.0 < reaction < 1.0


def test_turbo03_state_from_total_is_entropy_consistent() -> None:
    from aeroworkbench_turbomachinery.meanline import state_from_total

    state = state_from_total(
        gas=_AIR, total_temperature_k=300.0, total_pressure_pa=101325.0,
        mass_flow_kg_s=5.0, velocity_m_s=150.0,
    )
    assert state.static_temperature_k < 300.0
    assert state.static_pressure_pa < 101325.0
    exponent = _AIR.gamma / (_AIR.gamma - 1.0)
    assert state.static_pressure_pa == pytest.approx(
        101325.0 * (state.static_temperature_k / 300.0) ** exponent
    )


# -- B / E. row families and multi-row matching -------------------------------


def test_turbo03_row_families_cover_required_constructs() -> None:
    required = {
        "axial_compressor_rotor",
        "axial_compressor_stator",
        "axial_turbine_nozzle",
        "axial_turbine_rotor",
        "radial_compressor_impeller",
        "radial_compressor_diffuser",
        "radial_turbine_rotor",
    }
    assert required <= set(ROW_FAMILY_MODELS)
    assert ROW_FAMILY_MODELS["radial_compressor_impeller"].slip is True
    assert ROW_FAMILY_MODELS["axial_turbine_nozzle"].turning_frame == "absolute"
    assert ROW_FAMILY_MODELS["axial_compressor_rotor"].turning_frame == "relative"


def test_turbo03_axial_compressor_stage_solves_and_screens() -> None:
    result = solve_throughflow(stage("axial_compressor_stage.json"))
    assert result.validity.passed is True
    assert result.screened is True
    assert len(result.rows) == 2
    assert result.total_work_j_kg > 0.0
    assert result.pressure_ratio > 1.0
    assert result.temperature_rise_k > 0.0
    assert result.rows[0].euler_work_j_kg > 0.0
    assert result.rows[1].euler_work_j_kg == pytest.approx(0.0)
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert len(result.provenance.inputs_hash) == 64


def test_turbo03_multi_row_swirl_and_state_are_matched() -> None:
    result = solve_throughflow(stage("axial_compressor_stage.json"))
    rotor, stator = result.rows
    assert stator.inlet_triangle.absolute_angle_deg == pytest.approx(
        rotor.outlet_triangle.absolute_angle_deg
    )
    assert stator.inlet_state.total_pressure_pa == pytest.approx(
        rotor.outlet_state.total_pressure_pa
    )
    assert stator.inlet_state.total_temperature_k == pytest.approx(
        rotor.outlet_state.total_temperature_k
    )
    assert stator.outlet_state.total_pressure_pa < stator.inlet_state.total_pressure_pa


def test_turbo03_turbine_stage_extracts_work_and_drops_pressure() -> None:
    result = solve_throughflow(stage("axial_turbine_stage.json"))
    assert result.validity.passed is True
    assert result.total_work_j_kg < 0.0
    assert result.pressure_ratio < 1.0
    assert result.temperature_rise_k < 0.0
    assert all(row.role != "work_adding" for row in result.rows)


def test_turbo03_radial_compressor_uses_slip_and_diffuser() -> None:
    result = solve_throughflow(stage("radial_compressor_stage.json"))
    assert result.validity.passed is True
    impeller, diffuser = result.rows
    assert impeller.flow_family == "radial"
    assert impeller.euler_work_j_kg > 0.0
    assert impeller.slip_factor is not None
    assert 0.0 < impeller.slip_factor < 1.0
    diffuser_losses = [c.identity for c in diffuser.loss_breakdown.components]
    assert "japikse-diffuser-recovery" in diffuser_losses
    assert diffuser.role == "diffuser_guide"


# -- C. loss / deviation / slip correlations ----------------------------------


def test_turbo03_carter_deviation_formula_and_envelope() -> None:
    value = carter_deviation_deg(camber_deg=30.0, stagger_deg=30.0, solidity=1.2)
    expected_m = 0.23 + 0.1 * (30.0 / 50.0)
    assert value.value == pytest.approx(expected_m * 30.0 / math.sqrt(1.2))
    assert value.validity_passed is True
    assert value.identity == "carter-deviation"
    assert value.version
    assert value.source

    out_of_envelope = carter_deviation_deg(camber_deg=200.0, stagger_deg=30.0, solidity=1.2)
    assert out_of_envelope.validity_passed is False
    assert out_of_envelope.violations


def test_turbo03_lieblein_diffusion_and_slip_formulas() -> None:
    diffusion = lieblein_diffusion_factor(
        inlet_relative_velocity_m_s=300.0,
        outlet_relative_velocity_m_s=180.0,
        inlet_tangential_velocity_m_s=0.0,
        outlet_tangential_velocity_m_s=100.0,
        inlet_radius_m=0.25,
        outlet_radius_m=0.25,
        solidity=1.0,
    )
    expected = (1.0 - 180.0 / 300.0) + 100.0 / (2.0 * 1.0 * 300.0)
    assert diffusion.value == pytest.approx(expected)

    from aeroworkbench_turbomachinery.meanline import slip_factor

    stanitz = slip_factor(blade_count=20)
    assert stanitz.value == pytest.approx(1.0 - 0.63 * math.pi / 20.0)
    wiesner = slip_factor(blade_count=20, exit_blade_angle_deg=30.0)
    assert wiesner.identity == "wiesner-slip-factor"
    assert 0.0 < wiesner.value < 1.0


def test_turbo03_loss_components_carry_provenance() -> None:
    result = solve_throughflow(stage("axial_compressor_stage.json"))
    components = result.rows[0].loss_breakdown.components
    assert components
    for component in components:
        canonical = component.canonical()
        assert canonical["correlation"]
        assert canonical["version"]
        assert canonical["source"]
        provenance = component.provenance(inputs={"probe": 1.0})
        assert provenance.source is ResultSource.ANALYTICAL
        assert len(provenance.inputs_hash) == 64


# -- D. limits / stability indicators -----------------------------------------


def test_turbo03_screening_rejects_excessive_incidence() -> None:
    payload = load_fixture("axial_compressor_stage.json")
    payload["rows"][0]["inletMetalAngleDeg"] = -20.0
    result = solve_throughflow(stage_from_payload(payload))
    assert result.screened is False
    incidence = [i for i in result.rows[0].indicators if i.name == "incidence"]
    assert incidence and incidence[0].passed is False


def test_turbo03_declared_limits_are_configurable() -> None:
    strict = ScreeningLimits(max_diffusion_factor=0.05)
    result = solve_throughflow(
        stage("axial_compressor_stage.json"), limits=strict
    )
    assert result.screened is False
    proxy = [i for i in result.rows[0].indicators if i.name == "stall_surge_proxy"]
    assert proxy and proxy[0].limit == pytest.approx(0.05)


# -- F. geometry synthesis outputs --------------------------------------------


def test_turbo03_geometry_synthesis_produces_row_targets() -> None:
    design = stage("axial_compressor_stage.json")
    result = solve_throughflow(design)
    synthesis = synthesize_geometry(design, result)
    assert len(synthesis.targets) == len(design.rows)
    for target, row in zip(synthesis.targets, design.rows, strict=True):
        assert target.chord_m == pytest.approx(row.chord_m)
        assert target.solidity == pytest.approx(row.solidity)
        assert target.blade_count == row.blade_count
        low, high = target.blade_count_range
        assert low < high
        assert target.annulus_area_in_m2 > 0.0
        assert target.annulus_area_out_m2 > 0.0
        assert target.row_spacing_m > 0.0
    assert synthesis.provenance.source is ResultSource.ANALYTICAL


# -- G. scalar participant and OpenMDAO adapter -------------------------------


def test_turbo03_scalar_participant_outputs_are_consistent() -> None:
    outputs = meanline_scalars(DEFAULT_MEANLINE_INPUTS)
    assert outputs["euler_work_j_kg"] > 0.0
    assert 0.0 <= outputs["reaction"] <= 1.0
    assert outputs["diffusion_factor"] > 0.0
    assert outputs["relative_mach_out"] > 0.0
    assert outputs["total_pressure_ratio"] > 1.0


def test_turbo03_finite_difference_jacobian_is_bounded() -> None:
    jacobian = finite_difference_jacobian(meanline_scalars, DEFAULT_MEANLINE_INPUTS)
    assert "euler_work_j_kg" in jacobian
    assert jacobian["euler_work_j_kg"]["rotational_speed_rpm"] > 0.0
    assert jacobian["euler_work_j_kg"]["mean_radius_m"] > 0.0
    assert set(jacobian["euler_work_j_kg"]) == set(DEFAULT_MEANLINE_INPUTS)


def test_turbo03_openmdao_component_executes() -> None:
    om = pytest.importorskip("openmdao.api")
    from aeroworkbench_turbomachinery.meanline import build_openmdao_component

    prob = om.Problem()
    prob.model.add_subsystem("meanline", build_openmdao_component()(), promotes=["*"])
    prob.setup()
    prob.run_model()
    work = float(prob.get_val("euler_work_j_kg")[0])
    expected = meanline_scalars(DEFAULT_MEANLINE_INPUTS)["euler_work_j_kg"]
    assert work == pytest.approx(expected, rel=1e-9)


# -- native fidelity is capability-gated and fails closed ----------------------


def test_turbo03_native_fidelity_fails_closed() -> None:
    status = native_meanline_status()
    assert status.state in ("unavailable", "engine-present-not-wired")
    assert status.implementation
    with pytest.raises(MeanlineCapabilityUnavailable):
        solve_meanline(stage("axial_compressor_stage.json"), fidelity="native")


def test_turbo03_reduced_fidelity_is_labelled_honestly() -> None:
    result = solve_meanline(stage("axial_compressor_stage.json"), fidelity="reduced")
    assert result.fidelity == "reduced"
    assert result.source == "row-matching-meanline-reduced"
    assert result.provenance.source is ResultSource.ANALYTICAL


# -- input validation ---------------------------------------------------------


def test_turbo03_canonical_outputs_are_json_safe_and_downstream_ready() -> None:
    design = stage("axial_compressor_stage.json")
    result = solve_throughflow(design)
    payload = result.canonical()
    text = json.dumps(payload, sort_keys=True, allow_nan=False)
    assert '"rows"' in text
    first_row = payload["rows"][0]
    assert "inletState" in first_row
    assert "outletState" in first_row
    assert "indicators" in first_row
    assert payload["validity"]["passed"] is True
    assert payload["source"] == "row-matching-meanline-analytical"
    assert stage_from_payload(design.canonical()).canonical() == design.canonical()
    assert json.dumps(synthesize_geometry(design, result).canonical(), allow_nan=False)


def test_turbo03_invalid_inputs_fail_closed() -> None:
    payload = load_fixture("axial_compressor_stage.json")
    payload["rows"][0]["rowFamily"] = "not-a-family"
    with pytest.raises(MeanlineInputError, match="UNKNOWN_ROW_FAMILY"):
        stage_from_payload(payload)

    with pytest.raises(MeanlineInputError, match="TIP_CLEARANCE_MUST_BE_SMALLER_THAN_SPAN"):
        MeanlineRow(
            row_family="axial_compressor_rotor",
            mean_radius_in_m=0.25,
            mean_radius_out_m=0.25,
            meridional_velocity_in_m_s=160.0,
            inlet_metal_angle_deg=-52.6,
            exit_metal_angle_deg=-45.0,
            stagger_deg=30.0,
            camber_deg=30.0,
            solidity=1.2,
            chord_m=0.05,
            span_m=0.01,
            blade_count=40,
            tip_clearance_m=0.02,
        )
