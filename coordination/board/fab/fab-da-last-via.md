# fab-da-last-via — clear the LAST non-through via by re-routing its blocking corridors

**Task (single):** the R=1.30 mm board from `fab-da-clear-reroute` leaves **1 non-through via**:
`/RF_GPIO0` at **(57.400, 56.100)**, with a legal through site **0.177 mm** away, "convertible on its own"
but blocked by the other 16 vias' corridors. Re-route the blocking corridors locally, convert it, then drive
unconnected toward 0, and report the non-through-vs-unconnected tradeoff rather than optimising one.

**Input:** `evidence/fab-da-clear-reroute/` — `work/R130.kicad_pcb` (328 vias, **1 non-through**, 36
unconnected), copied to `work/R130_base.kicad_pcb`; the base board and its project/rules copied for the DRC
gate. Everything is done on copies in `evidence/fab-da-last-via/`; nothing is written into a repo.

**Headline.** The 0.177 mm site **is real but no longer exists**: it was measured in the state *"base board
minus the 17 clearing disks, other 16 conversions not placed"*. On the real R=1.30 board that site is
**−0.385 mm illegal**, and the item that owns 0.385 of it is **the `/HGM` conversion via itself** — which has
**no legal alternative site anywhere within 1.6 mm** (best margin **−0.0327** mm, against `U10.28`'s pad).
The two vias need 0.725 mm of separation and the U10 escape cannot give it. The corridor jog is therefore
not the binding constraint; **a through via of the project's own minimum size (0.60 mm — `min_via_diameter`
0.6) has no site within 2.4 mm of that node** that a jog or a whole-track shift can open. The honest endgame
is reported in §6: what was executed, what was kept, and the exact residual.

---

## 1. State reproduced (step 1)

Both tools, on `work/R130_base.kicad_pcb` (a byte copy of the input board), all numbers derived per row:

| check | measured | how |
|---|---|---|
| copper layers | F, In1, In2, In3, In4, B (6) | `s0_dump.py` (pcbnew) |
| vias / **non-through** | 328 / **1** | `s0_dump.py` |
| the one non-through | **`/RF_GPIO0`, MICROVIA `In2.Cu→B.Cu`, (57.400, 56.100), size 0.300, drill 0.100** | `s2_block.py` |
| drill histogram | `{0.1: 1, 0.2: 5, 0.3: 47, 0.35: 275}` | `s0_dump.py` |
| **min drill** | **0.100** — held there by that single via | same |
| DRC, own rules | **60 violations = clearance 1 · via_diameter 5 · track_dangling 51 · via_dangling 3**; **36 unconnected** | `kicad-cli pcb drc --format json --severity-all --units mm` |
| the single clearance error | **Via `/HGM` F.Cu–B.Cu at (57.575,55.650) vs Micro Via `/RF_GPIO0` In2–B: "actual 0.0328 mm, clearance 0.1250"** | same JSON, quoted verbatim |
| unconnected, pcbnew | **36** (`GetUnconnectedCount`) — agrees with `kicad-cli`; the 499 cap is not in play | `s11_apply.py` preamble |
| the 0.177 mm site | reproduced: **373 legal through sites** for this row in the state the prior wave used, nearest **(57.375, 55.925), off 0.177 mm** | re-ran their `s10_diag.py 1.3 57.4 56.1 In2.Cu B.Cu /RF_GPIO0` |

**One instrument fault caught here.** `R130.kicad_pcb` carries no sibling `.kicad_pro`, so pcbnew reports
that board's design settings as the built-in defaults (`min_clearance 0.0`, `through_hole_min 0.3`) instead
of the project's `0.125 / 0.2`. Every board is therefore gated in a directory with the base project file
beside it (`gate/<tag>/<name>.kicad_pro`), and all clearance arguments in this report use the project values
`CLR 0.125`, `hole-to-hole 0.200`, `copper-edge 0.500`, `min_via_diameter 0.6`.

## 2. The corridors that block it (step 2)

The 0.425 mm exclusion circle of a 0.60/0.30 through via at **(57.375, 55.925)** — evaluated on the real
R=1.30 board, not on the cleared board the 0.177 mm figure came from (`s3_site.py`):

