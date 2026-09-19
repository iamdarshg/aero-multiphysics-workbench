"""ADV-PHYS 13: generic composite, laminate and anisotropic structural design.

Deterministic fixtures drive the generic composite participants: ply
architecture with temperature/moisture modifiers, canonical laminate
definitions, classical-laminate-theory A/B/D and ply stresses, selectable
failure criteria, manufacturing constraints enforced before analysis, and
capability-gated native structural mapping. Every result is unit-bearing,
hashable, and carries source/fidelity/provenance; missing data and absent
native capabilities fail closed. The same code path serves fixed and rotating
structures.
"""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_composites import (
    COMPOSITES_PARTICIPANTS,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    CapabilityUnavailable,
    CompositeInputs,
    CompositesError,
    DataUnavailable,
    FailureCriterion,
    LaminateDefinition,
    LaminateLoad,
    LocalFrame,
    ManufacturingViolation,
    MoistureModifier,
    NativeStructuralRequest,
    PlyArchitecture,
    PlyDiscardPolicy,
    PlyProcessLimits,
    PlyStrainLimits,
    PlyStrength,
    PlyStress,
    PrestressState,
    StrengthLibrary,
    UnitError,
    analyze_laminate,
    apply_environment,
    cantilever_bending_frequency_hz,
    centrifugal_membrane_load,
    composite_change_sections,
    composite_fatigue_damage,
    composite_invalidated_families,
    composite_invalidated_for,
    composites_participant_ids,
    evaluate_composite_design,
    evaluate_interlaminar,
    evaluate_manufacturability,
    evaluate_ply_failure,
    first_ply_failure,
    is_balanced,
    is_symmetric,
    laminate_definition_digest,
    manufacturing_envelope,
    manufacturing_limits,
    map_laminate_to_structural,
    native_structural_capability,
    ply_constants,
    ply_stresses,
    pressure_hoop_load,
    progressive_failure,
    reject_isotropic_reduction,
    require_manufacturable,
    require_native_structural,
    require_unit,
    screen_with_turbo05,
    solve_native_structural,
    to_aeroelastic_inputs,
)
from aeroworkbench_core.types import ResultSource
from aeroworkbench_durability.composites import CompositeFatigueAllowables
from aeroworkbench_durability.environment import DegradationMechanism, DegradationModifier
from aeroworkbench_durability.fatigue import StressCycle
from aeroworkbench_materials import (
    LaminateRevision,
    MaterialDatabase,
    MaterialRevision,
    Ply,
    PlyMaterialError,
    constant,
    effective_orthotropic,
    laminate_digest,
    material_digest,
    temperature_table,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "composites"
_CARBON = "carbon-epoxy-ud-ply"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _carbon() -> MaterialRevision:
    return MaterialDatabase.seeded().get_material(_CARBON)


def _laminate(
    angles: tuple[float, ...],
    *,
    thickness: float = 1.25e-4,
    laminate_id: str = "panel-1",
) -> LaminateRevision:
    material = _carbon()
    plies = tuple(
        Ply(material=material, angle_deg=angle, thickness_m=thickness) for angle in angles
    )
    return LaminateRevision(laminate_id=laminate_id, revision="r1", plies=plies)


def _symmetric_panel() -> LaminateRevision:
    return _laminate((0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0))


def _strength() -> PlyStrength:
    return PlyStrength(material_digest=material_digest(_carbon()), **_fixture("ply_strengths.json"))


def _library() -> StrengthLibrary:
    return StrengthLibrary((_strength(),))


def _process() -> PlyProcessLimits:
    return PlyProcessLimits(**_fixture("process_limits.json"))


def _criteria_strength(**overrides: float) -> PlyStrength:
    payload: dict[str, Any] = {
        "material_digest": material_digest(_carbon()),
        "source": "synthetic criteria allowables",
        "revision": "r1",
        "x_tension_pa": 1000.0e6,
        "x_compression_pa": 800.0e6,
        "y_tension_pa": 50.0e6,
        "y_compression_pa": 200.0e6,
        "shear_pa": 70.0e6,
        "temperature_min_k": 200.0,
        "temperature_max_k": 400.0,
    }
    payload.update(overrides)
    return PlyStrength(**payload)


def _static_stress() -> PlyStress:
    return PlyStress(sigma_1_pa=500.0e6, sigma_2_pa=10.0e6, tau_12_pa=20.0e6)


def _frame(frame_id: str = "blade-root") -> LocalFrame:
    return LocalFrame(frame_id=frame_id, x_axis=(1.0, 0.0, 0.0), z_axis=(0.0, 0.0, 1.0))


def _temperature_modifier() -> DegradationModifier:
    payload = _fixture("temperature_modifier.json")
    mechanism = DegradationMechanism(payload.pop("mechanism"))
    return DegradationModifier(mechanism=mechanism, **payload)


# -- A. material architecture -------------------------------------------------


def test_advphys13_ply_architecture_binds_strength_digest() -> None:
    material = _carbon()
    architecture = PlyArchitecture(
        fiber="carbon", matrix="epoxy", material=material, strength=_strength()
    )
    layer = architecture.layer(angle_deg=0.0, thickness_m=1.25e-4)
    assert layer.material is material
    wrong = _fixture("ply_strengths.json")
    wrong["material_digest"] = "0" * 64
    with pytest.raises(DataUnavailable):
        PlyArchitecture(
            fiber="carbon", matrix="epoxy", material=material, strength=PlyStrength(**wrong)
        )


def test_advphys13_isotropic_material_cannot_be_a_ply() -> None:
    aluminium = MaterialDatabase.seeded().get_material("aluminium-6061-t6")
    with pytest.raises(PlyMaterialError):
        Ply(material=aluminium, angle_deg=0.0, thickness_m=1.0e-3)


def test_advphys13_temperature_dependent_ply_and_fail_closed() -> None:
    payload = _fixture("temperature_dependent_ply.json")
    samples = tuple(tuple(pair) for pair in payload["youngs_modulus_samples"])
    material = MaterialRevision(
        material_id=payload["material_id"],
        revision=payload["revision"],
        symmetry="orthotropic",
        properties={
            "density": constant(payload["density_kg_m3"], "kg/m^3", "synthetic"),
            "youngs_modulus": temperature_table(samples, "Pa", "synthetic"),
            "youngs_modulus_transverse": constant(
                payload["youngs_modulus_transverse_pa"], "Pa", "synthetic"
            ),
            "poisson_ratio": constant(payload["poisson_ratio"], "1", "synthetic"),
            "shear_modulus": constant(payload["shear_modulus_pa"], "Pa", "synthetic"),
        },
    )
    ply = Ply(material=material, angle_deg=0.0, thickness_m=1.0e-4)
    cold = ply_constants(ply, temperature_k=293.15)
    hot = ply_constants(ply, temperature_k=393.15)
    assert cold.e1_pa == pytest.approx(135.0e9)
    assert hot.e1_pa == pytest.approx(128.0e9)
    assert hot.e1_pa < cold.e1_pa
    with pytest.raises(DataUnavailable):
        ply_constants(ply, temperature_k=500.0)


def test_advphys13_environmental_modifiers_reduce_allowables() -> None:
    strength = _strength()
    moisture = MoistureModifier(**_fixture("moisture_modifier.json"))
    assessment = apply_environment(
        strength,
        temperature_k=350.0,
        moisture_fraction=0.5,
        temperature_modifiers=(_temperature_modifier(),),
        moisture_modifiers=(moisture,),
    )
    assert assessment.strength.x_tension_pa == pytest.approx(
        strength.x_tension_pa * 0.9 * 0.85
    )
    assert assessment.provenance.source is ResultSource.ANALYTICAL
    with pytest.raises(DataUnavailable):
        apply_environment(strength, temperature_k=1000.0)
    with pytest.raises(DataUnavailable):
        apply_environment(
            strength,
            temperature_k=350.0,
            moisture_fraction=2.0,
            moisture_modifiers=(moisture,),
        )


# -- B. laminate definition ---------------------------------------------------


def test_advphys13_laminate_digest_distinguishes_order_and_orientation() -> None:
    base = _symmetric_panel()
    reordered = _laminate((45.0, 0.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0))
    reoriented = _laminate((0.0, -45.0, 45.0, 90.0, 90.0, -45.0, 45.0, 0.0))
    assert laminate_digest(base) != laminate_digest(reordered)
    assert laminate_digest(base) != laminate_digest(reoriented)


def test_advphys13_symmetry_and_balance_detection() -> None:
    symmetric = _symmetric_panel()
    assert is_symmetric(symmetric)
    assert is_balanced(symmetric)
    asymmetric = _laminate((0.0, 45.0, -45.0, 90.0, 0.0, -45.0, 45.0, 90.0))
    assert not is_symmetric(asymmetric)
    unbalanced = _laminate((0.0, 45.0, 45.0, 0.0, 0.0, 45.0, 45.0, 0.0))
    assert not is_balanced(unbalanced)
    with pytest.raises(DataUnavailable):
        LaminateDefinition(laminate=asymmetric, symmetric=True, balanced=True)


def test_advphys13_definition_digest_is_frame_sensitive() -> None:
    laminate = _symmetric_panel()
    skin = LaminateDefinition(laminate=laminate, symmetric=True, balanced=True, region="skin")
    skin_again = LaminateDefinition(
        laminate=laminate, symmetric=True, balanced=True, region="skin"
    )
    spar = LaminateDefinition(laminate=laminate, symmetric=True, balanced=True, region="spar")
    assert laminate_definition_digest(skin) == laminate_definition_digest(skin_again)
    assert laminate_definition_digest(skin) != laminate_definition_digest(spar)


# -- C. CLT / reduced laminate analysis ---------------------------------------


def test_advphys13_clt_abd_and_materials_agreement() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    a_scale = max(abs(value) for row in analysis.a for value in row)
    assert max(abs(value) for row in analysis.b for value in row) < 1e-6 * a_scale
    homogenized = effective_orthotropic(_symmetric_panel())
    assert analysis.membrane.ex_pa == pytest.approx(
        homogenized.evaluate("youngs_modulus"), rel=1e-9
    )
    assert analysis.membrane.ey_pa == pytest.approx(
        homogenized.evaluate("youngs_modulus_transverse"), rel=1e-9
    )
    assert analysis.membrane.gxy_pa == pytest.approx(
        homogenized.evaluate("shear_modulus"), rel=1e-9
    )
    assert analysis.membrane.nuxy == pytest.approx(
        homogenized.evaluate("poisson_ratio"), rel=1e-9
    )
    assert analysis.d[0][0] > 0.0


def _no_thermal_laminate() -> LaminateRevision:
    material = MaterialRevision(
        material_id="synthetic-no-cte",
        revision="r1",
        symmetry="orthotropic",
        properties={
            "density": constant(1600.0, "kg/m^3", "synthetic"),
            "youngs_modulus": constant(135.0e9, "Pa", "synthetic"),
            "youngs_modulus_transverse": constant(10.0e9, "Pa", "synthetic"),
            "poisson_ratio": constant(0.3, "1", "synthetic"),
            "shear_modulus": constant(5.0e9, "Pa", "synthetic"),
        },
    )
    ply = Ply(material=material, angle_deg=0.0, thickness_m=1.25e-4)
    return LaminateRevision(laminate_id="no-cte", revision="r1", plies=(ply, ply, ply, ply))


def test_advphys13_thermal_resultants_and_fail_closed() -> None:
    laminate = _symmetric_panel()
    hot = analyze_laminate(laminate, delta_temperature_k=50.0)
    cold = analyze_laminate(laminate, delta_temperature_k=0.0)
    assert hot.thermal.n_x_n_m != 0.0
    assert cold.thermal.n_x_n_m == 0.0
    with pytest.raises(DataUnavailable):
        analyze_laminate(_no_thermal_laminate(), delta_temperature_k=10.0)


def test_advphys13_ply_stresses_follow_orientation() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    responses = ply_stresses(analysis, LaminateLoad(n_x_n_m=1.0e5))
    by_angle = {response.angle_deg: response for response in responses}
    assert by_angle[0.0].sigma_1_pa > by_angle[90.0].sigma_1_pa
    assert by_angle[0.0].eps_1 > 0.0
    for unit in responses[0].units().values():
        require_unit(unit)


def test_advphys13_unsymmetric_rejected_for_reduced_analysis() -> None:
    asymmetric = _laminate((0.0, 45.0, -45.0, 90.0, 0.0, -45.0, 45.0, 90.0))
    with pytest.raises(DataUnavailable):
        analyze_laminate(asymmetric, require_symmetric=True)
    analysis = analyze_laminate(asymmetric)
    assert analysis.validity.checks["extension_bending_coupling_present"] is True


# -- D. native structural mapping ---------------------------------------------


def test_advphys13_structural_mapping_preserves_anisotropy() -> None:
    laminate = _symmetric_panel()
    mapping = map_laminate_to_structural(
        laminate,
        frame=_frame(),
        element_kind="shell",
        prestress=PrestressState(rotational_speed_rad_s=300.0, reference_radius_m=0.6),
    )
    assert mapping.reduction is None
    assert len(mapping.plies) == len(laminate.plies)
    assert mapping.plies[0].offset_m == pytest.approx(-laminate.total_thickness_m / 2.0)
    assert mapping.as_dict()["elementKind"] == "shell"


def test_advphys13_structural_mapping_carries_prestress_and_pressure() -> None:
    from aeroworkbench_composites import SurfaceLoad as CompositeSurfaceLoad

    laminate = _symmetric_panel()
    mapping = map_laminate_to_structural(
        laminate,
        frame=_frame(),
        prestress=PrestressState(rotational_speed_rad_s=300.0, reference_radius_m=0.6),
        pressure_loads=(
            CompositeSurfaceLoad(name="aero", pressure_pa=1.0e4, frame_id="blade-root"),
        ),
    )
    payload = mapping.as_dict()
    assert payload["prestress"]["rotationalSpeedRadS"] == 300.0
    assert payload["pressureLoads"][0]["pressurePa"] == 1.0e4


def test_advphys13_native_capability_fails_closed() -> None:
    assert native_structural_capability("code-aster-shell-composite").state == "unavailable"
    with pytest.raises(CapabilityUnavailable):
        require_native_structural("code-aster-shell-composite")
    mapping = map_laminate_to_structural(_symmetric_panel(), frame=_frame())
    request = NativeStructuralRequest(
        requirement="code-aster-shell-composite",
        solver_name="code_aster",
        analysis="static",
        mapping=mapping,
        provenance=mapping.provenance,
    )
    with pytest.raises(CapabilityUnavailable):
        solve_native_structural(request)
    with pytest.raises(CompositesError):
        reject_isotropic_reduction("homogenize-to-isotropic")


# -- E. failure criteria ------------------------------------------------------


def test_advphys13_max_stress_index_and_reserve() -> None:
    result = evaluate_ply_failure(
        _static_stress(), _criteria_strength(), FailureCriterion.MAX_STRESS
    )
    assert result.index == pytest.approx(0.5)
    assert result.reserve_factor == pytest.approx(2.0)
    assert result.failed is False
    assert result.mode == "fibre-1"


def test_advphys13_max_strain_requires_limits() -> None:
    limits = PlyStrainLimits(
        material_digest=material_digest(_carbon()),
        **_fixture("ply_strain_limits.json"),
    )
    stress = PlyStress(
        sigma_1_pa=1.0,
        sigma_2_pa=1.0,
        tau_12_pa=1.0,
        eps_1=0.005,
        eps_2=0.001,
        gamma_12=0.007,
    )
    result = evaluate_ply_failure(
        stress, _criteria_strength(), FailureCriterion.MAX_STRAIN, strain_limits=limits
    )
    assert result.index == pytest.approx(max(0.005 / 0.0111, 0.001 / 0.005, 0.007 / 0.014))
    with pytest.raises(DataUnavailable):
        evaluate_ply_failure(stress, _criteria_strength(), FailureCriterion.MAX_STRAIN)


def test_advphys13_tsai_hill_matches_closed_form() -> None:
    result = evaluate_ply_failure(
        _static_stress(), _criteria_strength(), FailureCriterion.TSAI_HILL
    )
    expected = (
        0.5**2
        - (500.0e6 * 10.0e6 / (1000.0e6**2))
        + (10.0e6 / 50.0e6) ** 2
        + (20.0e6 / 70.0e6) ** 2
    )
    assert result.index == pytest.approx(expected)
    assert result.mode == "tsai-hill-interaction"


def test_advphys13_tsai_wu_matches_closed_form() -> None:
    result = evaluate_ply_failure(
        _static_stress(), _criteria_strength(), FailureCriterion.TSAI_WU
    )
    x_t, x_c, y_t, y_c, shear = 1000.0e6, 800.0e6, 50.0e6, 200.0e6, 70.0e6
    f1 = 1.0 / x_t - 1.0 / x_c
    f2 = 1.0 / y_t - 1.0 / y_c
    f11 = 1.0 / (x_t * x_c)
    f22 = 1.0 / (y_t * y_c)
    f66 = 1.0 / (shear * shear)
    f12 = -0.5 * sqrt(f11 * f22)
    expected = (
        f1 * 500.0e6
        + f2 * 10.0e6
        + f11 * (500.0e6) ** 2
        + f22 * (10.0e6) ** 2
        + f66 * (20.0e6) ** 2
        + 2.0 * f12 * 500.0e6 * 10.0e6
    )
    assert result.index == pytest.approx(expected)
    with pytest.raises(DataUnavailable):
        evaluate_ply_failure(
            _static_stress(),
            _criteria_strength(),
            FailureCriterion.TSAI_WU,
            tsai_wu_f12_star=2.0,
        )


def test_advphys13_hashin_selects_fibre_and_matrix_modes() -> None:
    tension = evaluate_ply_failure(
        _static_stress(), _criteria_strength(), FailureCriterion.HASHIN
    )
    expected = max(0.5**2 + (20.0e6 / 70.0e6) ** 2, (10.0e6 / 50.0e6) ** 2 + (20.0e6 / 70.0e6) ** 2)
    assert tension.index == pytest.approx(expected)
    assert tension.mode == "fibre-tension"
    compression = evaluate_ply_failure(
        PlyStress(sigma_1_pa=-500.0e6, sigma_2_pa=-10.0e6, tau_12_pa=20.0e6),
        _criteria_strength(),
        FailureCriterion.HASHIN,
    )
    assert compression.mode == "fibre-compression"
    assert compression.index == pytest.approx((500.0e6 / 800.0e6) ** 2)


def test_advphys13_interlaminar_seam_fails_closed_without_data() -> None:
    through = PlyStress(
        sigma_1_pa=0.0,
        sigma_2_pa=0.0,
        tau_12_pa=0.0,
        sigma_3_pa=5.0e6,
        tau_13_pa=10.0e6,
        tau_23_pa=0.0,
    )
    with pytest.raises(DataUnavailable):
        evaluate_interlaminar(through, _criteria_strength())
    full = _criteria_strength(
        z_tension_pa=40.0e6, z_compression_pa=150.0e6, interlaminar_shear_pa=60.0e6
    )
    result = evaluate_interlaminar(
        PlyStress(
            sigma_1_pa=0.0,
            sigma_2_pa=0.0,
            tau_12_pa=0.0,
            sigma_3_pa=20.0e6,
            tau_13_pa=30.0e6,
            tau_23_pa=0.0,
        ),
        full,
    )
    assert result.index == pytest.approx((20.0e6 / 40.0e6) ** 2 + (30.0e6 / 60.0e6) ** 2)
    assert result.mode == "interlaminar"


def test_advphys13_first_ply_failure_critical_ply() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    result = first_ply_failure(
        analysis,
        LaminateLoad(n_x_n_m=5.0e4),
        _library(),
        criterion=FailureCriterion.MAX_STRESS,
    )
    assert result.critical_ply_index in (3, 4)
    assert result.mode == "transverse-2"
    assert len(result.ply_indices) == len(analysis.plies)
    assert result.failed is True


def test_advphys13_first_ply_criterion_requires_laminate() -> None:
    with pytest.raises(CompositesError):
        evaluate_ply_failure(_static_stress(), _criteria_strength(), FailureCriterion.FIRST_PLY)


def test_advphys13_progressive_failure_discards_plies() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    result = progressive_failure(
        analysis,
        LaminateLoad(n_x_n_m=5.0e4),
        _library(),
        criterion=FailureCriterion.MAX_STRESS,
        discard_policy=PlyDiscardPolicy(mode="immediate", max_iterations=20),
    )
    assert result.first_failed_ply in (3, 4)
    assert len(result.failed_plies) >= 1
    assert result.iterations >= 1


# -- F. manufacturing constraints ---------------------------------------------


def test_advphys13_manufacturability_pass_and_fail() -> None:
    laminate = _symmetric_panel()
    limits = _process()
    report = evaluate_manufacturability(
        laminate, limits, region_radius_m=0.5, drape_angle_deg=2.0
    )
    assert report.passed
    assert not report.findings
    thick = _laminate((0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0), thickness=5.0e-4)
    failed = evaluate_manufacturability(thick, limits, region_radius_m=0.5, drape_angle_deg=2.0)
    assert not failed.passed
    assert "PLY_THICKNESS_ABOVE_MAXIMUM" in failed.violations


def test_advphys13_orientation_and_count_rules() -> None:
    limits = _process()
    disallowed = _laminate((0.0, 30.0, -30.0, 90.0, 90.0, -30.0, 30.0, 0.0))
    report = evaluate_manufacturability(
        disallowed, limits, region_radius_m=0.5, drape_angle_deg=2.0
    )
    assert "ORIENTATION_NOT_ALLOWED" in report.violations
    short = _laminate((0.0, 0.0))
    report_short = evaluate_manufacturability(
        short, limits, region_radius_m=0.5, drape_angle_deg=2.0
    )
    assert "PLY_COUNT_BELOW_MINIMUM" in report_short.violations


def test_advphys13_radius_drape_and_ply_drop_fail_closed() -> None:
    limits = _process()
    laminate = _symmetric_panel()
    missing_radius = evaluate_manufacturability(laminate, limits, drape_angle_deg=2.0)
    assert "REGION_RADIUS_UNAVAILABLE" in missing_radius.violations
    tight = evaluate_manufacturability(
        laminate, limits, region_radius_m=0.01, drape_angle_deg=2.0
    )
    assert "REGION_RADIUS_BELOW_MINIMUM" in tight.violations
    too_much_drape = evaluate_manufacturability(
        laminate, limits, region_radius_m=0.5, drape_angle_deg=30.0
    )
    assert "DRAPE_ANGLE_EXCEEDED" in too_much_drape.violations
    varying = _laminate_varying()
    drop = evaluate_manufacturability(
        varying, limits, region_radius_m=0.5, drape_angle_deg=2.0
    )
    assert "PLY_DROP_RATIO_EXCEEDED" in drop.violations


def _laminate_varying() -> LaminateRevision:
    material = _carbon()
    thicknesses = (1.0e-4, 2.0e-4, 1.0e-4, 2.0e-4, 2.0e-4, 1.0e-4, 2.0e-4, 1.0e-4)
    angles = (0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0)
    plies = tuple(
        Ply(material=material, angle_deg=angle, thickness_m=thickness)
        for angle, thickness in zip(angles, thicknesses, strict=True)
    )
    return LaminateRevision(laminate_id="varying", revision="r1", plies=plies)


def test_advphys13_require_manufacturable_rejects_before_analysis() -> None:
    thick = _laminate((0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0), thickness=5.0e-4)
    with pytest.raises(ManufacturingViolation) as excinfo:
        require_manufacturable(thick, _process(), region_radius_m=0.5, drape_angle_deg=2.0)
    assert "PLY_THICKNESS_ABOVE_MAXIMUM" in excinfo.value.violations
    assert len(excinfo.value.provenance.inputs_hash) == 64


def test_advphys13_turbo05_gate_integration() -> None:
    limits = _process()
    accepted = screen_with_turbo05(limits, _symmetric_panel(), region_radius_m=0.5)
    assert accepted.status == "accepted"
    thick = _laminate((0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0), thickness=5.0e-4)
    rejected = screen_with_turbo05(limits, thick, region_radius_m=0.5)
    assert rejected.status == "rejected"
    assert not rejected.permits("pre-solver-physics")
    assert manufacturing_envelope(limits).content_hash == manufacturing_envelope(
        limits
    ).content_hash
    names = {limit.value_name for limit in manufacturing_limits(limits)}
    assert {"ply_count", "minimum_ply_thickness", "maximum_ply_thickness"} <= names


# -- G. dynamic / durability coupling -----------------------------------------


def test_advphys13_cantilever_frequency_is_deterministic() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    first = cantilever_bending_frequency_hz(analysis, length_m=0.5)
    second = cantilever_bending_frequency_hz(analysis, length_m=0.5)
    assert first.frequency_hz == second.frequency_hz > 0.0
    assert first.areal_mass_kg_m2 == pytest.approx(
        1600.0 * _symmetric_panel().total_thickness_m
    )
    assert first.provenance.source is ResultSource.ANALYTICAL
    with pytest.raises(ValueError):
        cantilever_bending_frequency_hz(analysis, length_m=0.0)


def test_advphys13_centrifugal_and_pressure_loads() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    rotating = centrifugal_membrane_load(analysis, tip_radius_m=0.6, omega_rad_s=300.0)
    assert rotating.n_x_n_m == pytest.approx(0.5 * 1.6 * 300.0**2 * 0.6**2)
    assert rotating.units()["n_x_n_m"] == "N/m"
    hoop = pressure_hoop_load(50_000.0, radius_m=0.15)
    assert hoop.n_y_n_m == pytest.approx(7500.0)


def test_advphys13_operating_point_feeds_aeroelastic_participant() -> None:
    estimate = cantilever_bending_frequency_hz(analyze_laminate(_symmetric_panel()), length_m=0.5)
    inputs = to_aeroelastic_inputs(estimate)
    assert set(inputs) == {
        "frequency_hz",
        "areal_mass_kg_m2",
        "bending_stiffness_d11_n_m",
    }
    assert all(value > 0.0 for value in inputs.values())


def test_advphys13_composite_fatigue_reuses_durability_seam() -> None:
    laminate = _symmetric_panel()
    cycles = (StressCycle(stress_amplitude_pa=300.0e6, stress_mean_pa=0.0, count=1.0e5),)
    with pytest.raises(CapabilityUnavailable):
        composite_fatigue_damage(laminate, cycles, allowables=None, temperature_k=300.0)
    allowables = CompositeFatigueAllowables(
        laminate_digest=laminate_digest(laminate), **_fixture("laminate_fatigue_allowables.json")
    )
    result = composite_fatigue_damage(
        laminate, cycles, allowables=allowables, temperature_k=300.0
    )
    assert result.damage == pytest.approx(0.1)
    assert result.provenance.source is ResultSource.ANALYTICAL
    mismatch = CompositeFatigueAllowables(
        laminate_digest="0" * 64, **_fixture("laminate_fatigue_allowables.json")
    )
    with pytest.raises(DataUnavailable):
        composite_fatigue_damage(
            laminate, cycles, allowables=mismatch, temperature_k=300.0
        )


# -- H. portable fixtures -----------------------------------------------------


def _fixture_laminate(payload: dict[str, Any]) -> LaminateRevision:
    return _laminate(
        tuple(payload["angles_deg"]),
        thickness=payload["ply_thickness_m"],
        laminate_id=payload["fixture_id"],
    )


@pytest.mark.parametrize(
    "name",
    ["cantilever_plate.json", "wing_spar_shell.json", "rotating_blade.json"],
)
def test_advphys13_portable_fixtures_run_the_same_contracts(name: str) -> None:
    payload = _fixture(name)
    laminate = _fixture_laminate(payload)
    limits = _process()
    assert require_manufacturable(
        laminate,
        limits,
        region_radius_m=payload["region_radius_m"],
        drape_angle_deg=2.0,
    ).passed
    design = evaluate_composite_design(
        laminate,
        process_limits=limits,
        strengths=_library(),
        load=LaminateLoad(n_x_n_m=payload["n_x_n_m"]),
        modal_length_m=payload["length_m"],
        region_radius_m=payload["region_radius_m"],
        drape_angle_deg=2.0,
        temperature_k=payload["temperature_k"],
        delta_temperature_k=payload["delta_temperature_k"],
    )
    assert design.laminate_digest == laminate_digest(laminate)
    assert len(design.digest) == 64
    prestress = None
    if payload.get("omega_rad_s"):
        prestress = PrestressState(
            rotational_speed_rad_s=payload["omega_rad_s"],
            reference_radius_m=payload.get("tip_radius_m", payload["length_m"]),
        )
    mapping = map_laminate_to_structural(
        laminate, frame=_frame(payload["fixture_id"]), prestress=prestress
    )
    assert mapping.reduction is None
    assert len(mapping.plies) == len(laminate.plies)


def test_advphys13_same_code_handles_fixed_and_rotating() -> None:
    for name in ("cantilever_plate.json", "rotating_blade.json"):
        payload = _fixture(name)
        laminate = _fixture_laminate(payload)
        analysis = analyze_laminate(laminate)
        if payload.get("omega_rad_s"):
            load = centrifugal_membrane_load(
                analysis,
                tip_radius_m=payload["tip_radius_m"],
                omega_rad_s=payload["omega_rad_s"],
            )
            assert load.n_x_n_m > 0.0
        outcome = evaluate_composite_design(
            laminate, strengths=_library(), load=LaminateLoad(n_x_n_m=payload["n_x_n_m"])
        )
        assert outcome.analysis.laminate_digest == laminate_digest(laminate)


# -- provenance, units, determinism, invalidation -----------------------------


def test_advphys13_results_carry_provenance_units_and_identity() -> None:
    analysis = analyze_laminate(_symmetric_panel())
    assert analysis.provenance.source is ResultSource.ANALYTICAL
    assert analysis.provenance.fidelity.value == "analytical"
    assert len(analysis.provenance.inputs_hash) == 64
    for unit in analysis.units().values():
        require_unit(unit)
    assert SOFTWARE_IDENTITY == "aeroworkbench-composites"
    assert SOFTWARE_VERSION == "1.0.0"
    design = evaluate_composite_design(
        _symmetric_panel(), strengths=_library(), load=LaminateLoad(n_x_n_m=5.0e4)
    )
    for unit in design.units().values():
        require_unit(unit)
    assert len(design.digest) == 64


def test_advphys13_unknown_unit_fails_closed() -> None:
    with pytest.raises(UnitError):
        require_unit("furlong")


def test_advphys13_analysis_and_design_are_deterministic() -> None:
    laminate = _symmetric_panel()
    first = analyze_laminate(laminate, delta_temperature_k=20.0)
    second = analyze_laminate(laminate, delta_temperature_k=20.0)
    assert first.provenance.inputs_hash == second.provenance.inputs_hash
    assert first.as_dict() == second.as_dict()
    result_a = evaluate_composite_design(laminate, strengths=_library(), delta_temperature_k=20.0)
    result_b = evaluate_composite_design(laminate, strengths=_library(), delta_temperature_k=20.0)
    assert result_a.digest == result_b.digest


def test_advphys13_design_invalidation_reuses_shared_dag() -> None:
    laminate_digest_value = laminate_digest(_symmetric_panel())
    before = CompositeInputs(
        part_id="panel",
        laminate_digest=laminate_digest_value,
        material_digest=material_digest(_carbon()),
        temperature_k=300.0,
    )
    after = CompositeInputs(
        part_id="panel",
        laminate_digest=laminate_digest_value,
        material_digest="a" * 64,
        temperature_k=320.0,
    )
    assert composite_change_sections(before, after) == ("materials", "operatingPoints")
    families = composite_invalidated_for(before, after)
    assert "structural" in families
    assert "thermal" in families
    assert composite_invalidated_families(("not-a-section",)) == ("all",)


def test_advphys13_participant_registry_covers_capabilities() -> None:
    ids = composites_participant_ids()
    assert {"laminate-clt", "ply-failure", "composite-structural-fea"} <= set(ids)
    assert len(COMPOSITES_PARTICIPANTS) == len(ids)
