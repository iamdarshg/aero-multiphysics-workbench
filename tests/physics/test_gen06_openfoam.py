"""GEN 06: native OpenFOAM execution on generated geometry + moving interfaces.

Native OpenFOAM binaries are absent on this host, so execution fails closed at
the capability probe. These tests prove the full prepare/ingest/parse/validity
path instead: a governed mesh artifact produced by the real mesh participant is
ingested with lineage + role + interface validation, cases (including multi-zone
MRF and transient AMI) are generated from arbitrary semantic zones, golden
output is parsed into forces/torque/flow/histories, and nonconverged output can
never publish a trusted result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from openfoam.adapter import inspect_openfoam
from openfoam.case import (
    AmiPair,
    parse_case_result,
    prepare_case_files,
    validate_case_result,
)
from openfoam.mesh_ingest import ingest_governed_mesh
from participants.capabilities import probe_participant
from participants.envelope import ArtifactFile, EvidenceBundle, publish_result
from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, ValidityReport

_BASE_INPUTS: dict[str, object] = {
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

_MESH_INPUTS: dict[str, object] = {
    "n_rotating": 2,
    "base_size_mm": 6.0,
    "length_mm": 24.0,
    "inner_diameter_mm": 20.0,
    "outer_diameter_mm": 24.0,
    "zone_length_mm": 5.0,
    "zone_gap_mm": 3.0,
}

SIMPLEFOAM_LOG = """\
Time = 499

smoothSolver:  Solving for Ux, Initial residual = 0.0012, Final residual = 8.1e-06, No Iterations 2
GAMG:  Solving for p, Initial residual = 0.0021, Final residual = 9.3e-05, No Iterations 4
time step continuity errors : sum local = 2.1e-09, global = 4.4e-10, cumulative = 4.4e-10

Time = 500

smoothSolver:  Solving for Ux, Initial residual = 0.0011, Final residual = 7.9e-06, No Iterations 2
GAMG:  Solving for p, Initial residual = 0.0020, Final residual = 9.1e-05, No Iterations 4
time step continuity errors : sum local = 2.0e-09, global = 4.1e-10, cumulative = 4.1e-10

End
"""

PROBE_P = """\
# Probe 0 (-0.45 0 0)
# Probe 1 (0.45 0 0)
# Time
499                      (12.5 10.1)
500                      (12.4 10.0)
"""

FORCES_DAT = """\
# Force and moment coefficients
# CofR : (0 0 0)
# Time          forces(pressure viscous porous)    moment(pressure viscous porous)
0.5 (1.0 0.0 0.0) (0.2 0.0 0.0) (0 0 0) (0.01 0.0 0.0) (0.002 0.0 0.0) (0 0 0)
1.0 (1.1 0.1 0.0) (0.2 0.0 0.0) (0 0 0) (0.02 0.001 0.0) (0.003 0.0 0.0) (0 0 0)
"""

MASSFLOW_DAT = """\
# Time          sum(phi)
0.5             0.10
1.0             0.12
"""

AREA_P_DAT = """\
# Time          areaAverage(p)
0.5             101300
1.0             101325
"""


def _write_mesh_artifact(
    directory: Path,
    *,
    zones: tuple[tuple[str, str, str], ...],
    patches: tuple[tuple[str, str, str], ...],
    interfaces: tuple[tuple[str, str, str, str], ...] = (),
    geometry_hash: str = "a" * 64,
    mesh_bytes: bytes = b"$MeshFormat\n4.1 0 8\n$EndMeshFormat\n",
) -> str:
    """Write a governed mesh artifact (mesh bytes + semantic mapping)."""

    directory.mkdir(parents=True, exist_ok=True)
    mesh_path = directory / "domain.msh"
    mesh_path.write_bytes(mesh_bytes)
    mesh_hash = hashlib.sha256(mesh_bytes).hexdigest()
    payload = {
        "provenance": {
            "geometryHash": geometry_hash,
            "meshHash": mesh_hash,
            "topologyDigest": "b" * 64,
        },
        "exports": [
            {
                "participant": "openfoam",
                "format": "openfoam",
                "zones": [
                    {"name": name, "motion": motion, "domain": domain}
                    for name, motion, domain in zones
                ],
                "patches": [
                    {"name": name, "kind": kind, "nativeType": native}
                    for name, kind, native in patches
                ],
                "interfaces": [
                    {
                        "name": name,
                        "kind": kind,
                        "zoneA": zone_a,
                        "zoneB": zone_b,
                        "conformalRequested": True,
                    }
                    for name, kind, zone_a, zone_b in interfaces
                ],
                "materials": [],
            }
        ],
    }
    (directory / "mesh_mapping.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return mesh_hash


@pytest.fixture(scope="module")
def generated_mesh(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Real governed mesh artifact produced by the GEN 05 mesh participant."""

    from aeroworkbench_mesh import probe_gmsh

    if not probe_gmsh().available:
        pytest.skip("gmsh python API is required to generate a real mesh artifact")
    from participants.mesh_case import execute_mesh_case, prepare_mesh_case

    case_dir = tmp_path_factory.mktemp("gen06-real-mesh")
    inputs = dict(_MESH_INPUTS)
    prepare_mesh_case(inputs, case_dir)
    execute_mesh_case(inputs, case_dir)
    if not (case_dir / "domain.msh").is_file():
        pytest.skip("mesh participant did not produce domain.msh on this host")
    return case_dir


