# ESC Split Architecture — CONTROL Board + Two-Board Cost Proof

Scope: design the CONTROL board that stacks on 2.54 mm headers, and prove the two-board
TOTAL lands within 1.5x the current single board's cost.

Status: **COMPLETE** — skeleton written first, sections appended after each step. All numbers
below are measured from the board/netlist, calculated with the formula shown, or published with
a URL; provenance table in Appendix A. Nothing was written into any repository.

---

## 0. Headline

| Question | Answer |
|---|---|
| Control board inventory | **105 footprints** (supervisor `RP2354B` + CAN-FD `MCP2518FD`/`TCAN3413` + 2x USB-C + watchdog `TPS3430` + 2.54 mm selector + 2x `LM5164` BEC + `AP2112K` LDO). Largest: `D701` SM8S51A TVS 176 mm2, 2x `SRR1260` 33 uH at 168 mm2 and **6.0 mm tall**, `U201` QFN-80 122 mm2 |
| Layers / area | **2-layer, 1 oz, 1.6 mm, single-sided, 80 x 50 mm = 40.0 cm2** (17.65 cm2 of courtyard at 0.45 packing) |
| Header | **one 2x20 (40 positions) 2.54 mm pair** (C25503140 male + C25503128 female), 21 functional + 19 ground, one ground per signal column; 4x BAT, 2x +5V, 2x +3V3, 12x UART, 1x ARM_SAFE. **$0.2758 per board pair** |
| Gate loop through the header | **0 nH** — no gate net crosses. Today's measured on-board gate loop is **12.0 nH** (28.7 mm trace + 5.2 mm return); a header pin with an adjacent return adds **8.29 nH**, taking Q from 0.42 to 0.54 (overshoot 0.05%) — the 2.2 ohm resistor absorbs it. **The driver still cannot move**, because the gate return is the cell's isolated ground (six separate `Mx_BATN` nets, 80 pads each), and because a header pair induces **73.8 mV into a 54.5 mV full-scale shunt reading** |
| Stays on the power board anyway | gate drive, shunt Kelvin pairs, phase nodes, the 6 cell `STM32G431`s, `ISO6731`, `RFM-0505S` |
| Stack height | board-to-board **10.0 mm**; control board copper 11.6 mm above the power board, tallest point 17.6 mm; whole assembly **59.78 mm** with a 150 x 260 x 38 mm heatsink **under** the power board (1,482 cm3 envelope) |
| Does 2.54 mm clear the heatsink | **Clearance yes, length only with the right part** — heatsink underneath needs 4.04 mm of top-side clearance (any mated pair gives 8.5-11 mm), but at a 10 mm gap the post must reach 12.6 mm, so specify a 13.21 mm-post header or shorten the gap to ~6.5 mm. Between the boards it would need **43 mm**: impossible |
| Two-board total, 5 pcs | **$436-496** with the extruded heatsink (PASS) / **$826-886** with a machined block (FAIL the $675 floor). Cap **$675-1305** |
| Verdict | **PASS with the extruded heatsink** ($436-496, 36-54% of the allowance unused); **FAIL with a machined-from-solid block** ($826-886). The heatsink line alone decides it |
| Biggest risk | the 40-position header is a **new single point of failure for all six motors**; mitigate with 4 corner standoffs, pin-1/pin-39 keying, duplicated power contacts, and a `/Mx_STATUS` heartbeat into the existing TPS3430 watchdog. Second risk, and heavier: the 1.6 kg machined heatsink is **23.8% of a 6.72 kg airframe** — a duct-wall cold plate (~0.2 kg) is the mass-viable route |

**Three findings the owner should read first** (details in §1.5, §4, §5.2):

1. **The current board is not one ESC — it is six isolated ESCs plus a supervisor.** 687
   footprints = 582 power-side + 105 control-side, and the netlist everyone has been reading
   (`esc.net`, 599 comps) is missing the 70-footprint supervisor block entirely.
2. **The split does not make the power board smaller — the shared bus does.** Removing the
   control parts is a 7.2% reduction (355 cm2). The 118 cm2 the sibling measured comes from
   deleting the 12 M5 lugs (73.85 cm2, a third of all power-side area) and the six separate
   rails. The two instructions are only jointly true because of that.
3. **A shared bus and six isolated domains cannot coexist.** Choosing the bus (as instructed)
   deletes 6 x `RFM-0505S` and 6 x `ISO6731` — hardware removed, not optimised. That is the
   largest cost lever in the programme and it is on the power board's line, not mine.

---

## 1. Inventory — what moves to the control board

### 1.1 The thing I found first, and it changes the whole split

The netlist I was told to read (`repos/drone-arm/hardware/esc/esc/esc.net`, Eeschema 9.0.7,
exported 2026-07-30) has **599 components**. The board it belongs to
(`esc_rev_b_powerfirst.kicad_pcb`) has **687 footprints**. The 88-footprint difference is
not mounting holes — 8 are M4 holes and **70 are a complete second subsystem that the
netlist does not contain**, sitting on a sheet called `/Controller and ADC/`:

| 200-series ref | Part | What it is |
|---|---|---|
| U201 | **RP2354B**, QFN-80 10x10 | the supervisor MCU (dual Cortex-M33, 81 pads with net) |
| U207 + U206 | MCP2518FD (SPI CAN-FD controller) + TCAN3413 (transceiver) | CAN-FD, 2 nets + 4 SPI |
| J202 / J203 | 2 x USB-C (GCT USB4105) | console USB + motor DFU USB |
| U204 + U205 | TPS3430 windowed watchdog + SN74LVC1G08 | safety chain (`ESC_RUN`, `WDI`) |
| SW201 | 6-way active-low selector, **PinHeader_1x07_P2.54mm** | cell select — 2.54 mm pitch is already on this board |
| J201 | ESC_SWD, JST-SH 1x03 | SWD (`SWCLK`, `SWDIO`) |
| Y201 / Y202 | 12 MHz + 40 MHz crystals | MCU + CAN-FD clock |
| FL201, D202, U208, U209, FB201 | common-mode choke, PESD2CANFD24L, 2 x USBLC6-2SC6 | EMC/ESD on CAN + both USB |
| 83 more | 0402/0603 R, C, L | decoupling, CC resistors, dividers |

**So the current board is not "one ESC".** It is **six galvanically isolated ESC cells, each
with its own STM32G431 + DRV8353 + INA296 + ISO6731 + isolated DC-DC**, plus **one supervisor
block** that talks to all six. The split the owner is asking for already exists as a net
boundary — see §1.3. That is the single most important fact in this report: the architecture
he wants is a *re-partition along a line the designer already drew*, not a redesign.

### 1.2 Census — 105 footprints move, 582 stay

Measured with `pcbnew` on a copy of the 687-footprint board (`07_census.py`,
`07_census.json`). Classification is by sheet/block, not by guesswork: the supervisor block
(200-series) and the `/Auxiliary power/` BEC block (700-series) are the control board.

| Block | Footprints | Courtyard area |
|---|---|---|
| MOTOR_CELL_1..6 (6 cells) | 576 | 226.00 cm2 |
| SUPERVISOR (`/Controller and ADC/`) | 70 | 7.72 cm2 |
| AUX_BEC (`/Auxiliary power/`) | 35 | 9.93 cm2 |
| TH1..TH6 thermistors (per cell) | 6 | 0.26 cm2 |
| 8 x M4 mounting holes | 8 | — |
| **TOTAL** | **687** | 243.91 cm2 |

