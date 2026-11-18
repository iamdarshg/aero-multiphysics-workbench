# ESC CONTROL board — giving it a real netlist

**Task:** the CONTROL board (107.00 × 60.00 mm, 2-layer, 100 % single-sided) had 648 of 768 pads netless; its only
connectivity was 41 ground links between adjacent socket pins. Port the connectivity from the original unsplit ESC
board by reference designator, then handle the 120 header pins.
**Status: measured, partially solvable, and the part that is not solvable is pinned to one budget shortfall (5 GPIO), six footprint defects and ten missing passives.**
<u>Work was done on copies only.</u> Nothing was written into a repository, committed, reset or pushed.

| question | answer |
|---|---|
| Original unsplit board | 607 footprints / 3 068 pads / **564 nets** / 2 617 pads netted / 451 netless / 7 230 tracks / 126 zones. Unconnected **282 on both tools**. Not the "~207" the brief expected — 207 is the count the split *cuts*, not the board's net count. |
| CONTROL components matched by reference | **0 of 148.** 3 refs collide (H1/H2/H3) but are different parts and carry no nets. |
| Netlist ported | **Impossible: 0 pads.** The split moved no reference designators; the control board was built from scratch out of KiCad library footprints. |
| Netlist *derived* instead | **436 new (ref,pad,net) assignments / 439 pad writes**, 120 → 559 pads netted (72.8 %), 80 → 172 nets. Every net tagged SRC / DECIDED / EXT / OPEN. |
| 120 header nets | **120/120 verified** identical to `pinmap.json`. |
| Seven-to-one merge | Target exists (one RP2354B). Application **does not close: 46 digital signals wanted vs 41 usable GPIO — short by 5.** 41 GPIO pads left netless on purpose. |
| Unconnected | 41 → **384** (kicad-cli) and 41 → **384** (pcbnew). Ratsnest now exists. |
| DRC (full companions) | 37 → **29**. Set diff: **0 physically new**, 8 physically removed, 6 relabelled. |
| Routed | **0.** 118 nets / 506 endpoints to route, and **53 nets have only one pad** — a complete route does not exist yet. Reasons in §8. |
| Real netlist? | **Yes on 559 of 768 pads (72.8 %), as a derived netlist with provenance. Not shippable:** 209 pads have no source, 53 nets are single-ended, 5 footprint defects and ~10 missing passives remain. |

---

## 0. Method, provenance and files

- KiCad 9.0.7: `kicad-cli.exe` for DRC; the bundled `C:\Program Files\KiCad\9.0\bin\python.exe` for pcbnew
  (load/save/`SetNet` only — `PCB_VIA.GetWidth()` was **never called**, no script touches vias or zones).
- s-expression parsing is done with my own reader (`scripts/kpcb.py`), not pcbnew, so counts are reproducible
  without a GUI-grade API. Every headline number was produced **twice, by two tools**, and they agree (§7).
- DRC ran in directories that carry the companions (`.kicad_pro`, `.kicad_dru`) — never against a naked `.kicad_pcb`,
  which is what invents footprint violations.

| role | path | SHA-256 |
|---|---|---|
| original unsplit board (read) | `evidence/esc-pinsplit-v2/esc_copy.kicad_pcb` | `A47E6E8C…A45041C` |
| same board, second copy (read) | `evidence/esc-split-control/src/esc.kicad_pcb` | `A47E6E8C…A45041C` (identical) |
| CONTROL board in (read) | `evidence/esc-split-layout/esc_control_board.kicad_pcb` | `092582E2…3A7A0` |
| CONTROL board out (written once) | `work/esc_control_board_netted.kicad_pcb` | `E702EBCC…EBF80B` |

`evidence/` is a junction to `D:\ep-audit-evidence`; D: had 140.66 GB free before the run, 140.6 GB after
(total written < 2 MB, board copies only).

