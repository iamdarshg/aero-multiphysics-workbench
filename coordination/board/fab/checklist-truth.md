# Master pre-fab checklist — r50

**Rewritten against the current verified state. Supersedes `evidence/fab-checklist-final/REPORT.md`
(462 lines, wave 18), which describes a programme that has since moved on every board except
Code-SDR.**

- **Date:** 2026-11-18 · **Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), cadquery 2.7.0 /
  OCP 7.8.1.1 (`C:/Program Files/Python312/python.exe`) · **Write scope:** this directory only.
  No repo was written, no commit, no reset; every board and part was read from a copy or via `git show`.
- **Basis:** the 30 cells below are **computed, not typed**. `build.py` derives every verdict from the
  row's metrics with the rules in §5 and emits the marked blocks; `check_truth.py` re-derives every
  verdict and tally from the same metrics and fails if this page disagrees with them.
- **Carried, not re-measured.** No instrument was re-run for this sheet. Every number is tagged with
  its provenance (§7): the tool that measured it in this programme, or the report and section it is
  carried from. The one live re-read is dev-board's DRC JSON (`10` rows, `8` after the two documented
  exclusions), which is read from disk, not re-run.
- **The rule this sheet will not break:** a summary row may not print PASS while its own detail row
  prints FAIL. §9 prints the reconciliation, and the checker fails the page if it drifts.

**One line per board — the whole sheet in six lines.**

| board | status today | the single thing that blocks it |
|---|---|---|
| Code-SDR V2 rev 2.1 | **ORDERABLE, bare board. 5 PASS / 0 WAIVED / 0 OPEN.** | nothing engineering; 373/373 BOM rows have no MPN (sourcing) |
| dev-board (radar/radio, HDI, revision unstamped) | **NOT ORDERABLE. 2 PASS / 0 WAIVED / 3 OPEN.** | 8 real geometry defects (5 copper_sliver, 2 holes_co_located, 1 track_dangling) — and, independently, a blank SurfaceFinish |
| drone-arm main rev B (6-layer, all-through) | **NOT SENDABLE. 2 PASS / 0 WAIVED / 3 OPEN.** | 7 U10 pads at 0.4 mm pitch cannot escape (0.18–0.30 mm vs 0.237 mm needed) |
| drone-mech assembly (fuselage REV 1 + fix set) | **FUSELAGE PART FAB-READY; ASSEMBLY NOT RELEASED. 1 PASS / 2 WAIVED / 2 OPEN.** | the vane root has no slot (bracket: 0 cylindrical faces) |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | **NOT ROUTED. 1 PASS / 0 WAIVED / 4 OPEN.** | 187 unconnected on the corrected board (60 on the routed copy) |
| ESC control rev_a (2-layer, 1 oz) | **NO NETLIST. 1 PASS / 0 WAIVED / 4 OPEN.** | 648 of 768 pads are netless; the 0-unconnected result is vacuous |

## 1. What changed since the 462-line sheet

The old sheet scored **four boards across 13 physical columns** (52 cells) and called two of them
orderable. This sheet scores **six boards across the five objective conditions** (30 cells) and calls
one of them orderable. The change is not a stricter grader: it is a different programme.

| # | change | old sheet | now | why it matters |
|---:|---|---|---|---|
| 1 | **drone-arm's HDI is gone** | 19 non-through = 15 micro + 4 blind, blocker **0.85 mm** | **0 non-through**, 343 vias all through, **6 layers**, min drill 0.200 | the sheet's headline "physics, not layout" blocker no longer exists; the board is a different board and the blocker moved to U10's fan-out |
| 2 | **dev-board enters the sheet** | absent | **201 non-through** (186 micro + 1 blind + 14 buried), proven unremovable (+545 violations / 80 shorts if forced), **recommendation: ACCEPT HDI** | the programme's "no HDI anywhere" rule now has exactly one board that needs an explicit exception |
| 3 | **ESC stopped being one board** | monolithic rev_b, 173.9 × 283.1 mm, 687 fps, DRC 229 → 102 | **power 151.77 × 122.55 mm + control 107 × 60 mm**, DRC 527 (capped) / 37 | every ESC number in the old sheet describes a board that will not ship |
| 4 | **drone-mech's row changed population** | the fuselage **part**, 5 of 5 | the **assembly**: 0 genuine clash, collar fixed, but 4 open geometry items and no assembly package | the fuselage is still fab-ready; "5 of 5" no longer describes the thing being scored |
| 5 | **dev-board's DRC was graded PASS while 8 of its rows were defects** | — (new board) | condition 1 is **OPEN** (7 fabrication-severity rows) | an "all warnings" DRC is not clean when the warnings are slivers and co-located holes — BC51 |

**The single biggest change: the HDI picture inverted.** drone-arm's 19 non-through vias are gone, and
in the same review the sheet has to admit the opposite case — dev-board's **201** non-through vias are
**measured, and forcing them to through vias breaks the board** (10 → 555 violations, 80 shorts, for
+545). So the programme rule "no HDI except where explicitly accepted" now has an accepted exception
on record, and drone-arm's old 0.85 mm sentence must never be quoted again. A reader of the old sheet
would draw the opposite conclusion on both boards.

**What did not change:** Code-SDR is still complete, and still cannot be assembled (373/373 MPNs).
The five objective conditions are still the right five. The correction discipline is unchanged — every
superseded row names its successor.

## 2. The conditions table — 30 cells, one row per condition per board

Each cell is **PASS with evidence**, **WAIVED** for an objective that does not apply (a CAD part has
no DRC), or **OPEN with what remains**. There are **no UNKNOWN and no blank cells**. A WAIVED cell is
never a hidden defect: a real defect is OPEN, or it is a PASS that carries a priced quote line in its
evidence text. The six boards are counted separately because the ESC power and control boards have
different rules, different layers, different stacks and different blockers; averaging them would hide
both.

