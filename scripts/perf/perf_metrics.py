"""Bounded Python microbenchmarks for the workbench engineering hot paths.

This module is measurement infrastructure, never a feature path. Every
measurement is bounded, reports its environment, and skips with an explicit
reason when a capability is unavailable instead of inventing a number.

Nothing here weakens provenance, validation, or fail-closed behavior: the
synthetic participant used for lifecycle-overhead timing executes the *real*
``NativeJobManager`` state machine in-process with a trivial body, and is
labelled as orchestration-only (solver compute excluded by construction).
"""

# ruff: noqa: E501 -- benchmark tables and JSON-shaped records read better unwrapped.

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from _bootstrap import ensure_sys_path, python_path_string

REPO_ROOT = ensure_sys_path()

SCHEMA_VERSION = 1
GROUP = "python"


# ---------------------------------------------------------------------------
# result model + timing helpers
# ---------------------------------------------------------------------------


def _empty_metric(
    metric_id: str,
    *,
    group: str = GROUP,
    unit: str = "ms",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "group": group,
        "status": "skipped",
        "available": False,
        "cold": False,
        "unit": unit,
        "iterations": 0,
        "median": None,
        "p95": None,
        "min": None,
        "max": None,
        "totalMs": None,
        "perItemMs": None,
        "itemsPerSecond": None,
        "mibPerSecond": None,
        "items": None,
        "bytes": None,
        "reason": None,
        "notes": notes,
        "stages": None,
    }


def skipped(
    metric_id: str, reason: str, *, unit: str = "ms", notes: str = ""
) -> dict[str, Any]:
    metric = _empty_metric(metric_id, unit=unit, notes=notes)
    metric["status"] = "skipped"
    metric["reason"] = reason
    return metric


def failed(metric_id: str, reason: str, *, unit: str = "ms") -> dict[str, Any]:
    metric = _empty_metric(metric_id, unit=unit)
    metric["status"] = "failed"
    metric["reason"] = reason
    return metric


def _percentile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        raise ValueError("EMPTY_SAMPLE")
    if len(ordered) == 1:
        return ordered[0]
    rank = fraction * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def latency(
    metric_id: str,
    samples_ms: list[float],
    *,
    iterations: int | None = None,
    cold: bool = False,
    notes: str = "",
    stages: dict[str, float] | None = None,
) -> dict[str, Any]:
    ordered = sorted(samples_ms)
    metric = _empty_metric(metric_id, notes=notes)
    metric.update(
        {
            "status": "measured",
            "available": True,
            "cold": cold,
            "iterations": iterations if iterations is not None else len(ordered),
            "median": round(_percentile(ordered, 0.5), 6),
            "p95": round(_percentile(ordered, 0.95), 6),
            "min": round(ordered[0], 6),
            "max": round(ordered[-1], 6),
            "totalMs": round(sum(ordered), 6),
            "stages": stages,
        }
    )
    return metric


def throughput(
    metric_id: str,
    *,
    total_ms: float,
    items: float,
    bytes_: float | None = None,
    iterations: int | None = None,
    unit: str = "ms",
    notes: str = "",
    stages: dict[str, float] | None = None,
) -> dict[str, Any]:
    metric = _empty_metric(metric_id, unit=unit, notes=notes)
    per_item = (total_ms / items) if items else None
    # When a byte count is supplied, MiB/s is the meaningful throughput and the
    # item count is only an iteration count; do not report a misleading items/s.
    items_per_second = (
        (items / (total_ms / 1000.0)) if total_ms > 0 and items and bytes_ is None else None
    )
    mib_per_second = (
        (bytes_ / (1024 * 1024)) / (total_ms / 1000.0)
        if bytes_ is not None and total_ms > 0
        else None
    )
    metric.update(
        {
            "status": "measured",
            "available": True,
            "iterations": iterations if iterations is not None else int(items),
            "totalMs": round(total_ms, 6),
            "perItemMs": round(per_item, 6) if per_item is not None else None,
            "itemsPerSecond": round(items_per_second, 3) if items_per_second else None,
            "mibPerSecond": round(mib_per_second, 3) if mib_per_second else None,
            "items": items,
            "bytes": bytes_,
            "stages": stages,
        }
    )
    return metric


