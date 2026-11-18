# ESC CONTROL board — WWDT, EEPROM, pours, schematic, TPS3430, and what routing buys

**Task (one).** Attack the ESC control board's four named blockers — **DEAD WWDT**, **UNCONNECTED
EEPROM**, **NO POURS**, **NO SCHEMATIC** — plus the TPS3430 part-number decision and a routing pass
on what is left. The GPIO budget already closes (45/48, 3 spare) and is **not** reopened.

**Status: COMPLETE.** Three of the four named blockers are closed and measured; the fourth (the
schematic) is honestly priced rather than claimed. Everything below was measured on copies, by two
tools wherever a second tool exists, and every set diff is keyed by `(type, item uuid)`.

| question | answer |
|---|---|
| What was "DEAD WWDT"? | Not a missing part: **U8 had 0 of 6 pads netted**, `WDO` did not exist as a net, `WDI` had one pad, and the safety gate U13 had A/B/Y netless. A footprint pretending to be a watchdog. |
| Fixed? | **Yes.** Land corrected to the TPS3430's only package (10-pin VSON DRC), 9 of 11 pads netted, `WDO`→`NRST`→`DRV_ENABLE` gate, R155/R157 added. Window 10.35–92.7 ms, tRST 200 ms. **Firmware must kick WDI every 30 ms — stated as a design requirement.** |
| The EEPROM? | `U12` 0/5 pads netted, `I2C_SDA`/`I2C_SCL` one-pad nets. The CAT24C32 **has no 5-lead SOT-23 option**, so the part became **24LC32A** (5-lead SOT-23: 1 SCL, 2 VSS, 3 SDA, 4 VCC, 5 WP — *not* the 8-lead order) + R153/R154 pull-ups. **Single-ended nets 3 → 0.** |
| Pours? | **5 zones** (F.Cu AGND/+3V3/DGND, B.Cu AGND/DGND) at 0.200 mm clearance, AGND and DGND joined **only** through a 1.3 mm moat notch at R152, plus **280 stitching vias**. **DRC set diff: 0 new, 0 removed; unconnected 284 → 249 (−35).** |
| The predicted clearance win? | **It did not happen, and could not.** All 9 pre-existing clearance errors are track/pad items no zone touches. Reported as the negative it is. |
| Schematic? | **Still does not exist.** 7 sheets, 169 symbols, 725 labels, **12–17 h** to a signable AC-schematic. KiCad cannot generate one from a PCB. §4. |
| TPS3430? | **Resolved with a citation: one package only** (10-pin VSON DRC). Land changed; **TPS3430WDRCR**. Alt route (TPS3813K33DBV, SOT-23-6) fully specified if no re-spin. §5. |
| Routed? | **96 of 284 open pairs (33.8 %)** in 420 s; that reaches **195 unconnected** — but with **97 DRC items including a short**, so the batch is **rejected**. Delivered board: **249 unconnected, 35 DRC, zero new**. §6. |
| Orderable? | **No.** Closer, but no. The schematic is the gate nothing else substitutes for. §7. |

Work is done on copies only. Nothing is written into a repository, committed, reset or pushed.
`evidence/` is a junction to `D:\ep-audit-evidence`; free space is checked before any large write.
`D:\CodeProjects` and `E:\1vm\TMP` are never written.

---

## 0. Method, provenance, files

- KiCad 9.0.7. `kicad-cli pcb drc --format json --severity-all --units mm`, **always** in a directory
  carrying `.kicad_pro` + `.kicad_dru` (a naked `.kicad_pcb` invents footprint violations — that
  exact error manufactured 52 fake violations in an earlier wave).
- `pcbnew` only from `C:\Program Files\KiCad\9.0\bin\python.exe`. **`PCB_VIA.GetWidth()` is never
  called** (it hangs forever on this build). Via geometry comes from text-parsing `(via … (size s)
  (drill d) (layers …))`. Via type ints: `1 = micro`, `2 = blind/buried`, `3 = through`.
- `pcbnew` scripts run as **background jobs with a hard 2–3 min cap**; orphan `python.exe` is killed
  by PID afterwards.
- `kicad-cli`'s **499** on the unconnected list is a **LIST CAP**, not a count. The uncapped number is
  quoted from `pcbnew GetUnconnectedCount(False)` and labelled "capped" wherever 499 appears.
- DRC results are reported as **set diffs** keyed by `(type, item uuid)`, never as bare totals.

| role | path | note |
|---|---|---|
| input | `evidence/esc-nfault-close/work/ctl_order_ready.kicad_pcb` | the artifact from the previous wave |
| input report | `evidence/esc-nfault-close/REPORT.md` | read first (§4.3 TPS3430 blocked, §5.4 no pours) |
| input report | `evidence/esc-control-netlist/REPORT.md` | read second (§A pin tables, §B decision register, §C single-ended nets) |
| delivered | `work/ctl_stitched.kicad_pcb` | fixes + 5 pours + 280 stitch vias — 35 DRC / 249 unconnected |
| evidence only | `work/ctl_final.kicad_pcb` | routed batch, poured — **195 unconnected but 97 DRC incl. a short: rejected** |

The full chain and every intermediate board is indexed in the Appendix.

---

## 1. DEAD WWDT — what "dead" means, and the fix

### 1.1 The diagnosis: three separate breaks, none of them "a missing part"

Measured on the input board (`ctl_order_ready.kicad_pcb`), pad by pad:

| # | what was found | evidence |
|---|---|---|
| 1 | **U8 `TPS3430` has 0 of 6 pads netted.** The footprint is placed at (52.725, 57.725) and the BOM carries the part, but pads 1–6 are all netless. | `survey_in.json`, and the DRC unconnected list contains no U8 item at all — a pad with no net produces no ratsnest |
| 2 | **`WDI` is a one-pad net.** It exists, with exactly one pad: `U1.44` (RP2354B). Nothing to kick, nothing to kick it. | net census: `WDI: 1 pad` |
| 3 | **There is no `WDO` net anywhere on the board.** 186 nets and not one of them is the watchdog output. | full net list, `survey_in.json` |
| 4 | **U13 `SN74LVC1G08` — the gate that would qualify `DRV_ENABLE` — has A/B/Y netless.** Only pad 3 (`DGND`) and pad 5 (`+3V3_REF_A`) were netted: the gate was powered and unused. | pad dump: pads 1,2,4 blank |

