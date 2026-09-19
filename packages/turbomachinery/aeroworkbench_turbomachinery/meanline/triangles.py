"""Velocity triangles and the Euler turbomachinery work equation.

Angles are measured from the meridional direction toward the tangential
direction (``atan2(tangential, meridional)``). For an axial row the meridional
direction is axial; for a radial row it is radial; a mixed row splits the
meridional velocity between the axial and radial axes by a meridional angle.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin, tan

from .errors import MeanlineInputError


@dataclass(frozen=True, slots=True)
class VelocityTriangle:
    """Consistent absolute/relative velocity triangle at one station."""

    station_id: str
    blade_speed_m_s: float
    axial_velocity_m_s: float
    radial_velocity_m_s: float
    tangential_velocity_m_s: float
    meridional_velocity_m_s: float
    absolute_velocity_m_s: float
    relative_velocity_m_s: float
    relative_tangential_velocity_m_s: float
    absolute_angle_deg: float
    relative_angle_deg: float
    flow_coefficient: float

    @property
    def is_rotating(self) -> bool:
        return self.blade_speed_m_s != 0.0

    def canonical(self) -> dict[str, object]:
        return {
            "stationId": self.station_id,
            "bladeSpeedMs": self.blade_speed_m_s,
            "axialVelocityMs": self.axial_velocity_m_s,
            "radialVelocityMs": self.radial_velocity_m_s,
            "tangentialVelocityMs": self.tangential_velocity_m_s,
            "meridionalVelocityMs": self.meridional_velocity_m_s,
            "absoluteVelocityMs": self.absolute_velocity_m_s,
            "relativeVelocityMs": self.relative_velocity_m_s,
            "relativeTangentialVelocityMs": self.relative_tangential_velocity_m_s,
            "absoluteAngleDeg": self.absolute_angle_deg,
            "relativeAngleDeg": self.relative_angle_deg,
            "flowCoefficient": self.flow_coefficient,
        }


def solve_triangle(
    *,
    station_id: str,
    blade_speed_m_s: float,
    axial_velocity_m_s: float,
    tangential_velocity_m_s: float,
    radial_velocity_m_s: float = 0.0,
) -> VelocityTriangle:
    """Build a velocity triangle from the Cartesian velocity components."""

    if not station_id.strip():
        raise MeanlineInputError("STATION_ID_REQUIRED")
    meridional = hypot(axial_velocity_m_s, radial_velocity_m_s)
    absolute = hypot(meridional, tangential_velocity_m_s)
    relative_tangential = tangential_velocity_m_s - blade_speed_m_s
    relative = hypot(meridional, relative_tangential)
    absolute_angle = degrees(atan2(tangential_velocity_m_s, meridional))
    relative_angle = degrees(atan2(relative_tangential, meridional))
    flow_coefficient = meridional / blade_speed_m_s if blade_speed_m_s != 0.0 else 0.0
    return VelocityTriangle(
        station_id=station_id,
        blade_speed_m_s=blade_speed_m_s,
        axial_velocity_m_s=axial_velocity_m_s,
        radial_velocity_m_s=radial_velocity_m_s,
        tangential_velocity_m_s=tangential_velocity_m_s,
        meridional_velocity_m_s=meridional,
        absolute_velocity_m_s=absolute,
        relative_velocity_m_s=relative,
        relative_tangential_velocity_m_s=relative_tangential,
        absolute_angle_deg=absolute_angle,
        relative_angle_deg=relative_angle,
        flow_coefficient=flow_coefficient,
    )


def triangle_from_angle(
    *,
    station_id: str,
    blade_speed_m_s: float,
    meridional_velocity_m_s: float,
    absolute_angle_deg: float,
    meridional_angle_deg: float = 0.0,
) -> VelocityTriangle:
    """Build a triangle from a meridional velocity and an absolute flow angle.

    ``meridional_angle_deg`` places the meridional velocity: 0 is axial, 90 is
    radial, and intermediate values describe a mixed-flow surface.
    """

    tangential = meridional_velocity_m_s * tan(radians(absolute_angle_deg))
    meridional_radians = radians(meridional_angle_deg)
    axial = meridional_velocity_m_s * cos(meridional_radians)
    radial = meridional_velocity_m_s * sin(meridional_radians)
    return solve_triangle(
        station_id=station_id,
        blade_speed_m_s=blade_speed_m_s,
        axial_velocity_m_s=axial,
        tangential_velocity_m_s=tangential,
        radial_velocity_m_s=radial,
    )


def triangle_from_relative_angle(
    *,
    station_id: str,
    blade_speed_m_s: float,
    meridional_velocity_m_s: float,
    relative_angle_deg: float,
    meridional_angle_deg: float = 0.0,
) -> VelocityTriangle:
    """Build a triangle from a meridional velocity and a relative flow angle."""

    relative_tangential = meridional_velocity_m_s * tan(radians(relative_angle_deg))
    tangential = blade_speed_m_s + relative_tangential
    meridional_radians = radians(meridional_angle_deg)
    axial = meridional_velocity_m_s * cos(meridional_radians)
    radial = meridional_velocity_m_s * sin(meridional_radians)
    return solve_triangle(
        station_id=station_id,
        blade_speed_m_s=blade_speed_m_s,
        axial_velocity_m_s=axial,
        tangential_velocity_m_s=tangential,
        radial_velocity_m_s=radial,
    )


def euler_work_j_kg(*, inlet: VelocityTriangle, outlet: VelocityTriangle) -> float:
    """Specific Euler work ``U2*Vt2 - U1*Vt1`` (positive for work-adding rows)."""

    return (
        outlet.blade_speed_m_s * outlet.tangential_velocity_m_s
        - inlet.blade_speed_m_s * inlet.tangential_velocity_m_s
    )


def degree_of_reaction(*, inlet: VelocityTriangle, outlet: VelocityTriangle) -> float:
    """Static-enthalpy rise as a fraction of the Euler work (rotor reaction)."""

    work = euler_work_j_kg(inlet=inlet, outlet=outlet)
    if abs(work) < 1e-12:
        return 0.0
    velocity_change = (
        outlet.absolute_velocity_m_s**2 - inlet.absolute_velocity_m_s**2
    )
    return 1.0 - velocity_change / (2.0 * work)


__all__ = [
    "VelocityTriangle",
    "solve_triangle",
    "triangle_from_angle",
    "triangle_from_relative_angle",
    "euler_work_j_kg",
    "degree_of_reaction",
]
