"""ADV-PHYS 09: generic performance maps, ROM, and surrogate generation.

These tests drive the product-neutral ROM layer from typed, deterministic
fixtures: declared independent variables with units, bounded sampling through
the existing candidate machinery, several model families, cross-validation,
solver/test fusion, active refinement, system consumption with fidelity
escalation, and a content-addressed artifact cache. Every result retains
source/fidelity/units/validity/provenance; native sampling and neural
surrogates are capability-gated and fail closed; nothing is fabricated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_optimization.design_space import validate_design_space
from aeroworkbench_optimization.drivers import StudyConstraint
from aeroworkbench_optimization.planner import FidelityPlan
from aeroworkbench_rom import (
    ArtifactRef,
    CapabilityUnavailable,
    CrossValidationReport,
    ExtrapolationError,
    ExtrapolationPolicy,
    IndependentVariable,
    MapArtifactCache,
    MapConsumption,
    MapContractError,
    MapFidelity,
    MapSample,
    NearestInterpolator,
    NeuralSurrogate,
    OutputVariable,
    PerformanceMap,
    PodRom,
    PolynomialResponseSurface,
    RBFSurrogate,
    RefinementCriteria,
    RefinementPlan,
    SampleKind,
    SamplingPlan,
    StructuredInterpolator,
    ValidationError,
    VariableKind,
    assess_trust,
    build_map,
    build_model,
    calibrate_simulation,
    calibration_offsets,
    consume_map,
    cross_validate,
    design_space_from_variables,
    fused_sample_set,
    map_trust,
    merge_samples,
    native_sample,
    native_sampling_capability,
    propose_refinement,
    refine,
    require_native_sampling,
    require_neural,
)
from aeroworkbench_rom.errors import CacheIntegrityError

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "rom"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _variables() -> tuple[IndependentVariable, ...]:
    payload = _fixture("variables.json")
    return tuple(
        IndependentVariable(
            name=item["name"],
            unit=item["unit"],
            kind=VariableKind(item["kind"]),
            lower=float(item["lower"]),
            upper=float(item["upper"]),
        )
        for item in payload["variables"]
    )


def _outputs() -> tuple[OutputVariable, ...]:
    payload = _fixture("variables.json")
    return tuple(
        OutputVariable(name=item["name"], unit=item["unit"]) for item in payload["outputs"]
    )


def _samples(name: str = "samples.json") -> tuple[MapSample, ...]:
    payload = _fixture(name)
    return tuple(
        MapSample(
            sample_id=item["id"],
            inputs={key: float(value) for key, value in item["inputs"].items()},
            outputs={key: float(value) for key, value in item["outputs"].items()},
            source=MapFidelity(item["source"]),
            kind=SampleKind(item["kind"]),
            cost=float(item.get("cost", 0.0)),
        )
        for item in payload["samples"]
    )


def _constraints() -> tuple[StudyConstraint, ...]:
    payload = _fixture("constraints.json")
    return tuple(
        StudyConstraint(
            name=item["name"], bound=item["bound"], limit=float(item["limit"]), unit=item["unit"]
        )
        for item in payload["constraints"]
    )


def _plan(**options: Any) -> SamplingPlan:
    defaults: dict[str, Any] = {
        "plan_id": "rom-fixture-plan",
        "strategy": "lhs",
        "count": 8,
        "seed": 7,
    }
    defaults.update(options)
    return SamplingPlan(variables=_variables(), **defaults)


def _model(family: str, **options: Any) -> Any:
    return build_model(family, **options)


def _map(
    family: str = "polynomial",
    samples: tuple[MapSample, ...] | None = None,
    **options: Any,
) -> PerformanceMap:
    return build_map(
        map_id="rom-fixture-map",
        variables=_variables(),
        outputs=_outputs(),
        samples=_samples() if samples is None else samples,
        model=_model(family, **options),
    )


def _validated_map(tolerances: dict[str, float] | None = None) -> PerformanceMap:
    samples = _samples()
    report = cross_validate(lambda: _model("polynomial", degree=2), samples, folds=3, seed=1)
    model = _model("polynomial", degree=2)
    model.fit([dict(s.inputs) for s in samples], [dict(s.outputs) for s in samples])
    return PerformanceMap(
        map_id="rom-fixture-map",
        revision=1,
        variables=_variables(),
        outputs=_outputs(),
        model=model,
        samples=samples,
        validation=report,
    )


def _analytic_sample(point: dict[str, float], sample_id: str) -> MapSample:
    mach = point["mach"]
    alpha = point["alpha_deg"]
    return MapSample(
        sample_id=sample_id,
        inputs=dict(point),
        outputs={
            "lift_coefficient": 0.1 + 0.9 * mach + 0.05 * alpha,
            "drag_coefficient": 0.02 + 0.01 * alpha * alpha + 0.1 * mach * mach,
        },
        source=MapFidelity.ANALYTICAL,
        kind=SampleKind.SIMULATION,
        cost=1.0,
    )


# -- A. declared variables ----------------------------------------------------


def test_advphys09_variable_requires_unit_and_finite_bounds() -> None:
    with pytest.raises(MapContractError):
        IndependentVariable("mach", "", VariableKind.CONTINUOUS, 0.0, 1.0)
    with pytest.raises(MapContractError):
        IndependentVariable("mach", "1", VariableKind.CONTINUOUS, 1.0, 0.0)
    with pytest.raises(MapContractError):
        IndependentVariable("mach", "1", VariableKind.INTEGER, 0.0, 2.5)


def test_advphys09_discrete_variable_needs_values() -> None:
    with pytest.raises(MapContractError):
        IndependentVariable("n", "1", VariableKind.DISCRETE, 0.0, 1.0)
    variable = IndependentVariable("n", "1", VariableKind.DISCRETE, 0.0, 2.0, (0.0, 1.0, 2.0))
    assert variable.contains(2.0) and not variable.contains(3.0)


def test_advphys09_output_variable_needs_unit() -> None:
    with pytest.raises(MapContractError):
        OutputVariable("thrust", "")


# -- B. sampling plan ---------------------------------------------------------


def test_advphys09_plan_design_space_validates_with_existing_contract() -> None:
    plan = _plan()
    validate_design_space(plan.design_space())
    assert plan.design_space()["id"] == "rom-fixture-plan"


def test_advphys09_plan_generates_bounded_deterministic_samples() -> None:
    plan = _plan(count=6, seed=11)
    first = plan.sample_points()
    second = plan.sample_points()
    assert first == second
    assert len(first) == 6
    assert all(set(point) == {"mach", "alpha_deg"} for point in first)


def test_advphys09_plan_digest_is_stable_and_seed_sensitive() -> None:
    assert _plan().digest() == _plan().digest()
    assert _plan(seed=1).digest() != _plan(seed=2).digest()


def test_advphys09_enumerative_plan_needs_explicit_budget() -> None:
    with pytest.raises(MapContractError):
        SamplingPlan(plan_id="p", variables=_variables(), strategy="grid", count=4)


def test_advphys09_adaptive_points_exclude_known_points() -> None:
    plan = _plan(strategy="grid", count=9, budget=9)
    known = plan.sample_points()
    fresh = plan.adaptive_points(exclude=known, round_index=1)
    assert fresh == ()
    partial = plan.adaptive_points(exclude=known[:4], round_index=1)
    assert len(partial) == 5


# -- C. model families --------------------------------------------------------


def test_advphys09_nearest_matches_training_point_exactly() -> None:
    samples = _samples()
    model = NearestInterpolator(neighbors=3)
    model.fit([dict(s.inputs) for s in samples], [dict(s.outputs) for s in samples])
    prediction = model.predict({"mach": 0.55, "alpha_deg": 2.0})
    assert prediction.outputs["lift_coefficient"] == pytest.approx(0.695, abs=1e-9)
    assert prediction.uncertainty["lift_coefficient"] >= 0.0


def test_advphys09_polynomial_response_surface_is_exact_for_polynomial_data() -> None:
    samples = _samples()
    model = PolynomialResponseSurface(degree=2)
    model.fit([dict(s.inputs) for s in samples], [dict(s.outputs) for s in samples])
    for sample in samples:
        prediction = model.predict(dict(sample.inputs))
        assert prediction.outputs["lift_coefficient"] == pytest.approx(
            sample.outputs["lift_coefficient"], abs=1e-6
        )
        assert prediction.outputs["drag_coefficient"] == pytest.approx(
            sample.outputs["drag_coefficient"], abs=1e-6
        )


def test_advphys09_rbf_interpolates_training_points() -> None:
    samples = _samples()
    model = RBFSurrogate()
    model.fit([dict(s.inputs) for s in samples], [dict(s.outputs) for s in samples])
    prediction = model.predict({"mach": 0.9, "alpha_deg": 8.0})
    assert prediction.outputs["lift_coefficient"] == pytest.approx(1.31, abs=1e-4)
    assert prediction.uncertainty["lift_coefficient"] == pytest.approx(0.0, abs=1e-9)


def test_advphys09_structured_interpolator_predicts_full_grid() -> None:
    samples = _samples()
    model = StructuredInterpolator()
    model.fit([dict(s.inputs) for s in samples], [dict(s.outputs) for s in samples])
    center = model.predict({"mach": 0.55, "alpha_deg": 2.0})
    assert center.outputs["lift_coefficient"] == pytest.approx(0.695, abs=1e-9)
    midpoint = model.predict({"mach": 0.375, "alpha_deg": -1.0})
    assert 0.0 < midpoint.outputs["lift_coefficient"] < 1.31


def test_advphys09_structured_interpolator_requires_full_grid() -> None:
    samples = _samples()[:5]
    model = StructuredInterpolator()
    with pytest.raises(MapContractError):
        model.fit([dict(s.inputs) for s in samples], [dict(s.outputs) for s in samples])


def test_advphys09_pod_reconstructs_snapshots() -> None:
    payload = _fixture("field_snapshots.json")
    parameter = payload["parameter"]
    inputs = [{parameter: float(item[parameter])} for item in payload["snapshots"]]
    fields = [tuple(float(value) for value in item["field"]) for item in payload["snapshots"]]
    rom = PodRom(energy=0.999)
    rom.fit(inputs, fields)
    assert rom.mode_count >= 1
    assert rom.reconstruction_error < 1e-6
    reconstructed = rom.predict_field(inputs[0])
    assert reconstructed == pytest.approx(fields[0], abs=1e-6)


def test_advphys09_neural_surrogate_fails_closed_without_backend() -> None:
    with pytest.raises(CapabilityUnavailable):
        NeuralSurrogate()
    with pytest.raises(CapabilityUnavailable):
        build_model("neural")
    with pytest.raises(CapabilityUnavailable):
        require_neural(present=False)


def test_advphys09_build_model_unknown_family_fails_closed() -> None:
    with pytest.raises(MapContractError):
        build_model("magic-regression")


# -- D. map contract ----------------------------------------------------------


def test_advphys09_map_records_units_sources_and_validity() -> None:
    performance_map = _map()
    payload = performance_map.canonical_payload()
    assert {item["unit"] for item in payload["variables"]} == {"1", "deg"}
    assert {item["unit"] for item in payload["outputs"]} == {"1"}
    assert set(payload["sourceSampleIds"]) == {f"s{i}" for i in range(1, 10)}
    assert payload["extrapolation"] == "reject"
    assert payload["validityDomain"]["mach"] == [0.2, 0.9]
    assert performance_map.source_label is MapFidelity.SURROGATE


def test_advphys09_map_prediction_is_labelled_surrogate() -> None:
    prediction = _map().predict({"mach": 0.5, "alpha_deg": 2.0})
    assert prediction.source is MapFidelity.SURROGATE
    assert prediction.source is not MapFidelity.NATIVE
    assert prediction.inside_validity is True
    assert prediction.trusted is False


def test_advphys09_map_rejects_silent_extrapolation() -> None:
    performance_map = _map()
    with pytest.raises(ExtrapolationError):
        performance_map.predict({"mach": 1.5, "alpha_deg": 2.0})


def test_advphys09_map_clamp_and_escalate_are_explicit() -> None:
    performance_map = _map()
    clamped = performance_map.predict(
        {"mach": 1.5, "alpha_deg": 2.0}, policy=ExtrapolationPolicy.CLAMP
    )
    assert clamped.extrapolated is True and clamped.inside_validity is False
    escalated = performance_map.predict(
        {"mach": 1.5, "alpha_deg": 2.0}, policy=ExtrapolationPolicy.ESCALATE
    )
    assert escalated.requires_escalation is True and escalated.extrapolated is True


def test_advphys09_map_digest_changes_with_revision() -> None:
    performance_map = _map()
    assert performance_map.digest() == _map().digest()
    assert performance_map.with_revision(revision=2).digest() != performance_map.digest()


def test_advphys09_map_rejects_unknown_point_fields() -> None:
    with pytest.raises(MapContractError):
        _map().predict({"mach": 0.5})


def test_advphys09_native_sample_requires_solver_identity() -> None:
    with pytest.raises(MapContractError):
        MapSample(
            sample_id="n1",
            inputs={"mach": 0.5},
            outputs={"lift_coefficient": 0.5},
            source=MapFidelity.NATIVE,
            kind=SampleKind.SIMULATION,
        )
    native = MapSample(
        sample_id="n1",
        inputs={"mach": 0.5},
        outputs={"lift_coefficient": 0.5},
        source=MapFidelity.NATIVE,
        kind=SampleKind.SIMULATION,
        solver=("cfd", "2.0"),
        run_id="run-1",
    )
    assert native.provenance()["solver"] == {"id": "cfd", "version": "2.0"}


def test_advphys09_surrogate_over_native_samples_is_still_surrogate() -> None:
    native = MapSample(
        sample_id="n1",
        inputs={"mach": 0.5, "alpha_deg": 2.0},
        outputs={"lift_coefficient": 0.5, "drag_coefficient": 0.1},
        source=MapFidelity.NATIVE,
        kind=SampleKind.SIMULATION,
        solver=("cfd", "2.0"),
        run_id="run-1",
    )
    performance_map = _map("nearest", samples=(native,))
    prediction = performance_map.predict({"mach": 0.5, "alpha_deg": 2.0})
    assert prediction.source is MapFidelity.SURROGATE
    assert performance_map.canonical_payload()["samples"][0]["source"] == "native"


# -- E. cross-validation and trust -------------------------------------------


def test_advphys09_cross_validation_records_error_statistics() -> None:
    report = cross_validate(lambda: _model("polynomial", degree=2), _samples(), folds=3)
    assert isinstance(report, CrossValidationReport)
    names = {stats.name for stats in report.per_output}
    assert names == {"lift_coefficient", "drag_coefficient"}
    assert all(stats.count == 9 for stats in report.per_output)
    assert report.passed({"lift_coefficient": 1e-6, "drag_coefficient": 1e-6})


def test_advphys09_unvalidated_map_is_not_trusted() -> None:
    decision = map_trust(_map())
    assert decision.trusted is False
    assert decision.status == "unvalidated"


def test_advphys09_validated_map_is_trusted_within_tolerance() -> None:
    performance_map = _validated_map()
    decision = map_trust(
        performance_map, {"lift_coefficient": 1e-6, "drag_coefficient": 1e-6}
    )
    assert decision.trusted is True
    assert decision.status == "validated"


def test_advphys09_cross_validation_needs_enough_samples() -> None:
    with pytest.raises(ValidationError):
        cross_validate(lambda: _model("polynomial", degree=2), _samples()[:2], folds=3)


def test_advphys09_assess_trust_fails_on_loose_tolerance() -> None:
    report = cross_validate(lambda: _model("nearest"), _samples(), folds=3)
    decision = assess_trust(report, {"lift_coefficient": 1e-12, "drag_coefficient": 1e-12})
    assert decision.trusted is False
    assert decision.status == "failed"


# -- F. solver/test fusion ----------------------------------------------------


def test_advphys09_merge_keeps_simulation_and_experiment_separate() -> None:
    fused = merge_samples(_samples(), _samples("experiment_samples.json"))
    assert len(fused.simulations()) == 9
    assert len(fused.experiments()) == 3
    assert len(fused.digest()) == 64


def test_advphys09_calibration_offsets_from_paired_points() -> None:
    offsets = calibration_offsets(_samples(), _samples("experiment_samples.json"))
    table = {offset.name: offset for offset in offsets}
    assert table["lift_coefficient"].offset == pytest.approx(0.05)
    assert table["drag_coefficient"].offset == pytest.approx(-0.01)
    assert table["lift_coefficient"].count == 3


def test_advphys09_calibration_preserves_lineage_and_source() -> None:
    offsets = calibration_offsets(_samples(), _samples("experiment_samples.json"))
    calibrated = calibrate_simulation(_samples(), offsets, revision=2)
    match = next(sample for sample in calibrated if sample.lineage == ("s2",))
    assert match.source is MapFidelity.ANALYTICAL
    assert match.kind is SampleKind.SIMULATION
    assert match.outputs["lift_coefficient"] == pytest.approx(0.43)
    assert match.sample_id == "s2~cal2"


def test_advphys09_fused_set_contains_both_kinds() -> None:
    fused = fused_sample_set(_samples(), _samples("experiment_samples.json"), revision=1)
    kinds = {sample.kind for sample in fused.samples}
    assert kinds == {SampleKind.SIMULATION, SampleKind.EXPERIMENT}


# -- G. active refinement -----------------------------------------------------


def test_advphys09_refinement_selects_high_uncertainty_points() -> None:
    performance_map = _map("nearest", samples=_samples()[:1])
    plan = propose_refinement(
        performance_map,
        _plan(count=8),
        RefinementCriteria(uncertainty_threshold=0.01, include_extrapolation_candidates=False),
        budget=3,
    )
    assert isinstance(plan, RefinementPlan)
    assert 0 < len(plan.points) <= 3
    assert all("high-uncertainty" in point.reasons for point in plan.points)
    assert len(plan.digest) == 64


def test_advphys09_refinement_requests_extrapolation_points() -> None:
    performance_map = _map("nearest", samples=_samples()[:4])
    plan = propose_refinement(
        performance_map,
        _plan(strategy="grid", count=9, budget=9),
        RefinementCriteria(include_extrapolation_candidates=True),
        budget=5,
    )
    assert any(point.extrapolates for point in plan.points)
    assert all(point.reasons for point in plan.points)


def test_advphys09_refinement_is_bounded() -> None:
    performance_map = _map("nearest", samples=_samples()[:1])
    plan = propose_refinement(
        performance_map,
        _plan(count=20),
        RefinementCriteria(uncertainty_threshold=1e-6),
        budget=2,
    )
    assert len(plan.points) <= 2
    assert plan.budget == 2


def _tiny_variable() -> IndependentVariable:
    return IndependentVariable("x", "1", VariableKind.CONTINUOUS, 0.0, 1.0)


def _tiny_samples() -> tuple[MapSample, ...]:
    return (
        MapSample("t0", {"x": 0.0}, {"y": 0.0}, MapFidelity.ANALYTICAL, SampleKind.SIMULATION),
        MapSample("t1", {"x": 1.0}, {"y": 1.0}, MapFidelity.ANALYTICAL, SampleKind.SIMULATION),
    )


def _tiny_map(model: Any) -> PerformanceMap:
    return build_map(
        map_id="tiny-map",
        variables=(_tiny_variable(),),
        outputs=(OutputVariable("y", "1"),),
        samples=_tiny_samples(),
        model=model,
    )


def test_advphys09_refinement_selects_near_constraint_boundary() -> None:
    performance_map = _tiny_map(_model("polynomial", degree=1))
    plan = propose_refinement(
        performance_map,
        SamplingPlan("tiny-plan", (_tiny_variable(),), strategy="grid", count=3, budget=3),
        RefinementCriteria(boundary_margin=0.1, include_extrapolation_candidates=False),
        constraints=(StudyConstraint("y", "upper", 0.5),),
        budget=2,
    )
    assert plan.points
    assert all("near-constraint-boundary" in point.reasons for point in plan.points)
    assert plan.points[0].point["x"] == pytest.approx(0.5)


def test_advphys09_refinement_selects_model_disagreement() -> None:
    primary = _model("polynomial", degree=1)
    other = RBFSurrogate()
    other.fit(
        [{"x": 0.0}, {"x": 1.0}],
        [{"y": 1.0}, {"y": 2.0}],
    )
    performance_map = _tiny_map(primary)
    plan = propose_refinement(
        performance_map,
        SamplingPlan("tiny-plan", (_tiny_variable(),), strategy="grid", count=3, budget=3),
        RefinementCriteria(disagreement_threshold=0.5, include_extrapolation_candidates=False),
        disagreement_model=other,
        budget=2,
    )
    assert plan.points
    assert any("model-disagreement" in point.reasons for point in plan.points)


def test_advphys09_refine_loop_adds_samples_and_revisions() -> None:
    performance_map = _map("nearest", samples=_samples()[:4])
    result = refine(
        performance_map,
        _plan(count=6, seed=3),
        RefinementCriteria(uncertainty_threshold=0.001),
        lambda point: _analytic_sample(point, f"r{len(point)}-{round(point['mach'], 4)}"),
        model_factory=lambda: _model("nearest"),
        rounds=2,
        budget=2,
    )
    assert result.rounds >= 1
    assert result.added_samples
    assert result.performance_map.revision > performance_map.revision
    assert len(result.performance_map.samples) > len(performance_map.samples)
    assert result.performance_map.parent_revision == result.performance_map.revision - 1


# -- H. system use ------------------------------------------------------------


def test_advphys09_consume_inside_validated_map() -> None:
    performance_map = _validated_map()
    consumption = consume_map(
        performance_map,
        {"mach": 0.5, "alpha_deg": 2.0},
        tolerances={"lift_coefficient": 1e-6, "drag_coefficient": 1e-6},
    )
    assert isinstance(consumption, MapConsumption)
    assert consumption.trusted is True
    assert consumption.requires_escalation is False
    assert consumption.escalation is None
    assert consumption.source is MapFidelity.SURROGATE
    assert "lift_coefficient" in consumption.outputs


def test_advphys09_consume_outside_validity_rejects() -> None:
    performance_map = _validated_map()
    with pytest.raises(ExtrapolationError):
        consume_map(
            performance_map,
            {"mach": 1.5, "alpha_deg": 2.0},
            tolerances={"lift_coefficient": 1e-6, "drag_coefficient": 1e-6},
        )


def test_advphys09_consume_outside_validity_escalates() -> None:
    performance_map = _validated_map()
    consumption = consume_map(
        performance_map,
        {"mach": 1.5, "alpha_deg": 2.0},
        policy=ExtrapolationPolicy.ESCALATE,
        tolerances={"lift_coefficient": 1e-6, "drag_coefficient": 1e-6},
    )
    assert consumption.requires_escalation is True
    assert isinstance(consumption.escalation, FidelityPlan)
    assert consumption.escalation.level == "native"


def test_advphys09_unvalidated_map_escalates_or_rejects() -> None:
    performance_map = _map()
    escalated = consume_map(
        performance_map, {"mach": 0.5, "alpha_deg": 2.0}, policy=ExtrapolationPolicy.ESCALATE
    )
    assert escalated.trusted is False
    assert escalated.requires_escalation is True
    with pytest.raises(ValidationError):
        consume_map(performance_map, {"mach": 0.5, "alpha_deg": 2.0})


# -- I. content-addressed artifact cache --------------------------------------


def test_advphys09_cache_roundtrip_and_digest() -> None:
    cache = MapArtifactCache()
    payload = {"mapId": "rom-fixture-map", "revision": 1}
    ref = cache.put(payload)
    assert isinstance(ref, ArtifactRef)
    assert len(ref.key) == 64
    assert cache.get(ref.key) == payload
    assert cache.describe(ref.key) == ref


def test_advphys09_cache_is_immutable_and_verifies() -> None:
    cache = MapArtifactCache()
    ref = cache.put({"a": 1})
    assert cache.put({"a": 1}) == ref
    cache._entries[ref.key] = json.dumps({"a": 2})  # tamper
    with pytest.raises(CacheIntegrityError):
        cache.get(ref.key)


def test_advphys09_map_revision_participates_in_cache_key() -> None:
    cache = MapArtifactCache()
    base = _map()
    first = cache.put(base.canonical_payload())
    second = cache.put(base.with_revision(revision=2).canonical_payload())
    assert first.key != second.key
    assert cache.get(first.key)["revision"] == 1
    assert cache.get(second.key)["revision"] == 2


def test_advphys09_cache_is_bounded_and_invalidates() -> None:
    cache = MapArtifactCache(max_entries=2)
    first = cache.put({"value": 1})
    cache.put({"value": 2})
    cache.put({"value": 3})
    assert first.key not in cache.keys()  # noqa: SIM118
    assert len(cache.keys()) == 2
    victim = cache.keys()[0]
    assert cache.invalidate(victim) is True
    assert cache.invalidate(victim) is False
    with pytest.raises(CacheIntegrityError):
        cache.get(victim)


# -- J. capability gating -----------------------------------------------------


def test_advphys09_native_sampling_fails_closed() -> None:
    state = native_sampling_capability("cfd-sampling")
    assert state.state == "unavailable"
    assert state.available is False
    with pytest.raises(CapabilityUnavailable):
        require_native_sampling("cfd-sampling")
    assert native_sampling_capability("cfd-sampling", present=True).available is True


class _FakeNativeBackend:
    solver_name = "fake-cfd"
    solver_version = "1.0"

    def sample(self, point: dict[str, float], *, run_id: str) -> dict[str, float]:
        return {"lift_coefficient": 0.5, "drag_coefficient": 0.1}


def test_advphys09_native_sample_requires_backend() -> None:
    with pytest.raises(CapabilityUnavailable):
        native_sample(
            {"mach": 0.5, "alpha_deg": 2.0},
            ("lift_coefficient", "drag_coefficient"),
            backend=None,
            run_id="run-1",
            sample_id="n1",
        )


def test_advphys09_native_sample_carries_native_identity() -> None:
    sample = native_sample(
        {"mach": 0.5, "alpha_deg": 2.0},
        ("lift_coefficient", "drag_coefficient"),
        backend=_FakeNativeBackend(),
        run_id="run-1",
        sample_id="n1",
    )
    assert sample.source is MapFidelity.NATIVE
    assert sample.solver == ("fake-cfd", "1.0")
    assert sample.run_id == "run-1"


# -- K. determinism -----------------------------------------------------------


def test_advphys09_predictions_are_deterministic() -> None:
    first = _map().predict({"mach": 0.5, "alpha_deg": 2.0})
    second = _map().predict({"mach": 0.5, "alpha_deg": 2.0})
    assert first.as_dict() == second.as_dict()


def test_advphys09_design_space_builder_is_reusable() -> None:
    space = design_space_from_variables("space-a", _variables())
    validate_design_space(space)
    assert [variable["id"] for variable in space["variables"]] == ["mach", "alpha_deg"]
