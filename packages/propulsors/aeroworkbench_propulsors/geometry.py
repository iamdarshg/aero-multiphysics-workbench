"""Real propeller / open-rotor CAD from generic blade-row primitives.

Spanwise airfoil sections, chord/twist/sweep/rake distributions, blade count,
pitch axis, hub/root geometry, an optional spinner/hub, and the actual axial
spacing between contra-rotating rows are represented through the shared
turbomachinery blade-row and section contracts. The canonical geometry is a
kernel-independent structured-surface body with a content digest; native BREP
solids are produced through the shared CAD seam and fail closed when no kernel
is present. No duct or stator is required.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import cos, isfinite, pi, sin
from typing import Any

from aeroworkbench_turbomachinery.geometry import (  # type: ignore[import-not-found, unused-ignore]
    CAMBER_FAMILIES,
    THICKNESS_FAMILIES,
    BladeRowGeometry,
    BladeSection,
    CamberLine,
    GeometryBody,
    GeometryDiagnostic,
    SurfacePatch,
    ThicknessDistribution,
)

from .architecture import SpinnerGeometry
from .validity import CapabilityUnavailable, PropulsorError, finite, integer, nonempty


@dataclass(frozen=True, slots=True)
class SpanSection:
    """One spanwise section: chord/twist/sweep/rake plus profile families."""

    radius_fraction: float
    chord_m: float
    twist_deg: float
    sweep_m: float = 0.0
    rake_m: float = 0.0
    thickness_ratio: float = 0.08
    camber_ratio: float = 0.0
    camber_family: str = "circular_arc"
    thickness_family: str = "naca4"

    def __post_init__(self) -> None:
        finite(self.radius_fraction, "section.radius_fraction", minimum=0.0, maximum=1.0)
        finite(self.chord_m, "section.chord_m", positive=True)
        finite(self.twist_deg, "section.twist_deg")
        finite(self.sweep_m, "section.sweep_m")
        finite(self.rake_m, "section.rake_m")
        finite(self.thickness_ratio, "section.thickness_ratio", positive=True)
        finite(self.camber_ratio, "section.camber_ratio", minimum=0.0, maximum=0.5)
        if self.camber_family not in CAMBER_FAMILIES:
            raise PropulsorError(f"section.camber_family unknown:{self.camber_family}")
        if self.thickness_family not in THICKNESS_FAMILIES:
            raise PropulsorError(f"section.thickness_family unknown:{self.thickness_family}")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "radiusFraction": self.radius_fraction,
            "chordM": self.chord_m,
            "twistDeg": self.twist_deg,
            "sweepM": self.sweep_m,
            "rakeM": self.rake_m,
            "thicknessRatio": self.thickness_ratio,
            "camberRatio": self.camber_ratio,
            "camberFamily": self.camber_family,
            "thicknessFamily": self.thickness_family,
        }


@dataclass(frozen=True, slots=True)
class PropellerGeometry:
    """Real geometry for one propulsor rotor (optionally a coaxial pair row)."""

    rotor_id: str
    blade_count: int
    tip_radius_m: float
    hub_radius_m: float
    sections: tuple[SpanSection, ...]
    pitch_axis_fraction: float = 0.25
    spinner: SpinnerGeometry | None = None
    coaxial: bool = False
    axial_spacing_m: float | None = None
    axial_offset_m: float = 0.0
    shroud_state: str = "unshrouded"
    root_fillet_m: float = 0.002
    material_ref: str | None = None
    architecture_id: str | None = None
    n_surface: int = 9
    n_edge: int = 4

    def __post_init__(self) -> None:
        nonempty(self.rotor_id, "geometry.rotor_id")
        integer(self.blade_count, "geometry.blade_count", minimum=1, maximum=64)
        finite(self.tip_radius_m, "geometry.tip_radius_m", positive=True)
        finite(self.hub_radius_m, "geometry.hub_radius_m", positive=True)
        if self.hub_radius_m >= self.tip_radius_m:
            raise PropulsorError("geometry.hub_radius_m must be below tip")
        if len(self.sections) < 2:
            raise PropulsorError("geometry needs at least two span sections")
        for section in self.sections:
            if section.radius_fraction > 1.0:
                raise PropulsorError("geometry.section.radius_fraction out of range")
        finite(self.pitch_axis_fraction, "geometry.pitch_axis_fraction", minimum=0.0, maximum=1.0)
        finite(self.axial_offset_m, "geometry.axial_offset_m")
        if self.shroud_state not in ("shrouded", "unshrouded"):
            raise PropulsorError(f"geometry.shroud_state unknown:{self.shroud_state}")
        finite(self.root_fillet_m, "geometry.root_fillet_m", minimum=0.0)
        if self.coaxial and self.axial_spacing_m is None:
            raise PropulsorError("coaxial geometry requires axial_spacing_m")
        if self.axial_spacing_m is not None:
            finite(self.axial_spacing_m, "geometry.axial_spacing_m", positive=True)

    def blade_sections(self) -> tuple[BladeSection, ...]:
        """Convert spanwise distributions to shared blade-section primitives."""

        span = self.tip_radius_m - self.hub_radius_m
        sections: list[BladeSection] = []
        for section in self.sections:
            sections.append(
                BladeSection(
                    span=section.radius_fraction,
                    radius_mm=(self.hub_radius_m + section.radius_fraction * span) * 1000.0,
                    chord_mm=section.chord_m * 1000.0,
                    stagger_deg=section.twist_deg,
                    camber=CamberLine(
                        family=section.camber_family, camber_ratio=section.camber_ratio
                    ),
                    thickness=ThicknessDistribution(
                        family=section.thickness_family,
                        thickness_ratio=section.thickness_ratio,
                    ),
                    sweep_mm=section.sweep_m * 1000.0,
                    stack_offset_mm=section.rake_m * 1000.0,
                    stacking_axis="axial",
                )
            )
        return tuple(sections)

    def blade_row(self) -> BladeRowGeometry:
        """Real structured-surface blade row in the shared geometry contract."""

        return BladeRowGeometry(
            row_id=self.rotor_id,
            role="work_adding",
            frame="rotating",
            family="axial",
            blade_count=self.blade_count,
            sections=self.blade_sections(),
            hub_radius_mm=self.hub_radius_m * 1000.0,
            shroud_radius_mm=self.tip_radius_m * 1000.0,
            tip_clearance_mm=0.0,
            axial_location_mm=self.axial_offset_m * 1000.0,
            axial_half_width_mm=max(section.chord_m for section in self.sections) * 500.0,
            architecture_id=self.architecture_id,
            shroud_state=self.shroud_state,
            root_fillet_mm=self.root_fillet_m * 1000.0,
            material_ref=self.material_ref,
            n_surface=self.n_surface,
            n_edge=self.n_edge,
        )

    def _spinner_body(self) -> GeometryBody | None:
        if self.spinner is None:
            return None
        columns = 16
        axial = 6
        patches: list[SurfacePatch] = []
        for label, radius_end, z_end in (
            ("spinner", self.spinner.nose_radius_m * 1000.0, 0.0),
            ("hub", self.spinner.hub_radius_m * 1000.0, self.spinner.nose_length_m * 1000.0),
        ):
            points: list[tuple[float, float, float]] = []
            z_start = -self.spinner.nose_length_m * 1000.0 if label == "spinner" else 0.0
            for axial_index in range(axial):
                fraction = axial_index / (axial - 1)
                z = z_start + (z_end - z_start) * fraction
                radius = max(radius_end * (0.15 + 0.85 * fraction), 1e-6)
                for column in range(columns):
                    theta = 2.0 * pi * column / columns
                    points.append((radius * cos(theta), radius * sin(theta), z))
            patches.append(
                SurfacePatch(
                    patch_id=f"{self.rotor_id}.{label}.surface",
                    role=label,
                    kind="wall",
                    nu=columns,
                    nv=axial,
                    points=tuple(points),
                    closed_u=True,
                )
            )
        return GeometryBody(
            body_id=f"{self.rotor_id}.spinner", domain="solid", patches=tuple(patches)
        )

    def bodies(self) -> tuple[GeometryBody, ...]:
        row = self.blade_row()
        bodies: list[GeometryBody] = list(row.row_bodies())
        spinner = self._spinner_body()
        if spinner is not None:
            bodies.append(spinner)
        return tuple(bodies)

    def validate(self) -> tuple[GeometryDiagnostic, ...]:
        diagnostics: tuple[GeometryDiagnostic, ...] = tuple(self.blade_row().validate())
        return diagnostics

    def geometry_digest(self) -> str:
        payload = {
            "rotorId": self.rotor_id,
            "bladeCount": self.blade_count,
            "tipRadiusM": self.tip_radius_m,
            "hubRadiusM": self.hub_radius_m,
            "pitchAxisFraction": self.pitch_axis_fraction,
            "shroudState": self.shroud_state,
            "coaxial": self.coaxial,
            "axialSpacingM": self.axial_spacing_m,
            "axialOffsetM": self.axial_offset_m,
            "sections": [section.canonical_payload() for section in self.sections],
            "spinner": None if self.spinner is None else self.spinner.canonical_payload(),
            "bodies": sorted(body.digest() for body in self.bodies()),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def parameters(self) -> tuple[tuple[str, float, str], ...]:
        defs: list[tuple[str, float, str]] = [
            (f"{self.rotor_id}.bladeCount", float(self.blade_count), "dimensionless"),
            (f"{self.rotor_id}.tipRadius", self.tip_radius_m, "m"),
            (f"{self.rotor_id}.hubRadius", self.hub_radius_m, "m"),
            (f"{self.rotor_id}.pitchAxis", self.pitch_axis_fraction, "dimensionless"),
        ]
        for index, section in enumerate(self.sections):
            prefix = f"{self.rotor_id}.section.{index}"
            defs.extend(
                (
                    (f"{prefix}.chord", section.chord_m, "m"),
                    (f"{prefix}.twist", section.twist_deg, "deg"),
                    (f"{prefix}.sweep", section.sweep_m, "m"),
                    (f"{prefix}.rake", section.rake_m, "m"),
                )
            )
        return tuple(defs)

    def brep_receipts(self) -> dict[str, Any]:
        """Native BREP solids through the shared CAD seam; fails closed if absent."""

        from aeroworkbench_turbomachinery.geometry import cad as cad_module

        identity = cad_module.probe_cad()
        if not identity.available:
            raise CapabilityUnavailable(
                "CAD kernel unavailable; native propeller BREP fails closed"
            )
        shapes: dict[str, Any] = cad_module.row_shapes(self.blade_row())
        return {
            name: cad_module.solid_receipt(name, shape).canonical()
            for name, shape in shapes.items()
        }


def geometry_hash(geometry: PropellerGeometry | tuple[PropellerGeometry, ...]) -> str:
    """Deterministic content hash of one or more rotor geometries."""

    items = (geometry,) if isinstance(geometry, PropellerGeometry) else geometry
    payload = [item.geometry_digest() for item in items]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def coaxial_spacing_ok(
    front: PropellerGeometry, rear: PropellerGeometry, *, minimum_spacing_m: float
) -> bool:
    """True when the real axial gap between contra-rotating rows clears a limit."""

    if not isfinite(minimum_spacing_m) or minimum_spacing_m < 0.0:
        raise PropulsorError("minimum_spacing_m must be finite and nonnegative")
    gap = rear.axial_offset_m - front.axial_offset_m
    return gap >= minimum_spacing_m


__all__ = [
    "PropellerGeometry",
    "SpanSection",
    "coaxial_spacing_ok",
    "geometry_hash",
]
