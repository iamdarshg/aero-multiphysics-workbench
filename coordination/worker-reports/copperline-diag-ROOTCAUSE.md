# copperline — "181 unattempted routes with expansions = 0" — root cause

**Verdict: ROOT CAUSE FOUND.** It is a **scheduler starvation / budget-accounting defect**, not a
routing-capability limit. The geometric search never ran on those tasks because **they were never
placed into a worker batch**. The epoch loop terminates on `epoch >= max_epochs` while tasks remain
unscheduled, and the failure attribution then records those never-scheduled tasks as
`unattempted` with `expansions = 0`.

| | |
|---|---|
| Repo | `E:\engineering-portfolio-audit\repos\copperline`, branch `work/2026-11-11` @ `e2af5c8` |
| Board | `rp2040_game_con` = `docs/validation/corpus/2026-10-29/boards/b019_stripped.json` |
| Budget | `--max-epochs 12 --max-search-nodes 200000 --timeout 1800 --threads 4 --seed 1` |
| Result | `INCOMPLETE`, exit 7, 22.7 s, 0 DRC violations |

---

## 1. Reproduction

```
router route docs/validation/corpus/2026-10-29/boards/b019_stripped.json \
  --json --no-board-echo --seed 1 --threads 4 --memory-budget-mb 512 \
  --max-epochs 12 --max-search-nodes 200000 --timeout 1800 \
  --report evidence/copperline-diag/reports/b019.rep.json
```
Log: `logs_b019_stdout.json`, `logs_b019_stderr.txt`.

Report: **36 failures** → **34 with `expansions: 0`** (exactly the 34 predicted), **2** with
expansions (1847 and 15). The finding's `modes_attempted` / `ripup_attempts` reproduce exactly.

Note on naming: the report's `reason` is `unattempted`, not the literal `no_candidate`. The string
`no_candidate` at `src/engine.cpp:596` is a *different* field (escape-stage reason). The
"produced no candidate" wording in the finding is `best_partial`. Corrections to the brief are
flagged in §6.

### Verbatim record (`failures[0]`, 34 identical in shape)

```json
{
  "attempted_layers": [0, 1],
  "attempted_via_classes": ["STD"],
  "best_partial": "unattempted: no worker candidate produced",
  "candidate_count": 1,
  "centre_depth": 0,
  "dst_component": "C4", "dst_pin": "1",
  "expansions": 0,
  "hierarchy": {"coarse_expansions": 0, "exact_expansions": 0,
                "fallback": false, "fallback_reason": "none",
                "levels_used_mm": [], "window_attempts": 0},
  "modes_attempted": ["FAST", "RECOVERY", "EXHAUSTIVE_LOCAL_RECOVERY"],
  "net": 0, "net_name": "GND",
  "reason": "unattempted",
  "ripup_attempts": 1,
  "src_component": "U3", "src_pin": "19",
  "terminal_a": 28, "terminal_b": 0,
  "blockers": ["trace:net=+3.3V", "trace:net=Net-(U3-XIN)",
               "trace:net=/GPIO_14", "trace:net=/GPIO_15"]
}
```

---

## 2. Code path

| Step | Location |
|---|---|
| Failure record built; `expansions` copied from `last_attempt` | `src/engine.cpp:2577-2610` |
| `if (!last)` → `reason = "unattempted"` | `src/engine.cpp:2579-2580` |
| `best_partial = "unattempted: no worker candidate produced"` | `src/engine.cpp:2691-2692` |
| `last_attempt[...]` is written **only** for batched tasks | `src/engine.cpp:1531` |
| Batch selected per epoch | `src/engine.cpp:1243-1246` → `select_interference_batch` `src/parallel.cpp:375` |
| Epoch loop condition `epoch < options_.max_epochs` | `src/engine.cpp:1074` |
| Loop falls through when the epoch cap is hit (no failure record, no timeout) | `src/engine.cpp:1656-1657` |
| Recovery escalation FAST→RECOVERY→EXHAUSTIVE_LOCAL | `src/engine.cpp:1677-1681`, `src/recovery.cpp:21` |
| Recovery branch A* call (where expansions accrue) | `src/recovery.cpp:770-773` |
| Escalation gate: recovery only retries tasks in `remaining` that `last_attempt` knows | `src/engine.cpp:1747-1752`, `src/recovery.cpp:455+` |

