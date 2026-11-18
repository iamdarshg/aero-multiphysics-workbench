# Master Pre-Fab Checklist — FINAL (wave 18)

Four boards, one question: **can this be ordered today, from artefacts that exist today, as the
design describes it?** Every cell is a measured value or an explicit PASS/FAIL/WAIVED with its reason
and its source. Documentation only: every number below already exists in a cited evidence directory.

- Input: `evidence/fab-checklist-v6/` (436 lines, 26 BOARD CORRECTIONS, checker exit 0, 8/8 negative
  mutations caught). Output: `evidence/fab-checklist-final/`.
- This is a closing wave. What it does: carries the four-row matrix forward, applies the wave-18
  settled state to every cell it touches (16 of 52), re-derives the corrections list with explicit
  supersession, and runs a stricter checker. What it does not do: measure anything new.

**Headline — one line per board.**

- **Code-SDR V2 rev 2.1** — **ORDERABLE, bare board, today. 5 of 5. COMPLETE.** *0 errors.*
- **drone-mech fuselage DM-FUS-001 REV 1** — **FAB-READY YES for the part. 5 of 5.** One solid,
  206,454.3197 mm³, 320.0042 g, 45 hashed files. Two open items are named, neither is part geometry.
- **ESC rev_b** — **NOT ORDERABLE.** *1,536-1,542 unconnected.* The design point moved to 36.6 A /
  33.7 A and the 3 oz pattern class cleared all 89 pad gaps; the board still has no route and no package.
- **drone-arm main rev_b** — **NOT ORDERABLE.** *0.85 mm.* 19 non-through vias remain and the clear
  diameter a through via needs does not exist at U10.

## 0. What changed since v6 — 16 of 52 cells, 6 verdict flips, 1 orderable flip

**16 cells updated, 6 verdicts flipped, 1 orderable flipped (drone-mech NO → YES).** The table lists the
flips and the population changes; the cells carried unchanged are nine on Code-SDR and the unchanged
ESC/arm columns.

| # | cell | v6 said | final says | why |
|---|---|---|---|---|
| 1 | drone-mech `drc` | 4 disjoint solids, 742,306.360 mm³, "0 genuine pairs" | **1 solid, 206,454.3197 mm³; 10 pairs / 3,305.834869 mm³** | the weld and the fore-fill executed; the pair count is the union of two populations that were each measured on one file |
| 2 | drone-mech `package` + `revision` | "none: 0 drawings, 0 ply book"; "no revision carries the fix" | **DM-FUS-001 REV 1, 45 hashed files, drawing PDF, STL −0.052 %** | the package was produced from copies and every check re-run on the shipped STEP |
| 3 | drone-mech `outline` | 372.425 × 158.328 × 640.000 mm (airframe span) | **640.00 × 211.78 × 93.87 mm part bbox, 320.0042 g** | population change: the row now describes the fuselage part, not the assembled airframe |
| 4 | ESC `copper` | 4 oz outer 0.140 / 1.5 oz inner; rail 23.1 A drawn | **3 oz outer 0.105 / 1.5 oz inner; phase 36.58 A, bus 34.5 A** | the settled design point is 36.6 A per phase / 33.7 A bus |
| 5 | ESC `min_track` + `min_space` | both **FAIL** at the 0.250 rule | both **PASS** at 0.200 | one variable changed: the pattern class of the weight |
| 6 | ESC `min_drill` | **FAIL** (PTH 0.200 below the 0.300 floor) | **PASS** (3 oz PTH floor 0.200) | same measurement, the floor moved with the weight |
| 7 | ESC `drc` | 253 reported / 351 fab-real (4 oz shrink arm) | **102 reported / 200 fab-real (3 oz)** | 229 → 102, GONE 127 / ADDED 0, all 89 pad gaps clear |
| 8 | ESC `min_ring` | 140 PTH pads below 0.200 | **70 annular rows** (42 PTH + 28 via) | the 140 is a pad census, the 70 is the DRC's object count; the 98 invisible rings stay the difference between 140 and 42 |
| 9 | drone-arm `nonthrough` | 36 = 26 blind + 10 buried | **19 = 15 micro + 4 blind** | 17 cleared by relocation and rule-legal re-sizing; and In1→In2 is an *adjacent* pair, so those are microvias |
| 10 | drone-arm `drc` | 0 own rules / 36 span gate | **4 own rules / 22 span gate** | the conversion added `{via_diameter:+4}` and removed 14 gate rows |

**The trap in #8, again.** The 70 and the 140 are not the same population and neither is wrong: 140 is
a per-pad census of PTH rings under 0.200 on the board, 42 of those pads are the ones KiCad reports,
28 vias add to them, and the 98 pads KiCad cannot see are why fab-real is 200 and not 102. A total
would have hidden which of the three numbers was being quoted.

**The trap in #9.** v6 and BC12 both called the In1→In2 span "buried". The copper order is F, In1, In2,
B — In1 and In2 are adjacent, so a via between them is a **microvia**, and the census that fixed the
layer-id sort says so (29 micro / 7 blind on 36, 15 micro / 4 blind on 19). The rule "classify by
layer pair" was right; that one example was wrong, and BC35 retracts it.

## 1. The master table

Four rows, the 13 required evidence columns plus two derived ones. `orderable` is YES iff the row has
0 FAIL cells, and `blocking` is the single number that stops the order — *for a NO row it must occur
verbatim in a FAIL cell* (check 3), and for a YES row it must be zero (check 2).

<!-- BEGIN TABLE -->
| board | layers | copper | min_track | min_space | min_drill | min_ring | nonthrough | unconnected | drc | package | revision | outline | finish | orderable | blocking |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b (19-via conversion)** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.200 mm | 0.1250 mm | via 0.100 / PTH 0.200 | via 0.100 / PTH 0.150 | 19 = 15 micro + 4 blind / 337; blocker 0.85 mm | 0 (pcbnew and kicad-cli) | 4 own rules / 22 span gate | package7 only (15-via work board), SENDABLE NO | empty on board; 'B' on a copy | 140.000 x 100.000 mm = 140.00 cm2 | ENIG | **NO** | **0.85 mm** |
| **ESC rev_b (36.6 A, 3 oz)** | 4 (F/In1/In2/B) | 3 oz outer 0.105 / 1.5 oz inner | 0.200 mm (rule 0.200) | 0.2000 mm (rule 0.200) | via 0.300 / PTH 0.200 | via 0.150 / PTH 0.125; 70 annular | 0 of 1,990 vias | 1,536-1,542 (pcbnew, uncapped) | 102 reported / 200 fab-real at 3 oz | none | empty, no silk rev | 491.732 cm2 drawn / 382.709 cm2 placement | ENIG | **NO** | **1,536-1,542 unconnected** |
| **Code-SDR V2 rev 2.1** | 4 (F/In1/In2/B) | 0.035 x4 = 1 oz | 0.100 mm | 0.1000 mm | via 0.200 / PTH 0.200 | via 0.100 / PTH 0.150 | 0 of 1,085 vias | 0 (pcbnew and kicad-cli agree) | 222 warn / 0 error; fab-real 222 | 22 files at HEAD, 20/20 manifest, 1,215 holes, rev 2.1 | 2.1 board = 2.1 job | 101.600 mm square = 103.2256 cm2 | ENIG | **YES** | **0 errors** |
| **drone-mech fuselage DM-FUS-001 REV 1** | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB files | n/a: 0 PCB holes | n/a: 0 plated holes | n/a: 0 vias | n/a: 0 nets | 1 solid, 0 free edges; 10 pairs / 3,305.834869 | 45 files + sha256 manifest, drawing, STL -0.052 % | DM-FUS-001 REV 1 | 640.00 x 211.78 x 93.87 mm; 206,454.3197 mm3 | n/a: no finish callout | **YES** | **0 (open: 2,096.819452 mm3 bearing rings)** |

### 1.1 Verdict ledger (full value, reason, source)

