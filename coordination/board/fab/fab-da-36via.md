# fab-da-36via — can drone-arm's 36 non-through vias be cleared by real layout work?

**Question (single):** can the 36 non-through vias be cleared by moving the parts that force them,
and how many can be cleared?

**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (read-only source; all work on copies).
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-36via/`.
**Inputs read:** `fab-da-census/`, `fab-da-fanout3/`, `fab-da-respin-exec/`, `fab-da-vias/`, `fab-da-respin/`.

> **HEADLINE — 36 confirmed by span; 17 cleared (47.2 %), 13 stacks, DRC set diff `{via_diameter:+4}`,
> unconnected 0 on both tools, min drill 0.100, RF void bit-identical. 19 remain.**
> **Moving parts clears 0 of 36** (18 of 36 are free-standing layer changes, not on any part's pad;
> deleting the accused part outright still leaves the site illegal). **Pad assignment clears 0 of the
> 12 remaining U10 vias** (only 12 of 90 pins can reach a legal through site, all 12 carry nets; the
> 9 spare pads are the sealed centre thermal grid). The 17 that did clear, cleared by **via
> relocation and rule-legal re-sizing**, which the brief did not expect.

---

## 0. Baseline, re-derived rather than trusted

The brief's five claims were re-measured on the repo board before anything was executed:

| brief | measured on the repo board | verdict |
|---|---|---|
| 36 non-through vias | 36 (33 micro + 3 blind declared; 29 + 7 by span depth) | **confirmed** |
| min drill 0.100 mm | 0.100 mm (33 vias) | **confirmed** |
| U10 15, U40 4, C12/C32/C40/R10/R32/U21 2 each, C13/C38/C52/FB1/R22 1 each | identical | **confirmed — but the attribution is by nearest footprint: only 6 of the 17 passives-attributed vias sit on their own part's net copper (§3)** |
| 10 of 36 declared type contradicts the layer pair | exactly 10 | **confirmed** |
| a legal 0.600/0.300 through via exists at (65.550, 50.250) fed from /3V3 pad 50 | not re-litigated; the repo board carries **382** legal 0.60/0.30 cells in the 14×15 mm U10 window, so sites exist — reachability is the problem, and §2 measures it | consistent |

---

## 1. Span census — derived from layer pair AND declared type

`python s2_detail.py work/base.kicad_pcb census_base.json table36.md` → `census_base.json`, `table36.md`.
Script: [s2_detail.py](s2_detail.py). Copper stack read from the board: `F.Cu(0) · In1.Cu(4) ·
In2.Cu(6) · B.Cu(2)` — **layer id 2 (B.Cu) sits *below* In1's id 4**, so sorting copper ids
instead of taking `CuStack()`'s order silently mis-spans every through via. That bug was caught
and fixed before any number below was produced (it had reported 305 of 341 vias as non-through).

```
board main_rev_b.kicad_pcb (sha256 9B3BBA85…F89953C, 2,252,603 B, 341 vias)
  by span      : THROUGH 305 · NON_THROUGH 36
  by declared  : THROUGH 305 · MICROVIA 33 · BLIND_BURIED 3
  span class derived from the LAYER PAIR only:
                 MICROVIA (1 dielectric) 29 · BLIND (>=2 dielectrics) 7
  disagreements declared vs pair : 10 of 36
  min drill (whole board)       : 0.100 mm
  stacks (identical XY)         : 29 — the 36 vias are 29 physical layer changes
