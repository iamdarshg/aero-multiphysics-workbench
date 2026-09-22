"""General DOE and optimization through OpenMDAO-compatible declared drivers.

Design variables, objectives, constraints, and operating points come from the
design state (see ``study_from_design_state`` for the DesignRevision-shaped
mapping), never from solver code. Supported drivers:

- parameter sweep (Cartesian grid over the declared variables),
- DOE (deterministic seeded Latin hypercube or full factorial),
- gradient-based optimization (real OpenMDAO ScipyOptimizeDriver/SLSQP),
- derivative-free optimization (real OpenMDAO ScipyOptimizeDriver/COBYLA),
- multiobjective study (weighted scalarization plus an honest Pareto front),
- constrained optimization (constraints declared in the study).

Every evaluation passes through the same physics function; results are
cached by input hash so variants reuse work. Samples that fail the quality
policy carry the explicit ``invalid-sample`` state and never rank.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import cast

from .quality import PhysicsFlags, QualityPolicy, assess_sample

EvaluateFunction = Callable[
    [Mapping[str, float], str], tuple[Mapping[str, float], PhysicsFlags]
]


@dataclass(frozen=True, slots=True)
class DesignVariable:
    name: str
    unit: str
    kind: str  # "continuous" | "integer" | "discrete"
    lower: float
    upper: float
    values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.unit.strip():
            raise ValueError("DESIGN_VARIABLE_NEEDS_NAME_AND_UNIT")
        if self.kind not in {"continuous", "integer", "discrete"}:
            raise ValueError(f"UNKNOWN_VARIABLE_KIND:{self.name}")
        if self.kind == "discrete" and not self.values:
            raise ValueError(f"DISCRETE_VARIABLE_NEEDS_VALUES:{self.name}")
        if self.kind != "discrete" and not self.lower <= self.upper:
            raise ValueError(f"INVALID_VARIABLE_BOUNDS:{self.name}")
        if self.kind == "integer" and (
            int(self.lower) != self.lower or int(self.upper) != self.upper
        ):
            raise ValueError(f"INTEGER_VARIABLE_NEEDS_INTEGER_BOUNDS:{self.name}")


@dataclass(frozen=True, slots=True)
class StudyObjective:
    name: str
    target: str  # "maximize" | "minimize" | "match"
    weight: float = 1.0
    unit: str = "dimensionless"

    def __post_init__(self) -> None:
        if self.target not in {"maximize", "minimize", "match"}:
            raise ValueError(f"UNKNOWN_OBJECTIVE_TARGET:{self.name}")
        if not isfinite(self.weight):
            raise ValueError(f"INVALID_OBJECTIVE_WEIGHT:{self.name}")


@dataclass(frozen=True, slots=True)
class StudyConstraint:
    name: str
    bound: str  # "upper" | "lower" | "equality"
    limit: float
    unit: str = "dimensionless"

    def __post_init__(self) -> None:
        if self.bound not in {"upper", "lower", "equality"}:
            raise ValueError(f"UNKNOWN_CONSTRAINT_BOUND:{self.name}")
        if not isfinite(self.limit):
            raise ValueError(f"INVALID_CONSTRAINT_LIMIT:{self.name}")


@dataclass(frozen=True, slots=True)
class OperatingPointEval:
    name: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class SampleReport:
    point: tuple[tuple[str, float], ...]
    operating_point: str
    outputs: Mapping[str, float]
    state: str  # "valid" | "invalid-sample"
    reasons: tuple[str, ...]
    source: str


@dataclass(frozen=True, slots=True)
class StudyResult:
    samples: tuple[SampleReport, ...]
    best: SampleReport | None
    invalid_count: int
    cache_hits: int
    engine: str
    detail: str


Study = Mapping[str, object]


def _section(
    design_state: Mapping[str, object], *keys: str
) -> tuple[Mapping[str, object], ...]:
    for key in keys:
        value = design_state.get(key)
        if isinstance(value, Mapping):
            return (value,)
        if isinstance(value, (list, tuple)):
            return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _number(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def study_from_design_state(
    design_state: Mapping[str, object],
    variables: tuple[DesignVariable, ...],
) -> dict[str, tuple[object, ...]]:
    """Build a study whose objectives/constraints/operating points come from
    design state (DesignRevision shape), not from solver code."""

    objectives = [
        StudyObjective(
            str(item["name"]),
            str(item["target"]),
            _number(item.get("weight", 1.0), 1.0),
            str(item.get("unit", "dimensionless")),
        )
        for item in _section(design_state, "objectives")
    ]
    constraints = [
        StudyConstraint(
            str(item["name"]),
            str(item["bound"]),
            _number(item.get("limitSI", item.get("limit"))),
            str(item.get("unit", "dimensionless")),
        )
        for item in _section(design_state, "constraints")
    ]
    operating_points = [
        OperatingPointEval(str(item["name"]), 1.0)
        for item in _section(design_state, "operatingPoints", "operating_points")
    ]
    if not objectives:
        raise ValueError("STUDY_NEEDS_OBJECTIVES_FROM_DESIGN_STATE")
    if not operating_points:
        operating_points.append(OperatingPointEval("nominal", 1.0))
    return {
        "variables": variables,
        "objectives": tuple(objectives),
        "constraints": tuple(constraints),
        "operating_points": tuple(operating_points),
    }


def _study_parts(study: Study) -> tuple[
    tuple[DesignVariable, ...],
    tuple[StudyObjective, ...],
    tuple[StudyConstraint, ...],
    tuple[OperatingPointEval, ...],
]:
    try:
        variables = cast("tuple[DesignVariable, ...]", study["variables"])
        objectives = cast("tuple[StudyObjective, ...]", study["objectives"])
        constraints = cast("tuple[StudyConstraint, ...]", study["constraints"])
        operating_points = cast("tuple[OperatingPointEval, ...]", study["operating_points"])
    except (KeyError, TypeError) as exc:
        raise ValueError("STUDY_MISSING_SECTION") from exc
    if not variables or not objectives or not operating_points:
        raise ValueError("STUDY_NEEDS_VARIABLES_OBJECTIVES_AND_POINTS")
    return variables, objectives, constraints, operating_points


def _cache_key(point: Mapping[str, float], operating_point: str) -> str:
    payload = json.dumps(
        {"point": dict(sorted(point.items())), "op": operating_point},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_float(value: object) -> float:
    """Extract a Python float from an OpenMDAO scalar (ndarray or scalar)."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return float(item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValueError("EXPECTED_SCALAR_VALUE")
        return _as_float(value[0])
    return float(value)  # type: ignore[arg-type]


