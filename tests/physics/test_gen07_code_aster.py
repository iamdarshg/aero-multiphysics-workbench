"""GEN 07: Code_Aster native structural participant for generated geometry/loads.

These tests exercise the governed prepare -> parse -> validate path with a
generic multi-region structural model: semantic volume/surface/node groups,
an isotropic and a full orthotropic material binding with a region orientation
frame, declared interfaces, and mapped loads (pressure from a coupling
interface, centrifugal through a declared rotation frame, nodal force, thermal).

Native Code_Aster is not installed in this environment, so the native execution
stays behind the capability probe and fails closed; the tests prove the full
non-native path (mesh/material ingestion, command generation, parsing, validity)
with golden files. No solver output is fabricated.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
from code_aster.adapter import prepare_structural_case
from code_aster.comm import parse_comm_result, prepare_comm, validate_comm_result
from participants.errors import NativeErrorCode, ParticipantError
from participants.lifecycle import NativeJobManager

GOLDEN_STATIC_SHA256 = "f1a750391008d209d8d8ba2e4822654b92e156588c728694e1f8f4682bef657e"
GOLDEN_STATIC = """\
DEBUT();

mesh = LIRE_MAILLAGE(FORMAT='MED', UNITE=20);

solid_groups = ('solid-core', 'solid-skin');

model = AFFE_MODELE(
    MAILLAGE=mesh,
    AFFE=_F(
        GROUP_MA=solid_groups,
        PHENOMENE='MECANIQUE',
        MODELISATION='3D',
    ),
);

mat_solid_core = DEFI_MATERIAU(
    ELAS=_F(
        E=2.100000e+11,
        NU=0.300000,
        RHO=7.850000e+03,
    ),
);

mat_solid_skin = DEFI_MATERIAU(
    ELAS_ORTH=_F(
        E_L=1.350000e+11,
        E_T=1.000000e+10,
        E_N=1.000000e+10,
        NU_LT=0.300000,
        NU_LN=0.300000,
        NU_TN=0.400000,
        G_LT=5.000000e+09,
        G_LN=5.000000e+09,
        G_TN=3.500000e+09,
        RHO=1.600000e+03,
    ),
);

fieldmat = AFFE_MATERIAU(
    MAILLAGE=mesh,
    AFFE=(
        _F(GROUP_MA='material:solid-core', MATER=(mat_solid_core,)),
        _F(GROUP_MA='material:solid-skin', MATER=(mat_solid_skin,)),
    ),
);

orientation = AFFE_CARA_ELEM(
    MODELE=model,
    ORIENTATION=(
        _F(GROUP_MA='material:solid-skin', ANGL_NAUT=(0.000000, 0.000000, 45.000000)),
    ),
);

char_clamp = AFFE_CHAR_MECA(
    MODELE=model,
    DDL_IMPO=_F(GROUP_MA='clamp-face', DX=0.000000e+00, DY=0.000000e+00, DZ=0.000000e+00),
);

char_tip = AFFE_CHAR_MECA(
    MODELE=model,
    DDL_IMPO=_F(GROUP_NO='tip-nodes', DZ=1.000000e-03),
);

load_pressure = AFFE_CHAR_MECA(
    MODELE=model,
    PRES=_F(GROUP_MA='load-face', PRES=2.500000e+05),
);

load_spin = AFFE_CHAR_MECA(
    MODELE=model,
    ROTATION=_F(
        GROUP_MA='material:solid-core',
        VITESSE=3.141590e+02,
        AXE=(0.000000, 0.000000, 1.000000),
        CENTRE=(0.000000, 0.000000, 0.000000),
    ),
);

load_axial = AFFE_CHAR_MECA(
    MODELE=model,
    FORCE_NODALE=_F(GROUP_NO='tip-nodes', FZ=1.000000e+03),
);

load_hot = AFFE_CHAR_MECA(
    MODELE=model,
    TEMP_CALCULEE=_F(GROUP_MA='material:solid-core', TEMP=3.500000e+02),
);

