# ESC rev_B — build at the settled 36.6 A point (4-layer, 3 oz outer)

**Wave 18 closing specialist report.** Assignment: build the ESC at its settled design point
— **36.6 A per phase / 33.7 A bus**, 4-layer, 3 oz (105 µm) outer — and push it as close to
fab-ready as the constraints allow. Closing wave: a finished, honest partial is preferred over
an unfinished whole.

Evidence dir: `E:/engineering-portfolio-audit/evidence/esc-36a-build/` — all work on copies.
Input (never written): `E:/engineering-portfolio-audit/repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`.
Prior evidence read: `evidence/esc-operating-point/`, `evidence/esc-3oz-build/`,
`evidence/esc-corridor-instrument/`.

Provenance convention in this report: **[native]** = measured by a tool on this host
(kicad-cli DRC, pcbnew python); **[derived]** = arithmetic on native rows, instrument named;
**[prior]** = carried from a previous wave's evidence dir, not re-measured here.

---

## 0. Status

| Step | State |
|---|---|
| Report skeleton | **written** |
| 1. 3 oz stackup + 0.200/0.200 rules, DRC total + SET DIFF | **done — 229 → 102, GONE 127 / ADDED 0, residual exactly 70+16+16** |
| 2. via_dangling split: power vs signal | **done — 16/16 SIGNAL, 0 on the power path** |
| 3. annular ring measurement + 0.150 rule trade | **done — rings are 0.150 (28 vias) and 0.175 (42 PTH); 0.150 rule clears all 70** |
| 4. Power path routed, corridor-confirmed | **done — 30 pours executed; 24/36 rows conduct, 12/36 at 36.6 A; the phase lane is 3.90 mm where 9.427 is needed** |
| 5. GATE G1–G8 at 36.6 A, exit code | **done — EXIT 1; G1, G2, G5, G6, G8 fail** |
| 6. Final state | **done — DRC 125 (+23, no short), unconnected 499/1,542 unchanged, routed fraction stated** |

---

## 1. The 3 oz build, and the set diff that has to be row-level

**What the board already is.** The input board is a **poured, not tracked** power stage:
687 footprints, 3,454 pads, **1,990 vias, 154 tracks, 96 F.Cu zones — all filled** — and the
only in-plane power copper is those 96 pours. Per cell the pour inventory is
`M#_BATP` ×3, `M#_PHASE_A/B/C` ×2 each, `M#_BATN` ×1, `M#_BATP_IN` ×1 (all F.Cu). There is
**no track on any power net at all** — 0 tracks against `M#_BATP 42 pads / 90 vias`,
`M#_PHASE_* 19 pads / 64 vias`, `M#_BATN 80 pads / 45 vias`. The vias are the layer
transitions and the pours are the conductors; this is the shape any routing work has to
work with, and it is why §4 is a *pour* job, not a trace job.

My starting copy is the repository board **plus the two shipped pad shrinks** (288 LQFP-48
pads 0.300→0.250, 16 USB-C power pads 0.600→0.500; re-read from the file) **plus the 3 oz
stackup** — built by the previous wave and re-verified here rather than trusted: F.Cu/B.Cu
0.1050 mm, In1/In2 0.0525 mm, total 1.600 mm (the 0.795 mm core goes to 0.865 so the board
thickness is held). **[native]**

**Both arms re-run on my copies, nothing inherited** (`01_drc.ps1`) **[native]**:

| arm | rule set | violations | unconnected |
|---|---|---:|---:|
| 3 oz | 0.200 pattern / ring 0.200 (`esc36a.kicad_dru`) | **102** | 499 |
| 4 oz | 0.250 pattern / ring 0.200 | **229** | 499 |
| control | 3 oz board, clearance 0.200 → 1.000 | **612** | 499 |
| trap | 3 oz board, **no `.dru`** (project rules) | **16** | 499 |

