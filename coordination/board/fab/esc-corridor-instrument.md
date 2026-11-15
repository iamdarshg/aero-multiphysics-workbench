# The power-corridor instrument, rebuilt — and the battery rails re-measured

**Scope.** Rebuild `esc-current-place/08_corridor_bottleneck.py` so it measures
foreign **copper** rather than foreign **pads**, never invents copper on a layer a
net does not occupy, and cannot print a PASS over its own FAIL. Then re-measure
`/M1_BATP`, `/M1_BATN` and `/M1_PHASE_A` on the three board states and state the
true deficit against 60 A.

**Boards measured (copies read only, nothing written outside this directory):**

| tag | file | sha256 |
|---|---|---|
| original (board of record) | `esc-current-place/esc_rev_b_orig.kicad_pcb` | `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD` |
| powerfirst (placement, no copper) | `esc_rev_b_powerfirst.kicad_pcb` | `4FB519AB85026694BCD6287472CD759E93A80AD014C1B7F7E09C1819D743132C` |
| compact (370.12 cm²) | `esc_rev_b_compact_stalefix.kicad_pcb` | `9F1963109C5ACB4B0942428D8AB9EB3D915EC640E74C0101D0E275AA601BE4F3` |

Host: KiCad **9.0.7**, `C:/Program Files/KiCad/9.0/bin/python.exe` (numpy 2.3.5,
scipy 1.17.1, shapely 2.2.0, PIL 12.0.0). Requirement constants are the settled
ones: **60 A** (`REV_B_ARCHITECTURE.md:18`), ΔT 20 K, **4 oz = 0.14 mm outer and
1.5 oz = 0.0525 mm inner** (stackup parsed from the board itself,
`(layer "F.Cu" (type "copper") (thickness 0.14))`, In1 `(thickness 0.0525)`).
That gives **13.981 mm of 0.14 mm copper = 1.9574 mm² cross-section**, and
**37.28 mm** if 60 A had to cross one 1.5 oz inner layer.

---

## 1. The five defects, as measured

The verifier's three are confirmed. Two more were found while rebuilding.

| # | defect | evidence |
|---|---|---|
| **1** | **PASS printed over its own FAIL.** `08_corridor.log:5` reads `BATP ... available 1.4 mm`, `:6` reads `BATN ... None`; `:20` prints `powerfirst narrowest 1.400 mm -> FAIL (-80.0%)`. `esc-current-place/REPORT.md:363` then publishes **7.400** as the "narrowest" and **PASS +5.9 %**, and `:34` carries the same claim in the top-line scorecard. 7.400 is the minimum over **three phase rows only**; the instrument's own minimum over all five is 1.400. | `08_corridor.log:5`, `:20`, `REPORT.md:34`, `:363` |
| **2** | **Copper fabricated on a layer that has none.** `REPORT.md:393` adds `B.Cu 9.5 × 0.14` to BATP. Measured here, twice: BATP's B.Cu copper is **0.000 mm² of zone, 0.000 mm² of track, 5.701 mm² of pads and 44.724 mm² of via barrels** — a via barrel is not a 9.5 mm-wide conductor. Corrected deficit is **1.735 mm²**, not 0.431, and the In1 neck that would be required is **33.55–37.28 mm**, not 8.21. | §3 census; `04_verdict.json` |
| **3** | **Pads counted, copper not.** `08_corridor_bottleneck.py:25-33` iterates `board.GetFootprints() → f.Pads()` and nothing else. On the placed boards that ignores **154 traces, 1,990 vias and 96 filled zones** (§3). On the power-first board, where 0 tracks and 0 zones exist, the omission is benign — which is why the defect went unnoticed: the first board it was run on had no copper to miss. | `00_probe_api.log`; §3 |
| **4** | **The terminal pad was "the first pad with that number".** Every FET pin here is a multi-pad group: `Q1101` pin 9 is **8 leads of 0.80 × 3.38 mm plus one 10.20 × 7.00 mm tab**. The old code seeded from the first match, i.e. a 0.80 mm lead, not the power tab. | pad dump in §3 |
| **5** | **The BATN row never measured BATN.** `08_corridor_bottleneck.py:110` uses `Q1102.1 → J1101.2`. Measured net names: `Q1102.1 = /Motor 1 power cell/M1_SHA_I`, `J1101.2 = /M1_BATN`. The old code resolves the net *from the first pad* and never asserts it, so its "BATN" row measured a sense net. That is why it printed `no path` — it was not looking at the battery rail. | pad dump §3; `02_calib.py` asserts the net on every terminal |