# ---------------------------------------------------------------------------
# synthetic participant (runtime-only; no source under solvers/ is touched)
# ---------------------------------------------------------------------------

_TINY_ID = "perf-tiny"
_TINY_REGISTERED = False
_ACCUM: dict[str, float] = {}


def _tiny_prepare(inputs: dict[str, object], case_dir: Path) -> Any:
    from participants.receipts import PrepareReceipt

    case_dir.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(
        {key: inputs[key] for key in sorted(inputs)}, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    (case_dir / "case.json").write_text(canonical, encoding="utf-8")
    return PrepareReceipt(
        participant_id=_TINY_ID,
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail="perf synthetic in-process participant",
    )


def _tiny_execute(inputs: dict[str, object], case_dir: Path) -> None:
    _ = inputs
    (case_dir / "result.json").write_text(json.dumps({"value": 1.0}), encoding="utf-8")


def _tiny_parse(case_dir: Path) -> Any:
    from participants.receipts import ParseReceipt

    data = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    return ParseReceipt(
        participant_id=_TINY_ID,
        parser="perf_metrics:_tiny_parse",
        scalars={"value": float(data["value"])},
        units={"value": "dimensionless"},
    )


def _tiny_validate(scalars: dict[str, float], inputs: dict[str, object]) -> Any:
    from participants.receipts import ValidityReport

    _ = (scalars, inputs)
    return ValidityReport(
        participant_id=_TINY_ID,
        passed=True,
        checks={"finite": True},
        detail="perf synthetic participant is always valid",
    )


def register_tiny_participant() -> None:
    """Register the synthetic participant in the live registry (idempotent)."""

    global _TINY_REGISTERED
    if _TINY_REGISTERED:
        return
    from participants import lifecycle as lifecycle_mod
    from participants import manifest as manifest_mod
    from participants.manifest import (
        ExecutableCapability,
        ParticipantManifest,
        PortSpec,
    )
    from participants.receipts import CapabilityProbe

    ports_in = (PortSpec("seed", "scalar", "int", "dimensionless", "in"),)
    ports_out = (PortSpec("value", "scalar", "float", "dimensionless", "out"),)
    synthetic = ParticipantManifest(
        participant_id=_TINY_ID,
        physics_domain="performance",
        manifest_version=manifest_mod.MANIFEST_VERSION,
        description="Benchmark-only in-process participant: orchestration overhead measured, solver compute excluded.",
        inputs=ports_in,
        outputs=ports_out,
        geometry_roles=(),
        mesh_roles=(),
        semantic_requirements=(),
        coupling_direction="none",
        convergence_measures=("residual",),
        fidelity_levels=("perf",),
        executable=ExecutableCapability("perf", ("perf-metrics",), "in-process"),
        prepare_ref="perf_metrics:_tiny_prepare",
        execute_ref="perf_metrics:_tiny_execute",
        parser_ref="perf_metrics:_tiny_parse",
        validity_ref="perf_metrics:_tiny_validate",
        artifacts=("result.json",),
        checkpoint=False,
        benchmark_ref="perf-01-baseline",
    )
    manifest_mod._REGISTRY[_TINY_ID] = synthetic
    lifecycle_mod._ALLOWED_MODULES = frozenset(
        set(lifecycle_mod._ALLOWED_MODULES) | {"perf_metrics"}
    )
    original_probe = lifecycle_mod.probe_participant

    def _probe(participant_id: str) -> CapabilityProbe:
        if participant_id == _TINY_ID:
            return CapabilityProbe(
                participant_id, "perf", "perf-metrics", "ready", "perf", "synthetic perf participant"
            )
        return original_probe(participant_id)

    lifecycle_mod.probe_participant = _probe
    _TINY_REGISTERED = True


class _TimedRepository:
    """Times the real repository writes performed while a job runs."""

    def __init__(self, inner: Any, accum: dict[str, float]) -> None:
        self._inner = inner
        self._accum = accum

    def append_provenance(self, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return self._inner.append_provenance(**kwargs)
        finally:
            self._accum["persistence_ms"] = self._accum.get("persistence_ms", 0.0) + (
                time.perf_counter() - start
            ) * 1000.0

    def close(self) -> None:
        self._inner.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _TimedLedger:
    def __init__(self, inner: Any, accum: dict[str, float]) -> None:
        self._inner = inner
        self._accum = accum

    def _record(self, start: float) -> None:
        self._accum["persistence_ms"] = self._accum.get("persistence_ms", 0.0) + (
            time.perf_counter() - start
        ) * 1000.0

    def create(self, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return self._inner.create(**kwargs)
        finally:
            self._record(start)

    def update(self, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return self._inner.update(*args, **kwargs)
        finally:
            self._record(start)

    def append_event(self, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return self._inner.append_event(**kwargs)
        finally:
            self._record(start)

    def close(self) -> None:
        self._inner.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@contextlib.contextmanager
def _instrumented_job(manager_root: Path) -> Iterator[tuple[Any, dict[str, float]]]:
    from participants.lifecycle import NativeJobManager
    from participants.store import JobLedger

    from aeroworkbench_api.repositories.sqlite import SQLiteRepository

    manager_root.mkdir(parents=True, exist_ok=True)
    accum: dict[str, float] = {"persistence_ms": 0.0, "hashing_ms": 0.0}
    repository = _TimedRepository(SQLiteRepository(manager_root / "provenance.sqlite3"), accum)
    ledger = _TimedLedger(JobLedger(manager_root / "native_jobs.sqlite3"), accum)
    manager = NativeJobManager(manager_root, repository=repository, ledger=ledger)
    original_hash = NativeJobManager._hash_artifacts

    def _timed_hash(case_dir: Path, expected: tuple[str, ...]) -> Any:
        start = time.perf_counter()
        try:
            return original_hash(case_dir, expected)
        finally:
            accum["hashing_ms"] += (time.perf_counter() - start) * 1000.0

    NativeJobManager._hash_artifacts = staticmethod(_timed_hash)
    try:
        yield manager, accum
    finally:
        NativeJobManager._hash_artifacts = staticmethod(original_hash)
        manager.close()


# ---------------------------------------------------------------------------
# measurements
# ---------------------------------------------------------------------------


def measure_api_warm_request_latency(ctx: Context) -> dict[str, Any]:
    metric_id = "api.warm_request_latency"
    try:
        from fastapi.testclient import TestClient

        from aeroworkbench_api.main import create_app
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"API/FastAPI unavailable: {type(exc).__name__}:{exc}")
    os.environ.setdefault("AEROWORKBENCH_JOB_ROOT", str(ctx.temp_root / "api-warm"))
    try:
        app = create_app()
        samples: list[float] = []
        with TestClient(app) as client:
            for _ in range(5):
                client.get("/health")
            for _ in range(100):
                start = time.perf_counter()
                response = client.get("/health")
                samples.append((time.perf_counter() - start) * 1000.0)
                if response.status_code != 200:
                    return failed(metric_id, f"/health returned {response.status_code}")
            state_samples: list[float] = []
            for _ in range(50):
                start = time.perf_counter()
                response = client.get("/api/v1/workbench/state")
                state_samples.append((time.perf_counter() - start) * 1000.0)
                if response.status_code != 200:
                    return failed(metric_id, f"/state returned {response.status_code}")
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    metric = latency(
        metric_id,
        samples,
        iterations=100,
        notes="in-process ASGI via TestClient after 5 warmups; each sample is one GET /health",
    )
    metric["stages"] = {
        "workbench_state_median_ms": round(_percentile(sorted(state_samples), 0.5), 6),
        "workbench_state_p95_ms": round(_percentile(sorted(state_samples), 0.95), 6),
    }
    return metric


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_ready(url: str, timeout: float = 0.3) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:  # noqa: BLE001
        return False


def _terminate_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        else:
            proc.terminate()
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            proc.kill()


def measure_api_cold_start_ready(ctx: Context, budget_s: float = 40.0) -> dict[str, Any]:
    metric_id = "api.cold_start_ready"
    if not (ctx.api_dir / "aeroworkbench_api" / "main.py").is_file():
        return skipped(metric_id, "services/api sources are missing")
    remaining_s = ctx.remaining_ms() / 1000.0
    if math.isfinite(remaining_s):
        budget_s = max(3.0, min(budget_s, remaining_s - 1.0))
    port = _free_port()
    job_root = ctx.temp_root / "api-cold"
    job_root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = python_path_string()
    env["AEROWORKBENCH_JOB_ROOT"] = str(job_root)
    log_path = ctx.temp_root / "api-cold-uvicorn.log"
    try:
        with log_path.open("wb") as log:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "aeroworkbench_api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                ],
                cwd=str(ctx.api_dir),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"could not spawn uvicorn: {type(exc).__name__}:{exc}")
    url = f"http://127.0.0.1:{port}/health"
    start = time.perf_counter()
    ready = False
    try:
        while time.perf_counter() - start < budget_s:
            if proc.poll() is not None:
                tail = _tail(log_path)
                return failed(metric_id, f"uvicorn exited early (code {proc.returncode}):{tail}")
            if _http_ready(url):
                ready = True
                break
            time.sleep(0.05)
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        _terminate_process(proc)
    if not ready:
        return skipped(
            metric_id,
            f"API did not answer /health within {budget_s:.0f}s",
            notes=_tail(log_path),
        )
    metric = latency(
        metric_id,
        [elapsed_ms],
        iterations=1,
        cold=True,
        notes="subprocess uvicorn cold start to first HTTP 200 on /health, then terminated",
    )
    return metric


def _tail(path: Path, limit: int = 400) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:].replace("\n", " | ")
    except OSError:
        return ""


def measure_job_submit_to_preparing(ctx: Context, iterations: int = 20) -> dict[str, Any]:
    metric_id = "lifecycle.submit_to_preparing"
    try:
        register_tiny_participant()
        from participants.lifecycle import TERMINAL_STATES, NativeJobManager
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"lifecycle unavailable: {type(exc).__name__}:{exc}")
    root = ctx.temp_root / "submit-preparing"
    samples: list[float] = []
    try:
        manager = NativeJobManager(root)
        try:
            for index in range(iterations):
                job_id = manager.submit(_TINY_ID, {"seed": index})
                deadline = time.perf_counter() + 10.0
                while manager.status(job_id)["state"] not in TERMINAL_STATES:
                    if time.perf_counter() > deadline:
                        return failed(metric_id, "job did not reach a terminal state")
                    time.sleep(0.002)
                created = _state_at(manager, job_id, "QUEUED")
                preparing = _state_at(manager, job_id, "PREPARING")
                if created is None or preparing is None:
                    return failed(metric_id, "PREPARING was never persisted")
                samples.append((preparing - created) * 1000.0)
        finally:
            manager.close()
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    return latency(
        metric_id,
        samples,
        iterations=iterations,
        notes="wall time from persisted QUEUED timestamp to persisted PREPARING timestamp (tiny in-process participant)",
    )


def measure_tiny_job_stage_split(ctx: Context, iterations: int = 10) -> dict[str, Any]:
    metric_id = "lifecycle.tiny_job_stage_split"
    try:
        register_tiny_participant()
        from participants.lifecycle import JobState
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"lifecycle unavailable: {type(exc).__name__}:{exc}")
    stage_samples: dict[str, list[float]] = {
        "submit_to_preparing_ms": [],
        "preparing_to_running_ms": [],
        "running_to_parsing_ms": [],
        "parsing_to_validating_ms": [],
        "validating_to_completed_ms": [],
        "total_ms": [],
        "persistence_ms": [],
        "hashing_ms": [],
    }
    try:
        for index in range(iterations):
            root = ctx.temp_root / f"tiny-job-{index}"
            with _instrumented_job(root) as (manager, accum):
                job_id = manager.submit(_TINY_ID, {"seed": index}, deferred=True)
                final = manager.run(job_id)
                if final != JobState.COMPLETED.value:
                    return failed(metric_id, f"tiny job ended {final}")
                times = {event["state"]: event["at"] for event in manager.events(job_id)}
                stamps = {state: _parse_iso(value) for state, value in times.items()}
                missing = [
                    state
                    for state in ("QUEUED", "PREPARING", "RUNNING", "PARSING", "VALIDATING", "COMPLETED")
                    if state not in stamps
                ]
                if missing:
                    return failed(metric_id, f"missing lifecycle events:{','.join(missing)}")
                stage_samples["submit_to_preparing_ms"].append(
                    (stamps["PREPARING"] - stamps["QUEUED"]) * 1000.0
                )
                stage_samples["preparing_to_running_ms"].append(
                    (stamps["RUNNING"] - stamps["PREPARING"]) * 1000.0
                )
                stage_samples["running_to_parsing_ms"].append(
                    (stamps["PARSING"] - stamps["RUNNING"]) * 1000.0
                )
                stage_samples["parsing_to_validating_ms"].append(
                    (stamps["VALIDATING"] - stamps["PARSING"]) * 1000.0
                )
                stage_samples["validating_to_completed_ms"].append(
                    (stamps["COMPLETED"] - stamps["VALIDATING"]) * 1000.0
                )
                stage_samples["total_ms"].append(
                    (stamps["COMPLETED"] - stamps["QUEUED"]) * 1000.0
                )
            stage_samples["persistence_ms"].append(accum["persistence_ms"])
            stage_samples["hashing_ms"].append(accum["hashing_ms"])
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    stages = {
        key: round(_percentile(sorted(values), 0.5), 6) for key, values in stage_samples.items()
    }
    return latency(
        metric_id,
        stage_samples["total_ms"],
        iterations=iterations,
        notes=(
            "real NativeJobManager state machine driven by a synthetic in-process participant; "
            "solver/external compute is absent by construction. persistence_ms/hashing_ms are measured "
            "by wrapping the real ledger/repository/artifact-hash calls and overlap the state windows."
        ),
        stages=stages,
    )


