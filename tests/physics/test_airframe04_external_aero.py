"""AIRFRAME 04: external-aerodynamics fidelity ladder.

Analytical screening, lifting-line/VLM and the governed VSPAERO native path
share the typed aero-coefficient contract trim consumes. Fixtures under
``tests/airframe/external_aero`` are tiny deterministic wing definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe.aero_geometry import (
    AirfoilProfile,
    ControlSurface,
    LiftingSurface,
    Planform,
)
from aeroworkbench_airframe.external_aero import (
    AeroCoefficients,
    AeroReference,
    ExternalAeroCapabilityUnavailableError,
    ExternalAeroCase,
    ExternalAeroFidelity,
    ExternalAeroValidationError,
    ExternalAeroValidityError,
    VlmOptions,
    evaluate_aero_validity,
    evaluate_analytic,
    finite_wing_lift_curve_slope,
    oswald_efficiency,
    plan_external_aero_fidelity,
    polar_from_points,
    prepare_vspaero_case,
    probe_any_vspaero_capability,
    probe_vspaero_capability,
    reference_from_altitude,
    reference_from_conditions,
    require_vspaero_capability,
    section_model_for_profile,
    solve_external_aero,
    solve_vlm,
    solve_vspaero,
    study_vlm_convergence,
    with_vlm_convergence,
)
from aeroworkbench_airframe.external_aero.analytic import DragComponent
from aeroworkbench_airframe.external_aero.contracts import (
    ANALYTICAL_VALIDITY_LIMITS,
    VLM_VALIDITY_LIMITS,
)
from aeroworkbench_airframe.external_aero.native import (
    VspaeroSolution,
    vspaero_case_manifest,
)
from aeroworkbench_core.types import ResultSource
from aeroworkbench_optimization import FidelitySignals

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "airframe" / "external_aero"
_TINY_VLM = VlmOptions(panels_per_surface=8)


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def profile_from_payload(payload: dict[str, Any]) -> AirfoilProfile:
    return AirfoilProfile(
        family=payload.get("family", "parametric"),
        thickness_ratio=float(payload.get("thicknessRatio", 0.12)),
        camber_ratio=float(payload.get("camberRatio", 0.0)),
        camber_position=float(payload.get("camberPosition", 0.4)),
        thickness_family=payload.get("thicknessFamily", "naca4"),
        camber_family=payload.get("camberFamily", "circular_arc"),
        cst_upper=tuple(float(value) for value in payload.get("cstUpper", ())),
        cst_lower=tuple(float(value) for value in payload.get("cstLower", ())),
    )


def case_from_payload(payload: dict[str, Any]) -> ExternalAeroCase:
    surfaces = []
    for item in payload["surfaces"]:
        planform_payload = item["planform"]
        planform = Planform(
            span_mm=float(planform_payload["spanMm"]),
            root_chord_mm=float(planform_payload["rootChordMm"]),
            tip_chord_mm=float(planform_payload["tipChordMm"]),
            sweep_deg=float(planform_payload.get("sweepDeg", 0.0)),
            dihedral_deg=float(planform_payload.get("dihedralDeg", 0.0)),
            twist_root_deg=float(planform_payload.get("twistRootDeg", 0.0)),
            twist_tip_deg=float(planform_payload.get("twistTipDeg", 0.0)),
        )
        surfaces.append(
            LiftingSurface.from_planform(
                item["surfaceId"],
                item["role"],
                planform,
                profile_from_payload(item["profile"]),
                frame=item.get("frame", "surface-local"),
                n_stations=int(item.get("nStations", 3)),
            )
        )
    controls = [
        ControlSurface(
            item["controlId"],
            item["parentId"],
            item["kind"],
            float(item["hingeFraction"]),
            (float(item["spanFraction"][0]), float(item["spanFraction"][1])),
            deflection_deg=float(item.get("deflectionDeg", 0.0)),
        )
        for item in payload.get("controls", ())
    ]
    return ExternalAeroCase(
        case_id=payload["caseId"],
        surfaces=tuple(surfaces),
        controls=tuple(controls),
        symmetry=payload.get("symmetry", "mirror"),
    )


def reference_from_payload(payload: dict[str, Any], case: ExternalAeroCase) -> AeroReference:
    conditions = payload["reference"]
    return reference_from_conditions(
        case.geometry_reference(),
        density_kg_m3=float(conditions["densityKgM3"]),
        velocity_m_s=float(conditions["velocityMS"]),
        speed_of_sound_m_s=float(conditions["speedOfSoundMS"]),
        viscosity_pa_s=float(conditions["viscosityPaS"]),
        altitude_m=conditions.get("altitudeM"),
        atmosphere_model=conditions.get("atmosphereModel", "declared"),
    )


def rectangular_case() -> tuple[ExternalAeroCase, AeroReference, dict[str, Any]]:
    payload = load_fixture("rectangular_wing.json")
    case = case_from_payload(payload)
    return case, reference_from_payload(payload, case), payload


def wing_tail_case() -> tuple[ExternalAeroCase, AeroReference, dict[str, Any]]:
    payload = load_fixture("wing_tail.json")
    case = case_from_payload(payload)
    return case, reference_from_payload(payload, case), payload


def test_airframe04_geometry_reference_is_derived_and_deterministic() -> None:
    case, _, _ = rectangular_case()
    reference = case.geometry_reference()
    assert reference.area_m2 == pytest.approx(6.0)
    assert reference.span_m == pytest.approx(6.0)
    assert reference.mean_chord_m == pytest.approx(1.0)
    assert case.digest == case_from_payload(load_fixture("rectangular_wing.json")).digest


def test_airframe04_symmetric_zero_alpha_has_near_zero_lift_and_moment() -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=0.0)
    result = solve_vlm(case, level, _TINY_VLM)
    assert abs(result.coefficients.lift) < 1e-9
    assert abs(result.coefficients.pitch) < 1e-9
    assert abs(result.coefficients.side) < 1e-9
    assert abs(result.coefficients.roll) < 1e-9
    assert abs(result.coefficients.yaw) < 1e-9
    analytic = evaluate_analytic(case, level)
    assert analytic.coefficients.lift == pytest.approx(0.0)
    assert analytic.coefficients.pitch == pytest.approx(0.0)


def test_airframe04_simple_wing_matches_lifting_line_trends() -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=4.0)
    result = solve_vlm(case, level, _TINY_VLM)
    assert result.validity.passed
    assert result.coefficients.lift > 0.0
    assert result.coefficients.drag > 0.0
    geometry = case.geometry_reference()
    aspect_ratio = geometry.span_m**2 / geometry.area_m2
    assert aspect_ratio == pytest.approx(6.0)
    efficiency = oswald_efficiency(aspect_ratio)
    expected_slope = finite_wing_lift_curve_slope(6.283185307179586, aspect_ratio, efficiency)
    measured_slope = result.derivatives.require("dCL/dalpha") * 57.29577951308232
    assert measured_slope == pytest.approx(expected_slope, rel=0.15)
    expected_induced = (
        result.coefficients.lift**2 / (3.141592653589793 * aspect_ratio * efficiency)
    )
    assert result.coefficients.drag == pytest.approx(expected_induced, rel=0.30)
    root = min(result.distributed_loads, key=lambda load: load.span_fraction)
    tip = max(result.distributed_loads, key=lambda load: load.span_fraction)
    assert root.section_lift_coefficient > tip.section_lift_coefficient
    assert abs(result.coefficients.pitch) < 0.02


def test_airframe04_analytic_drag_buildup_and_validity() -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=4.0)
    components = (
        DragComponent(name="wing", wetted_area_m2=12.0, form_factor=1.2),
        DragComponent(name="fuselage", wetted_area_m2=2.0, form_factor=1.1),
    )
    result = evaluate_analytic(case, level, drag_components=components)
    assert result.validity.passed
    assert result.coefficients.drag > 0.0
    assert result.derivatives.require("dCL/dalpha") > 0.0
    assert result.distributed_loads == ()
    assert result.provenance.source is ResultSource.ANALYTICAL
    stalled = evaluate_analytic(case, reference.with_state(alpha_deg=30.0))
    assert not stalled.validity.passed
    assert "alpha_in_range" in stalled.validity.check_dict()
    assert not stalled.validity.check_dict()["alpha_in_range"]
    with pytest.raises(ExternalAeroValidationError):
        DragComponent(name="bad", wetted_area_m2=-1.0, form_factor=1.0)


def test_airframe04_alpha_sweep_is_monotone_and_deterministic() -> None:
    case, reference, payload = rectangular_case()
    lifts = []
    for alpha in payload["alphaSweepDeg"]:
        result = solve_vlm(case, reference.with_state(alpha_deg=float(alpha)), _TINY_VLM)
        lifts.append(result.coefficients.lift)
    assert all(later > earlier for earlier, later in zip(lifts, lifts[1:], strict=False))
    first = solve_vlm(case, reference.with_state(alpha_deg=4.0), _TINY_VLM)
    second = solve_vlm(case, reference.with_state(alpha_deg=4.0), _TINY_VLM)
    assert first.content_hash == second.content_hash
    assert first.canonical() == second.canonical()


def test_airframe04_result_contract_is_hashable_and_trim_ready() -> None:
    case, reference, _ = rectangular_case()
    result = solve_vlm(case, reference.with_state(alpha_deg=4.0), _TINY_VLM)
    assert result.fidelity is ExternalAeroFidelity.VLM
    assert result.source is ResultSource.ANALYTICAL
    assert result.solver_name is None
    canonical = result.canonical()
    assert set(canonical["coefficients"]) == {"CL", "CD", "CY", "Cl", "Cm", "Cn"}
    assert canonical["derivatives"]["values"]["dCL/dalpha"] > 0.0
    assert len(result.content_hash) == 64
    assert result.provenance.inputs_hash
    assert result.reference.mach_number == pytest.approx(60.0 / 340.0)
    assert result.reference.reynolds_number == pytest.approx(1.225 * 60.0 * 1.0 / 1.81e-5)


def test_airframe04_wing_tail_vlm_reports_control_derivatives() -> None:
    case, reference, _ = wing_tail_case()
    level = reference.with_state(alpha_deg=0.0)
    result = solve_vlm(case, level, _TINY_VLM)
    assert result.validity.passed
    assert result.derivatives.get("dCL/ddelta:elevator") is not None
    assert result.derivatives.get("dCm/ddelta:elevator") is not None
    assert result.derivatives.get("dCL/ddelta:aileron") is not None
    assert abs(result.derivatives.require("dCm/ddelta:elevator")) > 0.0
    deflected = solve_vlm(case, level, _TINY_VLM, deflections=(("elevator", 5.0),))
    assert deflected.coefficients.lift != pytest.approx(result.coefficients.lift)
    assert deflected.coefficients.pitch != pytest.approx(result.coefficients.pitch)


def test_airframe04_vlm_convergence_signal_attaches_to_result() -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=4.0)
    record = study_vlm_convergence(case, level, panel_ladder=(4, 8))
    assert record.levels == ("panels-4", "panels-8")
    assert set(record.quantity_names) == {"CL", "CD", "Cm"}
    result = with_vlm_convergence(solve_vlm(case, level, _TINY_VLM), case, level,
                                  panel_ladder=(4, 8))
    assert result.convergence is not None
    assert result.convergence.levels == ("panels-4", "panels-8")


def test_airframe04_vspaero_fails_closed_without_executable() -> None:
    case, reference, _ = rectangular_case()
    assert probe_vspaero_capability("vspaero-definitely-missing").available is False
    assert probe_any_vspaero_capability() is not None
    with pytest.raises(ExternalAeroCapabilityUnavailableError):
        require_vspaero_capability("vspaero-definitely-missing")
    with pytest.raises(ExternalAeroCapabilityUnavailableError):
        solve_vspaero(case, reference)
    with pytest.raises(ExternalAeroCapabilityUnavailableError):
        solve_external_aero(case, reference, fidelity="vspaero")
    with pytest.raises(ExternalAeroCapabilityUnavailableError):
        solve_external_aero(case, reference, fidelity="full_field")
    with pytest.raises(ExternalAeroValidationError):
        solve_external_aero(case, reference, fidelity="not-a-fidelity")


def test_airframe04_native_envelope_carries_solver_identity() -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=4.0)

    class _StubVspaero:
        solver_name = "vspaero-test-stub"
        solver_version = "7.0-test"

        def solve(self, _case: ExternalAeroCase, _ref: AeroReference) -> VspaeroSolution:
            return VspaeroSolution(
                coefficients=AeroCoefficients(
                    lift=0.42, drag=0.025, side=0.0, roll=0.0, pitch=-0.05, yaw=0.0
                ),
                artifacts=("polar.dat", "history.csv"),
                detail="stub native run for envelope validation",
            )

    result = solve_vspaero(case, level, backend=_StubVspaero(), run_id="run-001")
    assert result.source is ResultSource.NATIVE_SOLVER
    assert result.fidelity is ExternalAeroFidelity.VSPAERO
    assert result.solver_name == "vspaero-test-stub"
    assert result.solver_version == "7.0-test"
    assert result.run_id == "run-001"
    assert result.artifacts == ("polar.dat", "history.csv")
    assert result.validity.passed
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    with pytest.raises(ExternalAeroValidationError):
        solve_vspaero(case, level, backend=_StubVspaero(), run_id="")


def test_airframe04_ladder_dispatch_and_planning() -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=4.0)
    analytic = solve_external_aero(case, level, fidelity="analytical")
    assert analytic.fidelity is ExternalAeroFidelity.ANALYTICAL
    lifting_line = solve_external_aero(case, level, fidelity="lifting_line")
    assert lifting_line.fidelity is ExternalAeroFidelity.LIFTING_LINE
    assert lifting_line.result_id.endswith("-lifting-line")
    vlm = solve_external_aero(case, level, fidelity="vlm")
    assert vlm.fidelity is ExternalAeroFidelity.VLM
    assert lifting_line.coefficients.lift == pytest.approx(vlm.coefficients.lift, rel=0.2)
    signals = FidelitySignals(
        question="screening",
        maturity=0.2,
        constraint_margin=0.5,
        disagreement=0.0,
        sensitivity=0.0,
        convergence_difficulty=0.0,
        mesh_dependence=0.0,
        timestep_dependence=0.0,
        resonance_proximity=1.0,
        validity_ok={"analytical": True, "lifting_line": True, "vlm": True, "vspaero": False},
        cost_budget=5.0,
    )
    plan = plan_external_aero_fidelity("analytical", signals)
    assert plan.level in ("analytical", "lifting_line", "vlm", "vspaero")
    assert plan.reasons


def test_airframe04_polar_seam_interpolates_and_fails_closed() -> None:
    symmetric = section_model_for_profile(AirfoilProfile(family="naca4", thickness_ratio=0.12))
    assert symmetric.zero_lift_angle_deg == pytest.approx(0.0)
    assert symmetric.lift_curve_slope_per_rad == pytest.approx(6.283185307179586)
    assert symmetric.quarter_chord_moment_coefficient() == pytest.approx(0.0)
    polar = polar_from_points(
        "tiny-polar",
        [(-4.0, -0.4, 0.012, 0.0), (0.0, 0.0, 0.01, 0.0), (4.0, 0.4, 0.012, 0.0)],
    )
    assert polar.section(2.0).lift == pytest.approx(0.2)
    assert polar.zero_lift_angle_deg() == pytest.approx(0.0)
    with pytest.raises(ExternalAeroValidityError):
        polar.section(20.0)
    with pytest.raises(ExternalAeroValidationError):
        polar_from_points("bad", [(0.0, 0.0, 0.01, 0.0)])


def test_airframe04_reference_construction_and_limits() -> None:
    case, reference, _ = rectangular_case()
    assert reference.dynamic_pressure_pa == pytest.approx(0.5 * 1.225 * 3600.0)
    isa = reference_from_altitude(case.geometry_reference(), altitude_m=0.0, velocity_m_s=60.0)
    assert isa.density_kg_m3 == pytest.approx(1.225, rel=0.02)
    assert isa.mach_number == pytest.approx(60.0 / isa.speed_of_sound_m_s)
    assert evaluate_aero_validity(reference, VLM_VALIDITY_LIMITS).passed
    assert not evaluate_aero_validity(
        reference.with_state(alpha_deg=25.0), VLM_VALIDITY_LIMITS
    ).passed
    assert not evaluate_aero_validity(
        reference.with_state(alpha_deg=20.0), ANALYTICAL_VALIDITY_LIMITS
    ).passed
    with pytest.raises(ExternalAeroValidationError):
        solve_vlm(case, reference.with_state(alpha_deg=25.0), VlmOptions(
            panels_per_surface=8, include_derivatives=False, require_valid=True))


def test_airframe04_invalid_contracts_fail_closed() -> None:
    with pytest.raises(ExternalAeroValidationError):
        ExternalAeroCase(case_id="empty", surfaces=())
    case, reference, _ = rectangular_case()
    with pytest.raises(ExternalAeroValidationError):
        ExternalAeroCase(case_id="bad-symmetry", surfaces=case.surfaces, symmetry="periodic")
    with pytest.raises(ExternalAeroValidationError):
        solve_vlm(case, reference_from_conditions(
            case.geometry_reference(), density_kg_m3=1.225, velocity_m_s=0.0,
            speed_of_sound_m_s=340.0, viscosity_pa_s=1.81e-5), _TINY_VLM)
    with pytest.raises(ExternalAeroValidationError):
        VlmOptions(panels_per_surface=1)


def test_airframe04_vspaero_case_preparation_is_deterministic(tmp_path: Path) -> None:
    case, reference, _ = rectangular_case()
    level = reference.with_state(alpha_deg=4.0)
    first = prepare_vspaero_case(case, level, tmp_path / "a")
    second = prepare_vspaero_case(case, level, tmp_path / "b")
    assert first.name == "rectangular-wing-ar6.vspaero-case.json"
    assert json.loads(first.read_text(encoding="utf-8")) == json.loads(
        second.read_text(encoding="utf-8"))
    manifest = vspaero_case_manifest(case, level)
    assert manifest["caseId"] == "rectangular-wing-ar6"
    assert manifest["caseDigest"] == case.digest
