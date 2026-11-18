# Copperline — engineering audit (worker agent report)

**Repo:** `E:\engineering-portfolio-audit\repos\copperline`
**Branch:** `work/2026-11-11` @ `e2af5c8` (base `origin/info-dump/2026-11-10-handoff`)
**Binary:** `build\router.exe`, built 2026-11-11 23:16:37 — verified **not stale**: 0 files under `src/` or `include/` are newer than it.
**Tracked files modified:** none (`git status --porcelain tests/ docs/ src/ include/` is empty). Every number below comes from a saved log in this directory.
**Constraint honoured:** `origin/audit/copperline` was read only through `git show` / `merge-base`. It was never checked out or modified.

---

## Headline

| Claim under audit | Verdict on this clone |
|---|---|
| "42/52 boards COMPLETE+legal (80.8% / 82.4% of 51)" | **Not reproducible, and not a claim this repo makes.** No 52-board denominator exists here. The clone's campaign has **10** boards. |
| ctest `-LE campaign` = 33/33 | **Reproduced: 33/33, 0 failed.** |
| Legal gate PASS 4/4, 0 violations | **Reproduced: PASS 4/4, 0 violations,** exit 0. |
| Completion gate FAIL 0/4 | **Reproduced: FAIL 0/4,** exit 1. Expected FAIL confirmed. |
| Dominant failure cause | **89.6% "produced no candidate"** — and those records carry `expansions=0`. This is an **algorithmic/bookkeeping** failure, not a geometric one. |
| Concurrency race fix (`9f3bc10`) | **The race is real and structurally present in this tree.** The fix and its stress test live **only** on `tannmay-python`'s branch. |

---

## Task 1 — What corpus is actually available

Artifacts: `task1_corpus_inventory.py`, `task1_corpus_inventory.txt`, `task1_boards21_reachability.log`

### `tests/corpus_manifest.json`

| property | value |
|---|---|
| boards | **10** |
| tier `short` | **4** |
| tier `long` | **10** (the 4 short ones are also long) |
| budget | 12 epochs / 200 000 search nodes / timeout 1800 |

The 6 long-only boards: `interf_u`, `tinytapeout-demo`, `Pico 2 C`, `RPI-PICO-R3a`, `Pico WH`, `OpenJBOD-RP2040`.

### Board input files on disk

`docs/validation/corpus/2026-10-29/boards/` holds **15** files: `b003, b007, b008, b009, b010, b011, b012, b013, b014, b015, b016, b017, b018, b019, b020`.

- **5 files on disk are not in the manifest** (`b009, b013, b014, b015, b016`). The harness only routes what the manifest lists, so these are inert.
- **Missing manifest inputs: 0.** All 10 referenced inputs exist.

Per-entry check — every manifest `input` path resolved:

| name | short | long | input | exists |
|---|---|---|---|---|
| interf_u | – | yes | boards/b003_stripped.json | OK |
| tinytapeout-demo | – | yes | boards/b007_stripped.json | OK |
| pico-radio-9-kotoldalas | yes | yes | boards/b008_stripped.json | OK |
| Pico 2 C | – | yes | boards/b010_stripped.json | OK |
| RPI-PICO-R3a | – | yes | boards/b011_stripped.json | OK |
| Pico WH | – | yes | boards/b012_stripped.json | OK |
| KiCAD_Board_3 | yes | yes | boards/b017_stripped.json | OK |
| rp2040_nema | yes | yes | boards/b018_stripped.json | OK |
| rp2040_game_con | yes | yes | boards/b019_stripped.json | OK |
| OpenJBOD-RP2040 | – | yes | boards/b020_stripped.json | OK |

### Can 52 boards be evaluated here? **No.**

- The only campaign manifest has **10** entries; **10** are evaluable (4 short, 10 long).
- No 52-entry board list exists anywhere in the tree.
- `docs/validation/corpus.md:25` describes a *historical* curated set of 52 boards (20 KiCad demos + 14 open-hardware + 4 local + 14 synthetic) — a composition list, not a runnable manifest.
- The frozen result files are historical rows, and none has 52 entries:

| file | entries | input_legal | COMPLETE+legal |
|---|---|---|---|
| curated.json | 38 | 26 | 9 |
| bench180.json | 21 | 21 | 11 |
| wide.json | 118 | 4 | 1 |
| synthetic.json | 15 | 15 | 12 |

- The 21-board list (`boards21.txt`) cannot be re-run in place either: **8 of 21** source paths remain, **13 are gone** (temp checkouts). Of those 21, only 13 have frozen pads-only inputs, and just **10 of those 13** are wired into the campaign.

**Strongest evidence the quoted figure is fabricated or misattributed:** the repo's own flagship curated result is **11/21 = 52.4%** (`docs/validation/corpus.md:155`, README:480). "42/52 … 80.8%" shares the *52* and the *decimal* with that 52.4% but has a different numerator and denominator. **The exact strings `42/52`, `80.8`, `82.4` appear nowhere in the repository.** The closest match is an unverifiable composition doc, not a measurement.

So: a 52-board completion claim is **unfalsifiable in this clone** — you cannot check it because you cannot run it.

---

## Task 2 — Both gates on what is available

Artifacts: `task2_ctest_LE_campaign.log`, `task2_gate_legal.log`, `task2_gate_complete.log`, `task2_failure_attribution.txt`, `task2_geometry_vs_algorithm.txt`, `task2c_unattempted_shape.txt`, `task2d_no_candidate_profile.txt`, `task2e_console.log`, plus each board's raw report in `task2_reports/`.

### `ctest --test-dir build -LE campaign`

```
100% tests passed, 0 tests failed out of 33
Total Test time (real) = 550.90 sec
```

**33/33 — matches the expected result.** (`test_engine` alone is 397 s; the run is slow but green.)

### Legality gate

```
python tests/test_corpus_boards.py --tier short --gate legal --router build/router.exe
legality gate: PASS (4/4 boards legal, 0 violations)      exit 0
```

**PASS 4/4, 0 violations — matches.** All four boards report `viol 0`, `legal=True`.

### Completion gate

```
python tests/test_corpus_boards.py --tier short --gate complete --router build/router.exe
completion gate: FAIL (0/4 boards COMPLETE)               exit 1
```

**FAIL 0/4 — matches the expectation (this failure is deliberate per `HANDOFF.md`).**

### Per-board detail, parsed from the raw reports

| board | status | connected | task-routes | failed | no candidate | searched+blocked | rejected by arbiter | viol | epochs |
|---|---|---|---|---|---|---|---|---|---|
| KiCAD_Board_3 | BUDGET_EXHAUSTED | 94/198 | 85/138 | 53 | **44** | 9 | **0** | 0 | 13 |
| pico-radio-9-kotoldalas | BUDGET_EXHAUSTED | 217/340 | 177/238 | 61 | **56** | 5 | **0** | 0 | 13 |
| rp2040_game_con | BUDGET_EXHAUSTED | 79/152 | 49/85 | 36 | **34** | 2 | **0** | 0 | 12 |
| rp2040_nema | BUDGET_EXHAUSTED | 94/184 | 58/110 | 52 | **47** | 5 | **0** | 0 | 13 |
| **TOTAL** | | **484/874** | **369/571** | **202** | **181** | **21** | **0** | **0** | |

My parse was cross-checked against the harness's own printed detail string for all four boards — **MATCH** on every one.

Attribution of the 202 failed task-routes:

- produced no candidate — **181 (89.6%)**
- searched and blocked — **21 (10.4%)**
- rejected by the arbiter — **0 (0.0%)**
- unclassified — **0**

The three buckets are disjoint and exhaustive on this data.

### The important part: this is algorithmic, not geometric

The breakdown is a real discriminator, but it must be read together with three facts, each measured:

1. **Geometry is nearly irrelevant.** Of **390** unconnected terminals across the four boards, only **5** pads have no legal escape at all — **1.3%**. The other **385 (98.7%)** are not geometrically blocked (`task2_geometry_vs_algorithm.txt`).

   | board | unconnected | infeasible pads | pads | unresolved reasons |
   |---|---|---|---|---|
   | KiCAD_Board_3 | 104 | 3 | 148 | no_exit_sectors ×2, blocked_channel |
   | pico-radio-9-kotoldalas | 123 | **0** | 62 | – |
   | rp2040_game_con | 73 | 1 | 78 | blocked_channel |
   | rp2040_nema | 90 | 1 | 86 | blocked_channel |

2. **The search never ran on those 181 tasks.** Every "no candidate" record has **`expansions = 0`** and a `hierarchy` block showing guidance was never attempted. So *"produced no candidate"* does **not** mean "A* searched and found nothing"; it means the geometric search produced **nothing at all** on a task that was nonetheless marked attempted.

3. **The label is a bookkeeping state, not a physical impossibility.** The 181 records all carry `category: UNROUTABLE_UNDER_CONFIGURED_CONSTRAINTS_AND_BUDGET`, yet **all 181** show `ripup_attempts > 0` and `modes_attempted = (FAST, RECOVERY, EXHAUSTIVE_LOCAL_RECOVERY)`. The engine escalated through its strongest search modes and still registered zero expansions. Blockers are overwhelmingly movable copper: **419 trace entries, 104 pad, 3 via**.

**Conclusion:** the dominant failure mode is an **algorithmic/control-flow defect** — tasks being counted as attempted while their geometric search contributes nothing — not a geometric limitation. Only ~1.3% of the shortfall is geometry. This also means `HANDOFF.md`'s "Workstream 1" (instrument why the candidate list is empty) is the right first target, and its own hint is confirmed: `expansions=0` is the signature.

### Secondary measurement: is it one global bug or per-board behaviour?

Per-board task-route success rate at identical budget/seed/binary: **61.6%, 74.4%, 57.6%, 52.7%** (overall 64.6%, 369/571). Spread is **21.6 percentage points**; G-statistic on the 4×2 table = **19.3** (3 dof). The boards are **not** draws from one common urn, so no single global fix should be expected to close the gap — but the shared `expansions=0` signature across all four boards shows the dominant mode is nonetheless common.

### Caveats I am flagging rather than hiding