The control moving 102 → 612 is the proof the `.dru` is read (prior wave recorded 1,080 for
the same substitution on its copy; my run is 612 and I report mine — the set diff below does
not depend on it). The trap arm is the one that matters: with the rule file deleted the same
board reads **16**, all `via_dangling`, and that is the plausible-green this programme keeps
producing — a number that says nothing about copper weight.

**Row-level set diff** (key = type + identified objects + positions to 0.01 mm; rule name and
required value excluded, since both change by construction) **[native]**:

```
SET DIFF 3oz - 4oz :  GONE 127   ADDED 0   unchanged 102
GONE by type     : clearance 120, track_width 4, connection_width 3
REMAIN by type   : annular_width 70, via_diameter 16, via_dangling 16
```

| pad↔pad family | 4 oz | gone | remain |
|---|---:|---:|---:|
| QFN-80 U201 (RP2354B) | 75 | **75** | **0** |
| USB-C J202/J203 | 14 | **14** | **0** |
| total | **89** | **89** | **0** |

**229 → 102 is confirmed, and so is the residual: exactly 70 annular + 16 via_diameter + 16
via_dangling, with ADDED 0.** The 127 rows that go are 120 clearance (89 of them pad↔pad,
all cleared by the 0.200 pattern class with zero layout change) plus 4 track_width and 3
connection_width. Nothing new appears: the pattern-class change is not buying its win with
new geometry.

## 2. The 16 dangling vias: the split is 0 power / 16 signal

Extracted from `drc_3oz.json` and **resolved against the board** (position → via → net), not
from the message text **[native]** (`02_rows.py`, `02_rows.json`):

| net | vias | class |
|---|---:|---|
| `/Controller and ADC/CAN_SCK` | 2 | signal |
| `/Controller and ADC/STATUS_LED` | 2 | signal |
| `/Motor 1 power cell/M1_STATUS_LED` … `/Motor 6 power cell/M6_STATUS_LED` | 2 each (12) | signal |
| **total** | **16** | **POWER 0 / SIGNAL 16** |

Every one of the 16 is a status-LED or CAN test via (0.6 mm OD / 0.3 mm drill → ring 0.150),
and **the same 16 vias are the 16 `via_diameter` rows** (set equality on positions, checked).
They are dangling because each net has two vias and no B.Cu track between them — a two-point
signal link, not a power transition.

**This reverses the premise of the assignment.** The instruction assumed the 16 dangling vias
were unrouted nets on the power path that "block a route". Measured: **none of the 16 is on a
power net**; all 16 are 0.6 mm signal vias that a 2-segment B.Cu link would close. The
unconnected count of **499** is a different set entirely (the position-independent ratsnest),
and it is dominated by the un-poured signal nets, not by these vias.

## 3. The 70 annular rows: what ring they actually have

Ring recomputed from the board geometry (`(OD − drill)/2`), not read off the message **[native]**:

| object | n | drill / OD | ring (measured) | rule cited |
|---|---:|---|---:|---|
| via | 28 | 0.30 / 0.60 (16 of them) and 0.40 / 0.70 (12) | **0.150** | via annular ≥ 0.200 |
| PTH pad | 42 | — | **0.175** | PTH annular ≥ 0.200 |

So the population is **28 vias at exactly 0.150 mm and 42 through-hole pads at 0.175 mm** —
nothing below 0.150. A **0.150 mm ring rule clears all 70 rows**: it clears the 42 pads by
0.025 mm and the 28 vias exactly at the limit. Verified by re-running DRC with one constraint
changed (0.200 → 0.150, both the via rule and the PTH rule, nothing else) — results in §3.1.

**The trade, stated before the number is quoted:** 0.150 mm annular at 3 oz is a
*some-fabs* acceptance, not a published Multi-CB row (the 0.200 pattern class is theirs; the
ring figure is the looser house standard that 3 oz quotes usually grant). Taking it means
**the ring on 28 signal vias and 42 THT pads drops to 0.150 — that is 0.075 mm of copper
land per side on the vias**, and at 0.6 mm OD / 0.3 mm drill the barrel-to-land interface is
the number that decides drill-registration scrap. It is a **fab capability question to be
quoted, not a free win**, and it does not touch the power path: every affected via is signal,
every affected pad is a connector/THT pad outside the phase corridors.

