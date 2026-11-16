# Code-SDR V2 — ship the fabrication package into its repo

Unit `fab-cs-ship`, wave 8. Board of record
`repos/Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb`, sha256
`309414D2B371C6265629352FC0AA7252AA3E3B630488849187761D24B09FF486` (5,562,840 bytes).
Host KiCad 9.0.7, `kicad-cli` for export, `pcbnew` (CPython 3.11.5 bundled) for board census.

| question | answer |
|---|---|
| repo clean before and after? | **yes** — `git status --porcelain` empty both times |
| did the package copy match the repo board? | **no** — 27 extra footprints, a pour-clearance edit and a refill; §1 |
| re-exported from the repo board? | **yes** — and it reproduces two earlier exports of the same board exactly; §2 |
| validation | **6 / 6 PASS**, every number parsed from the package files; §3 |
| FID1/FID2 pour gap **in the shipped board** | **does not exist — the board carries 0 fiducials**; §4. This is the unit's main finding. |
| committed | **`1a20bd6`**, 22 files, additive only, no existing tracked file touched |
| pushed | **yes** — `origin/work/2026-11-11` = `1a20bd64…`, new branch |
| assembly ready? | **no.** 373 of 373 BOM rows have no purchasable identifier. §6 |

---

## 0. Git state, as recorded before any write

```
$ git -C repos/Code-SDR status
On branch work/2026-11-11
Your branch is up to date with 'origin/info-dump/2026-11-10-handoff'.
nothing to commit, working tree clean

$ git -C repos/Code-SDR log --oneline -5
6fbc004 info-dump: temporary working-tree snapshot 2026-11-10
59ff14f Merge pull request #66 from iamdarshg/em-validation-evidence
43964fe docs: add EM/RF validation proof package (analytical only, fail-closed)
4cdf7e0 add the two missing gates: Verilator lint + RP2040 firmware compile
90cbb70 review+fix pass 2: 8 more issues fixed, P0 cluster deleted, new bugs from review
```

Two gate conditions from the assignment, checked rather than assumed:

1. **Dirty tree from someone else?** No — clean, and it stayed clean until my own write.
2. **Another agent's commits touching fabrication outputs?** **There are none to collide with.**
   `git ls-files | grep -E 'gbr|\.drl|\.pos|gbrjob|fab/'` returns **0 lines**. The repo has never
   held a fabrication output in any branch. Across the **39** commits that ever touched
   `hardware/v2/Code-SDR-V2.kicad_pcb` the authors are `iamdarshg` (38) and `github-actions[bot]` (1);
   none of them touched a fab file, because none existed.

One disclosure: this repo's git identity is configured to `iamdarshg`, so **my commit carries the same
author as the existing history** and authorship does not distinguish it. The commit *message* is the
identifier, and it states exactly what was added and what was not fixed.

`origin/work/2026-11-11` did not exist before this unit, so the push created it rather than moving it.

---

## 1. Why the package and the repo board differed

The orderable package copy is `evidence/fab-cs-close/_work/tp55/Code-SDR-V2.kicad_pcb`, sha256
`8EC5741AB66E8E3EBEDC8460D190FEF6B98467FF2D012B03E4AC03996F1DB7AD`, 5,601,490 bytes.
The repo board is `309414D2…`, 5,562,840 bytes. Difference **+38,650 bytes**, and the cause is not
cosmetic:

| | repo board `309414D2` | package copy `8EC5741A` |
|---|---:|---:|
| footprints | **373** | **400** |
| fiducial footprints | **0** | **9** (FID1/FID2/FID3 + 6 × FIDL_*) |
| test-point footprints | **0** | **18** (TP1…TP18) |
| global fiducial pad local copper clearance | n/a — no fiducial | **1.250 mm** (was 0.750 before the fix) |
| F.Cu zone fill | as committed | **refilled** after the clearance change |
| tracks | 12,253 | 12,253 — identical |
| vias | 1,085 (all through) | 1,085 (all through) — identical |
| zones | 4 | 4 |
| PTH / NPTH hole census | 128 / 2, 2 slots | **identical histogram, hole for hole** |
| outline | 101.600 × 101.600 mm | identical |
| DRC | 222 warn / 0 err | 222 warn / 0 err |

So the copy is the repo board **plus 27 added objects, one clearance property on 3 pads, and a zone
refill**. Naming the change exactly:

1. **+9 fiducial footprints** — 3 global (1.0 mm dot, 2.0 mm mask opening: FID1 @ 94.28, 8.68;
   FID2 @ 6.28, 9.48; FID3 @ 68.98, 86.62) and 6 local (0.5 mm dot, 1.0 mm mask: FIDL_U10_A/B,
   FIDL_U20_A/B, FIDL_U30_A/B).
2. **+18 test-point footprints** — 0.55 mm F.Mask-only apertures, no copper, no net, flagged
   exclude-from-BOM and exclude-from-position.
3. **FID1/FID2/FID3 pad local clearance 0.750 → 1.250 mm** — "the fiducial fix".
4. **The F.Cu pour refill that follows from (3).**

### Does it matter for fabrication?

* **Drill: no.** The hole census is identical in every bin, so the Excellon files are the same
  documents for both boards. This is measured (§1 table) rather than argued.
* **Etch: yes, but either board etches.** The 9 fiducial pads are copper (F.Cu and F.Mask artwork
  differ); the 18 test points are mask apertures (F.Mask differs). Any fab can produce either board
  and both carry the same netlist. They are **not interchangeable as documents**, which is exactly
  why they must not be shipped as if they were the same revision.
* **Assembly: yes, materially.** Fiducials exist only on the copy. A placement house needs them.

**Nothing was shipped from the copy.** The original 1.22-vs-1.25 argument ran for three waves over a
board that, in the repo, has no fiducial to measure at all — see §4.

---

## 2. Re-exported from the repo board

All work was done on a copy under `_work/repo/`, which is a full faithful copy of
`hardware/v2/` — board, `.kicad_pro`, `.kicad_dru`, `.kicad_sch`, `fp-lib-table`,
`sym-lib-table`, `sheets/` and `CodeSDR.pretty/`. A partial copy is a known trap: taking only the
top-level files costs 24 spurious `lib_footprint_issues` because `CodeSDR.pretty/` is a directory.
The work copy hashes to `309414D2…`, i.e. it is the repo file byte-for-byte.

```
kicad-cli pcb export gerbers  --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,\
  F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --precision 6
kicad-cli pcb export drill    --format excellon --excellon-units mm --excellon-separate-th \
  --generate-map --map-format gerberx2 --excellon-oval-format alternate --drill-origin absolute
kicad-cli pcb export pos      --format csv --units mm --side both
kicad-cli sch export bom      --fields Reference,Value,Footprint,Description,${QUANTITY},${DNP}
```

Script: `export.ps1`.

### 2.1 The reproduction control (this is why the files are quotable)

A gerber byte-hash is not a useful comparison: KiCad stamps `%TF.CreationDate` and — gerber X2 —
`%TF.ProjectId`, which embeds the **file name**. So `compare_dirs.py` strips exactly those lines and
compares the rest. Against two independent earlier exports of the same board:

| comparison | result |
|---|---|
| 11 gerbers vs `fab-cs-drc/fabpkg` (21-layer export, 2026-11-15 17:45) | **11 / 11 IDENTICAL** (6 volatile lines dropped from each) |
| 11 gerbers vs `fab-checklist-v3/export_cs` (11-layer export, 2026-11-16 05:09) | **11 / 11 IDENTICAL** |
| 2 drill maps vs `export_cs` | **2 / 2 IDENTICAL** |
| 2 `.drl` vs `export_cs` | differ on **one** line: `TF.CreationDate` |
| `.gbrjob` | differs on **one** line: `CreationDate` |

The export therefore reproduces two known-good artefacts byte-for-byte in content. That is the
gate: an instrument's output is not quotable until it reproduces a checkable known-good case.

**A phantom discrepancy, located.** My F_Cu was 673,412 bytes against `export_cs`'s 673,403 — a
9-byte gap that was constant across every gerber. It is not geometry: the `%TF.ProjectId` line carries
`Code-SDR-V2,436f6465-…` (62 chars) against `cs,63732e6b-…` (53 chars), because `export_cs` was
exported from a copy named `cs.kicad_pcb`. The 9 bytes are the file name. Diffing
`Edge_Cuts.gm1` line by line shows only `CreationDate` and `ProjectId` differ, with the geometry
(4 draws, 4 moves, X0/Y0 → X101.6/Y−101.6) identical.

### 2.2 Revision stamp and frame suppression

* **Revision stamp is derived, not asserted**: `(rev "2.1")` in the board's `title_block`, and
  `GeneralSpecs.ProjectId.Revision = "2.1"` in the `.gbrjob`. Both are the same value (§3.5).
