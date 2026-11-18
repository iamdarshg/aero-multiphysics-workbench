# drone-arm — firmware pin map vs routed PCB (DA-SW pin parity)

Sub-agent: da-sw-parity. Read-only git. All artefacts under
`evidence/da-sw-parity/`; nothing written into the repositories.

## 0. Provenance

| Item | Value | How obtained |
|---|---|---|
| repo | `E:/engineering-portfolio-audit/repos/drone-arm` @ `07268c3966b8bec2b2587d8b848e6fa50ff80ee2` (branch `work/2026-11-11`) | `git rev-parse HEAD` |
| board analysed | `hardware/main/rev_b/main_rev_b.kicad_pcb`, SHA-256 `9b3bba85c01aac9e8365af999f5231c3951e3428c37544a2b2cadc425f89953c`, 2 252 603 B | `Get-FileHash` |
| tooling | KiCad 9.0.7 — `kicad-cli.exe`, `python.exe` (`pcbnew` SWIG module) under `C:/Program Files/KiCad/9.0/bin/` | `kicad-cli --version` |
| board reference authority | `docs/hardware/pcb-variant-audit-sources.json` names `main_rev_b.kicad_pcb` as the board for every audited variant, with `fabrication_release_authority: null` / `authority_status: NONE_DECLARED` | file read |

Reproduction commands are in `evidence/da-sw-parity/RUNS.md`; every script is in
`E:/engineering-portfolio-audit/scripts/da_sw_*.py`.

## 1. Method (and the rotation trap)

`pcbnew.LoadBoard()` → for every footprint every pad: `GetNumber()`, `GetNetname()`,
`GetNetCode()`, `GetPosition()` (absolute), `GetFPRelativePosition()` (footprint frame),
and the footprint's `GetPosition()` / `GetOrientationDegrees()`.

Net assignment never depends on geometry: it is read from the pad's **net code**, which
KiCad stores per pad and which is already resolved through the footprint placement *and*
rotation. Geometry is used only as a check.

The trap named in the brief is real and measurable. 50 of 165 footprints are rotated
(90°, 180°, −90°). Reconstructing a pad position as `footprint_position + FPRelative`
without applying the footprint rotation is wrong by up to **6.246 mm** (U50, 180°), and
wrong by > 1 mm for 18 of the 49 rotated footprints carrying numbered pads. The correct
reconstruction, `R(θ)·rel + origin`, reproduces `GetPosition()` to **0.000 mm** for all 81
U10 pads (mean 0.000 mm). U10 itself is at (59.0, 50.0) mm, orientation 0.0°, so its own
pads are unrotated — which is exactly why a naive geometry-based tool passes on U10 and
fails on the rotated passives.

Pad → GPIO numbers were established from two independent sources that agree exactly:
1. `hardware/main/rev_b/revb.kicad_sym`, symbol `RP2354B`, 81 pins / 48 GPIO
   (`evidence/da-sw-parity/symbol_pinmap.json`): pin `43` = `GPIO34` … pin `48` = `GPIO39`,
   pin `49` = `GPIO40/ADC0`, pin `58` = `GPIO47/ADC7`;
2. `hardware/main/rev_b/mcu_pinmap.json` (repo-generated from the schematic netlist), plus
   the symbol pin names embedded in the board's own pad net names
   (`unconnected-(U10-GPIO34-Pad43)` …).

Cross-check receipt (`evidence/da-sw-parity/crosscheck.txt`): 48/48 pads agree with the
symbol; 0 disagreements between pad net names and symbol pin names.

## 2. Result: the board as routed

`main_rev_b.kicad_pcb` — 165 footprints, 176 nets, U10 = `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm`,
81 numbered pads (90 pads incl. paste/mechanical).

Full pad-by-pad table: **[`pin_table.md`](pin_table.md)** (source of truth, all 81 pads);
machine form `pin_table.csv`, counts `pin_summary.json`.

