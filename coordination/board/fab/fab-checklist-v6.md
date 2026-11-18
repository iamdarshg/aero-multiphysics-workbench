# Master Pre-Fab Checklist — v6 (wave 13)

Four boards, one question: **can this be ordered today, from artefacts that exist today, as the
design describes it?** Every cell below is a measured value or an explicit PASS/FAIL/WAIVED with its
reason and its source. Nothing is blank, nothing is TBD.

- Input: `evidence/fab-checklist-v5/` (413 lines, 17 BOARD CORRECTION rows, checker exit 0, 6/6
  mutations caught). Output: `evidence/fab-checklist-v6/`.
- Method: **documentation only, no new measurement.** Every number below already exists in a cited
  evidence directory; what this wave did is re-derive the cell values from that row-level data,
  carry the four-row table forward, and re-run a checker that now *computes* the ESC populations
  instead of repeating them.
- One derivation was re-run rather than carried (the ESC invisible pad rings, §1.3 and §5) because
  carrying it was the obvious way to be wrong.
- Board state this sheet describes: Code-SDR `fbf2eca` (377 footprints, 4 fiducials, 22-file
  package); drone-arm repo board (341 vias, 36 non-through); ESC rev_b **as drawn** (523) plus the
  post-shrink copy (253); drone-mech 42_6 shell (4 solids).

**Headline — one line per board, unchanged in count from v5 and changed in every number underneath.**

- **Code-SDR V2** is **ORDERABLE** today (bare board): 5 of 5 conditions, 0 errors, 0 unconnected,
  20/20 manifest entries. **Complete.**
- **drone-arm** is NOT: **36 non-through vias**, and **0 of the 36 are free** — none rides the copper
  the owed respin already re-lays.
- **ESC** is NOT: **1,536-1,542 unconnected**. The DRC work since v5 is real but it lives on a copy:
  **523 → 253 reported** with GONE 270 / ADDED 0, fab-real **351**.
- **drone-mech** is NOT: the blocker is **4 disjoint solids** (742,306.360 mm³), not interference —
  that is **0 genuine** pairs.

---

## 0. What changed since v5 — nine cells, one of them a trap

| # | cell | v5 said | v6 says | why |
|---|---|---|---|---|
| 1 | ESC `drc` | 523 reported / 621 fab-real | **253 reported / 351 fab-real** after the LQFP shrink, 523/621 as drawn | GONE 270, ADDED 0 by row identity; the fab-real equivalent is recomputed, not carried |
| 2 | ESC footprint-bound population | 413 (371 pad-gap + 42 PTH rings) | **155** = **113** pad-gap + 42 PTH rings | 258 of the 371 cleared; 113 cannot be shrunk at all |
| 3 | ESC `copper` (rail, cell 1 only) | 47.1 A at k=0.048 | **49.67 / 59.09 / 47.74 A** re-poured, 24.8 A at k=0.024, **23.1 A** as drawn | the re-pour is evidence, not the repo board's capacity |
| 4 | drone-mech `drc` + `solid_integrity` | "4 solids" as a count, volume 742,305.526 | **4 disjoint solids, 742,306.360 mm³, 84.2 % bulk fill, shell 42_6** | per-solid measurement, converged ε 1e-12 |
| 5 | drone-mech `revision` | 742,305.526 mm³ | **742,306.360 mm³** + file identity + sha256 | the body of record is now named, not described |
| 6 | drone-arm `nonthrough` | 33 microvia + 3 blind/buried | same counts, **plus 10 of 36 declared types contradict their layer pair** | declared type is not a classification |
| 7 | drone-arm `nonthrough` | (no free-rider statement) | **free-rider 0 of 36** | no J60-J66 header, no 7th-channel nets, `/CAN_5V` = 0 vias |
| 8 | Code-SDR `package` | 14 compared files byte-identical | **20/20 match the committed MANIFEST.sha256** | the control is now against what was committed |
| 9 | ESC `min_ring` | 140 pads under the 4 oz floor | 140, **recomputed on the shrunken board** | the number is the same; the derivation is new, and that is the point |

**The trap in #1.** The invisible-ring population is the one number a total cannot see. v5 carried
98; the honest move was to re-derive it on the *shrunken* board, where 288 pads just got 0.050 mm
narrower. Re-running the census gives **140 PTH pads under 0.200 mm — identical to the pre-shrink
histogram**, because the 288 shrunken pads are SMD and the census skips pads with no hole by
construction (`pad_ring_census.py:22`). Had the census scored SMD pads by `min(size)/2`, the shrink
would have *added* 288 invisible items and **351 would be 639**. That is checked explicitly
(check 7: "the shrunken pads are outside the hole census") rather than assumed.

---

## 1. The master table

Four rows, the 13 required evidence columns plus two derived ones. `orderable` is YES iff the row has
0 FAIL cells, and `blocking` is the single number that stops the order — *for a NO row it must occur
verbatim in a FAIL cell* (check 3).

<!-- BEGIN TABLE -->
| board | layers | copper | min_track | min_space | min_drill | min_ring | nonthrough | unconnected | drc | package | revision | outline | finish | orderable | blocking |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.200 mm | 0.1250 mm | via 0.100 / PTH 0.200 | via 0.100 / PTH 0.150 | 36 = 26 blind + 10 buried / 341; 10 of 36 declared != span; free-rider 0 of 36 | 0 (pcbnew, uncapped) | 0 own rules / 36 span gate | package7 only, 5 B/B files, SENDABLE NO | empty on board; 'B' on a copy | 140.000 x 100.000 mm = 140.00 cm2 | ENIG | **NO** | **36 non-through vias** |
| **ESC rev_b** | 4 (F/In1/In2/B) | 0.140 outer 4 oz / 0.0525 inner 1.5 oz; rail 49.67/59.09/47.74 A EVIDENCE ONLY, 23.1 A drawn | 0.200 mm (rule 0.250) | 0.2000 mm (rule 0.250) | via 0.300 / PTH 0.200 | via 0.150 / PTH 0.125; 140 below 0.200 | 0 of 1,990 vias | 1,536-1,542 (pcbnew, uncapped) | 253 reported / 351 fab-real after the shrink; 523/621 as drawn | none | empty, no silk rev | 173.800 x 282.930 mm = 491.732 cm2 | ENIG | **NO** | **1,536-1,542 unconnected** |
| **Code-SDR V2** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.100 mm | 0.1000 mm | via 0.200 / PTH 0.200 | via 0.100 / PTH 0.150 | 0 of 1,085 vias | 0 (pcbnew and kicad-cli agree) | 222 warn / 0 error; fab-real 222 | 22 files at HEAD, 20/20 manifest, 1,215 holes, rev 2.1 | 2.1 board = 2.1 job | 101.600 mm square = 103.2256 cm2 | ENIG | **YES** | **0 errors** |
| **drone-mech airframe** | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 holes | n/a: 0 plated holes | n/a: 0 vias | n/a: 0 nets | 0 genuine pairs; 4 disjoint solids, 742,306.360 mm3 | none: 0 drawings, 0 ply book | no revision carries the fix | 372.425 x 158.328 x 640.000 mm; 649.84 cm2 plan | n/a: no finish callout | **NO** | **4 disjoint solids** |

