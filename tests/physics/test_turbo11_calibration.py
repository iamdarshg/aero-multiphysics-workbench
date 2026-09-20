"""TURBO 11: calibration, uncertainty, benchmarks, and end-to-end design proof."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from aeroworkbench_core.types import ResultSource
from aeroworkbench_turbomachinery.calibration import (
    CASE_AXIAL_FAN,
    CASE_AXIAL_SHAFT,
    CASE_BRAYTON_CORE,
    CASE_RADIAL,
    REFERENCE_CASES,
    AffineResponseModel,
    BenchmarkExpectation,
    BiasModel,
    CalibrationCapabilityUnavailable,
    CalibrationDataset,
    CalibrationDatum,
    CalibrationInputError,
    DatumKind,
    NativeCalibrationRequest,
    ambient_condition_input,
    benchmark_matrix_digest,
    build_plan,
    build_spec,
    calibrate_model,
    check_reference_case,
    datum_from_mapping,
    estimate_only,
    fidelity_escalation_decision,
    geometry_tolerance_input,
    map_correlation_input,
    material_scatter_input,
    native_calibration_status,
    propagate_predictions,
    request_native_calibration,
    robust_constraint_margin,
    run_design_proof,
    run_reference_case,
    screening_label,
)
from aeroworkbench_turbomachinery.fidelity.native import (
    CapabilityStatus,
    NativeCapabilityGate,
    NativeCapabilityState,
    NativeReceipt,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "turbo" / "calibration"


def _load_dataset(name: str) -> CalibrationDataset:
    payload = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    return CalibrationDataset(
        dataset_id=str(payload["datasetId"]),
        data=tuple(datum_from_mapping(item) for item in payload["data"]),
        source="synthetic-test-rig",
    )


def _evaluate_linear(sample: Mapping[str, float]) -> Mapping[str, float]:
    return {"y": 2.0 * float(sample["x"]) + 1.0}


def test_turbo11_data_contract_ingest_and_split() -> None:
    dataset = _load_dataset("fan_efficiency_rig.json")
    assert len(dataset.data) == 6
    assert dataset.unit == "1"
    assert dataset.dataset_hash == _load_dataset("fan_efficiency_rig.json").dataset_hash
    receipt = dataset.ingest_receipt()
    assert receipt.count == 6
    assert receipt.result_hash == dataset.ingest_receipt().result_hash
    assert receipt.provenance is not None
    calibration, validation = dataset.split()
    assert len(calibration) == 4 and len(validation) == 2
    assert {d.datum_id for d in calibration}.isdisjoint({d.datum_id for d in validation})
    assert len(calibration) + len(validation) == 6
    before = dataset.canonical()
    _ = calibrate_model(
        BiasModel(0.90), dataset, ("efficiency_bias",), {"efficiency_bias": (-0.05, 0.05)}
    )
    assert dataset.canonical() == before


def test_turbo11_data_contract_fails_closed() -> None:
    with pytest.raises(CalibrationInputError):
        datum_from_mapping({"kind": "no-such-kind"})
    with pytest.raises(CalibrationInputError):
        CalibrationDatum(
            datum_id=" ",
            kind=DatumKind.RIG_MEASUREMENT,
            quantity="q",
            measured=1.0,
            uncertainty=0.1,
            unit="1",
            source="s",
            revision="1",
        )
    with pytest.raises(CalibrationInputError):
        CalibrationDatum(
            datum_id="x",
            kind=DatumKind.RIG_MEASUREMENT,
            quantity="q",
            measured=1.0,
            uncertainty=0.0,
            unit="1",
            source="s",
            revision="1",
        )
    good = CalibrationDatum(
        datum_id="a",
        kind=DatumKind.RIG_MEASUREMENT,
        quantity="q",
        measured=1.0,
        uncertainty=0.1,
        unit="1",
        source="s",
        revision="1",
    )
    other_unit = CalibrationDatum(
        datum_id="b",
        kind=DatumKind.RIG_MEASUREMENT,
        quantity="q",
        measured=1.0,
        uncertainty=0.1,
        unit="Pa",
        source="s",
        revision="1",
    )
    with pytest.raises(CalibrationInputError):
        CalibrationDataset(dataset_id="d", data=(good, other_unit))
    with pytest.raises(CalibrationInputError):
        CalibrationDataset(dataset_id="d", data=(good, good))
    with pytest.raises(CalibrationInputError):
        CalibrationDataset(dataset_id="d", data=())
    dataset = CalibrationDataset(dataset_id="d", data=(good,))
    with pytest.raises(CalibrationInputError):
        dataset.split(calibration_fraction=1.5)


def test_turbo11_calibration_fits_with_residuals() -> None:
    dataset = _load_dataset("fan_efficiency_rig.json")
    receipt = calibrate_model(
        BiasModel(0.90),
        dataset,
        ("efficiency_bias",),
        {"efficiency_bias": (-0.05, 0.05)},
        max_validation_rmse=0.01,
    )
    assert receipt.converged
    assert receipt.validity.passed
    assert receipt.fidelity == "calibrated-screening"
    assert receipt.source == ResultSource.SURROGATE.value
    assert len(receipt.residuals) == 6
    assert len(receipt.input_hash) == 64
    assert receipt.result_hash == calibrate_model(
        BiasModel(0.90),
        dataset,
        ("efficiency_bias",),
        {"efficiency_bias": (-0.05, 0.05)},
        max_validation_rmse=0.01,
    ).result_hash
    name, value, uncertainty, unit = receipt.parameters[0]
    assert name == "efficiency_bias" and unit == "1"
    assert -0.05 <= value <= 0.05 and uncertainty >= 0.0

    manufacturer = _load_dataset("fan_manufacturer_curve.json")
    affine = calibrate_model(
        AffineResponseModel("pressure_ratio"),
        manufacturer,
        ("gain", "offset"),
        {"gain": (-2.0, 0.0), "offset": (0.5, 1.5)},
    )
    assert affine.converged
    assert affine.parameters[0][0] == "gain"
    assert affine.parameters[0][1] < 0.0

    estimates = estimate_only(
        BiasModel(0.90),
        dataset.data[:4],
        ("efficiency_bias",),
        {"efficiency_bias": (-0.05, 0.05)},
        "1",
    )
    assert len(estimates) == 1


def test_turbo11_calibration_fails_closed() -> None:
    dataset = _load_dataset("fan_efficiency_rig.json")
    with pytest.raises(CalibrationInputError):
        calibrate_model(
            BiasModel(0.90), dataset, ("efficiency_bias",), {"other": (-1.0, 1.0)}
        )
    with pytest.raises(CalibrationInputError):
        calibrate_model(
            AffineResponseModel("missing_channel"),
            dataset,
            ("gain", "offset"),
            {"gain": (-1.0, 1.0), "offset": (-1.0, 1.0)},
        )
    with pytest.raises(CalibrationInputError):
        estimate_only(BiasModel(0.90), (), ("efficiency_bias",), {}, "1")
    with pytest.raises(CalibrationInputError):
        BiasModel(float("nan"))
    with pytest.raises(CalibrationInputError):
        AffineResponseModel(" ")


def test_turbo11_uncertainty_propagation_and_margins() -> None:
    spec = build_spec(
        "t11-test",
        (
            geometry_tolerance_input("gap", "mm", 0.5, 0.1),
            ambient_condition_input("p0", "Pa", 101325.0, 1500.0),
            map_correlation_input("eff", "1", 0.9, 0.005),
            material_scatter_input("rho", "kg/m3", 2700.0, 0.02),
        ),
    )
    plan = build_plan("t11-plan", 16, seed=3)
    result = propagate_predictions(
        build_spec("t11-linear", (geometry_tolerance_input("x", "m", 1.0, 0.2),)),
        plan,
        _evaluate_linear,
        ("y",),
    )
    assert result.count == 16
    moments = result.moment_for("y")
    assert moments.mean == pytest.approx(3.0, abs=0.2)
    assert moments.std > 0.0
    passing = robust_constraint_margin("y", "1", 10.0, result)
    assert passing.robust_pass and passing.margin > 0.0
    failing = robust_constraint_margin("y", "1", 1.0, result)
    assert not failing.robust_pass
    lower = robust_constraint_margin("y", "1", 1.0, result, upper_bound=False)
    assert lower.robust_pass
    calm = fidelity_escalation_decision(result, relative_std_threshold=0.5)
    assert not calm.escalate
    strict = fidelity_escalation_decision(result, relative_std_threshold=1e-9)
    assert strict.escalate
    with pytest.raises(CalibrationInputError):
        robust_constraint_margin("nope", "1", 1.0, result)
    with pytest.raises(CalibrationInputError):
        build_plan("too-many", 10**9)
    with pytest.raises(CalibrationInputError):
        build_spec("empty", ())
    with pytest.raises(CalibrationInputError):
        build_spec("dup", (geometry_tolerance_input("x", "m", 1.0, 0.1),) * 2)
    with pytest.raises(CalibrationInputError):
        propagate_predictions(spec, plan, _evaluate_linear, ())


def test_turbo11_benchmark_matrix_covers_four_families() -> None:
    assert set(REFERENCE_CASES) == {
        CASE_AXIAL_FAN,
        CASE_AXIAL_SHAFT,
        CASE_RADIAL,
        CASE_BRAYTON_CORE,
    }
    outcomes = {case_id: run_reference_case(case_id) for case_id in REFERENCE_CASES}
    for outcome in outcomes.values():
        assert outcome.converged
        assert outcome.validity.passed
        assert outcome.source == ResultSource.ANALYTICAL.value
        assert len(outcome.input_hash) == 64
    assert benchmark_matrix_digest(outcomes) == benchmark_matrix_digest(outcomes)
    with pytest.raises(CalibrationInputError):
        run_reference_case("no-such-case")


def test_turbo11_benchmark_expectations_regression() -> None:
    expectations = (
        BenchmarkExpectation(
            CASE_AXIAL_FAN,
            "60619b62b4faf89e343ec127e3991ad12ebde28b46eb22ab421415b1be0c263e",
            True,
            542.3701802214222,
            1.0,
            0.0,
            1e-9,
        ),
        BenchmarkExpectation(
            CASE_AXIAL_SHAFT,
            "e6f426a10c7fdde7b889e38dfca5f3333091e6cd034ff02b0b1e10c69247bb52",
            True,
            0.0,
            1e-9,
            0.15173596777623008,
            1e-6,
        ),
        BenchmarkExpectation(
            CASE_RADIAL,
            "30c3c22e2be4e16f0a40051df30f57e9286a3cecd7c0ba0d595a92e588a83ef8",
            True,
            0.0,
            1e-9,
            0.0,
            1e-9,
        ),
        BenchmarkExpectation(
            CASE_BRAYTON_CORE,
            "da5e5bd1972cfdfd1ac2e201593646f486160b2a69c34bf28e792eb8a1e14a7e",
            True,
            7562.251441907527,
            5.0,
            0.303297879420309,
            1e-6,
        ),
    )
    for expectation in expectations:
        check = check_reference_case(run_reference_case(expectation.case_id), expectation)
        assert check.passed, check.failures
    broken = BenchmarkExpectation(
        CASE_AXIAL_FAN,
        "60619b62b4faf89e343ec127e3991ad12ebde28b46eb22ab421415b1be0c263e",
        True,
        -542.3701802214222,
        1.0,
        0.0,
        1e-9,
    )
    assert not check_reference_case(run_reference_case(CASE_AXIAL_FAN), broken).passed
    with pytest.raises(CalibrationInputError):
        check_reference_case(
            run_reference_case(CASE_AXIAL_FAN),
            BenchmarkExpectation(CASE_RADIAL, "0" * 64, True, 0.0, 1.0, None, None),
        )


def test_turbo11_end_to_end_design_proof() -> None:
    proof = run_design_proof()
    assert proof.validity.passed, proof.validity.checks
    assert proof.cycle_converged
    assert proof.multipoint_passed
    assert proof.multipoint_ids == ("cruise", "idle", "takeoff")
    assert proof.triangle_work_j_kg == pytest.approx(8250.0, rel=1e-12)
    assert proof.cycle_thrust_n == pytest.approx(542.3701802214222, rel=1e-9)
    assert proof.thrust_std_n > 0.0
    assert proof.robust_pass
    assert not proof.escalation
    assert proof.fidelity == "calibrated-screening"
    assert "unavailable" in proof.native_status
    assert proof.result_hash == run_design_proof().result_hash
    assert proof.result_hash == "8d159c9518094c37a8d0f2da250173f83e8ca30621e6eebfc7b3f9e927e2a583"
    assert proof.calibration.validity.passed
    with pytest.raises(CalibrationInputError):
        run_design_proof("no-such-case")


def test_turbo11_native_paths_fail_closed() -> None:
    status = native_calibration_status()
    assert not status.available
    gate = NativeCapabilityGate(
        {
            "turbomachinery-calibration-native": CapabilityStatus(
                "turbomachinery-calibration-native", NativeCapabilityState.READY, "9.9"
            )
        }
    )
    assert native_calibration_status(gate).available
    with pytest.raises(CalibrationCapabilityUnavailable):
        request_native_calibration(
            NativeCalibrationRequest(dataset_id="d", dataset_hash="0" * 64)
        )
    trusted = NativeReceipt(
        capability="turbomachinery-calibration-native",
        solver_name="native-calibration",
        solver_version="9.9",
        run_id="run-1",
        inputs_hash="0" * 64,
        trusted=True,
    )
    with pytest.raises(CalibrationCapabilityUnavailable):
        request_native_calibration(
            NativeCalibrationRequest(
                dataset_id="d", dataset_hash="0" * 64, receipt=trusted
            ),
            gate,
        )


def test_turbo11_screening_labels_never_claim_validation() -> None:
    assert screening_label(calibrated=False) == "analytical-screening"
    assert screening_label(calibrated=True) == "calibrated-screening"
    assert "validat" not in screening_label(calibrated=False).lower()
    assert "native" not in screening_label(calibrated=True).lower()


def test_turbo11_result_envelope_complete() -> None:
    proof = run_design_proof()
    envelope: dict[str, Any] = proof.canonical()
    assert envelope["source"] == ResultSource.ANALYTICAL.value
    assert dict(proof.units)["cycleThrustN"] == "N"
    assert len(proof.input_hash) == 64
    assert proof.software.name == "aeroworkbench-turbomachinery-calibration"
    assert proof.provenance.inputs_hash == proof.input_hash
