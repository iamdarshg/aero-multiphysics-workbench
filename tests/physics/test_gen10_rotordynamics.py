"""GEN 10: generic rotor dynamics from geometry/material/support models.

Covers the canonical rotating-assembly contract, native ROSS construction from
it, participant-declared arbitrary forcing spectra, the screening-vs-native
validity policy (the short stiff shaft no longer trips a brittle beam gate), and
resonance signals feeding the generic fidelity planner. Native cases stay tiny
and bounded; absence of ROSS fails closed by skip, never by an invented value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_dynamics import (
    BENCHMARK_NAMES,
    ForcingLine,
    ForcingSpecError,
    RotorModelError,
    assess_forcing_separation,
    benchmark_inputs,
    benchmark_model,
    normalize_forcing_lines,
    normalize_rotor_model,
)
from aeroworkbench_optimization.planner import (
    FidelityImplementation,
    FidelitySignals,
    plan_fidelity,
)
from participants.capabilities import probe_participant
from participants.errors import NativeErrorCode, ParticipantError
from participants.lifecycle import JobState, NativeJobManager
from ross.rotor import (
    beam_first_critical_rpm,
    prepare_rotor_case,
    validate_rotor_result,
)


def _rotor_ready(participant: str = "rotor-campbell") -> None:
    if probe_participant(participant).state != "ready":
        pytest.skip("ROSS is not installed")


# -- A. canonical rotating-assembly model ------------------------------------


def test_canonical_model_normalizes_legacy_and_explicit_forms() -> None:
    legacy = normalize_rotor_model(benchmark_inputs("flexible-shaft-bearings", analysis="modal"))
    assert legacy.node_count == 7
    assert legacy.material.name == "steel"
    explicit = normalize_rotor_model(
        {
            "analysis": "modal",
            "speed_rpm": 3000.0,
            "segments": [
                {"length_m": 0.5, "outer_diameter_m": 0.06},
                {"length_m": 0.5, "outer_diameter_m": 0.04, "inner_diameter_m": 0.01},
            ],
            "material": {
                "name": "custom",
                "youngs_modulus_pa": 120e9,
                "shear_modulus_pa": 45e9,
                "density_kg_m3": 4500.0,
            },
            "disks": [{"position": 1, "outer_diameter_m": 0.15, "width_m": 0.03}],
            "bearings": [
                {"node": 0, "kxx": 1e7, "kyy": 1.2e7, "cxx": 100.0, "cyy": 120.0},
                {"node": 2, "kxx": 1e7, "kyy": 1.2e7, "cxx": 100.0, "cyy": 120.0},
            ],
        }
    )
    assert explicit.node_count == 3
    assert explicit.max_outer_diameter_m == pytest.approx(0.06)
    assert explicit.material.density_kg_m3 == pytest.approx(4500.0)
    assert explicit.disks[0].inner_diameter_m == pytest.approx(0.06)


def test_geometry_and_material_revisions_change_model_identity() -> None:
    base = normalize_rotor_model(benchmark_inputs("short-stiff-shaft", analysis="modal"))
    reamed = normalize_rotor_model(
        benchmark_inputs("short-stiff-shaft", analysis="modal", shaft_diameter_m=0.010)
    )
    light = normalize_rotor_model(
        benchmark_inputs(
            "short-stiff-shaft",
            analysis="modal",
            material={
                "name": "aluminium",
                "youngs_modulus_pa": 68.9e9,
                "shear_modulus_pa": 26.0e9,
                "density_kg_m3": 2700.0,
            },
        )
    )
    assert base.canonical_payload() != reamed.canonical_payload()
    assert base.canonical_payload() != light.canonical_payload()
    assert base.total_length_m == pytest.approx(0.15)


@pytest.mark.parametrize("name", BENCHMARK_NAMES)
def test_canonical_benchmarks_normalize(name: str) -> None:
    model = benchmark_model(name, analysis="modal")
    assert model.node_count >= 3
    assert model.total_length_m > 0
    assert model.bearings


# -- D. fail-closed model/support validity -----------------------------------


@pytest.mark.parametrize(
    "bad",
    (
        {"shaft_diameter_m": -0.1},
        {"n_elements": 1},
        {"bearing_stiffness_n_m": 0.0},
        {"max_speed_rpm": 0.0},
        {
            "segments": [{"length_m": 0.1, "outer_diameter_m": 0.01, "inner_diameter_m": 0.02}]
        },
        {"material": {"name": "unknown", "youngs_modulus_pa": 1e9}},
        {
            "bearings": [{"node": 99, "kxx": 1e6}],
            "analysis": "modal",
            "shaft_length_m": 1.0,
            "shaft_diameter_m": 0.02,
            "n_elements": 4,
            "speed_rpm": 1000.0,
        },
    ),
)
def test_invalid_support_or_model_input_fails_closed(tmp_path: Path, bad: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "analysis": "campbell",
        "shaft_length_m": 1.5,
        "shaft_diameter_m": 0.05,
        "n_elements": 4,
        "bearing_stiffness_n_m": 1e8,
        "max_speed_rpm": 12000.0,
    }
    base.update(bad)
    with pytest.raises(ParticipantError) as failed:
        prepare_rotor_case(base, tmp_path / "bad")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED


def test_rotor_model_errors_are_typed() -> None:
    with pytest.raises(RotorModelError):
        normalize_rotor_model({"analysis": "campbell", "shaft_length_m": 1.0})
    with pytest.raises(ForcingSpecError):
        normalize_forcing_lines([{"source": "p", "lines": [{"frequency_hz": -1.0}]}])


# -- C. participant-declared forcing spectra ---------------------------------


def test_forcing_lines_resolve_orders_without_invented_frequencies() -> None:
    lines = normalize_forcing_lines(
        [
            {
                "source": "aero",
                "label": "orders",
                "lines": [
                    {"order": 9.0, "speed_dependence": "order", "amplitude": 12.0},
                    {"frequency_hz": 350.0},
                    {"order": 1.0, "speed_dependence": "synchronous"},
                ],
            },
            {"source_id": "controller", "frequency_hz": 120.0, "harmonic_family": "control"},
        ]
    )
    assert len(lines) == 4
    by_order = {line.order: line for line in lines if line.order is not None}
    assert by_order[9.0].frequency_at(42000.0) == pytest.approx(6300.0)
    assert by_order[1.0].frequency_at(42000.0) == pytest.approx(700.0)
    fixed = next(line for line in lines if line.frequency_hz == 350.0)
    assert fixed.frequency_at(42000.0) == pytest.approx(350.0)
    # No forcing declared means no forcing frequencies are generated anywhere.
    assert normalize_forcing_lines(None) == ()


def test_forcing_margins_trigger_correct_state() -> None:
    modes = (100.0, 250.0, 400.0)
    near = assess_forcing_separation(
        (ForcingLine(source="p", frequency_hz=101.0, amplitude=1.0),),
        modes,
        speed_rpm=3600.0,
        warning_margin_hz=5.0,
        critical_margin_hz=2.0,
    )
    assert near.state == "triggered"
    assert near.required_capability == "transient"
    assert near.minima_hz == pytest.approx(1.0)
    watch = assess_forcing_separation(
        (ForcingLine(source="p", frequency_hz=103.0),),
        modes,
        speed_rpm=3600.0,
    )
    assert watch.state == "watch"
    assert watch.required_capability == "harmonic"
    clear = assess_forcing_separation(
        (ForcingLine(source="p", frequency_hz=150.0),),
        modes,
        speed_rpm=3600.0,
    )
    assert clear.state == "clear"
    assert clear.required_capability is None
    assert clear.lines[0].source == "p"


def test_resonance_signal_feeds_generic_fidelity_planner() -> None:
    assessment = assess_forcing_separation(
        (ForcingLine(source="p", frequency_hz=100.0, amplitude=1.0),),
        (100.5,),
        speed_rpm=3600.0,
        warning_margin_hz=5.0,
        critical_margin_hz=2.0,
    )
    signal = assessment.fidelity_signal(reference_hz=100.0)
    assert signal["required_capability"] == "transient"
    implementations = (
        FidelityImplementation("steady-native", 0, 10.0, ("steady",)),
        FidelityImplementation("harmonic-response", 1, 40.0, ("harmonic",)),
        FidelityImplementation("transient-fsi", 2, 200.0, ("transient", "field-coupled")),
    )
    decision = plan_fidelity(
        "steady-native",
        implementations,
        FidelitySignals(
            question="resonance",
            maturity=0.5,
            constraint_margin=0.5,
            disagreement=0.0,
            sensitivity=0.0,
            convergence_difficulty=0.0,
            mesh_dependence=0.0,
            timestep_dependence=0.0,
            resonance_proximity=signal["resonance_proximity"],
            validity_ok={},
            cost_budget=500.0,
            required_capability=signal["required_capability"],
        ),
    )
    assert decision.escalate is True
    assert decision.level == "transient-fsi"


# -- D. validity policy removes the false beam blocker ------------------------


def test_short_stiff_native_critical_is_not_rejected_by_beam_gate() -> None:
    inputs = benchmark_inputs("short-stiff-shaft", analysis="campbell")
    # Real native numbers measured on this assembly: first forward critical is
    # ~0.29x the simply-supported beam estimate (bearing-dominated mode).
    report = validate_rotor_result({"first_critical_rpm": 12593.56}, inputs)
    assert report.passed is True
    assert report.checks["screening_plausible"] is True
    # An order-of-magnitude implausible critical still fails closed.
    assert validate_rotor_result({"first_critical_rpm": 10.0}, inputs).passed is False
    estimate = beam_first_critical_rpm(shaft_length_m=0.15, shaft_diameter_m=0.008)
    assert estimate == pytest.approx(43544.6, rel=0.02)


# -- B/F. native ROSS construction and benchmarks ----------------------------


def test_native_short_stiff_campbell_now_completes(tmp_path: Path) -> None:
    _rotor_ready("rotor-campbell")
    manager = NativeJobManager(tmp_path / "jobs")
    inputs = benchmark_inputs("short-stiff-shaft", analysis="campbell")
    job_id = manager.submit("rotor-campbell", inputs, deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    first = envelope["scalars"]["first_critical_rpm"]
    assert first > 0
    assert envelope["validity"]["passed"] is True
    assert "screening" in envelope["validity"]["detail"]
    manager.close()


def test_native_bearing_stiffness_changes_modes(tmp_path: Path) -> None:
    _rotor_ready("rotor-modal")
    manager = NativeJobManager(tmp_path / "jobs")
    soft = benchmark_inputs("short-stiff-shaft", analysis="modal", bearing_stiffness_n_m=5.0e6)
    stiff = benchmark_inputs("short-stiff-shaft", analysis="modal", bearing_stiffness_n_m=5.0e8)
    soft_job = manager.submit("rotor-modal", soft, deferred=True)
    stiff_job = manager.submit("rotor-modal", stiff, deferred=True)
    assert manager.run(soft_job) == JobState.COMPLETED.value
    assert manager.run(stiff_job) == JobState.COMPLETED.value
    soft_hz = manager.envelope(soft_job)["scalars"]["first_whirl_hz"]
    stiff_hz = manager.envelope(stiff_job)["scalars"]["first_whirl_hz"]
    assert soft_hz > 0 and stiff_hz > 0
    assert stiff_hz > soft_hz
    # No forcing was declared, so no forcing-frequency result is invented.
    assert "min_forcing_separation_hz" not in manager.envelope(soft_job)["scalars"]
    manager.close()


def test_native_modal_publishes_declared_forcing_margin(tmp_path: Path) -> None:
    _rotor_ready("rotor-modal")
    manager = NativeJobManager(tmp_path / "jobs")
    inputs = benchmark_inputs(
        "short-stiff-shaft",
        analysis="modal",
        speed_rpm=42000.0,
        forcings=[
            {
                "source": "aero-participant",
                "label": "rotating-order",
                "lines": [
                    {"order": 9.0, "speed_dependence": "order", "amplitude": 12.0},
                    {"frequency_hz": 350.0},
                ],
            }
        ],
    )
    job_id = manager.submit("rotor-modal", inputs, deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["validity"]["passed"] is True
    assert "min_forcing_separation_hz" in envelope["scalars"]
    case_dir = tmp_path / "jobs" / f"case-{job_id[:12]}"
    result = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    report = result["forcing_separation"]
    assert report["min_separation_hz"] == pytest.approx(
        envelope["scalars"]["min_forcing_separation_hz"]
    )
    assert report["state"] in {"clear", "watch", "triggered"}
    assert {line["source"] for line in report["lines"]} == {"aero-participant"}
    manager.close()


def test_native_forced_unbalance_response_reference(tmp_path: Path) -> None:
    _rotor_ready("rotor-campbell")
    manager = NativeJobManager(tmp_path / "jobs")
    inputs = benchmark_inputs("unbalance-reference", analysis="forced", speed_rpm=8000.0)
    job_id = manager.submit("rotor-campbell", inputs, deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["scalars"]["peak_response_m"] > 0
    assert envelope["scalars"]["peak_speed_rpm"] > 0
    manager.close()


def test_native_jeffcott_rotor_benchmark(tmp_path: Path) -> None:
    _rotor_ready("rotor-modal")
    manager = NativeJobManager(tmp_path / "jobs")
    inputs = benchmark_inputs("jeffcott", analysis="modal", speed_rpm=6000.0)
    job_id = manager.submit("rotor-modal", inputs, deferred=True)
    assert manager.run(job_id) == JobState.COMPLETED.value, manager.status(job_id)
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["scalars"]["first_whirl_hz"] > 0
    assert 0 <= envelope["scalars"]["first_damping_ratio"] < 1
    assert envelope["validity"]["passed"] is True
    manager.close()
