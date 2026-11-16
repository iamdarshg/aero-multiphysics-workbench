# The pre-fab master checklist, v3 — four rows, thirteen columns, nothing inferred

**Owner:** fab-checklist specialist, wave 7. **Date:** 2026-11-16. **Host:** KiCad 9.0.7
(`C:/Program Files/KiCad/9.0/bin/kicad-cli.exe`; bundled `python.exe` + `pcbnew` 9.0.7 for board
reads; CPython 3.12 for arithmetic).
**Supersedes:** `evidence/fab-checklist-v2/REPORT.md` (v2, 2026-11-16), which superseded
`evidence/fab-checklist/REPORT.md` (v1).

**Hard rule observed:** nothing was written into a repo, nothing committed or pushed, no `audit/*`
branch touched. Every board analysed here is a **byte copy** in `boards/`; every artefact is under
`evidence/fab-checklist-v3/`. `$0` spent. The four copies reproduce the hashes the programme already
records (§2.0), so no measurement here is about a drifted file.

**Constraints in force:** NO HDI on any board; ONLY the ESC is 4 oz; $60 coupon/prototype cap; ESC
single-sided and as compact as possible (owner, 2026-11-15).

---

## 0. The answer, before the evidence

| board | orderable today | the number that decides it |
|---|---|---|
| **drone-arm main rev_b** | **NO** | **15 non-through vias** — 11 blind + 4 buried, 14 at 0.100 mm; **0 of 15** survive a KiCad DRC conversion, so the zero needs a U10 fan-out re-escape, not a via edit |
| **ESC rev_b** | **NO** | **1,542 unconnected** (pcbnew; the 499 everyone quotes is `kicad-cli`'s cap) — and when it is routed, the rail that must carry it measures **23.1 A of 59.05 A**, 2.6× short |
| **Code-SDR V2** | **YES**, bare board | **0 errors / 222 warnings / 0 unconnected** and a 1,215-hole frame-free package stamped `2.1`; assembly is a separate PO, blocked by 373/373 missing MPNs and a **1.22 mm** fiducial pour gap against a **1.25 mm** requirement |
| **drone-mech airframe** | **NO** (mechanical) | **6 genuine pairs / 1,250.769445 mm³ in the design of record**; the measured zero is a copy state that costs a **+38.485 mm** elevon station change no revision carries |

Three of four are refused, and none of the refusals is a labelling argument.

**What "orderable" means here** — unchanged from v1 and v2, because the word does the most work:

> **ORDERABLE = a bare-board fabrication order placed today, from artefacts that exist today,
> produces the board the design describes, with nothing to fix afterwards.**

A board that etches but cannot function is **not** orderable, because the rework is the thing this
programme exists to avoid (`AGENT_BOARD.md:5-25`). Assembly data is scored separately (§5, §7).

**Counting rule.** 13 verdict-bearing columns per board; column 14 is the verdict. Every cell ends
in exactly one of `PASS` / `FAIL` / `WAIVED`, **and every verdict is produced by a predicate over a
measurement file** (`derive.py`), never typed. `check_report.py` re-derives all 52 from the raw
measurements and fails if the table, the tallies or the prose disagree with them.

---

## 1. THE CHECKLIST

Rendered by `derive.py` from `out/cells.json`; each cell is **value** — **verdict**. Sources are
`M-*` (pcbnew on a copy), `D-*` (`kicad-cli pcb drc`), `G-DA`/`X-CS` (Excellon census), `SCAN`
(artefact scan of the repo). §2 gives the method behind every tag.

| board | 1. layers | 2. copper weight | 3. min track | 4. min space | 5. min drill | 6. min annular ring | 7. non-through vias BY SPAN | 8. unconnected (tool, cap?) | 9. DRC (severity, rules loaded?) | 10. gerber package state | 11. revision stamp | 12. panel outline and area | 13. surface finish | 14. orderable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** <br>*(best artefact: fanout3 = fanout7, sha `372C1D52…FA9077`)* | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) — **PASS** | 0.035 mm = 1 oz on all four copper layers (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) — **PASS** | 0.200 mm, 500 segments at exactly that width (of 2306) — **PASS** | 0.1250 mm minimum, identical in all 3 repeat runs; 507-510 pairs at the 0.30 mm probe floor (that count flickers: zone fill is threaded) — **PASS** | via 0.100 mm (min of 336 vias) / PTH pad 0.200 mm — **FAIL** | via 0.1000 x21, 0.1500 x28, 0.1750 x281, 0.2000 x6 / PTH min 0.150 mm at U41.17 — **WAIVED** | 15 = 11 blind + 4 buried of 336 vias -- 0.1 mm blind (F.Cu->In1.Cu x5, F.Cu->In2.Cu x2, In1.Cu->B.Cu x1, In2.Cu->B.Cu x2); 0.1 mm buried (In1.Cu->In2.Cu x4); 0.3 mm blind (In2.Cu->B.Cu x1) — **FAIL** | 0 pcbnew GetUnconnectedCount(False); kicad-cli 0 (below the cap, and it agrees) — **PASS** | 7 error / 0 warning under the board's own project rules; 22 error under the span gate (14 microvia + 1 drill + 7 via_diameter) — **FAIL** | package7: 63/63 assertions, 11 gerbers + job + 7 Excellon, 360 drills + 4 slots = 364 hits, 5 blind/buried files carrying 15 holes, job rev 'B', SENDABLE = NO — **FAIL** | board title block '' ; package7 carries 'B' on 19 carriers because title_block_rev_B.patch was applied to a COPY, not to the repo — **FAIL** | 140.000 x 100.000 mm Edge.Cuts (140.15 x 100.15 including the 0.15 mm stroke) = 140.000 cm2, 1-up, no rails — **PASS** | ENIG (board file, job file 'ENIG') — **PASS** | **NO** |
| **ESC rev_b** <br>*(sha `992570571D…995DDD`)* | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) — **PASS** | 0.140 mm outer = 4 oz / 0.0525 mm inner = 1.5 oz (F.Cu 0.1400, In1.Cu 0.0525, In2.Cu 0.0525, B.Cu 0.1400) — **PASS** | 0.200 mm, 4 segments at exactly that width (of 154) — **FAIL** | 0.2000 mm minimum, identical in all 2 repeat runs; 499 pairs at the 0.30 mm probe floor (that count flickers: zone fill is threaded) — **FAIL** | via 0.300 mm (min of 1990 vias) / PTH pad 0.200 mm; 110 of 223 PTH pads sit below the 0.30 mm finished-hole floor at 4 oz — **FAIL** | via 0.1500 x16, 0.1750 x12, 0.2000 x1962 / PTH min 0.125 mm at U204.11 — **FAIL** | 0 = 0 blind + 0 buried of 1990 vias -- all 1990 through on F.Cu->B.Cu; 0 blind, 0 buried, 0 micro — **PASS** | 1,542 pcbnew GetUnconnectedCount(False); kicad-cli 499 = ITS HARD CAP, therefore a truncation — **FAIL** | 504 error / 19 warn at 4 oz / 0.250 (total 523; 413 pad-bound as reported, 511 once duplicate pad numbers are addressed); 102 at 0.200 (86 error / 16 warn); 16 under the board's own rules, all via_dangling — **FAIL** | none: 0 gerber / drill / job files under repos/drone-arm/hardware/esc — **FAIL** | title block '' and no silk revision text anywhere on the board — **FAIL** | 173.800 x 282.930 mm Edge.Cuts (173.95 x 283.08 including the 0.15 mm stroke) = 491.732 cm2, 1-up, no rails — **PASS** | ENIG (board file, job file 'ENIG') — **PASS** | **NO** |
| **Code-SDR V2** <br>*(sha `309414D2…`)* | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) — **PASS** | 0.035 mm = 1 oz on all four copper layers (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) — **PASS** | 0.100 mm, 1510 segments at exactly that width (of 11168) — **PASS** | 0.1000 mm minimum, identical in all 5 repeat runs; 505-510 pairs at the 0.30 mm probe floor (that count flickers: zone fill is threaded) — **PASS** | via 0.200 mm (min of 1085 vias) / PTH pad 0.200 mm — **PASS** | via 0.1000 x53, 0.1250 x1013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57 — **WAIVED** | 0 = 0 blind + 0 buried of 1085 vias -- all 1085 through on F.Cu->B.Cu; 0 blind, 0 buried, 0 micro — **PASS** | 0 pcbnew GetUnconnectedCount(False); kicad-cli 0 (below the cap, and it agrees) — **PASS** | 0 error / 222 warning under the board's own project rules + its own .kicad_dru (4 rules, version line present, therefore LOADED) — **PASS** | 11 gerbers + .gbrjob + 2 Excellon = 1215 hits (1213 drills + 2 slots), 0 non-through, census reconciles; the repo carries 0 package files, so this package was exported here — **PASS** | title block '2.1' and cs-job.gbrjob Revision '2.1' — **PASS** | 101.600 x 101.600 mm Edge.Cuts (101.70 x 101.70 including the 0.15 mm stroke) = 103.226 cm2, 1-up, no rails — **PASS** | ENIG (board file, job file 'ENIG') — **PASS** | **YES** |
| **drone-mech airframe** <br>*(no PCB: measured 0 board files)* | n/a -- 0 PCB files (a machined/composite airframe) — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 vias: 0 via objects on 0 boards — **WAIVED** | n/a -- 0 nets: 0 net objects on 0 boards — **WAIVED** | interference sweep instead of DRC: 8 pairs / 1,255.303466 mm3 AS DELIVERED (6 genuine = 1,250.769445 mm3); the zero, 2 pairs / 4.010114 mm3 all artefact, exists only on evidence copies at a +38.485 mm elevon station change — **FAIL** | no manufacturing package: 205 STEP/brep, 0 drawings, 0 ply book, 0 revision; the executed change is 6 STEPs in evidence/, 0 in repos/ — **FAIL** | no revision carries the +38.485 mm station change; the design of record is the 42_6 shell, 4 solids, 742,306.360 mm3 — **FAIL** | not a panel: the 42_6 shell is 4 disjoint solids over 77.165 mm, with 41,775.81 mm3 of phantom outboard loft per side — **FAIL** | n/a -- no finish callout exists: 0 drawings, 0 ply book, printed PLA core + CF/glass wrap is a MATERIAL answer, not a surface finish — **WAIVED** | **NO** |

