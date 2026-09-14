"""Example-level EDF geometry: thin compositions of generic M1 CAD ops.

The duct system itself is built by the generic
``build_duct_system(n_rotating=...)`` facility; stage count and diameters are
example choices. This module only maps EDF configuration onto generic
parameters, reads back generic design variables, and exports artifacts
through the generic OCC pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aeroworkbench_geometry import build_duct_system
from aeroworkbench_geometry.builder import live_shapes
from aeroworkbench_geometry.parametric import BuiltModel, export_artifacts
from aeroworkbench_optimization.drivers import DesignVariable
from edf_config import EDF80Config


@dataclass(frozen=True, slots=True)
class EdfGeometry:
    """Generic build result projected onto example naming."""

    config_name: str
    n_rotating: int
    rotating_zones: tuple[str, ...]
    stationary_zones: tuple[str, ...]
    parameter_hash: str
    shape_hash: str
    kernel_available: bool
    component_volumes_mm3: tuple[tuple[str, float], ...]
    operation_count: int


def build_edf_geometry(config: EDF80Config) -> EdfGeometry:
    """Build the EDF flow-path geometry with generic CAD operations only."""

    model = build_duct_system(
        outer_diameter_mm=config.outer_diameter_mm,
        inner_diameter_mm=config.inner_diameter_mm,
        length_mm=config.length_mm,
        hub_diameter_mm=config.hub_diameter_mm,
        n_rotating=config.n_stages,
        n_solids=2,
        zone_length_mm=config.zone_length_mm,
        zone_gap_mm=config.axial_gap_mm,
    )
    built: BuiltModel = model.build()
    stationary = ["duct", "fluid_inlet", "fluid_outlet"]
    stationary.extend(f"stator_zone_{index}" for index in range(config.n_stages - 1))
    return EdfGeometry(
        config_name=config.name,
        n_rotating=config.n_stages,
        rotating_zones=config.rotor_names,
        stationary_zones=tuple(stationary),
        parameter_hash=built.parameter_hash,
        shape_hash=built.shape_hash,
        kernel_available=built.kernel.available,
        component_volumes_mm3=tuple(
            (component.name, component.volume_mm3) for component in built.components
        ),
        operation_count=built.operation_count,
    )


def export_edf_step(config: EDF80Config, directory: Path, basename: str = "edf") -> dict[str, Any]:
    """Export STEP/BREP (+STL visualization) through the generic OCC pipeline."""

    model = build_duct_system(
        outer_diameter_mm=config.outer_diameter_mm,
        inner_diameter_mm=config.inner_diameter_mm,
        length_mm=config.length_mm,
        hub_diameter_mm=config.hub_diameter_mm,
        n_rotating=config.n_stages,
        n_solids=2,
        zone_length_mm=config.zone_length_mm,
        zone_gap_mm=config.axial_gap_mm,
    )
    built = model.build()
    return export_artifacts(
        live_shapes(built), built.kernel, directory, basename=basename, export_stl=True
    )


def design_variables(config: EDF80Config) -> tuple[DesignVariable, ...]:
    """Milestone geometry variables as generic optimizer declarations."""

    _ = config
    return (
        DesignVariable("hub_diameter_mm", "mm", "continuous", 20.0, 36.0),
        DesignVariable("blade_count", "dimensionless", "integer", 6.0, 12.0),
        DesignVariable("stator_count", "dimensionless", "integer", 7.0, 14.0),
        DesignVariable("chord_mm", "mm", "continuous", 10.0, 16.0),
        DesignVariable("twist_deg", "deg", "continuous", 15.0, 35.0),
        DesignVariable("thickness_mm", "mm", "continuous", 0.8, 2.0),
        DesignVariable("axial_gap_mm", "mm", "continuous", 5.0, 12.0),
        DesignVariable("tip_clearance_mm", "mm", "continuous", 0.3, 1.0),
        DesignVariable("inlet_radius_mm", "mm", "continuous", 3.0, 10.0),
        DesignVariable("nozzle_exit_mm", "mm", "continuous", 68.0, 78.0),
        DesignVariable("rpm", "rpm", "continuous", 28000.0, 45000.0),
    )


def motion_frames(config: EDF80Config, rpm: float) -> tuple[dict[str, object], ...]:
    """DesignRevision motion frames: one rotating frame per blade row."""

    omega_si = rpm * 2.0 * 3.141592653589793 / 60.0
    frames: list[dict[str, object]] = [
        {
            "name": name,
            "kind": "rotating",
            "axis": (0.0, 0.0, 1.0),
            "rateSI": omega_si,
        }
        for name in config.rotor_names
    ]
    frames.append({"name": "duct-frame", "kind": "stationary", "axis": (0.0, 0.0, 1.0)})
    return tuple(frames)


__all__ = [
    "EdfGeometry",
    "build_edf_geometry",
    "design_variables",
    "export_edf_step",
    "motion_frames",
]
