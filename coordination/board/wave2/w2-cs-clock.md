# W2 · Code-SDR — D7 vs D9 and the "dead copper" clock

**Item:** Code-SDR / clock pin resolution
**Repo:** `E:/engineering-portfolio-audit/repos/Code-SDR`, branch `work/2026-11-11`
**Verdict:** the clock does **not** land on dead copper. It lands on **U20.D9 / net `ADC_CLK`**, fully
routed. The *constraint file the build actually consumes* points the clock at **U20.D7**, which has no
net at all and is not even a user-I/O ball — it is `VCCPLL_DPHY0`, a PLL supply. The defect is a
one-line error in `verilog/v2_top.lpf`, not in copper and not in firmware.

All measurements below are reproducible with the scripts in this directory. Tool: KiCad 9.0.7
`pcbnew` Python bindings (the same connectivity engine the GUI ratsnest uses) plus `kicad-cli pcb drc`.

---

## 1. Physical trace of the clock net

Driver chain, read pad-by-pad from `hardware/v2/Code-SDR-V2.kicad_pcb` (`chain.out.txt`):

| Stage | Ref | Pad | Net |
|---|---|---|---|
| Oscillator | Y40 `SiT8209AC-23-33E-100.000000X` | 3 | `REF_100M_OSC` |
| Fanout in | U42 `CDCLVC1104PWR` | 1 | `REF_100M_OSC` |
| Fanout out | U42 | 3 | `REF_100M_ADC` |
| Series R | R31 `33R` | 1 | `REF_100M_ADC` |
| Series R | R31 | 2 | **`ADC_CLK`** |
| **FPGA clock input** | **U20 `LIF-MD6000-6JMG80I`** | **D9** | **`ADC_CLK`** |
| ADC clock input | U21 `AD9215BCPZ-105` | 2 | `ADC_CLK` |

So the board's 100 MHz tree terminates on **U20 ball D9**, net **`ADC_CLK`** (netcode 12).

### Is that pad connected to anything else? Yes — and it is not dead copper

- Net `ADC_CLK` carries exactly 3 pads: `U21.2`, `U20.D9`, `R31.2` (`trace_pcbnew.out.txt`).
- Copper on the net: **51 track segments + 4 vias = 55 copper items**, total **42.371 mm**, on `F.Cu`
  and `B.Cu`. It is physically routed, not a stub.
- Authoritative connectivity: `kicad-cli pcb drc` on the PCB reports
  **`Found 0 unconnected items`** (222 violations, all of them `lib_footprint_mismatch`,
  `via_dangling`, `track_dangling`; `unconnected_items: 0`, `schematic_parity: 0`) — see `drc.json`.
  A net with 0 unconnected items is fully joined to every pad in its netlist class.
- Cross-check with the repo's own copper-derived generator, run read-only:
  `python tools/gen_lpf.py --table` prints `D9  ADC_CLK` (`gen_lpf_table.txt`).

**Dead copper: NO for D9.** One cosmetic `via_dangling` exists on this net (a stub via, ~ invisible at
100 MHz); it does not break the connection.

### D7, by contrast, is genuinely dead

| | netname | netcode | note |
|---|---|---|---|
| U20.**D7** | `''` (empty) | **0** | no net, no copper, no ratsnest edge |
| U20.**D9** | `'ADC_CLK'` | **12** | live, routed, 0 unconnected |

D7 is not merely unconnected — it is not assignable as a signal at all:

- `hardware/v2/tools/design_model.py:505` — `"D7": "VCCPLL_DPHY0"`
- `design_model.py:521` — *"The unused D-PHY analog and PLL supplies (D2/D4/D7/E7) are intentionally
  unpowered, as permitted by FPGA-TN-02013."*
- `design_model.py:1557` — `assert all(fpga_pins[ball] is None for ball in ["D2","D4","D7","E7"])`

D7 is a **PLL supply ball**. `LOCATE COMP "clk_100m_in" SITE "D7"` locates a clock net onto a power
ball: it is either rejected by place-and-route or lands on copper that no signal can reach.
Wave-1's phrase "dead copper at D7" is directionally right about the *constraint target* but wrong
about the *board*: the copper at D7 is absent, and the real clock copper at D9 is healthy.

---

## 2. What the RTL / build expects

The RTL has no pin knowledge — `clk_100m_in` is a bare port:

- `verilog/v2_top.v:38` — `input wire clk_100m_in,`
- `verilog/v2_clock_pll.v:2` — *"100 MHz board reference -> 125 MHz Ethernet clock"*
- `verilog/v2_clock_pll.v:34` — `localparam integer CLKIN_PERIOD = 10; // 100 MHz input, ns`
- `verilog/v2_clock_pll.v:41` — `CLKFB_DIV = 5` (VCO = 500 MHz), `.CLKI (clk_100m_in)`

The RTL expects a **100 MHz** clock, which is exactly what Y40/U42 deliver on `ADC_CLK`. **No RTL
change is required.** The pin location is decided solely by the `.lpf`.

### The two pad numbers and two net names

