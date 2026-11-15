# The pre-fab checklist — one sheet, three boards, signed or refused

**Owner:** fab-checklist specialist (this wave) · **Date:** 2026-11-15 · **Host:** KiCad 9.0.7
(`C:/Program Files/KiCad/9.0/bin/kicad-cli.exe`, `python.exe` + `pcbnew` 9.0.7).
**Repos:** `E:/engineering-portfolio-audit/repos/{drone-arm,Code-SDR}`, branch `work/2026-11-11`
(both verified: `git branch --show-current` = `work/2026-11-11`). **Nothing was written into any
repo, nothing committed or pushed, no `audit/*` branch touched.** Every copy this item needed lives
under `evidence/fab-checklist/`.
**Binding constraints read first:** `AGENT_BOARD.md` — §"Board roster and copper weight"
(:30-57), §"HARD CONSTRAINTS" (:448-464).

---

## 0. How to use this sheet

**What "orderable" means here**, because the word does the most work on the page:

> **ORDERABLE = a bare-board fabrication order placed today, from artefacts that exist today,
> would produce the board the design describes, with nothing to fix afterwards.**

It is deliberately *not* "the design is finished" and *not* "assembly can be quoted". Three
consequences, stated so nobody reads a green cell as more than it is:

1. A board that etches correctly but cannot function is **not** orderable, because the rework that
   follows is exactly what this programme exists to avoid (AGENT_BOARD.md:5-25). So missing
   connectors and unrouted nets count against the verdict, even though they are not fab-process
   limits.
2. Assembly data (BOM, pick-and-place, fiducials, test points) is tracked in §7. It stops an
   **assembly PO**, not the etch order, and it is scored separately.
3. A defect that no fab house ever looks at (library–schematic parity, dangling stubs, silkscreen
   artwork) never changes a verdict. It goes to §4.

**Source tags used in §1.** Every cell is a tag, not an assertion. The tag resolves to a file whose
`REPORT.md`/JSON states the number, and most resolve to a command I ran in this item:

| tag | resolves to | how it was produced |
|---|---|---|
| `M-DA` `M-ESC` `M-CS` | `measure/drone-arm-main-rev_b.json`, `measure/esc-rev_b.json`, `measure/Code-SDR-V2.json` | `python.exe measure.py` — `pcbnew` reads the repo boards read-only; no save |
| `S-DA` `S-ESC` `S-CS` | `probe/dapr/`, `probe/escpr/`, `probe/cspr2/` — `drc_probe_space.json` | `kicad-cli pcb drc` with the clearance floor raised to 0.30 mm, to read KiCad's own measured `actual` gap |
| `D-DA` `D-ESC` `D-CS` | `gate/dapr/drc_correct_rules.json`, `gate/escpr/drc_4oz_correct_rules.json`, `../fab-cs-drc/drc_baseline.json` | DRC under the rule set that actually governs that board (§2.9) |
| `G-DA` | `../fab-da-gerbers/package/` + `artefacts/drill_census.txt`, `artefacts/extents.txt` | the rev_b package that unit built; its drill census re-counted here |
| `X-DA` | `repos/drone-arm/hardware/main/pcb-gerbers-1/` | the package that is actually in the repo (stale) |
| `EXP-CS` | `export/cs/` — my own export from a byte copy of the repo board | `kicad-cli pcb export gerbers/drill/pos` |
| `R-DA-vias` `R-ESC` `R-CS` `R-CONN` `R-SERVO` | `../fab-da-vias/REPORT.md`, `../fab-esc-4oz/REPORT.md`, `../fab-cs-drc/REPORT.md`, `../fab-da-connectors/REPORT.md`, `../fab-da-servo/REPORT.md` | sibling units of this wave |

**Charge-summary of §1** — 13 verdict-bearing cells per board plus the orderable column, counted from
the table itself by `check_report.py`, no blank cells, no "TBD":

| board | PASS | FAIL | WAIVED | orderable |
|---|---:|---:|---:|---|
| drone-arm main rev_b | 7 | 6 | 0 | **NO** |
| ESC rev_b | 6 | 7 | 0 | **NO** |
| Code-SDR V2 | 12 | 0 | 1 | **YES** |
| **all three** | **25** | **13** | **1** | 1 of 3 orderable |

---

## 1. THE CHECKLIST — one row per board, one column per line

Cell format: **value** `source tag` — **verdict**, and on a FAIL the fix class (**PARAM** = parameter
change, **MOVE** = copper move, **RESPIN** = design/package respin), detailed in §3. Tags resolve in
§0; the full measurement behind each column is in §2. Read this table with the file's horizontal
scroll — 14 columns is the shape the sign-off needs.

