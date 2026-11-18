> **HOTFIX 1 appended (2026-11-14). This original text is retained verbatim for the record; the
> six places marked `⟵ SUPERSEDED` below are corrected in the appended section
> [HOTFIX 1](#hotfix-1--2026-11-14--stackup-arithmetic-and-impedance-wording): checklist lines 20,
> 21 and 23, the tallies table, §5's Code-SDR rank 2, and §8 item 1. Everything not marked stands
> as written (it was not part of the rejection).
# Pre-fab readiness checklist — drone-arm rev_b and Code-SDR V2

Author: fab-readiness specialist (swarm item). Date: 2026-11-14.
Scope: `repos/drone-arm/hardware/main/rev_b/` and `repos/Code-SDR/hardware/v2/`.
Everything below is measured on the working tree at branch `work/2026-11-11`; no repo file was
modified, nothing was committed, and no branch was checked out.

## 0. Method and tooling

| Item | Value |
|---|---|
| KiCad CLI | `C:/Program Files/KiCad/9.0/bin/kicad-cli.exe` (reports 9.0.7) |
| KiCad Python | `C:/Program Files/KiCad/9.0/bin/python.exe` |
| DRC invocation | `kicad-cli pcb drc --format json --severity-all --schematic-parity --all-track-errors --units mm` |
| Gerber geometry | custom gerber extent parser (`scripts/fabext.py`) over `%FSLAX46Y46*%` / `%MOMM*%` |
| Board geometry | `pcbnew.LoadBoard(...).GetBoardEdgesBoundingBox()` |

`--severity-all` is deliberate: it overrides project "ignore" severities, so it shows what the
project rules actually flag rather than what the GUI hides. Neither project sets a
clearance/shorting severity to `ignore` (verified: only 5 courtyard/footprint-filter rules are
ignored in each `.kicad_pro`), so these counts are the real rule results.

### Which board file is "the board"?

This matters more than any single checklist line, because both trees ship many parallel board
files and only one of them is clean.

**drone-arm rev_b — `hardware/main/rev_b/main_rev_b.kicad_pcb`** (last edited `a6274e5`,
2026-11-03) is the canonical board: it is the one filename that reproduces the agreed
0 violations / 0 unconnected / 191 parity result. The neighbouring `main_rev_b_completed.kicad_pcb`
does **not** — same nominal board, radically different DRC. Of the five variants present, I ran DRC
on two (the canonical one and `main_rev_b_completed`); the other three are marked "not run" below
rather than guessed at.

| Board file | Edge bbox (mm) | Footprints | DRC violations | Unconnected | Parity |
|---|---|---:|---:|---:|---:|
| **main_rev_b.kicad_pcb** (canonical) | **140.150 × 100.150** | **165** | **0** | **0** | **191** |
| main_rev_b_completed.kicad_pcb | 140.150 × 100.150 | 165 | 168 (all error) | 13 | 0 |
| main_rev_b_shortfix.kicad_pcb | 140.150 × 100.150 | 165 | not run | | |
| main_rev_b_routed_iter2_filled.kicad_pcb | 140.150 × 100.150 | 165 | not run | | |
| main_rev_b_final.kicad_pcb | 130.050 × 74.570 | 168 | not run | | |

The 168-error/13-unconnected result on `main_rev_b_completed.kicad_pcb` is not noise: its
breakdown is 109 clearance, 28 hole_clearance, **26 shorting_items**, 3 solder_mask_bridge,
2 tracks_crossing (`evidence/fab-readiness/da_drc.json`). Anyone who picks the wrong filename
from that directory ships a shorted board. This is a release-hygiene finding in its own right.

**Code-SDR V2 — `hardware/v2/Code-SDR-V2.kicad_pcb`**, 101.700 × 101.700 mm edge bbox, 4 copper
layers, 373 footprints, 261 nets, 1.6 mm, title-block rev `2.1`.

### Severity ranking rule used throughout

- **RIP-UP** — requires a design/copper change (reroute, add copper, fix a net). Artifacts must be
  re-validated afterwards.
- **RE-SPIN** — design unchanged; artifacts must be regenerated or re-exported.
- **DOC** — no artifact changes at all; paperwork/specification only.

---

## 1. THE HEADLINE FINDING (drone-arm): the only gerber package belongs to the previous board

`hardware/main/pcb-gerbers-1/` is the **rev_a** board, not rev_b. Chain of proof:

1. `main-job.gbrjob`: `"ProjectId": {"Name": "main", ... "Revision": "rev?"}`,
   `"Size": {"X": 75.05, "Y": 50.05}`, `CreationDate 2026-03-31T22:03:16+05:30`.
2. `hardware/main/main.kicad_pcb` (rev_a) carries a single clean Edge_Cuts rectangle
   (0,0)→(75.500, 50.500) with 0.050 mm line width, so its bbox is **75.550 × 50.550 mm**; it has
   112 footprints, **0 NPTH pads**, 90 PTH pads and 281 vias. Note rev_a's own profile is a single
   rectangle — the sheet-frame contamination in §1.2 came from the plot settings at export time,
   not from the design.
3. rev_b is **140.150 × 100.150 mm** with **165 footprints** and 6 NPTH pads, drawn as a clean
   (0,0)→(140,100) rectangle. No dimension in the job file or the gerbers is anywhere near it.
4. `main-NPTH.drl` contains **zero holes** (header, `G05`, `M30`, nothing between). That is only
   correct for a board with no NPTH pads — which is rev_a, not rev_b (which needs 6 NPTH).

The job file's declared 75.05 × 50.05 mm sits in the 75 mm size class, not the 140 mm class; it is
0.45 mm smaller than rev_a's drawn rectangle, a small inconsistency I record rather than explain.
It cannot belong to rev_b under any reading.

**Consequence:** no gerber exists for any rev_b variant. Nothing dated after 2026-03-31 exists in
the drone-arm tree at all. Building from the current package produces rev_a hardware: 112
footprints against rev_b's 165, i.e. **53 components short**, and with no NPTH drills at all — so
the four M4 mounting holes needed to bolt the board to the airframe do not exist in the package.

### Second finding in the same package: the drawing-sheet frame is plotted into every layer

All eleven gerbers have **identical** extents, which is the signature of a plotted page border:

```
layer                      Xmin     Xmax     Ymin      Ymax      W(mm)     H(mm)
main-Edge_Cuts.gbr       -1.395  287.002  -200.007   4.231    288.397   204.238
main-F_Cu.gbr            -1.395  287.002  -200.007   4.231    288.397   204.238
main-In1_Cu.gbr  ... (all 11 identical)
```

`main-Edge_Cuts.gbr` line 40 onward: `X10000000Y-10000000D02*` then `X287002200Y-10000000D01*` —
that is the A4 frame corner at (10, 10) mm running to (287.002, 10) mm, i.e. the KiCad drawing
sheet border, not board copper. There is additionally a 108 × 32 mm rectangle at
X177.002–285.002 / Y166.007–198.007 mm. A fab house reading this profile has a 288.4 × 204.2 mm
outline with an internal rectangle, against a 140 × 100 mm board.

---

## 2. Full checklist, pass/fail per line

34 lines. `PASS` = verified good for a fab submission today. `FAIL` = present but defective.
`MISSING` = does not exist and must be produced.

| # | Checklist line | drone-arm rev_b | Code-SDR V2 | Evidence |
|---:|---|---|---|---|
| **A. Artifact presence, completeness, freshness** ||||
| 1 | Gerbers exist for the exact revision to be built | **FAIL** — only package is rev_a | **MISSING** — none in repo | DA: gbrjob Size 75.05×50.05 + rev_a bbox 75.55×50.55. CS: `ls` of whole repo, no `.gbr` |
| 2 | Gerber layer set complete and mutually consistent | **PASS** (scoped to rev_a): 11 gbr = 4 Cu, 2 mask, 2 silk, 2 paste, 1 profile + 2 drill + job | **MISSING** | `pcb-gerbers-1/` listing; gbrjob `FilesAttributes` declares exactly those 11 |
| 3 | Gerbers match the current design | **FAIL** — the package is rev_a, so by construction no layer can match rev_b (a byte comparison against a fresh rev_b export is moot rather than merely negative) | **MISSING** | revision identity proven in §1 from gbrjob `Size` + rev_a bbox + empty NPTH; package 2026-03-31 vs board commit 2026-11-03 `a6274e5` |
| 4 | Package age vs last design edit | **FAIL** — ~7 months stale; also stale vs rev_a itself | **MISSING** | gbrjob `CreationDate 2026-03-31T22:03:16`; `git log -1` = 2026-11-03 |
| 5 | Gerber job file present and self-describing | **FAIL** — present but `Finish: "None"`, `Revision: "rev?"`, and stackup Dk 4.5 / 0.1 mm prepreg contradicts rev_b's Dk 4.2 / 0.2 mm prepreg | **MISSING** | `main-job.gbrjob` `GeneralSpecs`, `MaterialStackup`; rev_b stackup lines 39–98 of the `.kicad_pcb` |
| 6 | Edge_Cuts contains the board outline only | **FAIL** — A4 sheet frame present, extents 288.397 × 204.238 mm | **PASS** — 4 Edge_Cuts primitives, closed, bbox 101.700 | `scripts/fabext.py`; `main-Edge_Cuts.gbr` L36–L45 |
| 7 | Outline dimensions and tolerance defined | **FAIL** — no correct outline; no tolerance note | **PASS** — 101.700 × 101.700 bbox; 101.60 profile path vs 101.70 bbox = the 0.1 mm cut line width, consistent | `GetBoardEdgesBoundingBox()` |
| 8 | Drill: PTH file complete and matching design | **PASS for rev_a only** — 368 hits, 8 tools 0.200–1.150 mm | **MISSING** | `main-PTH.drl` (404 lines, 368 `X…Y…`); rev_a = 90 PTH pads + 281 vias |
| 9 | Drill: NPTH / mounting holes | **FAIL** — `main-NPTH.drl` has **0 holes**; rev_b needs 6 NPTH incl. H1–H4 M4 | **FAIL** — only 2 NPTH pads on the whole board, no mounting-hole pattern for an enclosure | `main-NPTH.drl` verbatim; `pcbnew` NPTH count DA 6 / CS 2 |
| 10 | Tooling holes (fab/assembly) | **MISSING** | **MISSING** | 0 footprints or pads matching tooling/`Hole` in either board |
| 11 | Pick-and-place / centroid `.pos` | **MISSING** — no `.pos`, `.csv` centroid, or `report` export anywhere | **MISSING** — `export_release.ps1:89` *defines* the pos export, but no artifact is committed | recursive `-Include *.pos` over both trees returns nothing |
| 12 | Assembly drawing (top/bottom, refdes, polarity) | **MISSING** — only motor-part PDFs exist in `motor_release/`, unrelated to the PCB | **MISSING** | recursive `-Include *.pdf` |
| 13 | Fiducials (global panel + local fine-pitch) | **FAIL** — 0 fiducials; 0.4 mm-pitch QFN-80 and 0.5 mm WQFN-40 parts on board | **FAIL** — 0 fiducials across all 373 footprints, including QFN and U.FL parts | refdes scan: `^FID` = 0 on both; footprint-name scan for `iducial` = 0; `revb.pretty/WQFN-40-EP_6x6_P0.5.kicad_mod` |
| 14 | Panelisation (array, rails, breakaway, spacing) | **MISSING** | **MISSING** | no panel/fab drawing in either tree |
| 15 | Test points / ICT or bed-of-nails access | **FAIL** — 0 test points | **FAIL** — 0 test points | `^TP` = 0 on both |
| **B. Electrical and CAD integrity** ||||
| 16 | DRC clean at project rules | **PASS** — 0 violations, 0 unconnected (canonical file only) | **PASS on errors, FAIL on hygiene** — 0 errors, 222 warnings: 199 `lib_footprint_mismatch`, 13 `via_dangling`, 10 `track_dangling` | `da_drc_newest.json`; `cs_drc_parity.json` |
| 17 | Schematic parity clean | **FAIL — 191** = 161 `footprint_symbol_mismatch`, 20 `net_conflict`, 6 `missing_footprint`, 4 `extra_footprint` | **FAIL — 4** `net_conflict` | see §3 for the 191 breakdown |
| 18 | Netlist parity / connectivity | **PASS** — 0 unconnected items | **PASS** — 0 unconnected items | both DRC jsons |
| 19 | Return-path / reference-plane integrity | **UNVERIFIED** — no tool, no plane-integrity receipt in the tree | **FAIL** — `tools/validate_route.py` exits 1 | see §4 |
| 20 | Controlled-impedance geometry checked against a net-class table | **MISSING** — no width/gap table for the 915 MHz RF50 or USB pair | **FAIL** — no widths/gaps table; `FABRICATOR_IMPEDANCE_NOTE.md` calls the 0.23 mm RF50 width "a nominal design input, not proof of impedance" ⟵ **PARTLY SUPERSEDED — a field solve now exists, see HOTFIX 1.5** | `FABRICATOR_IMPEDANCE_NOTE.md` |
| **C. Manufacturing specification** ||||
| 21 | Stackup declared in the design file | **PASS** — sums to exactly 1.60 mm | **FAIL** — sums to 1.62 mm vs declared 1.60 mm | DA: 0.01+0.035+0.20+0.035+1.04+0.035+0.20+0.035+0.01. CS: …0.13 + 1.20 + 0.13… = 1.62. ⟵ **SUPERSEDED — both verdicts wrong; see HOTFIX 1.2/1.3** |
| 22 | Fab-facing stackup receipt (pressed thickness, resin system, tolerance) | **MISSING** | **MISSING** — `STACKUP_DRAWING.md` explicitly asks the fab to *return* a stack; none on file | `STACKUP_DRAWING.md` last paragraph |
| 23 | Controlled-impedance spec + written fab approval + coupons | **FAIL** — gbrjob says `ImpedanceControlled: true` but no target Ω, no coupon, no approval | **FAIL** — note is well-written but demands field-solve + approval that does not exist ⟵ **SUPERSEDED — solve exists, approval/coupons do not; see HOTFIX 1.5** | `FABRICATOR_IMPEDANCE_NOTE.md`, "Required fabricator action" |
| 24 | Surface finish specified | **FAIL** — `Finish: "None"` in the package, though rev_b declares ENIG | **PASS** — `(copper_finish "ENIG")` in file and in all three docs | gbrjob `GeneralSpecs`; `.kicad_pcb` L103 |
| 25 | Copper weight | **PASS** — 0.035 mm = 1 oz all layers | **PASS** — 0.035 mm = 1 oz all layers | stackup blocks |
| 26 | Mask / silk spec | **PASS** — mask 0.010 mm, `solder_mask_min_width 0.05`, both silk layers plotted, mask polarity Negative (correct) | **PASS** — same, plus `allow_soldermask_bridges_in_footprints no` | gbrjob `FilePolarity`; `.kicad_pcb` setup |
| 27 | Thickness and layer count stated | **PASS** — 4 Cu, 1.6 mm | **PASS** — 4 Cu, 1.6 mm | gbrjob `LayerNumber`/`BoardThickness`; board settings |
| 28 | Revision marking resolved | **FAIL** — title block revision empty, gbrjob `"rev?"`, no silk revision string | **PASS** — title block `2.1` (no gerber exists yet to carry it) | `GetTitleBlock().GetRevision()` |
| 29 | IPC-D-356 bare-board netlist | **MISSING** | **MISSING** — `export_release.ps1:97` calls `pcb export ipcd356`, no artifact committed | no `.ipc`/`.d356` file |
| **D. Assembly data** ||||
| 30 | BOM exists for the board | **PASS** — `docs/hardware/REV_B_BOM.csv`, 172 lines | **MISSING** — only `redesign/V1_BOM.csv`, a different board | `REV_B_BOM.csv` |
| 31 | BOM ↔ PCB consistency | **PASS** — 161 references, PCB has 165; the 4 extra are exactly H1–H4 (mounting holes); 0 BOM refs absent from the PCB | **UNVERIFIED** — no BOM to compare | `scripts/bomcheck.py` |
| 32 | MPN complete on every line | **PASS** — 0 of 172 lines blank or placeholder | **MISSING** | `Import-Csv` + regex |
| 33 | DNP handling | **FAIL** — no DNP column, and 0 DNP footprints in the board, so DNP is simply not modelled | **PASS** — 2 DNP (R153, R156); exporter uses `--exclude-dnp` | `.kicad_pcb` DNP scan; `export_release.ps1:87,89` |
| 34 | Assembly notes / special instructions | **MISSING** | **MISSING** — `FIRST_ARTICLE_VALIDATION.md` is an electrical test plan, not assembly | `FIRST_ARTICLE_VALIDATION.md` |

**Tallies**

| | PASS | FAIL | MISSING | UNVERIFIED |
|---|---:|---:|---:|---:|
| drone-arm rev_b — ⟵ **SUPERSEDED, see HOTFIX 1.4** | ~~11~~ 10 | ~~14~~ 15 | 8 | 1 |
| Code-SDR V2 — ⟵ **SUPERSEDED, see HOTFIX 1.4** | ~~10~~ 11 | ~~8~~ 7 | 15 | 1 |

---

## 3. drone-arm: the 191 parity issues, and which 9 are real

The raw counts (`da_drc_newest.json`) are 161 `footprint_symbol_mismatch`, 20 `net_conflict`,
6 `missing_footprint`, 4 `extra_footprint`.

- The 161 `footprint_symbol_mismatch` (161 of the board's 165 footprints) are cosmetic-to-serious in
  one specific way: they mean the footprint has been detached from its library symbol mapping
  (e.g. `C_0402_1005Metric` "doesn't match footprint given by symbol
  (`Capacitor_SMD:C_0402_1005Metric`)"). The library link string is broken, so a future
  Forward-Annotate will not be reproducible. Ranked **DOC/RE-SPIN**, not rip-up: copper is unaffected.
- 6 `missing_footprint`: **J60–J65, all six ESC PWM connectors.** This is real copper that does not
  exist. The flight controller has no connector for the six ESC signal wires. **RIP-UP.**
- 4 `extra_footprint` (no reference designators emitted by kicad-cli) — must be identified by hand
  before any re-spin. Ranked **RIP-UP pending identification**.
- 20 `net_conflict`, split as:
  - **6 real, high severity:** `unconnected-(U10-GPIO34-Pad43)` vs schematic `PWM_ESC1`, and
    likewise GPIO35–39 / pads 44–48 vs `PWM_ESC2…PWM_ESC6`. The MCU pads carry auto-generated
    "unconnected-" netnames while the schematic expects the six ESC PWM nets. **RIP-UP** — it is the
    electronic twin of the missing J60–J65.
  - **3 real, highest severity:** the CAN pair is swapped.

    ```
    Pad net (/CANH)             doesn't match net given by schematic (/CAN interface/U50_CANL)
    Pad net (/CAN interface/U50_CANL) doesn't match net given by schematic (/CANL)
    Pad net (/CANL)             doesn't match net given by schematic (/CANH)
    ```

    That is an H/L inversion across the common-mode choke (FL50) / transceiver: the netlist maps the
    transceiver's H pin onto what the schematic calls L and vice versa. CAN differential is nominally
    H/L-symmetric, so this may still chatter on a bench, but the terminator split, the choke winding
    polarity and every downstream node label are not what was designed, and no bus conformance test
    can pass on a mislabelled pair. On an assembled board it is only fixable with a soldering iron on
    0402 parts. **RIP-UP.**
  - **11 cosmetic:** differences only in `/` vs `{slash}` escaping of auto-generated unconnected
    netnames (GPIO40–47/ADC0–7, U51 CLKO/SOF, INT1/GPIO1, INT0/GPIO0/XSTBY). **DOC.**

So: **9 real parity defects** (6 PWM + 3 CAN), not 6 as previously recorded. The 3 extra are the
CAN swap entries, which I treat as one defect expressed three times.

## 4. Code-SDR: the CS-G3 return-path failure, reproduced

```
PS> python tools/validate_route.py     (cwd = hardware/v2)
  File "...\tools\validate_route.py", line 109, in main
AssertionError: Signal routing exists on solid In1/In2 ground plane:
  +1V2_CORE, +3V3_ANA, +3V3_DIG, ADC_D3 … ADC_VREF, ADF_CPOUT, ADF_DATA, ADF_LE, ADF_LOCK,
  ADL_DETO, ADL_VSET, DSA_CLK, DSA_LE, FB_1V2, FB_ANA, FPGA_AUX_2V5, … GND, HSW_V2,
  IF_HIGH_N, IF_HIGH_P, … LO2_N, LO2_P, MDC, MDIO, MDI_A_N, MDI_A_P, MDI_B_N, MDI_D_N, …
  RGMII_RXD0 … RGMII_TX_EN_FPGA, REF_100M_ADC, SWD_CLK, SWD_IO, SYNTH_SCK, SYNTH_SDI
EXIT=1
```

84 nets, including the IF differential pair, LO2, the 100 MHz ADC reference, all RGMII, and MDI.
The project's own contract says these must not break the reference plane. The board fails its own
tool. This is the single strongest reason the board is not fabricable as-is.

**What the check actually enforces, stated precisely so the finding is not overstated.**
`tools/validate_route.py` lines 78–80:

```python
if item.GetLayer() in (pcbnew.In1_Cu, pcbnew.In2_Cu):
    forbidden_plane_items.append(net_name)
```

This is an absolute layer rule: *any* track item on In1 or In2 is a violation, whatever its net.
That is why `GND` appears in the list — a GND track on the GND plane is not electrically harmful,
but it does violate the stated "planes carry no routing" contract and it punches voids in the very
reference the other 83 nets depend on. So the honest reading is: 84 nets are in breach of the
project's own plane contract, of which the 83 non-GND entries (IF_HIGH_P/N, LO2_P/N, REF_100M_ADC,
RGMII, MDI, 3V3 rails) are the ones with a real signal-integrity cost. The verdict does not change:
the board fails the gate its own authors wrote.

Note also that `--severity-all` DRC alone would have missed this: DRC reports 0 errors and 0
unconnected on this board. Only the project's bespoke checker catches it.

## 5. Ranking of every FAIL

RIP-UP items are ordered by cost to fix after fab.

### drone-arm rev_b — all 14 FAILs, plus the 8 MISSING lines grouped at the end

| Rank | Line | FAIL | Class | Why this class |
|---:|---|---|---|---|
| 1 | 17 | J60–J65 absent; 6 ESC PWM nets unconnected on U10 pads 43–48 | **RIP-UP** | New connectors + 6 routed nets + connector footprints; then re-validate |
| 2 | 17 | CAN H/L swapped across FL50/U50 (3 parity entries) | **RIP-UP** | Net/pin re-assignment on an assembled board is a rework job, not a re-export |
| 3 | 1, 3, 4 | No rev_b gerber exists; the only package is rev_a | **RE-SPIN** | Design is unchanged by fixing this; export correct rev_b |
| 4 | 6, 7 | Sheet frame plotted into all 11 layers, wrong outline extents | **RE-SPIN** | Uncheck "plot border and title block", re-export; no copper change |
| 5 | 5 | gbrjob `Finish: "None"`, `Revision: "rev?"`, stale Dk/prepreg values | **RE-SPIN** | Regenerated by the same re-export |
| 6 | 9 | NPTH drill is empty; rev_b's 6 NPTH (H1–H4 M4 + 2) undrilled | **RE-SPIN** | Comes right with a correct rev_b drill export |
| 7 | 13 | 0 fiducials | **RIP-UP** | Adding fiducials is a copper + mask-opening edit; layout-only, no reroute |
| 8 | 23 | Impedance control claimed but unspecified | **DOC** | A spec document + fab approval changes no copper |
| 9 | 24 | Finish None in the package | **RE-SPIN** | Folded into the re-export |
| 10 | 28 | No revision marking | **DOC** | Silk/marking decision, plus title-block entry |
| 11 | 33 | No DNP column, DNP not modelled | **DOC** | BOM column |
| 12 | 15 | 0 test points | **RIP-UP (deferrable)** | Adding probe pads is copper; can be waived for a first hand-built article |
| 13 | 10, 11, 12, 14, 20, 22, 29, 34 | Tooling holes, .pos, assembly drawing, panelisation, net-class table, stackup receipt, IPC-D-356, assembly notes | **MISSING → RE-SPIN** (.pos, IPC-D-356) / **DOC** (the rest) | |

### Code-SDR V2 — all 8 FAILs, plus the 15 MISSING lines grouped at the end

| Rank | Line | FAIL | Class | Why this class |
|---:|---|---|---|---|
| 1 | 19 | 84 nets routed on/through solid In1 GND and In2 power planes (`validate_route.py:109`) | **RIP-UP** | Plane re-stitch + reroute of 84 nets incl. IF/RGMII/MDI. This is a layout redesign, not an export |
| 2 | 21, 23 | Stackup sums to 1.62 not 1.60 ⟵ **SUPERSEDED, 1.60 over copper**; impedance never field-solved or approved ⟵ **SUPERSEDED, solved 52.6/49.4 Ω** | **DOC** for the number, **RIP-UP** if the approved stack moves the 0.23 mm RF50 width | Cannot be closed without the fab's stack; the width may change → RF50 reroute |
| 3 | 17 | 4 parity `net_conflict`: U5–U8 `CT` pad 5 has no net on the PCB but a net in the schematic | **RIP-UP (small)** | Transformer/balun centre taps must be tied or explicitly no-connect; affects RF balance |
| 4 | 16 | 199 `lib_footprint_mismatch` + 23 dangling track/via stubs | **RE-SPIN** (dangling) / **DOC** (library links) | Dangling stubs are copper; library links are metadata |
| 5 | 1, 2, 3, 4, 5, 8, 29, 30, 32 | No gerber, no drill, no job file, no BOM, no IPC-D-356 | **RE-SPIN** | `tools/export_release.ps1` already does all of it — it just has never been run to a committed artifact |
| 6 | 13 | 0 fiducials | **RIP-UP** | Copper edit |
| 7 | 9 | Only 2 NPTH, no mounting/tooling pattern | **RIP-UP** | Enclosure mounting is undecided in copper |
| 8 | 15 | 0 test points | **RIP-UP (deferrable)** | |
| 9 | 10, 11, 12, 14, 22, 34 | Tooling holes, .pos, assembly drawing, panelisation, stackup receipt, assembly notes | **DOC** / **RE-SPIN** | |

## 6. The single highest rip-up risk on each board

**drone-arm rev_b — the six ESC PWM channels do not exist as copper.**
`J60`–`J65` are missing footprints *and* U10 pads 43–48 carry auto-generated
`unconnected-(U10-GPIOxx-PadNN)` netnames instead of `PWM_ESC1…6`. A rev_b built today has no way
to command an ESC without bodge wires from a 0.4 mm-pitch QFN-80. That is a design change plus
six connector footprints plus six routes — the largest unavoidable rework on either board.
(The CAN H/L swap on FL50 is the nastiest single defect, but it is one net-pair re-assignment;
the missing PWM interface is a whole subsystem.)

**Code-SDR V2 — 84 signal nets violate the solid-plane reference contract.**
`tools/validate_route.py` exits 1 at line 109 naming IF_HIGH_P/N, LO2_P/N, REF_100M_ADC, all
RGMII, MDI_A/B/D, SWD and both 3V3 rails as routed on solid In1/In2. Current returns for the
100 MHz ADC reference and the IF chain have no defined path, and In2 is a *split* power
plane, so B.Cu RF structures have no solid reference either. Fixing it means plane surgery plus
rerouting 84 nets — everything else on this board (missing gerbers, missing BOM, fiducials) is
mechanical by comparison.

## 7. Both boards, one-line verdicts

- **drone-arm rev_b: do not send out.** Not because of the design's DRC (0/0 is real on the
  canonical file) but because there is no rev_b gerber, and the only package is a mis-plotted A4
  sheet frame of the previous board. Order of work: fix the 9 parity defects → re-export with
  border/title-block plotting off → add fiducials → produce .pos, BOM DNP column, stackup and
  impedance receipts.
- **Code-SDR V2: do not send out.** Its own routing contract fails, no manufacturing artifact has
  ever been committed despite a working release script, and the electrically-clean DRC hides 199
  library-link mismatches. Order of work: fix the In1/In2 plane violation → re-run
  `export_release.ps1` → add fiducials and mountings → generate BOM, .pos, assembly drawing.

Both repos contain a self-authored "not ready" statement that agrees with these findings:
`drone-arm/docs/acceptance/issue21/main-board-drc-9.0.2-f653d8c.md` — *"The board remains
incomplete and is not fabrication-ready"* (7 violations, 42 unconnected on `main_rev_b.kicad_pcb`
under KiCad 9.0.2); and `Code-SDR/hardware/v2/WRAP_UP_20260907.md` — *"Work in progress, not a
fabrication release. … Do not manufacture from the root project or from the recovery candidates."*
Note the CS board hash no longer matches that doc's checkpoint
(`309414d2…` vs documented `30b64988…`), so the doc is stale — but no newer readiness statement
exists to replace it.

