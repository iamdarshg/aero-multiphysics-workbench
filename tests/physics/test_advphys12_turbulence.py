"""ADV-PHYS 12: generic transition/turbulence/roughness/model-validity management.

These tests drive the product-neutral capability from typed, deterministic
fixtures: flow-regime contracts, an explicit model/fidelity ladder, near-wall
treatment checked against measured mesh resolution, explicit provenance-backed
roughness (including ADV-PHYS 08 degradation), transition/separation/model-
disagreement diagnostics, solver-adapter derivation, and portable benchmarks.
Every result carries source/fidelity/units/validity/input-hash/software-identity/
provenance; native paths are capability-gated and fail closed, and a screening
correlation is never relabelled native.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aeroworkbench_turbulence as turb
import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_environmental import (
    EnvironmentState,
    ExposureKind,
    ExposureSpec,
    Quantity,
    evaluate_degradation,
)
from aeroworkbench_fluid_properties import dry_air_fluid, pure_species_fluid
from aeroworkbench_mesh import BoundaryLayerIntent

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "turbulence"

_THRESHOLDS = {
    "external_flow": turb.EXTERNAL_FLOW_THRESHOLDS,
    "internal_flow": turb.INTERNAL_FLOW_THRESHOLDS,
    "low_reynolds": turb.LOW_REYNOLDS_THRESHOLDS,
}


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _roughness(payload: dict[str, Any] | None) -> turb.RoughnessSpec | None:
    if payload is None:
        return None
    return turb.make_roughness(
        surface=payload["surface"],
        model=turb.RoughnessModel(payload["model"]),
        equivalent_sand_grain_m=float(payload["equivalentSandGrainM"]),
        source=payload["source"],
    )


def _flow(payload: dict[str, Any]) -> turb.FlowState:
    reference = payload["reference"]
    return turb.FlowState(
        label=payload["label"],
        reynolds_number=float(payload["reynoldsNumber"]),
        mach_number=float(payload["machNumber"]),
        turbulence_intensity=float(payload["turbulenceIntensity"]),
        reference=turb.ReferenceScales(
            label=reference["label"],
            length_m=float(reference["lengthM"]),
            velocity_m_s=float(reference["velocityMS"]),
            source=reference["source"],
        ),
        wall_temperature_k=payload.get("wallTemperatureK"),
        adiabatic_wall=payload.get("adiabaticWall", True),
        conjugate_heat_transfer=payload.get("conjugateHeatTransfer", False),
        roughness=_roughness(payload.get("roughness")),
        transition_state=turb.TransitionState(payload.get("transitionState", "unknown")),
        pressure_gradient_parameter=float(payload.get("pressureGradientParameter", 0.0)),
        separation_fraction=float(payload.get("separationFraction", 0.0)),
        thresholds=_THRESHOLDS[payload.get("thresholds", "external_flow")],
        source=payload.get("source", "test fixture"),
    )


def _flat_plate_flow() -> turb.FlowState:
    return _flow(_fixture("flat_plate_boundary_layer.json")["flow"])


def _low_re_flow() -> turb.FlowState:
    return _flow(_fixture("low_re_airfoil.json")["flow"])


def _measured(payload: dict[str, Any], surface: str) -> turb.MeasuredWallResolution:
    return turb.MeasuredWallResolution(
        surface=surface,
        first_cell_height_m=payload.get("firstCellHeightM"),
        y_plus=payload.get("yPlus"),
        layer_count=payload.get("layerCount"),
        growth_ratio=payload.get("growthRatio"),
        total_thickness_m=payload.get("totalThicknessM"),
        thermal_wall_temperature_k=payload.get("thermalWallTemperatureK"),
        source=payload["source"],
    )


# -- A. flow-regime contract -------------------------------------------------


def test_advphys12_flow_state_carries_full_contract() -> None:
    flow = _low_re_flow()
    canonical = flow.canonical()
    assert canonical["reynoldsNumber"] == pytest.approx(100000.0)
    assert canonical["machNumber"] == pytest.approx(0.05)
    assert canonical["turbulenceIntensity"] == pytest.approx(0.005)
    assert canonical["reference"]["lengthM"] == pytest.approx(0.15)
    assert canonical["transitionState"] == "natural"
    assert canonical["roughness"]["equivalentSandGrainM"] == pytest.approx(5e-6)
    assert canonical["thresholds"]["modelId"] == "low-reynolds-regime-band"


def test_advphys12_regime_classification_is_bounded() -> None:
    laminar = turb.FlowState(
        label="laminar",
        reynolds_number=1.0e5,
        mach_number=0.1,
        turbulence_intensity=0.001,
        reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
    )
    transitional = turb.FlowState(
        label="transitional",
        reynolds_number=7.0e5,
        mach_number=0.1,
        turbulence_intensity=0.01,
        reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
    )
    turbulent = turb.FlowState(
        label="turbulent",
        reynolds_number=5.0e6,
        mach_number=0.85,
        turbulence_intensity=0.05,
        reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
    )
    assert turb.classify_regime(laminar).regime is turb.FlowRegime.LAMINAR
    assert turb.classify_regime(transitional).regime is turb.FlowRegime.TRANSITIONAL
    assert turb.classify_regime(turbulent).regime is turb.FlowRegime.TURBULENT
    assert (
        turb.classify_regime(turbulent).compressibility
        is turb.CompressibilityRegime.TRANSONIC
    )
    assert turb.classify_regime(laminar).compressibility is (
        turb.CompressibilityRegime.INCOMPRESSIBLE
    )


def test_advphys12_transition_state_overrides_reynolds_band() -> None:
    base = dict(
        label="override",
        reynolds_number=1.0e5,
        mach_number=0.1,
        turbulence_intensity=0.01,
        reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
    )
    fully_turbulent = turb.FlowState(
        **base, transition_state=turb.TransitionState.FULLY_TURBULENT
    )
    natural = turb.FlowState(**base, transition_state=turb.TransitionState.NATURAL)
    assert turb.classify_regime(fully_turbulent).regime is turb.FlowRegime.TURBULENT
    assert turb.classify_regime(natural).regime is turb.FlowRegime.TRANSITIONAL


def test_advphys12_invalid_flow_state_fails_closed() -> None:
    with pytest.raises(turb.TurbulenceValidationError):
        turb.FlowState(
            label="bad",
            reynolds_number=-1.0,
            mach_number=0.1,
            turbulence_intensity=0.01,
            reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
        )
    with pytest.raises(turb.TurbulenceValidationError):
        turb.FlowState(
            label="bad",
            reynolds_number=1.0e5,
            mach_number=0.1,
            turbulence_intensity=1.5,
            reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
        )
    with pytest.raises(turb.TurbulenceValidationError):
        turb.FlowState(
            label="cht-without-wall",
            reynolds_number=1.0e5,
            mach_number=0.1,
            turbulence_intensity=0.01,
            reference=turb.ReferenceScales("x", 1.0, 1.0, "declared"),
            conjugate_heat_transfer=True,
        )


def test_advphys12_flow_state_from_fluid_reuses_properties() -> None:
    flow = turb.flow_state_from_fluid(
        dry_air_fluid(),
        label="external",
        pressure_pa=101325.0,
        temperature_k=288.15,
        length_m=0.5,
        velocity_m_s=30.0,
    )
    assert flow.reynolds_number > 0.0
    assert flow.mach_number > 0.0
    assert flow.source.startswith("fluid:")


def test_advphys12_missing_fluid_transport_fails_closed() -> None:
    with pytest.raises(turb.TurbulenceCapabilityUnavailableError):
        turb.flow_state_from_fluid(
            pure_species_fluid("co2"),
            label="no-transport",
            pressure_pa=101325.0,
            temperature_k=300.0,
            length_m=0.5,
            velocity_m_s=30.0,
        )


# -- B. model/fidelity policy ------------------------------------------------


def test_advphys12_catalog_is_an_ordered_provenance_ladder() -> None:
    fidelities = {validity.fidelity for validity in turb.MODEL_CATALOG.values()}
    assert {
        turb.TurbulenceFidelity.LAMINAR,
        turb.TurbulenceFidelity.RANS,
        turb.TurbulenceFidelity.TRANSITION_RANS,
        turb.TurbulenceFidelity.HYBRID_RANS_LES,
        turb.TurbulenceFidelity.LES,
        turb.TurbulenceFidelity.DNS,
    } <= fidelities
    for validity in turb.MODEL_CATALOG.values():
        assert validity.source
        assert validity.revision
        assert validity.wall_modes
    assert turb.FIDELITY_RANK[turb.TurbulenceFidelity.DNS] > turb.FIDELITY_RANK[
        turb.TurbulenceFidelity.RANS
    ]


def test_advphys12_selects_lowest_valid_model() -> None:
    flat = _flat_plate_flow()
    selection = turb.select_turbulence_model(flat, turb.classify_regime(flat))
    assert selection.fidelity is turb.TurbulenceFidelity.RANS
    assert selection.model is turb.TurbulenceModel.SPALART_ALLMARAS
    assert not selection.validity.requires_native


def test_advphys12_transitional_flow_requires_transition_model() -> None:
    low = _low_re_flow()
    selection = turb.select_turbulence_model(low, turb.classify_regime(low))
    assert selection.transition_model_required
    assert selection.validity.supports_transition
    assert selection.fidelity is turb.TurbulenceFidelity.TRANSITION_RANS


def test_advphys12_policy_can_forbid_transition_models() -> None:
    low = _low_re_flow()
    policy = turb.TurbulencePolicy(allow_transition_models=False)
    selection = turb.select_turbulence_model(
        low, turb.classify_regime(low), policy=policy
    )
    assert not selection.validity.supports_transition
    assert "TRANSITION_MODEL_UNAVAILABLE" in selection.escalation_reasons


def test_advphys12_no_valid_model_fails_closed() -> None:
    hypersonic = turb.FlowState(
        label="hypersonic",
        reynolds_number=1.0e6,
        mach_number=8.0,
        turbulence_intensity=0.05,
        reference=turb.ReferenceScales("x", 1.0, 100.0, "declared"),
    )
    with pytest.raises(turb.TurbulenceValidityError):
        turb.select_turbulence_model(
            hypersonic, turb.classify_regime(hypersonic)
        )


def test_advphys12_select_for_fidelity_restricts_rung() -> None:
    flat = _flat_plate_flow()
    classification = turb.classify_regime(flat)
    selection = turb.select_turbulence_model_for_fidelity(
        flat, classification, fidelity=turb.TurbulenceFidelity.LES
    )
    assert selection.fidelity is turb.TurbulenceFidelity.LES
    assert selection.validity.requires_native
    assert "NATIVE_MODEL_REQUIRED" in selection.escalation_reasons


def test_advphys12_escalation_uses_generic_fidelity_planner() -> None:
    flat = _flat_plate_flow()
    selection = turb.select_turbulence_model(flat, turb.classify_regime(flat))
    plan = turb.plan_fidelity_escalation(selection, flat, disagreement=0.5)
    assert plan.escalate
    assert plan.level == turb.TurbulenceFidelity.TRANSITION_RANS.value
    assert plan.reasons
    assert len(plan.input_hash) == 64
    hold = turb.plan_fidelity_escalation(selection, flat, disagreement=0.01)
    assert not hold.escalate
    assert hold.level == selection.fidelity.value


def test_advphys12_implementations_form_contiguous_ladder() -> None:
    implementations = turb.fidelity_implementations()
    assert [item.rank for item in implementations] == list(range(len(implementations)))
    names = [item.name for item in implementations]
    assert turb.TurbulenceFidelity.RANS.value in names


# -- C. near-wall treatment --------------------------------------------------


def test_advphys12_wall_requirement_y_plus_bands() -> None:
    flow = _flat_plate_flow()
    resolved = turb.wall_requirement_for_mode(
        surface="plate",
        mode=turb.WallTreatmentMode.WALL_RESOLVED,
        flow=flow,
        layer_count=20,
        growth_ratio=1.2,
    )
    function = turb.wall_requirement_for_mode(
        surface="plate",
        mode=turb.WallTreatmentMode.WALL_FUNCTION,
        flow=flow,
        layer_count=12,
        growth_ratio=1.3,
    )
    assert resolved.target_y_plus == pytest.approx(1.0)
    assert function.target_y_plus == pytest.approx(50.0)
    assert resolved.first_cell_height_target_m > 0.0
    assert resolved.total_thickness_intent_m > resolved.first_cell_height_target_m
    assert resolved.provenance.inputs_hash


def test_advphys12_wall_requirement_from_mesh_intent() -> None:
    flow = _low_re_flow()
    intent = BoundaryLayerIntent(
        wall_patches=("walls",), first_layer_mm=0.02, growth_ratio=1.2, layer_count=15
    )
    requirement = turb.wall_requirement_from_boundary_layer(
        intent, surface="airfoil", mode=turb.WallTreatmentMode.WALL_RESOLVED, flow=flow
    )
    assert requirement.first_cell_height_target_m == pytest.approx(2.0e-5)
    expected_total = turb.inflation_total_thickness(
        first_cell_height_m=2.0e-5, growth_ratio=1.2, layer_count=15
    )
    assert requirement.total_thickness_intent_m == pytest.approx(expected_total)


def test_advphys12_wall_compatibility_accepts_matching_mesh() -> None:
    payload = _fixture("low_re_airfoil.json")
    flow = _flow(payload["flow"])
    wall = payload["wall"]
    requirement = turb.wall_requirement_for_mode(
        surface=wall["surface"],
        mode=turb.WallTreatmentMode(wall["mode"]),
        flow=flow,
        layer_count=wall["layerCount"],
        growth_ratio=wall["growthRatio"],
    )
    compatibility = turb.require_wall_treatment(
        requirement, _measured(wall["measured"], wall["surface"])
    )
    assert compatibility.compatible
    assert compatibility.checks["y_plus_in_band"]
    assert compatibility.canonical()["units"]["yPlus"] == "1"


def test_advphys12_wall_compatibility_rejects_incompatible_mesh() -> None:
    flow = _flat_plate_flow()
    requirement = turb.wall_requirement_for_mode(
        surface="plate",
        mode=turb.WallTreatmentMode.WALL_RESOLVED,
        flow=flow,
        layer_count=20,
        growth_ratio=1.2,
    )
    measured = turb.MeasuredWallResolution(
        surface="plate",
        first_cell_height_m=0.01,
        y_plus=120.0,
        layer_count=4,
        growth_ratio=1.6,
        total_thickness_m=0.02,
        thermal_wall_temperature_k=None,
        source="coarse mesh",
    )
    compatibility = turb.evaluate_wall_treatment(requirement, measured)
    assert not compatibility.compatible
    assert "WALL_RESOLUTION_INCOMPATIBLE" in compatibility.detail
    with pytest.raises(turb.TurbulenceValidationError):
        turb.require_wall_treatment(requirement, measured)


def test_advphys12_wall_compatibility_fails_closed_without_measurement() -> None:
    flow = _flat_plate_flow()
    requirement = turb.wall_requirement_for_mode(
        surface="plate",
        mode=turb.WallTreatmentMode.WALL_FUNCTION,
        flow=flow,
        layer_count=12,
        growth_ratio=1.3,
    )
    measured = turb.MeasuredWallResolution(
        surface="plate",
        first_cell_height_m=None,
        y_plus=None,
        layer_count=None,
        growth_ratio=None,
        total_thickness_m=None,
        thermal_wall_temperature_k=None,
        source="unmeasured mesh",
    )
    compatibility = turb.evaluate_wall_treatment(requirement, measured)
    assert not compatibility.compatible
    assert not compatibility.checks["measured_available"]


def test_advphys12_thermal_wall_required_for_conjugate_heat_transfer() -> None:
    flow = turb.FlowState(
        label="cht",
        reynolds_number=1.0e6,
        mach_number=0.2,
        turbulence_intensity=0.02,
        reference=turb.ReferenceScales("x", 0.5, 40.0, "declared"),
        wall_temperature_k=450.0,
        conjugate_heat_transfer=True,
    )
    requirement = turb.wall_requirement_for_mode(
        surface="hot-wall",
        mode=turb.WallTreatmentMode.WALL_FUNCTION,
        flow=flow,
        layer_count=12,
        growth_ratio=1.3,
    )
    assert requirement.thermal_wall_required
    measured = turb.MeasuredWallResolution(
        surface="hot-wall",
        first_cell_height_m=requirement.first_cell_height_target_m,
        y_plus=50.0,
        layer_count=12,
        growth_ratio=1.25,
        total_thickness_m=requirement.total_thickness_intent_m,
        thermal_wall_temperature_k=None,
        source="mesh without wall temperature",
    )
    compatibility = turb.evaluate_wall_treatment(requirement, measured)
    assert not compatibility.checks["thermal_wall_present"]


def test_advphys12_first_cell_height_correlation_is_bounded() -> None:
    height, reference = turb.first_cell_height_for_y_plus(
        target_y_plus=1.0,
        density_kg_m3=1.2,
        velocity_m_s=30.0,
        length_m=1.0,
        viscosity_pa_s=1.8e-5,
        regime=turb.FlowRegime.TURBULENT,
    )
    assert 0.0 < height < 1.0e-3
    assert reference.correlation_id == "schlichting-turbulent-skin-friction"
    with pytest.raises(turb.TurbulenceValidationError):
        turb.laminar_skin_friction(1.0e8)


# -- D. surface roughness ----------------------------------------------------


def test_advphys12_roughness_requires_source() -> None:
    with pytest.raises(turb.TurbulenceValidationError):
        turb.make_roughness(
            surface="wall",
            model=turb.RoughnessModel.EQUIVALENT_SAND_GRAIN,
            equivalent_sand_grain_m=1e-5,
            source="",
        )
    with pytest.raises(turb.TurbulenceValidationError):
        turb.make_roughness(
            surface="wall",
            model=turb.RoughnessModel.EQUIVALENT_SAND_GRAIN,
            equivalent_sand_grain_m=-1e-5,
            source="vendor data",
        )


def test_advphys12_roughness_increment_is_additive() -> None:
    base = turb.make_roughness(
        surface="wall",
        model=turb.RoughnessModel.MANUFACTURED_FINISH,
        equivalent_sand_grain_m=5e-6,
        source="machined finish",
    )
    eroded = turb.apply_roughness_increment(
        base,
        increment_m=2e-5,
        model=turb.RoughnessModel.ERODED,
        source="erosion test data",
    )
    assert eroded.equivalent_sand_grain_m == pytest.approx(2.5e-5)
    assert eroded.degraded_from == base.model.value
    assert eroded.canonical()["units"]["equivalentSandGrainM"] == "m"
    assert eroded.sand_grain_ratio(0.5) == pytest.approx(5e-5)


def test_advphys12_roughness_from_degradation_uses_advphys08() -> None:
    exposure = ExposureSpec(
        kind=ExposureKind.ICING,
        drivers=(
            ("ambient_temperature", Quantity(-10.0, "degC")),
            ("droplet_diameter", Quantity(20.0, "um")),
            ("duration", Quantity(600.0, "s")),
            ("impact_speed", Quantity(100.0, "m/s")),
            ("water_content", Quantity(0.5, "g/m3")),
        ),
    )
    environment = EnvironmentState(
        environment_id="icing-case",
        revision=1,
        atmosphere_model="ISA",
        exposures=(exposure,),
    )
    degradation = evaluate_degradation(environment)
    base = turb.make_roughness(
        surface="airfoil",
        model=turb.RoughnessModel.MANUFACTURED_FINISH,
        equivalent_sand_grain_m=5e-6,
        source="machined finish",
    )
    roughness = turb.roughness_from_degradation(degradation, base=base)
    assert roughness.model is turb.RoughnessModel.ICED
    assert roughness.equivalent_sand_grain_m > base.equivalent_sand_grain_m
    assert "aeroworkbench-environmental" in roughness.source
    assert roughness.provenance.inputs_hash != base.provenance.inputs_hash


# -- E. transition / separation / disagreement -------------------------------


def test_advphys12_model_disagreement_flags_spread() -> None:
    disagreement = turb.compare_model_predictions(
        "drag",
        {
            turb.TurbulenceModel.K_EPSILON: 0.003,
            turb.TurbulenceModel.K_OMEGA_SST: 0.005,
        },
        threshold=0.2,
    )
    assert disagreement.exceeded
    assert disagreement.spread == pytest.approx(0.5)
    assert disagreement.canonical()["values"][0][0] == "kEpsilon"
    with pytest.raises(turb.TurbulenceValidationError):
        turb.compare_model_predictions("drag", {turb.TurbulenceModel.K_EPSILON: 0.003})


def test_advphys12_transition_location_fraction() -> None:
    flow = _low_re_flow()
    fraction, reference = turb.transition_location_fraction(
        flow, critical_reynolds=5.0e4, source="declared Re_c"
    )
    assert fraction == pytest.approx(0.5)
    assert reference.correlation_id == "critical-reynolds-transition"
    with pytest.raises(turb.TurbulenceValidationError):
        turb.transition_location_fraction(flow, critical_reynolds=0.0, source="x")


def test_advphys12_skin_friction_distribution_is_bounded() -> None:
    flow = _flat_plate_flow()
    values, reference = turb.skin_friction_distribution_flat_plate(flow, sample_count=5)
    assert len(values) == 5
    assert all(value > 0.0 for value in values)
    assert values[0] > values[-1]
    assert reference.correlation_id == "schlichting-turbulent-skin-friction"


def test_advphys12_sensitivity_to_intensity_and_roughness() -> None:
    flow = _low_re_flow()

    def intensity_model(state: turb.FlowState) -> float:
        return state.reynolds_number * (1.0 + state.turbulence_intensity)

    def roughness_model(state: turb.FlowState) -> float:
        assert state.roughness is not None
        return state.roughness.equivalent_sand_grain_m * state.reynolds_number

    assert turb.intensity_sensitivity(flow, model_fn=intensity_model) > 0.0
    assert turb.roughness_sensitivity(flow, model_fn=roughness_model) > 0.3
    no_roughness = _flat_plate_flow()
    with pytest.raises(turb.TurbulenceValidationError):
        turb.roughness_sensitivity(no_roughness, model_fn=roughness_model)


def test_advphys12_diagnostics_surface_escalation_triggers() -> None:
    flow = _low_re_flow()
    classification = turb.classify_regime(flow)
    selection = turb.select_turbulence_model(flow, classification)
    report = turb.assess_diagnostics(
        flow,
        classification,
        selection,
        model_predictions={
            turb.TurbulenceModel.K_EPSILON: 0.003,
            turb.TurbulenceModel.K_OMEGA_SST: 0.005,
        },
        skin_friction=(0.003, 0.0025),
        pressure_coefficient_values=(-0.4, 0.1),
        transition_location=0.5,
    )
    assert any(reason.startswith("MODEL_DISAGREEMENT") for reason in report.escalation_reasons)
    assert report.canonical()["units"]["skinFriction"] == "1"
    assert report.validity.passed
    assert len(report.provenance.inputs_hash) == 64


def test_advphys12_large_separation_triggers_escalation() -> None:
    payload = _fixture("separated_diffuser.json")
    flow = _flow(payload["flow"])
    classification = turb.classify_regime(flow)
    selection = turb.select_turbulence_model(flow, classification)
    report = turb.assess_diagnostics(flow, classification, selection)
    assert any(reason.startswith("LARGE_SEPARATED_REGION") for reason in report.escalation_reasons)


# -- F. solver adapter integration -------------------------------------------


def test_advphys12_derive_solver_flow_model_for_rans() -> None:
    flow = _flat_plate_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    requirement = turb.wall_requirement_for_mode(
        surface="plate",
        mode=turb.WallTreatmentMode.WALL_FUNCTION,
        flow=flow,
        layer_count=12,
        growth_ratio=1.3,
    )
    solver = turb.derive_solver_flow_model(
        flow=flow, selection=selection, wall_requirement=requirement
    )
    assert solver.simulation_type == "RAS"
    assert solver.ras_model == "SpalartAllmaras"
    assert solver.wall_function == "nutkWallFunction"
    assert solver.les_model is None
    assert solver.canonical()["simulationType"] == "RAS"


def test_advphys12_derive_solver_flow_model_transition() -> None:
    flow = _low_re_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    solver = turb.derive_solver_flow_model(flow=flow, selection=selection)
    assert solver.transition_model == "kOmegaSSTLM"
    text = turb.openfoam_turbulence_properties(solver)
    assert "simulationType  RAS;" in text
    assert "RASModel        kOmegaSSTLM;" in text
    assert "transition      on;" in text


def test_advphys12_roughness_wall_settings() -> None:
    flow = _low_re_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    requirement = turb.wall_requirement_for_mode(
        surface="airfoil",
        mode=turb.WallTreatmentMode.WALL_FUNCTION,
        flow=flow,
        layer_count=12,
        growth_ratio=1.3,
    )
    solver = turb.derive_solver_flow_model(
        flow=flow,
        selection=selection,
        wall_requirement=requirement,
        roughness=flow.roughness,
        roughness_constant_cs=0.5,
    )
    assert solver.wall_function == turb.ROUGHNESS_WALL_FUNCTION
    text = turb.openfoam_wall_roughness(solver)
    assert "Ks" in text
    assert "Cs" in text


def test_advphys12_laminar_selection_has_laminar_simulation() -> None:
    flow = turb.FlowState(
        label="laminar",
        reynolds_number=1.0e4,
        mach_number=0.05,
        turbulence_intensity=0.001,
        reference=turb.ReferenceScales("x", 0.1, 1.0, "declared"),
    )
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    assert selection.model is turb.TurbulenceModel.LAMINAR
    solver = turb.derive_solver_flow_model(flow=flow, selection=selection)
    assert solver.simulation_type == "laminar"
    assert "simulationType  laminar;" in turb.openfoam_turbulence_properties(solver)


class _FakeNativeBackend:
    backend_id = "fake-turbulence"
    software_version = "9.9.9"

    def solve(self, request: turb.NativeTurbulenceRequest) -> turb.NativeTurbulenceSolution:
        return turb.NativeTurbulenceSolution(
            transition_location_fraction=0.4,
            separation_fraction=0.1,
            skin_friction=(0.003, 0.0025),
            pressure_coefficient=(-0.5, 0.2),
            detail="fake native solve",
        )


def test_advphys12_native_fails_closed_without_backend() -> None:
    flow = _flat_plate_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    with pytest.raises(turb.TurbulenceCapabilityUnavailableError):
        turb.solve_native_turbulence_or_fail(flow, selection, run_id="run-1")
    assert isinstance(
        turb.probe_any_native_turbulence_capability().canonical()["available"], bool
    )


def test_advphys12_native_backend_seam_is_native() -> None:
    flow = _flat_plate_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    result = turb.evaluate_native_turbulence(
        flow, selection, backend=_FakeNativeBackend(), run_id="cfd-run-1"
    )
    assert result.source is ResultSource.NATIVE_SOLVER
    assert result.solver_name == "fake-turbulence"
    assert result.solver_version == "9.9.9"
    assert result.provenance.run_id == "cfd-run-1"
    assert len(result.provenance.inputs_hash) == 64
    assert result.canonical()["source"] == "native_solver"
    assert result.canonical()["units"]["skinFriction"] == "1"


def test_advphys12_native_requires_run_id() -> None:
    flow = _flat_plate_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    with pytest.raises(turb.TurbulenceValidationError):
        turb.evaluate_native_turbulence(
            flow, selection, backend=_FakeNativeBackend(), run_id=None
        )


def test_advphys12_screening_is_never_labelled_native() -> None:
    flow = _flat_plate_flow()
    selection = turb.select_turbulence_model(flow, turb.classify_regime(flow))
    assert selection.provenance.source is ResultSource.ANALYTICAL
    assert selection.canonical()["source"] == "analytical"


# -- G. portable benchmarks --------------------------------------------------


def test_advphys12_portable_benchmarks_cover_four_categories() -> None:
    cases = turb.portable_benchmarks()
    kinds = {case.kind for case in cases}
    assert kinds == {
        turb.BenchmarkKind.LOW_REYNOLDS_AIRFOIL,
        turb.BenchmarkKind.FLAT_PLATE_BOUNDARY_LAYER,
        turb.BenchmarkKind.SEPARATED_INTERNAL_FLOW,
        turb.BenchmarkKind.ROTATING_BLADE_SECTION,
    }
    assert all(case.reference_source for case in cases)


def test_advphys12_benchmark_results_are_labelled_and_pass() -> None:
    for case in turb.portable_benchmarks():
        result = turb.run_benchmark(case)
        assert result.source is ResultSource.BENCHMARK
        assert result.validity.passed, result.canonical()
        assert result.canonical()["source"] == "benchmark"
        assert result.canonical()["units"]
        assert len(result.provenance.inputs_hash) == 64


def test_advphys12_benchmark_never_claims_native() -> None:
    for case in turb.portable_benchmarks():
        result = turb.run_benchmark(case)
        assert result.source is not ResultSource.NATIVE_SOLVER


# -- H. fixtures and determinism ---------------------------------------------


def test_advphys12_fixtures_drive_portable_cases() -> None:
    for name in (
        "low_re_airfoil.json",
        "flat_plate_boundary_layer.json",
        "separated_diffuser.json",
        "rotating_blade_section.json",
    ):
        payload = _fixture(name)
        flow = _flow(payload["flow"])
        classification = turb.classify_regime(flow)
        assert classification.regime.value == payload["expect"]["regime"]
        selection = turb.select_turbulence_model(flow, classification)
        if payload["expect"].get("transitionModelRequired"):
            assert selection.validity.supports_transition
        assert selection.provenance.inputs_hash


def test_advphys12_wall_fixtures_match_measured_mesh() -> None:
    for name in ("low_re_airfoil.json", "flat_plate_boundary_layer.json"):
        payload = _fixture(name)
        flow = _flow(payload["flow"])
        wall = payload["wall"]
        requirement = turb.wall_requirement_for_mode(
            surface=wall["surface"],
            mode=turb.WallTreatmentMode(wall["mode"]),
            flow=flow,
            layer_count=wall["layerCount"],
            growth_ratio=wall["growthRatio"],
        )
        compatibility = turb.evaluate_wall_treatment(
            requirement, _measured(wall["measured"], wall["surface"])
        )
        assert compatibility.compatible is wall["expectCompatible"], compatibility.detail


def test_advphys12_results_are_deterministic_and_hashable() -> None:
    first = turb.classify_regime(_low_re_flow()).canonical()
    second = turb.classify_regime(_low_re_flow()).canonical()
    assert first == second
    assert len(first["inputsHash"]) == 64
    variant = turb.FlowState(
        label="low-re-airfoil",
        reynolds_number=1.0e5,
        mach_number=0.05,
        turbulence_intensity=0.02,
        reference=turb.ReferenceScales("airfoil chord", 0.15, 10.0, "declared chord reference"),
        transition_state=turb.TransitionState.NATURAL,
        thresholds=turb.LOW_REYNOLDS_THRESHOLDS,
        source="test fixture",
    )
    assert turb.classify_regime(variant).provenance.inputs_hash != first["inputsHash"]
