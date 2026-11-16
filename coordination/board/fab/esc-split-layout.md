# ESC split architecture -> actual board files (power + control)

**Status: complete for the assigned scope.** Two KiCad 9.0.7 board files exist, with explicit stackups,
real outlines, 321 footprints placed, rule sets written, and DRC run on both. **Neither board is routed,
has zones, or has a netlist** — that is stated in §7, not glossed over.

Inputs: `evidence/esc-stack-v2/`, `evidence/esc-pinsplit-v2/` (`pinmap.md`, `pinmap.json`),
`evidence/esc-sink-clearance/` (the 13.42 mm x-growth), and the source placement
`evidence/esc-sink-clearance/pwr_copy.kicad_pcb` (173 fps / 941 pads / unrouted / 138.35 x 122.55).

## 0. Method, provenance, and the one number I had to change

Every number below is either MEASURED (pcbnew 9.0.7 on the files in this directory, or `kicad-cli pcb
drc`) or quoted from the named upstream artefact. Nothing is carried over on trust.

| Item | Value | Provenance |
|---|---|---|
| power board outline | **151.77 x 122.55 mm** | `esc-sink-clearance` §2.3 (pick b'), applied and re-measured |
| power board stackup | **4-layer, 3 oz / 1.5 oz / 1.5 oz / 3 oz, 1.60 mm** | written into the board file, read back (§1) |
| control board outline | **107.00 x 60.00 mm** at (44.10,14.00)-(151.10,74.00) | see the set diff below |
| control board stackup | **2-layer, 1 oz, 1.60 mm** | written into the board file, read back |
| header | 3 x 2x20 on a 2.54 grid, x {133.27,135.81 / 139.36,141.90 / 145.45,147.99}, y 21.27..69.53 | `04_place_check.json` of `esc-sink-clearance`, reproduced and re-verified |
| 120 pins | 120 pads on each board, every pad netted from `pinmap.json` | §5 |
| DRC | power 528 / control 37, baseline 499 (set diffs in §4) | `kicad-cli pcb drc`, `drc_*.json` |

**Set diff on the control-board size — a forced correction, not a preference.**
The brief says 105 x 60 mm / 63.0 cm2. That is `esc-pinsplit-v2` §6, written *before* the sink-clearance
x-growth. `esc-sink-clearance` §2.3 requires **107 x 60 at x 44.10-151.10** because the header bank spans
x 132.00-150.27 and the board has to cover it: at 105 mm wide from x 44.10 the board would end at
149.10 and the H3 column (pins at 147.99, pad edge 2.93 mm further) would be hanging off the edge.
Measured in the file: the board is 107.00 x 60.00 = **64.20 cm2**, i.e. **+1.20 cm2 (+1.9 %)** on the
63.0 cm2 the brief quotes. I built the size the geometry requires and state the difference rather than
quoting the pre-growth number.

## 1. The two board files, their stackups and their outlines

| | power | control |
|---|---|---|
| file | `esc_power_board.kicad_pcb` | `esc_control_board.kicad_pcb` |
| project + rules | `.kicad_pro` + `.kicad_dru` (both written) | same |
| copper layers | **4** | **2** |
| stackup (read back from the file) | F.Cu 0.105 / prepreg 0.200 / In1.Cu 0.0525 / core 0.865 / In2.Cu 0.0525 / prepreg 0.200 / B.Cu 0.105 = **1.580 + 2 x 0.010 mask = 1.600 mm** | F.Cu 0.035 / core 1.510 / B.Cu 0.035 = **1.580 + 2 x 0.010 = 1.600 mm** |
| copper weight | **3 oz outer (105 um), 1.5 oz inner (52.5 um)** | **1 oz (35 um)** |
| outline | 151.77 x 122.55 at (0,0), 4 clean segments | 107.00 x 60.00 at (44.10,14.00) |
| single-sided | 0 footprints on B.Cu, 0 B.Cu-only pads | 0 footprints on B.Cu, 0 B.Cu-only pads |
| vias / tracks / zones | 0 / 0 / 0 | 0 / 0 / 0 |
| footprints / pads | **173 / 1581** | **148 / 768** |

The power board is the source placement with three changes: the outline grew +13.42 mm in x (138.35 ->
151.77), the three busbar lands were **trimmed from a right edge of 135.30 to 130.50** (the
`esc-sink-clearance` decision; untrimmed they physically overlap the H1/H2 pin columns and DRC reported
5 `shorting_items` on BATN|SWCLK and BATN|SWDIO), and the 30 generic `cell_part` placeholders were
replaced by real parts (§2). The 36 FETs, 18 leg shunts, 6 bus capacitors, 18 motor lands, 3 busbar
lands, 6 phase connectors and 2 mounting holes are untouched.

Both stackups are explicit `(stackup ...)` blocks in the board files; neither inherits a default.
`05_setup.py` writes them, `10_verify_constraints.py` reads them back (table above).

## 2. Power board placement

**What is placed:** 36 x `IPTC014N10NM5` (unchanged, one device per switch position, 6 cells x 3 phases
x 2), **18 leg shunts** (unchanged 0.5 mOhm 4-terminal), **2 shared-bus shunts** added (RS1 on the BAR1
bus line, RS2 on BAR3), **6 x DRV8353 gate stages** (QFN-48 7x7, at the six 7x7 placeholder slots),
**19 front-end amplifiers** (18 x INA296A2 in SOT-23-8, one per leg shunt, + 1 bus amplifier U40 at the
shared-bus shunt), 6 bus capacitors, 18 motor lands, 3 busbar lands, 6 phase connectors, 3 x 2x20 header.

**Shunt count, honest set diff:** the brief says 24. The pre-split board carries 24 = 6 cells x (3 leg
+ 1 DC-input) (`esc-current-place` §2). The split's **shared bus deletes the six per-cell DC-input feeds**,
so 6 DC-input shunts collapse to the 2 bus channels the pin map keeps (`BUS_I_A`, `BUS_I_B`). Placed:
**18 leg + 2 bus = 20**. The four that disappear are the six cell feeds minus the two shared-bus
channels — deleted by the bus merge that also deletes 24 blocks and cuts 207 nets to 77, not by me.
The board of record has no bus-shunt footprint at all; RS1/RS2 are copy-geometry instances of its own
0.5 mOhm 4-terminal shunt, placed on the bus-bar line at (140.00, 5.00) and (140.00, 81.00), both
0.00 mm past the land end and outside the header bank's y band.

**Gate loop achieved: 89.6 mm mean, 54.6 mm best cell, 158.6 mm worst single loop.** Placement-level,
straight-line, loop = 2 x (nearest DRV8353 pad to the FET gate pad) because the return runs the same
channel; unrouted, so the etch is this plus bends.

| cell | driver | gate-loop mean | gate-loop max |
|---|---:|---:|---:|
| M1 | U11 (6.00,44.00) | 54.6 mm | 80.6 mm |
| M2 | U12 (83.00,97.50) | 137.9 mm | 154.5 mm |
| M3 | U13 (100.50,97.50) | 140.1 mm | 158.6 mm |
| M4 | U14 (17.00,97.50) | 69.9 mm | 90.2 mm |
| M5 | U15 (60.50,97.50) | 69.7 mm | 89.8 mm |
| M6 | U16 (114.00,97.50) | 65.5 mm | 81.2 mm |

**This is a finding, not a choice.** The search was exhaustive: every 0.5 mm lattice site on the board,
scored by distance to that cell's gate-pad box. The FET field has **no legal 8.25 x 8.25 mm site**: the
only free gaps inside it are **1.10-1.20 mm** (between a low-side FET's gate/source pad row and its
shunt, and between the shunt and the CB copper pad), and the two 7.80 mm corridors
(x 43.58-51.38, 86.68-94.48) that `esc-sink-clearance` identified are **occupied by the six 2x12 phase
connectors J1-J6**. Hence the drivers sit in the only free band, y >= 93, and the lower cells' gates are
55-140 mm away. A 5 mm gate loop is not available on this outline; it needs a FET-field re-pitch, which
is outside this task. The *split* still adds 0 mm to the loop — the driver stays on the power board, as
the settled architecture requires — but the loop the board actually has is 89.6 mm mean, and that number
now exists in a file instead of in prose.

**Amplifiers: 15 of 18 within the 3 mm target, 1 at 7.32 mm, 2 at 39.53 mm.** The metric is pad-box edge
to pad-box edge; 0.00 means the boxes are adjacent, and the DRC set diff (§4) proves every new pad is
still >= 0.25 mm from every other pad. The three misses are R3C (7.32 mm) and R6B/R6C (39.53 mm each):
the board's right end has no free 4.10 x 2.95 courtyard nearer those shunts. As with the gate loop, a
hard 3.00 mm everywhere is not reachable on this placement: a leg shunt is boxed in by 1.15 mm above
(FET gate pad), 1.15 mm below (CB copper), and 2.3 mm in x (neighbouring phase column).

**Header columns at the sink's end, 1.50 mm — with the three distances stated.** Pins at x 133.27..147.99.
Distance to the sink's right edge (130.50): **pin centre 2.77 mm, pad edge 1.92 mm, moulding edge
1.50 mm, courtyard edge 1.00 mm.** The 1.50 mm requirement is met on the physical moulding. The
courtyard is 1.00 mm because the KiCad 2x20 courtyard is drawn 1.77 mm on the pin-1 side (5.08 body +
0.25 margin) and the pin map fixes pin 1 at 133.27; the 0.50 mm difference is the courtyard's own
placement margin, not an object. This is the same 1.50 the sink-clearance wave verified, restated at the
precision the real library footprint gives.

## 3. Control board placement

148 footprints / 768 pads. Blocks: **U1 RP2354B** (QFN-80 10x10 P0.4) with Y1 12 MHz, Y2 40 MHz,
U4 W25Q128 boot flash and 16 x 0402 decoupling; **BEC** (2 x U5/U6 LM5164 + L1/L2 33 uH 7.3 mm +
U7 AP2112K-3.3 + D1 SMBJ58A + 4 bulk caps); **USB-C** J1 (HRO TYPE-C-31-M-12) + D2 USBLC6-2SC6;
**SWD** J2 1x05; **WWDT** U8 TPS3430; **CAN-FD** U10 MCP2518FD + U9 TCAN3413 + FL1 choke + D3 PESD1CAN;
**calibration/glue** U11 REF5030, U12 CAT24C32, U13 SN74LVC1G08; **3 x 16-bit simultaneous ADC**
U14/U15/U16 (TQFP-64); **31 analogue channels** as 31 x (2 x 1k + 1 nF) 0402 = 93 parts; **3 x 2x20
socket** J_H1/H2/H3 per the pin map; 3 standoffs.

Each block occupies a declared region with the real courtyard used for packing (not the pad box), and
the packer refuses to overflow: the 0402 references are hidden where 93 parts sit at 0.3 mm gaps.

## 4. DRC — totals, set diffs, and the footprint / copper / parameter split

Run as `kicad-cli pcb drc --format json --severity-all`, with each board's own project + `.kicad_dru`.
To separate inherited from new I also ran the **source placement with the same rule set**
(`baseline_pwr_src.*`, a copy of `pwr_copy`).

| | violations | file-bound (footprint) | copper | parameter | unconnected |
|---|---:|---:|---:|---:|---:|
| baseline (source placement, 0.25 mm rules) | **499** | 0 | 499 | 0 | **146** |
| **power board** | **528** | 29 | 499 | 0 | **187** |
| **control board** | **37** | 23 | 14 | 0 | **41** |

**Set diff, power board minus the source placement (the only honest way to read 528):**

| type | baseline | power file | delta |
|---|---:|---:|---:|
| clearance | 499 | 499 | **+0** |
| silk_over_copper (warning) | 0 | 29 | +29 |
| unconnected | 146 | 187 | **+41** |

So **placement added zero copper violations**: every pad and part I placed is at least 0.25 mm clear, and
the entire 499 is inherited from the unrouted source placement, whose *library land patterns* have
0.15 mm pad-to-pad gaps (SOT-23-8 at 0.65 mm pitch, the TOLL FET). +29 is silkscreen clipped by mask on
the new parts (cosmetic, warnings), and +41 unconnected is exactly the two header return nets:
DGND 24 pads -> 23 items, AGND 19 pads -> 18 items. 146 + 41 = 187, closing the account.

**Classification the programme uses:**

- **footprint-bound** — 29 (power) / 23 (control): silkscreen and the 2 courtyard overlaps on the control
  board between J_H1/J_H2 and J_H2/J_H3, which is the `esc-sink-clearance` residual made concrete: at
  6.09 mm pitch the mouldings are 1.01 mm apart but the KiCad courtyard is 6.10 mm wide, so adjacent
  header courtyards overlap by **0.01 mm**. Nothing moved; the 1.01 mm moulding gap is real.
- **copper-bound** — 499 (power, all inherited) / 14 (control): 10 clearance + 4 solder-mask bridges, and
  **every one of the control board's 14 is inside a single library land pattern** (USB-C A12/B1 and the
  SOT-23-8 array) — i.e. pad-to-pad gaps below the rule, not a placement error.
