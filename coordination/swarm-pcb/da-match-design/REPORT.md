# drone-arm 915 MHz matching network — design to 50 Ω over 902–928 MHz

Evidence directory: `E:/engineering-portfolio-audit/evidence/da-match-design/`
Scripts: `E:/engineering-portfolio-audit/scripts/da_match_*.py`
Read-only on all repos. Nothing in any repo was modified.

---

## 0. Summary

| | worst in band, 902–928 MHz |
|---|---|
| as-built (MATCH_A/MATCH_B as populated) | **−0.86 … −2.34 dB** (badly mismatched, VSWR 6.7–18) |
| proposed (six component changes on existing pads, no layout change) | **−24.5 dB** at the worst of the four void fractions; −19.3 dB even if C94 is left unfitted |

The central worry in the brief — "the void is what makes impedance unknown" — turns out **not** to be
the limiting error. The proposed network holds ≤ −15.7 dB for every effective height from 0.10 mm to
0.58 mm (Z0 33 … 87 Ω), i.e. the entire plausible void range and well past it. The limiting errors are
component tolerance and the fact that the In1 plane is **3V3, not a ground plane** — neither of which
this analysis can settle.

---

## 1. What the files actually contain

### 1.1 Netlist (authoritative for connectivity)

```
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" sch export netlist --format kicadxml \
  -o evidence/da-match-design/main_rev_b.net.xml \
  repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_sch
```
→ exit 0, 285 655 bytes. Every net below is quoted from that export.

Schematic labels for these nets live at
`repos/drone-arm/hardware/main/rev_b/rf_915.kicad_sch:8265-8635`
(`SAW_PA` 8265/8315/8335, `MATCH_A` 8485…8595, `MATCH_B` 8585…8635).

### 1.2 Current MATCH_A / MATCH_B topology (one line)

CC1121 (U40) → FL40 balun/filter → FL41 B39921 SAW → `SAW_PA` → L42 10 nH + C88 0.8 pF →
CC1190 PA_IN (U41) → `RF_PA_OUT` → **C90 47 pF (DC block)** → `MATCH_A` → **L48 2.9 nH**
( ‖ `C94` 2.4 pF, **DNP**) → `MATCH_B` → **L49 9.1 nH** → `ANT_915` → U.FL J40,
with shunts **C91 3.3 pF** on MATCH_A, **C95 7.5 pF** on MATCH_B, **C96 2.7 pF (DNP)** on ANT_915,
and the receive tap **L47 7.5 nH → C92 12 pF → TR_SW** also hanging on MATCH_A.

Net contents from the export (`ref(pin)`):

```
/915 MHz RF/MATCH_A : C90(2), C91(1), C94(1), L47(1), L48(1)
/915 MHz RF/MATCH_B : C94(2), C95(1), L48(2), L49(1)
/915 MHz RF/ANT_915 : C96(1), J40(1), L49(2)
/915 MHz RF/RF_PA_OUT : C90(1), L46(2), U41(2)
/915 MHz RF/SAW_PA  : C88(1), FL41(2), L42(1)
```

Values (netlist `<components>`, all 0402 except L46 0603 and the two filters):

| ref | value | part | role |
|---|---|---|---|
| C90 | 47 pF C0G | 0402 | PA DC block |
| L46 | 22 nH | 0603 | PA bias choke (TI reference: 10 nH) |
| C91 | 3.3 pF C0G | 0402 | shunt, MATCH_A |
| L48 | 2.9 nH | 0402 | series MATCH_A→MATCH_B (TI: 2.2 nH) |
| C94 | 2.4 pF **DNP** | 0402 | parallel across L48 |
| C95 | 7.5 pF C0G | 0402 | shunt, MATCH_B (TI: 8.2 pF) |
| L49 | 9.1 nH | 0402 | series MATCH_B→ANT (TI: **3.9 nH**) |
| C96 | 2.7 pF **DNP** | 0402 | shunt, ANT_915 (TI: 0.5 pF) |
| L47 | 7.5 nH | 0402 | RX tap (matches TI L22 7.5 nH) |
| C92 | 12 pF C0G | 0402 | RX tap (matches TI C22 12 pF) |
| FL41 | B39921B3588U410 | — | 915 MHz SAW |
| U41 | CC1190RGVR | — | PA / LNA front end |

