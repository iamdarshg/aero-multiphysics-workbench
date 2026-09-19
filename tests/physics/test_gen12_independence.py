"""GEN 12: numerical-independence gates, physical closure, and promotion.

The independence, closure, and promotion contracts are exercised with small
deterministic synthetic executors first. The generic generative end-to-end
benchmark is then run from its seed/design hash and checked for lineage
completeness. No heavyweight native binary is required: every capability that
is absent is reported SKIPPED with a reason, never substituted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aeroworkbench_convergence import (
    IndependenceError,
    PromotionParticipantEvidence,
    QuantityOfInterest,
    RefinementLevel,
    StudyRun,
    assess_closure,
    assess_field_interface_conservation,
    assess_geometry_clearance,
    assess_promotion,
    assess_resonance_margin,
    run_mesh_independence,
    run_timestep_independence,
)

# ---------------------------------------------------------------------------
# A. numerical independence
# ---------------------------------------------------------------------------


def _converging_executor(*, exact: float = 10.0, coefficient: float = 2.0, order: float = 2.0):
    def execute(level: RefinementLevel) -> StudyRun:
        value = exact + coefficient * level.resolution**order
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash=f"hash-{level.name}",
            qoi=(("pressure_drop", value),),
            source="analytical",
        )

    return execute


def _diverging_executor():
    def execute(level: RefinementLevel) -> StudyRun:
        # Larger change on the finest pair: not numerically independent.
        value = {"coarse": 10.0, "medium": 9.0, "fine": 6.0}[level.name]
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash=f"hash-{level.name}",
            qoi=(("pressure_drop", value),),
        )

    return execute


def _mesh_levels() -> tuple[RefinementLevel, ...]:
    return (
        RefinementLevel("coarse", 0.4, (("element_count", 1000.0),)),
        RefinementLevel("medium", 0.2, (("element_count", 8000.0),)),
        RefinementLevel("fine", 0.1, (("element_count", 64000.0),)),
    )


def test_mesh_independence_passes_on_converging_qoi() -> None:
    report = run_mesh_independence(
        _mesh_levels(),
        (QuantityOfInterest("pressure_drop", "Pa", relative_tolerance=0.02),),
        _converging_executor(),
    )
    assert report.accepted is True
    assert report.kind == "mesh"
    assert report.levels == ("coarse", "medium", "fine")
    trend = report.trends[0]
    assert trend.passed is True
    # Observed order is well defined for a uniform, monotone, three-level ladder.
    assert trend.observed_order == pytest.approx(2.0, abs=0.05)
    assert trend.gci_fine is not None and trend.gci_fine >= 0.0
    assert len(report.run_hashes) == 3 and all(len(item) == 64 for item in report.run_hashes)
    assert report.as_dict()["accepted"] is True


def test_mesh_independence_fails_on_nonconverging_qoi() -> None:
    report = run_mesh_independence(
        _mesh_levels(),
        (QuantityOfInterest("pressure_drop", "Pa", relative_tolerance=0.02),),
        _diverging_executor(),
    )
    assert report.accepted is False
    assert "qoi-not-independent" in report.reason
    assert report.trends[0].passed is False


def test_element_count_similarity_alone_cannot_satisfy_independence() -> None:
    # Identical declared element counts (and qualities) but different QoI: the
    # element-count metadata must not be mistaken for a converged solution.
    levels = (
        RefinementLevel("coarse", 0.4, (("element_count", 8000.0), ("min_sicn", 0.6))),
        RefinementLevel("fine", 0.1, (("element_count", 8000.0), ("min_sicn", 0.6))),
    )
    report = run_mesh_independence(
        levels,
        (QuantityOfInterest("mass_flow", "kg/s", relative_tolerance=0.01),),
        _two_level_executor(10.0, 6.0),
    )
    assert report.accepted is False
    assert "qoi-not-independent" in report.reason
    # And the reverse: different element counts, converged QoI, accepted.
    levels_ok = (
        RefinementLevel("coarse", 0.4, (("element_count", 1000.0),)),
        RefinementLevel("fine", 0.1, (("element_count", 90000.0),)),
    )
    ok = run_mesh_independence(
        levels_ok,
        (QuantityOfInterest("mass_flow", "kg/s", relative_tolerance=0.01),),
        _two_level_executor(10.0, 10.0),
    )
    assert ok.accepted is True


def _two_level_executor(coarse: float, fine: float):
    def execute(level: RefinementLevel) -> StudyRun:
        value = coarse if level.name == "coarse" else fine
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash=f"hash-{level.name}",
            qoi=(("mass_flow", value),),
        )

    return execute


def _timestep_levels() -> tuple[RefinementLevel, ...]:
    return (
        RefinementLevel("coarse", 0.02, (("dt_s", 0.02),)),
        RefinementLevel("medium", 0.01, (("dt_s", 0.01),)),
        RefinementLevel("fine", 0.005, (("dt_s", 0.005),)),
    )


def test_timestep_independence_passes_and_reports_amplitude_trend() -> None:
    def execute(level: RefinementLevel) -> StudyRun:
        # First-order time integration of a fixed response.
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash=f"hash-{level.name}",
            qoi=(
                ("peak_amplitude", 1.0 + 3.0 * level.resolution),
                ("mean_value", 0.5 + 1.0 * level.resolution),
            ),
        )

    report = run_timestep_independence(
        _timestep_levels(),
        (
            QuantityOfInterest("peak_amplitude", "m", relative_tolerance=0.05),
            QuantityOfInterest("mean_value", "m", relative_tolerance=0.05),
        ),
        execute,
        transient=True,
    )
    assert report.accepted is True
    assert report.trends[0].observed_order == pytest.approx(1.0, abs=0.05)


def test_transient_timestep_independence_requires_three_levels() -> None:
    with pytest.raises(IndependenceError, match="INDEPENDENCE_NEEDS_AT_LEAST_3_LEVELS"):
        run_timestep_independence(
            _timestep_levels()[:2],
            (QuantityOfInterest("peak_amplitude", "m"),),
            _two_level_executor(1.0, 1.0),
            transient=True,
        )


def test_timestep_independence_fails_on_slowly_drifting_result() -> None:
    def execute(level: RefinementLevel) -> StudyRun:
        value = {"coarse": 1.0, "medium": 1.4, "fine": 1.9}[level.name]
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash=f"hash-{level.name}",
            qoi=(("peak_amplitude", value),),
        )

    report = run_timestep_independence(
        _timestep_levels(),
        (QuantityOfInterest("peak_amplitude", "m", relative_tolerance=0.05),),
        execute,
    )
    assert report.accepted is False


def test_nonconverged_run_blocks_independence() -> None:
    def execute(level: RefinementLevel) -> StudyRun:
        return StudyRun(
            level=level.name,
            run_id=f"run-{level.name}",
            input_hash=f"hash-{level.name}",
            qoi=(("pressure_drop", 10.0),),
            valid=level.name != "fine",
            detail="solver did not converge",
        )

    report = run_mesh_independence(
        _mesh_levels(),
        (QuantityOfInterest("pressure_drop", "Pa", relative_tolerance=0.02),),
        execute,
    )
    assert report.accepted is False
    assert "nonconverged-or-invalid-runs" in report.reason


def test_independence_requires_declared_qoi() -> None:
    with pytest.raises(IndependenceError, match="INDEPENDENCE_REQUIRES_DECLARED_QOI"):
        run_mesh_independence(_mesh_levels(), (), _converging_executor())


# ---------------------------------------------------------------------------
# B. physical closure gates
# ---------------------------------------------------------------------------


def test_mass_and_energy_closure_pass_and_fail() -> None:
    passed = assess_closure(
        "mass", {"mass": 1.0}, {"mass": 1.0 + 1e-9}
    )
    assert passed.passed is True
    failed = assess_closure("mass", {"mass": 1.0}, {"mass": 1.05})
    assert failed.passed is False
    assert "mass" in failed.reason


def test_closure_missing_declared_quantity_fails_closed() -> None:
    result = assess_closure("energy", {"energy": 1.0}, {})
    assert result.passed is False
    assert result.missing == ("energy",)


def test_force_and_torque_closure_uses_separate_scales() -> None:
    # A 1e-3 N force residual and a 1e-3 N.m torque residual are assessed
    # against their own scales rather than one shared raw tolerance.
    result = assess_closure(
        "momentum",
        {"momentum": 0.0, "force": 1e-3, "torque": 1e-4},
        {"momentum": 0.0, "force": 0.0, "torque": 0.0},
    )
    assert result.passed is True
    assert {check.name for check in result.checks} == {"momentum", "force", "torque"}


def test_field_interface_conservation_detects_transfer_loss() -> None:
    conserved = assess_field_interface_conservation(
        "pressure",
        (10.0, 10.0, 10.0, 10.0, 10.0),
        (8.0, 12.0, 8.0, 12.0, 8.0),
        source_coordinates=(0.0, 0.25, 0.5, 0.75, 1.0),
        target_coordinates=(0.0, 0.25, 0.5, 0.75, 1.0),
    )
    assert conserved.passed is True
    leaky = assess_field_interface_conservation(
        "heat-flux",
        (100.0, 100.0, 100.0),
        (90.0, 90.0, 90.0),
    )
    assert leaky.passed is False
    assert leaky.relative_error == pytest.approx(0.1, abs=1e-9)


def test_resonance_margin_and_geometry_clearance_gates() -> None:
    close = assess_resonance_margin(12000.0, (11500.0, 30000.0))
    assert close.passed is False
    clear = assess_resonance_margin(20000.0, (10000.0, 30000.0))
    assert clear.passed is True
    assert assess_geometry_clearance(0.5, 0.5 - 1e-9).passed is True
    assert assess_geometry_clearance(0.5, 0.4).passed is False


# ---------------------------------------------------------------------------
# C. promotion gate
# ---------------------------------------------------------------------------


def test_deferred_required_participant_blocks_validated_final() -> None:
    result = assess_promotion(
        "candidate-a",
        (
            PromotionParticipantEvidence(
                participant_id="incompressible-steady-flow",
                required=True,
                available=False,
                deferred=True,
            ),
            PromotionParticipantEvidence(participant_id="structural-static"),
        ),
    )
    assert result.validated_final is False
    assert result.status == "incomplete-diagnostic"
    assert any(
        blocker.startswith("required-participant-deferred") for blocker in result.blockers
    )
    assert any(
        blocker.startswith("required-participant-unavailable") for blocker in result.blockers
    )


def test_closure_failure_blocks_promotion() -> None:
    result = assess_promotion(
        "candidate-b",
        (
            PromotionParticipantEvidence(
                participant_id="thermal-conduction", closure_passed=False
            ),
        ),
    )
    assert result.validated_final is False
    assert result.blockers == ("physical-closure-failed:thermal-conduction",)


def test_complete_evidence_validates_and_requires_independence_when_declared() -> None:
    complete = assess_promotion(
        "candidate-c",
        (PromotionParticipantEvidence(participant_id="structural-static"),),
        require_mesh_independence=True,
        require_timestep_independence=True,
    )
    assert complete.validated_final is False
    assert all(
        blocker.startswith(("mesh-independence-failed", "timestep-independence-failed"))
        for blocker in complete.blockers
    )
    full = assess_promotion(
        "candidate-d",
        (
            PromotionParticipantEvidence(
                participant_id="structural-static",
                mesh_independence_passed=True,
                timestep_independence_passed=True,
            ),
        ),
        require_mesh_independence=True,
        require_timestep_independence=True,
    )
    assert full.validated_final is True
    assert full.status == "validated-final"


def test_optional_participant_failure_does_not_block() -> None:
    result = assess_promotion(
        "candidate-e",
        (
            PromotionParticipantEvidence(participant_id="required-one"),
            PromotionParticipantEvidence(
                participant_id="optional-one", required=False, closure_passed=False
            ),
        ),
    )
    assert result.validated_final is True


# ---------------------------------------------------------------------------
# D. generic generative end-to-end benchmark
# ---------------------------------------------------------------------------


def _kernel_and_gmsh_available() -> bool:
    try:
        from aeroworkbench_geometry.parametric import probe_kernel
        from aeroworkbench_mesh import probe_gmsh

        return bool(probe_kernel().available and probe_gmsh().available)
    except Exception:  # noqa: BLE001
        return False


def _screening_config(**overrides: object):
    from benchmarks.independence import BenchmarkConfig

    base: dict = {"execute_cad": False, "execute_mesh": False, "execute_native": False}
    base.update(overrides)
    return BenchmarkConfig(**base)  # type: ignore[arg-type]


def test_generic_benchmark_reproducible_from_seed_and_design_hash(tmp_path: Path) -> None:
    from benchmarks.independence import run_generic_benchmark

    cfg = _screening_config(seed=7)
    first = run_generic_benchmark(tmp_path / "a", config=cfg)
    second = run_generic_benchmark(tmp_path / "b", config=cfg)
    assert first.design_hash == second.design_hash
    assert first.campaign_digest == second.campaign_digest
    assert first.reproducible is True and second.reproducible is True
    # The design space is seed independent; the sampled campaign is not.
    other = run_generic_benchmark(tmp_path / "c", config=_screening_config(seed=8))
    assert other.design_hash == first.design_hash
    assert other.campaign_digest != first.campaign_digest
    # The whole report is JSON-serializable evidence.
    json.dumps(first.as_dict(), sort_keys=True)


def test_generic_benchmark_lineage_is_complete(tmp_path: Path) -> None:
    from benchmarks.independence import run_generic_benchmark

    report = run_generic_benchmark(tmp_path, config=_screening_config())
    steps = {step.step: step for step in report.steps}
    for required in (
        "design-space",
        "candidate-generation",
        "cheap-evaluation",
        "selection-diversity",
        "fidelity-promotion",
        "mesh-time-independence",
        "final-candidate-set",
        "deferred-capability-audit",
    ):
        assert required in steps, required
    assert report.candidate_set
    hashes = {item["candidateHash"] for item in report.candidate_set}
    assert set(report.lineage) == hashes
    for item in report.candidate_set:
        assert item["designHash"] == report.design_hash
        assert item["campaignDigest"] == report.campaign_digest
        entry = report.lineage[item["candidateHash"]]
        assert entry["candidateHash"] == item["candidateHash"]
        assert entry["designHash"] == report.design_hash
        assert entry["independenceRuns"]["mesh"]
        assert entry["independenceRuns"]["timestep"]
        assert entry["evaluations"], "every candidate keeps its evaluation lineage"
    advanced = [item for item in report.promotions if item["advanced"]]
    assert advanced
    for promotion in advanced:
        entry = report.lineage[promotion["candidateHash"]]
        fidelities = {record["fidelity"] for record in entry["evaluations"]}
        assert promotion["fromFidelity"] in fidelities
        assert promotion["toFidelity"] in fidelities


def test_generic_benchmark_native_shortfall_never_validates_final(tmp_path: Path) -> None:
    from benchmarks.independence import run_generic_benchmark

    report = run_generic_benchmark(tmp_path, config=_screening_config())
    assert report.candidate_set
    assert all(item["validatedFinal"] is False for item in report.candidate_set)
    blockers = {
        blocker.split(":", 1)[0]
        for item in report.candidate_set
        for blocker in item["blockers"]
    }
    assert (
        "required-participant-deferred" in blockers
        or "required-participant-unavailable" in blockers
    )
    by_capability = {entry["capability"]: entry for entry in report.audit}
    assert by_capability["flow"]["status"] == "BLOCKED"
    assert by_capability["field-coupling"]["status"] == "BLOCKED"
    assert by_capability["scalar-coupling"]["status"] == "PASS"
    # No audit entry can claim a native PASS without an executed native receipt.
    for entry in report.audit:
        if entry["status"] == "PASS" and entry["native"]:
            assert entry["capability"] in {"geometry", "mesh"}


@pytest.mark.skipif(
    not _kernel_and_gmsh_available(), reason="CAD kernel and Gmsh are required"
)
def test_generic_benchmark_executes_real_cad_and_mesh(tmp_path: Path) -> None:
    from benchmarks.independence import run_generic_benchmark

    report = run_generic_benchmark(
        tmp_path, config=_screening_config(execute_cad=True, execute_mesh=True)
    )
    steps = {step.step: step for step in report.steps}
    assert steps["cad-regeneration"].status == "EXECUTED"
    assert steps["mesh-generation"].status == "EXECUTED"
    mesh_evidence = steps["mesh-generation"].evidence
    assert mesh_evidence["element_count"] > 0
    assert len(mesh_evidence["mesh_hash"]) == 64
    assert steps["cad-regeneration"].evidence["shape_hash"]
    by_capability = {entry["capability"]: entry for entry in report.audit}
    assert by_capability["geometry"]["status"] == "PASS"
    assert by_capability["mesh"]["status"] == "PASS"
