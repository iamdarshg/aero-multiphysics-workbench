"""Generic multiphysics substrate acceptance: no hard-coded application.

The generic facilities (parametric CAD, semantic topology, materials,
interchange, meshing, morph policy) must represent an arbitrary ducted
system with a *configurable* number of rotating regions. Rotating-region
counts are parameters here, never core assumptions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from aeroworkbench_geometry import (
    ParameterDef,
    ParameterSet,
    ParametricModel,
    build_duct_system,
    fluid_zone_names,
    make_edf_geometry,
    rotating_zone_names,
)
from aeroworkbench_geometry.builder import live_shapes
from aeroworkbench_geometry.parametric import built_model_digest, export_artifacts
from aeroworkbench_materials import (
    LaminateRevision,
    MaterialAssignmentSet,
    MaterialDatabase,
    Ply,
    PlyMaterialError,
    RegionAssignment,
    assignment_digest,
    effective_orthotropic,
    export_assignment_set,
    material_digest,
)
from aeroworkbench_mesh import (
    BoxSelector,
    MeshSpec,
    PatchSpec,
    UpdatePolicy,
    ZoneSpec,
    build_native_mesh,
    decide_update_strategy,
    duct_mesh_spec,
    morph_affine,
    probe_gmsh,
)
from aeroworkbench_semantics import (
    TopologyEntity,
    TopologyModel,
    reconcile_topology,
    topology_from_components,
)
from freecad.adapter import convert_cad, export_fcstd, read_fcstd, step_roundtrip

COMPACT = {
    "outer_diameter_mm": 60.0,
    "inner_diameter_mm": 54.0,
    "length_mm": 48.0,
    "hub_diameter_mm": 16.0,
    "zone_length_mm": 10.0,
    "zone_gap_mm": 6.0,
}

BASE_SIZE_MM = 8.0


def _dims_for(n_rotating: int) -> dict[str, float]:
    dims = dict(COMPACT)
    span = n_rotating * dims["zone_length_mm"] + (n_rotating - 1) * dims["zone_gap_mm"]
    dims["length_mm"] = span + 28.0
    return dims


def _topology_for(n_rotating: int, face_map: dict[str, tuple[str, ...]]) -> TopologyModel:
    assignments: list[tuple[str, str, str, str]] = [
        ("duct.shell", "solid_region", "duct", "duct"),
        ("flow.inlet", "inlet", "inlet", "fluid_inlet"),
        ("flow.outlet", "outlet", "outlet", "fluid_outlet"),
        ("flow.wall", "wall", "duct-wall", "fluid_inlet"),
    ]
    for index in range(n_rotating):
        assignments.append(
            (f"rotor.{index}", "rotating_region", f"rotor-zone-{index}",
             f"rotor_zone_{index}")
        )
        assignments.append(
            (f"rotor.{index}.fsi", "fsi_interface", f"rotor-zone-{index}",
             f"rotor_zone_{index}")
        )
        if index < n_rotating - 1:
            assignments.append(
                (f"stator.{index}", "stationary_region", f"stator-zone-{index}",
                 f"stator_zone_{index}")
            )
            assignments.append(
                (f"stator.{index}.cht", "cht_interface", f"stator-zone-{index}",
                 f"stator_zone_{index}")
            )
    assignments.append(("shaft.main", "shaft", "shaft", "solid_0"))
    assignments.append(("duct.material", "material_assignment", "duct", "duct"))
    return topology_from_components(tuple(assignments), face_map)  # type: ignore[arg-type]


@pytest.mark.parametrize("n_rotating", [1, 2, 4])
def test_generic_system_represents_arbitrary_rotating_counts(n_rotating: int) -> None:
    model = build_duct_system(n_rotating=n_rotating, n_solids=2, **_dims_for(n_rotating))
    built = model.build()
    names = {component.name for component in built.components}
    assert {f"rotor_zone_{i}" for i in range(n_rotating)} <= names
    assert {f"stator_zone_{i}" for i in range(n_rotating - 1)} <= names
    assert {"duct", "fluid_inlet", "fluid_outlet", "solid_0", "solid_1"} <= names

    face_map = {
        component.name: component.face_fingerprints for component in built.components
    }
    topology = _topology_for(n_rotating, face_map)
    assert len(topology.of_kind("rotating_region")) == n_rotating
    assert len(topology.of_kind("fsi_interface")) == n_rotating
    report = reconcile_topology(topology, topology)
    assert report.valid is True
    assert report.reason == "TOPOLOGY_PRESERVED"
    assert len(report.preserved) == len(topology.entities)


def test_topology_guards_fail_closed() -> None:
    model = build_duct_system(n_rotating=2, n_solids=1, **COMPACT)
    built = model.build()
    face_map = {
        component.name: component.face_fingerprints for component in built.components
    }
    previous = _topology_for(2, face_map)
    # Missing entity: drop one rotor.
    current = TopologyModel(
        tuple(entity for entity in previous.entities
              if entity.semantic_key != "rotor.1")
    )
    report = reconcile_topology(previous, current)
    assert report.valid is False
    assert report.missing == ("rotor.1",)
    assert report.requires_remesh is True
    # Split identity: alter a fingerprint beyond tolerance.
    altered = tuple(
        type(entity)(
            semantic_key=entity.semantic_key,
            kind=entity.kind,
            region=entity.region,
            fingerprint=entity.fingerprint + "|EXTRA",
            frame=entity.frame,
            material_identity=entity.material_identity,
            detail=entity.detail,
        )
        if entity.semantic_key == "rotor.0" else entity
        for entity in previous.entities
    )
    changed_report = reconcile_topology(previous, TopologyModel(altered))
    assert changed_report.requires_remesh is True
    assert any(item.change == "split" for item in changed_report.changed)
    # Ambiguous mapping: duplicate semantic key must fail closed.
    with pytest.raises(ValueError, match="DUPLICATE_SEMANTIC_KEY"):
        TopologyModel(previous.entities + (previous.entities[0],))


def test_materials_and_composites_are_real() -> None:
    database = MaterialDatabase.seeded()
    assert set(database.inventory()) >= {
        "aluminium-6061-t6", "steel-structural", "copper-etp",
        "carbon-epoxy-ud-ply", "ndfeb-n42",
    }
    aluminium = database.get_material("aluminium-6061-t6")
    assert aluminium.evaluate("conductivity", temperature_k=300.0) == pytest.approx(
        167.96, abs=0.5
    )
    with pytest.raises(ValueError, match="OUT_OF_VALIDITY_RANGE"):
        aluminium.evaluate("conductivity", temperature_k=900.0)
    copper = database.get_material("copper-etp")
    assert copper.evaluate("resistivity", temperature_k=373.0) == pytest.approx(
        2.14e-8, rel=0.05
    )
    magnet = database.get_material("ndfeb-n42")
    assert magnet.evaluate("remanence") == pytest.approx(1.30)
    assert magnet.evaluate("core_loss", frequency_hz=400.0) == pytest.approx(6.5)

    ply = database.get_material("carbon-epoxy-ud-ply")
    layup = LaminateRevision(
        "screening-quad", "r1",
        (Ply(ply, 0.0, 0.000125), Ply(ply, 90.0, 0.000125),
         Ply(ply, 90.0, 0.000125), Ply(ply, 0.0, 0.000125)),
    )
    homogenized = effective_orthotropic(layup)
    assert homogenized.symmetry == "orthotropic"
    assert homogenized.evaluate("youngs_modulus") > homogenized.evaluate(
        "youngs_modulus_transverse"
    ) / 10.0
    # Unsymmetric layups and isotropic plies fail closed, never substituted.
    with pytest.raises(PlyMaterialError, match="UNSYMMETRIC"):
        effective_orthotropic(
            LaminateRevision("bad", "r1", (Ply(ply, 0.0, 0.000125),
                                           Ply(ply, 90.0, 0.000125)))
        )
    with pytest.raises(PlyMaterialError, match="ORTHOTROPIC"):
        Ply(aluminium, 0.0, 0.001)

    bound = MaterialAssignmentSet((
        RegionAssignment("duct", "aluminium-6061-t6@screening-r1",
                         database.material_digest("aluminium-6061-t6")),
        RegionAssignment("shaft", "steel-structural@screening-r1",
                         database.material_digest("steel-structural")),
    ))
    exported = export_assignment_set(bound, database, temperature_k=300.0)
    assert exported["duct"]["density_kg_m3"] == pytest.approx(2700.0)
    changed = MaterialAssignmentSet((
        RegionAssignment("duct", "steel-structural@screening-r1",
                         database.material_digest("steel-structural")),
        RegionAssignment("shaft", "steel-structural@screening-r1",
                         database.material_digest("steel-structural")),
    ))
    assert assignment_digest(changed) != assignment_digest(bound)
    assert material_digest(aluminium) == database.material_digest("aluminium-6061-t6")


def test_native_cad_artifacts_are_hashed(tmp_path: Path) -> None:
    first = build_duct_system(n_rotating=2, n_solids=1, **COMPACT).build()
    second = build_duct_system(n_rotating=2, n_solids=1, **COMPACT).build()
    assert first.shape_hash == second.shape_hash
    assert built_model_digest(first) == built_model_digest(second)
    assert first.parameter_hash == second.parameter_hash
    assert len(first.components) == 2 + (2 - 1) + 2 + 1 + 1  # rotors+stators+in/out+duct+solid

    records = export_artifacts(live_shapes(first), first.kernel, tmp_path, basename="duct")
    by_format: dict[str, list[str]] = {}
    for artifact in records["artifacts"]:
        by_format.setdefault(artifact["format"], []).append(artifact["path"])
    assert set(by_format) >= {"step", "brep", "stl"}
    for path in by_format["step"] + by_format["brep"]:
        assert Path(path).stat().st_size > 1000
    assert records["kernel"]["cadquery"] is not None


def test_interchange_roundtrip_is_real(tmp_path: Path) -> None:
    built = build_duct_system(n_rotating=1, n_solids=1, **COMPACT).build()
    records = export_artifacts(
        live_shapes(built), built.kernel, tmp_path / "cad", basename="duct",
        export_stl=False,
    )
    breps = {a["component"]: Path(a["path"]) for a in records["artifacts"]
             if a["format"] == "brep" and a["component"] != "assembly"}
    steps = {a["component"]: Path(a["path"]) for a in records["artifacts"]
             if a["format"] == "step" and a["component"] != "assembly"}
    converted = convert_cad(breps["duct"], tmp_path / "duct.step")
    assert converted.state == "completed"
    assert converted.product_sha256 is not None
    fcstd = export_fcstd(
        {"duct": breps["duct"], "solid_0": breps["solid_0"]},
        tmp_path / "assembly.FCStd",
    )
    assert fcstd.state == "completed"
    info = read_fcstd(tmp_path / "assembly.FCStd", extract_to=tmp_path / "parts")
    assert set(info["objects"]) == {"duct", "solid_0"}
    assert len(info["extracted"]) == 2
    roundtrip = step_roundtrip(steps["duct"], tmp_path / "rt")
    assert roundtrip.state == "completed"
    assert roundtrip.faces_before == roundtrip.faces_after
    assert roundtrip.faces_before and roundtrip.faces_before > 0


@pytest.mark.parametrize("n_rotating", [1, 2])
def test_native_fluid_and_structural_meshes(tmp_path: Path, n_rotating: int) -> None:
    assert probe_gmsh().available, "gmsh python API is required for native meshing"
    built = build_duct_system(n_rotating=n_rotating, n_solids=1, **COMPACT).build()
    records = export_artifacts(
        live_shapes(built), built.kernel, tmp_path / "cad",
        basename=f"duct-R{n_rotating}", export_stl=False,
    )
    files = {a["component"]: Path(a["path"]) for a in records["artifacts"]
             if a["format"] == "step" and a["component"] != "assembly"}

    rotating = rotating_zone_names(n_rotating)
    stationary = ("fluid_inlet", "fluid_outlet") + tuple(
        f"stator_zone_{i}" for i in range(n_rotating - 1)
    )
    fluid = duct_mesh_spec(
        name=f"fluid-R{n_rotating}", rotating=rotating, stationary_fluid=stationary,
        solids=(), length_mm=COMPACT["length_mm"],
        inner_diameter_mm=COMPACT["inner_diameter_mm"], base_size_mm=BASE_SIZE_MM,
    )
    fluid_receipt = build_native_mesh(
        fluid, files, built.shape_hash, tmp_path / "fluid",
        mesh_filename=f"fluid-R{n_rotating}.msh",
    )
    assert fluid_receipt.state == "completed", fluid_receipt.detail
    rotating_groups = [name for name in fluid_receipt.physical_groups
                       if name.startswith("zone:rot-")]
    assert len(rotating_groups) == n_rotating
    assert fluid_receipt.interfaces, "expected conformal interface groups"
    quality = fluid_receipt.quality
    assert quality is not None and quality.inverted_count == 0
    assert quality.min_sicn is not None
    assert fluid_receipt.geometry_hash == built.shape_hash
    assert fluid_receipt.topology_fingerprint is not None
    assert fluid_receipt.mesh_path is not None
    assert Path(fluid_receipt.mesh_path).stat().st_size > 10000

    structural = MeshSpec(
        name=f"structure-R{n_rotating}", dimension=3,
        base_size_mm=BASE_SIZE_MM, min_size_mm=BASE_SIZE_MM / 4.0,
        max_size_mm=BASE_SIZE_MM * 2.0,
        zones=(
            ZoneSpec("duct-shell", "stationary", "solid", ("duct",)),
            ZoneSpec("shaft", "stationary", "solid", ("solid_0",)),
        ),
        patches=(
            PatchSpec("clamp", "mechanical_constraint", "solid", ("duct", "solid_0"),
                      BoxSelector(-40, -40, -30, 40, 40, 30)),
        ),
    )
    structure_receipt = build_native_mesh(
        structural, files, built.shape_hash, tmp_path / "structure",
        mesh_filename=f"structure-R{n_rotating}.msh",
    )
    assert structure_receipt.state == "completed", structure_receipt.detail
    assert structure_receipt.quality is not None
    assert structure_receipt.quality.inverted_count == 0
    assert structure_receipt.mesh_hash != fluid_receipt.mesh_hash


def test_morph_and_remesh_policy(tmp_path: Path) -> None:
    assert probe_gmsh().available
    built = build_duct_system(n_rotating=1, n_solids=1, **COMPACT).build()
    records = export_artifacts(
        live_shapes(built), built.kernel, tmp_path / "cad", basename="duct",
        export_stl=False,
    )
    files = {a["component"]: Path(a["path"]) for a in records["artifacts"]
             if a["format"] == "step" and a["component"] != "assembly"}
    spec = duct_mesh_spec(
        name="fluid-morph", rotating=("rotor_zone_0",),
        stationary_fluid=("fluid_inlet", "fluid_outlet"), solids=(),
        length_mm=COMPACT["length_mm"],
        inner_diameter_mm=COMPACT["inner_diameter_mm"], base_size_mm=BASE_SIZE_MM,
    )
    receipt = build_native_mesh(spec, files, built.shape_hash, tmp_path)
    assert receipt.state == "completed", receipt.detail
    assert receipt.mesh_path is not None
    mesh_path = Path(receipt.mesh_path)

    face_map = {
        component.name: component.face_fingerprints for component in built.components
    }
    topology = _topology_for(1, face_map)
    decision, reason = decide_update_strategy(
        reconcile_topology(topology, topology),
        max_param_shift_mm=0.2, policy=UpdatePolicy(),
    )
    assert decision == "morph_candidate", reason
    morphed = morph_affine(mesh_path, tmp_path / "morphed.msh", scale=1.005)
    assert morphed.state == "morphed", morphed.detail
    assert morphed.mesh_hash != receipt.mesh_hash
    assert morphed.max_displacement_mm > 0.0

    missing = TopologyModel(
        tuple(entity for entity in topology.entities
              if entity.semantic_key != "rotor.0")
    )
    decision, reason = decide_update_strategy(
        reconcile_topology(topology, missing),
        max_param_shift_mm=0.1, policy=UpdatePolicy(),
    )
    assert decision == "remesh_required", reason
    decision, _ = decide_update_strategy(
        reconcile_topology(topology, topology),
        max_param_shift_mm=25.0, policy=UpdatePolicy(),
    )
    assert decision == "remesh_required"


def test_parametric_operations_cover_required_set() -> None:
    """Every mandated generic CAD capability builds real OCC topology."""

    parameters = ParameterSet((
        ParameterDef("d", 20.0),
        ParameterDef("h", expression="d*2"),
    ))
    model = ParametricModel("ops", parameters)
    model.add_box("block", 10.0, 10.0, 10.0)
    model.add_cylinder("boss", 6.0, 8.0, center_mm=(0.0, 0.0, 5.0))
    model.add_sphere("dome", 6.0, center_mm=(0.0, 0.0, 12.0))
    model.add_cone("tip", 8.0, 2.0, 6.0, center_mm=(0.0, 0.0, 18.0))
    model.extrude_profile("rib", ((0, 0), (8, 0), (8, 2), (0, 2)), 4.0)
    model.revolve_profile("ring", ((6, 0), (9, 0), (9, 3), (6, 3)), 360.0)
    model.loft_profiles(
        "fairing",
        (((0, 0), (6, 0), (6, 4), (0, 4)), ((0, 0), (4, 0), (4, 3), (0, 3))),
        offsets_mm=(0.0, 10.0),
    )
    model.sweep_profile(
        "elbow", ((0, 0), (3, 0), (3, 3), (0, 3)), ((0, 0, 0), (0, 0, 12)),
    )
    model.boolean("joined", "union", "block", "boss")
    model.boolean("cutout", "cut", "joined", "rib")
    model.boolean("kept", "intersection", "cutout", "block")
    model.circular_pattern("ring4", "boss", 4)
    model.linear_pattern("row2", "boss", 2, 20.0)
    model.fillet("block", 1.0)
    model.add_frame("axis", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    built = model.build()
    volumes = {c.name: c.volume_mm3 for c in built.components}
    faces = {c.name: len(c.face_fingerprints) for c in built.components}
    assert volumes["block"] == pytest.approx(1000.0, rel=0.05)  # fillet removes edge stock
    assert faces["block"] > 6  # fillet added real faces
    assert volumes["joined"] > volumes["block"]
    assert volumes["cutout"] < volumes["joined"]
    assert volumes["kept"] <= volumes["block"]
    assert volumes["ring4"] == pytest.approx(4.0 * volumes["boss"], rel=1e-6)
    assert all(len(c.face_fingerprints) > 0 for c in built.components)
    assert built.operation_count == len(model.operations)
    assert parameters.resolve() == {"d": 20.0, "h": 40.0}
    # Impossible dress-ups fail closed instead of silently skipping.
    doomed = ParametricModel("doomed", ParameterSet((ParameterDef("d", 5.0),)))
    doomed.add_box("tiny", 2.0, 2.0, 2.0)
    doomed.fillet("tiny", 50.0)
    with pytest.raises(ValueError, match="FILLET_FAILED"):
        doomed.build()


def test_reference_edf_maps_onto_generic_topology() -> None:
    """The EDF example stays an integration consumer, not a core assumption."""

    edf = make_edf_geometry()
    generic = TopologyModel((
        TopologyEntity(
            semantic_key="edf.inlet", kind="inlet", region="edf-flow",
            fingerprint="edf-envelope#inlet",
        ),
        TopologyEntity(
            semantic_key="edf.outlet", kind="outlet", region="edf-flow",
            fingerprint="edf-envelope#outlet",
        ),
        TopologyEntity(
            semantic_key="edf.shroud", kind="wall", region="edf-solid",
            fingerprint="edf-envelope#shroud",
        ),
    ))
    assert {surface.semantic_key for surface in edf.surfaces} >= {
        "edf.inlet", "edf.outlet", "edf.blade-tip"
    }
    assert {entity.kind for entity in generic.entities} == {"inlet", "outlet", "wall"}
    assert reconcile_topology(generic, generic).valid is True
    # Core fluid-zone helper never assumed three stages or 80 mm.
    assert len(fluid_zone_names(3)) == 3 + 2 + 2
    assert len(fluid_zone_names(5)) == 5 + 4 + 2