The chain is a de-tuned copy of the TI CC1190EM 915 MHz reference (datasheet Table 1, p.5 of
`docs/datasheets/main/ti-cc1190.pdf`, extracted to `cc1190_text.txt:229-244`). Two departures matter:
**L49 is 2.3× the reference value** and **L48 1.3×**, while C94/C96 are not fitted at all.

### 1.3 Physical geometry (from pcbnew, not guessed)

`scripts/da_match_pcb_geom.py` via `"C:/Program Files/KiCad/9.0/bin/python.exe"` → `pcb_geom.json`.
All RF copper is on F.Cu, 0.35 mm wide. Lengths used in the model:

| element | length | note |
|---|---|---|
| U41.2 → C90.1 | 1.668 mm | |
| **choke stub** C90.1 → L46.2 | **3.055 mm** | bias choke sits 3 mm off the trace |
| C90.2 → MATCH_A node | 2.535 mm | |
| MATCH_A → C94 tee T | 1.595 mm | |
| T → C91.1 | **4.920 mm** | C91 shunt stub is **6.52 mm** total |
| MATCH_A → L47.1 | 3.035 mm | RX tap stub |
| MATCH_B → C94.2 stub | 1.595 mm | dangles when C94 is DNP |
| L48.2 → L49.1 | 3.030 mm | |
| MATCH_B → C95.1 | 3.140 mm | |
| L49.2 → C96.1 | 3.922 mm | |
| L49.2 → J40 | **11.506 mm** | the long run to the U.FL |

Two things a schematic-only reading gets wrong, and which change the answer:

1. **The shunts are not at the nodes.** C91 sits 6.5 mm of line away from MATCH_A, C95 3.1 mm from
   MATCH_B, C96 3.9 mm from the L49 pad. Those stubs already contribute 0.35–0.75 pF of shunt
   capacitance on their own, which is why the as-built 3.3 pF / 7.5 pF parts are *far too large*.
2. **There is 19 mm of 0.35 mm line** in the series path. At 915 MHz that is ~38° of electrical
   length — a matching element in its own right, not a wire.

### 1.4 Stackup and the reference plane

`main_rev_b.kicad_pcb:50-60`:

```
F.Cu 0.035 mm | dielectric 1 prepreg 0.200 mm FR4 er 4.2 tan_d 0.02 | In1.Cu 0.035 mm
dielectric 2 core 1.04 mm | In2.Cu | prepreg 0.200 mm | B.Cu
```

`docs/diagnostics-2026-11-10/rf_ground_audit.json` samples 11 centreline points of the ANT_915 run and
finds **In1.Cu = `/3V3`** at every one (lines 12, 26, … — 11 occurrences), with `/GND` only on B.Cu at
1.275 mm. So the RF trace is referenced to a **power plane**, and the nearest ground is 6× further away.

Microstrip Z0 for 0.35/0.200 mm, er 4.2 (scikit-rf `MLine`, Hammerstad-Jensen):
**51.20 Ω** with 35 µm copper, **53.79 Ω** at zero thickness. This sits inside the host-supplied
48.6–54.0 Ω bracket; the bracket is treated as model uncertainty, not as extra data.

---

## 2. The criterion — and why the obvious one is wrong

The brief asks for "S11 with a 50 Ω port at the antenna side". Taken literally as a 50 Ω/50 Ω two-port,
**TI's own reference network scores −2.32 dB** on this board's port pair
(`scripts/da_match_criterion.py`, ideal elements, no parasitics). A known-good design cannot fail by
12 dB, so the 50 Ω/50 Ω number is the wrong metric for this port pair, and I do not use it as the target.

The reason: the CC1190 is a 26.5 dBm PA running from 3.3 V, so its load-line optimum is

```
R_opt = (Vdd − Vsat)² / (2·Pout) = (3.3 − 0.3)² / (2 × 0.447 W) = 10.07 Ω
```

TI's reference match presents **|Z| = 10.2 Ω** (6.8 − j7.6) at the PA node — independent confirmation
that ~10 Ω, not 50 Ω, is what belongs at that end. **So the network is a 50 Ω ↔ 10 Ω transformer**, and
a 50/50 two-port *must* reflect.

