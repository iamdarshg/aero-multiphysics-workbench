"""Map rotating-gas architecture choices into the canonical design-space contract.

The builder emits the same mixed/conditional/hierarchical JSON document that
``aeroworkbench_optimization.design_space`` validates and
``aeroworkbench_optimization.generation`` samples. Architecture, per-row, and
cycle choices are ordinary variables; family/machine/bypass/diffuser/process
choices are conditional branches; buildability rules become the existing
``relation``/``requires``/``mutually-exclusive`` constraints, so impossible
topology branches are never enumerated and unbuildable candidates are rejected by
the existing preflight before any CAD or solver work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from . import _engine
from .spec import GenerativeSpec

__all__ = [
    "ARRANGEMENTS",
    "BYPASS_TOPOLOGIES",
    "DIFFUSER_TYPES",
    "FAMILIES",
    "MACHINE_KINDS",
    "CardinalityReport",
    "SpaceSummary",
    "build_design_space",
    "cardinality_report",
    "default_generation_request",
    "run_generative_campaign",
    "space_summary",
]

FAMILIES: tuple[str, ...] = ("axial", "radial", "mixed")
ARRANGEMENTS: tuple[str, ...] = ("rotor_stator", "stator_rotor", "rotor_only")
MACHINE_KINDS: tuple[str, ...] = ("driven", "work_adding", "work_extracting")
BYPASS_TOPOLOGIES: tuple[str, ...] = ("none", "split", "split_mix")
DIFFUSER_TYPES: tuple[str, ...] = ("none", "vaned", "vaneless")


@dataclass(frozen=True, slots=True)
class SpaceSummary:
    """Typed, deterministic summary of a built design space."""

    variable_count: int
    kind_counts: tuple[tuple[str, int], ...]
    profile_variables: tuple[str, ...]
    branch_count: int
    constraint_count: int


@dataclass(frozen=True, slots=True)
class CardinalityReport:
    """Cardinality/budget exposure from the shared generator (never fabricated)."""

    exact: bool
    count: int | None
    estimate: int
    reason: str
    leaf_count: int
    exceeds_budget: bool
    budget: int | None


def _binding(target: str, path: str) -> dict[str, str]:
    return {"target": target, "path": path}


def _categorical(
    variable_id: str, path: str, values: Sequence[str], base: str, *, target: str = "parameter"
) -> dict[str, Any]:
    return {
        "id": variable_id,
        "kind": "categorical",
        "bindings": [_binding(target, path)],
        "baseValue": base,
        "domain": {"kind": "categorical", "values": list(values)},
    }


def _boolean(variable_id: str, path: str, base: bool) -> dict[str, Any]:
    return {
        "id": variable_id,
        "kind": "boolean",
        "bindings": [_binding("parameter", path)],
        "baseValue": base,
        "domain": {"kind": "boolean"},
    }


def _integer(
    variable_id: str, path: str, lower: int, upper: int, base: int
) -> dict[str, Any]:
    return {
        "id": variable_id,
        "kind": "integer",
        "bindings": [_binding("parameter", path)],
        "baseValue": base,
        "domain": {"kind": "integer", "lower": lower, "upper": upper, "step": 1},
    }


def _continuous(
    variable_id: str,
    path: str,
    lower: float,
    upper: float,
    base: float,
    *,
    unit: str | None = None,
    target: str = "parameter",
    active_when: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    variable: dict[str, Any] = {
        "id": variable_id,
        "kind": "continuous",
        "bindings": [_binding(target, path)],
        "baseValue": base,
        "domain": {"kind": "continuous", "lower": lower, "upper": upper},
    }
    if unit is not None:
        variable["unit"] = unit
    if active_when is not None:
        variable["activeWhen"] = dict(active_when)
    return variable


def _profile(
    variable_id: str,
    path: str,
    point_ids: Sequence[str],
    lower: float,
    upper: float,
    base: float,
    *,
    unit: str | None = None,
    target: str = "parameter",
) -> dict[str, Any]:
    variable: dict[str, Any] = {
        "id": variable_id,
        "kind": "vector-profile",
        "bindings": [_binding(target, path)],
        "domain": {
            "kind": "vector-profile",
            "lengthVariable": None,
            "controlPoints": [
                {"id": point_id, "lower": lower, "upper": upper, "baseValue": base}
                for point_id in point_ids
            ],
        },
    }
    if unit is not None:
        variable["unit"] = unit
    return variable


def _row_profile(
    spec: GenerativeSpec,
    variable_id: str,
    path: str,
    lower: float,
    upper: float,
    base: float,
    *,
    unit: str | None = None,
) -> dict[str, Any]:
    variable = _profile(variable_id, path, spec.row_point_ids, lower, upper, base, unit=unit)
    variable["domain"]["lengthVariable"] = "row_count"
    return variable


def _architecture_variables(spec: GenerativeSpec) -> list[dict[str, Any]]:
    return [
        _categorical("family", "architecture.family", FAMILIES, "axial"),
        _integer("stage_count", "architecture.stages", 1, spec.max_stages, 1),
        _integer("row_count", "architecture.rows", 1, spec.max_rows, 2),
        _categorical("arrangement", "architecture.arrangement", ARRANGEMENTS, "rotor_stator"),
        _integer("spool_count", "architecture.spools", 1, spec.max_spools, 2),
        _categorical("machine_kind", "architecture.machine", MACHINE_KINDS, "work_adding"),
        _boolean("free_power_turbine", "architecture.freePowerTurbine", False),
        _boolean("heat_addition", "architecture.heatAddition", True),
        _boolean("recuperator", "architecture.recuperator", False),
        _boolean("intercooler", "architecture.intercooler", False),
        _categorical("bypass_topology", "architecture.bypass", BYPASS_TOPOLOGIES, "none"),
        _boolean("shrouded", "architecture.shrouded", False),
        _categorical("diffuser_type", "architecture.diffuser", DIFFUSER_TYPES, "none"),
        _categorical(
            "material_family", "materials.family", spec.materials, spec.materials[0],
            target="material",
        ),
        _categorical(
            "process", "manufacturing.process", spec.processes, spec.processes[0],
            target="solver",
        ),
    ]


def _row_variables(spec: GenerativeSpec) -> list[dict[str, Any]]:
    return [
        _row_profile(spec, "row_blade_count", "rows.bladeCount", 8.0, 80.0, 40.0),
        _row_profile(spec, "row_chord_m", "rows.chord", 0.02, 0.12, 0.05, unit="m"),
        _row_profile(spec, "row_solidity", "rows.solidity", 0.6, 2.0, 1.2),
        _row_profile(spec, "row_stagger_deg", "rows.stagger", -40.0, 40.0, 0.0),
        _row_profile(spec, "row_twist_deg", "rows.twist", -30.0, 30.0, 0.0),
        _row_profile(spec, "row_metal_angle_deg", "rows.metalAngle", -60.0, 60.0, 0.0),
        _row_profile(spec, "row_camber_deg", "rows.camber", 0.0, 60.0, 20.0),
        _row_profile(spec, "row_thickness_ratio", "rows.thickness", 0.02, 0.2, 0.08),
        _row_profile(spec, "row_hub_radius_m", "rows.hubRadius", 0.05, 0.15, 0.08, unit="m"),
        _row_profile(spec, "row_tip_radius_m", "rows.tipRadius", 0.16, 0.30, 0.20, unit="m"),
        _row_profile(spec, "row_clearance_m", "rows.clearance", 1e-4, 1e-3, 3e-4, unit="m"),
        _row_profile(spec, "row_sweep_deg", "rows.sweep", -25.0, 25.0, 0.0),
        _row_profile(spec, "row_lean_deg", "rows.lean", -25.0, 25.0, 0.0),
        _row_profile(spec, "row_gap_m", "rows.gap", 0.005, 0.03, 0.01, unit="m"),
        _row_profile(spec, "row_speed_rpm", "rows.speed", 1000.0, 60000.0, 20000.0),
    ]


def _cycle_variables(spec: GenerativeSpec) -> list[dict[str, Any]]:
    heat_on = {"op": "equals", "variable": "heat_addition", "value": True}
    variables: list[dict[str, Any]] = [
        _continuous(
            "overall_pressure_ratio", "cycle.pressureRatio", 1.5, 12.0, 4.0,
            target="operating-point",
        ),
        _continuous(
            "corrected_flow_target", "cycle.correctedFlow", 1.0, 50.0, 10.0,
            target="operating-point",
        ),
        _continuous(
            "turbine_inlet_temperature_k", "cycle.turbineInletTemperature", 900.0, 1600.0,
            1200.0, target="operating-point", active_when=heat_on,
        ),
        _continuous(
            "cooling_fraction", "cycle.coolingFraction", 0.0, 0.3, 0.1,
            target="operating-point", active_when=heat_on,
        ),
        _continuous(
            "bleed_fraction", "cycle.bleedFraction", 0.0, 0.2, 0.0, target="operating-point"
        ),
        _continuous("bypass_ratio", "cycle.bypassRatio", 0.5, 10.0, 3.0),
        _continuous("mixer_area_ratio", "cycle.mixerAreaRatio", 0.5, 3.0, 1.2),
        _continuous(
            "electrical_power_fraction", "cycle.electricalPowerFraction", 0.0, 1.0, 0.5,
            target="operating-point",
        ),
        _continuous("motor_speed_rpm", "cycle.motorSpeed", 1000.0, 100000.0, 30000.0),
        _continuous(
            "generator_power_fraction", "cycle.generatorPowerFraction", 0.0, 1.0, 0.5,
            target="operating-point",
        ),
        _continuous("radial_slip_factor", "cycle.slipFactor", 0.6, 0.95, 0.85),
        _continuous("axial_reaction_deg", "cycle.reaction", 0.0, 1.0, 0.5),
        _continuous("mixed_flow_angle_deg", "cycle.mixedFlowAngle", 10.0, 80.0, 45.0),
        _continuous("diffuser_area_ratio", "cycle.diffuserAreaRatio", 1.5, 4.0, 2.0),
        _continuous("diffuser_vane_count", "cycle.diffuserVaneCount", 8.0, 40.0, 20.0),
        _continuous("min_wall_mm", "manufacturing.minWall", 0.2, 5.0, 1.0, unit="mm"),
        _continuous("tool_access_ratio", "manufacturing.toolAccess", 0.1, 1.0, 0.5),
    ]
    spool_schedule = _profile(
        "spool_speed_schedule", "cycle.spoolSpeed", spec.spool_point_ids,
        1000.0, 60000.0, 20000.0, target="operating-point",
    )
    spool_schedule["domain"]["lengthVariable"] = "spool_count"
    variables.append(spool_schedule)
    nozzle_schedule = _profile(
        "nozzle_area_schedule", "cycle.nozzleArea", spec.stage_point_ids,
        0.01, 1.0, 0.1, target="operating-point",
    )
    nozzle_schedule["domain"]["lengthVariable"] = "stage_count"
    variables.append(nozzle_schedule)
    return variables


def _branches(spec: GenerativeSpec) -> list[dict[str, Any]]:
    process_options: dict[str, list[str]] = {}
    for index, process in enumerate(spec.processes):
        members = ["min_wall_mm"]
        if index == 0:
            members.append("tool_access_ratio")
        process_options[process] = members
    return [
        {
            "id": "family-details",
            "selector": "family",
            "options": {
                "axial": ["axial_reaction_deg"],
                "radial": ["diffuser_type", "radial_slip_factor"],
                "mixed": ["diffuser_type", "mixed_flow_angle_deg"],
            },
        },
        {
            "id": "machine-details",
            "selector": "machine_kind",
            "options": {
                "driven": ["electrical_power_fraction", "motor_speed_rpm"],
                "work_adding": [],
                "work_extracting": ["generator_power_fraction"],
            },
        },
        {
            "id": "bypass-details",
            "selector": "bypass_topology",
            "options": {
                "none": [],
                "split": ["bypass_ratio"],
                "split_mix": ["bypass_ratio", "mixer_area_ratio"],
            },
        },
        {
            "id": "diffuser-details",
            "selector": "diffuser_type",
            "options": {
                "none": [],
                "vaned": ["diffuser_area_ratio", "diffuser_vane_count"],
                "vaneless": ["diffuser_area_ratio"],
            },
        },
        {
            "id": "process-details",
            "selector": "process",
            "options": process_options,
        },
    ]


def _constraints() -> list[dict[str, Any]]:
    return [
        {
            "id": "row-count-at-least-stages",
            "kind": "relation",
            "expression": {
                "op": "subtract",
                "left": {"op": "variable", "variable": "row_count"},
                "right": {"op": "variable", "variable": "stage_count"},
            },
            "relation": "greaterOrEqual",
            "limit": 0.0,
        },
        {
            "id": "row-count-at-most-two-per-stage",
            "kind": "relation",
            "expression": {
                "op": "subtract",
                "left": {
                    "op": "multiply",
                    "left": {"op": "variable", "variable": "stage_count"},
                    "right": {"op": "constant", "value": 2.0},
                },
                "right": {"op": "variable", "variable": "row_count"},
            },
            "relation": "greaterOrEqual",
            "limit": 0.0,
        },
        {
            "id": "recuperator-excludes-intercooler",
            "kind": "mutually-exclusive",
            "variables": ["recuperator", "intercooler"],
        },
        {
            "id": "recuperator-requires-heat-addition",
            "kind": "requires",
            "when": {"op": "equals", "variable": "recuperator", "value": True},
            "require": {"op": "equals", "variable": "heat_addition", "value": True},
        },
        {
            "id": "free-power-requires-two-spools",
            "kind": "requires",
            "when": {"op": "equals", "variable": "free_power_turbine", "value": True},
            "require": {"op": "greaterOrEqual", "variable": "spool_count", "valueSI": 2.0},
        },
        {
            "id": "bypass-requires-two-spools",
            "kind": "requires",
            "when": {"op": "in", "variable": "bypass_topology", "values": ["split", "split_mix"]},
            "require": {"op": "greaterOrEqual", "variable": "spool_count", "valueSI": 2.0},
        },
    ]


def build_design_space(
    spec: GenerativeSpec, *, envelopes: Any | None = None
) -> dict[str, Any]:
    """Build the canonical mixed/conditional/hierarchical design-space document.

    ``envelopes`` is an optional ``aeroworkbench_manufacturing`` :class:`EnvelopeSet`;
    its pre-CAD hard limits are compiled into the same constraint list the generic
    preflight already enforces.
    """

    variables: list[dict[str, Any]] = []
    variables.extend(_architecture_variables(spec))
    variables.extend(_row_variables(spec))
    variables.extend(_cycle_variables(spec))
    space: dict[str, Any] = {
        "id": spec.space_id,
        "variables": variables,
        "branches": _branches(spec),
        "constraints": _constraints(),
    }
    _engine.validate_design_space(space)
    if envelopes is not None:
        space = _engine.merge_envelope_constraints(space, envelopes)
    return space


def space_summary(space: Mapping[str, Any]) -> SpaceSummary:
    variables = [variable for variable in space.get("variables", ())]
    counts: dict[str, int] = {}
    profiles: list[str] = []
    for variable in variables:
        kind = str(variable["kind"])
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "vector-profile":
            profiles.append(str(variable["id"]))
    kinds = tuple((kind, counts[kind]) for kind in sorted(counts))
    return SpaceSummary(
        variable_count=len(variables),
        kind_counts=kinds,
        profile_variables=tuple(sorted(profiles)),
        branch_count=len(tuple(space.get("branches", ()))),
        constraint_count=len(tuple(space.get("constraints", ()))),
    )


def default_generation_request(
    spec: GenerativeSpec,
    *,
    strategy: str = "random",
    count: int = 32,
    seed: int = 0,
    budget: int = 10_000,
) -> Any:
    """Bounded, seeded, lazy-by-default generation request for this space.

    Enumerative strategies always carry an explicit budget, so the shared
    generator can never accidentally materialize a combinatorial explosion.
    """

    return _engine.generation_request(
        strategy=strategy, count=count, seed=seed, budget=budget, levels=spec.levels
    )


def run_generative_campaign(
    space: Mapping[str, Any],
    generation: Any,
    *,
    campaign_id: str,
    base_revision: str,
    objectives: Any,
    evaluator: Any,
    store: Any | None = None,
    **options: Any,
) -> Any:
    """Run the shared campaign engine over this space; a result store resumes it."""

    spec = _engine.campaign_spec(
        campaign_id=campaign_id,
        base_revision=base_revision,
        space=space,
        generation=generation,
        objectives=objectives,
        **options,
    )
    call_options: dict[str, Any] = {} if store is None else {"store": store}
    return _engine.run_campaign(spec, evaluator, **call_options)


def cardinality_report(space: Mapping[str, Any], request: Any) -> CardinalityReport:
    """Expose the shared generator's exact/estimated cardinality and budget verdict."""

    generator = _engine.candidate_generator(space, request)
    plan = generator.plan
    cardinality = plan.cardinality
    return CardinalityReport(
        exact=bool(cardinality.exact),
        count=None if cardinality.count is None else int(cardinality.count),
        estimate=int(cardinality.estimate),
        reason=str(cardinality.reason),
        leaf_count=len(tuple(generator.leaves)),
        exceeds_budget=bool(plan.exceeds_budget),
        budget=None if plan.budget is None else int(plan.budget),
    )
