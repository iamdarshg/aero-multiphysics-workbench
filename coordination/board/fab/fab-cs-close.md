# Code-SDR V2 — close-out: the fiducial failure, the MPN gap, the test points, and two verdicts

Unit `fab-cs-close` (wave 7) · board `repos/Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb`,
sha256 `309414D2B371C6265629352FC0AA7252AA3E3B630488849187761D24B09FF486` (5,562,840 bytes)
— byte-identical to the file `fab-cs-drc` measured, and the repo tree is clean (`git status
--porcelain` empty) both before and after this unit.

**Nothing was written into a repo.** Every board edit lives under
`evidence/fab-cs-close/_work/`, on copies. The deliverable board is
`_work/tp55/Code-SDR-V2.kicad_pcb`, sha256
`8EC5741AB66E8E3EBEDC8460D190FEF6B98467FF2D012B03E4AC03996F1DB7AD` (5,601,490 bytes):
the pour fix **and** the 18 test points, DRC **222, 0 errors, 0 unconnected, identical set**.

| question | answer |
|---|---|
| fiducial fix executed? | **yes** — global pour keepout widened 0.75 → 1.25 mm local clearance, refilled |
| gap achieved | **1.7505 mm** (was 1.2505), requirement 1.25 mm kept — *not* lowered |
| all 9 gaps measured | yes, §2, row-by-row, exact polygon distance **and** a 72-direction ring |
| DRC after | **222** — 0 new, 0 gone, 199 + 13 + 10 by type, 0 errors, 0 unconnected |
| MPN status | **58 / 373 rows determinable**, 3 series-only, 29 need an engineer, 283 commodity |
| test points | **placed, 18 sites, DRC 222** — as 0.55 mm mask apertures, land 0.45 mm |
| bare board | **ORDERABLE** |
| assembly | **NOT ready** — blocker is sourcing, not engineering |

---

## 1. The fiducial failure — what it actually was

Two separate things had been run together in the settled facts, and they have different answers.

### 1.1 The 1.22 mm was a measurement artefact

The number came from `fab-cs-assembly/verify_fiducials.py`, which **rastered** the F.Cu zone fill
at `RES = 0.02` mm (`:22`) and read a scipy distance transform at the fiducial centre (`:45`).
Re-running that exact method on this board at three resolutions (`repro_raster.py`,
`raster_repro.log.txt`):

| raster resolution | FID1/FID2 pour gap | what `%.2f` prints |
|---|---|---|
| 0.020 mm (the published method) | **1.2226** | **1.22** |
| 0.010 mm | 1.2366 | 1.24 |
| 0.0025 mm | ran out of memory (14.4 GiB array) | — |
| **exact polygon distance** (`measure_fid3.py`) | **1.2505** | — |

The series converges on the exact value, which is what a quantisation artefact does: a raster
distance transform can only under-report, by up to ≈1.4 pixels (0.028 mm at 0.02 mm). **The pour
was never at 1.22 mm.** It sat at **1.2505 mm**, i.e. the 1.25 mm the footprint asks for
(`fiducials.py:100`, `clearance=0.75` + 0.5 mm pad radius, stated as intent in `fiducials.py:8-10`).

### 1.2 The disclosure failure is real and independent

`fab-cs-assembly/REPORT.md:109-110` prints "sits **1.22 mm** from the global fiducial centres
(nominal 1.25 mm, i.e. 0.22 mm outside the 2.0 mm mask opening — **the requirement it has to meet
is 1.00 mm**)". Two defects in one sentence:

1. the measured number was a raster floor, and
2. a 1.00 mm requirement is **invented there and nowhere else** — the same report's own rule table
   (`:51`) says a global fiducial needs **1.5 mm** centre→track/via/pad, and its own construction
   intent (`fiducials.py:10`) is 1.25 mm. Nothing in the file supports 1.00 mm.

So the settled-fact wording "1.22 against a required 1.25" is right about the *report* and wrong
about the *geometry*. Both are recorded here; neither is smoothed away.

### 1.3 Why it still had to be fixed

A pass by **0.0005 mm** is not a pass. The pour sat at exactly the clearance the footprint
requests, only **0.25 mm outside the 2.0 mm mask opening**, and 0.25 mm *inside* the 1.5 mm
centre→copper rule — which the pour evaded only because that rule names tracks, vias and pads and
not zones. A vision system does not care what kind of copper it is.