Criterion actually used everywhere below:

* port 2 = **J40, 50 Ω** — this is the "50 ohm port at the antenna side" the brief asks about;
* port 1 = the CC1190 PA plane, terminated in **R_opt = 10.07 Ω**;
* Γ_ant = (Zin_J40 − 50)/(Zin_J40 + 50); target ≤ −10 dB for 902–928 MHz.

Both conventions are reported in §5 so nothing is hidden.

---

## 3. Model

`scripts/da_match_model.py`. Cascade of ABCD sections, one per real copper segment and part:

* every F.Cu segment at its measured length, width and stub topology, including dangling stubs where
  C94/C96 are unfitted (copper is there whether or not the part is);
* `Z0`, `γ`, `er_eff` from scikit-rf `MLine` at each void fraction;
* L: series R from Q = 45 at 915 MHz; C: ESR from Q = 200 plus 0402 ESL = 0.45 nH
  (the 47 pF DC block is near its own series resonance at 915 MHz, so the ESL is not cosmetic);
* C94, when fitted, joins MATCH_A and MATCH_B **in parallel with L48** — handled by adding the two
  paths' Y-matrices, not by a cascade;
* VDD / VSS at the top of L46 taken as AC ground through the choke.

**Validation — three independent algorithms, same netlist:**

| method | max ‖ΔΓ‖ vs ABCD cascade |
|---|---|
| admittance walk (tanh composition), `da_match_xcheck.py` | **8.3e-16** |
| nodal Y-matrix solve, `da_match_nodal.py` (incl. C94-fitted path) | **1.2e-14** |

Both agree with the ABCD cascade to machine precision, so the arithmetic and the topology
implementation are not in question. What remains uncertain is physics, not code (§7).

Sanity checks: a bare 19 mm line loses 0.10 dB (tan_d 0.02) and is passive; an ideal L+C network comes
out exactly passive (|S11|²+|S21|² = 1.000000).

### 3.1 Void / effective-er model

A void in In1 forces return current down to the B.Cu ground at 1.275 mm instead of the In1 plane at
0.200 mm. This is modelled as a current-weighted effective height,

```
h_eff(f_void) = 0.200 + f_void × (1.275 − 0.200)   [mm]
```

fed to `MLine`; the resulting `er_eff` and `Z0` are the effective-er perturbation the brief asks for.

| void | h_eff | Z0 @915 | er_eff @915 |
|---|---|---|---|
| 0 % | 0.200 mm | 51.2 Ω | 3.056 |
| 5 % | 0.254 mm | 58.6 Ω | 3.002 |
| 11.14 % | 0.320 mm | 66.1 Ω | 2.955 |
| 20 % | 0.415 mm | 75.0 Ω | 2.909 |
| 35 % | 0.576 mm | 86.5 Ω | 2.867 |

This is a first-order electrostatic argument (linear interpolation of return-path depth), **not** a
field solution; it deliberately spans a pessimistic range so the design cannot be flattered by it.
The 11.14 % figure is the host-supplied measurement; it is not reproducible from any file in the repo
(searched `docs/`, `evidence/`) and is carried as an input, not as my own result.

---

## 4. Result — the as-built network

Γ_ant, PA plane at R_opt = 10.07 Ω (`da_match_final.py`):

| void | Γ@915 | worst in band | at | Zin at J40 |
|---|---|---|---|---|
| 0 % | −2.63 dB | −2.34 dB | 928 MHz | 22.4 + j67.8 |
| 5 % | −1.86 dB | −1.66 dB | 928 MHz | 17.0 + j72.5 |
| **11.14 %** | **−1.35 dB** | **−1.20 dB** | **928 MHz** | **13.2 + j77.0** |
| 20 % | −0.95 dB | −0.86 dB | 928 MHz | 10.2 + j82.1 |

At the designed void fraction the antenna sees 13.2 + j77.0 Ω — VSWR ≈ 13, so about 73 % of the
incident power is reflected. Under the literal 50/50 convention it is S22 = −1.48 dB (0 %) /
−1.00 dB (11.14 %). The device end is no better: with a 50 Ω antenna the PA plane sees
2.8 + j16.6 Ω, i.e. −1.28 dB against R_opt.

