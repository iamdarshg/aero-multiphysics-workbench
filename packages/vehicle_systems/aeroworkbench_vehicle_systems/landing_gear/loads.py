"""Gear load cases and their structural / durability hand-off.

Load cases are derived from actual dynamics: touchdown peak load from the shock
stroke response, braking load from the deceleration and its pitch-moment load
transfer, and turning load from the lateral acceleration and track. The exported
cases feed durability rainflow counting through a real load-history contract.
Whether the structure *survives* those loads requires a native structural engine
and fails closed when absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import sqrt
from typing import Any

from aeroworkbench_airframe import content_digest
from aeroworkbench_durability import LoadHistory

from .contracts import LG_UNITS, LandingGearFidelity, ResultMeta, result_meta
from .errors import CapabilityUnavailable, LandingGearError, finite
from .shock import ShockStrokeResult

_NATIVE_REQUIREMENT = "gear-structural-fea"


class LoadCaseKind(StrEnum):
    """The declared gear load-case taxonomy."""

    TOUCHDOWN = "touchdown"
    BRAKING = "braking"
    TURNING = "turning"
    TAXI = "taxi"


@dataclass(frozen=True, slots=True)
class GearLoadCase:
    """One six-component gear load case at its declared fidelity."""

    case_id: str
    kind: LoadCaseKind
    gear_id: str
    vertical_force_n: float
    drag_force_n: float
    side_force_n: float
    sink_rate_m_s: float | None
    meta: ResultMeta

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.gear_id.strip():
            raise LandingGearError("loadcase id and gear_id are required")
        finite(self.vertical_force_n, "loadcase.vertical_force_n")
        finite(self.drag_force_n, "loadcase.drag_force_n")
        finite(self.side_force_n, "loadcase.side_force_n")
        if self.sink_rate_m_s is not None:
            finite(self.sink_rate_m_s, "loadcase.sink_rate_m_s")

    @property
    def resultant_force_n(self) -> float:
        return sqrt(
            self.vertical_force_n * self.vertical_force_n
            + self.drag_force_n * self.drag_force_n
            + self.side_force_n * self.side_force_n
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "caseId": self.case_id,
            "kind": self.kind.value,
            "gearId": self.gear_id,
            "verticalForceN": self.vertical_force_n,
            "dragForceN": self.drag_force_n,
            "sideForceN": self.side_force_n,
            "sinkRateMS": self.sink_rate_m_s,
            "resultantForceN": self.resultant_force_n,
            "meta": self.meta.canonical(),
        }


def touchdown_load_case(
    shock: ShockStrokeResult,
    *,
    gear_id: str,
    case_id: str = "touchdown",
    drag_force_n: float = 0.0,
    side_force_n: float = 0.0,
) -> GearLoadCase:
    """Build a touchdown case from an evaluated shock stroke peak load."""

    drag = finite(drag_force_n, "drag_force_n")
    side = finite(side_force_n, "side_force_n")
    meta = result_meta(
        model="vehicle-systems.landing-gear.touchdown-load-case",
        inputs={
            "shock": shock.canonical_payload(),
            "gearId": gear_id,
            "dragForceN": drag,
            "sideForceN": side,
        },
        valid=shock.peak_load_n > 0.0,
        checks={"peak_load_positive": shock.peak_load_n > 0.0},
        detail="touchdown peak load from the oleo-pneumatic stroke response",
        fidelity=LandingGearFidelity.GROUND_TRANSIENT,
        units=LG_UNITS,
    )
    return GearLoadCase(
        case_id=case_id,
        kind=LoadCaseKind.TOUCHDOWN,
        gear_id=gear_id,
        vertical_force_n=shock.peak_load_n,
        drag_force_n=drag,
        side_force_n=side,
        sink_rate_m_s=shock.sink_rate_m_s,
        meta=meta,
    )


def braking_load_case(
    *,
    gear_id: str,
    static_load_n: float,
    mass_kg: float,
    deceleration_m_s2: float,
    cg_height_m: float,
    wheelbase_m: float,
    drag_share: float = 1.0,
    case_id: str = "braking",
) -> GearLoadCase:
    """Braking case: vertical load transfer plus the drag force share."""

    static = finite(static_load_n, "static_load_n", minimum=0.0)
    mass = finite(mass_kg, "mass_kg", positive=True)
    decel = finite(deceleration_m_s2, "deceleration_m_s2", minimum=0.0)
    height = finite(cg_height_m, "cg_height_m", positive=True)
    base = finite(wheelbase_m, "wheelbase_m", positive=True)
    share = finite(drag_share, "drag_share", minimum=0.0, maximum=1.0)
    transfer = mass * decel * height / base
    drag = mass * decel * share
    meta = result_meta(
        model="vehicle-systems.landing-gear.braking-load-case",
        inputs={
            "gearId": gear_id,
            "staticLoadN": static,
            "massKg": mass,
            "decelerationMS2": decel,
            "cgHeightM": height,
            "wheelbaseM": base,
            "dragShare": share,
        },
        valid=True,
        checks={"vertical_positive": static + transfer > 0.0},
        detail="braking pitch-moment load transfer onto the forward gear",
        fidelity=LandingGearFidelity.ANALYTICAL,
    )
    return GearLoadCase(
        case_id=case_id,
        kind=LoadCaseKind.BRAKING,
        gear_id=gear_id,
        vertical_force_n=static + transfer,
        drag_force_n=drag,
        side_force_n=0.0,
        sink_rate_m_s=None,
        meta=meta,
    )


def turning_load_case(
    *,
    gear_id: str,
    static_load_n: float,
    mass_kg: float,
    lateral_acceleration_m_s2: float,
    cg_height_m: float,
    track_m: float,
    case_id: str = "turning",
) -> GearLoadCase:
    """Turning case: lateral force plus roll-moment load transfer."""

    static = finite(static_load_n, "static_load_n", minimum=0.0)
    mass = finite(mass_kg, "mass_kg", positive=True)
    lateral_accel = finite(lateral_acceleration_m_s2, "lateral_acceleration_m_s2", minimum=0.0)
    height = finite(cg_height_m, "cg_height_m", positive=True)
    track = finite(track_m, "track_m", positive=True)
    side = mass * lateral_accel
    transfer = side * height / track
    meta = result_meta(
        model="vehicle-systems.landing-gear.turning-load-case",
        inputs={
            "gearId": gear_id,
            "staticLoadN": static,
            "massKg": mass,
            "lateralAccelerationMS2": lateral_accel,
            "cgHeightM": height,
            "trackM": track,
        },
        valid=True,
        checks={"side_force_positive": side > 0.0},
        detail="turning roll-moment load transfer onto the outer gear",
        fidelity=LandingGearFidelity.ANALYTICAL,
    )
    return GearLoadCase(
        case_id=case_id,
        kind=LoadCaseKind.TURNING,
        gear_id=gear_id,
        vertical_force_n=static + transfer,
        drag_force_n=0.0,
        side_force_n=side,
        sink_rate_m_s=None,
        meta=meta,
    )


@dataclass(frozen=True, slots=True)
class LoadCaseExport:
    """A deterministic, hashable set of gear load cases and its durability feed."""

    vehicle_id: str
    cases: tuple[GearLoadCase, ...]

    def __post_init__(self) -> None:
        if not self.vehicle_id.strip():
            raise LandingGearError("export.vehicle_id is required")
        if not self.cases:
            raise LandingGearError("export requires at least one load case")
        identifiers = [case.case_id for case in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise LandingGearError("DUPLICATE_LOAD_CASE_ID")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "vehicleId": self.vehicle_id,
            "cases": [
                case.canonical_payload()
                for case in sorted(self.cases, key=lambda item: item.case_id)
            ],
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical_payload())

    def case(self, case_id: str) -> GearLoadCase:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise LandingGearError(f"UNKNOWN_LOAD_CASE:{case_id}")

    def durability_load_histories(self) -> tuple[LoadHistory, ...]:
        """One pulse history per case, ready for rainflow cycle counting."""

        histories: list[LoadHistory] = []
        for case in sorted(self.cases, key=lambda item: item.case_id):
            peak = case.resultant_force_n
            histories.append(
                LoadHistory(
                    channel=f"{case.gear_id}.{case.kind.value}.force",
                    unit="N",
                    time_s=(0.0, 1.0, 2.0),
                    values=(0.0, peak, 0.0),
                )
            )
        return tuple(histories)

    def meta(self) -> ResultMeta:
        return result_meta(
            model="vehicle-systems.landing-gear.load-case-export",
            inputs=self.canonical_payload(),
            valid=True,
            detail="gear load-case export for structural sizing and durability",
            fidelity=LandingGearFidelity.ANALYTICAL,
        )


def export_load_cases(vehicle_id: str, cases: tuple[GearLoadCase, ...]) -> LoadCaseExport:
    """Collect gear load cases into a deterministic, hashable export."""

    return LoadCaseExport(vehicle_id=vehicle_id, cases=cases)


def native_structural_capability(*, present: bool = False) -> bool:
    """Whether a native structural FEA/damage engine is wired."""

    return present


def require_native_structural(*, present: bool = False) -> None:
    """Gear structural sizing requires a native engine; else fail closed."""

    if not native_structural_capability(present=present):
        raise CapabilityUnavailable(
            f"{_NATIVE_REQUIREMENT} is not available; gear structural margins cannot be claimed"
        )


__all__ = [
    "GearLoadCase",
    "LoadCaseExport",
    "LoadCaseKind",
    "braking_load_case",
    "export_load_cases",
    "native_structural_capability",
    "require_native_structural",
    "touchdown_load_case",
    "turning_load_case",
]