## 8. UNVERIFIED — needs the fab's own DFM, or a capability absent here

1. ⟵ **SUPERSEDED by HOTFIX 1.5 (this item is withdrawn and replaced):** **Every impedance value.** Both boards declare impedance control and neither has a solved
   geometry. DA has no RF50 width table at all; CS documents 0.23 mm as a *nominal input*. Any
   Ω figure would be fabricated — not reported. Needs the fab's field solve and TDR coupons.
2. **Minimum annular ring, drill-to-copper, and copper-to-edge after the fab's etch compensation.**
   Not modelled by KiCad DRC in either project. Needs fab DFM.
3. **Solder mask dam width between fine-pitch pads.** drone-arm carries a QFN-80/0.4 mm
   (parity list) and a `WQFN-40-EP_6x6_P0.5` footprint; Code-SDR carries fine-pitch QFN and U.FL
   land patterns. Both declare `solder_mask_min_width 0.05` but only the fab can confirm the dam
   its process actually yields.
4. **DA line 19 (return-path integrity).** No plane-integrity tool exists in the drone-arm tree, and
   I did not build one. CS has a bespoke checker; DA has nothing comparable — so DA's reference-plane
   behaviour is genuinely unmeasured, not merely unrecorded.
5. **DA's 4 `extra_footprint` items.** kicad-cli emits the type without a reference designator, and
   resolving them requires a schematic-vs-board annotation diff that I did not run. They must be
   identified before a re-spin.
