# ESC STACK v2 — the control board mounts on the power board, heatsink under, and it costs under $78

**Unit:** esc-stack-v2 · **Date:** 2026-11-17 · **Author:** specialist subagent
**Inputs (read-only):** `evidence/esc-split-power/`, `evidence/esc-split-control/` (measured on copies)
**Outputs:** this directory — scripts, JSON, STEP/STL, the section sheet, this report.
Nothing written into a repo, into `D:\CodeProjects` or into `E:\1vm\TMP`. No commits.

**Provenance tags:** MEASURED (from the board files, scripts here) / PUBLISHED (datasheet, vendor page,
cited) / CALCULATED (arithmetic in `13_model.py` / `14_sink.py`) / ASSUMED (my choice, stated).

---

## 0. THE ANSWER

| question | answer |
|---|---|
| Where does the heatsink go? | **UNDER the power board, fins down (option i).** Option (ii) is not fixable — proven in §1. |
| Height budget | **sink 34.00 mm below the FET contact plane + 21.80 mm above it = 55.80 mm** total |
| (a) header reach | **solved — no long post needed.** Gap is 10.0 mm, **Samtec TSW-120-15-G-D** (post 13.21, OAL 18.54) + **SSW-120-01-G-D** socket. Tip lands 0.8 mm below the socket top by design. |
| (b) header vs sink | **solved — no shared plane.** Header stays at **x 131.5–136.6**, now **y 20.0–70.8** (40 pins); sink is **x 5.5–130.5**, i.e. **1.0 mm** clear, and it is on the opposite face anyway |
| (c) six 31–35.5 mm caps | **solved — they never cross anything.** Moved **y 116.5 → 112.5** (bodies y 103.5–121.5); they hang below the board outboard of the sink (sink ends at y 81) |
| Machined sink under $78? | **yes at 5 and 50 pcs** by two routes: cut-to-length extrusion with a machined face **$44.5 @5 / $33.7 @50**; machined base + bonded fins **$54.0 / $43.2** (both at a $45/h shop rate). Full 3D billet is **$92 @5 at a US rate — FAILS**; it passes at $81.2 at 50 pcs, or $66 at 5 pcs from a Shenzhen shop. |
| FET Tj at 80 A/phase | **123.2 °C** with the specified 0.010 in isolating pad (110.3 °C with a 0.006 in class pad); Tj limit 150 °C |
| Enclosure height | **55.80 mm**, single number — the cans sit 1.10 mm *above* the fin-tip datum, so no floor pocket is needed |
| Does the stack assemble? | **YES** — with the 9 board changes listed in §7. As filed, it did not. |

Cost: **$285–365 per ESC** (5 builds) = **0.42–0.63×** the $450–870 baseline, and **under the $675 floor
of the 1.5× cap** with $310 of slack. The heatsink is working out at **$44.5–54/part, not $245**.

---

## 1. WHERE THE SINK GOES — the first question, and it decides the other three

### 1.1 The physics forces the answer

