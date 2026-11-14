# Does raising the epoch cap close the starvation defect (and C-G1)?

**Verdict: NO. Raising the cap changes nothing, because the cap is never the
binding constraint.** Output is bit-identical before and after
(`state_hash` equal on all four boards, identical failure lists). 0/4 boards
move toward COMPLETE. The `unattempted` / `expansions: 0` tasks are starved by
a *load-balancing* rule, not by the epoch budget.

- Repo: `E:\engineering-portfolio-audit\repos\copperline`, branch `work/2026-11-11`, HEAD `e2af5c8c`
- Tracked tree **unmodified** (`git status --short` empty — see `proof/git_status.txt`)
- Tier: short (4 boards), manifest budget 12 epochs, seed 42, threads 4
- Instrumented build: separate tree `src-tree/` + separate build `build-fix/`

---

## 1. Headline numbers (before / after)

`conn` = connected/total terminals. Raised cap = 100000 (was 4096 default).

| Board | Status (both) | conn before | conn after | Δconn | viol | epochs used | unatt `exp0` before → after | state_hash equal |
|---|---|---|---|---|---|---|---|---|
| pico-radio-9-kotoldalas | BUDGET_EXHAUSTED | 217/340 | 217/340 | **0** | 0 | 13 (cap 100000) | 56 → 56 | **yes** |
| KiCAD_Board_3 | BUDGET_EXHAUSTED | 94/198 | 94/198 | **0** | 0 | 13 (cap 100000) | 44 → 44 | **yes** |
| rp2040_nema | BUDGET_EXHAUSTED | 94/184 | 94/184 | **0** | 0 | 13 (cap 100000) | 47 → 47 | **yes** |
| rp2040_game_con | BUDGET_EXHAUSTED | 79/152 | 79/152 | **0** | 0 | 12 (cap 100000) | 34 → 34 | **yes** |
| **Total** | 0/4 COMPLETE | **484/874** | **484/874** | **0** | **0** | — | **181 → 181** | 4/4 |

The `unattempted` net breakdown is also unchanged, confirming the *same* tasks
are starved, not merely the same count: pico GND 44, KiCAD GND 21 + +3.3V 13 +
GPIO scatter, nema GND 30 + +3.3V 9 + GPIO, game_con GND 27 + +3.3V 7.

## 2. Answers to the specific questions

- **How many previously-`unattempted` tasks now get real search (`expansions > 0`)? — Zero, of 181.**
- **Do any now ROUTE / connections gained? — None. 0 connections gained on every board.**
- **Do any boards reach COMPLETE? — No. Completion gate stays 0/4. C-G1 does NOT close.**
- **Is DRC still 0? — Yes, but trivially: nothing changed.** 0 violations, 0 total across both runs; `verifier_legal: true` on all 8 runs.
- **Runtime cost of the raised budget? — None (±2%):** 158.0 s → 160.1 s total campaign; per-board 58.4→58.3 s, 32.7→31.6 s, 49.9→48.9 s, 20.9→20.0 s. Expected, since no extra epoch ever runs.

## 3. Why nothing changed — the cap is not binding

Every board terminates at epoch 12–13 regardless of a 100000 cap. The `while`
at `src/engine.cpp:1074` therefore exits via `remaining.empty()` or an inner
`break`, never via `epoch < options_.max_epochs`. The real terminators:

1. **`kMaxStalledEpochs = 4`** (`include/router/parallel.h:49`). At
   `engine.cpp:1623-1624`, if an epoch's arbiter accepts nothing
   (`arb.accepted.empty()`), `++stalled > 4` breaks immediately. Reached near
   the end (e.g. game_con ep11 acc=1 rej=2; pico ep12 acc=2 rej=7).
2. **Greedy batch width.** The arbiter considers only
   `effective_width` tasks per epoch (8, or 32 on the first epoch). Each epoch
   accepts 1–8 of them. The per-net `picked_nets` gate
   (`parallel.cpp:412/439/451`) means the 27 GND + 7 +3.3V tasks need ≥27
   epochs to be *selected at all* — but only if other tasks keep advancing.
   They do not: once non-power nets are exhausted, batches shrink to 2–4
   candidates over 2–3 distinct nets, acceptance collapses, and the stall break
   fires long before epoch 27.
