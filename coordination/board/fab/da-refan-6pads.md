# drone-arm — re-fan the 6 remaining U10 pads (rip-debris pass, rev B)

STATUS: **COMPLETE.** The debris story was tested and it is **half right**: the copper in
front of the six pads is not debris at all, but there is a *different* population of
rip debris in the same neighbourhood, and clearing it opens exactly one of the six pads.
**1 of 6 is closed** (pad 5, /3V3) with zero new violations; pads 23 and 24 verify at a
0.4/0.2 mm via class the board's own rule forbids, and pads 16, 19, 30 have no path at any
via class. Unconnected **9 → 8**. Verdict: **still not sendable.**

One task only: the six U10 pads (5, 16, 19, 23, 24, 30) the previous wave could not close.
Nothing else on this board was re-opened.

- Input: `evidence/da-escape-7pads/work/f2r.kicad_pcb` — the rev-B package board *after*
  the pad-13 closure: DRC 36, unconnected 9, 344 through vias. Copied to `work/b0.kicad_pcb`
  (sha256 `94A747A79F1C5130…`), source tree never written.
- Output: `evidence/da-refan-6pads/` (junction → `D:\ep-audit-evidence\da-refan-6pads`;
  free space at start **141.84 GB** on D:).
- Host: KiCad 9.0.7, `kicad-cli.exe` + bundled `python.exe` (pcbnew). Board: 6 layers,
  165 footprints, min drill 0.200.

## 0. Preconditions — the input board reproduced, not quoted

| check | required | measured here | verdict |
|---|---|---|---|
| baseline DRC (copy + `.kicad_pro`, `--severity-all --units mm`) | 36 | **36** — 29 `track_dangling`, 5 `via_diameter`, 2 `track_width` | reproduces |
| unconnected, kicad-cli / pcbnew | 9 / 9 | **9 / 9** (`GetUnconnectedCount(False)`, no 499 cap) | reproduces |
| vias, span | 344, 0 non-through | **344, `non_through_by_span` 0** | reproduces |
| min drill | 0.200 | **0.200** (tools 0.20 / 0.30 / 0.35) | reproduces |
| RF void | 4.1699 mm² / 9.8338 % | **4.1699 / 9.8338** (void_B 3.8754 / 9.1392) | reproduces |
| design rules loaded from the board itself | 0.125 / 0.2 / 0.6 / 0.1 / 0.2 / 0.2 / 0.5 | identical, none zero | reproduces |

The companion set is the `.kicad_pro` alone: the whole `fab-da-route-35` tree carries no
`fp-lib-table` and no local `.pretty`, so the invented-footprint failure mode of other
boards cannot occur here. Every DRC below was run in its own directory holding the board
**and** that `.kicad_pro`.

## 1. STEP 1 — the 38 blockers, classified real vs debris

The 38-object census reproduces exactly on the input board (`c1_blockers.py`, foreign track
or via within 0.35 mm of a U10 pad polygon, tolerance 2 µm, pad geometry from KiCad's own
`TransformShapeToPolygon`).

**Result that changes the picture: none of the 38 is debris by the DRC's own definition.**
Every one of them has both terminals on same-net copper — `attach=2` for 38 of 38 — and not
one is in the baseline's `track_dangling` list. The 0.018 / 0.050 / 0.100 / 0.106 mm stubs
that read as debris in the previous report are *not* free ends: they are the last link
between a neighbour pad and its fan-out via, or a duplicate of a link that still exists.
So the brief's "delete the 15 debris objects and the lanes open" does not survive contact:
the 15 are **redundant**, not dangling, and redundancy of that kind need not compose.

Tested three ways, in this order:

1. **Per-object redundancy** (the previous wave's `g6_prune.py` method, reproduced): 15 of
   38 leave the unconnected count untouched when deleted *alone*.
2. **Composition-safe sweep** (`c2_prune.py`): deletion accepted only if the pcbnew
   unconnected count is still the baseline **after that deletion**, passes repeated to a
   fixed point. 14 of the 15 compose; the 15th (`/LSM_INT1` F.Cu 0.225 mm) must stay,
   because two of its parallel twins were deleted and it becomes the survivor. This is
   precisely the failure that killed the previous wave's batch of 15 (unconnected 10 → 11).
3. **The debris DRC actually flags** (`c3_dangle.py`, `c3b_dangle_sel.py`): the U10 window
   (51–62 × 45–58 mm) holds **31 `track_dangling` items** — a *different*, larger population
   than the 38. Acting on all 31 is wrong, and the script says why per object:

| rejection rule | objects hit | examples |
|---|---|---|
| is a ratsnest endpoint of the base board — deleting the target connects nothing | 6 | `/RF_GPIO3` F.Cu 0.890 mm **is** what pad 23 has to reach; `/RF_SCLK` In2 0.050 mm is pad 16's; `/RF_nCS` In2 13.153 mm is pad 19's |
| route fragment > 1.20 mm, not a stub | 6 | `/GNSS_RESET_N` B.Cu 10.587, `/RF_nCS` In2 13.153, `/3V3` F.Cu 2.605, `/RF_GPIO0` In2 2.143, `/LNA_EN` In2 1.697 / 1.400, `/RF_MOSI` B.Cu 1.400, `/1V1` F.Cu 1.220 |
| outside the window | 2 | `/3V3` F.Cu 1.117 at x 61.60 |

The reasons overlap (an object can be both a ratsnest endpoint and a 13 mm fragment); the
rejected population is **14 objects**, leaving 17 of the 31.

**17 deleted** (all ≤ 1.20 mm, none a ratsnest endpoint, unconnected unchanged after each),
plus the **14** redundant ones — **31 objects removed in total**, and the board's
unconnected count never left 9.

Where the 17 sat, relative to the pads: **2 within 0.35 mm, 8 within 1.0 mm, 11 within
2.0 mm** — and both of the 0.35 mm ones are on **inner** layers (`/GNSS_RX` In1 1.100 mm at
0.22 mm from pad 13; `/RF_GPIO0` B.Cu 0.106 mm at 0.30 mm from pad 24). That is the
mechanical reason most lanes did not move: an inner-layer stub obstructs a *via*, not the
F.Cu track corridor.

DRC set diff, baseline → debris-cleared (`c9_drcdiff.py`, keyed by type + item uuid, not by
totals): **36 → 34**, +13 `track_dangling`, −15 `track_dangling`, **0 new types**, and the 2
`track_width` / 5 `via_diameter` untouched. Deleting the 14 redundant objects cost +2
`track_dangling` (the surviving ends of the deleted `/LSM_INT1` via), which is why the
dangling sweep was run *after* it and not instead of it.

## 2. STEP 2 — the six lanes, before and after

Instrument: `g7b_lane.py`, H = 0.01 mm, flood fill from the pad over the **F.Cu** track mask
(clearance 0.125 + half-track 0.100 + 0.012 raster margin = 0.237), via sites tested against
the **all-layer** minimum plus exact hole-to-hole. Reproduces the previous wave's numbers on
`b0` to 4 decimals, which is the check that the instrument is unchanged.

| pad | net | lane mm² before | after | extent mm | 0.6 / 0.5 / 0.4 mm sites **before** | **after** |
|---|---|---|---|---|---|---|
| **5** | /3V3 | 0.1604 (the bare pad) | **1.0063** | 0.41 → **1.88** | 0 / 0 / 0 | **1026 / 1917 / 3000** |
| 16 | /RF_SCLK | 0.2262 | 0.2262 | 0.91 | 0 / 0 / 0 | 0 / 0 / 0 |
| 19 | /RF_nCS | 0.1750 | 0.1750 | 0.61 | 0 / 0 / 0 | 0 / 0 / 0 |
| 23 | /RF_GPIO3 | 0.9693 | 0.9693 | 1.85 | 0 / 0 / 25 | 0 / 0 / 25 |
| 24 | /3V3 | 0.9520 | 0.9520 | 1.83 | 0 / 0 / 131 | 0 / 0 / 131 |
| 30 | /RP2354B MCU/XIN | 0.3841 | 0.3841 | 1.20 | 0 / 0 / 0 | 0 / 0 / 0 |
| (13) | /GNSS_PPS | 1.0850 | 1.0850 | 1.90 | closed in the previous wave | — |

**So the pads were blocked by junk for exactly one pad.** Pad 5's free region goes from the
bare 0.200 × 0.800 pad to a 1.88 mm lane with a thousand legal 0.6 mm via sites — that is the
previous wave's "only a pad-4 re-fan would free it" claim, disproved: a composition-safe
cleanup frees it without touching pad 4, and pad 4 stays connected. The other five lanes are
**bit-identical before and after**, which is the honest reading: their blockers are real
route copper of their neighbours, and no amount of junk removal touches them.

## 3. STEP 3 — what now fits: attempts, keeps, set diff

Router: windowed A* at H = 0.01 over 6 layers, classes 0.60/0.30, 0.50/0.25, 0.40/0.20
(`c5_route.py`), each path reduced by greedy line-of-sight and **re-verified exactly** at
0.125 mm (`g10_place.py`), then applied on a copy, zones refilled (`ZONE_FILLER`, 5 zones),
and DRC'd with the board's own `.kicad_pro`.

Target choice matters: the target is an island of the same net **containing a pad of another
footprint**, not whatever the ratsnest names — two of the six pads are ratsnest-linked to a
0.05 mm dead stub and a 13 mm fragment, so "join the ratsnest" could have been satisfied
while the signal still went nowhere.

| # | pads | class | result | unconnected | DRC | kept? |
|---|---|---|---|---|---|---|
| A | 5 /3V3 | 0.6/0.3 | **3.347 mm, 5 segments, 0 vias, all F.Cu**, pad 5 → FB1.1 | 9 → **8** | 34 → **33**, **0 new**, 1 `track_dangling` resolved | **KEPT** |
| B | 23 /RF_GPIO3 | 0.4/0.2 | 2.457 mm, 3 segments, 1 via | 9 → 8 | 34 → 35, **+1 `via_diameter`** | no — adds a violation |
| C | 24 /3V3 | 0.4/0.2 | 2.325 mm, 3 segments, 1 via | 9 → 8 | 34 → 35, **+1 `via_diameter`** | no — adds a violation |
| D | 23 **and** 24 | 0.4/0.2 | both placed | 9 → 7 | 34 → **45**: **7 `shorting_items`**, 1 `clearance`, 1 `hole_to_hole`, +2 `via_diameter` | rolled back |
| E | 16, 19, 30 | 0.6 / 0.5 / 0.4 | **no path at any class** — A* exhausts 2192 / 1822 / 3448 cells inside the pocket | — | — | nothing to gate |

**Kept / attempted: 1 of 6 closed, 5 failed.** A and B/C were attempted separately *and*
together; D is the composed attempt and it is the one that fails hardest.

Two measured details worth recording:

- **pads 23 and 24 share one pocket.** Their best legal 0.4 sites are (56.295, 54.205) and
  (56.355, 54.355) — **0.150 mm apart**, against the 0.525 mm two 0.4 mm vias need. Each
  verifies alone; together they short 7 times. This is the same collision the previous wave
  hit between pads 13 and 24, moved one pad over.
- The 0.6 class never even gets a start cell on those pads: the best all-layer headroom
  anywhere in their lanes is 0.355 / 0.384 mm against the 0.437 needed — and the cap is the
  **adjacent U10 pad itself** (0.365 / 0.393 mm away). At 0.4 mm pitch the inter-pad gap is
  0.200 mm, so no via of any size ≥ 0.6 can ever be placed *between* two pads of a row. The
  only legal 0.6 sites are outboard, and the outboard rank is occupied.

## 4. STEP 4 — the residual, per pad, with the one structural change

`c7_headroom.py` finds the best cell of each lane (the cell a via would go in) and lists every
foreign object within 0.55 mm with the exact distance it would have to move to reach the 0.437
mm a 0.6/0.3 via needs. Absolute legal requirement for a 0.6 via is 0.425 (0.125 + 0.300);
0.437 adds the 0.012 raster margin.

| pad | best all-layer headroom in lane | needs | shortfall | capping objects (distance → must move) |
|---|---|---|---|---|
| 16 | **0.2069** at (53.985, 52.135) | 0.437 | **0.230** | `/GNSS_RX` In3 w0.20 ×4 (0.211 → 0.226), `/3V3` F.Cu w0.25 (0.214 → 0.223), `/ICM_nCS` B.Cu w0.25 ×2 (0.214 → 0.223), **pad U10.15** (0.235 → 0.202) |
| 19 | **0.2923** at (53.795, 53.405) | 0.437 | **0.145** | **pad U10.20** (0.295 → 0.142), `/GNSS_RX` In3 ×2 (0.296 → 0.141), `/RF_MISO` In1/In2 ×3 (0.301 → 0.136), **pad U10.18** (0.305 → 0.132), `/GNSS_RX` via 0.6 (0.323 → 0.114) |
| 23 | **0.3551** at (56.335, 54.185) | 0.437 | **0.082** | `/PA_EN` F.Cu w0.20 (0.365 → 0.072), **pad U10.24** (0.365 → 0.072), `/MAIN_LED` In1 w0.25 ×5 (0.366 → 0.058) |
| 24 | **0.3840** at (56.315, 54.245) | 0.437 | **0.053** | `/PA_EN` F.Cu w0.20 (0.385 → 0.052), **pad U10.23** (0.393 → 0.044), `/MAIN_LED` In1 ×5 (0.395 → 0.013), `/RF_GPIO0` In2 w0.25 (0.424 → 0.013) |
| 30 | **0.1050** at (59.145, 55.705) | 0.437 | **0.332** | `/RF_MISO` In3 w0.20 (0.105 → 0.332), `/RF_MOSI` In4 w0.20 (0.105 → 0.332), `/RF_GPIO2` B.Cu ×2 (0.145 → 0.292), `/1V1` In4 + via (0.230/0.259) |

**The residual is not "one object moved".** For pads 16, 19, 23 and 24 the binding cap is a
**U10 pad of the same row** — copper that cannot move without moving the part. No local edit
fixes them; that is the geometric limit of a 0.4 mm pitch field whose both fan-out ranks are
occupied. For pad 30 the cap is a four-layer stack of other nets' tracks crossing the pocket.

**The one structural change that fixes the residual: re-fan the U10 perimeter ring as a
staggered two-rank escape, outboard of the current rank.** Collateral measured **here, on
this board** (`work/c8_ring.py`): the ring is **280 objects — 233 tracks + 47 vias on 44 nets
— within 1.2 mm of a U10 pad**, all of which have to be ripped and re-laid together. The
alternative "move U10" detaches **76 of 90 pads** that have copper within 0.05 mm (inherited
measurement from the previous wave; not re-run because the conclusion — that moving the part
moves all 90 pads and their escapes together without creating a rank slot — does not depend
on it), and it is not the proposal for that reason.

Cheaper options, each measured and each rejected on a stated reason:

- **Declare a 0.4/0.2 via class for the U10 breakout** (annular 0.100, exactly the board's own
  `via_min_annular`; drill 0.200, the board's own minimum). It closes 23 *or* 24 — not both,
  they share the pocket — and it converts the **5 existing `via_diameter` errors** on the
  board into conforming geometry. It is a **design-rule change** (via_min_size 0.6 → 0.4) and
  therefore an owner decision, not something this task may take. Note the board already
  contradicts its own rule with 5 such vias.
- **A smaller drill (0.127)** does not exist here: measured drill tools are 0.20 / 0.30 / 0.35
  and the board's `m_MinThroughDrill` is 0.200. Not proposed.

## 5. STEP 5 — whole-board verification of the changed board (`work/b3r.kicad_pcb`)

| invariant | required | measured | verdict |
|---|---|---|---|
| span census | 0 non-through | **343 vias, 343 `THROUGH F.Cu → B.Cu`**, `non_through_by_span` 0, `non_through_by_drill_lt_0_2` `{}` | **PASS** |
| min drill | ≥ 0.200 | **0.200** (tools 0.20 / 0.30 / 0.35 / 0.6 slot / 0.65 / 4.3) | **PASS** |
| unconnected, kicad-cli | — | **8** | 9 → 8 |
| unconnected, pcbnew | — | **8** | both tools agree |
| DRC set diff vs baseline | no new types | **36 → 33**: 0 new types; 13 `track_dangling` added by the cleanup, 16 resolved, net −3; 2 `track_width` / 5 `via_diameter` untouched | **PASS** |
| RF void | 4.1699 mm² / 9.8338 % bit-identical | **4.1699 = 9.8338 %**, void_B 3.8754 = 9.1392 % — identical to `b0` | **PASS** |
| board size / layer count | 140 × 100, 6 Cu | 140.15 × 100.15 bbox, 6 Cu, 165 footprints, 0 on the back | unchanged |

Remaining 8 unconnected: U10 pads **16, 19, 23, 24, 30** (5), the two cross-layer joins
(/GNSS_RESET_N, /RF_GPIO0), and the GND F.Cu zone-fill split.

The 13 added `track_dangling` are not new defects introduced by me: each is a *surviving*
track whose partner I deleted (the deleted one carried the violation, its twin inherits it).
None is a new object, and the type count still fell by 3. This is stated because a +13/−16
set diff is exactly the shape that a "net −3" total can hide.

## 6. STEP 6 — package, drill census and POS reconciliation

The board changed, so the package was rebuilt by the **previous wave's own
`export_final.ps1`, unmodified** (staged into `pkg/` with its 10 helper scripts), run as
`-Board work/b3r.kicad_pcb -OutDir pkg -Rev B -BaseDir work/b0.kicad_pcb`:

- `pkg/package/` — **20 files** (13 Gerbers incl. Edge_Cuts, `.gbrjob`, 2 Excellon PTH/NPTH
  apart, 1 `.pos`, `FAB-README`, 2 drill maps), zipped to
  `pkg/drone-arm-main-revB-fab-package-6L.zip` (20 entries, **408,085 B**).
- Finish **ENIG** on both fields (V24 `Finish`, V36 explicit `SurfaceFinish`); revision **B**
  on 16 carriers (V25/V26); the stamp changed no geometry (V27, 13 layers compared).
- Rules really loaded: V06 pcbnew reads 0.125 / 0.2 / 0.6 / 0.2 / 0.2 from the sibling
  `.kicad_pro`; V07 a deliberately-wrong `.kicad_dru` moves DRC **33 → 544** (511 clearance).
- **Assertions: 34 pass / 2 fail of 36.** The two failures are V30/V31 — unconnected at
  **8** instead of 0. They failed at 10 before the last wave, at 9 after it, at 8 now.
  Everything else passes, including V28/V29 span census (343 vias, 0 non-through), V19 min
  drill 0.200, V32 RF void bit-identical, V16/V17/V18 drill file vs board, V20/V21 pos,
  V24/V36 ENIG, V25/V26 revision B, V33 zip contents, V35 sources unmodified.

### 6.1 The drill census, corrected — and the correction to the correction

Measured on the shipped package, per file, drills and G85 slots counted apart:

| file | FileFunction | **drills** | **G85 slots** | hits |
|---|---|---|---|---|
| `main_rev_b-PTH.drl` | `Plated,1,6,PTH` | **361** — 0.20 ×23, 0.30 ×63, 0.35 ×275 | **4** @0.60 (J1.S1, oblong 0.6×1.4 / 0.6×1.7) | 365 |
| `main_rev_b-NPTH.drl` | `NonPlated,1,6,NPTH` | **6** — 0.65 ×2, 4.30 ×4 | 0 | 6 |
| **package total** | | **367** | **4** | **371** |

Board-side reconciliation (`span_census7.py`, `all_files_match_board = true`): 343 through
vias + 18 round PTH pads = **361 PTH drills**; 6 NPTH pads; **4** slotted pads = 4 G85 slots;
KiCad's own `total_holes` = **371** = 367 drills + 4 slots.

Both published figures were wrong, and in two different ways:

- The shipped line **"361 drills + 4 slots = 371 hits"** does not add up as written
  (361 + 4 = 365). The missing term is the **6 NPTH drills**: 361 + 6 + 4 = 371. The total was
  right; the middle term was omitted.
- The brief's **"371 drills (365 PTH + 6 NPTH) + 4 G85 slots = 375 hits"** is a **double
  count**: 365 PTH counts the 4 slotted J1 pads as drills *and* then counts them again as
  slots. The 4 slotted pads are four holes that a fab drills as four G85 lines — they are one
  population, not two. Correct statement: **367 drills (361 PTH + 6 NPTH) + 4 G85 slots = 371
  hits.** Proven three ways above: the per-file Excellon counts, the board-side pad/via
  census, and KiCad's `total_holes` of 371.

### 6.2 The POS row count, reconciled

`main_rev_b-REV-B-all-pos.csv` has **162 lines = 1 header + 161 component rows** against
**165 footprints**. The 4 that are absent are **H1, H2, H3, H4** — the mounting holes, which
carry *exclude from position files*. So 165 − 4 = **161**, and `span_census7.py` states the
same number independently as `expected_pos_rows: 161`. V20 checks it directly
(`.pos data rows == footprints − pos-excluded`). The earlier "162 rows = 161 components"
phrasing was off by one because it counted the CSV header as a row.

## 7. Verdict

**IS DRONE-ARM NOW SENDABLE TO A FAB? — NO.**

What this pass establishes, with numbers:

1. **The debris hypothesis was tested and is half true, in a different place than expected.**
   None of the 38 blockers around the six pads is debris: all 38 have both terminals on
   same-net copper and none is DRC-flagged dangling. The debris is a separate population of
   **31 `track_dangling` tracks** in the U10 window, of which **17** can be removed safely
   (the other 14 are either a pad's own ratsnest target or route fragments > 1.20 mm), plus
   **14** electrically redundant objects removed under a composition-safe sweep. **31 objects
   gone, unconnected never above 9, DRC 36 → 34, 0 new types.**
2. **That cleanup closes exactly one pad.** Pad 5 (/3V3) went from a 0.160 mm² "lane" that was
   only the bare pad to 1.006 mm² with 1026 legal 0.6 mm sites, and is now closed by a
   **3.347 mm all-F.Cu track, 0 vias**, to FB1.1. DRC 34 → 33 with **0 new** violations,
   unconnected **9 → 8** on both tools. The previous wave judged pad 5 closable only by
   ripping pad 4's escape; that is now shown to be unnecessary.
3. **Five pads remain, and the reason is geometric, not unfinished work.** Pads 23/24 verify
   at the 0.4/0.2 class but each costs a `via_diameter` error against the board's own 0.6 mm
   floor, **and they share one pocket** (their best sites are 0.150 mm apart; placed together
   they short 7 times). Pads 16/19/30 have **no legal via site of any class anywhere on their
   lanes** and no A* path at any class. For 16/19/23/24 the capping object is a **neighbouring
   U10 pad** — copper that cannot move without moving the part.
4. **What would actually make it sendable**, in cost order, each measured:
   - **Declare a 0.4/0.2 mm via class for the U10 breakout** (annular 0.100 = the board's own
     `via_min_annular`; drill 0.200 = its own minimum). Closes one of 23/24 immediately and
     **resolves the 5 existing `via_diameter` errors**. It is a design-rule change
     (`via_min_size` 0.6 → 0.4) — an owner decision, not taken here.
   - **Re-fan the U10 ring as a staggered two-rank escape** — the only path that keeps 0.2 mm
     tracks, 0.125 mm clearance and 0.6 mm vias. Collateral, measured here: **233 tracks + 47
     vias on 44 nets within 1.2 mm of a U10 pad** (280 objects).
   - Then the 2 cross-layer joins (/GNSS_RESET_N, /RF_GPIO0) and the GND F.Cu fill split —
     3 unconnected items that were never in the seven-pad story.

Deliverables: `work/b3r.kicad_pcb` (the changed board, sha256 `21C000EF33B07EAC…`),
`pkg/package/` + the zip, `pkg/assertions.json`, `pkg/drill_census.json`, `pkg/run.log`,
and the measurement JSONs in `work/`.

## A. Appendix — instruments and raw evidence
`work/c1_blockers.py` blocker census + per-object terminal-attachment classification ·
`work/c2_prune.py` composition-safe redundancy sweep · `work/c3_dangle.py` (all dangling,
deliberately over-broad, kept for the audit trail) and `work/c3b_dangle_sel.py` (the
conservative subset that was applied) · `work/c5_route.py` windowed A* to a pad-bearing
destination island · `work/g10_place.py` line-of-sight reduction + exact re-verify ·
`work/g7b_lane.py` lane flood fill · `work/c7_headroom.py` residual attribution ·
`work/c8_ring.py` U10 fan-out ring census · `work/c9_drcdiff.py` per-type set diff ·
`work/span_census7.py`, `work/s5_void.py` the
programme's own board-truth instruments · `work/edit.py`, `work/refill.py` board edits and
zone refill. DRC JSON in `drc/`, logs in `logs/`, measurement JSON in `work/`.
