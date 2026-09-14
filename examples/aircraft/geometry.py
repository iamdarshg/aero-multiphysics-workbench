"""Canonical aircraft surfaces used by the analytical demonstration."""

from aeroworkbench_geometry import GeometryModel, Surface


def make_aircraft_geometry() -> GeometryModel:
    return GeometryModel(
        name="asterion-installed-edf",
        parameters_mm=(
            ("fuselageLength", 920.0),
            ("wingSpan", 1250.0),
            ("wingArea", 500_000.0),
            ("edfDiameter", 70.0),
            ("tailSpan", 360.0),
        ),
        surfaces=(
            Surface("fuselage", "solid-fuselage", "aircraft.fuselage"),
            Surface("wing-left", "lifting-surface", "aircraft.wing.left"),
            Surface("wing-right", "lifting-surface", "aircraft.wing.right"),
            Surface("tail", "control-surface", "aircraft.tail"),
            Surface("edf-inlet", "fluid-inlet", "edf.inlet"),
            Surface("edf-nozzle", "fluid-outlet", "edf.outlet"),
            Surface("external-domain", "farfield", "aircraft.external-domain"),
        ),
    )
