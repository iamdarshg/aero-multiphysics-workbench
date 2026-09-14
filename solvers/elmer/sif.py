"""Real Elmer model preparation, log parsing, and validation.

Supports a steady heat-conduction model and an electrostatic model, each
with mesh/material/boundary export in native .sif syntax. The sif declares
SaveScalars output so the parser reads solver-produced result.dat plus the
ElmerSolver log; execution stays fail-closed when ElmerSolver is absent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

MODELS = ("thermal", "electrostatic")


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


def _require_str(inputs: Mapping[str, object], name: str, allowed: tuple[str, ...]) -> str:
    value = inputs.get(name)
    if not isinstance(value, str) or value not in allowed:
        raise _fail(f"input {name} must be one of {sorted(allowed)}")
    return value


def prepare_sif(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Write case.sif for the requested supported model."""

    data: Mapping[str, object] = dict(inputs)
    model = _require_str(data, "model", MODELS)
    if model == "thermal":
        conductivity = _require_float(data, "conductivity_w_m_k")
        heat_load = _require_float(data, "heat_load_w")
        ambient = _require_float(data, "ambient_k")
        if conductivity <= 0 or ambient <= 0 or heat_load < 0:
            raise _fail("thermal properties out of physical range")
        canonical: dict[str, Any] = {
            "model": model,
            "conductivity_w_m_k": conductivity,
            "heat_load_w": heat_load,
            "ambient_k": ambient,
        }
        sif = _thermal_sif(conductivity, heat_load, ambient)
    else:
        permittivity = _require_float(data, "permittivity")
        voltage = _require_float(data, "voltage_v")
        if permittivity <= 0 or voltage < 0:
            raise _fail("electrostatic properties out of physical range")
        canonical = {"model": model, "permittivity": permittivity, "voltage_v": voltage}
        sif = _electrostatic_sif(permittivity, voltage)
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.sif").write_text(sif, encoding="utf-8")
    return PrepareReceipt(
        participant_id="elmer",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.sif",),
        detail=f"model={model}",
    )


def _thermal_sif(conductivity: float, heat_load: float, ambient: float) -> str:
    return (
        "Header\n"
        "  CHECK KEYWORDS Warn\n"
        "  Mesh DB \".\" \"mesh\"\n"
        "  Include Path \"\"\n"
        "  Results Directory \"\"\n"
        "End\n"
        "\n"
        "Simulation\n"
        "  Max Output Level = 4\n"
        "  Coordinate System = Cartesian 3D\n"
        "  Simulation Type = Steady State\n"
        "  Steady State Max Iterations = 50\n"
        "  Output File = \"case.result\"\n"
        "  Post File = \"case.vtu\"\n"
        "End\n"
        "\n"
        "Body 1\n"
        "  Equation = 1\n"
        "  Material = 1\n"
        f"  Body Force = 1\n"
        "End\n"
        "\n"
        "Body Force 1\n"
        "  Name = \"JouleHeat\"\n"
        f"  Heat Source = {heat_load:.6e}\n"
        "End\n"
        "\n"
        "Equation 1\n"
        "  Name = \"HeatEquation\"\n"
        "  Active Solvers(1) = 1\n"
        "End\n"
        "\n"
        "Solver 1\n"
        "  Equation = Heat Equation\n"
        "  Procedure = \"HeatSolve\" \"HeatSolver\"\n"
        "  Variable = Temperature\n"
        "  Exec Solver = Always\n"
        "  Stabilize = True\n"
        "  Bubbles = False\n"
        "  Lumped Mass Matrix = False\n"
        "  Optimize Bandwidth = True\n"
        "  Steady State Convergence Tolerance = 1.0e-5\n"
        "  Nonlinear System Convergence Tolerance = 1.0e-5\n"
        "  Nonlinear System Max Iterations = 20\n"
        "  Nonlinear System Newton After Iterations = 3\n"
        "  Nonlinear System Newton After Tolerance = 1.0e-3\n"
        "  Nonlinear System Relaxation Factor = 1\n"
        "  Linear System Solver = Iterative\n"
        "  Linear System Iterative Method = BiCGStab\n"
        "  Linear System Preconditioning = ILUT\n"
        "  Linear System Max Iterations = 500\n"
        "  Linear System Convergence Tolerance = 1.0e-7\n"
        "End\n"
        "\n"
        "Solver 2\n"
        "  Equation = SaveScalars\n"
        "  Procedure = \"SaveData\" \"SaveScalars\"\n"
        "  Filename = \"result.dat\"\n"
        "  Variable 1 = Temperature\n"
        "  Operator 1 = max\n"
        "  Variable 2 = Temperature\n"
        "  Operator 2 = min\n"
        "End\n"
        "\n"
        "Material 1\n"
        "  Name = \"GenericSolid\"\n"
        f"  Heat Conductivity = {conductivity:.6e}\n"
        "  Density = 2700.0\n"
        "  Heat Capacity = 900.0\n"
        "End\n"
        "\n"
        "Boundary Condition 1\n"
        "  Name = \"FixedTemp\"\n"
        "  Target Boundaries(1) = 1\n"
        f"  Temperature = {ambient:.6e}\n"
        "  Save Scalars = True\n"
        "End\n"
    )


