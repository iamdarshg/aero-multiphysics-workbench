# ADVERSARIAL VERIFY — ESC two-board split (power + control)

Verifier session, independent of both design units. All reads are copies; nothing written into a
repo, nothing under `D:\CodeProjects` or `E:\1vm\TMP`. Own evidence dir:
`E:/engineering-portfolio-audit/evidence/esc-split-verify/`.

Inputs: `esc-split-power/REPORT.md`, `esc-split-control/REPORT.md`, and the KiCad files they cite.

| step | what | state |
|---|---|---|
| 0 | skeleton | done |
| 1 | COST: own price check, 1.5x arithmetic | done |
| 2 | AREA: measured on the actual files | done |
| 3 | AMPACITY: k, A/barrel, table recompute | done — one real error found |
| 4 | GATE LOOP across the 2.54 mm header | done — quantified, correct |
| 5 | HEATSINK: volume + header clearance | done — **FAIL** |
| 6 | HDI / single-sided | done |
| 7 | CONSTRAINT_VIOLATION / CREDIBLE / VERDICT | done |

Tools: `C:\Program Files\KiCad\9.0\bin\python.exe` (pcbnew 9.0), `kicad-cli` 9.0.7, live web fetch.
Scripts `v01`–`v07` and their logs sit beside this file.

---

## 1. COST — does the two-board total come in under 1.5x?

### 1.1 What I checked at source, today

| item | published | source |
|---|---|---|
| PCBWay 2-layer 100 x 100 mm, 5 pcs, 1 oz, 1.6 mm, HASL | **$5.00** | fetched 2026-11-17, `/pcb_prototype/2_Layer_pcb/100x100mm.html` |
| PCBWay 4-layer 150 x 100 mm, 5 pcs, 1 oz | **$116.00** | fetched 2026-11-17, `/pcb_prototype/4_Layer_pcb/150x100mm.html` |
| PCBWay 4-layer 100 x 100 mm, 5 pcs, 1 oz | $48.00 | the reports' cited page (unchanged) |
| PCBWay heavy copper 3 oz | **no price published** — "Build time 5–10 days", capability table only | fetched 2026-11-17, `/pcb_prototype/Thick_Copper_PCBs.html` |
| PCBWay standard capability: outer 3 oz = 105 µm is standard; min spacing 0.1 mm; min annular 0.15 mm | confirmed | same domain, `/capabilities.html` |

Two useful confirmations that go **against** my own initial suspicions: 3 oz needs no special
clearance (the 13 mil minimum on the heavy-copper page is the 4 oz rule, not 3 oz), so the power
board's 0.15 mm DRC rule is inside capability; and the residual annular 0.150/0.175 mm violations of
the old board are exactly at PCBWay's 0.15 mm standard annular limit — legal, no margin.

### 1.2 My own arithmetic, 5 pcs, USD

The board of record's 4-layer 1 oz list at 169.7 cm², on the same two published points the programme
uses (slope $1.36/cm², intercept from 100 cm² = $48):

`48 + 1.36 x (169.68 − 100) = $142.7`

| line | low | high | basis |
|---|---:|---:|---|
| power board, 4L 3 oz, 169.7 cm² | $214 | $285 | $142.7 x 1.5–2.0 (**ESTIMATE** — no fab publishes 3 oz) |
| control board, 2L 1 oz, 80 x 50 mm | $5.00 | $5.00 | **PUBLISHED** |
| 2.54 mm header pair | $0.28 | $0.41 | LCSC, per the two reports (they disagree: 2x20 $0.2758 vs 2x15 $0.4131) |
| mating connectors (2x JST-GH, Micro-Fit DNI) | $9.04 | $9.04 | LCSC |
| **fab + headers + connectors** | **$228** | **$299** | |

Against $450–870: **0.26x – 0.66x**. The 1.5x cap is not close to binding on fab.

**Robustness to the one unmeasured input.** The 1.5–2.0 heavy-copper multiplier is an ASSUMPTION.
Push it to 3.0x: power board $428, total **$442** — still under the $675 floor of the cap and equal to
the low end of the $450 baseline. The PASS on fab survives a 3x multiplier, so it does not depend on
the guess being right.

**The heatsink is what decides the cap:**

| build | total, 5 pcs | vs cap $675–1305 | vs baseline $450–870 |
|---|---:|---|---|
| fab only (no sink) | $228–299 | PASS | 0.26x–0.66x |
| + extruded 261AS, milled lands ($245) | **$473–544** | **PASS** | 1.05x low-to-low / 0.63x high-to-high |
| + machined 120x90x25, cost-unit est. ($200–450) | $428–749 | PASS at $428; **$749 leaves $0 margin** at the $675 floor | 0.95x / 0.86x |
| + machined 150x260x38 on the mech model ($635) | **$863–934** | **FAIL — 1.28x the cap floor** | **1.92x the baseline floor** |

