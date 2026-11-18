# dev-board: assessed → ORDERABLE

**Task:** close the four named defects on `dev-board`, regenerate the package, prove each fix.
**Input (read-only):** `C:/Users/Darsh Gupta/engineering-portfolio-audit/repos/dev-board`
**Working copies:** `D:/ep-audit-evidence/dvb-to-orderable/work/` (never the repo; nothing in the repo was written)
**Deliverable package:** `D:/ep-audit-evidence/dvb-to-orderable/package/final/`
**Host:** KiCad 9.0.7 — `kicad-cli.exe` for DRC/plot/drill/pos, KiCad's bundled `python.exe` for pcbnew.
**Run date:** 2026-11-18 · **Status: COMPLETE**

---

## 0. Baseline and provenance

| Item | Value |
| --- | --- |
| Board under test | `dev-real-production.kicad_pcb`, 320 footprints, 5,412,875 bytes, last modified 2026-11-02 |
| Board dims / stack | 105.05 × 105.05 mm, 4 copper layers (F.Cu / In1 GND / In2 PWR / B.Cu), 1.6 mm |
| Vias (text census) | 1941 total = 1740 through + 186 micro + 1 blind + 14 buried → 201 non-through |
| DRC companions | `dev-real-production.kicad_pro`, `fp-lib-table`, `sym-lib-table`, 26 `*.pretty` dirs **plus the four non-`.pretty` footprint dirs** (`MM8108-MF15457`, `THS8136IPHPR`, `ENS161-BLGT_LGA9_T&R_1k5`, `ICM-42670-P`) |
| Free space at start | C 19.64 / D 140.66 / E 10.86 GB; all intermediates kept on D: |
| Reference state (carried from the earlier audit) | 10 DRC violations, all warnings, 0 errors, 0 unconnected; 8 of them real |

**Re-measured baseline, not taken on trust** — `kicad-cli pcb drc --severity-all --units mm` inside a
directory carrying every companion (`drc/before.json`):

```
10 violations : 5 copper_sliver, 2 holes_co_located, 2 lib_footprint_mismatch, 1 track_dangling
 0 errors     : 0 unconnected_items
```

Reproducing the isolation trap deliberately, then fixing it: with only the `*.pretty` directories copied and
the four plain footprint dirs left out, the same board reported **14** violations (4 extra
`lib_footprint_issues`). With the *full* companion set it is **10**. All numbers below are the 10-baseline.

Two supporting instruments were built because `kicad-cli` does not report them:

1. **Via / span census** by text-parsing the `.kicad_pcb` (`work/via_census.py`) — never `PCB_VIA.GetWidth()`,
   which hangs forever (it hung this run once, see §6).
2. **Sliver locator** (`work/sliver_scan.py`) — a re-implementation of
   `DRC_TEST_PROVIDER_SLIVER_CHECKER` from the KiCad 9.0 source, because `copper_sliver` violations carry
   **zero** items and no position in either the JSON or the text report. Constants are the headless
   `ADVANCED_CFG` defaults taken from `common/advanced_config.cpp` (width tolerance 0.08 mm, angle tolerance
   20°, minimum length 0.0008 mm). It reproduces the DRC verdict exactly: **5 slivers, 2 Top / 2 Bottom /
   1 Power Layer 2** (`work/slivers.json`). Same count *and* same layer split as the real checker — that
   agreement is what licenses quoting coordinates from it.

---

## 1. Defect 1 — SurfaceFinish empty in both .gbrjob

**What was there.** Both job files carried `GeneralSpecs.Finish = "Lead-Free"` (plain lead-free HASL) and **no
`SurfaceFinish` key at all**. For a board with 0.100 mm microvias and 0.400 mm-pitch lands that is both the
wrong process and an unusable field.

**Does `kicad-cli` support setting it?** Half. Two experiments settle it:

* No `SurfaceFinish` string exists anywhere in `_pcbnew.dll` (the library that writes the job file), while
  `BoardThickness`, `GeneralSpecs` and `ImpedanceControlled` all do — so KiCad 9.0.7 **cannot** emit that key.
* The finish *is* design data and is stored in the board stackup: `(copper_finish "Lead-Free")`. Changing it
  in the board and re-exporting produced `GeneralSpecs.Finish = "ENIG"` — so the finish value **is** settable
  through kicad-cli's own export path, but only under KiCad's key.

**What was done.**

1. **Set the finish in the board**, not in the Job file: `(copper_finish "Lead-Free")` → `(copper_finish "ENIG")`
   in `dev-real-production.kicad_pcb`, then a full re-export. The value is design data from this point on.
2. **Added the Ucamco key** with an idempotent, self-checking post-export step (`work/jobfile_finish.py`):
   it locates KiCad's `"Finish"` line, inserts `"SurfaceFinish"` with **the same value read back from the
   file**, re-parses the JSON to prove it is still valid, and refuses to run if `Finish` is empty. Re-running
   it is a no-op (verified).

**Result** (`package/final/dev-real-production-gerbers/dev-real-production-job.gbrjob`):

```json
"ProjectId": { "Name": "dev-real-production", "Revision": "B" },
"Size": { "X": 105.05, "Y": 105.05 },
"LayerNumber": 4, "BoardThickness": 1.6,
"Finish": "ENIG", "SurfaceFinish": "ENIG",
"FilesAttributes": 11 entries  (4 copper / 2 paste / 2 legend / 2 mask / 1 profile)
```

**Why ENIG is the right finish here.** 171 microvias are drilled 0.100 mm and 12 more 0.150 mm; the finest
land pitch is 0.400 mm. HASL cannot hold coplanarity across a 0.400 mm pitch land and its meniscus plugs or
partly fills 0.100 mm vias, with uncontrolled thickness. ENIG (3–6 µm Ni / 0.05–0.10 µm Au) is coplanar and
does not bridge fine-pitch lands. Nickel/gold thickness and cost still need the fabricator's agreement, and
the microvias still need via fill + sequential lamination (see §5).

---

## 2. Defect 2 — POS 292 rows vs 320 footprints

**Diagnosis (measured, not assumed).** Parsing all 320 footprint blocks out of the `.kicad_pcb` and diffing
against the 292 POS refs gives 28 missing refs, in two clean groups — **no part is missing for being DNP,
and nothing is unplaced**:

* **18 through-hole connectors**, none of which carries an exclude flag:
  `J1, J2, J3, J5, J6, J7, J8, J11, J12, J13, J14, J15, J16, J18, J19, J21, J22, J23`
  (Phoenix terminal blocks, SMA, RJ45, 2.54 mm headers, USB-C receptacles). The file had been produced with
  the **`--smd-only`** filter, which silently drops every footprint with a through-hole pad.
* **10 footprints carrying `exclude_from_pos_files` on the board**: `TP1–TP9`
  (`TestPoint:TestPoint_Pad_D1.0mm` — bare 1.0 mm probe pads, no part) and `NT1`
  (`NetTie:NetTie-2_SMD_Pad0.5mm` — copper-only net tie). These *should* be absent; the attribute was right.

Latent inconsistency found while reconciling: the old POS **included** the three parts the BOM marks `DNP`
(`CANT1`, `CANT2`, `REXTVDD1`), i.e. a pick-and-place that tells a machine to place parts the BOM says not to fit.

**Fix.** Re-exported with
`kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp` — no SMD filter, DNP excluded.

**Reconciliation to the BOM (the reference, 320 lines):**

```
320 footprints / BOM refs
 - 10  exclude_from_pos_files : TP1 TP2 TP3 TP4 TP5 TP6 TP7 TP8 TP9 NT1   (no part to place)
 -  3  DNP per BOM DNP column : CANT1 CANT2 REXTVDD1
 = 307  rows in dev-real-production-positions.csv      (294 top / 13 bottom)
```

