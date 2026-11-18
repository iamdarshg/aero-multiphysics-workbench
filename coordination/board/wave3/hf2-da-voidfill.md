# hf2 · hotfix of `w2-da-voidfill` — citations, provenance, B.Cu feasibility, and the minimum move set

**Item under hotfix:** `evidence/w2-da-voidfill/REPORT.md` (367 lines), branch `work/2026-11-11`.
**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (2,252,603 B).
**Tool:** KiCad 9.0.7 `C:/Program Files/KiCad/9.0/bin/python.exe` → `pcbnew` (verified `pcbnew.Version()` = 9.0.7).
**My evidence dir:** `evidence/hf2-da-voidfill/`. **Nothing written into any repo, any other owner's dir, or any `audit/*` branch.**
**Git:** read-only. No commit, push, reset.

> **Scope note.** The three citation defects are *inside another owner's file* (`evidence/w2-da-voidfill/`).
> The board rule is "write only in your folder — never another row's directory", so I did **not** edit their
> `REPORT.md`. I supply the exact per-line patch (§1) and the corrected claims (§2–§3) here, so the lead can
> apply them or fold this report in. Everything else below is new measurement in my own dir.

---

## 0. Verdict

| # | item | verdict |
|---|---|---|
| 1 | cites `12_measure.json` (does not exist) | **FIXED** — 3 refs, patch in §1; correct target is `void_results.json` |
| 2 | calls 1.307 % "measured" | **RELABELLED** — it is a counterfactual refill; now carries a measured number proving it (§2) |
| 3 | claims B.Cu "has room" | **RESOLVED** — premise wrong, conclusion now *measured per segment*: 10 of 13 feasible, **3 blocked** (§3) |
| — | real question: minimum move set | **ANSWERED** — **1 move** + a free constraint edit = **1.962 %**. Pure copper without the edit needs **5** (§4) |

Headline: w2's 13-segment reroute is **not** the minimum fix, and it is **not** the least-effort one.
One 5.115 mm segment plus a clearance-rule edit does the job, and that single segment is the *easiest*
of all 13 to put on B.Cu (nothing of another net within 1.0 mm of it).

---

## 1. Defect 1 — citations that point at a file that does not exist

`12_measure.json` is referenced three times and **is not in the directory**. What exists is
`12_measure.py` (the script) and `void_results.json` (the data it writes):

- `12_measure.py:5` — `RES = ".../void_results.json"`
- `12_measure.py:69-71` — reads that file if present, adds `all_[tag]`, rewrites it
- listing of the dir: 28 scripts/outputs, `void_results.json` present, `12_measure.json` absent

### Exact patch for `evidence/w2-da-voidfill/REPORT.md`

| line | was | is |
|---|---|---|
| **20** | `... 9.834 % (F.Cu) / 10.96 % incl. 2 In2 segments \| \`12_measure.json\`` | `... \| \`void_results.json\` (tag \`s0\`)` |
| **25** | `\| measured after fix \| **1.307 %** void \| \`12_measure.json\` tag \`s\` \|` | `\| refilled after the proposed edit (simulated, §2) \| **1.307 %** void \| \`void_results.json\` tag \`s\` \|` |
| **247** | `` `12_measure.json`, tags `r`,`s`,`h`,`f`. `` | `` `void_results.json`, tags `r`,`s`,`h`,`f`. `` |

Lines 44, 81, 246 and 358 correctly cite `12_measure.py` (the script exists) and need no change.

**Verified that `void_results.json` holds exactly the claimed numbers** (read directly, no re-derivation):
`s0` 9.834 % / 4.1699 mm², `r` 2.010, `s` 1.307 / 0.5542, `h` 1.307, `f` 1.307, `q` 8.967, `o` 8.975.

---

## 2. Defect 2 — the 1.307 % is a simulation of the proposed edit, not a measurement

