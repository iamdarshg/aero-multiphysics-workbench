"""TURBO 06: rotating-gas architecture mapped into the generative design space.

Architecture, per-row, and cycle choices become canonical mixed/conditional/
hierarchical variables; buildability becomes the existing constraints; candidate
generation, cardinality, campaign provenance, and content-addressed identity are
all provided by the shared optimization engine, and the TURBO 05 envelope gate /
TURBO 03 meanline screen prune candidates before CAD and before native promotion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aeroworkbench_manufacturing import EnvelopeSet
from aeroworkbench_optimization import (
    EvaluationResult,
    InMemoryResultStore,
    PhysicsFlags,
    StudyObjective,
    flatten_design_state,
)
from aeroworkbench_turbomachinery import topology_change_sections
from aeroworkbench_turbomachinery.generative import (
    GenerativeSpec,
    apply_mutation,
    architecture_from_state,
    build_design_space,
    candidate_generator,
    cardinality_report,
    default_generation_request,
    design_identity,
    native_promotion_allowed,
    parented_generation_request,
    run_generative_campaign,
    screen_state,
    space_summary,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "generative"
_SPEC = GenerativeSpec(
    space_id="turbo06-generative", max_stages=2, max_rows=3, max_spools=2, levels=2
)


def _space() -> dict[str, Any]:
    return build_design_space(_SPEC)


def _state() -> dict[str, Any]:
    payload = json.loads((_FIXTURES / "tiny_state.json").read_text(encoding="utf-8"))
    return dict(payload)


def _envelopes() -> EnvelopeSet:
    payload = json.loads((_FIXTURES / "tiny_envelope.json").read_text(encoding="utf-8"))
    return EnvelopeSet.from_dict(payload)


def test_turbo06_space_is_mixed_conditional_and_hierarchical() -> None:
    space = _space()
    summary = space_summary(space)
    assert summary.variable_count > 40
    assert summary.branch_count == 5
    assert summary.constraint_count == 6
    kinds = dict(summary.kind_counts)
    assert kinds.get("vector-profile", 0) >= 16
    assert kinds.get("categorical", 0) >= 7
    identifiers = {str(variable["id"]) for variable in space["variables"]}
    assert {
        "family",
        "stage_count",
        "row_count",
        "spool_count",
        "machine_kind",
        "bypass_topology",
        "diffuser_type",
        "process",
        "material_family",
        "overall_pressure_ratio",
        "turbine_inlet_temperature_k",
        "nozzle_area_schedule",
    } <= identifiers


def test_turbo06_every_row_is_independently_variable() -> None:
    space = _space()
    row_variables = [
        v
        for v in space["variables"]
        if str(v["id"]).startswith("row_") and v["kind"] == "vector-profile"
    ]
    assert len(row_variables) == 15
    for variable in row_variables:
        assert variable["domain"].get("lengthVariable") == "row_count"
        assert len(variable["domain"]["controlPoints"]) == _SPEC.max_rows

    flat = flatten_design_state(space, _state())
    entry = next(item for item in flat["entries"] if item["id"] == "row_blade_count")
    assert [point["valueSI"] for point in entry["points"]] == [40.0, 30.0]


def test_turbo06_inactive_branches_are_never_materialized() -> None:
    space = _space()
    request = default_generation_request(_SPEC, strategy="random", count=32, seed=5)
    candidates = list(candidate_generator(space, request))
    assert candidates
    for candidate in candidates:
        family = candidate.state.get("family", {}).get("value")
        if family == "axial":
            assert "diffuser_type" not in candidate.state
        else:
            assert "diffuser_type" in candidate.state
        machine = candidate.state.get("machine_kind", {}).get("value")
        if machine == "driven":
            assert "electrical_power_fraction" in candidate.state
        else:
            assert "electrical_power_fraction" not in candidate.state


def test_turbo06_cardinality_is_exposed_and_budget_bounded() -> None:
    space = _space()
    stochastic = default_generation_request(_SPEC, strategy="random", count=8)
    report = cardinality_report(space, stochastic)
    assert report.exact is False
    assert report.estimate > 0
    assert report.leaf_count > 0
    assert report.exceeds_budget is False
    assert report.reason

    enumerated = default_generation_request(
        _SPEC, strategy="grid", count=1_000_000, budget=64
    )
    bounded = cardinality_report(space, enumerated)
    assert bounded.exceeds_budget is True
    assert bounded.budget == 64

    generator = candidate_generator(space, enumerated)
    assert len(generator.take(64)) == 64


def test_turbo06_generation_is_deterministic_and_lazy() -> None:
    space = _space()
    request = default_generation_request(_SPEC, strategy="random", count=12, seed=3)
    first = [candidate.candidate_hash for candidate in candidate_generator(space, request)]
    second = [candidate.candidate_hash for candidate in candidate_generator(space, request)]
    assert first == second
    assert first

    generator = candidate_generator(space, request)
    assert len(generator.take(2)) == 2
    assert generator.stats.emitted == 2


def test_turbo06_relation_constraints_bind_rows_to_stages() -> None:
    space = _space()
    request = default_generation_request(_SPEC, strategy="random", count=200, seed=11)
    valid = [candidate for candidate in candidate_generator(space, request) if candidate.valid]
    assert valid
    for candidate in valid:
        stages = float(candidate.state["stage_count"]["value"])
        rows = float(candidate.state["row_count"]["value"])
        assert stages <= rows <= 2 * stages


def test_turbo06_architecture_materializes_rows_and_spools() -> None:
    space = _space()
    state = _state()
    architecture = architecture_from_state(space, state, _SPEC)
    assert len(architecture.rows) == 2
    assert architecture.rows[0].frame == "rotating"
    assert architecture.rows[0].shaft == "shaft0"
    assert architecture.rows[1].frame == "stationary"
    assert architecture.rows[1].shaft is None
    assert len(architecture.shafts) == 2

    driven = _state()
    driven["machine_kind"] = {"kind": "categorical", "value": "driven"}
    driven_architecture = architecture_from_state(space, driven, _SPEC)
    assert any(node.kind == "motor_coupling" for node in driven_architecture.nodes)

    radial = _state()
    radial["family"] = {"kind": "categorical", "value": "radial"}
    radial["diffuser_type"] = {"kind": "categorical", "value": "vaned"}
    radial_architecture = architecture_from_state(space, radial, _SPEC)
    assert radial_architecture.rows[-1].role == "diffuser_guide"
    diffuser_row = radial_architecture.rows[-1]
    last_node = next(
        node for node in radial_architecture.nodes if node.node_id == diffuser_row.node
    )
    assert last_node.kind == "diffuser"


def test_turbo06_topology_changes_invalidate_descendants() -> None:
    space = _space()
    before = architecture_from_state(space, _state(), _SPEC)

    family = apply_mutation(space, _state(), "change-row-family")
    assert family.accepted and family.state is not None
    family_sections = topology_change_sections(
        before, architecture_from_state(space, family.state, _SPEC)
    )
    assert "topologyDigest" in family_sections

    geometry = apply_mutation(space, _state(), "perturb-profile-control-points", magnitude=1.0)
    assert geometry.accepted and geometry.state is not None
    geometry_sections = topology_change_sections(
        before, architecture_from_state(space, geometry.state, _SPEC)
    )
    assert "geometry" in geometry_sections

    material = apply_mutation(space, _state(), "change-process-material")
    assert material.accepted and material.state is not None
    material_sections = topology_change_sections(
        before, architecture_from_state(space, material.state, _SPEC)
    )
    assert "materials" in material_sections


def test_turbo06_mutations_are_bounded_deterministic_and_contract_resolved() -> None:
    space = _space()
    state = _state()
    outcome = apply_mutation(
        space, state, "perturb-profile-control-points", magnitude=1.0
    )
    assert outcome.accepted and outcome.state is not None
    assert outcome.changes
    assert outcome.candidate_hash == design_identity(space, outcome.state)

    repeated = apply_mutation(
        space, state, "perturb-profile-control-points", magnitude=1.0
    )
    assert repeated.candidate_hash == outcome.candidate_hash

    noop = apply_mutation(space, state, "perturb-profile-control-points", magnitude=0.0)
    assert noop.accepted is False
    assert noop.reasons == ("OPERATOR_INAPPLICABLE",)

    request = default_generation_request(_SPEC, strategy="random", count=6, seed=2)
    for candidate in candidate_generator(space, request):
        if candidate.valid:
            assert candidate.candidate_hash == design_identity(space, candidate.state)


def test_turbo06_add_and_remove_stage_are_bounded() -> None:
    space = _space()
    state = _state()
    added = apply_mutation(space, state, "add-stage")
    assert added.accepted and added.state is not None
    assert float(added.state["stage_count"]["value"]) == 2.0
    assert float(added.state["row_count"]["value"]) == 3.0
    assert added.candidate_hash == design_identity(space, added.state)

    assert apply_mutation(space, state, "remove-stage").accepted is False

    removed = apply_mutation(space, added.state, "remove-stage")
    assert removed.accepted and removed.state is not None
    assert float(removed.state["stage_count"]["value"]) == 1.0


def test_turbo06_preflight_prunes_impossible_topology_before_cad() -> None:
    space = _space()
    state = _state()
    state["free_power_turbine"] = {"kind": "boolean", "value": True}
    state["spool_count"] = {"kind": "dimensionless", "value": 1.0}
    report = screen_state(space, state, _SPEC)
    assert report.admissible is False
    assert any("free-power-requires-two-spools" in reason for reason in report.preflight_reasons)
    assert report.stage_reached == "design-space-preflight"
    assert report.meanline_checked is False


def test_turbo06_envelope_rejects_before_cad_and_native_fails_closed() -> None:
    space = _space()
    state = _state()
    rejected = screen_state(space, state, _SPEC, envelopes=_envelopes())
    assert rejected.admissible is False
    assert rejected.envelope_status == "rejected"
    assert rejected.meanline_checked is False
    assert rejected.stage_reached.startswith("manufacturing-preflight")
    assert any("max-overall-pressure-ratio" in reason for reason in rejected.envelope_reasons)

    empty = EnvelopeSet.from_dict(
        {"schemaVersion": "turbo05-v1", "manufacturing": [], "hardware": []}
    )
    admitted = screen_state(space, state, _SPEC, envelopes=empty)
    assert admitted.envelope_status == "accepted"

    assert native_promotion_allowed(rejected, receipt_present=True) is False
    assert native_promotion_allowed(admitted, receipt_present=False) is False


def test_turbo06_meanline_screening_runs_before_native_promotion() -> None:
    space = _space()
    report = screen_state(space, _state(), _SPEC)
    assert report.source == "meanline-screening"
    assert report.meanline_checked is True or report.meanline_reasons
    if report.meanline_checked:
        assert report.meanline_screened is not None
        assert report.meanline_validity_passed is not None
        assert report.meanline_pressure_ratio is not None


def test_turbo06_parented_generation_reuses_mutation_provenance() -> None:
    space = _space()
    state = _state()
    request = parented_generation_request(space, state, strategy="random", count=6, seed=4)
    candidates = list(candidate_generator(space, request))
    assert candidates
    for candidate in candidates:
        assert candidate.parent_hash == design_identity(space, state)
        assert candidate.mutations
        assert all(mutation.source == "parent" for mutation in candidate.mutations)


def test_turbo06_campaign_reuses_engine_and_resumes_from_store() -> None:
    space = _space()
    request = default_generation_request(_SPEC, strategy="random", count=8, seed=7)
    objectives = (StudyObjective("pressure_ratio", "maximize"),)

    def evaluator(candidate: Any, fidelity: str) -> EvaluationResult:
        score = 1.0 + sum(value for _, value in candidate.normalized)
        return EvaluationResult(
            outputs={"pressure_ratio": score},
            flags=PhysicsFlags(converged=True, closure_passed=True, validity_ok=True),
            fidelity=fidelity,
        )

    store = InMemoryResultStore()
    first = run_generative_campaign(
        space,
        request,
        campaign_id="turbo06",
        base_revision="base",
        objectives=objectives,
        evaluator=evaluator,
        store=store,
    )
    second = run_generative_campaign(
        space,
        request,
        campaign_id="turbo06",
        base_revision="base",
        objectives=objectives,
        evaluator=evaluator,
        store=store,
    )
    assert first.best is not None
    assert first.best == second.best
    assert second.metrics["cache_hits"] >= 1
