"""Axial blade/vane row geometry: lofted solids from spanwise sections.

A row references a TURBO 01 :class:`~aeroworkbench_turbomachinery.BladeRow` by
id, carries its own spanwise section stack, and owns real structured-surface
topology: pressure/suction/leading/trailing-edge patches plus tip and root caps,
hub and shroud endwalls, an optional shroud band, a root fillet intent, and an
explicit tip clearance. Circular-pattern count comes from the row periodicity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from math import cos, isfinite, pi, sin

from aeroworkbench_geometry import ParameterDef, SemanticBinding

from ..rows import BladeRow
from .body import GeometryBody, SurfacePatch
from .robustness import (
    GeometryDiagnostic,
    check_clearance,
    check_manifold,
    check_required_roles,
    check_stack,
)
from .sections import (
    DEFAULT_EDGE_POINTS,
    DEFAULT_SURFACE_POINTS,
    BladeSection,
    place_section,
    section_loop_indices,
    section_parameters,
)

_ENDWALL_THETA_POINTS = 24
_ENDWALL_AXIAL_POINTS = 3
_SHROUD_STATES: tuple[str, ...] = ("shrouded", "unshrouded")


def _segment_patch(
    patch_id: str,
    role: str,
    kind: str,
    loops: tuple[tuple[tuple[float, float, float], ...], ...],
    indices: tuple[int, ...],
) -> SurfacePatch:
    points: list[tuple[float, float, float]] = []
    for loop in loops:
        for index in indices:
            points.append(loop[index])
    return SurfacePatch(
        patch_id=patch_id,
        role=role,
        kind=kind,
        nu=len(indices),
        nv=len(loops),
        points=tuple(points),
    )


def _cap_patch(
    patch_id: str,
    role: str,
    kind: str,
    loop: tuple[tuple[float, float, float], ...],
) -> SurfacePatch:
    return SurfacePatch(
        patch_id=patch_id,
        role=role,
        kind=kind,
        nu=len(loop),
        nv=1,
        points=loop,
        closed_u=True,
    )


def _annulus_patch(
    patch_id: str,
    role: str,
    radius_mm: float,
    z_start_mm: float,
    z_end_mm: float,
    *,
    theta_start: float = 0.0,
    theta_end: float = 2.0 * pi,
    n_theta: int = _ENDWALL_THETA_POINTS,
    n_axial: int = _ENDWALL_AXIAL_POINTS,
    closed_theta: bool = True,
) -> SurfacePatch:
    points: list[tuple[float, float, float]] = []
    columns = n_theta
    for axial_index in range(n_axial):
        fraction = axial_index / (n_axial - 1)
        z = z_start_mm + (z_end_mm - z_start_mm) * fraction
        for theta_index in range(columns):
            theta_fraction = (
                theta_index / columns if closed_theta else theta_index / (columns - 1)
            )
            theta = theta_start + (theta_end - theta_start) * theta_fraction
            points.append((radius_mm * cos(theta), radius_mm * sin(theta), z))
    return SurfacePatch(
        patch_id=patch_id,
        role=role,
        kind="wall",
        nu=columns,
        nv=n_axial,
        points=tuple(points),
        closed_u=closed_theta,
    )


@dataclass(frozen=True, slots=True)
class BladeRowGeometry:
    """Real geometry for one or more identical axial blade rows."""

    row_id: str
    role: str
    frame: str
    family: str
    blade_count: int
    sections: tuple[BladeSection, ...]
    hub_radius_mm: float
    shroud_radius_mm: float
    tip_clearance_mm: float
    axial_location_mm: float
    axial_half_width_mm: float
    architecture_id: str | None = None
    shroud_state: str | None = None
    root_fillet_mm: float = 0.5
    material_ref: str | None = None
    thermal_ref: str | None = None
    n_surface: int = DEFAULT_SURFACE_POINTS
    n_edge: int = DEFAULT_EDGE_POINTS

    def __post_init__(self) -> None:
        if not self.row_id.strip():
            raise ValueError("ROW_ID_REQUIRED")
        if self.family not in ("axial", "radial", "mixed"):
            raise ValueError(f"UNKNOWN_ROW_FAMILY:{self.family}")
        if self.frame not in ("rotating", "stationary"):
            raise ValueError(f"UNKNOWN_ROW_FRAME:{self.frame}")
        if self.blade_count < 1:
            raise ValueError("BLADE_COUNT_MUST_BE_POSITIVE")
        if len(self.sections) < 2:
            raise ValueError("ROW_NEEDS_TWO_SECTIONS")
        for label, value in (
            ("hubRadius", self.hub_radius_mm),
            ("shroudRadius", self.shroud_radius_mm),
            ("tipClearance", self.tip_clearance_mm),
            ("axialHalfWidth", self.axial_half_width_mm),
            ("rootFillet", self.root_fillet_mm),
        ):
            if not isfinite(value):
                raise ValueError(f"ROW_{label.upper()}_NOT_FINITE")
        if self.hub_radius_mm <= 0.0 or self.shroud_radius_mm <= self.hub_radius_mm:
            raise ValueError("ROW_RADII_INVALID")
        if self.axial_half_width_mm <= 0.0:
            raise ValueError("ROW_AXIAL_HALF_WIDTH_MUST_BE_POSITIVE")
        if self.shroud_state is not None and self.shroud_state not in _SHROUD_STATES:
            raise ValueError(f"UNKNOWN_SHROUD_STATE:{self.shroud_state}")
        if self.n_surface < 3 or self.n_edge < 2:
            raise ValueError("ROW_SECTION_RESOLUTION_TOO_LOW")

    @property
    def tip_radius_mm(self) -> float:
        if self.shroud_state == "shrouded":
            return self.shroud_radius_mm
        return self.shroud_radius_mm - self.tip_clearance_mm

    @property
    def sector_angle_rad(self) -> float:
        return 2.0 * pi / self.blade_count

    @property
    def blade_pitch_rad(self) -> float:
        return self.sector_angle_rad

    def blade_angle(self, blade_index: int) -> float:
        if not 0 <= blade_index < self.blade_count:
            raise ValueError(f"BLADE_INDEX_OUT_OF_RANGE:{blade_index}")
        return self.sector_angle_rad * blade_index

    def blade_loop(
        self, blade_index: int, section: BladeSection
    ) -> tuple[tuple[float, float, float], ...]:
        theta = self.blade_angle(blade_index)
        center = (
            section.radius_mm * cos(theta),
            section.radius_mm * sin(theta),
            self.axial_location_mm,
        )
        return place_section(
            section,
            center=center,
            theta_rad=theta,
            meridional_angle_rad=0.0,
            n_surface=self.n_surface,
            n_edge=self.n_edge,
        )

    def blade_body(self, blade_index: int) -> GeometryBody:
        loops = tuple(
            self.blade_loop(blade_index, section) for section in self.sections
        )
        indices = section_loop_indices(n_surface=self.n_surface, n_edge=self.n_edge)
        prefix = f"{self.row_id}.blade.{blade_index}"
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

    def endwall_bodies(self) -> tuple[GeometryBody, ...]:
        z0 = self.axial_location_mm - self.axial_half_width_mm
        z1 = self.axial_location_mm + self.axial_half_width_mm
        hub = GeometryBody(
            body_id=f"{self.row_id}.hub",
            domain="solid",
            patches=(
                _annulus_patch(f"{self.row_id}.hub.surface", "hub", self.hub_radius_mm, z0, z1),
            ),
        )
        shroud = GeometryBody(
            body_id=f"{self.row_id}.shroud",
            domain="solid",
            patches=(
                _annulus_patch(
                    f"{self.row_id}.shroud.surface", "shroud", self.shroud_radius_mm, z0, z1
                ),
            ),
        )
        bodies = [hub, shroud]
        if self.shroud_state == "shrouded":
            band = GeometryBody(
                body_id=f"{self.row_id}.shroud_band",
                domain="solid",
                patches=(
                    _annulus_patch(
                        f"{self.row_id}.shroud_band.surface",
                        "shroud_band",
                        self.tip_radius_mm,
                        z0,
                        z1,
                    ),
                ),
            )
            bodies.append(band)
        return tuple(bodies)

    def row_bodies(self) -> tuple[GeometryBody, ...]:
        return tuple(
            self.blade_body(index) for index in range(self.blade_count)
        ) + self.endwall_bodies()

    def row_body(self) -> GeometryBody:
        """Single merged body so blade/row count changes are receipt-visible."""

        patches = tuple(
            patch for body in self.row_bodies() for patch in body.patches
        )
        return GeometryBody(
            body_id=f"{self.row_id}.row", domain="solid", patches=patches
        )

    def row_digest(self) -> str:
        encoded = json.dumps(
            {
                "rowId": self.row_id,
                "bodies": [
                    {
                        "bodyId": body.body_id,
                        "digest": body.digest(),
                        "signature": body.topology_signature(),
                    }
                    for body in self.row_bodies()
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def semantic_keys(self) -> tuple[str, ...]:
        keys = [f"{self.row_id}.blade.{index}" for index in range(self.blade_count)]
        keys.extend((f"{self.row_id}.hub", f"{self.row_id}.shroud"))
        return tuple(keys)

    def semantic_bindings(self) -> tuple[SemanticBinding, ...]:
        """Bind each row component to the shared geometry-regeneration contract."""

        bindings: list[SemanticBinding] = [
            SemanticBinding(
                f"{self.row_id}.blade.{index}",
                "solid_region",
                f"{self.row_id}.blade.{index}",
                f"{self.row_id}.blade.{index}",
            )
            for index in range(self.blade_count)
        ]
        bindings.extend(
            SemanticBinding(f"{self.row_id}.{role}", "wall", f"{self.row_id}.{role}",
                            f"{self.row_id}.{role}")
            for role in ("hub", "shroud")
        )
        return tuple(bindings)

    def validate(self) -> tuple[GeometryDiagnostic, ...]:
        findings = [
            *check_stack(
                self.sections, n_surface=self.n_surface, n_edge=self.n_edge
            ),
            *check_clearance(
                hub_radius_mm=self.hub_radius_mm,
                tip_radius_mm=self.tip_radius_mm,
                shroud_radius_mm=self.shroud_radius_mm,
                tip_clearance_mm=self.tip_clearance_mm,
                shroud_state=self.shroud_state,
            ),
        ]
        for blade_index in (0, self.blade_count - 1):
            body = self.blade_body(blade_index)
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

    def cad_parameter_defs(self) -> tuple[ParameterDef, ...]:
        defs: list[ParameterDef] = [
            ParameterDef(
                f"{self.row_id}.bladeCount",
                float(self.blade_count),
                unit="dimensionless",
            ),
            ParameterDef(f"{self.row_id}.hubRadius", self.hub_radius_mm, unit="mm"),
            ParameterDef(f"{self.row_id}.shroudRadius", self.shroud_radius_mm, unit="mm"),
            ParameterDef(f"{self.row_id}.tipClearance", self.tip_clearance_mm, unit="mm"),
            ParameterDef(f"{self.row_id}.rootFillet", self.root_fillet_mm, unit="mm"),
        ]
        for index, section in enumerate(self.sections):
            defs.extend(section_parameters(section, f"{self.row_id}.section.{index}"))
        return tuple(defs)


def scaled_sections(
    sections: tuple[BladeSection, ...],
    *,
    hub_radius_mm: float,
    tip_radius_mm: float,
) -> tuple[BladeSection, ...]:
    span = tip_radius_mm - hub_radius_mm
    if span <= 0.0:
        raise ValueError("IMPOSSIBLE_BLADE_SPAN")
    return tuple(
        replace(section, radius_mm=hub_radius_mm + section.span * span)
        for section in sections
    )


def build_axial_blade_row(
    row: BladeRow,
    *,
    hub_radius_mm: float,
    shroud_radius_mm: float,
    sections: tuple[BladeSection, ...],
    tip_clearance_mm: float | None = None,
    axial_location_mm: float = 0.0,
    axial_half_width_mm: float | None = None,
    root_fillet_mm: float = 0.5,
    architecture_id: str | None = None,
    n_surface: int = DEFAULT_SURFACE_POINTS,
    n_edge: int = DEFAULT_EDGE_POINTS,
) -> BladeRowGeometry:
    """Generate a real axial/radial blade row from a TURBO 01 row declaration."""

    if row.family not in ("axial", "mixed"):
        raise ValueError(f"AXIAL_BUILDER_REJECTS_FAMILY:{row.family}")
    clearance = tip_clearance_mm
    if clearance is None:
        quantity = row.clearance.tip_clearance
        clearance = 0.5 if quantity is None else quantity.value_si * 1000.0
    shroud_state = row.clearance.shroud_state
    half_width = axial_half_width_mm
    if half_width is None:
        half_width = max(section.chord_mm for section in sections) / 2.0
    geometry = BladeRowGeometry(
        row_id=row.row_id,
        role=row.role,
        frame=row.frame,
        family=row.family,
        blade_count=row.periodicity * row.row_count,
        sections=scaled_sections(
            sections,
            hub_radius_mm=hub_radius_mm,
            tip_radius_mm=(
                shroud_radius_mm
                if shroud_state == "shrouded"
                else shroud_radius_mm - clearance
            ),
        ),
        hub_radius_mm=hub_radius_mm,
        shroud_radius_mm=shroud_radius_mm,
        tip_clearance_mm=clearance,
        axial_location_mm=axial_location_mm,
        axial_half_width_mm=half_width,
        architecture_id=architecture_id,
        shroud_state=shroud_state,
        root_fillet_mm=root_fillet_mm,
        material_ref=row.material_ref,
        thermal_ref=row.thermal_ref,
        n_surface=n_surface,
        n_edge=n_edge,
    )
    return geometry


def blade_row_parameter_defs(geometry: BladeRowGeometry) -> tuple[ParameterDef, ...]:
    return geometry.cad_parameter_defs()
