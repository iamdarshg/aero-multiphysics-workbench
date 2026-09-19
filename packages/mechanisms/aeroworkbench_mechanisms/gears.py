"""Gear meshes: ratio, geometry, loads, mesh stiffness, and efficiency.

A gear pair is evaluated from its tooth counts, module, face width, and
pressure/helix angles. Tangential, radial, and axial mesh loads come from the
input torque, the pitch-line velocity sets the sliding speed, and the ISO/AGMA
Hertzian contact stress is checked against a declared allowable. Mesh loss
feeds thermal closure and mesh stiffness feeds system dynamics. A limit
violation fails closed with provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import cos, pi, radians, sqrt, tan
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .validity import LimitExceeded, MechanismError, Validity, finite, integer

_OMEGA_FROM_RPM = pi / 30.0


class GearKind(StrEnum):
    """The generic toothed-element taxonomy."""

    SPUR = "spur"
    HELICAL = "helical"
    BEVEL = "bevel"
    RACK_PINION = "rack-pinion"


@dataclass(frozen=True, slots=True)
class GearPairSpec:
    """One external gear pair with declared mesh and material data."""

    gear_id: str
    kind: GearKind
    teeth_driving: int
    teeth_driven: int
    normal_module_m: float
    face_width_m: float
    pressure_angle_deg: float = 20.0
    helix_angle_deg: float = 0.0
    mesh_efficiency: float = 0.98
    backlash_m: float = 0.0
    mesh_stiffness_n_m: float = 0.0
    youngs_modulus_pa: float = 206.0e9
    poisson_ratio: float = 0.3
    allowable_contact_stress_pa: float | None = None
    allowable_torque_n_m: float | None = None

    def __post_init__(self) -> None:
        if not self.gear_id.strip():
            raise MechanismError("gear.gear_id is required")
        integer(self.teeth_driving, "gear.teeth_driving", minimum=1, maximum=1000)
        integer(self.teeth_driven, "gear.teeth_driven", minimum=1, maximum=1000)
        finite(self.normal_module_m, "gear.normal_module_m", positive=True)
        finite(self.face_width_m, "gear.face_width_m", positive=True)
        finite(self.pressure_angle_deg, "gear.pressure_angle_deg", positive=True, maximum=45.0)
        finite(self.helix_angle_deg, "gear.helix_angle_deg", minimum=0.0, maximum=45.0)
        finite(
            self.mesh_efficiency,
            "gear.mesh_efficiency",
            positive=True,
            maximum=1.0,
        )
        finite(self.backlash_m, "gear.backlash_m", minimum=0.0)
        finite(self.mesh_stiffness_n_m, "gear.mesh_stiffness_n_m", minimum=0.0)
        finite(self.youngs_modulus_pa, "gear.youngs_modulus_pa", positive=True)
        finite(self.poisson_ratio, "gear.poisson_ratio", minimum=0.0, maximum=0.5)
        if self.allowable_contact_stress_pa is not None:
            finite(
                self.allowable_contact_stress_pa,
                "gear.allowable_contact_stress_pa",
                positive=True,
            )
        if self.allowable_torque_n_m is not None:
            finite(self.allowable_torque_n_m, "gear.allowable_torque_n_m", positive=True)

    @property
    def gear_ratio(self) -> float:
        return self.teeth_driven / self.teeth_driving

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gear_id": self.gear_id,
            "kind": self.kind.value,
            "teeth_driving": self.teeth_driving,
            "teeth_driven": self.teeth_driven,
            "normal_module_m": self.normal_module_m,
            "face_width_m": self.face_width_m,
            "pressure_angle_deg": self.pressure_angle_deg,
            "helix_angle_deg": self.helix_angle_deg,
            "mesh_efficiency": self.mesh_efficiency,
            "backlash_m": self.backlash_m,
            "mesh_stiffness_n_m": self.mesh_stiffness_n_m,
            "youngs_modulus_pa": self.youngs_modulus_pa,
            "poisson_ratio": self.poisson_ratio,
            "allowable_contact_stress_pa": self.allowable_contact_stress_pa,
            "allowable_torque_n_m": self.allowable_torque_n_m,
        }


@dataclass(frozen=True, slots=True)
class GearResult:
    """Evaluated gear-mesh state feeding dynamics, thermal, and life."""

    gear_id: str
    kind: str
    gear_ratio: float
    pitch_diameter_driving_m: float
    pitch_line_velocity_m_s: float
    tangential_load_n: float
    radial_load_n: float
    axial_load_n: float
    mesh_stiffness_n_m: float
    contact_stress_pa: float
    power_in_w: float
    power_out_w: float
    power_loss_w: float
    heat_generation_w: float
    efficiency: float
    utilization: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "gear_ratio": "dimensionless",
            "pitch_diameter_driving_m": "m",
            "pitch_line_velocity_m_s": "m/s",
            "tangential_load_n": "N",
            "radial_load_n": "N",
            "axial_load_n": "N",
            "mesh_stiffness_n_m": "N/m",
            "contact_stress_pa": "Pa",
            "power_in_w": "W",
            "power_out_w": "W",
            "power_loss_w": "W",
            "heat_generation_w": "W",
            "efficiency": "dimensionless",
        }

    def loss_to_thermal(self) -> dict[str, float]:
        return {"heat_generation_w": self.heat_generation_w}

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "gear_id": self.gear_id,
            "gear_ratio": self.gear_ratio,
            "tangential_load_n": self.tangential_load_n,
            "contact_stress_pa": self.contact_stress_pa,
            "power_loss_w": self.power_loss_w,
            "efficiency": self.efficiency,
        }


def evaluate_gear_pair(
    spec: GearPairSpec,
    *,
    input_torque_n_m: float,
    input_speed_rpm: float,
) -> GearResult:
    """Evaluate mesh loads, efficiency, contact stress, and limits."""

    torque = finite(input_torque_n_m, "input_torque_n_m", minimum=0.0)
    speed = finite(input_speed_rpm, "input_speed_rpm", positive=True)
    pressure = radians(spec.pressure_angle_deg)
    helix = radians(spec.helix_angle_deg)
    driving_pitch = spec.normal_module_m * spec.teeth_driving / cos(helix)
    if driving_pitch <= 0.0:
        raise MechanismError("gear.pitch diameter must be positive")
    tangential = 2.0 * torque / driving_pitch
    radial = tangential * tan(pressure) / cos(helix)
    axial = tangential * tan(helix)
    velocity = pi * driving_pitch * speed / 60.0
    power_in = torque * speed * _OMEGA_FROM_RPM
    power_out = power_in * spec.mesh_efficiency
    power_loss = power_in - power_out
    ratio = spec.gear_ratio
    effective_modulus = spec.youngs_modulus_pa / (
        pi * (1.0 - spec.poisson_ratio**2)
    )
    contact_stress = effective_modulus**0.5 * sqrt(
        tangential / (spec.face_width_m * driving_pitch) * (ratio + 1.0) / ratio
    )
    utilization = (
        contact_stress / spec.allowable_contact_stress_pa
        if spec.allowable_contact_stress_pa
        else (torque / spec.allowable_torque_n_m if spec.allowable_torque_n_m else 0.0)
    )
    checks = {
        "efficiency_bounded": 0.0 < spec.mesh_efficiency <= 1.0,
        "contact_stress_within_allowable": (
            spec.allowable_contact_stress_pa is None
            or contact_stress <= spec.allowable_contact_stress_pa
        ),
        "torque_within_allowable": (
            spec.allowable_torque_n_m is None or torque <= spec.allowable_torque_n_m
        ),
        "power_closure": power_loss >= 0.0,
    }
    provenance = analytical_provenance(
        f"mechanisms.gears.{spec.kind.value}",
        {
            "gear": spec.canonical_payload(),
            "input_torque_n_m": torque,
            "input_speed_rpm": speed,
        },
        assumptions=("Hertzian line-contact stress; constant mesh efficiency",),
    )
    result = GearResult(
        gear_id=spec.gear_id,
        kind=spec.kind.value,
        gear_ratio=ratio,
        pitch_diameter_driving_m=driving_pitch,
        pitch_line_velocity_m_s=velocity,
        tangential_load_n=tangential,
        radial_load_n=radial,
        axial_load_n=axial,
        mesh_stiffness_n_m=spec.mesh_stiffness_n_m,
        contact_stress_pa=contact_stress,
        power_in_w=power_in,
        power_out_w=power_out,
        power_loss_w=power_loss,
        heat_generation_w=power_loss,
        efficiency=spec.mesh_efficiency,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="analytical gear-mesh load and contact-stress model",
        ),
        provenance=provenance,
    )
    violations: list[str] = []
    if (
        spec.allowable_contact_stress_pa is not None
        and contact_stress > spec.allowable_contact_stress_pa
    ):
        violations.append("contact_stress")
    if spec.allowable_torque_n_m is not None and torque > spec.allowable_torque_n_m:
        violations.append("torque")
    if violations:
        raise LimitExceeded(
            f"GEAR_LIMIT_EXCEEDED:{spec.gear_id}:{','.join(violations)}",
            violations=tuple(violations),
            provenance=provenance,
        )
    return result


__all__ = ["GearKind", "GearPairSpec", "GearResult", "evaluate_gear_pair"]