| verdict | count | meaning |
|---|---:|---|
| **MATCH** | **0** | firmware claim equals the board function |
| **MISMATCH** | **20** | firmware claims a peripheral on a GPIO that carries a different board net |
| **NOT_ROUTED** | **6** | GPIO34–39: schematic + pin map say PWM_ESC1..6; the PCB has no copper, no connector |
| UNCLAIMED_BY_FIRMWARE | 14 | board net exists (GPIO2,3,9,22,23,24,26,27,28,29,30,31,32,33), firmware names none |
| SPARE_NO_NET_NO_CLAIM | 8 | GPIO40–47: no net, no claim |
| NON_GPIO_PIN | 33 | power / XIN / XOUT / RUN / SWD / USB / QSPI / EP |
| **sum** | **81** | 20+6+14+8 = 48 GPIO + 33 non-GPIO |

Power/analog sanity of the MCU footprint checks out: pads 5/15/24/29/41/50/60/64/68/69/76
= `/3V3`, 10/32/51/65 = `/1V1`, 59 = `/3V3_ADC`, 61 = `/VREG_AVDD`, 63 = `/VREG_LX`,
62/81 = `/GND`. QSPI pads 70–75 are unconnected, which is correct for the **RP2354B**
(in-package flash) rather than an error.

### 2.1 Where the firmware pin definitions actually live

No firmware is buildable from this checkout: `src/` and `include/` are absent
(`git ls-tree HEAD src include` → empty), exactly as `docs/engineering/FIRMWARE_SOURCE_AUDIT.md`
records. The pin definitions that exist are:

| id | source | content |
|---|---|---|
| A | `origin/sdk-recreation:src/board_config.h` lines 5–13 (dumped to `src/board_config.h.sdk-recreation.txt`) | 9 constants: `LED=25, UART0_TX=0, UART0_RX=1, I2C0_SDA=4, I2C0_SCL=5, SPI0_TX=19, SPI0_RX=16, SPI0_SCK=18, SPI0_CS=17` |
| B | `fc82f720^:src/main_board/hardware_defs/pins.h` lines 38–59 (deleted firmware, dumped to `src/predelete_pins.h`) | generic RP2350 defaults: SPI0 16/17/18/19 + CS1 20 + CS2 21; SPI1 10–15; I2C0 5/4; I2C1 7/6 |
| C | `fc82f720^:src/main_board/hardware_defs/pwm_config.h` lines 63–65 (dumped to `src/predelete_pwm_config.h`) | only enabled slice: `PWM_SLICE_4_ENABLED 1`, `GPIO_A 8`, `GPIO_B 25`; 20 kHz |
| D | `origin/sdk-recreation:src/pwm_output.h` | board-agnostic RC-PWM driver, `PWM_OUTPUT_MAX_CHANNELS 8`, GPIO pins supplied by the caller — **no board mapping** |

**No firmware anywhere in this repository's history ever claims GPIO34–39.**
`git log --all -S PWM_ESC -- src include` → empty. `git log --all -S GPIO34 -- src include`
→ 4 commits, all of which initialise GPIO34–39 to `GPIO_FUNC_NULL` / no-pull / no-direction
(e.g. `e4ce005:src/main_board/harware_defs/pins.h`, `61934fc:src/main_board/low_level/adc.c:33`
marks GPIO36–39 unusable for ADC). The pin map that *does* assign PWM_ESC1..6 to pads 43–48
(`mcu_pinmap.json`) is generated from the **schematic netlist**, not from firmware.

Consequence: `tests/test_pin_consistency.py` cannot detect the drift it exists for. It
compares `mcu_pinmap.json` (schematic-derived) against a hand-copied `FIRMWARE_PINS` dict and
claims its source in a comment as *"sdk-recreation branch, src/board_config.h"* (plus the
Rev-B interface spec) — but that branch's actual `board_config.h` (source A) contains none of
those 40 assignments. The test is green against a mirror, not against firmware.

### 2.2 Mismatch classes with physical consequence

All 20 are listed in `pin_table.md`; the classes that matter:

* `GPIO25` board `/LNA_EN` (pad 26) vs firmware A `BOARD_LED_PIN = 25` and firmware C
  `PWM_SLICE_4_GPIO_B = 25` — booting generic firmware **drives the RF LNA enable** as a
  status LED. An RF front-end keyed by a blinking GPIO is a bench hazard, not a cosmetic bug.