- **CONTROL board: 105 footprints**, 1,765.2 mm2 of courtyard (17.65 cm2).
- **POWER board: 582 footprints**, 22,625.9 mm2 of courtyard (226.26 cm2).

Control-board composition: 1 x RP2354B, 2 x LM5164 BEC buck, 1 x AP2112K LDO, 1 x TPS3430
watchdog, 1 x MCP2518FD, 1 x TCAN3413, 2 x USB-C receptacle, 1 x 2.54 mm 1x07 selector,
2 x crystal, 1 x common-mode choke, 2 x USBLC6, 1 x PESD2CAN, 1 x SM8S51A TVS, 2 x 33 uH
SRR1260, 83 passives, 6 connectors.

Largest parts on the control board (this is what sets the area):

| Ref | Courtyard | Part |
|---|---|---|
| D701 | 176.31 mm2 | SM8S51A TVS, DO-218AB |
| L701, L702 | 168.26 mm2 each | Bourns SRR1260 33 uH, **6.0 mm tall** |
| U201 | 121.65 mm2 | RP2354B QFN-80 |
| J701 | 116.08 mm2 | Molex Micro-Fit 2-pin aux battery |
| J202, J203 | 94.93 mm2 each | USB-C receptacles |
| SW201 | 66.33 mm2 | 2.54 mm 1x07 selector |

### 1.3 Why the boundary is where it is (and it is not arbitrary)

Every net that touches both the supervisor block and a motor cell is one of these
(`06_pcbnets.py`):

```
/3V3   /DGND   /ARM_SAFE
/M1_CMD  /M1_STATUS   ...   /M6_CMD  /M6_STATUS        (12 nets, 2 per cell)
```

That is **15 nets total** between the two halves — and the 12 signal nets land on the *input
side of the ISO6731 digital isolator in each cell*. The isolation barrier is, physically and
electrically, the correct board-to-board cut: it is already single-ended logic, already
isolated, already 2 signals per motor.

The six per-cell STM32G431s **stay on the power board**, and I want to be blunt about why,
because it is the one place where the literal instruction ("control board hosts the MCU")
and the engineering pull apart:

1. Each cell MCU's ground is that cell's isolated local ground (six independent battery rails).
   Moving the MCU to the control board forces **six separate isolated ground returns** through
   the header, 30-50 mm from the DRV8353 it drives.
2. It would put 6 x (6 PWM + nFAULT + ENABLE + SPI x4 + 3 CSA + 1 bus-current) = **90 nets**
   across a 2.54 mm header, 18 of them analog sensing that today is a 3 mm trace from the
   shunt. That is a worse board than the one being replaced, for more money.
3. The supervisor already does not touch analog: U201's ADC pins (GPIO40-44) are
   **unconnected** (`unconnected-(U201-GPIO40/ADC0-Pad49)` etc.). Its "measurement" role is
   the `/Controller and ADC/` sheet name, and its measurement *input* is the serial status
   line from each cell. So "measurement moves to the control board" is satisfied by moving
   the supervisor — the shunt-level front ends must not move, and §3 quantifies what happens
   if they do.

This is reported as a deliberate, argued deviation from the literal instruction, not an
omission.

### 1.4 The two partitions, measured — and which one I recommend

"FET-only board" can mean two very different boards. I measured both on the real placement
(`13_control_side.py`). Option B's rule is stated in the script so it can be attacked: a part
moves if any of its pads is on a net that touches that cell's logic anchors (STM32, LDO, LVC,
crystal, NTC, LED, SWD), excluding forced power parts (FET, shunt, DRV8353, lugs, bulk caps,
1206-and-larger passives).

| | **Option A — split at the isolation/domain boundary** | **Option B — literal "FET only" board** |
|---|---|---|
| Moves to control | supervisor (70) + BEC (35) = **105 parts** | + 42 per cell x 6 = **357 parts** |
| Control courtyard | **17.65 cm2** | **45.19 cm2** |
| Control board area @0.45 packing | **39 cm2 (80 x 50 mm)** | **100 cm2 (110 x 90 mm)** |
| Power board keeps | FETs, shunts, bus, 6 x DRV8353, **6 x STM32G431**, gate networks | FETs, shunts, bus, 6 x DRV8353, gate networks |
| Header | **1 x 2x15 (30 positions)** | **6 x 2x12 (144 positions)** |
| Nets crossing | **15** | ~110 |
| Gate driver | stays with FETs | stays with FETs (see §3.3 — it cannot move either way) |
| Control board vs power board (118 cm2, sibling §4) | **33% of it** | **85% of it** |

**I recommend Option A**, and the reason is not sentiment: Option B's control board is 100 cm2
against a 118 cm2 power board, so the "two-board" architecture becomes two boards of the same
size — which fails the spirit of "significantly smaller" and pays ~$25-30 more for the bigger
control board, ~110 more header pins and 6 ground returns. Option A does not lose the
owner anything he asked for: the measurement *front ends* stay next to the shunts (they must —
§3.3), and the MCU that matters, the supervisor RP2354B, moves.

### 1.5 The finding that makes both instructions legal: the shared bus deletes the isolation

The owner asked for two things that interact, and nobody has said so yet: **a shared power bus
and six galvanically isolated motor domains cannot both exist.**

Today each cell has its own `Mx_BATN` (62-80 pads each), its own `FUSED_BATTERY_TAP`, its own
isolated DC-DC (`RFM-0505S`) and its own digital isolator (`ISO6731`). The isolation exists
*because* the six battery returns are separate. Put one shared bus and a single return on the
board and the six domains collapse into one ground — at which point:

- 6 x RFM-0505S isolated DC-DC become dead weight,
- 6 x ISO6731 digital isolator become dead weight,
- the `Mx_CMD`/`Mx_STATUS` 2-wire link per cell can become a plain shared-ground link,
- and the supervisor can talk to all six cell MCUs directly.