class _StudyCache:
    """Input-hash cache shared across variants within one study run.

    Evaluations are additionally memoized in a process-level registry keyed
    by (evaluator identity, input hash, quality policy, source) so repeated
    studies reuse work instead of re-running physics. The registry is
    bounded by the studies the process actually runs; entries are immutable
    reports.
    """

    _GLOBAL: dict[
        tuple[int, str, int, str], tuple[EvaluateFunction, SampleReport]
    ] = {}

    def __init__(self, evaluate: EvaluateFunction, policy: QualityPolicy, source: str) -> None:
        self._entries: dict[str, SampleReport] = {}
        self._evaluate_id = id(evaluate)
        self._policy_hash = hash(policy)
        self._source = source
        self.hits = 0

    def evaluate(
        self,
        point: Mapping[str, float],
        operating_point: str,
        evaluate: EvaluateFunction,
        policy: QualityPolicy,
        source: str,
    ) -> SampleReport:
        key = _cache_key(point, operating_point)
        hit = self._entries.get(key)
        if hit is not None:
            self.hits += 1
            return hit
        global_key = (self._evaluate_id, key, self._policy_hash, self._source)
        remembered = _StudyCache._GLOBAL.get(global_key)
        if remembered is not None and remembered[0] is evaluate:
            self.hits += 1
            self._entries[key] = remembered[1]
            return remembered[1]
        outputs, flags = evaluate(dict(point), operating_point)
        for name, value in outputs.items():
            if not isfinite(value):
                raise ValueError(f"NONFINITE_STUDY_OUTPUT:{name}")
        verdict = assess_sample(flags, policy)
        report = SampleReport(
            tuple(sorted(point.items())), operating_point, dict(outputs),
            verdict.state, verdict.reasons, source,
        )
        self._entries[key] = report
        # Retaining the callable alongside the report prevents CPython from
        # recycling its ``id()`` and aliasing an unrelated evaluator to this
        # cache entry later in the process.
        _StudyCache._GLOBAL[global_key] = (evaluate, report)
        return report