6. **Whether DA's 161 library-link mismatches map to real footprint geometry changes.** Byte-diffing
   161 footprints against `revb.pretty` and the KiCad stock libraries was out of scope.
7. **Panelisation cost/feasibility** for either board — no fab quote or panel drawing exists.
8. **Bare-board electrical test coverage** — no IPC-D-356 exists to price it.

## 9. Evidence index (this directory)

| File | Contents |
|---|---|
| `REPORT.md` | this report |
| `da_drc_newest.json` | canonical DA DRC: 0 violations / 0 unconnected / 191 parity |
| `da_drc.json` | DA on `main_rev_b_completed.kicad_pcb`: 168 errors incl. 26 shorts / 13 unconnected |
| `cs_drc.json` | CS DRC, no parity flag: 222 warnings / 0 unconnected |
| `cs_drc_parity.json` | CS DRC with parity: +4 `net_conflict` |
| `gerber_extents.txt` | per-layer extents of the drone-arm package (the 288.40 × 204.24 proof) |
| `bom_check.txt` | BOM↔PCB reference reconciliation |
| `validate_route_cs.txt` | CS-G3 failure, full net list |

Helper scripts live in `E:/engineering-portfolio-audit/scripts/` (`fabext.py`, `dabbox.py`,
`fabfeat3.py`, `drcsum.py`, `parity.py`, `bomcheck.py`, `csbbox.py`, `csparity.py`, `missfp.py`,
`reva.py`). All are re-runnable; none writes into a repo.