**Cap holds iff the heatsink costs ≤ about $390 for 5 (≤ $78/part).** An extruded profile or a modest
machined block is inside that; a 1.6 kg machined-from-solid block at $127/part is not.

### 1.3 The accounting flaw that inflates the reported ratios

The baseline ($450–870) is **fab only**. The control report's "$436–496 all-in" adds a $245 heatsink
to a fab-only baseline and calls the result a ratio. Like-for-like it should be either fab-vs-fab
($228–299 vs $450–870) or all-in-vs-all-in (and the incumbent also needed its 352–528 cm² spreader,
which is *not* in its $450–870). Either comparison passes; mixing them makes the number
unfalsifiable. State which basis the cap is applied to.

### 1.4 Cost verdict

**PASS — the two-board total is 0.26–0.66x of the current board on fab, and stays under 1.5x with any
heatsink up to ~$78/part. It FAILS 1.5x only in the worst machining estimate (1.28x the cap floor).**
Absolute numbers remain soft on both sides: the $450–870 baseline is `ESTIMATE (list x multiplier)`
by the programme's own record, and 3 oz is unquoted at every house.

---

## 2. AREA — is the power board really significantly smaller?

### 2.1 Measured, my own run (`v01`, `v02`, `v06`)

| board file | outline | area | fp | vias | tracks | B.Cu parts |
|---|---:|---:|---:|---:|---:|---:|
| `esc-split-power/esc_power_board_v1` (power stage) | 138.4 x 88.6 | **122.40 cm²** | 119 | 0 | 0 | 0 |
| `esc-split-power/esc_power_board_full` (**as split**) | 138.4 x 122.6 | **169.42 cm²** | 173 | 0 | 0 | 0 |
| `esc_base` (current board of record) | — | **491.73 cm²** | 687 | 1,990 (all through) | — | 0 |
| `esc_rev_b_powerfirst` (the 382.71 baseline) | 155.15 x 246.8 | **382.71 cm²** | 687 | **0** | **0** | 0 |

- **The 382.71 cm² baseline is an unrouted re-placement** — 687 footprints, zero tracks, zero vias,
  zero zones. The routed board of record is 491.73 cm². Comparing the new unrouted placement
  (169.42) to the old unrouted placement (382.71) is like-for-like and fair; just do not call 382.71
  "the board".
- **169.42 vs 382.71 = −55.7 %** (the report says −55.66 % using the 169.68 bbox: arithmetic correct).
  vs 491.73 = −65.5 %. Power stage alone: 122.40 = −68.0 %.
- The control report's **"118.2 cm² = 69 % smaller" is a mis-measure of the same file**: it quotes
  133.4 mm width where the edge cuts are 138.4 mm. Correct is 122.40 cm² = **−68.0 %**, not −69 %.
  Small error, but it is the number that propagated into its cost table (120 cm² row) and into
  "total 158 cm²".

### 2.2 The correction that matters: 173 footprints is not the power board

The as-split file carries **173 of the 582 power-side footprints**. Its parts are systematically
smaller than the same parts on the board of record (bbox, mine):

| part | on the board of record | on the as-split board | factor |
|---|---|---|---|
| IPTC014N10NM5 (36) | 11.6 x 16.5 = 1.91 cm² | 10.3 x 12.6 = 1.30 cm² | 1.47x |
| 0.5 mΩ shunt (18–24) | 9.2 x 11.0 = 1.01 cm² | 0.42 cm² | 2.4x |
| **820 µF 100 V can (6)** | **19.1 x 20.2 = 3.86 cm²** | **8.0 x 8.0 pad = 0.64 cm²** | **6.0x** |
| **motor terminal (6 lugs, 18 phases)** | **54.3 x 16.3 = 8.87 cm² each = 64.85 cm²** | **6 x 3.2 mm pad = 3.46 cm² total** | **18.7x** |
| busbar land | (12 battery lugs = 33.60 cm²) | 3 x 15.97 cm² | deleted, correct |

An 18 mm-diameter electrolytic cannot occupy an 8 x 8 mm footprint — that correction is
unconditional: **+19.3 cm² → 188.7 cm² (−50.7 %)**. The six motor lugs are the split's biggest single
"deletion", but the split does not delete the motors: they still draw 80–109 A per phase through 18
terminals, so either the design accepts 18 solder pads at 6 x 4 mm (a real choice, and 109 A through
24 mm² of 3 oz is 7x under the 20 K long-run rule — it is a neck, not a run) or the 64.85 cm² comes
back: **+61.4 cm² → 250.1 cm² (−34.6 %)**.

