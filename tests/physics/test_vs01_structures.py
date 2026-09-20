"""VS 01: generative airframe structural architecture and automatic sizing.

Deterministic tiny fixtures drive the generic structural participants: typed
internal structure generated from a wing/body/control-surface outer geometry,
bounded automatic sizing against aero/trim/mass load seams, strength and local
buckling checks with material allowables, composite ply/laminate preservation,
mass feedback into the AIRFRAME mass/CG/inertia breakdown, equivalent stiffness
for the aeroelastic loop, and a capability-gated native Code_Aster seam that
fails closed. No solver runs; every assertion is a pure contract check.

Fixture data lives in ``tests/vehicle_systems/structures``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_airframe import (
    IDENTITY,
    InertiaTensor,
    Quantity,
    Vec3,
)
from aeroworkbench_airframe.aero_geometry import (
    AirfoilProfile,
    ControlSurface,
    LiftingSurface,
    LoftedBody,
    Planform,
)
from aeroworkbench_airframe.mass import (
    InstallationTransform,
    MassBreakdown,
    MassCategory,
    MassItem,
    MassItemSource,
    aggregate_mass_properties,
    apply_participants,
)
from aeroworkbench_composites import PlyStrength, StrengthLibrary
from aeroworkbench_core.types import FidelityLevel, ResultSource
from aeroworkbench_materials import (
    LaminateRevision,
    MaterialDatabase,
    Ply,
    effective_orthotropic,
    material_digest,
)
from aeroworkbench_vehicle_systems.structures import (
    SOFTWARE_IDENTITY,
    STRUCTURAL_PARTICIPANTS,
    AeroLoadSeam,
    ArchitectureKind,
    CodeAsterStructureMapping,
    LoadSource,
    MassLoadSeam,
    MemberKind,
    MemberMaterial,
    NativeStructureRequest,
    SizingOptions,
    StructuralConstraintError,
    StructuralLayoutError,
    StructuralManufacturingLimits,
    StructuralMassParticipant,
    StructuresCapabilityUnavailable,
    TrimLoadSeam,
    apply_structure_mass,
    evaluate_member_margins,
    generate_body_architecture,
    generate_control_surface_architecture,
    generate_wing_architecture,
    load_case_from_aero,
    load_case_from_landing_gear,
    load_case_from_mass,
    load_case_from_propulsor,
    load_case_from_trim,
    map_structure_to_code_aster,
    margin_of_safety,
    native_structure_capability,
    participant_ids,
    participant_native_states,
    require_native_structure,
    screen_structure_manufacturability,
    size_architecture,
    solve_native_structure,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "vehicle_systems" / "structures"
_ALUMINIUM = "aluminium-6061-t6"
_CARBON = "carbon-epoxy-ud-ply"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _material(material_id: str = _ALUMINIUM) -> MemberMaterial:
    return MemberMaterial(material=MaterialDatabase.seeded().get_material(material_id))


def _surface(
    payload: dict[str, Any], *, surface_id: str = "wing", span_scale: float = 1.0
) -> LiftingSurface:
    planform = Planform(
        span_mm=payload["span_mm"] * span_scale,
        root_chord_mm=payload["root_chord_mm"],
        tip_chord_mm=payload["tip_chord_mm"],
        sweep_deg=payload.get("sweep_deg", 0.0),
        dihedral_deg=payload.get("dihedral_deg", 0.0),
    )
    profile = AirfoilProfile(thickness_ratio=payload["profile_thickness_ratio"])
    return LiftingSurface.from_planform(
        surface_id,
        "wing",
        planform,
        profile,
        frame=payload.get("plane", "aerodynamic"),
        n_stations=payload["n_stations"],
    )


def _composite_material(payload: dict[str, Any]) -> MemberMaterial:
    carbon = MaterialDatabase.seeded().get_material(_CARBON)
    angles = payload["ply_angles_deg"]
    plies = tuple(
        Ply(material=carbon, angle_deg=angle, thickness_m=payload["ply_thickness_m"])
        for angle in angles
    )
    laminate = LaminateRevision(laminate_id="vs01-skin", revision="r1", plies=plies)
    strength_payload = _fixture("composite_ply_strengths.json")
    strength = PlyStrength(material_digest=material_digest(carbon), **strength_payload)
    library = StrengthLibrary((strength,))
    return MemberMaterial(
        material=effective_orthotropic(laminate),
        laminate=laminate,
        strengths=library,
    )


def _load_set(
    payload: dict[str, Any],
    component_id: str,
    *,
    span_m: float | None = None,
    force_scale: float = 1.0,
):
    from aeroworkbench_vehicle_systems.structures import StructuralLoadSet

    resolved_span_m = span_m
    if resolved_span_m is None:
        if "span_mm" in payload:
            resolved_span_m = payload["span_mm"] / 1000.0
        else:
            spine = payload["spine_mm"]
            stations = [point[2] for point in spine]
            resolved_span_m = (max(stations) - min(stations)) / 1000.0
    load = payload["load"]
    seam = AeroLoadSeam(
        component_id=component_id,
        normal_force_n=load["normal_force_n"] * force_scale,
        span_m=resolved_span_m,
        tip_to_root_ratio=load.get("tip_to_root_ratio", 0.6),
        axial_force_n=load.get("axial_force_n", 0.0),
    )
    case = load_case_from_aero(seam, case_id="ultimate")
    return StructuralLoadSet(component_id=component_id, load_cases=(case,))


def _payload_breakdown(frame: str) -> MassBreakdown:
    local = f"{frame}-payload"
    item = MassItem(
        item_id="payload",
        category=MassCategory.PAYLOAD,
        mass=Quantity(value=10.0, unit="kg"),
        cg=Vec3(x=0.0, y=0.0, z=0.0, unit="m", frame=local),
        inertia=InertiaTensor(
            ixx=Quantity(1.0, "kg.m2"),
            iyy=Quantity(1.0, "kg.m2"),
            izz=Quantity(1.0, "kg.m2"),
            ixy=Quantity(0.0, "kg.m2"),
            ixz=Quantity(0.0, "kg.m2"),
            iyz=Quantity(0.0, "kg.m2"),
            frame=local,
        ),
        installation=InstallationTransform(
            from_frame=local,
            to_frame=frame,
            translation=Vec3(x=0.0, y=0.0, z=0.0, unit="m", frame=frame),
            rotation=IDENTITY,
        ),
        source=MassItemSource(
            source=ResultSource.ANALYTICAL,
            fidelity=FidelityLevel.ANALYTICAL,
            method="fixture",
            reference="vs01-fixture",
        ),
    )
    return MassBreakdown(vehicle_id="vs01-vehicle", frame=frame, items=(item,))


# -- A. generative architecture ------------------------------------------------


def test_vs01_wing_layout_generates_typed_members() -> None:
    payload = _fixture("wing_layout.json")
    surface = _surface(payload)
    architecture = generate_wing_architecture(
        surface,
        material=_material(),
        kind=ArchitectureKind(payload["architecture_kind"]),
        spar_count=payload["spar_count"],
        rib_count=payload["rib_count"],
        stringer_count=payload["stringer_count"],
    )
    kinds = {member.kind for member in architecture.members}
    assert MemberKind.SPAR_CAP in kinds
    assert MemberKind.SPAR_WEB in kinds
    assert MemberKind.RIB in kinds
    assert MemberKind.STRINGER in kinds
    assert MemberKind.SKIN in kinds
    assert all(
        member.geometry.component_id == surface.surface_id
        for member in architecture.members
    )
    assert all(
        member.geometry.station_fraction[0] < member.geometry.station_fraction[1]
        for member in architecture.members
    )
    assert len(architecture.digest) == 64
    assert (
        architecture.digest
        == generate_wing_architecture(
            surface,
            material=_material(),
            kind=ArchitectureKind(payload["architecture_kind"]),
            spar_count=payload["spar_count"],
            rib_count=payload["rib_count"],
            stringer_count=payload["stringer_count"],
        ).digest
    )


def test_vs01_body_and_control_surface_layouts() -> None:
    body_payload = _fixture("fuselage_layout.json")
    body = LoftedBody.from_spine(
        "fuselage",
        "fuselage",
        tuple(tuple(point) for point in body_payload["spine_mm"]),
        tuple(body_payload["widths_mm"]),
        tuple(body_payload["heights_mm"]),
        frame="body-local",
        exponent=body_payload["exponent"],
    )
    body_architecture = generate_body_architecture(
        body,
        material=_material(),
        frame_count=body_payload["frame_count"],
        stringer_count=body_payload["stringer_count"],
    )
    body_kinds = {member.kind for member in body_architecture.members}
    assert MemberKind.FRAME in body_kinds
    assert MemberKind.STRINGER in body_kinds
    assert MemberKind.SKIN in body_kinds

    control_payload = _fixture("control_surface_layout.json")
    parent = _surface(control_payload, surface_id="wing")
    control_data = control_payload["control"]
    control = ControlSurface(
        control_id=control_data["control_id"],
        parent_id="wing",
        kind=control_data["kind"],
        hinge_fraction=control_data["hinge_fraction"],
        span_fraction=tuple(control_data["span_fraction"]),
    )
    control_architecture = generate_control_surface_architecture(
        control,
        parent,
        material=_material(),
        rib_count=control_payload["rib_count"],
    )
    control_kinds = {member.kind for member in control_architecture.members}
    assert MemberKind.SPAR_CAP in control_kinds
    assert MemberKind.CONTROL_SURFACE in control_kinds
    assert len(control_architecture.digest) == 64


def test_vs01_architecture_rejects_invalid_inputs() -> None:
    payload = _fixture("wing_layout.json")
    surface = _surface(payload)
    with pytest.raises(StructuralLayoutError):
        generate_wing_architecture(
            surface,
            material=_material(),
            spar_root_fraction=0.9,
            spar_tip_fraction=0.1,
        )
    with pytest.raises(StructuralLayoutError):
        generate_wing_architecture(surface, material=_material(), rib_count=0)


# -- B. typed load seams -------------------------------------------------------


def test_vs01_load_cases_from_seams_hand_computable() -> None:
    span_m = 6.0
    aero = AeroLoadSeam(
        component_id="wing",
        normal_force_n=40000.0,
        span_m=span_m,
        tip_to_root_ratio=0.6,
    )
    case = load_case_from_aero(aero, case_id="aero")
    assert case.source is LoadSource.EXTERNAL_AERO
    expected_moment = 40000.0 * span_m * (1.0 + 2.0 * 0.6) / (3.0 * (1.0 + 0.6))
    assert case.root_bending_moment_n_m() == pytest.approx(expected_moment)
    assert case.normal_force_n() == pytest.approx(40000.0)

    trim = TrimLoadSeam(
        component_id="wing", normal_force_n=40000.0, span_m=span_m, load_factor=2.0
    )
    doubled = load_case_from_trim(trim, case_id="trim")
    assert doubled.load_factor == pytest.approx(2.0)
    assert doubled.root_bending_moment_n_m() == pytest.approx(2.0 * expected_moment)

    mass = MassLoadSeam(
        component_id="wing", mass_kg=100.0, span_m=span_m, load_factor=3.0
    )
    inertial = load_case_from_mass(mass, case_id="inertia")
    assert inertial.normal_force_n() == pytest.approx(100.0 * 9.80665 * 3.0)
    assert inertial.source is LoadSource.MASS


# -- C. automatic sizing -------------------------------------------------------


def _sized_wing(force_scale: float = 1.0, span_scale: float = 1.0):
    payload = _fixture("wing_layout.json")
    surface = _surface(payload, span_scale=span_scale)
    scaled_payload = dict(payload)
    scaled_payload["span_mm"] = payload["span_mm"] * span_scale
    architecture = generate_wing_architecture(
        surface,
        material=_material(),
        kind=ArchitectureKind.WINGBOX,
        spar_count=payload["spar_count"],
        rib_count=payload["rib_count"],
        stringer_count=payload["stringer_count"],
    )
    load_set = _load_set(scaled_payload, surface.surface_id, force_scale=force_scale)
    return size_architecture(architecture, load_set)


def test_vs01_sizing_is_deterministic_and_reports_stiffness() -> None:
    first = _sized_wing()
    second = _sized_wing()
    assert first.digest == second.digest
    assert first.total_mass_kg == pytest.approx(second.total_mass_kg)
    assert first.stiffness.bending_stiffness_n_m2 == pytest.approx(
        second.stiffness.bending_stiffness_n_m2
    )
    assert first.total_mass_kg > 0.0
    assert first.stiffness.torsional_stiffness_n_m2 > 0.0
    assert first.stiffness.first_bending_frequency_hz > 0.0
    assert first.validity.passed is True
    for candidate in first.members:
        assert candidate.mass_kg > 0.0
        assert candidate.passed


def test_vs01_increased_load_and_span_resize_deterministically() -> None:
    baseline = _sized_wing(force_scale=1.0)
    loaded = _sized_wing(force_scale=3.0)
    spanned = _sized_wing(span_scale=2.0)
    assert loaded.total_mass_kg > baseline.total_mass_kg
    assert loaded.digest != baseline.digest
    assert spanned.total_mass_kg > baseline.total_mass_kg
    assert (
        spanned.stiffness.bending_stiffness_n_m2
        > baseline.stiffness.bending_stiffness_n_m2
    )


def test_vs01_constraints_reject_infeasible_candidates() -> None:
    payload = _fixture("wing_layout.json")
    surface = _surface(payload)
    architecture = generate_wing_architecture(
        surface,
        material=_material(),
        kind=ArchitectureKind.WINGBOX,
        spar_count=payload["spar_count"],
        rib_count=payload["rib_count"],
        stringer_count=payload["stringer_count"],
    )
    heavy = _load_set(payload, surface.surface_id, force_scale=1000.0)
    with pytest.raises(StructuralConstraintError) as excinfo:
        size_architecture(
            architecture,
            heavy,
            options=SizingOptions(maximum_thickness_m=0.003, safety_factor=2.0),
        )
    assert excinfo.value.violations
    tight = _load_set(payload, surface.surface_id, force_scale=1.0)
    with pytest.raises(StructuralConstraintError):
        size_architecture(
            architecture, tight, options=SizingOptions(deflection_limit_fraction=1.0e-4)
        )


@pytest.mark.parametrize(
    "kind",
    tuple(
        ArchitectureKind(item)
        for item in ("wingbox", "multi_spar", "monocoque", "semi_monocoque", "shell")
    ),
)
def test_vs01_structural_branches_are_deterministic(kind: ArchitectureKind) -> None:
    branch_fixture = _fixture("architecture_branches.json")
    assert kind.value in branch_fixture["branches"]
    payload = _fixture("wing_layout.json")
    surface = _surface(payload)
    architecture = generate_wing_architecture(
        surface,
        material=_material(),
        kind=kind,
        spar_count=payload["spar_count"],
        rib_count=payload["rib_count"],
        stringer_count=payload["stringer_count"],
    )
    loads = _load_set(payload, surface.surface_id)
    first = size_architecture(architecture, loads)
    second = size_architecture(architecture, loads)
    assert first.digest == second.digest
    assert first.total_mass_kg == pytest.approx(second.total_mass_kg)


def test_vs01_manufacturing_gate_rejects_structurally_feasible_design() -> None:
    sized = _sized_wing()
    limits = StructuralManufacturingLimits(
        process="sheet-metal",
        revision="r1",
        minimum_gauge_m=0.01,
        dimensional_tolerance_m=1.0e-6,
        maximum_dimensional_tolerance_m=1.0e-5,
    )
    with pytest.raises(StructuralConstraintError) as excinfo:
        screen_structure_manufacturability(sized, limits)
    assert excinfo.value.violations
    assert any("gauge" in item for item in excinfo.value.violations)


def test_vs01_landing_and_propulsion_adapters_change_sizing_mass() -> None:
    from aeroworkbench_vehicle_systems.landing_gear import (
        GearLoadCase,
        LoadCaseKind,
        result_meta,
    )
    from aeroworkbench_vehicle_systems.structures import StructuralLoadSet

    payload = _fixture("wing_layout.json")
    surface = _surface(payload)
    architecture = generate_wing_architecture(surface, material=_material())
    baseline = _sized_wing()
    landing = GearLoadCase(
        case_id="touchdown",
        kind=LoadCaseKind.TOUCHDOWN,
        gear_id="main",
        vertical_force_n=5000.0,
        drag_force_n=1000.0,
        side_force_n=500.0,
        sink_rate_m_s=None,
        meta=result_meta(model="fixture", inputs={"case": "landing"}, valid=True),
    )
    landing_loads = load_case_from_landing_gear(
        landing,
        component_id=surface.surface_id,
        span_m=architecture.reference_span_m,
        station_fraction=0.2,
    )
    propulsion_loads = load_case_from_propulsor(
        type(
            "PropulsorLoads",
            (),
            {
                "normal_force_n": 2000.0,
                "thrust_n": 5000.0,
                "torque_n_m": 1000.0,
                "pitching_moment_n_m": 500.0,
                "yawing_moment_n_m": 250.0,
                "provenance": type("Provenance", (), {"model": "fixture"})(),
            },
        )(),
        component_id=surface.surface_id,
        span_m=architecture.reference_span_m,
        station_fraction=0.35,
        case_id="propulsion",
    )
    landing_sized = size_architecture(
        architecture, StructuralLoadSet("wing", (landing_loads,))
    )
    propulsion_sized = size_architecture(
        architecture, StructuralLoadSet("wing", (propulsion_loads,))
    )
    assert landing_sized.total_mass_kg != pytest.approx(baseline.total_mass_kg)
    assert propulsion_sized.total_mass_kg != pytest.approx(baseline.total_mass_kg)


# -- D. margins and checks -----------------------------------------------------


def test_vs01_margins_are_reserve_factors() -> None:
    assert margin_of_safety(300.0, 100.0) == pytest.approx(3.0)
    assert margin_of_safety(300.0, 0.0) > 1.0
    sized = _sized_wing()
    for candidate in sized.members:
        assert candidate.margins
        for result in candidate.margins:
            assert result.passed
            assert result.margin >= 1.0
            assert result.unit
    assert any(
        result.name == "local-buckling"
        for candidate in sized.members
        for result in evaluate_member_margins(candidate.member, candidate.demand)
    )


# -- E. mass feedback ----------------------------------------------------------


def test_vs01_structural_mass_feeds_breakdown() -> None:
    sized = _sized_wing()
    breakdown = _payload_breakdown(sized.frame)
    update = apply_structure_mass(sized, breakdown)
    assert update.added_item_ids
    aggregate = aggregate_mass_properties(update.breakdown)
    expected = 10.0 + sized.total_mass_kg
    assert aggregate.total_mass.value_si == pytest.approx(expected, rel=1e-9)
    assert aggregate.cg.dimension == "length"
    assert aggregate.inertia.ixx.value_si > 0.0


def test_vs01_structural_mass_participant_protocol() -> None:
    sized = _sized_wing()
    breakdown = _payload_breakdown(sized.frame)
    participant = StructuralMassParticipant(sized)
    assert participant.participant_id
    update = apply_participants(breakdown, (participant,), {"frame": sized.frame})
    assert set(update.added_item_ids) == {
        f"structure.{member.member.member_id}" for member in sized.members
    }
    assert update.breakdown.content_hash == update.breakdown.content_hash


# -- F. aeroelastic and stiffness loop ----------------------------------------


def test_vs01_stiffness_feeds_aeroelastic_loop() -> None:
    sized = _sized_wing()
    inputs = sized.stiffness.to_aeroelastic_inputs()
    assert set(inputs) == {
        "frequency_hz",
        "areal_mass_kg_m2",
        "bending_stiffness_d11_n_m",
    }
    assert all(value > 0.0 for value in inputs.values())


# -- G. composites -------------------------------------------------------------


def test_vs01_composite_members_preserve_ply_semantics() -> None:
    payload = _fixture("composite_wing_layout.json")
    surface = _surface(payload, surface_id="composite-wing")
    material = _composite_material(payload)
    architecture = generate_wing_architecture(
        surface,
        material=material,
        kind=ArchitectureKind.WINGBOX,
        spar_count=payload["spar_count"],
        rib_count=payload["rib_count"],
        stringer_count=payload["stringer_count"],
    )
    load_set = _load_set(payload, surface.surface_id)
    sized = size_architecture(architecture, load_set)
    laminate_members = [
        candidate
        for candidate in sized.members
        if candidate.member.material.kind == "laminate"
    ]
    assert laminate_members
    for candidate in laminate_members:
        after = candidate.member.material
        assert after.laminate is not None
        assert after.ply_angles_deg == tuple(payload["ply_angles_deg"])
        assert after.ply_count == len(payload["ply_angles_deg"])
        assert after.laminate.total_thickness_m >= material.minimum_thickness_m
    cap = sized.member("spar-1-cap")
    assert cap.member.material.kind == "laminate"
    assert cap.member.material.laminate is not None
    assert cap.member.section.thickness_m == pytest.approx(
        cap.member.material.laminate.total_thickness_m
    )


# -- H. native seam ------------------------------------------------------------


def test_vs01_native_code_aster_mapping_and_fail_closed() -> None:
    sized = _sized_wing()
    mapping = map_structure_to_code_aster(sized)
    assert isinstance(mapping, CodeAsterStructureMapping)
    assert mapping.solver == "code_aster"
    assert len(mapping.digest) == 64
    mapped = {member_id for group in mapping.groups for member_id in group.member_ids}
    assert mapped == {member.member.member_id for member in sized.members}
    assert any(group.element_type == "POU_D_T" for group in mapping.groups)
    assert any(group.element_type == "DKT" for group in mapping.groups)
    assert native_structure_capability("code-aster-shell-beam").state == "unavailable"
    with pytest.raises(StructuresCapabilityUnavailable):
        require_native_structure("code-aster-shell-beam")
    request = NativeStructureRequest(
        requirement="code-aster-shell-beam",
        solver_name="code_aster",
        analysis="static",
        mapping=mapping,
        inputs_hash=mapping.inputs_hash,
    )
    with pytest.raises(StructuresCapabilityUnavailable):
        solve_native_structure(request)
    with pytest.raises(StructuresCapabilityUnavailable):
        solve_native_structure(request, present=True)


def test_vs01_participant_registry_covers_capabilities() -> None:
    ids = participant_ids()
    assert {"generative-layout", "preliminary-sizing", "structural-margins"} <= set(ids)
    assert len(STRUCTURAL_PARTICIPANTS) == len(ids)
    states = participant_native_states()
    assert states
    assert states[0]["state"] == "unavailable"


# -- I. result contract --------------------------------------------------------


def test_vs01_results_carry_source_fidelity_units_and_provenance() -> None:
    sized = _sized_wing()
    meta = sized.meta
    assert meta.source is ResultSource.ANALYTICAL
    assert meta.fidelity.value == "analytical"
    assert len(meta.inputs_hash) == 64
    assert meta.software.name == SOFTWARE_IDENTITY
    assert meta.validity.passed is True
    units = dict(meta.units)
    assert units["mass"] == "kg"
    assert units["length"] == "m"
    assert units["force"] == "N"
    assert units["stress"] == "Pa"
    assert meta.provenance.inputs_hash == meta.inputs_hash
    assert len(sized.digest) == 64
    assert sized.stiffness.digest == sized.stiffness.digest


def test_vs01_architecture_digest_is_content_addressed() -> None:
    payload = _fixture("wing_layout.json")
    surface = _surface(payload)
    other = _surface(payload, span_scale=2.0)
    first = generate_wing_architecture(surface, material=_material())
    second = generate_wing_architecture(other, material=_material())
    assert first.digest != second.digest
    assert len(first.digest) == 64


# -- J. portable fixtures ------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["wing_layout.json", "fuselage_layout.json", "control_surface_layout.json"],
)
def test_vs01_fixtures_generate_and_size(name: str) -> None:
    payload = _fixture(name)
    if name == "fuselage_layout.json":
        body = LoftedBody.from_spine(
            "fuselage",
            "fuselage",
            tuple(tuple(point) for point in payload["spine_mm"]),
            tuple(payload["widths_mm"]),
            tuple(payload["heights_mm"]),
            frame="body-local",
            exponent=payload["exponent"],
        )
        architecture = generate_body_architecture(
            body,
            material=_material(),
            frame_count=payload["frame_count"],
            stringer_count=payload["stringer_count"],
        )
    elif name == "control_surface_layout.json":
        parent = _surface(payload, surface_id="wing")
        control_data = payload["control"]
        control = ControlSurface(
            control_id=control_data["control_id"],
            parent_id="wing",
            kind=control_data["kind"],
            hinge_fraction=control_data["hinge_fraction"],
            span_fraction=tuple(control_data["span_fraction"]),
        )
        architecture = generate_control_surface_architecture(
            control, parent, material=_material(), rib_count=payload["rib_count"]
        )
    else:
        surface = _surface(payload)
        architecture = generate_wing_architecture(
            surface,
            material=_material(),
            kind=ArchitectureKind(payload["architecture_kind"]),
            spar_count=payload["spar_count"],
            rib_count=payload["rib_count"],
            stringer_count=payload["stringer_count"],
        )
    load_set = _load_set(
        payload, architecture.component_id, span_m=architecture.reference_span_m
    )
    sized = size_architecture(architecture, load_set)
    assert sized.total_mass_kg > 0.0
    assert sized.validity.passed is True
    assert len(sized.digest) == 64
