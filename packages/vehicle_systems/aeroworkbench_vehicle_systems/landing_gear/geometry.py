"""Typed landing-gear architecture: legs, wheels, brakes, and shock absorbers.

The gear is a set of declared members in a body frame (``x`` forward, ``y``
starboard, ``z`` down). Geometry and mass are carried as unit-bearing
:class:`~aeroworkbench_airframe.units.Quantity` / ``Vec3`` values; the
attachment support reuses the mechanisms support contract. There is no default
geometry or mass: a missing member fails closed. ``content_hash`` makes an
assembly deterministic and hashable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_airframe import Quantity, Vec3, content_digest
from aeroworkbench_airframe.units import require_dimension
from aeroworkbench_mechanisms import SupportSpec

from .contracts import LG_UNITS, LandingGearFidelity, result_meta
from .errors import LandingGearError, finite

BODY_AXES = "body"


class GearArchitecture(StrEnum):
    """Declared landing-gear architecture (generic; no platform assumption)."""

    TRICYCLE = "tricycle"
    TAILDRAGGER = "taildragger"
    SKID = "skid"
    MULTI_BOGEY = "multi-bogey"


class GearRole(StrEnum):
    """The function of one gear leg/station."""

    NOSE = "nose"
    MAIN = "main"
    TAIL = "tail"
    SKID = "skid"


@dataclass(frozen=True, slots=True)
class WheelSpec:
    """A wheel + tire with friction, rolling-resistance, and spin inertia."""

    wheel_id: str
    radius: Quantity
    width: Quantity
    mass: Quantity
    spin_inertia: Quantity
    rolling_resistance_coefficient: float
    max_brake_friction_coefficient: float
    cornering_stiffness_n_per_rad: float = 0.0

    def __post_init__(self) -> None:
        if not self.wheel_id.strip():
            raise LandingGearError("wheel.wheel_id is required")
        require_dimension(self.radius, "length", "wheel.radius")
        require_dimension(self.width, "length", "wheel.width")
        require_dimension(self.mass, "mass", "wheel.mass")
        require_dimension(self.spin_inertia, "moment_of_inertia", "wheel.spin_inertia")
        if self.radius.value_si <= 0.0 or self.width.value_si <= 0.0:
            raise LandingGearError("wheel radius and width must be positive")
        if self.mass.value_si <= 0.0 or self.spin_inertia.value_si <= 0.0:
            raise LandingGearError("wheel mass and spin inertia must be positive")
        finite(
            self.rolling_resistance_coefficient,
            "wheel.rolling_resistance_coefficient",
            minimum=0.0,
            maximum=1.0,
        )
        finite(
            self.max_brake_friction_coefficient,
            "wheel.max_brake_friction_coefficient",
            positive=True,
        )

    @property
    def contact_patch_area_m2(self) -> float:
        """Declared rectangular contact patch (width x 0.25 radius)."""

        return self.width.value_si * 0.25 * self.radius.value_si

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "wheelId": self.wheel_id,
            "radius": self.radius.canonical(),
            "width": self.width.canonical(),
            "mass": self.mass.canonical(),
            "spinInertia": self.spin_inertia.canonical(),
            "rollingResistanceCoefficient": self.rolling_resistance_coefficient,
            "maxBrakeFrictionCoefficient": self.max_brake_friction_coefficient,
            "corneringStiffnessNPerRad": self.cornering_stiffness_n_per_rad,
        }


@dataclass(frozen=True, slots=True)
class BrakeSpec:
    """A wheel brake with a torque limit and anti-skid flag."""

    brake_id: str
    max_torque: Quantity
    friction_coefficient: float
    anti_skid: bool = False

    def __post_init__(self) -> None:
        if not self.brake_id.strip():
            raise LandingGearError("brake.brake_id is required")
        require_dimension(self.max_torque, "moment", "brake.max_torque")
        if self.max_torque.value_si <= 0.0:
            raise LandingGearError("brake.max_torque must be positive")
        finite(self.friction_coefficient, "brake.friction_coefficient", positive=True)

    def max_braking_force_n(self, wheel_radius_m: float) -> float:
        radius = finite(wheel_radius_m, "wheel_radius_m", positive=True)
        return self.max_torque.value_si / radius

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "brakeId": self.brake_id,
            "maxTorque": self.max_torque.canonical(),
            "frictionCoefficient": self.friction_coefficient,
            "antiSkid": self.anti_skid,
        }


@dataclass(frozen=True, slots=True)
class ShockAbsorberSpec:
    """An oleo-pneumatic strut: gas spring plus quadratic hydraulic damping."""

    absorber_id: str
    gas_charge_pressure: Quantity
    piston_area: Quantity
    initial_gas_length: Quantity
    polytropic_index: float
    hydraulic_damping_coefficient: float
    max_stroke: Quantity

    def __post_init__(self) -> None:
        if not self.absorber_id.strip():
            raise LandingGearError("absorber.absorber_id is required")
        require_dimension(self.gas_charge_pressure, "pressure", "absorber.gas_charge_pressure")
        require_dimension(self.piston_area, "area", "absorber.piston_area")
        require_dimension(self.initial_gas_length, "length", "absorber.initial_gas_length")
        require_dimension(self.max_stroke, "length", "absorber.max_stroke")
        if self.gas_charge_pressure.value_si <= 0.0:
            raise LandingGearError("absorber gas charge pressure must be positive")
        if self.piston_area.value_si <= 0.0 or self.initial_gas_length.value_si <= 0.0:
            raise LandingGearError("absorber piston area and gas length must be positive")
        if self.max_stroke.value_si <= 0.0:
            raise LandingGearError("absorber max stroke must be positive")
        if self.max_stroke.value_si >= self.initial_gas_length.value_si:
            raise LandingGearError("absorber max stroke must be below the gas length")
        finite(self.polytropic_index, "absorber.polytropic_index", positive=True)
        finite(
            self.hydraulic_damping_coefficient,
            "absorber.hydraulic_damping_coefficient",
            minimum=0.0,
        )

    @property
    def gas_preload_force_n(self) -> float:
        return self.gas_charge_pressure.value_si * self.piston_area.value_si

    def gas_force_n(self, stroke_m: float) -> float:
        stroke = finite(stroke_m, "stroke_m", minimum=0.0)
        if stroke >= self.initial_gas_length.value_si:
            raise LandingGearError("SHOCK_STROKE_EXCEEDS_GAS_LENGTH")
        volume_ratio = self.initial_gas_length.value_si / (
            self.initial_gas_length.value_si - stroke
        )
        return self.gas_preload_force_n * float(volume_ratio**self.polytropic_index)

    def damping_force_n(self, stroke_rate_m_s: float) -> float:
        rate = finite(stroke_rate_m_s, "stroke_rate_m_s")
        return self.hydraulic_damping_coefficient * rate * abs(rate)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "absorberId": self.absorber_id,
            "gasChargePressure": self.gas_charge_pressure.canonical(),
            "pistonArea": self.piston_area.canonical(),
            "initialGasLength": self.initial_gas_length.canonical(),
            "polytropicIndex": self.polytropic_index,
            "hydraulicDampingCoefficient": self.hydraulic_damping_coefficient,
            "maxStroke": self.max_stroke.canonical(),
        }


@dataclass(frozen=True, slots=True)
class GearLegSpec:
    """One leg/station: attachment, axle, wheel, brake, strut, and support."""

    leg_id: str
    role: GearRole
    attachment_point: Vec3
    axle_point: Vec3
    wheel: WheelSpec | None = None
    brake: BrakeSpec | None = None
    shock: ShockAbsorberSpec | None = None
    support: SupportSpec | None = None
    retractable: bool = False
    retracted_clearance: Quantity | None = None

    def __post_init__(self) -> None:
        if not self.leg_id.strip():
            raise LandingGearError("leg.leg_id is required")
        require_dimension(self.attachment_point, "length", "leg.attachment_point")
        require_dimension(self.axle_point, "length", "leg.axle_point")
        if self.attachment_point.frame != self.axle_point.frame:
            raise LandingGearError("LEG_FRAME_MISMATCH")
        if self.role is not GearRole.SKID and self.wheel is None:
            raise LandingGearError(f"WHEEL_REQUIRED:{self.leg_id}")
        if self.brake is not None and self.wheel is None:
            raise LandingGearError(f"BRAKE_REQUIRES_WHEEL:{self.leg_id}")
        if self.shock is not None and self.wheel is None and self.role is not GearRole.SKID:
            raise LandingGearError(f"SHOCK_REQUIRES_CONTACT_MEMBER:{self.leg_id}")
        if self.retracted_clearance is not None:
            require_dimension(self.retracted_clearance, "length", "leg.retracted_clearance")
            if self.retracted_clearance.value_si < 0.0:
                raise LandingGearError("leg.retracted_clearance must be non-negative")

    @property
    def frame(self) -> str:
        return self.axle_point.frame

    def contact_point(self) -> Vec3:
        """Static ground contact point: axle dropped by one wheel radius along -z."""

        offset = self.wheel.radius.value_si if self.wheel is not None else 0.0
        return Vec3(
            x=self.axle_point.x,
            y=self.axle_point.y,
            z=self.axle_point.z + offset,
            unit=self.axle_point.unit,
            frame=self.axle_point.frame,
        )

    def spin_inertia_kg_m2(self) -> float:
        if self.wheel is None:
            return 0.0
        return self.wheel.spin_inertia.value_si

    def rolling_resistance_coefficient(self) -> float:
        if self.wheel is None:
            return 0.0
        return self.wheel.rolling_resistance_coefficient

    def braking_friction_coefficient(self) -> float:
        if self.wheel is None:
            return 0.0
        coefficient = self.wheel.max_brake_friction_coefficient
        if self.brake is not None:
            coefficient = min(coefficient, self.brake.friction_coefficient)
        return coefficient

    def max_braking_force_n(self, normal_force_n: float, mu_runway: float) -> float:
        if self.wheel is None:
            return 0.0
        normal = finite(normal_force_n, "normal_force_n", minimum=0.0)
        mu = finite(mu_runway, "mu_runway", minimum=0.0)
        mu_limit = min(mu, self.wheel.max_brake_friction_coefficient)
        force = mu_limit * normal
        if self.brake is not None:
            force = min(force, self.brake.max_braking_force_n(self.wheel.radius.value_si))
        return force

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "legId": self.leg_id,
            "role": self.role.value,
            "attachmentPoint": self.attachment_point.canonical(),
            "axlePoint": self.axle_point.canonical(),
            "wheel": None if self.wheel is None else self.wheel.canonical_payload(),
            "brake": None if self.brake is None else self.brake.canonical_payload(),
            "shock": None if self.shock is None else self.shock.canonical_payload(),
            "support": None if self.support is None else self.support.canonical_payload(),
            "retractable": self.retractable,
            "retractedClearance": (
                None if self.retracted_clearance is None else self.retracted_clearance.canonical()
            ),
        }


@dataclass(frozen=True, slots=True)
class LandingGearAssembly:
    """A typed, deterministic set of gear legs in one declared body frame."""

    assembly_id: str
    architecture: GearArchitecture
    legs: tuple[GearLegSpec, ...]
    frame: str = BODY_AXES

    def __post_init__(self) -> None:
        if not self.assembly_id.strip():
            raise LandingGearError("assembly.assembly_id is required")
        if not self.frame.strip():
            raise LandingGearError("assembly.frame is required")
        if not self.legs:
            raise LandingGearError("assembly requires at least one leg")
        identifiers = [leg.leg_id for leg in self.legs]
        if len(identifiers) != len(set(identifiers)):
            raise LandingGearError("DUPLICATE_LEG_ID")
        for leg in self.legs:
            if leg.frame != self.frame:
                raise LandingGearError(f"LEG_FRAME_MISMATCH:{leg.leg_id}")
        roles = {leg.role for leg in self.legs}
        if self.architecture is GearArchitecture.SKID:
            if roles != {GearRole.SKID}:
                raise LandingGearError("SKID_ASSEMBLY_REQUIRES_ONLY_SKID_LEGS")
        elif GearRole.MAIN not in roles:
            raise LandingGearError("ASSEMBLY_REQUIRES_A_MAIN_LEG")

    def leg(self, leg_id: str) -> GearLegSpec:
        for candidate in self.legs:
            if candidate.leg_id == leg_id:
                return candidate
        raise LandingGearError(f"UNKNOWN_LEG:{leg_id}")

    def legs_with_role(self, role: GearRole) -> tuple[GearLegSpec, ...]:
        return tuple(leg for leg in self.legs if leg.role is role)

    @property
    def main_legs(self) -> tuple[GearLegSpec, ...]:
        return self.legs_with_role(GearRole.MAIN)

    @property
    def nose_legs(self) -> tuple[GearLegSpec, ...]:
        return self.legs_with_role(GearRole.NOSE)

    def contact_points(self) -> tuple[Vec3, ...]:
        return tuple(leg.contact_point() for leg in self.legs)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "assemblyId": self.assembly_id,
            "architecture": self.architecture.value,
            "frame": self.frame,
            "legs": [
                leg.canonical_payload()
                for leg in sorted(self.legs, key=lambda item: item.leg_id)
            ],
        }

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical_payload())

    def assembly_meta(self) -> dict[str, Any]:
        return result_meta(
            model="vehicle-systems.landing-gear.assembly",
            inputs=self.canonical_payload(),
            valid=True,
            fidelity=LandingGearFidelity.ANALYTICAL,
            detail="declared gear architecture",
            units=LG_UNITS,
        ).canonical()


def tricycle_gear(
    *,
    assembly_id: str,
    nose_leg: GearLegSpec,
    main_legs: tuple[GearLegSpec, ...],
    frame: str = BODY_AXES,
) -> LandingGearAssembly:
    """Build a nose + main tricycle assembly, validating the declared roles."""

    if nose_leg.role is not GearRole.NOSE:
        raise LandingGearError("TRICYCLE_NOSE_LEG_MUST_HAVE_NOSE_ROLE")
    if not main_legs or any(leg.role is not GearRole.MAIN for leg in main_legs):
        raise LandingGearError("TRICYCLE_MAIN_LEGS_MUST_HAVE_MAIN_ROLE")
    return LandingGearAssembly(
        assembly_id=assembly_id,
        architecture=GearArchitecture.TRICYCLE,
        legs=(nose_leg, *main_legs),
        frame=frame,
    )


def skid_gear(
    *, assembly_id: str, skid_legs: tuple[GearLegSpec, ...], frame: str = BODY_AXES
) -> LandingGearAssembly:
    """Build a skid/VTOL assembly of skid stations."""

    if not skid_legs or any(leg.role is not GearRole.SKID for leg in skid_legs):
        raise LandingGearError("SKID_LEGS_MUST_HAVE_SKID_ROLE")
    return LandingGearAssembly(
        assembly_id=assembly_id,
        architecture=GearArchitecture.SKID,
        legs=skid_legs,
        frame=frame,
    )


__all__ = [
    "BODY_AXES",
    "BrakeSpec",
    "GearArchitecture",
    "GearLegSpec",
    "GearRole",
    "LandingGearAssembly",
    "ShockAbsorberSpec",
    "WheelSpec",
    "skid_gear",
    "tricycle_gear",
]
