"""ADV-PHYS 14: physics-driven meshing, wall resolution, adaptive refinement.

These tests drive the product-neutral meshing layer from typed, deterministic
fixtures: physics-aware intent from flow regime and expected gradients, achieved
boundary-layer metrics against y+/clearance/curvature limits, local resolution
rules, rotating/open-propulsor intents, a bounded adaptive-refinement loop with
auditable revisions, mesh-budget control with an explicit insufficient-
resolution state, morph-vs-remesh gating, and a quality receipt. Every result
retains source/fidelity/units/validity/input-hash/software-identity/provenance.
Native meshing is capability-gated and fails closed; nothing is fabricated.
"""

from __future__ import annotations

import builtins
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_convergence import QuantityOfInterest, StudyRun, run_mesh_independence
from aeroworkbench_mesh import (
    MeshSpec,
    SemanticEntity,
    SemanticTopologyReceipt,
    ZoneSpec,
    probe_gmsh,
)
from aeroworkbench_meshing import (
    AdaptationError,
    AdaptationPolicy,
    ErrorIndicator,
    FeatureGeometry,
    FlowRegime,
    IndicatorKind,
    InsufficientResolutionError,
    InterfaceQuality,
    MeshBudget,
    MeshBudgetError,
    MeshContractError,
    MesherCapability,
    MesherCapabilityUnavailable,
    MeshRevision,
    PhysicsIntent,
    PhysicsIntentKind,
    PhysicsState,
    RegionCellCount,
    RegionResolution,
    WallResolutionTarget,
    adapt,
    adaptation_policy_from_budget,
    assess_budget,
    build_native_mesh_physics,
    build_quality_receipt,
    decide_physics_mesh_update,
    derive_local_size,
    estimate_cells,
    flow_reference_from_state,
    intent_digest,
    intents_from_blade_rows,
    intents_from_physics,
    intents_from_propeller,
    layer_heights_mm,
    mesh_box_native,
    mesh_independence_levels,
    next_revision,
    plan_boundary_layer,
    plan_physics_mesh,
    probe_mesher,
    require_feasible,
    require_native_mesher,
    resolution_rules_from_intents,
    total_thickness_mm,
)
from aeroworkbench_semantics import TopologyReport

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "meshing"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _physics() -> PhysicsState:
    payload = _fixture("physics_state.json")
    return PhysicsState(
        regime=FlowRegime(payload["regime"]),
        mach=float(payload["mach"]),
        reynolds=float(payload["reynolds"]),
        gradient_scale_mm=float(payload["gradient_scale_mm"]),
        wake_thickness_mm=float(payload["wake_thickness_mm"]),
        shock_strength=float(payload["shock_strength"]),
        thermal_gradient_k_mm=float(payload["thermal_gradient_k_mm"]),
        structural_thickness_mm=float(payload["structural_thickness_mm"]),
        tip_clearance_mm=float(payload["tip_clearance_mm"]),
        curvature_radius_mm=float(payload["curvature_radius_mm"]),
        contact_length_mm=float(payload["contact_length_mm"]),
        friction_velocity_m_s=float(payload["friction_velocity_m_s"]),
        density_kg_m3=float(payload["density_kg_m3"]),
        dynamic_viscosity_pa_s=float(payload["dynamic_viscosity_pa_s"]),
    )


def _topology() -> SemanticTopologyReceipt:
    payload = _fixture("semantic_topology.json")
    entities = tuple(
        SemanticEntity(
            semantic_key=item["key"],
            kind=item["kind"],
            region=item["region"],
            component=item["component"],
        )
        for item in payload["entities"]
    )
    return SemanticTopologyReceipt(digest="advphys14-fixture", entities=entities)


def _features() -> tuple[tuple[str, FeatureGeometry], ...]:
    payload = _fixture("geometry_features.json")
    return tuple(
        (
            item["key"],
            FeatureGeometry(**{key: value for key, value in item.items() if key != "key"}),
        )
        for item in payload["features"]
    )


