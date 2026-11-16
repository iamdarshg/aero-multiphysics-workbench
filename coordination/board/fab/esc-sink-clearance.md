# ESC split — sink / three-column header clearance re-solve

Status: **FINAL** — one task, answered. Short answer in §0.
Date: 2026-11-17
Host: KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), `C:\Program Files\Python312\python.exe` (cadquery 2.7.0 / OCP 7.8.1.1)

## 0. Assignment

Re-solve the sink/header clearance for the ESC split now that the pin split uses **THREE** 2x20
header columns (was TWO). Prior two-column case: 1.0 mm clearance. Three columns makes it worse.

Inputs (read-only):
- `evidence/esc-stack-v2/` — assembled stack + section drawing
- `evidence/esc-pinsplit-v2/` — 3 x 2x20 = 120-pin map (H1 25/15, H2 31/9, H3 21/19)

Output: this directory, `E:/engineering-portfolio-audit/evidence/esc-sink-clearance/`.
All work on COPIES. No repo writes.

Baseline numbers carried in (to be re-measured, not assumed):
- Board 105 x 60 mm, 63.0 cm2, 2-layer.
- Sink 125 x 74 mm at x 5.5-130.5, y 7.0-81.0 (overhangs the board on three sides).
- Two-column header at x 131.5-136.6, y 20.0-70.8.
- Stack total 55.80 mm (34.00 below FET contact face, 21.80 above).
- Tj at 80 A = 123.2 C, PAD-LIMITED (45.6 K is the Sil-Pad).
- Enclosure 55.80 mm tall; machined extrusion + machined face $44.5 at 5 pcs.

**Correction to the brief, measured:** the two-column header is **not** the one this split inherits —
it sat at x 131.5–136.6 **y 20.0–70.8** on a **138.35 × 122.55** power board (not 105 × 60; 105 × 60 is
the *control* board), and that site **drilled the BATN busbar land**. See §1.4.

---

## 0b. THE ANSWER

| question | answer |
|---|---|
| real 3-column footprint | **18.27 × 51.81 mm = 946.6 mm²** (three 6.09 × 51.81 courtyards at 6.09 pitch), bodies 15.24 × 50.80. **3 × TSW-120-15-G-D + 3 × SSW-120-01-G-D** — 2-column parts, three of them; the triple-row TSW traps its middle row for a 2-layer escape |
| overlap with the sink on today's board | **11.92 mm** in x over the 51.81 mm band — 617.6 mm² of sink, and it puts the holes through **Q3CL and Q6CL**. The board's free margin is **7.85 mm**; the field needs 18.27 |
| which option, and why | **none of (a)(b)(c)(d) survives** (a) 0.72 mm of sink margin, −13.42 uncovers 4 FETs → 521 °C; (b) largest free rectangle on the board is 162 mm² vs 315.5 needed, 0 of 3 sites; (c) the notch uncovers Q3CL/Q6CL → 521 °C; (d) 10.6 mm of depth exists vs 19.77, and fixing it costs +22.6 % area. **Pick: (b′) — the three columns stay at the sink's end and the board grows 13.42 mm in x**, zero thermal cost, nothing moved |
| Tj at 80 A after the change | **123.2 °C, unchanged** — the sink is untouched. Still **pad-limited** (45.6 K of 78.2 K is junction + Sil-Pad). The sink *could* give up 20 % for +7.7 K, but the 0.72 mm of aluminium beside the last FET is the real limit |
| total height | **55.80 mm** (unchanged; the bank moves in x only). Post tip z 19.95, 0.80 mm inside the socket |
| envelope | **151.77 × 122.55 mm plan** (was 138.35 × 122.55) × **55.80 mm tall**; sink still 125 × 74 × 34, 416 g, $44.5 |
| ASSEMBLES | **YES — but only as a board respin.** Not on the 138.35 mm outline, and the two-column stack did not assemble either (a pin drilled the BATN land) |

## 1. Real 3-column header footprint

