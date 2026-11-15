# ESC rev_b — the honest minimum area at 60 A, and what is actually proven

**Unit:** `esc-area-honest` · ESC battery-rail wave · 2026-11-16
**Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), `pcbnew` 9.0.7, CPython 3.12 for
arithmetic.
**Evidence:** `E:/engineering-portfolio-audit/evidence/esc-area-honest/`
**Nothing was written into a repo.** No commit, no push, no `audit/*` branch. Every board
worked on is a **copy** in `boards/` (`01_area.log` records each sha256).
**Constraints in force:** no HDI anywhere; only the ESC is 4 oz, **inners 1.5 oz**
(measured: `F.Cu 0.14 / In1 0.0525 / In2 0.0525 / B.Cu 0.14 mm`, `01_area.json → stackup`);
$60 spend cap; ESC single-sided and as compact as possible. **$0 spent.**

---

## 0. The answer in one table

| | |
|---|---|
| **Areas verified** (two methods, agree to 0.0000) | **491.732 / 370.119 / 382.709 cm²** |
| **Demonstrable area today** | **DOES NOT EXIST.** Two of the four conditions fail: the battery rail, and DRC at the correct rules. |
| **The area that is defensible** | **382.71 cm²** — the power-first placement — with the battery rail moved to the **bare back-layer 4 oz plane**, which costs **0 cm²** because 0 components are on B.Cu. |
| **Range if the rail must stay on the parts face** | **X 387.4** (re-place) · **Y 385.8** (more parallel feed) · **Z 390.5** (inner weight change). Bands: X 385–394, Y 384–390, Z 387–402. |
| **Reduction vs 491.732** | X −104.31 cm² (−21.2 %) · Y −105.98 (−21.6 %) · Z −101.25 (−20.6 %) · back-layer arm −109.02 (−22.2 %) |
| **What I would build** | **382.71 cm²**, BATP on the bare B.Cu plane, after the 4 oz footprint decision |
| **Heat spreader** | **MANDATORY** (60 A is 1.67× the board-only limit). **OUTSIDE the board outline**, top-side over the TOLT tops; **352–528 cm² at 250 W/m²K**, i.e. 0.92–1.38× the board itself |
| **The binding constraint is not area** | it is the 4 oz footprint rule: **413 DRC items on every candidate, 100 % footprint-bound** |

---

## 1. Instrument discipline — what was checked before anything was quoted

This programme has found four instruments that produced plausible green numbers while being
wrong. Five were touched here. Each check is a command that can be re-run.

### 1.1 Area — two independent methods, and they agree

`01_area.py`. M1 = `pcbnew.GetBoardPolygonOutlines().Area()`; M2 = shoelace over the
Edge_Cuts segments walked into loops. Both ran on all three boards.

| board | polygon cm² | shoelace cm² | diff | bbox cm² | footprints | on B.Cu |
|---|---|---|---|---|---|---|
| orig | **491.732** | 491.732 | **0.0000 PASS** | 492.418 | 687 | 0 |
| compact370 | **370.119** | 370.119 | **0.0000 PASS** | 370.514 | 687 | 0 |
| powerfirst | **382.709** | 382.709 | **0.0000 PASS** | 382.910 | 687 | 0 |

The 491.73 vs 492.42 difference is the 0.1 mm outline stroke; both are the same board.
`01_area.log` → `01_area.json`.

### 1.2 DRC — the rule file is PROVEN to have been read

`03_drc.ps1`. `AGENT_BOARD.md:533-536` records that a `.kicad_dru` without `(version 1)` is
silently ignored, so a clean count proves nothing. Three-arm test:

| arm | rule file | violations |
|---|---|---|
| project rules (no `.kicad_dru`) | — | **0** |
| 4 oz / 0.250, the fab-floor set | 9 rules, `(version 1)` present | **413** |
| **control: same file, clearance 0.25 → 1.00 mm** | 9 rules | **541** (+128) |

The count moves when one parameter moves, so the file is live. The 413 is therefore real.

**And the first row is the finding.** The power-first board reads **0 violations** at the
project's own rules and **413** at the rules that matter: the same board, two instruments,
one of which is a false green. Anyone who ran DRC "normally" would report a clean ESC.

### 1.3 The corridor instrument — pads only, and the endpoint window is load-bearing

