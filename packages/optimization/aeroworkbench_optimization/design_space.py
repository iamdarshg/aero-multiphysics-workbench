"""Canonical mixed, conditional, hierarchical design-space contract.

This module mirrors the ``designSpace`` handling in
``packages/schema/src/design.ts``. It operates on the same canonical JSON
document so the TypeScript design state and the Python optimization layer
agree on activation, unit normalization, and candidate identity. Conditions
use a small typed predicate/expression AST; no user-provided code is executed.

The flattened view returned by :func:`flatten_design_state` is the stable,
unit-normalized representation that DOE/OpenMDAO/search code consumes, while
:func:`unflatten_design_state` reverses it back to hierarchical state. Both
layers hash the same active evaluation view in :func:`candidate_hash`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

__all__ = [
    "DesignSpaceError",
    "active_variable_ids",
    "candidate_hash",
    "canonical_json",
    "content_digest",
    "effective_profile_length",
    "flatten_design_state",
    "numeric_vector",
    "preflight_design_state",
    "unflatten_design_state",
    "validate_design_space",
]

_UNIT_SCALE: dict[str, float] = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254}

_VARIABLE_KINDS = (
    "continuous",
    "integer",
    "discrete",
    "categorical",
    "boolean",
    "vector-profile",
    "linked",
    "derived",
)
_NUMERIC_KINDS = ("continuous", "integer", "discrete")
_BINDING_TARGETS = ("parameter", "material", "solver", "operating-point")


class DesignSpaceError(ValueError):
    """Raised when a design space, state, or combination is structurally invalid."""


def _require_finite(label: str, value: float) -> None:
    if not isfinite(value):
        raise DesignSpaceError(f"{label} must be finite")


def _normalize_number(value: float) -> float:
    return 0.0 if value == 0 else float(value)


def _to_si(label: str, value: float, unit: str | None) -> float:
    if unit is None:
        _require_finite(label, value)
        return _normalize_number(float(value))
    scale = _UNIT_SCALE.get(unit)
    if scale is None:
        raise DesignSpaceError(f"UNSUPPORTED_UNIT:{label}:{unit}")
    if not isfinite(value):
        raise DesignSpaceError(f"{label} must be finite")
    return _normalize_number((float(value) + 0.0) * scale)


def _canonical(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise DesignSpaceError("NONFINITE_CANONICAL_VALUE")
        if value == 0:
            return 0
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Deterministic JSON with sorted keys and integral-float normalization."""
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _index(space: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    variables = space.get("variables")
    if not isinstance(variables, Sequence):
        raise DesignSpaceError("DESIGN_SPACE_NEEDS_VARIABLES")
    return {str(variable["id"]): variable for variable in variables}


def _expression_variables(expression: Mapping[str, Any]) -> list[str]:
    op = expression.get("op")
    if op == "variable":
        return [str(expression["variable"])]
    if op == "constant":
        return []
    return [
        *_expression_variables(expression["left"]),
        *_expression_variables(expression["right"]),
    ]


def _validate_bindings(variable: Mapping[str, Any]) -> None:
    bindings = variable.get("bindings")
    if not isinstance(bindings, Sequence) or not bindings:
        raise DesignSpaceError(f"VARIABLE_NEEDS_BINDING:{variable['id']}")
    for binding in bindings:
        if binding.get("target") not in _BINDING_TARGETS:
            raise DesignSpaceError(f"UNKNOWN_BINDING_TARGET:{variable['id']}")
        if not str(binding.get("path", "")).strip():
            raise DesignSpaceError(f"BINDING_PATH_REQUIRED:{variable['id']}")


def _validate_control_points(variable: Mapping[str, Any], domain: Mapping[str, Any]) -> None:
    points = domain.get("controlPoints")
    if not isinstance(points, Sequence) or not points:
        raise DesignSpaceError(f"PROFILE_NEEDS_CONTROL_POINTS:{variable['id']}")
    seen: set[str] = set()
    for point in points:
        point_id = str(point.get("id", ""))
        if not point_id.strip():
            raise DesignSpaceError(f"PROFILE_POINT_ID_REQUIRED:{variable['id']}")
        if point_id in seen:
            raise DesignSpaceError(f"DUPLICATE_PROFILE_POINT:{variable['id']}:{point_id}")
        seen.add(point_id)
        lower = float(point["lower"])
        upper = float(point["upper"])
        base = float(point["baseValue"])
        _require_finite(f"profile:{variable['id']}:{point_id}", lower)
        _require_finite(f"profile:{variable['id']}:{point_id}", upper)
        _require_finite(f"profile:{variable['id']}:{point_id}", base)
        if lower > upper:
            raise DesignSpaceError(f"PROFILE_BOUNDS_INVALID:{variable['id']}:{point_id}")
        if base < lower or base > upper:
            raise DesignSpaceError(f"PROFILE_BASE_OUT_OF_BOUNDS:{variable['id']}:{point_id}")


def _validate_predicate(predicate: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    variable = index.get(str(predicate.get("variable")))
    if variable is None:
        raise DesignSpaceError(f"PREDICATE_UNKNOWN_VARIABLE:{predicate.get('variable')}")
    variable_id = variable["id"]
    op = predicate.get("op")
    if op in {"equals", "in"}:
        if variable["kind"] not in {"categorical", "boolean"}:
            raise DesignSpaceError(f"EQUALITY_NEEDS_CATEGORICAL_OR_BOOLEAN:{variable_id}")
        if op == "equals":
            values = [predicate.get("value")]
        else:
            raw_values = predicate.get("values")
            if not isinstance(raw_values, Sequence) or not raw_values:
                raise DesignSpaceError(f"PREDICATE_IN_NEEDS_VALUES:{variable_id}")
            values = list(raw_values)
        domain_values = variable["domain"].get("values", ())
        for value in values:
            if variable["kind"] == "boolean" and not isinstance(value, bool):
                raise DesignSpaceError(f"BOOLEAN_PREDICATE_VALUE_REQUIRED:{variable_id}")
            if variable["kind"] == "categorical":
                if not isinstance(value, str):
                    raise DesignSpaceError(f"CATEGORICAL_PREDICATE_VALUE_REQUIRED:{variable_id}")
                if value not in domain_values:
                    raise DesignSpaceError(f"PREDICATE_VALUE_NOT_IN_DOMAIN:{variable_id}:{value}")
        return
    if op in {"lessThan", "lessOrEqual", "greaterThan", "greaterOrEqual"}:
        if variable["kind"] not in _NUMERIC_KINDS:
            raise DesignSpaceError(f"COMPARISON_NEEDS_NUMERIC:{variable_id}")
        _require_finite(f"predicate:{variable_id}", float(predicate["valueSI"]))
        return
    if op in {"all", "any"}:
        for clause in predicate["clauses"]:
            _validate_predicate(clause, index)
        return
    if op == "not":
        _validate_predicate(predicate["clause"], index)
        return
    raise DesignSpaceError("UNKNOWN_PREDICATE_OP")


def _validate_expression(expression: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    op = expression.get("op")
    if op == "variable":
        variable = index.get(str(expression.get("variable")))
        if variable is None:
            raise DesignSpaceError(f"EXPRESSION_UNKNOWN_VARIABLE:{expression.get('variable')}")
        if variable["kind"] not in (*_NUMERIC_KINDS, "linked", "derived"):
            raise DesignSpaceError(f"EXPRESSION_NEEDS_NUMERIC:{variable['id']}")
        return
    if op == "constant":
        _require_finite("expression constant", float(expression["value"]))
        return
    _validate_expression(expression["left"], index)
    _validate_expression(expression["right"], index)
    if (
        op == "divide"
        and expression["right"].get("op") == "constant"
        and float(expression["right"]["value"]) == 0.0
    ):
        raise DesignSpaceError("EXPRESSION_DIVISION_BY_ZERO")


def _validate_variable(variable: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    variable_id = str(variable.get("id", ""))
    if not variable_id.strip():
        raise DesignSpaceError("VARIABLE_ID_REQUIRED")
    kind = variable.get("kind")
    if kind not in _VARIABLE_KINDS:
        raise DesignSpaceError(f"UNKNOWN_VARIABLE_KIND:{variable_id}")
    domain = variable["domain"]
    if domain.get("kind") != kind:
        raise DesignSpaceError(f"DOMAIN_KIND_MISMATCH:{variable_id}")
    unit = variable.get("unit")
    if unit is not None:
        if not str(unit).strip():
            raise DesignSpaceError(f"VARIABLE_UNIT_EMPTY:{variable_id}")
        if kind in {"categorical", "boolean"}:
            raise DesignSpaceError(f"NON_NUMERIC_VARIABLE_HAS_UNIT:{variable_id}")
        if unit not in _UNIT_SCALE:
            raise DesignSpaceError(f"UNSUPPORTED_UNIT:{variable_id}:{unit}")
    _validate_bindings(variable)
    mutation_scale = variable.get("mutationScale")
    if mutation_scale is not None:
        _require_finite(f"mutationScale:{variable_id}", float(mutation_scale))
        if float(mutation_scale) <= 0:
            raise DesignSpaceError(f"MUTATION_SCALE_MUST_BE_POSITIVE:{variable_id}")
    if kind == "continuous":
        lower, upper = float(domain["lower"]), float(domain["upper"])
        _require_finite(variable_id, lower)
        _require_finite(variable_id, upper)
        if not lower < upper:
            raise DesignSpaceError(f"INVALID_CONTINUOUS_BOUNDS:{variable_id}")
    elif kind == "integer":
        lower, upper, step = float(domain["lower"]), float(domain["upper"]), float(domain["step"])
        _require_finite(variable_id, lower)
        _require_finite(variable_id, upper)
        _require_finite(variable_id, step)
        if not lower <= upper:
            raise DesignSpaceError(f"INVALID_INTEGER_BOUNDS:{variable_id}")
        if not (lower.is_integer() and upper.is_integer() and step.is_integer()):
            raise DesignSpaceError(f"INTEGER_BOUNDS_NOT_INTEGRAL:{variable_id}")
        if step <= 0:
            raise DesignSpaceError(f"INTEGER_STEP_MUST_BE_POSITIVE:{variable_id}")
    elif kind == "discrete":
        values = domain.get("values")
        if not isinstance(values, Sequence) or not values:
            raise DesignSpaceError(f"DISCRETE_NEEDS_VALUES:{variable_id}")
        if len(set(values)) != len(values):
            raise DesignSpaceError(f"DISCRETE_VALUES_DUPLICATE:{variable_id}")
        for value in values:
            _require_finite(f"discrete:{variable_id}", float(value))
    elif kind == "categorical":
        values = domain.get("values")
        if not isinstance(values, Sequence) or not values:
            raise DesignSpaceError(f"CATEGORICAL_NEEDS_VALUES:{variable_id}")
        if any(not str(value).strip() for value in values):
            raise DesignSpaceError(f"CATEGORICAL_VALUE_EMPTY:{variable_id}")
        if len(set(values)) != len(values):
            raise DesignSpaceError(f"CATEGORICAL_VALUES_DUPLICATE:{variable_id}")
    elif kind == "vector-profile":
        _validate_control_points(variable, domain)
        length_variable = domain.get("lengthVariable")
        if length_variable is not None:
            target = index.get(str(length_variable))
            if target is None:
                raise DesignSpaceError(f"PROFILE_LENGTH_UNKNOWN_VARIABLE:{variable_id}")
            if target["kind"] != "integer":
                raise DesignSpaceError(f"PROFILE_LENGTH_NEEDS_INTEGER:{variable_id}")
    elif kind == "linked":
        target = index.get(str(domain.get("targetVariable")))
        if target is None:
            raise DesignSpaceError(f"LINKED_UNKNOWN_TARGET:{variable_id}")
        if target["kind"] not in _NUMERIC_KINDS:
            raise DesignSpaceError(f"LINKED_TARGET_NEEDS_NUMERIC:{variable_id}")
        if target["id"] == variable_id:
            raise DesignSpaceError(f"LINKED_SELF_REFERENCE:{variable_id}")
        if domain.get("scale") is not None:
            _require_finite(f"linked:{variable_id}", float(domain["scale"]))
        if domain.get("offset") is not None:
            _require_finite(f"linked:{variable_id}", float(domain["offset"]))
    elif kind == "derived":
        _validate_expression(domain["expression"], index)
    active_when = variable.get("activeWhen")
    if active_when is not None:
        _validate_predicate(active_when, index)


def _validate_branch(branch: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    branch_id = str(branch.get("id", ""))
    if not branch_id.strip():
        raise DesignSpaceError("BRANCH_ID_REQUIRED")
    selector = index.get(str(branch.get("selector")))
    if selector is None:
        raise DesignSpaceError(f"BRANCH_UNKNOWN_SELECTOR:{branch_id}")
    if selector["kind"] != "categorical":
        raise DesignSpaceError(f"BRANCH_SELECTOR_NEEDS_CATEGORICAL:{branch_id}")
    domain_values = selector["domain"].get("values", ())
    options = branch.get("options", {})
    if not isinstance(options, Mapping):
        raise DesignSpaceError(f"BRANCH_OPTIONS_REQUIRED:{branch_id}")
    for option, members in options.items():
        if option not in domain_values:
            raise DesignSpaceError(f"BRANCH_OPTION_NOT_IN_DOMAIN:{branch_id}:{option}")
        for member in members:
            if str(member) not in index:
                raise DesignSpaceError(f"BRANCH_UNKNOWN_MEMBER:{branch_id}:{member}")


def _validate_constraint(constraint: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    constraint_id = str(constraint.get("id", ""))
    if not constraint_id.strip():
        raise DesignSpaceError("CONSTRAINT_ID_REQUIRED")
    kind = constraint.get("kind")
    if kind == "mutually-exclusive":
        variables = constraint.get("variables", ())
        if len(variables) < 2:
            raise DesignSpaceError(f"MUTEX_NEEDS_TWO_VARIABLES:{constraint_id}")
        for variable_id in variables:
            variable = index.get(str(variable_id))
            if variable is None:
                raise DesignSpaceError(f"CONSTRAINT_UNKNOWN_VARIABLE:{constraint_id}:{variable_id}")
            if variable["kind"] != "boolean":
                raise DesignSpaceError(f"MUTEX_NEEDS_BOOLEAN:{constraint_id}:{variable_id}")
        return
    if kind == "requires":
        _validate_predicate(constraint["when"], index)
        _validate_predicate(constraint["require"], index)
        return
    if kind == "relation":
        _validate_expression(constraint["expression"], index)
        _require_finite(f"relation:{constraint_id}", float(constraint["limit"]))
        return
    if kind == "count":
        count_variable = index.get(str(constraint.get("countVariable")))
        if count_variable is None:
            raise DesignSpaceError(f"CONSTRAINT_UNKNOWN_VARIABLE:{constraint_id}")
        if count_variable["kind"] != "integer":
            raise DesignSpaceError(f"COUNT_NEEDS_INTEGER:{constraint_id}")
        member = index.get(str(constraint.get("memberVariable")))
        if member is None:
            raise DesignSpaceError(f"CONSTRAINT_UNKNOWN_VARIABLE:{constraint_id}")
        if member["kind"] != "vector-profile":
            raise DesignSpaceError(f"COUNT_NEEDS_PROFILE_MEMBER:{constraint_id}")
        return
    raise DesignSpaceError(f"UNKNOWN_CONSTRAINT_KIND:{kind}")


def _dependency_edges(space: Mapping[str, Any], index: Mapping[str, Any]) -> dict[str, list[str]]:
    edges: dict[str, list[str]] = {}
    for variable in space["variables"]:
        domain = variable["domain"]
        kind = domain["kind"]
        if kind == "linked":
            edges[variable["id"]] = [str(domain["targetVariable"])]
        elif kind == "derived":
            edges[variable["id"]] = [
                name for name in _expression_variables(domain["expression"]) if name in index
            ]
        elif kind == "vector-profile" and domain.get("lengthVariable") is not None:
            edges[variable["id"]] = [str(domain["lengthVariable"])]
        else:
            edges[variable["id"]] = []
    return edges


def _validate_acyclic(space: Mapping[str, Any], index: Mapping[str, Any]) -> None:
    edges = _dependency_edges(space, index)
    state: dict[str, str] = {}

    def visit(node_id: str) -> None:
        current = state.get(node_id)
        if current == "done":
            return
        if current == "visiting":
            raise DesignSpaceError(f"DESIGN_SPACE_CYCLE:{node_id}")
        state[node_id] = "visiting"
        for next_id in edges.get(node_id, ()):
            visit(next_id)
        state[node_id] = "done"

    for node_id in edges:
        visit(node_id)


def validate_design_space(space: Mapping[str, Any]) -> None:
    """Fail closed on any structural inconsistency in a design space."""
    if not str(space.get("id", "")).strip():
        raise DesignSpaceError("DESIGN_SPACE_ID_REQUIRED")
    variables = space.get("variables")
    if not isinstance(variables, Sequence) or not variables:
        raise DesignSpaceError("DESIGN_SPACE_NEEDS_VARIABLES")
    index = _index(space)
    if len(index) != len(variables):
        raise DesignSpaceError("DESIGN_SPACE_DUPLICATE_VARIABLE")
    for variable in variables:
        _validate_variable(variable, index)
    for branch in space.get("branches", ()):
        _validate_branch(branch, index)
    for constraint in space.get("constraints", ()):
        _validate_constraint(constraint, index)
    _validate_acyclic(space, index)


def _raw_state_value(variable: Mapping[str, Any], state: Mapping[str, Any]) -> Any:
    entry = state.get(variable["id"])
    if entry is None:
        return None
    kind = entry.get("kind")
    if kind in {"number", "dimensionless"}:
        if variable["kind"] not in _NUMERIC_KINDS:
            raise DesignSpaceError(f"STATE_KIND_MISMATCH:{variable['id']}")
        return float(entry["value"])
    if kind == "categorical":
        return str(entry["value"])
    if kind == "boolean":
        return bool(entry["value"])
    return None


def _resolve_value(
    variable: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
    visiting: set[str] | None = None,
) -> dict[str, Any]:
    visiting = visiting if visiting is not None else set()
    variable_id = str(variable["id"])
    if variable_id in visiting:
        raise DesignSpaceError(f"DESIGN_SPACE_CYCLE:{variable_id}")
    visiting.add(variable_id)
    try:
        entry = state.get(variable_id)
        if entry is not None:
            entry_kind = entry.get("kind")
            if entry_kind == "number":
                value = float(entry["value"])
                return {
                    "raw": value,
                    "value_si": _to_si(variable_id, value, str(entry["unit"])),
                    "unit": variable.get("unit"),
                }
            if entry_kind == "dimensionless":
                value = float(entry["value"])
                return {"raw": value, "value_si": _to_si(variable_id, value, None)}
            if entry_kind == "categorical":
                return {"raw": str(entry["value"])}
            if entry_kind == "boolean":
                return {"raw": bool(entry["value"])}
            raise DesignSpaceError(f"STATE_KIND_MISMATCH:{variable_id}")
        domain = variable["domain"]
        kind = domain["kind"]
        if kind == "linked":
            target = index[str(domain["targetVariable"])]
            resolved = _resolve_value(target, index, state, visiting)
            value_si = resolved.get("value_si")
            if not isinstance(value_si, float):
                raise DesignSpaceError(f"LINKED_TARGET_NOT_NUMERIC:{variable_id}")
            value = value_si * float(domain.get("scale", 1.0)) + float(domain.get("offset", 0.0))
            return {
                "raw": _normalize_number(value),
                "value_si": _normalize_number(value),
                "unit": resolved.get("unit"),
            }
        if kind == "derived":
            value = _evaluate_expression(domain["expression"], index, state, visiting)
            return {"raw": value, "value_si": value, "unit": variable.get("unit")}
        base_value = variable.get("baseValue")
        if base_value is not None:
            if isinstance(base_value, (int, float)) and not isinstance(base_value, bool):
                value = float(base_value)
                return {
                    "raw": value,
                    "value_si": _to_si(variable_id, value, variable.get("unit")),
                    "unit": variable.get("unit"),
                }
            return {"raw": base_value}
        raise DesignSpaceError(f"MISSING_VARIABLE_VALUE:{variable_id}")
    finally:
        visiting.discard(variable_id)


def _evaluate_expression(
    expression: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
    visiting: set[str] | None = None,
) -> float:
    op = expression.get("op")
    if op == "constant":
        return float(expression["value"])
    if op == "variable":
        variable = index[str(expression["variable"])]
        resolved = _resolve_value(variable, index, state, visiting)
        value_si = resolved.get("value_si")
        if not isinstance(value_si, float):
            raise DesignSpaceError(f"EXPRESSION_NEEDS_NUMERIC:{variable['id']}")
        return value_si
    left = _evaluate_expression(expression["left"], index, state, visiting)
    right = _evaluate_expression(expression["right"], index, state, visiting)
    if op == "add":
        return left + right
    if op == "subtract":
        return left - right
    if op == "multiply":
        return left * right
    if op == "divide":
        if right == 0.0:
            raise DesignSpaceError("EXPRESSION_DIVISION_BY_ZERO")
        return left / right
    raise DesignSpaceError("UNKNOWN_EXPRESSION_OP")


def _evaluate_predicate(
    predicate: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
    depth: int = 0,
) -> bool:
    if depth > 64:
        raise DesignSpaceError("PREDICATE_DEPTH_EXCEEDED")
    op = predicate.get("op")
    if op in {"equals", "in"}:
        variable = index[str(predicate["variable"])]
        resolved = _resolve_value(variable, index, state)
        values = [predicate.get("value")] if op == "equals" else list(predicate["values"])
        return any(resolved.get("raw") == value for value in values)
    if op == "all":
        return all(
            _evaluate_predicate(clause, index, state, depth + 1) for clause in predicate["clauses"]
        )
    if op == "any":
        return any(
            _evaluate_predicate(clause, index, state, depth + 1) for clause in predicate["clauses"]
        )
    if op == "not":
        return not _evaluate_predicate(predicate["clause"], index, state, depth + 1)
    variable = index[str(predicate["variable"])]
    resolved = _resolve_value(variable, index, state)
    value_si = resolved.get("value_si")
    if not isinstance(value_si, float):
        raise DesignSpaceError(f"COMPARISON_NEEDS_NUMERIC:{variable['id']}")
    limit = float(predicate["valueSI"])
    if op == "lessThan":
        return value_si < limit
    if op == "lessOrEqual":
        return value_si <= limit
    if op == "greaterThan":
        return value_si > limit
    if op == "greaterOrEqual":
        return value_si >= limit
    raise DesignSpaceError("UNKNOWN_PREDICATE_OP")


def _branch_membership(space: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    membership: dict[str, list[Mapping[str, Any]]] = {}
    for branch in space.get("branches", ()):
        for members in branch.get("options", {}).values():
            for member in members:
                membership.setdefault(str(member), []).append(branch)
    return membership


def _branch_allows(
    variable_id: str,
    branches: Sequence[Mapping[str, Any]],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
) -> bool:
    for branch in branches:
        selector = index[str(branch["selector"])]
        resolved = _resolve_value(selector, index, state)
        selected = branch.get("options", {}).get(str(resolved.get("raw")), [])
        if variable_id not in selected:
            return False
    return True


def active_variable_ids(space: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[str, ...]:
    """Active variables in declaration order; inactive ones stay as lineage."""
    index = _index(space)
    membership = _branch_membership(space)
    memo: dict[str, bool] = {}

    def is_active(variable_id: str, visiting: set[str]) -> bool:
        remembered = memo.get(variable_id)
        if remembered is not None:
            return remembered
        if variable_id in visiting:
            raise DesignSpaceError(f"DESIGN_SPACE_ACTIVATION_CYCLE:{variable_id}")
        visiting.add(variable_id)
        variable = index[variable_id]
        active = _branch_allows(variable_id, membership.get(variable_id, []), index, state)
        if active and variable.get("activeWhen") is not None:
            active = _evaluate_predicate(variable["activeWhen"], index, state)
        domain = variable["domain"]
        if active and domain["kind"] == "linked":
            active = is_active(str(domain["targetVariable"]), visiting)
        if active and domain["kind"] == "derived":
            active = all(
                is_active(name, visiting) for name in _expression_variables(domain["expression"])
            )
        if (
            active
            and domain["kind"] == "vector-profile"
            and domain.get("lengthVariable") is not None
        ):
            active = is_active(str(domain["lengthVariable"]), visiting)
        visiting.discard(variable_id)
        memo[variable_id] = active
        return active

    return tuple(
        str(variable["id"])
        for variable in space["variables"]
        if is_active(str(variable["id"]), set())
    )


def effective_profile_length(
    variable: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
) -> int:
    domain = variable["domain"]
    length_variable = domain.get("lengthVariable")
    if length_variable is None:
        return len(domain["controlPoints"])
    resolved = _resolve_value(index[str(length_variable)], index, state)
    raw = resolved.get("raw")
    if not isinstance(raw, (int, float)):
        raise DesignSpaceError(f"PROFILE_LENGTH_NEEDS_INTEGER:{variable['id']}")
    return int(raw)


def _profile_point_si_bounds(
    variable: Mapping[str, Any], point: Mapping[str, Any]
) -> tuple[float, float]:
    return (
        _to_si(str(variable["id"]), float(point["lower"]), variable.get("unit")),
        _to_si(str(variable["id"]), float(point["upper"]), variable.get("unit")),
    )


def _domain_violations(
    variable: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
) -> list[str]:
    violations: list[str] = []
    domain = variable["domain"]
    kind = domain["kind"]
    variable_id = str(variable["id"])
    if kind in {"continuous", "integer", "discrete"}:
        resolved = _resolve_value(variable, index, state)
        value = resolved.get("value_si")
        raw = resolved.get("raw")
        if kind == "integer" and not (isinstance(raw, (int, float)) and float(raw).is_integer()):
            return [f"{variable_id}:VALUE_NOT_INTEGER"]
        if not isinstance(value, float):
            return [f"{variable_id}:VALUE_NOT_NUMERIC"]
        if kind == "continuous" or kind == "integer":
            lower = _to_si(variable_id, float(domain["lower"]), variable.get("unit"))
            upper = _to_si(variable_id, float(domain["upper"]), variable.get("unit"))
            if value < lower or value > upper:
                violations.append(f"{variable_id}:OUT_OF_BOUNDS")
        else:
            allowed = [
                _to_si(variable_id, float(item), variable.get("unit")) for item in domain["values"]
            ]
            if value not in allowed:
                violations.append(f"{variable_id}:NOT_A_DISCRETE_VALUE")
    elif kind == "categorical":
        raw = _resolve_value(variable, index, state).get("raw")
        if not isinstance(raw, str):
            violations.append(f"{variable_id}:VALUE_NOT_CATEGORICAL")
        elif raw not in domain.get("values", ()):
            violations.append(f"{variable_id}:NOT_A_CATEGORICAL_VALUE")
    elif kind == "boolean":
        if not isinstance(_resolve_value(variable, index, state).get("raw"), bool):
            violations.append(f"{variable_id}:VALUE_NOT_BOOLEAN")
    elif kind == "vector-profile":
        length = effective_profile_length(variable, index, state)
        if length < 1 or length > len(domain["controlPoints"]):
            violations.append(f"{variable_id}:PROFILE_LENGTH_OUT_OF_RANGE")
        entry = state.get(variable_id)
        if entry is not None and entry.get("kind") != "vector-profile":
            violations.append(f"{variable_id}:STATE_KIND_MISMATCH")
        points = (
            entry.get("points")
            if entry is not None and entry.get("kind") == "vector-profile"
            else None
        )
        if points:
            control_by_id = {str(point["id"]): point for point in domain["controlPoints"]}
            for point in points:
                control = control_by_id.get(str(point["id"]))
                if control is None:
                    violations.append(f"{variable_id}:UNKNOWN_PROFILE_POINT:{point['id']}")
                    continue
                value = _to_si(
                    variable_id, float(point["value"]), point.get("unit", variable.get("unit"))
                )
                lower, upper = _profile_point_si_bounds(variable, control)
                if value < lower or value > upper:
                    violations.append(f"{variable_id}:PROFILE_POINT_OUT_OF_BOUNDS:{point['id']}")
    elif kind in {"linked", "derived"}:
        try:
            _resolve_value(variable, index, state)
        except DesignSpaceError:
            violations.append(f"{variable_id}:UNRESOLVED")
    return violations


def _constraint_violations(
    space: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
) -> list[str]:
    violations: list[str] = []
    for constraint in space.get("constraints", ()):
        constraint_id = str(constraint["id"])
        kind = constraint["kind"]
        if kind == "mutually-exclusive":
            truths = [
                variable_id
                for variable_id in constraint["variables"]
                if _resolve_value(index[str(variable_id)], index, state).get("raw") is True
            ]
            if len(truths) > 1:
                violations.append(f"{constraint_id}:MUTUALLY_EXCLUSIVE_VIOLATION")
        elif kind == "requires":
            if _evaluate_predicate(constraint["when"], index, state) and not _evaluate_predicate(
                constraint["require"], index, state
            ):
                violations.append(f"{constraint_id}:REQUIRED_CONDITION_UNMET")
        elif kind == "relation":
            value = _evaluate_expression(constraint["expression"], index, state)
            relation = constraint["relation"]
            limit = float(constraint["limit"])
            if (
                relation == "lessOrEqual"
                and value > limit
                or relation == "greaterOrEqual"
                and value < limit
                or relation == "equal"
                and abs(value - limit) > 1e-9
            ):
                violations.append(f"{constraint_id}:RELATION_VIOLATION")
        elif kind == "count":
            count_variable = index[str(constraint["countVariable"])]
            member = index[str(constraint["memberVariable"])]
            count = _resolve_value(count_variable, index, state).get("raw")
            if isinstance(count, (int, float)):
                entry = state.get(str(member["id"]))
                provided = (
                    len(entry["points"])
                    if entry is not None
                    and entry.get("kind") == "vector-profile"
                    and entry.get("points")
                    else None
                )
                actual = (
                    provided
                    if provided is not None
                    else effective_profile_length(member, index, state)
                )
                if actual != int(count):
                    violations.append(f"{constraint_id}:COUNT_MISMATCH")
    return violations


def preflight_design_state(space: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[str, ...]:
    """Cheap structural checks evaluated before any physics."""
    index = _index(space)
    for variable_id in state:
        if str(variable_id) not in index:
            raise DesignSpaceError(f"STATE_UNKNOWN_VARIABLE:{variable_id}")
    active = set(active_variable_ids(space, state))
    violations: list[str] = []
    for variable in space["variables"]:
        variable_id = str(variable["id"])
        if variable_id not in active:
            continue
        computed = variable["kind"] in {"linked", "derived", "vector-profile"}
        if variable_id not in state and variable.get("baseValue") is None and not computed:
            violations.append(f"{variable_id}:MISSING_VALUE")
            continue
        violations.extend(_domain_violations(variable, index, state))
    violations.extend(_constraint_violations(space, index, state))
    return tuple(violations)


def _flat_profile_points(
    variable: Mapping[str, Any],
    index: Mapping[str, Any],
    state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    domain = variable["domain"]
    length = effective_profile_length(variable, index, state)
    entry = state.get(str(variable["id"]))
    state_points = (
        entry.get("points") if entry is not None and entry.get("kind") == "vector-profile" else None
    )
    by_id = {str(point["id"]): point for point in (state_points or [])}
    points: list[dict[str, Any]] = []
    for position in range(length):
        control = domain["controlPoints"][position]
        state_point = by_id.get(str(control["id"]))
        raw_value = (
            float(state_point["value"]) if state_point is not None else float(control["baseValue"])
        )
        unit = (
            state_point.get("unit", variable.get("unit"))
            if state_point is not None
            else variable.get("unit")
        )
        point: dict[str, Any] = {
            "id": str(control["id"]),
            "valueSI": _to_si(str(variable["id"]), raw_value, unit),
            "rawValue": raw_value,
        }
        if unit is not None:
            point["unit"] = str(unit)
        points.append(point)
    return points


def flatten_design_state(space: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic unit-normalized view consumed by search/optimization code."""
    validate_design_space(space)
    violations = preflight_design_state(space, state)
    if violations:
        raise DesignSpaceError(f"DESIGN_SPACE_PREFLIGHT_FAILED:{'; '.join(violations)}")
    index = _index(space)
    active = set(active_variable_ids(space, state))
    entries: list[dict[str, Any]] = []
    for variable in space["variables"]:
        variable_id = str(variable["id"])
        is_active = variable_id in active
        base: dict[str, Any] = {
            "id": variable_id,
            "kind": variable["kind"],
            "active": is_active,
            "provided": variable_id in state,
            "lineage": [] if is_active else [variable_id],
            "bindings": list(variable["bindings"]),
        }
        if variable.get("unit") is not None:
            base["unit"] = variable["unit"]
        if not is_active:
            entries.append(base)
            continue
        if variable["kind"] == "vector-profile":
            base["points"] = _flat_profile_points(variable, index, state)
            entries.append(base)
            continue
        resolved = _resolve_value(variable, index, state)
        raw = resolved.get("raw")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            base["value"] = raw
            base["valueSI"] = resolved.get("value_si")
        else:
            base["value"] = raw
        entries.append(base)
    order = [entry["id"] for entry in entries if entry["active"]]
    inactive = [entry["id"] for entry in entries if not entry["active"]]
    return {"spaceId": space["id"], "order": order, "entries": entries, "inactive": inactive}


def unflatten_design_state(space: Mapping[str, Any], flat: Mapping[str, Any]) -> dict[str, Any]:
    """Reverse a flattened view back into hierarchical design state."""
    index = _index(space)
    result: dict[str, Any] = {}
    for entry in flat["entries"]:
        if not entry["provided"]:
            continue
        kind = entry["kind"]
        if kind in {"linked", "derived"}:
            continue
        variable_id = str(entry["id"])
        if variable_id not in index:
            raise DesignSpaceError(f"UNKNOWN_VARIABLE:{variable_id}")
        if kind == "vector-profile":
            points = []
            for point in entry.get("points", ()):
                rebuilt: dict[str, Any] = {"id": point["id"], "value": point["rawValue"]}
                if point.get("unit") is not None:
                    rebuilt["unit"] = point["unit"]
                points.append(rebuilt)
            result[variable_id] = {"kind": "vector-profile", "points": points}
        elif kind == "categorical":
            result[variable_id] = {"kind": "categorical", "value": str(entry["value"])}
        elif kind == "boolean":
            result[variable_id] = {"kind": "boolean", "value": bool(entry["value"])}
        elif entry.get("unit") is not None:
            result[variable_id] = {
                "kind": "number",
                "value": float(entry["value"]),
                "unit": entry["unit"],
            }
        else:
            result[variable_id] = {"kind": "dimensionless", "value": float(entry["value"])}
    return result


def candidate_hash(flat: Mapping[str, Any]) -> str:
    """Stable hash of the active evaluation view; key order and units do not matter."""
    by_id = {entry["id"]: entry for entry in flat["entries"]}
    variables: list[dict[str, Any]] = []
    for variable_id in flat["order"]:
        entry = by_id[variable_id]
        payload: dict[str, Any] = {"id": entry["id"], "kind": entry["kind"]}
        if entry.get("unit") is not None:
            payload["unit"] = entry["unit"]
        if "valueSI" in entry:
            payload["valueSI"] = entry["valueSI"]
        if entry["kind"] in {"categorical", "boolean"} and "value" in entry:
            payload["value"] = entry["value"]
        if "points" in entry:
            payload["points"] = [
                {"id": point["id"], "valueSI": point["valueSI"]} for point in entry["points"]
            ]
        variables.append(payload)
    return content_digest({"space": flat["spaceId"], "variables": variables})


def numeric_vector(flat: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    """Stable ``(id, valueSI)`` vector of active numeric variables for search drivers."""
    by_id = {entry["id"]: entry for entry in flat["entries"]}
    vector: list[tuple[str, float]] = []
    for variable_id in flat["order"]:
        entry = by_id[variable_id]
        value_si = entry.get("valueSI")
        if isinstance(value_si, (int, float)) and not isinstance(value_si, bool):
            vector.append((variable_id, float(value_si)))
    return tuple(vector)