**What the CONTROL board actually is.** `evidence/esc-split-layout/03_build_control.py` builds it from
`pcbnew.FootprintLoad(lib, name)` calls and assigns nets **only** to the three sockets, from `pinmap.json`
(line 122-124). There is no schematic, no `.net`, no symbol link. Its 28 distinct part values were chosen by that
script; none of them was copied from the original board. That is the root cause of the whole blocker, and it is
already stated in the previous wave's own report (`esc-split-layout/REPORT.md:246`): *"Only the 120 header pads
carry nets … the split boards have no schematic and inventing pin-net maps would be fabrication."*

---

## 1. The original unsplit ESC board — baseline (**MEASURED**)

`python dump_board.py` (text parse) and `pcbnew` agree exactly:

| metric | pcbnew | text parse | note |
|---|---:|---:|---|
| footprints | 607 | 607 | |
| pads | 3 068 | 3 068 | |
| pads with a net | 2 617 | 2 617 | 85.3 % |
| pads netless | 451 | 451 | no-net pads, mechanical + NC |
| net table entries | 564 | 564 | incl. net 0 |
| tracks | 7 230 | 5 286 segments + 1 944 vias | zones 126 |
| **unconnected (pcbnew)** | **282** | — | `GetUnconnectedCount(False)` |
| **unconnected (kicad-cli)** | **282** | — | same number, second tool |
| DRC violations (kicad-cli, companions present) | **382** | — | via_dangling 144, clearance 120, hole_clearance 42, shorting 24, track_dangling 24, mask_bridge 12, courtyards 10, zones_intersect 6 |

So the source board **does** carry a real netlist (564 nets, 2 617 netted pads) — the premise holds. It is a
work-in-progress board, not a clean one: 282 unconnected and 382 violations, dominated by dangling vias and
unfilled zone fills. That matters for §5: the port target is rich in connectivity, poor in polish.

**Correction to the brief:** the original has **564 nets, not ~207.** 207 is the number of nets the *split cuts*
(`esc-pinsplit-v2/s2_cut.py`), i.e. the interface, not the board.

---

## 2. Reference matching: 0 of 148 (**MEASURED**)

| | count |
|---|---:|
| CONTROL refs | 148 |
| original refs | 607 |
| refs present on both | 3 |
| … of those, same part | **0** |
| CONTROL refs with no counterpart | 145 |
| original refs not on CONTROL | 604 |

The three collisions are `H1/H2/H3` = `MountingHole_3.2` on the control board vs `M4` on the original — mechanical
holes with **zero nets**. Every real part is renumbered: control `U1 = RP2354B`, `U5/U6 = LM5164`, `U14-16 =
ADS8588S`, `R100A…R130B`, `C200…C230`; the original uses `U1101…U1601` (six cells), `U201…` (supervisor),
`C1164…`. The split preserved **positions of nothing and names of nothing**; it preserved function only.

**Consequence: step 3 of the assignment (apply `original[ref][pad].net` to `control[ref][pad]`) has exactly zero
inputs.** No amount of care makes it work. This is not a missing file or a path error — the two boards share no
anatomy.

---

## 3. Why a *derived* netlist is the only honest route — and where it stops

Nets can be derived without a schematic only if each pad's **pin number maps to a documented pin function**. That
mapping is what the board does not carry. Measured, pad count vs symbol pin count:

| value | control pads | symbol/part pins | verdict |
|---|---:|---:|---|
| RP2354B | 90 | 81 | 81 numbered + 9 unnamed mechanical pads — usable |
| ADS8588S | 64 | 64 (datasheet) | usable (pin table transcribed, §A.2) |
| TCAN3413 | 8 | 8 | usable (pin order caveat, §A.3) |
| USBLC6-2SC6 | 6 | 6 | usable |
| PESD1CAN | 3 | 3 | usable |
| SN74LVC1G08 | 5 | 5 | usable |
| AP2112K-3.3 | 5 | 5 | usable |
| **LM5164** | **8** | **9** | **footprint lost the exposed pad** (HSOP-8-1EP → SOIC-8) |
| **MCP2518FD** | **14** | **15** | pad count differs, mapping unproven |
| **TPS3430** | **6** | **11** | symbol is 11-pin, footprint is SOT-23-6 → **wrong package** |
| **CAN choke** | **2** | **4** | a common-mode choke has 4 terminals; placed in a 2-pad inductor |
| **12 MHz / 40 MHz** | **4** | **2** | 4-pad crystal land pattern, 2-pin symbol (resolvable, unmapped) |
| **USB-C receptacle** | **22** | **15** (16-pin pattern) | pad names carry function; resolvable |
| W25Q128, REF5030, CAT24C32 | 8 / 8 / 5 | no local source | industry-standard pinouts only |
| R / C / L / shields / holes | 2 / 2 / 2 / 1 | 2 / 1 | no electrical ambiguity |

I did **not** invent pin maps for the five defective parts. They stay netless and are listed in §A.1 as defects to
fix, because a netlist written over a wrong footprint is worse than no netlist: it passes DRC and fails at the fab.

---

## 4. The netlist that was applied (**MEASURED**, with provenance)

`scripts/design_netmap.py` emits `work/netmap.json`; `scripts/apply_nets.py` writes it onto a copy with pcbnew.
Net names are reused where the pinmap already defines them (`+3V3_REF_A`, `DGND`, `AGND`, `CAN_H/CAN_L`, `SWDIO`,
`SWCLK`, `NRST`, `NTC_M*`, `CSA_M*`, `BUS_*`), so the header stays authoritative.

