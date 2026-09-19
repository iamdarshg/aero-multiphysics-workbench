"""System use: consume a map only inside its validity, or escalate fidelity.

Cycle, off-design, control, and mission solvers consume a map's surrogate
prediction only inside the declared validity domain and only when the map is
trusted (validated). Outside validity the query is rejected or triggers a
fidelity escalation; an unvalidated map never silently becomes trusted.
Escalation reuses the optimization fidelity planner rather than duplicating it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aeroworkbench_optimization.planner import (
    FidelityImplementation,
    FidelityPlan,
    FidelitySignals,
    plan_fidelity,
)

from .contracts import ExtrapolationPolicy, MapFidelity
from .errors import ExtrapolationError, ValidationError
from .map import PerformanceMap
from .validation import TrustDecision, map_trust

__all__ = ["MapConsumption", "consume_map", "fidelity_escalation"]

_DEFAULT_LADDER: tuple[FidelityImplementation, ...] = (
    FidelityImplementation("surrogate", 0, 0.0),
    FidelityImplementation("native", 1, 1.0),
)


@dataclass(frozen=True, slots=True)
class MapConsumption:
    """The result of a system consuming a map at one operating point."""

    outputs: Mapping[str, float]
    uncertainty: Mapping[str, float]
    source: MapFidelity
    trusted: bool
    inside_validity: bool
    extrapolated: bool
    requires_escalation: bool
    escalation: FidelityPlan | None
    reasons: tuple[str, ...]
    map_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", {str(k): float(v) for k, v in self.outputs.items()})
        object.__setattr__(
            self, "uncertainty", {str(k): float(v) for k, v in self.uncertainty.items()}
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "outputs": dict(sorted(self.outputs.items())),
            "uncertainty": dict(sorted(self.uncertainty.items())),
            "source": self.source.value,
            "trusted": self.trusted,
            "insideValidity": self.inside_validity,
            "extrapolated": self.extrapolated,
            "requiresEscalation": self.requires_escalation,
            "reasons": list(self.reasons),
            "mapDigest": self.map_digest,
            "escalation": None
            if self.escalation is None
            else {
                "level": self.escalation.level,
                "escalate": self.escalation.escalate,
                "reasons": list(self.escalation.reasons),
                "inputHash": self.escalation.input_hash,
            },
        }


def fidelity_escalation(
    performance_map: PerformanceMap,
    *,
    uncertainty: Mapping[str, float],
    inside_validity: bool,
    trusted: bool,
    ladder: Sequence[FidelityImplementation] = (),
) -> FidelityPlan:
    """Ask the shared fidelity planner for the next implementation."""

    rungs = tuple(ladder) if ladder else _DEFAULT_LADDER
    current = rungs[0].name
    validity_ok = {rung.name: rung.rank > 0 for rung in rungs}
    validity_ok[current] = trusted and inside_validity
    budget = sum(rung.cost for rung in rungs) + 1.0
    signals = FidelitySignals(
        question=f"consume:{performance_map.map_id}",
        maturity=1.0,
        constraint_margin=1.0,
        disagreement=max(uncertainty.values(), default=0.0),
        sensitivity=0.0,
        convergence_difficulty=0.0,
        mesh_dependence=0.0,
        timestep_dependence=0.0,
        resonance_proximity=1.0,
        validity_ok=validity_ok,
        cost_budget=budget,
    )
    return plan_fidelity(current, rungs, signals)


def consume_map(
    performance_map: PerformanceMap,
    point: Mapping[str, float],
    *,
    tolerances: Mapping[str, float] | None = None,
    policy: ExtrapolationPolicy | None = None,
    ladder: Sequence[FidelityImplementation] = (),
) -> MapConsumption:
    """Consume a map at a point, rejecting or escalating outside validity."""

    trust: TrustDecision = map_trust(performance_map, tolerances)
    inside = performance_map.contains(point)
    active = performance_map.extrapolation if policy is None else policy
    if not inside and active is ExtrapolationPolicy.REJECT:
        raise ExtrapolationError(f"EXTRAPOLATION_REJECTED:{performance_map.map_id}")
    if inside and not trust.trusted and active is ExtrapolationPolicy.REJECT:
        raise ValidationError(f"UNVALIDATED_MAP_REJECTED:{performance_map.map_id}")
    prediction = performance_map.predict(point, policy=active)
    reasons: list[str] = []
    requires_escalation = False
    if not inside:
        requires_escalation = True
        reasons.append("query outside declared validity domain")
    if not trust.trusted:
        requires_escalation = True
        reasons.append(f"map is not trusted ({trust.status})")
    escalation = None
    if requires_escalation:
        escalation = fidelity_escalation(
            performance_map,
            uncertainty=prediction.uncertainty,
            inside_validity=inside,
            trusted=trust.trusted,
            ladder=ladder,
        )
    return MapConsumption(
        outputs=prediction.outputs,
        uncertainty=prediction.uncertainty,
        source=prediction.source,
        trusted=trust.trusted,
        inside_validity=inside,
        extrapolated=prediction.extrapolated,
        requires_escalation=requires_escalation,
        escalation=escalation,
        reasons=tuple(reasons) if reasons else ("consumed inside declared validity",),
        map_digest=performance_map.digest(),
    )
