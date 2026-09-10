from __future__ import annotations

from pathlib import Path

import pytest
from aeroworkbench_geometry import make_edf_geometry, shape_hash
from aeroworkbench_mesh import plan_gmsh_mesh
from aeroworkbench_mesh.gmsh_adapter import receipt_from_native_mesh, unavailable_receipt
from aeroworkbench_semantics import SemanticAssignment, reconcile_surfaces
from freecad.adapter import inspect_freecad


def test_reference_edf_is_parametric_and_hashes_deterministically() -> None:
    first = make_edf_geometry()
    second = make_edf_geometry(diameter_mm=70.0, hub_diameter_mm=24.0, blade_count=12)
    assert shape_hash(first) == shape_hash(second)
    assert dict(first.parameters_mm)["diameter"] == 70.0
    assert {surface.semantic_key for surface in first.surfaces} >= {
        "edf.inlet", "edf.outlet", "edf.blade-tip"
    }


def test_semantic_reconciliation_preserves_boundaries_and_flags_loss() -> None:
    previous = (
        SemanticAssignment("inlet-old", "edf.inlet", "fluid-inlet", "inlet"),
        SemanticAssignment("outlet-old", "edf.outlet", "fluid-outlet", "outlet"),
    )
    current = (
        SemanticAssignment("inlet-new", "edf.inlet", "fluid-inlet", "inlet"),
        SemanticAssignment("new-wall", "edf.wall", "solid-wall", "wall"),
    )
    report = reconcile_surfaces(previous, current)
    assert report.valid is False
    assert [item.semantic_key for item in report.persistent] == ["edf.inlet"]
    assert report.missing == ("edf.outlet",)
    assert [item.semantic_key for item in report.added] == ["edf.wall"]


def test_mesh_planning_is_native_only_and_quality_gated(tmp_path: Path) -> None:
    plan = plan_gmsh_mesh(make_edf_geometry(), case_directory="edf-case")
    assert plan.command[:4] == ("gmsh", "-3", "-format", "msh4")
    assert unavailable_receipt(plan).state == "unavailable"

    mesh_path = tmp_path / "edf.msh"
    mesh_path.write_bytes(b"native-mesh")
    accepted = receipt_from_native_mesh(
        plan, mesh_path=mesh_path, element_count=1000, minimum_quality=0.5
    )
    assert accepted.state == "completed"
    assert accepted.mesh_hash is not None
    rejected = receipt_from_native_mesh(
        plan, mesh_path=mesh_path, element_count=1000, minimum_quality=0.1
    )
    assert rejected.detail == "MESH_QUALITY_BELOW_THRESHOLD"
    with pytest.raises(ValueError, match="INVALID_CASE_DIRECTORY"):
        plan_gmsh_mesh(make_edf_geometry(), case_directory="../outside")


def test_freecad_capability_is_explicit_when_native_tool_is_missing() -> None:
    receipt = inspect_freecad("definitely-not-FreeCADCmd")
    assert receipt.state == "unavailable"
    assert "not installed" in receipt.detail