### 1.1 Which part — 2-column parts, three of them

`TSW-120-15-G-D` and `SSW-120-01-G-D` are **2-column** (2×20 = 40 positions). Three of each gives the
120 positions the split needs: **H1 40 + H2 40 + H3 40**. A triple-row part would put 60 positions in one
seam — `2 × TSW-120-15-G-T` = 120 pins in two seams instead of three — and **I did not take it**, for a
reason that does not depend on whether that variant exists: on a 2.54 mm grid a triple-row body traps the
middle row, and the control board is **2-layer** (see §6), so the trapped row has no escape. Three
double-row headers give every pin a free side. (Samtec TSW product page, fetched 2026-11-17:
0.100 in pitch, 0.025 in square post, through-hole, "numerous lead styles, plating options and pin
configurations" — https://www.samtec.com/products/tsw. The triple-row variant is **not** something I
verified on that page; the geometry in §1.2 is the 2-column part, which is what is specified.)

### 1.2 The real x/y extents

Measured from the parts and from the pinsplit's own field area (`s4_numbers.json`: `header_field_cm2`
= 9.4657):

| quantity | one 2×20 | three columns |
|---|---|---|
| position grid | 2.54 × 2.54 mm | — |
| pin centres | 19 × 2.54 = 48.26 c-c | — |
| **body (TSW/SSW moulding)** | **5.08 × 50.80** (0.200 × 2.000 in) | **15.24 × 50.80** |
| **courtyard, 0.505 mm/side** | **6.09 × 51.81** | **18.27 × 51.81** |
| **field area** | 315.5 mm² | **946.6 mm² = 9.4657 cm²** |
| height above B.Cu | insulator 2.54 + post 13.21, OAL 18.54, tail 2.79 | same |

So the new field is **18.27 mm across × 51.81 mm along** — 3.58× the 5.10 mm the two-column site used.
That is the whole problem in one number: the right-hand margin of the power board is **7.85 mm** wide
(x 130.50 → 138.35, MEASURED from the board copy).

### 1.3 The actual overlap with the sink

If the three columns are forced into the existing board, the field has to start at
`138.35 − 1.5 − 18.27 = 118.58` mm — i.e. it **overlaps the sink by 130.50 − 118.58 = 11.92 mm**
across the 51.81 mm band y 20.0–71.81, **617.6 mm² of sink footprint**, and it sits on top of the
FET column at x 119.48–129.78:

| forced onto the 138.35 mm board | consequence |
|---|---|
| 51.81 mm of through-holes at x 118.58–129.78 | pierce Q3CL (21.7–34.3) and Q6CL (54.2–66.8) bodies **and their thermal pads** |
| sink under the same area | still present, but the 120 tails end at z = +1.41 (1.41 mm *above* the contact face) — the sink base is **not** the conflict, the FETs are |
| result | 2 FETs destroyed, 2 half-bridges dead → **not buildable** |

### 1.4 Two defects in the two-column site that were not in the record

Re-checking the site that the last wave filed as "1.0 mm clear", against the board copy
(`01_probe.py`, `03_numbers.py` §6):

1. **One pin drills through the BATN busbar land.** The header sat at y 20.0–70.8, so its rows are at
   21.27 + 2.54·k; row k = 9 is **y 44.13**, which is inside `BAR2` — a **118.30 × 4.50 mm single SMD pad
   on F.Cu, net `BATN`, x 17.00–135.30, y 42.00–46.50** (MEASURED). The pin at (132.77, 44.13) lands
   inside it; the mirror pin at 135.31 is 0.01 mm outside the land edge but its 1.7 mm pad overlaps by
   0.84 mm. **The 2×20 site shorted the header to the 0 V bus.**
2. **The site does not fit its own y-segment either.** The right margin is broken by three busbar lands
   and two Ø3.2 mounting holes into segments of **30.4 mm** (y 11.6–42.0) and **35.5 mm** (y 46.5–82.0).
   A 2×20 needs **51.81 mm**. It fit only by crossing `BAR2`.

