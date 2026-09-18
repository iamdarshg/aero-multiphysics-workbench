"""Real ROSS rotor preparation, result parsing, and validity policy.

Prepare normalizes a generic rotating-assembly description (shaft segments,
material, disks, bearings, speed range, gyroscopic settings, unbalance) plus
any participant-declared forcing spectra, then writes an auditable ``case.json``
and a hashed copy of the governed run script. The run script builds actual ROSS
shaft/disk/bearing elements in a subprocess. Parse converts ``result.json`` into
typed scalars; validity treats a simply-supported Euler-Bernoulli beam estimate
as a wide screening plausibility band only -- native bearing/gyroscopic modes
are authoritative at native fidelity.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aeroworkbench_dynamics import (
    ForcingSpecError,
    RotorModelError,
    normalize_forcing_lines,
    normalize_rotor_model,
)
from participants.commands import run_script_path
from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

ANALYSES = ("campbell", "modal", "forced")
ROSS_MIN_VERSION = "2.0.0"
RUN_SCRIPT = "run_ross.py"
DEFAULT_WARNING_MARGIN_HZ = 5.0
DEFAULT_CRITICAL_MARGIN_HZ = 2.0
# A simply-supported beam estimate is a screening plausibility band only. The
# band is deliberately wide (an order-and-a-half of magnitude either way) so
# bearing-dominated and gyroscopic modes are never rejected merely for differing
# from a flexible-beam estimate; outside it the comparison indicates an invalid
# model/result rather than a fidelity difference.
SCREENING_PLAUSIBILITY_FACTOR = 50.0


def _finite_optional(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return result


def prepare_rotor_case(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Validate a generic rotating assembly and stage the governed run."""

    try:
        model = normalize_rotor_model(inputs)
        forcing_lines = normalize_forcing_lines(inputs.get("forcings"))
    except (RotorModelError, ForcingSpecError) as exc:
        raise ParticipantError(NativeErrorCode.PREPARATION_FAILED, str(exc)) from exc

    warning = _finite_optional(inputs.get("forcing_warning_margin_hz"))
    critical = _finite_optional(inputs.get("forcing_critical_margin_hz"))
    warning = DEFAULT_WARNING_MARGIN_HZ if warning is None else warning
    critical = DEFAULT_CRITICAL_MARGIN_HZ if critical is None else critical
    if warning <= 0 or critical <= 0 or critical > warning:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED,
            "forcing margins must be positive with critical <= warning",
        )

    canonical: dict[str, Any] = {
        "analysis": model.analysis,
        "model": model.canonical_payload(),
        "speed_rpm": model.speed_rpm,
        "max_speed_rpm": model.max_speed_rpm,
        "forcings": [line.canonical_payload() for line in forcing_lines],
        "forcing_warning_margin_hz": warning,
        "forcing_critical_margin_hz": critical,
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
        detail=(
            f"analysis={model.analysis} segments={len(model.segments)} "
            f"disks={len(model.disks)} bearings={len(model.bearings)} "
            f"forcings={len(forcing_lines)}"
        ),
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
    scalars: dict[str, float] = {}
    units: dict[str, str] = {}
    try:
        if analysis == "campbell":
            criticals = [float(value) for value in data["critical_speeds_rpm"]]
            if not criticals:
                raise ParticipantError(
                    NativeErrorCode.PARSER_FAILED, "campbell result has no critical speeds"
                )
            scalars["first_critical_rpm"] = criticals[0]
            units["first_critical_rpm"] = "rpm"
            # A short bearing-dominated rotor can show only one forward critical
            # below the swept speed; report a second only when it is detected.
            if len(criticals) >= 2:
                scalars["second_critical_rpm"] = criticals[1]
                units["second_critical_rpm"] = "rpm"
        elif analysis == "modal":
            scalars["first_whirl_hz"] = float(data["first_whirl_hz"])
            scalars["first_damping_ratio"] = float(data["first_damping_ratio"])
            units["first_whirl_hz"] = "Hz"
            units["first_damping_ratio"] = "dimensionless"
        elif analysis == "forced":
            scalars["peak_response_m"] = float(data["peak_response_m"])
            scalars["peak_speed_rpm"] = float(data["peak_speed_rpm"])
            units["peak_response_m"] = "m"
            units["peak_speed_rpm"] = "rpm"
        else:
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, f"unknown ROSS analysis:{analysis}"
            )
        log_decrement = _finite_optional(data.get("first_log_decrement"))
        if analysis == "modal" and log_decrement is not None:
            scalars["first_log_decrement"] = log_decrement
            units["first_log_decrement"] = "dimensionless"
        forcing_margin = _finite_optional(data.get("min_forcing_separation_hz"))
        if forcing_margin is not None and forcing_margin >= 0:
            scalars["min_forcing_separation_hz"] = forcing_margin
            units["min_forcing_separation_hz"] = "Hz"
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


