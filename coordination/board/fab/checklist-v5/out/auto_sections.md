| board | layers | copper | min_track | min_space | min_drill | min_ring | nonthrough | unconnected | drc | package | revision | outline | finish | orderable | blocking |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.200 mm | 0.1250 mm | via 0.100 / PTH 0.200 | via 0.100 / PTH 0.150 | 36 = 26 blind + 10 buried / 341 | 0 (pcbnew, uncapped) | 0 own rules / 36 span gate | package7 only, 5 B/B files, SENDABLE NO | empty on board; 'B' on a copy | 140.000 x 100.000 mm = 140.00 cm2 | ENIG | **NO** | **36 non-through vias** |
| **ESC rev_b** | 4 (F/In1/In2/B) | 0.140 outer 4 oz / 0.0525 inner 1.5 oz | 0.200 mm (rule 0.250) | 0.2000 mm (rule 0.250) | via 0.300 / PTH 0.200 | via 0.150 / PTH 0.125; 140 below 0.200 | 0 of 1,990 vias | 1,536-1,542 (pcbnew, uncapped) | 523 reported / 621 fab-real | none | empty, no silk rev | 173.800 x 282.930 mm = 491.732 cm2 | ENIG | **NO** | **1,536-1,542 unconnected** |
| **Code-SDR V2** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.100 mm | 0.1000 mm | via 0.200 / PTH 0.200 | via 0.100 / PTH 0.150 | 0 of 1,085 vias | 0 (pcbnew and kicad-cli agree) | 222 warn / 0 error; fab-real 222 | 22 files at HEAD, 1,215 holes, rev 2.1 | 2.1 board = 2.1 job | 101.600 sq mm = 103.2256 cm2 | ENIG | **YES** | **0 errors** |
| **drone-mech airframe** | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 holes | n/a: 0 plated holes | n/a: 0 vias | n/a: 0 nets | 0 genuine pairs on copies / 6 in the record; 4 solids | none: 0 drawings, 0 ply book | no revision carries the fix | 372.425 x 158.328 x 640.000 mm; 649.84 cm2 plan | n/a: no finish callout | **NO** | **4 disjoint solids** |

### 1.1 Verdict ledger (full value, reason, source)

| board | column | verdict | value | reason | source |
|---|---|---|---|---|---|
| drone-arm main rev_b | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured on the repo board copy | v5/out measure_da_repo.json copper_layers |
| drone-arm main rev_b | copper | **PASS** | 0.035 mm on all four layers = 1 oz (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) | stackup copper matches the declared 1 oz | measure_da_repo.json stackup_copper_mm |
| drone-arm main rev_b | min_track | **PASS** | 0.200 mm; 479 segments at the minimum, width histogram 0.200 / 0.250 / 0.350 = 507 / 1,702 / 70 of 2,279 | 0.200 >= 0.100 (1 oz) | measure_da_repo.json min_track, track_width_hist |
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
| ESC rev_b | drc | **FAIL** | 523 reported at 4 oz / 0.250 = 413 footprint-bound (371 pad-pad at exactly 0.200 + 42 PTH rings) + 110 copper-bound (28 via annular, 16 via_diameter, 16 via_dangling, 24 track-track, 19 pad-track, 4 track_width, 3 zone neck); fab-real 621 = 523 + 98 pad rings KiCad cannot report; 631 with --all-track-errors | 523 and 621 are both non-zero at the weight the board is drawn for; 621 is the count a fabricator would reject | esc-drc-resolve/REPORT.md rowsets, 413_items.csv, 110_items.csv; out/drc_summary.json |
| ESC rev_b | package | **FAIL** | none: 0 gerber / drill / job files under hardware/esc | no package exists | facts.json facts.scan.esc_package |
| ESC rev_b | revision | **FAIL** | title block '' and no silkscreen revision text anywhere on the board | no revision stamp | out/measure_esc.json title_revision |
| ESC rev_b | outline | **PASS** | 173.800 x 282.930 mm Edge.Cuts centreline (173.95 x 283.08 with its 0.150 mm stroke) = 491.732 cm2, 1-up, no rails, 1 loop 0 holes | polygon closes, area > 0 | out/measure_esc.json edge_cuts_extent_mm, outline_area_cm2 |
| ESC rev_b | finish | **PASS** | ENIG (board field and job file agree) | finish declared | out/measure_esc.json copper_finish |
| Code-SDR V2 | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured | out/measure_cs.json copper_layers |
| Code-SDR V2 | copper | **PASS** | 0.035 mm on all four layers = 1 oz | stackup matches the declared 1 oz | out/measure_cs.json stackup_copper_mm |
| Code-SDR V2 | min_track | **PASS** | 0.100 mm; 1,510 segments at exactly 0.100 of 11,168 | 0.100 >= 0.100 (1 oz) | out/measure_cs.json min_track |
| Code-SDR V2 | min_space | **PASS** | 0.1000 mm minimum, identical in 3 runs; 508-512 pairs at the 0.30 mm probe floor (the count does not reproduce and is not charged) | 0.1000 >= 0.100 (1 oz) | drc/cs_space/drc.json; out/space_repeat_v4.json |
| Code-SDR V2 | min_drill | **PASS** | via 0.200 mm (min of 1,085 vias) / PTH pad 0.200 mm | >= 0.200, no HDI | out/measure_cs.json min_via_drill, min_pth_drill |
| Code-SDR V2 | min_ring | **WAIVED** | via ring 0.1000 x53, 0.1250 x1,013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57; 94 PTH pads below 0.200; the 2 oblong slot pads are not scored by the ring formula | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line (waiver W2), not a defect | out/measure_cs.json via_ring_hist, pth_ring_hist; v5/out/cs_padcheck.json |
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

### 1.3 The five objective conditions, per board

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