def _state_at(manager: Any, job_id: str, state: str) -> float | None:
    for event in manager.events(job_id):
        if event["state"] == state:
            return _parse_iso(event["at"])
    return None


def _parse_iso(value: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(value).timestamp()


def measure_content_lookup(ctx: Context, entries: int = 200, lookups: int = 40_000) -> dict[str, Any]:
    metric_id = "cache.content_lookup"
    try:
        from aeroworkbench_coupling import ContentCache
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"coupling.ContentCache unavailable: {type(exc).__name__}:{exc}")
    cache: Any = ContentCache()
    keys = [hashlib.sha256(f"perf-{index}".encode()).hexdigest() for index in range(entries)]
    for key, index in zip(keys, range(entries), strict=True):
        cache.put(key, (float(index), "dimensionless"))
    samples: list[float] = []
    for index in range(lookups):
        key = keys[index % entries]
        start = time.perf_counter()
        cache.get(key)
        samples.append((time.perf_counter() - start) * 1000.0)
    metric = latency(
        metric_id,
        samples,
        iterations=lookups,
        notes=f"{entries} populated entries; each sample is one ContentCache.get (deepcopy)",
    )
    return metric


def measure_dag_cache_hit_vs_miss(ctx: Context, nodes: int = 12, iterations: int = 20) -> dict[str, Any]:
    metric_id = "dag.cache_hit_vs_miss"
    try:
        from aeroworkbench_coupling import ComputationDAG, NodeSpec
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"coupling.DAG unavailable: {type(exc).__name__}:{exc}")

    def make_dag() -> Any:
        dag = ComputationDAG(
            {f"n{index}": (lambda deps, index=index: (float(len(deps) + index), "dimensionless")) for index in range(nodes)}
        )
        for index in range(nodes):
            dag.add(
                NodeSpec(
                    node_id=f"n{index}",
                    kind="analytical",
                    family="geometry",
                    upstream=(() if index == 0 else (f"n{index - 1}",)),
                    solver=("perf", "1"),
                    settings={"index": index},
                    base_inputs=("geometry",),
                )
            )
        return dag

    base = {"geometry": hashlib.sha256(b"geometry").hexdigest()}
    hit_samples: list[float] = []
    miss_samples: list[float] = []
    try:
        dag = make_dag()
        dag.execute(base)  # warm: first pass computes every node
        for _ in range(iterations):
            start = time.perf_counter()
            receipts = dag.execute(base)
            hit_samples.append((time.perf_counter() - start) * 1000.0)
            if not all(receipt.cached for receipt in receipts.values()):
                return failed(metric_id, "warm pass reported a cache miss")
        for _ in range(iterations):
            start = time.perf_counter()
            receipts = dag.execute(base, changed_sections=("geometry",))
            miss_samples.append((time.perf_counter() - start) * 1000.0)
            if any(receipt.cached for receipt in receipts.values()):
                return failed(metric_id, "invalidated pass reported a cache hit")
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    hit_metric = latency(metric_id, hit_samples, iterations=iterations, notes=f"{nodes}-node DAG, warm cache")
    hit_metric["stages"] = {
        "hit_median_ms": round(_percentile(sorted(hit_samples), 0.5), 6),
        "miss_median_ms": round(_percentile(sorted(miss_samples), 0.5), 6),
        "miss_minus_hit_ms": round(
            _percentile(sorted(miss_samples), 0.5) - _percentile(sorted(hit_samples), 0.5), 6
        ),
    }
    hit_metric["notes"] = hit_metric["notes"] + "; miss = changed_sections=('geometry',) invalidates every node"
    return hit_metric


