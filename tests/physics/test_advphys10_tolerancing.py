"""ADV-PHYS 10: generic GD&T, tolerance stack-up, assembly, balance, and yield.

These tests drive the product-neutral tolerancing layer from typed,
deterministic fixtures: a revisioned tolerance contract, worst-case / RSS /
Monte-Carlo stack-up, clearance and interference fits, insertion/access and
fastener assembly rules, rotating-body balance with manufacturing mass scatter,
production yield against hard limits, declarative-limit reuse, and a native
capability gate. Every result retains source/fidelity/units/validity/input-hash/
software-identity/provenance; nothing is fabricated.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_dynamics.forcings import assess_forcing_separation
from aeroworkbench_manufacturing.envelopes import (
    EvaluationStage,
    HardwareLimitEnvelope,
    LimitProvenance,
    LimitRelation,
    LimitSourceKind,
    ScalarLimit,
)
from aeroworkbench_tolerancing import (
    MAX_MONTE_CARLO_SAMPLES,
    AssemblyViolation,
    BalanceSpec,
    CapabilityUnavailable,
    CorrectionPlane,
    DatumReference,
    DistributionKind,
    EdgeDistanceRule,
    FastenerJoint,
    FitSpec,
    FitType,
    InsertionPath,
    MassElement,
    MassProperties,
    MassScatterElement,
    StackupError,
    StackupModel,
    StackupTerm,
    ToleranceCallout,
    ToleranceClass,
    ToleranceContract,
    ToleranceContractError,
    YieldError,
    assess_balance,
    assess_fit,
    assess_imbalance,
    assess_robustness,
    balance_scatter,
    check_assembly,
    compute_mass_properties,
    estimate_yield,
    evaluate_limits,
    limits_for,
    native_interference_capability,
    native_interference_check,
    require_native_interference,
    require_robust,
    residual_unbalance_forcing,
    stackup_monte_carlo,
    stackup_statistical,
    stackup_worst_case,
    wilson_interval,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "tolerancing"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _contract() -> ToleranceContract:
    return ToleranceContract.from_dict(_fixture("contract.json"))


def _callouts() -> dict[str, ToleranceCallout]:
    return {callout.id: callout for callout in _contract().callouts}


def _stackup(name: str = "stackup_infeasible.json") -> StackupModel:
    payload = _fixture(name)
    callouts = _callouts()
    terms = tuple(
        StackupTerm(
            id=str(term["id"]),
            callout=callouts[str(term["calloutId"])],
            sensitivity=float(term["sensitivity"]),
        )
        for term in payload["terms"]
    )
    return StackupModel(
        stackup_id=str(payload["stackupId"]),
        characteristic=str(payload["characteristic"]),
        unit=str(payload["unit"]),
        terms=terms,
        lower_spec=float(payload["lowerSpec"]),
        upper_spec=float(payload["upperSpec"]),
    )


def _feasible_stackup() -> StackupModel:
    callouts = _callouts()
    bore = replace(callouts["bore"], lower_deviation=-0.01, upper_deviation=0.01)
    shaft = replace(callouts["shaft"], lower_deviation=-0.01, upper_deviation=0.01)
    runout = replace(
        callouts["face-runout"], lower_deviation=-0.005, upper_deviation=0.005
    )
    return StackupModel(
        stackup_id="running-clearance-tight",
        characteristic="running-clearance",
        unit="mm",
        terms=(
            StackupTerm("bore", bore, 0.5),
            StackupTerm("shaft", shaft, -0.5),
            StackupTerm("runout", runout, 1.0),
        ),
        lower_spec=0.0,
        upper_spec=0.15,
    )


def _balance_payload() -> dict[str, Any]:
    return _fixture("balance.json")


def _mass_elements() -> tuple[MassElement, ...]:
    return tuple(
        MassElement(
            id=str(item["id"]),
            mass_kg=float(item["massKg"]),
            x_m=float(item["xM"]),
            y_m=float(item["yM"]),
            z_m=float(item["zM"]),
        )
        for item in _balance_payload()["elements"]
    )


def _balance_spec() -> BalanceSpec:
    payload = _balance_payload()["spec"]
    return BalanceSpec(
        spec_id=str(payload["specId"]),
        correction_planes=tuple(
            CorrectionPlane(
                id=str(plane["id"]),
                axial_location_m=float(plane["axialLocationM"]),
                radius_m=float(plane["radiusM"]),
            )
            for plane in payload["correctionPlanes"]
        ),
        allowable_residual_kg_m=float(payload["allowableResidualKgM"]),
    )


def _scatter_elements() -> tuple[MassScatterElement, ...]:
    return tuple(
        MassScatterElement(
            id=str(item["id"]),
            mass_kg=float(item["massKg"]),
            mass_tolerance_kg=float(item["massToleranceKg"]),
            x_m=float(item["xM"]),
            y_m=float(item["yM"]),
            z_m=float(item["zM"]),
            distribution=DistributionKind(str(item["distribution"])),
        )
        for item in _balance_payload()["scatterElements"]
    )


# -- A. tolerance contract ----------------------------------------------------


def test_advphys10_callout_requires_known_unit() -> None:
    with pytest.raises(ToleranceContractError):
        ToleranceCallout(
            id="bad",
            characteristic="x",
            tolerance_class=ToleranceClass.DIMENSION,
            nominal=1.0,
            unit="furlong",
            lower_deviation=-0.1,
            upper_deviation=0.1,
        )


def test_advphys10_callout_rejects_inverted_interval() -> None:
    with pytest.raises(ToleranceContractError):
        ToleranceCallout(
            id="bad",
            characteristic="x",
            tolerance_class=ToleranceClass.DIMENSION,
            nominal=1.0,
            unit="mm",
            lower_deviation=0.1,
            upper_deviation=-0.1,
        )


def test_advphys10_asymmetric_tolerance_bounds_are_typed() -> None:
    callout = _callouts()["surface-finish"]
    assert callout.lower_si < callout.nominal_si < callout.upper_si
    assert callout.upper_si - callout.lower_si == pytest.approx(0.6e-6, rel=1e-9)


def test_advphys10_contract_roundtrip_and_revision() -> None:
    contract = _contract()
    rebuilt = ToleranceContract.from_dict(contract.as_dict())
    assert rebuilt.content_hash == contract.content_hash
    revised = contract.revise()
    assert revised.revision == contract.revision + 1
    assert revised.parent_hash == contract.content_hash


def test_advphys10_contract_hash_is_order_stable_and_revision_sensitive() -> None:
    contract = _contract()
    assert contract.content_hash == _contract().content_hash
    assert contract.revise().content_hash != contract.content_hash


def test_advphys10_duplicate_callout_id_fails_closed() -> None:
    callout = _callouts()["bore"]
    with pytest.raises(ToleranceContractError):
        ToleranceContract(contract_id="c", callouts=(callout, callout))


def test_advphys10_datum_index_conflict_fails_closed() -> None:
    contract = _contract()
    conflicting = ToleranceContract(
        contract_id="conflict",
        callouts=(
            ToleranceCallout(
                id="a",
                characteristic="a",
                tolerance_class=ToleranceClass.POSITION,
                nominal=0.0,
                unit="mm",
                lower_deviation=-0.01,
                upper_deviation=0.01,
                datums=(DatumReference("A", "face-one", 1),),
            ),
            ToleranceCallout(
                id="b",
                characteristic="b",
                tolerance_class=ToleranceClass.POSITION,
                nominal=0.0,
                unit="mm",
                lower_deviation=-0.01,
                upper_deviation=0.01,
                datums=(DatumReference("A", "face-two", 1),),
            ),
        ),
    )
    with pytest.raises(ToleranceContractError):
        conflicting.datum_index()
    assert contract.datum_index()["A"] == "mounting-face"


# -- B. stack-up --------------------------------------------------------------


def test_advphys10_worst_case_bounds_never_credit_cancellation() -> None:
    result = stackup_worst_case(_stackup())
    assert result.method == "worst_case"
    assert result.nominal == pytest.approx(0.035, abs=1e-9)
    assert result.lower == pytest.approx(-0.02, abs=1e-9)
    assert result.upper == pytest.approx(0.09, abs=1e-9)
    assert result.within_spec is False


def test_advphys10_rss_is_tighter_than_worst_case() -> None:
    model = _stackup()
    worst = stackup_worst_case(model)
    rss = stackup_statistical(model)
    assert rss.tolerance < worst.tolerance
    assert rss.nominal == pytest.approx(worst.nominal, abs=1e-9)
    assert rss.yield_fraction is not None and 0.0 <= rss.yield_fraction <= 1.0


def test_advphys10_monte_carlo_is_deterministic_and_seed_sensitive() -> None:
    model = _stackup()
    first = stackup_monte_carlo(model, samples=2000, seed=7)
    second = stackup_monte_carlo(model, samples=2000, seed=7)
    other = stackup_monte_carlo(model, samples=2000, seed=8)
    assert first.as_dict() == second.as_dict()
    assert first.envelope.inputs_hash == second.envelope.inputs_hash
    assert first.envelope.inputs_hash != other.envelope.inputs_hash


def test_advphys10_monte_carlo_is_bounded() -> None:
    with pytest.raises(StackupError):
        stackup_monte_carlo(_stackup(), samples=MAX_MONTE_CARLO_SAMPLES + 1, seed=0)
    with pytest.raises(StackupError):
        stackup_monte_carlo(_stackup(), samples=0, seed=0)


def test_advphys10_stackup_unit_dimension_mismatch_fails_closed() -> None:
    callouts = _callouts()
    with pytest.raises(StackupError):
        StackupModel(
            stackup_id="mixed",
            characteristic="mixed",
            unit="mm",
            terms=(StackupTerm("angle", callouts["angular"], 1.0),),
        )


def test_advphys10_every_result_carries_full_provenance() -> None:
    result = stackup_monte_carlo(_stackup(), samples=500, seed=1)
    envelope = result.envelope
    assert envelope.source == "analytical"
    assert envelope.fidelity == "analytical"
    assert envelope.unit == "mm"
    assert envelope.validity == "valid"
    assert len(envelope.inputs_hash) == 64
    assert envelope.software.name == "aeroworkbench-tolerancing"
    assert envelope.provenance.model == "advphys10-tolerance-stackup-monte-carlo"
    assert envelope.assumptions
    json.dumps(result.as_dict())


# -- C. balance and mass properties -------------------------------------------


def test_advphys10_mass_properties_center_of_mass() -> None:
    properties = compute_mass_properties(_mass_elements())
    assert isinstance(properties, MassProperties)
    assert properties.mass_kg == pytest.approx(0.52, abs=1e-12)
    assert properties.center_of_mass_m[2] == pytest.approx(0.05, abs=1e-9)


def test_advphys10_imbalance_has_static_and_dynamic_parts() -> None:
    state = assess_imbalance(_mass_elements())
    assert state.static_magnitude_kg_m > 0.0
    assert state.dynamic_magnitude_kg_m2 > 0.0
    assert state.envelope.unit == "kg*m"


def test_advphys10_balance_assessment_compares_residual_to_allowable() -> None:
    assessment = assess_balance(_balance_spec(), _mass_elements())
    assert assessment.satisfied is True
    assert assessment.residual_kg_m <= assessment.allowable_kg_m


def test_advphys10_balance_scatter_is_deterministic_and_bounded() -> None:
    spec = _balance_spec()
    first = balance_scatter(spec, _scatter_elements(), samples=2000, seed=3)
    second = balance_scatter(spec, _scatter_elements(), samples=2000, seed=3)
    assert first.as_dict() == second.as_dict()
    assert 0.0 <= first.yield_fraction <= 1.0
    assert first.ppm == pytest.approx((1.0 - first.yield_fraction) * 1.0e6)


def test_advphys10_residual_imbalance_feeds_dynamics() -> None:
    line = residual_unbalance_forcing(1.0e-4, 6000.0, source="rotor-1")
    omega = 2.0 * math.pi * 6000.0 / 60.0
    assert line.amplitude == pytest.approx(1.0e-4 * omega * omega, rel=1e-12)
    assert line.order == 1.0
    assert line.speed_dependence == "synchronous"
    assert line.frequency_at(6000.0) == pytest.approx(100.0)
    assessment = assess_forcing_separation([line], [90.0, 110.0], speed_rpm=6000.0)
    assert assessment.state == "clear"


# -- D. assembly constraints --------------------------------------------------


def test_advphys10_clearance_fit_classification() -> None:
    callouts = _callouts()
    spec = FitSpec(
        fit_id="pilot",
        hole=callouts["bore"],
        shaft=callouts["shaft"],
        required_fit=FitType.CLEARANCE,
    )
    assessment = assess_fit(spec, samples=2000, seed=1)
    assert assessment.worst_case_min_clearance >= 0.0
    assert assessment.satisfied is True


def test_advphys10_interference_fit_detects_guaranteed_interference() -> None:
    hole = ToleranceCallout(
        id="hole",
        characteristic="bore",
        tolerance_class=ToleranceClass.DIMENSION,
        nominal=39.95,
        unit="mm",
        lower_deviation=-0.01,
        upper_deviation=0.01,
    )
    shaft = ToleranceCallout(
        id="shaft",
        characteristic="shaft",
        tolerance_class=ToleranceClass.DIMENSION,
        nominal=40.0,
        unit="mm",
        lower_deviation=-0.01,
        upper_deviation=0.01,
    )
    spec = FitSpec(
        fit_id="press",
        hole=hole,
        shaft=shaft,
        required_fit=FitType.INTERFERENCE,
        min_interference=0.01,
    )
    assessment = assess_fit(spec, samples=1000, seed=1)
    assert assessment.worst_case_max_clearance < 0.0
    assert assessment.interference_probability == pytest.approx(1.0)
    assert assessment.satisfied is True


def test_advphys10_required_clearance_worst_case_rejected() -> None:
    callouts = _callouts()
    loose = replace(callouts["shaft"], lower_deviation=-0.1, upper_deviation=0.1)
    spec = FitSpec(
        fit_id="loose",
        hole=callouts["bore"],
        shaft=loose,
        required_fit=FitType.CLEARANCE,
        min_clearance=0.0,
    )
    assessment = assess_fit(spec, samples=1000, seed=1)
    assert assessment.satisfied is False
    assert "WORST_CASE_CLEARANCE_BELOW_MINIMUM" in assessment.violations


def test_advphys10_insertion_and_edge_distance_rules() -> None:
    path = InsertionPath(
        path_id="p", direction=(0.0, 0.0, 1.0), required_length_m=0.04, available_length_m=0.05
    )
    assert path.check().satisfied is True
    short = InsertionPath(
        path_id="p2", direction=(0.0, 1.0, 0.0), required_length_m=0.06, available_length_m=0.05
    )
    assert short.check().satisfied is False
    assert EdgeDistanceRule("r", 0.006, 0.015, 2.0).check().satisfied is True
    assert EdgeDistanceRule("r2", 0.006, 0.010, 2.0).check().satisfied is False


def test_advphys10_fastener_joint_pitch_rule() -> None:
    ok = FastenerJoint(
        "j", fastener_diameter_m=0.006, edge_distance_m=0.015, pitch_m=0.02, min_pitch_ratio=2.5
    )
    assert ok.check().satisfied is True
    bad = FastenerJoint(
        "j2", fastener_diameter_m=0.006, edge_distance_m=0.015, pitch_m=0.012, min_pitch_ratio=2.5
    )
    assert bad.check().satisfied is False


def test_advphys10_check_assembly_reports_typed_violations() -> None:
    callouts = _callouts()
    payload = _fixture("assembly.json")
    fits = tuple(
        FitSpec(
            fit_id=str(item["fitId"]),
            hole=callouts[str(item["holeCalloutId"])],
            shaft=callouts[str(item["shaftCalloutId"])],
            required_fit=FitType(str(item["requiredFit"])),
            min_clearance=float(item["minClearance"]),
        )
        for item in payload["fits"]
    )
    paths = tuple(
        InsertionPath(
            path_id=str(item["pathId"]),
            direction=tuple(float(value) for value in item["direction"]),
            required_length_m=float(item["requiredLengthM"]),
            available_length_m=float(item["availableLengthM"]),
        )
        for item in payload["paths"]
    )
    joints = tuple(
        FastenerJoint(
            joint_id=str(item["jointId"]),
            fastener_diameter_m=float(item["fastenerDiameterM"]),
            edge_distance_m=float(item["edgeDistanceM"]),
            min_edge_ratio=float(item["minEdgeRatio"]),
        )
        for item in payload["joints"]
    )
    report = check_assembly(contract=_contract(), fits=fits, paths=paths, joints=joints)
    assert report.satisfied is True
    assert report.datum_consistent is True

    bad_shaft = replace(callouts["shaft"], lower_deviation=-0.1, upper_deviation=0.1)
    bad_fit = FitSpec(fit_id="bad", hole=callouts["bore"], shaft=bad_shaft)
    rejected = check_assembly(
        contract=_contract(), fits=(*fits, bad_fit), paths=paths, joints=joints
    )
    assert rejected.satisfied is False
    assert any(
        isinstance(item, AssemblyViolation) and item.kind == "fit"
        for item in rejected.violations
    )


# -- E. yield and robustness --------------------------------------------------


def test_advphys10_estimate_yield_and_wilson_interval() -> None:
    estimate = estimate_yield([True] * 990 + [False] * 10, seed=5)
    assert estimate.samples == 1000
    assert estimate.passed == 990
    assert estimate.ppm == pytest.approx(10000.0)
    low, high = wilson_interval(estimate.passed, estimate.samples)
    assert low <= estimate.fraction <= high


def test_advphys10_nominally_valid_but_tolerance_infeasible_is_rejected() -> None:
    report = assess_robustness(_stackup(), required_yield=0.9999, samples=20000, seed=2)
    assert report.nominally_feasible is True
    assert report.tolerance_feasible is False
    assert report.meets_required_yield is False
    assert report.robust is False
    assert report.envelope.validity == "rejected"


def test_advphys10_low_required_yield_never_hides_worst_case_infeasibility() -> None:
    report = assess_robustness(_stackup(), required_yield=0.5, samples=2000, seed=2)
    assert report.meets_required_yield is True
    assert report.tolerance_feasible is False
    assert report.robust is False


def test_advphys10_robust_design_passes_with_rss_and_sampling() -> None:
    report = assess_robustness(_feasible_stackup(), required_yield=0.99, samples=4000, seed=4)
    assert report.nominally_feasible is True
    assert report.tolerance_feasible is True
    assert report.estimated_yield >= 0.99
    assert report.robust is True
    assert report.statistic.method == "rss"


def test_advphys10_require_robust_fails_closed() -> None:
    with pytest.raises(YieldError):
        require_robust(_stackup(), required_yield=0.9973, samples=2000, seed=2)


def test_advphys10_robustness_needs_spec_limits() -> None:
    model = replace(_stackup(), lower_spec=None, upper_spec=None)
    with pytest.raises(YieldError):
        assess_robustness(model)


# -- F. declarative limit reuse -----------------------------------------------


def _envelope_set() -> Any:
    limit = ScalarLimit(
        id="clearance-min",
        value_name="running-clearance",
        relation=LimitRelation.GREATER_OR_EQUAL,
        limit=0.0,
        unit="mm",
        stage=EvaluationStage.PRE_SOLVER_PHYSICS,
        provenance=LimitProvenance(LimitSourceKind.USER_REQUIREMENT, "generic-requirement"),
    )
    hardware = HardwareLimitEnvelope(
        id="assembly-hardware",
        component="generic-assembly",
        limits=(limit,),
        provenance=LimitProvenance(LimitSourceKind.USER_REQUIREMENT, "generic-requirement"),
    )
    from aeroworkbench_manufacturing.envelopes import EnvelopeSet

    return EnvelopeSet(hardware=(hardware,))


def test_advphys10_limits_for_finds_declared_limits() -> None:
    limits = limits_for(_envelope_set(), "running-clearance")
    assert [limit.id for limit in limits] == ["clearance-min"]


def test_advphys10_evaluate_limits_rejects_negative_clearance() -> None:
    limits = limits_for(_envelope_set(), "running-clearance")
    passed = evaluate_limits("running-clearance", 1.0e-5, limits)
    assert passed.satisfied is True
    failed = evaluate_limits("running-clearance", -1.0e-5, limits)
    assert failed.satisfied is False
    assert failed.violations[0].reason == "LIMIT_EXCEEDED"


# -- G. capability gating -----------------------------------------------------


class _FakeNativeBackend:
    solver_name = "native-cad"
    solver_version = "9.1"

    def interference(self, request: dict[str, Any], *, run_id: str) -> dict[str, float]:
        return {"housing|rotor": 0.0}


def test_advphys10_native_interference_fails_closed() -> None:
    state = native_interference_capability()
    assert state.available is False
    with pytest.raises(CapabilityUnavailable):
        require_native_interference()
    with pytest.raises(CapabilityUnavailable):
        native_interference_check(
            {"housing|rotor": {"volume": 1.0}},
            backend=None,
            run_id="run-1",
            request_id="req-1",
        )
    assert native_interference_capability(present=True).available is True


def test_advphys10_native_interference_carries_solver_identity() -> None:
    result = native_interference_check(
        {"housing|rotor": {"volume": 1.0}},
        backend=_FakeNativeBackend(),
        run_id="run-7",
        request_id="req-7",
    )
    assert result.envelope.source == "native_solver"
    assert result.solver_name == "native-cad"
    assert result.overlaps == (("housing", "rotor", 0.0),)
    assert result.envelope.provenance.run_id == "run-7"


# -- H. determinism -----------------------------------------------------------


def test_advphys10_robustness_report_is_deterministic() -> None:
    first = assess_robustness(_feasible_stackup(), required_yield=0.99, samples=1000, seed=9)
    second = assess_robustness(_feasible_stackup(), required_yield=0.99, samples=1000, seed=9)
    assert first.as_dict() == second.as_dict()
    json.dumps(first.as_dict())
