# drone-arm — give the 7 sealed U10 pads a legal escape (rev B → fab)

STATUS: **COMPLETE.** One of the seven pads is closed with zero new violations; the other
six are proven to be at the fan-out's capacity limit and cannot be closed without a U10
re-fan or a via-class change. Verdict: **not sendable — 9 unconnected remain** (10 → 9).
Every number below is measured here, on copies, with the board's own rules loaded.

One task only: the 7 U10 pads at 0.4 mm pitch that cannot escape against the 0.237 mm a
0.2 mm track needs. Nothing else on this board was re-opened.

- Input board (named in the task) : `evidence/fab-da-route-35/void/deliver.kicad_pcb`,
  sha256 `79AF9C91308D9F53…C686`, 2,406,687 B — **15** unconnected.
- Input board (actually worked on): `evidence/da-final-package/work/r_final.kicad_pcb`,
  sha256 `CA2093D1AD97CF8E…2729`, 2,442,062 B — the rev-B package board, = deliver + the
  5 closures of the last wave (4 inherited + /CAN_MOSI 16.8 mm on In1 + the U10.62 GND
  spoke). It is the board that carries the **10** remaining unconnected and every figure
  in the task state (DRC 37, 10 unconnected, 343 through vias, RF void 4.1699). Starting
  from `deliver` would re-open five items that are already closed, so the deviation is
  stated here and `deliver` is kept as the reference for every invariant comparison.
- Output: `evidence/da-escape-7pads/` (junction → `D:\ep-audit-evidence\da-escape-7pads`;
  free space at start **140.65 GB** on D:).
- Host: KiCad 9.0.7, `kicad-cli.exe` + bundled `python.exe` (pcbnew), CADQUERY at
  `C:\Program Files\Python312\python.exe`.
- Board: 6 layers (F / In1..In4 / B), 165 footprints, 657 pads, 343 vias — all through.

## 0. Preconditions — reproduced, not quoted

- [x] Working copy `work/base/da_base.kicad_pcb` + companion `da_base.kicad_pro`.
      The companion set is **only** the `.kicad_pro`: a search of the whole
      `fab-da-route-35` tree finds no `fp-lib-table` and no local `.pretty`, so no
      invented-footprint risk of the kind that produced 52 fake violations elsewhere.
- [x] Baseline DRC re-run from scratch in `drc/base/` with
      `kicad-cli pcb drc --format json --severity-all --units mm`:
      **37 violations, 10 unconnected** — histogram 30 `track_dangling`, 5 `via_diameter`,
      2 `track_width`. Independently reproduces the package report.
- [x] Design rules read back from the board itself (pcbnew `DesignSettings`), none zero:
      clearance **0.125**, track min **0.2**, via min size **0.6**, via min annular **0.1**,
      through drill min **0.2**, hole-to-hole **0.2**, copper-to-edge **0.5**.
- [x] U10 identified: `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm`, at (59.000, 50.000),
      rotation 0, F.Cu. 90 pads = 80 perimeter + 1 EP 3.4x3.4 + 9 paste-only apertures.
      Perimeter pads **0.200 x 0.800 mm on a 0.400 mm pitch** (0.200 mm gap).
- [x] The 10 unconnected items resolved to: 7 bare U10 pads, 2 cross-layer joins
      (/GNSS_RESET_N, /RF_GPIO0), 1 GND zone-fill split. Only the 7 are in scope.

### 0.1 What "0.237 mm" actually is
`0.125` clearance + `0.100` track half-width + `0.012` raster/verify margin = **0.237**.
The margin is the router's insurance against rasterisation error, not a fab rule: the
**absolute legal requirement is 0.225 mm**. Both numbers are reported below.

## 1. STEP 1 — the seven pads, measured

Two different quantities get conflated in "0.18–0.30 mm of escape", so both are measured
at **H = 0.01 mm** (the inherited figure came from a 0.04 mm raster, which is ±0.03 mm):

- **throat_max** — the largest clearance available to a 0.2 mm track centreline anywhere
  within 0.12 mm of the pad. This is the number the inherited report quoted. A *local best
  cell*, not a route.
