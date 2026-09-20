"""Canonical flap / slat / simple-airfoil fixtures for high-lift studies."""

from __future__ import annotations

from .devices import (
    DeflectionSchedule,
    DeviceIncrements,
    HighLiftConfiguration,
    HighLiftDevice,
    ScheduleEntry,
)
from .section import SectionStallParameters
from .wing import WingPlanform

MODEL_FIXTURES = "vehicle-systems.highlift.fixtures"


def simple_airfoil_section() -> SectionStallParameters:
    return SectionStallParameters(
        section_id="simple-airfoil",
        alpha_zero_lift_deg=-2.0,
        lift_slope_per_rad=5.8,
        alpha_stall_deg=14.0,
        cl_max=1.45,
        cd0=0.008,
        drag_k=0.012,
        cm0=-0.08,
        post_stall_drop_per_deg=0.045,
        post_stall_drag_rise_per_deg=0.006,
        deep_stall_alpha_deg=26.0,
        alpha_min_deg=-10.0,
        alpha_max_deg=30.0,
        source="vs04 canonical simple-airfoil fixture",
    )


def canonical_flap() -> HighLiftDevice:
    return HighLiftDevice(
        device_id="flap",
        parent_id="wing",
        kind="flap",
        chord_fraction=0.3,
        span_fraction=(0.1, 0.7),
        deflection_deg=0.0,
        deflection_limits_deg=(0.0, 40.0),
        increments=DeviceIncrements(
            dcl_per_deg=0.022,
            dcd_per_deg=0.0005,
            dcd_quad_per_deg2=0.00003,
            dcm_per_deg=-0.005,
            dstall_per_deg=-0.06,
            area_gain_per_deg=0.001,
        ),
    )


def canonical_slat() -> HighLiftDevice:
    return HighLiftDevice(
        device_id="slat",
        parent_id="wing",
        kind="slat",
        chord_fraction=0.15,
        span_fraction=(0.05, 0.95),
        deflection_deg=0.0,
        deflection_limits_deg=(0.0, 30.0),
        increments=DeviceIncrements(
            dcl_per_deg=0.012,
            dcd_per_deg=0.0002,
            dcd_quad_per_deg2=0.00001,
            dcm_per_deg=-0.001,
            dstall_per_deg=0.12,
            area_gain_per_deg=0.0005,
        ),
    )


def deflection_schedule() -> DeflectionSchedule:
    return DeflectionSchedule(
        schedule_id="vs04-canonical-schedule",
        entries=(
            ScheduleEntry(config_name="clean", deflections=(("flap", 0.0), ("slat", 0.0))),
            ScheduleEntry(
                config_name="takeoff", deflections=(("flap", 15.0), ("slat", 10.0))
            ),
            ScheduleEntry(
                config_name="landing", deflections=(("flap", 35.0), ("slat", 20.0))
            ),
        ),
    )


def _base_devices() -> tuple[HighLiftDevice, ...]:
    return (canonical_flap(), canonical_slat())


def clean_configuration() -> HighLiftConfiguration:
    base = HighLiftConfiguration(config_id="clean", devices=_base_devices())
    return base.with_schedule_config("clean", deflection_schedule())


def takeoff_configuration() -> HighLiftConfiguration:
    base = HighLiftConfiguration(config_id="takeoff", devices=_base_devices())
    return base.with_schedule_config("takeoff", deflection_schedule())


def landing_configuration() -> HighLiftConfiguration:
    base = HighLiftConfiguration(config_id="landing", devices=_base_devices())
    return base.with_schedule_config("landing", deflection_schedule())


def small_wing_planform() -> WingPlanform:
    return WingPlanform(aspect_ratio=7.0, oswald_efficiency=0.85, area_m2=2.0)


__all__ = [
    "MODEL_FIXTURES",
    "canonical_flap",
    "canonical_slat",
    "clean_configuration",
    "deflection_schedule",
    "landing_configuration",
    "simple_airfoil_section",
    "small_wing_planform",
    "takeoff_configuration",
]