### 1.1 Verdict ledger (full value, reason, source)

| board | column | verdict | value | reason | source |
|---|---|---|---|---|---|
| drone-arm main rev_b | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured on the repo board copy | fab-checklist-v4/out/measure_da_repo.json copper_layers |
| drone-arm main rev_b | copper | **PASS** | 0.035 mm on all four layers = 1 oz (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) | stackup copper matches the declared 1 oz | fab-checklist-v4/out/measure_da_repo.json stackup_copper_mm |
| drone-arm main rev_b | min_track | **PASS** | 0.200 mm; width histogram 0.200 / 0.250 / 0.350 = 507 / 1,702 / 70 of 2,279 segments | 0.200 >= 0.100 (1 oz) | measure_da_repo.json min_track, track_width_hist |
| drone-arm main rev_b | min_space | **PASS** | 0.1250 mm minimum, identical in 2 runs (0.125 both); 509 and 512 pairs at the 0.30 mm probe floor, so the count is quoted as a range and never charged | 0.1250 >= 0.100 (1 oz); the pair count does not reproduce | fab-checklist-v5/drc/da_space/drc_r1.json, drc_r2.json |
| drone-arm main rev_b | min_drill | **FAIL** | via 0.100 mm (33 of 341 vias) / PTH pad 0.200 mm | 0.100 < 0.200, so the board cannot be built without HDI | measure_da_repo.json min_via_drill, min_pth_drill |
| drone-arm main rev_b | min_ring | **WAIVED** | via ring 0.1000 x33, 0.1500 x21, 0.1750 x281, 0.2000 x6 / PTH min 0.150 mm at U41.17 and U40.33 (18 pads) | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line, not a redesign | measure_da_repo.json via_ring_hist, pth_ring_hist |
| drone-arm main rev_b | nonthrough | **FAIL** | 36 non-through vias = 26 blind + 10 buried of 341 (305 through); spans F.Cu-In1.Cu 14, F.Cu-In2.Cu 3, In1.Cu-B.Cu 4, In1.Cu-In2.Cu 10 (buried), In2.Cu-B.Cu 5; 10 of 36 declared types contradict their layer pair (29 span 2 copper layers, 7 span more), so the span is read from the layer pair; free-rider on the owed respin = 0 of 36, because this variant has no J60-J66 servo header and /CAN_5V carries 0 vias | 36 != 0; no non-HDI 4-layer house can drill or plate them, and none of the 36 sits on copper the respin re-lays | measure_da_repo.json vias_by_span, via_table; fab-da-census/via_census.json non_through_type_span_disagreements (10), nt_detail servo_header_pads (0); fab-da-census/tables.md |
| drone-arm main rev_b | unconnected | **PASS** | 0 pcbnew GetUnconnectedCount(False) and 0 kicad-cli; 438 of 438 required pad-to-pad connections are made. Not at a cap: the same netlist reads 2,196 on a zero-copper placement | pcbnew ratsnest 0, calibrated against the kicad-cli 499 cap on six boards | measure_da_repo.json unconnected_pcbnew; fab-checklist-v5/drc/da_own/drc.json |
| drone-arm main rev_b | drc | **FAIL** | 0 violations at the board's own project rules; 36 at the no-HDI span gate (33 microvia_drill_out_of_range + 3 drill_out_of_range) on the same board with only the .kicad_dru changed. fab-real = 36 | the right rules for a no-HDI process are the span gate, and 36 items survive it | fab-checklist-v5/drc/da_own/drc.json (0), fab-checklist-v5/drc/da_span/drc.json (36) |
| drone-arm main rev_b | package | **FAIL** | package7 only: 5 blind/buried Excellon files carrying 15 holes, 360 drills + 4 slots = 364 hits, SENDABLE = NO; its census expects 336 vias / 15 non-through, i.e. the 15-via WORK board, not the 36-via repo board | carries blind/buried files, and it is not an export of the board that would ship | fab-checklist-v5/out/drill_census.json 0.per_file, expect; fab-da-package7/-job.gbrjob |
| drone-arm main rev_b | revision | **FAIL** | board title block empty ('' / '' / ''); package7 stamps 'B' on 19 carriers because title_block_rev_B.patch was applied to a COPY | no revision on the board itself; the package's 'B' describes a copy | measure_da_repo.json title_revision; package7 job file |
| drone-arm main rev_b | outline | **PASS** | 140.000 x 100.000 mm Edge.Cuts centreline (140.15 x 100.15 with its 0.150 mm stroke) = 140.00 cm2, 1-up, no rails, 1 closed loop 0 holes | polygon closes, area > 0, one piece | measure_da_repo.json edge_cuts_extent_mm, outline_area_cm2, outline_loops |
| drone-arm main rev_b | finish | **PASS** | ENIG (board stackup field and job file agree) | finish declared and consistent | measure_da_repo.json copper_finish |
| ESC rev_b | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured | fab-checklist-v4/out/measure_esc.json copper_layers |
| ESC rev_b | copper | **PASS** | 0.140 mm outer = 4 oz / 0.0525 mm inner = 1.5 oz (F.Cu 0.1400, In1.Cu 0.0525, In2.Cu 0.0525, B.Cu 0.1400); RAIL, EVIDENCE ONLY: re-poured BATP 49.67 A / BATN 59.09 A / BATP_IN 47.74 A at k=0.048 / 20 K, and 24.8 A at k=0.024 — the repo board is still 23.1 A as drawn | stackup matches the declared heavy-copper build; the rail figures are labelled evidence-only, carry their k, and are not the repo board's capacity | measure_esc.json stackup_copper_mm; esc-rail-repour/22_numbers.json measured[] + controls C1-C7; esc-flip-current |
| ESC rev_b | min_track | **FAIL** | 0.200 mm; 4 segments at exactly 0.200 of 154 | 0.200 < 0.250 required at 4 oz | measure_esc.json min_track |
| ESC rev_b | min_space | **FAIL** | 0.2000 mm minimum, identical in 3 runs; 499 pairs at the 0.30 mm probe floor | 0.2000 < 0.250 required at 4 oz | fab-checklist-v5/drc/esc_space/drc.json; out/space_repeat_v4.json |
| ESC rev_b | min_drill | **FAIL** | via 0.300 mm (min of 1,990 vias) / PTH pad 0.200 mm; 110 of 223 PTH pads sit below the 0.300 finished-hole floor | 0.200 < 0.300 finished-hole floor at 4 oz | measure_esc.json min_via_drill, pth_drill_hist |
| ESC rev_b | min_ring | **FAIL** | via ring 0.1500 x16, 0.1750 x12, 0.2000 x1,962 / PTH min 0.125 mm at U204.11; 140 PTH pads below the 0.200 mm 4 oz floor, recomputed on the shrunken board and unchanged (DRC reports 42 of them because it skips duplicate-numbered pads; the 288 shrunken LQFP pads are SMD and sit outside the hole census) | 0.125 < 0.200 published 4 oz floor and 140 pads are under it | measure_esc.json via_ring_hist, pth_ring_below_020_count; esc-drc-resolve pad_ring_census; v6 derived/ring_census_shrink.json |
| ESC rev_b | nonthrough | **PASS** | 0 = 0 blind + 0 buried of 1,990 vias; all 1,990 are F.Cu-B.Cu through | no non-through span on the board | measure_esc.json vias_by_span |
| ESC rev_b | unconnected | **FAIL** | 1,536-1,542 unconnected (pcbnew, uncapped: 1,542 on the base board, 1,536 after the rail repour, -6); kicad-cli floors at exactly 499 on six calibration boards of known count, so the old 499 was the tool's cap | 1,536 of 2,316 required connections are open; there is nothing to fabricate yet | measure_esc.json unconnected_pcbnew; esc-rail-repour REPORT 2.1; out/esc_cap_test.json |
| ESC rev_b | drc | **FAIL** | 253 reported at 4 oz / 0.250 AFTER the LQFP pad shrink, against 523 as drawn on the repo board; row-level SET DIFF = GONE 270, ADDED 0 (258 pad-pad at 0.2000 + 12 pad-track at 0.2250, every gone row on the 6 STM32G431CBT6); 253 = 155 footprint-bound (113 pad-gap + 42 PTH rings) + 98 copper-bound; the 113 cannot be shrunk away and need a part change or a documented waiver: QFN-80 U201 RP2354B 75 gaps at 0.400 pitch need a 0.150 pad against a 0.200 terminal, USB-C J202/J203 GCT USB4105 38 gaps at 0.5/0.65/0.8 pitch need 0.250/0.400/0.550 against a 0.300 contact (28 via annular, 16 via_diameter, 16 via_dangling, 24 track-track, 7 pad-track, 4 track_width, 3 zone neck); FAB-REAL 351 = 253 + 98 pad rings KiCad cannot report, recomputed on the shrunken board as 140 PTH pads under 0.200 in the census - 42 reported | 253 reported and 351 fab-real are both non-zero at the weight the board is drawn for, and the shrink that produces 253 is executed on a copy, not on the repo board | esc-pad-shrink/runs/BASE/drc_base.json (523), runs/SHRINK/drc_shrink.json (253), setdiff.json (gone 270 / added 0); v6 derived/ring_census_shrink.json (140) minus 42 reported pad rings |
| ESC rev_b | package | **FAIL** | none: 0 gerber / drill / job files under hardware/esc | no package exists | facts.json facts.scan.esc_package |
| ESC rev_b | revision | **FAIL** | title block '' and no silkscreen revision text anywhere on the board | no revision stamp | measure_esc.json title_revision |
| ESC rev_b | outline | **PASS** | 173.800 x 282.930 mm Edge.Cuts centreline (173.95 x 283.08 with its 0.150 mm stroke) = 491.732 cm2, 1-up, no rails, 1 loop 0 holes | polygon closes, area > 0 | measure_esc.json edge_cuts_extent_mm, outline_area_cm2 |
| ESC rev_b | finish | **PASS** | ENIG (board field and job file agree) | finish declared | measure_esc.json copper_finish |
| Code-SDR V2 | layers | **PASS** | 4 copper (F.Cu / In1.Cu / In2.Cu / B.Cu) | 4 layers measured | measure_cs.json copper_layers |
| Code-SDR V2 | copper | **PASS** | 0.035 mm on all four layers = 1 oz | stackup matches the declared 1 oz | measure_cs.json stackup_copper_mm |
| Code-SDR V2 | min_track | **PASS** | 0.100 mm; 1,510 segments at exactly 0.100 of 11,168 | 0.100 >= 0.100 (1 oz) | measure_cs.json min_track |
| Code-SDR V2 | min_space | **PASS** | 0.1000 mm minimum, identical in 3 runs; 508-512 pairs at the 0.30 mm probe floor (the count does not reproduce and is not charged) | 0.1000 >= 0.100 (1 oz) | fab-checklist-v5/drc/cs_space/drc.json; out/space_repeat_v4.json |
| Code-SDR V2 | min_drill | **PASS** | via 0.200 mm (min of 1,085 vias) / PTH pad 0.200 mm | >= 0.200, no HDI | measure_cs.json min_via_drill, min_pth_drill |
| Code-SDR V2 | min_ring | **WAIVED** | via ring 0.1000 x53, 0.1250 x1,013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57; 94 PTH pads below 0.200 (96 with the 2 oblong slot pads, which the ring formula does not score) | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line (waiver W2), not a defect | measure_cs.json via_ring_hist, pth_ring_hist; fab-checklist-v5/out/cs_padcheck.json |
| Code-SDR V2 | nonthrough | **PASS** | 0 = 0 blind + 0 buried of 1,085 vias; all F.Cu-B.Cu through | no non-through span | measure_cs.json vias_by_span |
| Code-SDR V2 | unconnected | **PASS** | 0 pcbnew and 0 kicad-cli; 1,093 of 1,093 required connections made; both tools far below their caps and in agreement | ratsnest 0 on two independent tools | measure_cs.json unconnected_pcbnew; fab-cs-fid-real REPORT 5 |
| Code-SDR V2 | drc | **PASS** | 0 errors / 222 warnings / 0 unconnected at the board's own rules plus its own .kicad_dru (199 lib_footprint_mismatch + 13 via_dangling + 10 track_dangling); fab-real = 222. Control: with all 316 duplicate-numbered pads renumbered on a copy the count is identical (222 total, 0 errors), so the annular blind spot that hides 98 rings on the ESC is empty here | 0 errors, and the invisibility defect that would hide rings is proved empty by a renumber control | fab-cs-fid-real REPORT 5 (222/0/0 before and after); fab-checklist-v5/out/cs_drc_renum.json (222/0/0 renumbered) |
| Code-SDR V2 | package | **PASS** | 22 files at HEAD under hardware/v2/fab (12 gerber+job, 4 Excellon+drill map, 3 assembly CSV, 3 root); 20/20 files in git archive HEAD hardware/v2/fab match the committed MANIFEST.sha256, 0 mismatches; 1,215 holes = 1,213 drills + 2 G85 slots, 0 non-through, census reconciles; revision 2.1; 377 pos rows = 373 parts + the 4 fiducials | package exists in the repo, every one of its 20 manifest entries hashes to what was committed, it carries no blind/buried file, and it is an export of this board | verify-w9-adv/REPORT.md:118 (git archive vs MANIFEST.sha256, 20/20); fab-checklist-v5/out/drill_census.json 1; git show --name-status 1a20bd6 (22) |
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
| drone-mech airframe | drc | **FAIL** | no PCB, so the gate is the interference + solid sweep: 0 genuine interference pairs after the executed fix (2 residual pairs = 4.010114 mm3, 100 % pushrod-placeholder artefact); the design of record still reads 8 pairs = 6 genuine (1,250.769445 mm3) because no revision carries the fix; and the 42_6 shell is 4 disjoint solids (minimum separation 8.2592 mm) totalling 742,306.360 mm3, 4/4 valid, 0 free edges | interference is not the blocker any more (0 genuine); 4 disjoint solids are not one manufacturable part, and the measured zero lives on copies no revision carries | fab-dm-final/REPORT.md state_delivered/state_changed; body-source-sync/REPORT.md:68 (4 solids, converged volume); fab-checklist-v5/out/dm_geom.json body.min_separations_mm |
| drone-mech airframe | package | **FAIL** | none: 205 STEP/brep, 0 drawings, 0 ply book, 0 revision; the executed change is 6 STEPs in evidence/, 0 in repos/ | no manufacturing package | facts.json scan; fab-dm-final/REPORT.md |
| drone-mech airframe | revision | **FAIL** | no revision carries the +38.485 mm elevon station change; the design of record is the 42_6 shell, 4 solids, 742,306.360 mm3, file fuselage_battery_bay_shell_endpoint_relief_42_6.step (7,313,057 B, sha256 c4b81dc3...bc8ea4ec) | the fix exists only on copies | body-source-sync/REPORT.md:44-70 (file identity, 4 solids, converged volume); fab-dm-final/REPORT.md |
| drone-mech airframe | outline | **PASS** | design of record 372.425 x 158.328 x 640.000 mm (span x height x length); plan (x-z) area 649.84 cm2 = 64,984 mm2, converged to 0.011 % between 0.10 and 0.05 mm/px against a 120 x 30 mm control that reproduces 3,600.01 of 3,600.00 mm2 | outline and plan area are measured from the geometry and converge | fab-checklist-v5/out/dm_geom.json, dm_plan_refine.json, dm_plan_parts2.json |
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

