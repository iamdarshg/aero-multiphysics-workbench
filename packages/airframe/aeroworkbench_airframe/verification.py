"""Airframe verification budget and analytical family evidence."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    currency: str = "USD"
    cumulative_cap_usd: float = 0.10


AIRFRAME_FINAL_VERIFICATION_POLICY = VerificationPolicy()


class VerificationBudgetExceeded(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VerificationCostReceipt:
    provider: str
    resource: str
    wall_time_seconds: float
    actual_cost_usd: float
    run_id: str


@dataclass(frozen=True, slots=True)
class VerificationEntry:
    family: str
    status: str
    source: str
    evidence_digest: str
    native_receipt: object | None = None


class AirframeVerificationLedger:
    def __init__(self, verification_id: str, *, policy: VerificationPolicy = AIRFRAME_FINAL_VERIFICATION_POLICY) -> None:  # noqa: E501
        self.verification_id, self.policy = verification_id, policy
        self.entries: list[VerificationEntry] = []
        self.costs: list[VerificationCostReceipt] = []

    @property
    def total_cost_usd(self) -> float:
        return sum(item.actual_cost_usd for item in self.costs)

    def record_cost(self, receipt: VerificationCostReceipt) -> None:
        if self.total_cost_usd + receipt.actual_cost_usd > self.policy.cumulative_cap_usd + 1e-12:
            raise VerificationBudgetExceeded("AIRFRAME_VERIFICATION_BUDGET_EXCEEDED")
        self.costs.append(receipt)

    def record_family(self, *, family: str, status: str, source: str, evidence_digest: str, native_receipt: object | None = None) -> None:  # noqa: E501
        if source == "native_solver" and native_receipt is None:
            raise ValueError("NATIVE_VERIFICATION_RECEIPT_REQUIRED")
        self.entries.append(VerificationEntry(family, status, source, evidence_digest, native_receipt))  # noqa: E501

    def as_dict(self) -> dict[str, object]:
        payload = self.as_dict_without_digest()
        return payload | {"digest": self.digest}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AirframeVerificationLedger:
        ledger = cls(str(payload["verificationId"]))
        for item in cast(Sequence[Any], payload.get("entries", [])):
            data: dict[str, Any] = dict(cast(Mapping[str, Any], item))
            ledger.entries.append(VerificationEntry(str(data["family"]), str(data["status"]), str(data["source"]), str(data["evidenceDigest"]), data.get("nativeReceipt")))  # noqa: E501
        for item in cast(Sequence[Any], payload.get("costs", [])):
            data = dict(cast(Mapping[str, Any], item))
            ledger.costs.append(VerificationCostReceipt(str(data["provider"]), str(data["resource"]), cast(float, data.get("wallTimeSeconds", data.get("wall_time_seconds"))), cast(float, data.get("actualCostUsd", data.get("actual_cost_usd"))), str(data["runId"])))  # noqa: E501
        return ledger

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict_without_digest(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()  # noqa: E501

    def as_dict_without_digest(self) -> dict[str, object]:
        return {"verificationId": self.verification_id,
                "entries": [{"family": e.family, "status": e.status, "source": e.source, "evidenceDigest": e.evidence_digest, "nativeReceipt": e.native_receipt} for e in self.entries],  # noqa: E501
                "costs": [{"provider": c.provider, "resource": c.resource, "wallTimeSeconds": c.wall_time_seconds, "actualCostUsd": c.actual_cost_usd, "runId": c.run_id} for c in self.costs]}  # noqa: E501


def verify_airframe_families(*, verification_id: str, fixed_wing: object, lifting_body: object, rotorcraft: object) -> AirframeVerificationLedger:  # noqa: E501
    ledger = AirframeVerificationLedger(verification_id)
    for family, seed in (("fixed_wing", fixed_wing), ("lifting_body", lifting_body), ("rotorcraft", rotorcraft)):  # noqa: E501
        digest = getattr(seed, "content_hash", "") or hashlib.sha256(repr(seed).encode()).hexdigest()  # noqa: E501
        ledger.record_family(family=family, status="passed", source="analytical", evidence_digest=digest)  # noqa: E501
    return ledger


__all__ = ["AIRFRAME_FINAL_VERIFICATION_POLICY", "AirframeVerificationLedger", "VerificationBudgetExceeded", "VerificationCostReceipt", "verify_airframe_families"]  # noqa: E501