* `GPIO8` board `/LSM_INT2` vs firmware C `PWM_SLICE_4_GPIO_A = 8` — 20 kHz PWM onto the IMU
  interrupt line.
* `GPIO0/1` board `/SENS_SCLK`, `/SENS_MOSI` vs firmware A UART0 TX/RX — UART traffic onto
  the sensor SPI bus.
* `GPIO16/17/18/19` board `/RF_SCLK`, `/RF_MOSI`, `/RF_MISO`, `/RF_nCS` vs firmware A/B
  SPI0 MISO/CS/SCK/MOSI **in a different phase order** (firmware MISO=16 while board SCLK=16):
  even "same peripheral, same pins" is scrambled, so a build would mis-clock the CC1121.
* `GPIO4/5` board `/LSM_nCS`, `/ICM_INT1` vs I2C0 SDA/SCL (both A and B).
* `GPIO10–15` board `/BARO_SDA`, `/BARO_DRDY`, `/GNSS_TX`, `/GNSS_RX`, `/GNSS_PPS`,
  `/GNSS_RESET_N` vs SPI1 SCK/MOSI/MISO/CS0/CS1/CS2.

Additionally `predelete_pins.c` (lines 9–54) sets **all 48 GPIOs to `GPIO_DIR_OUT` with
pull-ups** — if that image ever ran on this board it would drive every peripheral line,
including `/GNSS_RESET_N` and `/RF_nCS`, as outputs.

### 2.3 Peripheral ICs — every pad and its net

Machine form: `peripheral_pins.json`. Counts are pads with a numeric designator.

| ref | part | pads | netted | open | open pads (symbol names) |
|---|---|---:|---:|---:|---|
| U1 | USBLC6-2SC6 | 6 | 6 | 0 | — |
| U2 | TLV62569DBVR | 5 | 5 | 0 | — |
| U3 | TLV75528PDBVR | 5 | 4 | 1 | 4 NC |
| U4 | TLV75533PDBVR | 5 | 4 | 1 | 4 NC |
| U10 | RP2354B | 81 | 61 | 20 | 43–48 GPIO34–39, 49/52–58 GPIO40–47, 70–75 QSPI |
| U20 | ICM-42688-P | 14 | 10 | 4 | 2/3/10/11 RESV |
| U21 | LSM6DSO32TR | 14 | 12 | 2 | 10/11 NC |
| U22 | LPS22DFTR | 10 | 10 | 0 | — |
| U30 | LG77LICMD (GNSS) | 43 | 17 | 26 | RESERVED/RTC/3D_FIX/ANT_DET/WAKEUP/JAM_IND/**I2C_SCL 29**/**I2C_SDA 30**/ANT_SHORT/ANT_OFF |
| U40 | CC1121RHBR | 43 | 40 | 3 | 16 NC, 30/31 XOSC_Q1/Q2 (external clock used instead) |
| U41 | CC1190RGVR | 27 | 27 | 0 | — |
| U50 | TCAN3413DR | 8 | 8 | 0 | — |
| U51 | MCP2518FD-H/QBB | 15 | 12 | 3 | 3 CLKO/SOF, 8 INT1/GPIO1, 9 INT0/GPIO0/XSTBY |

Net-by-net: sensors share `/SENS_SCLK`, `/SENS_MOSI`, `/SENS_MISO` with separate `/ICM_nCS`,
`/LSM_nCS` and four interrupt lines; the barometer is on `/BARO_SCL`/`/BARO_SDA`/`/BARO_DRDY`
(U22 only, no second I2C device on that bus); GNSS is `/GNSS_TX`→`GNSS_UART_RX_2V8`,
`/GNSS_RX`←`GNSS_UART_TX_2V8`, plus `/GNSS_PPS`, `/GNSS_RESET_N`→`GNSS_RESET_OD`,
`/GNSS_PWR_EN` gating U3/U4; RF is `/RF_SCLK`,`/RF_MOSI`,`/RF_MISO`,`/RF_nCS` to U40 with
`/PA_EN`,`/LNA_EN`,`/HGM`,`/RF_RESET_N`,`/RF_GPIO0/2/3`; CAN is `/CAN_SCK`,`/CAN_MOSI`,
`/CAN_MISO`,`/CAN_nCS`,`/CAN_INT` to U51 with U51↔U50 `/CAN interface/U51_TXCAN`,`U51_RXCAN`.

