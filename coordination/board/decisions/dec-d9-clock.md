# DEC · Is D9 clock-capable on the LIF-MD6000-6JMG80I?

**Item:** the open question blocking the Code-SDR clock fix (`v2_top.lpf:16` D7→D9 + `build_diamond.tcl:99`)
**Repo:** `E:/engineering-portfolio-audit/repos/Code-SDR`, branch `work/2026-11-11` (read-only; `git status --porcelain` empty after this work)
**Verdict:** **YES — and stronger than "clock-capable". D9 is `PB16A` = `PCLKT2_0`, a dedicated
*primary-clock* pad in bank 2 (true side of the PB16A/PB16B pair). The sibling's residual UNVERIFIED
(`w2-cs-clock/REPORT.md:179`) is resolved in the D9 direction. No copper change, no fab change, no respin.**

Sources for the part facts: **Lattice CrossLink Family Data Sheet, FPGA-DS-02007-2.2**, downloaded from the
URL the repo itself cites (`design_model.py:564`, document_id 51662), plus **RP2040 Datasheet** for §5.
Both PDFs and extracted text are in `raw/`; every claim below is reproduced by a script in this directory.

---

## 1. What D9 actually is

| | value | evidence |
|---|---|---|
| Part | `LIF-MD6000-6JMG80I` | `verilog/build_diamond.tcl:22` (`-dev`), `hardware/v2/tools/design_model.py:559` |
| Package | **ctfBGA80** (80-ball), footprint `CodeSDR:LIF-MD6000-6JMG80I`, 80 pads | `check_copper.out.txt`: `U20 fpid: LIF-MD6000-6JMG80I pads: 80` |
| **Ball D9** | **`PB16A`**, bank 2, dual function **`PCLKT2_0`**, differential partner `True_OF_PB16B` | **Table 5.3 ctfBGA80/ckfBGA80 Pinout, p.51** (`raw/ds02007_text.txt:2432`) |
| Ball D10 | `PB16B`, bank 2, `PCLKC2_0` (the complement of D9's pair) | Table 5.3, p.51 (text line 2433) |
| Ball D7 | `VCCPLL_DPHY0` — a **D-PHY PLL supply**, bank `DPHY0`, no I/O function | Table 5.3, p.51 (text line 2431) |
| Bank-2 rail | `VCCIO2` = `FPGA_VCCIO2_3V3` | `design_model.py:531-532`; datasheet F6/F7 = `VCCIO2` (p.52) |
| Pinout revision | "CrossLink LIF-MD6000 **Pinout Version 1.4**" | §5 preamble, p.48 (text line 2265) |

The repo's own ball map agrees ball-for-ball: `design_model.py:505` has `"D9": "PB16A"`,
`"D7": "VCCPLL_DPHY0"`. **Cross-check over all 80 balls: 79/80 names match Table 5.3 exactly;**
the single difference is a truncation (`GNDPLL_DPHY` vs datasheet `GNDPLL_DPHYx`, ball D6) — naming
only, no functional consequence. So the model behind the board is the vendor's 80-ball map, and the
board's `LVCMOS33` on a bank-2 clock pad is consistent with the 3V3 `VCCIO2` this design uses.

---

## 2. D9 capability — verdict and the three independent statements that carry it

1. **Pinout table.** `D9 PB16A 2 PCLKT2_0` (Table 5.3, p.51). The `PCLK` prefix is the vendor's
   dedicated-primary-clock naming; the same table gives plain balls no clock function at all (e.g.
   `D10 PB16B … PCLKC2_0` is its complement; `F9 PB6A … GR_PCLK2_0` is the second-string path).
2. **Dual Function Pin Descriptions.** *"PCLK[T/C][Bank]_[num] — General Purpose Primary CLK pads …
   These pins provide **direct access to the primary and edge clock networks**"* (Table 5.5, p.55,
   text line 2621). Contrast the weaker classes in the same table: `GR_PCLK[Bank]0` gives only "a short
   General Routing path … should only be used when the design has used up all the PCLK pins … low speed
   clocks that are not sensitive to skew" (text line 2616); `GPLL2_0[T,C]` and `MIPI_CLK[T,C]` "do not
   provide direct access to the primary clock network" (text lines 2613, 2624). **D9 is in the strongest class.**
