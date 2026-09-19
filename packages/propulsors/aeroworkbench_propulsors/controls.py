"""Generic propulsor controls, design space, and constraints.

Per-rotor design variables (blade count, diameter, pitch/twist/chord, RPM,
direction, axial spacing, pitch schedule) are declared with typed bounds, and
manufacturability/operating constraints (max diameter/chord/RPM/tip Mach/stress/
clearance) plus a structural-resonance margin are checked. A declared limit
violation fails closed with provenance. The collective pitch schedule drives
variable pitch, and an optional cyclic seam is reserved for future rotorcraft.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from aeroworkbench_core.types import Provenance

from .aero import RotorAeroResult, RotorSpec
from .architecture import PropulsorArchitecture
from .provenance import analytical_provenance
from .validity import (
    LimitExceeded,
    PropulsorError,
    Validity,
    finite,
    nonempty,
)


@dataclass(frozen=True, slots=True)
class DesignVariable:
    """One bounded numeric design variable with a current value."""

    name: str
    unit: str
    lower: float
    upper: float
    value: float

    def __post_init__(self) -> None:
        nonempty(self.name, "design_variable.name")
        nonempty(self.unit, "design_variable.unit")
        finite(self.lower, "design_variable.lower")
        finite(self.upper, "design_variable.upper")
        finite(self.value, "design_variable.value")
        if self.lower > self.upper:
            raise PropulsorError(f"design_variable bounds inverted:{self.name}")
        if not self.lower <= self.value <= self.upper:
            raise PropulsorError(f"design_variable value outside bounds:{self.name}")

    def with_value(self, value: float) -> DesignVariable:
        finite(value, f"design_variable.{self.name}")
        if not self.lower <= value <= self.upper:
            raise PropulsorError(f"design_variable value outside bounds:{self.name}")
        return replace(self, value=value)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "lower": self.lower,
            "upper": self.upper,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class PropulsorDesignSpace:
    """A typed design space of per-rotor propulsor variables."""

    design_id: str
    variables: tuple[DesignVariable, ...]

    def __post_init__(self) -> None:
        nonempty(self.design_id, "design_space.design_id")
        if not self.variables:
            raise PropulsorError("design_space needs at least one variable")
        names = [variable.name for variable in self.variables]
        if len(names) != len(set(names)):
            raise PropulsorError("design_space duplicate variable name")

    def names(self) -> tuple[str, ...]:
        return tuple(variable.name for variable in self.variables)

    def variable(self, name: str) -> DesignVariable:
        for variable in self.variables:
            if variable.name == name:
                return variable
        raise PropulsorError(f"design_variable unknown:{name}")

    def value(self, name: str) -> float:
        return self.variable(name).value

    def with_value(self, name: str, value: float) -> PropulsorDesignSpace:
        updated = tuple(
            variable.with_value(value) if variable.name == name else variable
            for variable in self.variables
        )
        return replace(self, variables=updated)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "designId": self.design_id,
            "variables": [
                variable.canonical_payload()
                for variable in sorted(self.variables, key=lambda item: item.name)
            ],
        }


def rotor_design_space(
    architecture: PropulsorArchitecture,
    rotor_id: str,
    *,
    blade_count_bounds: tuple[int, int] = (2, 12),
    diameter_factor_bounds: tuple[float, float] = (0.5, 1.5),
    pitch_bounds_deg: tuple[float, float] = (-5.0, 45.0),
    rpm_factor_bounds: tuple[float, float] = (0.3, 1.3),
) -> PropulsorDesignSpace:
    """Build a per-rotor design space from a declared architecture."""

    rotor = architecture.rotor(rotor_id)
    diameter = rotor.diameter_m
    lower_blades, upper_blades = blade_count_bounds
    lower_factor, upper_factor = diameter_factor_bounds
    pitch_low, pitch_high = pitch_bounds_deg
    rpm_low, rpm_high = rpm_factor_bounds
    reference_rpm = rotor.rpm if rotor.rpm > 0.0 else 1000.0
    variables = (
        DesignVariable(
            f"{rotor_id}.bladeCount",
            "dimensionless",
            float(lower_blades),
            float(upper_blades),
            float(min(max(rotor.blade_count, lower_blades), upper_blades)),
        ),
        DesignVariable(
            f"{rotor_id}.diameter",
            "m",
            diameter * lower_factor,
            diameter * upper_factor,
            diameter,
        ),
        DesignVariable(
            f"{rotor_id}.collectivePitch",
            "deg",
            pitch_low,
            pitch_high,
            min(max(rotor.collective_pitch_deg, pitch_low), pitch_high),
        ),
        DesignVariable(
            f"{rotor_id}.rpm",
            "rpm",
            reference_rpm * rpm_low,
            reference_rpm * rpm_high,
            reference_rpm,
        ),
    )
    return PropulsorDesignSpace(
        design_id=f"{architecture.architecture_id}:{rotor_id}", variables=variables
    )


@dataclass(frozen=True, slots=True)
class PropulsorConstraints:
    """Manufacturability and operating constraints for a propulsor rotor."""

    max_diameter_m: float | None = None
    max_chord_m: float | None = None
    max_rpm: float | None = None
    max_tip_mach: float | None = None
    min_clearance_m: float | None = None
    max_root_stress_pa: float | None = None
    resonance_margin_fraction: float = 0.15

    def __post_init__(self) -> None:
        for name, value in (
            ("max_diameter_m", self.max_diameter_m),
            ("max_chord_m", self.max_chord_m),
            ("max_rpm", self.max_rpm),
            ("max_tip_mach", self.max_tip_mach),
            ("max_root_stress_pa", self.max_root_stress_pa),
        ):
            if value is not None:
                finite(value, f"constraints.{name}", positive=True)
        if self.min_clearance_m is not None:
            finite(self.min_clearance_m, "constraints.min_clearance_m", minimum=0.0)
        finite(
            self.resonance_margin_fraction,
            "constraints.resonance_margin_fraction",
            minimum=0.0,
            maximum=1.0,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "maxDiameterM": self.max_diameter_m,
            "maxChordM": self.max_chord_m,
            "maxRpm": self.max_rpm,
            "maxTipMach": self.max_tip_mach,
            "minClearanceM": self.min_clearance_m,
            "maxRootStressPa": self.max_root_stress_pa,
            "resonanceMarginFraction": self.resonance_margin_fraction,
        }


@dataclass(frozen=True, slots=True)
class ConstraintReport:
    """Outcome of applying all declared propulsor constraints."""

    rotor_id: str
    passed: bool
    checks: dict[str, bool]
    violations: tuple[str, ...]
    utilization: dict[str, float]
    provenance: Provenance

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "rotorId": self.rotor_id,
            "passed": self.passed,
            "checks": dict(self.checks),
            "violations": list(self.violations),
            "utilization": dict(self.utilization),
        }


def blade_passing_frequency_hz(rotor: RotorSpec) -> float:
    """Blade passing frequency at the rotor plane (per-rev excitation)."""

    return rotor.revolutions_per_second * rotor.blade_count


def resonance_margin(
    excitation_hz: float,
    natural_frequency_hz: float,
) -> float:
    """Relative separation between an excitation and a natural frequency."""

    finite(excitation_hz, "resonance.excitation_hz", positive=True)
    finite(natural_frequency_hz, "resonance.natural_frequency_hz", positive=True)
    return abs(excitation_hz - natural_frequency_hz) / natural_frequency_hz


def check_constraints(
    rotor: RotorSpec,
    result: RotorAeroResult,
    constraints: PropulsorConstraints,
    *,
    max_chord_m: float | None = None,
    clearance_m: float | None = None,
    root_stress_pa: float | None = None,
    blade_natural_frequency_hz: float | None = None,
) -> ConstraintReport:
    """Apply constraints and fail closed (LimitExceeded) on any violation."""

    if clearance_m is not None:
        finite(clearance_m, "constraints.clearance_m", minimum=0.0)
    if root_stress_pa is not None:
        finite(root_stress_pa, "constraints.root_stress_pa", minimum=0.0)
    if blade_natural_frequency_hz is not None:
        finite(
            blade_natural_frequency_hz,
            "constraints.blade_natural_frequency_hz",
            positive=True,
        )
    diameter = rotor.diameter_m
    chord = max_chord_m if max_chord_m is not None else max(
        station.chord_m for station in rotor.stations
    )
    utilization: dict[str, float] = {}
    checks: dict[str, bool] = {}
    violations: list[str] = []

    def _apply(name: str, actual: float | None, limit: float | None, key: str) -> None:
        if limit is None or actual is None:
            return
        ratio = actual / limit if limit > 0.0 else 0.0
        utilization[key] = ratio
        checks[key] = actual <= limit
        if actual > limit:
            violations.append(key)

    _apply("diameter", diameter, constraints.max_diameter_m, "max_diameter")
    _apply("chord", chord, constraints.max_chord_m, "max_chord")
    _apply("rpm", rotor.rpm, constraints.max_rpm, "max_rpm")
    _apply("tip_mach", result.tip_mach, constraints.max_tip_mach, "max_tip_mach")
    _apply("root_stress", root_stress_pa, constraints.max_root_stress_pa, "max_root_stress")
    if constraints.min_clearance_m is not None and clearance_m is not None:
        checks["min_clearance"] = clearance_m >= constraints.min_clearance_m
        utilization["min_clearance"] = (
            constraints.min_clearance_m / clearance_m if clearance_m > 0.0 else float("inf")
        )
        if clearance_m < constraints.min_clearance_m:
            violations.append("min_clearance")
    if blade_natural_frequency_hz is not None:
        excitation = blade_passing_frequency_hz(rotor)
        margin = resonance_margin(excitation, blade_natural_frequency_hz)
        checks["structural_resonance_margin"] = margin >= constraints.resonance_margin_fraction
        utilization["structural_resonance_margin"] = margin
        if margin < constraints.resonance_margin_fraction:
            violations.append("structural_resonance_margin")
    provenance = analytical_provenance(
        "propulsors.controls.constraints",
        {
            "rotor": rotor.canonical_payload(),
            "constraints": constraints.canonical_payload(),
            "result": result.canonical_payload(),
            "clearanceM": clearance_m,
            "rootStressPa": root_stress_pa,
            "bladeNaturalFrequencyHz": blade_natural_frequency_hz,
        },
        assumptions=("Deterministic screening envelope checks against declared limits.",),
    )
    report = ConstraintReport(
        rotor_id=rotor.rotor_id,
        passed=not violations,
        checks=checks,
        violations=tuple(violations),
        utilization=utilization,
        provenance=provenance,
    )
    if violations:
        raise LimitExceeded(
            f"PROPULSOR_LIMIT_EXCEEDED:{rotor.rotor_id}:{','.join(violations)}",
            violations=report.violations,
            provenance=provenance,
        )
    return report


def apply_collective_schedule(
    rotor: RotorSpec,
    schedule_points: tuple[tuple[float, float], ...],
    advance_ratio: float,
) -> RotorSpec:
    """Return a rotor whose collective pitch follows a schedule at a J value."""

    if len(schedule_points) < 2:
        raise PropulsorError("collective schedule needs at least two points")
    finite(advance_ratio, "advance_ratio", minimum=0.0)
    ordered = tuple(sorted(schedule_points, key=lambda point: point[0]))
    if advance_ratio <= ordered[0][0]:
        pitch = ordered[0][1]
    elif advance_ratio >= ordered[-1][0]:
        pitch = ordered[-1][1]
    else:
        pitch = ordered[-1][1]
        for (x0, y0), (x1, y1) in zip(ordered, ordered[1:], strict=False):
            if x0 <= advance_ratio <= x1:
                pitch = y0 + (advance_ratio - x0) / (x1 - x0) * (y1 - y0)
                break
    return replace(rotor, collective_pitch_deg=pitch)


def validate_operating_envelope(result: RotorAeroResult) -> Validity:
    """Return the recorded validity of a screening result (never optimistic)."""

    return result.validity


__all__ = [
    "ConstraintReport",
    "DesignVariable",
    "PropulsorConstraints",
    "PropulsorDesignSpace",
    "apply_collective_schedule",
    "blade_passing_frequency_hz",
    "check_constraints",
    "resonance_margin",
    "rotor_design_space",
    "validate_operating_envelope",
]
