"""Gear placement, static load sharing, tip-back/tip-over, and CG compatibility.

Static reactions come from the actual contact-point geometry and the declared
CG: a nose/main split by moment balance, a tip-back angle measured from the main
contact to the CG, and a lateral tip-over (turnover) angle from the main track.
A bad placement or CG fails the corresponding check and the overall verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan, degrees
from typing import Any

from aeroworkbench_airframe import MassProperties

from .contracts import LandingGearFidelity, ResultMeta, result_meta
from .errors import GroundStabilityError, finite
from .geometry import GearArchitecture, GearLegSpec, GearRole, LandingGearAssembly

_GRAVITY = 9.80665


@dataclass(frozen=True, slots=True)
class GearReaction:
    """Static load carried by one leg and its share of total weight."""

    leg_id: str
    role: str
    static_load_n: float
    load_fraction: float

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "legId": self.leg_id,
            "role": self.role,
            "staticLoadN": self.static_load_n,
            "loadFraction": self.load_fraction,
        }


@dataclass(frozen=True, slots=True)
class GroundStabilityResult:
    """Static ground stability of a declared gear/CG combination."""

    scenario_id: str
    total_weight_n: float
    forward_gear_x_m: float
    main_gear_x_m: float
    cg_x_m: float
    cg_height_m: float
    nose_load_n: float
    main_load_n: float
    nose_load_fraction: float
    main_load_fraction: float
    tip_back_angle_rad: float
    tip_over_angle_rad: float
    track_m: float
    reactions: tuple[GearReaction, ...]
    stable: bool
    meta: ResultMeta

    def units(self) -> dict[str, str]:
        return {"force": "N", "length": "m", "angle": "rad"}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "scenarioId": self.scenario_id,
            "totalWeightN": self.total_weight_n,
            "forwardGearXM": self.forward_gear_x_m,
            "mainGearXM": self.main_gear_x_m,
            "cgXM": self.cg_x_m,
            "cgHeightM": self.cg_height_m,
            "noseLoadN": self.nose_load_n,
            "mainLoadN": self.main_load_n,
            "noseLoadFraction": self.nose_load_fraction,
            "mainLoadFraction": self.main_load_fraction,
            "tipBackAngleRad": self.tip_back_angle_rad,
            "tipOverAngleRad": self.tip_over_angle_rad,
            "trackM": self.track_m,
            "reactions": [reaction.canonical_payload() for reaction in self.reactions],
            "stable": self.stable,
            "meta": self.meta.canonical(),
        }


def _mean(values: list[float], label: str) -> float:
    if not values:
        raise GroundStabilityError(f"{label}_GEAR_REQUIRED")
    return sum(values) / len(values)


def _forward_and_main_legs(
    assembly: LandingGearAssembly,
) -> tuple[tuple[GearLegSpec, ...], tuple[GearLegSpec, ...]]:
    if assembly.architecture is GearArchitecture.SKID:
        skids = assembly.legs_with_role(GearRole.SKID)
        ordered = sorted(skids, key=lambda leg: leg.contact_point().x)
        return (ordered[0],), tuple(ordered[1:]) if len(ordered) > 1 else (ordered[0],)
    main = assembly.main_legs
    nose = assembly.nose_legs
    if not main:
        raise GroundStabilityError("ASSEMBLY_REQUIRES_A_MAIN_LEG")
    if not nose:
        others = tuple(leg for leg in assembly.legs if leg.role is not GearRole.MAIN)
        if not others:
            raise GroundStabilityError("FORWARD_GEAR_REQUIRED")
        ordered = sorted(others, key=lambda leg: leg.contact_point().x)
        nose = (ordered[0],)
    return nose, main


def check_ground_stability(
    assembly: LandingGearAssembly,
    mass_properties: MassProperties,
    *,
    cg_height_m: float,
    scenario_id: str = "ground-stability",
    min_tip_over_angle_deg: float = 25.0,
    min_tip_back_angle_deg: float = 10.0,
    min_nose_load_fraction: float = 0.05,
    max_nose_load_fraction: float = 0.35,
    gravity_m_s2: float = _GRAVITY,
) -> GroundStabilityResult:
    """Evaluate static stability; a bad gear/CG placement fails the verdict."""

    cg_height = finite(cg_height_m, "cg_height_m", positive=True)
    gravity = finite(gravity_m_s2, "gravity_m_s2", positive=True)
    min_tip_over = finite(min_tip_over_angle_deg, "min_tip_over_angle_deg", positive=True)
    min_tip_back = finite(min_tip_back_angle_deg, "min_tip_back_angle_deg")
    min_nose = finite(min_nose_load_fraction, "min_nose_load_fraction", minimum=0.0)
    max_nose = finite(max_nose_load_fraction, "max_nose_load_fraction", positive=True)
    if min_nose > max_nose:
        raise GroundStabilityError("NOSE_LOAD_FRACTION_BOUNDS_INVALID")

    weight = mass_properties.mass.value_si * gravity
    cg_x = mass_properties.cg.x
    nose_legs, main_legs = _forward_and_main_legs(assembly)
    nose_x = _mean([leg.contact_point().x for leg in nose_legs], "FORWARD")
    main_x = _mean([leg.contact_point().x for leg in main_legs], "MAIN")
    if main_x >= nose_x:
        raise GroundStabilityError("MAIN_GEAR_MUST_BE_AFT_OF_FORWARD_GEAR")

    nose_load = weight * (main_x - cg_x) / (main_x - nose_x)
    main_load = weight - nose_load
    nose_fraction = nose_load / weight
    main_fraction = main_load / weight

    tip_back = atan((cg_x - main_x) / cg_height)
    main_y = [leg.contact_point().y for leg in main_legs]
    track = max(main_y) - min(main_y)
    tip_over = atan((track / 2.0) / cg_height) if track > 0.0 else 0.0

    checks = {
        "cg_forward_of_main": cg_x > main_x,
        "cg_aft_of_forward_gear": cg_x < nose_x,
        "nose_load_positive": nose_load > 0.0,
        "nose_load_fraction_in_range": min_nose <= nose_fraction <= max_nose,
        "tip_back_angle_sufficient": degrees(tip_back) >= min_tip_back,
        "tip_over_angle_sufficient": degrees(tip_over) >= min_tip_over,
        "main_track_positive": track > 0.0,
    }
    stable = all(checks.values())

    legs_with_share: list[tuple[GearLegSpec, float]] = []
    for leg in main_legs:
        legs_with_share.append((leg, main_load / len(main_legs)))
    for leg in nose_legs:
        legs_with_share.append((leg, nose_load / len(nose_legs)))
    unique: dict[str, tuple[GearLegSpec, float]] = {}
    for leg, share in legs_with_share:
        unique[leg.leg_id] = (leg, share)
    reactions = tuple(
        GearReaction(
            leg_id=leg.leg_id,
            role=leg.role.value,
            static_load_n=share,
            load_fraction=share / weight,
        )
        for leg, share in sorted(unique.values(), key=lambda item: item[0].leg_id)
    )

    meta = result_meta(
        model="vehicle-systems.landing-gear.ground-stability",
        inputs={
            "assembly": assembly.canonical_payload(),
            "mass": {
                "massKg": mass_properties.mass.value_si,
                "cg": mass_properties.cg.canonical(),
            },
            "cgHeightM": cg_height,
            "minTipOverAngleDeg": min_tip_over,
            "minTipBackAngleDeg": min_tip_back,
            "minNoseLoadFraction": min_nose,
            "maxNoseLoadFraction": max_nose,
        },
        valid=stable,
        checks=checks,
        detail="static load sharing, tip-back and tip-over geometry",
        fidelity=LandingGearFidelity.ANALYTICAL,
    )
    return GroundStabilityResult(
        scenario_id=scenario_id,
        total_weight_n=weight,
        forward_gear_x_m=nose_x,
        main_gear_x_m=main_x,
        cg_x_m=cg_x,
        cg_height_m=cg_height,
        nose_load_n=nose_load,
        main_load_n=main_load,
        nose_load_fraction=nose_fraction,
        main_load_fraction=main_fraction,
        tip_back_angle_rad=tip_back,
        tip_over_angle_rad=tip_over,
        track_m=track,
        reactions=reactions,
        stable=stable,
        meta=meta,
    )


def require_stable_ground(assembly: LandingGearAssembly, result: GroundStabilityResult) -> None:
    """Fail closed when the declared gear/CG placement is not ground-stable."""

    if not result.stable:
        failed = [name for name, ok in result.meta.validity.checks.items() if not ok]
        raise GroundStabilityError(
            f"UNSTABLE_GROUND_PLACEMENT:{assembly.assembly_id}:{','.join(failed)}"
        )


__all__ = [
    "GearReaction",
    "GroundStabilityResult",
    "check_ground_stability",
    "require_stable_ground",
]
