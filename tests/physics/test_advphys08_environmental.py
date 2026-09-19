"""ADV-PHYS 08: generic environmental degradation, icing, contamination, erosion, FOD.

This module proves one authoritative environmental contract: declared exposure
state; explicit geometry/property degradation; a staged icing fidelity seam;
contamination, erosion, and foreign-object-damage contracts; coupling into
existing design revision + invalidation; and robust-design hooks. Every result
carries source/fidelity/units/validity/input-hash/software-identity/provenance.
Native paths are capability-gated and fail closed; nothing is fabricated.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.design import PhysicalDesignState
from aeroworkbench_core.types import Quantity as DesignQuantity
from aeroworkbench_core.types import ResultSource
from aeroworkbench_coupling.dag import CHANGE_IMPACT
from aeroworkbench_environmental import (
    DEFAULT_ENVELOPE_MODEL,
    ENVIRONMENTAL_PARTICIPANTS,
    SI_UNITS,
    CapabilityUnavailable,
    ConstraintDirection,
    DegradationKind,
    EnvelopeModel,
    EnvironmentalError,
    EnvironmentalFidelity,
    EnvironmentState,
    ExposureKind,
    ExposureSpec,
    ImpactEvent,
    Quantity,
    RobustConstraint,
    UnitError,
    ValidityError,
    apply_degradation,
    degradation_change_sections,
    degrade_material_revision,
    degraded_invalidated_families,
    environmental_participants,
    evaluate_contamination,
    evaluate_degradation,
    evaluate_erosion,
    evaluate_ice_accretion_envelope,
    evaluate_impact,
    evaluate_robust_constraint,
    ice_geometry_change,
    native_environmental_capability,
    native_icing_capability,
    participant_ids,
    require_native_environmental,
    require_residual_strength,
    require_unit,
    robust_conditions_for,
    solve_native_icing,
)
from aeroworkbench_materials.properties import constant
from aeroworkbench_materials.revision import MaterialRevision, material_digest

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "environmental"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _model() -> EnvelopeModel:
    return EnvelopeModel(**_fixture("envelope_model.json"))


def _exposure(payload: dict[str, Any]) -> ExposureSpec:
    drivers = tuple(
        (name, Quantity(value=spec["value"], unit=spec["unit"]))
        for name, spec in payload["drivers"].items()
    )
    return ExposureSpec(kind=ExposureKind(payload["kind"]), drivers=drivers)


def _icing_request(payload: dict[str, Any] | None = None) -> Any:
    from aeroworkbench_environmental import IceAccretionRequest

    return IceAccretionRequest(
        request_id="ice-req-1",
        exposure=_exposure(payload or _fixture("icing_exposure.json")),
        geometry_hash="a" * 64,
    )


# -- A. units -----------------------------------------------------------------


def test_advphys08_si_units_are_known() -> None:
    assert {"m", "kg/m3", "kg/m2", "kg/(m2*s)", "m/s", "K", "J", "kg*m/s"} <= SI_UNITS
    for label in ("m", "kg/m3", "kg/m2", "J"):
        assert require_unit(label) == label


def test_advphys08_unknown_unit_fails_closed() -> None:
    with pytest.raises(UnitError):
        require_unit("furlong")


def test_advphys08_quantity_dimension_mismatch_fails_closed() -> None:
    from aeroworkbench_environmental.units import require_dimension

    with pytest.raises(UnitError):
        require_dimension(Quantity(1.0, "N"), "length", "value")


# -- B. exposure state --------------------------------------------------------


def test_advphys08_exposure_fixture_constructs() -> None:
    exposure = _exposure(_fixture("icing_exposure.json"))
    assert exposure.kind is ExposureKind.ICING
    assert exposure.si("water_content") == pytest.approx(0.0005)
    assert exposure.si("ambient_temperature") == pytest.approx(263.15)


def test_advphys08_exposure_missing_driver_fails_closed() -> None:
    with pytest.raises(EnvironmentalError):
        ExposureSpec(
            kind=ExposureKind.ICING,
            drivers=(("water_content", Quantity(1.0, "kg/m3")),),
        )


def test_advphys08_exposure_unknown_and_wrong_dimension_fail_closed() -> None:
    with pytest.raises(EnvironmentalError):
        ExposureSpec(
            kind=ExposureKind.SAND_DUST,
            drivers=(
                ("particle_concentration", Quantity(1.0, "kg/m3")),
                ("particle_diameter", Quantity(1.0, "m")),
                ("impact_speed", Quantity(1.0, "m/s")),
                ("duration", Quantity(1.0, "s")),
                ("mystery", Quantity(1.0, "m")),
            ),
        )
    with pytest.raises(UnitError):
        ExposureSpec(
            kind=ExposureKind.SAND_DUST,
            drivers=(
                ("particle_concentration", Quantity(1.0, "m")),
                ("particle_diameter", Quantity(1.0, "m")),
                ("impact_speed", Quantity(1.0, "m/s")),
                ("duration", Quantity(1.0, "s")),
            ),
        )


def test_advphys08_negative_duration_fails_closed() -> None:
    with pytest.raises(EnvironmentalError):
        ExposureSpec(
            kind=ExposureKind.PARTICULATE_FOULING,
            drivers=(
                ("deposit_rate", Quantity(1.0, "kg/(m2*s)")),
                ("duration", Quantity(-1.0, "s")),
            ),
        )


def test_advphys08_environment_revisioning_replaces_exposure() -> None:
    exposure = _exposure(_fixture("icing_exposure.json"))
    environment = EnvironmentState(
        environment_id="env-1",
        revision=1,
        atmosphere_model="isa",
        exposures=(exposure,),
    )
    assert environment.exposure(ExposureKind.ICING) is exposure
    revised = environment.with_exposure(exposure, revision=2)
    assert revised.revision == 2
    assert len(revised.exposures) == 1


def test_advphys08_environment_duplicate_exposure_kind_fails_closed() -> None:
    exposure = _exposure(_fixture("icing_exposure.json"))
    with pytest.raises(EnvironmentalError):
        EnvironmentState(
            environment_id="env-1",
            revision=1,
            atmosphere_model="isa",
            exposures=(exposure, exposure),
        )


# -- C. degradation -----------------------------------------------------------


def test_advphys08_icing_degradation_is_explicit_and_provenanced() -> None:
    environment = EnvironmentState(
        environment_id="env-ice",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("icing_exposure.json")),),
    )
    state = evaluate_degradation(environment, model=_model())
    kinds = {modifier.kind for modifier in state.modifiers}
    assert DegradationKind.LEADING_EDGE_ROUGHNESS in kinds
    assert DegradationKind.SURFACE_ROUGHNESS in kinds
    assert state.fidelity is EnvironmentalFidelity.ENVELOPE
    assert state.geometry_changed is True
    assert state.provenance.source is ResultSource.ANALYTICAL
    assert len(state.digest) == 64
    assert state.validity.passed is True
    for modifier in state.modifiers:
        assert modifier.sections
        assert modifier.delta.value_si == modifier.delta.value_si


def test_advphys08_degradation_is_deterministic() -> None:
    environment = EnvironmentState(
        environment_id="env-ice",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("icing_exposure.json")),),
    )
    first = evaluate_degradation(environment, model=_model())
    second = evaluate_degradation(environment, model=_model())
    assert first.digest == second.digest
    assert first.canonical_payload() == second.canonical_payload()


def test_advphys08_salt_corrosion_produces_strength_and_stiffness_loss() -> None:
    environment = EnvironmentState(
        environment_id="env-salt",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("salt_corrosive.json")),),
    )
    state = evaluate_degradation(environment, model=_model())
    deltas = {modifier.quantity_name: modifier.delta.value_si for modifier in state.modifiers}
    expect = _fixture("salt_corrosive.json")["expect"]
    assert deltas["material_loss_depth"] == pytest.approx(expect["materialLossDepthM"])
    assert deltas["strength_fraction_reduction"] == pytest.approx(
        expect["strengthFractionReduction"]
    )
    assert deltas["stiffness_fraction_reduction"] == pytest.approx(
        expect["stiffnessFractionReduction"]
    )
    assert state.material_changed is True


def test_advphys08_thermal_cycling_clearance_and_fatigue() -> None:
    environment = EnvironmentState(
        environment_id="env-thermal",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("thermal_cycling.json")),),
    )
    state = evaluate_degradation(environment, model=_model())
    deltas = {modifier.quantity_name: modifier.delta.value_si for modifier in state.modifiers}
    expect = _fixture("thermal_cycling.json")["expect"]
    assert deltas["clearance_change"] == pytest.approx(expect["clearanceChangeM"])
    assert deltas["strength_fraction_reduction"] == pytest.approx(
        expect["strengthFractionReduction"]
    )
    assert state.geometry_changed and state.material_changed


def test_advphys08_corrosion_changes_heat_transfer_and_emissivity() -> None:
    environment = EnvironmentState(
        environment_id="env-salt",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("salt_corrosive.json")),),
    )
    state = evaluate_degradation(environment, model=_model())
    kinds = {modifier.kind for modifier in state.modifiers}
    assert DegradationKind.HEAT_TRANSFER_CHANGE in kinds
    assert DegradationKind.EMISSIVITY_CHANGE in kinds
    assert "heat_transfer_fraction_change" in state.units()
    assert "emissivity_change" in state.units()


def test_advphys08_all_exposure_kinds_produce_modifiers() -> None:
    names = (
        "icing_exposure.json",
        "sand_dust_erosion.json",
        "particulate_fouling.json",
        "salt_corrosive.json",
        "thermal_cycling.json",
    )
    impact = _fixture("impact_event.json")
    exposures = (
        *(_exposure(_fixture(name)) for name in names),
        _exposure(
            {
                "kind": "foreign_object_impact",
                "drivers": {
                    "impactor_mass": impact["impactorMass"],
                    "impact_speed": impact["impactSpeed"],
                    "impactor_diameter": impact["impactorDiameter"],
                },
            }
        ),
    )
    environment = EnvironmentState(
        environment_id="mixed",
        revision=1,
        atmosphere_model="isa",
        exposures=exposures,
    )
    state = evaluate_degradation(environment, model=_model())
    assert "geometry" in state.changed_sections
    assert "materials" in state.changed_sections
    assert "parameters" in state.changed_sections
    assert len(state.modifiers) >= 8


# -- D. icing staged fidelity seam -------------------------------------------


def test_advphys08_icing_envelope_is_labeled_screening() -> None:
    request = _icing_request()
    result = evaluate_ice_accretion_envelope(request, model=_model())
    expect = _fixture("icing_exposure.json")["expect"]
    assert result.fidelity is EnvironmentalFidelity.ENVELOPE
    assert result.fidelity is not EnvironmentalFidelity.NATIVE
    assert result.accreted_areal_mass.value_si == pytest.approx(
        expect["accretedArealMassKgM2"]
    )
    assert result.ice_thickness.value_si == pytest.approx(expect["iceThicknessM"])
    assert any("EMPIRICAL" in warning for warning in result.warnings)
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert len(str(result.provenance.inputs_hash)) == 64
    assert result.software.name == "aeroworkbench-environmental"


def test_advphys08_icing_geometry_change_advances_revision() -> None:
    result = evaluate_ice_accretion_envelope(_icing_request(), model=_model())
    change = ice_geometry_change(result, previous_hash="a" * 64, revision=2)
    assert change.fidelity is EnvironmentalFidelity.GEOMETRY
    assert change.geometry_hash != change.previous_hash
    assert len(change.geometry_hash) == 64
    assert change.changed_sections == ("geometry",)
    assert change.validity.passed is True


def test_advphys08_icing_native_fails_closed_without_backend() -> None:
    with pytest.raises(CapabilityUnavailable):
        solve_native_icing(_icing_request(), model=_model())
    assert native_icing_capability().state == "unavailable"


class _FakeIcingBackend:
    solver_name = "fake-ice"
    solver_version = "2.0"

    def accrete(self, request: Any, model: EnvelopeModel) -> dict[str, float]:
        return {
            "accreted_areal_mass_kg_m2": 30.0,
            "ice_thickness_m": 0.03,
            "roughness_increment_m": 0.004,
        }


def test_advphys08_icing_native_backend_carries_native_identity() -> None:
    result = solve_native_icing(
        _icing_request(), backend=_FakeIcingBackend(), run_id="ice-run-1"
    )
    assert result.fidelity is EnvironmentalFidelity.NATIVE
    assert result.provenance.source is ResultSource.NATIVE_SOLVER
    assert result.provenance.solver_name == "fake-ice"
    assert result.provenance.run_id == "ice-run-1"
    assert result.ice_thickness.value_si == pytest.approx(0.03)


def test_advphys08_icing_geometry_change_rejects_native_result() -> None:
    native = solve_native_icing(_icing_request(), backend=_FakeIcingBackend())
    with pytest.raises(EnvironmentalError):
        ice_geometry_change(native, previous_hash="a" * 64, revision=1)


# -- E. contamination and erosion --------------------------------------------


def test_advphys08_contamination_matches_fixture() -> None:
    exposure = _exposure(_fixture("particulate_fouling.json"))
    assessment = evaluate_contamination(exposure, model=_model())
    expect = _fixture("particulate_fouling.json")["expect"]
    assert assessment.fidelity is EnvironmentalFidelity.ENVELOPE
    assert assessment.deposit_areal_mass.value_si == pytest.approx(
        expect["depositArealMassKgM2"]
    )
    assert assessment.deposit_thickness.value_si == pytest.approx(
        expect["depositThicknessM"]
    )
    assert assessment.blocked_area_fraction.value_si == pytest.approx(
        expect["blockedAreaFraction"]
    )
    assert assessment.units()["deposit_areal_mass"] == "kg/m2"


def test_advphys08_contamination_rejects_wrong_exposure() -> None:
    with pytest.raises(EnvironmentalError):
        evaluate_contamination(_exposure(_fixture("icing_exposure.json")), model=_model())


def test_advphys08_erosion_matches_fixture() -> None:
    assessment = evaluate_erosion(_exposure(_fixture("sand_dust_erosion.json")), model=_model())
    expect = _fixture("sand_dust_erosion.json")["expect"]
    assert assessment.material_loss_depth.value_si == pytest.approx(
        expect["materialLossDepthM"]
    )
    assert assessment.areal_mass_impacted.value_si == pytest.approx(
        expect["arealMassImpactedKgM2"]
    )
    assert assessment.erosion_rate.value_si == pytest.approx(expect["erosionRateMS"])
    assert assessment.provenance.source is ResultSource.ANALYTICAL


def test_advphys08_erosion_rejects_wrong_exposure() -> None:
    with pytest.raises(EnvironmentalError):
        evaluate_erosion(_exposure(_fixture("thermal_cycling.json")), model=_model())


# -- F. foreign-object damage -------------------------------------------------


def _impact() -> ImpactEvent:
    fixture = _fixture("impact_event.json")
    return ImpactEvent(
        event_id=fixture["eventId"],
        impactor_mass=Quantity(fixture["impactorMass"]["value"], fixture["impactorMass"]["unit"]),
        impact_speed=Quantity(fixture["impactSpeed"]["value"], fixture["impactSpeed"]["unit"]),
        impactor_diameter=Quantity(
            fixture["impactorDiameter"]["value"], fixture["impactorDiameter"]["unit"]
        ),
        location=fixture["location"],
        incidence_angle_deg=fixture["incidenceAngleDeg"],
    )


def test_advphys08_impact_kinematics_match_fixture() -> None:
    report = evaluate_impact(_impact())
    expect = _fixture("impact_event.json")["expect"]
    assert report.kinetic_energy.value_si == pytest.approx(expect["kineticEnergyJ"])
    assert report.momentum.value_si == pytest.approx(expect["momentumKgMS"])
    assert report.footprint_area.value_si == pytest.approx(expect["footprintAreaM2"])
    assert report.residual_strength_provided is False
    assert report.structural_analysis_required is True


def test_advphys08_residual_strength_requires_native_and_fails_closed() -> None:
    with pytest.raises(CapabilityUnavailable):
        require_residual_strength()
    report = evaluate_impact(_impact())
    feed = report.structural_damage_feed()
    assert feed.residual_strength_provided is False
    assert feed.kinetic_energy.value_si == pytest.approx(5625.0)
    assert feed.location == "leading-edge"


def test_advphys08_impact_event_from_exposure() -> None:
    fixture = _fixture("impact_event.json")
    exposure = _exposure(
        {
            "kind": "foreign_object_impact",
            "drivers": {
                "impactor_mass": fixture["impactorMass"],
                "impact_speed": fixture["impactSpeed"],
                "impactor_diameter": fixture["impactorDiameter"],
            },
        }
    )
    event = ImpactEvent.from_exposure(exposure, event_id="fod-2", location="nose")
    assert event.kinetic_energy_j == pytest.approx(fixture["expect"]["kineticEnergyJ"])


# -- G. coupling into existing design + invalidation --------------------------


def _clean_design() -> PhysicalDesignState:
    return PhysicalDesignState(
        design_id="env08",
        variant_id="clean",
        parameters={
            "material_loss_depth": DesignQuantity(value=0.0, unit="m"),
            "surface_roughness_increment": DesignQuantity(value=1.0e-6, unit="m"),
        },
        geometry_hash="a" * 64,
        material_hash="b" * 64,
        scalar_results={"thrust": DesignQuantity(value=1000.0, unit="N")},
    )


def test_advphys08_degradation_couples_into_design_and_invalidates() -> None:
    environment = EnvironmentState(
        environment_id="env-erode",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("sand_dust_erosion.json")),),
    )
    degradation = evaluate_degradation(environment, model=_model())
    degraded = apply_degradation(
        _clean_design(),
        degradation,
        variant_id="degraded",
        author="advphys08",
        reason="sand erosion",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert degraded.geometry_revision_changed is True
    assert degraded.material_revision_changed is True
    assert degraded.design.geometry_hash != "a" * 64
    assert degraded.design.material_hash != "b" * 64
    assert degraded.design.scalar_results == {}
    assert degraded.design.parent_variant_id == "clean"
    assert set(degraded.parameter_changes) == {
        "material_loss_depth",
        "surface_roughness_increment",
    }
    assert degraded.design.parameters["material_loss_depth"].si_value > 0.0
    assert {"mesh", "analysis", "structural", "thermal", "electromagnetic"} <= set(
        degraded.invalidated_families
    )
    assert degraded.validity.passed is True


def test_advphys08_degradation_sections_use_existing_vocabulary() -> None:
    environment = EnvironmentState(
        environment_id="env-salt",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("salt_corrosive.json")),),
    )
    degradation = evaluate_degradation(environment, model=_model())
    sections = degradation_change_sections(degradation)
    for section in sections:
        assert section in CHANGE_IMPACT
    assert degraded_invalidated_families(degradation) == tuple(
        sorted(degraded_invalidated_families(degradation))
    )


def test_advphys08_no_exposure_yields_no_geometry_change() -> None:
    environment = EnvironmentState(
        environment_id="env-clean", revision=1, atmosphere_model="isa"
    )
    degradation = evaluate_degradation(environment, model=_model())
    assert degradation.modifiers == ()
    assert degradation.geometry_changed is False
    degraded = apply_degradation(
        _clean_design(),
        degradation,
        variant_id="clean-v2",
        author="advphys08",
        reason="no exposure",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert degraded.design.geometry_hash == "a" * 64
    assert degraded.design.material_hash == "b" * 64


# -- H. material property degradation ----------------------------------------


def test_advphys08_material_revision_degradation() -> None:
    material = MaterialRevision(
        material_id="alu-1",
        revision="1",
        symmetry="isotropic",
        properties={
            "density": constant(2700.0, "kg/m^3", "fixture"),
            "youngs_modulus": constant(70.0e9, "Pa", "fixture"),
            "yield_strength": constant(300.0e6, "Pa", "fixture"),
        },
    )
    environment = EnvironmentState(
        environment_id="env-salt",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("salt_corrosive.json")),),
    )
    degradation = evaluate_degradation(environment, model=_model())
    degraded = degrade_material_revision(material, degradation, revision="2")
    assert degraded.previous_digest == material_digest(material)
    assert degraded.digest != degraded.previous_digest
    assert set(degraded.changed_properties) == {"youngs_modulus", "yield_strength"}
    assert degraded.material.properties["youngs_modulus"].constant == pytest.approx(
        70.0e9 * (1.0 - 3.6e-5)
    )
    assert degraded.material.properties["yield_strength"].constant == pytest.approx(
        300.0e6 * (1.0 - 7.2e-5)
    )
    assert degraded.validity.passed is True
    assert degraded.material.revision == "2"


def test_advphys08_material_degradation_requires_degradable_property() -> None:
    material = MaterialRevision(
        material_id="alu-2",
        revision="1",
        symmetry="isotropic",
        properties={"density": constant(2700.0, "kg/m^3", "fixture")},
    )
    environment = EnvironmentState(
        environment_id="env-salt",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("salt_corrosive.json")),),
    )
    degradation = evaluate_degradation(environment, model=_model())
    with pytest.raises(EnvironmentalError):
        degrade_material_revision(material, degradation, revision="2")


def test_advphys08_material_thermal_property_degradation() -> None:
    material = MaterialRevision(
        material_id="alu-3",
        revision="1",
        symmetry="isotropic",
        properties={
            "density": constant(2700.0, "kg/m^3", "fixture"),
            "conductivity": constant(200.0, "W/(m K)", "fixture"),
            "emissivity": constant(0.1, "dimensionless", "fixture"),
        },
    )
    environment = EnvironmentState(
        environment_id="env-salt",
        revision=1,
        atmosphere_model="isa",
        exposures=(_exposure(_fixture("salt_corrosive.json")),),
    )
    degradation = evaluate_degradation(environment, model=_model())
    degraded = degrade_material_revision(material, degradation, revision="2")
    assert set(degraded.changed_properties) == {"conductivity", "emissivity"}
    assert degraded.material.properties["conductivity"].constant == pytest.approx(
        200.0 * (1.0 + 7.2e-5)
    )
    assert degraded.material.properties["emissivity"].constant == pytest.approx(
        0.1 * (1.0 + 7.2e-5)
    )
    assert degraded.validity.passed is True


# -- I. robust design ---------------------------------------------------------


def test_advphys08_robust_worst_case_maximum() -> None:
    constraint = RobustConstraint(
        name="roughness-limit",
        quantity_name="surface_roughness_increment",
        limit=Quantity(100.0, "um"),
    )
    verdict = evaluate_robust_constraint(
        constraint, Quantity(40.0, "um"), Quantity(80.0, "um")
    )
    assert verdict.worst_value.value_si == pytest.approx(80.0e-6)
    assert verdict.margin.value_si == pytest.approx(20.0e-6)
    assert verdict.passed is True
    assert verdict.governing_condition == "degraded"
    assert verdict.validity.passed is True


def test_advphys08_robust_constraint_fails_closed_when_exceeded() -> None:
    constraint = RobustConstraint(
        name="roughness-limit",
        quantity_name="surface_roughness_increment",
        limit=Quantity(100.0, "um"),
        margin_fraction=0.25,
    )
    verdict = evaluate_robust_constraint(
        constraint, Quantity(40.0, "um"), Quantity(90.0, "um")
    )
    assert verdict.passed is False
    assert verdict.validity.passed is False


def test_advphys08_robust_minimum_direction_and_dimension_check() -> None:
    constraint = RobustConstraint(
        name="thickness-floor",
        quantity_name="material_loss_depth",
        limit=Quantity(1.0, "mm"),
        direction=ConstraintDirection.MINIMUM,
    )
    verdict = evaluate_robust_constraint(
        constraint, Quantity(2.0, "mm"), Quantity(0.5, "mm")
    )
    assert verdict.worst_value.value_si == pytest.approx(0.5e-3)
    assert verdict.passed is False
    with pytest.raises(UnitError):
        evaluate_robust_constraint(constraint, Quantity(1.0, "N"), Quantity(0.5, "mm"))


def test_advphys08_robust_conditions_pairs_clean_with_each_exposure() -> None:
    environment = EnvironmentState(
        environment_id="env-mixed",
        revision=1,
        atmosphere_model="isa",
        exposures=(
            _exposure(_fixture("icing_exposure.json")),
            _exposure(_fixture("sand_dust_erosion.json")),
        ),
    )
    conditions = robust_conditions_for(environment)
    assert conditions[0].name == "clean"
    assert {condition.name for condition in conditions} == {
        "clean",
        "degraded:icing",
        "degraded:sand_dust",
    }


# -- J. participants and capability gating ------------------------------------


def test_advphys08_participant_registry_covers_environmental_effects() -> None:
    ids = participant_ids()
    assert {
        "ice-accretion",
        "surface-contamination",
        "surface-erosion",
        "foreign-object-impact",
        "corrosive-exposure",
    } <= set(ids)
    assert len(environmental_participants()) == len(ENVIRONMENTAL_PARTICIPANTS)


def test_advphys08_participant_ports_route_to_closures() -> None:
    ice = next(p for p in ENVIRONMENTAL_PARTICIPANTS if p.participant_id == "ice-accretion")
    targets = {port.target for port in ice.outputs}
    assert {"geometry", "performance", "structural"} <= targets
    assert "ice_thickness_m" in ice.port_names()


def test_advphys08_native_capabilities_fail_closed() -> None:
    for requirement in (
        "ice-accretion-cfd",
        "impact-structural-fea",
        "corrosion-life-model",
        "particle-erosion-cfd",
    ):
        state = native_environmental_capability(requirement)
        assert state.state == "unavailable"
        with pytest.raises(CapabilityUnavailable):
            require_native_environmental(requirement)
    assert native_environmental_capability("ice-accretion-cfd", present=True).available


# -- K. portability: same framework for airframes and propulsion hardware -----


def test_advphys08_same_framework_for_external_and_internal_hardware() -> None:
    external = EnvironmentState(
        environment_id="external-surface",
        revision=1,
        atmosphere_model="isa",
        exposures=(
            _exposure(_fixture("icing_exposure.json")),
            _exposure(_fixture("sand_dust_erosion.json")),
        ),
    )
    internal = EnvironmentState(
        environment_id="internal-flowpath",
        revision=1,
        atmosphere_model="isa",
        exposures=(
            _exposure(_fixture("particulate_fouling.json")),
            _exposure(_fixture("salt_corrosive.json")),
        ),
    )
    for environment in (external, internal):
        state = evaluate_degradation(environment, model=_model())
        assert state.modifiers
        assert state.changed_sections
        assert state.validity.passed is True
        for modifier in state.modifiers:
            assert modifier.canonical_payload()["quantity"] == modifier.quantity_name


def test_advphys08_default_envelope_model_is_declared_screening() -> None:
    assert "screening" in DEFAULT_ENVELOPE_MODEL.model_id
    assert DEFAULT_ENVELOPE_MODEL.source
    state = evaluate_degradation(
        EnvironmentState(
            environment_id="env-ice",
            revision=0,
            atmosphere_model="declared",
            exposures=(_exposure(_fixture("icing_exposure.json")),),
        )
    )
    assert any(
        "screening" in assumption for assumption in state.provenance.assumptions
    )


def test_advphys08_validity_error_is_environmental_error() -> None:
    assert issubclass(ValidityError, EnvironmentalError)
