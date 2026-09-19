"""Numerical-independence study runner (GEN 12).

Executes a declared mesh or time-step refinement ladder over a participant or
coupled graph and decides whether the participant-declared quantities of
interest (QoI) are numerically independent.

The decision is made from the declared QoI alone. Element count, node count,
mesh-quality metrics, run count, and solver identity are recorded as evidence
but are never the acceptance basis: two meshes with identical element counts
and materially different QoI are *not* independent, and two meshes with
different element counts but a converged QoI *are*. Observed order and the
Roache grid-convergence index are reported only when the ladder geometry makes
them mathematically well defined (at least three levels, monotone trend, and a
strictly positive refinement ratio); otherwise they are ``None`` with a reason.

Nothing here executes a solver. An executor callable maps one declared level to
one :class:`StudyRun`; the runner never fabricates a run, input hash, or value.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite, log
from typing import Any

__all__ = [
    "IndependenceError",
    "IndependenceReport",
    "LadderExecutor",
    "QuantityOfInterest",
    "QoITrend",
    "RefinementLevel",
    "StudyRun",
    "run_independence_study",
    "run_mesh_independence",
    "run_timestep_independence",
]

MESH = "mesh"
TIMESTEP = "timestep"
DEFAULT_GCI_SAFETY_FACTOR = 1.25


class IndependenceError(ValueError):
    """Typed, fail-closed independence-contract violation."""


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class QuantityOfInterest:
    """One participant-declared QoI with its own normalized tolerance band."""

    name: str
    unit: str = "dimensionless"
    relative_tolerance: float = 0.05
    absolute_tolerance: float = 0.0
    reference_scale: float = 1.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise IndependenceError("INDEPENDENCE_QOI_NAME_REQUIRED")
        if not isfinite(self.relative_tolerance) or self.relative_tolerance < 0:
            raise IndependenceError(f"INVALID_RELATIVE_TOLERANCE:{self.name}")
        if not isfinite(self.absolute_tolerance) or self.absolute_tolerance < 0:
            raise IndependenceError(f"INVALID_ABSOLUTE_TOLERANCE:{self.name}")
        if not isfinite(self.reference_scale) or self.reference_scale <= 0:
            raise IndependenceError(f"INVALID_REFERENCE_SCALE:{self.name}")

    def allowed_deviation(self, reference: float) -> float:
        return self.absolute_tolerance + self.relative_tolerance * max(
            abs(reference), self.reference_scale
        )


@dataclass(frozen=True, slots=True)
class RefinementLevel:
    """One declared ladder rung: a name, a characteristic resolution, and
    declared scalar metadata (for example ``element_count`` or ``dt_s``).

    ``resolution`` is the characteristic refinement size (mesh edge length or
    time step). Finer levels have a *smaller* resolution.
    """

    name: str
    resolution: float
    declared: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise IndependenceError("INDEPENDENCE_LEVEL_NAME_REQUIRED")
        if not isfinite(self.resolution) or self.resolution <= 0:
            raise IndependenceError(f"INDEPENDENCE_LEVEL_RESOLUTION_INVALID:{self.name}")
        for key, value in self.declared:
            if not key.strip():
                raise IndependenceError(f"INDEPENDENCE_DECLARED_KEY_REQUIRED:{self.name}")
            if not isfinite(value):
                raise IndependenceError(f"NONFINITE_DECLARED_VALUE:{self.name}:{key}")

    def declared_dict(self) -> dict[str, float]:
        return dict(self.declared)


@dataclass(frozen=True, slots=True)
class StudyRun:
    """The real evidence produced by executing one refinement level.

    ``run_id`` and ``input_hash`` are supplied by the executor and must be
    non-empty: the runner will not invent them. ``valid`` is False when the
    solver did not converge or its validity envelope was violated.
    """

    level: str
    run_id: str
    input_hash: str
    qoi: tuple[tuple[str, float], ...]
    valid: bool = True
    source: str = "analytical"
    artifact_hash: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.level.strip():
            raise IndependenceError("STUDY_RUN_LEVEL_REQUIRED")
        if not self.run_id.strip():
            raise IndependenceError(f"STUDY_RUN_ID_REQUIRED:{self.level}")
        if not self.input_hash.strip():
            raise IndependenceError(f"STUDY_RUN_INPUT_HASH_REQUIRED:{self.level}")
        seen: set[str] = set()
        for name, value in self.qoi:
            if not name.strip():
                raise IndependenceError(f"STUDY_RUN_QOI_NAME_REQUIRED:{self.level}")
            if name in seen:
                raise IndependenceError(f"STUDY_RUN_DUPLICATE_QOI:{self.level}:{name}")
            seen.add(name)
            if not isfinite(value):
                raise IndependenceError(f"STUDY_RUN_NONFINITE_QOI:{self.level}:{name}")

    def qoi_dict(self) -> dict[str, float]:
        return dict(self.qoi)

    def content_hash(self) -> str:
        return _digest(
            {
                "level": self.level,
                "runId": self.run_id,
                "inputHash": self.input_hash,
                "qoi": {name: value for name, value in self.qoi},
                "valid": self.valid,
                "source": self.source,
                "artifactHash": self.artifact_hash,
            }
        )


LadderExecutor = Callable[[RefinementLevel], StudyRun]


@dataclass(frozen=True, slots=True)
class QoITrend:
    """One QoI across the ordered (coarse to fine) ladder."""

    name: str
    values: tuple[float, ...]
    deltas: tuple[float, ...]
    relative_deltas: tuple[float, ...]
    observed_order: float | None
    gci_fine: float | None
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "values": list(self.values),
            "deltas": list(self.deltas),
            "relativeDeltas": list(self.relative_deltas),
            "observedOrder": self.observed_order,
            "gciFine": self.gci_fine,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class IndependenceReport:
    """Full evidence and verdict for one numerical-independence study."""

    kind: str
    levels: tuple[str, ...]
    run_ids: tuple[str, ...]
    run_hashes: tuple[str, ...]
    resolutions: tuple[float, ...]
    declared: tuple[tuple[tuple[str, float], ...], ...]
    trends: tuple[QoITrend, ...]
    accepted: bool
    reason: str
    min_levels: int
    gci_safety_factor: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "levels": list(self.levels),
            "runIds": list(self.run_ids),
            "runHashes": list(self.run_hashes),
            "resolutions": list(self.resolutions),
            "declared": [
                {key: value for key, value in level} for level in self.declared
            ],
            "trends": [trend.as_dict() for trend in self.trends],
            "accepted": self.accepted,
            "reason": self.reason,
            "minLevels": self.min_levels,
            "gciSafetyFactor": self.gci_safety_factor,
        }


def _order_levels(levels: Sequence[RefinementLevel]) -> tuple[RefinementLevel, ...]:
    ordered = sorted(levels, key=lambda item: item.resolution, reverse=True)
    names = [level.name for level in ordered]
    if len(set(names)) != len(names):
        raise IndependenceError("INDEPENDENCE_DUPLICATE_LEVEL")
    for index in range(len(ordered) - 1):
        if ordered[index].resolution <= ordered[index + 1].resolution:
            raise IndependenceError(
                f"INDEPENDENCE_RESOLUTIONS_NOT_STRICTLY_DECREASING:"
                f"{ordered[index].name}->{ordered[index + 1].name}"
            )
    return tuple(ordered)


def _observed_order(values: Sequence[float], resolutions: Sequence[float]) -> float | None:
    """Observed order from the three finest levels when it is well defined."""

    if len(values) < 3:
        return None
    coarse, middle, fine = values[-3], values[-2], values[-1]
    h_coarse, h_middle, h_fine = resolutions[-3], resolutions[-2], resolutions[-1]
    delta_coarse = middle - coarse
    delta_fine = fine - middle
    if delta_coarse == 0.0 or delta_fine == 0.0:
        return None
    if delta_coarse * delta_fine <= 0.0:
        return None
    ratio = h_middle / h_coarse
    ratio_fine = h_fine / h_middle
    if ratio <= 0.0 or ratio_fine <= 0.0 or ratio == 1.0:
        return None
    if abs(ratio - ratio_fine) > 1e-9 * max(ratio, ratio_fine):
        return None
    order = log(abs(delta_fine / delta_coarse)) / log(ratio)
    if not isfinite(order):
        return None
    return order


def _gci_fine(
    values: Sequence[float],
    resolutions: Sequence[float],
    observed_order: float | None,
    safety_factor: float,
) -> float | None:
    """Roache GCI on the finest level when order and geometry allow it."""

    if observed_order is None or observed_order <= 0:
        return None
    ratio = resolutions[-2] / resolutions[-1]
    if ratio <= 1.0:
        return None
    fine = values[-1]
    coarse = values[-2]
    if fine == 0.0:
        return None
    relative_error = abs((fine - coarse) / fine)
    denominator = ratio**observed_order - 1.0
    if denominator <= 0.0:
        return None
    gci = safety_factor * relative_error / denominator
    return gci if isfinite(gci) and gci >= 0.0 else None


def run_independence_study(
    kind: str,
    levels: Sequence[RefinementLevel],
    qoi: Sequence[QuantityOfInterest],
    execute: LadderExecutor,
    *,
    min_levels: int = 2,
    gci_safety_factor: float = DEFAULT_GCI_SAFETY_FACTOR,
    require_all_valid: bool = True,
) -> IndependenceReport:
    """Execute a declared ladder and decide numerical independence.

    Fail-closed: a missing QoI declaration, an executor that returns the wrong
    level, or a non-finite value all raise instead of producing a verdict.
    """

    if kind not in {MESH, TIMESTEP}:
        raise IndependenceError(f"UNKNOWN_INDEPENDENCE_KIND:{kind}")
    if not qoi:
        raise IndependenceError("INDEPENDENCE_REQUIRES_DECLARED_QOI")
    if not isfinite(gci_safety_factor) or gci_safety_factor <= 0:
        raise IndependenceError("INVALID_GCI_SAFETY_FACTOR")
    if len(levels) < min_levels:
        raise IndependenceError(
            f"INDEPENDENCE_NEEDS_AT_LEAST_{min_levels}_LEVELS:{len(levels)}"
        )
    names = [spec.name for spec in qoi]
    if len(set(names)) != len(names):
        raise IndependenceError("INDEPENDENCE_DUPLICATE_QOI_SPEC")

    ordered = _order_levels(levels)
    runs: list[StudyRun] = []
    for level in ordered:
        run = execute(level)
        if not isinstance(run, StudyRun):
            raise IndependenceError(f"EXECUTOR_MUST_RETURN_STUDY_RUN:{level.name}")
        if run.level != level.name:
            raise IndependenceError(
                f"STUDY_RUN_LEVEL_MISMATCH:expected {level.name} got {run.level}"
            )
        runs.append(run)

    resolutions = tuple(level.resolution for level in ordered)
    declared = tuple(level.declared for level in ordered)

    trends: list[QoITrend] = []
    for spec in qoi:
        values: list[float] = []
        for run in runs:
            if spec.name not in run.qoi_dict():
                raise IndependenceError(
                    f"STUDY_RUN_MISSING_QOI:{run.level}:{spec.name}"
                )
            values.append(run.qoi_dict()[spec.name])
        deltas = tuple(
            values[index + 1] - values[index] for index in range(len(values) - 1)
        )
        finest = values[-1]
        allowed = spec.allowed_deviation(finest)
        relative_deltas = tuple(
            abs(delta) / max(abs(finest), spec.reference_scale) for delta in deltas
        )
        # Independence means the two finest solutions agree within tolerance.
        # A three-level trend whose finest change grows is oscillatory or
        # divergent even if one pair happens to look small, so it fails too.
        finest_delta = deltas[-1] if deltas else 0.0
        finest_ok = abs(finest_delta) <= allowed
        diverging = len(deltas) >= 2 and abs(deltas[-1]) > abs(deltas[-2])
        passed = finest_ok and not diverging
        order = _observed_order(values, resolutions)
        gci = _gci_fine(values, resolutions, order, gci_safety_factor)
        if passed:
            detail = (
                f"finest={finest:.6g} finest-change={finest_delta:.3g} "
                f"allowed={allowed:.3g}"
            )
        elif not finest_ok:
            detail = (
                f"finest={finest:.6g} finest-change={finest_delta:.3g} exceeds "
                f"allowed={allowed:.3g}"
            )
        else:
            detail = (
                f"finest={finest:.6g} change grows from {deltas[-2]:.3g} to "
                f"{deltas[-1]:.3g}: oscillatory/divergent trend"
            )
        trends.append(
            QoITrend(
                spec.name,
                tuple(values),
                deltas,
                relative_deltas,
                order,
                gci,
                passed,
                detail,
            )
        )

    all_valid = all(run.valid for run in runs)
    qoi_ok = all(trend.passed for trend in trends)
    accepted = qoi_ok and (all_valid or not require_all_valid)
    failures: list[str] = []
    if require_all_valid and not all_valid:
        invalid = ",".join(run.level for run in runs if not run.valid)
        failures.append(f"nonconverged-or-invalid-runs:{invalid}")
    failed_qoi = [trend.name for trend in trends if not trend.passed]
    if failed_qoi:
        failures.append(f"qoi-not-independent:{','.join(failed_qoi)}")
    if accepted:
        reason = (
            f"{kind} independence accepted across {len(ordered)} levels for "
            f"declared QoI {','.join(names)}"
        )
    else:
        reason = f"{kind} independence rejected: {'; '.join(failures)}"

    return IndependenceReport(
        kind=kind,
        levels=tuple(level.name for level in ordered),
        run_ids=tuple(run.run_id for run in runs),
        run_hashes=tuple(run.content_hash() for run in runs),
        resolutions=resolutions,
        declared=declared,
        trends=tuple(trends),
        accepted=accepted,
        reason=reason,
        min_levels=min_levels,
        gci_safety_factor=gci_safety_factor,
    )


def run_mesh_independence(
    levels: Sequence[RefinementLevel],
    qoi: Sequence[QuantityOfInterest],
    execute: LadderExecutor,
    *,
    gci_safety_factor: float = DEFAULT_GCI_SAFETY_FACTOR,
    require_all_valid: bool = True,
) -> IndependenceReport:
    """Mesh independence over a declared coarse->fine ladder (>= 2 levels)."""

    return run_independence_study(
        MESH,
        levels,
        qoi,
        execute,
        min_levels=2,
        gci_safety_factor=gci_safety_factor,
        require_all_valid=require_all_valid,
    )


def run_timestep_independence(
    levels: Sequence[RefinementLevel],
    qoi: Sequence[QuantityOfInterest],
    execute: LadderExecutor,
    *,
    transient: bool = True,
    gci_safety_factor: float = DEFAULT_GCI_SAFETY_FACTOR,
    require_all_valid: bool = True,
) -> IndependenceReport:
    """Time-step independence; a transient validation needs >= 3 levels."""

    return run_independence_study(
        TIMESTEP,
        levels,
        qoi,
        execute,
        min_levels=3 if transient else 2,
        gci_safety_factor=gci_safety_factor,
        require_all_valid=require_all_valid,
    )
