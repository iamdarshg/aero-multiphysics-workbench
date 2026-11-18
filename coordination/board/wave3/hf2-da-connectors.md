# hf2-da-connectors — can J60–J66 be avoided / shrunk / left alone?

**Unit:** hotfix wave 2, drone-arm ESC PWM connectors.
**Reads:** `AGENT_BOARD.md` (pinned), `evidence/w2-da-connectors/REPORT.md`, `evidence/w2-da-gerbers/`.
**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`, 140.150 × 100.150 mm edge bbox,
1.6 mm, 4 copper layers, 165 footprints, 176 nets, 341 vias. Read-only; nothing committed.
**Owner steer applied:** fab burden free, design effort minimised → part swaps and constraint edits
first, copper moves second, stackup last.

---

## 0. Answer

| question | answer |
|---|---|
| **NO_NEW_FOOTPRINT possible?** | **NO.** 0 test points on 165 footprints; no connector carries ≥3 free signal pins; castellation is 49.48 mm from an edge and still crosses the same pinch (§2) |
| **FINE_PITCH part / free area** | 0.5 mm 14-way FFC (7 sig + 7 gnd) fits **11.00 × 5.85 mm at x 65.65–76.65, y 56.15–62.00**; but pitch is the wrong lever — the blocker is 0.6 mm of corridor at the MCU, not the field (§3) |
| **CHANNEL_COUNT / 7th** | **7**, the **fin rudder** (D3/B). 8 if F-10(a) two-rudder is ever taken (§5) |
| **Does the connector move?** | **No.** The fan-out goes on **B.Cu**, not F.Cu: as-built F.Cu 0 / B.Cu 4 lanes at 0.30 mm; re-home one trace + 0.13/0.10 rules → **8 lanes for 7 nets** (§4) |
| **What still needs copper** | 7 × ~0.5 mm F.Cu stubs → 7 vias (0.30/0.10, a size already on this board) → 7 B.Cu runs to J60–J66 pin 3, unchanged at y = 82.04; plus one trace re-home (§6) |
| **Board impact** | no part move, no new footprint, no stackup change, **no plane cut** (all new copper is on outer layers) |

---

## 1. What was actually measured, and how

The wave-2 verifier reported "0 free lanes at pads 43–49". Its method (`w2-da-connectors/escape_layer2.py`)
rasterised at **0.25 mm** and then blocked a further **0.25 mm around every object** — `PAD = 0.25`
applied to pads, courtyards, tracks *and* vias (its lines 6, 16–24, 30–33, 56–57). That imposes an
effective separation of ≥ 0.50 mm plus ±0.25 mm quantisation, i.e. ~3.3× coarser than a 0.1 mm
process. So the number needed re-deriving before any design decision rested on it.

Re-measured here at **0.01 mm**, exact obstacle sizes, no halo (`capacity.py`, `levers.py`), with two
corrections to the naive approach:

- **pads block only the layers they are on** (SMD pad → its own layer; THT → every copper layer).
  Marking every pad on both outer layers falsely blocks B.Cu with F.Cu 0402 pads and hides the whole
  back-layer answer. Fixed mid-run; v1 numbers (`single_lever.out`, first block) are superseded.
- **a "lane" is not a free run.** A 2.8 mm free run is 9 traces at 0.30 mm pitch, not 1. Capacity is
  reported as `Σ floor(run / (width + clearance))`.
- **vias are obstacles**; copper zones are treated as reflowable pours, not obstacles (that is what a
  pour does), and no inner-layer copper is touched at all.
- footprints' courtyards are *not* blocked: the U10 own-fan-out area belongs to U10, and a courtyard
  is not copper.

Metric: **capacity** = how many traces fit across a vertical cut through the pads' own band
(y 50.40–53.20, the 7 pads at 0.40 mm pitch), minimised over x 64.40–68.95 at 0.05 mm steps.
Need 7.

```
case                          | w0.15 c0.15 (0.30) | w0.13 c0.10 (0.25)
                              | F.Cu            B.Cu | F.Cu            B.Cu