def measure_sqlite_provenance_write(ctx: Context, events: int = 200) -> dict[str, Any]:
    metric_id = "sqlite.provenance_write"
    try:
        from aeroworkbench_api.repositories.sqlite import ArtifactReference, SQLiteRepository
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"SQLiteRepository unavailable: {type(exc).__name__}:{exc}")
    path = ctx.temp_root / "provenance-perf.sqlite3"
    if path.exists():
        path.unlink()
    artifact_sha = hashlib.sha256(b"artifact").hexdigest()
    repository = SQLiteRepository(path)
    start = time.perf_counter()
    try:
        for index in range(events):
            repository.append_provenance(
                event_id=f"perf-{index}",
                event_type="perf.benchmark",
                subject_hash=hashlib.sha256(str(index).encode()).hexdigest(),
                actor="perf",
                occurred_at="2026-01-01T00:00:00+00:00",
                details={"index": index, "note": "bounded perf fixture"},
                artifacts=[
                    ArtifactReference(
                        format="json", uri=f"perf/{index}.json", sha256=artifact_sha, bytes=16
                    )
                ],
            )
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    finally:
        repository.close()
    total_ms = (time.perf_counter() - start) * 1000.0
    return throughput(
        metric_id,
        total_ms=total_ms,
        items=events,
        iterations=events,
        notes="committed append-only provenance events (chained event hash) with one artifact ref each",
    )


