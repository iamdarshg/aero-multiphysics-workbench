# ESC rev_B — 3 oz build with parallel shunts: does it pass its own ampacity gate?

**Wave 14 specialist report.** Question: *at 3 oz with a parallel shunt per rail, does the ESC pass
its own ampacity gate?* Gate decides; no argument.

Evidence dir: `E:/engineering-portfolio-audit/evidence/esc-3oz-build/` (all work on copies).
Input board: `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` (never written).

---

## 0. Status

| Step | State |
|---|---|
| Report skeleton | written |
| 1. 3 oz stackup + DRC set diff vs 4 oz | **done — 229 → 102, GONE 127 / ADDED 0, all 89 gaps clear** |
| 2. Parallel shunt (top layer) + barrel recount | **attempted — not placeable, 0 legal positions; barrels rebuilt to 1.50 A, 36/48 sites met, 12 short by 4** |
| 3. Ampacity table, correct k per layer, 1.50 A/barrel | **done — 4 of 9 elements fail** |
| 4. Gate G1–G8 + exit code | **done — EXIT 1; G1, G2, G6 fail** |
| 5. Area at 3 oz vs before | **done — 382.709 cm², +0.000 cm²** |
| 6. SAFE_TO_ROUTE verdict | **NO** |

---

## 1. Stackup change to 3 oz outer (105 um)

Edit is the stackup block only (`03_stackup_3oz.py`), verified by re-reading the saved
file: `F.Cu 0.1050`, `In1.Cu 0.0525`, `In2.Cu 0.0525`, `B.Cu 0.1050`, total `1.600 mm`
(the 0.795 mm core goes to 0.865 so the 1.600 mm board thickness is held — the fab does
exactly this when the foil loses 35 µm per side).