as built                      |  0 @65.65      4 @64.70 |  2 @65.65      5 @64.90
L1 via 0.700 -> 0.450         |  0             4        |  2             6
L2 /RF_GPIO2 re-homed         |  0             6        |  2             8
L1+L2                         |  0             6        |  2             8
L1+L2+L3 C36 moved            |  2 @65.40      6        |  4 @65.40      8
```
(`levers.out`. Number is the minimum lanes; `x` is where the minimum occurs.)

**So the verifier is right and the board is right about F.Cu**: at 0.30 mm pitch the F.Cu band carries
**zero** traces. The wave-2 conclusion is robust to a 25× finer raster. What it misses is that the
**same band on B.Cu already carries 4**, and 8 after one trace moves.

### 1.1 Where the pinch is, item by item

Only three things sit in the corridor x 64.4–66.5 within the pads' own band:

| item | geometry | layer |
|---|---|---|
| **C36**, 0402 decoupling cap (2 pads 0.56 × 0.62, `/GND` + `/3V3`) | x 65.19–65.81, y 51.24–51.80 and 52.20–52.76 | F.Cu |
| its two fan-out diagonals (`/GND` 65.50,51.52→66.10,52.12 and `/3V3` 64.58,53.80→65.50,52.88) | w 0.25 | F.Cu |
| **one via**, `/GNSS_PWR_EN`, dia **0.700** / drill 0.350 at (64.95, 50.81) | x 64.60–65.30 | both |
| **`/RF_GPIO2`**, one straight trace (62.90,52.60)→(75.60,52.60), w 0.20 | crosses the whole band | B.Cu |

That is the entire defect: **one 0402, its two 0.25 mm stubs, one oversized via, one straight trace.**
The wave-2 report's §4.1 step 1 ("open a 7-trace channel through x 64.4–66.5 by rerouting the F.Cu
traces currently crossing there") describes the same objects but on the wrong layer.

---

## 2. NO_NEW_FOOTPRINT — measured, and the answer is no

Inventory on `main_rev_b.kicad_pcb` (`pinch.out`):

| option | measured | verdict |
|---|---|---|
| test points | **0** footprints of 165 carry `TestPoint` in the FPID or a `TP` ref | none exist |
| unused connector pins with a netable signal | `J1` USB-C 22 pads → **2** free, `A8`/`B8` = SBU1/SBU2 (the other 2 free are shield `''`). `J2` CAN 1x04 → 4/4 used (free = 2 mounting). `J10` SWD 1x03 → 3/3 used. `J30`/`J40` U.FL → 0 free | **max 2 free signal pins**, need 6–7 |
| castellation / edge finger | U10 at (59.00, 50.00), **50.08 mm** from the nearest edge; pad 49 (PWM_ESC7) at (63.95, 50.60) is **49.48 mm** from the nearest edge. The nearest usable free field is ~15 mm away (`w2` §2.2) | **worse on both axes** — 49 mm of 7-trace run instead of 15, and it must still cross the x 65.2–65.85 pinch, which is 1.3 mm from the pad tips |

So there is no existing feature that can carry the outputs, and an edge finger is strictly more copper
than the header row it would replace. **No.**

Note the footprint count is not this unit's choice anyway: `J60`–`J65` are netlist-mandated — the
schematic instantiates six `Conn_01x03` symbols (`mcu.kicad_sch:4607–4688` and siblings), and the
parity defect is that the board lacks the footprints. What is open is **which part**, not *whether*.

---

## 3. Fine pitch — fits easily, fixes nothing

Measured free rectangle in the window immediately SE of U10 (`blocks.out`, 0.05 mm max-rect over
pads + tracks + vias, F.Cu):

```
best 11.00 x 5.85 mm = 64.4 mm2 at x 65.65..76.65  y 56.15..62.00
```

Board-wide the field is not scarce at all: `w2-da-connectors` §2.2 measured **43.4 % = 6103 mm²** free
and a largest free rect of **53.25 × 21.25 mm** at x 77.67–130.93, y 74.67–95.92.

A 0.5 mm-pitch 7-way FFC ZIF needs ~8 × 4 mm; a 14-way ~10.5 × 4 mm. Both fit the 11.00 × 5.85 mm
rect with room. **Fine pitch is therefore not the constraint, and adopting it does not fix the defect**,
because every option — 2.54 mm header, 1.0 mm JST-SH, 0.5 mm FFC, edge finger — has to pass the same
**0.6 mm-wide pinch at x 65.2–65.85** (F.Cu) / **x 64.6–65.3** (B.Cu), which is 0.65–1.8 mm from the
pad tips and entirely upstream of the connector. Pitch changes the destination, not the source.

What fine pitch *would* buy if the routing is redone anyway: the wave-2 fan-out needs 17.78 × 7.62 mm
of field for seven 2.54 mm headers; seven 1.0 mm JST-SH (`SM03B-SRSS-TB`, **the part already at J10**)
need 7 × 1.0 = 7.0 mm width, and one 0.5 mm 14-way FFC needs one part ~10.5 mm wide. Copper saved,
defect unchanged.

---

## 4. The fix that needs no part and no connector move

Keep `J60`–`J66` exactly where wave 2 put them — y = 79.50, x = 80.00–95.24, pitch 2.54, pin 3 at
y = 82.04 — and put the fan-out on **B.Cu** instead of F.Cu.

| step | change | measured effect |
|---|---|---|
| 0 | as built | F.Cu **0**, B.Cu **4** — 4 of 7 lanes already exist on the back |
| L2 | re-home `/RF_GPIO2` out of the band (one 0.20 mm trace, 12.70 mm long) | B.Cu **6** @0.30, **8** @0.25 |
| L4 | set 0.13 mm trace / 0.10 mm clearance | B.Cu **8 ≥ 7** — done |
| L1 | optional: shrink the `/GNSS_PWR_EN` via 0.700 → 0.450 | +0 at 0.30 in this band; helpful at x 64.8–65.0 |
| L3 | optional: move **C36** (one 0402) clear of the band | F.Cu 0 → 2 @0.30, 4 @0.25 |

L4 is not a new fab burden: this board **already has 33 vias at 0.30 mm pad / 0.10 mm drill** and
already generates **5 blind/buried drill files** (`AGENT_BOARD.md:56`; `via_stats.out`). Current
design rules are 0.200 min track and 0.125 min clearance (`via_stats.out`), so L4 is a *rule edit*
in a direction the fabrication already supports. Owner steer: fab burden free → take it.

Layered against the steer's preference order: **constraint edit (L4) + one trace re-home (L2)** solves
it. That is cheaper than the "rip-up" wave 2 priced, which required excavating an F.Cu channel.

### 4.1 Why B.Cu is legal here

`/GND` pours exist on F.Cu and B.Cu, and `/3V3`+`/GND` on In1/In2 (`verify_parity.out`). Pours reflow
around new traces, so they are not obstacles; and because the fan-out stays on the two outer layers,
**In1 and In2 are not cut at all** — unlike the void-fill unit, which needs 13 In1 segments moved.
`RF_GPIO2` is a real functional net, so L2 is a genuine reroute of 12.70 mm, not a deletion.

---

## 5. Channel count — 7, and the 7th is the rudder

Verified directly, not inherited:

| claim | source |
|---|---|
| "2 elevons + 3–4 vanes + 1 rudder = **6–7 servos**" | `drone-mech/highspeed_edf/design/PHASE15_CONTROL_SURFACES.md:35` |
| "**Rudder ×1** … yaw has **no authority above ~400 km/h** without it" | same `:34` |
| "B — 4 vanes (2/duct) + **rudder (7 servos)** \| **+₹0.6–0.9k** \| **YES**" | `DESIGN_DECISIONS_FOR_VERDICT.md:50` |
| "D3 vanes \| **4 + rudder (7 servos)**" | same `:122` |
| "**F-05 — the 7th servo has no PWM channel.** D3 chose 4 vanes + 1 rudder = **7**" | same `:158` |
| `modeled_effector_count: 7`, pwm `capacity: 6`, actuators BLOCKED "seven modeled effectors exceed six PWM outputs" | `drone-arm/aircraft_interfaces/system_interface.json:55,104,124` |
| "J60–J66 … 6 missing_footprint becomes 0"; "**7 actuators vs 6 channels**" | `AGENT_BOARD.md:54,93` |

**7 is a floor, not a preference.** `DESIGN_DECISIONS_FOR_VERDICT.md:171–172` prices a two-rudder
option (a) at "+₹0.6–0.9k **and one more PWM channel (compounds F-05)**" — so if the rudder's
single-point failure (`:168` F-10) is ever answered with a second rudder, the requirement becomes 8.
Design for 7, leave the 8th as `PWM_ESC8` on pad 52 (GPIO41, free and already unconnected,
`verify_parity.out`) so a later decision costs a trace, not a board.

---

## 6. What still needs copper

All of it on outer layers; none of it on a plane.

1. 7 × F.Cu stub, pad → via, ~0.5 mm each, 0.13 mm wide, from pads 43–49.
2. 7 × via **0.30 pad / 0.10 drill** (already a board standard — 33 instances) in a row at x ≈ 64.6–64.9.
   At the pads' own 0.40 mm pitch a 0.30 mm via leaves 0.10 mm via-to-via; stagger into two rows if the
   row cannot be placed in one (not routed here — see UNVERIFIED).
3. 7 × B.Cu run from the via row east into the free field and on to pin 3 of J60–J66 at y = 82.04,
   width 0.13 mm — ample for ≤ 800 Hz PWM, and the servo signal is not an impedance-controlled path.
4. **L2**: `/RF_GPIO2` rerouted out of y 50.40–53.20, 12.70 mm.
5. Zone refill of F.Cu/B.Cu only. **No In1/In2 edit, no stackup change, no part move.**
6. Optional, for margin: `C36` relocated out of the band (one 0402, 2 pads, `/GND` + `/3V3`).

Not in scope here and unchanged from wave 2: the servo-rail risk (`w2` §6 — pin 2 hangs on a 0.75 A
PTC behind a 1 A buck against a 6.0–7.4 V / 3–9 A requirement; that is `AGENT_BOARD.md:165`,
decision 3, still an owner item) and the CAN H/L swap.

---

## 7. Corrections

**BOARD CORRECTION — `AGENT_BOARD.md:155`** (top-5 blocking fab item 3): the clause "**no lane at pads
43–49**" is true only for **F.Cu at 0.30 mm pitch**. On **B.Cu the same band already carries 4 lanes**
at 0.30 mm and 8 after one trace is re-homed (`levers.out`). The board line and `w2` §4.1 present the
defect as requiring a 7-trace F.Cu channel to be excavated; the measured work is one trace re-home plus
a rule edit. `AGENT_BOARD.md:54` (the "0 free lanes" cell) is **correct as stated** — 0 on F.Cu,
re-confirmed at 0.01 mm — and is not restated as a new finding.

Also corrected inside this unit: my own first `single_lever.out` block over-blocked B.Cu by marking
SMD pads on both outer layers; that row is superseded and kept visible in the artefact.

---

## 8. UNVERIFIED

1. **No route was authored.** Capacity across cuts is a necessary condition, not a proof: via-row
   placement at 0.40 mm pitch, exact jog geometry for `/RF_GPIO2`, and the 7 B.Cu runs are a routing
   task not done here.
2. Whether the 0.30/0.10 vias already on this board are microvias in the 5 blind/buried drill files
   (`AGENT_BOARD.md:56`) or through-vias with an aggressive aspect ratio — not determined.
3. GPIO40 (pad 49) → usable PWM slice remains a **firmware** claim, unchanged from `w2` §8.1.
4. The 0.5 mm FFC option's mechanical retention/vibration fidelity in a flight controller is a
   judgement, not a measurement; the 1.0 mm JST-SH already at J10 is the higher-fidelity small part.
5. Whether K37–K40 decoupling can live with C36 moved — the part is one of four (`C34`–`C37`), but the
   electrical consequence of moving it was not simulated.

---

## 9. Reproduce / files

```
& 'C:/Program Files/KiCad/9.0/bin/python.exe' capacity.py      # capacity vs cut, 5 rule sets
& '...' levers.py                                              # L1/L2/L3 decomposition
& '...' pinch.py                                               # inflight inventory + edge distances
& '...' blocks.py                                              # GPIO-block comparison + free rects
& '...' escape_exact.py                                        # corridor object dump
& '...' debug_raster.py                                        # column-level blocked runs
& '...' via_stats.py                                           # existing widths/vias/drule
& '...' vias_band.py                                           # vias inside the pad band
& '...' single_lever.py                                        # layer-attribution fix, superseded rows
```

Artefacts: `capacity.out`, `levers.out`, `pinch.out`, `blocks.out`, `escape_exact.out`,
`debug_raster.out`, `via_stats.out`, `vias_band.out`, `single_lever.out`, `unused_pads.json`,
`occF.npy`, `occB.npy`.