---

## HOTFIX 1 — 2026-11-14 — stackup arithmetic and impedance wording

Author: hotfix specialist. Scope unchanged: read-only on both repos at branch `work/2026-11-11`;
no commit, no push, no `audit/*` branch. Every write is under `evidence/hf-fab-readiness/`.

### 1.1 The rejection, verbatim

> "The drone-arm PASS line asserting the stackup sums to 1.60 double-counts two 0.010 mm mask
> layers, because copper plus dielectric is 1.58; and the same line FAILs Code-SDR at 1.62.
> Also the claim that impedance was never solved contradicts two FD reports that did solve it."

Both defects are real. Nothing below restates a rejected number as true.

### 1.2 Stackup arithmetic, redone from the two board files

Read directly out of each `.kicad_pcb` stackup block, not copied from the earlier stackup report
(`stackup_arith.json`, script `stackup_arith.py`):

| Row | drone-arm rev_b | Code-SDR V2 |
|---|---|---|
| declared board thickness, `(general (thickness …))` | 1.60 | 1.60 |
| copper, 4 × 0.035 | 0.140 | 0.140 |
| dielectrics | 0.200 + 1.040 + 0.200 = **1.440** | 0.130 + 1.200 + 0.130 = **1.460** |
| **copper + dielectric = the board** | **1.580** | **1.600** |
| solder mask, 2 × 0.010 | 0.020 | 0.020 |
| every stackup row including mask | 1.600 | 1.620 |
| Δ vs 1.60, over copper | **−0.020 (−1.25 %)** | **0.000** |
| Δ vs 1.60, including mask | 0.000 | +0.020 (+1.25 %) |