Both are fixed by the layout in §2, and both matter: any answer that keeps the old site is wrong.

## 2. Layout re-solve — four options with numbers

### 2.1 The constraint that decides everything

The sink is **the FET-field outline, not a thermal choice** (MEASURED, `01_probe.py` / `10_power_geom.json`):

| | left | right | top (y) | bottom (y) |
|---|---:|---:|---:|---:|
| FET body envelope | 8.28 | 129.78 | 7.90 | 80.60 |
| sink outline | 5.50 | 130.50 | 7.00 | 81.00 |
| **margin** | 2.78 | **0.72** | 0.90 | 0.40 |

The sink can be moved **0.72 mm** to the right before the last FET column (x 124.58, body
119.48–129.78, thermal pad to 129.68) hangs off it. **There is no "inboard" to move to.** This is why
option (a) dies for a geometric reason, not a thermal one.

### 2.2 The four options, measured

| # | option | what it needs | the number that kills it | Tj at 80 A |
|---|---|---|---|---|
| **(a)** | shrink/move the sink inboard | sink right edge at ≤ **117.08** (width 125 → **111.58**, −13.42) | the sink is 0.72 mm from the FET field; −13.42 uncovers **Q3CH, Q3CL, Q6CL, Q6CH** (x 124.58, 4 of 36 devices = 49.8 W). No sink → RthJA 40 °C/W → **Tj = 521 °C** | 126.9 °C *if* the FETs could stay on it — they cannot |
| **(b)** | three narrower positions around the sink | 3 × 315.5 mm² of F.Cu-free land | 0.1 mm raster of the whole board (941 F.Cu pads, 96 part bodies): free 4940 mm² (29.1 %) but the **largest free rectangle is 162 mm²** → **0 of 3 sites exist**; the only 7.80 mm strips (x 43.58–51.38, 86.68–94.48) are inside the sink, carry the Ø3.3 clamp screws, and would run the PWM and analogue lines between the half-bridges | n/a |
| **(c)** | sink notch | notch 13.42 × 51.81 at the sink's right edge | 695.2 mm² = **7.52 % of the sink**, 8 fin channels — cheap thermally (**+1.1 K**) but the notch band y 20–71.8 is exactly where **Q3CL (21.7–34.3) and Q6CL (54.2–66.8)** sit at x 119.48–129.78 → **2 FETs lose the sink → 521 °C** | 124.3 °C *if* the notch avoided the FETs — it cannot (any notch ≥ 0.72 mm hits them) |
| **(d)** | three columns along the sink's long edge | 18.27 mm clear depth at y ≥ 82.5 | deepest clear band between the motor lands (89.7–92.9) and the can bodies (103.5–121.5) = **10.6 mm** vs 19.77 needed → **9.2 mm short**; can be bought by moving the 6 cans 8.2 mm rearward + growing the board 8.2 mm in y, but the control board must then be **105 × 98** → chip area 180.9 + 102.9 = **~284 cm² (+22 %)** and an 8.2 mm longer can loop | 123.2 °C (sink untouched) |

*(c) and (d) are both thermally survivable and geometrically not. (a) is neither. (b) does not have a
site. Every option that keeps the sink intact puts the columns where the board has no area, and every
option that makes area puts the columns on a FET.)*

### 2.3 The pick: **(b′) three columns at the sink's end, board extended 13.42 mm in x**

The three columns stay where the two were — in the only F.Cu-free margin on the power board — and the
margin is made wide enough. This is (b)'s intent (three positions at the sink's end) with the width
bought from board area instead of from the FET field. **It is the only option with zero thermal cost,
zero re-layout of the power stage, and no FET, can, motor land or standoff moved.**