def _wall_target(**over: Any) -> WallResolutionTarget:
    payload = _fixture("wall_resolution.json")
    payload.update(over)
    return WallResolutionTarget(
        wall_patches=tuple(payload["wall_patches"]),
        layer_count=int(payload["layer_count"]),
        growth_ratio=float(payload["growth_ratio"]),
        y_plus_target=payload.get("y_plus_target"),
        curvature_limit_fraction=float(payload.get("curvature_limit_fraction", 0.2)),
        clearance_fraction=float(payload.get("clearance_fraction", 0.5)),
        y_plus_tolerance=float(payload.get("y_plus_tolerance", 0.25)),
    )


def _budget(**over: Any) -> MeshBudget:
    payload = _fixture("budget.json")
    payload.update(over)
    return MeshBudget(
        max_cells=int(payload["max_cells"]),
        max_memory_mb=float(payload["max_memory_mb"]),
        max_wall_time_s=float(payload["max_wall_time_s"]),
        max_adaptation_passes=int(payload["max_adaptation_passes"]),
        per_region_max_cells=tuple(
            (str(region), int(cap))
            for region, cap in payload.get("per_region_max_cells", ())
        ),
        bytes_per_cell=int(payload.get("bytes_per_cell", 512)),
        cells_per_second=float(payload.get("cells_per_second", 50000.0)),
    )


def _spec(**over: Any) -> MeshSpec:
    payload: dict[str, Any] = {
        "name": "advphys14",
        "dimension": 3,
        "base_size_mm": 4.0,
        "min_size_mm": 0.1,
        "max_size_mm": 8.0,
    }
    payload.update(over)
    return MeshSpec(
        name=str(payload["name"]),
        dimension=int(payload["dimension"]),
        base_size_mm=float(payload["base_size_mm"]),
        min_size_mm=float(payload["min_size_mm"]),
        max_size_mm=float(payload["max_size_mm"]),
        zones=(
            ZoneSpec("rotor_fluid", "rotating", "fluid", ("rotor",)),
            ZoneSpec("duct_fluid", "stationary", "fluid", ("duct",)),
            ZoneSpec("shaft_solid", "stationary", "solid", ("shaft",)),
        ),
        patches=(),
    )


def _request(**over: Any) -> Any:
    from aeroworkbench_meshing import MeshPlanRequest

    defaults: dict[str, Any] = {
        "name": "advphys14-plan",
        "spec": _spec(),
        "physics": _physics(),
        "budget": _budget(),
        "region_volumes_mm3": (
            ("rotor_fluid", 1000.0),
            ("duct_fluid", 2000.0),
            ("shaft_solid", 1000.0),
        ),
        "topology": _topology(),
        "features": _features(),
        "wall_resolution": _wall_target(),
        "curvature_radius_mm": 3.0,
        "clearance_mm": 0.5,
    }
    defaults.update(over)
    return MeshPlanRequest(**defaults)


def _indicator_payload() -> list[dict[str, Any]]:
    return _fixture("indicators.json")["indicators"]


def _scaled_indicators(scale: float) -> tuple[ErrorIndicator, ...]:
    return tuple(
        ErrorIndicator(
            IndicatorKind(item["kind"]),
            str(item["key"]),
            float(item["magnitude"]) * scale,
        )
        for item in _indicator_payload()
    )


def _preserved_report() -> TopologyReport:
    return TopologyReport((), (), (), (), (), False, "TOPOLOGY_PRESERVED")


# -- A. physics-aware intent --------------------------------------------------


def test_advphys14_intents_from_physics_are_semantic() -> None:
    intents = intents_from_physics(_physics(), _topology())
    kinds = {item.kind for item in intents}
    assert PhysicsIntentKind.NEAR_WALL in kinds
    assert PhysicsIntentKind.SHOCK in kinds
    assert PhysicsIntentKind.WAKE in kinds
    assert PhysicsIntentKind.THERMAL_INTERFACE in kinds
    assert PhysicsIntentKind.THIN_STRUCTURE in kinds
    assert PhysicsIntentKind.TIP_GAP in kinds
    keys = {key for item in intents for key in item.semantic_keys}
    assert keys <= {entity.semantic_key for entity in _topology().entities}


