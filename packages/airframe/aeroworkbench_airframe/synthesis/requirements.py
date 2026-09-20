"""Compile typed mission/performance/constraint requirements into a unit-safe set.

The compiler turns declarative requirements (each carrying its declared unit and
operator) into normalized SI bounds with provenance, detects internally
contradictory sets with explicit conflicting requirement identifiers, and fails
closed. It performs no physics: it is the deterministic front door the
physics-based synthesis consumes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any, cast

from aeroworkbench_core.types import FidelityLevel, Provenance, ResultSource

from ..canonical import content_digest, normalize_numbers
from ..units import dimension_of, to_si
from .errors import (
    RequirementCompileError,
    RequirementConflict,
    RequirementConflictError,
)

REQUIREMENTS_MODEL = "airframe-requirements-compiler"
REQUIREMENTS_MODEL_VERSION = "1"

KINDS: tuple[str, ...] = ("mission", "performance", "constraint")
OPERATORS: tuple[str, ...] = ("at_least", "at_most", "equals", "between")

METRIC_DIMENSIONS: dict[str, str] = {
    "payload_mass": "mass",
    "useful_load": "mass",
    "empty_mass": "mass",
    "empty_mass_fraction": "dimensionless",
    "cruise_speed": "velocity",
    "max_speed": "velocity",
    "stall_speed": "velocity",
    "range": "length",
    "endurance": "time",
    "climb_rate": "velocity",
    "climb_gradient": "dimensionless",
    "takeoff_distance": "length",
    "landing_distance": "length",
    "cruise_altitude": "length",
    "service_ceiling": "length",
    "span_limit": "length",
    "diameter_limit": "length",
    "volume_limit": "volume",
    "load_factor": "dimensionless",
    "dynamic_pressure": "pressure",
    "power_limit": "power",
    "energy_limit": "energy",
    "static_margin": "dimensionless",
    "tail_volume_coefficient": "dimensionless",
    "max_lift_coefficient": "dimensionless",
    "aspect_ratio": "dimensionless",
    "min_wall_thickness": "length",
    "packaging_length": "length",
}

METRIC_CATEGORIES: dict[str, str] = {
    "payload_mass": "mass",
    "useful_load": "mass",
    "empty_mass": "mass",
    "empty_mass_fraction": "mass",
    "cruise_speed": "speed",
    "max_speed": "speed",
    "stall_speed": "speed",
    "range": "range",
    "endurance": "endurance",
    "climb_rate": "climb",
    "climb_gradient": "climb",
    "takeoff_distance": "field",
    "landing_distance": "field",
    "cruise_altitude": "altitude",
    "service_ceiling": "altitude",
    "span_limit": "geometry",
    "diameter_limit": "geometry",
    "volume_limit": "geometry",
    "aspect_ratio": "geometry",
    "max_lift_coefficient": "geometry",
    "load_factor": "structural",
    "dynamic_pressure": "structural",
    "power_limit": "power",
    "energy_limit": "power",
    "static_margin": "stability",
    "tail_volume_coefficient": "stability",
    "min_wall_thickness": "manufacturability",
    "packaging_length": "manufacturability",
}

# A metric is not accepted by the compiler unless this catalog says where its
# constraint goes.  ``direct`` metrics are consumed while making an initial
# fixed-wing seed; ``downstream`` metrics are carried as explicit contracts for
# the named verification layer.  This prevents a syntactically valid metric
# from becoming dead data after compilation.
METRIC_ENFORCEMENT_ROUTES: dict[str, tuple[str, str]] = {
    "payload_mass": ("direct", "fixed_wing_synthesis"),
    "useful_load": ("downstream", "mission_campaign"),
    "empty_mass": ("downstream", "mission_campaign"),
    "empty_mass_fraction": ("downstream", "mission_campaign"),
    "cruise_speed": ("direct", "fixed_wing_synthesis"),
    "max_speed": ("direct", "fixed_wing_synthesis"),
    "stall_speed": ("direct", "fixed_wing_synthesis"),
    "range": ("direct", "fixed_wing_synthesis"),
    "endurance": ("downstream", "mission_campaign"),
    "climb_rate": ("direct", "fixed_wing_synthesis"),
    "climb_gradient": ("direct", "fixed_wing_synthesis"),
    "takeoff_distance": ("downstream", "vs06_landing_gear"),
    "landing_distance": ("downstream", "vs06_landing_gear"),
    "cruise_altitude": ("direct", "fixed_wing_synthesis"),
    "service_ceiling": ("downstream", "mission_campaign"),
    "span_limit": ("direct", "fixed_wing_synthesis"),
    "diameter_limit": ("downstream", "manufacturing_constraints"),
    "volume_limit": ("downstream", "manufacturing_constraints"),
    "load_factor": ("downstream", "trim_control"),
    "dynamic_pressure": ("direct", "fixed_wing_synthesis"),
    "power_limit": ("downstream", "mission_campaign"),
    "energy_limit": ("downstream", "mission_campaign"),
    "static_margin": ("downstream", "trim_control"),
    "tail_volume_coefficient": ("direct", "fixed_wing_synthesis"),
    "max_lift_coefficient": ("direct", "fixed_wing_synthesis"),
    "aspect_ratio": ("direct", "fixed_wing_synthesis"),
    "min_wall_thickness": ("downstream", "manufacturing_constraints"),
    "packaging_length": ("downstream", "manufacturing_constraints"),
}

_EXTRA_UNITS: dict[str, tuple[str, float]] = {
    "m3": ("volume", 1.0),
    "L": ("volume", 1e-3),
    "ft3": ("volume", 0.028316846592),
    "J": ("energy", 1.0),
    "kJ": ("energy", 1e3),
    "Wh": ("energy", 3600.0),
    "kWh": ("energy", 3.6e6),
}

_TOLERANCE = 1e-9

_ORDERINGS: tuple[tuple[str, str], ...] = (
    ("stall_speed", "cruise_speed"),
    ("cruise_speed", "max_speed"),
    ("stall_speed", "max_speed"),
    ("cruise_altitude", "service_ceiling"),
)

_COMPILER_ASSUMPTIONS: tuple[str, ...] = (
    "Requirements are compiled and normalized to SI, not verified against a physical model.",
    "Conflicts are reported between declared bounds only; no solver is executed.",
)


def _requirement_dimension(unit: str) -> str:
    try:
        return dimension_of(unit)
    except ValueError:
        extra = _EXTRA_UNITS.get(unit)
        if extra is None:
            raise RequirementCompileError(f"UNKNOWN_REQUIREMENT_UNIT:{unit}") from None
        return extra[0]


def _requirement_to_si(value: float, unit: str) -> float:
    if not isfinite(value):
        raise RequirementCompileError("NONFINITE_REQUIREMENT_VALUE")
    try:
        return to_si(value, unit)
    except ValueError:
        extra = _EXTRA_UNITS.get(unit)
        if extra is None:
            raise RequirementCompileError(f"UNKNOWN_REQUIREMENT_UNIT:{unit}") from None
        return value * extra[1]


def _check_unit(requirement_id: str, unit: str, dimension: str) -> None:
    actual = _requirement_dimension(unit)
    if actual != dimension:
        raise RequirementCompileError(
            f"REQUIREMENT_DIMENSION_MISMATCH:{requirement_id}:{actual}:{dimension}"
        )


@dataclass(frozen=True, slots=True)
class RequirementSpec:
    """A single declared requirement before normalization."""

    requirement_id: str
    kind: str
    metric: str
    operator: str
    value: float | None = None
    unit: str | None = None
    lower: float | None = None
    upper: float | None = None
    rationale: str = ""
    source: str = "user"
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RequirementEnforcementRoute:
    """Explicit destination for one registered requirement metric."""

    metric: str
    mode: str
    target: str

    def canonical(self) -> dict[str, str]:
        return {"metric": self.metric, "mode": self.mode, "target": self.target}


@dataclass(frozen=True, slots=True)
class NormalizedRequirement:
    """A normalized SI requirement with declared provenance."""

    requirement_id: str
    kind: str
    category: str
    metric: str
    operator: str
    dimension: str
    unit: str
    target_si: float | None
    lower_si: float | None
    upper_si: float | None
    rationale: str
    source: str
    assumptions: tuple[str, ...]

    @property
    def enforcement_route(self) -> RequirementEnforcementRoute:
        mode, target = METRIC_ENFORCEMENT_ROUTES[self.metric]
        return RequirementEnforcementRoute(self.metric, mode, target)

    def canonical(self) -> dict[str, object]:
        return cast(
            dict[str, object],
            normalize_numbers(
                {
                    "requirementId": self.requirement_id,
                    "kind": self.kind,
                    "category": self.category,
                    "metric": self.metric,
                    "operator": self.operator,
                    "dimension": self.dimension,
                    "unit": self.unit,
                    "targetSI": self.target_si,
                    "lowerSI": self.lower_si,
                    "upperSI": self.upper_si,
                    "rationale": self.rationale,
                    "source": self.source,
                    "assumptions": list(self.assumptions),
                    "enforcementRoute": self.enforcement_route.canonical(),
                }
            ),
        )

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class CompiledRequirements:
    """Deterministic, unit-safe requirement set plus any detected conflicts."""

    requirements: tuple[NormalizedRequirement, ...]
    conflicts: tuple[RequirementConflict, ...]
    provenance: Provenance
    assumptions: tuple[str, ...] = _COMPILER_ASSUMPTIONS

    @property
    def feasible(self) -> bool:
        return not self.conflicts

    def require_feasible(self) -> None:
        if self.conflicts:
            raise RequirementConflictError(self.conflicts)

    def canonical_payload(self) -> dict[str, object]:
        return cast(
            dict[str, object],
            normalize_numbers(
                {
                    "requirements": [item.canonical() for item in self.requirements],
                    "conflicts": [item.canonical() for item in self.conflicts],
                    "downstreamConstraints": list(self.downstream_constraints()),
                    "feasible": self.feasible,
                    "assumptions": list(self.assumptions),
                    "provenance": self.provenance.model_dump(mode="json"),
                }
            ),
        )

    @property
    def content_hash(self) -> str:
        return content_digest(self.canonical_payload())

    def by_metric(self) -> dict[str, tuple[NormalizedRequirement, ...]]:
        grouped: dict[str, list[NormalizedRequirement]] = {}
        for requirement in self.requirements:
            grouped.setdefault(requirement.metric, []).append(requirement)
        return {metric: tuple(items) for metric, items in grouped.items()}

    @property
    def enforcement_routes(self) -> tuple[RequirementEnforcementRoute, ...]:
        """Unique metric routes retained for downstream campaign assembly."""
        routes: list[RequirementEnforcementRoute] = []
        seen: set[str] = set()
        for requirement in self.requirements:
            if requirement.metric in seen:
                continue
            seen.add(requirement.metric)
            routes.append(requirement.enforcement_route)
        return tuple(routes)

    def downstream_constraints(self) -> tuple[dict[str, object], ...]:
        """Return explicit constraints for consumers outside initial synthesis."""
        return tuple(
            {
                "metric": requirement.metric,
                "requirementIds": [
                    item.requirement_id for item in self.by_metric()[requirement.metric]
                ],
                "mode": requirement.mode,
                "target": requirement.target,
            }
            for requirement in self.enforcement_routes
            if requirement.mode == "downstream"
        )


def _normalize(spec: RequirementSpec) -> NormalizedRequirement:
    requirement_id = spec.requirement_id.strip()
    if not requirement_id:
        raise RequirementCompileError("REQUIREMENT_ID_REQUIRED")
    if spec.kind not in KINDS:
        raise RequirementCompileError(
            f"UNKNOWN_REQUIREMENT_KIND:{requirement_id}:{spec.kind}"
        )
    if spec.metric not in METRIC_DIMENSIONS:
        raise RequirementCompileError(
            f"UNKNOWN_REQUIREMENT_METRIC:{requirement_id}:{spec.metric}"
        )
    if spec.metric not in METRIC_ENFORCEMENT_ROUTES:
        raise RequirementCompileError(
            f"UNSUPPORTED_REQUIREMENT_METRIC:{requirement_id}:{spec.metric}"
        )
    if spec.operator not in OPERATORS:
        raise RequirementCompileError(
            f"UNKNOWN_REQUIREMENT_OPERATOR:{requirement_id}:{spec.operator}"
        )
    dimension = METRIC_DIMENSIONS[spec.metric]
    category = METRIC_CATEGORIES[spec.metric]
    lower: float | None
    upper: float | None
    target: float | None

    if spec.operator == "between":
        if spec.lower is None or spec.upper is None:
            raise RequirementCompileError(
                f"REQUIREMENT_BOUNDS_REQUIRED:{requirement_id}"
            )
        if spec.value is not None or spec.unit is None:
            raise RequirementCompileError(
                f"REQUIREMENT_VALUE_NOT_APPLICABLE:{requirement_id}"
            )
        _check_unit(requirement_id, spec.unit, dimension)
        lower = _requirement_to_si(spec.lower, spec.unit)
        upper = _requirement_to_si(spec.upper, spec.unit)
        if lower > upper:
            raise RequirementCompileError(
                f"REQUIREMENT_BOUNDS_INVERTED:{requirement_id}"
            )
        target = None
    else:
        if spec.value is None or spec.unit is None:
            raise RequirementCompileError(
                f"REQUIREMENT_VALUE_REQUIRED:{requirement_id}"
            )
        if spec.lower is not None or spec.upper is not None:
            raise RequirementCompileError(
                f"REQUIREMENT_BOUNDS_NOT_APPLICABLE:{requirement_id}"
            )
        _check_unit(requirement_id, spec.unit, dimension)
        target = _requirement_to_si(spec.value, spec.unit)
        lower = target if spec.operator in {"at_least", "equals"} else None
        upper = target if spec.operator in {"at_most", "equals"} else None

    return NormalizedRequirement(
        requirement_id=requirement_id,
        kind=spec.kind,
        category=category,
        metric=spec.metric,
        operator=spec.operator,
        dimension=dimension,
        unit=spec.unit if spec.unit is not None else "",
        target_si=target,
        lower_si=lower,
        upper_si=upper,
        rationale=spec.rationale,
        source=spec.source,
        assumptions=spec.assumptions,
    )


def _aggregate(
    requirements: tuple[NormalizedRequirement, ...],
) -> tuple[dict[str, tuple[float, str]], dict[str, tuple[float, str]], dict[str, str]]:
    lower: dict[str, tuple[float, str]] = {}
    upper: dict[str, tuple[float, str]] = {}
    dimensions: dict[str, str] = {}
    for requirement in requirements:
        dimensions[requirement.metric] = requirement.dimension
        if requirement.lower_si is not None:
            current = lower.get(requirement.metric)
            if current is None or requirement.lower_si > current[0]:
                lower[requirement.metric] = (
                    requirement.lower_si,
                    requirement.requirement_id,
                )
        if requirement.upper_si is not None:
            current = upper.get(requirement.metric)
            if current is None or requirement.upper_si < current[0]:
                upper[requirement.metric] = (
                    requirement.upper_si,
                    requirement.requirement_id,
                )
    return lower, upper, dimensions


def detect_conflicts(
    requirements: tuple[NormalizedRequirement, ...],
) -> tuple[RequirementConflict, ...]:
    """Report pairs of bounds that cannot hold simultaneously (deterministic order)."""
    lower, upper, dimensions = _aggregate(requirements)
    conflicts: list[RequirementConflict] = []

    for metric in sorted(set(lower) | set(upper)):
        low = lower.get(metric)
        high = upper.get(metric)
        if low is not None and high is not None and low[0] > high[0] + _TOLERANCE:
            conflicts.append(
                RequirementConflict(
                    metric=metric,
                    dimension=dimensions[metric],
                    lower_si=low[0],
                    upper_si=high[0],
                    requirement_ids=(low[1], high[1]),
                    reason="LOWER_BOUND_EXCEEDS_UPPER_BOUND",
                )
            )

    for low_metric, high_metric in _ORDERINGS:
        low = lower.get(low_metric)
        high = upper.get(high_metric)
        if low is not None and high is not None and low[0] > high[0] + _TOLERANCE:
            dimension = dimensions.get(
                low_metric, dimensions.get(high_metric, "dimensionless")
            )
            conflicts.append(
                RequirementConflict(
                    metric=f"{low_metric}>{high_metric}",
                    dimension=dimension,
                    lower_si=low[0],
                    upper_si=high[0],
                    requirement_ids=(low[1], high[1]),
                    reason=f"{low_metric.upper()}_EXCEEDS_{high_metric.upper()}",
                )
            )

    gradient = lower.get("climb_gradient")
    if gradient is not None and gradient[0] > 1.0 + _TOLERANCE:
        conflicts.append(
            RequirementConflict(
                metric="climb_gradient",
                dimension="dimensionless",
                lower_si=gradient[0],
                upper_si=1.0,
                requirement_ids=(gradient[1],),
                reason="CLIMB_GRADIENT_IMPOSSIBLE",
            )
        )
    load = upper.get("load_factor")
    if load is not None and load[0] < 1.0 - _TOLERANCE:
        conflicts.append(
            RequirementConflict(
                metric="load_factor",
                dimension="dimensionless",
                lower_si=1.0,
                upper_si=load[0],
                requirement_ids=(load[1],),
                reason="LOAD_FACTOR_BELOW_UNITY",
            )
        )
    return tuple(conflicts)


def _provenance(requirements: tuple[NormalizedRequirement, ...]) -> Provenance:
    return Provenance.from_inputs(
        source=ResultSource.ANALYTICAL,
        model=REQUIREMENTS_MODEL,
        model_version=REQUIREMENTS_MODEL_VERSION,
        fidelity=FidelityLevel.ANALYTICAL,
        inputs={"requirements": [item.canonical() for item in requirements]},
        assumptions=_COMPILER_ASSUMPTIONS,
    )


def compile_requirements(
    specs: Iterable[RequirementSpec], *, strict: bool = True
) -> CompiledRequirements:
    """Normalize requirements, detect conflicts, and fail closed when strict."""
    normalized = tuple(
        sorted(
            (_normalize(spec) for spec in specs), key=lambda item: item.requirement_id
        )
    )
    identifiers = [item.requirement_id for item in normalized]
    if len(set(identifiers)) != len(identifiers):
        duplicate = next(
            identifier
            for identifier in identifiers
            if identifiers.count(identifier) > 1
        )
        raise RequirementCompileError(f"DUPLICATE_REQUIREMENT_ID:{duplicate}")
    conflicts = detect_conflicts(normalized)
    compiled = CompiledRequirements(normalized, conflicts, _provenance(normalized))
    if conflicts and strict:
        raise RequirementConflictError(conflicts)
    return compiled


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequirementCompileError(f"REQUIREMENT_VALUE_NOT_NUMBER:{label}")
    return float(value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequirementCompileError("REQUIREMENT_FIELD_NOT_STRING")
    return value


def _assumptions(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RequirementCompileError("REQUIREMENT_ASSUMPTIONS_NOT_ARRAY")
    return tuple(str(item) for item in value)


def requirement_spec_from_payload(payload: Mapping[str, Any]) -> RequirementSpec:
    """Build a :class:`RequirementSpec` from a declarative JSON document."""
    identifier = _optional_string(payload.get("requirementId", payload.get("id")))
    return RequirementSpec(
        requirement_id=identifier or "",
        kind=_optional_string(payload.get("kind")) or "",
        metric=_optional_string(payload.get("metric")) or "",
        operator=_optional_string(payload.get("operator")) or "",
        value=_optional_number(payload.get("value"), "value"),
        unit=_optional_string(payload.get("unit")),
        lower=_optional_number(payload.get("lower"), "lower"),
        upper=_optional_number(payload.get("upper"), "upper"),
        rationale=_optional_string(payload.get("rationale")) or "",
        source=_optional_string(payload.get("source")) or "user",
        assumptions=_assumptions(payload.get("assumptions")),
    )


def compile_requirements_payload(
    payload: Mapping[str, Any], *, strict: bool = True
) -> CompiledRequirements:
    """Compile a full requirement document with a ``requirements`` array."""
    raw = payload.get("requirements")
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise RequirementCompileError("REQUIREMENTS_ARRAY_REQUIRED")
    specs = [
        requirement_spec_from_payload(cast(Mapping[str, Any], item)) for item in raw
    ]
    return compile_requirements(specs, strict=strict)