| item | before | after | note |
|---|---|---|---|
| bank | 1 × 6.09 × 51.81 | **3 × 6.09 × 51.81 at x 132.00–150.27, y 20.00–71.81** | 18.27 × 51.81 courtyard |
| sink | 125 × 74 at (5.50–130.50, 7.00–81.00) | **unchanged** | 1.50 mm to the field; **2.64 mm to the nearest FET copper**, 1.92 mm to the trimmed BATN land |
| power board | 138.35 × 122.55 | **151.77 × 122.55** | +13.42 mm in x, = **+16.44 cm²** (169.55 → 185.99) |
| busbar lands BAR1/2/3 | x 17.00–135.30 | **x 17.00–130.50** | −4.80 mm at the outboard end; **required** — today `BAR2` (BATN) is crossed by the header pin at (132.77, 44.13) |
| control board | 105 × 60 | **107 × 60 at x 44.10–151.10, y 14.00–74.00** | 2.6 % more area; keeps a 3.4 mm screw margin at x 47.5 and covers the bank to 150.27 |
| board cost | $214–285 | **$235–313** | +$21–28 (at $1.26–1.68/cm²) |
| total area | 232.7 cm² | **250.2 cm²** | still **−34.6 %** vs the 382.71 cm² single board |

**Verified, not asserted** (`04_place_check.py`, 120 pins against every F.Cu pad, pad body and the
retrimmed lands):

```
pins checked: 120
min copper-edge distance : 2.77 mm   (to the trimmed BAR2 pad; pad edge 1.92 mm)
min part-body distance   : 3.49 mm   (to Q3CL)
pins inside a 0.30 mm copper halo: 0
nearest pin centre to the sink edge x = 130.50 : 2.77 mm  (courtyard 1.50 mm)
nearest pin centre to the new board edge 151.77: 3.78 mm  (pad edge 2.93 mm)
all 120 pins inside the 107 x 60 control board with >= 1.0 mm margin: True
```

**Requirement check — ≥ 1.5 mm on all four sides:** sink edge **1.50**, new board edge **1.50**,
trimmed busbar land **1.50** (and 2.64 mm of copper-to-copper to the nearest FET), and in y the field
sits 20.0 mm from the board edge and 17.9 mm from the nearest motor land. **Met, exactly, on the two
sides that are tight.**

**Residual, stated so it is not discovered later:** at 6.09 mm pitch the mouldings are 1.01 mm apart, so
there is no routing channel *between* the three headers. Each header's 40 pins must escape off its own
ends (y < 20.0 and y > 71.81 are clear board). On a 2-layer control board that is 8 escape tracks per gap
in the best case and none of the middle header's inner row gets between-body routing. **If the control
board's escape needs channels, the pitch must be 7.62 mm/column (2.54 mm gaps) → field 22.32 mm wide →
board 155.82 mm and a 111 × 60 control board.** I recommend routing the control board first and only
then committing the board outline; the 18.27 mm figure is the one the pinsplit's 9.4657 cm² counts.

## 3. Thermal consequence of the choice

### 3.1 The pick costs nothing, because nothing thermal moved

The sink keeps 125 × 74 at (5.50–130.50, 7.00–81.00), the fin field, the base, the 0.25 mm Sil-Pad and
the 36 pads are untouched, and the bank moved in **x** only. So:

| | as filed (two columns) | with the three-column pick |
|---|---:|---:|
| Q at 80 A/phase | 448.0 W | 448.0 W |
| Rth_sink-to-air | 0.0661 K/W | **0.0661 K/W** |
| Rth_sink total | 0.0727 K/W | **0.0727 K/W** |
| T_sink | 77.6 °C | **77.6 °C** |
| Rth_TIM (Sil-Pad 2000 0.010 in, 3.43 K/W) | 3.43 K/W | **3.43 K/W** |
| **Tj at 80 A** | **123.2 °C** | **123.2 °C** |

Still 26.8 K under the 150 °C limit, and **still pad-limited**: of the 78.2 K rise, **45.6 K is the
junction + Sil-Pad** and only **32.6 K is sink-to-air** (CALCULATED, `03_numbers.py`).

### 3.2 Is a smaller sink "nearly free"? Thermally yes — geometrically impossible

