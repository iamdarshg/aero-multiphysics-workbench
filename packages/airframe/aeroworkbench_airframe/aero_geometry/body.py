"""Generic lofted aerodynamic body primitives: cross-sections along a spine.

A :class:`LoftedBody` is a stack of :class:`BodySection` records along a spine.
Each section carries width, height, lateral/vertical offset and a superellipse
exponent, so circular, elliptic and rounded-rectangular fuselage, nacelle, boom
or pod cross-sections share one contract. Geometry is deterministic and
unit-bearing; the structured seam exposes the shell/nose/tail control grids for
FFD deformation and meshing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, isfinite, pi, sin
from typing import Any

from aeroworkbench_geometry import ParameterDef, SemanticBinding
from aeroworkbench_semantics import SemanticAssignment

from ..canonical import content_digest
from .seam import Point, SurfaceGrid, SurfaceSeam

BODY_ROLES: tuple[str, ...] = ("fuselage", "nacelle", "boom", "pod", "lifting_body", "general")


def _finite(label: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{label}_NOT_FINITE")

BODY_BOUNDARY_ROLES: tuple[tuple[str, str, str], ...] = (
    ("nose", "nose", "interface"),
    ("tail", "tail", "interface"),
    ("crown", "crown", "wall"),
    ("keel", "keel", "wall"),
    ("side_left", "side_left", "wall"),
    ("side_right", "side_right", "wall"),
    ("region", "solid_region", "wall"),
)

DEFAULT_SECTION_POINTS = 16
MAX_SUPERELLIPSE_EXPONENT = 8.0


def _sign(value: float) -> float:
    return -1.0 if value < 0.0 else 1.0


@dataclass(frozen=True, slots=True)
class BodySection:
    """One body cross-section in a spine local frame (all lengths in mm)."""

    station_fraction: float
    spine_mm: tuple[float, float, float]
    width_mm: float
    height_mm: float
    lateral_offset_mm: float = 0.0
    vertical_offset_mm: float = 0.0
    superellipse_exponent: float = 2.0

    def __post_init__(self) -> None:
        if not isfinite(self.station_fraction) or not 0.0 <= self.station_fraction <= 1.0:
            raise ValueError("BODY_STATION_FRACTION_OUT_OF_RANGE")
        for label, value in (
            ("SPINE_X", self.spine_mm[0]),
            ("SPINE_Y", self.spine_mm[1]),
            ("SPINE_Z", self.spine_mm[2]),
        ):
            _finite(f"BODY_{label}", value)
        if not isfinite(self.width_mm) or self.width_mm <= 0.0:
            raise ValueError("BODY_WIDTH_MUST_BE_POSITIVE")
        if not isfinite(self.height_mm) or self.height_mm <= 0.0:
            raise ValueError("BODY_HEIGHT_MUST_BE_POSITIVE")
        _finite("BODY_LATERAL_OFFSET", self.lateral_offset_mm)
        _finite("BODY_VERTICAL_OFFSET", self.vertical_offset_mm)
        if (
            not isfinite(self.superellipse_exponent)
            or not 2.0 <= self.superellipse_exponent <= MAX_SUPERELLIPSE_EXPONENT
        ):
            raise ValueError("BODY_SUPERELLIPSE_EXPONENT_OUT_OF_RANGE")

    def outline(self, n_points: int = DEFAULT_SECTION_POINTS) -> tuple[tuple[float, float], ...]:
        if n_points < 4:
            raise ValueError("BODY_SECTION_POINTS_TOO_LOW")
        half_width = self.width_mm / 2.0
        half_height = self.height_mm / 2.0
        power = 2.0 / self.superellipse_exponent
        points: list[tuple[float, float]] = []
        for index in range(n_points):
            angle = 2.0 * pi * index / n_points
            cos_angle = cos(angle)
            sin_angle = sin(angle)
            x = half_width * _sign(cos_angle) * abs(cos_angle) ** power + self.lateral_offset_mm
            y = (
                half_height * _sign(sin_angle) * abs(sin_angle) ** power
                + self.vertical_offset_mm
            )
            points.append((x, y))
        return tuple(points)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "stationFraction": self.station_fraction,
            "spineMm": list(self.spine_mm),
            "widthMm": self.width_mm,
            "heightMm": self.height_mm,
            "lateralOffsetMm": self.lateral_offset_mm,
            "verticalOffsetMm": self.vertical_offset_mm,
            "superellipseExponent": self.superellipse_exponent,
        }

    @property
    def volume_m3(self) -> float:
        from math import pi
        total_mm3 = 0.0
        for left, right in zip(self.sections, self.sections[1:], strict=False):
            a0, b0 = left.width_mm / 2.0, left.height_mm / 2.0
            a1, b1 = right.width_mm / 2.0, right.height_mm / 2.0
            length = (right.station_fraction - left.station_fraction) * self.length_mm
            total_mm3 += pi * length / 3.0 * (a0*b0 + (a0*b1 + a1*b0) / 2.0 + a1*b1)
        return total_mm3 / 1.0e9


@dataclass(frozen=True, slots=True)
class LoftedBody:
    """Deterministic, hashable lofted body from longitudinal cross-sections."""

    body_id: str
    role: str
    sections: tuple[BodySection, ...]
    frame: str
    n_points: int = DEFAULT_SECTION_POINTS

    def __post_init__(self) -> None:
        if not self.body_id.strip():
            raise ValueError("BODY_ID_REQUIRED")
        if not self.frame.strip():
            raise ValueError("BODY_FRAME_REQUIRED")
        if self.role not in BODY_ROLES:
            raise ValueError(f"UNKNOWN_BODY_ROLE:{self.role}")
        if len(self.sections) < 2:
            raise ValueError("BODY_REQUIRES_TWO_SECTIONS")
        if self.n_points < 4:
            raise ValueError("BODY_SECTION_POINTS_TOO_LOW")
        fractions = [section.station_fraction for section in self.sections]
        if any(later <= earlier for earlier, later in zip(fractions, fractions[1:], strict=False)):
            raise ValueError("BODY_SECTIONS_MUST_BE_STATION_ORDERED")

    @classmethod
    def from_spine(
        cls,
        body_id: str,
        role: str,
        spine_points: tuple[tuple[float, float, float], ...],
        widths_mm: tuple[float, ...],
        heights_mm: tuple[float, ...],
        *,
        frame: str = "body-local",
        lateral_offsets_mm: tuple[float, ...] | None = None,
        vertical_offsets_mm: tuple[float, ...] | None = None,
        exponent: float = 2.0,
        n_points: int = DEFAULT_SECTION_POINTS,
    ) -> LoftedBody:
        count = len(spine_points)
        if count < 2:
            raise ValueError("BODY_REQUIRES_TWO_SECTIONS")
        if len(widths_mm) != count or len(heights_mm) != count:
            raise ValueError("BODY_SPINE_SECTION_LENGTH_MISMATCH")
        laterals = lateral_offsets_mm or (0.0,) * count
        verticals = vertical_offsets_mm or (0.0,) * count
        if len(laterals) != count or len(verticals) != count:
            raise ValueError("BODY_OFFSET_LENGTH_MISMATCH")
        sections = tuple(
            BodySection(
                station_fraction=index / (count - 1),
                spine_mm=spine_points[index],
                width_mm=widths_mm[index],
                height_mm=heights_mm[index],
                lateral_offset_mm=laterals[index],
                vertical_offset_mm=verticals[index],
                superellipse_exponent=exponent,
            )
            for index in range(count)
        )
        return cls(body_id=body_id, role=role, sections=sections, frame=frame, n_points=n_points)

    @property
    def length_mm(self) -> float:
        reach = [section.spine_mm[2] for section in self.sections]
        return max(reach) - min(reach)

    def section_loops(self) -> tuple[tuple[tuple[float, float], ...], ...]:
        return tuple(section.outline(self.n_points) for section in self.sections)

    def offsets_mm(self) -> tuple[float, ...]:
        return tuple(section.spine_mm[2] for section in self.sections)

    def cad_parameter_defs(self, prefix: str | None = None) -> tuple[ParameterDef, ...]:
        name = prefix or self.body_id
        return (
            ParameterDef(f"{name}.length", self.length_mm, unit="mm"),
            ParameterDef(
                f"{name}.maxWidth", max(section.width_mm for section in self.sections), unit="mm"
            ),
            ParameterDef(
                f"{name}.maxHeight", max(section.height_mm for section in self.sections), unit="mm"
            ),
        )

    def parameter_values(self) -> dict[str, float]:
        return {
            definition.name: float(definition.value or 0.0)
            for definition in self.cad_parameter_defs()
        }

    def with_parameters(self, values: dict[str, float]) -> LoftedBody:
        prefix = self.body_id
        if not any(name.startswith(f"{prefix}.") for name in values):
            return self
        current_length = self.length_mm
        current_width = max(section.width_mm for section in self.sections)
        current_height = max(section.height_mm for section in self.sections)
        target_length = values.get(f"{prefix}.length", current_length)
        target_width = values.get(f"{prefix}.maxWidth", current_width)
        target_height = values.get(f"{prefix}.maxHeight", current_height)
        if target_length <= 0.0 or target_width <= 0.0 or target_height <= 0.0:
            raise ValueError("BODY_PARAMETER_MUST_BE_POSITIVE")
        base_z = min(section.spine_mm[2] for section in self.sections)
        sections = tuple(
            replace(
                section,
                spine_mm=(
                    section.spine_mm[0],
                    section.spine_mm[1],
                    base_z + section.station_fraction * target_length,
                ),
                width_mm=section.width_mm * target_width / current_width,
                height_mm=section.height_mm * target_height / current_height,
            )
            for section in self.sections
        )
        return replace(self, sections=sections)

    def semantic_assignments(self) -> tuple[SemanticAssignment, ...]:
        return tuple(
            SemanticAssignment(
                surface_id=f"{self.body_id}.{region}",
                semantic_key=f"{self.body_id}.{region}",
                role=role,
                boundary=boundary,
            )
            for region, role, boundary in BODY_BOUNDARY_ROLES
        )

    def semantic_binding(self, component: str) -> SemanticBinding:
        return SemanticBinding(
            semantic_key=f"{self.body_id}.solid",
            kind="solid_region",
            region=self.body_id,
            component=component,
        )

    def seam(self) -> SurfaceSeam:
        """Structured shell/nose/tail control-grid seam."""
        loops = self.section_loops()
        shell_points: tuple[Point, ...] = tuple(
            (point[0], point[1], self.sections[index].spine_mm[2])
            for index, loop in enumerate(loops)
            for point in loop
        )
        grids: list[SurfaceGrid] = [
            SurfaceGrid(
                grid_id=f"{self.body_id}.shell",
                role="shell",
                kind="wall",
                nu=self.n_points,
                nv=len(self.sections),
                points=shell_points,
                closed_u=True,
            )
        ]
        for region, index, kind in (("nose", 0, "interface"), ("tail", -1, "interface")):
            spine_z = self.sections[index].spine_mm[2]
            cap_points: tuple[Point, ...] = tuple(
                (point[0], point[1], spine_z) for point in loops[index]
            )
            grids.append(
                SurfaceGrid(
                    grid_id=f"{self.body_id}.{region}",
                    role=region,
                    kind=kind,
                    nu=len(cap_points),
                    nv=1,
                    points=cap_points,
                    closed_u=True,
                )
            )
        return SurfaceSeam(seam_id=self.body_id, domain="solid", grids=tuple(grids))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "bodyId": self.body_id,
            "role": self.role,
            "frame": self.frame,
            "nPoints": self.n_points,
            "sections": [section.canonical_payload() for section in self.sections],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def lofted_body_digest(body: LoftedBody) -> str:
    """Deterministic SHA-256 identity of a lofted body."""

    return body.digest


__all__ = [
    "BODY_BOUNDARY_ROLES",
    "BODY_ROLES",
    "DEFAULT_SECTION_POINTS",
    "MAX_SUPERELLIPSE_EXPONENT",
    "BodySection",
    "LoftedBody",
    "lofted_body_digest",
]