**Why `expansions` stays 0:** `last_attempt` has no entry for the task (`last == nullptr`), so the
`else if (last && !last->found)` branch that copies `f.expansions = last->expansions`
(`src/engine.cpp:2607-2610`) is never reached. `expansions` keeps its default `0`. The null
frontier follows from the same branch: `f.frontier = diagnose_task(...)` at `:2616` is also skipped.

**Why `ripup_attempts = 1` and `modes_attempted` is full despite no search:** these are
*run-global*, not per-task.

- `src/engine.cpp:2634`: `f.ripup_attempts = rit != ripup_attempts.end() ? rit->second : (rec.generations > 0 ? 1 : 0);`
  — any task with **no** ripup record gets a bare `1` once *any* recovery generation ran.
- `src/engine.cpp:2635`: `f.modes_attempted = rec.modes_attempted;` — copies the whole-run mode
  list onto *every* failed task unconditionally.

So the `ripup_attempts > 0` + full `modes_attempted` evidence is an **attribution artifact**, not
evidence that these tasks were searched. This is the exact trap that made the defect look like an
engine-capability limit.

**Why recovery never rescued them:** `build_dependency_graph` and the ripup attribution read
`last_attempt` (`src/engine.cpp:1747-1752`). A task that was never scheduled has no `last_attempt`
entry, so it contributes no dependency edges and is never selected as a ripup target — it can never
enter `to_route` (`src/engine.cpp:1855-1875`). Recovery therefore escalates through all three modes
re-routing only the tasks that *did* run.

---

## 3. Instrumentation (observed, not inferred)

The tracked tree was **not modified**. Tree copied to
`evidence/copperline-diag/scratch/copperline-diag` (git + build dirs excluded) and instrumented
there; built with `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release` into `build-diag` (exit 0).
Three probes, gated on `DIAG_FAILTRACE=1`:

1. `DIAGEPOCH` / `DIAGBATCH` — loop entry and batch size vs `remaining` size.
2. `DIAGLOOP_EXIT` — which loop-exit condition fired, and whether `remaining` was non-empty.
3. `DIAGFAIL` — per failure record: `has_last`, `last_epoch`, `fail_count`, `second_wind`.

### Output (`logs_diag_stderr.txt`)

```
DIAGEPOCH enter epoch=0 remaining=95 max_epochs=12
DIAGBATCH epoch=0 remaining=95 eligible_ordered=95 batch_n=8 max_epochs=12
DIAGEPOCH enter epoch=1 remaining=87 max_epochs=12
DIAGBATCH epoch=1 remaining=87 eligible_ordered=87 batch_n=8 max_epochs=12
DIAGBATCH epoch=2 remaining=77 eligible_ordered=77 batch_n=8 max_epochs=12
DIAGBATCH epoch=3 remaining=69 eligible_ordered=69 batch_n=5 max_epochs=12
DIAGBATCH epoch=4 remaining=62 eligible_ordered=62 batch_n=5 max_epochs=12
DIAGBATCH epoch=5 remaining=56 eligible_ordered=56 batch_n=3 max_epochs=12
DIAGBATCH epoch=6 remaining=51 eligible_ordered=51 batch_n=3 max_epochs=12
DIAGBATCH epoch=7 remaining=48 eligible_ordered=48 batch_n=2 max_epochs=12
DIAGBATCH epoch=8 remaining=45 eligible_ordered=45 batch_n=3 max_epochs=12
DIAGBATCH epoch=9 remaining=41 eligible_ordered=41 batch_n=3 max_epochs=12
DIAGBATCH epoch=10 remaining=39 eligible_ordered=39 batch_n=2 max_epochs=12
DIAGBATCH epoch=11 remaining=37 eligible_ordered=37 batch_n=3 max_epochs=12
DIAGLOOP_EXIT epoch=12 remaining=36 max_epochs=12 hit_epoch_limit=1 stalled=0
```

`DIAGFAIL` aggregate: **34 records `has_last=0 last_epoch=-1`**, 2 records with `has_last=1`.