Sweeping the sink narrower in x with the same fin family (`03_numbers.py`, Rth ∝ 1/fin area):

| sink width | % of 125 mm | Rth_sink total | Tj at 80 A | ΔTj | mass |
|---:|---:|---:|---:|---:|---:|
| 125.00 | 100 % | 0.0727 | **123.2 °C** | — | 424 g |
| 118.75 | 95 % | 0.0762 | 124.8 °C | +1.6 K | 403 g |
| 112.50 | 90 % | 0.0801 | 126.6 °C | +3.4 K | 382 g |
| 106.25 | 85 % | 0.0843 | 128.6 °C | +5.4 K | 360 g |
| 100.00 | 80 % | 0.0893 | 130.9 °C | +7.7 K | 339 g |
| 93.75 | 75 % | 0.0948 | 133.5 °C | +10.3 K | 318 g |
| **111.58** | **89 %** | 0.0810 | **126.9 °C** | **+3.7 K** | 378 g |

**So the assignment's premise is right and it does not help: the sink could give up 20 % of its area for
+7.7 K.** The exact shrink option (a) asks for — 125 → 111.58 mm — costs **+3.7 K**. What it also does is
drop the sink off **Q3CH, Q3CL, Q6CL, Q6CH** (x 124.58; their 10.2 × 7.0 mm pads start at x 119.48, which
is 2.40 mm past the new edge). Those four are 4/36 of the loss = **49.8 W**; with no sink they run on
RthJA 40 °C/W → **Tj = 45 + 11.9 × 40 = 521 °C**. The thermal budget was never the constraint; the
0.72 mm of aluminium between the last FET and the sink's edge is.

### 3.3 If more margin is ever wanted, price the interface — not the sink

| interface | Rth_TIM | Tj at 80 A | ΔTj | cost delta (ESTIMATE) |
|---|---:|---:|---:|---:|
| Sil-Pad 2000 0.010 in (as filed, 4 kV) | 3.43 K/W | 123.2 °C | — | — |
| Sil-Pad 2000 0.006 in | 2.35 K/W | **110.3 °C** | **−12.9 K** | +$0.10–0.20/device = **+$3.6–7.2/ESC** |
| PTM7950-class phase change (0.08 °C·in²/W) | 0.72 K/W | 90.9 °C | −32.3 K | ~+$0.15/device — **but it is not an insulator** |

The thin pad is the cheap lever and it is **not needed**: the design is 26.8 K inside its limit and the
sink is not the limiter. The phase-change option is listed only to be rejected — the FET's cooling pad is
the phase node at 44.4 V against an earthed aluminium sink, so an isolating pad has to stay in the stack,
and adding one back restores most of the 0.72 K/W. **The Sil-Pad 2000 0.010 in stays.**

## 4. Stack update and header post reach

Nothing in z moved — the bank relocated in x and y inside an existing layer — so the ladder is
identical and the stack is still **55.80 mm**:

| z from | layer | thk | z to |
|---|---:|---:|---:|
| −34.00 | fin field: 16 fins × 2.0, pitch 4.625 | 30.00 | −4.00 |
| −4.00 | base plate 6061-T6, machined contact face | 4.00 | 0.00 |
| 0.00 | thermal interface Sil-Pad 2000 0.010 in | 0.25 | +0.25 |
| +0.25 | FET PG-HDSOP-16: pad on the TIM, board above | 2.35 | +2.60 |
| +2.60 | power PCB, 4-layer 3 oz (**now 151.77 wide**) | 1.60 | +4.20 |
| +4.20 | air gap = header + 4 × 10 mm standoffs | 10.00 | +14.20 |
| +14.20 | control PCB 2-layer (**now 107 × 60**) | 1.60 | +15.80 |
| +15.80 | tallest control part, Bourns SRR1260 | 6.00 | +21.80 |
| | **TOTAL, fin tip to control-part top** | | **55.80** |

