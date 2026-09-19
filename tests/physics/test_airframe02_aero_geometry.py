"""AIRFRAME 02: generic aerodynamic geometry primitives.

Profiles, lifting surfaces, lofted bodies and typed control surfaces are
deterministic, unit-bearing and hashable, feed the existing
``GeometryRegenerationRequest`` path, preserve semantic identity across small
shape changes, and fail closed on impossible geometry or an unavailable native
CAD kernel. The tiny fixtures under ``tests/airframe/aero_geometry`` provide a
fixed-wing (wing + fuselage + controls) and a flying-wing assembly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe.aero_geometry import (
    DEFAULT_EDGE_POINTS,
    DEFAULT_PROFILE_POINTS,
    AeroGeometryAssembly,
    AeroGeometryRegenerator,
    AirfoilProfile,
    BodySection,
    ControlSurface,
    LiftingSurface,
    LoftedBody,
    Planform,
    SpanwiseStation,
    check_lifting_surface,
    probe_cad,
    regenerate_assembly,
)
from aeroworkbench_geometry import KernelIdentity

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _TESTS_ROOT / "airframe" / "aero_geometry"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def profile_from_payload(payload: dict[str, Any]) -> AirfoilProfile:
    return AirfoilProfile(
        family=payload.get("family", "parametric"),
        thickness_ratio=float(payload.get("thicknessRatio", 0.12)),
        camber_ratio=float(payload.get("camberRatio", 0.0)),
        camber_position=float(payload.get("camberPosition", 0.4)),
        thickness_family=payload.get("thicknessFamily", "naca4"),
        camber_family=payload.get("camberFamily", "circular_arc"),
        cst_upper=tuple(float(value) for value in payload.get("cstUpper", ())),
        cst_lower=tuple(float(value) for value in payload.get("cstLower", ())),
        upper_coordinates=tuple(
            (float(point[0]), float(point[1])) for point in payload.get("upperCoordinates", ())
        ),
        lower_coordinates=tuple(
            (float(point[0]), float(point[1])) for point in payload.get("lowerCoordinates", ())
        ),
        spline_controls=tuple(
            (float(point[0]), float(point[1])) for point in payload.get("splineControls", ())
        ),
    )


def assembly_from_payload(payload: dict[str, Any]) -> AeroGeometryAssembly:
    surfaces = []
    for item in payload["surfaces"]:
        planform_payload = item["planform"]
        planform = Planform(
            span_mm=float(planform_payload["spanMm"]),
            root_chord_mm=float(planform_payload["rootChordMm"]),
            tip_chord_mm=float(planform_payload["tipChordMm"]),
            sweep_deg=float(planform_payload.get("sweepDeg", 0.0)),
            dihedral_deg=float(planform_payload.get("dihedralDeg", 0.0)),
            twist_root_deg=float(planform_payload.get("twistRootDeg", 0.0)),
            twist_tip_deg=float(planform_payload.get("twistTipDeg", 0.0)),
        )
        surfaces.append(
            LiftingSurface.from_planform(
                item["surfaceId"],
                item["role"],
                planform,
                profile_from_payload(item["profile"]),
                frame=item.get("frame", "surface-local"),
                n_stations=int(item.get("nStations", 3)),
            )
        )
    bodies = []
    for item in payload.get("bodies", ()):
        bodies.append(
            LoftedBody.from_spine(
                item["bodyId"],
                item["role"],
                tuple(
                    (float(point[0]), float(point[1]), float(point[2]))
                    for point in item["spine"]
                ),
                tuple(float(value) for value in item["widthsMm"]),
                tuple(float(value) for value in item["heightsMm"]),
                frame=item.get("frame", "body-local"),
                exponent=float(item.get("exponent", 2.0)),
                n_points=int(item.get("nPoints", 12)),
            )
        )
    controls = []
    for item in payload.get("controls", ()):
        controls.append(
            ControlSurface(
                item["controlId"],
                item["parentId"],
                item["kind"],
                float(item["hingeFraction"]),
                (float(item["spanFraction"][0]), float(item["spanFraction"][1])),
                deflection_deg=float(item.get("deflectionDeg", 0.0)),
            )
        )
    return AeroGeometryAssembly(
        payload["assemblyId"], tuple(surfaces), tuple(bodies), tuple(controls)
    )


def fixed_wing() -> AeroGeometryAssembly:
    return assembly_from_payload(load_fixture("fixed_wing.json"))


def flying_wing() -> AeroGeometryAssembly:
    return assembly_from_payload(load_fixture("flying_wing.json"))


def _profile_families() -> dict[str, AirfoilProfile]:
    return {
        "parametric": AirfoilProfile(family="parametric", thickness_ratio=0.12, camber_ratio=0.02),
        "naca4": AirfoilProfile(family="naca4", thickness_ratio=0.12),
        "cst": AirfoilProfile(
            family="cst",
            cst_upper=(0.16, 0.11, 0.05),
            cst_lower=(-0.12, -0.08, -0.03),
        ),
        "imported": AirfoilProfile(
            family="imported",
            upper_coordinates=((0.0, 0.0), (0.3, 0.06), (0.7, 0.05), (1.0, 0.0)),
            lower_coordinates=((0.0, 0.0), (0.3, -0.05), (0.7, -0.04), (1.0, 0.0)),
        ),
        "bspline": AirfoilProfile(
            family="bspline",
            spline_controls=(
                (0.0, 0.0),
                (0.25, 0.09),
                (0.5, 0.11),
                (0.75, 0.06),
                (1.0, 0.0),
                (0.75, -0.05),
                (0.5, -0.06),
                (0.25, -0.04),
            ),
        ),
    }


def test_airframe02_profile_families_are_deterministic_and_distinct() -> None:
    signatures: set[str] = set()
    for family, profile in _profile_families().items():
        first = profile.outline()
        assert first == profile.outline()
        assert profile.digest == profile.digest
        assert len(first) == profile.point_count()
        signatures.add(profile.digest)
        assert profile.canonical_payload()["family"] == family
    assert len(signatures) == len(_profile_families())


def test_airframe02_profile_reuses_shared_section_primitive() -> None:
    from aeroworkbench_turbomachinery.geometry.sections import section_outline

    profile = _profile_families()["parametric"]
    section = profile.to_blade_section(chord_mm=2.0)
    assert section.chord_mm == pytest.approx(2.0)
    assert section.thickness.thickness_ratio == pytest.approx(profile.thickness_ratio)
    mine = profile.outline()
    shared = section_outline(
        profile.to_blade_section(chord_mm=1.0),
        n_surface=DEFAULT_PROFILE_POINTS,
        n_edge=DEFAULT_EDGE_POINTS,
    )
    assert len(mine) == len(shared)
    for left, right in zip(mine, shared, strict=True):
        assert left == pytest.approx(right)


def test_airframe02_planform_mutation_changes_stations_and_digest() -> None:
    profile = _profile_families()["naca4"]
    base = Planform(span_mm=100.0, root_chord_mm=20.0, tip_chord_mm=12.0, sweep_deg=5.0)
    stretched = Planform(span_mm=150.0, root_chord_mm=20.0, tip_chord_mm=8.0, sweep_deg=25.0)
    assert base.taper_ratio == pytest.approx(0.6)
    assert stretched.taper_ratio == pytest.approx(0.4)
    base_surface = LiftingSurface.from_planform("wing", "wing", base, profile, n_stations=3)
    stretched_surface = LiftingSurface.from_planform(
        "wing", "wing", stretched, profile, n_stations=3
    )
    assert base_surface.span_mm == pytest.approx(100.0)
    assert stretched_surface.span_mm == pytest.approx(150.0)
    assert base_surface.digest != stretched_surface.digest
    assert base_surface.section_loops() != stretched_surface.section_loops()


def test_airframe02_lifting_surface_metrics_and_semantics() -> None:
    wing = fixed_wing().surface("wing")
    assert wing.span_mm == pytest.approx(120.0)
    assert wing.area_mm2 > 0.0
    assert wing.aspect_ratio > 0.0
    keys = {assignment.semantic_key for assignment in wing.semantic_assignments()}
    assert keys == {
        "wing.upper",
        "wing.lower",
        "wing.leading_edge",
        "wing.trailing_edge",
        "wing.root",
        "wing.tip",
    }
    assert wing.digest == wing.digest


def test_airframe02_seam_exposes_structured_semantic_grids() -> None:
    wing = fixed_wing().surface("wing")
    seam = wing.seam()
    assert {"upper", "lower", "leading_edge", "trailing_edge", "root", "tip"} <= set(
        seam.roles()
    )
    upper = next(grid for grid in seam.grids if grid.role == "upper")
    assert upper.nu == wing.n_surface
    assert upper.nv == len(wing.stations)
    assert len(upper.points) == upper.nu * upper.nv
    assert seam.digest == seam.digest
    assert fixed_wing().diagnostics() == ()


def test_airframe02_fixed_wing_fixture_regenerates_valid_cad() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    receipt = regenerate_assembly(fixed_wing(), "fixed-wing")
    assert receipt.valid, receipt.invalid_reasons
    assert {component.name for component in receipt.components} == {
        "wing",
        "tail",
        "fin",
        "fuselage",
        "elevator",
        "rudder",
        "aileron",
    }
    assert len(receipt.shape_hash) == 64


def test_airframe02_flying_wing_fixture_regenerates_valid_cad() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    receipt = regenerate_assembly(flying_wing(), "flying-wing")
    assert receipt.valid, receipt.invalid_reasons
    assert {component.name for component in receipt.components} == {
        "blended",
        "elevon_left",
        "elevon_right",
    }


def test_airframe02_parameter_mutation_changes_geometry_and_hashes() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    assembly = fixed_wing()
    regenerator = AeroGeometryRegenerator(assembly, "fixed-wing")
    baseline = regenerator.evaluate()
    stretched = regenerator.evaluate({"wing.span": 180.0, "fuselage.length": 120.0})
    assert baseline.valid and stretched.valid
    assert dict(stretched.resolved_parameters)["wing.span"] == pytest.approx(180.0)
    assert dict(stretched.resolved_parameters)["fuselage.length"] == pytest.approx(120.0)
    assert stretched.shape_hash != baseline.shape_hash
    assert stretched.definition_hash != baseline.definition_hash
    assert regenerator.evaluate() is baseline
    assert regenerator.cache_hits == 1


def test_airframe02_unchanged_regeneration_preserves_semantics() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    assembly = fixed_wing()
    parent = regenerate_assembly(assembly, "parent")
    child = regenerate_assembly(assembly, "child", parent=parent)
    assert child.valid, child.invalid_reasons
    assert child.topology_report is not None
    assert child.topology_report.reason == "TOPOLOGY_PRESERVED"
    parent_keys = {item.semantic_key for item in parent.semantic_assignments}
    assert {item.semantic_key for item in child.semantic_report.persistent} == parent_keys


def test_airframe02_small_shape_change_preserves_semantic_identity() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    assembly = fixed_wing()
    parent = regenerate_assembly(assembly, "parent")
    child = regenerate_assembly(
        assembly,
        "small-change",
        values={"wing.rootChord": 24.01},
        parent=parent,
        permitted_topology_change="any",
    )
    assert child.valid, child.invalid_reasons
    assert child.semantic_report is not None and child.semantic_report.valid
    parent_keys = {item.semantic_key for item in parent.semantic_assignments}
    assert {item.semantic_key for item in child.semantic_report.persistent} == parent_keys
    assert child.shape_hash != parent.shape_hash


def test_airframe02_control_deflection_does_not_destroy_parent_semantics() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    assembly = fixed_wing()
    parent = regenerate_assembly(assembly, "parent")
    plain = regenerate_assembly(assembly, "plain")
    deflected_assembly = assembly.with_parameters({"aileron.deflection": 15.0})
    deflected = regenerate_assembly(
        deflected_assembly, "deflected", parent=parent, permitted_topology_change="any"
    )
    assert deflected.valid, deflected.invalid_reasons
    parent_keys = {item.semantic_key for item in parent.semantic_assignments}
    assert {item.semantic_key for item in deflected.semantic_report.persistent} == parent_keys
    assert any(component.name == "aileron" for component in deflected.components)
    assert deflected.shape_hash != plain.shape_hash


def test_airframe02_removing_component_fails_closed_on_topology() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    assembly = fixed_wing()
    parent = regenerate_assembly(assembly, "parent")
    without_body = AeroGeometryAssembly(
        "no-body", assembly.surfaces, (), assembly.controls
    )
    child = regenerate_assembly(without_body, "child", parent=parent)
    assert child.valid is False
    assert any(
        "SEMANTIC_MISSING" in reason or "TOPOLOGY_MISSING" in reason
        for reason in child.invalid_reasons
    )


def test_airframe02_impossible_shape_returns_invalid_receipt() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    profile = _profile_families()["naca4"]
    degenerate = LiftingSurface(
        "collapsed",
        "wing",
        (
            SpanwiseStation(0.0, (0.0, 0.0, 0.0), 20.0, 0.0, 0.0, profile),
            SpanwiseStation(1.0, (0.0, 0.0, 0.0), 12.0, 0.0, 0.0, profile),
        ),
        "surface-local",
    )
    assert check_lifting_surface(degenerate)
    receipt = regenerate_assembly(
        AeroGeometryAssembly("collapsed", (degenerate,)), "collapsed"
    )
    assert receipt.valid is False
    assert receipt.invalid_reasons


def test_airframe02_invalid_contracts_fail_closed() -> None:
    with pytest.raises(ValueError, match="PLANFORM_SPAN"):
        Planform(span_mm=-1.0, root_chord_mm=1.0, tip_chord_mm=1.0)
    with pytest.raises(ValueError, match="UNKNOWN_PROFILE_FAMILY"):
        AirfoilProfile(family="not-a-family")
    with pytest.raises(ValueError, match="THICKNESS_RATIO"):
        AirfoilProfile(thickness_ratio=-0.1)
    with pytest.raises(ValueError, match="DEFLECTION_OUT_OF_LIMITS"):
        ControlSurface("aileron", "wing", "aileron", 0.7, (0.0, 1.0), deflection_deg=80.0)
    with pytest.raises(ValueError, match="UNKNOWN_CONTROL_SURFACE_KIND"):
        ControlSurface("bad", "wing", "not-a-kind", 0.7, (0.0, 1.0))
    with pytest.raises(ValueError, match="CHORD"):
        SpanwiseStation(0.5, (0.0, 0.0, 0.0), -1.0, 0.0, 0.0, AirfoilProfile())
    with pytest.raises(ValueError, match="SUPERELLIPSE"):
        BodySection(0.5, (0.0, 0.0, 0.0), 1.0, 1.0, superellipse_exponent=20.0)


def test_airframe02_native_cad_fails_closed_when_kernel_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> KernelIdentity:
        return KernelIdentity(False, None, None, "forced-unavailable")

    monkeypatch.setattr("aeroworkbench_geometry.regeneration.probe_kernel", unavailable)
    receipt = regenerate_assembly(fixed_wing(), "fixed-wing")
    assert receipt.valid is False
    assert any("CAD_KERNEL_UNAVAILABLE" in reason for reason in receipt.invalid_reasons)


def test_airframe02_generic_core_owns_no_product_names() -> None:
    forbidden = [
        "".join(fragments)
        for fragments in (
            ("boe", "ing"),
            ("air", "bus"),
            ("embr", "aer"),
            ("cess", "na"),
            ("gulf", "stream"),
            ("prat", "t"),
            ("ge", "90"),
            ("tr", "ent"),
            ("ed", "f"),
        )
    ]
    package = (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "airframe"
        / "aeroworkbench_airframe"
        / "aero_geometry"
    )
    text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in sorted(package.glob("*.py"))
    )
    assert [token for token in forbidden if token in text] == []
