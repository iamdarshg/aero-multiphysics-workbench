"""TURBO 02: generic real 3-D turbomachinery geometry primitives.

The same section, row, meridional, fluid-domain and robustness contracts must
cover axial, radial and mixed-flow machinery, reference TURBO 01 rows by id, be
deterministic and hashable, and prove that chord/profile/stagger/twist/clearance/
count changes alter the actual structured-surface topology (not just metadata).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_semantics import reconcile_surfaces
from aeroworkbench_turbomachinery import BladeRow
from aeroworkbench_turbomachinery.geometry import (
    BladeSection,
    CamberLine,
    GeometryBody,
    MeridionalContour,
    SurfacePatch,
    ThicknessDistribution,
    VoluteInterface,
    blocking,
    build_axial_blade_row,
    build_radial_blade_row,
    build_return_channel,
    build_row_fluid_domain,
    build_vaneless_diffuser,
    check_clearance,
    check_manifold,
    check_required_roles,
    check_row_overlap,
    check_section,
    place_section,
    probe_cad,
    section_digest,
    section_outline,
    section_parameters,
    topology_change_receipt,
)

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_DIR = _TESTS_ROOT / "turbo" / "geometry"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def section_from_payload(payload: dict[str, Any]) -> BladeSection:
    camber = payload.get("camber", {})
    thickness = payload.get("thickness", {})
    return BladeSection(
        span=float(payload["span"]),
        radius_mm=float(payload["radiusMm"]),
        chord_mm=float(payload["chordMm"]),
        stagger_deg=float(payload["staggerDeg"]),
        camber=CamberLine(
            family=camber.get("family", "straight"),
            camber_ratio=float(camber.get("camberRatio", 0.0)),
        ),
        thickness=ThicknessDistribution(
            family=thickness.get("family", "elliptic"),
            thickness_ratio=float(thickness.get("thicknessRatio", 0.08)),
            max_thickness_location=float(thickness.get("maxThicknessLocation", 0.3)),
            leading_edge_thickness_ratio=float(
                thickness.get("leadingEdgeThicknessRatio", 0.006)
            ),
            trailing_edge_thickness_ratio=float(
                thickness.get("trailingEdgeThicknessRatio", 0.004)
            ),
        ),
        leading_edge_radius_mm=float(payload.get("leadingEdgeRadiusMm", 0.6)),
        trailing_edge_radius_mm=float(payload.get("trailingEdgeRadiusMm", 0.3)),
        sweep_mm=float(payload.get("sweepMm", 0.0)),
        lean_mm=float(payload.get("leanMm", 0.0)),
    )


def axial_sections() -> tuple[BladeSection, ...]:
    payload = load_fixture("axial_row.json")
    return tuple(section_from_payload(item) for item in payload["sections"])


def axial_row(**overrides: Any) -> BladeRow:
    values: dict[str, Any] = {
        "row_id": "fan-rotor",
        "node": "fan",
        "role": "work_adding",
        "frame": "rotating",
        "shaft": "fan-spool",
        "station_in": "1",
        "station_out": "2",
        "periodicity": 4,
        "family": "axial",
    }
    values.update(overrides)
    return BladeRow(**values)


def build_axial(**overrides: Any):
    payload = load_fixture("axial_row.json")
    row = overrides.pop("row", None) or axial_row()
    sections = overrides.pop("sections", None) or axial_sections()
    hub = overrides.pop("hub_radius_mm", payload["hubRadiusMm"])
    shroud = overrides.pop("shroud_radius_mm", payload["shroudRadiusMm"])
    return build_axial_blade_row(
        row,
        hub_radius_mm=hub,
        shroud_radius_mm=shroud,
        sections=sections,
        tip_clearance_mm=overrides.pop("tip_clearance_mm", payload["tipClearanceMm"]),
        **overrides,
    )


def contour_from_payload(payload: dict[str, Any]) -> MeridionalContour:
    return MeridionalContour(
        payload["name"], tuple((float(z), float(r)) for z, r in payload["points"])
    )


def radial_payload() -> dict[str, Any]:
    return load_fixture("radial_stage.json")


def radial_row(**overrides: Any) -> BladeRow:
    values: dict[str, Any] = {
        "row_id": "impeller-rotor",
        "node": "impeller",
        "role": "work_adding",
        "frame": "rotating",
        "shaft": "rc-spool",
        "station_in": "1",
        "station_out": "2",
        "periodicity": 4,
        "family": "radial",
    }
    values.update(overrides)
    return BladeRow(**values)


def build_radial(**overrides: Any):
    payload = radial_payload()
    return build_radial_blade_row(
        overrides.pop("row", None) or radial_row(),
        hub_contour=overrides.pop("hub_contour")
        if "hub_contour" in overrides
        else contour_from_payload(payload["hubContour"]),
        shroud_contour=overrides.pop("shroud_contour")
        if "shroud_contour" in overrides
        else contour_from_payload(payload["shroudContour"]),
        sections=overrides.pop("sections")
        if "sections" in overrides
        else tuple(section_from_payload(item) for item in payload["sections"]),
        splitter_count=overrides.pop("splitter_count", payload["splitterCount"]),
        **overrides,
    )


# --------------------------------------------------------------------------- A
def test_turbo02_section_outline_is_deterministic_and_hashable() -> None:
    section = axial_sections()[1]
    first = section_outline(section)
    second = section_outline(section)
    assert first == second
    assert section_digest(section) == section_digest(section)
    assert len(first) >= 8


def test_turbo02_section_is_parameter_bound_through_cad_parameters() -> None:
    from aeroworkbench_geometry import ParameterSet

    section = axial_sections()[0]
    definitions = section_parameters(section, "fan.section.0")
    names = {item.name for item in definitions}
    assert "fan.section.0.chord" in names
    resolved = ParameterSet(definitions).resolve()
    assert resolved["fan.section.0.chord"] == pytest.approx(section.chord_mm)
    assert resolved["fan.section.0.stagger"] == pytest.approx(section.stagger_deg)


def test_turbo02_profile_and_camber_families_change_real_geometry() -> None:
    base = axial_sections()[1]
    from dataclasses import replace

    thicker = replace(
        base,
        thickness=replace(
            base.thickness, thickness_ratio=base.thickness.thickness_ratio * 1.6
        ),
    )
    cambered = replace(base, camber=replace(base.camber, family="parabolic"))
    assert section_outline(base) != section_outline(thicker)
    assert section_digest(base) != section_digest(thicker)
    assert section_outline(base) != section_outline(cambered)
    assert section_digest(base) != section_digest(cambered)


def test_turbo02_stagger_changes_placed_world_coordinates() -> None:
    section = axial_sections()[0]
    from dataclasses import replace

    first = place_section(
        section, center=(100.0, 0.0, 0.0), theta_rad=0.0, meridional_angle_rad=0.0
    )
    turned = place_section(
        replace(section, stagger_deg=section.stagger_deg + 20.0),
        center=(100.0, 0.0, 0.0),
        theta_rad=0.0,
        meridional_angle_rad=0.0,
    )
    assert first != turned


# --------------------------------------------------------------------------- B
def test_turbo02_axial_row_is_closed_manifold_with_required_surfaces() -> None:
    geometry = build_axial()
    body = geometry.blade_body(0)
    assert body.is_closed()
    assert body.is_manifold()
    assert {
        "blade.pressure",
        "blade.suction",
        "blade.leading_edge",
        "blade.trailing_edge",
        "blade.tip",
        "blade.root",
    } <= set(body.roles())
    assert blocking(geometry.validate()) == ()


def test_turbo02_chord_profile_stagger_twist_change_brep_topology() -> None:
    from dataclasses import replace

    base = build_axial()
    base_digest = base.blade_body(0).digest()

    longer_chord = axial_sections()
    changed = build_axial(
        sections=(
            replace(longer_chord[0], chord_mm=longer_chord[0].chord_mm * 1.4),
            *longer_chord[1:],
        )
    )
    assert changed.blade_body(0).digest() != base_digest

    retwisted = axial_sections()
    changed = build_axial(
        sections=(
            retwisted[0],
            replace(retwisted[1], stagger_deg=retwisted[1].stagger_deg + 15.0),
            retwisted[2],
        )
    )
    assert changed.blade_body(0).digest() != base_digest

    reprofiled = axial_sections()
    changed = build_axial(
        sections=(
            replace(
                reprofiled[0],
                thickness=replace(reprofiled[0].thickness, family="naca4"),
            ),
            *reprofiled[1:],
        )
    )
    assert changed.blade_body(0).digest() != base_digest


def test_turbo02_clearance_and_count_change_topology() -> None:
    base = build_axial()
    tight = build_axial(tip_clearance_mm=0.1)
    assert tight.blade_body(0).digest() != base.blade_body(0).digest()
    assert tight.tip_radius_mm > base.tip_radius_mm

    more_blades = build_axial(row=axial_row(periodicity=6))
    assert more_blades.blade_count == 6
    assert len(more_blades.row_bodies()) > len(base.row_bodies())
    assert more_blades.row_digest() != base.row_digest()


def test_turbo02_shrouded_tip_adds_shroud_band() -> None:
    shrouded = build_axial(row=axial_row(clearance=_shrouded_clearance()))
    assert shrouded.shroud_state == "shrouded"
    body_ids = {body.body_id for body in shrouded.endwall_bodies()}
    assert "fan-rotor.shroud_band" in body_ids
    assert shrouded.tip_radius_mm == pytest.approx(shrouded.shroud_radius_mm)


def _shrouded_clearance():
    from aeroworkbench_turbomachinery import BladeClearance, Quantity

    return BladeClearance(shroud_state="shrouded", tip_clearance=Quantity(0.2, "mm"))


# --------------------------------------------------------------------------- C
def test_turbo02_radial_impeller_with_splitters_shares_section_contract() -> None:
    geometry = build_radial()
    assert geometry.family == "radial"
    assert geometry.blade_count == 4
    assert geometry.splitter_count == 2
    main = geometry.blade_body(0)
    splitter = geometry.blade_body(0, splitter=True)
    assert main.is_closed() and splitter.is_closed()
    assert main.digest() != splitter.digest()
    assert len(geometry.bodies()) == 4 + 2 + 2
    assert blocking(geometry.validate()) == ()


def test_turbo02_meridional_contours_are_deterministic_and_arc_sampled() -> None:
    contour = contour_from_payload(radial_payload()["hubContour"])
    assert contour.sample(7) == contour.sample(7)
    sample = contour.sample(7)
    assert sample[0] == pytest.approx(contour.points[0])
    assert sample[-1] == pytest.approx(contour.points[-1])
    assert contour.digest() == contour_from_payload(radial_payload()["hubContour"]).digest()


def test_turbo02_vaned_vaneless_diffuser_return_channel_and_volute() -> None:
    payload = radial_payload()
    hub = contour_from_payload(payload["diffuser"]["hubContour"])
    shroud = contour_from_payload(payload["diffuser"]["shroudContour"])
    vaneless = build_vaneless_diffuser(
        diffuser_id="diffuser", hub_contour=hub, shroud_contour=shroud, periodicity=4
    )
    assert vaneless.body.is_closed()
    assert blocking(vaneless.validate()) == ()

    return_channel = build_return_channel(
        channel_id="return-channel",
        hub_contour=contour_from_payload(payload["returnChannel"]["hubContour"]),
        shroud_contour=contour_from_payload(payload["returnChannel"]["shroudContour"]),
        periodicity=4,
    )
    assert return_channel.body.is_closed()

    volute_payload = payload["volute"]
    volute = VoluteInterface(
        interface_id=volute_payload["interfaceId"],
        inlet_radius_mm=volute_payload["inletRadiusMm"],
        inlet_width_mm=volute_payload["inletWidthMm"],
        outlet_diameter_mm=volute_payload["outletDiameterMm"],
        tongue_angle_deg=volute_payload["tongueAngleDeg"],
    )
    assert len(volute.digest()) == 64
    assert volute.parameter_defs()[0].name == "volute.inletRadius"

    stationary_diffuser = build_radial_blade_row(
        radial_row(
            row_id="diffuser-vanes",
            node="diffuser",
            role="diffuser_guide",
            frame="stationary",
            shaft=None,
            family="radial",
        ),
        hub_contour=hub,
        shroud_contour=shroud,
        sections=tuple(section_from_payload(item) for item in payload["sections"]),
    )
    assert stationary_diffuser.frame == "stationary"
    assert stationary_diffuser.blade_body(0).is_closed()


# --------------------------------------------------------------------------- D
def test_turbo02_fluid_domain_exposes_solver_ready_semantic_groups() -> None:
    geometry = build_axial()
    domain = build_row_fluid_domain(geometry)
    roles = set(domain.body.roles())
    assert {
        "inlet",
        "outlet",
        "hub",
        "shroud",
        "periodic_low",
        "periodic_high",
        "blade.pressure",
        "blade.suction",
        "blade.tip",
        "blade.root",
    } <= roles
    assert blocking(domain.validate()) == ()
    assert domain.periodicity == geometry.blade_count
    assert domain.rotating_zone == domain.domain_id
    assert domain.zones[0].motion == "rotating"


def test_turbo02_semantic_assignments_reconcile_across_rebuild() -> None:
    geometry = build_axial()
    parent = build_row_fluid_domain(geometry)
    child = build_row_fluid_domain(build_axial(tip_clearance_mm=0.6))
    report = reconcile_surfaces(
        parent.semantic_assignments(), child.semantic_assignments()
    )
    assert report.valid
    assert {item.semantic_key for item in report.persistent} == {
        item.semantic_key for item in parent.semantic_assignments()
    }


def test_turbo02_radial_fluid_domain_is_closed_with_periodic_sector() -> None:
    domain = build_radial().fluid_domain()
    assert domain.body.is_closed()
    assert blocking(domain.validate()) == ()


# --------------------------------------------------------------------------- E
def test_turbo02_fail_closed_on_invalid_section_and_clearance() -> None:
    with pytest.raises(ValueError, match="THICKNESS_RATIO_MUST_BE_POSITIVE"):
        ThicknessDistribution(thickness_ratio=-0.1)

    bad_clearance = check_clearance(
        hub_radius_mm=100.0,
        tip_radius_mm=140.0,
        shroud_radius_mm=140.0,
        tip_clearance_mm=-1.0,
        shroud_state=None,
    )
    assert any(item.code == "IMPOSSIBLE_CLEARANCE" for item in bad_clearance)

    consumed = check_clearance(
        hub_radius_mm=100.0,
        tip_radius_mm=140.0,
        shroud_radius_mm=140.0,
        tip_clearance_mm=60.0,
        shroud_state=None,
    )
    assert any(item.code == "CLEARANCE_EXCEEDS_PASSAGE" for item in consumed)


def test_turbo02_fail_closed_on_overlapping_rows() -> None:
    findings = check_row_overlap(
        (("row-a", 0.0, 20.0), ("row-b", 15.0, 30.0))
    )
    assert any(item.code == "ROWS_OVERLAP" for item in findings)
    clean = check_row_overlap((("row-a", 0.0, 10.0), ("row-b", 12.0, 20.0)))
    assert clean == ()


def test_turbo02_fail_closed_on_nonmanifold_and_missing_surfaces() -> None:
    p0, p1, p2, p3, p4 = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    body = GeometryBody(
        body_id="nonmanifold",
        domain="solid",
        patches=(
            SurfacePatch("a", "wall", "wall", 3, 1, (p0, p1, p2), closed_u=True),
            SurfacePatch("b", "wall", "wall", 3, 1, (p0, p1, p3), closed_u=True),
            SurfacePatch("c", "wall", "wall", 3, 1, (p0, p1, p4), closed_u=True),
        ),
    )
    findings = check_manifold(body)
    assert any(item.code == "GEOMETRY_NONMANIFOLD_EDGE" for item in findings)

    blade = build_axial().blade_body(0)
    missing = check_required_roles(blade, required_roles=("bleed_port",))
    assert any(item.code == "REQUIRED_ROLE_MISSING" for item in missing)


def test_turbo02_self_intersecting_section_fails_closed() -> None:
    section = BladeSection(
        span=0.5,
        radius_mm=100.0,
        chord_mm=20.0,
        stagger_deg=10.0,
        thickness=ThicknessDistribution(
            thickness_ratio=0.1, trailing_edge_thickness_ratio=0.0
        ),
        leading_edge_radius_mm=0.2,
        trailing_edge_radius_mm=0.0,
    )
    findings = check_section(section, n_surface=9, n_edge=4)
    assert findings
    assert any(item.code == "SECTION_INVALID" for item in findings)


def test_turbo02_topology_change_receipt_flags_count_changes() -> None:
    before = build_axial().row_body()
    after = build_axial(row=axial_row(periodicity=5)).row_body()
    receipt = topology_change_receipt(before, after)
    assert receipt.requires_remesh
    assert receipt.before_digest != receipt.after_digest
    assert len(receipt.digest()) == 64

    same = topology_change_receipt(before, build_axial().row_body())
    assert same.changes == ()
    assert same.requires_remesh is False


# ------------------------------------------------------------------------- CAD
def test_turbo02_cad_solids_are_real_when_kernel_is_available() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    from aeroworkbench_turbomachinery.geometry import (
        blade_shape,
        fluid_sector_shape,
        solid_receipt,
    )

    geometry = build_axial(row=axial_row(periodicity=3))
    blade = solid_receipt("blade", blade_shape(geometry, 0))
    assert blade.valid
    assert blade.volume_mm3 > 0.0
    assert blade.face_count > 0

    fluid = solid_receipt("fluid", fluid_sector_shape(geometry))
    assert fluid.valid
    assert fluid.volume_mm3 > 0.0
    assert fluid.volume_mm3 != pytest.approx(blade.volume_mm3)

    longer = build_axial(
        row=axial_row(periodicity=3),
        sections=tuple(
            section_from_payload(
                {**item, "chordMm": float(item["chordMm"]) * 1.5}
            )
            for item in load_fixture("axial_row.json")["sections"]
        ),
    )
    assert solid_receipt("longer", blade_shape(longer, 0)).volume_mm3 > blade.volume_mm3


def test_turbo02_radial_cad_solids_are_real_when_kernel_is_available() -> None:
    kernel = probe_cad()
    if not kernel.available:
        pytest.skip("CAD kernel unavailable")
    from aeroworkbench_turbomachinery.geometry import (
        radial_blade_shape,
        solid_receipt,
    )

    geometry = build_radial()
    blade = solid_receipt("radial-blade", radial_blade_shape(geometry, 0))
    assert blade.valid
    assert blade.volume_mm3 > 0.0


def test_turbo02_stacking_axis_offset_changes_geometry() -> None:
    from dataclasses import replace

    section = axial_sections()[0]
    base = place_section(
        section, center=(100.0, 0.0, 0.0), theta_rad=0.0, meridional_angle_rad=0.0
    )
    stacked = place_section(
        replace(section, stack_offset_mm=5.0, stacking_axis="radial"),
        center=(100.0, 0.0, 0.0),
        theta_rad=0.0,
        meridional_angle_rad=0.0,
    )
    assert base != stacked
    axial_stack = place_section(
        replace(section, stack_offset_mm=5.0, stacking_axis="axial"),
        center=(100.0, 0.0, 0.0),
        theta_rad=0.0,
        meridional_angle_rad=0.0,
    )
    assert stacked != axial_stack
    assert section_digest(
        replace(section, stack_offset_mm=5.0)
    ) != section_digest(section)


def test_turbo02_row_references_turbo01_row_and_architecture_by_id() -> None:
    row = axial_row()
    geometry = build_axial(row=row, architecture_id="turbo01-single-ducted-fan")
    assert geometry.row_id == row.row_id
    assert geometry.architecture_id == "turbo01-single-ducted-fan"
    assert all(
        key.startswith(f"{row.row_id}.") for key in geometry.semantic_keys()
    )
    definitions = geometry.cad_parameter_defs()
    assert any(item.name == "fan-rotor.hubRadius" for item in definitions)


def test_turbo02_mixed_flow_uses_the_same_contracts() -> None:
    payload = radial_payload()
    mixed = build_radial_blade_row(
        radial_row(row_id="mixed-rotor", family="mixed"),
        hub_contour=contour_from_payload(payload["hubContour"]),
        shroud_contour=contour_from_payload(payload["shroudContour"]),
        sections=tuple(section_from_payload(item) for item in payload["sections"]),
    )
    assert mixed.family == "mixed"
    assert mixed.blade_body(0).is_closed()
    assert blocking(mixed.validate()) == ()


def test_turbo02_stage_composes_sliding_interface_and_declared_ports() -> None:
    from aeroworkbench_turbomachinery.geometry import (
        build_stage_fluid_domain,
        port_patch,
    )

    rotor = build_row_fluid_domain(build_axial())
    stator = build_row_fluid_domain(
        build_axial(
            row=axial_row(
                row_id="outlet-stator",
                role="turning_only",
                frame="stationary",
                shaft=None,
            ),
            axial_location_mm=30.0,
        )
    )
    stage = build_stage_fluid_domain(rotor, stator, stage_id="fan-stage")
    assert stage.interfaces
    assert stage.interfaces[0].kind == "interface"
    assert stage.interfaces[0].conformal is False
    assert blocking(stage.validate()) == ()

    port = port_patch(
        patch_id="fan-rotor.fluid.bleed",
        kind="bleed",
        radius_mm=140.0,
        z_mm=0.0,
        theta_rad=0.2,
        width_rad=0.3,
        half_height_mm=2.0,
    )
    ported = build_row_fluid_domain(build_axial(), ports=(port,))
    assert "bleed" in set(ported.body.roles())
    assert blocking(ported.validate()) == ()


def test_turbo02_semantic_bindings_reference_row_components() -> None:
    geometry = build_axial()
    bindings = geometry.semantic_bindings()
    assert bindings
    body_ids = {body.body_id for body in geometry.row_bodies()}
    assert {binding.component for binding in bindings} <= body_ids

    radial = build_radial()
    assert any("splitter" in binding.component for binding in radial.semantic_bindings())


def test_turbo02_generic_layer_owns_no_product_names() -> None:
    forbidden = [
        "".join(pair)
        for pair in (("edf", "-"), ("gas", "turbine"), ("turbo", "fan"), ("aero", "engine"))
    ]
    package = (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "turbomachinery"
        / "aeroworkbench_turbomachinery"
        / "geometry"
    )
    text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in package.glob("*.py")
    )
    assert [token for token in forbidden if token in text] == []