**Convention adopted: over-copper — solder mask is not part of the 1.6 mm board thickness.**
The ordered 1.6 mm is a lamination-press output, controlled by the prepreg/core build and measured
across the finished copper; mask is applied after drilling and plating and its cured thickness is a
process outcome, not a build input. On both boards the 0.010 mm mask rows are KiCad's default
placeholder value, not a fabricator-committed figure. The mask-inclusive sums are stated above so
the choice is auditable rather than assumed; if a fabricator's stackup receipt counts mask
differently, that receipt governs line 22, not the arithmetic here. (The IPC-6012 clause text is
paywalled and is **not** quoted — this is a stated manufacturing convention, not a cited norm.)

**A second, separate error in the earlier evidence.** `evidence/da-stackup/stackup_verify.json`
reports `kicad_reported_finished_thickness_mm: 1.6` and treats KiCad's own report as a check on the
1.600 sum. It is not one: `pcbnew.GetDesignSettings().GetBoardThickness()` returns the stored
`(general (thickness 1.6))` field. Probe in `stackup_arith.py`: set both mask rows to 0.100 mm in a
copy of the drone-arm board, reload with `pcbnew` → still reports 1.600
(`stackup_arith.json` → `kicad_probe`, `thickness_changed: false`). KiCad never sums the stackup, so
that "verification" was circular. The arithmetic in the table above is the actual check.

