# Code-SDR V2 — shipped package: finish field + SHA256 manifest

**Scope:** fix exactly two paperwork defects on an otherwise complete/orderable board. No redesign, no reroute, no repo writes, no commit.
**Host:** KiCad 9.0.7 (`C:\Program Files\KiCad\9.0\bin\kicad-cli.exe`, bundled `python.exe`), 2026-11-18.
**Evidence dir (this work):** `E:\engineering-portfolio-audit\evidence\cs-orderable-fix\` → junction `D:\ep-audit-evidence\cs-orderable-fix\`.
**Package under repair (read-only):** `evidence/fab-cs-fid-real/package/` — 3 dirs, **19 files** (3 assembly + 4 drill + 11 gerbers + 1 `.gbrjob`).
**Corrected package produced here:** `evidence/cs-orderable-fix/package/` — same 19 files + `SHA256SUMS`.

---

## 1. Both defects confirmed on the CURRENT package

### 1.1 `SurfaceFinish` is absent from the job file

File inspected: `evidence/fab-cs-fid-real/package/gerbers/Code-SDR-V2-job.gbrjob`
(sha256 `dcb3077bccd58d8c0c12bd9478ffceb3b3aa952be7f27a7304b9dbc8a909936b`, 4111 bytes, `CreationDate 2026-11-16T07:18:25+05:30`, written by `KiCad/Pcbnew 9.0.7`).

`GeneralSpecs` keys as shipped, in order:

```
['ProjectId', 'Size', 'LayerNumber', 'BoardThickness', 'Finish', 'ImpedanceControlled']
```

- `"Finish": "ENIG"` — **present**, line 22.
- `"SurfaceFinish"` — **the key does not exist at all**. Not empty-string, not null: absent.

Reproduce:

```powershell
Select-String -LiteralPath '<pkg>\gerbers\Code-SDR-V2-job.gbrjob' -Pattern 'Finish'
# L22:     "Finish": "ENIG",      <- and nothing else
```

Nothing else in the file carries the finish either: `MaterialStackup` (13 entries) lists mask/copper/dielectric/legend layers with thickness, material, Dk and loss tangent, and **no** finish entries, notes or comments. So a fab that reads `SurfaceFinish` (the Gerber-Job standard field, and the one this programme's other job files populate) gets nothing.

Root cause is the exporter, not the board: KiCad 9.0.7 emits `GeneralSpecs.Finish` and never writes a `SurfaceFinish` key. Re-exporting the same board reproduces the defect exactly (verified below — the re-exported job file had only `Finish` before the repair step).

### 1.2 There is no hash manifest in the package

`evidence/fab-cs-fid-real/package/` contains **19 payload files and no manifest of any kind**:

```
assembly/Code-SDR-V2-BOM-flat.csv   assembly/Code-SDR-V2-BOM-grouped.csv   assembly/Code-SDR-V2-pos.csv
drill/Code-SDR-V2-NPTH.drl   drill/Code-SDR-V2-PTH.drl   drill/*-drl_map.gbr (2)
gerbers/Code-SDR-V2-{F_Cu,In1_Cu,In2_Cu,B_Cu,F_Paste,B_Paste,F_Silkscreen,B_Silkscreen,F_Mask,B_Mask,Edge_Cuts}.* (11)
gerbers/Code-SDR-V2-job.gbrjob
```

A name search for `sha|sum|manifest|checksum|digest|md5|crc` anywhere under `package/` returns **zero hits**. There is also no README or `.gitattributes`.

This is an outlier in the programme: the predecessor package for the same board, `evidence/fab-cs-ship/package/MANIFEST.sha256`, exists and verifies. The `fab-cs-fid-real` wave shipped scripts that *can* write a manifest (`make_manifest.py`) but nobody ran the step into this package.

---

## 2. Finish fix — mechanism and before/after

### 2.1 Source board found, and the finish was already design data

- Board of record: `repos/Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb`
  sha256 `fe8a41a60d5910d7579960f930fd4ddbaf957131cc932f94d005d110e698959d` (same bytes as `fab-cs-fid-real/post_commit/Code-SDR-V2.kicad_pcb`, i.e. the board the package was exported from).
- The finish **is already design data** in the stackup — `kicad_pcb` lines 45–105:

```
(setup (stackup … (copper_finish "ENIG") (dielectric_constraints yes)))
```

- Intended finish is documented as ENIG in the board's own paperwork: `STACKUP_DRAWING.md` ("Copper finish: **ENIG**") and `FABRICATOR_IMPEDANCE_NOTE.md` ("Nominal finished board thickness is 1.60 mm and finish is ENIG").
- **ENIG is therefore correct for this board and was not changed.** No silent finish swap: the value in the job file, the stackup and the two documents all agree.

Because the design data was already correct, the fix needed **no board edit at all** — the board stayed byte-identical (`fe8a41a6…`) and nothing was written into the repo.

### 2.2 Mechanism actually used (three steps, as prescribed)

1. **Design data present** — `(copper_finish "ENIG")` in `.kicad_pcb` setup stackup (verified, above).
2. **Re-export** — copied the board **and all its companions** into `cs-orderable-fix/src/` (`.kicad_pcb` byte-identical, `.kicad_pro`, `.kicad_dru`, `.kicad_sch`, `fp-lib-table`, `sym-lib-table`, `CodeSDR.kicad_sym`, `CodeSDR.pretty/`, `sheets/`), then re-ran the **recorded export flags** from `fab-cs-fid-real/export_pkg.ps1` with `kicad-cli`:
   - `pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --precision 6` → 11 gerbers + `.gbrjob`
   - `pcb export drill --format excellon --excellon-units mm --excellon-separate-th --generate-map --map-format gerberx2 --excellon-oval-format alternate --drill-origin absolute` → PTH/NPTH + 2 drill maps
   - `pcb export pos --format csv --units mm --side both` → pos csv
   - `sch export bom` (grouped, then flat, same fields/labels/group-by) → 2 BOMs
   - Run log: `cs-orderable-fix/export.log.txt`.
3. **Scripted `Finish` → `SurfaceFinish` copy** — `cs-orderable-fix/fix_surface_finish.py` inserts exactly one line (`"SurfaceFinish": "<Finish>",`) immediately after the `"Finish"` line, so the rest of the file stays byte-identical to what KiCad wrote. It validates the JSON before and after, refuses to run if `Finish` is missing/empty, and is **idempotent**.

```powershell
& 'C:\Program Files\KiCad\9.0\bin\python.exe' fix_surface_finish.py <pkg>\gerbers\Code-SDR-V2-job.gbrjob
# run 1: FIX  … : SurfaceFinish None -> 'ENIG'          (exit 0)
# run 2: OK   … : SurfaceFinish already == 'ENIG' (no change)  (exit 0)
```

### 2.3 Before / after

| Field | Shipped (before) | Corrected (after) |
|---|---|---|
| `GeneralSpecs.Finish` | `"ENIG"` | `"ENIG"` |
| `GeneralSpecs.SurfaceFinish` | **key absent** (`null`) | `"ENIG"` |
| `GeneralSpecs` keys | ProjectId, Size, LayerNumber, BoardThickness, Finish, ImpedanceControlled | … Finish, **SurfaceFinish**, ImpedanceControlled |
| job file size / sha256 | 4111 B / `dcb3077b…09936b` | 4140 B / `9b4365de…b86e2` |

`Finish` and `SurfaceFinish` are **both `ENIG`** in the corrected job file:

```
L22:     "Finish": "ENIG",
L23:     "SurfaceFinish": "ENIG",
```

The only other difference in the job file is its `CreationDate` (new export). Everything else — `ProjectId` (Name `Code-SDR-V2`, Revision `2.1`), `Size`, `LayerNumber`, `BoardThickness`, `ImpedanceControlled`, `DesignRules`, all 11 `FilesAttributes`, all 13 `MaterialStackup` entries — is **identical** to the shipped file, proven programmatically (`differ.py`).

---

## 3. Re-export regression check

Instrument: `cs-orderable-fix/inspect_pkg.py` (text/Excellon census, no pcbnew) and `cs-orderable-fix/board_metrics.py` (pcbnew: layers, edge bbox, title block — no `PCB_VIA.GetWidth()`).

| Check | Expected | Shipped package | Re-exported package | Verdict |
|---|---|---|---|---|
| Drill census | 1213 drills + 2 G85 slots = 1215 hits | PTH 1211 drills + 2 slots; NPTH 2 drills; **1213 + 2 = 1215** | PTH 1211 + 2; NPTH 2; **1213 + 2 = 1215** | unchanged |
| per-tool drill counts | — | T1 983, T2 73, T3 89, T4 11, T5 13, T6 10, T7 2, T8 10, T9 2, T10 12, T11 4, T12 2, T13 2 | identical, tool-for-tool | unchanged |
| Drill file functions | PTH / NPTH | `Plated,1,4,PTH` / `NonPlated,1,4,NPTH` | identical (no blind/buried) | unchanged |
| Pos rows | 377 components | 377 (`Ref,Val,Package,PosX,PosY,Rot,Side`) | 377 | unchanged — file **byte-identical** (`f51483bf…a43f7`) |
| BOMs | — | 32 918 B / 22 528 B | byte-identical both | unchanged |
| Outline | 101.7 x 101.7 mm | `Size` 101.7 / 101.7; board edge bbox 101.7000 x 101.7000 | `Size` 101.7 / 101.7; edge bbox 101.7000 x 101.7000 | unchanged |
| Copper layers | 4 | `LayerNumber` 4; 4 copper gerbers (L1 top, L2 inr, L3 inr, L4 bot) | identical | unchanged |
| Revision | 2.1 | `ProjectId.Revision` 2.1 | 2.1 | unchanged |
| Job file `FilesAttributes` | 11 | 11 | 11, same list/order/functions | unchanged |

Whole-package byte diff (`cs-orderable-fix/differ.py`, normalising only generation timestamps):

- **3 files byte-identical** — all three assembly files.
- **15 files differ only by the generation timestamp** in their headers (`%TF.CreationDate`, `G04 Created by KiCad … date …`, `; #@! TF.CreationDate`) — all 11 gerbers, both drill files, both drill maps. Same byte sizes, same line counts, geometry identical.
- **1 file differs by content** — `Code-SDR-V2-job.gbrjob`, and its sole content change is the added `SurfaceFinish` key (verified: removing that key and normalising the timestamp makes the two files identical).

**No regression.** The board did not change: `fe8a41a60d5910d7579960f930fd4ddbaf957131cc932f94d005d110e698959d` before and after, footprints 377, tracks 12 253, zones 4, vias 1085 (all through-hole, no blind/buried).

---

## 4. SHA256SUMS manifest — 19 of 19 verify

Produced by `cs-orderable-fix/make_manifest.py`; the manifest is `package/SHA256SUMS`.

Format (pure sha256sum style — **no comment lines**, so `sha256sum -c` exits 0 cleanly; LF endings; no BOM; no CR):

```
<64 hex delimiters><two spaces><package-relative path with forward slashes>
```

19 entries, one per payload file, sorted case-insensitively:

```
6341c99a10261f555ed27ebc58e4886bf1c71165672aeb55f60eee725c7155ff  assembly/Code-SDR-V2-BOM-flat.csv
2af66771713bd4b7bd9bc277387af7bcd934b32a8d0ecd19dcfc9622688fbc0d  assembly/Code-SDR-V2-BOM-grouped.csv
f51483bf4ae3e1cc94473dab3347af1a464d35382c11f8cf6d814edbe6fa43f7  assembly/Code-SDR-V2-pos.csv
8e9c4c93948394e2ab894d6f2d2e75aa238c027a8268373dd7349918c5a6aae8  drill/Code-SDR-V2-NPTH-drl_map.gbr
2375409ee0bffd5d657a9105b2ec7c69c3275c7981ae42c98cea2ef672ac9d9b  drill/Code-SDR-V2-NPTH.drl
cda82ab63de742230a70f75185c6ef60e21ec120df1235a3e59b74010b451b74  drill/Code-SDR-V2-PTH-drl_map.gbr
a0e231f5f422811a56eed389e467eea43ebece6e69cc56bc5f7db80cd7ea8a66  drill/Code-SDR-V2-PTH.drl
de6ccd0067d7805684a3dbeacb52781e8c5252bf2a04986523d072503292d09e  gerbers/Code-SDR-V2-B_Cu.gbl
bc66a7af6a86ceb4a48ff7085b61f4b11c8d1d238a210e364baaf9d3af6640ef  gerbers/Code-SDR-V2-B_Mask.gbs
2744137c35720c3f940b2287e642595a55e87112d2fd176ae832fdfa6833d9ee  gerbers/Code-SDR-V2-B_Paste.gbp
5ec7dd4e43801f12dd3c6f5617cdbfe5d6ad96121eecfb9c49db80d5c14b310f  gerbers/Code-SDR-V2-B_Silkscreen.gbo
91de6829378fca7e1c50b85c377ff97e53d15f2605be37ef8039dcbcd7c47a0c  gerbers/Code-SDR-V2-Edge_Cuts.gm1
1c2dc16d910a87474b13389b3b7aba476f1150563aa4aa73191b28e26a57f087  gerbers/Code-SDR-V2-F_Cu.gtl
b142c00e1368bc510b466943b4ef48707d0d1952845b194cd1f919196cf71a12  gerbers/Code-SDR-V2-F_Mask.gts
894059eacc096c2ee0c05f886fc56e172beb6ae735a4488892872c35d15b745f  gerbers/Code-SDR-V2-F_Paste.gtp
2b64a30644ccf2b0823c0c4da5517b2f314a077a23e904898c034da83e73a959  gerbers/Code-SDR-V2-F_Silkscreen.gto
a3a90695d44ad944927b6e6bef8ba72ef089f188c44644e27baeab027a6a9295  gerbers/Code-SDR-V2-In1_Cu.g1
7ad5d384bb62ac7fe32235b8c95d23d53adc2396f574d3e962153a8342ea12d7  gerbers/Code-SDR-V2-In2_Cu.g2
9b4365deeff0ce2d88f6279ad2b67b420b154c6e876d505875353af1332b86e2  gerbers/Code-SDR-V2-job.gbrjob
```

### Verification, three independent implementations

| Verifier | Result | Exit |
|---|---|---|
| `verify_manifest.py` (own parser, independently re-hashes) | **19 of 19 verify**; 0 failed, 0 missing, 0 unparseable, **0 uncovered files** | 0 |
| GNU coreutils **8.32** (`D:\Git\usr\bin\sha256sum.exe -c SHA256SUMS`, cwd = package) | 19 × `OK` | 0 |
| GNU coreutils **9.4** (WSL `Ubuntu2404`, `cd /mnt/e/.../package && sha256sum -c SHA256SUMS`) | 19 × `OK` | 0 |

### Spaces in filenames — handled, and proven

This package's 19 names contain **no spaces** (checked), but the writer/parser were built for names that do: the filename is taken as *the rest of the line* after the 64-hex digest and one whitespace run, exactly as GNU `sha256sum -c` does. Proven with a synthetic fixture (`a b c.txt`, `Code-SDR-V2 rev 2.1 job.gbrjob`):

- `make_manifest.py` → 2 entries, both with spaces;
- own verifier → 2 of 2 OK; GNU `sha256sum -c` → 2 × `OK`, exit 0;
- after appending a byte to one file: verifier reports `1 of 2 verify`, exit **1** — the manifest actually detects tampering rather than just formatting files.

---

## 5. Final DRC — 0 errors, 0 unconnected (both tools)

Run in `cs-orderable-fix/src/` **with the full companion set** present in the same directory (`.kicad_pro`, `.kicad_dru`, `fp-lib-table`, `sym-lib-table`, `CodeSDR.kicad_sym`, `CodeSDR.pretty/`, `sheets/`):

```powershell
kicad-cli pcb drc --output drc_final.json --format json --severity-all --units mm src\Code-SDR-V2.kicad_pcb
# Found 222 violations
# Found 0 unconnected items
```

| Metric | Value |
|---|---|
| **errors** | **0** |
| warnings | 222 → `lib_footprint_mismatch` 199, `via_dangling` 13, `track_dangling` 10 |
| unconnected (kicad-cli JSON `unconnected_items`) | **0** |
| schematic parity findings | 0 |
| unconnected (pcbnew `CONNECTIVITY_DATA.GetUnconnectedCount(False)` / `(True)`) | **0 / 0** |
| violations identical to the prior wave's `drc_final.json` (type+severity+description set) | **yes** — 222 vs 222, sets equal |

Nothing was rerouted, deleted or added. The 222 warnings are the pre-existing, unchanged set (library-footprint drift plus dangling stubs) and are byte-equivalent to the previous wave's record; they are not errors and were not "fixed" here.

---

## 6. Verdict

**IS CODE-SDR V2's PACKAGE NOW FULLY ORDERABLE: YES** — for the corrected package directory `evidence/cs-orderable-fix/package/` (19 files, `SurfaceFinish = ENIG = Finish`, `SHA256SUMS` 19 of 19 verify, 0 DRC errors, 0 unconnected).

Conditions and limits, stated plainly:

1. The old directory `evidence/fab-cs-fid-real/package/` is **untouched evidence** and still carries both defects. A fab must be given `cs-orderable-fix/package/`, or the old path must be replaced/pointed at the new one — that promotion decision belongs to the owner, not to this audit (write scope = this evidence dir only).
2. The board itself was not modified because the finish was already correct design data; the board sha256 is unchanged (`fe8a41a6…959d`), nothing was written into the repo, and nothing was committed. The repo working tree was already dirty before this work (board mtime still 2026-11-16 07:17:17).
3. The 222 pre-existing DRC warnings remain as found — they are warnings, not errors, and out of scope.
4. `SurfaceFinish` is still absent from what KiCad 9.0.7 emits; **any future re-export must re-run `fix_surface_finish.py`** (idempotent) or the defect returns silently. Same for `make_manifest.py` after any content change.

## Reproduce

```powershell
$py = 'C:\Program Files\KiCad\9.0\bin\python.exe'
cd E:\engineering-portfolio-audit\evidence\cs-orderable-fix
& $py inspect_pkg.py package                     # finish fields + drill/pos/outline census
& $py differ.py ..\fab-cs-fid-real\package package # shipped vs re-export classification
& $py fix_surface_finish.py package\gerbers\Code-SDR-V2-job.gbrjob   # idempotent
& $py make_manifest.py package
& $py verify_manifest.py package SHA256SUMS
```

Files in this evidence dir: `REPORT.md`, `src/` (board + companions, board byte-identical), `package/` (corrected 19 files + `SHA256SUMS`), `export.log.txt`, `drc_final.json`, `inspect_pkg.py`, `board_metrics.py`, `differ.py`, `drc_summarize.py`, `drc_compare.py`, `unconn_pcbnew.py`, `fix_surface_finish.py`, `make_manifest.py`, `verify_manifest.py`.