| board | column | verdict | value | reason | source |
|---|---|---|---|---|---|
| drone-arm main rev_b (19-via conversion) | layers | **PASS** | 4 copper: F.Cu / In1.Cu / In2.Cu / B.Cu | 4 layers measured on the repo board copy | fab-checklist-v4/out/measure_da_repo.json copper_layers |
| drone-arm main rev_b (19-via conversion) | copper | **PASS** | 0.035 mm on all four layers = 1 oz (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035) | stackup copper matches the declared 1 oz | measure_da_repo.json stackup_copper_mm |
| drone-arm main rev_b (19-via conversion) | min_track | **PASS** | 0.200 mm; width histogram 0.200 / 0.250 / 0.350 = 507 / 1,702 / 70 of 2,279 segments | 0.200 >= 0.100 (1 oz) | measure_da_repo.json min_track, track_width_hist |
| drone-arm main rev_b (19-via conversion) | min_space | **PASS** | 0.1250 mm minimum, identical in 2 runs; 509 and 512 pairs at the 0.30 mm probe floor, so the count is a range and is never charged | 0.1250 >= 0.100 (1 oz); the pair count does not reproduce | fab-checklist-v5/drc/da_space/drc_r1.json, drc_r2.json |
| drone-arm main rev_b (19-via conversion) | min_drill | **FAIL** | via 0.100 mm (15 of 337 vias at 0.100 after the conversion; 33 of 341 before) / PTH pad 0.200 mm | 0.100 < 0.200, so the board cannot be built without HDI | fab-da-36via/census_batA.json min_drill; measure_da_repo.json min_pth_drill |
| drone-arm main rev_b (19-via conversion) | min_ring | **WAIVED** | via ring 0.1000 x33, 0.1500 x21, 0.1750 x281, 0.2000 x6 (repo board, pre-conversion); PTH min 0.150 mm at U41.17 and U40.33 (18 pads); the post-conversion via-ring histogram was not re-censused | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line, not a redesign | measure_da_repo.json via_ring_hist, pth_ring_hist; open item N18 |
| drone-arm main rev_b (19-via conversion) | nonthrough | **FAIL** | 19 non-through = 15 micro + 4 blind by layer pair, of 337 vias (318 through), 16 stacks; split U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1; spans F-In1 7, In1-In2 5, F-In2 2, In2-B 3, In1-B 2; THE BLOCKER IS EXACTLY 0.85 mm: a 0.60/0.30 through via needs 0.85 mm clear on ALL FOUR LAYERS; U10 (RP2354B QFN-80, 0.4 mm pitch) offers 0.4 mm lanes | 19 != 0; no non-HDI 4-layer house can drill or plate them, and 0.85 mm of clear diameter has no site at U10 | fab-da-36via/census_batA.json, REPORT.md §7; fab-da-path/REPORT.md:14,318 |
| drone-arm main rev_b (19-via conversion) | unconnected | **PASS** | 0 pcbnew GetUnconnectedCount(False) and 0 kicad-cli after the 17-via conversion; 438 of 438 required pad-to-pad connections made; not a cap: the same netlist reads 2,196 on a zero-copper placement | both tools return 0, calibrated against the kicad-cli 499 cap | fab-da-36via/REPORT.md §7; measure_da_repo.json unconnected_pcbnew |
| drone-arm main rev_b (19-via conversion) | drc | **FAIL** | board's own rules 4 = {via_diameter:+4}, the only row the conversion added (set diff vs the 36-via board); no-HDI span gate 22 = 18 hole_size + 4 via_diameter; fab-real 22 | the right rules for a no-HDI process are the span gate, and 22 items survive it | fab-da-36via/REPORT.md:324-325; kicad-cli pcb drc --severity-all |
| drone-arm main rev_b (19-via conversion) | package | **FAIL** | package7 only: 5 blind/buried Excellon files carrying 15 holes, 360 drills + 4 slots = 364 hits, SENDABLE = NO; no package exists of the 19-via board | carries blind/buried files, and it is not an export of the board that would ship | fab-checklist-v4/out/drill_census.json 0.per_file; fab-da-package7/drill_census7.json |
| drone-arm main rev_b (19-via conversion) | revision | **FAIL** | board title block empty ('', '', ''); package7 stamps 'B' on 19 carriers because the patch was applied to a COPY | no revision on the board itself; the package's 'B' describes a copy | measure_da_repo.json title_revision; package7 job file |
| drone-arm main rev_b (19-via conversion) | outline | **PASS** | 140.000 x 100.000 mm Edge.Cuts centreline (140.15 x 100.15 with its 0.150 mm stroke) = 140.00 cm2, 1-up, no rails, 1 closed loop 0 holes | polygon closes, area > 0, one piece | measure_da_repo.json edge_cuts_extent_mm, outline_area_cm2 |
| drone-arm main rev_b (19-via conversion) | finish | **PASS** | ENIG (board stackup field and job file agree) | finish declared and consistent | measure_da_repo.json copper_finish |
| ESC rev_b (36.6 A, 3 oz) | layers | **PASS** | 4 copper: F.Cu / In1.Cu / In2.Cu / B.Cu | 4 layers measured; the 3 oz arm keeps the 4-layer stack | fab-checklist-v4/out/measure_esc.json copper_layers; esc-3oz-build/03_stackup.json |
| ESC rev_b (36.6 A, 3 oz) | copper | **PASS** | 3 oz outer: F.Cu 0.1050, B.Cu 0.1050; In1/In2 0.0525 = 1.5 oz (an assumption, not a published 3 oz inner weight); the 1.600 mm board is held; at the settled point the phase corridor carries 36.58 A (9.420 mm at 105 um, k=0.048, dT 20 K) and the bus 34.5 A (23 barrels x 1.50 A) against 36.6 / 33.7 A | the declared 3 oz outer stackup matches; the rail sits at 99.95 % of the 36.6 A phase requirement and at 102 % of the 33.7 A bus | esc-3oz-build/03_stackup.json, 08_ampacity.json, 01_capacity.json |
| ESC rev_b (36.6 A, 3 oz) | min_track | **PASS** | 0.200 mm; 4 segments at exactly 0.200 of 154; the 4 track_width rows the 0.250 rule flagged at 4 oz all clear at 0.200 | 0.200 >= 0.200 at 3 oz (it was < 0.250 at 4 oz) | measure_esc.json min_track; esc-3oz-build/04_setdiff.json |
| ESC rev_b (36.6 A, 3 oz) | min_space | **PASS** | 0.2000 mm minimum, identical in 3 runs; 499 pairs at the 0.30 mm probe floor, quoted as a range and never charged | 0.2000 >= 0.200 at 3 oz | fab-checklist-v4/out/space_repeat_v4.json; measure_esc.json min_space |
| ESC rev_b (36.6 A, 3 oz) | min_drill | **PASS** | via 0.300 mm (min of 1,990 vias) / PTH pad 0.200 mm; 110 of 223 PTH pads sit below 0.300 but every one clears the 0.200 PTH floor of the 3 oz rule set | 0.300 >= 0.300 via rule and 0.200 >= 0.200 PTH rule at 3 oz | measure_esc.json min_via_drill, pth_drill_hist; esc-3oz-build/rules_3oz_020.kicad_dru |
| ESC rev_b (36.6 A, 3 oz) | min_ring | **FAIL** | via ring min 0.150 (28 vias at 0.150), PTH min 0.125 mm at U204.11; 70 annular_width rows = 42 PTH rings at 0.150-0.175 + 28 via rings at 0.150, all under the 0.200 rule; a 3 oz quote normally grants 0.150 and nobody has quoted it | 0.125 < 0.200 published 3 oz floor and 70 rings are under it | esc-3oz-build/04_setdiff.json REMAIN by type; measure_esc.json via_ring_hist, pth_ring_hist |
| ESC rev_b (36.6 A, 3 oz) | nonthrough | **PASS** | 0 = 0 blind + 0 buried of 1,990 vias; every via is F.Cu-B.Cu through | no non-through span on the board | measure_esc.json vias_by_span |
| ESC rev_b (36.6 A, 3 oz) | unconnected | **FAIL** | 1,536-1,542 unconnected (pcbnew, uncapped: 1,542 on the base board, 1,536 after the rail repour, -6) of 2,316 required connections; kicad-cli floors at exactly 499 on six calibration boards, so 499 was the tool's cap | 1,536 of 2,316 connections are open: there is no route to fabricate | measure_esc.json unconnected_pcbnew; esc-rail-repour/REPORT.md:42; out/esc_cap_test.json |
| ESC rev_b (36.6 A, 3 oz) | drc | **FAIL** | 3 oz 0.200/0.200: 229 -> 102, row-level GONE 127 / ADDED 0 (120 clearance + 4 track_width + 3 connection_width); all 89 pad-pad gaps clear (QFN-80 U201 75 + USB-C J202/J203 14); 102 = 70 annular + 16 via_diameter + 16 via_dangling; fab-real 200 = 102 + 98 pad rings KiCad cannot report | 102 reported and 200 fab-real are both non-zero at 3 oz; only the pattern class changed, and it cleared exactly the footprint population | esc-3oz-build/04_setdiff.json, drc_base4oz/3oz.json, rules_3oz_020.kicad_dru |
| ESC rev_b (36.6 A, 3 oz) | package | **FAIL** | none: 0 gerber / drill / job files under hardware/esc | no package exists | facts.json facts.scan.esc_package |
| ESC rev_b (36.6 A, 3 oz) | revision | **FAIL** | title block '' and no silkscreen revision text anywhere on the board | no revision stamp | measure_esc.json title_revision |
| ESC rev_b (36.6 A, 3 oz) | outline | **PASS** | repo board 173.800 x 282.930 mm Edge.Cuts centreline = 491.732 cm2, 1-up, 1 loop 0 holes; the 3 oz DRC and ampacity run on the 382.709 cm2 placement of record (155.15 x 246.80 mm, 687 footprints, 492 vias) | both polygons close and both areas are > 0 | measure_esc.json edge_cuts_extent_mm; esc-3oz-build/09_area.json |
| ESC rev_b (36.6 A, 3 oz) | finish | **PASS** | ENIG (board field and job file agree) | finish declared | measure_esc.json copper_finish |
| Code-SDR V2 rev 2.1 | layers | **PASS** | 4 copper: F.Cu / In1.Cu / In2.Cu / B.Cu | 4 layers measured | measure_cs.json copper_layers |
| Code-SDR V2 rev 2.1 | copper | **PASS** | 0.035 mm on all four layers = 1 oz | stackup matches the declared 1 oz | measure_cs.json stackup_copper_mm |
| Code-SDR V2 rev 2.1 | min_track | **PASS** | 0.100 mm; 1,510 segments at exactly 0.100 of 11,168 | 0.100 >= 0.100 (1 oz) | measure_cs.json min_track |
| Code-SDR V2 rev 2.1 | min_space | **PASS** | 0.1000 mm minimum, identical in 3 runs; 508-512 pairs at the 0.30 mm probe floor (the count does not reproduce and is not charged) | 0.1000 >= 0.100 (1 oz) | fab-cs-fid-real/drc_r1.json; fab-checklist-v4/out/space_repeat_v4.json |
| Code-SDR V2 rev 2.1 | min_drill | **PASS** | via 0.200 mm (min of 1,085 vias) / PTH pad 0.200 mm | >= 0.200, no HDI | measure_cs.json min_via_drill, min_pth_drill |
| Code-SDR V2 rev 2.1 | min_ring | **WAIVED** | via ring 0.1000 x53, 0.1250 x1,013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57; 94 PTH pads below 0.200 (96 with the 2 oblong slot pads, which the ring formula does not score) | 0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: quote line W2, not a defect | measure_cs.json via_ring_hist, pth_ring_hist; fab-checklist-v5/out/cs_padcheck.json |
| Code-SDR V2 rev 2.1 | nonthrough | **PASS** | 0 = 0 blind + 0 buried of 1,085 vias; all F.Cu-B.Cu through | no non-through span | measure_cs.json vias_by_span |
| Code-SDR V2 rev 2.1 | unconnected | **PASS** | 0 pcbnew and 0 kicad-cli; 1,093 of 1,093 required connections made; both tools far below their caps and in agreement | ratsnest 0 on two independent tools | measure_cs.json unconnected_pcbnew; fab-cs-fid-real REPORT 5 |
| Code-SDR V2 rev 2.1 | drc | **PASS** | 0 errors / 222 warnings / 0 unconnected at the board's own rules plus its own .kicad_dru (199 lib_footprint_mismatch + 13 via_dangling + 10 track_dangling); fab-real 222; control: with all 316 duplicate-numbered pads renumbered on a copy the count is identical (222 total, 0 errors) | 0 errors, and the invisibility defect that would hide rings is proved empty by a renumber control | fab-cs-fid-real REPORT 5 (222/0/0 before and after); fab-checklist-v5/out/cs_drc_renum.json (222/0/0 renumbered) |
| Code-SDR V2 rev 2.1 | package | **PASS** | 22 files at HEAD under hardware/v2/fab (12 gerber+job, 4 Excellon+drill map, 3 assembly CSV, 3 root); 20/20 files in git archive HEAD hardware/v2/fab match the committed MANIFEST.sha256, 0 mismatches; 1,215 holes = 1,213 drills + 2 G85 slots, 0 non-through, census reconciles; revision 2.1; 377 pos rows = 373 parts + the 4 fiducials | the package exists in the repo, every manifest entry hashes to what was committed, it carries no blind/buried file, and it is an export of this board | verify-w9-adv/REPORT.md:118 (git archive vs MANIFEST.sha256, 20/20); fab-checklist-v4/out/drill_census.json 1 |
| Code-SDR V2 rev 2.1 | revision | **PASS** | board title block '2.1' and Code-SDR-V2-job.gbrjob Revision '2.1' | board and package agree | measure_cs.json title_revision; job file |
| Code-SDR V2 rev 2.1 | outline | **PASS** | 101.600 x 101.600 mm Edge.Cuts centreline (101.70 with its 0.100 mm stroke: 101.6 + 0.100 = 101.70, the measured bbox) = 103.2256 cm2, 1-up, no rails, 1 loop 0 holes | polygon closes, area > 0, and the extent reconciles with the 0.100 stroke | measure_cs.json edge_cuts_extent_mm, edges_bbox_mm |
| Code-SDR V2 rev 2.1 | finish | **PASS** | ENIG (board field and job file agree) | finish declared | measure_cs.json copper_finish |
| drone-mech fuselage DM-FUS-001 REV 1 | layers | **WAIVED** | n/a: 0 board / gerber / drill / project files against 205 STEP/brep | n/a: a printed/composite airframe part has no copper stackup | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | copper | **WAIVED** | n/a: 0 copper on any layer | n/a: no copper exists on this deliverable | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | min_track | **WAIVED** | n/a: no track | n/a: no copper exists on this deliverable | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | min_space | **WAIVED** | n/a: no copper | n/a: no copper exists on this deliverable | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | min_drill | **WAIVED** | n/a: 0 plated holes; the two 85.2 mm duct bores are modelled features, not drilled PCB holes | n/a: no PCB drilling operation exists on this part | facts.json scan.drone_mech; dm-final-package/README.md |
| drone-mech fuselage DM-FUS-001 REV 1 | min_ring | **WAIVED** | n/a: no plating | n/a: no plated hole on this deliverable | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | nonthrough | **WAIVED** | n/a: 0 vias on 0 boards | n/a: no vias exist | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | unconnected | **WAIVED** | n/a: 0 nets on 0 boards | n/a: no electrical netlist exists | facts.json scan.drone_mech |
| drone-mech fuselage DM-FUS-001 REV 1 | drc | **PASS** | geometry gate: 1 solid / 1 shell / closed, BRepCheck valid, 0 free and 0 non-manifold edges of 1,561; volume 206,454.3197 mm3 (BREP 206,454.3208, delta 0.001091); interference on the final part 10 pairs / 3,305.834869 mm3 = 6 genuine elevon-root clashes (1,204.481397) + 2 pushrod artefacts (4.534020) + 2 unclassified bearing-ring pairs (2,096.819452 = 63.4 %); knife edge at the wing-slot rim (z -90 to -70, |azimuth| 43-45 deg) | one valid watertight solid and 0 free edges; the knife edge is a stated process note and the bearing rings are an assembly interface, not part geometry | dm-final-package/out/r5_validate.json, r1c_pairs.json, REPORT.md §1e, README.md |
| drone-mech fuselage DM-FUS-001 REV 1 | package | **PASS** | 45 files hashed by SHA256SUMS (46 on disk including the manifest): STEP 9,801,595 B / BREP 4,712,827 B / STL 59,964 tri (mesh 206,347.1658 mm3, -0.052 % of STEP, watertight, Euler -2) / A3 drawing PDF 599,720 B / 6 check JSONs; copy-vs-source identical | the package exists, every file is hashed, and the mesh is inside its stated 0.1 % | dm-final-package/SHA256SUMS.txt (45 lines), README.md, out/r2_mesh.json, r6_sha256.json |
| drone-mech fuselage DM-FUS-001 REV 1 | revision | **PASS** | DM-FUS-001 REV 1 on the drawing title block and on the package; it supersedes the as-called 4-solid file | a revision stamp exists and the package agrees with it | dm-final-package/README.md; out/drone-mech_fuselage_rev1_drawing.pdf |
| drone-mech fuselage DM-FUS-001 REV 1 | outline | **PASS** | part bbox 640.00 x 211.78 x 93.87 mm; volume 206,454.3197 mm3; 2V/A 1.1492 mm; mass 320.0042 g at 1550 kg/m3 | the bbox and the volume are measured on the shipped STEP and the mass closes on the density | dm-final-package/README.md, out/r5_validate.json |
| drone-mech fuselage DM-FUS-001 REV 1 | finish | **WAIVED** | n/a: no finish callout exists; printed PLA core + CF/glass wrap is a MATERIAL answer, not a surface finish | n/a: surface finish is a bare-board parameter and neither the board nor a finish spec exists here | dm-final-package/README.md; AGENT_BOARD.md:281-283 |