def screening_beam_critical_rpm(inputs: Mapping[str, object]) -> float | None:
    """Best-effort screening estimate; never raises on unusual model shapes."""

    try:
        length = float(inputs["shaft_length_m"])  # type: ignore[arg-type]
        diameter = float(inputs["shaft_diameter_m"])  # type: ignore[arg-type]
        if length > 0 and diameter > 0:
            return beam_first_critical_rpm(shaft_length_m=length, shaft_diameter_m=diameter)
    except (KeyError, TypeError, ValueError):
        pass
    try:
        model = normalize_rotor_model(inputs)
    except (RotorModelError, ForcingSpecError):
        return None
    length = model.total_length_m
    diameter = model.max_outer_diameter_m
    if length <= 0 or diameter <= 0:
        return None
    return beam_first_critical_rpm(
        shaft_length_m=length,
        shaft_diameter_m=diameter,
        youngs_pa=model.material.youngs_modulus_pa,
        density_kg_m3=model.material.density_kg_m3,
    )


def validate_rotor_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    checks: dict[str, bool] = {}
    if "first_critical_rpm" in scalars:
        first = float(scalars["first_critical_rpm"])
        has_second = "second_critical_rpm" in scalars
        second = float(scalars.get("second_critical_rpm", float("nan")))
        checks["criticals_positive"] = first > 0 and (not has_second or second > 0)
        checks["criticals_ascending"] = (not has_second) or second > first
        estimate = screening_beam_critical_rpm(inputs)
        if estimate is not None and estimate > 0:
            ratio = first / estimate
            checks["screening_plausible"] = (
                math.isfinite(ratio)
                and 1.0 / SCREENING_PLAUSIBILITY_FACTOR
                <= ratio
                <= SCREENING_PLAUSIBILITY_FACTOR
            )
            detail = (
                f"native first critical {first:.1f} rpm vs screening beam estimate "
                f"{estimate:.1f} rpm (ratio {ratio:.3f}); native bearing/gyroscopic modes "
                "are authoritative, the beam estimate is a plausibility band only"
            )
        else:
            detail = (
                "screening beam estimate unavailable for this assembly; "
                "native bearing/gyroscopic modes are authoritative"
            )
    elif "first_whirl_hz" in scalars:
        whirl = float(scalars["first_whirl_hz"])
        damping = float(scalars["first_damping_ratio"])
        checks["whirl_positive"] = whirl > 0
        checks["damping_finite"] = damping == damping and abs(damping) < 1.0
        log_decrement = scalars.get("first_log_decrement")
        if log_decrement is not None:
            value = float(log_decrement)
            checks["log_decrement_valid"] = math.isfinite(value) and value >= 0
        detail = "forward whirl positive with bounded damping ratio"
    else:
        peak = float(scalars.get("peak_response_m", float("nan")))
        checks["response_finite"] = peak == peak and peak >= 0
        detail = "forced peak response finite and non-negative"
    margin = scalars.get("min_forcing_separation_hz")
    if margin is not None:
        value = float(margin)
        checks["forcing_separation_nonnegative"] = math.isfinite(value) and value >= 0
        detail = f"{detail}; declared forcing separation {value:.3f} Hz"
    return ValidityReport(
        participant_id="ross",
        passed=all(checks.values()),
        checks=checks,
        detail=detail,
    )