### What w2 actually did
`11_make.py:71-86` removes track segments from a **copy** of the board and `13_refill.py` refills it.
No replacement copper is added anywhere. So every variant number in w2 §5 is a *counterfactual*:
"if this copper were not there, what would the plane do". That is a legitimate experiment, and as a
*plane-response* simulation it is sound. It is not a measurement of a board that can be fabricated.

### The measured proof, not just the assertion

I added an unconnected-item count to the measurement (`GetUnconnectedCount(False)`, exact signature
confirmed: `CONNECTIVITY_DATA.GetUnconnectedCount(aVisibleOnly)`).

| variant | moves | void mm² | void % | **unconnected** |
|---|---|---|---|---|
| `s0` control, unmodified board | 0 | 4.1699 | 9.834 | **0** |
| `q` constraint edit only, no copper removed | 0 | 3.8025 | 8.967 | **0** |
| w2 `s` = my `s13` | 13 | 0.5542 | 1.307 | **7** |
| recommended (§5) | 1 | 0.8320 | 1.962 | **2** |

The unmodified board is fully routed (0). The 13-segment variant severs **7** connections. That number
is why "1.307 %" cannot be called a measurement of a fabbable board — the copper that carries
`VDD_CC112`, `RF_GPIO2` and the two GNSS nets is simply gone.

### Also a unit error, in the report and on the board
The deletion is **13 track segments**, not 13 nets. They belong to **4** nets, all on In1.Cu:

| net | segments | ids |
|---|---|---|
| `/915 MHz RF/VDD_CC112` | 7 | c00–c06 |
| `/RF_GPIO2` | 4 | c10–c13 |
| `/GNSS/GNSS_RESET_OD` | 1 | c08 |
| `/GNSS/GNSS_UART_RX_2V8` | 1 | c09 |

(plus `/GND` c07, which w2 deliberately leaves alone — I confirm it is inert, §4.3). See §8, **BOARD CORRECTION**.

### Corrected wording
> **was:** "measured after fix | **1.307 %** void"
> **is:** "**1.307 % is a simulation of the proposed edit**, from a refill of a copy with 13 In1
> track segments removed across 4 nets and nothing routed in their place. It is the plane response
> to the edit, not a measurement of a fabbable board. Fabbability depends on the B.Cu reroute (§3),
> which is now verified feasible for 10 of the 13 segments."

---

## 3. Defect 3 — "B.Cu has room": the premise was wrong, the flag was right

### The numbers in w2:218-219 are correct, the inference is not
Measured on the real board (`hf6_fill.py` → `fill_analysis.json`):

| quantity | value |
|---|---|
| board bbox | 140.150 × 100.150 = **14,036.02 mm²** |
| **B.Cu `/GND` fill** | **12,728.793 mm² = 90.69 %** |
| B.Cu not-GND remainder | 1,307.2 mm² |
| …of which actual signal/via/pad copper | **only 301.86 mm²** |
| …of which clearance gaps + area outside Edge_Cuts | 1,005.4 mm² |
| B.Cu GND fill inside the 96.7 mm² RF corridor | 82.3 mm² (**85.1 %**) |
| **B.Cu other-net copper inside that corridor** | **5.64 mm²** |

So 12,728.8 / 14,036 is right, and "about 1,307 mm² fragmented" is *not* fragmented ground — it is
mostly not copper at all. And **a pour percentage is not a free-space budget**: a pour recedes
around a new track, it does not block it. The 85 % fill in the corridor coexists with 5.64 mm² of
real obstacles. w2's conclusion ("it has room") happened to be right; its justification was not,
and — correctly — it refused to rely on that (w2:337 `UNVERIFIED`).

### So I measured it, per segment
`hf3_bcu.py` → `bcu_feasibility.json`. For each segment placed at the **same XY** on B.Cu, same width,
same net, I bisect the largest clearance it can keep to every other-net B.Cu copper object, using the
real KiCad shape engine (`TransformShapeToPolygon` + `BooleanIntersection`, error 0.002 mm).
**Every netclass on this board is 0.125 mm** (`.kicad_pro` `net_settings.classes`: Default, POWER,
RF_50R, CAN_DIFF, GATE_DRIVE, CURRENT_SENSE, HIGH_CURRENT all `clearance: 0.125`), so 0.125 is the bar.

