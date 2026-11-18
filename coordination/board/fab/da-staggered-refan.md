# drone-arm — staggered two-rank U10 ring re-fan (rev B, 6 layers)

STATUS: **COMPLETE.** The fix was designed as specified, then measured against the board,
and it **cannot work here — for a reason that is one layer down from the diagnosis**. The
cap on these five lanes is not the 0.4 mm pad pitch and not the F.Cu escape pattern: it is
the **saturation of the worst inner layer**. In the whole 10 × 8.3 mm U10 corner there are
**0 cells out of 132,800** that clear the 0.425 mm a 0.6/0.3 through via needs; the single
best cell in the window is **0.3998 mm** (0.010 mm short, exactly), and what caps it is a
`/3V3` through-via stack 0.415 mm away. Board-wide, **64.7 % of the board** can host that
same via. So no escape *pattern* — one rank, two ranks, or ten — manufactures clearance on a
layer that is full everywhere. **0 of 5 pads closed; pad 5 verified still closed;
unconnected 8 → 8; DRC 33 → 33** (the one applied batch was rolled back). Verdict:
**still not sendable.**

One task only: execute the staggered two-rank U10 ring re-fan and close pads 16, 19, 23, 24,
30. Nothing else on the board was changed.

- Input: `evidence/da-refan-6pads/work/b3r.kicad_pcb`, sha256 `21C000EF33B07EAC…`,
  copied to `work/b0.kicad_pcb`; the source tree was never written.
- Output: `evidence/da-staggered-refan/` (junction → `D:\ep-audit-evidence\da-staggered-refan`).
  Free space at start **141.78 GB** on D:, **10.86 GB** on E:.
- Host: KiCad 9.0.7, `kicad-cli.exe` + bundled `python.exe` (pcbnew). Board 6 Cu,
  165 footprints, 140.15 × 100.15 mm. Every pcbnew script ran as a bounded job, and each
  background job was checked to have exited before the next one started. On the hang: the
  inherited `geo.py` reads a via's size with **`GetWidth(TopLayer())` — the form that takes a
  layer argument** — and that completed in every run of this session; the **no-argument
  `GetWidth()` is never called anywhere in this evidence set**, which is the form the standing
  warning covers. Via type is written as integer **3 = THROUGH** (KiCad 9 has no
  `VIATYPE_BLIND`/`VIATYPE_BURIED`), and a 0.4 mm via was written with `SetWidth`/`SetDrill`
  only.

## 0. Preconditions — the baseline reproduced, not quoted

Every DRC below ran in its own directory holding the board **and** its `.kicad_pro`
companion. This mattered: the raster instruments read `m_MinClearance` from the project, and
the first run of them in a directory without the `.kicad_pro` silently used **clearance 0**.
That error was caught, the companion installed, and every number below re-measured.

| check | required | measured here | verdict |
|---|---|---|---|
| DRC (`--format json --severity-all --units mm`) | 33 | **33** — 26 `track_dangling`, 5 `via_diameter`, 2 `track_width` | reproduces |
| unconnected, kicad-cli / pcbnew | 8 / 8 | **8 / 8** | reproduces |
| vias, span | 343, 0 non-through | **343, `non_through_by_span` 0**, `THROUGH F.Cu → B.Cu` 343 | reproduces |
| min drill | 0.200 | **0.200** (tools 0.20 / 0.30 / 0.35 / 0.60 slot / 0.65 / 4.30) | reproduces |
| RF void | 4.1699 mm² / 9.8338 % | **4.1699 / 9.8338** (void_B 3.8754 / 9.1392) | reproduces |
| design rules actually loaded | 0.125 / 0.2 / 0.6 / 0.1 / 0.2 / 0.2 / 0.5 | `{'min_clearance': 0.125, 'track_min_width': 0.2, 'via_min_size': 0.6, 'via_min_annular': 0.1, 'hole_min': 0.2, 'hole_to_hole': 0.2, 'copper_edge': 0.5}` | reproduces |
| ring collateral within 1.2 mm of U10 | 233 tracks + 47 vias on 44 nets | **280 objects = 233 tracks + 47 vias on 44 nets** (`c8_ring.py`, re-run here) | reproduces |
| drill census / POS | 367 drills + 4 slots = 371; POS 161 | **371 `total_holes`, 367 minus slots, 4 slot pads, 343 vias + 18 round PTH = 361 PTH, 6 NPTH; 165 footprints − H1–H4 = 161 `expected_pos_rows`** | reproduces |

