"""VS 04: high-lift, nonlinear stall and post-stall aerodynamic fidelity.

Tiny deterministic fixtures: a simple airfoil section, flap/slat deployables
with a clean/takeoff/landing schedule, and approach/stall conditions. Native
unsteady/RANS requests fail closed; promotion is a ticket, never a result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aeroworkbench_optimization import FidelitySignals
from aeroworkbench_vehicle_systems.highlift import (
    AuthoritySurface,
    CapabilityUnavailable,
    DynamicStallRequest,
    DynamicStallSolution,
    HighLiftError,
    ValidityError,
    assess_deep_stall,
    check_control_authority,
    check_stall_constraint,
    clean_configuration,
    escalation_for_margin,
    evaluate_finite_wing,
    evaluate_section,
    evaluate_stall_margin,
    landing_configuration,
    linear_vlm_lift,
    native_highlift_status,
    plan_highlift_fidelity,
    promote_to_rans,
    require_native_highlift,
    section_polar_table,
    simple_airfoil_section,
    small_wing_planform,
    solve_dynamic_stall,
    solve_highlift_aero,
    takeoff_configuration,
    validity_signals_for_ladder,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "vehicle_systems" / "highlift"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _conditions() -> dict[str, object]:
    return _load("approach_conditions.json")


class _StubUnsteadyBackend:
    solver_name = "stub-unsteady"
    solver_version = "0.0.0"

    def solve(self, request: DynamicStallRequest) -> DynamicStallSolution:
        return DynamicStallSolution(
            lift_mean=1.0,
            lift_loop_width=0.1,
            moment_undershoot=-0.02,
            detail=f"stub solve of {request.request_id}",
        )


def test_fixture_files_match_canonical_fixtures() -> None:
    raw = _load("simple_airfoil.json")
    params = simple_airfoil_section()
    assert raw["section_id"] == params.section_id
    assert raw["cl_max"] == params.cl_max
    assert raw["alpha_stall_deg"] == params.alpha_stall_deg
    sched = _load("schedule_fixture.json")
    assert sched["schedule_id"] == "vs04-canonical-schedule"
    assert sched["schedules"]["landing"]["flap"] == 35.0


def test_configuration_changes_lift_drag_moment_with_provenance() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    alpha = 8.0
    clean = evaluate_finite_wing(alpha, params, planform, clean_configuration().delta())
    takeoff = evaluate_finite_wing(alpha, params, planform, takeoff_configuration().delta())
    landing = evaluate_finite_wing(alpha, params, planform, landing_configuration().delta())
    assert takeoff.lift > clean.lift
    assert landing.lift > takeoff.lift
    assert landing.drag > takeoff.drag > clean.drag
    assert landing.moment < clean.moment
    assert landing.cl_max_wing > clean.cl_max_wing
    for wing in (clean, takeoff, landing):
        assert len(wing.meta.input_hash) == 64
        assert wing.meta.software.name == "aeroworkbench-vehicle-systems-highlift"
        assert wing.meta.unit_map()["angle"] == "deg"
    assert takeoff.meta.input_hash != clean.meta.input_hash
    assert landing.meta.input_hash != takeoff.meta.input_hash


def test_results_deterministic_and_hashable() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    first = solve_highlift_aero(takeoff_configuration(), params, planform, 8.0)
    second = solve_highlift_aero(takeoff_configuration(), params, planform, 8.0)
    assert first.canonical() == second.canonical()
    assert hash(first.meta.input_hash) == hash(second.meta.input_hash)
    assert first.meta.provenance.inputs_hash == second.meta.provenance.inputs_hash


def test_nonlinear_branch_stall_onset_clmax_poststall() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    delta = clean_configuration().delta()
    attached = evaluate_finite_wing(6.0, params, planform, delta)
    assert attached.regime == "attached"
    assert not attached.separated
    assert attached.meta.validity.passed
    stalled = evaluate_finite_wing(16.0, params, planform, delta)
    assert stalled.regime == "stalled"
    assert stalled.separated
    assert not stalled.meta.validity.passed
    post = evaluate_finite_wing(22.0, params, planform, delta)
    assert post.regime == "poststall"
    assert post.lift < stalled.lift
    assert post.drag > stalled.drag
    deep = evaluate_finite_wing(27.0, params, planform, delta)
    assert deep.regime == "deepstall"
    table = section_polar_table(params, (0.0, 8.0, 14.0, 20.0), delta)
    assert [point.regime for point in table] == ["attached", "attached", "stalled", "poststall"]


def test_stall_constraint_rejects_linear_vlm_pass() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    wing = evaluate_finite_wing(16.0, params, planform, clean_configuration().delta())
    linear_cl = linear_vlm_lift(16.0, params, planform)
    assert linear_cl > wing.cl_max_wing
    verdict = check_stall_constraint(linear_cl, wing)
    assert not verdict.passed
    assert any("STALL" in reason for reason in verdict.reasons)
    assert not verdict.meta.validity.passed
    with pytest.raises(ValidityError):
        from aeroworkbench_vehicle_systems.highlift import require_nonlinear_guard

        require_nonlinear_guard(16.0, linear_cl, params, planform)


def test_stall_constraint_passes_approach() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    required = float(_conditions()["required_cl_approach"])
    wing = evaluate_finite_wing(8.0, params, planform, landing_configuration().delta())
    verdict = check_stall_constraint(required, wing)
    assert verdict.passed
    assert verdict.margin > 0.0


def test_stall_warning_margin_levels() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    delta = landing_configuration().delta()
    cruise = evaluate_stall_margin(evaluate_finite_wing(6.0, params, planform, delta))
    assert cruise.level == "none"
    assert not cruise.stick_shaker
    near = evaluate_stall_margin(evaluate_finite_wing(12.0, params, planform, delta))
    assert near.level in ("advisory", "caution")
    warn = evaluate_stall_margin(evaluate_finite_wing(16.0, params, planform, delta))
    assert warn.level in ("warning", "stall", "caution")
    assert warn.alpha_margin_deg < cruise.alpha_margin_deg
    assert warn.cl_margin < cruise.cl_margin


def test_control_authority_at_approach_and_stall() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    cond = _conditions()
    approach = cond["approach"]
    assert isinstance(approach, dict)
    ctrl = cond["control"]
    assert isinstance(ctrl, dict)
    wing = evaluate_finite_wing(
        8.0, params, planform, landing_configuration().delta()
    )
    held = check_control_authority(
        wing,
        (
            AuthoritySurface(
                surface_id=str(ctrl["surface_id"]) if "surface_id" in ctrl else "elevator",
                axis="pitch",
                moment_per_rad_n_m=float(ctrl["moment_per_rad_n_m"]),
                deflection_limit_deg=float(ctrl["deflection_limit_deg"]),
                required_moment_n_m=-40.0,
            ),
        ),
        condition="approach",
        dynamic_pressure_pa=float(approach["dynamic_pressure_pa"]),
        area_m2=2.0,
        chord_m=0.3,
    )
    assert held.passed
    blown = check_control_authority(
        wing,
        (
            AuthoritySurface(
                surface_id="elevator",
                axis="pitch",
                moment_per_rad_n_m=-320.0,
                deflection_limit_deg=25.0,
                required_moment_n_m=-5000.0,
            ),
        ),
        condition="approach",
        dynamic_pressure_pa=1800.0,
        area_m2=2.0,
        chord_m=0.3,
    )
    assert not blown.passed
    assert any("CONTROL_AUTHORITY_EXCEEDED" in reason for reason in blown.reasons)
    stalled_wing = evaluate_finite_wing(
        22.0, params, planform, landing_configuration().delta()
    )
    flagged = check_control_authority(
        stalled_wing,
        (
            AuthoritySurface(
                surface_id="elevator",
                axis="pitch",
                moment_per_rad_n_m=-320.0,
                deflection_limit_deg=25.0,
                required_moment_n_m=-40.0,
            ),
        ),
        condition="stall-entry",
        dynamic_pressure_pa=1500.0,
        area_m2=2.0,
        chord_m=0.3,
    )
    assert not flagged.passed
    assert any("POST_STALL" in reason for reason in flagged.reasons)


def test_dynamic_stall_fails_closed_without_backend() -> None:
    request = DynamicStallRequest(
        request_id="stub-case", mean_alpha_deg=12.0, amplitude_deg=5.0,
        reduced_frequency=0.1,
    )
    with pytest.raises(CapabilityUnavailable):
        solve_dynamic_stall(request, backend=None, run_id="run-1")
    with pytest.raises(CapabilityUnavailable):
        solve_highlift_aero(
            takeoff_configuration(),
            simple_airfoil_section(),
            small_wing_planform(),
            12.0,
            fidelity="unsteady",
            unsteady_request=request,
            run_id="run-1",
        )


def test_dynamic_stall_stub_backend_carries_native_provenance() -> None:
    request = DynamicStallRequest(
        request_id="stub-case", mean_alpha_deg=12.0, amplitude_deg=5.0,
        reduced_frequency=0.1,
    )
    result = solve_dynamic_stall(
        request, backend=_StubUnsteadyBackend(), run_id="run-1"
    )
    assert result.meta.source.value == "native_solver"
    assert result.meta.provenance.solver_name == "stub-unsteady"
    assert result.meta.provenance.run_id == "run-1"
    assert not result.quasi_steady_valid


def test_near_stall_triggers_fidelity_escalation() -> None:
    params = simple_airfoil_section()
    planform = small_wing_planform()
    delta = clean_configuration().delta()
    calm = evaluate_stall_margin(evaluate_finite_wing(6.0, params, planform, delta))
    escalate, _ = escalation_for_margin(calm)
    assert not escalate
    hot = evaluate_stall_margin(evaluate_finite_wing(13.0, params, planform, delta))
    escalate_hot, _ = escalation_for_margin(hot)
    assert escalate_hot
    signals = validity_signals_for_ladder(
        evaluate_finite_wing(13.0, params, planform, delta)
    )
    plan = plan_highlift_fidelity(
        "attached_linear",
        FidelitySignals(
            question="approach stall margin",
            maturity=0.8,
            constraint_margin=0.05,
            disagreement=0.0,
            sensitivity=0.0,
            convergence_difficulty=0.0,
            mesh_dependence=0.0,
            timestep_dependence=0.0,
            resonance_proximity=1.0,
            validity_ok=signals,
            cost_budget=1.0,
        ),
    )
    assert plan.escalate
    assert plan.level != "attached_linear"


def test_validity_envelope_fails_closed() -> None:
    params = simple_airfoil_section()
    with pytest.raises(ValidityError):
        evaluate_section(40.0, params)
    with pytest.raises(HighLiftError):
        solve_highlift_aero(
            clean_configuration(), params, small_wing_planform(), 8.0,
            fidelity="full_field",
        )


def test_rans_promotion_ticket_or_fail_closed() -> None:
    wing = evaluate_finite_wing(
        13.0, simple_airfoil_section(), small_wing_planform(),
        takeoff_configuration().delta(),
    )
    with pytest.raises(CapabilityUnavailable):
        promote_to_rans(wing, takeoff_configuration().digest)
    ticket = promote_to_rans(
        wing, takeoff_configuration().digest, backend="openfoam", run_id="run-9"
    )
    assert ticket.mesh_requirement == "meshing-rans-promotion"
    assert ticket.backend == "openfoam"
    assert ticket.meta.provenance.inputs_hash
    assert not native_highlift_status().available
    with pytest.raises(CapabilityUnavailable):
        require_native_highlift()


def test_deep_stall_undeclared_tail_never_claims_safe() -> None:
    wing = evaluate_finite_wing(
        27.0, simple_airfoil_section(), small_wing_planform(),
        clean_configuration().delta(),
    )
    unknown = assess_deep_stall(wing, deep_stall_alpha_deg=None, tail_declared=False)
    assert not unknown.assessed
    assert unknown.blanketing_risk == "unknown"
    declared = assess_deep_stall(
        wing, deep_stall_alpha_deg=26.0, tail_declared=True, tail_arm_m=2.5
    )
    assert declared.assessed
    assert declared.blanketing_risk == "high"
    assert not declared.meta.validity.passed
