"""Tiered perf regression tests.

These are bounded deterministic microbenchmarks, not "faster than an absolute
laptop number" assertions: the committed ``benchmarks/perf/budgets.json`` gate
uses generous order-of-magnitude ceilings, and these tests assert the harness
produces honest, structured, non-hanging measurements plus a couple of robust
relative invariants. They are deliberately outside the default testpaths so the
normal edit/test loop stays fast.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from perf_metrics import (
    REPO_ROOT,
    Context,
    environment_notes,
    measure_artifact_hashing,
    measure_candidate_generation,
    measure_content_lookup,
    measure_dag_cache_hit_vs_miss,
    measure_screening_batch,
    measure_sqlite_ledger_event_write,
    measure_sqlite_provenance_write,
    measure_tiny_job_stage_split,
)

BUDGETS_PATH = REPO_ROOT / "benchmarks" / "perf" / "budgets.json"
KNOWN_METRICS = {
    "median_ms",
    "p95_ms",
    "total_ms",
    "per_item_ms",
    "items_per_second",
    "mib_per_second",
}


@pytest.fixture()
def ctx(tmp_path: Path) -> Context:
    return Context(
        repo_root=REPO_ROOT,
        api_dir=REPO_ROOT / "services" / "api",
        temp_root=tmp_path,
        deadline=time.monotonic() + 30.0,
    )


def test_budget_manifest_is_well_formed() -> None:
    manifest = json.loads(BUDGETS_PATH.read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["policy"].strip()
    assert manifest["budgets"], "at least one budget is required"
    ids = [entry["id"] for entry in manifest["budgets"]]
    assert len(ids) == len(set(ids)), "budget ids must be unique"
    for entry in manifest["budgets"]:
        assert entry["id"].strip()
        assert entry["metric"] in KNOWN_METRICS, entry
        assert entry["direction"] in {"max", "min"}, entry
        assert isinstance(entry["limit"], (int, float)) and entry["limit"] > 0, entry
        assert entry["rationale"].strip()


def test_content_lookup_is_measurable_and_bounded(ctx: Context) -> None:
    metric = measure_content_lookup(ctx, entries=50, lookups=2_000)
    assert metric["status"] == "measured", metric
    assert metric["p95"] is not None and metric["p95"] < 50.0


def test_dag_cache_hit_is_not_slower_than_miss(ctx: Context) -> None:
    metric = measure_dag_cache_hit_vs_miss(ctx, nodes=8, iterations=5)
    assert metric["status"] == "measured", metric
    stages = metric["stages"]
    assert stages["hit_median_ms"] is not None and stages["miss_median_ms"] is not None
    # Relative invariant with generous slack: a cache hit must not be much
    # slower than a full recompute pass on the same machine.
    assert stages["miss_minus_hit_ms"] > -5.0, stages


def test_sqlite_write_throughput_is_measurable(ctx: Context) -> None:
    provenance = measure_sqlite_provenance_write(ctx, events=50)
    assert provenance["status"] == "measured", provenance
    assert provenance["itemsPerSecond"] is not None and provenance["itemsPerSecond"] > 1
    ledger = measure_sqlite_ledger_event_write(ctx, events=50)
    assert ledger["status"] == "measured", ledger
    assert ledger["itemsPerSecond"] is not None and ledger["itemsPerSecond"] > 1


def test_artifact_hashing_throughput_is_measurable(ctx: Context) -> None:
    metric = measure_artifact_hashing(ctx, size_mib=2, iterations=2)
    assert metric["status"] == "measured", metric
    assert metric["mibPerSecond"] is not None and metric["mibPerSecond"] > 1
    assert metric["itemsPerSecond"] is None, "byte throughput must not report a misleading items/s"


def test_tiny_job_reports_a_stage_split(ctx: Context) -> None:
    metric = measure_tiny_job_stage_split(ctx, iterations=3)
    assert metric["status"] == "measured", metric
    stages = metric["stages"]
    for key in (
        "submit_to_preparing_ms",
        "preparing_to_running_ms",
        "running_to_parsing_ms",
        "parsing_to_validating_ms",
        "validating_to_completed_ms",
        "total_ms",
        "persistence_ms",
        "hashing_ms",
    ):
        assert key in stages, key
    assert stages["total_ms"] >= 0.0


def test_gen03_gen04_defer_with_explicit_reasons(ctx: Context) -> None:
    candidate = measure_candidate_generation(ctx)
    screening = measure_screening_batch(ctx)
    # If GEN 03/04 have landed, the harness must still report honestly (either
    # measured or an explicit "not wired yet" skip), never a fabricated number.
    for metric in (candidate, screening):
        assert metric["status"] in {"measured", "skipped"}
        if metric["status"] == "skipped":
            assert metric["reason"], metric
            assert "GEN 0" in metric["reason"], metric


def test_environment_notes_record_the_host(ctx: Context) -> None:
    notes = environment_notes(ctx.temp_root)
    assert notes["pythonVersion"]
    assert notes["platform"]
    assert notes["cpuCount"] is None or notes["cpuCount"] >= 1