**Post reach, re-checked for the new site** (`03_numbers.py`): gap 10.00 mm, so the post must clear
10.00 + 1.60 + 0.80 = **12.40 mm** above the power board's B.Cu face.

| | value |
|---|---|
| TSW-120-15-G-D insulator | z 4.20 → 6.74 (2.54) |
| post | 13.21 → tip at **z 19.95** |
| SSW-120-01-G-D body on the control board | z 15.80 → **20.75** (4.95) |
| **tip below the socket's top face** | **0.80 mm — by design** |
| tails | 2.79 → end at **z 1.41**, i.e. 1.41 mm above the sink's contact face |
| tails over the sink? | **no** — the bank starts at x 132.00, the sink ends at 130.50 |

Unchanged part, unchanged geometry: 3 × TSW-120-15-G-D + 3 × SSW-120-01-G-D. **Cost triples** with the
third column: $12.53/pair at 1-off → **$37.59 for the set** ($32.19 at 100), i.e. **+$25.06 per ESC**
against the two-column stack. At $310–390 per ESC total it is still 0.46–0.58× the $675 cap floor.

## 5. Updated dimensioned section drawing and final envelope

Sheet: **`05_sink_clearance.png`** (`05_section.py`), five panels —
(a) plan of the 151.77 × 122.55 board with the sink, the bank, the trimmed lands and both 1.50 mm gaps;
(b) section A-A at y 28.00 through a FET row and the bank, with the z ladder and the 1.50 mm gap;
(c) detail of the field on a 2.54 grid; (d) the four options with verdicts; (e) the stack ladder.

**FINAL ENVELOPE**

| | value |
|---|---|
| plan | **151.77 × 122.55 mm** (was 138.35 × 122.55; **+13.42 mm in x**) |
| height | **55.80 mm** (unchanged) |
| heatsink | 125 × 74 × 34, 416 g, 6061-T6, unchanged; still $44.5 @ 5 pcs |
| board area | power **185.99 cm²** (was 169.55) + control **64.20 cm²** (was 63.00) = **250.19 cm²** |
| vs the 382.71 cm² single board | **−34.6 %** |
| vs the two-column split (232.7 cm²) | +7.5 % |

## 6. Does the stack assemble with the three-column pin split?

**Not as filed — and the two-column stack did not either.** Three answers, in order:

1. **The 138.35 mm board, three columns: NO.** The field is 18.27 mm; the only F.Cu-free margin is
   7.85 mm. Forced on, it overlaps the sink by 11.92 mm and puts 51.81 mm of through-holes through
   **Q3CL and Q6CL** and their thermal pads.
2. **The two-column stack as filed: also NO**, for two reasons that were not in the record: one pin at
   (132.77, 44.13) **drilled through the BATN busbar land** (`BAR2`, a 118.30 × 4.50 mm F.Cu pad), and
   the 51.81 mm header did not fit either of the margin's free y-segments (30.4 and 35.5 mm) — it fitted
   only by crossing that land.
3. **With the pick (option (b′)): YES.** 3 × 2x20 at x 132.00–150.27, y 20.00–71.81 on a 151.77 mm
   board with the sink untouched — verified pin by pin against the real board: **120 pins, 0
   violations, 2.77 mm from a pin centre to the nearest pad edge (1.92 mm copper-to-copper), 3.49 mm to
   the nearest part body, 1.50 mm to the sink and 1.50 mm to the new board edge, every pin inside the
   107 × 60 control board with ≥ 1.0 mm margin.**

**ASSEMBLES: yes — conditional on one board respin (+13.42 mm in x, the three busbar lands trimmed to
x 130.50, the control board at 107 × 60).** Zero change to the sink, the FETs, the cans, the standoffs,
the thermal path or the 55.80 mm height.

### What this does not cover

- **Control-board escape routing is not done.** At 6.09 mm pitch the mouldings are 1.01 mm apart; the
  middle header's inner row cannot route between headers on 2 layers. If the escape needs 2.54 mm
  channels, the field becomes 22.32 mm wide → board 155.82 mm and a 111 × 60 control board
  (**+4.05 mm more than the 151.77 quoted**). Route the control board before committing the outline.