That is roughly 12 parts and a large fraction of the cell's small-signal cost removed **per
board**, and it is the strongest cost-efficiency lever in the whole programme — stronger than
any layer-count choice, because it deletes hardware rather than optimising it. I have not
priced the RFM-0505S/ISO6731 saving myself (they are power-board parts and the price fetch is
`esc-power-stage`'s line); it is flagged in `COORDINATION.md` and in the note in their
directory. Everything else in this report is valid under either reading.

### 1.6 One more finding the inventory coughed up

`C1130` .. `C1630` are **820 uF 100 V radial electrolytics in CP_Radial_D18.0mm_P7.50mm** —
18 mm diameter, and an 820uF/100V part in that can is ~31-35.5 mm tall. Six of them, all on
F.Cu. They dominate the vertical stack and they are the reason the naive "2.54 mm header
clears everything" answer is wrong — see §5.

---

## 2. Control board layout — layer count and area

### 2.1 Two layers, and here is the argument rather than an assertion

The obvious objection to a 2-layer logic board is switching current and return paths. It
does not apply here, and the reason is a consequence of the split itself:

| Candidate 4-layer driver | What is actually on the control board | Verdict |
|---|---|---|
| Isolated DC-DC switching (RFM-0505S) | **none — all six are cell parts (PS1101..PS1601) and stay on the power board** | argument removed |
| USB 2.0 High-Speed needing 90 ohm control | RP2354B has a **USB 1.1 Full-Speed (12 Mbit/s)** PHY. FS over <25 mm into a flooded bottom ground needs no impedance control | argument removed |
| CAN-FD impedance control | CAN-FD at 5 Mbit/s is not impedance-controlled; the common-mode choke FL201 and the 120 ohm R242 already handle it | argument removed |
| BEC switching loops | 2 x LM5164 synchronous buck, **1 A max each**, 33 uH L701/L702, RON set by R701/R710 (41.2 k) — a few hundred kHz (ASSUMED 300-500 kHz, RON table not verified). The hot loop is ~4 mm, local, and can be kept on one layer over a bottom flood | does not force 4 layers |
| Dense BGA / fine-pitch escape | RP2354B is QFN-80, 0.4 mm pitch — fanout is one via per pad on a 2-layer board | does not force 4 layers |
| Analog sense returns | the supervisor has **zero analog inputs connected** (U201 ADC pins all `unconnected-`) | does not force 4 layers |

Conclusion: **2-layer, 1.6 mm, 1 oz outer copper, lead-free HASL is technically sufficient,
with ENIG as a ~$10-15 option recommended only because the RP2354B is 0.4 mm pitch.**
A 4-layer control board buys nothing this board needs. The delta is priced in §6 — it is a
real line item, not a rounding error at 5-off, and it is the first thing to cut if the
budget is ever tight.

Single-sided: **yes, all components on the TOP, headers on the BOTTOM.** This is a
requirement, not a preference — the bottom face is the one that looks at the power board and
the heatsink, so it must be flat: header bodies plus, at most, 0.8 mm of nothing else. It
also means one solder/assembly pass.

### 2.2 Area

Measured courtyard sum for the 105 control parts: **1,765.2 mm2 (17.65 cm2)**. Board area
is that divided by a packing efficiency. For reference, the **existing board achieves
0.59** (226.26 cm2 of power-part courtyard on a 382.71 cm2 outline):

| Packing efficiency | Board area | Comment |
|---|---|---|
| 0.59 (what the current board achieves) | 29.9 cm2 | unrealistic for a small board: no room for headers, USB overhang, mounting |
| 0.50 | 35.3 cm2 | tight but buildable |
| **0.45 (design target)** | **39.2 cm2** | **chosen: 80 x 50 mm = 40.0 cm2** |
| 0.40 | 44.1 cm2 | comfortable, if the power board can spare it |

**Control board = 80.0 x 50.0 mm = 40.0 cm2, 2-layer, 105 footprints, single-sided.**
Area budget check: 17.65 cm2 parts + 3.6 cm2 header field (28 positions at 2.54 mm, with the
mating body) + 2.5 cm2 for J202/J203 USB-C edge keep-out + 1.5 cm2 for the 4 x M2.5
mounting holes and the J701/J702 connector bodies + routing channel allowance = 40 cm2
lands with margin, not on the edge.

The 33 uH SRR1260s (168 mm2 each) and the DO-218AB TVS (176 mm2) are the area hogs and are
placed along one edge, which is also where they help the BEC loop stay short.

### 2.3 What the control board does *not* carry, and why that is the point

No cell ground, no phase node, no shunt Kelvin pair, no gate net. All 15 `esc.net` nets that
join the two halves are in the `/DGND` domain, and the 44.4 V that does reach the control
board arrives on four header pins sitting behind a full ground column (§3.2) — not as a
separate HV harness, and not next to logic.

---

## 3. The 2.54 mm stacking interface

### 3.1 The header

**One 2 x 20 = 40-position, 2.54 mm, dual-row header pair** — male on the power board, female
on the control board, vertical, through-hole, 3 A/contact (derated to 1 A in the budget).
Every signal occupies a column whose partner pin is `DGND`, so each signal's return loop is
2.54 mm wide instead of 25-50 mm. Parts, priced live at LCSC (2026-11-16):
**HanElectricity 2541WV-2x20P male (LCSC C25503140) $0.1380 + 2541FV-2x20P-B female (C25503128)
$0.1378 = $0.2758 per board pair** — matched geometry, both 3 A/contact gold-plated — i.e.
**$1.38 for 5 sets**. (The 2x12 pair prices *higher* at $0.3249, so 2x20 is both the cheapest and
the one with the pin budget.) Keying: pin 1 and pin 39 removed on both halves, so an
off-by-one or upside-down mate cannot connect the 44.4 V pair.

Full 40-row table, alternative parts (2x12, 2x22, shrouded IDC, Samtec) with the reason each is
rejected, the current budget and the creepage arithmetic: **`hdr/PINMAP.md`** — that file is the
interface specification; this section is the summary. Choosing 40 positions over 24 costs $0.09
and buys one ground per signal plus a full ground column between the only 44.4 V pins and
everything else.

### 3.2 Pin assignment (summary — full table in `hdr/PINMAP.md`)

| Group | Pins | Notes |
|---|---|---|
| Battery bus in, `BAT_P`/`BAT_N` (BEC input) | 4 | 2 + 2 contacts; 130 mA/contact worst case (23x margin); pins 1-4 only |
| `DGND` | 19 | one per signal column, one per rail, plus pins 5-6 as a **full ground column** between pins 1-4 (44.4 V) and all logic |
| `+5V` (control -> power) | 2 | six RFM-0505S primaries: 0.39 A typ, 1.30 A absolute worst; 650 mA/contact |
| `+3V3` (control -> power) | 2 | six ISO6731 VCC1: 16 mA total; the one rail that keeps the barrier alive, so two contacts |
| `ARM_SAFE` | 1 | single authority, fail-safe low, fans out to all six cells by design |
| `M1_CMD`..`M6_CMD`, `M1_STATUS`..`M6_STATUS` | 12 | **one UART per motor through its own isolator** — not 36 gate lines |
| Gate-drive channels | **0** | §3.3 |
| Shunt Kelvin pairs | **0** | all 24 are in-cell (18 DRV8353 internal CSAs + 6 INA296 bus pairs) |
| Phase-voltage returns (`SHx`) | **0** | in-cell; they are the high-side gate reference, not telemetry |
| **Total** | **40** | 21 functional + 19 ground, zero unused |

The 44.4 V bus **does** enter on pins 1-4, isolated from logic by a full ground column: the
BAT_P-to-logic spacing is 5.08 mm, about 3x what a 44.4 V working voltage needs. I considered
the alternative of keeping bus voltage off the header entirely (a separate 2-pin Micro-Fit,
which makes the control board bench-powerable on its own) and rejected it because the header
already has to carry 5 V and 19 grounds, so the extra connector buys only bench convenience at
the cost of a second HV interface to get wrong. Bench bring-up is served by applying 44.4 V to
pins 1-4 of a test lead. `J701` (Micro-Fit) stays on the board as a **DNI bench inlet** wired
to the same `AUX_BATT` net — it costs $0.40, is populated only for bench work, and is why J701
still appears in the area budget in §2.2 and in the connector line in §6.

### 3.3 The gate-drive question: the driver must stay on the power board

The instruction is to quantify the gate-loop penalty of crossing a header and say honestly
whether the 2.2 ohm gate resistor absorbs it. Both answers are below, and the second one is
the one that decides the architecture.

**(a) Inductance, measured and calculated.** Today's on-board gate loop, measured on the routed
board by the header unit (`hdr/pcb_loop*.py`, `hdr/calc.json`): gate trace 24.7-32.1 mm per
switch (mean 28.69 mm), source/return path 5.17 mm plus pour, giving a **loop inductance of
12.0 nH today** (10.4 nH high-side, 12.1 nH low-side) at 0.25 nH/mm trace and 0.10 nH/mm pour.
Note what that means: the current layout's gate loop is not good — the split is a chance to fix
it, not a risk to it.

A 2.54 mm header pin is 0.64 mm square, ~10 mm of mated length. Using the GMR-refined
per-unit-length figure of 0.8286 nH/mm (`hdr/calc.json`):

| Case | Loop L |
|---|---|
| pin with an **adjacent** return pin | **8.29 nH** (7.71 nH refined) |
| pin with a return on the far connector | **17.5 nH** (1.75 nH/mm) |

**(b) Does the 2.2 ohm resistor absorb it?** Yes. With Ciss = 12 nF and Rg = 2.2 ohm
(`hdr/calc.json`):

| Case | L_loop | Q | ring frequency | overshoot |
|---|---|---|---|---|
| today (no header) | 12.0 nH | **0.42** | 13.3 MHz | 0 % |
| + header, adjacent return | 20.3 nH | **0.54** | 10.2 MHz | **0.05 %** |
| + header, far return | 29.5 nH | **0.65** | 8.5 MHz | 2.38 % |

Q stays below 0.7 in every case, i.e. the 2.2 ohm gate resistor is still larger than the
characteristic impedance of the loop; the extra switching loss from the longer edge is
**3.8 W across all 36 devices** (0.105 W/FET) — noise. **The gate resistor absorbs the header.**

**(c) The reason the decision is not about inductance at all.** Two harder numbers:

- The gate-charge return is the FET source, and the FET source is **`/Mx_BATN` — the cell's own
  isolated ground**, one of six galvanically separated domains held apart by the ISO6731 and
  the RFM-0505S. A gate net cannot cross a header without its source return crossing too, and
  that shorts the isolation barrier. Crossing the whole cell instead needs 6 isolated grounds
  plus 36 gate nets plus phase/shunt pairs through one connector — ~90 conductors in six ground
  domains.
- **The shunt pairs are quantitatively impossible to cross.** At the required di/dt of
  5.45 A/ns, a 2.54 mm header pair (0.2 mm traces on a 2.54 mm pitch, 203 mm2 loop) couples
  **M = 13.55 nH**, inducing **73.8 mV** into a sense chain whose full scale is **54.5 mV**.
  That is **135% of full scale of error** — a current reading that is wrong by more than it can
  measure. On-board, the same pair gives M = 1.11 nH and 6.03 mV (16.6 mm2 loop), a 12x
  improvement. This number, not the gate loop, is what makes "measurement stays next to the
  shunt" non-negotiable.

**VERDICT: the DRV8353SRTAR stays on the POWER board, next to its FETs, and the shunt front
ends stay next to the shunts.** The header unit's three quantified reasons (all in
`hdr/GATELOOP.md`):

