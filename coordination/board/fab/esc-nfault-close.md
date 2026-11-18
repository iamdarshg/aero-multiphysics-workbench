# ESC CONTROL board — the nFAULT wire-OR, verified, and what it does and does not close

**Task (one).** Close the "5-GPIO gap" by wire-OR-ing the six DRV8353 nFAULT lines, then get the
board to a state that can be routed and ordered.

**Status: the wire-OR is electrically legal, it is worth exactly 5 GPIO — and it is already in the
budget, so it closes nothing further.** The board's own interface contract (H1 pin 26) is
`nFAULT_ALL`, commented *"6 open-drain nFAULT, wired-OR"*; the previous wave's demand table counts it
as **one** pin. `46 − 5 = 41` therefore subtracts the same five pins twice. The gap is real, it is −5
on the original 46-item list and −7 once the ADC bus is costed correctly, and it was closed by parts
(one 74HC138 + one MCP3208), not by the wire-OR. That work is inherited, independently re-verified
here, and extended: **165 footprints / 842 pads / 700 netted (83.1 %) / 186 nets / 3 single-ended**
(from 148 / 768 / 559 / 172 / 53). The AGND–DGND tie, the 10 missing BEC passives, two
datasheet-mandated open-drain pull-ups, the LM5164 exposed pad, the CAN choke and the MCP2518FD pin
map are applied; routing is reported honestly below. **The board still does not ship** — reason §6.

Work was done on copies only. Nothing was written into a repository, committed, reset or pushed.
`evidence/` is a junction to `D:\ep-audit-evidence` (141.8 GB free before, 141.8 GB after; this run
wrote < 4 MB).

| question | answer |
|---|---|
| Can the six nFAULT be wire-OR'd with no diode/gate? | **Yes.** DRV835x datasheet SLVSDY6A p7: `nFAULT` type is **OD = open-drain**, *"pulled logic low during a fault condition and requires an external pullup resistor"*. Six open-drain outputs may share one node and one pull-up; sink budget 6 × 0.33 mA = 2.0 mA ≤ 5 mA. |
| Does `46 − 5 = 41` check out? | **The arithmetic is right, the framing is wrong.** Six separate nFAULT lines = 51 pins; 51 − 5 = 46 ✔. But 46 *already* counts `nFAULT_ALL` as one pin, so on this board the wire-OR frees **0** further pins: 46 − 0 = 46, short 5. |
| Is 5 enough? | **No.** Corrected ADC bus (8 pins, not 6) makes the gap **7**. Closed with a 74HC138 CS decode (−4, $0.15) + MCP3208 NTC offload (−7 digital, $2.38): 45 of 48 GPIO used, **3 spare**. |
| Can firmware still say *which* driver faulted? | **No.** One wire-OR'd line gives an OR, not an identity. The interrupt is a **wake-up/latch only**: the ISR must poll the six status registers over SPI (0x00 Fault Status 1 *"Mirrors nFAULT pin"*, 0x01, 0x02) — non-destructive, because the status registers are read-only and a latched fault clears only on `CLR_FLT` or an 8–40 µs ENABLE pulse. |
| New pad/net coverage | 148/768/559/172 → **165/842/700/186** (699 before the MCU ground-pad fix, §5.3); single-ended **53 → 23 → 3**. |
| AGND–DGND tie | **Done** — R152, 0R 0603, one star point at the ADC cluster. |
| ~10 missing passives | **Done** — 10 BEC parts + 2 CC pulldowns + 2 open-drain pull-ups = 15 new parts, all netted. |
| 6 footprint defects | **3 done** (LM5164 EP ×2, CAN choke, MCP2518FD), **1 blocked** (TPS3430), **2 not defects** (crystal land, USB-C). |
| Routed | see §5 — routed/attempted and the true unconnected figure, DRC-gated with companions. |
| Does the board close? | **The pin budget closes. The board does not.** §6. |

---

## 0. Method, provenance, files

