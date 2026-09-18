"""GEN 05: solver-mesh generation driven by CAD artifacts and semantics.

The tests use a small generic multi-zone assembly (arbitrary rotating-zone
count), build a real Gmsh mesh from real BREP/STEP exports, and assert that
semantic boundaries, zones, materials, and interfaces survive meshing and are
mapped explicitly for OpenFOAM, Code_Aster/Elmer, and preCICE. No
application-specific region name is assumed by the mesh core.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from aeroworkbench_geometry import build_duct_system
from aeroworkbench_geometry.builder import live_shapes
from aeroworkbench_geometry.parametric import export_artifacts
from aeroworkbench_mesh import (
    BoundaryLayerIntent,
    BoxSelector,
    ExportNeed,
    InterfaceDeclaration,
    MeshQuality,
    NativeMeshReceipt,
    ResolvedMeshRequest,
    SemanticMeshRequest,
    ZoneDeclaration,
    build_native_mesh,
    build_solver_exports,
    evaluate_quality_gate,
    mesh_spec_digest,
    morph_affine,
    probe_gmsh,
    resolve_semantic_mesh_request,
    select_mesh_update,
    semantic_request_from_topology,
    semantic_topology_from_model,
    write_solver_mapping,
)
from aeroworkbench_semantics import (
    TopologyModel,
    reconcile_topology,
    topology_from_components,
)

_DIMS = {
    "outer_diameter_mm": 36.0,
    "inner_diameter_mm": 32.0,
    "length_mm": 28.0,
    "hub_diameter_mm": 10.0,
    "zone_length_mm": 8.0,
    "zone_gap_mm": 4.0,
}
_N_ROTATING = 2
_BASE_SIZE_MM = 6.0

pytestmark = pytest.mark.skipif(
    not probe_gmsh().available, reason="gmsh python API is required for native meshing"
)


def _assignments(n_rotating: int) -> tuple[tuple[str, str, str, str], ...]:
    assignments: list[tuple[str, str, str, str]] = [
        ("shell.region", "solid_region", "duct-shell", "duct"),
        ("flow.inlet.region", "fluid_region", "inlet-zone", "fluid_inlet"),
        ("flow.outlet.region", "fluid_region", "outlet-zone", "fluid_outlet"),
        ("flow.inlet", "inlet", "inlet", "fluid_inlet"),
        ("flow.outlet", "outlet", "outlet", "fluid_outlet"),
        ("flow.wall", "wall", "duct-wall", "fluid_inlet"),
        ("shell.material", "material_assignment", "duct-shell-material", "duct"),
    ]
    for index in range(n_rotating):
        assignments.append(
            (f"rotor.{index}", "rotating_region", f"rotor-zone-{index}", f"rotor_zone_{index}")
        )
        if index < n_rotating - 1:
            assignments.append(
                (
                    f"stator.{index}",
                    "stationary_region",
                    f"stator-zone-{index}",
                    f"stator_zone_{index}",
                )
            )
    return tuple(assignments)


def _selectors() -> dict[str, BoxSelector]:
    radius = _DIMS["inner_diameter_mm"] / 2.0
    half = _DIMS["length_mm"] / 2.0
    end = 0.51 * _DIMS["length_mm"]
    return {
        "inlet": BoxSelector(
            -radius, -radius, -half - 1.0, radius, radius, -half + end * 0.02 + 1.0
        ),
        "outlet": BoxSelector(
            -radius, -radius, half - end * 0.02 - 1.0, radius, radius, half + 1.0
        ),
        "duct-wall": BoxSelector(
            -radius - 1.0, -radius - 1.0, -half, radius + 1.0, radius + 1.0, half
        ),
    }


class _Assembly:
    def __init__(
        self,
        built: object,
        files: dict[str, Path],
        topology: TopologyModel,
        resolved: ResolvedMeshRequest,
    ) -> None:
        self.built = built
        self.files = files
        self.topology = topology
        self.resolved = resolved


@pytest.fixture(scope="module")
def assembly(tmp_path_factory: pytest.TempPathFactory) -> _Assembly:
    tmp = tmp_path_factory.mktemp("gen05")
    built = build_duct_system(n_rotating=_N_ROTATING, n_solids=1, **_DIMS).build()
    records = export_artifacts(
        live_shapes(built), built.kernel, tmp / "cad", basename="domain", export_stl=False
    )
    files = {
        str(artifact["component"]): Path(str(artifact["path"]))
        for artifact in records["artifacts"]
        if artifact["format"] == "step" and artifact["component"] != "assembly"
    }
    face_map = {
        component.name: component.face_fingerprints for component in built.components
    }
    topology = topology_from_components(_assignments(_N_ROTATING), face_map)  # type: ignore[arg-type]
    request = semantic_request_from_topology(
        topology,
        name="domain",
        geometry_hash=built.shape_hash,
        dimension=3,
        base_size_mm=_BASE_SIZE_MM,
        min_size_mm=_BASE_SIZE_MM / 4.0,
        max_size_mm=_BASE_SIZE_MM * 2.0,
        selectors=_selectors(),
        interfaces=(
            InterfaceDeclaration(
                "rotor0-inlet-fsi",
                "fsi_interface",
                "rotor-zone-0",
                "inlet-zone",
                True,
                ("rotor.0",),
            ),
            InterfaceDeclaration(
                "shell-flow-cht",
                "cht_interface",
                "duct-shell",
                "inlet-zone",
                True,
                ("shell.region", "flow.inlet.region"),
            ),
        ),
        boundary_layer=BoundaryLayerIntent(("duct-wall",), _BASE_SIZE_MM / 4.0, 1.2, 3),
        exports=(
            ExportNeed("openfoam"),
            ExportNeed("code_aster"),
            ExportNeed("elmer"),
            ExportNeed("precice"),
        ),
        required_kinds=("rotating_region", "fluid_region", "solid_region"),
        required_patches=("inlet", "outlet"),
    )
    resolved = resolve_semantic_mesh_request(
        request, semantic_topology_from_model(topology), files
    )
    return _Assembly(built, files, topology, resolved)


@pytest.fixture(scope="module")
def receipt(assembly: _Assembly, tmp_path_factory: pytest.TempPathFactory) -> NativeMeshReceipt:
    tmp = tmp_path_factory.mktemp("gen05mesh")
    return build_native_mesh(
        assembly.resolved.spec,
        assembly.files,
        assembly.resolved.request.geometry_hash,
        tmp / "mesh",
        mapping_payload=assembly.resolved.mapping.canonical_payload(),
    )


def test_gen05_real_assembly_meshes_with_semantic_groups(
    assembly: _Assembly, receipt: NativeMeshReceipt
) -> None:
    assert receipt.state == "completed", receipt.detail
    assert receipt.element_count > 0
    assert receipt.quality is not None and receipt.quality.inverted_count == 0
    groups = receipt.physical_groups
    assert "zone:rotor-zone-0" in groups and "zone:rotor-zone-1" in groups
    assert groups["zone:rotor-zone-0"].startswith("rotating:fluid")
    assert "zone:duct-shell" in groups and groups["zone:duct-shell"].startswith("stationary:solid")
    assert "patch:inlet" in groups and "patch:outlet" in groups
    assert "material:duct-shell-material" in groups
    assert receipt.geometry_hash == assembly.built.shape_hash  # type: ignore[attr-defined]
    assert receipt.input_hashes["geometryHash"] == assembly.built.shape_hash  # type: ignore[attr-defined]
    assert set(receipt.input_hashes) >= {"meshSpecDigest", "semanticMapping"}


def test_gen05_semantic_mapping_survives_meshing(
    assembly: _Assembly, receipt: NativeMeshReceipt
) -> None:
    mapping = assembly.resolved.mapping
    for name, _, _, _ in mapping.zones:
        assert f"zone:{name}" in receipt.physical_groups
    for name, _, _ in mapping.patches:
        assert f"patch:{name}" in receipt.physical_groups
    for name, _, _ in mapping.materials:
        assert f"material:{name}" in receipt.physical_groups
    interface_names = {item.name for item in receipt.interfaces}
    for name, _, _, _, _, _ in mapping.interfaces:
        assert name in interface_names
    assert all(keys for _, _, _, keys in mapping.zones)
    assert {name for name, _, _ in mapping.patches} == {"inlet", "outlet", "duct-wall"}


def test_gen05_multiple_rotating_zones_are_distinct(receipt: NativeMeshReceipt) -> None:
    rotating = sorted(
        name
        for name, value in receipt.physical_groups.items()
        if name.startswith("zone:") and value.startswith("rotating:")
    )
    assert rotating == ["zone:rotor-zone-0", "zone:rotor-zone-1"]
    rotating_interfaces = {
        (item.zone_a, item.zone_b)
        for item in receipt.interfaces
        if "rotor-zone-0" in (item.zone_a, item.zone_b)
    }
    assert rotating_interfaces, "rotating zone interface must be identified"


def test_gen05_interfaces_are_identified_deterministically(
    assembly: _Assembly,
) -> None:
    first = assembly.resolved.mapping
    second = resolve_semantic_mesh_request(
        assembly.resolved.request,
        semantic_topology_from_model(assembly.topology),
        assembly.files,
    )
    assert first.canonical_payload() == second.mapping.canonical_payload()
    assert mesh_spec_digest(assembly.resolved.spec) == mesh_spec_digest(second.spec)
    declared = {name: kind for name, kind, _, _, _, _ in first.interfaces}
    assert declared["rotor0-inlet-fsi"] == "fsi_interface"
    assert declared["shell-flow-cht"] == "cht_interface"


def test_gen05_boundary_layer_receipt_is_bounded_and_honest(
    receipt: NativeMeshReceipt,
) -> None:
    assert receipt.boundary_layer_requested is True
    assert isinstance(receipt.boundary_layer_achieved, bool)
    assert receipt.quality is not None
    detail = receipt.quality.boundary_layer_detail
    assert "requested 3 layers" in detail
    assert "achieved size field only" in detail
    assert receipt.quality.boundary_layer_applied == (
        receipt.boundary_layer_requested and receipt.boundary_layer_achieved
    )


def test_gen05_missing_required_region_fails_closed(assembly: _Assembly) -> None:
    with pytest.raises(ValueError, match="SEMANTIC_REQUIRED_PATCH_MISSING"):
        resolve_semantic_mesh_request(
            replace(assembly.resolved.request, required_patches=("does-not-exist",)),
            semantic_topology_from_model(assembly.topology),
            assembly.files,
        )
    bogus = SemanticMeshRequest(
        name="bogus",
        geometry_hash=assembly.built.shape_hash,  # type: ignore[attr-defined]
        topology_digest="",
        dimension=3,
        base_size_mm=_BASE_SIZE_MM,
        min_size_mm=1.0,
        max_size_mm=20.0,
        zones=(ZoneDeclaration("ghost", "stationary", "fluid", ("missing.key",)),),
    )
    with pytest.raises(ValueError, match="SEMANTIC_KEY_NOT_FOUND"):
        resolve_semantic_mesh_request(
            bogus, semantic_topology_from_model(assembly.topology), assembly.files
        )


def test_gen05_bad_quality_fails_closed() -> None:
    def quality(**overrides: object) -> MeshQuality:
        base: dict[str, object] = {
            "element_count": 100,
            "node_count": 50,
            "min_size_mm": 1.0,
            "max_size_mm": 2.0,
            "min_sicn": 0.5,
            "min_scaled_jacobian": 0.8,
            "inverted_count": 0,
            "aspect_ratio_max": 3.0,
            "boundary_layer_applied": False,
            "boundary_layer_detail": "none",
        }
        base.update(overrides)
        return MeshQuality(**base)  # type: ignore[arg-type]

    assert evaluate_quality_gate(quality(), 0.05)[0] is True
    assert evaluate_quality_gate(quality(min_sicn=0.01), 0.05)[0] is False
    assert evaluate_quality_gate(quality(min_sicn=None), 0.05)[0] is False
    assert evaluate_quality_gate(quality(inverted_count=3), 0.05)[0] is False


def test_gen05_small_mutation_morphs_only_when_allowed(
    assembly: _Assembly, receipt: NativeMeshReceipt, tmp_path: Path
) -> None:
    preserved = reconcile_topology(assembly.topology, assembly.topology)
    reuse = select_mesh_update(
        parent_geometry_hash=receipt.geometry_hash,
        current_geometry_hash=receipt.geometry_hash,
        parent_mesh_hash=receipt.mesh_hash,
        report=preserved,
        max_param_shift_mm=0.0,
    )
    assert reuse.action == "reuse", reuse.reason

    small = select_mesh_update(
        parent_geometry_hash="a" * 64,
        current_geometry_hash="b" * 64,
        parent_mesh_hash=receipt.mesh_hash,
        report=preserved,
        max_param_shift_mm=0.2,
    )
    assert small.action == "morph_candidate", small.reason
    assert small.topology_preserved is True
    assert receipt.mesh_path is not None
    morphed = morph_affine(
        Path(receipt.mesh_path), tmp_path / "morphed.msh", scale=1.002
    )
    assert morphed.state == "morphed", morphed.detail
    assert morphed.mesh_hash != receipt.mesh_hash
    assert morphed.max_displacement_mm > 0.0

    large = select_mesh_update(
        parent_geometry_hash="a" * 64,
        current_geometry_hash="b" * 64,
        parent_mesh_hash=receipt.mesh_hash,
        report=preserved,
        max_param_shift_mm=50.0,
    )
    assert large.action == "remesh_required"

    mismatch = select_mesh_update(
        parent_geometry_hash="a" * 64,
        current_geometry_hash="b" * 64,
        parent_mesh_hash=receipt.mesh_hash,
        report=None,
        max_param_shift_mm=0.1,
    )
    assert mismatch.action == "remesh_required"
    assert mismatch.geometry_hash_match is False


def test_gen05_topology_changing_mutation_forces_remesh(assembly: _Assembly) -> None:
    missing = TopologyModel(
        tuple(
            entity
            for entity in assembly.topology.entities
            if entity.semantic_key != "rotor.0"
        )
    )
    report = reconcile_topology(assembly.topology, missing)
    decision = select_mesh_update(
        parent_geometry_hash="a" * 64,
        current_geometry_hash="b" * 64,
        parent_mesh_hash="c" * 64,
        report=report,
        max_param_shift_mm=0.1,
    )
    assert decision.action == "remesh_required"
    assert decision.topology_preserved is False


def test_gen05_solver_export_mappings(
    assembly: _Assembly, receipt: NativeMeshReceipt, tmp_path: Path
) -> None:
    exports = build_solver_exports(assembly.resolved, assembly.resolved.mapping)
    by_participant = {export.participant: export for export in exports}
    assert set(by_participant) == {"openfoam", "code_aster", "elmer", "precice"}
    openfoam = by_participant["openfoam"]
    patch_types = {name: native for name, _, native in openfoam.patches}
    assert patch_types["inlet"] == "patch"
    assert patch_types["outlet"] == "patch"
    assert patch_types["duct-wall"] == "wall"
    assert any(item[1] == "fsi_interface" for item in openfoam.interfaces)
    precice = by_participant["precice"]
    assert precice.patches == ()
    assert {item[1] for item in precice.interfaces} >= {"fsi_interface", "cht_interface"}
    path = tmp_path / "mesh_mapping.json"
    digest = write_solver_mapping(
        path,
        exports,
        provenance={
            "geometryHash": receipt.geometry_hash,
            "meshHash": receipt.mesh_hash or "",
        },
    )
    assert len(digest) == 64 and path.stat().st_size > 0


def test_gen05_no_application_specific_names_in_mesh_core() -> None:
    # Fragments keep this guard's own source clean.
    forbidden = [
        "".join(pair)
        for pair in (
            ("bl", "ade"),
            ("wi", "ng"),
            ("tu", "rbine"),
            ("no", "zzle"),
            ("im", "peller"),
            ("pro", "peller"),
            ("com", "pressor"),
            ("rotor_zone"),
            ("stator_zone"),
            ("fluid_inlet"),
            ("fluid_outlet"),
        )
    ]
    package = (
        Path(__file__).resolve().parents[2] / "packages" / "mesh" / "aeroworkbench_mesh"
    )
    text = "\n".join(
        (package / name).read_text(encoding="utf-8").lower()
        for name in ("semantics.py", "export.py", "domains.py", "quality.py")
    )
    assert [token for token in forbidden if token in text] == []
