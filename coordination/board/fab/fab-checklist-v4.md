# The pre-fab master checklist, v4 — four rows, fifteen columns, one blocking number each

**Owner:** fab-checklist specialist, wave 8. **Date:** 2026-11-16. **Host:** KiCad 9.0.7
(`C:/Program Files/KiCad/9.0/bin/kicad-cli.exe`; bundled `python.exe` + `pcbnew` 9.0.7 for board
reads; CPython 3.12 + OCP/CadQuery for the CAD geometry).
**Supersedes:** `evidence/fab-checklist-v3/REPORT.md` (v3, 2026-11-16), which superseded v2 and v1.

**Hard rule observed:** nothing was written into a repo, nothing committed or pushed, no `audit/*`
branch touched. Every board analysed here is a **byte copy** in `boards/`; every artefact is under
`evidence/fab-checklist-v4/`. `$0` spent. The three board copies reproduce the hashes the programme
already records (§2.0), so no measurement here is about a drifted file.

**One thing changed under this sheet while it was being written, and it is not mine.** The Code-SDR
repo now carries a **16-file bare-board package** at `hardware/v2/fab/` in commit `1a20bd6`
("fab: add Code-SDR V2 rev 2.1 bare-board package exported from this board"), committed by another
unit. v3's cell said *"the repo carries 0 package files"*. That cell is now false, and §2.9 measures
whether the committed package is this board's before the sheet is allowed to say it is. I did not
write that package and did not touch the repo.

**Constraints in force:** NO HDI on any board; ONLY the ESC is 4 oz; $60 coupon/prototype cap; ESC
single-sided and as compact as possible (owner, 2026-11-15).

---

## 0. The answer, before the evidence

| board | orderable today | 15. the number that decides it |
|---|---|---|
| **drone-arm main rev_b** | **NO** | **15 non-through vias** — 11 blind + 4 buried, 14 at 0.100 mm; **0 of 15** survive a KiCad DRC conversion, so the zero needs a U10 fan-out re-escape, not a via edit |
| **ESC rev_b** | **NO** | **1,542 unconnected** (pcbnew, uncapped; `kicad-cli`'s 499 is its cap, calibrated in §2.7) — 1,542 of the 2,316 pad-to-pad connections this netlist requires are open, so there is nothing to fabricate yet |
| **Code-SDR V2** | **YES**, bare board | **0 for the bare board** (0 errors, 0 unconnected, 222 warnings; a 16-file package now in the repo and byte-matching this board) — the assembly PO stops at **373 of 373 BOM rows without an MPN** |
| **drone-mech airframe** | **NO** (mechanical) | **6 genuine interference pairs** (1,250.769445 mm³) in the design of record; the measured zero is a copy state at a **+38.485 mm** elevon station change no revision carries |

Three of four are refused, and none of the refusals is a labelling argument.

**What "orderable" means here** — unchanged from v1–v3, because the word does the most work:

> **ORDERABLE = a bare-board fabrication order placed today, from artefacts that exist today,
> produces the board the design describes, with nothing to fix afterwards.**

A board that etches but cannot function is **not** orderable, because the rework is the thing this
programme exists to avoid (`AGENT_BOARD.md:5-25`). Assembly data is scored separately (§7, §8).

**Counting rule.** 4 boards × **14 verdict-bearing columns** = **56 verdict cells**, plus a
**blocking-number** column (15) and the verdict column (16). Every cell ends in exactly one of
`PASS` / `FAIL` / `WAIVED`, **and every verdict is produced by a predicate over a measurement file**
(`derive.py`), never typed. `check_report.py` re-derives all 56 from the raw measurements and fails
if the table, the tallies, the blocking numbers, the corrections or the prose disagree with them.

**What v4 adds.** v3 was strong and had two wrong cells. v4 fixes both, moves the solids count out of
the outline cell into its own column (14), adds the blocking number (15), and files **13 BOARD
CORRECTION rows** with the old and the new value side by side (§4), each carrying a machine check.

---

## 1. THE CHECKLIST

Rendered by `derive.py` from `out/cells.json`; each cell is **value** — **verdict**. Sources are
`M-*` (pcbnew on a copy), `D-*` (`kicad-cli pcb drc`), `G-DA`/`X-CS` (Excellon census), `C-ESC`
(the cap calibration), `P-DM`/`G-DM` (STEP geometry), `SCAN` (artefact scan of the repo). §2 gives
the method behind every tag.

| board | 1. layers | 2. copper weight | 3. min track | 4. min space | 5. min drill | 6. min annular ring | 7. non-through vias BY SPAN | 8. unconnected (tool, cap?) | 9. DRC (severity, rules loaded?) | 10. gerber package state | 11. revision stamp | 12. outline and plan area | 13. surface finish | 14. model integrity | 15. blocking number | 16. orderable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** <br>*(best artefact: fanout3 = fanout7, sha `372C1D52…FA9077`)* | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) — **PASS** | 0.035 mm = 1 oz on all four copper layers (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) — **PASS** | 0.200 mm, 500 segments at exactly that width (of 2306) — **PASS** | 0.1250 mm minimum, identical in all 3 repeat runs; 515-517 pairs at the 0.30 mm probe floor (the count is not stable: 515, 515, 517 across 3 runs; zone fill is threaded) — **PASS** | via 0.100 mm (min of 336 vias) / PTH pad 0.200 mm — **FAIL** | via 0.1000 x21, 0.1500 x28, 0.1750 x281, 0.2000 x6 / PTH min 0.150 mm at U41.17 — **WAIVED** | 15 = 11 blind + 4 buried of 336 vias -- 0.1 mm blind (F.Cu->In1.Cu x5, F.Cu->In2.Cu x2, In1.Cu->B.Cu x1, In2.Cu->B.Cu x2); 0.1 mm buried (In1.Cu->In2.Cu x4); 0.3 mm blind (In2.Cu->B.Cu x1) — **FAIL** | 0 pcbnew GetUnconnectedCount(False) and 0 from kicad-cli; both far below every measured cap and in agreement; all 438 required pad-to-pad connections are made — **PASS** | 7 error / 0 warning under the board's own project rules; 22 error under the span gate (14 microvia + 1 drill + 7 via_diameter) — **FAIL** | package7: 63/63 assertions, 11 gerbers + job + 7 Excellon, 360 drills + 4 slots = 364 hits, 5 blind/buried files carrying 15 holes, job rev 'B', SENDABLE = NO — **FAIL** | board title block '' ; package7 carries 'B' on 19 carriers because title_block_rev_B.patch was applied to a COPY, not to the repo — **FAIL** | 140.000 x 100.000 mm Edge.Cuts (140.15 x 100.15 including the 0.15 mm stroke) = 140.000 cm2, 1-up, no rails — **PASS** | ENIG (board file, job file 'ENIG') — **PASS** | 1 closed Edge.Cuts loop, 0 holes -- the board is one piece (GetBoardPolygonOutlines) — **PASS** | 15 non-through vias (11 blind + 4 buried); 0 of 15 survive a KiCad DRC conversion, so the fix is a U10 fan-out re-escape | **NO** |
| **ESC rev_b** <br>*(sha `992570571D…995DDD`)* | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) — **PASS** | 0.140 mm outer = 4 oz / 0.0525 mm inner = 1.5 oz (F.Cu 0.1400, In1.Cu 0.0525, In2.Cu 0.0525, B.Cu 0.1400) — **PASS** | 0.200 mm, 4 segments at exactly that width (of 154) — **FAIL** | 0.2000 mm minimum, identical in all 3 repeat runs; 499 pairs at the 0.30 mm probe floor (the count is not stable: 499, 499, 499 across 3 runs; zone fill is threaded) — **FAIL** | via 0.300 mm (min of 1990 vias) / PTH pad 0.200 mm; 110 of 223 PTH pads sit below the 0.30 mm finished-hole floor at 4 oz — **FAIL** | via 0.1500 x16, 0.1750 x12, 0.2000 x1962 / PTH min 0.125 mm at U204.11 — **FAIL** | 0 = 0 blind + 0 buried of 1990 vias -- all 1990 through on F.Cu->B.Cu; 0 blind, 0 buried, 0 micro — **PASS** | 1,542 pcbnew 9.0.7 GetUnconnectedCount(False) -- NOT at a cap: the same netlist reads 2,196 on its zero-copper placement, and the tool returns 1,000 on a 1,000-net calibration board; kicad-cli floors at exactly 499 (calibrated N 400/499/500/501/550/1000) while pcbnew returns the true N (400/499/499/499/499/499); 1,542 of the 2,316 pad-to-pad connections this netlist requires are open — **FAIL** | 504 error / 19 warn at 4 oz / 0.250 (total 523; 413 pad-bound as reported, 511 once duplicate pad numbers are addressed, total 629); 102 at 0.200 (86 error / 16 warn); 16 under the board's own rules, all via_dangling — **FAIL** | none: 0 gerber / drill / job files under repos/drone-arm/hardware/esc — **FAIL** | title block '' and no silk revision text anywhere on the board — **FAIL** | 173.800 x 282.930 mm Edge.Cuts (173.95 x 283.08 including the 0.15 mm stroke) = 491.732 cm2, 1-up, no rails — **PASS** | ENIG (board file, job file 'ENIG') — **PASS** | 1 closed Edge.Cuts loop, 0 holes -- the board is one piece (GetBoardPolygonOutlines) — **PASS** | 1,542 unconnected (pcbnew, uncapped; kicad-cli's 499 is its cap) -- 1,542 of 2,316 required connections are open, so there is nothing to fabricate yet | **NO** |
| **Code-SDR V2** <br>*(sha `309414D2…`)* | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) — **PASS** | 0.035 mm = 1 oz on all four copper layers (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) — **PASS** | 0.100 mm, 1510 segments at exactly that width (of 11168) — **PASS** | 0.1000 mm minimum, identical in all 3 repeat runs; 508-512 pairs at the 0.30 mm probe floor (the count is not stable: 508, 512, 512 across 3 runs; zone fill is threaded) — **PASS** | via 0.200 mm (min of 1085 vias) / PTH pad 0.200 mm — **PASS** | via 0.1000 x53, 0.1250 x1013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57 — **WAIVED** | 0 = 0 blind + 0 buried of 1085 vias -- all 1085 through on F.Cu->B.Cu; 0 blind, 0 buried, 0 micro — **PASS** | 0 pcbnew GetUnconnectedCount(False) and 0 from kicad-cli; both far below every measured cap and in agreement; all 1,093 required pad-to-pad connections are made — **PASS** | 0 error / 222 warning under the board's own project rules + its own .kicad_dru (4 rules, version line present, therefore LOADED) — **PASS** | 16 files committed in the repo under hardware/v2/fab (commit 1a20bd6): 11 gerbers + .gbrjob + 2 Excellon + 2 drill maps; 1215 hits (1213 drills + 2 slots), 0 non-through, census reconciles; all 14 compared files are byte-identical to this sheet's export once the project name and timestamp metadata is stripped, so the package IS this board — **PASS** | title block '2.1' and cs-job.gbrjob Revision '2.1' — **PASS** | 101.600 x 101.600 mm Edge.Cuts (101.70 x 101.70 including the 0.15 mm stroke) = 103.226 cm2, 1-up, no rails — **PASS** | ENIG (board file, job file 'ENIG') — **PASS** | 1 closed Edge.Cuts loop, 0 holes -- the board is one piece (GetBoardPolygonOutlines) — **PASS** | 0 for the bare board (0 errors, 0 unconnected, 222 warnings); the assembly PO stops at 373 of 373 BOM rows without an MPN | **YES** |
| **drone-mech airframe** <br>*(no PCB: measured 0 board files)* | n/a -- 0 PCB files (a machined/composite airframe) — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 PCB files — **WAIVED** | n/a -- 0 vias: 0 via objects on 0 boards — **WAIVED** | n/a -- 0 nets: 0 net objects on 0 boards — **WAIVED** | interference sweep instead of DRC: 8 pairs / 1,255.303466 mm3 AS DELIVERED (6 genuine = 1,250.769445 mm3); the zero, 2 pairs / 4.010114 mm3 all artefact, exists only on evidence copies at a +38.485 mm elevon station change — **FAIL** | no manufacturing package: 205 STEP/brep, 0 drawings, 0 ply book, 0 revision; the executed change is 6 STEPs in evidence/, 0 in repos/ — **FAIL** | no revision carries the +38.485 mm station change; the design of record is the 42_6 shell, 4 solids, 742305.526 mm3 — **FAIL** | Outline and plan area, measured from the geometry (the solids are counted in column 14, not here): the design of record 42_6 is 372.425 x 158.328 x 640.000 mm (span x height x length) with a plan (x-z) area of 649.84 cm2 = 64,984 mm2, converged to 0.011 % between 0.10 and 0.05 mm/px after removing a raster bias that a known-good 120 x 30 mm control reproduces at 3,600.01 of 3,600.00 mm2; the phase15 assembly is 516 solids, 3 of them construction lofts spanning the whole model (3,409.6 mm, which no 756.0 mm airframe contains), so the 513 parts give 409.500 x 148.000 x 756.000 mm and 1,227.35 cm2 of plan — **PASS** | n/a -- no finish callout exists: 0 drawings, 0 ply book, printed PLA core + CF/glass wrap is a MATERIAL answer, not a surface finish — **WAIVED** | 4 solids, every pair separated: minimum 8.2592 mm, largest 112.5616 mm, so this is 4 pieces and not one manufacturable part; the +97 g Boolean repair is still a prerequisite — **FAIL** | 6 genuine interference pairs (1250.769445 mm3) in the design of record; the measured zero is a copy state at a +38.485 mm elevon station that no revision carries | **NO** |