- KiCad 9.0.7. `kicad-cli pcb drc --format json --severity-all` **always in a directory carrying
  `.kicad_pro` + `.kicad_dru`** (a naked `.kicad_pcb` invents footprint violations). `pcbnew` from
  `C:\Program Files\KiCad\9.0\bin\python.exe` for load/edit/save. **`PCB_VIA.GetWidth()` was never
  called**; all counts are text parses of the `.kicad_pcb` (my own s-expr reader) so nothing can hang.
- Every number below was produced twice where a second tool exists: text parse for counts, `pcbnew`
  `GetUnconnectedCount(False)`, `kicad-cli` for DRC/unconnected.
- Datasheets were read, not guessed: TI PDFs were downloaded and the text extracted locally with
  PyMuPDF, because `web_fetch` refuses `application/pdf` and TI's HTML datasheet viewer serves only
  its table of contents to a plain fetch.

| role | path |
|---|---|
| input (prior wave) | `evidence/esc-mcu-closes/work/esc_control_board_closed.kicad_pcb` — SHA-256 `…`, 650/800 pads |
| surgery pass 1 | `scripts/surgery.py` → `work/ctl_closed_gaps.kicad_pcb` |
| surgery pass 2 | `scripts/surgery2.py` → `work/ctl_closed_gaps2.kicad_pcb` |
| surgery pass 3 | `scripts/surgery3.py` → `work/ctl_final.kicad_pcb` |
| router | `scripts/route.py` → `work/ctl_routed.kicad_pcb` |
| DRC before / after | `work/drc_before.json`, `work/drc_final.json` |
| independent survey | `scripts/survey.py` → `work/survey_in.json`, `survey_gaps.json`, `survey_final.json` |

---

## 1. The wire-OR, verified against the datasheet

### 1.1 The pin is open-drain, active-low, and *requires* a pull-up

