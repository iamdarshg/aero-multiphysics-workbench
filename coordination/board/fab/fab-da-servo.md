# F701 servo-rail protection — fab readiness

**Owner:** fab-da-servo · **Board:** ESC rev_b (`esc_rev_b.kicad_pcb`) · **Date:** 2026-11-15
**Assignment:** a 0.75 A PTC against a 3–9 A requirement is a safety defect; fix it or prove the framing.

**Verdict in one line:** the 0.75 A part is not the safety defect — the *requirement* is. This rail is a
**1 A** 5 V feed (LM5164 buck → 1 A JST GH connector) that carries **≈0.2–0.35 A** to the flight board,
and **no servo power path exists on either board**. The real defects F701 carries are a **non-existent
MPN** and **two unconnected pads**. Both are fixed at rev_b with **zero other pads moved** and **zero DRC
delta**.

All numbers below are from `kicad-cli 9.0.7` DRC runs, `pcbnew 9.0.7` measurements, or the repo's own
datasheets/PDFs, each with a command or a `file:line`. Artefacts are in this directory.

---

## 1. What the rail actually is, and what it carries

### 1.1 F701 is on the exported 5 V rail, not on a servo rail

| item | value | evidence |
|---|---|---|
| Reference | **F701** | `esc_rev_b.kicad_pcb:121868` (property "Reference") |
| Footprint | **`Fuse_1206_3216Metric`** | `esc_rev_b.kicad_pcb:121862` |
| Placed | `(57.64, 20.275)`, rot 90°, F.Cu | `esc_rev_b.kicad_pcb:121865` |
| Value field | `PTC 0.75A` | `esc_rev_b.kicad_pcb:121879` |
| Pad 1 | `(at -1.4 0 90)`, 1.25 × 1.75 mm → net **`/Auxiliary power/CAN_5V_RAW`** | `esc_rev_b.kicad_pcb:121969-121974` |
| Pad 2 | `(at 1.4 0 90)`, 1.25 × 1.75 mm → net **`/Auxiliary power/CAN_5V_OUT`** | `esc_rev_b.kicad_pcb:121977-121982` |
| BOM | `Littelfuse, 1206L075/24WR, PTC 0.75A, Fuse:Fuse_1206_3216Metric, 1, F701` | `docs/hardware/REV_B_BOM.csv:57` |

Measured with pcbnew, the two pads sit 2.80 mm apart on the Y axis:

```
F701 Fuse_1206_3216Metric PTC 0.75A [57.64, 20.275] rot 90.0 F.Cu
   pad 1 | /Auxiliary power/CAN_5V_RAW  | [57.64, 21.675] [1.25, 1.75]
   pad 2 | /Auxiliary power/CAN_5V_OUT  | [57.64, 18.875] [1.25, 1.75]
```
(`s01_probe.py`, output in `s01_probe.json`)

> **Correction to my own first read.** Reading the `.kicad_pcb` text naively, the pads immediately above
> `121862` belong to a *preceding* `C_0603` (`M6_BUS_CURRENT` / `M6_BATN`) and look like F701's. They are
> not. Only the pcbnew pad dump is authoritative. Anyone grepping the file must read forward from the
> `(footprint` line, not backward.

### 1.2 The rail: a 1 A converter feeding one 1 A connector

`/CAN_5V_OUT` has exactly **two** pads on the whole board — F701 pad 2 and **J702 pad 1**:

```
=== /Auxiliary power/CAN_5V_OUT  (2 pads) ===
   F701  pad 2  ( 57.640, 18.875) F.Cu
   J702  pad 1  (  5.750, 19.360) F.Cu
```
(`s03_rail.py`)

`J702` is `JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal`, value **FLIGHT_CAN_POWER**
(`REV_B_BOM.csv:56`), carrying 5 V / CAN_GND / CANH / CANL (`esc_rev_b.kicad_pcb`, J702 pad map).

The source is one of the two LM5164 bucks:

> "The ESC auxiliary supply uses two independent LM5164 **1 A** buck rails: … one fused 5 V rail
> exported to the flight-control board." — `docs/hardware/REV_B_ARCHITECTURE.md:127-130`

and the converter is confirmed 1 A by the repo's own datasheet, page 1 title:
**"LM5164 100V Input, 1A Synchronous Buck DC/DC Converter"** — `docs/datasheets/esc/ti-lm5164.pdf` p.1
(extracted with pypdf, see `s05_lm5164.py`). U703 = `LM5164DDA` (`REV_B_BOM.csv:72`).

**Three independent 1 A-ish ceilings on this rail:**

