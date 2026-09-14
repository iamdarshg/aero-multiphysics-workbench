"""Real PyBaMM cell/pack preparation, result parsing, and validation.

Supports SPM, SPMe, DFN, and Thevenin ECM models with named parameter-set
identity and arbitrary series/parallel topology. Prepare stages case.json
plus the governed run script; parse converts result.json into pack-level
scalars; validity enforces voltage bounds, coulomb consistency, and SOC range.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.commands import run_script_path
from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

MODELS = ("spm", "spme", "dfn", "thevenin")
PARAMETER_SETS = ("Chen2020", "Chen2020_composite", "Marquis2019", "ECM_Example")
PYBAMM_MIN_VERSION = "24.1"
RUN_SCRIPT = "run_pybamm.py"


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _require_float(inputs: Mapping[str, object], name: str) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"input {name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise _fail(f"input {name} must be finite")
    return result


def _require_int(inputs: Mapping[str, object], name: str) -> int:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"input {name} must be an integer")
    return int(value)


def _require_str(inputs: Mapping[str, object], name: str, allowed: tuple[str, ...]) -> str:
    value = inputs.get(name)
    if not isinstance(value, str) or value not in allowed:
        raise _fail(f"input {name} must be one of {sorted(allowed)}")
    return value


def prepare_cell_case(
    inputs: dict[str, object], case_dir: Path
) -> PrepareReceipt:
    """Validate a generic cell/pack discharge and stage the governed run."""

    data: Mapping[str, object] = dict(inputs)
    model = _require_str(data, "model", MODELS)
    parameter_set = _require_str(data, "parameter_set", PARAMETER_SETS)
    if model == "thevenin" and parameter_set != "ECM_Example":
        raise _fail("thevenin requires the ECM_Example parameter set")
    if model in {"spm", "spme", "dfn"} and parameter_set == "ECM_Example":
        raise _fail(f"{model} requires a lithium-ion parameter set")
    current = _require_float(data, "discharge_current_a")
    duration = _require_float(data, "duration_s")
    n_series = _require_int(data, "n_series")
    n_parallel = _require_int(data, "n_parallel")
    if current <= 0 or current > 100:
        raise _fail("discharge_current_a out of range")
    if duration <= 0 or duration > 3600:
        raise _fail("duration_s must be within (0, 3600]")
    if n_series < 1 or n_series > 400 or n_parallel < 1 or n_parallel > 400:
        raise _fail("pack topology out of range")

    canonical: dict[str, Any] = {
        "model": model,
        "parameter_set": parameter_set,
        "discharge_current_a": current,
        "duration_s": duration,
        "n_series": n_series,
        "n_parallel": n_parallel,
        "library": "pybamm",
        "min_version": PYBAMM_MIN_VERSION,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    shutil.copyfile(run_script_path(RUN_SCRIPT), case_dir / RUN_SCRIPT)
    return PrepareReceipt(
        participant_id="pybamm",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json", RUN_SCRIPT),
        detail=f"model={model} set={parameter_set} topology={n_series}s{n_parallel}p",
    )


def parse_cell_result(case_dir: Path) -> ParseReceipt:
    """Parse the PyBaMM run script's result.json into pack-level scalars."""

    target = case_dir / "result.json"
    if not target.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is missing")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    if not isinstance(data, dict) or data.get("library") != "pybamm":
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is not a PyBaMM receipt")
    try:
        scalars = {
            "voltage_start_v": float(data["pack_voltage_start_v"]),
            "voltage_end_v": float(data["pack_voltage_end_v"]),
            "delivered_ah": float(data["pack_delivered_ah"]),
            "soc_end": float(data["pack_soc_end"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"PyBaMM result fields invalid:{exc}"
        ) from exc
    units = {
        "voltage_start_v": "V",
        "voltage_end_v": "V",
        "delivered_ah": "A.h",
        "soc_end": "dimensionless",
    }
    return ParseReceipt(
        participant_id="pybamm",
        parser="pybamm.cell:parse_cell_result",
        scalars=scalars,
        units=units,
        detail=f"model={data.get('model', 'unknown')} set={data.get('parameter_set', 'unknown')}",
    )


def validate_cell_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    start = float(scalars.get("voltage_start_v", float("nan")))
    end = float(scalars.get("voltage_end_v", float("nan")))
    delivered = float(scalars.get("delivered_ah", float("nan")))
    soc = float(scalars.get("soc_end", float("nan")))
    current = float(inputs.get("discharge_current_a", float("nan")))
    duration = float(inputs.get("duration_s", float("nan")))
    n_parallel = int(inputs.get("n_parallel", 1))
    n_series = int(inputs.get("n_series", 1))
    applied_ah = current * duration / 3600.0 * n_parallel if current == current else float("nan")
    cell_start = start / n_series if n_series else float("nan")
    cell_end = end / n_series if n_series else float("nan")
    checks = {
        "cell_voltage_bounds": (
            cell_start == cell_start
            and cell_end == cell_end
            and 2.0 <= cell_end <= cell_start <= 5.0
        ),
        "discharge_direction": end <= start,
        "coulomb_consistent": (
            delivered == delivered
            and applied_ah == applied_ah
            and abs(delivered - applied_ah) / max(applied_ah, 1e-12) < 0.05
        ),
        "soc_range": soc == soc and 0.0 <= soc <= 1.0,
    }
    return ValidityReport(
        participant_id="pybamm",
        passed=all(checks.values()),
        checks=checks,
        detail="per-cell voltage within [2,5] V, coulomb count within 5%, soc in [0,1]",
    )