### 1.4 The requirement, stated (unchanged threshold)

| id | class | requirement | source |
|---|---|---|---|
| **R1** | global (1.0 mm dot, 2.0 mm mask) | **≥ 1.25 mm** centre → F.Cu pour | the value in the settled fact, and the footprint's own clearance (`fiducials.py:100`) |
| **R2** | global | **≥ 1.5 mm** centre → **any** copper | `fab-cs-assembly/REPORT.md:51`, the rule the pour was exempted from by wording |
| **R3** | local (0.5 mm dot, 1.0 mm mask) | ≥ 0.75 mm centre → any copper | same table, `:52` |

**No threshold was moved.** R1 stays at 1.25 mm; the *geometry* moved.

**Vendor sign-off: UNVERIFIED, and stated as such.** Web search for a fabricator's written fiducial
clear-area spec returned no results (twice, `web_search` empty), so R1/R2/R3 are a design rule
derived from the mask-opening geometry plus the same unit's table — not a cited standard. A CM that
publishes a *larger* clear area would need the pour pulled back further; a CM that publishes 1 mm
would accept this board twice over.

### 1.5 The fix executed

`fix_pour.py IN OUT 1.25` — three pads, one property, then zone refill. Nothing moved, nothing
routed, no net changed, no copper added:

```
changed 3 pads:
   FID3 local clearance 0.750 -> 1.250 mm  (pour must now start at 1.750 mm)
   FID2 local clearance 0.750 -> 1.250 mm  (pour must now start at 1.750 mm)
   FID1 local clearance 0.750 -> 1.250 mm  (pour must now start at 1.750 mm)
saved _work/fix1/Code-SDR-V2.kicad_pcb ; zones 4 ; footprints 382
```

**Alternative considered and rejected:** move the fiducials. FID1 sits in a legal 7.5 mm copper
void, so the fiducial is not the problem — the pour was given a 0.75 mm keepout where the rule
wanted 1.5 mm. Widening the keepout is the smallest edit that satisfies all three rules; moving a
placed, triangle-optimised global fiducial would have re-opened the site selection.

---

## 2. All 9 fiducials, measured, before and after

Exact distances are shapely polygon distance (`measure_fid3.py`); `ring` is the copper-free radius
walked along 72 rays at 0.01 mm (`measure_ring.py`). Both are reported because the ring is what the
camera sees and the exact distance is the number that must clear a rule.

### 2.1 Globals — before the fix (`m3_fid9.json`, `ring_fid9.json`)

| ref | centre (mm) | dot / mask | **pour gap** | ring (72-dir) | nearest copper | R1 1.25 | R2 1.5 |
|---|---|---:|---:|---:|---|---:|---:|
| FID1 | 94.28, 8.68 | 1.00 / 2.00 | **1.2505** | 1.26 @0° | pour GND 1.2505 | +0.0005 | **−0.250 FAIL** |
| FID2 | 6.28, 9.48 | 1.00 / 2.00 | **1.2505** | 1.26 @0° | pour GND 1.2505 | +0.0005 | **−0.250 FAIL** |
| FID3 | 68.98, 86.62 | 1.00 / 2.00 | none < 6 mm; nearest copper 4.6313 | 4.64 @90° | track RGMII_TX_EN 0.15 | — | +3.131 |

### 2.2 Globals — after the fix (`ring_tp55.json`, the deliverable board)

| ref | **pour gap** | ring | R1 1.25 | R2 1.5 | beyond mask edge |
|---|---:|---:|---:|---:|---:|
| FID1 | **1.7505** | 1.76 @0° | **+0.5005** | **+0.2505** | **0.750** |
| FID2 | **1.7505** | 1.76 @0° | **+0.5005** | **+0.2505** | **0.750** |
| FID3 | unchanged (no pour within 41.3 mm) | 4.64 | n/a | +3.131 | 3.63 |

FID1 and FID2 are now the same by construction: 0.5 mm dot radius + 1.25 mm clearance, and the
measured 1.7505 is the fill's own 0.0005 mm chord error.

### 2.3 The six locals (`ring_fid9.json` = `ring_tp55.json`, untouched)