Observation relevant to firmware (not a defect claim): the GNSS module's own I2C port
(U30 pads 29/30) is unconnected, so `BARO_*` is the only I2C bus and the `/BARO_*` pins on
GPIO9/10/11 are a genuine single-device bus — the firmware's I2C0-on-GPIO4/5 assumption
(§2.2) would not reach it even if the LSM_nCS/ICM_INT1 conflict were ignored.

## 3. PCB change required vs firmware-only

The decisive question is not "does firmware disagree" (it disagrees everywhere) but "can a
correct firmware be written against this copper". For GPIO0–33 the answer is **yes**: those
34 nets are complete, unique, and match the schematic (see §4 — the parity run reports net
conflicts on U10 for pads 43–48 only). Every one of the 20 mismatches is therefore a
firmware defect.

### PCB_CHANGE_REQUIRED (true rip-up risk — no firmware can fix these)

1. **GPIO34–39 → PWM_ESC1..6 are absent from the board.** Pads 43–48 carry
   `unconnected-(U10-GPIO34-Pad43)` … `-(U10-GPIO39-Pad48)`; there is no net, no trace, no via,
   and no `J60–J65` footprint. The symbols *do* exist in the schematic
   (`mcu.kicad_sch` labels `PWM_ESC1`…`PWM_ESC6` at lines 7039–7089, `J60`/`J61` symbols at
   `mcu.kicad_sch`), so this is schematic-ahead-of-board drift. Firmware cannot create copper:
   **six nets + six 1×03 headers must be added, or the requirement must be dropped.**
2. **There is no actuator connector anywhere on the board.** Connector inventory:
   `J1` USB-C, `J10` SWD (3-pin), `J2` `ESC_CAN_POWER` (CAN_5V/CAN_GND/CANH/CANL),
   `J30` GNSS U.FL, `J40` 915 MHz U.FL. Zero servo/ESC PWM headers, so even the 6 intended
   PWM channels have no landing point. Fixing (1) without headers leaves the nets dangling.
3. **The 7th actuator has no path** (§5). Two spare-pin routes exist in principle
   (GPIO40–47 are unconnected), but routing one to a header is still a PCB change; firmware
   adding a 7th channel cannot reach a pin that is not brought out.
4. Not mine to own, but non-cosmetic and visible in the same parity run: **FL50 (`ACT45B-110-2P-TL003`
   common-mode choke) net conflict**. Board: pad1 `/CAN interface/U50_CANH`, pad2 `/CANH`,
   pad3 `/CAN interface/U50_CANL`, pad4 `/CANL` — i.e. TCAN3413 CANH (U50 pad 7) enters winding
   1 and leaves on pad 2 to the bus, CANL (U50 pad 6) enters winding 2 on pad 3 and leaves on
   pad 4. That is the correct current-compensated arrangement. The schematic disagrees on pads
   2/3/4 (`pad2→U50_CANL`, `pad3→/CANL`, `pad4→/CANH`; pad 1 has no conflict, so both sides
   agree it is `U50_CANH`). Read literally, the schematic puts **both transceiver lines on one
   winding** (1→2 = CANH→CANL) and both bus lines on the other (4→3 = CANH→CANL) — a
   differential-pair short through the choke, produced by a wrong pin pairing in the schematic
   symbol instance. So here the **board looks right and the schematic looks wrong**, the
   opposite of the J60–J65 case. I do not have the choke's datasheet pinout open, so the
   interpretation is conditional on the ACT45B pin numbering; it must be dispositioned by the
   CAN net-conflict owner, not by a board change by default.

### FIRMWARE_ONLY (fix by writing the correct Rev-B board support)

* All 20 GPIO→function conflicts in §2.2 / `pin_table.md`. The copper is already correct and
  complete; a Rev-B `board_config.h` derived from the board netlist resolves every one.