def measure_sqlite_ledger_event_write(ctx: Context, events: int = 500) -> dict[str, Any]:
    metric_id = "sqlite.ledger_event_write"
    try:
        from participants.store import JobLedger
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"JobLedger unavailable: {type(exc).__name__}:{exc}")
    path = ctx.temp_root / "ledger-perf.sqlite3"
    if path.exists():
        path.unlink()
    ledger = JobLedger(path)
    try:
        ledger.create(
            job_id="perf-job",
            participant_id="perf-tiny",
            design_id="perf",
            state="QUEUED",
            created_at="2026-01-01T00:00:00+00:00",
            inputs={"seed": 0},
        )
        start = time.perf_counter()
        for index in range(events):
            ledger.append_event(
                job_id="perf-job",
                state="PREPARING",
                at="2026-01-01T00:00:00+00:00",
                detail=f"perf-{index}",
            )
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    finally:
        ledger.close()
    total_ms = (time.perf_counter() - start) * 1000.0
    return throughput(
        metric_id,
        total_ms=total_ms,
        items=events,
        iterations=events,
        notes="native_job_events inserts, one committed transaction each",
    )


def measure_artifact_hashing(ctx: Context, size_mib: int = 4, iterations: int = 5) -> dict[str, Any]:
    metric_id = "artifact.hashing_throughput"
    try:
        from participants.lifecycle import _sha256_file
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"artifact hashing unavailable: {type(exc).__name__}:{exc}")
    fixture = ctx.temp_root / f"hash-fixture-{size_mib}mib.bin"
    if not fixture.is_file() or fixture.stat().st_size != size_mib * 1024 * 1024:
        block = os.urandom(1024 * 1024)
        with fixture.open("wb") as stream:
            for _ in range(size_mib):
                stream.write(block)
    total_ms = 0.0
    for _ in range(iterations):
        start = time.perf_counter()
        digest, size = _sha256_file(fixture)
        total_ms += (time.perf_counter() - start) * 1000.0
        if len(digest) != 64 or size != size_mib * 1024 * 1024:
            return failed(metric_id, "hash result did not match the fixture")
    return throughput(
        metric_id,
        total_ms=total_ms,
        items=iterations,
        bytes_=float(size_mib * 1024 * 1024 * iterations),
        iterations=iterations,
        notes=f"sha256 of a {size_mib} MiB fixture, {iterations} passes, same code path as artifact registration",
    )