### 1.3 Checklist line 21, both boards, one convention

| Line 21 — stackup declared in the design file | drone-arm rev_b | Code-SDR V2 |
|---|---|---|
| verdict, identical convention | **FAIL — 0.020 mm short** | **PASS — exact** |

Replacement cell text for the checklist (drop-in, both boards scored the same way):

- drone-arm rev_b: `**FAIL** — 1.580 mm of copper + dielectric (0.140 + 1.440) against a declared
  1.60, i.e. 0.020 mm short; it reads 1.600 only if the two 0.010 mm mask rows are added.`
- Code-SDR V2: `**PASS** — 1.600 mm of copper + dielectric (0.140 + 1.460) against a declared 1.60;
  its 1.620 counts the two 0.010 mm mask rows, which are not board thickness.`

**Reading of each verdict:**

- **drone-arm rev_b — FAIL.** The copper + dielectric build is 1.580 mm; the file declares 1.60.
  It reaches 1.600 only by adding the two 0.010 mm mask rows. In practice 1.25 % sits well inside a
  normal ±10 % laminate tolerance, so no fabricator will reject the board — but the design's own
  numbers do not reproduce its own declaration, which is exactly what line 21 asks. Fix is
  documentary (declare the pressed build as 1.58 with mask over it, or move 0.020 mm of core/prepreg
  into the build so the copper-to-copper stack closes 1.60); no copper change. Class **DOC**.
