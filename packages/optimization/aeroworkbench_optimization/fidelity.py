"""Choose fidelity from quality history without hiding failed convergence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FidelityDecision:
    level: str
    reason: str
    escalate: bool


def select_fidelity(
    requested: str,
    *,
    quality_history: Sequence[float] = (),
    converged: bool = True,
    allowed: tuple[str, ...] = ("analytical", "reduced", "native"),
) -> FidelityDecision:
    if requested not in allowed:
        raise ValueError("FIDELITY_NOT_ALLOWED")
    if not converged:
        index = min(len(allowed) - 1, allowed.index(requested) + 1)
        escalated = index > allowed.index(requested)
        return FidelityDecision(
            allowed[index], "convergence failed; escalate fidelity", escalated
        )
    if len(quality_history) >= 2 and abs(quality_history[-1] - quality_history[-2]) > 0.05:
        index = min(len(allowed) - 1, allowed.index(requested) + 1)
        escalated = index > allowed.index(requested)
        return FidelityDecision(
            allowed[index], "quality sensitivity exceeded tolerance", escalated
        )
    return FidelityDecision(requested, "requested fidelity accepted", False)
