"""Automated physical-closure gates for participant-declared measures.

GEN 12. Each family (mass, energy, momentum/force/torque, electrical power,
heat balance, field-interface conservation, geometry/clearance, dynamic and
resonance margins) is assessed with the normalized absolute/relative tolerance
already carried by :mod:`aeroworkbench_convergence.measures`, so 1 W and 1 m
are never compared against the same raw number.

Every assessment is fail-closed: a missing or non-finite declared quantity is
a failure with an explicit reason, never a silent pass. A candidate cannot be
called validated while one of its required closure gates fails.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from .measures import DEFAULT_MEASURES, ClosureMeasure, MeasureAssessment, assess_measure

__all__ = [
    "CLOSURE_FAMILIES",
    "ClosureAssessment",
    "FieldConservationAssessment",
    "ResonanceMargin",
    "assess_closure",
    "assess_field_interface_conservation",
    "assess_geometry_clearance",
    "assess_resonance_margin",
    "closure_measure_names",
]

#: Canonical closure families mapped to the measures they validate by default.
#: Callers may narrow the set via ``required=`` but never widen it silently.
CLOSURE_FAMILIES: dict[str, tuple[str, ...]] = {
    "mass": ("mass",),
    "energy": ("energy",),
    "momentum": ("momentum", "force", "torque"),
    "force": ("force", "torque"),
    "electrical-power": ("shaft-power",),
    "heat-balance": ("heat-flow", "energy", "temperature"),
    "field-interface": ("mass", "energy", "force"),
    "geometry": ("clearance", "displacement"),
    "resonance": (
        "resonance-separation",
        "critical-speeds",
        "modes",
        "forcing-spectra",
    ),
}


def closure_measure_names(family: str) -> tuple[str, ...]:
    """Canonical measures a family validates; raises on an unknown family."""

    try:
        return CLOSURE_FAMILIES[family]
    except KeyError:
        raise ValueError(f"UNKNOWN_CLOSURE_FAMILY:{family}") from None


@dataclass(frozen=True, slots=True)
class ClosureAssessment:
    """Verdict for one declared closure family on one candidate/result."""

    family: str
    passed: bool
    checks: tuple[MeasureAssessment, ...]
    missing: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "passed": self.passed,
            "missing": list(self.missing),
            "reason": self.reason,
            "checks": [
                {
                    "name": check.name,
                    "simulated": check.simulated,
                    "reference": check.reference,
                    "residual": check.residual,
                    "passed": check.passed,
                    "detail": check.detail,
                }
                for check in self.checks
            ],
        }


def assess_closure(
    family: str,
    simulated: Mapping[str, float],
    reference: Mapping[str, float],
    *,
    required: Sequence[str] | None = None,
    measures: Mapping[str, ClosureMeasure] | None = None,
) -> ClosureAssessment:
    """Assess one family against its declared simulated/reference quantities."""

    declared = tuple(required) if required is not None else closure_measure_names(family)
    if not declared:
        raise ValueError(f"CLOSURE_FAMILY_NEEDS_MEASURES:{family}")
    catalog = measures if measures is not None else DEFAULT_MEASURES
    checks: list[MeasureAssessment] = []
    missing: list[str] = []
    for name in declared:
        if name not in simulated or name not in reference:
            missing.append(name)
            continue
        spec = catalog.get(name)
        if spec is None:
            missing.append(name)
            continue
        checks.append(assess_measure(spec, float(simulated[name]), float(reference[name])))
    if missing:
        return ClosureAssessment(
            family,
            False,
            tuple(checks),
            tuple(missing),
            f"missing declared quantities:{','.join(missing)}",
        )
    failed = [check.name for check in checks if not check.passed]
    passed = not failed
    reason = (
        f"{family} closure passed for {','.join(declared)}"
        if passed
        else f"{family} closure failed:{','.join(failed)}"
    )
    return ClosureAssessment(family, passed, tuple(checks), (), reason)


@dataclass(frozen=True, slots=True)
class FieldConservationAssessment:
    """Conservation of one field integral across a nonmatching interface."""

    field: str
    source_integral: float
    target_integral: float
    relative_error: float
    tolerance: float
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "sourceIntegral": self.source_integral,
            "targetIntegral": self.target_integral,
            "relativeError": self.relative_error,
            "tolerance": self.tolerance,
            "passed": self.passed,
            "reason": self.reason,
        }


def _integral(values: Sequence[float], coordinates: Sequence[float] | None) -> float:
    if coordinates is None:
        return sum(float(value) for value in values)
    if len(coordinates) != len(values):
        raise ValueError("FIELD_CONSERVATION_COORDINATE_LENGTH_MISMATCH")
    if len(values) < 2:
        return float(values[0]) if values else 0.0
    total = 0.0
    for index in range(len(values) - 1):
        width = float(coordinates[index + 1]) - float(coordinates[index])
        total += 0.5 * (float(values[index]) + float(values[index + 1])) * width
    return total


def assess_field_interface_conservation(
    field: str,
    source_values: Sequence[float],
    target_values: Sequence[float],
    *,
    tolerance: float = 1e-6,
    source_coordinates: Sequence[float] | None = None,
    target_coordinates: Sequence[float] | None = None,
) -> FieldConservationAssessment:
    """Compare a field's integral on both sides of a nonmatching interface.

    A conservative transfer must reproduce the source integral on the target
    mesh. A relative error above ``tolerance`` (default 1e-6) fails closed.
    """

    if not field.strip():
        raise ValueError("FIELD_CONSERVATION_FIELD_REQUIRED")
    if not isfinite(tolerance) or tolerance <= 0:
        raise ValueError("FIELD_CONSERVATION_TOLERANCE_INVALID")
    source_integral = _integral(source_values, source_coordinates)
    target_integral = _integral(target_values, target_coordinates)
    scale = max(abs(source_integral), abs(target_integral), 1e-300)
    relative_error = abs(source_integral - target_integral) / scale
    passed = relative_error <= tolerance
    reason = (
        f"{field} interface conservation passed (rel err {relative_error:.3e} "
        f"<= {tolerance:.3e})"
        if passed
        else f"{field} interface conservation failed (rel err {relative_error:.3e})"
    )
    return FieldConservationAssessment(
        field,
        source_integral,
        target_integral,
        relative_error,
        tolerance,
        passed,
        reason,
    )


@dataclass(frozen=True, slots=True)
class ResonanceMargin:
    """Smallest normalized separation between an operating speed and a
    declared critical speed."""

    operating_speed: float
    closest_critical: float
    separation_ratio: float
    critical_margin: float
    warning_margin: float
    passed: bool
    warning: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "operatingSpeed": self.operating_speed,
            "closestCritical": self.closest_critical,
            "separationRatio": self.separation_ratio,
            "criticalMargin": self.critical_margin,
            "warningMargin": self.warning_margin,
            "passed": self.passed,
            "warning": self.warning,
            "reason": self.reason,
        }


def assess_resonance_margin(
    operating_speed: float,
    critical_speeds: Sequence[float],
    *,
    critical_margin: float = 0.05,
    warning_margin: float = 0.15,
) -> ResonanceMargin:
    """Dynamic/resonance gate: operating speed must clear every critical speed."""

    for label, value in (("operating", operating_speed),):
        if not isfinite(value) or value < 0:
            raise ValueError(f"RESONANCE_{label.upper()}_SPEED_INVALID")
    for label, value in (("critical", critical_margin), ("warning", warning_margin)):
        if not isfinite(value) or value < 0:
            raise ValueError(f"RESONANCE_{label.upper()}_MARGIN_INVALID")
    if critical_margin > warning_margin:
        raise ValueError("RESONANCE_CRITICAL_MARGIN_EXCEEDS_WARNING_MARGIN")
    positives = [float(speed) for speed in critical_speeds if isfinite(speed) and speed > 0]
    if not positives:
        return ResonanceMargin(
            operating_speed, 0.0, float("inf"), critical_margin, warning_margin,
            True, False, "no declared critical speeds; resonance gate vacuously holds",
        )
    closest = min(positives, key=lambda speed: abs(speed - operating_speed))
    separation = abs(closest - operating_speed) / closest
    passed = separation >= critical_margin
    warning = passed and separation < warning_margin
    if not passed:
        reason = (
            f"operating speed {operating_speed:.6g} is {separation:.3%} from critical "
            f"{closest:.6g} (< critical margin {critical_margin:.3%})"
        )
    elif warning:
        reason = (
            f"operating speed {operating_speed:.6g} is {separation:.3%} from critical "
            f"{closest:.6g} (< warning margin {warning_margin:.3%})"
        )
    else:
        reason = (
            f"operating speed clears critical {closest:.6g} by {separation:.3%}"
        )
    return ResonanceMargin(
        operating_speed, closest, separation, critical_margin, warning_margin,
        passed, warning, reason,
    )


@dataclass(frozen=True, slots=True)
class ClearanceAssessment:
    """Geometry/clearance gate with a normalized tolerance band."""

    required_clearance: float
    achieved_clearance: float
    tolerance: float
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "requiredClearance": self.required_clearance,
            "achievedClearance": self.achieved_clearance,
            "tolerance": self.tolerance,
            "passed": self.passed,
            "reason": self.reason,
        }


def assess_geometry_clearance(
    required_clearance: float, achieved_clearance: float, *, tolerance: float = 1e-6
) -> ClearanceAssessment:
    """Pass only when the achieved clearance is within tolerance of required."""

    for label, value in (
        ("required", required_clearance),
        ("achieved", achieved_clearance),
        ("tolerance", tolerance),
    ):
        if not isfinite(value):
            raise ValueError(f"GEOMETRY_CLEARANCE_NONFINITE:{label}")
    if tolerance < 0:
        raise ValueError("GEOMETRY_CLEARANCE_TOLERANCE_NEGATIVE")
    passed = abs(achieved_clearance - required_clearance) <= tolerance
    reason = (
        f"clearance {achieved_clearance:.6g} matches required {required_clearance:.6g} "
        f"within {tolerance:.3g}"
        if passed
        else f"clearance {achieved_clearance:.6g} violates required "
        f"{required_clearance:.6g} by {abs(achieved_clearance - required_clearance):.3g}"
    )
    return ClearanceAssessment(
        required_clearance, achieved_clearance, tolerance, passed, reason
    )