- **The busbar lands are trimmed 4.80 mm at one end without a current check.** The lands are solder
  area, not conductors, but the busbar-to-land joint area falls ~4 %; the bars themselves can stay long.
- **The can-to-header spacing and the analogue crosstalk are unchanged but not re-derived.** The field's
  near edge is 0.5 mm further from the phase field than before (x 132.00 vs 131.50) and its far edge
  13.7 mm further (150.27 vs 136.60); the pinsplit's 0.215 mV (0.020 % FS) figure was computed for a
  header outside the phase field, which this still is.
- **Nothing was routed, poured or DRC'd.** The board is a placeholder-level layout; this is a
  placement/clearance solve, verified numerically, not a released board.

## Appendix — provenance and reproduction

| claim | tag | source |
|---|---|---|
| board outline 138.35 × 122.55, 941 F.Cu pads, 3 busbar lands, 36 TOLL pads, 6 cans | MEASURED | `01_probe.py`, `pcbnew` 9.0.7 on `pwr_copy.kicad_pcb` (a copy of `evidence/esc-split-power/esc_power_board_full.kicad_pcb`) |
| sink is 0.72 mm from the last FET body; FET field 8.28–129.78 × 7.90–80.60 | MEASURED | `10_power_geom.json` (the stack wave's own read of the same file) |
| **one pin at (132.77, 44.13) lands inside `BAR2` (BATN, x 17.00–135.30, y 42.00–46.50)** | MEASURED | `01_probe.py` pad dump; `03_numbers.py` §6 |
| 941-pad free-space raster: 4940 mm² free (29.1 %), largest rectangle 162 mm² | MEASURED | `02_freespace.py` (0.1 mm raster, pads + 0.30 mm, part bodies, edge margin) |
| 3 × 2×20 = 18.27 × 51.81 = 946.6 mm² = 9.4657 cm² | CALCULATED | matches the pinsplit's own `header_field_cm2` 9.4657 |
| TSW-120-15-G-D post 13.21 / OAL 18.54 / tail 2.79; SSW body 4.95 / tail 2.64; TSW is 0.100 in pitch, 0.025 in post, through-hole | PUBLISHED | Samtec TSW product page, fetched 2026-11-17: https://www.samtec.com/products/tsw (carried from `esc-stack-v2` §3a for the lead-style numbers) |
| Tj, Rth, the sink sweep, the TIM rows | CALCULATED | `03_numbers.py` — same fin model and constants as `esc-stack-v2/13_model.py` (Q 448 W, 11.9 W/device, Rth_jc 0.40, Sil-Pad 0.38 °C·in²/W, Ta 45 °C, h 150 W/m²K) |
| 4 FETs at x 124.58 = 49.8 W, Tj 521 °C without a sink | CALCULATED | 4/36 × 448 W; RthJA 40 °C/W PUBLISHED (Infineon PG-HDSOP-16) |
| pin-by-pin clearance of the chosen field | MEASURED | `04_place_check.py`, `04_place_check.json` |
| TIM price deltas | ESTIMATE | distributor pricing bands, not a quote — web search was unavailable in this session (the `duckduckgo` provider was not registered; `web_fetch` on the Samtec page did work) |

Files in this directory:

```
REPORT.md                this report
01_probe.py              board copy: outline, busbar lands, zones, margin pads, tracks/vias
02_freespace.py/.json    0.1 mm free-space raster and maximal free rectangles
03_numbers.py/.json      footprint, four options, thermal sweep, stack, envelope, clearances
04_place_check.py/.json  the chosen field, 120 pins vs every pad/body/edge
05_section.py            the sheet
05_sink_clearance.png    plan + section A-A + detail + options + ladder
pwr_copy.kicad_pcb       working copy (never written back)
```

No repo was touched, nothing was committed, and every measurement above was taken on a copy.