- **parameter-bound** — 0 by my classification, but there is a real parameter finding underneath the 499:
  a **0.25 mm clearance rule is incompatible with 0.5-0.65 mm-pitch packages**, which is exactly what a
  3 oz (105 um) outer layer allows. The published Eurocircuits row for 105 um is
  OTT-OTP-OPP 0.250 / OTW 0.250 — the same row the original 4 oz board used as its floor. So the power
  board as specified (3 oz outer, HDI-free) cannot hold the DRV8353 VQFN-48 (0.5 mm pitch) or the
  SOT-23-8 amplifiers without an explicit land-pattern exemption, and even exempted, a 0.15 mm pad gap
  is below what 105 um copper etches. **This is the one thing in this deliverable that needs a decision
  above me**: either 2 oz outer (0.200 mm class) or a fine-pitch keepout for U11-U16/U20-U40.

**Unconnected, quoted from pcbnew, not from the tool's cap.** kicad-cli lists 187 and 41; neither board
reaches the 499 list cap, so no truncation applies. `CONNECTIVITY_DATA.GetUnconnectedCount()` is not
bindeable in this pcbnew build (it needs an argument), so the counts above are the full item lists plus
the net census: power 42 nets with more than one pad (BATP 164, BATN 37, DGND 24, AGND 19, ...), control
3 (DGND 24, AGND 19, plus the pin-map nets at one pad each). Every unconnected item is a ratsnest line
waiting for copper that this deliverable does not include.

