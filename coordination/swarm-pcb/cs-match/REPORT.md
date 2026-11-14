# Code-SDR V2 - 50 ohm interface audit of the 7 band paths (CS-match)

Scope: impedance at the filter / LNA / mixer / BAW / ADC interfaces of the seven
frequency-plan rows, with the board's own routed geometry. Read-only on git; no
repository file was modified. Everything below is under
`evidence/cs-match/`.

**Provenance of every number.** Three classes, kept separate:

| class | source | trust |
|---|---|---|
| MEASURED | trace width/length per net, pulled from `Code-SDR-V2.kicad_pcb` with `pcbnew` (`pcb_trace_geometry.csv`, `if_geometry_per_layer.txt`) | fact |
| MEASURED | component values, nets and placements, pulled from the board + netlist (`interface_pads.txt`) | fact |
| ANALYTIC | Z0 and S11 from scikit-rf, Hammerstad-Jensen microstrip, h=0.130 mm, t=0.035 mm, ideal lossless L/C, no vendor S2P, no field solve | model, not measurement |

No full-wave solver and no vendor S-parameter files were used. Every S11 here is
**a nominal-geometry analytic figure**. Device-port impedances that the board
cannot tell us (LNA input, BAW port, AD9215 sampling network) are the main
unverified input; that is stated per interface and collected at the end.

---

## 1. The transmission-line basis (MEASURED geometry -> ANALYTIC Z0)

Stackup per `FABRICATOR_IMPEDANCE_NOTE.md` and `STACKUP_DRAWING.md`:
F.Cu / 0.130 mm prepreg (Dk 4.2 model) / In1.Cu solid GND / 1.200 mm core /
In2.Cu **split +3V3_ANA / +3V3_DIG** / 0.130 mm prepreg / B.Cu.
`zones.txt` confirms the copper stack actually built: In1.Cu carries one GND
zone, In2.Cu carries only `+3V3_ANA` and `+3V3_DIG`, and **B.Cu carries no zone
at all**.

Z0 vs width (`z0_vs_width_dk.csv`, skrf `MLine`, h=0.130 mm, t=0.035 mm):

| width | Dk 4.0 | Dk 4.2 | Dk 4.6 |
|---|---|---|---|
| 0.100 mm | 74.74 | 73.27 | 70.57 |
| 0.150 mm | 63.16 | 61.89 | 59.55 |
| 0.200 mm | 54.97 | 53.84 | 51.78 |
| **0.230 mm** | **51.07** | **50.01** | **48.08** |

So the documented 0.23 mm / 0.130 mm geometry is indeed a 50 ohm design at
Dk 4.2, and 48-51 ohm over a realistic Dk window. The 48-55 ohm range in the
brief is reproduced at the low-Dk end being optimistic; 55 ohm needs Dk ~3.6.

**The widths that are actually routed are not all 0.23 mm.**
`pcb_trace_geometry.csv`, 260 routed nets: **49 nets are exclusively 0.230 mm**
and 125 exclusively 0.150 mm (75 are mixed). Among the 87 RF/IF-named nets,
47 carry a 0.230 mm segment, 39 carry 0.150 mm, 5 carry 0.100 mm and 4 carry
0.200 mm. The 0.23 mm "RF50" set covers the front end and the 2.42625 GHz
single-ended runs, but **every differential IF leg is 0.15 mm (61.9 ohm) or
0.10 mm (73.3 ohm)**:

```
IF_HIGH_P   0.15/0.10 mm  52.6 mm total, of which 51.2 mm on In1.Cu
IF_HIGH_N   0.15 mm       49.7 mm total, of which 48.9 mm on In1.Cu
IF_LOW_P/N  0.15-0.20 mm  12.0 mm, on B.Cu + F.Cu
IF2_P/N     0.15 mm  8.5-12.1 mm     LT_IN_P/N 0.10-0.15 mm  7-9 mm
ADC_VIN_P   0.15/0.10 mm 44.6 mm     ADC_VIN_N 0.15/0.10 mm  42.0 mm
```

For reference, 0.15 mm into a 50 ohm port is |S11| = -19.5 dB, so width alone
does not break the -10 dB target. Length and reference plane are what break it.

If the only continuous reference left is In1 GND at 1.335 mm (B.Cu over the
In2 split, or In1 traces whose own plane has been cut away), Z0 becomes
**130.65 ohm at 0.23 mm and 144.01 ohm at 0.15 mm** - a 2.6-2.9:1 mismatch.

---

## 2. Interfaces per row

Front-end definitions from `design_model.py` lines 976-1090 (low) and
1094-1299 (high); values confirmed against the board pads
(`interface_pads.txt`).

