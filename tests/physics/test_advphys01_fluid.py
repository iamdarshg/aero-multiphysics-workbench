"""ADV-PHYS 01: canonical working-fluid, atmosphere, and real-gas properties.

This module proves one authoritative property API: revisioned fluid identity,
layered standard atmosphere, ideal-gas and ideal-mixture evaluation, frozen and
equilibrium combustion products, humid air, and capability-gated real-gas
backends. Every result carries source/fidelity/units/validity/input-hash/
software-identity/provenance. Out-of-validity requests and absent native
capabilities fail closed; nothing is fabricated.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import aeroworkbench_fluid_properties as fp
import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_fluid_properties import (
    Composition,
    FluidCapabilityUnavailableError,
    FluidKind,
    FluidValidationError,
    FluidValidityError,
    IdealGasModel,
    PolynomialCp,
    PropertyFidelity,
    PropertyId,
    Species,
    WindState,
    WorkingFluid,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "advphys" / "fluid"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _air() -> WorkingFluid:
    return fp.dry_air_fluid()


# -- A. species and composition ----------------------------------------------


def test_advphys01_builtin_species_registry_is_present() -> None:
    for species_id in ("air", "n2", "o2", "ar", "co2", "h2o", "ch4"):
        assert species_id in fp.registered_species_ids()
        assert fp.get_species(species_id).molar_mass_kg_per_mol > 0.0


def test_advphys01_unknown_species_fails_closed() -> None:
    with pytest.raises(FluidValidationError):
        fp.get_species("not-a-species")
    with pytest.raises(FluidValidationError):
        Composition.from_mole_fractions((("not-a-species", 1.0),))


def test_advphys01_pure_species_fluid_requires_single_species() -> None:
    with pytest.raises(FluidValidationError):
        WorkingFluid(
            fluid_id="bad",
            revision="1",
            kind=FluidKind.PURE_SPECIES,
            composition=_air().composition,
        )


def test_advphys01_composition_is_order_independent_and_normalized() -> None:
    first = Composition.from_mole_fractions((("o2", 0.21), ("n2", 0.79)))
    second = Composition.from_mole_fractions((("n2", 0.79), ("o2", 0.21)))
    assert first == second
    assert first.digest() == second.digest()
    assert sum(fraction for _, fraction in first.species) == pytest.approx(1.0)

    normalized = Composition.from_mole_fractions(
        (("n2", 0.78084), ("o2", 0.20946), ("ar", 0.00934), ("co2", 0.000412))
    )
    assert sum(fraction for _, fraction in normalized.species) == pytest.approx(1.0)


def test_advphys01_composition_rejects_invalid_fractions() -> None:
    with pytest.raises(FluidValidationError):
        Composition.from_mole_fractions((("n2", 0.2), ("o2", 0.2)))
    with pytest.raises(FluidValidationError):
        Composition(species=(("n2", 1.5),))


def test_advphys01_mass_and_mole_fraction_conversion_round_trip() -> None:
    mole = _air().composition
    mass = mole.mass_fractions()
    rebuilt = Composition.from_mass_fractions(mass)
    for name, fraction in mole.mole_fractions():
        assert rebuilt.mole_fraction(name) == pytest.approx(fraction, abs=1e-12)


# -- B. fluid identity and revisioning ---------------------------------------


def test_advphys01_fluid_digest_is_deterministic_and_revision_sensitive() -> None:
    first = _air()
    second = _air()
    assert fp.fluid_digest(first) == fp.fluid_digest(second)
    assert len(fp.fluid_digest(first)) == 64

    revised = WorkingFluid(
        fluid_id=first.fluid_id,
        revision="2",
        kind=first.kind,
        composition=first.composition,
        default_fidelity=first.default_fidelity,
        transport=first.transport,
    )
    assert fp.fluid_digest(revised) != fp.fluid_digest(first)
    assert revised.identity == "dry-air@2"


def test_advphys01_fluid_round_trips_through_canonical_payload() -> None:
    fluid = _air()
    rebuilt = fp.fluid_from_payload(fluid.canonical_payload())
    assert rebuilt.identity == fluid.identity
    assert rebuilt.digest() == fluid.digest()
    assert rebuilt.kind is fluid.kind
    assert rebuilt.transport is not None


# -- C. ideal-gas evaluation -------------------------------------------------


def test_advphys01_air_reference_state_is_physical() -> None:
    evaluation = fp.evaluate_ideal_gas(_air(), temperature_k=288.15, pressure_pa=101325.0)
    assert evaluation.value(PropertyId.SPECIFIC_GAS_CONSTANT) == pytest.approx(287.05, abs=0.1)
    assert evaluation.value(PropertyId.GAMMA) == pytest.approx(1.4, abs=0.01)
    assert evaluation.value(PropertyId.DENSITY) == pytest.approx(1.225, abs=0.005)
    assert evaluation.value(PropertyId.SPEED_OF_SOUND) == pytest.approx(340.29, abs=0.6)


def test_advphys01_thermodynamic_identities_hold() -> None:
    evaluation = fp.evaluate_ideal_gas(_air(), temperature_k=320.0, pressure_pa=90000.0)
    cp = evaluation.value(PropertyId.CP)
    cv = evaluation.value(PropertyId.CV)
    gamma = evaluation.value(PropertyId.GAMMA)
    specific_gas_constant = evaluation.value(PropertyId.SPECIFIC_GAS_CONSTANT)
    assert cp - cv == pytest.approx(specific_gas_constant, rel=1e-12)
    assert cp / cv == pytest.approx(gamma, rel=1e-12)
    assert evaluation.value(PropertyId.INTERNAL_ENERGY) == pytest.approx(
        evaluation.value(PropertyId.ENTHALPY) - specific_gas_constant * 320.0, rel=1e-12
    )
    assert evaluation.value(PropertyId.SPEED_OF_SOUND) == pytest.approx(
        (gamma * specific_gas_constant * 320.0) ** 0.5, rel=1e-12
    )


def test_advphys01_enthalpy_difference_integrates_cp() -> None:
    model = IdealGasModel(_air())
    low = model.evaluate(temperature_k=280.0, pressure_pa=101325.0)
    high = model.evaluate(temperature_k=360.0, pressure_pa=101325.0)
    delta = high.value(PropertyId.ENTHALPY) - low.value(PropertyId.ENTHALPY)
    assert delta == pytest.approx(low.value(PropertyId.CP) * 80.0, rel=1e-12)


def test_advphys01_entropy_log_depends_on_pressure() -> None:
    model = IdealGasModel(_air())
    low = model.evaluate(temperature_k=300.0, pressure_pa=50000.0)
    high = model.evaluate(temperature_k=300.0, pressure_pa=100000.0)
    specific_gas_constant = low.value(PropertyId.SPECIFIC_GAS_CONSTANT)
    expected = -specific_gas_constant * math.log(2.0)
    assert high.value(PropertyId.ENTROPY) - low.value(PropertyId.ENTROPY) == pytest.approx(
        expected, rel=1e-12
    )


def test_advphys01_result_carries_full_contract() -> None:
    result = fp.evaluate_ideal_gas(
        _air(), temperature_k=288.15, pressure_pa=101325.0
    ).get(PropertyId.CP)
    assert result.unit == "J/(kg K)"
    assert result.fidelity is PropertyFidelity.CONSTANT_IDEAL_GAS
    assert result.provenance.source is ResultSource.ANALYTICAL
    assert len(result.provenance.inputs_hash) == 64
    assert result.software.name == fp.SOFTWARE_NAME
    assert result.validity.contains(288.15)
    canonical = result.canonical()
    assert canonical["unit"] == "J/(kg K)"
    assert canonical["inputsHash"] == result.provenance.inputs_hash
    assert canonical["software"] == {"name": fp.SOFTWARE_NAME, "version": fp.SOFTWARE_VERSION}


# -- D. validity and capability fail-closed ----------------------------------


def test_advphys01_out_of_range_temperature_fails_closed() -> None:
    with pytest.raises(FluidValidityError):
        fp.evaluate_ideal_gas(_air(), temperature_k=50.0, pressure_pa=101325.0)


def test_advphys01_out_of_range_pressure_fails_closed() -> None:
    with pytest.raises(FluidValidityError):
        fp.evaluate_ideal_gas(_air(), temperature_k=288.15, pressure_pa=1.0e12)


def test_advphys01_missing_transport_fails_closed() -> None:
    evaluation = fp.evaluate_ideal_gas(
        fp.pure_species_fluid("co2"), temperature_k=300.0, pressure_pa=101325.0
    )
    assert not evaluation.has(PropertyId.VISCOSITY)
    with pytest.raises(FluidCapabilityUnavailableError):
        evaluation.get(PropertyId.VISCOSITY)


def test_advphys01_ideal_model_rejects_native_fidelity() -> None:
    with pytest.raises(FluidValidationError):
        IdealGasModel(_air(), fidelity=PropertyFidelity.REAL_GAS)


def test_advphys01_air_transport_is_physical() -> None:
    evaluation = fp.evaluate_ideal_gas(_air(), temperature_k=288.15, pressure_pa=101325.0)
    viscosity = evaluation.value(PropertyId.VISCOSITY)
    assert 1.7e-5 < viscosity < 1.9e-5
    assert evaluation.value(PropertyId.THERMAL_CONDUCTIVITY) == pytest.approx(
        viscosity * evaluation.value(PropertyId.CP) / evaluation.value(PropertyId.PRANDTL)
    )


# -- E. temperature-dependent ideal mixture ----------------------------------


def _register_fixture_species(fixture: dict[str, Any]) -> None:
    for entry in fixture["species"]:
        polynomials = tuple(
            PolynomialCp(
                coefficients=tuple(poly["coefficients"]),
                temperature_min_k=poly["temperatureMinK"],
                temperature_max_k=poly["temperatureMaxK"],
                reference_temperature_k=poly["referenceTemperatureK"],
            )
            for poly in entry["polynomials"]
        )
        fp.register_species(
            Species(
                species_id=entry["speciesId"],
                name=entry["name"],
                molar_mass_kg_per_mol=entry["molarMassKgPerMol"],
                polynomials=polynomials,
                source=entry["source"],
            )
        )


def test_advphys01_temperature_dependent_mixture_matches_polynomial() -> None:
    fixture = load_fixture("temperature_dependent_mixture.json")
    _register_fixture_species(fixture)
    fluid = WorkingFluid(
        fluid_id="syn-mixture",
        revision="1",
        kind=FluidKind.USER_MIXTURE,
        composition=Composition.from_mole_fractions(tuple(fixture["composition"].items())),
        default_fidelity=PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE,
    )
    state = fixture["state"]
    evaluation = fp.evaluate_ideal_gas(
        fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    )
    assert evaluation.fidelity is PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE

    expected_cp = 0.0
    for name, mass_fraction in fluid.composition.mass_fractions():
        species = fp.get_species(name)
        coefficient, slope = species.polynomials[0].coefficients
        r_specific = species.r_specific_j_kg_k
        expected_cp += mass_fraction * (coefficient + slope * state["temperatureK"]) * r_specific
    assert evaluation.value(PropertyId.CP) == pytest.approx(expected_cp, rel=1e-12)


def test_advphys01_temperature_dependent_enthalpy_matches_numeric_integral() -> None:
    fixture = load_fixture("temperature_dependent_mixture.json")
    _register_fixture_species(fixture)
    fluid = WorkingFluid(
        fluid_id="syn-mixture",
        revision="1",
        kind=FluidKind.USER_MIXTURE,
        composition=Composition.from_mole_fractions(tuple(fixture["composition"].items())),
        default_fidelity=PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE,
    )
    model = IdealGasModel(fluid)
    low = model.evaluate(temperature_k=600.0, pressure_pa=200000.0)
    high = model.evaluate(temperature_k=900.0, pressure_pa=200000.0)

    steps = 4000
    total = 0.0
    previous = model.evaluate(temperature_k=600.0, pressure_pa=200000.0).value(PropertyId.CP)
    for index in range(1, steps + 1):
        temperature = 600.0 + 300.0 * index / steps
        current = model.evaluate(
            temperature_k=temperature, pressure_pa=200000.0
        ).value(PropertyId.CP)
        total += 0.5 * (previous + current) * (300.0 / steps)
        previous = current
    assert high.value(PropertyId.ENTHALPY) - low.value(PropertyId.ENTHALPY) == pytest.approx(
        total, rel=1e-6
    )


def test_advphys01_temperature_dependent_out_of_range_fails() -> None:
    fixture = load_fixture("temperature_dependent_mixture.json")
    _register_fixture_species(fixture)
    fluid = WorkingFluid(
        fluid_id="syn-mixture",
        revision="1",
        kind=FluidKind.USER_MIXTURE,
        composition=Composition.from_mole_fractions(tuple(fixture["composition"].items())),
        default_fidelity=PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE,
    )
    with pytest.raises(FluidValidityError):
        fp.evaluate_ideal_gas(
            fluid,
            temperature_k=fixture["expect"]["outOfRangeTemperatureK"],
            pressure_pa=200000.0,
        )


# -- F. standard atmosphere --------------------------------------------------


def test_advphys01_isa_sea_level_golden() -> None:
    state = fp.ISA.evaluate(altitude_m=0.0)
    assert state.temperature_k == pytest.approx(288.15, abs=1e-9)
    assert state.pressure_pa == pytest.approx(101325.0, rel=1e-9)
    assert state.density_kg_m3 == pytest.approx(1.225, abs=0.005)
    assert state.speed_of_sound_m_s == pytest.approx(340.29, abs=0.6)
    assert state.provenance.source is ResultSource.ANALYTICAL
    assert len(state.provenance.inputs_hash) == 64


def test_advphys01_isa_tropopause_and_stratosphere() -> None:
    tropopause_temperature, tropopause_pressure = fp.ISA.temperature_pressure(11000.0)
    assert tropopause_temperature == pytest.approx(216.65, abs=1e-6)
    assert tropopause_pressure == pytest.approx(22632.0, rel=0.002)

    fifteen_temperature, fifteen_pressure = fp.ISA.temperature_pressure(15000.0)
    assert fifteen_temperature == pytest.approx(216.65, abs=1e-6)
    assert fifteen_pressure == pytest.approx(12044.6, rel=0.005)


def test_advphys01_isa_out_of_range_fails_closed() -> None:
    with pytest.raises(FluidValidityError):
        fp.ISA.evaluate(altitude_m=90000.0)
    with pytest.raises(FluidValidityError):
        fp.ISA.evaluate(altitude_m=-10.0)


def test_advphys01_atmosphere_shares_fluid_definition() -> None:
    manifest = fp.ISA.participant_manifest()
    assert manifest["participantId"] == "environment-standard-atmosphere"
    assert manifest["fluid"] == _air().identity
    assert manifest["fluidDigest"] == fp.fluid_digest(_air())


def test_advphys01_atmosphere_temperature_offset_and_wind() -> None:
    baseline = fp.ISA.evaluate(altitude_m=0.0)
    offset = fp.ISA.evaluate(
        altitude_m=0.0, temperature_offset_k=12.0, wind=WindState(speed_m_s=5.0, heading_deg=90.0)
    )
    assert offset.temperature_k == pytest.approx(baseline.temperature_k + 12.0)
    assert offset.density_kg_m3 < baseline.density_kg_m3
    assert offset.wind.canonical() == {"speedMS": 5.0, "headingDeg": 90.0}


def test_advphys01_saturation_pressure_is_monotonic() -> None:
    values = [fp.saturation_pressure_water_pa(t) for t in (273.15, 283.15, 293.15, 303.15)]
    assert all(later > earlier for earlier, later in zip(values, values[1:], strict=False))
    assert fp.saturation_pressure_water_pa(298.15) == pytest.approx(3161.9, abs=4.0)


def test_advphys01_humid_air_is_less_dense_than_dry_air() -> None:
    dry = fp.ISA.evaluate(altitude_m=0.0)
    humid = fp.ISA.evaluate(altitude_m=0.0, relative_humidity=0.5)
    assert humid.relative_humidity == pytest.approx(0.5)
    assert "humid" in humid.fluid_identity
    assert humid.density_kg_m3 < dry.density_kg_m3


# -- G. combustion products --------------------------------------------------


def test_advphys01_frozen_combustion_products_evaluate() -> None:
    fixture = load_fixture("hot_combustion_products.json")
    fluid = fp.combustion_products_fluid(tuple(fixture["products"].items()))
    state = fixture["state"]
    evaluation = fp.evaluate_ideal_gas(
        fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    )
    assert evaluation.fidelity is PropertyFidelity.FROZEN_COMBUSTION_GAS
    expected_cp = sum(
        mass_fraction * fp.get_species(name).constant_cp_j_kg_k
        for name, mass_fraction in fluid.composition.mass_fractions()
    )
    assert evaluation.value(PropertyId.CP) == pytest.approx(expected_cp, rel=1e-12)
    assert evaluation.value(PropertyId.GAMMA) > 1.0
    assert evaluation.value(PropertyId.SPEED_OF_SOUND) > 0.0


def test_advphys01_equilibrium_fails_closed_without_backend() -> None:
    co2 = fp.pure_species_fluid("co2")
    with pytest.raises(FluidCapabilityUnavailableError):
        fp.require_equilibrium_capability()
    with pytest.raises(FluidCapabilityUnavailableError):
        fp.evaluate_equilibrium(co2, temperature_k=1800.0, pressure_pa=300000.0)


class _FakeEquilibriumBackend:
    backend_id = "fake-equilibrium"
    software_version = "1.2.3"

    def mechanism(self) -> str:
        return "synthetic.yaml"

    def temperature_validity(self, fluid: WorkingFluid) -> fp.ValidityRange:
        return fluid.temperature_range()

    def properties(
        self, fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
    ) -> Mapping[PropertyId, float]:
        return {
            PropertyId.DENSITY: 0.5,
            PropertyId.CP: 1600.0,
            PropertyId.GAMMA: 1.31,
        }


def test_advphys01_equilibrium_native_backend_seam_is_native() -> None:
    fluid = fp.combustion_products_fluid((("n2", 0.7), ("co2", 0.3)))
    results = fp.evaluate_equilibrium(
        fluid,
        backend=_FakeEquilibriumBackend(),
        temperature_k=1800.0,
        pressure_pa=300000.0,
        properties=(PropertyId.DENSITY, PropertyId.CP, PropertyId.GAMMA),
        run_id="equil-run-1",
    )
    by_id = {result.property: result for result in results}
    assert by_id[PropertyId.CP].value_si == pytest.approx(1600.0)
    assert by_id[PropertyId.CP].fidelity is PropertyFidelity.EQUILIBRIUM_COMBUSTION_GAS
    assert by_id[PropertyId.CP].provenance.source is ResultSource.NATIVE_SOLVER
    assert by_id[PropertyId.CP].provenance.solver_name == "fake-equilibrium"
    assert by_id[PropertyId.CP].provenance.run_id == "equil-run-1"
    assert len(by_id[PropertyId.CP].provenance.inputs_hash) == 64


# -- H. real gas -------------------------------------------------------------


class _FakeRealGasBackend:
    backend_id = "fake-heos"
    software_version = "9.9.9"

    def temperature_validity(self, fluid: WorkingFluid) -> fp.ValidityRange:
        return fluid.temperature_range()

    def properties(
        self, fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
    ) -> Mapping[PropertyId, float]:
        return {
            PropertyId.DENSITY: pressure_pa
            / (fluid.specific_gas_constant_j_kg_k * temperature_k),
            PropertyId.ENTHALPY: 1000.0 * temperature_k,
            PropertyId.COMPRESSIBILITY_FACTOR: 0.9,
        }

    def jacobian(
        self,
        fluid: WorkingFluid,
        *,
        temperature_k: float,
        pressure_pa: float,
        properties: tuple[PropertyId, ...],
        with_respect_to: tuple[str, ...],
    ) -> Mapping[tuple[PropertyId, str], float]:
        return {
            (prop, wrt): (1.0 if wrt == "temperature" else 2.0)
            for prop in properties
            for wrt in with_respect_to
        }


class _FakeNoJacobianBackend:
    backend_id = "fake-no-jacobian"
    software_version = "9.9.9"

    def temperature_validity(self, fluid: WorkingFluid) -> fp.ValidityRange:
        return fluid.temperature_range()

    def properties(
        self, fluid: WorkingFluid, *, temperature_k: float, pressure_pa: float
    ) -> Mapping[PropertyId, float]:
        return {PropertyId.DENSITY: 1.0}


def test_advphys01_real_gas_backend_seam_carries_native_identity() -> None:
    co2 = fp.pure_species_fluid("co2")
    results = fp.evaluate_real_gas(
        co2,
        backend=_FakeRealGasBackend(),
        temperature_k=300.0,
        pressure_pa=5000000.0,
        properties=(PropertyId.DENSITY, PropertyId.ENTHALPY, PropertyId.COMPRESSIBILITY_FACTOR),
    )
    by_id = {result.property: result for result in results}
    assert by_id[PropertyId.COMPRESSIBILITY_FACTOR].value_si == pytest.approx(0.9)
    assert by_id[PropertyId.DENSITY].fidelity is PropertyFidelity.REAL_GAS
    provenance = by_id[PropertyId.DENSITY].provenance
    assert provenance.source is ResultSource.NATIVE_SOLVER
    assert provenance.solver_name == "fake-heos"
    assert provenance.solver_version == "9.9.9"
    assert provenance.run_id is not None and provenance.run_id.startswith("realgas-")


def test_advphys01_real_gas_native_path_or_fail_closed() -> None:
    co2 = fp.pure_species_fluid("co2")
    capability = fp.probe_backend(fp.PropertyBackend.COOLPROP)
    if not capability.available:
        with pytest.raises(FluidCapabilityUnavailableError):
            fp.evaluate_real_gas(co2, temperature_k=300.0, pressure_pa=5000000.0)
        return
    results = fp.evaluate_real_gas(co2, temperature_k=300.0, pressure_pa=5000000.0)
    by_id = {result.property: result for result in results}
    assert by_id[PropertyId.COMPRESSIBILITY_FACTOR].value_si == pytest.approx(0.687, abs=0.05)
    assert by_id[PropertyId.DENSITY].provenance.solver_name == "coolprop"
    assert by_id[PropertyId.DENSITY].fidelity is PropertyFidelity.REAL_GAS


def test_advphys01_real_gas_jacobian_seam() -> None:
    co2 = fp.pure_species_fluid("co2")
    jacobian = fp.evaluate_real_gas_jacobian(
        co2,
        backend=_FakeRealGasBackend(),
        temperature_k=300.0,
        pressure_pa=5000000.0,
        properties=(PropertyId.ENTHALPY, PropertyId.DENSITY),
    )
    assert jacobian.value(PropertyId.ENTHALPY, "temperature") == pytest.approx(1.0)
    assert jacobian.value(PropertyId.DENSITY, "pressure") == pytest.approx(2.0)
    assert jacobian.provenance.source is ResultSource.NATIVE_SOLVER


def test_advphys01_real_gas_jacobian_fails_closed_when_unsupported() -> None:
    co2 = fp.pure_species_fluid("co2")
    with pytest.raises(FluidCapabilityUnavailableError):
        fp.evaluate_real_gas_jacobian(
            co2,
            backend=_FakeNoJacobianBackend(),
            temperature_k=300.0,
            pressure_pa=5000000.0,
        )


# -- I. adapters -------------------------------------------------------------


def test_advphys01_adapters_share_one_fluid_definition() -> None:
    fluid = _air()
    digest = fp.fluid_digest(fluid)
    openfoam = fp.export_openfoam_fluid(fluid, temperature_k=288.15, pressure_pa=101325.0)
    pycycle = fp.export_pycycle_fluid(fluid, temperature_k=288.15, pressure_pa=101325.0)
    reduced = fp.export_reduced_fluid(fluid)
    cantera = fp.export_cantera_fluid(fluid)
    assert openfoam["fluidDigest"] == digest
    assert pycycle["fluidDigest"] == digest
    assert reduced["fluidDigest"] == digest
    assert cantera["fluidDigest"] == digest
    assert openfoam["source"] == ResultSource.ANALYTICAL.value
    assert len(openfoam["inputsHash"]) == 64  # type: ignore[arg-type]
    assert pycycle["gamma"] == pytest.approx(1.4, abs=0.01)
    assert reduced["R"] == pytest.approx(287.05, abs=0.1)
    assert cantera["species"] == ["ar", "co2", "n2", "o2"]


def test_advphys01_adapter_requires_transport_and_ideal_fidelity() -> None:
    with pytest.raises(FluidCapabilityUnavailableError):
        fp.export_openfoam_fluid(
            fp.pure_species_fluid("co2"), temperature_k=300.0, pressure_pa=101325.0
        )
    native_fluid = WorkingFluid(
        fluid_id="co2-real",
        revision="1",
        kind=FluidKind.PURE_SPECIES,
        composition=Composition.from_mole_fractions((("co2", 1.0),)),
        default_fidelity=PropertyFidelity.REAL_GAS,
    )
    with pytest.raises(FluidCapabilityUnavailableError):
        fp.export_reduced_fluid(native_fluid)


# -- J. portability fixtures -------------------------------------------------


def test_advphys01_fixture_low_speed_external_flow() -> None:
    fixture = load_fixture("low_speed_external_flow.json")
    state = fixture["state"]
    evaluation = fp.evaluate_ideal_gas(
        _air(), temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    )
    expect = fixture["expect"]
    assert evaluation.value(PropertyId.GAMMA) == pytest.approx(
        expect["gamma"], abs=expect["gammaTolerance"]
    )
    assert evaluation.value(PropertyId.SPEED_OF_SOUND) == pytest.approx(
        expect["speedOfSoundMS"], abs=expect["speedToleranceMS"]
    )
    assert evaluation.value(PropertyId.DENSITY) == pytest.approx(
        expect["densityKgM3"], abs=expect["densityTolerance"]
    )
    assert evaluation.get(PropertyId.GAMMA).provenance.source.value == expect["source"]


def test_advphys01_fixture_high_altitude_high_mach() -> None:
    fixture = load_fixture("high_altitude_high_mach.json")
    temperature, pressure = fp.ISA.temperature_pressure(fixture["altitudeM"])
    expect = fixture["expect"]
    assert temperature == pytest.approx(expect["temperatureK"], abs=expect["temperatureTolerance"])
    assert pressure == pytest.approx(
        expect["pressurePa"], rel=expect["pressureTolerancePct"] / 100.0
    )
    evaluation = fp.evaluate_ideal_gas(_air(), temperature_k=temperature, pressure_pa=pressure)
    gamma = evaluation.value(PropertyId.GAMMA)
    total_temperature = temperature * (
        1.0 + (gamma - 1.0) / 2.0 * fixture["mach"] ** 2
    )
    hot = fp.evaluate_ideal_gas(_air(), temperature_k=total_temperature, pressure_pa=pressure)
    assert hot.value(PropertyId.SPEED_OF_SOUND) > evaluation.value(PropertyId.SPEED_OF_SOUND)


def test_advphys01_fixture_hot_combustion_products() -> None:
    fixture = load_fixture("hot_combustion_products.json")
    fluid = fp.combustion_products_fluid(tuple(fixture["products"].items()))
    state = fixture["state"]
    evaluation = fp.evaluate_ideal_gas(
        fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    )
    assert evaluation.fidelity.value == fixture["expect"]["fidelity"]
    assert evaluation.get(PropertyId.CP).provenance.source.value == fixture["expect"]["source"]


def test_advphys01_fixture_humid_air() -> None:
    fixture = load_fixture("humid_air.json")
    state = fixture["state"]
    dry = Composition.from_mole_fractions(tuple(fixture["dryAir"].items()))
    composition = fp.humid_air_composition(
        dry,
        temperature_k=state["temperatureK"],
        pressure_pa=state["pressurePa"],
        relative_humidity=state["relativeHumidity"],
    )
    expect = fixture["expect"]
    assert composition.mole_fraction("h2o") == pytest.approx(
        expect["waterVapourMoleFraction"], abs=expect["waterVapourTolerance"]
    )
    assert fp.saturation_pressure_water_pa(state["temperatureK"]) == pytest.approx(
        expect["saturationPressurePa"], abs=expect["saturationTolerancePa"]
    )
    fluid = fp.humid_air_fluid(
        temperature_k=state["temperatureK"],
        pressure_pa=state["pressurePa"],
        relative_humidity=state["relativeHumidity"],
    )
    assert fluid.kind is FluidKind.HUMID_AIR
    assert fp.evaluate_ideal_gas(
        fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    ).value(PropertyId.DENSITY) > 0.0


def test_advphys01_fixture_non_air_real_gas() -> None:
    fixture = load_fixture("non_air_real_gas.json")
    fluid = fp.pure_species_fluid(fixture["species"])
    state = fixture["state"]
    capability = fp.probe_backend(fp.PropertyBackend.COOLPROP)
    if not capability.available:
        with pytest.raises(FluidCapabilityUnavailableError):
            fp.evaluate_real_gas(
                fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
            )
        return
    results = fp.evaluate_real_gas(
        fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    )
    by_id = {result.property: result for result in results}
    expect = fixture["expect"]
    assert by_id[PropertyId.COMPRESSIBILITY_FACTOR].value_si == pytest.approx(
        expect["compressibilityFactor"], abs=expect["compressibilityTolerance"]
    )
    assert by_id[PropertyId.DENSITY].provenance.source is ResultSource.NATIVE_SOLVER


def test_advphys01_fixture_temperature_dependent_mixture() -> None:
    fixture = load_fixture("temperature_dependent_mixture.json")
    _register_fixture_species(fixture)
    fluid = WorkingFluid(
        fluid_id="syn-mixture-fixture",
        revision="1",
        kind=FluidKind.USER_MIXTURE,
        composition=Composition.from_mole_fractions(tuple(fixture["composition"].items())),
        default_fidelity=PropertyFidelity.TEMPERATURE_DEPENDENT_IDEAL_MIXTURE,
    )
    state = fixture["state"]
    evaluation = fp.evaluate_ideal_gas(
        fluid, temperature_k=state["temperatureK"], pressure_pa=state["pressurePa"]
    )
    assert evaluation.fidelity.value == fixture["expect"]["fidelity"]
    assert evaluation.value(PropertyId.CP) > 0.0
    with pytest.raises(FluidValidityError):
        fp.evaluate_ideal_gas(
            fluid,
            temperature_k=fixture["expect"]["outOfRangeTemperatureK"],
            pressure_pa=state["pressurePa"],
        )