3. **Recovery, not epochs, sets the final status.** All four boards run
   `recovery.generations = 4` modes ending in `EXHAUSTIVE_LOCAL`, which sets
   `budget_hit = true` at `engine.cpp:2039-2043` and `break`s. That is why the
   status reads `BUDGET_EXHAUSTED` / `SEARCH_BUDGET_EXHAUSTED_WITH_UNROUTED_CONNECTIONS`
   — it is a **search**-budget signal from the rip-up phase, not an epoch-cap
   signal. `budget_hit` has only two producers (`:1546`, `:2609`), both keyed on
   `fail_reason == "budget_exhausted"` from A* search, never on the epoch loop.

The loop is also ordered such that a starved task has *no attempt record*, so
the report falls to `engine.cpp:2579-2580` → `reason: "unattempted"` with
`expansions` left at its default 0 (`:2610` only fills it when `last` exists).
The observed `unattempted`/`expansions: 0` signature is thus real, but its
cause is that the task was never selected into a batch — not that the run ran
out of epochs.

## 4. Failure mode the fix could have introduced

**None observed, and none could surface — the code path never executes.** With
identical `state_hash` and identical failure lists on all four boards:

- DRC violations: 0 (no regression, but no added coverage either).
- Unconnected items: identical byte-for-byte; nothing new left dangling.
- Hanging: no. Longest board 58 s; campaign 160 s; all under the 1800 s guard.
- Note `verifier_ok: false` on all runs in **both** configurations — that is the
  pre-existing incomplete status, not a new failure.

## 5. Two methodology controls

1. **Equivalence control.** The instrumented binary was first run at the
   *unchanged* 12-epoch budget (`equivalence-12ep/`). Result: `state_hash`
   equal to the original binary and failure lists identical on all 4 boards.
   So the copy is a clean control and the raised-cap comparison is attributable.
2. **Cap override independent of the default.** `--max-epochs N` is applied
   unconditionally (`main.cpp:1355`) after the `:387` strategy override, and is
   validated only for `N >= 1` (`main.cpp:239`) — no upper clamp. The copy's
   default raise is therefore equivalent to a CLI override; a flag/env var was
   unnecessary.

## 6. What this means for the root cause

The established root cause is **incomplete**. The epoch cap is *a* cap, but it
is not the one that bites:

- True: one task per net per epoch (`parallel.cpp:412/439/451`) starves the
  27 GND + 7 +3.3V tasks; they are reported `unattempted` with `expansions: 0`.
- **False: that raising `max_epochs` would feed them.** The run stops at
  `kMaxStalledEpochs = 4` plus batch-width/acceptance collapse, and reports
  `BUDGET_EXHAUSTED` from the rip-up phase. A larger epoch cap cannot reach
  epoch 27.

A fix that would actually be testable against these numbers: let starved nets
advance without collapsing the batch (e.g. relax the one-task-per-net gate for
saturated power nets, or make the stall detector ignore epochs whose batch was
width-limited rather than acceptance-limited). That is a design change, not a
budget change — it should not be validated by simply raising `max_epochs`.

---

## Raw logs / artifacts

| Path | Contents |
|---|---|
| `baseline/baseline.log` | original binary, 12 epochs, gate complete — 0/4 |
| `baseline/reports/*.rep.json` | 4 baseline reports |
| `baseline/analysis.log` | per-board failure-reason histogram, starved nets |
| `equivalence-12ep/log.txt`, `reports/` | instrumented binary at 12 epochs (control) |
| `raised-cap/campaign.log` | instrumented binary, cap 100000 — 0/4, 160.1 s |
| `raised-cap/reports/*.rep.json` | 4 raised-cap reports |
| `raised-cap/analysis.log` | same analysis as baseline |
| `before_after.csv` | machine-readable before/after + equality flags |
| `proof/instrumented_diff.txt` | the single-line diff (only change) |
| `proof/git_head.txt`, `proof/git_status.txt` | HEAD + proof tracked tree untouched |
| `proof/binary_hashes.txt` | SHA-256 of both binaries |
| `analyze.py` | analyzer used to produce both analysis.log files |

Instrumented change (only edit, in the copy tree):

```diff
-    int max_epochs = 4096;
+    int max_epochs = 100000;  // fixverify: raised from 4096
```