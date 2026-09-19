"""Robust-design hooks: clean vs degraded worst-case constraints.

A campaign can evaluate clean and degraded conditions and impose a worst-case
robust constraint on any named quantity. The verdict records the clean value,
the degraded value, the governing (worst-case) value, the margin against the
declared limit, and full provenance. Nothing is fabricated: the values are the
explicit clean/degraded inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aeroworkbench_core.types import Provenance

from .contracts import DEFAULT_SOFTWARE, SoftwareIdentity, Validity
from .degradation import DegradationState
from .errors import EnvironmentalError, finite
from .exposure import EnvironmentState
from .provenance import analytical_provenance
from .units import Quantity, from_si, require_dimension


class ConstraintDirection(StrEnum):
    """A limit that bounds a quantity from above or below."""

    MAXIMUM = "maximum"
    MINIMUM = "minimum"


@dataclass(frozen=True, slots=True)
class RobustConstraint:
    """A worst-case constraint on a named quantity in a declared unit."""

    name: str
    quantity_name: str
    limit: Quantity
    direction: ConstraintDirection = ConstraintDirection.MAXIMUM
    margin_fraction: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.quantity_name.strip():
            raise EnvironmentalError("robust.constraint identity is required")
        finite(self.margin_fraction, "robust.marginFraction", minimum=0.0)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self.quantity_name,
            "limit": self.limit.canonical(),
            "direction": self.direction.value,
            "marginFraction": self.margin_fraction,
        }


@dataclass(frozen=True, slots=True)
class RobustCondition:
    """A named degraded condition to be evaluated by a robust campaign."""

    name: str
    environment: EnvironmentState

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise EnvironmentalError("robust.condition.name is required")


@dataclass(frozen=True, slots=True)
class RobustVerdict:
    """Worst-case verdict for one constraint over clean/degraded values."""

    constraint_name: str
    quantity_name: str
    clean_value: Quantity
    degraded_value: Quantity
    worst_value: Quantity
    margin: Quantity
    passed: bool
    validity: Validity
    provenance: Provenance
    software: SoftwareIdentity = DEFAULT_SOFTWARE

    @property
    def governing_condition(self) -> str:
        return (
            "degraded"
            if self.worst_value.value_si == self.degraded_value.value_si
            else "clean"
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "constraintName": self.constraint_name,
            "quantity": self.quantity_name,
            "cleanValue": self.clean_value.canonical(),
            "degradedValue": self.degraded_value.canonical(),
            "worstValue": self.worst_value.canonical(),
            "margin": self.margin.canonical(),
            "passed": self.passed,
            "governingCondition": self.governing_condition,
            "validity": self.validity.canonical(),
            "inputsHash": self.provenance.inputs_hash,
            "software": self.software.canonical(),
        }


def evaluate_robust_constraint(
    constraint: RobustConstraint,
    clean_value: Quantity,
    degraded_value: Quantity,
) -> RobustVerdict:
    """Apply a worst-case robust constraint over clean and degraded values."""

    require_dimension(clean_value, constraint.limit.dimension, "robust.cleanValue")
    require_dimension(degraded_value, constraint.limit.dimension, "robust.degradedValue")
    if constraint.direction is ConstraintDirection.MAXIMUM:
        worst = max(clean_value.value_si, degraded_value.value_si)
    else:
        worst = min(clean_value.value_si, degraded_value.value_si)
    limit = constraint.limit.value_si
    required = constraint.margin_fraction * abs(limit)
    margin = (
        limit - worst
        if constraint.direction is ConstraintDirection.MAXIMUM
        else worst - limit
    )
    passed = margin >= required
    provenance = analytical_provenance(
        "environmental.robust.worst-case",
        {
            "constraint": constraint.canonical_payload(),
            "cleanValue": clean_value.canonical(),
            "degradedValue": degraded_value.canonical(),
        },
        assumptions=("worst-case of explicit clean and degraded values",),
    )
    return RobustVerdict(
        constraint_name=constraint.name,
        quantity_name=constraint.quantity_name,
        clean_value=clean_value,
        degraded_value=degraded_value,
        worst_value=Quantity(from_si(worst, constraint.limit.unit), constraint.limit.unit),
        margin=Quantity(from_si(margin, constraint.limit.unit), constraint.limit.unit),
        passed=passed,
        validity=Validity(
            passed=passed,
            checks={"worst_case_within_required_margin": passed},
            detail=f"direction={constraint.direction.value}",
        ),
        provenance=provenance,
    )


def robust_conditions_for(
    environment: EnvironmentState, *, clean: bool = True
) -> tuple[RobustCondition, ...]:
    """Campaign conditions pairing the clean reference with each exposure."""

    conditions: list[RobustCondition] = []
    if clean:
        conditions.append(
            RobustCondition(
                name="clean",
                environment=EnvironmentState(
                    environment_id=environment.environment_id,
                    revision=environment.revision,
                    atmosphere_model=environment.atmosphere_model,
                    ambient_temperature=environment.ambient_temperature,
                ),
            )
        )
    for exposure in environment.exposures:
        conditions.append(
            RobustCondition(
                name=f"degraded:{exposure.kind.value}",
                environment=EnvironmentState(
                    environment_id=environment.environment_id,
                    revision=environment.revision,
                    atmosphere_model=environment.atmosphere_model,
                    exposures=(exposure,),
                    ambient_temperature=environment.ambient_temperature,
                ),
            )
        )
    return tuple(conditions)


def degradation_digest_for(environment: EnvironmentState, degradation: DegradationState) -> str:
    """A stable digest binding a condition to its produced degradation."""

    if degradation.environment_id != environment.environment_id:
        raise EnvironmentalError("robust.environmentMismatch")
    return degradation.digest


__all__ = [
    "ConstraintDirection",
    "RobustCondition",
    "RobustConstraint",
    "RobustVerdict",
    "degradation_digest_for",
    "evaluate_robust_constraint",
    "robust_conditions_for",
]
