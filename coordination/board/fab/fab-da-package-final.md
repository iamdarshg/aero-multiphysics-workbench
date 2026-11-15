# drone-arm main rev_b — FINAL fabrication package, from the COMPOSED board

**Unit:** fab-readiness wave 3 · `fab-da-package-final`
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-package-final/`
**Package:** `package/` (28 files) and `drone-arm-main-revB-fab-FINAL.zip`
(zip sha256 `9857E06B6E53AA3657EB6B02A002E430DBC8EAED37EFA18DE7F8767059AA5C81`, 383,887 bytes, 28 entries)
**Assertions:** **48 / 48 PASS**, on two independent from-scratch runs (`run_run1.log`, `run.log`)
**Sendable:** **NO** — one reason, measured on the package itself: the drill set is HDI.

Board line for the pinned board (for the lead to paste — this unit writes only its own folder):

> **drone-arm rev_b — FINAL package built from the composed board.** `evidence/fab-da-package-final/`:
> 11 Gerbers + .gbrjob + 7 Excellon + .pos + README (28 files, zip sha `9857E06B…5C81`), rev **B** stamped,
> **48/48** assertions. Edge_Cuts **140.000 × 100.000** (incl. stroke 140.150 × 100.150 = pcbnew bbox), 366 holes,
> 161 `.pos` rows / 165 footprints, gbrjob **140.15 × 100.15 · 1.6 mm · ENIG · Rev B**. **NOT sendable:**
> the drill set carries **24 non-through holes in 5 blind/buried files — 23 × 0.100 mm** — which is HDI.

---

## 0. The six answers, plainly

| question | answer |
|---|---|
| Export command | `kicad-cli pcb export gerbers/drill/pos` from `work/main_rev_b.kicad_pcb` (the stamped copy of the composed board); full lines in §2 |
| Does the title-block patch still apply to the composed board? | **Yes.** `git apply --check` exit 0 on the composed board *and* on its original target; the applied stamp adds exactly 5 lines and nothing else; all 11 layers are geometry-identical before/after |
| Assertion pass count | **48 / 48** (28 carried forward from wave 2 + 20 new), twice |
| Edge_Cuts vs board bbox | centreline **140.000 × 100.000 mm**; incl. 0.15 mm stroke **140.150 × 100.150** = pcbnew `GetBoardEdgesBoundingBox` **140.150 × 100.150**; 4 draw primitives, so **no sheet frame** |
| Drill tool count / hole census | **7** diameters `0.10, 0.20, 0.30, 0.35, 0.60, 0.65, 4.30`; **366 holes** = 22 PTH pads + 6 NPTH pads + 338 vias (23/18/34/281/4/2/4 by diameter) |
| `.pos` rows vs footprints | **161 rows** = 165 footprints − 4 excluded (H1–H4) |
| gbrjob fields | Size **140.15 × 100.15**, LayerNumber **4**, BoardThickness **1.6**, Finish **ENIG**, ProjectId.Revision **B** (Name `main_rev_b`) |
| Would a fab see blind/buried drills, and how many? | **Yes — they are separate Excellon files at the package root.** 5 files, **24 holes**: 23 × 0.100 mm + 1 × 0.300 mm |
| Is this sendable? | **NO.** Everything except the via set is ready; the 23 × 0.100 mm holes are laser-drill (HDI) and the 5-file blind/buried set is sequential-laminate |

---

## 1. Inputs, and what proves the package came from the composed board

| item | value | evidence |
|---|---|---|
| input board | `evidence/fab-da-consolidate/da_main_rev_b_composed.kicad_pcb` | `run.log` A01 |
| input sha256 | `5DBAE23888059E0B6D6F18DC3066924FB8194C5FD4DFA250186D3B024F6F73B6` | `run.log` A01/A04, unchanged at end (B26) |
| original rev_b board sha256 | `9B3BBA85C01AAC9E…` — **not** the input | `run.log` A02 |
| project rules file | composed `.kicad_pro`, byte-identical to `repos/…/main_rev_b.kicad_pro` (`186A4D4A…F719`) | measured before the run |
| title-block patch | `evidence/fab-da-gerbers/title_block_rev_B.patch`, sha256 `7D4A1343…` — **same bytes** as the wave-2 unit's | `run.log` A03 |

Two independent cross-checks that the *content* moved from the original to the composed board:

* **Via count.** The wave-2 package's board has **341 vias / 369 holes**
  (`evidence/fab-da-gerbers/boardfacts.json`); this one has **338 vias / 366 holes**
  (`boardfacts_final.json:56`, `:107`). Difference **−3**, which is exactly
  `compose_manifest.json` → `"vias_net": -3` (12 deleted, 9 added).
* **Copper geometry.** Plotting the *original* rev_b board and the package and diffing per layer
  (`diff_composition.json`) reports the four copper layers as **differing** —
  B.Cu 7,903 · F.Cu 18,474 · In1.Cu 24,852 · In2.Cu 2,070 differing geometry lines — and
  Edge_Cuts, both masks, both pastes, both silkscreens as **identical (0 lines)**
  (`diff_composition.json:18`, `:27`). That is the signature of a track/via/zone change with no
  outline or documentation change: **the package is the composed board, not the original.**

---

## 2. The export (frame suppressed)

Everything is done on **copies inside this evidence dir**; no repo, no branch, no commit. The source
is read, hashed, and hashed again at the end (B26 PASS).

```
# 0. copy the composed board (never the original), same file name so the Gerber X2
#    ProjectId Name/GUID stay stable -> work/src/main_rev_b.kicad_pcb
# 1. stamp: git apply title_block_rev_B.patch in a scratch repo -> work/main_rev_b.kicad_pcb
# 2. plot:
kicad-cli pcb export gerbers --output package --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --precision 6 work/main_rev_b.kicad_pcb
kicad-cli pcb export drill   --output package --format excellon --drill-origin absolute --excellon-units mm --excellon-zeros-format decimal --excellon-separate-th --generate-map --map-format gerberx2 work/main_rev_b.kicad_pcb
kicad-cli pcb export pos     --output package/main_rev_b-REV-B-all-pos.csv --side both --format csv --units mm work/main_rev_b.kicad_pcb
```

The frame is suppressed by **omission** of `--include-border-title`, and the suppression is proven two
ways rather than asserted:

* Edge_Cuts comes out as **4 primitives, one aperture (C 0.15)**, `extents.json:187-205`;
* a deliberate `--include-border-title` control plot of the *same* board measures
  **287.0022 × 200.0072 mm** (`control_extents.json`) — the A4 sheet, i.e. the flag is what moves it.

Output tree: `package/` is flat and zip-ready — 11 Gerbers, `.gbrjob`, **7 Excellon at the root**,
`.pos`, `FAB-README-REV-B-FINAL.txt`; the 7 drill **maps** are parked in `package/drill_maps/` so a CAM
tool globbing `*.gbr` cannot mistake a map (which flashes every hole) for copper.

---

## 3. Revision stamp: does the wave-2 patch still apply to a *different* board?

The composed board has **no `title_block`** (`grep title_block` → 0 hits), the same starting condition
the patch was written for, but its body is 4,815 bytes larger than the original. So the question was
re-tested, not assumed. Four independent facts:

| # | test | result |
|---|---|---|
| A05 | `git apply --check` against the patch's **original** target (control) | exit 0 |
| A06 | `git apply --check` against the **composed** board at the same path | exit 0 |
| A07 | line diff of composed vs stamped | 62,907 → 62,912 lines; head (`0..8`) and tail (`9..end`) **identical**; the 5 inserted lines are exactly the title_block |
| B23 | Gerber geometry diff, composed-unpatched plot vs stamped package | **all 11 layers geometry-identical** (metadata-only change) |

The inserted block (`work/main_rev_b.kicad_pcb:10-14`):

```
	(title_block
		(title "drone-arm main board rev B")
		(date "2026-11-15")
		(rev "B")
	)