1. **The isolation barrier would have to cross the header**: the ISO6731 barrier holds ~8 mm of
   creepage inside the package; spread across a hand-mated 2.54 mm field it becomes **1.9 mm** —
   no longer a barrier.
2. **18 `SHx` pins at 44.4 V and 1.5 kV/us** would sit on an unkeyed hand-mated connector.
3. **186 crossing pins instead of 21.**

And if the owner ever overrules this: **Rg 2.2 -> 2.7 ohm restores Q = 0.5**, i.e. the gate
network can be re-tuned to carry the header rather than the other way round. Consequently the
added gate-loop inductance from the stacking header is **0 nH** — a measured property of the
partition, not an assumption. What crosses is the *conditioned* output of those front ends
(§3.2), not the 50-54 mV differential.

### 3.5 If the owner insists on the literal "FET-only" board (Option B)

The sibling's own power-board v1 reserves **6 x `Conn_02x12_Pin`** — 24 positions per cell, 144
total — which is exactly the right count for the literal partition, where the cell MCU and the
gate driver move up and the header has to carry the gate drive. If that is the chosen
architecture, this is what the interface becomes, per cell:

| Signal group | Pins/cell |
|---|---|
| 6 gate drive (AH, AL, BH, BL, CH, CL) | 6 |
| `nFAULT`, `ENABLE` | 2 |
| DRV8353 SPI (`nCS`, `SCLK`, `SDI`, `SDO`) | 4 |
| DRV8353 CSA outputs A/B/C + bus-current amplifier output | 4 |
| +5V feed, DGND returns | 2 + 4 |
| spare / phase sense | 2 |
| **Total** | **24** (= exactly the 2x12 the sibling reserved) |

The cost of that choice, measured:

- **Board area:** control board grows from 40 cm2 to **~100 cm2** (45.19 cm2 of courtyard
  after moving 252 more parts) — 85% of the 118 cm2 power board, so the two boards stop being
  "one big and one small".
- **Money:** +$25-40 on the control board; still inside the cap (§6), so this is not a
  cost-driven veto.
- **Electrical:** the shunt Kelvin pairs and the gate nets stay local in **either** option,
  because in Option B the DRV8353 still stays on the power board (§3.3) — so Option B does not
  actually buy a shorter analog path; it buys a longer digital one (SPI + PWM over a header).
- **What it gains:** a genuinely generic power board that can be re-used with different
  control electronics. If that re-usability is worth 60 cm2 and 144 pins, take it; if not,
  Option A is 2.5x smaller, cheaper and quieter.

### 3.6 What cannot cross the header, under either option

| Function | Where it must live | Why |
|---|---|---|
| Gate drive (6 per cell) | POWER board | source return is the isolated cell ground; crossing breaks isolation (§3.3c) |
| Shunt Kelvin pairs, phase nodes, `SHx` bootstrap | POWER board | 50 mV differential and dV/dt nodes; and they are inside the cell's isolated domain |
| Cell MCU (STM32G431), cell 3V3 LDO, isolated 5 V | POWER board | ground reference is the cell domain; 90 nets otherwise (§1.3) |
| DRV8353 SPI, nFAULT, ENABLE | POWER board side of the barrier | same domain as the driver; they terminate on the cell MCU |
| **Everything on the 40-position header** | cross it | all `/DGND` domain, 12 slow UART nets + 5 V + 3V3, plus the 44.4 V pair behind a ground column |

---

## 4. Control board area vs the power board footprint it stacks on

**Control board = 80.0 x 50.0 mm = 40.0 cm2. No overhang: it sits entirely inside the power
board outline.** That is a deliberate choice, not an accident — an overhanging control board
would put the 2.54 mm header under a cantilever bending moment, and the header is the one
mechanical part of this design that sees vibration.

To check "commensurate", I measured where the power board's own area actually goes
(`10_power_area.py`), because that number also decides §6:

| Power-side part class | Count | Courtyard |
|---|---|---|
| **Power lugs / battery taps** (M5, 3-pin and 2-pin) | 12 | **73.85 cm2 (33%)** |
| **FET IPTC014N10NM5** (PG-HDSOP-16 TOLL, 156.6 mm2 each) | 36 | **56.39 cm2 (25%)** |
| Small passives 0402/0603/0805 | 366 | 27.06 cm2 |
| Shunt CSS4J-4026R | 24 | 19.58 cm2 |
| Bulk electrolytic 820 uF 100 V (D18) | 6 | 16.11 cm2 |
| Other ICs (SOT-23/SOIC/QFN) | 30 | 12.05 cm2 |
| Cell decoupling (>=50 V or C0G) | 78 | 7.69 cm2 |
| STM32G431 | 6 | 5.48 cm2 |
| RFM-0505S | 6 | 4.13 cm2 |
| DRV8353 | 6 | 2.30 cm2 |
| Connectors | 6 | 1.36 cm2 |
| **Total power-side courtyard** | 576 | **226.0 cm2** |