# -- A. governed mesh ingestion --------------------------------------------


def test_gen06_ingests_generated_mesh_with_lineage(generated_mesh: Path) -> None:
    mesh = ingest_governed_mesh(generated_mesh)
    assert len(mesh.mesh_hash) == 64
    assert len(mesh.geometry_hash) == 64
    assert mesh.mesh_hash == hashlib.sha256(mesh.mesh_path.read_bytes()).hexdigest()
    motions = {zone.motion for zone in mesh.zones}
    assert "rotating" in motions and "stationary" in motions
    kinds = {patch.kind for patch in mesh.patches}
    assert {"inlet", "outlet"} <= kinds
    assert any(zone.rotating for zone in mesh.zones)
    assert mesh.interfaces, "GEN 05 artifact must expose declared interfaces"
    assert mesh.mapping_hash == hashlib.sha256(
        (generated_mesh / "mesh_mapping.json").read_bytes()
    ).hexdigest()


def test_gen06_prepares_case_from_generated_mesh(generated_mesh: Path, tmp_path: Path) -> None:
    mesh = ingest_governed_mesh(generated_mesh)
    receipt = prepare_case_files(
        {
            **_BASE_INPUTS,
            "rotating_model": "MRF",
            "mesh_artifact_dir": str(generated_mesh),
            "geometry_hash": mesh.geometry_hash,
            "mesh_hash": mesh.mesh_hash,
            "rotation_rate_rpm": 3000.0,
        },
        tmp_path / "governed-mrf",
    )
    case_dir = tmp_path / "governed-mrf"
    velocity = (case_dir / "0" / "U").read_text(encoding="utf-8")
    for patch in mesh.patches:
        assert patch.name in velocity, patch.name
    mrf = (case_dir / "constant" / "MRFProperties").read_text(encoding="utf-8")
    for zone in mesh.moving_zones():
        assert f"cellZone        {zone.name};" in mrf
    assert receipt.geometry_hash == mesh.geometry_hash
    assert receipt.mesh_hash == mesh.mesh_hash
    manifest = json.loads((case_dir / "case_manifest.json").read_text(encoding="utf-8"))
    assert manifest["geometry_hash"] == mesh.geometry_hash
    assert manifest["mesh_hash"] == mesh.mesh_hash
    assert manifest["governed_mesh"] is True


def test_gen06_semantic_patch_mismatch_fails_before_execution(
    generated_mesh: Path, tmp_path: Path
) -> None:
    with pytest.raises(ParticipantError) as missing_role:
        prepare_case_files(
            {
                **_BASE_INPUTS,
                "mesh_artifact_dir": str(generated_mesh),
                "required_patch_kinds": ["does-not-exist"],
            },
            tmp_path / "bad-role",
        )
    assert missing_role.value.code is NativeErrorCode.MESH_INVALID
    assert not (tmp_path / "bad-role" / "system").exists()


