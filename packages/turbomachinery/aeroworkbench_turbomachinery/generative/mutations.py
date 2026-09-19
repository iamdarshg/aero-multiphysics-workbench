"""Domain-aware, bounded, deterministic mutations over the canonical contract.

Every operator produces a plain canonical design state. The result is validated by
the shared preflight and hashed by the shared candidate hasher, so a mutated design
is indistinguishable from one that was generated explicitly with the same values.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from . import _engine

__all__ = [
    "MUTATION_OPERATORS",
    "GenerativeMutationError",
    "MutationChange",
    "MutationOperator",
    "MutationOutcome",
    "apply_mutation",
    "design_identity",
    "operator_names",
    "parented_generation_request",
]


class GenerativeMutationError(ValueError):
    """Raised when a mutation request is structurally invalid."""


MutationOperator = Callable[[Mapping[str, Any], Mapping[str, Any], float], dict[str, Any] | None]


@dataclass(frozen=True, slots=True)
class MutationChange:
    variable_id: str
    point_id: str | None
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class MutationOutcome:
    operator: str
    accepted: bool
    reasons: tuple[str, ...]
    changes: tuple[MutationChange, ...]
    state: dict[str, Any] | None
    candidate_hash: str | None


def _index(space: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(variable["id"]): variable for variable in space.get("variables", ())}


def _variable(space: Mapping[str, Any], variable_id: str) -> Mapping[str, Any]:
    variable = _index(space).get(variable_id)
    if variable is None:
        raise GenerativeMutationError(f"UNKNOWN_VARIABLE:{variable_id}")
    return variable


def _raw_value(
    space: Mapping[str, Any], state: Mapping[str, Any], variable_id: str
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
    return _variable(space, variable_id).get("baseValue")


def _number(space: Mapping[str, Any], state: Mapping[str, Any], variable_id: str) -> float:
    value = _raw_value(space, state, variable_id)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GenerativeMutationError(f"NON_NUMERIC_VARIABLE:{variable_id}")
    return float(value)


def _domain(space: Mapping[str, Any], variable_id: str) -> Mapping[str, Any]:
    return cast("Mapping[str, Any]", _variable(space, variable_id)["domain"])


def _scalar_entry(space: Mapping[str, Any], variable_id: str, value: Any) -> dict[str, Any]:
    variable = _variable(space, variable_id)
    kind = str(variable["kind"])
    if kind == "categorical":
        return {"kind": "categorical", "value": str(value)}
    if kind == "boolean":
        return {"kind": "boolean", "value": bool(value)}
    number = float(value)
    if kind == "integer":
        number = float(int(round(number)))
    unit = variable.get("unit")
    if unit is None:
        return {"kind": "dimensionless", "value": number}
    return {"kind": "number", "value": number, "unit": str(unit)}


def _profile_entry(
    space: Mapping[str, Any], state: Mapping[str, Any], variable_id: str
) -> dict[str, Any]:
    """Full-length profile entry: control-point base values overlaid by any provided points."""

    controls = _domain(space, variable_id).get("controlPoints", ())
    provided: dict[str, float] = {}
    entry = state.get(variable_id)
    if isinstance(entry, Mapping) and entry.get("kind") == "vector-profile":
        for point in entry.get("points", ()):
            provided[str(point["id"])] = float(point["value"])
    return {
        "kind": "vector-profile",
        "points": [
            {
                "id": str(point["id"]),
                "value": provided.get(str(point["id"]), float(point["baseValue"])),
            }
            for point in controls
        ],
    }


def _clamp(value: float, lower: float, upper: float) -> float:
    if lower > upper:
        lower, upper = upper, lower
    return min(max(value, lower), upper)


def _perturb_profiles(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    new_state = copy.deepcopy(dict(state))
    changed = False
    for variable in space.get("variables", ()):
        if str(variable["kind"]) != "vector-profile":
            continue
        variable_id = str(variable["id"])
        controls = {str(point["id"]): point for point in variable["domain"]["controlPoints"]}
        entry = _profile_entry(space, state, variable_id)
        points: list[dict[str, Any]] = []
        for position, point in enumerate(entry["points"]):
            control = controls[str(point["id"])]
            lower = float(control["lower"])
            upper = float(control["upper"])
            before = float(point["value"])
            sign = 1.0 if position % 2 == 0 else -1.0
            after = _clamp(before + sign * magnitude * 0.1 * (upper - lower), lower, upper)
            if after != before:
                changed = True
            points.append({"id": str(point["id"]), "value": after})
        new_state[variable_id] = {"kind": "vector-profile", "points": points}
    return new_state if changed else None


def _add_stage(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    stage_upper = int(_domain(space, "stage_count")["upper"])
    row_upper = int(_domain(space, "row_count")["upper"])
    stages = int(round(_number(space, state, "stage_count")))
    rows = int(round(_number(space, state, "row_count")))
    next_stages = stages + 1
    next_rows = min(rows + 2, row_upper)
    if next_stages > stage_upper or next_rows <= rows:
        return None
    if next_rows > 2 * next_stages:
        return None
    new_state = copy.deepcopy(dict(state))
    new_state["stage_count"] = _scalar_entry(space, "stage_count", next_stages)
    new_state["row_count"] = _scalar_entry(space, "row_count", next_rows)
    return new_state


def _remove_stage(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    stages = int(round(_number(space, state, "stage_count")))
    rows = int(round(_number(space, state, "row_count")))
    if stages <= 1:
        return None
    next_stages = stages - 1
    next_rows = max(1, rows - 2)
    if next_rows < next_stages:
        next_rows = next_stages
    if next_rows > 2 * next_stages or next_rows == rows:
        return None
    new_state = copy.deepcopy(dict(state))
    new_state["stage_count"] = _scalar_entry(space, "stage_count", next_stages)
    new_state["row_count"] = _scalar_entry(space, "row_count", next_rows)
    return new_state


def _cycle_categorical(
    space: Mapping[str, Any], state: Mapping[str, Any], variable_id: str, value: Any
) -> Any | None:
    values = [str(item) for item in _domain(space, variable_id)["values"]]
    current = str(value)
    if current not in values or len(values) < 2:
        return values[0] if values and current not in values else None
    return values[(values.index(current) + 1) % len(values)]


def _change_row_family(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    current = _raw_value(space, state, "family")
    updated = _cycle_categorical(space, state, "family", current)
    if updated is None or updated == current:
        return None
    new_state = copy.deepcopy(dict(state))
    new_state["family"] = _scalar_entry(space, "family", updated)
    return new_state


def _redistribute_work(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    domain = _domain(space, "overall_pressure_ratio")
    lower = float(domain["lower"])
    upper = float(domain["upper"])
    before = _number(space, state, "overall_pressure_ratio")
    after = _clamp(before * (1.0 + 0.1 * magnitude), lower, upper)
    if after == before:
        after = _clamp(before - 0.1 * magnitude, lower, upper)
    if after == before:
        return None
    new_state = copy.deepcopy(dict(state))
    new_state["overall_pressure_ratio"] = _scalar_entry(
        space, "overall_pressure_ratio", after
    )
    return new_state


def _alter_hub_line(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    new_state = copy.deepcopy(dict(state))
    changed = False
    hub_controls = {
        str(point["id"]): point for point in _domain(space, "row_hub_radius_m")["controlPoints"]
    }
    tip_controls = {
        str(point["id"]): point for point in _domain(space, "row_tip_radius_m")["controlPoints"]
    }
    hub_entry = _profile_entry(space, state, "row_hub_radius_m")
    tip_entry = _profile_entry(space, state, "row_tip_radius_m")
    tip_by_id = {str(point["id"]): float(point["value"]) for point in tip_entry["points"]}
    hubs: list[dict[str, Any]] = []
    tips: list[dict[str, Any]] = []
    for point in hub_entry["points"]:
        point_id = str(point["id"])
        hub_control = hub_controls[point_id]
        tip_control = tip_controls[point_id]
        hub_before = float(point["value"])
        hub_after = _clamp(
            hub_before * (1.0 + 0.05 * magnitude),
            float(hub_control["lower"]),
            float(hub_control["upper"]),
        )
        tip_before = tip_by_id[point_id]
        tip_after = _clamp(
            tip_before * (1.0 + 0.05 * magnitude),
            float(tip_control["lower"]),
            float(tip_control["upper"]),
        )
        if tip_after <= hub_after:
            tip_after = _clamp(hub_after + 1e-3, float(tip_control["lower"]),
                               float(tip_control["upper"]))
        if hub_after != hub_before or tip_after != tip_before:
            changed = True
        hubs.append({"id": point_id, "value": hub_after})
        tips.append({"id": point_id, "value": tip_after})
    if not changed:
        return None
    new_state["row_hub_radius_m"] = {"kind": "vector-profile", "points": hubs}
    new_state["row_tip_radius_m"] = {"kind": "vector-profile", "points": tips}
    return new_state


def _change_process_material(
    space: Mapping[str, Any], state: Mapping[str, Any], magnitude: float
) -> dict[str, Any] | None:
    new_state = copy.deepcopy(dict(state))
    changed = False
    for variable_id in ("process", "material_family"):
        current = _raw_value(space, state, variable_id)
        updated = _cycle_categorical(space, state, variable_id, current)
        if updated is not None and updated != current:
            new_state[variable_id] = _scalar_entry(space, variable_id, updated)
            changed = True
    return new_state if changed else None


MUTATION_OPERATORS: dict[str, MutationOperator] = {
    "perturb-profile-control-points": _perturb_profiles,
    "add-stage": _add_stage,
    "remove-stage": _remove_stage,
    "change-row-family": _change_row_family,
    "redistribute-work": _redistribute_work,
    "alter-hub-line": _alter_hub_line,
    "change-process-material": _change_process_material,
}


def operator_names() -> tuple[str, ...]:
    return tuple(sorted(MUTATION_OPERATORS))


def design_identity(space: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    """Canonical candidate hash of a state, resolving through the shared contract."""

    return _engine.candidate_hash(_engine.flatten_design_state(space, state))


def _scalar_changes(
    space: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> list[MutationChange]:
    changes: list[MutationChange] = []
    for variable in space.get("variables", ()):
        variable_id = str(variable["id"])
        if variable["kind"] == "vector-profile":
            continue
        old = before.get(variable_id)
        new = after.get(variable_id)
        old_value = old.get("value") if isinstance(old, Mapping) else None
        new_value = new.get("value") if isinstance(new, Mapping) else None
        if old_value != new_value:
            changes.append(MutationChange(variable_id, None, old_value, new_value))
    return changes


def _profile_changes(
    space: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> list[MutationChange]:
    changes: list[MutationChange] = []
    for variable in space.get("variables", ()):
        if variable["kind"] != "vector-profile":
            continue
        variable_id = str(variable["id"])
        old_entry = before.get(variable_id)
        new_entry = after.get(variable_id)
        old_points = {
            str(point["id"]): float(point["value"])
            for point in (old_entry.get("points", ()) if isinstance(old_entry, Mapping) else ())
        }
        new_points = {
            str(point["id"]): float(point["value"])
            for point in (new_entry.get("points", ()) if isinstance(new_entry, Mapping) else ())
        }
        for point_id in sorted(set(old_points) | set(new_points)):
            old_value = old_points.get(point_id)
            new_value = new_points.get(point_id)
            if old_value != new_value:
                changes.append(MutationChange(variable_id, point_id, old_value, new_value))
    return changes


def apply_mutation(
    space: Mapping[str, Any],
    state: Mapping[str, Any],
    operator: str,
    *,
    magnitude: float = 1.0,
) -> MutationOutcome:
    """Apply one bounded operator, then resolve it through the canonical contract."""

    if operator not in MUTATION_OPERATORS:
        raise GenerativeMutationError(f"UNKNOWN_MUTATION_OPERATOR:{operator}")
    if not math.isfinite(magnitude) or magnitude < 0.0:
        raise GenerativeMutationError("MUTATION_MAGNITUDE_MUST_BE_NONNEGATIVE")
    candidate = MUTATION_OPERATORS[operator](space, state, magnitude)
    if candidate is None:
        return MutationOutcome(operator, False, ("OPERATOR_INAPPLICABLE",), (), None, None)
    reasons = _engine.preflight_design_state(space, candidate)
    if reasons:
        return MutationOutcome(operator, False, tuple(reasons), (), None, None)
    flat = _engine.flatten_design_state(space, candidate)
    identity = _engine.candidate_hash(flat)
    changes = _scalar_changes(space, state, candidate)
    changes.extend(_profile_changes(space, state, candidate))
    changes.sort(key=lambda change: (change.variable_id, change.point_id or ""))
    return MutationOutcome(operator, True, (), tuple(changes), candidate, identity)


def parented_generation_request(
    space: Mapping[str, Any],
    parent_state: Mapping[str, Any],
    *,
    strategy: str = "random",
    count: int = 16,
    seed: int = 0,
    budget: int = 10_000,
    levels: int = 3,
) -> Any:
    """Build a shared generation request whose mutation provenance is this parent."""

    return _engine.generation_request(
        strategy=strategy,
        count=count,
        seed=seed,
        budget=budget,
        levels=levels,
        parent_hash=design_identity(space, parent_state),
        parent_state=dict(parent_state),
    )
