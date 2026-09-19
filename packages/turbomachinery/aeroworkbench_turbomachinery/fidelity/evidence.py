"""Fidelity evidence ledger and disagreement-aware ranking.

Each evaluation at a rung is recorded as content-addressed evidence carrying
its source, fidelity, validity, convergence, provenance, and outputs. Ranking
always uses the highest-fidelity trusted evidence per candidate, so a cheap
result can never outrank a promoted trusted one; the disagreement between the
governing result and the cheaper results is preserved, and a demoted cheap
winner is reported explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_optimization import StudyObjective
from aeroworkbench_optimization.campaign import scalarized

from ..canonical import content_digest

__all__ = [
    "CandidateFidelityLedger",
    "FidelityEvidence",
    "RankedCandidate",
    "RankingReport",
    "rank_candidates",
]


@dataclass(frozen=True, slots=True)
class FidelityEvidence:
    """One evaluation of one candidate at one rung, with full provenance."""

    candidate_hash: str
    rung_id: str
    rank: int
    source: str
    fidelity: str
    outputs: tuple[tuple[str, float], ...]
    validity_ok: bool = True
    converged: bool = True
    trusted: bool = True
    cost: float = 0.0
    provenance: Provenance | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_hash.strip():
            raise ValueError("EVIDENCE_CANDIDATE_HASH_REQUIRED")
        if not self.rung_id.strip():
            raise ValueError("EVIDENCE_RUNG_ID_REQUIRED")
        if self.rank < 0:
            raise ValueError("EVIDENCE_RANK_NEGATIVE")
        if not isfinite(self.cost) or self.cost < 0:
            raise ValueError("EVIDENCE_COST_INVALID")
        for name, value in self.outputs:
            if not name.strip() or not isfinite(value):
                raise ValueError(f"EVIDENCE_OUTPUT_INVALID:{name}")

    @property
    def output_dict(self) -> dict[str, float]:
        return dict(self.outputs)

    @property
    def usable(self) -> bool:
        return bool(self.validity_ok and self.converged and self.trusted)

    def canonical(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "rungId": self.rung_id,
            "rank": self.rank,
            "source": self.source,
            "fidelity": self.fidelity,
            "outputs": [[name, value] for name, value in self.outputs],
            "validityOk": self.validity_ok,
            "converged": self.converged,
            "trusted": self.trusted,
            "cost": self.cost,
            "provenance": (
                None if self.provenance is None else self.provenance.model_dump(mode="json")
            ),
            "detail": self.detail,
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


class CandidateFidelityLedger:
    """Immutable, content-addressed evidence store across all fidelity rungs."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, FidelityEvidence]] = {}

    def record(self, evidence: FidelityEvidence) -> None:
        bucket = self._entries.setdefault(evidence.candidate_hash, {})
        existing = bucket.get(evidence.rung_id)
        if existing is not None and existing != evidence:
            raise ValueError(
                f"FIDELITY_EVIDENCE_IMMUTABLE:{evidence.candidate_hash}:{evidence.rung_id}"
            )
        bucket[evidence.rung_id] = evidence

    def evidence(self, candidate_hash: str) -> tuple[FidelityEvidence, ...]:
        bucket = self._entries.get(candidate_hash, {})
        return tuple(sorted(bucket.values(), key=lambda item: (item.rank, item.rung_id)))

    def candidates(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def governing(self, candidate_hash: str) -> FidelityEvidence | None:
        entries = self.evidence(candidate_hash)
        if not entries:
            return None
        trusted = [item for item in entries if item.usable]
        if trusted:
            return max(trusted, key=lambda item: (item.rank, item.rung_id))
        valid = [item for item in entries if item.validity_ok and item.converged]
        pool = valid if valid else list(entries)
        return max(pool, key=lambda item: (item.rank, item.rung_id))

    def canonical(self) -> dict[str, Any]:
        return {
            "candidates": {
                candidate: [item.canonical() for item in self.evidence(candidate)]
                for candidate in self.candidates()
            }
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical())


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate_hash: str
    rung_id: str
    rank: int
    score: float
    source: str
    fidelity: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "rungId": self.rung_id,
            "rank": self.rank,
            "score": self.score,
            "source": self.source,
            "fidelity": self.fidelity,
        }


