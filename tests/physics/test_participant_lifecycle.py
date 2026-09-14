"""Milestone 2: participant manifests, evidence gating, adapters, lifecycle units.

Every test here targets generic participants (no application specifics).
Heavy native runs live in test_native_execution.py; here, unavailable
binaries must fail closed and parsers prove themselves on golden files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from code_aster.comm import parse_comm_result, prepare_comm, validate_comm_result
from elmer.sif import parse_sif_result, prepare_sif, validate_sif_result
from openfoam.case import (
    parse_case_result,
    prepare_case_files,
    select_application,
    validate_case_result,
)
from participants.commands import build_command
from participants.envelope import (
    ArtifactFile,
    EvidenceBundle,
    publish_result,
)
from participants.errors import NativeErrorCode, ParticipantError
from participants.lifecycle import JobState, NativeJobManager
from participants.manifest import (
    MANIFEST_VERSION,
    PARTICIPANT_MANIFESTS,
    get_participant,
    participant_ids,
    participants_for_solver,
)
from participants.receipts import ParseReceipt, ValidityReport
from precice.validate import (
    parse_coupling_result,
    prepare_coupling_case,
    validate_coupling_result,
    validate_native_config,
)
from pybamm.cell import parse_cell_result, prepare_cell_case, validate_cell_result
from ross.rotor import (
    beam_first_critical_rpm,
    parse_rotor_result,
    prepare_rotor_case,
    validate_rotor_result,
)

CONTROL_DICT_GOLDEN = """\
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}
application     simpleFoam;

startFrom       startTime;

startTime       0;

stopAt          endTime;

endTime         500;

deltaT          1;

writeControl    timeStep;

writeInterval   50;

purgeWrite      0;

writeFormat     ascii;

writePrecision  6;

writeCompression off;

timeFormat      general;

timePrecision 6;

runTimeModifiable true;

functions
{
    pressureProbes
    {
        type            probes;
        libs            ("libsampling.so");
        writeControl    writeTime;
        fields          (p);
        probeLocations
        (
            (-0.45 0 0)
            (0.45 0 0)
        );
    }
}
"""

STATIC_COMM_GOLDEN = """\
DEBUT();

mesh = LIRE_MAILLAGE(FORMAT='MED', UNITE=20);

model = AFFE_MODELE(
    MAILLAGE=mesh,
    AFFE=_F(
        TOUT='OUI',
        PHENOMENE='MECANIQUE',
        MODELISATION='3D',
    ),
);

steel = DEFI_MATERIAU(
    ELAS=_F(E=2.100000e+11, NU=0.300000, RHO=7.800000e+03),
);

fieldmat = AFFE_MATERIAU(
    MAILLAGE=mesh,
    AFFE=_F(TOUT='OUI', MATER=(steel,)),
);

clamp = AFFE_CHAR_MECA(
    MODELE=model,
    DDL_IMPO=_F(GROUP_NO='clamp', DX=0.0, DY=0.0, DZ=0.0),
);

load = AFFE_CHAR_MECA(
    MODELE=model,
    FORCE_NODALE=_F(GROUP_NO='tip', FZ=1.000000e+03),
);

result = MECA_STATIQUE(
    MODELE=model,
    CHAM_MATER=fieldmat,
    EXCIT=(
        _F(CHARGE=clamp),
        _F(CHARGE=load),
    ),
);

IMPR_RESU(
    FORMAT='TABLEAU',
    UNITE=80,
    RESU=_F(RESULTAT=result),
);

FIN();
"""

SIMPLEFOAM_LOG = """\
Time = 499

smoothSolver:  Solving for Ux, Initial residual = 0.0012, Final residual = 8.1e-06, No Iterations 2
smoothSolver:  Solving for Uy, Initial residual = 0.0011, Final residual = 7.7e-06, No Iterations 2
smoothSolver:  Solving for Uz, Initial residual = 9.0e-04, Final residual = 6.2e-06, No Iterations 2
GAMG:  Solving for p, Initial residual = 0.0021, Final residual = 9.3e-05, No Iterations 4
time step continuity errors : sum local = 2.1e-09, global = 4.4e-10, cumulative = 4.4e-10
ExecutionTime = 12.3 s  ClockTime = 13 s

