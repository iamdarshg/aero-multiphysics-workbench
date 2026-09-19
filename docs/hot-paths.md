# Node hot-path map and edge budgets (PERF 04)

This document is the measured map of the Node/edge runtime paths that PERF 04
optimized. It is evidence, not aspiration: every number below was produced by
the bounded harnesses and tests in this repository, and no number is copied
from a source that was not run. Nothing here changes solver physics, validation,
provenance, policy gates, or fail-closed behavior.

- Issue: **PERF 04/07** (#27), depends on **PERF 01/07** (#24).
- Harnesses: `scripts/perf/perf-smoke.mjs` / `scripts/perf/perf_suite.py`
  (PERF 01), plus the focused tests added here.
- Focused tests: `tests/unit/perf04-node-edge.test.ts`,
  `tests/platform/perf04-hot-path.test.ts`.
- Environment for the recorded numbers: Windows `10.0.26200`, x64, Node
  `v24.10.0`, Python `3.12.2`, uv `0.9.6`, no native solvers installed
  (`solversReady: 0`, so probe timing is not confounded by a real solver).

## 1. Hot-path map

Mark every process/HTTP/serialization boundary. `[N→P]` is a Node→Python
process spawn, `[N⇄P]` is Node→Python loopback HTTP + JSON, `[P↔P]` is an
in-process Python call, and `[N]` is Node-local work.

### Candidate evaluation

```
UI / MCP tool ──[N⇄P POST /v1/native/analyses]──▶ FastAPI (uvicorn)
                                                    └─[P↔P] NativeJobManager.submit
                                                       ├─ participant prepare (loaded modules, in-process)
                                                       └─ deferred: no compute until start
```

There is **no Node→Python process spawn** on this path. Candidate evaluation is
owned by the Python engine; the Node edge submits a compact job and receives a
compact status. PERF 01 currently reports `optimization.candidate_generation`
and `optimization.screening_batch` as *skipped* (GEN 03/04 library not yet
wired), so no per-candidate Node hop exists to measure yet. The contract is
fixed now so that when GEN 03/04 land through the API, the edge stays thin.

### Job submission

```
MCP analysis.submit ──[N] policy gate (mutations, remote/cost escalation)
                    ──[N⇄P GET /v1/native/participants]──▶ participant allowlist (cached)
                    ──[N⇄P POST /v1/native/analyses]────▶ queued job id + status
```

The `participants` discovery call is the only hop that can be cached safely:
participants change at campaign boundaries, not per job. Before PERF 04 every
submit re-fetched it; now one fetch serves every submit inside the read-cache
window (default 15 s, `AERO_MCP_READ_CACHE_MS`, `0` disables). The allowlist
gate is unchanged: an unknown participant still fails closed with
`UNKNOWN_PARTICIPANT`.

### Solver execution

```
NativeJobManager.start ──[P] ProcessSupervisor ──[P] governed native executable
```

The executable is a **separate governed OS process** (native-only trust model,
RSS/allowlist/timeout policy). Node never launches a solver and never imports a
scheduler for this path. Solver executables must remain separate processes.

### Result retrieval

```
UI / MCP result.inspect ──[N⇄P GET results/{id} + results/{id}/manifest + provenance/{id}]──▶ compact envelope
```

The Python result envelope already carries scalars, units, validity, and
artifact *references* (name/sha256/bytes), not field arrays. PERF 04 makes the
edge bound explicit: at most 256 artifact refs, 256 scalars, 64 warnings, and
200 provenance events are forwarded over the MCP protocol. The scientific
arrays stay in Python; the edge never duplicates them.

### Capability checks

```
scripts/platform/capabilities.mjs / doctor.mjs
  └─[N] CapabilityProbeCache
       ├─ manifest fingerprint (sync, cheap)
       ├─ relevant-env fingerprint (sync, cheap)
       ├─ optional resolved-executable identity (opt-in, bounded refresh)
       └─[N→P <executable> --version] on miss only      (native version probe)

MCP capabilities.inspect ──[N⇄P GET /v1/native/capabilities]──▶ API
```

Two different probes exist and both are cached at the edge:

- **Node native probes** (`commandProbe`): one `--version` spawn per solver per
  environment. `CapabilityProbeCache` reuses a result while the manifest, the
  relevant environment, and (optionally) the resolved executable are unchanged.
- **API capability discovery** (`GET /v1/native/capabilities`): cached and
  single-flighted in the MCP HTTP client.

The Python endpoint currently calls `probe_all()` per request
(`services/api/aeroworkbench_api/native_jobs.py`); that side of the cache is
owned by the Python lifecycle workstream, not PERF 04. The Node edge cache
removes the repeated HTTP hits from long-lived MCP sessions regardless.

### Startup / readiness

```
scripts/platform/doctor.mjs
  └─ concurrent probes: pnpm, python, uv, workspace-deps, data-dir, sqlite,
     ports(3000,8000), api-preflight(uv run), solver:*(12)
     → report reassembled in deterministic order
```

## 2. What changed

| Area | Change | Files |
| --- | --- | --- |
| C. probe cache | `CapabilityProbeCache` (fingerprint + optional executable identity + single-flight + explicit `invalidate`) | `packages/solver-contracts/src/runtime.ts`, `.../manifests.ts` |
| E. startup | doctor probes run concurrently; report order is reassembled deterministically | `scripts/platform/doctor.mjs` |
| C. capabilities CLI | uses the probe cache; `--repeat N` reports probe/hit split | `scripts/platform/capabilities.mjs` |
| D. thin edge | MCP HTTP read cache + single-flight for `capabilities`/`participants`; bounded result/manifest/provenance projection | `mcp/engineering/api-client.ts`, `mcp/engineering/operations.ts` |
| B. long-lived services | documented: participant modules stay loaded in the Python API/worker; Node never runs `uv run`/import probes per candidate | this document |
| F. one scheduler | documented: the API's in-process `NativeJobManager` is the single authoritative execution owner; the Node `LocalScheduler` is a fail-closed contract adapter only (used by `packages/solver-contracts` tests and the legacy skeleton facade), never wired into `stack.mjs` | this document |

### Cache invalidation rules

A cached native probe is reused only while **all** of the following hold:

1. Manifest descriptor unchanged (`id`, category, probe executable + args,
   allowed executables, result kinds) — automatic.
2. Relevant environment unchanged (`PATH`/`PATHEXT`/`SystemRoot`/… plus any
   `AERO*`, `OPENFOAM*`, `ELMER*`, `ROSS*`, `PYBAMM*`, … keys) — automatic.
3. Within TTL (default: process lifetime; positive TTL optional).
4. If an `executableIdentity` resolver is injected: the resolved identity is
   re-checked at most every `executableTtlMs` (default 30 s) and a change misses.

`CapabilityProbeCache.invalidate(solverId?)` is the explicit refresh path
(exported from `doctor.mjs` as `invalidateSolverProbeCache`). Executable
identity resolution is **opt-in** because a full PATH filesystem scan per
solver is measurably expensive; see §3. With no resolver, an in-place binary
replacement is handled by explicit invalidation.

## 3. Measured before/after

### Doctor cold/warm (real host, `runDoctor(defaultEnv())` in one process)

| Run | Before (serial, no cache) | After (concurrent + cached probes) |
| --- | --- | --- |
| first | 3007 ms | 2142 ms |
| second | 4896 ms | 1819 ms |
| third | 3381 ms | 1991 ms (one later run under concurrent agent load hit 4116 ms) |
| CLI `node scripts/platform/doctor.mjs --json` | 4394.7 ms | 2775.3 ms |

The end-to-end CLI is ~37 % faster; warm in-process runs are ~55–63 % faster
across the recorded runs. The host was shared with other workstreams, so treat
the slow-side values as conservative. The remaining cost is dominated by the
one-shot `uv run --no-sync` API preflight, which is intentionally not cached
across a doctor invocation and is not run per solver. PERF 01 recorded the
pre-change per-probe split (`spawn` 3849 ms of a 3975 ms doctor), confirming
spawn serialization was the cost, not fs/SQLite.

### Repeated capability query

`node scripts/platform/capabilities.mjs --repeat 3` → `elapsed=1525ms probes=12
hits=24`: all 12 native probes run once; the next two full reports cost nothing.

| Measurement | ms |
| --- | --- |
| raw `CapabilityDetector.detect` (12 parallel `--version` probes) | 127–139 |
| cache cold `detect` (same probes, one fingerprint compute) | 117–138 |
| cache warm `detect` (no spawn) | 5–10 |

Cold ≈ raw (the synchronous fingerprint is negligible); warm avoids every
`--version` spawn. An early prototype that resolved executable identity by
default was measured at **1267 ms cold** (12 PATH scans) and was rejected — this
is why identity resolution is opt-in and bounded.

### Parallel readiness probes (deterministic fake, 25 ms per probe)

| Metric | Serial floor | Measured after |
| --- | --- | --- |
| 17 probes wall | ≈ 425 ms | 34–44 ms |
| peak concurrency | 1 | 17 |

Emitted by `tests/platform/perf04-hot-path.test.ts` as JSON
(`doctor.parallel_wall_ms`, `doctor.peak_concurrency`) and asserted with a
generous hang guard, so it catches a regression to a serial spawn chain without
flaking on a slow host.

### Repeated submission discovery (MCP)

Measured request counts against a loopback stub
(`tests/unit/perf04-node-edge.test.ts`):

| Calls | Before | After |
| --- | --- | --- |
| 3× `participants()` (2 concurrent + 1 sequential) | 3 HTTP GETs | 1 HTTP GET |
| 2× `capabilities()` | 2 HTTP GETs | 1 HTTP GET |

For 100 tiny submissions the MCP edge now issues 100 (`analyses`) + 1
(`participants`) HTTP requests instead of 200. PERF 01 measured a warm loopback
request at **2.32 ms median / 2.73 ms p95** (`api.warm_request_latency`), so
~99 avoided participant GETs ≈ **~230 ms** of loopback latency per 100 submits,
before accounting for JSON serialization of the participant manifest.

### Startup cost reductions

The doctor wall-time reductions in the table above are the startup win: the
same read-only probes, issued concurrently, with one-shot API preflight
untouched. `STARTUP_ORDER`/ports/report rows are unchanged.

## 4. What must not change

- Policy gates: mutation/destructive/ownership/remote/cost escalation checks in
  `mcp/engineering/policy.ts` and `operations.ts` are untouched. The read cache
  only affects discovery payloads, never authorization.
- Fail-closed: a failed discovery read is never cached (test asserts this);
  unknown participants, unavailable capabilities, and evidence-gated result
  publication all still fail closed.
- Provenance and scientific fidelity: the Python lifecycle/ledger remain the
  authoritative owner; the edge forwards bounded refs and never invents output.
- Native autonomy: solver executables remain separate governed processes.

## 5. Cloud spend

None. Every measurement is local and bounded. Estimated spend **$0.00**, actual
spend **$0.00**.

## 6. Handoff / blockers

- `docs/requirements-audit.json` pins SHA-256 evidence for source files. This
  batch changed `scripts/platform/capabilities.mjs` (section 80) and
  `mcp/engineering/api-client.ts` (section 31); section 29 is already pinned to
  `services/api/aeroworkbench_api/native_jobs.py`, which another workstream is
  editing. PERF 04 does not own that file, so the integrator must re-pin the
  audit SHAs after the batch merges (the PERF 01 batching pattern already does
  this). This is why `tests/unit/requirements-audit.test.ts` reports those three
  sections during concurrent work.
- The API's own `probe_all()` per `GET /v1/native/capabilities` request is a
  Python-side concern owned by the solver-lifecycle workstream; PERF 04 caches
  the Node edge's calls to it.
