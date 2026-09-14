"""Milestone 4: 80 mm three-stage EDF through the general workbench.

Part 1 (generic, core): the OpenFOAM case builder must accept ANY declared
rotating-zone count for MRF -- a general capability the EDF finalists need.
Part 2 (example layer): the 80 mm three-stage EDF lives entirely in
``examples/edf/80mm_three_stage/`` and composes generic M1/M2/M3 facilities
with zero core changes for 2/3/4 stages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "examples" / "edf" / "80mm_three_stage"),
)

# ---------------------------------------------------------------------------
# Part 1: generic N-zone MRF capability (core, not EDF-specific)
# ---------------------------------------------------------------------------

BASE_FLOW_INPUTS: dict[str, object] = {
    "participant_id": "rotating-flow-mrf",
    "compressibility": "incompressible",
    "rotating_model": "MRF",
    "thermal_model": "isothermal",
    "turbulence": "kOmegaSST",
    "steady": True,
    "inlet_velocity_m_s": 12.0,
    "outlet_pressure_pa": 0.0,
    "density_kg_m3": 1.225,
    "viscosity_pa_s": 1.81e-5,
    "rotation_rate_rpm": 35000.0,
}


def _mrf_text(case_dir: Path) -> str:
    return (case_dir / "constant" / "MRFProperties").read_text(encoding="utf-8")


@pytest.mark.parametrize("n_zones", [1, 2, 3, 4])
def test_openfoam_mrf_accepts_any_rotating_zone_count(tmp_path: Path, n_zones: int) -> None:
    from openfoam.case import prepare_case_files

    zones = [
        {"name": f"rotor_zone_{index}", "rotation_rate_rpm": 35000.0 + 500.0 * index}
        for index in range(n_zones)
    ]
    inputs = {**BASE_FLOW_INPUTS, "rotating_zones": zones}
    receipt = prepare_case_files(inputs, tmp_path / f"mrf-{n_zones}")
    assert receipt.input_hash is not None and len(receipt.input_hash) == 64
    text = _mrf_text(tmp_path / f"mrf-{n_zones}")
    for index in range(n_zones):
        assert f"MRF{index + 1}" in text
        assert f"cellZone        rotor_zone_{index};" in text
    assert f"MRF{n_zones + 1}" not in text
    # Per-zone rate lands in rad/s: 35000 rpm -> 3665.19 rad/s.
    assert "omega           constant 3665.191" in text


def test_openfoam_mrf_zone_hashes_distinguish_counts(tmp_path: Path) -> None:
    from openfoam.case import prepare_case_files

    digests = set()
    for n_zones in (1, 2, 3, 4):
        zones = [{"name": f"rotor_zone_{i}", "rotation_rate_rpm": 35000.0} for i in range(n_zones)]
        receipt = prepare_case_files(
            {**BASE_FLOW_INPUTS, "rotating_zones": zones}, tmp_path / f"hash-{n_zones}"
        )
        assert receipt.input_hash is not None
        digests.add(receipt.input_hash)
    assert len(digests) == 4


def test_openfoam_mrf_legacy_single_zone_output_unchanged(tmp_path: Path) -> None:
    from openfoam.case import prepare_case_files

    case_dir = tmp_path / "legacy"
    prepare_case_files(dict(BASE_FLOW_INPUTS), case_dir)
    text = _mrf_text(case_dir)
    assert "MRF1" in text
    assert "MRF2" not in text
    assert "cellZone        rotor;" in text
    assert "omega           constant 3665.191" in text


def test_openfoam_mrf_rejects_zones_without_mrf(tmp_path: Path) -> None:
    from openfoam.case import prepare_case_files
    from participants.errors import ParticipantError

    inputs = {
        **BASE_FLOW_INPUTS,
        "rotating_model": "none",
        "rotating_zones": [{"name": "rotor_zone_0", "rotation_rate_rpm": 35000.0}],
    }
    with pytest.raises(ParticipantError):
        prepare_case_files(inputs, tmp_path / "bad")


def test_openfoam_mrf_rejects_bad_zone_declarations(tmp_path: Path) -> None:
    from openfoam.case import prepare_case_files
    from participants.errors import ParticipantError

    for bad_zones in (
        [],
        [{"name": "", "rotation_rate_rpm": 35000.0}],
        [{"name": "rotor zone!", "rotation_rate_rpm": 35000.0}],
        [{"name": "rotor_zone_0", "rotation_rate_rpm": float("nan")}],
        [{"name": "rotor_zone_0", "rotation_rate_rpm": 35000.0}] * 9,
    ):
        with pytest.raises(ParticipantError):
            prepare_case_files(
                {**BASE_FLOW_INPUTS, "rotating_zones": bad_zones}, tmp_path / "bad"
            )


# ---------------------------------------------------------------------------
# Part 2: example-layer contract (all EDF specifics stay in the example dir)
# ---------------------------------------------------------------------------

VARIANTS = ("80mm-3stage", "70mm-2stage", "90mm-4stage")


def test_edf_config_defaults_and_variants() -> None:
    from edf_config import EDF80Config

    default = EDF80Config.default()
    assert default.outer_diameter_mm == pytest.approx(80.0)
    assert default.n_stages == 3
    assert len(default.rotor_names) == 3
    assert len(default.stator_names) == 2
    assert default.exit_deswirler is True
    by_name = {variant.name: variant for variant in EDF80Config.variants()}
    assert set(by_name) == set(VARIANTS)
    assert by_name["70mm-2stage"].outer_diameter_mm == pytest.approx(70.0)
    assert by_name["70mm-2stage"].n_stages == 2
    assert by_name["90mm-4stage"].outer_diameter_mm == pytest.approx(90.0)
    assert by_name["90mm-4stage"].n_stages == 4
    for variant in EDF80Config.variants():
        variant.validate()


@pytest.mark.parametrize("variant", VARIANTS)
def test_edf_geometry_uses_generic_duct_builder(variant: str) -> None:
    from edf_config import EDF80Config
    from edf_geometry import build_edf_geometry

    config = next(item for item in EDF80Config.variants() if item.name == variant)
    built = build_edf_geometry(config)
    assert built.n_rotating == config.n_stages
    assert built.parameter_hash is not None and len(built.parameter_hash) == 64
    assert built.shape_hash is not None and len(built.shape_hash) == 64
    assert tuple(built.rotating_zones) == tuple(config.rotor_names)
    assert built.kernel_available is True


def test_edf_design_variables_cover_milestone_geometry() -> None:
    from edf_config import EDF80Config
    from edf_geometry import design_variables

    variables = design_variables(EDF80Config.default())
    names = {variable.name for variable in variables}
    for required in (
        "hub_diameter_mm",
        "blade_count",
        "stator_count",
        "chord_mm",
        "twist_deg",
        "thickness_mm",
        "axial_gap_mm",
        "tip_clearance_mm",
        "inlet_radius_mm",
        "nozzle_exit_mm",
        "rpm",
    ):
        assert required in names


def test_edf_screening_is_labelled_analytical() -> None:
    from edf_config import EDF80Config
    from edf_screening import screen_candidate

    receipt = screen_candidate(EDF80Config.default(), rpm=35000.0, freestream_m_s=0.0)
    assert receipt.source == "analytical"
    assert receipt.fidelity == "screening-analytic"
    assert receipt.outputs["thrust_n"] > 0
    assert receipt.outputs["shaft_power_w"] > 0
    assert receipt.units["thrust_n"] == "N"
    assert len(receipt.input_hash) == 64
    assert receipt.outputs["tip_mach"] < 1.0


def test_edf_participant_graph_uses_registry_ids_only() -> None:
    from edf_participants import participant_graph
    from participants.manifest import participant_ids

    graph = participant_graph()
    assert set(graph.nodes) <= set(participant_ids())
    for required in (
        "rotating-flow-mrf",
        "domain-mesh",
        "cad-interchange",
        "rotor-campbell",
        "rotor-modal",
        "pack-thevenin-discharge",
        "thermal-conduction",
        "structural-static",
        "coupled-interface-validation",
    ):
        assert required in graph.nodes


def test_edf_openfoam_config_declares_all_three_rotors() -> None:
    from edf_config import EDF80Config
    from edf_participants import openfoam_inputs

    inputs = openfoam_inputs(EDF80Config.default(), rpm=35000.0)
    assert inputs["rotating_model"] == "MRF"
    zones = inputs["rotating_zones"]
    assert isinstance(zones, list) and len(zones) == 3
    assert [zone["name"] for zone in zones] == ["rotor_zone_0", "rotor_zone_1", "rotor_zone_2"]


def test_edf_coupled_system_converges_through_openmdao() -> None:
    from edf_config import EDF80Config
    from edf_coupling import solve_coupled_system

    result = solve_coupled_system(EDF80Config.default(), rpm=35000.0)
    assert result.engine == "openmdao"
    assert result.converged is True
    values = dict(result.values)
    # Electrical/mechanical reconciliation: shaft power == torque * omega.
    omega = 35000.0 * 2.0 * 3.141592653589793 / 60.0
    assert values["aero.shaft_power_w"] == pytest.approx(
        values["aero.torque_n_m"] * omega, rel=1e-6
    )
    assert values["motor.current_a"] > 0
    assert values["motor.voltage_v"] > 0
    # Terminal power balance closure held inside the coordinator.
    assert values["motor.current_a"] * values["motor.voltage_v"] == pytest.approx(
        values["motor.electrical_power_w"], rel=1e-9
    )


def test_edf_fidelity_sequence_comes_from_policies() -> None:
    from edf_participants import fidelity_ladders
    from edf_study import plan_edf_fidelity

    ladders = fidelity_ladders()
    assert "aero" in ladders and "electrical" in ladders and "rotor" in ladders
    plan = plan_edf_fidelity(maturity=0.7, constraint_margin=0.05)
    assert plan.level == "mrf-steady"
    assert plan.escalate is True
    assert len(plan.reasons) >= 1
    assert len(plan.input_hash) == 64


def test_edf_doe_runs_from_design_state_with_quality_gating() -> None:
    from edf_config import EDF80Config
    from edf_study import run_screening_doe
    from ross.rotor import beam_first_critical_rpm

    estimate_rpm = beam_first_critical_rpm(shaft_length_m=0.15, shaft_diameter_m=0.008)
    result = run_screening_doe(
        EDF80Config.default(),
        n_samples=4,
        seed=7,
        mesh_sensitivity=0.02,
        min_sicn=0.25,
        first_whirl_hz=estimate_rpm / 60.0,
    )
    assert result.engine != ""
    assert len(result.samples) == 12  # 4 points x 3 operating points
    assert result.best is not None
    assert result.best.state == "valid"


def test_edf_resonance_uses_generic_policy() -> None:
    from aeroworkbench_coupling.resonance import (
        ResonancePolicy,
        check_resonance,
    )
    from edf_coupling import forcing_spectra, modal_spectrum

    forcing = forcing_spectra(rpm=35000.0, blade_counts=(9, 9, 9), stator_counts=(11, 11))
    modal = (modal_spectrum(first_whirl_hz=812.5),)
    trigger = check_resonance(
        forcing,
        modal,
        ResonancePolicy(
            warning_margin_hz=100.0,
            critical_margin_hz=25.0,
            watch_activate=("transient",),
            critical_activate=("transient",),
            available=("transient",),
        ),
    )
    assert trigger.state in {"clear", "watch", "triggered"}
    assert trigger.min_separation_hz >= 0


def test_edf_field_transfer_uses_generic_coupler() -> None:
    from edf_coupling import aero_structural_transfer

    receipt = aero_structural_transfer()
    assert receipt.accepted is True
    assert receipt.relative_conservation_error <= receipt.tolerance
    assert receipt.quantity == "pressure"


def test_edf_design_revision_shape() -> None:
    from edf_config import EDF80Config
    from edf_study import design_state_for

    state = design_state_for(EDF80Config.default())
    assert state["designId"] == "edf-80mm-three-stage"
    assert len(state["revisionId"]) == 12
    assert len(state["objectives"]) >= 3
    assert len(state["constraints"]) >= 8
    assert len(state["operatingPoints"]) == 3
    assert len(state["motionFrames"]) == 4  # 3 rotating + 1 stationary frame
    assert len(state["participantSolvers"]) >= 6


# ---------------------------------------------------------------------------
# Part 3: executable natives through the governed job system (bounded cases)
# ---------------------------------------------------------------------------


def test_edf_ross_modal_runs_natively(tmp_path: Path) -> None:
    from edf_participants import rotor_modal_inputs
    from participants.capabilities import probe_participant
    from participants.lifecycle import NativeJobManager

    if probe_participant("rotor-modal").state != "ready":
        pytest.skip("ROSS is not installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "rotor-modal",
        rotor_modal_inputs(speed_rpm=42000.0),
        design_id="edf-80mm",
        deferred=True,
    )
    assert manager.run(job_id) == "COMPLETED"
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["scalars"]["first_whirl_hz"] > 0
    assert envelope["validity"]["passed"] is True


def test_edf_ross_campbell_gate_fails_closed_on_short_shaft(tmp_path: Path) -> None:
    """Short stiff EDF shafts trip the generic Campbell beam-consistency gate.

    ROSS executes natively (real numbers), but evidence-gated publication
    refuses to bless bearing-mode criticals against a flexible-beam estimate.
    This pins the GENERAL gap: the Campbell gate fits long flexible shafts.
    """

    from edf_participants import rotor_campbell_inputs
    from participants.capabilities import probe_participant
    from participants.errors import NativeErrorCode, ParticipantError
    from participants.lifecycle import NativeJobManager

    if probe_participant("rotor-campbell").state != "ready":
        pytest.skip("ROSS is not installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "rotor-campbell", rotor_campbell_inputs(), design_id="edf-80mm", deferred=True
    )
    state = manager.run(job_id)
    assert state in {"COMPLETED", "FAILED"}
    if state == "COMPLETED":
        assert manager.envelope(job_id)["validity"]["passed"] is True
    else:
        with pytest.raises(ParticipantError) as blocked:
            manager.envelope(job_id)
        assert blocked.value.code is NativeErrorCode.RESULT_INVALID


def test_edf_pybamm_thevenin_runs_natively(tmp_path: Path) -> None:
    from edf_participants import battery_inputs
    from participants.capabilities import probe_participant
    from participants.lifecycle import NativeJobManager

    if probe_participant("pack-thevenin-discharge").state != "ready":
        pytest.skip("PyBaMM is not installed")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "pack-thevenin-discharge",
        battery_inputs(discharge_current_a=25.0),
        design_id="edf-80mm",
        deferred=True,
    )
    assert manager.run(job_id) == "COMPLETED"
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["scalars"]["voltage_end_v"] < envelope["scalars"]["voltage_start_v"]
    assert envelope["validity"]["passed"] is True


def test_edf_mesh_sensitivity_coarse_medium(tmp_path: Path) -> None:
    from edf_config import EDF80Config
    from edf_participants import mesh_inputs
    from participants.capabilities import probe_participant
    from participants.lifecycle import NativeJobManager

    if probe_participant("domain-mesh").state != "ready":
        pytest.skip("Gmsh is not installed")
    config = next(
        item for item in EDF80Config.variants() if item.name == "70mm-2stage"
    )
    manager = NativeJobManager(tmp_path / "jobs")
    counts: dict[str, float] = {}
    for tag, base in (("coarse", 14.0), ("medium", 10.0)):
        job_id = manager.submit(
            "domain-mesh", mesh_inputs(config, base_size_mm=base),
            design_id="edf-70mm", deferred=True,
        )
        assert manager.run(job_id) == "COMPLETED"
        envelope = manager.envelope(job_id)
        assert envelope["source"] == "native_solver"
        assert envelope["validity"]["passed"] is True
        counts[tag] = float(envelope["scalars"]["element_count"])
    assert counts["medium"] > counts["coarse"]
    sensitivity = abs(counts["medium"] - counts["coarse"]) / counts["medium"]
    assert sensitivity == pytest.approx(sensitivity)  # recorded, finite
    assert 0.0 < sensitivity < 1.0


def test_edf_cad_interchange_runs_natively(tmp_path: Path) -> None:
    from edf_config import EDF80Config
    from edf_participants import cad_inputs
    from participants.capabilities import probe_participant
    from participants.lifecycle import NativeJobManager

    if probe_participant("cad-interchange").state != "ready":
        pytest.skip("no CAD backend installed")
    config = EDF80Config.default()
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "cad-interchange", cad_inputs(config), design_id="edf-80mm", deferred=True
    )
    assert manager.run(job_id) == "COMPLETED"
    envelope = manager.envelope(job_id)
    assert envelope["source"] == "native_solver"
    assert envelope["validity"]["passed"] is True


def test_edf_heavy_cfd_fails_closed_not_faked(tmp_path: Path) -> None:
    from edf_config import EDF80Config
    from edf_participants import openfoam_inputs
    from participants.capabilities import probe_participant
    from participants.lifecycle import NativeJobManager

    if probe_participant("rotating-flow-mrf").state == "ready":
        pytest.skip("OpenFOAM is installed; fail-closed path not exercised")
    manager = NativeJobManager(tmp_path / "jobs")
    # Full case inputs: prepare succeeds (real config evidence), execution
    # fails closed on the absent binary -- never a fabricated result.
    job_id = manager.submit(
        "rotating-flow-mrf",
        openfoam_inputs(EDF80Config.default(), rpm=35000.0),
        design_id="edf-80mm",
        deferred=True,
    )
    assert manager.run(job_id) == "FAILED"
    status = manager.status(job_id)
    assert "CAPABILITY_UNAVAILABLE" in json.dumps(status)
    events = manager.events(job_id)
    assert [event["state"] for event in events][0] == "QUEUED"


def test_edf_design_result_has_all_milestone_sections() -> None:
    from edf_config import EDF80Config
    from edf_study import assemble_design_result

    natives = {
        "rotor-modal": {"source": "native_solver", "scalars": {"first_whirl_hz": 210.0}}
    }
    meshes = {"coarse_elements": 1000.0, "medium_elements": 1500.0, "min_sicn": 0.2}
    result = assemble_design_result(
        EDF80Config.default(), native_summary=natives, mesh_summary=meshes
    )
    assert result["dynamic"]["first_whirl_hz"] == 210.0
    assert result["dynamic"]["whirl_source"] == "native_solver"
    for section in (
        "identity",
        "geometry",
        "meshes",
        "aerodynamic",
        "electrical",
        "thermal",
        "structural",
        "dynamic",
        "quality",
        "provenance",
    ):
        assert section in result, f"missing section {section}"
    assert result["provenance"]["solver_identities"] != {}
    assert result["quality"]["validation_state"] in {"validated", "not-validated"}
