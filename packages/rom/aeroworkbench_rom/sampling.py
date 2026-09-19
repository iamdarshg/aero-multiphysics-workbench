"""Bounded, deterministic sampling plans over declared independent variables.

A plan declares the independent variables (with units), a sampling strategy,
a sample count, a seed, and an optional hard budget. Sampling reuses the
existing candidate-generation machinery (``CandidateGenerator``) from
``aeroworkbench_optimization`` rather than re-implementing DOE: the canonical
design space is built from the typed variable contract, and generated
candidates are the sample points.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_optimization.generation import (
    STRATEGIES,
    Candidate,
    CandidateGenerator,
    GenerationRequest,
)

from .errors import MapContractError
from .variables import IndependentVariable, VariableKind

__all__ = [
    "SamplingPlan",
    "design_space_from_variables",
    "plan_from_variables",
]


def _domain(variable: IndependentVariable) -> dict[str, Any]:
    if variable.kind is VariableKind.DISCRETE:
        return {"kind": "discrete", "values": [float(value) for value in variable.values]}
    if variable.kind is VariableKind.INTEGER:
        return {
            "kind": "integer",
            "lower": float(variable.lower),
            "upper": float(variable.upper),
            "step": 1.0,
        }
    return {"kind": "continuous", "lower": float(variable.lower), "upper": float(variable.upper)}


def _base_value(variable: IndependentVariable) -> float:
    if variable.kind is VariableKind.DISCRETE:
        return float(variable.values[0])
    if variable.kind is VariableKind.INTEGER:
        return float(round((variable.lower + variable.upper) / 2.0))
    return (variable.lower + variable.upper) / 2.0


def design_space_from_variables(
    space_id: str, variables: Sequence[IndependentVariable]
) -> dict[str, Any]:
    """Build the canonical design-space document for a set of variables.

    The canonical space is unit-agnostic (declared magnitudes); the declared
    unit stays on the map contract. This is what lets the existing generator
    sample generic units such as angles, temperatures, or speeds.
    """

    if not space_id.strip():
        raise MapContractError("DESIGN_SPACE_ID_REQUIRED")
    if not variables:
        raise MapContractError("SAMPLING_PLAN_NEEDS_VARIABLES")
    names = [variable.name for variable in variables]
    if len(set(names)) != len(names):
        raise MapContractError("SAMPLING_PLAN_DUPLICATE_VARIABLE")
    return {
        "id": space_id,
        "variables": [
            {
                "id": variable.name,
                "kind": variable.kind.value,
                "domain": _domain(variable),
                "baseValue": _base_value(variable),
                "bindings": [{"target": "parameter", "path": variable.name}],
            }
            for variable in variables
        ],
    }


@dataclass(frozen=True, slots=True)
class SamplingPlan:
    """A declared, bounded sampling plan over typed independent variables."""

    plan_id: str
    variables: tuple[IndependentVariable, ...]
    strategy: str = "lhs"
    count: int = 8
    seed: int = 0
    budget: int | None = None

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise MapContractError("SAMPLING_PLAN_NEEDS_ID")
        if not self.variables:
            raise MapContractError("SAMPLING_PLAN_NEEDS_VARIABLES")
        if self.strategy not in STRATEGIES:
            raise MapContractError(f"UNKNOWN_SAMPLING_STRATEGY:{self.strategy}")
        if self.count <= 0:
            raise MapContractError("SAMPLING_COUNT_MUST_BE_POSITIVE")
        if self.budget is not None and self.budget <= 0:
            raise MapContractError("SAMPLING_BUDGET_MUST_BE_POSITIVE")
        if self.strategy in {"grid", "factorial", "permutation"} and self.budget is None:
            raise MapContractError("ENUMERATIVE_STRATEGY_NEEDS_EXPLICIT_BUDGET")

    def design_space(self) -> dict[str, Any]:
        return design_space_from_variables(self.plan_id, self.variables)

    def request(self, *, seed: int | None = None, count: int | None = None) -> GenerationRequest:
        return GenerationRequest(
            strategy=self.strategy,
            count=self.count if count is None else count,
            seed=self.seed if seed is None else seed,
            budget=self.budget,
        )

    def generate(
        self, *, seed: int | None = None, count: int | None = None
    ) -> tuple[Candidate, ...]:
        generator = CandidateGenerator(self.design_space(), self.request(seed=seed, count=count))
        return tuple(generator)

    def sample_points(
        self, *, seed: int | None = None, count: int | None = None
    ) -> tuple[dict[str, float], ...]:
        return tuple(_point(candidate) for candidate in self.generate(seed=seed, count=count))

    def adaptive_points(
        self,
        *,
        exclude: Sequence[Mapping[str, float]] = (),
        round_index: int = 1,
        count: int | None = None,
    ) -> tuple[dict[str, float], ...]:
        """New candidate points for one refinement round, excluding known ones.

        The seed is advanced deterministically by the round index so a repeated
        run reproduces the same refinement sequence, and the emitted count stays
        bounded by the declared count/budget.
        """

        if round_index < 1:
            raise MapContractError("REFINEMENT_ROUND_MUST_BE_POSITIVE")
        wanted = self.count if count is None else count
        generated = self.generate(seed=self.seed + round_index * 1009, count=wanted)
        seen = {_key(exclude_point) for exclude_point in exclude}
        points: list[dict[str, float]] = []
        for candidate in generated:
            point = _point(candidate)
            key = _key(point)
            if key in seen:
                continue
            seen.add(key)
            points.append(point)
        return tuple(points)

    def digest(self) -> str:
        return content_digest(
            {
                "planId": self.plan_id,
                "variables": [
                    {
                        "name": variable.name,
                        "unit": variable.unit,
                        "kind": variable.kind.value,
                        "lower": variable.lower,
                        "upper": variable.upper,
                        "values": list(variable.values),
                    }
                    for variable in self.variables
                ],
                "strategy": self.strategy,
                "count": self.count,
                "seed": self.seed,
                "budget": self.budget,
            }
        )


def plan_from_variables(
    plan_id: str,
    variables: Sequence[IndependentVariable],
    *,
    strategy: str = "lhs",
    count: int = 8,
    seed: int = 0,
    budget: int | None = None,
) -> SamplingPlan:
    return SamplingPlan(
        plan_id=plan_id,
        variables=tuple(variables),
        strategy=strategy,
        count=count,
        seed=seed,
        budget=budget,
    )


def _point(candidate: Candidate) -> dict[str, float]:
    point: dict[str, float] = {}
    for assignment in candidate.assignment:
        if assignment.point_id is not None:
            continue
        value = assignment.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MapContractError(f"NON_NUMERIC_SAMPLE_VALUE:{assignment.variable_id}")
        number = float(value)
        if not isfinite(number):
            raise MapContractError(f"NONFINITE_SAMPLE_VALUE:{assignment.variable_id}")
        point[assignment.variable_id] = number
    if not point:
        raise MapContractError("GENERATED_SAMPLE_HAS_NO_VALUES")
    return point


def _key(point: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((name, round(value, 12)) for name, value in point.items()))