| row | RF band MHz | path | in-series C | in-shunt C |
|---|---|---|---|---|
| LOW | 100-2500 | J50 -> FL50 LFCN-2500 -> U50 GRF4001 -> U51 ADL5801 | C208 100 pF | C209 0.2 pF |
| LOW_HF_OPTION | 10-2500 | J50 -> FL50 -> R153/R156 bypass (C208/C210 omitted) | - | - |
| HIGH_A | 2300-4200 | J60 -> D60/C215 -> U60 GRF4001 -> U64 QPC6144 | C215 100 pF | C219 0.2 pF |
| HIGH_B | 4200-6800 | J61 -> C216 -> U61 GRF2101 -> U64 | C216 0.6 pF | C2110 **22 pF** |
| HIGH_C (high side) | 6800-7350 | J62 -> C217 -> U62 GRF2101 -> U64 | C217 0.8 pF | C2111 0.3 pF |
| HIGH_C (low side) | 7150-9200 | same hardware, different LO1 sideband | C217 0.8 pF | C2111 0.3 pF |
| HIGH_D | 8000-10000 | J63 -> C218 -> U66 -> C291 -> U67 (2nd GRF2101) -> U64 | C218 0.5 pF | C2112 0.2 pF |

Common tail, shared by all seven rows after the 2.42625 GHz first IF
(`design_model.py` 1304-1522):

`IF_SELECTED -> FL70 QPQ1909 BAW (2402.5-2493.5 MHz) -> U71 GRF2013 ->
U72 PE4312 DSA -> U75 GRF2013 -> T70 2450BL15B0100001E (50:100) ->
U73 LT5560 -> IF2 26.25 MHz -> 100 ohm differential 9-element ladder at
46.5 MHz (L87-L96, C262/C264/C266/C268) -> U74 AD8351 -> R73/R74 25R ->
U21 AD9215 (ADC_VIN_P/N)`.

Interfaces enumerated per row: **I1** antenna/RF-in (SMA -> LNA/filter),
**I2** post-LNA (LNA out -> selector or mixer drive), **I3** mixer IF out
(differential IF -> balun -> 50 ohm), **I4** BAW in and out, **I5** ADC input.

Worst |S11| now (`s11_interfaces.csv`; dB, most negative = best):

| row | I1 front end | I2 post-LNA | I3 mixer IF out | I4 BAW | I5 ADC | **worst** |
|---|---|---|---|---|---|---|
| LOW | -15.94 @100 MHz | -88.7 | -14.71 | -79.7 | -36.1 | **-14.7** |
| LOW_HF_OPTION | -76.5 | -88.7 | -14.71 | -79.7 | -36.1 | **-14.7** |
| HIGH_A | -18.25 @4.2 GHz | -75.8 | -2.44 | -79.7 | -36.1 | **-2.44** |
| HIGH_B | **-0.25 @4.2 GHz** | -2.63 (B.Cu) | -2.44 | -79.7 | -36.1 | **-0.25** |
| HIGH_C high side | -6.77 @7.35 GHz | -83.6 | -2.44 | -79.7 | -36.1 | **-2.44** |
| HIGH_C low side | -5.42 @9.1 GHz | -77.1 | -2.44 | -79.7 | -36.1 | **-2.44** |
| HIGH_D | -5.44 @9.08 GHz | -2.50 (B.Cu) | -2.44 | -79.7 | -36.1 | **-2.44** |

Three things fall out of that table:

1. **I3 is the same physical pair for six rows** - the LTC5548 IF output is
   routed to T60 almost entirely on **In1.Cu** (`if_geometry_per_layer.txt`:
   51.2 mm of IF_HIGH_P and 48.9 mm of IF_HIGH_N on In1, with only 1.5 mm and
   0.8 mm on F.Cu). In1 is the declared solid GND plane, so those 50 mm of
   2.42625 GHz differential line have no ground reference: measured against
   In1-as-reference the pair is ~144 ohm and the interface sits at -2.44 dB.
   The LOW row uses ADL5801 -> T50 on B.Cu/F.Cu and lands at -14.71 dB.
2. **I4 (BAW in/out) is clean at -79.7 / -90.9 dB** because both runs are
   0.23 mm over In1 (7.42 mm and 1.89 mm). This is the design's best-matched
   interface *provided* the QPQ1909 really is a 50 ohm port at 2406.25 MHz,
   which is 3.75 MHz from the BAW lower passband edge - see UNVERIFIED.
