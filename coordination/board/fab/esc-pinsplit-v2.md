# ESC split — pin split v2: the control board carries the measurement, the BEC and the MCU

**Task:** redo the board split so the CONTROL board actually carries the measurement, the BEC and
the MCU (the owner's words), and define the complete 2x20 / 40-pin interconnect header.
**Input:** `evidence/esc-split-power/`, `evidence/esc-split-control/` (read-only)
**Output:** this directory. Every board file touched here is a COPY. Nothing written into any
repository, nothing committed.
**Status: COMPLETE.** Skeleton written first, sections appended after each step.

---

## 0. Headline

| Question | Answer |
|---|---|
| Block assignment | **MCUs: 7 -> 1, and that 1 is on the control board.** The six cell `STM32G431`s merge into the supervisor `RP2354B`; the six `INA296A2`, six `DRV8353`, 36 FETs, 24 shunts, bus bars and bus capacitance stay on the power board. BEC, CAN-FD, USB, watchdog, SWD, crystals, all ADC + calibration logic: control board. |
| What the split actually costs in conductors | The owner's split, taken literally on today's board, cuts **207 nets** (`s2_cut.py`, MEASURED). Merging the six cell MCUs into one is what makes it buildable: **77 signal nets**, which is the interface defined here. |
| The header | **The agreed 2x20/40 provides 40 positions against a measured requirement of 120 (77 signal + 43 ground) — one third of the interface.** The interface closes at **3 x 2x20 = 120 positions**, all 120 allocated, zero spare except a fully-pinned 7th channel. Forty positions is not a tight fit, it is 33% of the requirement, and no allocation of 40 carries 77 signals even with no grounds at all. |
| Gate drive | **The gate driver stays on the power board and no gate net crosses: 0 nH added.** What crosses is 3 PWM lines per motor (3x mode) instead of today's 6. Added inductance **8.29 nH per line** (adjacent return) / 17.5 nH (far return) -> **8.55 mV of a 3.3 V swing**, 0.18 ns of skew, **0.18% of the DRV8353's 200 ns propagation delay**. Series termination **not required for signal integrity**; 22 Ω recommended for crosstalk, and that is a different problem. |
| Current sense | **The `INA296A2` stays 3 mm from its shunt; only its analogue output crosses.** Contact resistance is *not* the risk: 20 mOhm/pin x 40 uA of bias current = **1.6 uV = 0.003% of full scale**. The risk is mutual inductance, and the header multiplies it **12.2x**. Error budget: **0.215 mV = 0.020% FS** (output crosses) vs **73.90 mV = 136% FS** (Kelvin pair crosses). |
| Currents on the header | Worst single pin **120.2 mA = 4.0% of the 3 A contact rating**. Nothing needs paralleling for ampacity; the 4x `BAT_P` and the 5.08 mm guard column are for **redundancy and 44.4 V creepage**, not current. |
| Control board | **63.0 cm2 (105 x 60 mm), 2-layer, 1 oz, single-sided, HDI-free**, 4-layer fallback if first-article noise fails. It stacks inside both candidate power-board outlines with 28 mm of margin — **but the vertical stack defects from the last wave are unchanged, and my change makes one of them worse** (§6.3). |

**Read this first:** the last wave's complaint was that 6 of 7 MCUs and all the measurement stayed
on the power board. Both are fixed, and one of them could only be fixed by **deleting hardware**,
not moving it: with a shared power bus there is one ground, so the six galvanic isolation
barriers are physically gone. That deletes 6 x `ISO6731` and 6 x `RFM-0505S`, and it is what makes
one MCU able to drive six bridge drivers across one quiet ground. The alternative reading — keep
six isolated domains and move the MCUs up — needs **six isolated ground returns through the
header** and 198 signal nets, and is not buildable on any 2.54 mm connector.

---

## 1. Functional census and board assignment

### 1.1 What is actually on the board (MEASURED, this wave)

`hdr/net_dump.json` (the parsed `esc.net`, Eeschema 9.0.7) and the PCB copy
(`esc_copy.kicad_pcb`, 607 footprints) read with `pcbnew` 9.0.7:

| Layer of the truth | Number | How |
|---|---|---|
| Netlist components | **599**, in **563 nets**, 7 sheets | `s1_blocks.py` |
| Per-cell components | **94 x 6 cells** | same |
| BEC / auxiliary-power sheet | **35** | same |
| Supervisor block (`/Controller and ADC/`, 200-series) | **70** — present on the PCB, **absent from `esc.net`** | last wave, still true |
| Board footprints / outline (repo board) | 607 / 728.16 cm2 | `s3_partition.py` |
| Board the area wave used ("powerfirst") | 687 fps / 382.71 cm2 | last wave |

Each of the six cells is 94 parts: 6 FETs, 4 shunts (3 phase + 1 bus), `DRV8353SRTAR`,
`STM32G431CBT6`, `INA296A2IDR`, `ISO6731FDWR`, `RFM-0505S`, `TPS70933DBVR`, `SN74LVC1G08DBVR`,
8 MHz crystal, NTC, 37 capacitors, 32 resistors, 3 connectors, 2 diodes, 1 ferrite.

The per-cell net names are the design document. From `s1_blocks.py`:

```
M1_PWM_AH -> U1101.32[INHA]      M1_PWM_AL -> U1101.33[INLA]     ... x3 phases  = 6 PWM per cell
M1_CSA_A_RAW -> U1101.23[SOA]    -> RC -> M1_CSA_A -> U1102.8[PA0]   ... x3 = 3 analogue
M1_BUS_SH_P -> U1105.8[IN+]      M1_BUS_SH_N -> U1105.1[IN-]     U1105.5[OUT] -> BUS_CURRENT_RAW -> PA3
M1_DRV_SCLK/SDI/SDO/nCS/nFAULT/ENABLE -> U1101 (SPI, fault, enable)
M1_NTC -> U1102.16[PB0]          M1_SWCLK/SWDIO/NRST -> J1103 LOCAL_SWD
```

So today: **6 PWM per motor (6x/independent mode), 3 phase-current analogue outputs, 1 bus-current
output, 1 NTC, 4 SPI, 2 control** — per cell.

### 1.2 The assignment table

Rule applied verbatim from the brief: *anything that touches high current or a fast edge stays on
the power board; anything that measures, computes or regulates goes to the control board.*

| # | Functional block | Today | **Board** | One-line reason |
|---|---|---|---|---|
| 1 | 3-phase FET bridge (6 x `IPTC014N10NM5`) | per cell | **POWER** | 154 A peaks, 1.5 kV/us edges |
| 2 | Phase shunts 3 + bus shunt 1 (0.5 mOhm 5 W) | per cell | **POWER** | 109 A through them; Kelvin taps must be 3 mm from the amplifier |
| 3 | Gate-drive power stage (`DRV8353` GHA/GLA.., gate resistors, VCP/CPH/CPL) | per cell | **POWER** | the loop is 12 nH today and must stay that way |
| 4 | `DRV8353` **logic side** (INHx/INLx, SPI, ENABLE, nFAULT) | per cell | **POWER device, CONTROL interface** | the driver cannot leave its FETs; its *inputs* cross as 3 PWM + 1 nCS and its fault joins a wired-OR |
| 5 | `DRV8353` internal CSAs x3 (SOA/SOB/SOC) | per cell | **POWER, output crosses** | §3: 54.5 mV-class differential cannot survive the header, the conditioned output can |
| 6 | `INA296A2` bus-current amplifier | per cell | **POWER, output crosses** | §3. Kelvin pair is 2 contacts from the shunt; output is 1.09 V low-Z |
| 7 | Cell MCU `STM32G431` **x6** | per cell | **CONTROL, merged into 1** | a shared bus means one ground and one control authority; six MCUs on one 44.4 V bus is six masters for one bus |
| 8 | Cell 3V3 LDO `TPS70933` x6 | per cell | **DELETE** | its three loads (MCU, isolator, gate) leave; one reference on the control board serves all six VREF pins instead |
| 9 | `ISO6731` digital isolator **x6** | per cell | **DELETE** | *deleted by the shared bus*: the barrier it maintains no longer exists |
| 10 | `RFM-0505S` isolated DC-DC **x6** | per cell | **DELETE** | same reason; with one ground, an isolated 5 V supply has nothing to be isolated from |
| 11 | `SN74LVC1G08` ARM gating x6 | per cell | **CONTROL (1 gate)** | six AND gates for six MCUs collapse to one for one MCU |
| 12 | 8 MHz crystal x6 | per cell | **CONTROL (1 crystal)** | one MCU, one clock |
| 13 | NTC thermistor x6 | per cell | **POWER, analogue crosses** | must be on the hot body; it is a resistor, not a measurement system |
| 14 | Bus-voltage divider | per cell | **POWER, analogue crosses** | 44.4 V must be divided before it goes anywhere |
| 15 | Status LED, LOCAL_SWD header x6 | per cell | **DELETE / 1 on CONTROL** | six debug headers for six MCUs that no longer exist |
| 16 | Bus capacitance (6 x 820 uF/100 V + 37 caps/cell) | per cell | **POWER** | energy storage belongs at the switches |
| 17 | Cell connectors (`FUSED_BATTERY_TAP`, `MOTOR_PHASES`), M5 lugs | per cell | **POWER** | high-current terminals |
| 18 | Supervisor `RP2354B` + CAN-FD `MCP2518FD`/`TCAN3413` + choke/ESD | 70 fps | **CONTROL** | computes and talks |
| 19 | BEC (2 x `LM5164` + `AP2112K`), TVS `SM8S51A` | 35 fps | **CONTROL** | regulates |
| 20 | 2 x USB-C, `TPS3430` watchdog, 12/40 MHz crystals, `SW201`, `J201` SWD | 70 fps | **CONTROL** | compute / debug / safety chain |
| 21 | **NEW: 3 x 16-bit 8-channel simultaneous ADC + 31-channel anti-alias RC** | — | **CONTROL** | the MCU's own 8-channel ADC cannot take 31 channels; this is the measurement the owner asked to move |
| 22 | **NEW: 3 x 2x20 header pair** | — | **both** | the interface itself |

### 1.3 The cut, measured — and why 40 pins is one third of a header

`s2_cut.py` assigns every component to a side and counts the nets that then have pads on both.
Measured on the real netlist:

| Partition | Which parts move | **Crossing nets** |
|---|---|---|
| **A — the owner's words, literally:** supervisor + BEC + the 6 `STM32G431` + the 6 `INA296A2` | 47 | **207** |
| **A' — same, but the 6 MCUs merge into 1 and the isolation hardware is deleted** | 105 move + 12 merge/delete | **77 signal nets** (§4) |

207 = **33 signal nets per cell x 6** + `/3V3` + `/5V` + `/DGND` + 6 x `/Mx_BATN`. The 33 per cell
are: 6 PWM, 3 CSA, 1 bus current, 1 bus voltage, 1 NTC, 4 SPI, nCS, nFAULT, ENABLE, MCU_ARM, NRST,
BOOT0, SWCLK, SWDIO, UART TX/RX, STATUS_LED, OSC_IN/OUT, 3V3A, 3V3I, ARM_ISO, BUS_DIV.

**19 of the 33 per-cell nets survive the merge; the other 14 are the MCU's own support nets**
(MCU_ARM, NRST, BOOT0, SWCLK, SWDIO, UART TX/RX, STATUS_LED, OSC_IN/OUT, 3V3I, 3V3A, ARM_ISO) and
cease to exist rather than crossing. That is where 150 of the 198 signal nets go — not into a wider
connector, out of the design. The arithmetic from 114 nets (19 x 6) to 77, with every step named:

| Step | Change | Nets |
|---|---|---|
| after the merge | 19 per cell x 6 | **114** |
| 6x -> 3x PWM mode | -18 | 96 |
| shared SPI (SCLK/MOSI/MISO once, not per cell) | -21 | 75 |
| nFAULT wired-OR (all six open drains, one line) | -5 | 70 |
| ENABLE shared (one `ARM_SAFE` authority) | -5 | 65 |
| one shared bus shunt + one redundant, not six | -4 | 61 |
| one shared bus-voltage divider, not six | -5 | 56 |
| 7th actuator channel, fully pinned (3 PWM + 3 CSA + NTC + nCS) | +8 | 64 |
| system: 4x BAT_P, 2x +3V3_REF, CAN, SWD, UART | +13 | **77** |

### 1.4 Three deletions and one merge, stated as decisions

1. **Merge the six cell MCUs into the supervisor.** This is the change that answers "6 of 7 MCUs
   stayed". It costs control-loop latency on six motors time-sliced by one core pair, which is a
   firmware question, not a hardware one — and the alternative (six MCUs on one shared 44.4 V bus,
   six independent PWM authorities) is worse than the latency.
2. **Delete 6 x `ISO6731` + 6 x `RFM-0505S`.** Forced by the owner's own premise. A shared power
   bus and six galvanically isolated domains cannot both exist; choosing the bus elects to delete
   them. 12 parts and 11.62 cm2 of power-board courtyard (MEASURED, `s3_partition.py`).
3. **Delete 6 x `TPS70933`.** With the cell MCU gone, the LDO's remaining jobs are the 3.3 V
   reference for the DRV8353's CSA and the gate's logic supply. One quiet reference on the control
   board serves all six VREF pins over 2 header pins, and makes all 31 analogue channels
   **ratiometric to the same reference**, which is strictly better than six independent LDOs.
4. **Delete 6 x LOCAL_SWD.** One MCU, one debug port.

Nothing else is deleted. The FETs, shunts, drivers, gate networks, bus capacitance, TVS, phase
connectors and thermistors are untouched.

### 1.5 The measurement question, answered precisely

"All the measurement stayed on the power board" is right about the last wave and it is a real
defect — but the fix is not to move the front ends, it is to move **the measurement system**:

| Measurement layer | Where | Why |
|---|---|---|
| Shunt, divider, thermistor | POWER | they are the sensor, and the sensor is a resistor |
| Amplifier (`INA296A2`, `DRV8353` CSA) | POWER, <=3 mm from its shunt | §3: 12.2x more induced error if it crosses |
| Anti-alias filter, ADC, oversampling, offset/gain calibration, cross-channel timing, telemetry | **CONTROL** | this is the part that measures |

And there is a fact that changes what "measurement" even means here, measured from the datasheets:

| Channel | Amplifier | Input offset | Referred to a 0.5 mOhm shunt | Grade |
|---|---|---|---|---|
| Phase current A/B/C (x18) | `DRV8353` internal CSA | **+/-3 mV** (SLVSDY6A p.15) | **+/-6.0 A** | protection / commutation grade |
| Bus current (x1..2) | `INA296A2` | **+/-10 uV** | **+/-0.02 A** | **the measurement-grade channel** |
| Bus voltage, 6 x NTC | divider / thermistor | — | — | monitoring grade |

**The 18 phase-current channels are protection-grade and always were** — the DRV8353's +/-3 mV
offset is +/-6 A whatever gain you select. The channel that carries the accuracy (bus current at
+/-0.02 A) is the `INA296A2`, and the divider/NTC channels are the pack telemetry. All of those
cross to the control board as conditioned outputs. So "measurement on the control board" is
satisfied where it matters — **31 analogue channels, 3 ADCs, all calibration** — and the honest
caveat is that **19 front-end amplifiers stay on the power board because moving them is measurably
worse** (§3).

---

## 2. The gate-drive split: PWM crosses, gate edges do not

### 2.1 The decision that halves the pin count: 6x PWM mode -> 3x

Today each cell drives the DRV8353 in **independent / 6x mode**: `M1_PWM_AH -> INHA`,
`M1_PWM_AL -> INLA`, and so on — **six PWM lines per motor, 36 in total**. Thirty-six PWM lines
will not fit in any 40-position header on their own.

TI SLVSDY6A p.7: *"Various PWM control modes (6x, 3x, 1x, and independent) are supported ... These
modes can decrease the number of outputs required of the controller for the motor driver PWM
control signals."* In 3x mode the three `INHx` inputs command the three half-bridges and the driver
inserts its own dead time (50/100/200/400 ns, `DEAD_TIME` register). On the 40-pin SPI part there
is **no `MODE` pin** (pin 27 is `SDO`; the `MODE` strap belongs to the 48-pin H/W variant), so
**6x -> 3x is a firmware register write, not a board change.**

`3 lines per motor x 6 + 3 for the 7th channel = 21 PWM lines`. That is what crosses.

*Open item, must be closed before layout:* the datasheet extract confirms 3x mode exists but the
extracted table does not state what the `INLx` pins must be tied to in 3x mode. Confirm in the
mode table (they are expected to be ignored / tied low). It is a strap, not an architecture change.

**One line per motor is not available.** 1x mode exists but is *"sensored trapezoidal ... using an
internal block commutation table"* — it needs Hall sensors this board does not have. So when the
brief says "the six PWM lines", the physical minimum is **six 3-line bundles**.

### 2.2 Slew of a PWM logic signal at the header vs a gate edge

| | PWM logic line | Gate edge | Ratio |
|---|---|---|---|
| Voltage swing | 3.3 V | 44.4 V (bus) / ~12 V (gate) | 13x |
| 10-90 edge | 4 ns (MCU GPIO) | 30 ns (`calc.json` tr/tf) | |
| **dV/dt** | **0.825 V/ns** | **1.480 V/ns** | 1.8x |
| Charge moved per edge | 16.5 pC (5 pF) | 168 nC gate charge | 10,000x |
| **dI/dt** | **1.03 mA/ns** | **5.14 A/ns** | **4,981x** |
| **Energy per edge** | **27 pJ** | **0.86 uJ** (gate) / **205 uJ** (commutation, `calc.json`) | **31,736x** / 7.6e6x |

dV/dt looks comparable — 1.8x — and that is the number that misleads people. The event that
matters is **dI/dt and energy**, and the PWM line is **5,000x lower in dI/dt and 31,000x lower in
energy** than the gate edge it commands. A gate edge is a 154 A commutation into a 12 nH loop; a
PWM line is a 4 mA charge into 5 pF.

### 2.3 Added inductance for the 21 PWM lines, and whether termination is needed

Using the header unit's own per-pin numbers (`hdr/calc.json`, GMR-refined): a 2.54 mm pin with an
**adjacent** return is **8.29 nH**, with a return on the far connector **17.5 nH**.

| Effect | Value | Verdict |
|---|---|---|
| L x dI/dt across the pin (adjacent return) | 8.29 nH x 1.03 mA/ns = **8.55 mV** of a 3.3 V swing = **0.26%** | harmless: the driver's `VIH` is **1.5 V max** (SLVSDY6A p.13), a 0.9 V margin |
| Same, far return (17.5 nH) | 18.0 mV = 0.55% | still harmless |
| L/R with a 47 ohm source | 8.29 nH / 47 ohm = **0.18 ns** | 4.4% of the 4 ns edge |
| Electrical length of the mated pin | 10 mm / 150 mm/ns = **0.067 ns** | 1.7% of the edge -> lumped element, no transmission-line study |
| Skew between any two PWM lines | <= **0.35 ns** | **0.18% of the DRV8353's 200 ns tPD** |
| **Added gate-loop inductance** | **0 nH** | no gate net crosses the header |

**Series termination: not required for signal integrity, and the reason is the numbers above** — the
pin is a lumped 8.29 nH into 5 pF with a 47 ohm source, so there is no reflection to damp and the
0.18 ns of L/R is 4% of an edge. **A 22 ohm series resistor at the MCU pin is still recommended,
for a different reason:** it doubles the edge to ~6 ns and cuts the charge coupled into the
neighbouring analogue bundle (next table). It costs 21 x $0.002 and buys margin in a 120-pin
connector where PWM and 54 mV-class analogue share the same plastic.

### 2.4 Crosstalk from a PWM line into an adjacent analogue line

Mutual capacitance between a header pin and its neighbour at 2.54 mm pitch with a 5 mm parallel run
and 0.2 mm to the plane: ~0.05 pF (conservative). Coupled current = C x dV/dt = **41 uA** peak.

| Mitigation | Error on the analogue channel |
|---|---|
| none (direct into the ADC) | 41 uA x 1 kohm = **41.2 mV — 3.8% of full scale, unacceptable** |
| 470 pF at the ADC | **0.351 mV (0.032%)** |
| **1 nF at the ADC (specified)** | **0.165 mV (0.015%)** |

So the anti-alias capacitor is not optional decoration: it is what makes a 120-position header
carrying PWM and analogue legal. It is required by §3's error budget and it doubles as the
anti-alias pole (1 kohm x 1 nF = 159 kHz, above the 25 kHz current loop and below the 1.1 MHz
amplifier bandwidth).

### 2.5 The answer, in one paragraph

The gate driver does not move — it stays within 3 mm of its FETs, so **the added gate-loop
inductance is 0 nH, a property of the partition rather than an assumption.** What crosses is 21 PWM
logic lines at 3.3 V / 4 ns / 4 mA. Their added inductance is 8.29 nH per line (17.5 nH worst
case), which costs 8.55 mV of logic margin, 0.18 ns of skew (0.18% of the driver's own propagation
delay) and 4.4% of an edge. **The header is harmless for PWM: it is 5,000x lower in dI/dt than the
gate edge it commands.** A 22 ohm series resistor is recommended but for crosstalk, not for
reflections; the mandatory part is the 1 nF at each ADC input.

---

## 3. The current-sense split: the Kelvin pair cannot cross, its output can

### 3.1 The two mechanisms, and which one actually decides it

The brief asks for the header contact resistance and the resulting offset error. **The contact
resistance is not the problem, and it is worth saying so with a number**, because pursuing it would
have produced the wrong architecture.

| Term | Kelvin pair crosses (amplifier on the control board) | Only the output crosses (amplifier on the power board) |
|---|---|---|
| Header contact resistance, 20 mOhm/pin x 2 pins | 40 mOhm x 40 uA of `INA296` input bias = **1.60 uV** (0.0029% FS) | 40 mOhm x 1 uA of ADC leakage = **0.04 uV** (0.000004% FS) |
| Contact thermal EMF, 2 junctions, ~20 C gradient | **40 uV = 0.040 mV** = **0.073%** of the 54.5 mV FS | 0.040 mV = **0.0037%** of the 1.09 V FS |
| Amplifier `Vos` (`INA296A` +/-10 uV) | 0.010 mV (0.018%) | 0.010 mV (0.001%) |
| **Magnetically induced, M x dI/dt** | **73.85 mV = 135.5%** | ~0 (see 2.4: 0.165 mV with the 1 nF) |
| **Full scale** | **54.5 mV** (0.5 mOhm x 109 A) | **1.09 V** (54.5 mV x gain 20) |
| **Worst-case total** | **73.90 mV = 136% FS** | **0.215 mV = 0.020% FS** |

**Contact resistance contributes 1.6 uV. The induced EMF contributes 73.85 mV — 46,000x more.**
The decision is made by mutual inductance alone, and the contact resistance is a rounding error in
both options.

Note also that the smaller full scale is itself a 20x penalty: 40 uV of thermal EMF is 0.073% of a
54.5 mV span but 0.0037% of a 1.09 V span. Moving the amplifier up costs you on two independent
axes at once.

### 3.2 The mutual-inductance number, with its units stated honestly

`hdr/calc.json` carries `didt_A_per_ns = 5.45` and `M_header_nH = 13.55`, and the sibling report
quotes **73.8 mV**. Those two are inconsistent by 1000x: 13.55 nH x 5.45 A/**ns** = **73.85 V**,
while 13.55 nH x 5.45 A/**us** = **73.85 mV**. The report's millivolt figure corresponds to the
microsecond convention; the JSON label says nanosecond. I am flagging the inconsistency rather than
inheriting it, because it matters for what the number is allowed to claim:

- The **physically plausible** edge rate at the shunt is the nanosecond one: the commutation loop is
  5-10 nH and 44.4 V, so di/dt = V/L ~ 4-9 A/ns, i.e. `calc.json` is right and the ~74 V answer is
  unphysical — which tells you the lumped-M model has simply run out of validity at that rate (a
  real 10 mm pin pair does not develop more volts than the bus).
- **The conclusion does not depend on which convention you take.** At the conservative 5.45 A/us
  the header pair is already **135% of full scale**. At 5.45 A/ns it is three orders of magnitude
  worse.
- **The one number that is convention-independent is the ratio**, because it is pure geometry:
  the header pair's loop is 203 mm2 against the on-board pair's 16.6 mm2, so
  **M_header / M_onboard = 12.21x**. Whatever the induced error is today, crossing the header
  multiplies it by 12.2.

And a secondary argument in the same direction: the `INA296A` has 150 dB of **DC** CMRR but no
PWM-rejection specification — TI sells the pin-compatible `INA241A` specifically for "enhanced PWM
rejection". On a board whose shunt sits in a 1.5 kV/us node, the amplifier's place is next to the
shunt, and 3 mm of trace is a better common-mode environment than 60 mm of trace plus two
2.54 mm contacts.

### 3.3 Recommendation

**The `INA296A2` stays on the power board, within 3 mm of the shunt, with its Kelvin pair on the
same layer as the shunt's terminals; only its single-ended output crosses the header.** The
output is a low-impedance 1.09 V full-scale signal behind a 1 kohm / 1 nF network, and it crosses
with **0.215 mV of total error = 0.020% of full scale** against **73.90 mV = 136%** for the
alternative.

The same rule applies to the 18 `DRV8353` CSA outputs, which are already amplifier outputs on a
part that cannot move. So **19 front-end amplifiers stay and 31 conditioned channels cross** — and
that is the answer to "all the measurement stayed on the power board": the front ends must, the
measurement system must not, and §1.5 says precisely which is which.
---

## 4. The complete pin map: 3 x 2x20 = 120 positions

### 4.1 Why three headers and not one

The agreed interface is one 2x20/40. The measured requirement is **77 signals + 43 grounds**. There
is no allocation of 40 positions that carries 77 signals: even with **zero** grounds — no return
path at all, which is not a board — 40 pins is 52% of the signal count. So the 2x20/40 is the unit
of construction, and the interface is **three of them**:

| Header | Signal pins | Ground pins | What it carries |
|---|---|---|---|
| H1 SYSTEM | 25 | 15 | 4x BAT_P (44.4 V), 2x +3V3_REF, CAN H/L, SWD (3), UART (2), DRV_ENABLE, nFAULT wired-OR, SPI (3), 7x nCS |
| H2 PWM | 31 | 9 | 21 PWM (7 channels x 3), 7x NTC, BUS_V, 2x BUS_I |
| H3 ANALOG | 21 | 19 | 21x DRV8353 CSA outputs, each with an adjacent return |
| **total** | **77** | **43** | 120 positions, **all allocated** |

Three 2x20 headers rather than one 2x40: a 2x40 is 101.6 mm of lever arm under vibration, a single
unseat takes out everything, and three 6.09 x 51.81 mm footprints pack onto a 105 x 60 board in
18.3 mm of width. Cost is the same part three times: **3 x $0.2758 = $0.83 per board pair** (LCSC
C25503140 male + C25503128 female, the pair the cost unit already priced).

### 4.2 Ground accounting: 43 pins, and why that number

| Class | Signal pins | Grounds | Rule | Why that is enough |
|---|---|---|---|---|
| Analogue current, H3 | 21 | 19 | 1 return per channel, same row | the return is there for **loop area**, not current: an ADC input draws <=10 uA, so 40 mOhm of contact gives 0.4 uV. Two spare channels (the 7th channel's B and C phases) share the last two returns |
| PWM, H2 | 21 | 7 | 1 per 3 lines | each 3-line bundle has a return behind it, keeping the loop under 5 mm at 2.54 mm pitch |
| Housekeeping analogue, H2 (7x NTC, BUS_V, 2x BUS_I) | 10 | 2 | shared | 100 uA-class excitation and ADC-only loads; the pair brackets the NTC group and the `BUS_I` pair sits next to one of them |
| Digital + comms, H1 | 25 | 15 | 1 per 1.7, plus a dedicated 4-pin guard column | the column is the 44.4 V barrier, and the rest halves every signal's return loop |
| **total** | **77** | **43** | 1 per 1.79 signals | the control board's total return is <=0.5 A, i.e. **<=12 mA per ground pin** |

**43 grounds is 56% of the interface and it is the cheapest part of it.** Ground pins cost the same
as signal pins and buy the return path that the analogue bundle cannot live without. The last wave
spent 19 of its 40 positions on grounds for the same reason; the ratio here is deliberately similar
even though the signal count has tripled.

### 4.3 What does not cross, and the two things that stopped needing to

- **No gate net** (0 of 36), no phase node, no shunt Kelvin pair, no busbar, no bus capacitance.
- **No 5 V rail.** The `DRV8353` generates `DVDD` (5 V, up to 10 mA) internally, and its `VIH` is
  1.5 V, so 3.3 V logic drives it directly. The six `RFM-0505S` that used to need 5 V are deleted.
  This is a pin saving the last wave could not have: **5 V does not cross at all.**
- **No per-cell 3.3 V.** One `+3V3_REF` (2 pins) is the BEC output and the reference for all six
  CSA banks and all three ADCs, which makes the whole analogue chain ratiometric. The six
  `TPS70933` are deleted.
- **Six bus-current amplifiers became two.** A shared bus means one shunt, not six. The other five
  pins per cell buy the 7th channel and the 19 analogue returns.

### 4.4 The pin map, every pin


#### H1 — SYSTEM: bus inlet, BEC output, comms, driver digital

Pins 1-8 are the 44.4 V inlet and a **4-pin ground guard column**. No logic pin is closer than 5.08 mm to a 44.4 V pin, which is 50x the IPC-2221B external-creepage minimum for 31-50 V (0.1 mm) and above the 0.5 mm I would design to at 1.5 kV/us.

| pin | net | dir | mA/pin | class | note |
|---:|---|---|---:|---|---|
| 1 | `BAT_P_1` | in | 120.2 | power | 44.4 V bus -> BEC input |
| 2 | `BAT_P_2` | in | 120.2 | power |  |
| 3 | `BAT_P_3` | in | 120.2 | power |  |
| 4 | `BAT_P_4` | in | 120.2 | power |  |
| 5 | `DGND` | - | 0 | gnd | guard column: 44.4 V -> logic |
| 6 | `DGND` | - | 0 | gnd | guard column |
| 7 | `DGND` | - | 0 | gnd | guard column |
| 8 | `DGND` | - | 0 | gnd | guard column |
| 9 | `+3V3_REF_A` | out | 13 | power | BEC output = DRV8353 VREF + ADC VREF |
| 10 | `DGND` | - | 0 | gnd |  |
| 11 | `+3V3_REF_B` | out | 13 | power | 2nd contact, ratiometric reference |
| 12 | `DGND` | - | 0 | gnd |  |
| 13 | `CAN_H` | io | 70 | comms | CAN-FD 5 Mbit/s |
| 14 | `CAN_L` | io | 70 | comms |  |
| 15 | `DGND` | - | 0 | gnd |  |
| 16 | `DGND` | - | 0 | gnd |  |
| 17 | `SWDIO` | io | 0.5 | comms |  |
| 18 | `SWCLK` | in | 0.5 | comms |  |
| 19 | `NRST` | in | 0.5 | comms |  |
| 20 | `DGND` | - | 0 | gnd |  |
| 21 | `UART_TX` | out | 0.5 | comms | telemetry / log |
| 22 | `UART_RX` | in | 0.5 | comms |  |
| 23 | `DGND` | - | 0 | gnd |  |
| 24 | `DGND` | - | 0 | gnd |  |
| 25 | `DRV_ENABLE` | out | 0.42 | digital | fan-out to 6 x DRV8353 ENABLE |
| 26 | `nFAULT_ALL` | in | 0.33 | digital | 6 open-drain nFAULT, wired-OR |
| 27 | `DGND` | - | 0 | gnd |  |
| 28 | `DGND` | - | 0 | gnd |  |
| 29 | `SPI_SCLK` | out | 0.07 | digital | shared to 6 drivers |
| 30 | `SPI_MOSI` | out | 0.07 | digital |  |
| 31 | `SPI_MISO` | in | 0.07 | digital |  |
| 32 | `DGND` | - | 0 | gnd |  |
| 33 | `nCS_M1` | out | 0.07 | digital |  |
| 34 | `nCS_M2` | out | 0.07 | digital |  |
| 35 | `nCS_M3` | out | 0.07 | digital |  |
| 36 | `nCS_M4` | out | 0.07 | digital |  |
| 37 | `nCS_M5` | out | 0.07 | digital |  |
| 38 | `nCS_M6` | out | 0.07 | digital |  |
| 39 | `nCS_M7` | out | 0.07 | digital | 7th channel spare |
| 40 | `DGND` | - | 0 | gnd |  |


#### H2 — PWM: 7 channels x 3 lines + housekeeping analogue

Each PWM bundle is 3 lines with a return behind it. `BUS_I_A/B` are the two measurement-grade channels (INA296A2, +/-10 uV = +/-0.02 A) and they sit next to a return, not next to PWM.

| pin | net | dir | mA/pin | class | note |
|---:|---|---|---:|---|---|
| 1 | `PWM_M1_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 2 | `PWM_M1_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 3 | `PWM_M1_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 4 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 5 | `PWM_M2_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 6 | `PWM_M2_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 7 | `PWM_M2_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 8 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 9 | `PWM_M3_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 10 | `PWM_M3_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 11 | `PWM_M3_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 12 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 13 | `PWM_M4_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 14 | `PWM_M4_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 15 | `PWM_M4_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 16 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 17 | `PWM_M5_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 18 | `PWM_M5_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 19 | `PWM_M5_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 20 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 21 | `PWM_M6_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 22 | `PWM_M6_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 23 | `PWM_M6_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 24 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 25 | `PWM_M7_A` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 26 | `PWM_M7_B` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 27 | `PWM_M7_C` | out | 2.13 | pwm | 3x PWM mode: one line per half-bridge |
| 28 | `DGND` | - | 0 | gnd | one return per 3 PWM lines |
| 29 | `NTC_M1` | in | 0.1 | analog |  |
| 30 | `DGND` | - | 0 | gnd |  |
| 31 | `NTC_M2` | in | 0.1 | analog |  |
| 32 | `NTC_M3` | in | 0.1 | analog |  |
| 33 | `NTC_M4` | in | 0.1 | analog |  |
| 34 | `DGND` | - | 0 | gnd |  |
| 35 | `NTC_M5` | in | 0.1 | analog |  |
| 36 | `NTC_M6` | in | 0.1 | analog |  |
| 37 | `NTC_M7` | in | 0.1 | analog | 7th channel spare |
| 38 | `BUS_V` | in | 0.01 | analog | 44.4 V divider, one shared bus |
| 39 | `BUS_I_A` | in | 0.01 | analog | INA296A2 output, 1.09 V full scale |
| 40 | `BUS_I_B` | in | 0.01 | analog | 2nd bus shunt, redundant channel |


#### H3 — ANALOG: 21 current channels, each with its own return

**One analogue pin, one return, in the same row.** This is the whole reason the analogue bundle is its own header: a 54.5 mV shunt signal riding on a shared return is what the last wave measured at 135% of full scale.

| pin | net | dir | mA/pin | class | note |
|---:|---|---|---:|---|---|
| 1 | `CSA_M1_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 2 | `AGND` | - | 0 | gnd | adjacent return |
| 3 | `CSA_M1_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 4 | `AGND` | - | 0 | gnd | adjacent return |
| 5 | `CSA_M1_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 6 | `AGND` | - | 0 | gnd | adjacent return |
| 7 | `CSA_M2_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 8 | `AGND` | - | 0 | gnd | adjacent return |
| 9 | `CSA_M2_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 10 | `AGND` | - | 0 | gnd | adjacent return |
| 11 | `CSA_M2_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 12 | `AGND` | - | 0 | gnd | adjacent return |
| 13 | `CSA_M3_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 14 | `AGND` | - | 0 | gnd | adjacent return |
| 15 | `CSA_M3_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 16 | `AGND` | - | 0 | gnd | adjacent return |
| 17 | `CSA_M3_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 18 | `AGND` | - | 0 | gnd | adjacent return |
| 19 | `CSA_M4_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 20 | `AGND` | - | 0 | gnd | adjacent return |
| 21 | `CSA_M4_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 22 | `AGND` | - | 0 | gnd | adjacent return |
| 23 | `CSA_M4_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 24 | `AGND` | - | 0 | gnd | adjacent return |
| 25 | `CSA_M5_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 26 | `AGND` | - | 0 | gnd | adjacent return |
| 27 | `CSA_M5_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 28 | `AGND` | - | 0 | gnd | adjacent return |
| 29 | `CSA_M5_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 30 | `AGND` | - | 0 | gnd | adjacent return |
| 31 | `CSA_M6_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 32 | `AGND` | - | 0 | gnd | adjacent return |
| 33 | `CSA_M6_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 34 | `AGND` | - | 0 | gnd | adjacent return |
| 35 | `CSA_M6_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 36 | `AGND` | - | 0 | gnd | adjacent return |
| 37 | `CSA_M7_A` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 38 | `AGND` | - | 0 | gnd | adjacent return |
| 39 | `CSA_M7_B` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |
| 40 | `CSA_M7_C` | in | 0.01 | analog | DRV8353 SOx output, 0-3.3 V, 1 kOhm + 1 nF at the ADC |

---

## 5. Pin-by-pin current check against the 3 A contact rating

2.54 mm header contacts are rated **3 A per contact** (the LCSC 2541 series pair the cost unit
priced is specified at 3 A/contact; the last wave derated to 1 A in its budget). Every pin's
design maximum, from the load model in `s4_numbers.py` (BEC input computed from the control board's
own 7.26 W at 85% efficiency, then x2.5 for margin):

| Net class | Pins | mA per pin | Margin vs 3 A | Carries |
|---|---|---|---|---|
| `BAT_P` (44.4 V) | 4 | **120.2** | **25x** | BEC input, 192 mA typ / 481 mA worst over 4 pins |
| `+3V3_REF` | 2 | 13.0 | 231x | 6x `INA296` (2.5 mA each) + 6x `DRV8353` VREF taps |
| `CAN_H` / `CAN_L` | 2 | 70.0 | 43x | `TCAN3413` driver peak |
| `SWDIO`/`SWCLK`/`NRST` | 3 | 0.5 | 6,000x | debug only, never in flight |
| `UART_TX`/`RX` | 2 | 0.5 | 6,000x | telemetry |
| `DRV_ENABLE` | 1 | 0.42 | 7,143x | fan-out to 6 drivers, 70 uA each |
| `nFAULT_ALL` | 1 | 0.33 | 9,091x | 6 open drains + one pull-up |
| `SPI_SCLK`/`MOSI`/`MISO` | 3 | 0.07 | 42,857x | `IIH` 70 uA max |
| `nCS` x7 | 7 | 0.07 | 42,857x | same |
| **PWM** | 21 | **2.13** | **1,407x** | 4.1 mA of 5 pF charge + 70 uA `IIH` |
| CSA analogue | 21 | 0.010 | 300,000x | ADC leakage + sample charge |
| NTC | 7 | 0.10 | 30,000x | 100 uA excitation |
| `BUS_I` x2, `BUS_V` | 3 | 0.010 | 300,000x | ADC input |
| **Grounds** | 43 | <=12 | >=250x | total control-board return <=0.5 A |

**Worst single pin: 120.2 mA = 4.0% of the 3 A rating. Zero pins exceed 3 A. Nothing needs to be
paralleled for ampacity, and nothing needs a heavier contact.**

At 120 mA through 20 mOhm of contact resistance the pin drops **2.4 mV** and dissipates
**0.29 mW**. The four `BAT_P` contacts are not there for current — one would carry it — they are
there because **a single bad contact should degrade the BEC input by 25%, not 100%**, and because
splitting the 44.4 V across two rows makes the guard column possible without putting a live pin
against a logic pin.

**Equally important is what must never cross**, and it is the reason the currents look so low:

| Current | Value | Route |
|---|---|---|
| Phase current | 109 A RMS, 154 A peak | busbar / M5 phase lug, **never a 2.54 mm pin** |
| Shared bus current | 6 x 63 A = 378 A at 600 km/h, 654 A at 720 | busbar and battery lug |
| Shunt-level differential | 54.5 mV at 109 A | 3 mm of trace on the power board (§3) |

A 3 A header carrying 4% of its rating is the signature of a correct split: **the high current
never gets near the connector, so the connector can be chosen for pin count and creepage instead of
ampacity.** That is the whole architectural prize, and it is why 120 pins at $0.83 is affordable
where 6 AWG cable would not be.

---

## 6. Control-board area, layer count, and whether it still stacks

### 6.1 Area, from measured courtyards

Every number below comes from a measured footprint courtyard (`s3_partition.py` on a copy of the
real board, and the last wave's `07_census.json` for the two blocks this netlist lacks):

| Item | Courtyard | Source |
|---|---|---|
| Supervisor block (70 fps: `RP2354B`, CAN-FD, USB, watchdog, crystals) | 7.72 cm2 | MEASURED, `esc-split-control/07_census.json` |
| BEC block (35 fps: 2x `LM5164`, `AP2112K`, TVS, inductors) | 9.93 cm2 | same |
| 6 x `STM32G431CBT6` (which merge into the one MCU) | 5.48 cm2 | MEASURED here |
| 6 x `SN74LVC1G08` (merge into 1 gate) | 0.74 cm2 | MEASURED here |
| **parts that move today** | **23.87 cm2** | |
| 3 x 16-bit 8-channel simultaneous ADC, TQFP-64 (1.49 cm2 each) | 4.47 cm2 | added |
| 31 analogue channels x (2R + 1C) 0402 = 93 parts | 0.60 cm2 | added |
| ADC decoupling + reference bypass | 0.06 cm2 | added |
| **control-board parts** | **29.00 cm2** | |
| 3 x 2x20 vertical header courtyard (6.09 x 51.81 mm, read from the KiCad library) | 9.47 cm2 | added |
| USB-C edge keepout + standoffs | 4.00 cm2 | as the last wave budgeted |
| **board area at the incumbent board's achieved packing (0.59)** | **62.6 cm2** | -> **105 x 60 mm = 63.0 cm2** |
| board area at the last wave's conservative packing (0.45) | 77.9 cm2 | -> 110 x 71 mm = 78.1 cm2 |

**Control board = 105 x 60 mm = 63.0 cm2.** The comparable statement is: **the control board is
63.0 cm2 against a power board of 169.7 cm2, i.e. 37% of it**, and the two-board total is
232.7 cm2 against 382.71 cm2 today = **-39%**, which lands inside the -35% to -50% band the area
wave told us to quote.

I quote the 0.45 case because it changes nothing structural: **78.1 cm2 still fits inside the power
board**, so "no overhang" does not depend on the packing assumption. That is the point of quoting
both ends.

### 6.2 Layers: 2, single-sided, HDI-free — with the analogue caveat stated

| Requirement | Verdict |
|---|---|
| **HDI-free** | Yes. The finest feature is the 0.5 mm pitch TQFP-64 fanout, which is 0.25 mm trace/space at the escape — standard 2-layer capability, no microvias, no laser drilling |
| **Single-sided (0 components on B.Cu)** | Yes, and it is forced: the bottom face is what looks at the power board and the heatsink |
| **2-layer** | **Yes, as the design intent** — and the single-sided requirement is what makes it defensible: with every part on top, **B.Cu is one unbroken ground plane with no bottom routing at all**, which is the correct topology for a 31-channel analogue front end (every trace is a microstrip over a solid plane) |
| The risk | 16-bit, 500 kSPS, 31 analogue channels on one routing layer. The analogue and PWM bundles must be physically separated on F.Cu, and the 19 analogue returns must reach the header without crossing the digital section |
| The escape hatch, if first-article noise fails | **4-layer (sig/gnd/pwr/sig), +$43** per the cost unit's own delta. Re-spinning the control board does **not** touch the power board, so this decision can legitimately be deferred to measurement rather than guessed now |

The previous wave's four arguments for 2 layers all still hold (no isolated DC-DC on the board, USB
is Full-Speed, CAN-FD is not impedance-controlled, no BGA), and the new ADC cluster is the one item
that could overrule them. I would build 2-layer, measure the noise floor, and let the data decide —
because the re-spin is a $43 line on a board that is 1-2% of the total.

### 6.3 Does it still stack? Geometric yes, vertical no — and my change makes one defect worse

**Footprint: yes.** 105 x 60 mm inside the sibling's 133.4 x 88.6 mm power-path core leaves **28.4
mm in x and 28.6 mm in y**; inside the area wave's 169.7 cm2 board (scaled to the same aspect,
~160 x 106 mm) it is not close. No overhang, all three header columns land on the power board's top
face.

**Vertical: the three defects the last wave found are untouched by this work, and one gets worse.**

| Defect (last wave) | Status after this wave |
|---|---|
| (a) the 28.55 mm gap needs 31.15 mm of reach; a TSW-15 gives 15.75 mm, **15.4 mm short** | **unchanged** — the gap is set by the heatsink, not by the pin split |
| (b) the header at x 131.5-136.6 mm **overlaps a 130 mm sink by 2.7 mm** | **worse: three header columns instead of one**, so there are three strips to keep clear of the sink edge instead of one. The sink must shrink to <=100 mm, or the columns move inboard |
| (c) six 31-35.5 mm capacitors pierce the gap | **unchanged**, and the clear window shrinks: a 63 cm2 control board covers **53%** of a 118 cm2 power board (37% of a 170 cm2 one), so the six 18 mm cans must be relocated to the uncovered perimeter rather than merely avoided locally |

Two things I can say that help the geometry unit rather than just handing the problem back:

1. **The top face is now nearly empty of components.** With the FETs flipped to B.Cu for top-side
   cooling (the mech wave's recommendation) and the six per-cell 2x12 headers deleted by this
   split, the power board's top face carries only the six `DRV8353` (2.3 cm2 total), the six
   `INA296`, the shunts, the cans and three header strips. The obsolete 6 x `Conn_02x12_Pin` are
   **144 positions of connector that no longer exist** — that is free top-face real estate where the
   header columns need to go.
2. **+9.47 cm2 of male header field lands on the power board** (three 2x20 mate footprints, which
   the area wave's 169.7 cm2 did not include when it assumed 2x15/30). The power board should be
   read as **169.7 cm2 + ~9.5 cm2 of interface**, or the interface area will appear as an overrun
   later.

---

## 7. Verdict, and what is still open

### 7.1 Against the brief, point by point

| The brief asked | Answer |
|---|---|
| 1. Every block assigned with a reason | §1.2, 22 blocks. MCU 7 -> 1 and that 1 is on the control board; measurement system, BEC, CAN, SWD, telemetry, crystals, watchdog on the control board; FETs, shunts, gate-stage, bus capacitance, power connector and the 19 front-end amplifiers on the power board |
| 2. Resolve the gate-drive split | §2. Driver stays, **0 nH** of added gate loop, 21 PWM lines at **8.29 nH each**, 8.55 mV of logic margin, 0.18 ns skew, **no termination needed for SI**, 22 ohm recommended for crosstalk |
| 3. Current-sense split, quantified | §3. Contact R is **1.6 uV (0.003%)**; the induced EMF is **73.85 mV (135%)**. Recommendation: amplifier stays 3 mm from the shunt, output crosses: **0.215 mV = 0.020% FS** vs **136% FS** |
| 4. Complete 2x20/40 pinout | §4. **The interface needs 3 x 2x20 = 120 positions** (77 signal + 43 ground); all 120 are allocated, including a fully-pinned 7th channel (3 PWM + 3 CSA + NTC + nCS) |
| 5. Pin-by-pin current vs 3 A | §5. Worst pin **120.2 mA = 4.0%**; zero pins over 3 A; nothing paralleled for ampacity |
| 6. New control-board area, layers, stack | §6. **63.0 cm2 (105 x 60 mm), 2-layer, single-sided, HDI-free**; fits inside both power-board outlines; **the vertical stack defects are unchanged and (b) is worse** |

### 7.2 What changed relative to the last wave

| | Last wave | This wave |
|---|---|---|
| MCUs on the control board | 1 of 7 | **1 of 1** (six cell MCUs merged, not moved) |
| Measurement on the control board | none (front ends only, on the power board) | **31 analogue channels + 3 ADCs + all calibration**; 19 front ends stay, with the reason quantified |
| Interface | 2x15 / 30 positions, 15 nets | **3 x 2x20 / 120 positions, 77 signals** |
| Control board | 40.0 cm2 | **63.0 cm2** |
| Parts deleted, not moved | 0 | **6 `ISO6731`, 6 `RFM-0505S`, 6 `TPS70933`, 6 LOCAL_SWD** |
| Two-board total area | 118 + 40 = 158 cm2 | 63 + 118 = **181 cm2 (-53%)** on the core footprint, or 63 + 169.7 = **232.7 cm2 (-39%)** on the area wave's full power board |

### 7.3 Open items, in the order they can hurt

1. **The 40-position header is not the interface.** If the 2x20/40 is a hard constraint from the
   owner rather than an estimate, then the only architectures that fit it are the ones that keep
   the six cell MCUs (the last wave's answer) — and that is the split the owner rejected. **This is
   the decision to put in front of him: 120 positions, or the six MCUs come back.** The cost of
   deciding for 120 is $1.65 more in headers and 9.5 cm2 on each board.
2. **The three ADC parts and their ~$45-66 are new money.** The cost wave's $436-496 total had $240
   of headroom at the low end, so it passes, but the cost line must be re-run with the ADC, the 93
   filter passives and the third header — that is the cost unit's call, not mine.
3. **The header's mated stack height is still unverified** (open in the last wave, still open): the
   LCSC drawing returns HTML to this host. It must be >=10 mm and the post must reach 12.6 mm.
4. **3x-mode `INLx` handling** must be confirmed in the DRV8353 mode table before layout (expected:
   ignored / tie low). It is a strap, not an architecture change.
5. **`INA296` input bias current is an assumed 40 uA** in the 1.6 uV contact-resistance term. The
   term is 1.6 uV at 40 uA and still under 40 uV at 1 mA, so the conclusion survives any plausible
   value — but the number should be taken from the datasheet before it is quoted again.

### 7.4 One paragraph for the owner

The split you asked for is buildable, and the parts you named do land where you said: the shunts,
the FETs and the shared power bus stay on the main board, and the measurement, the BEC and the MCU
come up to the control board. Two things had to change to make it real. First, the six per-motor
microcontrollers had to become one, because a shared bus means one ground and one authority —
that is what actually puts "the MCU" on the control board instead of six of seven. Second, the
connector has to be **three 2x20 headers, not one**: the interface is 77 signals and 43 grounds,
and one 40-pin header is a third of it. That costs $1.65 and about 9.5 cm2 on each board, which is
the cheapest part of this whole design. What I could not fix is the vertical stack: the heatsink
overlap and the six 35 mm capacitors are still there, and three header columns instead of one makes
the overlap worse rather than better — so the sink has to shrink to about 100 mm or the capacitors
have to move to the uncovered edge.

---

## Appendix A — provenance: MEASURED / CALCULATED / PUBLISHED / ASSUMED

The discipline from the programme's own evidence rules: every number states which it is.

| Claim | Class | How it was obtained |
|---|---|---|
| 599 netlist components, 563 nets, 7 sheets | MEASURED | `s1_blocks.py` on `hdr/net_dump.json` (parsed `esc.net`) |
| 94 parts per cell, 6 cells, 35 BEC parts | MEASURED | same |
| 607 footprints, 728.16 cm2 outline (repo board), 240.07 cm2 total courtyard | MEASURED | `s3_partition.py`, `pcbnew` 9.0.7 on `esc_copy.kicad_pcb` |
| 6 x `STM32G431` = 5.48 cm2, 6 x `SN74LVC1G08` = 0.74 cm2 | MEASURED | same, courtyard polygons, nm^2/1e12 |
| 12.62 cm2 of power-board courtyard deleted (isolators + isolated DC-DC) | MEASURED | same (`DELETE` bucket: 7.49 + 4.13) |
| 75.21 cm2 of M5 lugs/cell connectors (the shared bus's prize) | MEASURED | same |
| Supervisor 7.72 cm2 / BEC 9.93 cm2 | MEASURED (last wave) | `esc-split-control/07_census.json`; this netlist omits those 105 parts |
| **207 crossing nets** for the literal owner split; 33 signal nets per cell | MEASURED | `s2_cut.py` (pad/net graph, both sides of every net) |
| 77 signals + 43 grounds = 120 positions | CALCULATED + ASSERTED | `s5_pinmap.py`, which asserts 40 pins per header, no duplicate net, and recomputes every count |
| `DRV8353` 6x/3x/1x modes; `VIH` 1.5 V; `IIH` 70 uA; `RPD` 100 kOhm; `tPD` 200 ns; `DVDD` 5 V/10 mA | PUBLISHED | TI SLVSDY6A, pp.7, 13, 14, 27, 30 — text extract in `esc-split-control/hdr/ds/drv8353.txt` |
| `DRV8353` CSA gain 5/10/20/40, `VOFF` +/-3 mV, `VDIFF` +/-0.3 V, `VLINEAR` 0.25..VREF-0.25 | PUBLISHED | same, p.15 |
| `INA296A2` = 20 V/V, `Vos` +/-10 uV, gain error 0.01%, 2.5 mA, 1.1 MHz, CMRR 166 dB typ | PUBLISHED | ti.com/product/INA296A (fetched this session), gain table confirmed |
| `INA296` input bias current **40 uA** | **ASSUMED** | not read from the datasheet; the contact-resistance term is 1.6 uV at 40 uA and <40 uV even at 1 mA, so the conclusion is insensitive — but it must be replaced with the real figure |
| Header per-pin inductance 8.29 nH (adjacent return) / 17.5 nH (far) | PUBLISHED-in-programme | `esc-split-control/hdr/calc.json`, GMR-refined |
| Shunt mutual inductance 1.11 nH on-board / 13.55 nH through a header; 5.45 A/us | PUBLISHED-in-programme, **units corrected here** | same file: the JSON label says `A_per_ns` while the 73.8 mV result implies `A_per_us`. Both conventions reported in §3.2 |
| 2.54 mm contact resistance 20 mOhm max | ASSUMED (datasheet-class) | typical spec for gold-flashed 2.54 mm headers (10 mOhm typ, 20 mOhm max). The term it feeds is 1.6 uV, so the value is not load-bearing |
| 2 x 20 header courtyard 6.09 x 51.81 mm | MEASURED | read from `PinHeader_2x20_P2.54mm_Vertical.kicad_mod`, KiCad 9 official library |
| Control-board loads 1.376 A @ 5 V + 0.115 A @ 3V3, 7.26 W, 192 mA at 44.4 V | CALCULATED | `s4_numbers.py`, itemised per load; 85% BEC efficiency assumed |
| 3 ADC x 45-66 USD, +$43 for a 4-layer control board | ESTIMATE | ADC price is a distributor-class estimate, not quoted; the $43 delta is the cost unit's own 2L->4L number |
| Board packings 0.59 / 0.45 | MEASURED (0.59: 226.26/382.71 on the incumbent) / PROGRAMME TARGET (0.45) | the report quotes both, and the "does it stack" answer is the same at both |
| 133.4 x 88.6 mm = 118.2 cm2 power-board core; 169.7 cm2 area-wave power board | MEASURED (last wave) | `esc-split-control` §4 and `esc-split-power` |
| The three stack defects (31.15 mm reach, 2.7 mm sink overlap, 31-35.5 mm caps) | PUBLISHED-in-programme, unchanged | `esc-split-control` §5 + `esc-split-power`; re-examined in §6.3, not re-derived |

Reproduce everything with:

```
C:\Program Files\Python312\python.exe s1_blocks.py      # census
C:\Program Files\Python312\python.exe s2_cut.py         # the 207-net cut
C:\Program Files\KiCad\9.0\bin\python.exe s3_partition.py   # courtyards on a copy
C:\Program Files\Python312\python.exe s4_numbers.py     # every electrical number
C:\Program Files\Python312\python.exe s5_pinmap.py      # the 120-pin map + assertions
C:\Program Files\Python312\python.exe s6_report_s4.py   # the §4 tables
```

Artefacts in this directory: `s3_partition.json`, `s4_numbers.json`, `pinmap.json`,
`pinmap.md` (stand-alone pin map), `esc_copy.kicad_pcb` (the read-only copy every measurement ran
against).