**Row 4 is not padding.** A machined/composite airframe has no copper, so **eight** of the thirteen
columns are inapplicable — measured, not asserted: **0** `.kicad_pcb` / `.kicad_pro` / `.kicad_sch` /
gerber / drill / job files under `repos/drone-mech` against **205** STEP/brep files. The five
columns that do apply carry the mechanical verdicts.

**Column 13 for drone-mech is WAIVED, not answered with a mass.** v2 filled it with
"printed PLA core 145.739 g + CF/glass wrap 105.779 g" — a **mass**, which is not a surface finish.
The correct answer is that no finish callout exists (0 drawings, 0 ply book) and that printed PLA
plus a CF/glass wrap is a **material** answer. That single cell was the wrong cell v2 carried.

---

## 2. How each line was measured

### 2.0 The boards, and the proof they are the boards of record

`measure.py` loads each copy with `pcbnew` and **never saves**. Hashes of the copies:

| row | copy | sha256 | equals |
|---|---|---|---|
| drone-arm main rev_b | `boards/da_best.kicad_pcb` | `372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077` | `fab-da-fanout3/work.kicad_pcb` = `fab-da-fanout2/…fanout7` = `verify-w5`'s fanout7copy (`verify-w5/REPORT.md:18-20`) |
| ESC rev_b | `boards/esc.kicad_pcb` | `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD` | every ESC unit in this programme |
| Code-SDR V2 | `boards/cs.kicad_pcb` | `309414D2B371C6265629352FC0AA7252AA3E3B630488849187761D24B09FF486` | `fab-cs-drc/drcenv/V0.kicad_pcb` |
| drone-arm repo original | `boards/da_repo.kicad_pcb` | `9B3BBA85C01AAC9E8365AF999F5231C3951E3428C37544A2B2CADC425F89953C` | the repo board (reference only, not a row) |

Source tags:

| tag | file | produced by |
|---|---|---|
| `M-DA` `M-ESC` `M-CS` | `out/measure_{da_best,esc,cs}.json` | `"C:/Program Files/KiCad/9.0/bin/python.exe" measure.py` (pcbnew 9.0.7, read-only) |
| `D-*` | `drc/*/drc.json`, `out/drc_summary.json` | `kicad-cli pcb drc --format json --severity-all --units mm`, 10 runs, all exit 0 (`out/drc_run.log`) |
| `G-DA` `X-CS` | `out/drill_census.json`, `export_cs/` | `drill_census.py` (own Excellon parser, drills and G85 slots apart); the CS package exported here with `kicad-cli pcb export gerbers/drill` |
| `SCAN` | `out/facts.json → scan` | `os.walk` over `repos/drone-mech`, `repos/drone-arm/hardware/esc`, `repos/Code-SDR/hardware/v2` |

### 2.1 Layer count and copper weight — parsed from each file's own stackup block
| board | copper | dielectrics | total over copper |
|---|---|---|---|
| drone-arm | `F.Cu 0.035 / In1 0.035 / In2 0.035 / B.Cu 0.035` | 0.2 / 1.04 / 0.2 | 1.580 mm vs 1.60 declared |
| ESC | `F.Cu 0.14 / In1 0.0525 / In2 0.0525 / B.Cu 0.14` | 0.2 / 0.795 / 0.2 | 1.575 mm |
| Code-SDR | `0.035 ×4` | 0.13 / 1.2 / 0.13 | 1.600 mm exact |

