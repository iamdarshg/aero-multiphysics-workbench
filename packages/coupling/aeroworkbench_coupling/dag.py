"""Deterministic computation DAG from design state plus participant declarations.

Nodes represent analytical models, geometry, mesh, native-solver analyses,
scalar transformations, field coupling, post-processing, and quality checks.
Edges carry typed unit-bearing values (or artifact references); every node
execution is keyed by a content hash and served from an immutable
content-addressed cache. Only invalidated descendants re-run: design-section
changes map through ``CHANGE_IMPACT`` (kept in parity with
``packages/schema/src/design.ts``) to the node families they invalidate, and
unknown sections fail closed by invalidating everything.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite

# Parity with packages/schema/src/design.ts CHANGE_IMPACT. The TS table maps
# changed design sections to invalidated downstream node families; this copy
# must carry the same section keys (checked by test).
CHANGE_IMPACT: dict[str, tuple[str, ...]] = {
    "parameters": ("geometry", "mesh", "analysis", "objectives"),
    "parameterRevision": ("geometry", "mesh", "analysis", "objectives"),
    "geometry": ("geometry", "mesh", "analysis", "interfaces", "objectives"),
    "semantics": ("mesh", "analysis", "interfaces", "objectives"),
    "materials": ("mesh", "structural", "thermal", "electromagnetic", "objectives"),
    "operatingPoints": ("analysis", "objectives"),
    "objectives": ("optimization",),
    "constraints": ("optimization", "validation"),
    "solverPolicy": ("analysis",),
    "participantSolvers": ("analysis",),
    "coupling": ("coupled-analysis", "convergence"),
    "computePolicy": ("scheduling",),
    "fidelityPolicy": ("analysis", "optimization"),
    "motionFrames": ("mesh", "analysis", "interfaces"),
    "interfaces": ("coupled-analysis", "mesh"),
}

#: Node kinds the DAG accepts. Families are free-form downstream labels that
#: must intersect the CHANGE_IMPACT vocabulary for invalidation to be precise.
NODE_KINDS = (
    "analytical",
    "geometry",
    "mesh",
    "native-analysis",
    "transform",
    "field-coupling",
    "post",
    "quality",
)


def invalidated_families(changed_sections: tuple[str, ...]) -> tuple[str, ...]:
    """Map changed design sections to invalidated node families.

    Unknown sections fail closed by invalidating everything (``("all",)``).
    """
    invalidated: set[str] = set()
    for section in changed_sections:
        impact = CHANGE_IMPACT.get(section)
        if impact is None:
            return ("all",)
        invalidated.update(impact)
    return tuple(sorted(invalidated))


def _canonical(value: object) -> object:
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("NONFINITE_DAG_VALUE")
        return 0.0 if value == 0 else value
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    return value


def content_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class ContentCache[T]:
    """Immutable content-addressed cache mirroring the TS contract."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str, T]] = {}

    def put(self, key: str, value: T) -> None:
        import re

        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("CACHE_KEY_MUST_BE_SHA256")
        canonical = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"))
        existing = self._entries.get(key)
        if existing is not None and existing[0] != canonical:
            raise ValueError(f"content-addressed cache entry {key} is immutable")
        if existing is None:
            import copy

            self._entries[key] = (canonical, copy.deepcopy(value))

    def get(self, key: str) -> T | None:
        import copy

        entry = self._entries.get(key)
        return copy.deepcopy(entry[1]) if entry is not None else None

    def drop(self, key: str) -> None:
        self._entries.pop(key, None)


@dataclass(frozen=True, slots=True)
class NodeSpec:
    node_id: str
    kind: str
    family: str
    upstream: tuple[str, ...]
    solver: tuple[str, str]
    settings: Mapping[str, object]
    base_inputs: tuple[str, ...] = ()
    """Names of base content hashes this node depends on (e.g. "geometry",
    "semantic", "material"). Only these enter the content key, so unrelated
    design changes do not invalidate the node."""

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("NODE_ID_REQUIRED")
        if self.kind not in NODE_KINDS:
            raise ValueError(f"UNKNOWN_NODE_KIND:{self.kind}")
        if not self.family.strip():
            raise ValueError("NODE_FAMILY_REQUIRED")
        if self.node_id in self.upstream:
            raise ValueError(f"SELF_DEPENDENT_NODE:{self.node_id}")
        if not self.solver[0].strip() or not self.solver[1].strip():
            raise ValueError("NODE_SOLVER_IDENTITY_REQUIRED")