**Column 12 no longer answers a geometry question with a solids count.** In v3 the drone-mech cell
read *"not a panel: the 42_6 shell is 4 disjoint solids…"* — a solids census where an outline and an
area were asked for. The solids now sit in column 14, and column 12 carries the measured envelope and
the measured plan area (§2.11). That is the first of the two weak cells fixed.

**Column 8 names its tool, its cap, and proves which reading is truncated** (§2.7). That is the
second.

**Row 4 is not padding.** A machined/composite airframe has no copper, so **eight** of the fourteen
columns are inapplicable — measured, not asserted: **0** `.kicad_pcb` / `.kicad_pro` / `.kicad_sch` /
gerber / drill / job files under `repos/drone-mech` against **205** STEP/brep files. The six columns
that do apply carry measured answers, including the outline and the plan area that v3 was missing.

---

## 2. How each line was measured

### 2.0 The boards, and the proof they are the boards of record

`measure.py` loads each copy with `pcbnew` and **never saves**. Hashes of the copies:

| row | copy | sha256 | equals |
|---|---|---|---|
| drone-arm main rev_b | `boards/da_best.kicad_pcb` | `372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077` | `fab-da-fanout3/work.kicad_pcb` = `fab-da-fanout2/…fanout7` = `verify-w5`'s fanout7 copy |
| ESC rev_b | `boards/esc.kicad_pcb` | `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD` | every ESC unit in this programme |
| Code-SDR V2 | `boards/cs.kicad_pcb` | `309414D2B371C6265629352FC0AA7252AA3E3B630488849187761D24B09FF486` | `fab-cs-drc/drcenv/V0.kicad_pcb` = the repo board today |
| drone-arm repo original | `boards/da_repo.kicad_pcb` | `9B3BBA85C01AAC9E8365AF999F5231C3951E3428C37544A2B2CADC425F89953C` | the repo board (reference only, not a row) |

Source tags:

| tag | file | produced by |
|---|---|---|
| `M-DA` `M-ESC` `M-CS` | `out/measure_{da_best,esc,cs}.json` | `"C:/Program Files/KiCad/9.0/bin/python.exe" measure.py` (pcbnew 9.0.7, read-only) |
| `D-*` | `drc/*/drc.json`, `out/drc_summary.json` | `kicad-cli pcb drc --format json --severity-all --units mm`, **10 runs re-executed for v4**, all exit 0 (`out/drc_run.log`) |
| `G-DA` `X-CS` | `out/drill_census.json`, `export_cs/`, `out/cs_package_match.json` | `drill_census.py` (own Excellon parser) and `cs_package_match.py` (byte comparison against the committed package) |
| `C-ESC` | `out/esc_cap_test.json` | `esc_cap_test.py` — pcbnew and kicad-cli on six boards of KNOWN unconnected count |
| `S-*` | `out/space_repeat_v4.json` | `space_repeat.py` — three repeats of the 0.30 mm clearance probe per board |
| `P-DM` `G-DM` | `out/dm_geom.json`, `out/dm_plan_refine.json`, `out/dm_plan_parts2.json` | `dm_geom.py`, `dm_plan_refine.py`, `dm_plan_parts2.py` (OCP/CadQuery, read-only) |
| `SCAN` | `out/facts.json → scan` | `os.walk` over `repos/drone-mech`, `repos/drone-arm/hardware/esc`, `repos/Code-SDR/hardware/v2` |

