# ESC POWER — Gate-Drive Support Parts, and the DRV8353 Package

**Wave:** esc-power-passives · **Date:** 2026-11-19 · **Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), pcbnew 9.0.7 + `kicad-cli`, bundled Python 3.11.5 (numpy 2.3.5, scipy 1.17.1, shapely 2.2.0)
**Scope:** resolve the DRV8353 order code against the 48-pin RGZ land; add the gate-drive support parts the board is missing (charge pump, the VGLS/DVDD regulators, the VM decoupling, and the 36 gate resistors); place them; net and route them; verify the already-routed power path is untouched. Package only if the board reaches 0 unconnected with a clean DRC set diff.
**Write scope:** `evidence/esc-power-passives/` only, on copies. Nothing written to a repo, `D:\CodeProjects` or `E:\1vm\TMP`.

---

## 0. Verification status (read this first)

| Claim | Status |
|---|---|
| DRV8353 package resolved against the ordering table, with citation | **DONE** — §2. 48-pin RGZ = the "R" device; the BOM's `DRV8353` is the 40-pin RTA and cannot be placed here |
| The 48-pin RGZ orderable part named | **DONE** — `DRV8353RSRGZR` / `DRV8353RSRGZT` (§2.4) |
| Does this board need the integrated-current-sense variant (it has 19 INA296A2) | **DONE, and the premise is wrong** — no DRV8353 variant lacks the amps; the no-amp 48-pin RGZ part is the *other* family, DRV8350RSRGZ (§2.5) |
| Passive list enumerated with value / package / function / citation | **DONE** — §3, TI SLVSDY6A Table 21 p. 67 + pin table pp. 8–9 |
| 36 gate resistors added | **DONE** — 36 placed, but see §3.4: TI requires none; they are 0 Ω option links |
| Bootstrap-capacitor question answered from the topology | **DONE** — §3.5: no bootstrap capacitor exists in a charge-pump gate drive |
| Placement legality (no copper row added) | **DONE** — §4.2: 0 courtyards overlap, 0 copper rows; **+4** silk-clip rows (§4.3) |
| Gate loop length per phase vs 54.61/137.88/140.10/69.89/69.65/65.52 mm | **DONE, and it gets WORSE** — §4.4: the brief's proxy is reproduced to 0.01 mm and rises by +21.2 to +27.0 mm because a series element cannot shorten a path |
| Routing kept / attempted, per batch | PENDING (§5) |
| DRC set diff per batch (full companions) | PENDING (§5) |
| Power path intact (18×6.00 mm, BATN 4.00 mm, BATP 3.00 mm, 0/134 seg, 0/30 via, J_H1–J_H3 on B.Cu) | PENDING (§6) |
| Final unconnected on both tools | PENDING (§5.4) |
| Package produced | PENDING (§7) |
| **VERDICT: IS THE POWER BOARD COMPLETE AND ORDERABLE?** | PENDING (§8) |

---

## 1. Inputs, and what this pass started from

| item | path | figures |
|---|---|---|
| input board | `evidence/esc-power-nets/boards/n1_netted.kicad_pcb` | 627,551 B, 173 footprints, **1,581 pads, 209 nets**, 134 segments, 30 vias, **258 unconnected** |
| its provenance | `evidence/esc-power-nets/REPORT.md` | the power path as routed in `esc-power-route` (134/30, byte-identical), plus 294 pads netted so the DRV8353 and the FET drain tabs have nets |
| DRC companions | `evidence/esc-power-route/boards/p2_routed.kicad_pro` (netclass 0.25 mm) + `.kicad_dru` (3 oz, pattern class 0.200 mm) | every run below carries them; a run without them invents rows |
| datasheet | `evidence/esc-power-nets/rows/drv8353.pdf` = TI **SLVSDY6A** (Aug 2018, rev. June 2019), 101 pp. | text extracted to `rows/ds_pages.txt` with page tags, so every citation is a page |

The starting board reproduces the previous wave exactly: **539 violations in cfg A, 159 in cfg B, 258 unconnected**
(`drc/A_n1`, `drc/B_n1`). That equality is the check that this wave's DRC harness is the same instrument as the
last one's, not a looser one.

Two of the previous wave's premises are corrected here, both measured:

1. **"the 3 × INLx pins land on M#_DVDD, so that net is routable" is false.** Pins 37/39/40 all sit on the
   driver's **top** pad row, and that row is **0.72 mm** from the motor land above it (§5.5). A 0.25 mm track
   with 0.25 mm clearance needs 0.75 mm. The whole top row is boxed in.
2. **"the absence of gate resistors is the measured cause of the shorts" is not what the datasheet says** (§3.4).
   The measured cause of the previous pass's 204 shorting rows was that pass's own incremental obstacle raster;
   the fix for that is a per-segment legality gate, which §5 uses, not a series resistor.

---

## 2. STEP 1 — the DRV8353 package decision

### 2.1 The family table settles the land, and it is not the part the BOM names

TI SLVSDY6A **Table 1, "Device Information", page 1**:

| PART NUMBER | PACKAGE | BODY SIZE (NOM) |
|---|---|---|
| DRV8350 | WQFN (32) | 5.00 mm × 5.00 mm |
| DRV8350R | **VQFN (48)** | **7.00 mm × 7.00 mm** |
| DRV8353 | **WQFN (40)** | **6.00 mm × 6.00 mm** |
| DRV8353R | **VQFN (48)** | **7.00 mm × 7.00 mm** |

The board's land is `QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm`. **A 48-pin 7 × 7 VQFN is the "R" body in this family,
and nothing else.** The BOM value `DRV8353` is the 40-pin 6 × 6 RTA part — the part the *original* unsplit board
used (`DRV8353SRTAR`, `WQFN-40-EP_6x6_P0.5`). A 40-pin RTA cannot be placed on this land, and the DRV8353R's
7 extra pins (42–48, the buck block) have no counterpart on the RTA.

