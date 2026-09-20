"""Operating-envelope generation: viable/constrained/failed regions plus refinement."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import ResultSource

from ..canonical import content_digest
from .errors import OffdesignInputError
from .matching import PointMatch
from .operating_point import OperatingPoint
from .results import (
    DEFAULT_OFFDESIGN_SOFTWARE,
    EnvelopeCell,
    OffdesignFidelity,
    OffdesignValidity,
    OperatingEnvelope,
    offdesign_provenance,
)

MAX_ENVELOPE_CELLS = 64
MAX_REFINEMENT_SAMPLES = 16

ENVELOPE_AXES: tuple[str, ...] = (
    "mass_flow_kg_s",
    "ambient_pressure_pa",
    "ambient_temperature_k",
    "throttle",
    "bleed_fraction",
    "nozzle_area_m2",
    "inlet_mach",
)

EvaluatePoint = Callable[[OperatingPoint], PointMatch]

_CONSTRAINED_SURGE_FACTOR = 2.0


@dataclass(frozen=True, slots=True)
class EnvelopeAxis:
    field: str
    lower: float
    upper: float
    cells: int

    def __post_init__(self) -> None:
        if self.field not in ENVELOPE_AXES:
            raise OffdesignInputError(f"ENVELOPE_UNKNOWN_AXIS:{self.field}")
        if not self.lower < self.upper:
            raise OffdesignInputError(f"ENVELOPE_AXIS_BOUNDS_INVALID:{self.field}")
        if self.cells < 1:
            raise OffdesignInputError(f"ENVELOPE_AXIS_CELLS_INVALID:{self.field}")

    def centers(self) -> tuple[float, ...]:
        width = (self.upper - self.lower) / self.cells
        return tuple(self.lower + (index + 0.5) * width for index in range(self.cells))

    def canonical(self) -> dict[str, object]:
        return {
            "field": self.field,
            "lower": self.lower,
            "upper": self.upper,
            "cells": self.cells,
        }


@dataclass(frozen=True, slots=True)
class EnvelopeSpec:
    axes: tuple[EnvelopeAxis, ...]
    base: OperatingPoint
    min_surge_margin: float = 0.05
    point_prefix: str = "env"

    def __post_init__(self) -> None:
        if not 1 <= len(self.axes) <= 2:
            raise OffdesignInputError("ENVELOPE_NEEDS_ONE_OR_TWO_AXES")
        fields = [axis.field for axis in self.axes]
        if len(set(fields)) != len(fields):
            raise OffdesignInputError("ENVELOPE_DUPLICATE_AXIS")
        total = 1
        for axis in self.axes:
            total *= axis.cells
        if total > MAX_ENVELOPE_CELLS:
            raise OffdesignInputError(
                f"ENVELOPE_TOO_MANY_CELLS:{total}:{MAX_ENVELOPE_CELLS}"
            )
        if not self.min_surge_margin > 0.0:
            raise OffdesignInputError("ENVELOPE_SURGE_MARGIN_NOT_POSITIVE")

    def canonical(self) -> dict[str, object]:
        return {
            "axes": [axis.canonical() for axis in self.axes],
            "base": self.base.canonical(),
            "minSurgeMargin": self.min_surge_margin,
            "pointPrefix": self.point_prefix,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


def _point_for(
    spec: EnvelopeSpec, coordinates: Mapping[str, float], index: int
) -> OperatingPoint:
    fields: dict[str, object] = {
        "point_id": f"{spec.point_prefix}-{index}",
        "ambient_pressure_pa": spec.base.ambient_pressure_pa,
        "ambient_temperature_k": spec.base.ambient_temperature_k,
        "ambient_density_kg_m3": spec.base.ambient_density_kg_m3,
        "inlet_velocity_m_s": spec.base.inlet_velocity_m_s,
        "inlet_mach": spec.base.inlet_mach,
        "spool_speeds_rpm": spec.base.spool_speeds_rpm,
        "shaft_torque_n_m": spec.base.shaft_torque_n_m,
        "shaft_load_w": spec.base.shaft_load_w,
        "throttle": spec.base.throttle,
        "heat_input_w": spec.base.heat_input_w,
        "voltage_v": spec.base.voltage_v,
        "current_a": spec.base.current_a,
        "state_of_charge": spec.base.state_of_charge,
        "mass_flow_kg_s": spec.base.mass_flow_kg_s,
        "vgv_angle_deg": spec.base.vgv_angle_deg,
        "bleed_fraction": spec.base.bleed_fraction,
        "nozzle_area_m2": spec.base.nozzle_area_m2,
        "weight": spec.base.weight,
    }
    for field, value in coordinates.items():
        if field not in fields:
            raise OffdesignInputError(f"ENVELOPE_UNKNOWN_AXIS:{field}")
        fields[field] = value
    return OperatingPoint(**fields)  # type: ignore[arg-type]


def classify_match(match: PointMatch, min_surge_margin: float) -> str:
    if not match.hard_passed:
        return "failed"
    if match.surge_margin < min_surge_margin * _CONSTRAINED_SURGE_FACTOR:
        return "constrained"
    if any("boundary" in warning for warning in match.warnings):
        return "constrained"
    return "viable"


def generate_envelope(
    evaluate: EvaluatePoint,
    spec: EnvelopeSpec,
) -> tuple[tuple[EnvelopeCell, ...], tuple[OperatingPoint, ...]]:
    grids = [axis.centers() for axis in spec.axes]
    cells: list[EnvelopeCell] = []
    points: list[OperatingPoint] = []
    if len(grids) == 1:
        combos: list[tuple[float, ...]] = [(value,) for value in grids[0]]
    else:
        combos = [
            (first, second) for first in grids[0] for second in grids[1]
        ]
    for index, combo in enumerate(combos):
        coordinates = {
            axis.field: value for axis, value in zip(spec.axes, combo, strict=True)
        }
        point = _point_for(spec, coordinates, index)
        match = evaluate(point)
        status = classify_match(match, spec.min_surge_margin)
        ordered = tuple(sorted(coordinates.items(), key=lambda item: item[0]))
        cells.append(
            EnvelopeCell(
                coordinates=ordered,
                status=status,
                point_hash=content_digest(match.canonical()),
            )
        )
        points.append(point)
    return tuple(cells), tuple(points)


def refine_envelope(
    evaluate: EvaluatePoint,
    spec: EnvelopeSpec,
    cells: tuple[EnvelopeCell, ...],
) -> tuple[EnvelopeCell, ...]:
    boundaries: list[EnvelopeCell] = []
    statuses = [cell.status for cell in cells]
    for index, cell in enumerate(cells):
        if cell.status == "failed":
            continue
        neighbors = {
            statuses[other]
            for other in range(len(cells))
            if other != index
            and sum(
                1
                for (first_name, _), (second_name, _) in zip(
                    cells[other].coordinates, cell.coordinates, strict=True
                )
                if first_name == second_name
            )
            == len(cell.coordinates)
            and any(
                first != second
                for (_, first), (_, second) in zip(
                    cells[other].coordinates, cell.coordinates, strict=True
                )
            )
        }
        if "failed" in neighbors:
            boundaries.append(cell)
    refined: list[EnvelopeCell] = []
    budget = min(len(boundaries) * 2, MAX_REFINEMENT_SAMPLES)
    for position, cell in enumerate(boundaries):
        for half in (0.25, 0.75):
            if len(refined) >= budget:
                break
            coordinates = {
                name: value for name, value in cell.coordinates
            }
            first_axis = spec.axes[0].field
            width = (spec.axes[0].upper - spec.axes[0].lower) / spec.axes[0].cells
            coordinates[first_axis] = coordinates[first_axis] + (half - 0.5) * width
            point = _point_for(
                spec, coordinates, 1000 + position * 2 + (0 if half < 0.5 else 1)
            )
            match = evaluate(point)
            status = classify_match(match, spec.min_surge_margin)
            refined.append(
                EnvelopeCell(
                    coordinates=tuple(sorted(coordinates.items())),
                    status=status,
                    point_hash=content_digest(match.canonical()),
                )
            )
    return tuple(refined)


def envelope_result(
    spec: EnvelopeSpec,
    cells: tuple[EnvelopeCell, ...],
    refined: tuple[EnvelopeCell, ...] = (),
    fidelity: OffdesignFidelity = OffdesignFidelity.ENVELOPE_SCREENING,
) -> OperatingEnvelope:
    failed = sum(1 for cell in (*cells, *refined) if cell.status == "failed")
    inputs: dict[str, Any] = {
        "spec": spec.canonical(),
        "cells": [cell.canonical() for cell in cells],
        "refined": [cell.canonical() for cell in refined],
        "fidelity": fidelity.value,
    }
    provenance = offdesign_provenance(
        ResultSource.ANALYTICAL,
        fidelity,
        inputs,
        (
            "analytical screening envelope; adaptive refinement is bounded and local",
            "not a native solver result",
        ),
    )
    units = tuple(
        (axis.field, "dimensionless") for axis in spec.axes
    )
    validity = OffdesignValidity(
        passed=True,
        checks={"envelope_generated": True, "has_failed_region": failed > 0},
        detail=f"{len(cells)} cells, {len(refined)} refined, {failed} failed",
    )
    return OperatingEnvelope(
        cells=cells,
        refined_cells=refined,
        source=ResultSource.ANALYTICAL.value,
        fidelity=fidelity.value,
        units=units,
        validity=validity,
        input_hash=provenance.inputs_hash,
        software=DEFAULT_OFFDESIGN_SOFTWARE,
        provenance=provenance,
    )


__all__ = [
    "ENVELOPE_AXES",
    "MAX_ENVELOPE_CELLS",
    "MAX_REFINEMENT_SAMPLES",
    "EnvelopeAxis",
    "EnvelopeSpec",
    "classify_match",
    "envelope_result",
    "generate_envelope",
    "refine_envelope",
]