`measure.py` gained two censuses this run and both are used: the **outline topology** (`OutlineCount`
and `HoleCount`, which is the PCB analogue of a solids count and feeds column 14) and the **net
census** (`nets_total`, `nets_multi_pad`, `required_edges`, `nets_with_copper`), which is the control
on the unconnected column.

### 2.1 Layer count and copper weight — parsed from each file's own stackup block
| board | copper | dielectrics | total over copper |
|---|---|---|---|
| drone-arm | `F.Cu 0.035 / In1 0.035 / In2 0.035 / B.Cu 0.035` | 0.2 / 1.04 / 0.2 | 1.580 mm vs 1.60 declared |
| ESC | `F.Cu 0.14 / In1 0.0525 / In2 0.0525 / B.Cu 0.14` | 0.2 / 0.795 / 0.2 | 1.575 mm |
| Code-SDR | `0.035 ×4` | 0.13 / 1.2 / 0.13 | 1.600 mm exact |

These reproduce `AGENT_BOARD.md:34-41` exactly. The stackup block is **nested**, so it is split on
`(layer "` — a lazy `(.*?)` capture returns an empty dict and would make "1 oz" an assumption.

### 2.2 Minimum track — the minimum over every **segment**, never over segments + vias
DA **0.200** (500 of 2,306), ESC **0.200** (4 of 154), CS **0.100** (1,510 of 11,168). Acceptance
floor: **0.250 mm at 4 oz** (Eurocircuits 105 µm, the last published step), **0.100 mm at 1 oz**.

### 2.3 Minimum space — and the pair count, measured instead of assumed
DRC reports a gap only when it breaks a rule, so each board is re-run with a **0.30 mm clearance
floor**: KiCad then prints the ACTUAL gap of every pair, and the smallest actual is the real minimum.

| board | smallest actual | pairs at the floor, 3 repeats | own rule |
|---|---|---|---|
| DA | **0.1250**, identical in all 3 runs | 515, 515, 517 | 0.125 |
| ESC | **0.2000**, identical in all 3 runs | 499, 499, 499 | 0.200 |
| CS | **0.1000**, identical in all 3 runs | 508, 512, 512 | 0.100 |

All three land exactly on their own floor — a probe that over-reported would have found something
*below* the rule, one that under-reported something above it.

**The pair count is not reproducible and the minimum is.** v3 reported 507–510 on DA and 505–510 on
CS; v4's repeats give 515–517 and 508–512. Because a 48 % swing appeared once in the full DRC run
(CS 753 total `clearance` items), that was chased down rather than waved through: **753 = 531 error
items + 222 warnings**, and of the 531 only ~510 carry an `actual … mm` value; the charged quantity
is the count of clearance pairs that print an actual. The minimum never moved. Column 4 charges the
minimum and states the count as a range (`out/space_repeat_v4.json` is the receipt).

**Caveat, stated because it is real:** the probe file **replaces** the board's own `.kicad_dru`
rather than adding to it, which is why the CS probe run also shows `copper_edge_clearance` items that
the board's own rules suppress. Only the `clearance` values are used for this column.

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
stay live and both were hit and fixed in v3, not re-broken here:

1. **`PCB_VIA.GetWidth()` with no layer argument asserts and hangs** in 9.0.7 — every diameter is
   read per layer.
2. **A slot is not a circle.** J202/J203 pad S1 is a 0.6 × 1.7 mm slot in a 1.0 × 2.1 mm pad, i.e.
   0.200 mm ring on both axes. `(min(size) − max(drill))/2` calls that −0.350 mm and **invents 8
   violations**.

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

> **BOARD CORRECTION (C2).** The programme counted these by **declared type** and called it *"14
> microvia + 1 blind"*. A microvia is a drill class, not a span class; by span they are **11 blind +
> 4 buried**, and buried is worse for fabrication than blind (sequential lamination plus an
> internal-only connection). The 0.300 mm In2→B via is invisible to the old 0.2 mm diameter gate,
> which is the whole reason the classification moved to span.

### 2.7 Unconnected — the tool, the cap, and a calibration that settles it (WEAK CELL 2)

The v3 cell carried the placeholder token **"1,542 unconnected"**: a number with no tool, no cap
statement and no proof. It is replaced by a measured value that names the instrument and shows it is
not truncated.

> **BOARD CORRECTION (C3).** The count was quoted across the programme as **499**, which is
> `kicad-cli`'s reporting cap, not a measurement. The measured count is **1,542**. Both numbers are
> in this sheet — 1,542 as the count, 499 named as the cap — and §2.7 is what makes that distinction
> checkable rather than a matter of opinion.

Two instruments disagree by 3.09× on the same board. Wave 5's rule says a count sitting exactly on a
tool's cap is a truncation. So both were calibrated against boards whose unconnected count is known
**by construction** — N nets, two pads each, no copper (`fab-esc-reconcile/testboards/t6_*`):

| calibration board | known unconnected | pcbnew 9.0.7 | `kicad-cli` |
|---|---:|---:|---:|
| t6_400x2 | 400 | **400** | 400 |
| t6_499x2 | 499 | **499** | **499** |
| t6_500x2 | 500 | **500** | **499** ← floored |
| t6_501x2 | 501 | **501** | **499** ← floored |
| t6_550x2 | 550 | **550** | **499** ← floored |
| t6_1000x2 | 1,000 | **1,000** | **499** ← floored |

**The cap is exactly 499, and pcbnew returns the true count at every N.** Then, on the ESC:

| board | nets | required pad-to-pad connections | pcbnew | `kicad-cli` |
|---|---:|---:|---:|---:|
| ESC rev_b (as loaded) | 666 | **2,316** | **1,542** | 499 (capped) |
| ESC power-first placement, **0 tracks, 0 vias, 0 zones** | 666 | 2,316 | **2,196** | 499 (capped) |
| Code-SDR V2 (control) | 260 | 1,093 | **0** | 0 |

So the ESC's 1,542 is a **measurement, not a cap**: the same netlist reads **2,196** with all its
copper removed, which no tool capped at 1,542 or at 499 could return, and the count responds to
structure. The required-edge total (Σ pads−1 over nets with ≥2 pads) is computed from the pad census
alone and can be checked by hand: 2,316. Of those, **774 are connected** (2,316 − 1,542). The
zero-copper placement of the same netlist reads 2,196, i.e. **120** of the required edges are
satisfied by pads that already touch, so the board's 154 track segments, 1,990 vias and 96 zones
close the remaining **654**.

Control: Code-SDR reads **0** on both tools with 1,093 required connections all made — a known-good
zero reproduced by the same method (`out/esc_cap_test.json`).

### 2.8 DRC — the rule set is part of the number, and so is whether the rules loaded
A `.kicad_dru` without `(version 1)` is **silently ignored** by KiCad; the v5 verifier's first no-HDI
gate "passed" on a rule set that was never read. Three defences are built in and asserted in
`out/drc_summary.json → dru_file`:

1. every rule file is checked to exist, carry a `(version 1)` line and contain rules;
2. every custom-rule run must differ from the own-rules run in the direction the rule predicts;
3. the ESC's 0.250 / 0.200 variants differ in **exactly three values** by construction.

| board | rule set | violations | severity | unconnected in the same run |
|---|---|---|---|---|
| drone-arm | own project rules | **7** (`via_diameter` ×7) | 7 error | 0 |
| drone-arm | span gate `A.Via_Type != 'Through'` | **22** = 14 `microvia_drill_out_of_range` + 1 `drill_out_of_range` + 7 `via_diameter` | 22 error | 0 |
| ESC | own project rules | **16** (`via_dangling`) | 0 error / 16 warning | 499 (capped) |
| ESC | 4 oz @ 0.250 (9 rules) | **523** = 414 clearance + 70 annular + 16 via_diameter + 16 dangling + 4 track + 3 connection | 504 error / 19 warning | 499 (capped) |
| ESC | 4 oz @ 0.200 (9 rules) | **102** = 70 annular + 16 via_diameter + 16 dangling | 86 error / 16 warning | 499 (capped) |
| ESC | 4 oz @ 0.250, duplicate pad numbers addressed | **629** | 610 error / 19 warning | 499 (capped) |
| Code-SDR | own project rules + own `.kicad_dru` | **222** = 199 `lib_footprint_mismatch` + 13 `via_dangling` + 10 `track_dangling` | **0 error / 222 warning** | 0 |

**A KiCad annular-ring check does not report a pad whose number is duplicated inside its footprint**,
and the ESC has **1,160 such pads across 51 footprints**. Renumbering them (geometry untouched) takes
the same rule file **523 -> 629**, +98 `annular_width` and +8 `hole_clearance`, clearance count
unchanged at 414. So the pad-bound population is **511**, not 413, and the pad rings below 0.200 mm
at 4 oz are **140** (126 at 0.175, 12 at 0.150, 2 at 0.125), of which DRC reports 42.