3. **HIGH_B's front end is shorted, not mismatched.** C2110 = 22 pF_C0G from
   `RF_HB_LNA_IN` to GND (board pad dump: `C2110 22pF_C0G ... 1=RF_HB_LNA_IN
   2=GND`; netlist description "RF_HB_LNA_IN local bypass"). Xc(22 pF) is
   1.7 ohm at 4.2 GHz, so the 4.2-6.8 GHz input port is ~1.7 ohm to ground:
   -0.25 dB.

---

## 3. Matching proposals (`matching_search.csv`, `stub_matching_search.csv`)

Basis: one added 0402 series L and one added 0402 shunt L at the LNA node,
searched over E12 values and 0.3-22 nH; then a shunt open 0.23 mm microstrip
stub, 0.5-6 mm in 0.25 mm steps, optionally with the 0402 shunt L. Ideal
lossless elements - no Q, no ESL, no pad capacitance.

| case | now | best achievable | element values | verdict |
|---|---|---|---|---|
| HIGH_A 2.3-4.2 | -18.25 | -25.77 | 0.3 nH series + 22 nH shunt (optional) | **already passes, damping optional** |
| LOW 0.1-2.5 | -15.94 | -15.94 (the search only *adds* parts, and every pair degraded it to -1.28) | no part needed | **already passes** |
| HIGH_C high side 6.8-7.35 | -6.77 | -11.21 | 0.5 mm open stub + 1.6 nH shunt | **matched (LC+stub)** |
| HIGH_C low side 7.15-9.2 | -5.42 | -10.03 | 0.5 mm open stub + 1.1 nH shunt | **matched, 0.03 dB margin - fragile** |
| HIGH_D 8.0-10.0 | -5.44 | -9.09 | 0.5 mm stub + 1.1 nH shunt | **still fails by 1 dB** |
| HIGH_B 4.2-6.8 | -0.25 | -0.25 | none found | **no LC/stub solution** |
| I3 IF_HIGH_P/N | -2.44 | see T2 | search run on normal F.Cu geometry gives -14.17 -> -12.19, i.e. the *geometry* is not the defect; the reference plane is | **not a matching problem (T2)** |

Notes on the two marginal results:

* HIGH_C's fix is a 0.5 mm open stub (about 4 degrees at 7 GHz - it is behaving
  as a small shunt capacitance, not a real stub) plus a 1.6 nH / 1.1 nH shunt.
  A 0.5 mm stub is inside the LNA pad-escape area and is not separately
  manufacturable at the accuracy implied; treat as "needs the vendor S2P tune"
  rather than a released match.
* HIGH_D is 1 dB short across 8-10 GHz with one 0402 L and one stub. A second
  element or a wider shunt-L search does not close it because the 0.5 pF
  series block is -31.8 ohm of reactance at 10 GHz against a 1.25:1 band.
  See the topology section.

---

## 4. NEEDS_TOPOLOGY_CHANGE

These cannot be fixed by changing LC values on the existing copper.

**(T1) HIGH_B: C2110 22 pF to GND on RF_HB_LNA_IN.** A shunt inductor across
it would only work as a narrow notch (66 pH to resonate at 4.2 GHz, below the
0402 minimum and a DC short). Delete C2110, or move it to the VDD bypass it was
clearly copied from (its description says "local bypass"). After removal the
same port measures -5.58 dB and a 8.2 nH shunt brings the band to -6.94 dB,
still short - i.e. removal is necessary but not sufficient; the 0.6 pF series
C216 should be re-tuned with the vendor GRF2101 S2P at that point.

**(T2) IF_HIGH_P/N routed on In1.Cu (51.2 mm / 48.9 mm).** This is not a
matching error, it is the return-path defect CS-G3 already flagged, in its worst
form: the 2.42625 GHz differential pair is placed inside the plane that is
supposed to be the reference, and the pair is drawn as two 0.15 mm (61.9 ohm)
single-ended legs rather than a controlled differential pair. Move the pair to
F.Cu with continuous In1 GND underneath, as a controlled 0.23 mm differential
pair, and re-terminate T60. Expected then: better than -30 dB (the 0.23 mm leg
is 50.01 ohm) instead of -2.44 dB. No 0402 network can repair 50 mm of a
144 ohm line.

**(T3) B.Cu RF runs over the split In2 power plane** - `RF_HB_LNA_OUT` 41.7 mm
and `RF_HD_LNA_OUT` 14.3 mm at 0.23 mm (`if_geometry_per_layer.txt`), and
`IF_SELECTED` 5.0 mm. There is no B.Cu ground zone at all. Two bounding cases:
if In2 behaves as an RF ground the S11 is fine (50 ohm geometry) but the DC
return must cross the split, so the failure appears as common-mode current and
radiation rather than as |S11|; if In2 cannot be used at 4.2-10 GHz the port is
130.65 ohm and S11 is -2.63 dB / -2.50 dB. Either way the fix is a plane change
(B.Cu GND pour + via fence, or move the run to F.Cu), not an L/C value.
**An |S11| measurement into 50 ohm can look healthy while this defect is
present** - it must be judged with a VNA TDR/return-loss-to-split test, not
with S11 alone.