Every omitted reference is named and justified; there is no residual 28-row mystery. Convention is unchanged
from the previous package (mm, `Side`, no bottom X-mirror, KiCad's Y sense), which was spot-checked against
incumbent rows (`C81 64.000000, -26.000000, 0, bottom` reproduces byte-for-byte).

---

## 3. Defect 3 — the 8 real DRC defects

### 3.1 Locating the 5 slivers

`kicad-cli` gives `copper_sliver` with `items: []` and no coordinates in either output format, so the
checker was reimplemented from source (§0). It found exactly the 5 the DRC found, on the same layers:

| # | Layer | Position (mm) | needle: turn / mouth / arms |
| --- | --- | --- | --- |
| 1 | Top | 15.8167, 58.4148 | 13.82° / 0.329 / 0.590–0.871 mm |
| 2 | Top | 16.9495, 21.8363 | 13.03° / 0.594 / 0.164–0.752 mm |
| 3 | Power Layer 2 | 57.0605, 5.0266 | 17.82° / 5.037 / 6.529–10.839 mm |
| 4 | Bottom | 26.8045, 68.2266 | 6.99° / 0.435 / 0.800–1.218 mm |
| 5 | Bottom | 37.8973, 51.7887 | 15.95° / 0.206 / 0.337–0.507 mm |

### 3.2 Cause, fix, proof — one row per defect

Coordinates below are the copper that was actually edited; the edit log is `work/fix_one.py` (every mutation
prints) and the intermediate boards are `work/v2/s0..s9.kicad_pcb`.

| # | Defect | Where | Root cause | Fix | After |
| --- | --- | --- | --- | --- | --- |
| 1 | copper_sliver | Top 15.8167,58.4148 | Two GND branches into C105.2 pad (0.30 mm from C104.2, 0.25 mm from via 15.9857,59.0700) converged at **13.8°**, leaving a knife-edge wedge of copper 0.87 mm long. | Deleted the redundant **0.25 mm** branch; the pad keeps the 0.30 mm one. Via (15.9857,59.0700) stays on GND through the plane. | gone |
| 2 | copper_sliver | Top 16.9495,21.8363 | The +3V3 stub into via (16.9793,22.0911) left the U5.13 pad at **13.0°** to the main +3V3 trace. | Re-anchored the stub on via (17.0500,21.4375) (the pad is still tied by its own 0.2 mm track). Merge angle now 29°. | gone |
| 3 | copper_sliver | In2 57.0605,5.0266 | Two GND traces left vias (57.0000,4.5250) and (57.0000,4.8500) at **17.8°** — a 6.5 mm / 10.8 mm needle, the largest on the board. | Elbow inserted at (57.9000,5.2000); departure angle now 33°, second leg unchanged. | gone |
| 4 | copper_sliver | Bottom 26.8045,68.2266 | A 1.27 mm GND stitch ran 0.11 mm from a 4.6 mm GND trace and crossed it at **7.0°**. | Deleted the stitch; its via (26.1345,68.8427) now **T**s into the long trace perpendicular at (26.0099,68.6411). | gone |
| 5 | copper_sliver | Bottom 37.8973,51.7887 | A +3V3 stub met the +3V3 track at **15.9°** right at the track elbow. | Stub re-routed from the track end (38.1025,52.2888) to via (38.2528,52.0544); old 0.5 mm stub deleted. | gone |
| 6 | holes_co_located | 71.5, 66.3 | Buried **In1→In2** via drilled at the same XY as the **Top→In1** microvia: a stacked-via pair on /Power/SW at the MIC28516 switch node. | Buried via moved to **(71.5, 67.05)**; bridged on Ground Layer 1 and on Power Layer 2 (0.2 mm). | gone |
| 7 | holes_co_located | 71.5, 66.0 | Same stacked pair. | Buried via moved to **(71.5, 66.7)**; bridged by the same In1/In2 segments. | gone |
| 8 | track_dangling | Top 21.5420,40.3517 | `/STM32H7/JTDI` was left **0.90 mm short**: one segment ended at (20.5878,41.3059), the next began at (20.7705,40.9820). The stub's free end was the violation. | Moved that endpoint to (20.7705,40.9820). Route is now continuous; **nothing was deleted**, so no net lost its path. | gone |

Two things were explicitly avoided:

* **The span census.** Separating the stacked vias by *converting* them (merging each pair into one blind
  Top→In2 via) would have changed 186 micro + 14 buried into 184 + 12 + 2 blind — a census change. Instead all
  4 vias were kept where they are on Top and the two buried ones were relocated. Count, drill and span are
  identical: **1941 vias, 201 non-through = 186 micro + 1 blind + 14 buried, before and after.**
* **The HDI.** Nothing here touches the 186 microvias' annular ring. The recommendation on record (accept
  HDI; forcing through-vias measured +545 violations including 80 shorts) was not re-litigated.