## 5. Placement constraint checks

| check | power | control |
|---|---|---|
| components on B.Cu | **0** (0 B.Cu-only pads) | **0** (0 B.Cu-only pads) |
| blind / buried vias | **0 vias of any kind** — vacuously satisfied, and the rule set forbids microvias | same |
| header pin count / positions vs pin map | 120 pads, 3 footprints, nets assigned from `pinmap.json` | 120 pads, 3 footprints, same nets |
| sink rectangle unobstructed | see below | n/a |
| envelope | 151.77 x 122.55 plan | 107.00 x 60.00, **inside** the power board's plan |

**Pin-for-pin, measured on both files.** y is exact on all 120 pins (21.27..69.53, 20 rows, 2.54 pitch).
x: the **60 odd pins coincide exactly**; the **60 even pins are 5.08 mm apart**, because
`PinSocket_2x20_P2.54mm_Vertical` draws pin 2 at **-2.54** where the male header draws it at **+2.54**.
That is deliberate in the KiCad library: the socket is meant to be **flipped to the far side**, where the
flip mirrors x and pin 2 lands at +2.54 — a perfect mate. **The pin map is therefore correct on both
boards, but the pair as built does not mate**, because the brief's "single-sided, 0 components on B.Cu"
puts the sockets on the same side as the male posts. Flipping the three sockets to B.Cu makes every pin
coincide and puts the socket moulding below the control board exactly as the 55.80 mm stack assumes.
**Recommendation: accept 3 footprints (120 pins) on the control board's B side, or the header pair must
change part numbers.** This is the only place where the brief's constraints are mutually exclusive.

