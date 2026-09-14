"""Canonical gas-turbine flowpath used by the analytical demonstration."""

from aeroworkbench_geometry import GeometryModel, Surface


def make_gas_turbine_geometry() -> GeometryModel:
    return GeometryModel(
        name="brayton-reference-spool",
        parameters_mm=(
            ("compressorLength", 180.0),
            ("combustorLength", 120.0),
            ("turbineLength", 160.0),
            ("nozzleDiameter", 90.0),
            ("shaftDiameter", 24.0),
        ),
        surfaces=(
            Surface("inlet", "fluid-inlet", "engine.inlet"),
            Surface("compressor", "rotor-interface", "engine.compressor"),
            Surface("combustor", "combustion-region", "engine.combustor"),
            Surface("turbine", "rotor-interface", "engine.turbine"),
            Surface("nozzle", "fluid-outlet", "engine.nozzle"),
            Surface("shaft", "solid-shaft", "engine.shaft"),
        ),
    )
