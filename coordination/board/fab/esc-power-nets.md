# ESC POWER — Restore Nets to the 756 Netless Pads

**Wave:** esc-power-nets · **Date:** 2026-11-18 · **Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), pcbnew + `kicad-cli`, bundled python 3.11.5
**Scope:** give the routed ESC POWER board's netless pads their nets so the gate drive and signals can route; then route gate drive first, signals as budget allowed.
**Write scope:** `evidence/esc-power-nets/` only, on copies. Nothing written to a repo, `D:\CodeProjects` or `E:\1vm\TMP`.

---

## 0. Verification status (read this first)

| Claim | Status |
|---|---|
| 756 netless pads enumerated by component | **DONE** — §2, and 96 of them are stencil apertures, not pads |
| Component match: by reference vs part+position vs none | **DONE** — §3: 0 by reference, 15 by part+position (2–10 mm), 90 weak, 68 no counterpart |
| DRV8353 pad-function map from the datasheet, cited | **DONE** — §4, TI SLVSDY6A pp. 8–9 (48-pin RGZ) |
| Netted pads before/after + the unconnected jump | **DONE** — §5: 825 → 1119 netted, 0 → **258** unconnected |
| Gate loop length achieved per phase | **PARTIAL** — **27 of 36** gate nets routed (§6.1); 9 have no legal via site / no path |
| Final unconnected on both tools | **DONE** — §7.1: **231** on kicad-cli **and** pcbnew (they agree) |
| DRC set diff (added/gone) | **MIXED** — §7.2: netting **0 added / 0 gone** (cfg B, below the cap, trustworthy); the *routing* adds **+201 shorting** rows (exact) and **≥+385 clearance** rows (*capped at 499*) → the routed board is **not acceptable** |
| Power path untouched (18×6.00 mm, BATN 4.00 mm, BATP) | **DONE** — §7.4: 0 of 134 segments and 0 of 30 vias lost, every protected width byte-identical |
| Package regenerated | **NOT DONE** — the precondition (0 unconnected + clean set diff) is not met, so packaging would manufacture a pass |
| **VERDICT: IS THE POWER BOARD COMPLETE?** | **NO** — §9, five separate blockers |

---

## 1. Inputs, and what this pass actually measured

| item | path | figures |
|---|---|---|
| routed power board | `evidence/esc-power-route/boards/p2_routed.kicad_pcb` | 650,402 B, 173 footprints, **1,581 pads, 173 nets**, 134 segments, 30 vias, bbox 151.77 × 122.55 mm |
| original unsplit ESC | `evidence/esc-pinsplit-v2/esc_copy.kicad_pcb` | 5,805,101 B, 607 footprints, **3,068 pads, 564 nets**, 5,286 segments, 1,944 vias, 126 zones, bbox 246 × 296 mm |
| header pin map | `evidence/esc-pinsplit-v2/pinmap.md` | 3 × 2×20 = 120 positions, net names + direction + mA/pin |
| datasheet | `https://www.ti.com/lit/ds/symlink/drv8353.pdf` | DRV835x, SLVSDY6A (Aug 2018, rev. June 2019), 101 pp. |

Reproduction before I changed anything: a text parser (`scripts/parse_pcb.py`, no pcbnew — the parser reads the
s-expression directly, so nothing can hang) returns **756 netless of 1,581 pads, 173 nets, bbox 151.77 × 122.55**,
matching the brief exactly. `scripts/01_enum.py` then enumerates them.

**Board copies produced, and what each one is** (nothing outside this directory is written):

| file | what it is | segments / vias | unconnected |
|---|---|---|---|
| `boards/n1_netted.kicad_pcb` | **the netlist fix** — the input plus 294 netted pads, no copper added | 134 / 30 | **258** |
| `boards/n2_run1.kicad_pcb` | first routing pass (27 nets), kept for provenance | 2,574 / 84 | 231 |
| `boards/n2_final.kicad_pcb` | byte-identical copy of `n2_run1` — the routed board analysed in §6–§7 | 2,574 / 84 | 231 |

Discarded intermediates (a clobbered 0-route save, a 4-route partial, and the six bisection variants used to find why
KiCad rejected the patched file) were deleted so no stale board can be mistaken for a result.

**One correction to the brief's premise, up front.** "ALL 390 DRV8353 PADS ARE NETLESS" is true of the *pad objects*
but 96 of those 390 are **`F.Paste`-only stencil apertures** (1.13 × 1.13 mm, a 4 × 4 grid over the 5.6 × 5.6 mm
exposed pad, no copper layer at all). They can never carry a net. Each DRV8353 has **65 pad objects = 48 pins +
1 exposed pad + 16 paste apertures**, so the copper pads are **294, not 390**. Board-wide the electrical netless
pads are **660**, not 756.

---

## 2. The 756, enumerated by component