```

Revision traceability, measured, not assumed: **19 carriers, all `B`** — the `.gbrjob`
`ProjectId.Revision`, and the `%TF.ProjectId` token of all 18 plotted Gerbers (11 layers + 7 drill
maps), `rev_inventory.json`; plus pcbnew reading it back (`GetRevision()="B"`,
`boardfacts_final.json:116`), plus the F.Silkscreen legend
`"REV-B FLIGHT CONTROL - DISTINCT FROM ESC"` — **256 stroke segments, 53.143 mm wide**
(`silk_band.json`) — which is on the board, not only in the data. KiCad 9 emits no revision field in
Excellon or in the CSV position file (format limitation), so the package name and the `.pos` filename
carry it too.

---

## 4. Validation: 48 assertions, 28 of them carried forward

`assertions.json` holds all 48 as `{id, pass, what, detail}`; `run.log` prints them in order.
**48 pass, 0 fail**, repeated on a second clean run.

### 4.1 The wave-2 set of 28, re-run against the composed package

| wave-2 assertion | this package | id |
|---|---|---|
| board is 4 copper layers | 4 | B01 |
| copper Gerber count == `GetCopperLayerCount` | 4 / 4 | B02 |
| gbrjob LayerNumber == layers | 4 | B03 |
| gbrjob lists all 11 plotted files | 11 | B04 |
| Edge.Cuts centreline 140.000 × 100.000 | 140 × 100 | B05 |
| Edge.Cuts incl. stroke == pcbnew bbox | 140.15 × 100.15 | B06 |
| Edge.Cuts has 4 primitives (no frame) | 4 | B07 |
| no plotted layer exceeds the outline | max 140.150 × 100.150 | B08 |
| frame control plot carries the sheet | 287.00 × 200.01 | B09 |
| distinct drill diameters == tool table | 7 | B10 |
| drill hits == pads + vias | 366 | B11 |
| `.pos` rows == footprints − excluded | 161 | B12 |
| `.pos` header standard | `Ref,Val,Package,PosX,PosY,Rot,Side` | B13 |
| gbrjob Size == board bbox | 140.15 × 100.15 | B14 |
| gbrjob BoardThickness == thickness | 1.6 | B15 |
| gbrjob Finish == stackup finish | ENIG | B16 |
| every revision carrier reads B | 19 carriers | B17 |
| pcbnew reads the revision back | `B` | B18 |
| REV-B silkscreen legend present | 256 segments | B19 |
| stale rev_a package: 0 of 11 layers byte-identical | 0 / 11 | B20 |
| stale package is a different board (75.05 × 50.05) | 75.05 × 50.05 | B21 |
| stale package has no position file | 0 | B22 |
| all 11 layers geometry-equal before/after stamp | 11 | B23 |
| 0 unconnected (project rules) | 0 | B24 |
| 0 DRC violations (project rules) | 0 | B25 |
| source board and inputs unmodified | sha unchanged | B26 |
| title_block carries the revision | `(rev "B")` | A08 |
| working copy keeps the package file name | `main_rev_b.kicad_pcb` | A09 |

### 4.2 Twenty new assertions (why this package needed its own gates)

| id | assertion | result |
|---|---|---|
| A01 | input is the verified composed board | `5DBAE238…6F73B6` |
| A02 | input is **not** the original rev_b board | `9B3BBA85…` ≠ input |
| A03 | patch byte-identical to the wave-2 patch | `7D4A1343…` |
| A04 | working copy is a byte-copy of the composed board | identical sha |
| A05 | patch applies to its original target | exit 0 |
| A06 | patch applies to the **composed** board | exit 0 |
| A07 | stamp inserts exactly 5 lines, nothing else | 62,907 → 62,912 |
| C01 | via census == verified state | 338: 0.100×23, 0.300×34, 0.350×281; non-through 24 |
| C02 | 7 Excellon files | 7 |
| C03 | 5 blind/buried files | front-in1, front-in2, in1-in2, in1-back, in2-back |
| C04 | blind/buried hits == non-through vias | 24 == 24 |
| C05 | **every** drill file matches pcbnew **per tool**, not just in total | 7/7 |
| C06 | PTH file == through vias + PTH pads | 336 = 314 + 22 |
| C07 | NPTH file == NPTH pads | 6 = 6 |
| C08 | gbrjob ProjectId.Revision | `B` |
| C09 | composition visible: In1.Cu differs from the original board | 24,852 lines |
| C10 | via fix visible: F.Cu differs from the original board | 18,474 lines |
| C11 | no-HDI gate on the **packaged** board: 23 violations, all `microvia_drill_out_of_range` | 23 |
| C12 | no-HDI gate: 0 unconnected | 0 |
| C13 | zip == package | 28 entries / 28 files |

C05 is the one that matters most for trust: it compares each Excellon file's **hits per tool
diameter** against the pcbnew census of the layer pair named in that file's `TF.FileFunction`, so a
total that happens to add up cannot hide a hole in the wrong file.

---

## 5. Edge_Cuts vs the board's own bounding box

| measurement | value | source |
|---|---|---|
| Edge_Cuts coordinate bbox (centreline) | **140.000 × 100.000 mm** | `extents.json:187-205` |
| + 0.15 mm stroke radius each side | 140.150 × 100.150 | `extents.json` |
| pcbnew `GetBoardEdgesBoundingBox()` | **140.150 × 100.150** | `boardfacts_final.json:11` |
| Edge.Cuts primitives | 4 × D01, 1 aperture (C 0.15) | `extents.json:189-205` |
| sheet-frame control plot | 287.0022 × 200.0072 | `control_extents.json` |

A frame would show up as thousands of D01 primitives and a ~287 mm extent. Neither is present.

---

## 6. Drill tool count and the hole census — file by file

`drill_census.json`, cross-checked against pcbnew tool-by-tool:

| Excellon file | `TF.FileFunction` | holes | diameters |
|---|---|---|---|
| `main_rev_b-PTH.drl` | `Plated,1,4,PTH` | **336** | 0.20 ×18, 0.30 ×33, 0.35 ×281, 0.60 ×4 |
| `main_rev_b-NPTH.drl` | `NonPlated,1,4,NPTH` | **6** | 0.65 ×2, 4.30 ×4 |
| `main_rev_b-front-in1.drl` | `Plated,1,2,Blind` | **11** | 0.10 ×11 |
| `main_rev_b-front-in2.drl` | `Plated,1,3,Blind` | **2** | 0.10 ×2 |
| `main_rev_b-in1-back.drl` | `Plated,2,4,Blind` | **3** | 0.10 ×3 |
| `main_rev_b-in1-in2.drl` | `Plated,2,3,Buried` | **5** | 0.10 ×5 |
| `main_rev_b-in2-back.drl` | `Plated,3,4,Blind` | **3** | 0.10 ×2, 0.30 ×1 |
| **total** | | **366** | 7 tools |

Hole census: **0.100 ×23, 0.200 ×18, 0.300 ×34, 0.350 ×281, 0.600 ×4, 0.650 ×2, 4.300 ×4 = 366**
(`drill_census.json:181`; pcbnew agrees, `boardfacts_final.json:98-107`).
Composition: 22 PTH pads + 6 NPTH pads + 338 vias (`boardfacts_final.json`), of which 314 vias are
through and **24 are non-through** (`:56`, `:58`).

The non-through set, by layer pair and drill (`boardfacts_final.json:75-94`):

| layer pair | vias | drill | gate result |
|---|---|---|---|
| F.Cu → In1.Cu | 11 | 0.100 | violation |
| In1.Cu → In2.Cu (buried) | 5 | 0.100 | violation |
| F.Cu → In2.Cu | 2 | 0.100 | violation |
| In2.Cu → B.Cu | 3 | 0.100 ×2 + **0.300 ×1** | 2 violations, 1 in mechanical range |
| In1.Cu → B.Cu | 3 | 0.100 | violation |
| **total** | **24** | | **23** `microvia_drill_out_of_range` |

---

## 7. Position file

* **161 data rows**, header `Ref,Val,Package,PosX,PosY,Rot,Side`
  (`rev_inventory.json` → `pos`; `boardfacts_final.json` → `expected_pos_rows`).
* 165 footprints − 4 position-excluded (H1, H2, H3, H4 mounting holes) = 161.
* All 165 footprints are on **F.Cu** (`footprints_by_side F=165 B=0`), which is also why
  `B_Mask`, `B_Paste` and `B_Silkscreen` plot as empty files — a fact a fab will notice, so it is
  stated rather than left to be discovered.

---

## 8. The `.gbrjob` the fab actually reads

| field | value | check |
|---|---|---|
| `GeneralSpecs.Size` | **140.15 × 100.15** | == pcbnew edge bbox (B14) |
| `GeneralSpecs.LayerNumber` | **4** | == `GetCopperLayerCount` (B03) |
| `GeneralSpecs.BoardThickness` | **1.6 mm** | == design settings (B15) |
| `GeneralSpecs.Finish` | **ENIG** | == stackup `copper_finish` (B16) |
| `GeneralSpecs.ProjectId.Revision` | **B** | (C08) |
| `GeneralSpecs.ProjectId.Name` | `main_rev_b` | stable because the copy keeps the name (A09) |
| `FilesAttributes` | 11 entries | (B04) |
| `DesignRules` | outer 0.20 / inner 0.20 clearance, min line width 0.20 | read from the board |
| `ImpedanceControlled` | `true` | **see note below** |

**Note on `ImpedanceControlled: true`:** the wave-2 package's job file carries the identical value, and
**neither the board nor the project file contains any impedance setting** (`grep -i impedance` over
`work/main_rev_b.kicad_pcb` and `work/main_rev_b.kicad_pro`: 0 hits) — so this field is emitted by
KiCad 9.0.7's writer, not claimed by this export. It is flagged because a fab that reads it may come
back asking for a target, and on this board there is still **no measured impedance sign-off**
(`AGENT_BOARD.md`, "no impedance sign-off on either board"). It does not stop an etch order.

---

## 9. Should a fab receive this package? What is still wrong with it

**The package itself is correct.** It is a faithful, revision-stamped, frame-free description of the
board a fab would build, and everything a fab needs to *quote and plan* is present and consistent:
one outline, four copper layers, seven drill tools, a position file, and a job file whose six key
fields agree with the board. Nothing in it overstates the board: the copper is 1 oz, thickness 1.6 mm,
finish ENIG, and the drill files are the board's own holes.

**It is not sendable, and the reason is one drill set.** The drill files **do** include the
blind/buried holes — they are delivered as **5 separate Excellon files at the package root**, each
labelled `Blind` or `Buried` in `TF.FileFunction`, carrying **24 holes in total**:

* **23 × 0.100 mm** — laser-drill diameters. On a 4-layer standard-PTH process these cannot be
  drilled or plated at all. The no-HDI gate run on the *packaged board* returns exactly
  **23 `microvia_drill_out_of_range`** violations and **0 unconnected** (C11, C12).
* **1 × 0.300 mm blind via** (In2.Cu → B.Cu) — inside the mechanical range, so the gate does not flag
  it, but it still requires a blind drill and therefore a sequential-laminate schedule.

So a fab reading this package today would either quote HDI (which the owner's constraint bans) or
reject the drill set. That is the one thing that stops the order, and it is a **design** item, not an
export defect: the 24 vias need a **fan-out re-escape**, and per the verified composed state
**all 20 relief groups need one**, 9 of the 20 because the via **centre lies inside another net's
copper** (`evidence/fab-da-consolidate/remain.json:4, 9, 11` — `non_through 24`, `groups 20`,
`groups_centre_inside_foreign_copper 9`; 19 of 20 groups have a minimum drill below 200 µm, `:12`).

### What remains before it can be sent

| # | remaining item | class | owner |
|---|---|---|---|
| 1 | 24 non-through vias in 20 groups → fan-out re-escape to 0.2–0.3 mm standard through vias | **copper move (design)** | next routing pass |
| 2 | the ESC command path is still absent: **no J60…J66 footprints**, and U10 pads **43–48** sit on auto-generated `unconnected-(…)` nets — 64 such single-pad nets in total, 0 *named* nets without copper | **design/schematic** | next design pass |
| 3 | `ImpedanceControlled: true` with no target or measurement | **note** | paperwork / coupon |
| 4 | ESC rev_b 4 oz binary still open (drop to 2 oz, or change 3 packages) | **owner decision**, other board | owner |

Item 2 is stated because it is true of this board file and a fab cannot fix it; it is not a defect of
the package. `q_scope.json` records it: `esc_connectors_present: []`, U10 pads 43–48 each on their own
`unconnected-(U10-GPIO3x-PadNN)` net, `nets_without_track_or_zone_count: 64`, all of them
`unconnected-(…)`, **0 named nets without copper**.

Fix items 1–2 and re-run the script in §10: the export, the stamp and all 48 assertions re-verify the
new board with no manual step.

---

## 10. Reproduce in one command

```powershell
pwsh -NoProfile -File E:\engineering-portfolio-audit\evidence\fab-da-package-final\export_fab_package_final.ps1
```

That is the whole run: it copies the composed board, tests and applies the title-block patch, plots the
unpatched reference / original reference / frame control, exports the package, runs pcbnew facts, the
Gerber extents, the revision inventory, the drill census, the stale-package comparison, the silkscreen
band check, the two geometry diffs, DRC under both rule sets, writes the README, the SHA-256 manifest
and the zip, and prints `SUMMARY: 48 pass, 0 fail`. Exit code is non-zero if any assertion fails.
Every command line is echoed verbatim into `run.log`.

Directory contents (all of it inside `evidence/fab-da-package-final/`):

| file | what it proves |
|---|---|
| `package/`, `drone-arm-main-revB-fab-FINAL.zip` | the deliverable (28 files) |
| `work/src/main_rev_b.kicad_pcb` | unpatched composed copy (reference plot input) |
| `work/main_rev_b.kicad_pcb(+.kicad_pro)` | stamped copy the package was plotted from; nothing else is ever plotted |
| `_ref_unpatched/`, `_ref_original/`, `_control_frame/` | stamp no-op proof, composition proof, frame-control proof |
| `_patchtest/control`, `_patchtest/composed` | the two `git apply --check` runs (scratch repos, local only) |
| `_drc/drc_own.json`, `_drc/drc_gate.json` | 0/0 under the board's rules; 23 microvias under the no-HDI gate |
| `boardfacts_final.json` | pcbnew truth incl. via span × drill census |
| `drill_census.json` | per-file, per-tool Excellon census vs pcbnew |
| `extents.json`, `control_extents.json` | measured Gerber extents, frame suppressed / enabled |
| `rev_inventory.json` | every revision carrier and the gbrjob fields |
| `diff_geometry.json`, `diff_composition.json` | stamp moved no copper / package is the composed board |
| `silk_band.json`, `stale_compare.json`, `q_scope.json` | legend present, stale rev_a is a different board, scope gaps |
| `assertions.json`, `run.log`, `run_run1.log` | 48/48 twice |
| `PACKAGE-SHA256.txt` | sha256 of every package file |

---

## 11. What this report does NOT claim

* **Not fabbable yet.** 23 microvias + 1 blind via remain; see §9. No fab quote is implied.
* **No impedance measurement.** The package describes geometry; it does not certify Z0.
* **No assembly data.** No BOM, no pick-and-place notes beyond the `.pos`, no footprint-vs-BOM check —
  this is a bare-board package.
* **The `.pos` is positional only** — rotation/side as KiCad reports them; it is not an assembly
  drawing.
* **Two runs, same assertions — not byte-identical zips.** Gerber/zip timestamps differ between runs;
  the *geometry* is identical (that is what B23 compares), the container bytes are not. This is the
  same non-reproducibility the drone-mech report had to state about its PDF.

## 12. Corrections / clarifications carried into this unit

* **Not a contradiction, an input change:** `AGENT_BOARD.md:546` describes the wave-2 rev_b package as
  **21 files / 369 holes**. That package was built from the **original** board. This one is built from
  the **composed** board and has **21 fabrication files + 7 drill maps = 28 files**, and **366 holes**
  (−3 vias, matching `compose_manifest.json`'s `vias_net: -3`). The drill-map subfolder is why the
  headline file count differs; the fabrication file count is unchanged.
* **The wave-2 README's "33 × 0.100 blind/buried (36 total)" is the original board, not this one.**
  Measured here: **23 × 0.100 + 1 × 0.300 = 24**, consistent with the 12-deleted/9-added via fix.
* **`ImpedanceControlled: true` is KiCad's writer, not a claim by this package** — identical in the
  wave-2 package, and no impedance setting exists in the board or project files.