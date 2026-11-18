# Code-SDR — the IF2 varactor trim, as a real circuit

Wave 2, item Code-SDR: pick the one viable varactor and design its bias.

Repo `repos/Code-SDR`, branch `work/2026-11-11`, HEAD `6fbc004` (clean tree).
Read-only: nothing was committed, no netlist file in the repo was modified. All
outputs are in `evidence/w2-cs-varcap-real/`.

**Verdict.** One part works here: **Skyworks SMV1236-079LF**, used four times,
one bridged across each of the four nodes of the existing 26.25 MHz
differential anti-alias ladder. Biased 0.3–3.3 V of reverse voltage off a
trimpot on `+3V3_ANA`, it delivers a **1.293 : 1 node-capacitance scale** against
the **1.169 : 1** wave-1 requirement (+10.6 % margin) and places the −3 dB
corner anywhere from **44.63 to 51.05 MHz**, which contains the required
46.25–50.00 MHz window at both edges. It buys a factory alignment that absorbs
4.2 MHz of worst-case passive/varactor spread. It does **not** buy LO
correction and it should not be sold as temperature compensation.

---

## 1. The node being trimmed, verified rather than assumed

The IF2 ladder on `sheets/08_if_chain.kicad_sch` is a differential LC low-pass
between the LT5560 second mixer (U73) and the AD8351 IF amplifier (U74):

    IF2_P/N --L87/88 200nH-- F1 --L89/90 360nH-- F2 --L91/92 390nH-- F3
            --L93/94 360nH-- F4 --L95/96 200nH-- IF2_LPF_P/N
    bridge caps: C262 51 pF (F1), C264 56 pF (F2), C266 56 pF (F3), C268 51 pF (F4)

