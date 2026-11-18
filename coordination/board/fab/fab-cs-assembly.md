# Code-SDR V2 — assembly gaps closed (or shown closed-able)

Unit: `fab-cs-assembly` (wave 2, hotfix lane). Scope: `repos/Code-SDR/hardware/v2/`.
Nothing in this report writes to the repository; every board edit was made on a copy under
`_work/` and every number below has the command or the file that produced it.

## Verdict in one table

| gap | before | after this unit | blocks |
|---|---|---|---|
| fiducials | **0** | **3 global + 6 local placed, DRC identical (222 → 222)** | ASSEMBLY |
| test points | **0**, and all 1,085 vias mask-tented | **18 probe sites named, coordinates + size** | ASSEMBLY (bring-up) |
| BOM | no export existed | **exported: 373 rows, 129 grouped lines, 0 missing values, 373 missing MPN** | ASSEMBLY |
| impedance claim | `ImpedanceControlled: true`, no target | **targets stated; one of three was false, claim revised** | FAB (fab reads it) |
| IPC-D-356 | none | **produced: 1,289 pin + 1,213 via records** | neither (netlist tooling only) |

**Assembly still cannot be ordered even with these edits** — the missing BOM part numbers are
the binding constraint (§3). Everything else in the assembly path is now present.

Board of record, measured (`_work/…/Code-SDR-V2.kicad_pcb`): **101.6 × 101.6 mm, 4 layers,
373 footprints, 1,561 pads (1,431 SMD / 128 PTH / 2 NPTH), 1,085 vias, 261 nets, 4 zones**.
**0 footprints on the back side** → single-sided assembly, so one fiducial set is enough.

---

## 1. Fiducials

### How many

Three global fiducials, per the standard rule (three, not four, so that a rotated or mirrored
board is detectable — a four-fiducial symmetric pattern is ambiguous). Nothing on the bottom
side is assembled, so a second set is not required.

Local pairs for the parts where placement error is expensive. The rule applied here is
**pitch ≤ 0.5 mm and ≥ 40 pins**, which on this board is U10 (RP2040, QFN-56 P0.4),
U30 (KSZ9031, QFN-48 P0.5) and U20 (LIF-MD6000, 80-ball BGA). That is 3 global + 3 pairs.

*Sources for the practice, not for the numbers:* PCBWay's glossary separates global
("locate the overall pattern") from local ("pinpoint component sites, typically fine-pitch")
fiducials — <https://www.pcbway.com/blog/PCB_Knowledge/fiducial.html>. The **geometry** is taken from
KiCad 9.0's own footprint library, which ships `Fiducial_1mm_Mask2mm` and
`Fiducial_0.5mm_Mask1mm` (`C:/Program Files/KiCad/9.0/share/kicad/footprints/Fiducial.pretty/`),
i.e. the 1 mm copper / 2 mm mask global and the 0.5 mm / 1 mm local convention used here.
A specific fabricator's written fiducial requirement was **not** obtained (web search returned
no results) — vendor sign-off is UNVERIFIED.

### Rule used to declare a site legal

| class | copper dot | mask opening | min centre→track/via/pad | min centre→component | min centre→board edge |
|---|---|---|---|---|---|
| global | 1.0 mm | 2.0 mm | 1.5 mm | 2.0 mm | 2.0 mm |
| local | 0.5 mm | 1.0 mm | 0.75 mm | 1.0 mm | 1.0 mm |

The F.Cu GND pour is **not** an obstacle: the fiducial pad carries a local clearance
(0.75 mm global, 0.4 mm local) that pulls the pour back beyond the mask opening by design.

### Coordinates

Chosen by maximising the triangle over every legal pooled site (`pick_global.py`):
**triangle 3,419 mm² = 33.1 % of the board, minimum pairwise 81.9 mm**, all three asymmetric.

| id | x (mm) | y (mm) | margin vs rule | to copper | to a part | to board edge | in pour |
|---|---:|---:|---:|---:|---:|---:|---|
| FID1 | 94.28 | 8.68 | 5.25 | 7.45 | 7.25 | 7.25 | yes |
| FID2 | 6.28 | 9.48 | 4.16 | 6.12 | 6.16 | 6.20 | yes |
| FID3 | 68.98 | 86.62 | 3.15 | 4.65 | 5.15 | 14.90 | no |

