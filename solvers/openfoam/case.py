"""Real OpenFOAM case construction, log parsing, and result validation.

The writer consumes a *governed* mesh artifact + semantic mapping (GEN 05)
when one is declared, and otherwise reproduces the legacy single-region
placeholder for backwards compatibility. Domain/boundary identities arrive as
plain patch/zone names; no application-specific geometry is assumed.

Execution stays fail-closed behind the governed runner when no OpenFOAM binary
is present. Validity is decided from parsed physics (residual stabilization,
bounded continuity, declared time coverage), never from an exit code alone.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport

from .mesh_ingest import GovernedMesh, ingest_governed_mesh

COMPRESSIBILITY = ("incompressible", "compressible")
ROTATING = ("none", "MRF", "AMI")
THERMAL = ("isothermal", "CHT")
TURBULENCE = ("laminar", "kEpsilon", "kOmegaSST")
MAX_ROTATING_ZONES = 8

# Declared engineering outputs the case configures and the parser extracts.
RESULT_REQUESTS = (
    "probes",
    "force",
    "torque",
    "mass_flow",
    "pressure",
    "temperature",
    "residuals",
    "continuity",
)
CONVERGENCE_POLICIES = ("steady_stabilized", "periodic", "statistical")

_RPM_TO_RAD_S = 0.104719755
_STEADY_RESIDUAL_TOLERANCE = 1e-3
_STEADY_CONTINUITY_TOLERANCE = 1e-6
_TRANSIENT_CONTINUITY_TOLERANCE = 1e-4

_CASE_MANIFEST_NAME = "case_manifest.json"
_RESULT_META_NAME = "result.json"
_CONVERGENCE_RECEIPT_NAME = "convergence_receipt.json"
_HISTORIES_NAME = "histories.json"
_FIELD_REFS_NAME = "field_refs.json"

_ZONE_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)

# Legacy placeholder roles, used only when no governed mesh is declared.
_LEGACY_PATCHES: tuple[tuple[str, str], ...] = (
    ("inlet", "inlet"),
    ("outlet", "outlet"),
    ("walls", "wall"),
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


def _optional_str(inputs: Mapping[str, object], name: str) -> str | None:
    value = inputs.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"input {name} must be a non-empty string when present")
    return value


@dataclass(frozen=True, slots=True)
class RotatingZone:
    """One declared rotating cell zone with its own rate, axis, and origin."""

    name: str
    rate_rpm: float
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def omega_rad_s(self) -> float:
        return self.rate_rpm * _RPM_TO_RAD_S


@dataclass(frozen=True, slots=True)
class AmiPair:
    """A verified sliding/AMI interface pairing between two zones."""

    name: str
    zone_a: str
    zone_b: str
    master_patch: str
    slave_patch: str


def _vector3(value: object, label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise _fail(f"{label} must be a three-component vector")
    numbers: list[float] = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise _fail(f"{label} components must be numbers")
        number = float(component)
        if number != number or number in (float("inf"), float("-inf")):
            raise _fail(f"{label} components must be finite")
        numbers.append(number)
    return (numbers[0], numbers[1], numbers[2])


def _require_rotating_zones(data: Mapping[str, object]) -> list[RotatingZone] | None:
    """Validate an optional generic list of rotating zones.

    Each entry declares ``{"name": <cell-zone>, "rotation_rate_rpm": <rate>}``
    plus optional ``axis`` and ``origin`` vectors. Zone names are opaque
    cell-zone identifiers; rates/axes may differ per zone (counter-rotation is
    a negative rate or a reversed axis). Returns ``None`` when the caller
    declares no explicit zone list, so the legacy single-zone input applies.
    """

    raw = data.get("rotating_zones", None)
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= MAX_ROTATING_ZONES:
        raise _fail(f"rotating_zones must list 1..{MAX_ROTATING_ZONES} zones")
    zones: list[RotatingZone] = []
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
        axis = (
            _vector3(entry.get("axis"), f"rotating zone {name} axis")
            if entry.get("axis") is not None
            else (0.0, 0.0, 1.0)
        )
        if axis == (0.0, 0.0, 0.0):
            raise _fail(f"rotating zone {name} axis must be non-zero")
        origin = (
            _vector3(entry.get("origin"), f"rotating zone {name} origin")
            if entry.get("origin") is not None
            else (0.0, 0.0, 0.0)
        )
        zones.append(RotatingZone(name, rate_value, axis, origin))
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


def _clean_json(value: Any) -> Any:
    """Recursively convert tuples to lists so payloads hash deterministically."""

    if isinstance(value, Mapping):
        return {str(key): _clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json(item) for item in value]
    return value


def _require_result_requests(data: Mapping[str, object]) -> tuple[str, ...]:
    raw = data.get("result_requests", ())
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)) or not all(
        isinstance(item, str) for item in raw
    ):
        raise _fail("result_requests must be a list of output names")
    unknown = sorted({item for item in raw if item not in RESULT_REQUESTS})
    if unknown:
        raise _fail(f"unsupported result_requests:{','.join(unknown)}")
    return tuple(dict.fromkeys(str(item) for item in raw))


def _resolve_ami_pairs(
    data: Mapping[str, object], governed: GovernedMesh | None
) -> tuple[AmiPair, ...]:
    """Verify AMI/sliding interface pairing before any case is written."""

    explicit = data.get("ami_pairs")
    if explicit is not None:
        if not isinstance(explicit, (list, tuple)) or not explicit:
            raise _fail("ami_pairs must be a non-empty list")
        pairs: list[AmiPair] = []
        for entry in explicit:
            if not isinstance(entry, Mapping):
                raise _fail("each ami pair needs name, zone_a, zone_b, master, slave")
            pairs.append(
                AmiPair(
                    name=_text_field(entry, "name"),
                    zone_a=_text_field(entry, "zone_a"),
                    zone_b=_text_field(entry, "zone_b"),
                    master_patch=_text_field(entry, "master_patch"),
                    slave_patch=_text_field(entry, "slave_patch"),
                )
            )
        return tuple(pairs)
    if governed is None:
        raise _fail("AMI requires explicit ami_pairs or a governed mesh with interfaces")
    pairs = []
    for interface in governed.interfaces:
        zones = (governed.zone(interface.zone_a), governed.zone(interface.zone_b))
        if not any(zone.rotating for zone in zones):
            continue
        pairs.append(
            AmiPair(
                name=interface.name,
                zone_a=interface.zone_a,
                zone_b=interface.zone_b,
                master_patch=interface.name,
                slave_patch=f"{interface.name}Shadow",
            )
        )
    if not pairs:
        raise _fail("AMI requires at least one interface with a rotating zone")
    return tuple(pairs)


def _text_field(entry: Mapping[str, object], name: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"ami pair field {name} is required")
    return value


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
    result_requests = _require_result_requests(data)
    rotating_zones = _require_rotating_zones(data)
    if rotating_zones is not None and rotating_model not in {"MRF", "AMI"}:
        raise _fail("rotating_zones requires rotating_model=MRF or AMI")
    if rotating_model == "AMI" and steady:
        raise _fail("AMI relative motion requires a transient analysis (steady=false)")

    governed = _ingest_if_declared(data, rotating_model)
    zone_specs = _resolve_zone_specs(data, rotating_model, rotating_zones, governed)
    default_end = 500.0 if steady else 1.0
    end_time = _require_float(data, "end_time") if "end_time" in data else default_end
    if end_time <= 0:
        raise _fail("end_time must be positive")

    patches = (
        tuple((patch.name, patch.kind) for patch in governed.patches)
        if governed is not None
        else _LEGACY_PATCHES
    )
    ami_pairs = _resolve_ami_pairs(data, governed) if rotating_model == "AMI" else ()

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
            "rotation_rate_rpm": (zone_specs[0].rate_rpm if zone_specs else 0.0),
            "rotating_zones": (
                [
                    {
                        "name": zone.name,
                        "rotation_rate_rpm": zone.rate_rpm,
                        "axis": list(zone.axis),
                        "origin": list(zone.origin),
                    }
                    for zone in zone_specs
                ]
                if rotating_zones is not None
                else None
            ),
            "resolved_zones": [
                {
                    "name": zone.name,
                    "rotation_rate_rpm": zone.rate_rpm,
                    "axis": list(zone.axis),
                    "origin": list(zone.origin),
                }
                for zone in zone_specs
            ],
            "end_time": end_time,
            "result_requests": list(result_requests),
            "geometry_hash": governed.geometry_hash if governed else None,
            "mesh_hash": governed.mesh_hash if governed else None,
            "mesh_mapping_hash": governed.mapping_hash if governed else None,
        }
    )
    digest = _input_hash(canonical)

    nu = viscosity / density
    time_scheme = "steadyState" if steady else "Euler"
    ddt_line = f"    ddtSchemes\n    {{\n        default         {time_scheme};\n    }}\n"
    files = {
        "system/controlDict": _control_dict(
            application, end_time, steady, result_requests, patches, density
        ),
        "system/fvSchemes": _fv_schemes(ddt_line),
        "system/fvSolution": _fv_solution(application, steady, thermal_model),
        "constant/turbulenceProperties": _turbulence_properties(turbulence),
        "0/U": _field_u(inlet_velocity, patches, ami_pairs),
        "0/p": _field_p(outlet_pressure, patches, ami_pairs),
    }
    if compressibility == "incompressible":
        files["constant/transportProperties"] = (
            "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            "    class       dictionary;\n    object      transportProperties;\n}\n"
            f"nu              [0 2 -1 0 0 0 0] {nu:.6e};\n"
        )
    else:
        files["constant/thermophysicalProperties"] = _thermophysical_properties(viscosity)
    if rotating_model == "MRF":
        files["constant/MRFProperties"] = _mrf_properties(zone_specs, patches)
    if rotating_model == "AMI":
        files["constant/dynamicMeshDict"] = _dynamic_mesh_dict(zone_specs)
    if thermal_model == "CHT":
        files["0/T"] = _field_t(temperature, patches, ami_pairs)

    case_manifest = {
        "participant_id": str(data.get("participant_id", "incompressible-steady-flow")),
        "application": application,
        "compressibility": compressibility,
        "steady": steady,
        "rotating_model": rotating_model,
        "thermal_model": thermal_model,
        "turbulence": turbulence,
        "end_time": end_time,
        "result_requests": list(result_requests),
        "patches": [{"name": name, "kind": kind} for name, kind in patches],
        "zones": [
            {
                "name": zone.name,
                "motion": "rotating",
                "rotation_rate_rpm": zone.rate_rpm,
                "axis": list(zone.axis),
                "origin": list(zone.origin),
            }
            for zone in zone_specs
        ],
        "interfaces": [
            {
                "name": pair.name,
                "zone_a": pair.zone_a,
                "zone_b": pair.zone_b,
                "master_patch": pair.master_patch,
                "slave_patch": pair.slave_patch,
            }
            for pair in ami_pairs
        ],
        "geometry_hash": governed.geometry_hash if governed else None,
        "mesh_hash": governed.mesh_hash if governed else None,
        "mesh_mapping_hash": governed.mapping_hash if governed else None,
        "topology_digest": governed.topology_digest if governed else None,
        "governed_mesh": governed is not None,
        "input_hash": digest,
    }
    files[_CASE_MANIFEST_NAME] = json.dumps(case_manifest, indent=2, sort_keys=True)
    files[_RESULT_META_NAME] = json.dumps(
        {
            "case_manifest": _CASE_MANIFEST_NAME,
            "application": application,
            "geometry_hash": governed.geometry_hash if governed else None,
            "mesh_hash": governed.mesh_hash if governed else None,
            "mesh_mapping_hash": governed.mapping_hash if governed else None,
            "steady": steady,
            "rotating_model": rotating_model,
        },
        indent=2,
        sort_keys=True,
    )

    case_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for relative, text in files.items():
        target = case_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(relative)
    converted = _convert_governed_mesh(data, case_dir, governed)

    from participants.commands import register_case_executable

    register_case_executable(case_dir.name, application)
    return PrepareReceipt(
        participant_id=str(data.get("participant_id", "incompressible-steady-flow")),
        case_id=case_dir.name,
        input_hash=digest,
        files=tuple(sorted(written)),
        geometry_hash=governed.geometry_hash if governed else None,
        mesh_hash=governed.mesh_hash if governed else None,
        detail=(
            f"application={application} turbulence={turbulence}"
            + (f" mesh_conversion={converted}" if converted else "")
        ),
    )


_MESH_CONVERTERS = {"gmshToFoam": "gmshToFoam"}


def _convert_governed_mesh(
    data: Mapping[str, object], case_dir: Path, governed: GovernedMesh | None
) -> str | None:
    """Convert the governed Gmsh artifact into ``constant/polyMesh``.

    Only allowlisted converters run, and a declared conversion that cannot be
    performed (missing tool, missing governed mesh, or a failed conversion)
    fails closed instead of leaving a case with no mesh.
    """

    method = data.get("mesh_conversion")
    if method is None:
        return None
    if not isinstance(method, str) or method not in _MESH_CONVERTERS:
        raise _fail(f"unsupported mesh_conversion:{method!r}")
    tool = _MESH_CONVERTERS[method]
    resolved = shutil.which(tool)
    if resolved is None:
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE,
            f"mesh conversion tool {tool} is not installed",
        )
    if governed is None:
        raise _fail("mesh_conversion requires a governed mesh_artifact_dir")
    target = case_dir / "constant" / "polyMesh"
    if target.is_dir():
        return tool
    try:
        completed = subprocess.run(
            [resolved, str(governed.mesh_path)],
            cwd=case_dir,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"{tool} failed to start:{exc}"
        ) from exc
    if completed.returncode != 0 or not target.is_dir():
        tail = (completed.stderr or completed.stdout or "")[-500:]
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED,
            f"{tool} conversion failed rc={completed.returncode}:{tail}",
        )
    return tool


def _ingest_if_declared(
    data: Mapping[str, object],
    rotating_model: str,
) -> GovernedMesh | None:
    mesh_dir = data.get("mesh_artifact_dir")
    if mesh_dir is None:
        return None
    if not isinstance(mesh_dir, str) or not mesh_dir.strip():
        raise _fail("mesh_artifact_dir must be a non-empty path string")
    required_patches = data.get("required_patch_kinds", ("inlet", "outlet"))
    if not isinstance(required_patches, (list, tuple)) or not all(
        isinstance(item, str) for item in required_patches
    ):
        raise _fail("required_patch_kinds must be a list of role names")
    required_motions = data.get("required_zone_motions")
    if required_motions is None:
        required_motions = ("rotating",) if rotating_model in {"MRF", "AMI"} else ()
    if not isinstance(required_motions, (list, tuple)) or not all(
        isinstance(item, str) for item in required_motions
    ):
        raise _fail("required_zone_motions must be a list of motion names")
    return ingest_governed_mesh(
        Path(mesh_dir),
        expected_geometry_hash=_optional_str(data, "geometry_hash"),
        expected_mesh_hash=_optional_str(data, "mesh_hash"),
        required_patch_kinds=tuple(str(item) for item in required_patches),
        required_zone_motions=tuple(str(item) for item in required_motions),
        require_interfaces=rotating_model == "AMI",
    )


def _coerce_rate(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{label} must be a numeric rotation rate")
    rate = float(value)
    if rate != rate or rate in (float("inf"), float("-inf")):
        raise _fail(f"{label} must be a finite rotation rate")
    return rate


def _resolve_zone_specs(
    data: Mapping[str, object],
    rotating_model: str,
    explicit: list[RotatingZone] | None,
    governed: GovernedMesh | None,
) -> list[RotatingZone]:
    """Resolve rotating cell zones from an explicit list or a governed mesh.

    A mesh that carries rotating cell zones drives the zone list directly;
    per-zone rates/axes/origins come from ``rotation_rates_rpm``,
    ``rotation_axes``, and ``rotation_origins`` maps (or a single
    ``rotation_rate_rpm`` default). No rotor count or zone name is assumed.
    """

    if explicit is not None:
        return list(explicit)
    if rotating_model == "none":
        if governed is not None and governed.moving_zones():
            raise _fail("mesh declares rotating zones but rotating_model=none")
        return []
    if governed is not None:
        moving = governed.moving_zones()
        if not moving:
            raise _fail(f"{rotating_model} requires a rotating cell zone; mesh has none")
        rates = data.get("rotation_rates_rpm")
        if rates is not None and not isinstance(rates, Mapping):
            raise _fail("rotation_rates_rpm must map zone names to rates")
        axes = data.get("rotation_axes")
        if axes is not None and not isinstance(axes, Mapping):
            raise _fail("rotation_axes must map zone names to axis vectors")
        origins = data.get("rotation_origins")
        if origins is not None and not isinstance(origins, Mapping):
            raise _fail("rotation_origins must map zone names to origin vectors")
        default_rate = data.get("rotation_rate_rpm")
        zones: list[RotatingZone] = []
        for zone in moving:
            rate_value = (
                rates.get(zone.name)
                if isinstance(rates, Mapping) and zone.name in rates
                else default_rate
            )
            if rate_value is None:
                raise _fail(f"rotating zone {zone.name} has no declared rotation rate")
            axis = (0.0, 0.0, 1.0)
            if isinstance(axes, Mapping) and zone.name in axes:
                axis = _vector3(axes[zone.name], f"rotating zone {zone.name} axis")
            origin = (0.0, 0.0, 0.0)
            if isinstance(origins, Mapping) and zone.name in origins:
                origin = _vector3(
                    origins[zone.name], f"rotating zone {zone.name} origin"
                )
            zones.append(
                RotatingZone(zone.name, _coerce_rate(rate_value, zone.name), axis, origin)
            )
        return zones
    if rotating_model == "MRF":
        return [RotatingZone("rotor", _require_float(data, "rotation_rate_rpm"))]
    raise _fail("AMI requires explicit rotating zones or a governed mesh with interfaces")


# -- boundary conditions ----------------------------------------------------


def _ami_neighbour_map(ami_pairs: tuple[AmiPair, ...]) -> dict[str, str]:
    neighbours: dict[str, str] = {}
    for pair in ami_pairs:
        neighbours[pair.master_patch] = pair.slave_patch
        neighbours[pair.slave_patch] = pair.master_patch
    return neighbours


def _u_entry(name: str, kind: str, inlet_velocity: float, neighbour: str | None) -> str:
    if neighbour is not None:
        return (
            f"    {name}\n    {{\n        type            cyclicAMI;\n"
            f"        neighbourPatch  {neighbour};\n    }}\n"
        )
    if kind == "inlet":
        return (
            f"    {name}\n    {{\n        type            fixedValue;\n"
            f"        value           uniform ({inlet_velocity:g} 0 0);\n    }}\n"
        )
    if kind == "symmetry":
        return f"    {name}\n    {{\n        type            symmetryPlane;\n    }}\n"
    if kind == "periodic":
        return f"    {name}\n    {{\n        type            cyclic;\n    }}\n"
    if kind == "wall":
        return f"    {name}\n    {{\n        type            noSlip;\n    }}\n"
    return f"    {name}\n    {{\n        type            zeroGradient;\n    }}\n"


def _p_entry(
    name: str, kind: str, outlet_pressure: float, neighbour: str | None
) -> str:
    if neighbour is not None:
        return (
            f"    {name}\n    {{\n        type            cyclicAMI;\n"
            f"        neighbourPatch  {neighbour};\n    }}\n"
        )
    if kind == "outlet":
        return (
            f"    {name}\n    {{\n        type            fixedValue;\n"
            f"        value           uniform {outlet_pressure:g};\n    }}\n"
        )
    if kind == "symmetry":
        return f"    {name}\n    {{\n        type            symmetryPlane;\n    }}\n"
    if kind == "periodic":
        return f"    {name}\n    {{\n        type            cyclic;\n    }}\n"
    return f"    {name}\n    {{\n        type            zeroGradient;\n    }}\n"


def _t_entry(name: str, kind: str, temperature: float, neighbour: str | None) -> str:
    if neighbour is not None:
        return (
            f"    {name}\n    {{\n        type            cyclicAMI;\n"
            f"        neighbourPatch  {neighbour};\n    }}\n"
        )
    if kind == "inlet":
        return (
            f"    {name}\n    {{\n        type            fixedValue;\n"
            f"        value           uniform {temperature:g};\n    }}\n"
        )
    if kind == "symmetry":
        return f"    {name}\n    {{\n        type            symmetryPlane;\n    }}\n"
    if kind == "periodic":
        return f"    {name}\n    {{\n        type            cyclic;\n    }}\n"
    return f"    {name}\n    {{\n        type            zeroGradient;\n    }}\n"


def _field_u(
    inlet_velocity: float,
    patches: Sequence[tuple[str, str]],
    ami_pairs: tuple[AmiPair, ...],
) -> str:
    neighbours = _ami_neighbour_map(ami_pairs)
    entries = "".join(
        _u_entry(name, kind, inlet_velocity, neighbours.get(name))
        for name, kind in patches
    )
    entries += "".join(
        _u_entry(name, "interface", inlet_velocity, neighbour)
        for name, neighbour in neighbours.items()
        if name not in {patch for patch, _ in patches}
    )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       volVectorField;\n    object      U;\n}\n"
        "dimensions      [0 1 -1 0 0 0 0];\n\n"
        f"internalField   uniform ({inlet_velocity:g} 0 0);\n\n"
        f"boundaryField\n{{\n{entries}}}\n"
    )


def _field_p(
    outlet_pressure: float,
    patches: Sequence[tuple[str, str]],
    ami_pairs: tuple[AmiPair, ...],
) -> str:
    neighbours = _ami_neighbour_map(ami_pairs)
    entries = "".join(
        _p_entry(name, kind, outlet_pressure, neighbours.get(name))
        for name, kind in patches
    )
    entries += "".join(
        _p_entry(name, "interface", outlet_pressure, neighbour)
        for name, neighbour in neighbours.items()
        if name not in {patch for patch, _ in patches}
    )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       volScalarField;\n    object      p;\n}\n"
        "dimensions      [0 2 -2 0 0 0 0];\n\n"
        f"internalField   uniform {outlet_pressure:g};\n\n"
        f"boundaryField\n{{\n{entries}}}\n"
    )


def _field_t(
    temperature: float,
    patches: Sequence[tuple[str, str]],
    ami_pairs: tuple[AmiPair, ...],
) -> str:
    neighbours = _ami_neighbour_map(ami_pairs)
    entries = "".join(
        _t_entry(name, kind, temperature, neighbours.get(name)) for name, kind in patches
    )
    entries += "".join(
        _t_entry(name, "interface", temperature, neighbour)
        for name, neighbour in neighbours.items()
        if name not in {patch for patch, _ in patches}
    )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       volScalarField;\n    object      T;\n}\n"
        "dimensions      [0 0 0 1 0 0 0];\n\n"
        f"internalField   uniform {temperature:g};\n\n"
        f"boundaryField\n{{\n{entries}}}\n"
    )


# -- dictionaries -----------------------------------------------------------


def _control_dict(
    application: str,
    end_time: float,
    steady: bool,
    result_requests: tuple[str, ...],
    patches: Sequence[tuple[str, str]],
    density: float,
) -> str:
    delta_t = 1.0 if steady else 1e-4
    functions = _function_objects(result_requests, patches, density)
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
        "functions\n{\n" + functions + "}\n"
    )


def _function_objects(
    result_requests: tuple[str, ...],
    patches: Sequence[tuple[str, str]],
    density: float,
) -> str:
    """Build the controlDict function-object block for declared requests.

    The pressure-probes block is always emitted (golden legacy output). Every
    additional object is named after the semantic surface it samples so a
    parsed scalar can be traced back to the boundary that produced it.
    """

    entries = [
        "    pressureProbes\n    {\n"
        "        type            probes;\n"
        '        libs            ("libsampling.so");\n'
        "        writeControl    writeTime;\n        fields          (p);\n"
        "        probeLocations\n        (\n"
        "            (-0.45 0 0)\n            (0.45 0 0)\n"
        "        );\n    }\n"
    ]
    force_surfaces = tuple(
        name for name, kind in patches if kind == "wall"
    ) or tuple(name for name, _ in patches)
    for surface in force_surfaces if _wants_force(result_requests) else ():
        entries.append(_forces_object(surface, density))
    if "mass_flow" in result_requests:
        for name, kind in patches:
            if kind in {"inlet", "outlet"}:
                entries.append(_surface_value_object(f"massFlow_{name}", name, "phi", "sum"))
    if "pressure" in result_requests:
        for name, kind in patches:
            if kind in {"inlet", "outlet", "wall"}:
                entries.append(
                    _surface_value_object(f"areaAverage_p_{name}", name, "p", "areaAverage")
                )
    if "temperature" in result_requests:
        for name, kind in patches:
            if kind in {"inlet", "outlet", "wall"}:
                entries.append(
                    _surface_value_object(f"areaAverage_T_{name}", name, "T", "areaAverage")
                )
    if "residuals" in result_requests:
        entries.append(
            "    residuals\n    {\n"
            "        type            residuals;\n"
            '        libs            ("libutilityFunctionObjects.so");\n'
            "        writeControl    timeStep;\n        writeInterval   1;\n"
            "        fields          (U p);\n    }\n"
        )
    if "continuity" in result_requests:
        entries.append(
            "    continuityError\n    {\n"
            "        type            continuityError;\n"
            '        libs            ("libfieldFunctionObjects.so");\n'
            "        writeControl    timeStep;\n        writeInterval   1;\n    }\n"
        )
    return "".join(entries)


def _wants_force(result_requests: tuple[str, ...]) -> bool:
    return "force" in result_requests or "torque" in result_requests


def _forces_object(surface: str, density: float) -> str:
    return (
        f"    forces_{surface}\n    {{\n"
        "        type            forces;\n"
        '        libs            ("libforces.so");\n'
        "        writeControl    writeTime;\n"
        f"        patches         ({surface});\n"
        "        rho             rhoInf;\n"
        f"        rhoInf          {density:g};\n"
        "        CofR            (0 0 0);\n    }\n"
    )


def _surface_value_object(name: str, patch: str, field: str, operation: str) -> str:
    return (
        f"    {name}\n    {{\n"
        "        type            surfaceFieldValue;\n"
        '        libs            ("libfieldFunctionObjects.so");\n'
        "        writeControl    writeTime;\n"
        "        surfaceFormat   none;\n"
        "        regionType      patch;\n"
        f"        name            {patch};\n"
        f"        operation       {operation};\n"
        f"        fields          ({field});\n"
        f"        weightField     phi;\n    }}\n"
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


def _thermophysical_properties(viscosity: float) -> str:
    return (
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


def _mrf_properties(
    zone_specs: Sequence[RotatingZone], patches: Sequence[tuple[str, str]]
) -> str:
    non_rotating = " ".join(
        name for name, kind in patches if kind in {"inlet", "outlet"}
    ) or "inlet outlet"
    blocks = "".join(
        f"MRF{index + 1}\n{{\n    cellZone        {zone.name};\n"
        "    active          yes;\n"
        f"    nonRotatingPatches ({non_rotating});\n"
        f"    origin          ({zone.origin[0]:g} {zone.origin[1]:g} {zone.origin[2]:g});\n"
        f"    axis            ({zone.axis[0]:g} {zone.axis[1]:g} {zone.axis[2]:g});\n"
        f"    omega           constant {zone.omega_rad_s:.6f};\n"
        "}}\n"
        for index, zone in enumerate(zone_specs)
    )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      MRFProperties;\n}\n" + blocks
    )


def _dynamic_mesh_dict(zone_specs: Sequence[RotatingZone]) -> str:
    motions = "".join(
        f"    {zone.name}\n    {{\n"
        "        solidBodyMotionFunction rotatingMotion;\n"
        f"        origin          ({zone.origin[0]:g} {zone.origin[1]:g} {zone.origin[2]:g});\n"
        f"        axis            ({zone.axis[0]:g} {zone.axis[1]:g} {zone.axis[2]:g});\n"
        f"        omega           {zone.omega_rad_s:.6f};\n"
        "    }\n"
        for zone in zone_specs
    )
    return (
        "FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
        "    class       dictionary;\n    object      dynamicMeshDict;\n}\n"
        "dynamicFvMesh   dynamicMultiMotionSolverFvMesh;\n"
        'motionSolverLibs ("libfvMotionSolvers.so");\n'
        "solidBodyMotionSolver\n{\n" + motions + "}\n"
    )


# -- parsing ----------------------------------------------------------------


def _read_case_manifest(case_dir: Path) -> dict[str, Any]:
    target = case_dir / _CASE_MANIFEST_NAME
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_case_result(case_dir: Path) -> ParseReceipt:
    """Parse solver.log plus function-object output into typed scalars.

    Parsing is output-driven: forces/torque, mass flow, area-averaged
    pressure/temperature, and time histories are extracted only when the case
    declared them. A missing ``End`` marker or absent convergence evidence is
    a PARSER_FAILED, never a fabricated success.
    """

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

    manifest = _read_case_manifest(case_dir)
    requests = tuple(manifest.get("result_requests", ("probes",)))
    scalars: dict[str, float] = {
        "solver_completed": 1.0,
        "continuity_error": continuity,
    }
    units: dict[str, str] = {
        "solver_completed": "dimensionless",
        "continuity_error": "dimensionless",
    }
    pressure_drop = _parse_probe_drop(case_dir)
    if pressure_drop is not None:
        scalars["pressure_drop_pa"] = pressure_drop
        units["pressure_drop_pa"] = "Pa"
    elif "probes" in requests:
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "no probe output directory")
    for field, value in sorted(residuals.items()):
        scalars[f"residual_{field}"] = value
        units[f"residual_{field}"] = "dimensionless"

    forces = _parse_forces(case_dir)
    scalar_histories: dict[str, Any] = {}
    for surface, (force, moment) in sorted(forces.items()):
        tag = _sanitize(surface)
        magnitude = _vector_norm(force)
        scalars[f"force_{tag}_x"] = force[0]
        scalars[f"force_{tag}_y"] = force[1]
        scalars[f"force_{tag}_z"] = force[2]
        scalars[f"force_{tag}_n"] = magnitude
        for axis, value in zip("xyz", moment, strict=True):
            scalars[f"torque_{tag}_{axis}"] = value
        scalars[f"torque_{tag}_n_m"] = _vector_norm(moment)
        for key in (
            f"force_{tag}_x",
            f"force_{tag}_y",
            f"force_{tag}_z",
            f"force_{tag}_n",
        ):
            units[key] = "N"
        for key in (
            f"torque_{tag}_x",
            f"torque_{tag}_y",
            f"torque_{tag}_z",
            f"torque_{tag}_n_m",
        ):
            units[key] = "N.m"
        scalar_histories[f"forces_{tag}"] = {
            "force_n": magnitude,
            "torque_n_m": _vector_norm(moment),
            "source_patch": surface,
        }

    for name, value, unit in _parse_surface_values(case_dir):
        scalars[name] = value
        units[name] = unit
        scalar_histories[name] = {"value": value, "unit": unit}

    simulation_time = _parse_last_time(log_text)
    if simulation_time is not None:
        scalars["simulation_time_s"] = simulation_time
        units["simulation_time_s"] = "s"

    _write_json(
        case_dir / _CONVERGENCE_RECEIPT_NAME,
        {
            "participant_id": "openfoam",
            "solver_completed": completed,
            "continuity_error": continuity,
            "residuals": dict(sorted(residuals.items())),
            "simulation_time_s": simulation_time,
            "result_requests": list(requests),
            "geometry_hash": manifest.get("geometry_hash"),
            "mesh_hash": manifest.get("mesh_hash"),
            "input_hash": manifest.get("input_hash"),
        },
    )
    _write_json(
        case_dir / _HISTORIES_NAME,
        {
            "participant_id": "openfoam",
            "histories": scalar_histories,
            "geometry_hash": manifest.get("geometry_hash"),
            "mesh_hash": manifest.get("mesh_hash"),
        },
    )
    _write_json(
        case_dir / _FIELD_REFS_NAME,
        {
            "participant_id": "openfoam",
            "times": _field_time_refs(case_dir),
            "geometry_hash": manifest.get("geometry_hash"),
            "mesh_hash": manifest.get("mesh_hash"),
        },
    )
    return ParseReceipt(
        participant_id="openfoam",
        parser="openfoam.case:parse_case_result",
        scalars=scalars,
        units=units,
        detail=f"steps parsed; completed={completed}",
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(_clean_json(payload), indent=2, sort_keys=True), encoding="utf-8")


def _sanitize(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")


def _vector_norm(vector: tuple[float, float, float]) -> float:
    return (vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2) ** 0.5


def _parse_residuals(log_text: str) -> dict[str, float]:
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


def _parse_last_time(log_text: str) -> float | None:
    values: list[float] = []
    for match in re.finditer(r"^Time = ([0-9.eE+-]+)", log_text, flags=re.MULTILINE):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    return values[-1] if values else None


def _parse_probe_drop(case_dir: Path) -> float | None:
    probes = sorted((case_dir / "postProcessing" / "probes").glob("*"))
    if not probes:
        return None
    latest = sorted(probes, key=lambda path: _time_key(path.name))[-1]
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


def _time_key(name: str) -> float:
    try:
        return float(name)
    except ValueError:
        return 0.0


def _latest_dat(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    times = [entry for entry in directory.iterdir() if entry.is_dir()]
    if not times:
        return None
    latest = sorted(times, key=lambda entry: _time_key(entry.name))[-1]
    dats = sorted(latest.glob("*.dat"))
    return dats[0] if dats else None


_VECTOR_GROUP = re.compile(r"\(([^()]*)\)")


def _parse_forces(
    case_dir: Path,
) -> dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]]:
    post = case_dir / "postProcessing"
    if not post.is_dir():
        return {}
    forces: dict[
        str, tuple[tuple[float, float, float], tuple[float, float, float]]
    ] = {}
    for directory in sorted(post.iterdir()):
        if not directory.is_dir() or not directory.name.startswith("forces_"):
            continue
        target = _latest_dat(directory)
        if target is None:
            continue
        groups = _last_vector_groups(target)
        if not groups:
            continue
        if len(groups) >= 6:
            force = _sum_vectors(groups[0:3])
            moment = _sum_vectors(groups[3:6])
        elif len(groups) == 2:
            force = groups[0]
            moment = groups[1]
        else:
            force = groups[0]
            moment = (0.0, 0.0, 0.0)
        forces[directory.name[len("forces_") :]] = (force, moment)
    return forces


def _last_vector_groups(path: Path) -> list[tuple[float, float, float]]:
    last: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        groups: list[tuple[float, float, float]] = []
        for match in _VECTOR_GROUP.finditer(stripped):
            numbers = match.group(1).split()
            if len(numbers) != 3:
                groups = []
                break
            try:
                groups.append((float(numbers[0]), float(numbers[1]), float(numbers[2])))
            except ValueError:
                groups = []
                break
        if groups:
            last = groups
    return last


def _sum_vectors(
    vectors: Sequence[tuple[float, float, float]],
) -> tuple[float, float, float]:
    return (
        sum(vector[0] for vector in vectors),
        sum(vector[1] for vector in vectors),
        sum(vector[2] for vector in vectors),
    )


def _parse_surface_values(case_dir: Path) -> list[tuple[str, float, str]]:
    post = case_dir / "postProcessing"
    if not post.is_dir():
        return []
    parsed: list[tuple[str, float, str]] = []
    prefixes = (
        ("massFlow_", "mass_flow_", "kg/s"),
        ("areaAverage_p_", "area_average_p_", "Pa"),
        ("areaAverage_T_", "area_average_t_", "K"),
    )
    for directory in sorted(post.iterdir()):
        if not directory.is_dir():
            continue
        for prefix, scalar_prefix, unit in prefixes:
            if not directory.name.startswith(prefix):
                continue
            target = _latest_dat(directory)
            if target is None:
                continue
            value = _last_scalar(target)
            if value is None:
                continue
            surface = _sanitize(directory.name[len(prefix) :])
            parsed.append((f"{scalar_prefix}{surface}", value, unit))
    return parsed


def _last_scalar(path: Path) -> float | None:
    value: float | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens = stripped.replace("(", " ").replace(")", " ").split()
        for token in reversed(tokens):
            try:
                value = float(token)
                break
            except ValueError:
                continue
    return value


def _field_time_refs(case_dir: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for entry in sorted(case_dir.iterdir()):
        if not entry.is_dir() or not _is_time_name(entry.name):
            continue
        fields = sorted(
            path.name
            for path in entry.iterdir()
            if path.is_file() and path.name in {"U", "p", "T", "k", "omega", "epsilon"}
        )
        if fields:
            refs.append({"time": entry.name, "fields": fields})
    return refs


def _is_time_name(name: str) -> bool:
    return _time_key(name) != 0.0 or name == "0"


# -- validity ---------------------------------------------------------------


def validate_case_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """Physical validity: residual stabilization, bounded continuity, coverage.

    Exit status is never consulted. Steady cases require every residual below
    the stabilization tolerance and a bounded global continuity error.
    Transient cases additionally require a completed run and (when the
    analysis declares an end time) sufficient time coverage, plus any declared
    periodic/statistical convergence measure.
    """

    steady = inputs.get("steady", True)
    if not isinstance(steady, bool):
        steady = True
    completed = float(scalars.get("solver_completed", 0.0)) == 1.0
    continuity = float(scalars.get("continuity_error", float("nan")))
    residual_keys = sorted(key for key in scalars if key.startswith("residual_"))
    residual_ok = bool(residual_keys) and all(
        scalars[key] < _STEADY_RESIDUAL_TOLERANCE for key in residual_keys
    )
    continuity_tolerance = (
        _STEADY_CONTINUITY_TOLERANCE if steady else _TRANSIENT_CONTINUITY_TOLERANCE
    )
    checks: dict[str, bool] = {
        "solver_completed": completed,
        "continuity": continuity == continuity and continuity < continuity_tolerance,
        "residuals_stabilized": residual_ok,
    }
    if "pressure_drop_pa" in scalars:
        pressure_drop = float(scalars["pressure_drop_pa"])
        checks["pressure_drop_positive"] = pressure_drop == pressure_drop and pressure_drop >= 0
    if not steady:
        end_time = inputs.get("end_time")
        simulation_time = scalars.get("simulation_time_s")
        if isinstance(end_time, (int, float)) and not isinstance(end_time, bool):
            coverage = (
                float(simulation_time) / float(end_time)
                if simulation_time is not None and float(end_time) > 0
                else 0.0
            )
            checks["time_coverage"] = coverage >= float(
                inputs.get("min_time_coverage_fraction", 0.999)
            )
    policy = inputs.get("convergence_policy")
    if policy == "periodic":
        threshold = float(inputs.get("periodicity_tolerance", 1e-3))
        error = float(scalars.get("periodicity_error", float("nan")))
        checks["periodic_convergence"] = error == error and error <= threshold
    if policy == "statistical":
        threshold = float(inputs.get("statistical_tolerance", 1e-2))
        drift = float(scalars.get("statistical_drift", float("nan")))
        checks["statistical_convergence"] = drift == drift and drift <= threshold
    _assert_requested_outputs(scalars, inputs, checks)
    detail = (
        "completed + residual stabilization + bounded continuity"
        if steady
        else "completed + residual stabilization + bounded continuity + time coverage"
    )
    return ValidityReport(
        participant_id="openfoam",
        passed=all(checks.values()),
        checks=checks,
        detail=detail,
    )


def _assert_requested_outputs(
    scalars: Mapping[str, float],
    inputs: Mapping[str, object],
    checks: dict[str, bool],
) -> None:
    raw = inputs.get("result_requests")
    if not isinstance(raw, (list, tuple)):
        return
    requests = {str(item) for item in raw}
    if "force" in requests:
        checks["force_extracted"] = any(key.startswith("force_") for key in scalars)
    if "torque" in requests:
        checks["torque_extracted"] = any(key.startswith("torque_") for key in scalars)
    if "mass_flow" in requests:
        checks["mass_flow_extracted"] = any(key.startswith("mass_flow_") for key in scalars)


# Re-exported for callers that want to introspect a consumed artifact.
__all__ = [
    "AmiPair",
    "COMPRESSIBILITY",
    "CONVERGENCE_POLICIES",
    "GovernedMesh",
    "MAX_ROTATING_ZONES",
    "RESULT_REQUESTS",
    "ROTATING",
    "RotatingZone",
    "THERMAL",
    "TURBULENCE",
    "parse_case_result",
    "prepare_case_files",
    "select_application",
    "validate_case_result",
]