def test_gen06_tampered_mesh_and_lineage_fail_closed(tmp_path: Path) -> None:
    directory = tmp_path / "tampered"
    _write_mesh_artifact(
        directory,
        zones=(("fluid", "fluid", "fluid"),),
        patches=(("inlet", "inlet", "patch"), ("outlet", "outlet", "patch")),
    )
    (directory / "domain.msh").write_bytes(b"$MeshFormat\nchanged\n")
    with pytest.raises(ParticipantError) as tampered:
        ingest_governed_mesh(directory)
    assert tampered.value.code is NativeErrorCode.MESH_INVALID

    fresh = tmp_path / "fresh"
    _write_mesh_artifact(
        fresh,
        zones=(("fluid", "fluid", "fluid"),),
        patches=(("inlet", "inlet", "patch"), ("outlet", "outlet", "patch")),
        geometry_hash="c" * 64,
    )
    with pytest.raises(ParticipantError) as lineage:
        ingest_governed_mesh(fresh, expected_geometry_hash="d" * 64)
    assert lineage.value.code is NativeErrorCode.MESH_INVALID


def test_gen06_interface_with_unknown_zone_fails_closed(tmp_path: Path) -> None:
    directory = tmp_path / "bad-interface"
    _write_mesh_artifact(
        directory,
        zones=(("rotor_a", "rotating", "fluid"), ("stat_b", "stationary", "fluid")),
        patches=(("inlet", "inlet", "patch"),),
        interfaces=(("sliding_x", "interface", "rotor_a", "ghost_zone"),),
    )
    with pytest.raises(ParticipantError) as failed:
        ingest_governed_mesh(directory)
    assert failed.value.code is NativeErrorCode.MESH_INVALID


# -- B. general case generation --------------------------------------------


@pytest.mark.parametrize("n_zones", [1, 2, 3, 4])
def test_gen06_multi_mrf_from_arbitrary_zone_count(tmp_path: Path, n_zones: int) -> None:
    zones = tuple(
        (f"rotating_zone_{index}", "rotating", "fluid") for index in range(n_zones)
    )
    directory = tmp_path / f"mesh-{n_zones}"
    _write_mesh_artifact(
        directory,
        zones=zones,
        patches=(("inlet", "inlet", "patch"), ("outlet", "outlet", "patch")),
    )
    case_dir = tmp_path / f"case-{n_zones}"
    prepare_case_files(
        {
            **_BASE_INPUTS,
            "rotating_model": "MRF",
            "mesh_artifact_dir": str(directory),
            "rotation_rates_rpm": {
                f"rotating_zone_{index}": 3000.0 + 100.0 * index
                for index in range(n_zones)
            },
        },
        case_dir,
    )
    text = (case_dir / "constant" / "MRFProperties").read_text(encoding="utf-8")
    for index in range(n_zones):
        assert f"MRF{index + 1}" in text
        assert f"cellZone        rotating_zone_{index};" in text
    assert f"MRF{n_zones + 1}" not in text
    omegas = [
        line.split()[-1].rstrip(";")
        for line in text.splitlines()
        if line.strip().startswith("omega")
    ]
    assert len(set(omegas)) == n_zones


def test_gen06_counter_rotation_and_axis_are_independent(tmp_path: Path) -> None:
    case_dir = tmp_path / "counter"
    prepare_case_files(
        {
            **_BASE_INPUTS,
            "rotating_model": "MRF",
            "rotating_zones": [
                {"name": "rotor_a", "rotation_rate_rpm": 5000.0},
                {"name": "rotor_b", "rotation_rate_rpm": -5000.0},
                {"name": "rotor_c", "rotation_rate_rpm": 2000.0, "axis": [1, 0, 0]},
            ],
        },
        case_dir,
    )
    text = (case_dir / "constant" / "MRFProperties").read_text(encoding="utf-8")
    assert "omega           constant 523.598775;" in text
    assert "omega           constant -523.598775;" in text
    assert "axis            (1 0 0);" in text