> **BOARD CORRECTION (C10, C11).** The programme's "413 DRC items, 100 % footprint-bound" and the
> improvement claim **"413 -> 87"** both omitted the ring population: the same rule file reads **523**
> as reported, and **523 -> 629** once duplicate pad numbers are addressed. The rings below 0.200 mm
> are **140**, not the **42** the annular check reports.

### 2.9 Gerber package — three states, and a package that appeared mid-wave
| board | files | holes | verdict |
|---|---|---|---|
| drone-arm | 11 Gerbers + `.gbrjob` + **7 Excellon** + pos (161 rows) | **360 drills + 4 slots = 364 hits**, of which **5 blind/buried files carry 15 holes**; job rev `B` | complete, revision-stamped, **SENDABLE = NO** |
| ESC | **0** | — | nothing exists anywhere under `hardware/esc` |
| Code-SDR | **16 files committed** at `hardware/v2/fab/` (commit `1a20bd6`): 11 Gerbers + `.gbrjob` + 2 Excellon + 2 drill maps | **1,215 hits = 1,213 drills + 2 slots**; 0 non-through; job rev `2.1` | complete, frame-free, **in the repo** |

**Is the committed package this board's?** Measured rather than assumed (`cs_package_match.py`):
16 package files committed (1a20bd6) — and all 11 gerbers and both Excellon files are byte-**different**
raw (a re-export always is), and byte-**identical** once three pieces of export metadata are removed
— `%TF.CreationDate`, `%TF.ProjectId` (which carries the project *name*, and my export came from a
copy called `cs.kicad_pcb`), and the `G04`/`;` comment lines that repeat the timestamp. The
`.gbrjob` differs only in the same three fields. So:

> **the repo's package is geometrically the repo's board**, exported at a different time. It is not
> the fixed deliverable `8EC5741A` (that one carries the pour fix and 18 test points); it is
> `309414D2`, which is the board this row describes.

> **BOARD CORRECTION (C13).** v3 stated *"the repo carries 0 package files"*. As of commit `1a20bd6`
> that is false: **16 package files committed (1a20bd6)** at `hardware/v2/fab/`, and the paragraph
> above is the proof that they are this board's export rather than another board's.

Both censuses reconcile against an identity you can check by hand:

* drone-arm: 336 vias + 22 PTH pads + 6 NPTH = **364 hits**; minus 4 G85 slots = **360 drills**;
  5 blind/buried files carrying **15** holes = the 15 non-through vias.
* Code-SDR: 1,085 vias + 128 PTH pads + 2 NPTH = **1,215 hits**; minus 2 G85 slots = **1,213 drills**.

### 2.10 Revision stamp
`GetTitleBlock().GetRevision()` plus the package job file: drone-arm **`""`** on the board (the
package says `B` only because `title_block_rev_B.patch` was applied to a copy — 19 carriers); ESC
**`""`**, and no silk revision text anywhere; Code-SDR **`2.1`** in the title block **and** in
`cs-job.gbrjob → GeneralSpecs.ProjectId.Revision`.

### 2.11 Outline and plan area — measured from the geometry (WEAK CELL 1)

v3 answered the airframe's outline-and-area cell with a **solids count**. The replacement measures
both quantities from the STEP files the design of record points at.

**The method, and why it is quotable.** The plan area is the area of the shadow the part casts on the
ground plane. Every face triangle of every solid is projected onto (x, z) and filled into a binary
raster; for a closed solid the union of projected front and back faces is exactly the shadow. The
raster over-reads by roughly half a pixel around the silhouette, so the bias is modelled and
measured — `bias ≈ 0.5 · px · perimeter`, with the perimeter counted from the silhouette's boundary
pixels — and the correction is validated on shapes whose plan area is known in closed form:

| known-good case | exact | raster @0.25 | corrected | raster @0.10 | corrected |
|---|---:|---:|---:|---:|---:|
| box 120 × 40 × 30 (plan 120 × 30) | 3,600.00 | 3,637.56 | **3,600.06** | 3,615.01 | **3,600.01** |
| disc Ø40, axis y (plan π·20²) | 1,256.64 | 1,272.94 | **1,258.44** | 1,260.31 | **1,254.60** |

The rectangle reproduces to **0.0002 %**; the disc, whose perimeter is curved and therefore harder to
count from pixels, to **0.16 %**. That is the accuracy the airframe numbers inherit, and it is stated
beside them.

| shape | probe | raster | corrected |
|---|---|---:|---:|
| body of record 42_6 (4 solids) | 0.10 mm/px | 65,126.77 | **64,990.86 mm²** |
| body of record 42_6 | 0.05 mm/px | 65,051.65 | **64,983.73 mm²** |
| phase15 assembly, all 516 solids | 0.25 mm/px | 240,430.75 | 239,871.16 mm² |
| phase15 assembly | 0.125 mm/px | 240,155.70 | 239,872.02 mm² |
| the **513 parts** (construction lofts excluded) | 0.25 mm/px | 123,180.88 | 122,753.56 mm² |
| the **513 parts** | 0.125 mm/px | 122,949.42 | **122,735.33 mm²** |

Convergence: the body moves **0.011 %** between 0.10 and 0.05 mm/px; the assembly **0.0004 %** between
0.25 and 0.125. The quoted plan areas are the finest-resolution corrected values.

**A finding that changed the answer.** The full assembly's box is **1,193.869 × 148.000 × 3,409.595
mm** — a 3.4 m aircraft, which does not exist. Three of its 516 solids each span the whole model
(z from −1,393.354 to +2,016.241 mm, up to 1,193.869 mm wide, 88.643 mm tall); their own shadow is
**125,962 mm²**, which is *larger* than the 513 parts' 122,735 mm². They are loft/construction
geometry, not parts. Excluding them by a geometric rule — *z extent greater than half the model's z
span* — leaves **513 parts** with a coherent envelope:

| | span (x) | height (y) | length (z) | plan (x–z) area |
|---|---:|---:|---:|---:|
| **body of record, 42_6** | 372.425 mm | 158.328 mm | 640.000 mm | **649.84 cm²** |
| **airframe, 513 parts** | 409.500 mm | 148.000 mm | 756.000 mm | **1,227.35 cm²** |

`dm_plan_parts.py` (the first attempt) keyed its exclusion on solid INDEX; re-running it after
meshing returned the solids in a different order and it excluded **22 legitimate parts**, reporting
880 cm². That is the defect class this programme keeps finding — a correct measurement of the wrong
population — and it is recorded here rather than quietly deleted, because the fix was to key the
population on **geometry** and to mesh each solid immediately after reading its own bbox.

**The vertical axis is a measurement, not an assumption.** y is taken as up because the body of
record is 158.328 mm tall against 372.425 mm of span and 640.000 mm of length; a 640 mm-long fuselage
that was 372 mm tall would not be that aircraft. This is flagged as an open question (U21) rather
than hidden, because if the model's up-axis were different, the number above would be a side
projection.

### 2.12 Surface finish
`(copper_finish "ENIG")` in all three board files, `"Finish": "ENIG"` in the drone-arm and Code-SDR
job files. The repo's stale rev_a job file says `"Finish": "None"` — a third reason it cannot be the
order. For the airframe, **no finish callout exists** (0 drawings, 0 ply book) and printed PLA plus
a CF/glass wrap is a **material** answer, not a surface finish, so the cell is WAIVED.

### 2.13 Model integrity — the column the solids count belongs in
For a PCB the analogue of "how many bodies is this?" is the outline topology: `GetBoardPolygonOutlines`
returns the polygon set, and `OutlineCount` / `HoleCount` say whether the board is one piece. All
three boards read **1 loop, 0 holes**. For the airframe, `dm_geom.py` counts solids and measures the
pairwise minimum distance between them with `BRepExtrema_DistShapeShape`:

| body | solids | pairwise separations (mm) | reading |
|---|---:|---|---|
| 42_6 | **4** | 8.2592, 8.2592, 77.1654, 85.3893, 85.3893, 112.5616 | **4 pieces**, not one part |
| each board | 1 outline loop, 0 holes | — | one piece |

The 77.1654 mm is the 0↔2 separation the programme quotes as "4 disjoint solids over 77.165 mm"; the
**smallest** separation is 8.2592 mm, so the gap is 8.2592–112.5616 mm and the 77.1654 figure is one
pair of the six, not the closest one.

### 2.14 The blocking number — one figure per board, derived
Column 15 is not a summary of the row; it is the single figure that stops the purchase order, chosen
by rule and composed from the same JSON as the cells:

* the first number that must reach zero, in the order a fab would hit it;
* if a board has more than one independent stopper, the column carries the first, and §3 names the
  chain.

| board | blocking number | why this one |
|---|---:|---|
| drone-arm | **15** non-through vias | the board cannot be fabricated without HDI until this is 0 |
| ESC | **1,542** unconnected | nothing exists to fabricate; the rail and 4 oz questions come after a route exists |
| Code-SDR | **0** for the bare board | the etch order has no blocker; the assembly PO stops at **373** missing MPNs |
| drone-mech | **6** genuine pairs | first physical clash in the design of record |

---

## 3. The four rows, in their own units

### 3.1 drone-arm main rev_b — 15 non-through vias, and the zero is proved impossible
Fifteen was not assumed: nine conversion strategies were built and all 15 candidates were put through
KiCad's own DRC one at a time with a zone refill — **kept 0, dropped 15**
(`fab-da-fanout3.gated.kicad_pcb.gate.json`). The six measurements that close it:

| measurement | value |
|---|---|
| legal through-via pad at each site, ±0.50 mm sweep on a 0.01 mm grid | **0 of 15** reach 0.400 mm |
| best `pad_max` anywhere in reach | **0.3754 mm** (`/SENS_SCLK`), 24.6 µm short |
| sites with foreign copper **on** the point | **10 of 15** |
| sites that cannot host even a 0.300 mm pad | **12 of 15** |
| converting all 15 in place, own rules | **121 violations**, 0 unconnected |
| re-escape that passed the connectivity guard | 6 of 15 — **all six then failed DRC on refill** (58 violations) |

Eleven of the 15 sit inside the **U10 QFN-80 0.4 mm pitch pad field**; four need an inner-layer bus
moved whose tracks are all at the 0.125 mm floor. The package is complete and correct and still
unshippable: **63/63 assertions**, 364 hits, job rev `B` — with **5 blind/buried Excellon files
carrying all 15 holes**. The drill census also settles a counting slip: the package report's own
column adds to **359**; the census is **360 drills + 4 slots**.

### 3.2 ESC rev_b — four blockers, and the first is that there is no board yet
1. **1,542 unconnected** (pcbnew, uncapped — proved in §2.7). 774 of the 2,316 required connections
   exist, 654 of them made by copper; the rest of the route does not exist.
2. **4 oz cannot be built from these packages.** 371 pad gaps at exactly 0.2000 mm, **110 PTH pads at
   0.200 mm** against a published 0.30 mm finished hole at 140 µm, and **140 pad rings below 0.200
   mm** (DRC reports 42; §2.8). Eight fabricators were surveyed against published capability tables
   (`fab-4oz-capability/REPORT.md:37-41`): **no house publishes 0.200 mm at 4 oz** — four houses
   carry an explicit 4 oz row and the nearest published number is 0.229 mm.
3. **No package and no revision marking at all** — 0 gerber, 0 drill, 0 job, 0 pos.
4. **And the rail does not carry its bus current**, so routing it changes nothing:

| element | section | capacity | verdict |
|---|---|---|---|
| **BATP** F.Cu | 1,217.29 mm² in **14 unjoined components** → **0 mm in series** | contributes nothing | — |
| **BATP** In1 min-cut | **12.5–17.7 mm** (0.657–0.929 mm²) | **23.1 A** (k=.048) / **11.5 A** (k=.024) | **FAIL, 2.6× / 5.2×** |
| **BATN** B.Cu plane | 1.98–2.80 mm² | **60.5–77.8 A** (k=.048) | passes, 101–143 % |
| **BATN** 45 via barrels | 1.4137 mm² | **47.4 A** (k=.048) | **FAIL on the barrels** |

Required at 60 A / ΔT 20 K: **1.957 mm²** = 13.981 mm at 4 oz or 96.991 mm at 1.5 oz inner
(`REV_B_ARCHITECTURE.md:18`). The area floor is **370 cm2 for today's BOM** (§4, C5); the 316 cm2
figure needs the M5 lugs replaced. Six independent rails carry **59.05 A** each
(`REV_B_ARCHITECTURE.md:35-36`). The heat spreader is **mandatory**: 60 A is 1.67× the board-only
junction limit at RthJA 40 °C/W and TA 45 °C (35.9 A), top-side, **outside the outline**, 352–528 cm²
at 250 W/m²K — **0.92× to 1.38× the board's own area**, so the true packaging footprint is
**735–911 cm²**, not 382.71.

The "3 packages" framing is wrong in the direction that matters: at 4 oz this is **one impossible
part** (U201, QFN-80 P0.4, no equivalent at a coarser pitch) **plus 23 footprint edits** that keep
their parts and their netlist — one impossible part + 23 footprint edits, and nothing is a "three
packages" job.

> **BOARD CORRECTION (C4, C5, C7).** Three figures this programme carried are wrong, and all three
> move the decision rather than decorate it: the 4 oz vendor survey claimed *"five different houses"*
> where **four houses carry an explicit 4 oz row**; the area floor was published as **316 cm²** when
> it is **370 cm2 for today's BOM** (316 needs the M5 lugs replaced); and the package work is not
> **3 packages** but one impossible part plus 23 footprint edits. All three are rows C4, C5 and C7 of
> §4 with their sources.

### 3.3 Code-SDR V2 — orderable, and two numbers that were stale
Everything a bare-board order needs is there: **0 errors / 222 warnings / 0 unconnected**, a
frame-free 1,215-hole package stamped `2.1` **and now committed to the repo**, ENIG, 1.6 mm, closed
corners. The 222 warnings are 199 `lib_footprint_mismatch` (board-vs-library, 0 pad differences), 13
`via_dangling`, 10 `track_dangling` — fab houses do not read warnings.

**The fiducial: 1.22 mm was a measurement artefact.** The v3 sheet charged the fiducial pour gap as
"1.22 vs 1.25 FAIL". The 1.22 came from a **raster** distance transform at 0.02 mm; the exact polygon
distance is **1.2505 mm**, and the raster converges on that from below (1.2226 at 0.02, 1.2366 at
0.01). So on the repo board the requirement is met by **+0.0005 mm** — a pass with no manufacturing
margin, and the second, stricter rule (1.5 mm centre→any copper) is still missed by 0.250 mm. The
orderable copy in evidence (`8EC5741A`) pulls the pour back to **1.7505 mm** and clears both.

> **BOARD CORRECTION (C1).** The fiducial was charged as *"1.22 mm against 1.25 mm, FAIL"*. The 1.22
> is a raster floor, not the geometry: the exact polygon distance is **1.2505 mm**. The FAIL was
> manufactured by the measuring method, and the threshold it was compared against was separately
> moved from 1.25 to 1.00 in the source unit — both defects are named, neither is smoothed.

**The repo now holds a package.** Commit `1a20bd6` added 16 files under `hardware/v2/fab/`; §2.9
shows they are byte-identical to this sheet's export once export metadata is stripped. The last
bare-board mile is therefore closed, and the row's package cell says so.

The remaining gap is sourcing, not engineering: **373 of 373 BOM rows have no MPN** (58 rows
determinable without a decision, 32 needing an engineer, 283 being purchasing choices).

### 3.4 drone-mech airframe — zero genuine interference, on copies, at a cost nobody has accepted
| state | pairs | volume |
|---|---|---|
| as delivered (design of record) | **8** | 1,255.303466 mm³ = 6 genuine (1,250.769445) + 2 artefact (4.534020) |
| after the executed station change (copies) | **2** | **4.010114 mm³, 100 % artefact, genuine 0** |

The zero is reached by three changes (`fab-dm-final/REPORT.md`): the elevon moves **+38.485 mm
outboard** (root 55.250 → 93.735), the wing cove extends to z 157.000 (9,753.95 mm³/side), and the
pushrod must be re-drawn as a real link. Deletion alone does not reach zero — the claim was
**delete 4 + resize** and both are needed. **What it costs, named:** a tail-interface change — the horn
goes from |x| 121…139 to 159.485…177.485 while the servo stays at 125. No duct-module change and no
span loss. The zero is **not in any revision**, the 42_6 shell is **4 disjoint solids** with a
minimum separation of 8.2592 mm (a **+97 g Boolean repair** is a prerequisite), and the assembly
also carries **41,775.81 mm³** of phantom outboard loft per side. After the executed fixes the moved
state holds **0 genuine pairs**; the design of record still holds 6.

> **BOARD CORRECTION (C6, C8).** The board figure was **26 pairs**, which is exact arithmetic for a
> subset of the pair set and not a verdict about what is physically clashing: the **0 genuine pairs**
> state is the executed-fix copy. And the instruction *"delete 4 of 6 envelopes reaches zero"* is
> short by one step — deletion alone leaves 2 pairs; the **delete 4 + resize** change is what clears
> the module set.

