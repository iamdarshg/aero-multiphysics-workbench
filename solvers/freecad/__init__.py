"""FreeCAD capability boundary and headless interchange."""

from .adapter import (
    ConversionReceipt,
    FreeCADReceipt,
    RoundtripReceipt,
    convert_cad,
    convert_with_freecad,
    convert_with_ocp,
    export_fcstd,
    inspect_freecad,
    read_fcstd,
    step_roundtrip,
)

__all__ = [
    "FreeCADReceipt",
    "ConversionReceipt",
    "RoundtripReceipt",
    "inspect_freecad",
    "convert_cad",
    "convert_with_freecad",
    "convert_with_ocp",
    "export_fcstd",
    "read_fcstd",
    "step_roundtrip",
]