### 3.1 Result of the 0.150 rule

| arm | rule change | violations | by type |
|---|---|---:|---|
| as built | ring 0.200 | 102 | 70 annular, 16 via_diameter, 16 via_dangling |
| **ring 0.150** | annular 0.200 → 0.150 (via **and** PTH rule) | **32** | 16 via_diameter, 16 via_dangling |
| ring 0.150 + vd 0.60 | also via_diameter 0.700 → 0.600 | **16** | 16 via_dangling |

Rule file produced: `rules_3oz_020_ring150.kicad_dru`. **A 0.150 mm ring rule clears all 70
annular rows — 102 → 32, a clean 70-row removal, no new rows.** The remaining 16
`via_diameter` rows are the same 0.6 mm vias and need the diameter minimum relaxed to 0.600
(→ 16, `drc_3oz_ring150_vd60.json`); the last 16 are the signal dangling vias of §2.

So: **the whole ring population is a single house-rule question, and it is answerable "yes"
in one line of the rule file** — with the caveat above that 0.150 at 3 oz is a quote to
obtain, not a Multi-CB published row, and that it does not touch the power path.

## 4. The power path: what the board actually offers, and what was routed

### 4.1 First, the state of the conductor (not the corridor)

This board's power path is **96 filled F.Cu pours and zero power tracks**. So the first
measurement is not "how wide is the free lane" but "does the copper that is there conduct,
and how wide is it". `04_measure.py` measures both on the same board with the validated
instrument (grid 0.04 mm, calibration in the log: worst |err| 0.057 mm) **[native]**:

| row (×6 cells) | F.Cu own copper | own conductor band | needs at 36.6 A |
|---|---|---:|---:|
| BATP_IN | one component, 268 mm² | **CONDUCTOR 10.12 mm** | 8.413 → **PASS** |
| BATP | **FRAGMENTED** (10 components) | 0 | 8.413 → FAIL |
| PHASE_A | **FRAGMENTED** (5 components) | 0 | 9.427 → FAIL |
| PHASE_B | **FRAGMENTED** | 0 | 9.427 → FAIL |
| PHASE_C | **FRAGMENTED** | 0 | 9.427 → FAIL |
| BATN (B.Cu) | one component | **CONDUCTOR 22.88 mm** | 8.413 → **PASS** |

The pours are **terminal spreads, not conductors**. `05b_diag.py` finds why: on PHASE_A
the FET-side copper (196 mm²) and the lug-side copper (113 mm²) are separate islands whose
**nearest points are 12.63 mm apart**, and the straight line between them clears foreign
copper by only **0.088 mm** — i.e. the neighbouring pour sits in the gap. BATP is worse: its
shunt-side island (81 mm²) and drain-tab island (804 mm²) are **37.67 mm apart** with 0.000 mm
of clearance on the straight line.

### 4.2 The corridor the design point was derived from does not exist on this board

This is the wave's central finding, and it is a measurement with a control, not an opinion
(`05c_lane.py`, `05e_reconcile.py`) **[native]**. Same instrument, same grid, three boards:

| board | PHASE_A lane | PHASE_B | PHASE_C | BATP | what it isolates |
|---|---:|---:|---:|---:|---|
| **PLACEMENT (s3oz, pads + 492 vias)** | 12.10 | 13.30 | 13.30 | 1.50 | the gate-of-record board |
| **NOZONES** (this board, pours deleted) | 8.30 | 5.10 | 5.30 | 5.70 | the cost of the 1,990 vias + 154 tracks |
| **AS-BUILT** (the board as it stands) | **3.90** | **−0.50** | **0.70** | 3.32 | the cost of the 96 pours |