So "dead" is **not** a missing part and **not** a wrong part number alone: it is a part with no net,
a gate with no net, and an input net with nothing on the far end. That is the worst of the three
cases — the BOM reads "window watchdog", the schematic-less board carries a floating 6-pad land, and
nothing in between would ever reset anything.

**Root cause (same mechanism as everything else on this board):** these boards are footprint-only.
`esc-split-layout/03_build_control.py` places footprints with `pcbnew.FootprintLoad` and assigns nets
**only** to the three 2×20 headers; there is no symbol, no `.net`, no pin-function table. A footprint
with no symbol has no pin names, so any part whose pin map was never decided got **no nets at all**.
U8 and U12 are exactly those two parts.

### 1.2 Part A — the land is wrong, and only the land can be fixed

The previous wave left this "BLOCKED" on the belief that the TPS3430 exists in several packages and a
6-pin one could be relinked. **That branch does not exist.** The datasheet is unambiguous:

> "The TPS3430 is available in a small 3.00-mm × 3.00-mm, 10-pin VSON package."
> — [TPS3430 datasheet SBVS366A](https://www.ti.com/lit/ds/symlink/tps3430.pdf) §1 Features;
> §5 Pin Configuration, Figure 5-1 *"DRC Package — 3-mm × 3-mm VSON-10"*.

and the ordering table lists only `TPS3430WDRCR` / `TPS3430WDRCRG4`, both 10-pin VSON
([TI product page](https://www.ti.com/product/TPS3430): *"VSON (DRC) 10, 9 mm² (3 mm × 3 mm)"*).
There is no 6-pin TPS3430 to relink to, so the **SOT-23-6 land was simply the wrong land**.

**Applied:** U8's `SOT-23-6` land was replaced with `Package_SON:Texas_DRC0010J` — the TI DRC0010J
3 × 3 mm VSON-10 land, 10 numbered pads + pad **11** thermal — and the pin map was taken from Table
5-1 of the datasheet, not invented:

| pad | name | net applied | why |
|---|---|---|---|
| 1 | VDD1 | `+3V3_REF_A` | 1.6–6.5 V supply; 0.1 µF bypass recommended |
| 2 | CWD | `WWDT_CWD` (new) | timeout select — 10 kΩ to VDD, R155 |
| 3 | SET0 | `DGND` | window-ratio strap |
| 4 | CRST | **(no net)** | left unconnected on purpose = factory tRST preset |
| 5 | GND | `DGND` | |
| 6 | SET1 | `DGND` | window-ratio strap |
| 7 | WDI | `WDI` | **now 2 pads** (was 1) |
| 8 | WDO | `NRST` | the reset action — §1.3 |
| 9 | NC | **(no net)** | datasheet: "must be left floating" |
| 10 | VDD2 | `+3V3_REF_A` | datasheet: "must be externally connected to VDD1" |
| 11 | thermal pad | `DGND` | "internally connected to GND" |

Orderable part number: **TPS3430WDRCR** (tape & reel; the KiCad symbol `Power_Supervisor:TPS3430WDRC`
is the same die and its pin table matches Table 5-1 exactly, including pin 11 = GND).

### 1.3 Part B — what the output does, and the gate that was on the board for this

`WDO` is open-drain active-low and the datasheet requires a pull-up (*"Connect WDO with a 1-kΩ to
100-kΩ resistor to VDD"*). **R157, 10 kΩ, NRST → +3V3_REF_A** satisfies that and doubles as the
`NRST` pull-up. `NRST` became 5 pads: `J_H1.19`, `U1.35` (RP2354B RUN), `U8.8`, `U13.2`, `R157.1`.

A watchdog that only resets the MCU leaves the six DRV8353 gate drivers enabled for the whole reset
window. That is why U13 is on the board. It is now wired as the safety gate:

```
U1.28 ──DRV_ENABLE_MCU──▶ U13.1 (A)
NRST   ─────────────────▶ U13.2 (B)      U13 = SN74LVC1G08, SOT-23-5: 1 A, 2 B, 3 GND, 4 Y, 5 VCC
U13.4 (Y) ──DRV_ENABLE──▶ J_H1.25 ──▶ the six DRV8353 `ENABLE` pins on the power board
```

**`U1.28` had to be moved off `DRV_ENABLE` and onto the new net `DRV_ENABLE_MCU`.** Left where it
was, the gate would have been shorted out by the net itself — the MCU pin and the gate output would
have been the same node. This is the sort of thing that looks like a two-second edit and quietly
deletes the safety function, so it is called out.

Result on a watchdog timeout, with **no software in the path** (open-drain output, nanosecond
response): `DRV_ENABLE` falls → gate drivers disabled, and `NRST` is held low for tRST → the MCU
restarts. Both halves fail safe; neither depends on the firmware that just hung.

### 1.4 Part C — timing, and the firmware requirement (this part is not optional)

**tRST (reset stretch) = 200 ms, for zero components.** CRST is left unconnected; datasheet
Table 8-1 factory preset: `NC → 170 / 200 / 230 ms` (min/typ/max). Long enough for the RP2354B to
boot from QSPI, and §5 Table 5-1 notes *"During power up, all pulses to WDI are ignored before tRST
expires and the watchdog is disabled"* — so boot cannot be turned into a reset loop by the watchdog.

**Window: R155 10 kΩ CWD → +3V3_REF_A, SET0 = SET1 = DGND.** Datasheet Table 6-5:
`tWDL = 7.65 / 9.0 / 10.35 ms`, `tWDU = 92.7 / 109.0 / 125.4 ms` (min/typ/max).

> **DESIGN REQUIREMENT (firmware):** the MCU must produce exactly one falling edge on `WDI` per kick
> period, with **10.35 ms ≤ T_kick ≤ 92.7 ms** using the *worst-case* bounds. Recommended
> `T_kick = 30 ms`.
>
> This is a **window** watchdog, not a plain one. A 1 kHz control loop that kicks the watchdog every
> 1 ms is **faster than the lower boundary and will reset the board**. The kick must be decimated
> out of the fast loop (e.g. a 33 Hz task), and the strap that disables the watchdog
> (SET0 = 1, SET1 = 0) is hard-wired to GND here, so firmware cannot switch the watchdog off in
> flight. A watchdog that is wired but never kicked is still dead; that is a firmware obligation,
> and it is written here rather than assumed.

### 1.5 Verification of the WWDT fix

- U8: 17 physical pads (the KiCad TI land carries 6 unnamed mechanical pads besides the 11 numbered
  ones), **9 of the 11 numbered pads netted**, 2 deliberately netless (CRST = NC, pin 9 = NC).
  Netless-but-intentional is recorded so the next census does not read it as a defect.
- `WDI` 1 → **2 pads**; `NRST` 2 → **5 pads**; `DRV_ENABLE` stays 2 pads but its MCU end moved;
  new nets `DRV_ENABLE_MCU` (2 pads) and `WWDT_CWD` (2 pads).
- DRC: **0 new violations** (see §3.5 for the set diff).

---

## 2. UNCONNECTED EEPROM — which part, which pins, which bus, and the fix

### 2.1 The diagnosis

U12 `CAT24C32` in a `SOT-23-5` land at (90.625, 40.775): **all 5 pads netless**. The two nets that
were supposed to serve it, `I2C_SDA` and `I2C_SCL`, each had exactly **one** pad — `U1.42` and
`U1.43`. So the bus existed only at the MCU, and the previous wave's "3 single-ended nets" (`I2C_SDA`,
`I2C_SCL`, `WDI`) were three different symptoms of the same cause: a part with no pin map.

**Bus = I²C, not SPI.** Three independent reasons: the board's own net names are `I2C_SDA`/`I2C_SCL`;
the part is a 2-wire serial EEPROM; and the SPI bus is already fully committed (U1 + U10 MCP2518FD +
the six DRV8353 `SDO`s + U18 MCP3208 share `SPI_SCLK`/`SPI_MOSI`/`SPI_MISO`).

### 2.2 The land and the part could never match either

The onsemi CAT24C32 datasheet's *Pin Configurations (Top Views)* lists PDIP (L), SOIC (W), TSSOP (Y),
US (US), UDFN (HU4), SOIC-8 wide (X), WLCSP4 (C4C), WLCSP5 (C5A)
([CAT24C32 datasheet](https://www.onsemi.com/pdf/datasheet/cat24c32-d.pdf)). **There is no 5-lead
SOT-23 CAT24C32.** So, exactly like the TPS3430, the previous wave's "inventing a 5-lead I²C EEPROM
pinout" worry was aimed at the wrong object: the 5-pad land could never hold that part.

### 2.3 The fix: keep the land, change the part

The land matches the Microchip **24LC32A** family, which *does* come in 5-lead SOT-23
([24AA32A/24LC32A datasheet Doc 21713M](https://ww1.microchip.com/downloads/en/DeviceDoc/21713M.pdf):
*"The 24XX32A is also available in the 5-lead SOT-23 and Chip Scale packages"*). Orderable number
**24LC32AT-I/OT** (SOT-23-5, 2.5 V min). Pin numbers are taken from that datasheet's **Pin
Description** table, SOT-23 column — and this is the trap worth recording:

| SOT-23 pin | 24LC32A | 8-lead equivalent pin |
|---|---|---|
| 1 | **SCL** | 6 |
| 2 | **VSS** | 4 |
| 3 | **SDA** | 5 |
| 4 | **VCC** | 8 |
| 5 | **WP** | 7 |

The 5-lead pin order is **not** the 8-lead order truncated. A straight 8→5 guess would have put SCL
on pin 3 and SDA on pin 5 — both wrong, and the failure mode is an EEPROM that reads back nothing
while DRC stays perfectly clean.

Nets applied, and the resulting census:

| pad | function | net | effect |
|---|---|---|---|
| 1 | SCL | `I2C_SCL` | 1 → **3 pads** |
| 2 | VSS | `DGND` | |
| 3 | SDA | `I2C_SDA` | 1 → **3 pads** |
| 4 | VCC | `+3V3_REF_A` | |
| 5 | WP | `DGND` | WP = VSS → *"write operations are enabled"* |

Value text changed `CAT24C32` → `24LC32A`. Address pins A0–A2 do not exist in this package
(*"Address pins are not available in the SOT-23 and chip scale packages"*), so the device sits at
`0b1010_000`; it is the only EEPROM on the bus, so that is fine — but it must be written into the
bring-up notes, because a second 24LC32A could not be added without moving to an 8-lead part.

**Two pull-ups added, because SDA/SCL are open-drain.** The datasheet is explicit: *"the SDA bus
requires a pull-up resistor to VCC (typical 10 kΩ for 100 kHz, 2 kΩ for 400 kHz)"*. The BOM had none.
**R153** 10 kΩ `I2C_SDA` → `+3V3_REF_A` and **R154** 10 kΩ `I2C_SCL` → `+3V3_REF_A`. This is the same
class of defect as the `SPI_MISO` pull-up the previous wave found — an open-drain line with no
pull-up is a line that floats.

### 2.4 Is the EEPROM optional? Yes — and why it was kept anyway

It is technically optional: the board already has two non-volatile stores (the RP2354B's in-package
2 MB QSPI flash, and the external `W25Q128` U4 on the QSPI bus), so calibration constants could live
in a flash sector. Deleting U12 + R153/R154 would remove one part, two 0603s and 2 nets, and would
return GPIO42/43 → spare GPIO goes **3 → 5**.

It was **kept**, and the reason is a design decision that should be reviewed rather than assumed: a
board-unique calibration record that survives a QSPI reflash is a real function, and removing it
changes the GPIO allocation the brief told me not to reopen. The alternative is priced above; if the
owner prefers it, it is a deletion, not a re-design.

### 2.5 Verification of the EEPROM fix

`I2C_SDA` 1 → 3 pads, `I2C_SCL` 1 → 3 pads, **single-ended nets 3 → 0**, U12 0/5 → 5/5 pads netted.

---

## 3. NO POURS — ground and power planes, and the DRC set diff

### 3.1 What was there before: nothing

The input board had **0 zones**, 525 track segments and 22 vias. `AGND` (101 pads) and `DGND`
(85 pads) were being carried entirely by tracks — on a 2-layer board with all 165 parts on F.Cu. The
`AGND`–`DGND` star (R152) was a component sitting on two unrouted nets, which is to say the star
point existed on paper only.

### 3.2 The five zones

All five use **local clearance 0.200 mm** (the `.kicad_dru` floor: `(rule "clearance 0.200 mm min")`),
**min width 0.200 mm** (the `zone neck 0.200 mm min` rule), **solid pad connection** (a thermal spoke
on a 0.5 mm-pitch land cannot meet the 0.200 mm neck rule), and **islands always removed**.

| # | layer | net | priority | polygon |
|---|---|---|---:|---|
| 1 | F.Cu | `AGND` | 3 | `ANALOG` (12 vertices, below) |
| 2 | F.Cu | `+3V3_REF_A` | 2 | `(72.0, 14.6) (100.0, 14.6) (100.0, 56.0) (72.0, 56.0)` — the power pour |
| 3 | F.Cu | `DGND` | 1 | `(44.6, 14.5) (150.6, 14.5) (150.6, 73.5) (44.6, 73.5)` — whole board |
| 4 | B.Cu | `AGND` | 2 | `ANALOG` (same polygon) |
| 5 | B.Cu | `DGND` | 1 | whole board (the actual return plane) |

`ANALOG` — the ADC column plus the RC-filter band, with the star-point moat cut into it:

```
(100.5,14.6) (102.9,14.6) (102.9,23.0) (104.2,23.0) (104.2,14.6) (120.0,14.6)
(120.0,57.4) (105.0,57.4) (105.0,64.0) (71.0,64.0) (71.0,57.4) (100.5,57.4)
```

Board outline is `(44.1,14) – (151.1,74)`; every zone is inset **0.5 mm** for the
`copper to board edge 0.500 mm min` rule.

### 3.3 Why AGND and DGND can only meet at R152 — the moat, not just two rectangles

Two overlapping rectangles would not be a star point: the AGND flood would simply wrap around R152
and short the tie it is supposed to be. R152 sits at (102.725, 21.725) with pad 1 = `AGND` at
(101.90, 21.725) and pad 2 = `DGND` at (103.55, 21.725) — 1.65 mm apart, so a plane boundary drawn
between them has 0.85 mm to work in.

The `ANALOG` polygon therefore carries a **1.3 mm wide notch** `(102.9 … 104.2) × (14.6 … 23.0)` cut
from the zone's top edge down past R152 pad 2. The AGND fill stops at x = 102.9 (0.6 mm west of pad 1);
the DGND fill runs down the notch and reaches pad 2 from above. **No other copper path exists between
the two nets**, which is exactly the property the 0R tie is supposed to have, and it is now true
geometrically rather than by assertion.

### 3.4 Pad audit before filling (so the polygons are measured, not drawn by eye)

| region | same-net pads inside | foreign pads inside |
|---|---|---|
| `ANALOG` | **80 of 101** `AGND` | **0 `DGND`**; 12 `+5V`, 8 `+3V3_REF_A` (the ADCs' own AVDD/DVDD — the flood correctly backs off) |
| `POWER` | **36 of 58** `+3V3_REF_A` | 23 `DGND`, 5 `+1V1` (the flood backs off) |

**21 AGND pads are deliberately outside the analogue plane**, and both groups are named rather than
hidden:

- **19 × J_H3 `AGND`** pins at x = 142.91 — the analogue header column, ~40 mm east of the ADC
  cluster, with the digital headers J_H1/J_H2 in between. A plane does not belong down a 2.54 mm
  header column between digital pins.
- **2 × U18 `MCP3208`** pins, (78.09, 65.53) and (84.44, 70.47). U18 straddles the analogue/digital
  boundary and its `DGND` pin sits at (84.44, 65.53). A pour that included U18 would enclose that
  DGND pin in an isolated pocket inside the analogue plane — the measurement before the fix was made
  is why the band stops at y = 64.0 instead of y = 72.

Those 21 are what the router has to earn back with tracks; §6 reports how many it did.

### 3.5 The isolated plane, and 280 stitching vias

The first DRC on the poured board produced exactly one new violation, and it was the right one:

```
isolated_copper   Zone [AGND] on B.Cu, priority 2
```

Correct and unavoidable: **B.Cu has no AGND pad**, so the bottom analogue plane was a floating
island. A plane that connects to nothing is decoration. It was cured by stitching:

- **280 through vias, 0.600/0.300 mm** (220 `DGND` + 60 `AGND`), placed only where **both** layers
  carry that net's fill over a 0.45 mm-radius disc **and** the via is ≥ 0.55 mm from the bounding box
  of every foreign-net pad/track/via and ≥ 0.90 mm from every drilled hole; then the zones were
  **re-filled** so the fills are consistent with the copper that now exists.
- The first attempt at this is recorded because it was **wrong and DRC caught it**: a 2 %-permissive
  disc test with no copper-distance test placed 2 bad vias (0.0478 mm from C300 pad 1; 0.1994 mm from
  J_H1 pad 22 — one ten-thousandth under the rule) plus 3 `hole_clearance` items. Strict disc test +
  explicit bbox clearance test fixed it; the refill also cleared a stale fill that a `LM1_SW` via was
  sitting inside.

### 3.6 The DRC set diff the pours produced

Same board, companions present, `--severity-all`, identical rules file; keyed by `(type, item uuid)`.
**Fixed (surgery + silk) → poured → stitched:**

| type | before | after | delta |
|---|---:|---:|---:|
| clearance | 9 | 9 | **0** |
| connection_width | 1 | 1 | 0 |
| courtyards_overlap | 2 | 2 | 0 |
| silk_edge_clearance | 7 | 7 | 0 |
| silk_over_copper | 7 | 7 | 0 |
| silk_overlap | 8 | 8 | 0 |
| track_dangling | 1 | 1 | 0 |
| isolated_copper | 0 | 0 | 0 (＋1 when poured, −1 after stitching) |
| **violations total** | **35** | **35** | **0 new, 0 removed** |
| **unconnected_items** | **284** | **249** | **−35** |

**The honest negative:** the brief predicted that filling pours would *remove* clearance violations
because close copper becomes the same net. **It did not, and it could not.** All 9 pre-existing
clearance errors are track-to-track and pad-to-pad items — the `USB_DP`/`USB_VBUS` pair at 0.160 mm
and the `U9` TCAM3413 land whose own pads are 0.150 mm apart on a 0.5 mm pitch. No zone touches any of
them, so a pour can neither cause nor cure them. What the pours actually bought is measured below.

**Where the 35 fewer unconnected items came from** (unconnected pairs, by net, surgery → poured):

| net | before pours | after pours | delta |
|---|---:|---:|---:|
| `+3V3_REF_A` | 34 | 17 | **−17** |
| `DGND` | 23 | 9 | **−14** |
| `AGND` | 6 | 2 | **−4** |
| 250 signal nets | 221 | 221 | 0 |
| **total** | **284** | **249** | **−35** |

(Sum −17−14−4 = −35 ✓.) The grounds are essentially done — 2 `AGND` and 9 `DGND` items remain, and
those are the pads §3.4 named as deliberately outside the plane, plus pads a track of another net has
walled off. The remaining 249 is **signal and power routing**, which is §6.

### 3.7 Order of operations, stated because it matters

The pours above were built and measured **on the unrouted board** so that the set diff in §3.6 is a
clean pour-only measurement. For the delivered artifact the order is **route → pour → refill**,
because a solid B.Cu `DGND` plane plus a full-board F.Cu `DGND` flood leaves the router no second
layer and almost no F.Cu — that is not a defect of the pours, it is what a pour does to an unrouted
2-layer board. §6 reports the routed result and the final numbers on the poured board.

---

## 4. NO SCHEMATIC — the honest assessment

### 4.1 What exists: nothing, and the thing that exists is worse than nothing

Verified, not assumed: `glob **/*.kicad_sch` over the whole evidence tree returns 138 files and
**none of them is this board** — every hit belongs to Code-SDR V2 or the drone-arm project. The
control board has no `.kicad_sch`, no `.net`, and **no library link on any footprint**: the board file
reads `(footprint "SOT-23-6"`, a bare name with no `Lib:Name` — the footprints were placed by script
and never associated with a symbol.

What the board *does* carry is the more valuable half of a schematic: a provenance-tagged netlist.
**725 of 861 pads netted, 188 nets, and every pad write tagged `SRC` / `DECIDED` / `EXT` / `OPEN`**
(`esc-control-netlist` §4). The number that matters is **295 of the original 439 pad writes are
`DECIDED`** — design choices made by a script, reviewed by nobody.

So the fab blocker is not "there is no drawing to work from". A CM can build from the Gerbers, the
drill file and the position file. **The blocker is that there is no reviewable statement of design
intent** — nobody can sign off 295 script-made decisions, and there is nothing for the assembly house
to check the netlist against. That is what a schematic is for, and it is why this is the item that
blocks an order rather than merely delaying one.

### 4.2 Can it be generated from the board? No — but about half of it can

KiCad 9 has **no PCB → schematic conversion**. `kicad-cli sch` offers `erc` and `export` (netlist,
pdf, bom, …) and nothing that reads a `.kicad_pcb`. "Generate from the board" therefore produces one
specific thing: a **pin-label dump** — one real symbol per footprint, one net label on every pin, no
wires. That is a genuine, useful artifact (it round-trips the netlist and makes every pin's net
explicit), and it is exactly what the sibling board ships (§4.3). It is **not** an assembly document:
there is no functional grouping, no bypass capacitor drawn beside the pin it decouples, no divider
drawn as a divider. The functional drawing is the part that separates "a schematic" from "a netlist
with pictures", and that part is human work.

### 4.3 The fastest legitimate route — settled by precedent in this same portfolio

The board that **is** orderable (Code-SDR V2, 5/5) carries an 8-sheet schematic. Measured on
`evidence/cs-orderable-fix/src/sheets/*.kicad_sch`:

| sheet | symbols | placed pins | wires | labels |
|---|---:|---:|---:|---:|
| 01_power | 46 | 140 | 0 | 127 |
| 02_controller | 31 | 141 | 0 | 137 |
| 03_fpga_adc | 49 | 207 | 0 | 172 |
| 04_ethernet | 53 | 170 | 0 | 167 |
| 05_reference_lo | 58 | 186 | 0 | 181 |
| 06_rf_low | 25 | 84 | 0 | 82 |
| 07_rf_high | 55 | 172 | 0 | 171 |
| 08_if_chain | 56 | 167 | 0 | 166 |
| **total** | **373** | **1267** | **0** | **1203** |

**Zero wires, one label per pin, real symbols.** So the accepted style on this project is already
machine-generatable, and that settles the question: the route is *write from the pinmap and netlist*,
with real part symbols, and the acceptance test is **netlist equality** —
`kicad-cli sch export netlist` must reproduce the board netlist 1:1 (725 pads, 188 nets). A schematic
that cannot do that is decoration.

### 4.4 What this board needs, measured

Footprints assigned to functional blocks and passives to their nearest active part (measured, 165
footprints before this pass's 4 additions):

| sheet | contents | footprints |
|---|---|---:|
| 1 Power | 2 × LM5164 BEC + AP2112K + FB/RON/BST networks + input protection | 18 |
| 2 MCU | RP2354B + W25Q128 + 12/40 MHz crystals + USB-C + ESD + SWD | 14 |
| 3 Supervisor + NVM + gate | TPS3430WDRCR + 24LC32A + SN74LVC1G08 + R152–R157 | 19 |
| 4 CAN | MCP2518FD + TCAN3413 + ACM4532 choke + PESD1CAN | 19 |
| 5–6 Analogue front end | 3 × ADS8588S (64 pins each) + 31 RC filters + REF5030 + MCP3208 | **86** |
| 7 Headers + driver interface | J_H1/J_H2/J_H3 (120 nets) + 74HC138 | 9 |
| | **total** | **165** (+4 this pass = 169) |

**7 sheets minimum** (8 if the analogue front end gets one sheet per ADC, which the 86-footprint
count argues for). 169 symbols, 861 pins of which 725 are netted, 188 nets. For scale: Code-SDR V2
is 373 symbols / 8 sheets, so this board is roughly half the symbol count but *harder per symbol*
because three 64-pin parts must be transcribed exactly.

Six symbols have no KiCad library part and must be written from datasheets: `ADS8588S`,
`MCP2518FD`, `TCAN3413`, `24LC32A`, `REF5030`, `W25Q128`. The ADS8588S 64-pin table is already
transcribed in `esc-control-netlist` §A.2 — but note that transcription came from a third-party
mirror, so it must be re-checked against TI SBAS642A before the sheet is signed. That is a
one-hour check, not a formality.

### 4.5 A MINIMUM viable AC-schematic, defined, and what it costs

**Definition (acceptance criteria, hence "AC").** The smallest artifact that can be signed:

1. every reference designator has a real symbol carrying the right value → **169 symbols**;
2. every net is carried by exactly one set of labels → **725 pin labels over 188 nets**;
3. **ERC clean** (no unconnected-pin, no power-pin-driven conflicts);
4. **SCH → netlist equals the board netlist 1:1** — same 725 pads, same 188 nets, zero differences.

**Cost, estimated against the sibling's density:**

| slice | work | estimate |
|---|---|---|
| sheets 1, 2, 3, 4, 7 (79 footprints, 120 header nets) | 6 hand-written symbols + label generator + block drawing | **6–8 h** |
| sheets 5–6 (86 footprints, 192 ADC pins, 31 identical RC filters) | repetitive, but 3 × 64-pin pin tables to verify | **4–6 h** |
| netlist round-trip and ERC iteration | the acceptance test above | **2–3 h** |
| review of the 295 `DECIDED` rows against intent | human judgement, cannot be automated | **not estimable here** |
| **minimum viable AC-schematic** | | **12–17 h of engineering** |

A full, readable 7-sheet capture (drawing the dividers, the filter topology, the gate) is **2–4 days**,
because the 295 decisions have to be re-derived by a person rather than read off a table.

### 4.6 What I did not do, and why

**I did not produce the schematic.** The generator for a label-per-pin sheet is ~2–3 h of work
(the symbol worklist above plus a placer), and I judged it worth less than the routing pass and the
pour measurement it would have displaced — and a half-readable schematic on this board would invite
exactly the false confidence that produced the floating TPS3430 land in the first place. What is
handed over instead is the recipe, the measured sheet split, the symbol worklist, and the acceptance
test, all of which is what the next session needs to start.

---

## 5. TPS3430 — the part-number decision, resolved with a citation

**The premise in the brief was wrong, and correcting it *is* the resolution.** The TPS3430 does not
"come in several packages". It comes in one:

> "The TPS3430 is available in a small 3.00-mm × 3.00-mm, **10-pin VSON** package."
> — [TPS3430 datasheet, SBVS366A](https://www.ti.com/lit/ds/symlink/tps3430.pdf), §1 Features;
> §5 Figure 5-1 *"DRC Package — 3-mm × 3-mm VSON-10"*; Table 5-1 pin functions.
> Ordering information lists only **TPS3430WDRCR** / **TPS3430WDRCRG4**, both 10-pin VSON.
> [TI product page](https://www.ti.com/product/TPS3430): *"VSON (DRC) 10, 9 mm² (3 mm × 3 mm)"*.

So "relink the symbol to a 6-pin orderable TPS3430" was never an available branch, and the SOT-23-6
land was simply wrong. **Resolved in favour of the part that is already in the BOM**: the land moved
to the datasheet's only package (`Package_SON:Texas_DRC0010J`, 10 pads + thermal pad 11) and the
orderable number is **TPS3430WDRCR**. Nets and reasoning are in §1.2.

**The alternative, fully specified** so it can be taken instead if a land change is unwanted: keep the
SOT-23-6 land and use a **6-pin SOT-23 window watchdog**. The candidate that fits exactly is
**TPS3813K33DBV** — [TPS3813 datasheet SLVS331J](https://www.ti.com/lit/ds/symlink/tps3813.pdf),
§5 Figure 5-1 *"DBV Package, 6-Pin SOT-23"*, Table 5-1: `1 WDI, 2 GND, 3 WDT, 4 VDD, 5 WDR,
6 RESET`; 2.93 V threshold version for a 3.3 V rail. Cost of that route: 1 part, 1 capacitor on WDT,
1 strap on WDR, and its open-drain RESET wire-OR'd onto `NRST`.

Why the TPS3430 route was chosen: both its window **and** its reset delay are programmable (TPS3813's
window ratio is a two-way strap and its delay is fixed by a capacitor), its timing tolerance is 2.5 %
typical versus the TPS3813's ±15 %, and it is the part the BOM, the symbol and the prior review
already name. Adding a supply supervisor (TPS3813) also duplicates a function this board does not
need, because the RP2354B has its own brown-out detector. If a re-spin is off the table, take the
TPS3813 path — it is electrically legal and it is one part instead of a land change; it is named here
so the choice is explicit rather than defaulted.

---

## 6. Routing — raster A* at 0.04 mm, the routed fraction, the TRUE unconnected, and why the batch was rejected

### 6.1 What was routed, and against what denominator

The router is the proven raster A* at 0.04 mm (track 0.200, clearance 0.200, via 0.600/0.300,
edge 0.500, 2 layers), with two changes: the start/goal of every route is an **actual DRC
unconnected pair** rather than an MST guess, and the search is clipped to a 10 mm corridor around
that pair.

**Denominator = 284 open pairs** — the exact `unconnected_items` list from the DRC on the fixed
board, shortest 0.80 mm, longest 79.64 mm. (Not 513 MST connections: 254 of those were already
copper from the previous wave, and re-routing them would have inflated the fraction with work that
was already done.)

| | value |
|---|---:|
| open pairs (demand) | **284** |
| attempted inside the 420 s wall-clock box | **199** |
| **routed** | **96** — 48.2 % of attempted, **33.8 % of demand** |
| segments written / vias inserted | 368 / 82 |
| failed, with reason | **103** — 100 *A\* exhausted / budget*, 3 *no free start cell* |
| unconnected before → after routing (no pours) | **284 → 210** (−74) |
| … second tool (`pcbnew GetUnconnectedCount(False)`) | **210** — agrees |

### 6.2 What that copper costs: the batch does not pass its own gate

The routed board was then poured with the §3.2 topology and stitched (168 vias). That board,
`ctl_final.kicad_pcb`, reaches the best unconnected number anywhere in this run:

| board | zones | new copper | DRC (companions, all sev.) | true unconnected |
|---|---|---:|---:|---:|
| `ctl_order_ready` (input) | 0 | – | 38 | **261** |
| `ctl_fixed` (WWDT + EEPROM + gate) | 0 | 4 parts | 35 | 284 |
| **`ctl_stitched` (fixes + 5 pours + 280 stitch vias)** | **5** | 280 | **35** | **249** |
| `ctl_routed` (+96 pairs) | 0 | 450 | **113** | 210 |
| `ctl_final` (routed + poured + stitched) | 5 | 618 | **97** | **195** |

195 unconnected is 54 better than the pour-only board — and the price is **97 DRC violations against
35**, including **1 `shorting_items`, 1 `tracks_crossing`, 30 `clearance`, 21 `connection_width`,
13 `track_dangling`, 2 `hole_to_hole`, 1 `holes_co_located`, 1 `copper_sliver`, 3
`copper_edge_clearance`**. **A batch with a short is not a routing result; it is a defective board.**

**So the batch was gated, not shipped**, exactly as the previous wave rejected its first batch:

| gate pass | violations | unconnected | new-copper items deleted |
|---|---:|---:|---:|
| 0 (delete violators) | 113 → (79 blocks out) | 210 → 251 | **79 of 450** |
| 1 (delete what pass 0 orphaned) | 95 | | **52** |
| 2 | 74 | 247 | **23** |
| after | 74 (39 of them dangling) | **247** | **154 of 450** |

The gate removed **154 of the 450 new copper items (34 %)** and the survivors bought **~2 net
connections**. That is the measurement that settles it: **the routed batch is rejected.** The
delivered artifact is therefore `ctl_stitched.kicad_pcb` — the board with three of the four named
blockers closed, 5 pours, 280 stitching vias, **35 DRC items and not one of them new**.

### 6.3 The named cause — this is a router bug, not a "needs more time"

The failure is mechanical and it is in my script, not in the board: when the start of a pair is the
reported position of an existing **track** (the DRC reports a point on the item, not a pad), the
router spirals up to **60 cells = 2.4 mm** looking for a free cell and then starts the route *there*.
If the nearest free cell is even 0.3 mm from the copper it was supposed to join, the new segment
starts in open space: it is a dangling end, it connects nothing, and — because the start point is now
outside the clearance envelope that the obstacle grid was built around — it can also begin inside
foreign copper. That single defect explains all four symptoms at once: 13 `track_dangling`,
`shorting_items`, `tracks_crossing`, and the 96 "successes" that only retired 74 unconnected items.

**The fix, stated so the next run does not repeat it:** start cells must be constrained to the copper
being joined (tolerance ≤ 2 cells = 0.08 mm) and the pair must be *skipped with a reason* when no
start cell that close exists, exactly as the previous wave's router constrained start layers to the
pad's own layer set. Pads are the only safe route endpoints on this board; routing from an arbitrary
point on a track should be dropped from the design rather than patched.

### 6.4 The honest balance of the routing pass

- **Attempted fraction:** 199 of 284 pairs, 96 routed, 103 refused for a stated reason.
- **Best measured state, published:** `ctl_final` at **195 unconnected** — 66 fewer than the 261 this
  task started from — but at **97 DRC items including a short**, so it is *evidence*, not a deliverable.
- **Deliverable:** `ctl_stitched` at **249 unconnected**, 35 DRC, zero new.
- The 100 *A\* exhausted / budget* refusals are not all unfixable — they are the tail of the pair list
  after the box expired, and a longer box would have attempted them. What the gate measured is that
  the **quality** of the routes was the problem, not the quantity of time.

---

## 7. Verdict

**Is the control board closer to orderable? Yes — materially — and it still is not orderable.**

Closed in this pass, each with a number attached:

| blocker | state before | state after |
|---|---|---|
| **DEAD WWDT** | U8 0/6 pads netted, no `WDO` net, `WDI` a 1-pad net, gate netless | TPS3430WDRCR on the datasheet's only land, 9/11 pads netted, `WDI` 2 pads, `NRST` 5 pads, `WDO` → `NRST` → `DRV_ENABLE` gate; window 10.35–92.7 ms, tRST 200 ms, firmware obligation stated |
| **UNCONNECTED EEPROM** | U12 0/5 pads netted, `I2C_SDA`/`I2C_SCL` 1-pad nets, no pull-ups | 24LC32A in the existing SOT-23-5 land on the datasheet's 5-lead pin order, 5/5 netted, `I2C_SDA`/`I2C_SCL` 3 pads each, R153/R154 added, **single-ended nets 3 → 0** |
| **NO POURS** | 0 zones | 5 zones (AGND/DGND split with the R152 moat, +3V3 power pour), 280 stitching vias, **0 new DRC**, −35 unconnected |
| **NO SCHEMATIC** | does not exist | still does not exist — but now costed: 7 sheets, 169 symbols, 725 labels, 12–17 h to a signable AC-schematic, with a netlist-equality acceptance test |
| **TPS3430** | "blocked, part-number decision" | resolved with a citation: one package only (10-pin VSON DRC); land changed; **TPS3430WDRCR**. Alternative (TPS3813K33DBV, SOT-23-6) fully specified if a re-spin is unwanted |
| **Routing** | 261 unconnected | **249**, router attempt measured and rejected at 195-with-a-short |

**What still blocks an order, in order of severity:**

1. **No schematic.** Unchanged, and still the gate that nothing else can substitute for — §4.5 prices it
   at 12–17 h to the minimum signable artifact.
2. **249 unconnected items**, of which the grounds are done (2 `AGND`, 9 `DGND`) and the rest is signal
   and power copper that the router cannot place until its start-point defect is fixed (§6.3).
3. **35 DRC items**, all pre-existing: 9 clearance (the `USB_DP`/`USB_VBUS` pair at 0.160 mm and the
   `U9` TCAN3413 land whose own pads are 0.150 mm apart), 2 header courtyard overlaps, 8 silk overlaps,
   7 silk-edge and 7 silk-over-copper warnings, 1 `connection_width`, 1 `track_dangling`.
4. **`+1V1` has nothing on it but the MCU.** The net is 5 pads and **all five are `U1` pins**
   (10, 32, 51, 63, 65) — the RP2354B's own core-regulator pins, with no inductor and no capacitor
   on the BOM. Measured, not inferred: no other footprint on the board touches `+1V1`. Out of this
   task's scope, but it is a board-stopper and it is named rather than buried.
5. **21 `AGND` pads sit outside the analogue plane by design** (§3.4) and must be reached by tracks.

**Reading the two baselines, because two numbers appear above and only one of them is a regression:
the input board had 261 unconnected items; this pass added 29 netted pads (U8's 9, U12's 5, U13's 3,
and 8 across the four new resistors), and a pad with no copper is unconnected by definition, so the
fixed board measured 284 before any copper was added. The pours then retired 35 of those, which is
why the delivered board reads 249 — twelve below the 261 it started from, *after* paying for 29 new
pads.**

**The plain answer to the only question that matters:** the board is no longer lying about its
watchdog, it is no longer carrying a floating EEPROM, and it has real ground and power planes with a
measured star point. It is still **not orderable**, and the single largest remaining item is the one
item on the list that no script can close — the schematic.

---

## Appendix — evidence index

| path | what |
|---|---|
| `work/ctl_order_ready.kicad_pcb` | input, copied from `esc-nfault-close/work/` (165 fp / 842 pads / 700 netted / 186 nets / 3 single / 525 seg / 22 via / 0 zones) |
| `work/ctl_wwdt_eeprom.kicad_pcb` | + U8 land swap, U12 pin map, U13 gate, R153–R157 (169 fp / 861 pads / 725 netted / 188 nets) |
| `work/ctl_fixed.kicad_pcb` | + 5 reference fields moved to F.Fab and U9's ref repositioned — **0 new DRC** |
| `work/ctl_poured.kicad_pcb` | + the 5 zones, filled |
| `work/ctl_stitched.kicad_pcb` | **the delivered artifact** — + 280 stitching vias, refilled (35 DRC / 249 unconnected) |
| `work/ctl_routed.kicad_pcb` | + 96 pairs, 368 segments, 82 vias (113 DRC / 210 unconnected) — **rejected batch** |
| `work/ctl_final.kicad_pcb` | the rejected batch poured + stitched (97 DRC / **195 unconnected**) — evidence, not a deliverable |
| `work/ctl_routed_gated.kicad_pcb` | after 154 of 450 new copper items were gated out (74 DRC / 247 unconnected) |
| `work/drc_base.json` … `work/drc_final.json` | DRC at every stage, companions present, `--severity-all` |
| `work/route.json` | routed/attempted, every failure with its reason, rules, time box |
| `work/gate_p0..2.json` | the gate's per-pass violation census and deletion count |
| `work/stitch.json`, `stitch_final.json` | every stitching via with net and coordinate |
| `work/survey_in.json` | independent text-parse census of the input |
| `scripts/` | `s1_survey.py`, `s2_surgery.py`, `s3_silkfix.py`, `s4_zones.py`, `s5_stitch.py`, `s6_route.py`, `s7_gate.py`, `zfill.py`, `drc_run.py`, `drcdiff.py` |
| `datasheets/` | `tps3430.pdf`, `tps3813.pdf`, `cat24c32.pdf`, `24lc32a.pdf` + extracted text |
| `logs/` | raw tool output for every stage |

No script called `PCB_VIA.GetWidth()`. `pcbnew` ran as capped foreground jobs with a 180–420 s limit
and no orphan interpreter was left behind. Nothing was written into a repository, committed, reset or
pushed; `D:\CodeProjects` and `E:\1vm\TMP` were never touched. Free space on `D:` (the junction
target) was 141.76 GB before this run and 141.73 GB after; this whole directory is 28.88 MB
(114 files), of which the four datasheet PDFs are 4.9 MB.

