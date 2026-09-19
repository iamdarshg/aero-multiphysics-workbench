"""AIRFRAME 03: generic mass properties, packaging, and CG/inertia closure.

Deterministic, hand-computable fixtures prove the parallel-axis composition,
provenance, packaging/keep-out screening, generic CG and static-margin
constraints, the structural-participant seam, and design-space invalidation.
No hidden default mass is ever injected; malformed input fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe import InertiaTensor, MassProperties, Quantity, Vec3
from aeroworkbench_airframe.mass import (
    FEASIBLE,
    INFEASIBLE,
    PREFLIGHT_INVALID,
    Axis,
    AxisRange,
    BoundingBox,
    CenterOfGravityRange,
    InstallationTransform,
    MassBreakdown,
    MassCategory,
    MassClosureError,
    MassItem,
    MassItemSource,
    MassParticipantError,
    MassUpdate,
    PackageVolume,
    PackageVolumeKind,
    PackagingLayout,
    Placement,
    StaticMarginConstraint,
    aggregate_mass_properties,
    apply_participants,
    axis_rotation,
    close_mass_breakdown,
    evaluate_cog_constraints,
    evaluate_mass_feasibility,
    evaluate_packaging,
    is_orthonormal,
    is_positive_definite,
    mass_change_sections,
    mass_invalidated_families,
)
from aeroworkbench_core.types import FidelityLevel, ResultSource

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "airframe" / "mass"
_BREAKDOWN = "two_mass_breakdown.json"
_EXPECTED = "expected_aggregate.json"


def _load(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _vec3(payload: dict[str, Any]) -> Vec3:
    return Vec3(payload["x"], payload["y"], payload["z"], payload["unit"], payload["frame"])


def _inertia(payload: dict[str, Any]) -> InertiaTensor:
    unit = "kg.m2"
    return InertiaTensor(
        ixx=Quantity(payload["ixx"], unit),
        iyy=Quantity(payload["iyy"], unit),
        izz=Quantity(payload["izz"], unit),
        ixy=Quantity(payload["ixy"], unit),
        ixz=Quantity(payload["ixz"], unit),
        iyz=Quantity(payload["iyz"], unit),
        frame=payload["frame"],
    )


def _source(payload: dict[str, Any] | None = None, **overrides: Any) -> MassItemSource:
    base: dict[str, Any] = payload or {
        "source": "analytical",
        "fidelity": "analytical",
        "method": "unit test",
        "reference": "airframe03",
        "revision": "1",
    }
    values = {**base, **overrides}
    return MassItemSource(
        source=ResultSource(values["source"]),
        fidelity=FidelityLevel(values["fidelity"]),
        method=values["method"],
        reference=values["reference"],
        revision=values["revision"],
    )


def _installation(payload: dict[str, Any]) -> InstallationTransform:
    rotation = tuple(tuple(float(c) for c in row) for row in payload["rotation"])
    return InstallationTransform(
        from_frame=payload["fromFrame"],
        to_frame=payload["toFrame"],
        translation=_vec3(payload["translation"]),
        rotation=rotation,  # type: ignore[arg-type]
    )


def _item(payload: dict[str, Any]) -> MassItem:
    return MassItem(
        item_id=payload["id"],
        category=MassCategory(payload["category"]),
        mass=Quantity(payload["mass"]["value"], payload["mass"]["unit"]),
        cg=_vec3(payload["cg"]),
        inertia=_inertia(payload["inertia"]),
        installation=_installation(payload["installation"]),
        source=_source(payload["source"]),
    )


def _breakdown() -> MassBreakdown:
    data = _load(_BREAKDOWN)
    return MassBreakdown(
        vehicle_id=data["vehicleId"],
        frame=data["frame"],
        items=tuple(_item(item) for item in data["items"]),
    )


def _point_item(item_id: str, mass_kg: float, x_m: float) -> MassItem:
    unit = "kg.m2"
    return MassItem(
        item_id=item_id,
        category=MassCategory.OTHER,
        mass=Quantity(mass_kg, "kg"),
        cg=Vec3(x_m, 0.0, 0.0, "m", "body"),
        inertia=InertiaTensor(
            ixx=Quantity(1.0, unit),
            iyy=Quantity(1.0, unit),
            izz=Quantity(1.0, unit),
            ixy=Quantity(0.0, unit),
            ixz=Quantity(0.0, unit),
            iyz=Quantity(0.0, unit),
            frame="body",
        ),
        installation=InstallationTransform.identity("body"),
        source=_source(),
    )


def test_airframe03_fixture_matches_analytic_aggregate() -> None:
    aggregate = aggregate_mass_properties(_breakdown())
    expected = _load(_EXPECTED)
    assert aggregate.total_mass.value_si == pytest.approx(expected["mass"])
    assert aggregate.cg.value_si == pytest.approx(tuple(expected["cg"]))
    assert aggregate.inertia.ixx.value_si == pytest.approx(expected["ixx"])
    assert aggregate.inertia.iyy.value_si == pytest.approx(expected["iyy"])
    assert aggregate.inertia.izz.value_si == pytest.approx(expected["izz"])
    assert aggregate.inertia.ixy.value_si == pytest.approx(expected["ixy"])
    assert aggregate.feasible


def test_airframe03_moving_a_component_changes_cg_deterministically() -> None:
    base = _breakdown()
    payload = base.item("payload")
    moved = base.with_item(
        MassItem(
            item_id=payload.item_id,
            category=payload.category,
            mass=payload.mass,
            cg=Vec3(0.3, 0.0, 0.0, "m", "body"),
            inertia=payload.inertia,
            installation=payload.installation,
            source=payload.source,
        )
    )
    first = aggregate_mass_properties(moved)
    second = aggregate_mass_properties(moved)
    assert first.cg.value_si[0] == pytest.approx((2.0 * 0.3 + 2.0 * -0.5) / 4.0)
    assert first.as_dict() == second.as_dict()
    assert moved.content_hash != base.content_hash


def test_airframe03_rotation_moves_inertia_axes() -> None:
    unit = "kg.m2"
    item = MassItem(
        item_id="rotor",
        category=MassCategory.PROPULSION,
        mass=Quantity(1.0, "kg"),
        cg=Vec3(0.0, 0.0, 0.0, "m", "local"),
        inertia=InertiaTensor(
            ixx=Quantity(1.0, unit),
            iyy=Quantity(2.0, unit),
            izz=Quantity(3.0, unit),
            ixy=Quantity(0.0, unit),
            ixz=Quantity(0.0, unit),
            iyz=Quantity(0.0, unit),
            frame="local",
        ),
        installation=InstallationTransform(
            from_frame="local",
            to_frame="body",
            translation=Vec3(0.0, 0.0, 0.0, "m", "body"),
            rotation=axis_rotation("z", Quantity(90.0, "deg")),
        ),
        source=_source(),
    )
    aggregate = aggregate_mass_properties(
        MassBreakdown(vehicle_id="rotor", frame="body", items=(item,))
    )
    assert aggregate.inertia.ixx.value_si == pytest.approx(2.0)
    assert aggregate.inertia.iyy.value_si == pytest.approx(1.0)
    assert aggregate.inertia.izz.value_si == pytest.approx(3.0)


def test_airframe03_single_offset_item_inertia_is_position_invariant() -> None:
    unit = "kg.m2"
    item = MassItem(
        item_id="ballast",
        category=MassCategory.OTHER,
        mass=Quantity(1.0, "kg"),
        cg=Vec3(0.0, 0.0, 0.0, "m", "local"),
        inertia=InertiaTensor(
            ixx=Quantity(1.0, unit),
            iyy=Quantity(2.0, unit),
            izz=Quantity(3.0, unit),
            ixy=Quantity(0.0, unit),
            ixz=Quantity(0.0, unit),
            iyz=Quantity(0.0, unit),
            frame="local",
        ),
        installation=InstallationTransform(
            from_frame="local",
            to_frame="body",
            translation=Vec3(1.0, 2.0, 3.0, "m", "body"),
        ),
        source=_source(),
    )
    aggregate = aggregate_mass_properties(
        MassBreakdown(vehicle_id="ballast", frame="body", items=(item,))
    )
    assert aggregate.cg.value_si == pytest.approx((1.0, 2.0, 3.0))
    assert aggregate.inertia.ixx.value_si == pytest.approx(1.0)
    assert aggregate.inertia.iyy.value_si == pytest.approx(2.0)
    assert aggregate.inertia.izz.value_si == pytest.approx(3.0)


def test_airframe03_hash_is_order_independent_and_stable() -> None:
    data = _load(_BREAKDOWN)
    items = tuple(_item(item) for item in data["items"])
    forward = MassBreakdown(data["vehicleId"], data["frame"], items)
    reversed_items = MassBreakdown(data["vehicleId"], data["frame"], tuple(reversed(items)))
    assert forward.content_hash == reversed_items.content_hash
    assert forward.content_hash == _breakdown().content_hash


def test_airframe03_closure_report_carries_full_provenance() -> None:
    report = close_mass_breakdown(_breakdown())
    assert report.feasible and report.closure_passed
    names = {check.name for check in report.checks}
    assert names == {"component-mass-sum", "positive-total-mass", "inertia-positive-definite"}
    assert len(report.meta.input_hash) == 64
    assert report.meta.source is ResultSource.ANALYTICAL
    assert report.meta.software.name == "aeroworkbench-airframe-mass"
    assert report.meta.validity.valid
    assert dict(report.meta.units)["mass"] == "kg"
    assert report.content_hash == close_mass_breakdown(_breakdown()).content_hash


def test_airframe03_empty_and_nonpositive_items_fail_closed() -> None:
    with pytest.raises(ValueError, match="EMPTY_MASS_BREAKDOWN"):
        MassBreakdown(vehicle_id="empty", frame="body", items=())
    with pytest.raises(ValueError, match="NONPOSITIVE_MASS_ITEM"):
        MassItem(
            item_id="bad",
            category=MassCategory.OTHER,
            mass=Quantity(0.0, "kg"),
            cg=Vec3(0.0, 0.0, 0.0, "m", "body"),
            inertia=_inertia(_load(_BREAKDOWN)["items"][0]["inertia"]),
            installation=InstallationTransform.identity("body"),
            source=_source(),
        )
    with pytest.raises(TypeError):
        MassItem(  # type: ignore[call-arg]
            item_id="no-mass",
            category=MassCategory.OTHER,
            cg=Vec3(0.0, 0.0, 0.0, "m", "body"),
            inertia=_inertia(_load(_BREAKDOWN)["items"][0]["inertia"]),
            installation=InstallationTransform.identity("body"),
            source=_source(),
        )


def test_airframe03_non_positive_definite_inertia_fails_closed() -> None:
    unit = "kg.m2"
    item = MassItem(
        item_id="skewed",
        category=MassCategory.OTHER,
        mass=Quantity(1.0, "kg"),
        cg=Vec3(0.0, 0.0, 0.0, "m", "body"),
        inertia=InertiaTensor(
            ixx=Quantity(1.0, unit),
            iyy=Quantity(1.0, unit),
            izz=Quantity(1.0, unit),
            ixy=Quantity(100.0, unit),
            ixz=Quantity(0.0, unit),
            iyz=Quantity(0.0, unit),
            frame="body",
        ),
        installation=InstallationTransform.identity("body"),
        source=_source(),
    )
    breakdown = MassBreakdown(vehicle_id="skewed", frame="body", items=(item,))
    with pytest.raises(MassClosureError, match="MASS_CLOSURE_VIOLATION"):
        aggregate_mass_properties(breakdown)
    report = close_mass_breakdown(breakdown)
    assert not report.closure_passed
    assert evaluate_mass_feasibility(breakdown).status == PREFLIGHT_INVALID


def test_airframe03_packaging_keepout_and_intersection() -> None:
    body = "body"
    source = _source()
    bay = PackageVolume(
        "bay",
        PackageVolumeKind.BAY,
        BoundingBox(body, Vec3(0.0, 0.0, 0.0, "m", body), Vec3(1.0, 1.0, 1.0, "m", body)),
        source,
    )
    keepout = PackageVolume(
        "keepout",
        PackageVolumeKind.KEEPOUT,
        BoundingBox(body, Vec3(0.4, 0.0, 0.0, "m", body), Vec3(0.6, 1.0, 1.0, "m", body)),
        source,
    )
    clashing = PackagingLayout(
        frame=body,
        volumes=(bay, keepout),
        placements=(
            Placement(
                "payload",
                BoundingBox(body, Vec3(0.5, 0.1, 0.1, "m", body), Vec3(0.9, 0.9, 0.9, "m", body)),
            ),
        ),
    )
    report = evaluate_packaging(clashing)
    codes = {finding.code for finding in report.findings}
    assert "KEEPOUT_INTERSECTION" in codes
    assert not report.feasible

    clear = PackagingLayout(
        frame=body,
        volumes=(bay, keepout),
        placements=(
            Placement(
                "payload",
                BoundingBox(body, Vec3(0.7, 0.1, 0.1, "m", body), Vec3(0.9, 0.9, 0.9, "m", body)),
            ),
        ),
    )
    clear_report = evaluate_packaging(clear)
    assert clear_report.feasible
    assert clear_report.meta.validity.valid


def test_airframe03_packaging_component_intersection_and_bay_containment() -> None:
    body = "body"
    source = _source()
    bay = PackageVolume(
        "bay",
        PackageVolumeKind.BAY,
        BoundingBox(body, Vec3(0.0, 0.0, 0.0, "m", body), Vec3(1.0, 1.0, 1.0, "m", body)),
        source,
    )
    overlapping = PackagingLayout(
        frame=body,
        volumes=(bay,),
        placements=(
            Placement(
                "a",
                BoundingBox(
                    body, Vec3(0.1, 0.1, 0.1, "m", body), Vec3(0.5, 0.5, 0.5, "m", body)
                ),
            ),
            Placement(
                "b",
                BoundingBox(
                    body, Vec3(0.3, 0.3, 0.3, "m", body), Vec3(0.7, 0.7, 0.7, "m", body)
                ),
            ),
        ),
    )
    overlap_codes = {item.code for item in evaluate_packaging(overlapping).findings}
    assert "COMPONENT_INTERSECTION" in overlap_codes

    outside = PackagingLayout(
        frame=body,
        volumes=(bay,),
        placements=(
            Placement(
                "c",
                BoundingBox(
                    body, Vec3(1.2, 0.1, 0.1, "m", body), Vec3(1.4, 0.4, 0.4, "m", body)
                ),
            ),
        ),
    )
    assert "OUTSIDE_PACKAGING_BAY" in {item.code for item in evaluate_packaging(outside).findings}


def test_airframe03_cog_range_and_static_margin_constraints() -> None:
    mass_properties = aggregate_mass_properties(_breakdown()).mass_properties
    inside = CenterOfGravityRange(
        "cg-x",
        AxisRange(Axis.X, "body", lower=Quantity(-0.1, "m"), upper=Quantity(0.1, "m")),
        _source(),
    )
    outside = CenterOfGravityRange(
        "cg-x-tight",
        AxisRange(Axis.X, "body", lower=Quantity(0.5, "m")),
        _source(),
    )
    passing = evaluate_cog_constraints(mass_properties, ranges=(inside,))
    failing = evaluate_cog_constraints(mass_properties, ranges=(outside,))
    assert passing.feasible and failing.feasible is False
    assert failing.reasons

    margin = StaticMarginConstraint(
        "static-margin",
        Axis.X,
        Vec3(1.0, 0.0, 0.0, "m", "body"),
        Quantity(1.0, "m"),
        _source(),
        minimum=0.5,
    )
    assert margin.margin(mass_properties.cg) == pytest.approx(1.0)
    assert evaluate_cog_constraints(mass_properties, static_margins=(margin,)).feasible
    demanding = StaticMarginConstraint(
        "static-margin-tight",
        Axis.X,
        Vec3(1.0, 0.0, 0.0, "m", "body"),
        Quantity(1.0, "m"),
        _source(),
        minimum=2.0,
    )
    assert not evaluate_cog_constraints(mass_properties, static_margins=(demanding,)).feasible


def test_airframe03_feasibility_surfaces_infeasible_outputs() -> None:
    breakdown = _breakdown()
    assert evaluate_mass_feasibility(breakdown).status == FEASIBLE

    tight = CenterOfGravityRange(
        "cg-x-tight",
        AxisRange(Axis.X, "body", lower=Quantity(0.5, "m")),
        _source(),
    )
    assert evaluate_mass_feasibility(breakdown, cg_ranges=(tight,)).status == INFEASIBLE

    body = "body"
    keepout_layout = PackagingLayout(
        frame=body,
        volumes=(
            PackageVolume(
                "keepout",
                PackageVolumeKind.KEEPOUT,
                BoundingBox(body, Vec3(0.0, 0.0, 0.0, "m", body), Vec3(1.0, 1.0, 1.0, "m", body)),
                _source(),
            ),
        ),
        placements=(
            Placement(
                "payload",
                BoundingBox(body, Vec3(0.1, 0.1, 0.1, "m", body), Vec3(0.9, 0.9, 0.9, "m", body)),
            ),
        ),
    )
    report = evaluate_mass_feasibility(breakdown, layout=keepout_layout)
    assert report.status == INFEASIBLE
    assert report.reasons


def test_airframe03_participant_updates_mass_distribution() -> None:
    breakdown = _breakdown()

    class StructureSizing:
        participant_id = "structure-sizing"

        def mass_updates(self, context: dict[str, Any]) -> tuple[MassUpdate, ...]:
            assert context["load_case"] == "ultimate"
            return (MassUpdate(item_id="payload", mass=Quantity(3.0, "kg"), reason="resized"),)

    update = apply_participants(breakdown, (StructureSizing(),), {"load_case": "ultimate"})
    assert update.updated_item_ids == ("payload",)
    assert update.added_item_ids == ()
    aggregate = aggregate_mass_properties(update.breakdown)
    assert aggregate.total_mass.value_si == pytest.approx(5.0)
    assert aggregate.cg.value_si[0] == pytest.approx((3.0 * 0.5 + 2.0 * -0.5) / 5.0)

    with pytest.raises(MassParticipantError, match="NEW_MASS_ITEM_REQUIRES_FULL_PROPERTIES"):
        apply_participants(
            breakdown,
            (
                _FixedParticipant(
                    MassUpdate(item_id="unknown", mass=Quantity(1.0, "kg"), reason="partial")
                ),
            ),
            {},
        )

    unit = "kg.m2"
    full = MassUpdate(
        item_id="wing",
        mass=Quantity(1.0, "kg"),
        reason="added",
        cg=Vec3(0.0, 0.0, 0.0, "m", "body"),
        inertia=InertiaTensor(
            ixx=Quantity(1.0, unit),
            iyy=Quantity(1.0, unit),
            izz=Quantity(1.0, unit),
            ixy=Quantity(0.0, unit),
            ixz=Quantity(0.0, unit),
            iyz=Quantity(0.0, unit),
            frame="body",
        ),
        installation=InstallationTransform.identity("body"),
        category=MassCategory.STRUCTURE,
        source=_source(),
    )
    added = apply_participants(breakdown, (_FixedParticipant(full),), {})
    assert added.added_item_ids == ("wing",)


class _FixedParticipant:
    participant_id = "fixed"

    def __init__(self, update: MassUpdate) -> None:
        self._update = update

    def mass_updates(self, context: dict[str, Any]) -> tuple[MassUpdate, ...]:
        return (self._update,)


def test_airframe03_native_mass_source_requires_provenance() -> None:
    with pytest.raises(ValueError, match="NATIVE_MASS_SOURCE_REQUIRES_DIGEST_AND_SOFTWARE"):
        MassItemSource(
            source=ResultSource.NATIVE_SOLVER,
            fidelity=FidelityLevel.ANALYTICAL,
            method="fea",
            reference="run",
        )


def test_airframe03_design_space_invalidation_reuses_coupling_dag() -> None:
    before = aggregate_mass_properties(_breakdown()).mass_properties
    moved_item = _point_item("payload", 2.0, 0.25)
    after_breakdown = _breakdown().with_item(moved_item)
    after = aggregate_mass_properties(after_breakdown).mass_properties
    assert mass_change_sections(before, before) == ()
    assert mass_change_sections(before, after) == ("parameters",)
    assert {"geometry", "mesh", "analysis"} <= set(mass_invalidated_families(before, after))


def test_airframe03_linalg_helpers_are_deterministic() -> None:
    rotation = axis_rotation("x", Quantity(30.0, "deg"))
    assert is_orthonormal(rotation)
    assert is_positive_definite(((2.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0)))
    assert not is_positive_definite(((1.0, 2.0, 0.0), (2.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    assert isinstance(_breakdown().item("payload").mass, Quantity)
    assert isinstance(aggregate_mass_properties(_breakdown()).mass_properties, MassProperties)
