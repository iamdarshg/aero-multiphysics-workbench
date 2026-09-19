"""Geometry-synthesis targets produced from a solved meanline/throughflow state.

These targets are the quantitative row/section data a downstream geometry
generator (TURBO 02) turns into real CAD: metal angles and stagger, chord and
solidity targets, annulus areas, row spacing, and blade/vane count ranges. They
are design intents, not native solver output.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from .design import StageDesign
from .throughflow import ThroughflowResult

_ROW_SPACING_FACTOR = 0.3
_BLADE_COUNT_SPREAD = 0.15


@dataclass(frozen=True, slots=True)
class RowGeometryTarget:
    """Row/section targets ready to parameterize geometry."""

    row_family: str
    metal_angle_in_deg: float
    metal_angle_out_deg: float
    stagger_deg: float
    camber_deg: float
    chord_m: float
    solidity: float
    span_m: float
    mean_radius_m: float
    annulus_area_in_m2: float
    annulus_area_out_m2: float
    blade_count: int
    blade_count_range: tuple[int, int]
    row_spacing_m: float
    meridional_angle_deg: float

    def canonical(self) -> dict[str, object]:
        return {
            "rowFamily": self.row_family,
            "metalAngleInDeg": self.metal_angle_in_deg,
            "metalAngleOutDeg": self.metal_angle_out_deg,
            "staggerDeg": self.stagger_deg,
            "camberDeg": self.camber_deg,
            "chordM": self.chord_m,
            "solidity": self.solidity,
            "spanM": self.span_m,
            "meanRadiusM": self.mean_radius_m,
            "annulusAreaInM2": self.annulus_area_in_m2,
            "annulusAreaOutM2": self.annulus_area_out_m2,
            "bladeCount": self.blade_count,
            "bladeCountRange": list(self.blade_count_range),
            "rowSpacingM": self.row_spacing_m,
            "meridionalAngleDeg": self.meridional_angle_deg,
        }


@dataclass(frozen=True, slots=True)
class GeometrySynthesis:
    """All row targets plus provenance for the synthesis step."""

    targets: tuple[RowGeometryTarget, ...]
    provenance: Provenance

    def canonical(self) -> dict[str, object]:
        return {"targets": [target.canonical() for target in self.targets]}


def _annulus_area(*, mass_flow_kg_s: float, density_kg_m3: float, meridional_m_s: float) -> float:
    return mass_flow_kg_s / (density_kg_m3 * meridional_m_s)


def _count_range(blade_count: int) -> tuple[int, int]:
    low = max(3, floor(blade_count * (1.0 - _BLADE_COUNT_SPREAD)))
    high = max(low + 1, ceil(blade_count * (1.0 + _BLADE_COUNT_SPREAD)))
    return (low, high)


def synthesize_geometry(stage: StageDesign, result: ThroughflowResult) -> GeometrySynthesis:
    """Turn a solved throughflow result into geometry-synthesis targets."""

    targets: list[RowGeometryTarget] = []
    for row, row_result in zip(stage.rows, result.rows, strict=True):
        radius = 0.5 * (row.mean_radius_in_m + row.mean_radius_out_m)
        area_in = _annulus_area(
            mass_flow_kg_s=stage.mass_flow_kg_s,
            density_kg_m3=row_result.inlet_state.density_kg_m3,
            meridional_m_s=row.meridional_velocity_in_m_s,
        )
        meridional_out = row.meridional_velocity_out_m_s or row.meridional_velocity_in_m_s
        area_out = _annulus_area(
            mass_flow_kg_s=stage.mass_flow_kg_s,
            density_kg_m3=row_result.outlet_state.density_kg_m3,
            meridional_m_s=meridional_out,
        )
        targets.append(
            RowGeometryTarget(
                row_family=row.row_family,
                metal_angle_in_deg=row.inlet_metal_angle_deg,
                metal_angle_out_deg=row.exit_metal_angle_deg,
                stagger_deg=row.stagger_deg,
                camber_deg=row.camber_deg,
                chord_m=row.chord_m,
                solidity=row.solidity,
                span_m=row.span_m,
                mean_radius_m=radius,
                annulus_area_in_m2=area_in,
                annulus_area_out_m2=area_out,
                blade_count=row.blade_count,
                blade_count_range=_count_range(row.blade_count),
                row_spacing_m=_ROW_SPACING_FACTOR * row.chord_m,
                meridional_angle_deg=row.meridional_angle_deg,
            )
        )
    provenance = Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model="meanline-geometry-synthesis",
        model_version="1.0",
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={"stage": stage.canonical(), "meanlineSource": result.source},
        assumptions=(
            "Annulus area from continuity A = mdot/(rho*Vm); blade count from "
            "solidity and mean circumference; row spacing at 0.3 chord (screening).",
        ),
    )
    return GeometrySynthesis(targets=tuple(targets), provenance=provenance)


__all__ = ["RowGeometryTarget", "GeometrySynthesis", "synthesize_geometry"]
