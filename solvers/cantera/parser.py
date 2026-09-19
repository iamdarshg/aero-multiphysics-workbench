"""Parse and validate governed Cantera combustion results.

The parser converts the native ``result.json`` into typed scalars with units;
the validity gate enforces convergence, physical temperature/pressure bounds,
energy closure against the fuel lower heating value, and bounded mole fractions.
A malformed or non-Cantera result never passes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, ValidityReport

from .case import RUN_LIBRARY

_SPECIES_PREFIX = "x_"
_ENERGY_CLOSURE_TOLERANCE = 0.15
_SPECIES_SUM_TOLERANCE = 1.0e-3

_REQUIRED_RESULT_FIELDS = (
    "exit_total_temperature_k",
    "exit_total_pressure_pa",
    "adiabatic_flame_temperature_k",
    "fuel_mass_flow_kg_s",
    "heat_release_w",
    "combustion_efficiency",
    "pressure_loss_fraction",
)

_UNITS: dict[str, str] = {
    "exit_total_temperature_k": "K",
    "exit_total_pressure_pa": "Pa",
    "adiabatic_flame_temperature_k": "K",
    "fuel_mass_flow_kg_s": "kg/s",
    "heat_release_w": "W",
    "combustion_efficiency": "dimensionless",
    "pressure_loss_fraction": "dimensionless",
    "pattern_factor": "dimensionless",
    "residence_time_s": "s",
    "stability_indicator": "dimensionless",
    "converged": "dimensionless",
    "inlet_temperature_k": "K",
    "inlet_pressure_pa": "Pa",
}


def _parser_fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PARSER_FAILED, detail)


def parse_combustion_result(case_dir: Path) -> ParseReceipt:
    """Convert a native Cantera ``result.json`` into typed scalars."""

    target = case_dir / "result.json"
    if not target.is_file():
        raise _parser_fail("result.json is missing")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _parser_fail(f"result.json unreadable:{exc}") from exc
    if not isinstance(data, dict) or data.get("library") != RUN_LIBRARY:
        raise _parser_fail("result.json is not a Cantera receipt")

    for field in _REQUIRED_RESULT_FIELDS:
        if field not in data:
            raise _parser_fail(f"cantera result missing field:{field}")

    scalars: dict[str, float] = {}
    units = dict(_UNITS)
    try:
        for field in _REQUIRED_RESULT_FIELDS:
            scalars[field] = float(data[field])
    except (TypeError, ValueError) as exc:
        raise _parser_fail(f"cantera result field invalid:{exc}") from exc

    for optional in (
        "inlet_temperature_k",
        "inlet_pressure_pa",
        "pattern_factor",
        "residence_time_s",
        "stability_indicator",
    ):
        if optional in data:
            scalars[optional] = float(data[optional])
    scalars["converged"] = 1.0 if bool(data.get("converged", False)) else 0.0

    mole_fractions = data.get("mole_fractions")
    if not isinstance(mole_fractions, Mapping):
        raise _parser_fail("cantera result has no mole_fractions")
    for species, fraction in mole_fractions.items():
        key = f"{_SPECIES_PREFIX}{species}"
        scalars[key] = float(cast_fraction(fraction, str(species)))
        units[key] = "dimensionless"

    return ParseReceipt(
        participant_id="combustion-reacting-flow",
        parser="cantera.parser:parse_combustion_result",
        scalars=scalars,
        units=units,
        detail=(
            f"mechanism={data.get('mechanism', 'unknown')} "
            f"mode={data.get('reactor_mode', 'unknown')} "
            f"version={data.get('cantera_version', 'unknown')}"
        ),
    )


def cast_fraction(value: object, species: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _parser_fail(f"mole fraction invalid:{species}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise _parser_fail(f"mole fraction non-finite:{species}")
    return number


def validate_combustion_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """Enforce convergence, physical bounds, closure, and species bounds."""

    exit_temperature = float(scalars.get("exit_total_temperature_k", float("nan")))
    adiabatic = float(scalars.get("adiabatic_flame_temperature_k", float("nan")))
    exit_pressure = float(scalars.get("exit_total_pressure_pa", float("nan")))
    heat_release = float(scalars.get("heat_release_w", float("nan")))
    efficiency = float(scalars.get("combustion_efficiency", float("nan")))
    pressure_loss = float(scalars.get("pressure_loss_fraction", float("nan")))
    inlet_temperature = _lookup_float(scalars, inputs, "inlet_temperature_k")
    fuel_mass_flow = _lookup_float(scalars, inputs, "fuel_mass_flow_kg_s")
    heating_value = _input_float(inputs, "fuel_lower_heating_value_j_kg")
    input_efficiency = _input_float(inputs, "combustion_efficiency")

    expected_heat = input_efficiency * fuel_mass_flow * heating_value
    energy_residual = (
        abs(heat_release - expected_heat) / max(abs(expected_heat), 1e-30)
        if expected_heat > 0.0 and expected_heat == expected_heat
        else float("nan")
    )

    species = {
        name: value for name, value in scalars.items() if name.startswith(_SPECIES_PREFIX)
    }
    species_sum = sum(species.values()) if species else float("nan")

    checks = {
        "converged": scalars.get("converged", 0.0) == 1.0,
        "temperature_physical": (
            adiabatic == adiabatic
            and exit_temperature == exit_temperature
            and 200.0 < adiabatic < 4000.0
            and 200.0 < exit_temperature < 4000.0
            and (inlet_temperature != inlet_temperature or exit_temperature > inlet_temperature)
        ),
        "pressure_positive": exit_pressure == exit_pressure and exit_pressure > 0.0,
        "pressure_loss_bounds": pressure_loss == pressure_loss
        and 0.0 <= pressure_loss < 0.5,
        "efficiency_bounds": efficiency == efficiency and 0.0 < efficiency <= 1.0,
        "energy_closure": (
            energy_residual == energy_residual
            and energy_residual < _ENERGY_CLOSURE_TOLERANCE
        ),
        "species_bounded": (
            bool(species)
            and all(0.0 <= value <= 1.0 for value in species.values())
            and species_sum == species_sum
            and abs(species_sum - 1.0) < _SPECIES_SUM_TOLERANCE
        ),
    }
    return ValidityReport(
        participant_id="combustion-reacting-flow",
        passed=all(checks.values()),
        checks=checks,
        detail=(
            "converged, physical T/P, energy closure within 15% of LHV, "
            "mole fractions bounded and normalized"
        ),
    )


def _input_float(inputs: Mapping[str, object], name: str) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return float("nan")
    return float(value)


def _lookup_float(
    scalars: Mapping[str, float], inputs: Mapping[str, object], name: str
) -> float:
    if name in scalars:
        return float(scalars[name])
    return _input_float(inputs, name)