def test_advphys14_intent_requires_semantic_keys_and_valid_size() -> None:
    with pytest.raises(MeshContractError):
        PhysicsIntent(PhysicsIntentKind.WAKE, ())
    with pytest.raises(MeshContractError):
        PhysicsIntent(PhysicsIntentKind.WAKE, ("x",), target_size_mm=0.0)
    with pytest.raises(MeshContractError):
        PhysicsState(FlowRegime.TRANSONIC, shock_strength=1.5)


def test_advphys14_intent_digest_is_deterministic() -> None:
    first = intents_from_physics(_physics(), _topology())
    second = intents_from_physics(_physics(), _topology())
    assert intent_digest(first) == intent_digest(second)
    assert len(intent_digest(first)) == 64


# -- B. boundary-layer generation ---------------------------------------------


def test_advphys14_first_layer_from_y_plus_uses_reference_flow() -> None:
    reference = flow_reference_from_state(_physics())
    assert reference is not None
    assert reference.first_layer_from_y_plus(1.0) == pytest.approx(0.03, rel=1e-9)


def test_advphys14_plan_boundary_layer_records_achieved_metrics() -> None:
    reference = flow_reference_from_state(_physics())
    plan = plan_boundary_layer(
        _wall_target(), reference=reference, curvature_radius_mm=3.0, clearance_mm=0.5
    )
    assert plan.requested_layer_count == 6
    assert plan.achieved_layer_count == 5
    assert "clearance" in plan.limited_by
    assert plan.achieved_total_thickness_mm <= 0.25 + 1e-9
    assert plan.achieved_y_plus == pytest.approx(1.0, rel=1e-9)
    assert plan.valid is True


def test_advphys14_boundary_layer_collision_fails_closed() -> None:
    target = WallResolutionTarget(("walls",), 4, 1.2, first_layer_mm=0.3)
    plan = plan_boundary_layer(target, clearance_mm=0.2)
    assert plan.collision is True
    assert plan.valid is False
    assert plan.achieved_layer_count == 0


def test_advphys14_boundary_layer_needs_reference_for_y_plus() -> None:
    with pytest.raises(MeshContractError):
        plan_boundary_layer(_wall_target())


def test_advphys14_total_thickness_matches_layer_heights() -> None:
    heights = layer_heights_mm(0.03, 1.2, 5)
    assert sum(heights) == pytest.approx(total_thickness_mm(0.03, 1.2, 5))


# -- C. local resolution rules ------------------------------------------------


def test_advphys14_derive_local_size_picks_smallest_driver() -> None:
    derivation = derive_local_size(
        4.0,
        feature=FeatureGeometry(gap_mm=0.4, curvature_radius_mm=2.0, wavelength_mm=10.0),
    )
    assert derivation.size_mm == pytest.approx(0.05)
    assert "gap" in derivation.drivers
    assert derivation.below_floor is False


def test_advphys14_derive_flags_below_floor_without_coarsening() -> None:
    derivation = derive_local_size(
        4.0, feature=FeatureGeometry(gap_mm=0.4), min_size_mm=0.1
    )
    assert derivation.size_mm == pytest.approx(0.05)
    assert derivation.below_floor is True


def test_advphys14_shock_indicator_refines_base_size() -> None:
    derivation = derive_local_size(4.0, feature=FeatureGeometry(shock_indicator=1.0))
    assert derivation.size_mm == pytest.approx(1.0)


def test_advphys14_derive_covers_contact_and_gradient_scale() -> None:
    contact = derive_local_size(4.0, feature=FeatureGeometry(contact_length_mm=2.0))
    assert contact.size_mm == pytest.approx(0.5)
    gradient = derive_local_size(4.0, feature=FeatureGeometry(gradient_scale_mm=1.0))
    assert gradient.size_mm == pytest.approx(0.1)


def test_advphys14_resolution_rules_from_intents_are_deterministic() -> None:
    intents = intents_from_physics(_physics(), _topology())
    first = resolution_rules_from_intents(
        intents, dict(_features()), base_size_mm=4.0, min_size_mm=0.1
    )
    second = resolution_rules_from_intents(
        intents, dict(_features()), base_size_mm=4.0, min_size_mm=0.1
    )
    assert [rule.as_dict() for rule in first] == [rule.as_dict() for rule in second]
    assert first
    assert min(rule.size_mm for rule in first) == pytest.approx(0.25)


