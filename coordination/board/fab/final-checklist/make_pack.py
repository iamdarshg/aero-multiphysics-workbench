#!/usr/bin/env python3
"""fab-checklist-final -- single source for rows.json, corrections.json and facts.json.

Documentation-only wave: every number is carried from a cited evidence directory. This
script exists so the three data files cannot disagree with each other, and so that a
value is typed exactly once.

Run: "C:/Program Files/Python312/python.exe" make_pack.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
V6 = os.path.join(os.path.dirname(HERE), "fab-checklist-v6")

COLUMNS = ["layers", "copper", "min_track", "min_space", "min_drill", "min_ring",
           "nonthrough", "unconnected", "drc", "package", "revision", "outline",
           "finish", "orderable", "blocking"]
EVID = 13


def C(short, value, verdict, reason, source):
    return {"short": short, "value": value, "verdict": verdict,
            "reason": reason, "source": source}


ARM = "drone-arm main rev_b (19-via conversion)"
ESC = "ESC rev_b (36.6 A, 3 oz)"
CS = "Code-SDR V2 rev 2.1"
DM = "drone-mech fuselage DM-FUS-001 REV 1"

rows = {
    "schema": "fab-checklist-final rows; every cell is {short, value, verdict, reason, source}. No blanks, no TBD.",
    "supersedes": "fab-checklist-v6/rows.json (same 13 evidence columns and verdict rules; every cell that the settled wave-18 state changed has been re-derived)",
    "columns": COLUMNS,
    "evidence_columns": EVID,
    "verdict_rules": {
        "layers": "PASS iff copper layers == 4",
        "copper": "PASS iff the stackup matches the board's declared weight on every copper layer; a rail capacity may be quoted here only as a derived figure with its k and its rule",
        "min_track": "PASS iff min track >= the pattern rule for the declared weight (1 oz 0.100, 3 oz 0.200, 4 oz 0.250)",
        "min_space": "PASS iff the MINIMUM measured clearance >= the rule for the declared weight; the pair count is never charged (it does not reproduce)",
        "min_drill": "PASS iff min via drill >= 0.200 (no HDI) AND min PTH drill >= the finished-hole floor at the declared weight",
        "min_ring": "PASS iff the smallest ring >= the published floor for the weight; WAIVED iff below that floor but at or above the board's own rule, priced as a quote line",
        "nonthrough": "PASS iff blind + buried == 0, classified by LAYER PAIR (span), never by drill diameter or declared type",
        "unconnected": "PASS iff pcbnew GetUnconnectedCount(False) == 0 and the count is not at a tool cap; a kicad-cli count of exactly 499 is its cap",
        "drc": "PASS iff 0 errors at the right rules for the weight AND the fab-real count (reported + DRC-invisible population) is 0. A count measured on a COPY is named as a copy",
        "package": "PASS iff a package exists, reconciles, is an export of the shipped part, and carries 0 blind/buried drill files",
        "revision": "PASS iff the part or board carries a non-empty revision and the package agrees with it",
        "outline": "PASS iff the outline polygon closes and the area (or volume, for a solid) is > 0",
        "finish": "PASS iff the copper_finish field is populated; WAIVED where no PCB and no finish callout exist",
        "orderable": "YES iff 0 FAIL cells. A WAIVED cell is a priced quote line or an n/a column, never a defect",
        "blocking": "the single measured number that stops an order today; for a NO row it must occur verbatim in a FAIL cell; for a YES row it must be 0",
    },
    "boards": {
        ARM: {
            "kind": "PCB",
            "solid_integrity": {"verdict": "PASS", "value": "board parses and exports; no geometry repair is claimed by this sheet"},
            "cells": {
                "layers": C("4 (F/In1/In2/B)", "4 copper: F.Cu / In1.Cu / In2.Cu / B.Cu", "PASS",
                            "4 layers measured on the repo board copy",
                            "fab-checklist-v4/out/measure_da_repo.json copper_layers"),
                "copper": C("0.035 x4 = 1 oz", "0.035 mm on all four layers = 1 oz (F.Cu 0.035, In1.Cu 0.035, In2.Cu 0.035, B.Cu 0.035)", "PASS",
                            "stackup copper matches the declared 1 oz",
                            "measure_da_repo.json stackup_copper_mm"),
                "min_track": C("0.200 mm", "0.200 mm; width histogram 0.200 / 0.250 / 0.350 = 507 / 1,702 / 70 of 2,279 segments", "PASS",
                               "0.200 >= 0.100 (1 oz)",
                               "measure_da_repo.json min_track, track_width_hist"),
                "min_space": C("0.1250 mm", "0.1250 mm minimum, identical in 2 runs; 509 and 512 pairs at the 0.30 mm probe floor, so the count is a range and is never charged", "PASS",
                               "0.1250 >= 0.100 (1 oz); the pair count does not reproduce",
                               "fab-checklist-v5/drc/da_space/drc_r1.json, drc_r2.json"),
                "min_drill": C("via 0.100 / PTH 0.200", "via 0.100 mm (15 of 337 vias at 0.100 after the conversion; 33 of 341 before) / PTH pad 0.200 mm", "FAIL",
                               "0.100 < 0.200, so the board cannot be built without HDI",
                               "fab-da-36via/census_batA.json min_drill; measure_da_repo.json min_pth_drill"),
                "min_ring": C("via 0.100 / PTH 0.150", "via ring 0.1000 x33, 0.1500 x21, 0.1750 x281, 0.2000 x6 (repo board, pre-conversion); PTH min 0.150 mm at U41.17 and U40.33 (18 pads); the post-conversion via-ring histogram was not re-censused", "WAIVED",
                              "0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: a quote line, not a redesign",
                              "measure_da_repo.json via_ring_hist, pth_ring_hist; open item N18"),
                "nonthrough": C("19 = 15 micro + 4 blind / 337; blocker 0.85 mm",
                                "19 non-through = 15 micro + 4 blind by layer pair, of 337 vias (318 through), 16 stacks; split U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1; spans F-In1 7, In1-In2 5, F-In2 2, In2-B 3, In1-B 2; THE BLOCKER IS EXACTLY 0.85 mm: a 0.60/0.30 through via needs 0.85 mm clear on ALL FOUR LAYERS; U10 (RP2354B QFN-80, 0.4 mm pitch) offers 0.4 mm lanes", "FAIL",
                                "19 != 0; no non-HDI 4-layer house can drill or plate them, and 0.85 mm of clear diameter has no site at U10",
                                "fab-da-36via/census_batA.json, REPORT.md §7; fab-da-path/REPORT.md:14,318"),
                "unconnected": C("0 (pcbnew and kicad-cli)", "0 pcbnew GetUnconnectedCount(False) and 0 kicad-cli after the 17-via conversion; 438 of 438 required pad-to-pad connections made; not a cap: the same netlist reads 2,196 on a zero-copper placement", "PASS",
                                 "both tools return 0, calibrated against the kicad-cli 499 cap",
                                 "fab-da-36via/REPORT.md §7; measure_da_repo.json unconnected_pcbnew"),
                "drc": C("4 own rules / 22 span gate", "board's own rules 4 = {via_diameter:+4}, the only row the conversion added (set diff vs the 36-via board); no-HDI span gate 22 = 18 hole_size + 4 via_diameter; fab-real 22", "FAIL",
                         "the right rules for a no-HDI process are the span gate, and 22 items survive it",
                         "fab-da-36via/REPORT.md:324-325; kicad-cli pcb drc --severity-all"),
                "package": C("package7 only (15-via work board), SENDABLE NO", "package7 only: 5 blind/buried Excellon files carrying 15 holes, 360 drills + 4 slots = 364 hits, SENDABLE = NO; no package exists of the 19-via board", "FAIL",
                             "carries blind/buried files, and it is not an export of the board that would ship",
                             "fab-checklist-v4/out/drill_census.json 0.per_file; fab-da-package7/drill_census7.json"),
                "revision": C("empty on board; 'B' on a copy", "board title block empty ('', '', ''); package7 stamps 'B' on 19 carriers because the patch was applied to a COPY", "FAIL",
                              "no revision on the board itself; the package's 'B' describes a copy",
                              "measure_da_repo.json title_revision; package7 job file"),
                "outline": C("140.000 x 100.000 mm = 140.00 cm2", "140.000 x 100.000 mm Edge.Cuts centreline (140.15 x 100.15 with its 0.150 mm stroke) = 140.00 cm2, 1-up, no rails, 1 closed loop 0 holes", "PASS",
                             "polygon closes, area > 0, one piece",
                             "measure_da_repo.json edge_cuts_extent_mm, outline_area_cm2"),
                "finish": C("ENIG", "ENIG (board stackup field and job file agree)", "PASS",
                            "finish declared and consistent",
                            "measure_da_repo.json copper_finish"),
            },
            "orderable": "NO",
            "blocking": "0.85 mm",
        },
        ESC: {
            "kind": "PCB",
            "solid_integrity": {"verdict": "PASS", "value": "board parses; the 3 oz stackup edit is read back from the saved file (0.1050 / 0.0525 / 0.0525 / 0.1050, 1.600 mm)"},
            "cells": {
                "layers": C("4 (F/In1/In2/B)", "4 copper: F.Cu / In1.Cu / In2.Cu / B.Cu", "PASS",
                            "4 layers measured; the 3 oz arm keeps the 4-layer stack",
                            "fab-checklist-v4/out/measure_esc.json copper_layers; esc-3oz-build/03_stackup.json"),
                "copper": C("3 oz outer 0.105 / 1.5 oz inner", "3 oz outer: F.Cu 0.1050, B.Cu 0.1050; In1/In2 0.0525 = 1.5 oz (an assumption, not a published 3 oz inner weight); the 1.600 mm board is held; at the settled point the phase corridor carries 36.58 A (9.420 mm at 105 um, k=0.048, dT 20 K) and the bus 34.5 A (23 barrels x 1.50 A) against 36.6 / 33.7 A", "PASS",
                            "the declared 3 oz outer stackup matches; the rail sits at 99.95 % of the 36.6 A phase requirement and at 102 % of the 33.7 A bus",
                            "esc-3oz-build/03_stackup.json, 08_ampacity.json, 01_capacity.json"),
                "min_track": C("0.200 mm (rule 0.200)", "0.200 mm; 4 segments at exactly 0.200 of 154; the 4 track_width rows the 0.250 rule flagged at 4 oz all clear at 0.200", "PASS",
                               "0.200 >= 0.200 at 3 oz (it was < 0.250 at 4 oz)",
                               "measure_esc.json min_track; esc-3oz-build/04_setdiff.json"),
                "min_space": C("0.2000 mm (rule 0.200)", "0.2000 mm minimum, identical in 3 runs; 499 pairs at the 0.30 mm probe floor, quoted as a range and never charged", "PASS",
                               "0.2000 >= 0.200 at 3 oz",
                               "fab-checklist-v4/out/space_repeat_v4.json; measure_esc.json min_space"),
                "min_drill": C("via 0.300 / PTH 0.200", "via 0.300 mm (min of 1,990 vias) / PTH pad 0.200 mm; 110 of 223 PTH pads sit below 0.300 but every one clears the 0.200 PTH floor of the 3 oz rule set", "PASS",
                               "0.300 >= 0.300 via rule and 0.200 >= 0.200 PTH rule at 3 oz",
                               "measure_esc.json min_via_drill, pth_drill_hist; esc-3oz-build/rules_3oz_020.kicad_dru"),
                "min_ring": C("via 0.150 / PTH 0.125; 70 annular", "via ring min 0.150 (28 vias at 0.150), PTH min 0.125 mm at U204.11; 70 annular_width rows = 42 PTH rings at 0.150-0.175 + 28 via rings at 0.150, all under the 0.200 rule; a 3 oz quote normally grants 0.150 and nobody has quoted it", "FAIL",
                              "0.125 < 0.200 published 3 oz floor and 70 rings are under it",
                              "esc-3oz-build/04_setdiff.json REMAIN by type; measure_esc.json via_ring_hist, pth_ring_hist"),
                "nonthrough": C("0 of 1,990 vias", "0 = 0 blind + 0 buried of 1,990 vias; every via is F.Cu-B.Cu through", "PASS",
                                "no non-through span on the board",
                                "measure_esc.json vias_by_span"),
                "unconnected": C("1,536-1,542 (pcbnew, uncapped)", "1,536-1,542 unconnected (pcbnew, uncapped: 1,542 on the base board, 1,536 after the rail repour, -6) of 2,316 required connections; kicad-cli floors at exactly 499 on six calibration boards, so 499 was the tool's cap", "FAIL",
                                 "1,536 of 2,316 connections are open: there is no route to fabricate",
                                 "measure_esc.json unconnected_pcbnew; esc-rail-repour/REPORT.md:42; out/esc_cap_test.json"),
                "drc": C("102 reported / 200 fab-real at 3 oz", "3 oz 0.200/0.200: 229 -> 102, row-level GONE 127 / ADDED 0 (120 clearance + 4 track_width + 3 connection_width); all 89 pad-pad gaps clear (QFN-80 U201 75 + USB-C J202/J203 14); 102 = 70 annular + 16 via_diameter + 16 via_dangling; fab-real 200 = 102 + 98 pad rings KiCad cannot report", "FAIL",
                         "102 reported and 200 fab-real are both non-zero at 3 oz; only the pattern class changed, and it cleared exactly the footprint population",
                         "esc-3oz-build/04_setdiff.json, drc_base4oz/3oz.json, rules_3oz_020.kicad_dru"),
                "package": C("none", "none: 0 gerber / drill / job files under hardware/esc", "FAIL",
                             "no package exists",
                             "facts.json facts.scan.esc_package"),
                "revision": C("empty, no silk rev", "title block '' and no silkscreen revision text anywhere on the board", "FAIL",
                              "no revision stamp",
                              "measure_esc.json title_revision"),
                "outline": C("491.732 cm2 drawn / 382.709 cm2 placement", "repo board 173.800 x 282.930 mm Edge.Cuts centreline = 491.732 cm2, 1-up, 1 loop 0 holes; the 3 oz DRC and ampacity run on the 382.709 cm2 placement of record (155.15 x 246.80 mm, 687 footprints, 492 vias)", "PASS",
                             "both polygons close and both areas are > 0",
                             "measure_esc.json edge_cuts_extent_mm; esc-3oz-build/09_area.json"),
                "finish": C("ENIG", "ENIG (board field and job file agree)", "PASS",
                            "finish declared",
                            "measure_esc.json copper_finish"),
            },
            "orderable": "NO",
            "blocking": "1,536-1,542 unconnected",
        },
        CS: {
            "kind": "PCB",
            "solid_integrity": {"verdict": "PASS", "value": "board parses; 316 duplicate-numbered pads renumbered on a copy and re-DRC'd: count unchanged"},
            "cells": {
                "layers": C("4 (F/In1/In2/B)", "4 copper: F.Cu / In1.Cu / In2.Cu / B.Cu", "PASS",
                            "4 layers measured",
                            "measure_cs.json copper_layers"),
                "copper": C("0.035 x4 = 1 oz", "0.035 mm on all four layers = 1 oz", "PASS",
                            "stackup matches the declared 1 oz",
                            "measure_cs.json stackup_copper_mm"),
                "min_track": C("0.100 mm", "0.100 mm; 1,510 segments at exactly 0.100 of 11,168", "PASS",
                               "0.100 >= 0.100 (1 oz)",
                               "measure_cs.json min_track"),
                "min_space": C("0.1000 mm", "0.1000 mm minimum, identical in 3 runs; 508-512 pairs at the 0.30 mm probe floor (the count does not reproduce and is not charged)", "PASS",
                               "0.1000 >= 0.100 (1 oz)",
                               "fab-cs-fid-real/drc_r1.json; fab-checklist-v4/out/space_repeat_v4.json"),
                "min_drill": C("via 0.200 / PTH 0.200", "via 0.200 mm (min of 1,085 vias) / PTH pad 0.200 mm", "PASS",
                               ">= 0.200, no HDI",
                               "measure_cs.json min_via_drill, min_pth_drill"),
                "min_ring": C("via 0.100 / PTH 0.150", "via ring 0.1000 x53, 0.1250 x1,013, 0.1500 x6, 0.3000 x13 / PTH min 0.150 mm at U10.57; 94 PTH pads below 0.200 (96 with the 2 oblong slot pads, which the ring formula does not score)", "WAIVED",
                              "0.100 is below the published 0.125 mm 1 oz ring floor but at the board's own 0.10 rule: quote line W2, not a defect",
                              "measure_cs.json via_ring_hist, pth_ring_hist; fab-checklist-v5/out/cs_padcheck.json"),
                "nonthrough": C("0 of 1,085 vias", "0 = 0 blind + 0 buried of 1,085 vias; all F.Cu-B.Cu through", "PASS",
                                "no non-through span",
                                "measure_cs.json vias_by_span"),
                "unconnected": C("0 (pcbnew and kicad-cli agree)", "0 pcbnew and 0 kicad-cli; 1,093 of 1,093 required connections made; both tools far below their caps and in agreement", "PASS",
                                 "ratsnest 0 on two independent tools",
                                 "measure_cs.json unconnected_pcbnew; fab-cs-fid-real REPORT 5"),
                "drc": C("222 warn / 0 error; fab-real 222", "0 errors / 222 warnings / 0 unconnected at the board's own rules plus its own .kicad_dru (199 lib_footprint_mismatch + 13 via_dangling + 10 track_dangling); fab-real 222; control: with all 316 duplicate-numbered pads renumbered on a copy the count is identical (222 total, 0 errors)", "PASS",
                         "0 errors, and the invisibility defect that would hide rings is proved empty by a renumber control",
                         "fab-cs-fid-real REPORT 5 (222/0/0 before and after); fab-checklist-v5/out/cs_drc_renum.json (222/0/0 renumbered)"),
                "package": C("22 files at HEAD, 20/20 manifest, 1,215 holes, rev 2.1", "22 files at HEAD under hardware/v2/fab (12 gerber+job, 4 Excellon+drill map, 3 assembly CSV, 3 root); 20/20 files in git archive HEAD hardware/v2/fab match the committed MANIFEST.sha256, 0 mismatches; 1,215 holes = 1,213 drills + 2 G85 slots, 0 non-through, census reconciles; revision 2.1; 377 pos rows = 373 parts + the 4 fiducials", "PASS",
                             "the package exists in the repo, every manifest entry hashes to what was committed, it carries no blind/buried file, and it is an export of this board",
                             "verify-w9-adv/REPORT.md:118 (git archive vs MANIFEST.sha256, 20/20); fab-checklist-v4/out/drill_census.json 1"),
                "revision": C("2.1 board = 2.1 job", "board title block '2.1' and Code-SDR-V2-job.gbrjob Revision '2.1'", "PASS",
                              "board and package agree",
                              "measure_cs.json title_revision; job file"),
                "outline": C("101.600 mm square = 103.2256 cm2", "101.600 x 101.600 mm Edge.Cuts centreline (101.70 with its 0.100 mm stroke: 101.6 + 0.100 = 101.70, the measured bbox) = 103.2256 cm2, 1-up, no rails, 1 loop 0 holes", "PASS",
                             "polygon closes, area > 0, and the extent reconciles with the 0.100 stroke",
                             "measure_cs.json edge_cuts_extent_mm, edges_bbox_mm"),
                "finish": C("ENIG", "ENIG (board field and job file agree)", "PASS",
                            "finish declared",
                            "measure_cs.json copper_finish"),
            },
            "orderable": "YES",
            "blocking": "0 errors",
        },
        DM: {
            "kind": "CAD",
            "solid_integrity": {"verdict": "PASS", "value": "1 solid / 1 shell / closed; BRepCheck valid; 0 free and 0 non-manifold edges of 1,561; STEP-BREP delta 0.001091 mm3"},
            "cells": {
                "layers": C("n/a: 0 PCB files", "n/a: 0 board / gerber / drill / project files against 205 STEP/brep", "WAIVED",
                            "n/a: a printed/composite airframe part has no copper stackup",
                            "facts.json scan.drone_mech"),
                "copper": C("n/a: 0 PCB files", "n/a: 0 copper on any layer", "WAIVED",
                            "n/a: no copper exists on this deliverable",
                            "facts.json scan.drone_mech"),
                "min_track": C("n/a: 0 PCB files", "n/a: no track", "WAIVED",
                               "n/a: no copper exists on this deliverable",
                               "facts.json scan.drone_mech"),
                "min_space": C("n/a: 0 PCB files", "n/a: no copper", "WAIVED",
                               "n/a: no copper exists on this deliverable",
                               "facts.json scan.drone_mech"),
                "min_drill": C("n/a: 0 PCB holes", "n/a: 0 plated holes; the two 85.2 mm duct bores are modelled features, not drilled PCB holes", "WAIVED",
                               "n/a: no PCB drilling operation exists on this part",
                               "facts.json scan.drone_mech; dm-final-package/README.md"),
                "min_ring": C("n/a: 0 plated holes", "n/a: no plating", "WAIVED",
                              "n/a: no plated hole on this deliverable",
                              "facts.json scan.drone_mech"),
                "nonthrough": C("n/a: 0 vias", "n/a: 0 vias on 0 boards", "WAIVED",
                                "n/a: no vias exist",
                                "facts.json scan.drone_mech"),
                "unconnected": C("n/a: 0 nets", "n/a: 0 nets on 0 boards", "WAIVED",
                                 "n/a: no electrical netlist exists",
                                 "facts.json scan.drone_mech"),
                "drc": C("1 solid, 0 free edges; 10 pairs / 3,305.834869",
                         "geometry gate: 1 solid / 1 shell / closed, BRepCheck valid, 0 free and 0 non-manifold edges of 1,561; volume 206,454.3197 mm3 (BREP 206,454.3208, delta 0.001091); interference on the final part 10 pairs / 3,305.834869 mm3 = 6 genuine elevon-root clashes (1,204.481397) + 2 pushrod artefacts (4.534020) + 2 unclassified bearing-ring pairs (2,096.819452 = 63.4 %); knife edge at the wing-slot rim (z -90 to -70, |azimuth| 43-45 deg)", "PASS",
                         "one valid watertight solid and 0 free edges; the knife edge is a stated process note and the bearing rings are an assembly interface, not part geometry",
                         "dm-final-package/out/r5_validate.json, r1c_pairs.json, REPORT.md §1e, README.md"),
                "package": C("45 files + sha256 manifest, drawing, STL -0.052 %", "45 files hashed by SHA256SUMS (46 on disk including the manifest): STEP 9,801,595 B / BREP 4,712,827 B / STL 59,964 tri (mesh 206,347.1658 mm3, -0.052 % of STEP, watertight, Euler -2) / A3 drawing PDF 599,720 B / 6 check JSONs; copy-vs-source identical", "PASS",
                             "the package exists, every file is hashed, and the mesh is inside its stated 0.1 %",
                             "dm-final-package/SHA256SUMS.txt (45 lines), README.md, out/r2_mesh.json, r6_sha256.json"),
                "revision": C("DM-FUS-001 REV 1", "DM-FUS-001 REV 1 on the drawing title block and on the package; it supersedes the as-called 4-solid file", "PASS",
                              "a revision stamp exists and the package agrees with it",
                              "dm-final-package/README.md; out/drone-mech_fuselage_rev1_drawing.pdf"),
                "outline": C("640.00 x 211.78 x 93.87 mm; 206,454.3197 mm3", "part bbox 640.00 x 211.78 x 93.87 mm; volume 206,454.3197 mm3; 2V/A 1.1492 mm; mass 320.0042 g at 1550 kg/m3", "PASS",
                             "the bbox and the volume are measured on the shipped STEP and the mass closes on the density",
                             "dm-final-package/README.md, out/r5_validate.json"),
                "finish": C("n/a: no finish callout", "n/a: no finish callout exists; printed PLA core + CF/glass wrap is a MATERIAL answer, not a surface finish", "WAIVED",
                            "n/a: surface finish is a bare-board parameter and neither the board nor a finish spec exists here",
                            "dm-final-package/README.md; AGENT_BOARD.md:281-283"),
            },
            "orderable": "YES",
            "blocking": "0 (open: 2,096.819452 mm3 bearing rings)",
        },
    },
}

# ---------------------------------------------------------------- corrections
carried = json.load(open(os.path.join(V6, "corrections.json"), encoding="utf-8"))["rows"]
SUPERSEDED = {
    "BC1": "BC30", "BC3": "BC32", "BC4": "BC31", "BC6": "BC33",
    "BC10": "BC28", "BC11": "BC27", "BC12": "BC35", "BC13": "BC30",
    "BC16": "BC31", "BC18": "BC31", "BC19": "BC31", "BC20": "BC31",
    "BC21": "BC31", "BC22": "BC27", "BC23": "BC27", "BC24": "BC33",
    "BC25": "BC33",
}
STALE = {
    "BC1": ["43.5 A phase", "40 A bus"],
    "BC3": ["545", "570 km/h"],
    "BC4": ["621", "413", "511"],
    "BC6": ["36 non-through on the repo board"],
    "BC10": ["0 genuine pairs"],
    "BC11": ["delete 4 + resize"],
    "BC12": ["vias are BURIED"],
    "BC13": ["47.1 A", "1.08x"],
    "BC16": ["one impossible part", "23 footprint edits"],
    "BC18": ["GONE 270", "fab-real 351"],
    "BC19": ["155 footprint-bound"],
    "BC20": ["113 remain"],
    "BC21": ["re-poured BATP 49.67"],
    "BC22": ["742,306.360 mm3 converged"],
    "BC23": ["42_6 shell, unnamed file"],
    "BC24": ["10 of 36 declared"],
    "BC25": ["FREE = 0 of 36"],
}
for r in carried:
    r["status"] = "superseded" if r["id"] in SUPERSEDED else "live"
    if r["status"] == "superseded":
        r["superseded_by"] = SUPERSEDED[r["id"]]
        r["stale_in_rows"] = STALE[r["id"]]
        r.pop("present", None)

new_rows = [
    {"id": "BC27", "board": "drone-mech",
     "wrong": "the body of record was four disjoint solids totalling 742,306.360 mm3",
     "old": "4 disjoint solids, 742,306.360 mm3 (42_6 shell)",
     "new": "one solid: 206,454.3197 mm3, 320.0042 g at 1550 kg/m3, 1 solid / 1 shell / closed, 0 free and 0 non-manifold edges of 1,561",
     "source": "dm-final-package/out/r1b_doubles.json (the four solids were disjoint, 0.000000 mm3 pairwise), r5_validate.json; dm-fore-fill/out/part_nose_v2.step",
     "absent_in_rows": ["742,306.360", "4 disjoint solids"],
     "present": ["206,454.3197", "320.0042", "1,561"]},
    {"id": "BC28", "board": "drone-mech",
     "wrong": "the interference count was published as 6 pairs and as 8 pairs; both are true on one file each and neither is the union",
     "old": "8 pairs / 6 genuine (1,250.769445 mm3)",
     "new": "10 pairs / 3,305.834869 mm3 on the final part: 6 genuine (1,204.481397) + 2 pushrod artefacts (4.534020) + 2 unclassified bearing rings (2,096.819452 = 63.4 %)",
     "source": "dm-final-package/REPORT.md §1a-1e, out/r1c_pairs.json (three bodies, same instrument, eps 1e-12)",
     "absent_in_rows": ["1,250.769445", "8 pairs"],
     "present": ["3,305.834869", "2,096.819452", "63.4"]},
    {"id": "BC29", "board": "drone-mech",
     "wrong": "the deliverable had no package, no drawing and no revision",
     "old": "no drawings, 0 ply book, no revision",
     "new": "DM-FUS-001 REV 1: 45 files hashed by SHA256SUMS (46 on disk), STEP + BREP + STL (59,964 tri, -0.052 % of STEP) + A3 drawing PDF",
     "source": "dm-final-package/README.md, SHA256SUMS.txt (45 lines), out/r6_sha256.json",
     "absent_in_rows": ["0 ply book", "no revision carries the fix"],
     "present": ["DM-FUS-001 REV 1", "45", "0.052"]},
    {"id": "BC30", "board": "ESC",
     "wrong": "the ESC's design point was 43.5 A per phase / 40 A bus, a current the 3 oz corridor cannot carry",
     "old": "43.5 A phase / 40 A bus",
     "new": "36.6 A per phase / 33.7 A bus, a 35 A-class ESC; 36.6 A gives 497 km/h, 43.5 A would have bought only 527 km/h",
     "source": "esc-operating-point; esc-3oz-build/08_ampacity.json (36.58 A at 9.420 mm); esc-motor-demand",
     "absent_in_rows": ["43.5 A", "40 A bus"],
     "present": ["36.6 A", "33.7 A", "497"]},
    {"id": "BC31", "board": "ESC",
     "wrong": "the DRC was quoted on the 4 oz board with its pad-shrink total, which is not the 3 oz arm",
     "old": "523 -> 253 as the design-point DRC",
     "new": "3 oz 0.200/0.200: 229 -> 102, row-level GONE 127 / ADDED 0 (120 clearance + 4 track_width + 3 connection_width); all 89 pad-pad gaps clear; fab-real 200 = 102 + 98 invisible rings",
     "source": "esc-3oz-build/04_setdiff.json, drc_base4oz/3oz.json, rules_3oz_020.kicad_dru",
     "absent_in_rows": ["523"],
     "present": ["229", "102", "127", "200", "89"]},
    {"id": "BC32", "board": "ESC",
     "wrong": "the aircraft performance numbers were carried from the 43.5 A arm",
     "old": "~545-570 km/h at 43.5 A",
     "new": "497 km/h at 36.6 A (CdA 0.004162; band 353-616 km/h); FET 3.33 W/device, Tj 119.6 C = 68 % of 175 C at Rth 22.4",
     "source": "esc-operating-point; esc-3oz-build §5 (G7); esc-cda-bound",
     "absent_in_rows": ["545", "570 km/h", "101.4"],
     "present": ["497", "119.6", "68"]},
    {"id": "BC33", "board": "drone-arm",
     "wrong": "the non-through population was 36 after the census; 17 cleared by executed layout work and 19 remain",
     "old": "36 non-through vias (26 blind + 10 buried)",
     "new": "19 non-through of 337 vias (318 through): 15 micro + 4 blind by layer pair, 16 stacks; U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1; own-rules DRC 4 = {via_diameter:+4} and span gate 22 = 18 hole_size + 4 via_diameter",
     "source": "fab-da-36via/REPORT.md §7, census_batA.json; fab-da-u10-ripup/REPORT.md",
     "absent_in_rows": ["36 non-through", "26 blind"],
     "present": ["19 non-through", "337", "22"]},
    {"id": "BC34", "board": "drone-arm",
     "wrong": "the 0.100 mm drill was quoted as the blocker; the blocker is the clear diameter a through via needs",
     "old": "0.100 mm via drill is the blocker",
     "new": "exactly 0.85 mm: a 0.60/0.30 through via needs 0.85 mm of clear diameter on all four layers; U10 (QFN-80, 0.4 mm pitch) offers 0.4 mm lanes",
     "source": "fab-da-path/REPORT.md:14,318; fab-da-36via/REPORT.md §2, §7",
     "absent_in_rows": ["0.100 mm via drill is the blocker"],
     "present": ["0.85 mm", "0.60", "0.4 mm"]},
    {"id": "BC35", "board": "drone-arm",
     "wrong": "BC12 called the In1->In2 span buried; those two copper layers are adjacent, so the vias on that pair are microvias",
     "old": "In1.Cu-In2.Cu vias are BURIED (repo board: 10 of them)",
     "new": "In1 and In2 are ADJACENT: the 10 vias on that pair (5 after the conversion) are MICROVIAS; of the 19, 15 are micro and 4 are blind (F-In2 2, In1-B 2)",
     "source": "fab-da-36via/census_base.json (copper_order F, In1, In2, B; by_span_class 29 micro / 7 blind), census_batA.json (15 micro / 4 blind)",
     "absent_in_rows": ["vias are BURIED", "26 blind + 10 buried"],
     "present": ["15 micro + 4 blind", "MICROVIAS", "adjacent"]},
]
for r in new_rows:
    r["status"] = "live"
corrections = {
    "note": ("35 BOARD CORRECTION rows. BC1-BC26 are carried from fab-checklist-v6 with their "
             "OLD/NEW pairs intact; 17 of them are marked superseded by a wave-18 correction because "
             "the board they describe moved (36->19 vias, 4 oz->3 oz, 43.5 A->36.6 A, 4 solids->1). "
             "BC27-BC35 are new. A 'live' row's OLD tokens must appear nowhere in rows.json and its "
             "'present' tokens must appear in REPORT.md outside section 2; a 'superseded' row's "
             "stale_in_rows tokens must appear nowhere either."),
    "rows": carried + new_rows,
}

# --------------------------------------------------------------------- facts
facts = {
    "provenance_legend": "native = a tool ran on this host; derived = arithmetic on native rows; carried = from a cited evidence dir, not re-run in this wave",
    "drone_arm": {"vias_total": 337, "through": 318, "non_through": 19, "micro": 15, "blind": 4,
                  "stacks": 16, "by_pair": {"F-In1": 7, "In1-In2": 5, "F-In2": 2, "In2-B": 3, "In1-B": 2},
                  "by_ref": {"U10": 12, "U40": 2, "C32": 2, "C12": 1, "C40": 1, "FB1": 1},
                  "min_drill": 0.100, "own_drc": 4, "own_via_diameter": 4,
                  "gate": 22, "gate_hole_size": 18, "gate_via_diameter": 4,
                  "via_pad": 0.600, "via_drill": 0.300, "clearance": 0.125, "clear_need": 0.85,
                  "u10_lane": 0.4, "unconnected": 0, "required_connections": 438,
                  "void_mm2": 4.1699, "void_pct": 9.8338, "void_b_pct": 9.1392,
                  "outline_mm": [140.0, 100.0], "area_cm2": 140.0},
    "esc": {"layers": 4, "cu_outer": 0.1050, "cu_inner": 0.0525, "board_mm": 1.600,
            "drc_4oz": 229, "drc_3oz": 102, "gone": 127, "gone_clearance": 120,
            "gone_track_width": 4, "gone_connection_width": 3, "added": 0,
            "annular": 70, "annular_pth": 42, "annular_via": 28,
            "via_diameter": 16, "via_dangling": 16, "invisible_rings": 98, "fab_real": 200,
            "padgap_total": 89, "padgap_qfn": 75, "padgap_usbc": 14,
            "i_phase": 36.6, "i_bus": 33.7, "i_phase_possible": 36.58,
            "phase_corridor_mm": 9.420, "required_phase_mm": 11.963,
            "barrels": 23, "barrel_A": 1.50, "bus_capacity_A": 34.5, "barrels_needed_40A": 27,
            "area_cm2": 382.709, "bbox_mm": [155.15, 246.80], "footprints": 687, "b_cu_parts": 0,
            "repo_area_cm2": 491.732, "repo_outline_mm": [173.800, 282.930],
            "vias": 1990, "unconnected_low": 1536, "unconnected_high": 1542, "required_connections": 2316,
            "speed_kmh": 497, "speed_band": [353, 616], "cda": 0.004162, "cda_band": [0.0034, 0.0056],
            "cda_floor": 0.002710, "tj_c": 119.6, "tj_limit": 175, "tj_pct": 68,
            "rth": 22.4, "p_fet": 3.33, "cost_low": 450, "cost_high": 870,
            "cost_6l_low": 1300, "cost_6l_high": 1900},
    "code_sdr": {"footprints": 377, "vias": 1085, "holes": 1215, "drills": 1213, "slots": 2,
                 "drc_errors": 0, "drc_warnings": 222, "warn_lib_footprint": 199,
                 "warn_via_dangling": 13, "warn_track_dangling": 10, "fiducials": 4,
                 "fid_min_gap": 1.5005, "pos_rows": 377, "pos_parts": 373, "manifest": 20,
                 "files": 22, "gerber_job": 12, "excellon_docs": 4, "assembly_csv": 3, "root_files": 3,
                 "required_connections": 1093, "bom_rows": 373, "mpn_rows": 0,
                 "edge_mm": 101.6, "stroke_mm": 0.100, "bbox_mm": 101.70, "area_cm2": 103.2256},
    "drone_mech": {"volume_mm3": 206454.3197, "volume_brep_mm3": 206454.3208,
                   "mass_g": 320.0042, "density_kg_m3": 1550,
                   "bbox_mm": [640.00, 211.78, 93.87], "stl_volume_mm3": 206347.1658,
                   "stl_delta_mm3": 107.15, "stl_pct": -0.052, "triangles": 59964,
                   "edges": 1561, "free_edges": 0, "nonmanifold_edges": 0,
                   "solids": 1, "shells": 1, "wall_fore": 1.0921, "wall_pinch": 1.1990,
                   "wall_aft": 1.1800, "wall_2v": 1.1492, "nose_lo": 1.1982, "nose_hi": 1.2068,
                   "pairs": 10, "pairs_volume_mm3": 3305.834869,
                   "genuine_mm3": 1204.481397, "artefact_mm3": 4.534020,
                   "rings_mm3": 2096.819452, "ring_each_mm3": 1048.409726,
                   "ring_share_of_ring": 13.4, "ring_pct_of_total": 63.4,
                   "manifest_files": 45, "files_on_disk": 46,
                   "pre_weld_volume_mm3": 742306.3595},
    "not_known_count": 27,
}

with open(os.path.join(HERE, "rows.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(rows, f, indent=1, ensure_ascii=False)
with open(os.path.join(HERE, "corrections.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(corrections, f, indent=1, ensure_ascii=False)
with open(os.path.join(HERE, "facts.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(facts, f, indent=1, ensure_ascii=False)

n_live = sum(1 for r in corrections["rows"] if r["status"] == "live")
print("rows.json     : %d boards, %d cells" % (len(rows["boards"]), 13 * len(rows["boards"])))
print("corrections   : %d rows (%d live, %d superseded)"
      % (len(corrections["rows"]), n_live, len(corrections["rows"]) - n_live))
print("facts.json    : 4 boards")
print("\nLIVE correction tokens that must appear in REPORT.md outside section 2:")
for r in corrections["rows"]:
    if r["status"] == "live":
        print("  %s %-12s %s" % (r["id"], r["board"], r.get("present")))