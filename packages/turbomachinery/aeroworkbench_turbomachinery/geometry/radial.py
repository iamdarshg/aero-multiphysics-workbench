"""Radial and mixed-flow turbomachinery geometry.

Generic contracts for impeller/rotor blades, hub/shroud meridional contours,
vaned and vaneless diffusers, return/guide channels, and a declarative volute
interface. The same section contract used by the axial row is placed on a
meridional contour, so radial and mixed-flow blades are real lofts rather than
a separate framework.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from math import atan2, cos, isfinite, pi, sin, sqrt
from typing import Any

from aeroworkbench_geometry import ParameterDef, SemanticBinding

from ..rows import BladeRow
from .blade_rows import _cap_patch, _segment_patch, scaled_sections
from .body import GeometryBody, SurfacePatch
from .fluid import FluidDomain, build_annular_passage
from .robustness import GeometryDiagnostic, check_manifold, check_required_roles
from .sections import (
    DEFAULT_EDGE_POINTS,
    DEFAULT_SURFACE_POINTS,
    BladeSection,
    place_section,
    section_loop_indices,
    section_parameters,
)

_SPLITTER_CHORD_FRACTION = 0.62
_MERIDIONAL_STATIONS = 7
_RADIAL_THETA_POINTS = 9


def _lerp(a: float, b: float, fraction: float) -> float:
    return a + (b - a) * fraction


@dataclass(frozen=True, slots=True)
class MeridionalContour:
    """A monotone meridional ``(z_mm, r_mm)`` contour with arc-length sampling."""

    name: str
    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("MERIDIONAL_CONTOUR_NAME_REQUIRED")
        if len(self.points) < 2:
            raise ValueError("MERIDIONAL_CONTOUR_NEEDS_TWO_POINTS")
        for index, (z, r) in enumerate(self.points):
            if not isfinite(z) or not isfinite(r) or r <= 0.0:
                raise ValueError(f"MERIDIONAL_POINT_INVALID:{index}")
            if index and abs(z - self.points[index - 1][0]) < 1e-12 and abs(
                r - self.points[index - 1][1]
            ) < 1e-12:
                raise ValueError(f"MERIDIONAL_DUPLICATE_POINT:{index}")

    def _cumulative(self) -> tuple[float, ...]:
        lengths = [0.0]
        for (z0, r0), (z1, r1) in zip(self.points, self.points[1:], strict=False):
            lengths.append(lengths[-1] + sqrt((z1 - z0) ** 2 + (r1 - r0) ** 2))
        return tuple(lengths)

    def sample(self, count: int) -> tuple[tuple[float, float], ...]:
        if count < 2:
            raise ValueError("MERIDIONAL_SAMPLE_NEEDS_TWO_STATIONS")
        lengths = self._cumulative()
        total = lengths[-1]
        if total <= 1e-12:
            raise ValueError("MERIDIONAL_CONTOUR_DEGENERATE")
        result: list[tuple[float, float]] = []
        for index in range(count):
            target = total * index / (count - 1)
            segment = 0
            while segment < len(lengths) - 1 and lengths[segment + 1] < target:
                segment += 1
            segment_length = lengths[segment + 1] - lengths[segment]
            local = (
                0.0 if segment_length <= 1e-12 else (target - lengths[segment]) / segment_length
            )
            z0, r0 = self.points[segment]
            z1, r1 = self.points[segment + 1]
            result.append((_lerp(z0, z1, local), _lerp(r0, r1, local)))
        return tuple(result)

    def canonical(self) -> dict[str, Any]:
        return {"name": self.name, "points": [[z, r] for z, r in self.points]}

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _mean_meridional_angle(
    hub_sample: tuple[tuple[float, float], ...],
    shroud_sample: tuple[tuple[float, float], ...],
    station: int,
) -> float:
    def midpoint(index: int) -> tuple[float, float]:
        (zh, rh), (zs, rs) = hub_sample[index], shroud_sample[index]
        return (0.5 * (zh + zs), 0.5 * (rh + rs))

    last = len(hub_sample) - 1
    low = max(0, station - 1)
    high = min(last, station + 1)
    z0, r0 = midpoint(low)
    z1, r1 = midpoint(high)
    return atan2(r1 - r0, z1 - z0)


@dataclass(frozen=True, slots=True)
class RadialBladeRow:
    """Radial or mixed-flow blade/impeller row on hub/shroud meridional contours."""

    row_id: str
    frame: str
    family: str
    blade_count: int
    sections: tuple[BladeSection, ...]
    hub_contour: MeridionalContour
    shroud_contour: MeridionalContour
    splitter_count: int = 0
    splitter_chord_fraction: float = _SPLITTER_CHORD_FRACTION
    shroud_state: str | None = None
    tip_clearance_mm: float = 0.3
    architecture_id: str | None = None
    material_ref: str | None = None
    thermal_ref: str | None = None
    n_surface: int = DEFAULT_SURFACE_POINTS
    n_edge: int = DEFAULT_EDGE_POINTS
    n_stations: int = _MERIDIONAL_STATIONS

    def __post_init__(self) -> None:
        if not self.row_id.strip():
            raise ValueError("RADIAL_ROW_ID_REQUIRED")
        if self.family not in ("radial", "mixed"):
            raise ValueError(f"RADIAL_ROW_FAMILY_INVALID:{self.family}")
        if self.frame not in ("rotating", "stationary"):
            raise ValueError(f"RADIAL_ROW_FRAME_INVALID:{self.frame}")
        if self.blade_count < 1:
            raise ValueError("RADIAL_BLADE_COUNT_MUST_BE_POSITIVE")
        if self.splitter_count < 0:
            raise ValueError("SPLITTER_COUNT_MUST_NOT_BE_NEGATIVE")
        if len(self.sections) < 2:
            raise ValueError("RADIAL_ROW_NEEDS_TWO_SECTIONS")
        if not 0.0 < self.splitter_chord_fraction <= 1.0:
            raise ValueError("SPLITTER_CHORD_FRACTION_OUT_OF_RANGE")
        if self.n_stations < 3:
            raise ValueError("RADIAL_ROW_NEEDS_MERIDIONAL_STATIONS")

    def hub_sample(self) -> tuple[tuple[float, float], ...]:
        return self.hub_contour.sample(self.n_stations)

    def shroud_sample(self) -> tuple[tuple[float, float], ...]:
        return self.shroud_contour.sample(self.n_stations)

    def _station_radius(self, span: float, station: int) -> tuple[float, float]:
        (zh, rh), (zs, rs) = self.hub_sample()[station], self.shroud_sample()[station]
        return (_lerp(zh, zs, span), _lerp(rh, rs, span))

    def section_loop(
        self, section: BladeSection, theta: float, station: int, chord_fraction: float
    ) -> tuple[tuple[float, float, float], ...]:
        z, radius = self._station_radius(section.span, station)
        meridional = _mean_meridional_angle(
            self.hub_sample(), self.shroud_sample(), station
        )
        center = (radius * cos(theta), radius * sin(theta), z)
        scaled = section
        if chord_fraction != 1.0:
            scaled = replace(section, chord_mm=section.chord_mm * chord_fraction)
        return place_section(
            scaled,
            center=center,
            theta_rad=theta,
            meridional_angle_rad=meridional,
            n_surface=self.n_surface,
            n_edge=self.n_edge,
        )

    def blade_body(self, blade_index: int, *, splitter: bool = False) -> GeometryBody:
        station = self.n_stations // 2
        fraction = self.splitter_chord_fraction if splitter else 1.0
        sector = 2.0 * pi / self.blade_count
        offset = 0.5 * sector if splitter else 0.0
        self._sections_for(blade_index, splitter)  # validation of index range
        theta = sector * blade_index + offset
        loops = tuple(
            self.section_loop(section, theta, station, fraction)
            for section in self.sections
        )
        indices = section_loop_indices(n_surface=self.n_surface, n_edge=self.n_edge)
        suffix = "splitter" if splitter else "blade"
        prefix = f"{self.row_id}.{suffix}.{blade_index}"
        patches = (
            _segment_patch(
                f"{prefix}.pressure", "blade.pressure", "wall", loops, indices["pressure"]
            ),
            _segment_patch(
                f"{prefix}.suction", "blade.suction", "wall", loops, indices["suction"]
            ),
            _segment_patch(
                f"{prefix}.leading_edge",
                "blade.leading_edge",
                "wall",
                loops,
                indices["leading_edge"],
            ),
            _segment_patch(
                f"{prefix}.trailing_edge",
                "blade.trailing_edge",
                "wall",
                loops,
                indices["trailing_edge"],
            ),
            _cap_patch(f"{prefix}.tip", "blade.tip", "wall", loops[-1]),
            _cap_patch(f"{prefix}.root", "blade.root", "wall", loops[0]),
        )
        return GeometryBody(body_id=prefix, domain="solid", patches=patches)

    def _sections_for(self, blade_index: int, splitter: bool) -> None:
        count = self.splitter_count if splitter else self.blade_count
        if not 0 <= blade_index < count:
            raise ValueError(f"BLADE_INDEX_OUT_OF_RANGE:{blade_index}")

    def endwall_bodies(self) -> tuple[GeometryBody, ...]:
        sector = 2.0 * pi / self.blade_count
        hub = _contour_endwall(
            f"{self.row_id}.hub", "hub", self.hub_sample(), sector, n_theta=_RADIAL_THETA_POINTS
        )
        shroud = _contour_endwall(
            f"{self.row_id}.shroud",
            "shroud",
            self.shroud_sample(),
            sector,
            n_theta=_RADIAL_THETA_POINTS,
        )
        return (hub, shroud)

    def bodies(self) -> tuple[GeometryBody, ...]:
        blades = tuple(
            self.blade_body(index) for index in range(self.blade_count)
        )
        splitters = tuple(
            self.blade_body(index, splitter=True)
            for index in range(self.splitter_count)
        )
        return (*blades, *splitters, *self.endwall_bodies())

    def digest(self) -> str:
        encoded = json.dumps(
            {
                "rowId": self.row_id,
                "family": self.family,
                "bladeCount": self.blade_count,
                "splitterCount": self.splitter_count,
                "hub": self.hub_contour.digest(),
                "shroud": self.shroud_contour.digest(),
                "sections": [section.canonical() for section in self.sections],
                "bodies": [body.digest() for body in self.bodies()],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> tuple[GeometryDiagnostic, ...]:
        findings: list[GeometryDiagnostic] = []
        if self.shroud_state != "shrouded" and self.tip_clearance_mm <= 0.0:
            findings.append(
                GeometryDiagnostic("IMPOSSIBLE_CLEARANCE", "radial tip clearance must be positive")
            )
        for index in range(min(self.blade_count, 2)):
            body = self.blade_body(index)
            findings.extend(check_manifold(body))
            findings.extend(
                check_required_roles(
                    body,
                    required_roles=(
                        "blade.pressure",
                        "blade.suction",
                        "blade.leading_edge",
                        "blade.trailing_edge",
                        "blade.tip",
                        "blade.root",
                    ),
                )
            )
        return tuple(findings)

    def fluid_domain(self, *, n_theta: int = 9) -> FluidDomain:
        hub = self.hub_sample()
        shroud = self.shroud_sample()
        identifier = f"{self.row_id}.fluid"
        passage = build_annular_passage(
            passage_id=identifier,
            hub_points=hub,
            shroud_points=shroud,
            periodicity=self.blade_count,
            n_theta=n_theta,
            n_stations=len(hub),
        )
        blade_patches = tuple(
            patch
            for patch in self.blade_body(0).patches
            if patch.role.startswith("blade.")
        )
        body = GeometryBody(
            body_id=identifier,
            domain="fluid",
            patches=(*passage.patches, *blade_patches),
        )
        from aeroworkbench_mesh.domains import ZoneSpec

        motion = "rotating" if self.frame == "rotating" else "stationary"
        return FluidDomain(
            domain_id=identifier,
            body=body,
            zones=(
                ZoneSpec(
                    name=identifier,
                    motion=motion,  # type: ignore[arg-type]
                    domain="fluid",
                    components=(self.row_id,),
                ),
            ),
            periodicity=self.blade_count,
            rotating_zone=identifier if self.frame == "rotating" else None,
            required_roles=("inlet", "outlet", "hub", "shroud", "periodic_low", "periodic_high"),
        )

    def semantic_bindings(self) -> tuple[SemanticBinding, ...]:
        """Bind each row component to the shared geometry-regeneration contract."""

        keys = [f"{self.row_id}.blade.{index}" for index in range(self.blade_count)]
        keys.extend(
            f"{self.row_id}.splitter.{index}" for index in range(self.splitter_count)
        )
        keys.extend((f"{self.row_id}.hub", f"{self.row_id}.shroud"))
        return tuple(
            SemanticBinding(
                key,
                "solid_region" if "blade" in key or "splitter" in key else "wall",
                key,
                key,
            )
            for key in keys
        )

    def cad_parameter_defs(self) -> tuple[ParameterDef, ...]:
        defs: list[ParameterDef] = [
            ParameterDef(
                f"{self.row_id}.bladeCount",
                float(self.blade_count),
                unit="dimensionless",
            ),
            ParameterDef(
                f"{self.row_id}.splitterCount",
                float(self.splitter_count),
                unit="dimensionless",
            ),
            ParameterDef(f"{self.row_id}.tipClearance", self.tip_clearance_mm, unit="mm"),
        ]
        for index, section in enumerate(self.sections):
            defs.extend(section_parameters(section, f"{self.row_id}.section.{index}"))
        return tuple(defs)


def _contour_endwall(
    body_id: str,
    role: str,
    sample: tuple[tuple[float, float], ...],
    sector: float,
    *,
    n_theta: int,
) -> GeometryBody:
    stations = len(sample)
    points: list[tuple[float, float, float]] = []
    for z, r in sample:
        for theta_index in range(n_theta):
            theta = sector * theta_index / (n_theta - 1)
            points.append((r * cos(theta), r * sin(theta), z))
    patch = SurfacePatch(
        patch_id=f"{body_id}.surface",
        role=role,
        kind="wall",
        nu=n_theta,
        nv=stations,
        points=tuple(points),
    )
    return GeometryBody(body_id=body_id, domain="solid", patches=(patch,))


def build_radial_blade_row(
    row: BladeRow,
    *,
    hub_contour: MeridionalContour,
    shroud_contour: MeridionalContour,
    sections: tuple[BladeSection, ...],
    splitter_count: int = 0,
    tip_clearance_mm: float | None = None,
    architecture_id: str | None = None,
    n_surface: int = DEFAULT_SURFACE_POINTS,
    n_edge: int = DEFAULT_EDGE_POINTS,
    n_stations: int = _MERIDIONAL_STATIONS,
) -> RadialBladeRow:
    """Build a radial/mixed-flow row from a TURBO 01 :class:`BladeRow`."""

    clearance = tip_clearance_mm
    if clearance is None:
        quantity = row.clearance.tip_clearance
        clearance = 0.3 if quantity is None else quantity.value_si * 1000.0
    hub_sample = hub_contour.sample(n_stations)
    shroud_sample = shroud_contour.sample(n_stations)
    return RadialBladeRow(
        row_id=row.row_id,
        frame=row.frame,
        family=row.family,
        blade_count=row.periodicity * row.row_count,
        sections=scaled_radial_sections(
            sections, hub_sample=hub_sample, shroud_sample=shroud_sample
        ),
        hub_contour=hub_contour,
        shroud_contour=shroud_contour,
        splitter_count=splitter_count,
        shroud_state=row.clearance.shroud_state,
        tip_clearance_mm=clearance,
        architecture_id=architecture_id,
        material_ref=row.material_ref,
        thermal_ref=row.thermal_ref,
        n_surface=n_surface,
        n_edge=n_edge,
        n_stations=n_stations,
    )


def scaled_radial_sections(
    sections: tuple[BladeSection, ...],
    *,
    hub_sample: tuple[tuple[float, float], ...],
    shroud_sample: tuple[tuple[float, float], ...],
) -> tuple[BladeSection, ...]:
    station = len(hub_sample) // 2
    hub_radius = hub_sample[station][1]
    shroud_radius = shroud_sample[station][1]
    return scaled_sections(
        sections, hub_radius_mm=hub_radius, tip_radius_mm=shroud_radius
    )


def build_vaneless_diffuser(
    *,
    diffuser_id: str,
    hub_contour: MeridionalContour,
    shroud_contour: MeridionalContour,
    periodicity: int = 1,
    n_theta: int = 9,
    n_stations: int = 5,
) -> FluidDomain:
    """Generic vaneless diffuser passage (annular, no vanes)."""

    hub = hub_contour.sample(n_stations)
    shroud = shroud_contour.sample(n_stations)
    body = build_annular_passage(
        passage_id=diffuser_id,
        hub_points=hub,
        shroud_points=shroud,
        periodicity=periodicity,
        n_theta=n_theta,
        n_stations=n_stations,
    )
    from aeroworkbench_mesh.domains import ZoneSpec

    return FluidDomain(
        domain_id=diffuser_id,
        body=body,
        zones=(
            ZoneSpec(
                name=diffuser_id,
                motion="stationary",
                domain="fluid",
                components=(diffuser_id,),
            ),
        ),
        periodicity=periodicity,
        required_roles=("inlet", "outlet", "hub", "shroud", "periodic_low", "periodic_high"),
    )


def build_return_channel(
    *,
    channel_id: str,
    hub_contour: MeridionalContour,
    shroud_contour: MeridionalContour,
    periodicity: int = 1,
    n_theta: int = 9,
    n_stations: int = 6,
) -> FluidDomain:
    """Generic return/guide channel passage (turning annular duct)."""

    return build_vaneless_diffuser(
        diffuser_id=channel_id,
        hub_contour=hub_contour,
        shroud_contour=shroud_contour,
        periodicity=periodicity,
        n_theta=n_theta,
        n_stations=n_stations,
    )


@dataclass(frozen=True, slots=True)
class VoluteInterface:
    """Declarative volute/collector interface contract (no solid authored here)."""

    interface_id: str
    inlet_radius_mm: float
    inlet_width_mm: float
    outlet_diameter_mm: float | None = None
    tongue_angle_deg: float | None = None

    def __post_init__(self) -> None:
        if not self.interface_id.strip():
            raise ValueError("VOLUTE_INTERFACE_ID_REQUIRED")
        for label, value in (
            ("inletRadius", self.inlet_radius_mm),
            ("inletWidth", self.inlet_width_mm),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"VOLUTE_{label.upper()}_MUST_BE_POSITIVE")
        if self.outlet_diameter_mm is not None and self.outlet_diameter_mm <= 0.0:
            raise ValueError("VOLUTE_OUTLET_DIAMETER_MUST_BE_POSITIVE")

    def canonical(self) -> dict[str, Any]:
        return {
            "interfaceId": self.interface_id,
            "inletRadiusMm": self.inlet_radius_mm,
            "inletWidthMm": self.inlet_width_mm,
            "outletDiameterMm": self.outlet_diameter_mm,
            "tongueAngleDeg": self.tongue_angle_deg,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def parameter_defs(self) -> tuple[ParameterDef, ...]:
        return (
            ParameterDef(f"{self.interface_id}.inletRadius", self.inlet_radius_mm, unit="mm"),
            ParameterDef(f"{self.interface_id}.inletWidth", self.inlet_width_mm, unit="mm"),
        )