| # | component | refs | n | pads/part | netless | what the netless pads are |
|---|---|---|---:|---:|---:|---|
| 1 | **DRV8353** (`QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm`) | U11–U16 | 6 | 65 | **390** | 48 numbered pins + EP(49) + **16 paste apertures**. Copper pads 294; **all 294 netless** |
| 2 | **INA296A2** (`SOT-23-8`) | U20–U37, U40 | 19 | 8 | **152** | pins 1–8, all netless |
| 3 | **Conn_02x12_Pin** (2×12 THT, 2.54 mm) | J1–J6 | 6 | 24 | **144** | pins 1–24, all netless |
| 4 | **IPTC014N10NM5** (TO-leadless) | Q1AH…Q6CL | 36 | 17 | **36** | **one per FET: the 10.2 × 7.0 mm drain tab**, which lost its pad number (§5.4) |
| 5 | **MotorLand_6x4** (6.0 × 3.2 land) | P1–P18 | 18 | 1 | **18** | single land, no net |
| 6 | **L500x 0.5m 10W** (shared-bus shunt) | RS1, RS2 | 2 | 4 | **8** | 4 pads each, all netless |
| 7 | **820uF_35V** | C1–C6 | 6 | 1 | **6** | one 8.0 × 8.0 land each — **a 2-terminal capacitor in a 1-pad footprint** |
| 8 | **MountingHole_3.2** (NPTH) | H4, H5 | 2 | 1 | **2** | non-plated through holes — correctly netless |
| | **total** | | **173** | **1,581** | **756** | |

The other component types carry **no** netless pads: `copper` ×54 (busbar lands), `Busbar_land` ×3 (BAR1/2/3),
`TSW-120-15-G-D` ×3 (J_H1–J_H3, 120 pins, all netted).

---

## 3. Component matching: by part + position, not by reference

`scripts/11_match.py`. A previous attempt matched references and got 0 of 148; the brief is right that references
do not correspond. What the numbers actually show is stronger than that:

| measurement | result |
|---|---|
| reference strings present on **both** boards | **2** (`H4`, `H5`) — and those are different parts (M4 hole vs 3.2 mm hole) |
| matched by **reference + same part family** | **0 of 173** |
| best rigid transform from the 36 FETs (rotation ∈ {0,90,180,270} × mirror × translation, Hungarian per candidate) | rotate 90°, translate (+209.180, −78.463) mm |
| FET residual under that transform | **mean 49.015 mm, max 74.112 mm** |
| best **similarity** fit (scale free, chamfer objective) over the FET centroids | chamfer **9.99 mm** at scale 0.425 |
| matched by **part + position**, ≤2 mm | **0** |
| matched by part + position, 2–10 mm | **15** |
| matched by part + position, >10 mm (weak) | **90** |
| no counterpart part in the original at all | **68** |

Per family, nearest distance after the transform (mm):

| family | n | min | median | max |
|---|---:|---:|---:|---:|
| IPTC014N10NM5 | 36 | 2.540 | 25.048 | 36.037 |
| L500x 0.5m 10W (orig. CSS4J) | 20 | 3.457 | 24.231 | 42.230 |
| DRV8353 (orig. DRV8353SRTAR) | 6 | 7.873 | 44.706 | 55.461 |
| INA296A2 (orig. INA296A2IDR) | 19 | 8.128 | 31.676 | 68.112 |
| MotorLand_6x4 (orig. MOTOR_POWER_LUG) | 18 | 3.882 | 20.709 | 46.309 |
| 820uF_35V (orig. 820u 100V) | 6 | 63.424 | 70.194 | 75.224 |

**Conclusion, stated plainly: the power board is a re-layout, not a transformed copy of the original.** Even the
part class with identical part number and identical count (36 FETs) has a 49 mm mean residual under the best rigid
fit, and a free-scale similarity fit still only reaches a 10 mm chamfer. There is therefore **no positional
correspondence from which a net identity could be recovered** — not by reference (0/173) and not by part+position
(15 at 2–10 mm, out of 173). The board's own net names plus the datasheet are the only admissible authority, which
is what §4 does. The 68 components with no counterpart in the original are `copper` ×54, `Conn_02x12_Pin` ×6,
`MotorLand_6x4` ×18 minus the 6 original power lugs, and `TSW-120-15-G-D` ×3.

---

## 4. DRV8353 pad-function map — the datasheet, and a package finding

Source: **TI DRV835x datasheet, SLVSDY6A, `https://www.ti.com/lit/ds/symlink/drv8353.pdf`** —
*Pin Functions—48-Pin DRV8353R Devices*, **pages 8–9** (the function table) and the **48-pin RGZ package drawing on
page 8** (the pin numbering). PWM-mode truth tables: **page 30**. Buck-regulator block: **pages 46–47**.

### 4.1 The board's footprint is the 48-pin RGZ, and that is a *different device* from the original's

| | power board | original unsplit board |
|---|---|---|
| footprint | `QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm` | `WQFN-40-EP_6x6_P0.5` |
| value | `DRV8353` | `DRV8353SRTAR` |
| pins | **48** (7 × 7 mm VQFN) | **40** (6 × 6 mm WQFN) |

