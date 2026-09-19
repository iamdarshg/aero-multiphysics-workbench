"""ADV-PHYS 04: generic durability, fatigue, creep, fracture, life-limited parts.

These tests drive the generic durability participants from typed, deterministic
fixtures. Every result must be unit-bearing, hashable, and carry
source/fidelity/provenance; declared life limits fail closed with provenance;
missing material-life data yields unavailable rather than invented life; and
the native structural/FEA seams fail closed when the engine is absent. No
result is ever relabelled analytical when native physics was requested.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_durability import (
    DURABILITY_PARTICIPANTS,
    MINER_LIMITATIONS,
    SI_UNITS,
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    CapabilityUnavailable,
    CompositeFatigueAllowables,
    CountingResult,
    CrackGrowthCurve,
    CrackType,
    CreepExposure,
    CreepRuptureCurve,
    DataUnavailable,
    DegradationMechanism,
    DegradationModifier,
    DurabilityError,
    DurabilityInputs,
    LifeLedger,
    LifeRequirement,
    LoadHistory,
    MeanStressCorrection,
    NortonParameters,
    SNCurve,
    StrainCycle,
    StrainLifeCurve,
    StressCycle,
    ThermalMechanicalCycle,
    UnitError,
    apply_modifiers,
    assess_life_requirement,
    creep_fatigue_interaction,
    creep_strain_rate_per_s,
    critical_crack_length_m,
    durability_change_sections,
    durability_invalidated_families,
    durability_invalidated_for,
    equivalent_amplitude,
    evaluate_composite_fatigue,
    evaluate_crack_criticality,
    evaluate_margin,
    evaluate_tmf,
    inspection_interval_cycles,
    miner_damage,
    native_capability,
    overspeed_burst_margin,
    paris_life,
    participant_ids,
    rainflow_count,
    require_native,
    require_unit,
    robinson_rupture_fraction,
    solve_native_durability,
    strain_life_damage,
    stress_intensity_factor_pa_m05,
    temperature_range_from_thermal,
    turning_points,
    ultimate_load_margin,
)
from aeroworkbench_materials import (
    LaminateRevision,
    MaterialDatabase,
    Ply,
    PlyMaterialError,
    laminate_digest,
)
from aeroworkbench_thermal import ThermalNetwork

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "durability"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _sn_curve() -> SNCurve:
    return SNCurve(**_fixture("sn_curve_steel.json"))


def _creep_curve() -> CreepRuptureCurve:
    payload = _fixture("creep_rupture_curve.json")
    payload["samples"] = tuple(tuple(pair) for pair in payload["samples"])
    return CreepRuptureCurve(**payload)


def _crack_curve() -> CrackGrowthCurve:
    return CrackGrowthCurve(**_fixture("crack_growth_curve.json"))


def _laminate() -> LaminateRevision:
    ply_material = MaterialDatabase.seeded().get_material("carbon-epoxy-ud-ply")
    ply = Ply(material=ply_material, angle_deg=0.0, thickness_m=1.25e-4)
    return LaminateRevision(laminate_id="panel-1", revision="r1", plies=(ply, ply, ply, ply))


# -- A. units and validation contracts ---------------------------------------


def test_advphys04_units_are_known_si_labels() -> None:
    for label in ("Pa", "Pa*m^0.5", "m", "K", "cycle", "1", "m/cycle", "h"):
        assert label in SI_UNITS
        assert require_unit(label) == label


def test_advphys04_unknown_unit_fails_closed() -> None:
    with pytest.raises(UnitError):
        require_unit("furlong")


# -- B. S-N curves -----------------------------------------------------------


def test_advphys04_sn_basquin_life_is_deterministic() -> None:
    curve = _sn_curve()
    assert curve.life_cycles(100.0e6, temperature_k=300.0) == pytest.approx(1.0e10)
    assert curve.life_cycles(200.0e6, temperature_k=300.0) == pytest.approx(9.765625e6)


def test_advphys04_sn_endurance_limit_gives_infinite_life() -> None:
    curve = _sn_curve()
    assert curve.life_cycles(40.0e6, temperature_k=300.0) == float("inf")


def test_advphys04_sn_temperature_validity_is_enforced() -> None:
    with pytest.raises(DataUnavailable):
        _sn_curve().life_cycles(100.0e6, temperature_k=1000.0)


def test_advphys04_curve_identity_and_provenance_source() -> None:
    curve = _sn_curve()
    assert curve.identity == "steel-sn@screening-r1"
    assert curve.source.startswith("generic handbook")


# -- C. cycle counting -------------------------------------------------------


def test_advphys04_rainflow_counts_constant_amplitude_block() -> None:
    payload = _fixture("load_history_block.json")
    history = LoadHistory(**payload)
    result = rainflow_count(history)
    assert isinstance(result, CountingResult)
    assert result.total_count() == pytest.approx(3.0)
    assert result.maximum_range() == pytest.approx(200.0e6)
    for cycle in result.all_cycles():
        assert cycle.mean_value == pytest.approx(100.0e6)
        assert cycle.amplitude == pytest.approx(100.0e6)


def test_advphys04_rainflow_is_provenance_backed() -> None:
    result = rainflow_count(LoadHistory(**_fixture("load_history_block.json")))
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert len(result.provenance.inputs_hash) == 64
    assert result.method == "three-point-rainflow"
    assert result.as_dict()["source"] == "analytical"


def test_advphys04_turning_points_ignore_monotonic_samples() -> None:
    assert turning_points((0.0, 5.0, 10.0, 5.0, 0.0)) == (0.0, 10.0, 0.0)


# -- D. mean-stress corrections ----------------------------------------------


@pytest.mark.parametrize(
    ("correction", "expected"),
    [
        (MeanStressCorrection.NONE, 50.0e6),
        (MeanStressCorrection.GOODMAN, 66.6666667e6),
        (MeanStressCorrection.GERBER, 53.3333333e6),
        (MeanStressCorrection.SODERBERG, 100.0e6),
        (MeanStressCorrection.MORROW, 55.5555556e6),
    ],
)
def test_advphys04_mean_stress_corrections(
    correction: MeanStressCorrection, expected: float
) -> None:
    value = equivalent_amplitude(
        50.0e6,
        100.0e6,
        correction,
        ultimate_pa=400.0e6,
        yield_pa=200.0e6,
        fatigue_strength_coefficient_pa=1000.0e6,
    )
    assert value == pytest.approx(expected, rel=1e-6)


def test_advphys04_missing_reference_strength_fails_closed() -> None:
    with pytest.raises(DataUnavailable):
        equivalent_amplitude(50.0e6, 100.0e6, MeanStressCorrection.GOODMAN)
    with pytest.raises(DataUnavailable):
        equivalent_amplitude(50.0e6, 100.0e6, MeanStressCorrection.MORROW)


# -- E. Miner damage ---------------------------------------------------------


def test_advphys04_miner_damage_and_limitations() -> None:
    result = miner_damage(
        _sn_curve(),
        (StressCycle(stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, count=1000.0),),
        temperature_k=300.0,
    )
    assert result.damage == pytest.approx(1.0e-7)
    assert result.life_cycles == pytest.approx(1.0e7)
    assert result.provenance.source is ResultSource.ANALYTICAL
    for limitation in MINER_LIMITATIONS:
        assert limitation in result.provenance.assumptions
    assert result.validity.passed is True


def test_advphys04_safety_factor_scales_damage() -> None:
    result = miner_damage(
        _sn_curve(),
        (StressCycle(stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, count=1000.0),),
        temperature_k=300.0,
        safety_factor=2.0,
    )
    assert result.damage == pytest.approx(2.0e-7)


def test_advphys04_miner_requires_cycles() -> None:
    with pytest.raises(DataUnavailable):
        miner_damage(_sn_curve(), (), temperature_k=300.0)


def test_advphys04_damage_uses_rainflow_cycles() -> None:
    counted = rainflow_count(LoadHistory(**_fixture("load_history_block.json")))
    cycles = tuple(
        StressCycle(
            stress_amplitude_pa=cycle.amplitude,
            stress_mean_pa=cycle.mean_value,
            count=cycle.count,
        )
        for cycle in counted.all_cycles()
    )
    result = miner_damage(_sn_curve(), cycles, temperature_k=300.0)
    assert result.damage == pytest.approx(3.0e-10)


# -- F. strain-life ----------------------------------------------------------


def _strain_curve() -> StrainLifeCurve:
    return StrainLifeCurve(
        curve_id="steel-strain",
        revision="r1",
        source="synthetic Coffin-Manson",
        fatigue_strength_coefficient_pa=1000.0e6,
        fatigue_strength_exponent=-0.1,
        fatigue_ductility_coefficient=0.5,
        fatigue_ductility_exponent=-0.6,
        youngs_modulus_pa=70.0e9,
        temperature_min_k=293.15,
        temperature_max_k=873.15,
    )


def test_advphys04_strain_life_round_trips() -> None:
    curve = _strain_curve()
    amplitude = curve.strain_amplitude(1.0e4)
    recovered = curve.cycles_to_failure(amplitude, temperature_k=300.0)
    assert recovered == pytest.approx(1.0e4, rel=1e-6)


def test_advphys04_morrow_mean_stress_shortens_life() -> None:
    curve = _strain_curve()
    amplitude = curve.strain_amplitude(1.0e4)
    without = curve.reversals_to_failure(amplitude, temperature_k=300.0)
    with_mean = curve.reversals_to_failure(
        amplitude, mean_stress_pa=400.0e6, temperature_k=300.0
    )
    assert with_mean < without


def test_advphys04_strain_life_damage_and_temperature_gate() -> None:
    curve = _strain_curve()
    cycle = StrainCycle(
        total_strain_amplitude=curve.strain_amplitude(1.0e4),
        stress_mean_pa=0.0,
        count=1.0e3,
    )
    result = strain_life_damage(curve, (cycle,), temperature_k=300.0)
    assert result.damage == pytest.approx(0.1, rel=1e-6)
    with pytest.raises(DataUnavailable):
        strain_life_damage(curve, (cycle,), temperature_k=1000.0)


# -- G. creep -----------------------------------------------------------------


def test_advphys04_larson_miller_rupture_time() -> None:
    curve = _creep_curve()
    assert curve.rupture_time_hours(100.0e6, temperature_k=1000.0) == pytest.approx(1.0e4)
    assert curve.rupture_time_hours(200.0e6, temperature_k=1000.0) == pytest.approx(1.0e3)
    assert curve.allowable_stress_pa(temperature_k=1000.0, time_hours=1.0e4) == pytest.approx(
        100.0e6
    )


def test_advphys04_robinson_rupture_fraction() -> None:
    result = robinson_rupture_fraction(
        _creep_curve(), (CreepExposure(stress_pa=100.0e6, temperature_k=1000.0, time_hours=5000.0),)
    )
    assert result.fraction == pytest.approx(0.5)
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_advphys04_creep_temperature_validity_is_enforced() -> None:
    with pytest.raises(DataUnavailable):
        _creep_curve().rupture_time_hours(100.0e6, temperature_k=400.0)


def test_advphys04_norton_strain_rate_is_physical() -> None:
    parameters = NortonParameters(
        coefficient=1.0e-20,
        stress_exponent=3.0,
        activation_energy_j_mol=200.0e3,
        source="synthetic Norton",
        revision="r1",
        temperature_min_k=800.0,
        temperature_max_k=1200.0,
    )
    hot = creep_strain_rate_per_s(parameters, 100.0e6, temperature_k=1100.0)
    cold = creep_strain_rate_per_s(parameters, 100.0e6, temperature_k=900.0)
    assert hot > cold > 0.0
    with pytest.raises(DataUnavailable):
        creep_strain_rate_per_s(parameters, 100.0e6, temperature_k=300.0)


def test_advphys04_creep_fatigue_interaction() -> None:
    fatigue = miner_damage(
        _sn_curve(),
        (StressCycle(stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, count=4.0e9),),
        temperature_k=300.0,
    )
    creep = robinson_rupture_fraction(
        _creep_curve(), (CreepExposure(stress_pa=100.0e6, temperature_k=1000.0, time_hours=5000.0),)
    )
    combined = creep_fatigue_interaction(fatigue, creep)
    assert combined.combined_damage == pytest.approx(0.9)
    assert combined.passed is True
    with pytest.raises(CapabilityUnavailable):
        creep_fatigue_interaction(fatigue, creep, model="ductility-exhaustion")


# -- H. fracture -------------------------------------------------------------


def test_advphys04_stress_intensity_and_critical_length() -> None:
    intensity = stress_intensity_factor_pa_m05(100.0e6, 1.0e-3)
    assert intensity == pytest.approx(100.0e6 * (3.141592653589793e-3) ** 0.5, rel=1e-9)
    critical = critical_crack_length_m(30.0e6, 100.0e6)
    assert critical == pytest.approx(0.09 / 3.141592653589793, rel=1e-9)


def test_advphys04_crack_criticality_check() -> None:
    result = evaluate_crack_criticality(
        _crack_curve(), stress_pa=100.0e6, crack_length_m=1.0e-3
    )
    assert result.passed is True
    assert result.reserve_factor() is not None and result.reserve_factor() > 1.0
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_advphys04_paris_growth_life() -> None:
    result = paris_life(_crack_curve(), initial_crack_m=1.0e-3, stress_range_pa=100.0e6)
    assert result.critical_crack_m == pytest.approx(0.09 / 3.141592653589793, rel=1e-6)
    assert result.cycles_to_critical > 0.0
    assert result.initial_growth_rate_m_per_cycle == pytest.approx(1.76e-9, rel=2e-2)
    assert result.allowable_cycles == pytest.approx(result.cycles_to_critical)


def test_advphys04_paris_below_threshold_fails_closed() -> None:
    with pytest.raises(DataUnavailable):
        _crack_curve().growth_rate_m_per_cycle(1.0e4)


def test_advphys04_fracture_without_toughness_fails_closed() -> None:
    payload = _fixture("crack_growth_curve.json")
    payload["fracture_toughness_pa_m05"] = None
    curve = CrackGrowthCurve(**payload)
    with pytest.raises(DataUnavailable):
        paris_life(curve, initial_crack_m=1.0e-3, stress_range_pa=100.0e6)


def test_advphys04_surface_crack_has_higher_geometry_factor() -> None:
    through = stress_intensity_factor_pa_m05(
        100.0e6, 1.0e-3, crack_type=CrackType.THROUGH
    )
    surface = stress_intensity_factor_pa_m05(
        100.0e6, 1.0e-3, crack_type=CrackType.SURFACE
    )
    assert surface == pytest.approx(1.12 * through)


# -- I. environmental degradation --------------------------------------------


def test_advphys04_modifier_chain_reduces_allowable() -> None:
    oxidation = DegradationModifier(
        **_fixture("oxidation_modifier.json"),
        mechanism=DegradationMechanism.OXIDATION,
    )
    erosion = DegradationModifier(
        modifier_id="erosion-r1",
        mechanism=DegradationMechanism.EROSION,
        factor=0.95,
        source="synthetic erosion factor",
        revision="r1",
        temperature_min_k=300.0,
        temperature_max_k=900.0,
    )
    modified = apply_modifiers("fatigue_limit", 400.0e6, (oxidation, erosion), temperature_k=700.0)
    assert modified.modified == pytest.approx(400.0e6 * 0.9 * 0.95)
    assert modified.provenance.source is ResultSource.ANALYTICAL
    assert len(modified.factors) == 2


def test_advphys04_modifier_out_of_validity_fails_closed() -> None:
    oxidation = DegradationModifier(
        **_fixture("oxidation_modifier.json"),
        mechanism=DegradationMechanism.OXIDATION,
    )
    with pytest.raises(DataUnavailable):
        apply_modifiers("fatigue_limit", 400.0e6, (oxidation,), temperature_k=500.0)


# -- J. composite fatigue seam -----------------------------------------------


def test_advphys04_composite_requires_laminate_specific_allowables() -> None:
    laminate = _laminate()
    cycles = (StressCycle(stress_amplitude_pa=300.0e6, stress_mean_pa=0.0, count=1.0e5),)
    with pytest.raises(CapabilityUnavailable):
        evaluate_composite_fatigue(laminate, cycles, temperature_k=300.0)


def test_advphys04_composite_fatigue_with_allowables() -> None:
    laminate = _laminate()
    payload = _fixture("laminate_allowables.json")
    allowables = CompositeFatigueAllowables(
        laminate_digest=laminate_digest(laminate), **payload
    )
    cycles = (StressCycle(stress_amplitude_pa=300.0e6, stress_mean_pa=0.0, count=1.0e5),)
    result = evaluate_composite_fatigue(
        laminate, cycles, allowables=allowables, temperature_k=300.0
    )
    assert result.damage == pytest.approx(0.1)
    assert result.provenance.source is ResultSource.ANALYTICAL


def test_advphys04_composite_digest_mismatch_fails_closed() -> None:
    laminate = _laminate()
    payload = _fixture("laminate_allowables.json")
    allowables = CompositeFatigueAllowables(laminate_digest="0" * 64, **payload)
    cycles = (StressCycle(stress_amplitude_pa=300.0e6, stress_mean_pa=0.0, count=1.0e5),)
    with pytest.raises(DataUnavailable):
        evaluate_composite_fatigue(laminate, cycles, allowables=allowables, temperature_k=300.0)


def test_advphys04_isotropic_ply_material_is_rejected() -> None:
    aluminium = MaterialDatabase.seeded().get_material("aluminium-6061-t6")
    with pytest.raises(PlyMaterialError):
        Ply(material=aluminium, angle_deg=0.0, thickness_m=1.0e-3)


# -- K. thermo-mechanical fatigue -------------------------------------------


def _tmf_curves() -> tuple[SNCurve, SNCurve]:
    low = SNCurve(
        curve_id="sn-low",
        revision="r1",
        source="synthetic low-temperature curve",
        fatigue_strength_coefficient_pa=1.0e9,
        fatigue_strength_exponent=-0.1,
        temperature_min_k=293.15,
        temperature_max_k=573.15,
    )
    high = SNCurve(
        curve_id="sn-high",
        revision="r1",
        source="synthetic high-temperature curve",
        fatigue_strength_coefficient_pa=1.0e9,
        fatigue_strength_exponent=-0.1,
        temperature_min_k=573.15,
        temperature_max_k=873.15,
    )
    return low, high


def test_advphys04_tmf_from_coupled_thermal_result() -> None:
    network = ThermalNetwork()
    network.connect("node", "ambient", 1.0)
    network.add_load("node", 10.0)
    thermal = network.solve()
    minimum, maximum = temperature_range_from_thermal(thermal)
    assert minimum == pytest.approx(298.15, abs=1e-6)
    assert maximum == pytest.approx(308.15, abs=1e-6)


def test_advphys04_tmf_accumulates_damage() -> None:
    cycles = (
        ThermalMechanicalCycle(
            stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, temperature_k=400.0, count=1.0e6
        ),
        ThermalMechanicalCycle(
            stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, temperature_k=700.0, count=1.0e6
        ),
    )
    result = evaluate_tmf(cycles, _tmf_curves())
    assert result.damage == pytest.approx(2.0e-4)


def test_advphys04_tmf_without_valid_curve_fails_closed() -> None:
    cycles = (
        ThermalMechanicalCycle(
            stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, temperature_k=1000.0, count=1.0
        ),
    )
    with pytest.raises(CapabilityUnavailable):
        evaluate_tmf(cycles, _tmf_curves())


# -- L. life-limited parts and margins ---------------------------------------


def test_advphys04_life_requirement_assessment() -> None:
    requirement = LifeRequirement(
        part_id="disk-1", required_cycles=4.0e6, safety_factor=2.0
    )
    result = assess_life_requirement(
        requirement, damage_per_cycle=1.0e-7, consumed_cycles=1.0e6
    )
    assert result.allowable_cycles == pytest.approx(5.0e6)
    assert result.utilization == pytest.approx(0.2)
    assert result.remaining_cycles == pytest.approx(4.0e6)
    assert result.inspection_interval_cycles == pytest.approx(1.0e6)
    assert result.passed is True


def test_advphys04_static_strength_cannot_satisfy_life_requirement() -> None:
    requirement = LifeRequirement(part_id="disk-1", required_cycles=4.0e6)
    with pytest.raises(DataUnavailable):
        assess_life_requirement(requirement, damage_per_cycle=None)


def test_advphys04_life_requirement_can_fail() -> None:
    requirement = LifeRequirement(part_id="disk-2", required_cycles=2.0e7, safety_factor=2.0)
    result = assess_life_requirement(requirement, damage_per_cycle=1.0e-7)
    assert result.passed is False


def test_advphys04_hours_requirement_needs_cycles_per_hour() -> None:
    requirement = LifeRequirement(part_id="disk-3", required_hours=1000.0)
    with pytest.raises(DataUnavailable):
        assess_life_requirement(requirement, damage_per_cycle=1.0e-7)
    result = assess_life_requirement(
        requirement, damage_per_cycle=1.0e-7, cycles_per_hour=1000.0
    )
    assert result.allowable_hours == pytest.approx(10000.0)
    assert result.passed is True


def test_advphys04_inspection_interval() -> None:
    assert inspection_interval_cycles(1.0e-6) == pytest.approx(1.0e5)
    assert inspection_interval_cycles(1.0e-6, detectable_damage=0.2) == pytest.approx(2.0e5)


def test_advphys04_strength_margins() -> None:
    margin = evaluate_margin("hoop", 500.0e6, 200.0e6, safety_factor=1.5)
    assert margin.reserve_factor == pytest.approx(500.0e6 / 300.0e6)
    assert margin.passed is True
    burst = overspeed_burst_margin(600.0e6, 200.0e6, overspeed_factor=1.2)
    assert burst.applied_pa == pytest.approx(240.0e6)
    ultimate = ultimate_load_margin(600.0e6, 250.0e6, ultimate_factor=1.5)
    assert ultimate.reserve_factor == pytest.approx(600.0e6 / 375.0e6)


def test_advphys04_life_ledger_bookkeeping() -> None:
    ledger = LifeLedger()
    ledger = ledger.record(
        "disk-1", consumed_cycles=1.0e6, consumed_hours=1000.0, allowable_cycles=5.0e6
    )
    ledger = ledger.record(
        "disk-2", consumed_cycles=4.0e6, consumed_hours=4000.0, allowable_cycles=4.0e6
    )
    assert ledger.utilization("disk-1") == pytest.approx(0.2)
    assert ledger.exhausted() == ("disk-2",)
    assert len(ledger.digest()) == 64
    assert ledger.as_dict()["digest"] == ledger.digest()


# -- M. participants and native capability gating ----------------------------


def test_advphys04_participant_registry_covers_capabilities() -> None:
    ids = participant_ids()
    assert {"high-cycle-fatigue", "creep-rupture", "crack-growth", "composite-fatigue"} <= set(ids)
    assert len(DURABILITY_PARTICIPANTS) == len(ids)


def test_advphys04_participant_ports_route_to_closures() -> None:
    crack = next(p for p in DURABILITY_PARTICIPANTS if p.participant_id == "crack-growth")
    targets = {port.target for port in crack.outputs}
    assert {"fracture", "life"} <= targets
    assert "cycles_to_critical" in crack.port_names()


def test_advphys04_native_capability_is_gated() -> None:
    state = native_capability("fatigue-fea")
    assert state.state == "unavailable"
    with pytest.raises(CapabilityUnavailable):
        require_native("fatigue-fea")
    with pytest.raises(CapabilityUnavailable):
        solve_native_durability("crack-growth-fea", solver_name="absent-fea")


# -- N. provenance, units, and design-space invalidation ---------------------


def test_advphys04_results_carry_source_hash_and_si_units() -> None:
    result = miner_damage(
        _sn_curve(),
        (StressCycle(stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, count=1000.0),),
        temperature_k=300.0,
    )
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert result.provenance.fidelity.value == "analytical"
    assert len(result.provenance.inputs_hash) == 64
    for unit in result.units().values():
        require_unit(unit)
    counted = rainflow_count(LoadHistory(**_fixture("load_history_block.json")))
    for unit in counted.units().values():
        require_unit(unit)
    assert SOFTWARE_IDENTITY == "aeroworkbench-durability"
    assert SOFTWARE_VERSION == "1.0.0"


def test_advphys04_provenance_hash_is_deterministic() -> None:
    cycle = StressCycle(stress_amplitude_pa=100.0e6, stress_mean_pa=0.0, count=1000.0)
    first = miner_damage(_sn_curve(), (cycle,), temperature_k=300.0)
    second = miner_damage(_sn_curve(), (cycle,), temperature_k=300.0)
    assert first.provenance.inputs_hash == second.provenance.inputs_hash


def test_advphys04_design_space_invalidation_reuses_shared_table() -> None:
    before = DurabilityInputs(
        part_id="disk-1",
        material_digest="a" * 64,
        load_spectrum_digest="b" * 64,
        temperature_k=900.0,
    )
    after = DurabilityInputs(
        part_id="disk-1",
        material_digest="c" * 64,
        load_spectrum_digest="b" * 64,
        temperature_k=900.0,
    )
    assert durability_change_sections(before, after) == ("materials",)
    families = durability_invalidated_for(before, after)
    assert "structural" in families
    assert "thermal" in families
    assert durability_invalidated_families(("not-a-section",)) == ("all",)


def test_advphys04_part_or_temperature_change_invalidates_operating_points() -> None:
    before = DurabilityInputs(
        part_id="disk-1",
        material_digest="a" * 64,
        load_spectrum_digest="b" * 64,
        temperature_k=900.0,
    )
    after = DurabilityInputs(
        part_id="disk-1",
        material_digest="a" * 64,
        load_spectrum_digest="d" * 64,
        temperature_k=950.0,
    )
    assert durability_change_sections(before, after) == ("operatingPoints",)


def test_advphys04_result_contract_is_typed() -> None:
    with pytest.raises(DurabilityError):
        LifeRequirement(part_id="")
    with pytest.raises(DataUnavailable):
        SNCurve(
            curve_id="bad",
            revision="r1",
            source="synthetic",
            fatigue_strength_coefficient_pa=1.0e9,
            fatigue_strength_exponent=0.1,
            temperature_min_k=293.15,
            temperature_max_k=873.15,
        )