- **lane** — the free region actually **connected to the pad** through cells that satisfy the
  0.237 rule, i.e. the true escape, flood-filled from the pad; plus the legal via sites that
  lie *on that lane* (a via off the lane is unreachable). `g7b_lane.py`. Note the lane is
  measured on F.Cu, the layer the track occupies; the via test uses the all-layer minimum.

| pad | net | position (mm) | throat_max | vs 0.237 | lane | lane extent | 0.6/0.5/0.4 mm sites on the lane |
|---|---|---|---|---|---|---|---|
| 5 | /3V3 | (54.050, 47.800) | 0.210 | **−0.027** | 0.160 mm² | 0.41 mm | 0 / 0 / 0 |
| 13 | /GNSS_PPS | (54.050, 51.000) | 0.305 | +0.068 | **1.004 mm²** | **1.90 mm** | **2** / 154 / 538 |
| 16 | /RF_SCLK | (54.050, 52.200) | 0.278 | +0.041 | 0.226 mm² | 0.91 mm | 0 / 0 / 0 |
| 19 | /RF_nCS | (54.050, 53.400) | 0.259 | +0.022 | 0.175 mm² | 0.61 mm | 0 / 0 / 0 |
| 23 | /RF_GPIO3 | (56.000, 54.950) | 0.331 | +0.094 | 0.969 mm² | 1.85 mm | 0 / 0 / 25 |
| 24 | /3V3 | (56.400, 54.950) | 0.315 | +0.078 | 0.952 mm² | 1.83 mm | 0 / 0 / 131 |
| 30 | /RP2354B MCU/XIN | (58.800, 54.950) | 0.305 | +0.068 | 0.384 mm² | 1.20 mm | 0 / 0 / 0 |

**The inherited claim "0.18–0.30 mm of escape against the 0.237 mm needed" is only
literally true for pad 5.** For the other six the local best cell is *at or above* 0.237 —
but for four of them it is an isolated cell that no track can reach. The bare pad is
0.200 x 0.800 = 0.160 mm², so a lane of 0.160 mm² with an extent of 0.41 mm (the pad's own
half-length) means the free set **is the pad and nothing else**. So:

- **pads 5, 16, 19, 30 cannot leave the pad or reach any legal via site of any class.** Pad 5
  is walled in (lane = the pad); 16, 19 and 30 have a real lane, but the best all-layer
  headroom anywhere on it is **0.145 / 0.292 / 0.105 mm** against the 0.325 mm even a 0.4 mm
  via needs, so no via of any size can be placed in the pocket.
- **pads 13, 23, 24 do have lanes** and legal sites on them: 13 at the board's own 0.6 mm
  class; 23 and 24 only at 0.4 mm.

It is exactly these seven and no more: the flood fill finds no other U10 pad (or any other
pad on the board) in this condition; the other 73 U10 pads and all 83 pads of the two
cross-layer joins drain normally.

## 2. STEP 2 — the cause, per pad

Not a zone (pours recede), not the connector/shield, not a via's own annular ring (U10 is
SMD — its pads have no hole). Every one is **the previous fan-out of the neighbouring pads**.
Exact nearest foreign copper (tolerance 0.60 mm, `g2_cause.py`):