def _electrostatic_sif(permittivity: float, voltage: float) -> str:
    return (
        "Header\n"
        "  CHECK KEYWORDS Warn\n"
        "  Mesh DB \".\" \"mesh\"\n"
        "  Include Path \"\"\n"
        "  Results Directory \"\"\n"
        "End\n"
        "\n"
        "Simulation\n"
        "  Max Output Level = 4\n"
        "  Coordinate System = Cartesian 3D\n"
        "  Simulation Type = Steady State\n"
        "  Steady State Max Iterations = 1\n"
        "  Output File = \"case.result\"\n"
        "  Post File = \"case.vtu\"\n"
        "End\n"
        "\n"
        "Body 1\n"
        "  Equation = 1\n"
        "  Material = 1\n"
        "End\n"
        "\n"
        "Equation 1\n"
        "  Name = \"Electrostatics\"\n"
        "  Active Solvers(1) = 1\n"
        "End\n"
        "\n"
        "Solver 1\n"
        "  Equation = Stat Elec Solver\n"
        "  Procedure = \"StatElecSolve\" \"StatElecSolver\"\n"
        "  Variable = Potential\n"
        "  Exec Solver = Always\n"
        "  Stabilize = True\n"
        "  Optimize Bandwidth = True\n"
        "  Steady State Convergence Tolerance = 1.0e-5\n"
        "  Linear System Solver = Iterative\n"
        "  Linear System Iterative Method = BiCGStab\n"
        "  Linear System Preconditioning = ILU0\n"
        "  Linear System Max Iterations = 500\n"
        "  Linear System Convergence Tolerance = 1.0e-7\n"
        "End\n"
        "\n"
        "Solver 2\n"
        "  Equation = SaveScalars\n"
        "  Procedure = \"SaveData\" \"SaveScalars\"\n"
        "  Filename = \"result.dat\"\n"
        "  Variable 1 = Potential\n"
        "  Operator 1 = max\n"
        "  Variable 2 = Potential\n"
        "  Operator 2 = min\n"
        "End\n"
        "\n"
        "Material 1\n"
        "  Name = \"GenericDielectric\"\n"
        f"  Relative Permittivity = {permittivity:.6e}\n"
        "End\n"
        "\n"
        "Boundary Condition 1\n"
        "  Name = \"Electrode\"\n"
        "  Target Boundaries(1) = 1\n"
        f"  Potential = {voltage:.6e}\n"
        "  Save Scalars = True\n"
        "End\n"
        "\n"
        "Boundary Condition 2\n"
        "  Name = \"Ground\"\n"
        "  Target Boundaries(1) = 2\n"
        "  Potential = 0.0\n"
        "End\n"
    )


def parse_sif_result(case_dir: Path) -> ParseReceipt:
    """Parse ElmerSolver log plus SaveScalars result.dat."""

    log_path = case_dir / "solver.log"
    if not target_exists(log_path):
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver.log is missing")
    log_text = log_path.read_text(encoding="utf-8")
    if "ElmerSolver: ALL DONE" not in log_text and "ELMER SOLVER FINISHED" not in log_text:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "Elmer log shows no clean finish")
    table_path = case_dir / "result.dat"
    if not table_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.dat is missing")
    values = _parse_save_scalars(table_path.read_text(encoding="utf-8"))
    if "Temperature" in values:
        maximum, minimum = values["Temperature"]
        scalars = {
            "max_temperature_k": maximum,
            "min_temperature_k": minimum,
        }
        units = {"max_temperature_k": "K", "min_temperature_k": "K"}
        detail = "parsed heat-equation SaveScalars"
    elif "Potential" in values:
        maximum, minimum = values["Potential"]
        scalars = {
            "max_potential_v": maximum,
            "potential_span_v": max(maximum - minimum, 0.0),
        }
        units = {"max_potential_v": "V", "potential_span_v": "V"}
        detail = "parsed electrostatics SaveScalars"
    else:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result.dat has no known variable"
        )
    return ParseReceipt(
        participant_id="elmer",
        parser="elmer.sif:parse_sif_result",
        scalars=scalars,
        units=units,
        detail=detail,
    )


def target_exists(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _parse_save_scalars(text: str) -> dict[str, tuple[float, float]]:
    import re

    pattern = re.compile(r"^\s*(\w+)\s*:\s*max\s*=\s*([0-9.eE+-]+)\s+min\s*=\s*([0-9.eE+-]+)")
    values: dict[str, tuple[float, float]] = {}
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            try:
                values[match.group(1)] = (float(match.group(2)), float(match.group(3)))
            except ValueError:
                continue
    if not values:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "result.dat has no max/min rows"
        )
    return values


def validate_sif_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
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