# -- D. rotating / open-propulsor specifics via generic intents ---------------


def test_advphys14_blade_rows_map_to_generic_intents() -> None:
    from aeroworkbench_turbomachinery.rows import BladeClearance, BladeRow
    from aeroworkbench_turbomachinery.units import Quantity

    payload = _fixture("blade_rows.json")
    rows = tuple(
        BladeRow(
            row_id=item["row_id"],
            node=item["node"],
            role=item["role"],
            frame=item["frame"],
            shaft=item["shaft"],
            station_in=item["station_in"],
            station_out=item["station_out"],
            clearance=BladeClearance(
                tip_clearance=Quantity(float(item["tip_clearance_mm"]), "mm")
            ),
        )
        for item in payload["rows"]
    )
    intents = intents_from_blade_rows(
        rows, edge_size_mm=0.5, wake_size_mm=0.4, cells_across_gap=10
    )
    kinds = {item.kind for item in intents}
    assert {
        PhysicsIntentKind.LEADING_EDGE,
        PhysicsIntentKind.TRAILING_EDGE,
        PhysicsIntentKind.TIP_GAP,
        PhysicsIntentKind.WAKE,
        PhysicsIntentKind.ROTATING_INTERFACE,
    } <= kinds
    tip = next(
        item
        for item in intents
        if item.kind is PhysicsIntentKind.TIP_GAP
        and item.semantic_keys == ("rotor1:tip_gap",)
    )
    assert tip.target_size_mm == pytest.approx(0.05)


def test_advphys14_open_propeller_maps_to_generic_intents() -> None:
    from aeroworkbench_propulsors.geometry import PropellerGeometry, SpanSection

    payload = _fixture("propulsor.json")
    geometry = PropellerGeometry(
        rotor_id=payload["rotor_id"],
        blade_count=int(payload["blade_count"]),
        tip_radius_m=float(payload["tip_radius_m"]),
        hub_radius_m=float(payload["hub_radius_m"]),
        sections=tuple(
            SpanSection(
                float(section["radius_fraction"]),
                float(section["chord_m"]),
                float(section["twist_deg"]),
            )
            for section in payload["sections"]
        ),
        coaxial=bool(payload["coaxial"]),
        axial_spacing_m=float(payload["axial_spacing_m"]),
    )
    intents = intents_from_propeller(
        geometry, edge_size_mm=0.3, wake_size_mm=2.0, tip_gap_mm=1.0, cells_across_gap=10
    )
    kinds = {item.kind for item in intents}
    assert {
        PhysicsIntentKind.LEADING_EDGE,
        PhysicsIntentKind.TRAILING_EDGE,
        PhysicsIntentKind.SLIPSTREAM,
        PhysicsIntentKind.TIP_GAP,
        PhysicsIntentKind.INTERACTION_REGION,
    } <= kinds
    assert any(
        item.kind is PhysicsIntentKind.TIP_GAP
        and item.target_size_mm == pytest.approx(0.1)
        for item in intents
    )


def test_advphys14_propulsor_intents_drive_resolution_rules() -> None:
    from aeroworkbench_propulsors.geometry import PropellerGeometry, SpanSection

    geometry = PropellerGeometry(
        rotor_id="prop-a",
        blade_count=3,
        tip_radius_m=0.25,
        hub_radius_m=0.04,
        sections=(SpanSection(0.2, 0.06, 15.0), SpanSection(0.9, 0.04, 8.0)),
    )
    intents = intents_from_propeller(
        geometry, edge_size_mm=0.3, wake_size_mm=2.0, tip_gap_mm=0.8, cells_across_gap=10
    )
    rules = resolution_rules_from_intents(intents, {}, base_size_mm=4.0)
    assert min(rule.size_mm for rule in rules) == pytest.approx(0.08)


# -- E. adaptive refinement loop ----------------------------------------------


