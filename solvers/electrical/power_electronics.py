"""Governed prepare/execute/parse/validate for the generic inverter/ESC."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aeroworkbench_electrical import (
    FidelityLevel,
    InverterModelError,
    get_drive_parameters,
    solve_inverter,
)
from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

DEFAULT_REVISION = "screening-r1"


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


def canonical_inputs(inputs: Mapping[str, object]) -> dict[str, Any]:
    """Validate the inverter operating inputs and return a canonical mapping."""

    revision = inputs.get("device_parameter_revision", DEFAULT_REVISION)
    if not isinstance(revision, str) or not revision.strip():
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED,
            "device_parameter_revision must be a string",
        )
    get_drive_parameters(revision)  # raises ValueError on unknown revision
    fidelity_value = inputs.get("fidelity", FidelityLevel.ANALYTICAL.value)
    if not isinstance(fidelity_value, str):
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "fidelity must be a string"
        )
    try:
        fidelity = FidelityLevel(fidelity_value).value
    except ValueError as exc:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"unknown drive fidelity:{fidelity_value}"
        ) from exc
    return {
        "device_parameter_revision": revision,
        "fidelity": fidelity,
        "dc_bus_voltage_v": _require_float(inputs, "dc_bus_voltage_v"),
        "output_power_w": _require_float(inputs, "output_power_w"),
        "switching_frequency_hz": _require_float(inputs, "switching_frequency_hz"),
        "modulation_index": _require_float(inputs, "modulation_index"),
        "case_temp_k": _require_float(inputs, "case_temp_k"),
    }


def prepare_inverter_case(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Validate generic inverter inputs and stage the governed case."""

    canonical = canonical_inputs(dict(inputs))
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PrepareReceipt(
        participant_id="power-electronics-drive",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail=(
            f"revision={canonical['device_parameter_revision']} "
            f"fidelity={canonical['fidelity']}"
        ),
    )


def execute_inverter_case(inputs: dict[str, object], case_dir: Path) -> None:
    """Execute the generic inverter loss/thermal solve and record result.json."""

    canonical = canonical_inputs(dict(inputs))
    parameters = get_drive_parameters(str(canonical["device_parameter_revision"]))
    try:
        result = solve_inverter(
            parameters,
            dc_bus_voltage_v=float(canonical["dc_bus_voltage_v"]),
            output_power_w=float(canonical["output_power_w"]),
            switching_frequency_hz=float(canonical["switching_frequency_hz"]),
            modulation_index=float(canonical["modulation_index"]),
            case_temp_k=float(canonical["case_temp_k"]),
            fidelity=str(canonical["fidelity"]),
        )
    except InverterModelError as exc:
        raise ParticipantError(NativeErrorCode.PREPARATION_FAILED, str(exc)) from exc
    payload: dict[str, Any] = {
        "participant_id": "power-electronics-drive",
        "library": "aeroworkbench_electrical",
        "revision": parameters.revision,
        "fidelity": result.fidelity,
        "source": result.source,
        "iterations": result.iterations,
        "detail": result.detail,
        "warnings": list(result.warnings),
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


def parse_inverter_result(case_dir: Path) -> ParseReceipt:
    data = _read_result(case_dir)
    try:
        scalars = {name: float(value) for name, value in dict(data["scalars"]).items()}
        units = {str(name): str(unit) for name, unit in dict(data["units"]).items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"inverter result fields invalid:{exc}"
        ) from exc
    return ParseReceipt(
        participant_id="power-electronics-drive",
        parser="electrical.power_electronics:parse_inverter_result",
        scalars=scalars,
        units=units,
        detail=f"fidelity={data.get('fidelity')} source={data.get('source')}",
    )


def validate_inverter_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    _ = inputs
    output_power = float(scalars.get("dc_power_w", float("nan")))
    dc_current = float(scalars.get("dc_current_a", float("nan")))
    conduction = float(scalars.get("conduction_loss_w", float("nan")))
    switching = float(scalars.get("switching_loss_w", float("nan")))
    total_loss = float(scalars.get("total_loss_w", float("nan")))
    efficiency = float(scalars.get("efficiency", float("nan")))
    finite = all(
        value == value and value not in (float("inf"), float("-inf"))
        for value in (output_power, dc_current, conduction, switching, total_loss, efficiency)
    )
    checks = {
        "finite_outputs": finite,
        "losses_nonnegative": finite and conduction >= -1e-9 and switching >= -1e-9,
        "loss_sum_consistent": finite
        and abs(total_loss - conduction - switching) <= 1e-9 * max(1.0, total_loss),
        "efficiency_bounded": finite and 0.0 <= efficiency <= 1.0,
        "dc_current_finite": finite and dc_current >= -1e-9,
    }
    return ValidityReport(
        participant_id="power-electronics-drive",
        passed=all(checks.values()),
        checks=checks,
        detail="dc power = output power + conduction loss + switching loss",
    )


__all__ = [
    "canonical_inputs",
    "execute_inverter_case",
    "parse_inverter_result",
    "prepare_inverter_case",
    "validate_inverter_result",
]