---

## 2. The corrected instrument

`corridor_lib.py` + `03_corridor.py`. Method:

1. **Copper, not pads.** For each layer, every object is converted through KiCad's
   own shape code: pads by `PAD.TransformShapeToPolygon` (true polygon, not the
   bounding box), traces as capsules, vias as discs, and zones by
   **`ZONE.GetFilledPolysList(layer)`** — the *fill*, with its holes, never the
   outline. An unfilled zone is **refused**, not read as "no copper"
   (`corridor_lib.py:layer_copper`).
2. **Obstacles = all foreign copper on that layer.** For rail *N*,
   `obs = (all copper) − (N's copper)`. Nothing else is excluded.
3. **Measured quantity.** `d = EDT(¬obs)`; `gap = 2·max{t : terminals still
   connected through d > t}` is the physical free gap; `passable = gap − 2·0.25 mm`
   is the widest track of *N* that fits at the 0.25 mm design clearance. Grid
   `h = 0.02 mm`, 18-step bisection, per layer, in a window of the terminal
   bounding box inflated 12 mm, clipped to the board.
4. **Terminals are regions, not points.** The seed is the area-weighted centroid
   of the whole pad group, and the seed set is every copper cell within 3 mm of
   it. A *point* seed caps the answer at the terminal pad's own clearance; a
   *fixed search radius* (the old `near()`, 40 cells = 2 mm) lets the seed jump
   past foreign copper. Region seeding does neither, and the two terminal caps are
   reported (`term_clear_A/B`) so a terminal-limited result is visible.
5. **Own-copper width.** A second field, `EDT(own copper)`, gives the widest
   continuous band through the rail's existing copper; along that path the
   **perpendicular chord is measured at every station** with shapely, giving a
   real cross-section per layer, the neck, its coordinate, and how many separate
   stations fall below the layer's requirement (`05_profiles.json`).
6. **Layers are asserted.** A rail's copper is counted from pads + tracks + zones
   per layer; a layer is a *conductor* only if zones or tracks exist there
   (`> 10 mm²`). Via barrels are counted separately and never become plane area.
   Declared sets, measured on the board of record:
   **BATP = {F.Cu, In1.Cu}, BATN = {B.Cu}, PHASE_A = {F.Cu, In2.Cu}.**
   The placement board inherits that set — it has no copper of its own to declare.
7. **No summary can contradict its rows.** The verdict is computed from the
   per-layer table only (§4), and a layer the rail does not occupy contributes
   zero, not an estimate.

---

## 3. Copper census (measured twice: analytic polygons and an independent raster)

`01_copper_census.py` → `01_copper_census.json`, `03_corridor.py` → `03_corridor.json`.
Board of record, mm²:

| net | layer | pads | tracks | vias | **zone fill** | in-plane (= conductor)+ |
|---|---|---|---|---|---|---|
| `/M1_BATP` | F.Cu | 348.125 | 0.000 | 44.724 | **869.165** | 1217.29 |
| `/M1_BATP` | In1.Cu | 5.701 | 0.000 | 44.724 | **5039.008** | 5044.71 |
| `/M1_BATP` | In2.Cu | 5.701 | 0 | 44.724 | **0.000** | 5.70 |
| `/M1_BATP` | B.Cu | 5.701 | 0 | 44.724 | **0.000** | 5.70 |
| `/M1_BATN` | B.Cu | 124.605 | 0.000 | 22.362 | **5106.610** | 5231.22 |
| `/M1_BATN` | F.Cu | 327.559 | 0 | 22.362 | **0.000** | 327.56 (pads only) |
| `/M1_PHASE_A` | F.Cu | 225.466 | 0.000 | 31.804 | **183.726** | 409.19 |
| `/M1_PHASE_A` | In2.Cu | 112.860 | 0.000 | 31.804 | **622.252** | 735.11 |