* **Sheet frame suppressed**: `--include-border-title` not passed and `--board-plot-params` not
  passed, so neither the default nor a stored plot setting can plot the frame. Confirmed by
  coordinate extent rather than by trusting the flag (§3.6): the largest coordinate in any gerber is
  **101.600 mm**, which is the board, while the board's own paper is A4 (297 × 210 mm) and a plotted
  frame would reach ~200–287 mm.

---

## 3. Validation against checklist v3

`validate.py`, run with KiCad's python so the board side comes from `pcbnew`. **6 / 6 PASS.** Every
figure below is parsed from the package files; the board-side value is read from the board, never
assumed. Raw output `validate_repo.json`, log `validate.log.txt`.

### 3.1 Layers — `GetCopperLayerCount()`

`board_api_copper_layer_count = 4` (F.Cu, B.Cu, In1.Cu, In2.Cu) vs **4 copper gerbers** in the
package and **11 gerbers total**. PASS.

### 3.2 Edge_Cuts vs board bbox

| | value |
|---|---|
| gerber bbox parsed from `Edge_Cuts.gm1` | **101.600 × 101.600 mm** |
| `GetBoardPolygonOutlines()` bbox | **101.600 × 101.600 mm** |
| delta | **0.000000 mm / 0.000000 mm** |
| topology | 4 draw + 4 move ops — one closed rectangle |
| outline area | 10,322.56 mm² = 103.226 cm² |

Stroke-inclusive (0.100 mm Edge.Cuts stroke) is 101.700 × 101.700 mm — the same basis KiCad uses
for `GeneralSpecs.Size` (§3.5). **Note:** checklist v3 records the stroke as 0.15 mm; measured on
this board it is **0.100 mm**, and 101.6 + 0.1 = 101.7 still lands on the quoted 101.70 figure, so
the conclusion survives but the stated stroke does not. PASS.

### 3.3 Drill tool count and hole census, **G85 slots kept separate**

| file | tool definitions | distinct diameters | drills | **G85 slots** | hits |
|---|---:|---:|---:|---:|---:|
| `Code-SDR-V2-PTH.drl` | 13 | 12 | 1,211 | **2** | 1,213 |
| `Code-SDR-V2-NPTH.drl` | 1 | 1 | 2 | 0 | 2 |
| **total** | **14** | **13** | **1,213** | **2** | **1,215** |

Board side, from `pcbnew`: **1,085 vias + 128 PTH pad holes + 2 NPTH = 1,215**, of which **2 slots**
(the 0.6 × 1.3 mm slot in pad S1 of J202/J203). **The package reconciles to the board exactly**, and
the census is right only because slots are not counted as drills: a validator that adds the `G85`
lines reports 1,215 drills and over-counts by exactly 2.

Two counting traps, both live in this file:

* **14 tools ≠ 13 diameters.** PTH declares `T1C0.200` as `ViaDrill` and `T2C0.200` as
  `ComponentDrill` — same diameter, different aperture function. A distinct-diameter count and a
  tool-definition count legitimately differ; quote which one is meant.
* PTH set: 0.200 ×2 tools · 0.250 · 0.300 · 0.400 · 0.460 · 0.600 · 0.650 · 0.850 · 0.890 · 1.025 ·
  1.300 · 1.570 mm. NPTH: 3.200 mm ×2.

**HDI: 0.** 1,085 of 1,085 vias are `VIATYPE_THROUGH` on F.Cu→B.Cu; **0 blind, 0 buried, 0 microvia**.
No sequential lamination. Also **0 footprints on B.Cu**; all 128 PTH pads span F.Cu and B.Cu, as
through-hole pads must. PASS.

### 3.4 `.pos` rows vs footprints

`373 rows = 373 board footprints`; 0 footprints flagged exclude-from-position; **0 missing, 0 extra**,
compared ref-for-ref in both directions. PASS.

### 3.5 `.gbrjob` fields

| field | package value | board value | |
|---|---|---|---|
| `GeneralSpecs.LayerNumber` | 4 | `GetCopperLayerCount()` = 4 | ✓ |
| `GeneralSpecs.Size.X / Y` | 101.7 / 101.7 | 101.600 + 0.100 stroke | ✓ |
| `GeneralSpecs.BoardThickness` | 1.6 | 0.035×4 + 0.13 + 1.20 + 0.13 = 1.600 | ✓ |
| `GeneralSpecs.Finish` | `ENIG` | `(copper_finish "ENIG")` | ✓ |
| `GeneralSpecs.ProjectId.Revision` | `2.1` | `title_block (rev "2.1")` | ✓ |
| `FilesAttributes` | 11 files | matches the 11 plotted layers | ✓ |

