"""TURBO 05: manufacturability, buildability, and operating-limit constraints.

Envelopes are data bound into the canonical design-revision system. Cheap hard
limits reject candidates during generation (before CAD) and at staged screening
gates (before solvers); missing native capability and missing measurements fail
closed. Every rejection carries a typed, machine-readable violation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from aeroworkbench_optimization import (
    CandidateGenerator,
    GenerationRequest,
    flatten_design_state,
    preflight_design_state,
)

_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "packages" / "manufacturing"
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from aeroworkbench_manufacturing import (  # noqa: E402
    ConstraintClass,
    EnvelopeError,
    EnvelopeSet,
    EvaluationStage,
    HardwareLimitEnvelope,
    LimitProvenance,
    LimitRelation,
    LimitSourceKind,
    ManufacturabilityGate,
    ManufacturingProcessEnvelope,
    Measurement,
    ScalarLimit,
    bind_envelopes,
    envelope_design_constraints,
    evaluate_candidate,
    merge_envelope_constraints,
    rank_by_manufacturability,
    select_admissible,
    verify_binding,
)

DESIGN_SPACE = r"""
{
  "id": "turbo05-space",
  "variables": [
    { "id": "process", "kind": "categorical",
      "bindings": [{ "target": "solver", "path": "mfg.process" }], "baseValue": "subtractive",
      "domain": { "kind": "categorical", "values": ["subtractive", "additive"] } },
    { "id": "chord", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "blade.chord", "unit": "mm" }],
      "baseValue": 50.0, "domain": { "kind": "continuous", "lower": 10.0, "upper": 200.0 } },
    { "id": "wall", "kind": "continuous", "unit": "mm",
      "bindings": [{ "target": "parameter", "path": "blade.wall", "unit": "mm" }],
      "baseValue": 2.0, "domain": { "kind": "continuous", "lower": 0.1, "upper": 5.0 } }
  ],
  "branches": [],
  "constraints": []
}
"""

_PROCESS_SELECTOR = {"op": "equals", "variable": "process", "value": "subtractive"}
_ADDITIVE_SELECTOR = {"op": "equals", "variable": "process", "value": "additive"}


def space() -> dict:
    return json.loads(DESIGN_SPACE)


def base_state(**overrides: object) -> dict:
    state: dict = {
        "process": {"kind": "categorical", "value": "subtractive"},
        "chord": {"kind": "number", "value": 50.0, "unit": "mm"},
        "wall": {"kind": "number", "value": 2.0, "unit": "mm"},
    }
    state.update(overrides)
    return state


def _provenance(kind: LimitSourceKind, reference: str) -> LimitProvenance:
    return LimitProvenance(kind, reference, revision="2", software="std-2026")


def _limit(
    limit_id: str,
    value_name: str,
    relation: LimitRelation,
    limit: float,
    unit: str,
    stage: EvaluationStage,
    *,
    source: LimitSourceKind = LimitSourceKind.USER_REQUIREMENT,
    reference: str = "requirement",
    constraint_class: ConstraintClass = ConstraintClass.HARD,
    applies_when: dict | None = None,
    recommended: tuple[str, ...] = (),
) -> ScalarLimit:
    return ScalarLimit(
        id=limit_id,
        value_name=value_name,
        relation=relation,
        limit=limit,
        unit=unit,
        stage=stage,
        constraint_class=constraint_class,
        provenance=_provenance(source, reference),
        applies_when=applies_when,
        recommended_variables=recommended,
    )


def manufacturing_envelopes() -> EnvelopeSet:
    stock = ManufacturingProcessEnvelope(
        id="stock-envelope",
        process="stock-material",
        revision=2,
        provenance=_provenance(LimitSourceKind.MANUFACTURING_METHOD, "stock-capability"),
        limits=(
            _limit(
                "max-chord-stock",
                "chord",
                LimitRelation.LESS_OR_EQUAL,
                120.0,
                "mm",
                EvaluationStage.PRE_CAD_ALGEBRAIC,
                source=LimitSourceKind.MANUFACTURING_METHOD,
                reference="stock-envelope",
                recommended=("chord",),
            ),
        ),
    )
    subtractive = ManufacturingProcessEnvelope(
        id="subtractive-5axis",
        process="subtractive-5axis",
        revision=3,
        applies_when=_PROCESS_SELECTOR,
        provenance=_provenance(LimitSourceKind.MANUFACTURING_METHOD, "shop-capability"),
        limits=(
            _limit(
                "min-wall-subtractive",
                "wall",
                LimitRelation.GREATER_OR_EQUAL,
                1.0,
                "mm",
                EvaluationStage.PRE_CAD_ALGEBRAIC,
                source=LimitSourceKind.MANUFACTURING_METHOD,
                reference="cutter-radius",
                recommended=("wall",),
            ),
        ),
    )
    additive = ManufacturingProcessEnvelope(
        id="additive-lpbf",
        process="additive-lpbf",
        revision=1,
        applies_when=_ADDITIVE_SELECTOR,
        provenance=_provenance(LimitSourceKind.MANUFACTURING_METHOD, "printer-capability"),
        limits=(
            _limit(
                "min-wall-additive",
                "wall",
                LimitRelation.GREATER_OR_EQUAL,
                0.4,
                "mm",
                EvaluationStage.PRE_CAD_ALGEBRAIC,
                source=LimitSourceKind.MANUFACTURING_METHOD,
                reference="laser-spot",
                recommended=("wall",),
            ),
        ),
    )
    return EnvelopeSet(manufacturing=(stock, subtractive, additive))


def hardware_envelopes() -> EnvelopeSet:
    rotor = HardwareLimitEnvelope(
        id="rotor-assembly",
        component="impeller-rotor",
        revision=2,
        provenance=_provenance(LimitSourceKind.CERTIFIED_COMPONENT, "rotor-cert"),
        limits=(
            _limit(
                "max-rpm",
                "rpm",
                LimitRelation.LESS_OR_EQUAL,
                60000.0,
                "rpm",
                EvaluationStage.PRE_SOLVER_PHYSICS,
                source=LimitSourceKind.BEARING,
                reference="bearing-dn-limit",
                recommended=("rpm",),
            ),
            _limit(
                "max-tip-speed",
                "tip_speed",
                LimitRelation.LESS_OR_EQUAL,
                450.0,
                "m/s",
                EvaluationStage.PRE_SOLVER_PHYSICS,
                source=LimitSourceKind.MATERIAL,
                reference="material-tip-speed",
                recommended=("rpm", "diameter"),
            ),
            _limit(
                "min-running-clearance",
                "clearance",
                LimitRelation.GREATER_OR_EQUAL,
                0.2,
                "mm",
                EvaluationStage.PRE_SOLVER_PHYSICS,
                source=LimitSourceKind.USER_REQUIREMENT,
                reference="rub-clearance",
                recommended=("clearance", "rpm"),
            ),
            _limit(
                "min-trailing-edge",
                "trailing_edge_radius",
                LimitRelation.GREATER_OR_EQUAL,
                0.3,
                "mm",
                EvaluationStage.POST_CAD_GEOMETRY,
                source=LimitSourceKind.MANUFACTURING_METHOD,
                reference="edge-tooling",
                recommended=("trailing_edge_radius",),
            ),
            _limit(
                "max-rotor-stress",
                "stress",
                LimitRelation.LESS_OR_EQUAL,
                550.0,
                "MPa",
                EvaluationStage.NATIVE_SOLVER_VALIDATED,
                source=LimitSourceKind.MATERIAL,
                reference="allowable-stress",
                recommended=("wall", "rpm"),
            ),
        ),
    )
    return EnvelopeSet(hardware=(rotor,))


def full_envelopes() -> EnvelopeSet:
    mfg = manufacturing_envelopes()
    hw = hardware_envelopes()
    return EnvelopeSet(
        manufacturing=mfg.manufacturing,
        hardware=hw.hardware,
        schema_version=mfg.schema_version,
    )


def flat(**overrides: object) -> dict:
    return flatten_design_state(space(), base_state(**overrides))


def _native_stress(
    value: float, *, trusted: bool = True, source: str = "native_solver"
) -> Measurement:
    return Measurement(
        name="stress",
        value=value,
        unit="MPa",
        source=source,
        fidelity="transient",
        software="code_aster",
        software_version="14.6",
        run_id="run-0001",
        inputs_hash="a" * 64,
        trusted=trusted,
    )


def accepted_measurements() -> dict[str, Measurement]:
    return {
        "rpm": Measurement("rpm", 50000.0, "rpm"),
        "tip_speed": Measurement("tip_speed", 400.0, "m/s"),
        "clearance": Measurement("clearance", 0.5, "mm"),
        "trailing_edge_radius": Measurement("trailing_edge_radius", 0.5, "mm"),
        "stress": _native_stress(480.0),
    }


def _violation_ids(report) -> list[str]:  # type: ignore[no-untyped-def]
    return [item.constraint_id for item in report.hard_violations]


def test_turbo05_envelopes_round_trip_and_revision() -> None:
    envelopes = full_envelopes()
    rebuilt = EnvelopeSet.from_dict(envelopes.as_dict())
    assert rebuilt == envelopes
    assert rebuilt.content_hash == envelopes.content_hash

    original = envelopes.manufacturing[0]
    bumped = original.revise(limits=original.limits)
    assert bumped.revision == original.revision + 1
    assert bumped.parent_hash == original.content_hash
    assert bumped.content_hash != original.content_hash
    with pytest.raises(EnvelopeError, match="REVISE_MUST_NOT_SET_REVISION"):
        original.revise(revision=9)


def test_turbo05_binding_hash_verified_and_tamper_fails_closed() -> None:
    envelopes = full_envelopes()
    section = bind_envelopes({"contentHash": "b" * 64}, envelopes)
    assert section["binding"]["designRevisionHash"] == "b" * 64
    verify_binding(section, envelopes)

    tampered = json.loads(json.dumps(section))
    tampered["binding"]["envelopeSetHash"] = "0" * 64
    with pytest.raises(EnvelopeError, match="HASH_MISMATCH"):
        verify_binding(tampered, envelopes)


def test_turbo05_chord_above_envelope_rejected_before_cad() -> None:
    gate = ManufacturabilityGate(manufacturing_envelopes())
    report = gate.evaluate(flat(chord={"kind": "number", "value": 150.0, "unit": "mm"}))
    assert report.status == "rejected"
    violation = next(
        item for item in report.hard_violations if item.constraint_id == "max-chord-stock"
    )
    assert violation.stage == EvaluationStage.PRE_CAD_ALGEBRAIC.value
    assert violation.measured_value_si == pytest.approx(0.150)
    assert violation.limit_si == pytest.approx(0.120)
    assert violation.unit == "mm"
    assert violation.recommended_variables == ("chord",)
    assert violation.source["reference"] == "stock-envelope"
    assert report.cleared_stages == ()
    assert report.permits(EvaluationStage.PRE_CAD_ALGEBRAIC) is False
    assert report.permits(EvaluationStage.NATIVE_SOLVER_VALIDATED) is False


def test_turbo05_rpm_above_component_limit_rejected_before_solver() -> None:
    gate = ManufacturabilityGate(hardware_envelopes())
    report = gate.evaluate(
        flat(),
        measurements={
            "rpm": Measurement("rpm", 70000.0, "rpm"),
            "tip_speed": Measurement("tip_speed", 500.0, "m/s"),
        },
    )
    assert report.status == "rejected"
    ids = {item.constraint_id for item in report.hard_violations}
    assert {"max-rpm", "max-tip-speed"} <= ids
    assert "max-rpm" in _violation_ids(report)
    rpm = next(item for item in report.hard_violations if item.constraint_id == "max-rpm")
    assert rpm.stage == EvaluationStage.PRE_SOLVER_PHYSICS.value
    assert rpm.measured_value_si == pytest.approx(70000.0 / 60.0)
    assert rpm.limit_si == pytest.approx(1000.0)
    assert report.stage_reached == "none"
    assert EvaluationStage.NATIVE_SOLVER_VALIDATED.value not in report.cleared_stages


def test_turbo05_thin_trailing_edge_rejected_post_cad() -> None:
    gate = ManufacturabilityGate(hardware_envelopes())
    report = gate.evaluate(
        flat(),
        measurements={
            "trailing_edge_radius": Measurement("trailing_edge_radius", 0.1, "mm"),
        },
    )
    violation = next(
        item for item in report.hard_violations if item.constraint_id == "min-trailing-edge"
    )
    assert violation.stage == EvaluationStage.POST_CAD_GEOMETRY.value
    assert violation.measured_value_si == pytest.approx(1e-4)
    assert violation.limit_si == pytest.approx(3e-4)


def test_turbo05_missing_post_cad_measurement_fails_closed() -> None:
    gate = ManufacturabilityGate(hardware_envelopes())
    report = gate.evaluate(flat())
    assert report.status == "rejected"
    unresolved = {item.constraint_id for item in report.unresolved}
    assert "min-trailing-edge" in unresolved
    trailing = next(item for item in report.unresolved if item.constraint_id == "min-trailing-edge")
    assert trailing.reason == "geometry-not-built"
    assert trailing.measured_available is False


def test_turbo05_running_clearance_negative_after_growth() -> None:
    gate = ManufacturabilityGate(hardware_envelopes())
    report = gate.evaluate(
        flat(),
        measurements={"clearance": Measurement("clearance", -0.05, "mm")},
    )
    violation = next(
        item for item in report.hard_violations if item.constraint_id == "min-running-clearance"
    )
    assert violation.measured_value_si == pytest.approx(-5e-5)
    assert violation.reason == "LIMIT_EXCEEDED"


def test_turbo05_native_limit_requires_trusted_receipt() -> None:
    gate = ManufacturabilityGate(hardware_envelopes())
    missing = gate.evaluate(flat())
    assert "max-rotor-stress" in {item.constraint_id for item in missing.unresolved}

    untrusted = gate.evaluate(
        flat(),
        measurements={"stress": _native_stress(480.0, trusted=False, source="analytical")},
    )
    stress = next(
        item for item in untrusted.unresolved if item.constraint_id == "max-rotor-stress"
    )
    assert stress.reason == "native-receipt-untrusted"

    trusted = gate.evaluate(flat(), measurements=accepted_measurements())
    assert trusted.status == "accepted"
    assert "native-solver-validated" in trusted.cleared_stages
    assert trusted.permits(EvaluationStage.NATIVE_SOLVER_VALIDATED) is True


def test_turbo05_process_switch_changes_active_constraints() -> None:
    gate = ManufacturabilityGate(manufacturing_envelopes())
    thin_wall = {"kind": "number", "value": 0.5, "unit": "mm"}

    subtractive = gate.evaluate(
        flat(process={"kind": "categorical", "value": "subtractive"}, wall=thin_wall)
    )
    additive = gate.evaluate(
        flat(process={"kind": "categorical", "value": "additive"}, wall=thin_wall)
    )

    assert subtractive.status == "rejected"
    assert additive.status == "accepted"
    assert "min-wall-subtractive" in _violation_ids(subtractive)
    assert "min-wall-subtractive" in subtractive.active_limit_ids
    assert "min-wall-additive" not in subtractive.active_limit_ids
    assert "min-wall-additive" in additive.active_limit_ids
    assert "min-wall-subtractive" not in additive.active_limit_ids


def test_turbo05_design_space_compiles_and_generation_flags_rejections() -> None:
    envelopes = manufacturing_envelopes()
    merged = merge_envelope_constraints(space(), envelopes)
    constant = envelope_design_constraints(space(), envelopes)
    compiled_ids = {item["id"] for item in constant}
    assert {"max-chord-stock", "min-wall-subtractive", "min-wall-additive"} <= compiled_ids
    kinds = {item["kind"] for item in constant}
    assert kinds == {"relation", "requires"}

    thin_wall = {"kind": "number", "value": 0.5, "unit": "mm"}
    subtractive_state = base_state(
        process={"kind": "categorical", "value": "subtractive"}, wall=thin_wall
    )
    additive_state = base_state(
        process={"kind": "categorical", "value": "additive"}, wall=thin_wall
    )
    subtractive_thin = preflight_design_state(merged, subtractive_state)
    assert any(
        "min-wall-subtractive:REQUIRED_CONDITION_UNMET" in item for item in subtractive_thin
    )
    additive_thin = preflight_design_state(merged, additive_state)
    assert not any("min-wall-subtractive" in item for item in additive_thin)
    assert not any("min-wall-additive" in item for item in additive_thin)

    generator = CandidateGenerator(merged, GenerationRequest("grid", levels=3, budget=200))
    offenders = [
        candidate
        for candidate in generator
        if any(
            item.variable_id == "chord" and float(item.value) == 200.0
            for item in candidate.assignment
        )
    ]
    assert offenders
    assert all(not candidate.valid for candidate in offenders)
    assert any(
        "max-chord-stock:RELATION_VIOLATION" in candidate.preflight_reasons
        for candidate in offenders
    )


def test_turbo05_generation_filtered_before_expensive_work() -> None:
    envelopes = manufacturing_envelopes()
    merged = merge_envelope_constraints(space(), envelopes)
    gate = ManufacturabilityGate(envelopes)

    generator = CandidateGenerator(merged, GenerationRequest("grid", levels=3, budget=200))
    admitted = select_admissible(gate, generator)

    assert admitted
    for candidate in admitted:
        assert candidate.valid
        assert evaluate_candidate(gate, candidate).admissible
    chords = [
        float(item.value)
        for candidate in admitted
        for item in candidate.assignment
        if item.variable_id == "chord"
    ]
    assert chords
    assert max(chords) <= 120.0


def test_turbo05_hard_violation_never_optimized_away_by_soft_score() -> None:
    gate = ManufacturabilityGate(manufacturing_envelopes())
    accepted = gate.evaluate(
        flat(),
        soft_metrics={"cost": 0.9, "machining_time": 0.8},
    )
    assert accepted.admissible
    assert accepted.score is not None
    assert accepted.score == pytest.approx((0.20 * 0.9 + 0.20 * 0.8) / 0.40)

    rejected = gate.evaluate(
        flat(chord={"kind": "number", "value": 150.0, "unit": "mm"}),
        soft_metrics={"cost": 0.0, "machining_time": 0.0},
    )
    assert not rejected.admissible
    assert rejected.score is None

    ranked = rank_by_manufacturability([rejected, accepted])
    assert ranked == (accepted,)
    assert rejected not in ranked