Node-by-node walk (`da_match_profile.py`, port 1 terminated in R_opt, f_void = 11.14 %, 915 MHz).
Each row is the impedance at that node looking back toward the PA:

```
after section                    Zin (ohm)        G (dB)
U41.2                            10.1  +3.6j       -3.55
+ 22 nH choke (3.05 mm stub)      9.7  +4.0j       -3.37
+ C90 47 pF DC block              9.7  +2.9j       -3.39
+ 2.535 mm line -> MATCH_A        9.8  +8.4j       -3.37
+ L47/C92 RX tap                  6.5  +8.2j       -2.20
+ C91 3.3 pF (6.52 mm stub)      11.1  +7.8j       -3.81
+ L48 2.9 nH                     11.4 +24.5j       -3.21
+ C94 stub (unfitted)            11.9 +24.9j       -3.33
+ 3.030 mm line -> L49           13.1 +32.5j       -3.18
+ C95 7.5 pF (3.14 mm stub)       4.6 -19.4j       -1.40   <-- collapses
+ L49 9.1 nH                      5.8 +32.9j       -1.41
+ C96 stub (unfitted)             6.7 +35.0j       -1.56
+ 11.506 mm line -> J40          13.2 +77.0j       -1.35   = antenna sees this
```

The network is least wrong nearest the device: Γ sits at −3.2 … −3.8 dB from U41.2 through to L48 and
then degrades monotonically outward to −1.35 dB at J40. The 9.8 + j8.4 Ω at MATCH_A is at least the
right order for an optimum of 10.07 Ω, but the antenna half is where it fails — C95 (7.5 pF) drags the
node to 4.6 − j19.4 Ω, L49 (9.1 nH, +52 Ω at 915 MHz) swings it to +j33 Ω, and 11.5 mm of line turns
that into 13.2 + j77 Ω. L49 alone, as a series element into a 50 Ω antenna, caps the achievable match
at −6.7 dB.

---

## 5. Proposed design

Six component changes on pads that **already exist** — four re-values plus two DNP pads now
populated. No track, no layer, no footprint, no layout change. The board is reworked by swapping
0402 parts.

| | pad | now | **proposed** | line |
|---|---|---|---|---|
| C91 | shunt on MATCH_A, 6.52 mm stub | 3.3 pF | **4.7 pF** C0G 0402 | existing, fitted |
| L48 | series MATCH_A→MATCH_B | 2.9 nH | **1.5 nH** 0402 | existing, fitted |
| C94 | parallel across L48 | 2.4 pF DNP | **2.7 pF** C0G 0402 | existing pad, **now fit it** |
| C95 | shunt on MATCH_B, 3.14 mm stub | 7.5 pF | **0.82 pF** C0G 0402 | existing, fitted |
| L49 | series MATCH_B→ANT_915 | 9.1 nH | **1.0 nH** 0402 | existing, fitted |
| C96 | shunt on ANT_915, 3.92 mm stub | 2.7 pF DNP | **3.3 pF** C0G 0402 | existing pad, **now fit it** |

Unchanged: C90 47 pF, L46 22 nH, L47 7.5 nH, C92 12 pF, and all four filter/IC parts.
All six values are on the E24 ladder (verified in `tables.txt`; note C95 = 0.82 pF, not 0.8 pF).

### 5.1 Modelled performance

| void | Γ@915 | worst in band | at | Zin at J40 |
|---|---|---|---|---|
| 0 % | −29.57 dB | −26.16 dB | 902 MHz | 52.9 − j1.8 |
| 5 % | −28.56 dB | −24.70 dB | 902 MHz | 53.2 − j2.1 |
| 11.14 % | −32.55 dB | −26.29 dB | 902 MHz | 51.5 − j1.8 |
| **20 %** | −32.44 dB | **−24.48 dB** | 928 MHz | 47.7 + j0.3 |
| 35 % | −18.30 dB | −15.66 dB | — | — |

**Worst over the four required void fractions: −24.48 dB.** Margin over the −10 dB target: 14.5 dB.
Worst-case VSWR ≈ 1.13.