The FET is **IPTC014N10NM5, PG-HDSOP-16 "TO-Leadless top-side cooling" (TOLT)**. Its 6 cm² cooling
surface is the **top face of the package**, i.e. the face pointing away from the PCB it is soldered to
(**PUBLISHED**: Infineon datasheet — `RthJA 40 °C/W` "6 cm² cooling area", Figure 1 outline; the file is
in the previous wave's `hdr/ds/fet.txt`). Confirmed this pass: the footprint's thermal slug is a
**10.2 × 7.0 mm = 71.4 mm²** pad at the FET centre, **with no net assigned** (MEASURED, `10_power_geom.py`).

Consequence, and it is not a preference: **the heatsink must be on the same side of the power board as
the FET solder face.** The owner's words fix the other end — "the control board use 2.54 mm pins to
connect **on top of** the main ESC". So:

* control board on top,
* FETs + sink on the bottom,
* the two cannot fight for the same volume. That is option (i).

### 1.2 Option (ii) — sink between the boards — measured against the same rule

| what option (ii) needs | number | verdict |
|---|---|---|
| board-to-board gap | FET 2.35 + TIM 0.25 + sink 25 + air 2.0 = **28.55 mm** (the number the last wave measured) | — |
| post reach above the power board | 28.55 + 1.60 + 1.00 = **31.15 mm** | **no 2.54 mm header reaches it.** TSW-120-08 tip = 8.38 mm (22.8 short); TSW-120-15 tip = 15.75 mm (15.4 short); only the unlisted `-26` lead style (30.99 post → 33.53 tip) gets there, on a 33 mm unsupported pin |
| control board ambient | it sits 2 mm above a 100 °C+ sink, in a 28.55 mm box | the control board's own parts (SRR1260 at 6 mm) leave 22 mm of dead air over a 583 W heater |
| the six 820 µF cans | 31–35.5 mm tall on the same face as the gap | they pierce 2.5–7 mm. Relocating them widens the gap (see §3c) |
| total height | 28.55 + 1.6 + 1.6 + 6 + 4 + 30 ≈ **72 mm** | 1.29× option (i) |

Option (ii) can only be made to "close" by buying a 1.2 inch post, a 100 °C control board and a 72 mm
enclosure. **Disproved** — and the three defects the last wave found are exactly its three failure modes,
which is why fixing them one by one was always going to be the wrong job.

### 1.3 Option (i) as it actually assembles

The power board is **flipped over in the chassis**: its F.Cu face (which carries *every* SMD part — 36
FETs, 18 shunts, 6 cans, 6 gate drivers, the bus bars) faces **down** into the heatsink; its **B.Cu face
is bare** and that is what the control board stands off. Two consequences worth stating plainly:

1. **The board is still single-sided for assembly.** Zero back-side SMD, one reflow pass. The only B.Cu
   item anywhere is the 2×20 through-hole header's plastic body, hand-soldered on the mating face — which
   *every* two-board stack needs (the previous verifier reached the same conclusion: the rule must read
   "no back-side SMD"). No second reflow, no cost.
2. **The sink no longer competes with anything.** The 31–35.5 mm cans, the 2.54 mm motor-side headers and
   the bus bars all live on the now-downward face, and the sink only covers the FET/phase field
   (y 7–81 of a 122.5 mm board). The rear 41 mm of the board is open air.

---

## 2. THE STACK, LAYER BY LAYER

z = 0 is the heatsink's FET contact face. +z is up toward the control board. (Sheet §b, file
`15_stack_section.png`.)

| # | layer | thickness mm | z after | provenance |
|---:|---|---:|---:|---|
| 1 | fin field — **16 fins × 2.0 × 30.0, pitch 4.625** | 30.00 | −34.00 | CALCULATED (extrudable: h/t = 15) |
| 2 | base plate 6061-T6, machined contact face, flat 0.05 | 4.00 | −4.00 | CALCULATED / `14_sink.py` |
| 3 | thermal interface, **Sil-Pad 2000 0.010 in**, compressed, 4 kV | 0.25 | 0.25 | PUBLISHED (Bergquist 0.38 °C·in²/W @ 50 psi) |
| 4 | **FET package PG-HDSOP-16**, pad on the TIM, board above | 2.35 | 2.60 | PUBLISHED (A max) |
| 5 | power PCB, 4-layer, 3 oz outer | 1.60 | 4.20 | MEASURED (stackup in the board file) |
| 6 | **air gap: header + 4 × 10 mm standoffs** | 10.00 | 14.20 | ASSUMED (Keystone 24349 class) |
| 7 | control PCB, 4-layer, single-sided | 1.60 | 15.80 | ASSUMED (same class as the power board) |
| 8 | tallest control part, Bourns **SRR1260** | 6.00 | 21.80 | PUBLISHED (6.0 ± 0.5) |
| | **TOTAL** | **55.80** | | CALCULATED |

**How the FETs couple to the sink.** All 36 slug pads are coplanar (same footprint, same board, same
package) so the contact face is a **single flat machined surface** — no pedestals, no height matching. The
pad presses on a 0.25 mm Sil-Pad; the pad is the hard stop, so the clamp cannot over-compress it.

**Can the sink be recessed for the FETs?** Not for the FETs — they must *touch* it. It is recessed for the
**only parts that stand above the FET plane**: the 18 shunts (3.04 mm tall) stick **0.44 mm past** the
contact plane, so the base carries **two 0.7 mm deep × 6.2 mm wide milled channels** at board y 34.0–40.2
and 48.3–54.5, full length. Everything else on the down face clears: bus bars ≤ 2.0 mm thick (0.60 mm
clear), busbar lands and SMD copper 0.1 mm.

