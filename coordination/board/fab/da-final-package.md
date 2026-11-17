# drone-arm — close the last unconnected + REV B fab package

STATUS: **COMPLETE.** Package built and validated. Verdict: **not sendable — 10 unconnected
remain** (15 -> 10: 5 closed, 4 of them inherited from the interrupted attempt, 1 routed here).
Everything else in the package is verified; the single blocker is U10's 0.4 mm pitch fan-out.

Input : `evidence/fab-da-route-35/void/deliver.kicad_pcb` sha256 `79AF9C91308D9F53…` (unchanged, V35)
Result: `work/r_final.kicad_pcb` sha256 `CA2093D1AD97CF8E…` -> `package/` (20 files) ->
        `drone-arm-main-revB-fab-package-6L.zip`, manifest `PACKAGE-SHA256.txt`.
Output: `evidence/da-final-package/` (junction -> `D:\ep-audit-evidence\da-final-package`).
Board : 6 layers (F / In1..In4 / B), 165 footprints, 657 pads, 343 vias all through.

**Inherited state (not mine, re-verified here before use).** This directory already held an
interrupted attempt: it wrote `REPORT_attempt1_inherited.md`, routed 4 of the 15 (15 -> 11),
stamped REV B and plotted a package, then died at the manifest step. Everything below is measured
by me on copies; the inherited numbers are re-run, not quoted.

## 0. Preconditions — rules actually load (DONE)
- [x] `.kicad_pro` copied next to every working board (its own, unmodified; 15282 B).
- [x] rules read back by pcbnew: clr **0.125** / track **0.2** / via **0.6** / annular **0.1** /
      hole **0.2** / hole2hole **0.2** / copper-edge **0.5** — none zero
      (`work2/islands_r8b.json` header, `rules_assert.json`).
- [x] deliberately-wrong probe: `.kicad_dru` with `(constraint clearance (min 3mm))` moves
      kicad-cli DRC **42 -> 550** (42 inherited + **508** new `clearance`). Rules genuinely load.
      Run twice, independently: `_drc2/drc_own.json`, `_drc2/drc_wrong.json`.
- [x] baseline (delivered board, own rules): **42** violations = 37 `track_dangling` +
      5 `via_diameter`; **15** unconnected on kicad-cli and **15** on pcbnew ratsnest.
- [x] baseline invariants: 6 layers, 339 vias all through (**0** non-through), min drill **0.200**
      (tools 0.2/0.3/0.35), RF void **A 4.1699 mm2 = 9.8338 %** / B 3.8754 = 9.1392 %
      (`work2/void_measure_base_r8b.json`, same instrument as the delivered board).

## 1. STEP 1 — the unconnected (DONE: 5 of 15 closed, 10 open)

### 1.1 The 15 are not what the inherited note called them
`kicad-cli`'s unconnected list, resolved to geometric islands (`work2/islands_r8b.py`), shows
**11 items = 9 nets**, each a pair of copper islands. Six of the 11 are a bare U10 pad (no
copper at all); one more is a pad whose only copper sits on the other side of the break; the rest
carry copper that stops short:

| # | net | island A | island B | XY gap |
|---|---|---|---|---|
| 1 | /3V3 | 0.874 mm F.Cu track | U10.5 (pad only) | 2.924 |
| 2 | /3V3 | 0.600 mm F.Cu track | U10.24 (pad only) | 0.834 |
| 3 | /CAN_MOSI | In1 0.785 mm track | In1 12.332 mm track | 16.816 (same layer) |
| 4 | /GNSS_RESET_N | F.Cu 0.732 (U10.14 side) | B.Cu 10.587 | **0.000** (crosses under) |
| 5 | /RF_GPIO0 | F.Cu 1.032 (U10.21 side) | In2 2.143 | **0.000** |
| 6 | /RP2354B XIN | In1 0.707 (U10.30 side) | U10.30 pad | **0.000** |
| 7 | /GNSS_PPS | B.Cu 21.655 | U10.13 pad | 1.112 |
| 8 | /RF_GPIO3 | F.Cu 0.890 (U10.21 fan-out) | U10.23 pad | 1.128 |
| 9 | /RF_SCLK | In2 0.050 (stub) | U10.16 pad | 1.625 |
| 10 | /RF_nCS | In2 13.153 | U10.19 pad | 1.983 |
| 11 | /GND | 0.225 mm F.Cu track | C32.2 pad | zone-model item |

Three of them are two pieces of the *same net* that already overlap in XY on different layers:
they need a via, not routing. That reframes the job — and made item 3 closable immediately.
Item 11 changed shape after the GND spoke below (it is now a zone-fill split, see 1.5).

### 1.2 Routed so far, and how
Raster A\* 0.04 mm over 6 layers, foreign copper only as obstacle (pours recede on refill and the
final DRC runs on the refilled board), exact shapely verify at 0.125 mm before any track is kept,
island count re-measured after every edit (`work2/r11.py`, `r11b.py`, `r11c.py`).

