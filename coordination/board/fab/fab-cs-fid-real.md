# Code-SDR V2 — fiducials on the ACTUAL repo board, and re-ship

**Verdict: the ship-blocking defect is closed.** The repository board now carries 4 fiducials, the
fabrication package was re-exported from that board, both are committed and pushed as `fbf2eca`, and
the post-commit check reads the fiducials out of the committed blob — not out of a copy.

| | |
|---|---|
| Repo | `repos/Code-SDR`, branch `work/2026-11-11` |
| Start HEAD | `1a20bd6` (5,562,840 B board, sha256 `309414D2…FF486`) |
| Final HEAD | **`fbf2eca`**, pushed to `origin/work/2026-11-11` (`1a20bd6..fbf2eca`) |
| Committed board | sha256 **`FE8A41A6…E698959D`** (5,572,908 B), same bytes as the measured working file |
| Fiducials | **4** = 3 global + 1 local, 1.0 mm dot / 2.0 mm mask |
| Min gap | **1.5005 mm** against the 1.25 mm requirement (**+0.2505**, never 0.0005) |
| DRC | **222 → 222**, 0 errors, 0 unconnected, **0 added / 0 gone** |
| Assembly | **still blocked — 373 / 373 BOM rows have no MPN** |

---

## 0. Git state as found, before touching anything

```
$ git -C repos/Code-SDR status
On branch work/2026-11-11
Your branch is ahead of 'origin/info-dump/2026-11-10-handoff' by 1 commit.
nothing to commit, working tree clean

$ git -C repos/Code-SDR log --oneline -5
1a20bd6 fab: add Code-SDR V2 rev 2.1 bare-board package exported from this board
6fbc004 info-dump: temporary working-tree snapshot 2026-11-10
59ff14f Merge pull request #66 from iamdarshg/em-validation-evidence
43964fe docs: add EM/RF validation proof package (analytical only, fail-closed)
4cdf7e0 add the two missing gates: Verilator lint + RP2040 firmware compile
```

Remote check: `origin/work/2026-11-11` pointed at `1a20bd6`, so **HEAD equalled the remote**. The
local branch's *upstream* is `origin/info-dump/2026-11-10-handoff` at `6fbc004` (1 behind), which is a
branch-tracking artefact, not a divergence — `rev-list --left-right --count HEAD...origin/work/2026-11-11`
was `0 0`.

**Authorship check:** every commit touching `hardware/` or `fab/` is `iamdarshg <iamdarshg@gmail.com>`
(the repo owner / dsh-lead identity). No third-party author touched fab outputs. Tree clean, nothing
of mine or anyone else's uncommitted. Proceeded.

## 1. The defect, confirmed on the repo board (before)

Exact commands and outputs:

```powershell
$b='...\repos\Code-SDR\hardware\v2\Code-SDR-V2.kicad_pcb'
$t=Get-Content -LiteralPath $b -Raw
[regex]::Matches($t,'\(footprint\s').Count    # 373
[regex]::Matches($t,'FID').Count              # 0
[regex]::Matches($t,'fiducial').Count         # 0
```

| quantity | repo board @1a20bd6 |
|---|---|
| sha256 | `309414D2B371C6265629352FC0AA7252AA3E3B630488849187761D24B09FF486` |
| bytes | 5,562,840 |
| footprints | **373** |
| `FID` strings | **0** |
| fiducial properties | **0** |
| revision | 2.1 |
| tracks / vias | 11,168 segments / 1,085 vias |

So **the package could not be assembled**: the 1.2505 mm and 1.7505 mm gaps quoted in earlier waves
describe `B1263807…` and `8EC5741A…` evidence copies, not this board. This unit's whole point is that
the fix lands on the board that ships.

## 2. Method — sites chosen from real copper geometry, not from a raster

Two instruments were built and one **was caught being wrong mid-flight**, which changed the answer:

1. `export_geom.py` — dumps F.Cu pads (`PAD.GetEffectivePolygon(F.Cu)`), tracks, vias and zone fill
   to JSON.
2. `scan_sites.py` / `local_scan.py` — 0.1 mm raster distance transform to *propose* sites, then
   `confirm_sites.py` / `site_probe.py` re-measure every proposal with **exact shapely polygon
   distance**.
3. `courtyard_check.py` — exact distance to every `F.CrtYd` polygon.

