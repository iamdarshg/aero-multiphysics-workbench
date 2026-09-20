"""AIRFRAME 05: trim, static/dynamic stability, and control-authority solvers.

Deterministic analytic fixtures prove level-flight and climb trim converge to
force/moment balance, control limits and static instability surface as
infeasible constraint violations, sign conventions hold, and missing
coefficients, derivatives, CG, or native capability fail closed.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe import InertiaTensor, MassProperties, Quantity, Vec3
from aeroworkbench_airframe.trim import (
    INFEASIBLE,
    PREFLIGHT_INVALID,
    TRIMMED,
    AeroCoefficients,
    AerodynamicCoefficientProvider,
    AeroReference,
    AeroState,
    DerivativeBundle,
    FlightCondition,
    LateralDirectionalDerivatives,
    LinearAeroModel,
    LongitudinalDerivatives,
    NativeTrimCapabilityError,
    TrimFidelity,
    TrimSpec,
    TrimVariable,
    evaluate_control_authority,
    evaluate_dynamic_stability,
    evaluate_static_stability,
    native_trim_capability,
    neutral_point,
    solve_trim,
    static_margin,
    trim_level_flight,
    verification_fidelity,
    verify_trim_nonlinear,
)
from aeroworkbench_airframe.trim.errors import AeroCoefficientError

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "airframe" / "trim"
_FIXTURE = "linear_trim_fixture.json"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _load() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((_FIXTURE_DIR / _FIXTURE).read_text(encoding="utf-8"))
    return payload


def _quantity(payload: dict[str, Any]) -> Quantity:
    return Quantity(payload["value"], payload["unit"])


def _model(data: dict[str, Any]) -> LinearAeroModel:
    reference = data["reference"]
    moment = reference["momentReference"]
    return LinearAeroModel(
        model_id=data["modelId"],
        reference_geometry=AeroReference(
            frame=reference["frame"],
            area=_quantity(reference["area"]),
            span=_quantity(reference["span"]),
            chord=_quantity(reference["chord"]),
            moment_reference=Vec3(
                moment["x"], moment["y"], moment["z"], moment["unit"], moment["frame"]
            ),
            cg_mac_fraction=reference["cgMacFraction"],
        ),
        longitudinal=LongitudinalDerivatives(**data["longitudinal"]),
        lateral_directional=LateralDirectionalDerivatives(**data["lateralDirectional"]),
        induced_drag_factor=data["inducedDragFactor"],
    )


def _condition(data: dict[str, Any]) -> FlightCondition:
    payload = data["condition"]
    return FlightCondition(
        velocity=_quantity(payload["velocity"]),
        density=_quantity(payload["density"]),
        gravity=_quantity(payload["gravity"]),
        mass=_quantity(payload["mass"]),
        gamma=_quantity(payload["gamma"]),
        thrust_max=_quantity(payload["thrustMax"]),
    )


def _mass(data: dict[str, Any]) -> MassProperties:
    payload = data["mass"]
    cg = payload["cg"]
    inertia = payload["inertia"]
    zeros = {"ixy": 0.0, "ixz": 0.0, "iyz": 0.0}
    return MassProperties(
        mass=_quantity(payload["mass"]),
        cg=Vec3(cg["x"], cg["y"], cg["z"], cg["unit"], cg["frame"]),
        inertia=InertiaTensor(
            ixx=Quantity(inertia["ixx"], "kg.m2"),
            iyy=Quantity(inertia["iyy"], "kg.m2"),
            izz=Quantity(inertia["izz"], "kg.m2"),
            ixy=Quantity(zeros["ixy"], "kg.m2"),
            ixz=Quantity(zeros["ixz"], "kg.m2"),
            iyz=Quantity(zeros["iyz"], "kg.m2"),
            frame=inertia["frame"],
        ),
    )


def _closed_form_trim(data: dict[str, Any]) -> tuple[float, float, float]:
    lon = data["longitudinal"]
    cond = data["condition"]
    velocity = cond["velocity"]["value"]
    density = cond["density"]["value"]
    weight = cond["mass"]["value"] * cond["gravity"]["value"]
    dynamic = 0.5 * density * velocity * velocity * data["reference"]["area"]["value"]
    lift_needed = weight / dynamic
    rhs_alpha = lift_needed - lon["cl_0"]
    rhs_pitch = -lon["cm_0"]
    det = lon["cl_alpha"] * lon["cm_de"] - lon["cl_de"] * lon["cm_alpha"]
    alpha = (rhs_alpha * lon["cm_de"] - lon["cl_de"] * rhs_pitch) / det
    elevator = (lon["cl_alpha"] * rhs_pitch - rhs_alpha * lon["cm_alpha"]) / det
    drag_coef = lon["cd_0"] + lon["cd_alpha"] * alpha + data["inducedDragFactor"] * lift_needed**2
    return alpha, elevator, dynamic * drag_coef / cond["thrustMax"]["value"]


def test_level_trim_converges_to_force_moment_balance() -> None:
    data = _load()
    result = trim_level_flight(_model(data), _condition(data), elevator_limit=Quantity(0.5, "rad"))
    assert result.status == TRIMMED
    assert result.converged and result.feasible and result.trimmed
    assert result.solution is not None and result.residuals is not None
    assert result.residuals.scaled_norm < 1e-9
    assert result.solution.lift.value_si == pytest.approx(9810.0, abs=1e-6)
    assert result.solution.thrust.value_si == pytest.approx(result.solution.drag.value_si, abs=1e-6)
    assert result.solution.pitch_moment.value_si == pytest.approx(0.0, abs=1e-9)


def test_trim_matches_closed_form_equilibrium() -> None:
    data = _load()
    result = trim_level_flight(_model(data), _condition(data))
    alpha, elevator, throttle = _closed_form_trim(data)
    assert result.solution is not None
    assert result.solution.alpha.value_si == pytest.approx(alpha, abs=1e-6)
    assert result.solution.elevator.value_si == pytest.approx(elevator, abs=1e-6)
    assert result.solution.throttle == pytest.approx(throttle, abs=1e-6)


def test_climb_trim_maneuver_point() -> None:
    data = _load()
    base = _condition(data)
    gamma = Quantity(5.0, "deg")
    condition = FlightCondition(
        velocity=base.velocity, density=base.density, gravity=base.gravity,
        mass=base.mass, gamma=gamma,
    )
    spec = TrimSpec(
        condition=condition,
        variables=(TrimVariable.ALPHA, TrimVariable.ELEVATOR, TrimVariable.THRUST),
        elevator_limit=Quantity(0.5, "rad"),
        require_stability=False,
    )
    result = solve_trim(_model(data), spec)
    assert result.status == TRIMMED
    assert result.solution is not None and result.residuals is not None
    assert result.solution.gamma.value_si == pytest.approx(gamma.value_si, abs=1e-12)
    assert result.residuals.scaled_norm < 1e-9
    assert result.solution.thrust.value_si > result.solution.drag.value_si


def test_insufficient_elevator_authority_is_infeasible() -> None:
    data = _load()
    result = trim_level_flight(
        _model(data), _condition(data), elevator_limit=Quantity(0.001, "rad")
    )
    assert result.status == INFEASIBLE
    assert not result.feasible
    assert result.control_authority is not None
    assert not result.control_authority.within_authority
    assert "CONTROL_AUTHORITY_EXCEEDED:elevator" in result.control_authority.reasons
    assert "CONTROL_AUTHORITY_EXCEEDED:elevator" in result.notes


def test_throttle_beyond_max_is_infeasible() -> None:
    data = _load()
    payload = data["condition"]
    condition = FlightCondition(
        velocity=_quantity(payload["velocity"]), density=_quantity(payload["density"]),
        gravity=_quantity(payload["gravity"]), mass=_quantity(payload["mass"]),
        thrust_max=Quantity(100.0, "N"),
    )
    result = trim_level_flight(_model(data), condition)
    assert result.status == INFEASIBLE
    assert result.solution is not None and result.solution.throttle is not None
    assert result.solution.throttle > 1.0
    assert "THROTTLE_OUT_OF_RANGE" in result.notes


def test_static_instability_is_a_constraint_violation() -> None:
    data = _load()
    model = _model(data)
    unstable = replace(
        model, longitudinal=replace(model.longitudinal, cm_alpha=0.4),
    )
    result = trim_level_flight(unstable, _condition(data), elevator_limit=Quantity(0.5, "rad"))
    assert result.converged
    assert result.status == INFEASIBLE
    assert "STATIC_INSTABILITY_CONSTRAINT_VIOLATION" in result.notes
    assert result.static_stability is not None
    assert result.static_stability.longitudinal_stable is False


def test_static_margin_and_neutral_point() -> None:
    data = _load()
    model = _model(data)
    margin = static_margin(model.longitudinal)
    point = neutral_point(model.longitudinal, cg_mac_fraction=0.25)
    assert margin.value_si == pytest.approx(0.8 / 4.5)
    assert point.value_si == pytest.approx(0.25 + 0.8 / 4.5)
    report = evaluate_static_stability(
        model.longitudinal, model.lateral_directional, cg_mac_fraction=0.25
    )
    assert report.valid and report.longitudinal_stable and report.lateral_directional_stable
    assert report.static_margin is not None and report.neutral_point is not None
    assert report.coverage_complete
    assert report.meta.validity.valid


def test_sign_and_axis_conventions() -> None:
    data = _load()
    model = _model(data)
    high = model.coefficients(AeroState(alpha=Quantity(0.05, "rad")))
    low = model.coefficients(AeroState(alpha=Quantity(-0.05, "rad")))
    assert isinstance(high, AeroCoefficients)
    assert high.c_lift > low.c_lift
    neutral = model.coefficients(AeroState(alpha=Quantity(0.0, "rad")))
    up = model.coefficients(
        AeroState(alpha=Quantity(0.0, "rad"), deflections=(("elevator", Quantity(0.05, "rad")),))
    )
    assert up.c_pitch < neutral.c_pitch
    side = model.coefficients(
        AeroState(alpha=Quantity(0.0, "rad"), beta=Quantity(0.05, "rad"))
    )
    assert side.c_side < 0.0
    report = evaluate_static_stability(
        model.longitudinal, model.lateral_directional, cg_mac_fraction=0.25
    )
    verdicts = {finding.name: finding for finding in report.findings if finding.kind == "stability"}
    assert verdicts["cm_alpha_negative"].passed
    assert verdicts["cn_beta_positive"].passed
    assert verdicts["cl_beta_negative"].passed


def test_missing_derivative_coverage_fails_closed() -> None:
    data = _load()
    model = _model(data)
    sparse = replace(model, longitudinal=replace(model.longitudinal, cl_alpha=None, cm_alpha=None))
    with pytest.raises(AeroCoefficientError):
        sparse.coefficients(AeroState(alpha=Quantity(0.05, "rad")))
    report = evaluate_static_stability(
        sparse.longitudinal, sparse.lateral_directional, cg_mac_fraction=0.25
    )
    assert not report.valid
    assert report.longitudinal_stable is None
    assert not report.coverage_complete
    with pytest.raises(AeroCoefficientError):
        static_margin(sparse.longitudinal)
    dynamic = evaluate_dynamic_stability(
        sparse, condition=_condition(data), mass_properties=_mass(data)
    )
    assert not dynamic.valid
    assert dynamic.longitudinal_modes == () and dynamic.lateral_modes == ()


def test_missing_cg_fails_closed_for_stability_gated_trim() -> None:
    data = _load()
    model = _model(data)
    reference = replace(model.reference_geometry, cg_mac_fraction=None)
    floating = replace(model, reference_geometry=reference)
    gated = trim_level_flight(floating, _condition(data))
    assert gated.status == PREFLIGHT_INVALID
    assert "CG_UNAVAILABLE_FOR_STATIC_MARGIN" in gated.notes
    ungated = trim_level_flight(floating, _condition(data), require_stability=False)
    assert ungated.status == TRIMMED
    assert ungated.static_stability is None


def test_missing_thrust_source_fails_closed() -> None:
    data = _load()
    payload = data["condition"]
    condition = FlightCondition(
        velocity=_quantity(payload["velocity"]), density=_quantity(payload["density"]),
        gravity=_quantity(payload["gravity"]), mass=_quantity(payload["mass"]),
    )
    spec = TrimSpec(
        condition=condition,
        variables=(TrimVariable.ALPHA, TrimVariable.ELEVATOR, TrimVariable.THROTTLE),
    )
    result = solve_trim(_model(data), spec)
    assert result.status == PREFLIGHT_INVALID
    assert result.notes == ("THRUST_SOURCE_UNAVAILABLE",)


def test_dynamic_stability_modes_and_damping() -> None:
    data = _load()
    model = _model(data)
    condition = _condition(data)
    trim = trim_level_flight(model, condition)
    assert trim.solution is not None
    report = evaluate_dynamic_stability(
        model, condition=condition, mass_properties=_mass(data),
        trim_alpha=trim.solution.alpha.value_si, trim_elevator=trim.solution.elevator.value_si,
    )
    assert report.valid
    assert len(report.longitudinal_matrix) == 4 and len(report.lateral_matrix) == 4
    lon = {mode.kind for mode in report.longitudinal_modes}
    lat = {mode.kind for mode in report.lateral_modes}
    assert {"short-period", "phugoid"} <= lon
    assert {"dutch-roll", "roll", "spiral"} <= lat
    short_period = [mode for mode in report.longitudinal_modes if mode.kind == "short-period"]
    assert len(short_period) == 2 and all(mode.stable for mode in short_period)
    assert all(mode.frequency_hz >= 0.0 for mode in report.longitudinal_modes)
    assert report.meta.validity.valid


def test_control_authority_available_vs_required() -> None:
    data = _load()
    model = _model(data)
    condition = _condition(data)
    trim = trim_level_flight(model, condition, elevator_limit=Quantity(0.5, "rad"))
    assert trim.solution is not None
    dynamic = 0.5 * condition.density.value_si * trim.solution.velocity.value_si**2
    state = AeroState(alpha=trim.solution.alpha, velocity=trim.solution.velocity,
                      deflections=(("elevator", Quantity(0.0, "rad")),))
    report = evaluate_control_authority(
        model, state, reference=model.reference_geometry, dynamic_pressure=dynamic,
        required_pitch_moment=100.0, elevator_limit=Quantity(0.5, "rad"),
    )
    assert report.within_authority
    surface = report.surface("elevator")
    assert surface.moment_per_rad.value_si == pytest.approx(dynamic * 10.0 * 1.0 * -1.2)
    assert surface.available_moment.value_si == pytest.approx(
        abs(surface.moment_per_rad.value_si) * 0.5
    )
    assert surface.ratio == pytest.approx(100.0 / surface.available_moment.value_si)
    assert report.meta.validity.valid


def test_results_carry_metadata_and_are_deterministic() -> None:
    data = _load()
    model = _model(data)
    condition = _condition(data)
    first = trim_level_flight(model, condition, elevator_limit=Quantity(0.5, "rad"))
    second = trim_level_flight(model, condition, elevator_limit=Quantity(0.5, "rad"))
    assert first.content_hash == second.content_hash
    assert _HEX64.match(first.meta.input_hash)
    assert first.meta.source.value == "analytical"
    assert first.meta.fidelity.value == "analytical"
    assert first.meta.software.name == "aeroworkbench-airframe-trim"
    assert first.meta.provenance.model == "airframe-trim-equilibrium"
    assert dict(first.meta.units)["force"] == "N"
    assert first.static_stability is not None
    assert _HEX64.match(first.static_stability.meta.input_hash)
    assert first.control_authority is not None
    assert _HEX64.match(first.control_authority.meta.input_hash)
    assert json.loads(json.dumps(first.as_dict()))["status"] == TRIMMED
    assert hash(first.solution) == hash(second.solution)


def test_solution_quantities_are_unit_bearing() -> None:
    data = _load()
    result = trim_level_flight(_model(data), _condition(data))
    assert result.solution is not None
    assert result.solution.alpha.dimension == "angle"
    assert result.solution.thrust.dimension == "force"
    assert result.solution.velocity.dimension == "velocity"
    assert result.solution.lift.dimension == "force"
    assert result.solution.pitch_moment.dimension == "moment"
    assert result.solution.alpha.to_unit("deg").value_si == pytest.approx(
        result.solution.alpha.value_si
    )


def test_native_verifier_fails_closed_and_never_relabels_screening() -> None:
    capability = native_trim_capability()
    assert not capability.available
    assert verification_fidelity() is TrimFidelity.SCREENING
    with pytest.raises(NativeTrimCapabilityError):
        verify_trim_nonlinear()
    data = _load()
    result = trim_level_flight(_model(data), _condition(data))
    assert result.fidelity is TrimFidelity.SCREENING


def test_provider_contract_is_structural() -> None:
    data = _load()
    model = _model(data)
    assert isinstance(model, AerodynamicCoefficientProvider)
    bundle = model.derivatives(AeroState(alpha=Quantity(0.0, "rad")))
    assert isinstance(bundle, DerivativeBundle)
    assert bundle.content_hash == model.derivatives(
        AeroState(alpha=Quantity(0.0, "rad"))
    ).content_hash
