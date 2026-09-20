"""Typed, fail-closed adapters for compiled downstream airframe requirements.

The adapters consume observations produced by an actual campaign stage. They do
not synthesize missing values: an absent adapter or observation is an explicit
unsupported finding and makes the campaign infeasible.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .synthesis.requirements import CompiledRequirements, NormalizedRequirement


@dataclass(frozen=True, slots=True)
class ConstraintObservation:
    """A SI value emitted by a named downstream consumer."""

    metric: str
    value_si: float
    source: str = "consumer"


@dataclass(frozen=True, slots=True)
class ConstraintFinding:
    """Evidence for one hard requirement evaluation."""

    requirement_ids: tuple[str, ...]
    metric: str
    consumer_id: str | None
    status: str
    passed: bool
    value_si: float | None
    margin: float | None
    source: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation:
    """Campaign-level downstream constraint evidence."""

    findings: tuple[ConstraintFinding, ...]

    @property
    def feasible(self) -> bool:
        return all(finding.status == "passed" for finding in self.findings)

    @property
    def campaign_status(self) -> str:
        return "campaign-feasible" if self.feasible else "campaign-infeasible"

    def canonical(self) -> dict[str, object]:
        return {
            "campaignStatus": self.campaign_status,
            "findings": [
                {
                    "requirementIds": list(finding.requirement_ids),
                    "metric": finding.metric,
                    "consumerId": finding.consumer_id,
                    "status": finding.status,
                    "passed": finding.passed,
                    "valueSI": finding.value_si,
                    "margin": finding.margin,
                    "source": finding.source,
                    "detail": finding.detail,
                }
                for finding in self.findings
            ],
        }


@dataclass(frozen=True, slots=True)
class DownstreamConstraintAdapter:
    """Typed consumer contract for one registered downstream metric."""

    metric: str
    consumer_id: str
    read: Callable[[ConstraintObservation], float]


def _read_observation(observation: ConstraintObservation, metric: str) -> float:
    if observation.metric != metric:
        raise ValueError(f"CONSTRAINT_OBSERVATION_METRIC_MISMATCH:{metric}")
    if not isfinite(observation.value_si):
        raise ValueError(f"NONFINITE_CONSTRAINT_OBSERVATION:{metric}")
    return observation.value_si


def _adapter(metric: str, target: str) -> DownstreamConstraintAdapter:
    def reader(observation: ConstraintObservation) -> float:
        return _read_observation(observation, metric)

    return DownstreamConstraintAdapter(
        metric=metric,
        consumer_id=f"{target}:{metric}",
        read=reader,
    )


# Every downstream route has a concrete consumer identity. The value still has
# to be supplied by that consumer at evaluation time; no default is permitted.
DOWNSTREAM_CONSTRAINT_ADAPTERS: dict[str, DownstreamConstraintAdapter] = {
    metric: _adapter(metric, target)
    for metric, (mode, target) in {
        "useful_load": ("downstream", "mission_campaign"),
        "empty_mass": ("downstream", "mission_campaign"),
        "empty_mass_fraction": ("downstream", "mission_campaign"),
        "endurance": ("downstream", "mission_campaign"),
        "takeoff_distance": ("downstream", "vs06_landing_gear"),
        "landing_distance": ("downstream", "vs06_landing_gear"),
        "service_ceiling": ("downstream", "mission_campaign"),
        "diameter_limit": ("downstream", "manufacturing_constraints"),
        "volume_limit": ("downstream", "manufacturing_constraints"),
        "load_factor": ("downstream", "trim_control"),
        "power_limit": ("downstream", "mission_campaign"),
        "energy_limit": ("downstream", "mission_campaign"),
        "static_margin": ("downstream", "trim_control"),
        "min_wall_thickness": ("downstream", "manufacturing_constraints"),
        "packaging_length": ("downstream", "manufacturing_constraints"),
    }.items()
    if mode == "downstream"
}


def _margin(requirements: tuple[NormalizedRequirement, ...], value: float) -> float:
    margins: list[float] = []
    for requirement in requirements:
        if requirement.lower_si is not None:
            margins.append(value - requirement.lower_si)
        if requirement.upper_si is not None:
            margins.append(requirement.upper_si - value)
    return min(margins) if margins else float("nan")


def evaluate_downstream_requirements(
    compiled: CompiledRequirements,
    observations: dict[str, ConstraintObservation],
) -> ConstraintEvaluation:
    """Evaluate all downstream routes and fail closed for missing consumers."""
    findings: list[ConstraintFinding] = []
    for metric in sorted(
        {
            item.metric
            for item in compiled.requirements
            if item.enforcement_route.mode == "downstream"
        }
    ):
        requirements = tuple(item for item in compiled.requirements if item.metric == metric)
        adapter = DOWNSTREAM_CONSTRAINT_ADAPTERS.get(metric)
        if adapter is None:
            findings.append(
                ConstraintFinding(
                    tuple(item.requirement_id for item in requirements),
                    metric,
                    None,
                    "unsupported",
                    False,
                    None,
                    None,
                    None,
                    f"UNSUPPORTED_CONSTRAINT_CONSUMER:{metric}",
                )
            )
            continue
        observation = observations.get(metric)
        if observation is None:
            findings.append(
                ConstraintFinding(
                    tuple(item.requirement_id for item in requirements),
                    metric,
                    adapter.consumer_id,
                    "unsupported",
                    False,
                    None,
                    None,
                    None,
                    f"MISSING_CONSTRAINT_OBSERVATION:{metric}",
                )
            )
            continue
        try:
            value = adapter.read(observation)
        except (TypeError, ValueError) as error:
            findings.append(
                ConstraintFinding(
                    tuple(item.requirement_id for item in requirements),
                    metric,
                    adapter.consumer_id,
                    "unsupported",
                    False,
                    None,
                    None,
                    observation.source,
                    str(error),
                )
            )
            continue
        margin = _margin(requirements, value)
        passed = margin >= -1e-9
        findings.append(
            ConstraintFinding(
                tuple(item.requirement_id for item in requirements),
                metric,
                adapter.consumer_id,
                "passed" if passed else "violated",
                passed,
                value,
                margin,
                observation.source,
                f"{metric} {'satisfies' if passed else 'violates'} requirement; margin={margin}",
            )
        )
    return ConstraintEvaluation(tuple(findings))