| pad | sealed by | distance | what it is |
|---|---|---|---|
| 5 /3V3 | E: /LSM_INT1 via 0.60/0.30 | **0.150** | pad 4's fan-out via, dead ahead of the pad tip |
|  | E: /LSM_INT1 stub 0.106 mm | 0.175 | debris left by an earlier rip |
|  | W: /ICM_INT2 via 0.70/0.35 | 0.168 | pad 3's fan-out via, dead ahead of the other tip |
|  | N/S: pads 4 and 6 | 0.200 | the 0.4 mm pitch itself |
| 13 /GNSS_PPS | W: /GNSS_RX via 0.60 | 0.162 | pad 12's via |
|  | E: /GNSS_RESET_N track w0.25 | 0.175 | pad 14's escape turning out of its tip |
| 16 /RF_SCLK | E: /RF_MOSI track w**0.15** | 0.167 | the board's own `track_width` violation, reused as an obstacle |
|  | W: /3V3 track w0.25 + 0.100 mm stub | 0.175 / 0.200 | pads 15's escape |
|  | SW: /RF_MISO via 0.60 | 0.258 | covers the pad's whole y-range at the tip |
| 19 /RF_nCS | W: /GNSS_RX via 0.60 | 0.175 | a via of a *different* signal crossing here |
|  | E: /RF_MISO via 0.60 + 0.106 mm stub | 0.179 / 0.175 | pad 18's fan-out |
| 23 /RF_GPIO3 | S/SE: /RF_GPIO2 via 0.60 + 3 tracks | 0.175–0.250 | pad 22's fan-out runs the whole outboard lane |
|  | NE: /RF_GPIO0 via 0.60 | 0.285 | |
| 24 /3V3 | S: /RF_GPIO0 via 0.60 | **0.125** | exactly at the rule floor — zero margin |
|  | E: /PA_EN track w0.2 | 0.200 | pad 25's escape |
| 30 /XIN | E: /XOUT track w0.25 | 0.175 | pad 31's own escape runs straight past it |
|  | SE: /3V3 via 0.60 | 0.179 | |
|  | W: /3V3 track w0.2 | 0.200 | |
|  | SW: /CAN_SCK via 0.70 | 0.420 | not the blocker, but it caps the 0.6 via headroom |

**The mechanism.** At 0.4 mm pitch with 0.125 clearance and a 0.2 mm track, one track per
pad is geometrically impossible — a track plus its two clearances needs 0.45 mm of pitch.
The standard answer, and the one this board used, is a two-rank fan-out: 0.6 mm vias at
0.8 mm pitch in an inboard rank and an outboard rank, 0.85 mm from the pad tips. That works
only while both rank slots stay free. On these seven pads a neighbour took the slot on one
axis and something else took the other, so the pad has no lane at all.

**And a large part of the obstruction is not real routing.** Of the 38 foreign objects
within 0.35 mm of the seven pads, **15 are electrically redundant**: deleting any one of
them leaves the board's unconnected count at exactly 10 (`g6_prune.py` — delete, rebuild
connectivity, compare, re-add). Most are 0.018–0.150 mm stubs, i.e. debris from the earlier
rip-and-rejoin rounds that were rolled back. That is free clearance, so it gets taken first.

## 3. STEP 3 — the fix: candidates costed, the one chosen

### 3.1 What each candidate actually costs (all measured, not estimated)

**(a) move the escape to a different layer — CANNOT WORK AS STATED.**
The U10 pads are F.Cu SMD (0.200 x 0.800, layer set `F.Cu` only), so whatever happens
later the escape has to begin on F.Cu. The only layer freedom is *after* the via, and a
non-through via is forbidden here (span census must stay 0), so every escape ends in a
through via. Layering therefore does not touch the binding constraint, which is the F.Cu
lane: on this board the F.Cu region reachable from pads 5/16/19/30 is 0.159–0.384 mm², and
the best all-layer headroom anywhere inside it is **0.105–0.292 mm** against the 0.425 a
0.6/0.3 via needs. No layer assignment changes that.

**(b) a smaller legal via — helps 2 of 7 and costs a DRC error.**
Legal via sites *lying on each pad's own escape lane* (`g7b_lane.py`, H = 0.01, exact
hole-to-hole):

| pad | 0.6 / 0.5 / 0.4 mm sites on the lane |
|---|---|
| 13 /GNSS_PPS | **2** / 154 / 538 |
| 23 /RF_GPIO3 | 0 / 0 / 25 |
| 24 /3V3 | 0 / 0 / 131 |
| 5, 16, 19, 30 | **0 / 0 / 0** |

So a smaller via cannot reach four of the seven at any size. For 23 and 24 a 0.4/0.2 via
does work, but the board's floor is 0.6 mm, so each costs **1 new `via_diameter` error** —
that is weakening the gate, so it was not taken.
The brief's premise "the board's smallest through drill is 0.127" **does not hold on this
board**: the measured tools are 0.20 / 0.30 / 0.35 mm, min drill **0.200**, and the 5
existing 0.4 mm vias use a 0.2 mm drill. A 0.127 drill would break the min-drill ≥ 0.200
invariant that step 5 requires to survive.