**ESC — the DRC is now a set diff, and it is still not an order.** As drawn the board is **523
reported / 621 fab-real** = 523 + 98 invisible rings, decomposed as **413** footprint-bound (371
pad-pad at exactly 0.200 + 42 PTH rings) + **110** copper-bound, effective footprint-bound **511**
(371 + 140 pad rings). The executed shrink — 288 LQFP pads 0.300 → 0.250 on six STM32G431CBT6 — takes
it to **253 = 155 footprint-bound (113 pad-gap + 42 PTH rings) + 98 copper-bound**, and the row-level
set diff is **GONE 270, ADDED 0**: 258 pad-pad at 0.2000 and 12 pad-track at 0.2250, every one of
them on the LQFP family. Fab-real is **351**. The **113** that remain are not a routing problem and
not a shrink problem: the QFN-80 U201 (RP2354B) needs a 0.150 mm pad against a 0.200 mm terminal and
the 0.250 mm pattern floor forbids it, and the USB-C J202/J203 (GCT USB4105) needs 0.250/0.400/0.550
against a 0.300 mm contact. They need a part change or a written rule exception.

The rail, in cell 1 of this row only, is **EVIDENCE ONLY**: re-poured **BATP 49.67 A / BATN 59.09 A /
BATP_IN 47.74 A** at k=0.048 / 20 K (controls C1-C7 all pass in `22_numbers.json`), **24.8 A** at
k=0.024, against **23.1 A** as drawn on the repo board and a **47.1 A** = 1.08× target for the
**43.5 A** phase / **40 A bus** design current. Reaching 4 oz is still **one impossible part (U201) +
23 footprint edits**, **four houses** publish an explicit 4 oz row, and none publishes 0.200 mm
track/space at 140 µm. The compaction answer is still **370 cm²** for today's BOM, and the airframe
still flies at **~545-570 km/h** with **CdA 0.0034-0.0056 m²** (best **0.0042**) over the
**0.002710** m² friction floor.