- **The four boards are survivor-biased.** The manifest is the *10 previously-incomplete boards* from a 21-board clean corpus. "0/4 COMPLETE" is therefore a property of a deliberately hard subset, not a statement about all boards. It should not be quoted as a general success rate.
- **Episodes overshoot the budget.** `stats.epochs` is 13, 13, 13, 12 against `max_epochs: 12`. `HANDOFF.md` documents this (recovery generations are logged too) and tells readers never to assert `epochs == max_epochs`, so it is expected — but it confirms the counter is not a clean budget signal.
- **`docs/validation/corpus.md` contains an internally inconsistent table** (at lines 84–88): "Boards that were VIOLATION … now finish COMPLETE" followed by "The two remaining illegal cases (`tinytapeout-demo`, `Pico 2 C`, 4 violations each)". `curated.json` records `tinytapeout-demo` as legal, so the prose is stale. Not central, but it is the kind of drift that makes the headline numbers hard to trust.
- I did **not** re-run the long tier (6 large boards, ~25 min by the repo's own estimate). It was not in scope, and the short tier already establishes the mechanism.

---

## Task 3 — The claimed concurrency race

Artifacts: `task3_race_code_evidence.txt`, `task3_stress_test_absence.log`, `task3_test_hierarchy_repeat.log`

### What the current code does

`src/hierarchy.cpp:180-211` — the function **builds the snapshot under the mutex, then returns a reference to the shared member, releasing the lock on return**:

```cpp
180: const HierarchyCache::Snapshot& HierarchyCache::snapshot_for(const Board& board) const {
181:     std::string key = snapshot_key(board);
182:     std::lock_guard<std::mutex> lock(mutex_);
183:     if (key == cached_key_) return cached_;
...
208:     cached_ = std::move(s);
209:     cached_key_ = key;
210:     return cached_;
211: }
```

`include/router/hierarchy.h:133-137` — the storage is a single mutable member:

```cpp
133:     mutable std::mutex mutex_;
134:     mutable Snapshot cached_;
135:     mutable std::string cached_key_;
136:
137:     const Snapshot& snapshot_for(const Board& board) const;
```

The only caller, `build_guidance`, holds that reference across a long loop:

```cpp
220:     const Snapshot& snap = snapshot_for(board);
...
242:     for (const auto& o : snap.obstacles) {
```

### Is the described race plausible? **Yes — and it is fully realised in this tree.**

The reasoning is closed end-to-end; every link is in the code I read:

1. **The lock does not cover the reference's lifetime.** `lock_guard` lives inside `snapshot_for`; `snap.obstacles` at `hierarchy.cpp:242` is iterated *after* the lock is gone. The mutex protects the write at line 208 but nothing protects later reads.
2. **Workers really do share one cache and iterate concurrently.** `src/engine.cpp:1957` sets `mctx.hier_cache = &hier_cache` for multiply; `src/recovery.cpp:1142-1145` spawns `std::thread` workers that each call `reroute_branch` → `route_candidate_task` → `build_guidance`, passing the same `hier_cache` (`recovery.cpp:1134`).
3. **Workers really do route different boards.** Each worker uses `parent.state.board` (`recovery.cpp:1128`), a per-branch board copy. So `snapshot_key` differs per worker, `cached_` gets clobbered, and worker A can iterate worker B's obstacle list.
4. **The consequence is a real crash, not just wrong guidance.** A foreign obstacle carries a `net` id from another board; `build_guidance` passes it to `clearance_to` → `requiredClearance`. At `src/rules.cpp:973-975`:
   ```cpp
   973:     const NetInfo* na = board_->find_net(a);
   974:     const NetInfo* nb = board_->find_net(b);
   975:     if (!na || !nb) throw std::runtime_error("requiredClearance: unknown net");
   ```
5. **That throw kills the process.** The worker lambda at `recovery.cpp:1122-1138` has **no `try`/`catch`**. An exception escaping a `std::thread` calls `std::terminate` → SIGABRT.

So the race is not hypothetical: it is *thread-visible, mutation-visible, and fatal*. Besides the crash, there is an undetected hazard: `cached_ = std::move(s)` reallocates the vector's buffer while another thread may be mid-iteration, which is straight UB regardless of content.

**A caveat on the trigger conditions.** The race needs `snapshot_key` to *differ* between concurrent workers, i.e. recovery branches whose boards differ. And crucially it needs the recovery stage to actually reach `EXHAUSTIVE_LOCAL_RECOVERY`/multiply on a board large enough to overlap. That matches the reported reproducer (`OpenJBOD-RP2040`, long tier, 4 threads, 1 abort in 7 runs) — I did **not** reproduce the abort, because OpenJBOD is long-tier and single-shot at 1-in-7 odds.

Also worth noting: `include/router/hierarchy.h:18-22` already *claims* "Sharing a `HierarchyCache` across workers never changes results… safe to share across epochs and recovery branches." The code contradicts its own documented guarantee. That is a documentation defect independent of the bug.

### The stress test `shared_cache_is_safe_across_boards_and_threads`

**Absent from this clone.** It is on `tannmay-python`'s branch, not mine.

- 0 matches for `shared_cache_is_safe` across `src/`, `include/`, `tests/`, `docs/`.
- `tests/test_hierarchy.cpp` registers only 4 tests: `maze_reduces_expansions`, `narrow_01mm_path`, `misleading_corridor_fallback`, `no_grid_staircase` — and contains **no threading constructs at all**.
- `git merge-base --is-ancestor 9f3bc10 work/2026-11-11` → **1** (not an ancestor). Against `origin/audit/copperline` → **0** (present there). Read via `git show` only; nothing checked out.

I reviewed their diff read-only. The fix (`std::shared_ptr<const Snapshot> cached_`, returning the `shared_ptr`, taking a local owner in `build_guidance`) **correctly removes the race**: each caller owns a reference-counted immutable snapshot, and replacement never frees a snapshot in use. The API change is contained to one private member and one private method, so the blast radius is small.

**Substitute run, with its limitation stated plainly:** I ran the existing `build\test_hierarchy.exe` 10× consecutively — **10/10 exited 0, `PASS: 4/4`** each time. This proves the current code is healthy on its single-threaded tests; it **cannot** exercise the race and therefore **cannot be evidence for or against the bug or the fix.**

### Verdict on Task 3

| Element of their claim | My assessment |
|---|---|
| Race exists in `snapshot_for` (reference to shared `cached_` after unlock) | **Confirmed by code inspection** — exact lines quoted above |
| Reachable via multiply workers on different boards | **Confirmed** — `engine.cpp:1957`, `recovery.cpp:1128/1134/1142-1145` |
| Failure mode is `requiredClearance: unknown net` → `std::terminate` | **Confirmed mechanism** — `rules.cpp:975`, no `try`/`catch` in the worker lambda |
| "Failed 2/3 before, passed 20/20 after" | **Not verifiable here** — test and fix are both only on their branch |
| Their fix methodology | **Sound** — shared immutable snapshot is the right shape; no fix written by me, as instructed |

---

## What I would tell the portfolio owner

1. **Drop "42/52" from anything user-facing.** It cannot be reproduced, it is not what this repo measured, and the real headline (11/21 = 52.4% on a clean corpus) is already a defensible, honest number.
2. **State the corpus precisely.** "10 hard boards, all legal, 0/10 fully routed, 89.6% of failures produced no candidate with `expansions=0`" is a maintainable engineering claim. "42/52 boards" is not.
3. **Lead with legitimacy, not completion.** The one gate that *is* green (4/4 legal, 0 violations) is the genuinely hard safety property and is worth more than the completion number.
4. **Name the leading defect honestly:** tasks counted as attempted whose search contributes zero expansions. That is a bug, and the evidence points at it far more precisely than "the boards are hard."

## Evidence index

| file | contents |
|---|---|
| `task1_corpus_inventory.py` / `.txt` / `_console.log` | manifest vs disk inventory, denominator analysis |
| `task1_boards21_reachability.log` | 8/21 frozen source paths still exist |
| `task2_ctest_LE_campaign.log` | ctest 33/33 |
| `task2_gate_legal.log` | legality gate PASS 4/4 |
| `task2_gate_complete.log` | completion gate FAIL 0/4 + full detail strings |
| `task2_run_gates.py` | drives both gates, parses reports, cross-checks harness output |
| `task2_failure_attribution.txt` / `_console.log` | per-board table + 89.6/10.4/0.0 split |
| `task2_geometry_vs_algorithm.txt` | 390 unconnected vs 5 infeasible pads (1.3%) |
| `task2c_unattempted_shape.py` / `.txt` | full record of an `unattempted` failure; `expansions=0` |
| `task2b_contract_check.txt` | harness classification predicates (`test_corpus_boards.py:138-146`) |
| `task2b_best_partial_classes.log` | `best_partial` string classes; no `frontier_gap_mm` overlap |
| `task2c_frontier_field.log` | `frontier` is `null` on unattempted failures |
| `task2d_no_candidate_profile.txt` | profile of all 181; bucket exhaustiveness |
| `task2e_console.log` | per-board success rates, G-statistic |
| `task2_reports/` | raw per-board report JSON (4 boards) |
| `task3_race_code_evidence.txt` | line-numbered race code at working tree |
| `task3_stress_test_absence.log` | 0 matches; commit only on their branch |
| `task3_test_hierarchy_repeat.log` | 10/10 runs of the existing test (not a race repro) |