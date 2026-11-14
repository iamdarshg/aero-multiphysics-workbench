# Code-SDR V2 - RTL / firmware / PCB pin-map parity

Audit of `repos/Code-SDR` @ branch `work/2026-11-11`, commit `6fbc004af4bec9c5ec78e57709c7127a280489f6`.
Read-only: no repo file was modified. All artifacts are in this directory.

## 0. Verdict in one paragraph

A pin constraint file **does exist** (`verilog/v2_top.lpf`, 32 `LOCATE` entries), so the bitstream is targetable in principle. But the file the build script actually compiles in is the hand-written copy, and that copy puts the ADC sample clock on ball **D7**, while the routed board puts `ADC_CLK` on ball **D9**. Ball D7 exists in the `LIF-MD6000-6JMG80I` footprint as a **pad with no net**. D7 is a legal placement target, so nothing will fail at P&R - the clock input will simply land on copper that goes nowhere and the first article will produce no samples. The correct file (`v2_top_generated.lpf`, generated from copper) already exists and already says D9 - it is simply never referenced by `build_diamond.tcl`.

Separately, all six RP2040 pin constants in the firmware are wrong: they are physical QFN-56 pin numbers being passed to an API that takes GPIO numbers. Two of them are actively dangerous (the `RESET` constant lands on the `FPGA_CDONE` net and the `CDONE` constant is GPIO41, which does not exist on RP2040).

## 1. Method and provenance

| Step | Command | Output |
| --- | --- | --- |
| Pad -> net from routed copper | `"C:/Program Files/KiCad/9.0/bin/python.exe" extract_pads.py` | `pads_target.csv`, `net_to_pads.json`, `board_meta.json` |
| Symbol pin number -> pin name | `parse_symbols.py` | `symbol_pins.json`, `symbol_pins.txt` |
| RP2040 GPIO alternate functions | `gpio_af.py` | `gpio_af.json`, `gpio_af.txt` |
| Parity join + counts | `parity.py` | `pin_table.csv`, `rp2040_nets.csv`, `spi_role_audit.csv`, `summary.json` |

Board read with `pcbnew.LoadBoard` on `hardware/v2/Code-SDR-V2.kicad_pcb`: **373 footprints, 12,253 track objects, 4 copper layers, 261 nets** - matches the brief, so this is the routed board, not the snapshot in `docs/release-notes/`.

The RP2040 GPIO function table is not in the repo. It is taken from the local pico-sdk copy shipped with arduino-pico 6.1.0:

`C:/Users/Darsh Gupta/AppData/Local/Arduino15/packages/rp2040/hardware/rp2040/6.1.0/pico-sdk/src/rp2040/hardware_regs/include/hardware/regs/io_bank0.h`

