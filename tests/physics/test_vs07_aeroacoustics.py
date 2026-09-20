"""VS 07: vehicle aeroacoustics and observer/community-noise optimization.

Tiny deterministic fixtures: a 3-blade propulsor screened from declared
harmonic amplitudes, an airframe contributor scaled from a declared reference,
and a community grid sampled over a two-point trajectory. Blade count and rpm
drive tonal orders, observer distance drives propagated levels, source and
propagation fidelities are reported separately, missing transient or native
data fails closed, and noise outputs constrain a generic campaign study.
"""

from __future__ import annotations

import json
from math import log10
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_optimization import (
    DesignVariable,
    OperatingPointEval,
    run_sweep,
)
from aeroworkbench_vehicle_systems.aeroacoustics import (
    AirframeContributor,
    AirframeReference,
    CapabilityUnavailable,
    ContractError,
    EnvironmentSpec,
    FlightState,
    FootprintGrid,
    NoiseFidelity,
    NoiseTradeModel,
    ObserverSpec,
    RotorSpec,
    TrajectorySample,
    ValidityError,
    Weighting,
    assess_observer_noise,
    blade_passing_frequency_hz,
    footprint_from_trajectory,
    ingest_surface_record,
    lines_from_airframe,
    lines_from_broadband,
    lines_from_interaction,
    lines_from_rotor,
    noise_campaign_outputs,
    noise_constraint,
    noise_objective,
    noise_trade_evaluator,
    propagate_fw_h_native,
    propagate_spectrum_to_observer,
    propagate_to_observer,
    require_native_caa,
    rotor_tonal_orders,
    sample_footprint,
    screen_airframe_source,
    screen_broadband,
    screen_rotor_airframe_interaction,
    screen_rotor_tones,
    shaft_frequency_hz,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "vehicle_systems" / "aeroacoustics"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _rotor(payload: dict[str, Any]) -> RotorSpec:
    return RotorSpec(
        rotor_id=str(payload["rotorId"]),
        blade_count=int(payload["bladeCount"]),
        rpm=float(payload["rpm"]),
        radius_m=float(payload["radiusM"]),
        thrust_n=float(payload["thrustN"]),
    )


def _observer(payload: dict[str, Any]) -> ObserverSpec:
    return ObserverSpec(
        observer_id=str(payload["observerId"]),
        position_m=tuple(float(value) for value in payload["positionM"]),  # type: ignore[arg-type]
    )


def _environment(payload: dict[str, Any]) -> EnvironmentSpec:
    return EnvironmentSpec(
        speed_of_sound_m_s=float(payload["speedOfSoundMS"]),
        density_kg_m3=float(payload["densityKgM3"]),
        absorption_db_per_m=float(payload["absorptionDbPerM"]),
        reference_distance_m=float(payload["referenceDistanceM"]),
    )


def _flight(payload: dict[str, Any]) -> FlightState:
    return FlightState(
        source_position_m=tuple(float(value) for value in payload["sourcePositionM"]),  # type: ignore[arg-type]  # noqa: E501
        source_velocity_m_s=tuple(float(value) for value in payload["sourceVelocityMS"]),  # type: ignore[arg-type]  # noqa: E501
        time_s=float(payload["timeS"]),
    )


def _screened(payload: dict[str, Any]) -> Any:
    spec = _rotor(payload)
    amplitudes = {
        int(key): float(value) for key, value in payload["amplitudesPaByHarmonic"].items()
    }
    return screen_rotor_tones(
        spec, amplitudes, harmonics=int(payload["harmonics"]),
        reference_pressure_pa=float(payload["referencePressurePa"]),
    )


def test_rotor_orders_follow_blade_count_and_rpm() -> None:
    payload = _load("rotor.json")
    spec = _rotor(payload)
    assert shaft_frequency_hz(spec) == pytest.approx(20.0)
    assert blade_passing_frequency_hz(spec) == pytest.approx(60.0)
    tones = rotor_tonal_orders(spec, harmonics=3)
    assert [tone.frequency_hz for tone in tones] == pytest.approx([60.0, 120.0, 180.0])
    assert [tone.order for tone in tones] == [3.0, 6.0, 9.0]
    faster = RotorSpec(rotor_id="fast", blade_count=4, rpm=2400.0)
    assert blade_passing_frequency_hz(faster) == pytest.approx(160.0)
    assert rotor_tonal_orders(faster, harmonics=1)[0].frequency_hz == pytest.approx(160.0)


def test_screening_needs_declared_amplitudes() -> None:
    payload = _load("rotor.json")
    spec = _rotor(payload)
    with pytest.raises(ContractError):
        screen_rotor_tones(spec, {})
    partial = screen_rotor_tones(spec, {1: 0.42}, harmonics=3)
    assert len(partial.lines) == 1
    assert partial.dominant_frequency_hz == pytest.approx(60.0)
    assert partial.fidelity is NoiseFidelity.TONAL_SCREENING
    assert partial.validity.passed


def test_observer_distance_affects_propagated_result() -> None:
    payload = _load("rotor.json")
    screening = _screened(payload)
    lines = lines_from_rotor(screening)
    env = _environment(payload["environment"])
    flight = _flight(payload["flight"])
    near = propagate_to_observer(
        lines,
        ObserverSpec(observer_id="near", position_m=(50.0, 0.0, 1.2)),
        env, flight, source_fidelity=NoiseFidelity.TONAL_SCREENING,
    )
    far = propagate_to_observer(
        lines,
        ObserverSpec(observer_id="far", position_m=(400.0, 0.0, 1.2)),
        env, flight, source_fidelity=NoiseFidelity.TONAL_SCREENING,
    )
    assert near.overall_level_db > far.overall_level_db
    assert (near.overall_level_db - far.overall_level_db) == pytest.approx(
        20.0 * log10(far.distance_m / near.distance_m), abs=1e-9
    )


def test_doppler_motion_handling() -> None:
    payload = _load("rotor.json")
    screening = _screened(payload)
    lines = lines_from_rotor(screening)
    env = _environment(payload["environment"])
    observer = _observer(payload["observer"])
    static = propagate_to_observer(
        lines, observer, env,
        FlightState(source_position_m=(0.0, 0.0, 60.0)),
        source_fidelity=NoiseFidelity.TONAL_SCREENING,
    )
    assert static.doppler_factor == pytest.approx(1.0)
    approaching = propagate_to_observer(
        lines, observer, env, _flight(payload["flight"]),
        source_fidelity=NoiseFidelity.TONAL_SCREENING,
    )
    assert approaching.doppler_factor > 1.0
    assert approaching.lines[0].observed_frequency_hz > approaching.lines[0].source_frequency_hz
    with pytest.raises(ValidityError):
        propagate_to_observer(
            lines, observer, env,
            FlightState(
                source_position_m=(0.0, 0.0, 60.0),
                source_velocity_m_s=(500.0, 0.0, 0.0),
            ),
            source_fidelity=NoiseFidelity.TONAL_SCREENING,
        )


def test_source_and_propagation_fidelity_reported_separately() -> None:
    payload = _load("rotor.json")
    screening = _screened(payload)
    result = propagate_to_observer(
        lines_from_rotor(screening), _observer(payload["observer"]),
        _environment(payload["environment"]), _flight(payload["flight"]),
        source_fidelity=screening.fidelity,
    )
    assert result.source_fidelity is NoiseFidelity.TONAL_SCREENING
    assert result.propagation_fidelity is NoiseFidelity.OBSERVER_ANALYTICAL
    assert result.source == "analytical"
    assert len(result.input_hash) == 64
    assert result.units()["level_db"] == "dB"
    assert set(result.canonical_payload()) >= {
        "sourceFidelity", "propagationFidelity", "inputsHash", "software",
    }


def test_missing_transient_and_native_data_fail_closed() -> None:
    with pytest.raises(ContractError):
        ingest_surface_record([0.1, 0.2, 0.3], 1000.0, interface_id="tiny")
    with pytest.raises(CapabilityUnavailable):
        require_native_caa("fw-h-propagation")
    payload = _load("rotor.json")
    screening = _screened(payload)
    with pytest.raises(CapabilityUnavailable):
        propagate_fw_h_native(
            lines_from_rotor(screening), _observer(payload["observer"]),
            _environment(payload["environment"]), _flight(payload["flight"]),
            backend=None, run_id="run-1", source_fidelity=NoiseFidelity.TONAL_SCREENING,
        )
    with pytest.raises(ContractError):
        propagate_to_observer(
            [], _observer(payload["observer"]),
            _environment(payload["environment"]), _flight(payload["flight"]),
            source_fidelity=NoiseFidelity.TONAL_SCREENING,
        )


def test_ingested_spectrum_propagates_to_observer() -> None:
    record = [0.5 if index % 2 == 0 else -0.5 for index in range(16)]
    spectrum = ingest_surface_record(record, 2000.0, interface_id="blade-pass")
    assert spectrum.sample_count == 16
    payload = _load("rotor.json")
    result = propagate_spectrum_to_observer(
        spectrum, _observer(payload["observer"]),
        _environment(payload["environment"]), _flight(payload["flight"]),
    )
    assert result.validity.passed
    assert result.overall_level_db > 0.0


def test_airframe_scaling_and_validity() -> None:
    payload = _load("airframe.json")
    reference = AirframeReference(
        contributor=AirframeContributor(str(payload["contributor"])),
        velocity_m_s=float(payload["velocityMS"]),
        reference_velocity_m_s=float(payload["referenceVelocityMS"]),
        reference_level_db=float(payload["referenceLevelDb"]),
        exponent=float(payload["exponent"]),
        frequency_hz=float(payload["frequencyHz"]),
        mach_number=float(payload["machNumber"]),
    )
    screening = screen_airframe_source(reference)
    assert screening.scaled_level_db == pytest.approx(
        78.5 + 50.0 * log10(68.0 / 60.0), abs=1e-9
    )
    assert screening.validity.passed
    faster = AirframeReference(
        contributor=AirframeContributor.LANDING_GEAR,
        velocity_m_s=136.0, reference_velocity_m_s=68.0,
        reference_level_db=80.0, exponent=5.0, frequency_hz=400.0, mach_number=None,
    )
    assert screen_airframe_source(faster).scaled_level_db == pytest.approx(80.0 + 15.0515, abs=1e-3)
    supersonic = AirframeReference(
        contributor=AirframeContributor.HIGH_LIFT,
        velocity_m_s=200.0, reference_velocity_m_s=60.0,
        reference_level_db=80.0, exponent=5.0, frequency_hz=500.0, mach_number=0.9,
    )
    with pytest.raises(ContractError):
        screen_airframe_source(supersonic)


def test_broadband_and_interaction_seams() -> None:
    payload = _load("airframe.json")
    declared = [
        (float(frequency), float(pressure))
        for frequency, pressure in payload["broadband"]["declared"]
    ]
    broadband = screen_broadband(str(payload["broadband"]["contributor"]), declared)
    assert broadband.overall_level_db == pytest.approx(
        10.0 * log10(sum(10.0 ** (line.level_db / 10.0) for line in broadband.lines)),
        abs=1e-9,
    )
    rotor_payload = _load("rotor.json")
    spec = _rotor(rotor_payload)
    declared_map = {float(key): float(value) for key, value in payload["interaction"].items()}
    interaction = screen_rotor_airframe_interaction(spec, declared_map, harmonics=3)
    assert len(interaction.lines) == 2
    assert all(line.nearest_rotor_gap_hz >= 0.0 for line in interaction.lines)
    env = _environment(rotor_payload["environment"])
    flight = _flight(rotor_payload["flight"])
    observer = _observer(rotor_payload["observer"])
    combined = (
        lines_from_rotor(_screened(rotor_payload))
        + lines_from_broadband(broadband)
        + lines_from_interaction(interaction)
        + lines_from_airframe(
            screen_airframe_source(
                AirframeReference(
                    contributor=AirframeContributor.TRAILING_EDGE,
                    velocity_m_s=68.0, reference_velocity_m_s=60.0,
                    reference_level_db=78.5, exponent=5.0,
                    frequency_hz=800.0, mach_number=0.2,
                )
            )
        )
    )
    result = propagate_to_observer(
        combined, observer, env, flight, source_fidelity=NoiseFidelity.TONAL_SCREENING
    )
    assert len(result.lines) == len(combined)


def test_metrics_preserve_spectra_and_cite_standards() -> None:
    payload = _load("rotor.json")
    result = propagate_to_observer(
        lines_from_rotor(_screened(payload)), _observer(payload["observer"]),
        _environment(payload["environment"]), _flight(payload["flight"]),
        source_fidelity=NoiseFidelity.TONAL_SCREENING,
    )
    metrics = assess_observer_noise(result, weighting=Weighting.A, duration_s=10.0)
    assert metrics.oaspl_db == pytest.approx(result.overall_level_db)
    assert metrics.sel_db == pytest.approx(metrics.oaspl_db + 10.0 * log10(10.0), abs=1e-9)
    assert len(metrics.spectrum) == len(result.lines)
    assert any("IEC 61672" in standard for standard in metrics.standards)
    assert metrics.weighting is Weighting.A
    assert len(metrics.input_hash) == 64
    assert metrics.validity.passed


def test_footprint_max_at_nearest_observer() -> None:
    rotor_payload = _load("rotor.json")
    grid_payload = _load("footprint.json")
    grid = FootprintGrid(
        grid_id=str(grid_payload["gridId"]),
        origin_m=tuple(float(value) for value in grid_payload["originM"]),  # type: ignore[arg-type]
        spacing_m=float(grid_payload["spacingM"]),
        count_x=int(grid_payload["countX"]),
        count_y=int(grid_payload["countY"]),
        observer_height_m=float(grid_payload["observerHeightM"]),
    )
    env = _environment(grid_payload["environment"])
    lines = lines_from_rotor(_screened(rotor_payload))
    flight = FlightState(source_position_m=(0.0, 0.0, 60.0))
    footprint = sample_footprint(
        grid, lines, env, flight, source_fidelity=NoiseFidelity.TONAL_SCREENING
    )
    assert len(footprint.cells) == 9
    assert footprint.propagation_fidelity is NoiseFidelity.OBSERVER_ANALYTICAL
    nearest = min(
        grid.observers(),
        key=lambda observer: sum(
            (observed - emitted) ** 2
            for observed, emitted in zip(observer.position_m, (0.0, 0.0, 60.0), strict=True)
        ),
    )
    assert footprint.max_observer_id == nearest.observer_id
    assert footprint.area_above_db(0.0, grid.spacing_m) == pytest.approx(9 * 2500.0)
    assert footprint.area_above_db(1e9, grid.spacing_m) == pytest.approx(0.0)


def test_trajectory_footprint_worst_case() -> None:
    rotor_payload = _load("rotor.json")
    grid_payload = _load("footprint.json")
    grid = FootprintGrid(
        grid_id=str(grid_payload["gridId"]),
        origin_m=tuple(float(value) for value in grid_payload["originM"]),  # type: ignore[arg-type]
        spacing_m=float(grid_payload["spacingM"]),
        count_x=int(grid_payload["countX"]),
        count_y=int(grid_payload["countY"]),
        observer_height_m=float(grid_payload["observerHeightM"]),
    )
    env = _environment(grid_payload["environment"])
    lines = lines_from_rotor(_screened(rotor_payload))
    samples = tuple(
        TrajectorySample(
            time_s=float(entry["timeS"]),
            position_m=tuple(float(value) for value in entry["positionM"]),  # type: ignore[arg-type]  # noqa: E501
            velocity_m_s=tuple(float(value) for value in entry["velocityMS"]),  # type: ignore[arg-type]  # noqa: E501
            lines=lines,
        )
        for entry in grid_payload["samples"]
    )
    trajectory = footprint_from_trajectory(
        grid, samples, env, source_fidelity=NoiseFidelity.TONAL_SCREENING
    )
    assert trajectory.sample_count == 2
    single = sample_footprint(
        grid, lines, env, samples[0].flight(), source_fidelity=NoiseFidelity.TONAL_SCREENING
    )
    assert trajectory.max_level_db >= single.max_level_db
    assert trajectory.digest == footprint_from_trajectory(
        grid, samples, env, source_fidelity=NoiseFidelity.TONAL_SCREENING
    ).digest


def test_noise_constrains_vehicle_optimization() -> None:
    payload = _load("airframe.json")["trade"]
    model = NoiseTradeModel(
        reference_rpm=float(payload["referenceRpm"]),
        reference_noise_db=float(payload["referenceNoiseDb"]),
        rpm_exponent=float(payload["rpmExponent"]),
        reference_distance_m=float(payload["referenceDistanceM"]),
        thrust_per_rpm_n=float(payload["thrustPerRpmN"]),
    )
    study = {
        "variables": (
            DesignVariable("rpm", "rpm", "continuous", float(payload["rpmLower"]),
                           float(payload["rpmUpper"])),
            DesignVariable("distance_m", "m", "continuous", float(payload["distanceLower"]),
                           float(payload["distanceUpper"])),
        ),
        "objectives": (noise_objective(),),
        "constraints": (noise_constraint(float(payload["noiseLimitDb"])),),
        "operating_points": (OperatingPointEval("nominal", 1.0),),
    }
    result = run_sweep(study, noise_trade_evaluator(model), {"rpm": 4, "distance_m": 2})
    assert result.best is not None
    assert result.best.outputs["noise_db"] <= float(payload["noiseLimitDb"])
    ranked = [sample for sample in result.samples if sample.state == "valid"]
    assert ranked
    outputs = noise_campaign_outputs(
        propagate_to_observer(
            lines_from_rotor(_screened(_load("rotor.json"))),
            ObserverSpec(observer_id="campaign", position_m=(100.0, 0.0, 1.2)),
            EnvironmentSpec(), FlightState(source_position_m=(0.0, 0.0, 60.0)),
            source_fidelity=NoiseFidelity.TONAL_SCREENING,
        )
    )
    assert set(outputs) == {"noise_db", "observer_distance_m"}


def test_results_are_deterministic_and_fully_attributed() -> None:
    payload = _load("rotor.json")
    first = _screened(payload)
    second = _screened(payload)
    assert first.digest == second.digest
    assert first.canonical_payload() == second.canonical_payload()
    envelope = {
        "source": first.source,
        "fidelity": first.fidelity.value,
        "units": first.units(),
        "validity": first.validity.as_dict(),
        "inputHash": first.input_hash,
        "software": {"name": first.software, "version": first.software_version},
        "provenance": {
            "model": first.provenance.model,
            "inputsHash": first.provenance.inputs_hash,
        },
    }
    assert envelope["source"] == "analytical"
    assert len(str(envelope["inputHash"])) == 64
    assert all(envelope["units"].values())
    assert envelope["validity"]["passed"] is True