| layer | item | net | geometry | edge dist | **shortfall** | born |
|---|---|---|---|---:|---:|---|
| F,In1,In2,In3,In4,B | **via 0.600** | **`/HGM`** | (57.575, 55.650) | +0.0400 | **+0.3850** | **this wave's conversion** |
| In2 | track w0.20 | `/RF_MISO` | (57.050,55.900)→(57.000,55.950) | +0.2260 | +0.1990 | original |
| In2 | track w0.20 | `/RF_MISO` | (57.050,55.850)→(57.050,55.900) | +0.2260 | +0.1990 | original |
| F.Cu | track w0.20 | `/HGM` | (57.550,55.250)→(57.550,55.625) | +0.2473 | +0.1777 | this wave's conversion |
| In1.Cu | track w0.20 | `/HGM` | (57.550,55.250)→(57.550,55.625) | +0.2473 | +0.1777 | this wave's conversion |
| In2 | track w0.20 | `/RF_MISO` | (57.000,55.950)→(57.000,56.250) | +0.2758 | +0.1492 | original |
| In2 | track w0.20 | `/RF_MISO` | (57.000,56.250)→(57.050,56.300) | +0.3950 | +0.0300 | original |
| In2 | track w0.20 | `/RF_MISO` | (57.050,56.300)→(57.050,56.350) | +0.3962 | +0.0288 | original |
| hole | hole | `/HGM` d0.300 | (57.575, 55.650) | +0.0400 | +0.1600 | this wave's conversion |

So the answer to "which corridors block it" is precise and it is **not a track jog problem**:

* **9 of 14 blocker rows are the `/HGM` conversion** — 6 layer copies of one 0.600 through via
  at (57.575, 55.650), plus the two 0.20 mm corridor segments it owns on F.Cu and In1.Cu, plus its hole.
  That via is the same object as the board's single `clearance` error: it stands **0.483 mm** from the
  surviving microvia where 0.575 mm is needed (`0.0328` actual vs `0.1250` required, quoted from DRC).
* **5 rows are original `/RF_MISO` In2 copper** — a 0.20 mm staircase at x ≈ 57.00–57.05 that was restored
  verbatim by the R=1.30 batch, and which blocks the site by ≤0.199 mm.
* **Zero pads block this site**, which is why it looked convertible at all.

**Why the /HGM via cannot simply be moved out of the way.** Removing the `/HGM` conversion (via + its two
corridor legs) and scanning ±1.60 mm at 0.05 mm for a legal 0.600/0.300 through site gives **0 candidates**;
the best margin anywhere in that box is **−0.0327 mm, blocked by pad `U10.28` on F.Cu** — an immovable pad
in the LQFP-100 escape (`s5_hgm.py`). Its own original XY (57.600, 55.150) is worse: **−0.1500**, blocked by
`U10.26`/`U10.28` pads and `/RF_MISO`. So the /HGM via is **fixed at (57.575, 55.650)**, and any through via
for `/RF_GPIO0` must sit ≥**0.725 mm** away. The 0.177 mm move is inside that forbidden circle by 0.548 mm.

**And the /HGM via is what fixes the clearance error**: with the microvia present its margin is
**−0.0922**; with the microvia removed it is **+0.0027** (`s6_rfsite.py`). Removing the dead microvia alone
clears the board's only `clearance` violation — confirmed by DRC below (1 → 0).

## 3. Execution — kept versus attempted, every attempt DRC-gated (step 3)

The microvia at (57.400, 56.100) is **not a live node on this board**: its In2 and B fanouts were erased by
the R=1.30 batch and never restored, so it is an isolated island that accounts for 2 of the 36 unconnected
pairs. That changes what a "conversion" has to be: a through via dropped in free space would just move the
dangle, so each candidate site is scored on (a) legality for a 0.600/0.300 through via, (b) whether its own
net's copper can be re-reached on In2 and B, (c) whether the clearance error disappears.

Two movers were built and used (`fix.py`): a **chord jog** (both endpoints kept, the part of the track inside
the exclusion circle is displaced sideways, flanked by two short spurs) and a **whole-track shift** (both
endpoints kept, joined by two stubs) because a chord jog is impossible where a track is already wedged. Both
re-check every new segment against all foreign copper before being accepted.

