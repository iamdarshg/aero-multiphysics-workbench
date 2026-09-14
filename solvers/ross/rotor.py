"""Real ROSS rotor preparation, result parsing, and validation.

Prepare writes an auditable case.json plus a hashed copy of the governed run
script; the run script builds actual shaft/bearing/disk models with the ROSS
library in a subprocess. Parse converts result.json into typed scalars and
validity cross-checks the first critical speed against a simply-supported
Euler-Bernoulli beam estimate.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.commands import run_script_path
from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

ANALYSES = ("campbell", "modal", "forced")
ROSS_MIN_VERSION = "2.0.0"
RUN_SCRIPT = "run_ross.py"


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


def prepare_rotor_case(
    inputs: dict[str, object], case_dir: Path
) -> PrepareReceipt:
    """Validate a generic rotor description and stage the governed run."""

    data: Mapping[str, object] = dict(inputs)
    analysis = _require_str(data, "analysis", ANALYSES)
    shaft_length = _require_float(data, "shaft_length_m")
    shaft_diameter = _require_float(data, "shaft_diameter_m")
    n_elements = _require_int(data, "n_elements")
    bearing_stiffness = _require_float(data, "bearing_stiffness_n_m")
    if "bearing_damping_n_s_m" in data:
        bearing_damping = _require_float(data, "bearing_damping_n_s_m")
    else:
        bearing_damping = 1000.0
    if shaft_length <= 0 or shaft_diameter <= 0:
        raise _fail("shaft dimensions must be positive")
    if n_elements < 2 or n_elements > 64:
        raise _fail("n_elements must be within 2..64")
    if bearing_stiffness <= 0 or bearing_damping < 0:
        raise _fail("bearing coefficients out of physical range")
    disk_raw = data.get("disk", None)
    disk: dict[str, float] | None = None
    if disk_raw is not None:
        if not isinstance(disk_raw, Mapping):
            raise _fail("disk must be a mapping")
        disk = {
            "position": _require_float(disk_raw, "position"),
            "outer_diameter_m": _require_float(disk_raw, "outer_diameter_m"),
            "width_m": _require_float(disk_raw, "width_m"),
        }
        if (
            disk["outer_diameter_m"] <= shaft_diameter
            or disk["width_m"] <= 0
            or not 0 <= disk["position"] <= n_elements
        ):
            raise _fail("disk geometry out of range")
    if analysis == "campbell":
        max_speed = _require_float(data, "max_speed_rpm")
        if max_speed <= 0 or max_speed > 200_000:
            raise _fail("max_speed_rpm out of range")
        speed_rpm = 0.0
    else:
        speed_rpm = _require_float(data, "speed_rpm")
        if speed_rpm < 0 or speed_rpm > 200_000:
            raise _fail("speed_rpm out of range")
        max_speed = speed_rpm

    canonical: dict[str, Any] = {
        "analysis": analysis,
        "shaft_length_m": shaft_length,
        "shaft_diameter_m": shaft_diameter,
        "n_elements": n_elements,
        "bearing_stiffness_n_m": bearing_stiffness,
        "bearing_damping_n_s_m": bearing_damping,
        "disk": disk,
        "max_speed_rpm": max_speed,
        "speed_rpm": speed_rpm,
        "library": "ross-rotordynamics",
        "min_version": ROSS_MIN_VERSION,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    script_source = run_script_path(RUN_SCRIPT)
    shutil.copyfile(script_source, case_dir / RUN_SCRIPT)
    return PrepareReceipt(
        participant_id="ross",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json", RUN_SCRIPT),
        detail=f"analysis={analysis} elements={n_elements}",
    )


def parse_rotor_result(case_dir: Path) -> ParseReceipt:
    """Parse the ROSS run script's result.json into typed scalars."""

    target = case_dir / "result.json"
    if not target.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is missing")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    if not isinstance(data, dict) or data.get("library") != "ross-rotordynamics":
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is not a ROSS receipt")
    analysis = data.get("analysis")
    try:
        if analysis == "campbell":
            criticals = [float(value) for value in data["critical_speeds_rpm"]]
            if len(criticals) < 2:
                raise ParticipantError(
                    NativeErrorCode.PARSER_FAILED, "campbell result needs two criticals"
                )
            scalars = {
                "first_critical_rpm": criticals[0],
                "second_critical_rpm": criticals[1],
            }
            units = {"first_critical_rpm": "rpm", "second_critical_rpm": "rpm"}
        elif analysis == "modal":
            scalars = {
                "first_whirl_hz": float(data["first_whirl_hz"]),
                "first_damping_ratio": float(data["first_damping_ratio"]),
            }
            units = {"first_whirl_hz": "Hz", "first_damping_ratio": "dimensionless"}
        elif analysis == "forced":
            scalars = {
                "peak_response_m": float(data["peak_response_m"]),
                "peak_speed_rpm": float(data["peak_speed_rpm"]),
            }
            units = {"peak_response_m": "m", "peak_speed_rpm": "rpm"}
        else:
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, f"unknown ROSS analysis:{analysis}"
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"ROSS result fields invalid:{exc}"
        ) from exc
    return ParseReceipt(
        participant_id="ross",
        parser="ross.rotor:parse_rotor_result",
        scalars=scalars,
        units=units,
        detail=f"solver={data.get('solver_version', 'unknown')}",
    )


def beam_first_critical_rpm(
    *, shaft_length_m: float, shaft_diameter_m: float, youngs_pa: float = 211e9,
    density_kg_m3: float = 7810.0,
) -> float:
    """Simply-supported Euler-Bernoulli first-critical estimate (screening only)."""

    area = math.pi * shaft_diameter_m**2 / 4.0
    inertia = math.pi * shaft_diameter_m**4 / 64.0
    stiffness = youngs_pa * inertia / (density_kg_m3 * area)
    omega = (math.pi**2) * math.sqrt(stiffness) / shaft_length_m**2
    return omega * 60.0 / (2.0 * math.pi)


def validate_rotor_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    if "first_critical_rpm" in scalars:
        first = float(scalars["first_critical_rpm"])
        second = float(scalars["second_critical_rpm"])
        estimate = beam_first_critical_rpm(
            shaft_length_m=float(inputs["shaft_length_m"]),
            shaft_diameter_m=float(inputs["shaft_diameter_m"]),
        )
        checks = {
            "criticals_positive": first > 0 and second > 0,
            "criticals_ascending": second > first,
            "beam_consistent": first > 0 and abs(first - estimate) / estimate < 0.5,
        }
        detail = f"beam estimate {estimate:.1f} rpm within 50%"
    elif "first_whirl_hz" in scalars:
        whirl = float(scalars["first_whirl_hz"])
        damping = float(scalars["first_damping_ratio"])
        checks = {
            "whirl_positive": whirl > 0,
            "damping_finite": damping == damping and abs(damping) < 1.0,
        }
        detail = "forward whirl positive with bounded damping ratio"
    else:
        peak = float(scalars.get("peak_response_m", float("nan")))
        checks = {"response_finite": peak == peak and peak >= 0}
        detail = "forced peak response finite and non-negative"
    return ValidityReport(
        participant_id="ross",
        passed=all(checks.values()),
        checks=checks,
        detail=detail,
    )