Lane = widest track of that net that fits at 0.25 mm clearance. Reconciled at 0.05 mm grid
over **both** terminal pairs (`_H` rows included), the gate of record's number reproduces
exactly — **9.40 mm** (c3 PHASE_A, HS-source pair) against its 9.420 mm, and 9.50 mm at the
0.200 mm pattern-class clearance. **The 9.42 mm is real, and it is a property of a board with
the pours stripped off.** With the pours on it, the phase lane is 3.90 / −0.50 / 0.70 mm.

Three nested causes, in order of size: **the pours (8.30 → 3.90), the via field (12.10 →
8.30), and finally the pads**. The settled 36.6 A point was computed from a corridor that the
buildable board does not have — the pours the same programme counts as thermal spreading are
exactly what closes the phase lanes.

### 4.3 What was routed (executed, not proposed) — `05d_route.py`

Method: the maximin instrument finds the widest lane through **all** foreign copper and traces
it; the route width is `w = min(required, lane − 2 × 0.20)`; the corridor is poured as a zone
(KiCad's `ZONE_FILLER` does the clearance geometry, so the copper that lands is the copper the
rules allow) filled **only for the new zones**, leaving the 96 existing fills untouched so the
board differs from as-built by my copper and nothing else.

**Two arms were executed and the first was rejected on measurement**: the same corridor laid as TRACKS of the same width scored **242 violations — 28 shorting_items, 100 clearance, 6 tracks_crossing** (a maximin corridor is not a legal track centreline once chords are cut through it). That arm was abandoned, not shipped. A second pour arm with wider tubes scored 117 (more clipping); the shipped arm is the corridor-tight one at 125. Only the shipped arm's json is retained, so the 242 and 117 are reported from their runs.

| executed | rows | width | measured band after | capacity at 105 µm | vs 36.6 A |
|---|---:|---:|---:|---:|---:|
| PHASE_A pour | 6 | 3.95 mm | **2/6 CONDUCTOR 3.93-3.98**; 4/6 fragmented (fill clipped where foreign pours cross) | **19.4 A** | 53 % |
| PHASE_C pour | 6 | 0.75 mm | **6/6 CONDUCTOR 0.74** | **5.8 A** | 16 % |
| PHASE_B | 6 | **NO LANE** (-0.50 mm) | fragmented, 0.00 | **0 A** | 0 % |
| BATP pour | 6 | 3.37 mm | **4/6 CONDUCTOR 3.18** (c4-c6) and 1.36 (c2); 2/6 fragmented | **16.6 A** / 9.0 A | 49 % / 27 % |
| BATP_IN pour | 6 | 8.41 mm | 6/6 CONDUCTOR 10.12 (it already conducted) | **38.5 A** | 105 % |
| BATN | 6 | none needed | 6/6 CONDUCTOR 22.5-22.9 | **69.5 A** | 207 % |
| Kelvin shunt tap | 6 | 0.25 mm | pour routed and filled (12-19 mm2 per cell); its conduction is not on the 36-row instrument because it is a sense pair, not a current path | 2.6 A at 0.25 mm | sense only |

**24 of 36 power rows (67 %) now carry a continuous conductor; only 12 of 36 (33 %) carry it
at the 36.6 A requirement.** The phase conductor is routed at **19.4 A per phase**, not 36.6.

### 4.4 DRC cost of the routing, as a set diff

| board | violations | by type |
|---|---:|---|
| as built | 102 | 70 annular, 16 via_diameter, 16 via_dangling |
| routed | **125** | + **9 isolated_copper**, **6 copper_sliver**, **6 zones_intersect**, **2 connection_width** |

**SET DIFF routed − as-built : GONE 0, ADDED 23, unchanged 102.** The 23 new rows are all
artifacts of the 30 new pours — dead islands, fill slivers, outline overlaps and one thin
connection — and **none is a short or a clearance violation**: the filler never produced
copper closer than the 0.200 mm class. They are cleaned by hand or by a re-pour with
`remove islands` on the existing zones too; they are not a manufacturing defect.

## 5. The gate, re-based on 36.6 A / 33.7 A (`06_gate36.py`)