The four U10 sides are as measured, not assumed: left column x = 54.05 (pads 1–20,
y 46.20…53.80), bottom row y = 54.95 (pads 21–40, x 55.20…62.80), right column x = 63.95,
top row y = 45.05; pad copper 0.800 × 0.200, pitch 0.400, so the inter-pad gap is 0.200.
The five stranded pads sit in the **bottom-left corner**: 16 at (54.050, 52.200) and 19 at
(54.050, 53.400) on the left column, 23 at (56.000, 54.950), 24 at (56.400, 54.950) and 30
at (58.800, 54.950) on the bottom row.

## 1. STEP 1 — the two-rank ring, stated precisely

Frame: per U10 side, `n` = outward normal, `t` = in-row tangent, `p` = 0.400 pitch, pad half
length 0.400, track 0.200, clearance 0.125, via 0.600/0.300, 6 layers.

**Rank 1.** Track 0.200 wide leaves the pad centre along `n` at **exit angle 90° to the row**
(the pad's own long axis), straight, length `d1`, and terminates in a 0.600/0.300 through via
at

    d1 = 0.400 (pad half length) + 0.300 (via radius) + 0.125 (clearance) = 0.825 mm

so the site is `(pad_x − 0.825, pad_y)` on the left column and `(pad_x, pad_y + 0.825)` on
the bottom row. Rank 1 is **outboard of the pad row, never between two pads** — that is the
whole point of the pattern. Its clearance to the two adjacent pads is 0.520 mm (corner
distance `sqrt(0.425² + 0.300²)`), i.e. 0.095 mm of margin over the 0.425 required.

**Rank 2.** Same track width and same 90° exit, via at

    d2 = d1 + Δ,  Δ ≥ sqrt(0.725² − 0.600²) = 0.407 mm,  used as 0.605 mm

where 0.725 = 0.600 + 0.125 is the minimum centre distance between two 0.6 vias, and the
0.600 term is the lateral offset below. Δ = 0.407 clears a rank-1 via *diagonally*; 0.605 is
the straight-in figure.

**Stagger offset.** Two rank-1 vias cannot be placed at the pad pitch: the minimum pitch at
which a 0.200 track can pass between two 0.6 vias is

    0.200 + 2 × 0.125 + 0.600 = 1.050 mm

and at 0.4 pad pitch the vias would be 0.400 apart, giving the passing track **zero**
clearance. So rank-1 vias are taken on **every third pad (pitch 1.200 mm)** and the rank-2
lane takes the **middle of each 1.200 gap — lateral stagger offset 0.600 mm**, where its
clearance to each rank-1 via is `0.600 − 0.300 − 0.100 = 0.200 ≥ 0.125`.

**Consequence, and it is arithmetic not opinion:** two ranks close **two pads of every
three**; the third of each triplet has no via slot in two ranks and must run out to a third
rank. Pads 16/19 (three pitches apart) and 23/24 (adjacent, 0.4) are compatible with the
lattice; the nominal assignment is 19 → rank 1, 16 → rank 2, 23 → rank 1, 24 → rank 2
(Δ = 0.605 at 0.4 lateral: `sqrt(0.4²+0.605²) = 0.726 ≥ 0.725`, marginal), 30 → rank 1.

### 1.1 Then the pattern was measured against the copper, and it fails on a precondition

The design above assumes a legal 0.6 via *site family* exists outboard. It does not.

| designed rank-1 site | pad | measured worst-layer headroom | need | what caps it |
|---|---|---|---|---|
| (53.225, 52.200) | 16 | **0.1000** | 0.437 | 18 foreign objects within 0.437; the cap is a **`/RF_MISO` 0.600/0.300 through via at 0.100** (on all six layers), then `/GNSS_RX` In3 ×2 at 0.194, `/LSM_nCS` In4 at 0.204 |
| (53.225, 53.400) | 19 | **0.0000** | 0.437 | **an existing `/GNSS_RX` 0.600/0.300 through via sits exactly on the site** — the outboard rank is occupied, literally |
| (56.000, 55.775) | 23 | **0.1157** | 0.437 | `/RF_GPIO2` In2 track 0.116, `/RF_GPIO2` through via 0.130 |
| (56.725, 55.775) | 24 (rank 1) | **0.0000** | 0.437 | `/RF_GPIO0` through via on the site, plus its In1 tracks |
| (56.400, 56.380) | 24 (rank 2) | **0.0000** | 0.437 | `/RF_GPIO2` In2, `/1V1` In4, pad C40.1 on F.Cu |
| (58.800, 55.775) | 30 | **0.0000** | 0.437 | `/RF_GPIO2` B.Cu 0.000, `/RF_MISO` In3 0.040, `/3V3` through via 0.136 |

Every design position is occupied by **other nets' through vias and inner-layer tracks**, and
the hole-to-hole rule rejects **five of those six** outright as well (0.4008, 0.0901, 0.4750,
0.2500, 0.4366 against 0.500). Two independent measuments say this is not a local patch problem:

**Density of a legal 0.6 site** (`s7_density.py`; worst-layer headroom ≥ 0.125 + 0.300, holes
and edge excluded):

| window | cells | 0.6 mm | 0.5 mm | 0.4 mm | best worst-layer headroom |
|---|---|---|---|---|---|
| U10 corner 51.0–61.0 × 50.5–58.8 (10 × 8.3 mm) | 33 200 @ 0.05 | **0 (0.000 %)** | 1 (0.003 %) | 21 (0.063 %) | **0.375** |
| same, 0.025 raster | 132 800 | **0 (0.000 %)** | — | — | **0.3998** |
| whole board 140 × 100 | 5 600 000 @ 0.05 | **3 621 424 (64.668 %)** | 66.434 % | 68.578 % | 18.325 |

**The board is not short of 0.6 via room — the corner is.** 64.7 % of the board takes a
0.6/0.3 through via today; in the U10 corner, zero cells do, and the best of 132,800 misses
by **0.010 mm** (0.3998 raster / 0.415 exact, against 0.425). The cap at that best cell,
measured on all six layers, is `/3V3` at 0.415 — a through-via stack.

**The pads are not the cap, either.** With every other net's tracks and vias removed and only
pads left (`s3_ceiling2.py`, outward half-plane, so the flood fill cannot slip under the body
and report a site on the far side), each target has thousands of legal 0.6 sites:

| pad | as-is lane mm² | as-is 0.6 / 0.5 / 0.4 sites | ceiling lane mm² | ceiling 0.6 sites |
|---|---|---|---|---|
| 16 | 0.0846 | 0 / 0 / 0 | 5.7688 | **26 158** |
| 19 | 0.0826 | 0 / 0 / 0 | 6.8863 | **40 809** |
| 23 | 0.0869 | 0 / 0 / 0 | 4.6798 | **14 212** |
| 24 | 0.0838 | 0 / 0 / 0 | 4.9823 | **16 125** |
| 30 | 0.2272 | 0 / 0 / 0 | 3.7779 | **9 782** |

So the earlier reading — *the pad pitch is the cap, no escape pattern can help* — is half
right and half backwards. The pitch does forbid a via **between** pads (0.200 gap against
0.850 of disc), but the pads do not forbid a via **outboard**. What forbids it is the track
and via population on the inner layers, which is a real route, not a constraint of the part.
**The escape pattern is not the free variable; the stack-up and the fanout are.**

## 2. STEP 2 — per-pad outcome

| pad | net | before (lane mm², 0.6 sites) | designed rank-1 site | nearest legal 0.6 site anywhere in the window | nearest legal 0.4 site | outcome |
|---|---|---|---|---|---|---|
| **5** | /3V3 | closed, 1.0063 | — | none | 6.751 | **stays closed** — not in the unconnected list (checked in the DRC, §5) |
| 16 | /RF_SCLK | 0.2262, 0/0/0 | headroom 0.1000 | **none** | 3.004 mm, 41 corridor objects | **not closable** |
| 19 | /RF_nCS | 0.1750, 0/0/0 | headroom 0.0000 (a `/GNSS_RX` via is on it) | **none** | 2.385 mm, 33 corridor objects | **not closable** |
| 23 | /RF_GPIO3 | 0.9693, 0/0/0 | headroom 0.1157 | **none** | **0.801 mm**, 0.3486 headroom, 2 corridor objects | closable **only** at 0.4/0.2, and only if 24 does not take the pocket |
| 24 | /3V3 | 0.9520, 0/0/0 | headroom 0.0000 | **none** | **0.751 mm**, 0.3373 headroom, 1 corridor object | same pocket as 23 — one slot, not two |
| 30 | /RP2354B MCU/XIN | 0.3841, 0/0/0 | headroom 0.0000 | **none** | 2.559 mm, 31 corridor objects | **not closable** |

"Nearest legal 0.6 site anywhere in the window" is the hard result: for all five pads,
**no** cell in 10 × 8.3 mm qualifies. The nearest legal **0.5** site is 2.665–7.362 mm away
and all five pads' nearest one is the *same* far pocket at (51.785, 54.805), which is a good
sanity check that the search is not pad-local.

## 3. STEP 3 — the re-fan cost, in nets, measured

The collateral is 280 objects on 44 nets. What matters is not how many objects come out but
**how many nets have to be re-laid before a 0.6 site exists near each pad**. `s9_unlock.py`
computes, exactly, the worst-layer headroom with a chosen net's copper removed (two-smallest
values per cell, so it is not an approximation), then repeats greedily.

