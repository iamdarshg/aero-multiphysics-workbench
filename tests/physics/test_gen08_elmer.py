"""GEN 08: native Elmer thermal participant over governed meshes/materials.

These tests exercise the complete prepare/parse/validate path with golden
native output and a real GEN 05 solver-mapping export. ElmerSolver and Docker
are unavailable, so the native run itself stays capability-gated; the tests
prove that semantic material groups become Elmer bodies, missing thermal
properties and mesh groups fail closed, heat sources/BCs map correctly, the
parser extracts temperature and heat flow, energy closure gates validity, and
published interface field artifacts carry mesh and interface lineage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aeroworkbench_materials import MaterialDatabase
from aeroworkbench_mesh import (
    BoxSelector,
    InterfaceSpec,
    MaterialRegionSpec,
    MeshRequestMapping,
    MeshSpec,
    PatchSpec,
    ResolvedMeshRequest,
    SemanticMeshRequest,
    ZoneDeclaration,
    ZoneSpec,
    build_solver_exports,
)
from elmer.fields import read_field_artifact
from elmer.materials import map_material
from elmer.parser import parse_elmer_output, publish_case_fields, validate_elmer_result
from elmer.sif import parse_sif_result, prepare_sif, validate_sif_result
from participants.errors import NativeErrorCode, ParticipantError
from participants.lifecycle import JobState, NativeJobManager

_GEOMETRY_HASH = "a" * 64
_MESH_HASH = "b" * 64
_MATERIAL_ID = "aluminium-6061-t6"

_SOLVER_LOG = """\
ElmerSolver: Number of timesteps to be saved: 1
HeatSolve:  Steady state iteration:            1
HeatSolve:  Steady state iteration:            2
ElmerSolver: ALL DONE
"""


def _gen05_elmer_export(*, extra: bool = False) -> dict[str, object]:
    """Build an elmer solver mapping through the real GEN 05 export path."""

    zone_solid = ZoneSpec("duct-shell", "stationary", "solid", ("shell",))
    zone_fluid = ZoneSpec("flow-inlet", "stationary", "fluid", ("flow",))
    patches = (
        PatchSpec("inlet", "inlet", "fluid", ("flow",), BoxSelector(-1, -1, -1, 1, 1, 1)),
        PatchSpec("outlet", "outlet", "fluid", ("flow",), BoxSelector(-1, -1, -1, 1, 1, 1)),
        PatchSpec("duct-wall", "wall", "solid", ("shell",), BoxSelector(-1, -1, -1, 1, 1, 1)),
    )
    material = MaterialRegionSpec("duct-shell-material", _MATERIAL_ID, ("shell",), "solid")
    interface = InterfaceSpec(
        "shell-flow-cht",
        "cht_interface",
        "duct-shell",
        "flow-inlet",
        True,
        ("shell.region", "flow.inlet.region"),
    )
    spec_interfaces = [interface]
    mapping_interfaces = [
        (
            "shell-flow-cht",
            "cht_interface",
            "duct-shell",
            "flow-inlet",
            True,
            ("shell.region", "flow.inlet.region"),
        )
    ]
    mapping_materials = [("duct-shell-material", _MATERIAL_ID, ("shell.material",))]
    mapping_zones = [
        ("duct-shell", "stationary", "solid", ("shell.region",)),
        ("flow-inlet", "stationary", "fluid", ("flow.inlet.region",)),
    ]
    if extra:
        contact = InterfaceSpec(
            "shell-contact",
            "thermal_contact",
            "duct-shell",
            "flow-inlet",
            True,
            ("shell.contact",),
        )
        spec_interfaces.append(contact)
        mapping_interfaces.append(
            (
                "shell-contact",
                "thermal_contact",
                "duct-shell",
                "flow-inlet",
                True,
                ("shell.contact",),
            )
        )
        mapping_materials.append(("steel-region", "steel-structural", ("steel.region",)))
    spec = MeshSpec(
        "domain",
        3,
        4.0,
        1.0,
        8.0,
        (zone_solid, zone_fluid),
        patches,
        materials=(material,),
        interfaces=tuple(spec_interfaces),
    )
    request = SemanticMeshRequest(
        name="domain",
        geometry_hash=_GEOMETRY_HASH,
        topology_digest="d" * 64,
        dimension=3,
        base_size_mm=4.0,
        min_size_mm=1.0,
        max_size_mm=8.0,
        zones=(
            ZoneDeclaration("duct-shell", "stationary", "solid", ("shell.region",)),
            ZoneDeclaration("flow-inlet", "stationary", "fluid", ("flow.inlet.region",)),
        ),
    )
    mapping = MeshRequestMapping(
        zones=tuple(mapping_zones),
        patches=(
            ("inlet", "inlet", ("flow.inlet",)),
            ("outlet", "outlet", ("flow.outlet",)),
            ("duct-wall", "wall", ("flow.wall",)),
        ),
        interfaces=tuple(mapping_interfaces),
        materials=tuple(mapping_materials),
    )
    resolved = ResolvedMeshRequest(request=request, spec=spec, mapping=mapping)
    exports = build_solver_exports(resolved, mapping)
    elmer = next(export for export in exports if export.participant == "elmer")
    return elmer.canonical_payload()


# ``build_solver_exports`` produces the canonical elmer mapping consumed below.


def _write_msh(path: Path, names: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "$MeshFormat",
        "4.1 0 8",
        "$EndMeshFormat",
        "$PhysicalNames",
        str(len(names)),
    ]
    lines.extend(f'2 {index} "{name}"' for index, name in enumerate(names, start=1))
    lines.append("$EndPhysicalNames")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mesh_names(
    *, include_material_group: bool = True, extra: bool = False
) -> tuple[str, ...]:
    names = ["duct-shell", "flow-inlet", "inlet", "outlet", "duct-wall", "shell-flow-cht"]
    if include_material_group:
        names.append("material_duct-shell-material")
    if extra:
        names.extend(["shell-contact", "material_steel-region"])
    return tuple(names)


def _material_payload(*, drop: str | None = None) -> dict[str, object]:
    payload = MaterialDatabase.seeded().get_material(_MATERIAL_ID).canonical_payload()
    if drop is not None:
        del payload["properties"][drop]
    return payload


def _native_inputs(mesh_source: Path, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "model": "thermal",
        "analysis": "steady",
        "mesh_mapping": _gen05_elmer_export(),
        "mesh_file": "domain.msh",
        "mesh_source": str(mesh_source),
        "mesh_hash": _MESH_HASH,
        "geometry_hash": _GEOMETRY_HASH,
        "materials": {_MATERIAL_ID: _material_payload()},
        "heat_sources": [{"body": "duct-shell-material", "volumetric_w_m3": 1.0e5}],
        "fixed_temperature": [{"patch": "duct-wall", "temperature_k": 300.0}],
        "surface_heat_flux": [{"patch": "inlet", "heat_flux_w_m2": 1.0e4}],
        "convection": [
            {"patch": "outlet", "coefficient_w_m2_k": 25.0, "ambient_k": 293.15}
        ],
        "interface_exchange": [
            {"interface": "shell-flow-cht", "mode": "temperature", "value": 320.0}
        ],
        "energy_balance_tolerance": 1.0e-3,
        "ambient_k": 300.0,
    }
    base.update(overrides)
    return base


def _prepare(tmp_path: Path, **overrides: object) -> Path:
    mesh = tmp_path / "domain.msh"
    _write_msh(mesh, _mesh_names())
    case_dir = tmp_path / "case"
    prepare_sif(_native_inputs(mesh, **overrides), case_dir)
    return case_dir


def _write_native_output(
    case_dir: Path, *, energy_error: float = 1.0e-3, include_balance: bool = True
) -> None:
    (case_dir / "solver.log").write_text(_SOLVER_LOG, encoding="utf-8")
    rows = [
        "Temperature : max = 3.512000e+02 min = 3.000000e+02",
        "Temperature : mean = 3.200000e+02",
        "Heat Flux : max = 1.234500e+04 min = 0.000000e+00",
    ]
    if include_balance:
        rows.append(f"Energy Balance : error = {energy_error:.6e}")
    (case_dir / "result.dat").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (case_dir / "region_duct-shell-material.dat").write_text(
        "Temperature : max = 3.500000e+02 min = 3.100000e+02\n", encoding="utf-8"
    )
    (case_dir / "interface_shell-flow-cht.dat").write_text(
        "Temperature : max = 3.400000e+02 min = 3.200000e+02\n"
        "Temperature : flux = 4.200000e+01\n",
        encoding="utf-8",
    )


# -- A/B. prepare: bodies, materials, BCs ------------------------------------


def test_gen08_semantic_material_groups_become_elmer_bodies(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert manifest["native"] is True
    assert manifest["bodies"] == ["duct-shell-material"]
    assert manifest["bodyMaterials"] == [_MATERIAL_ID]
    assert manifest["materialNames"] == [_MATERIAL_ID]
    assert manifest["mesh"]["meshHash"] == _MESH_HASH
    sif = (case_dir / "case.sif").read_text(encoding="utf-8")
    assert "Body 1" in sif
    assert 'Name = "aluminium-6061-t6"' in sif
    assert "Material 1" in sif
    # Temperature-dependent conductivity must survive as an Elmer table.
    assert "Heat Conductivity = Variable Temperature" in sif
    assert "1.670000e+02" in sif and "1.860000e+02" in sif
    assert "Heat Capacity = 8.960000e+02" in sif
    assert "Density = 2.700000e+03" in sif


def test_gen08_heat_sources_and_boundary_conditions_map_correctly(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    sif = (case_dir / "case.sif").read_text(encoding="utf-8")
    assert "Body Force 1" in sif
    assert "Heat Source = 1.000000e+05" in sif
    assert 'Name = "fixed-temperature-duct-wall"' in sif
    assert "Temperature = 3.000000e+02" in sif
    assert 'Name = "heat-flux-inlet"' in sif
    assert "Heat Flux = 1.000000e+04" in sif
    assert 'Name = "convection-outlet"' in sif
    assert "Heat Transfer Coefficient = 2.500000e+01" in sif
    assert "External Temperature = 2.931500e+02" in sif
    assert 'Name = "interface-temperature-shell-flow-cht"' in sif
    assert "Temperature = 3.200000e+02" in sif
    assert sif.count("Target Boundaries(1)") >= 4


def test_gen08_transient_case_renders_transient_solver(tmp_path: Path) -> None:
    case_dir = _prepare(
        tmp_path,
        analysis="transient",
        time_step_s=1.0,
        end_time_s=10.0,
        output_intervals=2,
    )
    sif = (case_dir / "case.sif").read_text(encoding="utf-8")
    assert "Simulation Type = Transient" in sif
    assert "Timestep Sizes = 1.000000e+00" in sif
    assert "Timestep Intervals(1) = 10" in sif
    assert "Transient = True" in sif


def _seeded_payload(material_id: str) -> dict[str, object]:
    return MaterialDatabase.seeded().get_material(material_id).canonical_payload()


def test_gen08_multi_material_groups_become_distinct_bodies(tmp_path: Path) -> None:
    mesh = tmp_path / "domain.msh"
    _write_msh(mesh, _mesh_names(extra=True))
    inputs = _native_inputs(
        mesh,
        mesh_mapping=_gen05_elmer_export(extra=True),
        materials={
            _MATERIAL_ID: _material_payload(),
            "steel-structural": _seeded_payload("steel-structural"),
        },
        heat_sources=[
            {"body": "duct-shell-material", "volumetric_w_m3": 1.0e5},
            {"body": "steel-region", "volumetric_w_m3": 2.0e5},
        ],
    )
    case_dir = tmp_path / "case"
    prepare_sif(inputs, case_dir)
    manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert manifest["bodies"] == ["duct-shell-material", "steel-region"]
    assert manifest["bodyMaterials"] == [_MATERIAL_ID, "steel-structural"]
    sif = (case_dir / "case.sif").read_text(encoding="utf-8")
    assert "Body 2" in sif and "Material 2" in sif
    assert "Heat Source = 2.000000e+05" in sif


def test_gen08_interface_heat_flux_and_convection_modes(tmp_path: Path) -> None:
    mesh = tmp_path / "domain.msh"
    _write_msh(mesh, _mesh_names(extra=True))
    inputs = _native_inputs(
        mesh,
        mesh_mapping=_gen05_elmer_export(extra=True),
        materials={
            _MATERIAL_ID: _material_payload(),
            "steel-structural": _seeded_payload("steel-structural"),
        },
        interface_exchange=[
            {"interface": "shell-flow-cht", "mode": "heat_flux", "value": 5.0e3},
            {
                "interface": "shell-contact",
                "mode": "convection",
                "value": 0.0,
                "coefficient_w_m2_k": 100.0,
                "ambient_k": 290.0,
            },
        ],
    )
    case_dir = tmp_path / "case"
    prepare_sif(inputs, case_dir)
    sif = (case_dir / "case.sif").read_text(encoding="utf-8")
    assert 'Name = "interface-heat_flux-shell-flow-cht"' in sif
    assert "Heat Flux = 5.000000e+03" in sif
    assert 'Name = "interface-convection-shell-contact"' in sif
    assert "Heat Transfer Coefficient = 1.000000e+02" in sif


# -- B. material rejection ---------------------------------------------------


def test_gen08_missing_thermal_property_fails_closed(tmp_path: Path) -> None:
    mesh = tmp_path / "domain.msh"
    _write_msh(mesh, _mesh_names())
    with pytest.raises(ParticipantError) as failed:
        prepare_sif(
            _native_inputs(mesh, materials={_MATERIAL_ID: _material_payload(drop="heat_capacity")}),
            tmp_path / "case-a",
        )
    assert failed.value.code is NativeErrorCode.PREPARATION_FAILED
    assert "MATERIAL_PROPERTY_MISSING" in failed.value.detail
    assert "heat_capacity" in failed.value.detail

    with pytest.raises(ParticipantError) as absent:
        prepare_sif(_native_inputs(mesh, materials={}), tmp_path / "case-b")
    assert absent.value.code is NativeErrorCode.PREPARATION_FAILED
    assert "MATERIAL_PROPERTIES_MISSING" in absent.value.detail


def test_gen08_non_temperature_table_axis_is_rejected() -> None:
    payload = _material_payload()
    payload["properties"]["conductivity"] = {
        "kind": "frequency_dependent",
        "unit": "W/(m K)",
        "source": "test",
        "samples": [[50.0, 1.0], [100.0, 2.0]],
        "axisUnit": "Hz",
    }
    with pytest.raises(ParticipantError) as failed:
        map_material("bad-axis", payload)
    assert "MATERIAL_PROPERTY_UNSUPPORTED_AXIS" in failed.value.detail


def test_gen08_missing_semantic_mesh_group_fails_closed(tmp_path: Path) -> None:
    mesh = tmp_path / "domain.msh"
    _write_msh(mesh, _mesh_names(include_material_group=False))
    with pytest.raises(ParticipantError) as failed:
        prepare_sif(_native_inputs(mesh), tmp_path / "case")
    assert failed.value.code is NativeErrorCode.MESH_INVALID
    assert "MESH_GROUP_MISSING" in failed.value.detail


# -- C. parse + validity -----------------------------------------------------


def test_gen08_parser_extracts_temperature_region_and_heat_flow(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    _write_native_output(case_dir)
    parsed = parse_sif_result(case_dir)
    assert parsed.scalars["max_temperature_k"] == pytest.approx(351.2)
    assert parsed.scalars["min_temperature_k"] == pytest.approx(300.0)
    assert parsed.scalars["max_temperature_k_duct_shell_material"] == pytest.approx(350.0)
    assert parsed.scalars["interface_shell_flow_cht_heat_flow_w"] == pytest.approx(42.0)
    assert parsed.scalars["max_heat_flux_w_m2"] == pytest.approx(1.2345e4)
    assert parsed.scalars["converged"] == pytest.approx(1.0)
    assert parsed.units["max_temperature_k"] == "K"
    report = validate_sif_result(dict(parsed.scalars), _native_inputs(tmp_path / "domain.msh"))
    assert report.passed is True
    assert report.checks["energy_closure"] is True


def test_gen08_transient_history_is_parsed_when_present(tmp_path: Path) -> None:
    case_dir = _prepare(
        tmp_path, analysis="transient", time_step_s=1.0, end_time_s=3.0, output_intervals=1
    )
    _write_native_output(case_dir)
    (case_dir / "history.dat").write_text(
        "# time temperature_max temperature_min\n"
        "0.000000e+00 3.000000e+02 3.000000e+02\n"
        "1.000000e+00 3.200000e+02 3.000000e+02\n"
        "2.000000e+00 3.555000e+02 3.000000e+02\n",
        encoding="utf-8",
    )
    parsed = parse_sif_result(case_dir)
    assert parsed.scalars["transient_history_points"] == pytest.approx(3.0)
    assert parsed.scalars["peak_temperature_k"] == pytest.approx(355.5)
    assert parsed.scalars["final_max_temperature_k"] == pytest.approx(355.5)
    assert parsed.scalars["transient_end_time_s"] == pytest.approx(2.0)
    report = validate_sif_result(dict(parsed.scalars), _native_inputs(tmp_path / "domain.msh"))
    assert report.passed is True


def test_gen08_failed_energy_closure_cannot_validate(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    # 1e3 W error against a 1e5 W source is 1e-2 relative, above 1e-3.
    _write_native_output(case_dir, energy_error=1.0e3)
    parsed = parse_sif_result(case_dir)
    report = validate_sif_result(dict(parsed.scalars), _native_inputs(tmp_path / "domain.msh"))
    assert report.passed is False
    assert report.checks["energy_closure"] is False

    missing = _prepare(tmp_path / "missing-balance")
    _write_native_output(case_dir=missing, include_balance=False)
    parsed_missing = parse_elmer_output(missing)
    relative = parsed_missing.scalars["energy_balance_relative_error"]
    assert relative != relative  # NaN: a missing balance is not zero
    report_missing = validate_elmer_result(
        dict(parsed_missing.scalars), _native_inputs(tmp_path / "domain.msh")
    )
    assert report_missing.passed is False


def test_gen08_non_converged_native_result_cannot_validate(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    _write_native_output(case_dir)
    (case_dir / "solver.log").write_text(
        "ElmerSolver: ERROR in HeatSolve\nElmerSolver: ALL DONE\n", encoding="utf-8"
    )
    parsed = parse_elmer_output(case_dir)
    assert parsed.scalars["converged"] == 0.0
    report = validate_elmer_result(
        dict(parsed.scalars), _native_inputs(tmp_path / "domain.msh")
    )
    assert report.passed is False


# -- D. field artifacts ------------------------------------------------------


def test_gen08_field_artifact_carries_interface_and_mesh_lineage(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    _write_native_output(case_dir)
    parsed = parse_sif_result(case_dir)
    written = publish_case_fields(case_dir, parsed)
    assert written, "native interface values must produce field artifacts"

    temperature = read_field_artifact(case_dir / "fields" / "Temperature.json")
    assert temperature.field_name == "Temperature"
    assert temperature.unit == "K"
    assert temperature.source == "native_solver"
    assert temperature.mesh_hash == _MESH_HASH
    assert temperature.geometry_hash == _GEOMETRY_HASH
    assert temperature.interface_name == "shell-flow-cht"
    assert len(temperature.interface_hash) == 64
    assert {entry.label for entry in temperature.entries} == {"max", "min"}

    heat_flow = read_field_artifact(case_dir / "fields" / "Interface-Heat-Flow.json")
    assert heat_flow.unit == "W"
    assert heat_flow.entries[0].value == pytest.approx(42.0)

    heat_flux = read_field_artifact(case_dir / "fields" / "Heat-Flux.json")
    assert heat_flux.unit == "W/m^2"


def test_gen08_field_artifact_rejects_tampered_interface_hash(tmp_path: Path) -> None:
    case_dir = _prepare(tmp_path)
    _write_native_output(case_dir)
    parse_sif_result(case_dir)
    target = case_dir / "fields" / "Temperature.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["interface"]["interfaceHash"] = "0" * 64
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="FIELD_ARTIFACT_INTERFACE_HASH_MISMATCH"):
        read_field_artifact(target)


# -- E. native lifecycle fail-closed ----------------------------------------


def test_gen08_lifecycle_prepares_then_fails_closed_without_elmer(tmp_path: Path) -> None:
    from participants.capabilities import probe_participant

    if probe_participant("thermal-conduction").state == "ready":
        pytest.skip("ElmerSolver is installed; capability gating covered elsewhere")
    mesh = tmp_path / "domain.msh"
    _write_msh(mesh, _mesh_names())
    manager = NativeJobManager(tmp_path / "jobs")
    try:
        job_id = manager.submit("thermal-conduction", _native_inputs(mesh), deferred=True)
        assert manager.run(job_id) == JobState.FAILED.value
        status = manager.status(job_id)
        assert status["error_code"] == NativeErrorCode.CAPABILITY_UNAVAILABLE.value
        assert [event["state"] for event in manager.events(job_id)] == [
            JobState.QUEUED.value,
            JobState.PREPARING.value,
            JobState.FAILED.value,
        ]
        case_dir = tmp_path / "jobs" / f"case-{job_id[:12]}"
        assert (case_dir / "case.sif").is_file()
        assert (case_dir / "case.json").is_file()
    finally:
        manager.close()
