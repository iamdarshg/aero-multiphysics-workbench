# DEC-HDI-CONVERSION — Code-SDR V2 via feasibility

**Verdict: there is no HDI work to do on Code-SDR V2.** The board has **zero** microvias,
zero blind/buried vias, and zero vias below 0.2 mm. All 1085 vias are standard plated through
vias with 0.200 / 0.250 / 0.400 mm drills. The "36 × 0.1 mm HDI vias" figure is **not** on this
board; it belongs to `drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (§4).

Hard Constraint 1 (no HDI) is therefore **already satisfied**, and the least-total-effort action is
to spend nothing: no copper move, no re-spin, no coupon. §8 quantifies what a stricter 0.3 mm floor
would cost, so the choice is an informed one.

| provenance | value |
|---|---|
| repo / branch / HEAD | `repos/Code-SDR`, `work/2026-11-11`, `6fbc004af4bec9c5ec78e57709c7127a280489f6` |
| working tree after this audit | **0 changed paths** (nothing written into the repo) |
| `hardware/v2/Code-SDR-V2.kicad_pcb` | sha256 `309414D2B371C6265629352FC0AA7252…` |
| `hardware/v2/Code-SDR-V2.kicad_pro` | sha256 `957E75808E4F1BF4AB04D9F82B05219F…` |
| `hardware/v2/Code-SDR-V2.kicad_dru` | sha256 `6038E373C284135392744B0C838279EE…` |
| tools | KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), pcbnew 9.0.7 python, kicad-cli 9.0.7 |
| board objects measured | 12 253 track objects = 11 168 segments + 1 085 vias + 0 arcs; 373 footprints — matches the brief |

---

## 1. VIA_CENSUS — every via, measured

Method: `pcbnew.LoadBoard` → every `PCB_VIA_T`, reading `GetDrillValue()`, `GetWidth(layer)`
(KiCad 9 requires the layer argument — see §9 trap 1), `TopLayer()`, `BottomLayer()`,
`GetViaType()`, `IsMicroVia()`. Script: `census.py` → `vias.csv` (1085 rows), `census.json`.

| drill (mm) | pad (mm) | annulus (mm) | span | via type | microvia-class | count |
|---|---|---|---|---|---|---|
| 0.200 | 0.450 | 0.125 | F.Cu → B.Cu | through | no | **924** |
| 0.200 | 0.400 | 0.100 | F.Cu → B.Cu | through | no | **53** |
| 0.200 | 0.500 | 0.150 | F.Cu → B.Cu | through | no | **6** |
| 0.250 | 0.500 | 0.125 | F.Cu → B.Cu | through | no | **89** |
| 0.400 | 1.000 | 0.300 | F.Cu → B.Cu | through | no | **13** |
| | | | | **total** | | **1085** |

### Exact counts per class

| class | count | method |
|---|---|---|
| through (F.Cu→B.Cu) | **1085** | `span_histogram` in `census.json`; 1085/1085 |
| blind / buried (any other layer pair) | **0** | no layer pair other than `F.Cu→B.Cu`; `GetViaType()` = `THROUGH` for all |
| KiCad microvia flag (`IsMicroVia()`) | **0** | `microvia_flag_count: 0` |
| microvia-class by drill (< 0.15 mm) | **0** | drill histogram has no entry below 0.200 |
| **drill < 0.200 mm** (the actual target) | **0** | §6 target met on arrival |
| drill == 0.200 mm | **983** | 90.6 % of all vias |

### Drill-size distribution (true, 3 distinct drills)

`0.200 → 983`, `0.250 → 89`, `0.400 → 13`. Annulus: min **0.100** (53 vias), max 0.300 (13 vias).
The 53 vias at 0.100 mm annulus sit **exactly** on the board's own `min_via_annular_width`
(`.kicad_pro:136`), i.e. zero margin — see §10.3.

### Independent confirmation from the fab view

`kicad-cli pcb export drill --excellon-separate-th` produces exactly **two** drill files (PTH, NPTH),
no blind/buried file. PTH tool table and hit counts:

| tool | ⌀ | hits | what |
|---|---|---|---|
| T1 | 0.200 | **983** | the 983 through vias |
| T2 | 0.200 | 73 | 0.2 mm PTH pads |
| T3 | 0.250 | **89** | the 89 through vias |
| T5 | 0.400 | **13** | the 13 through vias |
| T4,T6–T13 | 0.300 … 1.570 | 11,10,2,10,2,12,4,2,2 | component pads only |
| NPTH T1 | 3.200 | 2 | mounting holes |

Via counts agree hit-for-hit with the pcbnew census (983 / 89 / 13). **The smallest hole that
would be drilled into this board is 0.200 mm.**

### History — the claim was never true, not even once

Every one of the **39 revisions** of `hardware/v2/Code-SDR-V2.kicad_pcb` was censused via
`git show` (`history.py` → `history.json`):

* 39/39 revisions: **0** micro/blind/buried tokens, **minimum drill 0.200 mm** in every revision.
* The four `.kicad_pcb` copies in the repo (`hardware/v2/`, `hardware/v2/docs/release-notes/`,
  `docs/em-validation/scripts/v2/`, `…/release-notes/`) are all through-only
  (`all_boards_census.json`): 1085, 395, 1152, 395 vias, drills {0.2, 0.25, 0.4} only.

---

## 2. The board's own rules already forbid HDI

`hardware/v2/Code-SDR-V2.kicad_pro`:

| line | setting | value |
|---|---|---|
| `:119` | `allow_blind_buried_vias` | **false** |
| `:120` | `allow_microvias` | **false** |
| `:122` | `min_clearance` | 0.1 |
| `:127` | `min_hole_to_hole` | 0.1 |
| `:134` | `min_through_hole_diameter` | 0.15 |
| `:136` | `min_via_annular_width` | 0.1 |
| `:137` | `min_via_diameter` | 0.4 |
| `:255` | netclass `Default` `via_drill` | **0.2** |
| `:291` | netclass `IF_DIFF` `via_drill` | 0.25 |
| `:309` | netclass `POWER` `via_drill` | 0.4 |
| `:327` | netclass `RF_50` `via_drill` | 0.3 |

The project **disallows** microvias and blind/buried vias, and its netclass via drills are
0.2 / 0.25 / 0.3 / 0.4 — exactly the four populations measured. Nothing on this board could have
been an HDI via without also being a standing DRC violation, and DRC reports **no** such violation
(§6 baseline).

The only place the number 0.1 mm appears at all is the **unused microvia template** in every
netclass — `"microvia_drill": 0.1` at `.kicad_pro:248, :266, :284, :302, :320`. That is a default
in a dialog, not geometry.

---

## 3. BOARD CORRECTION — where the "36 HDI vias" actually are

**BOARD CORRECTION:** AGENT_BOARD.md `:34-35`, `:199` and `:209` attribute "36 × 0.1 mm HDI vias"
to Code-SDR. Measured, Code-SDR V2 has **0** microvias, **0** blind/buried vias and **0** vias
below 0.2 mm in every one of its 39 revisions; the figures belong to the drone-arm board below.
Suggested replacement: *"drone-arm rev_b carries 36 non-through vias (33 × 0.1 mm microvias);
Code-SDR V2 has none — all 1085 of its vias are through, minimum drill 0.200 mm."*

The numbers on the board are not invented — they are **another board's**. Measured on the board
that does have them:

`repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (4 copper layers, 165 footprints,
2620 track objects):

