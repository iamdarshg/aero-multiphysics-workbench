"""Generic centre-of-gravity range and static-margin feasibility constraints.

Constraints are expressed per principal axis and carry their own source, so no
fixed-wing-only assumption is encoded in the core. A violated constraint yields
an explicit infeasible finding instead of raising, so a campaign can surface it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..state import MassProperties
from ..units import Quantity, Vec3, require_dimension
from .contracts import MassItemSource, MassResultMeta, result_meta

MODEL = "airframe-mass-constraints"

_ASSUMPTIONS = (
    "Constraints are declared per principal axis with explicit frames.",
    "Static margin is (neutral point - CG) / declared reference length.",
    "Feasibility is reported, never fabricated; violations are surfaced.",
)


class Axis(StrEnum):
    X = "x"
    Y = "y"
    Z = "z"


_AXIS_INDEX: dict[Axis, int] = {Axis.X: 0, Axis.Y: 1, Axis.Z: 2}


def axis_component(vector: Vec3, axis: Axis) -> float:
    return vector.value_si[_AXIS_INDEX[axis]]


@dataclass(frozen=True, slots=True)
class AxisRange:
    """Inclusive range along one axis in a declared frame; bounds are optional."""

    axis: Axis
    frame: str
    lower: Quantity | None = None
    upper: Quantity | None = None

    def __post_init__(self) -> None:
        if not self.frame.strip():
            raise ValueError("AXIS_RANGE_FRAME_REQUIRED")
        if self.lower is None and self.upper is None:
            raise ValueError("AXIS_RANGE_NEEDS_A_BOUND")
        for label, bound in (("lower", self.lower), ("upper", self.upper)):
            if bound is not None:
                require_dimension(bound, "length", f"axisRange.{label}")
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower.value_si > self.upper.value_si
        ):
            raise ValueError("AXIS_RANGE_LOWER_EXCEEDS_UPPER")

    def residual(self, value_si: float) -> float:
        """Non-negative violation magnitude; zero when inside the range."""
        if self.lower is not None and value_si < self.lower.value_si:
            return self.lower.value_si - value_si
        if self.upper is not None and value_si > self.upper.value_si:
            return value_si - self.upper.value_si
        return 0.0

    def contains(self, value_si: float, *, tolerance: float = 0.0) -> bool:
        return self.residual(value_si) <= tolerance

    def as_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis.value,
            "frame": self.frame,
            "lower": None if self.lower is None else self.lower.canonical(),
            "upper": None if self.upper is None else self.upper.canonical(),
        }


@dataclass(frozen=True, slots=True)
class CenterOfGravityRange:
    """Required CG interval along one axis, with provenance."""

    constraint_id: str
    axis_range: AxisRange
    source: MassItemSource

    def __post_init__(self) -> None:
        if not self.constraint_id.strip():
            raise ValueError("COG_CONSTRAINT_ID_REQUIRED")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.constraint_id,
            "kind": "cog-range",
            "axisRange": self.axis_range.as_dict(),
            "source": self.source.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class StaticMarginConstraint:
    """Static-margin-compatible CG constraint along one axis.

    ``margin = (neutral_point - cg) / reference_length``; the declared
    minimum/maximum are dimensionless margins.
    """

    constraint_id: str
    axis: Axis
    neutral_point: Vec3
    reference_length: Quantity
    source: MassItemSource
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not self.constraint_id.strip():
            raise ValueError("STATIC_MARGIN_ID_REQUIRED")
        require_dimension(self.neutral_point, "length", "staticMargin.neutralPoint")
        require_dimension(self.reference_length, "length", "staticMargin.referenceLength")
        if self.reference_length.value_si <= 0:
            raise ValueError("NONPOSITIVE_STATIC_MARGIN_REFERENCE_LENGTH")
        if self.minimum is None and self.maximum is None:
            raise ValueError("STATIC_MARGIN_NEEDS_A_BOUND")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("STATIC_MARGIN_MINIMUM_EXCEEDS_MAXIMUM")

    def margin(self, cg: Vec3) -> float:
        neutral = axis_component(self.neutral_point, self.axis)
        center = axis_component(cg, self.axis)
        return (neutral - center) / self.reference_length.value_si

    def residual(self, cg: Vec3) -> float:
        value = self.margin(cg)
        if self.minimum is not None and value < self.minimum:
            return self.minimum - value
        if self.maximum is not None and value > self.maximum:
            return value - self.maximum
        return 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.constraint_id,
            "kind": "static-margin",
            "axis": self.axis.value,
            "neutralPoint": self.neutral_point.canonical(),
            "referenceLength": self.reference_length.canonical(),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "source": self.source.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class CogConstraintFinding:
    constraint_id: str
    kind: str
    passed: bool
    detail: str
    value: float
    limit: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "constraintId": self.constraint_id,
            "kind": self.kind,
            "passed": self.passed,
            "detail": self.detail,
            "value": self.value,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class CogConstraintReport:
    findings: tuple[CogConstraintFinding, ...]
    meta: MassResultMeta

    @property
    def feasible(self) -> bool:
        return all(finding.passed for finding in self.findings)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(finding.detail for finding in self.findings if not finding.passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [finding.as_dict() for finding in self.findings],
            "meta": self.meta.as_dict(),
        }


def evaluate_cog_constraints(
    mass_properties: MassProperties,
    *,
    ranges: tuple[CenterOfGravityRange, ...] = (),
    static_margins: tuple[StaticMarginConstraint, ...] = (),
) -> CogConstraintReport:
    """Evaluate CG-range and static-margin constraints against an aggregate."""
    cg = mass_properties.cg
    findings: list[CogConstraintFinding] = []
    for range_constraint in ranges:
        if range_constraint.axis_range.frame != cg.frame:
            raise ValueError(f"COG_CONSTRAINT_FRAME_MISMATCH:{range_constraint.constraint_id}")
        value = axis_component(cg, range_constraint.axis_range.axis)
        residual = range_constraint.axis_range.residual(value)
        findings.append(
            CogConstraintFinding(
                constraint_id=range_constraint.constraint_id,
                kind="cog-range",
                passed=residual == 0.0,
                detail=(
                    f"CG {range_constraint.axis_range.axis.value}={value!r} m "
                    f"violates required range by {residual!r} m"
                    if residual
                    else f"CG {range_constraint.axis_range.axis.value}={value!r} m is inside range"
                ),
                value=value,
                limit=residual if residual else None,
            )
        )
    for margin_constraint in static_margins:
        if margin_constraint.neutral_point.frame != cg.frame:
            raise ValueError(f"STATIC_MARGIN_FRAME_MISMATCH:{margin_constraint.constraint_id}")
        margin = margin_constraint.margin(cg)
        residual = margin_constraint.residual(cg)
        findings.append(
            CogConstraintFinding(
                constraint_id=margin_constraint.constraint_id,
                kind="static-margin",
                passed=residual == 0.0,
                detail=(
                    f"static margin {margin!r} violates constraint by {residual!r}"
                    if residual
                    else f"static margin {margin!r} satisfies constraint"
                ),
                value=margin,
                limit=residual if residual else None,
            )
        )
    inputs = {
        "massProperties": mass_properties.canonical(),
        "ranges": [constraint.as_dict() for constraint in ranges],
        "staticMargins": [constraint.as_dict() for constraint in static_margins],
    }
    failed = tuple(finding.detail for finding in findings if not finding.passed)
    meta = result_meta(
        model=MODEL,
        inputs=inputs,
        valid=not failed,
        notes=failed,
        assumptions=_ASSUMPTIONS,
    )
    return CogConstraintReport(findings=tuple(findings), meta=meta)