def _scalarized(outputs: Mapping[str, float], objectives: tuple[StudyObjective, ...]) -> float:
    total = 0.0
    for objective in objectives:
        value = outputs[objective.name]
        total += objective.weight * (value if objective.target == "minimize" else -value)
    return total


def _satisfies_constraints(
    outputs: Mapping[str, float], constraints: tuple[StudyConstraint, ...]
) -> bool:
    for constraint in constraints:
        value = outputs[constraint.name]
        if constraint.bound == "upper" and value > constraint.limit:
            return False
        if constraint.bound == "lower" and value < constraint.limit:
            return False
        if constraint.bound == "equality" and value != constraint.limit:
            return False
    return True


def rank_valid(
    samples: tuple[SampleReport, ...], objectives: tuple[StudyObjective, ...]
) -> tuple[SampleReport, ...]:
    """Rank valid samples by scalarized objective; invalid samples never rank."""
    valid = [sample for sample in samples if sample.state == "valid"]
    return tuple(sorted(valid, key=lambda sample: _scalarized(sample.outputs, objectives)))


def pareto_front(
    samples: tuple[SampleReport, ...], objectives: tuple[StudyObjective, ...]
) -> tuple[SampleReport, ...]:
    """Nondominated valid samples (honest Pareto enumeration, no invention)."""
    valid = [sample for sample in samples if sample.state == "valid"]
    front: list[SampleReport] = []
    for candidate in valid:
        dominated = False
        for other in valid:
            if other is candidate:
                continue
            better_or_equal = True
            strictly_better = False
            for objective in objectives:
                mine, theirs = candidate.outputs[objective.name], other.outputs[objective.name]
                if objective.target == "minimize":
                    if theirs > mine:
                        better_or_equal = False
                    if theirs < mine:
                        strictly_better = True
                else:
                    if theirs < mine:
                        better_or_equal = False
                    if theirs > mine:
                        strictly_better = True
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return tuple(front)


def _grid_values(variable: DesignVariable, resolution: int) -> list[float]:
    if variable.kind == "discrete":
        return list(variable.values)
    if variable.kind == "integer":
        lo, hi = int(variable.lower), int(variable.upper)
        span = hi - lo
        count = min(resolution, span + 1)
        if count <= 1:
            return [float(lo)]
        step = span / (count - 1)
        picked = sorted({round(lo + index * step) for index in range(count)})
        return [float(value) for value in picked]
    if resolution <= 1:
        return [(variable.lower + variable.upper) / 2.0]
    return [
        variable.lower + index * (variable.upper - variable.lower) / (resolution - 1)
        for index in range(resolution)
    ]