def measure_process_launch_overhead(ctx: Context, iterations: int = 10) -> dict[str, Any]:
    metric_id = "lifecycle.process_launch_overhead"
    try:
        from aeroworkbench_api.process_supervisor import ProcessPolicy, ProcessSupervisor
    except Exception as exc:  # noqa: BLE001
        return skipped(metric_id, f"ProcessSupervisor unavailable: {type(exc).__name__}:{exc}")
    job_root = ctx.temp_root / "launch-overhead"
    case_dir = job_root / "case-perf"
    case_dir.mkdir(parents=True, exist_ok=True)
    allowed = {Path(sys.executable).name}
    launch_samples: list[float] = []
    compute_samples: list[float] = []
    total_samples: list[float] = []
    try:
        supervisor = ProcessSupervisor(
            ProcessPolicy(
                job_root=job_root,
                allowed_executables=frozenset(allowed),
                rss_limit_mib=256.0,
                timeout_seconds=10.0,
                poll_seconds=0.01,
            ),
            rss_probe=lambda _pid: 1.0,
        )
        for _ in range(iterations):
            wall0 = time.time()
            start = time.perf_counter()
            receipt = supervisor.run([sys.executable, "-c", "pass"], cwd=case_dir)
            total_samples.append((time.perf_counter() - start) * 1000.0)
            if receipt.state != "completed":
                return failed(metric_id, f"trivial process did not complete:{receipt.reason}")
            launch_samples.append((receipt.started_at - wall0) * 1000.0)
            compute_samples.append((receipt.finished_at - receipt.started_at) * 1000.0)
    except Exception as exc:  # noqa: BLE001
        return failed(metric_id, f"{type(exc).__name__}:{exc}")
    metric = latency(
        metric_id,
        total_samples,
        iterations=iterations,
        notes="governed spawn of a trivial python process; RSS probe injected (launch overhead only)",
        stages={
            "launch_median_ms": round(_percentile(sorted(launch_samples), 0.5), 6),
            "compute_median_ms": round(_percentile(sorted(compute_samples), 0.5), 6),
        },
    )
    return metric