3. **Clocking structure.** §3.5.2, p.22: the primary clock network reaches "every synchronous element of
   the device", 8 global primary clocks, sources selected in the centre mux; dedicated PCLK pins mux into
   the edge-clock tree too (§3.5.3, p.22, text line 1170: "Dedicated Clock (PCLK) pins muxed with the
   DLLDEL output"). `PCLKT2_0` is a first-class source for both trees.

**Does 100 MHz fit?** Yes, with margin on the official numbers:

| limit | value | D9's job | source |
|---|---|---|---|
| `fMAX_PRI` primary clock tree | **150 MHz** max | 100 MHz → 1.5× margin | Table 4.13, p.37 (text line 1816) |
| `tW_PRI` min pulse width | 0.8 ns | 5 ns half-period | p.37 (text line 1817) |
| `tSKEW_PRI` skew within a clock | 450 ps max | — | p.37 (text line 1818) |
| `fIN` PLL `CLKI`/`CLKFB` input | **10–400 MHz** | 100 MHz is in range | Table 4.14, p.43 (text line 2078) |

`CLKI` is a PLL *port* (Table 3.5, p.21), not a pin, so the chain is
**D9 (`PCLKT2_0`) → primary clock network → PLL `CLKI`** — exactly what `v2_clock_pll.v` needs
(`CLKIN_PERIOD = 10 ns`, `v2_clock_pll.v:34`). The RTL is unaffected; only the `.lpf` literal is wrong.

**Answer to the literal question:** D9 is *not* "a general I/O that can take a clock via the global clock
network" — it is a **dedicated clock input pad** with direct primary/edge access, one class above that.

---

## 3. D7, now corroborated from the vendor table rather than from the repo's model

`v2_top.lpf:16` targets **D7**, which Table 5.3 (p.51) defines as `VCCPLL_DPHY0` — a supply ball of the
D-PHY PLL, with no user-I/O function in the table. A `LOCATE COMP` on a supply ball is not a stale pin
number; it is **unplaceable**. The sibling report's statement (`w2-cs-clock/REPORT.md:53-63`) is confirmed
by the vendor document, not just by `design_model.py:505,521`.

**Trap worth recording:** in the **64-ball** package (Table 5.2, p.49, text line 2347) ball **D7 *is*
`PB16A`**. Anyone who checked the wrong package table would conclude D7 is right. The board is the
80-ball part (`build_diamond.tcl:22`), so Table 5.3 is the table that governs.

---

## 4. Copper at D9 — re-measured here (copper proves routing, not capability)

`check_copper.py` (KiCad 9.0 `pcbnew`, read-only):

* ball D9: net `ADC_CLK`, netcode **12**; ball D7: net `''`, netcode **0**; ball J8: net `''`, netcode 0;
  ball K8: net `RGMII_RXD0_FPGA` (netcode 212 — so K8 is **not** free, see §6).
* `ADC_CLK` pads: exactly **3** — `R31.2`, `U20.D9`, `U21.2`.
* copper: **51 track segments + 4 vias = 55 items, 42.371 mm**, on `F.Cu` and `B.Cu`.
* `GetUnconnectedCount(False)` = **0**.

These reproduce the board's cs-clock line (`AGENT_BOARD.md:57`: "55 items, 42.371 mm, 0 unconnected")
exactly. That is what routing can tell you. It says nothing about whether the ball can accept a clock —
which is why §2 is the load-bearing section, and it comes from the device datasheet, not from copper.

---

## 5. The 6 GPIO constants: pad → GPIO is right, the SPI transport is not

`firmware/rp2040_dashboard/fpga_config.h:25-30` holds pad numbers; the Arduino core wants GPIO numbers.
`check_gpio.py` maps each through RP2040 **Table 615 (p.613-614)** and **Table 2 (§1.4.3, p.13-14)**:

| constant | pad | → GPIO | board net (`design_model.py:379-386`) | SPI0 F1 on that GPIO | pad→GPIO | as an SPI0 role |
|---|---|---|---|---|---|---|
| `PIN_FPGA_SCK` | 2 | **0** | `FPGA_SPI_SCK_MCU` | `SPI0 RX` (input) | ✔ | **impossible** |
| `PIN_FPGA_MOSI` | 3 | **1** | `FPGA_SPI_MOSI` | `SPI0 CSn` | ✔ | **impossible** |
| `PIN_FPGA_MISO` | 4 | **2** | `FPGA_SPI_MISO` | `SPI0 SCK` (output) | ✔ | **impossible, and would drive into the FPGA's MISO output** |
| `PIN_FPGA_CS_N` | 5 | **3** | `FPGA_SPI_CS_N` | `SPI0 TX` | ✔ | irrelevant — CS is driven by `digitalWrite` (`fpga_config.cpp:38`) |
| `PIN_FPGA_RESET_N` | 29 | **18** | `FPGA_RESET_N` | `SPI0 SCK` (unused) | ✔ | n/a — plain SIO output |
| `PIN_FPGA_CDONE` | 41 | **29** | `FPGA_CDONE` | `SPI1 CSn` (unused) | ✔ | n/a — plain SIO input |

**Are the six real user I/O on this package?** Yes — all six are listed `Digital IO (FT)`,
power domain `IOVDD`, "User IO" in Table 615; `GPIO29` is `GPIO29 / ADC3` (also a digital pin, which is
all `digitalRead` needs). None of them is a QSPI, USB or crystal pin. `GPIO18` extra: it is even in SPI0's
legal SCK set, which is a coincidence, not a route.

**Is the remap valid?** **As a pin map: yes, 6/6 exactly.** **As a working firmware: no.** RP2040's SPI0
functions are fixed per pad by silicon, and the Arduino-Pico 6.1.0 core enforces them:

* `setRX` legal SPI0 = {0, 4, 16, 20} — `SPI.cpp:336-338`
* `setCS` legal SPI0 = {1, 5, 17, 21} — `SPI.cpp:368-370`
* `setSCK` legal SPI0 = {2, 6, 18, 22} — `SPI.cpp:395-397`
* `setTX` legal SPI0 = {3, 7, 19, 23} — `SPI.cpp:422-424`
* illegal pin ⇒ `panic("FATAL: … illegal pin %d")` — `SPI.cpp:357, 384, 411, 443`

So `SPI.setSCK(0)` / `SPI.setTX(1)` / `SPI.setRX(2)` (`fpga_config.cpp:42-44`, `rp2040_dashboard.ino:186-188`)
are all illegal and hit `panic()`; pico-sdk `panic()` prints `*** PANIC ***` and calls `_exit(1)`
(`pico_platform_panic/panic.c:31-49`). The board's four SPI nets are role-rotated against SPI0's fixed
sets: SCK is on GPIO0, MOSI on GPIO1, MISO on GPIO2, CS on GPIO3, i.e. `(RX, CSn, SCK, TX)`.

**Why no pin shuffle fixes it:** the FPGA side is fixed too — sysCONFIG pins are dedicated
(`SPI_SCK`/`MOSI`/`MISO`/`SPI_SS` in Table 5.5 "Configuration", p.55; board balls J1/G1/K1/H1 per
`fpga_config.h:9-11` and `v2_top.lpf:58-62`). Copper and both ends pin all four roles; SPI1's legal pads
(GPIO8-11, 12-15, 24-27) are already spent on `SYNTH_*`, `LMX_*`, `ADF_*`, `DSA_*`
(`design_model.py:380-386`). **The transport must leave the SPI0 peripheral.**

---

## 6. Least-effort answer under the owner steer

**D9 did not fail, so the least-effort answer is the fix already on the table**, unchanged:

1. `verilog/v2_top.lpf:16` — `SITE "D7"` → `SITE "D9"`; `IOBUF PORT "clk_100m_in" IO_TYPE=LVCMOS33`
   already matches bank 2's `VCCIO2` 3V3 rail (§1).
2. `verilog/build_diamond.tcl:99` — consume `v2_top_generated.lpf` (which already says `D9`,
   `v2_top_generated.lpf:7`) and delete the hand copy.
   ⇒ **constraint edit only: no copper, no stackup, no fab burden, no respin.**

**But the item is not "firmware-only" in the sense of six digits.** The bitstream-load path needs a
transport the SPI0 peripheral cannot provide on those pads (§5). Cheapest true fix, still zero copper:
drive SCK/MOSI/MISO/CS with **PIO** (or SIO bit-bang) on GPIO0-3 — legal because *"SIO, PIO0 and PIO1 can
connect to all GPIO pins"* (RP2040 §1.4.3, p.13, text line 554). Cost is a small PIO program plus replacing
the `SPI.transfer` call sites (`fpga_config.cpp:41-44,66`; `rp2040_dashboard.ino:153-166,186-189`).
Note the six constants are duplicated at `rp2040_dashboard.ino:91-96` *and* `fpga_config.h:25-30` — the
`.ino` block shadows the header, so both must change.

**If D9 had turned out not to be clock-capable**, ranked least-effort first:

* **A. Constraint-only, zero copper:** keep the net on D9 and clock the fabric through the
  *general-routing* path to the primary clock network. DS-02007 §3.5.2 (p.22) lists "GPIO pins" among
  legitimate primary-clock sources, so even a plain I/O ball can drive the network; the price is
  insertion delay/skew against the PCLK "direct access" path (Table 5.5). At 100 MHz that skew, not the
  pin, would be the risk.
* **B. One-trace copper move:** move only the `R31.2 → U20` leg onto a free bank-2 clock pad, then edit
  the LPF `SITE`. Which pads exist matters, and the obvious ones are taken: `K8` = `PB16C` = `PCLKT2_1`
  is the *only other true-side PCLK2 pad* and it carries `RGMII_RXD0_FPGA` (netcode 212, §4); the free
  one is `J8` = `PB16D` = `PCLKC2_1`, the **complement** side (netcode 0). So B is a trace swap in a
  0.65 mm BGA escape (`design_model.py:544-546` already complains that J8/J9 need via-in-pad HDI),
  i.e. design rework — acceptable fab burden, worse than A.
* **C. Respin** — not needed, not proposed.

---

## 7. UNVERIFIED — and exactly what would settle each

| # | open item | what settles it |
|---|---|---|
| 1 | Whether Diamond takes a `PCLKT2_0` pad straight to `PLL CLKI` with only `LOCATE`+`IOBUF` (no extra clock attribute), i.e. the clock-network assignment in the `.lpf` | **CrossLink sysCLOCK PLL/DLL Design and Usage Guide, FPGA-TN-02015** (cited by DS-02007 §3.5 and Table 5.5), plus a Diamond 3.x `par`/`map` run. Diamond is **not installed on this host** (`check` found no `C:\lscc`, no `diamondc`), so no PAR receipt exists. A vendor tool would also *refuse* an unplaceable clock site, which is the definitive end-to-end proof. |
| 2 | Single-ended use of `PCLKT2_0` while `D10` (`PB16B`, its complement, `PCLKC2_0`) carries `ADC_D0` | DS-02007 Table 5.5 does not forbid it; differential pairing binds only when a differential I/O standard is used. Diamond PAR would reject it if illegal. Low risk. |
| 3 | The bare-metal `_exit(1)` path after the SPI `panic()` | `panic.c:49` calls `_exit(1)`; the RP2040 `_exit` implementation in this core's newlib was not traced. Behaviour either way is "no valid SPI0 configuration". |
| 4 | Config-time budget: `fpga_config.h:6` claims 0.1–0.2 s, but **no `.bit`/`.jed` exists in the repo** (searched), so PIO-vs-bit-bang cannot be sized from evidence | A real `v2_top.bit` size, or a measured `fpga_program_from_file()` run. |
| 5 | Overall Code-SDR fab readiness / DRC count | Not mine; the sibling reported 222 violations, 0 unconnected, and I did not re-derive them. `AGENT_BOARD.md:146-159` / the fab owner. |

*Not* on this list any more: "is D9 clock-capable" — that is settled by §2.

---

## 8. Board status

* **No `BOARD CORRECTION:`** — every board number this item touches holds. `AGENT_BOARD.md:57`
  ("55 items, 42.371 mm, 0 unconnected") was **reproduced independently** here (`check_copper.out.txt`).
  The board's open decision #2 (`AGENT_BOARD.md:164`) is answered: **D9 is clock-capable — yes.**
* **Precision note on `AGENT_BOARD.md:130`** ("conditional on D9 = CLKI"): `CLKI` is a PLL port, not a
  pin. The condition is satisfied in the form that matters — D9 is a dedicated primary-clock pad
  (`PCLKT2_0`) with direct access to the clock network that feeds `CLKI`. The condition, not the wording,
  is what blocks nothing.
* **Correction to the sibling report, not the board:** `w2-cs-clock/REPORT.md:156` concludes
  "This is firmware-only: **0, 1, 2, 3, 18, 29**". The six values are **correct** as a pad→GPIO map, but
  the sentence implies the remap is sufficient. It is not: on those pads SPI0 cannot be the SPI master
  (§5), so the load path needs PIO/bit-bang as well. The clock half of that report stands unchanged.

---

## 9. Files in this directory

| file | what it is |
|---|---|
| `check_d9.py` / `check_d9.out.txt` | Parses Table 5.3 from the datasheet text: prints the D9/D7/D10 rows, the bank-2 clock-pad inventory, Table 5.5 clock-pad definitions, the four timing limits, and cross-checks all 80 `design_model.py` ball names against Table 5.3 (**79/80**). |
| `check_gpio.py` / `check_gpio.out.txt` | Parses RP2040 Table 2 (GPIO function select) and Table 615 (QFN-56 pad list), maps the six `fpga_config.h` constants pad→GPIO, and flags each one against the SPI0 role the firmware needs. |
| `check_copper.py` / `check_copper.out.txt` | KiCad `pcbnew` read-only: D7/D9/D10/K8/J8 nets, `ADC_CLK` pad list, 51 segments + 4 vias = 55 items, 42.371 mm, 0 unconnected. |
| `extract_pdf.py`, `extract_rp2040.py`, `pages.py`, `pages_rp2040.py` | Text extraction (pypdf 7.1.0) and text-line → PDF-page mapping used for the citations above. |
| `raw/ds02007_1.bin` (1,144,512 B) + `raw/ds02007_text.txt` | FPGA-DS-02007-2.2 as downloaded, and its 67-page text. `ds02007_2.bin` is the same document fetched via the second URL (identical size) — kept as a download receipt. |
| `raw/rp2040_datasheet.pdf` (5,301,205 B) + `raw/rp2040_text.txt` | RP2040 datasheet, 642 pages, and its text. |

**Provenance:** Tier A (vendor device datasheets, primary documents: Table 5.3/5.5/4.13/4.14, Table 2/615,
Arduino-Pico source), plus one Tier-B measurement (KiCad connectivity/copper count). No number here is
closed-form inference. Diamond was unavailable, so no place-and-route claim is made — every such item
is listed as UNVERIFIED in §7.

**Read-only compliance:** nothing written inside `repos/`; no commit, no branch operation;
`git -C repos/Code-SDR status --porcelain` returns empty and HEAD is still `work/2026-11-11`.