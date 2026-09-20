"""Mission evaluation: closure, reserves, design objectives, and mission sets.

A mission is an evaluator, not a second design optimizer. This module runs the
propagator, checks mass/fuel/energy/distance/continuity closure and reserve
requirements, and exposes design-objective scalars (energy, fuel, time, range,
endurance, operating cost) for the campaign layer. A weighted mission set
aggregates several missions through the same engine, and the campaign evaluator
seam lets a study vary segment controls as ordinary design variables.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aeroworkbench_optimization.design_space import content_digest
from aeroworkbench_optimization.drivers import StudyObjective
from aeroworkbench_optimization.quality import PhysicsFlags

from .closure import ClosureReport, MissionBalance, evaluate_closure
from .contracts import MissionFidelity, MissionMeta, result_meta
from .errors import ClosureError, MissionContractError, ReserveError
from .performance import PerformanceParticipant
from .propagator import MissionTrace, PropagationPolicy, propagate_mission
from .reserves import ReserveVerdict, evaluate_reserves
from .segments import ControlName, MissionSpec

__all__ = [
    "CampaignEvaluator",
    "MissionResult",
    "MissionSet",
    "MissionSetResult",
    "evaluate_mission_set",
    "mission_campaign_objectives",
    "mission_design_outputs",
    "mission_evaluator",
    "run_mission",
]


@dataclass(frozen=True, slots=True)
class MissionResult:
    """A fully evaluated mission: trace, closure, reserves, and provenance."""

    mission_id: str
    trace: MissionTrace
    closure_report: ClosureReport
    reserve_verdict: ReserveVerdict
    meta: MissionMeta
    final_energy_j: float
    final_specific_energy_j_kg: float
    unit_fuel_cost_per_kg: float = 0.0
    unit_energy_cost_per_j: float = 0.0

    @property
    def closure_passed(self) -> bool:
        return bool(self.closure_report.passed)

    @property
    def reserves_passed(self) -> bool:
        return self.reserve_verdict.passed

    @property
    def degraded(self) -> bool:
        return bool(self.trace.escalations)

    @property
    def valid(self) -> bool:
        return (
            self.closure_passed
            and self.reserves_passed
            and not self.trace.constraint_violations
            and not self.degraded
        )

    @property
    def energy_consumed_j(self) -> float:
        return self.trace.energy_consumed_j

    @property
    def fuel_burned_kg(self) -> float:
        return self.trace.fuel_burned_kg

    @property
    def propulsive_energy_j(self) -> float:
        return self.trace.propulsive_energy_j

    @property
    def time_s(self) -> float:
        return self.trace.final.time_s

    @property
    def distance_m(self) -> float:
        return self.trace.final.distance_m

    @property
    def endurance_s(self) -> float:
        return self.trace.final.time_s

    @property
    def range_m(self) -> float:
        return self.trace.final.distance_m

    @property
    def operating_cost(self) -> float:
        return (
            self.fuel_burned_kg * self.unit_fuel_cost_per_kg
            + self.energy_consumed_j * self.unit_energy_cost_per_j
        )

    def operating_cost_with(self, *, fuel_cost_per_kg: float, energy_cost_per_j: float) -> float:
        return self.fuel_burned_kg * fuel_cost_per_kg + self.energy_consumed_j * energy_cost_per_j

    def design_outputs(self) -> dict[str, float]:
        return mission_design_outputs(self)

    def canonical(self) -> dict[str, Any]:
        return {
            "missionId": self.mission_id,
            "trace": self.trace.canonical(),
            "closure": self.closure_report.as_dict(),
            "reserves": self.reserve_verdict.as_dict(),
            "meta": self.meta.as_dict(),
            "degraded": self.degraded,
            "valid": self.valid,
            "objectives": self.design_outputs(),
        }

    def digest(self) -> str:
        return content_digest(self.canonical())


def run_mission(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    *,
    policy: PropagationPolicy | None = None,
    unit_fuel_cost_per_kg: float = 0.0,
    unit_energy_cost_per_j: float = 0.0,
    raise_on_failure: bool = False,
) -> MissionResult:
    """Propagate a mission and evaluate closure plus declared reserves."""

    trace = propagate_mission(spec, participant, policy=policy)
    vehicle = spec.vehicle
    balance = MissionBalance(
        initial_mass_kg=trace.initial.mass_kg,
        final_mass_kg=trace.final.mass_kg,
        fuel_burned_kg=trace.fuel_burned_kg,
        jettisoned_kg=trace.jettisoned_kg,
        initial_fuel_kg=trace.initial.fuel_kg,
        final_fuel_kg=trace.final.fuel_kg,
        initial_energy_j=trace.initial.stored_energy_j(vehicle),
        final_energy_j=trace.final.stored_energy_j(vehicle),
        stored_energy_consumed_j=trace.final.stored_energy_consumed_j,
        mission_distance_m=trace.final.distance_m,
        segment_distance_sum_m=trace.segment_distance_sum_m,
        max_boundary_discontinuity=trace.max_boundary_discontinuity,
    )
    closure_report = evaluate_closure(spec, balance)
    reserve_verdict = evaluate_reserves(
        spec, trace.final, reserve_duration_s=trace.reserve_duration_s
    )
    checks = {
        "closure": closure_report.passed,
        "reserves": reserve_verdict.passed,
        "constraints": not trace.constraint_violations,
        "no-escalation": not trace.escalations,
        "fidelity-nominal": (
            spec.expected_fidelity is not MissionFidelity.NATIVE
            or trace.fidelity is MissionFidelity.NATIVE
        ),
    }
    meta = result_meta(
        model="mission-propagation",
        inputs={"mission": spec.digest(), "participant": participant.participant_id},
        valid=all(checks.values()),
        checks=checks,
        detail=";".join(trace.constraint_violations),
        assumptions=trace.assumptions,
        fidelity=trace.fidelity,
    )
    result = MissionResult(
        mission_id=spec.mission_id,
        trace=trace,
        closure_report=closure_report,
        reserve_verdict=reserve_verdict,
        meta=meta,
        final_energy_j=trace.final.stored_energy_j(vehicle),
        final_specific_energy_j_kg=trace.final.specific_energy_j_kg(vehicle),
        unit_fuel_cost_per_kg=unit_fuel_cost_per_kg,
        unit_energy_cost_per_j=unit_energy_cost_per_j,
    )
    if raise_on_failure and not result.valid:
        if not reserve_verdict.passed:
            failed = next(item for item in reserve_verdict.reports if not item.passed)
            raise ReserveError(
                f"RESERVE_NOT_MET:{failed.label}:required={failed.required}:achieved={failed.achieved}"
            )
        if not closure_report.passed:
            failed_dim = next(item for item in closure_report.residuals if not item.passed)
            raise ClosureError(f"CLOSURE_FAILED:{failed_dim.dimension}:{failed_dim.residual}")
        raise ClosureError(f"MISSION_INVALID:{spec.mission_id}")
    return result


def mission_design_outputs(result: MissionResult) -> dict[str, float]:
    """Scalars a campaign can optimize directly from a mission result."""

    return {
        "energy_consumed_j": result.energy_consumed_j,
        "fuel_burned_kg": result.fuel_burned_kg,
        "propulsive_energy_j": result.propulsive_energy_j,
        "time_s": result.time_s,
        "distance_m": result.distance_m,
        "range_m": result.range_m,
        "endurance_s": result.endurance_s,
        "operating_cost": result.operating_cost,
        "final_mass_kg": result.trace.final.mass_kg,
        "final_fuel_kg": result.trace.final.fuel_kg,
        "final_energy_j": result.final_energy_j,
        "final_specific_energy_j_kg": result.final_specific_energy_j_kg,
        "valid": 1.0 if result.valid else 0.0,
    }


def mission_campaign_objectives() -> tuple[StudyObjective, ...]:
    """Standard mission-derived study objectives for the campaign layer."""

    return (
        StudyObjective("energy_consumed_j", "minimize", unit="J"),
        StudyObjective("fuel_burned_kg", "minimize", unit="kg"),
        StudyObjective("time_s", "minimize", unit="s"),
        StudyObjective("range_m", "maximize", unit="m"),
        StudyObjective("endurance_s", "maximize", unit="s"),
        StudyObjective("operating_cost", "minimize", unit="cost"),
    )


@dataclass(frozen=True, slots=True)
class CampaignEvaluator:
    """A mission-to-campaign evaluator: design point in, mission outputs out."""

    spec: MissionSpec
    participant: PerformanceParticipant
    controls: Mapping[str, tuple[str, ControlName]]
    policy: PropagationPolicy | None = None
    unit_fuel_cost_per_kg: float = 0.0
    unit_energy_cost_per_j: float = 0.0

    def __call__(
        self, point: Mapping[str, float], fidelity: str
    ) -> tuple[Mapping[str, float], PhysicsFlags]:
        del fidelity
        controls = dict(self.controls)
        segments = []
        for segment in self.spec.segments:
            updated = segment
            for name, (segment_id, control) in controls.items():
                if segment_id == segment.segment_id and name in point:
                    updated = updated.with_control(control, float(point[name]))
            segments.append(updated)
        spec = self.spec.with_segments(segments)
        try:
            result = run_mission(
                spec,
                self.participant,
                policy=self.policy,
                unit_fuel_cost_per_kg=self.unit_fuel_cost_per_kg,
                unit_energy_cost_per_j=self.unit_energy_cost_per_j,
            )
        except MissionContractError:
            return {}, PhysicsFlags(converged=False, closure_passed=False, validity_ok=False)
        outputs = result.design_outputs()
        flags = PhysicsFlags(
            converged=True,
            closure_passed=result.closure_passed,
            validity_ok=result.valid,
        )
        return outputs, flags


def mission_evaluator(
    spec: MissionSpec,
    participant: PerformanceParticipant,
    controls: Mapping[str, tuple[str, ControlName]],
    *,
    policy: PropagationPolicy | None = None,
    unit_fuel_cost_per_kg: float = 0.0,
    unit_energy_cost_per_j: float = 0.0,
) -> CampaignEvaluator:
    return CampaignEvaluator(
        spec=spec,
        participant=participant,
        controls=controls,
        policy=policy,
        unit_fuel_cost_per_kg=unit_fuel_cost_per_kg,
        unit_energy_cost_per_j=unit_energy_cost_per_j,
    )


@dataclass(frozen=True, slots=True)
class MissionSet:
    """A weighted set of independent missions sharing the same evaluation engine."""

    set_id: str
    missions: tuple[MissionSpec, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.set_id.strip():
            raise MissionContractError("MISSION_SET_ID_REQUIRED")
        if not self.missions:
            raise MissionContractError("MISSION_SET_NEEDS_MISSIONS")
        if len(self.missions) != len(self.weights):
            raise MissionContractError("MISSION_SET_WEIGHTS_LENGTH_MISMATCH")
        if any(weight < 0.0 for weight in self.weights) or sum(self.weights) <= 0.0:
            raise MissionContractError("MISSION_SET_WEIGHTS_INVALID")
        identifiers = [mission.mission_id for mission in self.missions]
        if len(identifiers) != len(set(identifiers)):
            raise MissionContractError("MISSION_SET_DUPLICATE_MISSION")


@dataclass(frozen=True, slots=True)
class MissionSetResult:
    """Weighted aggregate of a mission set's design objectives."""

    set_id: str
    results: tuple[MissionResult, ...]
    weights: tuple[float, ...]
    aggregate: Mapping[str, float]
    valid: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "setId": self.set_id,
            "weights": list(self.weights),
            "valid": self.valid,
            "aggregate": dict(sorted(self.aggregate.items())),
            "missions": [result.canonical() for result in self.results],
        }


def evaluate_mission_set(
    mission_set: MissionSet,
    participants: Mapping[str, PerformanceParticipant],
    *,
    policy: PropagationPolicy | None = None,
) -> MissionSetResult:
    """Evaluate each mission through the same engine and aggregate objectives."""

    results: list[MissionResult] = []
    for mission in mission_set.missions:
        participant = participants.get(mission.mission_id)
        if participant is None:
            raise MissionContractError(f"MISSION_SET_MISSING_PARTICIPANT:{mission.mission_id}")
        results.append(run_mission(mission, participant, policy=policy))
    total_weight = sum(mission_set.weights)
    aggregate: dict[str, float] = {}
    for key in results[0].design_outputs():
        if key == "valid":
            continue
        aggregate[key] = sum(
            weight * result.design_outputs()[key]
            for weight, result in zip(mission_set.weights, results, strict=True)
        ) / total_weight
    return MissionSetResult(
        set_id=mission_set.set_id,
        results=tuple(results),
        weights=mission_set.weights,
        aggregate=aggregate,
        valid=all(result.valid for result in results),
    )