| board | 1. layers | 2. copper weight | 3. min track | 4. min space | 5. min drill | 6. min annular ring | 7. via classes present | 8. unconnected | 9. DRC (correct rules) | 10. gerber package | 11. revision stamp | 12. panel size | 13. surface finish | 14. orderable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** | **4** `M-DA` PASS | **1 oz, 0.035 mm ×4** `M-DA` PASS | **0.200 mm** (479 seg; 28 @ 0.2002) `M-DA` PASS at 1 oz | **0.125 mm** `S-DA` PASS | **0.100 mm**, 33 vias `M-DA` FAIL → MOVE | **0.100 mm** via / 0.150 PTH pad; **0.150 floor over the 305 through vias** `M-DA` FAIL → MOVE | **0.10/0.30 µvia ×33**; 0.30/0.60 ×21; 0.30/0.70 ×6; 0.35/0.70 ×281; **36 non-through, 5 spans** `M-DA` FAIL → MOVE | **0** `D-DA` PASS | **33 err / 0 unc**; 0 under its own rules — that is the trap `D-DA` FAIL → MOVE | rev_b pkg valid — 369 holes, 140.000 × 100.000, no frame, `Rev "B"` `G-DA` — but the repo ships rev_a only, A4 frame 288.397 × 204.238, `Rev "rev?"`, `Finish "None"` `X-DA`; **5 blind/buried .drl** FAIL → PARAM + MOVE | repo rev `""`; silk `REV-B FLIGHT CONTROL…`; job `"B"` `M-DA` FAIL → PARAM | **140.15 × 100.15**, 1-up `M-DA` PASS | **ENIG** `M-DA` PASS | **NO** |
| **ESC rev_b** | **4** `M-ESC` PASS | **4 oz outer 0.140 / 1.5 oz inner 0.0525** `M-ESC` PASS as declared | **0.200 mm** (4 seg, 5.79 mm) `M-ESC` FAIL at 4 oz → PARAM | **0.200 mm**; 371 of 414 misses are pad↔pad at exactly 0.2000 `S-ESC` FAIL at 4 oz → RESPIN | **0.300 mm** via / 0.200 mm pad `M-ESC` PASS | **0.150 mm** via / **0.125 mm** PTH pad (U204.11) `M-ESC` FAIL at 4 oz → PARAM + MOVE | 0.30/0.60 ×16; 0.35/0.70 ×12; 0.40/0.80 ×1,962; **all through** `M-ESC` PASS | **499**, over 67 nets `D-ESC` FAIL → MOVE | **523 + 499 unc** at 4 oz; 16 warnings at 0.2 mm `D-ESC` FAIL → PARAM + RESPIN + MOVE | **none** — 0 gerber, 0 drill, 0 job, 0 pos under `hardware/esc` `artefacts/repo_scans.txt` FAIL → PARAM | rev `""`, no silk rev text `M-ESC` FAIL → PARAM | **173.95 × 283.08**, 1-up `M-ESC` PASS | **ENIG** `M-ESC` PASS | **NO** |
| **Code-SDR V2** | **4** `M-CS` PASS | **1 oz, 0.035 mm ×4** `M-CS` PASS | **0.100 mm** (1,510 seg) `M-CS` PASS | **0.100 mm** `S-CS` PASS | **0.200 mm** via / 0.200 mm pad `M-CS` PASS | **0.100 mm** via (53) / 0.125 (1,013) / 0.150 PTH `M-CS` WAIVED — below a 0.15 house floor, above its own 0.10 rule; quote line | 0.20/0.40 ×53; 0.20/0.45 ×924; 0.20/0.50 ×6; 0.25/0.50 ×89; 0.40/1.00 ×13; **all through** `M-CS` PASS | **0** `D-CS` PASS | **0 err / 222 warn / 0 unc** `D-CS` PASS — all three warning classes waived, §4 | 11 Gerbers + job + pos (373 rows), **1,215 holes = 1,085 vias + 128 PTH + 2 NPTH**, 101.600 × 101.600, `Rev "2.1"` `EXP-CS` PASS — not in the repo, and one sibling package is 2 holes short (§2.10) | **`2.1`** in title block and job file `M-CS` PASS | **101.70 × 101.70**, 1-up; 1.7 mm over the 100 mm tier `M-CS` PASS — price class, not process | **ENIG** `M-CS` PASS | **YES** |

Tally, counted from the table by `check_report.py`: DA **7 PASS / 6 FAIL / 0 WAIVED**, ESC
**6 / 7 / 0**, CS **12 / 0 / 1**; column 14 carries the verdict itself.

---

## 2. How each line was measured, and the one place a number can lie

