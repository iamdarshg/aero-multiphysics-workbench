"""Real Elmer model preparation, log parsing, and validation.

The lifecycle entry points live here. Given a governed solver-mesh mapping the
native thermal builder (steady or transient, multi-body, semantic material
groups, heat sources, fixed/flux/convection/interface boundary conditions) is
used; otherwise the original single-body thermal/electrostatic scalar deck is
rendered. Parsing reads solver-produced SaveScalars tables plus the ElmerSolver
log and fails closed when ElmerSolver is absent. Native parsing also publishes
canonical interface field artifacts (Temperature / Heat-Flux) with mesh and
interface lineage.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

from .case import prepare_native_thermal
from .parser import parse_elmer_output, publish_case_fields, validate_elmer_result

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
    """Write case.sif for the requested supported model.

    A governed solver-mesh mapping (``mesh_mapping`` or ``mesh_mapping_path``)
    selects the native thermal case builder, which ingests semantic groups and
    material revisions. The scalar legacy thermal/electrostatic inputs keep the
    original single-body behavior.
    """

    if "mesh_mapping" in inputs or "mesh_mapping_path" in inputs:
        return prepare_native_thermal(inputs, case_dir)

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
    """Parse an Elmer run: native thermal output or the legacy scalar tables.

    Native cases additionally publish canonical interface field artifacts
    (Temperature / Heat-Flux / interface heat flow) when native values exist.
    A ``result.json`` canonical artifact is always written from the parsed
    native scalars so the manifested artifact set is complete.
    """

    parsed = parse_elmer_output(case_dir)
    publish_case_fields(case_dir, parsed)
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "participant_id": "elmer",
                "parser": parsed.parser,
                "detail": parsed.detail,
                "scalars": dict(sorted(parsed.scalars.items())),
                "units": dict(sorted(parsed.units.items())),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return parsed


def validate_sif_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """Validate an Elmer result.

    Native thermal cases require solver convergence and an energy-balance
    closure within the declared tolerance; the legacy scalar paths keep their
    original temperature/potential checks.
    """

    return validate_elmer_result(scalars, inputs)