@dataclass(frozen=True, slots=True)
class NodeResult:
    node_id: str
    key: str
    cached: bool
    value: object
    unit: str
    input_hash: str
    detail: str


# NodeFunction receives resolved upstream NodeResults and returns (value, unit).
NodeFunction = Callable[[Mapping[str, NodeResult]], tuple[object, str]]


class ComputationDAG:
    """Deterministic content-addressed execution graph."""

    def __init__(self, functions: Mapping[str, NodeFunction]) -> None:
        self._functions = dict(functions)
        self._nodes: dict[str, NodeSpec] = {}
        self._cache: ContentCache[tuple[object, str]] = ContentCache()

    def add(self, node: NodeSpec) -> None:
        if node.node_id in self._nodes:
            raise ValueError(f"DUPLICATE_NODE:{node.node_id}")
        if node.node_id not in self._functions:
            raise ValueError(f"NODE_FUNCTION_MISSING:{node.node_id}")
        self._nodes[node.node_id] = node

    def _order(self) -> tuple[str, ...]:
        ordered: list[str] = []
        visited: dict[str, str] = {}
        def visit(node_id: str) -> None:
            state = visited.get(node_id)
            if state == "done":
                return
            if state == "visiting":
                raise ValueError(f"CYCLIC_DAG:{node_id}")
            if node_id not in self._nodes:
                raise ValueError(f"UNKNOWN_UPSTREAM_NODE:{node_id}")
            visited[node_id] = "visiting"
            for upstream in sorted(self._nodes[node_id].upstream):
                visit(upstream)
            visited[node_id] = "done"
            ordered.append(node_id)
        for node_id in sorted(self._nodes):
            visit(node_id)
        return tuple(ordered)

    def execute(
        self,
        base_hashes: Mapping[str, str],
        changed_sections: tuple[str, ...] = (),
    ) -> dict[str, NodeResult]:
        import re

        for name, digest in base_hashes.items():
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"INVALID_BASE_HASH:{name}")
        invalidated = set(invalidated_families(changed_sections))
        invalidate_all = "all" in invalidated
        receipts: dict[str, NodeResult] = {}
        for node_id in self._order():
            node = self._nodes[node_id]
            upstream_keys = [receipts[upstream].key for upstream in sorted(node.upstream)]
            try:
                relevant_base = {name: base_hashes[name] for name in node.base_inputs}
            except KeyError as exc:
                raise ValueError(f"NODE_MISSING_BASE_HASH:{node_id}:{exc.args[0]}") from None
            key = content_digest(
                {
                    "node": node.node_id,
                    "kind": node.kind,
                    "solver": list(node.solver),
                    "settings": dict(node.settings),
                    "base": relevant_base,
                    "upstream": upstream_keys,
                }
            )
            must_recompute = invalidate_all or node.family in invalidated
            if must_recompute:
                self._cache.drop(key)
            hit = None if must_recompute else self._cache.get(key)
            if hit is not None:
                value, unit = hit
                receipts[node_id] = NodeResult(
                    node_id, key, True, value, unit, key,
                    "cache hit; inputs unchanged",
                )
                continue
            deps = {upstream: receipts[upstream] for upstream in node.upstream}
            value, unit = self._functions[node_id](deps)
            if not unit.strip():
                raise ValueError(f"NODE_UNIT_REQUIRED:{node_id}")
            self._cache.put(key, (value, unit))
            receipts[node_id] = NodeResult(
                node_id, key, False, value, unit, key,
                f"computed with {node.solver[0]} {node.solver[1]}",
            )
        return receipts