**Mass.** 154.2 cm³ = **416.3 g** of 6061-T6 (CALCULATED, cadquery solid `esc_hs2.step`/`.stl`), 6.2 % of
the 6.72 kg airframe. That is 2.5× the previous 166 g estimate (10 fins × 22 mm), and the extra 250 g
buys **24 K**: Rth_sa 0.120 → 0.0661. Read §5.3 before spending any more on aluminium — at this point a
watt of pad beats a kilogram of fin.

---

## 3. THE THREE DEFECTS, EACH CLOSED

### (a) Header reach — the 31.15 mm requirement is gone, not met

With the sink underneath, the board-to-board gap is set by the standoffs, not by the sink. Chosen gap
**10.00 mm**, so the post must reach `10.00 + 1.60 (control PCB) + ~0.8 (into the socket body)` =
**12.4 mm** above the power board's B.Cu face.

| part | role | real geometry | tip above B.Cu | verdict |
|---|---|---|---|---|
| **Samtec TSW-120-15-G-D** | 2×20, 2.54 mm, 40-pin male, on the power board | **post 13.21 mm, OAL 18.54 mm, tail 2.79 mm**, 0.635 mm square post | **15.75 mm** | **specified.** $5.69 @1, $4.85 @100 (PUBLISHED, Samtec) |
| **Samtec SSW-120-01-G-D** | 2×20 socket on the control board's top face | body **4.95 mm** (.195 in), tail 2.64 mm | — | **specified.** $6.84 @1, $5.88 @100 (PUBLISHED) |
| Samtec TSW-120-08-G-D | the standard 0.230 in post | post 5.84, tip 8.38 | 8.38 | not used — 4.0 mm short of 12.4 |
| *(`-26` 30.99 mm post)* | what option (ii) would need | tip 33.53 | — | **not needed any more** |

Mated check: post tip at z = 4.20 + 2.54 + 13.21 = **19.95**; socket body occupies 15.80 → 20.75, so the
tip sits **0.80 mm below the socket's top face** — fully through the control board's hole and inside the
contact. Tail ends at z = 1.41, in free air. **No trimming, no long-post special, no 15.4 mm shortfall.**

Cost note: **$12.53/pair at 1-off, $10.73 at 100**, against the $0.41 the cost model carried. That is
**+$12.12 per ESC** — 4 % of the total (§4.3). A commodity 2.54 mm 2×20 with a 13 mm post would be
~$0.60, if the buyer prefers to trade the published length guarantee for price.

### (b) Header vs sink — moved, with coordinates

| item | before | now | clearance |
|---|---|---|---|
| 2×20 header site | x 131.5–136.6, **y 20–58** (2×15 reserved) | **x 131.5–136.6, y 20.0–70.8** (2×20 = 50.8 mm) | — |
| heatsink outline | 130 mm wide, centred → x 4.2–134.2 | **125 × 74 mm at x 5.5–130.5, y 7.0–81.0** | **1.0 mm** in x to the header's pads |
| face conflict | both on the top face → 2.7 mm overlap | the sink is **under** the board; the header is **on top** | **none — different faces** |
| header tails (2.79 mm, the only part that reaches the FET side) | would enter the sink | end at **z = 1.41, x ≥ 131.5** — outside the sink's x range | **1.0 mm** |
| sink clamp screws | the board had **no** clamp holes | **4 × Ø3.3 at (47.5, 14), (90.5, 14), (47.5, 74), (90.5, 74)** — in the two 7.8 mm inter-block corridors | the 7 mm boss leaves **0.4 mm** to the neighbouring FET pad each side |

Also deleted: **J1–J6**, six `Conn_02x12_Pin` bodies 5.08 wide × 29.64 long, sitting **inside** the sink
footprint at x 46.35–50.59 and 89.45–93.69, y 9.45–79.09. They are 2.54 mm tall, so they would have
clashed with the contact face by 0.19 mm — and **all 24 pads on each are unassigned (no net)**: they are
vestigial from the single-board design. Their deletion is what frees the two clamp corridors.

### (c) The six 820 µF cans — they were only ever a defect because of option (ii)

| | before | now |
|---|---|---|
| x | 6.0, 28.3, 50.6, 72.9, 95.2, 117.5 | unchanged |
| y (centre) | **116.5** → D18 body 107.5–125.5, i.e. **3 mm over the board edge** | **112.5** → body **103.5–121.5**, inside the 122.5 edge |
| relation to the gap | pierced a 28.55 mm gap by 2.5–7 mm | **there is no gap on that face.** They hang 35.5 mm down into free air, **22.5 mm outboard of the sink** (sink ends y 81.0, can band starts 103.5) |
| relation to the sink | inside the sink's footprint | **outside it** — no pocket, no cutout, no channel |
| relation to the enclosure floor | — | can tips reach z = **−32.90**, i.e. **1.10 mm above** the fin tips (−34.00). No floor cut needed beyond the fin datum |