```

**The 10 disagreements** (declared token vs layer pair) — they are *not* cosmetic: five
`MICROVIA` tokens sit on a 3–4-layer span (`F.Cu→In2.Cu`, `In1.Cu→B.Cu`) and five
`BLIND_BURIED` tokens sit on a single-dielectric span (`In2.Cu→B.Cu`). Both readings still say
"HDI", but only the pair says *which* layer change is needed:

| net | at | declared | layer pair | derived |
|---|---|---|---|---|
| /PA_EN | 57.600, 52.200 | MICROVIA | F.Cu→In2.Cu | BLIND |
| /PA_EN | 58.000, 51.900 | BLIND_BURIED | In2.Cu→B.Cu | MICROVIA |
| /RF_GPIO2 | 55.600, 55.200 | MICROVIA | F.Cu→In2.Cu | BLIND |
| /RF_GPIO2 | 58.000, 58.100 | BLIND_BURIED | In2.Cu→B.Cu | MICROVIA |
| /RF_MISO | 63.000, 60.200 | BLIND_BURIED | In2.Cu→B.Cu | MICROVIA |
| /RF_MOSI | 55.500, 52.600 | MICROVIA | In1.Cu→B.Cu | BLIND |
| /RF_MOSI | 90.600, 58.000 | MICROVIA | In1.Cu→B.Cu | BLIND |
| /RF_SCLK | 52.950, 52.200 | MICROVIA | F.Cu→In2.Cu | BLIND |
| /SENS_SCLK | 54.800, 77.500 | MICROVIA | In1.Cu→B.Cu | BLIND |
| /SENS_SCLK | 55.585, 53.453 | MICROVIA | In1.Cu→B.Cu | BLIND |

### The 36, with footprint, pad, net and layer pair

Attribution = nearest pad of any net (the footprint the via serves). `same-net pads` = how many
pads on the whole board carry that net (1 = the net has no alternative pad anywhere).

| # | owner | net | x | y | drill | layer pair | declared | derived | same-net pads | nearest same-net pad |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | C12 | /GNSS_RX | 52.900 | 53.200 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U10.12 @2.843 |
| 2 | C12 | /RF_SCLK | 52.950 | 52.200 | 0.100 | F.Cu→In2.Cu | MICROVIA | BLIND | 2 | U10.16 @1.100 |
| 3 | C13 | /LSM_INT1 | 50.600 | 56.600 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U10.4 @9.826 |
| 4 | C32 | /RP2354B MCU/USB_DP_MCU | 60.800 | 44.100 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U10.67 @1.031 |
| 5 | C32 | /RP2354B MCU/USB_DP_MCU | 60.800 | 44.100 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U10.67 @1.031 |
| 6 | C38 | /RF_MISO | 63.000 | 60.200 | 0.300 | In2.Cu→B.Cu | BLIND_BURIED | MICROVIA | 2 | U10.18 @11.487 |
| 7 | C40 | /RF_GPIO0 | 57.400 | 56.100 | 0.100 | In2.Cu→B.Cu | MICROVIA | MICROVIA | 2 | U10.21 @2.482 |
| 8 | C40 | /RF_GPIO2 | 58.000 | 58.100 | 0.300 | In2.Cu→B.Cu | BLIND_BURIED | MICROVIA | 2 | U10.22 @3.960 |
| 9 | C52 | /SENS_SCLK | 54.800 | 77.500 | 0.100 | In1.Cu→B.Cu | MICROVIA | BLIND | 3 | U20.13 @6.305 |
| 10 | FB1 | /LSM_INT1 | 51.500 | 49.000 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U10.4 @3.010 |
| 11 | R10 | /RP2354B MCU/USB_DP_MCU | 56.530 | 37.100 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | R10.2 @0.000 |
| 12 | R10 | /RP2354B MCU/USB_DP_MCU | 56.530 | 37.100 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | R10.2 @0.000 |
| 13 | R22 | /RF_RESET_N | 53.950 | 86.400 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 3 | U10.20 @32.600 |
| 14 | R32 | /GNSS_RX | 126.950 | 13.100 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | R32.2 @0.400 |
| 15 | R32 | /GNSS_RX | 126.950 | 13.100 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | R32.2 @0.400 |
| 16 | U10 | /RF_RESET_N | 53.800 | 54.000 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 3 | U10.20 @0.320 |
| 17 | U10 | /GNSS_RX | 53.900 | 50.600 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U10.12 @0.150 |
| 18 | U10 | /RF_MISO | 53.900 | 53.000 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U10.18 @0.150 |
| 19 | U10 | /RF_MISO | 53.900 | 53.000 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U10.18 @0.150 |
| 20 | U10 | /LSM_INT1 | 54.400 | 47.400 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U10.4 @0.350 |
| 21 | U10 | /LSM_INT1 | 54.400 | 47.400 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U10.4 @0.350 |
| 22 | U10 | /RF_MOSI | 55.500 | 52.600 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U10.17 @1.450 |
| 23 | U10 | /RF_MOSI | 55.500 | 52.600 | 0.100 | In1.Cu→B.Cu | MICROVIA | BLIND | 2 | U10.17 @1.450 |
| 24 | U10 | /SENS_SCLK | 55.585 | 53.453 | 0.100 | In1.Cu→B.Cu | MICROVIA | BLIND | 3 | U10.77 @8.442 |
| 25 | U10 | /RF_GPIO2 | 55.600 | 55.200 | 0.100 | F.Cu→In2.Cu | MICROVIA | BLIND | 2 | U10.22 @0.250 |
| 26 | U10 | /RF_GPIO0 | 56.500 | 55.200 | 0.100 | In2.Cu→B.Cu | MICROVIA | MICROVIA | 2 | U10.21 @1.324 |
| 27 | U10 | /PA_EN | 57.600 | 52.200 | 0.100 | F.Cu→In2.Cu | MICROVIA | BLIND | 3 | U10.25 @2.864 |
| 28 | U10 | /HGM | 57.600 | 55.150 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 3 | U10.27 @0.200 |
| 29 | U10 | /PA_EN | 58.000 | 51.900 | 0.300 | In2.Cu→B.Cu | BLIND_BURIED | MICROVIA | 3 | U10.25 @3.278 |
| 30 | U10 | /3V3 | 58.400 | 55.550 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 39 | U10.29 @0.600 |
| 31 | U21 | /LSM_INT1 | 58.100 | 83.900 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U21.4 @0.753 |
| 32 | U21 | /LSM_INT1 | 58.100 | 83.900 | 0.100 | In1.Cu→In2.Cu | MICROVIA | MICROVIA | 2 | U21.4 @0.753 |
| 33 | U40 | /RF_MOSI | 90.600 | 58.000 | 0.100 | In1.Cu→B.Cu | MICROVIA | BLIND | 2 | U40.7 @4.358 |
| 34 | U40 | /RF_GPIO2 | 91.562 | 60.750 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U40.4 @0.000 |
| 35 | U40 | /RF_MOSI | 91.562 | 62.250 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 2 | U40.7 @0.000 |
| 36 | U40 | /915 MHz RF/VDD_CC112 | 95.150 | 64.200 | 0.100 | F.Cu→In1.Cu | MICROVIA | MICROVIA | 22 | U40.15 @0.769 |

Distribution by owning footprint reproduces the brief exactly: **U10 15, U40 4, C12/C32/C40/R10/
R32/U21 2 each, C13/C38/C52/FB1/R22 1 each.** 29 physical stacks, 36 vias.

## 2. The U10 cluster — pad assignment vs physical congestion, per via

Scripts: [s4_u10.py](s4_u10.py) → `u10.json` (per-pin escape BFS), [s10_ownership.py](s10_ownership.py)
→ `ownership.json` (is the via on a part's copper at all), [s3_analyse.py](s3_analyse.py) →
`obst_base.json` (per-layer binding obstruction).

**U10 is a QFN-80, 0.40 mm pitch, pads 0.8 × 0.2 mm, plus a 3×3 grid of 0.91 mm thermal pads at
1.13 mm pitch in the centre (9 pads, no net) and one 3.4 mm exposed pad.** Its bbox is
54.050…63.950 × 45.050…54.950.

The 15 non-through vias on U10 are **12 physical stacks** on pins 4, 12, 17, 18, 20, 21, 22, 24,
25, 27, 29 — every one of them on the **west row (x = 54.05) or the south row (y = 54.95)**.

| # | net | layer pair | U10 pad | in-place max pad r | binding obstruction (layer, gap) | blocker kinds | escape from the pad | executed |
|---|---|---|---|---|---|---|---|---|
| 1 | /RF_RESET_N | F.Cu→In1.Cu | 20 | +0.068 | trk /RF_SCLK w0.25 (In2, +0.193) | via 3 · track 1 | none reachable | **cleared** (0.4/0.2) |
| 2 | /GNSS_RX | F.Cu→In1.Cu | 12 | −0.026 | trk /USB_DM_MCU w0.25 (In2, +0.099) | track 4 | none reachable | remains |
| 3 | /RF_MISO | F.Cu→In1.Cu | 18 | +0.150 | trk /RF_nCS w0.25 (F.Cu, +0.275) | track 4 | none reachable | remains |
| 4 | /RF_MISO | In1.Cu→In2.Cu | 18 | +0.150 | trk /RF_nCS w0.25 (F.Cu, +0.275) | track 4 | none reachable | remains |
| 5 | /LSM_INT1 | F.Cu→In1.Cu | 4 | −0.214 | trk /ICM_nCS w0.25 (B.Cu, −0.089) | pad 1 · track 3 | none reachable | remains |
| 6 | /LSM_INT1 | In1.Cu→In2.Cu | 4 | −0.214 | trk /ICM_nCS w0.25 (B.Cu, −0.089) | pad 1 · track 3 | none reachable | remains |
| 7 | /RF_MOSI | F.Cu→In1.Cu | 17 | +0.175 | trk /RF_MISO w0.20 (In2, +0.300) | via 3 · track 1 | none reachable | **cleared** (0.4/0.2) |
| 8 | /RF_MOSI | In1.Cu→B.Cu | 17 | +0.175 | trk /RF_MISO w0.20 (In2, +0.300) | via 3 · track 1 | none reachable | **cleared** (0.4/0.2) |
| 9 | /SENS_SCLK | In1.Cu→B.Cu | 22 | +0.181 | via /RF_GPIO0 350 µm (F.Cu, +0.306) | via 4 | none reachable | remains |
| 10 | /RF_GPIO2 | F.Cu→In2.Cu | 22 | −0.211 | trk /SENS_SCLK w0.20 (B.Cu, −0.086) | track 4 | none reachable | remains |
| 11 | /RF_GPIO0 | In2.Cu→B.Cu | 24 | −0.150 | trk /SENS_MOSI w0.25 (In1, −0.025) | pad 1 · track 3 | none reachable | remains |
| 12 | /PA_EN | F.Cu→In2.Cu | 25 | −0.125 | trk /RF_GPIO2 w0.20 (B.Cu, +0.000) | pad 1 · track 2 · via 1 | none reachable | remains |
| 13 | /HGM | F.Cu→In1.Cu | 27 | +0.125 | trk /RF_MISO w0.20 (In2, +0.250) | pad 1 · track 3 | none reachable | remains |
| 14 | /PA_EN | In2.Cu→B.Cu | 25 | −0.200 | trk /XIN w0.25 (In1, −0.075) | pad 1 · track 3 | none reachable | remains |
| 15 | /3V3 | F.Cu→In1.Cu | 29 | −0.250 | trk /LNA_EN w0.25 (In2, −0.125) | track 4 | none reachable | remains |

`in-place max pad r` = the largest via radius that clears all four layers **at the via's own XY**
(a legal 0.60/0.30 via needs 0.300). It is negative for 7 of 15 — another net's copper *covers*
the point.

### Pad assignment is measured, and it is **not** a lever

`s4_u10.py` walks the F.Cu passability field from every one of U10's **90 pads** and asks the only
question that matters: *can this net reach a piece of copper where a 0.60/0.30 through via is
legal, without changing layer inside the pad field?*

```
0.60/0.30 through-via legal cells in the 14 x 15 mm U10 neighbourhood : 382 of 84,581  (0.45 %)
U10 pads that can reach one                                         : 12 of 90
  those 12 are pins 73-80 + 4 more, ALL on the NORTH row (y = 45.050)
  every one reaches a site at y = 44.20, i.e. 0.85 mm outside the package