| step | net removed | legal 0.6 cells | nearest 0.6 site: 16 / 19 / 23 / 24 / 30 (mm) |
|---|---|---|---|
| 0 | — | **0** | none / none / none / none / none |
| 1 | `/3V3` | 223 | 3.307 / 2.567 / 4.226 / 4.625 / 7.021 |
| 2 | `/VREG_AVDD` | 707 | 2.163 / 2.357 / 4.179 / 4.575 / 6.962 |
| 3 | `/GNSS_RX` | 1 601 | 2.163 / 2.288 / 4.179 / 4.575 / 6.962 |
| 4 | `/LSM_INT1` | 2 159 | 2.163 / 2.288 / 4.179 / 4.575 / 6.962 |
| 5 | `/CAN_INT` | 3 059 | 2.163 / 2.288 / 4.179 / 4.575 / 6.962 |
| 6 | `/RP2354B MCU/USB_DM_MCU` | 4 194 | **1.493** / 2.288 / 4.179 / 4.575 / 6.891 |
| 7 | `/ICM_INT2` | 4 993 | 1.493 / 2.288 / 4.088 / 4.488 / 6.832 |
| 8 | `/GND` | 5 545 | 1.493 / 2.138 / 4.034 / 4.411 / 6.732 |
| 9 | `/ICM_INT1` | 6 613 | 1.493 / **1.971** / **3.788** / **4.188** / 6.588 |
| 10 | `/LSM_nCS` | 8 774 | **0.811** / 1.728 / 3.238 / 3.638 / **4.277** |
| 11 | `/SENS_MOSI` | 13 630 | 0.811 / **0.946** / 3.025 / 3.400 / 4.277 |
| 12 | `/ICM_nCS` | 15 411 | 0.811 / 0.946 / 3.025 / 3.400 / 4.277 |
| 13 | `/3V3_ADC` | 17 092 | 0.811 / 0.946 / 3.025 / 3.400 / 4.277 |
| 14 | `/LSM_INT2` | 21 178 | 0.811 / 0.946 / 3.025 / 3.400 / 4.277 |
| 15 | `/1V1` | 22 694 | 0.811 / 0.946 / 3.025 / 3.400 / **1.707** |
| 16 | `/RF_RESET_N` | 24 022 | 0.811 / **0.783** / 2.589 / 2.982 / 1.707 |
| 17 | `/RP2354B MCU/RUN` | 26 609 | 0.811 / 0.783 / 2.589 / 2.982 / 1.707 |
| 18 | `/RF_nCS` | 29 089 | 0.811 / **0.338** / 2.492 / 2.846 / 1.707 |
| 19 | `/RF_GPIO3` | 31 071 | 0.811 / 0.338 / 1.980 / 2.369 / 1.707 |
| 20 | `/RP2354B MCU/MAIN_LED_A` | 33 316 | 0.811 / 0.338 / **0.830** / **0.799** / 1.707 |