`esc-current-place/08_corridor_bottleneck.py:26-33` builds obstacles from **other-net pad
bounding boxes only** — no tracks, no vias, no zone fills. Two consequences:

- **On a board with copper the number is an upper bound.** Adding obstacles cannot widen a
  corridor, so a published **FAIL stands a fortiori**. A published PASS on a copper-bearing
  board would not stand — but `powerfirst` has **0 tracks, 0 vias, 0 zones** (`01_area.json`),
  so there the pads *are* the whole obstacle set and the instrument is exact.
- **The endpoint rule changes the answer.** The published tool snaps to the nearest free cell
  within ±2 mm; a strict "reach the pad centre" reading gives much less. `02_corridor.py`
  measures both, and sweeps the fan-out radius R = 0 / 1 / 2 / 3 mm.

| board | phase A | phase B | phase C | flat in R? |
|---|---|---|---|---|
| powerfirst (R=2) | 7.600 | 7.600 | 7.600 | no — 3.700 → 5.600 → 7.600 → 9.300 |
| powerfirst (R=0) | 3.700 | 3.700 | 3.700 | — |
| compact370 (all R) | 2.700 | 3.400 | 4.912 | **yes — a real pinch** |
| orig (R=2, =R=3) | 7.600 | **5.346** | **5.400** | B and C flat ⇒ real pinch |

`02_corridor.log`, `02_corridor.json`. Two things follow:

1. **All 18 phase conductors** on `powerfirst` measure **7.600 mm** at R=2 and **3.700 mm** at
   R=0 (all six cells, three phases each — they are a stamped array, and the measurement
   confirms it).
2. **The board of record fails its own phase corridor on two of three phases** — 5.346 /
   5.400 mm. Against the published 6.991 mm that is 23.5 % short; against the exact two-face
   requirement of 5.374 mm (§2.1) phase B is 0.5 % short. The 7.51 mm on
   `AGENT_BOARD.md:458` is phase A only, and it was never measured on B or C.

### 1.4 The BATN pair is not a corridor at all — the published BATN result is VOID

`02_corridor.log`, every board, every radius:

```
BATN LSsrc->tap   nets /Motor 1 power cell/M1_SHA_I -> /M1_BATN   same=False   widths all None
```

`Q1102.1` is **M1_SHA_I** (the low-side source, before the leg shunt), not BATN. The
published pair therefore spans two different nets: the own-net pad exclusion applies to the
*first* pad's net, so the destination pad is treated as an **obstacle**. BATN returns "no
path" on **all three boards including the board of record** — a measurement that cannot
distinguish a good board from a bad one is not measuring the board.

