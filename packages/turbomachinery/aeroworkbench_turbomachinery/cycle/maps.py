"""Generic component-map contract for correctable-flow turbomachinery.

A map carries corrected speed, corrected flow, pressure/expansion ratio,
efficiency, surge/choke boundaries, provenance, a declared validity region, and
an explicit out-of-envelope policy. There is never silent extrapolation beyond
the declared validity: a request outside the region either fails closed or is
clamped with a recorded warning, and ``extrapolated`` stays ``False``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import CycleModelError, OutOfEnvelopePolicy


@dataclass(frozen=True, slots=True)
class MapProvenance:
    """Where a map revision came from; never a solver run unless executed."""

    source: str
    revision: str
    reference: str | None = None
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.revision.strip():
            raise CycleModelError("MAP_PROVENANCE_NEEDS_SOURCE_AND_REVISION")

    def canonical(self) -> dict[str, object]:
        return {
            "source": self.source,
            "revision": self.revision,
            "reference": self.reference,
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True, slots=True)
class MapLine:
    """One corrected-speed line: flow axis plus ratio/efficiency arrays."""

    corrected_speed: float
    corrected_flows: tuple[float, ...]
    pressure_ratios: tuple[float, ...]
    efficiencies: tuple[float, ...]
    surge_corrected_flow: float
    choke_corrected_flow: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.corrected_speed) or self.corrected_speed <= 0:
            raise CycleModelError("MAP_LINE_NEEDS_POSITIVE_CORRECTED_SPEED")
        if len(self.corrected_flows) < 1:
            raise CycleModelError("MAP_LINE_NEEDS_AT_LEAST_ONE_POINT")
        if not (
            len(self.corrected_flows)
            == len(self.pressure_ratios)
            == len(self.efficiencies)
        ):
            raise CycleModelError("MAP_LINE_ARRAY_LENGTH_MISMATCH")
        for low, high in zip(self.corrected_flows, self.corrected_flows[1:], strict=False):
            if not low < high:
                raise CycleModelError("MAP_LINE_FLOW_MUST_BE_STRICTLY_INCREASING")
        for ratio in self.pressure_ratios:
            if not math.isfinite(ratio) or ratio <= 0:
                raise CycleModelError("MAP_LINE_RATIO_MUST_BE_POSITIVE")
        for efficiency in self.efficiencies:
            if not 0 < efficiency <= 1:
                raise CycleModelError("MAP_LINE_EFFICIENCY_OUT_OF_RANGE")
        if not (
            self.corrected_flows[0]
            <= self.surge_corrected_flow
            <= self.choke_corrected_flow
            <= self.corrected_flows[-1]
        ):
            raise CycleModelError("MAP_LINE_SURGE_CHOKE_BOUNDS_INVALID")

    @property
    def flow_bounds(self) -> tuple[float, float]:
        return (self.corrected_flows[0], self.corrected_flows[-1])

    def canonical(self) -> dict[str, object]:
        return {
            "correctedSpeed": self.corrected_speed,
            "correctedFlows": list(self.corrected_flows),
            "pressureRatios": list(self.pressure_ratios),
            "efficiencies": list(self.efficiencies),
            "surgeCorrectedFlow": self.surge_corrected_flow,
            "chokeCorrectedFlow": self.choke_corrected_flow,
        }


@dataclass(frozen=True, slots=True)
class MapEvaluation:
    """One map evaluation with explicit boundary and envelope reporting."""

    corrected_speed: float
    corrected_flow: float
    pressure_ratio: float
    efficiency: float
    near_surge: bool
    near_choke: bool
    clamped: tuple[str, ...] = ()
    extrapolated: bool = False
    warnings: tuple[str, ...] = ()

    def canonical(self) -> dict[str, object]:
        return {
            "correctedSpeed": self.corrected_speed,
            "correctedFlow": self.corrected_flow,
            "pressureRatio": self.pressure_ratio,
            "expansionRatio": self.pressure_ratio,
            "efficiency": self.efficiency,
            "nearSurge": self.near_surge,
            "nearChoke": self.near_choke,
            "clamped": list(self.clamped),
            "extrapolated": self.extrapolated,
            "warnings": list(self.warnings),
        }


def _bracket(axis: tuple[float, ...], value: float) -> tuple[int, float]:
    if value <= axis[0]:
        return 0, 0.0
    if value >= axis[-1]:
        return len(axis) - 2, 1.0
    for index in range(len(axis) - 1):
        if axis[index] <= value <= axis[index + 1]:
            span = axis[index + 1] - axis[index]
            fraction = 0.0 if span == 0 else (value - axis[index]) / span
            return index, fraction
    return len(axis) - 2, 1.0


def _invert(axis: tuple[float, ...], values: tuple[float, ...], value: float) -> float:
    """Interpolate ``values`` at ``value`` on a monotonic axis of either sign."""

    if len(axis) == 1:
        return values[0]
    for index in range(len(axis) - 1):
        low, high = axis[index], axis[index + 1]
        if (low <= value <= high) or (high <= value <= low):
            if high == low:
                return values[index]
            fraction = (value - low) / (high - low)
            return values[index] + fraction * (values[index + 1] - values[index])
    return values[0] if abs(value - axis[0]) <= abs(value - axis[-1]) else values[-1]


def _clamp(
    value: float, bounds: tuple[float, float], policy: OutOfEnvelopePolicy, label: str
) -> tuple[float, tuple[str, ...]]:
    low, high = bounds
    if low <= value <= high:
        return value, ()
    if policy is OutOfEnvelopePolicy.FAIL:
        raise CycleModelError(f"MAP_OUT_OF_ENVELOPE:{label}:{value}:range=[{low},{high}]")
    clamped = min(max(value, low), high)
    return clamped, (f"{label} {value} clamped into validity envelope [{low},{high}]",)


class OperatingMap:
    """Immutable, validity-bounded map with explicit interpolation policy."""

    def __init__(
        self,
        *,
        machine: str,
        lines: tuple[MapLine, ...],
        provenance: MapProvenance,
        interpolation: str = "linear",
    ) -> None:
        if machine not in {"compressor", "fan", "turbine", "expander"}:
            raise CycleModelError(f"UNKNOWN_MAP_MACHINE:{machine}")
        if len(lines) < 1:
            raise CycleModelError("MAP_NEEDS_AT_LEAST_ONE_SPEED_LINE")
        for low, high in zip(lines, lines[1:], strict=False):
            if not low.corrected_speed < high.corrected_speed:
                raise CycleModelError("MAP_SPEED_LINES_MUST_BE_STRICTLY_INCREASING")
        if interpolation != "linear":
            raise CycleModelError(f"UNSUPPORTED_MAP_INTERPOLATION:{interpolation}")
        self.machine = machine
        self.lines = lines
        self.provenance = provenance
        self.interpolation = interpolation

    @property
    def corrected_speed_bounds(self) -> tuple[float, float]:
        return (self.lines[0].corrected_speed, self.lines[-1].corrected_speed)

    @property
    def corrected_flow_bounds(self) -> tuple[float, float]:
        return (
            min(line.surge_corrected_flow for line in self.lines),
            max(line.choke_corrected_flow for line in self.lines),
        )

    def _line_at_flow(
        self, line: MapLine, corrected_flow: float, policy: OutOfEnvelopePolicy
    ) -> tuple[float, float, tuple[str, ...]]:
        flow, clamped = _clamp(
            corrected_flow, line.flow_bounds, policy, "corrected_flow"
        )
        index, fraction = _bracket(line.corrected_flows, flow)
        if len(line.corrected_flows) == 1:
            return line.pressure_ratios[0], line.efficiencies[0], clamped
        pressure_ratio = (
            line.pressure_ratios[index]
            + fraction * (line.pressure_ratios[index + 1] - line.pressure_ratios[index])
        )
        efficiency = (
            line.efficiencies[index]
            + fraction * (line.efficiencies[index + 1] - line.efficiencies[index])
        )
        return pressure_ratio, efficiency, clamped

    def evaluate(
        self,
        corrected_speed: float,
        corrected_flow: float,
        policy: OutOfEnvelopePolicy = OutOfEnvelopePolicy.FAIL,
    ) -> MapEvaluation:
        """Evaluate ratio and efficiency from corrected speed and flow."""

        if not math.isfinite(corrected_speed) or not math.isfinite(corrected_flow):
            raise CycleModelError("MAP_NONFINITE_REQUEST")
        speed, speed_clamped = _clamp(
            corrected_speed, self.corrected_speed_bounds, policy, "corrected_speed"
        )
        index, fraction = _bracket(
            tuple(line.corrected_speed for line in self.lines), speed
        )
        first = self.lines[index]
        last = self.lines[min(index + 1, len(self.lines) - 1)]
        pr_first, eff_first, clamp_first = self._line_at_flow(first, corrected_flow, policy)
        pr_last, eff_last, clamp_last = self._line_at_flow(last, corrected_flow, policy)
        pressure_ratio = pr_first + fraction * (pr_last - pr_first)
        efficiency = eff_first + fraction * (eff_last - eff_first)
        nearest = first if fraction < 0.5 else last
        clamped = tuple(dict.fromkeys((*speed_clamped, *clamp_first, *clamp_last)))
        effective_flow = min(max(corrected_flow, nearest.flow_bounds[0]), nearest.flow_bounds[1])
        near_surge = effective_flow <= nearest.surge_corrected_flow * 1.02
        near_choke = effective_flow >= nearest.choke_corrected_flow * 0.98
        warnings = list(clamped)
        if near_surge:
            warnings.append("map operating point is near the surge boundary")
        if near_choke:
            warnings.append("map operating point is near the choke boundary")
        return MapEvaluation(
            corrected_speed=speed,
            corrected_flow=corrected_flow,
            pressure_ratio=pressure_ratio,
            efficiency=efficiency,
            near_surge=near_surge,
            near_choke=near_choke,
            clamped=clamped,
            extrapolated=False,
            warnings=tuple(warnings),
        )

    def flow_for_pressure_ratio(
        self,
        corrected_speed: float,
        pressure_ratio: float,
        policy: OutOfEnvelopePolicy = OutOfEnvelopePolicy.FAIL,
    ) -> float:
        """Invert one speed line to corrected flow for a target ratio."""

        if not math.isfinite(corrected_speed) or not math.isfinite(pressure_ratio):
            raise CycleModelError("MAP_NONFINITE_REQUEST")
        speed, _ = _clamp(
            corrected_speed, self.corrected_speed_bounds, policy, "corrected_speed"
        )
        line_index, speed_fraction = _bracket(
            tuple(line.corrected_speed for line in self.lines), speed
        )
        first, second = self.lines[line_index], self.lines[
            min(line_index + 1, len(self.lines) - 1)
        ]
        low = min(first.pressure_ratios[0], first.pressure_ratios[-1])
        high = max(first.pressure_ratios[0], first.pressure_ratios[-1])
        ratio, _ = _clamp(pressure_ratio, (low, high), policy, "pressure_ratio")
        flows: list[float] = []
        for line in (first, second):
            line_low = min(line.pressure_ratios[0], line.pressure_ratios[-1])
            line_high = max(line.pressure_ratios[0], line.pressure_ratios[-1])
            target = min(max(ratio, line_low), line_high)
            flows.append(_invert(line.pressure_ratios, line.corrected_flows, target))
        return flows[0] + speed_fraction * (flows[1] - flows[0])

    def canonical(self) -> dict[str, object]:
        return {
            "machine": self.machine,
            "interpolation": self.interpolation,
            "provenance": self.provenance.canonical(),
            "correctedSpeedBounds": list(self.corrected_speed_bounds),
            "correctedFlowBounds": list(self.corrected_flow_bounds),
            "lines": [line.canonical() for line in self.lines],
        }


def build_screening_map(
    *,
    machine: str,
    design_corrected_speed: float,
    design_corrected_flow: float,
    design_pressure_ratio: float,
    design_efficiency: float,
    speed_factors: tuple[float, ...] = (0.85, 1.0, 1.15),
    flow_factors: tuple[float, ...] = (0.75, 0.9, 1.0, 1.1, 1.2),
    revision: str = "screening-map-r1",
) -> OperatingMap:
    """Derive a tiny deterministic map from a declared preliminary design point.

    The map is a declared analytical reduction, not solver output; its
    provenance records that explicitly.
    """

    if not design_corrected_flow > 0 or not design_corrected_speed > 0:
        raise CycleModelError("SCREENING_MAP_NEEDS_POSITIVE_DESIGN_POINT")
    if design_pressure_ratio <= 0 or not 0 < design_efficiency <= 1:
        raise CycleModelError("SCREENING_MAP_DESIGN_RATIO_OR_EFFICIENCY_INVALID")
    lines: list[MapLine] = []
    for speed_factor in speed_factors:
        flows = tuple(design_corrected_flow * factor for factor in flow_factors)
        ratios: list[float] = []
        efficiencies: list[float] = []
        for factor in flow_factors:
            deviation = factor - 1.0
            ratio = design_pressure_ratio * (1.0 - 0.35 * deviation)
            efficiency = design_efficiency * (1.0 - 2.5 * deviation * deviation)
            ratios.append(max(ratio, 1.0001))
            efficiencies.append(min(max(efficiency, 0.05), 0.98))
        lines.append(
            MapLine(
                corrected_speed=design_corrected_speed * speed_factor,
                corrected_flows=flows,
                pressure_ratios=tuple(ratios),
                efficiencies=tuple(efficiencies),
                surge_corrected_flow=flows[0],
                choke_corrected_flow=flows[-1],
            )
        )
    return OperatingMap(
        machine=machine,
        lines=tuple(lines),
        provenance=MapProvenance(
            source="reduced-from-analytical-preliminary-design",
            revision=revision,
            assumptions=(
                "parabolic ratio/efficiency falloff around the declared design point",
                "no measured data; screening fidelity only",
            ),
        ),
    )


__all__ = [
    "MapEvaluation",
    "MapLine",
    "MapProvenance",
    "OperatingMap",
    "build_screening_map",
]
