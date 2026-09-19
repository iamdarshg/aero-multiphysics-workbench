"""ADV-PHYS 11: generic experiment, DAQ, system-identification, HIL evidence.

These tests drive the product-neutral experimental layer from tiny deterministic
fixtures: a typed experiment definition for two unrelated domains (wind tunnel
and structural), provenance-backed ingestion of raw tabular data (preserved and
content-addressed), sensor/calibration provenance, reproducible synchronization
and derived signals, measurement-versus-simulation comparison, bounded system
identification with a distinct calibration/validation split, HIL/replay, and a
fail-closed evidence contract that never conflates measurement with simulation.
Every result carries source/fidelity/units/validity/input-hash/software-identity/
provenance; nothing is fabricated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import FidelityLevel, ResultSource
from aeroworkbench_experiment import (
    CalibrationRevision,
    CapabilityUnavailable,
    ChannelSpec,
    ComparisonError,
    EnvironmentalState,
    EvidenceError,
    EvidenceFidelity,
    EvidenceKind,
    ExperimentError,
    ExperimentPlan,
    FilterSpec,
    Frame,
    IdentificationError,
    IngestionError,
    Observation,
    OperatingCondition,
    ParameterBound,
    Quantity,
    ReplayStream,
    SamplingSpec,
    SensorSpec,
    SimulationChannel,
    SimulationResultEnvelope,
    SynchronizationError,
    TabularAdapter,
    TestArticle,
    UnitError,
    Validity,
    align_to_trigger,
    apply_filter,
    assert_no_relabel,
    channel_provenance,
    compare_dataset,
    condition_key,
    corroborate,
    dataset_sensor_provenance,
    estimate_parameters,
    hil_capability,
    identify,
    ingest_tabular,
    match_dataset,
    measurement_evidence,
    measurement_provenance,
    native_solver_provenance,
    order_spectrum,
    promote_to_native,
    replay,
    require_hil_hardware,
    require_match,
    require_unit,
    resample,
    run_hardware,
    scalar_residual,
    segment_cycles,
    segment_events,
    simulation_evidence,
    simulation_provenance,
    spectrum,
    split_calibration_validation,
    to_si,
    trigger_time,
)
from aeroworkbench_rom.cache import MapArtifactCache

_FIXTURES = Path(__file__).resolve().parents[1] / "advphys" / "experiment"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _raw(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _plan(name: str = "wind_tunnel_plan.json") -> ExperimentPlan:
    payload = _fixture(name)
    calibrations = tuple(CalibrationRevision(**item) for item in payload["calibrations"])
    channels = tuple(
        ChannelSpec(
            name=item["name"],
            unit=item["unit"],
            lower=item["lower"],
            upper=item["upper"],
            role=item["role"],
            sensor=SensorSpec(
                sensor_id=item["sensor_id"],
                sensor_type=item["sensor_type"],
                unit=item["unit"],
                calibration_id=item["calibration_id"],
                uncertainty=item["uncertainty"],
                location_m=tuple(item["location_m"]),
                orientation_deg=tuple(item["orientation_deg"]),
                sample_rate_hz=item["sample_rate_hz"],
                filtering=tuple(item["filtering"]),
            ),
        )
        for item in payload["channels"]
    )
    condition = OperatingCondition(
        name=payload["condition"]["name"],
        values=tuple(
            (key, Quantity(value=spec["value"], unit=spec["unit"]))
            for key, spec in payload["condition"]["values"].items()
        ),
    )
    environment = EnvironmentalState(
        values=tuple(
            (key, Quantity(value=spec["value"], unit=spec["unit"]))
            for key, spec in payload["environment"]["values"].items()
        )
    )
    article = payload["article"]
    return ExperimentPlan(
        plan_id=payload["plan_id"],
        article=TestArticle(**article),
        design_revision=payload["design_revision"],
        configuration=payload["configuration"],
        condition=condition,
        environment=environment,
        channels=channels,
        calibrations=calibrations,
        sampling=SamplingSpec(**payload["sampling"]),
    )


_WT_COLUMNS = {
    "lift": ("lift_N", "N"),
    "drag": ("drag_N", "N"),
    "pressure": ("pressure_kPa", "kPa"),
}


def _dataset(
    plan: ExperimentPlan | None = None,
    raw_name: str = "wind_tunnel_raw.csv",
    *,
    columns: dict[str, tuple[str, str]] | None = None,
    cache: MapArtifactCache | None = None,
) -> Any:
    active_plan = plan or _plan()
    return ingest_tabular(
        active_plan,
        _raw(raw_name),
        dataset_id="ds-1",
        columns=columns or _WT_COLUMNS,
        time_column="time_ms",
        time_unit="ms",
        adapter=TabularAdapter(),
        artifact_cache=cache,
    )


def _structural_dataset() -> Any:
    return ingest_tabular(
        _plan("structural_plan.json"),
        _raw("structural_raw.csv"),
        dataset_id="ds-struct",
        columns={
            "strain": ("strain_microstrain", "microstrain"),
            "load": ("load_kN", "kN"),
            "accel": ("accel_g", "g0"),
        },
        time_column="time_ms",
        time_unit="ms",
    )


def _envelope(name: str, plan: ExperimentPlan) -> SimulationResultEnvelope:
    payload = _fixture(name)
    channels = tuple(
        SimulationChannel(
            name=item["name"],
            unit=item["unit"],
            values=tuple(item["values"]),
            time_s=None if "time_s" not in item else tuple(item["time_s"]),
            frequency_hz=None if "frequency_hz" not in item else tuple(item["frequency_hz"]),
        )
        for item in payload["channels"]
    )
    provenance = simulation_provenance(
        "fixture-simulation-envelope", {"envelopeId": payload["envelope_id"]}
    )
    return SimulationResultEnvelope(
        envelope_id=payload["envelope_id"],
        design_revision=payload["design_revision"],
        condition_key=plan.condition_key,
        channels=channels,
        source=ResultSource.ANALYTICAL,
        fidelity=FidelityLevel.ANALYTICAL,
        provenance=provenance,
    )


# -- A. units -----------------------------------------------------------------


def test_advphys11_si_units_are_known() -> None:
    for label in ("ms", "Hz", "rpm", "N", "kN", "lbf", "Pa", "kPa", "degC", "microstrain"):
        assert require_unit(label) == label


def test_advphys11_unknown_unit_fails_closed() -> None:
    with pytest.raises(UnitError):
        require_unit("furlong")


def test_advphys11_temperature_offset_round_trips() -> None:
    assert Quantity(68.0, "degF").to_unit("K").value == pytest.approx(293.15, abs=1e-9)
    assert to_si(0.25, "km/h") == pytest.approx(0.25 * 1000.0 / 3600.0)


def test_advphys11_quantity_dimension_mismatch_fails_closed() -> None:
    with pytest.raises(UnitError):
        Quantity(1.0, "N").to_unit("Pa")


# -- B. experiment definition -------------------------------------------------


def test_advphys11_wind_tunnel_plan_constructs() -> None:
    plan = _plan()
    assert plan.article.kind == "wind_tunnel"
    assert plan.channel("lift").sensor.sensor_id == "lc-1"
    assert plan.calibration("cal-lift").revision == 2


def test_advphys11_structural_plan_shares_generic_code() -> None:
    plan = _plan("structural_plan.json")
    assert plan.article.kind == "structural"
    assert len(plan.channels) == 3
    assert plan.sampling.trigger_channel == "load"


def test_advphys11_plan_digest_is_stable() -> None:
    assert _plan().digest() == _plan().digest()
    assert _plan("structural_plan.json").digest() != _plan().digest()


def test_advphys11_plan_rejects_unknown_channel() -> None:
    with pytest.raises(ExperimentError):
        _plan().channel("missing")


def test_advphys11_plan_rejects_channel_unknown_calibration() -> None:
    plan = _plan()
    with pytest.raises(ExperimentError):
        replace(plan, calibrations=plan.calibrations[:1])


def test_advphys11_channel_range_validation() -> None:
    channel = _plan().channel("lift")
    assert channel.contains(50.0) is True
    assert channel.contains(500.0) is False


def test_advphys11_condition_key_is_stable() -> None:
    condition = OperatingCondition(
        name="cruise",
        values=(("mach", Quantity(0.3, "1")), ("alpha", Quantity(2.0, "deg"))),
    )
    assert condition_key(condition) == condition_key(condition)
    assert len(condition_key(condition)) == 64


# -- C. sensor provenance -----------------------------------------------------


def test_advphys11_channel_provenance_records_measurement_chain() -> None:
    plan = _plan()
    provenance = channel_provenance(plan, "pressure")
    assert provenance.sensor_type == "pressure_transducer"
    assert provenance.calibration_id == "cal-pressure"
    assert provenance.calibration_revision == 3
    assert provenance.uncertainty == pytest.approx(50.0)
    assert provenance.location_m == (0.1, 0.0, 0.2)
    assert provenance.sample_rate_hz == pytest.approx(1000.0)
    assert provenance.filtering == ()


def test_advphys11_dataset_sensor_provenance_covers_every_channel() -> None:
    plan = _plan()
    resolved = dataset_sensor_provenance(plan)
    assert {item.channel for item in resolved} == {"lift", "drag", "pressure"}
    assert all(item.calibration_revision >= 1 for item in resolved)


# -- D. ingestion -------------------------------------------------------------


def test_advphys11_ingestion_normalizes_units_and_timebase() -> None:
    dataset = _dataset()
    assert dataset.channel("lift").unit == "N"
    assert dataset.channel("pressure").unit == "Pa"
    assert dataset.channel("pressure").values[0] == pytest.approx(101325.0)
    assert dataset.channel("lift").time_s[-1] == pytest.approx(0.004)
    assert dataset.origin is EvidenceKind.MEASUREMENT
    assert dataset.fidelity is EvidenceFidelity.MEASURED


def test_advphys11_ingestion_preserves_raw_bytes() -> None:
    dataset = _dataset()
    raw_text = _raw("wind_tunnel_raw.csv")
    assert dataset.raw.content == raw_text
    assert dataset.raw.digest == hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def test_advphys11_ingestion_records_provenance_and_evidence() -> None:
    dataset = _dataset()
    assert dataset.provenance.source is ResultSource.BENCHMARK
    assert all(channel.provenance.source is ResultSource.BENCHMARK for channel in dataset.channels)
    assert all(len(channel.inputs_hash) == 64 for channel in dataset.channels)


def test_advphys11_ingestion_rejects_non_monotonic_time() -> None:
    plan = _plan()
    raw = "time_ms,lift_N\n0.0,50.0\n1.0,51.0\n0.5,52.0\n"
    with pytest.raises(IngestionError):
        ingest_tabular(
            plan, raw, dataset_id="bad", columns={"lift": ("lift_N", "N")}, time_column="time_ms"
        )


def test_advphys11_ingestion_rejects_missing_column() -> None:
    plan = _plan()
    raw = "time_ms,lift_N\n0.0,50.0\n1.0,51.0\n"
    with pytest.raises(IngestionError):
        ingest_tabular(
            plan, raw, dataset_id="bad", columns={"drag": ("drag_N", "N")}, time_column="time_ms"
        )


def test_advphys11_ingestion_is_content_addressed() -> None:
    cache = MapArtifactCache()
    dataset = _dataset(cache=cache)
    assert dataset.artifact is not None
    stored = cache.get(dataset.artifact.key)
    assert stored["digest"] == dataset.raw.digest
    repeated = cache.put(
        {
            "mediaType": dataset.raw.media_type,
            "digest": dataset.raw.digest,
            "content": dataset.raw.content,
        }
    )
    assert repeated.key == dataset.artifact.key


def test_advphys11_ingestion_flags_out_of_range_values() -> None:
    plan = _plan()
    raw = "time_ms,lift_N\n0.0,200.0\n1.0,201.0\n"
    dataset = ingest_tabular(
        plan, raw, dataset_id="oor", columns={"lift": ("lift_N", "N")}, time_column="time_ms"
    )
    assert dataset.channel("lift").validity.passed is False
    assert dataset.validity.passed is False
    assert dataset.channels  # still ingested; out-of-range is a flag, not a fabrication


# -- E. synchronization and derived signals -----------------------------------


def test_advphys11_resample_is_deterministic_and_records_params() -> None:
    channel = _dataset().channel("lift")
    first = resample(channel, rate_hz=2000.0)
    second = resample(channel, rate_hz=2000.0)
    assert len(first.values) == 9
    assert first.digest() == second.digest()
    assert first.fidelity is EvidenceFidelity.DERIVED
    assert first.derived_from == (channel.digest(),)
    assert first.transform["rateHz"] == pytest.approx(2000.0)


def test_advphys11_resample_refuses_extrapolation() -> None:
    channel = _dataset().channel("lift")
    with pytest.raises(SynchronizationError):
        resample(channel, rate_hz=1000.0, start_s=-0.001)


def test_advphys11_trigger_alignment_finds_crossing() -> None:
    channel = _dataset().channel("lift")
    assert trigger_time(channel, level=50.5, direction="rising") == pytest.approx(0.0005)
    alignment = align_to_trigger(channel, level=50.5, direction="rising")
    assert alignment.trigger_time_s == pytest.approx(0.0005)
    assert alignment.channel.time_s[0] == pytest.approx(-0.0005)


def test_advphys11_filter_records_parameters() -> None:
    channel = _dataset().channel("lift")
    filtered = apply_filter(channel, FilterSpec(kind="moving_average", window=2))
    assert filtered.transform["spec"]["kind"] == "moving_average"
    assert "moving_average" in filtered.filtering
    assert filtered.fidelity is EvidenceFidelity.DERIVED
    lowpass = apply_filter(channel, FilterSpec(kind="lowpass", cutoff_hz=100.0))
    assert lowpass.transform["spec"]["cutoffHz"] == pytest.approx(100.0)


def test_advphys11_spectrum_finds_known_frequency() -> None:
    channel = _dataset().channel("pressure")
    spectrum_result = spectrum(channel)
    frequency, amplitude = spectrum_result.peak()
    assert frequency == pytest.approx(200.0)
    assert amplitude == pytest.approx(5.236, abs=0.01)
    assert len(spectrum_result.digest()) == 64


def test_advphys11_order_spectrum_reports_orders() -> None:
    spectrum_result = spectrum(_dataset().channel("pressure"))
    orders = order_spectrum(spectrum_result, reference_hz=100.0)
    assert orders.orders[1] == pytest.approx(2.0)
    assert orders.orders[2] == pytest.approx(4.0)


def test_advphys11_cycle_segmentation_is_reproducible() -> None:
    channel = _dataset().channel("lift")
    first = segment_cycles(channel, reference_hz=250.0, cycles_per_segment=1)
    second = segment_cycles(channel, reference_hz=250.0, cycles_per_segment=1)
    assert len(first) == 1
    assert [segment.canonical() for segment in first] == [
        segment.canonical() for segment in second
    ]


def test_advphys11_event_segmentation_and_failure() -> None:
    channel = _dataset().channel("pressure")
    segments = segment_events(channel, level=101330.0, direction="above")
    assert len(segments) == 1
    assert segments[0].peak == pytest.approx(101335.0)
    with pytest.raises(SynchronizationError):
        segment_events(channel, level=1e12, direction="above")


def test_advphys11_derived_signal_keeps_raw_immutable() -> None:
    dataset = _dataset()
    original = dataset.channel("lift").values
    resample(dataset.channel("lift"), rate_hz=2000.0)
    apply_filter(dataset.channel("lift"), FilterSpec(kind="moving_average", window=3))
    assert dataset.channel("lift").values == original


# -- F. simulation comparison -------------------------------------------------


def test_advphys11_match_requires_design_and_condition() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    envelope = _envelope("simulation_envelope.json", plan)
    assert match_dataset(dataset, [envelope]) == (envelope,)
    other = replace(envelope, design_revision="some-other-revision")
    assert match_dataset(dataset, [other]) == ()


def test_advphys11_require_match_fails_closed() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    foreign = replace(
        _envelope("simulation_envelope.json", plan),
        condition_key="0" * 64,
    )
    with pytest.raises(ComparisonError):
        require_match(dataset, [foreign])
    with pytest.raises(ComparisonError):
        require_match(dataset, [])


def test_advphys11_time_domain_residuals() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    envelope = _envelope("simulation_envelope.json", plan)
    report = compare_dataset(
        dataset,
        envelope,
        modes={"lift": "time", "drag": "time"},
        tolerances={"lift": 0.5, "drag": 0.2},
    )
    table = {item.channel: item for item in report.series}
    assert table["lift"].domain == "time"
    assert table["lift"].rmse == pytest.approx(0.1844, abs=1e-3)
    assert table["drag"].rmse == pytest.approx(0.05)
    assert report.passed() is True


def test_advphys11_frequency_domain_residuals() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    envelope = _envelope("simulation_envelope.json", plan)
    report = compare_dataset(
        dataset,
        envelope,
        modes={"pressure": "frequency"},
        tolerances={"pressure": 0.1},
    )
    assert report.series[0].domain == "frequency"
    assert report.series[0].passed is True


def test_advphys11_scalar_residuals() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    scalar_envelope = _envelope("simulation_envelope_scalar.json", plan)
    report = compare_dataset(
        dataset,
        scalar_envelope,
        modes={"lift": "scalar", "drag": "scalar"},
        tolerances={"lift": 0.2, "drag": 0.2},
    )
    table = {item.channel: item for item in report.scalars}
    assert table["lift"].absolute == pytest.approx(0.1)
    assert table["lift"].relative == pytest.approx(0.1 / 49.9)
    assert table["drag"].absolute == pytest.approx(-0.05)
    assert report.passed() is True
    assert scalar_residual("x", 2.0, 0.0).relative is None


def test_advphys11_comparison_report_is_reproducible_and_labelled() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    envelope = _envelope("simulation_envelope.json", plan)
    modes = {"lift": "time", "pressure": "frequency"}
    tolerances = {"lift": 0.5, "pressure": 0.1}
    first = compare_dataset(dataset, envelope, modes=modes, tolerances=tolerances)
    second = compare_dataset(dataset, envelope, modes=modes, tolerances=tolerances)
    assert first.digest() == second.digest()
    assert first.provenance.source is ResultSource.ANALYTICAL
    assert first.validity.passed is True


def test_advphys11_comparison_rejects_design_mismatch() -> None:
    plan = _plan()
    dataset = _dataset(plan)
    envelope = replace(_envelope("simulation_envelope.json", plan), design_revision="other")
    with pytest.raises(ComparisonError):
        compare_dataset(dataset, envelope, modes={"lift": "time"}, tolerances={"lift": 0.5})


# -- G. system identification -------------------------------------------------


class _LinearModel:
    def predict(self, inputs: Any, parameters: Any) -> float:
        return float(parameters[0]) * float(inputs["x"]) + float(parameters[1])


def _observations() -> tuple[Observation, ...]:
    payload = _fixture("observations.json")
    return tuple(
        Observation(inputs=dict(item["inputs"]), measured=float(item["measured"]))
        for item in payload["observations"]
    )


def _bounds() -> tuple[ParameterBound, ...]:
    return (
        ParameterBound(name="slope", unit="1", lower=0.0, upper=10.0),
        ParameterBound(name="intercept", unit="1", lower=-10.0, upper=10.0),
    )


def test_advphys11_identification_recovers_known_parameters() -> None:
    report = identify(_LinearModel(), _observations(), bounds=_bounds())
    assert report.parameter("slope").value == pytest.approx(2.5, abs=0.05)
    assert report.parameter("intercept").value == pytest.approx(1.0, abs=0.05)
    assert report.parameter("slope").uncertainty >= 0.0
    assert report.validation_rmse < 0.05
    assert report.provenance.source is ResultSource.SURROGATE


def test_advphys11_identification_keeps_splits_distinct() -> None:
    split = split_calibration_validation(_observations(), seed=0)
    assert len(split.calibration) == 4
    assert len(split.validation) == 2


def test_advphys11_identification_respects_bounds() -> None:
    bounds = (
        ParameterBound(name="slope", unit="1", lower=0.0, upper=2.0),
        ParameterBound(name="intercept", unit="1", lower=-10.0, upper=10.0),
    )
    report = identify(_LinearModel(), _observations(), bounds=bounds)
    assert report.parameter("slope").value <= 2.0


def test_advphys11_identification_needs_enough_observations() -> None:
    with pytest.raises(IdentificationError):
        estimate_parameters(_LinearModel(), _observations()[:2], bounds=_bounds())


def test_advphys11_identification_fails_validation_tolerance() -> None:
    report = identify(
        _LinearModel(),
        _observations(),
        bounds=_bounds(),
        max_validation_rmse=1e-9,
    )
    assert report.passed(max_validation_rmse=1e-9) is False
    assert report.validity.passed is False


# -- H. HIL and replay --------------------------------------------------------


class _EchoController:
    def __init__(self) -> None:
        self.commands: list[float] = []

    def reset(self) -> None:
        self.commands = []

    def update(self, frame: Frame) -> dict[str, float]:
        value = frame.values["y"]
        self.commands.append(value)
        return {"u": value * 2.0}


def _replay_stream() -> ReplayStream:
    payload = _fixture("replay_frames.json")
    return ReplayStream(
        recorded=tuple(
            Frame(
                time_s=float(item["time_s"]),
                values=dict(item["values"]),
                origin=EvidenceKind(item["origin"]),
            )
            for item in payload["frames"]
        )
    )


def test_advphys11_replay_is_deterministic_and_labelled() -> None:
    first = replay(_EchoController(), _replay_stream(), run_id="run-1")
    second = replay(_EchoController(), _replay_stream(), run_id="run-1")
    assert first.origin is EvidenceKind.REPLAY
    assert first.fidelity is EvidenceFidelity.REPLAY
    assert first.frame_count == 3
    assert first.frames[0].command["u"] == pytest.approx(2.0)
    assert first.digest() == second.digest()


def test_advphys11_hardware_fails_closed_without_backend() -> None:
    state = hil_capability("daq-board")
    assert state.available is False
    with pytest.raises(CapabilityUnavailable):
        require_hil_hardware("daq-board")
    with pytest.raises(CapabilityUnavailable):
        run_hardware(_EchoController(), _replay_stream(), run_id="run-2")


def test_advphys11_hardware_run_labelled_when_present() -> None:
    report = run_hardware(
        _EchoController(), _replay_stream(), run_id="run-3", hardware_present=True
    )
    assert report.origin is EvidenceKind.HARDWARE_IN_LOOP
    assert report.fidelity is EvidenceFidelity.HARDWARE
    assert report.frame_count == 3


# -- I. evidence status -------------------------------------------------------


def _measured_evidence(*, native: bool = False) -> Any:
    provenance = (
        native_solver_provenance(
            "solver", {}, solver_name="cfd", solver_version="1.0", run_id="run-1"
        )
        if native
        else measurement_provenance("sensor-chain", {"channel": "lift"})
    )
    return measurement_evidence(
        evidence_id="meas-1",
        unit="N",
        validity=Validity(passed=True),
        inputs_hash="a" * 64,
        provenance=provenance,
    )


def test_advphys11_measurement_evidence_is_benchmark_not_native() -> None:
    record = _measured_evidence()
    assert record.kind is EvidenceKind.MEASUREMENT
    assert record.source is ResultSource.BENCHMARK
    assert record.native is False


def test_advphys11_measurement_cannot_use_native_provenance() -> None:
    with pytest.raises(EvidenceError):
        _measured_evidence(native=True)


def test_advphys11_corroboration_never_relabels_source() -> None:
    base = simulation_evidence(
        evidence_id="sim-1",
        unit="N",
        validity=Validity(passed=True),
        inputs_hash="b" * 64,
        provenance=simulation_provenance("analytical-model", {"lift": 50.0}),
    )
    experiment = _measured_evidence()
    result = corroborate(base, experiment, agreement=0.01, tolerance=0.05)
    assert result.experimentally_supported is True
    assert result.relabelled_source is ResultSource.ANALYTICAL
    assert result.base.source is ResultSource.ANALYTICAL


def test_advphys11_promote_to_native_rejects_non_native() -> None:
    base = simulation_evidence(
        evidence_id="sim-2",
        unit="N",
        validity=Validity(passed=True),
        inputs_hash="c" * 64,
        provenance=simulation_provenance("analytical-model", {"lift": 50.0}),
    )
    with pytest.raises(EvidenceError):
        promote_to_native(base)
    with pytest.raises(EvidenceError):
        assert_no_relabel(base, ResultSource.NATIVE_SOLVER)


def test_advphys11_native_simulation_evidence_requires_identity() -> None:
    record = simulation_evidence(
        evidence_id="sim-native",
        unit="N",
        validity=Validity(passed=True),
        inputs_hash="d" * 64,
        provenance=native_solver_provenance(
            "cfd", {"lift": 50.0}, solver_name="openfoam", solver_version="2406", run_id="run-9"
        ),
    )
    assert record.native is True
    assert record.source is ResultSource.NATIVE_SOLVER
    assert record.provenance.run_id == "run-9"


# -- J. determinism -----------------------------------------------------------


def test_advphys11_derived_pipeline_is_deterministic() -> None:
    def pipeline() -> tuple[str, str, str]:
        channel = _dataset().channel("pressure")
        resampled = resample(channel, rate_hz=2000.0)
        filtered = apply_filter(resampled, FilterSpec(kind="lowpass", cutoff_hz=150.0))
        return channel.digest(), filtered.digest(), spectrum(filtered).digest()

    assert pipeline() == pipeline()