PASS. (A first run of this check compared `Size` against the centreline polygon and FAILED on a
perfectly good package — see §7.3.)

### 3.6 Frame suppression

| | value |
|---|---|
| largest absolute coordinate in any gerber | **101.600 mm** |
| board items bbox (pads, tracks, drawings) | −14.315 … 108.175 mm |
| overshoot beyond the board's own items | **0.0000 mm** |
| board paper | A4 (297 × 210 mm); a plotted frame would reach ~200–287 mm |

Every file's coordinates lie inside the board's own item extent, and the global maximum equals the
board's own dimension. No page furniture is present. PASS.

The up-to-4.26 mm overhang on F.Cu/B.Cu/F.Mask/B.Mask is the five **SMA edge-launch** connectors,
which cross Edge.Cuts deliberately — the reason `Code-SDR-V2.kicad_dru` exists. It is board geometry,
not a frame.

### 3.7 DRC (corroboration, run fresh on the shipped board)

`kicad-cli pcb drc --severity-all`: **222 violations, 0 errors, 0 unconnected**, all 222 at
`warning`:

| type | count |
|---|---:|
| `lib_footprint_mismatch` | 199 |
| `via_dangling` | 13 |
| `track_dangling` | 10 |

This reproduces checklist v3's certified 222 / 0 / 0 on the same sha, which is a second, independent
confirmation that the board being shipped is the board that was certified.

---

## 4. FIDUCIALS — the shipped board has none

**This is the finding of this unit.** The assignment asked to verify that the FID1/FID2 pour gap in
the shipped board is at or above 1.25 mm, with the latest measurement 1.2505 passing by 0.0005.

**The shipped board contains zero fiducials, so there is no such gap and no such margin.**

Evidence, from three independent instruments:

1. **String census with positive controls** (`probe.py`). Counts `FID` in the board text:

   | file | sha256 | `FID` | footprint blocks | refs starting FID / TP |
   |---|---|---:|---:|---|
   | **repo board (shipped)** | `309414D2…` | **0** | 373 | **0 / 0** |
   | control `fid9` | `B1263807…` | 9 | 382 | 9 / 0 |
   | control `tp55` | `8EC5741A…` | 9 | 400 | 9 / 18 |

   The same scanner returns 9 on two known-populated files, so the zero is an absence, not a silent
   miss. (The scanner also returns 8,145 `F.Cu` and 5 `Edge.Cuts` hits on the repo board, so it is
   reading the whole file.)

2. **Object census** (`census.py`, via `pcbnew`): `fiducial_refs = []`, `testpoint_refs = []`,
   373 footprints.

3. **The exact-distance instrument, run on all three boards** (`measure_fid3.py`, shapely polygon
   distance on the F.Cu fill):

   | board | fiducials found | FID1 pour gap | FID2 pour gap | global pad local clearance | K1 control |
   |---|---:|---:|---:|---:|---:|
   | **shipped (repo) board** | **0** | — | — | — | 1.9999238 |
   | `fid9` | 9 | **1.2505** | **1.2505** | 0.750 | 1.9999238 |
   | `tp55` | 9 | **1.7505** | **1.7505** | 1.250 | 1.9999238 |

   This reproduces `fab-cs-close`'s published 1.2505 and 1.7505 exactly, and their difference is
   **+0.5000 mm** — precisely the 0.750 → 1.250 mm clearance change. That arithmetic identity is the
   hand-checkable control that the instrument measures what it claims. K1 (point → 1-degree circle of
   r = 2) returns 1.9999238 against the expected chord value 1.999924.

4. **No committed version ever had one.** All **39** commits that touched
   `hardware/v2/Code-SDR-V2.kicad_pcb` were scanned; **0** contain `FID`. The repo board has never
   carried a fiducial.

### 4.1 What this means for the three waves of argument over 1.22 vs 1.2505

Both numbers are measurements of **evidence copies**, and both are internally sound:
1.2505 on the pre-fix copy (passes a 1.25 mm rule by 0.0005 — a pass with no manufacturing margin),
1.7505 on the widened copy. Neither describes the design of record. **The repo board should not have
been charged either a FAIL or a PASS on a fiducial rule, because it has no fiducial.**

