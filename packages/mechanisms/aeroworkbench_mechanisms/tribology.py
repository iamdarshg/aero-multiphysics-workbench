"""Tribology: friction, power loss, wear, and lubrication regime.

A generic contact/friction interface carries normal load, sliding speed,
friction coefficient, hardness, and an Archard wear coefficient, yielding
friction force, power loss, heat generation, and wear rate for energy, thermal,
and life closures. When a lubricant state is supplied, a Hamrock-Dowson line
contact film thickness and the lambda ratio classify the lubrication regime.
Detailed EHL/contact-FEA is a native seam that fails closed when absent.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import StrEnum
from math import sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .lubrication import LubricationState
from .provenance import analytical_provenance
from .validity import CapabilityUnavailable, MechanismError, Validity, finite

_NATIVE_TRIBOLOGY_IMPLEMENTATION = "declared-tribology-fea-interface"


class LubricationRegime(StrEnum):
    """Lubrication regime from the lambda ratio."""

    DRY = "dry"
    BOUNDARY = "boundary"
    MIXED = "mixed"
    ELASTOHYDRODYNAMIC = "elastohydrodynamic"


@dataclass(frozen=True, slots=True)
class ContactInterface:
    """One generic contact/friction interface."""

    interface_id: str
    normal_load_n: float
    sliding_velocity_m_s: float
    friction_coefficient: float
    hardness_pa: float
    wear_coefficient: float
    contact_area_m2: float
    effective_radius_m: float
    contact_length_m: float
    roughness_rq1_m: float
    roughness_rq2_m: float
    effective_modulus_pa: float

    def __post_init__(self) -> None:
        if not self.interface_id.strip():
            raise MechanismError("contact.interface_id is required")
        finite(self.normal_load_n, "contact.normal_load_n", minimum=0.0)
        finite(self.sliding_velocity_m_s, "contact.sliding_velocity_m_s", minimum=0.0)
        finite(self.friction_coefficient, "contact.friction_coefficient", minimum=0.0, maximum=2.0)
        finite(self.hardness_pa, "contact.hardness_pa", positive=True)
        finite(self.wear_coefficient, "contact.wear_coefficient", minimum=0.0)
        finite(self.contact_area_m2, "contact.contact_area_m2", positive=True)
        finite(self.effective_radius_m, "contact.effective_radius_m", positive=True)
        finite(self.contact_length_m, "contact.contact_length_m", positive=True)
        finite(self.roughness_rq1_m, "contact.roughness_rq1_m", minimum=0.0)
        finite(self.roughness_rq2_m, "contact.roughness_rq2_m", minimum=0.0)
        finite(self.effective_modulus_pa, "contact.effective_modulus_pa", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "normal_load_n": self.normal_load_n,
            "sliding_velocity_m_s": self.sliding_velocity_m_s,
            "friction_coefficient": self.friction_coefficient,
            "hardness_pa": self.hardness_pa,
            "wear_coefficient": self.wear_coefficient,
            "contact_area_m2": self.contact_area_m2,
            "effective_radius_m": self.effective_radius_m,
            "contact_length_m": self.contact_length_m,
            "roughness_rq1_m": self.roughness_rq1_m,
            "roughness_rq2_m": self.roughness_rq2_m,
            "effective_modulus_pa": self.effective_modulus_pa,
        }


@dataclass(frozen=True, slots=True)
class TribologyResult:
    """Evaluated friction, wear, heat, film, and regime."""

    interface_id: str
    friction_force_n: float
    friction_power_w: float
    heat_generation_w: float
    wear_volume_rate_m3_s: float
    wear_depth_rate_m_s: float
    contact_pressure_pa: float
    film_thickness_m: float
    lambda_ratio: float
    regime: str
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "friction_force_n": "N",
            "friction_power_w": "W",
            "heat_generation_w": "W",
            "wear_volume_rate_m3_s": "m3/s",
            "wear_depth_rate_m_s": "m/s",
            "contact_pressure_pa": "Pa",
            "film_thickness_m": "m",
            "lambda_ratio": "dimensionless",
        }

    def loss_to_thermal(self) -> dict[str, float]:
        return {"heat_generation_w": self.heat_generation_w}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "friction_force_n": self.friction_force_n,
            "friction_power_w": self.friction_power_w,
            "heat_generation_w": self.heat_generation_w,
            "wear_volume_rate_m3_s": self.wear_volume_rate_m3_s,
            "lambda_ratio": self.lambda_ratio,
            "regime": self.regime,
        }


def _film_thickness(interface: ContactInterface, lubricant: LubricationState) -> float:
    """Hamrock-Dowson minimum film thickness for line contact."""

    alpha = lubricant.pressure_viscosity_coefficient_inv_pa
    dynamic = lubricant.dynamic_viscosity_pa_s
    modulus = interface.effective_modulus_pa
    radius = interface.effective_radius_m
    speed = interface.sliding_velocity_m_s
    load_per_length = interface.normal_load_n / interface.contact_length_m
    dimensionless_material = alpha * modulus
    dimensionless_speed = dynamic * speed / (modulus * radius)
    dimensionless_load = load_per_length / (modulus * radius)
    if dimensionless_speed <= 0.0 or dimensionless_load <= 0.0:
        return 0.0
    h_min = (
        2.65
        * dimensionless_material**0.54
        * dimensionless_speed**0.70
        * dimensionless_load**-0.13
    )
    return float(radius * h_min)


def _regime(lambda_ratio: float) -> LubricationRegime:
    if lambda_ratio >= 3.0:
        return LubricationRegime.ELASTOHYDRODYNAMIC
    if lambda_ratio >= 1.0:
        return LubricationRegime.MIXED
    return LubricationRegime.BOUNDARY


def evaluate_contact_friction(
    interface: ContactInterface,
    lubricant: LubricationState | None = None,
) -> TribologyResult:
    """Evaluate friction power, Archard wear, and lubrication regime."""

    load = interface.normal_load_n
    speed = interface.sliding_velocity_m_s
    friction_force = interface.friction_coefficient * load
    friction_power = friction_force * speed
    wear_volume_rate = interface.wear_coefficient * load * speed / interface.hardness_pa
    wear_depth_rate = wear_volume_rate / interface.contact_area_m2
    contact_pressure = load / interface.contact_area_m2
    if lubricant is None:
        film_thickness = 0.0
        lambda_ratio = 0.0
        regime = LubricationRegime.DRY
    else:
        film_thickness = _film_thickness(interface, lubricant)
        composite = sqrt(interface.roughness_rq1_m**2 + interface.roughness_rq2_m**2)
        lambda_ratio = film_thickness / composite if composite > 0.0 else 0.0
        regime = _regime(lambda_ratio)
    checks = {
        "friction_coefficient_bounded": 0.0 <= interface.friction_coefficient <= 2.0,
        "friction_power_nonnegative": friction_power >= 0.0,
        "wear_rate_nonnegative": wear_volume_rate >= 0.0,
        "film_nonnegative": film_thickness >= 0.0,
    }
    inputs = {
        "contact": interface.canonical_payload(),
        "lubricant": lubricant.canonical_payload() if lubricant else None,
    }
    provenance = analytical_provenance(
        "mechanisms.tribology.contact-friction",
        inputs,
        assumptions=(
            "Coulomb friction; Archard wear; Hamrock-Dowson line-contact film",
        ),
    )
    return TribologyResult(
        interface_id=interface.interface_id,
        friction_force_n=friction_force,
        friction_power_w=friction_power,
        heat_generation_w=friction_power,
        wear_volume_rate_m3_s=wear_volume_rate,
        wear_depth_rate_m_s=wear_depth_rate,
        contact_pressure_pa=contact_pressure,
        film_thickness_m=film_thickness,
        lambda_ratio=lambda_ratio,
        regime=regime.value,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"regime={regime.value}",
        ),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class NativeTribologyStatus:
    """Actual status of the native tribology/FEA seam (never optimistic)."""

    state: str
    executable: str | None
    implementation: str
    detail: str


def native_tribology_status(executable: str = "tribo-fea") -> NativeTribologyStatus:
    """Report whether a native tribology/FEA engine is present and wired."""

    resolved = shutil.which(executable)
    if resolved is None:
        return NativeTribologyStatus(
            "unavailable",
            None,
            _NATIVE_TRIBOLOGY_IMPLEMENTATION,
            f"{executable} is not installed; native tribology fails closed",
        )
    return NativeTribologyStatus(
        "engine-present-not-wired",
        resolved,
        _NATIVE_TRIBOLOGY_IMPLEMENTATION,
        "engine present but no native contact-FEA case is wired",
    )


def solve_native_tribology(
    interface: ContactInterface,
    *,
    solver_name: str = "tribo-fea",
) -> TribologyResult:
    """Request the native contact-FEA level; always fails closed until wired."""

    status = native_tribology_status(solver_name)
    raise CapabilityUnavailable(status.detail)


__all__ = [
    "ContactInterface",
    "LubricationRegime",
    "NativeTribologyStatus",
    "TribologyResult",
    "evaluate_contact_friction",
    "native_tribology_status",
    "solve_native_tribology",
]