| class | count |
|---|---|
| vias total | 341 |
| drill 0.100 | **33** |
| drill 0.300 | 27 |
| drill 0.350 | 281 |
| **non-through (blind/buried)** | **36** |
| — of which KiCad-classified MICROVIA | 33 |
| — of which BLIND_BURIED at 0.3 mm | 3 |
| spans | F.Cu→In1.Cu 14, In1.Cu→In2.Cu 10, F.Cu→In2.Cu 3, In2.Cu→B.Cu 5, In1.Cu→B.Cu 4 |

So the figure on the board merges **two different numbers from the drone-arm board**:
36 = the blind/buried population, 33 = the subset that is 0.1 mm. The full per-via list is in
`drone-arm_rev_b_HDI_vias.csv` (36 rows, with net, position, drill, pad, span) so the real task can
start where the geometry actually is.

**Consequence for the plan:** the HDI-fanout work item assigned to Code-SDR has **no object**.
Doing it would have meant editing a correct board — the most expensive possible outcome. One
sibling copy of the same family, `main_rev_b_completed.kicad_pcb`, already has **0** non-through
vias (drills 0.3 / 0.35 only), which is worth knowing before re-doing the fanout by hand.

*This file is outside my assignment scope (Code-SDR only) and I did not analyse or modify it beyond
this census.*