**drone-mech — the blocker is geometry, and it now has a mass basis.** Interference is **0 genuine**
pairs after the executed fixes (2 residual pairs = **4.010114 mm³** of pushrod placeholder, 100 %
artefact); the design of record still reads 8 pairs = 6 genuine (**1,250.769445** mm³) because no
revision carries the fix. What stops the order is that the 42_6 shell is **4 disjoint solids** totalling
**742,306.360 mm³** at converged ε 1e-12 — per-solid 624,770.530 · 75,919.237 · 20,808.297 ·
20,808.297 — of which **84.2 %** is bulk fill (624,770.5 mm³, t_eff 11.34 mm) against 117,531.8 mm³
of 1.2 mm wall. A single manufactured part cannot be four disconnected bodies; **delete 4 + resize**
remains the change, and the +97 g Boolean repair is its prerequisite.

**Code-SDR — complete, and the package control got stricter.** 5 of 5 conditions. 0 DRC errors, 222
warnings (199 lib_footprint_mismatch + 13 via_dangling + 10 track_dangling), **20/20** files in
`git archive HEAD hardware/v2/fab` match the committed `MANIFEST.sha256`, **22 files** at HEAD, 1,215
holes = 1,213 drills + 2 G85 slots, revision 2.1 on board and job, **4 fiducials** (FID1 4.7843,
FID2 1.8462, FID3 2.9604, **FIDL_U63_U64 1.5005 mm = +0.2505**). The renumber control that proves the
zero is a true zero (316 pads renumbered → 222 / 0 / 0) is unchanged. Assembly is still not orderable:
373 of 373 BOM rows have no MPN.

**drone-arm — the number did not move and neither did the reason.** **36 non-through** vias of 341
(26 blind + 10 buried by span). **10 of the 36** have a declared type that contradicts their layer
pair (29 span 2 copper layers, 7 span more), so the span is read from the layer pair, never the
declaration. **Free-rider 0 of 36**: this variant has **no J60-J66** servo header, the six U10
7th-channel pads carry 0 vias, `/CAN_5V` reaches 2 pads and carries 0 vias of any type, and the net
family scan reads ESC 0 · PWM 0 · TELEM 0 · FAULT 0 · SERVO 0 of 175 nets. DRC is **0 at its own
rules** and **36 at the no-HDI span gate**. It needs real layout work, and there is no free ride.