def test_advphys14_adapt_creates_auditable_revision_lineage() -> None:
    initial = MeshRevision(revision=1, mesh_hash="mesh-1", element_count=1000, min_sicn=0.3)

    def refiner(
        parent: MeshRevision,
        selected: tuple[ErrorIndicator, ...],
        factor: float,
    ) -> MeshRevision:
        return next_revision(
            parent,
            mesh_hash=f"mesh-{parent.revision + 1}",
            refined_keys=tuple(item.semantic_key for item in selected),
            indicators=selected,
            element_count=parent.element_count + 500,
            min_sicn=0.25,
        )

    result = adapt(
        initial=initial,
        indicators=lambda revision: _scaled_indicators(0.5**revision.revision),
        refine=refiner,
        policy=AdaptationPolicy(
            max_passes=4, refinement_factor=0.5, indicator_threshold=0.2, cell_budget=100000
        ),
    )
    assert result.accepted is True
    assert result.stopped_reason == "indicators_below_threshold"
    assert len(result.revisions) >= 3
    for parent, child in zip(result.revisions, result.revisions[1:], strict=False):
        assert child.parent_hash == parent.digest
        assert child.parent_revision == parent.revision
        assert child.revision == parent.revision + 1
    assert result.revisions[0].digest != result.revisions[-1].digest


def test_advphys14_adapt_is_bounded_by_max_passes() -> None:
    initial = MeshRevision(revision=1, mesh_hash="mesh-1", element_count=1000, min_sicn=0.3)

    def refiner(
        parent: MeshRevision,
        selected: tuple[ErrorIndicator, ...],
        factor: float,
    ) -> MeshRevision:
        return next_revision(
            parent,
            mesh_hash=f"m{parent.revision + 1}",
            refined_keys=("k",),
            indicators=selected,
            element_count=parent.element_count + 100,
            min_sicn=0.2,
        )

    result = adapt(
        initial=initial,
        indicators=lambda revision: (ErrorIndicator(IndicatorKind.GRADIENT, "k", 1.0),),
        refine=refiner,
        policy=AdaptationPolicy(max_passes=2, indicator_threshold=0.0),
    )
    assert result.passes == 2
    assert result.stopped_reason == "max_passes_reached"
    assert result.accepted is False


def test_advphys14_adapt_stops_on_cell_budget() -> None:
    initial = MeshRevision(revision=1, mesh_hash="m1", element_count=900, min_sicn=0.3)

    def refiner(
        parent: MeshRevision,
        selected: tuple[ErrorIndicator, ...],
        factor: float,
    ) -> MeshRevision:
        return next_revision(
            parent,
            mesh_hash=f"m{parent.revision + 1}",
            refined_keys=("k",),
            indicators=selected,
            element_count=parent.element_count + 200,
            min_sicn=0.2,
        )

    result = adapt(
        initial=initial,
        indicators=lambda revision: (ErrorIndicator(IndicatorKind.GRADIENT, "k", 1.0),),
        refine=refiner,
        policy=AdaptationPolicy(max_passes=5, indicator_threshold=0.0, cell_budget=1000),
    )
    assert result.stopped_reason == "cell_budget_exceeded"
    assert result.accepted is False


def test_advphys14_adapt_stops_on_quality_gate() -> None:
    initial = MeshRevision(revision=1, mesh_hash="m1", element_count=100, min_sicn=0.3)

    def refiner(
        parent: MeshRevision,
        selected: tuple[ErrorIndicator, ...],
        factor: float,
    ) -> MeshRevision:
        return next_revision(
            parent,
            mesh_hash=f"m{parent.revision + 1}",
            refined_keys=("k",),
            indicators=selected,
            element_count=parent.element_count + 10,
            min_sicn=0.01,
            accepted=False,
        )

    result = adapt(
        initial=initial,
        indicators=lambda revision: (ErrorIndicator(IndicatorKind.GRADIENT, "k", 1.0),),
        refine=refiner,
        policy=AdaptationPolicy(max_passes=3, indicator_threshold=0.0, min_sicn=0.05),
    )
    assert result.stopped_reason == "quality_gate_failed"
    assert result.accepted is False