| # | what was attempted | result | kept? |
|---:|---|---|---|
| 1 | convert at the 0.177 mm site after removing the `/HGM` conversion | `/HGM` has no legal site in ±1.60 mm (best −0.0327, pad `U10.28`) | **rejected** |
| 2 | convert at the 0.177 mm site with `/HGM` in place | shortest blocker +0.3850 (via) — no track move can help | **rejected** |
| 3 | 0.60/0.30 sites, ±1.80 mm, 0.05 grid, jog + shift allowed | **0 convertible** (626 sites pass the pre-filter) | **rejected** |
| 4 | via-in-track: place the through via ON existing `/RF_GPIO0` copper (keeps it connected) | **0 legal points** on any of the 7 net segments within 3.0 mm (`s8_onsite.py`) | **rejected** |
| 5 | relocate along the net's own erased fanout line (both fanouts are collinear, so both could be re-added) | **0 legal sites** for 0.60, 0.55 and 0.50 — the line is hemmed by the `/RF_MISO` 45° trace 0.424 mm away | **rejected** |
| 6 | **0.50/0.30 at (56.900, 57.400)**, 1.393 mm from the node, 4 chord jogs | DRC-gated: `clearance` 1→0 **but `via_diameter` 5→6** | **rejected** |
| 7 | **0.60/0.30 sites, ±2.40 mm, 0.05 grid** (8 757 sites) | **11 convertible, all 2.77–3.39 mm away**; nearest reachable one applied | **KEPT — §3.1** |

Attempt 6 is worth recording because it is the one that *almost* worked, and the gate is what killed it. At
(56.900, 57.400) a 0.50 mm through via needs only two movers — `In2 /RF_GPIO2` w0.20 (0.0507 short) and
`F.Cu /RP2354B MCU/RUN` w0.25 (0.0064 short), both of which a 0.025 mm chord jog clears — and its B.Cu
fanout to (56.525, 55.225) is **legal (+0.1500)**, so the new via lands inside its own net instead of
floating. The DRC run on that board (`work/F1.kicad_pcb`, `drc/w1_F1_own.json`) returns
**59 violations: clearance 1→0, track_dangling 51→50, via_diameter 5→6**, 36 unconnected. The +1
`via_diameter` is the project's own `min_via_diameter 0.6` — a 0.50 mm via is not a legal PTH on this board,
so **the attempt is rejected** rather than shipped with a new rule violation. It also cost a
`Zone /GND F.Cu ↔ Zone /GND F.Cu` unconnected pair, i.e. the via's clearance hole split a GND sliver.

**Instrument control for unconnected set diffs.** Refilling the zones is part of applying any edit, and a
refill alone (`work/C_refl.kicad_pcb`) cycles 3 unconnected pairs without changing the count — so unconnected
**pair identities are not a stable set** and are never quoted as a set diff here. Only the count, and the
per-net census, are quoted.

### 3.1 The attempt that was kept

Attempt 7 — the wider scan — found **11 convertible 0.60/0.30 sites in ±2.40 mm** (8 757 sites pass the
pre-filter; the fail tally is dominated by `nomove /RF_GPIO2` 617, `nomove /RF_SCLK` 518, `nomove
MCU/RUN` 491 and `immovable U10.2x` pads). Every one of them is **2.77–3.39 mm from the node**. The
nearest site that is *also* reachable from the net's own surviving copper is **(59.750, 58.450), off
3.323 mm**, and it is the plan that was applied:

| element | value |
|---|---|
| microvia removed | `/RF_GPIO0` In2→B (57.400,56.100), size 0.300, **drill 0.100** |
| through via added | **0.600 / 0.300 THROUGH** F.Cu–B.Cu at **(59.750, 58.450)**, net `/RF_GPIO0`, **true site margin +0.0064 mm** |
| jog 1 | `/RP2354B MCU/STATUS_LED` **B.Cu** w0.25, chord bump **0.450 mm**, on (59.0256,59.3725)→(62.5828,55.8153), shortfall 0.4099 |
| jog 2 | `/RF_MISO` **In2.Cu** w0.20, chord bump **0.150 mm**, on (57.050,56.350)→(60.600,59.900), shortfall 0.1007 |
| fanout restored | **In2.Cu** 0.25 mm (59.750,58.450)→(60.842,59.559), margin **+0.0194** — joins the new via to the net's In2 bus, so it is not a new dangle |
| B fanout | **not restorable** (−0.3500, blocked by `/RF_GPIO2` w0.20) |