---

## 4. BOARD CORRECTIONS — every figure this programme has corrected

**13 rows, old and new side by side.** The eight the owner asked for are C1–C8; C9–C13 are
corrections this sheet found while building v4. Each row carries a machine check that `check_report.py`
re-executes: the OLD value must appear **nowhere** in the section-1 table, the NEW value must appear
in this report outside this table, and the row must reproduce against its named source file. A
correction whose check fails is a FAIL of the sheet, not a footnote.

| id | board | what was wrong | OLD | NEW | checked against |
|---|---|---|---|---|---|
| C1 | Code-SDR V2 | the fiducial pour gap read 1.22 mm from a raster distance transform and was charged as a FAIL | `1.22 mm` | **1.2505 mm** | fab-cs-close/REPORT.md |
| C2 | drone-arm main rev_b | the 15 non-through vias were counted by DECLARED TYPE (14 microvia + 1 blind); by SPAN they are 11 blind + 4 buried | `14 microvia + 1 blind` | **11 blind + 4 buried** | fab-checklist-v4/out/measure_da_best.json (vias_by_span) |
| C3 | ESC rev_b | the unconnected count: 499 was quoted as the count, and it is kicad-cli's cap | `499 unconnected` | **1,542 unconnected** | fab-checklist-v4/out/measure_esc.json (unconnected_pcbnew) |
| C4 | ESC rev_b | the 4 oz vendor rows: 'five different houses' was claimed; four houses publish an explicit 4 oz row | `five different houses` | **four houses carry an explicit 4 oz row** | v2v-fab-verify/REPORT.md |
| C5 | ESC rev_b | the area floor: 316 cm2 was published as the floor; it is 370 cm2 for today's BOM, and 316 needs the M5 lugs replaced | `316 cm2 floor` | **370 cm2 for today's BOM** | esc-compaction-verify/REPORT.md |
| C6 | drone-mech airframe | interference: the board carried 26 pairs; after the executed fixes 0 of the remaining pairs are genuine | `26 pairs` | **0 genuine pairs** | fab-dm-final/REPORT.md |
| C7 | ESC rev_b | 'change 3 packages' understates it: at 4 oz it is one impossible part (U201) plus 23 footprint edits that keep their netlist | `3 packages` | **one impossible part + 23 footprint edits** | esc-branch-4oz/REPORT.md |
| C8 | drone-mech airframe | 'delete 4 of 6 envelopes reaches zero' is not true: deletion alone reaches 2 pairs, and the resize is needed too | `delete 4 of 6 envelopes reaches zero` | **delete 4 + resize** | fab-dm-envelopes/REPORT.md |
| C9 | ESC rev_b | the ESC outline was quoted as the stroke-inclusive bounding box, not the Edge.Cuts centreline | `173.950 x 283.080` | **173.800 x 282.930** | fab-checklist-v4/out/measure_esc.json (edge_cuts_extent_mm) |
| C10 | ESC rev_b | pad rings below 0.200 mm at 4 oz: DRC reports 42 because it skips pads with duplicate numbers; the pad census finds 140 | `42 pad rings` | **140 pad rings** | fab-checklist-v4/out/measure_esc.json (pth_ring_below_020_count) |
| C11 | ESC rev_b | the 4 oz DRC improvement '413 -> 87' omitted 98 pad rings; renumbering the 1,160 duplicate-numbered pads takes the same rule file from 523 to 629 | `413 -> 87` | **523 -> 629** | fab-checklist-v4/out/drc_summary.json (total) |
| C12 | drone-arm main rev_b | the drill census sums: the package report's own column adds to 359; the census is 360 drills + 4 G85 slots = 364 hits | `359 drills` | **360 drills + 4 slots** | fab-checklist-v4/out/drill_census.json (0.drills) |
| C13 | Code-SDR V2 | 'the repo holds zero packages' is no longer true: commit 1a20bd6 added a 16-file bare-board package, and its bytes are this board's export | `the repo carries 0 package files` | **16 package files committed (1a20bd6)** | fab-checklist-v4/out/facts.json (facts.scan.cs_package) |

**How to read it.** C1 is the fiducial whose "FAIL" was manufactured by a raster floor. C2 is a
classification relabel: a microvia is a *drill class*, not a *span class*, and the four In1→In2 vias
are **buried**, which is worse for fabrication than blind. C3 is the cap. C4 counts vendor rows
instead of house names. C5 is the area floor, which needs a lug change to reach 316. C6 states that
the interference that remains after the executed fixes is not genuine. C7 replaces a package count
with the work that actually exists. C8 adds the qualifier the deletion claim was missing. C9–C13 were
found in this wave.

---

## 5. What is NOT known

Every item below is a question this sheet cannot answer from an artefact. The owner column is who
must answer it, not who is at fault.

| # | open question | owner | why it blocks |
|---:|---|---|---|
| **U1** | **The ESC A/B**: 2 oz, 4 oz + 23 footprint edits, or a written 4 oz waiver at 0.200 mm? | **owner (Darsh)** | no routing budget is meaningful until it is answered; the geometry is compliant at 2 oz today and non-compliant at 4 oz forever |
| **U2** | **Whether *any* heavy-copper house will build 0.200 mm track/space, 0.200 mm finished hole and 0.200 mm ring at 140 µm, in writing** | fab / CM (quote) | four houses publish an explicit 4 oz row and all of them sit above it; door C exists only if one signs |
| **U3** | **The ESC's real per-phase current** — 60 A per phase / 59.05 A per rail is repo-stated, never measured; **it is being measured in parallel**, and if it lands below 60 A the ESC's verdict changes with it: the 23.1 A rail, the 4 oz requirement, the mandatory heat spreader and the 382.71 cm² placement answer all scale with this one number | **EE, measurement in flight** | every copper width, hole size, thermal number and the A/B decision itself are functions of it. This is now the highest-leverage open number in the programme |
| **U4** | **Where BATP goes.** The recommended fix puts it on the "bare" B.Cu plane — where BATN's 5,106.6 mm² plane already sits | EE / next layout wave | the only routing fix on the table is unevidenced |
| **U5** | **The mapping of the 110 × 0.200 mm PTH pads to their footprints** | next PCB wave | decides whether the 23-footprint edit clears them; measured: 0 of the 110 are in the three packages once named |
| **U6** | **Whether the true 4 oz pad-bound population is 511, not 413** | independent instrument | changes the size of the 23-footprint job, not its existence |
| **U7** | **Via barrel plating: 25 µm or 38 µm?** | fab / CM | moves every barrel number by 1.5× and **flips BATN's verdict** |
| **U8** | **The heat spreader inside or outside the outline**, and whether any airframe bay has **735–911 cm²** | owner + airframe | the ESC's real packaging footprint is 2× the board |
| **U9** | **The 38.485 mm elevon station change** — accept the tail-interface change or not? | **owner** | the interference zero exists only at that station, on copies |
| **U10** | **The +97 g Boolean repair** of the 42_6 shell (4 solids, minimum separation 8.2592 mm) | next CAD wave | no stress, mass or interference number describes a manufacturable part until it lands |
| **U11** | **The pushrod re-draw** — compulsory after U9, and its 4.010114 mm³ of placeholder is the only thing the sweep still sees | next CAD wave | the last 2 "pairs" are this placeholder |
| **U12** | **The 41,775.81 mm³ phantom outboard loft** (3.09 %/side beyond the station table) | CAD author | the fixture around the moved plate is not real |
| **U13** | **MPN sourcing for Code-SDR: 373 of 373 BOM rows** | owner / purchasing | stops the **assembly** PO, not the etch order |
| **U14** | **A named assembly house's written fiducial requirement** (size, count, edge distance, pour gap) | CM | the 1.25 mm the 1.2505 mm is measured against is a design rule, not a quote |
| **U15** | **DFM etch compensation** on Code-SDR's 0.100/0.125 mm ring | fab | KiCad does not model it; the ring may grow or shrink post-compensation |
| **U16** | **Every impedance number** — two 2-D finite-difference solves, no measurement; the coupon is designed and **not ordered** ($54.24 against the $60 cap, $0 committed) | owner (spend) | the coplanar-pour question is 43.6 Ω wide |
| **U17** | **Solder-mask dam width** between the 0.4–0.5 mm pitch pads on DA and ESC | fab | every board declares 0.05 mm; only the shop knows its yield |
| **U18** | **Panelisation cost and feasibility** for any board — no panel drawing, no quote | CM | a 1-up 284 mm ESC board is not a price |
| **U19** | **Who owns the U10 fan-out re-escape** (drone-arm 15 vias + the missing ESC command path are the same rip-up) | programme lead | it is the single largest remaining design task and it has no owner |
| **U20** | **Whether the Code-SDR 101.6 mm board should be re-cut to 100 mm** for the price tier, or paid for | owner (cost) | 1.7 mm of price class, not a process limit |
| **U21** | **Whether y is the airframe's vertical axis.** It is taken as up because the body of record is 158.328 mm tall against 372.425 mm of span and 640.000 mm of length | CAD author | if the up-axis is different, 649.84 cm² is a side projection and the plan area must be re-measured |
| **U22** | **What the three construction lofts are** (1,193.869 × 88.643 × 3,409.595 mm each) and whether they belong in the assembly export at all | CAD author | their shadow is 125,962 mm², so leaving them in would overstate the airframe's plan area by 2× |
| **U23** | **Which airframe revision is the orderable one** — no revision carries any executed fix | owner | the sheet can measure the design of record, not a revision that does not exist |
| **U24** | **Whether a fab cares that the committed package's `ProjectId` is `Code-SDR-V2` while an internal copy exports as `cs`** | CM | metadata only; named so nobody re-opens it as a defect |