- **Code-SDR V2 — PASS.** Copper + dielectric is 1.600 mm against a declared 1.60. Its 1.620 is the
  same quantity with the two 0.010 mm mask rows added — a surface coating, not board thickness. The
  original FAIL was scored on the mask-inclusive sum.

Be exact about what the original did wrong, since the rejection's phrasing is loose on this point:
the original used **one** convention for both boards (all rows, mask included). It was internally
consistent but used the wrong convention, and the consequence was that the board 0.020 mm short
passed while the board that is exactly right failed. Under the corrected convention the two
verdicts invert. That inversion is the whole content of this hotfix, so it is stated, not softened.

### 1.4 Tallies after the correction

| | PASS | FAIL | MISSING | UNVERIFIED |
|---|---:|---:|---:|---:|
| drone-arm rev_b | 10 *(was 11)* | 15 *(was 14)* | 8 | 1 |
| Code-SDR V2 | 11 *(was 10)* | 7 *(was 8)* | 15 | 1 |

Only line 21 moved on either board; both totals still sum to 34. The ranked view in §5 gains one
**DOC** entry (drone-arm line 21, beside its lines 23 and 28) and loses the stackup half of
Code-SDR's rank 2 — see 1.6.

### 1.5 The impedance claim, corrected

**Withdrawn**, because false: "neither has a solved geometry" (§8 item 1), "demands field-solve +
approval that does not exist" (line 23), "impedance never field-solved or approved" (§5 rank 2).
Two 2D finite-difference cross-section solves exist on disk and both are re-runnable:

