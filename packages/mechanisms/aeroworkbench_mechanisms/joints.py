"""Generic joints, fasteners, bushings, splines, and couplings.

Bolted/clamped joints are evaluated with a Shigley-style load factor between
the bolt and member stiffness, so preload, clamp load, slip capacity, and
separation are explicit. Pin/hinge joints report bearing pressure and friction
torque. All kinds expose 6-DOF stiffness/damping and a friction/power-loss path
into energy closure; a declared limit violation fails closed with provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .provenance import analytical_provenance
from .supports import SixDofProperties
from .validity import LimitExceeded, MechanismError, Validity, finite


class JointKind(StrEnum):
    """The generic mechanical-joint taxonomy."""

    FIXED = "fixed"
    ELASTIC_SUPPORT = "elastic-support"
    BOLTED = "bolted"
    CLAMPED = "clamped"
    PIN = "pin"
    HINGE = "hinge"
    BUSHING = "bushing"
    SPLINE = "spline"
    COUPLING = "coupling"
    CONTACT = "contact"


@dataclass(frozen=True, slots=True)
class JointSpec:
    """A generic joint defined from typed 6-DOF and contact data."""

    joint_id: str
    kind: JointKind
    properties: SixDofProperties = SixDofProperties()
    preload_n: float = 0.0
    backlash_m: float = 0.0
    clearance_m: float = 0.0
    friction_coefficient: float = 0.0
    allowable_load_n: float | None = None
    allowable_pressure_pa: float | None = None

    def __post_init__(self) -> None:
        if not self.joint_id.strip():
            raise MechanismError("joint.joint_id is required")
        finite(self.preload_n, "joint.preload_n", minimum=0.0)
        finite(self.backlash_m, "joint.backlash_m", minimum=0.0)
        finite(self.clearance_m, "joint.clearance_m", minimum=0.0)
        finite(self.friction_coefficient, "joint.friction_coefficient", minimum=0.0)
        if self.allowable_load_n is not None:
            finite(self.allowable_load_n, "joint.allowable_load_n", positive=True)
        if self.allowable_pressure_pa is not None:
            finite(self.allowable_pressure_pa, "joint.allowable_pressure_pa", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "joint_id": self.joint_id,
            "kind": self.kind.value,
            "properties": self.properties.canonical_payload(),
            "preload_n": self.preload_n,
            "backlash_m": self.backlash_m,
            "clearance_m": self.clearance_m,
            "friction_coefficient": self.friction_coefficient,
            "allowable_load_n": self.allowable_load_n,
            "allowable_pressure_pa": self.allowable_pressure_pa,
        }


@dataclass(frozen=True, slots=True)
class JointResult:
    """Evaluated joint state feeding stiffness, thermal, and life closures."""

    joint_id: str
    kind: str
    stiffness_n_m: tuple[float, ...]
    damping_n_s_m: tuple[float, ...]
    preload_n: float
    clamp_load_n: float
    bolt_load_n: float
    interface_load_n: float
    slip_capacity_n: float
    friction_force_n: float
    friction_torque_n_m: float
    heat_generation_w: float
    contact_pressure_pa: float
    displacement_m: tuple[float, ...]
    backlash_m: float
    clearance_m: float
    utilization: float
    validity: Validity
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "stiffness_n_m": "N/m",
            "damping_n_s_m": "N*s/m",
            "preload_n": "N",
            "clamp_load_n": "N",
            "bolt_load_n": "N",
            "interface_load_n": "N",
            "slip_capacity_n": "N",
            "friction_force_n": "N",
            "friction_torque_n_m": "N*m",
            "heat_generation_w": "W",
            "contact_pressure_pa": "Pa",
            "displacement_m": "m",
            "backlash_m": "m",
            "clearance_m": "m",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "joint_id": self.joint_id,
            "kind": self.kind,
            "interface_load_n": self.interface_load_n,
            "friction_force_n": self.friction_force_n,
            "heat_generation_w": self.heat_generation_w,
            "contact_pressure_pa": self.contact_pressure_pa,
            "utilization": self.utilization,
        }


def _displacement(load: float, stiffness: float) -> float:
    return load / stiffness if stiffness > 0.0 else 0.0


def _enforce_limits(result: JointResult, spec: JointSpec) -> None:
    violations: list[str] = []
    if spec.allowable_load_n is not None and result.interface_load_n > spec.allowable_load_n:
        violations.append("load")
    if (
        spec.allowable_pressure_pa is not None
        and result.contact_pressure_pa > spec.allowable_pressure_pa
    ):
        violations.append("contact_pressure")
    if violations:
        raise LimitExceeded(
            f"JOINT_LIMIT_EXCEEDED:{spec.joint_id}:{','.join(violations)}",
            violations=tuple(violations),
            provenance=result.provenance,
        )


def evaluate_joint(
    spec: JointSpec,
    *,
    applied_load_n: tuple[float, float, float] = (0.0, 0.0, 0.0),
    applied_moment_n_m: float = 0.0,
    sliding_velocity_m_s: float = 0.0,
    contact_area_m2: float = 0.0,
) -> JointResult:
    """Evaluate a generic joint and fail closed on a declared limit."""

    load_vector = tuple(finite(value, "applied_load_n", minimum=0.0) for value in applied_load_n)
    moment = finite(applied_moment_n_m, "applied_moment_n_m", minimum=0.0)
    velocity = finite(sliding_velocity_m_s, "sliding_velocity_m_s", minimum=0.0)
    area = finite(contact_area_m2, "contact_area_m2", minimum=0.0)
    stiffness = spec.properties.translation_stiffness_n_m
    interface_load = sum(load_vector) + moment
    displacement = tuple(
        _displacement(load_vector[index], stiffness[index]) for index in range(3)
    )
    friction_force = spec.friction_coefficient * interface_load
    contact_pressure = interface_load / area if area > 0.0 else 0.0
    allowable = spec.allowable_load_n
    utilization = interface_load / allowable if allowable else 0.0
    checks = {
        "backlash_not_exceeded": all(value <= spec.backlash_m for value in displacement),
        "clearance_not_exceeded": all(value <= spec.clearance_m for value in displacement),
        "within_allowable_load": allowable is None or interface_load <= allowable,
    }
    provenance = analytical_provenance(
        f"mechanisms.joints.{spec.kind.value}",
        {
            "joint": spec.canonical_payload(),
            "applied_load_n": list(load_vector),
            "applied_moment_n_m": moment,
            "sliding_velocity_m_s": velocity,
            "contact_area_m2": area,
        },
        assumptions=("linear stiffness; friction from a declared Coulomb coefficient",),
    )
    result = JointResult(
        joint_id=spec.joint_id,
        kind=spec.kind.value,
        stiffness_n_m=tuple(stiffness),
        damping_n_s_m=tuple(spec.properties.translation_damping_n_s_m),
        preload_n=spec.preload_n,
        clamp_load_n=spec.preload_n,
        bolt_load_n=spec.preload_n + interface_load,
        interface_load_n=interface_load,
        slip_capacity_n=spec.friction_coefficient * spec.preload_n,
        friction_force_n=friction_force,
        friction_torque_n_m=friction_force * 0.5,
        heat_generation_w=friction_force * velocity,
        contact_pressure_pa=contact_pressure,
        displacement_m=displacement,
        backlash_m=spec.backlash_m,
        clearance_m=spec.clearance_m,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="linear joint stiffness with Coulomb friction loss",
        ),
        provenance=provenance,
    )
    _enforce_limits(result, spec)
    return result


@dataclass(frozen=True, slots=True)
class BoltedJointSpec:
    """A bolted/clamped joint with bolt and member stiffness."""

    joint_id: str
    bolt_count: int
    bolt_stiffness_n_m: float
    member_stiffness_n_m: float
    proof_load_n: float
    preload_fraction: float
    external_load_n: float
    friction_coefficient: float
    slip_factor: float = 1.0

    def __post_init__(self) -> None:
        if not self.joint_id.strip():
            raise MechanismError("bolt.joint_id is required")
        if isinstance(self.bolt_count, bool) or not isinstance(self.bolt_count, int):
            raise MechanismError("bolt.bolt_count must be an integer")
        if self.bolt_count < 1:
            raise MechanismError("bolt.bolt_count must be positive")
        finite(self.bolt_stiffness_n_m, "bolt.bolt_stiffness_n_m", positive=True)
        finite(self.member_stiffness_n_m, "bolt.member_stiffness_n_m", positive=True)
        finite(self.proof_load_n, "bolt.proof_load_n", positive=True)
        finite(
            self.preload_fraction,
            "bolt.preload_fraction",
            minimum=0.0,
            maximum=1.0,
        )
        finite(self.external_load_n, "bolt.external_load_n", minimum=0.0)
        finite(self.friction_coefficient, "bolt.friction_coefficient", minimum=0.0)
        finite(self.slip_factor, "bolt.slip_factor", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "joint_id": self.joint_id,
            "bolt_count": self.bolt_count,
            "bolt_stiffness_n_m": self.bolt_stiffness_n_m,
            "member_stiffness_n_m": self.member_stiffness_n_m,
            "proof_load_n": self.proof_load_n,
            "preload_fraction": self.preload_fraction,
            "external_load_n": self.external_load_n,
            "friction_coefficient": self.friction_coefficient,
            "slip_factor": self.slip_factor,
        }


def evaluate_bolted_joint(spec: BoltedJointSpec) -> JointResult:
    """Evaluate bolt/member load sharing and fail closed on separation."""

    load_factor = spec.bolt_stiffness_n_m / (
        spec.bolt_stiffness_n_m + spec.member_stiffness_n_m
    )
    total_preload = spec.preload_fraction * spec.proof_load_n * spec.bolt_count
    bolt_load = total_preload + load_factor * spec.external_load_n
    clamp_load = total_preload - (1.0 - load_factor) * spec.external_load_n
    slip_capacity = spec.slip_factor * spec.friction_coefficient * max(clamp_load, 0.0)
    bolt_capacity = spec.proof_load_n * spec.bolt_count
    utilization = bolt_load / bolt_capacity
    checks = {
        "no_separation": clamp_load >= 0.0,
        "within_proof_load": bolt_load <= bolt_capacity,
        "slip_capacity_sufficient": spec.external_load_n <= slip_capacity,
    }
    provenance = analytical_provenance(
        "mechanisms.joints.bolted",
        {"bolt": spec.canonical_payload()},
        assumptions=("Shigley load factor C = kb/(kb+km); uniform bolt sharing",),
    )
    result = JointResult(
        joint_id=spec.joint_id,
        kind=JointKind.BOLTED.value,
        stiffness_n_m=(spec.bolt_stiffness_n_m, spec.member_stiffness_n_m, 0.0),
        damping_n_s_m=(0.0, 0.0, 0.0),
        preload_n=total_preload,
        clamp_load_n=clamp_load,
        bolt_load_n=bolt_load,
        interface_load_n=spec.external_load_n,
        slip_capacity_n=slip_capacity,
        friction_force_n=spec.friction_coefficient * max(clamp_load, 0.0),
        friction_torque_n_m=0.0,
        heat_generation_w=0.0,
        contact_pressure_pa=0.0,
        displacement_m=(0.0, 0.0, 0.0),
        backlash_m=0.0,
        clearance_m=0.0,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail=f"load factor C={load_factor:.6g}",
        ),
        provenance=provenance,
    )
    violations: list[str] = []
    if clamp_load < 0.0:
        violations.append("separation")
    if bolt_load > bolt_capacity:
        violations.append("proof_load")
    if violations:
        raise LimitExceeded(
            f"BOLT_LIMIT_EXCEEDED:{spec.joint_id}:{','.join(violations)}",
            violations=tuple(violations),
            provenance=provenance,
        )
    return result


@dataclass(frozen=True, slots=True)
class PinJointSpec:
    """A pin/hinge joint loaded through a cylindrical bearing surface."""

    joint_id: str
    pin_diameter_m: float
    length_m: float
    load_n: float
    friction_coefficient: float
    angle_deg: float = 0.0
    angular_velocity_rad_s: float = 0.0
    allowable_pressure_pa: float | None = None
    allowable_load_n: float | None = None

    def __post_init__(self) -> None:
        if not self.joint_id.strip():
            raise MechanismError("pin.joint_id is required")
        finite(self.pin_diameter_m, "pin.pin_diameter_m", positive=True)
        finite(self.length_m, "pin.length_m", positive=True)
        finite(self.load_n, "pin.load_n", minimum=0.0)
        finite(self.friction_coefficient, "pin.friction_coefficient", minimum=0.0)
        finite(self.angle_deg, "pin.angle_deg")
        finite(self.angular_velocity_rad_s, "pin.angular_velocity_rad_s", minimum=0.0)
        if self.allowable_pressure_pa is not None:
            finite(self.allowable_pressure_pa, "pin.allowable_pressure_pa", positive=True)
        if self.allowable_load_n is not None:
            finite(self.allowable_load_n, "pin.allowable_load_n", positive=True)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "joint_id": self.joint_id,
            "pin_diameter_m": self.pin_diameter_m,
            "length_m": self.length_m,
            "load_n": self.load_n,
            "friction_coefficient": self.friction_coefficient,
            "angle_deg": self.angle_deg,
            "angular_velocity_rad_s": self.angular_velocity_rad_s,
            "allowable_pressure_pa": self.allowable_pressure_pa,
            "allowable_load_n": self.allowable_load_n,
        }


def evaluate_pin_hinge(spec: PinJointSpec) -> JointResult:
    """Evaluate pin bearing pressure and friction torque; fail closed on limit."""

    area = spec.pin_diameter_m * spec.length_m
    bearing_pressure = spec.load_n / area
    friction_torque = spec.friction_coefficient * spec.load_n * spec.pin_diameter_m / 2.0
    heat = friction_torque * spec.angular_velocity_rad_s
    utilization = (
        bearing_pressure / spec.allowable_pressure_pa
        if spec.allowable_pressure_pa
        else (spec.load_n / spec.allowable_load_n if spec.allowable_load_n else 0.0)
    )
    checks = {
        "pressure_within_allowable": (
            spec.allowable_pressure_pa is None or bearing_pressure <= spec.allowable_pressure_pa
        ),
        "load_within_allowable": (
            spec.allowable_load_n is None or spec.load_n <= spec.allowable_load_n
        ),
    }
    provenance = analytical_provenance(
        "mechanisms.joints.pin-hinge",
        {"pin": spec.canonical_payload()},
        assumptions=("uniform bearing pressure over the projected pin area",),
    )
    result = JointResult(
        joint_id=spec.joint_id,
        kind=JointKind.PIN.value,
        stiffness_n_m=(0.0, 0.0, 0.0),
        damping_n_s_m=(0.0, 0.0, 0.0),
        preload_n=0.0,
        clamp_load_n=0.0,
        bolt_load_n=0.0,
        interface_load_n=spec.load_n,
        slip_capacity_n=0.0,
        friction_force_n=spec.friction_coefficient * spec.load_n,
        friction_torque_n_m=friction_torque,
        heat_generation_w=heat,
        contact_pressure_pa=bearing_pressure,
        displacement_m=(0.0, 0.0, 0.0),
        backlash_m=0.0,
        clearance_m=0.0,
        utilization=utilization,
        validity=Validity(
            passed=all(checks.values()),
            checks=checks,
            detail="pin bearing pressure and Coulomb friction torque",
        ),
        provenance=provenance,
    )
    violations: list[str] = []
    if (
        spec.allowable_pressure_pa is not None
        and bearing_pressure > spec.allowable_pressure_pa
    ):
        violations.append("contact_pressure")
    if spec.allowable_load_n is not None and spec.load_n > spec.allowable_load_n:
        violations.append("load")
    if violations:
        raise LimitExceeded(
            f"PIN_LIMIT_EXCEEDED:{spec.joint_id}:{','.join(violations)}",
            violations=tuple(violations),
            provenance=provenance,
        )
    return result


__all__ = [
    "BoltedJointSpec",
    "JointKind",
    "JointResult",
    "JointSpec",
    "PinJointSpec",
    "evaluate_bolted_joint",
    "evaluate_joint",
    "evaluate_pin_hinge",
]