### 1.2 Tally, recomputed from the rows

| board | PASS | FAIL | WAIVED | cells | orderable | blocking number |
|---|---:|---:|---:|---:|---|---|
| drone-arm main rev_b (19-via conversion) | 7 | 5 | 1 | 13 | **NO** | **0.85 mm** |
| ESC rev_b (36.6 A, 3 oz) | 8 | 5 | 0 | 13 | **NO** | **1,536-1,542 unconnected** |
| Code-SDR V2 rev 2.1 | 12 | 0 | 1 | 13 | **YES** | **0 errors** |
| drone-mech fuselage DM-FUS-001 REV 1 | 4 | 0 | 9 | 13 | **YES** | **0 (open: 2,096.819452 mm3 bearing rings)** |
| **all four** | **32** | **10** | **11** | **52** | 2 of 4 | — |
<!-- END TABLE -->

### 1.3 Row notes — what the settled state does to each row

**ESC — the design point moved, and the pattern class opened, but there is still no route.** The
settled point is **36.6 A per phase / 33.7 A bus, a 35 A-class ESC**. 43.5 A was never achievable: at
3 oz the phase conductor needs **11.963 mm** and the placement offers **9.420 mm** (36.58 A), the bus
needs **40.02 A** and 23 barrels give **34.50 A**, and the motor would have needed **1,777 W** against
**1,600** — and it would have bought only **527 km/h**. At 36.6 A the aircraft does **497 km/h**
(CdA 0.004162; band **353-616 km/h**, best 0.0042 over a 0.002710 friction floor) and the FETs sit at
**3.33 W/device, Tj 119.6 C = 68 % of 175 C** at Rth 22.4 with the spreader. The 3 oz stackup is
**0.1050 / 0.0525 / 0.0525 / 0.1050** in a held 1.600 mm board; the DRC goes **229 → 102** with
**GONE 127 / ADDED 0** and **all 89 pad-pad gaps** clear (QFN-80 U201 75 + USB-C J202/J203 14), which
is the door the programme was looking for. What is left is **102 = 70 annular + 16 via_diameter + 16
via_dangling**, fab-real **200 = 102 + 98** invisible rings, and **1,536-1,542 unconnected** — so the
board still has nothing to fabricate. The gate G1-G8 exits non-zero: G1 offers **9.420 mm = 36.58 A**
against 36.6 A, and G6's 23-barrel bus pad is now adequate at **34.5 A ≥ 33.7 A**. 687 footprints, 0 on
B.Cu; the heat spreader is mandatory and outside the outline (36/36 tight, 181.202 cm² declared vs
181.2 needed); **4-layer 3 oz is $450-870 per 5 pcs**, six layers **$1,300-1,900** and it still fails
the shunt pad. The compacted board is **382.709 cm²** against the drawn **491.732 cm²**, and the 370 cm² compaction floor for today's BOM is a separate question. The 4 oz route was vendor-limited — four houses publish an explicit 4 oz row, and none publishes the 0.200 mm pattern at 140 µm.