Local fiducials are 0.0 mm from the pour (nearest fill 18–36 mm away), so the pour never was their
constraint; the constraint is track copper, which is why they were measured too.

| ref | centre (mm) | dot / mask | pour gap | **nearest copper** | ring | R3 0.75 | margin |
|---|---|---:|---:|---|---:|---:|---:|
| FIDL_U10_A | 36.10, 72.94 | 0.50 / 1.00 | 27.62 | via QSPI_SD1 0.45 | 0.83 | 0.75 | **+0.077** |
| FIDL_U10_B | 46.50, 80.74 | 0.50 / 1.00 | 35.50 | track IF_PATH_SEL 0.15 | 1.13 | 0.75 | +0.370 |
| FIDL_U20_A | 54.12, 63.51 | 0.50 / 1.00 | 18.20 | track FPGA_PLL_1V2 0.15 | 0.77 | 0.75 | **+0.014** |
| FIDL_U20_B | 59.92, 75.51 | 0.50 / 1.00 | 30.19 | track ADC_PDWN 0.15 | 0.87 | 0.75 | +0.117 |
| FIDL_U30_A | 77.91, 68.41 | 0.50 / 1.00 | 23.09 | track PHY_AVDDL_1V2 0.18 | 0.86 | 0.75 | +0.102 |
| FIDL_U30_B | 95.11, 70.61 | 0.50 / 1.00 | 25.29 | track RGMII_RXD1 0.10 | 2.32 | 0.75 | +1.561 |

**All six pass R3. One passes by 0.014 mm** (FIDL_U20_A, 0.7641 vs 0.75) — a technical pass with no
manufacturing margin, flagged here rather than buried. I did **not** move it: a local fiducial's
value is its geometric relation to the part it serves, its pair separation is 13.3 mm, and R3 is
met. It belongs on the rev-C watch list as a 0.2 mm outward nudge.

---

## 3. DRC — 222, and the set is identical, not merely equal in count

`kicad-cli pcb drc --format json --severity-all --units mm` (`drc_compare.py`):

| board | total | errors | warnings | unconnected | set vs baseline |
|---|---:|---:|---:|---:|---|
| `fid9` (9 fiducials, pre-fix) | **222** | 0 | 222 | 0 | — (control) |
| `fix1` (pour fix only) | **222** | 0 | 222 | **0 new, 0 gone** | 222 common |
| **`tp55` (fix + 18 test points)** | **222** | 0 | 222 | **0 new, 0 gone** | 222 common |

Type tally on every board: `lib_footprint_mismatch` 199, `via_dangling` 13, `track_dangling` 10.
Files `drc_base.json`, `drc_fix1b.json`, `drc_tp55.json`, comparison `drc_compare.txt`.

### 3.1 The `(version 1)` trap, tested rather than trusted

The standing rule after event 4 is that a `.kicad_dru` must be *proved loaded*. The project rule
file starts `(version 1)` and carries the five SMA edge-launch exceptions and the J30 shield-stake
exception. Control: the same board with the `.kicad_dru` deleted (`_work/nodru`):

| board | total | errors |
|---|---:|---:|
| with `.kicad_dru` | **222** | 0 |
| without it | **247** | **25 `copper_edge_clearance`** — J50/J60/J61/J62/J63 pads crossing Edge.Cuts |

So the rule file is genuinely read, and it is doing exactly the 25 suppressions it was written for.
(`drc_nodru.json`, `drc_compare_nodru.txt`.)

### 3.2 One more copy trap, hit and named

The first `fix1` DRC returned **246**, not 222: `+24 lib_footprint_issues`. Cause: my copy took only
the top-level files, and `CodeSDR.pretty/` is a directory, so 24 custom footprints had no library.
This is the *same* 246 the previous unit hit and discarded. A board copy is only faithful with
`fp-lib-table`, the `.kicad_pro`, the `.kicad_dru` **and `CodeSDR.pretty/`**; `drc_fix1.json` is kept
as the failed control, `drc_fix1b.json` is the good run.

---

## 4. The assembly gap: 373 of 373 BOM rows have no MPN