### 2.1 Layer count and copper weight — read from the file, not from the brief
`M-*` parse the board with `pcbnew` and separately regex the `(stackup …)` block. ESC:
`F.Cu 0.14, In1 0.0525, In2 0.0525, B.Cu 0.14`; DA and CS: `0.035 ×4`. These reproduce
`AGENT_BOARD.md:34-41` exactly. Measured stackup totals (including the two 0.010 mm mask rows):
DA **1.600**, ESC **1.600**, CS **1.620**. Over copper only — mask is not board thickness, the
convention `evidence/hf-fab-readiness/REPORT.md:376-402` adopted — DA is **1.580 against a declared
1.60 (−1.25 %)** and CS is **1.600, exact**. That is a drawing note (§4.7), not a fab reject.

### 2.2 Minimum track width
Minimum over every `PCB_TRACE` segment. Note the brief's "2,620 tracks" on DA and "12,253" on CS are
**segments + vias**, not segments: DA 2,279 + 341 = 2,620; CS 11,168 + 1,085 = 12,253; ESC
154 + 1,990 = 2,144 `M-*`. `../fab-esc-4oz/REPORT.md:71-83` already records this correction and my
census confirms it to the hole.

### 2.3 Minimum space — the only line where a plausible method gives a wrong answer
DRC only reports a gap when the gap breaks a rule, so "0 clearance violations" means
*min space ≥ the rule*, not "min space is the rule". To get the actual number I raised the floor to
0.30 mm in a copy and read KiCad's own `actual` value off each violation (`S-*`). The two ends then
bracket the truth: the board is clean at its own floor and the probe finds the smallest pair above
it.

| board | own clearance rule | DRC at own rule | probe floor | **smallest actual gap found** | bracket |
|---|---|---|---|---|---|
| DA | 0.125 `M-DA` | 0 clearance violations `D-DA` | 0.30 | **0.1250**, 505 pairs reported | = 0.125 exactly |
| ESC | 0.200 `M-ESC` | 0 (only 16 dangling) at 0.2 rules | 0.30 | **0.2000**, 499 pairs | = 0.200 exactly |
| CS | 0.100 `M-CS` | 0 clearance violations `D-CS` | 0.30 | **0.1000**, 511 pairs (faithful env) | = 0.100 exactly |

Each of the three lands exactly on its own rule floor, so the measurement is self-checking: a probe
that over-reported would have found something *below* the rule (which would have been a hidden DRC
miss), and one that under-reported would have found something above it.

**One methodological trap, recorded because it nearly entered this sheet.** My first CS probe ran in
a bare copy directory and reported **25 `copper_edge_clearance` errors and 24 `lib_footprint_issues`**
that the repo board does not have. Cause: the copy was missing the repo's own
`Code-SDR-V2.kicad_dru` (1,534 B) — which carries a conditional waiver for the five edge-launch SMA
footprints — and the footprint libraries. Re-run in a faithful copy (`probe/cspr2/`, repo
`.kicad_dru` + `fp-lib-table` + `CodeSDR.pretty` copied in): **733 = 222 + 511 clearance pairs, 0
edge violations, 0 lib issues.** The unfaithful run was deleted rather than left to be misquoted. A
DRC run outside its project directory invents violations.

### 2.4 Minimum drill
Minimum over via drills **and** PTH pad drills, reported separately because on ESC they differ by
0.1 mm: min **via** drill 0.300, min **pad** drill 0.200 (110 thermal vias inside exposed pads)
`M-ESC`. `R-ESC:115-120` reached the same split; a via-only count reports "0 below 0.2" on a board
that does contain sub-0.3 mm holes.

### 2.5 Minimum annular ring
Computed as `(min(pad_x, pad_y) − drill) / 2` for every via and every PTH pad, so the reported
minimum names its own population (`M-*`): DA `0.100` on a 0.10/0.30 microvia at (58.4, 55.55); ESC
`0.125` on `U204.11`; CS `0.100` on a 0.20/0.40 via at (32.75, 58.5625). The through-via population
on DA bottoms out at **0.150**, which is what a 1 oz house will happily build — the 0.100 is a
property of the vias that are illegal anyway, not a second defect.

### 2.6 Via classes
Grouped by (drill, diameter) with the span of every non-through via (`M-*`). DA's 36 non-through:
`F→In1 14, In1→In2 10, In1→B 4, F→In2 3, In2→B 5`. **DRC cannot see a via's process type** — the 3
blind 0.300 mm vias carry a legal drill and pass every rule, so the 33-error gate count understates
the problem by three. What a fab house actually receives is the drill-file set, and that is line 10's
evidence: 5 blind/buried Excellon files, 33 + 3 = 36 of the 369 holes in files a 4-layer house does
not run.