These reproduce `AGENT_BOARD.md:34-41` exactly. The stackup block is **nested**, so it is split on
`(layer "` — a lazy `(.*?)` capture returns an empty dict and would make "1 oz" an assumption
(v2 trap, still armed).

### 2.2 Minimum track — the minimum over every **segment**, never over segments + vias
DA **0.200** (500 of 2,306), ESC **0.200** (4 of 154), CS **0.100** (1,510 of 11,168). Acceptance
floor: **0.250 mm at 4 oz** (Eurocircuits 105 µm, the last published step), **0.100 mm at 1 oz**
(Multi-CB's 1 oz row; PCBWay publishes 0.075).

### 2.3 Minimum space — the only column where the obvious method returns a wrong answer
DRC reports a gap only when it breaks a rule, so a clean board says *min space ≥ rule* and nothing
more. Each board is re-run with a **0.30 mm clearance floor** in a copy; KiCad then prints the
ACTUAL gap of every pair, and the smallest actual is the real minimum.

| board | smallest actual | pairs at the floor | own rule |
|---|---|---|---|
| DA | **0.1250**, identical in 3 repeat runs | 507–510 | 0.125 |
| ESC | **0.2000**, identical in 2 repeat runs (372 at 0.2000 under the 0.250 rule, 371 of them pad-only) | 499 | 0.200 |
| CS | **0.1000**, identical in 5 repeat runs | 505–510 | 0.100 |

All three land exactly on their own floor — a probe that over-reported would have found something
*below* the rule, one that under-reported something above it.

**The pair count is not reproducible and the minimum is.** Re-running the sheet from scratch produced
a different pair count on DA and CS (507, 510, 508 and 509, 510, 505, 507, 507) while the minimum
read 0.1250 / 0.1000 in **every** run (`out/space_repeat.log`). KiCad fills zones on worker threads
before the check, so pairs sitting within a few micrometres of the floor flicker. **Column 4 charges
the minimum, which is stable to 0.0001 mm; the pair count is stated as a range and charged at
nothing.** A cell that quoted "509 pairs" as an exact number would be quoting a run, not a board.

**Caveat, stated because it is real:** the probe file **replaces** the board's own `.kicad_dru`
rather than adding to it, which is why the CS probe run also shows **25 `copper_edge_clearance`**
items that the board's own rules suppress. Only the `clearance` values are used for this column.

### 2.4 Minimum drill — via and PTH pad reported separately
| board | min via drill | min PTH pad drill | pads below the applicable hole floor |
|---|---|---|---|
| drone-arm | **0.100** (14 vias) | 0.200 | 0 at 1 oz |
| ESC | 0.300 (16) | **0.200** | **110 of 223** below 0.300 at 4 oz |
| Code-SDR | 0.200 | 0.200 | 0 at 1 oz |

A via-only count reports "0 below 0.2" on a board carrying 110 sub-0.3 mm holes at 4 oz — which is
exactly how v1's ESC cell came out PASS.

### 2.5 Minimum annular ring, with its population named
Ring = min over the pad's two axes of `(size − drill)/2`, per via **and** per PTH pad. Two traps
were live here and both were hit and fixed this run:

1. **`PCB_VIA.GetWidth()` with no layer argument asserts and hangs** in 9.0.7 — every diameter is
   read per layer.
2. **A slot is not a circle.** J202/J203 pad S1 is a 0.6 × 1.7 mm slot in a 1.0 × 2.1 mm pad, i.e.
   0.200 mm ring on both axes. The first version of this script used
   `(min(size) − max(drill))/2`, called it −0.350 mm, and **invented 8 violations**. Fixed to the
   per-axis minimum before any number was published.

| board | via rings (count) | min PTH ring | owner |
|---|---|---|---|
| drone-arm | 0.100 (21) · 0.150 (28) · 0.175 (281) · 0.200 (6) | **0.150** | `U41.17` |
| ESC | 0.150 (16) · 0.175 (12) · **0.200 (1,962)** | **0.125** | `U204.11` |
| Code-SDR | 0.100 (53) · 0.125 (1,013) · 0.150 (6) · 0.300 (13) | **0.150** | `U10.57` |

### 2.6 Non-through vias BY SPAN — never a diameter-derived total
Classification is `GetViaType()` **plus the measured layer pair**: through = F.Cu→B.Cu; blind =
touches exactly one outer layer; buried = touches neither. Drill is never used to classify.

| artefact | vias | through | blind | buried | non-through | old 0.2 mm gate |
|---|---|---|---|---|---|---|
| **drone-arm best** | 336 | 321 | **11** | **4** | **15** | 14 |
| drone-arm repo original | 341 | 305 | 26 | 10 | **36** | 33 |
| ESC rev_b | 1,990 | 1,990 | 0 | 0 | **0** | 0 |
| Code-SDR V2 | 1,085 | 1,085 | 0 | 0 | **0** | 0 |

The 15, layer pair by layer pair:

```
0.100 F.Cu→In1.Cu blind 5 | 0.100 F.Cu→In2.Cu blind 2 | 0.100 In1.Cu→B.Cu blind 1
0.100 In2.Cu→B.Cu blind 2 | 0.300 In2.Cu→B.Cu blind 1 | 0.100 In1.Cu→In2.Cu BURIED 4
```

Three readings agree the answer is 15 (span 11 + 4; depth 12 + 3; declared type 14 micro + 1 blind),
and the 0.2 mm diameter gate sees 14 — it cannot see the 0.300 mm blind, whose only defect is its
span (`fab-da-package7/REPORT.md:61-76`; `verify-w5/REPORT.md:33-53`).

### 2.7 Unconnected — the tool named, and whether it is at its cap
| board | pcbnew `GetUnconnectedCount(False)` | `kicad-cli` | reading |
|---|---|---|---|
| drone-arm | **0** | 0 | both far below any cap and in agreement ⇒ the zero is evidence |
| ESC | **1,542** | **499** | exactly 499 on two different ESC boards ⇒ the cap, i.e. a truncation |
| Code-SDR | **0** | 0 | below cap, trustworthy |

The ESC population behind 1,542 is also measured: 667 nets, **556** with ≥2 pads, **16** carrying a
segment (2.88 %), **540** with no copper at all, 154 segments / 628.27 mm
(`fab-checklist-v2/REPORT.md:192-205`, reproduced from the same board).

### 2.8 DRC — the rule set is part of the number, and so is whether the rules loaded
A `.kicad_dru` without `(version 1)` is **silently ignored** by KiCad; the v5 verifier's first
no-HDI gate "passed" on a rule set that was never read (`verify-w5/REPORT.md:55-60`). Three defences
are built in and asserted in `out/drc_summary.json → dru_file`:

1. every rule file is checked to exist, carry a `(version 1)` line and contain rules;
2. every custom-rule run must differ from the own-rules run in the direction the rule predicts;
3. the ESC's 0.250 / 0.200 variants differ in **exactly three values** by construction, so their
   different counts are a controlled proof the file is live.

| board | rule set | violations | severity | unconnected in the same run |
|---|---|---|---|---|
| drone-arm | own project rules | **7** (`via_diameter` ×7) | 7 error | 0 |
| drone-arm | span gate `A.Via_Type != 'Through'` | **22** = 14 `microvia_drill_out_of_range` + 1 `drill_out_of_range` + 7 `via_diameter` | 22 error | 0 |
| ESC | own project rules | **16** (`via_dangling`) | 0 error / 16 warning | 499 |
| ESC | 4 oz @ 0.250 (9 rules) | **523** = 414 clearance + 70 annular + 16 via_diameter + 16 dangling + 4 track + 3 connection | 504 error / 19 warning | 499 |
| ESC | 4 oz @ 0.200 (9 rules) | **102** = 70 annular + 16 via_diameter + 16 dangling | 86 error / 16 warning | 499 |
| ESC | 4 oz @ 0.250, duplicate pad numbers addressed | **629** | 610 error / 19 warning | 499 |
| Code-SDR | own project rules + own `.kicad_dru` | **222** = 199 `lib_footprint_mismatch` + 13 `via_dangling` + 10 `track_dangling` | **0 error / 222 warning** | 0 |

**The ESC's 523 is a floor, and this run measures by how much.** A KiCad annular-ring check does
not report a pad whose number is duplicated inside its footprint, and this board has **1,160 such
pads across 51 footprints**. One controlled experiment (`drc/x_renum`, `drc/x_allrenum`): renumber
them uniquely, change nothing else, re-run the same rule file — **523 → 629, +98 `annular_width`
and +8 `hole_clearance`**, with the clearance count unchanged at 414 and unconnected unchanged at
499. So:

| reading | pad-bound | carried copper | total |
|---|---|---|---|
| as DRC reports it | **413** | 110 | 523 |
| with duplicate pad numbers addressed | **511** | 110 | 629 |

The programme's settled "413 DRC items at 4 oz, 100 % footprint-bound, identical on all three board
states" is therefore **correct as a DRC reading and a floor as a design fact**: the 371 intra-footprint
pad gaps at exactly 0.2000 mm are complete (the clearance count does not move), but the pad **ring**
population at 4 oz is **140 pads below 0.200 mm**, of which DRC reports 42.

### 2.9 Gerber package — three states
| board | files | holes | verdict |
|---|---|---|---|
| drone-arm | 11 Gerbers + `.gbrjob` + **7 Excellon** + pos (161 rows) | **360 drills + 4 slots = 364 hits**, of which **5 blind/buried files carry 15 holes**; job rev `B` | complete, revision-stamped, **SENDABLE = NO** |
| ESC | **0** | — | nothing exists anywhere under `hardware/esc` |
| Code-SDR | 11 Gerbers + `.gbrjob` + **2 Excellon** | **1,215 hits = 1,213 drills + 2 slots**; 0 non-through; job rev `2.1`, 4 layers, 1.6 mm, ENIG | complete, frame-free, **exported here** because the repo carries none |

Both censuses reconcile against an identity you can check by hand:

* drone-arm: 336 vias + 22 PTH pads + 6 NPTH = **364 hits**; minus 4 G85 slots = **360 drills**;
  5 blind/buried files carrying **15** holes = the 15 non-through vias.
* Code-SDR: 1,085 vias + 128 PTH pads + 2 NPTH = **1,215 hits**; minus 2 G85 slots = **1,213 drills**.

A validator that adds `G85` lines into a drill count over-counts by exactly those slots; one that
cannot read a blind/buried file's `FileFunction` under-counts the HDI holes.

### 2.10 Revision stamp
`GetTitleBlock().GetRevision()` plus the package job file: drone-arm **`""`** on the board (the
package says `B` only because `title_block_rev_B.patch` was applied to a copy — 5 lines, 19
carriers); ESC **`""`**, and no silk revision text anywhere; Code-SDR **`2.1`** in the title block
**and** in `cs-job.gbrjob → GeneralSpecs.ProjectId.Revision`.

### 2.11 Panel outline and area — centreline, not the stroke-inclusive bbox
`GetBoardEdgesBoundingBox()` includes the 0.15 mm stroke: on drone-arm it reads 140.15 × 100.15 for
a 140.000 × 100.000 outline. The **Edge.Cuts drawings' own extent** is measured here, and the area
is the closed polygon from `GetBoardPolygonOutlines().Area()` (nm² → mm²):

| board | Edge.Cuts extent | incl. stroke | polygon area | panelisation |
|---|---|---|---|---|
| drone-arm | **140.000 × 100.000** | 140.15 × 100.15 | **140.000 cm²** | 1-up, no rails |
| ESC | **173.800 × 282.930** | 173.95 × 283.08 | **491.732 cm²** | 1-up |
| Code-SDR | **101.600 × 101.600** | 101.70 × 101.70 | **103.226 cm²** | 1-up; 1.7 mm over the 100 mm price tier |

**v2's ESC outline was the bbox, not the outline** (173.950 × 283.080). Corrected here to
173.800 × 282.930; the area is unchanged because it comes from the polygon, not the bbox.

The ESC's compaction answer belongs here and only here: the only compaction delivered is
**370.119 cm² (−121.613 cm², −24.73 %)** and it is **UNSAFE** (phase corridor 1.50–3.50 mm against
6.991 mm needed; 935 DRC against 523 at 0.250; pcbnew unconnected 1,620, +78). The honest floor for
today's BOM is **370 cm²**; **382.709 cm²** is the smallest placement whose 18 phases pass at the
conservative requirement — and it is a **placement** answer, not a 60 A answer (§3.2).

### 2.12 Surface finish
`(copper_finish "ENIG")` in all three board files, `"Finish": "ENIG"` in the drone-arm and Code-SDR
job files. The repo's stale rev_a job file says `"Finish": "None"` — a third reason it cannot be the
order.

### 2.13 Orderable
Column 14 is not a new measurement: it is the reading of columns 1–13 under §0's definition. A board
is **YES** only if no sampled row carries a blocking defect **and** a sendable package exists today.

---

## 3. The four rows, in their own units

### 3.1 drone-arm main rev_b — 15 non-through vias, and the zero is proved impossible
Fifteen was not assumed: nine conversion strategies were built and all 15 candidates were put
through KiCad's own DRC one at a time with a zone refill — **kept 0, dropped 15**
(`fab-da-fanout3/gated.kicad_pcb.gate.json`). The six measurements that close it:

| measurement | value |
|---|---|
| legal through-via pad at each site, ±0.50 mm sweep on a 0.01 mm grid | **0 of 15** reach 0.400 mm |
| best `pad_max` anywhere in reach | **0.3754 mm** (`/SENS_SCLK`), 24.6 µm short |
| sites with foreign copper **on** the point | **10 of 15** |
| sites that cannot host even a 0.300 mm pad | **12 of 15** |
| converting all 15 in place, own rules | **121 violations**, 0 unconnected |
| re-escape that passed the connectivity guard | 6 of 15 — **all six then failed DRC on refill** (58 violations) |

Eleven of the 15 sit inside the **U10 QFN-80 0.4 mm pitch pad field**; four need an inner-layer bus
moved whose tracks are all at the 0.125 mm floor. **The fix is a U10 fan-out re-escape, not a via
edit** — and the same fan-out is what the missing ESC command path needs (`U10.43–48` on 64
auto-generated nets, no `J60–J66`).

The package is complete and correct and still unshippable: **63/63 assertions**, 364 hits, job rev
`B` — with **5 blind/buried Excellon files carrying all 15 holes**. A fab reading those drill files
would refuse or mis-build the board, which is why the sendability check is separate from the
assertion count.

### 3.2 ESC rev_b — three independent blockers plus one design failure
1. **1,542 unconnected** (pcbnew; 499 is `kicad-cli`'s cap). 2.88 % of the route exists: 154
   segments, 628.27 mm, 540 of 556 nets with no copper.
2. **4 oz cannot be built from these packages.** 371 pad gaps at exactly 0.2000 mm inside 9
   footprints, **110 PTH pads at 0.200 mm** against a published 0.30 mm finished hole at 140 µm,
   and every via ring ≤ 0.200 mm against a 0.200 mm OAR row. Eight fabricators surveyed against
   published capability tables (`fab-4oz-capability/REPORT.md:37-41`): **no house publishes 0.200 mm
   at 4 oz.** The pad-ring population is **140 pads below 0.200 mm**, not the 42 DRC reports (§2.8).
3. **No package and no revision marking at all** — 0 gerber, 0 drill, 0 job, 0 pos.
4. **And the rail does not carry its bus current**, so routing it changes nothing:

| element | section | capacity | verdict |
|---|---|---|---|
| **BATP** F.Cu | 1,217.29 mm² in **14 unjoined components** → **0 mm in series** | contributes nothing | — |
| **BATP** In1 min-cut | **12.5–17.7 mm** (0.657–0.929 mm²) | **23.1 A** (k=.048) / **11.5 A** (k=.024) | **FAIL, 2.6× / 5.2×** |
| **BATN** B.Cu plane | 1.98–2.80 mm² | **60.5–77.8 A** (k=.048) | passes, 101–143 % |
| **BATN** 45 via barrels | 1.4137 mm² | **47.4 A** (k=.048) | **FAIL on the barrels** |

Required at 60 A / ΔT 20 K: **1.957 mm²** = 13.981 mm at 4 oz or 96.991 mm at 1.5 oz inner
(`REV_B_ARCHITECTURE.md:18`; `av-esc-rail-wave/REPORT.md:131-146`). Six independent rails carry
**59.05 A** each (`REV_B_ARCHITECTURE.md:35-36`). BATN survives only on an **unmeasured** ⅓
per-leg sharing assumption. Both rail-fix attempts still fall short (1.5082 / 1.7595 mm²), and the
back-layer arm puts BATP on B.Cu **where BATN's 5,106.6 mm² plane already sits** — never costed.

The heat spreader is **mandatory**: 60 A is 1.67× the board-only junction limit at RthJA 40 °C/W and
TA 45 °C (35.9 A). Top-side, **outside the outline**, 352–528 cm² at 250 W/m²K — **0.92× to 1.38×
the board's own area**, so the true packaging footprint is **735–911 cm²**, not 382.71.

### 3.3 Code-SDR V2 — orderable, and the fiducial "PASS" was manufactured by moving a threshold
Everything a bare-board order needs is there: **0 errors / 222 warnings / 0 unconnected**, a
frame-free 1,215-hole package stamped `2.1`, ENIG, 1.6 mm, closed corners. The 222 warnings are
199 `lib_footprint_mismatch` (board-vs-library, 0 of 373 footprints differs in any pad node or 3-D
model), 13 `via_dangling`, 10 `track_dangling` — fab houses do not read warnings.

**What v2 could not see and this sheet states:** the assembly unit placed **9 fiducials** and its own
verifier printed

```
FID1 (94.28, 8.68)  pour gap 1.22 mm (need 1.25)  FAIL
FID2 (6.28, 9.48)   pour gap 1.22 mm (need 1.25)  FAIL
all fiducials OK: False
```

`need` is `dot/2 + clearance = 0.5 + 0.75 = 1.25` with ±0.02 tolerance (`verify_fiducials.py:65`),
so **1.22 mm is 0.01 mm short even of the tolerance**. `fab-cs-assembly/REPORT.md:107-110` reports
the 1.22 correctly and then substitutes "the requirement it has to meet is 1.00 mm", never saying
the verifier returned False (`v2v-fab-verify/REPORT.md:70-80`). The engineering risk is negligible —
the shortfall is most likely the 0.02 mm raster — but **the threshold was moved after the tool
failed, and undisclosed**. No summary in this sheet repeats that: the fiducial state is *9 placed,
0 new DRC items, 1.22 mm against 1.25 mm required, FAIL, undisclosed in the source unit*.

The remaining assembly gaps are sourcing, not engineering: **373 of 373 BOM rows have no MPN**.

### 3.4 drone-mech airframe — zero genuine interference, on copies, at a cost nobody has accepted
| state | pairs | volume |
|---|---|---|
| as delivered (design of record) | **8** | 1,255.303466 mm³ = 6 genuine (1,250.769445) + 2 artefact (4.534020) |
| after the executed station change (copies) | **2** | **4.010114 mm³, 100 % artefact, genuine 0** |

The zero is reached by three changes (`fab-dm-final/REPORT.md:37-53`): the elevon moves **+38.485 mm
outboard** (root 55.250 → 93.735), the wing cove extends to z 157.000 (9,753.95 mm³/side), and the
pushrod must be re-drawn as a real link. **What it costs, named:** a tail-interface change — the horn
goes from |x| 121…139 to 159.485…177.485 while the servo stays at 125, i.e. 34.485 mm inboard of the
horn. No duct-module change and no span loss. The zero is **not** in any revision, the 42_6 shell is
**4 disjoint solids over 77.165 mm** (a **+97 g Boolean repair** is a prerequisite), and outboard of
|x| 204.750 the solid carries **41,775.81 mm³ (3.09 %)** of phantom loft per side.

---

## 4. The two settled constraints, and what each costs

### 4.1 NO HDI — drone-arm is blocked at 15, ESC and Code-SDR at 0
Classified by span: **drone-arm 15, ESC 0, Code-SDR 0.** One owner decision sits inside the
constraint and only one: dropping `m_MinThroughDrill` from 0.200 to 0.150 (still a standard
mechanical drill at every fab surveyed) converts **2 of 15 and no more** (`/SENS_SCLK`, `/RF_MISO`).

### 4.2 4 oz on the ESC only — three doors, all costed
| door | what it means | cost |
|---|---|---|
| **A — 2 oz** | geometry is already 2 oz-compliant (0.200 at 70 µm) | zero work; **halves the copper** on a rail that already fails at 23.1 A |
| **B — 4 oz + 3 packages** | U201 (QFN-80 P0.4), 6 × LQFP-48 P0.5, J202/J203 (USB-C) | real work; clears the **371 intra-footprint pad gaps**; **does not clear the 110 × 0.200 mm holes** and does not touch the **42 pad rings DRC reports (140 measured)** |
| **C — a written fab waiver** | 0.200 mm at 140 µm, 0.200 mm hole, 0.200 mm ring | a quote, not engineering; LeitOn's own page refuses it |

There is no fourth door. **The 4 oz rules must be adopted before the route is finished** — 97.1 % of
it does not exist, so it is free now and a 540-net rip-up later.

---

## 5. What is NOT known

Every item below is a question this sheet cannot answer from an artefact. The owner column is who
must answer it, not who is at fault.

| # | open question | owner | why it blocks |
|---:|---|---|---|
| **U1** | **The ESC A/B**: 2 oz, 4 oz + 3 packages, or a written 4 oz waiver at 0.200 mm? | **owner (Darsh)** | no routing budget is meaningful until it is answered; the geometry is compliant at 2 oz today and non-compliant at 4 oz forever |
| **U2** | **Whether *any* heavy-copper house will build 0.200 mm track/space, 0.200 mm finished hole and 0.200 mm ring at 140 µm, in writing** | fab / CM (quote) | eight surveyed houses publish floors above it; door C exists only if one signs |
| **U3** | **Whether 60 A per phase (59.05 A per rail) is the real current** — repo-stated, never measured; no current waveform exists | owner + EE | every copper, hole and thermal requirement scales with it |
| **U4** | **Where BATP goes.** The recommended fix puts it on the "bare" B.Cu plane — where BATN's 5,106.6 mm² plane already sits. Two 60 A rails on one layer, separated, is not costed | EE / next layout wave | the only routing fix on the table is unevidenced |
| **U5** | **The mapping of the 110 × 0.200 mm PTH pads to their footprints** | next PCB wave | decides whether door B actually clears them; nobody has done it |
| **U6** | **Whether the true 4 oz pad-bound population is 511, not 413** — the +98 ring items and +8 hole-clearance items this run found by renumbering duplicate pads | independent instrument | changes the size of door B, not its existence |
| **U7** | **Via barrel plating: 25 µm or 38 µm?** | fab / CM | moves every barrel number by 1.5× and **flips BATN's verdict** |
| **U8** | **The heat spreader inside or outside the outline**, and whether any airframe bay has **735–911 cm²** | owner + airframe | the ESC's real packaging footprint is 2× the board |
| **U9** | **The 38.485 mm elevon station change** — accept the tail-interface change or not? | **owner** | the interference zero exists only at that station, on copies |
| **U10** | **The +97 g Boolean repair** of the 42_6 shell (4 disjoint solids over 77.165 mm) | next CAD wave | no stress, mass or interference number describes a manufacturable part until it lands |
| **U11** | **The pushrod re-draw** — compulsory after U9, and its 4.010114 mm³ of placeholder is the only thing the sweep still sees | next CAD wave | the last 2 "pairs" are this placeholder |
| **U12** | **The 41,775.81 mm³ phantom outboard loft** (3.09 %/side beyond the station table) | CAD author | the fixture around the moved plate is not real |
| **U13** | **MPN sourcing for Code-SDR: 373 of 373 BOM rows** | owner / purchasing | stops the **assembly** PO, not the etch order |
| **U14** | **A named assembly house's written fiducial requirement** (size, count, edge distance, pour gap) | CM | the 1.25 mm the 1.22 mm is measured against is a house-agnostic construction, not a quote |
| **U15** | **DFM etch compensation** on Code-SDR's 0.100/0.125 mm ring | fab | KiCad does not model it; the ring may grow or shrink post-compensation |
| **U16** | **Every impedance number** — two 2-D finite-difference solves, no measurement; the coupon is designed and **not ordered** ($54.24 against the $60 cap, $0 committed) | owner (spend) | the coplanar-pour question is 43.6 Ω wide |
| **U17** | **Solder-mask dam width** between the 0.4–0.5 mm pitch pads on DA and ESC | fab | every board declares 0.05 mm; only the shop knows its yield |
| **U18** | **Panelisation cost and feasibility** for any board — no panel drawing, no quote | CM | a 1-up 284 mm ESC board is not a price |
| **U19** | **Who owns the U10 fan-out re-escape** (drone-arm 15 vias + the missing ESC command path are the same rip-up) | programme lead | it is the single largest remaining design task and it has no owner |
| **U20** | **Whether the Code-SDR 101.6 mm board should be re-cut to 100 mm** for the price tier, or paid for | owner (cost) | 1.7 mm of price class, not a process limit |

---

## 6. The instruments behind these numbers

Five instruments in this programme produced plausible green numbers while being wrong. A reader
deserves to know which numbers came from which tool, and which of them were checked.

| measurement | instrument (file) | sanity check | status |
|---|---|---|---|
| layers, stackup, copper weight | `measure.py` stackup parser (pcbnew) | reproduces `AGENT_BOARD.md:34-41` on three boards; nested-block parse verified against a hand read of `esc_rev_b.kicad_pcb` | **checked** |
| min track | `measure.py` segment census | 500 segments at 0.200 on DA matches the programme's count; the "2,306 tracks" that circulated is segments **+ vias** (2,306 segs + 336 vias) | **checked** |
| min space | `kicad-cli` DRC with a 0.30 mm probe `.kicad_dru` | all three boards land **exactly** on their own rule (0.1250 / 0.2000 / 0.1000) in **every** repeat run; the PAIR COUNT does not reproduce (507–510 on DA, 505–510 on CS across 5 runs, `out/space_repeat.log`), so the minimum is charged and the count is a range | **checked, with one caveat**: the probe replaces the board's own `.kicad_dru` (25 CS edge items appear) |
| min drill | `measure.py` via + pad drill census | reconciles with the drill package by hand identity (336+22+6−4 = 360) | **checked** |
| **min annular ring** | `measure.py` per-layer diameters | **FAILED FIRST, THEN FIXED**: `(min size − max drill)/2` invented 8 slot violations on J202/J203; now per-axis | **checked after a caught defect** |
| **the DRC annular check itself** | `kicad-cli` 9.0.7 | **FAILS**: it does not report a pad whose number is duplicated in its footprint — measured by renumbering 1,160 pads and watching the count go 523 → 629. The 42 it reports is a **floor**; the measured population is 140 | **known-broken; quoted only as a floor** |
| non-through vias by span | `measure.py` (`GetViaType` + `TopLayer`/`BottomLayer`) | three independent readings agree on 15; the diameter gate sees 14 and is retired as a count | **checked** (the diameter gate is **not**) |
| unconnected | `pcbnew GetUnconnectedCount(False)` vs `kicad-cli` | the cap test: exactly 499 on two different boards is structurally a cap | **checked** |
| DRC counts | `kicad-cli pcb drc`, 10 runs | every `.kicad_dru` asserted to carry `(version 1)`; behaviour proved by the controlled 0.250/0.200 pair; all runs exit 0 | **checked, with the annular blind spot above** |
| drill/gerber census | `drill_census.py` (own Excellon parser) | both censuses reconcile to a hand identity; slots counted apart from drills; blind/buried recognised by `FileFunction` | **checked** |
| area / outline | `pcbnew GetBoardPolygonOutlines().Area()` + Edge.Cuts extent | area agrees with a shoelace walk to 0.0000 on all three boards; the extent is the centreline, not the stroke-inclusive bbox | **checked** (v2 used the bbox for the ESC) |
| revision / finish | board title block + job file JSON | CS reads `2.1` in both; DA's board is empty while its package says `B` | **checked** |
| drone-mech interference | OCCT `BRepAlgoAPI` booleans (`fab-dm-final`) | independently reproduced to **1e-9** on 12 quantities including the 4.010114 and the 0.831215 horn clip (`verify-w5/REPORT.md:137-171`) | **checked by a second instrument** |
| drone-mech solids/loft | CadQuery/OCP + section probes | 4 disjoint solids over 77.165 mm and the 41,775.81 mm³ loft are both re-derivable from `body-structure` | **checked for existence, not re-measured here** |
| ESC rail capacity | `av-esc-rail-wave/02_geom.py` max-flow | four controls (K1–K4) pass before any board number is quoted; the earlier corridor tool's min-cut returned **flow 0** on both rails and was excluded | **checked, with the controls named** |
| heat spreader area | thermal solve + area arithmetic | 1.67× the junction limit; 352–528 cm² at 250 W/m²K | **cited, not re-measured** |

**The five broken instruments, and where their fingerprints are:**

1. **An ASCII text probe missed a Unicode minus.**
2. **A threshold moved from 1.25 to 1.00 so a FAIL printed as PASS** — the Code-SDR fiducial, §3.3.
   Not repeated anywhere in this sheet: every threshold has one value, quoted once.
3. **The no-HDI gate classified by drill DIAMETER** and could not see blind/buried vias — column 7
   is by **span**, and the 0.300 mm blind that the diameter gate cannot see is named in the cell.
4. **A `.kicad_dru` without `(version 1)` is silently ignored** — §2.8 asserts the version line in
   every rule file and proves load by behaviour.
5. **A corridor tool counted foreign pads, invented B.Cu on a net with none, and printed PASS over
   its own −80 % FAIL** — the rail numbers here come from the replacement instrument, which
   measures filled zone polygons and refuses to sum a layer a net does not occupy; its own min-cut
   defect (flow 0, excluded) is stated rather than hidden.

Two more instruments were caught **this run** and are recorded because they are the same class:
`(min size − max drill)/2` on a slot (§2.5) and the stroke-inclusive bbox as an outline (§2.11).

---

## 7. One line per board, unforgiving

**drone-arm main rev_b — NOT ORDERABLE.** *15 non-through vias* (11 blind + 4 buried, 14 at
0.100 mm) in 5 blind/buried drill files; **0 of 15** survive conversion, so the fix is a U10
fan-out re-escape. Behind it: no ESC command path (`U10.43–48` on 64 auto nets, no `J60–J66`), an
empty revision, and a repo whose only package is the rev_a board.

**ESC rev_b — NOT ORDERABLE.** *1,542 unconnected* (pcbnew; 499 is a cap) so there is nothing to
fabricate — and when there is, **4 oz cannot be built from these packages** (371 pad gaps at
0.2000 mm, 110 holes at 0.200 mm, 140 pad rings below 0.200 mm, no house publishing 0.200 mm at
140 µm) *and the rail carries 23.1 A of 59.05 A*, 2.6× short. The 370.12 cm² compaction must not be
ordered either: its phase corridor is 1.50–3.50 mm against 6.991 mm.

**Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today.** *0 errors, 0 unconnected, 1,215 holes*, a
frame-free package stamped `2.1`, ENIG, closed corners. Two quote lines, neither a redesign: the
0.100–0.125 mm ring and the 0.100 mm track/space at 1 oz. **Assembly is not orderable**: 373/373
MPNs missing, and the fiducials sit 1.22 mm from the pour against a 1.25 mm requirement — a FAIL
its own unit reported as a PASS by moving the threshold.

**drone-mech airframe — NOT READY, and not for the reason the last two waves said.** *6 genuine
pairs / 1,250.769445 mm³* are in the design of record. The zero is real and measured — 2 pairs /
4.010114 mm³, 100 % artefact — but it lives on evidence copies at a **+38.485 mm** station change no
revision carries, over a shell that is **4 disjoint solids**. The blocker is not interference any
more; it is that the fix was never accepted into the design.

---

## 8. Charge summary, and what changed since v2

Counted from §1 by `check_report.py` (it parses the markdown table, re-derives every verdict from
the raw measurements, and exits non-zero on any disagreement):

| board | PASS | FAIL | WAIVED | counted cells | orderable |
|---|---:|---:|---:|---:|---|
| drone-arm main rev_b | 7 | 5 | 1 | 13 | **NO** |
| ESC rev_b | 5 | 8 | 0 | 13 | **NO** |
| Code-SDR V2 | 12 | 0 | 1 | 13 | **YES** |
| drone-mech airframe | 0 | 4 | 9 | 13 | **NO** |
| **all four** | **24** | **17** | **11** | **52** | **1 of 4** |

### Corrections and additions since v2

1. **drone-mech surface finish: PASS → WAIVED.** v2 answered a surface-finish cell with a **mass**
   (145.739 g PLA + 105.779 g wrap). No finish callout exists; the cell is now WAIVED with that
   reason. This is the wrong cell v2 carried.
2. **drone-mech DRC → interference: PASS → FAIL.** v2 PASSed the cell on the **copy** state
   (0 pairs / 0.000000 mm³). The deliverable carries **8 pairs / 1,255.303466 mm³, 6 of them
   genuine**. A copy state is not the artefact; the cell now says both numbers and fails.
3. **drone-arm annular ring: FAIL → WAIVED.** v2 charged drone-arm's 0.100 mm via ring as FAIL while
   charging Code-SDR's identical 0.100 mm ring as WAIVED. One rule now applies to both rows: at 1 oz
   a 0.1 mm ring is **below the published 0.125 floor but above the board's own rule** — a quote
   line, not a redesign. At 4 oz it is a FAIL (the ESC), because the OAR row is 0.200.
4. **ESC outline: 173.950 × 283.080 → 173.800 × 282.930.** v2 quoted the stroke-inclusive bounding
   box as the Edge.Cuts outline. The area, 491.732 cm², is unchanged (polygon, not bbox).
5. **ESC DRC: 523 is a floor.** Renumbering the board's **1,160 duplicate-numbered pads** (geometry
   untouched) takes the same 0.250 rule set from **523 to 629**, +98 pad rings and +8 hole-clearance
   items the annular check silently skips. The pad-bound floor is **511**, not 413. The 371 pad gaps
   are unaffected and remain complete.
6. **The 140-pad ring population is stated.** The pad rings below 0.200 mm at 4 oz are **140**
   (126 at 0.175, 12 at 0.150, 2 at 0.125) — not the 42 DRC reports, and not "all 1,990 vias".
7. **The slot-ring defect is recorded.** `(min size − max drill)/2` invents 8 violations on
   J202/J203 pad S1; the ring of a slot is per-axis. Caught before publication, and both the broken
   and the fixed formula are named in §2.5 and §6.
8. **Code-SDR's fiducial FAIL is stated, with its source unit named.** 1.22 mm against 1.25 mm;
   the 1.00 mm threshold was a substitution made after the unit's own verifier returned False.
9. **The ESC rail failure is in the verdict, not a footnote.** BATP 23.1 A of 59.05 A; BATN's plane
   passes but its 45 barrels give 47.4 A, and its pass rests on an unmeasured ⅓ sharing assumption.
10. **The heat spreader is carried as a packaging number**: 352–528 cm² outside the board outline,
    making the ESC's true footprint **735–911 cm²**.
11. **Counts move by one in two rows** (drone-arm 7/6/0 → 7/5/1; drone-mech 2/3/8 → 0/4/9), and the
    total from 26/17/9 to **24/17/11**. All three changes are items 1–3 above, not new measurements.
12. **The clearance-pair count is not reproducible; the clearance minimum is.** A from-scratch re-run
    of this sheet moved the probe's pair count on DA and CS (507/510/508 and 509/510/505/507/507) while
    the minimum stayed 0.1250 / 0.1000 in every run. Column 4 now charges the **minimum** and states
    the count as a range; `out/space_repeat.log` is the receipt. This is a new instrument finding, not
    a correction of v2 — v2 quoted one run of the same probe without saying which.

---

## 9. Artefacts and reproduction

| file | what it is |
|---|---|
| `REPORT.md` | this sheet |
| `measure.py` → `out/measure_{da_best,da_repo,esc,cs}.json` | every board quantity: stackup, tracks, vias by span, ring and drill histograms, PTH rings below 0.200 with owners, title block, Edge.Cuts extent, area, unconnected |
| `drc_run.py` → `drc/*/drc.json`, `out/drc_summary.json` | **all 10 DRC runs**, each with its rule file's presence, `(version 1)` line and rule count |
| `drill_census.py` → `out/drill_census.json` | Excellon census for package7 and for the CS export, with the hand identity checked |
| `out/space_repeat.log` | the repeatability control on the clearance probe: the minimum is stable in every run, the pair count is not |
| `derive.py` → `out/cells.json`, `out/summary.json`, `out/table.md`, `out/facts.json` | the 52 cells, each with its verdict **and the rule that produced it**; the blocking number per board; the rendered table |
| `check_report.py` → `out/check_report.log` | parses REPORT.md, re-derives every verdict from the raw JSON, and fails on any contradiction. **Exit code 0.** |
| `out/checker_negative_test.log` | the checker's own control: three deliberate corruptions (a flipped cell, a changed blocking number, a softened verdict) each produce **exit 1**, and the restored file hashes identical |
| `boards/` | byte copies of the three boards (+ the repo original as a control) with each project's `.kicad_dru`, `fp-lib-table` and `CodeSDR.pretty` — a DRC outside its project directory invents violations |
| `export_cs/` | the Code-SDR package exported for this sheet: 11 Gerbers, `.gbrjob`, PTH + NPTH Excellon, drill maps, pos |
| `drc/x_pthring`, `drc/x_renum`, `drc/x_allrenum` | the three experiments that establish the annular blind spot (isolated rule → 42; renumber one footprint → +16; renumber all → +106) |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-checklist-v3
& "C:/Program Files/KiCad/9.0/bin/python.exe"   measure.py        # 4 boards, ~2 min
& "C:/Program Files/KiCad/9.0/bin/python.exe"   drc_run.py        # 10 DRC runs, ~2.5 min
& "C:/Program Files/Python312/python.exe"       drill_census.py `
      "E:/engineering-portfolio-audit/evidence/fab-da-package7/package" export_cs
& "C:/Program Files/Python312/python.exe"       derive.py         # 52 cells + tallies
& "C:/Program Files/Python312/python.exe"       check_report.py   # must exit 0
```

---

*One board, one truth. If a number here is not on a command or a file, it does not exist.*

---

## 10. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-checklist-v3 | THE MASTER CHECKLIST: 4 rows x 13 verdict cells + orderable = 52 cells, every
| one a measured value with its source and a verdict DERIVED by predicate (derive.py, not typed);
| check_report.py re-derives all 52 independently from the raw JSON, exit 0, and is negative-tested
| (3 deliberate corruptions -> exit 1, restored file hash-identical).
| PASS/FAIL/WAIVED: drone-arm 7/5/1 - ESC 5/8/0 - Code-SDR 12/0/1 - drone-mech 0/4/9 = 24/17/11.
| ORDERABLE: Code-SDR YES (bare board); the other three NO.
| BLOCKING NUMBERS: drone-arm 15 non-through vias (11 blind + 4 buried, 14 at 0.100), 0 of 15
| convertible -> U10 fan-out re-escape. ESC 1,542 unconnected (pcbnew; 499 is kicad-cli's cap) and
| the rail at 23.1 A of 59.05 A (2.6x short) and 4 oz unbuildable (371 pad gaps at 0.2000 mm, 110
| holes at 0.200 mm, 140 pad rings below 0.200 mm against a 0.200 OAR row). Code-SDR 0 error / 222
| warning / 0 unconnected, 1,215-hole package rev 2.1 - assembly blocked by 373/373 missing MPNs
| and a 1.22 mm fiducial pour gap against 1.25 mm. drone-mech 6 genuine pairs / 1,250.769445 mm3 in
| the design of record; the zero costs +38.485 mm of elevon station and lives on copies only.
| THREE v2 CELLS CORRECTED: drone-mech surface finish was answered with a MASS -> WAIVED; drone-mech
| interference PASSed on a copy state -> FAIL on the artefact; drone-arm's 0.100 mm ring FAIL vs
| Code-SDR's identical 0.100 mm ring WAIVED -> one rule applied to both, WAIVED at 1 oz.
| TWO MEASUREMENT CORRECTIONS: the ESC Edge.Cuts is 173.800 x 282.930 (v2 quoted the stroke-inclusive
| bbox); the ESC 4 oz DRC of 523 is a FLOOR - renumbering the 1,160 duplicate-numbered pads takes the
| same rule file to 629 (+98 annular, +8 hole clearance), so the pad-bound floor is 511, not 413.
| 20 open questions listed with an owner each (section 5).
```