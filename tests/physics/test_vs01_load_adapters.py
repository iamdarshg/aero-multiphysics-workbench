"""Vehicle-system load handoffs into the existing structural sizing contract."""

from __future__ import annotations

import pytest
from aeroworkbench_core.types import Provenance, ResultSource
from aeroworkbench_propulsors import VehicleLoads
from aeroworkbench_vehicle_systems.landing_gear import (
    GearLoadCase,
    LoadCaseKind,
    export_load_cases,
    result_meta,
)
from aeroworkbench_vehicle_systems.mission import SegmentKind, SegmentMode, SegmentSpec
from aeroworkbench_vehicle_systems.structures import (
    LoadSource,
    ground_load_set_for_segment,
    load_case_from_landing_gear,
    load_case_from_propulsor,
)


def _gear_case(case_id: str, kind: LoadCaseKind) -> GearLoadCase:
    return GearLoadCase(
        case_id=case_id,
        kind=kind,
        gear_id="main-left",
        vertical_force_n=12_000.0,
        drag_force_n=2_500.0,
        side_force_n=-800.0,
        sink_rate_m_s=2.4 if kind is LoadCaseKind.TOUCHDOWN else None,
        meta=result_meta(
            model="test.gear-load",
            inputs={"caseId": case_id},
            valid=True,
        ),
    )


def _vehicle_loads() -> VehicleLoads:
    return VehicleLoads(
        thrust_n=900.0,
        normal_force_n=120.0,
        torque_n_m=44.0,
        pitching_moment_n_m=18.0,
        yawing_moment_n_m=-7.0,
        total_inflow_angle_deg=4.0,
        provenance=Provenance.from_inputs(
            source=ResultSource.ANALYTICAL,
            model="test.installed-loads",
            inputs={"fixture": "installed-propulsor"},
        ),
    )


def test_landing_gear_result_becomes_structural_load_case() -> None:
    case = load_case_from_landing_gear(
        _gear_case("touchdown", LoadCaseKind.TOUCHDOWN),
        component_id="wing-box",
        span_m=4.0,
        station_fraction=0.25,
        load_factor=1.5,
    )

    assert case.source is LoadSource.LANDING
    assert case.case_id == "landing:touchdown"
    assert case.normal_force_n() == pytest.approx(18_000.0)
    assert case.total_axial_n() == pytest.approx(3_750.0)
    assert case.total_shear_n() == pytest.approx(-1_200.0)
    assert case.root_bending_moment_n_m() == pytest.approx(18_000.0)
    assert "main-left" in case.reference


def test_propulsor_result_retains_forces_and_applied_moments() -> None:
    case = load_case_from_propulsor(
        _vehicle_loads(),
        component_id="rear-propulsor-mount",
        span_m=1.2,
        station_fraction=0.5,
        case_id="propulsion:max-thrust",
        load_factor=1.25,
    )

    assert case.source is LoadSource.PROPULSION
    assert case.normal_force_n() == pytest.approx(150.0)
    assert case.total_axial_n() == pytest.approx(1_125.0)
    assert case.applied_moments_n_m == pytest.approx((55.0, 22.5, -8.75))
    assert case.canonical_payload()["appliedMomentsNm"] == pytest.approx(
        [55.0, 22.5, -8.75]
    )


def test_mission_ground_bridge_selects_only_relevant_declared_cases() -> None:
    export = export_load_cases(
        "vehicle-1",
        (
            _gear_case("touchdown", LoadCaseKind.TOUCHDOWN),
            _gear_case("braking", LoadCaseKind.BRAKING),
            _gear_case("turning", LoadCaseKind.TURNING),
        ),
    )
    landing = SegmentSpec(
        segment_id="landing",
        kind=SegmentKind.LANDING,
        mode=SegmentMode.DURATION,
        speed_m_s=28.0,
        altitude_m=0.0,
        duration_s=15.0,
    )

    load_set = ground_load_set_for_segment(
        landing,
        export,
        component_id="fuselage-keel",
        span_m=5.0,
        station_fraction=0.2,
    )

    assert {case.case_id for case in load_set.load_cases} == {
        "landing:touchdown",
        "landing:braking",
        "landing:turning",
    }
    assert all(case.source is LoadSource.LANDING for case in load_set.load_cases)


def test_mission_ground_bridge_rejects_airborne_segment() -> None:
    export = export_load_cases(
        "vehicle-1", (_gear_case("touchdown", LoadCaseKind.TOUCHDOWN),)
    )
    cruise = SegmentSpec(
        segment_id="cruise",
        kind=SegmentKind.CRUISE,
        mode=SegmentMode.DURATION,
        speed_m_s=80.0,
        altitude_m=1_000.0,
        duration_s=30.0,
    )

    with pytest.raises(ValueError, match="GROUND_SEGMENT_REQUIRED"):
        ground_load_set_for_segment(
            cruise,
            export,
            component_id="fuselage-keel",
            span_m=5.0,
            station_fraction=0.2,
        )