### 2.7/2.8 Unconnected count
Read from the DRC JSON's `unconnected_items` array, not from a GUI count: DA **0**, ESC **499**, CS
**0** — and DA/CS are independently corroborated by the probe runs on copies (0 and 0). ESC's 499 span
67 nets, dominated by `/DGND` (170), `/3V3` (118) and `/M1..M3_BATN` (112 each) `R-ESC:145-157`: the
power distribution has not been poured.

### 2.9 What "the correct rules" are — the single most important definition here
| board | rule set that governs it | why that one |
|---|---|---|
| DA | board rules **+ `hole_size ≥ 0.20 mm` for vias** + no microvia, no blind/buried | AGENT_BOARD.md:448-456. Under its own rules the board is *clean* (0 violations), because `min_microvia_drill` is still 0.1 `M-DA`. **That is the trap**: a clean DRC on a board no non-HDI fab can build |
| ESC | the 4 oz ruleset, 11 rules, `../fab-esc-4oz/kicad/esc_rev_b.kicad_dru` | 0.25 track/space/neck, 0.20 ring, 0.30 via drill, 0.20 PTH drill, 0.50 edge — with the published source for each number in `R-ESC:§1` |
| CS | its own project rules **and** its own `.kicad_dru` | that is the contract its authors wrote; it passes it |

I re-ran ESC's 4 oz DRC myself rather than quoting it: **523 violations, 499 unconnected**, and the
type split is identical to `../fab-esc-4oz/REPORT.md:141-160` (414 clearance, 70 annular, 16 via
diameter, 4 track width, 3 connection width, 16 dangling). Independent reproduction, same numbers.

### 2.10 Gerber/drill/position package, and a package that is subtly wrong
Complete drill census in `artefacts/drill_census.txt`; extents in `artefacts/extents.txt`.

| package | files | holes | Edge_Cuts | verdict |
|---|---:|---:|---|---|
| `../fab-da-gerbers/package/` (rev_b) | 21 (+7 drill maps) | **369** = 33 @0.1 + 18 @0.2 + 27 @0.3 + 281 @0.35 + 4 @0.6 + 2 @0.65 + 4 @4.30 | **140.000 × 100.000** | complete and frame-free; 5 of the 7 drill files are blind/buried and carry 36 holes |
| `repos/…/pcb-gerbers-1/` (what the repo ships) | 14 | 0 NPTH holes | **288.397 × 204.238** | the rev_a board with an A4 worksheet frame plotted into all 11 layers |
| ESC | **0** | — | — | nothing exists |
| `export/cs/` (mine) | 13 + pos | **1,215** = 1,213 plated (1,056 @0.2, 89 @0.25, 11 @0.3, 13 @0.4, 10 @0.46, 2 @0.6, 10 @0.65, 2 @0.85, 12 @0.89, 4 @1.025, 2 @1.3, 2 @1.57) **+ 2 NPTH @3.2** | **101.600 × 101.600** | complete; matches the board's own census |
| `../fab-cs-clock/gerbers/` (sibling) | 17 | **1,215** (PTH and NPTH in separate files) | 101.600 × 101.600 | complete |
| `../fab-cs-drc/fabpkg/` (sibling) | 32 | **1,213** — **the 0.600 mm tool is declared and has zero hits** | 101.600 × 101.600 | **2 holes short**; do not send |
| `../fab-cs-drc/fabpkg-clean/` (sibling) | 12 | **no drill files at all** | 101.600 × 101.600 | 11 Gerbers + job only; not sendable on its own |

Two delivery notes fell out of that table and neither is in any earlier report: **`fabpkg-clean/` is
Gerbers only** (no Excellon), and **`fabpkg/` draws 28 layers** — including `F.Adhesive`, `F.Fab`,
`F.Courtyard` and `User_1…4` — which a fab house ignores but which makes the job file's layer list
look like a mistake. The package to send is the one whose drill census is 1,215.

The 1,215 is not a coincidence: **1,085 vias + 128 PTH pads + 2 NPTH = 1,215** `M-CS` `pads_pth=128,
pads_npth=2`. Two independent exports agree with the board; the third declares a 0.600 mm tool,
drills no holes with it, and is short by exactly the two 0.600 mm holes the board has. That is the
class of defect this sheet exists to catch — a package that looks complete, lists its tool, and is
missing holes.

For CS the copper extends **1.720 mm beyond Edge_Cuts** on F_Cu (`artefacts/extents.txt`): those are
the five Molex edge-launch SMA lands, waived by the repo's own rule file, and correct for the part.

### 2.11 Revision stamp
`GetTitleBlock().GetRevision()`: DA `""`, ESC `""`, CS `"2.1"` `M-*`. Only DA carries any revision
marking in artwork (`REV-B FLIGHT CONTROL - DISTINCT FROM ESC`, F.Silkscreen); ESC carries none
anywhere. The rev_b package's job file does say `"B"` — because that unit patched the title block in
its own copy (5 added lines, `../fab-da-gerbers/title_block_rev_B.patch`), which is why the fix is
"apply the patch, re-export" and not "fix the artwork".

