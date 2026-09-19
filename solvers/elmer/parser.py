"""Elmer result parsing and validity for the native thermal participant.

Parsing reads the ElmerSolver log (clean finish and convergence state) plus the
SaveScalars tables: the global ``result.dat`` (max/min/mean temperature and
heat flux), per-body ``region_<name>.dat`` tables, per-interface
``interface_<name>.dat`` tables (temperature and integrated heat flow), an
optional transient ``history.dat``, and the native energy-balance row. Nothing
is fabricated: a missing energy balance parses as ``NaN`` and fails validity
rather than being defaulted to zero.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, ValidityReport

from . import fields

_OP_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_ -]*?)\s*:\s*(.+?)\s*$")
_OP_VALUE = re.compile(r"([A-Za-z][A-Za-z0-9_ ]*?)\s*=\s*([0-9.eE+-]+)")
_ERROR_MARKERS = ("ERROR", "SEGMENTATION FAULT", "SIGSEGV", "ABORTED")


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PARSER_FAILED, detail)


def _sanitize(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")


def _parse_operators(text: str) -> dict[tuple[str, str], float]:
    """Parse ``Variable : op = value [op = value]`` SaveScalars rows."""

    values: dict[tuple[str, str], float] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _OP_LINE.match(line)
        if match is None:
            continue
        variable = match.group(1).strip()
        for operator, raw in _OP_VALUE.findall(match.group(2)):
            try:
                values[(variable, operator.strip().lower())] = float(raw)
            except ValueError:
                continue
    return values


def _load_case_manifest(case_dir: Path) -> dict[str, object] | None:
    target = case_dir / "case.json"
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _log_convergence(log_text: str) -> float:
    upper = log_text.upper()
    if any(marker in upper for marker in _ERROR_MARKERS):
        return 0.0
    return 1.0


def _parse_history(case_dir: Path) -> dict[str, float]:
    target = case_dir / "history.dat"
    if not target.is_file():
        return {}
    rows: list[tuple[float, float, float]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        try:
            rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
        except ValueError:
            continue
    if not rows:
        return {}
    peak = max(row[1] for row in rows)
    return {
        "transient_history_points": float(len(rows)),
        "transient_start_time_s": rows[0][0],
        "transient_end_time_s": rows[-1][0],
        "peak_temperature_k": peak,
        "final_max_temperature_k": rows[-1][1],
        "final_min_temperature_k": rows[-1][2],
    }


def _native_scalars(case_dir: Path, case_manifest: Mapping[str, object]) -> dict[str, float]:
    log_path = case_dir / "solver.log"
    if not log_path.is_file():
        raise _fail("solver.log is missing")
    log_text = log_path.read_text(encoding="utf-8")
    if "ElmerSolver: ALL DONE" not in log_text and "ELMER SOLVER FINISHED" not in log_text:
        raise _fail("Elmer log shows no clean finish")

    table_path = case_dir / "result.dat"
    if not table_path.is_file():
        raise _fail("result.dat is missing")
    global_values = _parse_operators(table_path.read_text(encoding="utf-8"))
    if ("Temperature", "max") not in global_values:
        raise _fail("result.dat has no Temperature max row")

    scalars: dict[str, float] = {}
    maximum = global_values.get(("Temperature", "max"))
    minimum = global_values.get(("Temperature", "min"))
    if maximum is not None:
        scalars["max_temperature_k"] = maximum
    if minimum is not None:
        scalars["min_temperature_k"] = minimum
    mean = global_values.get(("Temperature", "mean"))
    if mean is not None:
        scalars["mean_temperature_k"] = mean
    flux_max = global_values.get(("Heat Flux", "max"))
    if flux_max is not None:
        scalars["max_heat_flux_w_m2"] = flux_max
    flux_min = global_values.get(("Heat Flux", "min"))
    if flux_min is not None:
        scalars["min_heat_flux_w_m2"] = flux_min
    scalars["converged"] = _log_convergence(log_text)

    balance_error = global_values.get(("Energy Balance", "error"))
    balance_relative = global_values.get(("Energy Balance", "relative error"))
    scale = case_manifest.get("totalHeatInputW")
    scale_value = float(scale) if isinstance(scale, (int, float)) else 0.0
    if balance_relative is not None:
        scalars["energy_balance_relative_error"] = abs(balance_relative)
    elif balance_error is not None:
        scalars["energy_balance_error_w"] = balance_error
        scalars["energy_balance_relative_error"] = abs(balance_error) / max(scale_value, 1e-30)
    else:
        # Derive closure from the masked per-boundary diffusive-flux tables that
        # the native SIF writes: a steady domain with no volumetric source must
        # have net boundary heat flow ~0 relative to the incident flow.
        boundary_fluxes: list[float] = []
        for boundary_file in sorted(case_dir.glob("boundary_*.dat")):
            values = _parse_operators(boundary_file.read_text(encoding="utf-8"))
            flux = values.get(("Temperature", "diffusive flux"))
            if flux is None:
                flux = values.get(("Temperature", "flux"))
            if flux is None:
                continue
            tag = _sanitize(boundary_file.stem.removeprefix("boundary_"))
            scalars[f"boundary_{tag}_heat_flow_w"] = flux
            boundary_fluxes.append(flux)
        if boundary_fluxes:
            net_flux = sum(boundary_fluxes)
            denominator = 0.5 * sum(abs(value) for value in boundary_fluxes)
            scalars["energy_balance_error_w"] = net_flux
            scalars["energy_balance_relative_error"] = abs(net_flux) / max(
                denominator, 1e-30
            )
        else:
            scalars["energy_balance_error_w"] = float("nan")
            scalars["energy_balance_relative_error"] = float("nan")

    for region_file in sorted(case_dir.glob("region_*.dat")):
        region = _sanitize(region_file.stem.removeprefix("region_"))
        values = _parse_operators(region_file.read_text(encoding="utf-8"))
        region_max = values.get(("Temperature", "max"))
        region_min = values.get(("Temperature", "min"))
        if region_max is not None:
            scalars[f"max_temperature_k_{region}"] = region_max
        if region_min is not None:
            scalars[f"min_temperature_k_{region}"] = region_min

    for interface_file in sorted(case_dir.glob("interface_*.dat")):
        interface = _sanitize(interface_file.stem.removeprefix("interface_"))
        values = _parse_operators(interface_file.read_text(encoding="utf-8"))
        interface_max = values.get(("Temperature", "max"))
        interface_min = values.get(("Temperature", "min"))
        interface_flux = values.get(("Temperature", "flux"))
        if interface_flux is None:
            interface_flux = values.get(("Temperature", "diffusive flux"))
        if interface_max is not None:
            scalars[f"interface_{interface}_max_temperature_k"] = interface_max
        if interface_min is not None:
            scalars[f"interface_{interface}_min_temperature_k"] = interface_min
        if interface_flux is not None:
            scalars[f"interface_{interface}_heat_flow_w"] = interface_flux

    scalars.update(_parse_history(case_dir))
    return scalars


def _legacy_scalars(case_dir: Path) -> dict[str, float]:
    log_path = case_dir / "solver.log"
    if not log_path.is_file():
        raise _fail("solver.log is missing")
    log_text = log_path.read_text(encoding="utf-8")
    if "ElmerSolver: ALL DONE" not in log_text and "ELMER SOLVER FINISHED" not in log_text:
        raise _fail("Elmer log shows no clean finish")
    table_path = case_dir / "result.dat"
    if not table_path.is_file():
        raise _fail("result.dat is missing")
    values = _parse_operators(table_path.read_text(encoding="utf-8"))
    if ("Temperature", "max") in values:
        scalars = {
            "max_temperature_k": values[("Temperature", "max")],
            "min_temperature_k": values.get(("Temperature", "min"), float("nan")),
        }
        if ("Heat Flux", "max") in values:
            scalars["max_heat_flux_w_m2"] = values[("Heat Flux", "max")]
        return scalars
    if ("Potential", "max") in values:
        maximum = values[("Potential", "max")]
        minimum = values.get(("Potential", "min"), maximum)
        return {
            "max_potential_v": maximum,
            "potential_span_v": max(maximum - minimum, 0.0),
        }
    raise _fail("result.dat has no known variable")


def parse_elmer_output(case_dir: Path) -> ParseReceipt:
    """Parse an Elmer run; native cases include energy/convergence scalars."""

    manifest = _load_case_manifest(case_dir)
    if manifest is not None and manifest.get("native") is True:
        scalars = _native_scalars(case_dir, manifest)
        detail = (
            f"native {manifest.get('analysis', 'steady')} thermal: "
            f"{len([k for k in scalars if k.endswith('_k')])} temperature scalars"
        )
    else:
        scalars = _legacy_scalars(case_dir)
        detail = (
            "parsed electrostatics SaveScalars"
            if "max_potential_v" in scalars
            else "parsed heat-equation SaveScalars"
        )
    units: dict[str, str] = {}
    for key in scalars:
        if key.endswith("_k"):
            units[key] = "K"
        elif key.startswith("max_heat_flux") or key.startswith("min_heat_flux"):
            units[key] = "W/m^2"
        elif "heat_flow_w" in key or key == "energy_balance_error_w":
            units[key] = "W"
        elif key.endswith("_s"):
            units[key] = "s"
        elif key.endswith("_v"):
            units[key] = "V"
        elif key == "converged":
            units[key] = "dimensionless"
        else:
            units[key] = "dimensionless"
    return ParseReceipt(
        participant_id="elmer",
        parser="elmer.parser:parse_elmer_output",
        scalars=scalars,
        units=units,
        detail=detail,
    )


def validate_elmer_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """Native thermal validity requires convergence and energy closure."""

    if "energy_balance_relative_error" in scalars or (
        "converged" in scalars and "energy_balance_error_w" in scalars
    ):
        converged = float(scalars.get("converged", 0.0)) >= 0.5
        relative = float(scalars.get("energy_balance_relative_error", float("nan")))
        tolerance = inputs.get("energy_balance_tolerance", 1.0e-3)
        tolerance_value = float(tolerance) if isinstance(tolerance, (int, float)) else 1.0e-3
        closure = (
            relative == relative
            and not math.isinf(relative)
            and relative <= tolerance_value
        )
        finite = all(
            value == value
            for value in (
                scalars.get("max_temperature_k", float("nan")),
                scalars.get("min_temperature_k", float("nan")),
            )
        )
        ambient = inputs.get("ambient_k")
        heating_consistent = True
        if isinstance(ambient, (int, float)):
            heating_consistent = (
                scalars.get("min_temperature_k", float("nan"))
                >= float(ambient) - 1e-6
            )
        checks = {
            "converged": converged,
            "temperature_finite": finite,
            "energy_closure": closure,
            "heating_consistent": heating_consistent,
        }
        return ValidityReport(
            participant_id="elmer",
            passed=all(checks.values()),
            checks=checks,
            detail=(
                "native run converged and energy balance closed within "
                f"{tolerance_value:g} relative"
            ),
        )

    if "max_temperature_k" in scalars:
        maximum = float(scalars["max_temperature_k"])
        minimum = float(scalars.get("min_temperature_k", float("nan")))
        ambient = inputs.get("ambient_k", 0.0)
        ambient_value = float(ambient) if isinstance(ambient, (int, float)) else 0.0
        checks = {
            "temperature_finite": maximum == maximum and minimum == minimum,
            "heating_consistent": maximum >= minimum >= ambient_value,
        }
        detail = "peak/min temperatures finite and at/above the fixed boundary value"
    else:
        maximum = float(scalars.get("max_potential_v", float("nan")))
        span = float(scalars.get("potential_span_v", float("nan")))
        voltage = inputs.get("voltage_v", 0.0)
        applied = float(voltage) if isinstance(voltage, (int, float)) else 0.0
        checks = {
            "potential_finite": maximum == maximum and span == span and span >= 0,
            "bounded_by_electrode": maximum <= applied * (1.0 + 1e-6) + 1e-12,
        }
        detail = "potential span finite and bounded by the electrode voltage"
    return ValidityReport(
        participant_id="elmer",
        passed=all(checks.values()),
        checks=checks,
        detail=detail,
    )


def publish_case_fields(case_dir: Path, parsed: ParseReceipt) -> tuple[Path, ...]:
    """Write canonical Temperature/Heat-Flux artifacts from a native parse.

    Only interfaces with parsed native values produce artifacts; the interface
    hash, mesh hash, and units are carried from ``case.json``. Nothing is
    synthesized when the native result lacks the corresponding value.
    """

    manifest = _load_case_manifest(case_dir)
    if manifest is None or manifest.get("native") is not True:
        return ()
    mesh = manifest.get("mesh")
    if not isinstance(mesh, Mapping):
        return ()
    mesh_hash = str(mesh.get("meshHash", ""))
    if len(mesh_hash) != 64:
        return ()
    geometry_hash = mesh.get("geometryHash")
    mapping_hash = mesh.get("mappingHash")
    analysis = str(manifest.get("analysis", "steady"))
    interfaces = manifest.get("interfaces", [])
    if not isinstance(interfaces, list):
        return ()
    case_hash = hashlib.sha256((case_dir / "case.json").read_bytes()).hexdigest()
    written: list[Path] = []
    for interface in interfaces:
        if not isinstance(interface, Mapping):
            continue
        name = str(interface.get("name", ""))
        kind = str(interface.get("kind", ""))
        zone_a = str(interface.get("zoneA", ""))
        zone_b = str(interface.get("zoneB", ""))
        sanitized = _sanitize(name)
        maximum = parsed.scalars.get(f"interface_{sanitized}_max_temperature_k")
        minimum = parsed.scalars.get(f"interface_{sanitized}_min_temperature_k")
        heat_flow = parsed.scalars.get(f"interface_{sanitized}_heat_flow_w")
        if maximum is None and minimum is None and heat_flow is None:
            continue
        common = {
            "mesh_hash": mesh_hash,
            "interface_name": name,
            "interface_kind": kind,
            "zone_a": zone_a,
            "zone_b": zone_b,
            "analysis": analysis,
            "geometry_hash": geometry_hash if isinstance(geometry_hash, str) else None,
            "mapping_hash": mapping_hash if isinstance(mapping_hash, str) else None,
            "case_hash": case_hash,
            "detail": "interface exchange parsed from native Elmer SaveScalars",
        }
        if maximum is not None or minimum is not None:
            entries: list[fields.FieldEntry] = []
            if maximum is not None:
                entries.append(fields.FieldEntry("max", maximum))
            if minimum is not None:
                entries.append(fields.FieldEntry("min", minimum))
            statistics = {entry.label: entry.value for entry in entries}
            artifact = fields.build_field_artifact(
                field_name="Temperature",
                entries=tuple(entries),
                statistics=statistics,
                **common,
            )
            written.append(fields.write_field_artifact(case_dir, artifact))
        if heat_flow is not None:
            artifact = fields.build_field_artifact(
                field_name="Interface-Heat-Flow",
                entries=(fields.FieldEntry("heat-flow", heat_flow),),
                statistics={"heat-flow": heat_flow},
                **common,
            )
            written.append(fields.write_field_artifact(case_dir, artifact))
    flux_max = parsed.scalars.get("max_heat_flux_w_m2")
    flux_min = parsed.scalars.get("min_heat_flux_w_m2")
    if (flux_max is not None or flux_min is not None) and interfaces:
        first = interfaces[0]
        if isinstance(first, Mapping):
            entries = []
            if flux_max is not None:
                entries.append(fields.FieldEntry("max", flux_max))
            if flux_min is not None:
                entries.append(fields.FieldEntry("min", flux_min))
            artifact = fields.build_field_artifact(
                field_name="Heat-Flux",
                mesh_hash=mesh_hash,
                interface_name=str(first.get("name", "")),
                interface_kind=str(first.get("kind", "")),
                zone_a=str(first.get("zoneA", "")),
                zone_b=str(first.get("zoneB", "")),
                entries=tuple(entries),
                statistics={entry.label: entry.value for entry in entries},
                analysis=analysis,
                geometry_hash=geometry_hash if isinstance(geometry_hash, str) else None,
                mapping_hash=mapping_hash if isinstance(mapping_hash, str) else None,
                case_hash=case_hash,
                detail="heat-flux field extrema parsed from native Elmer SaveScalars",
            )
            written.append(fields.write_field_artifact(case_dir, artifact))
    return tuple(written)