### 4.2 Why the fix was not applied here

Adding the 9 fiducials and widening the keepout is a **board edit** — it changes 27 objects and
requires a zone refill on `hardware/v2/Code-SDR-V2.kicad_pcb`, which is an existing tracked file.
This unit's write scope is additive only ("never modify an existing tracked file"), so it was not
done. It is a small, already-proven change: the same edit on an evidence copy keeps DRC at 222 with
0 new and 0 gone.

**Recommended next action, for a unit with board-write scope:** commit the fiducial + test-point
change to `hardware/v2/Code-SDR-V2.kicad_pcb`, re-export, and this package's README §4 becomes a
pass instead of a gap. Nothing else about the bare board changes.

### 4.3 Fiducials do not affect the bare-board verdict

They are a placement aid, not an etch feature. The 6/6 package validation and the 222-warning DRC
stand, which is why "bare board orderable" is still true and "assembly ready" is still false.

---

## 5. Commit and push

```
1a20bd6  fab: add Code-SDR V2 rev 2.1 bare-board package exported from this board
         22 files changed, 176638 insertions(+)

$ git push origin work/2026-11-11:work/2026-11-11
 * [new branch]  work/2026-11-11 -> work/2026-11-11

$ git ls-remote --heads origin 'work/*'
1a20bd64ae245b32933658c40214b0a53577d5bb  refs/heads/work/2026-11-11
```

Local `HEAD` = remote = **`1a20bd64ae245b32933658c40214b0a53577d5bb`**. No force-push, no reset, no
amend; the branch was created on the remote by this push.

**Additive proof.** `git diff --cached --name-status` showed **22 × `A`** and nothing else; the
pre-existing tree was `?? hardware/v2/fab/` alone. No tracked file was modified or deleted.

**What landed** (`hardware/v2/fab/`):

```
.gitattributes  MANIFEST.sha256  README.md
gerbers/   11 layers + Code-SDR-V2-job.gbrjob
drill/     PTH.drl NPTH.drl PTH-drl_map.gbr NPTH-drl_map.gbr
assembly/  Code-SDR-V2-pos.csv  BOM-flat.csv (373 rows)  BOM-grouped.csv
```

### 5.1 A false-verification trap caught before it shipped

`core.autocrlf=true` in this repo. Before `.gitattributes` existed, git's own warnings showed that
**README.md and both BOM CSVs would be stored as LF and checked out as CRLF**, silently breaking 3 of
the 20 `MANIFEST.sha256` entries for anyone who verified after a clone — a manifest that passes here
and fails there. KiCad writes the gerbers, drills, pos and job with CRLF.

`hardware/v2/fab/.gitattributes` now pins it: `Code-SDR-V2-* -text` (payload stored and checked out
verbatim) and `README.md` / `MANIFEST.sha256` `text eol=lf`.

Verified the way a verifier would: every one of the **20** manifest entries was extracted from the
**committed blobs** (`git cat-file blob HEAD:…`) and re-hashed — **0 mismatches** — and the
post-commit working tree also matches, **0 mismatches**.

---

## 6. What still blocks assembly

**This unit does not make Code-SDR assembly-ready.** It closes the bare-board last mile only.

| # | blocker | size | tier |
|---|---|---|---|
| 1 | **No purchasable identifier on any BOM row.** No `MPN`, `Manufacturer`, `Supplier` or `SupplierPart` property exists in any of the nine schematic files, so `kicad-cli sch export bom` cannot emit one. **373 / 373 rows.** Three rows (C11, C12, C346 in `01_power`) state a required part number in free-text `Description` — Murata GRM31CR71A226KE15L / GRM32ER71A476KE15L — and no BOM tool reads that column. The 3 further "MPN" hits in `07_rf_high` are the phrase *"manufacturer-characterized"*, not part numbers. | **373 rows** | measured |
| 2 | **No fiducials on the board** (§4) | 9 objects | measured |
| 3 | **No assembly drawing** | 1 document | missing |
| 4 | **No test points.** The 18 sites proven in evidence are 0.45 mm probe lands; 9 of 18 cannot take a 1.0 mm ATE land without a copper change. | 18 sites | measured |

Blockers 2–4 are cheap. **Blocker 1 is the gap and it is sourcing, not engineering**: earlier
row-level classification put it at 58 rows inferable with no decision, 32 requiring an engineer and
283 a purchasing choice.