If C94 is left unfitted (fewer parts to place), the same other five values still give **−19.29 dB**
worst in band — so C94 is a fine-tune, not a requirement.

### 5.2 In-band detail (Γ, dB, 2 MHz steps; full 521-point data in `sweep_915.csv`)

```
   MHz   now/0%  now/11%  now/20%   prop/0%  prop/11%  prop/20%
   902    -2.98    -1.52    -1.07    -26.16    -26.29    -37.51
   910    -2.76    -1.41    -1.00    -28.44    -30.02    -40.27
   916    -2.61    -1.33    -0.95    -29.72    -32.97    -31.48
   920    -2.51    -1.29    -0.92    -30.02    -33.79    -28.44
   928    -2.34    -1.20    -0.86    -28.98    -31.00    -24.48
```

### 5.3 Why these values — and what the stubs mean

The optimizer's answer is physically sensible once the stubs are counted:

* **C95 falls to 0.82 pF** because its 3.14 mm stub is already ≈ 0.35 pF of shunt capacitance. The
  as-built 7.5 pF was 6× too much.
* **C91 rises to 4.7 pF** because its 6.52 mm stub presents ≈ 0.75 pF and then *transforms* the
  capacitor; the fitted part has to be larger, not smaller, than the reference value.
* **L49 9.1 nH → 1.0 nH**: at 915 MHz 9.1 nH is +52 Ω in series with a 50 Ω antenna. That alone limits
  the match to −6.7 dB. 1.0 nH is essentially "a short with the lowest inductance 0402 allows".
* **C94 fitted at 2.7 pF** across the new 1.5 nH L48 turns the series element from +j8.6 Ω into
  +j10.0 Ω. A 15 % reactance shift, but it pushes the worst-case null 5 dB deeper
  (−19.3 → −24.5 dB). It is a trim, not a structural element — see §5.1.

### 5.4 Per-void tuning chart (if you measure the real void fraction)

`e24_refine.json`. Every column is the best E24 set for that void fraction alone; the values barely
move, which is the real reason one value set covers the whole range:

| void | worst | C91 | L48 | C94 | C95 | L49 | C96 |
|---|---|---|---|---|---|---|---|
| 0 % | −30.43 dB | 5.1 | 1.6 | 2.2 | 0.91 | 1.0 | 3.3 |
| 5 % | −30.52 dB | 5.1 | 1.6 | 2.4 | 0.91 | 1.1 | 3.3 |
| 11.14 % | −29.17 dB | 4.7 | 1.5 | 1.5 | 0.82 | 1.0 | 3.3 |
| 20 % | −29.06 dB | 4.7 | 1.5 | 3.3 | 0.75 | 1.0 | 3.3 |

Units pF for capacitors, nH for inductors.

---

## 6. Robustness (all on the proposed set)

| perturbation | worst in band |
|---|---|
| effective height 0.10 → 0.576 mm (Z0 33 → 87 Ω) | −19.75 … −15.66 dB; deepest −28.0 dB at 0.15 mm, degrades to −6.7 dB only beyond 1 mm |
| ±5 % on every L and C, ±0.10 mm on every stub, 400 trials | median **−21.4 dB**, 10–90 % **−19.5 … −23.5 dB**, meets −10 dB in **100 %** of trials |
| R_opt = 7 Ω (PA more compressed than assumed) | −13.76 dB |
| R_opt = 12 Ω | −22.15 dB |
| receive tap open instead of grounded at TR_SW | −12.11 dB worst (fv = 20 %) |

The design survives every one of these variants above −10 dB. The two that eat the most margin are
**R_opt below 8 Ω** and **the RX tap being open rather than grounded in TX** — both are modelling
assumptions, not measurements (§7).

---

## 7. Residual risk — what fabrication and a VNA must settle

Stated plainly, in order of how much it can move the answer:

1. **The In1 plane is 3V3, not ground.** This model treats it as a solid reference and only
   parameterises its *voids*. In reality a power plane with 11 % void and no local stitching is a
   poor and lossy RF reference; it also carries digital switching current under the RF run. The
   effective height sweep bounds the *impedance* consequence (≤ −15.7 dB across 0.10–0.58 mm) but
   **cannot** bound coupling from whatever else is on 3V3. The only real fix is a ground pour with a
   stitching fence along the trace, which is a layout change and outside this assignment.
