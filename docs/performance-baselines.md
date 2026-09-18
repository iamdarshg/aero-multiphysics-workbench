# Performance baselines and regression budgets

This document is the baseline record for **PERF 01/07** (issue #24). Later PERF
issues cite these numbers when they claim a speedup. It is measurement
infrastructure, not a feature: nothing here changes solver physics, validation,
provenance, or fail-closed behavior.

- Harness: `scripts/perf/perf-smoke.mjs` (Node/control-plane) + `scripts/perf/perf_suite.py` (Python orchestration).
- Regression budgets: `benchmarks/perf/budgets.json`.
- Tiered tests: `tests/perf/` (Python pytest + Node `node --test`).
- Generated reports: `benchmarks/perf/reports/` (**gitignored — never committed**).
- Profiling is opt-in and is never part of the normal test loop (see [Profiling hooks](#profiling-hooks)).

## How to run

```powershell
# One fast bounded entry point (<=60 s on a normal dev host). The package.json
# "perf:smoke" alias is owned by the integrator; see Integrator actions.
node --no-warnings scripts/perf/perf-smoke.mjs

# CI-style gate: nonzero exit when a measured budget is violated or a benchmark fails.
node --no-warnings scripts/perf/perf-smoke.mjs --fail-on-budget

# Python half only
uv run --no-sync --directory services/api python scripts/perf/perf_suite.py

# Tiered tests
node --test tests/perf/*.test.mjs
uv run --directory services/api pytest -q -k "perf"          # requires tests/perf in testpaths (see below)
uv run --directory services/api pytest -q ../../tests/perf    # works today
```

Options: `--json <path>`, `--budget-ms N` (default 60000), `--no-stack`,
`--fail-on-budget`, `--cpu-prof`.

## What is measured, and how time is split

The suite never collapses a job into one wall-clock number. A governed job is
attributed to distinct buckets:

| Bucket | Source |
| --- | --- |
| queue wait | persisted `QUEUED -> PREPARING` timestamps |
| preparation (prepare + capability probe) | `PREPARING -> RUNNING` |
| in-process execute (solver compute excluded) | `RUNNING -> PARSING` |
| parse | `PARSING -> VALIDATING` |
| validate + publish + persistence | `VALIDATING -> COMPLETED` |
| persistence (wrapped ledger/repository writes) | method-level instrumentation |
| hashing/artifact registration (wrapped `_hash_artifacts`) | method-level instrumentation |
| process launch vs compute | `ProcessSupervisor` receipt `started_at`/`finished_at` |

The lifecycle benchmark drives the **real** `NativeJobManager` state machine with
a synthetic in-process participant (`perf-tiny`, registered at runtime) whose
body is trivial, so the numbers are orchestration overhead — solver/external
compute is absent by construction, not by omission. The synthetic participant
executes the same prepare → probe → run → parse → validate → hash → publish →
persist path as a native job.

## Recorded baseline

Environment (recorded in every report): Windows `10.0.26200`, x64, 16 logical
CPUs, ~15.6 GiB RAM, Node `v24.10.0`, Python `3.12.2`, uv `0.9.6`, commit
`8a104b6` plus local PERF 01 changes. Values below are from one full
`perf-smoke.mjs` run; the host was also running concurrent work, so treat these
as conservative (slow-side) numbers. Re-run the harness to record your own.

### Node / control-plane

| Benchmark | Unit | median | p95 |
| --- | --- | --- | --- |
| `node.content_lookup` (cache get + structuredClone) | ms | 0.0032 | 0.0057 |
| `node.canonical_digest` (canonicalJson + sha256) | ms | 0.018 | 0.033 |
| `node.doctor_total` (full doctor) | ms | 3974.9 | 3974.9 |
| `api.cold_start_ready` (uvicorn subprocess → first HTTP 200) | ms | 2360.8 | 2360.8 |
| `api.warm_request_latency` (GET /health, in-process) | ms | 2.32 | 2.73 |
| `stack.cold_start_ready` (API + web `next start`) | ms | 8157.6 | 8157.6 |

Doctor per-probe (same run, cumulative ms): `spawn` 3849.2, `solverProbe`
112.7, `checkPort` 9.8, `sqliteProbe` 2.2, `fsStat` 0.6, `fsAccess` 0.2,
`apiFilesPresent` 0.4. This shows the Node doctor cost is overwhelmingly
subprocess spawn (version probes), not the filesystem or SQLite checks.

### Python orchestration

| Benchmark | Unit | value |
| --- | --- | --- |
| `lifecycle.submit_to_preparing` | ms median / p95 | 33.0 / 132.2 |
| `lifecycle.tiny_job_stage_split` (total, no solver compute) | ms median | 101.2 |
| `cache.content_lookup` (`ContentCache.get`) | ms median / p95 | 0.0038 / 0.0053 |
| `dag.cache_hit_vs_miss` (12-node DAG, all-hit) | ms median | 0.51 (miss 0.61; hit−miss ≈ +0.1) |
| `lifecycle.process_launch_overhead` | ms median | 101.3 (launch 2.0 + interpreter compute 100.0) |
| `sqlite.provenance_write` | events/s | 45.8 (per event 21.8 ms) |
| `sqlite.ledger_event_write` | events/s | 39.1 (per event 25.6 ms) |
| `artifact.hashing_throughput` (4 MiB sha256) | MiB/s | 404.1 |
| `python.suite_wall` | ms | 30072 (whole Python half) |

Tiny-job stage split (median ms), solver compute excluded:
`submit_to_preparing` 25.8, `preparing_to_running` 20.9, `running_to_parsing`
19.8, `parsing_to_validating` 14.5, `validating_to_completed` 22.6, total 101.2.
Wrapped persistence 95.8 ms across the job (overlaps the state windows); artifact
hashing 1.4 ms. The dominant lifecycle cost is committed SQLite persistence, not
hashing or parsing — exactly the kind of finding this baseline exists to expose.

### Deferred (capability absent, never faked)

- `optimization.candidate_generation` — **GEN 03** (issue #14) is not present; skipped with reason.
- `optimization.screening_batch` — **GEN 04** (issue #15) is not present; skipped with reason.

Once GEN 03/04 land, the harness will report `skipped: "...importable but not wired yet"`
rather than a fabricated figure until PERF 02–07 (or a follow-up) wires the real API.

## Regression budgets

`benchmarks/perf/budgets.json` holds the initial ceilings. They are deliberately
generous: the deterministic microbenchmark budgets catch order-of-magnitude
(typically >3–10x) regressions, while the cold-start budgets only catch hangs.
CI must not assert "faster than an absolute laptop number" where host variance
dominates; the floors for SQLite/hashing are set at ~1/4 of the conservative
observed numbers so a contended host does not flake.

`--fail-on-budget` exits nonzero when a measured value crosses its budget or a
benchmark errors. Skipped benchmarks never fail the gate. The report JSON records
the commit, Node/Python/uv versions, CPU count, iterations, median/p95,
bytes/items where relevant, and the cold/warm flag.

## Profiling hooks

Opt-in only; none of this runs in the default suite:

- **Python**: `uv run --directory services/api python scripts/perf/perf_suite.py --profile`
  writes a cProfile dump to `benchmarks/perf/reports/perf-python.prof`. `py-spy`
  can attach to the same process (`py-spy record -- uv run ... perf_suite.py`).
- **Node**: `node --cpu-prof scripts/perf/perf-smoke.mjs` profiles the
  orchestrator; `AERO_PERF_PROFILE=1` additionally records a
  `node.event_loop_delay` benchmark (mean/max event-loop delay).

## What must not change

Measurements only. PERF 01 does not weaken provenance, validation, quality
gates, fail-closed behavior, or scientific fidelity, and it starts no long-lived
servers (cold-start servers are bounded and terminated) and uses **no cloud
compute**.

## Integrator actions (files not owned by this workstream)

1. Add the alias to `package.json` scripts:
   `"perf:smoke": "node --no-warnings scripts/perf/perf-smoke.mjs"`.
2. Add `"../../tests/perf"` to `[tool.pytest.ini_options].testpaths` in
   `services/api/pyproject.toml` so `pytest -k "perf"` collects the tiered tests.
   (The suite already runs via `pytest ../../tests/perf`.)
3. Optionally add `benchmarks/perf/reports/` to `.gitignore` (already covered by
   `benchmarks/perf/.gitignore`).

## GCP spend

None. Every benchmark is local and bounded; estimated spend **$0.00**, actual
spend **$0.00**.