| | Pad | Net | Where it comes from |
|---|---|---|---|
| **CLOCK_PAD** (physical truth) | **U20.D9** | **`ADC_CLK`** (netcode 12) | PCB copper; `verilog/v2_top_generated.lpf:7` |
| **EXPECTED_PAD** (what the build is told) | **U20.D7** | *(none — netcode 0)* | `verilog/v2_top.lpf:16` |

### The two LPFs disagree, and the build uses the wrong one

```
verilog/v2_top.lpf:16            LOCATE COMP "clk_100m_in" SITE "D7";   # ADC_CLK (... -> U20.D7)
verilog/v2_top_generated.lpf:7   LOCATE COMP "clk_100m_in" SITE "D9";
verilog/build_diamond.tcl:99     prj_src add verilog/v2_top.lpf          <-- the wrong one
```

`v2_top_generated.lpf` is produced by `tools/gen_lpf.py` straight from the PCB pads and is **correct**.
`build_diamond.tcl:99` adds the **hand-written** `v2_top.lpf` (D7) and never references the generated
file — grep for `v2_top_generated` finds only `gen_lpf.py` and `README.md:134`, never the Tcl flow.
That is the entire D7/D9 defect: a stale hand-maintained constraint file shadowing the generated one.

The repo already documents the mismatch without fixing the file that matters:
`HARDWARE.md:44-47` ("the sample clock lands on U20.D9, not D7 as an earlier revision of this
document stated ... U20.D7 has no net") and `BRINGUP.md:19` ("`ADC_CLK` (net 12) rings from U21.1 to
U20.D9 (not D7)").

*(Secondary doc error, not a hardware fault: `HARDWARE.md:40` says `ADC_CLK` is at `U21.1`. The
AD9215 pad map at `design_model.py:610` gives `"1": "DNC", "2": "CLK"`, and the PCB puts `ADC_CLK`
on U21 pad 2 — the clock is on the ADC's real `CLK` pin. `HARDWARE.md` should say U21.2.)*

---

## 3. The fix

**Not firmware. Not copper. Copper is correct and needs no change.**

The fix is a constraint-file correction (one line) plus removing the duplicate source of truth:

1. **`verilog/v2_top.lpf:16`** — change `SITE "D7"` to `SITE "D9"`:
   ```
   LOCATE COMP "clk_100m_in" SITE "D9";      # ADC_CLK (100 MHz tree -> U20.D9)
   IOBUF PORT "clk_100m_in" IO_TYPE=LVCMOS33;
   ```
2. **`verilog/build_diamond.tcl:99`** — consume the generated file instead of the hand copy:
   `prj_src add verilog/v2_top_generated.lpf`, then delete `v2_top.lpf` so the D7 value cannot
   reappear. One file, derived from copper, is the only durable fix.
3. **Still required before a releasable bitstream** (the LPF's own TODO block,
   `v2_top.lpf:64-77`): add `create_clock` for 100 MHz in and the PLL's 125 MHz out; confirm per-bank
   `IO_TYPE`/VCCO (3V3 vs 2V5); replace the behavioural RGMII DDR process with real CrossLink DDR
   cells. These are timing/QoR work, not a pad error.

**No copper respin is needed for the clock.** The 100 MHz tree, the 33R series termination and the
fanout are all routed and DRC-clean (0 unconnected).

### The 6 firmware constants (asked for explicitly)

These are **not** the clock fix, but they are the six values that gate whether a bitstream can be
loaded at all, and wave-1 flagged them as 0 match / 6 mismatch. **Wave-1 is correct, and I confirmed
the mechanism:** `firmware/rp2040_dashboard/fpga_config.h:25-30` uses **physical pad numbers where
the Arduino core expects GPIO numbers**.

The firmware itself confesses this at `rp2040_dashboard.ino:19-22`: *"the four SPI GPIO numbers below
are physical RP2040 pins from the PCB net list (U10.x) and must be cross-checked against ... the
RP2040 QFN-56 pin -> GPIO mapping before flashing."*

Pad→GPIO mapping from `design_model.py:362-368`, board nets from `design_model.py:379-386`:

| Constant | `fpga_config.h` | Pad (correct net ✓) | GPIO for that pad | Correct value | Status |
|---|---|---|---|---|---|
| `PIN_FPGA_SCK` | 2 | U10.2 → `FPGA_SPI_SCK_MCU` (GPIO0) | **0** | **0** | wrong |
| `PIN_FPGA_MOSI` | 3 | U10.3 → `FPGA_SPI_MOSI` (GPIO1) | **1** | **1** | wrong |
| `PIN_FPGA_MISO` | 4 | U10.4 → `FPGA_SPI_MISO` (GPIO2) | **2** | **2** | wrong |
| `PIN_FPGA_CS_N` | 5 | U10.5 → `FPGA_SPI_CS_N` (GPIO3) | **3** | **3** | wrong |
| `PIN_FPGA_RESET_N` | 29 | U10.29 → `FPGA_RESET_N` (GPIO18) | **18** | **18** | wrong |
| `PIN_FPGA_CDONE` | 41 | U10.41 → `FPGA_CDONE` (GPIO29_ADC3) | **29** | **29** | wrong |

All six constants point at the right *net* but the wrong *GPIO*: as written, `digitalWrite(41, …)`
targets a GPIO that does not exist on the RP2040, and `SPI.setSCK(2)` drives the pin wired to
`FPGA_SPI_MISO`. This is firmware-only: **0, 1, 2, 3, 18, 29**. It does not touch the clock pad and
it does not touch copper.

---

## 4. Does an FPGA pin constraint file exist?

**YES — wave-1's "no pin constraint file was found" is REFUTED.** Two exist:

| File | Clock SITE | Complete? | Used by build? |
|---|---|---|---|
| `verilog/v2_top.lpf` (77 lines, hand-maintained) | **D7** (wrong) | yes — 25 `LOCATE`/`IOBUF` pairs for every `v2_top` port | **yes**, `build_diamond.tcl:99` |
| `verilog/v2_top_generated.lpf` (generated) | **D9** (right) | yes — same port set, emitted from PCB pads | no |

No other constraint format exists in the tree: a repo-wide search for `*.ldf, *.prj, *.sty, *.pdc,
*.sdc, *.xdc, *.qsf` outside the vendored `openfpga_framework/` returns nothing. The `.lpf` is the
project's only pin-constraint mechanism (Lattice Diamond `LOCATE`/`IOBUF`, LPF format), and
`build_diamond.tcl` creates the Diamond project from scratch (`prj_project new ... -dev
LIF-MD6000-6JMG80I`, `build_diamond.tcl:22,94-95`), so no project file is needed.

Therefore **a bitstream can be targeted** — the blocker was never a missing constraint file, it was
one wrong literal inside a constraint file that exists.

**UNVERIFIED:** whether Diamond accepts **PB16A (ball D9)** as a PLL `CLKI` / primary-clock input.
`design_model.py:540` asserts the ball was chosen as *"a true primary-clock input"*, but the Lattice
device pin database is not in the repo and Diamond is not installed on this host, so that claim
cannot be checked here. If D9 turns out not to be clock-capable, the fix moves from a one-line edit
to a ball relocation — that is the one residual risk in a "no copper change" conclusion.

---

## 5. Answer block

- **CLOCK_PAD:** U20.D9, net **`ADC_CLK`** (netcode 12); driven Y40.3 `REF_100M_OSC` → U42.1 →
  U42.3 `REF_100M_ADC` → R31 (33R) → `ADC_CLK` → U20.D9 + U21.2.
- **EXPECTED_PAD:** U20.**D7**, net **none** (`''`, netcode 0) — the value in
  `verilog/v2_top.lpf:16`, which `build_diamond.tcl:99` actually compiles.
- **DEAD_COPPER:** **No** on D9 (55 copper items, 42.371 mm, DRC 0 unconnected). **Yes** on D7 (no net
  at all; D7 is `VCCPLL_DPHY0`, a PLL supply ball per `design_model.py:505,521`). So the clock does
  **not** land on dead copper; the constraint does.
- **FIX:** constraint-only, no copper. `v2_top.lpf:16` `SITE "D7"` → `SITE "D9"`; point
  `build_diamond.tcl:99` at `v2_top_generated.lpf` and delete the hand copy. Separately (firmware-only,
  the bitstream-load path, not the clock): `fpga_config.h:25-30` must become **0, 1, 2, 3, 18, 29** —
  they are pad numbers today, GPIO numbers are required.
- **CONSTRAINT_FILE:** **EXISTS** — `verilog/v2_top.lpf` (D7, wrong, used) and
  `verilog/v2_top_generated.lpf` (D9, right, unused). Wave-1 "not found" is refuted.
- **FAB_BLOCKED:** **No, not by this item.** Constraints exist, target real copper after the one-line
  fix, and the net is DRC-connected (0 unconnected). Residual: 222 DRC violations (199
  `lib_footprint_mismatch`, 13 `via_dangling`, 10 `track_dangling`) and the UNVERIFIED D9
  clock-capability question. Overall fab readiness is the fab agent's call — wave-1 reported
  10 PASS / 8 FAIL / 15 MISSING for Code-SDR fab; I did not re-derive that.

---

## Evidence files in this directory

| File | What it is |
|---|---|
| `trace_pcbnew.py` / `.out.txt` | U20 D7 vs D9 pad/net dump, ADC_CLK pad list + copper counts, all 80 U20 balls |
| `clusters.py` / `.out.txt` | per-pad cluster + ratsnest attempt (shows `GetUnconnectedCount` = 0) |
| `chain.py` / `.out.txt` | Y40 → U42 → R31 → ADC_CLK → U21/U20 full chain, U21 pad map |
| `drc_and_fw.py` / `.out.txt` | DRC violation breakdown + the 6 firmware constants vs U10 pads |
| `drc.json` | raw `kicad-cli pcb drc` output: 222 violations, **0 unconnected_items** |
| `gen_lpf_table.txt` | repo's own `tools/gen_lpf.py --table`, showing `D9 ADC_CLK` |
| `trace_clock.py` | first-attempt pure-s-expr parser (superseded by pcbnew; kept for audit trail) |

Read-only compliance: no file inside `repos/` was modified; `gen_lpf.py` was run with `--table` only.