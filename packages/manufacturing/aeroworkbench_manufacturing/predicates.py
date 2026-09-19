"""Safe predicate evaluation over a flattened design state.

The predicate AST is the *same* typed AST used by the canonical design space
(``equals``/``in``/``lessThan``/``lessOrEqual``/``greaterThan``/
``greaterOrEqual``/``all``/``any``/``not``). No user-provided code is executed
and unknown variables fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aeroworkbench_optimization.design_space import active_variable_ids

__all__ = ["PredicateError", "evaluate_predicate", "flatten_index", "predicate_variables"]


class PredicateError(ValueError):
    """Raised when a predicate references unknown data or a bad operand."""


def flatten_index(flat: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Index a flattened design state by variable id."""

    entries = flat.get("entries")
    if not isinstance(entries, list):
        raise PredicateError("FLAT_STATE_ENTRIES_REQUIRED")
    return {str(entry["id"]): entry for entry in entries}


def predicate_variables(predicate: Mapping[str, Any]) -> tuple[str, ...]:
    op = predicate.get("op")
    if op in {"all", "any"}:
        found: list[str] = []
        for clause in predicate.get("clauses", ()):
            found.extend(predicate_variables(clause))
        return tuple(found)
    if op == "not":
        return predicate_variables(predicate["clause"])
    return (str(predicate["variable"]),)


def _entry_value(entry: Mapping[str, Any]) -> Any:
    return entry.get("value")


def _entry_si(entry: Mapping[str, Any]) -> float:
    value = entry.get("valueSI")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PredicateError(f"COMPARISON_NEEDS_NUMERIC:{entry.get('id')}")
    return float(value)


def evaluate_predicate(
    predicate: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]]
) -> bool:
    """Evaluate a safe predicate against an indexed flat design state."""

    return _evaluate(predicate, index, depth=0)


def _evaluate(
    predicate: Mapping[str, Any],
    index: Mapping[str, Mapping[str, Any]],
    *,
    depth: int,
) -> bool:
    if depth > 64:
        raise PredicateError("PREDICATE_DEPTH_EXCEEDED")
    op = predicate.get("op")
    if op in {"all", "any"}:
        clauses = [dict(clause) for clause in predicate.get("clauses", ())]
        if op == "all":
            return all(_evaluate(clause, index, depth=depth + 1) for clause in clauses)
        return any(_evaluate(clause, index, depth=depth + 1) for clause in clauses)
    if op == "not":
        return not _evaluate(predicate["clause"], index, depth=depth + 1)
    variable_id = str(predicate.get("variable"))
    entry = index.get(variable_id)
    if entry is None:
        raise PredicateError(f"PREDICATE_UNKNOWN_VARIABLE:{variable_id}")
    if op in {"equals", "in"}:
        wanted = [predicate.get("value")] if op == "equals" else list(predicate.get("values", ()))
        actual = _entry_value(entry)
        return any(actual == value for value in wanted)
    if op in {"lessThan", "lessOrEqual", "greaterThan", "greaterOrEqual"}:
        value_si = _entry_si(entry)
        limit = float(predicate["valueSI"])
        if op == "lessThan":
            return value_si < limit
        if op == "lessOrEqual":
            return value_si <= limit
        if op == "greaterThan":
            return value_si > limit
        return value_si >= limit
    raise PredicateError(f"UNKNOWN_PREDICATE_OP:{op}")


def active_design_variables(space: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[str, ...]:
    """Re-export the canonical activation query for callers that need it."""

    return active_variable_ids(space, state)