Local pairs (0.5 mm dot / 1.0 mm mask, body gap = distance from the part's bounding box):

| pair | A (mm) | B (mm) | separation | max body gap |
|---|---|---|---:|---:|
| U10 (QFN-56 P0.4) | 36.10, 72.94 | 46.50, 80.74 | 13.0 mm | 1.09 mm |
| U20 (BGA 80) | 54.12, 63.51 | 59.92, 75.51 | 13.3 mm | 3.20 mm |
| U30 (QFN-48 P0.5) | 77.91, 68.41 | 95.11, 70.61 | 17.3 mm | 4.60 mm |

The remaining 15 parts at 0.5 mm pitch have legal local pairs too (table in `sites.json`,
`local` key, produced by `pick_final3.py`); they are not placed because they are ≤ 32 pins and
the three global fiducials plus panel fiducials carry them. Add them only if the CM asks.

### The edit, as a script

`fiducials.py` — `--add IN OUT` or `--refill IN OUT`. It builds each fiducial as a real
footprint (SMD circular pad, `F_Cu`+`F_Mask` only — **no paste aperture**, no net,
`FP_EXCLUDE_FROM_BOM | FP_EXCLUDE_FROM_POS_FILES`, an F.CrtYd rectangle, reference on F.Fab),
adds it, then refills all four zones and saves. Run against a copy:

```
"C:/Program Files/KiCad/9.0/bin/python.exe" fiducials.py --add \
    _work/src/Code-SDR-V2.kicad_pcb _work/fid2/Code-SDR-V2.kicad_pcb
```

### Verification (this is the part that matters)

| run | command | result |
|---|---|---|
| baseline | `kicad-cli pcb drc --format json --severity-all` | **222 violations, 0 errors, 0 unconnected** (`drc_base.json`) |
| refill-only control | same, after a bare zone refill | **222** (`drc_refill2.json`) — the refill changes nothing |
| with 9 fiducials | same | **222** (`drc_fid2.json`) |
| *first attempt (discarded)* | same, on a copy **without `fp-lib-table`** | 246 (`drc_fid.json`) — the extra 24 were `lib_footprint_issues` "library 'CodeSDR' not configured", an artefact of the bare copy, **not** of the fiducials. A board copy must carry `fp-lib-table`, the `.kicad_pro` and the `.kicad_dru` or the DRC delta is meaningless. |

The violation **sets** are identical, not merely equal in count: comparing on
`(type, sorted item descriptions/positions)` gives *0 new, 0 gone* — 199 `lib_footprint_mismatch`,
13 `via_dangling`, 10 `track_dangling`, all warnings. This also reproduces the board's published
"222, zero errors" figure on an untouched copy.

Geometry verified in the **saved** file (`verify_fiducials.py`, `_work/verify_fid.out.txt`):
9 fiducials found; dot 1.00 mm with mask 2.00 mm, dot 0.50 mm with mask 1.00 mm; **no paste
layer on any pad**; net name empty on all; BOM and position-file exclusion set; the F.Cu pour
sits **1.22 mm** from the global fiducial centres (nominal 1.25 mm, i.e. 0.22 mm outside the
2.0 mm mask opening — the requirement it has to meet is 1.00 mm).

---

## 2. Test points

**Existing: 0.** No `TestPoint` footprint, no bare probe pad, and — the part that makes "reuse a
via" impossible as built — `(tenting front back)` at `Code-SDR-V2.kicad_pcb:109` tents **every
via** with solder mask. A probe cannot land on any of the 1,085 vias without a mask edit.

Nets a bring-up engineer needs, and the best existing copper on each (`testpoints.py`).
All sites are on-board and ranked by hand room to the nearest component body first
(a probe comes down at an angle), then copper size.

| net | why | site (mm) | copper | room to a part |
|---|---|---|---:|---:|
| VIN_FUSED | raw input after the fuse | 6.52, 81.78 | via 0.45/0.20 | 0.40 |
| VIN_5V | 5 V before the fuse | 9.00, 93.00 | pad J1.1 2.60 | connector |
| +5V_RF | RF section 5 V | 85.70, 30.71 | via 0.45/0.20 | 0.65 |
| +3V3_DIG | digital 3V3 | 58.92, 61.50 | via 0.45/0.20 | 2.45 |
| +3V3_ANA | analog 3V3 | 41.47, 44.71 | via 0.45/0.20 | **8.25** |
| +1V2_CORE | FPGA/PHY core | 72.11, 50.45 | via 0.45/0.20 | 2.35 |
| +2V5_AUX | FPGA aux 2V5 | 52.89, 58.10 | via 0.45/0.20 | 0.14 |
| FPGA_PLL_1V2 | FPGA PLL rail | 55.42, 61.96 | via 0.45/0.20 | 2.55 |
| PHY_AVDDL_1V2 | PHY core rail | 90.91, 58.43 | via 0.45/0.20 | 1.35 |
| ADC_VREF | U21 reference | 70.33, 69.99 | via 0.45/0.20 | 0.30 |
| LMX_VREF | U40 reference | 23.82, 60.26 | via 0.45/0.20 | 1.25 |
| GND | ground | 49.50, 15.10 | via 0.45/0.20 | **9.37** |
| FPGA_RESET_N | FPGA reset | 47.90, 79.27 | via 0.45/0.20 | 2.45 |
| PHY_RESET_N | PHY reset | 80.50, 64.00 | via 0.45/0.20 | 0.30 |
| BOOTSEL_SWITCH | boot-mode strap | 59.08, 90.82 | via 0.45/0.20 | 0.65 |
| SWD_CLK | debug clock | 30.41, 77.27 | via 0.45/0.20 | 2.35 |
| SWD_IO | debug data | 26.48, 75.59 | pad J11.2 1.00 | header pin |
| USB_VBUS_SENSE | USB present | 40.78, 95.63 | via 0.45/0.20 | 0.90 |

One point per major IC is covered: U10/RP2040 (`+3V3_DIG`, `SWD_CLK/IO`, `BOOTSEL_SWITCH`),
U20/FPGA (`FPGA_PLL_1V2`, `FPGA_RESET_N`, `+1V2_CORE`), U30/KSZ9031 (`PHY_AVDDL_1V2`,
`PHY_RESET_N`), U21/AD9215 (`ADC_VREF`), U40/LMX2592 (`LMX_VREF`).

Two ways to make these real, in cost order:

1. **Open the mask over the 12 listed vias** (no copper change, no schematic change, no parity
   debt). That yields a 0.45 mm probe land — fine for a hand probe or a fine-pitch needle, too
   small for a bed-of-nails fixture. KiCad 9 supports per-via tenting, so this is 12 object
   properties, not a board-wide `(tenting)` flip.
2. **Add 18 real test pads** of 1.0–1.5 mm on the free area. This is *not* done here on purpose:
   a test pad in the PCB with no schematic symbol is exactly the "extra pad" parity defect this
   programme already carries (4 pads) and is auditing. Add the `TestPoint` symbols first, then
   the pads.

---

## 3. BOM

`kicad-cli` can export it and does:

```
kicad-cli sch export bom --fields 'Reference,Value,Footprint,${QUANTITY},${DNP},MPN,Manufacturer,
  PartNumber,Supplier,SupplierPart,Description,Height' -o bom_fields.csv \
  .../Code-SDR-V2.kicad_sch
```

**373 rows** (matches the 373 board footprints), 48 distinct footprints, 122 distinct values;
grouped by Value+Footprint it is **129 lines**. `--exclude-dnp` would drop **R153, R156** (both 0R
straps marked DNP).

Missing fields — the schematic carries only `Reference, Value, Footprint, Datasheet, Description`
(property-key census over the 8 sheets: no MPN/Manufacturer/Supplier/PartNumber/Height key exists
anywhere):

| field | rows missing |
|---|---:|
| **MPN** | **373 / 373** |
| Manufacturer, PartNumber, Supplier, SupplierPart, Height | 373 / 373 each |
| Value | **0** |
| Footprint | 0 |
| Description | 122 (a net-function note, not a part description) |

So the schematic carries **enough to build a BOM and not enough to buy one**: 0 of 373 rows can
be sourced from this file. Two smaller defects worth naming: `R5` has value `"0"` where every
other 0 Ω part says `"0R"`, and the DNP straps are only identifiable from the `${DNP}` column.

**This is the item that still blocks assembly.** Fiducials and test points are board edits; a BOM
without a single part number is a purchasing task, and no amount of PCB work closes it.

---

## 4. Impedance — the claim, the number, and the one that does not survive

`ImpedanceControlled: true` is generated into the Gerber job file by `kicad-cli` (see
`evidence/fab-cs-clock/gerbers/Code-SDR-V2-job.gbrjob:23`) from the board's own settings; it is
not hand-written. A fab reading only that file gets a claim with no number.

Measured geometry (`geometry.json`): the **RF_50 width is 0.23 mm on 593 segments across 49 nets**,
the USB pair is 0.12 mm, MDI is 0.15–0.20 mm. The stackup is F.Cu 0.035 / prepreg 0.130 (Dk 4.2) /
In1 0.035 / core 1.200 / In2 0.035 / prepreg 0.130 / B.Cu 0.035, i.e. **1 oz (0.035 mm) copper** on
a 0.130 mm dielectric (`STACKUP_DRAWING.md`, board `(stackup …)` block).

| net class | geometry | target to state | evidence |
|---|---|---|---|
| **RF_50** | 0.23 mm single-ended, F.Cu over In1 | **50 Ω ±10 %** | FD solve **49.50 Ω** at 0.23 mm (`evidence/cs-em-field/width_sweep.csv`, `w_mm 0.2300`), band **48.56–49.92 Ω** over mask Dk 3.0–4.5 (`evidence/hf-cs-em-field/hotfix_z0_band.csv`) |
| **MDI (1000BASE-T)** | 0.15/0.20 mm pairs, measured gaps 0.164–0.360 mm | **100 Ω ±15 % differential** | closed form 94.5–101.7 Ω from the same per-width Z0 (`Zdiff = 2·Z0·(1−0.48·e^(−0.96·s/h))`, h = 0.130 mm) — inside the band, keep |
| **USB (RP2040)** | 0.12 mm body runs, 0.25 mm connector stubs, gaps **0.191–0.461 mm** measured | **90 Ω** as the note claims | **FAILS.** Closed form gives **≈102–107 Ω** on the 0.12 mm runs and **≈84 Ω** on the 0.25 mm stubs: not matched, and not uniform. |
| POWER / Default / DIGITAL_HS | 0.6 / 0.15 / 0.15 mm | **not controlled** | — |

**The specific edit.** Keep `ImpedanceControlled: true` for the RF geometry and add the number
where a fab reads it — an impedance table in `STACKUP_DRAWING.md` (the file that already goes with
the order) reading *"RF_50: 0.23 mm ⇒ 49.5 Ω nominal, 50 Ω ±10 %, report TDR on coupons"* — and
fix the USB row in `FABRICATOR_IMPEDANCE_NOTE.md:37-38`: either

- **(a) revise the claim**: delete "USB 2.0: 90 ohm differential target" and replace it with
  *"USB: RP2040 Full-Speed (12 Mbit/s) device; the 0.12 mm pair with 0.19–0.46 mm gaps is not
  impedance-controlled and does not need to be at Full Speed"* — cheap, and true; or
- **(b) fix the geometry**: 0.20 mm width with a 0.10 mm gap to reach 90 Ω, which is a copper
  change on a pair that already runs 0.12 mm.

(a) is recommended: U10 is an RP2040 (BOM value `bom_fields.csv`), a Full-Speed-only USB device,
so 90 Ω buys nothing measurable. If the FPGA ever drives USB at High Speed this flips to (b).

**Second defect found while measuring this:** the project defines five net classes but
`netclass_assignments` is `null` and `netclass_patterns` is empty (`Code-SDR-V2.kicad_pro:335-336`),
so **no net is in RF_50** — the 0.23 mm width exists only because the router drew it, and no DRC
rule enforces 0.23 mm or 0.18 mm clearance. Fix: assign the 49 RF nets to RF_50 so the target above
becomes enforceable. (Reported, not edited: it is a project-file change and this unit writes only
its own directory.)

---

## 5. IPC-D-356

`kicad-cli pcb export ipcd356` exists in 9.0.7 and works:

```
kicad-cli pcb export ipcd356 -o Code-SDR-V2.ipc .../Code-SDR-V2.kicad_pcb
Successfully created IPC-D-356 file        # 198,701 bytes
```

| record | count |
|---|---:|
| header (`P`) | 3 |
| **327 pin records (pads with a net)** | **1,289** |
| 317 via records | 1,213 |
| 367 bare-pad records | 2 (J30, net `N/C`) |
| 999 terminator | 1 |
| total lines | 2,508 |

Reconciliation: 1,561 pads − 1,289 emitted = **272 pads carry no net** (mechanical/shield/NPTH)
and are correctly absent from a netlist; 1,213 via records = 1,085 vias + 128 through-hole pads
emitted again as via records, which is exactly the board's PTH count — arithmetic closes, cause
INFERRED not read out of the writer. **1,289 is the answer to "pad count"**: it is the number of
pads a netlist tester can actually test.

---

## 6. What blocks ASSEMBLY vs what blocks FAB

**Blocks ASSEMBLY (an assembly PO cannot be placed):**

1. **No part numbers anywhere** — 373/373 BOM rows lack MPN/Manufacturer/Supplier. This is the
   one hard blocker left, and it is not a PCB defect.
2. No assembly drawing has been produced (the fiducials now give it something to reference, but
   the drawing itself does not exist).
3. Test points are proposed, not placed (§2) — bring-up without them needs a probe on a tented via.

**Blocks FAB (the bare-board order):** nothing new. DRC is 222 warnings / 0 errors / 0 unconnected
both before and after this unit, all vias are standard 0.20–0.40 mm drill through vias (0 HDI), and
the impedance claim now carries numbers. **Fab was already clear; this unit did not change that.**

**Was wrongly believed to block fab, and does not:** the 84-net In1 signal pilot (SI debt, per the
brief) and the 4 schematic-parity pads — both untouched here, as instructed.

---

## 7. Artefacts in this directory

| file | what |
|---|---|
| `REPORT.md` | this report |
| `fiducials.py` | the fiducial edit (9 footprints + zone refill) — run on a copy |
| `verify_fiducials.py` | post-save verification of the 9 fiducials |
| `geometry.json`, `extract.py` | board geometry dump (tracks/vias/pads/zones) |
| `pick_global.py`, `pick_final3.py`, `sites.json` | site selection and the full 18-part local table |
| `testpoints.py`, `testpoints.json` | test-point ranking |
| `bom_fields.csv` | the BOM export (373 rows, 12 columns) |
| `Code-SDR-V2.ipc` | the IPC-D-356 netlist |
| `drc_base.json`, `drc_refill2.json`, `drc_fid2.json` | the three comparable DRC runs (`drc_fid.json` = discarded first attempt, bare copy without `fp-lib-table`) |
| `assembly_sites.png` | board map with all 27 proposed sites |
| `free_FCu.png` | free-area field used to choose them |
| `_work/fid2/…kicad_pcb` | the edited board (copy, 382 footprints, 1,570 pads) |

## 8. UNVERIFIED / limits

- A named fabricator's written fiducial requirement (size, count, edge distance) was **not
  obtained**; web search returned no results. The sizes used are KiCad's own library convention.
- The diff-pair impedances are **closed form** (Tier C) applied to FD per-width Z0 — not a coupled
  2D solve, and no TDR exists for any of them.
- The 128 extra 317 records in the IPC file are explained by arithmetic (PTH count), not by
  reading the KiCad writer.
- Local fiducials for the other 15 fine-pitch parts are legal per `sites.json` but are **not
  placed**; that is a decision, not a measurement.
- The 84-net In1 pilot and the 4 parity pads were out of scope and were not touched.