These reproduce the verifier's independent figures — **F.Cu 869.17, In1 5,039.01**
— to the last printed digit, which is what makes defect 2 citable: on the same
census, BATP's B.Cu zone is **0.000 mm²**, and the 9.5 mm the old report multiplied
by 0.14 mm does not exist.

The two scripts agree to **0.04 %** (e.g. BATP F.Cu 1262.53 vs 1262.01 mm²); the
whole difference is the via-barrel area, which `01` computes as πr² and `03` as a
24-gon polygon. Both agree that BATP's B.Cu has **0.000 mm² of zone and 0.000 mm²
of track** and 5.70 mm² of pads, so no conductor exists there either way.

Board inventories that make defect 3 concrete: original **687 footprints, 154
traces + 1,990 vias (2,144 track objects), 96 zones**; compact **687 footprints,
2,118 track objects, 96 zones**; powerfirst **687 footprints, 0 track objects,
0 zones**. Every zone is filled; **0 unfilled zones** on all three boards
(asserted, `03_corridor.json` → `unfilled_zones`), so no zone outline was mistaken
for copper and none was silently dropped.

---

## 4. Per-layer results

`gap` = physical free gap through all foreign copper; `pass` = gap − 0.5 mm (widest
track of that net at 0.25 mm clearance); `need` = 13.981 mm outer / 37.28 mm inner;
**`own`** = the rail's own transverse copper width (min perpendicular chord along
the widest continuous band); `bot` = number of separate stations along the corridor
whose available width is below that layer's requirement.

### Board of record (the only board with copper on these layers)

| rail | layer | copper present mm² | gap | pass | need | **own width** | at | bot |
|---|---|---|---|---|---|---|---|---|
| **BATP** | F.Cu | 869.17 zone + 348.13 pad | 3.991 | **3.491** | 13.981 | **FRAGMENTED** | — | 1 (min 3.02 @ 33.287,101.40) |
| **BATP** | In1.Cu | 5039.01 zone + 5.70 pad | 8.752 | **8.252** | 37.28 | **4.225 mm** | 46.187, 91.20 | 1 (min 7.78 @ 46.187,91.90) |
| **BATN** | B.Cu | 5106.61 zone + 124.61 pad | 25.006 | **24.506** | 13.981 | **35.407 mm** | 22.925, 90.48 | **0** |
| **PHASE_A** | F.Cu | 183.73 zone + 225.47 pad | 4.400 | **3.900** | 13.981 | **FRAGMENTED** | — | 1 (min 3.34 @ 25.023,63.89) |
| **PHASE_A** | In2.Cu | 622.25 zone + 112.86 pad | 15.758 | **15.258** | 37.28 | **12.503 mm** | 23.69, 51.39 | 1 (min 14.74 @ 22.39,56.59) |

**FRAGMENTED is a measurement, not a failure to measure.** On that layer the rail's
copper is physically in several pieces: at h = 0.05 mm on the board of record,
**BATP's F.Cu is 5 disconnected islands** and the two terminals land on **different
ones** (shunt pad on island 4, FET drain tab on island 1); **PHASE_A's F.Cu is 4
islands**, terminal A on island 2, terminal B on island 1. There is therefore no
continuous conductor to put a cross-section on, and the layer contributes **zero**
rather than an estimate. (On In1 and B.Cu the same test finds one island containing
both terminals — which is why those layers are measured.)

Profile shape (from `05_profiles.json`), which is what makes the neck auditable
rather than a bare number:

| rail | layer | band | stations | min | p5 | median | p95 |
|---|---|---|---|---|---|---|---|
| BATP | In1.Cu | 7.740 | 132 | **4.225** | 7.806 | 28.17 | 84.50 |
| BATN | B.Cu | 22.800 | 26 | **35.407** | 35.442 | 45.98 | 70.40 |
| PHASE_A | In2.Cu | 12.394 | 32 | **12.503** | 12.646 | 14.81 | 15.51 |