The 4 mm inboard shift also **shortens** the can-to-FET path: the nearest FET pad edge is y 78.0, so the
can-to-pad distance falls from **29.5 mm to 25.5 mm** (−14 %). The bulk loop gets *better*, not worse.

**Should they move to the control board instead? No — and here is the number.** The header contributes
**8.29 nH** to any loop that crosses it (the previous wave's measurement, verified). Six 820 µF cans in
parallel are 4 920 µF; against 8.29 nH that resonates at

```
f = 1 / (2 pi sqrt(L C)) = 1 / (2 pi sqrt(8.29e-9 x 4.92e-3)) = 24.9 kHz
```

— **the 24 kHz switching frequency.** Putting the DC-link cans across the header places the commutation
impedance minimum exactly at fsw. The cans stay on the power board. (This is also why the measurement
front ends can't cross, which the earlier wave established: 73.8 mV of coupling into a 54.5 mV full
scale.)

---

## 4. THE MACHINED HEATSINK — design, and five ways to make it, costed

### 4.1 The part: **ESC-HS2**

| feature | value |
|---|---|
| envelope | **125 × 74 × 34 mm** (4.0 base + 30.0 fins) |
| fins | **16 × 2.0 mm thick, 30.0 mm tall, pitch 4.625 mm, channel 2.625 mm** — h/t = 15, the extrusion limit; a 4.6 mm pitch with 2.0 mm fins is a standard high-density profile, not a custom die |
| contact face | machined flat **0.05 mm over 125 mm** (this is what makes the clamp pressure uniform across 36 pads) |
| relief | 2 channels **0.7 deep × 6.2 wide × 125 long** at y 34.0–40.2 / 48.3–54.5 (the shunt rows) |
| mounting | **4 × M3 × 6 deep tapped bosses, 7 × 10 mm, 2 mm proud into the fin field** at (47.5, 14) (90.5, 14) (47.5, 74) (90.5, 74) — a 6 mm boss is what lets a 4 mm base hold a 2 D thread |
| edge | 1.5 mm corner chamfers |
| material | 6061-T6 (extrusion 6063 is equally acceptable; 6061 for a billet) |
| solid | **154.2 cm³ = 416.3 g** (cadquery, `14_sink.py`), surface 1406 cm² |
| thermal | **Rth_sa 0.0661, Rth_tot 0.0727 K/W** at h = 150 W/m²K, fin efficiency 0.796 |

A 1.2 mm fin at 30 mm would be a 25:1 aspect — **not extrudable** — and, at that height, *worse*
(Rth_tot 0.0792, because the fin efficiency falls to 0.708). So 2.0 mm wins on both counts: it is
extrudable and it is 3 % better thermally than the thin fin. The bill-of-materials question is a
manufacturing question, and here the manufacturable answer is also the better one.

### 4.2 Five manufacturing routes, per-part cost at 5 and 50

Minutes are a bottom-up time model (cut, face, 2 channels, 4 drill+tap, deburr, inspect; billet roughing
at 2 mm DOC, 3 mm stepover, 125 mm long slots). Rates: the programme's own **$45/h** (the rate the last
wave used, so the delta is design not shop) and a **$30/h Shenzhen online-CNC** rate; setup $60 / $40 per
order. Consumables: anodise/chem-film $3–4, bonding adhesive $5, brazing $25. Material at $8/kg.

| # | approach | 5 pc @$45/h | 50 pc @$45/h | 5 pc @$30/h | 50 pc @$30/h | meets $78? |
|---|---|---:|---:|---:|---:|---|
| **A** | **cut-to-length extruded profile, mounting face machined** (face skim, 2 shunt channels, 4 tapped bosses, chamfer) | **$44.5** | **$33.7** | **$34.0** | **$26.8** | **yes, everywhere** |
| **B** | **machined 6061 base plate + extruded fin block bonded into a pocket** (fully custom outline, tapped ears, the same features) | **$54.0** | **$43.2** | **$41.5** | **$34.3** | **yes, everywhere** |
| C | waterjet/laser-cut fins (16 off 2 mm plate) vacuum-brazed to a machined plate | $64.0 | $53.2 | $55.0 | $47.8 | yes at 5 (both rates) and 50 |
| D | skived fin stack bonded/screwed to a machined plate (1.2 mm fins possible) | $80.5 | $69.7 | $72.0 | $64.8 | **no at 5** (both rates), yes at 50 |
| E | **full 3D billet** — fins and base from one block, 245 cm³ removed, 88 min | $92.0 | $81.2 | $66.0 | $58.8 | **no at 5 US**, marginal at 5 CN, yes at 50 |