Board `work/F2.kicad_pcb`. The 0.600 size is not a preference: `min_via_diameter` is **0.6** on this
project, and the board's five 0.400/0.200 PTH vias are the pre-existing `via_diameter` violations it
inherits — attempt 6 shows a 0.500 mm via is a **new** rule violation.

## 4. Unconnected — the tradeoff, measured (step 4)

The same fix (same site, same two jogs, same In2 fanout) applies unchanged to the R=0.70 mm board, whose
local geometry at (59.750,58.450) is identical (STATUS_LED +0.4099, `/RF_MISO` +0.1007, In2 fanout
+0.0194). Applying it there is board `work/G1.kicad_pcb`. Both variants were DRC-gated and censused:

| board | non-through | **unconnected** | min drill | DRC own | SET DIFF vs its own baseline |
|---|---:|---:|---:|---|---|
| R = 0.70 as delivered | 2 (`F→In1`, `In2→B`) | 30 | 0.100 | 52 = `clearance 1 · via_diameter 6 · track_dangling 43 · via_dangling 2` | — |
| **R = 0.70 + this fix** (G1) | **1** (`/LSM_INT1` F→In1) | **29** | 0.100 | 50 = `via_diameter 6 · track_dangling 42 · via_dangling 2` | `+{}` / `−{clearance 1, track_dangling 1}` |
| R = 1.30 as delivered | 1 (`In2→B`) | 36 | 0.100 | 60 = `clearance 1 · via_diameter 5 · track_dangling 51 · via_dangling 3` | — |
| **R = 1.30 + this fix** (F2) | **0** | **35** | **0.200** | 58 = `via_diameter 5 · track_dangling 50 · via_dangling 3` | `+{}` / `−{clearance 1, track_dangling 1}` |

**The tradeoff, stated rather than optimised: 0.70 + fix buys one fewer unconnected (29 vs 35) and pays one
non-through via (1 vs 0).** The task's target is the non-through count, so the shipped board is F2; G1 is
kept as the alternative point. Neither reaches 0 unconnected.

On **both** boards the *only* net whose unconnected census changes is `/RF_GPIO0` (3 → 2 pairs) — checked
per net, not as a total (`s17_sets.py`, `s21_g1diff.py`) — so the fix does not borrow connectivity from
anywhere else.

## 5. Verification of the delivered board (step 5)

`work/F2.kicad_pcb` — every row derived, nothing estimated.

| check | base | R = 1.30 | **F2 (shipped)** | required | verdict |
|---|---|---|---|---|---|
| copper layers | 6 | 6 | **6** | 6 | ok |
| vias total | 337 | 328 | **328** | — | — |
| **non-through by span** | **17** | **1** (`In2→B`) | **0** — `nontrough_by_pair {}`, stacks 0 | **0** | **PASS** |
| through vias | 320 | 327 | **328** | — | — |
| **DRC set diff, own rules** | `{via_diameter 6}` | see §4 | **`+{}` / `−{clearance 1, track_dangling 1}` vs R=1.30** | nothing new | **PASS** |
| **DRC, no-HDI gate** | 22 = `microvia_drill 16 + via_diameter 6` | 60 | **58 — identical to own rules: zero sub-0.20 drills left** | — | **PASS** |
| `clearance` errors | 0 | **1** | **0** | 0 | **PASS** |
| **unconnected, `pcbnew`** | 0 | 36 | **35** | **0** | **FAIL** |
| **unconnected, `kicad-cli`** | 0 | 36 | **35** | 0 | agrees; 499 cap not in play |
| **min drill** | 0.100 | 0.100 | **0.200** — histogram `{0.2: 5, 0.3: 48, 0.35: 275}` | ≥ 0.200 | **PASS** (the 0.100 drill went with the last via, as predicted) |
| **RF void A / B** | 4.1699 mm² / 9.8338 % · 3.8754 / 9.1392 | identical | **4.1699 / 9.8338 · 3.8754 / 9.1392 — bit-identical** | unchanged | **PASS** |
| pads / gap census | 657, sha `fad11a71c92532d9`, gaps <0.20/0.25/0.30 = 145/219/309 (U10 40/84/84) | identical | **identical, sha `fad11a71c92532d9`** | untouched | **PASS** |
| board area | 14 000.0000 mm² | 14 000.0000 | **14 000.0000** (outline untouched) | — | ok |

