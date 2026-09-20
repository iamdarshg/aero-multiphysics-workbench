"""Deterministic, structured FFD refinement before optional native CAD."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .assembly import AeroGeometryAssembly
from .body import BodySection, LoftedBody


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


def estimate_body_volume_mm3(body: LoftedBody) -> float:
    """Canonical body volume in mm^3.

    Delegates to the single canonical ``LoftedBody.volume_m3`` definition so
    the preservation gate and all downstream consumers agree exactly.
    """
    return float(body.volume_m3) * 1.0e9


def refine_assembly(assembly: AeroGeometryAssembly, plan: GeometryRefinementPlan) -> RefinementReceipt:  # noqa: E501
    before = assembly.digest
    bodies = list(assembly.bodies)
    reasons: list[str] = []
    for control in plan.controls:
        body_index = next((i for i, body in enumerate(bodies) if body.body_id == control.component_id), None)  # noqa: E501
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
                spine_mm=(
                    section.spine_mm[0] + control.displacement_mm[0] * weight,
                    section.spine_mm[1] + control.displacement_mm[1] * weight,
                    section.spine_mm[2] + control.displacement_mm[2] * weight,
                ),  # noqa: E501
                width_mm=section.width_mm * scale,
                height_mm=section.height_mm * height_scale,
            ))
        bodies[body_index] = replace(body, sections=tuple(sections))
        if plan.preserve_body_volume:
            candidate = bodies[body_index]
            before_v = float(body.volume_m3)
            after_v = float(candidate.volume_m3)
            if before_v > 0.0 and after_v > 0.0:
                factor = before_v / after_v
                fixed = tuple(
                    replace(section, height_mm=section.height_mm * factor)
                    for section in candidate.sections
                )
                bodies[body_index] = replace(candidate, sections=fixed)
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


__all__ = ["FfdControl", "GeometryRefinementPlan", "RefinementReceipt", "estimate_body_volume_mm3", "refine_assembly"]  # noqa: E501