**Recommendation: A**, because it is the cheapest thing that is also the best thermally, and it is
"custom" in the way that matters — a unique part number with a machined mounting interface, not a
stock casting. B is the answer if the owner wants a genuinely bespoke outline (ears, pockets, a logo);
it still clears $78 at 5 off by $24.

**What the owner actually asked for — a full machined part — is route E, and E and D are the two that
break the cap at 5 off in a Western shop ($92 and $80.5 vs the $78 ceiling).** E becomes viable at 50 pcs
($81.2 US, $58.8 China) or at 5 pcs from a Shenzhen shop ($66). That reproduces the last wave's finding
from the other side: the $635 machined block was never a geometry problem, it was a *process* choice —
88 min of fin slotting against 26 min of interface machining.

### 4.3 What the money buys, per ESC

| line | before (last wave) | now |
|---|---:|---:|
| power board 4L 3 oz, 169.7 cm² | $214–285 | $214–285 |
| control board 2L 100×100 | $5.00 | $5.00 |
| 2.54 mm header pair | $0.41 | **$12.53** (TSW-15 + SSW-01) |
| connectors | $9.04 | $9.04 |
| **heatsink** | $245 ("extruded, milled lands") | **$44.5–54.0** |
| **total per ESC, 5 builds** | $473–544 | **$285–365** |
| vs the 1.5× cap floor ($675) | 0.70–0.81× | **0.42–0.54×** |
| vs the baseline ($450–870) | 1.05× / 0.63× | **0.63× / 0.42×** |

The cap is no longer close. Against today's $285–365 total, the sink budget under the $675 floor is
**$364–434 per part**, and the recommended part costs $44.5. Priced the other way: even route E at
$92/part leaves the total at $332–412, still under $675.

---

## 5. THERMAL VERIFICATION AT 80 A/PHASE

### 5.1 Model (transparent, `13_model.py`)

```
Q(80 A)   = 448.0 W   (the programme's own 04_heatsink.json loss table, 36 devices at 11.9 W)
Rth_sa    = 0.0661    fin analysis: 16 x 2.0 x 30 fins, eta_f 0.796, A_eff 1008 cm2, h = 150 W/m2K
Rth_base  = 0.0066    conduction through the 4 mm base + a 0.004 spreading allowance
Rth_tot   = 0.0727 K/W
Rth_TIM   = 3.43 degC/W   = 0.38 degC-in2/W (PUBLISHED, Sil-Pad 2000 @ 50 psi) / 0.1107 in2 (71.4 mm2)
Rth_jc    = 0.40 degC/W   (PUBLISHED, PG-HDSOP-16)
```

### 5.2 Result

| I/phase | Q | T_sink | Tj (0.010 in pad) | Tj (0.006 in class pad, 2.35 °C/W) |
|---:|---:|---:|---:|---:|
| 63 A (600 km/h @2 km) | 298.2 W | 66.7 °C | **98.5 °C** | 89.5 °C |
| **80 A (650 km/h @2 km)** | 448.0 W | 77.6 °C | **123.2 °C** | **110.3 °C** |
| 109 A (720 km/h @2 km) | 771.0 W | 101.1 °C | 183.1 °C **FAIL** | 162.4 °C **FAIL** |

