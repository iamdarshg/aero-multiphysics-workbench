"""Explainable promotion policy and fail-closed final validation.

Promotion reuses the shared optimization planner for the signal-driven step and
augments it with the rotating-gas-specific proximity cues. It refuses to
advance onto a native rung whose capability is not probed ready, refuses to buy
a rung the cost budget cannot afford, and never treats an unavailable native
capability as satisfied. Final validation reuses the convergence promotion gate
so a candidate is only ``validated-final`` when every required participant
passes and every required native capability is available.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from typing import Any

from aeroworkbench_convergence import (
    PromotionGateResult,
    PromotionParticipantEvidence,
    assess_promotion,
)
from aeroworkbench_optimization import plan_fidelity

from ..canonical import content_digest
from .features import ArchitectureFeatures
from .ladder import RotatingGasFidelityLadder
from .native import NativeCapabilityGate
from .signals import PromotionSignals

__all__ = [
    "FinalValidation",
    "ParticipantGate",
    "PromotionOutcome",
    "plan_promotion",
    "validate_final",
]


@dataclass(frozen=True, slots=True)
class PromotionOutcome:
    current_rung: str
    target_rung: str
    escalate: bool
    blocked: bool
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    signal_digest: str
    budget_ok: bool
    native_gate_ok: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "currentRung": self.current_rung,
            "targetRung": self.target_rung,
            "escalate": self.escalate,
            "blocked": self.blocked,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
            "signalDigest": self.signal_digest,
            "budgetOk": self.budget_ok,
            "nativeGateOk": self.native_gate_ok,
        }


def _outcome(
    current: str,
    target: str,
    *,
    escalate: bool,
    blocked: bool,
    reasons: Sequence[str],
    blockers: Sequence[str],
    signals: PromotionSignals,
    ladder: RotatingGasFidelityLadder,
    budget_ok: bool,
    native_gate_ok: bool,
) -> PromotionOutcome:
    payload = {
        "current": current,
        "target": target,
        "escalate": escalate,
        "blocked": blocked,
        "reasons": list(reasons),
        "blockers": list(blockers),
        "signals": signals.canonical(),
        "ladder": ladder.digest,
    }
    return PromotionOutcome(
        current,
        target,
        escalate,
        blocked,
        tuple(reasons),
        tuple(blockers),
        content_digest(payload),
        budget_ok,
        native_gate_ok,
    )


def plan_promotion(
    current_rung: str,
    ladder: RotatingGasFidelityLadder,
    signals: PromotionSignals,
    *,
    features: ArchitectureFeatures | None = None,
    requested: Collection[str] = (),
    capability_gate: NativeCapabilityGate | None = None,
    question: str = "rotating-gas-promotion",
) -> PromotionOutcome:
    """Plan one explainable promotion step, failing closed on missing capability."""
    applicable = (
        ladder.rungs if features is None else ladder.applicable(features, requested)
    )
    applicable_ids = tuple(rung.rung_id for rung in applicable)
    if current_rung not in applicable_ids:
        raise ValueError(f"CURRENT_RUNG_NOT_APPLICABLE:{current_rung}")
    if not signals.validity_ok.get(current_rung, True):
        return _outcome(
            current_rung,
            current_rung,
            escalate=False,
            blocked=True,
            reasons=[f"validity failed at {current_rung}"],
            blockers=[f"VALIDITY_FAILED:{current_rung}"],
            signals=signals,
            ladder=ladder,
            budget_ok=True,
            native_gate_ok=True,
        )
    implementations = ladder.implementations(applicable)
    fidelity_signals = signals.to_fidelity_signals(current_rung, question)
    try:
        plan = plan_fidelity(current_rung, implementations, fidelity_signals)
    except ValueError as exc:
        return _outcome(
            current_rung,
            current_rung,
            escalate=False,
            blocked=True,
            reasons=[str(exc)],
            blockers=[str(exc)],
            signals=signals,
            ladder=ladder,
            budget_ok=False,
            native_gate_ok=True,
        )
    target = str(plan.level)
    escalate = bool(plan.escalate)
    reasons = list(plan.reasons)
    if not escalate:
        extra = signals.extra_escalation_reasons()
        if extra:
            current_position = applicable_ids.index(current_rung)
            if current_position + 1 < len(applicable_ids):
                target = applicable_ids[current_position + 1]
                escalate = True
                reasons.extend(f"{reason}; escalate one rank to {target}" for reason in extra)
    budget = signals.cost_budget
    gate = capability_gate if capability_gate is not None else NativeCapabilityGate()
    target_rung = ladder.rung(target)
    budget_ok = target_rung.cost <= budget
    native_gate_ok = (not target_rung.requires_native) or gate.permits_all(
        target_rung.native_capabilities
    )
    if escalate and target != current_rung and target_rung.requires_native:
        missing = [
            capability
            for capability in target_rung.native_capabilities
            if not gate.permits(capability)
        ]
        if missing:
            blockers = [f"NATIVE_CAPABILITY_UNAVAILABLE:{capability}" for capability in missing]
            reasons.extend(
                f"{target_rung.rung_id} requires unavailable native capability {capability}"
                for capability in missing
            )
            return _outcome(
                current_rung,
                current_rung,
                escalate=False,
                blocked=True,
                reasons=reasons,
                blockers=blockers,
                signals=signals,
                ladder=ladder,
                budget_ok=budget_ok,
                native_gate_ok=False,
            )
    if escalate and target != current_rung and not budget_ok:
        return _outcome(
            current_rung,
            current_rung,
            escalate=False,
            blocked=True,
            reasons=[*reasons, f"cost budget {budget:.3g} excludes {target_rung.rung_id}"],
            blockers=[f"COST_BUDGET_EXCLUDED:{target_rung.rung_id}"],
            signals=signals,
            ladder=ladder,
            budget_ok=False,
            native_gate_ok=native_gate_ok,
        )
    return _outcome(
        current_rung,
        target,
        escalate=escalate and target != current_rung,
        blocked=False,
        reasons=reasons,
        blockers=(),
        signals=signals,
        ladder=ladder,
        budget_ok=budget_ok,
        native_gate_ok=native_gate_ok,
    )


@dataclass(frozen=True, slots=True)
class ParticipantGate:
    """Per-participant scientific gates plus its optional native requirement."""

    participant_id: str
    required: bool = True
    available: bool = True
    deferred: bool = False
    converged: bool = True
    validity_ok: bool = True
    closure_passed: bool = True
    field_coupling_passed: bool = True
    mesh_independence_passed: bool | None = None
    timestep_independence_passed: bool | None = None
    native_capability: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise ValueError("PROMOTION_PARTICIPANT_REQUIRED")

    def resolve(self, gate: NativeCapabilityGate | None) -> ParticipantGate:
        """A declared native requirement with no ready capability is unavailable."""
        if self.native_capability is None:
            return self
        permitted = gate is not None and gate.permits(self.native_capability)
        if permitted:
            return self
        return replace(self, available=False)


@dataclass(frozen=True, slots=True)
class FinalValidation:
    candidate_hash: str
    status: str
    validated_final: bool
    blockers: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "status": self.status,
            "validatedFinal": self.validated_final,
            "blockers": list(self.blockers),
            "reason": self.reason,
        }


def validate_final(
    candidate_hash: str,
    participants: Sequence[ParticipantGate],
    *,
    capability_gate: NativeCapabilityGate | None = None,
    require_mesh_independence: bool = False,
    require_timestep_independence: bool = False,
) -> FinalValidation:
    """Fail-closed validated-final gate over every required participant."""
    if not candidate_hash.strip():
        raise ValueError("PROMOTION_CANDIDATE_HASH_REQUIRED")
    if not participants:
        raise ValueError("PROMOTION_NEEDS_PARTICIPANT_EVIDENCE")
    evidence = tuple(
        PromotionParticipantEvidence(
            participant_id=participant.participant_id,
            required=participant.required,
            available=participant.available,
            deferred=participant.deferred,
            converged=participant.converged,
            validity_ok=participant.validity_ok,
            closure_passed=participant.closure_passed,
            field_coupling_passed=participant.field_coupling_passed,
            mesh_independence_passed=participant.mesh_independence_passed,
            timestep_independence_passed=participant.timestep_independence_passed,
        )
        for participant in (item.resolve(capability_gate) for item in participants)
    )
    result: PromotionGateResult = assess_promotion(
        candidate_hash,
        evidence,
        require_mesh_independence=require_mesh_independence,
        require_timestep_independence=require_timestep_independence,
    )
    return FinalValidation(
        candidate_hash,
        str(result.status),
        bool(result.validated_final),
        tuple(str(blocker) for blocker in result.blockers),
        str(result.reason),
    )
