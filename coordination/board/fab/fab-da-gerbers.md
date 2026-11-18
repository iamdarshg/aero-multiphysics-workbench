# fab-da-gerbers — drone-arm main rev_b, a stamped fabrication package

**Item:** replace the stale `rev_a` Gerber package with a properly revision-stamped `rev_b`
package, and prove it describes the board.
**Board of record:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`, 2,252,603 bytes,
SHA-256 `9B3BBA85C01AAC9E8365AF999F5231C3951E3428C37544A2B2CADC425F89953C` (identical before and
after this run — the script fails if it changes).
**Tool:** KiCad 9.0.7 (`kicad-cli.exe` for plot/drill/pos/DRC, `python.exe` + `pcbnew` for board truth).
**Nothing was written into any repo.** No git write command of any kind was run against the repos;
the one `git diff --no-index` / `git apply --check` pair ran in `%TEMP%` on copies.
**No fabrication was performed.**

**Reproduce:** [`export_fab_package.ps1`](./export_fab_package.ps1) — 28 assertions, all pass,
exit 0. Everything below is its output; `run.log` holds every command line verbatim.

---

## 1. Verdict

**The package is correct, complete, stamped and provably the board. It is not yet orderable, and
the reason is not the package.** One line of the hard constraints is still violated by the design
that this package faithfully describes.

| question | answer |
|---|---|
| Is this a valid rev_b fab package? | **Yes.** 11 Gerbers + `.gbrjob` + 7 Excellon + 161-row `.pos`, frame-free, `Revision: B`. |
| Does it describe *this* board? | **Yes**, four independent ways (§9). |
| Is it the stale package? | **No.** 0 of 11 layers byte-identical; the stale `.gbrjob` says Size **75.05 × 50.05 mm** and Finish **None**. |
| Is the package ORDERABLE? | **The package, yes. The board, no** — 36 blind/buried vias, 33 of them 0.100 mm, across 5 layer pairs. Standard 4-layer PTH only, per `AGENT_BOARD.md:448-456`. |
| What human action remains? | `git apply title_block_rev_B.patch` in the repo (5 added lines), so future exports are born stamped. Verified to reproduce this package's source board byte-for-byte. |

The second blocker is **not mine to fix** and cannot be fixed in a Gerber export: it is the via
conversion item (`evidence/da-via-conversion/`, `evidence/dec-hdi-conversion/`). Shipping this
package to a normal 4-layer house would draw a quote rejection on the five blind/buried drill files.

---

## 2. What was produced

```
drone-arm-main-revB-fab.zip        392,071 B   sha256 1B2786BACF32FAD452AE50AFE00B13428CFA638B16A5660A440731A7211E31E0
package/                           28 files
  main_rev_b-*.gtl/.g1/.g2/.gbl/.gts/.gbs/.gto/.gbo/.gtp/.gbp/.gm1   11 Gerbers
  main_rev_b-job.gbrjob                                               job file, Revision "B"
  main_rev_b-PTH.drl / -NPTH.drl                                      2 through-hole files
  main_rev_b-front-in1/-front-in2/-in1-back/-in1-in2/-in2-back.drl     5 blind/buried files
  main_rev_b-REV-B-all-pos.csv                                        161 rows
  FAB-README-REV-B.txt                                                stackup/finish/drill/rev note
  drill_maps/*.gbr                                                    7 maps (documentation, not data)
PACKAGE-SHA256.txt                 sha256 of all 28 files
```

The 7 drill **maps** were moved into `drill_maps/` after export. Their `%TF.FileFunction` is
`Drillmap`, so a CAM front-end should skip them anyway, but a tool that globs `*.gbr` at the package
root would otherwise see seven files that flash every hole in the board. Folder placement is the
cheaper defence.

Protel extensions (`.gtl/.g1/.g2/.gbl/.gm1/…`) rather than 11×`.gbr`: a fab auto-maps the former
by extension, and `%TF.FileFunction` + the `.gbrjob` map every file either way.

---

## 3. Revision — every place it appears, before and after

The board had **no `title_block` node at all** (`Select-String -Pattern 'title_block'` → 0 hits;
the file goes `(generator_version "9.0")` → `(general …)` → `(paper "A4")` → `(layers …)`).
`rev?` is therefore KiCad's *fallback* token, not a stored value. That is why "the rev field still
reads unresolved" resisted export-only fixes.

| # | artefact | field | before | after | does a fab read it? |
|---|---|---|---|---|---|
| 1 | `.kicad_pcb` | `title_block` | **section absent** | `(rev "B")` + title + date | source of everything below |
| 2 | `.gbrjob` | `GeneralSpecs.ProjectId.Revision` | `rev?` | **`B`** | **cosmetic** — no CAM step branches on it |
| 3 | 11 layer Gerbers | `%TF.ProjectId,<name>,<guid>,<rev>` | `…,rev?` | **`…,B`** | **cosmetic** — X2 revision token |
| 4 | 7 drill-map Gerbers | same X2 attribute | `…,rev?` | **`…,B`** | **cosmetic** |
| 5 | 7 Excellon `.drl` | — | **no revision field exists** | unchanged | nothing to read |
| 6 | `.pos` CSV | — | **no revision field exists** | unchanged header | assembly keys on the **filename** |
| 7 | `F.Silkscreen` | `gr_text` | `REV-B FLIGHT CONTROL - DISTINCT FROM ESC` | unchanged | **yes — by humans** |
| 8 | filenames | package zip, `.pos` | `main_rev_b-all-pos.csv` | `…-REV-B-all-pos.csv`, `…revB-fab.zip` | **yes** — assembly keys on this |

**Measured after the fix: 19 carriers read `B`, zero read `rev?`** (`rev_inventory.json`;
`Select-String 'rev?'` across the whole package → 0 hits). The 19 = 11 layers + 7 drill maps +
1 `.gbrjob`.

The asymmetry that matters: **the drill *map* carries the revision, the drill *data* does not.**
KiCad's Excellon writer emits no project identity at all:

```
M48
; DRILL file {KiCad 9.0.7} date 2026-11-15T16:20:01+0530
; FORMAT={-:-/ absolute / metric / decimal}
; #@! TF.FileFunction,Plated,1,4,PTH
```

and the CSV position header is `Ref,Val,Package,PosX,PosY,Rot,Side` — no comment block, no column.

So the ordering of what actually matters: **silkscreen (human) > filenames (assembly) > `.gbrjob`
(quoting) > X2 token (nothing) > Excellon/`.pos` (field does not exist)**. The revision was a
*traceability* defect, not a CAM defect — which is exactly how it caused the original mistake: two
structurally different boards both declaring `rev?`.

### The silk legend is really in the plotted Gerber

`silk_band.py` on the exported `main_rev_b-F_Silkscreen.gto`:

| | value |
|---|---|
| total D01 segments | 562 |
| segments in the 1.5 mm band y ∈ [1.685, 3.185] mm | **256** |
| x span of that band | 43.464 – 96.607 mm = **53.143 mm** |

That band is a 40-character 1.5 mm string at `main_rev_b.kicad_pcb:29522-29529` (`(at 70 2.5 0)`,
`(size 1.5 1.5)`). Nothing else on this board is up there.

---

## 4. Sheet frame — suppressed, and proven three ways

| proof | measurement |
|---|---|
| `--include-border-title` is **not** passed | `kicad-cli pcb export gerbers --layers … --precision 6 <board>` (run.log) |
| the board stores the setting off | `main_rev_b.kicad_pcb:114` `(plotframeref no)` inside `(pcbplotparams …)` at `:103-141` |
| measured | Edge.Cuts = **4 D01 primitives**, **1 aperture** (`C,0.15`), bbox **140.000 × 100.000 mm**; every one of the 11 layers ≤ 140.150 × 100.150 |
| positive control (same board, `--include-border-title`) | Edge.Cuts = **287.002 × 200.007 mm**, 875 primitives → the frame is one flag away, so the clean result is caused by the flag and not by a board without a sheet |

**BOARD CORRECTION** — `evidence/w2-da-gerbers/REPORT.md:77-80` says *"The board itself stores no
`plot_params` block and no `use_drawing_sheet` key"*. It does: `(pcbplotparams …)` at
`main_rev_b.kicad_pcb:103-141`, with `(plotframeref no)` at `:114`. The conclusion (a CLI plot is
frame-free by default) is right; the reason given is wrong, and the difference matters — a GUI user
who ticks "plot drawing sheet" overrides a stored `no`, while a CLI user has to pass a flag.

---

## 5. Layers and extents

`GetCopperLayerCount()` = **4**; 4 copper Gerbers; `.gbrjob LayerNumber` = 4;
`FilesAttributes` = **11**. All agree.

| layer | FileFunction | w × h (mm) centreline | incl. stroke | D01 | D02 | D03 |
|---|---|---|---:|---:|---:|---:|
| F.Cu | Copper,L1,Top | 138.999 × 98.999 | 139.699 × 99.699 | 16,837 | 1,211 | 941 |
| In1.Cu | Copper,L2,Inr | 138.999 × 98.999 | 139.699 × 99.699 | 23,273 | 548 | 358 |
| In2.Cu | Copper,L3,Inr | 135.700 × 94.000 | 136.400 × 94.700 | 1,431 | 412 | 349 |
| B.Cu | Copper,L4,Bot | 138.200 × 98.000 | 138.900 × 98.700 | 7,408 | 308 | 338 |
| F.Paste | SolderPaste,Top | 134.155 × 82.200 | same | 0 | 0 | 627 |
| B.Paste | SolderPaste,Bot | **empty** | — | 0 | 0 | 0 |
| F.Silkscreen | Legend,Top | 102.705 × 97.077 | 102.885 × 97.257 | 562 | 562 | 0 |
| B.Silkscreen | Legend,Bot | **empty** | — | 0 | 0 | 0 |
| F.Mask | SolderMask,Top (negative) | 135.255 × 92.000 | 139.555 × 96.300 | 8 | 2 | 607 |
| B.Mask | SolderMask,Bot (negative) | 133.105 × 92.000 | 137.405 × 96.300 | 0 | 0 | 10 |
| **Edge.Cuts** | Profile,NP | **140.000 × 100.000** | **140.150 × 100.150** | **4** | 4 | 0 |

- **Edge.Cuts vs board edge bbox:** the Gerber stores the centreline (140.000 × 100.000); pcbnew's
  `GetBoardEdgesBoundingBox()` adds half the 0.150 mm stroke on each side and returns
  **140.150 × 100.150**. Δ = 0.150 = exactly the `ADD10C,0.150000` aperture. **They agree.**
- `B.Paste` and `B.Silkscreen` are legitimately empty: all 165 footprints are on `F.Cu`
  (`boardfacts.json` → `footprints_by_side = {F:165, B:0}`).
- Copper sits 0.5 mm inside the outline (138.999 vs 140) = normal pull-back, not a shrink.

---

## 6. Drill

**7 distinct diameters, 369 hits** — exactly pcbnew's own count (341 vias + 22 PTH pads + 6 NPTH pads).

| file | FileFunction | tools (mm) | hits |
|---|---|---|---:|
| `main_rev_b-PTH.drl` | Plated,1,4,PTH | 0.2, 0.3, 0.35, 0.6 | 327 (323 round + **4 G85 slots**) |
| `main_rev_b-NPTH.drl` | NonPlated,1,4,NPTH | 0.65, 4.3 | 6 (4 × M4 mounting) |
| `main_rev_b-front-in1.drl` | Plated,1,2,**Blind** | 0.1 | 14 |
| `main_rev_b-front-in2.drl` | Plated,1,3,**Blind** | 0.1 | 3 |
| `main_rev_b-in1-back.drl` | Plated,2,4,**Blind** | 0.1 | 4 |
| `main_rev_b-in1-in2.drl` | Plated,2,3,**Buried** | 0.1 | 10 |
| `main_rev_b-in2-back.drl` | Plated,3,4,**Blind** | 0.1, 0.3 | 5 |

Diameter census from pcbnew (`boardfacts.json`), independently reproducing the drill files:
`0.100 → 33, 0.200 → 18, 0.300 → 27, 0.350 → 281, 0.600 → 4, 0.650 → 2, 4.300 → 4` = **369**.

Via spans: `F.Cu→B.Cu 305` (through) + `F.Cu→In1 14`, `In1→In2 10`, `F.Cu→In2 3`, `In2→B 5`,
`In1→B 4` = **36 blind/buried, 341 vias**.

The 4 × 0.600 mm PTH "holes" are **routed slots** (`G85`), 0.800–1.100 mm long at y ≈ −71.68 and
−80.32. A naive `^X…Y…$` parser counts 323 and silently loses 4 holes; 369 only reconciles when
slots are counted. Price them as a router step, not as drills.

### The one thing in this section that blocks an order

**36 blind/buried vias, 33 of them 0.100 mm, across 5 layer pairs, on a 1.6 mm 4-layer laminate.**
`AGENT_BOARD.md:448-456` allows only standard plated-through vias at 0.2–0.3 mm, no blind/buried
process. Five drill files in this package can only be built by an HDI shop. The export is *correct*;
the board is the defect. 33 @ 0.1 + 3 @ 0.3 = 36 is consistent with
`evidence/dec-gerber-rev/REPORT.md:238-256`, which also shows 17 of the 36 have no viable process
route at 0.1 mm at all (aspect ratio 10.4:1 and 12.75:1 through a 1.04 mm core).

Copper weight is **1 oz (0.035 mm)** here, so the ESC's 4 oz trace-width rule does **not** apply to
this board — the 0.2 / 0.25 / 0.35 mm tracks are in spec for 1 oz.

---

## 7. Position

| quantity | value |
|---|---|
| board footprints | **165** (all `F.Cu`) |
| `exclude_from_pos_files` | **4** — `H1, H2, H3, H4` (`MountingHole_4.3mm_M4`) |
| expected rows | 165 − 4 = **161** |
| actual data rows | **161** ✅ |
| header | `Ref,Val,Package,PosX,PosY,Rot,Side` (no revision field exists in this format) |
| DNP parts | 0 |

No part is silently missing from an order, and no mounting hole is offered to a pick-and-place
machine. The revision is carried by the filename (`main_rev_b-REV-B-all-pos.csv`), which is what an
assembly house actually keys on.

---

## 8. Job file (`.gbrjob`) — the fields a fab quotes from

```json
"ProjectId": { "Name": "main_rev_b",
               "GUID": "6d61696e-5f72-4657-965f-622e6b696361",
               "Revision": "B" },
"Size": { "X": 140.15, "Y": 100.15 },
"LayerNumber": 4,
"BoardThickness": 1.6,
"Finish": "ENIG",
"ImpedanceControlled": true
```

| field | value | cross-check |
|---|---|---|
| Size | **140.15 × 100.15** | `GetBoardEdgesBoundingBox()` = 140.150 × 100.150 (centreline + 0.15 stroke) ✅ |
| BoardThickness | **1.6** | `main_rev_b.kicad_pcb:6` `(thickness 1.6)`, `GetDesignSettings()` = 1.6 ✅ |
| Finish | **ENIG** | `main_rev_b.kicad_pcb:97` `(copper_finish "ENIG")` ✅ |
| LayerNumber | 4 | `GetCopperLayerCount()` ✅ |
| Revision | **B** | pcbnew `GetRevision()` = `B` ✅ |
| FilesAttributes | 11 | 11 plotted layers ✅ |
| MaterialStackup | 13 entries | F.Cu 0.035 / prepreg 0.2 (εr 4.2, tanδ 0.02) / In1 / core 1.04 / In2 / prepreg 0.2 / B.Cu 0.035, sum 1.6 ✅ |

`ImpedanceControlled: true` is inherited from the board's stackup; that is a **claim**, and the
impedance sign-off is a different item (no measurement exists — `AGENT_BOARD.md:622`).

`ProjectId.GUID` is derived from the **file name**, not the project or the contents. Measured: the
same board exported from the repo and from a same-named copy in another directory produced the same
`6d61696e-5f72-…696361`, and `evidence/dec-gerber-rev/REPORT.md:73-79` shows a *renamed* copy
producing a different GUID. This is why the working copy keeps the repo's basename.

---

## 9. Four independent proofs that the package is this board

1. **Geometry equality across the stamp.** The repo board was plotted unpatched (`_ref_unpatched/`)
   and the stamped copy into `package/`; after removing only `%TF.*` attributes, `G04 #@! TF.*` and
   the `G04 Created by KiCad … date …` comment, **all 11 layers are line-for-line equal**
   (`diff_geometry.json`, `all_geometry_equal: true`). The revision edit moved no copper.
2. **Extents vs pcbnew.** Edge.Cuts 140.150 × 100.150 == `GetBoardEdgesBoundingBox()`; every layer
   inside the outline (§5).
3. **Counts vs pcbnew.** 7 drill diameters / 369 hits == 341 vias + 28 pad holes; 161 `.pos` rows ==
   165 − 4; 4 copper Gerbers == `GetCopperLayerCount()`.
4. **The stamped source is reproducible from a patch.** `title_block_rev_B.patch` applies to a
   pristine copy of the repo board with `git apply --check` exit 0 and reproduces
   `work/main_rev_b.kicad_pcb` **byte-for-byte** (both SHA-256
   `984EA32556DF013C60D22CA7BC47B9A6244F6B1801D75FA6ABE0D6DA1BDCA467`). The 5 added lines are the
   entire design content of this change.

---

## 10. The package being replaced

`repos/drone-arm/hardware/main/pcb-gerbers-1/` — measured read-only (`stale_compare.json`):

| | stale package | this package |
|---|---|---|
| `.gbrjob` Size | **75.05 × 50.05 mm** | 140.15 × 100.15 mm |
| `.gbrjob` Finish | **None** | ENIG |
| `.gbrjob` Revision | `rev?` | **B** |
| Layer extents | **288.397 × 204.238** centreline on **all 11** layers (288.797–290.097 incl. stroke) | ≤ 140.150 × 100.150 |
| byte-identical layers | **0 of 11** | — |
| drill files | 2 (PTH, NPTH) — **no mounting holes**, empty NPTH, no blind/buried | 7, 369 hits incl. 4 × 4.300 mm |
| position file | **absent** | 161 rows |
| tool set | 0.2/0.3/0.4/0.4/0.65/0.8/1.0/1.15 | 0.1/0.2/0.3/0.35/0.6/0.65/4.3 |

Two conclusions, both hard: the stale package is **not this board** (its own `.gbrjob` describes a
75 × 50 mm board with no finish), and its Gerbers carry the A4 worksheet frame baked into every
layer. It also had **no position file at all**, so it could never have supported assembly — the
"rev_a package" was a bare plot, not a fabrication package.

---

## 11. DRC — and a trap worth recording

| run | board | rules | violations | unconnected |
|---|---|---|---:|---:|
| A | repo `main_rev_b.kicad_pcb` (project beside it) | `main_rev_b.kicad_pro` | **0** | **0** |
| B | stamped copy in `work/` (no project file) | KiCad **defaults** | 548 (clearance 499, hole_clearance 31, drill_out_of_range 18) | 0 |

**Run A is the number that counts: 0 violations, 0 unconnected items.** Run B is a methodology trap,
kept as evidence: DRC rules live in `main_rev_b.kicad_pro`, so any board checked away from its
project is judged against default clearances and reports hundreds of phantom errors. Anyone
re-checking this board from a copied file will hit it; the answer is to run DRC on the repo path (or
copy the `.kicad_pro` alongside).

Run B does **not** invalidate the export: the plot is driven by the board's own `(pcbplotparams …)`
and stackup, and §9.1 proves the unpatched (project-context) and stamped (no project) plots are
geometry-identical in all 11 layers.

---

## 12. Is it orderable — and the single human action

**Package: yes.** Every measurable fab-package criterion passes: 4-layer set complete, frame-free,
140 × 100 mm, 1.6 mm, ENIG, 7 tools, 369 holes, 161 placements, 19/19 revision carriers correct,
0 DRC violations, 0 unconnected, 0/11 inherited from the stale package.

**Order: not yet, for one design reason.** 33 × 0.100 mm blind/buried vias (36 blind/buried in
total) require sequential lamination. That is the `da-via-conversion` item; a Gerber export cannot
fix it, and shipping this zip to a standard 4-layer house would produce a quote rejection on the
five `*-in*.drl` files.

**The single human action in this item:**

```powershell
cd E:\engineering-portfolio-audit\repos\drone-arm
git apply --check  E:\engineering-portfolio-audit\evidence\fab-da-gerbers\title_block_rev_B.patch   # exit 0
git apply          E:\engineering-portfolio-audit\evidence\fab-da-gerbers\title_block_rev_B.patch
```

Five added lines under `(paper "A4")`. After that, every future export of this board is born
stamped, and re-running `export_fab_package.ps1` against the repo board directly will reproduce this
package (the script's working-copy step becomes a no-op copy). Until the patch is applied, the
stamped package lives only in this evidence directory — which is exactly the situation `rev?`
caused in the first place, so applying it is not optional bookkeeping.

---

## 13. Corrections to the board and to prior evidence

**BOARD CORRECTION** — `evidence/w2-da-gerbers/REPORT.md:77-80`: "The board itself stores no
`plot_params` block and no `use_drawing_sheet` key." False. `(pcbplotparams …)` is at
`main_rev_b.kicad_pcb:103-141`; `(plotframeref no)` at `:114`. Conclusion unchanged, reason wrong.

**Supersedes** `AGENT_BOARD.md:520` (the `da-gerbers` row): the revision no longer reads `rev?`.
Ready replacement line is in §15.

**Not a correction, a scope note** — `AGENT_BOARD.md:456` says "36 × 0.1 mm HDI vias". The count 36
is right; the diameter split is **33 @ 0.100 + 3 @ 0.300**, as `dec-gerber-rev` already recorded.

---

## 14. UNVERIFIED

1. **No fab house was asked.** Which fields a given CAM front-end ingests is industry practice, not
   a measurement against a named supplier; I did not submit this package for a DFM reply.
2. **The HDI envelope.** That five blind/buried drill files cannot be built on a standard 4-layer
   process is an inference from the hard constraint and from the aspect ratios in
   `dec-gerber-rev/REPORT.md:258-280`; I did not obtain a supplier's capability sheet.
3. **Impedance.** `.gbrjob ImpedanceControlled: true` is a stackup claim. No coupon, no TDR, no
   measurement (unchanged from `AGENT_BOARD.md:622`).
4. **Assembly.** The `.pos` file is geometrically correct (161 rows, mm, both sides) but no part
   rotation, polarity or footprint-vs-BOM check was performed here; that is the `fab-da-connectors`
   / BOM item.
5. **Gerber correctness beyond extents/counts.** I verified extents, primitive counts, tool tables,
   row counts, job fields, revision carriers and cross-export geometry equality. "Does the copper
   match the netlist" is what DRC 0/0 at §11 supports, not a net-by-net CAM comparison.
6. **Zero-context repro.** `export_fab_package.ps1` writes timestamps (see `CreationDate`), so two
   runs produce different bytes in metadata; geometry and every asserted field are stable.

---

## 15. Ready replacement line for AGENT_BOARD.md

```markdown
| da-gerbers | **rev B stamped and frame-free**: 11 Gerbers + `.gbrjob` (Size 140.15×100.15, 1.6 mm, ENIG, Revision **B**, 19/19 carriers read B, 0 read `rev?`), 7 Excellon (369 hits, 7 tools, 4 G85 slots), 161-row `.pos`; Edge_Cuts **140.000×100.000**; 0/11 byte-identical to the stale 75×50 package. DRC 0 violations / 0 unconnected in project context. Artefacts: `evidence/fab-da-gerbers/` (`drone-arm-main-revB-fab.zip`) | **package YES** — one repo action: `git apply title_block_rev_B.patch`; ordering still blocked by the 36 blind/buried vias (33×0.1 mm), which is the via-conversion item |
```

---

## 16. Files in this directory

| file | contents |
|---|---|
| `REPORT.md` | this report |
| `export_fab_package.ps1` | **the reproducible command sequence** (copy → stamp → export → validate → manifest → zip) |
| `boardfacts.py` / `boardfacts.json` | pcbnew ground truth for the stamped board |
| `gerber_measure.py` / `extents.json` | Gerber extents (centreline and incl. stroke) |
| `rev_inventory.py` / `rev_inventory.json` | every revision carrier, drill tables, `.pos`, job fields |
| `diff_geometry.py` / `diff_geometry.json` | unpatched vs stamped, all 11 layers |
| `stale_compare.py` / `stale_compare.json` | stale `pcb-gerbers-1` vs this package |
| `silk_band.py` / `silk_band.json` | proof the REV-B legend is in the plotted silkscreen |
| `drc_repo_board.json` | DRC, project rules: 0 / 0 |
| `drc_workcopy_noproject.json` | DRC, no project file: the 548-error trap |
| `control_extents.json` | `--include-border-title` control plot (287 × 200 mm) |
| `title_block_rev_B.patch` | the 5-line change, applies with `git apply -p1` from the repo root |
| `work/main_rev_b.kicad_pcb` | the stamped copy (never the repo file) |
| `package/` | the 28-file package, zip-ready |
| `drone-arm-main-revB-fab.zip` | same, zipped |
| `PACKAGE-SHA256.txt` | sha256 of all 28 package files |
| `run.log` | every command line and its output, verbatim |
| `_ref_unpatched/`, `_control_frame/` | the two control plots |