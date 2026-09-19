"""Morph versus remesh, forced by physics-quality gates.

The existing semantic morph/remesh gate decides reuse/morph/remesh from geometry
hashes and topology reconciliation. This layer forces a full remesh whenever a
physics-quality condition makes morphing unsafe: boundary-layer quality failed,
topology changed, moving-interface compatibility failed, tip/clearance
resolution collapsed, or an adaptation pass violated quality limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aeroworkbench_mesh import UpdatePolicy, select_mesh_update
from aeroworkbench_semantics import TopologyReport

__all__ = ["MeshUpdateDecision", "decide_physics_mesh_update"]

MeshAction = Literal["reuse", "morph", "remesh"]


@dataclass(frozen=True, slots=True)
class MeshUpdateDecision:
    """Physics-aware reuse/morph/remesh decision with explicit reasons."""

    action: MeshAction
    forced_remesh: bool
    reasons: tuple[str, ...]
    topology_action: str
    max_displacement_mm: float

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "forcedRemesh": self.forced_remesh,
            "reasons": list(self.reasons),
            "topologyAction": self.topology_action,
            "maxDisplacementMm": self.max_displacement_mm,
        }


def decide_physics_mesh_update(
    *,
    parent_geometry_hash: str | None,
    current_geometry_hash: str,
    parent_mesh_hash: str | None,
    topology_report: TopologyReport | None,
    max_param_shift_mm: float,
    boundary_layer_valid: bool = True,
    interface_motion_compatible: bool = True,
    tip_clearance_cells: int | None = None,
    min_tip_clearance_cells: int = 3,
    adaptation_quality_ok: bool = True,
    policy: UpdatePolicy | None = None,
) -> MeshUpdateDecision:
    """Decide mesh update, forcing remesh on any physics-quality failure."""

    if min_tip_clearance_cells < 1:
        raise ValueError("MIN_TIP_CLEARANCE_CELLS_INVALID")
    base = select_mesh_update(
        parent_geometry_hash=parent_geometry_hash,
        current_geometry_hash=current_geometry_hash,
        parent_mesh_hash=parent_mesh_hash,
        report=topology_report,
        max_param_shift_mm=max_param_shift_mm,
        policy=policy,
    )
    forced: list[str] = []
    if not boundary_layer_valid:
        forced.append("boundary-layer-quality-failed")
    if topology_report is not None and topology_report.requires_remesh:
        forced.append("topology-changed")
    if not interface_motion_compatible:
        forced.append("moving-interface-incompatible")
    if tip_clearance_cells is not None and tip_clearance_cells < min_tip_clearance_cells:
        forced.append("tip-clearance-collapse")
    if not adaptation_quality_ok:
        forced.append("adaptation-quality-violation")

    if forced:
        return MeshUpdateDecision(
            action="remesh",
            forced_remesh=True,
            reasons=(*forced, base.reason),
            topology_action=base.action,
            max_displacement_mm=base.max_displacement_mm,
        )
    if base.action == "remesh_required":
        return MeshUpdateDecision(
            action="remesh",
            forced_remesh=False,
            reasons=(base.reason,),
            topology_action=base.action,
            max_displacement_mm=base.max_displacement_mm,
        )
    if base.action == "morph_candidate":
        return MeshUpdateDecision(
            action="morph",
            forced_remesh=False,
            reasons=(base.reason,),
            topology_action=base.action,
            max_displacement_mm=base.max_displacement_mm,
        )
    return MeshUpdateDecision(
        action="reuse",
        forced_remesh=False,
        reasons=(base.reason,),
        topology_action=base.action,
        max_displacement_mm=base.max_displacement_mm,
    )