Hole geometry after the move: the four holes at x = 71.5 mm are **0.350 mm** apart on centre in y
(66.0 / 66.35 / 66.7 / 67.05). The project's minimum hole-to-hole is 0.15 mm edge-to-edge, i.e. 0.30 mm
centre distance for equal 0.150 mm drills — so 0.350 mm has margin, and no two holes share a drill position.

### 3.3 DRC before / after, and the per-type set diff

Both runs: `kicad-cli pcb drc --format json --severity-all --units mm`, inside a directory carrying
`.kicad_pro` + `fp-lib-table` + `sym-lib-table` + every local footprint library.
Before: `drc/before.json`. After: `package/final/drc-dev-real-production.json`.

| Type | Severity | before | after | delta |
| --- | --- | ---: | ---: | ---: |
| copper_sliver | warning | 5 | 0 | **−5** |
| holes_co_located | warning | 2 | 0 | **−2** |
| track_dangling | warning | 1 | 0 | **−1** |
| lib_footprint_mismatch | warning | 2 | 2 | 0 |
| **total** | | **10** | **2** | **−8** |
| errors | | 0 | 0 | 0 |
| unconnected_items | | 0 | 0 | 0 |

**New violations: none.** The set diff is exactly the eight named defects, nothing else moved.

The 2 remaining items are named, and they are **not** copper, drill or connectivity defects:

* `lib_footprint_mismatch`: **RANT1** (`R_0402_1005Metric`) and **CANT1** (`C_0402_1005Metric`) — the board's
  embedded copies of those two footprints differ from the copies in the project's local `Resistor_SMD` /
  `Capacitor_SMD` libraries. Fabrication is driven by the board's embedded footprints, which are exactly what
  the Gerbers were plotted from. With `lib_footprint_mismatch` set to `ignore` — the setting the earlier audit
  used — the same board reports **0 violations / 0 unconnected** (`drc/after-mismatch-ignore.json`).

### 3.4 Connectivity, on both tools

* `kicad-cli` JSON `unconnected_items`: **0**
* `pcbnew` `CONNECTIVITY_DATA::GetUnconnectedCount(false)`: **0** (and 0 for visible-only)

---

## 4. Defect 4 — manifest, release notes, revision stamp

* **Revision stamped.** No `.kicad_pcb` in the repo had a `title_block` at all — the job file's
  `ProjectId.Revision` was literally `"rev?"`. The released board now carries
  `title / date 2026-11-18 / rev "B" / company / 4 comments`, and kicad-cli propagates the revision into the
  job file (`"Revision": "B"`). "B" is deliberate: the predecessor `dev-real` (4-layer prototype, still in the
  repo and *not* orderable) is the A-line; this is its first controlled release.
