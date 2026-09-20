"""Subassembly synthesis, requirement allocation and reuse for recursive assemblies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import dist, isfinite
from typing import Literal

from .composition import (
    AssemblyFidelity,
    AssemblyLink,
    Binding,
    ComposedPort,
    DesignVariable,
    MassProperties,
    OperatingState,
    Requirement,
    SolverCapability,
    SubassemblyMode,
    SystemRecord,
    Validity,
    aggregate_mass,
    check_compatible,
    check_feed_compatible,
)
from .physical import Vector3, contract_digest


class ChildFailure(Exception):
    def __init__(self, system_id: str, reason: str, detail: str = "") -> None:
        super().__init__(f"{system_id}:{reason}:{detail}")
        self.system_id = system_id
        self.reason = reason
        self.detail = detail


PartialStatus = Literal["partial", "failed"]


@dataclass(frozen=True, slots=True)
class PartialState:
    system_id: str
    status: PartialStatus
    reason: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.system_id.strip() or not self.reason.strip():
            raise ValueError("PARTIAL_STATE_IDENTITY_REQUIRED")
        if self.status not in ("partial", "failed"):
            raise ValueError("PARTIAL_STATUS_INVALID")


@dataclass(frozen=True, slots=True)
class Interference:
    pair: tuple[str, str]
    gap_m: float
    contact: bool

    def __post_init__(self) -> None:
        if not isfinite(self.gap_m):
            raise ValueError("INTERFERENCE_GAP_NONFINITE")


def detect_interference(
    spheres: Mapping[str, tuple[Vector3, float]], *, clearance_m: float = 0.0,
) -> tuple[Interference, ...]:
    if not isfinite(clearance_m) or clearance_m < 0:
        raise ValueError("INTERFERENCE_CLEARANCE_INVALID")
    names = sorted(spheres)
    for name in names:
        center, radius = spheres[name]
        if len(center) != 3 or any(not isfinite(v) for v in center):
            raise ValueError(f"INTERFERENCE_CENTER_INVALID:{name}")
        if not isfinite(radius) or radius < 0:
            raise ValueError(f"INTERFERENCE_RADIUS_INVALID:{name}")
    findings: list[Interference] = []
    for index, first in enumerate(names):
        for second in names[index + 1:]:
            gap = dist(spheres[first][0], spheres[second][0]) - (
                spheres[first][1] + spheres[second][1]) - clearance_m
            findings.append(Interference((first, second), gap, gap < 0))
    return tuple(findings)


def synthesize_subassembly(
    *,
    system_id: str,
    revision: str,
    system_type: str,
    children: tuple[SystemRecord, ...],
    links: tuple[AssemblyLink, ...] = (),
    ports: tuple[ComposedPort, ...] = (),
    bindings: tuple[Binding, ...] = (),
    design_vars: tuple[DesignVariable, ...] = (),
    requirements: tuple[Requirement, ...] = (),
    operating: OperatingState | None = None,
    solvers: tuple[SolverCapability, ...] = (),
    capabilities: tuple[str, ...] = (),
    fidelity: AssemblyFidelity = "analytical",
    local_geometry: str = "",
    semantic_digest: str = "",
    model_digest: str = "",
    mass: MassProperties | None = None,
    mode: SubassemblyMode = "live",
    lineage: tuple[str, ...] = (),
) -> SystemRecord:
    if not children:
        raise ValueError("SYNTHESIS_NEEDS_CHILDREN")
    resolved_mass = mass
    if resolved_mass is None and all(child.mass is not None for child in children):
        entries = tuple((child.mass, child.transform) for child in children
                        if child.mass is not None)
        resolved_mass = aggregate_mass(entries)
    geometry = local_geometry
    if not geometry:
        geometry = contract_digest({
            "children": [{"id": c.system_id, "revision": c.revision,
                          "digest": c.subtree_digest,
                          "transform": c.transform.digest if c.transform else None}
                         for c in sorted(children, key=lambda c: c.system_id)],
        })
    return SystemRecord(
        system_id=system_id, revision=revision, system_type=system_type,
        capabilities=tuple(capabilities), ports=tuple(ports), children=tuple(children),
        links=tuple(links), bindings=tuple(bindings), mass=resolved_mass,
        design_vars=tuple(design_vars), requirements=tuple(requirements), operating=operating,
        solvers=tuple(solvers), fidelity=fidelity, geometry_digest=geometry,
        semantic_digest=semantic_digest, model_digest=model_digest, mode=mode,
        lineage=tuple(lineage),
    )


def allocate_requirements(
    record: SystemRecord, allocations: Mapping[str, tuple[Requirement, ...]],
) -> SystemRecord:
    for system_id in allocations:
        if record.find(system_id) is None:
            raise ValueError(f"ALLOCATION_TARGET_UNKNOWN:{system_id}")

    def apply(node: SystemRecord) -> SystemRecord:
        children = tuple(apply(child) for child in node.children)
        extra = allocations.get(node.system_id, ())
        if not children and not extra:
            return node
        return replace(node, children=children,
                       requirements=tuple(node.requirements) + tuple(extra))

    return apply(record)


def margin_rollup(record: SystemRecord) -> dict[str, float]:
    rolled: dict[str, float] = {}
    for req in record.requirements:
        current = rolled.get(req.req_id)
        rolled[req.req_id] = req.margin if current is None else min(current, req.margin)
    for child in record.children:
        for req_id, margin in margin_rollup(child).items():
            current = rolled.get(req_id)
            rolled[req_id] = margin if current is None else min(current, margin)
    return rolled


def system_margin(record: SystemRecord) -> float:
    rolled = margin_rollup(record)
    if not rolled:
        raise ValueError("NO_REQUIREMENTS_FOR_MARGIN")
    return min(rolled.values())


def limiting_fidelity(record: SystemRecord) -> AssemblyFidelity:
    rank = {"analytical": 0, "surrogate": 1, "benchmark": 2, "native": 3}
    worst = rank[record.fidelity]
    label: AssemblyFidelity = record.fidelity
    for child in record.children:
        child_limit = limiting_fidelity(child)
        if rank[child_limit] < worst:
            worst = rank[child_limit]
            label = child_limit
    return label


def fidelity_evidence(record: SystemRecord) -> dict[str, AssemblyFidelity]:
    evidence = {record.system_id: record.fidelity}
    for child in record.children:
        evidence.update(fidelity_evidence(child))
    return evidence


def promote_fidelity(
    record: SystemRecord, target_id: str, fidelity: AssemblyFidelity,
) -> SystemRecord:
    if fidelity not in ("analytical", "surrogate", "benchmark", "native"):
        raise ValueError("FIDELITY_UNKNOWN")
    if record.find(target_id) is None:
        raise ValueError(f"FIDELITY_TARGET_UNKNOWN:{target_id}")

    def apply(node: SystemRecord) -> SystemRecord:
        if node.system_id == target_id:
            return replace(node, fidelity=fidelity)
        rebuilt = tuple(apply(child) for child in node.children)
        if all(new is old for new, old in zip(rebuilt, node.children, strict=True)):
            return node
        return replace(node, children=rebuilt)

    return apply(record)


def _check_drop_in(
    parent: SystemRecord, target_id: str, replacement: SystemRecord,
) -> None:
    if replacement.system_id != target_id:
        raise ValueError("SUBASSEMBLY_ID_MISMATCH")
    new_ports = {port.port_id: port for port in replacement.ports}
    for link in parent.links:
        if link.source_system == target_id:
            candidate = new_ports.get(link.source_port)
            if candidate is None:
                raise ValueError(f"SUBASSEMBLY_PORT_MISSING:{target_id}:{link.source_port}")
            peer = parent.find(link.target_system)
            other = next(p for p in (peer.ports if peer else ()) if p.port_id == link.target_port)
            if link.target_system == parent.system_id:
                check_feed_compatible(candidate, other, transform=link.transform)
            else:
                check_compatible(candidate, other, transform=link.transform)
        if link.target_system == target_id:
            candidate = new_ports.get(link.target_port)
            if candidate is None:
                raise ValueError(f"SUBASSEMBLY_PORT_MISSING:{target_id}:{link.target_port}")
            peer = parent.find(link.source_system)
            other = next(p for p in (peer.ports if peer else ()) if p.port_id == link.source_port)
            if link.source_system == parent.system_id:
                check_feed_compatible(other, candidate, transform=link.transform)
            else:
                check_compatible(other, candidate, transform=link.transform)
    for binding in parent.bindings:
        if binding.child_system == target_id and binding.child_port not in new_ports:
            raise ValueError(f"SUBASSEMBLY_BINDING_MISSING:{target_id}:{binding.child_port}")


def replace_subassembly(
    record: SystemRecord, target_id: str, replacement: SystemRecord,
    *, mode: SubassemblyMode = "rom",
) -> SystemRecord:
    if mode not in ("frozen", "parametric", "rom", "live"):
        raise ValueError("SUBASSEMBLY_MODE_INVALID")
    if record.system_id == target_id:
        raise ValueError("SUBASSEMBLY_REPLACE_ROOT")
    if record.find(target_id) is None:
        raise ValueError(f"SUBASSEMBLY_TARGET_UNKNOWN:{target_id}")
    staged = replace(replacement, mode=mode,
                     lineage=tuple(replacement.lineage) + (f"{mode}:{replacement.revision}",))

    def apply(node: SystemRecord) -> SystemRecord:
        rebuilt_children: list[SystemRecord] = []
        changed = False
        for child in node.children:
            if child.system_id == target_id:
                _check_drop_in(node, target_id, staged)
                rebuilt_children.append(staged)
                changed = True
            else:
                updated = apply(child)
                rebuilt_children.append(updated)
                changed = changed or updated is not child
        if not changed:
            return node
        return replace(node, children=tuple(rebuilt_children))

    return apply(record)


def evaluate_requirements(
    record: SystemRecord, quantities: Mapping[str, float],
) -> Validity:
    checks: dict[str, bool] = {}
    notes: list[str] = []
    for req in record.requirements:
        if req.quantity not in quantities:
            notes.append(f"unevaluated:{req.req_id}")
            continue
        passed, margin = req.evaluate(quantities[req.quantity])
        checks[req.req_id] = passed
        notes.append(f"{req.req_id}:margin={margin:.6g}")
    evaluated = [checks[req.req_id] for req in record.requirements if req.req_id in checks]
    return Validity(bool(all(evaluated)) if evaluated else True, checks,
                    ";".join(notes) if notes else "no local requirements")


def evaluate_tree(
    record: SystemRecord, quantities_by_system: Mapping[str, Mapping[str, float]],
) -> dict[str, Validity]:
    verdicts = {record.system_id: evaluate_requirements(
        record, quantities_by_system.get(record.system_id, {}))}
    for child in record.children:
        verdicts.update(evaluate_tree(child, quantities_by_system))
    return verdicts
