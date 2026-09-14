"""Generic fidelity planner over participant-declared implementations.

A participant declares its implementation ladder (analytical, reduced-order,
steady/transient native, harmonic, full field-coupled, high-resolution
native, or any other ordered set). The planner weighs the requested
question/output, design maturity, constraint margin, solver disagreement,
sensitivity, convergence difficulty, mesh/timestep dependence, resonance
proximity, validity ranges, and cost limits. Escalation is explainable (every
decision carries the fired rules) and provenance-backed (the signal digest is
recorded). The planner never jumps to the most expensive implementation
unless validity forces it: ordinary escalation moves one rank, validity
failure moves to the cheapest valid implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class FidelityImplementation:
    """One declared implementation with cost rank and capabilities."""

    name: str
    rank: int
    cost: float
    capabilities: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("IMPLEMENTATION_NAME_REQUIRED")
        if self.rank < 0 or not isfinite(self.cost) or self.cost < 0:
            raise ValueError(f"INVALID_IMPLEMENTATION_SPEC:{self.name}")


@dataclass(frozen=True, slots=True)
class FidelitySignals:
    """Everything the planner may consider; all fields are generic."""

    question: str
    maturity: float  # 0 (concept) .. 1 (frozen)
    constraint_margin: float  # fraction of allowable band remaining
    disagreement: float  # normalized solver-to-solver disagreement
    sensitivity: float  # normalized output sensitivity to the modelled effect
    convergence_difficulty: float  # 0 (easy) .. 1 (stalled)
    mesh_dependence: float  # normalized mesh sensitivity
    timestep_dependence: float  # normalized timestep sensitivity
    resonance_proximity: float  # minimum separation normalized (large = safe)
    validity_ok: Mapping[str, bool]
    cost_budget: float
    required_capability: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("maturity", self.maturity),
            ("constraint_margin", self.constraint_margin),
            ("disagreement", self.disagreement),
            ("sensitivity", self.sensitivity),
            ("convergence_difficulty", self.convergence_difficulty),
            ("mesh_dependence", self.mesh_dependence),
            ("timestep_dependence", self.timestep_dependence),
            ("resonance_proximity", self.resonance_proximity),
        ):
            if not isfinite(value):
                raise ValueError(f"NONFINITE_FIDELITY_SIGNAL:{label}")
        if not self.question.strip() or not isfinite(self.cost_budget) or self.cost_budget < 0:
            raise ValueError("INVALID_FIDELITY_SIGNALS")


@dataclass(frozen=True, slots=True)
class FidelityPlan:
    level: str
    escalate: bool
    reasons: tuple[str, ...]
    input_hash: str
    detail: str


def plan_fidelity(
    current: str,
    implementations: Sequence[FidelityImplementation],
    signals: FidelitySignals,
) -> FidelityPlan:
    """Plan one fidelity step with explicit, ordered, explainable rules."""

    ordered = sorted(implementations, key=lambda item: item.rank)
    if not ordered or [item.rank for item in ordered] != list(range(len(ordered))):
        raise ValueError("IMPLEMENTATIONS_MUST_FORM_RANK_LADDER_FROM_ZERO")
    names = [item.name for item in ordered]
    if current not in names:
        raise ValueError(f"CURRENT_FIDELITY_NOT_DECLARED:{current}")
    costs = {item.name: item.cost for item in ordered}
    index = names.index(current)
    reasons: list[str] = []
    target = index
    validity_forced = False
    # Rule 1: validity failure forces the cheapest valid implementation.
    if not signals.validity_ok.get(current, True):
        valid = [
            position
            for position, name in enumerate(names)
            if signals.validity_ok.get(name, False)
        ]
        if not valid:
            raise ValueError("NO_VALID_FIDELITY_IMPLEMENTATION")
        target = min(valid)
        validity_forced = True
        reasons.append(f"validity failed at {current}; cheapest valid is {names[target]}")
    # Rule 2: resonance proximity demands the required capability.
    if signals.required_capability:
        capable = [
            position
            for position, item in enumerate(ordered)
            if signals.required_capability in item.capabilities
        ]
        if capable and signals.resonance_proximity < 0.1 and target < min(capable):
            target = min(capable)
            reasons.append(
                f"resonance proximity {signals.resonance_proximity:.3g} requires "
                f"{signals.required_capability}; activating {names[target]}"
            )
    # Rule 3+: single-rank escalation on difficulty signals.
    triggers = [
        (signals.disagreement > 0.2, f"solver disagreement {signals.disagreement:.3g}"),
        (signals.sensitivity > 0.3, f"sensitivity {signals.sensitivity:.3g}"),
        (signals.convergence_difficulty > 0.5, "convergence difficulty"),
        (signals.mesh_dependence > 0.2, f"mesh dependence {signals.mesh_dependence:.3g}"),
        (signals.timestep_dependence > 0.2, "timestep dependence"),
        (
            signals.constraint_margin < 0.1 and signals.maturity > 0.5,
            f"tight margin {signals.constraint_margin:.3g} "
            f"at maturity {signals.maturity:.3g}",
        ),
    ]
    for fired, reason in triggers:
        if fired and target == index and target < len(ordered) - 1:
            target = index + 1
            reasons.append(f"{reason}; escalate one rank to {names[target]}")
            break
    # Cost guard: the budget never silently buys the top rung, and a validity
    # requirement the budget cannot afford fails closed instead of degrading.
    if costs[names[target]] > signals.cost_budget:
        affordable = [
            position
            for position, name in enumerate(names)
            if costs[name] <= signals.cost_budget
        ]
        if not affordable or validity_forced:
            raise ValueError("FIDELITY_BUDGET_EXCLUDES_REQUIRED_IMPLEMENTATION")
        target = max(affordable)
        reasons.append(f"cost budget {signals.cost_budget:.3g}; holding {names[target]}")
    escalated = target > index
    if not reasons:
        reasons.append(f"{current} remains sufficient for question {signals.question!r}")
    payload = json.dumps(
        {
            "current": current,
            "ladder": names,
            "signals": {
                "question": signals.question,
                "maturity": signals.maturity,
                "constraint_margin": signals.constraint_margin,
                "disagreement": signals.disagreement,
                "sensitivity": signals.sensitivity,
                "convergence_difficulty": signals.convergence_difficulty,
                "mesh_dependence": signals.mesh_dependence,
                "timestep_dependence": signals.timestep_dependence,
                "resonance_proximity": signals.resonance_proximity,
                "validity_ok": dict(sorted(signals.validity_ok.items())),
                "cost_budget": signals.cost_budget,
                "required_capability": signals.required_capability,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return FidelityPlan(
        names[target], escalated, tuple(reasons),
        hashlib.sha256(payload).hexdigest(),
        f"{'escalate' if escalated else 'hold'} {current} -> {names[target]}",
    )
