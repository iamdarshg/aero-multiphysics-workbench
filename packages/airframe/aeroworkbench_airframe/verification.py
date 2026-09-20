"""Fail-closed, staged airframe verification evidence."""
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
    stage: str = "family"
    fidelity: str = "unknown"
    provenance_hash: str = ""
    replay_hash: str = ""
    detail: str = ""


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

    def record_stage(
        self,
        *,
        family: str,
        stage: str,
        status: str,
        source: str,
        fidelity: str,
        evidence_digest: str,
        provenance_hash: str = "",
        replay_hash: str = "",
        detail: str = "",
        native_receipt: object | None = None,
    ) -> None:
        """Record one governed stage; native claims require an observed receipt."""
        if status == "passed" and source in {"unknown", "unavailable"}:
            raise ValueError("PASSED_VERIFICATION_NEEDS_TRUSTED_SOURCE")
        if source == "native_solver" and native_receipt is None:
            raise ValueError("NATIVE_VERIFICATION_RECEIPT_REQUIRED")
        self.entries.append(
            VerificationEntry(
                family, status, source, evidence_digest, native_receipt,
                stage, fidelity, provenance_hash, replay_hash, detail,
            )
        )

    @property
    def passed(self) -> bool:
        return bool(self.entries) and all(
            any(
                entry.family == family and entry.stage == stage and entry.status == "passed"
                for entry in self.entries
            )
            for family in {entry.family for entry in self.entries}
            for stage in _STAGES
        )

    def as_dict(self) -> dict[str, object]:
        payload = self.as_dict_without_digest()
        return payload | {"digest": self.digest}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AirframeVerificationLedger:
        ledger = cls(str(payload["verificationId"]))
        for item in cast(Sequence[Any], payload.get("entries", [])):
            data: dict[str, Any] = dict(cast(Mapping[str, Any], item))
            ledger.entries.append(VerificationEntry(
                str(data["family"]), str(data["status"]), str(data["source"]),
                str(data["evidenceDigest"]), data.get("nativeReceipt"),
                str(data.get("stage", "family")), str(data.get("fidelity", "unknown")),
                str(data.get("provenanceHash", "")), str(data.get("replayHash", "")),
                str(data.get("detail", "")),
            ))
        for item in cast(Sequence[Any], payload.get("costs", [])):
            data = dict(cast(Mapping[str, Any], item))
            ledger.costs.append(VerificationCostReceipt(str(data["provider"]), str(data["resource"]), cast(float, data.get("wallTimeSeconds", data.get("wall_time_seconds"))), cast(float, data.get("actualCostUsd", data.get("actual_cost_usd"))), str(data["runId"])))  # noqa: E501
        return ledger

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict_without_digest(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()  # noqa: E501

    def as_dict_without_digest(self) -> dict[str, object]:
        return {"verificationId": self.verification_id,
                "entries": [{"family": e.family, "stage": e.stage, "status": e.status,
                             "source": e.source,
                             "fidelity": e.fidelity, "evidenceDigest": e.evidence_digest,
                             "provenanceHash": e.provenance_hash, "replayHash": e.replay_hash,
                             "detail": e.detail, "nativeReceipt": e.native_receipt} for e in self.entries],  # noqa: E501
                "costs": [{"provider": c.provider, "resource": c.resource, "wallTimeSeconds": c.wall_time_seconds, "actualCostUsd": c.actual_cost_usd, "runId": c.run_id} for c in self.costs]}  # noqa: E501


_STAGES = (
    "requirements", "synthesis", "campaign", "mass_cg_trim", "aero_rotor",
    "fidelity_promotion", "provenance_replay",
)


def _digest(value: object) -> str:
    for name in ("content_hash", "digest"):
        candidate = getattr(value, name, None)
        if isinstance(candidate, str) and candidate:
            return candidate
    if hasattr(value, "canonical_payload"):
        value = value.canonical_payload()
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _evidence(
    value: object,
    *,
    stage: str,
    family: str,
    ledger: AirframeVerificationLedger,
    native_receipt: object | None = None,
    source_override: str | None = None,
    fidelity_override: str | None = None,
) -> None:
    """Consume an injected receipt/result without treating a seed as its result."""
    digest = _digest(value)
    provenance = getattr(value, "provenance", None)
    provenance_hash = _digest(provenance) if provenance is not None else ""
    replay_hash = getattr(value, "digest", "") if stage in {"campaign", "provenance_replay"} else ""
    source = source_override or str(getattr(value, "source", "analytical"))
    fidelity = fidelity_override or str(getattr(value, "fidelity", "analytical"))
    ledger.record_stage(family=family, stage=stage, status="passed", source=source,
                        fidelity=fidelity, evidence_digest=digest,
                        provenance_hash=provenance_hash, replay_hash=replay_hash,
                        detail="observed evidence", native_receipt=native_receipt)


def verify_airframe_families(*, verification_id: str, fixed_wing: object, lifting_body: object, rotorcraft: object) -> AirframeVerificationLedger:  # noqa: E501
    """Run the bounded local verification matrix; never promote seed bookkeeping."""
    ledger = AirframeVerificationLedger(verification_id)
    families = (
        ("fixed_wing", fixed_wing),
        ("lifting_body", lifting_body),
        ("rotorcraft", rotorcraft),
    )
    for family, item in families:
        seed = getattr(item, "seed", item)
        compiled = next(
            (
                getattr(item, name, None)
                for name in ("requirements", "compiled_requirements")
                if getattr(item, name, None) is not None
            ),
            None,
        )
        if compiled is not None:
            _evidence(compiled, stage="requirements", family=family, ledger=ledger)
        else:
            ledger.record_stage(
                family=family,
                stage="requirements",
                status="unavailable",
                source="unavailable",
                fidelity="none",
                evidence_digest=_digest(seed),
                detail="compiled requirements not supplied",
            )
        if getattr(seed, "content_hash", None):
            _evidence(seed, stage="synthesis", family=family, ledger=ledger)
        else:
            ledger.record_stage(
                family=family,
                stage="synthesis",
                status="unavailable",
                source="unavailable",
                fidelity="none",
                evidence_digest=_digest(seed),
                detail="synthesis receipt not supplied",
            )

        session_factory = getattr(item, "session", None) or getattr(item, "campaign_session", None)
        if callable(session_factory):
            try:
                session = session_factory()
                receipt = session.run() if hasattr(session, "run") else session
                _evidence(receipt, stage="campaign", family=family, ledger=ledger)
            except Exception as exc:  # capability and evaluator failures remain explicit
                ledger.record_stage(
                    family=family,
                    stage="campaign",
                    status="blocked",
                    source="campaign",
                    fidelity="unknown",
                    evidence_digest=_digest(seed),
                    detail=f"campaign blocked: {type(exc).__name__}",
                )
        else:
            ledger.record_stage(
                family=family,
                stage="campaign",
                status="unavailable",
                source="unavailable",
                fidelity="none",
                evidence_digest=_digest(seed),
                detail="generic campaign adapter not supplied",
            )

        for stage, names in (
            ("mass_cg_trim", ("mass_cg_trim", "trim_result")),
            ("aero_rotor", ("coupling_result", "aero_result")),
        ):
            result = next(
                (
                    getattr(item, name, None)
                    for name in names
                    if getattr(item, name, None) is not None
                ),
                None,
            )
            if result is None and stage == "aero_rotor":
                coupling = getattr(item, "couple_rotor_airframe", None)
                if callable(coupling):
                    try:
                        result = coupling()
                    except Exception as exc:
                        ledger.record_stage(
                            family=family,
                            stage=stage,
                            status="blocked",
                            source="coupling",
                            fidelity="unknown",
                            evidence_digest=_digest(seed),
                            detail=f"installed coupling blocked: {type(exc).__name__}",
                        )
                        continue
            if result is not None:
                _evidence(result, stage=stage, family=family, ledger=ledger)
            else:
                ledger.record_stage(
                    family=family,
                    stage=stage,
                    status="unavailable",
                    source="unavailable",
                    fidelity="none",
                    evidence_digest=_digest(seed),
                    detail="trusted result not supplied",
                )

        try:
            from .external_aero.native import probe_any_vspaero_capability
            capability = probe_any_vspaero_capability()
            native_receipt = getattr(item, "native_receipt", None)
            if capability.available and native_receipt is None:
                solver = getattr(item, "solve_vspaero", None)
                if callable(solver):
                    native_receipt = solver(capability)
            if capability.available and native_receipt is not None:
                _evidence(
                    native_receipt,
                    stage="fidelity_promotion",
                    family=family,
                    ledger=ledger,
                    native_receipt=native_receipt,
                    source_override="native_solver",
                    fidelity_override="vspaero",
                )
            else:
                ledger.record_stage(
                    family=family,
                    stage="fidelity_promotion",
                    status="unavailable",
                    source="native_capability",
                    fidelity="vspaero",
                    evidence_digest=_digest(capability.canonical()),
                    detail=capability.detail,
                )
        except Exception as exc:
            ledger.record_stage(
                family=family,
                stage="fidelity_promotion",
                status="blocked",
                source="native_capability",
                fidelity="vspaero",
                evidence_digest=_digest(seed),
                detail=f"VSPAERO capability probe blocked: {type(exc).__name__}",
            )
        ledger.record_stage(
            family=family,
            stage="provenance_replay",
            status="pending",
            source="analytical",
            fidelity="analytical",
            evidence_digest=_digest(seed),
            detail="replay receipt required for promotion",
        )
    return ledger


__all__ = ["AIRFRAME_FINAL_VERIFICATION_POLICY", "AirframeVerificationLedger", "VerificationBudgetExceeded", "VerificationCostReceipt", "VerificationEntry", "verify_airframe_families"]  # noqa: E501
