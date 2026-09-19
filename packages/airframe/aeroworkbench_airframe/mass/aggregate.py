"""Aggregate mass, centre of gravity, and full inertia via parallel-axis composition.

Component mass properties are rotated into the aggregate frame, translated to
the frame origin with the parallel-axis theorem, summed, and then shifted to the
aggregate centre of gravity. Closure (component sum, positive mass, positive-
definite inertia) is checked and fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..canonical import content_digest
from ..frames import Mat3, matmul, matvec, transpose
from ..state import InertiaTensor, MassProperties
from ..units import Quantity, Vec3
from .contracts import MassBreakdown, MassResultMeta, result_meta
from .errors import MassClosureError
from .linalg import (
    inertia_matrix,
    is_positive_definite,
    parallel_axis_matrix,
    tensor_from_matrix,
)

MODEL = "airframe-mass-properties"

_ASSUMPTIONS = (
    "Analytical parallel-axis composition of declared component mass items.",
    "No hidden default mass is injected; every item states its own properties.",
    "Installation rotations are orthonormal and carry determinant +1.",
)

_DEFAULT_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class MassClosureCheck:
    name: str
    passed: bool
    detail: str
    value: float | None = None
    tolerance: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "value": self.value,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True, slots=True)
class MassAggregate:
    """Aggregate mass properties plus closure checks and result metadata."""

    mass_properties: MassProperties
    checks: tuple[MassClosureCheck, ...]
    meta: MassResultMeta

    @property
    def total_mass(self) -> Quantity:
        return self.mass_properties.mass

    @property
    def cg(self) -> Vec3:
        return self.mass_properties.cg

    @property
    def inertia(self) -> InertiaTensor:
        return self.mass_properties.inertia

    @property
    def feasible(self) -> bool:
        return all(check.passed for check in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {
            "massProperties": self.mass_properties.canonical(),
            "checks": [check.as_dict() for check in self.checks],
            "meta": self.meta.as_dict(),
        }


def _matrix_add(left: Mat3, right: Mat3) -> Mat3:
    return (
        (left[0][0] + right[0][0], left[0][1] + right[0][1], left[0][2] + right[0][2]),
        (left[1][0] + right[1][0], left[1][1] + right[1][1], left[1][2] + right[1][2]),
        (left[2][0] + right[2][0], left[2][1] + right[2][1], left[2][2] + right[2][2]),
    )


def _matrix_scale(matrix: Mat3, factor: float) -> Mat3:
    return (
        (matrix[0][0] * factor, matrix[0][1] * factor, matrix[0][2] * factor),
        (matrix[1][0] * factor, matrix[1][1] * factor, matrix[1][2] * factor),
        (matrix[2][0] * factor, matrix[2][1] * factor, matrix[2][2] * factor),
    )


def compute_mass_properties(breakdown: MassBreakdown) -> MassProperties:
    """Aggregate one breakdown into mass, CG, and inertia in the breakdown frame."""
    total_mass = 0.0
    weighted = [0.0, 0.0, 0.0]
    about_origin: Mat3 = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    for item in breakdown.sorted_items():
        mass = item.mass.value_si
        rotation = item.installation.rotation
        local = inertia_matrix(item.inertia)
        rotated = matmul(matmul(rotation, local), transpose(rotation))
        local_cg = item.cg.value_si
        rotated_cg = matvec(rotation, local_cg)
        translation = item.installation.translation.value_si
        offset = (
            translation[0] + rotated_cg[0],
            translation[1] + rotated_cg[1],
            translation[2] + rotated_cg[2],
        )
        total_mass += mass
        for index in range(3):
            weighted[index] += mass * offset[index]
        term = _matrix_add(rotated, _matrix_scale(parallel_axis_matrix(offset), mass))
        about_origin = _matrix_add(about_origin, term)
    if total_mass <= 0.0:
        raise MassClosureError("NONPOSITIVE_TOTAL_MASS")
    cg = (weighted[0] / total_mass, weighted[1] / total_mass, weighted[2] / total_mass)
    about_cg = _matrix_add(about_origin, _matrix_scale(parallel_axis_matrix(cg), -total_mass))
    return MassProperties(
        mass=Quantity(total_mass, "kg"),
        cg=Vec3(x=cg[0], y=cg[1], z=cg[2], unit="m", frame=breakdown.frame),
        inertia=tensor_from_matrix(about_cg, breakdown.frame),
    )


def mass_closure_checks(
    breakdown: MassBreakdown,
    mass_properties: MassProperties,
    *,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> tuple[MassClosureCheck, ...]:
    """Deterministic closure checks over a computed aggregate."""
    component_sum = 0.0
    for item in breakdown.sorted_items():
        component_sum += item.mass.value_si
    total = mass_properties.mass.value_si
    residual = component_sum - total
    checks: list[MassClosureCheck] = [
        MassClosureCheck(
            name="component-mass-sum",
            passed=abs(residual) <= tolerance,
            detail=f"sum(components) - total = {residual!r}",
            value=residual,
            tolerance=tolerance,
        ),
        MassClosureCheck(
            name="positive-total-mass",
            passed=total > 0.0,
            detail=f"total mass = {total!r} kg",
            value=total,
            tolerance=0.0,
        ),
    ]
    matrix = inertia_matrix(mass_properties.inertia)
    checks.append(
        MassClosureCheck(
            name="inertia-positive-definite",
            passed=is_positive_definite(matrix),
            detail="leading principal minors of the aggregate inertia are positive",
            value=None,
            tolerance=0.0,
        )
    )
    return tuple(checks)


def aggregate_mass_properties(
    breakdown: MassBreakdown,
    *,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> MassAggregate:
    """Aggregate a breakdown and fail closed when any closure check is violated."""
    mass_properties = compute_mass_properties(breakdown)
    checks = mass_closure_checks(breakdown, mass_properties, tolerance=tolerance)
    failures = [check for check in checks if not check.passed]
    if failures:
        detail = ";".join(f"{check.name}:{check.detail}" for check in failures)
        raise MassClosureError(f"MASS_CLOSURE_VIOLATION:{detail}")
    meta = result_meta(
        model=MODEL,
        inputs=breakdown.canonical(),
        valid=True,
        notes=("all closure checks passed",),
        assumptions=_ASSUMPTIONS,
    )
    return MassAggregate(mass_properties=mass_properties, checks=checks, meta=meta)


def mass_properties_canonical(mass_properties: MassProperties) -> dict[str, Any]:
    """Canonical payload for a bare :class:`MassProperties` aggregate."""
    return mass_properties.canonical()


def mass_properties_digest(mass_properties: MassProperties) -> str:
    """Deterministic content digest of an aggregate mass-property set."""
    return content_digest(mass_properties.canonical())