def test_advphys14_adapt_fails_closed_on_broken_lineage() -> None:
    initial = MeshRevision(revision=1, mesh_hash="m1", element_count=100, min_sicn=0.3)

    def refiner(
        parent: MeshRevision,
        selected: tuple[ErrorIndicator, ...],
        factor: float,
    ) -> MeshRevision:
        return MeshRevision(
            revision=parent.revision + 1,
            mesh_hash="bad",
            element_count=110,
            parent_revision=parent.revision,
            parent_hash="wrong",
        )

    with pytest.raises(AdaptationError):
        adapt(
            initial=initial,
            indicators=lambda revision: (ErrorIndicator(IndicatorKind.GRADIENT, "k", 1.0),),
            refine=refiner,
            policy=AdaptationPolicy(max_passes=1, indicator_threshold=0.0),
        )


def test_advphys14_indicator_kinds_cover_solver_signals() -> None:
    kinds = {
        IndicatorKind.GRADIENT,
        IndicatorKind.RESIDUAL,
        IndicatorKind.QOI_SENSITIVITY,
        IndicatorKind.SHOCK,
        IndicatorKind.VORTICITY,
        IndicatorKind.WAKE,
        IndicatorKind.STRESS_GRADIENT,
        IndicatorKind.TEMPERATURE_GRADIENT,
    }
    assert len(kinds) == 8


# -- F. mesh-budget control ---------------------------------------------------


def test_advphys14_estimate_cells_is_bounded_below_one() -> None:
    assert estimate_cells(1000.0, 1.0) == 1000
    assert estimate_cells(1.0, 1.0) == 1


def test_advphys14_budget_within_budget() -> None:
    resolutions = (
        RegionResolution("a", 0.5, 1000.0),
        RegionResolution("b", 1.0, 2000.0),
    )
    assessment = assess_budget(
        resolutions,
        required_min_size_mm=0.5,
        budget=_budget(),
        base_size_mm=4.0,
        dimension=3,
        floor_size_mm=0.1,
    )
    assert assessment.state == "within_budget"
    assert assessment.feasible is True
    require_feasible(assessment)


def test_advphys14_budget_insufficient_resolution_refuses_coarsening() -> None:
    resolutions = (
        RegionResolution("a", 0.25, 1000.0),
        RegionResolution("b", 0.3, 2000.0),
    )
    assessment = assess_budget(
        resolutions,
        required_min_size_mm=0.25,
        budget=_budget(max_cells=100),
        base_size_mm=4.0,
        dimension=3,
        floor_size_mm=0.1,
    )
    assert assessment.state == "insufficient_resolution"
    assert assessment.feasible is False
    assert assessment.allowed_min_size_mm > 0.25
    with pytest.raises(InsufficientResolutionError):
        require_feasible(assessment)


def test_advphys14_budget_exceeded_when_base_mesh_does_not_fit() -> None:
    assessment = assess_budget(
        (RegionResolution("a", 1.0, 3000.0),),
        required_min_size_mm=1.0,
        budget=_budget(max_cells=100),
        base_size_mm=1.0,
        dimension=3,
        floor_size_mm=0.1,
    )
    assert assessment.state == "budget_exceeded"
    with pytest.raises(MeshBudgetError):
        require_feasible(assessment)


def test_advphys14_budget_region_cap_forces_exceeded() -> None:
    assessment = assess_budget(
        (RegionResolution("a", 0.5, 1000.0),),
        required_min_size_mm=0.5,
        budget=_budget(per_region_max_cells=(("a", 10),)),
        base_size_mm=4.0,
        dimension=3,
        floor_size_mm=0.1,
    )
    assert assessment.state == "budget_exceeded"


def test_advphys14_adaptation_policy_respects_budget() -> None:
    policy = adaptation_policy_from_budget(
        _budget(max_adaptation_passes=3, max_cells=12345), indicator_threshold=0.2
    )
    assert policy.max_passes == 3
    assert policy.cell_budget == 12345
    assert policy.indicator_threshold == 0.2


# -- G. morph versus remesh ---------------------------------------------------


def test_advphys14_update_reuses_unchanged_geometry() -> None:
    decision = decide_physics_mesh_update(
        parent_geometry_hash="g",
        current_geometry_hash="g",
        parent_mesh_hash="m",
        topology_report=_preserved_report(),
        max_param_shift_mm=0.0,
    )
    assert decision.action == "reuse"
    assert decision.forced_remesh is False