---

## 2. BOARD CORRECTIONS — 26 rows, old → new

Every row is re-executed by `check_fab.py`. A row whose OLD value survives in §1, or whose NEW value
appears nowhere outside this table, is a FAIL of the sheet.

<!-- BEGIN CORRECTIONS -->
| id | board | what was wrong | OLD | NEW | source |
|---|---|---|---|---|---|
| BC1 | ESC | the ESC was designed to 60 A per phase | `60 A per phase` | **43.5 A phase / 40 A bus** | verify-w9-adv/REPORT.md:63 (43.5 = 240 A pack / 6 channels / 0.92); esc-flip-current, esc-rail-repour |
| BC2 | ESC / airframe | two whole-aircraft CdA values were used that are below the friction floor, so they are not physical | `CdA 0.000693 and 0.0015 m2` | **CdA 0.0034-0.0056 m2, best 0.0042 (friction floor 0.002710)** | esc-cda-bound/REPORT.md:320-336; verify-w9-adv/REPORT.md:12 (floor 0.002710) |
| BC3 | airframe / ESC | the 720 km/h design point is not reachable with this power system | `720 km/h` | **~545-570 km/h on this power system** | verify-w9-adv/REPORT.md:77-78; esc-cda-bound/REPORT.md:371 |
| BC4 | ESC | 523 was quoted as the DRC total; it omits the pad rings KiCad cannot report | `523 reported as the total` | **fab-real = reported + invisible pad rings; as drawn 621 = 523 + 98, footprint-bound 413 (371 pad-pad at 0.200 + 42 PTH rings), 110 copper-bound, effective footprint-bound 511** | esc-drc-resolve/REPORT.md:26,336-346,372 |
| BC5 | ESC | 499 was quoted as the unconnected count; it is kicad-cli's cap | `499 unconnected` | **1,536-1,542 unconnected (pcbnew, uncapped)** | fab-checklist-v4/out/esc_cap_test.json; esc-rail-repour/REPORT.md:42 (1,542 -> 1,536) |
| BC6 | drone-arm | 15 non-through vias was a fan-out work-board artefact, not the repo board | `15 non-through vias` | **36 non-through on the repo board (26 blind + 10 buried by span, of 341 vias)** | fab-checklist-v4/out/measure_da_repo.json vias_by_span; verify-wave10-adv/final_answer.txt |
| BC7 | Code-SDR | the fiducial was charged as a 1.22 mm FAIL on a board that had no fiducials at all | `1.22 FAIL` | **4 fiducials on the committed board (HEAD fbf2eca), min gap 1.5005 mm = +0.2505** | fab-cs-fid-real/REPORT.md:14,132-141,237-249; git show HEAD:hardware/v2/Code-SDR-V2.kicad_pcb |
| BC8 | ESC | the 4 oz vendor survey over-counted houses | `five different houses` | **four houses carry an explicit 4 oz row** | v2v-fab-verify/REPORT.md |
| BC9 | ESC | the published area floor was 316 cm2 | `316 cm2 floor` | **370 cm2 for today's BOM (316 needs the M5 lugs replaced)** | esc-compaction-verify/REPORT.md |
| BC10 | drone-mech | 26 interference pairs was arithmetic over a subset of the pair set, not a verdict | `26 pairs` | **0 genuine pairs (2 residual pairs = 4.010114 mm3, 100 % artefact)** | fab-dm-final/REPORT.md state_changed |
| BC11 | drone-mech | 'delete 4 of 6 envelopes reaches zero' is short by one step | `delete 4 of 6 envelopes reaches zero` | **delete 4 + resize** | fab-dm-envelopes/REPORT.md |
| BC12 | drone-arm | the In1->In2 vias were labelled blind; by span they are buried (a drill class is not a span class) | `the four In1->In2 vias are blind` | **In1.Cu-In2.Cu vias are BURIED (repo board: 10 of them); classify by layer pair** | fab-checklist-v4/out/measure_da_repo.json via_table |
| BC13 | ESC | 'rail PASS' was a single number; it holds only at one barrel-plating convention | `rail PASS` | **PASS only at k=0.048 (47.1 A = 1.08x of 43.5 A); 24.8 A and FAIL (0.57x) at k=0.024** | esc-rail-repour/REPORT.md:45,283-285; esc-flip-current/REPORT.md:303 |
| BC14 | Code-SDR | the Edge_Cuts stroke was stated as 0.15 mm; 101.6 + 0.15 = 101.75, which is not the measured 101.70 | `0.15 mm stroke` | **0.100 mm stroke (101.6 + 0.100 = 101.70)** | board file: 4 Edge.Cuts shapes at (stroke (width 0.1)); v5/D1 arithmetic |
| BC15 | Code-SDR | the fab commit was counted as 16 files | `16 files committed` | **22 files committed by 1a20bd6** | git show --name-status 1a20bd6 |
| BC16 | ESC | '3 packages' understates the 4 oz work | `3 packages` | **one impossible part (U201) + 23 footprint edits** | esc-branch-4oz/REPORT.md |
| BC17 | ESC | the ESC outline was quoted stroke-inclusive | `173.950 x 283.080` | **173.800 x 282.930 (Edge.Cuts centreline)** | fab-checklist-v4/out/measure_esc.json edge_cuts_extent_mm |
| BC18 | ESC | the post-shrink DRC was going to be reported as a before/after total, which is what this programme has been burned by twice on this board | `523 -> 253 as a total` | **row-level set diff GONE 270, ADDED 0; 253 = 155 footprint-bound + 98 copper-bound; fab-real 351 = 253 + 98 invisible pad rings** | esc-pad-shrink/setdiff.json (gone_rows 270, added_rows 0); runs/SHRINK/drc_shrink.json; v6 derived/ring_census_shrink.json |
| BC19 | ESC | the footprint-bound population was quoted at its pre-shrink size and never revised | `413 footprint-bound (371 pad-pad at 0.200 + 42 PTH rings)` | **155 footprint-bound = 113 pad-gap + 42 PTH rings after the shrink** | esc-pad-shrink/setdiff.json gone by type; runs/SHRINK/drc_shrink.json annular_width rows (70) minus the 28 via rings |
| BC20 | ESC | the footprint gaps were treated as one population and one shrink width, as if all of them could be cleared by editing pads | `all pad-gap rows shrinkable` | **113 remain and cannot be shrunk: QFN-80 U201 RP2354B 75 + USB-C J202/J203 GCT USB4105 38, each needing a part change or a documented waiver** | esc-pad-shrink/groups.json (371 = 258 + 75 + 38), required_widths.json, REPORT.md section 3 (land-pattern floor); esc-gaps-113 scope |
| BC21 | ESC | the rail capacity was quoted as one as-drawn number and the re-poured geometry had no cell at all | `23.1 A quoted as the rail capacity` | **re-poured BATP 49.67 A / BATN 59.09 A / BATP_IN 47.74 A at k=0.048 / 20 K; 24.8 A at k=0.024; the repo board is still 23.1 A as drawn, so this is EVIDENCE ONLY** | esc-rail-repour/22_numbers.json measured[] (before/after per net) with controls C1-C7 all pass |
| BC22 | drone-mech | the body volume was quoted as one number, with no bulk/wall split and no per-solid identity, so '4 solids' was a count and not a measurement | `742,305.526 mm3 as one undifferentiated volume` | **742,306.360 mm3 converged, 4 solids at 624,770.530 + 75,919.237 + 20,808.297 + 20,808.297 mm3; 84.2 % is bulk fill (624,770.5) against 117,531.8 mm3 of 1.2 mm wall** | body-source-sync/REPORT.md:60-70 (probe_body_identity.py, converged_split.json, epsilon 1e-12); body-record-final/REPORT.md:275 |
| BC23 | drone-mech | the body of record was cited by name only, so no reader could tell which of the five registered candidates the numbers describe | `the 42_6 shell, unnamed file` | **fuselage_battery_bay_shell_endpoint_relief_42_6.step, 7,313,057 B, sha256 c4b81dc3...bc8ea4ec, 4 solids 4/4 valid 0 free edges** | body-source-sync/REPORT.md:55-70; body-record-final/REPORT.md:273-283 |
| BC24 | drone-arm | the declared via type was quoted beside the span as if the two agreed; for 10 of the 36 they do not, so a declared type is not a classification | `declared type 33 microvia + 3 blind/buried taken as the classification` | **10 of 36 declared types contradict their layer pair (29 span 2 copper layers, 7 span more); the span is read from the layer pair** | fab-da-census/via_census.json non_through_type_span_disagreements (10), non_through_adjacent_pair (29), non_through_span_gt2 (7); tables.md |
| BC25 | drone-arm | the 36 non-through vias were assumed to overlap the copper the owed respin already re-lays, i.e. that some were free | `36 vias could ride the respin` | **FREE = 0 of 36: this variant has no J60-J66 servo header, the 6 U10 7th-channel pads carry 0 vias, and /CAN_5V reaches 2 pads with 0 vias of any type** | fab-da-census/REPORT.md section 3 (free-rider test, net-family scan 0 matches of 175 nets); via_census.json nt_detail servo_header_pads |
| BC26 | Code-SDR | the package integrity control was a byte compare over the files a prior wave happened to export, not over what was committed | `14 compared files byte-identical to an independent export` | **20/20 files in git archive HEAD hardware/v2/fab match the committed MANIFEST.sha256, 0 mismatches** | verify-w9-adv/REPORT.md:118 (git archive <tree> | hash every file against MANIFEST.sha256) |