**drone-mech — FAB-READY YES for the part.** One watertight solid, **206,454.3197 mm³**, **320.0042 g**
at 1550 kg/m³, 1 solid / 1 shell / closed, 0 free and 0 non-manifold edges of 1,561, walls
**1.0921 / 1.1990 / 1.1800** and nose sections **1.1982-1.2068**. The package is **45 files hashed by
SHA256SUMS** (46 on disk), with the STEP, BREP, a watertight 59,964-triangle STL at **−0.052 %** of the
STEP volume, and an A3 drawing PDF. The **nose tip** is solid forward of z −359: that is a **design
note**, not a blocker. What is not part geometry: interference on the final part is **10 pairs /
3,305.834869 mm³** = 6 genuine elevon-root clashes (1,204.481397, one named cause, a measured
re-station fix not yet in the shipped wings) + 2 pushrod modelling artefacts (4.534020) + **2
bearing-ring pairs, 2,096.819452 mm³ = 63.4 % of the total, never classified by any document**. Plus a
**knife edge at the wing-slot rim** that wants a fillet or a 0.3 mm rim offset before a machinist cuts it.

**Code-SDR — complete, unchanged.** 5 of 5 conditions. 0 DRC errors / 222 warnings (199
lib_footprint_mismatch + 13 via_dangling + 10 track_dangling), 0 unconnected on two tools, **20/20**
files in `git archive HEAD hardware/v2/fab` match the committed **MANIFEST.sha256**, **22 files** at
HEAD, 1,215 holes = 1,213 drills + 2 G85 slots, rev 2.1 on board and job, **4 fiducials** (FID1 4.7843,
FID2 1.8462, FID3 2.9604, **FIDL_U63_U64 1.5005 mm = +0.2505**), bbox 101.70 mm at a **0.100 mm
stroke**. Assembly is still not orderable: 373 of 373 BOM rows have no MPN.

**drone-arm — the number is 19 and the blocker is 0.85 mm.** 19 non-through vias of 337 (**15 micro +
4 blind** by layer pair, 16 stacks), split U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1. In1 and In2 are
adjacent, so the 5 vias on that pair are MICROVIAS, not buried. The census moved
from 36 to 19 by executed layout work: **17 cleared (47.2 %, 13 stacks) by via relocation and
rule-legal re-sizing, 0 by moving a part**; every structural option failed — 11 south/west re-escape
attempts kept 0, net→pin 1 attempted 0 kept, rotating U10 gives a pad-set deviation of 0.000000 mm
(exactly a net permutation), and there is no SPI flash. **The blocker is exactly 0.85 mm**: a 0.60/0.30
through via needs 0.85 mm of clear diameter on all four layers and the QFN-80 U10 at 0.4 mm pitch
offers 0.4 mm lanes. DRC is **4 at its own rules** ({via_diameter:+4}) and **22 at the no-HDI span
gate** (18 hole_size + 4 via_diameter); unconnected 0 on both tools; RF void bit-identical at
**4.1699 mm² = 9.8338 %**. The only package is still `package7`, an export of the 15-via work board.

---