So BATP's inner plane is a broad pour (**median 28.17 mm**) with **one pinch of
4.225 mm at (46.187, 91.20)** — a single, findable, fixable place. That is a
different finding from "the plane is 8.21 mm wide", and it is the one the design has
to answer.

### Power-first placement (687 footprints, 0 tracks, 0 zones — no conductor at all)

| rail | layer | gap | pass | need | own |
|---|---|---|---|---|---|
| BATP | F.Cu | 1.960 | **1.460** | 13.981 | no conductor |
| BATP | In1.Cu | 23.156 | 22.656 | 37.28 | no conductor (5.70 mm² of THT pad) |
| BATN | B.Cu | 21.770 | 21.270 | 13.981 | no conductor |
| PHASE_A | F.Cu | 9.923 | **9.423** | 13.981 | no conductor |
| PHASE_A | In2.Cu | 28.078 | 27.578 | 37.28 | no conductor |

This is the board the old 7.400 mm was measured on. **It carries no copper**, so
7.400 mm describes empty space between pads, not a power path. The corrected
clearance figure for the same rail is **9.423 mm** (see §5 C/D for why it differs).

### Compacted 370.12 cm²

| rail | layer | gap | pass | own width | at |
|---|---|---|---|---|---|
| BATP | F.Cu | 1.280 | 0.780 | FRAGMENTED | — |
| BATP | In1.Cu | 10.240 | 9.740 | **7.075 mm** | 15.80, 40.29 |
| BATN | B.Cu | 8.750 | 8.250 | **7.785 mm** | 35.25, 35.45 |
| PHASE_A | F.Cu | 1.240 | 0.740 | FRAGMENTED | — |
| PHASE_A | In2.Cu | 15.956 | 15.456 | **12.510 mm** | 23.70, 16.15 |

---

## 5. Sanity checks — and what they do not cover

Run `02_calib.py` → `02_calib.json`, `04_verdict.py` → `04_verdict.json`.

**A. Analytic channels (exact answer known).** Two parallel bars, designed gap *W*:

| W | h = 0.10 | h = 0.05 | h = 0.02 |
|---|---|---|---|
| 1.400 | 1.200 (−0.200) | 1.300 (−0.100) | 1.360 (−0.040) |
| 6.991 | 6.800 (−0.191) | 6.900 (−0.091) | 6.960 (−0.031) |
| 7.400 | 7.200 (−0.200) | 7.300 (−0.100) | **7.400 (−0.000)** |
| 37.280 | 37.200 (−0.080) | 37.200 (−0.080) | **37.280 (−0.000)** |

Worst error at the pitch actually used, **0.040 mm** (0.6 % of 6.991). The error is
one-sided (the raster never over-states a gap) and scales with pitch.

**B. Real board, documented geometry.** 44 adjacent foreign-net pad pairs on the
board of record measure **exactly 0.2000 mm** in shapely — the 371-pad-gap figure
independently reproduced — and the raster reproduces a 0.2000 mm gap as
**0.2000 mm at both h = 0.02 and h = 0.005** (error +0.0000).

**C. Legacy reproduction — the decisive check.** Running *this* engine in legacy
mode (pads only, bounding boxes, F.Cu, first-pad seeds, whole-board domain,
h = 0.05, and the old `near()` scan verbatim) reproduces the published numbers to
the last digit:

| board | published | reproduced | delta |
|---|---|---|---|
| powerfirst, phase A | 7.400 | **7.400** (t\* = 3.950) | −0.000 |
| original, phase A | 7.674 | **7.674** (t\* = 4.087) | +0.000 |

So the old number is *understood*, not merely contradicted: the change from 7.400
is attributable to named assumptions, below. (Reproducing it required the old
`int()` cell truncation; `round()` moves the seed one cell and shifts the answer by
one raster step, which is itself worth knowing about that instrument.)

**D. What made the old number.** Same pair, one assumption at a time:

| board | pad bounding boxes | true pad shapes | true shapes + all copper |
|---|---|---|---|
| powerfirst, h = 0.02 | 6.860 | 6.860 | 6.860 |
| original, h = 0.02 | 6.860 | **5.660** | **5.660** |

Two attribution facts fall out. (i) Bounding-box pads **inflate the original's
phase corridor by 1.20 mm** — round and rotated pads were rasterised as squares.
(ii) On the original board, near this pair, tracks and zones change nothing: the
corridor there is bounded by pads. The copper omission is *not* what broke this
particular pair — it breaks every pair whose corridor crosses a pour or a trace, and
it is what makes the power-first measurement meaningless on a board with no copper.

**E. Chord check (the own-copper number).** A 10.000 mm bar at 0°, 17°, 45°, 73°,
90° measures **10.0000 mm** every time, and a real 0.200 mm track measures
**0.2000 mm** — the chord machinery is exact, so the own-copper widths are geometry,
not smoothing. `05_own_profile.py` re-derives every neck independently and agrees to
within 0.5 % (compact BATN 7.82 vs 7.785 mm).

**F. The check that FAILED, and is therefore unused.** An independent min-cut
estimator (max-flow on the copper graph, `scipy.sparse.csgraph.maximum_flow`) was
built to corroborate the neck. It returned **flow = 0** on a graph whose two
terminal sets are provably in one component — a *plausible-looking zero*, exactly
the failure class this programme keeps finding. Two fixes were attempted; neither
made it trustworthy, so **it is excluded and no number depends on it**. The neck is
instead reported with a bound that does not need it: the perpendicular chord at any
station *is* a candidate cut, so **min-cut ≤ 4.225 mm** for BATP's In1 plane — the
true cross-section is at most what is reported, never more.

**What these checks do NOT cover.** They validate the distance/raster/maximim
machinery, the shape reading, and the reproducibility of the old outputs. They do
**not** validate the *definition* that "a plane's capability is its narrowest
transverse chord" — that is a modelling choice, stated in §2.5, and a 2-D current
solve would be the better instrument for a plane. They also say nothing about via
ampacity, which no instrument in this programme has counted (see §6).

---

## 6. The true deficit against 60 A