**26 rows.** BC1-BC17 are carried from v5 unchanged (13 the owner required, plus BC14 and
BC15 which v5 shipped as its own defects and BC16/BC17 which a shorter list would have
dropped). BC18-BC26 are new since v5. Two of them, BC21 and BC25, carry an empty
`absent_in_rows` on purpose: they add a state instead of retracting one, because 23.1 A is
still the repo board's capacity and no cell ever claimed a free-rider. Check 11d fails if
any other row goes silent that way.
<!-- END CORRECTIONS -->

**How to read it.** BC18-BC20 are the shape of the mistake this programme keeps making on the ESC:
523 was a real count of a real population and it was not the population that mattered, and the same
is true of 413 and of 371. BC21 is the discipline that goes with a repour: 49.67 A is a property of a
copy until someone commits it, so the cell prints the number and the "evidence only" label together,
next to the 23.1 A the repo actually has. BC22-BC23 are the drone-mech version: 742,306.360 mm³ is not
a bigger number than 742,305.526, it is the same body at a converged tolerance — the correction is
that the body now has an identity, a per-solid split and a bulk share. BC24-BC25 are the drone-arm
version: the declared via type was never a classification, and the respin was never going to absorb
any of the 36. BC26 is this sheet's own control getting stricter: a byte compare over 14 files a
prior wave happened to export is not the same statement as 20/20 against the committed manifest.

---

## 3. What is NOT known

18 open items. Each one is a question no artefact answers, with the owner who must answer it — not a
verdict left blank. N1-N13 carry from v5; N14-N18 are new and are consequences of this wave's numbers.

| # | open question | owner | why it blocks |
|---:|---|---|---|
| **N1** | **The ESC A/B**: 2 oz, 4 oz + 23 footprint edits, or a written 4 oz waiver at 0.200 mm? | owner | no routing budget is meaningful until it is answered; today's geometry is compliant at 2 oz and non-compliant at 4 oz |
| **N2** | Whether **any** heavy-copper house will build 0.200 mm track/space, 0.200 mm finished hole and 0.200 mm ring at 140 µm, **in writing** | fab / CM | four houses publish an explicit 4 oz row and all four sit above it; the waiver route exists only if one signs |
| **N3** | **Barrel plating wall: 25 µm or 38 µm?** | fab / CM | it is the k=0.024 vs k=0.048 question: 24.8 A (FAIL) vs 49.67 A (PASS) on the same copper |
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
| **N14** | **Does the 258-row shrink survive production etch tolerance?** The pad is 0.250 mm — *exactly* the 4 oz minimum pattern — and the resulting gap is *exactly* the 0.250 mm rule; a ±0.075 mm etch tolerance can still deliver a 0.175 mm gap | fab / CM | the 253 is cleared nominally, not demonstrably fab-real; this is a sign-off question, not a layout one |
| **N15** | **Is the shrink accepted into the repo board?** It is executed on `esc-pad-shrink/runs/SHRINK/`, not on `repos/drone-arm/.../esc_rev_b.kicad_pcb`, which still reads 523 | PCB wave | the row quotes 253 as the post-shrink state and 523 as the repo state; until it lands, the board a fabricator receives is the 523 one |
| **N16** | **The 8 pad-pair items hidden by duplicate pad numbers.** v5's renumber control on the *unshrunk* board read 629, i.e. 98 rings + 8 more; that control was **not** re-run on the shrunken board, so 351 carries the same ≤8 under-count as 621 | next PCB wave | a fab-real number with a known blind spot should name the blind spot |
| **N17** | **Part change or waiver for the 113?** No RP2354B package offers a 0.150 mm-land variant at 0.4 pitch, and the GCT USB4105 needs three widths; nobody has chosen, and nobody has quoted a waiver | owner / component engineering | this is the whole of the remaining ESC footprint work |
| **N18** | **The weld.** `dm-solid-weld` (wave 13, in flight) asks whether the 4 solids can become one valid watertight solid; as of this sheet there is no result, so the row keeps **4 disjoint solids** as its blocker | next CAD wave | if a weld is possible it is cheaper than a Boolean repair, and either way the row does not move until one lands |