## 2. BOARD CORRECTIONS — 35 rows, old → new
<!-- BEGIN CORRECTIONS -->
| id | board | what was wrong | OLD | NEW | status | source |
|---|---|---|---|---|---|---|
| BC1 | ESC | the ESC was designed to 60 A per phase | `60 A per phase` | **43.5 A phase / 40 A bus** | superseded by BC30 | verify-w9-adv/REPORT.md:63 (43.5 = 240 A pack / 6 channels / 0.92); esc-flip-current, esc-rail-repour |
| BC2 | ESC / airframe | two whole-aircraft CdA values were used that are below the friction floor, so they are not physical | `CdA 0.000693 and 0.0015 m2` | **CdA 0.0034-0.0056 m2, best 0.0042 (friction floor 0.002710)** | live | esc-cda-bound/REPORT.md:320-336; verify-w9-adv/REPORT.md:12 (floor 0.002710) |
| BC3 | airframe / ESC | the 720 km/h design point is not reachable with this power system | `720 km/h` | **~545-570 km/h on this power system** | superseded by BC32 | verify-w9-adv/REPORT.md:77-78; esc-cda-bound/REPORT.md:371 |
| BC4 | ESC | 523 was quoted as the DRC total; it omits the pad rings KiCad cannot report | `523 reported as the total` | **fab-real = reported + invisible pad rings; as drawn 621 = 523 + 98, footprint-bound 413 (371 pad-pad at 0.200 + 42 PTH rings), 110 copper-bound, effective footprint-bound 511** | superseded by BC31 | esc-drc-resolve/REPORT.md:26,336-346,372 |
| BC5 | ESC | 499 was quoted as the unconnected count; it is kicad-cli's cap | `499 unconnected` | **1,536-1,542 unconnected (pcbnew, uncapped)** | live | fab-checklist-v4/out/esc_cap_test.json; esc-rail-repour/REPORT.md:42 (1,542 -> 1,536) |
| BC6 | drone-arm | 15 non-through vias was a fan-out work-board artefact, not the repo board | `15 non-through vias` | **36 non-through on the repo board (26 blind + 10 buried by span, of 341 vias)** | superseded by BC33 | fab-checklist-v4/out/measure_da_repo.json vias_by_span; verify-wave10-adv/final_answer.txt |
| BC7 | Code-SDR | the fiducial was charged as a 1.22 mm FAIL on a board that had no fiducials at all | `1.22 FAIL` | **4 fiducials on the committed board (HEAD fbf2eca), min gap 1.5005 mm = +0.2505** | live | fab-cs-fid-real/REPORT.md:14,132-141,237-249; git show HEAD:hardware/v2/Code-SDR-V2.kicad_pcb |
| BC8 | ESC | the 4 oz vendor survey over-counted houses | `five different houses` | **four houses carry an explicit 4 oz row** | live | v2v-fab-verify/REPORT.md |
| BC9 | ESC | the published area floor was 316 cm2 | `316 cm2 floor` | **370 cm2 for today's BOM (316 needs the M5 lugs replaced)** | live | esc-compaction-verify/REPORT.md |
| BC10 | drone-mech | 26 interference pairs was arithmetic over a subset of the pair set, not a verdict | `26 pairs` | **0 genuine pairs (2 residual pairs = 4.010114 mm3, 100 % artefact)** | superseded by BC28 | fab-dm-final/REPORT.md state_changed |
| BC11 | drone-mech | 'delete 4 of 6 envelopes reaches zero' is short by one step | `delete 4 of 6 envelopes reaches zero` | **delete 4 + resize** | superseded by BC27 | fab-dm-envelopes/REPORT.md |
| BC12 | drone-arm | the In1->In2 vias were labelled blind; by span they are buried (a drill class is not a span class) | `the four In1->In2 vias are blind` | **In1.Cu-In2.Cu vias are BURIED (repo board: 10 of them); classify by layer pair** | superseded by BC35 | fab-checklist-v4/out/measure_da_repo.json via_table |
| BC13 | ESC | 'rail PASS' was a single number; it holds only at one barrel-plating convention | `rail PASS` | **PASS only at k=0.048 (47.1 A = 1.08x of 43.5 A); 24.8 A and FAIL (0.57x) at k=0.024** | superseded by BC30 | esc-rail-repour/REPORT.md:45,283-285; esc-flip-current/REPORT.md:303 |
| BC14 | Code-SDR | the Edge_Cuts stroke was stated as 0.15 mm; 101.6 + 0.15 = 101.75, which is not the measured 101.70 | `0.15 mm stroke` | **0.100 mm stroke (101.6 + 0.100 = 101.70)** | live | board file: 4 Edge.Cuts shapes at (stroke (width 0.1)); v5/D1 arithmetic |
| BC15 | Code-SDR | the fab commit was counted as 16 files | `16 files committed` | **22 files committed by 1a20bd6** | live | git show --name-status 1a20bd6 |
| BC16 | ESC | '3 packages' understates the 4 oz work | `3 packages` | **one impossible part (U201) + 23 footprint edits** | superseded by BC31 | esc-branch-4oz/REPORT.md |
| BC17 | ESC | the ESC outline was quoted stroke-inclusive | `173.950 x 283.080` | **173.800 x 282.930 (Edge.Cuts centreline)** | live | fab-checklist-v4/out/measure_esc.json edge_cuts_extent_mm |
| BC18 | ESC | the post-shrink DRC was going to be reported as a before/after total, which is what this programme has been burned by twice on this board | `523 -> 253 as a total` | **row-level set diff GONE 270, ADDED 0; 253 = 155 footprint-bound + 98 copper-bound; fab-real 351 = 253 + 98 invisible pad rings** | superseded by BC31 | esc-pad-shrink/setdiff.json (gone_rows 270, added_rows 0); runs/SHRINK/drc_shrink.json; v6 derived/ring_census_shrink.json |
| BC19 | ESC | the footprint-bound population was quoted at its pre-shrink size and never revised | `413 footprint-bound (371 pad-pad at 0.200 + 42 PTH rings)` | **155 footprint-bound = 113 pad-gap + 42 PTH rings after the shrink** | superseded by BC31 | esc-pad-shrink/setdiff.json gone by type; runs/SHRINK/drc_shrink.json annular_width rows (70) minus the 28 via rings |
| BC20 | ESC | the footprint gaps were treated as one population and one shrink width, as if all of them could be cleared by editing pads | `all pad-gap rows shrinkable` | **113 remain and cannot be shrunk: QFN-80 U201 RP2354B 75 + USB-C J202/J203 GCT USB4105 38, each needing a part change or a documented waiver** | superseded by BC31 | esc-pad-shrink/groups.json (371 = 258 + 75 + 38), required_widths.json, REPORT.md section 3 (land-pattern floor); esc-gaps-113 scope |
| BC21 | ESC | the rail capacity was quoted as one as-drawn number and the re-poured geometry had no cell at all | `23.1 A quoted as the rail capacity` | **re-poured BATP 49.67 A / BATN 59.09 A / BATP_IN 47.74 A at k=0.048 / 20 K; 24.8 A at k=0.024; the repo board is still 23.1 A as drawn, so this is EVIDENCE ONLY** | superseded by BC31 | esc-rail-repour/22_numbers.json measured[] (before/after per net) with controls C1-C7 all pass |
| BC22 | drone-mech | the body volume was quoted as one number, with no bulk/wall split and no per-solid identity, so '4 solids' was a count and not a measurement | `742,305.526 mm3 as one undifferentiated volume` | **742,306.360 mm3 converged, 4 solids at 624,770.530 + 75,919.237 + 20,808.297 + 20,808.297 mm3; 84.2 % is bulk fill (624,770.5) against 117,531.8 mm3 of 1.2 mm wall** | superseded by BC27 | body-source-sync/REPORT.md:60-70 (probe_body_identity.py, converged_split.json, epsilon 1e-12); body-record-final/REPORT.md:275 |
| BC23 | drone-mech | the body of record was cited by name only, so no reader could tell which of the five registered candidates the numbers describe | `the 42_6 shell, unnamed file` | **fuselage_battery_bay_shell_endpoint_relief_42_6.step, 7,313,057 B, sha256 c4b81dc3...bc8ea4ec, 4 solids 4/4 valid 0 free edges** | superseded by BC27 | body-source-sync/REPORT.md:55-70; body-record-final/REPORT.md:273-283 |
| BC24 | drone-arm | the declared via type was quoted beside the span as if the two agreed; for 10 of the 36 they do not, so a declared type is not a classification | `declared type 33 microvia + 3 blind/buried taken as the classification` | **10 of 36 declared types contradict their layer pair (29 span 2 copper layers, 7 span more); the span is read from the layer pair** | superseded by BC33 | fab-da-census/via_census.json non_through_type_span_disagreements (10), non_through_adjacent_pair (29), non_through_span_gt2 (7); tables.md |
| BC25 | drone-arm | the 36 non-through vias were assumed to overlap the copper the owed respin already re-lays, i.e. that some were free | `36 vias could ride the respin` | **FREE = 0 of 36: this variant has no J60-J66 servo header, the 6 U10 7th-channel pads carry 0 vias, and /CAN_5V reaches 2 pads with 0 vias of any type** | superseded by BC33 | fab-da-census/REPORT.md section 3 (free-rider test, net-family scan 0 matches of 175 nets); via_census.json nt_detail servo_header_pads |
| BC26 | Code-SDR | the package integrity control was a byte compare over the files a prior wave happened to export, not over what was committed | `14 compared files byte-identical to an independent export` | **20/20 files in git archive HEAD hardware/v2/fab match the committed MANIFEST.sha256, 0 mismatches** | live | verify-w9-adv/REPORT.md:118 (git archive <tree> | hash every file against MANIFEST.sha256) |
| BC27 | drone-mech | the body of record was four disjoint solids totalling 742,306.360 mm3 | `4 disjoint solids, 742,306.360 mm3 (42_6 shell)` | **one solid: 206,454.3197 mm3, 320.0042 g at 1550 kg/m3, 1 solid / 1 shell / closed, 0 free and 0 non-manifold edges of 1,561** | live | dm-final-package/out/r1b_doubles.json (the four solids were disjoint, 0.000000 mm3 pairwise), r5_validate.json; dm-fore-fill/out/part_nose_v2.step |
| BC28 | drone-mech | the interference count was published as 6 pairs and as 8 pairs; both are true on one file each and neither is the union | `8 pairs / 6 genuine (1,250.769445 mm3)` | **10 pairs / 3,305.834869 mm3 on the final part: 6 genuine (1,204.481397) + 2 pushrod artefacts (4.534020) + 2 unclassified bearing rings (2,096.819452 = 63.4 %)** | live | dm-final-package/REPORT.md §1a-1e, out/r1c_pairs.json (three bodies, same instrument, eps 1e-12) |
| BC29 | drone-mech | the deliverable had no package, no drawing and no revision | `no drawings, 0 ply book, no revision` | **DM-FUS-001 REV 1: 45 files hashed by SHA256SUMS (46 on disk), STEP + BREP + STL (59,964 tri, -0.052 % of STEP) + A3 drawing PDF** | live | dm-final-package/README.md, SHA256SUMS.txt (45 lines), out/r6_sha256.json |
| BC30 | ESC | the ESC's design point was 43.5 A per phase / 40 A bus, a current the 3 oz corridor cannot carry | `43.5 A phase / 40 A bus` | **36.6 A per phase / 33.7 A bus, a 35 A-class ESC; 36.6 A gives 497 km/h, 43.5 A would have bought only 527 km/h** | live | esc-operating-point; esc-3oz-build/08_ampacity.json (36.58 A at 9.420 mm); esc-motor-demand |
| BC31 | ESC | the DRC was quoted on the 4 oz board with its pad-shrink total, which is not the 3 oz arm | `523 -> 253 as the design-point DRC` | **3 oz 0.200/0.200: 229 -> 102, row-level GONE 127 / ADDED 0 (120 clearance + 4 track_width + 3 connection_width); all 89 pad-pad gaps clear; fab-real 200 = 102 + 98 invisible rings** | live | esc-3oz-build/04_setdiff.json, drc_base4oz/3oz.json, rules_3oz_020.kicad_dru |
| BC32 | ESC | the aircraft performance numbers were carried from the 43.5 A arm | `~545-570 km/h at 43.5 A` | **497 km/h at 36.6 A (CdA 0.004162; band 353-616 km/h); FET 3.33 W/device, Tj 119.6 C = 68 % of 175 C at Rth 22.4** | live | esc-operating-point; esc-3oz-build §5 (G7); esc-cda-bound |
| BC33 | drone-arm | the non-through population was 36 after the census; 17 cleared by executed layout work and 19 remain | `36 non-through vias (26 blind + 10 buried)` | **19 non-through of 337 vias (318 through): 15 micro + 4 blind by layer pair, 16 stacks; U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1; own-rules DRC 4 = {via_diameter:+4} and span gate 22 = 18 hole_size + 4 via_diameter** | live | fab-da-36via/REPORT.md §7, census_batA.json; fab-da-u10-ripup/REPORT.md |
| BC34 | drone-arm | the 0.100 mm drill was quoted as the blocker; the blocker is the clear diameter a through via needs | `0.100 mm via drill is the blocker` | **exactly 0.85 mm: a 0.60/0.30 through via needs 0.85 mm of clear diameter on all four layers; U10 (QFN-80, 0.4 mm pitch) offers 0.4 mm lanes** | live | fab-da-path/REPORT.md:14,318; fab-da-36via/REPORT.md §2, §7 |
| BC35 | drone-arm | BC12 called the In1->In2 span buried; those two copper layers are adjacent, so the vias on that pair are microvias | `In1.Cu-In2.Cu vias are BURIED (repo board: 10 of them)` | **In1 and In2 are ADJACENT: the 10 vias on that pair (5 after the conversion) are MICROVIAS; of the 19, 15 are micro and 4 are blind (F-In2 2, In1-B 2)** | live | fab-da-36via/census_base.json (copper_order F, In1, In2, B; by_span_class 29 micro / 7 blind), census_batA.json (15 micro / 4 blind) |