### 2.12 Panel size
Edge bounding box from `GetBoardEdgesBoundingBox()` `M-*`, cross-checked against the plotted
Edge_Cuts extents (`artefacts/extents.txt`). **No board has a panelisation drawing, rails,
breakaways or fiducials** — all three are 1-up. One coupon panel (100 × 100 mm, 2 coupons) exists as a
separate design in `../dec-coupon-60/`; it is not a panel for any of these three boards.

### 2.13 Surface finish
`(copper_finish "ENIG")` in all three board files `M-*`, and `"Finish": "ENIG"` in the DA and CS job
files `G-DA` `EXP-CS`. The stale rev_a job file says `"Finish": "None"` `X-DA` — another reason it
cannot be the order.

---

## 3. What would stop this order today

Only true blockers: things that would produce a wrong board, a refused quote, or guaranteed rework.
Ordered by cost-to-fix-after-fab, because that is the cost that matters.

| # | board | blocker | why it stops the order | fix class | measured size of the job |
|---:|---|---|---|---|---|
| 1 | **DA** | **36 non-through vias — 33 at 0.100 mm** | No non-HDI 4-layer house can drill or plate them. The rev_b package would ship **5 blind/buried Excellon files**; `R-DA-vias:§1` shows 12 of the 36 need nothing but via work | **MOVE** | 24 remain after that 12-via patch (23 microvia + 1 blind) in 20 groups; **13 of those groups have the via centre inside another net's copper** (dist ≤ 0), so no via of any size fits. Needs a fan-out re-escape, not a via edit |
| 2 | **DA** | **no ESC command path in copper**: J60–J65 absent, U10 pads 43–48 carry `unconnected-(U10-GPIOxx)` | The board cannot command an ESC. Fabricating it guarantees hand rework on a 0.4 mm-pitch QFN | **MOVE** | 0 of 7 candidate pads has a legal escape: U10 is 0.4 mm pitch with 0.200 mm pad gaps, and a 0.20 mm track needs 0.45 mm `R-CONN:§1`. Six connectors, six nets, one fan-out |
| 3 | **DA** | **the only package in the repo is rev_a**, and the title block has no revision | A fab reading `pcb-gerbers-1/` builds a 75 mm, 112-footprint board inside a 288 × 204 mm A4 frame, with `Finish: None` and `Revision: "rev?"` | **PARAM** | install the rev_b package (21 files, verified against the board: 369 holes, 140.000 × 100.000, no frame) + `git apply title_block_rev_B.patch` |
| 4 | **ESC** | **499 unconnected items / 540 of 556 nets with no copper** | There is almost nothing to fabricate: 154 segments totalling 628.27 mm, 16 nets routed (2.88 %), 1,978 of 1,990 vias on nets with no track at all `R-ESC:§4.2` | **MOVE** | finish the route. The one free decision: **adopt the 4 oz ruleset first** — it is free now and a 540-net rip-up later |
| 5 | **ESC** | **523 violations at 4 oz, 371 of them 0.200 mm pad gaps inside 9 footprints** | Not routable away: U201 (QFN-80 P0.4), 6 × LQFP-48 P0.5, J202/J203 (USB-C). At 140 µm the pattern floor is 0.25 mm; these pads cannot be made 0.25-compliant by any edit | **RESPIN** unless the fab accepts 0.200 mm in writing (fab burden — the acceptable spend). If refused: 2 oz (geometry already compliant, contradicts "ESC 4 oz only") or change 3 packages — an owner decision, not mine | 371 pad gaps; 62 copper objects have a mechanical fix; 28 vias need re-placement (+54 new conflicts); 49 bus segments need re-spacing; 90 zones need the 0.25 parameter + refill `R-ESC:§5.2` |
| 6 | **ESC** | **no package and no revision marking at all** | Nothing to export, nothing to stamp | **PARAM** | one export once #4 exists; add a title-block revision first |

**Not on this list, deliberately:** every DRC warning on CS (fab houses never read them, §5 of
`R-CS`), the CS 84-net pilot on In1/In2 (a signal-integrity debt, not a process limit — the board
etches and runs), the clock constraint fix (`R-CS`, `../fab-cs-clock/REPORT.md`: a 2-hunk LPF patch,
no copper, no fab step), and everything in §4.

---

## 4. What is cosmetic and should not stop an order

Use this list to end arguments. Each item is real, measured, and irrelevant to a fabrication order.