Read the last column as the **upper bound of the re-fan**, and read it strictly: it is the
state after *deleting* that many whole nets' copper from the corner, not re-laying it. Twenty
nets — nearly half of the 44-net ring — buys 16, 19, 23 and 24 a site inside 0.85 mm and still
leaves **pad 30 with nothing closer than 1.707 mm**. A real re-fan has to put every one of
those nets back somewhere in the same window, so the true cost is higher and the true benefit
lower than this bound. That is why the 233-track / 47-via collateral is not the price of the
fix: **it is the price of a fix that still does not close pad 30, and does so only by emptying
half the ring.**

## 4. STEP 4 — the 23/24 shared pocket: the decision from geometry

Both options on the table are rejected by measurement, and the third point is the one that
decides it.

1. **Sequence them through the same via — impossible.** Pad 23 is `/RF_GPIO3` and pad 24 is
   `/3V3`. One via cannot carry two nets. Not a close call: different net codes.
2. **Give them different ranks — arithmetically possible, geometrically unsupported.** Two
   0.4/0.2 vias need **0.525 mm** centre distance (0.200 + 0.200 + 0.125). The pocket is one
   slot: at 0.005 raster over 55.0–58.2 × 53.2–55.2 there are **156 legal 0.4/0.2 cells, all
   in one blob**, and among the 60 nearest to each pad **there is no pair ≥ 0.525 apart** — the
   0.4/0.2 result for the two pads is `pairs >= 0.525 apart: 0`. Their own best cells are
   0.010 mm apart ((56.295, 54.205) and (56.305, 54.205)); the prior wave's two sites were
   0.150 apart against 0.525 and shorted 7 ways. Widening the window to 53.0–61.0 × 51.8–56.2
   produces 20 pairs that clear 0.525, and **every one of them has 34 corridor objects,
   including 4 crossings of other U10 pads** — corridors that no rip can legalise.