Verified from a netlist I exported with KiCad 9.0.7
(`kicad-cli sch export netlist --format kicadsexpr`, 373 components /
264 nets, saved as `Code-SDR-V2.net`) and matching
`hardware/redesign/RF_ANALYSIS.md:45-49`. The four "Differential anti-alias
ladder shunt capacitor" symbols are at `08_if_chain.kicad_sch:5004, 5074, 5144,
5214`.

Three facts from the netlist decide the whole bias design:

1. **The ladder sits at +3.3 V DC.** `IF2_P` is `{L85 2.2uH, L87 200nH,
   R79 100R, U73.5 OUT-}` and `L85.1` is on `+3V3_ANA`; likewise `L86` for
   `IF2_N`. Every ladder node is therefore at the `+3V3_ANA` potential
   (LT5560 VCC is the same rail, `U73.7`).
2. **`C254/C255` (100 nF) are the only DC break**, and they are at the far end
   into `U74.3/4` (AD8351). So the trim cannot be biased from a node — the
   nodes are all one DC potential.
3. **`R79` and `R80` are 100 Ω across the pair** at the input and output, so the
   differential port impedance is 100 Ω.

IF2 is fixed at 26.25 MHz and the ADC (AD9215, 100 MSPS) has a 50 MHz Nyquist:
`evidence/notrun-gates/raw/codesdr_freqplan_check.log:13` ("ADC fs=100 MSPS ->
Nyquist 50.0 MHz; IF2 26.25 MHz below Nyquist"), confirmed by the
`FREQUENCY_PLAN.csv` rows (`second_lo_mhz = 2400`, `second_if_mhz = 26.25`,
`useful_bw_mhz = 40`).

The 40 MHz useful band therefore spans 6.25–46.25 MHz and the first alias edge
is 53.75 MHz (`RF_ANALYSIS.md:52`). The corner must be high enough not to eat
46.25 MHz and low enough to reject at 50 MHz. Stock it lands at **47.90 MHz**
(−3.5 dB at 48 MHz, `FILTER_RESPONSE.csv`).

## 2. The model, and why its numbers can be trusted

`tools/if2_ladder.py` is an exact nodal solve of the differential ladder
(series elements are the two legs in series, i.e. 2·L per section; shunt
elements are the bridge capacitors; 100 Ω differential ports; LT5560 output
1200 Ω ∥ 0.7 pF and AD8351 input 5000 Ω ∥ 0.8 pF per `RF_ANALYSIS.md:71-78`).

`tools/validate_model.py` reproduces the repo's own `FILTER_RESPONSE.csv`
"ideal matched" column to **0.001 dB worst case** from 6.25 to 100 MHz, so the
solver is not an approximation of the design - it is the design. (The
"finite ports" column is not reproduced to the same accuracy because that
column is normalised to a Norton-source reference; the trim work below uses the
validated ideal-port model and states its own normalisation, −3 dB relative to
the 26.25 MHz response.)

## 3. Choosing the part

The requirement is a capacitance *scale* of the ladder. Measured sensitivities
(`tools/scaling_law.py`, +1 pF at each node):

| node | C | corner shift per +1 pF | exponent S = dln fc/dln C |
|---|---|---|---|
| F1 | 51 pF | −0.058 MHz | −0.062 |
| F2 | 56 pF | −0.168 MHz | −0.198 |
| F3 | 56 pF | −0.170 MHz | −0.202 |
| F4 | 51 pF | −0.063 MHz | −0.067 |

Scaling all four nodes together gives **S = −0.523**, i.e. fc ∝ C^−0.523, and
the capacitance ratio needed to move the corner over 46.25→50.00 MHz is
**k(46.25)/k(50.00) = 1.069/0.921 = 1.161**, which agrees with wave-1's
**1.169:1** (`evidence/cs-varcap/REPORT.md:84`, point P4_aa) to 0.7 %. The
1.169 figure is therefore independently confirmed - and it is a *scale across the
ladder*, not a ratio at one component.

That number is what rejects the obvious instinct ("pick a small varactor").
A 1.5 pF part (SMV1231) moves a 56 pF node by 2.1 % and the corner by 0.51 MHz
(47.39–47.90 MHz) - against the 4.4 % / 2.1 MHz of correction the window needs.
The trim needs a part whose capacitance *change* is a large fraction of the node
capacitance.

Datasheet used: **Skyworks SMV123x Series, 200058AB, May 7 2026**
(`datasheets/SMV123x_skyworks_F9C9BC.pdf`, text dump
`datasheets/SMV123x_pages1-6.txt`). Table 4 (C vs reverse voltage, pF):

| VR (V) | 0 | 0.5 | 1.0 | 1.5 | 2.0 | 2.5 | 3.0 | 3.5 | 4.0 | 6.0 | 15.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SMV1236 | 26.75 | 20.61 | 17.02 | 14.38 | 12.29 | 10.56 | 9.16 | 8.04 | 7.19 | 5.28 | 3.80 |

Table 3: `CT @ 1 V = 15.5–18.5 pF`, ratio 1 V/3 V = 1.6–2.0, ratio 1 V/6 V =
3.0–3.5, **Rs @ 3 V, 500 MHz = 0.50 Ω**. Table 5 (SPICE): CJO 22.89 pF, VJ 9.62 V,
M 5.23, CP 3.59 pF, RS 0.50 Ω - and that model reproduces Table 4 to 0.54 pF
(2.6 %) worst case, so the C(V) I integrate against is cross-checked by two
independent tables (`tools/design_compare.py` section (a)).

So: **Cmax = 26.75 pF at 0 V, Cmin = 3.80 pF at 15 V, ratio 7.04 : 1**; over the
*usable* 0.3–3.3 V control range the swing is 23.07 → 8.49 pF = 2.72 : 1.
Rs = 0.50 Ω typ → **Q = 455 at 50 MHz** (C = 14 pF) and 866 at 26.25 MHz.

This is also where wave-1's pessimistic ceiling gets explained rather than
contradicted: its 4.736 : 1 maximum at 15 V
(`evidence/cs-varcap/REPORT.md:56`) came from the assignment's M = 0.5, Vj = 0.7
model. The real part has **M = 5.23, VJ = 9.62 V**, which gives a 1 V/6 V ratio
of 17.02/5.28 = 3.22 : 1, exactly Table 3's 3.0–3.5. The 4.74 : 1 figure is a
bound on that hyperbolic model, not on hyperabrupt parts - and neither is
anywhere near the 10 000 : 1 that wave 1 correctly rejected.

Part selection as measured (`tools/design_compare.py`, ganged across all four
nodes, fixed caps sized to keep the node at nominal mid-control):

| part | C_v @1.5 V | k span | k ratio | corner span | verdict |
|---|---|---|---|---|---|
| SMV1234 | 5.39 pF | 0.96–1.05 | 1.094 | 46.46–48.71 | 6.4 % short of 1.169 - reject |
| SMV1235 | 9.91 pF | 0.93–1.10 | 1.189 | 45.36–49.66 | +1.7 % only, misses the 50 MHz edge - reject |
| **SMV1236** | **14.38 pF** | **0.89–1.15** | **1.291** | **44.38–50.69** | **covers both edges, +10.4 % - pick** |
| SMV1237 | 40.33 pF | 0.72–1.39 | 1.925 | 41.03–57.07 | over-range: a 57 MHz setting deletes the anti-alias filter - reject |

Worst S11 at 26.25 MHz over each part's own range shows the same ordering from
the other side (`cs_varcap_part_selection.csv`): SMV1234 −26.6 dB, SMV1235
−22.2 dB, SMV1236 −18.8 dB, SMV1237 −12.6 dB. The 1237's extra range is paid for
with match.

One alternative topology was built and measured rather than dismissed
(`tools/compare_fair.py`): a **single SMV1237 at F3** also covers the window
(45.13–51.49 MHz) with 1 part instead of 4, but the varactor becomes 72 % of the
node, and at the window edges it gives S11@26.25 MHz of −20.0/−18.1 dB and
0.26–0.28 dB of passband tilt, against −25.4/−23.0 dB and 0.08 dB for the
four-part version. It also amplifies the temperature and non-linearity
sensitivity by about 2.5× (section 6). It is a legitimate cheap fallback; the
four-part design is the one specified.

## 4. The bias network

Per ladder node i (F1…F4), the varactor is **bridged across P–N**, which adds its
capacitance directly to that node (one part per node, not two):

    F_i_P --[C350..353 1 nF C0G]-- A_i --[D70..73 SMV1236]-- F_i_N
                                     |
                                   [R162..165 100 k]
                                     |
                                  IF2_TRIM --[C354 100 nF || C355 1 nF]-- GND
                                     |
                          RV1 10 k pot wiper   (top of pot --[R166 1 k]-- +3V3_ANA)

DC state: `F_i_N` is at +3.3 V (section 1), `A_i` is at Vc, so the reverse
voltage is **VR = 3.3 − Vc**. Ratiometric: if Vc is a fraction of the same
`+3V3_ANA` rail, VR is set by the resistor ratio and is independent of the rail's
absolute value - a 2 % rail error does not move the bias point.

**The "RF choke" is a resistor here, and that is a calculated choice.** A shunt
inductor resonates with the varactor inside the IF band:

| RFC | with C_v | parallel resonance |
|---|---|---|
| 1.0 µH | 14 pF | 42.5 MHz - in band |
| 2.2 µH | 14 pF | 28.7 MHz - in band |
| 4.7 µH | 14 pF | 19.6 MHz - in band |
| 10 µH | 14 pF | 13.5 MHz - in band |

(`tools/design_compare.py` section (c).) Any practical RFC would poke a
high-impedance hole in the trim exactly where it is needed. A 100 kΩ resistor
gives |Z| = 100 kΩ at 50 MHz - 32× the best choke - with no self-resonance, and
it is harmless here because the junction leakage is ≤ 20 nA (datasheet Table 3),
i.e. 2 mV of bias error. It also limits any fault current to 33 µA.

**DC blocking:** 1 nF C0G 0402 (|Z| = 3.2 Ω at 50 MHz, 25 Ω at 6.25 MHz, both
negligible against the varactor's 200–1000 Ω). It is what lets the bridge
carry a bias at all, since both ends of the node are at 3.3 V DC.

**Control divider:** RV1 10 kΩ trim pot with a 1 kΩ top resistor off
`+3V3_ANA` (the TPS7A8300 low-noise rail that already feeds U73), loaded by the
four 100 kΩ feeds (25 kΩ). Because the load is real, the mapping is not linear;
`tools/bias_divider.py` computes it:

| pot rotation | Vc | VR | source Z |
|---|---|---|---|
| 0 % | 0.000 V | 3.30 V | 11.0 kΩ |
| 27.7 % | 0.768 V | 2.53 V | 1.91 kΩ |
| 67.9 % | 1.846 V | 1.45 V | 2.35 kΩ |
| 90.2 % | 2.541 V | 0.76 V | 1.53 kΩ |
| 100 % | 2.895 V | 0.41 V | 877 Ω |

Full rotation spans VR = 3.30 → 0.41 V, so **the junction can never be driven
to zero bias** (0.41 V minimum) even at the pot's end stop; the IF2 swing at the
ladder is about ±0.1 V peak for a −13 dBm level across 100 Ω, so it never
forward-conducts. The window 46.25–50.00 MHz lives between 27.7 % and 90.2 % of
rotation - 62 % of the pot, good resolution. A fixed-divider production variant
(R_top 8.45 k, R_bot 16.9 k, 1 %) sets Vc = 1.795 V for units aligned without a
pot.

**Why a mechanical pot and not a firmware trim:** there is no spare control pin.
The netlist has all 30 RP2040 GPIOs allocated - 0–3 FPGA SPI, 4–5 LMX2592 SPI,
6–7 LMX CSB/CE, 8–10 ADF4360, 11–14 LNA enables, 15–17 DSA, 18 FPGA reset,
19 IF path select, 20–21 HSW drives, 22 ADC power-down, 23 LNA enable, 24 mixer
enable, 25 PHY reset, 26–28 ADC inputs, 29 FPGA CDONE (`tools/pins.py`) - and the
RP2040 has no DAC. A PWM+RC trim would need a pin that does not exist, so the
alignment is a one-time ATE setting by pot (or by fitting the fixed divider).

## 5. The design, and the tuning range achieved

`tools/design_production.py` (log `cs_varcap_design_run.log`, tables
`cs_varcap_cv_vs_vc.csv`, `cs_varcap_corner_placement.csv`):

- C262/C268: 51 pF → **36.5 pF**; C264/C266: 56 pF → **41.2 pF** (C0G 0402)
- D70–D73 SMV1236-079LF bridged across F1…F4, cathodes on the N nodes
- bias: 1 nF DC block + 100 kΩ + 100 nF∥1 nF at IF2_TRIM, RV1 10 k + 1 k
- new refdes checked free against the netlist (`tools/refdes.py`): D70–D73,
  R162–R166, C350–C355, RV1 are all unused.

C(V) and the resulting response over the control range:

| Vc (V) | VR (V) | C_v (pF) | node F3 (pF) | k | corner (MHz) | S21 26.25 | S21 46.25 | S11 26.25 |
|---|---|---|---|---|---|---|---|---|
| 0.00 | 3.30 | 8.49 | 49.69 | 0.887 | 51.05 | −0.59 | −0.49 | −20.4 |
| 0.50 | 2.80 | 9.72 | 50.92 | 0.909 | 50.39 | −0.57 | −0.50 | −21.9 |
| 1.00 | 2.30 | 11.25 | 52.45 | 0.937 | 49.60 | −0.54 | −0.51 | −24.4 |
| 1.50 | 1.80 | 13.13 | 54.33 | 0.970 | 48.69 | −0.52 | −0.58 | −28.9 |
| 1.75 | 1.55 | 14.17 | 55.37 | 0.989 | 48.21 | −0.50 | −0.70 | −32.8 |
| 2.00 | 1.30 | 15.44 | 56.64 | 1.011 | 47.64 | −0.49 | −1.02 | −36.5 |
| 2.25 | 1.05 | 16.76 | 57.96 | 1.035 | 47.07 | −0.48 | −1.68 | −31.8 |
| 2.50 | 0.80 | 18.46 | 59.66 | 1.065 | 46.37 | −0.47 | −3.15 | −26.2 |
| 3.00 | 0.30 | 23.07 | 64.27 | 1.148 | 44.63 | −0.48 | −9.36 | −18.7 |

Corner placement for the window edges:

| target corner | Vc | VR | C_v | node | k | S11 @26.25 |
|---|---|---|---|---|---|---|
| 46.25 MHz | 2.541 V | 0.76 V | 18.75 pF | 59.95 pF | 1.071 | −25.4 dB |
| 48.00 MHz | 1.846 V | 1.45 V | 14.62 pF | 55.82 pF | 0.997 | −34.7 dB |
| 50.00 MHz | 0.768 V | 2.53 V | 10.47 pF | 51.67 pF | 0.923 | −23.0 dB |

**Tuning range achieved: k = 0.887 … 1.148, ratio 1.293 : 1** against the
1.169 : 1 required → **+10.6 % margin**. In frequency: **44.63 … 51.05 MHz**,
ratio 1.144 : 1 against 1.081 : 1 required (+5.8 %). Both window edges are
reachable with 0.77 V of control headroom at the bottom (Vc = 0) and 0.35 V at
the top (Vc = 2.895 V max).
The nominal (corner 48.00 MHz) sits at 67.9 % pot rotation.

Costs: insertion loss at 26.25 MHz moves only −0.47 … −0.59 dB across the whole
range, and the varactor's Rs is worth **−0.007 dB at 26.25 MHz and −0.056 dB at
46.25 MHz** (`tools/loss_check.py`, Rs = 0 vs 0.5 Ω). Match at the IF itself
stays better than −18.7 dB everywhere and is −23 … −35 dB over the useful part of
the range.

The trim is **not** free at the extremes: at Vc = 0 (corner 51.05) the rejection
at 53.75 MHz falls to −11.9 dB and at 50 MHz to −1.6 dB, because the corner has
moved; at Vc = 3.0 (corner 44.63) the 46.25 MHz band edge sits at −9.4 dB. The
rolloff slope is fixed by the ladder order - the trim translates the whole
response. That is precisely why the corner must be *placed*, not maximised.

## 6. What it buys, and what it does not

**It buys the static tolerance (yes).** Worst-case corner stack at nominal
control (`tools/tolerance.py`):

| contributor | corner shift |
|---|---|
| inductors ±2 % (LQW class) | ±0.47 MHz |
| inductors ±5 % (generic 0603) | ±1.15 MHz |
| C262–C268 ±2 % C0G | ±0.37 MHz |
| varactor CT@1 V bin −8.9 %/+8.7 % (15.5/18.5 pF) | ±0.60 MHz |

Stacked worst case: **46.00 … 50.21 MHz** (±2.1 MHz). Trim authority is
**44.63 … 51.05 MHz** (±3.2 MHz) - 1.5× the spread, 0.85 MHz spare at the top
and 1.37 MHz at the bottom. So every unit can be aligned to 48.0 MHz at ATE, and
the design can use ±5 % inductors instead of ±2 % ones. It also absorbs what the
datasheets do not bound: the LT5560's 0.7 pF output capacitance, the AD8351's
0.8 pF input capacitance, board parasitics, and the −8.9 %/+8.7 % varactor bin
itself.

**It does not buy LO correction (no).** LO1 (LMX2592) and LO2 (ADF4360-1) are
fractional-N synthesizers; a frequency error is fixed by the PLL's own registers,
not by moving a filter corner. What the trim can do is re-centre the passband
after a *deliberate* IF2 plan change within about ±4 %, which is not a
substitute for re-synthesising the ladder.

**It does not buy temperature compensation (no, and it is slightly negative).**
The passive ladder is stable (C0G ±30 ppm/°C, the inductors ~±100 ppm/°C). The
varactor is the only temperature-sensitive element in the passband node;
datasheet Figure 3 bounds its C drift at ≤5 % over −40…+80 °C (axis range; curves
not read numerically - see UNVERIFIED). Because the varactor is diluted by the
fixed capacitor (14.4 of 56 pF = 25.7 %), that becomes ±1.28 % of node
capacitance and **±0.32 MHz of corner drift** - smaller than the ±2.1 MHz spread
it removes, but real and in the wrong direction to ignore. A closed-loop version
(inject a test tone, maximise S21 at 46.25 MHz) would correct it; an open-loop
trim cannot, and must not be credited with it.

**It does not fix the order or the stopband.** The alias attenuation at
53.75 MHz is set by the nine-element ladder; the trim moves it with the corner
(−11.9 to −32.2 dB across the control range) but cannot steepen it.

One further honest caveat: a varactor in the signal path is a non-linearity.
dC/dV at 1.5 V is 4.73 pF/V; at ±0.1 V peak of IF swing the node capacitance
modulates by 0.84 % (0.47 pF of 56 pF), which is a second-order term of order
−47 dBc. The ladder sits before the AD8351 gain stage, so this is the best
possible place to put it, but a two-tone test at full blocker level is required
before release.

## 7. Schematic patch

One line:

> In `08_if_chain`: replace C262/C268 51 pF with 36.5 pF and C264/C266 56 pF with
> 41.2 pF; add D70–D73 SMV1236-079LF bridged across IF2_F1_P/N … IF2_F4_P/N with
> 1 nF C0G DC blocks (C350–C353) on the P side, 100 kΩ bias feeds (R162–R165) to
> net IF2_TRIM, C354 100 nF ∥ C355 1 nF from IF2_TRIM to GND, and RV1 10 kΩ trim
> pot from +3V3_ANA through R166 1 kΩ to the IF2_TRIM wiper.

BOM additions: 4 × SMV1236-079LF (SC-79), 4 × 1 nF C0G 0402, 1 × 100 nF 0402,
1 × 1 nF C0G 0402, 4 × 100 kΩ 1 % 0402, 1 × 1 kΩ 1 %, 1 × 10 kΩ multi-turn trim
pot (e.g. Bourns 3224W-1-103E). C262/C264/C266/C268 change value, not part.

## 8. Method and provenance

Everything is computed, nothing is quoted from a simulator I did not run.

| file | what it does |
|---|---|
| `Code-SDR-V2.net` | netlist export, `kicad-cli` 9.0.7, the connectivity source |
| `tools/net_extract.py` | net/node extraction from that netlist |
| `tools/if2_ladder.py` | nodal model + datasheet C(V) tables |
| `tools/validate_model.py` | 0.001 dB agreement with `FILTER_RESPONSE.csv` |
| `tools/scaling_law.py` | S_eff per node subset; 1.161 vs 1.169 cross-check |
| `tools/design_sweep.py` | why a single node cannot do it |
| `tools/design_compare.py` | part table, Table 4 vs Table 5, choke resonances |
| `tools/compare_fair.py` | 1 × SMV1237 at F3 vs 4 × SMV1236 |
| `tools/design_production.py` | the final C(V)/corner/S11 table |
| `tools/tolerance.py` | the worst-case corner stack |
| `tools/bias_divider.py` | loaded control curve, pot rotation, fixed-divider option |
| `tools/divider_z.py` | divider source impedance at the mapped rotations |
| `tools/pins.py` | RP2040 GPIO allocation - proves there is no spare control pin |
| `tools/loss_check.py` | Rs penalty, stopband vs control voltage |
| `tools/refdes.py` | free reference designators |
| `cs_varcap_*.csv`, `cs_varcap_*.log` | every number above, re-runnable |

Wave-1 numbers used here are cited, not re-derived: the 1.169 : 1 requirement
(`evidence/cs-varcap/REPORT.md:84`), the 4.736 : 1 model ceiling at 15 V
(`:56`), the IF2/ADC facts (`codesdr_freqplan_check.log:13`).

## 9. UNVERIFIED

- **Rs has no published maximum**, only 0.50 Ω typ (Table 3). The Q of 455 at
  50 MHz is therefore a typical, not a guaranteed, number.
- **Temperature curves** (Figures 1–4) are plots; only the axis bounds (±4–5 %,
  −40…+80 °C) were read from the text layer. The ±0.32 MHz drift figure uses the
  axis bound, not the curve.
- **Inductor Q and tolerance** for the actual 0603/0402 BOM parts: the BOM
  carries value only (`200nH`, `360nH`, `390nH`), no series or tolerance, so the
  ±2 %/±5 % and Q50/Q30 cases are assumptions.
- **Board parasitics** at the four nodes are not extracted; ±0.2 pF is assumed.
  At 50 MHz that is 2 % of a 51 pF node.
- **LT5560 and AD8351 input models** (1200 Ω ∥ 0.7 pF, 5000 Ω ∥ 0.8 pF) come from
  `RF_ANALYSIS.md:71-78`'s reading of the ADI datasheets, not from measurement.
- **No VNA measurement of the board exists**, so the stock corner of 47.90 MHz is
  a design-model number, not a measured one. First-article alignment must measure
  S21 at 26.25, 46.25 and 50 MHz before the pot is set.
- **Varactor die-to-die tracking** of four separate SC-79 parts is not specified;
  using one reel/lot is assumed.
- The trim's **non-linearity** (0.84 % node modulation, ≈ −47 dBc estimate) is
  analytical only.