| | drone-arm rev_b | Code-SDR V2 |
|---|---|---|
| evidence | `evidence/da-em-field/` (`fd_results.json`, `REPORT.md`) | `evidence/cs-em-field/` (`fd_solve.json`, `02_fd_solve.py`) |
| method | own 2D FD quasi-static Laplace solve (numpy/scipy) — a solve, **not a measurement** | own 2D FD Laplace solve, ∇·(ε∇φ)=0, Z0 = 1/(c·√(C_air·C_die)) — a solve, **not a measurement** |
| geometry solved | 0.35 mm F.Cu, t 0.035, εr 4.2, h 0.200 (L1–L2), over the board's real In1 = /3V3 | 0.23 mm F.Cu, t 0.035, εr 4.2, h 0.130 (L1–L2), mask 0.010 / εr 3.5 |
| **Z0** | **52.6 Ω** (51.7–54.4 Ω across four grid refinements) on a solid plane | **49.4 Ω** (49.43 with mask, 52.57 with no mask), ±0.2 Ω numerical |
| ε_eff | 3.33 | 3.29 |
| behaviour that is the actual finding | 118.1 Ω in a full void, 65.0–117.6 Ω partial → 2.25× spread over the 102 mm run | 0.2275 mm would be 50.0 Ω; mask εr ±0.5 moves Z0 ∓0.47 Ω |
| closed-form cross-check | Hammerstad/MLine 2.7 % away (51.2 Ω at h 0.200) | skrf 1.6 % at t→0, 5.6 % at t 0.035 |

**Corrected statement of what is missing — a measurement and a receipt, not a solve:**

1. **No impedance has been measured.** No VNA on a finished coupon, no TDR on a test line, no
   fabricator-issued impedance report. Every Ω figure above is solver output, and solver output is
   not evidence that the etched board lands at 50 Ω.
2. **No written fabricator approval of either stackup exists** (line 22), and no impedance coupons
   are ordered (line 23).
3. **Scope limit of the solves, stated plainly:** each covers *one* width — the width its RF net
   already uses (DA 0.35 mm, CS 0.23 mm). Neither board has a solved net-class table; the drone-arm
   USB pair has no solve at all; the drone-arm number is a cross-section value whose along-run
   behaviour depends on the 11.14 % void fraction already measured, and that spread is modelled,
   not measured.

Re-scored lines:

- **Line 23 — FAIL, for the right reason.** The field solve it asked for now exists (52.6 Ω DA /
  49.4 Ω CS); the written fab approval, the impedance coupons and any measurement do not.
- **Line 20 — unchanged verdict (MISSING/FAIL), narrower reason.** Neither board carries a
  controlled-impedance *net-class table* (width/gap per net class). For Code-SDR the note's caveat
  that 0.23 mm is "a nominal design input, not proof of impedance" is now answered — that width
  solves to 49.4 Ω on the board's own stackup — but the table is still absent. For drone-arm the
  Z0-vs-width data now exists (`da-stackup/z0_results.json`: 0.365 mm → ~50 Ω at h 0.200) yet was
  never written back as a netclass spec, and the USB pair has none.
- **§8 item 1 — replaced by:** *impedance is solved but not measured, and not fab-approved.*

### 1.6 What this changes in §5's ranking

- **Code-SDR rank 2 splits.** The stackup half drops out (1.600 mm exact over copper). What remains
  is DOC-class receipts: fab stackup approval + coupons + measurement. **No reroute is implied** —
  49.4 Ω was solved on the board's own h 0.130 stackup, and 50 Ω would need 0.2275 mm, a 1 % width
  change. The earlier "RIP-UP if the approved stack moves the 0.23 mm RF50 width" survives only if
  the fab returns a materially different dielectric thickness.
- **drone-arm gains one DOC-class FAIL** (line 21, 0.020 mm), alongside its existing line 23 and
  line 28 DOC items.

### 1.7 Verification performed

- `stackup_arith.py` (this directory, run with `C:/Program Files/KiCad/9.0/bin/python.exe`) parses
  both boards' stackup blocks, prints §1.2's table, writes `stackup_arith.json`, and runs the
  mask-thickness probe on a *copy* of the board — no repo file is touched.
- Impedance numbers read from `da-em-field/fd_results.json` (`void_sweep[solid].Z0` = 52.6139 Ω) and
  `cs-em-field/fd_solve.json` (`nominal.Z0_with_mask` = 49.4297 Ω, `mask_sensitivity`), with each
  directory's `REPORT.md` for the method statement and cross-check. Not re-solved for this hotfix.
- Git state: none of this wrote to either repo; no commit, no checkout, no branch.

### 1.8 Still unverified after this fix

1. **Whether a given fabricator counts mask in its own "1.6 mm" quote.** I adopted over-copper and
   published both sums; that fabricator's stackup receipt (line 22) is the arbiter. Until it
   arrives, drone-arm is "0.020 mm short of its declared thickness but inside normal tolerance".
2. **Either board's actual impedance.** No coupon, no VNA, no TDR — needs hardware this workspace
   does not have. That is the remaining gap on line 23, and it cannot be closed by more computation.
3. **Whether drone-arm's 52.6 Ω survives the real void distribution.** Modelled as 65.0–118.1 Ω over
   the 11.14 % void, not measured.
4. **Full-wave confirmation.** openEMS was built in the da-em-field item but deliberately not used;
   both figures are 2D quasi-static. Agreement with a second family is closed-form (Hammerstad), off
   by 2.7 % (DA) and 5.6 % (CS at full copper thickness) — i.e. the absolute numbers carry a
   few-percent model uncertainty, larger than the ±0.2 Ω numerical error, and larger than the
   5.2 % by which 52.6 Ω sits above 50 Ω.
5. **The IPC-6012 board-thickness measurement clause text** — paywalled, not quoted; the convention
   is argued from lamination practice, not cited from the standard.

### 1.9 Evidence index (this directory)

| File | Contents |
|---|---|
| `REPORT.md` | the original (marked superseded where corrected) + this HOTFIX 1 |
| `stackup_arith.py` | re-derives both stackup sums, runs the KiCad no-auto-sum probe |
| `stackup_arith.json` | its output: per-board rows, copper/dielectric/mask sums, both deltas, probe result |
| `_mask_probe_board.kicad_pcb` | copy of the drone-arm board with both mask rows set to 0.100 mm (probe only) |
