"""Bounded unit tests for the four governed native-path blocker fixes.

These run without any native binary: capability probing, allowlisted command
selection, Elmer SIF validity, Code_Aster table parsing, and the native preCICE
coupled-window prepare/parse/validate path are all exercised through fakes and
golden files. No solver output is fabricated.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from code_aster.comm import parse_comm_result, prepare_comm
from elmer.parser import parse_elmer_output
from elmer.sif import prepare_sif
from participants import capabilities
from participants import commands
from participants.commands import build_command, register_case_executable, run_script_path
from participants.errors import NativeErrorCode, ParticipantError
from participants.manifest import get_participant
from precice.validate import (
    parse_native_window_result,
    prepare_native_window,
    validate_native_window_config,
    validate_native_window_result,
)

_GEOMETRY_HASH = "a" * 64
_MESH_HASH = "b" * 64


# -- OpenFOAM: capability probe accepts a nonzero-exit version banner ---------


def test_openfoam_probe_accepts_nonzero_help_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "/opt/solvers/bin/simpleFoam")
    monkeypatch.setattr(
        capabilities.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="--> FOAM FATAL ERROR : cannot find file\nOpenFOAM-v2412\n",
        ),
    )
    state, version, detail = capabilities._probe_openfoam("simpleFoam")
    assert state == "ready"
    assert version is not None and "2412" in version
    assert "present" in detail


def test_openfoam_probe_uses_environment_version_when_banner_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "/opt/solvers/bin/pimpleFoam")
    monkeypatch.setattr(
        capabilities.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    monkeypatch.setenv("WM_PROJECT_VERSION", "v2412")
    state, version, _ = capabilities._probe_openfoam("pimpleFoam")
    assert state == "ready"
    assert version == "OpenFOAM v2412"


def test_generic_probe_still_fails_closed_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        capabilities.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="usage\n", stderr=""),
    )
    state, _, detail = capabilities._probe_executable("not-openfoam")
    assert state == "unavailable"
    assert "exited 1" in detail


# -- OpenFOAM: executable selection from declared physics --------------------


def test_build_command_uses_registered_physics_executable() -> None:
    register_case_executable("case-ami0001", "pimpleFoam")
    assert build_command("rotating-flow-mrf", "case-ami0001") == ("pimpleFoam",)
    # Unregistered cases keep the manifest's declared default.
    assert build_command("rotating-flow-mrf", "case-steady") == ("simpleFoam",)


def test_register_case_executable_rejects_path_escape() -> None:
    with pytest.raises(ParticipantError) as failed:
        register_case_executable("case-evil", "../../bin/sh")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED


# -- OpenFOAM: governed mesh conversion --------------------------------------


def test_convert_governed_mesh_runs_allowlisted_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openfoam.case import _convert_governed_mesh

    case_dir = tmp_path / "case"
    case_dir.mkdir()
    mesh = tmp_path / "artifact"
    mesh.mkdir()
    (mesh / "domain.msh").write_text("$MeshFormat\n4.1 0 8\n$EndMeshFormat\n", encoding="utf-8")
    governed = SimpleNamespace(mesh_path=mesh / "domain.msh")

    monkeypatch.setattr("openfoam.case.shutil.which", lambda name: f"/opt/solvers/bin/{name}")

    def fake_run(argv, **kwargs):
        assert argv[0].endswith("gmshToFoam")
        (case_dir / "constant" / "polyMesh").mkdir(parents=True)
        return SimpleNamespace(returncode=0, stdout="Mesh stats\n", stderr="")

    monkeypatch.setattr("openfoam.case.subprocess.run", fake_run)
    assert _convert_governed_mesh({"mesh_conversion": "gmshToFoam"}, case_dir, governed) == "gmshToFoam"
    assert (case_dir / "constant" / "polyMesh").is_dir()


def test_convert_governed_mesh_fails_closed_without_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openfoam.case import _convert_governed_mesh

    monkeypatch.setattr("openfoam.case.shutil.which", lambda name: None)
    with pytest.raises(ParticipantError) as failed:
        _convert_governed_mesh(
            {"mesh_conversion": "gmshToFoam"}, tmp_path, SimpleNamespace(mesh_path=tmp_path / "x.msh")
        )
    assert failed.value.code is NativeErrorCode.CAPABILITY_UNAVAILABLE


def test_convert_governed_mesh_rejects_unknown_method(tmp_path: Path) -> None:
    from openfoam.case import _convert_governed_mesh

    with pytest.raises(ParticipantError) as failed:
        _convert_governed_mesh({"mesh_conversion": "rm -rf"}, tmp_path, None)
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED


# -- Elmer: SIF must be valid for Elmer 26.2 --------------------------------


def _elmer_export() -> dict[str, object]:
    return {
        "participant": "elmer",
        "zones": [{"name": "body-a", "motion": "stationary", "domain": "solid"}],
        "patches": [{"name": "left", "kind": "wall"}, {"name": "right", "kind": "wall"}],
        "interfaces": [],
        "materials": [{"name": "body-a", "material": "steel"}],
        "bodyIds": {"body-a": 3},
        "boundaryIds": {"left": 7, "right": 8},
    }


def _elmer_mesh(tmp_path: Path) -> Path:
    mesh = tmp_path / "domain.msh"
    mesh.write_text(
        "\n".join(
            [
                "$MeshFormat",
                "4.1 0 8",
                "$EndMeshFormat",
                "$PhysicalNames",
                "4",
                '3 1 "body-a"',
                '3 2 "material_body-a"',
                '2 3 "left"',
                '2 4 "right"',
                "$EndPhysicalNames",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return mesh


def _elmer_inputs(mesh: Path) -> dict[str, object]:
    material = {
        "deterministic": True,
        "properties": {
            "conductivity": 2.0,
            "heat_capacity": 1.0,
            "density": 1.0,
        },
    }
    return {
        "model": "thermal",
        "analysis": "steady",
        "mesh_mapping": _elmer_export(),
        "mesh_file": "domain.msh",
        "mesh_source": str(mesh),
        "mesh_hash": _MESH_HASH,
        "geometry_hash": _GEOMETRY_HASH,
        "materials": {"steel": material},
        "heat_sources": [],
        "fixed_temperature": [
            {"patch": "left", "temperature_k": 400.0},
            {"patch": "right", "temperature_k": 300.0},
        ],
        "energy_balance_tolerance": 1.0e-3,
        "ambient_k": 300.0,
    }


def test_elmer_sif_is_valid_native_form(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    prepare_sif(_elmer_inputs(_elmer_mesh(tmp_path)), case_dir)
    sif = (case_dir / "case.sif").read_text(encoding="utf-8")

    # `Target Bodies` belongs to a Body, never to a SaveScalars solver.
    assert "Target Bodies(1) = 3" in sif
    solver_sections = sif.split("Solver ", 1)[1] if "Solver " in sif else ""
    assert "Target Bodies" not in solver_sections
    # No duplicate bare `Equation = SaveScalars`; each post-solver is unique.
    assert "\n  Equation = SaveScalars\n" not in sif
    assert 'Equation = "SaveScalarsGlobal"' in sif
    assert sif.count('Equation = "SaveScalarsBoundary_') == 2
    # Convergence tolerance stays on the solver; post-solvers run after the solve.
    assert "Steady State Convergence Tolerance = 1.0e-6" in sif
    assert "Exec Solver = After Simulation" in sif
    # Native boundary numbering, not declaration order.
    assert "Target Boundaries(1) = 7" in sif
    assert "Target Boundaries(1) = 8" in sif
    # Energy-balance quantity the parser can read.
    assert "Operator 1 = diffusive flux" in sif
    assert "Coefficient 1 = Heat Conductivity" in sif
    assert 'Mask Name 1 = "save_left"' in sif
    assert "Save Scalars = True" in sif
    assert "save_left = Logical True" in sif


def _write_elmer_native(case_dir: Path, *, left_flux: float, right_flux: float) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "native": True,
                "analysis": "steady",
                "mesh": {"meshHash": _MESH_HASH, "geometryHash": _GEOMETRY_HASH},
                "totalHeatInputW": 0.0,
                "interfaces": [],
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "solver.log").write_text(
        "HeatSolve: Steady state iteration 1\nElmerSolver: ALL DONE\n", encoding="utf-8"
    )
    (case_dir / "result.dat").write_text(
        "Temperature : max = 4.000000e+02 min = 3.000000e+02\n"
        "Temperature : mean = 3.500000e+02\n"
        "Heat Flux : max = 1.333333e+02 min = 1.333333e+02\n",
        encoding="utf-8",
    )
    (case_dir / "boundary_left.dat").write_text(
        f"Temperature : diffusive flux = {left_flux:.6e}\n", encoding="utf-8"
    )
    (case_dir / "boundary_right.dat").write_text(
        f"Temperature : diffusive flux = {right_flux:.6e}\n", encoding="utf-8"
    )


def test_elmer_parser_reads_energy_balance_from_boundary_fluxes(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _write_elmer_native(case_dir, left_flux=133.3333, right_flux=-133.3333)
    parsed = parse_elmer_output(case_dir)
    assert parsed.scalars["energy_balance_error_w"] == pytest.approx(0.0, abs=1e-9)
    assert parsed.scalars["energy_balance_relative_error"] == pytest.approx(0.0, abs=1e-9)
    assert parsed.scalars["boundary_left_heat_flow_w"] == pytest.approx(133.3333)


def test_elmer_parser_energy_imbalance_is_not_zero(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _write_elmer_native(case_dir, left_flux=100.0, right_flux=-10.0)
    parsed = parse_elmer_output(case_dir)
    assert parsed.scalars["energy_balance_relative_error"] > 1e-3


# -- Code_Aster: run_aster support and export naming -------------------------


def test_code_aster_export_names_the_parsed_table(tmp_path: Path) -> None:
    case_dir = tmp_path / "static"
    prepare_comm(
        {
            "analysis": "static",
            "youngs_modulus_pa": 2.1e11,
            "poisson_ratio": 0.3,
            "density_kg_m3": 7800.0,
            "applied_force_n": 1000.0,
            "mesh_file": "mesh.med",
        },
        case_dir,
    )
    export = (case_dir / "case.export").read_text(encoding="utf-8")
    assert "R repe result_table.txt R 80" in export
    assert "result.rmed" not in export


def test_build_command_prefers_available_run_aster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        commands.shutil, "which", lambda name: "/opt/aster/bin/run_aster" if name == "run_aster" else None
    )
    assert build_command("structural-static", "case-aster01") == ("run_aster", "case.export")


def test_code_aster_generic_tableau_is_parsed(tmp_path: Path) -> None:
    case_dir = tmp_path / "run"
    case_dir.mkdir()
    (case_dir / "solver.log").write_text("run_aster\nFIN\n", encoding="utf-8")
    (case_dir / "result_table.txt").write_text(
        "# NODE DX DY DZ\n"
        " N1 1.0e-3 0.0 0.0\n"
        " N2 0.0 2.0e-3 0.0\n",
        encoding="utf-8",
    )
    parsed = parse_comm_result(case_dir)
    assert parsed.scalars["max_displacement_m"] == pytest.approx(2.0e-3)


# -- preCICE: governed native coupled window ---------------------------------


def test_prepare_native_window_writes_valid_native_config(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    receipt = prepare_native_window(
        {
            "participants": ["A", "B"],
            "coupling_dt_s": 1.0,
            "max_iterations": 5,
            "tolerance": 1.0e-6,
            "n_interface_points": 8,
        },
        case_dir,
    )
    assert receipt.files == ("precice-config.xml", "case.json", "run_precice.py")
    xml_text = (case_dir / "precice-config.xml").read_text(encoding="utf-8")
    report = validate_native_window_config(xml_text)
    assert report.passed is True
    assert "coupling-scheme:serial-implicit" in xml_text
    assert "relative-convergence-measure" in xml_text
    assert (case_dir / "run_precice.py").is_file()
    assert case_dir.name in receipt.case_id


def test_precice_run_script_is_allowlisted() -> None:
    assert run_script_path("run_precice.py").is_file()


def test_native_coupled_window_manifest_and_fail_closed(tmp_path: Path) -> None:
    manifest = get_participant("native-coupled-window")
    assert manifest.executable.run_script == "run_precice.py"
    assert manifest.executable.solver_id == "precice"

    probe = capabilities.probe_participant("native-coupled-window")
    if probe.state == "ready":
        pytest.skip("native preCICE is installed; fail-closed covered elsewhere")
    assert probe.state == "unavailable"


def _native_window_result(
    case_dir: Path,
    *,
    engine: str = "precice-native",
    completed: bool = True,
    residual: float = 1.0e-8,
    conservation: float = 1.0e-9,
) -> None:
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "engine": engine,
                "coupling_completed": completed,
                "converged": True,
                "interface_residual": residual,
                "conservation_error": conservation,
                "coupling_iterations": 7,
                "checkpoints": 3,
                "rollbacks": 1,
            }
        ),
        encoding="utf-8",
    )


def test_native_window_parse_and_validate(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    _native_window_result(case_dir)
    parsed = parse_native_window_result(case_dir)
    assert parsed.scalars["coupling_iterations"] == 7.0
    assert parsed.scalars["checkpoints"] == 3.0
    report = validate_native_window_result(
        dict(parsed.scalars), {"tolerance": 1.0e-6}
    )
    assert report.passed is True
    assert report.checks["converged"] is True


def test_native_window_rejects_analytic_engine(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    _native_window_result(case_dir, engine="analytic-transfer")
    with pytest.raises(ParticipantError) as failed:
        parse_native_window_result(case_dir)
    assert failed.value.code is NativeErrorCode.PARSER_FAILED


def test_native_window_nonconvergence_cannot_validate(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    _native_window_result(case_dir, residual=1.0e-1, conservation=1.0e-1)
    parsed = parse_native_window_result(case_dir)
    report = validate_native_window_result(dict(parsed.scalars), {"tolerance": 1.0e-6})
    assert report.passed is False
    assert report.checks["residual_within_tolerance"] is False
