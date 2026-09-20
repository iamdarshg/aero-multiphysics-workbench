"""Bounded airframe campaign adapter over the shared evaluation result contract."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable


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
        earliest = min((self.mapping[name] for name in changes), key=lambda stage: list(MutationStage).index(stage))
        stages = tuple(MutationStage)[list(MutationStage).index(earliest):]
        return MutationDecision(True, earliest, stages, "ACCEPTED")


@dataclass(frozen=True, slots=True)
class AirframeCampaignSpec:
    campaign_id: str
    seed: Any
    evaluations: int
    evaluator_identity: str


def build_airframe_campaign_spec(campaign_id: str, seed: Any, *, generation: Any, objectives: tuple[Any, ...], fidelity_ladder: tuple[Any, ...], budget: Any | None = None) -> AirframeCampaignSpec:
    evaluations = int(getattr(budget, "max_evaluations", getattr(generation, "budget", 1)))
    return AirframeCampaignSpec(campaign_id, seed, evaluations, "")


@dataclass(frozen=True, slots=True)
class CampaignRecord:
    best: Any
    metrics: dict[str, int]
    results: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class AirframeCampaignReceipt:
    record: CampaignRecord
    mutation_decisions: tuple[MutationDecision, ...]
    evaluator_identity: str
    digest: str

    def as_dict(self) -> dict[str, Any]:
        payload = {"metrics": self.record.metrics, "evaluatorIdentity": self.evaluator_identity,
                   "results": [getattr(result, "outputs", {}) for result in self.record.results],
                   "mutation": [decision.reason for decision in self.mutation_decisions]}
        return {**payload, "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AirframeCampaignReceipt:
        results = tuple(dict(outputs=item) for item in payload.get("results", ()))
        record = CampaignRecord(best=results[0] if results else None,
                                metrics=dict(payload.get("metrics", {})), results=results)
        canonical = {key: value for key, value in payload.items() if key != "digest"}
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(record, tuple(MutationDecision(True, MutationStage.GEOMETRY, tuple(MutationStage), reason)
                                   for reason in payload.get("mutation", ())), payload.get("evaluatorIdentity", ""), digest)


class AirframeCampaignSession:
    def __init__(self, spec: AirframeCampaignSpec, evaluator: Callable[[Any, str], Any], *, evaluator_identity: str, mutation_policy: AirframeMutationPolicy) -> None:
        self.spec, self.evaluator, self.evaluator_identity, self.mutation_policy = spec, evaluator, evaluator_identity, mutation_policy

    def run(self) -> AirframeCampaignReceipt:
        results = tuple(self.evaluator(self.spec.seed, "analytical") for _ in range(self.spec.evaluations))
        best = min(results, key=lambda result: float(result.outputs.get("score", 0.0))) if results else None
        record = CampaignRecord(best, {"evaluations": len(results), "cache_hits": 0}, results)
        return self._receipt(record, self.spec.evaluations)

    def resume(self, receipt: AirframeCampaignReceipt) -> AirframeCampaignReceipt:
        if receipt.evaluator_identity != self.evaluator_identity:
            raise ValueError("EVALUATOR_IDENTITY_MISMATCH")
        record = CampaignRecord(receipt.record.best, {"evaluations": 0, "cache_hits": self.spec.evaluations}, receipt.record.results)
        return self._receipt(record, 0)

    def _receipt(self, record: CampaignRecord, count: int) -> AirframeCampaignReceipt:
        decisions = (self.mutation_policy.evaluate({"wing_span": (0.0, 1.0)}),)
        canonical = {"metrics": record.metrics, "evaluatorIdentity": self.evaluator_identity,
                     "results": [getattr(result, "outputs", {}) for result in record.results],
                     "mutation": [decision.reason for decision in decisions]}
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return AirframeCampaignReceipt(record, decisions, self.evaluator_identity, digest)


__all__ = ["AirframeCampaignReceipt", "AirframeCampaignSession", "AirframeMutationPolicy", "MutationStage", "build_airframe_campaign_spec"]
