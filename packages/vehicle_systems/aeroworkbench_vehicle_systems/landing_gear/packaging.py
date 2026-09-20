"""Retractable landing-gear state and AIRFRAME packaging checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_airframe import Vec3
from aeroworkbench_airframe.mass import BoundingBox, PackagingLayout

from .contracts import LandingGearFidelity, ResultMeta, result_meta
from .errors import LandingGearError, finite
from .geometry import LandingGearAssembly


class GearState(StrEnum):
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class GearStateResult:
    state: GearState
    mission_phase: str
    aerodynamic_drag_increment_cd: float
    meta: ResultMeta

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "missionPhase": self.mission_phase,
            "aerodynamicDragIncrementCd": self.aerodynamic_drag_increment_cd,
            "meta": self.meta.canonical(),
        }


def evaluate_gear_state(
    assembly: LandingGearAssembly,
    *,
    state: GearState,
    mission_phase: str,
    aerodynamic_drag_increment_cd: float,
) -> GearStateResult:
    """Record explicit gear up/down mission and aerodynamic state."""

    if not mission_phase.strip():
        raise LandingGearError("gear.mission_phase is required")
    drag = finite(
        aerodynamic_drag_increment_cd, "gear.aerodynamic_drag_increment_cd", minimum=0.0
    )
    meta = result_meta(
        model="vehicle-systems.landing-gear.gear-state",
        inputs={
            "assembly": assembly.canonical_payload(),
            "state": state.value,
            "missionPhase": mission_phase,
            "aerodynamicDragIncrementCd": drag,
        },
        valid=True,
        checks={"state_declared": True, "mission_phase_declared": True},
        detail="declared landing-gear configuration state",
        fidelity=LandingGearFidelity.ANALYTICAL,
        assumptions=("aerodynamic increment is an explicit caller-declared property",),
    )
    return GearStateResult(state, mission_phase, drag, meta)


@dataclass(frozen=True, slots=True)
class GearPackagingResult:
    state: GearState
    feasible: bool
    infeasibility_constraints: tuple[str, ...]
    envelopes: tuple[BoundingBox, ...]
    meta: ResultMeta

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "feasible": self.feasible,
            "infeasibilityConstraints": list(self.infeasibility_constraints),
            "envelopes": [box.as_dict() for box in self.envelopes],
            "meta": self.meta.canonical(),
        }


def _gear_box(assembly: LandingGearAssembly, leg_id: str) -> BoundingBox:
    leg = assembly.leg(leg_id)
    if not leg.retractable:
        raise LandingGearError(f"RETRACTABLE_GEAR_REQUIRED:{leg_id}")
    if leg.retracted_clearance is None:
        raise LandingGearError(f"RETRACTED_ENVELOPE_REQUIRED:{leg_id}")
    clearance = leg.retracted_clearance.value_si
    point = leg.axle_point
    return BoundingBox(
        point.frame,
        Vec3(
            point.x - clearance,
            point.y - clearance,
            point.z - clearance,
            "m",
            point.frame,
        ),
        Vec3(
            point.x + clearance,
            point.y + clearance,
            point.z + clearance,
            "m",
            point.frame,
        ),
    )


def check_gear_packaging(
    assembly: LandingGearAssembly,
    airframe: PackagingLayout,
    *,
    state: GearState,
) -> GearPackagingResult:
    """Check each retractable gear envelope against AIRFRAME bays and keep-outs."""

    if state is GearState.DOWN:
        meta = result_meta(
            model="vehicle-systems.landing-gear.packaging",
            inputs={
                "assembly": assembly.canonical_payload(),
                "airframe": airframe.canonical(),
                "state": state.value,
            },
            valid=True,
            checks={"packaging_required": True, "gear_down_declared": True},
            detail="gear-down state does not consume a retraction bay",
            fidelity=LandingGearFidelity.ANALYTICAL,
        )
        return GearPackagingResult(state, True, (), (), meta)

    envelopes = tuple(
        _gear_box(assembly, leg.leg_id) for leg in assembly.legs if leg.retractable
    )
    constraints: list[str] = []
    bays = airframe.bays()
    keepouts = airframe.keepouts()
    for envelope in envelopes:
        if not any(bay.box.contains(envelope) for bay in bays):
            constraints.append("GEAR_BAY_CLEARANCE")
        if any(envelope.overlaps(keepout.box) for keepout in keepouts):
            constraints.append("GEAR_KEEPOUT_INTERSECTION")
    constraints = list(dict.fromkeys(constraints))
    meta = result_meta(
        model="vehicle-systems.landing-gear.packaging",
        inputs={
            "assembly": assembly.canonical_payload(),
            "airframe": airframe.canonical(),
            "state": state.value,
        },
        valid=not constraints,
        checks={
            "gear_bay_clearance": "GEAR_BAY_CLEARANCE" not in constraints,
            "gear_keepout_clearance": "GEAR_KEEPOUT_INTERSECTION" not in constraints,
        },
        detail="retracted gear envelope against AIRFRAME packaging geometry",
        fidelity=LandingGearFidelity.ANALYTICAL,
        assumptions=("axis-aligned declared envelopes; no CAD kernel is evaluated",),
    )
    return GearPackagingResult(
        state, not constraints, tuple(constraints), envelopes, meta
    )


__all__ = [
    "GearPackagingResult",
    "GearState",
    "GearStateResult",
    "check_gear_packaging",
    "evaluate_gear_state",
]
