# drone-arm · regenerate & validate a real rev_b fab package

**Item:** produce a genuine `rev_b` fabrication package and prove it matches the board,
replacing the stale `rev_a` one.
**Board under test:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`
(2,252,603 bytes, SHA-256 `9B3BBA85C01AAC9E8365AF999F5231C3951E3428C37544A2B2CADC425F89953C`,
branch `work/2026-11-11`, last modified 2026-11-11 22:57:07).
**Tool:** KiCad 9.0.7 (`kicad-cli` 9.0.7, `python.exe` with `pcbnew`).
**Nothing was written into the repository.** The board was opened read-only; all output
went to this evidence directory.
**No fabrication was performed.**

Reproduction script: [`export_rev_b_fab.ps1`](./export_rev_b_fab.ps1)
(machine-readable results: `boardfacts.json`, `new_extents.json`, `stale_extents.json`,
`diff.json`, `pos_gap.json`).

---

## 1. Verdict

The regenerated package is real, self-consistent, and describes the board it came from.
The stale package in the repo is **not merely stale — it is a different board**, and its
own two halves (Gerbers vs `.gbrjob`) disagree with each other as well as with
`main_rev_b.kicad_pcb`. Every check below triangulates to the same conclusion.

| Check | Required | Result |
|---|---|---|
| Gerber layer count vs `GetCopperLayerCount` | 4 copper / 11 files | **4 copper, 11 Gerbers, 11 gbrjob entries** ✅ |
| Edge.Cuts extent vs board edge bbox | equal (mod. stroke) | **140.000×100.000 vs 140.150×100.150, Δ = 0.150 = line width** ✅ |
| Worksheet frame suppressed | none in any layer | **all 11 layers ≤140×100; Edge.Cuts = 4 primitives** ✅ |
| Drill tool count | matches board | **7 diameters, 369 hits — exactly pcbnew's 369** ✅ |
| `.pos` rows vs footprints | 165 − 4 excluded = 161 | **161 rows** ✅ |
| gbrjob Size / Thickness / Finish | 140.15×100.15 / 1.6 / ENIG | **140.15×100.15 / 1.6 / ENIG** ✅ |
| Byte-identical to stale | 0 | **0 / 11** (reproduces wave‑1) ✅ |

**One new constraint the fab package exposes:** the board carries **36 blind/buried
(HDI) vias across 5 layer pairs with 0.1 mm drills**. This is not a defect in the export —
it is a genuine, previously unrecorded manufacturability requirement (§6).

---

## 2. Board facts (authoritative, from `pcbnew`)

Extracted by `boardfacts.py` → `boardfacts.json`. Probe: `GetCopperLayerCount`,
`GetBoardEdgesBoundingBox`, `GetFootprints`, `GetPads`, `GetTracks`.

| Fact | Value | Source |
|---|---|---|
| Copper layer count | **4** (`F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`) | `GetCopperLayerCount()` |
| Enabled layers | 26 (11 plotted) | `IsLayerEnabled()` |
| Board edge bbox | `x −0.075…140.075`, `y −0.075…100.075` = **140.150 × 100.150 mm** | `GetBoardEdgesBoundingBox()` |
| Edge.Cuts geometry | **4 straight segments** (0 arcs/circles/polys) = rectangle | `GetDrawings()` |
| Board thickness | **1.6 mm** | `GetDesignSettings().GetBoardThickness()` |
| Copper finish | **ENIG** | [main_rev_b.kicad_pcb:97](E:/engineering-portfolio-audit/repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb#L97) `(copper_finish "ENIG")` |
| Footprints | **165**, all 165 on `F.Cu`, 0 on `B.Cu` | `GetFootprints()` |
| Pads | 22 PTH, 6 NPTH | `GetPads()` |
| Vias | 305 through + 36 blind/buried = **341** | `via_audit.py` |
| Nets | 176 | `GetNetCount()` |
| Title block | title/revision/date/company **all empty** | `GetTitleBlock()` |

The board outline is exactly 140 × 100 mm centreline; the extra 0.150 mm in the bbox is the
0.15 mm Edge.Cuts stroke (half-width 0.075 on each side), which is why
`−0.075` and `140.075` appear rather than `0` and `140`.

---

## 3. Export (what was produced)

```powershell
kicad-cli pcb export gerbers --output <ev>\new --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --precision 6 main_rev_b.kicad_pcb
kicad-cli pcb export drill   --output <ev>\gerbers --format excellon --drill-origin absolute --excellon-units mm --excellon-zeros-format decimal --excellon-separate-th --generate-map --map-format gerberx2 main_rev_b.kicad_pcb
kicad-cli pcb export pos     --output <ev>\gerbers\main_rev_b-all-pos.csv --side both --format csv --units mm main_rev_b.kicad_pcb
```

**Sheet-frame suppression:** `kicad-cli pcb export gerbers` plots the drawing sheet **only**
when `--include-border-title` is passed (confirmed in `--help`: *"Include the border and
title block"*). The board itself stores **no** `plot_params` block and no
`use_drawing_sheet` key, so there was no stored setting to override — the CLI default is
already frame-free. This is precisely why the stale package (plotted from the GUI, where
"Plot drawing sheet" was checked) carries a frame while this export does not.

### 3.1 Layers exported — 11

| # | Layer | File | Bytes | Function |
|---|---|---|---|---|
| 1 | F.Cu | `main_rev_b-F_Cu.gtl` | 519,530 | Copper,L1,Top |
| 2 | In1.Cu | `main_rev_b-In1_Cu.g1` | 624,785 | Copper,L2,Inr |
| 3 | In2.Cu | `main_rev_b-In2_Cu.g2` | 58,881 | Copper,L3,Inr |
| 4 | B.Cu | `main_rev_b-B_Cu.gbl` | 205,104 | Copper,L4,Bot |
| 5 | F.Paste | `main_rev_b-F_Paste.gtp` | 27,502 | SolderPaste,Top |
| 6 | B.Paste | `main_rev_b-B_Paste.gbp` | 468 | SolderPaste,Bot |
| 7 | F.Silkscreen | `main_rev_b-F_Silkscreen.gto` | 28,286 | Legend,Top |
| 8 | B.Silkscreen | `main_rev_b-B_Silkscreen.gbo` | 469 | Legend,Bot |
| 9 | F.Mask | `main_rev_b-F_Mask.gts` | 27,239 | SolderMask,Top (Negative) |
| 10 | B.Mask | `main_rev_b-B_Mask.gbs` | 950 | SolderMask,Bot (Negative) |
| 11 | Edge.Cuts | `main_rev_b-Edge_Cuts.gm1` | 649 | Profile,NP |

`GetCopperLayerCount()` = **4**; copper Gerbers emitted = **4**; `gbrjob` `LayerNumber` = **4**;
`FilesAttributes` entries = **11**. All agree.

Extensions are KiCad's Protel set (`.gtl/.g1/.g2/.gbl/…`) because `kicad-cli` defaults to
Protel naming; the stale package used plain `.gbr`. Both are conventional and the
`.gbrjob` maps every file explicitly, so this is cosmetic — but pass `--no-protel-ext` if a
cam tool insists on `.gbr`.

### 3.2 Per-layer extents (all inside the board outline)

Measured from raw Gerber coordinates by `gerber_measure.py` (FSLAX46Y46 → mm).

| Layer | width × height (mm) | D01 draws | D03 flashes |
|---|---|---|---|
| F.Cu | 138.999 × 98.999 | 16,837 | 941 |
| In1.Cu | 138.999 × 98.999 | 23,273 | 358 |
| In2.Cu | 135.700 × 94.000 | 1,431 | 349 |
| B.Cu | 138.200 × 98.000 | 7,408 | 338 |
| F.Paste | 134.155 × 82.200 | 0 | 627 |
| B.Paste | — **empty** | 0 | 0 |
| F.Silkscreen | 102.705 × 97.077 | 562 | 0 |
| B.Silkscreen | — **empty** | 0 | 0 |
| F.Mask | 135.255 × 92.000 | 8 | 607 |
| B.Mask | 133.105 × 92.000 | 0 | 10 |
| **Edge.Cuts** | **140.000 × 100.000** | **4** | 0 |

Copper sits 0.5 mm inside the edge (138.999 vs 140), which is normal pull-back and the
reason no layer exceeds the outline. `B.Paste` and `B.Silkscreen` are legitimately empty —
all 165 footprints are on the front, so there is nothing to place or mark on the back.
`B.Mask` has 10 flashes (10 back-side mask openings) but no drawn geometry.

### 3.3 Edge.Cuts — the whole file

`main_rev_b-Edge_Cuts.gm1` contains one aperture and four draws; this *is* the frame
suppression, in full:

```
%TA.AperFunction,Profile*%
%ADD10C,0.150000*%
D10*
X140000000Y-100000000D02*   X0Y-100000000D01*
X0Y-100000000D02*           X0Y0D01*
X0Y0D02*                    X140000000Y0D01*
X140000000Y0D02*            X140000000Y-100000000D01*
```

Extent **140.000 × 100.000 mm**, 4 primitives, 1 aperture.
Versus `GetBoardEdgesBoundingBox()` **140.150 × 100.150 mm** → **Δ = 0.150 mm**, exactly the
`ADD10C,0.150000` stroke width. The Gerber stores centreline coordinates; the pcbnew bbox
adds half the stroke on each side. **They agree.** No second rectangle, no title block, no
A4 page anywhere in the file.

---

## 4. Drill files

`--excellon-separate-th` splits plated from non-plated; the blind/buried vias additionally
produce one file per drilled layer pair.

| File | FileFunction | Tools | Hits | Diameters (mm) |
|---|---|---|---|---|
| `main_rev_b-PTH.drl` | Plated,1,4,PTH | 4 | 327 | 0.200, 0.300, 0.350, 0.600 |
| `main_rev_b-NPTH.drl` | NonPlated,1,4,NPTH | 2 | 6 | 0.650, 4.300 |
| `main_rev_b-front-in1.drl` | Plated,1,2,**Blind** | 1 | 14 | 0.100 |
| `main_rev_b-front-in2.drl` | Plated,1,3,**Blind** | 1 | 3 | 0.100 |
| `main_rev_b-in1-in2.drl` | Plated,2,3,**Buried** | 1 | 10 | 0.100 |
| `main_rev_b-in1-back.drl` | Plated,2,4,**Blind** | 1 | 4 | 0.100 |
| `main_rev_b-in2-back.drl` | Plated,3,4,**Blind** | 2 | 5 | 0.100, 0.300 |

**Distinct drill diameters: 7** — `0.100, 0.200, 0.300, 0.350, 0.600, 0.650, 4.300`.
**Total hits: 369.**

Cross-check against `boardfacts.json` — independent paths, exact agreement:

| Diameter | pcbnew count | Drill-file hits |
|---|---|---|
| 0.100 | 33 | 33 (14+3+10+4+2) |
| 0.200 | 18 | 18 |
| 0.300 | 27 | 27 (24 PTH + 3 in in2-back) |
| 0.350 | 281 | 281 |
| 0.600 | 4 | 4 (**routed slots**, `G85` — see note) |
| 0.650 | 2 | 2 |
| 4.300 | 4 | 4 |
| **Σ** | **369** | **369** ✅ |

Reconciliation from the board side: **341 vias** (305 through + 36 blind/buried, drills
0.1/0.3/0.35) plus **28 pad holes** (22 PTH + 6 NPTH) = **369 holes**, matching the 369
drill hits exactly.

The 4.300 mm NPTH hits are the four M4 mounting holes (`H1`–`H4`,
`MountingHole_4.3mm_M4`). The 0.650 mm NPTH hits are 2 non-plated component holes.

**Note — 4 of the 0.6 mm PTH holes are slots, not round holes.** Tool `T4` contains four
`G85` routed slots rather than drill hits:

```
T4
X2.345Y-71.68G85X3.445Y-71.68      (1.100 mm slot)
X2.345Y-80.32G85X3.445Y-80.32      (1.100 mm slot)
X6.675Y-71.68G85X7.475Y-71.68      (0.800 mm slot)
X6.675Y-80.32G85X7.475Y-80.32      (0.800 mm slot)
```

So the PTH file is 323 round hits + 4 slots = 327 entries in tool `T4`-inclusive terms.
Slots require a router step, not just drilling, and some cheap fab quotes price them
separately — worth carrying into the quote comparison. (A naive `^X…Y…$` parser counts 323
and silently loses 4 holes; the 369 total only reconciles if slots are counted.)

---

## 5. Position file

`main_rev_b-all-pos.csv` (CSV, mm, both sides): header + **161 data rows**, all `top`.

| Quantity | Value |
|---|---|
| Board footprints | 165 |
| `exclude_from_pos_files` footprints | 4 |
| Expected rows | 165 − 4 = **161** |
| Actual rows | **161** ✅ CONSISTENT |

The 4 exclusions are the four mounting holes — `H1`, `H2`, `H3`, `H4`
(`MountingHole_4.3mm_M4`), each flagged `(attr exclude_from_pos_files exclude_from_bom)`
at board lines 1671, 10891, 13141, 26277 and confirmed via
`IsExcludedFromPosFiles()` in `pos_gap.json`. They are correctly absent from the placement
file *and* from the BOM; no part is silently missing from an order.
`pos_refs_not_on_board` = `[]`, `dnp_count` = 0, `zero_pad_footprints` = `[]`.

---

## 6. NEW constraint surfaced: 36 HDI blind/buried vias

KiCad emitted five layer-pair drill files, which it only does when vias actually span those
pairs. Confirmed independently by grepping via layer pairs in the board:

| Via span | Count | Drill diameter |
|---|---|---|
| `F.Cu ↔ B.Cu` (through) | 305 | 0.300 / 0.350 |
| `F.Cu ↔ In1.Cu` (blind) | 14 | 0.100 |
| `In1.Cu ↔ In2.Cu` (buried) | 10 | 0.100 |
| `In2.Cu ↔ B.Cu` (blind) | 5 | 0.100 / 0.300 |
| `In1.Cu ↔ B.Cu` (blind) | 4 | 0.100 |
| `F.Cu ↔ In2.Cu` (blind) | 3 | 0.100 |
| **blind/buried total** | **36** | mostly 0.100 |

A 1.6 mm 4-layer board needing 0.1 mm-diameter blind and buried vias is an **HDI
(build-up) stackup**, not a conventional laminate. This is a real order constraint that
neither wave‑1 nor the stale package discloses — the stale package emitted *no* blind/buried
files at all. **Action for the fab-quote step: confirm a supplier that does sequential
lamination with 0.1 mm buried microvias, or convert these 36 vias to through vias and pay
the routing-density cost.** I flag this as a finding, not a defect: the geometry exports
correctly either way.

---

## 7. gbrjob

`new/main_rev_b-job.gbrjob`, 4,107 bytes, `FilesAttributes` = 11:

```
Size            : 140.15 × 100.15 mm
LayerNumber     : 4
BoardThickness  : 1.6 mm
Finish          : ENIG
ImpedanceControlled : true
ProjectId       : main_rev_b / revision "rev?"
GenerationSoftware : KiCad Pcbnew 9.0.7
CreationDate    : 2026-11-14T18:42:14+05:30
```

* **Size 140.15 × 100.15** is the board-edge bbox including the 0.15 mm stroke — it matches
  `GetBoardEdgesBoundingBox()` to the digit.
* **BoardThickness 1.6** matches `(thickness 1.6)` and `GetDesignSettings()`.
* **Finish ENIG** matches `(copper_finish "ENIG")` at line 97.
* **ImpedanceControlled: true** — the stackup declares εr 4.5 / tanδ 0.02 FR4, consistent
  with the wave‑1 impedance work (2D FD solve gave 52.6 Ω over solid In1/3V3).

⚠ **`Revision` is `"rev?"`, not `"B"`.** The board's title block is completely empty
(`GetTitle()`, `GetRevision()`, `GetDate()`, `GetCompany()` all `""`). Nothing inside the
package identifies it as rev_b except the filename. **Recommendation: set
`(title_block (rev "B"))` so the fabrication data carries its own revision** — otherwise a
fab house holding both rev_a and rev_b files has no in-file discriminator, which is exactly
the failure mode that produced the stale package.

---

## 8. Stale vs new — what actually differs

Byte comparison: **0 of 11 layers identical** (`diff.json`). This independently reproduces
wave‑1's "0/11 byte-identical" claim (cited, not re-derived as my own).

### 8.1 The stale package's own two halves disagree with each other

| | stale gbrjob | stale Gerbers | current board |
|---|---|---|---|
| Board size | **75.05 × 50.05** | A4 page 288.397 × 204.238 | **140.15 × 100.15** |
| Finish | **None** | — | **ENIG** |
| LayerNumber | 4 | 4 | 4 |
| Thickness | 1.6 | 1.6 | 1.6 |

Three-way disagreement. The gbrjob is generated by the same KiCad call that writes the
Gerbers, so these cannot both describe `main_rev_b.kicad_pcb`.

### 8.2 Proof: the stale package is a 75 × 50 mm board

In `pcb-gerbers-1/main-Edge_Cuts.gbr`, aperture **`D14` = `C,0.050000`** has bbox
**exactly 75.000 × 50.000 mm with 5 primitives** — that is the real board outline of the
stale export: a 75 × 50 mm rectangle drawn with a 0.05 mm stroke. Its bbox including stroke
is 75.05 × 50.05, which is *precisely* the stale gbrjob's declared `Size`. The arithmetic
closes exactly.

The 288.397 × 204.238 extent belongs to a different aperture: **`D11` = `C,0.150000`,
11,305 primitives**, bbox 288.397 × 204.238 — the A4 drawing-sheet frame plus title block.
That single aperture is what inflated every one of the 11 layers.

A third aperture, `D16` = `C,0.040000` (3,614 prims, 67.386 × 48.182), and `D22`/`D23`
etc. are worksheet text and frame details, not board geometry.

### 8.3 The ~9,004-primitive worksheet tax, per layer

| Layer | stale D01/D02/D03/AP | new D01/D02/D03/AP | Interpretation |
|---|---|---|---|
| Edge.Cuts | 9008 / 8743 / 0 / 14 | **4 / 4 / 0 / 1** | 9,004 phantom draws = worksheet; real board = 4 |
| B.Paste | 9015 / 8753 / 0 / 13 | **0 / 0 / 0 / 0** | looked populated; genuinely empty |
| B.Silkscreen | 9059 / 8797 / 71 / 20 | **0 / 0 / 0 / 0** | looked populated; genuinely empty |
| B.Mask | 9019 / 8757 / 71 / 20 | **0 / 0 / 10 / 4** | 10 real openings only |
| F.Mask | 9015 / 8753 / 545 / 68 | **8 / 2 / 607 / 64** | 9,007 phantom draws |
| F.Paste | 9009 / 8747 / 482 / 61 | **0 / 0 / 627 / 62** | 9,009 phantom draws |
| F.Silkscreen | 12446 / 12196 / 545 / 71 | **562 / 562 / 0 / 1** | 11,884 phantom draws |
| In2.Cu | 21491 / 9176 / 368 / 25 | **1431 / 412 / 349 / 9** | 20,060 phantom draws |
| In1.Cu | 16529 / 9293 / 368 / 25 | **23273 / 548 / 358 / 8** | differs both ways (different design) |
| B.Cu | 9703 / 9441 / 368 / 26 | **7408 / 308 / 338 / 10** | different design |
| F.Cu | 10991 / 10199 / 843 / 81 | **16837 / 1211 / 941 / 70** | different design |

The constant ≈9,004 offset is the worksheet. Where the counts *cannot* be reconciled by
subtracting it (`In1.Cu`, `B.Cu`, `F.Cu` differ in both directions), the underlying designs
genuinely differ — consistent with §8.2: the stale data is a different, smaller board, not
an older export of this one. The new board has more copper draw commands because it has
~3.7× the area (14,000 mm² vs 3,750 mm²).

### 8.4 Drill differences

| | stale | new |
|---|---|---|
| PTH tools | **8** (0.2, 0.3, 0.4, 0.4, 0.65, 0.8, 1.0, 1.15) | **4** (0.2, 0.3, 0.35, 0.6) |
| PTH hits | — | 327 |
| NPTH file | **present but empty** (0 hits) | **6 hits** incl. 4 × 4.300 M4 |
| Blind/buried files | **none** | **5** (36 hits, 0.1 mm) |
| Distinct diameters | 8 | 7 (incl. 0.100 and 4.300) |

The stale package drills **no mounting holes** (empty NPTH) and has **no 4.3 mm tool** — it
could not have produced a buildable board for the current mechanical interface. Its tool
set (0.8/1.0/1.15) does not intersect the current board's (0.1/0.35/4.3) at all.

---

## 9. Caveats / UNVERIFIED

* **Fabrication not performed** — this is a data package, not a physical board. Whether a
  given house accepts the HDI blind/buried vias is **UNVERIFIED** (§6).
* **Gerber correctness beyond extents/counts** is not proven here. I validated geometry
  extents, primitive counts, tool tables, row counts and gbrjob fields. A full DRC /
  "does the copper match the netlist" check is a separate item; the parity audit
  (wave‑1: 0 match / 20 mismatch / 6 unrouted, J60–J65 absent, U10 pads 43–48 unconnected,
  CAN H/L swapped on FL50) is **not** fixed by a correct export — those are design errors
  that will now be faithfully reproduced in copper.
* **Revision string `rev?`** — the package does not self-identify as rev_b (§7).
* The `Color theme 'user' not found` warning from `kicad-cli` is cosmetic (an unset UI
  theme); it does not affect plotted geometry.
* Layer extents outside Edge.Cuts are *not* independently proof of "no frame" — the proof
  is the 4-primitive, single-aperture Edge.Cuts file and the absence of any ~288 mm extent
  in all 11 layers.

---

## 10. Files in this evidence directory

| File | Contents |
|---|---|
| `export_rev_b_fab.ps1` | **The reproducible command sequence** (export + validate) |
| `boardfacts.py` / `boardfacts.json` | pcbnew-side ground truth |
| `gerber_measure.py` | Gerber X2 extents/primitive parser |
| `new_extents.json` | measured extents of the fresh package |
| `stale_extents.json` | measured extents of `pcb-gerbers-1` |
| `diff_stale_new.py` / `diff.json` | per-layer SHA-256 + structural diff |
| `pos_gap.py` / `pos_gap.json` | 165-vs-161 footprint attribution |
| `via_audit.py` | authoritative via layer-pair + drill-diameter census |
| `tool_hits.py` | per-tool drill hit counts |
| `cmp_runs.py` | structural equality check between two independent export runs |
| `probe_edge.py` | stale Edge.Cuts coordinate clustering probe |
| `new/` | 11 Gerbers + `.gbrjob` |
| `gerbers/` | PTH/NPTH/blind-buried Excellon + drill maps + `.pos.csv` |
