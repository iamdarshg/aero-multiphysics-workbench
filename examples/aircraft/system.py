"""Run the bounded analytical installed-EDF aircraft workflow."""

from aeroworkbench_core.envelope import AircraftDefinition
from aeroworkbench_envelope import (
    AircraftEnvelope,
    EnvelopeConstraints,
    evaluate_aircraft_envelope,
    sweep_conditions,
)

from .geometry import make_aircraft_geometry


def run_aircraft_demo() -> AircraftEnvelope:
    geometry = make_aircraft_geometry()
    conditions = sweep_conditions(
        airspeeds_m_s=(24.0, 35.0, 48.0),
        mach_numbers=(0.08, 0.14, 0.19),
        altitudes_m=(0.0,),
        density_kg_m3=(1.225,),
        temperature_k=(288.15,),
        load_factor=1.0,
        current_a=45.0,
        rpm=45_000.0,
        soc=0.8,
    )
    return evaluate_aircraft_envelope(
        AircraftDefinition(
            mass_kg=4.0,
            wing_area_m2=0.5,
            cd0=0.025,
            induced_drag_factor=0.055,
            available_thrust_n=45.0,
        ),
        EnvelopeConstraints(),
        conditions,
        geometry=geometry,
    )
