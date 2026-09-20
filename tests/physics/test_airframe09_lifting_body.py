"""AIRFRAME 09: thick lifting-body aero and tailless trim/CG closure."""

from __future__ import annotations

from dataclasses import replace

import pytest
from aeroworkbench_airframe.aero_geometry import AirfoilProfile, LiftingSurface, LoftedBody, Planform
from aeroworkbench_airframe.external_aero import (
    AeroReference,
    ExternalAeroCase,
    evaluate_analytic,
)
from aeroworkbench_airframe.trim import TaillessClosureSpec, evaluate_tailless_closure


def _configuration() -> tuple[LiftingSurface, LoftedBody]:
    surface = LiftingSurface.from_planform(
        "blended-planform",
        "lifting_body",
        Planform(span_mm=10000.0, root_chord_mm=5000.0, tip_chord_mm=1000.0, sweep_deg=35.0),
        AirfoilProfile(family="naca4", thickness_ratio=0.14),
        n_stations=5,
    )
    body = LoftedBody.from_spine(
        "thick-centerbody",
        "lifting_body",
        ((0.0, 0.0, 0.0), (0.0, 0.0, 2500.0), (0.0, 0.0, 5000.0)),
        (200.0, 2600.0, 200.0),
        (100.0, 850.0, 100.0),
    )
    return surface, body


def _reference(case: ExternalAeroCase) -> AeroReference:
    geometry = case.geometry_reference()
    return AeroReference(
        alpha_deg=4.0,
        beta_deg=0.0,
        mach_number=0.25,
        reynolds_number=5.0e6,
        density_kg_m3=1.225,
        speed_m_s=80.0,
        area_m2=geometry.area_m2,
        span_m=geometry.span_m,
        mean_chord_m=geometry.mean_chord_m,
        moment_reference_m=geometry.moment_reference_m,
    )


def test_airframe09_thick_body_semantics_feed_analytical_drag() -> None:
    surface, body = _configuration()
    thin_case = ExternalAeroCase("thin", (surface,), symmetry="mirror")
    thick_case = ExternalAeroCase("thick", (surface,), bodies=(body,), symmetry="mirror")
    thin = evaluate_analytic(thin_case, _reference(thin_case))
    thick = evaluate_analytic(thick_case, _reference(thick_case))
    assert thick.coefficients.drag > thin.coefficients.drag
    assert thick_case.canonical()["bodies"][0]["role"] == "lifting_body"
    assert thick_case.body_volume_m3 > 0.0


def test_airframe09_tailless_trim_requires_cg_margin_and_elevon_authority() -> None:
    stable = evaluate_tailless_closure(
        TaillessClosureSpec(
            cg_mac_fraction=0.28,
            neutral_point_mac_fraction=0.42,
            zero_control_pitch_coefficient=0.04,
            elevon_pitch_derivative_per_rad=-0.8,
            elevon_limit_rad=0.35,
            required_internal_volume_m3=2.0,
            available_internal_volume_m3=2.5,
        )
    )
    assert stable.feasible
    assert stable.static_margin == pytest.approx(0.14)
    assert abs(stable.required_elevon_rad) < 0.35
    unstable = evaluate_tailless_closure(
        replace(stable.spec, cg_mac_fraction=0.46)
    )
    assert not unstable.feasible
    assert "TAILESS_STATIC_MARGIN_NONPOSITIVE" in unstable.reasons


def test_airframe09_tailless_volume_closure_fails_closed() -> None:
    report = evaluate_tailless_closure(
        TaillessClosureSpec(
            cg_mac_fraction=0.25,
            neutral_point_mac_fraction=0.4,
            zero_control_pitch_coefficient=0.02,
            elevon_pitch_derivative_per_rad=-1.0,
            elevon_limit_rad=0.3,
            required_internal_volume_m3=3.0,
            available_internal_volume_m3=2.0,
        )
    )
    assert not report.feasible
    assert "TAILESS_INTERNAL_VOLUME_INSUFFICIENT" in report.reasons
