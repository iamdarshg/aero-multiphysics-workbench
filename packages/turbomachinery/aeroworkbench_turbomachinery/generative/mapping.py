"""Resolve a canonical design state into a concrete rotating-gas architecture.

The same row plan drives both the canonical :class:`RotatingGasArchitecture`
(topology, spools, stations) and the TURBO 03 meanline stage, so topology changes
detected by the existing invalidation tables correspond to real architecture
deltas rather than a parallel notion of "topology".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..architecture import RotatingGasArchitecture
from ..components import GasPathEdge, GasPathNode
from ..meanline.design import MeanlineRow, StageDesign
from ..meanline.properties import IdealGas
from ..rows import BladeRow
from ..shafts import Shaft, ShaftCoupling, SpeedBound
from ..stations import Station, StationState
from ..units import Quantity
from .space import FAMILIES
from .spec import GenerativeSpec

__all__ = [
    "RowPlan",
    "architecture_from_state",
    "meanline_stage_from_state",
    "row_plan",
]

_AIR = IdealGas(cp_j_kg_k=1005.0, gamma=1.4, gas_constant_j_kg_k=287.05)

_ROLE_NODE_KIND = {
    "work_adding": "rotor_row",
    "work_extracting": "rotor_row",
    "turning_only": "stator_row",
    "diffuser_guide": "diffuser",
}


@dataclass(frozen=True, slots=True)
class RowPlan:
    """Resolved role/frame/family/spool for one independently-variable row."""

    index: int
    role: str
    frame: str
    family: str
    shaft_id: str | None

    @property
    def node_kind(self) -> str:
        return _ROLE_NODE_KIND[self.role]


def _index(space: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(variable["id"]): variable for variable in space.get("variables", ())}


def _base(index: Mapping[str, Mapping[str, Any]], variable_id: str) -> Any:
    variable = index.get(variable_id)
    if variable is None:
        return None
    return variable.get("baseValue")


def _raw(
    index: Mapping[str, Mapping[str, Any]], state: Mapping[str, Any], variable_id: str
) -> Any:
    entry = state.get(variable_id)
    if isinstance(entry, Mapping):
        kind = entry.get("kind")
        if kind in {"number", "dimensionless"}:
            return float(entry["value"])
        if kind == "categorical":
            return str(entry["value"])
        if kind == "boolean":
            return bool(entry["value"])
    return _base(index, variable_id)


def _number(
    index: Mapping[str, Mapping[str, Any]],
    state: Mapping[str, Any],
    variable_id: str,
    default: float,
) -> float:
    value = _raw(index, state, variable_id)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _flag(
    index: Mapping[str, Mapping[str, Any]], state: Mapping[str, Any], variable_id: str
) -> bool:
    return bool(_raw(index, state, variable_id))


def _choice(
    index: Mapping[str, Mapping[str, Any]],
    state: Mapping[str, Any],
    variable_id: str,
    default: str,
) -> str:
    value = _raw(index, state, variable_id)
    return value if isinstance(value, str) else default


def _profile_values(
    index: Mapping[str, Mapping[str, Any]],
    state: Mapping[str, Any],
    variable_id: str,
    count: int,
    default: float,
) -> tuple[float, ...]:
    variable = index.get(variable_id)
    control_ids: tuple[str, ...] = ()
    if variable is not None:
        points = variable["domain"].get("controlPoints", ())
        control_ids = tuple(str(point["id"]) for point in points)
    provided: dict[str, float] = {}
    entry = state.get(variable_id)
    if isinstance(entry, Mapping) and entry.get("kind") == "vector-profile":
        for point in entry.get("points", ()):
            provided[str(point["id"])] = float(point["value"])
    values: list[float] = []
    for position in range(max(count, 0)):
        point_id = control_ids[position] if position < len(control_ids) else ""
        values.append(provided.get(point_id, default))
    return tuple(values)


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _resolved_shafts(
    roles: Sequence[str],
    frames: Sequence[str],
    spool_count: int,
    free_power_turbine: bool,
) -> tuple[str | None, ...]:
    rotating = [position for position, frame in enumerate(frames) if frame == "rotating"]
    assignment: list[str | None] = [None] * len(roles)
    if not rotating:
        return tuple(assignment)
    if spool_count <= 1:
        for position in rotating:
            assignment[position] = "shaft0"
        return tuple(assignment)
    for order, position in enumerate(rotating):
        spool = min(spool_count - 1, order * spool_count // len(rotating))
        assignment[position] = f"shaft{spool}"
    if free_power_turbine:
        assignment[rotating[-1]] = f"shaft{spool_count - 1}"
    return tuple(assignment)


def row_plan(
    space: Mapping[str, Any], state: Mapping[str, Any], spec: GenerativeSpec
) -> tuple[RowPlan, ...]:
    """Resolve every row independently: role, frame, family, and spool binding."""

    index = _index(space)
    row_count = int(_clamp(round(_number(index, state, "row_count", 2.0)), 1, spec.max_rows))
    family = _choice(index, state, "family", "axial")
    if family not in FAMILIES:
        family = "axial"
    arrangement = _choice(index, state, "arrangement", "rotor_stator")
    machine_kind = _choice(index, state, "machine_kind", "work_adding")
    diffuser_type = _choice(index, state, "diffuser_type", "none")
    spool_count = int(_clamp(round(_number(index, state, "spool_count", 1.0)), 1, spec.max_spools))
    free_power_turbine = _flag(index, state, "free_power_turbine")

    rotating_role = "work_extracting" if machine_kind == "work_extracting" else "work_adding"
    roles: list[str] = []
    frames: list[str] = []
    for position in range(row_count):
        if arrangement == "stator_rotor":
            rotating = position % 2 == 1
        elif arrangement == "rotor_only":
            rotating = True
        else:
            rotating = position % 2 == 0
        roles.append(rotating_role if rotating else "turning_only")
        frames.append("rotating" if rotating else "stationary")
    if (
        family in ("radial", "mixed")
        and diffuser_type != "none"
        and machine_kind != "work_extracting"
        and row_count >= 1
    ):
        roles[-1] = "diffuser_guide"
        frames[-1] = "stationary"

    shafts = _resolved_shafts(roles, frames, spool_count, free_power_turbine)
    return tuple(
        RowPlan(
            index=position,
            role=roles[position],
            frame=frames[position],
            family=family,
            shaft_id=shafts[position],
        )
        for position in range(row_count)
    )


def _chain(plan: Sequence[RowPlan], heat_addition: bool, recuperator: bool,
           intercooler: bool, bypass_topology: str) -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = [("ambient", "ambient"), ("inlet", "inlet")]
    if intercooler:
        chain.append(("intercooler", "intercooler"))
    if bypass_topology != "none":
        chain.append(("splitter", "splitter"))
    for row in plan:
        chain.append((f"row{row.index}", row.node_kind))
    if heat_addition:
        chain.append(("combustor", "combustor"))
    if recuperator:
        chain.append(("recuperator", "recuperator"))
    if bypass_topology == "split_mix":
        chain.append(("mixer", "mixer"))
    chain.append(("nozzle", "nozzle"))
    chain.append(("exhaust", "exhaust"))
    return chain


def _shaft_kind(position: int, spool_count: int, free_power_turbine: bool) -> str:
    if spool_count <= 1:
        return "single"
    if free_power_turbine and position == spool_count - 1:
        return "free_power"
    return "common"


def architecture_from_state(
    space: Mapping[str, Any], state: Mapping[str, Any], spec: GenerativeSpec
) -> RotatingGasArchitecture:
    """Materialize the canonical architecture described by a design state."""

    index = _index(space)
    plan = row_plan(space, state, spec)
    heat_addition = _flag(index, state, "heat_addition")
    recuperator = _flag(index, state, "recuperator")
    intercooler = _flag(index, state, "intercooler")
    bypass_topology = _choice(index, state, "bypass_topology", "none")
    machine_kind = _choice(index, state, "machine_kind", "work_adding")
    material_family = _choice(index, state, "material_family", "aluminum")

    chain = _chain(plan, heat_addition, recuperator, intercooler, bypass_topology)
    position_of = {node_id: position for position, (node_id, _) in enumerate(chain)}

    nodes = [GasPathNode(node_id, kind) for node_id, kind in chain]
    edges: list[GasPathEdge] = []
    for position in range(len(chain) - 1):
        edges.append(
            GasPathEdge(chain[position][0], chain[position + 1][0], "flow")
        )
    if bypass_topology == "split_mix":
        edges.append(GasPathEdge("splitter", "mixer", "bypass"))

    stations = tuple(
        Station(f"st{position}", StationState()) for position in range(len(chain) + 1)
    )

    row_values: dict[str, tuple[float, ...]] = {
        variable_id: _profile_values(index, state, variable_id, len(plan), 0.0)
        for variable_id in (
            "row_blade_count",
            "row_chord_m",
            "row_stagger_deg",
            "row_sweep_deg",
            "row_lean_deg",
        )
    }
    rows: list[BladeRow] = []
    for row in plan:
        position = position_of[f"row{row.index}"]
        chord = row_values["row_chord_m"][row.index]
        stagger = row_values["row_stagger_deg"][row.index]
        sweep = row_values["row_sweep_deg"][row.index]
        lean = row_values["row_lean_deg"][row.index]
        periodicity = max(1, int(round(row_values["row_blade_count"][row.index])))
        rows.append(
            BladeRow(
                row_id=f"row{row.index}",
                node=f"row{row.index}",
                role=row.role,
                frame=row.frame,
                shaft=row.shaft_id,
                station_in=f"st{position}",
                station_out=f"st{position + 1}",
                row_count=1,
                periodicity=periodicity,
                family=row.family,
                geometry_ref=f"geom:{chord:.6f}:{stagger:.4f}:{sweep:.4f}:{lean:.4f}",
                material_ref=f"material:{material_family}",
            )
        )

    spool_count = int(_clamp(round(_number(index, state, "spool_count", 1.0)), 1, spec.max_spools))
    free_power_turbine = _flag(index, state, "free_power_turbine")
    speed_schedule = _profile_values(index, state, "spool_speed_schedule", spool_count, 20000.0)
    if machine_kind == "driven":
        nodes.append(GasPathNode("motor", "motor_coupling"))
    if machine_kind == "work_extracting":
        nodes.append(GasPathNode("generator", "generator_coupling"))

    shafts: list[Shaft] = []
    for spool in range(spool_count):
        members = tuple(
            sorted(f"row{row.index}" for row in plan if row.shaft_id == f"shaft{spool}")
        )
        couplings: list[ShaftCoupling] = []
        if machine_kind == "driven" and spool == 0 and "motor" in {node.node_id for node in nodes}:
            couplings.append(ShaftCoupling("drive", "electric_motor", target_node="motor"))
        if (
            machine_kind == "work_extracting"
            and spool == spool_count - 1
            and "generator" in {node.node_id for node in nodes}
        ):
            couplings.append(
                ShaftCoupling("generator-drive", "electric_generator", target_node="generator")
            )
        rpm = speed_schedule[spool] if spool < len(speed_schedule) else 20000.0
        shafts.append(
            Shaft(
                shaft_id=f"shaft{spool}",
                kind=_shaft_kind(spool, spool_count, free_power_turbine),
                members=members,
                speed=SpeedBound("speed", Quantity(max(0.0, rpm), "rpm")),
                couplings=tuple(couplings),
            )
        )

    return RotatingGasArchitecture(
        architecture_id=f"{spec.space_id}:architecture",
        nodes=tuple(nodes),
        edges=tuple(edges),
        stations=stations,
        rows=tuple(rows),
        shafts=tuple(shafts),
    )


def _meanline_family(family: str, role: str, machine_kind: str) -> str:
    if family == "radial":
        if role == "work_adding":
            return "radial_compressor_impeller"
        if role == "work_extracting":
            return "radial_turbine_rotor"
        if role == "diffuser_guide":
            return "radial_compressor_diffuser"
        return "axial_compressor_stator"
    if family == "mixed":
        if role == "work_adding":
            return "mixed_compressor_rotor"
        if role == "work_extracting":
            return "mixed_turbine_rotor"
        if role == "diffuser_guide":
            return "radial_compressor_diffuser"
        return "axial_compressor_stator"
    if role == "work_adding":
        return "axial_compressor_rotor"
    if role == "work_extracting":
        return "axial_turbine_rotor"
    if machine_kind == "work_extracting":
        return "axial_turbine_nozzle"
    return "axial_compressor_stator"


def meanline_stage_from_state(
    space: Mapping[str, Any], state: Mapping[str, Any], spec: GenerativeSpec
) -> StageDesign:
    """Resolve the TURBO 03 meanline stage that the design state describes."""

    index = _index(space)
    plan = row_plan(space, state, spec)
    machine_kind = _choice(index, state, "machine_kind", "work_adding")
    heat_addition = _flag(index, state, "heat_addition")
    shrouded = _flag(index, state, "shrouded")
    mass_flow = max(1e-3, _number(index, state, "corrected_flow_target", 10.0))
    meridional = max(20.0, mass_flow)
    inlet_temperature = (
        _number(index, state, "turbine_inlet_temperature_k", 1200.0)
        if heat_addition
        else 288.15
    )
    speed_schedule = _profile_values(index, state, "spool_speed_schedule", spec.max_spools, 20000.0)
    rotational_speed = max(0.0, speed_schedule[0])
    diffuser_area_ratio = _number(index, state, "diffuser_area_ratio", 2.0)

    def values(variable_id: str, default: float) -> tuple[float, ...]:
        return _profile_values(index, state, variable_id, len(plan), default)

    blade_counts = values("row_blade_count", 40.0)
    chords = values("row_chord_m", 0.05)
    solidities = values("row_solidity", 1.2)
    staggers = values("row_stagger_deg", 0.0)
    metal_angles = values("row_metal_angle_deg", 0.0)
    cambers = values("row_camber_deg", 20.0)
    hubs = values("row_hub_radius_m", 0.08)
    tips = values("row_tip_radius_m", 0.20)
    clearances = values("row_clearance_m", 3e-4)

    rows: list[MeanlineRow] = []
    for row in plan:
        position = row.index
        hub = max(1e-3, hubs[position])
        tip = tips[position]
        if tip <= hub:
            tip = hub + 0.05
        span = tip - hub
        clearance = _clamp(clearances[position], 0.0, min(1e-3, span * 0.5))
        camber = cambers[position]
        metal = metal_angles[position]
        rows.append(
            MeanlineRow(
                row_family=_meanline_family(row.family, row.role, machine_kind),
                mean_radius_in_m=0.5 * (hub + tip),
                mean_radius_out_m=0.5 * (hub + tip),
                meridional_velocity_in_m_s=meridional,
                inlet_metal_angle_deg=metal,
                exit_metal_angle_deg=metal - 0.5 * camber,
                stagger_deg=staggers[position],
                camber_deg=camber,
                solidity=max(0.1, solidities[position]),
                chord_m=max(1e-3, chords[position]),
                span_m=span,
                blade_count=max(1, int(round(blade_counts[position]))),
                tip_clearance_m=clearance,
                shrouded=shrouded,
                diffuser_area_ratio=diffuser_area_ratio if row.role == "diffuser_guide" else None,
            )
        )
    return StageDesign(
        gas=_AIR,
        inlet_total_temperature_k=max(200.0, inlet_temperature),
        inlet_total_pressure_pa=101325.0,
        mass_flow_kg_s=mass_flow,
        rotational_speed_rpm=rotational_speed,
        rows=tuple(rows),
        name=f"{spec.space_id}:meanline",
    )