One cost note, not a defect: the board is 101.6 mm, **1.7 mm over the 100 mm price tier**.

---

## 7. Instrument notes — what my own tools got wrong first

Recorded because the standing rule is that no instrument's output is quotable until it reproduces a
known-good case, and these are the cases where it did not.

### 7.1 Two of six checks failed on my bugs, not on the package

The first validation run returned 4/6. Both failures were mine:

* **C5 `.gbrjob` size.** I compared `GeneralSpecs.Size` (101.7) against the *centreline* polygon
  (101.6) and failed a good package. KiCad's `Size` is **outline + Edge.Cuts stroke**. Fixed by
  comparing on the stroke-inclusive basis, and the stroke is now read from the board rather than
  assumed.
* **C6 "frame".** I tested "no coordinate outside the board bbox" and failed — because gerber Y is
  plotted negated, and because the SMA edge-launch pads legitimately overhang Edge.Cuts. Fixed by
  negating Y and comparing against the **board's own item extent** instead of a hand-picked margin,
  so the test has no tunable threshold.

**No threshold was moved and no package file was changed to turn either one green.**

### 7.2 PowerShell silently rounded my numbers

`Format-Table` on the parsed stackup printed copper thickness as **`0.04`**; the file says
**`0.035`**. A table-format rounding artefact that would have mis-filed 1 oz copper as something
else. All figures in this report were re-read from the raw JSON. This is the same class as the
ASCII-minus probe: read the value, not the rendering.

### 7.3 Corrections to facts in circulation

* **"43 THT pads legitimately span both layers"** — measured on this board: **128 of 128** PTH pads
  span F.Cu and B.Cu. That figure does not belong to Code-SDR V2.
* **checklist v3 states the Edge.Cuts stroke as 0.15 mm**; measured here it is **0.100 mm**. The
  101.70 mm outcome is unaffected (101.6 + 0.1), so the row's conclusion stands on a wrong input.
* **The 9-byte gerber delta between the two existing exports** is the `%TF.ProjectId` file name, not
  geometry (§2.1).
* **"the repo carries 0 package files"** was true and is now false: `hardware/v2/fab/` holds 22.

### 7.4 Limits, stated

* Gerber reproduction is **content-identical after stripping `CreationDate` and `ProjectId`**, not
  byte-identical — KiCad embeds a timestamp, so byte equality is not achievable and is not claimed.
* The fiducial rule 1.25 mm is this programme's design rule, derived from mask-opening geometry, not
  a cited fabricator spec; no fabricator's written fiducial clear-area document was obtained.
* Whether the fab prices the 101.6 mm board at the 100 mm tier was not quoted.
* The `.pos` was exported `--side both` with no bottom footprints present, so the file is
  front-side-only in content.
* DRC was run with the project's own `.kicad_dru` present; the 247-without control is quoted from
  `fab-cs-close`, not re-run here.

---

## 8. Artefacts

| path | what |
|---|---|
| `package/` | the shipped package, byte-for-byte what `hardware/v2/fab/` holds (plus `.gitattributes`) |
| `census.py`, `census_repo.json`, `census_tp55.json` | board census: layers, stackup, outline, holes, fiducials, test points |
| `probe.py`, `probe.log.txt` | string census with positive controls |
| `measure` outputs `fid_shipped.json`, `fid_fid9_control.json`, `fid_tp55_control.json` | exact fiducial gaps on 3 boards + K1/K2 controls |
| `export.ps1`, `export.log.txt` | the export commands and their output |
| `compare_dirs.py`, `cmp_vs_fabpkg.json`, `cmp_vs_exportcs.json`, `cmp_drill.json` | reproduction against two known-good exports |
| `geom_hash.py` | volatile-line-stripping content hash |
| `validate.py`, `validate_repo.json`, `validate.log.txt` | the 6 checks |
| `drc_shipped.json` | fresh DRC on the shipped board: 222 / 0 / 0 |
| `commit-msg.txt` | the commit message |
| `_work/repo/` | the faithful board copy everything was done on |
| `_work/blobcheck/` | blobs extracted from the commit for manifest verification |
| `REPORT.md` | this file |

**Nothing in this unit wrote outside `evidence/fab-cs-ship/` and the new
`repos/Code-SDR/hardware/v2/fab/` directory.** The repo was clean before the write, and
`git status --porcelain` was empty after the commit.