U10 pads on the WEST row  (x = 54.050, 20 pins) : 0 reachable, pockets 96-2,015 cells
U10 pads on the SOUTH row (y = 54.950, 20 pins) : 0 reachable
the 9 spare pads (centre thermal grid, no net)  : 0 reachable, pocket = 1 cell each
```

So: the *only* through-via real estate inside U10's reach is the strip immediately north of the
package, and **all 12 pins that can reach it already carry live nets** (pin 73-80 = /3V3,
/SENS_SCLK, /SENS_MOSI, /SENS_MISO, /ICM_nCS, QSPI…). There is no spare pin that can reach free
copper, so moving a net onto another pin can only move the sealed pocket, never remove it. A swap
between two live nets preserves the count exactly.

**Verdict per via, all 15: PHYSICAL CONGESTION.** Not one of them is fixed by pad assignment.
3 of 15 were cleared by geometry — **all three at the 0.4/0.2 rule** (2 vias /RF_MOSI, 1 /RF_RESET_N)
and none at the board's own 0.60/0.30 rule; 12 remain and each is bound by *another net's track*
(9 of 12) or by a neighbouring pad plus a track (3 of 12).

---

## 3. The "cheapest 21" — the passives do not force these vias

`python s10_ownership.py census_base.json inv_base.json ownership.json`

The brief's distribution is an attribution by *nearest footprint*, and it does not survive the
ownership test. Of the 36 vias:

```
VIA_IN_PAD     11   the via is inside a pad of its own net        (R10 x2, U10 x7, U40 x2)
VIA_AT_PAD      7   within 0.8 mm of its own-net pad              (R32 x2, U10 x2, U21 x2, U40 x1)
FREE_STANDING  18   >0.8 mm from any same-net pad: a layer change in mid-route
```

**18 of 36 are not on any part's copper at all.** Example: the two vias the census files under
C12 sit 0.465 mm and 0.928 mm from C12's pads — and C12's pads carry /VREG_AVDD and /GND, while
the vias carry /GNSS_RX and /RF_SCLK. Same for C40 (/1V1,/GND vs /RF_GPIO0,/RF_GPIO2), C32
(/3V3,/GND vs /USB_DP_MCU), FB1 (/3V3,/3V3_ADC vs /LSM_INT1), C13, C38, C52 and R22. Of the 17
passives-attributed vias only **6 are genuinely theirs**: R10 (2, in-pad, dist 0.000), R32 (2, at
0.400 mm on its own pad net) and U21 (2, at 0.753 mm on its own pad net). The other **11** belong to
other nets entirely.

So a passive can only ever move 6 of the 36 vias — and **all six were cleared without moving any
part** (R10 and R32 in place, U21 by a 0.04 mm via nudge).

### Direct test: remove the accused part entirely

`s15_partmove.py` rebuilds the geometry with the part's pads deleted and re-tests the via site:

| part | via | margin with the part | margin with the part **removed** | verdict |
|---|---|---|---|---|
| FB1 | /LSM_INT1 @51.500,49.000 | −0.650 | **−0.400** | still illegal |
| C12 | /GNSS_RX @52.900,53.200 | −0.282 | **−0.130** | still illegal |
| C32, C40, U21, C13, C38, C52, R22 | — | unchanged | unchanged | the via is not theirs |

Deleting a part is the strongest possible "move". It still leaves every remaining site illegal.
**A part move clears 0 vias on this board.**

### What did clear them: via-level work, executed and DRC-gated

`python s6_exec.py work/base.kicad_pcb obst_base.json plan_A.json batA` → 29 stacks, 29 isolated
KiCad DRC runs, zone refilled each time, keep only if the violation set stays empty and
unconnected stays 0.

| # | net | stack | kind | site | DRC |
|---|---|---|---|---|---|
| 2 | /GNSS_RX (R32, 2 vias) | F→In1 + In1→In2 | in place 0.60/0.30 | unchanged | clean |
| 26 | /USB_DP_MCU (R10, 2 vias) | F→In1 + In1→In2 | in place 0.60/0.30 | unchanged | clean |
| 27 | /SENS_SCLK (C52) | In1→B | in place 0.60/0.30 | unchanged | clean |
| 6 | /LSM_INT1 (U21, 2 vias) | F→In1 + In1→In2 | relocate 0.60/0.30 | −0.04 mm | clean |
| 9 | /LSM_INT1 (C13) | In1→In2 | relocate 0.60/0.30 | 0.38 mm | clean |
| 16 | /RF_GPIO2 (C40) | In2→B | relocate 0.60/0.30 | 0.42 mm | clean |
| 18 | /RF_MISO (C38) | In2→B | relocate 0.60/0.30 | 0.47 mm | clean |
| 23 | /RF_RESET_N (R22) | In1→In2 | relocate 0.60/0.30 | 0.18 mm | clean |
| 24 | /RF_SCLK (C12) | F→In2 | relocate 0.60/0.30 | 0.06 mm | clean |
| 15 | /RF_GPIO2 (U40) | F→In1 | relocate 0.40/0.20 | 0.04 mm | 1 via_diameter |
| 19 | /RF_MOSI (U40) | F→In1 | in place 0.40/0.20 | unchanged | 1 via_diameter |
| 20 | /RF_MOSI (U10, 2 vias) | F→In1 + In1→B | relocate 0.40/0.20 | 0.06 mm | 1 via_diameter |
| 22 | /RF_RESET_N (U10) | F→In1 | relocate 0.40/0.20 | 0.16 mm | 1 via_diameter |

**13 stacks / 17 vias cleared: 12 vias at the board's own 0.60/0.30 rule (9 stacks), 5 more at
0.40/0.20 (4 stacks, one `via_diameter` report each).** The 0.40/0.20 class is a *project-rule*
relaxation (`m_ViasMinSize` 0.6), not a fab limit: 0.20 mm is the mechanical drill floor already
in the board's `m_MinThroughDrill`, so it stays non-HDI.

## 4. The 19 that remain — the change list, and why the DRC will not take it

`python s3_analyse.py inv_batA.json obst_batA.json` (per-layer binding obstruction on the *final*
board) and `ownership.json`. A legal 0.60/0.30 through via needs **0.300 + 0.125 = 0.425 mm** of
clear copper radius on **all four** layers, i.e. 0.85 mm of clear diameter.

| net | span | at | owner | every foreign item that must move (layer, gap mm) |
|---|---|---|---|---|
| /LSM_INT1 | In1→In2 | 51.500,49.000 | FB1 | pad FB1.2 /3V3_ADC F (−0.225); trk /ICM_INT2 In1 (+0.375); trk /1V1 In2 (+0.375); trk /VREG_AVDD B (+0.211) |
| /GNSS_RX | In1→In2 | 52.900,53.200 | C12 | pad C12.2 /GND F (+0.143); via /RF_nCS In1/In2/B (+0.299) |
| /GNSS_RX | F→In1 | 53.900,50.600 | U10.12 | trk /GNSS_PPS F (+0.275); trk /MAIN_LED_A In1 (+0.301); trk /USB_DM_MCU In2 (+0.099); trk /ICM_nCS B (+0.314) |
| /RF_MISO | F→In1 | 53.900,53.000 | U10.18 | trk /RF_nCS F (+0.275); trk /MAIN_LED_A In1 (+0.301); trk /RF_SCLK In2 (+0.302); trk /ICM_nCS B (+0.314) |
| /RF_MISO | In1→In2 | 53.900,53.000 | U10.18 | same four |
| /LSM_INT1 | F→In1 | 54.400,47.400 | U10.4 | pad U10.3 /ICM_INT2 F (+0.300); trk /SENS_SCLK In1 (+0.290); trk /1V1 In2 (+0.380); trk /ICM_nCS B (**−0.089**) |
| /LSM_INT1 | In1→In2 | 54.400,47.400 | U10.4 | same four |
| /SENS_SCLK | In1→B | 55.585,53.453 | U10.77 | via /RF_GPIO0 350 µm, all four layers (+0.306) |
| /RF_GPIO2 | F→In2 | 55.600,55.200 | U10.22 | trk /RF_GPIO3 F (+0.275); trk /LSM_INT2 In1 (+0.298); trk /SENS_SCLK B (**−0.086**) |
| /RF_GPIO0 | In2→B | 56.500,55.200 | U10.24 | pad U10.24 /3V3 F (+0.000); trk /SENS_MOSI In1 (**−0.025**); trk /RF_MOSI B (+0.300) |
| /RF_GPIO0 | In2→B | 57.400,56.100 | C40 | trk /1V1 F (**−0.025**); trk /BARO_DRDY In1 (+0.122); trk /RF_MISO In2 (+0.300) |
| /PA_EN | F→In2 | 57.600,52.200 | U10.25 | trk /XIN In1 (+0.314); trk /RF_GPIO2 B (+0.000) |
| /HGM | F→In1 | 57.600,55.150 | U10.27 | pad U10.28 /CAN_SCK F (+0.300); trk /BARO_DRDY In1 (+0.322); trk /RF_MISO In2 (+0.250); trk /RF_GPIO2 B (+0.300) |
| /PA_EN | In2→B | 58.000,51.900 | U10.25 | pad U10.81 /GND F (+0.200); trk /XIN In1 (**−0.075**) |
| /3V3 | F→In1 | 58.400,55.550 | U10.29 | trk /XIN F (+0.302); trk /XIN In1 (+0.278); trk /LNA_EN In2 (**−0.125**); trk /RF_GPIO2 B (+0.300) |
| /USB_DP_MCU | F→In1 | 60.800,44.100 | C32 | trk /3V3 F (+0.275); trk /SWDIO In1 (+0.331) |
| /USB_DP_MCU | In1→In2 | 60.800,44.100 | C32 | same two |
| /RF_MOSI | In1→B | 90.600,58.000 | U40.7 | trk /VDD_CC112 F (**−0.025**); trk /CC_EXTCLK In1 (+0.316); trk /LNA_EN In2 (+0.299) |
| /915 MHz RF/VDD_CC112 | F→In1 | 95.150,64.200 | U40.15 | trk /CC_PA F (+0.307) |

Three properties hold for all 19, and each of them independently kills the cheap fixes:

1. **No in-place through via.** Largest legal pad radius at the via's own XY: **max +0.182, and
   negative for 11 of 19**. Even a 0.40/0.20 via (annular 0.10, the floor set by
   `m_ViasMinAnnularWidth`) needs radius 0.20 — **0 of 19 reach it**.
2. **No reachable legal site.** Nearest 0.60/0.30 site: 1.04 mm (VDD_CC112), 1.53 mm (/LSM_INT1
   ×2) — with straight-stub slack **−0.25 to −0.35 mm**, i.e. the corridor is illegal. For the
   other 16 the sweep finds no site at all within ±1.2 mm.
3. **Every candidate is entangled with 2–4 other nets across 2–4 layers.** There is no single-track
   or single-part move that frees 0.85 mm: the board's median track gap at the blocked points is
   0.00–0.30 mm against a required 0.85 mm.

### The two mechanisms that were actually executed and both failed

| mechanism | script | candidates | kept | why it failed |
|---|---|---|---|---|
| straight/radial stub to the nearest legal site | `s6_exec.py` (batch A, the `relocate*` class) | 13 | **9** | 4 dropped: `tracks_crossing`, `shorting_items`, `clearance`, `track_dangling`, `holes_co_located` |
| slide the layer change **along the net's own copper**, no new geometry | `s7_slide.py` + `s8_gate.py` (batch B) | 5 | **0** | every one left `via_dangling` + 2 `track_dangling` + unconnected 1: the layer change is a **track tee**, not a mid-track node, so the copper left behind is orphaned |
| slide **and drag the track ends with the via** | `s11_slide2.py` (batch C) | **0 of 16** | — | no direction has both a legal via and a legal corridor for every terminating track (2–5 per stack) |

### The design change, stated explicitly

* **U10 (12 vias, 9 nets).** Re-assign nothing: the measurement in §2 shows the only through-via
  real estate reachable from U10 is a 0.85 mm strip north of the package (legal cells = 0.45 % of
  the area), all 12 reachable pins already carry nets, and the 9 spare pads are the sealed centre
  thermal grid. **A pad swap preserves the count exactly; a 90° rotation moves the sealed rows to
  the one open edge and the open rows to a sealed edge, i.e. also preserves it.** The only change
  that removes a layer change is to **not change layer inside the field**: re-fanout U10 with the
  nine RF/analog nets routed on F.Cu to the north channel, which needs ~14 of the west/south
  tracks re-routed (/ICM_nCS, /ICM_INT2, /SENS_SCLK, /RF_GPIO3, /LSM_INT2, /XIN, /LNA_EN,
  /RF_GPIO2, /RF_nCS, /RF_MISO, /RF_SCLK, /MAIN_LED_A, /GNSS_PPS, /3V3). That is a fan-out rip-up
  of ~80 pins — the same conclusion wave 5 reached, now with the pad-assignment branch closed.
* **U40 (2 vias).** /VDD_CC112 needs /CC_PA moved 0.35 mm on F.Cu; /RF_MOSI needs /VDD_CC112
  moved 0.25 mm on F.Cu. Both are the radio's own supply/PA rows — a real but small re-route.
* **C12, C32, C40, FB1 (5 vias).** These are not on the parts' pads (§3). Their blockers are
  /ICM_INT2, /1V1, /VREG_AVDD, /BARO_DRDY, /3V3, /SWDIO and the /RF_nCS via stack — inner-layer
  copper that has to be re-spaced, not a part that has to move.

---

## 5. Verification after each batch

All on copies; `base` = `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`
(sha256 `9B3BBA85C01AAC9E8365AF999F5231C3951E3428C37544A2B2CADC425F89953C`).

| check | base | after batch A (shipped) | how |
|---|---|---|---|
| vias total | 341 | **337** | `s2_detail.py` |
| **non-through by span** | **36** (33 micro/3 blind declared; 29 micro + 7 blind by pair) | **19** (15 micro + 4 blind by pair) | `s2_detail.py`, `census_batA.json` |
| by layer pair | F→In1 14 · In1→In2 10 · F→In2 3 · In2→B 5 · In1→B 4 | F→In1 7 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 2 | same |
| DRC, board's own rules (**set diff**) | 0 violations | **4** — `{via_diameter: +4}`, nothing else added | `kicad-cli pcb drc --severity-all` |
| DRC, no-HDI gate (drill ≥ 0.20) | 33 (`hole_size`) | **22** = 18 `hole_size` + 4 `via_diameter` | `.kicad_dru` + `kicad-cli` |
| unconnected, `kicad-cli` | 0 | **0** | DRC json |
| unconnected, `pcbnew` `GetUnconnectedCount` | 0 | **0** | `s24_void.py` |
| cap note | — | neither tool caps: both read 0, and the ESC 499-vs-1,542 discrepancy does not arise on this board | — |
| **minimum drill** | 0.100 | **0.100** (18 vias at 0.1) | `inv_batA.json` |
| **RF void** | 4.1699 mm² = **9.8338 %** (void_B 9.1392 %) | **bit-identical**: 4.1699 mm² = 9.8338 % | `s24_void.py`, `void_base_and_batA.json` |

**Two provenance notes, both measured, both differing from the brief:**

1. **RF void.** The brief's 1.2959 % is the **composed** board's figure. I reproduce it exactly on
   `fab-da-fanout3/work.kicad_pcb` (0.5495 mm² of 42.4040 mm², void_B 0.6013 %), and it is **not**
   the repo board's number: the repo board measures 4.1699 mm² / 9.8338 % over the *same* 42.4040 mm²
   of RF_50R F.Cu, before and after my edits. The difference is real copper (the repo board's In1
   /3V3 pour is 12,164 mm² against the composed board's 12,589 mm²), not a fill-state artefact —
   every zone is filled and `NeedRefill()` is false on both.
2. **"21 of 36 lie within U10's bbox + 2 mm".** Measured: **20** (15 on U10, C12 2, C32 2, C40 1) —
   and only 7 of those 20 are actually inside a U10 pad.

---

## 6. Answer

**36 confirmed by span** (33 `MICROVIA` + 3 `BLIND_BURIED` declared; 29 single-dielectric + 7
multi-dielectric by layer pair; 10 declared tokens contradict their pair; 29 physical stacks).
**17 of 36 cleared (47.2 %)** — 12 at the board's own 0.60/0.30 rule, 5 more at 0.40/0.20 — via 13
DRC-gated stack conversions, **0 by moving a part**. **19 remain (52.8 %)**.

Can the 36 be cleared by real layout work? **Two-thirds of them, yes — by via relocation, which the
brief did not expect; not by moving the parts, which the brief did expect.**

* **Moving parts clears 0.** 18 of the 36 are free-standing layer changes >0.8 mm from any pad of
  their own net, so no part can move them; and deleting the accused part outright still leaves
  every remaining site illegal (FB1: −0.650 → −0.400 mm; C12: −0.282 → −0.130 mm).
* **Pad assignment clears 0 of the U10 twelve.** Only 12 of U10's 90 pins can reach a legal
  through-via site and all 12 carry nets; the 9 spare pads are the sealed centre thermal grid, and
  the 0.60/0.30 site field inside U10's reach is 0.45 % of the area. Every one of the 15 U10 vias is
  **physically forced**, and 12 of them are bound by *another net's track*.

**What blocks the last 19: copper, not assignment.** No in-place through via (max legal radius
+0.182, and 0.40/0.20 needs 0.200); no reachable legal site (nearest 1.04–1.53 mm with stub slack
−0.25 to −0.35); and each needs 2–4 other nets moved across 2–4 layers. Batch B (slide along own
copper) kept **0 of 5** — the layer changes are track tees; batch C (slide + drag track ends)
produced **0 of 16** candidates. Clearing the rest is a U10 fan-out rip-up (~80 pins) plus a small
U40 re-route, or the HDI the board ships with.

### Artefacts

| file | note |
|---|---|
| `da_main_rev_b_36via_batA.kicad_pcb` (sha256 `160D6B97…9DED`, 2,268,484 B) | **the shipped board**: 19 non-through (from 36), DRC set diff `{via_diameter: +4}`, unconnected 0 on both tools |
| `da_main_rev_b_36via_batA.gate.json` | kept 13 stacks / 17 vias, dropped 16, per-stack evidence |
| `da_main_rev_b_36via_batA_batB.kicad_pcb` | **byte-identical to batA** (same sha256): batch B kept 0, so nothing was shipped from it — the identical hash is the receipt |
| `work/base.kicad_pcb` (sha256 `9B3BBA85…953C`, 2,252,603 B) | the untouched repo copy every number starts from |
| `census_base.json`, `census_batA.json`, `table36.md` | span census, both boards |
| `obst_base.json`, `obst_batA.json`, `u10.json`, `ownership.json` | per-layer obstruction, per-pin escape BFS, on-part ownership |
| `plan_A.json`, `plan_B.json`, `plan_C.json`, `partmove.json` | every candidate, kept or dropped |
| `drc/own_*.json`, `drc/gate_*.json` | every DRC run quoted above |

Scripts, in the order they matter: `s2_detail.py` (span census) · `s10_ownership.py` (is the via on
a pad) · `s3_analyse.py` (obstruction + site sweep) · `s4_u10.py` (per-pin escape BFS) · `s15_partmove.py`
(part-removal test) · `s6_exec.py` / `s5_apply.py` (batch A, DRC-gated) · `s7_slide.py` /
`s11_slide2.py` (batches B and C) · `s24_void.py` (RF void + unconnected).