TI's own product page for the 48-pin device states the package explicitly: **"VQFN (RGZ) 48, 49 mm²
(7 mm × 7 mm)"** (<https://www.ti.com/product/DRV8353R>), and its "similar functionality" sibling is listed as
*DRV8353 — No integrated buck regulator*, i.e. the 40-pin part
(<https://www.ti.com/product/DRV8353>).

### 2.2 What actually differs between RTA and RGZ

| | DRV8353 (RTA, 40-pin) | DRV8353R (RGZ, 48-pin) | citation |
|---|---|---|---|
| pins | 40 | 48 | Table 1 p. 1; pin tables pp. 5–9 |
| exposed pad | yes, WQFN 6 × 6 | yes, VQFN 7 × 7, EP 5.6 × 5.6 | pp. 6, 8 |
| gate outputs | 6 (GHA/GLA/GHB/GLB/GHC/GLC) | 6, same names | pp. 6, 8 |
| charge pump | CPH/CPL/VCP present | CPH/CPL/VCP present | pp. 6, 8 |
| **integrated shunt amps** | **yes, 3 (SOA/SOB/SOC)** | **yes, 3 (SOA/SOB/SOC)** | pp. 6, 8; "the current-sense amplifiers on the DRV8353 *and DRV8353R* SPI devices" p. 45 |
| **buck regulator** | **no** | **yes — pins 42–48 (SW, VIN, VCC, BST, RCL, RT/SD, FB)** | pp. 5, 8; §9.2.1.2.7 p. 71 |
| interface option | H or S | H or S | p. 33 |

**So the only functional difference that the land forces on this design is the buck regulator**: on RGZ you get a
buck you did not ask for, and its seven pins have to be dealt with.

### 2.3 SPI or hardware: the board's own nets decide

The H/W variants "convert the four SPI pins into four resistor configurable inputs, GAIN, IDRIVE, MODE and VDS"
(p. 33). This board nets pads **29–32** (`SDO`, `SDI`, `SCLK`, `nSCS`) to `SPI_MISO`, `SPI_MOSI`, `SPI_SCLK`,
`nCS_M#` (`evidence/esc-power-nets/REPORT.md` §4.2). Those four pads exist only on the **S** device. Therefore the
ordering code carries `S`.

### 2.4 The orderable part

**`DRV8353RSRGZR` (reel) / `DRV8353RSRGZT` (tube)** — 48-pin VQFN 7 × 7, SPI, buck, triple shunt amps.
Distributor listing confirming the package/interface pairing: *DRV8353RSRGZT — Multiphase Motor Driver Power
MOSFET SPI 48-VQFN (7x7)* (<https://www.digikey.com/en/products/detail/texas-instruments/DRV8353RSRGZT/9642041>;
the page itself is behind a bot wall, the title/metadata is what is cited).
TI package designator **RGZ** = VQFN-48 7 × 7, drawing MPQF123F, linked from the product page above.

**Decision: order `DRV8353RSRGZR` and change the BOM value from `DRV8353` to `DRV8353RSRGZ`.**
The seven buck pins (42–48) are left unconnected; the buck cannot switch because VIN (pin 43) is unconnected, so
its external components (Table 22 p. 68: `CBST`, `CVCC`, `LOUT`, `DOUT`, `COUT`, `RFB1/2`, `RRT/SD`, `RRCL`) are
not needed and are not added. **This is a design decision with a residual risk** — TI gives no "unused buck"
recipe, and pin 44 (`VCC`) then has no bypass, which datasheet p. 48 only requires *when the buck is switching*.
It is flagged for review, not silently accepted.

### 2.5 "If the board has external INA296A2s it may not need the integrated-amp variant"

This is the one place the brief's premise does not survive the datasheet, and the correction matters for
procurement:

- **There is no amp-less DRV8353.** The amps are on the 40-pin `DRV8353` and the 48-pin `DRV8353R` alike (Table 1
  p. 1; pin table pp. 5–9; register note "Driver Configuration Register (DRV8353 **and DRV8353R** Only)" p. 64).
  The variant axis in this family is **buck present/absent** and **SPI vs hardware**, not amps present/absent.
- **The amp-less 48-pin RGZ part is a different family**: `DRV8350R`, whose 48-pin pin table (p. 5) is
  pin-for-pin the same land with `NC` on 12, 13, 22, 23, 24, 25, 26, 32 — i.e. **pads 23/24/25 (`SOA/SOB/SOC`)
  become no-connects**. That is the part that "does not need the integrated amps", and it drops into the same
  48-pin RGZ land. Orderable as `DRV8350RSRGZR` (SPI) per the p. 5 column head `DRV8350RH | DRV8350RS`.

**Which one does *this* board need?** The board's netting already commits to the internal amps: pads 23/24/25 are
netted `CSA_M#_A/B/C` and land on 18 leg shunts (3 amps × 6 drivers = 18 header nets, a 1:1 map). The 19
INA296A2 have no 1:1 destination — 19 amplifiers against 18 leg shunts plus 2 bus shunts (`RS1`, `RS2`) and only
2 header bus-current nets (`BUS_I_A`, `BUS_I_B`) — and 152 of their pads are still netless, 14 of them with other
nets' copper through them (`esc-power-nets` §5.5). The board is therefore built around the **internal** amps.

**Decision: `DRV8353RSRGZ`.** If the owner instead decides the INA296A2 own the current sense, `DRV8350RSRGZ`
is the drop-in on the same land and pads 23–25 become NC — but that is an owner decision about the
current-sense architecture, not a package question, and it does not change the land, the passives, or the
gate resistors in this report.

### 2.6 The `TPS7H6022RGZEVM` check the brief asked for

`https://www.ti.com/product/TPS7H6022` returns **HTTP 404** (checked 2026-11-19), as does
`https://www.ti.com/product/TPS7H6022RGZEVM`. There is no TI catalogue page for that device or that EVM, so
"the same question" cannot arise from it — **a precise negative, not an assumption of absence**. What *does*
generalise, and is the real lesson of §2.1: **`RGZ` is TI's package designator (VQFN-48, 7 × 7), reused across
families — it pins the package, never the device.** A KiCad land pattern named after the package therefore
cannot validate a BOM line; the BOM's device field has to be checked against the **package column of that
device's own ordering table**, which is exactly the 30-second check that this board's BOM skipped.

---

## 3. STEP 2 — the missing passives

### 3.1 The list, from the datasheet's own external-component table

TI SLVSDY6A **Table 21, "DRV835x Gate-Driver External Components", page 67** — with the per-pin requirements from
the pin-function table (pp. 8–9) and the charge-pump description (§8.3.1.3, p. 34):

| # | ref (new) | value | package | between | why / citation |
|---:|---|---|---|---|---|
| 1 | `CVCP` ×6 | **1 µF, 16 V, X7R** | 0603 | `VCP` (pin 7) — `VM`/`VDRAIN` (pin 6, net `BATP`) | charge-pump **storage** capacitor. Table 21 p. 67; p. 34: "requires a X5R or X7R, 1-µF, 16-V ceramic capacitor between the VDRAIN and VCP pins" |
| 2 | `CSW` ×6 | **47 nF, VDRAIN-rated (100 V), X7R** | 0603 | `CPH` (pin 4) — `CPL` (pin 3) | charge-pump **flying** capacitor, the one part that makes the doubler work. Table 21 p. 67; p. 34 |
| 3 | `CVGLS` ×6 | **1 µF, 16 V, X7R** | 0603 | `VGLS` (pin 2) — `GND` (pin 1, net `BATN`) | low-side 11 V regulator output. Table 21; p. 34: "requires a X5R or X7R, 1-µF, 16-V ceramic capacitor between VGLS and GND" |
| 4 | `CDVDD` ×6 | **1 µF, 6.3 V, X7R** | 0402 | `DVDD` (pin 40) — `DGND` (pin 41) | 5 V regulator output; also the reference the 3 × INLx pins are tied to. Table 21; p. 38; p. 9 pin 40 |
| 5 | `CVM1` ×6 | **0.1 µF, VM-rated (100 V)** | 0402 | `VM` (pin 5, net `BATP`) — `GND` (`BATN`) | local VM decoupling. Table 21 (`CVM1`); p. 6 pin 5: "0.1-µF, VM-rated ceramic **and** ≥ 10-µF local capacitance" |
| 6 | `CVM2` ×6 | **10 µF, 100 V, X7R** | 1210 | `BATP` — `BATN` | the "≥ 10-µF local capacitance" half of the same sentence (Table 21 `CVM2`; p. 6) |
| 7 | `CVREF` ×6 | **100 nF, 16 V, X7R** | 0402 | `VREF` (pin 26) — `AGND` (pin 27) | shunt-amp supply/reference bypass. p. 9 pin 26: "Connect a X5R or X7R, 0.1-µF, 6.3-V ceramic capacitor between the VREF and AGND pins"; Table 21 lists it as `CVREF` (optional) |
| 8 | `R1…R36` ×36 | **0 Ω** | 0402 | driver gate output → FET gate | 6 outputs × 6 drivers. **See §3.4** |

Total added: **42 capacitors + 36 resistors = 78 parts**, on 6 drivers. Placed: **78 of 78** (§4).

### 3.2 The parts already on the board that this list does *not* duplicate

`C1–C6` (820 µF) are the bulk bus capacitors and are **not** `CVM2`: each sits in a **one-pad** footprint
(`820uF_35V`, one 8.0 × 8.0 land), so both terminals land on the same copper — a capacitor that cannot do
anything, and if populated, a short across its own terminals. That is a carried-over defect from
`esc-power-nets` §2, restated here because `CVM2` (10 µF) is only credible as *additional* local decoupling
while those six are unusable. It is not fixed in this wave (out of scope) and is listed in §8.

### 3.3 What is deliberately NOT added, and why

- `RnFAULT` / `RSDO` pull-ups (Table 21): the board's `nFAULT_ALL`, `SPI_MISO` nets already carry pads on the
  header side; adding a second pull-up would duplicate an existing owner. Not this wave's defect.
- `RIDRIVE` / `RVDS` / `RMODE` / `RGAIN` (Table 21, "DRV835x hardware interface"): this board uses the **SPI**
  device, where those four pins do not exist (they are the H/W variant's substitution, p. 33). Nothing to add.
- `CBST`, `CVCC`, and the rest of Table 22 (buck, p. 68): the buck is not used (§2.4).
- The 820 µF bulk repairs, the INA296A2 question, J1–J6, and the motor lands P1–P18: other owners' blockers,
  unchanged by this wave (§8).

### 3.4 The 36 gate resistors — what the datasheet actually says

**The datasheet does not ask for them, and the schematic it publishes does not have them.**
Table 21 (p. 67) is the complete external-component list for the gate driver and contains **no series gate
resistor**; the primary application schematic (Figure 63, p. 66) wires `GHA`, `GLA`, `GHB` … straight to the
MOSFET gates. The reason is the architecture: "The DRV835x uses smart gate drive (SGD) architecture to decrease
the number of external components that are typically necessary for MOSFET slew rate control" (p. 1), with the
slew rate set by `IDRIVE` (7-level, §9.2.1.2.2 p. 68) instead of by `Rg`. TI states the position directly on its
own support forum, for this exact EVM:

> "Technically there is no requirement. The smart gate drive architecture replaces the need for the gate drive
> resistor as gate drive resistors simply result in a changed rise and fall time to the FET. The adjustable gate
> drive current within the device will do the same thing. However, feel free to put a 0 ohm resistor in series
> with the gate just in case it needs to be adjusted in-between …"
> — TI E2E, *DRV8353RS-EVM: DRV8353 used inverter design*
> (<https://e2e.ti.com/support/motor-drivers-group/motor-drivers/f/motor-drivers-forum/961857/drv8353rs-evm-drv8353-used-in-inverter-design>)

So the 36 resistors are added **as 0 Ω option links**, which is exactly the practice TI endorses: with 0 Ω
stuffed the gate path is the electrical path TI designed (slew set by `IDRIVE`); with a non-zero value stuffed
later they become a tuning element. **They are not a short-circuit fix.** What fixed the previous pass's shorts
is the per-segment legality gate in §5 — and the measured cause of those shorts was that pass's own router
(`esc-power-nets` §6.4: `M2_GCH` 0.0000 mm from `M3_GAH`, introduced by the incremental obstacle raster), not a
missing component. Stating that plainly is the point: adding 36 parts to a board to fix a software defect would
have been a manufactured cause.

### 3.5 Bootstrap capacitors — the topology does not have one

**None are added, because a charge-pump gate drive has no bootstrap capacitor.** The high-side supply is "a
doubler charge pump that operates from the VM and VDRAIN voltage supply inputs … regulated to keep a fixed output
voltage of VVDRAIN + 10.5 V" (p. 34), whose storage element is `CVCP` (1 µF, VCP–VDRAIN) and whose flying
element is `CSW` (47 nF, CPH–CPL) — both in §3.1. The only `BST` pin in the datasheet is the **buck regulator's**
bootstrap (pin 45, "Connect a X5R or X7R, 0.01-µF, 16-V capacitor between the BST and SW pins", p. 5), and the
buck is unused (§2.4). No `CBST` is therefore required or added.

---

## 4. STEP 3 — placement

### 4.1 Method

`scripts/05_place.py`. Placement is solved, not drawn: for each of the 78 parts the two pad centres are fixed
grid offsets, so the "is this spot clear" test is a pair of shifted distance-transform lookups on the F.Cu
clearance field (0.05 mm raster, against the file's copper **and** every part already placed), and the cost is
`pad1 → its driver pin` plus `0.6 × pad2 → its partner`. The K cheapest spots are then re-checked exactly with
shapely against the real pad polygons, against every existing footprint's courtyard (DRC flags
courtyard-vs-courtyard), and against the board edge. Each part must also sit outside a **5.0 mm square ring**
around its own driver, so the 0.5 mm-pitch pad escapes stay open.

Result: **78 of 78 placed** (36 `R`, 6×`CVCP`, 6×`CSW`, 6×`CVGLS`, 6×`CDVDD`, 6×`CVM1`, 6×`CVM2`, 6×`CVREF`).
Gate resistors land **1.83–5.76 mm** from their own driver gate pin (median 2.53 mm), i.e. inside the driver's
own escape, which is the only place a series element does not add a detour of its own.

The four parts that had to be searched wide are the two bus parts per driver: `CVM2` sits 4.0 mm from its driver
on five cells, and on **M1 it could only be placed 36.8 mm away** (`C13` at 4.825, 80.825) because `U11` sits in
the board corner behind the M1 phase lands. `CVM1` on M1 is 10.0 mm away for the same reason. Both are
bus-decoupling parts, so distance costs damping, not function — but it is a placement weakness of `U11`, stated
rather than hidden.

### 4.2 DRC effect of the placement alone: 0 copper rows

| cfg | board | violations | unconnected | notes |
|---|---|---:|---:|---|
| B | `n1_netted` (input) | **159** | 258 | clearance 119, shorting 3, mask-bridge 8, silk 29 |
| B | `g1_parts` (placed) | **163** | 378 | clearance **119**, shorting **3**, mask-bridge **8**, silk **33** |
| **set diff** | | | | **ADDED 4, GONE 0** — all four are `silk_over_copper`, zero are copper |

The first placement attempt added **28 `courtyards_overlap` and 6 `silk_over_copper`** rows; both were then
designed out, not accepted: the courtyard test now runs against every existing footprint's real courtyard
(`STRtree`), and the new parts' library silk outline is moved to `F.Fab` (the fab outline is kept for
documentation, the reference designators are hidden and come from the POS file instead). The remaining **+4**
silk rows are existing silkscreen being clipped by the *new parts'* solder-mask openings — the same class the
board already carries 29 of, and the class every fab clips automatically. No clearance, short, width, hole or
annular-ring row is added by placement.

**Companion check, measured rather than assumed:** the same board DRC'd with and without an `fp-lib-table` +
local `.pretty` gives **identical results (0 gone / 0 added)**, so on this host the `.kicad_pro` (+ `.kicad_dru`)
is what matters and the footprint-library companion changes nothing. That is recorded because the brief warns
that DRC without companions invents violations — true for the `.kicad_pro`, not measurable for the library table.

### 4.3 The unconnected jump is arithmetic, and it reconciles exactly

258 → **378** is **+120**, and `scripts/09_netcount.py` accounts for every edge:

| source | edges |
|---|---:|
| 36 gate nets split by the series resistor (each `M#_Gx` gains the resistor's pad: 2 pads → 3) | 36 |
| 6 × `M#_CPH`, 6 × `M#_CPL`, 6 × `M#_VCP`, 6 × `M#_VGLS` (single-pad nets gain their cap pad) | 24 |
| 6 × `M#_DVDD` (4 pads → 5) | 6 |
| `BATP` 194 → 212 pads, `BATN` 49 → 67 (the two bus caps per driver) | 36 |
| `DGND` 30 → 36, `AGND` 25 → 31, `+3V3_REF_A` 7 → 13 | 18 |
| the 36 new `M#_Gx_D` nets are **single-pad** nets and need no edge | 0 |
| **total** | **120** |

Measured +120. A board that reports 0 unconnected while carrying a dead charge pump is not routed; this one
now reports the true size of the job.

### 4.4 STEP 3's actual answer: the loops get **worse**, and they cannot do anything else

The brief's six numbers are the previous pass's placement proxy: per FET,
`2 × (FET gate pad → nearest pad of ANY kind on the owning driver)`, then the cell mean. Recomputed here from
`p2_routed`'s geometry it reproduces **exactly**: 54.61 / 137.88 / 140.10 / 69.90 / 69.65 / 65.52 (published
69.89, a 0.01 rounding difference). Same instrument, same numbers.

| cell | brief's proxy | **after the parts are placed** | delta | worst gate | prior pass's *routed* loop |
|---|---:|---:|---:|---:|---:|
| M1 | 54.61 | **81.65** | **+27.04** | 104.27 | 76.81 |
| M2 | 137.88 | **159.10** | **+21.22** | 174.33 | 174.13 |
| M3 | 140.10 | **162.47** | **+22.37** | 183.09 | 162.33 |
| M4 | 69.89 | **91.96** | **+22.07** | 110.84 | 97.81 |
| M5 | 69.65 | **91.68** | **+22.03** | 110.48 | 97.75 |
| M6 | 65.52 | **86.94** | **+21.42** | 103.12 | 88.03 |

**Read this as a negative result with a measured cause, not as a pass.** A series element sits *in* the path:
`d(pin → R) + body + d(R → FET) ≥ d(pin → FET)` always, by the triangle inequality, and the measured excess is
`pin→R` (1.83–5.76 mm) + the 0402 body (1.02 mm) + a small angular penalty. **No placement of a gate resistor
can improve the brief's proxy** — that proxy measures a straight line between two fixed pads. The only way to
move those six numbers down is to move the *drivers*, which is a different decision with its own evidence
(the previous pass measured that M2 and M3 are badly served by every driver: best one-way 75.03 and 74.74 mm).

What the placement *did* achieve is that the added length is the minimum physically available: every resistor
is inside its driver's own escape, and the extra is `pin→R + body` (2.85–6.78 mm one-way) rather than a detour
around the QFN. The routed figures that this change actually competes with are in §5.6.