---

## 6. The instruments behind these numbers

Five instruments in this programme produced plausible green numbers while being wrong, and two more
were caught in this wave. A reader deserves to know which numbers came from which tool, and which of
them were checked against a known-good case.

| measurement | instrument (file) | sanity check | status |
|---|---|---|---|
| layers, stackup, copper weight | `measure.py` stackup parser (pcbnew) | reproduces `AGENT_BOARD.md:34-41` on three boards; nested-block parse verified against a hand read | **checked** |
| min track | `measure.py` segment census | 500 segments at 0.200 on DA matches the programme's count; "2,306 tracks" is segments + vias | **checked** |
| min space | `kicad-cli` DRC with a 0.30 mm probe `.kicad_dru`, **3 repeats per board** (`space_repeat.py`) | all three land **exactly** on their own rule (0.1250 / 0.2000 / 0.1000) in every run; the pair count does not reproduce (515–517, 499, 508–512), so the minimum is charged and the count is a range | **checked, count explicitly not quotable** |
| min drill | `measure.py` via + pad drill census | reconciles with the drill package by hand identity (336+22+6−4 = 360) | **checked** |
| min annular ring | `measure.py` per-layer diameters | per-axis ring; `(min size − max drill)/2` invented 8 slot violations before it was fixed | **checked after a caught defect** |
| **the DRC annular check itself** | `kicad-cli` 9.0.7 | **FAILS**: it skips pads with duplicate numbers — measured by renumbering 1,160 pads (523 → 629). The 42 it reports is a **floor**; the measured population is 140 | **known-broken; quoted only as a floor** |
| non-through vias by span | `measure.py` (`GetViaType` + layer pair) | three independent readings agree on 15; the diameter gate sees 14 and is retired as a count | **checked** (the diameter gate is **not**) |
| **unconnected** | `pcbnew GetUnconnectedCount(False)` vs `kicad-cli` | **calibrated** on six boards of known count (`esc_cap_test.py`): pcbnew returns N at every N; kicad-cli floors at 499. pcbnew returns 2,196 on the zero-copper placement, so it is not capped at 1,542 | **checked against a known cap** |
| DRC counts | `kicad-cli pcb drc`, 10 runs re-executed | every `.kicad_dru` asserted to carry `(version 1)`; behaviour proved by the controlled 0.250/0.200 pair; all runs exit 0 | **checked, with the annular blind spot above** |
| drill/gerber census | `drill_census.py` (own Excellon parser) | both censuses reconcile to a hand identity; slots counted apart from drills; blind/buried recognised by `FileFunction` | **checked** |
| **is the repo package this board's?** | `cs_package_match.py` | every gerber and both Excellon files are byte-identical to an independent export once `CreationDate`, `ProjectId` and `G04` comments are stripped; `.gbrjob` differs only in those fields | **checked** |
| area / outline (PCB) | `pcbnew GetBoardPolygonOutlines().Area()` + Edge.Cuts extent | area agrees with a shoelace walk to 0.0000 on all three boards; the extent is the centreline, not the stroke-inclusive bbox | **checked** |
| **outline + plan area (airframe)** | `dm_geom.py` / `dm_plan_refine.py` / `dm_plan_parts2.py` | known-good controls: a 120 × 30 mm plan reproduces **3,600.01 of 3,600.00 mm²** and a Ø40 disc **1,254.60 of 1,256.64 mm²**; resolution convergence 0.011 %; `dm_plan_parts.py`'s index-keyed exclusion mis-selected 22 parts and is superseded | **checked, after a caught defect** |
| model integrity (solids) | `dm_geom.py` `BRepExtrema_DistShapeShape` + `measure.py` outline topology | 4 solids with six pairwise distances, all > 0; each board 1 loop 0 holes | **checked** |
| revision / finish | board title block + job file JSON | CS reads `2.1` in both; DA's board is empty while its package says `B` | **checked** |
| drone-mech interference | OCCT `BRepAlgoAPI` booleans (`fab-dm-final`) | independently reproduced to **1e-9** on 12 quantities | **checked by a second instrument** |
| ESC rail capacity | `av-esc-rail-wave/02_geom.py` max-flow | four controls (K1–K4) pass before any board number is quoted | **checked, with the controls named** |
| heat spreader area | thermal solve + area arithmetic | 1.67× the junction limit; 352–528 cm² at 250 W/m²K | **cited, not re-measured** |

**The five broken instruments, and where their fingerprints are:**

1. **An ASCII text probe missed a Unicode minus.**
2. **A threshold moved from 1.25 to 1.00 so a FAIL printed as PASS** — the Code-SDR fiducial. In this
   sheet the threshold keeps one value, quoted once, and the measured gap is 1.2505 mm.
3. **The no-HDI gate classified by drill DIAMETER** — column 7 is by **span**, and the 0.300 mm blind
   the diameter gate cannot see is named in the cell.
4. **A `.kicad_dru` without `(version 1)` is silently ignored** — §2.8 asserts the version line in
   every rule file and proves load by behaviour.
5. **A corridor tool counted foreign pads, invented B.Cu on a net with none, and printed PASS over
   its own −80 % FAIL** — the rail numbers here come from the replacement instrument.

**Two more caught in this wave, recorded because they are the same class:** the raster that read the
fiducial 1.22 (a quantisation floor quoted as a measurement) and the *index-keyed* solids exclusion
in `dm_plan_parts.py`, which measured the wrong population correctly. The second one is mine, in this
wave, and it is kept in the artefact list rather than deleted.

---

## 7. One line per board, unforgiving

**drone-arm main rev_b — NOT ORDERABLE.** *15 non-through vias* (11 blind + 4 buried, 14 at 0.100 mm)
in 5 blind/buried drill files; **0 of 15** survive conversion, so the fix is a U10 fan-out re-escape.
Behind it: no ESC command path (`U10.43–48` on 64 auto nets, no `J60–J66`), an empty revision, and a
repo whose only package is the rev_a board.

**ESC rev_b — NOT ORDERABLE.** *1,542 unconnected* (pcbnew, uncapped, calibrated) so there is nothing
to fabricate — and when there is, **4 oz cannot be built from these packages** (371 pad gaps at
0.2000 mm, 110 holes at 0.200 mm, 140 pad rings below 0.200 mm, no house publishing 0.200 mm at
140 µm) *and the rail carries 23.1 A of 59.05 A*, 2.6× short. The 370.12 cm² compaction must not be
ordered either: its phase corridor is 1.50–3.50 mm against 6.991 mm.

**Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today.** *0 errors, 0 unconnected, 1,215 holes*, a
frame-free package stamped `2.1` and **committed to the repo**, ENIG, closed corners. The blocking
number is **0 for the bare board**; nothing stops the etch order. Two quote lines, neither a redesign:
the 0.100–0.125 mm ring and the 0.100 mm track/space at 1 oz. **Assembly is not orderable**: 373/373
MPNs missing, and the repo board's fiducials sit at **1.2505 mm** against a 1.25 mm rule — a pass by
0.0005 mm that the evidence copy improves to 1.7505 mm.

**drone-mech airframe — NOT READY.** **6 genuine interference pairs** (1,250.769445 mm³) are in the
design of record. The zero is real and measured — 2 pairs / 4.010114 mm³, 100 % artefact — but it
lives on evidence copies at a **+38.485 mm** station change no revision carries, over a shell that is
**4 disjoint solids**. The blocker is not interference any more; it is that the fix was never
accepted into the design.

---