| net | how | width | islands |
|---|---|---|---|
| /CAN_MOSI | raster A\* on In1, 16.8 mm span | 0.20 | 2 -> 1 |

### 1.3 Why the other 10 do not close at the board's own via size (measured)
A 0.2 mm track needs **0.237 mm** of clear space; a 0.6 mm via needs **0.425 mm**. Measured on the
board (`work2/why11.py`, exact distances): the best cell within 3 mm of every remaining break has
**0.34-0.42 mm** — below 0.425 for all ten. The U10 pads are 0.4 mm pitch (0.2 mm pad, 0.2 mm gap)
and the fan-out vias of the pins routed earlier sit 0.144-0.20 mm from each sealed pad, so the
raster A\* exhausts its free region in 1-9 s: "no path" for 10/10 at 0.2 and at 0.15 mm.
- [x] 0.6 mm via: **no legal site within 3 mm of any of the 10** (max exact clearance 0.42 mm).
- [ ] resolution (rip + 0.4/0.2 via class, the class the board already uses 5x) — see 1.4

### 1.4 Targeted rip and re-fan-out (two rounds, both rolled back)
The board already carries five **0.4/0.2** through vias (its own 5 inherited `via_diameter`
violations are exactly those), so the joiner was given a via ladder 0.6 -> 0.5 -> 0.45 -> 0.4,
recording the class each connection actually needed.

| pass | board in | objects ripped | unconnected in -> out | kept | verdict |
|---|---|---|---|---|---|
| A | inherited `r8b` (11) | none | 11 | **1** | kept: /CAN_MOSI |
| B | `r11_out` (10) | 41 (31 trk + 10 via, 13 nets, 0.32 mm ring) | 10 -> 31 after rip | **15** | 11 left, 3 nets newly broken, +6 `track_width`, +3 `via_diameter` -> **rolled back** |
| C | `r11c_out` | 85 (71 trk + 14 via, 19 nets, 0.90 mm ring) | 42 after rip | **20** | 16 left -> **rolled back** |

Round B/C are the useful measurement, not a fix: the joiner *can* re-close 15 and 20 breaks at the
board's **own 0.6 mm via class** once space is cleared, but the seven originally sealed pads stayed
sealed and each round leaves more nets broken than it closes. The fan-out ring is one connected
structure: 240 tracks + 47 vias serving 43 nets sit within 1.2 mm of a U10 pad, so a *local* rip is
zero-sum, and the *full* re-fan-out of that ring is a re-layout, not a routing job.

### 1.5 Final STEP 1 result — kept 5 of 15
- /CAN_MOSI (16.816 mm In1 span), 0.20 mm, raster A* + exact verify — kept.
- U10.62 /GND spoke: 0.58 mm x 0.20 mm track from the isolated thermal pad into the F.Cu pour
  (exact-verified clean) — kept.  It removes the pad item and exposes the real GND defect: one
  12174 mm2 F.Cu GND zone whose fill is split into two pieces that KiCad's connectivity calls
  disconnected (164 GND vias, all in the main piece).
- 4 of the 15 were routed by the interrupted attempt and are inherited, not mine (see A).
- **10 unconnected remain** — kicad-cli 10, pcbnew 10 — and every one is measured:
  7 U10 pads (5, 24, 13, 23, 16, 19, 30) whose escape throat is 0.18-0.30 mm against the 0.237 mm
  a 0.2 mm track needs and 0.325-0.425 mm a via needs; 2 cross-layer joins (/GNSS_RESET_N,
  /RF_GPIO0) whose only exact-legal 0.6 via sites clear foreign copper by 0.002 mm (0.1272 vs
  0.125), which is inside the plotting grid — not a design margin; 1 GND fill split above.

## 2. STEP 2 — REV B fab package (DONE, validated)
Built by `export_final.ps1` (one command; `logs/export_run5.log` holds every kicad-cli line), on a
copy of the final board `work/r_final.kicad_pcb` sha256 `CA2093D1AD97CF8E…`.