DRV835x **SLVSDY6A**, §6 "Pin Functions — 40-Pin DRV8353 Devices" ([TI datasheet, HTML viewer](https://www.ti.com/document-viewer/DRV8353/datasheet), PDF [SLVSDY6](https://www.ti.com/lit/ds/symlink/drv8353.pdf)), page 7, verbatim:

> `nFAULT  26  26  OD   Fault indicator output. This pin is pulled logic low during a fault condition and requires an external pullup resistor.`

with the table's footnote `(1) PWR = power, I = input, O = output, NC = no connection, OD = open-drain`.
§7.3 Recommended Operating Conditions, page 11:

> `VOD  Open drain pullup voltage (nFAULT, SDO)  0 … 5.5 V`  ·  `IOD  Open drain output current (nFAULT, SDO)  0 … 5 mA`

### 1.2 Therefore the wire-OR is legal with no diode and no gate

Six open-drain outputs on one node and one pull-up is a wired-AND of active-low signals — the standard
fault bus. Each driver can only sink; no source contends with another source, so no steering diode is
needed and no gate is needed. Design numbers, checked against the two limits above:

| quantity | value | limit |
|---|---|---|
| pull-up rail | +3V3_REF_A = 3.3 V | VOD ≤ 5.5 V ✔ |
| pull-up | 10 kΩ → 0.33 mA per asserted driver | — |
| worst case sink (all six faulted at once) | 6 × 0.33 = **2.0 mA** | IOD ≤ 5 mA ✔ (2.5× margin) |
| lowest legal pull-up | 3.3 V / 5 mA = 660 Ω | — |

**A second, unasked-for find: `SDO` is also OD.** The same pin table reads
`SDO 27 OD  … This pin requires an external pullup resistor.` The control board ties all six driver
SDOs plus the MCP2518FD and MCP3208 onto one `SPI_MISO` net with **no pull-up on the BOM**. Open-drain
SDO is what makes that shared bus safe (no push-pull contention when two CS are briefly low), but the
line floats without a pull-up. **R151 (10 kΩ to +3V3_REF_A) is added for this** — it is a datasheet
requirement, not a nicety, and the prior wave missed it.

### 1.3 The arithmetic: the five pins are already spent

The demand, itemised exactly as the prior wave counts it (46 = the number in dispute):

| block | pins |
|---|---:|
| 7 motor channels × 3 PWM | 21 |
| 7 driver chip selects `nCS_M1..M7` | 7 |
| driver SPI `SCLK/MOSI/MISO` | 3 |
| `DRV_ENABLE` | 1 |
| **`nFAULT_ALL`** | **1** |
| MCP2518FD `CS`,`INT` | 2 |
| `UART_TX/RX` | 2 |
| `I2C_SDA/SCL` | 2 |
| TPS3430 `WDI` | 1 |
| 3 × ADS8588S serial port (as budgeted) | 6 |
| **total** | **46** |

Now the check the assignment asked for:

- If the six nFAULT arrived **separately** — which is what the power board actually has, six
  `M<n>_DRV_nFAULT` nets in the original board's own netlist — the line item is **6**, not 1, and the
  total is **51**.
  51 − 5 = **46**. The wire-OR is worth exactly 5 GPIO. ✔
- The board's interface contract already banks that 5. `pinmap.json` H1 pin 26 is `nFAULT_ALL`,
  direction `in`, comment **"6 open-drain nFAULT, wired-OR"**. The applied netlist has
  `nFAULT_ALL` as one net on two pads (`J_H1.26`, `U1.36`).
- So the board's *current* budget is **46 − 0 = 46**, and against 41 usable GPIO the shortfall is
  **−5**. `46 − 5 = 41` is arithmetically true and semantically wrong: it subtracts a saving that was
  already taken.

**So the answer to step 1 is a precise negative:** the wire-OR is legal, it saves 5, and it saves
nothing *further* on this board. Wiring it in could not have closed the gap; the five pins were
already gone.

### 1.4 The gap is actually 7, not 5

Independently re-derived here (and matching the prior wave): the three ADS8588S cannot share **one**
CS *and* **one** DOUT. One CS for three devices means two or three of them drive the same MCU pin at
once; the minimum legal serial port is 8 pins either way — shared CS + 3 DOUT
(`CS 1 + SCLK 1 + DOUT 3 + CONVST 1 + RESET 1 + BUSY 1 = 8`) or 3 CS + 1 DOUT. The budget's 6 is two
pins short, so the real digital demand is 48 and the gap is **−7**. With six drivers (M7 is a header
spare) the gap is −3. Either way, "short by 5" reproduces only because a 6-pin ADC bus was assumed.

### 1.5 Can firmware identify the faulting driver? No — and that is the design

One wire-OR'd line is an OR. It cannot encode which of six drivers pulled it low. What the firmware
can do, and what this board relies on:

1. The line is a **wake-up / latch**: on the falling edge the ISR knows *a* driver faulted, nothing more.
2. Localisation is a **poll of the six status registers over SPI** — each driver already has its own
   `nCS` (now from the 74HC138), and §8.6.1.1 defines `Fault Status Register 1` at **0x00**, whose bit
   10 is `FAULT` — *"Logic OR of FAULT status registers. Mirrors nFAULT pin."* Registers 0x01/0x02
   carry the VGS/OC detail. Worst case six 16-bit reads ≈ 6 × 2.56 µs at 10 MHz ≈ **15 µs**.
3. The poll is **non-destructive**: the status registers are read-only, so reading them does not clear
   anything. A latched fault is cleared only by the `CLR_FLT` bit (register 0x02 bit 0) or an ENABLE
   reset pulse — §8.4.1.3: *"the device can reenter the operating state by either setting the CLR_FLT
   SPI bit … or issuing a reset pulse to the ENABLE pin"*, and the pin table: *"An 8 to 40-µs pulse can
   be used to reset fault conditions."* That matters because it means firmware may poll freely and
   decide when to clear.

This is a real design statement, not a dodge: the interrupt buys **latency** (a hardware edge, not a
poll loop) and the SPI poll buys **identity**. What is given up is a same-instant per-driver flag; what
is gained is five GPIO.

---

## 2. Further savings — and their part cost

The wire-OR closes 0. The gap (5 on the old list, 7 corrected) was closed by moving signals off the MCU:

| measure | saves | cost | status |
|---|---:|---|---|
| **74HC138** 3→8 decode for `nCS_M1..M7` (3 GPIO → 7 CS) | **4** | **$0.15** (SOIC-16) | **applied** (U17) |
| **MCP3208** 8-channel SAR ADC for the 7 `NTC_M*` thermistors — frees GPIO40..46 | **7 digital** (net 6, after paying 1 `NTC_ADC_CS`) | **$2.38** (SOIC-16) | **applied** (U18) |
| drive `DRV_ENABLE` from the TPS3430 `/WDO` instead of a GPIO | 1 | $0 | **not used** — the budget already closes with 3 spare, and it would remove independent software disable |
| drop the 7th motor channel (M7 is a header spare; the power board has 6 drivers) | 4 + 3 PWM | $0 | **not used** — it is an interface change, not a pin re-allocation |
| unused GPIO reclaimed | **0** | — | the 3 spare (GPIO45–47) are deliberately kept as spare |

Result: **45 of 48 GPIO used, 3 spare.** Prices are LCSC single-unit as read by the prior wave on
2026-11-18 (`esc-mcu-closes/REPORT.md` §2); I did not re-fetch them this session, so treat them as
carried-over, not re-verified. The ADC **channel** budget is untouched and still closes: 3 × ADS8588S
= 24 external channels + the RP2354B's own 7 = 31.

---

## 3. Applied: netlist and coverage

| metric | netlist wave | after GPIO closure | **after this pass** |
|---|---:|---:|---:|
| footprints | 148 | 150 | **165** |
| pads | 768 | 800 | **842** |
| pads with a net | 559 (72.8 %) | 650 (81.3 %) | **699 (83.0 %)** |
| nets | 172 | 188 | **186** |
| single-ended nets | 53 | 23 | **3** |
| unconnected (kicad-cli) | 384 | 458 | see §5 |

The 3 survivors are one-ended at the **far** end, not at the MCU: `I2C_SDA`, `I2C_SCL` (U12
CAT24C32) and `WDI` (U8 TPS3430) — both parts are unresolved footprint/package defects (§4.3).

What this pass specifically did (all on `work/ctl_final.kicad_pcb`):

| # | change | effect |
|---|---|---|
| 1 | `nFAULT_ALL` pull-up **R150** 10 kΩ → +3V3_REF_A | the wire-OR's one required external part; net now 3 pads |
| 2 | `SPI_MISO` pull-up **R151** 10 kΩ → +3V3_REF_A | mandatory, `SDO` is OD (datasheet p7) |
| 3 | **R152** 0R `AGND`–`DGND` star tie | §4.1 |
| 4 | **R140–R147, C300, C301** — 10 BEC passives for U5/U6 | 8 single-ended nets closed |
| 5 | **R148, R149** 5.1 kΩ `CC1`/`CC2` → DGND | 2 nets closed (USB-C sink role) |
| 6 | **U5, U6** SOIC-8 → `HSOP-8-1EP` with pad 9 → DGND | the exposed pad exists and is grounded |
| 7 | **U10 MCP2518FD** 14-pad pin map | closes `CAN_CS`, `CAN_INT`, `XIN_40M`, `XOUT_40M`; creates `CAN_TX`/`CAN_RX` to U9 |
| 8 | **FL1** 2-pad 0805 → `L_CommonModeChoke_Coilank_ACM4532` 4-pad | closes `CANH_PHY`, `CANL_PHY`; the choke is now in series |
| 9 | parallel power contacts merged (`BAT_P_2/3/4`→`BAT_P_1`, `+3V3_REF_B`→`+3V3_REF_A`) | 4 single-pad nets removed — four lugs of the same 44.4 V bus cannot be four nets |

The MCP2518FD map is not invented: pins come from `drone-arm-final/esc_netlist.net` (a real
MCP2518FD-H/QBB node table) — 1 `TXCAN`, 2 `RXCAN`, 4 `~INT`, 5 `OSC2`, 6 `OSC1`, 7/15 `VSS`,
10 `SCK`, 11 `SDI`, 12 `SDO`, 13 `~CS`, 14 `VDD`. The choke winding map likewise: FL201 in the same
netlist has pin1 = transceiver CANH side, pin2 = `/CANH`, pin3 = transceiver CANL side, pin4 = `/CANL`.

**DRC set diff, before → after this pass** (companions present, `--severity-all`):

| type | before | after | delta |
|---|---:|---:|---:|
| clearance | 6 | 6 | **0** |
| courtyards_overlap | 2 | 2 | **0** (both pre-existing header-vs-header) |
| silk_edge_clearance | 7 | 7 | 0 |
| silk_over_copper | 5 | 7 | +2 |
| silk_overlap | 9 | 11 | +2 |
| **total** | **29** | **33** | **+4, all silkscreen warnings** |

**Zero new electrical violations.** The 8 errors (6 clearance + 2 courtyard) are the pre-existing ones;
the 4 new items are silkscreen warnings on the added 0603s, whose reference text was moved to `F.Fab`
so it cannot clip a neighbour again. Two intermediate passes are documented because they were wrong
first: a pads-only obstacle model put 0603s inside neighbouring courtyards (+25 `courtyards_overlap`),
and a first FL1 swap left the larger choke over C5/D3 — both fixed by re-placing against real
courtyard polygons (`surgery_v3.log`, `surgery3.log`).

---

## 4. The named gaps

### 4.1 AGND–DGND tie — **DONE**

`R152`, 0R 0603 at **(102.72, 21.73)**, pad 1 = `AGND`, pad 2 = `DGND`, immediately west of U14.
One point, by construction: the only copper path between the two nets on the board is through this part.
Why there: the ADC cluster (U14/U15/U16, 100 AGND pads vs 84 DGND) is the largest analogue return
consumer and the reference caps sit there, so the star sits at the ADC end, not at the MCU end.
Why a 0R and not a net-tie footprint: a 0R is a real BOM line, it can be lifted for a
conducted-emissions measurement, and it keeps the DRC honest (a net-tie would suppress the check that
proves nothing else bridges the two planes). Consequence for routing: `AGND` and `DGND` are still
**two nets** until they meet at this part, so both must be poured/ routed to it.

### 4.2 The ~10 missing passives — **DONE** (10 BEC + 4 more)

| ref | value | connects | why it was missing |
|---|---|---|---|
| R140 | 10 kΩ | `+5V` → `LM1_FB` | FB divider top — sets VOUT |
| R141 | 3.09 kΩ | `LM1_FB` → `DGND` | FB divider bottom |
| R142 | 100 kΩ | `BAT_P_1` → `LM1_RON` | on-time resistor |
| C300 | 100 nF | `LM1_BST` ↔ `LM1_SW` | bootstrap cap |
| R143 | 100 kΩ | `LM1_PGOOD` → `+3V3_REF_A` | PGOOD is open-drain |
| R144–R147, C301 | same set | U6 → `+5V_CAN` | second BEC |
| R148, R149 | 5.1 kΩ | `CC1`/`CC2` → `DGND` | USB-C sink advertisement |
| R150, R151 | 10 kΩ | `nFAULT_ALL`, `SPI_MISO` → `+3V3_REF_A` | **datasheet-mandated** (OD pins) |

Divider arithmetic: LM5164 feedback reference is **1.2 V** (datasheet SLVSF02 p15: *"A switching pulse
is set when VFB drops below 1.2V"*; p8 FB regulation threshold 1.2 V), so 10 k / 3.09 k gives
VOUT = 1.2 × (1 + 10/3.09) = **5.08 V**, a 1.6 % step against 5.00 V. `RON` is 100 kΩ; the switching
frequency it produces must be confirmed against the LM5164 RON table for the chosen inductor before
release (the datasheet's design procedure is §9.2.2, p11) — that is the one value I did **not**
close out, and I would rather say so than pick a number.

**Placement honesty:** the search placed each part in the nearest *courtyard-clear* position near its
IC, not at the electrically ideal spot. The FB dividers ended **up to ~8 mm** from their FB pins
(R140 at 64.60, 33.98 vs U5 pad 5 at 56.85, 28.23). A DC feedback node tolerates that, but a 400 kHz
buck layout should have it at the pin. **This is a layout task remaining, not a netlist one.**

### 4.3 The six footprint defects — 3 done, 1 blocked, 2 were never defects

| # | defect (as named) | verdict | evidence / reason |
|---|---|---|---|
| 1 | LM5164 lost its exposed pad (8 pads / 9 pins), U5 **and** U6 | **DONE** | swapped to `Package_SO:HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm`; 9/9 pads netted, pad 9 → `DGND` (the part's own GND). The plain EP land is used, not the thermal-via variant, to avoid 9 new vias against the existing pad grid; thermal vias are a layout-stage addition. |
| 2 | CAN choke: 2-pad inductor for a 4-terminal common-mode choke | **DONE** | swapped to `Inductor_SMD:L_CommonModeChoke_Coilank_ACM4532` (the footprint the source design itself uses for ACT45B-110-2P-TL003); pads 1/2/3/4 = `CANH_PHY`/`CAN_H`/`CANL_PHY`/`CAN_L`, i.e. two windings in series with each leg, case-grounded parts untouched. |
| 3 | MCP2518FD 14 pads vs 15 symbol pins | **DONE (functional)** | the 15th pin is `VSS`/EP, which exists only on the QFN/QBB variant; the board carries the SOIC-14 `MCP2518FD-I/SO`, which has no EP. All 14 pads are now netted; the residual is **symbol-side** (pin 15 must be marked NC or removed), not a footprint change. |
| 4 | TPS3430: 11-pin symbol in a SOT-23-6 land (U8) | **BLOCKED** | The symbol `Power_Supervisor:TPS3430WDRC` is the 10-pin VSON variant (pins `VDD1,VDD2,CWD,CRST,SET0,SET1,WDI,~WDO,NC,GND,GND`); the land is 6-pad SOT-23-6. There is no single fix that is a *layout* change: either relink the symbol to a 6-pin orderable part, or move the land to the 10-pin VSON and re-net 10 pads. Both need the orderable part number confirmed against the TPS3430 datasheet — a sourcing/schematic decision, not something to guess at 23:00. **Consequence: `WDI`/`WDO` stay unconnected and the window watchdog does not function.** |
| 5 | Crystals: 4-pad land for a 2-pin symbol (Y1, Y2) | **NOT A DEFECT** | The 3225 4-pad land is the correct land for the ABM8-SMD parts: pads **1,3** are the crystal terminals and pads **2,4** are the grounded case. Verified per-pad on the board: Y1/Y2 pad 2 = `DGND`, pad 4 = `DGND`, pad 1/3 = `XIN`/`XOUT`. A pad-count check flags this; a pin-function check does not. |
| 6 | USB-C: 22 pads vs 15-pin symbol | **NOT A DEFECT** | The 22 physical pads are 16 signal pads (A1–A12, B1–B12 with the A/B pairs commonly bussed) + 4 shield pads sharing name `S1` + 2 mechanical. The prior integrity probe already returned `verdict: OK` for J1 on pad *names*. |

Also worth recording, because it changes what "netted" means: **the second ADC `BUSY`.** `ADC_BUSY`
is taken from U14 only; U15/U16 `BUSY` remain netless. That is defensible *only* because one shared
`CONVST` starts all three sample-and-holds on the same edge, so U14's BUSY is a valid proxy — but it
must be written into the schematic note, or the next engineer will read it as a missing pin.

---

## 5. Routing — raster A* at 0.04 mm, DRC-gated

Rules carried from the proven router (`evidence/esc-route-control/03_route.py`): track **0.200 mm**,
clearance **0.200 mm**, via **0.600/0.300**, edge keep-out **0.500 mm**, grid **0.04 mm**, 2 layers.
The board has **0 pre-existing tracks, 0 vias, 0 zones**, so every segment below is new and every
number is attributable.

Routing load: **700 netted pads → 186 nets → 513 MST connections** (shortest span 0.00 mm — coincident
pads — longest 79.64 mm).

| | value |
|---|---:|
| connections needed | 513 |
| attempted inside the wall-clock box (360 s) | **270** |
| **routed** | **254 (94.1 % of attempted)** |
| segments written | **525** |
| vias inserted | **22** |
| failed, with reason | 16 — 12 *"no free start cell"* (pad box fully inside other-net clearance), 4 *"A\* exhausted / budget"* |
| **unconnected items, before → after** | **499 → 260** (−239, −47.9 %) |
| … after the MCU EP fix (§5.3) | **261** |

### 5.1 The first batch was rejected — and that is the gate working

The first 420 s run attempted 336 connections and routed 326. DRC, with companions, then said:

`shorting_items 0 → 11` · `tracks_crossing 0 → 7` · `solder_mask_bridge 0 → 11` · `clearance 6 → 50` · `track_dangling 0 → 42`

**That batch was discarded, not shipped.** Root cause, found in the router rather than guessed: (a) start
cells were generated on **both** layers regardless of where the start pad physically is, so a path could
begin on `B.Cu` under an F.Cu-only SMD pad — that produces a dangling end, no connection, and a track
running under a pad; (b) the end-point snap to the pad centre was applied **without** re-testing the
snap segment against the obstacle grid, so a dense 0.4 mm-pitch field could be shorted at the last
0.04 mm. Both were fixed (`scripts/route.py`: start layers from the pad's own layer set; goal accepted
only on a pad layer; snap accepted only if `seg_free`), then the batch was re-run from the clean board.

### 5.2 The accepted batch

| type | pre-route | post-route | delta |
|---|---:|---:|---:|
| clearance | 6 | 9 | **+3** |
| connection_width | 0 | 1 | +1 |
| track_dangling | 0 | 1 | +1 |
| shorting_items | 0 | **0** | 0 |
| tracks_crossing | 0 | **0** | 0 |
| solder_mask_bridge | 0 | **0** | 0 |
| courtyards/silk (all pre-existing) | 20 | 20 | 0 |
| **total** | **33** | **38** | **+5** |

So the batch is DRC-gated and **not clean**: 5 items (3 clearance errors, 1 segment below the netclass
width, 1 dangling end) are named by uuid in `work/drc_order_ready.json` and must be deleted or repaired
before the board is ordered. I did not delete them to make the count look better, because deleting a
cleared segment silently re-opens the connection it was making.

### 5.3 One more defect found while checking the pad map

`U1` pad **81** — the RP2354B's **exposed ground pad** — was **netless on every prior wave's board**.
A QFN-80 whose thermal/ground pad is unconnected is not a board; it is a heater with an intermittent
ground. It is now `DGND`. Honest cost: **+1 unconnected item**, because no copper has been routed to it
yet (it will be swallowed by the `DGND` pour).

### 5.4 What is *not* done to the copper

No zones are poured. On a 2-layer board with 101 `AGND` pads and 84 `DGND` pads, most of those
connections are supposed to be **planes**, not tracks, and the `AGND`–`DGND` star (§4.1) is only
meaningful once both are poured and meet at R152. The 261 unconnected items therefore overstate the
remaining *work* and understate the remaining *decision*: the pour strategy has to be chosen before the
number means anything.

---

## 6. Honest end state

**Do the 46 signals have a destination?** Yes — all 46. 44 close end-to-end (both ends netted);
3 nets are one-ended at the far end: `I2C_SDA`, `I2C_SCL` (U12 CAT24C32) and `WDI` (U8 TPS3430).

| | count |
|---|---:|
| digital signals demanded (corrected) | 48 |
| allocated to a named GPIO pad | **45** |
| spare GPIO left | **3** (GPIO45/46/47 = pads 56/57/58) |
| single-ended nets | **53 → 3** |
| pads netted | 559/768 → **700/842 (83.1 %)** |
| nets | 172 → **186** |
| unconnected items | 384 → 458 → 499 → **261** |
| DRC (companions, all severities) | 29 → 33 → **38** (11 errors: 9 clearance, 2 pre-existing header courtyards) |

**Can it be ordered? No.** Five reasons, each a decision or a part, none of them "needs more routing":

1. **The window watchdog cannot work.** U8's 11-pin symbol has no 6-pad SOT-23-6 counterpart decided;
   `WDI` and `~WDO` are unconnected, so the safety feature that motivates the TPS3430 is not in circuit.
2. **The calibration EEPROM is unconnected.** U12 CAT24C32 has no pin map anywhere on disk, so
   `I2C_SDA`/`I2C_SCL` are one-ended. Inventing a 5-lead I2C EEPROM pinout is exactly the failure mode
   that produces a board that passes DRC and fails at the fab, so it is left open and named.
3. **No schematic exists.** The netlist is *derived*, with per-pad provenance (SRC / DECIDED / EXT /
   OPEN). 295 of the original 439 pad writes were DECIDED choices. A fab order needs a schematic that
   someone has signed; the board currently encodes decisions, not a design intent anyone reviewed.
4. **Copper is incomplete and 5 items are gated out.** 254 of 270 attempted connections, 261
   unconnected items, and 5 DRC items from the accepted batch that must be repaired.
5. **No power planes.** `AGND`/`DGND` are un-poured, so the star tie is a component on an unrouted net.

**What this pass did buy.** The pin budget genuinely closes (45/48, 3 spare) instead of "short by 5";
the wire-OR is now *legal and complete* rather than assumed — one 10 kΩ pull-up on `nFAULT_ALL` and a
second on `SPI_MISO` that the datasheet demands and every prior wave missed; the BEC can conduct
(FB/RON/BST/PGOOD now exist); the analog and digital returns meet at one point; the choke is the right
part with the right windings; the MCU's ground pad is grounded; and 239 of 499 missing connections are
now real copper that passes the short/crossing/mask checks.

---

## Appendix — evidence index

| path | what |
|---|---|
| `work/ctl_closed_in.kicad_pcb` | input copy of the prior wave's closed board (independent re-verify: 150 fp / 800 pads / 650 netted / 188 nets / 23 single) |
| `work/ctl_closed_gaps.kicad_pcb` | + 2 pull-ups, tie, 10 BEC passives, 2 CC pulldowns, EP swap, MCP2518FD map |
| `work/ctl_closed_gaps2.kicad_pcb` | + parallel-contact merge, 4-pad CAN choke |
| `work/ctl_final.kicad_pcb` | + FL1 re-placed, reference silk to F.Fab — **0 tracks** |
| `work/ctl_routed.kicad_pcb` | + 525 segments, 22 vias |
| `work/ctl_order_ready.kicad_pcb` | + U1 pad 81 → DGND — **the artifact** |
| `work/drc_before.json` | 29 violations / 458 unconnected (input) |
| `work/drc_final.json` | 33 / 499 (all gaps applied, no copper) |
| `work/drc_routed.json` | **rejected batch**: 151 / 252 |
| `work/drc_routed2.json` | accepted batch: 38 / 260 |
| `work/drc_order_ready.json` | final: 38 / 261 |
| `work/route.json` | routed/attempted, failures with reasons, spans |
| `work/survey_in.json`, `survey_gaps.json`, `survey_final.json`, `survey_order_ready.json` | independent text-parse census at each stage |
| `logs/surgery*.log`, `logs/drc_*.log`, `logs/pass4.log` | raw tool output, including the two failed placement models |
| `scripts/` | `survey.py`, `surgery.py`, `surgery2.py`, `surgery3.py`, `route.py`, `pass4_ep.py` |
| datasheets | DRV835x **SLVSDY6A** ([TI](https://www.ti.com/lit/ds/symlink/drv8353.pdf), pin table p7, OD note; `VOD`/`IOD` p11; fault reset §8.4.1.3; status regs §8.6.1.1) · LM5164 **SLVSF02** ([TI](https://www.ti.com/lit/ds/symlink/lm5164.pdf), VFB = 1.2 V p15, FB threshold p8) — both downloaded and text-extracted locally because `web_fetch` rejects PDFs |

## Verdict

**The wire-OR is legal and worth exactly 5 GPIO — and this board had already banked those 5, so wiring
it closed nothing.** The pin budget closes anyway (45 of 48, 3 spare) via a 74HC138 CS decode and an
MCP3208 NTC offload, +$2.53 of parts. **The control board does NOT close: it is not routable and not
orderable** — 261 unconnected items, 5 gated DRC items, no pours, no schematic, a dead window watchdog
and an unconnected calibration EEPROM. What is fixed is fixed and measured; what is blocked is blocked
for a stated reason, not for want of trying.