def test_advphys14_update_morphs_small_change() -> None:
    decision = decide_physics_mesh_update(
        parent_geometry_hash="g1",
        current_geometry_hash="g2",
        parent_mesh_hash="m",
        topology_report=_preserved_report(),
        max_param_shift_mm=0.5,
    )
    assert decision.action == "morph"
    assert decision.forced_remesh is False


def test_advphys14_update_forces_remesh_on_tip_collapse() -> None:
    decision = decide_physics_mesh_update(
        parent_geometry_hash="g1",
        current_geometry_hash="g2",
        parent_mesh_hash="m",
        topology_report=_preserved_report(),
        max_param_shift_mm=0.5,
        tip_clearance_cells=1,
    )
    assert decision.action == "remesh"
    assert decision.forced_remesh is True
    assert "tip-clearance-collapse" in decision.reasons


def test_advphys14_update_forces_remesh_on_boundary_layer_quality() -> None:
    decision = decide_physics_mesh_update(
        parent_geometry_hash="g",
        current_geometry_hash="g",
        parent_mesh_hash="m",
        topology_report=_preserved_report(),
        max_param_shift_mm=0.0,
        boundary_layer_valid=False,
    )
    assert decision.action == "remesh"
    assert decision.forced_remesh is True
    assert "boundary-layer-quality-failed" in decision.reasons


def test_advphys14_update_forces_remesh_on_topology_change() -> None:
    report = TopologyReport(
        (), (), ("missing.key",), (), (), True, "RECONCILIATION_MISSING_ENTITIES"
    )
    decision = decide_physics_mesh_update(
        parent_geometry_hash="g",
        current_geometry_hash="g",
        parent_mesh_hash="m",
        topology_report=report,
        max_param_shift_mm=0.0,
    )
    assert decision.action == "remesh"
    assert decision.forced_remesh is True


# -- H. quality receipt -------------------------------------------------------


def test_advphys14_gmsh_loader_error_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fail_gmsh_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "gmsh":
            raise OSError("libXft.so.2: cannot open shared object file")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_gmsh_import)

    capability = probe_gmsh()

    assert capability.available is False
    assert capability.version is None
    assert "libXft.so.2" in capability.detail


def test_advphys14_planned_quality_receipt_is_unmeasured() -> None:
    plan = plan_physics_mesh(_request())
    assert plan.boundary_layer is not None
    receipt = build_quality_receipt(
        region_cell_counts=(RegionCellCount("rotor_fluid", 100),),
        boundary_layer=plan.boundary_layer,
        target_y_plus=1.0,
        envelope=plan.envelope,
    )
    assert receipt.measured is False
    assert receipt.min_sicn is None
    assert receipt.non_orthogonality_deg_max is None
    assert receipt.layer_count == plan.boundary_layer.achieved_layer_count
    assert receipt.achieved_y_plus == pytest.approx(1.0, rel=1e-9)
    assert receipt.validity.passed is False


@pytest.mark.skipif(not probe_mesher().available, reason="gmsh not available")
def test_advphys14_measured_quality_receipt_copies_native_metrics(tmp_path: Path) -> None:
    result = mesh_box_native(
        "quality-box", extent_mm=(10.0, 10.0, 10.0), size_mm=2.5, workdir=tmp_path
    )
    assert result.state == "completed"
    assert result.quality is not None
    assert result.envelope is not None
    receipt = build_quality_receipt(
        region_cell_counts=(RegionCellCount("box", result.quality.element_count),),
        interfaces=(InterfaceQuality("box-wall", "wall", 6, True),),
        measured=result.quality,
        minimum_sicn=0.05,
        envelope=result.envelope,
    )
    assert receipt.measured is True
    assert receipt.total_cells == result.quality.element_count
    assert receipt.min_sicn == result.quality.min_sicn
    assert receipt.validity.passed is True
    assert receipt.non_orthogonality_deg_max is None
    assert "checkMesh" in receipt.non_orthogonality_note


# -- I. planner and independence bridge ---------------------------------------


