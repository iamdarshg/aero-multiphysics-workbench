"""Hierarchical coupled simulation over recursive physical assemblies.

Acyclic assembly levels execute through :class:`ComputationDAG` (ordering,
parallel leaves, upstream-failure propagation). Link cycles that a DAG cannot
express converge through explicit Gauss-Seidel fixed-point sweeps. Leaf reuse
across runs is content-addressed; prior coupled states only warm-start new
solves and never count as verified reuse. Native models fail closed unless a
matching capability is present.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Literal

from aeroworkbench_core.assembly import ChildFailure, evaluate_requirements, limiting_fidelity
from aeroworkbench_core.composition import (
    AssemblyFidelity,
    SystemRecord,
    check_compatible,
    check_feed_compatible,
    convert_unit,
    units_compatible,
)
from aeroworkbench_core.physical import contract_digest

from .dag import ComputationDAG, ContentCache, NodeResult, NodeSpec

SOFTWARE_IDENTITY = "aeroworkbench-coupling-hierarchy"
SOFTWARE_VERSION = "1.0.0"

CacheReason = Literal[
    "hit_exact", "warm_start", "miss_input_changed", "miss_boundary_changed",
    "miss_solver_changed", "miss_mesh_changed", "miss_interface_changed",
    "miss_validity_policy_changed", "miss_harmonic_basis_changed",
]
ResultStatus = Literal["converged", "partial", "failed"]
_HEX = frozenset("0123456789abcdef")


class CapabilityUnavailable(Exception):
    def __init__(self, requirement: str) -> None:
        super().__init__(f"NATIVE_CAPABILITY_UNAVAILABLE:{requirement}")
        self.requirement = requirement


def require_capability(requirement: str, *, present: bool) -> None:
    if not requirement.strip():
        raise ValueError("CAPABILITY_REQUIREMENT_REQUIRED")
    if not present:
        raise CapabilityUnavailable(requirement)


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64 or any(c not in _HEX for c in value):
        raise ValueError(f"HIERARCHY_DIGEST_INVALID:{name}")


def hierarchy_cache_key(
    *,
    subtree_digest: str,
    qoi: tuple[str, ...] = (),
    boundary_digest: str,
    solver: tuple[str, str],
    settings: Mapping[str, Any] | None = None,
    fidelity: str = "analytical",
    validity_policy: str = "v1",
    mesh_digest: str | None = None,
    interface_digest: str | None = None,
    harmonic_digest: str | None = None,
    temporal_digest: str | None = None,
) -> str:
    _require_digest("subtree", subtree_digest)
    _require_digest("boundary", boundary_digest)
    for name, value in (("mesh", mesh_digest), ("interface", interface_digest),
                        ("harmonic", harmonic_digest), ("temporal", temporal_digest)):
        if value is not None:
            _require_digest(name, value)
    if not solver[0].strip() or not solver[1].strip():
        raise ValueError("HIERARCHY_SOLVER_IDENTITY_REQUIRED")
    if fidelity not in ("analytical", "surrogate", "benchmark", "native"):
        raise ValueError("HIERARCHY_FIDELITY_UNKNOWN")
    if not validity_policy.strip():
        raise ValueError("HIERARCHY_VALIDITY_POLICY_REQUIRED")
    try:
        return contract_digest({
            "subtree": subtree_digest, "qoi": list(qoi), "boundary": boundary_digest,
            "solver": [solver[0], solver[1]], "settings": dict(settings or {}),
            "fidelity": fidelity, "validityPolicy": validity_policy,
            "mesh": mesh_digest, "interface": interface_digest,
            "harmonic": harmonic_digest, "temporal": temporal_digest,
        })
    except (TypeError, ValueError) as exc:
        raise ValueError(f"HIERARCHY_KEY_UNCANONICAL:{exc}") from exc


_AXIS_REASON: tuple[tuple[str, CacheReason], ...] = (
    ("solver", "miss_solver_changed"),
    ("boundary", "miss_boundary_changed"),
    ("mesh", "miss_mesh_changed"),
    ("interface", "miss_interface_changed"),
    ("harmonic", "miss_harmonic_basis_changed"),
    ("validity", "miss_validity_policy_changed"),
)


def classify_miss(
    previous: Mapping[str, str], current: Mapping[str, str],
) -> CacheReason:
    for axis, reason in _AXIS_REASON:
        if previous.get(axis) != current.get(axis):
            return reason
    return "miss_input_changed"


@dataclass(frozen=True, slots=True)
class CacheOutcome:
    status: Literal["hit_exact", "warm_start", "miss"]
    reason: CacheReason
    key: str
    detail: str = ""


class SingleFlightCache[T]:
    def __init__(self) -> None:
        self._entries: dict[str, T] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self._computations = 0

    @property
    def computations(self) -> int:
        with self._guard:
            return self._computations

    def compute_if_absent(self, key: str, factory: Callable[[], T]) -> T:
        _require_digest("single-flight key", key)
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            with self._guard:
                if key in self._entries:
                    return deepcopy(self._entries[key])
            value = factory()
            with self._guard:
                if key not in self._entries:
                    self._entries[key] = deepcopy(value)
                    self._computations += 1
                return deepcopy(self._entries[key])


@dataclass(frozen=True, slots=True)
class LeafModel:
    system_id: str
    fn: Callable[[Mapping[str, float]], Mapping[str, float]]
    outputs: dict[str, str] = field(default_factory=dict)
    native: bool = False
    solver: tuple[str, str] = ("analytical", "1")
    parameters: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.system_id.strip():
            raise ValueError("LEAF_MODEL_ID_REQUIRED")
        if not self.solver[0].strip() or not self.solver[1].strip():
            raise ValueError("LEAF_MODEL_SOLVER_REQUIRED")
        for key, value in self.parameters.items():
            if not key.strip() or not isfinite(value):
                raise ValueError("LEAF_MODEL_PARAMETER_INVALID")
        object.__setattr__(self, "outputs", dict(self.outputs))
        object.__setattr__(self, "parameters", dict(self.parameters))


@dataclass(frozen=True, slots=True)
class HierarchicalResult:
    system_id: str
    revision: str
    status: ResultStatus
    values: dict[str, float] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    source: str = "analytical"
    fidelity: AssemblyFidelity = "analytical"
    validity_passed: bool = False
    checks: dict[str, bool] = field(default_factory=dict)
    inputs_hash: str = ""
    software: tuple[str, str] = (SOFTWARE_IDENTITY, SOFTWARE_VERSION)
    provenance_id: str = ""
    detail: str = ""
    cache_reason: CacheReason = "miss_input_changed"
    cache_key: str = ""
    children: tuple[HierarchicalResult, ...] = ()
    receipts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", dict(self.values))
        object.__setattr__(self, "units", dict(self.units))
        object.__setattr__(self, "checks", dict(self.checks))
        object.__setattr__(self, "children", tuple(self.children))
        object.__setattr__(self, "receipts", tuple(self.receipts))

    def as_dict(self) -> dict[str, Any]:
        return {
            "systemId": self.system_id, "revision": self.revision, "status": self.status,
            "values": dict(self.values), "units": dict(self.units),
            "source": self.source, "fidelity": self.fidelity,
            "validityPassed": self.validity_passed, "checks": dict(self.checks),
            "inputsHash": self.inputs_hash,
            "software": {"name": self.software[0], "version": self.software[1]},
            "provenanceId": self.provenance_id, "detail": self.detail,
            "cacheReason": self.cache_reason, "cacheKey": self.cache_key,
            "children": [c.as_dict() for c in self.children],
            "receipts": list(self.receipts),
        }


_SOURCE_RANK = {"analytical": 0, "surrogate": 1, "benchmark": 2, "native_solver": 3}


def validate_links(record: SystemRecord) -> None:
    members = {record.system_id: record}
    for child in record.children:
        members[child.system_id] = child
    ports = {sid: {p.port_id: p for p in node.ports} for sid, node in members.items()}
    for link in record.links:
        source = ports[link.source_system][link.source_port]
        target = ports[link.target_system][link.target_port]
        if link.target_system == record.system_id:
            raise ValueError("LINK_TO_PARENT_USE_BINDING")
        if link.source_system == record.system_id:
            check_feed_compatible(source, target, transform=link.transform)
        else:
            check_compatible(source, target, transform=link.transform)
    for child in record.children:
        validate_links(child)


class HierarchicalSimulator:
    def __init__(
        self,
        record: SystemRecord,
        models: Mapping[str, LeafModel],
        *,
        software: tuple[str, str] = (SOFTWARE_IDENTITY, SOFTWARE_VERSION),
        tolerance: float = 1e-9,
        max_iterations: int = 200,
        relaxation: float = 1.0,
    ) -> None:
        if not software[0].strip() or not software[1].strip():
            raise ValueError("HIERARCHY_SOFTWARE_IDENTITY_REQUIRED")
        if not isfinite(tolerance) or tolerance <= 0:
            raise ValueError("HIERARCHY_TOLERANCE_INVALID")
        if max_iterations < 1:
            raise ValueError("HIERARCHY_MAX_ITERATIONS_INVALID")
        if not isfinite(relaxation) or not 0.0 < relaxation <= 1.0:
            raise ValueError("HIERARCHY_RELAXATION_INVALID")
        leaves = {node.system_id: node for node in record.leaves()}
        for system_id, model in models.items():
            if system_id not in leaves:
                if record.find(system_id) is None:
                    raise ValueError(f"MODEL_UNKNOWN_SYSTEM:{system_id}")
                raise ValueError(f"MODEL_FOR_ASSEMBLY:{system_id}")
            node = leaves[system_id]
            if model.native != (node.fidelity == "native"):
                raise ValueError(f"MODEL_FIDELITY_MISMATCH:{system_id}")
            out_ports = {p.port_id: p for p in node.ports if p.direction == "out"}
            if set(model.outputs) != set(out_ports):
                raise ValueError(f"MODEL_PORT_MISMATCH:{system_id}")
            for port_id, unit in model.outputs.items():
                port = out_ports[port_id]
                if unit != port.unit and not units_compatible(unit, port.unit):
                    raise ValueError(f"MODEL_UNIT_MISMATCH:{system_id}:{port_id}")
        missing = [sid for sid in leaves if sid not in models]
        if missing:
            raise ValueError(f"MODEL_MISSING:{missing[0]}")
        self._record = record
        self._models = dict(models)
        self._software = software
        self._tolerance = tolerance
        self._max_iterations = max_iterations
        self._relaxation = relaxation
        self._lock = threading.RLock()
        self._node_cache: ContentCache[tuple[dict[str, float], dict[str, str]]] = ContentCache()
        self._last_axes: dict[str, dict[str, str]] = {}
        self._warm_states: dict[str, dict[tuple[str, str], float]] = {}
        self._flight: SingleFlightCache[HierarchicalResult] = SingleFlightCache()

    def evaluate(
        self,
        boundary: Mapping[str, float],
        *,
        capabilities: Mapping[str, bool] | None = None,
        validity_policy: str = "v1",
        qoi: tuple[str, ...] = (),
    ) -> HierarchicalResult:
        for key, value in boundary.items():
            if not key.strip() or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"BOUNDARY_INVALID:{key}")
        validate_links(self._record)
        gates = dict(capabilities or {})
        for system_id, model in self._models.items():
            if model.native and not gates.get(system_id, False):
                raise CapabilityUnavailable(system_id)
        if not validity_policy.strip():
            raise ValueError("HIERARCHY_VALIDITY_POLICY_REQUIRED")
        boundary_digest = contract_digest({k: float(boundary[k]) for k in sorted(boundary)})
        root_key = hierarchy_cache_key(
            subtree_digest=self._record.subtree_digest, qoi=tuple(qoi),
            boundary_digest=boundary_digest, solver=self._software, settings={},
            fidelity=limiting_fidelity(self._record), validity_policy=validity_policy,
            interface_digest=contract_digest(sorted(link.digest for link in self._record.links)),
        )
        return self._flight.compute_if_absent(
            root_key,
            lambda: self._eval_assembly(
                self._record, {k: float(v) for k, v in boundary.items()},
                validity_policy, tuple(qoi)),
        )

    def _consume_key_axes(
        self, node_id: str, axes: dict[str, str], key: str,
    ) -> CacheOutcome:
        with self._lock:
            previous = self._last_axes.get(node_id)
            self._last_axes[node_id] = dict(axes)
        if previous is None:
            return CacheOutcome("miss", "miss_input_changed", key, "first evaluation")
        if self._node_cache.get(key) is not None:
            return CacheOutcome("hit_exact", "hit_exact", key, "inputs unchanged")
        return CacheOutcome("miss", classify_miss(previous, axes), key, "inputs changed")

    def _eval_node(
        self, node: SystemRecord, boundary: Mapping[str, float],
        validity_policy: str, qoi: tuple[str, ...],
    ) -> HierarchicalResult:
        if node.is_leaf:
            return self._eval_leaf(node, boundary, validity_policy, qoi)
        return self._eval_assembly(node, boundary, validity_policy, qoi)

    def _eval_leaf(
        self, node: SystemRecord, boundary: Mapping[str, float],
        validity_policy: str, qoi: tuple[str, ...],
    ) -> HierarchicalResult:
        model = self._models[node.system_id]
        in_ports = [p for p in node.ports if p.direction == "in"]
        missing = [p.port_id for p in in_ports if p.port_id not in boundary]
        if missing:
            return self._failed(node, f"MODEL_INPUT_MISSING:{missing[0]}", "", validity_policy)
        consumed = {p.port_id: float(boundary[p.port_id]) for p in in_ports}
        axes = {
            "solver": f"{model.solver[0]}@{model.solver[1]}",
            "boundary": contract_digest(consumed),
            "mesh": node.geometry_digest or "none",
            "interface": contract_digest(sorted(link.digest for link in node.links)),
            "harmonic": "none", "validity": validity_policy,
            "input": contract_digest({"rev": node.revision, "qoi": list(qoi)}),
        }
        key = hierarchy_cache_key(
            subtree_digest=node.subtree_digest, qoi=tuple(qoi),
            boundary_digest=axes["boundary"], solver=model.solver,
            settings={"revision": node.revision, "parameters": dict(model.parameters)},
            fidelity=node.fidelity,
            validity_policy=validity_policy,
            interface_digest=axes["interface"] if node.links else None,
        )
        with self._lock:
            cached = self._node_cache.get(key)
        if cached is not None:
            values, units = cached
            with self._lock:
                self._last_axes[node.system_id] = dict(axes)
            return self._seal(node, values, units, "converged", key,
                              CacheOutcome("hit_exact", "hit_exact", key, "inputs unchanged"),
                              (), validity_policy, ())
        outcome = self._consume_key_axes(node.system_id, axes, key)
        try:
            produced = dict(model.fn(dict(consumed)))
        except ChildFailure as exc:
            return self._failed(node, f"CHILD_FAILED:{exc.system_id}:{exc.reason}",
                                exc.detail, validity_policy, outcome=outcome, key=key)
        except Exception as exc:
            return self._failed(node, f"MODEL_FAILED:{node.system_id}", str(exc),
                                validity_policy, outcome=outcome, key=key)
        out_ports = {p.port_id: p for p in node.ports if p.direction == "out"}
        if set(produced) != set(out_ports):
            return self._failed(node, f"MODEL_PORT_MISMATCH:{node.system_id}", "",
                                validity_policy, outcome=outcome, key=key)
        values = {}
        units = {}
        for port_id, raw in produced.items():
            if not isinstance(raw, (int, float)) or not isfinite(raw):
                return self._failed(node, f"VALUE_NONFINITE:{node.system_id}:{port_id}", "",
                                    validity_policy, outcome=outcome, key=key)
            values[port_id] = convert_unit(float(raw), model.outputs[port_id],
                                           out_ports[port_id].unit)
            units[port_id] = out_ports[port_id].unit
        with self._lock:
            self._node_cache.put(key, (values, units))
        return self._seal(node, values, units, "converged", key, outcome, (), validity_policy, ())

    def _seal(
        self, node: SystemRecord, values: Mapping[str, float], units: Mapping[str, str],
        status: ResultStatus, key: str, outcome: CacheOutcome,
        children: tuple[HierarchicalResult, ...], validity_policy: str,
        receipts: tuple[str, ...],
    ) -> HierarchicalResult:
        verdict = evaluate_requirements(node, values)
        source: str
        if node.is_leaf:
            model = self._models[node.system_id]
            source = "native_solver" if model.native else node.fidelity
        else:
            rank = min([_SOURCE_RANK[c.source] for c in children] or [0])
            by_rank = {value: name for name, value in _SOURCE_RANK.items()}
            source = by_rank[rank]
        fidelity = node.fidelity if node.is_leaf else limiting_fidelity(node)
        provenance_id = contract_digest({
            "key": key, "software": [self._software[0], self._software[1]],
            "validityPolicy": validity_policy, "status": status,
        })
        detail = verdict.detail
        if status == "failed" and not detail:
            detail = "node failed"
        return HierarchicalResult(
            system_id=node.system_id, revision=node.revision, status=status,
            values=dict(values), units=dict(units), source=source, fidelity=fidelity,
            validity_passed=verdict.passed if status == "converged" else False,
            checks=dict(verdict.checks), inputs_hash=key,
            software=self._software, provenance_id=provenance_id, detail=detail,
            cache_reason=outcome.reason, cache_key=key, children=tuple(children),
            receipts=tuple(receipts),
        )

    def _failed(
        self, node: SystemRecord, reason: str, detail: str, validity_policy: str,
        *, outcome: CacheOutcome | None = None, key: str = "",
    ) -> HierarchicalResult:
        resolved_key = key or contract_digest(
            {"failed": node.system_id, "reason": reason, "rev": node.revision})
        resolved = outcome or CacheOutcome("miss", "miss_input_changed", resolved_key, reason)
        receipts = (reason,) if not detail else (reason, detail)
        return self._seal(node, {}, {}, "failed", resolved_key, resolved, (),
                          validity_policy, receipts)

    def _eval_assembly(
        self, node: SystemRecord, boundary: Mapping[str, float],
        validity_policy: str, qoi: tuple[str, ...],
    ) -> HierarchicalResult:
        ports = {p.port_id: p for p in node.ports}
        members = {node.system_id: node}
        for child in node.children:
            members[child.system_id] = child
        lookup = {sid: {p.port_id: p for p in member.ports} for sid, member in members.items()}
        try:
            receipts, produced = self._run_dag(node, boundary, validity_policy, qoi)
        except ValueError as exc:
            if "CYCLIC_DAG" not in str(exc):
                raise
            return self._eval_cyclic(node, boundary, validity_policy, qoi)
        results: dict[str, HierarchicalResult] = {}
        transfer_receipts: list[str] = []
        for child in node.children:
            receipt = receipts[child.system_id]
            child_result = produced.get(child.system_id)
            if child_result is None:
                results[child.system_id] = self._failed(
                    child, f"UPSTREAM_FAILED:{child.system_id}", receipt.detail,
                    validity_policy)
                continue
            results[child.system_id] = child_result
        for link in node.links:
            if link.source_system == node.system_id or link.target_system == node.system_id:
                continue
            source_result = results.get(link.source_system)
            if source_result is None or source_result.status == "failed":
                continue
            value = source_result.values.get(link.source_port)
            if value is None:
                continue
            target_unit = lookup[link.target_system][link.target_port].unit
            transfer_receipts.append(
                f"{link.source_system}.{link.source_port}->"
                f"{link.target_system}.{link.target_port}:{value:.6g}{target_unit}")
        failed = [cid for cid, result in results.items() if result.status == "failed"]
        ordered_children = tuple(results[child.system_id] for child in node.children)
        if failed:
            key = hierarchy_cache_key(
                subtree_digest=node.subtree_digest, qoi=tuple(qoi),
                boundary_digest=contract_digest({k: float(v) for k, v in sorted(boundary.items())}),
                solver=self._software, settings={"failed": sorted(failed)},
                fidelity=limiting_fidelity(node), validity_policy=validity_policy)
            return self._seal(node, {}, {port_id: p.unit for port_id, p in ports.items()
                                         if p.direction == "out"},
                              "failed", key,
                              CacheOutcome("miss", "miss_input_changed", key,
                                           f"CHILD_FAILED:{failed[0]}"),
                              ordered_children, validity_policy,
                              tuple([f"CHILD_FAILED:{failed[0]}", *transfer_receipts]))
        values: dict[str, float] = {}
        units: dict[str, str] = {}
        for port in node.ports:
            if port.direction != "out":
                continue
            exposed = [b for b in node.bindings
                       if b.parent_port == port.port_id and b.kind == "interface"]
            if len(exposed) != 1:
                key = hierarchy_cache_key(
                    subtree_digest=node.subtree_digest, qoi=tuple(qoi),
                    boundary_digest=contract_digest(
                        {k: float(v) for k, v in sorted(boundary.items())}),
                    solver=self._software, settings={"unbound": port.port_id},
                    fidelity=limiting_fidelity(node), validity_policy=validity_policy)
                return self._seal(node, {}, {}, "failed", key,
                                  CacheOutcome("miss", "miss_input_changed", key,
                                               f"PARENT_OUTPUT_UNBOUND:{port.port_id}"),
                                  ordered_children, validity_policy,
                                  tuple([f"PARENT_OUTPUT_UNBOUND:{port.port_id}"]))
            binding = exposed[0]
            child_value = results[binding.child_system].values.get(binding.child_port)
            if child_value is None:
                key = hierarchy_cache_key(
                    subtree_digest=node.subtree_digest, qoi=tuple(qoi),
                    boundary_digest=contract_digest(
                        {k: float(v) for k, v in sorted(boundary.items())}),
                    solver=self._software, settings={"missing": port.port_id},
                    fidelity=limiting_fidelity(node), validity_policy=validity_policy)
                return self._seal(node, {}, {}, "failed", key,
                                  CacheOutcome("miss", "miss_input_changed", key,
                                               f"BINDING_VALUE_MISSING:{port.port_id}"),
                                  ordered_children, validity_policy,
                                  tuple([f"BINDING_VALUE_MISSING:{port.port_id}"]))
            child_unit = lookup[binding.child_system][binding.child_port].unit
            values[port.port_id] = convert_unit(child_value, child_unit, port.unit)
            units[port.port_id] = port.unit
        key = hierarchy_cache_key(
            subtree_digest=node.subtree_digest, qoi=tuple(qoi),
            boundary_digest=contract_digest({k: float(v) for k, v in sorted(boundary.items())}),
            solver=self._software,
            settings={"children": sorted(r.inputs_hash for r in ordered_children)},
            fidelity=limiting_fidelity(node), validity_policy=validity_policy,
            interface_digest=contract_digest(sorted(link.digest for link in node.links)))
        axes = {"solver": f"{self._software[0]}@{self._software[1]}",
                "boundary": contract_digest({k: float(v) for k, v in sorted(boundary.items())}),
                "input": node.subtree_digest}
        outcome = self._consume_key_axes(f"assembly:{node.system_id}", axes, key)
        with self._lock:
            self._node_cache.put(key, (values, units))
        return self._seal(node, values, units, "converged", key, outcome,
                          ordered_children, validity_policy, tuple(transfer_receipts))

    def _incoming(
        self, node: SystemRecord, child_id: str,
    ) -> list[tuple[str, str, str]]:
        return [(link.source_system, link.source_port, link.target_port)
                for link in node.links if link.target_system == child_id]

    def _run_dag(
        self, node: SystemRecord, boundary: Mapping[str, float],
        validity_policy: str, qoi: tuple[str, ...],
    ) -> tuple[dict[str, NodeResult], dict[str, HierarchicalResult]]:
        members = {node.system_id: node}
        for child in node.children:
            members[child.system_id] = child
        lookup = {sid: {p.port_id: p for p in member.ports} for sid, member in members.items()}
        boundary_digest = contract_digest({k: float(v) for k, v in sorted(boundary.items())})
        for link in node.links:
            if link.source_system == node.system_id and link.source_port not in boundary:
                raise ValueError(f"PARENT_INPUT_MISSING:{link.source_port}")
        produced: dict[str, HierarchicalResult] = {}
        guard = threading.Lock()

        def make_fn(child_id: str) -> Callable[[Mapping[str, NodeResult]], tuple[object, str]]:
            def fn(deps: Mapping[str, NodeResult]) -> tuple[object, str]:
                try:
                    child_inputs: dict[str, float] = {}
                    for src_sys, src_port, tgt_port in self._incoming(node, child_id):
                        if src_sys == node.system_id:
                            raw = float(boundary[src_port])
                            child_inputs[tgt_port] = convert_unit(
                                raw, lookup[src_sys][src_port].unit,
                                lookup[child_id][tgt_port].unit)
                        else:
                            payload = deps[src_sys].value
                            available = payload.get("outputs", {}) if isinstance(
                                payload, dict) else {}
                            if src_port not in available:
                                raise ChildFailure(src_sys, "OUTPUT_MISSING", src_port)
                            child_inputs[tgt_port] = convert_unit(
                                float(available[src_port]), lookup[src_sys][src_port].unit,
                                lookup[child_id][tgt_port].unit)
                    merged = {**{k: float(v) for k, v in boundary.items()}, **child_inputs}
                    result = self._eval_node(members[child_id], merged, validity_policy, qoi)
                    with guard:
                        produced[child_id] = result
                    return ({"outputs": dict(result.values)}, "record")
                except ChildFailure as exc:
                    failed = self._failed(members[child_id],
                                          f"CHILD_FAILED:{exc.system_id}:{exc.reason}",
                                          exc.detail, validity_policy)
                    with guard:
                        produced[child_id] = failed
                    return ({"outputs": {}}, "record")
                except Exception as exc:
                    failed = self._failed(members[child_id], "NODE_FAILED", str(exc),
                                          validity_policy)
                    with guard:
                        produced[child_id] = failed
                    return ({"outputs": {}}, "record")

            return fn

        dag = ComputationDAG({child.system_id: make_fn(child.system_id)
                              for child in node.children})
        for child in node.children:
            deps = sorted({src for src, _, _ in self._incoming(node, child.system_id)
                           if src != node.system_id})
            child_digest = child.subtree_digest
            if child.is_leaf:
                model = self._models[child.system_id]
                solver = (model.solver[0], model.solver[1])
            else:
                solver = (self._software[0], self._software[1])
            dag.add(NodeSpec(
                child.system_id, "analytical", "analysis", tuple(deps), solver,
                {"subtree": child_digest, "boundary": boundary_digest,
                 "fidelity": child.fidelity, "validity": validity_policy,
                 "interface": contract_digest(sorted(
                     link.digest for link in node.links
                     if link.source_system == child.system_id
                     or link.target_system == child.system_id))},
                base_inputs=("boundary",)))
        return dag.execute({"boundary": boundary_digest}), produced

    def _eval_cyclic(
        self, node: SystemRecord, boundary: Mapping[str, float],
        validity_policy: str, qoi: tuple[str, ...],
    ) -> HierarchicalResult:
        members = {child.system_id: child for child in node.children}
        lookup = {sid: {p.port_id: p for p in members[sid].ports} for sid in members}
        lookup[node.system_id] = {p.port_id: p for p in node.ports}
        order = [c.system_id for c in node.children]
        internal = [link for link in node.links
                    if link.source_system in members and link.target_system in members]
        topology = contract_digest({
            "children": sorted(members),
            "links": sorted(link.digest for link in internal)})
        with self._lock:
            warm = self._warm_states.get(topology)
        state: dict[tuple[str, str], float] = {}
        for child_id, child in members.items():
            for port in child.ports:
                if port.direction == "out":
                    slot = (child_id, port.port_id)
                    state[slot] = warm[slot] if warm and slot in warm else 0.0
        outcome: CacheOutcome = CacheOutcome(
            "miss", "miss_input_changed", topology,
            "first coupled solve" if warm is None else "warm-started coupled solve")
        if warm is not None:
            outcome = CacheOutcome("warm_start", "warm_start", topology,
                                   "prior converged state reused as initial guess")
        results: dict[str, HierarchicalResult] = {}
        external_inputs: dict[str, dict[str, float]] = {cid: {} for cid in members}
        for link in node.links:
            if link.source_system == node.system_id:
                if link.source_port not in boundary:
                    return self._failed(node, f"PARENT_INPUT_MISSING:{link.source_port}", "",
                                        validity_policy)
                external_inputs[link.target_system][link.target_port] = convert_unit(
                    float(boundary[link.source_port]),
                    lookup[node.system_id][link.source_port].unit,
                    lookup[link.target_system][link.target_port].unit)
        converged = False
        for _ in range(self._max_iterations):
            changed = 0.0
            for child_id in order:
                child_inputs = dict(external_inputs[child_id])
                for link in node.links:
                    if link.target_system != child_id or link.source_system not in members:
                        continue
                    value = state.get((link.source_system, link.source_port))
                    if value is None:
                        continue
                    child_inputs[link.target_port] = convert_unit(
                        value, lookup[link.source_system][link.source_port].unit,
                        lookup[child_id][link.target_port].unit)
                merged = {**{k: float(v) for k, v in boundary.items()}, **child_inputs}
                result = self._eval_node(members[child_id], merged, validity_policy, qoi)
                results[child_id] = result
                if result.status == "failed":
                    node_key = hierarchy_cache_key(
                        subtree_digest=node.subtree_digest, qoi=tuple(qoi),
                        boundary_digest=contract_digest(
                            {k: float(v) for k, v in sorted(boundary.items())}),
                        solver=self._software, settings={"childFailed": child_id},
                        fidelity=limiting_fidelity(node), validity_policy=validity_policy)
                    ordered = tuple(results.get(c.system_id, self._failed(
                        c, "NOT_EVALUATED", "", validity_policy)) for c in node.children)
                    return self._seal(node, {}, {}, "failed", node_key,
                                      CacheOutcome("miss", "miss_input_changed", node_key,
                                                   f"CHILD_FAILED:{child_id}"),
                                      ordered, validity_policy,
                                      (f"CHILD_FAILED:{child_id}",))
                for port_id, value in result.values.items():
                    slot = (child_id, port_id)
                    previous = state.get(slot, 0.0)
                    relaxed = previous + self._relaxation * (value - previous)
                    changed = max(changed, abs(relaxed - previous))
                    state[slot] = relaxed
            if changed <= self._tolerance:
                converged = True
                break
        if not converged:
            node_key = hierarchy_cache_key(
                subtree_digest=node.subtree_digest, qoi=tuple(qoi),
                boundary_digest=contract_digest(
                    {k: float(v) for k, v in sorted(boundary.items())}),
                solver=self._software, settings={"diverged": topology},
                fidelity=limiting_fidelity(node), validity_policy=validity_policy)
            ordered = tuple(results[c.system_id] for c in node.children)
            return self._seal(node, {}, {}, "failed", node_key,
                              CacheOutcome("miss", "miss_input_changed", node_key,
                                           "COUPLING_DIVERGED"),
                              ordered, validity_policy, ("COUPLING_DIVERGED",))
        with self._lock:
            self._warm_states[topology] = dict(state)
        transfer_receipts = [
            f"{link.source_system}.{link.source_port}->"
            f"{link.target_system}.{link.target_port}:"
            f"{state[(link.source_system, link.source_port)]:.6g}"
            f"{lookup[link.target_system][link.target_port].unit}"
            for link in internal]
        values: dict[str, float] = {}
        units: dict[str, str] = {}
        for port in node.ports:
            if port.direction != "out":
                continue
            exposed = [b for b in node.bindings
                       if b.parent_port == port.port_id and b.kind == "interface"]
            if len(exposed) != 1:
                return self._failed(node, f"PARENT_OUTPUT_UNBOUND:{port.port_id}", "",
                                    validity_policy)
            binding = exposed[0]
            child_value = results[binding.child_system].values.get(binding.child_port)
            if child_value is None:
                return self._failed(node, f"BINDING_VALUE_MISSING:{port.port_id}", "",
                                    validity_policy)
            values[port.port_id] = convert_unit(
                child_value, lookup[binding.child_system][binding.child_port].unit, port.unit)
            units[port.port_id] = port.unit
        node_key = hierarchy_cache_key(
            subtree_digest=node.subtree_digest, qoi=tuple(qoi),
            boundary_digest=contract_digest({k: float(v) for k, v in sorted(boundary.items())}),
            solver=self._software,
            settings={"children": sorted(results[c].inputs_hash for c in results)},
            fidelity=limiting_fidelity(node), validity_policy=validity_policy,
            interface_digest=contract_digest(sorted(link.digest for link in node.links)))
        ordered = tuple(results[c.system_id] for c in node.children)
        return self._seal(node, values, units, "converged", node_key, outcome,
                          ordered, validity_policy, tuple(transfer_receipts))