@pytest.mark.parametrize(
    ("compressibility", "steady", "thermal", "turbulence", "application"),
    [
        ("incompressible", True, "isothermal", "kOmegaSST", "simpleFoam"),
        ("incompressible", False, "isothermal", "laminar", "pimpleFoam"),
        ("compressible", True, "CHT", "kEpsilon", "rhoSimpleFoam"),
        ("compressible", False, "CHT", "kOmegaSST", "rhoPimpleFoam"),
    ],
)
def test_gen06_case_generation_matrix(
    tmp_path: Path,
    compressibility: str,
    steady: bool,
    thermal: str,
    turbulence: str,
    application: str,
) -> None:
    inputs: dict[str, object] = {
        **_BASE_INPUTS,
        "compressibility": compressibility,
        "steady": steady,
        "thermal_model": thermal,
        "turbulence": turbulence,
    }
    if thermal == "CHT":
        inputs["inlet_temperature_k"] = 320.0
    receipt = prepare_case_files(inputs, tmp_path / f"matrix-{application}-{turbulence}")
    assert application in receipt.detail
    manifest = json.loads(
        (tmp_path / f"matrix-{application}-{turbulence}" / "case_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["application"] == application


def test_gen06_unsupported_combinations_rejected(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as ami_steady:
        prepare_case_files({**_BASE_INPUTS, "rotating_model": "AMI"}, tmp_path / "ami")
    assert ami_steady.value.code is NativeErrorCode.PREPARATION_FAILED
    with pytest.raises(ParticipantError):
        prepare_case_files(
            {**_BASE_INPUTS, "result_requests": ["anti-gravity"]}, tmp_path / "out"
        )
    with pytest.raises(ParticipantError):
        prepare_case_files(
            {
                **_BASE_INPUTS,
                "rotating_model": "none",
                "rotating_zones": [{"name": "rotor", "rotation_rate_rpm": 10.0}],
            },
            tmp_path / "zones",
        )


# -- C. AMI pairing and transient motion ------------------------------------


def test_gen06_ami_pairs_derived_from_semantic_interfaces(tmp_path: Path) -> None:
    directory = tmp_path / "ami-mesh"
    _write_mesh_artifact(
        directory,
        zones=(
            ("rotor_zone_0", "rotating", "fluid"),
            ("stator_zone_0", "stationary", "fluid"),
        ),
        patches=(("inlet", "inlet", "patch"), ("outlet", "outlet", "patch")),
        interfaces=(("sliding_seal", "interface", "rotor_zone_0", "stator_zone_0"),),
    )
    case_dir = tmp_path / "ami-case"
    receipt = prepare_case_files(
        {
            **_BASE_INPUTS,
            "steady": False,
            "rotating_model": "AMI",
            "mesh_artifact_dir": str(directory),
            "rotation_rate_rpm": 4000.0,
            "result_requests": ["force", "torque"],
        },
        case_dir,
    )
    assert receipt.input_hash
    dynamic = (case_dir / "constant" / "dynamicMeshDict").read_text(encoding="utf-8")
    assert "rotor_zone_0" in dynamic
    assert "418.879" in dynamic
    velocity = (case_dir / "0" / "U").read_text(encoding="utf-8")
    assert "cyclicAMI" in velocity
    assert "neighbourPatch  sliding_sealShadow;" in velocity
    manifest = json.loads((case_dir / "case_manifest.json").read_text(encoding="utf-8"))
    assert manifest["interfaces"] == [
        {
            "name": "sliding_seal",
            "zone_a": "rotor_zone_0",
            "zone_b": "stator_zone_0",
            "master_patch": "sliding_seal",
            "slave_patch": "sliding_sealShadow",
        }
    ]


def test_gen06_ami_requires_pairing_or_governed_mesh(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as unpaired:
        prepare_case_files(
            {**_BASE_INPUTS, "steady": False, "rotating_model": "AMI"},
            tmp_path / "x",
        )
    assert unpaired.value.code is NativeErrorCode.PREPARATION_FAILED

    directory = tmp_path / "static-interface"
    _write_mesh_artifact(
        directory,
        zones=(("a", "stationary", "fluid"), ("b", "stationary", "fluid")),
        patches=(("inlet", "inlet", "patch"),),
        interfaces=(("contact_ab", "interface", "a", "b"),),
    )
    with pytest.raises(ParticipantError) as no_moving:
        ingest_governed_mesh(directory, required_zone_motions=("rotating",))
    assert no_moving.value.code is NativeErrorCode.MESH_INVALID


def test_gen06_explicit_ami_pairing_verified(tmp_path: Path) -> None:
    case_dir = tmp_path / "explicit-ami"
    prepare_case_files(
        {
            **_BASE_INPUTS,
            "steady": False,
            "rotating_model": "AMI",
            "rotating_zones": [{"name": "rotor", "rotation_rate_rpm": 1000.0}],
            "ami_pairs": [
                {
                    "name": "seal_pair",
                    "zone_a": "rotor",
                    "zone_b": "stator",
                    "master_patch": "seal_master",
                    "slave_patch": "seal_slave",
                }
            ],
        },
        case_dir,
    )
    velocity = (case_dir / "0" / "U").read_text(encoding="utf-8")
    assert "type            cyclicAMI;" in velocity
    assert "neighbourPatch  seal_slave;" in velocity
    assert "neighbourPatch  seal_master;" in velocity


# -- D. parser / outputs -----------------------------------------------------


def test_gen06_parser_extracts_forces_torque_flow_and_residuals(tmp_path: Path) -> None:
    case_dir = tmp_path / "parsed"
    prepare_case_files(
        {
            **_BASE_INPUTS,
            "result_requests": ["force", "torque", "mass_flow", "pressure"],
        },
        case_dir,
    )
    (case_dir / "solver.log").write_text(SIMPLEFOAM_LOG, encoding="utf-8")
    probe_dir = case_dir / "postProcessing" / "probes" / "500"
    probe_dir.mkdir(parents=True)
    (probe_dir / "p").write_text(PROBE_P, encoding="utf-8")
    forces = case_dir / "postProcessing" / "forces_walls" / "1" / "forces.dat"
    forces.parent.mkdir(parents=True)
    forces.write_text(FORCES_DAT, encoding="utf-8")
    mass = case_dir / "postProcessing" / "massFlow_inlet" / "1" / "surfaceFieldValue.dat"
    mass.parent.mkdir(parents=True)
    mass.write_text(MASSFLOW_DAT, encoding="utf-8")
    area = case_dir / "postProcessing" / "areaAverage_p_outlet" / "1" / "surfaceFieldValue.dat"
    area.parent.mkdir(parents=True)
    area.write_text(AREA_P_DAT, encoding="utf-8")

    control = (case_dir / "system" / "controlDict").read_text(encoding="utf-8")
    assert "forces_walls" in control and "massFlow_inlet" in control
    parsed = parse_case_result(case_dir)
    assert parsed.scalars["force_walls_x"] == pytest.approx(1.3)
    assert parsed.scalars["force_walls_y"] == pytest.approx(0.1)
    assert parsed.scalars["torque_walls_n_m"] == pytest.approx((0.023**2 + 0.001**2) ** 0.5)
    assert parsed.scalars["mass_flow_inlet"] == pytest.approx(0.12)
    assert parsed.scalars["area_average_p_outlet"] == pytest.approx(101325.0)
    assert parsed.scalars["residual_p"] == pytest.approx(9.1e-05)
    assert parsed.scalars["continuity_error"] == pytest.approx(4.1e-10)
    assert validate_case_result(dict(parsed.scalars), {"result_requests": ["force"]}).checks[
        "force_extracted"
    ] is True
    histories = json.loads((case_dir / "histories.json").read_text(encoding="utf-8"))
    assert histories["histories"]["forces_walls"]["source_patch"] == "walls"


def test_gen06_nonconverged_cannot_publish_trusted_result(tmp_path: Path) -> None:
    case_dir = tmp_path / "truncated"
    prepare_case_files(dict(_BASE_INPUTS), case_dir)
    (case_dir / "solver.log").write_text("Time = 1\nEnd\n", encoding="utf-8")
    with pytest.raises(ParticipantError) as no_residual:
        parse_case_result(case_dir)
    assert no_residual.value.code is NativeErrorCode.PARSER_FAILED

    converged = validate_case_result(
        {
            "solver_completed": 1.0,
            "continuity_error": 1e-9,
            "residual_Ux": 5e-06,
            "residual_p": 8e-05,
        },
        {},
    )
    assert converged.passed is True
    diverged = validate_case_result(
        {"solver_completed": 1.0, "continuity_error": 1e-2, "residual_Ux": 2.0},
        {},
    )
    assert diverged.passed is False

    parse = ParseReceipt(
        participant_id="openfoam",
        parser="openfoam.case:parse_case_result",
        scalars={"residual_p": 8e-05},
        units={"residual_p": "dimensionless"},
    )
    evidence = EvidenceBundle(
        capability_state="ready",
        capability_detail="native OpenFOAM",
        solver_name="openfoam",
        solver_version="2312",
        input_hash="a" * 64,
        run_id="run-1",
        process_state="completed",
        exit_code=0,
        execution_mode="subprocess",
        stdout_sha256="b" * 64,
        stderr_sha256="c" * 64,
        parser_name="openfoam.case:parse_case_result",
        output_files=(ArtifactFile(name="result.json", sha256="d" * 64, bytes=1),),
        participant_id="openfoam",
        manifest_version="2",
        validity_passed=False,
        validity_detail="did not converge",
    )
    with pytest.raises(ParticipantError) as refused:
        publish_result(
            evidence,
            parse=parse,
            validity=ValidityReport(participant_id="openfoam", passed=False, detail="no"),
            fidelity="rans-steady",
            provenance_id="prov-1",
        )
    assert refused.value.code is NativeErrorCode.RESULT_INVALID


def test_gen06_field_artifacts_retain_mesh_lineage(
    generated_mesh: Path, tmp_path: Path
) -> None:
    mesh = ingest_governed_mesh(generated_mesh)
    case_dir = tmp_path / "lineage-case"
    prepare_case_files(
        {
            **_BASE_INPUTS,
            "rotating_model": "MRF",
            "mesh_artifact_dir": str(generated_mesh),
            "rotation_rate_rpm": 2000.0,
            "result_requests": [],
        },
        case_dir,
    )
    (case_dir / "solver.log").write_text(SIMPLEFOAM_LOG, encoding="utf-8")
    parse_case_result(case_dir)
    for name in ("convergence_receipt.json", "histories.json", "field_refs.json"):
        payload = json.loads((case_dir / name).read_text(encoding="utf-8"))
        assert payload["geometry_hash"] == mesh.geometry_hash, name
        assert payload["mesh_hash"] == mesh.mesh_hash, name
    refs = json.loads((case_dir / "field_refs.json").read_text(encoding="utf-8"))
    assert any(entry["time"] == "0" and "U" in entry["fields"] for entry in refs["times"])


# -- E. transient validity policy -------------------------------------------


def test_gen06_transient_validity_requires_coverage_and_periodicity() -> None:
    short = validate_case_result(
        {
            "solver_completed": 1.0,
            "continuity_error": 1e-6,
            "residual_Ux": 1e-4,
            "simulation_time_s": 0.2,
        },
        {"steady": False, "end_time": 1.0},
    )
    assert short.passed is False
    assert short.checks["time_coverage"] is False
    covered = validate_case_result(
        {
            "solver_completed": 1.0,
            "continuity_error": 1e-6,
            "residual_Ux": 1e-4,
            "simulation_time_s": 1.0,
            "periodicity_error": 2e-4,
        },
        {"steady": False, "end_time": 1.0, "convergence_policy": "periodic"},
    )
    assert covered.passed is True
    not_periodic = validate_case_result(
        {
            "solver_completed": 1.0,
            "continuity_error": 1e-6,
            "residual_Ux": 1e-4,
            "simulation_time_s": 1.0,
            "periodicity_error": 0.5,
        },
        {"steady": False, "end_time": 1.0, "convergence_policy": "periodic"},
    )
    assert not_periodic.passed is False


# -- F. capability fail-closed ----------------------------------------------


def test_gen06_native_openfoam_fails_closed() -> None:
    probe = probe_participant("rotating-flow-mrf")
    if probe.state == "ready":  # pragma: no cover - host-dependent
        pytest.skip("native OpenFOAM present; fail-closed path not observable")
    assert probe.state == "unavailable"
    missing = inspect_openfoam("definitely-not-openfoam")
    assert missing.state == "unavailable"


def test_gen06_ami_pair_dataclass_is_typed(tmp_path: Path) -> None:
    pair = AmiPair("seal", "rotor", "stator", "seal", "sealShadow")
    assert pair.master_patch == "seal"
    with pytest.raises(ParticipantError):
        prepare_case_files(
            {
                **_BASE_INPUTS,
                "steady": False,
                "rotating_model": "AMI",
                "rotating_zones": [{"name": "rotor", "rotation_rate_rpm": 100.0}],
                "ami_pairs": [],
            },
            tmp_path / "empty-pairs",
        )