def _available_module(*names: str) -> str | None:
    for name in names:
        try:
            if importlib.util.find_spec(name) is not None:
                return name
        except (ImportError, ModuleNotFoundError, ValueError):
            continue
    return None


def measure_candidate_generation(ctx: Context, counts: tuple[int, ...] = (100, 1000)) -> dict[str, Any]:
    metric_id = "optimization.candidate_generation"
    found = _available_module(
        "aeroworkbench_optimization.candidates",
        "aeroworkbench_optimization.generator",
        "aeroworkbench_optimization.design_space",
    )
    if found is None:
        return skipped(
            metric_id,
            "GEN 03 candidate-generation layer is not present (issue #14 open); benchmark deferred, not faked",
        )
    return skipped(
        metric_id,
        f"GEN 03 module {found} is importable but the perf harness has not been wired to its API yet",
    )


def measure_screening_batch(ctx: Context) -> dict[str, Any]:
    metric_id = "optimization.screening_batch"
    found = _available_module(
        "aeroworkbench_optimization.campaign",
        "aeroworkbench_optimization.screening",
        "aeroworkbench_optimization.selection",
    )
    if found is None:
        return skipped(
            metric_id,
            "GEN 04 campaign/screening layer is not present (issue #15 open); benchmark deferred, not faked",
        )
    return skipped(
        metric_id,
        f"GEN 04 module {found} is importable but the perf harness has not been wired to its API yet",
    )