result = MECA_STATIQUE(
    MODELE=model,
    CHAM_MATER=fieldmat,
    EXCIT=(
        _F(CHARGE=char_clamp),
        _F(CHARGE=char_tip),
        _F(CHARGE=load_pressure),
        _F(CHARGE=load_spin),
        _F(CHARGE=load_axial),
        _F(CHARGE=load_hot),
    ),
);

IMPR_RESU(
    FORMAT='TABLEAU',
    UNITE=80,
    RESU=_F(RESULTAT=result),
);

FIN();
"""

GOVERNED_RESULT_TABLE = """\
# NODE DISPLACEMENT_M VON_MISES_PA STRAIN REACTION_N RESIDUAL
1 0.0 0.0 0.0 0.0 1.0e-09
2 0.00041 1.2e+07 3.0e-04 500.0 5.0e-10
3 0.00112 3.4e+07 8.0e-04 1000.0 2.0e-10
"""


def _governed_inputs(**overrides: object) -> dict[str, object]:
    """A generic two-region structural model driven by governed mesh semantics."""

    base: dict[str, object] = {
        "analysis": "static",
        "prestress": False,
        "mesh": {
            "file": "domain.med",
            "format": "MED",
            "volumes": ["solid-core", "solid-skin"],
            "surfaces": ["clamp-face", "load-face", "contact-slave", "contact-master"],
            "nodes": ["tip-nodes"],
            "material_groups": {
                "solid-core": "material:solid-core",
                "solid-skin": "material:solid-skin",
            },
            "interfaces": [
                {
                    "name": "fsi-lower",
                    "kind": "fsi_interface",
                    "zone_a": "solid-core",
                    "zone_b": "solid-skin",
                    "surface": "load-face",
                }
            ],
            "frames": {
                "spin-axis": {
                    "origin": [0.0, 0.0, 0.0],
                    "axis": [0.0, 0.0, 1.0],
                    "angles_deg": [0.0, 0.0, 0.0],
                },
                "ply-frame": {
                    "origin": [0.0, 0.0, 0.0],
                    "axis": [1.0, 0.0, 0.0],
                    "angles_deg": [0.0, 0.0, 45.0],
                },
            },
        },
        "materials": [
            {
                "region": "solid-core",
                "identity": "steel-structural@screening-r1",
                "symmetry": "isotropic",
                "youngs_modulus_pa": 2.1e11,
                "poisson_ratio": 0.3,
                "density_kg_m3": 7850.0,
            },
            {
                "region": "solid-skin",
                "identity": "carbon-epoxy-ud-ply@screening-r1",
                "symmetry": "orthotropic",
                "e_l_pa": 1.35e11,
                "e_t_pa": 1.0e10,
                "e_n_pa": 1.0e10,
                "nu_lt": 0.3,
                "nu_ln": 0.3,
                "nu_tn": 0.4,
                "g_lt_pa": 5.0e9,
                "g_ln_pa": 5.0e9,
                "g_tn_pa": 3.5e9,
                "density_kg_m3": 1600.0,
                "frame": "ply-frame",
            },
        ],
        "constraints": [
            {"name": "clamp", "mode": "fixed", "group": "clamp-face"},
            {
                "name": "tip",
                "mode": "kinematic",
                "group": "tip-nodes",
                "dofs": {"DZ": 0.001},
            },
        ],
        "loads": [
            {
                "name": "pressure",
                "kind": "pressure",
                "target": "fsi-lower",
                "pressure_pa": 250000.0,
            },
            {
                "name": "spin",
                "kind": "centrifugal",
                "target": "solid-core",
                "frame": "spin-axis",
                "omega_rad_s": 314.159,
            },
            {
                "name": "axial",
                "kind": "nodal_force",
                "target": "tip-nodes",
                "FZ": 1000.0,
            },
            {
                "name": "hot",
                "kind": "thermal",
                "target": "solid-core",
                "temperature_k": 350.0,
            },
        ],
        "n_modes": 4,
    }
    base.update(overrides)
    return base


def _write_governed_result(case_dir: Path, **meta: object) -> None:
    (case_dir / "solver.log").write_text("as_run EXIT_CODE=0\nFIN\n", encoding="utf-8")
    (case_dir / "result_table.txt").write_text(GOVERNED_RESULT_TABLE, encoding="utf-8")
    payload: dict[str, object] = {
        "converged": True,
        "residual_norm": 2.0e-10,
        "loads": {"total_force_n": 1000.0},
        "reactions": {"total_force_n": 1000.0},
        "requested_results": ["displacement", "stress", "reaction"],
    }
    payload.update(meta)
    import json

    (case_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")


# -- A. mesh/material ingestion ---------------------------------------------


def test_gen07_governed_prepare_ingests_mesh_and_materials(tmp_path: Path) -> None:
    receipt = prepare_comm(_governed_inputs(), tmp_path / "case")
    assert receipt.input_hash and len(receipt.input_hash) == 64
    assert receipt.files == ("case.comm", "case.export")
    text = (tmp_path / "case" / "case.comm").read_text(encoding="utf-8")
    assert "governed" in receipt.detail
    assert "GROUP_MA=solid_groups" in text
    assert text.count("DEFI_MATERIAU") == 2


def test_gen07_governed_prepare_carries_geometry_and_mesh_lineage(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    inputs["mesh"]["geometry_hash"] = "a" * 64  # type: ignore[index]
    inputs["mesh"]["mesh_hash"] = "b" * 64  # type: ignore[index]
    receipt = prepare_comm(inputs, tmp_path / "lineage")
    assert receipt.geometry_hash == "a" * 64
    assert receipt.mesh_hash == "b" * 64

    bad = _governed_inputs()
    bad["mesh"]["geometry_hash"] = "not-a-hash"  # type: ignore[index]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(bad, tmp_path / "bad")
    assert "geometry_hash" in failed.value.detail


def test_gen07_missing_semantic_group_fails_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs(
        constraints=[{"name": "clamp", "mode": "fixed", "group": "ghost-face"}]
    )
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    assert "UNKNOWN_CONSTRAINT_GROUP" in failed.value.detail


def test_gen07_missing_material_binding_fails_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    inputs["materials"] = [inputs["materials"][0]]  # type: ignore[index]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert "MISSING_MATERIAL_BINDING" in failed.value.detail


def test_gen07_unsupported_anisotropy_fails_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    inputs["materials"] = [  # type: ignore[index]
        inputs["materials"][0],  # type: ignore[index]
        {
            "region": "solid-skin",
            "identity": "layup@r1",
            "symmetry": "laminate",
            "e_l_pa": 1.0e11,
            "e_t_pa": 1.0e10,
            "density_kg_m3": 1600.0,
        },
    ]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert "UNSUPPORTED_ANISOTROPY" in failed.value.detail


def test_gen07_incomplete_orthotropic_constants_fail_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    ortho = dict(inputs["materials"][1])  # type: ignore[index]
    del ortho["g_tn_pa"]
    inputs["materials"] = [  # type: ignore[index]
        inputs["materials"][0],  # type: ignore[index]
        ortho,
    ]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert "INCOMPLETE_ORTHOTROPIC_CONSTANTS" in failed.value.detail


def test_gen07_undeclared_orientation_frame_fails_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    ortho = dict(inputs["materials"][1])  # type: ignore[index]
    ortho["frame"] = "ghost-frame"
    inputs["materials"] = [  # type: ignore[index]
        inputs["materials"][0],  # type: ignore[index]
        ortho,
    ]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert "UNDECLARED_ORIENTATION_FRAME" in failed.value.detail


# -- B/C. case and load generation -------------------------------------------


def test_gen07_static_comm_matches_golden_file(tmp_path: Path) -> None:
    prepare_comm(_governed_inputs(), tmp_path / "case")
    text = (tmp_path / "case" / "case.comm").read_text(encoding="utf-8")
    assert text == GOLDEN_STATIC
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == GOLDEN_STATIC_SHA256


def test_gen07_pressure_field_maps_to_declared_surface(tmp_path: Path) -> None:
    prepare_comm(_governed_inputs(), tmp_path / "case")
    text = (tmp_path / "case" / "case.comm").read_text(encoding="utf-8")
    # The coupling interface ``fsi-lower`` resolves to its declared surface.
    assert "PRES=_F(GROUP_MA='load-face', PRES=2.500000e+05)" in text


def test_gen07_centrifugal_load_uses_declared_rotation_frame(tmp_path: Path) -> None:
    prepare_comm(_governed_inputs(), tmp_path / "case")
    text = (tmp_path / "case" / "case.comm").read_text(encoding="utf-8")
    assert "AXE=(0.000000, 0.000000, 1.000000)" in text
    assert "CENTRE=(0.000000, 0.000000, 0.000000)" in text
    assert "GROUP_MA='material:solid-core'" in text


def test_gen07_undeclared_rotation_frame_fails_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    inputs["loads"] = [  # type: ignore[index]
        {
            "name": "spin",
            "kind": "centrifugal",
            "target": "solid-core",
            "frame": "ghost-frame",
            "omega_rad_s": 100.0,
        }
    ]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert "UNDECLARED_ROTATION_FRAME" in failed.value.detail


def test_gen07_orthotropic_material_reaches_generated_command_input(tmp_path: Path) -> None:
    prepare_comm(_governed_inputs(), tmp_path / "case")
    text = (tmp_path / "case" / "case.comm").read_text(encoding="utf-8")
    assert "ELAS_ORTH=_F(" in text
    assert "E_L=1.350000e+11" in text
    assert "G_TN=3.500000e+09" in text
    assert "ANGL_NAUT=(0.000000, 0.000000, 45.000000)" in text


def test_gen07_material_system_export_is_consumed_without_substitution(
    tmp_path: Path,
) -> None:
    from aeroworkbench_materials import MaterialDatabase, export_mechanical

    database = MaterialDatabase.seeded()
    steel = export_mechanical(database.get_material("steel-structural"))
    inputs = _governed_inputs()
    inputs["materials"] = [  # type: ignore[index]
        {
            "region": "solid-core",
            "identity": steel["identity"],
            "symmetry": steel["symmetry"],
            "youngs_modulus_pa": steel["youngs_modulus_pa"],
            "poisson_ratio": steel["poisson_ratio"],
            "density_kg_m3": steel["density_kg_m3"],
        },
        inputs["materials"][1],  # type: ignore[index]
    ]
    prepare_comm(inputs, tmp_path / "case")
    text = (tmp_path / "case" / "case.comm").read_text(encoding="utf-8")
    assert "E=2.100000e+11" in text

    # A UD ply export carries only in-plane constants; a 3D orthotropic deck
    # needs the full set, so binding it must fail closed rather than silently
    # dropping to an isotropic approximation.
    ply = export_mechanical(database.get_material("carbon-epoxy-ud-ply"))
    assert ply["symmetry"] == "orthotropic"
    incomplete = _governed_inputs()
    incomplete["materials"] = [  # type: ignore[index]
        inputs["materials"][0],  # type: ignore[index]
        {
            "region": "solid-skin",
            "identity": ply["identity"],
            "symmetry": ply["symmetry"],
            "youngs_modulus_pa": ply["youngs_modulus_pa"],
            "poisson_ratio": ply["poisson_ratio"],
            "density_kg_m3": ply["density_kg_m3"],
        },
    ]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(incomplete, tmp_path / "bad")
    assert "INCOMPLETE_ORTHOTROPIC_CONSTANTS" in failed.value.detail


def test_gen07_modal_prestressed_and_dynamic_decks(tmp_path: Path) -> None:
    modal = _governed_inputs(analysis="modal", prestress=True)
    prepare_comm(modal, tmp_path / "modal")
    modal_text = (tmp_path / "modal" / "case.comm").read_text(encoding="utf-8")
    assert "CALC_MODES(" in modal_text
    assert "PREC_CONTRAINTE=prestress_field," in modal_text
    assert "RESU=_F(RESULTAT=modes)" in modal_text

    spectrum = {
        "name": "spec",
        "kind": "harmonic_spectrum",
        "target": "fsi-lower",
        "frequencies_hz": [10.0, 100.0, 1000.0],
        "amplitude": 1.0,
    }
    harmonic = _governed_inputs(analysis="harmonic", prestress=True)
    harmonic["loads"] = [*harmonic["loads"], spectrum]  # type: ignore[index]
    prepare_comm(harmonic, tmp_path / "harmonic")
    harmonic_text = (tmp_path / "harmonic" / "case.comm").read_text(encoding="utf-8")
    assert "DYNA_LINE_HARM(" in harmonic_text
    assert "FREQ=_F(LIST_FREQ=(10.000000, 100.000000, 1000.000000,))" in harmonic_text

    transient = _governed_inputs(analysis="transient", prestress=True, time_end_s=0.01, n_steps=100)
    prepare_comm(transient, tmp_path / "transient")
    transient_text = (tmp_path / "transient" / "case.comm").read_text(encoding="utf-8")
    assert "DYNA_LINE_TRAN(" in transient_text
    assert "INTERVALLE=_F(JUSQU_A=1.000000e-02, NOMBRE=100)" in transient_text


def test_gen07_harmonic_requires_a_declared_spectrum(tmp_path: Path) -> None:
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(_governed_inputs(analysis="harmonic"), tmp_path / "bad")
    assert "HARMONIC_ANALYSIS_REQUIRES_SPECTRUM" in failed.value.detail


def test_gen07_contact_and_constraint_modes_are_explicit(tmp_path: Path) -> None:
    good = _governed_inputs(
        contact={"mode": "discrete", "slave": "contact-slave", "master": "contact-master"}
    )
    prepare_comm(good, tmp_path / "contact")
    text = (tmp_path / "contact" / "case.comm").read_text(encoding="utf-8")
    assert "DEFI_CONTACT(" in text
    assert "GROUP_MA_ESCL='contact-slave'" in text

    bad = _governed_inputs(
        contact={"mode": "continuous", "slave": "contact-slave", "master": "contact-master"}
    )
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(bad, tmp_path / "bad")
    assert "UNSUPPORTED_CONTACT_MODE" in failed.value.detail


def test_gen07_unknown_load_kind_fails_closed(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    inputs["loads"] = [{"name": "x", "kind": "magic", "target": "tip-nodes"}]  # type: ignore[index]
    with pytest.raises(ParticipantError) as failed:
        prepare_comm(inputs, tmp_path / "bad")
    assert "UNSUPPORTED_LOAD_KIND" in failed.value.detail


def test_gen07_legacy_scalar_path_is_preserved(tmp_path: Path) -> None:
    receipt = prepare_comm(
        {
            "analysis": "static",
            "youngs_modulus_pa": 2.1e11,
            "poisson_ratio": 0.3,
            "density_kg_m3": 7800.0,
            "applied_force_n": 1000.0,
            "mesh_file": "mesh.med",
        },
        tmp_path / "legacy",
    )
    assert "prestress=False" in receipt.detail
    text = (tmp_path / "legacy" / "case.comm").read_text(encoding="utf-8")
    assert "TOUT='OUI'" in text
    assert "ELAS=_F(E=2.100000e+11, NU=0.300000, RHO=7.800000e+03)" in text


# -- D/E. parser and validity -------------------------------------------------


def test_gen07_parser_reads_full_governed_result(tmp_path: Path) -> None:
    case_dir = tmp_path / "run"
    prepare_comm(_governed_inputs(), case_dir)
    _write_governed_result(case_dir)
    parsed = parse_comm_result(case_dir)
    assert parsed.scalars["max_displacement_m"] == pytest.approx(0.00112)
    assert parsed.scalars["max_von_mises_pa"] == pytest.approx(3.4e7)
    assert parsed.scalars["max_strain"] == pytest.approx(8.0e-4)
    assert parsed.scalars["max_reaction_n"] == pytest.approx(1000.0)
    assert parsed.scalars["solver_converged"] == 1.0
    assert validate_comm_result(dict(parsed.scalars), _governed_inputs()).passed is True


def test_gen07_parser_rejects_incomplete_or_missing_results(tmp_path: Path) -> None:
    case_dir = tmp_path / "run"
    prepare_comm(_governed_inputs(), case_dir)

    with pytest.raises(ParticipantError) as failed:
        parse_comm_result(case_dir)
    assert failed.value.code is NativeErrorCode.PARSER_FAILED

    (case_dir / "solver.log").write_text("as_run EXIT_CODE=0\nFIN\n", encoding="utf-8")
    (case_dir / "result_table.txt").write_text("# FOO BAR\n1 2\n", encoding="utf-8")
    with pytest.raises(ParticipantError) as failed:
        parse_comm_result(case_dir)
    assert "no known columns" in failed.value.detail

    (case_dir / "result_table.txt").write_text(
        "# NODE DISPLACEMENT_M\n1 0.5\n2\n", encoding="utf-8"
    )
    with pytest.raises(ParticipantError) as failed:
        parse_comm_result(case_dir)
    # A table with unlabelled/ragged rows is rejected; the exact reason may
    # come from either the golden or the tolerant native-table reader.
    assert "width mismatch" in failed.value.detail or "columns" in failed.value.detail


def test_gen07_trusted_result_requires_successful_validity_receipt(tmp_path: Path) -> None:
    inputs = _governed_inputs()
    trusted = tmp_path / "trusted"
    prepare_comm(inputs, trusted)
    _write_governed_result(trusted)
    parsed = parse_comm_result(trusted)
    assert validate_comm_result(dict(parsed.scalars), inputs).passed is True

    unconverged = tmp_path / "unconverged"
    prepare_comm(inputs, unconverged)
    _write_governed_result(unconverged, converged=False)
    parsed_bad = parse_comm_result(unconverged)
    report = validate_comm_result(dict(parsed_bad.scalars), inputs)
    assert report.passed is False
    assert report.checks["solver_converged"] is False

    missing = tmp_path / "missing"
    prepare_comm(inputs, missing)
    (missing / "solver.log").write_text("as_run EXIT_CODE=0\nFIN\n", encoding="utf-8")
    (missing / "result_table.txt").write_text(
        "# NODE DISPLACEMENT_M\n1 0.5\n2 0.6\n", encoding="utf-8"
    )
    import json

    (missing / "result.json").write_text(
        json.dumps({"converged": True, "requested_results": ["stress"]}),
        encoding="utf-8",
    )
    parsed_missing = parse_comm_result(missing)
    report = validate_comm_result(dict(parsed_missing.scalars), inputs)
    assert report.passed is False
    assert report.checks["requested_results_available"] is False


def test_gen07_parser_rejects_corrupt_solver_metadata(tmp_path: Path) -> None:
    case_dir = tmp_path / "run"
    prepare_comm(_governed_inputs(), case_dir)
    (case_dir / "solver.log").write_text("as_run EXIT_CODE=0\nFIN\n", encoding="utf-8")
    (case_dir / "result_table.txt").write_text(GOVERNED_RESULT_TABLE, encoding="utf-8")
    (case_dir / "result.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ParticipantError) as failed:
        parse_comm_result(case_dir)
    assert failed.value.code is NativeErrorCode.PARSER_FAILED


# -- adapter modes ------------------------------------------------------------


def test_gen07_case_selection_bounds_contact_and_constraint_modes() -> None:
    case = prepare_structural_case(analysis="modal", prestress=True)
    assert case.prestress is True
    assert case.contact_mode is None
    assert case.constraint_mode == "fixed"

    with_contact = prepare_structural_case(contact=True)
    assert with_contact.contact_mode == "discrete"

    with pytest.raises(ValueError, match="UNSUPPORTED_CONTACT_MODE"):
        prepare_structural_case(contact=True, contact_mode="continuous")
    with pytest.raises(ValueError, match="UNSUPPORTED_CONSTRAINT_MODE"):
        prepare_structural_case(constraint_mode="penalty")


# -- native lifecycle fails closed -------------------------------------------


def test_gen07_governed_job_fails_closed_without_native_aster(tmp_path: Path) -> None:
    manager = NativeJobManager(tmp_path / "jobs", timeout_s=30.0)
    try:
        job_id = manager.submit("structural-static", _governed_inputs(), deferred=False)
        deadline = time.monotonic() + 20.0
        status = manager.status(job_id)
        while status["state"] not in {"COMPLETED", "FAILED", "CANCELLED"}:
            if time.monotonic() > deadline:
                pytest.fail(f"job did not reach a terminal state: {status['state']}")
            time.sleep(0.05)
            status = manager.status(job_id)
        assert status["state"] == "FAILED"
        assert status["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
        assert status["input_hash"] and len(status["input_hash"]) == 64
    finally:
        manager.close()