TI's family covers 32-, 40- and 48-pin versions; per the datasheet's own package column and the ordering information,
**the 48-pin 7 × 7 VQFN is the "R" variant (DRV8353R / DRV8353RS, RGZ)**, i.e. the one *with* the integrated buck
regulator — the pin-function table on p. 8 is headed "48-Pin DRV8353R Devices" and pins 42–48 are the buck block.
The generic "DRV8353" order code is the 40-pin RTA part. **So the board's BOM value is wrong for its footprint: the
part that fits is DRV8353RSRGZ (48-pin VQFN 7×7, SPI)** — DigiKey lists `DRV8353RSRGZR … 48 - VQFN (7x7)`
(<https://www.digikey.com/en/products/detail/texas-instruments/DRV8353RSRGZR/9692628>). A 40-pin RTA cannot be
placed on this land pattern, and a 48-pin RGZ has 7 pins with no function in the original design.

### 4.2 Pad → function → net (48-pin DRV8353RS; `M` = motor 1…6, driver → motor as in §4.3)

| pad | function (datasheet p. 8–9) | net assigned | other terminal on this board? |
|---:|---|---|---|
| 1 | GND — device power ground | `BATN` | yes (37 pads) |
| 2 | VGLS — 11 V regulator output, **needs 1 µF to GND** | `M#_VGLS` | **no — capacitor absent** |
| 3 | CPL — charge-pump flying cap, **47 nF to CPH** | `M#_CPL` | **no** |
| 4 | CPH — charge-pump flying cap | `M#_CPH` | **no** |
| 5 | VM — gate-driver supply ("connect to VDRAIN or separate supply") | `BATP` | yes (194 pads) |
| 6 | VDRAIN — HS drain sense / charge-pump reference | `BATP` | yes |
| 7 | VCP — charge-pump output, **1 µF to VDRAIN** | `M#_VCP` | **no** |
| 8 | GHA — high-side gate output A | `M#_GAH` | yes → FET gate pad |
| 9 | SHA — high-side source sense A ("connect to the HS MOSFET source") | `M#_PHA` | yes (18 pads) |
| 10 | GLA — low-side gate output A | `M#_GAL` | yes |
| 11 | SPA — shunt amp + / low-side source sense | `M#_SNA_K` | yes → leg-shunt Kelvin |
| 12 | SNA — shunt amp − ("low side of the shunt") | `BATN_K` | yes (36 pads) |
| 13 | SNB | `BATN_K` | yes |
| 14 | SPB | `M#_SNB_K` | yes |
| 15 | GLB | `M#_GBL` | yes |
| 16 | SHB | `M#_PHB` | yes |
| 17 | GHB | `M#_GBH` | yes |
| 18 | GHC | `M#_GCH` | yes |
| 19 | SHC | `M#_PHC` | yes |
| 20 | GLC | `M#_GCL` | yes |
| 21 | SPC | `M#_SNC_K` | yes |
| 22 | SNC | `BATN_K` | yes |
| 23 | SOC — shunt amplifier output C | `CSA_M#_C` | yes (header) |
| 24 | SOB | `CSA_M#_B` | yes |
| 25 | SOA | `CSA_M#_A` | yes |
| 26 | VREF — shunt-amp supply + reference, **0.1 µF to AGND** | `+3V3_REF_A` | yes, and `pinmap.md` says `+3V3_REF_A` = "BEC output = **DRV8353 VREF** + ADC VREF" |
| 27 | AGND | `AGND` | yes (25 pads) |
| 28 | nFAULT — open-drain, needs pull-up | `nFAULT_ALL` | yes (7 pads) |
| 29 | SDO — serial data out, needs pull-up | `SPI_MISO` | yes (7 pads) |
| 30 | SDI | `SPI_MOSI` | yes |
| 31 | SCLK | `SPI_SCLK` | yes |
| 32 | nSCS — serial chip select | `nCS_M#` | yes |
| 33 | ENABLE — gate-driver enable | `DRV_ENABLE` | yes, fan-out to 6 drivers per `pinmap.md` |
| 34 | INHA — HS gate control A | `PWM_M#_A` | yes |
| 35 | INLA — LS gate control A | `M#_DVDD` | yes (4 pads) — see below |
| 36 | INHB | `PWM_M#_B` | yes |
| 37 | INLB | `M#_DVDD` | yes |
| 38 | INHC | `PWM_M#_C` | yes |
| 39 | INLC | `M#_DVDD` | yes |
| 40 | DVDD — 5 V regulator out, **1 µF to DGND** | `M#_DVDD` | no capacitor — **but the 3 × INLx pins land on this net**, so it is routable |
| 41 | DGND | `DGND` | yes (30 pads) |
| 42 | SW — buck switch node | **not netted** | buck unused, no inductor |
| 43 | VIN — buck supply | **not netted** | buck unused |
| 44 | VCC — 7 V reg for the buck, **0.47 µF** | `M#_VCC` | **no** |
| 45 | BST — buck bootstrap, 0.01 µF to SW | **not netted** | buck unused |
| 46 | RCL — buck current limit, resistor to GND | **not netted** | buck unused |
| 47 | RT/SD — buck on-time, resistor to VIN | **not netted** | buck unused |
| 48 | FB — buck feedback divider | **not netted** | buck unused |
| 49 | exposed thermal pad → system ground | `BATN` | yes; the original board tied its EP to `M#_BATN` |

**Two datasheet facts drive the INLx decision.** The board exposes only **3 PWM lines per motor** (`PWM_M#_A/B/C`
on J_H2, `pinmap.md`), so the drivers must run **3x PWM mode**. The 3x truth table on **p. 30** is
`INLx = 0 → GLx = GHx = L (Hi-Z, half-bridge disabled); INLx = 1 → normal control`. INLx must therefore be held
**high**, and with no pull-up resistor on the board the only place to hold it is the driver's own 5 V rail, pin 40
DVDD. That is a datasheet-grounded net, not an invention — and it is the one net in the map that exists *only*
because the passive that should do the job is missing.

**The internal shunt amplifiers are used, and the external INA296A2 are not.** The original board is unambiguous
here: its DRV8353 pins 21/22/23 (SOA/SOB/SOC — shunt-amp outputs) drove `M#_CSA_A/B/C_RAW`, and its six INA296A2
sensed the **bus** shunt (`M1_BUS_SH_P/N` → `M1_BUS_CURRENT_RAW`, one per motor cell). The power board carries 18
leg shunts and exactly 18 `CSA_M#_A/B/C` header nets — a 1:1 match to 3 shunt amps × 6 drivers — so the leg-current
path is netted as the original did (SPx → leg-shunt Kelvin, SNx → bus-side Kelvin, SOx → `CSA_M#_x`). The 19
INA296A2 on this board have **no 1:1 destination**: 19 amplifiers against 18 leg shunts and 2 bus shunts (`RS1`,
`RS2`), with only 2 bus-current nets (`BUS_I_A`, `BUS_I_B`) on the header. They are left netless and flagged in §9
as a duplicate-owner design question, not silently netted to something plausible.

### 4.3 Driver → motor assignment

Solved from geometry (`scripts/06_netmap.py`): the cost of driver `d` to motor `m` is the mean distance from `d`'s
six gate-output pads to `m`'s six FET gate pads, minimised over all 6! = 720 assignments.

| | M1 | M2 | M3 | M4 | M5 | M6 |
|---|---:|---:|---:|---:|---:|---:|
| U11 | **34.05** | 72.57 | 114.43 | 31.56 | 71.41 | 113.69 |
| U12 | 90.28 | **75.03** | 82.50 | 63.88 | 39.63 | 52.30 |
| U13 | 101.16 | 78.78 | **76.70** | 78.50 | 46.29 | 42.59 |
| U14 | 76.12 | 94.57 | 125.76 | **41.56** | 69.82 | 108.41 |
| U15 | 79.83 | 76.04 | 94.32 | 48.04 | **41.42** | 69.49 |
| U16 | 110.71 | 84.08 | 74.74 | 90.49 | 54.78 | **39.05** |

The geometry-optimal assignment (U11→M1, U12→M5, U13→M3, U14→M4, U15→M2, U16→M6) totals **307.03 mm**; the
published sequential one (U11…U16 → M1…M6) totals **307.81 mm** — a **0.78 mm (0.25 %)** difference, i.e. degenerate.
I kept the published sequential assignment so the net map does not churn for no measurable gain, and report both.
Note the shape of the matrix: **M2 and M3 are badly served by every driver** (best 75.03 and 74.74 mm one-way), which
is why their gate loops cannot come near the best cell no matter how the assignment is drawn.

---

## 5. Applying the nets

`scripts/07_apply.py` — text surgery on a copy (`boards/n1_netted.kicad_pcb`), never a re-serialisation, so every byte
that is not a patched pad survives.

### 5.1 What was applied

| class | pads |
|---|---:|
| DRV8353: pads 1–41 and 49 (43 per driver × 6) | **258** |
| DRV8353 pads 42–48 (buck block, unused) left netless | 36 |
| DRV8353 paste apertures left alone | 96 |
| FET drain tabs: pad number restored `"" → "9"` **and** netted | **36** |
| **total netted this pass** | **294** |
| new net names declared | **36** (`M#_CPH`, `M#_CPL`, `M#_VCP`, `M#_VGLS`, `M#_VCC`, `M#_DVDD` × 6 motors) |

Of the 294, **30 sit on a net whose only other terminal is a missing capacitor** (`M#_VGLS`, `M#_CPL`, `M#_CPH`,
`M#_VCP`, `M#_VCC` — 5 per driver). They are netted because that is the design intent and a future schematic pass
needs the name, but they are *not* routable and they create no ratsnest edge. **264 of the 294 gain a real second
terminal.**

### 5.2 The 36 FET drain tabs — a footprint defect, not a missing net

The power board's `IPTC014N10NM5` land pattern has a 10.2 × 7.0 mm `F.Cu` pad with **no pad number and no net**. The
original board's FET footprint is the same part in `PG-HDSOP-16_TOLT_IPTC` and the same 10.2 × 7.0 pad is **pad
`"9"`, netted to the drain** (`/M4_BATP` for Q1405). So the tab is the FET's drain land and it lost its number when
the footprint was re-authored for this board. Left as is, **all 36 FETs have a floating drain land** — the largest
copper area in each device. Restoring `"9"` + the drain net (BATP for high-side, `M#_PHx` for low-side) is a net
restoration, not a geometry change.

### 5.3 Result, and the ratsnest jump

| | before | after | delta |
|---|---:|---:|---:|
| pads | 1,581 | 1,581 | 0 |
| netted pads | 825 | **1,119** | **+294** |
| netless pads | 756 | **462** | **−294** |
| declared nets | 173 | 209 | +36 |
| **unconnected items (kicad-cli)** | **0** | **258** | **+258** |
| **unconnected items (pcbnew, uncapped)** | **0** | **258** | **+258** |

**The jump from 0 to 258 is the correct, expected result and it is arithmetic, not an accident.** Each new
two-terminal net contributes exactly one ratsnest edge, each added pad to an existing net contributes one, and the
30 single-terminal nets contribute none:

| source of edges | edges |
|---|---:|
| 36 gate nets (driver gate pad ↔ FET gate pad) | 36 |
| 18 `CSA_M#_*` (DRV SOx ↔ header) | 18 |
| 18 `M#_SN*_K` (DRV SPx ↔ shunt Kelvin) | 18 |
| 6 `M#_DVDD` (4 pads → 3 edges each) | 18 |
| BATP +30 pads | 30 |
| BATN_K +18 pads | 18 |
| BATN +12 pads | 12 |
| phases `M#_PH*` +2 each | 36 |
| `SPI_SCLK/MOSI/MISO` +6 each | 18 |
| `+3V3_REF_A` +6, `AGND` +6, `DGND` +6 | 18 |
| `nFAULT_ALL` +6, `DRV_ENABLE` +6 | 12 |
| `nCS_M#` +1 each | 6 |
| `PWM_M#_*` +1 each | 18 |
| 30 single-terminal nets | 0 |
| **total** | **258** |

258 is what "the connections are now real" looks like on this netlist. A board that reports 0 unconnected while
carrying 756 netless pads is not routed; it is un-instrumented.

### 5.4 Copper untouched by the netlist edit

Every pre-existing top-level copper block is byte-identical between the input and the netted copy:

| block | input | netted | identical |
|---|---:|---:|---|
| `segment` | 134 | 134 | **yes** |
| `via` | 30 | 30 | **yes** |
| `zone` | 0 | 0 | **yes** |
| `gr_line` | 4 | 4 | **yes** |
| `gr_text` | 4 | 4 | **yes** |

### 5.5 The previous pass's 0-unconnected number was built on invisible pads

A netless pad is still a hole in the copper. `scripts/05_collide.py` (layer-aware, so a B.Cu bus under an F.Cu pad
is *not* counted) finds **24 electrical netless pads that already have another net's copper running through them on
the same layer**:

| component | pads | occupied by |
|---|---:|---|
| U20 (INA296A2) | 8 | a **4.00 mm-wide `BATN` track on F.Cu** passes diagonally through the whole SOT-23-8 footprint |
| U29 (INA296A2) | 6 | the same 4.00 mm `BATN` track |
| U40 (INA296A2) | 6 | `J_H2` header pin pads (`PWM_M3_A/B/C`, `DGND`) — the amplifier is placed on top of the header pin field |
| RS1 (bus shunt) | 3 | `J_H1`/`J_H2` header pin pads (`CAN_L`, `PWM_M4_A/B/C`, `DGND`) |
| H4 (mounting hole) | 1 | `J_H1` pins 9–12 |

So the earlier "0 unconnected" was achieved by a router that treated the 756 netless pads as free space — it routed a
4 mm `BATN` bus straight through two front-end amplifier footprints. That is why the netless population has to be
fixed *before* routing can be trusted, and it is why the INA296A2 and RS1 pads in this pass are left netless rather
than netted into a short (§9).

---

## 6. Routing: gate drive first — 27 of 36 nets, and the attempt fails DRC

**Read this section as a negative result with a measured cause, not as a pass.**

Router: raster A\* at 0.04 mm (`scripts/10_route_gates.py`), built on the previous pass's validated engine
(`evidence/esc-power-route/scripts/router2.py`) with per-layer STRtrees, a distance-transform via search over all four
copper layers, and an exact shapely legality check at the board's own 0.25 mm netclass clearance. Track 0.25 mm
(the `.kicad_pro` `min_track_width`), via 0.70/0.30 mm. Each gate net is
`F.Cu stub out of the driver pad → via → In1/In2 A* → via → F.Cu stub into the FET gate pad`.

### 6.1 What was achieved

**27 of 36 gate nets routed**, 2,440 track segments, 54 vias, **1,480.96 mm of gate etch** (1,394.67 mm on
In1/In2 + 86.28 mm of F.Cu escape stubs). Per cell, one-way etch (mm):

| cell | A-high | A-low | B-high | B-low | C-high | C-low | mean | worst |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | 33.67 | 23.46 | 49.08 | 34.28 | – | 51.52 | **38.40** | 51.52 |
| M2 | – | – | – | – | 99.89 | 74.24 | **87.06** | 99.89 |
| M3 | 84.11 | 69.00 | 88.07 | 73.77 | – | 90.89 | **81.17** | 90.89 |
| M4 | 32.87 | 49.12 | 38.37 | 52.85 | – | 71.33 | **48.91** | 71.33 |
| M5 | 32.72 | 48.81 | 38.28 | 52.73 | – | 71.83 | **48.87** | 71.83 |
| M6 | 32.78 | 48.88 | 36.02 | 50.16 | – | 52.25 | **44.02** | 52.25 |

global mean of cell means **58.07 mm**, best cell 38.40 mm, worst single net 99.89 mm.

### 6.2 Against the brief's numbers — they are a different quantity, and I say so

The brief's `54.61 / 137.88 / 140.10 / 69.89 / 69.65 / 65.52` are the **placement proxy** the previous pass used:
`loop = 2 × (nearest driver pad to the FET gate pad)`. My figure is **routed copper from the gate output pad to the
gate pad**, doubled on the same convention to make a loop:

| cell | routed etch (one-way) | **loop = 2 ×** | brief's placement proxy | difference |
|---|---:|---:|---:|---:|
| M1 | 38.40 | **76.81** | 54.61 | +22.20 (+40.7 %) |
| M2 | 87.06 | **174.13** | 137.88 | +36.25 (+26.3 %) |
| M3 | 81.17 | **162.33** | 140.10 | +22.23 (+15.9 %) |
| M4 | 48.91 | **97.81** | 69.89 | +27.92 (+39.9 %) |
| M5 | 48.87 | **97.75** | 69.65 | +28.10 (+40.3 %) |
| M6 | 44.02 | **88.03** | 65.52 | +22.51 (+34.4 %) |

The routed loop is longer than the proxy in every cell, which is what should happen: the proxy measures a straight
line between the *nearest* pad pair, while the routed figure has to reach the actual gate-output pin, climb out of a
0.5 mm-pitch QFN, change layer, and come back down. The two numbers bracket the same loop from below and above.
Note also that **no routed net is within 40.7 % of the brief's best cell (M1, 54.61 mm)** — the placement, not the
routing, sets that floor.

### 6.3 The 9 nets that did not route, and why

| net | driver pad | failure |
|---|---|---|
| M1_GCH, M3_GCH, M6_GCH | U1x.18 | no legal 0.7 mm via site at the driver end |
| M4_GCH, M5_GCH | U1x.18 | no legal via site at **either** end |
| M2_GBH | U12.17 | no legal via site at the driver end |
| M2_GAH, M2_GAL, M2_GBL | U12.8/10/15 | A\* found no path on In1 or In2 |

The GCH failures are geometric, not incidental: the `Q#CH` gate pad sits between the 8.0 × 1.2 mm phase land
(`CN#`, M#_PHC) and the 3.95–4.00 mm BATP bus on B.Cu, and a 0.70 mm via needs a 0.60 mm keep-out
(0.35 radius + 0.25 clearance) on **all four** layers. Measured over a ±6 mm box, only **2.11 %** of positions near
Q1CH's gate pad admit a legal via, and the nearest one is **4.72 mm** away — reachable only with a long F.Cu dog-leg
that then has nowhere clean to go. The M2 block (GAH/GAL/GBL) failed on congestion: U12 is the furthest driver from
its cell (§4.3) and by the time the shorter nets were routed, In1/In2 had no continuous corridor left.

### 6.4 The routed board FAILS DRC — and the cause is my router, measured

This must be stated plainly: **adding these 2,440 tracks introduces 204 shorting-item rows (exact, not capped) and at
least 499 clearance rows (that list is capped — see §7.2).** The routed board is therefore **not an acceptable board
and is not the deliverable of this wave.**

The cause is reproducible and measured, not hand-waved. Two nets that my router believes are separate were laid on
top of each other on In2.Cu:

| measurement | value |
|---|---|
| `M2_GCH` vs `M3_GAH`, minimum copper-to-copper distance on In2.Cu | **0.0000 mm** |
| where | `M2_GCH` at x = 94.62 mm, `M3_GAH` a 47.04 mm run at x = 94.82 mm |
| `M2_GCH` segments within 0.20 mm of `M3_GAH` | **1 132 of its 2 218** |
| `M2_GCH` was routed | after `M3_GAH` (sorted by span: 79.39 mm before 81.81 mm) |

`M3_GAH` was already in the engine's `added` list when `M2_GCH` was routed, so the A\* obstacle raster was supposed to
carry it and did not. That is a defect in **my** instrument — the incremental-obstacle path — not in the board and not
in the netlist. What it needs is a rerun with the added-copper raster rebuilt per net instead of incrementally; I did
not have budget to re-route 36 nets a third time after the failure was found, so I report the routing as
**27 nets of copper that cannot be shipped**, rather than quietly deleting the evidence or claiming the loop figures
as a win.

---

## 7. Verification

### 7.1 Unconnected, on both tools, uncapped

| board | kicad-cli | pcbnew (`GetUnconnectedCount(False)`, uncapped) | netted pads |
|---|---:|---:|---:|
| input `p2_routed` | **0** | **0** | 825 |
| netted `n1_netted` | **258** | **258** | **1,119** |
| routed `n2_final` | **231** | **231** | 1,119 |

Both tools agree exactly on both boards. The 0 → 258 jump is the netlist becoming real (§5.3); 258 → 231 is the 27
gate connections the router closed. **The board is at 231 unconnected, not 0.**

### 7.2 DRC, with companions, two rule configurations — and the list cap

Every run is in its own directory carrying the `.kicad_pro` (and, for cfg B, the 3 oz `.kicad_dru`), because a DRC
without companions invents violations:

| cfg | companions | board | violations | unconnected |
|---|---|---|---:|---:|
| A | `.kicad_pro` (netclass 0.25 mm) | `p2_routed` | 539 | 0 |
| A | | `n1_netted` | 539 | 258 |
| A | | `n2_final` | 747 | 231 |
| B | `.kicad_pro` + 3 oz `.kicad_dru` (0.200 mm) | `p2_routed` | 159 | 0 |
| B | | `n1_netted` | 159 | 258 |
| B | | `n2_final` | 750 | 231 |

**cfg A's clearance list is capped at 499 and is therefore not usable for a set diff** — its 499 clearance rows are
always full, so rows can only be "swapped", never added. The netting comparison in cfg B (119 clearance rows) is
below the cap and is the trustworthy one. **The routed board is over the cap in BOTH configurations** (cfg A 505,
cfg B 504 clearance rows). So on `n2_final` the **shorting-item count is exact (204) but the clearance count is a
floor (`≥499`, quoted as "capped")** — that is the one place in this report where a number is a bound, and it is
labelled as such everywhere it appears.

**Set diff, netting step (`p2_routed` → `n1_netted`), cfg B — the answer to "does adding nets create shorts":**

| type | input | netted | delta |
|---|---:|---:|---:|
| clearance | 119 | 119 | **+0** |
| shorting_items | 3 | 3 | **+0** |
| silk_over_copper | 29 | 29 | **+0** |
| solder_mask_bridge | 8 | 8 | **+0** |
| **set diff** | | | **GONE 0 / ADDED 0** |

So **the netlist fix creates no short and no clearance violation** under the real 3 oz rule set. (Under cfg A the same
step shows 120 gone / 120 added, all of them the FET footprint's own drain-tab-to-source gap of exactly 0.200 mm,
which is legal at the 0.200 mm pattern class and illegal at 0.250 mm — §7.3.)

**Set diff, routing step (`n1_netted` → `n2_final`), cfg B:**

| type | netted | routed | delta |
|---|---:|---:|---:|
| shorting_items | 3 | 204 | **+201** (exact) |
| clearance | 119 | 504 | **≥+385** (*capped at 499*) |
| hole_clearance | 0 | 4 | +4 |
| solder_mask_bridge | 8 | 9 | +1 |
| silk_over_copper | 29 | 29 | 0 |

The routing is not clean. §6.4 gives the measured cause.

### 7.3 The one new violation class introduced by the netlist edit, and why it is legal

Giving the FET drain tabs their net makes KiCad check a gap it previously ignored: inside every one of the 36
`IPTC014N10NM5` footprints, the **10.2 × 7.0 mm drain tab is 0.200 mm from its own source pads**. Before netting, both
were net-0 and the pair was not compared; after netting they are `BATP` vs `M#_PHx` (or `M#_PHx` vs `M#_SNx`) and the
0.200 mm gap is a real different-net gap. At the approved **0.200 mm pattern class for 105 µm copper** it is legal and
cfg B reports **+0**; at the generic 0.250 mm netclass it is a violation. This is a footprint property, present in the
input copper, and it is not something the netlist pass changed.

### 7.4 The already-routed power path is untouched

Every pre-existing top-level copper block is byte-identical between `n1_netted` and `n2_final`:

| block | parent | final | lost | added |
|---|---:|---:|---:|---:|
| `segment` | 134 | 2,574 | **0** | 2,440 |
| `via` | 30 | 84 | **0** | 54 |
| `zone` | 0 | 0 | 0 | 0 |
| `gr_line` | 4 | 4 | 0 | 0 |
| `gr_text` | 4 | 4 | 0 | 0 |

and the protected widths, counted per net and per layer:

| net | required | measured |
|---|---|---|
| 18 phase nets `M1_PHA` … `M6_PHC` | 6.00 mm | **6.00 mm F.Cu × 1 each — UNCHANGED** |
| `BATN` | 4.00 mm columns | **4.00 mm F.Cu × 43 — UNCHANGED** |
| `BATP` | 3.00 mm | **3.00 mm F.Cu × 2, 3.95 mm B.Cu × 1, 4.00 mm B.Cu × 1 — UNCHANGED** |
| leg-shunt taps | 4.00 mm | covered by the `BATN` 4.00 mm population (unchanged) |

**Nothing was moved, resized or deleted — only copper was added.** No ampacity claim is reduced.

### 7.5 Only the three 2×20 headers are on B.Cu

Footprints whose layer is `B.Cu`: **`J_H1`, `J_H2`, `J_H3`** — exactly three, exactly those. Confirmed
**`ONLY J_H1..J_H3 ON B.Cu: True`**.

---

## 8. Package

**Not produced.** Step 7 of the assignment makes packaging conditional on the board ending at **0 unconnected with a
clean DRC set diff**. It ends at **231 unconnected** with **+201 shorting rows** from the routing attempt, so
regenerating a manufacturing package (ENIG, revision stamp, drill/G85 census, POS reconcile, manifest) would
manufacture a pass. No package, no drills, no POS, no manifest was generated for this wave.

---

## 9. Verdict

**IS THE POWER BOARD NOW COMPLETE? — NO.**

What is now true, and is a real step forward:

- The netlist defect is **characterised and partially fixed**: 294 pads netted (258 DRV8353 + 36 FET drain tabs),
  netted pads 825 → **1,119**, netless 756 → **462**, with **zero DRC rows and zero shorts created** (cfg B set diff
  0 / 0) and all pre-existing copper byte-identical.
- The DRV8353 pad-function map is derived from the datasheet, cited, and applied pin by pin (§4.2), including the
  package correction (48-pin RGZ = DRV8353RS, not the 40-pin RTA the BOM names) and the 3x-PWM consequence for INLx.
- The gate drive is no longer un-routable-in-principle: 27 of 36 gate nets now have real copper with measured loops
  of 76.81 / 174.13 / 162.33 / 97.81 / 97.75 / 88.03 mm against the brief's placement proxy
  54.61 / 137.88 / 140.10 / 69.89 / 69.65 / 65.52 mm (§6.2).

Why it is still **not** complete — five separate blockers, each of which is a hardware or schematic fact that routing
cannot fix:

1. **462 pads are still netless, and 30 of the pads I did net have no partner because the passive does not exist.**
   Every DRV8353 needs a VCP 1 µF, a CPH–CPL 47 nF, a VGLS 1 µF, a DVDD 1 µF and a VCC 0.47 µF; **none of these
   capacitors is on the board**, and there are **no gate resistors anywhere** either. The board has no passives at
   all except the shunts and the bulk capacitors. A DRV8353 without charge-pump capacitors cannot switch.
2. **The DRV8353 part number does not match its footprint.** The land is a 48-pin 7 × 7 VQFN; the BOM says
   "DRV8353", which is the 40-pin 6 × 6 RTA part the *original* board used. The orderable part that fits is
   DRV8353RSRGZ — and it carries a buck regulator whose 7 pins (42–48) have no components and are left as
   no-connects here.
3. **The current-sense architecture has two owners.** Six DRV8353 internal shunt amplifiers and nineteen INA296A2
   are both placed; the header exposes 18 `CSA_M#_x` nets (3 per motor) plus 2 bus-current nets. I netted the
   original board's topology (DRV internal amps for the legs). That leaves **152 INA296A2 pads netless**, and 14 of
   them already have other nets' copper through them (§5.5), so they cannot be netted without moving copper.
4. **144 pads on J1–J6 and 18 on the motor lands are not nettable at all.** J1–J6 are 2×12 THT connectors sitting in
   the routing channels with live copper **0.30 mm** from their pads; P1–P18 are 18 single lands behind the BATP
   bar with no determinable phase assignment. Netting either would be a guess, and a wrong guess on P1–P18 is an
   inter-phase short.
5. **The routing is 75 % done and does not pass DRC** (204 shorting rows, §6.4, cause measured and mine).

So: the *data* half of this wave succeeded and is verified clean; the *copper and hardware* half did not, and the
board remains un-orderable. The next pass should (a) add the missing DRV passives and gate resistors, (b) fix the
DRV8353 order code to the RGZ part, (c) decide the single current-sense owner, (d) delete or re-place J1–J6 and
define the motor lands, and (e) rerun the gate router with the added-copper raster rebuilt per net.