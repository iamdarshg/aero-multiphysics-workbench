"""Parameter dependency graph for generic parametric geometry.

Parameters are scalar millimetre values. A parameter is either a literal or a
safe expression over other parameters. Cycles and unknown names fail closed.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Load,
    ast.Name,
    ast.Constant,
    ast.Call,
    ast.Tuple,
    ast.List,
)

_ALLOWED_CALLS = ("min", "max", "abs")


def _dependencies(expression: str) -> tuple[str, ...]:
    tree = ast.parse(expression, mode="eval")
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"PARAMETER_EXPRESSION_FORBIDDEN:{type(node).__name__}")
        if isinstance(node, ast.Call):
            func = node.func
            if not isinstance(func, ast.Name) or func.id not in _ALLOWED_CALLS:
                raise ValueError("PARAMETER_EXPRESSION_CALL_FORBIDDEN")
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_CALLS:
            names.append(node.id)
    return tuple(dict.fromkeys(names))


def _evaluate(expression: str, values: dict[str, float]) -> float:
    tree = ast.parse(expression, mode="eval")

    def _node(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _node(node.body)
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("PARAMETER_EXPRESSION_CONSTANT_INVALID")
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_CALLS:
                raise ValueError("PARAMETER_EXPRESSION_CALL_MISPLACED")
            try:
                return values[node.id]
            except KeyError as exc:
                raise ValueError(f"UNKNOWN_PARAMETER:{node.id}") from exc
        if isinstance(node, ast.BinOp):
            left, right = _node(node.left), _node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return float(pow(left, right))
            if isinstance(node.op, ast.Mod):
                return left % right
            raise ValueError("PARAMETER_EXPRESSION_OPERATOR_FORBIDDEN")
        if isinstance(node, ast.UnaryOp):
            operand = _node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError("PARAMETER_EXPRESSION_OPERATOR_FORBIDDEN")
        if isinstance(node, ast.Call):
            func = node.func
            assert isinstance(func, ast.Name)
            args = [_node(arg) for arg in node.args]
            if func.id == "min":
                return float(min(args))
            if func.id == "max":
                return float(max(args))
            if func.id == "abs" and len(args) == 1:
                return float(abs(args[0]))
            raise ValueError("PARAMETER_EXPRESSION_CALL_FORBIDDEN")
        raise ValueError(f"PARAMETER_EXPRESSION_FORBIDDEN:{type(node).__name__}")

    result = _node(tree)
    if not isfinite(result):
        raise ValueError("PARAMETER_VALUE_NOT_FINITE")
    return result


@dataclass(frozen=True, slots=True)
class ParameterDef:
    """One named scalar parameter with an optional dependency expression."""

    name: str
    value: float | None = None
    expression: str | None = None
    unit: str = "mm"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PARAMETER_NAME_REQUIRED")
        if (self.value is None) == (self.expression is None):
            raise ValueError("PARAMETER_NEEDS_VALUE_XOR_EXPRESSION")
        if self.value is not None and not isfinite(self.value):
            raise ValueError("PARAMETER_VALUE_NOT_FINITE")
        if self.expression is not None:
            _dependencies(self.expression)


@dataclass(frozen=True, slots=True)
class ParameterSet:
    """Immutable ordered parameter definitions with a dependency graph."""

    definitions: tuple[ParameterDef, ...]

    def __post_init__(self) -> None:
        names = [item.name for item in self.definitions]
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_PARAMETER")

    def dependency_edges(self) -> dict[str, tuple[str, ...]]:
        """Map each parameter to the parameters it depends on."""

        edges: dict[str, tuple[str, ...]] = {}
        for item in self.definitions:
            edges[item.name] = (
                _dependencies(item.expression) if item.expression else ()
            )
        known = set(edges)
        for name, deps in edges.items():
            for dep in deps:
                if dep not in known:
                    raise ValueError(f"UNKNOWN_PARAMETER:{dep}-in-{name}")
                if dep == name:
                    raise ValueError(f"PARAMETER_SELF_DEPENDENCY:{name}")
        # Cycle detection via DFS.
        visiting: set[str] = set()
        visited: set[str] = set()

        def _visit(node: str, stack: tuple[str, ...]) -> None:
            if node in visited:
                return
            if node in visiting:
                raise ValueError(
                    f"PARAMETER_CYCLE:{'->'.join((*stack, node))}"
                )
            visiting.add(node)
            for dep in edges[node]:
                _visit(dep, (*stack, node))
            visiting.discard(node)
            visited.add(node)

        for name in edges:
            _visit(name, ())
        return edges

    def resolve(self) -> dict[str, float]:
        """Evaluate all parameters in dependency order (values in mm)."""

        edges = self.dependency_edges()
        resolved: dict[str, float] = {}
        literals = {item.name: item.value for item in self.definitions}
        expressions = {
            item.name: item.expression
            for item in self.definitions
            if item.expression is not None
        }
        pending = dict(expressions)
        for name, value in literals.items():
            if value is not None:
                resolved[name] = float(value)
        while pending:
            progressed = False
            for name, expression in list(pending.items()):
                assert expression is not None
                if all(dep in resolved for dep in edges[name]):
                    resolved[name] = _evaluate(expression, resolved)
                    del pending[name]
                    progressed = True
            if not progressed:  # pragma: no cover - guarded by cycle check
                raise ValueError("PARAMETER_RESOLUTION_STALLED")
        return dict(sorted(resolved.items()))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "parameters": [
                {
                    "name": item.name,
                    "value": item.value,
                    "expression": item.expression,
                    "unit": item.unit,
                }
                for item in sorted(self.definitions, key=lambda d: d.name)
            ]
        }


def parameter_digest(parameters: ParameterSet) -> str:
    encoded = json.dumps(
        parameters.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