which is generated from the RP2040 datasheet (e.g. `IO_BANK0_GPIO0_CTRL_FUNCSEL_VALUE_SPI0_RX` at that file's line 175). This is the authority for the 'which GPIO can be SPI SCK' claims below.

## 2. Constraint files: what exists and what actually gets built

| File | LOCATE entries | Clock ball | Referenced by build? |
| --- | --- | --- | --- |
| `verilog/v2_top.lpf` (hand-written) | 32 | **D7** | **YES** - `build_diamond.tcl` L99 `prj_src add verilog/v2_top.lpf` |
| `verilog/v2_top_generated.lpf` (from copper) | 32 | **D9** | no - referenced only by `README.md` L134 and `tools/gen_lpf.py` |

The two files are identical in all 32 `LOCATE` lines **except one**:

```
clk_100m_in    hand=v2_top.lpf -> D7        generated -> D9
```

`build_diamond.tcl` L99 adds only the hand-written file, so the D9 correction never reaches the bitstream. `v2_top_generated.lpf` is dead weight in the tree.

Board truth for the clock net (`net_to_pads.json`):

```
ADC_CLK  =>  R31.2, U20.D9, U21.2      # U42.3 (CDCLVC1104 fanout) -> R31 -> FPGA D9 + ADC pin 2
U20.D7   =>  no net at all (pad present, unconnected)
```

`HARDWARE.md` L44-45 already documents this exact correction in prose ("the sample clock lands on U20.D9, not D7"), which means the doc was fixed and the LPF that the build uses was not.

## 3. FPGA pin table (32 `v2_top` ports vs routed balls)

`MATCH` = the ball in the LPF equals the ball carrying the intended net in copper.

| RTL port | board ball | board net | hand LPF | generated LPF | status |
| --- | --- | --- | --- | --- | --- |
| `rst_n` | H2 | `FPGA_RESET_N` | H2 | H2 | MATCH |
| `clk_100m_in` | D9 | `ADC_CLK` | D7 | D9 | **MISMATCH** |
| `adc_data[0]` | D10 | `ADC_D0` | D10 | D10 | MATCH |
| `adc_data[1]` | E9 | `ADC_D1` | E9 | E9 | MATCH |
| `adc_data[2]` | E10 | `ADC_D2` | E10 | E10 | MATCH |
| `adc_data[3]` | F9 | `ADC_D3` | F9 | F9 | MATCH |
| `adc_data[4]` | F10 | `ADC_D4` | F10 | F10 | MATCH |
| `adc_data[5]` | G9 | `ADC_D5` | G9 | G9 | MATCH |
| `adc_data[6]` | G10 | `ADC_D6` | G10 | G10 | MATCH |
| `adc_data[7]` | H9 | `ADC_D7` | H9 | H9 | MATCH |
| `adc_data[8]` | H10 | `ADC_D8` | H10 | H10 | MATCH |
| `adc_data[9]` | J10 | `ADC_D9` | J10 | J10 | MATCH |
| `adc_ovr` | K9 | `ADC_OR` | K9 | K9 | MATCH |
| `spi_clk` | J1 | `FPGA_SPI_SCK` | J1 | J1 | MATCH |
| `spi_mosi` | G1 | `FPGA_SPI_MOSI` | G1 | G1 | MATCH |
| `spi_cs_n` | H1 | `FPGA_SPI_CS_N` | H1 | H1 | MATCH |
| `spi_miso` | K1 | `FPGA_SPI_MISO` | K1 | K1 | MATCH |
| `rgmii_txd[0]` | E1 | `RGMII_TXD0_FPGA` | E1 | E1 | MATCH |
| `rgmii_txd[1]` | E2 | `RGMII_TXD1_FPGA` | E2 | E2 | MATCH |
| `rgmii_txd[2]` | F1 | `RGMII_TXD2_FPGA` | F1 | F1 | MATCH |
| `rgmii_txd[3]` | F2 | `RGMII_TXD3_FPGA` | F2 | F2 | MATCH |
| `rgmii_tx_ctl` | J3 | `RGMII_TX_EN_FPGA` | J3 | J3 | MATCH |
| `rgmii_txc` | J7 | `RGMII_TXC_FPGA` | J7 | J7 | MATCH |
| `rgmii_rxd[0]` | K8 | `RGMII_RXD0_FPGA` | K8 | K8 | MATCH |
| `rgmii_rxd[1]` | J5 | `RGMII_RXD1_FPGA` | J5 | J5 | MATCH |
| `rgmii_rxd[2]` | K10 | `RGMII_RXD2_FPGA` | K10 | K10 | MATCH |
| `rgmii_rxd[3]` | K4 | `RGMII_RXD3_FPGA` | K4 | K4 | MATCH |
| `rgmii_rx_ctl` | K5 | `RGMII_RX_DV_FPGA` | K5 | K5 | MATCH |
| `rgmii_rxc` | K6 | `RGMII_RXC_FPGA` | K6 | K6 | MATCH |
| `mdc` | J6 | `MDC` | J6 | J6 | MATCH |
| `mdio` | K7 | `MDIO` | K7 | K7 | MATCH |
| `phy_int_n` | K2 | `PHY_INT_N` | K2 | K2 | MATCH |

Counts: **31 MATCH / 1 MISMATCH / 0 NO-CONSTRAINT** (of 32 ports).

The generated file would score 32/32 against copper; the file that is built scores 31/32.

## 4. RP2040 firmware pin constants

`firmware/rp2040_dashboard/rp2040_dashboard.ino` L91-96 and `firmware/rp2040_dashboard/fpga_config.h` L25-30 define six pins. `fpga_config.h` L23-24 already admits the problem: *"These are physical PCB pins from the net list, not confirmed GPIOs"*. Arduino-Pico's `pinMode`/`SPI.setSCK` take **GPIO numbers**, so every one of these is off.

| firmware define | value | intended pad (comment) | pad's real GPIO | GPIO the value selects | net actually hit | should be | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PIN_FPGA_SCK` | 2 | U10.2 | GPIO0 | GPIO2 (pad 4) | `FPGA_SPI_MISO` | 0 | **MISMATCH** |
| `PIN_FPGA_MOSI` | 3 | U10.3 | GPIO1 | GPIO3 (pad 5) | `FPGA_SPI_CS_N` | 1 | **MISMATCH** |
| `PIN_FPGA_MISO` | 4 | U10.4 | GPIO2 | GPIO4 (pad 6) | `SYNTH_SCK` | 2 | **MISMATCH** |
| `PIN_FPGA_CS_N` | 5 | U10.5 | GPIO3 | GPIO5 (pad 7) | `SYNTH_SDI` | 3 | **MISMATCH** |
| `PIN_FPGA_RESET` / `PIN_FPGA_RESET_N` | 29 | U10.29 | GPIO18 | GPIO29 (pad 41) | `FPGA_CDONE` | 18 | **MISMATCH** |
| `PIN_FPGA_CDONE` | 41 | U10.41 | GPIO29 | GPIO41 - does not exist | *(nothing)* | 29 | **MISMATCH** |

Counts: **0 MATCH / 6 MISMATCH**. RP2040 exposes GPIO0-GPIO29 only, so `pinMode(41, ...)` is out of range.

Consequences if flashed as-is: the SPI master emits clock on the MISO line, the FPGA sees no configuration clock, `fpga_program_from_file()` reports CDONE timeout, and the "reset" helper actually pulses the FPGA's CDONE output pin, which is driven by the FPGA - a driver conflict on pad 41/GPIO29.

## 5. RP2040-owned nets with no firmware at all

30 RP2040 GPIO pads carry nets on this board. 6 are the FPGA link (above, wrong GPIO numbers). The other **24 have no driver in any firmware, Verilog, software or tools file**. All 30 are listed below so the two groups can be told apart at a glance:

| pad | GPIO | net | driver |
| --- | --- | --- | --- |
| U10.2 | GPIO0 | `FPGA_SPI_SCK_MCU` | firmware (wrong GPIO#) |
| U10.3 | GPIO1 | `FPGA_SPI_MOSI` | firmware (wrong GPIO#) |
| U10.4 | GPIO2 | `FPGA_SPI_MISO` | firmware (wrong GPIO#) |
| U10.5 | GPIO3 | `FPGA_SPI_CS_N` | firmware (wrong GPIO#) |
| U10.6 | GPIO4 | `SYNTH_SCK` | none |
| U10.7 | GPIO5 | `SYNTH_SDI` | none |
| U10.8 | GPIO6 | `LMX_CSB` | none |
| U10.9 | GPIO7 | `LMX_CE` | none |
| U10.11 | GPIO8 | `ADF_LE` | none |
| U10.12 | GPIO9 | `ADF_CLK` | none |
| U10.13 | GPIO10 | `ADF_DATA` | none |
| U10.14 | GPIO11 | `LNA_EN_LOW` | none |
| U10.15 | GPIO12 | `LNA_EN_H1` | none |
| U10.16 | GPIO13 | `LNA_EN_H2` | none |
| U10.17 | GPIO14 | `LNA_EN_H3` | none |
| U10.18 | GPIO15 | `DSA_LE` | none |
| U10.27 | GPIO16 | `DSA_DATA` | none |
| U10.28 | GPIO17 | `DSA_CLK` | none |
| U10.29 | GPIO18 | `FPGA_RESET_N` | firmware (wrong GPIO#) |
| U10.30 | GPIO19 | `IF_PATH_SEL` | none |
| U10.31 | GPIO20 | `HSW_V1` | none |
| U10.32 | GPIO21 | `HSW_V2` | none |
| U10.34 | GPIO22 | `ADC_PDWN` | none |
| U10.35 | GPIO23 | `LNA_EN_H4` | none |
| U10.36 | GPIO24 | `MIXER_EN_HIGH` | none |
| U10.37 | GPIO25 | `PHY_RESET_N` | none |
| U10.38 | GPIO26 | `LMX_LOCK` | none |
| U10.39 | GPIO27 | `ADF_LOCK` | none |
| U10.40 | GPIO28 | `ADC_OR` | none |
| U10.41 | GPIO29 | `FPGA_CDONE` | firmware (wrong GPIO#) |

`git grep -E 'SYNTH_SCK|SYNTH_SDI|LMX_CSB|LMX_CE|lmx|LMX2592' -- firmware verilog software tools tests` returns **no hits** (exit 1). The LMX2592 is entirely unprogrammed: CE is never asserted, no register writes exist, so the LO never locks and the receive path is dead on first power-up.

## 6. Bus-order checks

### 6.1 AD9215 10-bit data bus - CORRECT

| RTL bit | net | AD9215 pin | pin name | FPGA ball |
| --- | --- | --- | --- | --- |
| `adc_data[0]` | `ADC_D0` | 9 | D0 | D10 |
| `adc_data[1]` | `ADC_D1` | 10 | D1 | E9 |
| `adc_data[2]` | `ADC_D2` | 11 | D2 | E10 |
| `adc_data[3]` | `ADC_D3` | 12 | D3 | F9 |
| `adc_data[4]` | `ADC_D4` | 13 | D4 | F10 |
| `adc_data[5]` | `ADC_D5` | 14 | D5 | G9 |
| `adc_data[6]` | `ADC_D6` | 17 | D6 | G10 |
| `adc_data[7]` | `ADC_D7` | 18 | D7 | H9 |
| `adc_data[8]` | `ADC_D8` | 19 | D8 | H10 |
| `adc_data[9]` | `ADC_D9` | 20 | D9 | J10 |

The bus is straight: `adc_data[n]` -> `ADC_Dn` -> AD9215 pin `Dn` (symbol pin names from `CodeSDR.kicad_sym`, pin 9 = `D0` ... pin 20 = `D9`), and ball order D10,E9,E10,F9,F10,G9,G10,H9,H10,J10 ascends cleanly. No swap, no mirror.

RTL width check: `v2_top.v` L40 declares `input wire [9:0] adc_data`; `v2_raw_path.v` L112 does `sample = adc_data[9 -: SAMPLE_BITS]`, and `build_diamond.tcl` L18 sets `SAMPLE_BITS 8`, so bits [9:2] are kept - the top 8 bits, MSB-aligned, LSBs dropped. That is the correct truncation for a 10-bit converter. Nothing to change.

The ADC's DNC pins (1,3,5,6,7,8) are unconnected on the board, which is **correct** for `DNC` pins - not a defect.

### 6.2 LMX2592 SPI - no software exists, and the wiring cannot use a hardware SPI

| net | RP2040 pad | GPIO | role needed | SPI role available on that GPIO |
| --- | --- | --- | --- | --- |
| `SYNTH_SCK` | U10.6 | GPIO4 | SCK | SPI0_RX |
| `SYNTH_SDI` | U10.7 | GPIO5 | TX | SPI0_SS_N |
| `LMX_CSB` | U10.8 | GPIO6 | CS | SPI0_SCLK |
| `LMX_CE` | U10.9 | GPIO7 | GPIO | SPI0_TX |

Board wiring is `SCK=GPIO4, SDI=GPIO5, CSB=GPIO6, CE=GPIO7`. GPIO4-7 offer only `SPI0_RX / SPI0_SS_N / SPI0_SCLK / SPI0_TX`, so the three-wire port is rotated one position against the peripheral: the board's SCK is on the RX pin, SDI on the CSn pin, CSB on the SCK pin. An RP2040 hardware SPI cannot drive this pin set in these roles.

## 7. The same rotation hits the FPGA configuration bus

| bus | GPIO | net | role needed | SPI role available | hw SPI usable | PIO available |
| --- | --- | --- | --- | --- | --- | --- |
| FPGA sysCONFIG | GPIO0 | `FPGA_SPI_SCK_MCU` | SCK | SPI0_RX | **no** | yes |
| FPGA sysCONFIG | GPIO1 | `FPGA_SPI_MOSI` | TX | SPI0_SS_N | **no** | yes |
| FPGA sysCONFIG | GPIO2 | `FPGA_SPI_MISO` | RX | SPI0_SCLK | **no** | yes |
| FPGA sysCONFIG | GPIO3 | `FPGA_SPI_CS_N` | CS | SPI0_TX | **no** | yes |
| LMX2592 | GPIO4 | `SYNTH_SCK` | SCK | SPI0_RX | **no** | yes |
| LMX2592 | GPIO5 | `SYNTH_SDI` | TX | SPI0_SS_N | **no** | yes |
| LMX2592 | GPIO6 | `LMX_CSB` | CS | SPI0_SCLK | **no** | yes |
| LMX2592 | GPIO7 | `LMX_CE` | GPIO | SPI0_TX | yes | yes |
| ADF4360 | GPIO9 | `ADF_LE` | CS1 | SPI1_SS_N | yes | yes |
| ADF4360 | GPIO10 | `ADF_CLK` | SCK1 | SPI1_SCLK | yes | yes |
| ADF4360 | GPIO11 | `ADF_DATA` | TX1 | SPI1_TX | yes | yes |

`FPGA_SPI_*` sits on GPIO0-3 in the order **SCK, MOSI, MISO, CS**, but SPI0 on GPIO0-3 is natively **RX, CSn, SCK, TX**. Every signal is one position off. The third bus, the ADF4360 on GPIO9/10/11, is wired **correctly** for SPI1 (`SS_N`, `SCLK`, `TX`) - which is what makes the other two look like a systematic mistake rather than a stylistic choice.

Every GPIO exposes `PIO0_x`/`PIO1_x` (funcsel 6/7 in `io_bank0.h`), so a PIO-based SPI can drive the board as wired. That is why this is a firmware work item, not a mandatory rip-up.

## 8. Classification

### PCB_CHANGE_REQUIRED

**None proven.** Every pin-level defect found is fixable outside copper:

- the clock ball error is a *constraint file* bug - the board's D9 is right, the LPF is stale;
- the six firmware constants are a *firmware* bug;
- the rotated SPI pin order is workable with PIO on any GPIO.

The one item that could still force a **rip-up** is not decidable from this repo: whether ball **D9** on the `LIF-MD6000-6JMG80I` is a dedicated clock-capable (PCLK/GCLK) input. `v2_clock_pll.v` L44-61 instantiates `EHXPLLL` with `CLKI` driven straight from `clk_100m_in`, so the ball must reach a PLL clock input. If D9 is an ordinary I/O ball, the ADC sample clock is unroutable to the PLL and the board requires a re-spin of the clock net to a clock ball (D7 is unconnected and may be the clock ball the original map intended - which would explain where the stale D7 came from). **This is the single highest-risk open question in this audit.**

### FIRMWARE_ONLY

1. Fix the six GPIO constants: `2,3,4,5,29,41` -> `0,1,2,3,18,29`. One-line change, both `.ino` L91-96 and `fpga_config.h` L25-30.
2. Replace the `SPI` object use (`SPI.setSCK/setTX/setRX`, `.ino` L186-189, `fpga_config.cpp` L42-44) with a PIO SPI, because hardware SPI0 cannot serve GPIO0-3 in the required roles.
3. Write the missing LMX2592 driver (3-wire, CE + SCK + SDI + CSB on GPIO4/5/6/7, lock on GPIO26) - again as PIO, or re-map to a hardware SPI group.
4. Add drivers for the other 20 undriven RP2040 nets (LNA_EN x5, DSA x3, HSW x2, ADF4360 x3, `IF_PATH_SEL`, `ADC_PDWN`, `MIXER_EN_HIGH`, `PHY_RESET_N`, `LMX_LOCK`, `ADF_LOCK`, `ADC_OR`).

### Build-system fix (also not copper)

Delete `verilog/v2_top.lpf`, or point `build_diamond.tcl` L99 at `verilog/v2_top_generated.lpf` and regenerate it from copper after every PCB change (`tools/gen_lpf.py` already does this). Two divergent copies of a pin map is how the D7/D9 error survived.

## 9. UNVERIFIED - needs the physical board or the vendor pinout

| Claim | Why unverified | What is needed |
| --- | --- | --- |
| D9 is clock-capable on LIF-MD6000-6JMG80I | no Lattice pinout file in repo; web search provider unavailable this session | Lattice CrossLink pinout guide / Diamond `.ldf` device file, check D9 and D7 against PCLK/GCLK columns |
| `IO_TYPE=LVCMOS33` valid for every pin | LPF's own TODO L66-67 says bank VCCO must be confirmed; `FPGA_VCCIO0/1/2_3V3` nets read 3V3 on copper, but bank membership of each ball is unknown | same pinout file (bank column) |
| RGMII DDR cells available for all 12 RGMII balls | DDR is only in Banks 1-2; ball-to-bank mapping unknown | same pinout file |
| Whether PIO SPI reaches the bitrate the FPGA config needs | no timing measurement possible without hardware | scope/logic analyser on first article |
| Whether the stale D7 was ever a real ball for this package | D7 is a pad with no net; no revision history proves intent | schematic revision history / Lattice pinout |

Everything else in this report is read directly from `Code-SDR-V2.kicad_pcb`, `CodeSDR.kicad_sym`, the two LPF files, `v2_top.v`, `v2_raw_path.v`, `build_diamond.tcl` and the firmware sources.

## 10. Reproduce

```powershell
$env:PYTHONIOENCODING='utf-8'
$K='C:/Program Files/KiCad/9.0/bin/python.exe'
& $K E:/engineering-portfolio-audit/evidence/cs-sw-parity/extract_pads.py
& $K E:/engineering-portfolio-audit/evidence/cs-sw-parity/parse_symbols.py
& $K E:/engineering-portfolio-audit/evidence/cs-sw-parity/gpio_af.py
& $K E:/engineering-portfolio-audit/evidence/cs-sw-parity/parity.py
& $K E:/engineering-portfolio-audit/evidence/cs-sw-parity/report_gen.py
```