**Instrument bug found and fixed.** The first export flattened each zone's outline/hole rings into one
flat list, so `Polygon(rings[0], rings[1:])` produced 4.69 mm² of F.Cu GND fill instead of 3,340 mm²
and a total copper area of 1,502 mm² instead of 4,754.8 mm². The pour was therefore *absent* from the
first distance test, and several sites looked like voids when the pour was in fact right there. The
authoritative measurement (`measure_gaps_pcb.py`) now reads the board objects directly, grouping each
zone outline **with its own holes**. The corrected numbers are what this report quotes.

Site rules applied uniformly:

* fiducial copper edge → any foreign copper ≥ **1.50 mm** (requirement 1.25, so 0.25 margin);
* distance to every footprint courtyard > 0 (a fiducial must not sit in a part's keepout);
* mask opening (r = 1.0 mm) safely inside Edge.Cuts;
* global set asymmetric: two points on a long diagonal, third offset, so a 90°/180° rotation cannot
  match.

## 3. What was placed

| ref | role | x, y (mm) | footprint |
|---|---|---|---|
| FID1 | global | 4.700, 50.600 | `Fiducial:Fiducial_1mm_Mask2mm` |
| FID2 | global | 91.000, 61.000 | same |
| FID3 | global | 49.600, 96.600 | same |
| FIDL_U63_U64 | local | 81.000, 17.900 | same |

* Dot 1.0 mm bare copper, mask opening 2.0 mm (`solder_mask_margin 0.5`), Level A.
* Each pad carries `(clearance 1.5)` so the F.Cu GND pour is pulled back to 1.50 mm from the dot
  edge. Nothing else about the footprint was changed; reference text hidden so no silk lands on
  exposed copper.
* **Triangle:** FID1–FID2 is an **86.9 mm** diagonal; FID3 sits **40.3 mm off that line**, triangle
  area **1,751 mm²**. Rotation-unambiguous.
* Board census before → after: footprints 373 → **377**; tracks 11,168 → 11,168 (**identical set**);
  vias 1,085 → 1,085 (**identical set**); net declarations 1,614 → 1,614; zones 4 → 4; rev 2.1 → 2.1.

### 3.1 Two placement defects I created and then removed (stated, not hidden)

1. **First FID2 at (94.400, 91.000) sat inside J30's courtyard** — DRC reported
   `courtyards_overlap FID2 | J30` at `error` severity. Exact courtyard distance was **0.000 mm**.
   Moved to (91.000, 61.000), 2.794 mm from the nearest courtyard.
2. **Local reference text landed on exposed copper** — `silk_over_copper` on FIDL_U72 and
   FIDL_U63_U64. Reference text is now hidden on all fiducials.

With those fixed, the DRC set diff went to exactly zero (§5).

## 4. Measured gaps — every fiducial, on the committed board

Requirement R1: **≥ 1.25 mm**. Measured as exact polygon distance from the fiducial pad polygon
(`PAD.GetEffectivePolygon(F.Cu)`) to every foreign F.Cu object — tracks buffered at half width, vias
as circles at copper diameter, pads as exact polygons, zone fills grouped per outline with their own
holes — **after `ZONE_FILLER` refilled the board**. Raster is never the evidence.

| ref | edge → copper | centre → copper | margin vs 1.25 | pour-only gap | nearest item |
|---|---:|---:|---:|---:|---|
| FID1 | **4.7843** | 5.2843 | +3.5343 | 4.7843 | F.Cu GND pour |
| FID2 | **1.8462** | 2.3462 | +0.5962 | 15.1843 | via `PHY_AVDDL_1V2` (0.45 mm) |
| FID3 | **2.9604** | 3.4604 | +1.7104 | 50.7897 | pad R120.1 `RGMII_TXD0_FPGA` |
| FIDL_U63_U64 | **1.5005** | 2.0005 | +0.2505 | 1.5005 | F.Cu GND pour |

**Minimum 1.5005 mm.** No fiducial clears by 0.0005: the tightest margin is **+0.2505 mm**, and every
other one is ≥ +0.59. FID2's and FID3's binding items are a via and a pad — the pour is 15.2 mm and
50.8 mm away, so their clearance does not depend on the keepout at all.

Two readings are given because earlier waves measured centre-to-pour (1.2505 = 0.750 clearance +
0.500 radius). The table's first column is **stricter** than that convention.

## 5. DRC — unchanged, item for item

Harness: `kicad-cli pcb drc --format json --severity-all`, board run in its own project directory so
`Code-SDR-V2.kicad_pro` and `.kicad_dru` load.

| | before (`1a20bd6`) | after (`fbf2eca`) |
|---|---:|---:|
| violations | **222** | **222** |
| errors | **0** | **0** |
| unconnected | **0** | **0** |
| `lib_footprint_mismatch` | 199 | 199 |
| `via_dangling` | 13 | 13 |
| `track_dangling` | 10 | 10 |

Set diff on a stable key (type + severity + sorted item descriptions): **0 added, 0 gone.**

Notes that belong with the number:

* A trial in a directory containing only `.kicad_pro`/`.kicad_dru` (no `fp-lib-table`) reported **24
  bogus `lib_footprint_issues`** and dropped 3 `lib_footprint_mismatch` rows. That is a library-
  resolution artefact of the trial directory, not a board change; the final DRC ran with the real
  project library tables.
* A 1.50 mm keepout at the first U72 local site pinched a **1.088 mm² free-standing GND island**, and
  DRC reported `unconnected Zone [GND]`. That site was rejected (§6) and the final board has
  **0 unconnected**.

## 6. Local fiducials — one placed, four parts refused with measurements

A local is placed only where a compliant site exists (≥1.50 mm copper, no courtyard intrusion, no
floating island created by the refill). Searched 0.1 mm raster over ±14 mm per fine-pitch part, then
exact-confirmed.

| part | pitch | outcome |
|---|---|---|
| U63 (DFN-12) / U64 (LGA-24) | 0.5 mm | **placed** FIDL_U63_U64 at (81.000, 17.900), 5.4 / 8.1 mm away, 2.605 mm from copper before the keepout, **no island** |
| U72 (QFN-20) | 0.5 mm | **rejected** — only ≥1.5 mm site (61.950, 36.500) pinched a **1.088 mm²** floating GND island (`unconnected Zone [GND]`); six alternatives within 12 mm have copper at **1.075 / 0.375 / 0.895 / 1.212 / 0.895 / 0.097 mm** |
| U10 (QFN-56) | 0.4 mm | **no compliant site within 10 mm** (best 1.018 mm at 10.2 mm; nearest qualifying void 16.1 mm) |
| U30 (QFN-48) | 0.5 mm | **no compliant site within 10 mm** (nearest 14–15 mm) |
| U40 (VQFN-40) | 0.5 mm | **no compliant site within 10 mm** (nearest 14 mm) |

**The fabricator's written fiducial requirement is UNVERIFIED** — no vendor document was obtained.
The 1.25 mm figure is the programme's own standing requirement, retained unchanged (not lowered).

The prior evidence copies carried 9 fiducials (3 global + 6 local). This board carries 4 because 5 of
those 9 sites do not survive an exact re-measurement against real copper geometry at 1.25 mm.

## 7. Package re-exported from this board (`hardware/v2/fab/`)

Same recipe and flags as the previous package (`fab-cs-ship/export.ps1`), run against the modified repo
board. Validation harness: `validate.py`, **6 / 6 PASS**.

| check | measured |
|---|---|
| copper layers | **4 = 4** (F.Cu, In1.Cu, In2.Cu, B.Cu); 11 gerbers + job |
| Edge_Cuts vs bbox | **101.600 × 101.600 vs 101.600 × 101.600**, delta **0.000000**; 4 draw / 4 move |
| drills | **14 tool definitions**, 13 distinct diameters; **1,213 drills + 2 G85 slots = 1,215 hits**, separate as required; board side 1,085 vias + 128 PTH + 2 NPTH = 1,215, slots 2 — reconciles |
| `.pos` | **377 rows = 377 footprints**, 0 missing / 0 extra / 0 excluded (373 components + 4 fiducials) |
| `.gbrjob` | LayerNumber **4**, Size **101.7**, thickness **1.6**, finish **ENIG**, Revision **2.1**, 11 files |
| revision stamp | board `(rev "2.1")` = job `ProjectId.Revision "2.1"` |
| frame suppression | max coordinate **101.600 mm** (a plotted A4 frame would reach ~200–287) |

Fiducials add **no holes** (1,215 hits unchanged), and they do not enter the BOM (`exclude_from_bom`),
so the MPN blocker stays exactly 373 rows.

**Content comparison against the previous package** (after stripping `%TF.CreationDate` and
`G04 Created by KiCad … date`): B_Cu, B_Mask, B_Paste, B_Silkscreen, F_Paste, F_Silkscreen, Edge_Cuts,
In1_Cu, In2_Cu, both drill maps and both BOMs are **identical**. Only **F_Cu** (673,412 → 676,008 B),
**F_Mask** (682,038 → 685,377 B) and **`.pos`** (373 → 377 rows) changed — exactly the fiducials.
`.drl` and `.gbrjob` differ by timestamp lines only.

Zone fill before → after: **only F.Cu GND changed** (3,340.068 → 3,327.477 mm², −12.591 mm²); In1 GND,
In2 +3V3_DIG and +3V3_ANA are identical to the digit. The refill anomaly noted in §9 is therefore not
in the shipped board.

## 8. Commit, push, and post-commit verification FROM THE COMMITTED BOARD

```
$ git commit  ->  fbf2eca  fab: put 4 fiducials on the Code-SDR V2 board and re-ship the package
   20 files changed, 2908 insertions(+), 2212 deletions(-)   (all modified; nothing deleted)
$ git push origin work/2026-11-11
   1a20bd6..fbf2eca  work/2026-11-11 -> work/2026-11-11
$ git rev-parse HEAD / origin/work/2026-11-11   -> fbf2eca… / fbf2eca…    (0  0)
$ git status --short                            -> (empty, tree clean)
```

**Post-commit check, from the commit object, not the working tree:**

```powershell
git show fbf2eca:hardware/v2/Code-SDR-V2.kicad_pcb > post_commit\Code-SDR-V2.kicad_pcb
```

| check on the committed blob | result |
|---|---|
| sha256 | **`FE8A41A6…E698959D`** — identical to the measured working file |
| bytes | 5,572,908 |
| footprints | **377** |
| `FID` strings | **4** |
| fiducial strings | **4** |
| pads with `(clearance 1.5)` | **4** |
| revision | 2.1 |
| FID1 / FID2 / FID3 / FIDL_U63_U64 | present at 4.7,50.6 / 91,61 / 49.6,96.6 / 81,17.9 |
| **measured gaps from the committed blob** | **4.7843 / 1.8462 / 2.9604 / 1.5005 mm** — identical to §4 |
| DRC on the committed blob | **222 / 0 errors / 0 unconnected, 0 added, 0 gone** |
| committed `MANIFEST.sha256` vs committed blobs | **20 entries, 0 mismatches** |

That is the verification this unit exists for: the fiducials are on the board that is in the commit.

## 9. Honest notes, deviations and limits

1. **A refill non-determinism was observed once and not explained.** One early trial (`trial_out`)
   refilled In1.Cu and In2.Cu with different geometry (In1 8,808.7 → 8,589.3 mm², +3V3_DIG 4,465.0 →
   4,208.6 mm²). It was not used. Two independent re-runs of the final placement agreed to the digit,
   and the shipped board's In1/In2 fills are **identical to the pre-fiducial board**, so the anomaly
   is not in the package. Recorded because an unexplained non-determinism in a zone refill is worth
   knowing about.
2. **A raster-only check was 0.05 mm optimistic** early in site selection; every accepted site was
   re-measured with exact polygons, and the reported gaps are polygon-exact.
3. **No fabricator sign-off** on the local-fiducial requirement. 1 local is what the board geometry
   supports; the 0.4 mm QFN (U10) has no compliant local site at all, which is a genuine limitation
   of this layout, not an omission.
4. The board remains **101.6 mm square** (1.6 mm over the 100 mm tier) — unchanged, out of scope.
5. Assembly remains blocked: **373 / 373 BOM rows have no MPN**, no assembly drawing, no ATE test
   points. Fiducials were the only one of those four blockers a board edit could close.

## 10. Evidence inventory (`evidence/fab-cs-fid-real/`)

```
export_geom.py confirm_sites.py scan_sites.py local_scan.py site_probe.py courtyard_check.py
measure_gaps.py measure_gaps_pcb.py place_fiducials.py place_v2.py place_final.py
test_local.py islands.py filldiff2.py fill_cmp_commit.py board_census.py
drc_diff.py validate.py pkg_compare2.py verify_committed_manifest.py
post_commit_census.py make_manifest.py export_pkg.ps1 export.log.txt
drc_before.json drc_repo_after.json drc_final.json drc_committed.json drc_150.json
gaps_repo.json gaps_committed.json gaps_final.json
geom_before.json geom_hide.json geom_trial.json
validate.json package/ (the re-exported package) board_backup/ post_commit/ proj_full/ proj_test/
sites.json sites_confirmed.json local_sites.json local_sites_tight.json
board_HEAD.kicad_pcb commit-msg.txt REPORT.md
```

Board backup of the pre-edit state: `board_backup/Code-SDR-V2.kicad_pcb` (`309414D2…`), and in git at
`1a20bd6:hardware/v2/Code-SDR-V2.kicad_pcb`.