Time = 500

smoothSolver:  Solving for Ux, Initial residual = 0.0011, Final residual = 7.9e-06, No Iterations 2
smoothSolver:  Solving for Uy, Initial residual = 0.0010, Final residual = 7.5e-06, No Iterations 2
smoothSolver:  Solving for Uz, Initial residual = 8.8e-04, Final residual = 6.0e-06, No Iterations 2
GAMG:  Solving for p, Initial residual = 0.0020, Final residual = 9.1e-05, No Iterations 4
time step continuity errors : sum local = 2.0e-09, global = 4.1e-10, cumulative = 4.1e-10
ExecutionTime = 12.4 s  ClockTime = 13 s

End
"""

PROBE_P = """\
# Probe 0 (-0.45 0 0)
# Probe 1 (0.45 0 0)
# Time
499                      (12.5 10.1)
500                      (12.4 10.0)
"""

STATIC_TABLE = """\
# NODE DISPLACEMENT_M VON_MISES_PA
1 0.0 0.0
2 0.00041 1.2e+07
3 0.00112 3.4e+07
"""

MODAL_TABLE = """\
# MODE FREQUENCY_HZ
1 12.4
2 78.9
3 221.3
"""

ELMER_LOG = """\
ElmerSolver: Number of timesteps to be saved: 1
HeatSolve:  Steady state iteration:            1
HeatSolve:  Steady state iteration:            2
ElmerSolver: ALL DONE
"""

ELMER_DAT = "Temperature : max = 3.512000e+02 min = 3.000000e+02\n"

ELECTRO_DAT = "Potential : max = 4.000000e+02 min = 0.000000e+00\n"

PRECIICE_LOG = """\
preCICE config check: CONFIG_VALID
participants: fluid, structure
conservation error = 2.5e-09
"""


def _openfoam_inputs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "compressibility": "incompressible",
        "steady": True,
        "rotating_model": "none",
        "thermal_model": "isothermal",
        "turbulence": "kOmegaSST",
        "inlet_velocity_m_s": 10.0,
        "outlet_pressure_pa": 0.0,
        "density_kg_m3": 1.225,
        "viscosity_pa_s": 1.8e-5,
    }
    base.update(overrides)
    return base


def _comm_inputs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "analysis": "static",
        "prestress": False,
        "thermal_load": False,
        "contact": False,
        "youngs_modulus_pa": 2.1e11,
        "poisson_ratio": 0.3,
        "density_kg_m3": 7800.0,
        "applied_force_n": 1000.0,
        "n_modes": 4,
        "mesh_file": "mesh.med",
    }
    base.update(overrides)
    return base


def _evidence(**overrides: object) -> EvidenceBundle:
    base: dict[str, object] = {
        "capability_state": "ready",
        "capability_detail": "probe ok",
        "solver_name": "ross",
        "solver_version": "2.3.0",
        "input_hash": "a" * 64,
        "run_id": "run-1",
        "process_state": "completed",
        "exit_code": 0,
        "peak_rss_mib": 64.0,
        "execution_mode": "subprocess",
        "stdout_sha256": "b" * 64,
        "stderr_sha256": "c" * 64,
        "parser_name": "ross.rotor:parse_rotor_result",
        "parser_detail": "parsed",
        "output_files": (
            ArtifactFile(name="result.json", sha256="d" * 64, bytes=10),
        ),
        "geometry_hash": None,
        "mesh_hash": None,
        "participant_id": "rotor-campbell",
        "manifest_version": MANIFEST_VERSION,
        "validity_passed": True,
        "validity_detail": "ok",
    }
    base.update(overrides)
    return EvidenceBundle.model_validate(base)


# -- A. ParticipantManifest contract ---------------------------------------


def test_registry_covers_every_required_solver_family() -> None:
    solvers = {manifest.executable.solver_id for manifest in PARTICIPANT_MANIFESTS}
    assert {
        "openfoam",
        "code-aster",
        "ross",
        "pybamm",
        "elmer",
        "precice",
        "gmsh",
        "freecad",
    } <= solvers
    for manifest in PARTICIPANT_MANIFESTS:
        assert manifest.manifest_version == MANIFEST_VERSION
        assert manifest.inputs and manifest.outputs
        assert manifest.fidelity_levels
        assert manifest.artifacts
        assert manifest.benchmark_ref
        assert manifest.prepare_ref and manifest.parser_ref and manifest.validity_ref


def test_one_executable_services_multiple_participants() -> None:
    assert len(participants_for_solver("openfoam")) == 3
    assert len(participants_for_solver("ross")) == 2
    assert len(participants_for_solver("pybamm")) == 3
    assert len(participants_for_solver("elmer")) == 2
    assert len(participants_for_solver("code-aster")) == 2


def test_registry_is_generic_not_application_specific() -> None:
    forbidden = ("edf", "80mm", "80_mm", "turbine-stage", "stage-count")
    for participant_id in participant_ids():
        lowered = participant_id.lower()
        assert not any(token in lowered for token in forbidden), participant_id
    with pytest.raises(ValueError, match="UNKNOWN_PARTICIPANT"):
        get_participant("no-such-participant")


def test_manifest_rejects_stale_or_underspecified_declarations() -> None:
    import dataclasses

    template = get_participant("rotor-campbell")
    with pytest.raises(ValueError, match="STALE_PARTICIPANT_MANIFEST"):
        dataclasses.replace(template, manifest_version="1")
    with pytest.raises(ValueError, match="FIDELITY_LEVELS_REQUIRED"):
        dataclasses.replace(template, fidelity_levels=())


# -- G. error taxonomy ------------------------------------------------------


def test_error_taxonomy_covers_every_required_code() -> None:
    assert {code.value for code in NativeErrorCode} == {
        "CAPABILITY_UNAVAILABLE",
        "ADMISSION_REJECTED",
        "PREPARATION_FAILED",
        "MESH_INVALID",
        "PROCESS_START_FAILED",
        "PROCESS_TIMEOUT",
        "PROCESS_RSS_LIMIT_EXCEEDED",
        "PROCESS_EXIT_NONZERO",
        "PARSER_FAILED",
        "QUALITY_GATE_FAILED",
        "RESULT_INVALID",
        "CANCELLED",
        "INTERRUPTED",
    }
    error = ParticipantError(NativeErrorCode.PARSER_FAILED, "no log")
    assert error.code is NativeErrorCode.PARSER_FAILED
    assert str(error).startswith("PARSER_FAILED:")
    with pytest.raises(ValueError, match="DETAIL_REQUIRED"):
        ParticipantError(NativeErrorCode.PARSER_FAILED, "  ")


# -- C. evidence-gated publication ------------------------------------------


def test_publish_result_produces_canonical_envelope() -> None:
    parse = ParseReceipt(
        participant_id="rotor-campbell",
        parser="ross.rotor:parse_rotor_result",
        scalars={"first_critical_rpm": 2691.0, "second_critical_rpm": 10464.0},
        units={"first_critical_rpm": "rpm", "second_critical_rpm": "rpm"},
    )
    validity = ValidityReport(
        participant_id="rotor-campbell", passed=True, checks={"a": True}, detail="ok"
    )
    envelope = publish_result(
        _evidence(),
        parse=parse,
        validity=validity,
        fidelity="beam-campbell",
        provenance_id="prov-1",
        expected_artifacts=("result.json",),
    )
    assert envelope.source == "native_solver"
    assert envelope.fidelity == "beam-campbell"
    assert envelope.solver_identity == "ross"
    assert envelope.input_hash == "a" * 64
    assert envelope.scalars["first_critical_rpm"] == 2691.0


def test_publish_result_refuses_every_evidence_gap() -> None:
    parse = ParseReceipt(
        participant_id="rotor-campbell",
        parser="p",
        scalars={"first_critical_rpm": 1.0},
        units={"first_critical_rpm": "rpm"},
    )
    validity = ValidityReport(participant_id="rotor-campbell", passed=True, detail="ok")
    with pytest.raises(ParticipantError) as failed:
        publish_result(
            _evidence(validity_passed=False),
            parse=parse,
            validity=validity,
            fidelity="beam-campbell",
            provenance_id="prov-1",
        )
    assert failed.value.code is NativeErrorCode.RESULT_INVALID
    with pytest.raises(ParticipantError) as missing_logs:
        publish_result(
            _evidence(stdout_sha256=None),
            parse=parse,
            validity=validity,
            fidelity="beam-campbell",
            provenance_id="prov-1",
        )
    assert missing_logs.value.code is NativeErrorCode.RESULT_INVALID
    with pytest.raises(ParticipantError):
        publish_result(
            _evidence(),
            parse=parse,
            validity=validity,
            fidelity="beam-campbell",
            provenance_id="prov-1",
            expected_artifacts=("missing-file.dat",),
        )
    with pytest.raises(ParticipantError):
        publish_result(
            _evidence(),
            parse=ParseReceipt(participant_id="other", parser="p", scalars={"x": 1.0}),
            validity=validity,
            fidelity="beam-campbell",
            provenance_id="prov-1",
        )


# -- D. OpenFOAM -------------------------------------------------------------


def test_openfoam_application_selection_is_physics_driven() -> None:
    assert (
        select_application(compressibility="incompressible", steady=True, rotating_model="none")
        == "simpleFoam"
    )
    assert (
        select_application(compressibility="incompressible", steady=True, rotating_model="AMI")
        == "pimpleFoam"
    )
    assert (
        select_application(compressibility="compressible", steady=True, rotating_model="none")
        == "rhoSimpleFoam"
    )
    assert (
        select_application(compressibility="compressible", steady=False, rotating_model="none")
        == "rhoPimpleFoam"
    )


def test_openfoam_case_files_match_golden_text(tmp_path: Path) -> None:
    receipt = prepare_case_files(_openfoam_inputs(), tmp_path / "case-a")
    assert (tmp_path / "case-a" / "system" / "controlDict").read_text(
        encoding="utf-8"
    ) == CONTROL_DICT_GOLDEN
    assert "simpleFoam" in receipt.detail
    assert receipt.input_hash == prepare_case_files(
        _openfoam_inputs(), tmp_path / "case-b"
    ).input_hash
    mrf = prepare_case_files(
        _openfoam_inputs(rotating_model="MRF", rotation_rate_rpm=3000.0), tmp_path / "case-c"
    )
    assert "constant/MRFProperties" in mrf.files
    cht = prepare_case_files(
        _openfoam_inputs(thermal_model="CHT", inlet_temperature_k=350.0), tmp_path / "case-d"
    )
    assert "0/T" in cht.files
    compressible = prepare_case_files(
        _openfoam_inputs(compressibility="compressible"), tmp_path / "case-e"
    )
    assert "rhoSimpleFoam" in compressible.detail


def test_openfoam_prepare_fails_closed_on_bad_inputs(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as failed:
        prepare_case_files(_openfoam_inputs(viscosity_pa_s=-1.0), tmp_path / "bad")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    with pytest.raises(ParticipantError):
        prepare_case_files(_openfoam_inputs(turbulence="bogus"), tmp_path / "bad2")


def test_openfoam_log_and_probe_parsing(tmp_path: Path) -> None:
    case_dir = tmp_path / "parsed"
    prepare_case_files(_openfoam_inputs(), case_dir)
    (case_dir / "solver.log").write_text(SIMPLEFOAM_LOG, encoding="utf-8")
    probe_dir = case_dir / "postProcessing" / "probes" / "500"
    probe_dir.mkdir(parents=True)
    (probe_dir / "p").write_text(PROBE_P, encoding="utf-8")
    parsed = parse_case_result(case_dir)
    assert parsed.scalars["pressure_drop_pa"] == pytest.approx(2.4)
    assert parsed.scalars["continuity_error"] == pytest.approx(4.1e-10)
    assert parsed.scalars["residual_Ux"] == pytest.approx(7.9e-06)
    assert parsed.scalars["residual_p"] == pytest.approx(9.1e-05)
    assert validate_case_result(dict(parsed.scalars), {}).passed is True


def test_openfoam_parser_fails_closed_without_solver_output(tmp_path: Path) -> None:
    case_dir = tmp_path / "empty"
    prepare_case_files(_openfoam_inputs(), case_dir)
    with pytest.raises(ParticipantError) as failed:
        parse_case_result(case_dir)
    assert failed.value.code is NativeErrorCode.PARSER_FAILED
    (case_dir / "solver.log").write_text("Time = 1\n", encoding="utf-8")
    with pytest.raises(ParticipantError):
        parse_case_result(case_dir)


# -- D. Code_Aster -------------------------------------------------------------


def test_code_aster_static_comm_matches_golden_text(tmp_path: Path) -> None:
    receipt = prepare_comm(_comm_inputs(), tmp_path / "static")
    assert (tmp_path / "static" / "case.comm").read_text(
        encoding="utf-8"
    ) == STATIC_COMM_GOLDEN
    assert (tmp_path / "static" / "case.export").read_text(encoding="utf-8").startswith(
        "P actions make_etude"
    )
    assert receipt.files == ("case.comm", "case.export")


def test_code_aster_modal_comm_supports_prestress(tmp_path: Path) -> None:
    receipt = prepare_comm(
        _comm_inputs(analysis="modal", prestress=True), tmp_path / "modal"
    )
    text = (tmp_path / "modal" / "case.comm").read_text(encoding="utf-8")
    assert "CALC_MODES" in text
    assert "MECA_STATIQUE" in text
    assert "RESULTAT=modes" in text
    assert "prestress=True" in receipt.detail
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(_comm_inputs(analysis="static", prestress=True), tmp_path / "bad")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED


def test_code_aster_result_parsing(tmp_path: Path) -> None:
    static_dir = tmp_path / "static-run"
    prepare_comm(_comm_inputs(), static_dir)
    (static_dir / "solver.log").write_text("as_run EXIT_CODE=0\nFIN\n", encoding="utf-8")
    (static_dir / "result_table.txt").write_text(STATIC_TABLE, encoding="utf-8")
    parsed = parse_comm_result(static_dir)
    assert parsed.scalars["max_displacement_m"] == pytest.approx(0.00112)
    assert parsed.scalars["max_von_mises_pa"] == pytest.approx(3.4e7)
    assert validate_comm_result(dict(parsed.scalars), {"applied_force_n": 1000.0}).passed

    modal_dir = tmp_path / "modal-run"
    prepare_comm(_comm_inputs(analysis="modal"), modal_dir)
    (modal_dir / "solver.log").write_text("as_run EXIT_CODE=0\nFIN\n", encoding="utf-8")
    (modal_dir / "result_table.txt").write_text(MODAL_TABLE, encoding="utf-8")
    modal = parse_comm_result(modal_dir)
    assert modal.scalars["first_frequency_hz"] == pytest.approx(12.4)
    assert validate_comm_result(dict(modal.scalars), {}).passed

    with pytest.raises(ParticipantError) as failed:
        parse_comm_result(tmp_path / "missing")
    assert failed.value.code is NativeErrorCode.PARSER_FAILED


# -- D. ROSS -------------------------------------------------------------------


def _rotor_inputs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "analysis": "campbell",
        "shaft_length_m": 1.5,
        "shaft_diameter_m": 0.05,
        "n_elements": 4,
        "bearing_stiffness_n_m": 1e8,
        "bearing_damping_n_s_m": 1000.0,
        "max_speed_rpm": 12000.0,
    }
    base.update(overrides)
    return base


def test_ross_prepare_is_stable_and_fail_closed(tmp_path: Path) -> None:
    first = prepare_rotor_case(_rotor_inputs(), tmp_path / "rotor-a")
    second = prepare_rotor_case(_rotor_inputs(), tmp_path / "rotor-b")
    assert first.input_hash == second.input_hash
    assert first.files == ("case.json", "run_ross.py")
    assert (tmp_path / "rotor-a" / "run_ross.py").stat().st_size > 1000
    with pytest.raises(ParticipantError) as failed:
        prepare_rotor_case(_rotor_inputs(shaft_diameter_m=-0.1), tmp_path / "bad")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    with pytest.raises(ParticipantError):
        prepare_rotor_case(_rotor_inputs(n_elements=1), tmp_path / "bad2")


def test_ross_parse_and_beam_validity_on_golden_receipt(tmp_path: Path) -> None:
    case_dir = tmp_path / "rotor-run"
    prepare_rotor_case(_rotor_inputs(), case_dir)
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "library": "ross-rotordynamics",
                "solver_version": "2.3.0",
                "analysis": "campbell",
                "ndof": 30,
                "critical_speeds_rpm": [2691.28, 10464.47],
                "speed_range_rpm": [0, 2000, 4000, 6000, 8000, 10000, 12000],
            }
        ),
        encoding="utf-8",
    )
    parsed = parse_rotor_result(case_dir)
    assert parsed.scalars["first_critical_rpm"] == pytest.approx(2691.28)
    estimate = beam_first_critical_rpm(shaft_length_m=1.5, shaft_diameter_m=0.05)
    assert estimate == pytest.approx(2747.0, rel=0.02)
    assert validate_rotor_result(dict(parsed.scalars), _rotor_inputs()).passed is True
    bad = dict(parsed.scalars, first_critical_rpm=10.0)
    assert validate_rotor_result(bad, _rotor_inputs()).passed is False


# -- D. PyBaMM -----------------------------------------------------------------


def _cell_inputs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "model": "spm",
        "parameter_set": "Chen2020",
        "discharge_current_a": 1.0,
        "duration_s": 60.0,
        "n_series": 2,
        "n_parallel": 3,
    }
    base.update(overrides)
    return base


def test_pybamm_supports_arbitrary_topology_and_models(tmp_path: Path) -> None:
    for model, parameter_set in (
        ("spm", "Chen2020"),
        ("spme", "Chen2020"),
        ("dfn", "Marquis2019"),
        ("thevenin", "ECM_Example"),
    ):
        receipt = prepare_cell_case(
            _cell_inputs(model=model, parameter_set=parameter_set, n_series=7, n_parallel=5),
            tmp_path / f"cell-{model}",
        )
        assert "topology=7s5p" in receipt.detail
    with pytest.raises(ParticipantError) as failed:
        prepare_cell_case(
            _cell_inputs(model="thevenin", parameter_set="Chen2020"), tmp_path / "bad"
        )
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    with pytest.raises(ParticipantError):
        prepare_cell_case(_cell_inputs(duration_s=7200.0), tmp_path / "bad2")


def test_pybamm_parse_and_coulomb_validity_on_golden_receipt(tmp_path: Path) -> None:
    case_dir = tmp_path / "cell-run"
    prepare_cell_case(_cell_inputs(), case_dir)
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "library": "pybamm",
                "solver_version": "26.8.0.0",
                "model": "spm",
                "parameter_set": "Chen2020",
                "pack_voltage_start_v": 8.286,
                "pack_voltage_end_v": 8.241,
                "pack_delivered_ah": 0.05,
                "pack_soc_end": 0.9967,
            }
        ),
        encoding="utf-8",
    )
    parsed = parse_cell_result(case_dir)
    assert parsed.scalars["voltage_start_v"] == pytest.approx(8.286)
    assert parsed.units["delivered_ah"] == "A.h"
    assert validate_cell_result(dict(parsed.scalars), _cell_inputs()).passed is True
    charged = dict(parsed.scalars, voltage_end_v=9.0)
    assert validate_cell_result(charged, _cell_inputs()).passed is False


# -- D. Elmer --------------------------------------------------------------------


def test_elmer_sif_covers_thermal_and_electrostatic(tmp_path: Path) -> None:
    thermal = prepare_sif(
        {
            "model": "thermal",
            "conductivity_w_m_k": 167.0,
            "heat_load_w": 10.0,
            "ambient_k": 300.0,
        },
        tmp_path / "thermal",
    )
    text = (tmp_path / "thermal" / "case.sif").read_text(encoding="utf-8")
    assert "HeatSolve" in text
    assert "SaveScalars" in text
    assert "Temperature = 3.000000e+02" in text
    assert thermal.files == ("case.sif",)
    electrostatic = prepare_sif(
        {"model": "electrostatic", "permittivity": 4.5, "voltage_v": 400.0},
        tmp_path / "electro",
    )
    assert "StatElecSolve" in (tmp_path / "electro" / "case.sif").read_text(encoding="utf-8")
    assert electrostatic.files == ("case.sif",)
    with pytest.raises(ParticipantError) as failed:
        prepare_sif({"model": "thermal", "conductivity_w_m_k": -1.0}, tmp_path / "bad")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED


def test_elmer_log_and_scalars_parsing(tmp_path: Path) -> None:
    case_dir = tmp_path / "elmer-run"
    prepare_sif(
        {
            "model": "thermal",
            "conductivity_w_m_k": 167.0,
            "heat_load_w": 10.0,
            "ambient_k": 300.0,
        },
        case_dir,
    )
    (case_dir / "solver.log").write_text(ELMER_LOG, encoding="utf-8")
    (case_dir / "result.dat").write_text(ELMER_DAT, encoding="utf-8")
    parsed = parse_sif_result(case_dir)
    assert parsed.scalars["max_temperature_k"] == pytest.approx(351.2)
    assert validate_sif_result(dict(parsed.scalars), {"ambient_k": 300.0}).passed is True
    with pytest.raises(ParticipantError) as failed:
        parse_sif_result(tmp_path / "missing")
    assert failed.value.code is NativeErrorCode.PARSER_FAILED


# -- D. preCICE --------------------------------------------------------------------


def test_precice_native_config_validates_and_parses(tmp_path: Path) -> None:
    receipt = prepare_coupling_case(
        {
            "participants": ["fluid", "structure"],
            "coupling_dt_s": 1e-3,
            "max_iterations": 50,
            "tolerance": 1e-6,
        },
        tmp_path / "coupling",
    )
    xml_text = (tmp_path / "coupling" / "precice-config.xml").read_text(encoding="utf-8")
    assert "<precice-configuration>" in xml_text
    assert "serial-implicit" in xml_text
    assert validate_native_config(xml_text).passed is True
    with pytest.raises(ParticipantError):
        validate_native_config("<broken")
    with pytest.raises(ParticipantError):
        validate_native_config("<precice-configuration/>")
    with pytest.raises(ParticipantError) as failed:
        prepare_coupling_case(
            {
                "participants": ["solo"],
                "coupling_dt_s": 1e-3,
                "max_iterations": 50,
                "tolerance": 1e-6,
            },
            tmp_path / "bad",
        )
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    assert receipt.files == ("precice-config.xml", "case.json")

    (tmp_path / "coupling" / "solver.log").write_text(PRECIICE_LOG, encoding="utf-8")
    parsed = parse_coupling_result(tmp_path / "coupling")
    assert parsed.scalars["conservation_error"] == pytest.approx(2.5e-09)
    assert validate_coupling_result(dict(parsed.scalars), {"tolerance": 1e-6}).passed is True


# -- DoD 14: no manifest bypass ------------------------------------------------------


def test_command_builder_rejects_everything_but_manifest_commands(tmp_path: Path) -> None:  # noqa: ARG001
    ross_command = build_command("rotor-campbell", "case-abc123")
    assert ross_command[1] == "run_ross.py"
    openfoam_command = build_command("incompressible-steady-flow", "case-abc123")
    assert openfoam_command == ("simpleFoam",)
    assert build_command("structural-static", "case-abc123") == ("as_run", "case.export")
    assert build_command("thermal-conduction", "case-abc123") == ("ElmerSolver", "case.sif")
    with pytest.raises(ValueError, match="UNKNOWN_PARTICIPANT"):
        build_command("rm-rf-everything", "case-abc123")
    for bad_id in ("../outside", "/absolute", "C:\\win", "case with spaces", "case\x00x", ""):
        with pytest.raises(ParticipantError):
            build_command("rotor-campbell", bad_id)
    with pytest.raises(ParticipantError):
        build_command("domain-mesh", "case-abc123")


# -- B. lifecycle units --------------------------------------------------------------


def test_deferred_job_can_be_cancelled_with_full_event_history(tmp_path: Path) -> None:
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit(
        "cell-spm-discharge",
        {
            "model": "spm",
            "parameter_set": "Chen2020",
            "discharge_current_a": 1.0,
            "duration_s": 60.0,
            "n_series": 1,
            "n_parallel": 1,
        },
        deferred=True,
    )
    assert manager.status(job_id)["state"] == JobState.QUEUED.value
    assert manager.cancel(job_id) == JobState.CANCELLED.value
    states = [event["state"] for event in manager.events(job_id)]
    assert states == [JobState.QUEUED.value, JobState.CANCELLED.value]
    with pytest.raises(ParticipantError) as failed:
        manager.envelope(job_id)
    assert failed.value.code is NativeErrorCode.RESULT_INVALID


def test_lifecycle_fails_closed_for_unknown_participant_and_bad_inputs(tmp_path: Path) -> None:
    manager = NativeJobManager(tmp_path / "jobs")
    with pytest.raises(ValueError, match="UNKNOWN_PARTICIPANT"):
        manager.submit("does-not-exist", {}, deferred=True)
    with pytest.raises(ValueError, match="INVALID_JOB_INPUTS"):
        manager.submit("rotor-campbell", ["not-a-mapping"], deferred=True)  # type: ignore[arg-type]
    with pytest.raises(KeyError, match="JOB_NOT_FOUND"):
        manager.status("0" * 32)


def test_windows_tree_rss_probe_measures_live_process() -> None:
    import os

    if os.name != "nt":
        pytest.skip("windows-only RSS probe")
    from participants.win_rss import windows_process_tree_rss_mib

    from aeroworkbench_api.process_supervisor import SupervisorError

    assert windows_process_tree_rss_mib(os.getpid()) > 0
    with pytest.raises(SupervisorError):
        windows_process_tree_rss_mib(-1)


def test_missing_binary_fails_closed_with_capability_code(tmp_path: Path) -> None:
    from participants.capabilities import probe_participant

    probe = probe_participant("incompressible-steady-flow")
    if probe.state == "ready":
        pytest.skip("OpenFOAM is installed; capability gating covered by unit probe")
    manager = NativeJobManager(tmp_path / "jobs")
    job_id = manager.submit("incompressible-steady-flow", _openfoam_inputs(), deferred=True)
    assert manager.run(job_id) == JobState.FAILED.value
    status = manager.status(job_id)
    assert status["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
    events = [event["state"] for event in manager.events(job_id)]
    assert events == [
        JobState.QUEUED.value,
        JobState.PREPARING.value,
        JobState.FAILED.value,
    ]
    assert events[-1] == JobState.FAILED.value
