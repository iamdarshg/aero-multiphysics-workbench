"""Seals: leakage, clearance, friction loss, and fluid-network feed.

Clearance and annular seals use the Hagen-Poiseuille pressure flow plus the
Couette drag term for the surface speed. Labyrinth seals use an orifice
discharge scaled by the number of throttling lands. Contact seals (lip/oring)
report declared leakage (zero when an effectively dry contact is declared).
Leakage is exposed as both volumetric and mass flow so it can enter a fluid
network; friction torque feeds energy/thermal closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import pi, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .validity import LimitExceeded, MechanismError, Validity, finite, integer

_OMEGA_FROM_RPM = pi / 30.0


class SealKind(StrEnum):
    """The generic seal taxonomy."""

    CLEARANCE = "clearance"
    ANNULAR = "annular"
    LABYRINTH = "labyrinth"
    LIP = "lip"
    ORING = "oring"
    BRUSH = "brush"


_CONTACT_SEALS = frozenset({SealKind.LIP.value, SealKind.ORING.value, SealKind.BRUSH.value})


@dataclass(frozen=True, slots=True)
class SealSpec:
    """One typed seal declaration."""

    seal_id: str
    kind: SealKind
    diameter_m: float
    clearance_m: float
    length_m: float
    land_count: int = 1
    discharge_coefficient: float = 0.65
    friction_coefficient: float = 0.1
    radial_preload_n: float = 0.0
    declared_leakage_m3_s: float | None = None
    allowable_leakage_m3_s: float | None = None

    def __post_init__(self) -> None:
        if not self.seal_id.strip():
            raise MechanismError("seal.seal_id is required")
        finite(self.diameter_m, "seal.diameter_m", positive=True)
        finite(self.clearance_m, "seal.clearance_m", minimum=0.0)
        finite(self.length_m, "seal.length_m", positive=True)
        integer(self.land_count, "seal.land_count", minimum=1, maximum=1000)
        finite(
            self.discharge_coefficient,
            "seal.discharge_coefficient",
            positive=True,
            maximum=1.0,
        )
        finite(self.friction_coefficient, "seal.friction_coefficient", minimum=0.0)
        finite(self.radial_preload_n, "seal.radial_preload_n", minimum=0.0)
        if self.declared_leakage_m3_s is not None:
            finite(self.declared_leakage_m3_s, "seal.declared_leakage_m3_s", minimum=0.0)
        if self.allowable_leakage_m3_s is not None:
            finite(self.allowable_leakage_m3_s, "seal.allowable_leakage_m3_s", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "seal_id": self.seal_id,
            "kind": self.kind.value,
            "diameter_m": self.diameter_m,
            "clearance_m": self.clearance_m,
            "length_m": self.length_m,
            "land_count": self.land_count,
            "discharge_coefficient": self.discharge_coefficient,
            "friction_coefficient": self.friction_coefficient,
            "radial_preload_n": self.radial_preload_n,
            "declared_leakage_m3_s": self.declared_leakage_m3_s,
            "allowable_leakage_m3_s": self.allowable_leakage_m3_s,
        }


@dataclass(frozen=True, slots=True)
class SealResult:
    """Evaluated seal leakage and loss for fluid/thermal networks."""

    seal_id: str
    kind: str
    leakage_volume_flow_m3_s: float
    leakage_mass_flow_kg_s: float
    clearance_m: float
    friction_torque_n_m: float
    heat_generation_w: float
    utilization: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "leakage_volume_flow_m3_s": "m3/s",
            "leakage_mass_flow_kg_s": "kg/s",
            "clearance_m": "m",
            "friction_torque_n_m": "N*m",
            "heat_generation_w": "W",
        }

    def leakage_to_fluid_network(self) -> dict[str, float]:
        """Scalar hand-off for a fluid-network participant."""

        return {
            "leakage_volume_flow_m3_s": self.leakage_volume_flow_m3_s,
            "leakage_mass_flow_kg_s": self.leakage_mass_flow_kg_s,
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "seal_id": self.seal_id,
            "kind": self.kind,
            "leakage_volume_flow_m3_s": self.leakage_volume_flow_m3_s,
            "leakage_mass_flow_kg_s": self.leakage_mass_flow_kg_s,
            "heat_generation_w": self.heat_generation_w,
        }


def _annular_leakage(
    spec: SealSpec, pressure_drop_pa: float, dynamic_viscosity_pa_s: float, surface_speed_m_s: float
) -> float:
    circumference = pi * spec.diameter_m
    pressure_flow = (
        circumference
        * spec.clearance_m**3
        * pressure_drop_pa
        / (12.0 * dynamic_viscosity_pa_s * spec.length_m)
    )
    couette_flow = circumference * spec.clearance_m * surface_speed_m_s / 2.0
    return pressure_flow + couette_flow


def _labyrinth_leakage(
    spec: SealSpec, pressure_drop_pa: float, density_kg_m3: float
) -> float:
    area = pi * spec.diameter_m * spec.clearance_m
    orifice = spec.discharge_coefficient * area * sqrt(2.0 * pressure_drop_pa / density_kg_m3)
    return orifice / sqrt(float(spec.land_count))


def evaluate_seal(
    spec: SealSpec,
    *,
    pressure_drop_pa: float,
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    speed_rpm: float = 0.0,
) -> SealResult:
    """Evaluate seal leakage and friction loss; fail closed on leakage limit."""

    pressure_drop = finite(pressure_drop_pa, "pressure_drop_pa", minimum=0.0)
    density = finite(density_kg_m3, "density_kg_m3", positive=True)
    viscosity = finite(dynamic_viscosity_pa_s, "dynamic_viscosity_pa_s", positive=True)
    speed = finite(speed_rpm, "speed_rpm", minimum=0.0)
    surface_speed = speed * _OMEGA_FROM_RPM * spec.diameter_m / 2.0
    if spec.kind.value in _CONTACT_SEALS:
        leakage = spec.declared_leakage_m3_s or 0.0
    elif spec.kind is SealKind.LABYRINTH:
        leakage = _labyrinth_leakage(spec, pressure_drop, density)
    else:
        leakage = _annular_leakage(spec, pressure_drop, viscosity, surface_speed)
    mass_flow = leakage * density
    friction_torque = (
        spec.friction_coefficient * spec.radial_preload_n * spec.diameter_m / 2.0
    )
    heat = friction_torque * speed * _OMEGA_FROM_RPM
    utilization = (
        leakage / spec.allowable_leakage_m3_s if spec.allowable_leakage_m3_s else 0.0
    )
    checks = {
        "pressure_drop_nonnegative": pressure_drop >= 0.0,
        "leakage_nonnegative": leakage >= 0.0,
        "leakage_within_allowable": (
            spec.allowable_leakage_m3_s is None or leakage <= spec.allowable_leakage_m3_s
        ),
    }
    provenance = analytical_provenance(
        f"mechanisms.seals.{spec.kind.value}",
        {
            "seal": spec.canonical_payload(),
            "pressure_drop_pa": pressure_drop,
            "density_kg_m3": density,
            "dynamic_viscosity_pa_s": viscosity,
            "speed_rpm": speed,
        },
        assumptions=("laminar annular flow with Couette drag; orifice labyrinth carryover",),
    )
    result = SealResult(
        seal_id=spec.seal_id,
        kind=spec.kind.value,
        leakage_volume_flow_m3_s=leakage,
        leakage_mass_flow_kg_s=mass_flow,
        clearance_m=spec.clearance_m,
        friction_torque_n_m=friction_torque,
        heat_generation_w=heat,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="analytical seal leakage and friction loss",
        ),
        provenance=provenance,
    )
    if (
        spec.allowable_leakage_m3_s is not None
        and leakage > spec.allowable_leakage_m3_s
    ):
        raise LimitExceeded(
            f"SEAL_LIMIT_EXCEEDED:{spec.seal_id}:leakage",
            violations=("leakage",),
            provenance=provenance,
        )
    return result


__all__ = ["SealKind", "SealResult", "SealSpec", "evaluate_seal"]