Source `fab-cs-assembly/bom_fields.csv` (kicad-cli export of the root schematic): **373 rows, 129
grouped lines, 48 footprints, 122 values**. `MPN`, `Manufacturer`, `PartNumber`, `Supplier`,
`SupplierPart`, `Height` are empty on **373 / 373**. A property-key census over all 9 sheet files
finds only `Reference, Value, Footprint, Datasheet, Description` on the 442 symbols — there is no
MPN field anywhere in the schematic format used here.

`bom_mpn.py` classifies every one of the 129 lines; the counts below are a property of
`bom_mpn_lines.csv`, not prose:

| bucket | lines | rows | meaning |
|---|---:|---:|---|
| **MPN_DESIGN** | **44** | **58** | the file already determines the order code |
| **MPN_SERIES** | 3 | 3 | manufacturer series stated, order code open |
| **PARAM_ENG** | 14 | 29 | an electrically significant parameter is unstated |
| **PARAM_COMM** | 68 | 283 | commodity passive; MPN is a purchasing choice |
| unclassified | 0 | 0 | every row is covered |

### 4.1 What the 58 are made of

* **49 rows** carry the MPN in the **Value** field — the designer wrote the part number there:
  `RP2040`, `LIF-MD6000-6JMG80I`, `KSZ9031RNXCA`, `LMX2592RHAT`, `AD9215BCPZ-105`,
  `QPC6144TR13`, `QPQ1909TR13`, `GRF2101/2013/4001`, `TC1-1-13M+`, `LFCN-2500+`,
  `2450BL15B0100001E`, `SiT8209AC-23-33E-100.000000X`, … Two need a suffix stripped
  (`ECS-250-20-33-TR_25MHz`, `ABM8-272-T3_12MHz`) and two ADI parts order as `…#PBF`.
* **6 rows** have the order code in the **footprint name**: 5 × `SMA_Molex_73251-1153`, 1 ×
  `USB_Micro-B_Molex-105017-0001`.