Cross-section = Σ over the layers the rail **actually conducts on** of
(own width × that layer's thickness). Basis **1.9574 mm²** (60 A, ΔT 20 K, 4 oz).

| board | rail | layer | own width | × thickness | **total** | vs 1.9574 | margin |
|---|---|---|---|---|---|---|---|
| **original** | BATP | In1.Cu (F.Cu fragmented) | 4.225 | 0.0525 | **0.222 mm²** | **−1.735 mm²** | **−88.7 % FAIL** |
| **original** | BATN | B.Cu | 35.407 | 0.14 | **4.957 mm²** | +3.000 mm² | **+153.2 % PASS** |
| **original** | PHASE_A | In2.Cu (F.Cu fragmented) | 12.503 | 0.0525 | **0.656 mm²** | **−1.301 mm²** | **−66.5 % FAIL** |
| compact | BATP | In1.Cu | 7.075 | 0.0525 | 0.371 mm² | −1.586 mm² | −81.0 % FAIL |
| compact | BATN | B.Cu | 7.785 | 0.14 | 1.090 mm² | −0.867 mm² | −44.3 % FAIL |
| compact | PHASE_A | In2.Cu | 12.510 | 0.0525 | 0.657 mm² | −1.301 mm² | −66.4 % FAIL |
| powerfirst | all three | — | no conductor | — | 0.000 mm² | not testable | no copper exists |

**BATP's deficit is 1.735 mm², not 0.431 mm² — 4.03× the published figure.** On the
verifier's more generous basis (crediting the old F.Cu 1.4 mm as 0.196 mm²) it is
**1.761 mm²**; the two agree to 0.026 mm² from opposite directions, which is a
strong independent confirmation of their correction. In width: the In1 plane would
have to carry **37.28 mm** alone, or **33.55 mm** with that credit, and it is
**4.225 mm** at its pinch — **8.8× / 7.9× short**.

**BATN is the only rail that closes**, and it is also the only corridor with **0**
stations below requirement. Two caveats stand beside it, neither measured here: the
B.Cu plane gets its current through **vias whose ampacity nobody has counted**
(`AGENT_BOARD.md`: ~3.0 A/barrel, 21 vias per transition at 60 A), and the 60 A is
per phase, so the 360 A board total is not what this table means.

---

## 7. Was 'PASS' ever justified for BATP?

**No.** Three independent reasons, each sufficient:

1. **It was measured on a board with no copper.** The 7.400 mm comes from
   `esc_rev_b_powerfirst.kicad_pcb`, which has **0 traces and 0 zones**. On that
   board the instrument's obstacle set — foreign pads — *is* all the copper there
   is, so its output describes free space between parts. BATP's actual conductors
   are F.Cu and In1, and neither was measured.
2. **It contradicted its own output.** The same run printed `BATP 1.400 mm` and
   `BATN no path`, then a summary `narrowest 1.400 → FAIL (−80 %)`. Publishing
   7.400 as "the narrowest" is the minimum of a **subset** presented as the minimum
   of the set; `REPORT.md:372-376` argues the subset case in prose. A number is not
   a verdict: the same instrument said FAIL four lines earlier.
3. **The 7.400 that survived is a seed artefact.** Reproduced exactly (§5 C), it
   comes from a point seed plus a 2 mm `near()` search that lifts the seed off the
   terminal's own clearance. With region seeding the same pair, pads only, reads
   **6.860 mm** — and with real pad shapes **5.660 mm** — on the board of record.

**Corrected verdict per rail, board of record:** BATP **FAIL** (−88.7 %, and its
F.Cu does not even connect its terminals); BATN **PASS** on cross-section
(+153 %) with 0 clearance bottlenecks; PHASE_A **FAIL** (−66.5 %). On the compacted
board all three **FAIL**; on the placement board there is no conductor, so the
corridor question is a routing question only, and the measured clearance says a
6.991 mm phase conductor **fits** (9.423 mm) while the BATP feed does not
(1.460 mm).

---

## 8. Artefacts

| file | what it is |
|---|---|
| `corridor_lib.py` | the corrected geometry: copper per layer, raster, region-seeded maximin, corridor path, chords |
| `00_probe_api.py/.log` | API surface actually used (pad layer argument, filled-polys accessors, inventories) |
| `01_copper_census.py/.json/.log` | per-net per-layer census: pads / tracks / vias / zone fill, unfilled-zone assertion |
| `02_calib.py/.json/.log` | checks A–D: analytic channels, documented 0.2000 mm gaps, legacy reproduction, assumption decomposition |
| `03_corridor.py/.json/.log` | the measurement: gap, passable, per-layer own width, bottleneck count and coordinates |
| `04_verdict.py/.json/.log` | chord check, min-cut attempt (failed, excluded), neck class, cross-section verdicts |
| `05_own_profile.py/.json/.log` | every chord station per case, so each neck is auditable |

**Reproduce:**

```
cd evidence/esc-corridor-instrument
& 'C:/Program Files/KiCad/9.0/bin/python.exe' -u 01_copper_census.py
& 'C:/Program Files/KiCad/9.0/bin/python.exe' -u 02_calib.py
& 'C:/Program Files/KiCad/9.0/bin/python.exe' -u 03_corridor.py
& 'C:/Program Files/KiCad/9.0/bin/python.exe' -u 04_verdict.py
& 'C:/Program Files/KiCad/9.0/bin/python.exe' -u 05_own_profile.py
```

**Not done, and why.** No via-ampacity measurement (separate instrument, and the
settled 3.0 A/barrel is an assumption). No 2-D current solve for the planes — the
chord bound in §5 F is the conservative statement this instrument can make. No DRC
and no `kicad-cli` run: nothing here creates or edits a board, so the
`(version 1)` `.kicad_dru` trap is out of scope, and the 1,542-unconnected figure is
cited, not re-derived. Nothing was written outside this directory, no repo was
touched, and no spend was incurred.