Also: the six caps on the generated board are valued **`820uF_35V`** — 35 V on a 44.4 V 12S bus. The
board of record uses 820 µF/**100 V**. That is a BOM defect in the file the area claim is measured on.

### 2.3 Area verdict

**Yes, significantly smaller — but 35–50 %, not 56 % and certainly not 69 %.** The defensible power
board is **189–250 cm² (−50.7 % to −34.6 %)**; 169.42 cm² is a power-path core with 30 single-pad
placeholders standing in for ~96 small parts per cell, and two part classes drawn far below their real
size. Total two-board area as filed 209.4 cm² (−45.3 %); corrected 290 cm² (−24 %). Control board's
40.0 cm² has **no board file at all** — it is courtyard 17.65 ÷ 0.45 packing, an estimate.

---

## 3. AMPACITY — k, and A per barrel

`02_currents.py` uses `k = 0.048` external, `0.024` internal, `dT = 20 K`, `1.50 A` per barrel —
correctly, everywhere. I re-derived the barrel rating independently: a 0.4 mm hole through 25 µm is
`πDt = 0.0314 mm² = 48.7 mil²`; `I = 0.024 x 20^0.44 x 48.7^0.725 = 1.50 A`. So 1.50 A **is** the
internal-layer (k 0.024) rating, and using it with k 0.048 elsewhere would be double counting — the
report does not. The 3.00 A figure appears only as `barrels_at_3A_wrong`, a labelled cross-check.
**No violation of hunt item 3 on method.**

**But there is a transcription error.** `REPORT.md` §1.3's inner-layer column prints
**23.3 / 32.4 / 49.6 mm**; its own `02_currents.json` holds **38.9 / 54.09 / 82.87 mm**. I recompute
38.9 mm by hand for 62.95 A on 140 µm at k 0.024, so the JSON is right and the table understates the
inner-layer width by **1.67x**. It does not change the conclusion (the shared-bus table in §2.2 uses
the correct 571.1 mm), but anyone routing a phase on an inner layer from that table would be 40 %
undersized.

Checks that stand: 441.8 A / 1.5 = **295 barrels** ✓; 8.2 mm x 4 x 105 µm = 3.44 mm² → 90 A at
k 0.024 (99.8 A mixed outer/inner — their figure is conservative) ✓; R = 6.0 µΩ and 71 mW at 109 A
over 1.2 mm ✓.

---

## 4. GATE LOOP across the 2.54 mm header

**In the delivered partition: 0 nH added.** No gate net crosses — verified against both reports'
pin tables. The six DRV8353 and six cell MCUs stay on the power board.

**If a gate pair were forced across** (`hdr/calc.json`): 0.64 mm square post, 2.54 mm pitch, 10 mm
mated, return on the adjacent pin → **8.29 nH** (7.71 nH GMR-refined); return on the far connector →
**17.5 nH**. I verified the per-unit figure from first principles: `(µ0/π)·ln(s/r) = 0.4·ln(2.54/0.32)
= 0.829 nH/mm` — the report's 0.8286 is right, and it is a loop figure (both conductors), so 8.29 nH
for 10 mm is not double counted.

Ringing, with R_total = 2.4 Ω (2.2 Ω gate + 0.2 Ω driver) and C 12 nF: 0.417 → 0.542 → 0.653; overshoot
0 / 0.05 % / 2.38 %. Arithmetic checks (Q = (1/R)√(L/C); OS = exp(−πζ/√(1−ζ²)) at ζ = 1/(2Q)).
Extra switching loss 3.8 W across 36 devices. **Rg → 2.7 Ω restores Q ≈ 0.45.**

The stronger number is the shunt, and it is the one that decides the architecture: a 2.54 mm header
pair at 5.45 A/ns couples M = 13.55 nH → **73.8 mV into a 54.5 mV full scale (135 %)** vs 1.11 nH /
6.03 mV on-board. Measurement cannot cross. Correctly stated in both reports.

**Caveat, and it is a requirement issue, not a maths one:** 0 nH is *bought* by keeping six of the
seven MCUs and every analog front end on the power board. The owner asked for "the measurement, the
BEC and MCU" on the control board. The control report argues this deviation openly (§1.3); the power
report's summary does not, so read as a deliverable the split under-delivers on requirement 1.

---

## 5. HEATSINK — volume, and does the 2.54 mm header clear it?

**The volume is stated, and the arithmetic is right:** 130 x 70 x 25 mm envelope = **227.5 cm³**,
61.6 cm³ of aluminium (27.3 base + 34.3 fins), **166 g**, 663 cm² wetted, Rth 0.101 K/W at
h 150 W/m²K. Heat rejected 448 W at 650 km/h. 0.10 C/W is self-consistent with h; h itself is
ASSUMED (a 5.2 mm fin channel at 167 m/s is near-choked — this is the number to measure).

**The stack does not close.** The power report's stack is
`1.60 + 1.30 + 0.25 + 25.0 + 2.0 + 1.60 = 31.75 mm`, i.e. **board-to-board 28.55 mm**, so the post
must reach `28.55 + 1.60 + 1.0 = 31.15 mm` above the power board. Published Samtec TSW:
- `-08` post 5.84 mm → tip 8.38 mm — **22.8 mm short**
- `-15` post 13.21 mm → tip 15.75 mm — **15.4 mm short**
- only lead style `-26` (30.99 mm post, tip 33.5 mm) reaches — **and neither report specifies it.**

Three independent clashes, all measured:

1. **Header length** — needs a 30.99 mm-post part that is not in the BOM. A standard mated pair
   reaches 8.38 mm.
2. **Header site vs sink footprint** — the report reserves the 2x15 at **x 131.5–136.6**; a 130 mm
   sink centred on a 138.4 mm board spans **x 4.2–134.2**, overlapping the header by **2.7 mm**. The
   border outside the sink is 4.2 mm per side; a 2x15 body is 5.08 mm plus pads.
3. **The six 820 µF/100 V cans are 31–35.5 mm tall** (measured footprint `CP_Radial_D18.0mm_P7.50mm`
   on the board of record) and sit on the power board's top face. The gap is **28.55 mm**. They
   pierce the stack by **2.5–7 mm**. The power report's stack table does not mention them.

The control report's alternative (sink underneath, 10 mm gap, header clears with TSW-125-15) is
mechanically sound — but it achieves that by **soldering 36 FETs on B.Cu**, which is the forbidden
back-side component. **So the split has no compliant stack as drawn: on top = header and caps clash;
underneath = back-side FETs.**

---

## 6. HDI / single-sided

| board | layers | blind/buried | B.Cu SMD | verdict |
|---|---:|---:|---:|---|
| power v1 / as split | 4 / 4 | 0 | 0 | **clean** (100 % F.Cu, 0 vias at all — unrouted) |
| control (as specified) | 2 | 0 | 0 | clean for SMD; its 2x20 header body is on the **bottom** face |
| control (recommended stack) | — | — | **36 FETs flipped to B.Cu** | **VIOLATION** |

Note the structural tension the owner must rule on: any two-board stack has one connector on the
mating face of each board. If "no back-side component" is literal, requirement 4 and requirement 6
are mutually unsatisfiable — the rule needs to read "no back-side SMD".

---

## 7. FINDINGS

**COST — PASS.** 0.26–0.66x on fab; ≤1.5x with any sink up to ~$78/part; 1.28x the cap floor only
with the $127/part machined block. Both absolute sides are estimates; 3 oz is unquoted everywhere.

**AREA — PASS, with a corrected number.** 169.42 cm² measured = −55.7 % as filed; **189–250 cm²
(−50.7 % to −34.6 %)** once the 820 µF cans (6x) and the motor terminals (18.7x) are drawn at their
real size. "Significantly smaller" holds either way. The control unit's −69 % is a mis-measure of the
same file (133.4 mm vs 138.4 mm width).

**AMPACITY — method correct, one table wrong.** k 0.048/0.024 and 1.50 A/barrel all correct;
§1.3's inner column is 1.67x too small against its own JSON.

**GATE LOOP — quantified and correct.** 0 nH as built (no gate net crosses); 8.29 nH adjacent-return
/ 17.5 nH far-return if forced, Q 0.54/0.65, Rg 2.7 Ω restores margin. Shunt coupling 73.8 mV into
54.5 mV FS is the real blocker and is right.

**HEATSINK — FAIL.** Volume stated (227.5 cm³, 166 g) but the stack needs an unspecified 30.99 mm-post
header, the header site overlaps the 130 mm sink by 2.7 mm, and six 31–35.5 mm cans pierce a
28.55 mm gap.

**HDI — none. Single-sided — clean on both boards as filed, violated by the control report's
recommended B.Cu FET flip.**

**CONSTRAINT_VIOLATION: YES.** (a) the board-to-board connector is specified as **2x15/30 positions**
by the power unit and **2x20/40 positions** by the control unit — mutually exclusive; (b) the stack in
§5; (c) 36 FETs on B.Cu in the control report's recommendation; (d) "MCU + measurement on the control
board" is not delivered — 6 of 7 MCUs and all shunt front ends stay on the power board.

**CREDIBLE: PARTLY.** The method is good and the two hard requirements are met on their own terms
(cost, and a smaller power board), but the published percentages (−55.7 %, −69 %) and the
architecture's only assembly stack do not survive measurement.

**VERDICT:** cost is compliant and the power board is genuinely smaller, but the split is **not
buildable as specified** until the header/stack is redesigned (single post-length decision + cap
cutouts + sink width), the connector position count is unified at 40, and the area headline is
restated at ~35–50 %.