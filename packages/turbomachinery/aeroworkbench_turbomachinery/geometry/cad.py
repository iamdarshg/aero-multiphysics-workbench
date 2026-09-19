"""CadQuery/OpenCascade bridge for the turbomachinery geometry contracts.

The canonical structured-surface model is kernel-independent; this module turns
it into real BREP solids through the shared CAD capability probe. When the
kernel is unavailable every entry point fails closed instead of returning a
placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from aeroworkbench_geometry import (
    KernelIdentity,
    export_artifacts,
    probe_kernel,
    require_kernel,
)

from .blade_rows import BladeRowGeometry
from .body import Point
from .radial import RadialBladeRow


@dataclass(frozen=True, slots=True)
class CadSolidReceipt:
    """Measured identity of one native BREP solid."""

    name: str
    face_count: int
    volume_mm3: float
    valid: bool
    bounds_mm: tuple[float, float, float, float, float, float]

    def canonical(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "faceCount": self.face_count,
            "volumeMm3": self.volume_mm3,
            "valid": self.valid,
            "boundsMm": list(self.bounds_mm),
        }


def probe_cad() -> KernelIdentity:
    """Report the shared CAD kernel identity without constructing geometry."""

    return probe_kernel()


def _wire(loop: tuple[Point, ...], cq: Any) -> Any:
    if len(loop) < 3:
        raise ValueError("BLADE_LOOP_NEEDS_THREE_POINTS")
    vectors = [cq.Vector(point[0], point[1], point[2]) for point in loop]
    return cq.Wire.makePolygon(vectors, close=True)


def _loft(loops: tuple[tuple[Point, ...], ...], cq: Any) -> Any:
    if len(loops) < 2:
        raise ValueError("LOFT_NEEDS_TWO_SECTIONS")
    wires = [_wire(loop, cq) for loop in loops]
    try:
        return cq.Solid.makeLoft(wires, ruled=True)
    except Exception as exc:  # noqa: BLE001 - kernel loft failure fails closed
        raise ValueError(f"CAD_LOFT_FAILED:{type(exc).__name__}:{exc}") from exc


def _sector_wedge(
    radius_mm: float,
    angle_deg: float,
    z_start_mm: float,
    z_end_mm: float,
    cq: Any,
) -> Any:
    from math import cos, pi, sin

    segments = max(2, int(abs(angle_deg) / 15.0) + 1)
    span = angle_deg * pi / 180.0
    profile: list[tuple[float, float]] = [(0.0, 0.0)]
    for index in range(segments + 1):
        theta = span * index / segments
        profile.append((radius_mm * cos(theta), radius_mm * sin(theta)))
    profile.append((0.0, 0.0))
    return (
        cq.Workplane("XY")
        .workplane(offset=z_start_mm)
        .polyline(profile)
        .close()
        .extrude(z_end_mm - z_start_mm)
        .val()
    )


def annular_revolve(
    *,
    radius_inner_mm: float,
    radius_outer_mm: float,
    z_start_mm: float,
    z_end_mm: float,
    angle_deg: float = 360.0,
) -> Any:
    """Revolve an annular axial profile about the Z axis into a real solid."""

    if radius_inner_mm <= 0.0 or radius_outer_mm <= radius_inner_mm:
        raise ValueError("ANNULAR_REVOLVE_RADII_INVALID")
    if z_end_mm <= z_start_mm:
        raise ValueError("ANNULAR_REVOLVE_AXIAL_ORDER_INVALID")
    if not 0.0 < angle_deg <= 360.0:
        raise ValueError("ANNULAR_REVOLVE_ANGLE_INVALID")
    cq = require_kernel()
    full = (
        cq.Workplane("XY")
        .workplane(offset=z_start_mm)
        .circle(radius_outer_mm)
        .circle(radius_inner_mm)
        .extrude(z_end_mm - z_start_mm)
        .val()
    )
    if angle_deg >= 360.0 - 1e-9:
        return full
    wedge = _sector_wedge(radius_outer_mm * 1.5, angle_deg, z_start_mm, z_end_mm, cq)
    return cq.Workplane(obj=full).intersect(cq.Workplane(obj=wedge)).val()


def blade_shape(geometry: BladeRowGeometry, blade_index: int) -> Any:
    cq = require_kernel()
    loops = tuple(
        geometry.blade_loop(blade_index, section) for section in geometry.sections
    )
    return _loft(loops, cq)


def radial_blade_shape(
    row: RadialBladeRow, blade_index: int, *, splitter: bool = False
) -> Any:
    cq = require_kernel()
    station = row.n_stations // 2
    fraction = row.splitter_chord_fraction if splitter else 1.0
    angle = (2.0 * 3.141592653589793 / row.blade_count) * blade_index
    if splitter:
        angle += 0.5 * (2.0 * 3.141592653589793 / row.blade_count)
    loops = tuple(
        row.section_loop(section, angle, station, fraction)
        for section in row.sections
    )
    return _loft(loops, cq)


def row_shapes(geometry: BladeRowGeometry) -> dict[str, Any]:
    shapes: dict[str, Any] = {}
    for index in range(geometry.blade_count):
        shapes[f"{geometry.row_id}.blade.{index}"] = blade_shape(geometry, index)
    z0 = geometry.axial_location_mm - geometry.axial_half_width_mm
    z1 = geometry.axial_location_mm + geometry.axial_half_width_mm
    shapes[f"{geometry.row_id}.hub"] = annular_revolve(
        radius_inner_mm=0.5 * geometry.hub_radius_mm,
        radius_outer_mm=geometry.hub_radius_mm,
        z_start_mm=z0,
        z_end_mm=z1,
    )
    shapes[f"{geometry.row_id}.shroud"] = annular_revolve(
        radius_inner_mm=geometry.shroud_radius_mm,
        radius_outer_mm=geometry.shroud_radius_mm * 1.1,
        z_start_mm=z0,
        z_end_mm=z1,
    )
    if geometry.tip_radius_mm <= geometry.hub_radius_mm:
        raise ValueError("BLADE_SPAN_EMPTY")
    return shapes


def fluid_sector_shape(geometry: BladeRowGeometry, *, offset_mm: float = 0.0) -> Any:
    """Sector fluid volume: annular passage minus all blade solids."""

    cq = require_kernel()
    z0 = geometry.axial_location_mm - geometry.axial_half_width_mm
    z1 = geometry.axial_location_mm + geometry.axial_half_width_mm
    angle = 360.0 / geometry.blade_count
    sector = annular_revolve(
        radius_inner_mm=max(geometry.hub_radius_mm - offset_mm, 1e-6),
        radius_outer_mm=geometry.shroud_radius_mm,
        z_start_mm=z0,
        z_end_mm=z1,
        angle_deg=angle,
    )
    result = sector
    for index in range(geometry.blade_count):
        blade = blade_shape(geometry, index)
        result = cq.Workplane(obj=result).cut(cq.Workplane(obj=blade)).val()
    return result


def radial_fluid_sector_shape(row: RadialBladeRow) -> Any:
    """Sector fluid volume for a radial/mixed-flow row (hub-shroud annulus minus blades)."""

    cq = require_kernel()
    hub = row.hub_sample()
    shroud = row.shroud_sample()
    profile: list[tuple[float, float]] = []
    for z, r in hub:
        profile.append((r, z))
    for z, r in reversed(shroud):
        profile.append((r, z))
    angle = 360.0 / row.blade_count
    result = (
        cq.Workplane("XZ")
        .polyline(profile)
        .close()
        .revolve(angle, (0, 0, 0), (0, 1, 0))
        .val()
    )
    for index in range(row.blade_count):
        blade = radial_blade_shape(row, index)
        result = cq.Workplane(obj=result).cut(cq.Workplane(obj=blade)).val()
    return result


def solid_receipt(name: str, shape: Any) -> CadSolidReceipt:
    try:
        valid = bool(shape.isValid())
    except Exception:  # noqa: BLE001 - validity probe unavailable
        valid = False
    try:
        volume = float(shape.Volume())
    except Exception:  # noqa: BLE001 - volume probe unavailable
        volume = 0.0
    try:
        box = shape.BoundingBox()
        bounds = (
            float(box.xmin),
            float(box.ymin),
            float(box.zmin),
            float(box.xmax),
            float(box.ymax),
            float(box.zmax),
        )
    except Exception:  # noqa: BLE001 - bounds probe unavailable
        bounds = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if not all(isfinite(value) for value in bounds):
        bounds = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    try:
        faces = int(len(shape.Faces()))
    except Exception:  # noqa: BLE001 - topology probe unavailable
        faces = 0
    return CadSolidReceipt(
        name=name, face_count=faces, volume_mm3=volume, valid=valid, bounds_mm=bounds
    )


def export_shapes(
    shapes: dict[str, Any],
    directory: Path,
    *,
    basename: str,
    kernel: KernelIdentity | None = None,
) -> dict[str, Any]:
    """Export native STEP/BREP artifacts through the shared exporter."""

    identity = kernel or probe_kernel()
    if not identity.available:
        raise RuntimeError("CAD_KERNEL_UNAVAILABLE")
    return export_artifacts(
        shapes, identity, directory, basename=basename, export_stl=False
    )


__all__ = [
    "CadSolidReceipt",
    "annular_revolve",
    "blade_shape",
    "export_shapes",
    "fluid_sector_shape",
    "probe_cad",
    "radial_blade_shape",
    "radial_fluid_sector_shape",
    "row_shapes",
    "solid_receipt",
]