**Tj = 123.2 °C at 80 A/phase**, 27 K under the 150 °C limit, at a 45 °C ambient. That is the number the
owner should carry; the 720 point needs the 72-FET build (the programme's own "all 12 sites" upgrade),
not this sink.

### 5.3 Why this differs from the earlier 66.6 °C / 85.9 °C, and what actually limits the design

The earlier figures used an **8 °C/W per-device lump**; the present model resolves it into
jc + pad + sink. The difference is almost entirely the **isolation pad**:

```
of the 123.2 °C,   45.6 K is the Sil-Pad (0.4 + 3.43 degC/W x 11.9 W)
                   32.6 K is the heatsink (0.0727 x 448 W)
                    4.0 K is Rth_jc
                   45.0 K is ambient
```

**The pad, not the sink, is the thermal bottleneck.** Going to a 60 mm fin stack (+332 g, 748 g total,
+$15) buys **6.9 K** (Tj 116.3). Changing the 0.010 in pad for a 0.005 in class buys **12.9 K** and costs
no mass at all. The whole-sink budget cannot buy more than ~20 K; the pad alone is worth 13.

The previous table used the pad's *bulk* impedance (0.78 °C/W) and dropped its ~2.4 °C/W contact term —
that is the whole gap between 93.7 °C and 123.2 °C at the same 80 A through the same sink. Recommendation: specify the 0.010 in pad (4 kV, the conservative choice), and
if Tj margin is ever needed, the first lever is a thinner 0.005 in / 0.1 mm-class insulator (≈ −13 K), the
second is the 72-FET build, and only the third is more aluminium.

Sensitivity: h is ASSUMED at 150 W/m²K. At h = 300 (a 2.6 mm channel at 167 m/s, if the duct does not
choke) Rth_tot falls to 0.0454 and **Tj = 111.0 °C**; at h = 100 it rises to 0.0996 and **Tj = 135.2 °C**. **h is the one
number in this report that should be measured in the duct.**

---

## 6. THE DRAWING AND THE HEIGHT A BUYER MUST ALLOW

`15_stack_section.png` — (a) plan with the section markers, the sink outline, the header site, the clamp
screws and the can positions; (b) section A–A through a phase column; (c) section B–B through a clamp
screw; (d) section C–C through the header at the right edge; (e) the stack ladder. `esc_hs2.step` and
`esc_hs2.stl` are the heatsink solid.

**Enclosure**: allow **55.80 mm** of clear height from the fin-tip datum to the top of the tallest
control-board part, over a footprint of the board plus 5–8 mm of installation margin. That is one
number, not two: the lowest point anywhere is the fin tip (z = −34.00), and the cans stop at −32.90,
1.10 mm above it, so a plain box needs no floor pocket. Leave **≥ 6 mm of free space at the header end**
for the 2.54 mm pins' insertion travel.

Sub-assembly order (this is what makes it assemble):
1. solder 36 FETs + all SMD on the power board's F.Cu (one reflow);
2. hand-solder the 2×20 header on the B.Cu side and the cans, motor lugs and bus bars on the F.Cu side;
3. lay the Sil-Pad sheet on the sink, locate the sink on the four Ø3.3 board holes, drop the four M3
   screws from the B.Cu side, torque **0.13 N·m** in a cross pattern (24 N per FET = 50 psi);
4. plug the control board (with its SSW socket) onto the pin field, fit the four 10 mm spacers and the
   four longer M3 screws, torque 0.1 N·m.

---

## 7. WHAT HAS TO CHANGE ON THE BOARDS (the manifest, all on copies)

**Power board** (7 items)
1. **Confirm the F.Cu-down mounting** in the assembly drawing and on the silkscreen (a "THIS SIDE DOWN"
   legend + a FET-1 marker) — this is the change that makes the whole stack legal.
2. Delete **J1–J6** (6 × `Conn_02x12_Pin`, 144 pads, **zero nets**): inside the sink footprint, 2.54 mm
   tall, vestigial.
3. Add **4 × Ø3.3 NPTH** clamp holes at **(47.5, 14), (90.5, 14), (47.5, 74), (90.5, 74)**.
4. Move the 6 × `820uF_35V` cans **y 116.5 → 112.5** (bodies then y 103.5–121.5, inside the edge).
5. Correct the can voltage: **`820uF_35V` on a 44.4 V bus is wrong** — the board of record uses 820 µF
   100 V (the previous verifier flagged this; it is a BOM defect independent of the stack).
6. Keep the **Busbar_land** bars ≤ **2.0 mm** thick on the F.Cu side (0.60 mm clear of the contact face); or move
   the BAR2 bar to a pocket if a thicker bus is wanted.
7. Assign the FET **slug pad** (10.2 × 7.0, currently **no net**) — or document it as an isolated thermal
   pad. With 36 pads at different potentials (BATP / phase nodes) the sink **must** be isolated by the
   TIM; do not substitute grease.

**Control board** (the 2×20 header is now specified)
8. 2×20 / 40 positions at the power-board site x 131.5–136.6, y 20.0–70.8, with the **SSW-120-01-G-D
   socket on the control board's top face** (it is a through-hole part; the male post enters from below
   through the board hole). 100 × 100 outline, positioned so the socket lands on the pin field
   (x 37–137, y 11–111 works).