* **Release notes rewritten.** The old `RELEASE_NOTES.md` claimed "0 errors / 0 unconnected" and never
  mentioned the 8 defects, the empty SurfaceFinish or the 292-row POS — it was stale in exactly the way that
  makes a package dangerous. The new notes state the revision, the four fixes with coordinates, the
  verification numbers, the drill census, the POS reconciliation and the HDI requirement.
* **Manifest regenerated.** `package/final/SHA256SUMS.csv`, 28 entries, uppercase SHA-256,
  `<hash>  <relpath>`, sorted — covers every file in the package including `RELEASE_NOTES.md`, the board
  itself and the DRC reports; excludes only itself.

**Self-verification: 28 / 28 entries recomputed and matched, 0 mismatches.** (Carried from the earlier audit,
not re-measured here: the old manifest was 46 clean + 2 that matched only after CRLF normalisation + 1
genuinely stale + 0 missing = 48 of 49.)

---

## 5. Final verification matrix

| Check | Required | Measured | Verdict |
| --- | --- | --- | --- |
| DRC with full companions, errors | 0 | 0 | PASS |
| DRC total | 10 → target 0 | 10 → **2** (both `lib_footprint_mismatch`) | PASS on the 8 assigned defects; 2 named library warnings remain |
| DRC per-type set diff | only the 8 defects removed | −5 sliver, −2 co-located, −1 dangling; 0 new | PASS |
| DRC with `lib_footprint_mismatch` = ignore | 0 | 0 violations / 0 unconnected | PASS |
| Unconnected — kicad-cli | 0 | 0 | PASS |
| Unconnected — pcbnew | 0 | 0 | PASS |
| Span census | 201 = 186 micro + 1 blind + 14 buried | 201 = 186 + 1 + 14, of 1941 vias | PASS (unchanged) |
| gbrjob SurfaceFinish | non-empty | `"ENIG"` (plus `Finish: "ENIG"`) | PASS |
| gbrjob size / thickness / layers / revision | 105.05×105.05 / 1.6 / 4 / set | 105.05×105.05 / 1.6 / 4 / "B" / 11 layer files | PASS |
| POS rows vs BOM | reconcile to 320 | 307 = 320 − 10 attribute-excluded − 3 DNP, all named | PASS |
| Manifest self-verify | 100 % | 28/28 = 100 % | PASS |
| Drill census | drills and G85 slots separate | 2069 drills + 16 G85 slots = 2085 hits | PASS |
| Non-through drill hits | 201 | 183 (front-in1) + 1 (front-in2) + 17 (in1-in2) = 201 | PASS |
| HDI re-litigation | none | none | PASS |

**Drill census detail** (Excellon, `work/drill_census.json`):

| File | FileFunction | tools | drills | G85 slots | hits |
| --- | --- | ---: | ---: | ---: | ---: |
| `dev-real-production.drl` | MixedPlating,1,4 | 13 | 1868 | 16 | 1884 |
| `dev-real-production-front-in1.drl` | Plated,1,2,Blind | 2 | 183 | 0 | 183 |
| `dev-real-production-front-in2.drl` | Plated,1,3,Blind | 1 | 1 | 0 | 1 |
| `dev-real-production-in1-in2.drl` | Plated,2,3,Buried | 3 | 17 | 0 | 17 |
| **total** | | **19** | **2069** | **16** | **2085** |

**Board-level diff, original → released:** footprints 320 → 320, vias 1941 → 1941, track segments
9310 → 9312 (+2 net: one deleted, three added), copper finish Lead-Free → ENIG, title block absent → rev B.

---

## 6. Hazards hit on this run (worth carrying forward)

1. **`PCB_VIA.GetWidth()` hang — confirmed live.** A console print of a via's size inside the edit script hit
   `pcb_track.cpp(381) assert "false" … GetWidth called without a layer argument` and then hung with no exit.
   The job was killed, the orphan `python.exe` (PID 13400) killed by PID, and the print reduced to
   `GetDrillValue()`. Via size never came from the API; the census parses `(size …)`/`(drill …)` from the text.
