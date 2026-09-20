"""Deterministic, structured FFD refinement before optional native CAD."""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi

from ..canonical import content_digest
from .assembly import AeroGeometryAssembly
from .body import BodySection


@dataclass(frozen=True, slots=True)
class FfdControl:
    component_id: str
    station_fraction: float
    support_fraction: float
    width_scale: float = 1.0
    displacement_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class GeometryRefinementPlan:
    plan_id: str
    controls: tuple[FfdControl, ...]
    preserve_body_volume: bool = False
    max_volume_change_fraction: float = 1e-6


@dataclass(frozen=True, slots=True)
class RefinementReceipt:
    valid: bool
    before_digest: str
    after_digest: str
    topology_changed: bool
    volume_change_fraction: float
    assembly: AeroGeometryAssembly
    reasons: tuple[str, ...] = ()


def estimate_body_volume_mm3(body) -> float:
    total = 0.0
    for left, right in zip(body.sections, body.sections[1:]):
        dz = abs(right.spine_mm[2] - left.spine_mm[2])
        area_left = pi * left.width_mm * left.height_mm / 4.0
        area_right = pi * right.width_mm * right.height_mm / 4.0
        total += 0.5 * (area_left + area_right) * dz
    return total


def refine_assembly(assembly: AeroGeometryAssembly, plan: GeometryRefinementPlan) -> RefinementReceipt:
    before = assembly.digest
    bodies = list(assembly.bodies)
    reasons: list[str] = []
    for control in plan.controls:
        body_index = next((i for i, body in enumerate(bodies) if body.body_id == control.component_id), None)
        if body_index is None:
            reasons.append(f"UNKNOWN_COMPONENT:{control.component_id}")
            continue
        body = bodies[body_index]
        sections: list[BodySection] = []
        for section in body.sections:
            distance = abs(section.station_fraction - control.station_fraction)
            weight = max(0.0, 1.0 - distance / max(control.support_fraction, 1e-12))
            scale = 1.0 + weight * (control.width_scale - 1.0)
            height_scale = 1.0 / scale if plan.preserve_body_volume else 1.0
            sections.append(replace(
                section,
                spine_mm=tuple(section.spine_mm[i] + control.displacement_mm[i] * weight for i in range(3)),
                width_mm=section.width_mm * scale,
                height_mm=section.height_mm * height_scale,
            ))
        bodies[body_index] = replace(body, sections=tuple(sections))
    refined = replace(assembly, bodies=tuple(bodies))
    before_volume = sum(estimate_body_volume_mm3(body) for body in assembly.bodies)
    after_volume = sum(estimate_body_volume_mm3(body) for body in refined.bodies)
    change = abs(after_volume - before_volume) / before_volume if before_volume else 0.0
    if plan.preserve_body_volume and change > plan.max_volume_change_fraction:
        reasons.append("BODY_VOLUME_PRESERVATION_FAILED")
    return RefinementReceipt(
        valid=not reasons,
        before_digest=before,
        after_digest=refined.digest,
        topology_changed=False,
        volume_change_fraction=change,
        assembly=refined,
        reasons=tuple(reasons),
    )


__all__ = ["FfdControl", "GeometryRefinementPlan", "RefinementReceipt", "estimate_body_volume_mm3", "refine_assembly"]
