"""Native Elmer thermal case generation from governed meshes and materials.

The case builder ingests the GEN 05 solver-mesh mapping (semantic zones,
patches, interfaces, and material regions) plus a real Gmsh ``.msh`` file. It
emits an Elmer ``.sif`` with one Body per semantic material group, material
properties mapped from immutable revisions, body heat sources, fixed
temperature / surface heat-flux / convection boundary conditions, and
interface temperature/heat-flux exchange. Steady and transient analyses share
one renderer. Nothing is executed here; execution stays capability-gated.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import PrepareReceipt

from .materials import ElmerMaterial, map_materials, material_digest

ANALYSES = ("steady", "transient")
INTERFACE_MODES = ("temperature", "heat_flux", "convection")


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _mesh_fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.MESH_INVALID, detail)


def _require_float(source: Mapping[str, Any], name: str, *, positive: bool = False) -> float:
    value = source.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise _fail(f"{name} must be finite")
    if positive and result <= 0:
        raise _fail(f"{name} must be positive")
    return result


def _require_str(source: Mapping[str, Any], name: str) -> str:
    value = source.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{name} must be a non-empty string")
    return value


def _require_mapping(source: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = source.get(name)
    if not isinstance(value, Mapping):
        raise _fail(f"{name} must be a mapping")
    return value


def _require_sequence(source: Mapping[str, Any], name: str) -> Sequence[Any]:
    value = source.get(name, ())
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _fail(f"{name} must be a sequence")
    for item in value:
        if not isinstance(item, Mapping):
            raise _fail(f"{name} entries must be mappings")
    return value


# -- mesh ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ElmerZone:
    name: str
    motion: str
    domain: str


@dataclass(frozen=True, slots=True)
class ElmerPatch:
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class ElmerInterface:
    name: str
    kind: str
    zone_a: str
    zone_b: str


@dataclass(frozen=True, slots=True)
class ElmerMesh:
    mesh_file: str
    mesh_hash: str
    geometry_hash: str | None
    mapping_hash: str
    zones: tuple[ElmerZone, ...]
    patches: tuple[ElmerPatch, ...]
    interfaces: tuple[ElmerInterface, ...]
    # (region name, material name) pairs from semantic material groups.
    material_regions: tuple[tuple[str, str], ...]

    @property
    def material_names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(name for _, name in self.material_regions))


def _parse_msh_physical_names(text: str) -> set[str]:
    """Return every physical-group name declared by an ASCII Gmsh mesh."""

    names: set[str] = set()
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "$PhysicalNames":
            in_section = True
            continue
        if stripped == "$EndPhysicalNames":
            in_section = False
            continue
        if not in_section or not stripped:
            continue
        quoted = stripped.split('"')
        if len(quoted) >= 2 and quoted[1].strip():
            names.add(quoted[1])
    return names


def _extract_elmer_export(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if "exports" in payload:
        exports = payload.get("exports")
        if not isinstance(exports, Sequence):
            raise _mesh_fail("mesh_mapping exports must be a sequence")
        for export in exports:
            if isinstance(export, Mapping) and export.get("participant") == "elmer":
                return export
        raise _mesh_fail("mesh_mapping has no elmer export")
    if payload.get("participant") == "elmer":
        return payload
    raise _mesh_fail("mesh_mapping is not an elmer export")


def _strings(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key, ())
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _mesh_fail(f"mesh export {key} must be a sequence")
    entries: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise _mesh_fail(f"mesh export {key} entries must be mappings")
        entries.append(item)
    return entries


def load_elmer_mesh(inputs: Mapping[str, Any], case_dir: Path) -> ElmerMesh:
    """Ingest a governed solver mesh and verify its semantic groups exist."""

    raw_mapping = inputs.get("mesh_mapping")
    if raw_mapping is None and isinstance(inputs.get("mesh_mapping_path"), str):
        mapping_path = Path(str(inputs["mesh_mapping_path"]))
        if not mapping_path.is_absolute():
            mapping_path = case_dir / mapping_path
        if not mapping_path.is_file():
            raise _mesh_fail(f"mesh mapping file missing:{mapping_path}")
        try:
            raw_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _mesh_fail(f"mesh mapping unreadable:{exc}") from exc
    if not isinstance(raw_mapping, Mapping):
        raise _mesh_fail("mesh_mapping is required for a native thermal case")
    export = _extract_elmer_export(raw_mapping)

    provenance = raw_mapping.get("provenance") if "exports" in raw_mapping else {}
    provenance = provenance if isinstance(provenance, Mapping) else {}

    zones = tuple(
        ElmerZone(
            _require_str(entry, "name"),
            str(entry.get("motion", "stationary")),
            str(entry.get("domain", "solid")),
        )
        for entry in _strings(export, "zones")
    )
    patches = tuple(
        ElmerPatch(_require_str(entry, "name"), str(entry.get("kind", "wall")))
        for entry in _strings(export, "patches")
    )
    interfaces = tuple(
        ElmerInterface(
            _require_str(entry, "name"),
            str(entry.get("kind", "interface")),
            _require_str(entry, "zoneA"),
            _require_str(entry, "zoneB"),
        )
        for entry in _strings(export, "interfaces")
    )
    material_regions = tuple(
        (_require_str(entry, "name"), _require_str(entry, "material"))
        for entry in _strings(export, "materials")
    )
    if not zones:
        raise _mesh_fail("mesh export declares no zones")

    mesh_file = str(inputs.get("mesh_file", "domain.msh"))
    mesh_source = inputs.get("mesh_source")
    if isinstance(mesh_source, str) and mesh_source.strip():
        source_path = Path(mesh_source)
        if not source_path.is_file():
            raise _mesh_fail(f"mesh source missing:{source_path}")
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / mesh_file).write_bytes(source_path.read_bytes())
    mesh_path = case_dir / mesh_file
    if not mesh_path.is_file():
        raise _mesh_fail(f"mesh file missing in case directory:{mesh_file}")
    physical_names = _parse_msh_physical_names(
        mesh_path.read_text(encoding="utf-8", errors="replace")
    )
    if not physical_names:
        raise _mesh_fail("mesh has no $PhysicalNames section")
    required = {zone.name for zone in zones}
    required |= {patch.name for patch in patches}
    required |= {interface.name for interface in interfaces}
    required |= {f"material_{name}" for name, _ in material_regions}
    missing = sorted(required - physical_names)
    if missing:
        raise _mesh_fail(f"MESH_GROUP_MISSING:{','.join(missing)}")

    mesh_hash = _observed_hash(inputs.get("mesh_hash")) or hashlib.sha256(
        mesh_path.read_bytes()
    ).hexdigest()
    geometry_hash = _observed_hash(inputs.get("geometry_hash")) or _observed_hash(
        provenance.get("geometryHash")
    )
    mapping_hash = hashlib.sha256(
        json.dumps(export, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ElmerMesh(
        mesh_file=mesh_file,
        mesh_hash=mesh_hash,
        geometry_hash=geometry_hash,
        mapping_hash=mapping_hash,
        zones=zones,
        patches=patches,
        interfaces=interfaces,
        material_regions=material_regions,
    )


def _observed_hash(value: Any) -> str | None:
    if (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    ):
        return value
    return None


# -- loads and boundary conditions ----------------------------------------


@dataclass(frozen=True, slots=True)
class HeatSource:
    body: str
    volumetric_w_m3: float


@dataclass(frozen=True, slots=True)
class FixedTemperature:
    patch: str
    temperature_k: float


@dataclass(frozen=True, slots=True)
class SurfaceHeatFlux:
    patch: str
    heat_flux_w_m2: float


@dataclass(frozen=True, slots=True)
class Convection:
    patch: str
    coefficient_w_m2_k: float
    ambient_k: float


@dataclass(frozen=True, slots=True)
class InterfaceExchange:
    interface: str
    mode: str
    value: float
    coefficient_w_m2_k: float | None = None
    ambient_k: float | None = None


@dataclass(frozen=True, slots=True)
class ThermalCase:
    analysis: str
    mesh: ElmerMesh
    bodies: tuple[str, ...]
    body_materials: tuple[str, ...]
    materials: dict[str, ElmerMaterial]
    heat_sources: tuple[HeatSource, ...]
    fixed_temperatures: tuple[FixedTemperature, ...]
    surface_heat_fluxes: tuple[SurfaceHeatFlux, ...]
    convections: tuple[Convection, ...]
    interface_exchanges: tuple[InterfaceExchange, ...]
    time_step_s: float | None
    end_time_s: float | None
    output_intervals: int
    energy_balance_tolerance: float
    ambient_k: float | None = field(default=None)

    @property
    def total_heat_input_w(self) -> float:
        return sum(source.volumetric_w_m3 for source in self.heat_sources)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis,
            "meshHash": self.mesh.mesh_hash,
            "geometryHash": self.mesh.geometry_hash,
            "mappingHash": self.mesh.mapping_hash,
            "bodies": list(self.bodies),
            "bodyMaterials": list(self.body_materials),
            "materials": [
                self.materials[name].canonical_payload() for name in self.body_materials
            ],
            "heatSources": [
                {"body": source.body, "volumetricWm3": source.volumetric_w_m3}
                for source in self.heat_sources
            ],
            "fixedTemperatures": [
                {"patch": bc.patch, "temperatureK": bc.temperature_k}
                for bc in self.fixed_temperatures
            ],
            "surfaceHeatFluxes": [
                {"patch": bc.patch, "heatFluxWm2": bc.heat_flux_w_m2}
                for bc in self.surface_heat_fluxes
            ],
            "convections": [
                {
                    "patch": bc.patch,
                    "coefficientWm2K": bc.coefficient_w_m2_k,
                    "ambientK": bc.ambient_k,
                }
                for bc in self.convections
            ],
            "interfaceExchanges": [
                {
                    "interface": exchange.interface,
                    "mode": exchange.mode,
                    "value": exchange.value,
                    "coefficientWm2K": exchange.coefficient_w_m2_k,
                    "ambientK": exchange.ambient_k,
                }
                for exchange in self.interface_exchanges
            ],
            "timeStepS": self.time_step_s,
            "endTimeS": self.end_time_s,
            "outputIntervals": self.output_intervals,
            "energyBalanceTolerance": self.energy_balance_tolerance,
            "ambientK": self.ambient_k,
        }


def _resolve_bodies(mesh: ElmerMesh) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if mesh.material_regions:
        bodies: list[str] = []
        materials: list[str] = []
        for region_name, material_name in mesh.material_regions:
            bodies.append(region_name)
            materials.append(material_name)
        return tuple(bodies), tuple(materials)
    solid_zones = [zone.name for zone in mesh.zones if zone.domain == "solid"]
    if not solid_zones:
        raise _fail("THERMAL_CASE_NEEDS_SOLID_BODY")
    return tuple(solid_zones), tuple(solid_zones)


def _parse_heat_sources(
    inputs: Mapping[str, Any], bodies: tuple[str, ...]
) -> tuple[HeatSource, ...]:
    sources: list[HeatSource] = []
    known = set(bodies)
    for entry in _require_sequence(inputs, "heat_sources"):
        body = _require_str(entry, "body")
        if body not in known:
            raise _fail(f"HEAT_SOURCE_UNKNOWN_BODY:{body}")
        if "volumetric_w_m3" in entry:
            density = _require_float(entry, "volumetric_w_m3")
        elif "power_w" in entry and "volume_m3" in entry:
            density = _require_float(entry, "power_w") / _require_float(
                entry, "volume_m3", positive=True
            )
        else:
            raise _fail(f"HEAT_SOURCE_NEEDS_VOLUMETRIC:{body}")
        if density < 0:
            raise _fail(f"HEAT_SOURCE_NEGATIVE:{body}")
        sources.append(HeatSource(body, density))
    return tuple(sources)


def _parse_boundary_conditions(
    inputs: Mapping[str, Any], patches: tuple[str, ...], interfaces: tuple[str, ...]
) -> tuple[
    tuple[FixedTemperature, ...],
    tuple[SurfaceHeatFlux, ...],
    tuple[Convection, ...],
    tuple[InterfaceExchange, ...],
]:
    known_patches = set(patches)
    known_interfaces = set(interfaces)
    fixed: list[FixedTemperature] = []
    for entry in _require_sequence(inputs, "fixed_temperature"):
        patch = _require_str(entry, "patch")
        if patch not in known_patches:
            raise _fail(f"FIXED_TEMPERATURE_UNKNOWN_PATCH:{patch}")
        temperature = _require_float(entry, "temperature_k", positive=True)
        fixed.append(FixedTemperature(patch, temperature))
    fluxes: list[SurfaceHeatFlux] = []
    for entry in _require_sequence(inputs, "surface_heat_flux"):
        patch = _require_str(entry, "patch")
        if patch not in known_patches:
            raise _fail(f"SURFACE_HEAT_FLUX_UNKNOWN_PATCH:{patch}")
        fluxes.append(SurfaceHeatFlux(patch, _require_float(entry, "heat_flux_w_m2")))
    convections: list[Convection] = []
    for entry in _require_sequence(inputs, "convection"):
        patch = _require_str(entry, "patch")
        if patch not in known_patches:
            raise _fail(f"CONVECTION_UNKNOWN_PATCH:{patch}")
        convections.append(
            Convection(
                patch,
                _require_float(entry, "coefficient_w_m2_k", positive=True),
                _require_float(entry, "ambient_k", positive=True),
            )
        )
    exchanges: list[InterfaceExchange] = []
    for entry in _require_sequence(inputs, "interface_exchange"):
        interface = _require_str(entry, "interface")
        if interface not in known_interfaces:
            raise _fail(f"INTERFACE_EXCHANGE_UNKNOWN_INTERFACE:{interface}")
        mode = _require_str(entry, "mode")
        if mode not in INTERFACE_MODES:
            raise _fail(f"INTERFACE_EXCHANGE_MODE:{mode}")
        value = _require_float(entry, "value")
        coefficient = (
            _require_float(entry, "coefficient_w_m2_k", positive=True)
            if mode == "convection"
            else None
        )
        ambient = (
            _require_float(entry, "ambient_k", positive=True)
            if mode == "convection"
            else None
        )
        exchanges.append(InterfaceExchange(interface, mode, value, coefficient, ambient))
    return tuple(fixed), tuple(fluxes), tuple(convections), tuple(exchanges)


def build_thermal_case(inputs: Mapping[str, Any], case_dir: Path) -> ThermalCase:
    data: Mapping[str, Any] = dict(inputs)
    analysis = data.get("analysis", "steady")
    if analysis not in ANALYSES:
        raise _fail(f"ANALYSIS must be one of {sorted(ANALYSES)}")
    mesh = load_elmer_mesh(data, case_dir)
    bodies, body_materials = _resolve_bodies(mesh)

    material_payloads = _require_mapping(data, "materials")
    resolved: dict[str, ElmerMaterial] = {}
    for body, material_name in zip(bodies, body_materials, strict=True):
        payload = material_payloads.get(material_name)
        if payload is None:
            payload = material_payloads.get(body)
        if payload is None:
            raise _fail(f"MATERIAL_PROPERTIES_MISSING:{body}:{material_name}")
        if material_name not in resolved:
            resolved[material_name] = map_materials({material_name: payload})[material_name]

    heat_sources = _parse_heat_sources(data, bodies)
    fixed, fluxes, convections, exchanges = _parse_boundary_conditions(
        data, tuple(p.name for p in mesh.patches), tuple(i.name for i in mesh.interfaces)
    )

    time_step = None
    end_time = None
    if analysis == "transient":
        time_step = _require_float(data, "time_step_s", positive=True)
        end_time = _require_float(data, "end_time_s", positive=True)
        if end_time <= time_step:
            raise _fail("TRANSIENT_END_TIME_MUST_EXCEED_STEP")
    intervals_raw = data.get("output_intervals", 1)
    if isinstance(intervals_raw, bool) or not isinstance(intervals_raw, int) or intervals_raw < 1:
        raise _fail("output_intervals must be a positive integer")
    tolerance = data.get("energy_balance_tolerance", 1.0e-3)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance <= 0:
        raise _fail("energy_balance_tolerance must be positive")

    return ThermalCase(
        analysis=analysis,
        mesh=mesh,
        bodies=bodies,
        body_materials=body_materials,
        materials=resolved,
        heat_sources=heat_sources,
        fixed_temperatures=fixed,
        surface_heat_fluxes=fluxes,
        convections=convections,
        interface_exchanges=exchanges,
        time_step_s=time_step,
        end_time_s=end_time,
        output_intervals=int(intervals_raw),
        energy_balance_tolerance=float(tolerance),
        ambient_k=_require_float(data, "ambient_k", positive=True) if "ambient_k" in data else None,
    )


# -- SIF rendering ---------------------------------------------------------


def _boundary_index_map(case: ThermalCase) -> dict[str, int]:
    index: dict[str, int] = {}
    counter = 1
    for patch in case.mesh.patches:
        index[f"patch:{patch.name}"] = counter
        counter += 1
    for interface in case.mesh.interfaces:
        index[f"interface:{interface.name}"] = counter
        counter += 1
    return index


def render_thermal_sif(case: ThermalCase) -> str:
    """Render a steady or transient Elmer heat-conduction case."""

    lines: list[str] = [
        "Header",
        "  CHECK KEYWORDS Warn",
        f'  Mesh DB "." "{Path(case.mesh.mesh_file).stem}"',
        '  Include Path ""',
        '  Results Directory ""',
        "End",
        "",
        "Simulation",
        "  Max Output Level = 4",
        "  Coordinate System = Cartesian 3D",
    ]
    if case.analysis == "transient":
        assert case.time_step_s is not None and case.end_time_s is not None
        steps = max(1, int(round(case.end_time_s / case.time_step_s)))
        lines += [
            "  Simulation Type = Transient",
            f"  Timestep Sizes = {case.time_step_s:.6e}",
            f"  Timestep Intervals(1) = {steps}",
            f"  Output Intervals(1) = {case.output_intervals}",
        ]
    else:
        lines += [
            "  Simulation Type = Steady State",
            "  Steady State Max Iterations = 50",
        ]
    lines += [
        '  Output File = "case.result"',
        '  Post File = "case.vtu"',
        "End",
        "",
    ]

    source_by_body = {source.body: source for source in case.heat_sources}
    material_index = {name: position for position, name in enumerate(case.materials, start=1)}
    for position, body in enumerate(case.bodies, start=1):
        material_name = case.body_materials[position - 1]
        index = material_index[material_name]
        lines += [
            f"Body {position}",
            f'  Name = "{body}"',
            "  Equation = 1",
            f"  Material = {index}",
        ]
        if body in source_by_body:
            lines.append(f"  Body Force = {position}")
        lines += ["End", ""]

    for position, body in enumerate(case.bodies, start=1):
        source = source_by_body.get(body)
        if source is None:
            continue
        lines += [
            f"Body Force {position}",
            f'  Name = "heat-source-{body}"',
            f"  Heat Source = {source.volumetric_w_m3:.6e}",
            "End",
            "",
        ]

    lines += [
        "Equation 1",
        '  Name = "HeatEquation"',
        "  Active Solvers(1) = 1",
        "End",
        "",
        "Solver 1",
        "  Equation = Heat Equation",
        '  Procedure = "HeatSolve" "HeatSolver"',
        "  Variable = Temperature",
        "  Exec Solver = Always",
        "  Stabilize = True",
        "  Bubbles = False",
        "  Lumped Mass Matrix = False",
        "  Optimize Bandwidth = True",
        "  Steady State Convergence Tolerance = 1.0e-6",
        "  Nonlinear System Convergence Tolerance = 1.0e-6",
        "  Nonlinear System Max Iterations = 20",
        "  Nonlinear System Newton After Iterations = 3",
        "  Nonlinear System Newton After Tolerance = 1.0e-3",
        "  Nonlinear System Relaxation Factor = 1",
        "  Linear System Solver = Iterative",
        "  Linear System Iterative Method = BiCGStab",
        "  Linear System Preconditioning = ILUT",
        "  Linear System Max Iterations = 500",
        "  Linear System Convergence Tolerance = 1.0e-7",
    ]
    if case.analysis == "transient":
        lines.append("  Transient = True")
    lines += ["End", ""]

    lines += [
        "Solver 2",
        "  Equation = SaveScalars",
        '  Procedure = "SaveData" "SaveScalars"',
        '  Filename = "result.dat"',
        "  Variable 1 = Temperature",
        "  Operator 1 = max",
        "  Variable 2 = Temperature",
        "  Operator 2 = min",
        "  Variable 3 = Temperature",
        "  Operator 3 = mean",
        "  Variable 4 = Heat Flux",
        "  Operator 4 = max",
        "  Variable 5 = Heat Flux",
        "  Operator 5 = min",
        "End",
        "",
    ]

    solver_index = 3
    for position, body in enumerate(case.bodies, start=1):
        lines += [
            f"Solver {solver_index}",
            "  Equation = SaveScalars",
            '  Procedure = "SaveData" "SaveScalars"',
            f'  Filename = "region_{body}.dat"',
            "  Variable 1 = Temperature",
            "  Operator 1 = max",
            "  Variable 2 = Temperature",
            "  Operator 2 = min",
            f"  Target Bodies(1) = {position}",
            "End",
            "",
        ]
        solver_index += 1

    boundary_index = _boundary_index_map(case)
    for interface in case.mesh.interfaces:
        target = boundary_index[f"interface:{interface.name}"]
        lines += [
            f"Solver {solver_index}",
            "  Equation = SaveScalars",
            '  Procedure = "SaveData" "SaveScalars"',
            f'  Filename = "interface_{interface.name}.dat"',
            "  Variable 1 = Temperature",
            "  Operator 1 = max",
            "  Variable 2 = Temperature",
            "  Operator 2 = min",
            "  Variable 3 = Temperature",
            "  Operator 3 = flux",
            f"  Target Boundaries(1) = {target}",
            "End",
            "",
        ]
        solver_index += 1

    for index, material_name in enumerate(case.materials, start=1):
        lines.append(case.materials[material_name].sif_block(index))
        lines.append("")

    bc_counter = 1
    for bc in case.fixed_temperatures:
        target = boundary_index[f"patch:{bc.patch}"]
        lines += [
            f"Boundary Condition {bc_counter}",
            f'  Name = "fixed-temperature-{bc.patch}"',
            f"  Target Boundaries(1) = {target}",
            f"  Temperature = {bc.temperature_k:.6e}",
            "End",
            "",
        ]
        bc_counter += 1
    for bc in case.surface_heat_fluxes:
        target = boundary_index[f"patch:{bc.patch}"]
        lines += [
            f"Boundary Condition {bc_counter}",
            f'  Name = "heat-flux-{bc.patch}"',
            f"  Target Boundaries(1) = {target}",
            f"  Heat Flux = {bc.heat_flux_w_m2:.6e}",
            "End",
            "",
        ]
        bc_counter += 1
    for bc in case.convections:
        target = boundary_index[f"patch:{bc.patch}"]
        lines += [
            f"Boundary Condition {bc_counter}",
            f'  Name = "convection-{bc.patch}"',
            f"  Target Boundaries(1) = {target}",
            f"  Heat Transfer Coefficient = {bc.coefficient_w_m2_k:.6e}",
            f"  External Temperature = {bc.ambient_k:.6e}",
            "End",
            "",
        ]
        bc_counter += 1
    for exchange in case.interface_exchanges:
        target = boundary_index[f"interface:{exchange.interface}"]
        lines += [
            f"Boundary Condition {bc_counter}",
            f'  Name = "interface-{exchange.mode}-{exchange.interface}"',
            f"  Target Boundaries(1) = {target}",
        ]
        if exchange.mode == "temperature":
            lines.append(f"  Temperature = {exchange.value:.6e}")
        elif exchange.mode == "heat_flux":
            lines.append(f"  Heat Flux = {exchange.value:.6e}")
        else:
            assert exchange.coefficient_w_m2_k is not None and exchange.ambient_k is not None
            lines.append(
                f"  Heat Transfer Coefficient = {exchange.coefficient_w_m2_k:.6e}"
            )
            lines.append(f"  External Temperature = {exchange.ambient_k:.6e}")
        lines += ["End", ""]
        bc_counter += 1
    return "\n".join(lines)


def prepare_native_thermal(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Build a native Elmer thermal case; returns the governed prepare receipt."""

    case = build_thermal_case(dict(inputs), case_dir)
    sif = render_thermal_sif(case)
    canonical = case.canonical_payload()
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.sif").write_text(sif, encoding="utf-8")
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "native": True,
                "analysis": case.analysis,
                "mesh": {
                    "meshHash": case.mesh.mesh_hash,
                    "geometryHash": case.mesh.geometry_hash,
                    "mappingHash": case.mesh.mapping_hash,
                    "meshFile": case.mesh.mesh_file,
                },
                "bodies": list(case.bodies),
                "bodyMaterials": list(case.body_materials),
                "materialDigest": material_digest(case.materials),
                "materialNames": list(case.materials),
                "patches": [patch.name for patch in case.mesh.patches],
                "interfaces": [
                    {
                        "name": interface.name,
                        "kind": interface.kind,
                        "zoneA": interface.zone_a,
                        "zoneB": interface.zone_b,
                    }
                    for interface in case.mesh.interfaces
                ],
                "totalHeatInputW": case.total_heat_input_w,
                "energyBalanceTolerance": case.energy_balance_tolerance,
                "canonical": canonical,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return PrepareReceipt(
        participant_id="elmer",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.sif", "case.json"),
        geometry_hash=case.mesh.geometry_hash,
        mesh_hash=case.mesh.mesh_hash,
        detail=(
            f"analysis={case.analysis} bodies={len(case.bodies)} "
            f"interfaces={len(case.mesh.interfaces)}"
        ),
    )