| # | item | board | why it is cosmetic |
|---:|---|---|---|
| 1 | **199 `lib_footprint_mismatch`** | CS | A board-vs-library comparison. **0 of 373 footprints differ from library in any pad node or 3-D model**; it is deleted silkscreen body lines and `zone_connect` spelling `R-CS:§2.2`. Restoring the library silk on 246 footprints removes all 199 and adds a `silk_over_copper` warning instead |
| 2 | **13 `via_dangling` + 10 `track_dangling`** | CS | Etch and plate like any other copper. 9 are electrically free (deleting them is verified safe: 215 warnings, 0 unconnected); the other 14 are load-bearing one-ended segments whose only correct repair is a copper trim with no fab benefit `R-CS:§3` |
| 3 | **SMA copper 1.720 mm across Edge_Cuts** | CS | The Molex edge-launch lands clamp onto the board edge by design; the repo's own `.kicad_dru` waives exactly J50/J60–J63, and `R-CS:§4` names it. The gerber is right, not wrong (`artefacts/extents.txt`) |
| 4 | **101.70 mm vs the 100 mm panel tier** | CS | 1.7 mm of price class, not a process limit. Paying the next tier up is cheaper than redrawing a 101.7 mm board |
| 5 | **191 schematic-parity items** (161 library-link strings) | DA | Not in the gerber set. They break forward-annotation reproducibility; a fab house never sees them `evidence/fab-readiness/REPORT.md:§3` |
| 6 | **28 segments at 0.2002 mm** | DA | 2 µm over the 0.2 mm rule — inside any etch tolerance. Fix it in the next revision because it is ugly, not because a fab cares |
| 7 | **stackup 1.580 mm over copper vs 1.60 declared** | DA | −1.25 %, inside a normal ±10 % laminate tolerance. Fix is one sentence on the fab drawing (`hf-fab-readiness/REPORT.md:376-402`) |
| 8 | **16 `via_dangling`** | ESC | Vias dropped, tracks not yet drawn; they get connected by the route that blocker #4 requires. Zero action now |
| 9 | **1.5 oz inner layers (0.0525 mm)** | ESC | Inner weight is a lamination input the shop controls; it is not a customer-facing geometry and no rule depends on it |
| 10 | **0 fiducials, 0 test points, no panelisation, no assembly drawing** | all three | These stop an **assembly PO**, not the etch order (§7). For CS specifically, none of them is a reason to hold the bare-board order |
| 11 | **no silk revision marking** | CS | The title block and the job file carry `2.1`. Silk artwork is not the revision control of record |

---

## 5. The three hard constraints, stated for the signature

**Constraint 1 — NO HDI on any board. No 0.1 mm microvias, no laser drilling, no blind or buried
vias. Standard plated through vias only, 0.2–0.3 mm drill** (`AGENT_BOARD.md:448-456`).

| board | state | measured |
|---|---|---|
| drone-arm main rev_b | **VIOLATED — BLOCKER** | 341 vias, **36 non-through**; 33 at **0.100 mm** drill (`M-DA`). A no-HDI DRC rule returns exactly **33 errors** (`D-DA`), and 5 blind/buried drill files carry 36 of the 369 holes |
| ESC rev_b | **COMPLIES** | 1,990 vias, **0 non-through**, min drill **0.300** mm (`M-ESC`) |
| Code-SDR V2 | **COMPLIES** | 1,085 vias, **0 non-through**, drills 0.200 / 0.250 / 0.400 mm (`M-CS`) — the board the board-notes once blamed for "36 HDI vias" is clean; the correction at `AGENT_BOARD.md:454-457` is confirmed here |

**Constraint 2 — ONLY the ESC is 4 oz. ESC 4 oz (0.14 mm outer); drone-arm main and Code-SDR V2 are
1 oz (0.035 mm)** (`AGENT_BOARD.md:34-57`).

| board | declared & measured | consequence |
|---|---|---|
| ESC rev_b | 0.140 outer / 0.0525 inner `M-ESC` | 4 oz forces 0.25 track/space and 0.20 ring: the board currently fails 523 lines of it. **This is a real cost of the weight, not a defect of the rule** |
| drone-arm main | 0.035 ×4 `M-DA` | 1 oz rules; no 4 oz constraint applies |
| Code-SDR V2 | 0.035 ×4 `M-CS` | as above |

**Constraint 3 — coupon / prototype spend cap $60 total, launches and shipping included**
(`AGENT_BOARD.md:458-464`).

| item | value | source |
|---|---|---|
| planned coupon set | **$54.24** | `../dec-coupon-60/REPORT.md:21, :265` |
| headroom under $60 | **$5.76** | same, `:22` |
| what it buys | 2 coupons (CA 74.53 Ω / CB 50.19 Ω) on one **100 × 100 mm** panel, **2 SMA launches**, 5 boards ordered | `AGENT_BOARD.md:636-649` |
| committed to date | **$0.00** — no coupon order has been placed | no order artefact exists in `evidence/` |
| does the cap bind this sheet? | **No.** None of these three boards is a coupon or prototype under that cap; the cap governs the impedance coupon that settles whether the *coplanar pour* is carrying the reference | — |