**Sink rectangle (x 5.50-130.50, y 7.00-81.00):** 1013 pads inside, of which **120 are through-hole and
0 of those belong to a new part**. The 120 are the six phase connectors J1-J6 (24+24+24+24+12+12), i.e.
the board of record already puts 120 PTH tails inside the sink footprint. **That is a pre-existing
mechanical conflict the sink-clearance wave never checked** (it verified only the new header bank's
tails, which end 1.41 mm above the contact face). New SMD pads inside the footprint: 115, all on F.Cu,
above the board, which does not intrude on the sink. **Recommendation: pocket the sink under J1-J6 or
trim those tails** — placement-level, the sink is clear of everything I added.

**Envelope 151.77 x 122.55 x 55.80 mm.** Plan: measured on both files (the power board is the plan; the
control board sits inside it, 44.05-151.15 x 13.95-74.05 incl. the edge line). Height: **not re-derived**
— the 55.80 mm is `esc-stack-v2`'s stack and my placement does not touch it: the tallest part I added on
the power board is the 2.54 mm header moulding, and on the control board the 6.35 mm socket, both already
inside the 21.80 mm above-the-contact-face budget. No new part has a 3-D model, so a true z-envelope
would be a lie; what is verified is that no new part consumes any of the budget the stack had not
already counted.