**The correct BATN pair is `R1120.2` (the leg shunt's BATN pad) → `J1101.2`.** And BATN's
real carrier is a plane, so §3 measures it as a plane.

### 1.5 The rail must be measured as a PLANE, and that is the measurement A7 left open

`05_plane_neck.py` / `05b_verify.py`. BATP is an In1 pour (5,039.0 mm²) and BATN a B.Cu pour
(5,106.6 mm²) — both reproduce the published areas to 0.1 mm² (`04_rail.log`). A trace-width
test cannot see a plane, which is why `esc-current-place/REPORT.md:398-400` left A7 open.

Instrument: rasterise the net's fill on the layer, `d = EDT(copper)·h` = half-width at every
copper pixel, then bisect on t for a path from A to B inside `{d > t}`; **neck = 2·t\***.

**Checked before use:**

| check | result |
|---|---|
| grid convergence (same plane, same pair) | 7.529 (h 0.10) → **7.580** (0.05) → 7.640 (0.025) ⇒ +0.8 % over 4× refinement |
| pair robustness (bus shunt → each of the 3 HS drains) | 7.360 / 7.580 / 8.855 ⇒ min 7.360 |
| endpoint rule | PTH pad → pad centre; SMD pad → nearest via of the net on that layer |

| net | layer | fill mm² | **neck mm** | span mm |
|---|---|---|---|---|
| /M1_BATP | **In1 1.5 oz** | 5,039.0 | **7.360** (min of 3) | 53.32 |
| /M1_BATN | **B.Cu 4 oz** | 5,106.6 | **16.700** | 19.71 |
| /M1_PHASE_A | In2 1.5 oz | 622.3 | 10.242 | 20.50 |

Converted with IPC-2221 §6.2 **at each layer's own k** (0.048 external, **0.024 internal**),
ΔT = 20 K:

| conductor | current it can carry | of 60 A |
|---|---|---|
| BATP on In1 (7.360 mm, 1.5 oz) | **9.25 A** | **15 %** |
| BATP on F.Cu (6.400 mm, pads-only **upper bound**) | 34.05 A | 57 % |
| **BATP rail total on the board of record** | **43.30 A** | **72 %** |
| BATN on B.Cu (16.700 mm) | **68.25 A** | **114 % — passes** |
| phase A on In2 (10.242 mm) | 11.76 A | 20 % |

**So the board of record's battery rail carries ≈43 A of 60 A — it is 1.39× short — and its
phase inner path is decorative.** No board in this programme has a proven 60 A rail.

**And the inner layer cannot ever carry it on this stackup.** At 1.5 oz an inner conductor
needs **96.99 mm** of width for 60 A (`04_rail.log`); the cell is **86.27 × 80.03 mm**
(`esc-placement/REPORT.md:65`). 96.99 > 86.27, so no placement can make the In1 route work.
The rail is a 4 oz **outer** conductor or it is nothing.

### 1.6 The 6.991 mm figure is conservative — the exact split is 5.374 mm

`04_rail.py` solves the two-face split properly instead of halving the width:

| combination | width for 60 A at ΔT 20 K |
|---|---|
| F.Cu alone (4 oz) | **13.981 mm** |
| **F.Cu + B.Cu (both 4 oz), exact split** | **5.374 mm** |
| F.Cu + In1 (4 oz + 1.5 oz inner) | 10.328 |
| F.Cu + In1 + In2 | 8.058 |
| **F.Cu + B.Cu + In1 + In2** | **3.970** |
| In1 alone (1.5 oz inner) | 96.991 |
| In1 alone **if it were 4 oz** | 36.372 |
| F.Cu + In1@4oz | 7.960 |

Because I ∝ A^0.725, halving the current needs 0.384× the area, not 0.5× — so the published
**6.991 mm is 30 % conservative**. Every published PASS/FAIL is re-stated against both.
**An inner layer is half-rate per unit copper (k 0.024 vs 0.048)**, which is why a 4 oz inner
(36.37 mm) is still **2.6× worse than the bare B.Cu** (13.98 mm).

---

## 2. The three numbers in circulation: PROVEN vs NOT

### 2.1 370.119 cm² — the compacted placement. **UNSAFE. Do not build.**

| PROVEN | NOT proven |
|---|---|
| area 370.119 cm², two methods, 0.0000 apart | that any 60 A conductor exists |
| 687/687 footprints on F.Cu, **0 on B.Cu** | that it is routable at 4 oz |
| fill 70.84 %, min part gap +0.600 mm, 0 pairs < 0.5 mm | that the 2.700 mm it measured is its worst case |
| DRC **934** at 4 oz/0.250 (41 shorts, 466 clearance, 199 dangling, 81 mask bridge) | — |
| unconnected **1,620** on pcbnew (1,542 +78) | — |
| phase corridor **2.700 / 3.400 / 4.912 mm**, and **the reading is flat in R** ⇒ a real pinch, not an endpoint artefact | — |

The failure is 2.0–2.6× against the exact requirement and 2.6–3.4× against the published
one, and because the instrument ignores copper the true corridor is **smaller still**.

### 2.2 382.709 cm² — the power-first placement. **The best artefact. Still not demonstrable.**

| PROVEN | NOT proven |
|---|---|
| area 382.709 cm², two methods | that the battery rail carries 60 A — the board has **0 tracks, 0 vias, 0 zones**; there is nothing to test |
| 687/687 on F.Cu, **0 on B.Cu** | that its 413 DRC items are survivable — they are footprint-bound (§4) |
| **all 18 phase conductors 7.600 mm** at a 2 mm fan-out | 7.600 at a 0 mm fan-out = **3.700 mm**, a 1.9× window dependence |
| **413 DRC at 4 oz/0.250** — 371 × 0.2000 mm pad gaps + **42 annular rings, and this board has no vias at all, so all 42 are PTH pad rings** ⇒ all 413 are footprint-bound | that it is routable: **2,196 unconnected** (worse than the original's 1,542, because it carries no copper) |
| out-of-scope cost of the corridor is **measured**: 12.590 cm² = the whole difference from 370.119 | the In1/In2 plane widths (A7) — and §1.5 now shows the In1 route is impossible anyway |

The 0.2000 mm gaps and the 42 rings are the same 413 on every board in the programme: they
are the **4 oz footprint blocker**, not a placement defect.

### 2.3 491.732 cm² — the original board. **Oversized AND not proven adequate.**

| PROVEN | NOT proven |
|---|---|
| area 491.732 cm², two methods | **that it is routable** — the board is **2.88 % routed**, 154 segments, 16 nets of 556, 1,542 unconnected (`AGENT_BOARD.md:923`). "Certainly routable" is an area-based assumption, not a result. |
| DRC **523** at 4 oz/0.250 (414 clearance, 70 annular, 16 via_dia, 16 dangling, 4 track, 3 neck) — reproduces the board's own split exactly | **that its battery rail carries 60 A: it carries ≈43.3 A (§1.5)** |
| unconnected **1,542** | **that its phase corridor is adequate: 5.346 / 5.400 mm on phases B and C** (§1.3) |
| 0 on B.Cu; 96 zones / 154 segments / 1,990 vias | that its In1 BATP pour can ever carry the rail — it cannot (96.99 mm > 86.27 mm cell) |

**This is the correction the board needs:** 491.732 cm² is *oversized*, not *safe*. It buys
room, and room is not a current rating.

---

## 3. The demonstrable area — does the four-condition board exist?

**No.** Checked on the best candidate, `powerfirst` at 382.709 cm²:

| # | condition | verdict | evidence |
|---|---|---|---|
| 1 | all six phases at 7.400 mm or better | **PASS at a 2 mm fan-out; FAIL at 0 mm** | 18/18 conductors 7.600 mm (R=2), 3.700 mm (R=0) — `02_corridor.log` |
| 2 | **battery rail passing at bus current** | **FAIL / UNPROVEN** | BATP free F.Cu **1.400 mm** vs 5.374 required (3.8× short), and the board carries **no copper at all** — `01_area.json`, `02_corridor.log` |
| 3 | 0 components on B.Cu | **PASS** | 687/687 on F.Cu — `01_area.log` |
| 4 | **DRC at the correct rules** | **FAIL, irreducibly** | 413 at 4 oz/0.250: 371 intra-footprint 0.2000 mm gaps inside 9 footprints + 42 PTH rings. No placement can move them. |

**Two conditions fail.** Condition 4 fails on all three boards and cannot be fixed by any
area: it is the owner's three-way decision already on the board (fab signs 0.200 mm at 4 oz /
drop to 2 oz / change U201 + 6 × LQFP-48 + J202/J203). Condition 2 fails because the rail has
never been drawn on a 4 oz outer, and the inner route it was planned on is geometrically
impossible at 1.5 oz.

---

## 4. The range, with the binding constraint named

Method (`06_area_range.py`): take the measured 382.709 cm² as the base, and price each rail
fix as the **parts-face channel** it consumes, using the one calibrated conversion this
programme has — the phase corridor cost the measured 12.590 cm² for 522 mm²/cell of reserved
channel, i.e. **k = 0.402 mm² of board per mm² reserved**. Rail channel length = the measured
BATP span **49.13 mm**; rail free width = the measured **1.400 mm**.

| arm | what the rail needs | area | vs 491.732 |
|---|---|---|---|
| **back-layer arm** | BATP wholly on the bare B.Cu plane — **13.981 mm neck** (one 4 oz face carries it alone); 0 components on B.Cu, so **no parts-face channel** | **382.71 cm²** | **−109.02 (−22.2 %)** |
| **X — fixed by re-placing** | BATP gets its own F.Cu corridor at **5.374 mm**, paired with a B.Cu half | **387.42 cm²** (band 385.1–394.4) | **−104.31 (−21.2 %)** |
| **Y — needs more parallel feed** | BATP on all four layers at **3.970 mm** | **385.75 cm²** (band 384.2–390.3) | **−105.98 (−21.6 %)** |
| **Z — inner-layer weight change** | In1 → 4 oz; BATP on F.Cu + In1@4oz at **7.960 mm** | **390.48 cm²** (band 386.6–402.0) | **−101.25 (−20.6 %)** |

**The binding constraint is the parts-face copper width of `/M1_BATP`.** Not total area, not
parts density, not creepage. Every other 60 A net already has its room or does not need any:

- the **three phases** have 7.600 mm ≥ 5.374 mm ✔ (and ≥ 6.991 on the conservative reading),
- **BATN** is a back-layer plane that already measures above requirement at 16.700 mm ✔,
- only **BATP** is pinched to 1.400 mm, and only BATP drives the range.

**Z is the worst lever, and that is a real result:** an inner conductor is half-rate, so a
4 oz inner (36.372 mm alone; 7.960 mm paired with F.Cu) is *worse* than spending the empty
back layer (13.981 mm alone; 5.374 mm paired with B.Cu). Buying inner copper to fix this rail
buys 20 % less than using the layer that is already bare.

### 4.1 Which I would build

**382.71 cm² — the power-first placement, with BATP and BATN carried as 4 oz back-layer
planes.** Reasons, in order:

1. It is the only artefact in the programme whose **18 phase conductors** pass at a 2 mm
   fan-out, and it passes on the **most conservative** requirement (6.991), not the exact one.
2. It has **0 components on B.Cu**, so the layer that can fix the rail is empty and free — the
   rail's price is a copper drawing plus ~21 vias per transition, not cm².
3. Its 413 DRC items are **exactly** the footprint blocker every other candidate also has, so
   choosing a bigger board buys nothing on the condition that actually fails.
4. Shrinking further is pointless anyway: the **spreader** is 352–528 cm² (§5).

I would **not** build 370.12 (2.700 mm phase corridor) and I would **not** pay for 491.73 (no
proven advantage — its rail is 43.3 A and its phase B is 5.346 mm).

**What must happen before either is true:** the 4 oz footprint decision, and a drawn-and-measured
BATP back-layer plane. Neither is an area question.

---

## 5. The heat spreader — mandatory, and OUTSIDE the board outline

**Mandatory.** 60 A is **1.67× the board-only junction limit** (52.0 / 35.9 / 26.8 A at RthJA
22.4 / 40 / 62 °C/W, TA 45 °C; central 35.9 A → 60/35.9 = 1.67). This is a design fact, not a
defect: `REV_B_ARCHITECTURE.md:204` already lists "thermal soak at 60 A with the production
heat spreader" as a test prerequisite (cited here from `esc-current-place/REPORT.md:139`).

**Outside the outline.** `IPTC014N10NM5` is a **TO-Leaded Top-side-cooled (TOLT)** package.
Its thermal path is its top; `RthJC 0.4 K/W max` is junction-to-**case-top**. With the case
held at 95 °C the junction bound exceeds 300 A per device — junction temperature stops being
the limit and the **spreader** becomes it. The heat therefore leaves **above F.Cu**, through
a plate clamped to the package tops. It is a separate mechanical part with its own plan area,
and it appears in **none** of 491.732 / 382.709 / 370.119.

**Size** (§`06_area_range.log`): P = 7.332 W per FET × 36 = **264.0 W**.

| h_eff | ΔT | spreader area | × the 382.709 cm² board |
|---|---|---|---|
| 250 W/m²K (forced) | 20 K | **527.9 cm²** | 1.38× |
| 250 W/m²K | 30 K | **351.9 cm²** | 0.92× |
| 100 W/m²K | 20 K | 1,319.8 cm² | 3.45× |
| 100 W/m²K | 30 K | 879.8 cm² | 2.30× |

**Why this changes the packaging answer.** At 250 W/m²K the spreader is **0.92–1.38× the
board's own area**. Below ≈352 cm² the board stops being the largest object in the stack, so
shrinking 382.71 → 370.12 (a 12.6 cm² win, 3.3 %) changes nothing in the airframe while adding
a 2.700 mm phase corridor. The board-side 70 W of shunt + copper loss needs **no** extra area:
the copper the current already pays for *is* the spreader (`esc-area-floor/REPORT.md:236-238`).

---

## 6. Assumption register

| # | assumption | value | direction if wrong |
|---|---|---|---|
| A1 | allowed copper rise ΔT | 20 K | the whole width table scales; at 30 K the rail needs 4.55 mm two-face and the range loosens ~15 % |
| A2 | fan-out radius for a corridor endpoint | 2 mm | **load-bearing**: 3.700 mm at 0 mm, 9.300 mm at 3 mm |
| A3 | channel→board conversion k | 0.402 (measured once) | bands given: X 385–394, Y 384–390, Z 387–402 |
| A4 | rail channel length = the measured BATP span 49.13 mm | — | proportional |
| A5 | BATN resolved as a 16.700 mm B.Cu plane | measured on the board of record | not verified on a new placement |
| A6 | spreader h_eff | swept 100 / 250 W/m²K | 2.6× spread in area |
| A7 | 21 vias per 60 A transition is **not** costed | board's own figure, `AGENT_BOARD.md:462` | could add via-cluster area; not measured |

## 7. What this does NOT establish

- **No route was drawn.** 0 segments were added. The rail fix is specified, not executed.
- **The back-layer arm is ANALYTICAL.** Nobody has drawn a 13.981 mm BATP plane on B.Cu and
  measured it; the requirement comes from IPC-2221 and the *availability* from 0 parts on
  B.Cu. That is the single measurement standing between "range" and "board".
- **The 413 DRC items are untouched** — they are the owner's decision, and no area answers them.
- Zone refills were not re-run; the copper-area figures are the board of record's own fills.
- Via ampacity at 4 oz (0.300 mm drill, 0.700 mm pad) was not solved; 21 vias per transition
  is a cited figure, not a result of this unit.

## 8. Reproduce

```powershell
$ev="E:\engineering-portfolio-audit\evidence\esc-area-honest"
$kpy="C:\Program Files\KiCad\9.0\bin\python.exe"; $py="C:\Program Files\Python312\python.exe"
& $kpy "$ev\01_area.py"            # areas, two methods, census, stackup
& pwsh -NoProfile -File "$ev\03_drc.ps1"   # DRC + rule-file-read assertion
& $kpy "$ev\02_corridor.py"        # corridor, R sweep, all 18 conductors, net-name audit
& $kpy "$ev\04_rail.py"            # required widths by layer combination, unconnected, copper area
& $kpy "$ev\05_plane_neck.py"      # plane necks: In1 BATP, B.Cu BATN, In2 phase A
& $kpy "$ev\05b_verify.py"         # grid convergence + pair robustness + amps per neck
& $py  "$ev\06_area_range.py"      # the range and the spreader
```

## 9. Artefacts

| file | what |
|---|---|
| `boards/` | the three boards, **copies**, sha256 in `01_area.json` |
| `01_area.py/.log/.json` | §1.1 area by two methods + census + stackup |
| `02_corridor.py/.log/.json` | §1.3 corridor reproduction, R sweep, 18 conductors, net audit |
| `03_drc.ps1/.log/`, `drc/` | §1.2 DRC + the three-arm rule-read assertion |
| `04_rail.py/.log/.json` | §1.6 required widths, unconnected counts, per-net copper area |
| `05_plane_neck.py/.log/.json` | §1.5 plane necks |
| `05b_verify.py/.log/.json` | §1.5 grid convergence, pair robustness, amps per neck |
| `06_area_range.py/.log/.json` | §4 range, §5 spreader |

## 10. Correction history

1. **`BATN: no path` is withdrawn.** The published pair spans two different nets (`M1_SHA_I`
   → `/M1_BATN`), so the destination pad is an obstacle. It returns null on all three boards
   including the board of record. The real BATN carrier is a 16.700 mm B.Cu plane carrying
   68.25 A — **it passes**.
2. **`Phases 7.400 / 7.674 / 7.674` is reproduced only as 7.600 / 7.600 / 7.600**, and the
   number is **endpoint-dependent** (3.700 mm at a 0 mm fan-out). Both readings pass the
   conservative 6.991 mm; the 7.400 was not a hard pinch.
3. **`BATP 1.400 mm (-80 %)` stands** and reproduces exactly at every radius — but it is a
   **front-face** number. On the board of record the same rail measured as a plane gives
   43.30 A of 60 A, which is the number that matters.
4. **`491.73 cm² is certainly routable` is not supported.** The board is 2.88 % routed with
   1,542 unconnected, its phase B corridor is 5.346 mm, and its rail is 43.3 A.
5. **`6.991 mm per face` is conservative by 30 %** — the exact two-face split is 5.374 mm.
   Nothing in this report depends on the difference, but the requirement should be restated.
6. **`0 DRC violations`** is what the power-first board returns at the project's own rules.
   The correct-rules answer is 413. The 0 is a false green and must not be quoted.