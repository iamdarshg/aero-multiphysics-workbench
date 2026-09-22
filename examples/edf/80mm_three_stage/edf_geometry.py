"""Example-level EDF geometry: thin compositions of generic M1 CAD ops.

The duct system itself is built by the generic
``build_duct_system(n_rotating=...)`` facility; stage count and diameters are
example choices. This module only maps EDF configuration onto generic
parameters, reads back generic design variables, and exports artifacts
through the generic OCC pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import radians, tan
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
    """Build the EDF flow path with real patterned rotor/stator solids.

    The generic duct builder supplies the zones.  This example adds the
    domain-specific blade rows and subtracts them from their fluid slices,
    leaving the generic solver and mesh contracts unchanged.
    """

    model = _edf_model(config)
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

    model = _edf_model(config)
    built = model.build()
    return export_artifacts(
        live_shapes(built), built.kernel, directory, basename=basename, export_stl=True
    )


def _edf_model(config: EDF80Config):
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
    half_length = config.length_mm / 2.0
    rotor_span = config.n_stages * config.zone_length_mm + (config.n_stages - 1) * config.axial_gap_mm
    cursor = -rotor_span / 2.0
    hub_radius = config.hub_diameter_mm / 2.0
    tip_radius = config.inner_diameter_mm / 2.0 - config.tip_clearance_mm

    for index, blade_count in enumerate(config.blade_counts):
        center = cursor + config.zone_length_mm / 2.0
        _add_row(model, f"rotor_{index}", blade_count, hub_radius, tip_radius, center, config)
        cursor += config.zone_length_mm
        if index < len(config.stator_counts):
            stator_center = cursor + config.axial_gap_mm / 2.0
            _add_row(
                model,
                f"stator_{index}",
                config.stator_counts[index],
                hub_radius,
                tip_radius,
                stator_center,
                config,
            )
            cursor += config.axial_gap_mm
    if cursor >= half_length:
        raise ValueError("EDF_ROW_SPAN_EXCEEDS_DUCT")
    return model


def _add_row(model, row_id: str, count: int, hub_radius: float, tip_radius: float, center: float, config: EDF80Config) -> None:
    span = tip_radius - hub_radius
    twist_offset = tan(radians(config.twist_deg)) * span * 0.2
    half_chord = config.chord_mm / 2.0
    profile = (
        (hub_radius, -half_chord),
        (tip_radius, -half_chord + twist_offset),
        (tip_radius, half_chord + twist_offset),
        (hub_radius, half_chord),
    )
    source = f"_{row_id}_blade_source"
    pattern = f"{row_id}_blades"
    zone = f"rotor_zone_{row_id.split('_')[-1]}" if row_id.startswith("rotor") else f"stator_zone_{row_id.split('_')[-1]}"
    model.extrude_profile(source, profile, config.thickness_mm, offset_mm=(0.0, 0.0, center - config.thickness_mm / 2.0))
    model.circular_pattern(pattern, source, count)
    model.boolean(zone, "cut", zone, pattern)


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