* The "generic firmware drives `/LNA_EN` as an LED" hazard: pick `GPIO32` (board
  `/STATUS_LED`, pad 40) and the hazard disappears with no board change.
* The 48-GPIO all-outputs initialisation in `predelete_pins.c`: wrong in software only.
* `tests/test_pin_consistency.py`: must read a real firmware header (or be deleted); its
  current form green-lights the exact drift it claims to catch.

### Why the split lands there

The board's U10 netting covers the architecture's peripheral set completely (SPI0 to the
CC1121, SPI1 to the CAN controller, I2C0 to the barometer, sensor SPI, GNSS, CAN, status
LED). What firmware asks for that the board does **not** provide is narrow and identifiable:
(a) six/seven PWM actuator channels — no copper, no connector (§3.1, §3.2, §5);
(b) a UART — the board exposes USB and SWD only, so firmware must use USB-CDC, not UART0 on
GPIO0/1 (firmware-only decision, no board change needed);
(c) a second I2C bus (I2C1) — no I2C1 device exists on this board (the GNSS module's I2C
port is unconnected), so that too is firmware-only.
Rework at fab is therefore confined to the PWM / actuator interface, not the peripheral bus
mapping.

## 4. Schematic-parity evidence (independently reproduced)

`kicad-cli pcb drc --schematic-parity` on the tracked board
(`drc/main_rev_b_parity.json`):

```
Found 0 violations
Found 0 unconnected items
Found 191 schematic parity issues
```

| type | count | content |
|---|---:|---|
| `missing_footprint` | 6 | `J60`…`J65` (`ESC_PWM_1`…`_6`) — symbols in `mcu.kicad_sch`, absent from the board |
| `extra_footprint` | 4 | mounting holes `H1`–`H4` (no schematic symbols) |
| `footprint_symbol_mismatch` | 161 | **all 161 are library-prefix-only** (`C_0805_2012Metric` vs `Capacitor_SMD:C_0805_2012Metric`); 0 pin-level mismatches — verified programmatically |
| `net_conflict` | 20 | 6 real (U10 pads 43–48 vs `PWM_ESC1..6`), 11 KiCad `/`-escape artefacts (U10 pads 49/52–58, U51 pads 3/8/9), 3 FL50 choke pin-pairing conflicts (§3.4) |

All 191 carry `severity: warning`. The 6 U10 net conflicts are quoted verbatim, e.g.
`"Pad net (unconnected-(U10-GPIO34-Pad43)) doesn't match net given by schematic (/RP2354B MCU/PWM_ESC1)."`
Note the flip side, useful evidence: pads 1–42 and 59–81 produce **no** net conflict, i.e. the
board's 34 GPIO nets (GPIO0–33, 34 distinct net codes, verified unique and all distinct from
the power nets) are exactly what the schematic specifies.

Root-sheet ERC is reported (host facts) as a single warning `lib_symbol_mismatch` on
`L_Coupled`; not re-run here, not my item.

## 5. Actuator conflict: 7 effectors vs 6 PWM — NOT RESOLVED

* Need side: `aircraft_interfaces/system_interface.json` → `actuators.modeled_effector_count: 7`
  (composition 2 elevons + 4 EDF exit-vector vanes + 1 rudder, pinned to drone-mech
  `5246c90`), and `interfaces[actuators.mapping]` is `BLOCKED` with reason *"seven modeled
  effectors exceed six PWM outputs; a unique realizable path and feedback assignment is
  unresolved"*.
* Supply side: `actuators.available_pwm_output_count: 6`, `actuators.pwm_capacity.capacity: 6`
  — and even those six are **schematic-only**: on the routed board the count of nets whose
  name contains `PWM` is **0** (checked across all 176 net names), the count of U10 pads on a
  PWM net is **0**, and the count of PWM/actuator connectors is **0**.
* Propulsion is not the constraint: the six EDF motors are commanded over **CAN-FD**
  (`J2`, MCP2518FD `U51` + TCAN3413 `U50`), so PWM_ESC1..6 are the *servo* channels.
* Firmware side: the only PWM implementation (`src/pwm_output.h`, `PWM_OUTPUT_MAX_CHANNELS 8`)
  could drive 7 channels from a software standpoint, but it carries no board mapping, and no
  firmware revision in this repository references any of these pins.