* **3 rows** state a **required MPN in a free-text Description** — and this is the one finding that
  changes the blanket "no MPN anywhere" claim: `01_power.kicad_sch:3523` (C11, *"Required MPN
  Murata GRM31CR71A226KE15L"*), `:3593` (C12) and `:4806` (C346), both *"Murata
  GRM32ER71A476KE15L"*. They are real requirements, they survive into the BOM `Description` column,
  and **no BOM tool reads them**, because that same column carries net-function notes on 122 other
  rows.

### 4.2 What needs a human, and how much of it is engineering

| bucket | rows | what the human must decide |
|---|---:|---|
| MPN_SERIES | 3 | `TL3342` switch actuator/plating (**BOOTSEL, RESET**), Phoenix `MKDS 1,5/2` order code (5 V input) |
| PARAM_ENG | 29 | 28 magnetics — Q, SRF, I_sat, DCR for `200nH/220nH/360nH/390nH/2.2uH/33nH/2.7nH` 0603/0402 and `120R/220R/600R @100 MHz` beads — plus the 1 × `2.5A_PTC` 1812 fuse (breaking capacity, voltage) |
| PARAM_COMM | 283 | any approved 0402/0603/0805 resistor or capacitor of the stated value, tolerance and dielectric. 115 of them are 100nF (85) + 10uF (26) + 22uF (4) bypass |

**So: 58 rows are inferable without a decision; 315 need one, of which 32 are decisions an engineer
must make and 283 are purchasing choices.** That single split is the whole assembly problem: it is
~2 hours of engineering and ~5 hours of purchasing, not a design defect.

### 4.3 Is the BOM usable as-is?

**Yes for four things, no for the one that matters.**

* **Usable:** (1) an engineering BOM review — quantities, references, values, footprints and the DNP
  marks (`R153`, `R156`) are complete and correct; (2) a **cost enquiry** once MPNs are filled, and a
  grouped 129-line quote request today with the 58 determinable lines pre-filled; (3) a **hand-build
  kit list** for a bench prototype, where a human reads value+footprint off the schematic; (4)
  mechanical/placement data (48 footprints, all on a 101.7 × 101.7 mm board, single-sided).
* **Not usable:** a **turnkey assembly PO**. Zero of 373 rows has a purchasable identifier, there is
  no approved-vendor list, no alternate parts, and no part heights — a CM cannot quote, kit or place
  from it.

Two smaller defects worth naming for whoever fills it in: `R5` has value `"0"` where every other
0 Ω part says `"0R"`, and the DNP straps are identifiable **only** from the `${DNP}` column.

---

## 5. Test points: 18 placed, DRC 222 — but they are 0.45 mm lands, not ATE targets

### 5.1 Why a 1.0 mm land cannot go at all 18 sites

`tp_fit.py` measures, per site, the distance from the site centre to the nearest copper of a
**different** net (project rules: netclass `Default` clearance **0.1 mm**, no net-class assignments
so every net is Default). A land of diameter `D` is legal only if `D/2 + 0.1 ≤ d_foreign`:

| site | kind | nearest foreign copper | d (mm) | **max legal land (mm)** |
|---|---|---|---:|---:|
| +5V_RF | via | track AD8351_OUT_P | **0.326** | **0.452** |
| FPGA_RESET_N | via | track FPGA_CDONE | 0.383 | 0.566 |
| ADC_VREF | via | track ADC_REFT | 0.425 | 0.650 |
| +1V2_CORE | via | track ADC_VIN_N | 0.426 | 0.652 |
| +2V5_AUX | via | pad FB36.2 | 0.476 | 0.752 |
| LMX_VREF | via | via GND | 0.479 | 0.758 |
| USB_VBUS_SENSE | via | via USB_DM_CONN | 0.508 | 0.815 |
| BOOTSEL_SWITCH | via | track RGMII_TXD3_FPGA | 0.524 | 0.848 |
| PHY_RESET_N | via | pad C345.2 | 0.575 | 0.950 |
| SWD_IO | pad | track LNA_EN_H2 | 0.601 | 1.002 |
| FPGA_PLL_1V2 | via | track HSW_V2 | 0.601 | 1.002 |
| SWD_CLK | via | track LNA_EN_H2 | 0.663 | 1.125 |
| VIN_FUSED | via | pad C1.2 | 0.838 | 1.476 |
| PHY_AVDDL_1V2 | via | via +3V3_DIG | 1.012 | 1.824 |
| GND | via | track RF_HA_LNA_OUT | 1.115 | 2.030 |
| +3V3_DIG | via | via HSW_V2 | 1.936 | 3.673 |
| +3V3_ANA | via | track LO_HIGH_P | 2.890 | 5.581 |
| VIN_5V | pad | pad J1.2 | 3.704 | 7.208 |

**9 of 18 sites cannot hold a 1.0 mm land**; the floor is **0.452 mm** at `+5V_RF`. Confirmed by
building it: 1.0 mm lands → **245 violations, 22 errors** (9 `clearance`, 6 `shorting_items`,
7 `solder_mask_bridge`); 1.0 mm mask apertures → **231, 8 errors** (mask bridge). Both are worse
than doing nothing, so neither was kept.

### 5.2 What was actually placed — and it is the honest version

Each site gets a **0.55 mm mask-only aperture** (0.45 mm via + 0.05 mm expansion per side): no
copper added, no net, no paste, excluded from BOM and position files, concentric with the target.
The probe land is the **existing copper**: 0.45 mm on the 16 vias, 2.60 mm on J1.1, 1.00 mm on J11.2.

`place_tp.py … mask 0.55` → `verify_final.py` reads the **saved file** and asserts every row:

```
fiducials 9   test points 18   footprints 400   vias 1085
TP1..TP18   0.550 mm  F.Mask  no net   d_via 0.0000-0.0001   OK      ALL ROWS PASS: True
```

DRC on that board: **222 — 0 new, 0 gone, identical set** (`drc_tp55.json`).

**The headroom model is validated by an independent DRC run, not asserted:**

| aperture | DRC | what it proves |
|---|---:|---|
| 0.55 mm (chosen) | **222** | passes with 0.10 mm margin |
| 0.60 mm | **222** | passes with 0.05 mm margin |
| 0.70 mm | **223** | the model predicted failure above 0.652; the one new violation is exactly `Pad of TP3 on F.Mask @(85.700,30.711)` bridging the `+5V_RF` track |

**What this means for assembly:** bring-up by hand probe or fine-pitch needle is covered. A
**bed-of-nails fixture is not** — that needs 0.9–1.0 mm targets, which needs 9 of the 18 sites moved
(via `+5V_RF` needs 0.55 mm more room) or re-placed parts, i.e. a copper change, not a copy edit.

---

## 6. Two verdicts

### BARE BOARD — **ORDERABLE**

| item | value |
|---|---|
| DRC | **222 warnings, 0 errors, 0 unconnected**, identical set before and after both edits |
| the 222 | 199 `lib_footprint_mismatch` (silk/Fab artwork, 0 pad differences per `fab-cs-drc`), 13 `via_dangling`, 10 `track_dangling` — no copper defect, no unconnected net |
| HDI | **0** — 1,085 through vias, 0.45 mm pad / 0.20 mm drill, project `min_via_diameter` 0.4 |
| stackup | 1 oz (0.035 mm) all four layers, 0.130 mm dielectric, 101.7 × 101.7 mm |
| fiducials | 3 global at **1.7505 mm** pour gap, 6 local, all rules met |
| rules loaded | proved: 222 with `.kicad_dru`, 247 without (25 edge-launch exceptions) |
| impedance | RF_50 0.23 mm → 49.5 Ω (±10 %) stated in `STACKUP_DRAWING.md`; USB 90 Ω claim already corrected to "Full-Speed, not controlled" |

**Blocker: none.** The only thing a fab must be told is the 25 rule-file exceptions, and those are
already in the file a fab receives next to the board.

### ASSEMBLY — **NOT ready**

| # | blocker | size |
|---|---|---|
| 1 | **No purchasable identifier on any row**: 0 of 373 BOM rows carry an MPN | 58 rows fillable with no decision (3 of them only out of a Description field no tool reads), 32 need an engineer, 283 need purchasing |
| 2 | **No assembly drawing** (fiducials and test points now give it something to reference) | 1 document |
| 3 | **Test points are 0.45 mm probe lands, not ATE targets** | 9 of 18 sites cannot take 1.0 mm without a copper change |

Blockers 2 and 3 are cheap. **Blocker 1 is the whole gap, and it is sourcing, not engineering.**

---

## 7. Artefacts

| file | what |
|---|---|
| `_work/tp55/Code-SDR-V2.kicad_pcb` | **deliverable board** — pour fix + 18 test points, sha `8EC5741A…1DB7AD` |
| `_work/fix1/…` | pour fix only, sha `57164973…FCB555D` |
| `_work/fid9/…` | the 9-fiducial board this unit started from (copy of `fab-cs-assembly/_work/fid2`) |
| `_work/{tp10,tpmask,tp060,tp070,nodru}/…` | the rejected/control variants (1.0 mm land, 1.0 mm aperture, 0.60, 0.70, no-`.dru`) |
| `measure_fid2.py`, `measure_fid3.py` | exact per-fiducial distances + nearest-copper identity |
| `measure_ring.py` | 72-ray copper-free annulus + exact-distance cross-check |
| `repro_raster.py`, `raster_repro.log.txt` | the raster artefact, reproduced at three resolutions |
| `fix_pour.py` | the fix (3 pads, refill) |
| `tp_fit.py`, `tp_fit.json` | per-site headroom and the max legal land at each |
| `place_tp.py`, `verify_final.py` | test-point placement, and file-level verification of all 27 objects |
| `bom_mpn.py`, `bom_mpn_lines.csv`, `bom_mpn.out.txt` | per-line MPN classification, 129/129 covered |
| `drc_*.json`, `drc_compare.py`, `drc_compare*.txt` | every DRC run and its set comparison |
| `m3_fid9.json`, `ring_fid9.json`, `ring_tp55.json`, `ring_fix1.json` | raw measurements |

## 8. Limits, stated

* **No fabricator's written fiducial spec was obtained** (two web searches, no results). R1/R2/R3
  are a design rule from mask geometry + the prior unit's table; R1 is the settled-fact number and
  was not changed.
* The **0.014 mm margin** on FIDL_U20_A is a pass, and is reported as a watch item, not a clean bill.
* The raster's exact failure floor is **inferred** from three converged samples, not from a
  formula; the 0.0025 mm run exceeded available memory.
* `R5` value `"0"` and the DNP-only visible straps are recorded, not fixed — they are schematic edits.
* MPN classification is a **judgement table**, published row-by-row in `bom_mpn_lines.csv` so any
  bucket can be argued with line by line; the counts (58/3/29/283) are derived from it.
* Untouched by design: the 84-net In1 signal pilot, the 4 parity pads, the USB impedance geometry.