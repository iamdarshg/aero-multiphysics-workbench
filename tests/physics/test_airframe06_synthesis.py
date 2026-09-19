"""AIRFRAME 06: requirements compiler and physics-based initial synthesis.

The fixtures under ``tests/airframe/synthesis`` are tiny declarative requirement
sets. This module proves the compiler is unit-safe and conflict-aware, that the
fixed-wing seed generator honours user hard constraints and emits deterministic,
hashable, provenance-carrying screening evidence, and that seeds feed the existing
design-space / design-state machinery without a special optimizer. Rotorcraft is a
capability-gated seam and fails closed until AIRFRAME 08/#61 is available.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe.synthesis import (
    METHODS,
    SYNTHESIS_MODEL,
    CompiledRequirements,
    RequirementCompileError,
    RequirementConflictError,
    RequirementSpec,
    SynthesisInfeasibleError,
    VehicleSeed,
    build_seed_design_space,
    compile_requirements,
    compile_requirements_payload,
    detect_conflicts,
    generate_fixed_wing_seeds,
    synthesize_initial_seeds,
    synthesize_lifting_body_seam,
    synthesize_rotorcraft_seam,
)
from aeroworkbench_core.design import PhysicalDesignState
from aeroworkbench_optimization.design_space import (
    flatten_design_state,
    numeric_vector,
    validate_design_space,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "airframe" / "synthesis"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _compiled() -> CompiledRequirements:
    return compile_requirements_payload(load_fixture("requirements_tiny.json"))


def _requirement(
    requirement_id: str, metric: str, operator: str, **kwargs: Any
) -> RequirementSpec:
    return RequirementSpec(
        requirement_id=requirement_id,
        kind=str(kwargs.pop("kind", "constraint")),
        metric=metric,
        operator=operator,
        **kwargs,
    )


def test_airframe06_compiler_normalizes_units_and_is_unit_safe() -> None:
    compiled = _compiled()
    metrics = {requirement.metric: requirement for requirement in compiled.requirements}
    assert metrics["stall_speed"].dimension == "velocity"
    assert metrics["stall_speed"].upper_si == pytest.approx(30.0)
    assert metrics["stall_speed"].unit == "m/s"
    assert metrics["range"].lower_si == pytest.approx(400000.0)
    assert metrics["aspect_ratio"].lower_si == pytest.approx(7.0)
    assert metrics["aspect_ratio"].upper_si == pytest.approx(9.0)
    assert compiled.feasible is True
    assert compiled.conflicts == ()

    converted = RequirementSpec(
        requirement_id="REQ-STALL",
        kind="performance",
        metric="stall_speed",
        operator="at_most",
        value=58.3151188,
        unit="kt",
    )
    mixed = compile_requirements(
        [_requirement("REQ-CRUISE", "cruise_speed", "at_least", value=126.0, unit="kt")]
    )
    assert mixed.requirements[0].lower_si == pytest.approx(64.8, rel=1e-3)
    assert compile_requirements([converted]).requirements[0].upper_si == pytest.approx(
        30.0, rel=1e-4
    )


def test_airframe06_compiler_is_deterministic_and_order_independent() -> None:
    payload = load_fixture("requirements_tiny.json")
    first = compile_requirements_payload(payload)
    second = compile_requirements_payload(deepcopy(payload))
    assert first.content_hash == second.content_hash

    reordered = {"requirements": list(reversed(payload["requirements"]))}
    third = compile_requirements_payload(reordered)
    assert third.content_hash == first.content_hash
    assert [r.requirement_id for r in first.requirements] == sorted(
        r.requirement_id for r in first.requirements
    )


def test_airframe06_impossible_requirements_fail_closed_with_explicit_conflicts() -> None:
    with pytest.raises(RequirementConflictError) as raised:
        compile_requirements_payload(load_fixture("requirements_impossible.json"))
    conflicts = raised.value.conflicts
    assert conflicts
    reasons = {conflict.reason for conflict in conflicts}
    assert "LOWER_BOUND_EXCEEDS_UPPER_BOUND" in reasons
    assert any(conflict.metric == "payload_mass" for conflict in conflicts)
    assert any(
        "STALL_SPEED_EXCEEDS_MAX_SPEED" in conflict.reason
        or conflict.metric == "stall_speed>max_speed"
        for conflict in conflicts
    )
    for conflict in conflicts:
        assert len(conflict.requirement_ids) >= 1

    inspected = compile_requirements_payload(
        load_fixture("requirements_impossible.json"), strict=False
    )
    assert inspected.feasible is False
    assert inspected.conflicts == tuple(conflicts)
    assert detect_conflicts(inspected.requirements) == tuple(conflicts)
    with pytest.raises(RequirementConflictError):
        inspected.require_feasible()


def test_airframe06_unknown_metric_unit_and_dimension_fail_closed() -> None:
    with pytest.raises(RequirementCompileError, match="UNKNOWN_REQUIREMENT_METRIC"):
        compile_requirements(
            [_requirement("REQ-X", "warp_speed", "at_least", value=1.0, unit="m/s")]
        )
    with pytest.raises(RequirementCompileError, match="UNKNOWN_REQUIREMENT_UNIT"):
        compile_requirements(
            [_requirement("REQ-X", "payload_mass", "at_least", value=1.0, unit="furlong")]
        )
    with pytest.raises(RequirementCompileError, match="REQUIREMENT_DIMENSION_MISMATCH"):
        compile_requirements(
            [_requirement("REQ-X", "payload_mass", "at_least", value=1.0, unit="m")]
        )
    with pytest.raises(RequirementCompileError, match="REQUIREMENT_BOUNDS_INVERTED"):
        compile_requirements(
            [_requirement("REQ-X", "payload_mass", "between", lower=10.0, upper=1.0, unit="kg")]
        )


def test_airframe06_fixed_wing_fixture_yields_valid_provenanced_seeds() -> None:
    seeds = generate_fixed_wing_seeds(_compiled(), seed_count=2)
    assert len(seeds) == 2
    for seed in seeds:
        assert isinstance(seed, VehicleSeed)
        assert seed.architecture_type == "fixed_wing"
        assert seed.admissible is True
        assert seed.admissibility == ()
        assert seed.content_hash
        for name in (
            "max_takeoff_mass",
            "wing_loading",
            "wing_area",
            "aspect_ratio",
            "wing_span",
            "mean_chord",
            "thrust_to_weight",
            "required_thrust",
            "required_power",
            "horizontal_tail_area",
            "fuel_mass_fraction",
        ):
            assert seed.parameter(name).value_si > 0.0
        assert seed.parameter("quarter_chord_sweep").value_si >= 0.0
        for quantity in seed.quantities:
            assert quantity.method in METHODS
            assert quantity.provenance.source.value == "analytical"
            assert quantity.provenance.model.startswith(SYNTHESIS_MODEL)
            assert len(quantity.provenance.inputs_hash) == 64
            assert quantity.provenance.solver_name is None
            assert quantity.quantity.dimension
            assert quantity.validity.method == quantity.method
            assert quantity.validity.assumptions
    assert seeds[0].parameter("aspect_ratio").value_si != seeds[1].parameter(
        "aspect_ratio"
    ).value_si


def test_airframe06_seeds_never_overwrite_user_hard_constraints() -> None:
    compiled = _compiled()
    seeds = generate_fixed_wing_seeds(compiled, seed_count=2)
    limits = {
        requirement.metric: requirement
        for requirement in compiled.requirements
        if requirement.metric in {"stall_speed", "aspect_ratio", "load_factor", "range"}
    }
    for seed in seeds:
        assert seed.parameter("stall_speed").value_si <= limits["stall_speed"].upper_si
        aspect = seed.parameter("aspect_ratio").value_si
        assert limits["aspect_ratio"].lower_si <= aspect <= limits["aspect_ratio"].upper_si
        assert seed.parameter("load_factor").value_si == pytest.approx(
            limits["load_factor"].lower_si
        )
        assert seed.parameter("range").value_si == pytest.approx(limits["range"].lower_si)
    assert limits["aspect_ratio"].lower_si == pytest.approx(7.0)
    assert limits["stall_speed"].upper_si == pytest.approx(30.0)


def test_airframe06_seeds_are_deterministic_and_hashable() -> None:
    first = generate_fixed_wing_seeds(_compiled(), seed_count=2)
    second = generate_fixed_wing_seeds(_compiled(), seed_count=2)
    assert [seed.seed_id for seed in first] == [seed.seed_id for seed in second]
    assert [seed.content_hash for seed in first] == [seed.content_hash for seed in second]

    reordered = compile_requirements_payload(
        {"requirements": list(reversed(load_fixture("requirements_tiny.json")["requirements"]))}
    )
    third = generate_fixed_wing_seeds(reordered, seed_count=2)
    assert [seed.content_hash for seed in third] == [seed.content_hash for seed in first]


def test_airframe06_seed_feeds_design_space_and_design_state_machinery() -> None:
    seed = generate_fixed_wing_seeds(_compiled(), seed_count=1)[0]
    space = build_seed_design_space(seed)
    validate_design_space(space)
    identifiers = {str(variable["id"]) for variable in space["variables"]}
    assert {"wing_span", "wing_area", "aspect_ratio", "required_thrust"} <= identifiers

    flat = flatten_design_state(space, {})
    assert numeric_vector(flat)
    for entry in flat["entries"]:
        assert entry["active"] is True
        assert entry["bindings"][0]["target"] == "parameter"

    state = seed.to_physical_design_state(
        design_id="airframe06",
        variant_id="v1",
        geometry_hash="a" * 64,
        material_hash="b" * 64,
    )
    assert isinstance(state, PhysicalDesignState)
    assert state.parameters["wing_span"].unit == "m"
    rebuilt = PhysicalDesignState.model_validate_json(state.model_dump_json())
    assert rebuilt == state
    assert len(state.content_hash) == 64


def test_airframe06_missing_or_impossible_requirements_fail_closed() -> None:
    payload_only = compile_requirements(
        [_requirement("REQ-PAYLOAD", "payload_mass", "at_least", value=100.0, unit="kg")]
    )
    with pytest.raises(SynthesisInfeasibleError, match="REQUIRED_METRIC_MISSING:stall_speed"):
        generate_fixed_wing_seeds(payload_only)

    tight = compile_requirements_payload(
        {
            "requirements": [
                {
                    "id": "REQ-PAYLOAD",
                    "kind": "mission",
                    "metric": "payload_mass",
                    "operator": "at_least",
                    "value": 300.0,
                    "unit": "kg",
                },
                {
                    "id": "REQ-STALL",
                    "kind": "performance",
                    "metric": "stall_speed",
                    "operator": "at_most",
                    "value": 30.0,
                    "unit": "m/s",
                },
                {
                    "id": "REQ-CRUISE",
                    "kind": "performance",
                    "metric": "cruise_speed",
                    "operator": "at_least",
                    "value": 65.0,
                    "unit": "m/s",
                },
                {
                    "id": "REQ-SPAN",
                    "kind": "constraint",
                    "metric": "span_limit",
                    "operator": "at_most",
                    "value": 2.0,
                    "unit": "m",
                },
            ]
        }
    )
    with pytest.raises(SynthesisInfeasibleError, match="SPAN_LIMIT_EXCEEDED"):
        generate_fixed_wing_seeds(tight)


def test_airframe06_rotorcraft_seam_is_capability_gated_and_fails_closed() -> None:
    seam = synthesize_rotorcraft_seam(_compiled())
    assert seam.available is False
    assert seam.seeds == ()
    assert "AIRFRAME" in seam.reason or "rotor" in seam.reason.lower()
    assert seam.blocking_issue
    assert seam.provenance.source.value == "analytical"
    assert len(seam.provenance.inputs_hash) == 64


def test_airframe06_lifting_body_seam_uses_planform_volume_and_sweep() -> None:
    compiled = compile_requirements_payload(load_fixture("requirements_lifting_body.json"))
    seam = synthesize_lifting_body_seam(compiled)
    assert seam.available is True
    assert len(seam.seeds) == 1
    quantities = {quantity.name: quantity for quantity in seam.seeds[0].quantities}
    expected = {"lifting_body_planform_area", "lifting_body_thickness_ratio", "lifting_body_sweep"}
    assert expected <= set(quantities)
    assert quantities["lifting_body_thickness_ratio"].validity.valid is True
    assert quantities["lifting_body_planform_area"].quantity.dimension == "area"
    assert 0.0 < quantities["lifting_body_thickness_ratio"].quantity.value_si <= 0.2


def test_airframe06_report_aggregates_seeds_and_seams_deterministically() -> None:
    report = synthesize_initial_seeds(_compiled(), seed_count=2)
    assert report.seeds
    assert {seam.architecture_type for seam in report.seams} >= {"rotorcraft", "lifting_body"}
    assert any(seam.available for seam in report.seams) or any(
        not seam.available for seam in report.seams
    )
    assert report.requirements.content_hash == _compiled().content_hash
    assert report.content_hash == synthesize_initial_seeds(_compiled(), seed_count=2).content_hash
    assert report.canonical_payload()["seeds"]