2. **DRC outside the companion directory manufactures violations — confirmed twice.** With only `*.pretty`
   copied: 10 → 14 (4 fake `lib_footprint_issues`). With a *bare* board directory (no `.kicad_pro` at all):
   the same fixed board reported **1510** violations (199 `annular_width`, 199 `via_diameter`, 199
   `drill_out_of_range`, 506 `clearance`, 213 `hole_clearance`, 132 `hole_to_hole` …) purely because default
   design rules replaced the project's 0.050 mm microvia annular ring and 0.127 mm via rules. Always copy
   `.kicad_pro` + `fp-lib-table` + all local library dirs, and check the JSON exists before parsing.
3. **`kicad-cli` cannot emit `GeneralSpecs.SurfaceFinish`** — verified by binary string search and two exports.
   Fab-facing releases need the documented post-export key, or the vendor reads `Finish` and guesses.

---

## 7. Verdict

**IS DEV-BOARD NOW ORDERABLE: YES.**

The four assigned defects are closed and proven: the job file states `SurfaceFinish = ENIG` (set in the board
stackup, propagated by kicad-cli, mirrored into the Ucamco key by a documented idempotent step); the position
file reconciles to the BOM with all 13 omissions named; all 8 copper/drill defects are gone from a
full-companion DRC (10 → 2, set diff exactly the 8, no new items) with 0 unconnected on both tools and the
201-via HDI census untouched; the manifest verifies 100 % of its own 28 entries and carries a revision stamp
the board previously did not have.

**What still needs saying to the fabricator, and is not a defect:**

1. **Two `lib_footprint_mismatch` warnings remain** (RANT1, CANT1): the board's embedded footprints differ from
   the project's local library copies. Not fab-blocking — the Gerbers come from the embedded footprints — but
   it will keep the DRC counter off 0 until the library copies are reconciled.
2. **This is a sequential-lamination HDI build** (183 blind Top→In1 hits, 1 Top→In2, 17 buried In1→In2, all
   microvias 0.200/0.100 and 0.300/0.150). Quote it as HDI with via fill; a shop that quotes it as an ordinary
   4-layer through-via job will not build it correctly.
3. **Impedance is not certified**, and the USB/RF length-tuning mismatches carried in the previous notes are
   still open. Neither blocks ordering; both belong in the RFQ conversation.
4. The `dev-real` prototype variant is deliberately **not** in this package — it still has the same 8 defects.

---

## 8. Artefacts

| Path | Contents |
| --- | --- |
| `package/final/` | 28-file released package + `SHA256SUMS.csv` (100 %) |
| `package/final/RELEASE_NOTES.md` | revision B notes, in the manifest |
| `package/final/dev-real-production-gerbers/` | 11 Gerbers, job file, 4 Excellon files, 4 drill maps |
| `package/final/dev-real-production-positions.csv` | 307 rows |
| `package/final/drc-dev-real-production.{json,rpt}` | the DRC of record for this board |
| `drc/before.json` | baseline 10-violation DRC (full companions) |
| `drc/after-mismatch-ignore.json` | same board, `lib_footprint_mismatch` ignored: 0 / 0 |
| `work/sliver_scan.py`, `work/slivers.json`, `work/slivers_after.json` | sliver locator, before (5) / after (0) |
| `work/via_census.py`, `work/viacensus.json` | span census, both boards |
| `work/drill_census.py`, `work/drill_census.json` | drills vs G85 slots |
| `work/fix_one.py` | every board edit, one site per invocation, prints each mutation |
| `work/v2/s0..s9.kicad_pcb`, `work/v3/dev-real-production.kicad_pcb` | edit chain, release board |
| `logs/` | raw kicad-cli stdout for the DRC runs |