9. The pin assignment itself (measurement + BEC + MCU on the control board, 6 of 7 MCUs moving off the
   power board) is **outside this task** — but the enabler is here: the six cell MCUs and their AFEs
   leaving the rear band frees the space the 40-pin header needs, and the header is now sized for 40.

---

## 8. WHAT STILL DOES NOT CLOSE

1. **h = 150 W/m²K is ASSUMED.** Everything thermal scales with it (§5.3). A 2.6 mm channel at 167 m/s is
   near-choked; the real number could be 100 (Tj 135.2) or 300 (Tj 111.0).
2. **Costs are modelled, not quoted.** No shop has seen this part. The material line ($9–10) is anchored to
   the previous wave's published extrusion price ($38.73 for 260 mm of a 150 mm-wide profile, scaled by
   width and length); the minutes are a time model with ±40 %. The *ranking* and the pass/fail at $78 are
   robust to that; the absolute dollars are not.
3. **The 2.625 mm channel / 4.625 mm pitch, 30 mm deep extruded profile is a catalogue selection, not a locked
   part.** If no stock die matches, route B (machined base + bonded fin block, $54/5) is the fallback and
   the thermal numbers are unchanged.
4. **The control board has no board file anywhere in the programme.** Its 100 × 100 × 1.60 envelope and
   6 mm tallest part are a specification, not a measurement.
5. **The 44.4 V → 100 V can derating and the 4 kV pad** are what keep the sink's isolation legal; a
   0.005 in pad improves Tj by 13 K but must be re-checked for dielectric strength at the pad edges.
6. **Vibration/mass**: 416 g of aluminium hanging below a 1.6 mm board on four M3 screws is a
   structural load case nobody has run. The four bosses are 2 mm proud into the fin field for a reason —
   keep the thread engagement at 6 mm, and consider a fifth screw if the airframe sees >5 g RMS.
7. **The pin split (requirement: measurement + BEC + MCU on the control board) is still not delivered.**
   That is the one owner requirement this stack does not address; it is a schematic/partition job, and the
   connector and volume are now ready for it.

---

## 9. FILES

| file | what |
|---|---|
| `10_power_geom.py` / `.json` | footprint census + board outline, pcbnew |
| `11_tall_parts.py` | tall parts, lands, mounting holes, edge cuts |
| `12_pads_nets.py` / `12_occ.json` | FET slug pad 71.4 mm² (no net), 18 shunts, J1–J6 nets (none), free-space grid |
| `13_model.py` / `.json` | fin sweep, stack frame, Tj, cost model — every number in §2/§4/§5 |
| `14_sink.py`, `14_sink.json`, `esc_hs2.step`, `esc_hs2.stl` | ESC-HS2 solid, volume/mass/area (cadquery 2.7.0 + OCP 7.8.1) |
| `15_section.py` / `.png` | the dimensioned sheet |\n| `16_sens.py` / `16_sens.json` | fin-height and h sensitivities quoted in §5.3 |

**Provenance of the numbers this report leans on**
PUBLISHED: TOLT top-side cooling + RthJA 40 °C/W at 6 cm² (Infineon PG-HDSOP-16); A max 2.35 mm;
Sil-Pad 2000 0.38 °C·in²/W @ 50 psi / 4 kV; SRR1260 6.0 ± 0.5 mm; TSW-120-15-G-D post 13.21 / OAL 18.54 /
$5.69 @1; SSW-120-01-G-D body .195 in / tail .104 in / $6.84 @1; 6061-T6 properties.
MEASURED: board 138.3 × 122.5 × 1.60, 4-layer; FET slug 10.2 × 7.0 = 71.4 mm², no net; 18 shunts at
y 34.5–39.7 / 48.8–54.0, 3.04 tall; 6 cans at y 112.5 (moved) D18; 2 × M3 holes at x 134.2; 36 pads
x 8.28–128.68, y 10.7–78.0.
CALCULATED: 55.80 mm; 0.0727 K/W; 123.2 °C; 416.3 g; every dollar in §4.
ASSUMED: h = 150 W/m²K; 10 mm gap; the $45/h and $30/h shop rates; the ±40 % cost band; control-board
thickness and tallest part.