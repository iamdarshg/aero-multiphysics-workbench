"""PERF 05: batch and vectorized cheap-candidate evaluation.

Early-stage generative searches evaluate many analytical / reduced-order
candidates before anything is promoted to a native solver. Paying Python and
OpenMDAO setup plus one function call per candidate dominates that phase. This
module provides:

- an optional :class:`BatchEvaluator` contract (N normalized inputs in, N
  independently labelled result/quality rows out, candidate hash and
  operating-point identity preserved, individual rows markable invalid);
- a :class:`OneAtATimeBatchEvaluator` fallback for participants that cannot
  batch;
- a NumPy-vectorized path restricted to *pure analytical / reduced* models
  (native solver execution fails closed and is never vectorized);
- memory-bounded chunking so a large request never materializes everything;
- throughput metrics (candidates/s, per-candidate overhead, setup time, batch
  size).

Correctness comes first: batching must reproduce the one-at-a-time result
within an explicit tolerance, and a failed or malformed batch falls back to the
scalar path for that chunk rather than inventing values.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from typing import Any, Protocol, runtime_checkable

from .quality import PhysicsFlags

__all__ = [
    "BATCH_VECTORIZABLE_FIDELITIES",
    "BatchEvaluator",
    "BatchMetrics",
    "BatchRequest",
    "BatchRow",
    "BatchRunResult",
    "ChunkedBatchRunner",
    "OneAtATimeBatchEvaluator",
    "ScalarBatchFallback",
    "ScalarEvaluation",
    "VectorizedReducedModel",
    "build_batch_requests",
    "compare_batch_rows",
    "iter_chunks",
    "plan_batch_size",
    "run_batch_requests",
]

#: Fidelities that may be vectorized. Native/field/transient execution is never
#: batched through this module (see :class:`VectorizedReducedModel`).
BATCH_VECTORIZABLE_FIDELITIES = frozenset(
    {"analytical", "reduced", "reduced-order", "surrogate"}
)


def _valid_flags() -> PhysicsFlags:
    return PhysicsFlags(converged=True, closure_passed=True, validity_ok=True)


def _invalid_flags() -> PhysicsFlags:
    return PhysicsFlags(converged=False, closure_passed=False, validity_ok=False)


@dataclass(frozen=True, slots=True)
class ScalarEvaluation:
    """What a scalar fallback returns for one (inputs, operating point) pair."""

    outputs: Mapping[str, float]
    flags: PhysicsFlags
    source: str = "analytical"
    detail: str = ""
    cost: float = 0.0
    signals: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.cost) or self.cost < 0:
            raise ValueError("EVALUATION_COST_MUST_BE_NONNEGATIVE")


ScalarBatchFallback = Callable[[Mapping[str, float], str], ScalarEvaluation]


@dataclass(frozen=True, slots=True)
class BatchRequest:
    """One normalized candidate input at one operating point.

    ``candidate_hash`` and ``operating_point`` are the identity that must be
    preserved end to end: a batch result is never matched to a request by
    position alone.
    """

    candidate_hash: str
    operating_point: str
    inputs: tuple[tuple[str, float], ...]
    index: int = 0

    def __post_init__(self) -> None:
        if not self.candidate_hash.strip():
            raise ValueError("BATCH_REQUEST_NEEDS_CANDIDATE_HASH")
        if not self.operating_point.strip():
            raise ValueError("BATCH_REQUEST_NEEDS_OPERATING_POINT")
        for name, value in self.inputs:
            if not name.strip():
                raise ValueError("BATCH_REQUEST_INPUT_NEEDS_NAME")
            if not isfinite(value):
                raise ValueError(f"NONFINITE_BATCH_INPUT:{name}")

    @property
    def key(self) -> tuple[str, str]:
        return (self.candidate_hash, self.operating_point)

    def input_dict(self) -> dict[str, float]:
        return dict(self.inputs)


@dataclass(frozen=True, slots=True)
class BatchRow:
    """One independently labelled batch result / quality record."""

    candidate_hash: str
    operating_point: str
    index: int
    state: str  # "valid" | "invalid"
    outputs: tuple[tuple[str, float], ...]
    flags: PhysicsFlags
    reasons: tuple[str, ...] = ()
    source: str = "analytical"
    detail: str = ""
    cost: float = 0.0
    signals: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if self.state not in {"valid", "invalid"}:
            raise ValueError(f"UNKNOWN_BATCH_ROW_STATE:{self.state}")
        if not isfinite(self.cost) or self.cost < 0:
            raise ValueError("EVALUATION_COST_MUST_BE_NONNEGATIVE")

    @property
    def key(self) -> tuple[str, str]:
        return (self.candidate_hash, self.operating_point)

    @property
    def output_dict(self) -> dict[str, float]:
        return dict(self.outputs)

    @property
    def signal_dict(self) -> dict[str, float]:
        return dict(self.signals)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidateHash": self.candidate_hash,
            "operatingPoint": self.operating_point,
            "index": self.index,
            "state": self.state,
            "outputs": [[name, value] for name, value in self.outputs],
            "reasons": list(self.reasons),
            "source": self.source,
            "detail": self.detail,
            "cost": self.cost,
            "signals": [[name, value] for name, value in self.signals],
        }


@runtime_checkable
class BatchEvaluator(Protocol):
    """Optional batch implementation a participant/model may declare."""

    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> Sequence[BatchRow]: ...


class OneAtATimeBatchEvaluator:
    """Fallback that runs the scalar function once per request.

    A single failing row is marked invalid; the rest of the chunk still
    returns.
    """

    def __init__(self, fallback: ScalarBatchFallback) -> None:
        self._fallback = fallback

    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> tuple[BatchRow, ...]:
        rows: list[BatchRow] = []
        for request in requests:
            try:
                result = self._fallback(request.input_dict(), request.operating_point)
            except Exception as exc:  # noqa: BLE001 - evaluation failures fail closed
                rows.append(
                    BatchRow(
                        candidate_hash=request.candidate_hash,
                        operating_point=request.operating_point,
                        index=request.index,
                        state="invalid",
                        outputs=(),
                        flags=_invalid_flags(),
                        reasons=(f"EVALUATION_ERROR:{type(exc).__name__}:{exc}",),
                    )
                )
                continue
            outputs: list[tuple[str, float]] = []
            kept: list[str] = []
            reasons: list[str] = []
            for name, value in result.outputs.items():
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    reasons.append(f"NONFINITE_OUTPUT:{name}")
                    continue
                if not isfinite(number):
                    reasons.append(f"NONFINITE_OUTPUT:{name}")
                    continue
                outputs.append((str(name), number))
                kept.append(str(name))
            state = "invalid" if reasons else "valid"
            flags = result.flags if state == "valid" else _invalid_flags()
            rows.append(
                BatchRow(
                    candidate_hash=request.candidate_hash,
                    operating_point=request.operating_point,
                    index=request.index,
                    state=state,
                    outputs=tuple(sorted(outputs)),
                    flags=flags,
                    reasons=tuple(reasons),
                    source=result.source,
                    detail=result.detail,
                    cost=result.cost,
                    signals=tuple(
                        sorted(
                            (str(name), float(value))
                            for name, value in (result.signals or {}).items()
                        )
                    ),
                )
            )
        return tuple(rows)


#: A vectorized model maps named input arrays (and the operating-point labels)
#: to named output arrays in one call.
VectorFunction = Callable[[Mapping[str, Any], tuple[str, ...]], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class VectorizedReducedModel:
    """A pure analytical/reduced model expressed as true array math.

    Native (or otherwise stateful) execution is refused: vectorization must
    never hide a native solver call behind a fake batch.
    """

    model_id: str
    fidelity: str
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]
    vector_function: VectorFunction
    source: str = "analytical"
    cost_per_candidate: float = 0.0

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("VECTORIZED_MODEL_NEEDS_ID")
        if self.fidelity not in BATCH_VECTORIZABLE_FIDELITIES:
            raise ValueError(f"BATCH_VECTORIZATION_NATIVE_NOT_ALLOWED:{self.fidelity}")
        if not self.input_names or not self.output_names:
            raise ValueError("VECTORIZED_MODEL_NEEDS_NAMED_IO")
        if len(set(self.input_names)) != len(self.input_names):
            raise ValueError("VECTORIZED_MODEL_DUPLICATE_INPUT")
        if len(set(self.output_names)) != len(self.output_names):
            raise ValueError("VECTORIZED_MODEL_DUPLICATE_OUTPUT")
        if not isfinite(self.cost_per_candidate) or self.cost_per_candidate < 0:
            raise ValueError("EVALUATION_COST_MUST_BE_NONNEGATIVE")

    def evaluate_batch(self, requests: Sequence[BatchRequest]) -> tuple[BatchRow, ...]:
        import numpy as np

        count = len(requests)
        if count == 0:
            return ()
        arrays = {name: np.empty(count, dtype=float) for name in self.input_names}
        missing: dict[int, list[str]] = {}
        for position, request in enumerate(requests):
            values = request.input_dict()
            for name in self.input_names:
                value = values.get(name)
                if value is None:
                    missing.setdefault(position, []).append(name)
                    arrays[name][position] = math.nan
                else:
                    arrays[name][position] = float(value)
        operating_points = tuple(request.operating_point for request in requests)
        computed = self.vector_function(arrays, operating_points)
        unknown = [name for name in self.output_names if name not in computed]
        if unknown:
            raise ValueError(f"VECTORIZED_MODEL_MISSING_OUTPUT:{unknown[0]}")
        rows: list[BatchRow] = []
        for position, request in enumerate(requests):
            reasons: list[str] = [
                f"MISSING_BATCH_INPUT:{name}" for name in missing.get(position, ())
            ]
            outputs: list[tuple[str, float]] = []
            for name in self.output_names:
                try:
                    number = float(computed[name][position])
                except (TypeError, ValueError, IndexError):
                    reasons.append(f"NONFINITE_BATCH_OUTPUT:{name}")
                    continue
                if not isfinite(number):
                    reasons.append(f"NONFINITE_BATCH_OUTPUT:{name}")
                    continue
                outputs.append((name, number))
            state = "invalid" if reasons else "valid"
            rows.append(
                BatchRow(
                    candidate_hash=request.candidate_hash,
                    operating_point=request.operating_point,
                    index=request.index,
                    state=state,
                    outputs=tuple(sorted(outputs)),
                    flags=_valid_flags() if state == "valid" else _invalid_flags(),
                    reasons=tuple(reasons),
                    source=self.source,
                    detail=f"vectorized:{self.model_id}",
                    cost=self.cost_per_candidate,
                )
            )
        return tuple(rows)


# ---------------------------------------------------------------------------
# chunking + memory bound
# ---------------------------------------------------------------------------


def plan_batch_size(
    requested: int,
    *,
    memory_budget_bytes: int | None = None,
    bytes_per_row: int = 1024,
) -> int:
    """Effective rows per chunk, reduced to respect a memory budget."""
    if requested <= 0:
        raise ValueError("BATCH_SIZE_MUST_BE_POSITIVE")
    if bytes_per_row <= 0:
        raise ValueError("BYTES_PER_ROW_MUST_BE_POSITIVE")
    if memory_budget_bytes is None:
        return requested
    if memory_budget_bytes <= 0:
        raise ValueError("MEMORY_BUDGET_MUST_BE_POSITIVE")
    return max(1, min(requested, memory_budget_bytes // bytes_per_row))


def iter_chunks(
    requests: Sequence[BatchRequest], batch_size: int
) -> Iterator[tuple[BatchRequest, ...]]:
    if batch_size <= 0:
        raise ValueError("BATCH_SIZE_MUST_BE_POSITIVE")
    for start in range(0, len(requests), batch_size):
        yield tuple(requests[start : start + batch_size])


def build_batch_requests(
    entries: Sequence[tuple[str, Mapping[str, float]]],
    operating_points: Sequence[str] = ("nominal",),
    *,
    start_index: int = 0,
) -> tuple[BatchRequest, ...]:
    """Expand candidate inputs across operating points, preserving identity."""
    if not operating_points:
        raise ValueError("BATCH_NEEDS_AN_OPERATING_POINT")
    requests: list[BatchRequest] = []
    index = start_index
    for candidate_hash, inputs in entries:
        frozen = tuple(sorted((str(name), float(value)) for name, value in inputs.items()))
        for operating_point in operating_points:
            requests.append(
                BatchRequest(
                    candidate_hash=str(candidate_hash),
                    operating_point=str(operating_point),
                    inputs=frozen,
                    index=index,
                )
            )
            index += 1
    return tuple(requests)


# ---------------------------------------------------------------------------
# metrics + runner
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BatchMetrics:
    candidates: int
    batches: int
    effective_batch_size: int
    fallback_batches: int
    invalid_rows: int
    peak_batch_rows: int
    setup_seconds: float
    evaluate_seconds: float
    candidates_per_second: float
    per_candidate_overhead_ms: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "candidates": self.candidates,
            "batches": self.batches,
            "batchSize": self.effective_batch_size,
            "fallbackBatches": self.fallback_batches,
            "invalidRows": self.invalid_rows,
            "peakBatchRows": self.peak_batch_rows,
            "setupSeconds": self.setup_seconds,
            "evaluateSeconds": self.evaluate_seconds,
            "candidatesPerSecond": self.candidates_per_second,
            "perCandidateOverheadMs": self.per_candidate_overhead_ms,
        }


@dataclass(frozen=True, slots=True)
class BatchRunResult:
    rows: tuple[BatchRow, ...]
    metrics: BatchMetrics

    def by_key(self) -> dict[tuple[str, str], BatchRow]:
        return {row.key: row for row in self.rows}


def _reconcile(
    chunk: Sequence[BatchRequest],
    produced: Sequence[BatchRow],
    fallback: OneAtATimeBatchEvaluator,
) -> tuple[tuple[BatchRow, ...], bool]:
    """Match produced rows to requests by identity, falling back per chunk.

    Returns the ordered rows plus whether the scalar fallback was used because
    the batch was unusable (wrong count, duplicate/mismatched identity).
    """
    available: dict[tuple[str, str], BatchRow] = {}
    duplicates = False
    for row in produced:
        if row.key in available:
            duplicates = True
        available[row.key] = row
    if duplicates or {row.key for row in produced} != {request.key for request in chunk}:
        # A malformed batch cannot be trusted; replay the chunk one-at-a-time.
        return fallback.evaluate_batch(chunk), True
    return tuple(available[request.key] for request in chunk), False


@dataclass
class ChunkedBatchRunner:
    """Memory-bounded chunked runner over an optional batch evaluator."""

    evaluator: BatchEvaluator | None
    fallback: ScalarBatchFallback
    batch_size: int = 64
    memory_budget_bytes: int | None = None
    bytes_per_row: int = 1024

    def effective_batch_size(self) -> int:
        return plan_batch_size(
            self.batch_size,
            memory_budget_bytes=self.memory_budget_bytes,
            bytes_per_row=self.bytes_per_row,
        )

    def run(self, requests: Sequence[BatchRequest]) -> BatchRunResult:
        effective = self.effective_batch_size()
        fallback_evaluator = OneAtATimeBatchEvaluator(self.fallback)
        evaluator = self.evaluator or fallback_evaluator
        rows: list[BatchRow] = []
        batches = 0
        fallback_batches = 0
        peak = 0
        start = perf_counter()
        for chunk in iter_chunks(requests, effective):
            batches += 1
            peak = max(peak, len(chunk))
            try:
                produced = tuple(evaluator.evaluate_batch(chunk))
            except Exception:  # noqa: BLE001 - an unusable batch falls back, fail-safe
                produced = ()
            reconciled, used_fallback = _reconcile(chunk, produced, fallback_evaluator)
            if used_fallback and self.evaluator is not None:
                fallback_batches += 1
            rows.extend(reconciled)
        evaluate_seconds = perf_counter() - start
        invalid_rows = sum(1 for row in rows if row.state != "valid")
        return BatchRunResult(
            rows=tuple(rows),
            metrics=_metrics(
                rows=len(rows),
                batches=batches,
                effective=effective,
                fallback_batches=fallback_batches,
                invalid_rows=invalid_rows,
                peak=peak,
                setup_seconds=0.0,
                evaluate_seconds=evaluate_seconds,
            ),
        )


def _metrics(
    *,
    rows: int,
    batches: int,
    effective: int,
    fallback_batches: int,
    invalid_rows: int,
    peak: int,
    setup_seconds: float,
    evaluate_seconds: float,
) -> BatchMetrics:
    total = setup_seconds + evaluate_seconds
    return BatchMetrics(
        candidates=rows,
        batches=batches,
        effective_batch_size=effective,
        fallback_batches=fallback_batches,
        invalid_rows=invalid_rows,
        peak_batch_rows=peak,
        setup_seconds=setup_seconds,
        evaluate_seconds=evaluate_seconds,
        candidates_per_second=(rows / evaluate_seconds) if evaluate_seconds > 0 and rows else 0.0,
        per_candidate_overhead_ms=(total * 1000.0 / rows) if rows else 0.0,
    )


def run_batch_requests(
    requests: Sequence[BatchRequest],
    *,
    fallback: ScalarBatchFallback,
    evaluator: BatchEvaluator | None = None,
    batch_size: int = 64,
    memory_budget_bytes: int | None = None,
    bytes_per_row: int = 1024,
    setup: Callable[[], None] | None = None,
) -> BatchRunResult:
    """Run requests in bounded chunks, measuring setup, throughput, overhead."""
    setup_seconds = 0.0
    if setup is not None:
        started = perf_counter()
        setup()
        setup_seconds = perf_counter() - started
    runner = ChunkedBatchRunner(
        evaluator=evaluator,
        fallback=fallback,
        batch_size=batch_size,
        memory_budget_bytes=memory_budget_bytes,
        bytes_per_row=bytes_per_row,
    )
    result = runner.run(requests)
    metrics = _metrics(
        rows=result.metrics.candidates,
        batches=result.metrics.batches,
        effective=result.metrics.effective_batch_size,
        fallback_batches=result.metrics.fallback_batches,
        invalid_rows=result.metrics.invalid_rows,
        peak=result.metrics.peak_batch_rows,
        setup_seconds=setup_seconds,
        evaluate_seconds=result.metrics.evaluate_seconds,
    )
    return BatchRunResult(rows=result.rows, metrics=metrics)


def compare_batch_rows(
    reference: Sequence[BatchRow],
    candidate: Sequence[BatchRow],
    *,
    rtol: float = 1e-9,
    atol: float = 1e-12,
) -> tuple[str, ...]:
    """Bounded tolerance comparison keyed by candidate hash + operating point."""
    if rtol < 0 or atol < 0:
        raise ValueError("COMPARISON_TOLERANCE_MUST_BE_NONNEGATIVE")
    ref = {row.key: row for row in reference}
    cand = {row.key: row for row in candidate}
    problems: list[str] = []
    for key in sorted(set(ref) - set(cand)):
        problems.append(f"missing:{key[0]}:{key[1]}")
    for key in sorted(set(cand) - set(ref)):
        problems.append(f"extra:{key[0]}:{key[1]}")
    for key in sorted(set(ref) & set(cand)):
        left, right = ref[key], cand[key]
        if left.state != right.state:
            problems.append(f"state:{key[0]}:{key[1]}:{left.state}!={right.state}")
        left_outputs, right_outputs = left.output_dict, right.output_dict
        for name in sorted(set(left_outputs) - set(right_outputs)):
            problems.append(f"missing-output:{key[0]}:{name}")
        for name in sorted(set(right_outputs) - set(left_outputs)):
            problems.append(f"extra-output:{key[0]}:{name}")
        for name in sorted(set(left_outputs) & set(right_outputs)):
            expected, actual = left_outputs[name], right_outputs[name]
            if abs(expected - actual) > atol + rtol * abs(expected):
                problems.append(f"value:{key[0]}:{name}:{expected}!={actual}")
    return tuple(problems)
