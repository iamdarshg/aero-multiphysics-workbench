"""Automatic higher-fidelity escalation from measured aeroacoustic cues.

Instability proximity, thermoacoustic growth, and structural resonance
separation are mapped onto the shared fidelity planner's signals, so a
near-instability or near-resonance condition requests the next applicable rung
without any product-specific rules. Native rungs are capability-gated and fail
closed; an unaffordable rung is never bought silently.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_optimization import plan_fidelity

from ..canonical import content_digest
from ..fidelity.features import ArchitectureFeatures
from ..fidelity.native import NativeCapabilityGate
from ..fidelity.signals import PromotionSignals
from .coupling import StructuralHandoff
from .errors import AcousticInputError
from .instability import InstabilityIndicators
from .spectra import AeroacousticLadder
from .thermoacoustics import ThermoacousticResult

__all__ = [
    "AcousticPromotion",
    "acoustic_promotion_signals",
    "plan_acoustic_escalation",
]


@dataclass(frozen=True, slots=True)
class AcousticPromotion:
    """One explainable aeroacoustic promotion step."""

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


def _digest(
    current: str,
    target: str,
    ladder: AeroacousticLadder,
    signals: PromotionSignals,
    reasons: Sequence[str],
    blockers: Sequence[str],
) -> str:
    return content_digest(
        {
            "current": current,
            "target": target,
            "ladder": ladder.digest,
            "signals": signals.canonical(),
            "reasons": list(reasons),
            "blockers": list(blockers),
        }
    )


def acoustic_promotion_signals(
    *,
    instability: InstabilityIndicators | None = None,
    thermoacoustic: ThermoacousticResult | None = None,
    resonance: StructuralHandoff | None = None,
    resonance_reference_hz: float = 1000.0,
    cost_budget: float = 100.0,
    required_capability: str | None = None,
) -> PromotionSignals:
    """Map measured aeroacoustic cues onto the shared fidelity-planner signals."""

    choke_stall_surge_proximity = 1.0
    model_disagreement = 0.0
    resonance_proximity = 1.0
    capability = required_capability
    if instability is not None:
        signal = instability.promotion_signal()
        choke_stall_surge_proximity = float(signal["choke_stall_surge_proximity"])
        if capability is None:
            capability = signal["required_capability"]
    if thermoacoustic is not None:
        signal = thermoacoustic.promotion_signal()
        model_disagreement = float(signal["model_disagreement"])
        if capability is None:
            capability = signal["required_capability"]
    if resonance is not None:
        signal = resonance.fidelity_signal(reference_hz=resonance_reference_hz)
        resonance_proximity = float(signal["resonance_proximity"])
        if capability is None:
            capability = signal["required_capability"]
    return PromotionSignals(
        model_disagreement=model_disagreement,
        choke_stall_surge_proximity=choke_stall_surge_proximity,
        resonance_proximity=resonance_proximity,
        cost_budget=cost_budget,
        required_capability=capability,
    )


def plan_acoustic_escalation(
    current_rung: str,
    ladder: AeroacousticLadder,
    signals: PromotionSignals,
    *,
    features: ArchitectureFeatures | None = None,
    requested: Sequence[str] = (),
    capability_gate: NativeCapabilityGate | None = None,
    question: str = "aeroacoustic-promotion",
) -> AcousticPromotion:
    """Plan one aeroacoustic promotion step, failing closed on missing capability."""

    applicable = ladder.rungs if features is None else ladder.applicable(features, requested)
    implementations = ladder.implementations(applicable)
    applicable_ids = tuple(item.name for item in implementations)
    if current_rung not in applicable_ids:
        raise AcousticInputError(f"CURRENT_RUNG_NOT_APPLICABLE:{current_rung}")
    plan = plan_fidelity(
        current_rung, implementations, signals.to_fidelity_signals(current_rung, question)
    )
    target = plan.level
    escalate = plan.escalate
    reasons = list(plan.reasons)
    if not escalate:
        extra = signals.extra_escalation_reasons()
        if extra:
            position = applicable_ids.index(current_rung)
            if position + 1 < len(applicable_ids):
                target = applicable_ids[position + 1]
                escalate = True
                reasons.extend(f"{reason}; escalate one rank to {target}" for reason in extra)
    gate = capability_gate if capability_gate is not None else NativeCapabilityGate()
    target_rung = ladder.rung(target)
    budget_ok = target_rung.cost <= signals.cost_budget
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
            digest = _digest(current_rung, current_rung, ladder, signals, reasons, blockers)
            return AcousticPromotion(
                current_rung,
                current_rung,
                escalate=False,
                blocked=True,
                reasons=tuple(reasons),
                blockers=tuple(blockers),
                signal_digest=digest,
                budget_ok=budget_ok,
                native_gate_ok=False,
            )
    if escalate and target != current_rung and not budget_ok:
        blockers = [f"COST_BUDGET_EXCLUDED:{target_rung.rung_id}"]
        reasons.append(f"cost budget {signals.cost_budget:.3g} excludes {target_rung.rung_id}")
        digest = _digest(current_rung, current_rung, ladder, signals, reasons, blockers)
        return AcousticPromotion(
            current_rung,
            current_rung,
            escalate=False,
            blocked=True,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
            signal_digest=digest,
            budget_ok=False,
            native_gate_ok=native_gate_ok,
        )
    digest = _digest(current_rung, target, ladder, signals, reasons, ())
    return AcousticPromotion(
        current_rung,
        target,
        escalate=escalate and target != current_rung,
        blocked=False,
        reasons=tuple(reasons),
        blockers=(),
        signal_digest=digest,
        budget_ok=budget_ok,
        native_gate_ok=native_gate_ok,
    )