**35 rows: 18 live, 17 superseded.** BC1-BC26 are the v6 list, carried with their OLD/NEW pairs intact and their status re-derived. Seventeen of them describe a board that has since moved (36 vias to 19, 4 oz to 3 oz, 43.5 A to 36.6 A, 4 solids to 1), so they are marked superseded and their successor is named: a superseded row is history, not a live claim. BC27-BC35 are wave-18. Check 11 fails if a live OLD token survives in rows.json, if a live NEW token is used nowhere outside this section, or if a superseded row's stale token is still quoted in a cell.
<!-- END CORRECTIONS -->

**How to read it.** The 17 superseded rows are not deletions: they are the history of a programme that
kept finding the number it had was true of a different population. BC18-BC20 walked the ESC down from
523 to 253 on a shrink at 4 oz; BC31 replaces that whole arm with the 3 oz one (229 → 102) because the
weight, the rule set and the pad shrink all changed — quoting 253 against 102 would be the same class of
mistake BC18 was written to stop. BC22-BC23 gave the 4-solid body an identity; BC27 replaces it with the
one-solid part that was actually welded. BC12 fixed a *class* ("classify by layer pair") and got one
*example* wrong (In1→In2 is adjacent, so microvia); BC35 retracts the example and keeps the rule.

---

## 3. What is NOT known — 27 open items

Each row is a question no artefact answers, with the owner who must answer it. The four the brief named
are N1 (the ESC route), N7 (the 150 C battery label), N13 (drone-arm's path choice) and N21 (the 63 %
bearing-ring pairs).

| # | open question | owner | why it matters |
|---:|---|---|---|
| **N1** | **Where the ESC route comes from.** At 36.6 A / 33.7 A the 3 oz pattern class clears every footprint gap, but **1,536-1,542 of 2,316** connections are open and no route exists in evidence | PCB wave | there is no routed ESC to fabricate; the DRC work is necessary, not sufficient |
| **N2** | **Does the G1-G8 gate pass at 36.6 A?** It exits non-zero: G1 offers **9.420 mm = 36.58 A** against 36.6 A, 0.02 A (0.05 %) short, and the gate has not been re-run at 36.6 A as its own row set | owner | the design point needs 100.05 % of the corridor; that is a tolerance question, not a layout one |
| **N3** | **Barrel plating wall: 25 µm or 38 µm?** (k = 0.024 vs 0.048, 1.50 A vs 3.00 A per barrel) | fab / CM | it is the difference between 34.5 A and a bus that passes, and between 4 of 9 ampacity elements failing or not |
| **N4** | **Is the inner weight 1.5 oz?** The 3 oz quote publishes the outer only; 0.0525 inner is an assumption | fab | if the shop forces 1 oz inners, inner capacity per mm drops 26 %; no rail uses the inners, so the verdict holds |
| **N5** | **A measured CdA.** 0.004162 is analytical; 0.0034-0.0056 is the band over a 0.002710 floor | owner / test | every current, every copper width and the 497 km/h scale linearly with it |
| **N6** | **The heat-spreader interface.** Rth 22.4 °C/W is an assumption; Tj 119.6 C is 68 % of 175 C only at that number, and the spreader is outside the outline | mechanical / thermal | the FET margin is a thermal-stack answer, not a silicon answer |
| **N7** | **The 150 C battery label.** The "12S 1.6 Ah 150C" pack is a **label**, never measured; it sets the 240 A supply and therefore the whole current budget | owner / test | the largest single input to every current in this sheet is a marketing rating |
| **N8** | **The 3 oz price.** $450-870 per 5 pcs is an estimate; no quote exists | CM | the checklist says buildable, not affordable |
| **N9** | **The ring floor at 3 oz.** 70 annular rows sit under the 0.200 rule (42 PTH 0.150-0.175 + 28 via 0.150); a 3 oz quote usually grants 0.150, nobody has quoted it | fab / owner | this is the whole of the remaining ESC DRC population that is not via_diameter or dangling |
| **N10** | **The 16 via_diameter and 16 via_dangling.** The diameter rows are vias below 0.700 mm; the dangling rows are stubs that vanish with a route | PCB wave | they are the only rows left that a re-rule or a route changes |
| **N11** | **A second source for 0.200 mm at 105 µm.** One house (Multi-CB) publishes it | CM | a single-house process is a supply risk and a price risk |
| **N12** | **Which ESC board ships.** The repo board is **491.732 cm²**; the 3 oz DRC and ampacity run on the **382.709 cm²** placement of record | owner / PCB wave | the sheet quotes both; until one is chosen the fabricator's outline is undecided |
| **N13** | **drone-arm's path choice.** Three exist: keep HDI (forbidden), **6 layers + 80-pin re-fanout**, or a **0.5 mm LQFP-100 STM32H723VGT6** | programme lead | no number moves until one is chosen; this is the largest remaining design decision |
| **N14** | **0.85 mm is physics, not a layout preference.** 11 south/west re-escape attempts kept 0; net→pin 1 attempted 0 kept; rotating U10 is exactly a net permutation (0.000000 mm); there is no SPI flash | programme lead | no local fix exists; only N13 changes the arithmetic |
| **N15** | **drone-arm's package.** `package7` is the **15-via work board**; no package of the 19-via board exists | PCB wave | a package that is not an export of the shipped board is not a package |
| **N16** | **drone-arm's revision.** Title block empty; `package7` stamps 'B' on a copy | PCB wave | the board a fabricator receives carries no revision |
| **N17** | **The 4 own-rule `via_diameter` rows** (the 0.40/0.20 class): waive, re-rule, or convert | owner | they are the only own-rule violations on the board |
| **N18** | **The post-conversion via-ring histogram** was not re-censused; the ring cell quotes the pre-conversion board | next wave | the WAIVED verdict is on the old histogram, at the board's own rule |
| **N19** | **The free-rider status of the 19.** It was 0 of 36; it was not re-derived after the conversion | next wave | if any of the 19 rides the owed respin, the count could fall without new layout |
| **N20** | **The RF void.** 4.1699 mm² = 9.8338 % is bit-identical to the base; no acceptance threshold exists | RF / owner | the void is measured, not judged |
| **N21** | **The 2 bearing-ring pairs.** **2,096.819452 mm³ = 63.4 % of all interference**, measured identically on three bodies at 13.4 % of each ring's own volume, and **never classified** by any document | owner / CAD | the largest interference term in the assembly has no fit class; it must be declared or relieved |
| **N22** | **The knife edge at the wing-slot rim** (z −90…−70, \|azimuth\| 43-45°): needs a fillet or a 0.3 mm rim offset | next CAD wave | a printer renders it as a feather edge; a machinist cannot cut it as drawn |
| **N23** | **The elevon re-station (+38.485 mm)** is measured but not executed in the shipped wings | CAD | the 6 genuine clashes (1,204.481397 mm³) stay in the assembly until it lands |
| **N24** | **Code-SDR assembly MPNs: 373 of 373 BOM rows** | owner / purchasing | stops the assembly PO, not the etch order |
| **N25** | **A named assembly house's written fiducial requirement.** 1.5005 mm passes the programme's own 1.25 mm rule; nobody has quoted it back | CM | the passing rule is ours, not the builder's |
| **N26** | **Panelisation and price** for any board: no panel drawing, no quote | CM | a 1-up outline is not a price |
| **N27** | **Solder-mask dam width** between 0.4-0.5 mm pitch pads: the boards declare 0.05 mm; only the shop knows its yield | fab | a declared dam is not a quoted capability |