---

## 4. NON_REPLACEABLE — which vias cannot become a standard through via

The question "which of the 0.1 mm vias cannot be replaced by a 0.2 or 0.3 mm through via" has an
empty answer set at 0.2 mm, because **there is nothing at 0.1 mm to replace**, and the 983 vias
that are already at 0.2 mm are already standard.

To make the answer useful, I measured the *forward* version of the same question: **if the owner
imposed a stricter 0.3 mm floor, which vias would fight it and why?** Method: build variants by a
block-wise text transform of via blocks only (`variant.py`), refill zones (`refill.py`), run
`kicad-cli pcb drc --severity-all --format json` with the matching project file, and attribute each
violation back to a via (`analyse.py`, `classify.py`).

### Result: 0 blocked at 0.200, 285 blocked at 0.250, 337 blocked at 0.300

| variant | drill / pad | violations | unconnected | clearance | shorts | hole-to-hole | blocked vias | Σ worst radial deficit |
|---|---|---|---|---|---|---|---|---|
| baseline (unmodified) | 0.20 / 0.45 | 246 | 0 | **0** | 0 | 0 | — | — |
| refill control | 0.20 / 0.45 | 246 | 0 | 0 | 0 | 0 | — | — |
| V025 | 0.25 / 0.50 | 744 | 0 | 499 | 0 | 0 | **285** | 9.93 mm |
| V030 | 0.30 / 0.60 | 779 | **2** | 500 | **28** | 4 | **337** | 15.59 mm |

The 0.2 mm floor produces **zero** clearance, annular, hole and short violations against the board's
own rules. The 0.3 mm floor produces 28 **shorts between different nets**, 4 hole-to-hole conflicts
and **2 broken connections** — a hard fail, not a nuisance.

### Why each blocked case is blocked (0.30 floor, disjoint partition)

| reason | vias | typical measured geometry |
|---|---|---|
| **adjacent track on the layer pair** | **290** | e.g. `Via[GND] @83.07,69.60` vs `Track[RGMII_RXD0] on In1.Cu`; gap 0.203 mm vs 0.25 required |
| **GND return via immediately adjacent** | **29** | `Via[GND] @73.18,67.996` vs `Via[ADC_REFT] @73.739,67.786` — 0.590 mm centre distance; 0.6 pads short |
| **pad pitch / BGA escape (pad within 0.35 mm)** | **18** | 35 pad conflicts, 7 on `U10`, 5 on `U30`, 2 on `U20` (the ADC) |
| different layer pair (option d) | **0** | impossible on a through-only 4-layer stack — see §5 |
| **total** | **337** | |

Sample hard failures at 0.6 mm pads (`drc_v030_filled.json`):

* `Items shorting two nets (AUX_EN and DSA_DATA)`: via centres **0.565 mm** apart
  `@44.0895,68.0260` / `@43.6895,67.6274`.
* `Items shorting two nets (+1V2_CORE and +3V3_DIG)`: `@88.4332,70.4906` / `@87.89,70.59`.
* `hole_to_hole` 4× — all **same-net twins**: `ADC_D8` pair 0.360 mm apart (0.0524 mm remaining
  hole-to-hole, 0.0995 required), `RGMII_RXD0_FPGA` pair, `+3V3_DIG` pair, `GND` pair.
* 2 nets **break** on refill: `Pad 10 [+3V3_DIG] of U10` and `Pad 2 [GND] of C55` lose their
  connection when the pour pulls back from the 0.6 mm pads.

The mechanism is uniform: the board was routed and filled for **0.45–0.50 mm pads at 0.100 mm
clearance**, so vias sit at exactly the spacing a 0.45 pad needs. Enlarging the pad spends the
entire remaining gap.

---

## 5. Mitigation ladder — what each option actually fixes