---

## 6. Verdict per board — one line each, and what to do in order

**drone-arm main rev_b — NOT ORDERABLE.** The design is DRC-clean and the rev_b package is now real
and provably the board, but **36 vias cannot be drilled by a non-HDI house**, the board has no ESC
command path at all, and the revision field the order is signed against is empty. Order of work:
① convert or re-escape the 24 remaining sub-standard vias (12 of 36 already proven convertible);
② give U10 pads 43–48 an escape and place J60–J65; ③ `git apply title_block_rev_B.patch`, re-export
without the worksheet frame, and confirm what the ①-fixed board should produce: **2 drill files and
369 holes**. Until ① is done the 369 holes still come in 7 files, and 5 of those are the ones a
4-layer house refuses.

**ESC rev_b — NOT ORDERABLE, and not because of the fab.** 97.1 % of the route does not exist
(154 segments, 628 mm), so there is nothing to fabricate; and when it is routed, 0.200 mm pad gaps
inside nine footprints mean **4 oz cannot be built from these packages** unless a heavy-copper shop
accepts 0.200 mm in writing. Order of work: ① install the 4 oz ruleset **now** (free before routing,
a 540-net rip-up after); ② decide 4 oz vs 2 oz on the measured pair (523 vs 16 violations) or get
the fab's written acceptance; ③ finish the route; ④ stamp a revision and export. The 4 tracks at
0.200 mm and the 28 via rings are a day of mechanical work; the pad gaps are the decision.

**Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today.** 0 errors, 0 unconnected, 222 warnings that no
fab house reads, a complete frame-free package whose drill census matches the board hole for hole
(1,215), a finish, a thickness that closes, and a revision in the job file. Two quote lines, neither
a redesign: **0.100–0.125 mm annular ring** against a 0.15 mm published house standard, and
**0.100 mm track/space** at 1 oz — both are "pay the tighter tolerance", which costs less than
rework. Send `export/cs/` (or a fresh export), **not** `../fab-cs-drc/fabpkg/`, which is 2 holes
short. Assembly needs §7 first.

---

## 7. Companion — what an *assembly* PO still needs (does not block the etch)

| item | DA | ESC | CS |
|---|---|---|---|
| BOM for this board | **PASS** — `docs/hardware/REV_B_BOM.csv`, 173 lines = 172 data rows, 161 PCB refs, 0 blank MPNs | **the same file covers the ESC** — F701 is row `:57`, the main board's F1 is row `:140`; this is one BOM across two boards, not two BOMs | **MISSING** — only `redesign/V1_BOM.csv`, a different board |
| BOM defect | **F1 carries a phantom MPN** `1206L075/24WR` (`REV_B_BOM.csv:140`) → `1812L075/33DR` `R-SERVO:§2` | same phantom MPN at **F701** (`REV_B_BOM.csv:57`), fixed in that unit's candidate | no BOM to check |
| pick-and-place | **PASS** — 161 rows, H1–H4 excluded, `G-DA` | none | exports: **373 rows**, or **371** with `--exclude-dnp` (the 2 DNP are `R153`, `R156`); both exist in `../fab-cs-clock/` as `Code-SDR-V2-pos.csv` and `Code-SDR-V2-pos-exclude-dnp.csv` |
| fiducials | **0** | **0** | **0** |
| test points | **0** | **0** | **0** |
| panel / rails / breakaway | none | none | none |
| assembly drawing | none | none | none |

Adding fiducials and probe pads is copper; on CS it is the one thing worth doing at the *next*
revision rather than paying for a respin now — but it does not hold the bare-board order.

---

## 8. UNVERIFIED — what this sheet does not know

1. **Whether a heavy-copper shop will accept 0.200 mm pad gaps at 140 µm.** This is the single
   question that decides ESC blocker #5. It is a written answer in a quote, not a measurement
   available here. Two shops should be asked (PCBWay lists 4 oz; JLCPCB cannot build 4-layer 4 oz at
   all, `R-ESC:§1.2`).
2. **Whether a fab's DFM will pass the 0.100–0.125 mm annular ring on CS**, after its own etch
   compensation. KiCad does not model etch compensation; no DFM report exists.
3. **Solder-mask dam width between fine-pitch pads** on all three boards (0.4–0.5 mm pitch parts on
   DA and ESC, QFN/U.FL on CS). Every board declares `solder_mask_min_width 0.05`, but only the fab
   can confirm the dam its process yields.
4. **Every impedance value.** Two 2D finite-difference solves exist; a measurement does not, and the
   coupon that would settle the coplanar-pour question is planned, not ordered (§5).