**(c) re-order the fan-out row — works for one pad and breaks its neighbour.**
This is what genuinely frees pad 5. Deleting the 15 obstruction objects in front of the
seven pads grows pad 5's lane from **0.160 mm² (the bare pad) to 1.006 mm² with 20 legal
0.6 mm sites**. But those same objects are pad 4's (/LSM_INT1) escape: the 15-object batch
takes unconnected **10 → 11** and leaves pad 4 broken; restoring pad 4's via reseals pad 5
(measured, both directions). Cost: a re-fan of one neighbour per pad — i.e. the whole U10
ring, which is what the previous wave already judged too expensive.

**(d) nudge U10 — rejected.** 90 pads move at once and 76 of them have track copper
attached within 0.05 mm of the pad, so any nudge detaches all of them. The defect is
capacity, not position: moving the part does not create a rank slot.

**(e) stub on the pads that have 0.30, a different route on the pad at 0.18 — EXECUTED.**
Pad 13 closes at the board's own 0.6/0.3 class with zero new violations (§3.2).

### 3.2 The fix that was kept — pad 13, /GNSS_PPS
| object | layer | from | to | length |
|---|---|---|---|---|
| track w0.20 | F.Cu | (54.455, 50.945) — the pad's inboard tip | (54.925, 50.765) | 0.503 mm |
| via **0.60 / 0.30** through | F.Cu–B.Cu | (54.925, 50.765) | | |
| track w0.20 | B.Cu | (54.925, 50.765) | (53.955, 49.775) — joins the existing 21.655 mm /GNSS_PPS run | 1.386 mm |

Found by windowed A* at H = 0.01 over 6 layers, reduced from 15 raster segments to 2 by
greedy line-of-sight, and then re-verified exactly at 0.125 mm before placement
(`g10_place.py`). It is the *only* one of the 7 whose escape needs no other net's copper
to move.

### 3.3 Pad 24 — a legal 0.6 route exists, but it is the same site pad 13 needs
The A* also finds a legal 0.6/0.3 route for pad 24 (11.73 mm, 8 segments after smoothing,
In4 for the long leg). It terminates on the **same** 0.6 mm site (54.925, 50.765) — that
cell is the only one within 4 mm of either pad with the 0.425 mm of all-layer headroom a
0.6 via needs. Placing both put two vias **0.010 mm apart** and produced 6
`shorting_items` (/3V3 ↔ /GNSS_PPS) + 1 `hole_to_hole`, so the pair was rolled back and
only pad 13 kept. Pad 24 does have a clean 2.46 mm route at the 0.4/0.2 class — 1 new
`via_diameter` error, not taken.

### 3.4 Why 5, 16, 19, 23 and 30 are not closed
- **16, 19, 30**: no legal via site of *any* class lies on their escape lane (§3.1b), and
  the lane itself is a dead end 0.61–1.20 mm long. Closing them requires a neighbour's
  fan-out copper to move, and every candidate move measured here breaks that neighbour
  (§3.1c) — that is a U10 re-fan, not a fix.
- **5**: closable, but only after ripping pad 4's escape copper, which then has to be
  re-laid (§3.1c).
- **23**: closable only at the 0.4/0.2 class.

## 4. STEP 4 — DRC gate: kept vs attempted

Every attempt was run with the board's own `.kicad_pro` beside it, zones refilled
(`ZONE_FILLER` on all 5 zones) and DRC'd with `--severity-all --units mm`.

