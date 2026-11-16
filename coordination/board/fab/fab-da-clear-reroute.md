# fab-da-clear-reroute — minimum copper move to convert all 17 non-through vias

**Task (single):** convert all 17 of drone-arm's non-through vias to legal 0.60/0.30 **through** vias by
clearing the MINIMUM possible copper — a local track jog or site relocation, not the 10 mm disk that
cost 42–49 nets and left 81 unconnected — then re-route whatever got cut, and deliver 0 non-through
vias with 0 unconnected on pcbnew.

**Input:** `evidence/fab-da-path/da_main_rev_b_path6L.kicad_pcb` (6 copper layers, 337 vias, **17
non-through**, DRC `{via_diameter: 6}`, unconnected 0/0, min drill 0.100). Copied to
`work/base.kicad_pcb`; nothing written into a repo.
**Prior waves read:** `fab-da-radical/REPORT.md` (rip-up 6/10/15 mm), `fab-da-growth-north/REPORT.md`
(growth +2/4/8 mm, per-site binding table).
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-clear-reroute/`. All work on copies.

> **HEADLINE — the premise is wrong, and this is the measurement that says so: the copper that blocks
> these 17 vias is NOT local, and no jog or relocation converts even one of them.**
> At its own site each via has **3 to 24 infringing items** (median 13) and **15 of 17 have an immovable
> PAD** among them; over **504 geometric candidates per via** — 21 shift radii × 24 directions, plus a
> chord jog of every offending track, plus a *routed* corridor (A\*, the net's own copper counted as free
> space) — **0 of 17 convert with zero copper deleted**. The closest miss is **0.031 mm**; most miss by
> 0.031–0.375 mm. A 0.20 mm track needs **0.450 mm of lane** and the U10 field does not contain one.
> What does work is a per-via clearing of **R = 0.70 mm**, and it is **better than the prior wave on every
> axis**: **15 of 17 converted** (prior best 10), **247 items erased on 38 nets** (prior 696 on 48),
> **unconnected 30** (prior 81). Non-through reaches **1** at R = 1.30 (16 of 17) and never 0.
> **Final: 1 non-through, 36 unconnected, min drill 0.100, one clearance error — NOT shippable.** The
> reason is structural, not budgetary.

---

## 0. Instrument validation

The input reproduces the shipped board exactly on both tools, and the per-site model reproduces the
prior wave's published extremes, so nothing below rests on an unvalidated instrument.

| check | measured here | prior evidence | how |
|---|---|---|---|
| copper layers | 6 (F, In1–In4, B) | 6 | `s0_dump.py` |
| vias / **non-through** | 337 / **17** (14 stacks) | 337 / 17 | `s1_verify.py`, span from `CuStack()` |
| by layer pair | F→In1 6 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 1 | identical | same |
| rules | CLR **0.125**, hole-to-hole **0.200**, copper-edge **0.500**, through-drill min **0.200**, track min **0.200** | same | `s0_dump.py` |
| DRC own rules | `{via_diameter: 6}` (6) | `{via_diameter: 6}` | `kicad-cli pcb drc --format json --severity-all` |
| DRC no-HDI gate | **22** = 16 `microvia_drill_out_of_range` + 6 `via_diameter` | 22 | `<board>.kicad_dru` |
| unconnected | **0** on both tools | 0 / 0 | `kicad-cli` + `pcbnew GetUnconnectedCount` |
| min drill | 0.100 (16 vias) | 0.100 | `s1_verify.py` |
| RF void A / B | **4.1699 mm² = 9.8338 % / 3.8754 = 9.1392 %** | identical | `s5_void.py` |
| pads / pad-gap census | 657 pads, sha **fad11a71c92532d9**, gaps <0.20/0.25/0.30 mm = **145/219/309** | — | `s9_verify.py` |
| worst copper margin at a site | **−0.6500** (pad FB1.2 `/3V3_ADC`) | −0.650 | `s1_obstruct.py` |
| best copper margin at a site | **−0.1192** (`/RF_GPIO0` 350 µm via) | −0.119 | same |
| binding kind at the original XY | **track 14 · pad 2 · via 1** | 14 / 2 / 1 | same |

**Five instrument faults caught in this wave, each of which produced a plausible wrong number:**

1. **Erasing pads in the model.** The first batch deleted copper inside the clearing circle *including
   pads*, which are immovable on a real board; it reported **17 of 17 converted** and would have shipped
   a board full of pad-clearance errors. Fixed: pads are never erased (`s5_batch.py`), and the honest
   count is 15–16 of 17.
2. **A via counted once per copper layer.** `Model.erase` walks layers, so a via spanning six layers made
   six "removed" records and — worse — six restored copies on the board: `holes_co_located` **+158**,
   `annular_width` **+67**. Fixed by de-duplicating on the via UUID; DRC violations fell 349 → 52.
3. **Sub-standard vias restored.** Restoring a 0.100 mm microvia as a THROUGH via produced
   `drill_out_of_range` **+5**. Fixed: only through vias are restored, and any of the 17 that does not
   convert **keeps its original microvia** — nothing is silently deleted.
4. **A vertex-only owner-pad distance**, inherited from the earlier waves, reported a 6.5 mm stub where
   the copper is 1.785 mm away. All stub lengths here use exact segment↔edge projection.
5. **The no-HDI ruleset silently not applied.** A `.kicad_dru` must be named after the board; copying it
   as `no_hdi.kicad_dru` made the "gate" column identical to the "own" column on every board. Caught
   because the base gate came out 6 instead of 22. Fixed in `s8_gate.py`; the gate numbers below are real
   gate runs.

---

## 1. The 17 obstructions — the target list

Every one of the 17, with a 0.60/0.30 **through** via standing exactly at its ORIGINAL XY on the
unmodified board. A through via needs **0.425 mm** of copper-edge clearance on **all six** layers
(0.300 annulus + 0.125 clearance) plus a 0.200 mm hole-to-hole gap. "Shortfall" is 0.425 minus the
measured edge distance to the binding item — how far that item would have to move for an in-place
conversion.

| # | net | span | XY (mm) | worst shortfall | binding item | kind | layer | items in the 0.425 set | pads in it |
|---|---|---|---|---:|---|---|---|---:|---|
| 1 | `/3V3` | F>In1 | 58.400, 55.550 | 0.5500 | trk `/LNA_EN` w0.25 | track | In2 | 24 | `/CAN_SCK`, `/RP2354B MCU/XIN` |
| 2 | `/GNSS_RX` | F>In1 | 53.900, 50.600 | 0.3260 | trk `/RP2354B MCU/USB_DM_MCU` w0.25 | track | In2 | 14 | `/GNSS_PPS`, `/GNSS_TX` |
| 3 | `/GNSS_RX` | In1>In2 | 52.900, 53.200 | 0.2818 | **pad C12.2 `/GND`** | pad | F | 13 | `/GND` |
| 4 | `/HGM` | F>In1 | 57.600, 55.150 | 0.1750 | trk `/RF_MISO` w0.20 | track | In2 | 13 | `/CAN_SCK`, `/LNA_EN` |
| 5 | `/LSM_INT1` | F>In1 | 54.400, 47.400 | 0.5141 | trk `/ICM_nCS` w0.25 | track | B | 18 | `/3V3`, `/ICM_INT2` |
| 6 | `/LSM_INT1` | In1>In2 | 54.400, 47.400 | 0.5141 | trk `/ICM_nCS` w0.25 | track | B | 18 | `/3V3`, `/ICM_INT2` |
| 7 | `/LSM_INT1` | In1>In2 | 51.500, 49.000 | 0.6500 | **pad FB1.2 `/3V3_ADC`** | pad | F | 6 | `/3V3_ADC` |
| 8 | `/PA_EN` | In2>B | 58.000, 51.900 | 0.4998 | trk `/RP2354B MCU/XIN` w0.25 | track | In1 | 3 | `/GND` |
| 9 | `/PA_EN` | F>In2 | 57.600, 52.200 | 0.4250 | trk `/RF_GPIO2` w0.20 | track | B | 6 | none |
| 10 | `/RF_GPIO0` | In2>B | 56.500, 55.200 | 0.4498 | trk `/SENS_MOSI` w0.25 | track | In1 | 13 | `/3V3`, `/PA_EN`, `/RF_GPIO3` |
| 11 | `/RF_GPIO0` | In2>B | 57.400, 56.100 | 0.4500 | trk `/1V1` w0.25 | track | F | 16 | `/GND` |
| 12 | `/RF_GPIO2` | F>In2 | 55.600, 55.200 | 0.5115 | trk `/SENS_SCLK` w0.20 | track | B | 9 | `/RF_GPIO0`, `/RF_GPIO3` |
| 13 | `/RF_MISO` | F>In1 | 53.900, 53.000 | 0.1500 | trk `/RF_nCS` w0.25 | track | F | 18 | `/RF_MOSI`, `/RF_nCS` |
| 14 | `/RF_MISO` | In1>In2 | 53.900, 53.000 | 0.1500 | trk `/RF_nCS` w0.25 | track | F | 18 | `/RF_MOSI`, `/RF_nCS` |
| 15 | `/RP2354B MCU/USB_DP_MCU` | F>In1 | 60.800, 44.100 | 0.1500 | trk `/3V3` w0.25 | track | F | 5 | `/GND` |
| 16 | `/RP2354B MCU/USB_DP_MCU` | In1>In2 | 60.800, 44.100 | 0.1500 | trk `/3V3` w0.25 | track | F | 5 | `/GND` |
| 17 | `/SENS_SCLK` | In1>B | 55.585, 53.453 | 0.1192 | **via `/RF_GPIO0` 350 µm** | via | F | 9 | none |

**What the table says, read as a whole.** The *binding* item is a track in 14 of 17, a pad in 2 and a via
in 1 — which reproduces `fab-da-growth-north` §5.1 exactly — but **the binding item is not the
obstruction**. The 0.425 mm exclusion circle around each site contains a **crowd**: 3 to 24 items, and 15
of 17 include at least one **pad**, which cannot be erased, moved or shrunk. Only two sites (row 9
`/PA_EN` F→In2 and row 17 `/SENS_SCLK` In1→B) contain no pad at all; every other site is pad-bound and
therefore cannot be converted *in place* at any price. Rows 5/6 and 13/14 are stacked pairs sharing one
XY; rows 15/16 likewise.

The full per-item geometry of all 17 sets — item kind, net, width, both endpoints, exact edge distance
and shortfall — is in `work/local.json`; the per-layer margin decomposition is in `work/obstruct.json`.

---

## 2. The minimum copper move — designed, then tested to destruction

The brief's hypothesis is that the copper to move is local. Four mechanisms were built and measured, each
stricter than the last, each allowing **zero foreign copper to be deleted**:

| mechanism | what moves | candidates | converted |
|---|---|---:|---:|
| **A. in place** | nothing | 17 | **0** |
| **B. shift + track bump + straight stub** | via ≤0.65 mm, offending tracks bumped sideways | 17 × 81 | **0** |
| **C. shift + chord jog + ROUTED corridor** | via ≤1.0 mm, tracks jogged by their own shortfall, corridor A\*-routed | **504 per via** | **0** |
| **D. routed corridor, no copper move** | via only, to the nearest legal site ≤2.6 mm | 17 | **0** |

Mechanism D carries its own decisive number: **the nearest legal 0.60/0.30 through site is 3.32–5.45 mm
away** for all 17 (median 4.2 mm), and no 0.20 mm corridor reaches it, because a corridor needs 0.225 mm
of berth each side — **0.450 mm of lane** — and the U10 field does not have it.

Mechanism C settles it. For each via it walks 21 shift radii (0, 0.05 … 1.00 mm) × 24 directions, and at
every site it jogs **every** offending track by its own shortfall + 0.03 mm as a chord-limited bump (only
the part of the segment inside the exclusion circle moves sideways; both endpoints stay, so the net
cannot break), then routes the corridor on the microvia's top and bottom layer. The failures are not
marginal in kind and are marginal in size:

| why it fails, worst candidate per via | count |
|---|---:|
| **endpoint inside the exclusion circle** — the fanout segment is 0.05–1.1 mm long, so its *endpoint* is inside the 0.425 mm circle and a jog cannot help: the endpoint is a pad or another via | 8 |
| bump blocked by the next track or pad (slack **−0.031 … −0.375 mm**) | 5 |
| no chord (the track misses the circle, so it is not the blocker) | 2 |
| pad immovable (`/GND`, `/3V3_ADC`) | 2 |
| foreign via immovable (`/RF_GPIO0` 350 µm) | 1 |

**The single most informative number in this report is 0.031 mm**: the best push-fit anywhere in the U10
field misses legality by 0.031 mm, against 0.450 mm of lane needed. That is not a search that needs a
better algorithm; it is a pitch that cannot hold the copper.

**So the minimum copper move is a clearing, not a jog.** The smallest clearing that converts anything is
**R = 0.70 mm per via** — a per-via disk, *not* a 10 mm disk about U10 — and it pays 247 items on 38 nets
for 15 of 17.

---

## 3. Execution, DRC-gated, batch by batch

Batches are per-via clearing radii, applied to a copy of the base board, zones refilled, each batch gated
by its own `kicad-cli` run on both rulesets. "Kept" means: a legal 0.60/0.30 through via at a site legal
on all six layers with hole-to-hole and copper-to-edge satisfied, plus a **routed** 0.20 mm corridor on
the microvia's top and bottom layer, plus no new DRC violation from the placement. Conversion order is
hardest-first (most crowded site first), because a placed via and its corridors are foreign copper to
every later one — that ordering change alone took R = 0.70 from 12 to 15.

| batch | attempted | **kept** | running non-through | items erased (track / via) | nets cut | unconnected | DRC SET DIFF vs base (own) | (no-HDI gate) |
|---|---:|---:|---:|---|---:|---:|---|---|
| **R = 0.70 mm** | 17 | **15** | **2** | 247 (221 / 26) | **38** | **30** | `+clearance 1, +track_dangling 43, +via_dangling 2` | `−microvia_drill 14` |
| **R = 1.30 mm** | 17 | **16** | **1** | 393 (357 / 36) | 43 | 36 | `+clearance 1, +track_dangling 51, +via_dangling 3, −via_diameter 1` | `−microvia_drill 15, −via_diameter 1` |
| **R = 1.60 mm** | 17 | **16** | **1** | 421 (382 / 36) | 43 | 35 | `+clearance 1, +track_dangling 48, +via_dangling 4, −via_diameter 1` | `−microvia_drill 15, −via_diameter 1` |

No `shorting_items`, no `tracks_crossing`, no `track_width`, no `annular_width`, no `isolated_copper` in
any batch. The single `clearance` error in every batch is **the same one object** and is named in §6. The
gate diff confirms the conversions are real: 14–15 of the 16 `microvia_drill_out_of_range` errors leave.

**Against the prior wave, same board, same acceptance test:**

| | radical R = 10 mm (prior) | **this wave R = 0.70 mm** | change |
|---|---:|---:|---|
| converted | 10 of 17 | **15 of 17** | **+5** |
| copper erased | 696 tracks + 64 vias | **221 tracks + 26 vias** | **−71 %** |
| nets cut | 48 | **38** | **−10** |
| unconnected | 81 | **30** | **−63 %** |
| final non-through | 0 (7 vias *deleted*) | 2, none deleted silently | +2 |
| min drill | 0.200 | 0.100 | worse by 1 via |

The prior wave's zero was bought by deleting seven vias with their fan-out; this wave converts 15 and
leaves 2 standing.

---

## 4. Re-routing what got cut — scripting, with freerouting attempted and abandoned

Every erased item is re-routed by script, in this order, each step checked against the model:

1. **restore verbatim** — if the erased segment is legal again once the new vias are in place, re-add it
   unchanged. This is the cheapest re-route and it carries the result: at R = 1.30, **242 of 393** erased
   items were restored with no geometry change at all.
2. **A\* detour** — otherwise the erased part of the segment is replaced by a routed detour, endpoints
   kept. **18** succeeded at R = 1.30.
3. **via restore** — erased vias of other nets are re-added at their own position when legal (**10** at
   R = 1.30); sub-standard vias are never restored, and a via that does not convert keeps its microvia.

At R = 1.30 the residue is **123 items**: 97 tracks where no detour exists (the fanout segments inside
U10's escape), 16 microvias that are the 16 conversions themselves, and 10 vias not restorable.

**Budget.** Scripted router: 0.075 mm grid, search box R + 3.5 mm, 60 000-cell expansion cap per search;
per batch ~6–9 min wall clock. **freerouting: attempted with a hard 5-minute router budget**
(`-mt 5`, jar `evidence/esc-routable2/tools/freerouting-2.5.0.jar`, java 25). DSN export succeeded in
0.4 s (360,810 B, `fr/R070.dsn`), but **the router wrote no `.ses` and no log inside a 20-minute wall and
was killed**, so **no freerouting result is reported or relied on** — the re-route is script-only. Its
value was going to be nil anyway for the same reason as everything else: the residual is not an unrouted
net, it is a **missing lane**. An autorouter can only place a 0.20 mm track where 0.450 mm is free, and
the measured best fit is 0.031 mm short.

---

## 5. Final verification of the best board

**Best board = `work/R130.kicad_pcb`** (16 of 17 converted — the fewest vias short of zero).

| check | base | **R = 1.30** | required | verdict |
|---|---|---|---|---|
| copper layers | 6 | 6 | 6 | ok |
| vias total | 337 | 328 | — | — |
| **non-through by span** | **17** (14 stacks) | **1** (`In2→B`, 1 stack) | **0** | **FAIL by 1** |
| by layer pair | F→In1 6 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 1 | `{In2→B: 1}` | `{}` | — |
| **DRC set diff, own rules** | `{via_diameter: 6}` | `+clearance 1, +track_dangling 51, +via_dangling 3, −via_diameter 1` | no new error | **FAIL — 1 clearance** |
| **DRC set diff, no-HDI gate** | 22 = 16 microvia + 6 via_diameter | `+clearance 1, +track_dangling 51, +via_dangling 3, −microvia_drill 15, −via_diameter 1` | — | 1 microvia left |
| **unconnected, `pcbnew`** | 0 | **36** | **0** | **FAIL** |
| **unconnected, `kicad-cli`** | 0 | **36** (`unconnected_items` list; no 499 cap in play) | 0 | agrees |
| **min drill** | 0.100 | **0.100** (1 via) | **≥ 0.200** | **FAIL** — the one remaining microvia |
| **RF void A / B** | 4.1699 mm² / 9.8338 % · 3.8754 / 9.1392 | **4.1699 / 9.8338 · 3.8754 / 9.1392 — bit-identical** | unchanged | **PASS** |
| **pads / gaps** | 657, sha `fad11a71c92532d9`, gaps <0.20/0.25/0.30 = 145/219/309 (U10 field 40/84/84) | **identical** | untouched | **PASS** |
| board area | 14,000.0000 mm² | 14,000.0000 (outline untouched) | — | ok |

**The R = 0.70 board** is the minimum-copper point and the better *engineering* one: **2 non-through**
(F→In1 1, In2→B 1), **30 unconnected**, min drill 0.100, RF void and pads bit-identical, DRC set diff
`+clearance 1, +track_dangling 43, +via_dangling 2`, 247 items erased on 38 nets.

**On the 371 pad-to-pad gaps.** I could not reproduce 371: the pad-gap census at 0.20/0.25/0.30 mm is
145/219/309 on the base board and identical on every output. What is proved instead is stronger and does
not depend on a threshold — **the pad geometry hash is `fad11a71c92532d9` on the base board and on all
three outputs**, over every pad's (ref, pad, x, y, sx, sy, rotation, copper outline). So every pad-to-pad
gap, under any definition including the one that gave 371, and U10's pad rows in particular, are
**unchanged by construction**: the apply path only ever removes or adds tracks and vias and has no pad
operation at all.

---

## 6. What remains, exactly

**One via, one DRC error, one drill, and 36 connections.**

1. **`/RF_GPIO0` In2→B at (57.400, 56.100), 0.100 mm microvia — not converted at any radius ≤ 1.60 mm.**
   It is convertible *in isolation*: `s10_diag.py` finds a legal through site **0.177 mm** away with both
   corridors routed when the other 16 are not placed (373 legal sites in total for this one row alone).
   It fails only when the other 16 go first, because their new corridors are foreign copper on the same
   two layers. So the last via is not a geometric impossibility — it is a **simultaneous-placement
   conflict over 0.450 mm lanes**, and resolving it needs one of the other 16 to move.
2. **The one `clearance` error** in every batch is that same object: the new `/HGM` through via (F→B)
   sits **0.0328 mm** from the surviving `/RF_GPIO0` microvia where 0.125 mm is required. It disappears
   the moment that last via converts — a consequence of (1), not a separate defect.
3. **min drill 0.100** is (1) again: one microvia holds the board's minimum drill below 0.200.
4. **36 unconnected (30 at R = 0.70)** are the erased fanout segments inside U10's escape: 97 tracks at
   R = 1.30 have **no legal detour**, which is the 0.450 mm lane statement in another form.

**Verdict.** 0 non-through with 0 unconnected is **not reachable from this board by clearing local
copper**, and that is measured three ways: 504 candidates per via find no zero-deletion conversion; the
nearest legal through site is 3.3–5.5 mm away with no corridor to it; and the best push-fit anywhere in
the field misses legality by 0.031 mm against 0.450 mm of lane needed. The brief's alternative stands and
is what this wave delivers: **15 of 17 converted for 38 nets cut and 30 unconnected**, strictly better
than the prior wave's 10 of 17 for 48 nets and 81 unconnected, rising to **16 of 17** if another 0.60 mm
of clearing per via is paid. The remaining two are the same two doors wave 18/19 left open: the HDI
1+2+1 build the vias were always designed for, or an LQFP-100 re-escape.

### Artefacts

| file | note |
|---|---|
| `work/R070.kicad_pcb` | **minimum-copper result**: 15/17, 247 items, 38 nets, unconnected 30 |
| `work/R130.kicad_pcb` | **best non-through**: 16/17, non-through 1, unconnected 36 |
| `work/R160.kicad_pcb` | radius ceiling: still 16/17 — the last via is not a radius problem |
| `work/local.json` | **the step-1 target list**: every infringing item per via, with geometry |
| `work/table17.md` | the §1 table as generated |
| `work/obstruct.json`, `work/open.json` | per-layer margins at the original XY; nearest legal site per via |
| `work/plan_bump_fine.json` | the 504-candidate zero-deletion search, every failure reason recorded |
| `work/plan_routed.json` | mechanism D: routed corridors to the nearest legal site |
| `work/R070.json`, `work/R130.json`, `work/R160.json` | per batch: kept/attempted, every erasure, every re-route |
| `drc/final2_*.json`, `drc/setdiff_final2.json` | both rulesets per batch and the set diffs |
| `work/ident_R0*.json`, `census_R130.json`, `void_measure.json` | census, pad hash, gaps, RF void |
| `fr/R070.dsn` | the freerouting attempt's only output (no `.ses` was produced) |

Scripts in the order they matter: `s1_obstruct.py` (the 17, per layer) · `s2c_local.py` (complete
infringing set + jog feasibility at each original XY) · `s2b_open.py` (nearest legal site) ·
`s3_plan.py` / `s6_bump.py` (zero-deletion shift + bump + corridor; 0 of 17) · `s4_route.py` (routed
corridor only; 0 of 17) · `s5_batch.py R` (per-via clearing, conversion, restore/detour re-route) ·
`s7_apply.py` (bump plan → board) · `s8_gate.py` (DRC set diffs, both rulesets) · `s9_verify.py` (census,
pad hash, pad gaps) · `s10_diag.py` (why the last via fails) · `s5_void.py` (RF void) · `vmod.py`
(editable copper model) · `vgeom.py` (KiCad-outline geometry primitives).

**Provenance.** Everything above is **measured** with `pcbnew` (KiCad 9.0.7 bundled python) and
`kicad-cli pcb drc --format json --severity-all --units mm`, on copies, in this evidence dir. The only
figures not re-derived here are the prior-wave column of the comparison table, quoted from
`fab-da-radical/REPORT.md`, and the 371 pad-gap figure, which this wave could not reproduce and therefore
does not use. No number here is estimated.