## 6. Verdict (step 6)

**0 non-through is reached; 0/0 is not.** F2 is **0 non-through, 0 clearance errors, min drill 0.200,
RF void and pads bit-identical, DRC `+{}` against the board it came from** — and **35 unconnected**, one
fewer than the 36 it started with. One pair of the net's three (`/RF_GPIO0`) was recovered; the other two
would need the fanout corridors that the R=1.30 clearing erased, and those need **0.450 mm of lane** in a
U10 field that has none (the prior wave's measured 0.031 mm miss, not re-litigated here).

**The premise of the task does not survive contact with the board, and that is the finding.** The
0.177 mm site was measured on *"base minus the 17 clearing disks, other 16 not placed"*. On the real board
that site is **−0.385 mm illegal**, and 0.385 of it is **the `/HGM` conversion via at (57.575,55.650)** —
a 0.600 through via that has **no legal alternative site anywhere within 1.60 mm** (best margin
**−0.0327 mm**, against pad `U10.28`; its own original XY is −0.1500). Two 0.600 through vias need
**0.725 mm** between centres and the escape cannot supply it, so no jog of any track could have opened
that site: the blocker is a via, not a corridor. What the jog budget *could* buy is the 3.32 mm
relocation delivered here, plus the deletion of the dead 0.100 mm stub — the same object that carried the
board's only `clearance` error and its 0.100 mm minimum drill. Both are now gone.

**What would be needed for 0/0:** an HDI 1+2+1 build (the vias were designed for it), or an LQFP-100
re-escape, or 0.450 mm lanes into U10 — all three are board-level re-work, not local jog. The nearest
honest alternative is G1: **1 non-through, 29 unconnected**, one fewer connection lost but a microvia kept.

### Artefacts

| file | note |
|---|---|
| `work/F2.kicad_pcb` | **delivered board**: 0 non-through, 35 unconnected, min drill 0.200 |
| `work/G1.kicad_pcb` | alternative: R=0.70 + same fix, 1 non-through, 29 unconnected |
| `work/F1.kicad_pcb` | **rejected** near-miss: 0.50/0.30 at 1.393 mm, `via_diameter 5→6` |
| `work/C_refl.kicad_pcb` | control: refill only, proves unconnected pairs are not a stable set |
| `work/block.json`, `work/site_block.json` | §2 blocker tables with per-layer decomposition |
| `work/plan60.json` | the ±2.40 mm 0.60 site scan: 11 convertible sites, fail tally |
| `work/onsite.json`, `work/hgm_sites.json` | via-in-track scan (0 legal) and the /HGM site scan (0 legal) |
| `work/applied.json` | the F2 plan: site, margin, both jog geometries, fanout margin |
| `work/ver_F2.json`, `work/ver_G1.json`, `void/void_measure.json` | census, pad hash, gaps, RF void |
| `drc/w0_*.json`, `drc/w1_*.json`, `drc/w2_*.json`, `drc/w3_*.json` | every DRC run, both rulesets |

Scripts, in the order they matter: `s2_block.py` (state + the 17-row context) · `s3_site.py` (blockers at
the 0.177 mm site) · `s5_hgm.py` (proves the /HGM via cannot move) · `s6_rfsite.py` /
`s8_onsite.py` / `s9_line.py` (three failed conversion families) · `s13_scan.py` (the ±2.40 mm 0.60 site
scan) · `s11_apply.py` (writes the fix) · `s14_control.py` (refill control) · `s12_diff.py` /
`s17_sets.py` / `s21_g1diff.py` (set diffs, per net) · `s9_verify.py` / `s5_void.py` (census, pads, void) ·
`fix.py` (chord jog, whole-track shift, site legality).

**Provenance.** All numbers are **measured** here with `pcbnew` (KiCad 9.0.7 bundled python) and
`kicad-cli pcb drc --format json --severity-all --units mm`, on copies, in this evidence directory. The
inherited R=0.70 / R=1.30 baselines are re-measured in `drc/w3_R070_own.json` and `drc/w0_R130_own.json`
rather than quoted. Nothing is estimated.