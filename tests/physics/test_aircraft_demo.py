from __future__ import annotations

import pytest
from aeroworkbench_core.envelope import AircraftDefinition
from aeroworkbench_envelope import (
    EnvelopeConstraints,
    FlightCondition,
    Region,
    evaluate_aircraft_envelope,
    sweep_conditions,
)
from examples.aircraft.system import run_aircraft_demo


def _aircraft() -> AircraftDefinition:
    return AircraftDefinition(
        mass_kg=4,
        wing_area_m2=0.5,
        cd0=0.025,
        induced_drag_factor=0.055,
        available_thrust_n=45,
    )


def _condition(speed: float, *, current: float = 35.0, mach: float = 0.12) -> FlightCondition:
    return FlightCondition(speed, mach, 0.0, 1.225, 288.15, current_a=current, rpm=45_000.0)


def test_installed_edf_geometry_and_envelope_are_explicitly_analytical() -> None:
    result = run_aircraft_demo()
    assert result.geometry_hash is not None
    assert result.points
    assert result.provenance.source.value == "analytical"
    assert any("native external CFD" in assumption for assumption in result.provenance.assumptions)


def test_region_classification_marks_viable_constrained_and_failed_points() -> None:
    aircraft = _aircraft()
    constraints = EnvelopeConstraints(max_current_a=60, max_load_factor=8)
    result = evaluate_aircraft_envelope(
        aircraft,
        constraints,
        (_condition(35), _condition(35, current=57), _condition(35, current=65)),
        refinement_depth=0,
    )
    regions = [point.region for point in result.points]
    assert Region.VIABLE in regions
    assert Region.CONSTRAINED in regions
    assert Region.FAILED in regions
    assert "current" in result.points[-1].violations


def test_adaptive_refinement_inserts_midpoint_at_region_boundary() -> None:
    aircraft = _aircraft()
    conditions = (_condition(20, current=35), _condition(80, current=75))
    result = evaluate_aircraft_envelope(
        aircraft, EnvelopeConstraints(max_current_a=60), conditions, refinement_depth=2
    )
    assert result.refinement.inserted_points >= 1
    assert len(result.points) > len(conditions)
    assert result.refinement.source_points == 2


def test_sweep_is_bounded_and_preserves_all_requested_axes() -> None:
    sweep = sweep_conditions(
        airspeeds_m_s=(20, 30),
        mach_numbers=(0.06, 0.1),
        altitudes_m=(0, 1000),
        density_kg_m3=(1.225,),
        temperature_k=(288.15,),
    )
    assert len(sweep) == 8
    with pytest.raises(ValueError, match="SWEEP_EXCEEDS_POINT_LIMIT"):
        sweep_conditions(
            airspeeds_m_s=tuple(20 + i for i in range(32)),
            mach_numbers=tuple(0.05 + 0.01 * i for i in range(17)),
            altitudes_m=(0,),
            density_kg_m3=(1.2,),
            temperature_k=(288,),
        )