## 8. Charge summary, and what changed since v3

Counted from §1 by `check_report.py` (it parses the markdown table, re-derives every verdict from the
raw measurements, and exits non-zero on any disagreement):

| board | PASS | FAIL | WAIVED | counted cells | orderable |
|---|---:|---:|---:|---:|---|
| drone-arm main rev_b | 8 | 5 | 1 | 14 | **NO** |
| ESC rev_b | 6 | 8 | 0 | 14 | **NO** |
| Code-SDR V2 | 13 | 0 | 1 | 14 | **YES** |
| drone-mech airframe | 1 | 4 | 9 | 14 | **NO** |
| **all four** | **28** | **17** | **11** | **56** | **1 of 4** |

### What v4 changed

1. **The drone-mech outline cell is now an outline and a plan area** (§2.11): 372.425 × 158.328 ×
   640.000 mm and **649.84 cm²** for the body of record; 409.500 × 148.000 × 756.000 mm and
   **1,227.35 cm²** for the 513-part airframe, with the three construction lofts excluded by rule and
   named. The solids count moved to column 14, where it belongs.
2. **The ESC unconnected cell now names the tool, the cap and the proof** (§2.7): 1,542 from pcbnew,
   shown uncapped by calibration and by a 2,196 reading on a zero-copper copy of the same netlist;
   `kicad-cli`'s 499 shown to be a hard cap on six boards of known count.
3. **Column 15 is new**: one blocking number per board, derived by rule (§2.14).
4. **Column 14 is new**: model integrity — outline topology for a PCB, solids and pairwise
   separation for the airframe.
5. **13 BOARD CORRECTIONS with old and new side by side** (§4), each with a passing machine check.
   v3 filed none.
6. **The Code-SDR package cell is now true**: 16 files are committed, and §2.9 proves they are this
   board's export. v3 said the repo held zero packages; that became false mid-wave.
7. **The clearance-pair count was re-measured, not inherited**: three repeats per board
   (515/515/517, 499/499/499, 508/512/512), and the one 48 % outlier in the full run is explained
   (total violations include warnings and non-clearance items) rather than smoothed over.
8. **The NOT-KNOWN list is 24 items** (v3 had 20) and promotes the ESC per-phase current to U3: it is
   being measured in parallel and may change the ESC's entire verdict.
9. **Counts move from 24/17/11 (52 cells) to 28/17/11 (56 cells)** — four cells became PASS because
   they are now measured rather than unanswered (three model-integrity cells and the airframe's
   outline/area), and the FAIL count is unchanged.

---

## 9. Artefacts and reproduction

| file | what it is |
|---|---|
| `REPORT.md` | this sheet, built from `REPORT.template.md` by `build_report.py` |
| `measure.py` → `out/measure_{da_best,da_repo,esc,cs}.json` | every board quantity: stackup, tracks, vias by span, ring and drill histograms, PTH rings below 0.200 with owners, title block, Edge.Cuts extent, area, **outline loops/holes**, **net census**, unconnected |
| `drc_run.py` → `drc/*/drc.json`, `out/drc_summary.json` | **all 10 DRC runs**, each with its rule file's presence, `(version 1)` line and rule count |
| `space_repeat.py` → `out/space_repeat_v4.json` | three repeats of the 0.30 mm clearance probe per board: minimum stable, pair count not |
| `esc_cap_test.py` → `out/esc_cap_test.json` | the calibration: six boards of known count through both tools, plus the ESC, its zero-copper placement and the Code-SDR control |
| `drill_census.py` → `out/drill_census.json` | Excellon census for package7 and the CS export, with the hand identity checked |
| `cs_package_match.py` → `out/cs_package_match.json` | byte comparison of the repo's committed package against an independent export |
| `dm_geom.py` → `out/dm_geom.json` | airframe outline, solids, pairwise separations, plan-area passes at two deflections × three resolutions, plus three known-good controls |
| `dm_plan_refine.py` → `out/dm_plan_refine.json` | the perimeter-bias model, tested against the controls |
| `dm_plan_parts2.py` → `out/dm_plan_parts2.json` | parts vs construction solids by geometric rule, with each solid meshed immediately after its own bbox |
| `dm_plan_parts.py` | the superseded index-keyed attempt, kept as the record of a caught defect |
| `derive.py` → `out/{cells,facts,summary,corrections}.json`, `out/table.md`, `out/corrections.md` | the 56 cells with their rules, the blocking numbers, and the corrections table |
| `check_report.py` → `out/check_report.log` | re-derives all 56 verdicts, checks the blocking numbers, the corrections and the prose. **Exit code 0.** |
| `negative_test.py` → `out/checker_negative_test.log` | four deliberate corruptions, each must exit 1, and the restored file must hash identically |
| `boards/` | byte copies of the three boards (+ the repo original as a control) with each project's `.kicad_dru`, `fp-lib-table` and `CodeSDR.pretty` |
| `export_cs/` | the Code-SDR package exported for this sheet |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-checklist-v4
& "C:/Program Files/KiCad/9.0/bin/python.exe"   measure.py        # 4 boards
& "C:/Program Files/KiCad/9.0/bin/python.exe"   drc_run.py        # 10 DRC runs
& "C:/Program Files/KiCad/9.0/bin/python.exe"   space_repeat.py 3 # clearance-probe repeats
& "C:/Program Files/KiCad/9.0/bin/python.exe"   esc_cap_test.py   # cap calibration
& "C:/Program Files/Python312/python.exe"       drill_census.py `
      "E:/engineering-portfolio-audit/evidence/fab-da-package7/package" export_cs
& "C:/Program Files/Python312/python.exe"       cs_package_match.py
& "C:/Program Files/Python312/python.exe"       dm_geom.py          # ~6 min on the 64 MB assembly
& "C:/Program Files/Python312/python.exe"       dm_plan_refine.py
& "C:/Program Files/Python312/python.exe"       dm_plan_parts2.py
& "C:/Program Files/Python312/python.exe"       derive.py
& "C:/Program Files/Python312/python.exe"       build_report.py
& "C:/Program Files/Python312/python.exe"       check_report.py     # must exit 0
& "C:/Program Files/Python312/python.exe"       negative_test.py    # must report 4 of 4 caught
```

---

*One board, one truth. If a number here is not on a command or a file, it does not exist.*

---

## 10. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-checklist-v4 | THE MASTER CHECKLIST, 4 rows x 14 verdict cells + a blocking number + orderable =
| 56 verdict cells, every one a measured value with its source and a verdict DERIVED by predicate
| (derive.py); check_report.py re-derives all 56 from the raw JSON, exit 0, negative-tested
| (4 corruptions -> exit 1, restored file hash-identical).
| THE TWO v3 WEAK CELLS ARE FIXED.
| (1) drone-mech outline+area: measured from STEP, not answered with solids. Body of record 42_6 =
| 372.425 x 158.328 x 640.000 mm, plan 649.84 cm2; the 513-part airframe = 409.500 x 148.000 x
| 756.000 mm, plan 1,227.35 cm2, after excluding 3 construction lofts that each span the WHOLE model
| (1,193.869 x 88.643 x 3,409.595 mm) - quoting them would describe a 3.4 m aircraft that does not
| exist. Method validated on known shapes: 3,600.01 of 3,600.00 mm2 for a 120x30 rectangle, 0.011 %
| resolution convergence. Solidity moved to its own column: 4 solids, pairwise separation 8.2592-112.5616 mm.
| (2) ESC unconnected: 1,542, pcbnew GetUnconnectedCount(False), NOT at a cap - calibrated on six
| boards of known count (pcbnew returns N at every N), and pcbnew returns 2,196 on the zero-copper
| placement of the same netlist. kicad-cli floors at exactly 499. 1,542 of 2,316 required connections open.
| PASS/FAIL/WAIVED: drone-arm 8/5/1 - ESC 6/8/0 - Code-SDR 13/0/1 - drone-mech 1/4/9 = 28/17/11 (56 cells).
| BLOCKING NUMBERS (new column 15): drone-arm 15 non-through vias - ESC 1,542 unconnected -
| Code-SDR 0 for the bare board (assembly 373 missing MPNs) - drone-mech 6 genuine interference pairs.
| 13 BOARD CORRECTIONS filed with old and new side by side (the 8 requested + ESC outline, pad rings
| 42->140, DRC 523->629, drill census 359->360, and 'the repo holds 0 packages' -> 16 files committed
| in 1a20bd6 whose bytes are this board's export). v3 filed none.
| NOT-KNOWN: 24 items, U3 now the ESC's real per-phase current, being measured in parallel.
| ORDERABLE: Code-SDR YES (bare board); the other three NO.
```