| id | net | len mm | **c_max mm** | verdict |
|---|---|---|---|---|
| c00 | VDD_CC112 | 0.207 | 1.000 | feasible |
| c01 | VDD_CC112 | 0.389 | 0.199 | feasible |
| **c02** | VDD_CC112 | 1.538 | **0.000** | **INFEASIBLE** at this XY |
| c03 | VDD_CC112 | 2.167 | 0.192 | feasible |
| **c04** | VDD_CC112 | 5.115 | **1.000** | **feasible — nothing within 1.0 mm** |
| c05 | VDD_CC112 | 2.716 | 0.218 | feasible |
| c06 | VDD_CC112 | 0.134 | 1.000 | feasible |
| c07 | /GND (not in the 13) | 12.000 | 0.000 | infeasible (irrelevant, w2 leaves it) |
| c08 | GNSS_RESET_OD | 22.147 | 0.140 | feasible — 0.015 mm margin |
| c09 | GNSS_UART_RX_2V8 | 12.123 | 0.131 | feasible — 0.006 mm margin |
| **c10** | RF_GPIO2 | 1.900 | **0.000** | **INFEASIBLE** |
| **c11** | RF_GPIO2 | 2.000 | **0.000** | **INFEASIBLE** |
| c12 | RF_GPIO2 | 0.100 | 0.300 | feasible |
| c13 | RF_GPIO2 | 0.141 | 0.328 | feasible |

**Answer to the question asked: of the 13 moved segments, 10 are feasible on B.Cu at 0.125 mm and
3 are infeasible — `c02`, `c10`, `c11`** (each blocked down to c_max = 0.000, i.e. it would short).
What stands in the way is named in `bcu_feasibility.json`:

| segment | blocked by (B.Cu) |
|---|---|
| c02 | `/HGM` tracks at y = 59.400 and y = 59.200 × 12.8 mm long — c02 crosses both |
| c10 | `/HGM` track (91.200, 59.400) → (96.800, 59.400), 0.1125 mm² overlap |
| c11 | U40 pad 33 (`/GND`) at (94.000, 61.000), 0.8675 mm² overlap |

So the blocker is **B.Cu signal routing, not the ground pour** — which is precisely the thing the
"12,728.8 mm² is filled" argument could not see.

The long diagonals are *not* the problem, contrary to w2's guess in its risk list: the **22.147 mm**
GNSS diagonal fits with 0.140 mm and the 12.123 mm one with 0.131 mm.

### A track needs a via, so I tested the landings too
0.7 mm pad / 0.35 mm drill through via, checked against **all four** copper layers. Of the 18 unique
endpoints of the 13 segments, **6 are blocked** and 12 are clear:

| blocked point | net | deficit |
|---|---|---|
| (98.998, 61.571) | VDD_CC112 | 0.125 |
| (96.378, 58.951) | VDD_CC112 | 0.125 |
| (95.500, 60.500) | RF_GPIO2 | 0.125 |
| (93.500, 60.500) | RF_GPIO2 | 0.125 |
| (95.600, 58.400) | RF_GPIO2 | 0.075 |
| (95.600, 58.500) | RF_GPIO2 | 0.047 |

Note (98.998, 61.571) is blocked *as a via site* but it is the **shared corner of c03 and c05**. If both
move, the corner stays on B.Cu and needs **no via** — only the two far ends do. That is how the
recommendation in §5 gets away with two vias, both clear at 1.000 mm and 0.447 mm.

---

## 4. The real question — what is the minimum set of moves?

### 4.1 Trust gate first
My harness must reproduce w2 before it can contradict it. It does, exactly:

| | w2 `void_results.json` | mine | 
|---|---|---|
| control `s0` | 9.834 %, void 4.1699, In1 fill 12,619.235 | **identical** |
| `s` / all-13 | 1.307 %, void 0.5542, In1 fill 12,648.595 | **identical** |
| `q` clearance-only | 8.967 %, void 3.8025 | **identical** |

Pipeline is w2's own 3-process discipline (`hf_make.py` → `hf_refill.py` → `hf_measure.py`; a
collect-then-remove order is required, because `board.Remove()` mid-iteration leaves dangling SWIG
proxies and `GetStart()` then returns a `SwigPyObject`). Determinism check: `S0208` and its duplicate
`DUP_0208` both give 1.4438 mm² to 4 dp.

Two baseline figures reconcile: `06_void_polys.json` sums to 4.1701 mm² over 20 polygons (polygon
clustering), the segment-subtraction method gives 4.1699 (my `s0`, w2's `s0`). Both are 9.834 %; the
0.0002 mm² is method, not defect.

### 4.2 "Is it simply tightening the clearance rule?" — No, and I measured why

The 20 voids really are all clearance-caused (w2's `08_cause.json`; I did not re-derive it).
But clearance alone **saturates**:

| change | void % | Δ |
|---|---|---|
| none | 9.834 | — |
| **`q`: /3V3 clearance 0.25→0.125, min_thickness 0.25→0.10** | **8.967** | −0.87 pp |
| `q` reproduced independently (mine) | 8.967 | −0.87 pp |

Because **14 of the 20 voids span the full 0.350 mm trace width** — the reference is 100 % absent
under those sections. Halving a clearance sliver cannot restore a 2.6 mm cutout. So no: the rule
edit alone cannot reach 2 %.

### 4.3 Marginal effect of each segment on its own
Full table in **`analysis.md` §1**; the decisive part:

| id | len mm | void % alone | Δ mm² | B.Cu |
|---|---|---|---|---|
| c03 | 2.167 | 3.163 | −2.829 | ok |
| c04 | 5.115 | 3.270 | −2.783 | ok (1.0 mm clear) |
| c02 | 1.538 | 3.542 | −2.668 | **blocked** |
| c05 | 2.716 | 3.586 | −2.649 | ok |
| c08 | 22.147 | 9.696 | −0.058 | ok |
| c09 | 12.123 | 9.545 | −0.123 | ok |
| c00, c01, c06, c07, c10–c13 | ≤12 | 9.834 | **0.000** | — |

**8 of the 13 segments change the void by exactly nothing when moved alone.** c07 (the 12 mm /GND run
w2 left alone) is confirmed inert. So "move 13 segments" spends 8 moves on no measurable gain.

**Important caveat I have to state:** inertness does *not* compose. `c02` alone is 0.000, yet
`c02+c08` = 1.4438 mm² and `c02+c08+c09` = 1.2042, far below either part. The In1 `/3V3` fill is
sensitive globally: removing `c02` alone raises corridor 3V3 fill from 60.5 to 73.7 mm² while changing
the under-trace void not at all (`fill_analysis.json`). So per-segment attribution is unsafe and I
searched by measurement, exhaustively, not by reasoning.

### 4.4 Exhaustive search
All subsets of the 8 segments that ever show an effect ({c02,c03,c04,c05,c08,c09,c10,c11}) were built,
refilled and measured — 55 four-subsets plus the 2- and 3-subsets — **149 variants** built, refilled and measured in total. Best achievable:

| moves | plain copper only | with the free constraint edit `q` |
|---|---|---|
| 0 | 9.834 % | 8.967 % |
| 1 | c03 → 3.163 % | **c04 → 1.962 %** |
| 2 | c03+c05 → 2.747 % | c03+c04 → 1.681 % |
| 3 | c03+c05+c09 → 2.458 % | c03+c04+c05 → 1.474 % |
| 4 | c03+c05+c08+c09 → 2.044 % | c03+c05+c08+c09 → 1.403 % |
| 5 | c03+c04+c05+c08+c09 → **1.772 %** | → 1.090 % |
| 13 (w2's proposal) | 1.307 % | — |

Threshold is 2 % of 42.404 = **0.84808 mm²**.

### 4.5 The answer
- **Least effort, constraint edits free (the owner steer): 1 move.**
  `c04` — the 5.115 mm `/915 MHz RF/VDD_CC112` run at y = 64.381 — moved to B.Cu, **plus** the
  `/3V3` clearance edit. **0.8320 mm² = 1.962 %.**
- **If no constraint edit is allowed: 5 moves** (c03, c04, c05, c08, c09) → 1.772 %. 4 moves cannot
  do it (best 2.044 %), so 5 is the true pure-copper minimum.
- **Not 13.** 13 buys 1.307 % instead of 1.962 % and costs 8 dead moves plus 3 segments that cannot
  even go on B.Cu.

The constraint edit is worth **4 moves**. That is the whole point of the steer: it is a rule change,
not copper.

`c04` is the safest member of the set to move: it is the only long candidate with **nothing of another
net within 1.0 mm on B.Cu**, and both of its endpoints take a via at 1.000 mm clearance.

---

## 5. The recommended change, exactly

**Constraint edit** (in `.kicad_pro` / zone properties, In1 `/3V3` zone):
```
In1 /3V3  (connect_pads yes (clearance 0.125))   <- from 0.25
          (min_thickness 0.10)                   <- from 0.25
```
The `/GND` zone on In1 is untouched. This is DRC-legal (0.125 mm is the board's own netclass minimum
and the global `min_clearance` in `design_settings.rules`), it *grows* the 3V3 plane
(12,164.05 → 12,993.85 mm²), and it removes copper from nowhere.

**One copper move** — delete from In1.Cu, re-route on B.Cu:
```
net /915 MHz RF/VDD_CC112, w=0.250
(98.903, 64.381) -> (93.788, 64.381)   len 5.115 mm      [c04]
B.Cu clearance available: c_max = 1.000 mm  (bar = 0.125)
vias needed: 2  at (98.903,64.381) and (93.788,64.381), both c_max = 1.000 mm
```
Result **0.8320 mm² void = 1.962 %** (from 9.834 %), unconnected 2 until the reroute is drawn.

**If a margin on the 2 % line is wanted** (1.962 % has only 0.016 mm² headroom): add `c03`
(97.466, 60.038) → (98.998, 61.571), w=0.250, 2.167 mm, c_max 0.192 → **0.7128 mm² = 1.681 %**,
3 moves total. This is the version I would actually sign, and it is still 10 moves cheaper than w2.

---

## 6. What is left after the recommended change (12 residual polygons, 0.8320 mm²)

| net | mm² | location | cause |
|---|---|---|---|
| CC_LNA_N | 0.2512 | x 98.496–99.476, y 60.824–61.216 | layer-change via (99.300, 61.000) |
| CC_LNA_N | 0.1934 | x 100.824–101.383, y 60.624–61.210 | layer-change via (101.000, 60.800) |
| CC_LNA_N | 0.0575 | x 98.006–98.493, y 60.919–61.257 | via clearance |
| GNSS_RF_IN | 0.0583 + 0.0439 + 0.0439 + 0.0165 | x ≈ 93.8–94.7, y ≈ 16.3–17.2 | GNSS diagonals still on In1 |
| CC_LNA_P | 0.0479 + 0.0439 | y ≈ 61.6–61.9 | VDD_CC112 c05/via envelope |
| CC_PA | 0.0452 + 0.0210 + 0.0092 | x ≈ 95.2–95.5, y ≈ 64.3–64.6 | L41 land clearance |

The two largest are **irreducible without blind/buried vias** — a CC_LNA_N via must punch In1 to reach
In2 — exactly as w2 said. They are the reason the floor is ~1.3–2 % and not 0 %. Adding the GNSS pair
(c08, c09) is what removes the ~0.16 mm² GNSS group; that is where w2's extra 0.5 pp comes from, and it
is not worth two 12–22 mm diagonals.

---

## 7. NOT verified

- **S11 after the change.** Still inherited from wave-1's solid-plane model. Not re-simulated. UNVERIFIED.
- **DRC not run on any variant.** Every number here is geometry (fill + clearance), not a DRC pass.
  `c_max` is a clearance measurement made with the same shape engine DRC uses, not a DRC report.
- **The reroute is not drawn.** I proved a clear corridor exists; I did not lay the track, so
  length/timing/EMC of the new B.Cu run is unevaluated, and the two vias' current return is unexamined.
- **Why inertness does not compose (§4.3) is unexplained.** The fill changes are real and reproducible,
  but I have not proven the island-connectivity mechanism. Numbers stand; the mechanism is a hypothesis.
- **The `q` edit's side effects are unexamined**: it narrows plane-to-signal gaps across the whole
  board, not just the RF corridor. No other-net coupling or creepage review was done.
- **`min_thickness 0.10`** creates 0.1 mm copper slivers. Fab-acceptable per the owner's steer, but
  not reviewed for mechanical robustness.
- w2 §6 says "5 residual polygons"; I measure **6 outlines** for the same variant (0.5542 mm² matched
  exactly). Outline-vs-hole counting, not an area discrepancy — not filed as a defect.

---

## 8. BOARD CORRECTIONS

**BOARD CORRECTION: `AGENT_BOARD.md:53` and `:152` say the 1.307 % "is a copy with 13 nets deleted".
It is 13 track segments across 4 nets** (`VDD_CC112` ×7, `RF_GPIO2` ×4, `GNSS_RESET_OD` ×1,
`GNSS_UART_RX_2V8` ×1). Measured unconnected count of that copy: **7** (control: 0).

**BOARD CORRECTION: `AGENT_BOARD.md:53` "B.Cu reroute UNVERIFIED" is now stale.** It is verified:
10 of the 13 segments route on B.Cu at 0.125 mm clearance, 3 do not (`c02`, `c10`, `c11`). The
recommended single move `c04` has 1.000 mm of clearance available and two clean via sites.

**Supersedes `AGENT_BOARD.md:150-152`** ("The fix is moving 13 In1 segments") and **`:163` decision 1**:
the minimum fix is **1 segment + a /3V3 clearance edit → 1.962 %**. Moving 13 is not required and 3 of
the 13 cannot go on B.Cu at all. Category stays **RIP-UP** but drops from a 13-segment rip-up to a
1-segment rip-up.

Not contradicted: `:53` void counts (20 voids, 9.834 %) and the 1.307 % figure all reproduce exactly.

---

## 9. Files

| file | what |
|---|---|
| `hf1_enum.py`, `cand.json` | 14 corridor In1 tracks enumerated, matched 1:1 to w2 `15_movetracks.json` |
| `hf_make.py`, `hf_refill.py`, `hf_measure.py`, `hf_batch.py` | 3-process make → refill → measure (w2 method, + unconnected count, + per-void polygons) |
| `hf7_make.py`, `hf7_batch.py` | same, with the `q` constraint edit option |
| `hf3_bcu.py`, `bcu_feasibility.json` | **per-segment B.Cu clearance bisection + via landings + colliders** |
| `hf6_fill.py`, `fill_analysis.json` | **B.Cu occupancy, corridor copper, In1 fill per variant** |
| `hf8_analyze.py`, `analysis.md`, `analysis.json` | marginal table, best-by-k, residual voids |
| `void_results2.json` | **149 variants** measured, one tag each |
| `fixwork/v_*.kicad_pcb` | every variant, refilled and reproducible |
| `plan0..7.json` | exact subset list per batch |

Reproduce: `"C:\Program Files\KiCad\9.0\bin\python.exe" hf_batch.py plan4.json`

---

*Status: citations fixed (patch supplied, not applied — other owner's directory), provenance relabelled
with a measured unconnected count, B.Cu feasibility resolved per segment, minimum move set found.*