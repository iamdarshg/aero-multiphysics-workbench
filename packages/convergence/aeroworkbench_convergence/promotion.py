"""Evidence-gated promotion of a candidate to validated-final (GEN 12).

A high-fidelity candidate may only be called validated or final when the whole
scientific evidence chain holds:

* every required participant is present (not deferred, not unavailable),
* every solver converged,
* required mesh and time-step independence passed,
* required physical-closure gates passed,
* field coupling passed,
* the result is inside its validity envelope.

When any gate fails the candidate is still returned as
``incomplete-diagnostic`` with the exact blockers, never as a validated winner.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "PromotionGateResult",
    "PromotionParticipantEvidence",
    "assess_promotion",
    "blocking_order",
]

#: Stable, human-readable gate order used for blocker messages.
blocking_order: tuple[str, ...] = (
    "required-participant-unavailable",
    "required-participant-deferred",
    "solver-nonconverged",
    "validity-envelope-violated",
    "physical-closure-failed",
    "field-coupling-failed",
    "mesh-independence-failed",
    "timestep-independence-failed",
)


@dataclass(frozen=True, slots=True)
class PromotionParticipantEvidence:
    """All scientific gates for one participant of a candidate."""

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

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise ValueError("PROMOTION_PARTICIPANT_ID_REQUIRED")


@dataclass(frozen=True, slots=True)
class PromotionGateResult:
    """Verdict for one candidate, with the unmodified blocker list."""

    candidate_hash: str
    validated_final: bool
    status: str
    blockers: tuple[str, ...]
    reason: str
    evidence: tuple[PromotionParticipantEvidence, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "validatedFinal": self.validated_final,
            "status": self.status,
            "blockers": list(self.blockers),
            "reason": self.reason,
            "participants": [
                {"participantId": item.participant_id, "required": item.required}
                for item in self.evidence
            ],
        }


def _participant_blockers(
    item: PromotionParticipantEvidence,
    *,
    require_mesh_independence: bool,
    require_timestep_independence: bool,
) -> list[str]:
    if not item.required:
        return []
    blockers: list[str] = []
    pid = item.participant_id
    if not item.available:
        blockers.append(f"required-participant-unavailable:{pid}")
    if item.deferred:
        blockers.append(f"required-participant-deferred:{pid}")
    if not item.converged:
        blockers.append(f"solver-nonconverged:{pid}")
    if not item.validity_ok:
        blockers.append(f"validity-envelope-violated:{pid}")
    if not item.closure_passed:
        blockers.append(f"physical-closure-failed:{pid}")
    if not item.field_coupling_passed:
        blockers.append(f"field-coupling-failed:{pid}")
    if require_mesh_independence and item.mesh_independence_passed is not True:
        blockers.append(f"mesh-independence-failed:{pid}")
    if require_timestep_independence and item.timestep_independence_passed is not True:
        blockers.append(f"timestep-independence-failed:{pid}")
    return blockers


def assess_promotion(
    candidate_hash: str,
    evidence: Sequence[PromotionParticipantEvidence],
    *,
    require_mesh_independence: bool = False,
    require_timestep_independence: bool = False,
) -> PromotionGateResult:
    """Return validated-final only when every required gate holds."""

    if not candidate_hash.strip():
        raise ValueError("PROMOTION_CANDIDATE_HASH_REQUIRED")
    if not evidence:
        raise ValueError("PROMOTION_NEEDS_PARTICIPANT_EVIDENCE")
    blockers: list[str] = []
    for item in evidence:
        blockers.extend(
            _participant_blockers(
                item,
                require_mesh_independence=require_mesh_independence,
                require_timestep_independence=require_timestep_independence,
            )
        )
    blockers = sorted(set(blockers), key=lambda token: (blocking_order.index(token.split(":")[0]),
                                                       token))
    validated = not blockers
    status = "validated-final" if validated else "incomplete-diagnostic"
    reason = (
        "all required scientific gates passed"
        if validated
        else f"not validated: {', '.join(blockers)}"
    )
    return PromotionGateResult(
        candidate_hash=candidate_hash,
        validated_final=validated,
        status=status,
        blockers=tuple(blockers),
        reason=reason,
        evidence=tuple(evidence),
    )