G1–G8 logic is the gate of record. Two declared changes: the currents (36.6 / 33.7, so the
phase requirement is 9.427 mm and the bus 8.413 mm at 105 µm) and the reading — on a poured
board a "free corridor" number is not a capacity statement, so G1/G2/G3 take the net's own
conductor where one exists and print both readings. G2's layer was also released to *either*
outer layer, because on this board the battery rails are on F.Cu whereas the gate of record
read them on B.Cu; both readings are printed per row.

| ID | condition | n | worst measured | required | verdict |
|---|---|---:|---:|---:|---|
| G1 | phase conductor ≥ 9.427 mm | 18 | **−0.50 mm** (M1 PHASE_B) | 9.427 | **FAIL** (18/18) |
| G2 | BATP_IN/BATP ≥ 8.413 mm | 12 | **1.26 mm** (M1 BATP) | 8.413 | **FAIL** (6/12) |
| G3 | BATN ≥ 8.413 mm | 6 | 22.94 mm | 8.413 | PASS |
| G4 | no component on B.Cu/inner | 1 | 0 (F=687, B=0) | 0 | PASS |
| G5 | spreader reserved and stated | 1 | rects=0, 0/36 TOLTs, no declaration | 36 | **FAIL** |
| G6 | barrels per rail transition @1.50 A | 60 | 2 vs 15 (BATP @ Q1x01.9) | 15 | **FAIL** (2/60) |
| G7 | Tj ≤ 175 °C at TA 45 °C | 1 | 84.9 °C (1.78 W/device, 22.4 C/W) | 175 | PASS |
| G8 | back-layer budget ≤ 50 % | 6 | **54.0 %** (cell 6) | 50 | **FAIL** |

```
3 PASS, 5 FAIL (G1,G2,G5,G6,G8), 0 UNMEASURABLE  ->  EXIT 1
```

**G7 cross-check, stated because the settled point quotes a different number:** the gate's own
model is conduction-only and gives 1.78 W/device → 84.9 °C. The settled operating point uses
**3.33 W/device including switching → 119.6 °C** at the same 22.4 C/W. Both are ≤175 °C; the
gate's model is the optimistic one and I report the settled figure as the design number.

**G5 is a file-level gap, not a thermal one:** this board carries **4 drawings, all Edge.Cuts**
— no spreader marker rectangles and no `SPREADER_EXCHANGE_CM2=` declaration. The reservation
exists only on the placement-of-record board (`s3oz`), where the gate of record passed it. The
spreader requirement itself (36 TOLTs, ≥181.2 cm² of exchange area) is unchanged and unmet *on
this file*.

## 6. Final state

| measure | as built | routed | tool |
|---|---:|---:|---|
| DRC violations (3 oz, 0.200/0.200) | 102 | **125** | kicad-cli **[native]** |
| — of which annular / via_dia / via_dangling | 70/16/16 | 70/16/16 | kicad-cli |
| — new rows from the routing | — | 23 (no short, no clearance) | kicad-cli |
| unconnected, kicad-cli `unconnected_items` | 499 | **499** | kicad-cli |
| unconnected, pcbnew ratsnest | 1,542 | **1,542** | pcbnew |
| power rows conducting | 12 / 36 | **24 / 36** | corridor instrument |
| power rows at the 36.6 A requirement | 12 / 36 | **12 / 36** | corridor instrument |
| gate G1–G8 | — | **EXIT 1** (G1,G2,G5,G6,G8 fail) | `06_gate36.py` |

**On the two unconnected numbers — they are not the same instrument and neither moves.**
kicad-cli's 499 and pcbnew's 1,542 differ by construction (one groups ratsnest edges into DRC
rows, the other counts edges). Both are **identical before and after the routing**, and the
reason is visible in the rows: the three rows for M1_PHASE_A are `Q1102.9 ↔ Q1102.9` (a
multi-pad group inside one footprint), `R1102.2 ↔ Q1102.9` (the shunt tap) and
`U1101.7 ↔ R1102.2` (the CSA input). **The FET-tab → motor-lug pair that the pour was routed to
close is not in that list on either board** — KiCad's model already considers it joined, while
the geometric instrument measured the two islands as separate. So the unconnected count is a
poor progress metric for power routing on this board: it cannot register the change in either
direction. That disagreement is reported as a finding, not resolved by preference.

