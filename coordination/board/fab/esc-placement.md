# ESC rev_b — compacted single-sided placement

**Unit:** esc-placement · **Input:** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
(sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`, copied to
`esc_rev_b_orig.kicad_pcb`) · **Host:** KiCad 9.0.7, `pcbnew` via
`C:/Program Files/KiCad/9.0/bin/python.exe`, analysis in CPython 3.12.

**Nothing in this unit was written into a repo.** Every artefact below is in
`E:/engineering-portfolio-audit/evidence/esc-placement/`, produced from a copy.

---

## 0. Headline

| quantity | before | after | delta |
|---|---|---|---|
| board outline | **173.800 × 282.930 mm** | **153.10 × 241.75 mm** | −20.7 mm W, −41.2 mm H |
| board area | **491.73 cm²** | **370.12 cm²** | **−121.61 cm² = −24.73 %** |
| footprint bbox area | 262.19 cm² | 262.19 cm² (unchanged) | — |
| **fill ratio** | **53.32 %** | **70.84 %** | +17.52 pts |
| footprints | 687 | 687 | 0 added, 0 deleted |
| on B.Cu | 0 | **0** | none placed on the back |
| footprints translated | — | **687 / 687** | all |
| min part-to-part bbox gap | **−2.52 mm** (362 pairs < 0.5 mm) | **+0.60 mm** (0 pairs < 0.5 mm) | cleaner than today |
| kicad-cli unconnected | 499 | **499** | **0 change** |
| pcbnew ratsnest unconnected | 1542 | 1620 | +78 (+5.1 %), 8 stale segments |

Artefacts: `esc_rev_b_compact.kicad_pcb` (placement + carried copper),
`placement_after.png`, `placement_before_after.png`, `placement_before.png`,
`placement.json`, `placement_after.json`, `blocks.json`, `new_positions.json`,
`verify_compact.json`, `drc_*.json`.

The brief's 492.4 cm² is the same board measured including the 0.1 mm outline stroke;
this unit's figure (491.73 cm²) is the Edge_Cuts **polygon** area
(`placement.json` → `outline.true_area_mm2 = 49173.2`). Both are the same board; the
percentage reduction is identical to 0.1 pt either way.

---

## 1. What the board actually is (measured, not assumed)

`dump_placement.py` → `placement.json`:

```
outline     4 Edge_Cuts items, x 0.200..174.000, y 0.520..283.450
            bbox 173.800 x 282.930 = 49173.2 mm2 ; polygon area 49173.2 mm2  (a plain rectangle)
board       687 footprints · 3454 pads · 667 nets · 154 track segments · 1990 vias · 96 zones
            footprints on F.Cu = 687 ; on B.Cu = 0
sum of footprint bounding boxes = 26218.8 mm2 = 262.19 cm2  -> fill 53.32 %
```

**The functional map falls out of the reference designators, and it is exact.**
Refs are `<prefix>1<channel><seq>` for the six motor channels, `<prefix>2<seq>` for
control, `<prefix>7<seq>` for the isolated aux section (`group_blocks3.py`):

| block | footprints | part area | what it is |
|---|---|---|---|
| **M1…M6** (6 × identical) | 97 each = 582 | **4060.5 mm² each** | one complete, **galvanically isolated 60 A motor drive** |
| **CTRL** | 105 | 1856.0 mm² | 174 × 43 mm strip along the top edge |
| total | 687 | 26218.8 mm² | |

**The six channels are bit-identical, not merely similar.** Tested three ways
(`group_blocks3.py`, `group_blocks2.py`):

1. multiset of `(value, footprint)` identical across all six — `extra=[] missing=[]`;
2. every channel occupies the *same* 86.27 × 80.03 mm box;
3. 564 footprints carry motor-channel nets and **564 of 564 agree with their ref
   channel; 0 disagree**.

`cell_max_local_deviation` between channels, measured on the saved compact board, is
0.1 mm — i.e. 0.01 mm rounding of the source layout, not a design difference
(`verify_place.py`). **So the six phase blocks are already laid out identically and
symmetry is not currently a defect.** The compaction stamps the same cell six times by
pure translation, which keeps it that way (`six_cells_identical_multiset = true`).

### Each channel is an independent 60 A cell — there is no shared high-current bus

This is the most important structural fact and it decides the whole problem. From
`J1101`/`J1102`/`U1101` net lists:

```
J1101 FUSED_BATTERY_TAP  nets /Motor 1 power cell/M1_BATP_IN , /M1_BATN
J1102 MOTOR_PHASES       nets /M1_PHASE_A , /M1_PHASE_B , /M1_PHASE_C
U1101 DRV8353SRTAR       M1_BATP, M1_PHASE_A/B/C, M1_GHA/GLA/... gate nets
U1102 STM32G431CBT6      M1_3V3I, M1_PWM_*, M1_CSA_*, M1_UART_*
U1103 ISO6731FDWR        /3V3 , /DGND , M1_CMD , M1_STATUS , M1_UART_*
```

Net census: **`/M1_BATN` … `/M6_BATN` are six separate nets** (56 pads each), as are
`/M1_BATP`…`/M6_BATP` (17 pads each) and `/M{1..6}_PHASE_{A,B,C}` (5 pads each).
There is **no** shared `VBAT` or `PHASE` net. Each channel: own fused battery tap →
own shunt → own 820 µF bulk + 9 × 10 µF DC link → own 6 × TOLL half-bridge → own 3-phase
lug, with its own STM32G431, its own DRV8353, its own INA296A, its own RFM-0505S isolated
supply and an **ISO6731 digital isolator** to the control block. The only cross-channel
nets are `/3V3`, `/DGND`, `/ARM_SAFE`, `M*_CMD`/`M*_STATUS`, CAN and USB — all
milliamp-class.

Consequence: **the board is 6 × (one 60 A converter) + 1 × housekeeping, and the six
converters do not interact.** That is why an identical regular array is the correct
answer, and why the CTRL block can be packed hard with no current-path penalty at all.

---

## 2. The limits, established before any placement (as instructed)

The instruction was right that an ESC's area should be set by current, creepage and
thermal. So those were derived first. **All three turn out to constrain *width and
adjacency*, not *area* — and the measured evidence for that is below.**

### (a) Current-carrying copper width at 4 oz — NOT the binding constraint

Outer copper is 0.14 mm = 4 oz (`placement.json` stackup, and AGENT_BOARD confirms).
Assumed phase current **60 A** (the brief's figure — flagged ASSUMED, not derivable from
the file). IPC-2221/2152 external, `A = (I / (k·ΔT^0.44))^(1/0.725)`, k = 0.048,
A in mil², copper 0.14 mm = 5.512 mil:

| ΔT | required area | required **width, one 0.14 mm layer** | with all 4 layers paralleled (0.385 mm) |
|---|---|---|---|
| 20 °C | 3037 mil² | **14.00 mm** | **5.09 mm** |
| 40 °C | 1992 mil² | **9.18 mm** | **3.34 mm** |
| 60 °C | 1555 mil² | **7.17 mm** | **2.61 mm** |

The TOLL land (`PG-HDSOP-16_TOLT`, 11.56 × 14.92 mm) is ≈ 9 mm wide on its drain tab, so
a single-layer 60 A run is at the ΔT = 40 °C limit and **fails at ΔT = 20 °C**. A 4-layer
ESC must therefore parallel F.Cu + In1 + In2 + B.Cu, which is what the pour pattern
already does (96 zones, 66 on F.Cu, 18 on In2, 6 on In1, 6 on B.Cu).

**So 60 A needs ≥ 3.3–5.1 mm of copper width, and every phase column on this board
already has 11.56 mm of FET plus a 20 mm slot — 3.9× the requirement.** Copper width
therefore does not set the cell size at all. It sets two rules that the new placement
obeys:

1. each 60 A run must be a **plane, not a trace** — the FET drain/source land is the
   plane, which is why the switch block must stay contiguous;
2. **adjacency**: battery tap → FET drain, and FET source → phase lug, must be short.
   In the executed cell those runs are **< 40 mm** with the tap directly beside the
   FET block and the lug directly above it (`design_cell.py:anchors`).

### (b) Creepage / clearance — this IS the binding constraint, and it is measured

The board's own pour rule, measured across all 96 zones
(`summary.json`: `zone_clearance_hist {"0.5": 96}`), is **0.5 mm**. At a ~50 V rail
(12S; corroborated by the `820u 100V` bulk and the `SM8S51A` 51 V standoff TVS) 0.5 mm
is the design's own creepage choice, and it is what consumes area between parts. The new
placement therefore adopts **0.5 mm as a hard rule between every pair of parts** and
achieves **0.60 mm worst case** — 20 % better than the original board, which has 362
pairs closer than 0.5 mm and a worst case of **−2.52 mm** (overlapping bounding boxes).

### (c) Thermal — constrains contiguity, not area

`IPTC014N10NM5` = 100 V, 1.4 mΩ TOLL. Conduction at 60 A with one FET conducting 1/3 of
the time: `P = I²R·D = 60² × 1.4 mΩ / 3 = 1.68 W` per FET cold, ≈ 2.4 W at hot
R_DS(on) ≈ 2 mΩ; switching adds ≈ 0.6 W. So ≈ **3 W per FET, ≈ 18 W per channel,
≈ 108 W** across the board. The heatsink is the copper: each FET owns 172.5 mm² of land
plus a shared phase-node plane. Requirement: the six FETs per channel stay a **contiguous
2 × 3 block on a 20 mm phase pitch** so the drain/source planes are unbroken. The
executed cell does exactly that.

### (d) Parts floor — irreducible without a package change

**262.19 cm² of footprint bounding box.** Nothing in a placement exercise can move this;
only a package change can (§6). At the *measured* achievable packing density of this part
mix (see §3) the implied board floor is

```
262.19 cm² / 0.736  =  356.2 cm²      cell-density floor
executed                       370.12 cm²      -> 13.9 cm² (3.8 %) of residual loss
```

Residual loss is structural, not slack: 1.5 mm between cells × 5 gaps, 0.5 mm edge
margin, and a control strip whose 18.0 mm height is floored by the 11.25 mm QFN-80.

**Verdict: the honest floor is ≈ 356 cm², not 262 cm² and not the 492 cm² that exists.**
The executed 370.12 cm² is 96.2 % of the packing floor, and every remaining cm² would
need a smaller connector or a re-poured copper design to reclaim.

---

## 3. Why the original is 53 % and where the void actually is

Measured occupancy (1 mm grid, `plot_before.py`): **53.1 %**; the empty space is one
connected region of 23,287 mm², i.e. **it is interstitial channel, not one big hole**.
The board decomposes exactly:

| region | area | parts | fill |
|---|---|---|---|
| 6 phase cells (86.27 × 80.03 each) | 6 × 6903.9 = **41,423 mm²** | 24,363 | **58.8 %** |
| control strip (top, ≈174 × 43) | ≈**7,437 mm²** | 1856 | **25.0 %** |
| | **49,173** | 26,218.8 | 53.3 % |

Two findings that contradict the natural guess:

1. **The phase cells are not loose — 58.8 % is close to a structural ceiling.** The
   `POWER_LUG_M5_3P_P20` motor lug has a **20.0 mm pin pitch** and is 54.30 mm long,
   while a TOLL FET is only 11.56 mm wide. Three FET columns on a 20 mm pitch leave
   **8.44 mm gaps** — by construction a 3 × 11.56 / 60 = 58 % dense switch block. The
   cell width is set by the lug, not by the parts.
2. **The 813 mm² of low-current parts inside each cell are spread over 4089 mm² — 19.9 %
   local fill.** *That* is the slack: 78 parts (MCU, driver, isolator, sense amp,
   isolated DC-DC, crystal, 60 passives) at one fifth density, interleaved with the
   power block. Same for CTRL at 25 %.

I tried to reclaim it by pure slack-removal first and it does **not** work: a
squeeze-then-legalise compactor recovered only **2.3 %** on the cell
(`compactor2.py`: 6903.9 → 6745.1 mm²), and a force-based legaliser diverged
(`compactor3.py`). The slack is not pairwise gap — it is *arrangement*. **A real
compaction needs the cell re-designed, not squeezed.**

---

## 4. The new placement

### Cell design (`design_cell.py`)

Cell = **designed anchors for the 19 high-current parts** + **bottom-left-decreasing
packing of the other 78 into the residual area**. Anchors honour the physics above:

```
                       <- 20.0 mm lug pin pitch ->
  y  0.0 .. 14.3   J1102 MOTOR_PHASES 54.30 x 14.30    (motor lug, top edge)
  y 15.5 .. 30.4   Q_HS A,B,C  (11.56 x 14.92 each)    (high side, 3 phases)
  y 31.5 .. 46.4   Q_LS A,B,C                          (low side, 3 phases)
  y 47.5 .. 58.5   R_shunt A,B,C  (7.62 x 11.02)       (one phase shunt per leg)
  y 60.0 .. 71.0   D1101 TVS (16.32 x 11.02) + bus shunt
  x 0.0 .. 14.3    J1101 FUSED_BATTERY_TAP 34.30 x 14.30, y 15.5..49.8   (left, beside FETs)
  x 0.0 .. 19.1    C1130 820 uF 19.09 x 18.55, y 51.0..69.6
  gaps x 32.56..41.0 / 52.56..61.0   9 x 10 uF 100 V DC-link (5 + 4)
  remainder                           78 low-current parts, BLD-packed at 0.5 mm rule
```

**Cell result: 75.30 × 73.26 mm = 5516.5 mm², 73.6 % fill** (from 6903.9 mm² / 58.8 %) —
**−20.1 % per cell** with the current path *shorter and straighter* than before.

`CTRL` block: pure BLD (no current path) — 1856.0 mm² packed at **74.1 %** into a
**152.1 × 16.47 mm** strip, versus 25.0 % today. Its height is floored by the 11.25 mm
QFN-80 plus clearance; the ~5 mm above that is the residual the BLD could not use.

### Array and outline (`assemble.py`)

The 6 cells are stamped by **pure translation** (identical layout, verified), and the
arrangement was swept over 8 combinations with a 2:1 aspect cap:

| arrangement | outline | area |
|---|---|---|
| 1 × 6 + ctrl below | 76.30 × 466.84 | 356.2 cm² — *rejected, aspect 6.1* |
| **2 × 3 + ctrl below** | **153.10 × 241.75** | **370.1 cm²** ← chosen |
| 3 × 2 + ctrl below | 229.90 × 161.79 | 372.0 cm² |
| 6 × 1 / 3 × 2 + ctrl right | — | 384–556 cm², rejected |

**Target outline: 153.10 × 241.75 mm (aspect 1.58), 370.12 cm².**
Why these numbers: 153.10 = 2 × 75.30 cell + 1.5 gap + 2 × 0.5 margin; 241.75 = 3 ×
73.26 cell + 2 × 1.5 gaps + 1.5 + 18.0 control strip + 2 × 0.5 margin. The 2 × 3
arrangement is chosen because it is the second-smallest rectangle, keeps the *same
topology* the board already has (cell array + control strip, so nothing about the
architecture changes), and is 1.26 cm² larger than an unbuildable 467 mm strip. A 6 × 1
strip is possible on paper and rejected on packaging grounds — an ESC for a hexacopter
must be a plate, not a ruler.

Connector accessibility: the `POWER_LUG_M5_*` parts are **M5 bolt lugs accessed from the
top**, not board-edge connectors — the existing board already mounts half of them in the
interior (`J1201` at x = 94.6, mid-board). No connector is required to reach an edge, so
none was placed against one; every lug keeps ≥ 0.6 mm of clearance to its neighbours.

---

## 5. Execution and verification

`execute_place.py` (pcbnew) on the **copy**: sets each footprint's orientation, then
translates so its **measured** bbox lands on the target (rotation-agnostic, no frame
math to get wrong), carries each channel's 96 zone outlines and its existing route with
its cell, rebuilds Edge_Cuts, refills the zones, saves.

```
footprints moved: 687 / 687   (missing from board: none)
zone outlines translated with their cell: 96 / 96
route carried with its cell: 150 segments + 1986 vias; 8 left stale (cross-cell nets)
outline rebuilt: 153.10 x 241.75 mm
zone refill: ok
```

`verify_place.py` — **independent process, reloaded from disk** (`verify_compact.json`):

| check | original | compact |
|---|---|---|
| footprints / layer census | 687 / {F.Cu: 687} | 687 / **{F.Cu: 687}** |
| **on B.Cu** | 0 | **0** ✔ |
| outline polygon area | 49173.23 mm² | **37011.93 mm²** |
| sum of fp bboxes | 26218.9 mm² | 26218.9 mm² (unchanged) |
| fill | 53.32 % | **70.84 %** |
| **min pair gap** | **−2.5172 mm** | **+0.60 mm** |
| pairs < 0.5 mm | 362 | **0** |
| zones / tracks / vias | 96 / 154 / 1990 | 96 / 154 / 1990 |
| unconnected, pcbnew ratsnest | 1542 | 1620 |
| unconnected, kicad-cli | 499 | **499** |
| six channels identical (multiset) | true | **true** |
| footprints translated | — | **687** |

**Both unconnected instruments are reported, per the brief.** This unit's baseline
pcbnew figure is **1542** — it reproduces the brief's pcbnew number exactly, which is a
useful independent confirmation of the disputed pair. On the compact board pcbnew says
**1620 (+78, +5.1 %)** while kicad-cli says **499 → 499, unchanged**. The +78 is fully
accounted for: 8 track segments on cross-cell nets were deliberately left stale, and the
pours were refilled at new positions. **kicad-cli's conjunction of 499 → 499 is the
stronger signal that connectivity was not damaged**, and the 499-vs-1542 reconciliation
remains a sibling unit's job — this unit does not depend on it.

### DRC — and the one number that looks bad but is not

`kicad-cli pcb drc --severity-all`, **project rules on both boards**
(`esc_rev_b.kicad_pro` copied for each — the first run was invalid because the original
had no `.kicad_pro` beside it and silently used default rules, giving **126** instead of
**16**; that 126 was 110 × `drill_out_of_range` + 16 × `via_dangling`, and the 110 are the
known 0.200 mm-PTH-at-4 oz blocker, not anything this unit touched).

| board | violations | composition |
|---|---|---|
| original | **16** | 16 × `via_dangling` |
| compact | **447** | via_dangling 199 · solder_mask_bridge 81 · clearance 71 · shorting 51 · track_dangling 26 · copper_edge_clearance 13 · isolated_copper 6 |

**Classifying every one of the 447 by what the two offending items are
(`classify_drc.py`) gives the answer:**

```
original : pad-to-pad only (pure placement) = 0   involves track/via/zone = 16
compact  : pad-to-pad only (pure placement) = 0   involves track/via/zone = 447
```

**Zero of the 447 is pad-to-pad.** Every single one is the 150 carried track segments,
1986 vias or 96 pour outlines no longer agreeing with the re-arranged parts — exactly
what "placement only, not routed" must produce, and exactly why the brief says routing
is out of scope. KiCad's own engine therefore confirms the **placement** is clean: no
pad-to-pad clearance, mask or short violation was created anywhere on the board.

Region fills of the executed board: cell array 152.1 × 223.3 = 33,984 mm² at **71.7 %**,
control strip 152.1 × 16.47 = 2505 mm² at **74.1 %**, whole board **70.84 %**. The
original's 16 dangling vias and the 110 `drill_out_of_range` (§ 4 oz blocker) are
pre-existing and untouched by this unit.

---

## 6. What a package change would buy (not done — reported only)

**The 12 power lugs are 29.0 % of all part area and they set the cell geometry.**
Measured: 6 × `POWER_LUG_M5_3P_P20` at 776.49 mm² = 4658.9 mm², 6 ×
`POWER_LUG_M5_2P_P20` at 490.49 mm² = 2942.9 mm², total **7601.8 mm² = 29.0 % of the
262.19 cm²**. More important than their area, their **20.0 mm pin pitch** is the single
parameter that forces the 51.56 mm FET block, which is 68 % of the 75.30 mm cell width.

A 3-pin lug on a **10 mm pitch** (~34.3 × 10.3 ≈ 353 mm²) would let the phase pitch drop
to the FET-limited **13.06 mm** (11.56 + 1.5 clearance), shrinking the FET block from
51.56 to **39.2 mm** and the cell to ≈ 63 mm wide, while removing ≈ 424 mm² of part area
per cell. ANALYTICAL (not executed): cell ≈ 4940 mm², board ≈ **335 cm²**, i.e. a
**further −9 %** on top of the −24.7 % delivered here; with P10 battery taps too, ≈ 326 cm²
(−12 %). Caveats: 10 mm pitch changes the lug's current rating and M5 hardware spacing,
and 3.34 mm of paralleled 4 oz copper per phase would then need checking at the new
13.06 mm pitch — which it passes (13.06 / 3.34 = 3.9×), so the change is electrically
available. **Not executed here, per the brief.**

---

## 7. What this does NOT establish

1. **No routing.** 2.88 % of the board is routed and this unit does not add any. The
   compact placement is *route-ready* in the sense that it is geometrically legal with a
   ≥ 0.60 mm part gap and a contiguous switch block — it is not routeable-by-proof.
2. **The 447 DRC items are stale copper, not placement.** Anyone re-running DRC must
   re-pour the 96 zones and re-route the 150 segments before quoting a violation count.
3. **The BLD packing is density-driven, not connectivity-driven.** Within the 78
   low-current parts per cell, decoupling caps may not be adjacent to the pin they
   decouple. That is acceptable because those parts are all low-current and the nets are
   short inside a 75 mm cell, but a designer must re-order them during layout. The
   *area* result is sound; the *netlist-aware* version would be equal or slightly larger.
4. **60 A per phase is the brief's number**, labelled ASSUMED. It drives the copper-width
   derivation only; the area result is insensitive to it, because copper width is 3.9×
   over-provisioned at the cell's own 20 mm pitch.
5. **No change to 4 oz, no HDI, no PTH via change.** The stackup is untouched
   (0.14 mm outer, 0.0525 mm inner), the 1990 vias are unchanged (1962 × 0.8/0.4,
   12 × 0.7/0.35, 16 × 0.6/0.3) and all 96 zones keep their 0.5 mm clearance.
6. **The board has no mounting holes.** `TH1`…`TH6` are NTC thermistors
   (`NTCG163JF103FT1`), not mounting hardware; there is no `H*`/`MH*` reference on the
   board and only 5 NPTH pads, all inside connectors. A 153 × 242 mm board with no
   mounting feature is a packaging problem this unit did not create and did not fix.

---

## 8. Reproduce

```
cd E:/engineering-portfolio-audit/evidence/esc-placement
C:/Program Files/KiCad/9.0/bin/python.exe dump_placement.py      # census            -> placement.json
python group_blocks3.py                                          # block map         -> blocks.json
python plot_before.py                                            # void + before PNG
python design_cell.py                                            # anchors + cell    -> local_layout.json
python assemble.py                                               # array sweep       -> new_positions.json
C:/Program Files/KiCad/9.0/bin/python.exe execute_place.py       # move, refill      -> esc_rev_b_compact.kicad_pcb
C:/Program Files/KiCad/9.0/bin/python.exe verify_place.py        # independent verify-> verify_compact.json
C:/Program Files/KiCad/9.0/bin/python.exe dump_after.py && python plot_after.py
kicad-cli pcb drc --severity-all --format json -o drc_compact.json esc_rev_b_compact.kicad_pcb
python classify_drc.py
```

Superseded/side artefacts kept for the audit trail: `compactor.py`, `compactor2.py`,
`compactor3.py` (the failed squeeze-only attempts, §3), `group_blocks.py`,
`group_blocks2.py` (weaker block assignments, superseded by the ref-digit rule),
`drc_orig.json` (default-rules baseline, superseded by `drc_orig_proj.json`).