| provenance | meaning | pads |
|---|---|---:|
| **PROVEN** | already on the board from the agreed pinmap (untouched) | 120 |
| **SRC** | pin function from a local authoritative source (KiCad 9 symbol library, or the `pinfunction` field of a `.net` from another DRC'd project), and only one net is possible on this board | 142 |
| **DECIDED** | a design choice the board's own BOM/architecture forces — all 7 logged in §B | 295 |
| **EXT** | industry-standard pinout, no local library hit (25-series SOIC-8 flash) | 8 |
| **OPEN** | deliberately left netless: no source exists | 8 |
| — | not attempted: pin mapping unproven (§3) or needs the GPIO allocation (§6) | 195 |

Applied and verified per pad:

| check | value |
|---|---:|
| pad-net writes | 439 (436 distinct `(ref,pad)` + 3 extra shield pads sharing pad name `S1`) |
| `(ref,pad,net)` triples added | **436** |
| triples lost | **0** |
| triples changed to a different net | **0** |
| triples added that are **not** in the netmap (accidents) | **0** |
| pads with a net, before → after | 120 → **559** (text parse: 556 unique pad names; 768 physical pads − 12 duplicate-name pads) |
| pads netless, before → after | 648 → **209** |
| net table, before → after | 80 → **172** (+92) |

What the 209 remaining netless pads are:

| ref | pads | why |
|---|---:|---|
| U1 RP2354B | 51 | 41 unallocated GPIO + ADC7 spare + 9 unnamed mechanical pads |
| U14 / U15 / U16 ADS8588S | 35 each (105) | DB0-15 / CS / RD / BUSY / CONVST / RESET (needs the GPIO allocation) + REFSEL / REFCAPA-B / REGCAP1-2 straps (parts not on the BOM) |
| U10 MCP2518FD | 14 | pad count ≠ pin count (§3) |
| U11 REF5030 | 8 | no local pin source; reference configuration undecided |
| U8 TPS3430 | 6 | 11-pin symbol in a 6-pad footprint |
| J2 SWD header | 5 | no local pin map; 5-pin SWD pin order is vendor-dependent |
| U12 CAT24C32 | 5 | no local pin source |
| J1 USB-C | 4 | A8/B8 (SBU) + 2 unnamed shield pads — no signal here |
| U13 SN74LVC1G08 | 3 | A/B/Y are the WWDT gating decision, not made |
| U9 TCAN3413 | 2 | TXD/RXD have no MCU pin |
| FL1 choke | 2 | 2-pad footprint for a 4-terminal part |
| H1, H2, H3 | 3 | mounting holes — correctly netless |
| U7 AP2112K | 1 | pad 4 = NC, correctly netless |
| **total** | **209** | |

**53 nets carry a single pad** — they are the visible shape of the missing design, and they are listed in §C:
21 `PWM_M*_*`, 7 `nCS_M*`, `SPI_*`, `DRV_ENABLE`, `nFAULT_ALL`, `UART_*` (no MCU pin), `CANH_PHY`/`CANL_PHY`
(no choke), `CC1`/`CC2` (no 5.1 k pulldowns on the BOM), `LM1/LM2_FB|RON|BST` (no feedback/RON/BST passives),
`BAT_P_2..4` and `+3V3_REF_B` (paralleled contacts).

---

## 5. The 120 header pins (**PROVEN**)

Verification, not assertion: every socket pad `(ref, pad number)` was compared against `pinmap.json`.

| header | pads checked | exact net match | mismatch |
|---|---:|---:|---:|
| J_H1 (H1 SYSTEM) | 40 | 40 | 0 |
| J_H2 (H2 PWM) | 40 | 40 | 0 |
| J_H3 (H3 ANALOG) | 40 | 40 | 0 |
| **total** | **120** | **120** | **0** |

Signal/ground split per header matches the brief: H1 25/15, H2 31/9, H3 21/19; the board's net table holds
79 interface nets = 77 signals + `DGND` + `AGND`. Nothing was changed here.

---

## 6. The seven-to-one merge: what merges, and why it cannot be applied

**What exists.** Original: six `STM32G431CBT6` cell supervisors plus a 70-part supervisor block (200-series,
`RP2354B` = U201) that is on the PCB but absent from `esc.net`. Control: one `RP2354B` (U1). The merge *target* is
therefore already correct — the 6→1 hardware exchange is done.

**What the merge produces on the interface.** The split cuts 207 nets; the surviving interface is 77 signals +
43 ground returns = 120 positions. Those 120 are exactly the socket nets above and are 120/120 applied.

**Why the merge cannot be applied at the MCU.** Re-pointing six MCUs' peripheral nets to one MCU requires a pin
allocation, and no allocation exists anywhere on disk. The allocation also does not close. Measured:

| MCU-side demand (flexible GPIO only) | pins |
|---|---:|
| `PWM_M1..M7` × 3 lines | 21 |
| `nCS_M1..M7` | 7 |
| DRV SPI `SCLK`/`MOSI`/`MISO` | 3 |
| `DRV_ENABLE` | 1 |
| `nFAULT_ALL` | 1 |
| MCP2518FD `CS` + `INT` | 2 |
| `UART_TX`/`UART_RX` | 2 |
| CAT24C32 I²C | 2 |
| TPS3430 `WDI` | 1 |
| 3 × ADS8588S on one shared serial bus (`SCLK`,`CS`,`DOUT`,`CONVST`,`BUSY`,`RESET`) | 6 |
| **total digital** | **46** |
| flexible GPIO available: 48 − 7 (NTC_M1..M7 on ADC0..ADC6) | **41** |
| **shortfall** | **−5** |

(`SWDIO`/`SWCLK`/`RUN`/`USB`/`QSPI` are dedicated pins and are not in this budget.)

Two facts make this a *design* blocker rather than a dead end, and both are worth quoting:

1. **The channel count closes exactly.** 3 × ADS8588S = 24 analogue inputs (21 `CSA_M*` + `BUS_V` + `BUS_I_A` +
   `BUS_I_B`) and the RP2354B's own ADC0..ADC6 take the 7 `NTC_M*` = **31 channels**. Decision D6 (§B) puts the
   three phases of a motor on one ADC so they stay simultaneous.
2. **The ADS8588S is only viable in serial mode.** It is a parallel/byte/serial 16-bit part
   ([TI SBAS642A](https://www.ti.com/lit/ds/symlink/ads8588s.pdf)); three of them in parallel would need 48 data
   lines *plus* control — impossible on a 48-GPIO MCU. In serial mode (DB7/DOUTA, DB8/DOUTB) the three share one
   bus in 6 pins, which is what the table above assumes.

**Orphaned nets: 53** (§C). None were dropped silently — every one is listed with its reason: 35 are interface
signals that have no MCU pin, 8 are passives the BOM does not contain, 4 are paralleled contacts, 4 need a choke
or CC pulldowns the BOM lacks, 2 are the 40 MHz crystal's controller side (MCP2518FD unmapped).

---

## 7. Verification before / after (**MEASURED, both tools**)

| metric | before | after | delta | tool |
|---|---:|---:|---:|---|
| pads with net | 120 | 559 | +439 | pcbnew + text parse |
| net table | 80 | 172 | +92 | pcbnew + text parse |
| **unconnected** | **41** | **384** | **+343** | `kicad-cli pcb drc` |
| **unconnected** | **41** | **384** | **+343** | `pcbnew GetConnectivity().GetUnconnectedCount(False)` |
| DRC violations | 37 | 29 | −8 | `kicad-cli pcb drc --severity-all`, companions present |

**The rise from 41 to 384 unconnected items is the correct and expected result of a netlist appearing.** With no
nets there is no ratsnest to be unconnected; the 41 old items were the ground links between adjacent socket pins.
384 is now "559 netted pads, zero copper". It is *not* a regression — it is the first honest measure of how much
routing this board needs. Reporting it as anything else would be hiding the result.

**DRC set diff** (identity = violation type + sorted item descriptions):

| | count |
|---|---:|
| present before, gone after | 14 |
| … of those, re-labelled with their new net name (same physical item) | 6 (U9 pads 1,2,3,5,6,7) |
| … of those, genuinely gone (they were netlessness artefacts) | 8 (J1 A1/A4/A9/A12: 4 clearance + 4 solder-mask bridges — those four pads are now `DGND`/`USB_VBUS`, i.e. same-net pairs) |
| **physically new violations** | **0** |
| violations new after, being the U9 relabels | 6 |

So: **0 new DRC problems were introduced**; 8 disappeared because four USB-C pads stopped being "no net" islands.
Residual 29 = 10→6 clearance, 9 silk_overlap, 7 silk_edge_clearance, 5 silk_over_copper, 2 courtyards_overlap
(all pre-existing, all mechanical/silkscreen, none created by the netlist).

---

## 8. Routing: 0 routed, and exactly why

Measured routing load of the netted board (text parse, both tools agree on net/pad counts):

| | value |
|---|---:|
| nets with ≥ 1 pad | 171 |
| nets needing routing (≥ 2 pads) | **118** |
| ratsnest endpoints | **506** |
| largest nets | `AGND` 98 pads, `DGND` 68, `+3V3_REF_A` 38, `+5V` 16, `BAT_P_1` 8 |
| **single-pad nets (nothing to route to)** | **53** |

I routed **0 of 118** and **0 tracks were written**. That is a decision, not an omission, and the reasons are
upstream of the router:

1. **53 nets are single-ended** (§C). No router can connect a pad to itself; the interface cannot be routed until
   the GPIO allocation exists.
2. **The BEC cannot conduct.** U5/U6 have no `FB` divider, no `RON` resistor and no `BST` capacitor on the BOM
   (§A.4) — the `LM1/LM2_FB|RON|BST` nets end on a single pad. Routing them would draw copper to nothing.
3. **`AGND` and `DGND` are two nets with no tie** on the BOM. Routing them separately, as DRC requires, would
   build a board that oscillates; the star point is a schematic decision.
4. **The netlist is provisional by construction** — 295 of 439 pad writes are DECIDED, not sourced. Routing copper
   over decisions that are about to change would produce numbers that mean nothing and would have to be thrown
   away, and it would look like progress.

A raster A* router at 0.04 mm with the proven rules (track 0.150 min, clearance 0.200, via 0.600/0.300, edge
0.500) already exists at `evidence/esc-route-control/03_route.py`; only its two path constants need repointing at
this board. It should run **after** §9 closes, not before.

---

## 9. Verdict, and the shortest path to shippable

**Does the CONTROL board now have a real netlist?** On 559 of 768 pads (72.8 %), yes: a derived netlist, per-pad
provenance-tagged, 436 triples added with 0 lost / 0 mis-assigned / 0 accidental, DRC-neutral, and cross-checked
by two tools. **Is it shippable?** No. 209 pads have no source, 53 nets are single-ended, and the BOM cannot build
what the nets describe. Netlisting was never the top blocker — it is the symptom.

Five things, in order, make it shippable. Each is a decision or a part, not a script:

| # | action | closes |
|---|---|---|
| 1 | Allocate the 41 usable GPIO (46 wanted). Cheapest closure: add **one 74HC138** (3 GPIO → 7 DRV `nCS`, saves 4) and drive `DRV_ENABLE` from the existing SN74LVC1G08 AND of `WDO` (saves 1) → **41/41, zero spare**; dropping UART gives 2 spare; dropping the `M7` spare channel gives 5. | 41 netless GPIO pads + 35 single-ended interface nets |
| 2 | Fix the 5 footprint defects: `TPS3430` 11-pin symbol in SOT-23-6, `LM5164DDA` EP missing, CAN choke 2 pads for a 4-terminal part, crystals 4-pad/2-pin, `MCP2518FD` 14 vs 15 | 22 netless pads, 4 nets |
| 3 | Add the ~10 missing passives: 2 × `FB` divider, 2 × `RON`, 2 × `BST` cap, 1.1 V `VREG` L+C, `REFCAPA/B`, `REGCAP1/2`, `REFSEL`/`OS`/`RANGE` straps, `CC1/CC2` 5.1 k, one `AGND`-`DGND` tie | 12 single-ended nets + the ADS8588S straps |
| 4 | Assign symbols to footprints (i.e. capture the schematic) so `REF5030`, `CAT24C32`, `W25Q128`, `TPS3430` and the SWD header get pin maps | 24 netless pads |
| 5 | Then route: 118 nets / 506 endpoints, raster A* 0.04 mm, DRC-gated per batch | the 384 unconnected items |

Until step 1-3 are done, "routable" and "orderable" are not reachable — and no amount of copper or netlist
authoring changes that, which is why I stopped at the boundary instead of manufacturing numbers past it.

---

## Appendix A — footprint/pin integrity defects (**MEASURED**)

### A.1 Pad count vs symbol pin count
See the table in §3. Six defects: `LM5164` (8 pads / 9 pins, EP lost), `TPS3430` (6 / 11), `CAN choke` (2 / 4),
`MCP2518FD` (14 / 15), crystals (4 pads / 2 pins), plus `USB-C` (22 pads / 15-pin symbol).

Concrete evidence: `esc-split-layout/03_build_control.py:153` places `U5 = LM5164` in
`Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`; the same part in the drone-arm project is placed in
`HSOP-8-1EP_3.9x4.9mm_EP2.41x3.1mm_ThermalVias` and carries a pad 9 (`EP`). The KiCad symbol
`Regulator_Switching:LM5164DDA` has 9 pins (1 GND, 2 VIN, 3 EN/UVLO, 4 RON, 5 FB, 6 PGOOD, 7 BST, 8 SW, 9 EP).
`Power_Supervisor:TPS3430WDRC` has 11 pins (VDD1, CWD, SET0, CRST, GND, SET1, WDI, ~WDO, NC, VDD2, GND).

### A.2 ADS8588S pin table used (TI SBAS642A, "Pin Configuration and Functions", 64-pin LQFP)
1 AVDD · 2 AGND · 3 OS0 · 4 OS1 · 5 OS2 · 6 PAR/SER/BYTE SEL · 7 STBY · 8 RANGE · 9 CONVSTA · 10 CONVSTB ·
11 RESET · 12 RD/SCLK · 13 CS · 14 BUSY · 15 FRSTDATA · 16 DB0 · 17 DB1 · 18 DB2 · 19 DB3 · 20 DB4 · 21 DB5 ·
22 DB6 · 23 DVDD · 24 DB7/DOUTA · 25 DB8/DOUTB · 26 AGND · 27 DB9 · 28 DB10 · 29 DB11 · 30 DB12 · 31 DB13 ·
32 DB14/HBEN · 33 DB15/BYTE SEL · 34 REFSEL · 35 AGND · 36 REGCAP1 · 37 AVDD · 38 AVDD · 39 REGCAP2 · 40 AGND ·
41 AGND · 42 REFIN/REFOUT · 43 REFGND · 44 REFCAPA · 45 REFCAPB · 46 REFGND · 47 AGND · 48 AVDD · 49 AIN_1P …
64 AIN_8GND (odd/even pairs: `AIN_nP = 47+2n`, `AIN_nGND = 48+2n`). Retrieved from
[the datasheet text](https://www.manua.ls/texas-instruments/ads8588s/manual?p=4); the TI PDF itself could not be
fetched (`unsupported content type application/pdf`), so the pin table was transcribed from that mirror and is
**the one input in this report not taken from a local file** — it is flagged as such in every provenance row
(`SRC AVDD`, `SRC AGND`, …) and it should be re-checked against the TI PDF before the schematic is signed off.

### A.3 TCAN3413 caveat
Pin order used (1 TXD, 2 GND, 3 VCC, 4 RXD, 5 VIO, 6 CANL, 7 CANH, 8 STB) comes from a real `TCAN3413DR` (SOIC-8)
netlist node table in `drone-arm-final/esc_netlist.net`. The control board places the part in **SOT-23-8**, whose
pin order is not proven identical. 6 of its 8 pads are netted; the 2 MCU-side pads are open anyway.

### A.4 Missing passives (BOM defects that invalidate the nets)
`LM5164` needs `FB` divider + `RON` + `BST` cap; the only resistors on the board are 62 × 1 k, all committed to the
31 analogue RC filters. `RP2354B` `VREG_LX`/`VREG_FB` need a 1.1 V inductor + capacitor (none placed).
`ADS8588S` `REFCAPA/B`, `REGCAP1/2` need capacitors (none placed). `CC1/CC2` need 5.1 k pulldowns (none).
`AGND`/`DGND` need one tie (none).

---

## Appendix B — decision register (the 7 DECIDED choices, all reversible)

| id | decision | basis |
|---|---|---|
| D1 | U5 (LM5164 #1) output = `+5V` | SRC: drone-arm `U701 → /5V` (same part, same 33 µH) |
| D2 | U6 (LM5164 #2) output = `+5V_CAN` | SRC: drone-arm `U703 → /Auxiliary power/CAN_5V_RAW` |
| D3 | AP2112 output net = `+3V3_REF_A` | PROVEN pinmap: H1 pins 9/11 are the BEC 3.3 V outputs |
| D4 | all 3.3 V loads on `+3V3_REF_A` | single 3.3 V source (D3) |
| D5 | ADC `AVDD` on `+5V`, TCAN `VCC` on `+5V_CAN` | D1+D2 analogue/digital 5 V split |
| D6 | channel → ADC grouping | pinmap order; the 3 phases of a motor stay on one ADC (simultaneous) |
| D7 | RC topology: channel → `R?A` → node → (`C?` to `AGND`, `R?B`) → ADC input | pinmap note "1 kOhm + 1 nF at the ADC", 2 R + 1 C as placed |

D6 assignment, explicitly: **U14** = `CSA_M1_A/B/C`, `CSA_M2_A/B/C`, `BUS_V`, `BUS_I_A`; **U15** = `CSA_M3_A/B/C`,
`CSA_M4_A/B/C`, `BUS_I_B`, `CSA_M7_A`; **U16** = `CSA_M5_A/B/C`, `CSA_M6_A/B/C`, `CSA_M7_B`, `CSA_M7_C`. NTC
channels: `NTC_M1..M7` → U1 pads 49, 52, 53, 54, 55, 56, 57 (ADC0..ADC6); `ADC7` (pad 58) is spare.

---

## Appendix C — the 53 single-ended nets (nothing to route to)

| group | n | nets |
|---|---:|---|
| interface signals with no MCU pin | 35 | `PWM_M1_A/B/C` … `PWM_M7_A/B/C` (21), `nCS_M1`…`nCS_M7` (7), `SPI_SCLK`/`SPI_MOSI`/`SPI_MISO` (3), `DRV_ENABLE`, `nFAULT_ALL`, `UART_TX`, `UART_RX` |
| passives the BOM lacks | 8 | `LM1_FB`, `LM1_RON`, `LM1_BST`, `LM1_PGOOD`, `LM2_FB`, `LM2_RON`, `LM2_BST`, `LM2_PGOOD` |
| paralleled contacts | 4 | `BAT_P_2`, `BAT_P_3`, `BAT_P_4`, `+3V3_REF_B` |
| no choke / no pulldowns | 4 | `CANH_PHY`, `CANL_PHY` (choke footprint), `CC1`, `CC2` (no 5.1 k) |
| 40 MHz crystal, controller side unmapped | 2 | `XIN_40M`, `XOUT_40M` |
| **total** | **53** | |

## Appendix D — artifacts (all under `evidence/esc-control-netlist/`)

| file | what |
|---|---|
| `REPORT.md` | this file |
| `work/esc_control_board_netted.kicad_pcb` | the board with the derived netlist (559/768 pads netted) |
| `work/netmap.json` | the netlist + provenance + decision register (machine-readable) |
| `work/apply_receipt.json` | every one of the 439 pad writes: ref, pad, before, after |
| `work/ctl_dump.json`, `ctl_after_dump.json` | independent text parse of the board before/after |
| `work/verify.json` | triple diff: added/lost/changed/unexpected, netless reasons |
| `work/drc_ctl_before.json`, `drc_ctl_after.json` | kicad-cli DRC, companions present |
| `work/drc_orig.json`, `orig_pcbnew.json` | original-board DRC + census |
| `work/pintable.json` | pin number → pin name for every part, with its source |
| `work/pcbnew_unconnected.json` | both-tool unconnected cross-check (41 / 384) |
| `scripts/` | `kpcb.py`, `dump_board.py`, `compare.py`, `net_extract.py`, `net_pinmap.py`, `pins2.py`, `design_netmap.py`, `apply_nets.py`, `verify_nets.py` |
| `logs/` | raw kicad-cli output |

## Appendix E — commands (exact, reproducible)

```
python dump_board.py  esc_control_board.kicad_pcb  ctl_dump.json
python compare.py     ctl_dump.json  orig_dump.json  compare.json
python pins2.py       pintable.json
python design_netmap.py
"…KiCad/9.0/bin/python.exe" apply_nets.py  ctl_src_copy.kicad_pcb netmap.json \
                                            esc_control_board_netted.kicad_pcb apply_receipt.json
python dump_board.py  esc_control_board_netted.kicad_pcb  ctl_after_dump.json
python verify_nets.py ctl_dump.json ctl_after_dump.json netmap.json verify.json
kicad-cli pcb drc --format json --output drc_ctl_after.json --severity-all \
        drc_ctl_after/esc_control_board_netted.kicad_pcb      # .kicad_pro + .kicad_dru alongside
"…KiCad/9.0/bin/python.exe" -c "…LoadBoard; BuildConnectivity; GetUnconnectedCount(False)"
```

No script called `PCB_VIA.GetWidth()`. No repo was written. `D:\CodeProjects` and `E:\1vm\TMP` untouched.