| # | board in | change | unconnected | violations | kept? |
|---|---|---|---|---|---|
| **A** | `base` | 2 tracks + 1 via 0.6/0.3 on pad 13 | 10 → **9** | 37 → **36** — **0 new**, 1 `track_dangling` resolved | **KEPT** |
| B | `base` | A **plus** the 11.73 mm /3V3 route for pad 24 | 10 → 8 | 37 → **43**: +6 `shorting_items`, +1 `hole_to_hole` (vias 0.010 mm apart) | rolled back |
| C | `base` | delete the 15 individually-redundant objects in front of the 7 pads | 10 → **11** | 37 → 39 (+2 `track_dangling`) | rolled back |
| D | `base` | delete 14 of them (keep pad 4's via) | 10 → **11**, and pad 5 resealed | — | rolled back |

Two instrument errors were caught and corrected rather than worked around:
1. `g7_escape.py` first scored "can a track go here" with the **all-layer** minimum
   distance — that is the *via* criterion, and it made every pad look sealed (it hid
   pad 5's 20 legal sites entirely). Replaced by `g7b_lane.py`, which uses F.Cu for the
   track mask and all layers only for the via mask. The buggy instrument is kept as
   `work/g7_escape_buggy_allayer.py` for the audit trail.
2. The 0.04 mm raster used by the previous wave is blind to a site that clears copper by
   4 µm (0.4414 vs 0.4370), which is exactly the case for pads 13 and 24. At H = 0.01 both
   close at 0.6/0.3. **The previous wave's "no path at any class" was raster resolution,
   not geometry.**

A third: the delete-one-at-a-time redundancy test does not compose — 15 objects each
measured "free" in isolation cost one break when deleted together, because two stubs were
in series. Hence D.

## 5. STEP 5 — whole-board verification of the changed board (`work/f2r.kicad_pcb`)

| invariant | required | measured | verdict |
|---|---|---|---|
| span census | 0 non-through | **344 vias, 344 THROUGH F.Cu→B.Cu**, `non_through_by_span = 0`, `non_through_by_drill_lt_0_2 = {}` | **PASS** |
| min drill | ≥ 0.200 | **0.200** (tools 0.20 / 0.30 / 0.35) | **PASS** |
| unconnected, kicad-cli | — | **9** | 10 → 9 |
| unconnected, pcbnew | — | **9** | agrees |
| DRC set diff vs 42-baseline chain | no new types | **37 → 36**: 0 new, 1 `track_dangling` resolved; histogram 29 dangling / 5 `via_diameter` / 2 `track_width` | **PASS** |
| RF void | 4.1699 mm² / 9.8338 % bit-identical | **A 4.1699 = 9.8338 %**, B 3.8754 = 9.1392 % — identical to the delivered board *and* to the base | **PASS** |

Remaining 9 unconnected: U10 pads **5, 16, 19, 23, 24, 30** (6), the two cross-layer joins
(/GNSS_RESET_N, /RF_GPIO0), and the GND F.Cu zone-fill split.

## 6. STEP 6 — regenerated package and assertions (DONE)

The board changed, so the package was rebuilt by the **previous wave's own
`export_final.ps1`, unmodified** (staged into `pkg/` with its 10 helper scripts), run as
`-Board work/f2r.kicad_pcb -OutDir pkg -Rev B -BaseDir <delivered board copy>`:

- `pkg/package/` — **20 files** (13 Gerbers, `.gbrjob`, 2 Excellon PTH/NPTH apart, 1 `.pos`),
  zipped to `pkg/drone-arm-main-revB-fab-package-6L.zip` (20 entries, **408,065 B**).
- SurfaceFinish / Finish **ENIG** (V24 and V36 both read from the gbrjob, neither empty).
- Revision **B** on 16 carriers (V25/V26), and the stamp changed no geometry (V27, 13 layers).
- Hole census **368 drills + 4 slots = 372 hits**, min drill **0.200** (tools 0.2/0.3/0.35/
  0.6/0.65/4.3); .pos 161 rows; outline 140.00 x 100.00 centreline.
- Rules proof re-run on the packaged board: a deliberately-wrong `.kicad_dru` (3 mm) moves
  DRC **36 → 544** (508 clearance), so the 36 is a real measurement and not a missing ruleset.

### Assertion count: **34 pass / 2 fail of 36**

The two failures are **V30 and V31** — the unconnected count, at **9** instead of 0. They
were also the two failures before this work (at 10). Everything else passes, including
V28 span census (344 vias, 0 non-through), V19 min drill 0.200, V32 RF void bit-identical,
V08/V10 layer count and outline, V15/V16/V17/V18 drills-vs-slots, V20/V21 pos, V24/V36
ENIG, V25/V26 revision B.
(The brief quotes the previous figure as "34/35"; the script's own set is 36 because V36,
the explicit `SurfaceFinish` field, was added after that number was written. The count is
unchanged: 34 pass, the same two fail.)

## 7. Verdict

**IS DRONE-ARM NOW SENDABLE TO A FAB? — NO.**

What this work establishes, with numbers:

1. **1 of the 7 is closed.** Pad 13 (/GNSS_PPS) now has a legal escape at the board's own
   0.6/0.3 through-via class: 0.503 mm F.Cu stub + 0.6/0.3 via + 1.386 mm B.Cu. Verified
   exactly, DRC'd on a refilled board, **zero new violations** (37 → 36, one `track_dangling`
   resolved), unconnected 10 → 9 on both tools.
2. **The other 6 cannot be closed by any local engineering that keeps the current rules.**
   This is a capacity limit, not unfinished routing: at 0.4 mm pitch with 0.2 mm tracks,
   0.125 mm clearance and 0.6 mm through vias the U10 field needs a two-rank fan-out, both
   ranks are occupied, and the measurements prove there is nothing left to take —
   no 0.6 mm via site within 2.5 mm of pads 5, 19, 24, 30 (max all-layer headroom 0.295–0.420
   against 0.425 needed); no via site of *any* class on the lanes of pads 5, 16, 19, 30; and
   the one operation that does free pad 5 (removing pad 4's fan-out via) breaks pad 4.
3. **The 7 were never the whole blocker.** Three of the board's 10 unconnected items are
   outside them: the two cross-layer joins (/GNSS_RESET_N, /RF_GPIO0) and the F.Cu GND
   zone-fill split. So even a complete 7-pad fix would have left the board at 3 unconnected;
   the brief's "7 pads are the only thing between a finished rev-B package and a fab order"
   does not hold as stated.

What would actually make it sendable, in cost order:
- **Re-fan U10** — rip and re-lay the fan-out ring (240 tracks + 47 vias on 43 nets within
  1.2 mm of a U10 pad) as one 2-rank/4-side fan-out, then re-join. This is the only path that
  keeps 0.2 mm tracks / 0.125 mm clearance / 0.6 mm vias unchanged. It is a re-layout.
- **Declare a 0.4/0.2 mm via class for the U10 breakout** (0.1 mm annular, 0.2 mm drill — the
  board already carries 5 of them). Closes 23 and 24 immediately and, with the pad-4 re-fan,
  5 as well; it converts the 5 existing `via_diameter` errors into conforming geometry, but it
  is a **design-rule change** and therefore not taken here.
- Then close the 2 joins and the GND fill split.

Deliverables: `work/f2r.kicad_pcb` (the changed board), `pkg/package/` + the zip, `pkg/assertions.json`,
`pkg/run.log`, and the measurement JSONs listed in the appendix.

## A. Appendix — instruments and raw evidence
`work/g1_dump.py` pad/via/neighbour dump · `work/g2_cause.py` exact nearest-foreign-copper
· `work/g5_head.py` fine local via headroom · `work/g6_prune.py` one-at-a-time redundancy
test · `work/g7b_lane.py` per-pad lane flood fill (correct layer semantics) ·
`work/g7_escape_buggy_allayer.py` the superseded version, kept for audit ·
`work/g3b_feas.py` A* per via class at 0.04 · `work/g9_join.py` windowed A* at H = 0.01 ·
`work/g10_place.py` line-of-sight smoothing + exact re-verify · `work/g8_verify_ops.py`
exact pre-flight for a proposed op list · `work/edit.py` parametric board edits ·
`work/refill.py` zone refill · `work/render.py` layer renders · `work/s5_void.py`,
`work/span_census7.py` the programme's own RF-void and span instruments.
JSONs: `g1_base`, `g2_base`, `g3b_base`, `g5_base`, `g6_base`, `g7_base`, `g7b_base`,
`g7b_p1`, `g7b_p2`, `g9_base_06`, `span_f2r`; DRC `drc/drc_base.json`,
`drc/drc_p1.json`, `drc/drc_f1r.json`, `drc/drc_f2r.json`; logs in `logs/`.