# ESC compaction wave — adversarial verification

**Unit:** `esc-compaction-verify` · **Wave under review:** `esc-area-floor`, `esc-placement`,
`esc-routability` · **Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), `kicad-cli` for DRC,
the bundled `python.exe` for pcbnew, CPython 3.12 for the arithmetic.
**Nothing was written into any repo.** Every board here is a **copy**, made in this directory:
`compact_COPY.kicad_pcb` (sha256 `A26EEADAC0D085865B7FD1C912520521C2085EB49DC20A6E2CB795184E99A007`)
and `orig_COPY.kicad_pcb` (sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`,
which reproduces the hash all three reports quote — the chain check passes).

> **Artefact gap, stated first:** the placement report publishes the sha256 of the *original* board
> but **not of the compacted board it delivers**. The hash above is the first one on the record for
> the artefact under test.

---

## THE VERDICT

| question | answer |
|---|---|
| **Smallest honest area** | **370 cm² for today's BOM** (delivered = 370.12, at the floor). **316 cm²** needs the M5 lugs replaced. **255 cm²** if the phase pours also use B.Cu — which the single-sided rule permits, because it forbids *components*, not copper. |
| **Compaction claim verified** | **YES** on every mechanical claim, with two arithmetic slips in the text. |
| **B.Cu count** | **0** — 687/687 on F.Cu, 0 flipped. Constraint met. |
| **Power path** | **FAIL.** The 60 A phase corridor is 5.0× narrower than the board it replaced. |
| **Routable at 4 oz** | **NO**, and *worse* than the original: 934 vs 523 under the 0.250 mm rule set. |
| **VERDICT** | **UNSAFE.** A layout that looks compact and cannot carry its current. |

---

## 1. AREA_FLOOR — the 316 cm² figure is a conditional, not a floor

Everything below is `02_arith.py` / `02_arith.json`. The floor report's own numbers reproduce
**exactly**, so the disagreement is not arithmetic, it is two unstated inputs.

```
(a) copper block  3 x 13.981 + 2 x 0.60 = 43.143 mm  x  46.06 mm  = 1987.2 mm2 = 119.23 cm2 / 6 cells
    (reproduces the report's 19.87 cm2/cell to the digit)
(b) creepage 6.19   (c) thermal 0.00   (d) 22.94 x 6 = 137.64   supervisor 37.66
    raw 300.72 cm2  ->  +5 %  =  315.76 cm2                       (reproduces 316)
```

Two inputs move it, and neither is swept in the report's sensitivity table (which sweeps ΔT only):

**(i) the 60 A phase width is assumed to be carried on ONE 4 oz layer.** 13.981 mm is right for one
face. Each conductor's required cross-section is 1.9574 mm² at ΔT = 20 K, so **two 4 oz faces give
6.991 mm each** and three phases fit in `3 x 6.991 + 2 x 0.60 = 22.173 mm`, not 43.143. The block
becomes 1021.3 mm²/cell = 61.28 cm², i.e. **−57.95 cm²** → floor **254.91 cm²**. Nothing forbids
this: the owner's rule bans components on the back, not copper. Cost, computed here for the first
time: a plated barrel is 25 µm even on 4 oz laminate, so a 0.40 mm drill has 0.03142 mm² of copper
= **3.0 A at ΔT 20 K** → **21 vias per 60 A transition**, ~2 transitions per phase.

**(ii) the 400 mm² terminal is ASSUMED; the board's own lugs are 1267 mm²/cell.** Putting the real
lugs back: component term 31.61 cm²/cell → raw 352.74 → **370.38 cm²**.

**That is the triangulation that matters.** 370.38 (floor report's components, real lugs, its own
5 % margin) against **370.12 delivered** — **0.07 % apart**, two methods. So the compaction did not
leave 13.9 cm² on the table; **it hit the floor of the BOM it was given.** The report's claim that
the honest floor is 356.2 cm² is a different number because its 73.6 % density is the density its
own cell achieved — self-consistent, but not independent.

**Answer to the owner's question:** 370 cm² with today's connectors; 316 needs the lug change the
placement report itself prices at −9 %; 255 is the real ceiling of the exercise and is **not**
reachable at 316.

---

## 2. COMPACTION claim — verified, with two slips

Re-measured on `compact_COPY.kicad_pcb` (`01_census.py`, `03_measure.py`):

| claim | published | measured here | |
|---|---|---|---|
| outline | 153.10 × 241.75 | **153.100 × 241.750** (Edge_Cuts bbox, origin 0,0) | ✓ |
| area | 370.12 cm² | **370.119** = 153.10 × 241.75 | ✓ |
| fill | 70.84 % | **70.84 %** = 262.189 / 370.119 | ✓ |
| footprints / B.Cu | 687 / 0 | **687 / 0** | ✓ |
| six cells | 75.30 × 73.26 | **75.30 × 73.26, all six, area 5516.5 mm² each** | ✓ |
| gaps / margins | 1.5 / 0.5 | **1.5 in x, 1.5 in y, 1.5 to CTRL, 0.5 all round — closes exactly** | ✓ |
| min pair gap | +0.60, 0 pairs < 0.5 | **+0.5999 (pair C706–C701), 0 pairs < 0.5** | ✓ |
| area reduction | −24.73 % | **−121.61 cm² / 491.73 = −24.73 %** | ✓ |

**Slip 1 — the stated outline formula does not produce the published height.**
`241.75 = 3 × 73.26 + 2 × 1.5 + 1.5 + 18.0 + 2 × 0.5` evaluates to **243.28**. The board is right
and the formula is wrong: the control strip is **16.47 mm** (measured, and as the same report says
in §4 and §5.5), and `… + 16.47 + …` = 241.75 exactly. `18.0` is a leftover from the abandoned
`sizes.json` (cell_h 71.02 / ctrl_h 22.76).

**Slip 2 — the reconciliation does not close in the artefact the report cites for it.**
`05_floor.log` §6 prints its five rows and **TOTAL 412.96 cm²** against a board of **492.42** — a
missing **79.47 cm²**. The missing term is the in-cell slack (57.09 − 43.85) × 6 = 79.44, which
`08_verify.py` **does** compute (79.462) and which brings the total to 492.418. So the report's
§5.6 table is right and the cited log is wrong; §5.6 should cite `08_verify.log`, not `05_floor.log`.
Related: **`04_calc.py` exits non-zero** — `04_calc.log` ends in a `TypeError` at line 224, so the
§5 sum never printed there.

---

## 3. B.Cu count = 0 — the absolute constraint holds

```
layer_census {"F.Cu": 687} · on_B_Cu 0 · flipped 0
pads touching B.Cu 230 (through-hole) · zones on B.Cu 6
```

No component anywhere on the back, on either board. **But note for §4:** the back is *not* bare —
6 B.Cu zones and 230 through-hole pads reach it, which is why back copper remains available as a
current path even under a single-sided *assembly* rule.

---

## 4. POWER_PATH — the finding that decides this wave

`esc-routability` §4.4 states the two numbers compaction **must preserve**: *"the phase corridor,
≥ 7.5 mm, and the battery-tap corridor, ≥ 1.76 mm, or the fallback to a multi-layer pour stops being
available."* Nobody re-measured them on the compacted board. I did, with the same method, parameters
and obstacle set (`03_measure.py` imports the routability unit's own `escapes.py`, 0.2 mm grid,
0.25 mm clearance, ±6 mm window).

**Chain check first:** run on the *original*, my code reproduces their published numbers to three
decimals — `/M1_PHASE_A` **7.51**, `/M1_PHASE_B` **7.51**, `/M1_PHASE_C` **7.50**, `/M1_BATP`
**1.763**, `/M1_BATN` **0.394**, cell 86.27 × 80.03, min gap −2.5172. The method is therefore
comparable, and the comparison below is not a method artefact.

| net (usable width at 0.25 mm clearance) | original | **compacted** | change |
|---|---|---|---|
| `/M1_PHASE_A` | 7.51 mm | **1.50 mm** | **−80 %** |
| `/M1_PHASE_B` | 7.51 | **1.50** | −80 % |
| `/M1_PHASE_C` | 7.50 | **1.90** | −75 % |
| `/M2…M6_PHASE_A` | 7.51 | **1.50 each** | −80 % |
| `/M1_BATP` | 1.763 | **0.70** | −60 % |
| `/M1_BATN` | 0.394 | **0.30** | −24 % |

**The arithmetic that makes this a failure, not a preference.** 60 A needs 1.9574 mm² of copper at
ΔT = 20 K. Two 4 oz faces supply that at **6.991 mm per face**; one face at 13.981 mm. The compacted
phase corridor is **1.50 mm** — **4.7× short of the two-face requirement and 9.3× short of one
face.** The original's 7.51 mm cleared the two-face bar by 7 %. So the compaction did not shave
margin off the power path; **it removed the last configuration in which 60 A could be carried.**

`esc-placement` §2(a) concluded the opposite — *"copper width does not set the cell size at all"* —
and it reached that from the FET land width (11.56 mm) rather than from a measured corridor. §7.3
concedes the packing is *"density-driven, not connectivity-driven"* and that a designer *"must
re-order"* the parts. Re-ordering is the fix, but the report does not flag that the delivered board
**cannot be built as it stands**, and the 60 A nets are exactly the ones the re-ordering is for.

**And the path got longer, not shorter.** §4 claims the cell has *"the current path shorter and
straighter than before"* (`06_path_length.py`, same pad pairs on both boards):

| run (channel 1) | original | compacted |
|---|---|---|
| **J1101 battery lug → R1123 bus shunt (60 A feed)** | **17.144 mm** | **40.847 mm (+138 %)** |
| J1101 → Q1101 high-side FET | 28.768 | 16.653 |
| J1102 phase lug → Q1101 | 9.787 | 10.316 |
| J1102 phase lug → Q1102 | 26.061 | 26.312 |

At the width 60 A forces, that feed goes **0.1507 → 0.3589 mΩ, 0.54 → 1.29 W per channel** —
**+4.5 W** on a board whose whole board-side loss is 70 W. The phase runs are unchanged to ±0.3 mm.

**One honest counterweight, measured:** the back face is still free copper (6 B.Cu zones, 0
components), so a via-fed B.Cu phase pour remains available in principle. I could not certify it:
only **one** power pad per phase net reaches B.Cu, so it needs the 21-vias-per-transition array
computed in §1 — a cost **no unit in this wave has counted.**

---

## 5. ROUTABLE at 4 oz — no, and measurably worse

`kicad-cli pcb drc --severity-all` run here on **both boards, both rule sets**, so every number in
this table is from one instrument. Project rules are each board's own `.kicad_pro`; the 4 oz set is
the 9-rule `esc_rev_b.kicad_dru` from `esc-routability/orig-025/`.

| | original | **compacted** | |
|---|---|---|---|
| **project rules** | **16** | **447** | both reproduce the published figures **exactly** (16 / 447) |
| **4 oz / 0.250 mm** | **523** | **934** | **+411 (+79 %)** |
| violations per cm² @0.250 | 1.0621 | **2.524** | **2.38× worse** |
| unconnected (kicad-cli / pcbnew) | 499 / 1542 | 499 / **1620** | +78 |

**The placement report's central defence survives, and it deserves to be said plainly:** I
classified every item by the object pair involved (`04_drc_class.py`), and **0 of the 447 is
pad-to-pad.** All 447 are carried copper that no longer agrees with the moved parts. That claim is
**confirmed**.

**But the two consequences it draws are not.** First, the 447 are not a soft finding: they include
**51 `shorting_items`**, 81 `solder_mask_bridge`, 199 `via_dangling`, 26 `track_dangling`, 13
`copper_edge_clearance` and 6 `isolated_copper`. The original board's 16 are **all 16
`via_dangling`** — so every short, every mask bridge and every copper-to-edge item is new. Second,
under the rule set the board must actually be built to, the compacted board carries **934**, not
523, and **2.38× the violations per cm²** — which is the exact metric `esc-routability` §2.4 wrote
for scoring a compacted placement ("*a compacted placement that keeps 523 violations over 400 cm²
has improved density by 19 %; one that keeps 523 over 492 cm² has not moved*"). On that instrument
this placement **regressed**.

The `Pad+Pad` population is **371 on both boards, item for item** — the fine-pitch blocker is
invariant, exactly as the routability unit said. Everything else is not: **152 non-pad items before,
563 after.**

| class pair @0.250 | original | compacted |
|---|---|---|
| `Pad+Pad` | 371 | **371** (invariant) |
| `Pad+Track` | 22 | **131** |
| `Pad+Via` | 0 | **58** |
| `Via` (dangling) | 60 | **243** |
| `Track` / `Track+Track` / `Via+Via` | 4 / 24 / 0 | **30 / 10 / 18** |
| `Via+Zone`, `Track+Track`, `solo Zone`, edge | 0 | **12 / 10 / 6 / 13** |
| **total** | **523** | **934** |

**And no route exists.** No unit has drawn 4 oz copper on the compacted board; the routability
unit's freerouting attempt crashed and its own certificate is **40 of 81 nets routable** per phase
block, with 202 pads irreducibly unescapable. So "routable" is not merely unproven here — it is
contradicted, on the same instrument, by 2.4×.

---

## 6. UNSOURCED currents and the missing ambient

| figure | placement | routability | area-floor |
|---|---|---|---|
| **60 A per phase** | "ASSUMED, not derivable from the file" (§2a, §7.4) | "taken as given" (§4.1, O5 hedged) | **sourced: `REV_B_ARCHITECTURE.md:18`** |
| dissipation | ≈108 W, no ambient stated | — | 247.5 W, ambient 45 °C **ASSUMED** |

60 A **is** in the repo, so this is not a fabrication — but two of three units treat the single
number the entire area floor turns on as an assumption because they read the board instead of the
repo. `esc-area-floor` also surfaces the contradiction both others miss: the repo sizes the
*aircraft* for a **50 s burst** (`FA4119_PROPULSION_DECISION.md:44`) and the *board* for continuous.

**The thermal numbers disagree by 2.3× and nobody reconciled them**: 108 W vs 247.5 W for the same
six cells. The gap is the duty factor — placement uses `I²R·D` with D = 1/3 (18 W/channel),
area-floor counts six devices at D ≈ 1/2 plus 27 W of shunts and 42.7 W of copper I²R. Placement's
figure also **omits the shunts and the copper loss entirely**. Its area result does not depend on the
number, so this is not a floor error — but it is a thermal claim in a report that states no ambient,
and it is 2.3× optimistic.

---

## 7. Creepage — a number without a standard

`esc-placement` §2(b) derives its rule from **the board's own pour clearance** (0.5 mm, 96/96 zones)
and states no external standard. `esc-area-floor` §3.2 establishes the standard properly:
**IPC-2221B Table 6-1 B2 external uncoated = 0.60 mm** at 51–100 V, cross-checked against IEC 60664-1
(creepage 0.60 mm, PD2, IIIa). The compacted board's worst pair is **0.5999 mm** — exactly at the
requirement, **zero margin**, and its legalisation floor (0.5 mm) is 17 % *below* it. Not a new
defect (the original is 0.2000 mm, 3× under), but a report that says "achieves 0.60 mm, cleaner than
today" should say "achieves exactly the uncoated creepage limit, from a 0.5 mm rule that is not the
limit".

---

## 8. Hunt list, answered

| # | item | finding |
|---|---|---|
| 1 | area claim without dims + arithmetic | dims and area **shown and correct**; the mode/height **formula is wrong by 1.53 mm** and the cited reconciliation log closes at 412.96 not 492.42 |
| 2 | copper squeezed below the current | **YES — found.** Phase corridor 7.51 → **1.50 mm** vs 6.991 required; BATP 1.763 → 0.70. No unit measured it |
| 3 | footprint on B.Cu | **none. 0 / 687.** Absolute constraint holds |
| 4 | "routable" without DRC | **no routable claim is made**, and DRC run here says **934** at 0.250 (2.38×/cm² worse), unconnected 1620 pcbnew |
| 5 | creepage/thermal without a standard | creepage: placement gives **no standard** (0.5 mm from the board's own zones; the standard is 0.60). thermal: **no ambient stated**, and 2.3× below area-floor |
| 6 | current from nowhere | 60 A is **sourced** by area-floor (`REV_B_ARCHITECTURE.md:18`) but **ASSUMED** by the other two; the 50 s burst in `FA4119:44` is unreconciled |
| 7 | contradiction without a BOARD CORRECTION | **one:** `esc-routability` §0 states *"`evidence/esc-placement/` does not exist"*. It does, and it was measured in this wave. Its conclusion survives (the 202 irreducible pads are footprint-bound) but the premise is stale and the report needs a correction line |

---

## 9. Answer to the two direct questions

**What is the smallest board area this ESC can honestly be?**
**370 cm² for the BOM it has** — and the delivered board is *exactly* that: my independent
floor-with-real-lugs gives 370.38 against 370.12 delivered (0.07 %). **316 cm²** is the floor only
after the M5 lugs (1267 mm²/cell, 76.02 cm² total) are replaced with something sized for 60 A.
**255 cm²** is the real ceiling, and it requires two things the wave did not do: put the phase
pours on **both** 4 oz faces (permitted — the rule bans components on the back, not copper), and
pay the via array that makes that legal (~21 vias per 60 A transition). No single number is "the"
floor without naming the BOM; 316 is not it.

**Is the proposed placement routable at 4 oz?**
**No.** Two independent reasons, either sufficient. **(a)** The 60 A phase corridor is **1.50 mm**
where 60 A needs **6.991 mm** across two faces — the compaction removed the only configuration in
which the current could be carried, while the report argued the opposite from the FET land width
instead of a measurement. **(b)** At the 0.250 mm rule set the board carries **934 violations
(2.38× per cm²) and 51 shorts**, up from 523 and 0, with **499 unconnected** by `kicad-cli` and
**1,620** by `pcbnew`; and no 4 oz route has ever been drawn on it — the one attempt crashed, and
the block certificate is 40 of 81 nets.

---

## 10. What is credible here

- The **geometry** of the compaction: exact, reproducible, −24.73 %, single-sided, six identical
  cells, and it lands on the floor of its own BOM. That is real work and it survives.
- The **"0 of 447 is pad-to-pad"** defence: confirmed by independent classification.
- `esc-area-floor`'s **standards work** (IPC-2221B B2, IEC 60664-1, the 8-fab 4 oz survey) — and its
  honesty about the 50 s-burst conflict and the six-vs-four-motor population.
- `esc-routability`'s **202 irreducible pads** and its **40/81 certificate**: both are bounds no
  placement can move, and both stand.

**What does not survive:** `esc-placement`'s §2(a) conclusion that copper width is not a constraint,
its §4 claim that the current path is shorter, and any reading of this wave as an improvement in
routability.

---

## 11. Reproduce

```powershell
$ev="E:\engineering-portfolio-audit\evidence\esc-compaction-verify"
$kpy="C:\Program Files\KiCad\9.0\bin\python.exe"
$cli="C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
& $kpy "$ev\01_census.py"  "$ev\compact_COPY.kicad_pcb" "$ev\01_census.json"
python    "$ev\02_arith.py"                                        # -> 02_arith.json
& $kpy "$ev\03_measure.py" "$ev\orig_COPY.kicad_pcb"    "$ev\03_measure_orig.json"   # chain check
& $kpy "$ev\03_measure.py" "$ev\compact_COPY.kicad_pcb" "$ev\03_measure.json"        # the collapse
python    "$ev\04_drc_class.py" "$ev\drc_proj\drc.json" "$ev\drc_025\drc.json"
& $kpy "$ev\05_back_copper.py" "$ev\compact_COPY.kicad_pcb" "$ev\05_back_copper.json"
& $kpy "$ev\06_path_length.py" "$ev\orig_COPY.kicad_pcb" "$ev\compact_COPY.kicad_pcb" "$ev\06_path_length.json"
& $cli pcb drc "$ev\drc_proj\compact_proj.kicad_pcb" -o "$ev\drc_proj\drc.json" --format json --severity-all --units mm
& $cli pcb drc "$ev\drc_025\compact_025.kicad_pcb"   -o "$ev\drc_025\drc.json"  --format json --severity-all --units mm
& $cli pcb drc "$ev\drc_orig\orig_proj.kicad_pcb"    -o "$ev\drc_orig\drc_proj.json" --format json --severity-all --units mm
& $cli pcb drc "$ev\drc_orig\orig_025.kicad_pcb"     -o "$ev\drc_orig\drc_025.json"  --format json --severity-all --units mm
python    "$ev\04_drc_class.py" "$ev\drc_orig\drc_proj.json" "$ev\drc_orig\drc_025.json"
```

| file | what |
|---|---|
| `compact_COPY.kicad_pcb` | the artefact under test (sha256 `A26EEADA…A007`) |
| `orig_COPY.kicad_pcb` | the baseline (sha256 `99257057…9DDD` — reproduces the published hash) |
| `01_census.json` | census, outline, fill, via/zone histograms, both unconnected instruments |
| `02_arith.json` | every closed-form number in §1: widths, the two-face floor, via ampacity, the outline formula |
| `03_measure.json` / `_orig.json` | cell geometry, min pair gap, **the corridors, both boards** |
| `04_drc_class.json` | DRC by object pair, both rule sets |
| `05_back_copper.json` | B.Cu pad census per phase net |
| `06_path_length.json` | current-path lengths before/after |
| `drc_proj/`, `drc_025/` | the compact board's two DRC runs and their rule files |
| `drc_orig/` | the original's two DRC runs — **16 / 523 / 499 reproduce my own instrument** |
| `04_drc_class_orig.log` | the original's item-pair classification, for the like-for-like table in §5 |

**Trap for the next unit:** `PCB_VIA.GetWidth()` with no layer argument trips a wx assert in 9.0.7
and **hangs the process** — pass the layer (`GetWidth(pcbnew.F_Cu)`). It cost this run one killed job.

---

## 12. Correction history

- **Nothing withdrawn.** First report of this unit.
- One method caveat, stated because it affects one row: my re-run of the maximin corridor reproduces
  the routability unit's figures for 5 of 6 channel-1 nets exactly, but `/M1_BATP_IN` reads
  **7.707 mm** here against their **12.149 mm**. Both are above any requirement, so the verdict does
  not use that net. The five that reproduce are the five the verdict turns on.