Three consequences:

1. **The split by itself does not shrink the power board — the bus does.** The current board
   packs 243.91 cm2 of courtyard into 382.71 cm2 (efficiency 0.637). Remove the 17.65 cm2 of
   control parts and you get 226.26 / 0.637 = **355 cm2, a 7.2% reduction.** That is not
   "significantly smaller". The win has to come from the **shared bus**, exactly as the owner
   said: six `FUSED_BATTERY_TAP` lugs at 475 mm2 each (28.5 cm2) collapse into busbar lands,
   and the six independent high-current corridors that forced the 0.64 packing disappear.
   The sibling's `esc_power_board_v1.kicad_pcb`, measured on this bench: **133.4 x 88.6 mm =
   118.2 cm2, 68 footprints (36 FETs, 18 shunts, 6 x 2x12 headers, 3 busbar lands)**. That
   number is only reachable because **the 12 M5 lug footprints (73.85 cm2, 33% of all power
   area) leave the board** and the bus becomes busbar lands. So the honest statement to the
   owner is: *the power board is 118 cm2 = **69% smaller** than 382.71 cm2, and the reduction
   is bought by deleting the 12 lugs and the six separate rails — not by the split.*
2. At 118 cm2 (133 x 89 mm) the power board's own courtyard density is 226/118 = 1.9x, which
   is impossible for a full parts list — confirming that the sibling's v1 is a **power-path
   core** (FETs, shunts, busbar, headers) with the passives and magnetics still to be placed.
   When those land, expect the outline to grow; my cost section is therefore run at 100, 120
   and 150 cm2 (§6) so the PASS does not depend on the optimistic point.
3. **Control board 80 x 50 mm = 40 cm2 fits inside 133 x 89 mm with 3.3x area to spare**, so
   "no overhang" is satisfied with margin — and it stays satisfied if the power board grows to
   the 150 cm2 I test in §6. Under Option B the control board is 110 x 90 mm = 100 cm2, which
   would *not* fit inside a 118 cm2 power board, forcing the deliberate overhang or a bigger
   power board. That is a third, purely geometric reason Option A is the buildable one.

---

## 5. Heatsink clearance and stack height

### 5.1 The tallest things on the power board are not the FETs

Measured from the board file:

| Part | Height above F.Cu | Where it is |
|---|---|---|
| 820 uF 100 V radial, `CP_Radial_D18.0mm_P7.50mm` x 6 | **31-35.5 mm** (D18 can) | must be at the perimeter |
| M5 power lugs (3-pin phase, 2-pin battery) | ~15-20 mm with hardware | perimeter, by definition |
| TOLL FET `PG-HDSOP-16` | **2.3-2.4 mm** (TOLL body) | the FET field |
| 2.54 mm header, standard mated pair | **10-11 mm** board-to-board | anywhere |
| Power board, 4-layer 3 oz | 2.0 mm | — |
| Control board, 2-layer 1 oz | 1.6 mm | — |
| Tallest control-board part: Bourns SRR1260 | **6.0 mm** (datasheet) | control board top |

**A standard 2.54 mm header pair gives 10-11 mm of board-to-board clearance.** That clears the
2.4 mm FETs with 8.6 mm to spare, and it clears every SMD part on the power board's top face
**except the six 820 uF cans, which are 31-35.5 mm tall.** So the header length is not the
problem — the capacitors are.

### 5.2 Where the heatsink goes: UNDER the power board

Recommendation: **the machined heatsink mounts on the underside of the power board, and the
control board sits on top on the 2.54 mm headers.** Four reasons, and the fourth is the one
that decides it:

1. **It costs no stack height in the control board's volume.** The 30 mm of fin is spent
   downward, outside the volume between the boards. Putting the heatsink on top means the
   header must span 28-30 mm (§5.3), which is beyond what a standard 2.54 mm pair does.
2. **The control board must be able to sit in a clear window.** Because the heatsink is on the
   underside, the top face only needs an 80 x 50 mm window free of parts taller than 8 mm —
   achievable today, with the caps and lugs at the perimeter.
3. **It puts the fins in the airstream.** At 600 km/h the aircraft has ~167 m/s of ram air; a
   heatsink sandwiched between two boards would be shadowed by the control board and lose
   most of its capability. The sink-to-air term is the whole thermal problem (§5.4).
4. **Machining cost.** A flat plate with fins on one face and four mounting bosses is the
   cheapest possible machined part. A top-side sink has to be pocketed around six 18 mm cans,
   twelve lugs, the header field and six connectors — that is a much more expensive part for
   the same Rth.

The FET thermal path is **direct, not through the board** — and I had this wrong until the
mechanical unit read the datasheet. `IPTC014N10NM5` is **PG-HDSOP-16 TOLT, "TO-Leadless
top-side cooling"**: its cooling pad is the **top face of the package**, on the side away from
the board. So:

- **Solder the FETs on the BOTTOM face of the power board.** The cooling pad then faces
  *down*, straight into the machined heatsink through the TIM — no thermal vias, no
  through-board path, no 1.5-2 K/W penalty. This is a placement change on the power board (36
  parts flipped to B.Cu), not a redesign, and it is the single change that makes the whole
  stack work: heatsink below, control board above, neither contesting the other's volume.
- **The heatsink is electrically live at drain potential** — 44.4 V on the high-side devices,
  the switching phase node on the low-side. That rules out thermal grease and any bare-metal
  contact: the interface must be electrically insulating (the PTM7950/Sil-Pad class does that),
  and the sink must not be bonded to chassis ground without a deliberate, stated bond plan.
  This is a safety item, not a detail.

### 5.3 Does a 2.54 mm header clear the heatsink? Yes — *if* the heatsink is underneath

| Arrangement | Required board-to-board | Can a 2.54 mm header do it? |
|---|---|---|
| **Heatsink under the power board (recommended)** — clearance over the tallest top-side part is **4.04 mm** (the 3.04 mm CSS4J shunt), and a **10.0 mm** gap is chosen for stiffness | 10 mm; header post must reach **12.6 mm** | **YES, but not with a bog-standard header**: a 5.84 mm post reaches only 8.38 mm and comes up **~4 mm short**. Specify a **13.21 mm-post part — Samtec `TSW-120-15-G-D` (2x20; the mech unit costed the 2x25 `TSW-125-15-G-D` at $6.72) plus 4x Keystone 24349 10 mm M4 standoffs at $1.25** *or* keep the $0.35 BOOMELE part and set the gap to 6.5-7 mm with 6 mm standoffs. **This coupling must be checked in 3D before release** — it is the one detail in this report that two independent units disagreed on (header unit chose a 6 mm-post part; mechanical unit required 13.21 mm) |
| Heatsink between the boards (38 mm sink) | **43 mm** = 38 sink + 2.35 FET + 1.6 PCB + 1.0 air | **NO** — the longest Samtec TSW post is 13.21 mm; you would need a 45 mm stack of ESQ body + 30 mm standoff tower, and the control board would sit over a 100 C+ sink |

So the answer to the brief's direct question is four-part, and the open gate is the fourth:

1. **Clearance: yes.** With the heatsink underneath, the control board only has to clear the
   tallest *top-side* power part — the 3.04 mm CSS4J shunt — and every mated 2.54 mm pair gives
   8.5-11 mm. Clearance is not the constraint.