`last_epoch[i]` is initialised to `-1` (`src/engine.cpp:847`) and assigned only at
`src/engine.cpp:1247` for tasks in the batch. **`last_epoch = -1` is a direct, independent proof the
task was never scheduled.** `fail_count = 0` and `second_wind = 0` on the same records confirm the
task never went through any batch (`fail_count` only rises at `src/engine.cpp:1568`).

### Two independent confirmations from the unmodified binary

- Epoch batches: 53 batch slots total, but only **51 distinct** task indices — versus
  `stats.tasks_total = 85`. **34 tasks were never batched**, matching the 34 `expansions = 0`
  failures exactly (85 = 49 routed + 36 failed).
- `stats.expansions = 138280` while `sum(epoch_log.expansions) = 34266` — recovery *did* do real
  A* work (~104k expansions). The engine was searching; it just was not searching the 34.

### The arithmetic

- Task queue at epoch 0: **95 candidate tasks** (85 in final accounting after tree regeneration).
- Batch width `kParallelBatchSize = 8` (`include/router/parallel.h:134`, `maturity.h:220`).
- Wells under 8: epochs 3-11 shrink to 5, 5, 3, 3, 2, 3, 3, 2, 3 — of 95 tasks, 53 slots delivered.
- The loop runs at most `max_epochs = 12` (from the manifest budget) and then exits at
  `src/engine.cpp:1656-1657`. 53 < 95, so 34+ tasks are left unscheduled.
- Note `hit_epoch_limit=1` and `stalled=0`: the loop did **not** stall out and was **not**
  deadline-limited (`timed_out = false`). It stopped purely on the epoch cap, while progress was
  still being made (epoch 11 accepted 1, epoch 2 accepted 7). The cap ends the loop at a point
  where the run is healthy, not exhausted.

---

## 4. Trigger characterization

Distribution of the 34 `expansions = 0` records:

| Dimension | Distribution |
|---|---|
| `reason` | `unattempted` 34/34 |
| `best_partial` | `"unattempted: no worker candidate produced"` 34/34 |
| `net_name` | **GND 27**, **+3.3V 7** — 100% power/ground |
| `dst` | **C4.1 (GND) 27**, **C3.1 (+3.3V) 7** — a single shared sink per net |
| `terminal_b` | `0` (27×), `2` (7×) — one common tiny value |
| `has_last` / `last_epoch` | `0` / `-1` — **never scheduled** (instrumented) |
| `hierarchy.coarse_expansions` | 0 |
| `hierarchy.window_attempts` | 0 |
| `layers` | `[0, 1]` — all layers, not layer-specific |
| `escape_infeasible` blockers | **0/34** — none of the endpoints are in the escape-infeasible set |

The common factor is not geometry, layer, or board edge. It is **task multiplicity on one net**:

- GND and +3.3V are the high-fanout nets. Every one of the 34 tasks targets the *same* sink pad
  per net (C4.1 / C3.1), i.e. they are the many sibling connections of a single power tree.
- `select_interference_batch` enforces **`one task per net`** (`src/parallel.cpp:412`,
  and again in both relaxation sweeps at `:439` and `:451`).
- So per epoch at most **one GND task and one +3.3V task** can enter a batch, regardless of batch
  width. 27 GND tasks need ≥27 epochs; the budget allows 12. The batch needs no congestion at all
  to starve these — the per-net rule caps them structurally.
- The interleaved shrink (8→5→3→2) is the same effect: as the remaining set becomes dominated by
  the GND/+3.3V backlogs, fewer *distinct nets* remain, so the per-net rule binds tighter and the
  batch can no longer fill width.

This also explains why it is board-class-specific: boards whose completion depends on many
many-terminal power-tree joins (the "gave-up" class) hit the cap; boards where the power tree is
resolved by the escape/plane path do not.

**Ruled out** (each contradicts a measurement):
- *Not a geometric dead-end*: only 5/390 terminals are unescapable; none of the 34 have
  `escape_infeasible` blockers.