**Inner weight:** kept at **0.0525 mm (1.5 oz)**. Multi-CB's capability table is headed
"Copper thickness **Outer\* and Inner layers**" and gives one pattern column per copper
thickness, so it does not force a different inner weight; the only inner-layer sentence in
that source is about the 4-layer **pool** service ("either 18 µm or 35 µm copper … on the
inner layers"), not the 105 µm special line. **So 1.5 oz inners are an assumption to
confirm with the fab, not a published commitment** — and it is load-bearing, because
`k=0.024` on 1.5 oz inner copper is what makes an inner-layer route uneconomic (§4). If the
fab forces 1 oz (35 µm) inners, inner capacity per mm of width drops from 2.18 A to 1.62 A
(−26 %); no rail in this build uses the inner layers, so the verdict does not move.

## 2. DRC at 3 oz, 0.200/0.200 — SET DIFF vs 4 oz

Both arms are the **same board** (`boards/base4oz.kicad_pcb`), rebuilt here from the
repository board with the two shipped pad changes and verified at 229 rows before the
change: 288 LQFP-48 pads 0.300→0.250 across-pitch, 16 USB-C power pads 0.600→0.500
(read-back from the saved file: `lqfp 0.25 x 1.475 -> 288`, `usbc 0.5 x 1.15 -> 16`).

| arm | rule set | violations | unconnected |
|---|---|---:|---:|
| 4 oz | 0.250 / ring 0.200 (as shipped) | **229** | 499 |
| 3 oz | 0.200 / ring 0.200 (`rules_3oz_020.kicad_dru`) | **102** | 499 |
| control | same 3 oz file, clearance 0.20 → 1.00 | **1080** | — |

The control moving 102 → 1080 is the proof the `.dru` is being read. That control is not
decoration: **with the `.dru` deleted, the same board reads 16 violations** at KiCad's own
project rules (all via_dangling) — a plausible green that says nothing about any copper
weight, and the exact failure class this programme has been burned by before
(`esc-placement-gate/REPORT.md` §6.1; `drc_projectrules.json` here).

**Row-level set diff** (key = type + the identified objects + their positions to
0.01 mm; the rule name and the rule's required value are *excluded* from the key,
because both change by construction):

```
SET DIFF 3oz - 4oz :  GONE 127   ADDED 0   unchanged 102
GONE by type     : clearance 120, track_width 4, connection_width 3
REMAIN by type   : annular_width 70, via_diameter 16, via_dangling 16
```

| pad↔pad family | 4 oz | gone | remain |
|---|---:|---:|---:|
| QFN-80 U201 (RP2354B) | 75 | **75** | **0** |
| USB-C J202/J203 | 14 | **14** | **0** |
| **total** | **89** | **89** | **0** |

**The expected result is confirmed, row by row, not assumed:** all 89 remaining
footprint gaps clear at 3 oz with zero layout change, and nothing new appears
(ADDED 0). The 4 track_width and 3 connection_width rows also clear at the 0.200
pattern class.

**What is still there (102 reported):** 70 annular_width (42 PTH rings at 0.150–0.175
+ 28 vias at 0.150), 16 via_diameter, 16 via_dangling. These are **not** pattern-class
rows: they are ring/drill geometry and would need the ring minimum relaxed from 0.200
to 0.150 (a 3 oz quote usually grants that) — deliberately **not** taken here, so the
only variable in the diff is the pattern class. Fab-real at 3 oz = 102 reported + 98
pad rings KiCad cannot report = **200**.

## 3. Barrel fix: what the pads actually hold, and why the second shunt is not placeable

Both instruments are re-run at the **settled** basis: **1.50 A per 0.4 mm / 25 µm barrel**
(k = 0.024, the internal constant; a barrel has no external form). At 1.50 A a 40 A bus
terminal needs **27** barrels and a 25.11 A leg terminal (43.5/√3) needs **17**. The gate
of record used 3.00 A and therefore asked for 14 and 9 — the withdrawn constant, and the
reason its G6 was green (`logs/gate_safe.log`, `gate_safe.json` → `i_barrel: 3.0`).

### 3.1 Measured legal capacity per pad (`01_capacity.py`, `01_capacity.json`)

Legality: inside the pad with 0.30 mm to the border, **or** a collar whose 0.80 mm annulus
overlaps the pad (≤0.30 mm out), 0.25 mm to foreign copper, 0.90 mm barrel pitch.

| pad class | copper area | legal barrels | need at 1.50 A | verdict |
|---|---:|---:|---:|---|
| bus shunt pad (CSS4J-4026, 5.6 × 2.55) ×12 | 14.19 mm² | **23** | 27 | **short 4** |
| leg shunt pad (same part) ×18 | 14.19 mm² | 21–35 | 17 | fits |
| TOLT drain EP (10.2 × 7.0) ×18 | 92.91 mm² | 101–152 | 17 | fits |

So the programme's "17–18 barrels" appears to count pad-interior positions only; under its
own builder's collar rule the pad gives **23**. It is still **4 short** — the pad-area
argument survives, but the deficit is 4 barrels (6 A), not 9–10.

### 3.2 The barrels were rebuilt (`05_barrels.py`, `05_barrels.json`)

All 48 declared G6 sites were re-laid at the 1.50 A requirement: **492 → 888 barrels**.

```
36 of 48 sites at or above the 1.50 A need; 12 short (total deficit 48 barrels)
```

The 12 short sites are exactly the **12 bus-shunt power pads** (R1c23.1/.2, 6 cells × 2),
at 23 vs 27. Every leg shunt and every drain tab now has 17.

The placement board carries **no copper zones** (the repository board has 96; the
placement of record is stripped to pads so the corridor instrument measures free space), so
these 888 barrels are capacity *reservations* at the terminals, exactly as the earlier wave
treated its 492 — the pour that feeds them is the routing step.

### 3.3 The parallel shunt: executed as a *search*, and it has no legal position

The prescribed fix is a second 0.5 mΩ shunt adjacent to each first one. It is **not
placeable on the F.Cu of the bus node**, and this is a measurement, not an opinion:

- exhaustive search (`00c`, `00f`): **±12 mm around R1c23, 0.25 mm grid, 4 rotations × 4
  mirrors, courtyard/body-clearance object ⇒ 0 legal positions in all six cells**
  (150,544 candidates per cell, every one rejected at the mate-pad test — no orientation
  puts *both* power pads of a twin within a 3 mm neck of the same-net pad of its parent);
- the one pads-only position that clears foreign copper by 2.27 mm has the **body**
  colliding: there is no 6.6 × 10.2 mm slot (C1170 sits 0.21 mm from the shunt's
  bounding box, C1162 and C1166 at 0.00);
- the geometric reason is structural, not local: the two big pads are **5.6 mm wide**
  along the neighbour axis and **8.05 mm apart** along the current axis *carrying
  different nets*. End-to-end (offset ≈ +10.4 mm) the twin's body clears everything, but
  then its BATP pad faces the parent's *BATP_IN* pad and its own BATP mate is 18 mm away;
  laterally (offset ≥ 5.6 mm) the pads sit on the right nets but the bodies collide; and
  any position far enough out to be legal puts the barrels outside the gate's 7 mm count.

**Which rails it would have gone on: the 12 bus-shunt pads, not the 24.** Only those 12
sites are short (23 vs 27); the 18 leg-shunt pads on BATN and the 18 TOLT drain tabs
already meet 17/17 in their existing pad area, so a second part there would buy nothing.
The bus shunt is the one place where the full 40 A crosses a 14.19 mm² pad.

**Consequence, stated not hidden:** the parallel shunt would also have halved the sense
element to 0.25 mΩ and required a 2× firmware current-gain rescale. That consequence never
arises, because the part cannot be placed. The site needs **pad area** — a longer land on
the two power pads, or a relocated shunt — and that is a footprint change the owner has
not taken.

## 4. Ampacity at 3 oz with the correct k per layer (`08_ampacity.py`)

`A[mil²] = (I/(k·dT^0.44))^(1/0.725)`, dT 20 K; `k=0.048` F.Cu/B.Cu at 0.105 mm,
`k=0.024` In1/In2 at 0.0525 mm; barrel 0.03142 mm² = 48.69 mil² → **1.50 A**.

| element | layer | k | req mm² | avail mm² | req width | capacity A | I req | ratio | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| PHASE_A/B/C (worst cell) | F.Cu 105 µm | 0.048 | 1.2561 | 0.9891 | 11.963 mm | **36.58** | 43.5 | 0.84 | **FAIL** |
| PHASE_A/B/C (best cell) | F.Cu 105 µm | 0.048 | 1.2561 | 0.9929 | 11.963 mm | 36.68 | 43.5 | 0.84 | **FAIL** |
| BATP_IN (worst cell) | B.Cu 105 µm | 0.048 | 1.1189 | 1.1015 | 10.656 mm | **39.55** | 40.0 | 0.99 | **FAIL** |
| BATP (worst cell) | B.Cu 105 µm | 0.048 | 1.1189 | 1.6443 | 10.656 mm | 52.88 | 40.0 | 1.32 | PASS |
| BATN (worst cell) | B.Cu 105 µm | 0.048 | 1.1189 | 2.1154 | 10.656 mm | 63.47 | 40.0 | 1.59 | PASS |
| In1/In2 alone | inner 52.5 µm | 0.024 | 3.2678 | 3.2676 | 62.244 mm | 43.50 | 43.5 | 1.00 | REF |
| In1/In2, 10 mm trace | inner 52.5 µm | 0.024 | 3.2678 | 0.5250 | 62.244 mm | 11.56 | 43.5 | 0.27 | REF |
| bus shunt pad, 23 × 1.50 A | barrel | 0.024 | 2.9108 | 0.7226 | — | **34.50** | 40.0 | 0.86 | **FAIL** |
| leg / drain pad, 17 × 1.50 A | barrel | 0.024 | 1.5318 | 0.5341 | — | 25.50 | 25.1 | 1.01 | PASS |

**4 of 9 elements fail.** The phase conductor is the big one: at 105 µm it needs 11.963 mm
where the best cell offers 9.456 mm (0.84×). The inner-layer rows are references: a single
1.5 oz inner layer needs 62.2 mm of width for 43.5 A, which is why the rail lives on B.Cu.

## 5. The gate (`07_gate3oz.py`, `gate_s3oz_par.json`)

Two constants changed in a copy, **logic untouched**: `k_barrel` 0.048 → **0.024**, and the
requirement width recomputed from `01_standard.json`'s own areas at **t = 0.105**
(8.972 → 11.963 mm phase; 7.992 → 10.656 mm bus). One measurement row set was extended:
rows for `Q1c03.9` / `Q1c05.9` were added so the gate's own 12 declared-but-skipped sites
resolve — G6 now measures **48/48**, and the 12 filled sites pass at 17/17.

| ID | condition | n | measured (worst) | required | margin | verdict |
|---|---|---|---:|---:|---:|---|
| G1 | phase corridors ≥ 11.963 mm F.Cu | 18 | **9.420 mm** (M1 PHASE_A) | 11.963 | **−21.3 %** | **FAIL** (18/18) |
| G2 | BATP_IN/BATP ≥ 10.656 mm B.Cu | 12 | **10.490 mm** (M1 BATP_IN) | 10.656 | **−1.6 %** | **FAIL** (3/12) |
| G3 | BATN ≥ 10.656 mm B.Cu | 6 | 20.147 mm | 10.656 | +89.1 % | PASS |
| G4 | no component on B.Cu / inner | 1 | 0 (F=687, B=0) | 0 | 0 | PASS |
| G5 | spreader reserved and stated | 1 | 36/36 tight, 90.5 cm² contact, 181.202 cm² declared vs 181.2 needed | 36 | +0.0 % | PASS |
| G6 | barrels per rail transition @1.50 A | 48 | **23** (BATP_IN @ R1c23.1) | 27 | **−4 barrels** | **FAIL** (12/48) |
| G7 | Tj ≤ 175 °C at TA 45 °C | 1 | 101.4 °C (2.52 W, 22.4 C/W) | 175 | +73.6 K | PASS |
| G8 | back-layer budget ≤ 50 % | 6 | 26.2 % (1414 / 5405 mm²) | 50 | +23.8 pt | PASS |

**EXIT CODE 1. 5 PASS, 3 FAIL (G1, G2, G6), 0 unmeasurable.**

### 5.1 Four instrument states, one board — the false green is reproducible

| arm | requirement | k_barrel | G1 | G2 | G6 | exit |
|---|---|---:|---|---|---|---|
| **as shipped** (withdrawn basis) | 4 oz 8.972/7.992 | 0.048 (3.00 A) | PASS | PASS | PASS | **0** |
| 4 oz geometry, corrected barrel | 4 oz | 0.024 (1.50 A) | PASS | PASS | **FAIL** | 1 |
| 3 oz, withdrawn barrel | 3 oz 11.963/10.656 | 0.048 | **FAIL** | **FAIL** | PASS | 1 |
| **3 oz, corrected barrel (the answer)** | 3 oz | 0.024 | **FAIL** | **FAIL** | **FAIL** | **1** |

Same board, same gate logic: the top row is the plausible green that this programme keeps
producing, and it comes from a constant that was withdrawn. Nothing in the build changes
between rows 1 and 4.

### 5.2 One interaction worth naming

G2's failure is **caused by the G6 fix**. Before the barrel rebuild (`gate_s3oz.json`) the
worst BATP_IN corridor was 12.519 mm and G2 passed 12/12; after it, the 23-barrel BATP farm
at the neighbouring pad is 13.8 mm² of foreign copper inside the BATP_IN window and the
corridor falls to **10.490 mm** — 0.166 mm under the 3 oz requirement. At 4 oz the same
corridor is still +31 %. The two fixes fight each other only at 105 µm.

## 6. Area (`09_area.py`)

| board | area cm² | vias | bbox mm | footprints |
|---|---:|---:|---|---:|
| safe_base (4 oz, placement of record) | 382.709 | 492 | 155.15 × 246.80 | 687 |
| s3oz (3 oz stackup) | 382.709 | 492 | 155.15 × 246.80 | 687 |
| **s3oz_par (3 oz + 888 barrels)** | **382.709** | 888 | 155.15 × 246.80 | 687 |

**The parallel parts changed the area by 0.000 cm² — because neither was added.** The
barrel rebuild costs 0.000 cm² and 396 extra drills. 3 oz itself costs 0.000 cm²: it is a
foil change, not a layout change. The 382.709 cm² floor of the programme is untouched.

DRC control on the placement board: 241 violations before the rebuild, **241 after**
(199 via_dangling + 42 annular in both) — the 396 added barrels introduce **no clearance,
short, edge or mask row**.

## 7. Verdict

**Is the ESC safe to route at 3 oz with a parallel shunt per rail? NO.**

The gate exits 1 on three conditions. All three are real; the first two are structural:

1. **G1 — the phase corridor.** At 105 µm, 43.5 A needs **11.963 mm** of F.Cu alone. The
   placement has **9.420–9.456 mm**. That is −21 %, and it is 3 oz's own arithmetic: the
   corridor was sized against 8.972 mm at 140 µm, and thinning the foil by 35 µm raises the
   requirement by a third. **This is the single blocker**: no barrel, shunt, or fan-out
   work moves it, and it fails on 18 of 18 phase rows.
2. **G6 — the 12 bus pads.** 23 barrels × 1.50 A = **34.5 A against 40 A**. The prescribed
   parallel shunt is the right fix and is **not placeable** (zero legal positions); the pad
   area that would carry 27 barrels does not exist on this layout.
3. **G2 — BATP_IN at 10.490 mm against 10.656 mm**, 0.166 mm short, and *caused by* the
   G6 barrel farm. At 4 oz the same corridor is +31 %.

**What 3 oz buys and what it costs:** it clears all 89 footprint gaps and 127 DRC rows with
zero layout change (the door the programme was looking for), and in exchange it takes the
43.5 A phase rail from a 5 % corridor margin to a 21 % deficit and the bus rail from +56 %
to −1.6 %. **The door is real and it opens onto a rail that no longer passes.** If 3 oz is
taken for the MCU/connector geometry, the phase conductor has to come from somewhere else —
a second layer in parallel (the gate's `F_Cu_plus_B_Cu_each` reading is 3.449 mm at 140 µm, so
4.60 mm per layer at 105 µm), a
thicker local outer, or a re-placed power stage with a wider phase window — and the bus
shunt pad needs more land before the rail can carry 40 A at 1.50 A per barrel.

Evidence: `00*` probes/search · `01_capacity.json` · `02_base.json` · `03_stackup.json` ·
`04_setdiff.json` · `drc_base4oz/3oz/3oz_ctl100.json` · `05_barrels.json` · `02_s3oz*.json` ·
`gate_s3oz*.json`, `gate_arm*.json` · `08_ampacity.json` · `09_area.json` · `logs/`.