def test_advphys14_plan_is_feasible_and_deterministic() -> None:
    first = plan_physics_mesh(_request())
    second = plan_physics_mesh(_request())
    assert first.digest == second.digest
    assert first.feasible is True
    assert first.validity.passed is True
    assert first.budget.state == "within_budget"
    assert first.boundary_layer is not None and first.boundary_layer.valid
    assert first.envelope.source.value == "analytical"
    assert first.envelope.fidelity.value == "analytical"
    assert len(first.envelope.inputs_hash) == 64
    first.require_feasible()


def test_advphys14_plan_returns_insufficient_resolution_without_coarsening() -> None:
    plan = plan_physics_mesh(_request(budget=_budget(max_cells=100)))
    assert plan.budget.state == "insufficient_resolution"
    assert plan.feasible is False
    assert plan.validity.passed is False
    sizes = dict(plan.per_region_sizes_mm)
    assert sizes["duct_fluid"] == pytest.approx(0.25)
    assert sizes["rotor_fluid"] == pytest.approx(0.3)
    assert plan.required_min_size_mm < plan.budget.allowed_min_size_mm
    with pytest.raises(InsufficientResolutionError):
        plan.require_feasible()


def test_advphys14_plan_budget_exceeded_for_base_mesh() -> None:
    plan = plan_physics_mesh(
        _request(
            topology=None,
            features=(),
            wall_resolution=None,
            budget=_budget(max_cells=10),
            spec=_spec(base_size_mm=1.0, min_size_mm=0.1, max_size_mm=2.0),
        )
    )
    assert plan.budget.state == "budget_exceeded"


def test_advphys14_mesh_independence_levels_feed_gen12() -> None:
    plan = plan_physics_mesh(_request())
    levels = mesh_independence_levels(plan)
    resolutions = [level.resolution for level in levels]
    assert resolutions == sorted(resolutions, reverse=True)
    assert len(set(resolutions)) == len(resolutions)

    def execute(level: Any) -> StudyRun:
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash="a" * 64,
            qoi=(("cl", 0.5 + 0.1 * level.resolution),),
        )

    report = run_mesh_independence(
        levels, (QuantityOfInterest("cl", relative_tolerance=0.5),), execute
    )
    assert report.kind == "mesh"
    assert len(report.levels) == 3


def test_advphys14_envelope_reuses_core_result_contract() -> None:
    payload = plan_physics_mesh(_request()).envelope.as_dict()
    assert "resultContract" in payload
    assert payload["software"]["name"] == "aeroworkbench-meshing"
    assert "units" in payload
    assert "validity" in payload
    assert "provenance" in payload


# -- J. native capability gating ----------------------------------------------


def test_advphys14_native_mesher_capability_reports_honestly() -> None:
    capability = probe_mesher()
    assert isinstance(capability, MesherCapability)
    assert capability.available in (True, False)


def test_advphys14_native_mesher_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import aeroworkbench_meshing.native as native_module

    monkeypatch.setattr(
        native_module, "probe_mesher", lambda: MesherCapability(False, None, "not installed")
    )
    with pytest.raises(MesherCapabilityUnavailable):
        require_native_mesher()
    result = mesh_box_native("missing-gmsh")
    assert result.state == "unavailable"
    assert result.quality is None
    assert result.mesh_hash is None
    failed = build_native_mesh_physics(_spec(), {}, "0" * 64, Path(tempfile.mkdtemp()))
    assert failed.state == "unavailable"


@pytest.mark.skipif(not probe_mesher().available, reason="gmsh not available")
def test_advphys14_native_box_mesh_is_measured_and_deterministic(tmp_path: Path) -> None:
    first = mesh_box_native(
        "smoke-box", extent_mm=(10.0, 10.0, 10.0), size_mm=2.5, workdir=tmp_path
    )
    second = mesh_box_native(
        "smoke-box", extent_mm=(10.0, 10.0, 10.0), size_mm=2.5, workdir=tmp_path
    )
    assert first.state == "completed"
    assert first.quality is not None
    assert first.quality.element_count > 0
    assert first.quality.min_sicn is not None
    assert first.mesh_hash == second.mesh_hash
    assert first.envelope is not None
    assert first.envelope.source.value == "native_solver"
    assert first.envelope.fidelity.value == "native"
    assert first.envelope.provenance.solver_name == "gmsh"
    assert first.envelope.provenance.run_id
