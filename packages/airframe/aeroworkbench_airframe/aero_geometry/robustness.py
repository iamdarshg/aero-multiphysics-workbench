"""Fail-closed robustness gates and topology-change receipts.

The checks are pure functions over the canonical primitive contracts. A
configuration either passes on measured geometry or yields an explicit
diagnostic that downstream stages treat as invalid; no verdict is fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..canonical import content_digest
from .body import LoftedBody
from .control import ControlSurface
from .seam import SurfaceSeam
from .surface import LiftingSurface

SEVERITY_LEVELS: tuple[str, ...] = ("error", "warning")

_EXCESSIVE_TAPER_RATIO = 0.05
_MAX_TWIST_DEG = 90.0


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


@dataclass(frozen=True, slots=True)
class TopologyChangeReceipt:
    """Deterministic receipt describing how a seam topology changed."""

    before_digest: str
    after_digest: str
    changes: tuple[tuple[str, str], ...]
    requires_remesh: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "beforeDigest": self.before_digest,
            "afterDigest": self.after_digest,
            "requiresRemesh": self.requires_remesh,
            "changes": [
                {"change": change, "grid": grid} for change, grid in self.changes
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def topology_change_receipt(before: SurfaceSeam, after: SurfaceSeam) -> TopologyChangeReceipt:
    """Classify a seam topology delta; any change forces a remesh."""

    before_signature = {item[0]: item for item in before.topology_signature()}
    after_signature = {item[0]: item for item in after.topology_signature()}
    changes: list[tuple[str, str]] = []
    for grid_id in sorted(after_signature):
        if grid_id not in before_signature:
            changes.append(("added", grid_id))
        elif before_signature[grid_id] != after_signature[grid_id]:
            changes.append(("modified", grid_id))
    for grid_id in sorted(before_signature):
        if grid_id not in after_signature:
            changes.append(("removed", grid_id))
    return TopologyChangeReceipt(
        before_digest=before.digest,
        after_digest=after.digest,
        changes=tuple(changes),
        requires_remesh=bool(changes) or before.digest != after.digest,
    )


def check_lifting_surface(surface: LiftingSurface) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    if surface.span_mm <= 0.0:
        findings.append(GeometryDiagnostic("SURFACE_SPAN_NOT_POSITIVE", surface.surface_id))
    if surface.area_mm2 <= 0.0:
        findings.append(GeometryDiagnostic("SURFACE_AREA_NOT_POSITIVE", surface.surface_id))
    for station in surface.stations:
        if abs(station.twist_deg) > _MAX_TWIST_DEG:
            findings.append(
                GeometryDiagnostic(
                    "SURFACE_TWIST_EXCESSIVE",
                    f"{surface.surface_id}:{station.span_fraction}",
                )
            )
    chords = [station.chord_mm for station in surface.stations]
    if min(chords) / max(chords) < _EXCESSIVE_TAPER_RATIO:
        findings.append(GeometryDiagnostic("SURFACE_TAPER_EXCESSIVE", surface.surface_id))
    # A crossed station centreline is a cheap, deterministic pre-CAD proxy for
    # a self-intersecting loft.  Native CAD remains the authoritative gate.
    points = [(station.leading_edge_mm[0], station.leading_edge_mm[2]) for station in surface.stations]
    def orient(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    for index, (a, b) in enumerate(zip(points, points[1:])):
        for other in range(index + 2, len(points) - 1):
            c, d = points[other], points[other + 1]
            if orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0:
                findings.append(GeometryDiagnostic("SURFACE_SELF_INTERSECTION", surface.surface_id))
                return tuple(findings)
    return tuple(findings)


def check_body(body: LoftedBody) -> tuple[GeometryDiagnostic, ...]:
    findings: list[GeometryDiagnostic] = []
    if body.length_mm <= 0.0:
        findings.append(GeometryDiagnostic("BODY_LENGTH_NOT_POSITIVE", body.body_id))
    for section in body.sections:
        if section.width_mm <= 0.0 or section.height_mm <= 0.0:
            findings.append(
                GeometryDiagnostic(
                    "BODY_SECTION_NOT_POSITIVE",
                    f"{body.body_id}:{section.station_fraction}",
                )
            )
    return tuple(findings)


def check_control_surface(
    control: ControlSurface, parent: LiftingSurface | None
) -> tuple[GeometryDiagnostic, ...]:
    if parent is None:
        return (GeometryDiagnostic("CONTROL_PARENT_MISSING", control.control_id),)
    findings: list[GeometryDiagnostic] = []
    if parent.surface_id != control.parent_id:
        findings.append(
            GeometryDiagnostic(
                "CONTROL_PARENT_MISMATCH", f"{control.control_id}:{control.parent_id}"
            )
        )
        return tuple(findings)
    if not 0.0 < control.hinge_fraction < 1.0:
        findings.append(GeometryDiagnostic("CONTROL_HINGE_OUT_OF_RANGE", control.control_id))
    start, end = control.span_fraction
    if not 0.0 <= start < end <= 1.0:
        findings.append(GeometryDiagnostic("CONTROL_SPAN_OUT_OF_RANGE", control.control_id))
    selected = [
        station
        for station in parent.stations
        if start <= station.span_fraction <= end
    ]
    if len(selected) < 2:
        findings.append(
            GeometryDiagnostic("CONTROL_SPAN_NEEDS_TWO_STATIONS", control.control_id)
        )
    return tuple(findings)


def aero_geometry_diagnostics(
    surfaces: tuple[LiftingSurface, ...],
    bodies: tuple[LoftedBody, ...],
    controls: tuple[ControlSurface, ...],
) -> tuple[GeometryDiagnostic, ...]:
    by_id = {surface.surface_id: surface for surface in surfaces}
    findings: list[GeometryDiagnostic] = []
    for surface in surfaces:
        findings.extend(check_lifting_surface(surface))
    for body in bodies:
        findings.extend(check_body(body))
    for control in controls:
        findings.extend(check_control_surface(control, by_id.get(control.parent_id)))
    if len(by_id) != len(surfaces):
        findings.append(GeometryDiagnostic("DUPLICATE_SURFACE_ID", "assembly"))
    body_ids = [body.body_id for body in bodies]
    if len(body_ids) != len(set(body_ids)):
        findings.append(GeometryDiagnostic("DUPLICATE_BODY_ID", "assembly"))
    return tuple(findings)


__all__ = [
    "GeometryDiagnostic",
    "SEVERITY_LEVELS",
    "TopologyChangeReceipt",
    "aero_geometry_diagnostics",
    "blocking",
    "check_body",
    "check_control_surface",
    "check_lifting_surface",
    "topology_change_receipt",
]