- [x] 13 Gerbers (6 copper + 2 mask + 2 paste + 2 silk + Edge.Cuts), `.gbrjob`, 2 Excellon files
      (PTH/NPTH apart), drill maps quarantined in `drill_maps\`, 1 position file — **20 files**,
      listed with sha256 in `PACKAGE-SHA256.txt`, zipped to
      `drone-arm-main-revB-fab-package-6L.zip` (20 entries, 408181 B).
- [x] sheet frame suppressed — proved by a control plot *with* `--include-border-title`:
      control Edge.Cuts = 287.00 x 200.01 mm vs package 140.15 x 100.15 mm (V13/V14).
- [x] revision stamp 'B' on 16 carriers (title block, gbrjob ProjectId, 13 gerbers' %TF.ProjectId,
      F.Silk text) and the stamp changed **no** geometry (V27: 13/13 layers identical).

| check | result |
|---|---|
| V08 6 copper layers: board / copper gerbers / gbrjob LayerNumber | **6 / 6 / 6** |
| V10-V12 Edge.Cuts centreline | 140.000 x 100.000 mm, 4 primitives, incl-stroke 140.15 x 100.15 = pcbnew bbox |
| V15/V16/V17/V18 drill files | 2 files, 0 blind/buried; per-diameter match: PTH **361 drills + 4 slots**, NPTH 6 drills; total **367 drills + 4 slots = 371 hits** |
| V19 min drill | **0.200 mm** (tools 0.20, 0.30, 0.35, 0.60, 0.65, 4.30) |
| V20/V21 .pos | **161 rows** = 165 footprints - 4 excluded; header `Ref,Val,Package,PosX,PosY,Rot,Side`; all 161 top side |
| V22/V23 gbrjob Size, BoardThickness | 140.15 x 100.15, 1.6 mm |
| V24/V36 gbrjob finish | `Finish: ENIG` **and** `SurfaceFinish: ENIG` (added explicitly, same value; not empty) |
| V25 gbrjob ProjectId | `main_rev_b` / **`B`** |
| V26 revision carriers | 16 carriers all read 'B', no 'rev?' anywhere |
| assertions | **34 pass / 2 fail** — the 2 are V30/V31, the unconnected count |

Two instruments were wrong and were fixed, not worked around:
`rev_inventory.py` did not parse `.g4` (so In4.Cu was invisible and V08 read 5 copper gerbers —
it is 6); `export_final.ps1` crashed reading a non-existent `drill_diameters_min` field, and wrote a
README whose dielectric table and drill census came out as `System.Object[]` — the shipped README is
now generated by `fab_readme.py` from the measured JSONs. Both fixes are logged in the report.

## 3. VERIFY — the invariants
| invariant | result |
|---|---|
| span census: 0 non-through vias | **PASS** — 343 vias, all `THROUGH F.Cu->B.Cu`; independent `.kicad_dru` gate (`A.Via_Type != Through`) finds 0 (V28/V29) |
| min drill >= 0.200 | **PASS** — 0.200 mm |
| RF void 4.1699 / 9.8338 % | **PASS** — A 4.1699 mm2 = 9.8338 %, B 3.8754 = 9.1392 %, bit-identical to the delivered board (V32) |
| unconnected on both tools | **FAIL — 10 on pcbnew, 10 on kicad-cli** |
| DRC set diff vs 42 baseline | **42 -> 37**: +2 `track_width` (both inherited 0.15 mm necks on /LSM_INT2 and /RF_MOSI), -7 `track_dangling`, 35 kept, 5 inherited `via_diameter` untouched |

## 4. Verdict
**Not sendable to a fab at 6 layers.** 10 unconnected items remain. Nothing else blocks: the package
is internally consistent (6 copper layers, 140x100 outline, drills+slots reconciles with the board
by diameter, position rows reconcile with footprints, gbrjob complete with an explicit
SurfaceFinish, 0 non-through vias, 0.200 mm min drill, RF void unchanged, revision 'B' everywhere).

The blocker is one thing: **U10's fan-out**. U10 is a 90-pad 0.4 mm pitch part (0.2 mm pad, 0.2 mm
gap); a 0.2 mm track needs 0.237 mm and the board's 0.6 mm via needs 0.425 mm. The pins that were
fanned out earlier put their 0.6 vias 0.144-0.200 mm from the 7 pins that are still open, and the
inner layers under the package are just as crowded, so:
- 7 pads (5, 24, 13, 23, 16, 19, 30) have a measured escape throat of 0.18-0.30 mm — no legal exit;
- 2 cross-layer joins (/GNSS_RESET_N, /RF_GPIO0) have exactly one near-legal 0.6 via site that
  clears foreign copper by 0.002 mm (0.1272 vs 0.125) — inside the plotter grid, not a margin;
- 1 item is a GND fill split (one 12174 mm2 zone, fill disconnected in two, 164 GND vias all in
  the main piece).

What would close it, in cost order: (1) re-fan-out the whole U10 ring — 240 tracks + 47 vias on 43
nets sit within 1.2 mm of a U10 pad, and a *partial* rip is zero-sum (rounds B and C above); (2)
declare the 0.4/0.2 via class for these pins, which the board already uses 5x — the joiner closed
15 and 20 breaks that way, but the 7 pads still had no legal exit; (3) move the part or change its
pitch. None of these is "routing the last 15".

**Sendable today: NO. Sendable after a U10 fan-out redo: everything else is already verified.**


## A. Appendix — inherited attempt (superseded, kept for audit trail)
See `REPORT_attempt1_inherited.md`.