3. **The deciding measurement: pad 24 has no second family at all.** In a 55 440-cell window
   directly outboard of pad 24 (55.0–58.6 × 55.35–56.9) there are **0 legal 0.4/0.2 cells**
   (best headroom 0.2113 against 0.325), and 0 at 0.5 and 0.6. So 24's only via family is the
   inboard pocket — the same pocket as 23. **The pocket can serve exactly one of the two, and
   the choice between them is not geometric** (24's corridor costs 1 object and 0.751 mm,
   23's costs 2 and 0.801 mm; both sites are legal on copper at 0.3387 / 0.3373 against the
   0.337 raster demand). Any assignment is a design trade — one signal pad against one power
   pad — and it is the owner's, not this task's.

## 5. STEP 5 — batches, kept/attempted, set diff

| # | batch | what was done | exact verify | unconnected | DRC | outcome |
|---|---|---|---|---|---|---|
| A | pad 24 → pocket, 0.4/0.2 | 1 track 0.751 mm F.Cu `(56.400,54.950)→(56.305,54.205)`, 1 via 0.400/0.200, 0 objects ripped | **0 clearance violations, hole-to-hole OK, edge OK** (`work/b1.kicad_pcb.editlog.json`, `report` block) | 8 → **8** | 33 → **34**: **+1 `via_diameter`**, 0 new types, 0 `shorting_items`, 0 `clearance`, 0 `hole_to_hole` | **REJECTED, rolled back** |
| B | 23 + 24 paired | not attempted — **0 legal pairs exist** (§4, measured) | — | — | — | nothing to gate |
| C | 16, 19, 30 at 0.6/0.5/0.4 | not attempted — **0 legal sites exist** in the whole corner at 0.6 (§1.1); nearest at 0.4 is 2.4–3.0 mm with 31–41 corridor objects | — | — | — | nothing to gate |