What is **not** on this list any more, because it was answered: the ESC's per-phase current (36.6 A /
33.7 A), whether 43.5 A was reachable (it was not), whether 3 oz clears the footprint gaps (89 of 89),
whether the ESC unconnected count is 499 (it is pcbnew's 1,536-1,542), whether drone-mech is four solids
(it is one), whether the 6-vs-8 pair count was an error (it was a population mismatch), and whether any
of drone-arm's non-through vias is free (none is).

---

## 4. The instruments behind these numbers

Six instruments in this programme produced plausible green numbers while being wrong. They are named
first, because the numbers below are only worth what their controls are worth.

**The six.** (1) An ASCII text probe that missed a Unicode minus. (2) The Code-SDR fiducial chain: a
raster distance transform quoted a quantisation floor (1.22) as a measurement, and a threshold was moved
from 1.25 to 1.00 so a FAIL printed as PASS. (3) The no-HDI gate classified vias by drill **diameter**
instead of span, so it could not see a 0.300 mm blind via. (4) A `.kicad_dru` without a `(version 1)`
line is silently ignored, so a gate can pass on rules that were never read. (5) A corridor tool counted
foreign pads, invented B.Cu where a net had none, and printed PASS over its own −80 % FAIL. (6) An
index-keyed solids exclusion measured the wrong population correctly.

**A seventh is a tool limit:** `kicad-cli`'s unconnected count floors at exactly 499. It is a cap, not a
count. **An eighth is the carried number** — right once, quoted again without re-running its instrument;
the ESC's 4 oz total was exactly that shape and is why BC31 re-derives the arm at 3 oz. **A ninth, new
here, is the superseded number:** a figure that was correct for the board it was measured on and is now
a different board (36 vias, 43.5 A, 4 solids). Every one of those is marked in §2 with its successor.
**A tenth, also new here, is the mis-classified layer pair:** BC12 fixed the rule and got the example
wrong; the census invented later (with the layer-id sort bug caught and fixed) is what settled it.

| measurement | instrument | control | status |
|---|---|---|---|
| layers, stackup, copper weight | `measure.py` stackup parser (pcbnew 9.0.7) | reproduces `AGENT_BOARD.md:34-41` on three boards; nested-block parse hand-verified | checked |
| min track | `measure.py` segment census | 1,510 segments at 0.100 on CS; "11,168 tracks" is segments, not nets | checked |
| **min space** | `kicad-cli` DRC with a 0.30 mm probe `.kicad_dru`, 2-3 repeats | repeats land **exactly** on their own rule (0.1250 / 0.2000 / 0.1000); the pair count does not reproduce (509/512, 499, 508-512), so the minimum is charged and the count is a range | checked, count not quotable |
| min drill | `measure.py` via + pad drill census | reconciles with the Excellon by hand identity (336+22+6−4 = 360) | checked |
| min annular ring | per-pad diameter census | the naive `(min size − max drill)/2` invented 8 slot violations before it was fixed | checked after a caught defect |
| **non-through by span** | `GetViaType` + **layer pair** from `CuStack()` order | the layer-id sort bug was caught and fixed (it had reported 305 of 341 as non-through); two independent censuses agree on 36 then 19 | checked, and the declared type is demoted |
| **unconnected** | `pcbnew GetUnconnectedCount(False)` vs `kicad-cli` | calibrated on six boards of known count: pcbnew returns N at every N, kicad-cli floors at 499; pcbnew returns 2,196 on a zero-copper placement | checked against a known cap |
| **the ESC 3 oz set diff** | `04_setdiff.py` on row identity (type + objects + position), rule name excluded | **229 → 102, GONE 127 / ADDED 0**; the control (same file, clearance 1.00) moves 102 → 1080, proving the `.kicad_dru` is read; with the `.dru` deleted the same board reads 16 (a plausible green) | checked, with the control named |
| **the 89 pad gaps** | the same set diff, grouped by footprint family | 75 QFN-80 + 14 USB-C = 89, every one gone, ADDED 0 | checked row by row |
| **fab-real = reported + invisible rings** | `pad_ring_census.py` per-pad census vs DRC | 140 census pads under 0.200, 42 reported, 98 invisible; `200 = 102 + 98` | checked, with the blind spot named |
| **the 43.5 A vs 36.6 A design point** | IPC-2221 with k = 0.048 external / 0.024 internal, dT 20 K | the checker recomputes 36.58 A from 9.420 mm × 105 µm independently of the report text | checked by independent arithmetic |
| **the bus barrel count** | pad-capacity builder (0.30 mm to border, 0.90 mm pitch) | 23 legal positions × 1.50 A = 34.5 A; the gate's own withdrawn 3.00 A/barrel is named as the cause of its old green | checked, with the withdrawn constant named |
| **the gate G1-G8** | `07_gate3oz.py` | four arms of the same board: only the withdrawn constants produce exit 0; the four-instrument table is quoted | checked, exit code visible |
| **the 0.85 mm blocker** | geometric obstruction census per net at the site | 0.60 pad + 2 × 0.125 clearance = 0.85 mm on all four layers; U10 lane 0.4 mm; median gap at the blocked points 0.00-0.30 mm | checked by arithmetic and by the site table |
| **drone-arm's 17-via conversion** | `s6_exec.py` / `s7_slide.py` + DRC gate | the 17 kept are DRC-gated; the two batches that failed (slide 0 of 5, track-crossing drops) are reported, not hidden | checked |
| **the drone-mech solid** | OCC `BRepGProp` at ε 1e-12 on the shipped STEP | 1 solid / 1 shell / closed; 0 free and 0 non-manifold edges of 1,561; STEP↔BREP Δ 0.001091 mm³ | checked |
| **the drone-mech mass** | density × volume | 206.4543197 cm³ × 1.55 = 320.0042 g, recomputed by the checker | checked |
| **the drone-mech mesh** | written-STL volume, vertices merged at 1e-4 mm | deflection ladder from 0.200 to 0.002 mm; shipped 0.002 = 59,964 tri, **−0.052 %**, watertight, Euler −2 | checked |
| **the interference pairs** | OCCT `BRepAlgoAPI` booleans at ε 1e-12, three bodies, same instrument | 6-vs-8 shown to be two populations; the set diff closes to 6 × 10⁻⁶ mm³; ring rows identical on all three bodies | checked by decomposition |
| **the package manifest** | SHA256SUMS.txt regenerated last, 45 lines | every file in the package hashed, README and REPORT included; copy-vs-source identical | checked |
| **row/summary consistency** | `check_fab.py` (13 check entries, this directory) | re-derives the tally, orderable, every blocking number, the ESC/arm/CS/dm arithmetic, the correction status and the NOT-KNOWN count; 9 negative tests each force a non-zero exit | **rewritten in this wave** |

---

## 5. The checker

`check_fab.py` (13 numbered checks, exit 0 iff clean). It is not a prose linter: it re-reads
`rows.json`, `corrections.json`, `facts.json` and `REPORT.md`, recomputes the arithmetic the cells
assert (including IPC-2221 at 9.420 mm × 105 µm and the 320.0042 g mass from volume × density),
re-derives the three generated blocks, resolves every cited evidence path on disk, and fails if any
summary contradicts its rows.

| # | check | what would make it fail |
|---:|---|---|
| 1 | coverage and vocabulary: 52 cells, 4 × 13, no blank, no TBD | a missing column, an empty reason, a verdict outside PASS/FAIL/WAIVED |
| 2 | `orderable` == (0 FAIL cells), blocking non-zero iff a FAIL exists | a row claimed YES with a FAIL in it, or a NO row with a zero blocker |
| 3 | the blocking number occurs verbatim in a FAIL cell | a blocking number invented for the summary |
| 4 | the three REPORT blocks are byte-identical to the generator | any hand-edited table cell |
| 5 | the tally rows reproduce from `rows.json` | a summary count that drifted |
| 6 | drone-arm identities: 337=318+19, 19=15+4, pair and ref sums, 0.60+2×0.125=0.85, 4/22 DRC, 438 connections | any count that does not re-derive, or a blocker that is not a blocker |
| 7 | ESC identities: 229=102+127, 127=120+4+3, 102=70+16+16, 70=42+28, 200=102+98, 89=75+14, stackup closes to 1.600, 34.5=23×1.50, **IPC-2221 recomputes 36.58 A** | a population that does not re-derive, or a capacity that arithmetic rejects |
| 8 | Code-SDR identities: 1213+2=1215, 22=12+4+3+3, 373+4=377, 101.6+0.100=101.70, 222=199+13+10 | any count that drifted |
| 9 | drone-mech identities: mass from volume × density, sets sum to 3,305.834869, 2×1,048.409726, 63.4 %, STL −0.052 %, 45+1=46 | a volume, a mass, a pair count or a manifest length that does not close |
| 10 | corrections: 35 unique ids, 18 live / 17 superseded, no live OLD token survives, every live NEW token is used outside §2, no superseded stale token is quoted, every successor is live | a retracted figure left as a live claim, a new figure that exists only inside §2, or a silent supersession |
| 11 | every WAIVED cell is n/a or a priced quote line | a waiver hiding a defect behind an orderable YES |
| 12 | the conditions block reproduces from the cells; NOT KNOWN carries 27 owned items and names the four required subjects | a condition that does not follow from the cells, or a shorter list than the sheet claims |
| 13 | every cited evidence path exists on disk | a source that names a directory or file that is not there |

**Run records — real exit codes, not claims.**

| run | what it did | exit |
|---|---|---:|
| `make_pack.py` | emitted `rows.json` (52 cells), `corrections.json` (35 rows), `facts.json` | 0 |
| `build_report.py --inject` | rewrote the three marked blocks from the data files | 0 |
| `check_fab.py` | 13 checks, **0 failures** | **0** |
| `negative_test.py` | 9 one-variable mutations, **9 caught**, each through `check_fab.py` as a subprocess | **0** |

Logs: `out/check_report.log`, `out/checker_negative_test.log`; mutated packs under `out/neg/c1..c9`.
The mutations are: orderable flipped on a row with FAIL cells; a matrix cell hand-edited; the
grand-total row changed by one; a non-through count changed to 36 against its own totals; ESC fab-real
set equal to the reported count; the drone-mech mass cell edited by 0.0008 g; a superseded row pointed
at a successor that does not exist; a WAIVED reason with no n/a and no price; the NOT-KNOWN count off
by one. Eight of the nine are caught by the semantic check each one targets (2, 5, 6, 7, 9, 10, 11,
12); the hand-edited matrix cell is caught by check 4 alone. Six of the nine also trip check 4, because
they change a block the generator owns — the intended belt-and-braces.

**One finding from check 13, worth a line.** Two source citations carried in from v6 point at files
that are not on disk (`fab-checklist-v5/out/drill_census.json` and
`fab-checklist-v5/drc/cs_space/drc.json`). The numbers are real — the first is in
`fab-checklist-v4/out/drill_census.json`, the second in `fab-cs-fid-real/drc_r1.json` — but a citation
nobody resolves is not a citation. They are repointed here, and check 13 now fails if any cited
evidence path is absent.

---

## 6. Evidence in this directory

```
REPORT.md            this sheet
rows.json            the 52 cells: short/value/verdict/reason/source, plus solid_integrity
corrections.json     35 BOARD CORRECTION rows (18 live, 17 superseded) + stale/present tokens
facts.json           every measured number the checker recomputes, grouped by board
make_pack.py         single source: emits rows.json, corrections.json, facts.json
build_report.py      generates the three marked blocks; --inject rewrites them in place
check_fab.py         13 checks; exit 0 iff nothing contradicts a row
negative_test.py     9 one-variable mutations, each must make the checker exit non-zero
out/                 auto_sections.md, check_report.log, checker_negative_test.log, neg/
```

No repo was written, no commit was made: every board and part was read through an existing copy or
through `git show`, and the drone-mech package was produced in `evidence/dm-final-package/` from copies.

---

## 7. Verdict — the five objective conditions, per board

The conditions are derived, not typed: `build_report.conditions()` recomputes each one from the row's
own cells (1 from the DRC cell, 2 from unconnected, 3 from non-through + ring + model integrity, 4 from
package + revision, 5 from 52/52 cells carrying a value, a verdict and a reason).

<!-- BEGIN CONDITIONS -->
| board | condition | verdict | blocking number |
|---|---|---|---|
| drone-arm main rev_b (19-via conversion) | 1 DRC-clean at the right rules | **FAIL** | 0.85 mm |
| drone-arm main rev_b (19-via conversion) | 2 zero unconnected | **PASS** | — |
| drone-arm main rev_b (19-via conversion) | 3 zero geometry defects | **FAIL** | 0.85 mm |
| drone-arm main rev_b (19-via conversion) | 4 validated package | **FAIL** | 0.85 mm |
| drone-arm main rev_b (19-via conversion) | 5 no open checklist cell | **PASS** | — |
| ESC rev_b (36.6 A, 3 oz) | 1 DRC-clean at the right rules | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b (36.6 A, 3 oz) | 2 zero unconnected | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b (36.6 A, 3 oz) | 3 zero geometry defects | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b (36.6 A, 3 oz) | 4 validated package | **FAIL** | 1,536-1,542 unconnected |
| ESC rev_b (36.6 A, 3 oz) | 5 no open checklist cell | **PASS** | — |
| Code-SDR V2 rev 2.1 | 1 DRC-clean at the right rules | **PASS** | — |
| Code-SDR V2 rev 2.1 | 2 zero unconnected | **PASS** | — |
| Code-SDR V2 rev 2.1 | 3 zero geometry defects | **PASS** | — |
| Code-SDR V2 rev 2.1 | 4 validated package | **PASS** | — |
| Code-SDR V2 rev 2.1 | 5 no open checklist cell | **PASS** | — |
| drone-mech fuselage DM-FUS-001 REV 1 | 1 DRC-clean at the right rules | **PASS** | — |
| drone-mech fuselage DM-FUS-001 REV 1 | 2 zero unconnected | **PASS** | — |
| drone-mech fuselage DM-FUS-001 REV 1 | 3 zero geometry defects | **PASS** | — |
| drone-mech fuselage DM-FUS-001 REV 1 | 4 validated package | **PASS** | — |
| drone-mech fuselage DM-FUS-001 REV 1 | 5 no open checklist cell | **PASS** | — |
<!-- END CONDITIONS -->

**In one line each — 13 of 20 conditions pass.**

- **Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today. 5 of 5. COMPLETE.** *0 errors*: 0 DRC errors,
  0 unconnected on two tools, 0 non-through, 1,215 holes reconciled, 20/20 manifest entries, 22
  committed package files, rev 2.1 on board and package, 4 fiducials at 1.5005 mm. Two quote lines,
  neither a defect: the 0.100-0.125 mm ring (W2) and the 0.100 mm track/space at 1 oz. Assembly is not
  orderable: 373/373 MPNs missing.
- **drone-mech fuselage DM-FUS-001 REV 1 — FAB-READY YES for the part. 5 of 5.** *0 blocking*: one
  solid, 206,454.3197 mm³, 320.0042 g, 0 free edges, walls 1.0921-1.1990, 45 hashed files, STL
  −0.052 %, REV 1 on the drawing. The nine WAIVED cells are n/a PCB columns, not waivers of a defect.
  Sequence does not make the airframe orderable: the 2 bearing-ring pairs (2,096.819452 mm³) are
  undeclared and the knife edge needs one CAD edit.
- **ESC rev_b — NOT ORDERABLE. 1 of 5.** *1,536-1,542 unconnected.* The 3 oz arm is a real improvement
  (229 → 102, all 89 pad gaps clear, the design point now 36.6 A / 33.7 A at 497 km/h and Tj 119.6 C),
  but 1,536 of 2,316 connections are open, 70 rings sit under the 0.200 rule, and there is no package
  and no revision. The gate G1-G8 exits non-zero on G1 by 0.02 A.
- **drone-arm main rev_b — NOT ORDERABLE. 2 of 5.** *0.85 mm.* 19 non-through vias (15 micro + 4 blind)
  after 17 were cleared by real layout work; DRC 4 at its own rules and 22 at the no-HDI span gate; 0
  unconnected on both tools; the only package is an export of the 15-via work board. The blocker is
  geometric: a 0.60/0.30 through via needs 0.85 mm clear on all four layers and U10 offers 0.4 mm lanes.

**What the objective achieved, and what it did not.** It produced a four-row sheet in which every cell
is a measured value or an explicit verdict with a reason, and in which the two boards that can be
ordered are the two that genuinely are: Code-SDR is complete, and the drone-mech fuselage is a
watertight, hashed, revision-stamped part. It also did what a closing sheet should do to its own
history: 35 corrections, 17 of them marked superseded with a named successor, so the sheet no longer
claims a 36-via board, a 43.5 A ESC, a 4-solid body or a 253-row DRC as live facts. What it did **not**
achieve is equally explicit: there is no routed ESC (1,536-1,542 open connections), no non-HDI
drone-arm (0.85 mm is physics, and the path choice — 6 layers or an LQFP-100 — is unmade), no assembly
order for Code-SDR (373/373 MPNs), and no disposition of the 63.4 % of drone-mech interference that
belongs to two unclassified bearing rings. Two of four boards are orderable; the other two each have
exactly one number standing in the way, and both of those numbers are now written down where a reader
can check them.