What is **not** on this list any more, because it was answered: the ESC's real per-phase current
(43.5 A / 40 A bus), the CdA bound (0.0034-0.0056), the true unconnected count (pcbnew, uncapped), the
413-vs-511 pad population (now 155-vs-113 after the shrink), whether Code-SDR has fiducials (it has 4),
whether the ESC's 371 gaps could all be shrunk (258 could, 113 cannot), and whether any of drone-arm's
36 vias is free (none is).

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

**An eighth class, new in v6: the carried number.** A number that was right once and is quoted again
without re-running its instrument. The ESC's 98 invisible rings is exactly that shape, and it is the
number that would have been silently right-or-wrong by 288 items (§0). It was re-derived on the
shrunken board; the derivation is in `derived/ring_census_shrink.json` and check 7.

| measurement | instrument | control | status |
|---|---|---|---|
| layers, stackup, copper weight | `measure.py` stackup parser (pcbnew 9.0.7) | reproduces `AGENT_BOARD.md:34-41` on three boards; nested-block parse hand-verified | checked |
| min track | `measure.py` segment census | 1,510 segments at 0.100 on CS; "11,168 tracks" is segments, not nets | checked |
| **min space** | `kicad-cli` DRC with a 0.30 mm probe `.kicad_dru`, 2-3 repeats per board | all repeats land **exactly** on their own rule (0.1250 / 0.2000 / 0.1000); the **pair count does not reproduce** (509/512, 499, 508-512), so the minimum is charged and the count is a range | checked, count not quotable |
| min drill | `measure.py` via + pad drill census | reconciles with the Excellon by hand identity (336+22+6−4 = 360) | checked |
| min annular ring | per-pad diameter census | the naive `(min size − max drill)/2` invented 8 slot violations before it was fixed; the 2 CS oblong pads are excluded by name | checked after a caught defect |
| **ring census, post-shrink** | `pad_ring_census.py` re-run on `runs/SHRINK/esc_rev_b.kicad_pcb` | histogram **identical** to the pre-shrink board (140 under 0.200) *and* the script skips pads with no hole, so the 288 shrunken SMD pads cannot enter it; 11 PTH pads share ref+number, which is the mechanism behind the 98 | **new in v6** |
| non-through by span | `GetViaType` + layer pair | three independent readings agree on 36 for the repo board; the declared-type count is reported beside it and is now shown to disagree for **10 of 36** | checked, and the declared type is demoted |
| **unconnected** | `pcbnew GetUnconnectedCount(False)` vs `kicad-cli` | **calibrated on six boards of known count**: pcbnew returns N at every N, kicad-cli floors at 499; pcbnew returns 2,196 on a zero-copper placement, so 1,542 is not a cap | checked against a known cap |
| DRC counts | `kicad-cli pcb drc`, `(version 1)` asserted in every `.kicad_dru` | behaviour proved by a controlled 0.250/0.200 pair and by the DA own-rules/spangate pair (0 → 36, one variable) | checked, with the annular blind spot named |
| **the ESC set diff** | **row identity on the violation key, v6**: `setdiff.json` gone/added rows, then re-classified from the DRC's own item descriptions | **GONE 270, ADDED 0**; the 270 are 258 at 0.2000 + 12 at 0.2250, all clearance; the 113 remaining pad rows are read *back out of the DRC* (pad 113 / track 24 / pad-track 7 = 144) and agree with `371 − 258` from an independent file | **new in v6, two instruments agreeing** |
| **the annular blind spot** | v5 negative control: renumber all 316 duplicate-numbered CS pads and re-run | count unchanged at **222 / 0 / 0**, so the CS zero is a true zero; on the ESC the same control moves 523 to 629 (+106) | carried, with its un-rerun status named as N16 |
| is the repo package this board's? | `git archive HEAD hardware/v2/fab` vs `MANIFEST.sha256` | **20/20 match, 0 mismatches** (supersedes a 14-file compare against an independent export) | **new in v6** |
| **is the fiducial on the committed board?** | `git show HEAD:<board>` parsed as a text blob | 377 footprints / 4 fiducials / 4 refs / gaps identical to the working file | carried |
| Edge_Cuts stroke | per-shape `(stroke (width …))` read from the board file | 4/4 lines agree; arithmetic closes against the bbox on all three boards (0.100 / 0.150 / 0.150) | carried |
| area / outline (PCB) | `GetBoardPolygonOutlines().Area()` + centreline extent | area agrees with a shoelace walk to 0.0000; the extent is the centreline, not the stroke-inclusive bbox | checked |
| outline + plan area (airframe) | `dm_geom.py` / `dm_plan_refine.py` / `dm_plan_parts2.py` | known-good controls: a 120 x 30 mm plan reproduces **3,600.01 of 3,600.00 mm²**; convergence 0.011 % | checked, after a caught defect |
| **body volume + solid count** | OCP `BRepGProp` at ε 1e-12, per solid and as a compound | the per-solid sum and the compound reading agree to 4e-5 mm³ (742,306.35951 vs 742,306.35954); the **as-recorded** 742,305.526 is 0.833 mm³ lower, which is the integrator tolerance and is why the cell quotes the converged value; the repo's own `segmentation_manifest.json` agrees to 2e-10 mm³ | **new in v6** |
| interference (airframe) | OCCT `BRepAlgoAPI` booleans | independently reproduced to **1e-9** on 12 quantities | checked by a second instrument |
| rail capacity | `av-esc-rail-wave/02_geom.py` max-flow + `esc-rail-repour` repour | four controls (K1-K4) pass before any board number is quoted; the repour is re-measured, not argued; `22_numbers.json` re-runs C1-C7 (including the 23.08452 vs published 23.1) before reporting 49.67 | checked, with the controls named |
| **row/summary consistency** | `check_fab.py` (17 check entries, this directory) | re-derives the tally, the orderable flag, every blocking number, the ESC populations and the DRC cells from raw JSONs; 8 negative tests each force a non-zero exit | **rewritten in v6** |

---

## 5. The checker

