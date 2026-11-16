# esc-3oz-bigboard — does the ORIGINAL 491.73 cm2 placement at 3 oz reach 11.963 mm?

**Wave 15 · one question.** On the ORIGINAL 491.73 cm2 placement (`esc_rev_b.kicad_pcb`), at
3 oz outer copper, does the phase corridor reach the **11.963 mm** that 43.5 A requires?
If yes, the 4-layer contradiction is resolved without adding layers.

Input: `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` (the 491.73 cm² board of
record — see Step 1 for why the `D:/CodeProjects` copy at that path is a different file).
Instruments reused: `evidence/esc-placement-gate/` (gate.py, 02_measure.py, 01_standard.json,
04_drc.ps1, 05_drcdiff.py), `evidence/esc-3oz-build/` (rules_3oz_020, 03_stackup_3oz) and
`evidence/esc-corridor-instrument/` (corridor_lib.py). Work is done on COPIES under `boards/`;
nothing is written to the repo.

Provenance of every number below: measured by the tools named, on this board, this run.

## Status

- [x] Step 1 — 3 oz stackup + DRC 0.200/0.200, set diff vs 4 oz
- [x] Step 2 — corridor width per phase on the ORIGINAL board
- [x] Step 3 — per-phase pass/fail and shortfall
- [x] Step 4 — ampacity table at 3 oz with correct k (phase, BATP, BATN, BATP_IN, barrels)
- [x] Step 5 — gate G1–G8 on this board, exit code
- [x] Step 6 — plain YES/NO and the board size that would close a failure

## Step 1 — 3 oz DRC on the original board

**Which file is "the original".** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
sha256 `9925…95DDD` is byte-identical to the programme's board of record
(`esc-placement-gate/boards/orig.kicad_pcb`, `esc-current-place/esc_rev_b_orig.kicad_pcb`):
**491.732 cm²**, 173.95 × 283.08 mm, 687 footprints (all on F.Cu), **154 tracks, 1,990 vias,
96 filled zones**. The file at `D:/CodeProjects/drone-arm/…/esc_rev_b.kicad_pcb` is a
*different* file — sha `9BDD…5776`, 2,797,200 bytes, 646 footprints, **0 tracks, 0 vias,
0 zones**, 150.15 × 150.15 mm — i.e. a bare placement of another state, not the 491.73 cm²
board. Every number below is from the `9925…` file, copied to `boards/big4oz.kicad_pcb`.

**Stackup (`02_stackup.json`).** F.Cu and B.Cu 0.140 → **0.1050 mm**, core dielectric
0.795 → 0.865 mm so the board stays 1.600 mm; In1/In2 untouched at 0.0525. Proven three
ways, because the pcbnew stackup read-back is unavailable in this build:
R1 re-parse of the **saved** file (0.105 / 0.0525 / 0.0525 / 0.105, general thickness 1.6),
R2 `pcbnew.GetBoardThickness() = 1.6000`, `m_HasStackup = True`,
R3 text diff between the two files = **exactly 6 lines (3 substitutions)** and identical
object census (687 fps / 154 tracks / 1,990 vias / 96 zones / 4 drawings). The predecessor
evidence dir published an **empty** read-back list as its "read-back"; that is not repeated here.

**DRC (`03_drc.ps1`, `04_setdiff.json`).** Same board, same run, only the rule arm changes.

| arm | rules | violations | unconnected |
|---|---|---|---|
| A | 4 oz / 0.250 (`rules_4oz_025`, 9 rules) | **523** | 499 |
| B | 3 oz / 0.200 (`rules_3oz_020`, 9 rules) | **102** | 499 |
| control | same 3 oz board, clearance forced to 1.000 | 611 | — |
| arm C | same 3 oz board, **no `.dru`** (project rules) | 126 | — |

Arm A reproduces the recorded 4 oz total **523** exactly, so the missing `.kicad_pro` beside
the copy is immaterial. The control moves the count 102 → 611, and arm C returns a different
126: **the rule file is being read**, and it — not the project — is what produced 102.

**SET DIFF 3 oz − 4 oz (row key = type + item description@position to 0.01 mm):
GONE 421, ADDED 0, unchanged 102 — the residual set is *identically* the 4 oz survivors.**

