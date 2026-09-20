"""Airframe adapter for the shared deterministic campaign engine."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import SimpleNamespace
from typing import Any, Protocol

from aeroworkbench_optimization import (
    CampaignBudget,
    CampaignSpec,
    Candidate,
    EvaluationResult,
    FidelityImplementation,
    GenerationRequest,
    InMemoryResultStore,
    PhysicsFlags,
    StudyObjective,
    run_campaign,
)
from aeroworkbench_optimization import CampaignRecord as GenericCampaignRecord

from .synthesis.seeds import VehicleSeed, build_seed_design_space


class MutationStage(StrEnum):
    GEOMETRY = "geometry"
    MASS = "mass"
    AERO = "aero"
    TRIM = "trim"
    VERIFICATION = "verification"


@dataclass(frozen=True, slots=True)
class MutationDecision:
    accepted: bool
    earliest_stage: MutationStage | None
    invalidated_stages: tuple[MutationStage, ...]
    reason: str


class AirframeMutationPolicy:
    @classmethod
    def default(cls) -> AirframeMutationPolicy:
        return cls({"wing_span": MutationStage.GEOMETRY, "wing_area": MutationStage.GEOMETRY,
                    "max_takeoff_mass": MutationStage.MASS})

    def __init__(self, mapping: dict[str, MutationStage]) -> None:
        self.mapping = mapping

    def evaluate(self, changes: dict[str, tuple[float, float]]) -> MutationDecision:
        unknown = next((name for name in changes if name not in self.mapping), None)
        if unknown:
            return MutationDecision(False, None, (), f"UNKNOWN_AIRFRAME_MUTATION:{unknown}")
        if not changes:
            return MutationDecision(True, None, (), "NO_AIRFRAME_MUTATION")
        order = list(MutationStage)
        earliest = min((self.mapping[name] for name in changes), key=order.index)
        return MutationDecision(True, earliest, tuple(order[order.index(earliest):]), "ACCEPTED")


@dataclass(frozen=True, slots=True)
class AirframeCampaignSpec:
    campaign_id: str
    seed: Any
    evaluations: int
    evaluator_identity: str
    generic: CampaignSpec

    @property
    def generic_spec(self) -> CampaignSpec:
        return self.generic


def _seed_space(seed: Any) -> Mapping[str, Any]:
    if isinstance(seed, VehicleSeed):
        return build_seed_design_space(seed)
    if isinstance(seed, Mapping):
        return seed
    space = getattr(seed, "design_space", None)
    if isinstance(space, Mapping):
        return space
    raise TypeError("AIRFRAME_SEED_NEEDS_DESIGN_SPACE")


def _seed_revision(seed: Any) -> str:
    value = getattr(seed, "content_hash", None)
    if isinstance(value, str) and value:
        return value
    return hashlib.sha256(json.dumps(seed, sort_keys=True, default=str).encode()).hexdigest()


def build_airframe_campaign_spec(
    campaign_id: str,
    seed: Any,
    *,
    generation: GenerationRequest,
    objectives: tuple[StudyObjective, ...],
    fidelity_ladder: tuple[FidelityImplementation, ...],
    budget: CampaignBudget | None = None,
) -> AirframeCampaignSpec:
    # The generic stochastic strategies require an explicit sample count. A
    # legacy airframe caller may provide only its bounded evaluation budget;
    # preserve that request without inventing a second generation algorithm.
    if generation.count is None and generation.strategy in {"random", "lhs", "halton", "sobol"}:
        if generation.budget is None:
            raise ValueError("AIRFRAME_STOCHASTIC_GENERATION_NEEDS_COUNT_OR_BUDGET")
        generation = replace(generation, count=generation.budget)
    active_budget = budget or CampaignBudget(max_evaluations=generation.budget)
    generic = CampaignSpec(
        campaign_id=campaign_id,
        base_revision=_seed_revision(seed),
        space=_seed_space(seed),
        generation=generation,
        objectives=objectives,
        fidelity_ladder=fidelity_ladder,
        budget=active_budget,
    )
    evaluations = int(active_budget.max_evaluations or generation.budget or generation.count or 1)
    return AirframeCampaignSpec(campaign_id, seed, evaluations, "", generic)


@dataclass(frozen=True, slots=True)
class CampaignRecord:
    best: Any
    metrics: dict[str, int | float]
    results: tuple[Any, ...]


class GeometryReceiptLike(Protocol):
    validity_state: str
    shape_hash: str
    invalid_reasons: tuple[str, ...]


GeometryRegenerator = Callable[[Candidate, GeometryReceiptLike | None], GeometryReceiptLike]


@dataclass(frozen=True, slots=True)
class AirframeCampaignReceipt:
    record: CampaignRecord
    mutation_decisions: tuple[MutationDecision, ...]
    evaluator_identity: str
    digest: str
    generic_record: GenericCampaignRecord | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {"metrics": self.record.metrics, "evaluatorIdentity": self.evaluator_identity,
                   "results": [getattr(result, "outputs", {}) for result in self.record.results],
                   "mutation": [decision.reason for decision in self.mutation_decisions]}
        return {**payload, "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AirframeCampaignReceipt:
        results = tuple(SimpleNamespace(outputs=dict(item)) for item in payload.get("results", ()))
        record = CampaignRecord(
            results[0] if results else None, dict(payload.get("metrics", {})), results
        )
        canonical = {key: value for key, value in payload.items() if key != "digest"}
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        decisions = tuple(
            MutationDecision(True, None, (), str(reason))
            for reason in payload.get("mutation", ())
        )
        return cls(record, decisions, payload.get("evaluatorIdentity", ""), digest)


class AirframeCampaignSession:
    def __init__(
        self,
        spec: AirframeCampaignSpec,
        evaluator: Callable[[Candidate, str], EvaluationResult],
        *,
        evaluator_identity: str,
        mutation_policy: AirframeMutationPolicy,
        geometry_regenerator: GeometryRegenerator | None = None,
    ) -> None:
        self.spec = spec
        self.evaluator = evaluator
        self.evaluator_identity = evaluator_identity
        self.mutation_policy = mutation_policy
        self.geometry_regenerator = geometry_regenerator
        self._store = InMemoryResultStore()
        self._receipts: dict[str, GeometryReceiptLike] = {}
        self._last_receipt: GeometryReceiptLike | None = None
        self._decisions: dict[str, MutationDecision] = {}

    def _evaluate(self, candidate: Candidate, fidelity: str) -> EvaluationResult:
        if candidate.candidate_hash not in self._decisions:
            changes = {
                mutation.variable_id: (float(mutation.before), float(mutation.after))
                for mutation in candidate.mutations
                if mutation.variable_id in self.mutation_policy.mapping
                and isinstance(mutation.before, (int, float))
                and isinstance(mutation.after, (int, float))
            }
            self._decisions[candidate.candidate_hash] = self.mutation_policy.evaluate(changes)
        if self.geometry_regenerator is not None:
            receipt = self._receipts.get(candidate.candidate_hash)
            if receipt is None:
                receipt = self.geometry_regenerator(candidate, self._last_receipt)
                self._receipts[candidate.candidate_hash] = receipt
                self._last_receipt = receipt
            if receipt.validity_state != "valid":
                reasons = ";".join(receipt.invalid_reasons) or "UNKNOWN_GEOMETRY_INVALIDITY"
                return EvaluationResult(
                    outputs={},
                    flags=PhysicsFlags(converged=False, closure_passed=False, validity_ok=False),
                    fidelity=fidelity,
                    geometry_hash=receipt.shape_hash or None,
                    detail=f"GEOMETRY_INVALID:{reasons}",
                )
            result = self.evaluator(candidate, fidelity)
            return EvaluationResult(
                outputs=result.outputs,
                flags=result.flags,
                fidelity=result.fidelity,
                source=result.source,
                cost=result.cost,
                geometry_hash=receipt.shape_hash or result.geometry_hash,
                signals=result.signals,
                detail=result.detail,
            )
        return self.evaluator(candidate, fidelity)

    def run(self) -> AirframeCampaignReceipt:
        generic_record = run_campaign(
            self.spec.generic,
            self._evaluate,
            store=self._store,
            evaluator_identity=self.evaluator_identity,
        )
        evaluations = tuple(
            SimpleNamespace(
                candidate_hash=item.candidate_hash,
                fidelity=item.fidelity,
                outputs=item.output_dict,
                detail=item.detail,
            )
            for item in generic_record.evaluations
        )
        best = next(
            (item for item in evaluations if item.candidate_hash == generic_record.best), None
        )
        record = CampaignRecord(best, dict(generic_record.metrics), evaluations)
        decisions = tuple(self._decisions.values())
        canonical = {"metrics": record.metrics, "evaluatorIdentity": self.evaluator_identity,
                     "results": [item.outputs for item in evaluations],
                     "mutation": [decision.reason for decision in decisions]}
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return AirframeCampaignReceipt(
            record, decisions, self.evaluator_identity, digest, generic_record
        )

    def resume(self, receipt: AirframeCampaignReceipt) -> AirframeCampaignReceipt:
        if receipt.evaluator_identity != self.evaluator_identity:
            raise ValueError("EVALUATOR_IDENTITY_MISMATCH")
        if receipt.generic_record is None:
            record = CampaignRecord(
                receipt.record.best,
                {"evaluations": 0, "cache_hits": self.spec.evaluations},
                receipt.record.results,
            )
            return AirframeCampaignReceipt(
                record, receipt.mutation_decisions, self.evaluator_identity, receipt.digest
            )
        return self.run()


__all__ = [
    "AirframeCampaignReceipt",
    "AirframeCampaignSession",
    "AirframeMutationPolicy",
    "MutationStage",
    "build_airframe_campaign_spec",
]