<!-- BEGIN CONDITIONS -->
| board | # | objective | verdict | evidence (value + source) | provenance | what remains |
|---|---:|---|---|---|---|---|
| Code-SDR V2 rev 2.1 | 1 | DRC-clean at the correct rules | **PASS** | 0 errors / 222 warnings / 0 unconnected at the board's own rules plus its own `.kicad_dru`; the 222 are 199 `lib_footprint_mismatch` (library-copy drift), 13 `via_dangling`, 10 `track_dangling`, and a renumber control leaves the count identical (222/0/0). No fabrication-severity row. | M-2TOOLS (kicad-cli 9.0.7 + pcbnew); C:fab-cs-fid-real:5; C:fab-checklist-v5/cs_drc_renum.json | — |
| Code-SDR V2 rev 2.1 | 2 | zero unconnected | **PASS** | 0 `pcbnew GetUnconnectedCount(False)` and 0 `kicad-cli`; 1,093 of 1,093 required connections made; both tools far below their caps and in agreement. | M-2TOOLS; C:measure_cs:unconnected_pcbnew | — |
| Code-SDR V2 rev 2.1 | 3 | zero unresolved geometry defects | **PASS** | 0 non-through of 1,085 vias; 1,215 holes = 1,213 drills + 2 G85 slots, census reconciles; 4 fiducials, min gap 1.5005 mm; the 0.100 mm ring is at the board's own 0.10 rule and is a quote line (W2), not a defect. | C:fab-checklist-v4/out/drill_census.json; C:fab-cs-fid-real:14 | — |
| Code-SDR V2 rev 2.1 | 4 | a revision-stamped package validated against its own board | **PASS** | 22 files at HEAD under `hardware/v2/fab`; 20/20 files in `git archive HEAD` match the committed `MANIFEST.sha256` (0 mismatches); rev 2.1 on the board title block and in `Code-SDR-V2-job.gbrjob`; ENIG; no blind/buried drill file. | M-SHA; C:verify-w9-adv:118; C:measure_cs:title_revision | — |
| Code-SDR V2 rev 2.1 | 5 | no open checklist cell | **PASS** | All five conditions carry a verdict, a value and a resolved source; 13 columns reconciled (0.100 stroke: 101.6 + 0.100 = 101.70). | this sheet | — |
| dev-board (radar/radio, HDI, revision unstamped) | 1 | DRC-clean at the correct rules | **OPEN** | 10 warnings / 0 errors / 0 unconnected with full companions (`.kicad_pro`, fp-lib-table, local `.pretty`); 2 are the narrowly excluded `lib_footprint_mismatch` (silkscreen-only, pads identical); of the remaining 8, **5 `copper_sliver` + 2 `holes_co_located` are fabrication-severity**, and 1 `track_dangling` is an annotation charged under condition 3. Without companions the same board read 70 (52 fake `lib_footprint_issues`). | M-KICAD (re-read drc_full.json: 10 / drc_excluded.json: 8); C:D:/devboard-evidence/dvb-exclusions/EXCLUSIONS.md | clear the 7 fabrication-severity rows, then re-run with companions; a DRC carrying 7 real defects is not clean even when every row is a warning |
| dev-board (radar/radio, HDI, revision unstamped) | 2 | zero unconnected | **PASS** | 0 on all four DRC runs (own rules, 0.200/1 oz, deliberately absurd 5.000 mm, no `.dru`); `pcbnew` and `kicad-cli` agree, below the 499 cap. | M-2TOOLS; C:dev-board-assessment:2 | — |
| dev-board (radar/radio, HDI, revision unstamped) | 3 | zero unresolved geometry defects | **OPEN** | 8 real, none cleared: 5 `copper_sliver` (2 Top, 2 Bottom, 1 Power Layer 2), 2 `holes_co_located` (two drills in one place), 1 `track_dangling`. | M-KICAD (drc_excluded.json: 8); C:dev-board-assessment:2 | the 8 real defects stand; no fix is recorded in any evidence directory |
| dev-board (radar/radio, HDI, revision unstamped) | 4 | a revision-stamped package validated against its own board | **OPEN** | `release/final/`: 49-entry SHA256SUMS = 46 byte-identical + 2 only after CRLF->LF (the two BOMs, proven artefact) + 1 genuinely stale (`RELEASE_NOTES.md`) = 48/49, 0 missing; POS 292 vs 320 footprints = 28 short; **SurfaceFinish EMPTY in both `.gbrjob`** (fab cannot choose a finish); revision is not in the title block. A re-export against the board has not been reproduced (`dvb-package-verify` is a skeleton). | C:dev-board-assessment:3-4; M-SHA (manifest re-hash) | set SurfaceFinish (one field), resolve 28 POS rows (DNP markers or regenerate), regenerate RELEASE_NOTES.md, stamp a revision, then re-export and re-hash |
| dev-board (radar/radio, HDI, revision unstamped) | 5 | no open checklist cell | **PASS** | All five conditions carry a verdict, a value and a resolved source; the HDI population is quoted by span (201 = 186 + 1 + 14) and the 183 single-span concentration is stated. | this sheet | — |
| drone-arm main rev B (6-layer, all-through) | 1 | DRC-clean at the correct rules | **OPEN** | 37 at the board's own rules: 30 `track_dangling` (annotation stubs), **2 `track_width`** (inherited 0.15 mm necks on /LSM_INT2 and /RF_MOSI) and **5 `via_diameter`** (the inherited 0.4/0.2 class). Set diff against the 42 baseline: +2 / -7, so no new geometry defect was added, but 7 error-severity rows stand. | M-KICAD; C:da-final-package:3 | dispose of the 5 via_diameter (waive / re-rule / convert) and re-route the 2 0.15 mm necks; the 30 dangling are stubs, not defects |
| drone-arm main rev B (6-layer, all-through) | 2 | zero unconnected | **OPEN** | 10 on `pcbnew` and 10 on `kicad-cli` (both below the cap, so both are real): 7 U10 pads, 2 cross-layer joins, 1 GND fill split. 15 -> 10: 5 closed (4 inherited from the interrupted attempt, 1 routed here — /CAN_MOSI 16.816 mm); the U10.62 GND spoke reshaped the GND item rather than lowering the count. | M-2TOOLS; C:da-final-package:1.5 | re-fan-out the U10 ring (240 tracks + 47 vias on 43 nets sit within 1.2 mm of a U10 pad; a partial rip is zero-sum) or declare the 0.4/0.2 class |
| drone-arm main rev B (6-layer, all-through) | 3 | zero unresolved geometry defects | **OPEN** | The geometric defect is the same 7 pads: a 0.2 mm track needs 0.237 mm and every remaining break's best cell within 3 mm is 0.18-0.30 mm; a 0.6 mm via needs 0.425 mm and the maximum exact clearance is 0.42 mm. U10 is a 90-pad 0.4 mm-pitch part (0.2 pad / 0.2 gap). | C:da-final-package:1.3,4 | no local fix exists: re-fan-out, change the pitch, or move the part |
| drone-arm main rev B (6-layer, all-through) | 4 | a revision-stamped package validated against its own board | **PASS** | Rev-B package built from `r_final.kicad_pcb` sha256 CA2093D1...: 20 files, 6/6/6 copper layers (board / gerbers / gbrjob), 140 x 100 outline, drills+slots reconcile by diameter, POS 161 = 165 - 4 excluded, gbrjob LayerNumber 6 and SurfaceFinish ENIG, ProjectId main_rev_b / B on 16 carriers; 34 of 36 assertions pass, and the 2 fails are V30/V31, both the unconnected count (condition 2). | M-SHA; C:da-final-package:2 | — |
| drone-arm main rev B (6-layer, all-through) | 5 | no open checklist cell | **PASS** | All five conditions carry a verdict, a value and a resolved source; the old 19-via population is retired (0 non-through now). | this sheet | — |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | 1 | DRC-clean at the correct rules | **WAIVED** | n/a: no PCB, no DRC. The analogue gate passes on the part: 1 solid / 1 shell / closed, `BRepCheck` valid, 0 free and 0 non-manifold edges of 1,561, STEP<->BREP delta 0.001091 mm3. | M-OCCT; C:dm-close-clashes:6 | — |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | 2 | zero unconnected | **WAIVED** | n/a: a CAD part has no nets; the assembly's interference pair list is the analogue and it closes to 0 genuine. | C:dm-close-clashes:5a | — |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | 3 | zero unresolved geometry defects | **OPEN** | 4 open geometry items: (a) vane root — a slot is required and the bracket has **0 cylindrical faces**; (b) A2's rib sits 14.000 mm outboard of its mirror, so 196.000000 mm3 is the same joint with the rib out of the blade's path; (c) **third knuckle + bracket do not exist** — 33.265 mm unsupported root overhang, never analysed; (d) knife-edge residual **5.1162 deg** at z +172. The 8 genuine clashes themselves are 0.000000. | M-OCCT; C:dm-close-clashes:4a,7; C:programme state block | cut the vane root slot (3 features), mirror the A2 rib, model the third knuckle + bracket, close the knife edge (fillet or 0.3 mm rim offset) |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | 4 | a revision-stamped package validated against its own board | **OPEN** | The released package validates against its own **part**: DM-FUS-001 REV 1, 45 files hashed, STL -0.052 %, drawing PDF, copy-vs-source identical. But the fix set this sheet reports — trimmed elevons, bored collars — is carried as **BREP only** (`dm-close-clashes` B1: the wing cove does not round-trip through the OCP STEP writer), and **no assembly package exists**; nothing here is a STEP-delivered part. | M-SHA; C:dm-final-package; C:dm-close-clashes:B1 | re-export the trimmed elevons and bored collars as STEP and issue an assembly-level package with its own revision |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | 5 | no open checklist cell | **PASS** | All five conditions carry a verdict, a value and a resolved source; 0 genuine clash is quoted with its population (16 pairs / 1,229.794165 mm3). | this sheet | — |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 1 | DRC-clean at the correct rules | **OPEN** | 527 listed = **499 `clearance` (CAPPED, a per-type list cap; true count >= 499 and not quotable)** + 28 `silk_over_copper`. The 11 named items (3 shorting + 8 mask on J_H1 vs BAR2/Q3CL/Q6CL/Q6CH) are 0 after the +2.54 mm bank shift, set diff +0 / -11 normalised; 8 rule-gate runs prove the `.kicad_dru` is read (a 5 mm hole rule adds 120 rows). | M-KICAD (JSON read from disk); C:esc-corrections:0.1,5 | routing is the only thing that removes clearance rows; the total cannot be measured by this CLI, only bounded from below |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 2 | zero unconnected | **OPEN** | **187** on the corrected board (uncapped, both tools). **60** on the routed copy after 58 elements closed 127 of 187. The corrected board has 0 tracks/vias/zones and the routed copy predates the +2.54 shift and the pad deletion, so no single artefact carries both. | M-2TOOLS; C:esc-corrections:5; C:esc-route-power:5 | merge the 58-element power route onto the corrected board, then close the remaining 187 -> 60 (DGND 23, AGND 18, BATN_K 17, BATN 2) and the 134 signal nets that have one terminal each |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 3 | zero unresolved geometry defects | **OPEN** | Two unresolved classes. (a) **Copper capacity**: the routed phase conductor is 6.00 mm = **26.4 A against the settled 36.6 A/phase (72 %)** and the shared bus 31.0 A against 6 x 36.6 = 219.6 A (14 %); on the retired 80 A/phase basis the same copper is 33 %. (b) **Annular rings**: 28 via rings at 0.150 and 42 PTH at 0.150-0.175 sit under the published 0.200 3-oz floor — carried from the 3 oz arm of this stack; the split board's own rules accept 0.150 and its 527-row DRC reports no annular row. No non-through via, sliver, co-located hole or open outline exists. | C:esc-route-power:6; C:fab-checklist-final:1.1; C:esc-corrections:5 | widen the phase/bus copper to the chosen current basis (OQ-7) and obtain a written 0.150 ring grant or re-rule (OQ-8) |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 4 | a revision-stamped package validated against its own board | **OPEN** | `fab/power/` = 9 files + `.gbrjob` with `GeneralSpecs.Finish: ENIG` (KiCad's name for the Ucamco SurfaceFinish field). No revision stamp; no manifest; and the gerbers are of the **unrouted** board, while the routed copy has no package at all. | M-SHA; C:esc-corrections:6 | stamp a revision, merge the route, re-export and hash |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 5 | no open checklist cell | **PASS** | All five conditions carry a verdict, a value and a resolved source; the 499 is labelled CAPPED wherever it appears. | this sheet | — |
| ESC control rev_a (2-layer, 1 oz) | 1 | DRC-clean at the correct rules | **OPEN** | 37 at own rules: **16 error-severity** — 10 `clearance` (4 J1 coincident pad pairs at 0.0000 mm + 6 U9 pads at 0.150 vs 0.200), 2 `courtyards_overlap`, 4 `solder_mask_bridge` — plus 21 silk warnings. Routing adds nothing: set diff +0 / -0. | M-KICAD; C:esc-route-control:7 | fix J1's 4 coincident pad pairs and U9's 0.65 mm-pitch land (pads to 0.450 or a documented rule exception) |
| ESC control rev_a (2-layer, 1 oz) | 2 | zero unconnected | **OPEN** | 0 on both tools after routing 41/41 ground links. **The metric is vacuous**: a netless board reports zero unconnected however unrouted it is — 648 of 768 pads carry no net and 0 signal connections exist. | M-2TOOLS; C:esc-route-control:2.1,9 | a netlist (768/768 pads netted) is the only thing that makes the 648 netless pads and this zero mean anything; then re-route with the existing router |
| ESC control rev_a (2-layer, 1 oz) | 3 | zero unresolved geometry defects | **OPEN** | 16 geometry items: J1's 4 coincident pad pairs (copper shorted inside the land pattern), U9's 6 pads at 0.150, 2 courtyard overlaps, 4 mask bridges. All are placement/land-pattern; none is a routing defect. | C:esc-route-control:7 | land-pattern and placement fixes; the 1 nF caps are a median 16.829 mm from their ADC and need re-placing (< 2.0 mm) |
| ESC control rev_a (2-layer, 1 oz) | 4 | a revision-stamped package validated against its own board | **OPEN** | `fab/control/` = 7 files + `.gbrjob` with `Finish: ENIG`. No revision stamp, no manifest, and the package is of a placement mock: 648/768 pads netless, 0 signal connections, 0.45 % copper utilisation. | M-SHA; C:esc-corrections:6; C:esc-route-control:2.1 | a netlist, a revision stamp and a re-export |
| ESC control rev_a (2-layer, 1 oz) | 5 | no open checklist cell | **PASS** | All five conditions carry a verdict, a value and a resolved source; the vacuous zero is labelled as vacuous, not as a pass. | this sheet | — |
<!-- END CONDITIONS -->

## 3. Summary — derived from the 30 rows above

<!-- BEGIN SUMMARY -->
| board | PASS | WAIVED | OPEN | PASS of 5 | orderable | gating objectives met (c1-c4) | single blocker |
|---|---:|---:|---:|---:|---|---:|---|
| Code-SDR V2 rev 2.1 | 5 | 0 | 0 | **5 of 5** | **YES** (bare board) | 4 of 4 | nothing engineering: 373/373 BOM rows have no MPN, which stops the assembly PO only |
| dev-board (radar/radio, HDI, revision unstamped) | 2 | 0 | 3 | **2 of 5** | **NO** | 1 of 4 | 8 real geometry defects (5 copper_sliver, 2 holes_co_located, 1 track_dangling); the package is independently fab-blocked by a blank SurfaceFinish |
| drone-arm main rev B (6-layer, all-through) | 2 | 0 | 3 | **2 of 5** | **NO** | 1 of 4 | 7 U10 pads at 0.4 mm pitch cannot escape: 0.18-0.30 mm measured against 0.237 mm needed (10 unconnected) |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | 1 | 2 | 2 | **1 of 5** | **NO** (the fuselage part alone is fabricable) | 0 of 4 | the vane root has no slot: the servo bracket is 7 boxes / 42 planar faces / 0 cylindrical faces |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 1 | 0 | 4 | **1 of 5** | **NO** | 0 of 4 | 187 unconnected on the corrected board (60 on the routed copy; the two are different artefacts) |
| ESC control rev_a (2-layer, 1 oz) | 1 | 0 | 4 | **1 of 5** | **NO** | 0 of 4 | 648 of 768 pads are netless, so the 0-unconnected result is vacuous |
| **all six** | **12** | **2** | **16** | **30 cells** | **1 of 6** | — | — |
<!-- END SUMMARY -->

**Reading the tally.** 12 PASS / 2 WAIVED / 16 OPEN. **One board is orderable**: Code-SDR, bare
board. The 2 WAIVED cells are both drone-mech's non-applicable PCB objectives — they are not passes
and they are not waivers of a defect. **dev-board is the only board with two independent blockers**
(8 geometry defects and a blank finish); every other non-orderable board is stopped by one thing.
**No board's blocker is a number the sheet cannot point at**: §9 checks that each of the five
non-orderable boards names its blocker inside an OPEN cell.

- **Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today. 5 of 5.** 0 DRC errors, 0 unconnected on two
  tools, 0 non-through, 1,215 holes reconciled, 20/20 manifest entries, 22 committed package files,
  rev 2.1 on board and package, 4 fiducials at 1.5005 mm. Two quote lines, neither a defect: the
  0.100–0.125 mm ring (W2) and the 0.100 mm track/space at 1 oz. Assembly is not orderable: 373/373
  MPNs missing.
- **dev-board — NOT ORDERABLE. 2 of 5.** DRC at its own rules with full companions: **10 warnings,
  0 errors, 0 unconnected**; 2 are the excluded silkscreen-only `lib_footprint_mismatch`, and **8 are
  real** (5 `copper_sliver`, 2 `holes_co_located`, 1 `track_dangling`). The HDI is **201 non-through
  and unremovable** (all 201 → 10 → 555, +545 with 80 shorts; the 15 blind/buried alone → 48). The
  package is **48 of 49**, POS is **28 rows short**, **SurfaceFinish is empty** in both `.gbrjob`
  (fab-blocking), and no revision is stamped. HDI acceptance is the owner's call (OQ-1).
- **drone-arm main rev B — NOT SENDABLE. 2 of 5.** 6 layers, **0 non-through of 343**, min drill
  0.200, DRC **37** (set diff 42 → 37, +2 / −7), **10 unconnected on both tools**, RF void bit-identical
  at 4.1699 mm² / 9.8338 %. The rev-B package is real and internally consistent (20 files, 6/6/6
  copper, 371 hits, POS 161, ENIG, 34 of 36 assertions). The blocker is one thing: **7 U10 pads at 0.4 mm
  pitch** have a 0.18–0.30 mm escape against the 0.237 mm a 0.2 mm track needs. Not sendable today;
  everything else is verified.
- **drone-mech assembly — FUSELAGE PART FAB-READY; ASSEMBLY NOT RELEASED. 1 of 5.** **0 genuine
  clash** (16 pairs / 1,229.794165 mm³ = 14 dispositioned contact / 1,224.865011 + 2 withdrawn /
  4.929154, from 8 / 2,140.555804). Collar: **3.067 → 0.305 σ_y** rigid (0.113–0.173 two-body), bore
  D81.900. Fuselage **byte-identical** at 206,454.319709 mm³ / 320.0042 g, ring v2 0.000000. Open:
  vane root slot (0 cylindrical faces), A2's rib 14.000 mm off its mirror, the **33.265 mm** knuckle
  overhang never analysed, and a **5.1162°** knife edge at z +172.
- **ESC power rev_b — NOT ROUTED. 1 of 5.** Stack **49.80 mm** (6.00 under the 55.80 envelope),
  Samtec **TSW-120-07-G-D** 5.842 mm post / 3.33 mm inserted / 1.62 mm clear, sink trim **refused**
  (0.00 mm applied; the +2.54 mm bank shift restores 1.500 mm; Tj **123.15 °C**), 144 netless pads
  deleted (PTH 264 → 120), ENIG, headers mate 120/120. But **187 unconnected** on the corrected
  board and **60** on the routed copy — and they are **different artefacts**: the 58-element power
  route was laid on the pre-correction board. DRC is **527 listed = 499 CAPPED + 28 silk**, and the
  routed copper itself is **26.4 A against 36.6 A/phase (72 %)**, so even the route that exists is
  short of the settled design point (OQ-7).
- **ESC control rev_a — NO NETLIST. 1 of 5.** 37 DRC items (16 error/21 warning), 148/148 on F.Cu,
  0 B.Cu, AGND↔DGND 4.39 mm, and 41/41 of the connectivity that exists is routed. The problem is that
  **648 of 768 pads have no net**: the board is a placement mock, so its 0 unconnected is vacuous.
  That is the real blocker, not routing.

## 4. Detail rows — the population each verdict is computed from

Every cell above is a rule applied to one of these measured populations. This table is the audit
trail for §2, not a second source of truth: the same data is in `conditions.json`.

<!-- BEGIN DETAIL -->
| board | metric | value | provenance |
|---|---|---|---|
| Code-SDR V2 rev 2.1 | layers / copper | 4 (F/In1/In2/B), 0.035 mm on all four = 1 oz | C:fab-checklist-final:1.1 |
| Code-SDR V2 rev 2.1 | outline / area | 101.600 x 101.600 mm centreline, 0.100 stroke -> 101.70 bbox = 103.2256 cm2 | C:fab-checklist-final:1.1 |
| Code-SDR V2 rev 2.1 | min track / space | 0.100 mm / 0.1000 mm (space identical in 3 runs) | C:fab-cs-fid-real:drc_r1 |
| Code-SDR V2 rev 2.1 | min drill / ring | via 0.200 / PTH 0.200; ring via 0.100, PTH 0.150 (94 pads < 0.200 at own 0.10 rule) | C:fab-checklist-final:1.1 |
| Code-SDR V2 rev 2.1 | non-through | 0 of 1,085 vias | C:measure_cs:vias_by_span |
| Code-SDR V2 rev 2.1 | DRC at own rules | 0 errors / 222 warnings / 0 unconnected (199 lib_mismatch, 13 via_dangling, 10 track_dangling) | C:fab-cs-fid-real:5 |
| Code-SDR V2 rev 2.1 | unconnected | 0 pcbnew + 0 kicad-cli; 1,093/1,093 connections | M-2TOOLS |
| Code-SDR V2 rev 2.1 | package | 22 files at HEAD; 20/20 match MANIFEST.sha256; 1,215 holes = 1,213 + 2 G85 slots | C:verify-w9-adv:118 |
| Code-SDR V2 rev 2.1 | revision / finish | board title block '2.1'; job Revision '2.1'; ENIG | C:measure_cs:title_revision |
| Code-SDR V2 rev 2.1 | BOM | 373 rows, 0 MPNs; POS 377 = 373 parts + 4 fiducials | C:fab-checklist-final:1.1 |
| dev-board (radar/radio, HDI, revision unstamped) | outline / area | 105.050 x 105.050 mm = 110.4 cm2; 4 copper layers | C:dev-board-assessment:1 |
| dev-board (radar/radio, HDI, revision unstamped) | footprints | 320 (18 on B.Cu); 9,310 track segments; min via drill 0.100 | C:dev-board-assessment:1 |
| dev-board (radar/radio, HDI, revision unstamped) | vias by span | 1,740 through + 201 non-through (186 micro + 1 blind + 14 buried) | C:dev-board-assessment:1 |
| dev-board (radar/radio, HDI, revision unstamped) | single blind span | 183 of 201 are Top -> Ground Layer 1 (0.100 x171, 0.150 x12) | C:dev-board-assessment:1 |
| dev-board (radar/radio, HDI, revision unstamped) | HDI removal test | all 201 -> through: 10 -> 555 (+545, 80 shorting_items); 15 blind/buried only: 10 -> 48 | C:D:/devboard-evidence/hdi/HDI_REMOVAL_VERDICT.md |
| dev-board (radar/radio, HDI, revision unstamped) | DRC with companions | 10 violations, all warning, 0 error, 0 unconnected; 2 lib_footprint_mismatch + 8 real | M-KICAD (re-read D:/devboard-evidence/drc_full/drc_full.json: 10) |
| dev-board (radar/radio, HDI, revision unstamped) | DRC with the 2 exclusions | 8: 5 copper_sliver (2 Top, 2 Bottom, 1 Power L2), 2 holes_co_located, 1 track_dangling | M-KICAD (re-read drc_excluded.json: 8) |
| dev-board (radar/radio, HDI, revision unstamped) | package manifest | 49 entries: 46 byte-identical + 2 after CRLF->LF + 1 stale (RELEASE_NOTES.md) = 48/49; 0 missing | C:dev-board-assessment:3 |
| dev-board (radar/radio, HDI, revision unstamped) | POS / BOM | POS 292 rows vs 320 footprints = 28 short; BOM 320 lines (consistent) | C:dev-board-assessment:3 |
| dev-board (radar/radio, HDI, revision unstamped) | gbrjob | 105.05 x 105.05, 1.6 mm, 11 layer files, LayerNumber ok; SurfaceFinish EMPTY in both | C:dev-board-assessment:3 |
| dev-board (radar/radio, HDI, revision unstamped) | schematic cross-check | 320 match / 0 differ / 0 missing / 0 value mismatches | C:D:/devboard-evidence/dvb-exclusions/REPORT.md:7 |
| drone-arm main rev B (6-layer, all-through) | layers | 6 (F / In1..In4 / B); owner-approved | C:da-final-package:0 |
| drone-arm main rev B (6-layer, all-through) | footprints / pads | 165 / 657; 343 vias, all THROUGH F.Cu->B.Cu | C:da-final-package:0,3 |
| drone-arm main rev B (6-layer, all-through) | non-through | 0 of 343 (independent .kicad_dru gate: A.Via_Type != Through = 0) | C:da-final-package:3 |
| drone-arm main rev B (6-layer, all-through) | min drill | 0.200 mm (tools 0.2/0.3/0.35) | C:da-final-package:3 |
| drone-arm main rev B (6-layer, all-through) | outline | 140.000 x 100.000 centreline, 140.15 x 100.15 with stroke, 1-up | C:da-final-package:2 |
| drone-arm main rev B (6-layer, all-through) | DRC at own rules | 37: 30 track_dangling + 2 track_width + 5 via_diameter (set diff 42 -> 37, +2 / -7) | C:da-final-package:3 |
| drone-arm main rev B (6-layer, all-through) | unconnected | 10 on pcbnew and 10 on kicad-cli (uncapped); 15 -> 10 this wave | M-2TOOLS; C:da-final-package:1.5 |
| drone-arm main rev B (6-layer, all-through) | blocker | 7 U10 pads (5,24,13,23,16,19,30): escape 0.18-0.30 vs 0.237 needed; 2 joins at 0.002 mm; 1 GND fill split | C:da-final-package:4 |
| drone-arm main rev B (6-layer, all-through) | package | 20 files, 13 Gerbers, 361 drills + 4 G85 slots = 371 hits, POS 161 = 165 - 4 | C:da-final-package:2 |
| drone-arm main rev B (6-layer, all-through) | revision / finish | rev 'B' on 16 carriers; Finish + SurfaceFinish ENIG; ProjectId main_rev_b / B | C:da-final-package:2 |
| drone-arm main rev B (6-layer, all-through) | RF void | A 4.1699 mm2 = 9.8338 % / B 3.8754 = 9.1392 %, bit-identical to the delivered board | C:da-final-package:3 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | fuselage | 206,454.319709 mm3, 320.0042 g at 1550 kg/m3, 1 solid / 1 shell / 540 faces, walls 1.0921/1.1990/1.1800 | M-OCCT; C:dm-close-clashes:6 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | fuselage sha256 | d9ba7aeb...cadf, byte-identical to the dm-remaining-26 operand | C:dm-close-clashes:6 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | ring v2 | 0.000000 against all 28 parts, both rings | C:dm-close-clashes:6 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | clash closure | 16 pairs / 1,229.794165 mm3 = 0 genuine + 14 dispositioned contact (1,224.865011) + 2 withdrawn (4.929154) | C:dm-close-clashes:5a |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | elevon trim | one straight cut per side at \|x\| = 93.735; 2,440.874912 mm3 per side removed; 0.499723 mm to the fuselage | C:dm-close-clashes:2 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | collar | bore D81.900; 0.050 mm radial interference; hoop 846.6 -> 84.2 MPa = 3.067 -> 0.305 sigma_y rigid (0.113-0.173 two-body) | C:dm-close-clashes:3 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | vane root (J2) | needs a 3.000 mm mortise 2.000 x 29.000 + a 2.000 mm through-slot + a D3 bore; bracket has 0 cylindrical faces | C:dm-close-clashes:4a |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | A2 rib | y -70.000..-68.000 vs a true mirror at -56.000..-54.000: 14.000 mm outboard; 124.137167 mm3 of the J2 difference | C:dm-close-clashes:4a |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | knuckle overhang | trimmed root overhangs the first remaining knuckle by 33.265 mm; third knuckle + bracket NOT modelled | C:dm-close-clashes:7 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | knife edge | 5.1162 deg residual at z +172 (rim minimum 2.8334 deg, 2.47 um at 50 um out) | C:dm-knife-fairing:263 |
| drone-mech assembly (fuselage DM-FUS-001 REV 1 + fix set) | package | DM-FUS-001 REV 1: 45 files hashed (46 on disk), STEP + BREP + STL 59,964 tri (-0.052 %) + A3 drawing PDF | M-SHA; C:dm-final-package |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | outline / area | 151.77 x 122.55 mm = 185.99 cm2 (pcbnew bbox 151.87 x 122.65) | C:esc-corrections:5 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | footprints / pads | 167 / 1,437; PTH 264 -> 120 after deleting 144 netless J1-J6 pads | C:esc-corrections:3 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | copper | 4 layers, 3 / 1.5 / 1.5 / 3 oz | C:esc-corrections:5 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | DRC final | 527 listed = 499 clearance (CAPPED, true >= 499) + 28 silk_over_copper | C:esc-corrections:0.1,5 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | 11 target items | 3 shorting_items + 8 solder_mask_bridge -> 0, set diff +0 / -11 normalised | C:esc-corrections:4.3 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | unconnected, corrected | 187 (pcbnew and kicad-cli, below the cap) | M-2TOOLS; C:esc-corrections:5 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | unconnected, routed copy | 60 after 58 elements + 12 vias; GONE 0 / ADDED 0 on the DRC item set | C:esc-route-power:5 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | routed widths | BATP 2 x 3.00 mm = 16.0 A; BATN 18 x 4.00 mm = 19.7 A; 18 phases at 6.00 mm = 26.4 A | C:esc-route-power:6 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | annular | 70 rows under the published 0.200 3 oz floor: 42 PTH 0.150-0.175 + 28 via 0.150 (own rules accept 0.150; no annular row in the 527) | C:fab-checklist-final:1.1; C:esc-corrections:5 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | non-through / drill | 0 of 1,990 vias; min via drill 0.300, PTH 0.200 | C:fab-checklist-final:1.1 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | package / finish | fab/power: 9 Gerbers + gbrjob, Finish ENIG; no revision stamp; gerbers of the unrouted board | C:esc-corrections:6 |
| ESC power rev_b (4-layer, 3 / 1.5 / 1.5 / 3 oz) | stack | 49.80 mm as built (-34.00 -> +15.80), 6.00 mm under the 55.80 envelope | C:esc-corrections:1.4 |
| ESC control rev_a (2-layer, 1 oz) | outline / area | 107 x 60 mm = 64.20 cm2 (pcbnew bbox 107.10 x 60.10) | C:esc-route-control:0 |
| ESC control rev_a (2-layer, 1 oz) | footprints / pads | 148 / 768; 148 on F.Cu, 0 on B.Cu | C:esc-route-control:2.1 |
| ESC control rev_a (2-layer, 1 oz) | nets | 79 declared; 120 pads netted (15.6 %); 648 netless (84.4 %); only 2 nets have >= 2 pads | C:esc-route-control:2.1 |
| ESC control rev_a (2-layer, 1 oz) | routable connectivity | 41 connections total, all ground inside the 3 header sockets; 0 signal connections | C:esc-route-control:2.1 |
| ESC control rev_a (2-layer, 1 oz) | routed | 41/41 (100 %), 61 segments, 146.087 mm F.Cu, 0 B.Cu, 0 vias | C:esc-route-control:3 |
| ESC control rev_a (2-layer, 1 oz) | DRC | 37 at own rules before and after routing: 10 clearance (4 at 0.0000 + 6 at 0.150) + 2 courtyard + 4 mask (error) + 21 silk (warning); set diff +0 / -0 | C:esc-route-control:7 |
| ESC control rev_a (2-layer, 1 oz) | unconnected | 41 at placement / 0 after routing on both tools — but vacuous (see nets) | M-2TOOLS; C:esc-route-control:5 |
| ESC control rev_a (2-layer, 1 oz) | analogue | 1 nF cap to nearest ADC: min 5.042, median 16.829, max 32.211 mm; all 31 caps nearest to U16 | C:esc-route-control:4.1 |
| ESC control rev_a (2-layer, 1 oz) | AGND/DGND | 4.3900 mm minimum copper separation, 0 pairs < 0.5 mm | C:esc-route-control:5 |
| ESC control rev_a (2-layer, 1 oz) | package / finish | fab/control: 7 Gerbers + gbrjob, Finish ENIG; no revision stamp | C:esc-corrections:6 |
<!-- END DETAIL -->

## 5. How every cell is derived

The verdicts are functions of the metrics, not adjectives. The five rules, and the one place each
rule departs from the old sheet:

| # | objective | PASS when | WAIVED when | OPEN when |
|---:|---|---|---|---|
| 1 | DRC-clean | 0 errors **and** 0 fabrication-severity rows | objective is n/a (no PCB) | any error, **or any fabrication-severity row** |
| 2 | zero unconnected | 0 on `pcbnew` and 0 on a second tool, **and the count is measurable** | objective is n/a | > 0, **or the metric is vacuous** (a netless board always reads 0) |
| 3 | zero geometry defects | the defect list is empty | objective is n/a | the list is non-empty |
| 4 | validated package | revision stamped + files exist + manifest agrees + finish present when required + export of this design + POS reconciles | objective is n/a | any one missing |
| 5 | no open checklist cell | 5 of 5 cells carry a verdict, a value and a resolved source | — | any cell unfilled |

**Fabrication-severity vs annotation.** `copper_sliver`, `holes_co_located`, `shorting_items`,
`clearance` at error severity, `track_width`, `via_diameter`, `annular_width`, `hole_size`,
`edge_clearance`, `solder_mask_bridge` at error and `courtyards_overlap` at error are **fabrication
issues**: if one is present, condition 1 is OPEN. `*_dangling`, `silk_*`, `lib_footprint_issues` and
`lib_footprint_mismatch` are **annotations**: they are enumerated in the cell and do not fail it. This
one rule is why Code-SDR (222 annotation warnings) passes condition 1 and dev-board (7 fabrication
rows among 10 warnings) does not. An "all warnings" DRC is not clean when 7 of the warnings are
slivers and co-located holes — that was the old sheet's defect, recorded as BC51.

**Orderable** is `c1 and c2 and c3 and c4`; condition 5 is documentation completeness and never gates
an order. A board with a filled OPEN cell is **documented**, not **orderable**: those are different
claims and the summary keeps them apart. No board is marked orderable with an OPEN gating condition.

**WAIVED is only for "this objective does not exist here".** A defect is never waived by this sheet:
it is either OPEN, or a PASS that carries a named quote line (the Code-SDR 0.100 mm ring is quote line
W2, a PASS). The ESC's 0.150 rings are not in that class: they sit inside an OPEN condition because
no fab has granted them.

## 6. BOARD CORRECTIONS — carried, re-derived, and superseded

<!-- BEGIN CORRECTIONS-NOTE -->
**52 rows: 35 carried from the stale sheet (BC1-BC35: 11 live, 23 superseded, 1 partly live) + 17 new at r50 (BC36-BC52).** A SUPERSEDED row is history, not a live claim: its successor is named and the successor is itself a row in this table. PARTLY LIVE means one half survived (BC5: the 499-cap lesson) and one half did not (the monolithic count).
<!-- END CORRECTIONS-NOTE -->

<!-- BEGIN CORRECTIONS -->
| id | board | what was wrong | OLD | NEW | status | successor | source |
|---|---|---|---|---|---|---|---|
| BC1 | ESC | the ESC was designed to 60 A per phase | `60 A per phase` | **43.5 A phase / 40 A bus** | **SUPERSEDED** | BC30 | verify-w9-adv:63 |
| BC2 | ESC / airframe | two whole-aircraft CdA values were used that sit below the friction floor | `CdA 0.000693 and 0.0015 m2` | **CdA 0.0034-0.0056 m2, best 0.0042 (friction floor 0.002710)** | **LIVE** | — | esc-cda-bound:320-336 |
| BC3 | airframe / ESC | the 720 km/h design point is not reachable with this power system | `720 km/h` | **~545-570 km/h on this power system** | **SUPERSEDED** | BC32 | verify-w9-adv:77-78 |
| BC4 | ESC | 523 was quoted as the DRC total; it omits the pad rings KiCad cannot report | `523 reported as the total` | **fab-real = reported + invisible pad rings** | **SUPERSEDED** | BC31 | esc-drc-resolve:26,336-346 |
| BC5 | ESC | 499 was quoted as the unconnected count; it is kicad-cli's list cap | `499 unconnected` (the cap, quoted as a count) | **499 is a per-type LIST CAP, not a count: quote pcbnew uncapped.** The monolithic 1,536-1,542 count is retired with that board (BC45) | **PARTLY LIVE** | BC45 | fab-checklist-v4/out/esc_cap_test.json; esc-rail-repour:42 |
| BC6 | drone-arm | 15 non-through vias was a fan-out work-board artefact, not the repo board | `15 non-through vias` | **36 non-through on the repo board (26 blind + 10 buried by span, of 341 vias)** | **SUPERSEDED** | BC33 | fab-checklist-v4/out/measure_da_repo.json |
| BC7 | Code-SDR | the fiducial was charged as a 1.22 mm FAIL on a board that had no fiducials at all | `1.22 FAIL` | **4 fiducials on the committed board, min gap 1.5005 mm = +0.2505** | **LIVE** | — | fab-cs-fid-real:14,132-141 |
| BC8 | ESC | the 4 oz vendor survey over-counted houses | `five different houses` | **four houses carry an explicit 4 oz row** | **LIVE** | — | v2v-fab-verify |
| BC9 | ESC | the published area floor was 316 cm2 | `316 cm2 floor` | **370 cm2 for today's BOM (316 needs the M5 lugs replaced)** | **LIVE** | — | esc-compaction-verify |
| BC10 | drone-mech | 26 interference pairs was arithmetic over a subset, not a verdict | `26 pairs` | **0 genuine pairs (2 residual = 4.010114 mm3, 100 % artefact)** | **SUPERSEDED** | BC28 | fab-dm-final:state_changed |
| BC11 | drone-mech | 'delete 4 of 6 envelopes reaches zero' is short by one step | `delete 4 of 6 envelopes` | **delete 4 + resize** | **SUPERSEDED** | BC27 | fab-dm-envelopes |
| BC12 | drone-arm | the In1->In2 vias were labelled blind; by span they are buried (a drill class is not a span class) | `the four In1->In2 vias are blind` | **In1.Cu-In2.Cu vias are BURIED (10 of them); classify by layer pair** | **SUPERSEDED** | BC35 | fab-checklist-v4/out/measure_da_repo.json via_table |
| BC13 | ESC | 'rail PASS' was a single number; it holds only at one barrel-plating convention | `rail PASS` | **PASS only at k=0.048; 24.8 A and FAIL at k=0.024** | **SUPERSEDED** | BC30 | esc-rail-repour:45,283-285 |
| BC14 | Code-SDR | the Edge_Cuts stroke was stated as 0.15 mm; 101.6 + 0.15 != 101.70 | `0.15 mm stroke` | **0.100 mm stroke (101.6 + 0.100 = 101.70)** | **LIVE** | — | board file: 4 Edge.Cuts shapes at width 0.1 |
| BC15 | Code-SDR | the fab commit was counted as 16 files | `16 files committed` | **22 files committed by 1a20bd6** | **LIVE** | — | git show --name-status 1a20bd6 |
| BC16 | ESC | '3 packages' understates the 4 oz work | `3 packages` | **one impossible part (U201) + 23 footprint edits** | **SUPERSEDED** | BC31 | esc-branch-4oz |
| BC17 | ESC | the ESC outline was quoted stroke-inclusive | `173.950 x 283.080` | **173.800 x 282.930 (Edge.Cuts centreline)** | **SUPERSEDED** | BC44 | fab-checklist-v4/out/measure_esc.json |
| BC18 | ESC | the post-shrink DRC was going to be reported as a before/after total | `523 -> 253 as a total` | **row-level set diff GONE 270, ADDED 0** | **SUPERSEDED** | BC31 | esc-pad-shrink/setdiff.json |
| BC19 | ESC | the footprint-bound population was quoted at its pre-shrink size | `413 footprint-bound` | **155 footprint-bound after the shrink** | **SUPERSEDED** | BC31 | esc-pad-shrink/setdiff.json |
| BC20 | ESC | the footprint gaps were treated as one population and one shrink width | `all pad-gap rows shrinkable` | **113 remain: QFN-80 U201 75 + USB-C J202/J203 38** | **SUPERSEDED** | BC31 | esc-pad-shrink/groups.json |
| BC21 | ESC | the rail capacity was quoted as one as-drawn number and the re-pour had no cell | `23.1 A quoted as the rail capacity` | **re-poured BATP 49.67 / BATN 59.09 / BATP_IN 47.74 A at k=0.048** | **SUPERSEDED** | BC31 | esc-rail-repour/22_numbers.json |
| BC22 | drone-mech | the body volume was quoted as one number with no solid identity | `742,305.526 mm3 as one volume` | **742,306.360 mm3, 4 solids, 84.2 % bulk fill** | **SUPERSEDED** | BC27 | body-source-sync:60-70 |
| BC23 | drone-mech | the body of record was cited by name only | `the 42_6 shell, unnamed file` | **fuselage_battery_bay_shell_endpoint_relief_42_6.step, sha256 c4b81dc3...** | **SUPERSEDED** | BC27 | body-source-sync:55-70 |
| BC24 | drone-arm | the declared via type was quoted beside the span as if they agreed | `declared type 33 microvia + 3 blind/buried as the classification` | **10 of 36 declared types contradict their layer pair; the span is read from the layer pair** | **SUPERSEDED** | BC33 | fab-da-census/via_census.json |
| BC25 | drone-arm | the 36 non-through vias were assumed to overlap copper the respin already re-lays | `36 vias could ride the respin` | **FREE = 0 of 36** | **SUPERSEDED** | BC33 | fab-da-census:3 |
| BC26 | Code-SDR | the package integrity control was a byte compare over a prior wave's export | `14 compared files byte-identical to an independent export` | **20/20 files in `git archive HEAD` match the committed MANIFEST.sha256** | **LIVE** | — | verify-w9-adv:118 |
| BC27 | drone-mech | the body of record was four disjoint solids totalling 742,306.360 mm3 | `4 disjoint solids, 742,306.360 mm3` | **one solid: 206,454.3197 mm3, 320.0042 g, 1 solid / 1 shell / 0 free edges** | **LIVE** | — | dm-final-package/out/r1b_doubles.json, r5_validate.json |
| BC28 | drone-mech | the interference count was published as 6 pairs and as 8 pairs; neither is the union | `8 pairs / 6 genuine (1,250.769445 mm3)` | **10 pairs / 3,305.834869 mm3 = 6 genuine + 2 pushrod + 2 bearing rings** | **SUPERSEDED** | BC37 | dm-final-package:1a-1e |
| BC29 | drone-mech | the deliverable had no package, no drawing and no revision | `no drawings, 0 ply book, no revision` | **DM-FUS-001 REV 1: 45 files hashed, STEP + BREP + STL + A3 drawing** | **LIVE** | — | dm-final-package/README.md |
| BC30 | ESC | the design point was 43.5 A per phase / 40 A bus, which the 3 oz corridor cannot carry | `43.5 A phase / 40 A bus` | **36.6 A per phase / 33.7 A bus, a 35 A-class ESC; 497 km/h** | **LIVE** | — | esc-operating-point; esc-3oz-build/08_ampacity.json |
| BC31 | ESC | the DRC was quoted on the 4 oz board with its pad-shrink total | `523 -> 253 as the design-point DRC` | **3 oz 0.200/0.200: 229 -> 102, GONE 127 / ADDED 0; fab-real 200** | **SUPERSEDED** | BC46 | esc-3oz-build/04_setdiff.json |
| BC32 | ESC | the aircraft performance numbers were carried from the 43.5 A arm | `~545-570 km/h at 43.5 A` | **497 km/h at 36.6 A (CdA 0.004162; band 353-616); Tj 119.6 C** | **LIVE** | — | esc-operating-point; esc-cda-bound |
| BC33 | drone-arm | the non-through population was 36 after the census; 17 cleared and 19 remained | `36 non-through (26 blind + 10 buried)` | **19 non-through of 337 (15 micro + 4 blind); own DRC 4, span gate 22** | **SUPERSEDED** | BC36 | fab-da-36via:7 |
| BC34 | drone-arm | the 0.100 mm drill was quoted as the blocker; the blocker is the clear diameter a via needs | `0.100 mm via drill is the blocker` | **0.85 mm: a 0.60/0.30 through via needs 0.85 mm clear; U10 offers 0.4 mm lanes** | **SUPERSEDED** | BC38 | fab-da-path:14,318 |
| BC35 | drone-arm | BC12 called the In1->In2 span buried; those layers are adjacent, so those vias are microvias | `In1.Cu-In2.Cu vias are BURIED` | **In1 and In2 are ADJACENT: those 10 (5 after conversion) are MICROVIAS** | **SUPERSEDED** | BC36 | fab-da-36via/census_base.json |
| BC36 | drone-arm | the 19-via HDI board was the current board | `19 non-through = 15 micro + 4 blind on 4 layers` | **0 non-through: 343 vias, all THROUGH F.Cu->B.Cu, on 6 copper layers; min drill 0.200** | **LIVE** | — | da-final-package:0,3 |
| BC37 | drone-mech | the 10-pair interference population was current; 63.4 % of it was unclassified bearing rings | `10 pairs / 3,305.834869 mm3 = 6 genuine (1,204.481397) + 2 pushrod + 2 rings` | **16 pairs / 1,229.794165 mm3 = 0 genuine + 14 dispositioned contact (1,224.865011) + 2 withdrawn (4.929154); one cut per side at \|x\| = 93.735; collar 3.067 -> 0.305 sigma_y** | **LIVE** | — | dm-close-clashes:2,3,5a |
| BC38 | drone-arm | the blocker was 0.85 mm of clear diameter at U10 | `0.85 mm clear diameter for a 0.60/0.30 through via` | **7 U10 pads at 0.4 mm pitch with 0.18-0.30 mm escape against 0.237 mm needed (10 unconnected)** | **LIVE** | — | da-final-package:1.3,4 |
| BC39 | drone-arm | the only package was package7, an export of the 15-via work board | `package7 (15-via work board), SENDABLE NO` | **20-file rev-B package of the 6-layer board: 13 Gerbers, 371 hits, POS 161, ENIG, 34 of 36 assertions (V30/V31 fail on the unconnected count; the earlier 35-assertion count predates the added V36 SurfaceFinish check)** | **LIVE** | — | da-final-package:2 |
| BC40 | drone-arm | DRC was 4 at own rules and 22 at the no-HDI span gate | `4 own rules / 22 span gate` | **37 at own rules: 30 track_dangling + 2 track_width + 5 via_diameter; set diff 42 -> 37 (+2 / -7)** | **LIVE** | — | da-final-package:3 |
| BC41 | ESC | the stack was 55.80 mm | `55.80 mm stack` | **49.80 mm as built (-34.00 -> +15.80), 6.00 mm headroom; TSW-120-07-G-D 5.842 mm post, 3.33 mm inserted, 1.62 mm clear** | **LIVE** | — | esc-corrections:1 |
| BC42 | ESC | the 1.04 mm sink trim was the specified correction | `1.04 mm trim applied` | **trim 0.00 mm: it uncovers 6.16 mm2 of drain land on Q3CH/Q3CL/Q6CH/Q6CL; a +2.54 mm bank shift restores 1.500 mm with no cut; Tj 123.15 C** | **LIVE** | — | esc-corrections:2 |
| BC43 | ESC | the power board carried 264 PTH pads, 144 of them netless | `264 PTH, 144 netless pads` | **144 deleted (6 x Conn_02x12 J1-J6): PTH 264 -> 120, 0 PTH inside the sink rect, 167 fps / 1,437 pads** | **LIVE** | — | esc-corrections:3 |
| BC44 | ESC | the ESC was one 173.9 x 283.1 mm board with 687 footprints | `monolithic ESC rev_b, 173.9 x 283.1 mm, 687 fps` | **split pair: power 151.77 x 122.55 mm (4L 3/1.5/1.5/3 oz) + control 107 x 60 mm (2L 1 oz); areas 185.99 + 64.20 = 250.19 cm2 vs 382.71 = -34.62 %** | **LIVE** | — | esc-corrections:5; esc-split-verify |
| BC45 | ESC | the ESC's unconnected count was 1,536-1,542 | `1,536-1,542 unconnected` | **power 187 on the corrected board / 60 on the routed copy; control 41 at placement / 0 routed but vacuous (648/768 pads netless)** | **LIVE** | — | esc-corrections:5; esc-route-power:5; esc-route-control:2.1 |
| BC46 | ESC | the ESC DRC was 229 -> 102 at 3 oz | `229 -> 102 (3 oz, monolithic)` | **power 527 listed = 499 clearance (CAPPED, >= 499) + 28 silk; control 37 (16 error + 21 warning)** | **LIVE** | — | esc-corrections:0.1,5; esc-route-control:7 |
| BC47 | ESC | the routed power pass was measured against 80 A per phase | `80 A/phase requirement (33 % achieved)` | **the settled design point is 36.6 A/phase (BC30): 26.4 A is 72 % of it, not 33 %; the bus at 31.0 A is 14 % of 6 x 36.6 = 219.6 A. Both readings fail; the requirement basis is unresolved** | **LIVE** | — | esc-route-power:6; BC30 |
| BC48 | dev-board | the board's DRC was 70 violations (52 lib_footprint_issues, 10 mismatch, 8 real) | `70 warnings, 8 real` | **10 with full companions (.kicad_pro, fp-lib-table, .pretty): 2 excluded lib_footprint_mismatch + 8 real. The 52 were an isolation artefact and 8 of the 10 mismatches were too** | **LIVE** | — | M-KICAD: D:/devboard-evidence/drc_full/drc_full.json = 10; drc_excluded.json = 8 |
| BC49 | dev-board | the 201 non-through vias might be convertible to through vias | `201 non-through, removable` | **PROVEN unremovable: all 201 -> 10 -> 555 violations (+545, 80 shorting_items); the 15 blind/buried alone -> 10 -> 48. 183 are one Top -> Ground L1 blind span. Recommendation: ACCEPT HDI** | **LIVE** | — | D:/devboard-evidence/hdi/HDI_REMOVAL_VERDICT.md |
| BC50 | dev-board | the package was reported as '16 files missing', then as clean | `16 files missing / manifest clean` | **48 of 49 verify: 46 byte-identical + 2 only after CRLF->LF (the two BOMs) + 1 genuinely stale (RELEASE_NOTES.md); POS 292 vs 320 = 28 short; SurfaceFinish EMPTY in both .gbrjob; no revision stamp** | **LIVE** | — | dev-board-assessment:3 |
| BC51 | dev-board | condition 1 (DRC-clean) was graded PASS (qualified) while 8 of the same 10 DRC rows were called real defects | `condition 1 PASS; condition 3 FAIL` | **condition 1 OPEN: 5 copper_sliver + 2 holes_co_located are fabrication-severity, so the DRC is not clean; the 1 track_dangling is charged under condition 3** | **LIVE** | — | dev-board-assessment:verdict; r50 derivation rule 1 |
| BC52 | drone-mech | the drone-mech row described the fuselage part alone and scored 5 of 5 | `fuselage part DM-FUS-001 REV 1, 5 of 5` | **the row is the ASSEMBLY: the fuselage part still passes (byte-identical, 0 genuine clash) but the assembly carries 4 open geometry items and no released package (BC37)** | **LIVE** | — | dm-close-clashes:7; r50 row population |
<!-- END CORRECTIONS -->

**Why each carried row is now superseded.** 23 of the 35 carried rows describe an artefact or a number
that no longer exists, and each names its successor in the table: **BC1, BC13 → BC30** (the current
moved 60 → 43.5 → 36.6 A/phase); **BC3 → BC32** (performance recomputed at the settled current);
**BC4, BC16, BC18-BC21 → BC31, and BC31 itself → BC46** (the monolithic 4 oz / 3 oz ESC was replaced by the split
pair, so its DRC population and pad-shrink totals belong to no shipping board); **BC17 → BC44** (the
outline population changed from one 173.9 × 283.1 mm board to a 151.77 × 122.55 + 107 × 60 pair);
**BC6, BC24, BC25, BC33, BC35 → BC36** and **BC34 → BC38** (drone-arm was rebuilt as 6 layers with
**0** non-through vias, so the 36/19-via census, the "buried" example, the free-rider test and the
0.85 mm clear-diameter blocker are all history); **BC10, BC11, BC22, BC23 → BC27** and **BC28 →
BC37** (the drone-mech body was welded to one solid and the clash closure was re-run to 16 pairs /
1,229.794165 mm³ with 0 genuine); **BC12 → BC35 → BC36** (the layer-pair example was retracted, then
the vias it described ceased to exist). A superseded row is not a deletion: it is the history of a
programme that kept discovering its number was true of a different population. BC5 is the one
**partly live** row: the 499 list cap is permanent, the 1,536–1,542 count belonged to the retired
board.

## 7. Provenance — what each number is worth

| tag | meaning | instrument and control |
|---|---|---|
| **M-KICAD** | measured in this programme by `kicad-cli 9.0.7` | `pcb drc --severity-all --units mm --format json`, JSON read from disk, run in a directory carrying the board's companions (`.kicad_pro`, fp-lib-table, local `.pretty`). Rule-load proved by a deliberately wrong rule moving the count |
| **M-PCBNEW** | measured by the KiCad-bundled `pcbnew 9.0.7` | ratsnest `GetUnconnectedCount(False)`, pad/via census. **`PCB_VIA.GetWidth()` is never called** (it hangs); via size is text-parsed |
| **M-2TOOLS** | reproduced on both tools | `pcbnew` and `kicad-cli` return the same count, below the 499 cap |
| **M-OCCT** | measured by cadquery 2.7.0 / OCP 7.8.1.1 | `BRepGProp.VolumeProperties_s(..., 1e-12)`, solid-by-solid booleans, fuzzy 0.0 |
| **M-SHA** | hashed | sha256 over the manifest and the files it names |
| **C:&lt;report&gt;:&lt;section&gt;** | carried from a named report | that report's own instrument, quoted with its section; not re-run here |

**The numbers this sheet turns on, and where each comes from.**

| number | value | tag | note |
|---|---|---|---|
| Code-SDR DRC | 0 errors / 222 warnings / 0 unconnected | M-2TOOLS | 199 + 13 + 10; renumber control identical |
| Code-SDR manifest | 20/20 in `git archive HEAD` | M-SHA | `verify-w9-adv:118` |
| dev-board DRC | **10** with companions; **8** with the 2 exclusions | M-KICAD | re-read from `D:/devboard-evidence/drc_full/`; 70 is a no-companion artefact |
| dev-board HDI | 201 = 186 micro + 1 blind + 14 buried; **183** one span | M-PCBNEW | forcing through vias: 10 → 555, +545, 80 shorts |
| dev-board package | 48/49; POS 292/320; SurfaceFinish empty | M-SHA + C:dev-board-assessment:3 | 1 genuinely stale file, not 3 |
| drone-arm vias | **0 non-through of 343**, 6 layers | M-PCBNEW | independent `.kicad_dru` gate: `A.Via_Type != Through` = 0 |
| drone-arm DRC | 37 (set diff 42 → 37) | M-KICAD | 30 dangling + 2 track_width + 5 via_diameter |
| drone-arm unconnected | 10 / 10 | M-2TOOLS | not capped; 15 → 10 |
| drone-arm package | 20 files, 371 hits, POS 161, ENIG | M-SHA | 34 of 36 pass; V30/V31 fail on the unconnected count |
| drone-mech clash | 16 / 1,229.794165 mm³, **0 genuine** | M-OCCT | 14 contact + 2 withdrawn; one cut per side at \|x\| = 93.735 |
| drone-mech collar | 3.067 → 0.305 σ_y rigid | M-OCCT | 0.915–1.495 → 0.113–0.173 two-body |
| ESC power unconnected | **187** corrected / **60** routed | M-2TOOLS | different artefacts; do not merge the two numbers |
| ESC power DRC | **527 listed = 499 CAPPED + 28 silk** | M-KICAD | true clearance ≥ 499; not quotable as a total |
| ESC control | 648/768 netless; 37 DRC | M-PCBNEW + M-KICAD | 41/41 routed, but the zero is vacuous |
| ESC stack | 49.80 mm as built | C:esc-corrections:1 (arithmetic on the z ladder) | TSW-120-07-G-D; Tj 123.15 °C |

**The 499 flag.** Every occurrence of **499** in this sheet is a **list cap**: the ESC power board's
clearance population is **CAPPED at 499** (true count ≥ 499), and the old 1,536–1,542 monolithic
count is retired. The checker greps the data for `499` and fails if any occurrence is not labelled `CAP`.
**A figure at 499 is a cap, never a count.**

## 8. Open questions — decisions for the owner, not measurements

Each is a choice with a cost, not a gap in the evidence.

| # | question | recommendation | cost of the recommendation |
|---:|---|---|---|
| **OQ-1** | **Accept dev-board's HDI?** 201 non-through, 183 of them one cheap blind span | **ACCEPT.** It is proven unremovable (10 → 555, 80 shorts) and it is the cheapest HDI class: one lamination cycle, one blind span | one lamination cycle and a fab that quotes 0.100 microvias; refusal means a full re-layout, not a via conversion |
| **OQ-2** | **dev-board re-release:** who signs the finish, POS and revision? | **ENIG + DNP-mark the 28 POS rows + stamp a revision.** The board already carries a real release and 320/320 schematic parity | ~1 hour of package work, no layout; the 8 defects are a separate fix |
| **OQ-3** | **drone-arm's U10 path:** re-fan-out, declare 0.4/0.2, or move the part? | **Re-fan-out the U10 ring** (240 tracks + 47 vias within 1.2 mm of a U10 pad). It is the only option that closes all 7 pads | a re-layout of one package ring; a partial rip is measured zero-sum (rounds B/C broke more than they closed) |
| **OQ-4** | **drone-arm's 5 `via_diameter` + 2 `track_width`:** waive or fix? | **Fix the 2 necks; seek a written 0.2 mm drill grant for the 5 vias.** A waiver without the fab's signature is a guess | 2 tracks re-routed; one fab question |
| **OQ-5** | **drone-mech's vane root, A2 rib, third knuckle:** cut now or ship the part? | **Ship the fuselage part (REV 1) and open REV 2** with the slot, the mirrored rib and a modelled knuckle | one CAD wave; mirroring the rib *adds* 292.274334 mm³ of contact, so it must be dispositioned, not silently fixed |
| **OQ-6** | **drone-mech's knife edge:** fillet or rim offset? | **A 0.3 mm rim offset.** Re-stationing was measured to produce 3 solids | one edit, no re-station; 2.47 µm at 50 µm out is the residual to accept |
| **OQ-7** | **Which ESC current governs:** the settled 36.6 A or the 80 A the routing was scored against? | **36.6 A** (the 497 km/h airframe number is built on it). Then re-score: 26.4 A is **72 %**, still short — the route does not pass at either basis | re-issuing the routing acceptance; no copper moves |
| **OQ-8** | **The ESC 3 oz ring floor:** 70 rings at 0.150–0.175 under the published 0.200 floor (the board's own rules accept 0.150) | **Ask the house for a written 0.150 grant** before re-ruling the board | one quote; a refusal turns 70 rings into a pad redesign |
| **OQ-9** | **The ESC control board:** stop or keep laying copper? | **Stop until a netlist exists.** 648/768 pads netless makes every routing result unfalsifiable | schematic capture of 148 parts; everything else on the board is already measured |
| **OQ-10** | **Code-SDR's 373 MPNs:** order bare boards now? | **Order the bare board; source the BOM in parallel.** Engineering is complete | sourcing only; nothing in the board changes |
| **OQ-11** | **Code-SDR's 23 dangling warnings** (13 via + 10 track): deliberate stubs? | **State it in the release notes.** No evidence directory justifies them; the cell passes on the fabrication-severity rule, not on a waiver | one paragraph; if they are not deliberate, 23 items become a fix |
| **OQ-12** | **Panelisation and price** for any of the six boards | **Commission one panel drawing per board before RFQ.** No panel drawing or quote exists anywhere in the tree | CM time; without it a 1-up outline is not a price |

## 9. Self-check — the summary against its own detail rows

<!-- BEGIN SELFCHECK -->
| check | computed | required | |
|---|---|---|---|
| cells | 30 (6 boards x 5) | 30 | PASS |
| tally | 12 PASS + 2 WAIVED + 16 OPEN = 30 | sums to 30 | PASS |
| orderable | 1 of 6 (cs) | every YES has c1-c4 PASS, every NO has >=1 OPEN | PASS |
| blocker named in an OPEN row | 5 of 5 non-orderable boards | each blocker token occurs in an OPEN cell's 'what remains' | PASS |
| corrections | 52 rows: 28 live / 23 superseded / 1 partly live | unique BC1..BC52, every successor exists | PASS |
| vocabulary | 16 OPEN, 2 WAIVED, 0 UNKNOWN, 0 blank | no cell outside PASS/WAIVED/OPEN | PASS |
| 499 flags | 7 strings quote 499, 0 unlabelled | every capped figure is labelled CAPPED | PASS |
<!-- END SELFCHECK -->

**In one sentence: the table prints 12/2/16, the tally recomputes 12/2/16, the one YES board has no
OPEN gating cell, every NO board's blocker occurs in an OPEN cell, and all 52 corrections resolve.**
`check_truth.py` re-derives the verdicts from the metrics (not from the printed verdicts), checks
every printed verdict and provenance cell against the data, re-parses each table's column count,
resolves every cited path, and exits non-zero on any drift.

## 10. Limits — what this sheet does not establish

1. **Nothing was re-measured this wave.** Every number is carried from a named report; only dev-board's
   DRC JSONs were re-read. A carried number is worth its source, no more.
2. **The ESC has no single current board.** The 58-element power route (`esc-route-power`) and the
   corrections (`esc-corrections`: +2.54 mm shift, 144 pads deleted) exist on different copies. 187 and
   60 are both true of their own artefact; **neither describes a merged board, because none exists.**
3. **The ESC capacity basis is unresolved.** The route was scored against 80 A/phase while the settled
   design point is 36.6 A (BC30/BC47). At 36.6 A the same copper reads 72 % of phase, not 33 % — still
   a fail, but a different one. OQ-7 is the decision.
4. **drone-mech's assembly fix is BREP-only.** The trim and bore do not exist as a STEP-delivered part,
   so the 0-genuine-clash state is a measurement on operands, not a released assembly.
5. **dev-board's DRC baseline is still not fully reconciled.** The shipped release records **176**, the
   first isolation run read **70**, and the full-companion run reads **10**. The 176-vs-70 difference is
   a different rule set or toolchain and is not explained here; only 10 is quoted.
6. **Code-SDR's 222 annotation warnings are accepted, not justified.** 199 are library-copy drift and
   23 are dangling stubs (13 via + 10 track); OQ-11.
7. **No panelisation, no price, no assembly quote** exists for any board. Orderable means "the fab can
   build the artefact as described", not "it is affordable or panelised".
8. **The 499 cap is a floor.** The ESC power clearance count is ≥ 499 and cannot be measured by this
   CLI; no total is quoted for it anywhere in this sheet.
9. **One carried assertion count was wrong.** The drone-arm package was summarised as "34 of 35"; the
   artefact has **36** assertions and **34 pass**. V30 and V31 both fail on the unconnected count, and
   the earlier 35-check count predates the added V36 SurfaceFinish check (BC39).

## 11. Files

```
REPORT.md            this sheet
conditions.json      the 30 cells: metrics, stated verdict, evidence, provenance, remaining
build.py             the data and the generators for the marked blocks
check_truth.py       re-derives every verdict/tally from metrics; exits non-zero on drift
out/check.log        the checker's run record
```

No repo was written and nothing was committed: every board and part was read from an existing copy or
through `git show`, and the drone-mech / ESC / drone-arm artefacts live in their own evidence
directories.