@dataclass(frozen=True, slots=True)
class RankingReport:
    ranking: tuple[RankedCandidate, ...]
    demoted: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]
    disagreement: tuple[tuple[str, float], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ranking": [item.as_dict() for item in self.ranking],
            "demoted": list(self.demoted),
            "excluded": [[candidate, reason] for candidate, reason in self.excluded],
            "disagreement": [[candidate, value] for candidate, value in self.disagreement],
        }


def _relative_disagreement(
    objectives: Sequence[StudyObjective],
    governing: FidelityEvidence,
    others: Iterable[FidelityEvidence],
) -> float:
    worst = 0.0
    governing_outputs = governing.output_dict
    for other in others:
        if other.rung_id == governing.rung_id:
            continue
        other_outputs = other.output_dict
        for objective in objectives:
            mine = governing_outputs.get(objective.name)
            theirs = other_outputs.get(objective.name)
            if mine is None or theirs is None:
                continue
            scale = max(abs(mine), abs(theirs), 1e-9)
            worst = max(worst, abs(mine - theirs) / scale)
    return worst


def _order_by_cheap(
    ledger: CandidateFidelityLedger,
    objectives: Sequence[StudyObjective],
    candidate_hashes: Sequence[str],
) -> tuple[str, ...]:
    scored: list[tuple[float, str]] = []
    for candidate_hash in candidate_hashes:
        entries = ledger.evidence(candidate_hash)
        if not entries:
            continue
        cheapest = min(entries, key=lambda item: (item.rank, item.rung_id))
        scored.append((scalarized(objectives, cheapest.output_dict), candidate_hash))
    return tuple(candidate_hash for _, candidate_hash in sorted(scored))


def rank_candidates(
    ledger: CandidateFidelityLedger,
    objectives: Sequence[StudyObjective],
    *,
    candidate_hashes: Sequence[str] | None = None,
) -> RankingReport:
    """Rank by governing (highest-fidelity trusted) evidence, not stale cheap results."""
    if not objectives:
        raise ValueError("RANKING_NEEDS_OBJECTIVES")
    hashes = list(candidate_hashes) if candidate_hashes is not None else list(ledger.candidates())
    excluded: list[tuple[str, str]] = []
    ranked: list[tuple[float, str, FidelityEvidence]] = []
    disagreement: list[tuple[str, float]] = []
    for candidate_hash in hashes:
        entries = ledger.evidence(candidate_hash)
        if not entries:
            excluded.append((candidate_hash, "no-evidence"))
            continue
        governing = ledger.governing(candidate_hash)
        if governing is None or not governing.usable:
            excluded.append((candidate_hash, "no-trusted-valid-evidence"))
            continue
        score = scalarized(objectives, governing.output_dict)
        ranked.append((score, candidate_hash, governing))
        disagreement.append(
            (
                candidate_hash,
                _relative_disagreement(objectives, governing, entries),
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1]))
    ranking = tuple(
        RankedCandidate(
            candidate_hash,
            governing.rung_id,
            governing.rank,
            score,
            governing.source,
            governing.fidelity,
        )
        for score, candidate_hash, governing in ranked
    )
    trusted_order = tuple(item[1] for item in ranked)
    cheap_order = _order_by_cheap(ledger, objectives, [item[1] for item in ranked])
    cheap_position = {candidate: position for position, candidate in enumerate(cheap_order)}
    trusted_position = {
        candidate: position for position, candidate in enumerate(trusted_order)
    }
    demoted = tuple(
        candidate
        for candidate in trusted_order
        if cheap_position.get(candidate, 0) < trusted_position[candidate]
    )
    return RankingReport(
        ranking,
        demoted,
        tuple(excluded),
        tuple(sorted(disagreement)),
    )