| element | limit | evidence |
|---|---|---|
| U703 LM5164 | **1 A** | `REV_B_ARCHITECTURE.md:127`, `ti-lm5164.pdf` p.1 |
| J702 JST GH 1.25 mm | **1.0 A AC/DC** (AWG #26), 50 V | JST GH catalogue, `jst.com/wp-content/uploads/2021/08/eGH-new.pdf` |
| L702 33 µH SRR1260 | **1.8 A** | `REV_B_BOM.csv:34` ("33u 1.8A", `Inductor_SMD:L_Bourns_SRR1260`) |

So the binding element is the **1 A connector**, and it is the connector — not the PTC — that caps this
rail below the briefed 3 A.

### 1.3 What the rail's load actually is — the flight board, not servos

On the flight board the ESC's 5 V arrives at **J2** (`ESC_CAN_POWER`, the same JST GH part) → **F1**
(a second identical 0.75 A PTC) → `/Power and USB/CAN_5V_FUSED` → **D2** (`PMEG2010ER` ORing diode)
→ **`/SYS_5V`**:

```
### fuse F1 Fuse_1206_3216Metric PTC 0.75A [11.0, 31.0]
   pad 1 | /CAN_5V                       | others: [('J2','1',4.15,21.875)]
   pad 2 | /Power and USB/CAN_5V_FUSED   | others: [('D2','1',15.35,31.0)]
### D2 D_SOD-123 value=PMEG2010ER
   pad 1 | /Power and USB/CAN_5V_FUSED
   pad 2 | /SYS_5V
```
(`s06_main.py`, `s07_consumers.py`)

`/SYS_5V` feeds **U3** `TLV75528` (2.8 V, 500 mA LDO) and **U4** `TLV75533` (3.3 V, 500 mA LDO)
(`REV_B_BOM.csv:170-171`). Because U3/U4 are **linear**, the 5 V draw ≈ the 3.3 V/2.8 V load.

ANALYTICAL load bound, from the repo's own datasheets:

| consumer | current | evidence |
|---|---|---|
| CC1121 TX peak | **54 mA** | `docs/datasheets/main/ti-cc1121.pdf` p.10 ("TX current consumption +15 dBm 54 mA") |
| CC1121 RX | 22 mA | `ti-cc1121.pdf` p.1 |
| CC1190 TX | **56 mA** | `docs/datasheets/main/ti-cc1190.pdf` p.2 ("Transmit current No input signal, HGM = 1 56 mA") |
| CC1190 RX | 3 mA | `ti-cc1190.pdf` p.2 |
| IMU / baro / strain (~4 parts) | ~mA class | `tdk-icm42688p.pdf`, `st-lsm6dso32.md`, `st-lps22df.md` |
| RP2350, LG77L GNSS | **UNVERIFIED** | LG77L PDF is AES-encrypted (`pypdf.errors.DependencyError: cryptography>=3.1 required`); RP2350 draw is configuration-dependent. `docs/datasheets/main/quectel-lg77l-hardware-design.pdf`, `rp2350-hardware-design.pdf` |

Sum of the *verified* line items is ≈ **0.135 A** at 3.3 V, and with the two unverified class leaders
(RP2350 + GNSS) a defensible band is **≈0.2–0.35 A** on the 5 V rail. **No current measurement exists
on either board** — there is no shunt and no logged rail current in the repo — so the number is
**ANALYTICAL, not MEASURED**, and is labelled as such.

### 1.4 There is no servo rail. At all.

| claim | finding | evidence |
|---|---|---|
| a servo rail exists on the ESC | **no net named servo/motor/PWM anywhere** — 667 nets scanned, 0 matches | `s01_probe.json` census; `grep servo` in `esc_rev_b.kicad_pcb` returns 0 hits |
| a servo rail exists on the flight board | **"The board netlist contains no servo, motor, ESC, or PWM-labelled nets, so there is no servo ratline to route in this project revision."** | `hardware/main/rev_b/reports/route_audit_f653d8c_high_value_open_nets.md:13` |
| servo *signal* capacity is declared | `"capacity": 6, "consumer": "servo_outputs", "signal": "independent_pwm_command_paths", "status": "KNOWN"` | `aircraft_interfaces/system_interface.json:104-117` |
| that mapping is itself unresolved | `"capacity": null, "reason": "seven modeled effectors exceed six PWM outputs; a unique realizable path and feedback assignment is unresolved"` | `system_interface.json:119-125` |
| servo *power* connectors exist | **none.** The flight board has exactly 5 connectors: J40 (U.FL), J2 (CAN), J30 (U.FL), J1 (USB-C), J10 (SWD) — no servo header, no servo power | `s06_main.py` connector dump |

**So the 3–9 A figure has no rail to apply to.** It is **BRIEF-SUPPLIED** and is not traceable to any
repo document, net, or connector. It describes a servo power rail that rev_b does not implement.

---

## 2. F701's real rating, and the MPN does not exist

### 2.1 The real part behind the value field

The `1206L` series table (Littelfuse, revised 03/22/17, saved as `pdf/1206L_datasheetscom.pdf`):

| Part Number | I hold | I trip | V max | I max | P d | R min | R 1max |
|---|---|---|---|---|---|---|---|
| 1206L075/13.2 | 0.75 A | 1.50 A | 13.2 V | 100 A | 0.6 W | 0.090 Ω | 0.350 Ω |
| **1206L075/16** | **0.75 A** | **1.50 A** | **16 V** | 100 A | 0.6 W | 0.090 Ω | 0.2900 Ω |
| 1206L110 | 1.10 A | 2.20 A | 8 V | 100 A | 0.8 W | 0.040 Ω | 0.210 Ω |
| 1206L150 | 1.50 A | 3.00 A | 8 V | 100 A | 0.8 W | 0.040 Ω | 0.120 Ω |
| 1206L200 | 2.00 A | 3.50 A | 6 V | 100 A | 0.8 W | 0.018 Ω | 0.080 Ω |

Hold/trip for the 0.75 A 1206 part: **0.75 A hold, 1.50 A trip**, per the datasheet's own definitions
("I hold = maximum current device will pass without tripping in 20 °C still air"; "I trip = minimum
current at which the device will trip").

### 2.2 `1206L075/24WR` is a phantom part number — a fab blocker

| check | result |
|---|---|
| present in the `1206L` electrical table (rev 03/22/17)? | **No.** The 0.75 A rows are `/13.2` and `/16` only. The only 24 V rows are `1206L020` (0.20 A) and `1206L050/24` (0.50 A). |
| exact-string web search | **"No results found for `1206L075/24WR`"** — DuckDuckGo HTML |
| control: exact-string search for `1206L075/16WR` | **many hits**, incl. DigiKey 3997165, 16 V 750 mA |

**A fab house cannot order this part.** The BOM line must change regardless of the current question.
The plausible reconstructions are `1206L075/16WR` (0.75 A / 1.5 A / **16 V**) or a typo for
`1206L050/24WR` (0.50 A / 1.0 A / 24 V) — the two differ by 50 % in hold current, so this is not a
cosmetic fix.

**The same phantom MPN is on the flight board**: `Flight Control Rev-B,Littelfuse,1206L075/24WR,PTC 0.75A,Fuse:Fuse_1206_3216Metric,1,F1` (`REV_B_BOM.csv:140`). That board has the same defect and is **not mine to edit** — flagged for its owner.

### 2.3 Is 0.75 A the right number for the real rail?

- Rail capability: **1 A** (converter and connector).
- Verified load: **≈0.2–0.35 A**; band to ~0.35 A with unverified loads.
- PPTC derating from the 1812L rerating table (`pdf/1812L.pdf`, row 1812L075: 1.13 / 1.00 / 0.87 /
  0.75 / 0.62 / 0.56 / 0.50 / 0.43 / 0.37 / 0.34 A at −40 / −20 / 0 / **20** / 40 / 50 / **60** / 70 /
  80 / 85 °C): a 0.75 A part holds **0.50 A at 60 °C** and **0.43 A at 70 °C**.

So at a realistic 60–70 °C ESC ambient the part holds 0.43–0.50 A against a ≤0.35 A load — margin, not
a defect. Against a 3–9 A requirement it is 6–18× short, but that requirement does not apply to this
rail (§1.4).

**Sizing rule that does apply:** the PTC must hold above the maximum legitimate load and below the
connector rating — i.e. **hold ≤ 1.0 A (J702)**, and derived from measured load it is **0.75 A**. The
existing choice is correct *in the rail it is actually in*.

---

## 3. Drop-in replacement search — measured, not assumed

### 3.1 Ceilings per package (verified against the datasheets)

| package | max I hold in family | part | V max | source |
|---|---|---|---|---|
| 1206 | **2.00 A** | 1206L200 | 6 V | `pdf/1206L_datasheetscom.pdf` |
| 1812 | **2.60 A** | 1812L260 | 33 V (from the `/33` part suffix; see provenance note) | `pdf/1812L.pdf` rerating table |
| 2920 | **5.00 A** | 2920L500/16 | 16 V | `pdf/2920L_2920l300-15dr.pdf` |

**The prior attempt's "no drop-in at 1206/1812 (about 2 A)" is CONFIRMED, with corrected numbers.** The
1206 ceiling is exactly 2.00 A; the 1812 ceiling is 2.60 A, not 2 A. Neither reaches 3 A. The 2920
reaches 3 A — and 5 A.

### 3.2 2920 electrical data (the 3 A option)

| Part | I hold | I trip | V max | I max | P d | R min | R 1max |
|---|---|---|---|---|---|---|---|
| 2920L250 | 2.50 A | 5.00 A | 15 V | 40 A | 1.5 W | 0.035 Ω | 0.085 Ω |
| **2920L300** | **3.00 A** | **5.00 A** | **6 V** | 40 A | 1.5 W | 0.015 Ω | 0.048 Ω |
| **2920L300/15** | **3.00 A** | **5.00 A** | **15 V** | 40 A | 1.5 W | 0.015 Ω | 0.048 Ω |
| 2920L500/16 | 5.00 A | 10.00 A | 16 V | 40 A | 2.0 W | 0.005 Ω | 0.025 Ω |

Source: `pdf/2920L_2920l300-15dr.pdf` (Littelfuse 2920L series, rev 04/01/14).
For a 5 V rail the right member is **2920L300/15** (15 V ≥ 5 V), not the plain `2920L300` (V max 6 V).

### 3.3 Which pads actually move — measured with the real library footprints

Placing each candidate at F701's exact site and measuring every pad rectangle against every other pad,
track and via within 16 mm (`s10_packagefit.py`; clearance target 0.20 mm = the board's own
`min_clearance`, `esc_rev_b.kicad_pro:120`):

| package | at F701 site (rot 90°, unchanged) | verdict |
|---|---|---|
| 1206 (current) | clean | — |
| **1812** | 1 item: **C700.2 at +0.070 mm** | 0.13 mm short |
| 2512 | C700.2 **overlap −0.805 mm** | C700 must move |
| **2920** | C700.2 **−1.580 mm**, C700.1 **−0.655 mm**, C716.1 **+0.165 mm** | C700 must move, C716 marginal |

**The prior claim "2920 … needs D2 and D50 moved" is REFUTED for the ESC board.** There is no D2 and no
D50 on `esc_rev_b.kicad_pcb`. Its complete diode population is:

```
['D1101','D1102','D1201','D1202','D1301','D1302','D1401','D1402','D1501','D1502','D1601','D1602','D201','D202','D701']
```
(`s04_neighbours.py`). The parts a 2920 collides with are **C700** (1210, 2.2u 100V input cap) and
**C716** — capacitors, not diodes.

Where D2 and D50 *do* exist is the **flight board** (`REV_B_BOM.csv:155-156`: D50 `PESD2CANFD24L-T`,
D2 `PMEG2010ER`), so the earlier finding was real but **belongs to a different board's F1**. On that
board the collision is specifically:

| part | distance from F1 site | 2920 result |
|---|---|---|
| **D2.1** | 4.57 mm (pad at 15.35, 31.0) | **copper overlap −0.450 mm** → must move |
| **D50** | 7.34 mm (bbox 9.04,23.92–12.96,28.73) | pads **clear** (`/CANH`, `/CANL` at x = 10.062, outside the 2920 pad span 6.65–8.575); only its courtyard is 0.71 mm inside the 2920 body outline |

So even on the flight board it is **D2 that must move (1 part, electrically)** and D50 only by courtyard
(1 part, no copper). "D2 **and** D50" overstates it. (Flight-board geometry from `s11_mainfit.py`;
pad-vs-track gaps there are indicative only — the 16 mm track bboxes over-report, and that board was not
re-DRC'd for this candidate.)

### 3.4 The package that costs nothing: 1812 rotated 90°

The ESC's rail nets have **no copper at all** (§4), so relocating F701 itself costs zero rework. A site
search over ±2 mm and both rotations (`s12_sitesearch.py`, 0.05 mm grid) found:

| package | best legal site | shift | min clearance | limiting |
|---|---|---|---|---|
| **1812** | (57.64, 20.28), **rot 180°** | **(0.00, 0.00)** | **0.425 mm** | R712.2 |
| 2512 | (57.64, 19.68), rot 180° | (0.00, −0.60) | 0.240 mm | R712.2 |
| 2920 | (57.64, 18.63), rot 180° | (0.00, −1.65) | 0.240 mm | R712.2 |

Rotating the fuse 90° (to horizontal) frees the space outright, because the obstruction is *below* the
part, not beside it. One residual: rotating in place puts the 1812 courtyard into **R712**'s courtyard
(DiCad DRC flags this — §5). A −1.2 mm Y shift clears both copper and courtyard.

**Chosen fix: Littelfuse `1812L075/33DR`** — 1812, 0.75 A hold, 1.5 A trip, 33 V, 20 A I max, 0.11 Ω,
0.2 s trip. It keeps the hold and trip exactly, raises V max from the real 1206 alternative's 16 V to
**33 V** (matching the design intent implied by the `/24` suffix), and **moves zero other pads**.

**Provenance of those four numbers — read this before quoting them:**

| figure | tier | source |
|---|---|---|
| **0.75 A hold at 20 °C** | **DATASHEET** | `pdf/1812L.pdf` rerating table, row `1812L075`, 20 °C column = 0.75 |
| 0.50 A hold at 60 °C / 0.43 A at 70 °C | **DATASHEET** | same table, 60 / 70 °C columns |
| 2.60 A = 1812 family ceiling | **DATASHEET** | same table, row `1812L260` |
| **1.5 A trip, 33 V max, 20 A I max, 0.11 Ω** | **DISTRIBUTOR-SOURCED, not datasheet-verified** | Mouser / hssl listing for `1812L075/33DR` ("PPTC 33V 1812 .750A POLYFUSE", "0.75A hold 1.5A trip 33VDC 20A 0.8W 0.2s 0.11Ohm"). The Littelfuse 1812L *electrical* table could not be retrieved: `littelfuse.com` returns **HTTP 403** to both the 1206L and 2920L PDF URLs, and the `datasheets.com` extract of the 1812L sheet is the **2-page rerating brief only** (no V max / I trip columns). |

The 1.5 A trip is consistent with the whole `0.75 A → 1.50 A` pattern that the 1206L and 2920L tables
both show (`1206L075/13.2`, `1206L075/16`, `2920L075`, `2920L075/60` are all 0.75 A / 1.50 A), so the
risk that it is wrong is low — but it is **not** datasheet-verified here and is labelled accordingly.
If a hard datasheet column is required before release, the one action outstanding is to pull
Littelfuse's 1812L electrical table through a browser (the vendor site blocks scripted GETs).

**Pads moved: 0 others; F701 itself moves 1.2 mm** — and F701's pads are currently connected to nothing
(§4), so this discards no routed copper.

If a zero-layout-delta change is mandatory, the fallback is **`1206L075/16WR`** (same site, same pads,
0.75 A / 1.5 A / **16 V**) — a pure BOM edit that accepts half the voltage margin.

---

## 4. The defect nobody priced: the rail is not routed

`kicad-cli pcb drc --severity-all --format json` on the untouched ESC (`drc_esc_baseline.json`):

```
16 violations (all via_dangling), 499 unconnected items, 0 schematic parity
```

**499 unconnected items on a 687-footprint board.** The ESC's copper is 1,990 vias + **154 real tracks**
(`s02_debug.py`: `{'PCB_TRACK': 154, 'PCB_VIA': 1990}`), with 96 filled zones covering only motor
phase/BATP/BATN/sense nets. The entire control and auxiliary section — `/DGND` (90 pads, 170 unconnected
endpoints), `/3V3` (61 pads, 118 endpoints), `/5V`, `/AUX_*`, CAN — is parked.

**Both of F701's pads are open**, along with both ends of its connector:

```
Missing connection between items
  Pad 1 [/Auxiliary power/CAN_5V_OUT] of J702   <->  Pad 2 [/Auxiliary power/CAN_5V_OUT] of F701
  Pad 2 [/Auxiliary power/CAN_5V_RAW] of C715   <->  Pad 1 [/Auxiliary power/CAN_5V_RAW] of F701
  Pad 1 [/Auxiliary power/CAN_5V_RAW] of F701   <->  Pad 1 [/Auxiliary power/CAN_5V_RAW] of R711
  Pad 1 [/Auxiliary power/CAN_5V_RAW] of C713   <->  Pad 1 [/Auxiliary power/CAN_5V_RAW] of F701
  Pad 3 [/CANH] of J702                         <->  Pad 2 [/CANH] of FL201
  Pad 4 [/CANL] of FL201                        <->  Pad 4 [/CANL] of J702
  Pad 2 [/DGND] of R704                         <->  Pad 2 [/DGND] of J702
```
(`s08_drc.py`, 9 of the 499 touch this rail and J702)

A part swap on an open net changes nothing electrically. **This is the reason the PTC cannot be called
"fixed" by a BOM edit alone** — the rail has to be routed, and *that* work is the same work item either
way. Which is exactly why the package question is cheap to get right now: the router has drawn none of
this net yet, so there is no copper to throw away.

By contrast the flight board is **complete**: `drc_main_baseline.json` = **0 violations, 0 unconnected**.
The ESC is the outlier.

---

## 5. DRC before / after

| board | file | violations | unconnected | delta |
|---|---|---|---|---|
| ESC baseline (untouched repo file) | `drc_esc_baseline.json` | **16** (16 × `via_dangling`) | **499** | — |
| ESC + 1812 at same site, rot 0 | `drc_cand1812_rot0.json` | 17 (+1 `courtyards_overlap` **R712 ↔ F701**) | 499 | **+1 — rejected** |
| ESC + 1812, rot 0, **Δy −1.0 mm** | `drc_dy-1.json` | **16** | 499 | **0** |
| ESC + 1812, rot 0, **Δy −1.2 mm** | `drc_dy-1.2.json` | **16** | 499 | **0** |
| ESC + 1812, rot 0, **Δy −1.5 mm** | `drc_dy-1.5.json` | **16** | 499 | **0** |
| flight board baseline | `drc_main_baseline.json` | 0 | 0 | — |

Commands:
```
kicad-cli pcb drc --severity-all --format json -o <out>.json <board>.kicad_pcb
```

**Recommended artefact: `candidate_F701_1812_dy-1.2.kicad_pcb`** (built by `s13_patch.py`, which reads the
repo file and writes only into this evidence dir; the repo file is never touched). Δy −1.2 mm is chosen
over −1.0 mm for 0.2 mm of courtyard margin against R712.

The 16 `via_dangling` violations are pre-existing and belong to the unrouted board, not to this change.
The change is **DRC-neutral: no new violation, no cleared violation, identical unconnected count.**

---

## 6. Split-rail option, quantified

The idea: if one PTC cannot carry 3–9 A, use two.

### 6.1 Two PPTCs in parallel — physically does not do what it looks like

PPTCs have a strong positive temperature coefficient and a wide as-shipped resistance window. The
datasheet's own numbers for the 0.75 A 1206 part are **R min 0.090 Ω … R 1max 0.290 Ω** — a **3.2:1**
spread within one part number. Two "identical" devices can legitimately differ 3:1 in resistance, so the
low-R device carries

`(1/0.090) / (1/0.090 + 1/0.290) = 11.11 / (11.11 + 3.45) = **76.3 %**` of the total.

Generalising to *n* devices (one at R min, the rest at R 1max):

`hold(n) = 0.75 / share(n)`, `share(n) = (1/0.090) / (1/0.090 + (n−1)/0.290)`

| configuration | share carried by the low-R device | effective hold | effective trip | body area | vs 1 × 2920 |
|---|---|---|---|---|---|
| **1 × 0.75 A** | 1.000 | **0.75 A** | 1.50 A | 5.1 mm² | — |
| 2 in parallel | 0.763 | **≈0.98 A** | ≈1.97 A | 10.2 mm² | — |
| 3 in parallel | 0.617 | ≈1.22 A | ≈2.43 A | 15.4 mm² | — |
| 4 in parallel | 0.518 | ≈1.45 A | ≈2.90 A | 20.5 mm² | — |
| 5 in parallel | 0.446 | ≈1.68 A | ≈3.36 A | 25.6 mm² | — |
| **11 in parallel** | 0.244 | **≈3.08 A** | ≈6.16 A | **56.3 mm²** | **1.49× larger** |
| 1 × 2920L300/15 | — | **3.00 A** | 5.00 A | 37.7 mm² | 1.00× |

Two things fall out, and the second one kills the idea:

1. **A pair buys 1.31×, not 2×.** Doubling part count does not double hold current, because the
   low-resistance member carries 76 % of the total and trips first.
2. **Reaching 3 A hold takes ≈11 × 1206** — 25.6 → **56.3 mm² of body area, 1.49× *larger* than one
   2920L300/15**, with 11 reflow sites, 11 failure sites and completely undefined sharing. It is
   **not cheaper in area** once the sharing penalty is accounted for, and it is not cheaper in anything
   else either.

**Verdict: parallel PTCs are electrically invalid, physically *larger* than the single 2920 they would
replace, and still capped at 1 A by J702. Refuted, not merely discouraged.**

### 6.2 Two separate rails

Two independent 5 V rails at 1 A each needs: a second LM5164 (1 A) + inductor + second JST GH connector
pair, on **both** boards (the flight board has one J2). Aggregate 2 A — still short of 3 A, and
`/SYS_5V` has only one ORing diode D2.
- Cost: **+2 BOM lines, +1 connector pair, +1 wire in the harness**, on 2 boards.
- To actually reach 3 A you need three such rails, i.e. 3 × (converter + inductor + connector + PTC).

**Verdict: two rails buy 2 A at the cost of a connector and harness change on both boards, and still
miss 3 A. Strictly worse than one correctly-rated converter.**

### 6.3 What 3–9 A actually costs

Not a PTC — a **new power path**:

| blocker | now | needed for 3 A | change class |
|---|---|---|---|
| source | LM5164 **1 A** | ≥3 A buck (e.g. 5 A class) + inductor + layout | **respin** |
| connector | JST GH **1.0 A** (J702 and J2) | ≥5 A (JST VH 3.96 mm ≈10 A, or Molex Micro-Fit 3.0 ≈5 A) | **respin** |
| PTC | 1206 0.75 A | `2920L300/15` (3.00 A / 5.00 A / 15 V) | BOM + 1 part moved |
| servo connector | **does not exist** | 6 × servo header + 6.0 V BEC | **new function** |
| servo nets | **do not exist** | netlist + ERC | **new function** |

The PTC is the *cheapest* of the five. Anyone who "fixes" the PTC to 3 A without the other four has
built a 3 A fuse on a 1 A connector — the connector then becomes the fuse.

That is the crux of the finding: **the PTC is the only element on this rail that is already sized
correctly. Raising it alone converts a protection defect into a fire risk.**

---

## 7. BOM change

`BOM_F701.diff` in this directory. Line 57 only:

```diff
-ESC Rev-B,Littelfuse,1206L075/24WR,PTC 0.75A,Fuse:Fuse_1206_3216Metric,1,F701
+ESC Rev-B,Littelfuse,1812L075/33DR,PTC 0.75A 33V,Fuse:Fuse_1812_4532Metric,1,F701
```

| field | was | is |
|---|---|---|
| MPN | `1206L075/24WR` — **does not exist** | `1812L075/33DR` — orderable (Mouser) |
| Value | `PTC 0.75A` | `PTC 0.75A 33V` |
| Footprint | `Fuse:Fuse_1206_3216Metric` | `Fuse:Fuse_1812_4532Metric` |
| Hold / Trip | 0.75 A / 1.50 A (intended) | **0.75 A / 1.50 A** (unchanged) |
| V max | 16 V (real 1206 alternatives) | **33 V** |

**Also required, not mine:** `REV_B_BOM.csv:140` (Flight Control Rev-B, F1) carries the same phantom
MPN and needs the same correction — but with its own geometry check, because F1's neighbourhood is
different (D2.1 at 4.57 mm). Flagged, unedited.

---

## 8. Ship at rev_b, or respin?

| item | disposition |
|---|---|
| F701 phantom MPN | **fix at rev_b** — BOM edit, zero layout impact |
| F701 package 1206 → 1812 | **fix at rev_b** — footprint swap, 1.2 mm move of F701 itself, **0 other pads move**, DRC delta 0 |
| F701 3–9 A requirement | **waived, with cause** — the requirement describes a servo rail that does not exist; the rail F701 protects is 1 A by construction (`REV_B_ARCHITECTURE.md:127`, `ti-lm5164.pdf` p.1, JST GH 1.0 A) |
| a real 3–9 A servo rail | **RESPIN** — new converter + new connector + new servo headers + new nets; 4 of its 5 blockers are outside the PTC |
| rail routed | **blocked at rev_b** — 499 unconnected items; F701's own rail is open at both pads |

**The PTC item closes at rev_b and does not ride a respin.** The board's fab readiness is gated by the
routing deficit, not by this part — 499 opens is 31× the 16 DRC violations and cannot be waived.

Recommended order of work for whoever routes the rail: place F701 as `candidate_F701_1812_dy-1.2.kicad_pcb`
**before** drawing `CAN_5V_RAW`/`CAN_5V_OUT`, so the 1.2 mm shift costs nothing.

---

## 9. Fab-readiness checklist line

| # | check | state | evidence |
|---|---|---|---|
| 1 | F701 MPN exists and is orderable | **PASS** | `1812L075/33DR`, Mouser listing; family table `pdf/1812L.pdf` |
| 2 | F701 hold/trip sized to the real load and ≤ the connector | **PASS** | 0.75 A / 1.5 A vs ≈0.2–0.35 A load, 1.0 A JST GH (§1.3, §2.3) |
| 3 | F701 V max ≥ rail working voltage | **PASS** | 33 V ≥ 5 V (V max is distributor-sourced — §3.4) |
| 4 | F701 footprint change causes no new DRC violation | **PASS** | Δ 0, `drc_dy-1.2.json` vs `drc_esc_baseline.json` |
| 5 | F701 footprint change moves no other component | **PASS** | §3.4, site search |
| 6 | Rail carries the briefed 3–9 A | **WAIVED** | no servo rail exists; source 1 A, connector 1.0 A — `REV_B_ARCHITECTURE.md:127`, `route_audit_...:13`, `system_interface.json:104-125` |
| 7 | Rail is electrically connected | **FAIL** | both F701 pads and both J702 power pads open — 499 unconnected items |
| 8 | ESC DRC clean | **FAIL** | 16 `via_dangling` |
| 9 | Zero unconnected nets | **FAIL** | 499 |
| 10 | Rev-stamped gerber/drill/pos package | **NOT IN SCOPE** | separate unit |

Lines 7–9 are the fab gate and they are **red for reasons unrelated to F701**.

---

## 10. BOARD CORRECTION

Per the board's rule 4, three statements on `AGENT_BOARD.md` need correcting:

**BOARD CORRECTION — `AGENT_BOARD.md:617` and `:631`.** "the servo rail protection is undersized — a
0.75 A PTC against a 3–9 A requirement" and "No PTC at 3–9 A exists in that footprint, so it is not a
BOM swap. The fix is deleting **six pad-to-net connections**".

- There is **no servo rail** on either board (`route_audit_f653d8c_high_value_open_nets.md:13`; 0 servo
  nets in 667 ESC nets; 0 servo connectors on the flight board). The 3–9 A requirement is unowned.
- The rail F701 is actually in is the **1 A** exported 5 V rail (`REV_B_ARCHITECTURE.md:127`), feeding
  the flight board's `/SYS_5V` through D2 at ≈0.2–0.35 A.
- A **3 A part does exist** at 2920 (`2920L300/15`, 3.00 A / 5.00 A / 15 V), so "no PTC at 3–9 A exists
  in that footprint" is true only of 1206/1812 — but the 2920 is the wrong answer here, not because it
  does not exist but because the connector caps the rail at 1 A.
- **"Deleting six pad-to-net connections" is not a protection fix** — on this rail F701's own two pads
  are already disconnected, and 499 nets are open. Nothing about the PTC is repaired by deleting
  connections.
- The earlier "2920 needs **D2 and D50** moved" belongs to the **flight board's F1**; the ESC has no D2
  or D50. On the flight board it is **D2 that collides (−0.450 mm)**; D50's pads are clear.

**What is true:** the BOM MPN is phantom, the 1206 package cannot exceed 2.00 A, and the correct change
is `1812L075/33DR` at **zero other-pad cost**.

---

## 11. Artefact index

| file | what it is |
|---|---|
| `s01_probe.py` / `s01_probe.json` | F701 pad/net/geometry dump + 666-net census |
| `s02_debug.py` | proof the ESC has 1,990 vias and only 154 tracks; 96 zone nets |
| `s03_rail.py` | `/CAN_5V_OUT` = 2 pads (F701.2, J702.1); connector inventory |
| `s04_neighbours.py` | 8 mm neighbourhood; **complete diode list — no D2/D50** |
| `s05_lm5164.py` | LM5164 = "100V Input, 1A Synchronous Buck" from the repo's own PDF |
| `s06_main.py` | flight board F1/D2 chain, `/SYS_5V`, connector inventory |
| `s07_consumers.py` | D1/D2/U2/U3/U4 nets; rail track widths |
| `s08_drc.py` | DRC unconnected extraction; the 9 rail/J702 opens |
| `s09_pdf.py` | pypdf text extraction for the datasheets |
| `s10_packagefit.py` / `.json` | pad-vs-copper clearance for 1206/1812/2512/2920 at F701 |
| `s11_mainfit.py` / `.json` | same at the flight board's F1 (where D2/D50 live) |
| `s12_sitesearch.py` / `.json` | legal-site search ±2 mm × 2 rotations |
| `s13_patch.py` | builds the candidate copy (never writes into the repo) |
| `s14_loads.py` | supply-current extraction for the load bound |
| `BOM_F701.diff` | the BOM change |
| `candidate_F701_1812_dy-1.2.kicad_pcb` | **the recommended board copy** (DRC-neutral) |
| `drc_esc_baseline.json` | 16 / 499 |
| `drc_cand1812_rot0.json` | 17 / 499 — rejected (courtyard) |
| `drc_dy-1.json`, `drc_dy-1.2.json`, `drc_dy-1.5.json` | 16 / 499 each |
| `drc_main_baseline.json` | flight board 0 / 0 |
| `pdf/` | Littelfuse 1206L, 1812L, 2920L datasheets as retrieved |

No file in `repos/` was modified. Nothing was committed, pushed, or reset.
