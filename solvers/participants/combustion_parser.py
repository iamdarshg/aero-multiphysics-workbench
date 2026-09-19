"""Participant-level parse and validity entrypoints for combustion.

The native chemistry parser/validator lives in ``cantera.parser``; this module
re-exports them as the governed participant refs and adds parsing for the
reduced-order combustor-network payload.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from cantera.parser import (
    parse_combustion_result as _parse_combustion_result,
)
from cantera.parser import (
    validate_combustion_result as _validate_combustion_result,
)

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, ValidityReport

from .combustion_case import validate_combustor_network_result

_NETWORK_UNITS: dict[str, str] = {
    "exit_total_temperature_k": "K",
    "exit_total_pressure_pa": "Pa",
    "exit_peak_temperature_k": "K",
    "fuel_mass_flow_kg_s": "kg/s",
    "heat_release_w": "W",
    "combustion_efficiency": "dimensionless",
    "pressure_loss_fraction": "dimensionless",
    "pattern_factor": "dimensionless",
    "residence_time_s": "s",
    "stability_indicator": "dimensionless",
}


def parse_combustion_result(case_dir: Path) -> ParseReceipt:
    """Parse a native Cantera ``result.json`` through the governed parser."""

    return _parse_combustion_result(case_dir)


def validate_combustion_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """Validate native Cantera scalars through the governed gate."""

    return _validate_combustion_result(scalars, inputs)


def parse_combustor_network_result(case_dir: Path) -> ParseReceipt:
    """Parse a reduced-order combustor-network ``result.json``."""

    target = case_dir / "result.json"
    if not target.is_file():
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "combustor network result.json is missing"
        )
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    if not isinstance(data, dict) or data.get("model") != "reduced-combustor-network":
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result.json is not a combustor network receipt"
        )
    scalars: dict[str, float] = {}
    for key in _NETWORK_UNITS:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, f"combustor network field invalid:{key}"
            )
        scalars[key] = float(value)
    return ParseReceipt(
        participant_id="combustion-reacting-flow",
        parser="participants.combustion_parser:parse_combustor_network_result",
        scalars=scalars,
        units=dict(_NETWORK_UNITS),
        detail="reduced-order combustor network result",
    )


def validate_combustor_network(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    return validate_combustor_network_result(scalars, inputs)