Batch A is the interesting failure and it fails in the specific way the rule exists for. The
copper was clean: 0.751 mm of F.Cu track and a 0.400/0.200 via that passed an exact shapely
check on all six layers at the board's own 0.125 clearance, with hole-to-hole and edge clear.
It still did not close the pad. The DRC's unconnected line **moved** rather than closed:

    before: Pad 24 [/3V3] of U10  <->  Track [/3V3] on F.Cu, length 0.6000 mm
    after:  Track [/3V3] on F.Cu, length 0.6000 mm  <->  Track [/3V3] on F.Cu, length 0.7510 mm

i.e. the via landed in an **In1 `/3V3` zone fragment that is not the ratsnest partner's
island** — the pad now reaches a pour that goes nowhere, which is the electrical version of a
stub. So the batch closed nothing, added one `via_diameter` (the board's `via_min_size` is
0.600; 0.400 is a rule change and therefore an owner decision, not this task's to take), and
was rolled back under the stated rule: *a batch that closes 0 and opens 1 is a failure.*
`work/b1.kicad_pcb` is kept as the artefact of the rejected attempt, not as a deliverable.

**Kept / attempted: 0 of 5 pads closed by this pass, 1 batch attempted, 1 rolled back, 0 of
the 233 collateral tracks and 0 of the 47 vias re-routed** — because no batch reached the
point of needing a re-lay: the blocker was upstream of the re-lay.

## 6. STEP 6 — whole-board verification, and why no package was regenerated

Reference board `work/b0.kicad_pcb` (= the input, unchanged — this pass wrote only copies):

| invariant | required | measured | verdict |
|---|---|---|---|
| span census | 0 non-through | **343 vias, all `THROUGH F.Cu → B.Cu`, `non_through_by_span` 0** | **PASS** |
| min drill | ≥ 0.200 | **0.200** | **PASS** |
| unconnected, kicad-cli | — | **8** | unchanged |
| unconnected, pcbnew | — | **8** | both tools agree |
| DRC set diff vs baseline | no new types | **33 → 33**, identical type histogram (26 / 5 / 2) | **PASS** |
| RF void | bit-identical | **4.1699 mm² = 9.8338 %**, void_B 3.8754 = 9.1392 % | **PASS** |
| pad 5 | stays closed | **not in the 8 unconnected pairs** | **PASS** |

The rejected batch A was verified on its own copy before rollback, and the invariants held
there too (`work/span_b1.json`): **344 vias, 0 non-through, min drill 0.200, void 4.1699 /
9.8338** — so the failure was electrical, not geometric.

Remaining 8 unconnected (unchanged from the input, listed to show nothing moved):
U10 pads **16, 19, 23, 24, 30**; `/GNSS_RESET_N` cross-layer join; `/RF_GPIO0` cross-layer
join; the `/GND` F.Cu zone-fill split.

**The package was not regenerated, and that is the correct outcome, not an omission.** The
brief's precondition is 0 unconnected **and** 0 non-through **and** a clean set diff; here it
is 8 / 0 / clean-but-no-closure. Rebuilding 20 Gerbers, a drill pair, a POS and 36 assertions
off a board that still has 8 opens would ship a package whose V30/V31 assertions fail, which
is exactly the "manufactured pass" to avoid. The census arithmetic the regeneration would
have to satisfy was nevertheless **independently re-verified** on `b0` and it agrees with the
corrected figure: **`total_holes` 371 = 367 drills (343 via drills + 18 round PTH pads = 361
PTH, + 6 NPTH) + 4 G85 slots** (`slot_pads_total` 4, all J1.S1 oblong 0.6 × 1.4/1.7), and
**POS 161 rows** = 165 footprints − H1–H4. The "371 drills + 4 slots = 375" form is a double
count of the four slotted J1 pads; the "361 + 4 = 371" form drops the six NPTH drills.

## 7. Verdict

**IS DRONE-ARM SENDABLE TO A FAB? — NO.**

What this pass establishes, with numbers:

1. **The two-rank ring was designed to the brief's own terms** — rank 1 at `d1 = 0.825` mm
   (0.400 pad half length + 0.300 via radius + 0.125 clearance) with a 90° exit and 0.200
   track; rank 2 at `d2 ≥ d1 + 0.407` with the same track and exit; rank-1 vias on every
   third pad (1.200 pitch, because a 0.200 track needs 1.050 between two 0.6 vias) and the
   rank-2 lane on the 0.600 lateral stagger. It closes 2 pads of every 3 by construction.
2. **It cannot work on this board, and the reason is one layer below the diagnosis.** The
   corner has **0 of 132 800 cells** able to host a 0.6/0.3 through via under the board's own
   0.125 clearance; the best cell misses by **0.010 mm**, capped by a `/3V3` through-via stack
   0.415 away, on all six layers. The whole rest of the board is fine — **64.668 %** of it
   accepts that via. And with only pads left as obstacles, the five pads have 9 782–40 809
   legal 0.6 sites each: **the pads were never the cap; the inner-layer field is.**
3. **Three pads are not closable at any class, and one pair is not closable at any class.**
   Pads 16, 19, 30 have no legal 0.6 site within 3 mm (nearest 0.4 sites 2.385 / 2.559 /
   3.004 mm away behind 31–41 corridor objects). Pads 23/24 share **one** via slot: 156 legal
   0.4 cells in a single blob with **no pair ≥ 0.525 apart**, and pad 24 has **0** legal 0.4
   cells in a 55 440-cell outboard window, so different ranks have nothing to stand on and
   the shared-via option is impossible across two nets.
4. **The collateral is not the obstacle; it is beside the point.** Deleting **20 of the 44
   ring nets'** copper from the corner — the upper bound of any re-fan, and copper that a real
   re-fan must put back — brings 16, 19, 23 and 24 to a 0.6 site inside 0.85 mm and still
   leaves pad 30 at **1.707 mm**. Spending the 233 tracks and 47 vias therefore buys the
   *opportunity* to re-open four lanes by emptying half the ring, and never reaches the fifth.
5. **What would actually move the answer**, in cost order: (a) the owner declaring a 0.4/0.2
   via class for the U10 breakout — it makes pad 23 *or* 24 closable (never both) and would
   also retire the 5 existing `via_diameter` errors, but leaves 16/19/30 and the pair
   unresolved, so it does not make the board sendable; (b) a fanout/stack-up change at U10
   (laser-via HDI or a finer annular) that puts the escape on a different layer pair — the
   only option on this list that addresses 3 of the 5 pads at once.

Deliverables: `work/b0.kicad_pcb` (the verified reference board, unchanged from input, sha256
`21C000EF…A4223`), `work/b1.kicad_pcb` (**rejected** batch A, kept for the audit trail),
`drc/drc_b0.json`, `drc/drc_b1.json`, `work/span_b0.json`, `work/span_b1.json`, the
measurement JSONs `s1_geo.json`, `s2_ceiling.json`, `s3_ceiling2.json`, `s5_rank1.json`,
`s6_ladder.json`, `s7_density.json`, `s8b_binders.json`, `s9_unlock20.json`,
`s10_pair.json`, `s11_wide.json`, and logs in `work/*.log`.

## A. Appendix — instruments (all in `work/`, run with the KiCad 9.0.7 bundled python)

`s1_geo.py` U10 pad-array geometry + per-target local-copper census · `s2_ceiling.py` first
as-is/ceiling attempt (unrestricted lane; **superseded**, kept because it is the one that
exposed the under-body flood-fill artefact) · `s3_ceiling2.py` as-is vs ceiling with the
outward half-plane, which is the comparable measurement · `s5_sites.py` exact obstruction
report per designed via site and corridor · `s6_ladder.py` nearest legal site per pad per via
class · `s7_density.py` board-wide vs corner via-class density · `s8b_binders.py`
single-net-removal unlock (correct per-(net,layer) construction) · `s9_unlock.py` greedy
unlock curve with the per-pad nearest site · `s10_pair.py`/`s11_wide.py` sequenced-pair search
for 23/24 · `s12_apply.py` verify-then-apply with an exact clearance/hole/edge gate that
refuses to write on failure · `geo.py`, `router.py`, `span_census7.py`, `s5_void.py`,
`c8_ring.py` the programme's own board-truth instruments, reused unmodified.

One instrument defect was found and fixed mid-task and is worth recording because it changes
numbers: the first density run read **clearance 0** because the board's `.kicad_pro` was not
beside the `.kicad_pcb`; every raster number in this report comes from the re-run with the
companion present and the rules printing `0.125 / 0.6 / 0.2 / 0.2`.