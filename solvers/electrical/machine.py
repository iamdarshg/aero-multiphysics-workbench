"""Governed prepare/execute/parse/validate for the generic electrical machine.

The analytical and reduced levels execute a real in-process physics solve and
label their fidelity honestly. The native level is the declared Elmer seam and
fails closed when the engine (or its case execution) is unavailable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aeroworkbench_electrical import (
    ElectricalCapabilityUnavailable,
    ElectricalModelError,
    FidelityLevel,
    build_analytical_map,
    get_machine_parameters,
    native_em_status,
    solve_machine,
)
from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

DEFAULT_REVISION = "screening-r1"
DEFAULT_MAP_SPEEDS_RPM = (5000.0, 10000.0, 20000.0, 30000.0)
DEFAULT_MAP_TORQUES_N_M = (0.0, 0.25, 0.5, 0.75, 1.0)


def _require_float(inputs: Mapping[str, object], name: str) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"input {name} must be a number"
        )
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"input {name} must be finite"
        )
    return result


def _optional_float(inputs: Mapping[str, object], name: str) -> float | None:
    if name not in inputs:
        return None
    return _require_float(inputs, name)


def _revision(inputs: Mapping[str, object]) -> str:
    value = inputs.get("machine_parameter_revision", DEFAULT_REVISION)
    if not isinstance(value, str) or not value.strip():
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "machine_parameter_revision must be a string"
        )
    return value


def _fidelity(inputs: Mapping[str, object]) -> str:
    value = inputs.get("fidelity", FidelityLevel.ANALYTICAL.value)
    if not isinstance(value, str):
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "fidelity must be a string"
        )
    try:
        return FidelityLevel(value).value
    except ValueError as exc:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"unknown machine fidelity:{value}"
        ) from exc


def canonical_inputs(inputs: Mapping[str, object]) -> dict[str, Any]:
    """Validate the machine operating inputs and return a canonical mapping."""

    revision = _revision(inputs)
    get_machine_parameters(revision)  # raises ValueError on unknown revision
    fidelity = _fidelity(inputs)
    canonical: dict[str, Any] = {
        "machine_parameter_revision": revision,
        "fidelity": fidelity,
        "bus_voltage_v": _require_float(inputs, "bus_voltage_v"),
        "commanded_speed_rpm": _require_float(inputs, "commanded_speed_rpm"),
        "winding_temp_k": _require_float(inputs, "winding_temp_k"),
        "magnet_temp_k": _require_float(inputs, "magnet_temp_k"),
    }
    load = _optional_float(inputs, "load_torque_n_m")
    if load is not None:
        canonical["load_torque_n_m"] = load
    if fidelity == FidelityLevel.REDUCED.value and load is None:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED,
            "reduced machine fidelity requires load_torque_n_m",
        )
    return canonical


def prepare_machine_case(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Validate generic machine inputs and stage the governed case."""

    try:
        canonical = canonical_inputs(dict(inputs))
    except ValueError as exc:
        raise ParticipantError(NativeErrorCode.PREPARATION_FAILED, str(exc)) from exc
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PrepareReceipt(
        participant_id="rotating-electrical-machine",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail=(
            f"revision={canonical['machine_parameter_revision']} "
            f"fidelity={canonical['fidelity']}"
        ),
    )


def execute_machine_case(inputs: dict[str, object], case_dir: Path) -> None:
    """Execute the requested machine fidelity level and record result.json."""

    canonical = canonical_inputs(dict(inputs))
    parameters = get_machine_parameters(str(canonical["machine_parameter_revision"]))
    fidelity = str(canonical["fidelity"])
    machine_map = None
    load = canonical.get("load_torque_n_m")
    if fidelity == FidelityLevel.REDUCED.value:
        machine_map = build_analytical_map(
            parameters,
            speeds_rpm=DEFAULT_MAP_SPEEDS_RPM,
            torques_n_m=DEFAULT_MAP_TORQUES_N_M,
        )
    try:
        result = solve_machine(
            parameters,
            bus_voltage_v=float(canonical["bus_voltage_v"]),
            speed_rpm=float(canonical["commanded_speed_rpm"]),
            winding_temp_k=float(canonical["winding_temp_k"]),
            magnet_temp_k=float(canonical["magnet_temp_k"]),
            load_torque_n_m=float(load) if load is not None else None,
            fidelity=fidelity,
            machine_map=machine_map,
        )
    except ElectricalCapabilityUnavailable as exc:
        raise ParticipantError(NativeErrorCode.CAPABILITY_UNAVAILABLE, str(exc)) from exc
    except ElectricalModelError as exc:
        raise ParticipantError(NativeErrorCode.PREPARATION_FAILED, str(exc)) from exc

    status = native_em_status()
    payload: dict[str, Any] = {
        "participant_id": "rotating-electrical-machine",
        "library": "aeroworkbench_electrical",
        "revision": parameters.revision,
        "fidelity": result.fidelity,
        "source": result.source,
        "iterations": result.iterations,
        "detail": result.detail,
        "warnings": list(result.warnings),
        "native_em": {
            "state": status.state,
            "implementation": status.implementation,
            "detail": status.detail,
        },
        "validity": {
            "passed": result.validity.passed,
            "checks": result.validity.checks,
            "detail": result.validity.detail,
        },
        "scalars": result.as_scalars(),
        "units": result.units(),
    }
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _read_result(case_dir: Path) -> dict[str, Any]:
    target = case_dir / "result.json"
    if not target.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is missing")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    if not isinstance(data, dict) or data.get("library") != "aeroworkbench_electrical":
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result.json is not an electrical receipt"
        )
    return data


def parse_machine_result(case_dir: Path) -> ParseReceipt:
    data = _read_result(case_dir)
    try:
        scalars = {name: float(value) for name, value in dict(data["scalars"]).items()}
        units = {str(name): str(unit) for name, unit in dict(data["units"]).items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"machine result fields invalid:{exc}"
        ) from exc
    return ParseReceipt(
        participant_id="rotating-electrical-machine",
        parser="electrical.machine:parse_machine_result",
        scalars=scalars,
        units=units,
        detail=f"fidelity={data.get('fidelity')} source={data.get('source')}",
    )


def validate_machine_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    _ = inputs
    electrical = float(scalars.get("electrical_power_w", float("nan")))
    mechanical = float(scalars.get("mechanical_power_w", float("nan")))
    total_loss = float(scalars.get("total_loss_w", float("nan")))
    efficiency = float(scalars.get("efficiency", float("nan")))
    torque = float(scalars.get("torque_n_m", float("nan")))
    finite = all(
        value == value and value not in (float("inf"), float("-inf"))
        for value in (electrical, mechanical, total_loss, efficiency, torque)
    )
    balance = (
        abs(electrical - mechanical - total_loss)
        if finite
        else float("inf")
    )
    checks = {
        "finite_outputs": finite,
        "power_balance": finite
        and balance <= 1e-6 * max(1.0, abs(electrical), abs(mechanical)),
        "losses_nonnegative": finite and total_loss >= -1e-9,
        "efficiency_bounded": finite and 0.0 <= efficiency <= 1.0,
    }
    return ValidityReport(
        participant_id="rotating-electrical-machine",
        passed=all(checks.values()),
        checks=checks,
        detail="electrical = mechanical + copper + core + friction losses",
    )


__all__ = [
    "canonical_inputs",
    "execute_machine_case",
    "parse_machine_result",
    "prepare_machine_case",
    "validate_machine_result",
]