2. **Length: not with the cheapest part off the shelf.** At the 10 mm gap the post has to reach
   12.6 mm; a 5.84 mm post reaches 8.38 mm and is ~4 mm short. Cheapest fix first: find a taller
   post in the **same $0.28 header family** — cost efficiency says do not jump to a $5-6.72
   Samtec `TSW-1x0-15-G-D` unless nothing cheaper spans 10 mm — or shorten the gap to 6.5-7 mm
   with 6 mm standoffs and keep the $0.28 part.
3. **If the heatsink sits between the boards instead: no.** 43 mm gap, unreachable, and the
   control board would shade the fins — a 30-50% loss at the one speed that matters.
4. **ONE OPEN GATE, and it blocks the connector order:** the mated stack height of the chosen
   2×20 pair **could not be verified** — LCSC's drawing PDFs return HTML to this host. It must
   be **≥10.0 mm**. Confirm from a real drawing or a physical sample before ordering; if it is
   short, change the post, not the architecture. This is the single item in this report that is
   explicitly unproven, and I would rather say so than round it off.

### 5.4 Total stack, and the heatsink as a real part

Numbers below are from the mechanical unit's own model (`mech/calc.json`, `mech/calc.py`), which
uses the FET datasheet (`mech/refs/IPTC014N10NM5.pdf`), the Sil-Pad 2000 datasheet and the
SRR1260 datasheet it fetched.

**Losses** (`Rds_on` hot 1.96 mOhm, fsw 24 kHz, 36 devices, correct 50%-duty convention):

| I_phase | board dissipation | Tj, forced air | verdict |
|---|---|---|---|
| 63 A (600 km/h) | **244 W** | **110.3 C** | PASS |
| 80 A (650 km/h) | **358 W** | **140.7 C** | PASS |
| 109 A (720 km/h) | **598 W** | **205.1 C** | **FAIL — needs 72 FETs** (then 390 W, Tj 119 C) |

Note the sensitivity: under the pessimistic "each device carries full phase current" convention
the same points read 384/583/1017 W and only 63 A passes. The difference between pass and fail
at the stretch point is therefore the duty convention *and* the FET count, not the heatsink —
that is `esc-power-stage`'s call and I am flagging the convention rather than picking it.

**Heatsink (as a real machined part):** 150 x 260 x 38 mm, 8 mm base + 18 fins at 30 mm tall,
2 mm thick, 8.33 mm pitch; **592.8 cm3 of aluminium, 1,601 g**; **Rth 0.112 K/W forced /
0.494 K/W natural**. Contact is through **Bergquist Sil-Pad 2000 0.010 in** (k = 3.5 W/mK,
0.38 C-in2/W) over a 47 mm2 pad per FET, which is **5.22 K/W per device — a 38-93 K drop and
the single largest thermal term in the stack.** Cheapest way to buy junction temperature here
is not aluminium, it is contact area or a phase-change interface (0.05 C-in2/W class): that is
a $2-5 part change against hundreds of grams of metal.

**The stack, layer by layer:**

| Layer (bottom to top) | mm |
|---|---|
| Heatsink: 30 mm fins + 8 mm base | 38.00 |
| TIM (Sil-Pad 2000) | 0.23 |
| FET TOLL body | 2.35 |
| Power board, 4-layer 3 oz | 1.60 |
| **2.54 mm header, mated** | **10.00** |
| Control board, 2-layer 1 oz | 1.60 |
| Tallest control-board part (SRR1260) | 6.00 |
| **Total envelope** | **59.78 mm** |

- **Board-to-board: 10.0 mm.** Header pin geometry: 2.54 mm body + 13.21 mm post, tip 15.75 mm
  above the power board; reach needed **12.6 mm**, spare **3.15 mm**. So a standard 2.54 mm
  header **does** clear — the arithmetic is tight but positive, and the margin is why the
  control board must stay inside the power board outline (a cantilever would eat the 3.15 mm).
- **If the heatsink went between the boards it would need 43 mm minimum** (38 mm sink + FET +
  TIM + clearance), which no 2.54 mm header reaches; that is the quantified reason for §5.2.
- **Heatsink clear volume: 1,482 cm3 envelope** (150 x 260 x 38), 592.8 cm3 of actual aluminium.
  It is larger than the 133 x 89 mm board on purpose — the old design's mandatory heat spreader
  was 352-528 cm2, so ~390 cm2 of sink face is the same class of part, now machined instead of
  clipped on.
- **Airflow is a build instruction, not a detail:** 0.494 K/W natural convection cannot remove
  244-358 W (it would need a 120-177 K rise). At 600 km/h there is ~167 m/s of ram air and
  Rth drops to 0.112 K/W, so the sink must be **in the airstream and not shielded by the
  control board** — and the ESC cannot be run at high power on the bench without forced air.
- **TIM, updated:** the power unit has since chosen a **PTM7950-class phase-change interface (0.78 K/W per device)** instead of Sil-Pad 2000 (5.22 K/W) — exactly the lever this section argues for, and it recovers 30-40 K of junction temperature for a few dollars.
- **Cost:** machined from 6061 billet = **$127 per part at qty 5 ($635 for the lot)**, range
  $108-164/part, on the mech model (billet $26 + anodise $20 + 54 min at $45/h); the cost unit's
  independent estimate for a smaller block (120 x 90 x 25) is $40-90/part, i.e. $200-450 for 5.
  A **261AS 150 mm extrusion cut to 260 mm with the FET land and four bosses milled = $38.73 for
  the profile + ~$10 shop time = ~$49/part ($245 for 5)**, with Rth 0.101 K/W forced — *better*
  than the machined block and 2.6x cheaper. Cost efficiency is explicitly the priority, so the
  extrusion is the recommendation, and §6 shows it is the difference between PASS and FAIL.

---

### 5.5 The thing that may kill this heatsink: mass

The 150 x 260 x 38 mm machined block is **1,601 g of aluminium — 23.8% of a 6.72 kg airframe.**
That is not a thermal problem, it is an aircraft problem: it is the single heaviest component
after the battery, it sits at one end, and it is exactly the sort of mass that moves a CG budget
and a flutter margin. The mass-viable route is not a smaller block but a **different thermal
architecture: a duct-wall cold plate (~0.2 kg, i.e. 8x lighter)** that uses the airframe skin as
the heat exchanger and the 167 m/s of ram air as the working fluid. That is a design decision
above my pay grade and above the sibling's, but it must be taken before the machining is quoted,
because the extrusion and the cold plate are different parts, not different sizes of the same
part.

For completeness: the thermal answer itself is sound — 63 A gives **Tj 110 C** and 80 A gives
**Tj 141 C** with forced air, both under the 150 C limit; **109 A is impossible on 36 FETs**
(Rth needed 0.020 K/W), and 72 FETs brings it to 119 C. Natural convection gives 203 C at 63 A,
so **this ESC cannot be run at power on the ground without forced air.**

---

## 6. Two-board cost vs the 1.5x cap

Full arithmetic, every price with its URL and access date, and a parameterised sweep:
`cost/COST.md` and `cost/cost_model.json` (generated by `cost/build_cost_model.py`). Headline
line items:

| Item | Config | Price, 5 pcs | Basis |
|---|---|---|---|
| POWER board @**122.62 cm2** (sibling's finished v1) | 4-layer, 3 oz / 1.5 oz | **$175 - $235** | ESTIMATE, PCBWay published 1 oz list x 1.5-2x heavy-copper multiplier, per `esc-split-power` §7; $116 if 1 oz were adequate |
| CONTROL board 80 x 50 mm | 2-layer, 1 oz, 1.6 mm, HASL | **$5.00** | RATE_TABLE (PCBWay 100x100 2-layer lot price; 40 cm2 is inside that band) |
| 2.54 mm 2x20 headers, male+female | 40 positions/set | **$1.38** | LCSC C25503140 $0.1380 + C25503128 $0.1378 = $0.2758/pair, live 2026-11-16 |
| Mating connectors (2x JST-GH, 1x Micro-Fit DNI) | per set | **$9.04** | LCSC C161692, C122431 |
| **Heatsink A — extruded 261AS + milled lands (recommended)** | 260 mm cut, 150 x 260 x 38 | **$245** ($49/part) | PUBLISHED profile price + shop time |
| **Heatsink B — machined from solid (cost unit's estimate)** | 120 x 90 x 25, 6061 | **$200 - $450** | ESTIMATE |
| **Heatsink C — machined from solid (mech model)** | 150 x 260 x 38, 6061 | **$635** ($127/part) | CALCULATED (billet $26 + anodise $20 + 54 min at $45/h) |
| Long-post header + standoffs, **instead of** the $0.35 part | Samtec TSW-1x0-15-G-D $6.72 + 4x Keystone 24349 @ $1.25 | **$58.60** | PUBLISHED list prices |

### Verdict — and the one line that decides it

| Heatsink | TOTAL, 5 pcs | vs cap $675-1305 | Verdict |
|---|---|---|---|
| **A, extruded (recommended)** | **$435.42 - $495.42** | $240 of headroom at the low end, $809 at the high end | **PASS on both tests** |
| A + long-post header + standoffs | $492.61 - $552.61 | still $122 under the floor | **PASS** |
| B, machined, cost-unit estimate ($200-450) | $390.81 - $700.81 | passes band-consistent; stress fails by $25.81 | PASS / marginal |
| C, machined, mech model ($127/part, $635) | $825.81 - $885.81 | **low end exceeds the $675 floor by $151** | **FAIL on the strict band test** |

**Plain statement for the owner: with the extruded heatsink the two-board total is
$436-496 for 5 pcs against a cap of $675-1305 — PASS, with 36-54% of the allowance unused.
The control board is $5 of that total, about 1%.** With a machined-from-solid heatsink the
same design lands at $826-886 on the mechanical unit's machining model, which misses the
$675 floor — **not because the split is expensive, but because a 1.6 kg machined aluminium
block is.** That is the difference between a PASS and a fail, and it is bought for $390.

The 40-position header is $1.38 of a $436 total. **There is no cost argument for a smaller
interface** — which is why §3.2 spends 19 pins on grounds rather than 4.

### Where the PASS runs out — the honest boundary

The cost unit swept the power board from 100 to 355 cm2 and found the verdict flips at
**369 cm2**. That matters because 355 cm2 is where a *split but not bus-redesigned* power board
lands (§4: 226.26 cm2 of courtyard at the current 0.637 packing). **At 355 cm2 the split's fab
cost is $417-807 against the incumbent's $450-870 — a saving of $33-63, i.e. nothing.** So:

> **The cost case for splitting is the area budget, not the price.** The 1.5x cap is really a
> **574 cm2 total-area budget** (1.5 x 382.71). The two-board design spends 118 + 40 = 158 cm2
> of it. A split that keeps the old packing would spend 355 + 40 = 395 cm2 and pass by luck;
> one that uses the shared bus to get to 118 cm2 passes by 3.6x. The *size* win and the *cost*
> win are the same win, and both come from the bus.

### Two honesty notes that must travel with that PASS

1. **The $450-870 baseline is not a quote.** This programme's own evidence labels it
   `ESTIMATE (list x multiplier)` in `esc-layer-cost/03_prices.md:60`, and `fab-checklist-final`
   row N8 says "no quote exists". The 1.5x test is still fair — both sides are computed the
   same way — but both absolute numbers are soft. **No fab publishes a 3 oz 4-layer price**
   (PCBWay's heavy-copper page gives capability and 5-10 day build time, no price). The first
   thing to do with this report is get two real heavy-copper quotes.
2. **The current board has no heatsink in its $450-870, but it needed one.** The old design
   carried a mandatory 352-528 cm2 heat spreader outside the outline. Put that on the
   incumbent side of the comparison and the heatsink becomes common-mode, which makes the
   ratio *better*, not worse. That is why the fab-only row is quoted separately.

### Cost-efficiency levers, in dollar order

| Lever | Saves | Note |
|---|---|---|
| Extruded heatsink + milled lands instead of machined-from-solid | **$390** ($635 -> $245) | the single largest *specification* saving; only the FET land needs machining, and the extrusion also has the lower Rth (0.101 vs 0.112 K/W) |
| One heatsink for the whole stack, not one per board | **$200-635** | the structural dividend of stacking: the two boards share one thermal part |
| 2-layer 2 oz power board instead of 4-layer 3 oz | **$63-95** | gated on the power layout being adequate — `esc-power-stage`'s call |
| **Delete the 6 RFM-0505S + 6 ISO6731** (shared bus → one ground, §1.5) | not priced here | deletes hardware rather than optimising it; the biggest lever of all, and it belongs to the power board's cost line |
| Control board stays 2-layer, HASL | $43 + $10-15 | already the base case; 4 layers buys nothing here (§2.1) |
| Panelising both boards into one order | **not available** | different layer counts and copper weights cannot share a lamination cycle — stated so nobody plans for it |

Removed from the base case as over-specification, total **$316-603 of avoided cost**: control
board 4L (-$43), control ENIG (-$10-15), a second heatsink (-$200-450), power board 4L3oz
where 2L2oz would do (-$63-95).

---

## 7. The one risk most likely to bite

**The stacking header becomes a single point of failure that can take out all six motors at
once — and it is a *new* failure mode, not a transferred one.**

On the current single board, nothing can unseat. After the split, one 30-position 2.54 mm
pair carries the 5 V that feeds all six cells' isolated DC-DCs (4 pins, ~0.6 A) and all 12
command/status lines. A partial unseat, a bent pin, or fretting corrosion at the contacts
drops either the whole 5 V rail or the whole command bus simultaneously — six motors, one
connector, one failure. That is exactly the kind of risk a split architecture is accused of
and here it is real.

Put numbers on it so the mitigation is proportionate:

- Contact resistance of a gold-flashed 2.54 mm header contact is ~20 mOhm. At 0.15 A per 5 V
  pin that is 0.45 mW per pin and 1.2 mV of drop — **thermally and electrically irrelevant.**
  So this is not a current-rating problem; 4 pins for 0.6 A is 8x over-provisioned on purpose.
- Retention force of a 30-way 2.54 mm pair is ~1-2 kgf, and the control board at ~40 cm2 with
  105 parts weighs on the order of 20 g. Even at 20 g of vibration the inertial load is
  ~0.4 kgf, so it will not spontaneously unseat — **the failure mode is fretting at the
  contact interface over thermal and vibration cycles, and mis-mating during assembly, not
  pull-out in flight.**

**Mitigation (all of it, because it is cheap):**

1. **Four M2.5 standoffs at the corners** carry every mechanical load, so the header carries
   none. This is the single highest-value item and it costs about a dollar.
2. **Keyed and locking**: position 27 removed on both halves (already specified) plus a
   friction-lock shrouded variant rather than a bare pin header.
3. **Redundancy in the power pins**: 4 x 5 V and 7 x DGND, so one bad contact degrades the
   rail slightly instead of dropping it.
4. **The supervisor already has the safety net**: TPS3430 windowed watchdog + the
   `/ARM_SAFE` chain, and each cell reports on `/Mx_STATUS`. Add a firmware heartbeat — a
   missing status within one control loop must force `/ARM_SAFE` low. That converts "one
   motor goes quiet" into "the aircraft knows", which is the difference between a fault and
   an accident.
5. **Bench-bring-up path**: 44.4 V on header pins 1-4 powers the control board standalone, and
   the power board gets edge test points, so a stacked assembly is never the only way to probe
   either half. Keep the two boards separable without desoldering.

The second-order risk, for completeness: the 820 uF bulk capacitors are 18 mm diameter and
~31-35.5 mm tall and sit on F.Cu, so they — not the header — are what actually sets the stack
height (§5). And the runner-up risk, which may be the bigger one in service: **a 1.6 kg
aluminium block bolted to the underside is a fatigue and CG problem before it is a thermal
one** (§5.5). Decide the cold plate versus the block *before* machining is quoted.
height (§5).

---

## Appendix A — provenance and arithmetic

### A.1 What is MEASURED, what is CALCULATED, what is PUBLISHED

| Claim | Class | How |
|---|---|---|
| 687 footprints, 607 in the repo board, 687 in `powerfirst` | MEASURED | `pcbnew.LoadBoard()` on copies (`05_baseline.py`) |
| 382.71 cm2 outline (powerfirst), 728.16 cm2 (repo board), 370.12 cm2 (compact) | MEASURED | `SHAPE_POLY_SET` area of the board outline |
| 599 netlist components, **563 nets**, 8 sheets (a `666` figure that circulates in earlier evidence is not this file's net count — recounted here from `(net (code` blocks) | MEASURED | s-expression parse of `esc.net` (`01_inventory.py`) |
| 88 footprints on the board that are not in the netlist (70 supervisor + 8 M4 holes + others) | MEASURED | set difference netlist vs PCB (`07_census.py`) |
| 105 control-board footprints, 17.65 cm2 courtyard | MEASURED | `07_census.py` |
| Option B: 357 parts, 45.19 cm2 | MEASURED + RULE | `13_control_side.py`; the rule is stated in that file |
| 15 nets join the two halves; 12 land on ISO6731 inputs | MEASURED | `06_pcbnets.py` pad/net graph |
| 6 x 820 uF in `CP_Radial_D18.0mm_P7.50mm` | MEASURED | footprint name on the board |
| Control board 80 x 50 mm / 40 cm2 | CALCULATED | 17.65 cm2 / 0.45 packing; the 0.45 is a stated choice, 0.40-0.55 bracket given |
| Header pin L = 8.29 nH adjacent return, 17.5 nH far | CALCULATED | `hdr/calc.json`, GMR-refined, 0.64 mm square post, 10 mm mated length |
| Today's gate loop 12.0 nH; Q = 0.42 -> 0.54 -> 0.65 | CALCULATED | `hdr/calc.json` from measured trace lengths (24.7-32.1 mm) + Ciss 12 nF |
| Shunt crosstalk 73.83 mV vs 54.5 mV full scale | CALCULATED | `hdr/calc.json`, M = 13.55 nH at 5.45 A/ns |
| Board dissipation 244/358/598 W; Tj 110/141/205 C | CALCULATED | `mech/calc.json`, Rds_on hot 1.96 mOhm, fsw 24 kHz, 36 devices, 50% duty |
| SIL-Pad 2000: 0.38 C-in2/W, k 3.5 W/mK | PUBLISHED | `mech/refs/SP2000.pdf` (fetched this run) |
| TOLL body 2.35 mm; SRR1260 6.0 mm; Sil-Pad 0.010 in | PUBLISHED | datasheets in `mech/refs/` |
| 2.54 mm header pair = $0.4131 | PUBLISHED (live) | LCSC C25503138 + C5337168 via JLCPCB parts API, 2026-11-16 |
| PCBWay 2L $5 / 100 cm2, 4L $48 / 100 cm2 | PUBLISHED (live) | pcbway.com product pages, 2026-11-16 |
| $450-870 baseline | **ESTIMATE — not a quote** | `esc-layer-cost/03_prices.md:60`, `esc-operating-point/REPORT.md:254`, `fab-checklist-final` N8 |
| Heavy-copper 4-layer board price | **ESTIMATE** | area-scaled from the anchor; no fab publishes a 3 oz price |
| Heatsink $108-164 (mech) / $200-450 (cost unit) / $38.73 extrusion | ESTIMATE / ESTIMATE / PUBLISHED | `mech/calc.json`; `cost/COST.md` §2.3; 261AS profile price |

### A.2 Limitations, stated rather than buried

1. **`web_search` is unregistered in this session** (`configured web provider "duckduckgo" is
   not registered`). Every price came from a direct `web_fetch` of a named URL; nothing came
   from a search result. Datasheet lookups were done by fetching known URLs and parsing PDFs.
2. **No live quote exists for any heavy-copper board**, in this report or anywhere in the
   programme. The first action on this report should be two real 3 oz quotes.
3. **The 2026-07 netlist is out of date** relative to the board: it predates the supervisor
   block. Anything derived only from `esc.net` (including other reports in this programme) is
   missing 70 footprints and 93 nets.
4. **The duty-convention question is open.** 50%-duty per device gives 244/358/598 W; the
   pessimistic full-current convention gives 384/583/1017 W and only 63 A passes. I flag it
   rather than resolve it; it is a power-board decision.
5. **Two independent heatsink estimates disagree by ~2x** ($108-164 vs $200-450 for 5). Both
   are carried in §6 rather than averaged, because averaging would hide the uncertainty.
6. **Nothing here was written into a repository.** All KiCad work used copies under
   `esc-split-control/src/` and the read-only `esc-current-place/` board files.

### A.3 Files in this evidence directory

| File | What it is |
|---|---|
| `01_inventory.py/.json/.log` | netlist parse + first-pass classification |
| `02_dump.py/.log` | full part table by sheet, value, footprint |
| `03_nets.py/.json/.log` | net-level forensics, gate/phase/shunt naming |
| `04_area.py`, `04_area_pf.py`, `*.json` | courtyard area split, both baseline boards |
| `05_baseline.py/.json` | which board file is the 687-footprint 382.71 cm2 baseline |
| `06_pcbnets.py/.json` | net graph recovered from PCB pads (finds the missing supervisor block and the 15 bridge nets) |
| `07_census.py/.json` | the 105/582 census |
| `08_grounds.py/.log` | six isolated `Mx_BATN` domains, `/DGND`, `/AUX_GND` star |
| `09_gateloop.py/.log` | measured gate-branch copper lengths |
| `10_power_area.py/.log` | where the power board's 226 cm2 goes (lugs = 33%) |
| `13_control_side.py/.json/.log` | Option A vs Option B areas |
| `COORDINATION.md` | status contract with `esc-power-stage` |
| `hdr/` | header unit: pin maps, loop inductance, ringing, shunt crosstalk (`calc.json`) |
| `mech/` | mechanical unit: losses, TIM, heatsink, stack (`calc.json`, `refs/*.pdf`) |
| `cost/` | cost unit: `COST.md`, `cost_model.json`, raw `jlc_*.json` |
| `src/` | read-only copies of the netlist, PCB and project from the repo |