**(T4) ADC interface cannot be a single-ended 50 ohm LC match.** The port is
the AD9215 differential switched-capacitor input, reached through 25 ohm per
leg (R73/R74) from the AD8351 differential driver, with VOCM set to 1.65 V (3V3/2) by
the R75/R76 divider. A 2-element LC match of a 1 kohm differential load to
50 ohm at 26.25 MHz needs Q = 4.36 (L = 1321 nH, C = 26.4 pF) and gives only
**6.0 MHz** of matched bandwidth (`adc_26mhz_limits.json`), against the
6.25-46.25 MHz span the 40 MHz channel needs. A Bode-Fano check with a 2 pF
sampling capacitance says the 40 MHz band is feasible only in principle
(required/allowed = 0.58), i.e. it needs a multi-section network - which is
exactly the 9-element differential ladder plus the AD8351 that the design
already has. So: the single-ended 50 ohm LC match the task hypothesised is
impossible, but **the design already chose the correct topology** (active
differential driver, 100 ohm differential, internally terminated with R79/R80).
No balun is required as drawn. If the AD8351 were ever removed, a 1:1/1:4
transformer with a grounded centre tap would be mandatory; an LC network cannot
set the ADC common mode.

---

## 5. UNVERIFIED - what a first article must measure

1. **Every device port impedance.** LNA S11 (GRF4001/GRF2101/GRF2013), BAW
   S11/S22 of QPQ1909 at 2406.25 MHz (3.75 MHz from the 2402.5 MHz passband
   edge - the design's 40 MHz channel sits asymmetrically in the 91 MHz BAW
   band), AD9215 differential input impedance/R, LT5560 IF output, AD8351
   output. Without these the S11 columns above are board-only bounds.
2. **Fabricator Dk/t after pressing.** All Z0 numbers assume the nominal
   0.130 mm dielectric. 0.23 mm gives 50.01 ohm at Dk 4.2/h 0.130, 48.08 ohm at
   Dk 4.6, 51.18 ohm at Dk 4.4/h 0.140 and 54.32 ohm at h 0.150 - a 48-54 ohm
   window for press tolerances that are still inside the "controlled impedance"
   claim. Only a coupon TDR settles it.
3. **Whether In2 acts as an RF ground under the B.Cu runs** (T3). Resolve with
   TDR on a first-article coupon that crosses the split.
4. **Field solve / VNA of the In1 segments** (T2) - the model's 144 ohm is an
   assumption about which plane is the reference, not a solved value.
5. **0402 self-resonance at 8-10 GHz** - the HIGH_C/HIGH_D stub+L proposals are
   ideal-element results; a 1.1-1.6 nH 0402 is at its SRF near 10 GHz.
6. **ADC `ADC_VIN` CM** measurement: VOCM = 3V3/2 = 1.65 V from the 10k/10k
   divider, and the ADC datasheet common-mode target was not verified here.

---

## 6. Files

Under `E:/engineering-portfolio-audit/evidence/cs-match/`:

| file | content |
|---|---|
| `REPORT.md` | this report |
| `z0_vs_width_dk.csv` | Z0/eeff vs width and Dk, both reference heights |
| `pcb_trace_geometry.csv` | per-net length, widths, layers, segment and via counts for all 260 routed nets |
| `if_geometry_per_layer.txt` | per-net per-layer length for the 50 interface nets |
| `interface_pads.txt` | pad -> net dump of 82 interface components (the C2110 evidence) |
| `s11_interfaces.csv` | S11 at band edges and worst-in-band per row per interface |
| `s11_curves.csv` | 201-point S11 sweeps for I1/I2 |
| `matching_search.csv` | 0402 series-L / shunt-L search results |
| `stub_matching_search.csv` | open-stub search results |
| `adc_26mhz_limits.json` | 2-element L-match and Bode-Fano numbers for the ADC port |
| `zones.txt` | copper zone inventory (In1 GND, In2 split power, no B.Cu zone) |
| `model_run.log`, `stub_run.log` | tool output of the two model runs |

Scripts (read-only, do not touch the repo):
`E:/engineering-portfolio-audit/scripts/cs_pcb_geom.py`, `cs_if_geom.py`,
`cs_pads.py`, `cs_zones.py`, `cs_match_model.py`, `cs_match_stubs.py`.