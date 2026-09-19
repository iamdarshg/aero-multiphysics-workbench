"""Fail-closed geometry robustness gates and topology-change receipts.

All checks are pure functions over the canonical structured-surface model. They
never fabricate a verdict: a configuration either passes on measured geometry or
yields an explicit diagnostic that downstream stages treat as invalid.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any

from .body import OPEN_PATCH_KINDS, GeometryBody, SurfacePatch
from .sections import BladeSection, section_outline

SEVERITY_LEVELS: tuple[str, ...] = ("error", "warning")


@dataclass(frozen=True, slots=True)
class GeometryDiagnostic:
    """One measured robustness finding."""

    code: str
    message: str
    severity: str = "error"

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("DIAGNOSTIC_CODE_REQUIRED")
        if self.severity not in SEVERITY_LEVELS:
            raise ValueError(f"UNKNOWN_DIAGNOSTIC_SEVERITY:{self.severity}")

    def canonical(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


def blocking(diagnostics: tuple[GeometryDiagnostic, ...]) -> tuple[GeometryDiagnostic, ...]:
    return tuple(item for item in diagnostics if item.severity == "error")


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
    eps: float = 1e-12,
) -> bool:
    def orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def between(
        p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]
    ) -> bool:
        return (
            min(p[0], r[0]) - eps <= q[0] <= max(p[0], r[0]) + eps
            and min(p[1], r[1]) - eps <= q[1] <= max(p[1], r[1]) + eps
        )

    o1, o2 = orient(a, b, c), orient(a, b, d)
    o3, o4 = orient(c, d, a), orient(c, d, b)
    if (o1 * o2 < -eps) and (o3 * o4 < -eps):
        return True
    if abs(o1) <= eps and between(a, c, b):
        return True
    if abs(o2) <= eps and between(a, d, b):
        return True
    if abs(o3) <= eps and between(c, a, d):
        return True
    return bool(abs(o4) <= eps and between(c, b, d))


def check_section(
    section: BladeSection,
    *,
    n_surface: int,
    n_edge: int,
    label: str = "section",
) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    try:
        outline = section_outline(section, n_surface=n_surface, n_edge=n_edge)
    except ValueError as exc:
        return (GeometryDiagnostic("SECTION_INVALID", f"{label}:{exc}"),)
    count = len(outline)
    closed = [*outline, outline[0]]
    for index in range(count):
        a, b = closed[index], closed[index + 1]
        for other in range(index + 1, count):
            if other in (index, index + 1):
                continue
            if index == 0 and other == count - 1:
                continue
            c, d = closed[other], closed[other + 1]
            if _segments_intersect(a, b, c, d):
                findings.append(
                    GeometryDiagnostic(
                        "SECTION_SELF_INTERSECTION", f"{label}: segments {index}/{other}"
                    )
                )
                break
        if any(item.code == "SECTION_SELF_INTERSECTION" for item in findings):
            break
    area = 0.0
    for index in range(count):
        x0, y0 = outline[index]
        x1, y1 = outline[(index + 1) % count]
        area += x0 * y1 - x1 * y0
    if abs(area) <= 1e-12:
        findings.append(GeometryDiagnostic("SECTION_ZERO_AREA", label))
    return tuple(findings)


def check_stack(
    sections: tuple[BladeSection, ...],
    *,
    n_surface: int,
    n_edge: int,
) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    if len(sections) < 2:
        return (GeometryDiagnostic("LOFT_NEEDS_TWO_SECTIONS", "at least two sections"),)
    spans = [section.span for section in sections]
    if any(later <= earlier for earlier, later in zip(spans, spans[1:], strict=False)):
        findings.append(
            GeometryDiagnostic("LOFT_SPAN_NOT_INCREASING", "sections must be span-ordered")
        )
    counts = {len(section_outline(s, n_surface=n_surface, n_edge=n_edge)) for s in sections}
    if len(counts) != 1:
        findings.append(
            GeometryDiagnostic("LOFT_POINT_COUNT_MISMATCH", f"point counts {sorted(counts)}")
        )
    for index, section in enumerate(sections):
        findings.extend(
            check_section(
                section, n_surface=n_surface, n_edge=n_edge, label=f"section[{index}]"
            )
        )
    return tuple(findings)


def check_clearance(
    *,
    hub_radius_mm: float,
    tip_radius_mm: float,
    shroud_radius_mm: float,
    tip_clearance_mm: float,
    shroud_state: str | None,
) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    if tip_radius_mm <= hub_radius_mm:
        findings.append(
            GeometryDiagnostic("IMPOSSIBLE_BLADE_SPAN", "tip radius must exceed hub radius")
        )
    if shroud_state == "shrouded":
        return tuple(findings)
    if tip_clearance_mm < 0.0:
        findings.append(GeometryDiagnostic("IMPOSSIBLE_CLEARANCE", "clearance is negative"))
    if tip_clearance_mm >= (shroud_radius_mm - hub_radius_mm):
        findings.append(
            GeometryDiagnostic("CLEARANCE_EXCEEDS_PASSAGE", "clearance consumes the passage")
        )
    if tip_radius_mm > shroud_radius_mm + 1e-9:
        findings.append(
            GeometryDiagnostic("TIP_PENETRATES_SHROUD", "tip radius exceeds shroud radius")
        )
    return tuple(findings)


def check_row_overlap(
    extents: tuple[tuple[str, float, float], ...],
) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    ordered = sorted(extents, key=lambda item: item[1])
    for (id_a, start_a, end_a), (id_b, start_b, end_b) in zip(
        ordered, ordered[1:], strict=False
    ):
        if start_a > end_a or start_b > end_b:
            findings.append(GeometryDiagnostic("INVALID_ROW_EXTENT", f"{id_a}/{id_b}"))
            continue
        if start_b < end_a - 1e-9:
            findings.append(
                GeometryDiagnostic("ROWS_OVERLAP", f"{id_a}:{end_a} > {id_b}:{start_b}")
            )
    return tuple(findings)


def check_patch(patch: SurfacePatch) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    if not all(isfinite(float(value)) for point in patch.points for value in point):
        findings.append(GeometryDiagnostic("PATCH_NOT_FINITE", patch.patch_id))
    for start, end in patch.edges():
        if start == end:
            findings.append(GeometryDiagnostic("PATCH_DEGENERATE_EDGE", patch.patch_id))
            break
    return tuple(findings)


def check_manifold(
    body: GeometryBody,
    *,
    allow_open_kinds: frozenset[str] = OPEN_PATCH_KINDS,
) -> tuple[GeometryDiagnostic, ...]:
    """Fail closed on nonmanifold faces; report open boundaries honestly.

    A solid must be a closed 2-manifold. A fluid sector may legitimately have
    declared open boundaries (inlet/outlet/periodic/interface), so those are a
    warning carrying the measured count, never silently ignored.
    """

    findings: list[GeometryDiagnostic] = []
    for patch in body.patches:
        patch_findings = check_patch(patch)
        if patch_findings:
            findings.extend(patch_findings)
    if findings:
        return tuple(findings)
    for edge in body.nonmanifold_edges()[:8]:
        findings.append(
            GeometryDiagnostic(
                "GEOMETRY_NONMANIFOLD_EDGE",
                f"{body.body_id}: edge shared by >2 patches: {edge}",
            )
        )
    unpaired = body.unpaired_edges()
    if body.domain == "solid":
        for edge in unpaired[:8]:
            findings.append(
                GeometryDiagnostic(
                    "SOLID_OPEN_EDGE", f"{body.body_id}: unpaired edge: {edge}"
                )
            )
    elif unpaired:
        touches_open = any(patch.kind in allow_open_kinds for patch in body.patches)
        findings.append(
            GeometryDiagnostic(
                "FLUID_OPEN_BOUNDARY",
                f"{body.body_id}: {len(unpaired)} open edges"
                + ("" if touches_open else " (no open-kind patch declared)"),
                severity="warning",
            )
        )
    return tuple(findings)


def check_required_roles(
    body: GeometryBody,
    *,
    required_roles: tuple[str, ...],
    required_kinds: tuple[str, ...] = (),
) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    present_roles = set(body.roles())
    present_kinds = set(body.kinds())
    for role in required_roles:
        if role not in present_roles:
            findings.append(GeometryDiagnostic("REQUIRED_ROLE_MISSING", role))
    for kind in required_kinds:
        if kind not in present_kinds:
            findings.append(GeometryDiagnostic("REQUIRED_KIND_MISSING", kind))
    return tuple(findings)


@dataclass(frozen=True, slots=True)
class TopologyChange:
    change: str
    entity: str
    detail: str = ""

    def canonical(self) -> dict[str, str]:
        return {"change": self.change, "entity": self.entity, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class TopologyChangeReceipt:
    """Deterministic receipt describing how a geometry topology changed."""

    before_digest: str
    after_digest: str
    changes: tuple[TopologyChange, ...]
    requires_remesh: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "beforeDigest": self.before_digest,
            "afterDigest": self.after_digest,
            "requiresRemesh": self.requires_remesh,
            "changes": [item.canonical() for item in self.changes],
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def topology_change_receipt(
    before: GeometryBody,
    after: GeometryBody,
) -> TopologyChangeReceipt:
    """Classify a topology delta; count changes force a remesh."""

    before_signature = {item[0]: item for item in before.topology_signature()}
    after_signature = {item[0]: item for item in after.topology_signature()}
    changes: list[TopologyChange] = []
    for patch_id in sorted(after_signature):
        if patch_id not in before_signature:
            changes.append(TopologyChange("added", patch_id, after_signature[patch_id][1]))
        elif before_signature[patch_id] != after_signature[patch_id]:
            changes.append(
                TopologyChange("modified", patch_id, "topology signature changed")
            )
    for patch_id in sorted(before_signature):
        if patch_id not in after_signature:
            changes.append(TopologyChange("removed", patch_id, before_signature[patch_id][1]))
    requires_remesh = bool(changes) or before.digest() != after.digest()
    return TopologyChangeReceipt(
        before_digest=before.digest(),
        after_digest=after.digest(),
        changes=tuple(changes),
        requires_remesh=requires_remesh,
    )