2. **R_opt = 10.07 Ω is a load-line estimate, not a load-pull measurement.** TI does not publish the
   CC1190's optimum load impedance in SWRS089; AN001/SWRA090 was not available. Margin holds at
   −13.8 dB for R_opt = 7 Ω and −22.2 dB at 12 Ω, but a substantially lower optimum would need a re-tune.
3. **Component tolerance in situ is larger than the ±5 % modelled.** At 1.0–1.5 nH the 0402 body
   inductance is comparable to the pad and trace inductance, so L48/L49 will read high. Expect the
   built board to need one iteration on L48/L49 — tune those two against a VNA, in that order
   (L49 first: it dominates).
4. **The TR_SW state in TX is assumed, not known.** Grounded (used for the headline numbers) vs open
   costs about 12 dB of margin: −24.5 dB vs −12.1 dB.
5. **C94 = 2.7 pF across L48 is a fine-tune whose value depends on assumptions 1–3.** If it is left
   unfitted the design still meets the target by 9 dB, which is the safer build.

### What a VNA must confirm (all currently UNVERIFIED)

* **S11 at J40, 902–928 MHz, board powered, PA in TX** — the only number that settles the design. No
  VNA measurement of any kind exists for this board in the repo; every figure here is modelled.
* TDR or a swept S11 with the PA plane terminated in 10 Ω, to establish the real Z0 of the 19 mm run
  and hence the true void/effective-height condition.
* The actual void fraction and copper coverage of In1 under the RF corridor (the 11.14 % figure is
  carried from the brief; nothing in the repo computes it).
* Load-pull or a power sweep of the CC1190 at 3.3 V to replace R_opt = 10.07 Ω with a measured value.
* No full-wave solver was run. openEMS exists for WSL but was not used: no simulation of the plane
  void, no 3-D model of the U.FL launch or the 3V3 reference.

---

## 8. Reproducing this

```
# netlist and geometry
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" sch export netlist --format kicadxml \
    -o evidence/da-match-design/main_rev_b.net.xml hardware/main/rev_b/main_rev_b.kicad_sch
"C:/Program Files/KiCad/9.0/bin/python.exe" scripts/da_match_pcb_geom.py > .../pcb_geom.json

# model, validation, synthesis, tables  (system python 3.12 + scikit-rf 1.9.0)
python scripts/da_match_model.py       # media table + as-built result
python scripts/da_match_criterion.py   # why R_opt, not 50 ohm, is the criterion
python scripts/da_match_xcheck.py      # validation 1: admittance walk   (8e-16)
python scripts/da_match_nodal.py       # validation 2: nodal solve       (1e-14)
python scripts/da_match_synth.py       # E12 grid + E24 coordinate descent
python scripts/da_match_e24.py         # strict E24 re-refinement
python scripts/da_match_final.py       # results.json, sweep_915.csv
python scripts/da_match_tables.py      # tables.txt
python scripts/da_match_profile.py     # nodewalk.txt
python scripts/da_match_sens.py        # effective-height sweep (§6, §7)
```

Provenance of every number: **analytical / transmission-line model** (scikit-rf `MLine` + ABCD
cascade), never a solver result. The only measured inputs are the KiCad board data (track lengths,
pad positions, stackup) and the host-supplied 11.14 % void fraction. Files in this directory:

| file | what |
|---|---|
| `main_rev_b.net.xml` | netlist export the topology is read from |
| `pcb_geom.json` | track, pad, zone and stackup dump |
| `cc1190_text.txt` | extracted CC1190 datasheet text (Table 1 reference values) |
| `results.json` | all Γ / Zin tables, Monte Carlo, R_opt sweep |
| `sweep_915.csv` | 521-point Γ and Zin, current and proposed, four void fractions |
| `e24_refine.json` | final E24 search results and per-void optima |
| `synth_search.json` | first-pass E12 grid and descent |
| `tables.txt` | human-readable tables quoted above |
| `nodewalk.txt` | node-by-node impedance walk of the as-built network |