def run_sweep(
    study: Study,
    evaluate: EvaluateFunction,
    resolutions: Mapping[str, int],
    *,
    quality: QualityPolicy | None = None,
    source: str = "analytical",
) -> StudyResult:
    """Cartesian parameter sweep over declared variables and operating points."""
    variables, objectives, constraints, operating_points = _study_parts(study)
    policy = quality or QualityPolicy()
    cache = _StudyCache(evaluate, policy, source)
    names = [variable.name for variable in variables]
    grids = {
        variable.name: _grid_values(
            variable, int(resolutions.get(variable.name, 3))
        )
        for variable in variables
    }
    samples: list[SampleReport] = []
    for operating_point in operating_points:
        for combination in itertools.product(*(grids[name] for name in names)):
            point = dict(zip(names, combination, strict=True))
            samples.append(
                cache.evaluate(point, operating_point.name, evaluate, policy, source)
            )
    ranked = rank_valid(tuple(samples), objectives)
    feasible = [sample for sample in ranked if _satisfies_constraints(sample.outputs, constraints)]
    best = feasible[0] if feasible else None
    return StudyResult(
        tuple(samples), best,
        sum(1 for sample in samples if sample.state == "invalid-sample"),
        cache.hits, "openmdao-compatible",
        f"sweep evaluated {len(samples)} samples; best={'none' if best is None else 'found'}",
    )


def run_doe(
    study: Study,
    evaluate: EvaluateFunction,
    *,
    method: str = "lhs",
    n: int = 8,
    seed: int = 0,
    quality: QualityPolicy | None = None,
    source: str = "analytical",
) -> StudyResult:
    """Deterministic DOE: seeded Latin hypercube or full factorial."""
    variables, objectives, constraints, operating_points = _study_parts(study)
    if method not in {"lhs", "factorial"}:
        raise ValueError(f"UNKNOWN_DOE_METHOD:{method}")
    if n <= 0:
        raise ValueError("DOE_NEEDS_POSITIVE_SAMPLES")
    policy = quality or QualityPolicy()
    cache = _StudyCache(evaluate, policy, source)
    points: list[dict[str, float]] = []
    if method == "factorial":
        grids = {variable.name: _grid_values(variable, n) for variable in variables}
        names = [variable.name for variable in variables]
        for combination in itertools.product(*(grids[name] for name in names)):
            points.append(dict(zip(names, combination, strict=True)))
    else:
        import random

        rng = random.Random(seed)
        for index in range(n):
            point: dict[str, float] = {}
            for variable in variables:
                if variable.kind == "discrete":
                    point[variable.name] = variable.values[index % len(variable.values)]
                    continue
                low, high = variable.lower, variable.upper
                strata = (index + rng.random()) / n
                value = low + strata * (high - low)
                point[variable.name] = float(round(value)) if variable.kind == "integer" else value
            points.append(point)
    samples: list[SampleReport] = []
    for operating_point in operating_points:
        for point in points:
            samples.append(
                cache.evaluate(point, operating_point.name, evaluate, policy, source)
            )
    ranked = rank_valid(tuple(samples), objectives)
    feasible = [sample for sample in ranked if _satisfies_constraints(sample.outputs, constraints)]
    best = feasible[0] if feasible else None
    return StudyResult(
        tuple(samples), best,
        sum(1 for sample in samples if sample.state == "invalid-sample"),
        cache.hits, "openmdao-compatible",
        f"doe/{method} evaluated {len(samples)} samples",
    )


