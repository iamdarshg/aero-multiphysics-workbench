"""Operating-point dimensions for multi-point off-design evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from ..canonical import content_digest
from .errors import OffdesignInputError

MAX_OFFDESIGN_POINTS = 32


def _check_positive(label: str, value: float | None) -> None:
    if value is not None and (not isfinite(value) or value <= 0.0):
        raise OffdesignInputError(f"OPERATING_POINT_INVALID:{label}:{value}")


def _check_non_negative(label: str, value: float | None) -> None:
    if value is not None and (not isfinite(value) or value < 0.0):
        raise OffdesignInputError(f"OPERATING_POINT_INVALID:{label}:{value}")


def _check_finite(label: str, value: float | None) -> None:
    if value is not None and not isfinite(value):
        raise OffdesignInputError(f"OPERATING_POINT_INVALID:{label}:{value}")


@dataclass(frozen=True, slots=True)
class OperatingPoint:
    """One off-design operating point; every dimension is optional except identity."""

    point_id: str
    ambient_pressure_pa: float | None = None
    ambient_temperature_k: float | None = None
    ambient_density_kg_m3: float | None = None
    inlet_velocity_m_s: float | None = None
    inlet_mach: float | None = None
    spool_speeds_rpm: tuple[tuple[str, float], ...] = ()
    shaft_torque_n_m: float | None = None
    shaft_load_w: float | None = None
    throttle: float | None = None
    heat_input_w: float | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    state_of_charge: float | None = None
    mass_flow_kg_s: float | None = None
    vgv_angle_deg: float | None = None
    bleed_fraction: float | None = None
    nozzle_area_m2: float | None = None
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.point_id.strip():
            raise OffdesignInputError("OPERATING_POINT_ID_REQUIRED")
        for label, value in (
            ("ambientPressurePa", self.ambient_pressure_pa),
            ("ambientTemperatureK", self.ambient_temperature_k),
            ("ambientDensityKgM3", self.ambient_density_kg_m3),
            ("massFlowKgS", self.mass_flow_kg_s),
            ("nozzleAreaM2", self.nozzle_area_m2),
        ):
            _check_positive(label, value)
        for label, value in (
            ("shaftLoadW", self.shaft_load_w),
            ("heatInputW", self.heat_input_w),
        ):
            _check_non_negative(label, value)
        for label, value in (
            ("inletVelocityMS", self.inlet_velocity_m_s),
            ("inletMach", self.inlet_mach),
            ("shaftTorqueNM", self.shaft_torque_n_m),
            ("voltageV", self.voltage_v),
            ("currentA", self.current_a),
            ("vgvAngleDeg", self.vgv_angle_deg),
        ):
            _check_finite(label, value)
        if self.throttle is not None and (
            not isfinite(self.throttle) or not 0.0 <= self.throttle <= 1.0
        ):
            raise OffdesignInputError(f"OPERATING_POINT_INVALID:throttle:{self.throttle}")
        if self.state_of_charge is not None and (
            not isfinite(self.state_of_charge) or not 0.0 <= self.state_of_charge <= 1.0
        ):
            raise OffdesignInputError(f"OPERATING_POINT_INVALID:soc:{self.state_of_charge}")
        if self.bleed_fraction is not None and (
            not isfinite(self.bleed_fraction) or not 0.0 <= self.bleed_fraction < 1.0
        ):
            raise OffdesignInputError(
                f"OPERATING_POINT_INVALID:bleedFraction:{self.bleed_fraction}"
            )
        if not isfinite(self.weight) or self.weight < 0.0:
            raise OffdesignInputError(f"OPERATING_POINT_INVALID:weight:{self.weight}")
        seen: set[str] = set()
        for shaft_id, speed in self.spool_speeds_rpm:
            if not shaft_id.strip():
                raise OffdesignInputError("OPERATING_POINT_SHAFT_ID_REQUIRED")
            if shaft_id in seen:
                raise OffdesignInputError(f"OPERATING_POINT_DUPLICATE_SHAFT:{shaft_id}")
            seen.add(shaft_id)
            if not isfinite(speed) or speed < 0.0:
                raise OffdesignInputError(
                    f"OPERATING_POINT_INVALID:spoolSpeed:{shaft_id}:{speed}"
                )

    def canonical(self) -> dict[str, object]:
        return {
            "pointId": self.point_id,
            "ambientPressurePa": self.ambient_pressure_pa,
            "ambientTemperatureK": self.ambient_temperature_k,
            "ambientDensityKgM3": self.ambient_density_kg_m3,
            "inletVelocityMS": self.inlet_velocity_m_s,
            "inletMach": self.inlet_mach,
            "spoolSpeedsRpm": [[shaft, speed] for shaft, speed in self.spool_speeds_rpm],
            "shaftTorqueNM": self.shaft_torque_n_m,
            "shaftLoadW": self.shaft_load_w,
            "throttle": self.throttle,
            "heatInputW": self.heat_input_w,
            "voltageV": self.voltage_v,
            "currentA": self.current_a,
            "stateOfCharge": self.state_of_charge,
            "massFlowKgS": self.mass_flow_kg_s,
            "vgvAngleDeg": self.vgv_angle_deg,
            "bleedFraction": self.bleed_fraction,
            "nozzleAreaM2": self.nozzle_area_m2,
            "weight": self.weight,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def operating_points_hash(points: tuple[OperatingPoint, ...]) -> str:
    if not points:
        raise OffdesignInputError("OFFDESIGN_NEEDS_AT_LEAST_ONE_POINT")
    if len(points) > MAX_OFFDESIGN_POINTS:
        raise OffdesignInputError(
            f"OFFDESIGN_TOO_MANY_POINTS:{len(points)}:{MAX_OFFDESIGN_POINTS}"
        )
    ids = [point.point_id for point in points]
    if len(set(ids)) != len(ids):
        raise OffdesignInputError("OFFDESIGN_DUPLICATE_POINT_ID")
    return content_digest(
        [point.canonical() for point in sorted(points, key=lambda item: item.point_id)]
    )


__all__ = [
    "MAX_OFFDESIGN_POINTS",
    "OperatingPoint",
    "operating_points_hash",
]