5. **Panelisation cost/feasibility** for any of the three — no panel drawing, no quote.
6. **DA's 4 `extra_footprint` parity items** — `kicad-cli` emits the type without a reference designator.
7. **Whether the CS 84-net In1/In2 pilot** changes any measurement a fab house cares about. It does
   not stop an etch; it is unquantified signal integrity.

---

## 9. Artefacts and reproduction

| file | what it is |
|---|---|
| `REPORT.md` | this sheet |
| `measure.py` → `measure/*.json` | every column-1..13 quantity, per board, from `pcbnew` |
| `summarize_drc.py` | counts/types/unconnected/min-`actual` from any DRC JSON |
| `manifest.py` → `artefacts/drc_summary.md` | **every DRC run behind §1 and §2.9**, one row each, machine-generated |
| `gerber_extents.py` → `artefacts/extents.txt` | the plotted outline of every package, including the stale rev_a frame |
| `drill_census.py` → `artefacts/drill_census.txt` | hole census per drill file; this is how the 2-hole shortfall was found |
| `artefacts/repo_scans.txt` | recursive artefact scan of all three repo trees |
| `gate/dapr/`, `gate/escpr/` | faithful board copies + the correct-rules `.kicad_dru` + the DRC JSON |
| `probe/dapr/`, `probe/escpr/`, `probe/cspr2/` | min-space probe copies and JSON (cspr2 is faithful: repo `.kicad_dru` + libs) |
| `export/cs/` | a complete CS package exported from a byte copy: 11 Gerbers, job, merged drill (1,215 holes), pos (373 rows) |
| `check_report.py` | self-check on this file: 3 data rows × 14 columns, no empty cell, no `TBD` |

**Fidelity of every copy used.** The sibling directories' copies of the boards are byte-identical to
the repo files, verified by SHA-256 in this item:

| board | sha256 | vs repo |
|---|---|---|
| drone-arm main rev_b | `9B3BBA85…F89953C` | `../fab-da-vias/base.kicad_pcb` **identical** |
| ESC rev_b | `99257057…7995DDD` | `../fab-esc-4oz/kicad/esc_rev_b.kicad_pcb` **identical** |
| Code-SDR V2 | `309414D2…B09FF486` | `../fab-cs-drc/drcenv/V0.kicad_pcb` **identical** |

So the sibling DRC numbers quoted in §2.9 are numbers about the repo boards, not about copies that
drifted.

Reproduce the four load-bearing commands:

```
"C:/Program Files/KiCad/9.0/bin/python.exe" measure.py
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" pcb drc --format json --severity-all --units mm \
    -o gate/dapr/drc_correct_rules.json  gate/dapr/main_rev_b.kicad_pcb
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" pcb drc --format json --severity-all --units mm \
    -o gate/escpr/drc_4oz_correct_rules.json  gate/escpr/esc_rev_b.kicad_pcb
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" pcb export drill --output export/cs/gerbers/ \
    --format excellon --drill-origin absolute  export/cs/Code-SDR-V2.kicad_pcb
```

---

## 10. Measurement notes and corrections made inside this item

1. **No `BOARD CORRECTION` is required against `AGENT_BOARD.md`.** Every number on the board that I
   touched reproduced: 4 layers each, ESC 4 oz, DA 33 sub-0.2 vias, ESC min drill 0.300, CS zero
   microvias. The board's own correction at `:454-457` (the 36 HDI vias are on drone-arm, not
   Code-SDR) is confirmed by measurement here.
2. **The tasking brief's ESC line ("2,144 tracks, 1,990 vias") is already corrected by
   `../fab-esc-4oz/REPORT.md:71-83`** — 2,144 is segments **+** vias (154 + 1,990) — and my census
   reproduces 154 segments / 1,990 vias to the hole. Recorded here so the same slip is not inherited
   by the next reader of the brief.
3. **My own first CS probe was wrong and is not in this sheet.** Running DRC in a copy directory
   without the repo's `.kicad_dru` and footprint libraries invented 25 edge-clearance errors and 24
   library errors. Cause and correction in §2.3; the unfaithful run was deleted.
4. **A clean DRC is not evidence of fabricability.** DA scores 0 violations under its own rules — which
   still allow `min_microvia_drill 0.1` — and is the least orderable of the three boards. The rule set
   is the thing being audited, not only the board.
5. **A package can be complete and still be wrong.** `../fab-cs-drc/fabpkg/` declares a 0.600 mm tool,
   drills nothing with it, and is 2 holes short of the board. It was caught only by counting holes
   against `1,085 vias + 128 PTH + 2 NPTH`, not by looking at the file list.

---

*One board, one truth. If a number here is not on a command or a file, it does not exist.*