# Master Pre-Fab Checklist — final form (v5, wave 12)

Four boards, one question: **can this be ordered today, from artefacts that exist today, as the
design describes it?** Every cell below is a measured value or an explicit PASS/FAIL/WAIVED with its
reason and its source. Nothing is blank, nothing is TBD.

- Input: `evidence/fab-checklist-v4/`. Output: `evidence/fab-checklist-v5/`.
- Method: assembly and correction of numbers already established. Two new controls were run because
  a v4 number could not be trusted as written (the fiducial existed on no board; the Edge_Cuts stroke
  was inferred from the wrong board) and one v4 "green" needed a negative control before it could be
  quoted (Code-SDR's 0-error DRC).
- Board state at HEAD this sheet describes: Code-SDR `fbf2eca` (377 footprints, 4 fiducials);
  drone-arm repo board (341 vias, 36 non-through); ESC rev_b as drawn; drone-mech 42_6 shell.

**Headline.** One of four boards is orderable: **Code-SDR V2**, bare board, today. Three are not, and
each one stops on a different number: drone-arm on **36 non-through vias**, ESC on
**1,536-1,542 unconnected**, drone-mech on **4 disjoint solids**.

---

## 0. The four v4 defects, fixed

### D1 — the fiducial "+0.0005 mm" was a claim about a board that had no fiducials
v4 wrote *"on the repo board the requirement is met by +0.0005 mm"*. **The repo board carried no
fiducial at all** at `1a20bd6`: 373 footprints, `FID` strings 0, `fiducial` properties 0. The 1.2505
figure described two evidence copies (`B1263807…`, `8EC5741A…`), not the board.

Verified on the blob in commit **HEAD = `fbf2eca`**, not on a working copy:

| check on `git show HEAD:hardware/v2/Code-SDR-V2.kicad_pcb` | measured |
|---|---|
| bytes | 5,572,908 |
| footprints | **377** (373 parts + 4 fiducials) |
| `Fiducial:Fiducial_1mm_Mask2mm` | **4** |
| refs | **FID1, FID2, FID3, FIDL_U63_U64** |
| revision | 2.1 |
| vias / track segments | 1,085 / 11,168 (unchanged by the edit) |

**Current gap, polygon-exact, edge→copper against the 1.25 mm requirement:** FID1 4.7843,
FID2 1.8462, FID3 2.9604, FIDL_U63_U64 **1.5005** mm. **Minimum 1.5005 mm = +0.2505 mm margin.**
No fiducial clears by 0.0005 mm; the tightest margin is +0.2505 and every other is ≥ +0.59.
The second, stricter convention (1.5 mm centre→copper) is also met by the local at 2.0005 mm.
Source: `fab-cs-fid-real/REPORT.md` §4, measured from the committed blob.

### D2 — Edge_Cuts stroke on Code-SDR is 0.100 mm, not 0.15
Read per shape from the board file: Code-SDR's 4 Edge.Cuts lines are each **0.100 mm**; drone-arm and
ESC are **0.150 mm** each. That is where 0.15 came from — it was generalised from the other two boards.

**The arithmetic is the proof:** 101.600 + 0.150 = 101.750 ≠ 101.700 (the measured bbox);
101.600 + **0.100** = **101.700** ✓. DA 140.000 + 0.150 = 140.150 ✓; ESC 173.800 + 0.150 = 173.950 ✓.

### D3 — the commit added 22 files, not 16
`git show --name-status 1a20bd6`:

| group | files |
|---|---|
| gerbers + job | 11 gerbers + `Code-SDR-V2-job.gbrjob` = **12** |
| Excellon | 2 `.drl` + 2 `drl_map.gbr` = **4** |
| assembly | BOM-flat.csv, BOM-grouped.csv, pos.csv = **3** |
| root | `README.md`, `MANIFEST.sha256`, `.gitattributes` = **3** |
| **total added** | **22** |

v4 counted the 16 fabrication outputs and silently dropped the 3 assembly CSVs and the 3 root files.
The fab tree at HEAD holds **22** files; the later `fbf2eca` modified **20** of them (it skipped
`.gitattributes` and the two BOM CSVs — fiducials do not enter the BOM).

### D4 — BOARD CORRECTION lines
v4 had none. This sheet carries **17** in §2, OLD → NEW, one named source per row, and two machine
checks per row (§5, checks 11a/11b): the OLD value must be gone from the rows, the NEW value must be
used outside the table.

---

## 1. The master table

Four rows, the 15 required columns. The last two are derived, not asserted: `orderable` is YES iff
the row has 0 FAIL cells, and `blocking` is the single number that stops the order — *for a NO row it
must occur verbatim in a FAIL cell* (check 3).

<!-- BEGIN TABLE -->
| board | layers | copper | min_track | min_space | min_drill | min_ring | nonthrough | unconnected | drc | package | revision | outline | finish | orderable | blocking |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.200 mm | 0.1250 mm | via 0.100 / PTH 0.200 | via 0.100 / PTH 0.150 | 36 = 26 blind + 10 buried / 341 | 0 (pcbnew, uncapped) | 0 own rules / 36 span gate | package7 only, 5 B/B files, SENDABLE NO | empty on board; 'B' on a copy | 140.000 x 100.000 mm = 140.00 cm2 | ENIG | **NO** | **36 non-through vias** |
| **ESC rev_b** | 4 (F/In1/In2/B) | 0.140 outer 4 oz / 0.0525 inner 1.5 oz | 0.200 mm (rule 0.250) | 0.2000 mm (rule 0.250) | via 0.300 / PTH 0.200 | via 0.150 / PTH 0.125; 140 below 0.200 | 0 of 1,990 vias | 1,536-1,542 (pcbnew, uncapped) | 523 reported / 621 fab-real | none | empty, no silk rev | 173.800 x 282.930 mm = 491.732 cm2 | ENIG | **NO** | **1,536-1,542 unconnected** |
| **Code-SDR V2** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.100 mm | 0.1000 mm | via 0.200 / PTH 0.200 | via 0.100 / PTH 0.150 | 0 of 1,085 vias | 0 (pcbnew and kicad-cli agree) | 222 warn / 0 error; fab-real 222 | 22 files at HEAD, 1,215 holes, rev 2.1 | 2.1 board = 2.1 job | 101.600 mm square = 103.2256 cm2 | ENIG | **YES** | **0 errors** |
| **drone-mech airframe** | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 holes | n/a: 0 plated holes | n/a: 0 vias | n/a: 0 nets | 0 genuine pairs on copies / 6 in the record; 4 solids | none: 0 drawings, 0 ply book | no revision carries the fix | 372.425 x 158.328 x 640.000 mm; 649.84 cm2 plan | n/a: no finish callout | **NO** | **4 disjoint solids** |

### 1.1 Verdict ledger (full value, reason, source)

| board | column | verdict | value | reason | source |
|---|---|---|---|---|---|
| drone-arm main rev_b | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured on the repo board copy | v5/out measure_da_repo.json copper_layers |
| drone-arm main rev_b | copper | **PASS** | 0.035 mm on all four layers = 1 oz (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) | stackup copper matches the declared 1 oz | measure_da_repo.json stackup_copper_mm |
| drone-arm main rev_b | min_track | **PASS** | 0.200 mm; width histogram 0.200 / 0.250 / 0.350 = 507 / 1,702 / 70 of 2,279 segments | 0.200 >= 0.100 (1 oz) | measure_da_repo.json min_track, track_width_hist |
| drone-arm main rev_b | min_space | **PASS** | 0.1250 mm minimum, identical in 2 runs (0.125 both); 509 and 512 pairs at the 0.30 mm probe floor, so the count is quoted as a range and never charged | 0.1250 >= 0.100 (1 oz); the pair count does not reproduce | v5/drc/da_space/drc_r1.json, drc_r2.json |
| drone-arm main rev_b | min_drill | **FAIL** | via 0.100 mm (33 of 341 vias) / PTH pad 0.200 mm | 0.100 < 0.200, so the board cannot be built without HDI | measure_da_repo.json min_via_drill, min_pth_drill |
| drone-arm main rev_b | min_ring | **WAIVED** | via ring 0.1000 x33, 0.1500 x21, 0.1750 x281, 0.2000 x6 / PTH min 0.150 mm at U41.17 and U40.33 (18 pads) | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line, not a redesign | measure_da_repo.json via_ring_hist, pth_ring_hist |
| drone-arm main rev_b | nonthrough | **FAIL** | 36 non-through vias = 26 blind + 10 buried of 341 (305 through); by declared type 33 microvia + 3 blind/buried; spans F.Cu-In1.Cu 14, F.Cu-In2.Cu 3, In1.Cu-B.Cu 4, In1.Cu-In2.Cu 10 (buried), In2.Cu-B.Cu 5 | 36 != 0; no non-HDI 4-layer house can drill or plate them | measure_da_repo.json vias_by_span, via_table, vias_by_declared_type |
| drone-arm main rev_b | unconnected | **PASS** | 0 pcbnew GetUnconnectedCount(False) and 0 kicad-cli; 438 of 438 required pad-to-pad connections are made. Not at a cap: the same netlist reads 2,196 on a zero-copper placement | pcbnew ratsnest 0, calibrated against the kicad-cli 499 cap on six boards | measure_da_repo.json unconnected_pcbnew; v5/drc/da_own/drc.json |
| drone-arm main rev_b | drc | **FAIL** | 0 violations at the board's own project rules; 36 at the no-HDI span gate (33 microvia_drill_out_of_range + 3 drill_out_of_range) on the same board with only the .kicad_dru changed. fab-real = 36 | the right rules for a no-HDI process are the span gate, and 36 items survive it | v5/drc/da_own/drc.json (0), v5/drc/da_span/drc.json (36) |
| drone-arm main rev_b | package | **FAIL** | package7 only: 5 blind/buried Excellon files carrying 15 holes, 360 drills + 4 slots = 364 hits, SENDABLE = NO; its census expects 336 vias / 15 non-through, i.e. the 15-via WORK board, not the 36-via repo board | carries blind/buried files, and it is not an export of the board that would ship | out/drill_census.json 0.per_file, expect; fab-da-package7/-job.gbrjob |
| drone-arm main rev_b | revision | **FAIL** | board title block empty ('' / '' / ''); package7 stamps 'B' on 19 carriers because title_block_rev_B.patch was applied to a COPY | no revision on the board itself; the package's 'B' describes a copy | measure_da_repo.json title_revision; package7 job file |
| drone-arm main rev_b | outline | **PASS** | 140.000 x 100.000 mm Edge.Cuts centreline (140.15 x 100.15 with its 0.150 mm stroke) = 140.00 cm2, 1-up, no rails, 1 closed loop 0 holes | polygon closes, area > 0, one piece | measure_da_repo.json edge_cuts_extent_mm, outline_area_cm2, outline_loops |
| drone-arm main rev_b | finish | **PASS** | ENIG (board stackup field and job file agree) | finish declared and consistent | measure_da_repo.json copper_finish |
| ESC rev_b | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured | out/measure_esc.json copper_layers |
| ESC rev_b | copper | **PASS** | 0.140 mm outer = 4 oz / 0.0525 mm inner = 1.5 oz (F.Cu 0.1400, In1.Cu 0.0525, In2.Cu 0.0525, B.Cu 0.1400) | stackup matches the declared heavy-copper build | out/measure_esc.json stackup_copper_mm |
| ESC rev_b | min_track | **FAIL** | 0.200 mm; 4 segments at exactly 0.200 of 154 | 0.200 < 0.250 required at 4 oz | out/measure_esc.json min_track |
| ESC rev_b | min_space | **FAIL** | 0.2000 mm minimum, identical in 3 runs; 499 pairs at the 0.30 mm probe floor | 0.2000 < 0.250 required at 4 oz | drc/esc_space/drc.json; out/space_repeat_v4.json |
| ESC rev_b | min_drill | **FAIL** | via 0.300 mm (min of 1,990 vias) / PTH pad 0.200 mm; 110 of 223 PTH pads sit below the 0.300 finished-hole floor | 0.200 < 0.300 finished-hole floor at 4 oz | out/measure_esc.json min_via_drill, pth_drill_hist |
| ESC rev_b | min_ring | **FAIL** | via ring 0.1500 x16, 0.1750 x12, 0.2000 x1,962 / PTH min 0.125 mm at U204.11; 140 PTH pads below the 0.200 mm 4 oz floor (DRC reports 42 because it skips duplicate-numbered pads) | 0.125 < 0.200 published 4 oz floor and 140 pads are under it | out/measure_esc.json via_ring_hist, pth_ring_below_020_count; esc-drc-resolve pad_ring_census |
| ESC rev_b | nonthrough | **PASS** | 0 = 0 blind + 0 buried of 1,990 vias; all 1,990 are F.Cu-B.Cu through | no non-through span on the board | out/measure_esc.json vias_by_span |
| ESC rev_b | unconnected | **FAIL** | 1,536-1,542 unconnected (pcbnew, uncapped: 1,542 on the base board, 1,536 after the rail repour, -6); kicad-cli floors at exactly 499 on six calibration boards of known count, so the old 499 was the tool's cap | 1,536 of 2,316 required connections are open; there is nothing to fabricate yet | out/measure_esc.json unconnected_pcbnew; esc-rail-repour REPORT 2.1; out/esc_cap_test.json |
| ESC rev_b | drc | **FAIL** | 523 reported at 4 oz / 0.250 = 413 footprint-bound (371 pad-pad at exactly 0.200 + 42 PTH rings) + 110 copper-bound (28 via annular, 16 via_diameter, 16 via_dangling, 24 track-track, 19 pad-track, 4 track_width, 3 zone neck); fab-real 621 = 523 + 98 pad rings KiCad cannot report; 631 with --all-track-errors; 16 at the board's own project rules (all via_dangling), which is why 'own rules' is not the gate here | 523 and 621 are both non-zero at the weight the board is drawn for; 621 is the count a fabricator would reject | esc-drc-resolve/REPORT.md rowsets, 413_items.csv, 110_items.csv; out/drc_summary.json |
| ESC rev_b | package | **FAIL** | none: 0 gerber / drill / job files under hardware/esc | no package exists | facts.json facts.scan.esc_package |
| ESC rev_b | revision | **FAIL** | title block '' and no silkscreen revision text anywhere on the board | no revision stamp | out/measure_esc.json title_revision |
| ESC rev_b | outline | **PASS** | 173.800 x 282.930 mm Edge.Cuts centreline (173.95 x 283.08 with its 0.150 mm stroke) = 491.732 cm2, 1-up, no rails, 1 loop 0 holes | polygon closes, area > 0 | out/measure_esc.json edge_cuts_extent_mm, outline_area_cm2 |
| ESC rev_b | finish | **PASS** | ENIG (board field and job file agree) | finish declared | out/measure_esc.json copper_finish |
| Code-SDR V2 | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured | out/measure_cs.json copper_layers |
| Code-SDR V2 | copper | **PASS** | 0.035 mm on all four layers = 1 oz | stackup matches the declared 1 oz | out/measure_cs.json stackup_copper_mm |
| Code-SDR V2 | min_track | **PASS** | 0.100 mm; 1,510 segments at exactly 0.100 of 11,168 | 0.100 >= 0.100 (1 oz) | out/measure_cs.json min_track |
| Code-SDR V2 | min_space | **PASS** | 0.1000 mm minimum, identical in 3 runs; 508-512 pairs at the 0.30 mm probe floor (the count does not reproduce and is not charged) | 0.1000 >= 0.100 (1 oz) | drc/cs_space/drc.json; out/space_repeat_v4.json |
| Code-SDR V2 | min_drill | **PASS** | via 0.200 mm (min of 1,085 vias) / PTH pad 0.200 mm | >= 0.200, no HDI | out/measure_cs.json min_via_drill, min_pth_drill |
| Code-SDR V2 | min_ring | **WAIVED** | via ring 0.1000 x53, 0.1250 x1,013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57; 94 PTH pads below 0.200 (96 with the 2 oblong slot pads, which the ring formula does not score) | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line (waiver W2), not a defect | out/measure_cs.json via_ring_hist, pth_ring_hist; v5/out/cs_padcheck.json |
| Code-SDR V2 | nonthrough | **PASS** | 0 = 0 blind + 0 buried of 1,085 vias; all F.Cu-B.Cu through | no non-through span | out/measure_cs.json vias_by_span |
| Code-SDR V2 | unconnected | **PASS** | 0 pcbnew and 0 kicad-cli; 1,093 of 1,093 required connections made; both tools far below their caps and in agreement | ratsnest 0 on two independent tools | out/measure_cs.json unconnected_pcbnew; fab-cs-fid-real REPORT 5 |
| Code-SDR V2 | drc | **PASS** | 0 errors / 222 warnings / 0 unconnected at the board's own rules plus its own .kicad_dru (199 lib_footprint_mismatch + 13 via_dangling + 10 track_dangling); fab-real = 222. Control: with all 316 duplicate-numbered pads renumbered on a copy the count is identical (222 total, 0 errors), so the annular blind spot that hides 98 rings on the ESC is empty here | 0 errors, and the invisibility defect that would hide rings is proved empty by a renumber control | fab-cs-fid-real REPORT 5 (222/0/0 before and after); v5/out/cs_drc_renum.json (222/0/0 renumbered) |
| Code-SDR V2 | package | **PASS** | 22 files at HEAD under hardware/v2/fab (12 gerber+job, 4 Excellon+drill map, 3 assembly CSV, 3 root); 1,215 holes = 1,213 drills + 2 G85 slots, 0 non-through, census reconciles; all 14 compared files byte-identical to an independent export once metadata is stripped; revision 2.1; 377 pos rows = 373 parts + the 4 fiducials | package exists in the repo, reconciles, has no blind/buried file, and its bytes are this board | git show --name-status 1a20bd6 (22); out/drill_census.json 1; out/cs_package_match.json |
| Code-SDR V2 | revision | **PASS** | board title block '2.1' and Code-SDR-V2-job.gbrjob Revision '2.1' | board and package agree | measure_cs.json title_revision; job file |
| Code-SDR V2 | outline | **PASS** | 101.600 x 101.600 mm Edge.Cuts centreline (101.70 with its 0.100 mm stroke: 101.6 + 0.100 = 101.70, which is the measured bbox) = 103.2256 cm2, 1-up, no rails, 1 loop 0 holes | polygon closes, area > 0, and the extent reconciles with the 0.100 stroke | measure_cs.json edge_cuts_extent_mm, edges_bbox_mm; board-file stroke read 0.1 on 4 lines |
| Code-SDR V2 | finish | **PASS** | ENIG (board field and job file agree) | finish declared | measure_cs.json copper_finish |
| drone-mech airframe | layers | **WAIVED** | n/a: 0 PCB files (0 board/gerber/drill/project files under repos/drone-mech against 205 STEP/brep) | a machined/composite airframe has no copper stackup | facts.json scan.drone_mech |
| drone-mech airframe | copper | **WAIVED** | n/a: 0 PCB files | no copper exists on this deliverable | facts.json scan.drone_mech |
| drone-mech airframe | min_track | **WAIVED** | n/a: 0 PCB files | no copper exists on this deliverable | facts.json scan.drone_mech |
| drone-mech airframe | min_space | **WAIVED** | n/a: 0 PCB files | no copper exists on this deliverable | facts.json scan.drone_mech |
| drone-mech airframe | min_drill | **WAIVED** | n/a: 0 PCB files, 0 holes | no drilled part on this deliverable | facts.json scan.drone_mech |
| drone-mech airframe | min_ring | **WAIVED** | n/a: 0 plated holes | no plating on this deliverable | facts.json scan.drone_mech |
| drone-mech airframe | nonthrough | **WAIVED** | n/a: 0 vias on 0 boards | no vias exist | facts.json scan.drone_mech |
| drone-mech airframe | unconnected | **WAIVED** | n/a: 0 nets on 0 boards | no electrical netlist exists | facts.json scan.drone_mech |
| drone-mech airframe | drc | **FAIL** | no PCB, so the gate is the interference + solid sweep: 0 genuine interference pairs after the executed fix (2 residual pairs = 4.010114 mm3, 100 % pushrod-placeholder artefact); the design of record still reads 8 pairs = 6 genuine (1,250.769445 mm3) because no revision carries the fix; and the 42_6 shell is 4 disjoint solids (minimum separation 8.2592 mm) | the measured zero lives on evidence copies, and 4 disjoint solids are not one manufacturable part | fab-dm-final/REPORT.md state_delivered/state_changed; out/dm_geom.json body.min_separations_mm |
| drone-mech airframe | package | **FAIL** | none: 205 STEP/brep, 0 drawings, 0 ply book, 0 revision; the executed change is 6 STEPs in evidence/, 0 in repos/ | no manufacturing package | facts.json scan; fab-dm-final/REPORT.md |
| drone-mech airframe | revision | **FAIL** | no revision carries the +38.485 mm elevon station change; the design of record is the 42_6 shell, 4 solids, 742,305.526 mm3 | the fix exists only on copies | out/dm_geom.json body.volume_mm3; fab-dm-final/REPORT.md |
| drone-mech airframe | outline | **PASS** | design of record 372.425 x 158.328 x 640.000 mm (span x height x length); plan (x-z) area 649.84 cm2 = 64,984 mm2, converged to 0.011 % between 0.10 and 0.05 mm/px against a 120 x 30 mm control that reproduces 3,600.01 of 3,600.00 mm2 | outline and plan area are measured from the geometry and converge | out/dm_geom.json, out/dm_plan_refine.json, out/dm_plan_parts2.json |
| drone-mech airframe | finish | **WAIVED** | n/a: no finish callout exists (0 drawings, 0 ply book); printed PLA core + CF/glass wrap is a MATERIAL answer, not a surface finish | surface finish is a bare-board or finish-spec parameter and neither exists here | facts.json scan (0 drawings); AGENT_BOARD.md:281-283 |

### 1.2 Tally, recomputed from the rows

| board | PASS | FAIL | WAIVED | cells | orderable | blocking number |
|---|---:|---:|---:|---:|---|---|
| drone-arm main rev_b | 7 | 5 | 1 | 13 | **NO** | **36 non-through vias** |
| ESC rev_b | 5 | 8 | 0 | 13 | **NO** | **1,536-1,542 unconnected** |
| Code-SDR V2 | 12 | 0 | 1 | 13 | **YES** | **0 errors** |
| drone-mech airframe | 1 | 3 | 9 | 13 | **NO** | **4 disjoint solids** |
| **all four** | **25** | **16** | **11** | **52** | 1 of 4 | — |
<!-- END TABLE -->

### 1.3 Row notes — what the corrections do to each row

**drone-arm.** The repo board is not the work board. The work board (`da_best`, the fan-out
experiment) carries 336 vias and 15 non-through; the **repo board carries 341 vias and 36 non-through**
(33 microvia + 3 blind/buried declared; 26 blind + 10 buried by layer pair, of which the ten
**In1.Cu→In2.Cu vias are buried, not blind** — a drill class is not a span class). Both DRC numbers
below come from the same board with only the `.kicad_dru` changed: **0 at its own rules, 36 at the
no-HDI span gate** (33 `microvia_drill_out_of_range` + 3 `drill_out_of_range`). Fab-real = 36, and the
coincidence with the span census is the check.

**ESC.** The board is drawn for 4 oz outer / 1.5 oz inner, and the current that requirement was sized
for is **43.5 A phase / 40 A bus**, not 60 A per phase. At that current the rail is **PASS at k=0.048
only** (47.1 A = 1.08× of 43.5 A) and **24.83 A, a FAIL at k=0.024** (0.57×) — one barrel-plating
convention separates a pass from a fail, so the rail verdict is quoted with its k. The DRC at 4 oz /
0.250 mm is **621 fab-real**, i.e. **523 reported** plus **98** pad rings KiCad cannot report; the
413 footprint-bound rows are 371 pad↔pad at exactly 0.200 mm plus 42 PTH rings, the **110** copper-bound
rows are routing and via geometry, and the **511** effective footprint-bound population is 371 + 140
pad rings from the pad census. Getting to 4 oz is **one impossible part (U201) + 23 footprint edits**,
not "3 packages", and **four houses** publish an explicit 4 oz row. The compaction answer is
**370 cm² for today's BOM** (316 needs the M5 lugs replaced). The airframe this ESC is sized for flies
at **~545-570 km/h**, not 720, and its real drag is **CdA 0.0034-0.0056 m², best 0.0042** — the two
old figures sit below the **0.002710 m²** friction floor and are physically impossible, which is why
every current number in this row moved with them.

**Code-SDR.** Orderable, bare board, today: 0 errors, 0 unconnected, 1,215 holes, revision 2.1 on
board and package, 22 files at HEAD, 4 fiducials whose tightest gap is 1.5005 mm. The one thing that
could have hidden a defect is the annular blind spot that under-reports 98 rings on the ESC, so it was
tested here: **renumbering all 316 duplicate-numbered pads on a copy leaves the count at 222 / 0
errors.** The zero is a true zero, not a skipped population.

**drone-mech.** The interference is solved: **0 genuine pairs** after the executed fixes, the 2
residual pairs being **4.010114 mm³** of pushrod placeholder, 100 % artefact. What is not solved is
that **the fix lives on copies** — the design of record still reads 8 pairs (6 genuine, 1,250.769445
mm³) — and that the shell is **4 disjoint solids**, which is why the blocking number moved from
interference to geometry. Deletion alone does not reach zero: **delete 4 + resize** is the change.

---

## 2. BOARD CORRECTIONS — 17 rows, old → new

Every row is re-executed by `check_fab.py`. A row whose OLD value survives in §1, or whose NEW value
appears nowhere outside this table, is a FAIL of the sheet.

<!-- BEGIN CORRECTIONS -->
| id | board | what was wrong | OLD | NEW | source |
|---|---|---|---|---|---|
| BC1 | ESC | the ESC was designed to 60 A per phase | `60 A per phase` | **43.5 A phase / 40 A bus** | verify-w9-adv/REPORT.md:63 (43.5 = 240 A pack / 6 channels / 0.92); esc-flip-current, esc-rail-repour |
| BC2 | ESC / airframe | two whole-aircraft CdA values were used that are below the friction floor, so they are not physical | `CdA 0.000693 and 0.0015 m2` | **CdA 0.0034-0.0056 m2, best 0.0042 (friction floor 0.002710)** | esc-cda-bound/REPORT.md:320-336; verify-w9-adv/REPORT.md:12 (floor 0.002710) |
| BC3 | airframe / ESC | the 720 km/h design point is not reachable with this power system | `720 km/h` | **~545-570 km/h on this power system** | verify-w9-adv/REPORT.md:77-78; esc-cda-bound/REPORT.md:371 |
| BC4 | ESC | 523 was quoted as the DRC total; it omits 98 pad rings KiCad cannot report | `523 reported as the total` | **621 FAB-REAL = 523 + 98 invisible pad rings; 413 footprint-bound (371 pad-pad at 0.200 + 42 PTH rings), 110 copper-bound, effective footprint-bound 511** | esc-drc-resolve/REPORT.md:26,336-346,372 |
| BC5 | ESC | 499 was quoted as the unconnected count; it is kicad-cli's cap | `499 unconnected` | **1,536-1,542 unconnected (pcbnew, uncapped)** | fab-checklist-v4/out/esc_cap_test.json; esc-rail-repour/REPORT.md:42 (1,542 -> 1,536) |
| BC6 | drone-arm | 15 non-through vias was a fan-out work-board artefact, not the repo board | `15 non-through vias` | **36 non-through on the repo board (33 microvia + 3 blind/buried; 26 blind + 10 buried by span, of 341 vias)** | fab-checklist-v4/out/measure_da_repo.json vias_by_span; verify-wave10-adv/final_answer.txt |
| BC7 | Code-SDR | the fiducial was charged as a 1.22 mm FAIL on a board that had no fiducials at all | `1.22 FAIL` | **4 fiducials on the committed board (HEAD fbf2eca), min gap 1.5005 mm = +0.2505** | fab-cs-fid-real/REPORT.md:14,132-141,237-249; git show HEAD:hardware/v2/Code-SDR-V2.kicad_pcb |
| BC8 | ESC | the 4 oz vendor survey over-counted houses | `five different houses` | **four houses carry an explicit 4 oz row** | v2v-fab-verify/REPORT.md |
| BC9 | ESC | the published area floor was 316 cm2 | `316 cm2 floor` | **370 cm2 for today's BOM (316 needs the M5 lugs replaced)** | esc-compaction-verify/REPORT.md |
| BC10 | drone-mech | 26 interference pairs was arithmetic over a subset of the pair set, not a verdict | `26 pairs` | **0 genuine pairs (2 residual pairs = 4.010114 mm3, 100 % artefact)** | fab-dm-final/REPORT.md state_changed |
| BC11 | drone-mech | 'delete 4 of 6 envelopes reaches zero' is short by one step | `delete 4 of 6 envelopes reaches zero` | **delete 4 + resize** | fab-dm-envelopes/REPORT.md |
| BC12 | drone-arm | the In1->In2 vias were labelled blind; by span they are buried (a drill class is not a span class) | `the four In1->In2 vias are blind` | **In1.Cu-In2.Cu vias are BURIED (repo board: 10 of them); classify by layer pair** | fab-checklist-v4/out/measure_da_repo.json via_table |
| BC13 | ESC | 'rail PASS' was a single number; it holds only at one barrel-plating convention | `rail PASS` | **PASS at k=0.048 only (47.1 A = 1.08x of 43.5 A); 24.83 A and FAIL (0.57x) at k=0.024** | esc-rail-repour/REPORT.md:45,283-285; esc-flip-current/REPORT.md:303 |
| BC14 | Code-SDR | the Edge_Cuts stroke was stated as 0.15 mm; 101.6 + 0.15 = 101.75, which is not the measured 101.70 | `0.15 mm stroke` | **0.100 mm stroke (101.6 + 0.100 = 101.70)** | board file: 4 Edge.Cuts shapes at (stroke (width 0.1)); v5/D1 arithmetic |
| BC15 | Code-SDR | the fab commit was counted as 16 files | `16 files committed` | **22 files committed by 1a20bd6** | git show --name-status 1a20bd6 |
| BC16 | ESC | '3 packages' understates the 4 oz work | `3 packages` | **one impossible part (U201) + 23 footprint edits** | esc-branch-4oz/REPORT.md |
| BC17 | ESC | the ESC outline was quoted stroke-inclusive | `173.950 x 283.080` | **173.800 x 282.930 (Edge.Cuts centreline)** | fab-checklist-v4/out/measure_esc.json edge_cuts_extent_mm |

**17 rows.** 13 are the list the owner required; BC14 and BC15 are defects this sheet
itself shipped in v4 (the 0.15 mm stroke and the 16-file count); BC16 and BC17 are
earlier v4 corrections that a shorter list would have silently dropped.
<!-- END CORRECTIONS -->

**How to read it.** BC4 is the shape of the mistake this programme keeps making: 523 is a real count
of a real population, and it is not the population that matters — 98 more rings are invisible to the
tool, 371 of the 413 are geometry no routing can touch, and the number a fabricator would reject with
is 621. BC6 is the same class in a different instrument: 15 was measured correctly, on the wrong
board. BC13 is the third: one convention gives a pass, the other gives a fail, and the honest row
prints both. BC14 and BC15 are this checklist's own errors, kept rather than quietly overwritten.

---

## 3. What is NOT known

13 open items. Each one is a question no artefact answers, with the owner who must answer it — not a
verdict left blank.

| # | open question | owner | why it blocks |
|---:|---|---|---|
| **N1** | **The ESC A/B**: 2 oz, 4 oz + 23 footprint edits, or a written 4 oz waiver at 0.200 mm? | owner | no routing budget is meaningful until it is answered; today's geometry is compliant at 2 oz and non-compliant at 4 oz |
| **N2** | Whether **any** heavy-copper house will build 0.200 mm track/space, 0.200 mm finished hole and 0.200 mm ring at 140 µm, **in writing** | fab / CM | four houses publish an explicit 4 oz row and all four sit above it; the waiver route exists only if one signs |
| **N3** | **Barrel plating wall: 25 µm or 38 µm?** | fab / CM | it is the k=0.024 vs k=0.048 question: 24.83 A (FAIL) vs 47.1 A (PASS) on the same copper |
| **N4** | **A measured CdA.** 0.0034-0.0056 is an analytical band with a 0.002710 floor; nothing was measured in a tunnel or in flight | owner / test | every current, every copper width and the whole 4 oz case scale linearly with it |
| **N5** | Whether the **370 cm² compaction** is orderable — its phase corridor is 1.50-3.50 mm against 6.991 mm required | next PCB wave | the smaller board is not a cheaper ESC until the corridor closes |
| **N6** | **Who owns the U10 fan-out re-escape**, and whether a no-HDI escape exists at all (six conversion trials cleared 0 of the 15 tested) | programme lead | it is the largest remaining design task on drone-arm and it has no owner |
| **N7** | **Which drone-arm package ships.** The only package on record (`package7`) carries 5 blind/buried drill files with **15** holes — it was exported from the 15-via work board, not the 36-via repo board | PCB wave | a package that is not an export of the shipped board is not a package |
| **N8** | Whether the **+38.485 mm elevon station change** is accepted into a revision | owner | the interference zero exists only at that station, on copies |
| **N9** | The **+97 g Boolean repair** of the 42_6 shell, and the **pushrod re-draw** that removes the last 4.010114 mm³ placeholder | next CAD wave | no stress, mass or interference number describes a manufacturable part until both land |
| **N10** | **MPN sourcing for Code-SDR: 373 of 373 BOM rows** | owner / purchasing | stops the assembly PO, not the etch order |
| **N11** | **A named assembly house's written fiducial requirement.** The 1.25 mm is the programme's own rule; 4 of the 9 prior fiducial sites survive an exact re-measure, and the 0.4 mm QFN (U10) has no compliant local site at all | CM | the 1.5005 mm passes a rule nobody has quoted back |
| **N12** | **Panelisation and price** for any board: no panel drawing, no quote. A 1-up 284 mm ESC board is not a price | CM | the checklist says "buildable", not "affordable" |
| **N13** | **Solder-mask dam width** between the 0.4-0.5 mm pitch pads on DA and ESC: every board declares 0.05 mm and only the shop knows its yield | fab | a declared dam is not a quoted capability |

What is **not** on this list any more, because it was answered: the ESC's real per-phase current
(43.5 A / 40 A bus), the CdA bound (0.0034-0.0056), the true unconnected count (pcbnew, uncapped), the
413-vs-511 pad population, and whether Code-SDR has fiducials (it has 4).

---

## 4. The instruments behind these numbers

Six instruments in this programme produced plausible green numbers while being wrong. They are named
first, because the numbers below are only worth what their controls are worth.

**The six.** (1) An ASCII text probe that missed a Unicode minus. (2) The Code-SDR fiducial chain: a
**raster** distance transform quoted a quantisation floor (1.22) as a measurement, and a threshold was
**moved from 1.25 to 1.00** so a FAIL printed as PASS. (3) The no-HDI gate classified vias by drill
**diameter** instead of span, so it could not see a 0.300 mm blind via — and it read 15 where the repo
board has 36. (4) A `.kicad_dru` without a `(version 1)` line is **silently ignored**, so a gate can
"pass" on rules that were never read. (5) A corridor tool counted foreign pads, invented B.Cu where a
net had none, and printed PASS over its own −80 % FAIL. (6) An index-keyed solids exclusion measured
the wrong population correctly.

**A seventh is a tool limit rather than a wrong instrument, and it caught this programme once:**
`kicad-cli`'s unconnected count **floors at exactly 499**. It is not a count; it is a cap.

| measurement | instrument | control | status |
|---|---|---|---|
| layers, stackup, copper weight | `measure.py` stackup parser (pcbnew 9.0.7) | reproduces `AGENT_BOARD.md:34-41` on three boards; nested-block parse hand-verified | checked |
| min track | `measure.py` segment census | 1,510 segments at 0.100 on CS; "11,168 tracks" is segments, not nets | checked |
| **min space** | `kicad-cli` DRC with a 0.30 mm probe `.kicad_dru`, 2-3 repeats per board | all repeats land **exactly** on their own rule (0.1250 / 0.2000 / 0.1000); the **pair count does not reproduce** (509/512, 499, 508-512), so the minimum is charged and the count is a range | checked, count not quotable |
| min drill | `measure.py` via + pad drill census | reconciles with the Excellon by hand identity (336+22+6−4 = 360) | checked |
| min annular ring | per-pad diameter census | the naive `(min size − max drill)/2` invented 8 slot violations before it was fixed; the 2 CS oblong pads are excluded by name | checked after a caught defect |
| non-through by span | `GetViaType` + layer pair | three independent readings agree on 36 for the repo board; the declared-type count (33+3) is reported beside it, never instead of it | checked |
| **unconnected** | `pcbnew GetUnconnectedCount(False)` vs `kicad-cli` | **calibrated on six boards of known count**: pcbnew returns N at every N, kicad-cli floors at 499; pcbnew returns 2,196 on a zero-copper placement, so 1,542 is not a cap | checked against a known cap |
| DRC counts | `kicad-cli pcb drc`, `(version 1)` asserted in every `.kicad_dru` | behaviour proved by a controlled 0.250/0.200 pair and by the DA own-rules/spangate pair (0 → 36, one variable) | checked, with the annular blind spot named |
| **the annular blind spot** | **v5 negative control**: renumber all 316 duplicate-numbered CS pads and re-run | count unchanged at **222 / 0 / 0**, so the CS zero is a true zero; on the ESC the same control moves 523 to **629** (+106: the 98 invisible rings plus 8 pad-pair items the skipped pads also hid) | new in v5 |
| ESC DRC populations | row-level set diff on a stable key | **413 ∪ 110 = 523** (common 413, gone 110, added 0), verified per row and not by subtracting totals | checked |
| is the repo package this board's? | `cs_package_match.py` byte compare | all 14 compared files byte-identical once `CreationDate`, `ProjectId` and `G04` are stripped | checked |
| **is the fiducial on the committed board?** | `git show HEAD:<board>` parsed as a text blob | 377 footprints / 4 fiducials / 4 refs / 4 `(clearance 1.5)` / gaps identical to the working file | new in v5 |
| **Edge_Cuts stroke** | per-shape `(stroke (width …))` read from the board file | 4/4 lines agree; arithmetic closes against the bbox on all three boards (0.100 / 0.150 / 0.150) | new in v5 |
| area / outline (PCB) | `GetBoardPolygonOutlines().Area()` + centreline extent | area agrees with a shoelace walk to 0.0000; the extent is the centreline, not the stroke-inclusive bbox | checked |
| outline + plan area (airframe) | `dm_geom.py` / `dm_plan_refine.py` / `dm_plan_parts2.py` | known-good controls: a 120 x 30 mm plan reproduces **3,600.01 of 3,600.00 mm²**; convergence 0.011 % | checked, after a caught defect |
| interference (airframe) | OCCT `BRepAlgoAPI` booleans | independently reproduced to **1e-9** on 12 quantities | checked by a second instrument |
| rail capacity | `av-esc-rail-wave/02_geom.py` max-flow + `esc-rail-repour` repour | four controls (K1-K4) pass before any board number is quoted; the repour is re-measured, not argued | checked, with the controls named |
| **row/summary consistency** | `check_fab.py` (12 checks, this directory) | re-derives the tally, the orderable flag, every blocking number and the DRC cells from the raw JSONs; 4 negative tests each force a non-zero exit | new in v5 |

---

## 5. The checker

`check_fab.py` (16 check entries, 12 numbered; exit 0 iff clean). It is not a prose linter: it re-reads
`rows.json`, `corrections.json`, the raw v4 measurement JSONs and the v5 DRC outputs, and it fails if
any summary contradicts its rows.

| # | check | what would make it fail |
|---:|---|---|
| 1 | coverage and vocabulary: 52 cells, 4 x 13, no blank, no TBD | a missing column, an empty reason, a verdict outside PASS/FAIL/WAIVED |
| 2 | `orderable` == (0 FAIL cells) | a row claimed YES with a FAIL in it |
| 3 | the blocking number occurs verbatim in a FAIL cell | a blocking number invented for the summary |
| 4 | the three REPORT blocks are byte-identical to the generator's output | any hand-edited table cell |
| 5 | the tally rows reproduce from `rows.json` | a summary count that drifted |
| 6 | drone-arm identities vs `measure_da_repo.json` | 341≠305+26+10, 36≠26+10, 36≠33+3, blind spans≠26, buried≠10 |
| 7 | ESC identities vs `measure_esc.json` | 413+110≠523, 523+98≠621, 371+42≠413, 371+140≠511, 110 decomposition≠110, 140≠census |
| 8 | Code-SDR identities | 1213+2≠1215, 1085+128+2≠1215, 373+4≠377, 22≠12+4+3+3, 101.6+0.100≠101.70 |
| 9 | drone-mech identities | 6+2≠8, a missing 4.010114 / 1,250.769445 / 4-solids citation |
| 10 | the DRC cells reproduce from `drc/*.json` | da_own≠0, da_span≠36, span types≠33+3, span gate≠the non-through count, CS renumbered≠222/0 |
| 11 | corrections: 11a OLD gone from rows, 11b NEW used outside §2, 11c 17 rows parse | an old figure left as a live claim, or a new figure that exists only inside the correction table |
| 12 | every WAIVED cell on a YES row is priced as a quote line | a waiver hiding a defect behind an orderable YES |

**Run records.** Real exit codes, not claims:

| run | what it did | exit |
|---|---|---|
| `build_report.py --inject` | rewrote the three marked blocks from `rows.json` + `corrections.json` | 0 |
| `check_fab.py` | 16 check entries (12 numbered, 3 sub-blocks of #4, 2 of #11), 0 failures | **0** |
| `negative_test.py` | 6 one-variable mutations, each run through `check_fab.py` as a subprocess | **0** (all 6 caught) |

The four mandatory mutations, plus two this sheet added because they were the holes that mattered:
(1) DA non-through **36 → 15**, the old work-board artefact — caught by check 6 *and* 11a; (2) ESC
**orderable NO → YES** while carrying 8 FAIL cells — caught by check 2; (3) an OLD figure re-introduced
as a live claim (**1.22 mm**) — caught by check 11a; (4) a **REPORT cell hand-edited** (1,536-1,542 →
499) — caught by check 4; (5) a **blocking number invented** (DA → "0 errors") — caught by check 3;
(6) the **NEW 621 used only inside the correction table** — caught by check 11b. Every mutated run
exited **1**; the unmutated run exits **0**. Logs: `out/check_report.log`,
`out/checker_negative_test.log`; mutated inputs under `out/neg/`.

---

## 6. Verdict — the five objective conditions, per board

The conditions are derived, not typed: `check_fab.py` recomputes each one from the row's own cells
(condition 1 from the DRC cell, 2 from unconnected, 3 from non-through + ring + model integrity,
4 from package + revision, 5 from 52/52 cells carrying a value, a verdict and a reason).

<!-- BEGIN CONDITIONS -->
| board | condition | verdict | blocking number |
|---|---|---|---|
| drone-arm main rev_b | 1 DRC-clean at the right rules | **FAIL** | 36 non-through vias |
| drone-arm main rev_b | 2 zero unconnected | **PASS** | — |
| drone-arm main rev_b | 3 zero geometry defects | **FAIL** | 36 non-through vias |
| drone-arm main rev_b | 4 validated package | **FAIL** | 36 non-through vias |
| drone-arm main rev_b | 5 no open checklist cell | **PASS** | — |
| ESC rev_b | 1 DRC-clean at the right rules | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b | 2 zero unconnected | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b | 3 zero geometry defects | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b | 4 validated package | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b | 5 no open checklist cell | **PASS** | — |
| Code-SDR V2 | 1 DRC-clean at the right rules | **PASS** | — |
| Code-SDR V2 | 2 zero unconnected | **PASS** | — |
| Code-SDR V2 | 3 zero geometry defects | **PASS** | — |
| Code-SDR V2 | 4 validated package | **PASS** | — |
| Code-SDR V2 | 5 no open checklist cell | **PASS** | — |
| drone-mech airframe | 1 DRC-clean at the right rules | **FAIL** | 4 disjoint solids |
| drone-mech airframe | 2 zero unconnected | **PASS** | — |
| drone-mech airframe | 3 zero geometry defects | **FAIL** | 4 disjoint solids |
| drone-mech airframe | 4 validated package | **FAIL** | 4 disjoint solids |
| drone-mech airframe | 5 no open checklist cell | **PASS** | — |
<!-- END CONDITIONS -->

**In one line each.**

- **drone-arm main rev_b — NOT ORDERABLE.** 2 of 5. *36 non-through vias* (33 at 0.100 mm) in 5
  blind/buried drill files: no non-HDI 4-layer house can drill or plate them, a KiCad conversion
  cleared 0 of the 15 vias that were tried, and the only package on record describes the 15-via work
  board instead. DRC is 0 at its own rules and 36 at the rules the process actually has.
- **ESC rev_b — NOT ORDERABLE.** 1 of 5. *1,536-1,542 unconnected*: 1,536 of 2,316 required
  connections are open, so there is nothing to fabricate. When there is, the drawn 4 oz geometry is
  621 fab-real defects and the rail passes 43.5 A only at k=0.048.
- **Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today.** 5 of 5. *0 errors*: 0 DRC errors, 0
  unconnected on two tools, 0 non-through, 1,215 holes reconciled, 22 committed package files, rev
  2.1 on board and package, 4 fiducials at 1.5005 mm. Two quote lines, neither a defect: the
  0.100-0.125 mm ring (W2) and the 0.100 mm track/space at 1 oz. Assembly is not orderable: 373/373
  MPNs missing.
- **drone-mech airframe — NOT READY.** 2 of 5. *4 disjoint solids*: the interference is at 0 genuine
  pairs after the executed fixes, but that zero lives on copies no revision carries, the shell is 4
  separated solids (min 8.2592 mm) needing a +97 g Boolean repair, and there is no drawing, ply book
  or manufacturing package.

---

## 7. Evidence in this directory

```
REPORT.md            this sheet
rows.json            the 52 cells: value, verdict, reason, source (+ solid integrity)
corrections.json     17 BOARD CORRECTION rows + the two machine checks each
build_report.py      generates the three marked blocks; --inject rewrites them in place
check_fab.py         16 check entries (12 numbered); exit 0 iff nothing contradicts a row
negative_test.py     6 mutations, each must make the checker exit non-zero
cs_padcheck.py       CS duplicate-pad / ring census
cs_drc_renum.py      CS negative control: 316 pads renumbered, DRC re-run
out/                 auto_sections.md, cs_padcheck.json, cs_drc_renum.json,
                     check_report.log, checker_negative_test.log, neg/ (mutated inputs)
drc/da_own/          drone-arm repo board, own project rules   -> 0
drc/da_span/         same board, no-HDI span gate (.kicad_dru) -> 36 (33 microvia + 3 drill)
drc/da_space/        min-space probe at a 0.30 mm floor, 2 runs -> 0.1250 mm
drc/cs_renum/        Code-SDR copy with all pad numbers made unique -> 222 / 0 / 0
```

No repo was written: boards were copied into this directory before any tool touched them, and the
`Code-SDR` working tree is clean at `fbf2eca`.