# ---------------------------------------------------------------------------
# context + runner
# ---------------------------------------------------------------------------


@dataclass
class Context:
    repo_root: Path
    api_dir: Path
    temp_root: Path
    deadline: float | None = None
    extended: bool = False
    only: tuple[str, ...] = ()
    python_path: str = field(default="")

    def remaining_ms(self) -> float:
        if self.deadline is None:
            return float("inf")
        return max(0.0, (self.deadline - time.monotonic()) * 1000.0)


DEFAULT_PYTHON_BENCHMARKS: tuple[Callable[[Context], dict[str, Any]], ...] = (
    measure_api_warm_request_latency,
    measure_api_cold_start_ready,
    measure_job_submit_to_preparing,
    measure_tiny_job_stage_split,
    measure_content_lookup,
    measure_dag_cache_hit_vs_miss,
    measure_process_launch_overhead,
    measure_sqlite_provenance_write,
    measure_sqlite_ledger_event_write,
    measure_artifact_hashing,
    measure_candidate_generation,
    measure_screening_batch,
)


def run_python_benchmarks(ctx: Context) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for benchmark in DEFAULT_PYTHON_BENCHMARKS:
        predicate = benchmark.__name__
        if ctx.only and not any(token in predicate or token in getattr(benchmark, "__doc__", "") for token in ctx.only):
            continue
        if ctx.remaining_ms() <= 0:
            results.append(skipped(predicate, "suite deadline reached before this benchmark ran"))
            continue
        started = time.perf_counter()
        try:
            result = benchmark(ctx)
        except Exception as exc:  # noqa: BLE001
            result = failed(f"{predicate}", f"{type(exc).__name__}:{exc}")
        result["wallMs"] = round((time.perf_counter() - started) * 1000.0, 3)
        results.append(result)
    return results


def environment_notes(temp_root: Path) -> dict[str, Any]:
    git_commit, dirty = _git_state()
    return {
        "platform": sys.platform,
        "platformRelease": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pythonVersion": platform.python_version(),
        "pythonExecutable": sys.executable,
        "cpuCount": os.cpu_count(),
        "nodeVersion": _tool_version("node"),
        "uvVersion": _tool_version("uv"),
        "gitCommit": git_commit,
        "gitDirty": dirty,
        "tempRoot": str(temp_root),
    }


def _tool_version(executable: str) -> str | None:
    resolved = shutil.which(executable)
    if resolved is None:
        return None
    try:
        completed = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True, timeout=10, check=False
        )
        text = (completed.stdout or completed.stderr).strip().splitlines()
        return text[0].strip() if text else None
    except Exception:  # noqa: BLE001
        return None


def _git_state() -> tuple[str | None, bool]:
    git = shutil.which("git")
    if git is None:
        return (None, False)
    try:
        head = subprocess.run(
            [git, "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10, check=False
        )
        status = subprocess.run(
            [git, "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10, check=False
        )
        commit = head.stdout.strip() or None
        return (commit, bool(status.stdout.strip()))
    except Exception:  # noqa: BLE001
        return (None, False)


# ---------------------------------------------------------------------------
# opt-in profiling (Section E) -- never active unless explicitly requested
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def python_profile(enabled: bool, target: Path) -> Iterator[None]:
    """cProfile the block when ``enabled`` (py-spy can be pointed at the process instead)."""

    if not enabled:
        yield
        return
    import cProfile

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield
    finally:
        profiler.disable()
        target.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(target))


__all__ = [
    "Context",
    "DEFAULT_PYTHON_BENCHMARKS",
    "REPO_ROOT",
    "SCHEMA_VERSION",
    "environment_notes",
    "failed",
    "latency",
    "measure_candidate_generation",
    "measure_screening_batch",
    "python_profile",
    "register_tiny_participant",
    "run_python_benchmarks",
    "skipped",
    "throughput",
]