## 6. Areas and the reduction claim

| | area |
|---|---:|
| power board, outline centreline 151.77 x 122.55 | **185.99 cm2** |
| control board, 107.00 x 60.00 | **64.20 cm2** |
| **pair total** | **250.19 cm2** |
| incumbent single ESC board | 382.71 cm2 |
| **reduction** | **34.62 %** |

(Edge-bbox measurement including the 0.10 mm outline stroke: 186.27 + 64.37 = 250.64 cm2 = 34.51 %.)

**Does the 18-34 % claim hold? It holds only at the very top of the band, and the -39 % that
`esc-pinsplit-v2` §6 published does not.** At 232.7 cm2 the pinsplit's -39 % used the 169.7 cm2 power
board, before the +13.42 mm x-growth and before the control board had to become 107 mm. On the real
files: **-34.62 %**, inside 18-34 % by 0.6 points and 4.2 points worse than the published -39 %. The
honest sentence is "**-34.6 %, not -39 %**"; the 13.42 mm x-growth (16.44 cm2) and the 1.2 cm2 control
board are where the difference went.

## 7. What is done, what remains

**Done and verifiable in this directory:** two board files that open in KiCad 9.0.7; explicit 3 oz /
1.5 oz / 1.5 oz / 3 oz 4-layer and 1 oz 2-layer stackups; measured outlines; 321 footprints placed with
per-part net assignment on the interface; rule sets (project + custom `.kicad_dru`) written and used;
DRC run with the inherited baseline separated by set diff; five placement constraints checked on the
files; areas re-derived and the reduction claim corrected down.

**Not done, and this is a placed / DRC'd / unrouted pair, nothing more:**
1. **No routing.** 0 tracks, 0 vias, 0 zones on both boards. The 187 and 41 unconnected items are the
   ratsnest of an unrouted placement.
2. **No netlist.** Only the 120 header pads carry nets, from `pinmap.json`. The new parts carry none,
   because the split boards have no schematic and inventing pin-net maps would be fabrication.
3. **No thermal plane, no copper pour, no power plane.** The 3 oz outer layer is a stackup declaration;
   none of it is drawn.
4. **Gate loop at 89.6 mm mean / 158.6 mm worst is a real problem**, not a rounding error. It needs the
   FET-field re-pitch that this scope excluded.
5. **The header pair does not mate in a single-sided build** (§5). One decision: flip the sockets to
   B.Cu, or change the header part pair.
6. **The 3 oz / fine-pitch conflict** (§4): 0.25 mm pattern class vs 0.5-0.65 mm pitches. Needs 2 oz
   outer or a documented keepout.
7. **120 pre-existing through-hole tails inside the sink footprint** (§5): pocket or trim.
8. The 18-34 % claim survives at 34.6 %; the -39 % figure should be retired.

## Files

```
esc_power_board.kicad_pcb / .kicad_pro / .kicad_dru     the 4-layer power board
esc_control_board.kicad_pcb / .kicad_pro / .kicad_dru   the 2-layer control board
baseline_pwr_src.kicad_pcb / .kicad_pro / .kicad_dru    the source placement, same rules (DRC baseline)
drc_power.json  drc_control.json  drc_baseline_src.json raw kicad-cli DRC, --severity-all
01_probe.py 01b_probe_power.py 04_probe_free.py         census and the free-space probe
02_build_power.py 03_build_control.py 05_setup.py 08_fix_pass.py   the build path
06_drc_analyse.py 07_drc_items.py 09_final_numbers.py 10_verify_constraints.py  the measurement path
02_build_power.json 03_build_control.json 06_drc_summary.json 09_final_numbers.json 10_verify.json
```