Ranked by least design effort (the brief's order). Counts are the **disjoint** partition from
`partition.py` / `partition.json` at the 0.30 floor; copper is the radial move each via needs,
taken as `required_clearance − actual_clearance` from the DRC text (an exact geometric minimum,
not an estimate).

| # | option | vias fixed | copper moved | notes |
|---|---|---|---|---|
| **(c)** | share / delete a return via | **29** | **1.31 mm** | cheapest: the GND twin goes, the signal via moves by its residual only. 4 of these are same-net twins (`ADC_D8`, `RGMII_RXD0_FPGA`, `+3V3_DIG`, `GND`) where the twin is deletable outright at **0 mm** if current capacity allows (UNVERIFIED — no current calc done) |
| **(a)** | shift via outward along the escape + jog track | **290** | **13.74 mm** | the bulk. Each is a 0.001–0.088 mm radial move (median 0.049); the track needs the same jog at the via, so the copper moved is ≈ 2 × deficit ≈ 27 mm of trace |
| **(b)** | dogbone with a short stub | **18** | 0.54 mm shift + **5.94 mm of new stub** | `stub = deficit + 0.30` per via (0.30 = 0.6 pad radius). All 18 are pad-escape cases (U10 ×7, U30 ×5, U20 ×2); a dogbone is the textbook fix there, but each one adds a 0.33 mm stub and a second drill hit |
| **(d)** | reroute the affected net to a different layer pair | **0** | — | **Void under Constraint 1.** On a 4-layer through-only board "a different layer pair" *is* blind/buried, which is forbidden. The only reading that survives is "move the net to different copper", i.e. a full reroute — measured cost unbounded, and it fixes vias one at a time |
| | **total** | **337** | **15.59 mm radial + 5.94 mm stub** | |

---

## 6. RANKED PLAN

| rank | option | vias fixed | copper moved | min drill after |
|---|---|---|---|---|
| **R0** | **no copper change — board already complies** | **0 needed (1085/1085 compliant)** | **0 mm** | **0.200 mm** |
| R1 | delete the 13 DRC-flagged "dangling" vias | 0 — **rejected by test**, breaks 8 connections (§7) | 0 | 0.200 mm |
| R2 | grow the 53 zero-annulus vias 0.40 → 0.45 pad (drill unchanged) | 32 of 53 clear; **21 need a move** | 0.525 mm radial | 0.200 mm |
| R3 | raise the floor to 0.25 mm | 285 vias need work | 9.93 mm radial | 0.250 mm |
| R4 | raise the floor to 0.30 mm | 337 vias need work | 15.59 mm radial + 5.94 mm stub | 0.300 mm |

**MIN_DRILL achieved: 0.200 mm.** The assignment target ("zero vias below 0.2 mm") is met on
arrival, and R0 is the recommendation: it satisfies Constraint 1 at zero cost and zero rework, and
it leaves the $60 cap untouched.

R3/R4 are *not* recommended. They buy 0.05–0.10 mm of drill margin in exchange for touching 285–337
vias on a routed, DRC-clean 4-layer board — exactly the "cheap choice that forces rework" the
governing principle warns about. The margin they buy is not a fab requirement: 0.2 mm mechanical
drill is ordinary for any shop that can hold this board's 0.15 mm traces; the specific shop's
minimum is **UNVERIFIED** until quoted, but the drill file already carries C0.200 as its smallest
tool and nothing in the design needs smaller.

---

## 7. DELETABLE — measured, not assumed

DRC flags **13** vias as `via_dangling` ("not connected or connected on only one layer"). That
looks like the cheapest fix in the brief: delete them. It is wrong, and I tested it.

`delete_test.py` removes exactly those 13 (by UUID, into a copy), refills, and re-runs DRC:

| board | violations | **unconnected items** |
|---|---|---|
| baseline | 246 | 0 |
| refill control (no deletion) | 246 | **0** ← refill is innocent |
| 13 deleted | 248 | **8** ← the deletion is the cause |

Examples of what broke:

```
Missing connection: Track [ADC_CLK] on F.Cu, 0.0626 mm  <>  Track [ADC_CLK] on F.Cu, 3.3941 mm
Missing connection: Track [ADC_REFB] on F.Cu, 0.0602 mm <>  Track [ADC_REFB] on F.Cu, 0.7391 mm
Missing connection: Track [MDIO] on B.Cu, 0.0273 mm     <>  Track [MDIO] on B.Cu, 1.6800 mm
(+ FPGA_VCCIO2_3V3 ×2, QSPI_SD1, REF_100M_ADC, RGMII_RXC_FPGA)
```

The vias are **junction patches**: two track ends stop 0.027–0.089 mm short of each other and only
the via pad bridges the gap. KiCad therefore calls the via dangling while the net depends on it. **DELETABLE = 0**, measured, per class:

| class | deletable |
|---|---|
| 0.1 mm microvias | 0 (none exist) |
| 0.2 mm through vias | 0 |
| 0.25 mm through vias | 0 |
| 0.4 mm through vias | 0 |

The 13 DRC-flagged vias are **not** removable; the fix for them, if anyone wants it, is to extend
the short track to the via centre (a copper edit that costs more than the via).

---

## 8. Findings beyond the assignment

**8.1 The clock net has a hairline junction — this one matters.** The `via_dangling` `ADC_CLK` via
is at `(66.9500, 73.0225)`, drill 0.25, pad 0.50. Measured geometry around it:

```
ADC_CLK F.Cu len 3.3941  start (66.9500,73.0225)  end (64.5500,75.4225)   <- ends ON the via
ADC_CLK F.Cu len 0.5600  start (66.9787,72.1764)  end (66.9787,72.7364)
ADC_CLK F.Cu len 0.0626  start (66.9787,72.7364)  end (66.9720,72.7986)   <- the bridge
```

The clock net's continuity at that node rests on the via pad alone. The **0.0626 mm × 0.150 mm
stub** runs from 0.2876 mm from the via centre (outside the 0.250 mm pad radius) in to 0.2250 mm
(**inside** it) — so the via pad is the only thing joining that stub to the 3.3941 mm track. A
0.0626 mm stub is a sliver: an etch that erodes it opens the clock, and DRC will not say so
because the copper still "connects". Two hard facts make this an owner decision: (a) this is the
net the board already flags for review (`U20.D9 / ADC_CLK`), and (b) the fix is a small copper
edit — extend the stub to the via centre and the via stops being load-bearing. Reported, not
fixed: this is a repo and I write only in my own evidence folder.

**8.2 The 246-violation baseline is almost entirely library noise.** 199 `lib_footprint_mismatch`
+ 24 `lib_footprint_issues` = 223 of 246, unchanged by every variant I built. The board's own
clearance / annular / hole rules produce **0** violations. Any future report that quotes "246 DRC
violations" without this split will overstate the board's defect count by 20×.

**8.3 The 53 zero-margin annulus vias are the real (small) DFM exposure.** 53 vias at pad 0.40 /
drill 0.20 sit exactly on `min_via_annular_width` 0.100 (`:136`). Growing just those to 0.45 is
separable from any drill change — and **21 of the 53 then violate clearance**, so even this
"free" margin costs a move for 40 % of them. Worth doing only if the chosen fab quotes a tighter
annular tolerance than 0.100 mm.

**8.4 What the phantom task would have cost.** The plan on the board is to "fan out 36 HDI vias to
standard vias". On this board that means editing a correct board between two revisions, then
re-running DRC, refill and gerber export, then re-reviewing a diff of a 5.5 MB board — the full
re-spin pipeline for a change whose measured effect is zero. The measured outcome of the correct
action (R0) is: drill file identical, DRC identical, 0 mm of copper moved. That is the case for
spending nothing here and spending the effort on `drone-arm rev_b`, where the 36 actually are.

---

## 9. Two measurement traps (both caught before the numbers were used)

1. **`kicad-cli` applies the project rules only when the board and project share a stem.** My first
   V025/V030 runs used `Code-SDR-V2_v025.kicad_pcb` with no matching `.kicad_pro`, so DRC silently
   fell back to KiCad *defaults* — clearance 0.2 instead of 0.1, min hole 0.3 instead of 0.15,
   min via diameter 0.5 instead of 0.4 — and reported 199 `drill_out_of_range` and 53
   `via_diameter` errors that were pure artefacts. Every variant now ships a matching
   `.kicad_pro` / `.kicad_dru`, and the control run confirms the rule set in use (baseline 246 /
   0 unconnected).
2. **A modified board keeps its old zone fills.** Comparing unfilled variants manufactures
   via-to-zone clearance errors the fab would never see. Every variant is passed through
   `pcbnew.ZONE_FILLER` before DRC (`refill.py`), and a refill-only control on the unmodified board
   reproduces the baseline exactly (246 / 0), so the refill itself is provably not doing work.
   Note the honest effect: fill state moves the *attribution* (zone conflicts 249 → 0 at 0.30) but
   not the total (500 clearance either way).

---

## 10. Files

| file | contents |
|---|---|
| `REPORT.md` | this report |
| `vias.csv` | all 1085 vias: x, y, drill, pad, annulus, top/bottom layer, span, type, microvia flag, net |
| `census.json` | drill/size/span histograms, class counts, object counts |
| `history.json` | per-revision via census over all 39 revisions of the board |
| `all_boards_census.json` | the four `.kicad_pcb` copies in the repo |
| `role.json` | connectivity role per via (track layers touched, duplicates, stitching candidates) |
| `blocked.json`, `options.json`, `partition.json` | per-variant blocked-via sets, option mapping, disjoint partition |
| `deleted13.json` | the 13 deletion candidates with net and position |
| `drone-arm_rev_b_HDI_vias.csv` | the 36 real HDI vias, where they actually live |
| `census.py`, `history.py`, `all_boards.py`, `role.py`, `variant.py`, `refill.py`, `delete_test.py`, `analyse.py`, `classify.py`, `partition.py` | every measurement above, re-runnable |
| `_*.py` | ad-hoc spot checks quoted in §4, §7, §8 (clock-net geometry, drone-arm census, control refill, annulus join) |
| `work/` | board copies, variants, drill files, DRC JSON (baseline, control, V025, V030, del13) |

### Reproduction

```powershell
$py = "C:/Program Files/KiCad/9.0/bin/python.exe"
& $py evidence/dec-hdi-conversion/census.py          # the census
& $py evidence/dec-hdi-conversion/history.py         # 39 revisions
& $py evidence/dec-hdi-conversion/variant.py         # build V025/V030
& $py evidence/dec-hdi-conversion/refill.py          # refill zones
& $py evidence/dec-hdi-conversion/delete_test.py     # the deletion experiment
& $py evidence/dec-hdi-conversion/analyse.py         # attribute DRC -> vias
& $py evidence/dec-hdi-conversion/partition.py       # disjoint option partition

$cli = "C:/Program Files/KiCad/9.0/bin/kicad-cli.exe"
$w = "evidence/dec-hdi-conversion/work"
& $cli pcb drc --format json --severity-all --units mm -o "$w/drc_baseline.json" "$w/Code-SDR-V2.kicad_pcb"
& $cli pcb export drill -o "$w/drl/" --excellon-separate-th --excellon-units mm "$w/Code-SDR-V2.kicad_pcb"
```

Read-only guarantee: every write in this audit went to
`E:/engineering-portfolio-audit/evidence/dec-hdi-conversion/`. `git status --porcelain` in
`repos/Code-SDR` reports **0 changed paths**; no commit, no push, no `audit/*` branch.

---

## 11. Answers to the five questions, in one place

1. **Every via enumerated, exact counts per class** → §1. 1085 vias; 983 × 0.200, 89 × 0.250,
   13 × 0.400; all through F.Cu→B.Cu; 0 microvia, 0 blind/buried, 0 below 0.2 mm.
2. **Which cannot become a 0.2 / 0.3 mm through via** → §4. At 0.2: **none** (nothing to convert).
   At 0.3: **337**, why: adjacent track 290, adjacent GND return via 29, pad/BGA-escape 18;
   28 outright shorts and 2 broken nets prove it.
3. **Concrete mitigation per blocked case, by effort** → §5: (c) 29 vias / 1.31 mm, (a) 290 vias /
   13.74 mm, (b) 18 vias / 0.54 mm + 5.94 mm stub, (d) 0 vias — void under Constraint 1.
4. **Single ranked plan, min drill** → §6: R0 wins (0 fixed because 0 need fixing, 0 mm copper,
   **min drill 0.200 mm**); R3/R4 listed with their cost and not recommended.
5. **Are any 0.1 mm vias electrically unnecessary?** → §7: there are none to judge, and the
   analogous test on the 13 deletion candidates says **deletion is not free** — 8 connections
   break. **DELETABLE = 0.**