- *Not a search budget*: `max_search_nodes` 200000 was never approached; the 34 ran zero nodes.
- *Not a timeout*: `escape.timed_out = false`, `report.status = BUDGET_EXHAUSTED` via `budget_hit`
  set at `src/engine.cpp:2042` (recovery exhausted), not via the deadline path.
- *Not layer- or edge-specific*: `attempted_layers = [0,1]` on every record; `centre_depth = 0`.
- *Not a candidate generator producing an empty seed list* (the brief's hypothesis): the A* was
  never invoked for these tasks at all, so no seed list was ever requested. Confirmed by
  `last_epoch = -1`.

---

## 5. Smallest proposed fix (not implemented)

**Primary — do not end the run with never-scheduled tasks.** In `src/engine.cpp`, after the epoch
loop (~`:1656`), the loop exit on `epoch >= options_.max_epochs` must not be treated as an exhausted
search. Two candidate minimal forms:

- **(a) Prefer the fix at the cap.** Make `max_epochs` a *stall* cap rather than an absolute cap:
  keep iterating while `remaining` still contains tasks with `last_epoch[i] == -1` (they have never
  been tried), and require the stale-priority ordering (`last_epoch[a] < epoch - 1`,
  `src/engine.cpp:1165-1167`) to drain them. Since that comparator already sorts never-tried tasks
  first, the mechanism already exists — it is only the loop cap that truncates it.
- **(b) Alternatively, cost the cap correctly.** If an absolute cap is required for
  determinism/bounded runtime, the exit must mark the leftover tasks `budget_exhausted` (not
  `unattempted`) and set `budget_hit`, so the report stops claiming the engine failed to find a
  candidate when it never looked. This is honest-reporting only; it does not route anything.

**(a) is the smallest fix that changes outcomes**, and it is still small: one loop-condition change
plus a "never attempted" predicate. A complementary change removes the structural starvation:
relax `one task per net` (`src/parallel.cpp:412`) to allow a bounded number (e.g. 2-4) of
same-net tasks per batch once their corridors provably do not interfere, or allow extra same-net
tasks to exploit unused width after the distinct-net sweep cannot fill it.

**What the 181 tasks would do instead:** they would receive a real worker batch slot and a genuine
`route_candidate_task` call. They would then acquire a `last_attempt` entry with real
`expansions`/`frontier` — either complete, or fail with a truthful `unreachable` /
`frontier_gap_mm` / `budget_exhausted` attribution instead of the current
`unattempted: no worker candidate produced`. Recovery would also be able to rip in their
neighbourhood, since they would then appear in the dependency graph. Whether their *connectivity*
improves depends on geometry and is not guaranteed by this fix; what is guaranteed is that the
report no longer attributes a scheduler bug to the geometric search.

---

## 6. Corrections to the brief

1. `reason` is `"unattempted"` (not `no_candidate`). `no_candidate` at `src/engine.cpp:596` is an
   **escape-stage** reason string, unrelated to task routes.
2. `expansions = 0` records have **no frontier at all**: `has_frontier` is absent/false because
   `diagnose_task` is skipped for null `last` (`src/engine.cpp:2611-2617`).
3. `ripup_attempts > 0` and `modes_attempted = (FAST, RECOVERY, EXHAUSTIVE_LOCAL_RECOVERY)` are
   **run-global values broadcast onto every failure** (`src/engine.cpp:2634-2635`). They do not
   indicate the task was searched. This is the key reason the finding was misread as a
   capability limit, and item 3 is arguably a second, independent reporting defect.
4. The brief's hypothesis (search returns early before the expansion loop, e.g. a geometry/port/
   keepout pre-check or an empty seed list) is **falsified** for these records: control never
   reached the candidate generator.

## Log inventory

| File | Contents |
|---|---|
| `reports/b019.rep.json` | unmodified-binary per-board report (36 failures) |
| `reports/b019.diag.rep.json` | instrumented-binary report (identical geometry) |
| `logs_b019_stdout.json` / `logs_b019_stderr.txt` | build-router run logs |
| `logs_diag_stderr.txt` | `DIAG*` instrumentation trace |
| `logs_diag_stdout.json` | instrumented run stdout |
| `scratch/copperline-diag/` | instrumented source copy + `build-diag` (tracked tree untouched) |