def run_optimize(
    study: Study,
    evaluate: EvaluateFunction,
    *,
    driver: str = "slsqp",
    max_iter: int = 50,
    quality: QualityPolicy | None = None,
    source: str = "analytical",
) -> StudyResult:
    """Constrained optimization with a real OpenMDAO driver.

    ``slsqp`` is gradient-based (finite-difference totals), ``cobyla`` is
    derivative-free. Integer/discrete variables fail closed here: they need
    the enumerative sweep/DOE drivers. Multiple operating points aggregate
    into one scalarized objective; invalid physics samples are recorded but
    never rank.
    """
    import openmdao.api as om  # function-local: keeps module import light

    variables, objectives, constraints, operating_points = _study_parts(study)
    if driver not in {"slsqp", "cobyla"}:
        raise ValueError(f"UNKNOWN_OPTIMIZER:{driver}")
    if max_iter <= 0:
        raise ValueError("OPTIMIZER_NEEDS_POSITIVE_ITERATIONS")
    for variable in variables:
        if variable.kind != "continuous":
            raise ValueError(
                f"INTEGER_VAR_NEEDS_ENUMERATIVE_DRIVER:{variable.name}"
            )
    policy = quality or QualityPolicy()
    cache = _StudyCache(evaluate, policy, source)
    ledger: list[SampleReport] = []

    def aggregate(point: Mapping[str, float]) -> tuple[float, list[float]]:
        total = 0.0
        constraint_values: list[float] = []
        for operating_point in operating_points:
            report = cache.evaluate(dict(point), operating_point.name, evaluate, policy, source)
            ledger.append(report)
            if report.state != "valid":
                total += operating_point.weight * 1e12
                constraint_values.extend(1e12 for _ in constraints)
                continue
            total += operating_point.weight * _scalarized(report.outputs, objectives)
            for constraint in constraints:
                value = report.outputs[constraint.name]
                if constraint.bound == "upper":
                    constraint_values.append(value - constraint.limit)
                elif constraint.bound == "lower":
                    constraint_values.append(constraint.limit - value)
                else:
                    constraint_values.append(value - constraint.limit)
        return total, constraint_values

    safe_names = {variable.name: f"x_{index}" for index, variable in enumerate(variables)}

    class _StudyComp(om.ExplicitComponent):  # type: ignore[misc]
        def setup(self) -> None:
            for variable in variables:
                self.add_input(
                    safe_names[variable.name],
                    val=(variable.lower + variable.upper) / 2.0,
                )
            self.add_output("objective", val=0.0)
            for index in range(len(constraints) * len(operating_points)):
                self.add_output(f"con_{index}", val=0.0)
            self.declare_partials("*", "*", method="fd")

        def compute(self, inputs: object, outputs: object) -> None:
            point = {
                variable.name: _as_float(inputs[safe_names[variable.name]])  # type: ignore[index]
                for variable in variables
            }
            total, constraint_values = aggregate(point)
            outputs["objective"] = total  # type: ignore[index]
            for index, value in enumerate(constraint_values):
                outputs[f"con_{index}"] = value  # type: ignore[index]

    problem = om.Problem(reports=False)
    model = problem.model
    indep = om.IndepVarComp()
    for variable in variables:
        indep.add_output(
            safe_names[variable.name],
            val=(variable.lower + variable.upper) / 2.0,
        )
    model.add_subsystem("design_vars", indep, promotes_outputs=list(safe_names.values()))
    model.add_subsystem("study", _StudyComp(), promotes_inputs=list(safe_names.values()))
    for variable in variables:
        model.add_design_var(
            f"design_vars.{safe_names[variable.name]}",
            lower=variable.lower,
            upper=variable.upper,
        )
    model.add_objective("study.objective")
    position = 0
    for _ in operating_points:
        for constraint in constraints:
            name = f"study.con_{position}"
            if constraint.bound == "upper":
                model.add_constraint(name, upper=0.0)
            elif constraint.bound == "lower":
                model.add_constraint(name, lower=0.0)
            else:
                model.add_constraint(name, equals=0.0)
            position += 1
    problem.driver = om.ScipyOptimizeDriver()
    problem.driver.options["optimizer"] = "SLSQP" if driver == "slsqp" else "COBYLA"
    problem.driver.options["maxiter"] = max_iter
    problem.driver.options["disp"] = False
    problem.setup()
    problem.run_driver()
    ranked = rank_valid(tuple(ledger), objectives)
    feasible = [sample for sample in ranked if _satisfies_constraints(sample.outputs, constraints)]
    best = feasible[0] if feasible else None
    engine = f"openmdao/ScipyOptimizeDriver({'SLSQP' if driver == 'slsqp' else 'COBYLA'})"
    return StudyResult(
        tuple(ledger), best,
        sum(1 for sample in ledger if sample.state == "invalid-sample"),
        cache.hits, engine,
        f"{engine} finished; {len(ledger)} evaluations; best={'none' if best is None else 'found'}",
    )