| | count |
|---|---|
| GONE by type | clearance **414**, track_width 4, connection_width 3 |
| REMAIN by type | annular_width 70, via_diameter 16, via_dangling 16 |

The clearance rows that clear are the pad-gap ones, and they clear completely:

- pad-to-pad clearance rows at 4 oz: **371**, of which **0 remain** at 0.200 mm → all clear
- their actual gap is **0.200 mm median, 0.200 mm max** — i.e. exactly at the 3 oz floor, and
  **0 rows sit below 0.200 mm**. The `89 pad-pad gaps` of the compacted board appear here as
  371 rows; the same conclusion holds and on a much larger population.
- by family, none left behind: LQFP-48 STM32G431 **258 → 0**, USB-C J202/J203 **38 → 0**,
  QFN-80 U201 **75 → 0**.

So the expectation that the pad gaps clear again is **verified, and more strongly than asked**:
not only do they clear, the surviving 102 rows are the *same rows* as at 4 oz, and no new row
appears anywhere on the board.

## Step 2 — the phase corridor on this board

**Instrument.** `05_measure.py` is `esc-placement-gate/02_measure.py` verbatim (which is
`esc-corridor-instrument/corridor_lib.py`: copper not pads, zone **fill** polygons not
outlines, region seeding, foreign copper = all copper of other nets, `gap = 2t`,
`passable = gap − 2×0.25`). Only the board path and two extra terminal pairs change.
Calibration re-run at this grid: 1.400/3.449/6.991/7.992/8.972/**11.963** designed →
1.360/3.440/6.960/7.920/8.960/**11.920** measured, **worst |err| 0.072 mm**.
The requirement itself (11.963 mm) is measured by the instrument as 11.920.

**The stackup cannot move this number, and that is checked, not assumed.** 90 rows were
compared against the 4 oz board's own published measurement: **0 rows moved, worst
|Δ| 0.000 mm** — the corridor is 2-D copper geometry.

**What the corridor is measured against matters, so three arms were run (`09_phase_pads.py`).**
The compacted placements carry **zero zones, and powerfirst zero tracks and zero vias**, so
the published 9.420 mm was a pads-only measurement. To compare like with like:

| arm | obstacles counted as foreign copper | why |
|---|---|---|
| **Q** | foreign **pads** only | the convention the 9.420 mm / 7.400 mm compacted numbers were measured under |
| **P** | pads + 154 tracks + 1,990 vias | routed copper added |
| **Z** | + the 96 zone **fills** | the validated default, and what the gate uses |

**Per phase, per cell (all six cells measure identically — see Step 3).** Each phase has two
real terminal pairs (the LS-drain tab and the HS-source lead, labelled `_H`); the table quotes
the **narrower** of the two, which is what binds:

| phase | arm Q pads only | arm P +tracks/vias | arm Z as built (gap) | requirement | ratio (Q) |
|---|---|---|---|---|---|
| PHASE_A | **8.300 mm** (both pairs) | 8.300 | 3.900 (gap 4.400) | 11.963 | **0.69×** |
| PHASE_B | **5.420 mm** (pairs 5.420 / 5.500) | 5.020 | **−0.500 = severed** (gap 0.000) | 11.963 | **0.45×** |
| PHASE_C | **5.420 mm** (both pairs) | 5.420 | 0.700 (gap 1.200) | 11.963 | **0.45×** |

The headline numbers are **grid-invariant**, not one-grid artefacts. `10_crosscheck.py`
re-measures cell 1 at `h = 0.040 / 0.020 / 0.010 mm`:

| h mm | PHASE_A arm Q | PHASE_B arm Q | PHASE_A arm Z | PHASE_B arm Z |
|---|---|---|---|---|
| 0.040 | 8.300 | 5.500 | 3.900 | −0.500 (severed) |
| 0.020 | 8.300 | 5.500 | 3.900 | −0.500 |
| 0.010 | 8.300 | 5.500 | 3.920 | −0.500 |

Spread across a 4× pixel refinement: **0.000 mm** for both arm-Q rows. The severed PHASE_B is
therefore a property of the copper, not of the raster: at `h = 0.010 mm` there is still no free
path at any clearance. At `h = 0.020` the calibration error is 0.032 mm, at `h = 0.040` 0.072 mm.

`−0.500` is the instrument's floor for `gap = 0`: no free path exists at any clearance, so
`passable = 0 − 2×0.25`. It means "cannot be widened at all", not "0.5 mm short".

**The area premise is refuted by the measurement.** 491.73 cm² is 1.285× the compacted
382.71 cm², and on the like-for-like pads-only convention the phase corridor went **down**:

| placement | area | phase corridor (pads-only, same instrument) |
|---|---|---|
| powerfirst (compacted) | 382.71 cm² | **9.420 mm** (all six phases) |
| **original (this board)** | **491.73 cm²** | **8.300 mm** best / 5.420 mm worst |

28 % more area bought **−11.9 %** corridor. The corridor is not an outline property: it is
bounded by the pad field *inside* each ~30.6 mm cell — six `PG-HDSOP-16_TOLT` FETs (26 pads
each, including a 10.20 × 7.00 mm drain tab), a 2-pin and a 3-pin M5 power lug, and twelve
shunts — which the compaction rearranged in the **favourable** direction.

## Step 3 — per phase

The six cells are **symmetric**: every cell returns the same three numbers (arm Q
8.300 / 5.420 / 5.420; arm Z 3.900 / 0.000 / 0.700), because each cell is a repeat of one
footprint set at identical relative geometry. The asymmetry that matters is **between the
three phases**, and it is large:

| phase | available (Q) | required | shortfall | as-built (Z) | as-built shortfall |
|---|---|---|---|---|---|
| A | 8.300 | 11.963 | **3.663 mm** | 3.900 | 8.063 mm |
| B | 5.420 | 11.963 | **6.543 mm** | severed (floor −0.500) | ≥ 11.963 mm |
| C | 5.420 | 11.963 | **6.543 mm** | 0.700 | 11.263 mm |

PHASE_A escapes past the outer TOLT tab; B and C must squeeze between the inner tabs, which is
2.880 mm narrower before any copper is drawn. **No phase reaches 11.963 mm under any of the
three obstacle conventions** — the best single number on this board is 8.300 mm, 0.69× of what
3 oz needs.

The phase nets are implemented as **pads + zone fill, with zero track copper** on F.Cu
(`09_phase_pads.json` census: pad 225.47 mm² + zone 183.73 mm² = 409.20 mm² per phase net).
So the corridor is a *pour* width, not a trace width, and the 3.9 mm as-built reading is the
width of the channel the phase pour already occupies between ground pour.

## Step 4 — ampacity at 3 oz, correct k

`k = 0.048` external (F.Cu/B.Cu, 105 µm), `k = 0.024` internal (52.5 µm), ΔT 20 K,
barrel 0.4 mm drill / 25 µm plate = 0.03142 mm² = 48.69 mil² → **1.50 A per barrel**
(the 3.00 A form is k=0.048 on a barrel, i.e. the external coefficient on a surface with no
free-air face; the gate asserts `I_BARREL < 1.6` so that arm cannot be re-entered).

| element | layer | avail mm | req mm | avail mm² | cap A | I req | ratio | verdict |
|---|---|---|---|---|---|---|---|---|
| PHASE, best cell as-built | F.Cu | 3.900 | 11.963 | 0.4095 | **19.30** | 43.5 | 0.44 | **FAIL** |
| PHASE, worst cell as-built | F.Cu | 0 (severed) | 11.963 | 0 | **0.00** | 43.5 | 0.00 | **FAIL** |
| PHASE, best, pure placement | F.Cu | 8.300 | 11.963 | 0.8715 | **33.37** | 43.5 | 0.77 | **FAIL** |
| PHASE, worst, pure placement | F.Cu | 5.420 | 11.963 | 0.5691 | **24.50** | 43.5 | 0.56 | **FAIL** |
| BATP_IN | B.Cu | 0.000 | 10.656 | 0 | **0.00** | 40.0 | 0.00 | **FAIL** |
| BATP | B.Cu | 0.000 | 10.656 | 0 | **0.00** | 40.0 | 0.00 | **FAIL** |
| BATN | B.Cu | 22.939 | 10.656 | 2.4086 | **69.74** | 40.0 | 1.74 | PASS |
| In1/In2 alone at 40 A (ref) | inner | 55.443 | 55.443 | 2.9108 | 40.00 | 40.0 | 1.00 | REF |

Barrels, 1.50 A each, counted within 7 mm of each terminal on this board: the counts are
**bimodal across the six cells** (routing, not placement, so it is not symmetric): bus/shunt
sites have **0, 0, 0, 0, 0, 0, 40, 40, 40, 40, 40, 40** barrels — **need 27 → 6 of 12 sites
short**, capacity 0.0–60.0 A against 40 A; leg/drain-tab sites have **2 ×6 and 15 ×6** —
**need 17 → 12 of 12 short**, capacity 3.0–22.5 A against 25.1 A. At the withdrawn
3.00 A/barrel the requirement falls to 14 and 9, and G6 **still fails** (6 of 12 and 6 of 12),
so the barrel constant never decided this verdict — but it does decide *how much* is missing,
which is why it is pinned at 1.50 A and asserted.

Read against the settled compacted figure (**36.58 A, 0.84×**) the original board is worse
again: 33.37 A / 0.77× at best, 19.30 A / 0.44× as built, and **0 A on PHASE_B**, whose
corridor is severed in every cell as poured. Note the rails here live on **F.Cu pours**
(BATP zone 869.17 mm² of F.Cu, BATN pad only), so the B.Cu bus requirement in this gate is a
*new* requirement against a back layer that is currently a solid ground pour — hence BATP and
BATP_IN reading 0 A on all 12 rows.

## Step 5 — the gate, G1–G8

`07_gate3oz.py`, same logic and same constants asserted in-file as `esc-placement-gate/gate.py`:
phase 11.963 mm / bus 10.656 mm (3 oz, k=0.048), barrel 1.50 A, Tj 175 °C at TA 45 °C.

| ID | condition | verdict | worst row | measured | margin |
|---|---|---|---|---|---|
| G1 | phase corridors ≥ 11.963 mm on F.Cu | **FAIL** | M1 PHASE_B | **−0.500** (severed) | −104.2 % |
| G2 | BATP_IN / BATP ≥ 10.656 mm on B.Cu | **FAIL** | M1 BATP_IN | **−0.500** (severed) | −104.7 % |
| G3 | BATN ≥ 10.656 mm on B.Cu | PASS | M2 BATN | 22.939 | +115.3 % |
| G4 | no component on B.Cu / inner layers | PASS | components on B.Cu | 0 (F = 687) | 0 |
| G5 | heat spreader reserved and stated | **FAIL** | spreader reserve | 0/36 TOLT covered, 0 markers, no declaration (need 181.2 cm²) | — |
| G6 | barrels per rail transition | **FAIL** | BATP_IN @ R1123.1 | 0 vs 27 | −27 |
| G7 | Tj ≤ 175 °C at TA 45 °C with spreader | PASS | Tj with spreader | 101.4 °C | +73.6 °C |
| G8 | back-layer capacity budget per cell | **FAIL** | cell 6 | 67.6 % of uncommitted B.Cu | −17.6 % |

**3 PASS, 5 FAIL, 0 unmeasurable. EXIT CODE = 1.**

G1 fails on all 18 phase rows, not just the worst: the best row is 3.900 against 11.963.
G5 fails because no spreader reservation was ever drawn on this board (0 `Cmts_User`
rectangles, no `SPREADER_EXCHANGE_CM2` text) — a missing deliverable, not a physics result.
Re-running the identical gate at 4 oz (`--t-ext 0.140`, a labelled reproducibility arm) gives
the same verdict set and exit 1: **this board does not pass at 4 oz either**, which is why the
programme compacted it in the first place. G8 is the only condition that moved between the
arms (51.5 % → 67.6 % of the cell budget, both failing).

## Step 6 — the answer

**NO.** On the original 491.73 cm² placement at 3 oz the phase corridor does **not** reach
11.963 mm. The best number anywhere on the board is **8.300 mm** (PHASE_A, pads only), i.e.
**0.69×** the requirement; PHASE_B and PHASE_C are **5.420 mm** (0.45×). Measured as the board
stands, with its pours: 3.900 / severed / 0.700 mm. The gate exits **1**.

**Shortfall: 3.663 mm on the best phase, 6.543 mm on the other two** (as-built: 8.063 mm,
≥ 11.963 mm on the severed phase, 11.263 mm).

**How much larger would the board have to be: no size closes it, and that is measured, not
argued.** The premise was that corridor scales with area (491.73 cm² → 12.06 mm). Measured,
28 % more area produced **12 % less** corridor (382.71 cm² → 9.420 mm; 491.73 cm² →
8.300 mm). The corridor is set by the pad field inside one ~30.6 mm cell, not by the outline,
so an empty margin buys nothing. For the record, the premise's own model inverted would
demand **491.73 × 11.963/8.300 = 708.7 cm²** (+44 %), and an outline-distance model would
demand **1,021 cm²** (+108 %) — but the counter-example above says neither number is
achievable by growing the board.

What does close the phase gap, stated as measurements rather than a plan: the requirement
fits inside geometry this board already has **if the 43.5 A is split across two external
faces** — two identical faces need `11.963 × 2^(−1/0.725) = 4.598 mm` each, and the placement
already offers 5.420 mm at its worst, with G4 confirming a free B.Cu. That is a routing and
pour-plan change (and a layer-stack decision for the spreader), not a bigger outline. The
4-layer contradiction therefore stands: **the original board is not the escape route.**

---

## Files, and what each one is evidence of

| file | what it proves |
|---|---|
| `01_standard3oz.py` → `01_standard.json` | 11.963 mm / 10.656 mm / 1.50 A, after re-passing all three settled 4 oz vectors |
| `02_stackup3oz.py` → `02_stackup.json` | the board is 105 µm outer, by saved-file re-parse + pcbnew thickness + a 3-substitution text diff |
| `03_drc.ps1` → `drc_big4oz.json`, `drc_big3oz.json`, `drc_big3oz_ctl100.json`, `drc_big3oz_project.json` | 523 → 102, and that the rule file (not the project) is the cause |
| `04_setdiff.py` → `04_setdiff.json` | GONE 421 / ADDED 0 / residual set identical; 371 pad-to-pad rows clear |
| `05_measure.py` → `05_big3oz.json` | the validated corridor instrument on this board, with calibration and a stackup-invariance control |
| `06_phase_fine.py` → `06_phase_fine.json` | the same phases at half the pixel pitch, plus a straight-line pinch diagnostic |
| `07_gate3oz.py` → `gate_big3oz.json`, `gate_big4oz.json` | G1–G8 and exit codes, constants asserted in-file |
| `08_ampacity.py` → `08_ampacity.json` | per-element ampacity at 3 oz with k per conductor type |
| `09_phase_pads.py` → `09_phase_pads.json` | the three obstacle conventions, and the F.Cu copper census per net |
| `10_crosscheck.py` → `10_crosscheck.json` | grid refinement 0.040 → 0.010 mm, spread 0.000 mm |

## Limitations, stated rather than hidden

1. **The pcbnew stackup read-back is unavailable in KiCad 9.0.7** (`GetStackupDescriptor()`
   returns a bare `SwigPyObject`). The 105 µm claim rests on the saved-file re-parse plus
   `GetBoardThickness()`; the numbers a fab reads are exactly those.
2. **The gate's "corridor" is free space, not existing copper width.** On a board whose
   phases are pours, a wide pour can coexist with a narrow corridor. That is why step 4 reports
   capacity two ways — from the corridor (19–33 A) and from the copper that exists (the census
   in `09_phase_pads.json`) — and why the three obstacle arms were measured.
3. **A severed reading means "no free path", not a measured zero.** Its numeric floor is
   `−2 × clearance = −0.500`; it is quoted as a verdict, never as a millimetre of defect.
4. The 1,990 vias and 154 tracks on this board are treated as fixed obstacles. Arm P shows
   removing them changes the corridor by 0.00–0.48 mm, so the conclusion does not hinge on that.