`check_fab.py` (17 check entries, 12 numbered; exit 0 iff clean). It is not a prose linter: it re-reads
`rows.json`, `corrections.json`, the v4 measurement JSONs, the ESC base/shrink DRC pair, the set diff,
the gap grouping, the post-shrink ring census, the drone-arm via census and the drone-mech converged
split, and it fails if any summary contradicts its rows.

| # | check | what would make it fail |
|---:|---|---|
| 1 | coverage and vocabulary: 52 cells, 4 x 13, no blank, no TBD | a missing column, an empty reason, a verdict outside PASS/FAIL/WAIVED |
| 2 | `orderable` == (0 FAIL cells) | a row claimed YES with a FAIL in it |
| 3 | the blocking number occurs verbatim in a FAIL cell | a blocking number invented for the summary |
| 4 | the three REPORT blocks are byte-identical to the generator's output | any hand-edited table cell |
| 5 | the tally rows reproduce from `rows.json` | a summary count that drifted |
| 6 | drone-arm identities vs `measure_da_repo.json` + `via_census.json` | 341≠305+26+10, 36≠26+10, blind spans≠26, buried≠10, 10 disagreements≠10, 29+7≠36, a free-rider ≠ 0, or no J60/7th-channel net present |
| 7 | **ESC identities, derived**: 523/253, gone 270/added 0, 258+12, 371=258+75+38, 113=371−258 **and** = the DRC's own pad rows, 113+24+7=144, 155=113+42, 42=70−28, 98=140−42, 253=155+98, **351=253+98**, the shrunken pads outside the census | any population that does not re-derive, or a fab-real total that does not equal reported + recomputed invisible |
| 8 | Code-SDR identities | 1213+2≠1215, 1085+128+2≠1215, 373+4≠377, 22≠12+4+3+3, 101.6+0.100≠101.70, 20/20 or 22 files missing from the package cell |
| 9 | drone-mech identities vs `converged_split.json` | 4 solids, a sum that does not round to 742,306.360, a per-solid split that does not match, 84.2 % that is not 624,770.5/742,306.360, a missing 4.010114 / 1,250.769445 citation, or 42_6/7,313,057 absent |
| 10 | the DRC cells reproduce from the carried `drc/*.json` runs | da_own≠0, da_span≠36, span types≠33+3, span gate≠the non-through count, CS renumbered≠222/0 |
| 11 | corrections: 11a OLD gone from rows, 11b NEW used outside §2, 11c 26 rows parse, **11d the additive rows are declared** | an old figure left as a live claim, a new figure that exists only inside the correction table, or a silent empty `absent_in_rows` |
| 12 | every WAIVED cell on a YES row is priced as a quote line | a waiver hiding a defect behind an orderable YES |

**Run records.** Real exit codes, not claims:

| run | what it did | exit |
|---|---|---|
| `pad_ring_census.py` on `runs/SHRINK/esc_rev_b.kicad_pcb` | re-derived the invisible-ring population on the shrunken board | 0 |
| `build_report.py --inject` | rewrote the three marked blocks from `rows.json` + `corrections.json` | 0 |
| `check_fab.py` | 17 check entries (12 numbered, 3 sub-blocks of #4, 4 of #11), 0 failures | **0** |
| `negative_test.py` | 8 one-variable mutations, each run through `check_fab.py` as a subprocess | **0** (all 8 caught) |

**Runs in this directory:** `out/check_report.log`, `out/checker_negative_test.log`, mutated inputs
under `out/neg/`, the census output under `derived/ring_census_shrink.json`.

---

## 6. Evidence in this directory

```
REPORT.md            this sheet
rows.json            the 52 cells: value, verdict, reason, source (+ solid integrity)
corrections.json     26 BOARD CORRECTION rows + the two machine checks each
build_report.py      generates the three marked blocks; --inject rewrites them in place
check_fab.py         17 check entries (12 numbered); exit 0 iff nothing contradicts a row
negative_test.py     8 mutations, each must make the checker exit non-zero
pad_ring_census.py   the ring census, re-run on the shrunken board (copied instrument)
derived/             ring_census_shrink.json  <- 140 PTH pads under 0.200, 28 via rings
out/                 auto_sections.md, cs_drc_renum.json, cs_padcheck.json (carried v5
                     controls), check_report.log, checker_negative_test.log, neg/
```

No repo was written, no commit was made: every board was read through an existing copy or through
`git show`, the ESC shrink lives where it was executed (`esc-pad-shrink/runs/SHRINK/`), and the only
file this wave created on the instrument side is the census output under `derived/`.
---

## 7. Verdict — the five objective conditions, per board

The conditions are derived, not typed: `check_fab.py` recomputes each one from the row's own cells
(condition 1 from the DRC cell, 2 from unconnected, 3 from non-through + ring + model integrity,
4 from package + revision, 5 from 52/52 cells carrying a value, a verdict and a reason).

**In one line each.**

- **Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today. 5 of 5. COMPLETE.** *0 errors*: 0 DRC errors,
  0 unconnected on two tools, 0 non-through, 1,215 holes reconciled, 20/20 manifest entries, 22
  committed package files, rev 2.1 on board and package, 4 fiducials at 1.5005 mm. Two quote lines,
  neither a defect: the 0.100-0.125 mm ring (W2) and the 0.100 mm track/space at 1 oz. Assembly is not
  orderable: 373/373 MPNs missing.
- **ESC rev_b — NOT ORDERABLE. 1 of 5.** The DRC cell moving from 523/621 to 253/351 does not make it
  a PASS, it makes it a smaller FAIL, and condition 3 is still FAIL on the 140-pad ring count.
  *1,536-1,542 unconnected*:
  1,536 of 2,316 required connections are open, so there is nothing to fabricate. When there is, the
  drawn 4 oz geometry is 253 reported / 351 fab-real — 113 of which no shrink can clear — and the rail
  passes 43.5 A only at k=0.048, at 49.67 A on a re-poured copy against 23.1 A as drawn.
- **drone-arm main rev_b — NOT ORDERABLE. 2 of 5.** *36 non-through vias* (33 at 0.100 mm) in 5
  blind/buried drill files: no non-HDI 4-layer house can drill or plate them, a KiCad conversion
  cleared 0 of the 15 vias that were tried, none of the 36 is free, and the only package on record
  describes the 15-via work board instead. DRC is 0 at its own rules and 36 at the rules the process
  actually has.
- **drone-mech airframe — NOT READY. 2 of 5.** *4 disjoint solids* (742,306.360 mm³, 84.2 % bulk fill,
  shell 42_6): interference is at 0 genuine pairs after the executed fixes, but that zero lives on
  copies no revision carries, the shell is four separated solids (min 8.2592 mm) needing a +97 g
  Boolean repair, and there is no drawing, ply book or manufacturing package.

### The five conditions, per board

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

**No board is marked complete unless all five conditions pass. One board passes all five.**
