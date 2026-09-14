"""Real OpenFOAM case construction, log parsing, and result validation.

The writer produces a complete single-region case (system/, constant/, 0/)
from validated generic inputs: domain/boundary roles arrive as plain patch
names, never as application-specific geometry. Execution stays fail-closed
behind the governed runner when no OpenFOAM binary is present.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

COMPRESSIBILITY = ("incompressible", "compressible")
ROTATING = ("none", "MRF", "AMI")
THERMAL = ("isothermal", "CHT")
TURBULENCE = ("laminar", "kEpsilon", "kOmegaSST")
MAX_ROTATING_ZONES = 8

_ZONE_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)


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


def _require_rotating_zones(data: Mapping[str, object]) -> list[tuple[str, float]] | None:
    """Validate an optional generic list of rotating zones.

    Each entry declares ``{"name": <cell-zone>, "rotation_rate_rpm": <rate>}``.
    Zone names are opaque cell-zone identifiers (letters, digits, ``_``, ``-``);
    rates are finite floats and may differ per zone (counter-rotation allowed).
    Returns ``None`` when the caller declares no explicit zone list, in which
    case the legacy single ``rotation_rate_rpm`` input applies.
    """

    raw = data.get("rotating_zones", None)
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= MAX_ROTATING_ZONES:
        raise _fail(f"rotating_zones must list 1..{MAX_ROTATING_ZONES} zones")
    zones: list[tuple[str, float]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise _fail("each rotating zone must declare name and rotation_rate_rpm")
        name = entry.get("name")
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 64
            or any(character not in _ZONE_NAME_CHARS for character in name)
            or not name[0].isalnum()
        ):
            raise _fail(f"rotating zone name invalid:{name!r}")
        if name in seen:
            raise _fail(f"duplicate rotating zone:{name}")
        seen.add(name)
        rate = entry.get("rotation_rate_rpm")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise _fail(f"rotating zone {name} needs a numeric rotation_rate_rpm")
        rate_value = float(rate)
        if rate_value != rate_value or rate_value in (float("inf"), float("-inf")):
            raise _fail(f"rotating zone {name} needs a finite rotation_rate_rpm")
        zones.append((name, rate_value))
    return zones


def select_application(
    *, compressibility: str, steady: bool, rotating_model: str
) -> str:
    if compressibility == "compressible":
        return "rhoSimpleFoam" if steady else "rhoPimpleFoam"
    if rotating_model == "AMI":
        return "pimpleFoam"
    return "simpleFoam" if steady else "pimpleFoam"


def _canonical(inputs: Mapping[str, object]) -> dict[str, Any]:
    return {key: inputs[key] for key in sorted(inputs)}


def _input_hash(canonical: Mapping[str, object]) -> str:
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_case_files(
    inputs: dict[str, object], case_dir: Path
) -> PrepareReceipt:
    """Write a complete OpenFOAM case from validated generic inputs."""

    data: Mapping[str, object] = dict(inputs)
    compressibility = _require_str(data, "compressibility", COMPRESSIBILITY)
    rotating_model = _require_str(data, "rotating_model", ROTATING)
    thermal_model = _require_str(data, "thermal_model", THERMAL)
    turbulence = _require_str(data, "turbulence", TURBULENCE)
    steady_raw = data.get("steady", True)
    if not isinstance(steady_raw, bool):
        raise _fail("input steady must be a boolean")
    steady = steady_raw
    inlet_velocity = _require_float(data, "inlet_velocity_m_s")
    outlet_pressure = _require_float(data, "outlet_pressure_pa")
    density = _require_float(data, "density_kg_m3")
    viscosity = _require_float(data, "viscosity_pa_s")
    if inlet_velocity < 0 or density <= 0 or viscosity <= 0:
        raise _fail("velocity/density/viscosity out of physical range")
    temperature = (
        _require_float(data, "inlet_temperature_k") if thermal_model == "CHT" else 300.0
    )
    if temperature <= 0:
        raise _fail("temperature must be positive")
    rotating_zones = _require_rotating_zones(data)
    if rotating_zones is not None and rotating_model != "MRF":
        raise _fail("rotating_zones requires rotating_model=MRF")
    if rotating_model == "MRF" and rotating_zones is not None:
        rotation_rpm = rotating_zones[0][1]
        zone_specs: list[tuple[str, float]] = list(rotating_zones)
    else:
        rotation_rpm = (
            _require_float(data, "rotation_rate_rpm") if rotating_model != "none" else 0.0
        )
        zone_specs = (
            [("rotor", rotation_rpm)]
            if rotating_model == "MRF"
            else []
        )
    default_end = 500.0 if steady else 1.0
    end_time = _require_float(data, "end_time") if "end_time" in data else default_end
    if end_time <= 0:
        raise _fail("end_time must be positive")

    application = select_application(
        compressibility=compressibility, steady=steady, rotating_model=rotating_model
    )
    canonical = _canonical(
        {
            "compressibility": compressibility,
            "steady": steady,
            "rotating_model": rotating_model,
            "thermal_model": thermal_model,
            "turbulence": turbulence,
            "inlet_velocity_m_s": inlet_velocity,
            "outlet_pressure_pa": outlet_pressure,
            "density_kg_m3": density,
            "viscosity_pa_s": viscosity,
            "inlet_temperature_k": temperature,
            "rotation_rate_rpm": rotation_rpm,
            "rotating_zones": (
                [
                    {"name": name, "rotation_rate_rpm": rate}
                    for name, rate in zone_specs
                ]
                if rotating_zones is not None
                else None
            ),
            "end_time": end_time,
        }
    )
    digest = _input_hash(canonical)

    nu = viscosity / density
    time_scheme = "steadyState" if steady else "Euler"
    ddt_line = f"    ddtSchemes\n    {{\n        default         {time_scheme};\n    }}\n"
    files = {
        "system/controlDict": _control_dict(application, end_time, steady),
        "system/fvSchemes": _fv_schemes(ddt_line),
        "system/fvSolution": _fv_solution(application, steady, thermal_model),
        "constant/turbulenceProperties": _turbulence_properties(turbulence),
        "0/U": _field_u(inlet_velocity),
        "0/p": _field_p(outlet_pressure),
    }
    if compressibility == "incompressible":
        files["constant/transportProperties"] = (
            "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            "    class       dictionary;\n    object      transportProperties;\n}\n"
            f"nu              [0 2 -1 0 0 0 0] {nu:.6e};\n"
        )
    else:
        files["constant/thermophysicalProperties"] = (
            "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            "    class       dictionary;\n    object      thermophysicalProperties;\n}\n"
            "thermoType\n{\n    type            hePsiThermo;\n"
            "    mixture         pureMixture;\n    transport       const;\n"
            "    thermo          hConst;\n    equationOfState perfectGas;\n"
            "    specie          specie;\n    energy          sensibleEnthalpy;\n}\n"
            f"mixture\n{{\n    specie\n    {{\n        molWeight       28.9;\n    }}\n"
            "    thermodynamics\n    {\n        Cp              1005;\n"
            "        Hf              0;\n    }\n"
            "    transport\n    {\n"
            f"        mu              {viscosity:.6e};\n"
            "        Pr              0.7;\n    }}\n}}\n"
        )
    if rotating_model == "MRF":
        blocks = "".join(
            f"MRF{index + 1}\n{{\n    cellZone        {name};\n"
            "    active          yes;\n"
            "    nonRotatingPatches (inlet outlet);\n"
            "    origin          (0 0 0);\n    axis            (0 0 1);\n"
            f"    omega           constant {(rate * 0.104719755):.6f};\n"
            "}}\n"
            for index, (name, rate) in enumerate(zone_specs)
        )
        files["constant/MRFProperties"] = (
            "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            "    class       dictionary;\n    object      MRFProperties;\n}\n" + blocks
        )
    if thermal_model == "CHT":
        files["0/T"] = _field_t(temperature)

    case_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for relative, text in files.items():
        target = case_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(relative)
    return PrepareReceipt(
        participant_id=str(data.get("participant_id", "incompressible-steady-flow")),
        case_id=case_dir.name,
        input_hash=digest,
        files=tuple(sorted(written)),
        detail=f"application={application} turbulence={turbulence}",
    )


def _control_dict(application: str, end_time: float, steady: bool) -> str:
    delta_t = 1.0 if steady else 1e-4
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      controlDict;\n}\n"
        f"application     {application};\n\n"
        "startFrom       startTime;\n\nstartTime       0;\n\n"
        "stopAt          endTime;\n\n"
        f"endTime         {end_time:g};\n\n"
        f"deltaT          {delta_t:g};\n\n"
        "writeControl    timeStep;\n\nwriteInterval   50;\n\n"
        "purgeWrite      0;\n\nwriteFormat     ascii;\n\n"
        "writePrecision  6;\n\nwriteCompression off;\n\n"
        "timeFormat      general;\n\ntimePrecision 6;\n\n"
        "runTimeModifiable true;\n\n"
        "functions\n{\n    pressureProbes\n    {\n"
        "        type            probes;\n"
        '        libs            ("libsampling.so");\n'
        "        writeControl    writeTime;\n        fields          (p);\n"
        "        probeLocations\n        (\n"
        "            (-0.45 0 0)\n            (0.45 0 0)\n        );\n    }\n}\n"
    )


def _fv_schemes(ddt_line: str) -> str:
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      fvSchemes;\n}\n"
        f"{ddt_line}\n"
        "    gradSchemes\n    {\n        default         Gauss linear;\n    }\n\n"
        "    divSchemes\n    {\n"
        "        default         none;\n"
        '        div(phi,U)      Gauss linear;\n        div(phi,k)      Gauss linear;\n'
        '        div(phi,omega)  Gauss linear;\n        div(phi,epsilon) Gauss linear;\n'
        "        div((nuEff*dev2(T(grad(U))))) Gauss linear;\n    }\n\n"
        "    laplacianSchemes\n    {\n        default         Gauss linear orthogonal;\n    }\n\n"
        "    interpolationSchemes\n    {\n        default         linear;\n    }\n\n"
        "    snGradSchemes\n    {\n        default         orthogonal;\n    }\n"
    )


def _fv_solution(application: str, steady: bool, thermal_model: str) -> str:
    solvers = (
        "    solvers\n    {\n        p\n        {\n"
        "            solver          GAMG;\n            tolerance       1e-06;\n"
        "            relTol          0.1;\n            smoother        GaussSeidel;\n        }\n\n"
        '        "(U|k|omega|epsilon)"\n        {\n'
        "            solver          smoothSolver;\n            smoother        GaussSeidel;\n"
        "            tolerance       1e-05;\n            relTol          0.1;\n        }\n"
    )
    if thermal_model == "CHT":
        solvers += (
            "\n        T\n        {\n            solver          smoothSolver;\n"
            "            smoother        GaussSeidel;\n            tolerance       1e-06;\n"
            "            relTol          0.1;\n        }\n"
        )
    solvers += "    }\n\n"
    if steady:
        algorithm = (
            "    SIMPLE\n    {\n        nNonOrthogonalCorrectors 0;\n"
            "        residualControl\n        {\n            p               1e-4;\n"
            "            U               1e-4;\n"
            '            "(k|omega|epsilon)" 1e-4;\n        }\n    }\n'
        )
    else:
        algorithm = (
            "    PISO\n    {\n        nCorrectors     2;\n        nNonOrthogonalCorrectors 0;\n"
            "    }\n"
        )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      fvSolution;\n}\n"
        f"{solvers}{algorithm}\n"
        "    relaxationFactors\n    {\n        equations\n        {\n"
        "            U               0.9;\n            k               0.7;\n"
        "            omega           0.7;\n        }\n    }\n"
        f"// application {application}\n"
    )


def _turbulence_properties(turbulence: str) -> str:
    if turbulence == "laminar":
        return (
            "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            "    class       dictionary;\n    object      turbulenceProperties;\n}\n"
            "simulationType  laminar;\n"
        )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      turbulenceProperties;\n}\n"
        "simulationType  RAS;\n\nRAS\n{\n"
        f"    RASModel        {turbulence};\n    turbulence      on;\n"
        "    printCoeffs     on;\n}\n"
    )


def _field_u(inlet_velocity: float) -> str:
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       volVectorField;\n    object      U;\n}\n"
        "dimensions      [0 1 -1 0 0 0 0];\n\n"
        f"internalField   uniform ({inlet_velocity:g} 0 0);\n\n"
        "boundaryField\n{\n    inlet\n    {\n        type            fixedValue;\n"
        f"        value           uniform ({inlet_velocity:g} 0 0);\n    }}\n"
        "    outlet\n    {\n        type            zeroGradient;\n    }\n"
        "    walls\n    {\n        type            noSlip;\n    }\n}\n"
    )


def _field_p(outlet_pressure: float) -> str:
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       volScalarField;\n    object      p;\n}\n"
        "dimensions      [0 2 -2 0 0 0 0];\n\n"
        f"internalField   uniform {outlet_pressure:g};\n\n"
        "boundaryField\n{\n    inlet\n    {\n        type            zeroGradient;\n    }\n"
        "    outlet\n    {\n        type            fixedValue;\n"
        f"        value           uniform {outlet_pressure:g};\n    }}\n"
        "    walls\n    {\n        type            zeroGradient;\n    }\n}\n"
    )


def _field_t(temperature: float) -> str:
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       volScalarField;\n    object      T;\n}\n"
        "dimensions      [0 0 0 1 0 0 0];\n\n"
        f"internalField   uniform {temperature:g};\n\n"
        "boundaryField\n{\n    inlet\n    {\n        type            fixedValue;\n"
        f"        value           uniform {temperature:g};\n    }}\n"
        "    outlet\n    {\n        type            zeroGradient;\n    }\n"
        "    walls\n    {\n        type            zeroGradient;\n    }\n}\n"
    )


def parse_case_result(case_dir: Path) -> ParseReceipt:
    """Parse solver.log plus pressure probes into typed scalars."""

    log_path = case_dir / "solver.log"
    if not log_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver.log is missing")
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"solver.log unreadable:{exc}"
        ) from exc
    residuals = _parse_residuals(log_text)
    continuity = _parse_continuity(log_text)
    completed = any(line.strip() == "End" for line in log_text.splitlines())
    if not completed:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver log has no End marker")
    pressure_drop = _parse_probe_drop(case_dir)
    scalars = {
        "pressure_drop_pa": pressure_drop,
        "continuity_error": continuity,
    }
    for field, value in sorted(residuals.items()):
        scalars[f"residual_{field}"] = value
    return ParseReceipt(
        participant_id="openfoam",
        parser="openfoam.case:parse_case_result",
        scalars=scalars,
        units={name: ("Pa" if name == "pressure_drop_pa" else "dimensionless") for name in scalars},
        detail=f"steps parsed; completed={completed}",
    )


def _parse_residuals(log_text: str) -> dict[str, float]:
    import re

    pattern = re.compile(
        r"Solving for (\w+), Initial residual = ([0-9.eE+-]+), Final residual = ([0-9.eE+-]+)"
    )
    finals: dict[str, float] = {}
    for match in pattern.finditer(log_text):
        try:
            finals[match.group(1)] = float(match.group(3))
        except ValueError:
            continue
    if not finals:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "no solver residuals in log")
    return finals


def _parse_continuity(log_text: str) -> float:
    import re

    pattern = re.compile(
        r"time step continuity errors : sum local = ([0-9.eE+-]+),\s*global = ([0-9.eE+-]+)"
    )
    values: list[float] = []
    for match in pattern.finditer(log_text):
        try:
            values.append(float(match.group(2)))
        except ValueError:
            continue
    if not values:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "no continuity errors in log")
    return values[-1]


def _parse_probe_drop(case_dir: Path) -> float:
    probes = sorted((case_dir / "postProcessing" / "probes").glob("*"))
    if not probes:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "no probe output directory")
    latest = sorted(probes, key=lambda path: path.name)[-1]
    target = latest / "p"
    if not target.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "probe file p is missing")
    rows: list[tuple[float, float]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        head, _, tail = stripped.partition("(")
        values = tail.rstrip(")").split()
        if len(values) < 2:
            continue
        try:
            rows.append((float(values[0]), float(values[1])))
        except ValueError:
            continue
    if not rows:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "probe file has no samples")
    return rows[-1][0] - rows[-1][1]


def validate_case_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    continuity = float(scalars.get("continuity_error", float("nan")))
    pressure_drop = float(scalars.get("pressure_drop_pa", float("nan")))
    residual_keys = sorted(key for key in scalars if key.startswith("residual_"))
    residual_ok = bool(residual_keys) and all(scalars[key] < 1e-3 for key in residual_keys)
    checks = {
        "continuity": continuity == continuity and continuity < 1e-6,
        "residuals": residual_ok,
        "pressure_drop_positive": pressure_drop == pressure_drop and pressure_drop >= 0,
    }
    _ = inputs
    return ValidityReport(
        participant_id="openfoam",
        passed=all(checks.values()),
        checks=checks,
        detail="continuity<1e-6, residuals<1e-3, non-negative pressure drop",
    )