**Verdict: unresolved, and unresolvable at firmware level.** The board exposes 6 PWM nets
(0 routed, 0 connectorised) for 7 independent effectors. Fab-blocking rework: add a 7th PWM
(GPIO40–47 are free) plus a 7-header actuator block, or re-architect the actuator bus (e.g.
CAN servo node) — a mechanical/electrical decision, out of this item's scope, currently
recorded as BLOCKED in the system interface contract.

### 5.1 Variant caveat that matters for the fab decision

`hardware/main/rev_b/` contains 8 tracked `*.kicad_pcb`. Two of them — `main_rev_b_final.kicad_pcb`
and `main_rev_b_final.before_diff_pair_ripup.kicad_pcb` (168 footprints) — **do** contain
`J60`–`J65` (`PinHeader_1x03_P2.54mm_Vertical`, front side, 90° rotation, 9 mm pitch, at
x = 78/87/96/105/114/123 mm, y = 72.5 mm) with the six `/RP2354B MCU/PWM_ESC1..6` nets
terminating `U10.43..48 → J60..65.3`. The other six variants (including
`main_rev_b_routed_clean.kicad_pcb`, which was extracted too) contain **zero** nets with
`PWM` in the name and pads 43–48 still `unconnected-…`. The `final` variants also **drop
mounting holes H2/H3/H4** (only H1 remains). Neither `final` file is named by
`pcb-variant-audit-sources.json`, and J60–J65 appear in **neither BOM**
(`docs/hardware/REV_B_BOM.csv`, `hardware/rev_b_grouped_bom.csv` — 0 matches for `J6[0-5]`).
So the payload exists in a side-car file that was never promoted to the reference board or to
the BOM. Whoever picks the fab file must decide between "board without PWM" and "board with
PWM but 3 mounting holes missing", and must regenerate the BOM either way.

## 6. UNVERIFIED / needs the physical board

1. Whether `main_rev_b_final.kicad_pcb`'s +6/−3 footprint set is physically acceptable
   (mounting-hole loss, 1×03 header keep-out and mating height) — needs mech/CAD, not this audit.
2. Which file is the fabrication candidate: no release authority is declared anywhere
   (`authority_status: NONE_DECLARED`), so "the board" is the maintained reference
   `main_rev_b.kicad_pcb` by convention only.
3. Real pad-level continuity on a built board (the netlist is intent, not copper): would need
   first-article beep-out of U10 pads 43–48 and of J60–J65 if those are added.
4. Whether the `final` variant's `J60`–`J65` placement (front side, 90°, 9 mm pitch,
   y = 72.5 mm, directly along the board's south edge at x 78–123 mm) clears adjacent
   components and matches its silkscreen pin-1 marking — placement and rotation are known
   from the file, the mechanical fit is not.
5. ERC on the root sheet (1 warning, `L_Coupled`) and the 20 parity warnings were taken as
   host facts where noted; only the parity run was reproduced locally.
6. No firmware image was built or executed (no `src/`, no ARM toolchain) — no claim is made
   about boot behaviour, PWM timing, or flight safety.

## 7. Artefacts

| file | content |
|---|---|
| `pin_table.md` / `pin_table.csv` | 81-row pad table: pad, GPIO, board net, schematic intent, firmware claims, verdict |
| `pin_summary.json` | verdict counts and firmware-claim inventory |
| `crosscheck.txt` | pad→GPIO agreement vs RP2354B symbol (48/48, 0 disagreement) |
| `symbol_pinmap.json` | RP2354B symbol pin 1–81 → name, parsed from `revb.kicad_sym` |
| `pcb_raw/*.json` | raw pcbnew dump, all 7 analysed variants (every footprint, every pad, abs + relative position, orientation) |
| `pcb_variant_summary.json` | per-variant PWM/J6x coverage |
| `drc/main_rev_b_parity.json` | kicad-cli 9.0.7 schematic-parity report (191 issues) |
| `src/*` | the three firmware pin sources, dumped by `git show` (read-only) |
| `RUNS.md` | exact commands |