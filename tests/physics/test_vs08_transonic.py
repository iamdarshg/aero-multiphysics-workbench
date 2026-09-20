"""VS 08: transonic/supersonic external-aero design, shock/wave-drag fidelity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_optimization import FidelitySignals
from aeroworkbench_vehicle_systems.transonic import (
    FlowRegime,
    NativeCompressibleRequest,
    NativeCompressibleSolution,
    TransonicCapabilityUnavailable,
    TransonicContractError,
    TransonicFidelity,
    TransonicOutOfScope,
    TransonicValidityError,
    apply_correction,
    area_rule_assessment,
    assess_drag_rise,
    assess_supersonic_section,
    buffet_boundary_cl,
    classify_regime,
    compatible_derivative,
    escalation_for_mach,
    evaluate_transonic_constraints,
    heating_seam_required,
    karman_tsien,
    korn_drag_divergence,
    laitone,
    max_thickness_ratio,
    normal_shock_ratios,
    plan_compressible_fidelity,
    prandtl_glauert,
    prepare_compressible_case,
    probe_compressible_capability,
    promotion_for,
    required_sweep_deg,
    sears_haack_wave_drag,
    solve_native_compressible,
    tip_section_guidance,
    transonic_design_constraints,
    wave_drag_rise,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "vehicle_systems" / "transonic"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_fixtures_load() -> None:
    wing = load_fixture("transonic_wing.json")
    body = load_fixture("supersonic_body.json")
    assert wing["caseId"] == "vs08-transonic-wing"
    assert body["caseId"] == "vs08-supersonic-body"


def test_regime_classification() -> None:
    assert classify_regime(0.1) is FlowRegime.INCOMPRESSIBLE
    assert classify_regime(0.5) is FlowRegime.SUBSONIC
    assert classify_regime(0.9) is FlowRegime.TRANSONIC
    assert classify_regime(1.6) is FlowRegime.SUPERSONIC
    assert classify_regime(5.0) is FlowRegime.HYPERSONIC
    with pytest.raises(TransonicContractError):
        classify_regime(-0.1)


def test_hypersonic_out_of_scope() -> None:
    with pytest.raises(TransonicOutOfScope):
        apply_correction(-0.5, 5.5)
    with pytest.raises(TransonicOutOfScope):
        normal_shock_ratios(6.0)
    with pytest.raises(TransonicOutOfScope):
        escalation_for_mach(5.2)


def test_low_mach_no_correction() -> None:
    result = apply_correction(-0.5, 0.2)
    assert result.method == "none"
    assert result.cp_corrected == pytest.approx(-0.5)
    assert result.correction_factor == pytest.approx(1.0)


def test_correction_bands_fail_closed() -> None:
    assert prandtl_glauert(-0.5, 0.6) == pytest.approx(-0.5 / (1.0 - 0.36) ** 0.5)
    assert karman_tsien(-0.5, 0.6) < prandtl_glauert(-0.5, 0.6)
    assert laitone(-0.5, 0.8) < 0.0
    with pytest.raises(TransonicValidityError):
        prandtl_glauert(-0.5, 0.75)
    with pytest.raises(TransonicValidityError):
        karman_tsien(-0.5, 0.85)
    with pytest.raises(TransonicValidityError):
        laitone(-0.5, 0.9)
    with pytest.raises(TransonicContractError):
        apply_correction(-0.5, 0.5, "unknown-method")


def test_korn_divergence_fixture() -> None:
    wing = load_fixture("transonic_wing.json")
    m_dd = korn_drag_divergence(
        wing["thicknessRatio"], wing["liftCoefficient"], wing["sweepDeg"], wing["kappa"]
    )
    assert m_dd == pytest.approx(0.7999, rel=1e-3)
    assert wave_drag_rise(wing["mach"], m_dd) == pytest.approx(0.0)
    assert wave_drag_rise(0.85, m_dd) == pytest.approx(5.0 * (0.85 - m_dd) ** 2)
    with pytest.raises(TransonicValidityError):
        wave_drag_rise(1.05, m_dd)


def test_drag_rise_escalates_near_divergence() -> None:
    clean = assess_drag_rise(0.70, 0.10, 0.45, 25.0)
    assert clean.shock_sensitive is False
    assert clean.requires_native is False
    assert clean.delta_cd_wave == pytest.approx(0.0)
    hot = assess_drag_rise(0.81, 0.10, 0.45, 25.0)
    assert hot.shock_sensitive is True
    assert hot.requires_native is True
    assert hot.delta_cd_wave > 0.0
    assert len(hot.input_hash) == 64
    assert hot.content_hash == assess_drag_rise(0.81, 0.10, 0.45, 25.0).content_hash


def test_escalation_policy() -> None:
    assert escalation_for_mach(0.2).required_fidelity == "incompressible"
    assert escalation_for_mach(0.5).required_fidelity == "corrected"
    assert escalation_for_mach(0.9).required_fidelity == "transonic_screening"
    assert escalation_for_mach(1.6).required_fidelity == "supersonic_screening"
    near = escalation_for_mach(0.79, divergence_mach=0.7999)
    assert near.required_fidelity == "rans_cfd"
    assert near.needs_native is True
    flagged = escalation_for_mach(0.5, shock_sensitive=True)
    assert flagged.required_fidelity == "rans_cfd"


def test_area_rule_fixture_passes_and_kink_fails() -> None:
    wing = load_fixture("transonic_wing.json")
    stations = tuple((float(x), float(a)) for x, a in wing["stations"])
    good = area_rule_assessment(stations)
    assert good.passes is True
    assert good.delta_cd_penalty >= 0.0
    kinked = ((0.0, 1.0), (1.0, 1.0), (2.0, 3.0), (3.0, 1.0), (4.0, 1.0))
    bad = area_rule_assessment(kinked)
    assert bad.passes is False
    with pytest.raises(TransonicContractError):
        area_rule_assessment(((0.0, 1.0), (1.0, 1.0)))


def test_sears_haack_body_fixture() -> None:
    body = load_fixture("supersonic_body.json")
    result = sears_haack_wave_drag(
        body["volumeM3"],
        body["lengthM"],
        body["maxCrossSectionM2"],
        body["referenceAreaM2"],
        body["mach"],
    )
    assert result.drag_over_q_m2 == pytest.approx(128.0 * 14.0**2 / (3.141592653589793 * 20.0**4))
    assert result.cd_wave == pytest.approx(result.drag_over_q_m2 / 8.0)
    assert result.fineness_ratio >= 5.0
    with pytest.raises(TransonicValidityError):
        sears_haack_wave_drag(14.0, 2.0, 8.0, 8.0, 1.6)
    with pytest.raises(TransonicValidityError):
        sears_haack_wave_drag(14.0, 20.0, 1.2, 8.0, 0.9)


def test_supersonic_section_and_shock() -> None:
    body = load_fixture("supersonic_body.json")
    assessment = assess_supersonic_section(body["alphaDeg"], body["thicknessRatio"], body["mach"])
    assert assessment.lift_coefficient == pytest.approx(0.1118, rel=1e-3)
    assert assessment.cd_wave == pytest.approx(0.01543, rel=1e-3)
    shock = normal_shock_ratios(1.6)
    assert shock["downstreamMach"] == pytest.approx(0.6684, rel=1e-3)
    assert shock["staticPressureRatio"] == pytest.approx(2.82, rel=1e-3)
    assert shock["totalPressureRatio"] == pytest.approx(0.8952, rel=1e-3)
    with pytest.raises(TransonicValidityError):
        normal_shock_ratios(0.9)
    with pytest.raises(TransonicContractError):
        assess_supersonic_section(20.0, 0.06, 1.6)


def test_design_guidance_round_trip() -> None:
    sweep = required_sweep_deg(0.85, 0.10, 0.45)
    assert sweep == pytest.approx(31.5, rel=1e-2)
    assert required_sweep_deg(0.70, 0.10, 0.45) == pytest.approx(0.0)
    thick = max_thickness_ratio(0.80, 0.45, 25.0)
    assert thick == pytest.approx(0.10, rel=1e-2)
    with pytest.raises(TransonicValidityError):
        required_sweep_deg(1.6, 0.10, 0.45)
    boundary = buffet_boundary_cl(0.76, 0.10, 25.0)
    assert boundary == pytest.approx(0.582, rel=1e-2)
    guidance = tip_section_guidance(0.70, 0.76, 0.10, 25.0)
    assert guidance.washout_recommended is True
    assert guidance.margin == pytest.approx(boundary - 0.70)
    calm = tip_section_guidance(0.30, 0.76, 0.10, 25.0)
    assert calm.washout_recommended is False


def test_derivative_compatibility_fail_closed() -> None:
    assert compatible_derivative(5.0, 0.5, 0.80) == pytest.approx(5.0 / (1.0 - 0.25) ** 0.5)
    with pytest.raises(TransonicValidityError):
        compatible_derivative(5.0, 0.79, 0.7999)


def test_constraints_participate_in_optimization() -> None:
    constraints = transonic_design_constraints()
    assert {item.name for item in constraints} == {"divergence-margin", "wave-drag-rise"}
    evaluations = evaluate_transonic_constraints(0.76, 0.7999, 0.0)
    assert all(item.satisfied for item in evaluations)
    violated = evaluate_transonic_constraints(0.85, 0.7999, 0.005)
    assert not all(item.satisfied for item in violated)


def test_promotion_and_heating_seam() -> None:
    calm = promotion_for(0.5, False)
    assert calm.needs_native is False
    assert calm.thermal_coupling_required is False
    hot = promotion_for(0.79, True, 0.7999)
    assert hot.needs_native is True
    assert "ADV-PHYS 14" in hot.mesh_requirement
    assert "ADV-PHYS 12" in hot.turbulence_requirement
    assert heating_seam_required(3.2) is True
    assert heating_seam_required(2.0) is False
    warm = promotion_for(3.2, False)
    assert warm.thermal_coupling_required is True


def test_fidelity_ladder_plans() -> None:
    signals = FidelitySignals(
        question="transonic drag",
        maturity=0.4,
        constraint_margin=0.5,
        disagreement=0.0,
        sensitivity=0.0,
        convergence_difficulty=0.0,
        mesh_dependence=0.0,
        timestep_dependence=0.0,
        resonance_proximity=1.0,
        validity_ok={"corrected": False, "transonic_screening": True},
        cost_budget=5.0,
    )
    plan = plan_compressible_fidelity("corrected", signals)
    assert plan.level == "transonic_screening"
    assert plan.escalate is True


def test_native_fails_closed_without_backend(tmp_path: Path) -> None:
    request = NativeCompressibleRequest(
        case_id="vs08-transonic-wing",
        mach=0.79,
        geometry_digest="abc123",
        shock_sensitive=True,
        mesh_shock_refined=True,
        turbulence_model="k-omega-sst",
        thermal_coupling=False,
    )
    with pytest.raises(TransonicCapabilityUnavailable):
        solve_native_compressible(request, backend=None, run_id="run-1")
    assert probe_compressible_capability("definitely-not-installed-xyz").available is False
    manifest = prepare_compressible_case(request, tmp_path)
    assert json.loads(manifest.read_text(encoding="utf-8"))["caseId"] == "vs08-transonic-wing"


def test_native_requires_mesh_and_model() -> None:
    class StubBackend:
        solver_name = "stub-cfd"
        solver_version = "0.0-test"

        def solve(self, request: NativeCompressibleRequest) -> NativeCompressibleSolution:
            return NativeCompressibleSolution(0.5, 0.001, "weak shock", ("log.txt",))

    backend = StubBackend()
    no_mesh = NativeCompressibleRequest(
        case_id="c", mach=0.79, geometry_digest="g", shock_sensitive=True,
        mesh_shock_refined=False, turbulence_model="k-omega-sst", thermal_coupling=False,
    )
    with pytest.raises(TransonicValidityError):
        solve_native_compressible(no_mesh, backend=backend, run_id="run-1")
    no_model = NativeCompressibleRequest(
        case_id="c", mach=0.79, geometry_digest="g", shock_sensitive=True,
        mesh_shock_refined=True, turbulence_model=None, thermal_coupling=False,
    )
    with pytest.raises(TransonicValidityError):
        solve_native_compressible(no_model, backend=backend, run_id="run-1")
    hot = NativeCompressibleRequest(
        case_id="c", mach=3.2, geometry_digest="g", shock_sensitive=False,
        mesh_shock_refined=True, turbulence_model="k-omega-sst", thermal_coupling=False,
    )
    with pytest.raises(TransonicValidityError):
        solve_native_compressible(hot, backend=backend, run_id="run-1")
    calm = NativeCompressibleRequest(
        case_id="c", mach=0.5, geometry_digest="g", shock_sensitive=False,
        mesh_shock_refined=False, turbulence_model=None, thermal_coupling=False,
    )
    receipt = solve_native_compressible(calm, backend=backend, run_id="run-1")
    assert receipt.solver_name == "stub-cfd"
    assert receipt.envelope.source is ResultSource.NATIVE_SOLVER
    assert receipt.envelope.fidelity is TransonicFidelity.NATIVE
    assert len(receipt.input_hash) == 64


def test_envelope_carries_contract() -> None:
    result = apply_correction(-0.5, 0.6, "prandtl-glauert")
    envelope = result.envelope
    assert envelope.source is ResultSource.ANALYTICAL
    assert envelope.units
    assert envelope.validity.passed is True
    assert envelope.software.name.startswith("aeroworkbench-vehicle-systems")
    assert envelope.provenance.inputs_hash == envelope.inputs_hash
    assert result.content_hash == apply_correction(-0.5, 0.6, "prandtl-glauert").content_hash