**What still blocks a fab order, plainly:**

1. **The phase conductor cannot carry 36.6 A on this placement.** 9.427 mm is needed on one
   outer layer at 105 µm; the buildable board offers **3.90 mm** (phase A), **0.70 mm**
   (phase C) and **−0.50 mm** (phase B, no legal lane at all). The routed phase A conductor is
   measured at **19.4 A** and phase C at **5.8 A**. This is not a routing choice — the 96
   existing pours and the 1,990-via field consume the corridor the design point was sized
   against. Options, all outside this wave: reshape the pours that cross the phase lanes and
   re-pour (the pours are the single largest consumer, 12.10 → 3.90 mm), cut a phase lane into
   In1/In2 in parallel (0.0525 mm each: 3.90 + 2 × inner would reach ~38 A, at the cost of
   splitting the return planes under a 36 A switching stage), or re-place the power stage with
   a wider phase window.
2. **BATP is routed but under capacity.** 4 of 6 cells now conduct at 3.18 mm (16.6 A) or
   1.36 mm (9.0 A); cells 1 and 3 were clipped apart by foreign pours and read 0. Against the
   33.7 A bus that is 49 % / 27 %, so the bus is only fully fed through BATP_IN's F.Cu pour
   and BATN's B.Cu pour.
3. **G8 — cell 6's back layer is over budget at 54.0 %** (754 mm² needed against 1,396 mm²
   uncommitted), so the anti-vacuity condition fails there.
4. **G5 — the spreader reservation is not on this board file** (0 markers, no declared
   exchange area). A documentation gap that a fab order would inherit.
5. **The 102 residual DRC rows** are 70 annular (0.150/0.175 mm), 16 via_diameter (0.6 mm
   vias) and 16 signal dangling vias. §3 shows the annular set clears to 32 with one rule line
   (0.150) and to 16 with the via diameter at 0.600 — both are **fab-quote questions**, not
   layout defects, and both are stated with their trade.

**What is finished and usable:** the 3 oz / 0.200 mm build is confirmed at 102 with an exact
row-level set diff; the annular question is answered with a rule file and a measured count; the
dangling population is resolved to 16 signal vias, 0 power; 30 pours were routed and measured;
the gate is re-based on the real design point and exits 1 with every condition reported; and the
reason the design point is unreachable is measured rather than argued.

---

## Files

| file | what it is |
|---|---|
| `01_drc.ps1`, `drc_3oz.json`, `drc_4oz.json`, `drc_3oz_ctl100.json`, `drc_3oz_project.json` | the two arms, control and trap |
| `02_rows.py`, `02_rows.json` | set diff, via_dangling split, annular census |
| `03_drc_ring150.ps1`, `rules_3oz_020_ring150.kicad_dru`, `drc_3oz_ring150.json`, `drc_3oz_ring150_vd60.json` | the ring-0.150 lever and its price |
| `04_measure.py`, `02_routed.json` | per-row free + own-conductor measurement (36.6 A basis) |
| `05b_diag.py/json` | why each row fails: components, gap, clearance in the gap |
| `05c_lane.py/json`, `05e_reconcile.py/json` | the three-board lane control and the 9.42 mm reconciliation |
| `05d_route.py`, `05d_route.json`, `boards/esc36a_routed.kicad_pcb` | the executed routing |
| `05_refill.py` | the refill experiment (rejected as a fix; fills move ≤212 mm² per power net) |
| `06_gate36.py`, `gate_routed.json`, `logs/06_gate_routed.log` | G1–G8 at 36.6 A, exit 1 |
| `08_conn.py/json`, `09_uncset.py/json` | the two unconnected instruments and the per-net set |
| `boards/` | every board is a COPY; the repository file was never written |
