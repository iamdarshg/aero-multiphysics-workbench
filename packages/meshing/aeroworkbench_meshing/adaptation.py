"""Generic adaptive-refinement loop with auditable mesh revisions.

A solver-derived error indicator (gradient, residual, QoI sensitivity, shock,
vorticity, wake, stress or temperature gradient) drives bounded refinement. Each
pass produces a new :class:`MeshRevision` with a content hash and a preserved
parent lineage. The loop stops when indicators fall below the threshold, when
the cell budget is exhausted, when a quality gate fails, or at the declared
maximum pass count.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .budget import MeshBudget
from .contracts import (
    ResultEnvelope,
    Validity,
    analytical_envelope,
    content_digest,
)
from .errors import AdaptationError, MeshContractError

__all__ = [
    "AdaptationPolicy",
    "AdaptationResult",
    "ErrorIndicator",
    "IndicatorKind",
    "MeshRevision",
    "adapt",
    "adaptation_policy_from_budget",
    "next_revision",
]


class IndicatorKind(StrEnum):
    """Solver-derived error indicator families."""

    GRADIENT = "gradient"
    RESIDUAL = "residual"
    QOI_SENSITIVITY = "qoi_sensitivity"
    SHOCK = "shock"
    VORTICITY = "vorticity"
    WAKE = "wake"
    STRESS_GRADIENT = "stress_gradient"
    TEMPERATURE_GRADIENT = "temperature_gradient"


@dataclass(frozen=True, slots=True)
class ErrorIndicator:
    """One localized solver error indicator over a semantic key."""

    kind: IndicatorKind
    semantic_key: str
    magnitude: float
    threshold: float | None = None

    def __post_init__(self) -> None:
        if not self.semantic_key.strip():
            raise MeshContractError(f"INDICATOR_SEMANTIC_KEY_REQUIRED:{self.kind.value}")
        if not isfinite(self.magnitude) or self.magnitude < 0.0:
            raise MeshContractError(f"INDICATOR_MAGNITUDE_INVALID:{self.semantic_key}")
        if self.threshold is not None and (
            not isfinite(self.threshold) or self.threshold < 0.0
        ):
            raise MeshContractError(f"INDICATOR_THRESHOLD_INVALID:{self.semantic_key}")

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "semanticKey": self.semantic_key,
            "magnitude": self.magnitude,
            "threshold": self.threshold,
        }


@dataclass(frozen=True, slots=True)
class MeshRevision:
    """One auditable mesh revision with preserved parent lineage."""

    revision: int
    mesh_hash: str
    element_count: int
    parent_revision: int | None = None
    parent_hash: str | None = None
    refined_keys: tuple[str, ...] = ()
    indicator_digest: str | None = None
    min_sicn: float | None = None
    accepted: bool = True
    reason: str = ""

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise MeshContractError(f"REVISION_INVALID:{self.revision}")
        if not self.mesh_hash.strip():
            raise MeshContractError(f"REVISION_MESH_HASH_REQUIRED:{self.revision}")
        if self.element_count < 0:
            raise MeshContractError(f"REVISION_ELEMENT_COUNT_INVALID:{self.revision}")
        if (self.parent_revision is None) != (self.parent_hash is None):
            raise MeshContractError(f"REVISION_PARENT_INCONSISTENT:{self.revision}")
        if self.parent_revision is not None and self.parent_revision >= self.revision:
            raise MeshContractError(f"REVISION_PARENT_NOT_PRIOR:{self.revision}")
        if self.min_sicn is not None and not isfinite(self.min_sicn):
            raise MeshContractError(f"REVISION_SICN_INVALID:{self.revision}")

    def content_payload(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "meshHash": self.mesh_hash,
            "elementCount": self.element_count,
            "parentRevision": self.parent_revision,
            "parentHash": self.parent_hash,
            "refinedKeys": list(self.refined_keys),
            "indicatorDigest": self.indicator_digest,
            "minSicn": self.min_sicn,
            "accepted": self.accepted,
            "reason": self.reason,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.content_payload())

    def as_dict(self) -> dict[str, object]:
        payload = self.content_payload()
        payload["digest"] = self.digest
        return payload


def next_revision(
    parent: MeshRevision,
    *,
    mesh_hash: str,
    refined_keys: Sequence[str],
    indicators: Sequence[ErrorIndicator],
    element_count: int,
    min_sicn: float | None = None,
    accepted: bool = True,
    reason: str = "",
) -> MeshRevision:
    """Build the child revision of ``parent`` with an explicit lineage."""

    return MeshRevision(
        revision=parent.revision + 1,
        mesh_hash=mesh_hash,
        element_count=element_count,
        parent_revision=parent.revision,
        parent_hash=parent.digest,
        refined_keys=tuple(refined_keys),
        indicator_digest=content_digest([item.as_dict() for item in indicators]),
        min_sicn=min_sicn,
        accepted=accepted,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class AdaptationPolicy:
    """Bounded adaptation controls."""

    max_passes: int
    refinement_factor: float = 0.5
    indicator_threshold: float = 0.0
    min_sicn: float | None = None
    cell_budget: int | None = None

    def __post_init__(self) -> None:
        if self.max_passes < 0:
            raise MeshContractError("ADAPTATION_MAX_PASSES_INVALID")
        if not 0.0 < self.refinement_factor < 1.0:
            raise MeshContractError("ADAPTATION_REFINEMENT_FACTOR_INVALID")
        if not isfinite(self.indicator_threshold) or self.indicator_threshold < 0.0:
            raise MeshContractError("ADAPTATION_INDICATOR_THRESHOLD_INVALID")
        if self.cell_budget is not None and self.cell_budget < 1:
            raise MeshContractError("ADAPTATION_CELL_BUDGET_INVALID")
        if self.min_sicn is not None and not isfinite(self.min_sicn):
            raise MeshContractError("ADAPTATION_MIN_SICN_INVALID")


def adaptation_policy_from_budget(
    budget: MeshBudget,
    *,
    refinement_factor: float = 0.5,
    indicator_threshold: float = 0.0,
    min_sicn: float | None = None,
) -> AdaptationPolicy:
    """Derive an adaptation policy that respects the declared mesh budget."""

    return AdaptationPolicy(
        max_passes=budget.max_adaptation_passes,
        refinement_factor=refinement_factor,
        indicator_threshold=indicator_threshold,
        min_sicn=min_sicn,
        cell_budget=budget.max_cells,
    )


IndicatorProvider = Callable[[MeshRevision], Sequence[ErrorIndicator]]
MeshRefiner = Callable[[MeshRevision, tuple[ErrorIndicator, ...], float], MeshRevision]


@dataclass(frozen=True, slots=True)
class AdaptationResult:
    """Full adaptation lineage and verdict."""

    revisions: tuple[MeshRevision, ...]
    accepted: bool
    passes: int
    stopped_reason: str
    envelope: ResultEnvelope

    @property
    def final(self) -> MeshRevision:
        return self.revisions[-1]

    def as_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "passes": self.passes,
            "stoppedReason": self.stopped_reason,
            "revisions": [item.as_dict() for item in self.revisions],
        }


def _select(indicators: Sequence[ErrorIndicator], threshold: float) -> tuple[ErrorIndicator, ...]:
    selected = [item for item in indicators if item.magnitude >= threshold]
    return tuple(
        sorted(selected, key=lambda item: (item.semantic_key, item.kind.value))
    )


def adapt(
    *,
    initial: MeshRevision,
    indicators: IndicatorProvider,
    refine: MeshRefiner,
    policy: AdaptationPolicy,
) -> AdaptationResult:
    """Run a bounded refinement loop and return the auditable revision chain."""

    revisions: list[MeshRevision] = [initial]
    current = initial
    stopped_reason = "max_passes_reached"
    for _ in range(policy.max_passes):
        produced = tuple(indicators(current))
        for item in produced:
            if not isinstance(item, ErrorIndicator):
                raise AdaptationError("INDICATOR_PROVIDER_MUST_RETURN_ERROR_INDICATORS")
        selected = _select(produced, policy.indicator_threshold)
        if not selected:
            stopped_reason = "indicators_below_threshold"
            break
        child = refine(current, selected, policy.refinement_factor)
        if not isinstance(child, MeshRevision):
            raise AdaptationError("REFINER_MUST_RETURN_MESH_REVISION")
        if (
            child.revision != current.revision + 1
            or child.parent_revision != current.revision
            or child.parent_hash != current.digest
        ):
            raise AdaptationError(
                f"ADAPTATION_LINEAGE_BROKEN:{current.revision}->{child.revision}"
            )
        revisions.append(child)
        current = child
        if policy.cell_budget is not None and child.element_count > policy.cell_budget:
            stopped_reason = "cell_budget_exceeded"
            break
        if not child.accepted:
            stopped_reason = "quality_gate_failed"
            break
        if policy.min_sicn is not None and (
            child.min_sicn is None or child.min_sicn < policy.min_sicn
        ):
            stopped_reason = "quality_gate_failed"
            break

    accepted = stopped_reason == "indicators_below_threshold" and all(
        item.accepted for item in revisions
    )
    validity = Validity(
        passed=accepted,
        checks={
            "lineage_preserved": all(
                item.parent_hash is not None for item in revisions[1:]
            ),
            "quality_gate_passed": all(item.accepted for item in revisions),
            "converged": stopped_reason == "indicators_below_threshold",
        },
        detail=stopped_reason,
    )
    envelope = analytical_envelope(
        model="mesh-adaptation",
        inputs={
            "initialDigest": initial.digest,
            "maxPasses": policy.max_passes,
            "refinementFactor": policy.refinement_factor,
            "indicatorThreshold": policy.indicator_threshold,
            "cellBudget": policy.cell_budget,
            "minSicn": policy.min_sicn,
        },
        units=(("dimensionless", "1"), ("length", "mm")),
        validity=validity,
        assumptions=(
            "revisions carry measured quality from their own mesh",
            "loop is bounded by max_passes, cell budget, and quality gates",
        ),
    )
    return AdaptationResult(
        revisions=tuple(revisions),
        accepted=accepted,
        passes=len(revisions) - 1,
        stopped_reason=stopped_reason,
        envelope=envelope,
    )
